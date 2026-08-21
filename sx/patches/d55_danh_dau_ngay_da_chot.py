"""D55: ngày đã chốt TRƯỚC khi tách hai nửa phải được đánh dấu là chốt CẢ HAI.

Không chạy patch này thì mọi ngày cũ hiện lên như "chưa chốt Ghi sổ / Vào hộp",
portal sẽ mời chốt lại một ngày đã có đủ chứng từ kho — và nếu ai bấm thì sinh
trùng toàn bộ WO/SE. Đây là loại lỗi im lặng, phải vá bằng patch chứ không phải
bằng ghi chú.
"""

import frappe


def execute():
    if not frappe.db.has_column("SX Ngay San Xuat", "chot_ghiso"):
        return
    frappe.db.sql("""
        UPDATE `tabSX Ngay San Xuat`
        SET chot_ghiso = 1, chot_vaohop = 1
        WHERE docstatus = 1 AND (chot_ghiso = 0 OR chot_vaohop = 0)
    """)
    frappe.db.commit()
