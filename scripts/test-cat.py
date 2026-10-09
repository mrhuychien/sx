"""D141 (W20, W12) + D164 (W32) — nhật ký cát rang BM.08.03 mỗi việc một dòng, xem xét tháng theo ngày sản xuất.

Vì sao phải có bài này:
  · Số ngày cát đã dùng là con số app TỰ ĐẾM (ngày có rang kể từ lần thay toàn bộ) — bổ sung mà tính lại ngày,
    loại rồi mà vẫn đếm, ghi bù lượt kiểm mà không cộng thì sổ nói sai mà không ai thấy.
  · Dòng sổ cũ (mỗi ngày một dòng, trước D164) mất mốc → cát đang dùng bỗng "0 ngày".
  · Nhập cát của NCC khác mà không nhắc kiểm kim loại nặng / lưu lọ mẫu → mất đúng cái tài liệu đòi.
  · Kim loại nặng Không đạt mà không thành phiếu sự cố → lô đã rang bằng cát đó không ai xem.
  · Dòng Ban ISO đã ký mà QC vẫn sửa được → chữ ký xem xét vô nghĩa.
  · Tỷ lệ hoàn tất lượt chia cho MỌI ngày lịch (Chủ nhật, ngày chưa tới) → tháng nào cũng "thiếu"; dòng nhập /
    vệ sinh cát rơi vào ngày nghỉ mà bị tính là ngày sản xuất → "thiếu lượt" oan.

Nạp sx/qc/cat.py, controller SX Nhat Ky Cat, sx/api/qc_cat.py, sx/api/qc.py, sx/qc/nhac.py, patch d164 THẬT;
frappe giả (fakefrappe). Chạy: python3 scripts/test-cat.py   (verify.sh gọi sẵn)
"""

import json
import os
import re
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

frappe = F.cai()
Q = F.nap_qc()
CAT = sys.modules["sx.qc.cat"]
NH = sys.modules["sx.qc.nhac"]
A = F.nap("sx.api.qc_cat", "sx/api/qc_cat.py")
CTL = F.nap("cat_ctl", "sx/qc/doctype/sx_nhat_ky_cat/sx_nhat_ky_cat.py")
F.dang_ky(CAT.PT, CTL.SXNhatKyCat)
P = F.nap("sx.patches.d164_cat_theo_viec", "sx/patches/d164_cat_theo_viec.py")
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")
SO = F.bang(CAT.PT)
LUOT = F.bang("SX QC Round")
NHAP, RANG_KHO, BO_SUNG, LOAI, VE_SINH = CAT.NHAP, CAT.RANG_KHO, CAT.BO_SUNG, CAT.LOAI, CAT.VE_SINH

F.bang("Supplier").update({
    "CAT-A": {"name": "CAT-A", "supplier_name": "Cát sông Lô", "custom_loai_ncc": "Cát rang",
              "custom_ncc_duyet": 1, "disabled": 0},
    "CAT-B": {"name": "CAT-B", "supplier_name": "Cát Minh Anh", "custom_loai_ncc": "Cát rang",
              "custom_ncc_duyet": 1, "disabled": 0},
    "DX-1": {"name": "DX-1", "supplier_name": "NCC đỗ", "custom_loai_ncc": "Nguyên liệu thực phẩm",
             "custom_ncc_duyet": 1, "disabled": 0}})
F.bang("SX QC Cong Doan")["3 Rang"] = {"name": "3 Rang"}


def ghi(**k):
    return A.ghi(json.dumps(k))


def loi(f):
    return thu(f) or ""


def luot(ngay, ten="Đầu sáng", ds=1, **k):
    n = f"QC-{ngay}-{ten}"
    LUOT[n] = dict({"name": n, "ngay": ngay, "luot": ten, "docstatus": ds, "ghi_muon": 0, "nhap_lai_tu_giay": 0,
                    "reviewed_on": None, "rang_nhiet_do": 0}, **k)


def d(viec, ngay, **k):
    return dict({"name": f"{viec}-{ngay}", "ngay": ngay, "viec": viec, "creation": f"{ngay} 09:00:00"}, **k)


# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- đếm số ngày cát đã dùng (hàm thuần) --")
dn = CAT.dem_ngay
R = {"2026-09-30", "2026-10-01", "2026-10-02", "2026-10-05"}
kiem("sổ trống → không có cát đang dùng (None)", dn([], R, "2026-10-05") is None)
moc = [d(RANG_KHO, "2026-10-01")]
kiem("đưa dùng 01/10: đếm NGÀY CÓ RANG từ hôm đó (tính cả hôm đó), ngày rang trước mốc không tính",
     (dn(moc, R, "2026-10-05"), dn(moc, R, "2026-10-01"), dn(moc, R, "2026-09-30")) == (3, 1, None))
kiem("ngày có rang dạng date cũng đếm", dn(moc, {date(2026, 10, 1), date(2026, 10, 2)}, "2026-10-02") == 2)
kiem("bổ sung KHÔNG tính lại ngày", dn(moc + [d(BO_SUNG, "2026-10-02")], R, "2026-10-05") == 3)
lo = moc + [d(LOAI, "2026-10-06")]
kiem("loại 06/10 → từ hôm đó không có cát đang dùng; trước đó vẫn đếm",
     (dn(lo, R, "2026-10-06"), dn(lo, R, "2026-10-05")) == (None, 3))
moi = lo + [d(RANG_KHO, "2026-10-07")]
kiem("đưa cát mới 07/10 → đếm lại từ 07/10", dn(moi, R | {"2026-10-07", "2026-10-08"}, "2026-10-08") == 2)
cung = moc + [d(RANG_KHO, "2026-10-07", creation="2026-10-07 08:00:00"),
              d(LOAI, "2026-10-07", creation="2026-10-07 10:00:00")]
