"""Helper Manufacture dùng chung (tang1 T1 + chot T2/T3).

Đọc từ source ERPNext v16 thật: make_stock_entry, get_batch_qty,
make_bundle_using_old_serial_batch_fields. FIFO qua use_serial_batch_fields=1 +
batch_no (bundle tự sinh khi submit). Non-stock (Nước) tự loại khỏi SE.
"""

import frappe
from frappe import _
from frappe.utils import flt


def tao_batch(item_code, batch_id, ngay_sx=None):
    """Batch tạo trước SE thành phẩm; batch_id đặt tay (D13).

    Idempotent: nếu Batch cùng batch_id đã tồn tại (vd huỷ + nhập lại lô R — batch
    bột nền dùng lại đúng lô R để giữ mắt xích truy xuất), tái dùng thay vì insert
    (tránh DuplicateEntryError). Khác item -> lỗi rõ ràng.
    """
    if frappe.db.exists("Batch", batch_id):
        cu = frappe.db.get_value("Batch", batch_id, "item")
        if cu != item_code:
            frappe.throw(
                _("Batch {0} đã tồn tại cho item khác ({1}), không dùng cho {2} được.").format(
                    batch_id, cu, item_code
                )
            )
        return batch_id
    batch = frappe.get_doc(
        {
            "doctype": "Batch",
            "batch_id": batch_id,
            "item": item_code,
            "custom_ngay_sx": ngay_sx,
        }
    )
    batch.flags.ignore_permissions = True
    batch.insert()
    return batch.name


def tao_wo(company, item_code, qty, bom_no, source_wh, fg_wh, ngay_sx=None, planned_date=None):
    """Work Order skip_transfer=1, use_multi_level_bom=0 (chặn explode BOM đa tầng)."""
    wo = frappe.get_doc(
        {
            "doctype": "Work Order",
            "company": company,
            "production_item": item_code,
            "qty": qty,
            "bom_no": bom_no,
            "skip_transfer": 1,
            "use_multi_level_bom": 0,
            "source_warehouse": source_wh,
            "fg_warehouse": fg_wh,
            "wip_warehouse": fg_wh,  # không dùng (skip_transfer) — chỉ thoả reqd
            "custom_ngay_sx": ngay_sx,
        }
    )
    if planned_date:
        wo.planned_start_date = str(planned_date)
    wo.flags.ignore_permissions = True
    wo.insert()
    wo.submit()
    return wo


def loai_phieu_kho(purpose="Manufacture"):
    """Tên Stock Entry Type ứng với `purpose` (D28).

    Core v16 (`StockEntry.set_stock_entry_type`) CHỈ tìm bản ghi
    `{purpose: X, is_standard: 1}`. Site nào lỡ bỏ tick "Is Standard", đổi tên hay
    xoá bản chuẩn thì SE sinh ra thiếu `stock_entry_type` -> chết ở validate với
    "Value missing for Stock Entry: Stock Entry Type" — không nói gì về nguyên nhân.
    Ở đây nới dần điều kiện rồi báo lỗi CHỈ ĐÚNG chỗ phải sửa.
    """
    ten = frappe.db.get_value(
        "Stock Entry Type", {"purpose": purpose, "is_standard": 1}, "name"
    )
    if not ten:  # có bản ghi đúng purpose nhưng không tick is_standard
        ten = frappe.db.get_value("Stock Entry Type", {"purpose": purpose}, "name")
    if not ten and frappe.db.exists("Stock Entry Type", purpose):
        ten = purpose  # bản ghi tên "Manufacture" nhưng purpose bị sửa
    if not ten:
        co = frappe.get_all("Stock Entry Type", pluck="name") or []
        frappe.throw(
            _("Site chưa có 'Stock Entry Type' nào cho mục đích {0}. Vào Desk → "
              "Stock Entry Type → New: Type = {0}, Purpose = {0}, tick 'Is Standard'. "
              "(Hiện có: {1})").format(purpose, ", ".join(co) or _("chưa có loại nào"))
        )
    return ten


def tao_se_manufacture(wo, qty, batch_fg, kho_nguon, ngay=None, ngay_sx=None):
    """SE Manufacture từ WO. kho_nguon(item_code)->warehouse cho từng RM (đổi kho
    nguồn per-item vì WO chỉ có 1 source_warehouse). RM pick batch FIFO; FG gắn batch."""
    from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

    se = frappe.get_doc(make_stock_entry(wo.name, "Manufacture", qty))
    if not se.stock_entry_type:
        se.stock_entry_type = loai_phieu_kho("Manufacture")
    se.custom_ngay_sx = ngay_sx
    if ngay:
        se.set_posting_time = 1
        se.posting_date = str(ngay)

    for row in se.items:
        if row.get("is_finished_item"):
            row.serial_and_batch_bundle = None
            row.use_serial_batch_fields = 1
            row.batch_no = batch_fg
        elif row.s_warehouse:
            row.s_warehouse = kho_nguon(row.item_code)

    _gan_batch_fifo(se)

    se.flags.ignore_permissions = True
    se.insert()
    se.submit()
    return se


