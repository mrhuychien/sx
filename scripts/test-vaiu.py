"""D163 (W29) — sổ giặt vải ủ BM.08.05 + danh mục vải ủ.

Vì sao phải có bài này:
  · Đun sôi chưa đủ 10 phút mà QC vẫn ký được thì tờ sổ nói dối đúng chỗ đoàn đánh giá hỏi (HD.08.02 mục 6:
    tính từ lúc nước SÔI LẠI). Vớt qua nửa đêm mà tính ra số âm là chặn oan.
  · Nhập / loại vải phải đi qua sổ: loại tay ở danh mục là mất dòng BM.08.05; xoá dòng loại mà vải vẫn
    Đã loại là danh mục sai; vải thay mới khâu lại ĐÚNG MÃ của thùng (mục 8) — mã phải dùng lại được.
  · Nhắc giặt khi chưa khai vải là nhắc hão (C31: số thùng, số vải còn để trống) — chưa khai thì im.
  · Dòng đã QC ký / Trưởng Ban ISO đã xem thì khoá; người ghi xoá nhầm trong ngày được, người khác thì không.
  · BM.08.05 phải vào danh mục hồ sơ, gói zip, Tổng quan ATTP (W46 bắt options khớp BIEU_MAU).

Nạp sx/qc/vai_u.py, nhac.py, attp.py, controller SX Giat Vai / SX Vai U, sx/api/qc_vaiu.py, qc_hoso.py,
patch d163 THẬT trên frappe giả.
Chạy: python3 scripts/test-vaiu.py   (verify.sh gọi sẵn)
"""

import json
import os
import re
import sys
from datetime import date, datetime, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

frappe = F.cai()
Q = F.nap_qc()
for t in ("khieu_nai", "ncc", "rework", "attp", "ho_so"):
    F.nap(f"sx.qc.{t}", f"sx/qc/{t}.py")
for t in ("qc_ncc", "qc_attp", "qc_vaiu", "qc_hoso"):
    F.nap(f"sx.api.{t}", f"sx/api/{t}.py")
VU = sys.modules["sx.qc.vai_u"]
NH = sys.modules["sx.qc.nhac"]
A = sys.modules["sx.qc.attp"]
HS = sys.modules["sx.qc.ho_so"]
API = sys.modules["sx.api.qc_vaiu"]
ATTP = sys.modules["sx.api.qc_attp"]
HSA = sys.modules["sx.api.qc_hoso"]
GV = F.nap("gv_ctl", "sx/qc/doctype/sx_giat_vai/sx_giat_vai.py")
VC = F.nap("vu_ctl", "sx/qc/doctype/sx_vai_u/sx_vai_u.py")
F.dang_ky(VU.PT, GV.SXGiatVai)
F.dang_ky(VU.VAI, VC.SXVaiU, ten_theo="ma")
F.bang_con(VU.PT, "vai", VU.CON)
HCT = F.nap("hs_ctl", "sx/qc/doctype/sx_ho_so_danh_muc/sx_ho_so_danh_muc.py")
F.dang_ky(HS.PT, HCT.SXHoSoDanhMuc)
P = F.nap("sx.patches.d163_vai_u", "sx/patches/d163_vai_u.py")
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")          # thứ Sáu
GD, NL, NH_, LO = VU.DINH_KY, VU.NGOAI_LICH, VU.NHAP, VU.LOAI
VAI, DONG = F.bang(VU.VAI), F.bang(VU.PT)


def vai(ma):
    return VAI.get(ma) or {}


def ghi(**k):
    """Gọi API ghi như màn — payload JSON."""
    p = dict({"ngay": "2026-10-09", "viec": GD, "vai": [], "nguoi_lam": "Chị Lan", "phoi_tai": "Giá phơi mái che",
              "gio_soi_lai": "07:00", "gio_vot": "07:12", "cat_luc": "2026-10-09T15:30"}, **k)
    return API.ghi(json.dumps(p))


def loi(f):
    return thu(f) or ""


# ═══ 1. Hàm thuần ═══════════════════════════════════════════════════════════
print("-- hàm thuần: mã vải, số phút đun sôi --")
kiem("mã vải chuẩn: ' v01-a ' → 'V01-A'; thùng đọc từ mã (V12-B → 12); mã khác mẫu → thùng trống",
     (VU.chuan_ma(" v01-a "), VU.thung_cua("v12-b"), VU.thung_cua("CARO-1")) == ("V01-A", "12", ""))
kiem("số phút = giờ vớt − giờ sôi lại: 07:00 → 07:12 = 12", VU.so_phut("07:00", "07:12") == 12)
kiem("vớt qua nửa đêm: 23:55 → 00:07 = 12 phút (không âm)", VU.so_phut("23:55", "00:07") == 12)
kiem("ô Time từ DB là timedelta / time / '07:05:00' đều đọc được",
     VU.so_phut(timedelta(hours=7), time(7, 10)) == 10 and VU.so_phut("07:05:00", "07:15:30") == 10)
kiem("thiếu một đầu / giờ sai → None (không đoán)",
     (VU.so_phut("07:00", None), VU.so_phut("", "07:10"), VU.so_phut("25:00", "07:10")) == (None, None, None))
kiem("giờ để in 'HH:MM'", (VU.gio(timedelta(hours=7, minutes=5)), VU.gio("7:05"), VU.gio(None)) == ("07:05", "07:05", ""))

print("\n-- hàm thuần: chặn ghi, chặn ký --")
D = {"ngay": "2026-10-09", "viec": GD, "vai": ["V01-A"], "nguoi_lam": "Lan"}
kiem("dòng đủ → không lỗi", VU.loi_dong(D, "2026-10-09") is None)
kiem("ngày sau hôm nay → chặn", "sau hôm nay" in VU.loi_dong(dict(D, ngay="2026-10-10"), "2026-10-09"))
kiem("không mã vải, không số lượng → chặn; chỉ số lượng (chưa khâu mã) → được",
     "mã vải" in VU.loi_dong(dict(D, vai=[]), "2026-10-09")
     and VU.loi_dong(dict(D, vai=[], so_luong=4), "2026-10-09") is None)
kiem("giặt ngoài lịch / loại vải thiếu lý do → chặn; giặt định kỳ không cần lý do",
     "lý do" in VU.loi_dong(dict(D, viec=NL), "2026-10-09") and "lý do" in VU.loi_dong(dict(D, viec=LO), "2026-10-09")
     and VU.loi_dong(dict(D, viec=NL, ly_do="vải ẩm"), "2026-10-09") is None)