kiem("cùng ngày: ghi đưa dùng TRƯỚC rồi mới ghi loại (cát cũ) → vẫn hiểu là loại cũ rồi đưa mới",
     dn(cung, {"2026-10-07"}, "2026-10-07") == 1)
kiem("dòng đưa dùng đầu sổ khai cát đã dùng 5 ngày trước đó → 5 + ngày có rang từ mốc",
     dn([d(RANG_KHO, "2026-10-01", so_ngay_dau=5)], R, "2026-10-05") == 8)
cu = [d("", "2026-10-01", so_cu=1, so_ngay_dung=5), d("", "2026-10-02", so_cu=1, so_ngay_dung=6)]
kiem("dòng sổ cũ: đếm tiếp từ số ngày của dòng cũ cuối cùng (ngày cũ không đếm hai lần)",
     dn(cu, R | {"2026-10-06"}, "2026-10-06") == 8)
cu2 = cu + [d(RANG_KHO, "2026-10-03", so_cu=1, so_ngay_dung=1, thay_cat=1), d("", "2026-10-04", so_cu=1, so_ngay_dung=2)]
kiem("dòng cũ thay cát (đã thành Rang khô đưa dùng) là mốc; đếm tiếp sau dòng cũ cuối",
     dn(cu2, R, "2026-10-05") == 3)
kiem("đưa dùng mới sau sổ cũ → bỏ hẳn chuỗi cũ", dn(cu2 + [d(RANG_KHO, "2026-10-06")], {"2026-10-06"}, "2026-10-06") == 1)
kiem("thứ tự trong ngày: nhập → vệ sinh → loại → đưa dùng → bổ sung",
     [x["viec"] for x in sorted([d(BO_SUNG, "2026-10-01"), d(RANG_KHO, "2026-10-01"), d(LOAI, "2026-10-01"),
                                 d(VE_SINH, "2026-10-01"), d(NHAP, "2026-10-01")], key=CAT.xep)]
     == [NHAP, VE_SINH, LOAI, RANG_KHO, BO_SUNG])

print("\n-- đổi nguồn, nguồn đang dùng (hàm thuần) --")
dong = [d(NHAP, "2026-09-01", ncc_cat="A"), d(NHAP, "2026-09-05", ncc_cat="A"), d(NHAP, "2026-09-10", ncc_cat="B"),
        d("", "2026-09-12", so_cu=1, ncc_cat="C"), d(NHAP, "2026-09-15", ncc_cat="C"), d(NHAP, "2026-09-20", ncc_cat="A"),
        d(RANG_KHO, "2026-09-21", ncc_cat="B")]
kiem("nhập lần đầu không phải đổi nguồn; NCC khác lần nhập trước → đổi; dòng sổ cũ cũng là 'lần trước'; dòng đưa "
     "dùng không tính", CAT.doi_nguon(dong) == {f"{NHAP}-2026-09-01": 0, f"{NHAP}-2026-09-05": 0,
                                                 f"{NHAP}-2026-09-10": 1, f"{NHAP}-2026-09-15": 0,
                                                 f"{NHAP}-2026-09-20": 1}, CAT.doi_nguon(dong))
kiem("nguồn đang dùng = nguồn của dòng nhập / đưa dùng / bổ sung / sổ cũ mới nhất có nguồn",
     CAT.nguon_dang_dung(dong, "2026-09-25")[0] == "B" and CAT.nguon_dang_dung(dong, "2026-09-13")[0] == "C"
     and CAT.nguon_dang_dung([d(VE_SINH, "2026-09-01", ncc_cat="X")], "2026-09-02") == ("", ""))
CK = CAT.cho_kln([{"doi_nguon": 1, "kln": "", "luu_lo_mau": 1}, {"doi_nguon": 1, "kln": "Đạt", "luu_lo_mau": 0},
                  {"doi_nguon": 1, "kln": "Đạt", "luu_lo_mau": 1}, {"doi_nguon": 1, "kln": "Không đạt"},
                  {"doi_nguon": 0, "kln": ""}])
kiem("đổi nguồn còn treo: chưa có KLN Đạt HOẶC chưa lọ mẫu; Không đạt đã thành sự cố → không treo",
     len(CK) == 2, CK)

print("\n-- ngày có rang (lượt kiểm) --")
luot("2026-10-01", rang_nhiet_do=260)
luot("2026-10-02", rang_nhiet_do=0, rang_nhiet_do_m2=255)
luot("2026-10-03", rang_nhiet_do=0)
luot("2026-10-04", ds=2, rang_nhiet_do=260)
luot("2026-10-05", ds=0, rang_nhiet_do=250)
kiem("ngày có rang = lượt ghi nhiệt độ rang ở máy nào đó (cả máy 2, 3; cả lượt đang dở); bỏ lượt huỷ, lượt không rang",
     CAT.ngay_rang("2026-10-01", "2026-10-09") == {"2026-10-01", "2026-10-02", "2026-10-05"},
     CAT.ngay_rang("2026-10-01", "2026-10-09"))

# ═══ 2. Ghi sổ theo việc ════════════════════════════════════════════════════
print("\n-- ghi theo việc: luật từng việc --")
F.vai("SX QC")
kiem("nhập cát thiếu nguồn → chặn", "chọn nguồn cát" in loi(lambda: ghi(ngay="2026-09-28", viec=NHAP, khoi_luong=500)))
kiem("nhập cát thiếu khối lượng → chặn", "khối lượng" in loi(lambda: ghi(ngay="2026-09-28", viec=NHAP, ncc_cat="CAT-A")))
kiem("dòng mới không chọn việc → chặn", "Chọn việc" in loi(lambda: ghi(ngay="2026-09-28", ncc_cat="CAT-A")))
r = ghi(ngay="2026-09-28", viec=NHAP, ncc_cat="CAT-A", khoi_luong=500, so_bm0703=" PN-0012 ", cam_quan="Đạt",
        nguoi_lam=" Anh Tâm ")
