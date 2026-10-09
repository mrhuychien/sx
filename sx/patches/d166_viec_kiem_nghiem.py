"""D166 (W35): việc kiểm nghiệm KH.KN.01 (lần BH 01, 21/9/2026) ngoài thành phẩm — tạo nếu chưa có (so theo tên,
không phân biệt hoa thường / khoảng trắng; việc đã có thì giữ nguyên chỗ người ta đã sửa). Chạy lại vô hại.

Theo KH.KN.01 (khác danh sách giao việc): nước sản xuất theo QCVN 01-1:2024/BYT; đỗ xanh nhập khẩu đủ chỉ tiêu
của KH.KN.01 (không chỉ độ ẩm, aflatoxin); lạc nhân và dầu thực vật là HAI dòng riêng (chỉ tiêu khác nhau).
Hạn lần đầu: KH.KN.01 "lần gửi mẫu đầu tiên theo kế hoạch này: trước 31/10/2026" — lấy hạn đầu kiểm nghiệm
của SX QC Setting (như sản phẩm); thôi nhiễm bao bì ("khi đổi NCC hoặc 2 năm/lần") chưa biết lần gần nhất → để
trống, app hiện "Chưa đặt hạn". Thẩm tra vải ủ (HD.08.02 mục 9): 3 việc "Một lần" hạn cuối tháng 10, 11, 12/2026.
"""

import frappe

from sx.qc import kiem_nghiem as KN
from sx.qc import viec_dinh_ky as VD

HAN_DAU = "han_dau"            # = KN.han_dau() lúc chạy
TAM_TRA = ("Tổng số nấm men, nấm mốc — 1 mẫu bột đậu xanh sau nghiền làm từ đỗ ủ bằng vải ngày cuối chu kỳ "
           "(ngày trước ngày giặt); đạt khi không vượt giới hạn nấm men, nấm mốc của thành phẩm theo TCCS. Không "
           "đạt: chuyển sang giặt, đun sôi sau mỗi lần dùng; Trưởng Ban ISO đánh giá lại.")
# (tên, chu kỳ, hạn, mẫu của, chỉ tiêu (Làm gì), căn cứ)
DS = (
    ("Kiểm nghiệm nước sản xuất — mẫu nước tại vòi", "Năm", HAN_DAU, "Nước",
     "Theo QCVN 01-1:2024/BYT nhóm A (và chỉ tiêu nhóm B theo yêu cầu)", "KH.KN.01 · PRP SSOP 1"),
    ("Kiểm nghiệm đỗ xanh nhập khẩu — mẫu gộp ≥ 10 bao (năm / khi đổi nguồn)", "Năm", HAN_DAU, "Nguyên liệu",
     "Aflatoxin B1, tổng; độ ẩm; Pb, Cd, As, Hg; đa dư lượng thuốc BVTV; phosphine; ochratoxin A",
     "KH.KN.01 · KH.HACCP.01 mục 5.2, 5.12 · HD.07.01"),
    ("Kiểm nghiệm lạc nhân — aflatoxin (năm / khi đổi NCC)", "Năm", HAN_DAU, "Nguyên liệu",
     "Aflatoxin B1, tổng (thay kết quả từng lô)", "KH.KN.01 · KH.HACCP.02 oPRP-6"),
    ("Kiểm nghiệm dầu thực vật — peroxide, acid (năm / khi đổi NCC)", "Năm", HAN_DAU, "Nguyên liệu",
     "Chỉ số peroxide (lô nhập ≤ 2,0 meq O2/kg, TCCS 03), chỉ số acid", "KH.KN.01 · QT.14 Phụ lục A · TCCS 03 mục 3.1"),
    ("Kiểm nghiệm thôi nhiễm bao bì tiếp xúc thực phẩm (2 năm / khi đổi NCC)", "2 năm", None, "Khác",
     "Thôi nhiễm theo QCVN 12-1/12-3", "KH.KN.01 · QT.14 Phụ lục A"),
    ("Thẩm tra vải ủ — nấm men, nấm mốc bột sau nghiền tháng 10/2026", "Một lần", "2026-10-31", "Khác", TAM_TRA,
     "HD.08.02 mục 9 · BM.08.05"),
    ("Thẩm tra vải ủ — nấm men, nấm mốc bột sau nghiền tháng 11/2026", "Một lần", "2026-11-30", "Khác", TAM_TRA,
     "HD.08.02 mục 9 · BM.08.05"),
    ("Thẩm tra vải ủ — nấm men, nấm mốc bột sau nghiền tháng 12/2026", "Một lần", "2026-12-31", "Khác", TAM_TRA,
     "HD.08.02 mục 9 · BM.08.05"),
)


def chuan(ten):
    return " ".join(str(ten or "").split()).casefold()


def execute():
    if not frappe.db.table_exists(VD.PT):
        return
    co = {chuan(x) for x in frappe.get_all(VD.PT, pluck="ten")}
    for ten, chu_ky, han, mau, chi_tieu, can_cu in DS:
        if chuan(ten) in co:
            continue
        frappe.get_doc({"doctype": VD.PT, "ten": ten, "chu_ky": chu_ky,
                        "han": str(KN.han_dau()) if han == HAN_DAU else han, "bao_truoc": 30,
                        "doi_tuong_kn": mau, "mo_ta": chi_tieu, "ho_so": can_cu}).insert(ignore_permissions=True)
