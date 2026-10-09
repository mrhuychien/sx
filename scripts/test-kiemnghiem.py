"""D144 (W18) — kế hoạch kiểm nghiệm KH.KN.01.

Vì sao phải có bài này:
  · Hạn "1 lần / năm" tính từ lần gửi gần nhất — tính sai là sản phẩm quá hạn mà app báo Đạt.
  · Sản phẩm chưa gửi lần nào phải hiện hạn đầu 31/10/2026, không phải "không có hạn".
  · Kết quả Không đạt mà không thành phiếu sự cố → lô đó không ai xem lại.
  · Mẫu cát gắn lần đổi nguồn: kết quả phải chép sang nhật ký cát, và chỉ MỘT phiếu sự cố.

Nạp sx/qc/kiem_nghiem.py, controller SX Kiem Nghiem + SX Nhat Ky Cat, sx/api/qc_kiemnghiem.py THẬT;
frappe giả (fakefrappe). Chạy: python3 scripts/test-kiemnghiem.py   (verify.sh gọi sẵn)
"""

import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

F.cai()
Q = F.nap_qc()
NH = sys.modules["sx.qc.nhac"]
KN = sys.modules["sx.qc.kiem_nghiem"]
CATM = sys.modules["sx.qc.cat"]
A = F.nap("sx.api.qc_kiemnghiem", "sx/api/qc_kiemnghiem.py")
KNC = F.nap("kn_ctl", "sx/qc/doctype/sx_kiem_nghiem/sx_kiem_nghiem.py")
CC = F.nap("cat_ctl", "sx/qc/doctype/sx_nhat_ky_cat/sx_nhat_ky_cat.py")
F.dang_ky(KN.PT, KNC.SXKiemNghiem)
F.dang_ky(CATM.PT, CC.SXNhatKyCat)
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")

F.bang(KN.SP).update({
    "SPCB-001": {"name": "SPCB-001", "so_cong_bo": "01/2023", "ten_san_pham": "Bánh đậu xanh sen", "loai": "Bánh",
                 "tccs": "TCCS 01", "ngung_san_xuat": 0},
    "SPCB-009": {"name": "SPCB-009", "so_cong_bo": "09/2021", "ten_san_pham": "Bột đậu xanh dinh dưỡng", "loai": "Bột",
                 "ngung_san_xuat": 0},
    "SPCB-010": {"name": "SPCB-010", "so_cong_bo": "10/2021", "ten_san_pham": "Chè đậu đen cốt dừa", "loai": "Chè",
                 "ngung_san_xuat": 0},
    "SPCB-099": {"name": "SPCB-099", "so_cong_bo": "99/2020", "ten_san_pham": "Sản phẩm ngừng", "ngung_san_xuat": 1}})
F.bang("Supplier").update({
    "CAT-A": {"name": "CAT-A", "supplier_name": "Cát sông Lô", "custom_loai_ncc": "Cát rang", "custom_ncc_duyet": 1},
    "CAT-B": {"name": "CAT-B", "supplier_name": "Cát Minh Anh", "custom_loai_ncc": "Cát rang", "custom_ncc_duyet": 1}})

# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- một dòng kế hoạch (hàm thuần) --")
sp = {"name": "SPCB-001", "ten_san_pham": "Bánh", "so_cong_bo": "01/2023"}
d = KN.dong_ke_hoach(sp, [], "2026-10-09")
kiem("chưa gửi lần nào → hạn đầu 31/10/2026, còn 22 ngày → Đến hạn", (d["han"], d["con"], d["trang_thai"])
     == ("2026-10-31", 22, KN.DEN_HAN), d)
d = KN.dong_ke_hoach(sp, [{"name": "a", "ngay_gui": "2025-12-01", "ket_qua": "Đạt"}], "2026-10-09")
kiem("gửi 01/12/2025 Đạt → lần sau 01/12/2026, còn 53 ngày → Đạt", (d["han"], d["trang_thai"]) == ("2026-12-01", KN.DAT_TT), d)
d = KN.dong_ke_hoach(sp, [{"name": "a", "ngay_gui": "2025-10-01", "ket_qua": "Đạt"}], "2026-10-09")
kiem("gửi 01/10/2025 → quá hạn từ 02/10/2026", d["trang_thai"] == KN.QUA_HAN and d["con"] == -8, d)
kiem("… đúng ngày 01/10/2026 chưa quá hạn (còn 0 ngày → Đến hạn)", KN.dong_ke_hoach(
    sp, [{"name": "a", "ngay_gui": "2025-10-01", "ket_qua": "Đạt"}], "2026-10-01")["trang_thai"] == KN.DEN_HAN)