kiem("thiếu người làm → chặn; việc lạ → chặn",
     "người làm" in VU.loi_dong(dict(D, nguoi_lam=" "), "2026-10-09")
     and "Chọn việc" in VU.loi_dong(dict(D, viec="Giặt khô"), "2026-10-09"))
kiem("giờ sai dạng → chặn; giờ cất trước ngày giặt → chặn",
     "giờ sôi lại" in VU.loi_dong(dict(D, gio_soi_lai="7 giờ"), "2026-10-09")
     and "trước ngày giặt" in VU.loi_dong(dict(D, cat_luc="2026-10-08 20:00:00"), "2026-10-09"))
K = dict(D, gio_soi_lai="07:00", gio_vot="07:10", phoi_tai="Giá A", cat_luc="2026-10-09 15:00:00")
kiem("ký: giặt đun đúng 10 phút, có chỗ phơi, giờ cất → ký được", VU.loi_ky(K) is None)
kiem("ký: giặt đun 9 phút → 'đun lại cho đủ 10 phút'",
     "đun lại cho đủ 10 phút" in (VU.loi_ky(dict(K, gio_vot="07:09")) or ""))
kiem("ký: giặt chưa ghi giờ đun / chưa ghi chỗ phơi / chưa ghi giờ cất → chưa ký được",
     "giờ sôi lại" in VU.loi_ky(dict(K, gio_vot=None)) and "chỗ phơi" in VU.loi_ky(dict(K, phoi_tai=""))
     and "cất" in VU.loi_ky(dict(K, cat_luc=None)))
kiem("ký: nhập vải mới, loại vải không bắt đun sôi", VU.loi_ky({"viec": NH_}) is None and VU.loi_ky({"viec": LO}) is None)
kiem("ký: nhập vải mới mới ghi giờ sôi lại, chưa ghi giờ vớt → chưa ký được",
     "giờ vớt" in (VU.loi_ky({"viec": NH_, "gio_soi_lai": "08:00"}) or ""))
kiem("ký: nhập vải mới mà ĐÃ ghi giờ đun 7 phút → cũng chặn (sổ ghi làm sai)",
     "đun lại" in (VU.loi_ky({"viec": NH_, "gio_soi_lai": "08:00", "gio_vot": "08:07"}) or ""))
kiem("hạn xem tháng: ngày 5 → tháng trước còn hạn (mốc = đầu tháng trước); ngày 6 → mốc = đầu tháng này",
     (VU.thang_qua_han_xem("2026-10-05"), VU.thang_qua_han_xem("2026-10-06")) == (date(2026, 9, 1), date(2026, 10, 1)))

# ═══ 2. Danh mục vải ═══════════════════════════════════════════════════════
print("\n-- danh mục vải: QLSX / Ban ISO khai --")
F.vai("SX QC")
kiem("QC không khai danh mục vải", "QLSX hoặc Ban ISO" in loi(lambda: API.luu_vai(json.dumps({"ma": "V01-A"}))))
F.vai("Production Manager", u="qlsx@x")
r = API.luu_vai(json.dumps({"ma": " v01-a ", "trang_thai": VU.DANG_DUNG, "moi": 1}))
kiem("QLSX khai ' v01-a ' Đang dùng → V01-A, thùng 01 tự đọc từ mã",
     r == {"ma": "V01-A", "thung": "01", "trang_thai": VU.DANG_DUNG} and vai("V01-A")["trang_thai"] == VU.DANG_DUNG, r)
API.luu_vai(json.dumps({"ma": "V01-B", "moi": 1}))
API.luu_vai(json.dumps({"ma": "V02-A", "trang_thai": VU.DANG_DUNG, "thung": "02", "moi": 1}))
kiem("bỏ trạng thái → Dự phòng", vai("V01-B")["trang_thai"] == VU.DU_PHONG)
kiem("khai trùng mã → báo đã có", "đã có trong danh mục" in loi(lambda: API.luu_vai(json.dumps({"ma": "v01-a", "moi": 1}))))
kiem("loại vải tay ở danh mục → chặn (phải ghi dòng Loại vải trong sổ)",
     "Loại vải" in loi(lambda: API.luu_vai(json.dumps({"ma": "V01-B", "trang_thai": VU.DA_LOAI})))
     and vai("V01-B")["trang_thai"] == VU.DU_PHONG)
API.luu_vai(json.dumps({"ma": "V01-B", "trang_thai": VU.DANG_DUNG}))
API.luu_vai(json.dumps({"ma": "V01-B", "trang_thai": VU.DU_PHONG}))
kiem("Đang dùng ↔ Dự phòng đổi tự do", vai("V01-B")["trang_thai"] == VU.DU_PHONG)
F.vai("ISO Manager")
API.luu_vai(json.dumps({"ma": "V09-Z", "moi": 1}))
kiem("Ban ISO khai được; xoá vải khai nhầm (chưa dòng sổ nào ghi tới)",
     "V09-Z" in VAI and API.xoa_vai("V09-Z") == {"ma": "V09-Z"} and "V09-Z" not in VAI)
frappe.get_doc({"doctype": VU.VAI, "ma": " v05-a ", "trang_thai": VU.DU_PHONG}).insert()
kiem("Desk: khai ' v05-a ' → tên V05-A, thùng 05", "V05-A" in VAI and vai("V05-A")["thung"] == "05")

# ═══ 3. Ghi, ký ════════════════════════════════════════════════════════════
print("\n-- sổ giặt: ghi, ký --")
F.vai("Production Manager", u="qlsx@x")
kiem("QLSX không ghi sổ giặt (QC ghi hộ người giặt)", "QC" in loi(lambda: ghi(vai=["V01-A"])))
F.vai("SX QC")
r = ghi(vai=["V01-A", "v02-a"], ky=1)
g1 = r["name"]
kiem("QC ghi giặt định kỳ + ký luôn: 07:00 → 07:12 = 12 phút, đã ký",
     r["so_phut"] == 12 and r["da_ky"] and DONG[g1]["qc_ky_boi"] == "qc@x" and DONG[g1]["ghi_boi"] == "qc@x"
     and [x["vai"] for x in F.bang(VU.CON).values() if x["parent"] == g1] == ["V01-A", "V02-A"], r)
n = len(DONG)
kiem("đun 8 phút mà bấm LƯU VÀ KÝ → chặn 'đun lại cho đủ 10 phút', không lưu gì",
     "đun lại cho đủ 10 phút" in loi(lambda: ghi(ngay="2026-10-08", vai=["V01-A"], gio_vot="07:08", ky=1))
     and len(DONG) == n)
