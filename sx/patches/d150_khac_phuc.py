"""D150 (W24): thêm phiếu hành động khắc phục BM.01.07 vào danh mục hồ sơ cho đoàn đánh giá (W27).
Đã có mã BM.01.07 (so không phân biệt khoảng trắng / hoa thường) thì bỏ qua. Chạy lại vô hại.
"""

import frappe

from sx.qc import ho_so as HS


def execute():
    if not frappe.db.table_exists(HS.PT):
        return
    if HS.chuan_ma("BM.01.07") in {HS.chuan_ma(x) for x in frappe.get_all(HS.PT, pluck="ma")}:
        return
    frappe.get_doc({"doctype": HS.PT, "ma": "BM.01.07", "ten": "Phiếu hành động khắc phục",
                    "nhom": "Truy xuất, sự cố, khiếu nại", "nguon": HS.APP, "bieu_mau": "BM.01.07",
                    "thu_tu": 15, "bat_buoc": 1}).insert(ignore_permissions=True)
