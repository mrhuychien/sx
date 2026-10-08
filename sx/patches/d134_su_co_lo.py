"""D134 (W11): ô "Lô thành phẩm" (lo_tp, một lô — D133) thành bảng Lô liên quan.

Site đã chạy D133 thì cột lo_tp còn nằm trong bảng (Frappe không xoá cột khi bỏ field):
chép mỗi giá trị thành một dòng của bảng ds_lo, lô đã có trong bảng thì bỏ qua. Site
chưa chạy D133 thì không có cột — không làm gì. Chạy lại vô hại.
"""

import frappe


def execute():
    if not frappe.db.table_exists("SX Su Co Lo") or not frappe.db.has_column("SX Su Co", "lo_tp"):
        return
    for r in frappe.db.sql("""SELECT name, lo_tp FROM `tabSX Su Co`
                              WHERE IFNULL(lo_tp, '') != ''""", as_dict=True):
        if not frappe.db.exists("Batch", r.lo_tp):
            continue
        if frappe.db.exists("SX Su Co Lo", {"parenttype": "SX Su Co", "parent": r.name,
                                            "batch": r.lo_tp}):
            continue
        b = frappe.db.get_value("Batch", r.lo_tp, ["item", "item_name", "expiry_date"], as_dict=True)
        idx = (frappe.db.count("SX Su Co Lo", {"parenttype": "SX Su Co", "parent": r.name}) or 0) + 1
        frappe.get_doc({
            "doctype": "SX Su Co Lo", "parent": r.name, "parenttype": "SX Su Co",
            "parentfield": "ds_lo", "idx": idx, "batch": r.lo_tp, "item": b.item,
            "ten": b.item_name or b.item, "hsd": b.expiry_date,
        }).db_insert()
