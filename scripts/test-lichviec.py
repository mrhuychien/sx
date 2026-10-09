"""D146 (W21) — lịch việc định kỳ cho hồ sơ giấy (việc năm / quý lên hộp nhắc).

Vì sao phải có bài này:
  · Việc làm muộn mà hạn kỳ sau tính từ ngày làm → lịch trôi dần (tháng 11 thành tháng 12…).
  · Việc "một lần" làm xong vẫn nhắc mãi → người ta học cách bỏ qua hộp nhắc.
  · Hai việc tài liệu nêu (thử khôi phục dữ liệu T11/2026, thay bóng đèn bẫy T3/2027) phải có sẵn.

Nạp sx/qc/viec_dinh_ky.py, controller, sx/api/qc_lichviec.py, patch THẬT; frappe giả.
Chạy: python3 scripts/test-lichviec.py   (verify.sh gọi sẵn)
"""

import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

F.cai()
Q = F.nap_qc()
NH = sys.modules["sx.qc.nhac"]
VD = sys.modules["sx.qc.viec_dinh_ky"]
A = F.nap("sx.api.qc_lichviec", "sx/api/qc_lichviec.py")
VDC = F.nap("vd_ctl", "sx/qc/doctype/sx_viec_dinh_ky/sx_viec_dinh_ky.py")
F.dang_ky(VD.PT, VDC.SXViecDinhKy)
P = F.nap("sx.patches.d146_viec_dinh_ky", "sx/patches/d146_viec_dinh_ky.py")
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")


def lan_cua(ten):
    return [r for r in (F.bang(VD.PT)[ten].get("ds_lan") or [])]


# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- kỳ sau, trạng thái (hàm thuần) --")
kiem("kỳ sau tính từ hạn cũ: năm +12, quý +3, tháng +1; một lần → hết",
     VD.ke_tiep("2026-11-30", "Năm") == date(2027, 11, 30) and VD.ke_tiep("2026-11-30", "Quý") == date(2027, 2, 28)
     and VD.ke_tiep("2026-01-31", "Tháng") == date(2026, 2, 28) and VD.ke_tiep("2026-11-30", "Một lần") is None)
tt = VD.trang_thai
kiem("trạng thái: quá hạn / sắp đến (trong số ngày nhắc trước) / còn hạn / ngừng",
     tt({"han": "2026-10-08"}, "2026-10-09")[0] == VD.QUA_HAN
     and tt({"han": "2026-10-20", "bao_truoc": 14}, "2026-10-09") == (VD.SAP_DEN, 11)
     and tt({"han": "2026-11-30", "bao_truoc": 30}, "2026-10-09")[0] == VD.CON_HAN
     and tt({"han": "2026-10-01", "ngung": 1}, "2026-10-09")[0] == VD.NGUNG)
kiem("nhắc trước trống / 0 → 14 ngày", tt({"han": "2026-10-23", "bao_truoc": 0}, "2026-10-09")[0] == VD.SAP_DEN
     and tt({"han": "2026-10-24"}, "2026-10-09")[0] == VD.CON_HAN)

# ═══ 2. Patch, ghi đã làm ══════════════════════════════════════════════════
print("\n-- hai việc tài liệu nêu, ghi đã làm --")
P.execute()
ten = {x["ten"]: n for n, x in F.bang(VD.PT).items()}
kp = ten["Thử khôi phục dữ liệu app từ bản sao lưu"]
den = ten["Thay bóng đèn bẫy côn trùng"]
kiem("patch: thử khôi phục dữ liệu hạn 30/11/2026, thay bóng đèn bẫy 31/03/2027, nhắc trước 30 ngày, hằng năm",
     (str(F.bang(VD.PT)[kp]["han"]), str(F.bang(VD.PT)[den]["han"]), F.bang(VD.PT)[kp]["bao_truoc"],
      F.bang(VD.PT)[kp]["chu_ky"]) == ("2026-11-30", "2027-03-31", 30, "Năm"))
F.bang(VD.PT)[kp]["han"] = "2026-11-20"
P.execute()
kiem("chạy lại patch: không nhân đôi, giữ hạn người ta đã sửa", len(F.bang(VD.PT)) == 2
     and F.bang(VD.PT)[kp]["han"] == "2026-11-20")
F.bang(VD.PT)[kp]["han"] = "2026-11-30"
q = {x["name"]: x for x in A.tong_quan()["ds"]}
kiem("09/10: thử khôi phục còn 52 ngày → Còn hạn", q[kp]["trang_thai"] == VD.CON_HAN and q[kp]["con"] == 52)
F.dat_ngay("2026-11-05")
kiem("05/11: vào cửa sổ nhắc 30 ngày → Sắp đến hạn", {x["name"]: x for x in A.tong_quan()["ds"]}[kp]["trang_thai"]
     == VD.SAP_DEN)
