"""D149 (W27): tạo sẵn danh mục hồ sơ cho đoàn đánh giá.

Chỉ ghi những gì chắc: nguồn pháp lý đổi ngày 08/10/2026 (CV 21/CV-HGC thay CV 10; TCCS 01 theo QĐ 11;
TCCS 03 theo QĐ 12), bản tự công bố 16 sản phẩm (W28) và các biểu mẫu app đang lập. Văn bản pháp lý khác
(giấy chứng nhận, giấy phép…) Ban ISO thêm trên màn Hồ sơ đánh giá — không đoán.
Mã đã có (so không phân biệt khoảng trắng / hoa thường) thì bỏ qua — giữ chỗ người ta đã sửa. Chạy lại vô hại.
"""

import frappe

from sx.qc import ho_so as HS

PL, SP, KS, TX, TB, NCC, PRP = ("Pháp lý", "Sản phẩm", "Kiểm soát sản xuất", "Truy xuất, sự cố, khiếu nại",
                                "Thiết bị đo", "Nhà cung cấp, nguyên liệu", "Điều kiện nhà xưởng (PRP)")

# (mã, tên, nhóm, nằm ở đâu, biểu mẫu app, căn cứ, thay thế, thứ tự)
DS = (
    ("CV 21/CV-HGC", "Công văn 21/CV-HGC", PL, HS.TEP, None, "Nguồn pháp lý từ 08/10/2026, thay CV 10.", "CV 10", 10),
    ("Tự công bố SP", "Bản tự công bố sản phẩm (16 sản phẩm)", SP, HS.APP, "TU_CONG_BO",
     "Danh mục sản phẩm tự công bố trên app (W28): số bản, TCCS áp dụng.", None, 10),
    ("TCCS 01", "Tiêu chuẩn cơ sở TCCS 01", SP, HS.TEP, None, "Ban hành theo QĐ 11.", None, 20),
    ("TCCS 03", "Tiêu chuẩn cơ sở TCCS 03", SP, HS.TEP, None, "Ban hành theo QĐ 12.", None, 30),
    ("KH.KN.01", "Kế hoạch kiểm nghiệm sản phẩm", SP, HS.APP, "KH.KN.01", None, None, 40),
    ("BM.08.01", "Vòng kiểm hằng ngày", KS, HS.APP, "BM.08.01", None, None, 10),
    ("BM.08.03", "Nhật ký cát rang", KS, HS.APP, "BM.08.03", None, None, 20),
    ("BM.08.04", "Kiểm tra xuất xưởng theo lô", KS, HS.APP, "BM.08.04", None, None, 30),
    ("BM.15.01", "Phiếu rework", KS, HS.APP, "BM.15.01", None, None, 40),
    ("BM.08.02", "Sổ phiếu sự cố", TX, HS.APP, "BM.08.02", None, None, 10),
    ("BM.11.01", "Sổ khiếu nại khách hàng", TX, HS.APP, "BM.11.01", None, None, 20),
    ("BM.02.04", "Diễn tập truy xuất (phụ lục BM.02.04)", TX, HS.APP, "BM.02.04", None, None, 30),
    ("Huỷ mẫu lưu", "Biên bản huỷ mẫu lưu", TX, HS.APP, "HUY_MAU", None, None, 40),
    ("BM.06.01", "Danh mục thiết bị đo", TB, HS.APP, "BM.06.01", None, None, 10),
    ("BM.06.02", "Kiểm tra đồng hồ nhiệt", TB, HS.APP, "BM.06.02", None, None, 20),
    ("BM.06.03", "Kiểm tra nam châm", TB, HS.APP, "BM.06.03", None, None, 30),
    ("BM.06.04", "Kiểm tra lưới sàng, rây", TB, HS.APP, "BM.06.04", None, None, 40),
    ("BM.07.02", "Danh sách nhà cung cấp được duyệt", NCC, HS.APP, "BM.07.02", None, None, 10),
    ("BM.09.01", "Kiểm tra xe (giao hàng, nhận nguyên liệu)", NCC, HS.APP, "BM.09.01", None, None, 20),
    ("BM.PRP.03", "Theo dõi động vật gây hại — tuần", PRP, HS.APP, "BM.PRP.03", None, None, 10),
    ("BM.PRP.01", "Tổng hợp động vật gây hại — tháng", PRP, HS.APP, "BM.PRP.01", None, None, 20),
)


def execute():
    if not frappe.db.table_exists(HS.PT):
        return
    co = {HS.chuan_ma(x) for x in frappe.get_all(HS.PT, pluck="ma")}
    for ma, ten, nhom, nguon, bm, can_cu, thay, thu_tu in DS:
        if HS.chuan_ma(ma) in co:
            continue
        frappe.get_doc({"doctype": HS.PT, "ma": ma, "ten": ten, "nhom": nhom, "nguon": nguon, "bieu_mau": bm,
                        "can_cu": can_cu, "thay_the": thay, "thu_tu": thu_tu, "bat_buoc": 1}).insert(
            ignore_permissions=True)
