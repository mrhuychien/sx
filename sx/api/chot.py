"""Chốt ngày sản xuất v3 (spec §5.4) + huỷ ngược (on_cancel_ngay).

Sinh T2 (mẻ trộn/nấu theo bao_me, topo-sort theo phụ thuộc BOM: màu → đường hoán →
bột bánh/bột đậu) rồi T3 (TP theo bảng vào hộp). KHÔNG xử lý T1 (đậu đã trừ ở
SX Nhap Bot — D7). RM FIFO toàn tuyến. try/except toàn khối + rollback.

GATE-B (SalaryProduct): mapping ADAPTIVE đọc meta runtime; không map được -> báo
lỗi rõ + rollback. Chốt mapping cứng sau khi chủ đầu tư duyệt.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from sx.api.mfg import cancel_doc, tao_batch, tao_se_manufacture, tao_wo
from sx.config.roles import guard_card
from sx.utils import get_bom_active, get_settings, sinh_ma_lo, topo_rank_by_bom


@frappe.whitelist()
def chot_ngay(ngay_sx):
    """Chốt ngày: validate -> T2 (topo) -> submit vào hộp -> T3 -> SalaryProduct
    -> tổng hợp + submit. Lỗi giữa chừng: rollback toàn bộ, báo bước hỏng."""
    guard_card("chotngay")
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)

    buoc = _("kiểm tra điều kiện")
    canh_bao = []
    try:
        bang = _validate_truoc_chot(doc)

        chung_tu = []  # [{dt, name}] theo thứ tự sinh — để huỷ ngược

        buoc = _("tầng 2 (nấu + trộn theo báo mẻ)")
        _chot_tang_2(doc, chung_tu)

        buoc = _("submit bảng vào hộp")
        if bang and bang.docstatus == 0:
            bang.flags.ignore_permissions = True
            bang.submit()

        ket_qua_tp = {}
        ds_salary = []
        if bang:
            buoc = _("tầng 3 (thành phẩm)")
            ket_qua_tp = _chot_tang_3(doc, bang, chung_tu)

            buoc = _("sinh SalaryProduct (lương sản phẩm)")
            ds_salary = _sinh_salary_product(doc, bang)

        buoc = _("tổng hợp + submit phiếu ngày")
        doc.tong_hop_tp = cint(bang.tong_hop) if bang else 0
        doc.tong_luong_sp = flt(bang.tong_tien) if bang else 0
        doc.ds_wo_se = json.dumps(chung_tu)
        doc.salary_products_json = json.dumps(ds_salary)
        doc.flags.tu_chot_ngay = True
        doc.save()
        doc.submit()

        canh_bao = _canh_bao_mem(doc)
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
        "canh_bao": canh_bao,
    }


# ─────────────────────────────────────────────── validate ──


def _validate_truoc_chot(doc):
    if doc.docstatus == 1:
        frappe.throw(_("Phiếu ngày {0} ĐÃ chốt rồi.").format(doc.name))
    if doc.docstatus == 2:
        frappe.throw(_("Phiếu ngày {0} đã huỷ.").format(doc.name))

    settings = get_settings()
    for f, label in (
        ("cong_ty", "Công ty"),
        ("kho_nvl", "Kho NVL"),
        ("kho_btp", "Kho BTP"),
        ("kho_tp", "Kho TP"),
    ):
        if not settings.get(f):
            frappe.throw(_("SX Settings chưa cấu hình: {0}").format(label))

    ten_bang = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": doc.name, "docstatus": ("<", 2)}, "name"
    )
    bang = frappe.get_doc("SX Bang Vao Hop", ten_bang) if ten_bang else None

    # Ít nhất một trong {bao_me có dòng, bảng vào hộp có dòng} — ngày rỗng vô nghĩa
    co_bao_me = len(doc.bao_me) > 0
    co_vao_hop = bool(bang and cint(bang.tong_hop) > 0)
    if not co_bao_me and not co_vao_hop:
        frappe.throw(
            _("Ngày chưa có báo mẻ lẫn bảng vào hộp — không có gì để chốt.")
        )

    if bang and bang.docstatus == 0:
        # Controller lookup đơn giá khi save — save lại để chắc mọi dòng có giá
        bang.flags.ignore_permissions = True
        bang.save()

    _kiem_ton_kho(doc, bang, settings)
    return bang


def _kho_nguon(item_code, settings):
    """RM nhóm BTP (bột nền/đường hoán/màu/bột bánh/bột đậu) rút Kho BTP; còn lại Kho NVL."""
    nhom = frappe.get_cached_value("Item", item_code, "custom_sx_nhom") or ""
    return settings.kho_btp if nhom.startswith("BTP") else settings.kho_nvl


def _nhu_cau_bom(bom_name, qty_fg):
    """Explode 1 cấp BOM (use_multi_level_bom=0): {item_code: stock_qty cần}."""
    bom = frappe.get_cached_doc("BOM", bom_name)
    he_so = flt(qty_fg) / flt(bom.quantity or 1)
    nhu_cau = {}
    for r in bom.items:
        # Non-stock (Nước) không tính vào nhu cầu kho
        if not cint(frappe.get_cached_value("Item", r.item_code, "is_stock_item")):
            continue
        nhu_cau[r.item_code] = nhu_cau.get(r.item_code, 0) + flt(r.stock_qty) * he_so
    return nhu_cau


def _tong_hop_theo_sp(bang):
    tong = {}
    for r in bang.dong:
        tong[r.san_pham] = tong.get(r.san_pham, 0) + cint(r.so_hop)
    return tong


def _kiem_ton_kho(doc, bang, settings):
    """Kiểm đủ tồn TRƯỚC khi sinh chứng từ. BTP sinh trong chốt (bao_me) được cộng
    tín dụng (xấp xỉ — FIFO thật ở bước sinh sẽ bắt thiếu chính xác & rollback)."""
    thieu = []
    sx_hom_nay = {}
    for row in doc.bao_me:
        sx_hom_nay[row.item_btp] = sx_hom_nay.get(row.item_btp, 0) + flt(row.tong_kg)

    def _check(item_code, kho, can):
        ton = flt(
            frappe.db.get_value(
                "Bin", {"item_code": item_code, "warehouse": kho}, "actual_qty"
            )
        ) + flt(sx_hom_nay.get(item_code, 0))
        if ton + 1e-6 < can:
            thieu.append(
                _("- {0} tại {1}: cần {2}, tồn {3}").format(
                    item_code, kho, flt(can, 3), flt(ton, 3)
                )
            )

    for row in doc.bao_me:
        bom = get_bom_active(row.item_btp)
        if not bom:
            frappe.throw(_("BTP {0} chưa có BOM active").format(row.item_btp))
        for item_code, can in _nhu_cau_bom(bom, flt(row.tong_kg)).items():
            _check(item_code, _kho_nguon(item_code, settings), can)

    if bang:
        for sp, so_hop in _tong_hop_theo_sp(bang).items():
            bom_sp = get_bom_active(sp)
            if not bom_sp:
                frappe.throw(_("Sản phẩm {0} chưa có BOM active").format(sp))
            for item_code, can in _nhu_cau_bom(bom_sp, so_hop).items():
                _check(item_code, _kho_nguon(item_code, settings), can)

    if thieu:
        frappe.throw(
            _("Không đủ tồn kho để chốt ngày (có thể quên nhập bột / báo mẻ / thiếu NVL):")
            + "<br>" + "<br>".join(thieu)
        )


# ─────────────────────────────────────────────── T2 / T3 ──


def _chot_tang_2(doc, chung_tu):
    """Mỗi dòng bao_me (topo-sort: màu → đường hoán → bột bánh/bột đậu):
    Batch -> WO -> SE Manufacture (RM FIFO, FG vào Kho BTP)."""
    settings = get_settings()
    rank = topo_rank_by_bom([r.item_btp for r in doc.bao_me])
    rows = sorted(doc.bao_me, key=lambda r: rank.get(r.item_btp, 0))

    for row in rows:
        qty = flt(row.tong_kg)
        if qty <= 0:
            continue
        bom = get_bom_active(row.item_btp)
        batch = tao_batch(row.item_btp, sinh_ma_lo(row.item_btp, doc.ngay), ngay_sx=doc.name)
        wo = tao_wo(
            settings.cong_ty, row.item_btp, qty, bom,
            source_wh=settings.kho_nvl, fg_wh=settings.kho_btp,
            ngay_sx=doc.name, planned_date=doc.ngay,
        )
        se = tao_se_manufacture(
            wo, qty, batch,
            kho_nguon=lambda item: _kho_nguon(item, settings),
            ngay=doc.ngay, ngay_sx=doc.name,
        )
        row.batch, row.wo, row.se = batch, wo.name, se.name
        chung_tu.append({"dt": "Work Order", "name": wo.name})
        chung_tu.append({"dt": "Stock Entry", "name": se.name})


def _chot_tang_3(doc, bang, chung_tu):
    """Mỗi SKU trong bảng vào hộp: Batch TP -> WO -> SE (RM bột bánh/đậu FIFO Kho BTP
    + bao bì Kho NVL; FG vào Kho TP). Trả {sku: batch}."""
    settings = get_settings()
    ket_qua = {}
    for sp, so_hop in _tong_hop_theo_sp(bang).items():
        if so_hop <= 0:
            continue
        bom_sp = get_bom_active(sp)
        batch = tao_batch(sp, sinh_ma_lo(sp, doc.ngay), ngay_sx=doc.name)
        wo = tao_wo(
            settings.cong_ty, sp, so_hop, bom_sp,
            source_wh=settings.kho_nvl, fg_wh=settings.kho_tp,
            ngay_sx=doc.name, planned_date=doc.ngay,
        )
        se = tao_se_manufacture(
            wo, so_hop, batch,
            kho_nguon=lambda item: _kho_nguon(item, settings),
            ngay=doc.ngay, ngay_sx=doc.name,
        )
        ket_qua[sp] = batch
        chung_tu.append({"dt": "Work Order", "name": wo.name})
        chung_tu.append({"dt": "Stock Entry", "name": se.name})
    return ket_qua


# ─────────────────────────────────────────────── SalaryProduct (GATE-B) ──

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
    """1 bản ghi SalaryProduct / dòng bảng vào hộp (GATE-B adaptive)."""
    dt = _salary_doctype()
    if not dt:
        frappe.throw(
            _("Không tìm thấy DocType SalaryProduct (app lam-luong). GATE-B: chạy "
              "frappe.get_meta('SalaryProduct') trên site, chốt mapping rồi cập nhật "
              "_FIELD_CANDIDATES trong sx/api/chot.py.")
        )
    meta = frappe.get_meta(dt)
    mapping = _map_salary_fields(meta)
    if "employee" not in mapping or "qty" not in mapping:
        frappe.throw(
            _("Schema {0} không khớp mapping tối thiểu (employee, qty). GATE-B: chốt "
              "mapping rồi cập nhật sx/api/chot.py. Field hiện có: {1}").format(
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


# ─────────────────────────────────────────────── cảnh báo mềm ──


def _canh_bao_mem(doc):
    """Không chặn: tồn bột bánh loại < lượng cán báo (dấu hiệu quên báo mẻ trộn)."""
    settings = get_settings()
    canh_bao = []
    can_theo_loai = {}
    for row in doc.bao_can:
        can_theo_loai[row.item_bot_banh] = can_theo_loai.get(row.item_bot_banh, 0) + flt(row.so_me)
    for item, so_me_can in can_theo_loai.items():
        bom = get_bom_active(item)
        co_me = flt(frappe.db.get_value("BOM", bom, "custom_co_me_chuan_kg")) if bom else 0
        kg_can = so_me_can * co_me
        ton = flt(
            frappe.db.get_value(
                "Bin", {"item_code": item, "warehouse": settings.kho_btp}, "actual_qty"
            )
        )
        if kg_can > ton + 1e-6:
            canh_bao.append(
                _("Cán {0} ({1} kg) nhiều hơn tồn bột bánh ({2} kg) — có thể quên báo mẻ trộn.")
                .format(item, flt(kg_can, 1), flt(ton, 1))
            )
    return canh_bao


# ─────────────────────────────────────────────── huỷ ngược (hook) ──


def on_cancel_ngay(doc, method=None):
    """Huỷ chuỗi ngược theo ds_wo_se (đảo thứ tự: SE T3 -> WO T3 -> SE T2 -> WO T2)
    -> huỷ bảng vào hộp -> xoá SalaryProduct. Batch giữ. KHÔNG đụng SX Nhap Bot."""
    log = []
    chung_tu = json.loads(doc.ds_wo_se) if doc.ds_wo_se else []
    for ct in reversed(chung_tu):
        cancel_doc(ct.get("dt"), ct.get("name"), log)

    bang = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": doc.name, "docstatus": 1}, "name"
    )
    cancel_doc("SX Bang Vao Hop", bang, log)

    dt = _salary_doctype()
    if dt and doc.salary_products_json:
        for ten in json.loads(doc.salary_products_json):
            if frappe.db.exists(dt, ten):
                frappe.delete_doc(dt, ten, ignore_permissions=True, force=True)
                log.append(f"Xoá {dt} {ten}")

    batches = [r.batch for r in doc.bao_me if r.batch]
    if batches:
        log.append("Batch giữ nguyên (đã có ledger): " + ", ".join(batches))

    if log:
        ghi_chu = (doc.ghi_chu or "") + "\n[Huỷ ngày] " + "; ".join(log)
        doc.db_set("ghi_chu", ghi_chu.strip(), update_modified=False)
