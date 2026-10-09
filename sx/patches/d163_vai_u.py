"""D163 (W29): thêm sổ giặt vải ủ BM.08.05 vào danh mục hồ sơ cho đoàn đánh giá (W27).
Đã có mã BM.08.05 (so không phân biệt khoảng trắng / hoa thường — vd dòng "Bản giấy" Ban ISO tự thêm) thì bỏ
qua, giữ chỗ người ta đã sửa. Không khai sẵn vải ủ (C31: số thùng, số vải HD.08.02 còn để trống — QLSX khai
trên app). Chạy lại vô hại.
"""

import frappe

from sx.qc import ho_so as HS


def execute():
    if not frappe.db.table_exists(HS.PT):
        return
    if HS.chuan_ma("BM.08.05") in {HS.chuan_ma(x) for x in frappe.get_all(HS.PT, pluck="ma")}:
        return
    frappe.get_doc({"doctype": HS.PT, "ma": "BM.08.05", "ten": "Sổ giặt vải ủ", "nhom": "Kiểm soát sản xuất",
                    "nguon": HS.APP, "bieu_mau": "BM.08.05", "thu_tu": 25, "bat_buoc": 1,
                    "can_cu": "HD.08.02 lần BH 01: giặt, đun sôi ≥ 10 phút 1 lần/tuần; lưu 2 năm tại xưởng."}).insert(
        ignore_permissions=True)