d = KN.dong_ke_hoach(sp, [{"name": "a", "ngay_gui": "2026-03-01", "ket_qua": "Đạt"},
                          {"name": "b", "ngay_gui": "2026-09-10", "ket_qua": ""}], "2026-10-09")
kiem("lần gửi gần nhất chưa có kết quả → Chờ kết quả, đếm số ngày chờ; trong năm có 2 lần",
     d["trang_thai"] == KN.CHO_KQ and d["cho_ngay"] == 29 and d["trong_nam"] == ["2026-03-01", "2026-09-10"]
     and d["han"] == "2027-09-10", d)
d = KN.dong_ke_hoach(sp, [{"name": "b", "ngay_gui": "2026-09-10", "ket_qua": "Không đạt"},
                          {"name": "a", "ngay_gui": "2026-03-01", "ket_qua": "Đạt"}], "2026-10-09")
kiem("lần gần nhất Không đạt (dù thứ tự lộn) → Không đạt — kiểm lại", d["trang_thai"] == KN.HONG and d["phieu_cuoi"] == "b", d)

# ═══ 2. Gửi mẫu, kết quả, sự cố ═══════════════════════════════════════════
print("\n-- gửi mẫu, kết quả, sự cố --")
q = A.tong_quan()
kiem("kế hoạch: 3 sản phẩm còn sản xuất (bỏ sản phẩm ngừng), chưa gửi → hạn 31/10/2026",
     [x["so_cong_bo"] for x in q["ke_hoach"]] == ["01/2023", "09/2021", "10/2021"]
     and all(x["han"] == "2026-10-31" for x in q["ke_hoach"]), [x["so_cong_bo"] for x in q["ke_hoach"]])


def gui(**k):
    return A.gui_mau(json.dumps(k))


kiem("mẫu sản phẩm phải chọn sản phẩm", "Chọn sản phẩm" in (thu(lambda: gui(doi_tuong="Sản phẩm")) or ""))
kiem("ngày gửi sau hôm nay → chặn", "sau hôm nay" in (thu(lambda: gui(doi_tuong="Sản phẩm", san_pham="SPCB-001",
                                                                      ngay_gui="2026-10-10")) or ""))
r = gui(doi_tuong="Sản phẩm", san_pham="SPCB-001", ngay_gui="2026-10-05", mo_ta_mau="HSD 05/07/2027",
        phong_kn="Viện Pasteur", chi_tieu="Vi sinh, kim loại nặng")
p1 = F.bang(KN.PT)[r["name"]]
kiem("gửi mẫu: lần sau = gửi + 12 tháng, người ghi tự điền", r["lan_sau"] == "2027-10-05" and p1["nguoi_ghi"] == "qc@x", r)
kiem("… kế hoạch: sản phẩm chuyển Chờ kết quả", next(x for x in A.tong_quan()["ke_hoach"]
                                                     if x["san_pham"] == "SPCB-001")["trang_thai"] == KN.CHO_KQ)
kiem("ngày kết quả trước ngày gửi → chặn", "trước ngày gửi" in (thu(lambda: A.ghi_ket_qua(
    r["name"], json.dumps({"ket_qua": "Đạt", "ngay_kq": "2026-10-01"}))) or ""))
A.ghi_ket_qua(r["name"], json.dumps({"ket_qua": "Đạt", "so_phieu": "KQ-1001"}))
p1 = F.bang(KN.PT)[r["name"]]
kiem("ghi Đạt không ghi ngày → ngày kết quả = hôm nay; kế hoạch Đạt, lần sau 05/10/2027",
     str(p1["ngay_kq"]) == "2026-10-09" and next(x for x in A.tong_quan()["ke_hoach"] if x["san_pham"] == "SPCB-001")
     ["trang_thai"] == KN.DAT_TT)