r = ghi(ngay="2026-10-08", viec=NL, ly_do="Vải ẩm, có mùi", vai=["V01-A"], gio_vot="07:08")
g2 = r["name"]
kiem("đun 8 phút, LƯU (ký sau) → lưu, chưa ký, nói rõ vì sao chưa ký được",
     not r["da_ky"] and r["so_phut"] == 8 and "đun lại cho đủ 10 phút" in r["chua_ky_duoc"], r)
kiem("QC bấm ký dòng đun 8 phút → chặn", "đun lại cho đủ 10 phút" in loi(lambda: API.ky(g2)))
ghi(name=g2, ngay="2026-10-08", viec=NL, ly_do="Vải ẩm, có mùi", vai=["V01-A"], gio_soi_lai="07:20", gio_vot="07:31")
kiem("đun lại, ghi giờ mới (07:20 → 07:31) → ký được", API.ky(g2)["name"] == g2 and DONG[g2]["qc_ky_luc"])
kiem("ký lần hai → báo đã ký", "đã ký" in loi(lambda: API.ky(g2)))
kiem("dòng đã ký: QC sửa → chặn (chỉ Ban ISO)",
     "chỉ Ban ISO" in loi(lambda: ghi(name=g2, ngay="2026-10-08", viec=NL, ly_do="sửa", vai=["V01-A"],
                                      gio_soi_lai="07:20", gio_vot="07:31")))
d = frappe.get_doc(VU.PT, g2)
d.set("vai", [{"vai": "V02-A"}])
kiem("… kể cả chỉ đổi mã vải (đường Desk)", "chỉ Ban ISO" in loi(d.save))
d = frappe.get_doc(VU.PT, g2)
d.gio_soi_lai, d.gio_vot = timedelta(hours=7, minutes=20), "07:31:00"
kiem("… lưu lại y nguyên (giờ đọc từ DB là timedelta) không bị coi là sửa", thu(d.save) is None)
F.vai("ISO Manager")
d = frappe.get_doc(VU.PT, g2)
d.phoi_tai = "Giá phơi trong nhà (trời nồm)"
kiem("Ban ISO sửa dòng đã ký được (Desk)", thu(d.save) is None and DONG[g2]["phoi_tai"].startswith("Giá phơi trong"))
d = frappe.get_doc(VU.PT, g2)
d.gio_vot = "07:25:00"
kiem("… nhưng dòng đã ký vẫn phải đủ điều kiện ký: sửa giờ thành 5 phút → chặn",
     "đun lại" in loi(d.save))
F.vai("SX QC")
kiem("mã chưa có trong danh mục (việc giặt) → chặn, nói QLSX khai hoặc chọn Nhập vải mới",
     "chưa có trong danh mục" in loi(lambda: ghi(vai=["V07-A"])) and "V07-A" not in VAI)
r = ghi(ngay="2026-10-01", vai=[], so_luong=6, gio_soi_lai="", gio_vot="", phoi_tai="", cat_luc="")
kiem("chỉ ghi số lượng (vải chưa có mã) → lưu được; chưa ghi giờ đun → chưa ký được",
     DONG[r["name"]]["so_luong"] == 6 and not r["da_ky"] and "giờ sôi lại" in r["chua_ky_duoc"], r)
g3 = r["name"]
kiem("ngày sau hôm nay → chặn", "sau hôm nay" in loi(lambda: ghi(ngay="2026-10-10", vai=["V01-A"])))
d = frappe.get_doc({"doctype": VU.PT, "ngay": "2026-10-09", "viec": GD, "nguoi_lam": "Lan",
                    "vai": [{"vai": "V02-A"}, {"vai": "V02-A"}]})
kiem("Desk: một mã ghi hai lần trong một dòng → chặn", "ghi hai lần" in loi(d.insert))
d = frappe.get_doc({"doctype": VU.PT, "ngay": "2026-10-09", "viec": GD, "nguoi_lam": "Lan", "vai": [{"vai": "V77-A"}]})
kiem("Desk: mã không có trong danh mục → chặn", "chưa có trong danh mục" in loi(d.insert))
r = ghi(ngay="2026-10-09", vai=["V02-A", " v02-a"], ky=1)
kiem("mã gửi trùng (gõ hai kiểu) → gộp một", [x["vai"] for x in F.bang(VU.CON).values() if x["parent"] == r["name"]]
     == ["V02-A"])
F.vai("ISO Manager")
F.delete_doc(VU.PT, r["name"])
F.vai("SX QC")
n = len(VAI)
kiem("nhập vải mới bấm LƯU VÀ KÝ mà đun 7 phút → chặn TRƯỚC khi thêm vải vào danh mục",
     "đun lại" in loi(lambda: ghi(viec=NH_, vai="V08-A", gio_soi_lai="08:00", gio_vot="08:07", ky=1))
     and "V08-A" not in VAI and len(VAI) == n)
kiem("ô giờ trống gửi lên là trống, giờ cất 'T' của ô datetime-local đổi thành ' '",
     DONG[g1]["cat_luc"] == "2026-10-09 15:30:00" and DONG[g3]["gio_soi_lai"] is None)

# ═══ 4. Nhập vải mới, loại vải → danh mục ════════════════════════════════
print("\n-- nhập vải mới, loại vải → danh mục --")
n = len(VAI)
kiem("nhập vải mới hỏng (thiếu người làm) → không thêm vải nào vào danh mục",
     "người làm" in loi(lambda: ghi(viec=NH_, vai="V03-A, V03-B", nguoi_lam="")) and len(VAI) == n)
r = ghi(ngay="2026-10-07", viec=NH_, vai="v03-a; V03-B", gio_soi_lai="", gio_vot="", phoi_tai="", cat_luc="")
gn = r["name"]
kiem("nhập vải mới 'v03-a; V03-B' → 2 vải Dự phòng, ngày nhập, dòng nhập, thùng 03",
     r["vai_moi"] == ["V03-A", "V03-B"] and all(vai(m)["trang_thai"] == VU.DU_PHONG and vai(m)["thung"] == "03"
                                               and str(vai(m)["ngay_nhap"]) == "2026-10-07" and vai(m)["dong_nhap"] == gn
                                               for m in ("V03-A", "V03-B")), r)
