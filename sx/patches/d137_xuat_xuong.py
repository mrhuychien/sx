"""D137 (W08): đặt "Áp dụng BM.08.04 từ ngày" = ngày cập nhật, nếu chưa khai.

Không có ngày này thì mọi lô thành phẩm đang tồn (nhập trước khi có phiếu kiểm tra xuất
xưởng) bị chặn bán ngay sau khi cập nhật. Đã khai thì để nguyên. Chạy lại vô hại.
"""

import frappe
from frappe.utils import nowdate


def execute():
    # SX Settings là doctype Single: không có bảng "tabSX Settings" → table_exists luôn sai. Bản đầu dùng
    # table_exists nên patch không làm gì (D152 chạy bù).
    if not frappe.db.exists("DocType", "SX Settings"):
        return
    s = frappe.get_single("SX Settings")
    if s.get("xuat_xuong_tu_ngay"):
        return
    frappe.db.set_single_value("SX Settings", "xuat_xuong_tu_ngay", nowdate())