r2 = gui(doi_tuong="Sản phẩm", san_pham="SPCB-009", ngay_gui="2026-10-08")
A.ghi_ket_qua(r2["name"], json.dumps({"ket_qua": "Không đạt", "so_phieu": "KQ-2002"}))
sc = F.bang("SX Su Co").get(F.bang(KN.PT)[r2["name"]]["su_co"] or "") or {}
kiem("Không đạt → phiếu sự cố Kết quả kiểm nghiệm, mức Cao, nói sản phẩm + số phiếu",
     sc.get("nguon") == "Kết quả kiểm nghiệm" and sc.get("muc_do") == "Cao" and "Bột đậu xanh" in sc.get("mo_ta", "")
     and "KQ-2002" in sc.get("mo_ta", ""), sc)
A.ghi_ket_qua(r2["name"], json.dumps({"ket_qua": "Không đạt", "ghi_chu": "đã báo QLSX"}))
kiem("lưu lại → không lập phiếu thứ hai", len(F.bang("SX Su Co")) == 1)
kiem("… kế hoạch: Không đạt — kiểm lại", next(x for x in A.tong_quan()["ke_hoach"]
                                             if x["san_pham"] == "SPCB-009")["trang_thai"] == KN.HONG)

# ═══ 3. Cát: chỉ khi đổi nguồn, chép sang nhật ký cát ══════════════════════
print("\n-- cát rang: đổi nguồn, chép kết quả sang nhật ký cát --")
for ngay, ncc, so in (("2026-10-01", "CAT-A", 5), ("2026-10-07", "CAT-B", 0)):
    F.get_doc({"doctype": CATM.PT, "ngay": ngay, "ncc_cat": ncc, "so_ngay_dung": so}).insert()
dong = next(n for n, x in F.bang(CATM.PT).items() if str(x["ngay"]) == "2026-10-07")
c = KN.cat_cho_kiem()
kiem("kế hoạch cát: chỉ lần đổi nguồn 07/10 (Cát Minh Anh), chưa gửi mẫu", [x["name"] for x in c] == [dong]
     and not c[0]["phieu"], c)
r3 = gui(doi_tuong="Cát rang", nhat_ky_cat=dong, chi_tieu="Kim loại nặng")
kiem("gửi mẫu cát → nhật ký cát ghi 'Đã gửi mẫu'", F.bang(CATM.PT)[dong]["kln"] == "Đã gửi mẫu"
     and KN.cat_cho_kiem()[0]["phieu"] == r3["name"])
kiem("gửi lần hai cho cùng lần đổi nguồn → chặn", "đã có phiếu" in (thu(lambda: gui(doi_tuong="Cát rang",
                                                                                   nhat_ky_cat=dong)) or ""))
n_sc = len(F.bang("SX Su Co"))
A.ghi_ket_qua(r3["name"], json.dumps({"ket_qua": "Không đạt", "so_phieu": "KL-77"}))
moi = [x for x in F.bang("SX Su Co").values()][n_sc:]
kiem("kết quả cát Không đạt → nhật ký cát Không đạt + số phiếu; ĐÚNG MỘT phiếu sự cố (do nhật ký cát lập)",
     F.bang(CATM.PT)[dong]["kln"] == "Không đạt" and F.bang(CATM.PT)[dong]["so_phieu_kln"] == "KL-77"
     and len(moi) == 1 and moi[0]["nguon"] == "Nhật ký cát" and F.bang(KN.PT)[r3["name"]]["su_co"] == moi[0]["name"],
     moi)
kiem("phiếu cát không có 'lần sau' (chỉ kiểm khi đổi nguồn)", not F.bang(KN.PT)[r3["name"]].get("lan_sau"))

# ═══ 4. Nhắc, quyền ═══════════════════════════════════════════════════════
print("\n-- hộp nhắc, quyền --")
n = KN.nhac(F.hom_nay())
kiem("nhắc: chè 10/2021 chưa gửi → đến hạn 31/10; bột Không đạt → kiểm lại",
     [x["so_cong_bo"] for x in n["den_han"]] == ["10/2021"] and [x["so_cong_bo"] for x in n["khong_dat"]] == ["09/2021"], n)
