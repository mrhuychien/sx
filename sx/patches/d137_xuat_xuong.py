"""D137 (W08): đặt "Áp dụng BM.08.04 từ ngày" = ngày cập nhật, nếu chưa khai.

Không có ngày này thì mọi lô thành phẩm đang tồn (nhập trước khi có phiếu kiểm tra xuất
xưởng) bị chặn bán ngay sau khi cập nhật. Đã khai thì để nguyên. Chạy lại vô hại.
"""

import frappe
from frappe.utils import nowdate


def execute():
    if not frappe.db.table_exists("SX Settings"):
        return
    s = frappe.get_single("SX Settings")
    if s.get("xuat_xuong_tu_ngay"):
        return
    frappe.db.set_single_value("SX Settings", "xuat_xuong_tu_ngay", nowdate())
