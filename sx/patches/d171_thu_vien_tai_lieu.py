"""D171 (W42): thư viện tài liệu — thêm BM.01.02 (danh mục tài liệu nội bộ), BM.01.03 (danh mục tài liệu bên
ngoài), BM.01.13 (biên bản phổ biến, danh sách phân phối theo đợt) vào danh mục hồ sơ cho đoàn đánh giá (W27):
app tự lập, gói zip có bản in. Mã đã có (so không phân biệt khoảng trắng / hoa thường) thì bỏ qua, giữ chỗ người
ta đã sửa. Chạy lại vô hại.

Nạp bộ tài liệu 21/9/2026 KHÔNG ở patch: Ban ISO chọn tệp seed + PDF trên màn Tài liệu → Nạp bộ (cần tệp PDF,
và role mới SX Co Dien / SX Hanh Chinh do after_migrate tạo — chạy sau patch).
"""

import frappe

from sx.qc import ho_so as HS

CAN_CU = "QT.01 phần kiểm soát tài liệu; QĐ ban hành, sửa đổi tài liệu 21/9/2026."
# (mã, tên, thứ tự)
DS = (
    ("BM.01.02", "Danh mục tài liệu nội bộ", 3),
    ("BM.01.03", "Danh mục tài liệu bên ngoài", 4),
    ("BM.01.13", "Biên bản phổ biến, đào tạo tài liệu và danh sách phân phối", 5),
)


def execute():
    if not frappe.db.table_exists(HS.PT):
        return
    co = {HS.chuan_ma(x) for x in frappe.get_all(HS.PT, pluck="ma")}
    for ma, ten, thu_tu in DS:
        if HS.chuan_ma(ma) in co:
            continue
        frappe.get_doc({"doctype": HS.PT, "ma": ma, "ten": ten, "nhom": "Hệ thống quản lý", "nguon": HS.APP,
                        "bieu_mau": ma, "thu_tu": thu_tu, "bat_buoc": 1, "can_cu": CAN_CU}).insert(
            ignore_permissions=True)