kiem("nhập vải mới không bắt đun sôi khi ký", API.ky(gn)["name"] == gn)
kiem("nhập đè mã của vải còn đang dùng → chặn (ghi Loại vải trước)",
     "Loại vải trước" in loi(lambda: ghi(viec=NH_, vai=["V01-A"])))
kiem("nhập đè mã đã nhập (Dự phòng có dòng nhập) → chặn", "Loại vải trước" in loi(lambda: ghi(viec=NH_, vai=["V03-A"])))
F.vai("Production Manager", u="qlsx@x")
API.luu_vai(json.dumps({"ma": "V04-A", "moi": 1}))
F.vai("SX QC")
r = ghi(ngay="2026-10-08", viec=NH_, vai=["V04-A"], gio_soi_lai="", gio_vot="", phoi_tai="", cat_luc="")
kiem("vải QLSX khai trước (Dự phòng, chưa dòng nhập) → nhập được, gắn dòng nhập",
     vai("V04-A")["dong_nhap"] == r["name"] and str(vai("V04-A")["ngay_nhap"]) == "2026-10-08")

kiem("loại vải thiếu lý do → chặn", "lý do" in loi(lambda: ghi(viec=LO, vai=["V01-A"])))
r = ghi(ngay="2026-10-05", viec=LO, vai=["V01-A"], ly_do="Rách mép, sổ chỉ", gio_soi_lai="", gio_vot="",
        phoi_tai="", cat_luc="", ky=1)
gl = r["name"]
v = vai("V01-A")
kiem("loại vải (ngày 05/10) → V01-A Đã loại, ngày loại, lý do, dòng loại — KHÔNG xoá vải",
     v["trang_thai"] == VU.DA_LOAI and str(v["ngay_loai"]) == "2026-10-05" and v["ly_do_loai"] == "Rách mép, sổ chỉ"
     and v["dong_loai"] == gl and r["da_ky"], v)
kiem("giặt vải đã loại vào ngày SAU ngày loại → chặn",
     "đã loại" in loi(lambda: ghi(ngay="2026-10-06", vai=["V01-A"])))
kiem("… ghi bù lần giặt TRƯỚC ngày loại, hay cùng ngày (giặt cả mẻ rồi mới loại) → được",
     thu(lambda: ghi(ngay="2026-10-02", vai=["V01-A"])) is None and thu(lambda: ghi(ngay="2026-10-05", vai=["V01-A"])) is None)
kiem("loại lần hai → chặn", "đã loại ngày 05/10/2026" in loi(lambda: ghi(viec=LO, vai=["V01-A"], ly_do="x")))
F.vai("ISO Manager")
d = frappe.get_doc(VU.PT, gl)
d.ly_do = "Rách mép, sổ chỉ, ố"
kiem("Ban ISO sửa lý do dòng loại (vải đã loại theo chính dòng này) → được, danh mục theo lý do mới",
     thu(d.save) is None and vai("V01-A")["ly_do_loai"] == "Rách mép, sổ chỉ, ố")
d = frappe.get_doc(VU.PT, gl)
d.viec = NL
kiem("dòng đã ký đổi thành giặt mà chưa có giờ đun → chặn (dòng đã ký phải đủ điều kiện ký)", "giờ vớt" in loi(d.save))
d.gio_soi_lai, d.gio_vot, d.phoi_tai, d.cat_luc = "07:00:00", "07:10:00", "Giá A", "2026-10-05 16:00:00"
d.save()
kiem("đổi việc dòng loại thành giặt ngoài lịch (ghi nhầm việc) → V01-A hết Đã loại", vai("V01-A")["trang_thai"] == VU.DU_PHONG)
d = frappe.get_doc(VU.PT, gl)
d.viec = LO
d.save()
kiem("… đổi lại Loại vải → Đã loại", vai("V01-A")["trang_thai"] == VU.DA_LOAI)
F.vai("SX QC")
F.vai("Production Manager", u="qlsx@x")
kiem("QLSX dựng lại vải đã loại ở danh mục → chặn (vải thay mới thì ghi Nhập vải mới)",
     "Nhập vải mới" in loi(lambda: API.luu_vai(json.dumps({"ma": "V01-A", "trang_thai": VU.DU_PHONG}))))
kiem("… sửa ghi chú vải đã loại (không đổi trạng thái) thì được",
     thu(lambda: API.luu_vai(json.dumps({"ma": "V01-A", "ghi_chu": "thay vải mới"}))) is None
     and vai("V01-A")["trang_thai"] == VU.DA_LOAI)
F.vai("SX QC")
r = ghi(ngay="2026-10-06", viec=NH_, vai=["V01-A"], gio_soi_lai="09:00", gio_vot="09:15", phoi_tai="", cat_luc="")
gm = r["name"]
v = vai("V01-A")
kiem("vải thay mới khâu lại ĐÚNG mã V01-A (nhập vải mới) → Dự phòng, bỏ dấu loại (HD.08.02 mục 8)",
     v["trang_thai"] == VU.DU_PHONG and not v["ngay_loai"] and not v["dong_loai"] and v["dong_nhap"] == gm
     and str(v["ngay_nhap"]) == "2026-10-06" and r["vai_moi"] == [], v)
d = frappe.get_doc(VU.PT, gm)
d.ngay = "2026-10-04"
F.vai("ISO Manager")
d.save()
kiem("sửa ngày dòng nhập về TRƯỚC ngày loại → mới nhất là loại → V01-A lại Đã loại",
     vai("V01-A")["trang_thai"] == VU.DA_LOAI and vai("V01-A")["dong_loai"] == gl)
d = frappe.get_doc(VU.PT, gm)
d.ngay = "2026-10-06"
d.save()
F.delete_doc(VU.PT, gm)
kiem("xoá dòng nhập thay mới → V01-A về Đã loại theo dòng loại", vai("V01-A")["trang_thai"] == VU.DA_LOAI)
F.delete_doc(VU.PT, gl)
v = vai("V01-A")
kiem("xoá dòng loại → V01-A về Dự phòng, hết dấu loại, hết ngày nhập của dòng đã xoá (QLSX đưa lại Đang dùng nếu cần)",
     v["trang_thai"] == VU.DU_PHONG and not v["ngay_loai"] and not v["ly_do_loai"] and not v["dong_loai"]
     and not v["ngay_nhap"], v)