n_nhap = r["name"]
x = SO[n_nhap]
kiem("nhập cát: nguồn, số BM.07.03, kg, cảm quan, người làm, QC ghi; lần nhập đầu không phải đổi nguồn",
     x["ten_ncc"] == "Cát sông Lô" and x["so_bm0703"] == "PN-0012" and x["khoi_luong"] == 500 and x["nguoi_ghi"] == "qc@x"
     and x["nguoi_lam"] == "Anh Tâm" and not r["doi_nguon"] and not x["thay_cat"], x)
kiem("bổ sung khi máy chưa có cát đang dùng → chặn, chỉ sang 'Rang khô đưa dùng'",
     "Rang khô đưa dùng" in loi(lambda: ghi(ngay="2026-09-30", viec=BO_SUNG, khoi_luong=10)))
kiem("loại khi chưa có cát đang dùng → chặn", "chưa có cát đang dùng" in loi(
    lambda: ghi(ngay="2026-09-30", viec=LOAI, ly_do_loai="x")))
r = ghi(ngay="2026-10-01", viec=RANG_KHO, khoi_luong=120, thung="T1 · 30/09", so_ngay_dau=3)
n_moc = r["name"]
x = SO[n_moc]
kiem("đưa dùng đầu sổ: khai 3 ngày trước đó; đánh dấu thay toàn bộ; nguồn bỏ trống = nguồn lần nhập gần nhất",
     x["thay_cat"] == 1 and x["so_ngay_dau"] == 3 and x["ncc_cat"] == "CAT-A" and x["ten_ncc"] == "Cát sông Lô"
     and x["thung"] == "T1 · 30/09" and r["so_ngay"] == 3 + 3, (x, r))
ghi(name=n_moc, ngay="2026-10-01", viec=RANG_KHO, khoi_luong=120, thung="T1 · 30/09 (sửa)")
kiem("sửa dòng đưa dùng đầu sổ mà không gửi số ngày đầu → giữ số đã khai (3)", SO[n_moc]["so_ngay_dau"] == 3
     and SO[n_moc]["thung"] == "T1 · 30/09 (sửa)")
kiem("đưa dùng sau đó mà khai số ngày trước → chặn (chỉ dòng đầu sổ)",
     "ĐẦU SỔ" in loi(lambda: ghi(ngay="2026-10-03", viec=RANG_KHO, khoi_luong=100, so_ngay_dau=2)))
r = ghi(ngay="2026-10-05", viec=BO_SUNG, khoi_luong=20)
kiem("bổ sung 05/10: số ngày đã dùng = 3 khai + ngày có rang 01, 02, 05/10 = 6 (ghi vào dòng)",
     r["so_ngay_dung"] == 6 and SO[r["name"]]["so_ngay_dung"] == 6, r)
n_bs = r["name"]
luot("2026-10-06", rang_nhiet_do=262)
kiem("cát đang dùng hôm nay: 7 ngày (thêm 06/10), nguồn Cát sông Lô, thay toàn bộ 01/10",
     A.tong_quan()["hien_tai"] == {"so_ngay": 7, "ncc": "CAT-A", "ten_ncc": "Cát sông Lô", "ngay_thay": "2026-10-01",
                                   "ngay_loai": None, "dau_so": False}, A.tong_quan()["hien_tai"])
luot("2026-10-03", ten="Trưa", rang_nhiet_do=258)
kiem("ghi bù lượt kiểm có rang 03/10 → số ngày tự cộng (8)", A.tong_quan()["hien_tai"]["so_ngay"] == 8)
kiem("loại thiếu lý do → chặn", "lý do" in loi(lambda: ghi(ngay="2026-10-07", viec=LOAI)))
kiem("khối lượng âm → chặn", "âm" in loi(lambda: ghi(ngay="2026-10-07", viec=LOAI, ly_do_loai="x", khoi_luong=-1)))
r = ghi(ngay="2026-10-07", viec=LOAI, ly_do_loai="Đủ số ngày; Màu sẫm đen", khoi_luong=130)
n_loai = r["name"]
h = A.tong_quan()["hien_tai"]
kiem("loại 07/10: ghi số ngày đã dùng (8); sau đó không có cát đang dùng, biết ngày loại",
     r["so_ngay_dung"] == 8 and h["so_ngay"] is None and h["ngay_loai"] == "2026-10-07", (r, h))
kiem("bổ sung sau khi loại → chặn", "chưa có cát đang dùng" in loi(lambda: ghi(ngay="2026-10-08", viec=BO_SUNG,
                                                                             khoi_luong=5)))
F.BAO.clear()
r = ghi(ngay="2026-10-08", viec=RANG_KHO, khoi_luong=125, thung="T2 · 07/10")
luot("2026-10-08", rang_nhiet_do=255)
kiem("đưa cát mới 08/10 sau khi đã loại → không cảnh báo; đếm lại từ 08/10",
     not [b for b in F.BAO if "Loại cát" in b] and A.tong_quan()["hien_tai"]["so_ngay"] == 1)
r = ghi(ngay="2026-10-09", viec=RANG_KHO, khoi_luong=100)
kiem("đưa cát mới khi cát cũ còn trong máy mà chưa ghi Loại cát → nhắc ghi dòng loại (không chặn)",
     any("chưa có dòng Loại cát" in b for b in F.BAO), F.BAO)