def tao_se_repack(cong_ty, item_vao, kg_vao, kho_vao, item_ra, kg_ra, kho_ra,
                  batch_ra=None, batch_vao=None, ngay=None, ghi_chu=None,
                  lo_rang=None, cong_doan=None):
    """Stock Entry Repack: đổi item A -> item B mà KHÔNG cần BOM (D31).

    Dùng cho các công đoạn tầng 1 (luộc+rang / tách vỏ / nghiền): mỗi công đoạn là
    một lần chuyển hoá có hao hụt, số kg ra do QC cân thật — không có định mức cố
    định để dựng BOM. Repack là purpose chuẩn của ERPNext cho đúng việc này.

    batch_vao=None -> tự pick FIFO. batch_ra bắt buộc nếu item ra có batch.
    """
    se = frappe.new_doc("Stock Entry")
    se.purpose = "Repack"
    se.stock_entry_type = loai_phieu_kho("Repack")
    se.company = cong_ty
    se.custom_lo_rang = lo_rang
    se.custom_cong_doan = cong_doan
    if ngay:
        se.set_posting_time = 1
        se.posting_date = str(ngay)
    if ghi_chu:
        se.remarks = ghi_chu

    se.append("items", {
        "item_code": item_vao, "qty": flt(kg_vao),
        "s_warehouse": kho_vao,
        **({"use_serial_batch_fields": 1, "batch_no": batch_vao} if batch_vao else {}),
    })
    se.append("items", {
        "item_code": item_ra, "qty": flt(kg_ra),
        "t_warehouse": kho_ra, "is_finished_item": 1,
        **({"use_serial_batch_fields": 1, "batch_no": batch_ra} if batch_ra else {}),
    })
    if not batch_vao:
        _gan_batch_fifo(se)

    se.flags.ignore_permissions = True
    se.insert()
    se.submit()
    return se


def tao_se_chuyen_kho(cong_ty, item, kg, kho_di, kho_den, ngay=None, ghi_chu=None,
                      lo_rang=None, cong_doan=None):
    """Stock Entry Material Transfer — xuất kho nguyên liệu ra xưởng (D31). FIFO lô."""
    se = frappe.new_doc("Stock Entry")
    se.purpose = "Material Transfer"
    se.stock_entry_type = loai_phieu_kho("Material Transfer")
    se.company = cong_ty
    se.custom_lo_rang = lo_rang
    se.custom_cong_doan = cong_doan
    if ngay:
        se.set_posting_time = 1
        se.posting_date = str(ngay)
    if ghi_chu:
        se.remarks = ghi_chu
    se.append("items", {
        "item_code": item, "qty": flt(kg),
        "s_warehouse": kho_di, "t_warehouse": kho_den,
    })
    _gan_batch_fifo(se)
    se.flags.ignore_permissions = True
    se.insert()
    se.submit()
    return se


def _gan_batch_fifo(se):
    """Gán batch FIFO cho dòng RM có has_batch_no; 1 dòng tách nhiều batch nếu cần.

    get_batch_qty trả batch theo chiến lược pick Stock Settings (mặc định FIFO) ->
    lô cũ nhất dùng trước (D5). Không đủ tồn theo lô -> throw rõ ràng.
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
            from sx.utils import cho_phep_ton_am

            if not cho_phep_ton_am():
                frappe.throw(
                    _("Không đủ tồn theo lô cho {0} tại {1} (thiếu {2}).").format(
                        row.item_code, row.s_warehouse, flt(con_lai, 3)
                    )
                )
            # Cho tồn âm: item có batch VẪN bắt buộc khai lô, nên dồn phần thiếu vào
            # lô mới nhất (không có lô nào thì phải tạo/nhập lô trước — không đoán được).
            lo_am = phan[-1][0] if phan else frappe.db.get_value(
                "Batch", {"item": row.item_code}, "name", order_by="creation desc"
            )
            if not lo_am:
                frappe.throw(
                    _("{0} chưa có lô nào trong hệ thống nên không ghi âm được. "
                      "Nhập một phiếu nhập kho (hoặc Stock Reconciliation) có lô cho "
                      "item này trước.").format(row.item_code)
                )
            if phan and phan[-1][0] == lo_am:
                phan[-1] = (lo_am, phan[-1][1] + con_lai)
            else:
                phan.append((lo_am, con_lai))
            con_lai = 0
        if not phan:
            continue
        row.serial_and_batch_bundle = None
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


def cancel_doc(doctype, name, log=None):
    """Huỷ 1 chứng từ submitted (ignore_permissions sau guard nghiệp vụ)."""
    if not name or not frappe.db.exists(doctype, name):
        return
    d = frappe.get_doc(doctype, name)
    if d.docstatus == 1:
        d.flags.ignore_permissions = True
        d.cancel()
        if log is not None:
            log.append(f"Huỷ {doctype} {name}")