d = frappe.get_doc(VU.PT, gn)
F.vai("ISO Manager")
d.set("vai", [{"vai": "V03-A"}])
d.save()
kiem("sửa dòng nhập bỏ V03-B → V03-B hết dòng nhập, hết ngày nhập (vẫn còn trong danh mục)",
     vai("V03-B")["dong_nhap"] is None and not vai("V03-B")["ngay_nhap"] and vai("V03-A")["dong_nhap"] == gn
     and str(vai("V03-A")["ngay_nhap"]) == "2026-10-07")
F.vai("Production Manager", u="qlsx@x")
kiem("vải đã có trong sổ → không xoá được khỏi danh mục", "đã có trong sổ" in loi(lambda: API.xoa_vai("V03-A")))
kiem("vải hết dòng sổ (V03-B) → xoá được (khai nhầm)", API.xoa_vai("V03-B") == {"ma": "V03-B"})

# ═══ 5. Xoá dòng ═══════════════════════════════════════════════════════════
print("\n-- xoá dòng --")
F.vai("SX QC")
r = ghi(ngay="2026-10-09", viec=NL, ly_do="vải ẩm", vai=["V02-A"])
gx = r["name"]
F.vai("SX QC", u="qc2@x")
kiem("QC khác xoá dòng người khác ghi → chặn", "Chỉ người ghi" in loi(lambda: API.xoa(gx)))
F.vai("SX QC")
DONG[gx]["creation"] = "2026-10-08 09:00:00"
kiem("người ghi xoá dòng ghi hôm qua → chặn", "Chỉ người ghi" in loi(lambda: API.xoa(gx)))
DONG[gx]["creation"] = "2026-10-09 09:00:00"
kiem("người ghi xoá trong ngày, chưa ký → được", API.xoa(gx) == {"name": gx} and gx not in DONG)
kiem("dòng đã ký → người ghi không xoá được", "Chỉ người ghi" in loi(lambda: API.xoa(g1)))
d = frappe.get_doc(VU.PT, g1)
kiem("… kể cả đi đường Desk (controller chặn)", "chỉ Ban ISO" in loi(lambda: F.delete_doc(VU.PT, g1)) and g1 in DONG)

# ═══ 6. Trưởng Ban ISO xem tháng ═════════════════════════════════════════
print("\n-- Trưởng Ban ISO xem tháng --")
for vt in ("SX QC", "Production Manager"):
    F.vai(vt)
    kiem(f"{vt} không bấm được 'Đã xem tháng'", "Trưởng Ban ISO" in loi(lambda: API.xem_thang("2026-10")))
F.vai("ISO Manager")
kiem("tháng chưa tới → chặn", "chưa tới" in loi(lambda: API.xem_thang("2026-11")))
kiem("tháng không có dòng → báo", "không có dòng" in loi(lambda: API.xem_thang("2026-08")))
cho_ky = sum(1 for x in DONG.values() if str(x["ngay"]).startswith("2026-10") and not x.get("qc_ky_luc"))
r = API.xem_thang("2026-10", " Đủ 1 lần/tuần; nhắc QC ký dòng 01/10 ")
thang10 = [x for x in DONG.values() if str(x["ngay"]).startswith("2026-10")]
kiem("ISO xem tháng 10 → mọi dòng của tháng có người xem, giờ, nhận xét (đã bỏ khoảng trắng)",
     r["so"] == len(thang10) and all(x["xem_boi"] == "iso@x" and x["xem_nhan_xet"] == "Đủ 1 lần/tuần; nhắc QC ký dòng 01/10"
                                     for x in thang10) and cho_ky >= 1, r)
kiem("bấm lần hai → báo không còn dòng chưa xem", "không có dòng" in loi(lambda: API.xem_thang("2026-10")))
F.vai("SX QC")
kiem("dòng Ban ISO đã xem: QC sửa nội dung → chặn",
     "Trưởng Ban ISO xem" in loi(lambda: ghi(name=g3, ngay="2026-10-01", vai=[], so_luong=7, gio_soi_lai="",
                                              gio_vot="", phoi_tai="", cat_luc="")))
d = frappe.get_doc(VU.PT, g3)
d.gio_soi_lai, d.gio_vot, d.phoi_tai, d.cat_luc = "07:00:00", "07:10:00", "Giá A", "2026-10-01 16:00:00"
F.vai("ISO Manager")
d.save()
F.vai("SX QC")
kiem("dòng đã xem mà chưa ký: QC vẫn ký muộn được (chỉ khoá nội dung)", API.ky(g3)["name"] == g3)

# ═══ 7. Hộp nhắc ═════════════════════════════════════════════════════════
print("\n-- hộp nhắc --")
DONG.clear()
F.bang(VU.CON).clear()
VAI.clear()


def nhac(hom_nay="2026-10-09"):
    F.dat_ngay(hom_nay)
    ds = NH.tinh(hom_nay, [], [], {}, vai_u=VU.nhac(hom_nay))
    return [x for x in ds if x["nhom"] == "vai_u"]


def dong(ten, ngay, viec=GD, tao=None, **k):
    DONG[ten] = dict({"name": ten, "ngay": ngay, "viec": viec, "creation": f"{tao or ngay} 09:00:00",
                      "qc_ky_luc": "2026-10-09 10:00:00", "xem_luc": None}, **k)


kiem("chưa khai vải nào, sổ trống → không nhắc gì (C31)", nhac() == [])
VAI["V01-A"] = {"name": "V01-A", "ma": "V01-A", "trang_thai": VU.DU_PHONG}
kiem("chỉ có vải Dự phòng → vẫn không nhắc giặt", nhac() == [])
dong("G-cu", "2026-09-01", xem_luc="2026-10-01 08:00:00")
kiem("… kể cả sổ có lần giặt cũ đã quá hạn (vải không còn dùng thì không có gì để giặt)", nhac() == [])
DONG.pop("G-cu")
VAI["V01-A"]["trang_thai"] = VU.DANG_DUNG
x = nhac()
kiem("có vải Đang dùng mà sổ chưa có lần giặt định kỳ nào → nhắc ghi (ghi bù được)",
     len(x) == 1 and "chưa có lần giặt định kỳ" in x[0]["tieu_de"] and x[0]["route"] == "#/qc/vaiu", x)
dong("G1", "2026-10-02")
kiem("giặt định kỳ 7 ngày trước → chưa quá hạn, không nhắc", nhac() == [])
dong("G2", "2026-10-03", NL, ly_do="ẩm")
DONG.pop("G1")
dong("G0", "2026-10-01")
x = nhac()
kiem("8 ngày chưa giặt định kỳ → nhắc thường (giặt ngoài lịch không thay cho giặt định kỳ)",
     len(x) == 1 and x[0]["tieu_de"] == "Vải ủ 8 ngày chưa giặt định kỳ" and x[0]["muc_do"] == "thuong"
     and "01/10" in x[0]["chi_tiet"], x)