F.vai("ISO Manager")
F.delete_doc(CAT.PT, r["name"])
F.vai("SX QC")
dd = frappe.get_doc({"doctype": CAT.PT, "ngay": "2026-10-08", "viec": BO_SUNG, "khoi_luong": 5, "so_ngay_dau": 9,
                     "doi_nguon": 1})
dd.insert()
kiem("Desk: bổ sung mang số ngày đầu sổ / dấu đổi nguồn → app bỏ (chỉ đưa dùng / nhập mới có)",
     not SO[dd.name]["so_ngay_dau"] and not SO[dd.name]["doi_nguon"] and SO[dd.name]["so_ngay_dung"] == 1)
F.vai("ISO Manager")
F.delete_doc(CAT.PT, dd.name)
F.vai("SX QC")
kiem("vệ sinh không đánh dấu thùng / khay → chặn", "thùng hay khay" in loi(lambda: ghi(ngay="2026-10-08", viec=VE_SINH)))
r = ghi(ngay="2026-10-04", viec=VE_SINH, ve_sinh_thung=1, thung="T1")
kiem("vệ sinh thùng: không cần khối lượng; không ghi số ngày", SO[r["name"]]["ve_sinh_thung"] == 1
     and not SO[r["name"]]["so_ngay_dung"] and not SO[r["name"]]["khoi_luong"])
kiem("ngày sau hôm nay → chặn", "sau hôm nay" in loi(lambda: ghi(ngay="2026-10-10", viec=VE_SINH, ve_sinh_khay=1)))
kiem("số ngày khai âm → chặn", "âm" in loi(lambda: ghi(ngay="2026-10-08", viec=RANG_KHO, khoi_luong=1, so_ngay_dau=-1)))
F.BAO.clear()
ghi(ngay="2026-10-02", viec=NHAP, ncc_cat="DX-1", khoi_luong=10)
kiem("nguồn không phải NCC loại Cát rang → báo (không chặn — W09)", any("Cát rang" in b for b in F.BAO), F.BAO)
F.vai("ISO Manager")
F.delete_doc(CAT.PT, next(n for n, x in SO.items() if x.get("ncc_cat") == "DX-1"))
kiem("Ban ISO không ghi nhật ký (người xem xét không tự ghi)",
     loi(lambda: ghi(ngay="2026-10-08", viec=VE_SINH, ve_sinh_khay=1)) != "")

# ═══ 3. Đổi nguồn: kim loại nặng, lọ mẫu, sự cố ════════════════════════════
print("\n-- đổi nguồn: nhập NCC khác, kim loại nặng, lọ mẫu, sự cố --")
F.vai("SX QC")
r = ghi(ngay="2026-10-08", viec=NHAP, ncc_cat="CAT-B", khoi_luong=400)
n_b = r["name"]
kiem("nhập cát NCC khác lần nhập trước → đổi nguồn", r["doi_nguon"] == 1 and SO[n_b]["doi_nguon"] == 1)
F.BAO.clear()
r = ghi(ngay="2026-10-09", viec=BO_SUNG, khoi_luong=10, ncc_cat="CAT-B")
kiem("bổ sung cát nguồn mới khi chưa có kim loại nặng Đạt → báo 'kiểm trước khi dùng' (không chặn)",
     any("kiểm trước khi dùng" in b for b in F.BAO), F.BAO)
F.vai("ISO Manager")
F.delete_doc(CAT.PT, r["name"])
F.vai("SX QC")
r = ghi(ngay="2026-10-03", viec=NHAP, ncc_cat="CAT-B", khoi_luong=50)
n_b0 = r["name"]
kiem("nhập bù một lần CAT-B ngày 03/10 → nó là đổi nguồn; lần nhập CAT-B 08/10 hết là đổi nguồn (tính lại)",
     SO[n_b0]["doi_nguon"] == 1 and SO[n_b]["doi_nguon"] == 0)
A.xoa(n_b0)
kiem("xoá dòng nhập bù → 08/10 lại là đổi nguồn", SO[n_b]["doi_nguon"] == 1)
q = A.tong_quan()
kiem("tổng quan: đổi nguồn 08/10 còn treo; nguồn nhập gần nhất; danh sách nguồn chỉ NCC Cát rang; QC ghi được",
     [x["name"] for x in q["cho_kln"]] == [n_b] and q["nguon_nhap"] == "CAT-B"
     and sorted(x["name"] for x in q["ncc"]) == ["CAT-A", "CAT-B"] and q["duoc_ghi"] and not q["la_iso"]
     and q["viec"] == list(CAT.VIEC), q["cho_kln"])
kiem("ghi kết quả vào dòng KHÔNG đổi nguồn → chặn",
     "không phải lần đổi nguồn" in loi(lambda: A.cap_nhat_kln(n_nhap, json.dumps({"kln": "Đạt"}))))
A.cap_nhat_kln(n_b, json.dumps({"kln": "Đã gửi mẫu"}))
m = [x for x in NH.tinh(F.hom_nay(), [], [], {}, cat=CAT.nhac(F.hom_nay())) if x["route"] == "#/qc/cat"]
kiem("đã gửi mẫu, chưa lọ mẫu → nhắc mức thường, nói rõ thiếu gì",
     len(m) == 1 and m[0]["muc_do"] == "thuong" and "chờ kết quả kim loại nặng" in m[0]["tieu_de"]
     and "chưa lưu lọ mẫu" in m[0]["tieu_de"] and "nhập ngày 08/10" in m[0]["chi_tiet"], m)
