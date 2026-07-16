"""Chốt ngày sản xuất v2 (spec §5.4) + huỷ ngược (on_cancel_ngay).

Chốt ngày sinh T2 (hỗn hợp theo báo mẻ) + T3 (TP theo bảng vào hộp).
KHÔNG xử lý T1 — bột đã nhập ở SX Nhap Bot (GATE-C=A), là tồn kho sẵn.
RM pick batch FIFO qua use_serial_batch_fields + batch_no (bundle tự sinh khi
submit — đã đối chiếu source erpnext v16). skip_transfer=1, use_multi_level_bom=0.

GATE-B (SalaryProduct): mapping ADAPTIVE đọc meta runtime; không map được ->
báo lỗi tiếng Việt rõ + rollback. Chốt mapping cứng sau khi chủ đầu tư duyệt.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from sx.api.common import QUAN_LY, TO_DONG_GOI, _guard
from sx.utils import (
    get_bom_active,
    get_settings,
    sinh_ma_lo_hh,
    sinh_ma_lo_tp,
)


@frappe.whitelist()
def chot_ngay(ngay_sx):
    """Chốt ngày: validate -> T2 hỗn hợp -> submit bảng vào hộp -> T3 TP
    -> SalaryProduct -> tổng hợp + submit. Lỗi giữa chừng: rollback toàn bộ."""
    _guard([TO_DONG_GOI, QUAN_LY])
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)

    buoc = _("kiểm tra điều kiện")
    try:
        bang = _validate_truoc_chot(doc)

        chung_tu = []  # [{dt, name}] theo thứ tự sinh — để huỷ ngược

        buoc = _("tầng 2 (trộn hỗn hợp)")
        _chot_tang_2(doc, chung_tu)

        buoc = _("submit bảng vào hộp")
        bang.flags.ignore_permissions = True
        if bang.docstatus == 0:
            bang.submit()

        buoc = _("tầng 3 (thành phẩm)")
        _chot_tang_3(doc, bang, chung_tu)

        buoc = _("sinh SalaryProduct (lương sản phẩm)")
        ds_salary = _sinh_salary_product(doc, bang)

        buoc = _("tổng hợp + submit phiếu ngày")
        doc.tong_hop_tp = cint(bang.tong_hop)
        doc.tong_luong_sp = flt(bang.tong_tien)
        doc.ds_wo_se = json.dumps(chung_tu)
        doc.salary_products_json = json.dumps(ds_salary)
        doc.flags.tu_chot_ngay = True
        doc.save()
        doc.submit()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(
            title=f"chot_ngay {ngay_sx} hỏng ở bước: {buoc}",
            message=frappe.get_traceback(),
        )
        frappe.throw(
            _("Chốt ngày THẤT BẠI ở bước: {0}. Toàn bộ đã được hoàn tác — "
              "không có trạng thái nửa vời. Chi tiết trong Error Log.").format(buoc)
        )

    return {
        "name": doc.name,
        "trang_thai": doc.trang_thai,
        "tong_hop_tp": doc.tong_hop_tp,
        "tong_luong_sp": doc.tong_luong_sp,
    }


# ─────────────────────────────────────────────── bước 1: validate chặn ──


def _validate_truoc_chot(doc):
    if doc.docstatus == 1:
        frappe.throw(_("Phiếu ngày {0} ĐÃ chốt rồi.").format(doc.name))
    if doc.docstatus == 2:
        frappe.throw(_("Phiếu ngày {0} đã huỷ.").format(doc.name))

    settings = get_settings()
    for f, label in (
        ("cong_ty", "Công ty"),
        ("item_bot", "Item bột BTP"),
        ("kho_nvl", "Kho NVL"),
        ("kho_btp", "Kho BTP"),
        ("kho_tp", "Kho TP"),
    ):
        if not settings.get(f):
            frappe.throw(_("SX Settings chưa cấu hình: {0}").format(label))

    # Bảng vào hộp bắt buộc — đây là sản lượng TP (spec §5.4.1)
    ten_bang = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": doc.name, "docstatus": ("<", 2)}, "name"
    )
    if not ten_bang:
        frappe.throw(_("Chưa có bảng vào hộp — không có sản lượng TP để chốt."))
    bang = frappe.get_doc("SX Bang Vao Hop", ten_bang)
    if not cint(bang.tong_hop):
        frappe.throw(_("Bảng vào hộp tổng = 0 hộp — không có gì để chốt."))
    # Đơn giá: controller đã lookup khi save; save lại để chắc mọi dòng có giá
    if bang.docstatus == 0:
        bang.flags.ignore_permissions = True
        bang.save()

    _kiem_ton_kho(doc, bang, settings)
    return bang


def _nhu_cau_bom(bom_name, qty_fg):
    """Explode 1 cấp BOM: {item_code: stock_qty cần} cho qty_fg thành phẩm."""
    bom = frappe.get_cached_doc("BOM", bom_name)
    he_so = flt(qty_fg) / flt(bom.quantity or 1)
    nhu_cau = {}
    for r in bom.items:
        nhu_cau[r.item_code] = nhu_cau.get(r.item_code, 0) + flt(r.stock_qty) * he_so
    return nhu_cau


def _kho_nguon(item_code, settings):
    """RM nhóm BTP (bột/hỗn hợp) rút từ Kho BTP; còn lại từ Kho NVL."""
    nhom = frappe.get_cached_value("Item", item_code, "custom_sx_nhom") or ""
    return settings.kho_btp if nhom.startswith("BTP") else settings.kho_nvl


def _kiem_ton_kho(doc, bang, settings):
    """Kiểm đủ tồn TRƯỚC khi tạo chứng từ — báo thiếu cụ thể (spec §5.4.1).
    Tồn hỗn hợp được cộng thêm lượng sinh ra ở T2 trong cùng lần chốt."""
    thieu = []
    hh_sinh_hom_nay = {}
    for row in doc.bao_me:
        hh_sinh_hom_nay[row.hon_hop] = (
            hh_sinh_hom_nay.get(row.hon_hop, 0) + flt(row.tong_kg)
        )

    def _check(item_code, kho, can, cong_them=0.0):
        ton = flt(
            frappe.db.get_value(
                "Bin", {"item_code": item_code, "warehouse": kho}, "actual_qty"
            )
        ) + flt(cong_them)
        if ton + 1e-6 < can:
            thieu.append(
                _("- {0} tại {1}: cần {2}, tồn {3}").format(
                    item_code, kho, flt(can, 3), flt(ton, 3)
                )
            )

    # T2: nhu cầu bột + phụ liệu cho từng dòng báo mẻ
    for row in doc.bao_me:
        bom = get_bom_active(row.hon_hop)
        if not bom:
            frappe.throw(_("Hỗn hợp {0} chưa có BOM active").format(row.hon_hop))
        for item_code, can in _nhu_cau_bom(bom, flt(row.tong_kg)).items():
            _check(item_code, _kho_nguon(item_code, settings), can)

    # T3: nhu cầu hỗn hợp + bao bì cho từng SKU
    for sp, so_hop in _tong_hop_theo_sp(bang).items():
        bom_sp = get_bom_active(sp)
        if not bom_sp:
            frappe.throw(_("Sản phẩm {0} chưa có BOM active").format(sp))
        for item_code, can in _nhu_cau_bom(bom_sp, so_hop).items():
            _check(
                item_code,
                _kho_nguon(item_code, settings),
                can,
                cong_them=hh_sinh_hom_nay.get(item_code, 0),
            )

    if thieu:
        frappe.throw(
            _("Không đủ tồn kho để chốt ngày (có thể quên báo mẻ / quên nhập bột):")
            + "<br>" + "<br>".join(thieu)
        )


def _tong_hop_theo_sp(bang):
    tong = {}
    for r in bang.dong:
        tong[r.san_pham] = tong.get(r.san_pham, 0) + cint(r.so_hop)
    return tong


# ─────────────────────────────────────────────── tạo Batch / WO / SE ──


def _tao_batch(item_code, batch_id, lo_rang=None):
    batch = frappe.get_doc(
        {
            "doctype": "Batch",
            "batch_id": batch_id,
            "item": item_code,
            "custom_lo_rang": lo_rang,
        }
    )
    batch.flags.ignore_permissions = True
    batch.insert()
    return batch.name


def _tao_wo(doc, item_code, qty, bom_no, fg_wh, chung_tu):
    """Work Order skip_transfer=1 (D11). Guard role đã qua -> ignore_permissions."""
    settings = get_settings()
    wo = frappe.get_doc(
        {
            "doctype": "Work Order",
            "company": settings.cong_ty,
            "production_item": item_code,
            "qty": qty,
            "bom_no": bom_no,
            "skip_transfer": 1,
            # BẮT BUỘC 0: BOM T3 chứa hỗn hợp (item có BOM riêng), BOM T2 chứa bột —
            # multi-level sẽ explode ngược phá kiến trúc 3 tầng (D1)
            "use_multi_level_bom": 0,
            "source_warehouse": settings.kho_nvl,
            "fg_warehouse": fg_wh,
            "wip_warehouse": fg_wh,  # không dùng vì skip_transfer, chỉ thoả reqd
            "planned_start_date": str(doc.ngay),
            "custom_ngay_sx": doc.name,
        }
    )
    wo.flags.ignore_permissions = True
    wo.insert()
    wo.submit()
    chung_tu.append({"dt": "Work Order", "name": wo.name})
    return wo


def _tao_se_manufacture(doc, wo, qty, batch_fg, chung_tu):
    """SE Manufacture từ WO: RM nhóm BTP đổi kho nguồn sang Kho BTP, pick batch
    FIFO (bột cũ / hỗn hợp cũ dùng trước — D6); FG gắn batch đã tạo."""
    from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

    settings = get_settings()
    se = frappe.get_doc(make_stock_entry(wo.name, "Manufacture", qty))
    se.custom_ngay_sx = doc.name
    se.set_posting_time = 1
    se.posting_date = str(doc.ngay)

    for row in se.items:
        if row.get("is_finished_item"):
            row.use_serial_batch_fields = 1
            row.batch_no = batch_fg
        elif row.s_warehouse:
            row.s_warehouse = _kho_nguon(row.item_code, settings)

    _gan_batch_fifo(se)

    se.flags.ignore_permissions = True
    se.insert()
    se.submit()
    chung_tu.append({"dt": "Stock Entry", "name": se.name})
    return se


def _gan_batch_fifo(se):
    """Gán batch FIFO cho dòng RM có has_batch_no; 1 dòng có thể tách nhiều batch.

    get_batch_qty trả batch theo chiến lược pick của Stock Settings (mặc định FIFO)
    -> lô R / batch hỗn hợp cũ nhất dùng trước (D6 — mắt xích truy xuất)."""
    from erpnext.stock.doctype.batch.batch import get_batch_qty

    them = []
    for row in list(se.items):
        if row.get("is_finished_item") or not row.s_warehouse:
            continue
        if not frappe.get_cached_value("Item", row.item_code, "has_batch_no"):
            continue
        batches = get_batch_qty(item_code=row.item_code, warehouse=row.s_warehouse) or []
        con_lai = flt(row.qty)
        phan = []
        for b in batches:
            if con_lai <= 1e-9:
                break
            lay = min(flt(b.get("qty")), con_lai)
            if lay <= 0:
                continue
            phan.append((b.get("batch_no"), lay))
            con_lai -= lay
        if con_lai > 1e-6:
            frappe.throw(
                _("Không đủ tồn theo lô cho {0} tại {1} (thiếu {2}).").format(
                    row.item_code, row.s_warehouse, flt(con_lai, 3)
                )
            )
        if not phan:
            continue
        row.use_serial_batch_fields = 1
        row.batch_no, row.qty = phan[0]
        for batch_no, qty in phan[1:]:
            mau = row.as_dict()
            for k in (
                "name", "idx", "parent", "parentfield", "parenttype",
                "owner", "creation", "modified", "modified_by", "docstatus",
                "serial_and_batch_bundle",
            ):
                mau.pop(k, None)
            mau.update({"qty": qty, "batch_no": batch_no, "use_serial_batch_fields": 1})
            them.append(mau)
    for mau in them:
        se.append("items", mau)


# ───────────────────────────────────────────────────── tầng 2 / tầng 3 ──


def _chot_tang_2(doc, chung_tu):
    """Mỗi dòng báo mẻ: Batch HH -> WO -> SE Manufacture (bột FIFO, FG vào Kho BTP)."""
    settings = get_settings()
    for row in doc.bao_me:
        qty_hh = flt(row.tong_kg)
        if qty_hh <= 0:
            continue
        bom = get_bom_active(row.hon_hop)
        batch = _tao_batch(row.hon_hop, sinh_ma_lo_hh(row.hon_hop, doc.ngay))
        wo = _tao_wo(doc, row.hon_hop, qty_hh, bom, settings.kho_btp, chung_tu)
        _tao_se_manufacture(doc, wo, qty_hh, batch, chung_tu)
        row.batch_hh = batch


def _chot_tang_3(doc, bang, chung_tu):
    """Mỗi SKU trong bảng vào hộp: Batch TP -> WO -> SE (hỗn hợp FIFO, FG vào Kho TP)."""
    settings = get_settings()
    for sp, so_hop in _tong_hop_theo_sp(bang).items():
        if so_hop <= 0:
            continue
        bom_sp = get_bom_active(sp)
        batch = _tao_batch(sp, sinh_ma_lo_tp(sp, doc.ngay))
        wo = _tao_wo(doc, sp, so_hop, bom_sp, settings.kho_tp, chung_tu)
        _tao_se_manufacture(doc, wo, so_hop, batch, chung_tu)


# ─────────────────────────────────────────────── bước 6: SalaryProduct ──

# GATE-B: mapping field ứng viên — xác nhận schema thật bằng
# frappe.get_meta("SalaryProduct").as_dict() trên site rồi chốt với chủ đầu tư.
_SALARY_DT_CANDIDATES = ("SalaryProduct", "Salary Product")
_FIELD_CANDIDATES = {
    "employee": ("employee", "nhan_vien", "nhanvien"),
    "date": ("date", "ngay", "posting_date", "transaction_date", "work_date"),
    "item": ("item", "item_code", "san_pham", "product", "sanpham"),
    "qty": ("qty", "quantity", "so_luong", "soluong", "so_hop"),
    "rate": ("rate", "don_gia", "dongia", "price"),
    "amount": ("amount", "thanh_tien", "thanhtien", "total", "total_amount"),
    "phuong_thuc": ("phuong_thuc", "phuongthuc", "method"),
    "ref": ("custom_ngay_sx", "ngay_sx", "reference", "ref_docname"),
}


def _salary_doctype():
    for dt in _SALARY_DT_CANDIDATES:
        if frappe.db.exists("DocType", dt):
            return dt
    return None


def _map_salary_fields(meta):
    fieldnames = {df.fieldname for df in meta.fields}
    mapping = {}
    for khoa, candidates in _FIELD_CANDIDATES.items():
        for c in candidates:
            if c in fieldnames:
                mapping[khoa] = c
                break
    return mapping


def _sinh_salary_product(doc, bang):
    """1 bản ghi SalaryProduct / dòng bảng vào hộp (GATE-B adaptive).

    Không tìm được doctype hoặc không map nổi (employee, qty) -> throw rõ ràng
    (rollback toàn bộ, không nửa vời)."""
    dt = _salary_doctype()
    if not dt:
        frappe.throw(
            _("Không tìm thấy DocType SalaryProduct (app lam-luong). "
              "GATE-B: chạy frappe.get_meta('SalaryProduct') trên site, chốt mapping "
              "rồi cập nhật _FIELD_CANDIDATES trong sx/api/chot.py.")
        )
    meta = frappe.get_meta(dt)
    mapping = _map_salary_fields(meta)
    if "employee" not in mapping or "qty" not in mapping:
        frappe.throw(
            _("Schema {0} không khớp mapping tối thiểu (employee, qty). "
              "GATE-B: chốt mapping rồi cập nhật sx/api/chot.py. Field hiện có: {1}").format(
                dt, ", ".join(sorted(df.fieldname for df in meta.fields if df.fieldname))
            )
        )

    ds_ten = []
    for r in bang.dong:
        sp_doc = frappe.new_doc(dt)
        sp_doc.set(mapping["employee"], r.nhan_vien)
        sp_doc.set(mapping["qty"], cint(r.so_hop))
        if "date" in mapping:
            sp_doc.set(mapping["date"], str(doc.ngay))
        if "item" in mapping:
            sp_doc.set(mapping["item"], r.san_pham)
        if "rate" in mapping:
            sp_doc.set(mapping["rate"], flt(r.don_gia))
        if "amount" in mapping:
            sp_doc.set(mapping["amount"], flt(r.thanh_tien))
        if "phuong_thuc" in mapping:
            sp_doc.set(mapping["phuong_thuc"], r.phuong_thuc)
        if "ref" in mapping:
            sp_doc.set(mapping["ref"], doc.name)
        sp_doc.flags.ignore_permissions = True
        sp_doc.insert()
        ds_ten.append(sp_doc.name)
    return ds_ten


# ─────────────────────────────────────────────── huỷ ngược (hook) ──


def on_cancel_ngay(doc, method=None):
    """Huỷ chuỗi ngược theo ds_wo_se: đảo thứ tự sinh (SE T3 -> WO T3 -> SE T2 -> WO T2)
    -> huỷ bảng vào hộp -> xoá SalaryProduct. Batch giữ nguyên (spec §5.4)."""
    log = []

    def _cancel(doctype, ten):
        if not ten or not frappe.db.exists(doctype, ten):
            return
        d = frappe.get_doc(doctype, ten)
        if d.docstatus == 1:
            d.flags.ignore_permissions = True
            d.cancel()
            log.append(f"Huỷ {doctype} {ten}")

    chung_tu = json.loads(doc.ds_wo_se) if doc.ds_wo_se else []
    for ct in reversed(chung_tu):
        _cancel(ct.get("dt"), ct.get("name"))

    bang = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": doc.name, "docstatus": 1}, "name"
    )
    _cancel("SX Bang Vao Hop", bang)

    dt = _salary_doctype()
    if dt and doc.salary_products_json:
        for ten in json.loads(doc.salary_products_json):
            if frappe.db.exists(dt, ten):
                frappe.delete_doc(dt, ten, ignore_permissions=True, force=True)
                log.append(f"Xoá {dt} {ten}")

    batches = [r.batch_hh for r in doc.bao_me if r.batch_hh]
    if batches:
        log.append(
            "Batch giữ nguyên (đã có ledger, không xoá được): " + ", ".join(batches)
        )

    if log:
        ghi_chu = (doc.ghi_chu or "") + "\n[Huỷ ngày] " + "; ".join(log)
        doc.db_set("ghi_chu", ghi_chu.strip(), update_modified=False)
