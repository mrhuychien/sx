"""D136 (W26): tạo "Kho hàng trả về" và "Kho cách ly" nếu SX Settings chưa khai.

Tạo cạnh kho thành phẩm (cùng công ty, cùng kho cha). Công ty đã có kho cùng tên
(do người dùng tự tạo) thì dùng lại kho đó, không tạo trùng. Ô nào đã khai thì để
nguyên. Chưa khai công ty / kho thành phẩm thì không làm gì — khai tay trong SX
Settings. Chạy lại vô hại.
"""

import frappe

KHO = (("kho_hang_tra_ve", "Kho hàng trả về"), ("kho_cach_ly", "Kho cách ly"))


def execute():
    if not frappe.db.table_exists("Warehouse"):
        return
    s = frappe.get_single("SX Settings")
    cong_ty = s.get("cong_ty")
    if not cong_ty or not s.get("kho_tp"):
        return
    cha = frappe.db.get_value("Warehouse", s.kho_tp, "parent_warehouse")
    doi = False
    for truong, ten in KHO:
        if s.get(truong):
            continue
        co = frappe.db.get_value("Warehouse", {"warehouse_name": ten, "company": cong_ty}, "name")
        if not co:
            w = frappe.get_doc({"doctype": "Warehouse", "warehouse_name": ten, "company": cong_ty,
                                "parent_warehouse": cha, "is_group": 0})
            w.insert(ignore_permissions=True)
            co = w.name
        s.set(truong, co)
        doi = True
    if doi:
        s.flags.ignore_mandatory = True
        s.save(ignore_permissions=True)