A.cap_nhat_kln(n_b, json.dumps({"kln": "", "luu_lo_mau": 1}))
m = [x for x in NH.tinh(F.hom_nay(), [], [], {}, cat=CAT.nhac(F.hom_nay())) if x["route"] == "#/qc/cat"]
kiem("chưa gửi mẫu kim loại nặng → mức CAO", len(m) == 1 and m[0]["muc_do"] == "cao", m)
F.vai("ISO Manager")
r = A.cap_nhat_kln(n_b, json.dumps({"kln": "Không đạt", "so_phieu_kln": "KN-77"}))
sc = F.bang("SX Su Co").get(r["su_co"] or "") or {}
kiem("Ban ISO ghi kết quả được; Không đạt → phiếu sự cố Nhật ký cát, mức Cao, công đoạn 3 Rang, nói nguồn + phiếu",
     sc.get("nguon") == "Nhật ký cát" and sc.get("muc_do") == "Cao" and sc.get("cong_doan") == "3 Rang"
     and "Cát Minh Anh" in sc.get("mo_ta", "") and "KN-77" in sc.get("mo_ta", ""), sc)
A.cap_nhat_kln(n_b, json.dumps({"kln": "Không đạt", "so_phieu_kln": "KN-77b"}))
kiem("lưu lại lần nữa → KHÔNG lập phiếu thứ hai", len(F.bang("SX Su Co")) == 1)
kiem("Không đạt rồi thì hết treo (đã thành sự cố)", not CAT.nhac(F.hom_nay())["cho_kln"])
A.cap_nhat_kln(n_b, json.dumps({"kln": "Đạt", "luu_lo_mau": 1}))
F.vai("SX QC")
F.BAO.clear()
r = ghi(ngay="2026-10-09", viec=BO_SUNG, khoi_luong=10, ncc_cat="CAT-B")
kiem("kim loại nặng Đạt rồi → bổ sung cát nguồn đó không báo nữa", not [b for b in F.BAO if "kiểm trước khi dùng" in b],
     F.BAO)
F.vai("ISO Manager")
F.delete_doc(CAT.PT, r["name"])
F.vai("SX QC")
r = ghi(ngay="2026-10-03", viec=NHAP, ncc_cat="CAT-B", khoi_luong=50)
dd = frappe.get_doc(CAT.PT, r["name"])
dd.ngay = "2026-10-09"
dd.save()
kiem("dời ngày một lần nhập CAT-B từ 03/10 sang 09/10 → tính lại từ ngày CŨ: 08/10 lại là đổi nguồn, 09/10 thì không",
     SO[n_b]["doi_nguon"] == 1 and SO[r["name"]]["doi_nguon"] == 0)
r2 = ghi(ngay="2026-10-09", viec=NHAP, ncc_cat="CAT-A", khoi_luong=30)
r3 = ghi(ngay="2026-10-09", viec=NHAP, ncc_cat="CAT-B", khoi_luong=30)
kiem("nhập CAT-A sau CAT-B → đổi nguồn; rồi CAT-B sau CAT-A → đổi nguồn",
     SO[r2["name"]]["doi_nguon"] == 1 and SO[r3["name"]]["doi_nguon"] == 1)
ghi(name=r2["name"], ngay="2026-10-09", viec=BO_SUNG, khoi_luong=30, ncc_cat="CAT-A")
kiem("sửa dòng nhập CAT-A thành bổ sung → hết dấu đổi nguồn, không còn treo kim loại nặng; lần nhập CAT-B sau nó "
     "tính lại (lần nhập trước giờ cũng là CAT-B → hết đổi nguồn)",
     SO[r2["name"]]["doi_nguon"] == 0 and r2["name"] not in [x["name"] for x in A.tong_quan()["cho_kln"]]
     and SO[r3["name"]]["doi_nguon"] == 0)
F.vai("ISO Manager")
for n in (r["name"], r2["name"], r3["name"]):
    F.delete_doc(CAT.PT, n)
F.vai("SX QC")

# ═══ 4. Nhắc ═════════════════════════════════════════════════════════════
print("\n-- nhắc: tối đa (C19), có rang mà không có cát đang dùng --")


def nhac_cat(ngay=None):
    return [x for x in NH.tinh(F.hom_nay(), [], [], {}, cat=CAT.nhac(ngay or F.hom_nay())) if x["route"] == "#/qc/cat"]


kiem("C19 chưa chốt (tối đa = 0) → chỉ đếm, KHÔNG nhắc số ngày", not [x for x in nhac_cat() if "tối đa" in x["tieu_de"]])
F.CAI_DAT["cat_so_ngay_toi_da"] = 1
m = [x for x in nhac_cat() if "tối đa" in x["tieu_de"]]
kiem("điền tối đa (khi C19 chốt) → tới ngưỡng thì nhắc thay cát", len(m) == 1 and "1 ngày" in m[0]["tieu_de"], m)
kiem("không có cát đang dùng → không nhắc tối đa dù số liệu lệch",
     not NH._nhac_cat({"dang_dung": False, "so_ngay": 9, "toi_da": 5}))
kiem("không còn nhắc kiểu cũ 'ngày có rang chưa ghi nhật ký'",
     not [x for x in nhac_cat() if "chưa ghi nhật ký" in x["tieu_de"] or x["tieu_de"].startswith("Hôm nay có rang")])
SO[n_loai]["ngay"] = "2026-10-08"
SO[n_loai]["creation"] = "2026-10-08 23:00:00"
F.vai("ISO Manager")
F.delete_doc(CAT.PT, next(n for n, x in SO.items() if x["viec"] == RANG_KHO and str(x["ngay"]) == "2026-10-08"))
F.vai("SX QC")
c = CAT.nhac(F.hom_nay())
m = nhac_cat()
kiem("đã loại 08/10 mà chưa ghi cát mới: không nhắc tối đa; có rang 08/10 → nhắc 'có rang mà không có cát đang dùng'",
     not c["dang_dung"] and c["rang_khong_cat"] == "2026-10-08" and not [x for x in m if "tối đa" in x["tieu_de"]]
     and any(x["tieu_de"] == "Có rang mà nhật ký cát không có cát đang dùng" and "08/10" in x["chi_tiet"] for x in m), m)