x = nhac("2026-10-16")
kiem("15 ngày (quá gấp đôi chu kỳ) → mức cao", x[0]["muc_do"] == "cao" and "15 ngày" in x[0]["tieu_de"], x)
F.CAI_DAT["vai_u_giat_moi_lan"] = 1
x = nhac("2026-10-06")
kiem("giặt sau mỗi lần dùng (thẩm tra không đạt): giặt ngoài lịch cũng tính, quá 2 ngày → nhắc",
     len(x) == 1 and x[0]["tieu_de"] == "Vải ủ 3 ngày chưa giặt (giặt sau mỗi lần dùng)", x)
kiem("… 2 ngày thì chưa", nhac("2026-10-05") == [])
F.CAI_DAT["vai_u_thu_giat"] = "Thứ Hai"
kiem("… đang giặt sau mỗi lần dùng thì không nhắc 'ngày giặt cố định' (thứ Hai 05/10)", nhac("2026-10-05") == [])
F.CAI_DAT.pop("vai_u_thu_giat")
F.CAI_DAT.pop("vai_u_giat_moi_lan")
F.CAI_DAT["vai_u_thu_giat"] = "Thứ Sáu"
dong("G0", "2026-10-05")
x = nhac("2026-10-09")
kiem("hôm nay (thứ Sáu) là ngày giặt cố định, chưa ghi → nhắc", len(x) == 1 and "thứ sáu" in x[0]["tieu_de"], x)
dong("G9", "2026-10-09")
kiem("… ghi giặt định kỳ hôm nay rồi → hết nhắc", nhac("2026-10-09") == [])
kiem("ngày khác ngày giặt → không nhắc", nhac("2026-10-08") == [])
F.CAI_DAT.pop("vai_u_thu_giat")
DONG.clear()
dong("G0", "2026-10-09")
dong("C1", "2026-10-06", NL, tao="2026-10-07", qc_ky_luc=None)
dong("C2", "2026-10-08", tao="2026-10-08", qc_ky_luc=None)
x = nhac()
kiem("dòng chờ QC ký quá 1 ngày (ghi 07/10) → nhắc; dòng ghi hôm qua chưa nhắc",
     len(x) == 1 and x[0]["tieu_de"] == "1 dòng sổ giặt vải ủ chờ QC ký" and "06/10" in x[0]["chi_tiet"], x)
VAI.clear()
kiem("chờ ký vẫn nhắc dù chưa khai vải (dòng đã có trong sổ)", len(nhac()) == 1)
DONG.clear()
dong("T9", "2026-09-20")
kiem("ngày 05/10: tháng 9 chưa xem nhưng còn hạn → không nhắc", nhac("2026-10-05") == [])
x = nhac("2026-10-06")
kiem("ngày 06/10: tháng 9 chưa được Trưởng Ban ISO xem → nhắc",
     len(x) == 1 and x[0]["tieu_de"] == "Sổ giặt vải ủ tháng 09/2026 chưa được Trưởng Ban ISO xem", x)
dong("T8", "2026-08-11")
kiem("tháng cũ hơn chưa xem cũng nhắc, cũ trước",
     [re.search(r"\d\d/\d{4}", y["tieu_de"]).group() for y in nhac("2026-10-06")] == ["08/2026", "09/2026"])
DONG["T9"]["xem_luc"] = DONG["T8"]["xem_luc"] = "2026-10-06 08:00:00"
kiem("đã xem → hết nhắc", nhac("2026-10-06") == [])
goc = frappe.db.count
frappe.db.count = lambda *a, **k: 1 / 0
kiem("chưa migrate (lỗi đọc) → {} — hộp nhắc không chết", VU.nhac("2026-10-09") == {})
frappe.db.count = goc
F.dat_ngay("2026-10-09")

# ═══ 8. Tổng quan ATTP, hồ sơ, bản in ═════════════════════════════════════
print("\n-- Tổng quan ATTP, danh mục hồ sơ, gói zip, bản in --")
kiem("mảng vải ủ ở Tổng quan ATTP: sau cát rang, BM.08.05, #/qc/vaiu",
     ("vai_u", "Vải ủ", "BM.08.05", "#/qc/vaiu") in A.LINH_VUC
     and [x[0] for x in A.LINH_VUC].index("vai_u") == [x[0] for x in A.LINH_VUC].index("cat") + 1)
DONG.clear()
VAI.update({"V01-A": {"name": "V01-A", "trang_thai": VU.DANG_DUNG}, "V01-B": {"name": "V01-B", "trang_thai": VU.DU_PHONG},
            "V02-A": {"name": "V02-A", "trang_thai": VU.DA_LOAI}})
dong("A1", "2026-09-25")
dong("A2", "2026-10-02", qc_ky_luc=None, tao="2026-10-02")
dong("A3", "2026-10-03", NL, ly_do="ẩm")
F.vai("ISO Manager")
th = {x["ma"]: x for x in ATTP.tong_quan()["linh_vuc"]}["vai_u"]
kiem("thẻ vải ủ: 3 lần giặt trong 30 ngày, gần nhất 02/10, 1 đang dùng · 1 dự phòng · 1 đã loại, 1 chờ ký → Vàng",
     th["so"] == "3" and th["dong"] == ["Giặt gần nhất 02/10/2026 · chu kỳ 7 ngày",
                                        "1 vải đang dùng · 1 dự phòng · 1 đã loại", "1 dòng chờ QC ký"]
     and th["den"] == A.VANG and th["nhac"][0]["nhom"] == "vai_u", th)
kiem("thẻ khi chưa khai vải, chưa ghi sổ → '–'; chưa khai vải mà sổ đã có lần giặt → vẫn hiện số",
     A.THE["vai_u"]({"dang_dung": 0, "so_lan": 0})["so"] == "–"
     and A.THE["vai_u"]({"dang_dung": 0, "so_lan": 2, "lan_cuoi": "2026-10-02"})["so"] == "2")
kiem("BIEU_MAU có BM.08.05 → mảng vai_u", HS.BIEU_MAU.get("BM.08.05") == ("Sổ giặt vải ủ", "vai_u"))
hs = json.load(open("sx/qc/doctype/sx_ho_so_danh_muc/sx_ho_so_danh_muc.json", encoding="utf-8"))
kiem("Select 'Biểu mẫu app' có BM.08.05 (W46: options = BIEU_MAU)",
     "BM.08.05" in next(f for f in hs["fields"] if f["fieldname"] == "bieu_mau")["options"].split("\n"))