F.dat_ngay("2026-12-05")
kiem("ghi đã làm ngày sau hôm nay → chặn", "sau hôm nay" in (thu(lambda: A.da_lam(kp, json.dumps(
    {"ngay": "2026-12-06"}))) or ""))
r = A.da_lam(kp, json.dumps({"ngay": "2026-12-05", "ghi_chu": "BB-KP-01"}))
l = lan_cua(kp)
kiem("làm MUỘN 05/12 → hạn kỳ sau vẫn 30/11/2027 (tính từ hạn cũ), ghi lần làm + kỳ hạn + người",
     r["han"] == "2027-11-30" and len(l) == 1 and str(l[0]["han_ky"]) == "2026-11-30" and l[0]["nguoi"] == "qc@x"
     and l[0]["ghi_chu"] == "BB-KP-01" and str(F.bang(VD.PT)[kp]["lan_cuoi"]) == "2026-12-05", (r, l))
A.luu(json.dumps({"ten": "Đánh giá nội bộ lần đầu", "chu_ky": "Một lần", "han": "2026-12-20"}))
mot = next(n for n, x in F.bang(VD.PT).items() if x["ten"] == "Đánh giá nội bộ lần đầu")
r = A.da_lam(mot)
kiem("việc một lần làm xong → ngừng, không nhắc nữa", r["ngung"] == 1
     and mot not in json.dumps(VD.nhac("2027-06-01")))
kiem("ghi đã làm việc đã ngừng → chặn", "đã ngừng" in (thu(lambda: A.da_lam(mot)) or ""))
kiem("thêm việc thiếu hạn → chặn", "hạn" in (thu(lambda: A.luu(json.dumps({"ten": "x", "chu_ky": "Quý"}))) or ""))
kiem("chu kỳ lạ → chặn (controller)", "Chu kỳ" in (thu(lambda: A.luu(json.dumps({"ten": "x", "chu_ky": "Tuần",
                                                                                "han": "2027-01-01"}))) or ""))

# ═══ 3. Nhắc, quyền ═══════════════════════════════════════════════════════
print("\n-- hộp nhắc, quyền --")
F.dat_ngay("2027-04-02")
n = VD.nhac(F.hom_nay())
m = [x for x in NH.tinh(F.hom_nay(), [], [], {}, viec_dinh_ky=n) if x["route"] == "#/qc/lichviec"]
kiem("thay bóng đèn bẫy quá hạn 31/03 → nhắc mức CAO, tên việc ngay trên tiêu đề",
     any(x["muc_do"] == "cao" and "Thay bóng đèn bẫy" in x["tieu_de"] for x in m), m)
F.dat_ngay("2027-11-05")
n = VD.nhac(F.hom_nay())
m = [x for x in NH.tinh(F.hom_nay(), [], [], {}, viec_dinh_ky=n) if x["route"] == "#/qc/lichviec"]
kiem("kỳ sau của thử khôi phục (30/11/2027) vào cửa sổ → nhắc mức thường",
     any(x["muc_do"] == "thuong" and "khôi phục" in x["tieu_de"] for x in m), m)
F.dat_ngay("2026-10-09")
kiem("sx.api.qc.nhac truyền việc định kỳ vào hộp nhắc", "_viec_dinh_ky.nhac(d)" in open(
    "sx/api/qc.py", encoding="utf-8").read())
F.vai("Stock User")
kiem("người ngoài không xem được", thu(A.tong_quan) is not None)
F.vai("SX Quan Ly")
kiem("quản trị xem được", thu(A.tong_quan) is None)
F.vai("ISO Manager")
kiem("Ban ISO ghi được", thu(lambda: A.luu(json.dumps({"ten": "Xem xét lãnh đạo", "chu_ky": "Năm",
                                                        "han": "2026-12-15"}))) is None)
F.vai("SX QC")

# ═══ 4. Màn hình ══════════════════════════════════════════════════════════
print("\n-- màn hình --")
kiem("patch có trong patches.txt", "sx.patches.d146_viec_dinh_ky" in open("sx/patches.txt", encoding="utf-8").read())
kiem("route #/qc/lichviec + nút ở Hôm nay", "lichviec: '/assets/sx/sx/views/qc_lichviec.js'" in open(
    "sx/public/sx/views/qc.js", encoding="utf-8").read() and "#/qc/lichviec" in open(
    "sx/public/sx/views/qc_home.js", encoding="utf-8").read())
js = open("sx/public/sx/views/qc_lichviec.js", encoding="utf-8").read()
kiem("màn việc định kỳ: đã làm, thêm / sửa", "sx.api.qc_lichviec.da_lam" in js and "sx.api.qc_lichviec.luu" in js)

F.ket_thuc("LICHVIEC")