m = [x for x in NH.tinh(F.hom_nay(), [], [], {}, kiem_nghiem=n) if x["route"] == "#/qc/kiemnghiem"]
kiem("hộp nhắc: Không đạt mức CAO, đến hạn mức thường", sorted(x["muc_do"] for x in m) == ["cao", "thuong"], m)
F.dat_ngay("2026-11-05")
n = KN.nhac(F.hom_nay())
kiem("qua 31/10 chưa gửi → quá hạn (cao)", [x["so_cong_bo"] for x in n["qua_han"]] == ["10/2021"]
     and any(x["muc_do"] == "cao" and "quá hạn" in x["tieu_de"] for x in NH.tinh(F.hom_nay(), [], [], {}, kiem_nghiem=n)))
gui(doi_tuong="Sản phẩm", san_pham="SPCB-010", ngay_gui="2026-10-01")
F.dat_ngay("2026-10-25")
n = KN.nhac(F.hom_nay())
kiem("gửi mẫu 24 ngày chưa có kết quả → nhắc hỏi phòng kiểm nghiệm", [x["so_cong_bo"] for x in n["cho_lau"]] == ["10/2021"], n)
F.dat_ngay("2026-10-09")
kiem("sx.api.qc.nhac truyền kế hoạch kiểm nghiệm vào hộp nhắc", "_kiem_nghiem.nhac(d)" in open(
    "sx/api/qc.py", encoding="utf-8").read())
F.vai("Stock User")
kiem("người ngoài QC không xem được", thu(A.tong_quan) is not None)
F.vai("ISO Manager")
kiem("Ban ISO ghi được phiếu gửi mẫu", thu(lambda: gui(doi_tuong="Nước", mo_ta_mau="nước giếng")) is None)
F.vai("SX QC", u="qc2@x")
kiem("QC khác không xoá phiếu của người khác", thu(lambda: A.xoa(r2["name"])) is not None)
F.vai("SX QC")
F.bang(KN.PT)[r2["name"]]["creation"] = "2026-10-01 08:00:00"
kiem("người ghi không xoá được phiếu ghi từ hôm trước", "Ban ISO" in (thu(lambda: A.xoa(r2["name"])) or ""))

# ═══ 5. Bản in, cấu hình, màn hình ═════════════════════════════════════════
print("\n-- KH.KN.01, cấu hình, màn hình --")
if F.jinja2:
    h = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", A.in_kh_kn01(2026).split("</style>")[1]))
    kiem("KH.KN.01: từng sản phẩm (số công bố, TCCS, tháng dự kiến, ngày gửi, kết quả), mục cát, mẫu khác, chỗ ký",
         "KH.KN.01" in h and "01/2023" in h and "TCCS 01" in h and "10/2027" in h and "05/10 (KQ-1001)" in h
         and "Cát rang — chỉ kiểm khi đổi nguồn" in h and "nước giếng" in h and "Trưởng Ban ISO" in h, h[:400])
st = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_qc_setting/sx_qc_setting.json", encoding="utf-8"))["fields"]}
kiem("SX QC Setting: hạn gửi mẫu lần đầu 31/10/2026", st["kn_han_dau"].get("default") == "2026-10-31")
kiem("route #/qc/kiemnghiem + nút ở Hôm nay", "kiemnghiem: '/assets/sx/sx/views/qc_kiemnghiem.js'" in open(
    "sx/public/sx/views/qc.js", encoding="utf-8").read() and "#/qc/kiemnghiem" in open(
    "sx/public/sx/views/qc_home.js", encoding="utf-8").read())
js = open("sx/public/sx/views/qc_kiemnghiem.js", encoding="utf-8").read()
kiem("màn kiểm nghiệm: gửi mẫu (sản phẩm / cát / khác), ghi kết quả, xoá, in KH.KN.01",
     all(x in js for x in ("sx.api.qc_kiemnghiem.gui_mau", "sx.api.qc_kiemnghiem.ghi_ket_qua", "sx.api.qc_kiemnghiem.xoa",
                           "sx.api.qc_kiemnghiem.in_kh_kn01", "GỬI MẪU CÁT")))

F.ket_thuc("KIEMNGHIEM")