DONG.clear()
F.bang(VU.CON).clear()
DONG.update({
    "P1": {"name": "P1", "ngay": "2026-10-05", "viec": GD, "gio_soi_lai": timedelta(hours=7), "gio_vot": timedelta(hours=7, minutes=12),
           "so_phut": 12, "phoi_tai": "Giá mái che", "cat_luc": datetime(2026, 10, 5, 15, 30), "nguoi_lam": "Chị Lan",
           "qc_ky_boi": "qc@x", "qc_ky_luc": datetime(2026, 10, 5, 16, 0), "creation": "2026-10-05 08:00:00",
           "xem_boi": "iso@x", "xem_luc": datetime(2026, 10, 9, 9, 0), "xem_nhan_xet": "Đạt, đủ chu kỳ"},
    "P2": {"name": "P2", "ngay": "2026-10-07", "viec": LO, "ly_do": "Rách mép", "so_luong": 2, "so_phut": 0,
           "nguoi_lam": "Chị Lan", "creation": "2026-10-07 08:00:00", "su_co": "SC-0007"},
    "P3": {"name": "P3", "ngay": "2026-10-08", "viec": NL, "ly_do": "ẩm", "gio_soi_lai": "23:55:00",
           "gio_vot": "00:03:00", "so_phut": 8, "nguoi_lam": "Chị Lan", "creation": "2026-10-08 08:00:00"}})
F.bang(VU.CON).update({"c1": {"name": "c1", "parent": "P1", "parenttype": VU.PT, "vai": "V01-A", "idx": 1},
                       "c2": {"name": "c2", "parent": "P1", "parenttype": VU.PT, "vai": "V01-B", "idx": 2},
                       "c3": {"name": "c3", "parent": "P2", "parenttype": VU.PT, "vai": "V02-A", "idx": 1}})
F.CAI_DAT.update({"vai_u_noi_giat": "Nhà giặt sau xưởng", "vai_u_thu_giat": "Thứ Hai"})
F.vai("SX QC")
h = re.sub(r"\s+", " ", API.in_bm0805("2026-10"))
kiem("bản in BM.08.05: tiêu đề tháng, mã, lần BH 01, nơi giặt, ngày giặt cố định",
     "Sổ giặt vải ủ" in h and "tháng 10/2026" in h and "BM.08.05" in h and "Lần BH: 01" in h and "Kèm HD.08.02" in h
     and "Giặt tại: Nhà giặt sau xưởng" in h and "Ngày giặt cố định: Thứ Hai" in h)
kiem("đúng 8 cột giấy theo thứ tự",
     re.findall(r"<th[^>]*>(.*?)</th>", h) == ["Ngày", "Việc", "Mã vải (V01-A…) hoặc số lượng",
                                               "Lý do giặt ngoài lịch, loại vải", "Đun sôi: giờ sôi lại → giờ vớt (phút)",
                                               "Phơi tại; khô hẳn, cất lúc", "Người làm", "QC ký"])
kiem("dòng giặt: mã vải, 07:00 → 07:12 (12′), phơi + giờ cất, QC ký + ngày",
     "V01-A, V01-B" in h and "07:00 → 07:12 (12′)" in h and "Giá mái che; 15:30 05/10" in h and "qc@x · 05/10" in h)
kiem("dòng loại: số lượng, lý do + phiếu sự cố; dòng chưa ký ghi CHƯA KÝ",
     "V02-A · 2 vải" in h and "Rách mép · sự cố SC-0007" in h and h.count("CHƯA KÝ") == 2)
kiem("đun qua nửa đêm 23:55 → 00:03 = 8′, in đậm (chưa đủ 10 phút)",
     '<td class="thieu">23:55 → 00:03 (8′)</td>' in h)
kiem("dòng Trưởng Ban ISO xem xét cuối tháng: nhận xét, người, ngày",
     "Trưởng Ban ISO xem xét cuối tháng:</b> Đạt, đủ chu kỳ · iso@x · Ngày 09/10/2026" in h.replace("&nbsp;", ""))
h0 = re.sub(r"\s+", " ", API.in_bm0805("2026-08"))
kiem("tháng trống: 'chưa có dòng nào', ô xem xét để trống như giấy",
     "Tháng này chưa có dòng nào" in h0 and "Ngày ……/……/20……" in h0)
F.vai("ISO Manager")
f = HSA._in("BM.08.05", date(2026, 9, 1), date(2026, 10, 9))
kiem("gói zip hồ sơ: BM.08.05 mỗi tháng một tệp", [x[0] for x in f] == ["2026-09.html", "2026-10.html"]
     and "Sổ giặt vải ủ" in f[1][1] and "tháng 10/2026" in f[1][1])

# ═══ 9. Màn tong_quan, quyền ════════════════════════════════════════════════
print("\n-- tong_quan, quyền theo vai --")
DONG["P3"].update(xem_boi="iso@x", xem_luc=datetime(2026, 10, 8, 9, 0), xem_nhan_xet="Lần đầu")
DONG["P0"] = {"name": "P0", "ngay": "2026-09-20", "viec": GD, "phoi_tai": "Giá cũ", "nguoi_lam": "Lan",
              "creation": "2026-09-20 08:00:00"}
F.vai("SX QC")
r = API.tong_quan("2026-10")
kiem("dòng mới trước, kèm mã vải; số phút tính lại từ giờ (ô Int trống lưu 0 không làm '0 phút')",
     [x["name"] for x in r["ds"]] == ["P3", "P2", "P1"] and r["ds"][2]["vai"] == ["V01-A", "V01-B"]
     and r["ds"][1]["so_phut"] is None and r["ds"][0]["so_phut"] == 8 and r["ds"][2]["gio_soi_lai"] == "07:00")
kiem("lần xem GẦN NHẤT (không phải lần đầu), số dòng chưa xem / chưa ký của tháng",
     r["xem"]["nhan_xet"] == "Đạt, đủ chu kỳ" and r["chua_xem"] == 1 and r["chua_ky"] == 2, (r["xem"], r["chua_xem"]))
kiem("chỗ phơi gần nhất điền sẵn; cài đặt ngày giặt, nơi giặt",
     r["phoi_tai"] == "Giá mái che" and r["cai_dat"]["thu_giat"] == "Thứ Hai")
