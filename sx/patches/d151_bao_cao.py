"""D151 (W25): thêm báo cáo ATTP tháng (chỉ tiêu ATTP, đầu vào họp xem xét của lãnh đạo) vào danh mục hồ sơ
cho đoàn đánh giá (W27). Đã có mã thì bỏ qua. Chạy lại vô hại.
"""

import frappe

from sx.qc import ho_so as HS

MA = "BC ATTP tháng"


def execute():
    if not frappe.db.table_exists(HS.PT):
        return
    if HS.chuan_ma(MA) in {HS.chuan_ma(x) for x in frappe.get_all(HS.PT, pluck="ma")}:
        return
    frappe.get_doc({"doctype": HS.PT, "ma": MA, "ten": "Báo cáo ATTP tháng, chỉ tiêu ATTP", "nhom": "Hệ thống quản lý",
                    "nguon": HS.APP, "bieu_mau": "BC.THANG", "thu_tu": 10, "bat_buoc": 1,
                    "can_cu": "Đầu vào họp xem xét của lãnh đạo; mục tiêu ATTP năm."}).insert(ignore_permissions=True)
