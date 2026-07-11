"""Chốt ngày sản xuất — orchestrator (spec 5.4) + huỷ ngược (on_cancel_ngay).

Mọi Work Order + Stock Entry sinh LÚC CHỐT NGÀY với số liệu thực tế,
skip_transfer=1 (D8). RM pick batch FIFO qua use_serial_batch_fields + batch_no
(bundle tự sinh khi submit — đã đối chiếu source erpnext v16
stock_controller.make_bundle_using_old_serial_batch_fields).

GATE-B (SalaryProduct): schema app lam-luong chưa chốt với Chiến — bước 5 dùng
mapping ADAPTIVE đọc meta lúc runtime; không map được thì báo lỗi tiếng Việt rõ
ràng và rollback (không để trạng thái nửa vời). Xem _sinh_salary_product.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from sx.api.common import QUAN_LY, TO_TRUONG, _guard
from sx.utils import get_bom_tang_1, get_settings, sinh_ma_lo


@frappe.whitelist()
def chot_ngay(ngay_sx):
    """Chốt ngày: validate -> tầng 1 -> bảng vào hộp -> tầng 2 -> SalaryProduct
    -> tổng hợp + submit phiếu. Lỗi giữa chừng: rollback toàn bộ, báo rõ bước hỏng."""
    _guard([TO_TRUONG, QUAN_LY])
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)

    buoc = _("kiểm tra điều kiện")
    try:
        _validate_truoc_chot(doc)

        wo1 = se1 = batch_btp = None
        if doc.chay_tang_1:
            buoc = _("tầng 1 (rang bột)")
            wo1, se1, batch_btp = _chot_tang_1(doc)

        buoc = _("submit bảng vào hộp")
        bang = _submit_bang_vao_hop(doc)

        ket_qua_tang_2 = {}
        if bang:
            buoc = _("tầng 2 (thành phẩm)")
            ket_qua_tang_2 = _chot_tang_2(doc, bang)

            buoc = _("sinh SalaryProduct (lương sản phẩm)")
            ds_salary = _sinh_salary_product(doc, bang)
            doc.salary_products_json = json.dumps(ds_salary)

        buoc = _("tổng hợp + submit phiếu ngày")
        _hoan_tat(doc, bang, wo1, se1, batch_btp, ket_qua_tang_2)
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
        "tong_hop": doc.tong_hop,
        "tong_luong_sp": doc.tong_luong_sp,
        "btp_thuc_te_kg": doc.btp_thuc_te_kg,
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
        ("item_btp", "Item bột BTP"),
        ("kho_nvl", "Kho NVL"),
        ("kho_btp", "Kho BTP"),
        ("kho_tp", "Kho TP"),
    ):
        if not settings.get(f):
            frappe.throw(_("SX Settings chưa cấu hình: {0}").format(label))

    if doc.chay_tang_1:
        # ≥1 bản ghi CCP và mọi bản ghi lệch phải có hành động khắc phục
        ccp = frappe.get_all(
            "SX Ghi Nhan CCP",
            filters={"ngay_sx": doc.name},
            fields=["name", "dat", "hanh_dong_khac_phuc"],
        )
        if not ccp:
            frappe.throw(
                _("Hôm nay có rang nhưng CHƯA ghi lần CCP nào. Ghi ít nhất 1 lần "
                  "nhiệt độ rang rồi mới chốt được.")
            )
        thieu = [r.name for r in ccp if not r.dat and not (r.hanh_dong_khac_phuc or "").strip()]
        if thieu:
            frappe.throw(
                _("Bản ghi CCP lệch chưa có hành động khắc phục: {0}").format(
                    ", ".join(thieu)
                )
            )
        if flt(doc.dau_vao_kg) <= 0:
            frappe.throw(_("Số bao đậu / khối lượng bao chưa hợp lệ"))

    # Mọi mẻ trộn của ngày phải đã submit
    me_nhap = frappe.get_all(
        "SX Me Tron", filters={"ngay_sx": doc.name, "docstatus": 0}, pluck="name"
    )
    if me_nhap:
        frappe.throw(
            _("Mẻ trộn còn ở trạng thái nháp: {0}. Submit hết rồi mới chốt.").format(
                ", ".join(me_nhap)
            )
        )

    if doc.san_pham_tang_2:
        bang = frappe.db.get_value(
            "SX Bang Vao Hop",
            {"ngay_sx": doc.name, "docstatus": ("<", 2)},
            ["name", "tong_hop"],
            as_dict=True,
        )
        if not bang or not cint(bang.tong_hop):
            frappe.throw(
                _("Có sản phẩm đóng hộp hôm nay nhưng bảng vào hộp chưa có/tổng = 0.")
            )

    _kiem_ton_kho(doc, settings)


def _nhu_cau_bom(bom_name, qty_fg):
    """Explode 1 cấp BOM: {item_code: stock_qty cần} cho qty_fg thành phẩm."""
    bom = frappe.get_cached_doc("BOM", bom_name)
    he_so = flt(qty_fg) / flt(bom.quantity or 1)
    nhu_cau = {}
    for r in bom.items:
        nhu_cau[r.item_code] = nhu_cau.get(r.item_code, 0) + flt(r.stock_qty) * he_so
    return nhu_cau


def _kiem_ton_kho(doc, settings):
    """Kiểm đủ tồn NVL/BTP TRƯỚC khi tạo chứng từ — báo thiếu cụ thể (spec 5.4.1)."""
    thieu = []

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

    btp_hom_nay = 0.0
    if doc.chay_tang_1:
        for item_code, can in _nhu_cau_bom(get_bom_tang_1(), flt(doc.btp_du_kien_kg)).items():
            _check(item_code, settings.kho_nvl, can)
        btp_hom_nay = flt(doc.btp_du_kien_kg)

    bang = _lay_bang_vao_hop(doc)
    if bang:
        for sp, so_hop in _tong_hop_theo_sp(bang).items():
            bom_sp = frappe.db.get_value(
                "BOM", {"item": sp, "is_active": 1, "is_default": 1, "docstatus": 1}, "name"
            )
            if not bom_sp:
                frappe.throw(_("Sản phẩm {0} chưa có BOM active").format(sp))
            for item_code, can in _nhu_cau_bom(bom_sp, so_hop).items():
                if item_code == settings.item_btp:
                    # BTP rút từ kho BTP; bột rang hôm nay được cộng vào nguồn
                    _check(item_code, settings.kho_btp, can, cong_them=btp_hom_nay)
                else:
                    _check(item_code, settings.kho_nvl, can)

    if thieu:
        frappe.throw(
            _("Không đủ tồn kho để chốt ngày:") + "<br>" + "<br>".join(thieu)
        )


def _lay_bang_vao_hop(doc):
    ten = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": doc.name, "docstatus": ("<", 2)}, "name"
    )
    return frappe.get_doc("SX Bang Vao Hop", ten) if ten else None


def _tong_hop_theo_sp(bang):
    tong = {}
    for r in bang.dong:
        tong[r.san_pham] = tong.get(r.san_pham, 0) + cint(r.so_hop)
    return tong


# ─────────────────────────────────────────────── tạo Batch / WO / SE ──


def _tao_batch(item_code, doc):
    """Batch tạo TRƯỚC SE thành phẩm, mã lô {prefix}-{DDMMYY} (spec 2.7)."""
    batch = frappe.get_doc(
        {
            "doctype": "Batch",
            "batch_id": sinh_ma_lo(item_code, doc.ngay),
            "item": item_code,
            "custom_ngay_sx": doc.name,
        }
    )
    batch.flags.ignore_permissions = True
    batch.insert()
    return batch.name


def _tao_wo(doc, item_code, qty, bom_no, source_wh, fg_wh, uom=None):
    """Work Order skip_transfer=1 (D8) — guard role đã qua, thao tác ignore_permissions."""
    settings = get_settings()
    wo = frappe.get_doc(
        {
            "doctype": "Work Order",
            "company": settings.cong_ty,
            "production_item": item_code,
            "qty": qty,
            "bom_no": bom_no,
            "skip_transfer": 1,
            "source_warehouse": source_wh,
            "fg_warehouse": fg_wh,
            "wip_warehouse": fg_wh,  # không dùng vì skip_transfer, chỉ để thoả reqd
            "planned_start_date": str(doc.ngay),
            "custom_ngay_sx": doc.name,
        }
    )
    wo.flags.ignore_permissions = True
    wo.insert()
    wo.submit()
    return wo


def _tao_se_manufacture(doc, wo, qty, batch_fg, override_wh=None):
    """SE Manufacture từ WO: RM pick batch FIFO, FG gắn batch đã tạo.

    override_wh: {item_code: warehouse} để đổi kho nguồn từng RM (BOT-NC lấy từ kho BTP).
    """
    from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

    se = frappe.get_doc(make_stock_entry(wo.name, "Manufacture", qty))
    se.custom_ngay_sx = doc.name
    se.set_posting_time = 1
    se.posting_date = str(doc.ngay)

    for row in se.items:
        if row.get("is_finished_item"):
            row.use_serial_batch_fields = 1
            row.batch_no = batch_fg
        elif override_wh and row.item_code in override_wh:
            row.s_warehouse = override_wh[row.item_code]

    _gan_batch_fifo(se)

    se.flags.ignore_permissions = True
    se.insert()
    se.submit()
    return se


def _gan_batch_fifo(se):
    """Gán batch FIFO cho dòng RM có has_batch_no; 1 dòng có thể tách nhiều batch.

    get_batch_qty trả batch theo chiến lược pick của Stock Settings (mặc định FIFO)
    -> bột cũ dùng trước, gồm cả batch rang hôm nay (đã submit ở tầng 1).
    """
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


# ───────────────────────────────────────────────────── tầng 1 / tầng 2 ──


def _chot_tang_1(doc):
    settings = get_settings()
    qty_btp = flt(doc.btp_du_kien_kg)  # D4: BTP thực tế = dự kiến từ yield BOM
    batch = _tao_batch(settings.item_btp, doc)
    wo = _tao_wo(
        doc, settings.item_btp, qty_btp, get_bom_tang_1(), settings.kho_nvl, settings.kho_btp
    )
    se = _tao_se_manufacture(doc, wo, qty_btp, batch)
    return wo.name, se.name, batch


def _submit_bang_vao_hop(doc):
    bang = _lay_bang_vao_hop(doc)
    if not bang:
        return None
    if bang.docstatus == 0:
        bang.flags.ignore_permissions = True
        bang.submit()
    return bang


def _chot_tang_2(doc, bang):
    """Mỗi SP có hộp trong bảng: Batch TP -> WO -> SE Manufacture.
    Trả {san_pham: {"so_hop","wo","se","batch"}}."""
    settings = get_settings()
    ket_qua = {}
    tong_theo_sp = _tong_hop_theo_sp(bang)

    # SP có trong bảng nhưng chưa tick lúc mở ngày -> tự bổ sung dòng (0 chạm)
    da_tick = {r.san_pham for r in doc.san_pham_tang_2}
    for sp in tong_theo_sp:
        if sp not in da_tick:
            doc.append("san_pham_tang_2", {"san_pham": sp})

    for sp, so_hop in tong_theo_sp.items():
        if so_hop <= 0:
            continue
        bom_sp = frappe.db.get_value(
            "BOM", {"item": sp, "is_active": 1, "is_default": 1, "docstatus": 1}, "name"
        )
        batch = _tao_batch(sp, doc)
        wo = _tao_wo(doc, sp, so_hop, bom_sp, settings.kho_nvl, settings.kho_tp)
        # BOT-NC rút từ kho BTP (bột cũ FIFO trước, gồm batch hôm nay); còn lại kho NVL
        se = _tao_se_manufacture(
            doc, wo, so_hop, batch, override_wh={settings.item_btp: settings.kho_btp}
        )
        ket_qua[sp] = {"so_hop": so_hop, "wo": wo.name, "se": se.name, "batch": batch}
    return ket_qua


# ─────────────────────────────────────────────── bước 5: SalaryProduct ──

# GATE-B: mapping field ứng viên — xác nhận schema thật bằng
# `frappe.get_meta("SalaryProduct").as_dict()` trên site rồi chốt với Chiến.
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
    """1 bản ghi SalaryProduct / dòng bảng vào hộp (spec 5.4.5, GATE-B adaptive).

    Không tìm được doctype hoặc không map nổi field tối thiểu (employee, qty)
    -> throw rõ ràng (rollback toàn bộ chốt ngày, không nửa vời).
    """
    dt = _salary_doctype()
    if not dt:
        frappe.throw(
            _("Không tìm thấy DocType SalaryProduct (app lam-luong). "
              "GATE-B: chạy frappe.get_meta('SalaryProduct') trên site, chốt mapping "
              "với Chiến rồi cập nhật _FIELD_CANDIDATES trong sx/api/chot.py.")
        )
    meta = frappe.get_meta(dt)
    mapping = _map_salary_fields(meta)
    if "employee" not in mapping or "qty" not in mapping:
        frappe.throw(
            _("Schema {0} không khớp mapping tối thiểu (employee, qty). "
              "GATE-B: chốt mapping với Chiến rồi cập nhật sx/api/chot.py. "
              "Field hiện có: {1}").format(
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


# ─────────────────────────────────────────────── bước 6: hoàn tất ──


def _hoan_tat(doc, bang, wo1, se1, batch_btp, ket_qua_tang_2):
    if doc.chay_tang_1:
        doc.btp_thuc_te_kg = flt(doc.btp_du_kien_kg)
        doc.wo_tang_1 = wo1
        doc.se_tang_1 = se1
        doc.batch_btp = batch_btp
    for row in doc.san_pham_tang_2:
        kq = ket_qua_tang_2.get(row.san_pham)
        if kq:
            row.so_hop_thuc_te = kq["so_hop"]
            row.wo = kq["wo"]
            row.se = kq["se"]
            row.batch_tp = kq["batch"]
        else:
            row.so_hop_thuc_te = 0
    doc.tong_hop = cint(bang.tong_hop) if bang else 0
    doc.tong_luong_sp = flt(bang.tong_tien) if bang else 0
    doc.flags.tu_chot_ngay = True
    doc.save()
    doc.submit()


# ─────────────────────────────────────────────── huỷ ngược (hook) ──


def on_cancel_ngay(doc, method=None):
    """Huỷ chuỗi ngược: SE tầng 2 -> WO tầng 2 -> SE tầng 1 -> WO tầng 1
    -> xoá SalaryProduct. Batch giữ nguyên (đã có ledger) — ghi chú lại (spec 2.1)."""
    log = []

    def _cancel(doctype, ten):
        if not ten:
            return
        d = frappe.get_doc(doctype, ten)
        if d.docstatus == 1:
            d.flags.ignore_permissions = True
            d.cancel()
            log.append(f"Huỷ {doctype} {ten}")

    for row in doc.san_pham_tang_2:
        _cancel("Stock Entry", row.se)
    for row in doc.san_pham_tang_2:
        _cancel("Work Order", row.wo)
    _cancel("Stock Entry", doc.se_tang_1)
    _cancel("Work Order", doc.wo_tang_1)

    # Bảng vào hộp huỷ theo để mở lại được ngày (amend)
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

    batches = [b for b in [doc.batch_btp] + [r.batch_tp for r in doc.san_pham_tang_2] if b]
    if batches:
        log.append(
            "Batch giữ nguyên (đã có ledger, không xoá được): " + ", ".join(batches)
        )

    if log:
        ghi_chu = (doc.ghi_chu or "") + "\n[Huỷ ngày] " + "; ".join(log)
        doc.db_set("ghi_chu", ghi_chu.strip(), update_modified=False)
