"""D143 (W17) — thiết bị đo, hiệu chuẩn BM.06.01–06.04.

Vì sao phải có bài này:
  · Hạn kiểm tính sai (cộng tháng, cân theo giấy kiểm định) → thiết bị quá hạn mà app báo còn hạn.
  · Kiểm nội bộ cân bằng quả chuẩn mà kéo dài hạn kiểm định pháp lý → hồ sơ nói dối.
  · Sai số vượt cho phép / tiêu chí hỏng mà vẫn ghi Đạt → thiết bị hỏng tiếp tục đo.
  · Không đạt / quá hạn mà không ngừng dùng, không có phiếu sự cố → trái tài liệu.
  · Lịch chạy nền lập phiếu sự cố mỗi ngày cho cùng một thiết bị → sổ sự cố ngập.

Nạp sx/qc/thiet_bi.py, hai controller, sx/api/qc_thietbi.py, patch THẬT; frappe giả (fakefrappe).
Chạy: python3 scripts/test-thietbi.py   (verify.sh gọi sẵn)
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
T = sys.modules["sx.qc.thiet_bi"]
A = F.nap("sx.api.qc_thietbi", "sx/api/qc_thietbi.py")
TBC = F.nap("tb_ctl", "sx/qc/doctype/sx_thiet_bi_do/sx_thiet_bi_do.py")
KTC = F.nap("kt_ctl", "sx/qc/doctype/sx_kiem_thiet_bi/sx_kiem_thiet_bi.py")
F.dang_ky(T.TB, TBC.SXThietBiDo, ten_theo="ma")
F.dang_ky(T.KT, KTC.SXKiemThietBi)
P = F.nap("sx.patches.d143_thiet_bi", "sx/patches/d143_thiet_bi.py")
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")

# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- hạn kiểm, trạng thái, đánh giá phiếu (hàm thuần) --")
kiem("cộng tháng: 31/01 + 1 → 28/02 (29/02 năm nhuận); 15/10/2026 + 12 → 15/10/2027",
     T.cong_thang("2027-01-31", 1) == date(2027, 2, 28) and T.cong_thang("2028-01-31", 1) == date(2028, 2, 29)
     and T.cong_thang("2026-10-15", 12) == date(2027, 10, 15))
kiem("chu kỳ trống / 0 (ô Int trống trên Desk) → 12 tháng; 6 → 6",
     T.chu_ky({"loai": T.NAM_CHAM, "chu_ky_thang": 0}) == 12 and T.chu_ky({"loai": T.LUOI, "chu_ky_thang": 6}) == 6)
dh = {"loai": T.DONG_HO}
kiem("chưa kiểm lần nào → hạn đầu 31/10/2026", T.han_ke_tiep(dh, None) == date(2026, 10, 31))
kiem("đồng hồ nhiệt kiểm 15/01/2026 → hạn 15/01/2027 (1 lần / năm)",
     T.han_ke_tiep(dh, {"ngay": "2026-01-15"}) == date(2027, 1, 15))
kiem("có hạn ghi trên giấy hiệu chuẩn → lấy hạn giấy",
     T.han_ke_tiep(dh, {"ngay": "2026-01-15", "han_giay": "2026-07-01"}) == date(2026, 7, 1))
can = {"loai": T.CAN}
kiem("cân: kiểm nội bộ sau (không giấy) KHÔNG kéo dài hạn kiểm định gần nhất",
     T.han_ke_tiep(can, {"ngay": "2026-11-01"}, giay={"ngay": "2026-03-01", "han_giay": "2027-03-01"})
     == date(2027, 3, 1))
kiem("cân chưa có giấy nào → lần kiểm cuối + 12 tháng", T.han_ke_tiep(can, {"ngay": "2026-11-01"}) == date(2027, 11, 1))
kiem("trạng thái: hôm đúng hạn còn dùng; quá một ngày → ngừng quá hạn",
     T.trang_thai(dh, None, "2026-10-31")[0] == T.DANG_DUNG and T.trang_thai(dh, None, "2026-11-01")[0] == T.NGUNG_HAN)
kiem("lần kiểm gần nhất Không đạt → ngừng (dù còn hạn); thanh lý → Thanh lý",
     T.trang_thai(dh, {"ngay": "2026-10-01", "ket_qua": "Không đạt"}, "2026-10-09")[0] == T.NGUNG_HONG
     and T.trang_thai(dict(dh, thanh_ly=1), None, "2027-01-01")[0] == T.THANH_LY)
dg = T.danh_gia
kiem("đồng hồ nhiệt: không điểm nào → thiếu; nửa điểm → thiếu; chữ → phải nhập số",
     dg({"loai": T.DONG_HO})["thieu"] and "đủ cả" in dg({"loai": T.DONG_HO, "chuan_1": "100"})["thieu"][0]
     and "nhập số" in dg({"loai": T.DONG_HO, "chuan_1": "abc", "doc_1": "1"})["thieu"][0])
r = dg({"loai": T.DONG_HO, "chuan_1": "0", "doc_1": "0,5", "sai_so_cho_phep": 2})
kiem("điểm 0 °C (nước đá) là điểm đo thật; dấu phẩy thập phân đọc được", not r["thieu"] and r["sai_so"] == 0.5
     and not r["hong"], r)
r = dg({"loai": T.DONG_HO, "chuan_1": "0", "doc_1": "1", "chuan_2": "100", "doc_2": "103", "sai_so_cho_phep": 2})
kiem("sai số lớn nhất 3 °C > ± 2 → hỏng", r["sai_so"] == 3 and r["hong"], r)
kiem("nam châm: thiếu tiêu chí → thiếu; lực hút Không đạt → hỏng",
     len(dg({"loai": T.NAM_CHAM, "be_mat": "Đạt"})["thieu"]) == 1
     and dg({"loai": T.NAM_CHAM, "be_mat": "Đạt", "luc_hut": "Không đạt"})["hong"])
kiem("lưới sàng: đủ 3 tiêu chí Đạt → không thiếu, không hỏng",
     dg({"loai": T.LUOI, "nguyen_ven": "Đạt", "mat_luoi": "Đạt", "khung": "Đạt"}) == {"thieu": [], "hong": [], "sai_so": None})
kiem("cân kiểm định bên ngoài: phải có số giấy + hạn",
     len(dg({"loai": T.CAN, "hinh_thuc": "Kiểm định bên ngoài"})["thieu"]) == 2
     and not dg({"loai": T.CAN, "hinh_thuc": "Kiểm tra nội bộ"})["thieu"])
CC = [{"user": "a@x", "hinh_thuc": "Chứng chỉ", "han": "2027-01-01"},
      {"user": "b@x", "hinh_thuc": "Chứng chỉ", "han": "2026-01-01"}, {"user": "c@x", "hinh_thuc": "Đào tạo nội bộ"}]
kiem("chứng chỉ: còn hạn → có; hết hạn / chỉ đào tạo nội bộ → không",
     T.co_chung_chi(CC, "a@x", "2026-10-09") and not T.co_chung_chi(CC, "b@x", "2026-10-09")
     and not T.co_chung_chi(CC, "c@x", "2026-10-09"))

# ═══ 2. Danh mục, ghi kiểm ════════════════════════════════════════════════
print("\n-- danh mục, ghi kiểm, ngừng dùng, sự cố --")
P.execute()
P.execute()
kiem("patch: LS-01 cho máy rang M1 / M2 / M3 + rây RY-01, chạy lại không nhân đôi",
     sorted(F.bang(T.TB)) == ["LS-01-M1", "LS-01-M2", "LS-01-M3", "RY-01"] and F.bang(T.TB)["LS-01-M2"]["may"] == "M2")


def luu(**k):
    return A.luu_thiet_bi(json.dumps(k))


def ghi(**k):
    return A.ghi_kiem(json.dumps(k))


r = luu(ma=" dh-01 ", ten="Đồng hồ nhiệt máy rang M1", loai=T.DONG_HO, may="M1")
kiem("thêm thiết bị: mã chuẩn hoá DH-01, chưa kiểm → hạn 31/10/2026, đang dùng",
     r["name"] == "DH-01" and r["han"] == "2026-10-31" and r["trang_thai"] == T.DANG_DUNG, r)
kiem("trùng mã → chặn", "Đã có" in (thu(lambda: luu(ma="DH-01", ten="x", loai=T.DONG_HO)) or ""))
F.get_doc({"doctype": T.TB, "ma": " nc-09 ", "ten": "Nam châm phụ", "loai": T.NAM_CHAM}).insert()
kiem("Desk gõ \"nc-09\" → thiết bị TÊN NC-09 (chuẩn hoá trước khi đặt tên)", "NC-09" in F.bang(T.TB))
F.bang(T.TB).pop("NC-09")
kiem("không chọn loại → chặn", "loại" in (thu(lambda: luu(ma="X-1", ten="x")) or ""))
luu(ma="NC-01", ten="Nam châm vỡ đỗ", loai=T.NAM_CHAM, vi_tri="6 Vỡ đỗ")
q = A.tong_quan()
dh1 = next(x for x in q["ds"] if x["name"] == "DH-01")
kiem("tổng quan: chưa kiểm, còn 22 ngày tới hạn đầu", dh1["chua_kiem"] and dh1["con"] == 22 and dh1["bieu_mau"] == "BM.06.02")
r = ghi(thiet_bi="DH-01", chuan_1="100", doc_1="101", ket_qua="Đạt")
tb = F.bang(T.TB)["DH-01"]
kiem("ghi Đạt → thiết bị: lần kiểm, kết quả, hạn 09/10/2027, đang dùng; người kiểm tự điền",
     (str(tb["lan_kiem_cuoi"]), tb["ket_qua_cuoi"], str(tb["han_kiem"]), tb["trang_thai"])
     == ("2026-10-09", "Đạt", "2027-10-09", T.DANG_DUNG) and F.bang(T.KT)[r["name"]]["nguoi_kiem"] == "qc@x", tb)
F.BAO.clear()
r = ghi(thiet_bi="DH-01", chuan_1="100", doc_1="104", ket_qua="Đạt")
sc = F.bang("SX Su Co").get(r["su_co"] or "") or {}
kiem("sai số 4 °C mà ghi Đạt → ép Không đạt, báo; thiết bị ngừng; phiếu sự cố Thiết bị đo mức Cao",
     r["ket_qua"] == "Không đạt" and any("Không đạt" in b for b in F.BAO)
     and F.bang(T.TB)["DH-01"]["trang_thai"] == T.NGUNG_HONG and sc.get("nguon") == "Thiết bị đo"
     and sc.get("muc_do") == "Cao" and "DH-01" in sc.get("mo_ta", ""), (r, sc))
ghi(thiet_bi="DH-01", chuan_1="100", doc_1="100,5", ket_qua="Đạt")
kiem("kiểm lại Đạt (sau sửa / thay) → dùng lại; phiếu sự cố cũ vẫn còn",
     F.bang(T.TB)["DH-01"]["trang_thai"] == T.DANG_DUNG and len(F.bang("SX Su Co")) == 1)
kiem("nam châm thiếu tiêu chí → chặn, nói thiếu gì", "lực hút" in (thu(lambda: ghi(thiet_bi="NC-01", be_mat="Đạt",
                                                                                       ket_qua="Đạt")) or ""))
kiem("chưa chọn kết quả → chặn", "Chọn kết quả" in (thu(lambda: ghi(thiet_bi="NC-01", be_mat="Đạt",
                                                                    luc_hut="Đạt")) or ""))
kiem("ngày sau hôm nay → chặn", "sau hôm nay" in (thu(lambda: ghi(thiet_bi="NC-01", ngay="2026-10-10", be_mat="Đạt",
                                                                  luc_hut="Đạt", ket_qua="Đạt")) or ""))
luu(ma="CAN-01", ten="Cân bàn 60 kg", loai=T.CAN)
kiem("cân kiểm định ngoài thiếu hạn giấy → chặn", "hạn ghi trên giấy" in (thu(lambda: ghi(
    thiet_bi="CAN-01", hinh_thuc="Kiểm định bên ngoài", so_giay="KĐ-123", ket_qua="Đạt")) or ""))
ghi(thiet_bi="CAN-01", ngay="2026-03-01", hinh_thuc="Kiểm định bên ngoài", so_giay="KĐ-123",
    don_vi="TT Kỹ thuật 1", han_giay="2027-03-01", ket_qua="Đạt")
ghi(thiet_bi="CAN-01", ngay="2026-10-09", hinh_thuc="Kiểm tra nội bộ", ket_qua="Đạt", ghi_chu="quả chuẩn 20 kg")
kiem("cân: hạn = hạn giấy kiểm định 01/03/2027, lần kiểm nội bộ sau không đổi hạn",
     str(F.bang(T.TB)["CAN-01"]["han_kiem"]) == "2027-03-01")
r = ghi(thiet_bi="LS-01-M1", nguyen_ven="Đạt", mat_luoi="Không đạt", khung="Đạt", ket_qua="Đạt")
kiem("lưới sàng mắt lưới giãn → Không đạt, ngừng dùng, có phiếu sự cố",
     r["ket_qua"] == "Không đạt" and r["trang_thai"] == T.NGUNG_HONG and r["su_co"])
F.vai("SX QC", u="qc2@x")
kiem("QC khác không xoá phiếu của người khác", thu(lambda: A.xoa_kiem(r["name"])) is not None)
F.vai("SX QC")
luu(ma="LS-09", ten="Lưới sàng dự phòng", loai=T.LUOI)
cu = ghi(thiet_bi="LS-09", nguyen_ven="Đạt", mat_luoi="Đạt", khung="Đạt", ket_qua="Đạt")["name"]
F.bang(T.KT)[cu]["creation"] = "2026-10-01 08:00:00"
kiem("người ghi không xoá được phiếu ghi từ hôm trước (chỉ Ban ISO)", "Ban ISO" in (thu(lambda: A.xoa_kiem(cu)) or ""))
F.vai("SX QC")
A.xoa_kiem(r["name"])
kiem("người ghi xoá phiếu ghi nhầm trong ngày → trạng thái tính lại (về chưa kiểm, đang dùng)",
     F.bang(T.TB)["LS-01-M1"]["trang_thai"] == T.DANG_DUNG and not F.bang(T.TB)["LS-01-M1"]["lan_kiem_cuoi"])
F.vai("ISO Manager")
kiem("Ban ISO ghi kiểm được", thu(lambda: ghi(thiet_bi="NC-01", be_mat="Đạt", luc_hut="Đạt", ket_qua="Đạt")) is None)
F.vai("Stock User")
kiem("người ngoài QC không xem được", thu(A.tong_quan) is not None)
F.vai("SX QC")

# ═══ 3. Chứng chỉ người kiểm (chờ quyết định) ══════════════════════════════
print("\n-- người kiểm đồng hồ nhiệt (W17 f — chờ quyết định) --")
kiem("chưa chọn (trống) → không chặn", thu(lambda: ghi(thiet_bi="DH-01", chuan_1="0", doc_1="0",
                                                        ket_qua="Đạt")) is None)
F.CAI_DAT.update(chung_chi_dong_ho="Giữ chứng chỉ", nguoi_kiem_dong_ho=[])
loi = thu(lambda: ghi(thiet_bi="DH-01", chuan_1="0", doc_1="0", ket_qua="Đạt"))
kiem("Giữ chứng chỉ: QC chưa có chứng chỉ tự kiểm đồng hồ nhiệt → chặn", loi and "chứng chỉ" in loi, loi)
kiem("… hiệu chuẩn bên ngoài thì không chặn", thu(lambda: ghi(thiet_bi="DH-01", hinh_thuc="Hiệu chuẩn bên ngoài",
                                                              chuan_1="0", doc_1="0", ket_qua="Đạt")) is None)
kiem("… nam châm (không phải đồng hồ nhiệt) không chặn", thu(lambda: ghi(thiet_bi="NC-01", be_mat="Đạt",
                                                                         luc_hut="Đạt", ket_qua="Đạt")) is None)
F.CAI_DAT["nguoi_kiem_dong_ho"] = [{"user": "qc@x", "hinh_thuc": "Chứng chỉ", "han": "2027-06-30"}]
kiem("… có chứng chỉ còn hạn → ghi được", thu(lambda: ghi(thiet_bi="DH-01", chuan_1="0", doc_1="0",
                                                          ket_qua="Đạt")) is None)
F.CAI_DAT.clear()

# ═══ 4. Quá hạn: lịch chạy nền, nhắc ═══════════════════════════════════════
print("\n-- quá hạn: lịch chạy nền, hộp nhắc --")
d = T.nhac(F.hom_nay())
kiem("nhắc: chưa kiểm LS-01-M1..3 / RY-01 sắp đến hạn đầu; danh mục đủ 4 loại → không báo thiếu",
     {x["ma"] for x in d["sap_den"]} >= {"LS-01-M1", "LS-01-M2", "LS-01-M3", "RY-01"} and not d["thieu_loai"]
     and not d["qua_han"], d)
ds = [x for x in NH.tinh(F.hom_nay(), [], [], {}, thiet_bi=d) if x["route"] == "#/qc/thietbi"]
kiem("hộp nhắc: sắp đến hạn mức thường", len(ds) == 1 and ds[0]["muc_do"] == "thuong" and "30 ngày" in ds[0]["tieu_de"], ds)
F.dat_ngay("2026-11-02")
n_sc = len(F.bang("SX Su Co"))
sc = T.quet_qua_han()
moi = F.bang("SX Su Co").get(sc or "") or {}
kiem("qua 31/10: lịch chạy nền đặt NGỪNG — QUÁ HẠN cho thiết bị chưa kiểm, MỘT phiếu sự cố gộp",
     len(F.bang("SX Su Co")) == n_sc + 1 and all(F.bang(T.TB)[m]["trang_thai"] == T.NGUNG_HAN
                                                 for m in ("LS-01-M1", "LS-01-M2", "LS-01-M3", "RY-01"))
     and "4 thiết bị" in moi.get("mo_ta", "") and F.bang(T.TB)["DH-01"]["trang_thai"] == T.DANG_DUNG, moi.get("mo_ta"))
kiem("chạy lại ngày sau → KHÔNG lập phiếu thứ hai cho cùng hạn", T.quet_qua_han() is None
     and len(F.bang("SX Su Co")) == n_sc + 1)
d = T.nhac(F.hom_nay())
ds = [x for x in NH.tinh(F.hom_nay(), [], [], {}, thiet_bi=d) if x["route"] == "#/qc/thietbi"]
kiem("hộp nhắc: quá hạn mức CAO, kể mã", any(x["muc_do"] == "cao" and "quá hạn" in x["tieu_de"]
                                             and "LS-01-M1" in x["chi_tiet"] for x in ds), ds)
ghi(thiet_bi="LS-01-M1", nguyen_ven="Đạt", mat_luoi="Đạt", khung="Đạt", ket_qua="Đạt")
kiem("kiểm Đạt → hết quá hạn, dùng lại", F.bang(T.TB)["LS-01-M1"]["trang_thai"] == T.DANG_DUNG)
F.dat_ngay("2027-11-03")
T.quet_qua_han()
kiem("lần quá hạn MỚI (hạn khác) → phiếu mới", "LS-01-M1" in max(F.bang("SX Su Co").values(),
                                                               key=lambda x: x["name"]).get("mo_ta", ""))
F.dat_ngay("2026-10-09")
luu(ma="TL-01", ten="Đồng hồ cũ", loai=T.DONG_HO, thanh_ly=1)
kiem("thiết bị thanh lý không vào nhắc", "TL-01" not in json.dumps(T.nhac("2027-01-01")))
kiem("sx.api.qc.nhac truyền thiết bị đo vào hộp nhắc", "_thiet_bi.nhac(d)" in open("sx/api/qc.py", encoding="utf-8").read())

# ═══ 5. Bản in, cấu hình, màn hình ═════════════════════════════════════════
print("\n-- BM.06.01–06.04, cấu hình, màn hình --")
if F.jinja2:
    def chu(h):
        return re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", h.split("</style>")[1]))

    h = chu(A.in_bieu_mau("BM.06.01"))
    kiem("BM.06.01: danh mục đủ thiết bị, chu kỳ, hạn, trạng thái, chỗ ký",
         "BM.06.01" in h and "DH-01" in h and "CAN-01" in h and "theo giấy KĐ" in h and "Trưởng Ban ISO" in h, h[:300])
    h = chu(A.in_bieu_mau("BM.06.02", 2026))
    kiem("BM.06.02: các lần kiểm đồng hồ nhiệt năm 2026, điểm đo, sai số / cho phép",
         "BM.06.02" in h and "100 / 104" in h and "Không đạt" in h and "± 2" in h, h[:300])
    kiem("BM.06.03 / 06.04 dựng được", "Nam châm" in A.in_bieu_mau("BM.06.03", 2026)
         and "Lưới" in A.in_bieu_mau("BM.06.04", 2026))
st = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_qc_setting/sx_qc_setting.json", encoding="utf-8"))["fields"]}
kiem("SX QC Setting: hạn kiểm lần đầu 31/10/2026; người kiểm đồng hồ nhiệt mặc định Đào tạo nội bộ (chốt 09/10), "
     "vẫn chọn được Giữ chứng chỉ",
     st["thiet_bi_han_dau"].get("default") == "2026-10-31" and st["chung_chi_dong_ho"].get("default") == "Đào tạo nội bộ"
     and "Giữ chứng chỉ" in st["chung_chi_dong_ho"]["options"])
PC = F.nap("sx.patches.d152_chung_chi_dong_ho", "sx/patches/d152_chung_chi_dong_ho.py")
F.CAI_DAT.pop("chung_chi_dong_ho", None)
PC.execute()
kiem("patch D152: site chưa chọn → đặt Đào tạo nội bộ", F.CAI_DAT.get("chung_chi_dong_ho") == "Đào tạo nội bộ")
F.CAI_DAT["chung_chi_dong_ho"] = "Giữ chứng chỉ"
PC.execute()
kiem("patch D152: đã chọn Giữ chứng chỉ → để nguyên", F.CAI_DAT["chung_chi_dong_ho"] == "Giữ chứng chỉ"
     and "sx.patches.d152_chung_chi_dong_ho" in open("sx/patches.txt", encoding="utf-8").read())
F.CAI_DAT["chung_chi_dong_ho"] = "Đào tạo nội bộ"
hk = open("sx/hooks.py", encoding="utf-8").read()
kiem("lịch chạy nền hằng ngày quét thiết bị quá hạn", '"daily": ["sx.qc.thiet_bi.quet_qua_han"]' in hk)
kiem("patch có trong patches.txt", "sx.patches.d143_thiet_bi" in open("sx/patches.txt", encoding="utf-8").read())
kiem("route #/qc/thietbi + nút ở Hôm nay", "thietbi: '/assets/sx/sx/views/qc_thietbi.js'" in open(
    "sx/public/sx/views/qc.js", encoding="utf-8").read() and "#/qc/thietbi" in open(
    "sx/public/sx/views/qc_home.js", encoding="utf-8").read())
js = open("sx/public/sx/views/qc_thietbi.js", encoding="utf-8").read()
kiem("màn thiết bị: ghi kiểm theo loại, lịch sử + xoá, thêm / sửa, in 4 biểu mẫu",
     all(x in js for x in ("sx.api.qc_thietbi.ghi_kiem", "sx.api.qc_thietbi.lich_su", "sx.api.qc_thietbi.xoa_kiem",
                           "sx.api.qc_thietbi.luu_thiet_bi", "'BM.06.04'")))

F.ket_thuc("THIETBI")