for vt, ghi_, khai, xem in (("SX QC", True, False, False), ("SX QC Packing", True, False, False),
                            ("Production Manager", False, True, False), ("ISO Manager", False, True, True),
                            ("SX Quan Ly", True, True, True)):
    F.vai(vt)
    r = API.tong_quan()
    kiem(f"{vt}: ghi/ký {ghi_} · khai vải {khai} · xem tháng {xem}",
         (r["duoc_ghi"], r["duoc_khai_vai"], r["duoc_xem_thang"]) == (ghi_, khai, xem))
F.vai("Stock User")
kiem("người ngoài QC không vào được", "không có quyền" in loi(API.tong_quan))
F.vai("SX QC")

# ═══ 10. Patch, DocType, nối màn ═══════════════════════════════════════════
print("\n-- patch D163, DocType, nối màn --")
F.bang(HS.PT).clear()
P.execute()
x = list(F.bang(HS.PT).values())
kiem("patch thêm BM.08.05 vào danh mục hồ sơ (App lập, nhóm Kiểm soát sản xuất)",
     len(x) == 1 and x[0]["ma"] == "BM.08.05" and x[0]["nguon"] == HS.APP and x[0]["bieu_mau"] == "BM.08.05"
     and x[0]["nhom"] == "Kiểm soát sản xuất", x)
P.execute()
kiem("chạy lại vô hại", len(F.bang(HS.PT)) == 1)
F.bang(HS.PT).clear()
F.bang(HS.PT)["h1"] = {"name": "h1", "ma": " bm.08.05 ", "nguon": HS.GIAY}
P.execute()
kiem("Ban ISO đã có dòng ' bm.08.05 ' (bản giấy) → giữ, không thêm", len(F.bang(HS.PT)) == 1)
kiem("patch có trong patches.txt", "sx.patches.d163_vai_u" in open("sx/patches.txt", encoding="utf-8").read())
kiem("patch KHÔNG khai sẵn vải (C31)", "SX Vai U" not in open("sx/patches/d163_vai_u.py", encoding="utf-8").read())


def meta(p):
    d = json.load(open(p, encoding="utf-8"))
    return d, {f["fieldname"]: f for f in d["fields"]}


d, f = meta("sx/qc/doctype/sx_giat_vai/sx_giat_vai.json")
kiem("SX Giat Vai: số GVU-.YYYY.-.#####, 4 việc, mã vải là Table MultiSelect SX Giat Vai Ma, số phút chỉ đọc",
     f["naming_series"]["options"] == "GVU-.YYYY.-.#####" and f["viec"]["options"].split("\n")[1:] == list(VU.VIEC)
     and f["vai"]["fieldtype"] == "Table MultiSelect" and f["vai"]["options"] == VU.CON and f["so_phut"]["read_only"]
     and d["field_order"] == [x["fieldname"] for x in d["fields"]])
kiem("SX Giat Vai: đủ ô theo giấy + ký + xem tháng",
     {"ngay", "viec", "vai", "so_luong", "ly_do", "gio_soi_lai", "gio_vot", "so_phut", "phoi_tai", "cat_luc", "nguoi_lam",
      "ghi_boi", "qc_ky_boi", "qc_ky_luc", "su_co", "xem_boi", "xem_luc", "xem_nhan_xet"} <= set(f))
d, f = meta("sx/qc/doctype/sx_vai_u/sx_vai_u.json")
kiem("SX Vai U: tên = mã vải, 3 trạng thái, không ai được xoá vì loại (QC chỉ đọc)",
     d["autoname"] == "field:ma" and f["trang_thai"]["options"].split("\n") == list(VU.TRANG_THAI)
     and next(p for p in d["permissions"] if p["role"] == "SX QC").get("write") is None)
d, f = meta("sx/qc/doctype/sx_giat_vai_ma/sx_giat_vai_ma.json")
kiem("SX Giat Vai Ma: bảng con, một ô Link SX Vai U", d.get("istable") == 1 and f["vai"]["options"] == VU.VAI)
d, f = meta("sx/qc/doctype/sx_qc_setting/sx_qc_setting.json")
kiem("SX QC Setting: ngày giặt cố định (thứ), nơi giặt, người giặt, giặt sau mỗi lần dùng — để trống được",
     f["vai_u_thu_giat"]["options"].split("\n")[1:] == list(VU.THU) and f["vai_u_giat_moi_lan"]["fieldtype"] == "Check"
     and not any(f[k].get("reqd") or f[k].get("default") for k in ("vai_u_thu_giat", "vai_u_noi_giat", "vai_u_nguoi_giat"))
     and all(k in d["field_order"] for k in ("vai_u_thu_giat", "vai_u_noi_giat", "vai_u_nguoi_giat", "vai_u_giat_moi_lan")))
for p in ("sx/qc/doctype/sx_vai_u", "sx/qc/doctype/sx_giat_vai", "sx/qc/doctype/sx_giat_vai_ma"):
    kiem(f"{p}: đủ __init__.py, .json, .py", all(os.path.exists(f"{p}/{x}") for x in
                                                ("__init__.py", f"{p.rsplit('/', 1)[1]}.json", f"{p.rsplit('/', 1)[1]}.py")))
qj = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
hj = open("sx/public/sx/views/qc_home.js", encoding="utf-8").read()
kiem("màn #/qc/vaiu có route, sáng tab Hôm nay; nút ở lưới cuối Hôm nay ngay sau nhật ký cát",
     "vaiu: '/assets/sx/sx/views/qc_vaiu.js'" in qj and re.search(r"SO_HOM_NAY = \[[^\]]*'vaiu'", qj)
     and hj.index("'#/qc/vaiu'") > hj.index("'#/qc/cat'") and hj.index("'#/qc/vaiu'") < hj.index("'#/qc/thietbi'"))
vj = open("sx/public/sx/views/qc_vaiu.js", encoding="utf-8").read()
kiem("màn gọi đúng các API", all(f"sx.api.qc_vaiu.{m}" in vj for m in
                                 ("tong_quan", "ghi", "ky", "xoa", "luu_vai", "xoa_vai", "xem_thang", "in_bm0805")))
rd = open("README.md", encoding="utf-8").read()
kiem("README có mục D163 — W29", "(D163 — W29)" in rd)
kiem("verify.sh chạy bài này", "test-vaiu.py" in open("scripts/verify.sh", encoding="utf-8").read())

F.ket_thuc("VAIU")
