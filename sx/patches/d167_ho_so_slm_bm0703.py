"""D167 (W36): thêm Sổ lưu mẫu SLM và sổ tiếp nhận BM.07.03 (app in theo tháng) vào danh mục hồ sơ cho đoàn
đánh giá (W27) — gói zip có bản in từng tháng của kỳ. Mã đã có (so không phân biệt khoảng trắng / hoa thường — vd
dòng "Bản giấy" Ban ISO tự thêm) thì bỏ qua, giữ chỗ người ta đã sửa. Chạy lại vô hại.
"""

import frappe

from sx.qc import ho_so as HS

# (mã, tên, nhóm, căn cứ, thứ tự)
DS = (
    ("SLM", "Sổ lưu mẫu sản phẩm", "Truy xuất, sự cố, khiếu nại",
     "QĐ.01 lần BH 02 — SLM lần BH 02 (21/9/2026): mỗi lô một mẫu, lưu 1 năm từ NSX; sổ lưu 2 năm.", 35),
    ("BM.07.03", "Sổ kiểm tra chất lượng vật tư / nguyên liệu nhập vào", "Nhà cung cấp, nguyên liệu",
     "QT.07, HD.07.01 — một dòng mỗi lô nhận; lưu 2 năm kèm COA, phiếu kiểm nghiệm.", 15),
)


def execute():
    if not frappe.db.table_exists(HS.PT):
        return
    co = {HS.chuan_ma(x) for x in frappe.get_all(HS.PT, pluck="ma")}
    for ma, ten, nhom, can_cu, thu_tu in DS:
        if HS.chuan_ma(ma) in co:
            continue
        frappe.get_doc({"doctype": HS.PT, "ma": ma, "ten": ten, "nhom": nhom, "nguon": HS.APP, "bieu_mau": ma,
                        "thu_tu": thu_tu, "bat_buoc": 1, "can_cu": can_cu}).insert(ignore_permissions=True)
