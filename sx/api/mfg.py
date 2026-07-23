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


def tao_se_manufacture(wo, qty, batch_fg, kho_nguon, ngay=None, ngay_sx=None):
    """SE Manufacture từ WO. kho_nguon(item_code)->warehouse cho từng RM (đổi kho
    nguồn per-item vì WO chỉ có 1 source_warehouse). RM pick batch FIFO; FG gắn batch."""
    from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

    se = frappe.get_doc(make_stock_entry(wo.name, "Manufacture", qty))
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
            frappe.throw(
                _("Không đủ tồn theo lô cho {0} tại {1} (thiếu {2}).").format(
                    row.item_code, row.s_warehouse, flt(con_lai, 3)
                )
            )
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