F.CAI_DAT["cat_so_ngay_toi_da"] = 0
ghi(ngay="2026-10-08", viec=RANG_KHO, khoi_luong=120)
kiem("ghi đưa dùng 08/10 → hết nhắc; thẻ cát đang dùng không còn nói 'đã loại' (loại cùng ngày, trước lần đưa dùng)",
     not CAT.nhac(F.hom_nay())["rang_khong_cat"] and A.tong_quan()["hien_tai"]["ngay_loai"] is None
     and A.tong_quan()["hien_tai"]["so_ngay"] == 1)
kiem("nhắc 'có rang mà không có cát' chỉ soi 7 ngày (rang 01/10 khi sổ chưa có cát không nhắc ngày 15/10)",
     CAT.nhac("2026-10-15")["rang_khong_cat"] is None)
# Sổ khác (bảng tạm): loại 20/09, rang 25/09 không có cát (quá 7 ngày), đưa dùng lại 05/10.
luu_so, luu_luot = dict(SO), dict(LUOT)
SO.clear()
LUOT.clear()
SO.update({"X1": d(RANG_KHO, "2026-09-15"), "X2": d(LOAI, "2026-09-20", ly_do_loai="x"), "X3": d(RANG_KHO, "2026-10-05")})
luot("2026-09-25", rang_nhiet_do=260)
luot("2026-10-06", rang_nhiet_do=260)
kiem("có rang mà không có cát nhưng đã quá 7 ngày (25/09) → không nhắc nữa (chỗ của nó là Xem xét tháng)",
     CAT.nhac("2026-10-09")["rang_khong_cat"] is None and CAT.nhac("2026-09-27")["rang_khong_cat"] == "2026-09-25")
SO.clear()
SO.update(luu_so)
LUOT.clear()
LUOT.update(luu_luot)
goc = frappe.get_all
frappe.get_all = lambda *a, **k: 1 / 0
kiem("chưa migrate (lỗi đọc) → {} — hộp nhắc không chết", CAT.nhac(F.hom_nay()) == {})
frappe.get_all = goc
qcpy = open("sx/api/qc.py", encoding="utf-8").read()
kiem("sx.api.qc lấy số liệu nhắc cát từ cat.nhac(d) (cát tự đọc ngày có rang)", '"cat": _cat.nhac(d)' in qcpy)
kiem("hộp nhắc QC có mảng cát", "cat" in Q._du_lieu_nhac(F.hom_nay()))

# ═══ 5. Sổ cũ: patch D164 ══════════════════════════════════════════════════
print("\n-- dòng sổ cũ (mỗi ngày một dòng) — patch D164 --")
CU = {
    "CU-1": {"name": "CU-1", "ngay": "2026-09-20", "ncc_cat": "CAT-A", "so_ngay_dung": 9, "thay_cat": 0,
             "ve_sinh_thung": 0, "ve_sinh_khay": 0, "creation": "2026-09-20 09:00:00"},
    "CU-2": {"name": "CU-2", "ngay": "2026-09-21", "ncc_cat": "CAT-A", "so_ngay_dung": 1, "thay_cat": 1,
             "ve_sinh_thung": 1, "ve_sinh_khay": 1, "creation": "2026-09-21 09:00:00"},
    "CU-3": {"name": "CU-3", "ngay": "2026-09-22", "ncc_cat": "CAT-A", "so_ngay_dung": 2, "thay_cat": 0,
             "ve_sinh_thung": 0, "ve_sinh_khay": 1, "creation": "2026-09-22 09:00:00", "xem_luc": "2026-09-30 10:00:00"}}
SO.update({k: dict(v) for k, v in CU.items()})
P.execute()
kiem("thay cát → Rang khô đưa dùng; vệ sinh → Vệ sinh thùng, khay; còn lại để trống; tất cả đánh dấu sổ cũ; số liệu giữ",
     [(SO[k]["viec"], SO[k]["so_cu"], SO[k]["so_ngay_dung"]) for k in ("CU-1", "CU-2", "CU-3")]
     == [("", 1, 9), (RANG_KHO, 1, 1), (VE_SINH, 1, 2)] and SO["CU-3"]["xem_luc"])
kiem("dòng mới không bị đụng", all(not x.get("so_cu") for k, x in SO.items() if not k.startswith("CU-")))
SO["CU-1"]["viec"] = "sửa tay"
P.execute()
kiem("chạy lại vô hại", SO["CU-1"]["viec"] == "sửa tay")
SO["CU-1"]["viec"] = ""
kiem("đếm qua dòng cũ: tới 22/09 cát ngày thứ 2", CAT.so_ngay("2026-09-22") == 2)
kiem("chỉ có dòng sổ cũ (20/09) → không phải 'đầu sổ' (không cho khai số ngày đầu nữa); sổ trống → đầu sổ",
     A.hien_tai("2026-09-20")["dau_so"] is False and A.hien_tai("2026-09-19")["dau_so"] is True
     and A.hien_tai("2026-09-20")["so_ngay"] == 9)
kiem("dòng sổ cũ không sửa qua màn (giữ nguyên)", "sổ cũ" in loi(lambda: ghi(name="CU-1", ngay="2026-09-20", viec=VE_SINH,
                                                                           ve_sinh_thung=1)))
