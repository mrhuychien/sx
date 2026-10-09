"""D152: W17 (f) — chốt ngày 09/10/2026: người kiểm đồng hồ nhiệt theo "Đào tạo nội bộ" (app chỉ lưu biên bản
đào tạo, không chặn ghi). Đặt vào SX QC Setting nếu còn trống; đã chọn rồi (kể cả "Giữ chứng chỉ") thì để
nguyên. Chạy lại vô hại.
"""

import frappe

GIA_TRI = "Đào tạo nội bộ"


def execute():
    if not frappe.db.exists("DocType", "SX QC Setting"):
        return
    if not frappe.db.get_single_value("SX QC Setting", "chung_chi_dong_ho"):
        frappe.db.set_single_value("SX QC Setting", "chung_chi_dong_ho", GIA_TRI)