SO["CU-4"] = {"name": "CU-4", "ngay": "2026-09-23", "ncc_cat": "CAT-B", "so_ngay_dung": 1, "thay_cat": 1, "doi_nguon": 1,
              "so_cu": 1, "viec": RANG_KHO, "creation": "2026-09-23 09:00:00"}
kiem("dòng sổ cũ đổi nguồn: vẫn ghi được kết quả kim loại nặng (không vướng luật dòng mới)",
     thu(lambda: A.cap_nhat_kln("CU-4", json.dumps({"kln": "Đạt", "luu_lo_mau": 1}))) is None and SO["CU-4"]["kln"] == "Đạt")
SO.pop("CU-4")
kiem("đã có dòng sổ cũ trước đó (21/09: chỉ có sổ cũ 20/09, chưa có lần đưa dùng) → không khai số ngày đầu sổ nữa",
     "ĐẦU SỔ" in loi(lambda: ghi(ngay="2026-09-21", viec=RANG_KHO, khoi_luong=10, so_ngay_dau=2)))
r = ghi(ngay="2026-09-24", viec=NHAP, ncc_cat="CAT-B", khoi_luong=20)
kiem("nhập NCC khác nguồn của dòng sổ cũ trước đó → đổi nguồn (cả số trả về màn)",
     SO[r["name"]]["doi_nguon"] == 1 and r["doi_nguon"] == 1, r)
F.vai("ISO Manager")
F.delete_doc(CAT.PT, r["name"])
F.vai("SX QC")

# ═══ 6. Xoá, khoá sau xem xét; Ban ISO xem xét tháng (W12) ══════════════════
print("\n-- xoá, xem xét tháng: ngày sản xuất, nhật ký cát, chữ ký --")
F.vai("SX QC", u="qc2@x")
kiem("QC khác không xoá được dòng người khác", "Chỉ người ghi" in loi(lambda: A.xoa(n_bs)))
F.vai("SX QC")
SO[n_bs]["creation"] = "2026-10-05 08:00:00"
kiem("người ghi không xoá được dòng ghi từ hôm trước (chỉ Ban ISO)", "Ban ISO" in loi(lambda: A.xoa(n_bs)))
for ng in ("2026-10-01", "2026-10-05"):
    for t in ("Trưa", "Cuối chiều"):
        luot(ng, t)
F.bang("SX Ngay San Xuat").update({
    f"SXN-{ng}": {"name": f"SXN-{ng}", "ngay": ng, "docstatus": dst}
    for ng, dst in (("2026-10-02", 0), ("2026-10-04", 2), ("2026-10-10", 0))})
F.vai("ISO Manager")
db = Q.dashboard("2026-09-20", "2026-10-31")
kiem("ngày sản xuất = phiếu ngày SX (bỏ phiếu huỷ) ∪ có lượt (cả dở, bỏ huỷ) ∪ dòng cát SỔ CŨ — dòng cát mới (nhập, "
     "vệ sinh, loại…) không làm ra ngày sản xuất",
     db["ngay_sx"] == ["2026-09-20", "2026-09-21", "2026-09-22", "2026-10-01", "2026-10-02", "2026-10-03",
                       "2026-10-05", "2026-10-06", "2026-10-08"], db["ngay_sx"])
kiem("theo ngày: dòng cát thay toàn bộ → 'thay', dòng khác → 'co'",
     db["theo_ngay"]["2026-10-01"].get("cat") == "thay" and db["theo_ngay"]["2026-09-28"].get("cat") == "co",
     {k: v for k, v in db["theo_ngay"].items() if "cat" in v})
cs = Q.dashboard("2026-10-01", "2026-10-31")["cat"]
kiem("tóm tắt tháng: số dòng theo việc, cuối kỳ cát đã dùng mấy ngày, đổi nguồn + KLN + lọ mẫu, chưa xem",
     (cs["so_dong"], cs["so_nhap"], cs["so_lan_thay"], cs["so_bo_sung"], cs["so_loai"], cs["so_ve_sinh"])
     == (6, 1, 2, 1, 1, 1) and cs["so_ngay_cuoi"] == 1 and cs["chua_xem"] == 6 and cs["so_cu"] == 0
     and cs["doi_nguon"] == [{"ngay": "2026-10-08", "ncc": "Cát Minh Anh", "kln": "Đạt", "lo_mau": 1}], cs)
c9 = Q.dashboard("2026-09-01", "2026-09-30")["cat"]
kiem("tháng có dòng sổ cũ: đếm sổ cũ riêng; việc của dòng sổ cũ không đếm vào việc mới (trừ thay toàn bộ)",
     (c9["so_dong"], c9["so_cu"], c9["so_lan_thay"], c9["so_ve_sinh"], c9["so_nhap"]) == (4, 3, 1, 0, 1), c9)
luot("2026-10-20", rang_nhiet_do=255)
kiem("cuối kỳ tính tới hôm nay (lượt ghi nhầm ngày tương lai không cộng)",
     Q.dashboard("2026-10-01", "2026-10-31")["cat"]["so_ngay_cuoi"] == 1)
LUOT.pop("QC-2026-10-20-Đầu sáng")
kq = Q.review_rounds("2026-10-01", "2026-10-31")
kiem("MỘT chữ ký xem xét: cả lượt lẫn nhật ký cát", kq["so_cat"] == 6 and all(
    x.get("xem_boi") == "iso@x" for x in SO.values() if str(x["ngay"]) >= "2026-10-01"), kq)
kiem("ký lần hai → không còn gì", Q.review_rounds("2026-10-01", "2026-10-31")["so_cat"] == 0
     and Q.dashboard("2026-10-01", "2026-10-31")["cat"]["chua_xem"] == 0)
F.vai("SX QC")
kiem("dòng đã ký: QC không sửa được", "Ban ISO đã xem xét" in loi(
    lambda: ghi(name=n_bs, ngay="2026-10-05", viec=BO_SUNG, khoi_luong=25)))
kiem("… nhưng kết quả kim loại nặng / lọ mẫu vẫn ghi được (kết quả về muộn)",
     thu(lambda: A.cap_nhat_kln(n_b, json.dumps({"so_phieu_kln": "KN-78"}))) is None)
kiem("… và QC không xoá được", "Ban ISO" in loi(lambda: F.delete_doc(CAT.PT, n_bs)))
F.vai("ISO Manager")
dd = frappe.get_doc(CAT.PT, n_bs)
dd.khoi_luong = 25
kiem("Ban ISO sửa được dòng đã ký", thu(dd.save) is None and SO[n_bs]["khoi_luong"] == 25)

# ═══ 7. Bản in, doctype, giao diện ════════════════════════════════════════
print("\n-- BM.08.03, doctype, màn hình --")
F.vai("SX QC")
h = re.sub(r"\s+", " ", A.in_bm0803("2026-10"))
kiem("BM.08.03: tháng, mã, lần BH 01; đúng 7 cột giấy theo thứ tự",
     "Nhật ký cát rang — tháng 10/2026" in h and "Lần BH 01" in h
     and re.findall(r"<th[^>]*>(.*?)</th>", h.split('class="doi"')[0]) == [
         "Ngày", "Việc", "Nguồn, số BM.07.03", "Khối lượng (kg)", "Thùng số / nhãn ngày",
         "Số ngày đã dùng; lý do loại", "Người làm / QC ký"], re.findall(r"<th[^>]*>(.*?)</th>", h)[:7])
kiem("dòng nhập: nguồn + đổi nguồn + kg; dòng loại: số ngày + lý do; dòng đưa dùng: thay toàn bộ; người làm / QC",
     "Cát Minh Anh <b>(ĐỔI NGUỒN)</b>" in h and ">400<" in h and "8 ngày; Đủ số ngày; Màu sẫm đen" in h
     and "thay toàn bộ (đã dùng 3 ngày trước đó)" in h and "qc@x" in h, h[h.find("<table>"):][:900])
kiem("bảng đổi nguồn: KLN, số phiếu, lọ mẫu; dòng Trưởng Ban ISO xem xét cuối tháng",
     "KN-78" in h and "Đã lưu" in h and "Trưởng Ban ISO xem xét cuối tháng:</b> iso@x" in h.replace("&nbsp;", ""))
h9 = re.sub(r"\s+", " ", A.in_bm0803("2026-09"))
kiem("tháng có dòng sổ cũ: in kèm, ghi 'sổ cũ', số ngày của dòng cũ", "(sổ cũ)" in h9 and "Ngày có rang" in h9
     and "9 ngày" in h9)
dj = json.load(open("sx/qc/doctype/sx_nhat_ky_cat/sx_nhat_ky_cat.json", encoding="utf-8"))
fl = {f["fieldname"]: f for f in dj["fields"]}
kiem("doctype: việc 5 lựa chọn (trống cho sổ cũ); số ngày / đổi nguồn / thay / sổ cũ / người ghi / xem xét chỉ đọc",
     fl["viec"]["options"].split("\n") == [""] + list(CAT.VIEC)
     and all(fl[f].get("read_only") for f in ("so_ngay_dung", "doi_nguon", "thay_cat", "so_cu", "nguoi_ghi", "xem_boi",
                                              "xem_luc", "su_co"))
     and {"khoi_luong", "thung", "so_bm0703", "ly_do_loai", "nguoi_lam", "so_ngay_dau"} <= set(fl)
     and dj["field_order"] == [f["fieldname"] for f in dj["fields"]] and "Không đạt" in fl["kln"]["options"])
st = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_qc_setting/sx_qc_setting.json",
                                                encoding="utf-8"))["fields"]}
kiem("SX QC Setting: cát dùng tối đa — mặc định 0 (C19 chưa chốt: chỉ đếm)", st["cat_so_ngay_toi_da"].get("default") == "0")
kiem("patch có trong patches.txt", "sx.patches.d164_cat_theo_viec" in open("sx/patches.txt", encoding="utf-8").read())
qcjs = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
kiem("route #/qc/cat; nút ở Hôm nay", "cat: '/assets/sx/sx/views/qc_cat.js'" in qcjs
     and "#/qc/cat" in open("sx/public/sx/views/qc_home.js", encoding="utf-8").read())
cj = open("sx/public/sx/views/qc_cat.js", encoding="utf-8").read()
kiem("màn nhật ký cát: ghi theo việc, khai số ngày đầu sổ, ghi kết quả KLN, xoá, in BM.08.03",
     all(x in cj for x in ("sx.api.qc_cat.ghi", "so_ngay_dau", "sx.api.qc_cat.cap_nhat_kln", "sx.api.qc_cat.xoa",
                           "sx.api.qc_cat.in_bm0803", "ĐỔI NGUỒN CÁT", "dl.viec.forEach")))
rj = open("sx/public/sx/views/qc_review.js", encoding="utf-8").read()
kiem("màn Xem xét: tô đỏ ngày sản xuất thiếu lượt, cột Cát, mục nhật ký cát theo việc + in BM.08.03, chữ ký gồm cả cát",
     all(x in rj for x in ("kpi.ngay_sx", "sx-qc-o-loi", "<th>Cát</th>", "sx.api.qc_cat.in_bm0803", "kq.so_cat",
                           "ngày sản xuất", "cat.so_dong", "cat.so_ngay_cuoi")))

F.ket_thuc("CAT")
