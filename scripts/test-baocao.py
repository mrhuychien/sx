"""D151 (W25) — báo cáo tháng ATTP, chỉ tiêu ATTP (số liệu cho mục tiêu ATTP, họp xem xét của lãnh đạo).

Vì sao phải có bài này:
  · Tỷ lệ lũy kế năm lấy trung bình các tháng → tháng ít ngày sản xuất kéo lệch cả năm.
  · Tháng không có sự cố hiện "—" thay vì 0 → người đọc tưởng thiếu số liệu.
  · Lượt bổ sung / phiếu diễn tập lọt vào số liệu → chỉ số đẹp hơn thực tế.
  · Chỉ tiêu ≤ / ≥ so ngược → Không đạt thành Đạt.
  · Một loại hồ sơ chưa migrate làm hỏng cả báo cáo.

Nạp sx/qc/bao_cao.py, controller SX Chi Tieu ATTP, sx/api/qc_baocao.py, patch THẬT; frappe giả.
Chạy: python3 scripts/test-baocao.py   (verify.sh gọi sẵn)
"""

import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

F.cai()
Q = F.nap_qc()
for t in ("khieu_nai", "ncc", "rework", "attp", "ho_so", "bao_cao"):
    F.nap(f"sx.qc.{t}", f"sx/qc/{t}.py")
for t in ("qc_ncc", "qc_attp", "qc_baocao", "qc_hoso"):
    F.nap(f"sx.api.{t}", f"sx/api/{t}.py")
BC = sys.modules["sx.qc.bao_cao"]
HS = sys.modules["sx.qc.ho_so"]
A = sys.modules["sx.api.qc_baocao"]
HSA = sys.modules["sx.api.qc_hoso"]
FR = sys.modules["frappe"]
CT = F.nap("ct_ctl", "sx/qc/doctype/sx_chi_tieu_attp/sx_chi_tieu_attp.py")
F.dang_ky(BC.PT, CT.SXChiTieuATTP)
HCT = F.nap("hs_ctl", "sx/qc/doctype/sx_ho_so_danh_muc/sx_ho_so_danh_muc.py")
F.dang_ky(HS.PT, HCT.SXHoSoDanhMuc)
P = F.nap("sx.patches.d151_bao_cao", "sx/patches/d151_bao_cao.py")
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")

# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- tỷ lệ, lũy kế, đánh giá (hàm thuần) --")
kiem("tỷ lệ giữ (tử, mẫu): 5/9 → 55,6%; mẫu 0 → chưa có số liệu", BC.gia_tri((5, 9)) == 55.6
     and BC.gia_tri((0, 0)) is None and BC.gia_tri(3) == 3 and BC.gia_tri(None) is None)
kiem("lũy kế tỷ lệ cộng tử / mẫu (3/3 + 5/9 = 8/12 = 66,7%), KHÔNG lấy trung bình 100% và 55,6%",
     BC.gia_tri(BC.luy_ke({"a": {"x": (3, 3)}, "b": {"x": (5, 9)}}, "x")) == 66.7)
kiem("lũy kế số đếm cộng thẳng; tháng chưa có số liệu (None) bỏ qua",
     BC.luy_ke({"a": {"x": 2}, "b": {"x": None}, "c": {"x": 1}}, "x") == 3)
kiem("≥: 96 ≥ 95 đạt; ≤: 1 ≤ 0 không đạt; chưa có số liệu → —",
     BC.danh_gia(96, BC.GE, 95) is True and BC.danh_gia(1, BC.LE, 0) is False and BC.danh_gia(None, BC.GE, 1) is None)
kiem("so sánh mặc định theo hướng tốt: tỷ lệ lượt ≥, sự cố ≤",
     BC.so_sanh_mac_dinh("ty_le_luot") == BC.GE and BC.so_sanh_mac_dinh("su_co") == BC.LE)
kiem("hiển thị kiểu tờ giấy: 55.6 → 55,6%; 3 → 3; None → —",
     (BC.hien(55.6, "%"), BC.hien(3, "phiếu"), BC.hien(None, "%")) == ("55,6%", "3", "—"))
kiem("tháng từ đầu năm", BC.thang_tu_dau_nam("2026-03") == ["2026-01", "2026-02", "2026-03"])

# ═══ 2. Dữ liệu tháng 8, 9, 10 ════════════════════════════════════════════
R = F.bang("SX QC Round")


def luot(n, ngay, ten, **k):
    R[n] = dict({"name": n, "ngay": ngay, "luot": ten, "docstatus": 1, "ghi_muon": 0, "nhap_lai_tu_giay": 0}, **k)


luot("A1", "2026-08-15", "Đầu sáng")
luot("A2", "2026-08-15", "Trưa")
luot("A3", "2026-08-15", "Cuối chiều")
luot("S1", "2026-09-01", "Đầu sáng", ghi_muon=1)
luot("S2", "2026-09-01", "Trưa")
luot("S3", "2026-09-01", "Cuối chiều", nhap_lai_tu_giay=1)
luot("S4", "2026-09-02", "Đầu sáng")
luot("S5", "2026-09-02", "Trưa")
luot("S6", "2026-09-02", "Bổ sung")
luot("O1", "2026-10-08", "Đầu sáng")
luot("O2", "2026-10-08", "Trưa")
luot("O3", "2026-10-08", "Cuối chiều")
luot("O4", "2026-10-09", "Đầu sáng")          # hôm nay — chưa tính
F.bang("SX Ngay San Xuat")["SXN-1"] = {"name": "SXN-1", "ngay": "2026-09-03", "docstatus": 1}
F.bang("SX Su Co").update({
    "SC-1": {"name": "SC-1", "ngay": "2026-09-05", "muc_do": "Cao", "trang_thai": "Đóng",
             "dong_ngay": datetime(2026, 9, 8, 10, 0), "dien_tap": 0},
    "SC-2": {"name": "SC-2", "ngay": "2026-09-10", "muc_do": "Thường", "trang_thai": "Mở", "dien_tap": 0},
    "SC-3": {"name": "SC-3", "ngay": "2026-09-12", "muc_do": "Cao", "trang_thai": "Đóng", "dien_tap": 1,
             "dong_ngay": datetime(2026, 9, 12, 10, 0)},
    "SC-4": {"name": "SC-4", "ngay": "2026-08-20", "muc_do": "Thường", "trang_thai": "Đóng",
             "dong_ngay": datetime(2026, 9, 5, 10, 0), "dien_tap": 0}})
F.bang("Issue").update({
    "I-1": {"name": "I-1", "custom_khieu_nai": 1, "opening_date": "2026-09-15", "status": "Open", "subject": "Bánh mốc"},
    "I-2": {"name": "I-2", "custom_khieu_nai": 1, "opening_date": "2026-10-02", "status": "Open"},
    "I-3": {"name": "I-3", "custom_khieu_nai": 0, "opening_date": "2026-09-16", "status": "Open"}})
F.bang("SX San Pham Cong Bo").update({
    "SP-1": {"name": "SP-1", "so_cong_bo": "01/2023", "ten_san_pham": "Bánh 1", "ngung_san_xuat": 0},
    "SP-2": {"name": "SP-2", "so_cong_bo": "02/2023", "ten_san_pham": "Bánh 2", "ngung_san_xuat": 0}})
F.bang("SX Kiem Nghiem").update({
    "KN-1": {"name": "KN-1", "doi_tuong": "Sản phẩm", "san_pham": "SP-1", "ten_san_pham": "Bánh 1",
             "ngay_gui": "2026-09-10", "ngay_kq": "2026-09-20", "ket_qua": "Đạt"},
    "KN-2": {"name": "KN-2", "doi_tuong": "Sản phẩm", "san_pham": "SP-2", "ten_san_pham": "Bánh 2",
             "ngay_gui": "2026-09-11", "ngay_kq": "2026-09-25", "ket_qua": "Không đạt"},
    "KN-3": {"name": "KN-3", "doi_tuong": "Sản phẩm", "san_pham": "SP-1", "ngay_gui": "2026-08-01",
             "ngay_kq": "2026-08-10", "ket_qua": "Đạt"}})
F.bang("SX Kiem Tra Xuat Xuong").update({
    "XX-1": {"name": "XX-1", "trang_thai": "Đã duyệt", "duyet_luc": "2026-09-03 10:00:00",
             "kiem_luc": "2026-08-30 10:00:00"},
    "XX-2": {"name": "XX-2", "trang_thai": "Trả lại", "duyet_luc": "2026-09-04 10:00:00"},
    "XX-3": {"name": "XX-3", "trang_thai": "Đã duyệt", "kiem_luc": "2026-09-06 10:00:00"},
    "XX-4": {"name": "XX-4", "trang_thai": "Chờ duyệt", "kiem_luc": "2026-09-07 10:00:00"}})
F.bang("SX Rework")["RW-1"] = {"name": "RW-1", "ngay": "2026-09-09", "ty_le": 5}
F.bang("SX Dau Hieu Dong Vat").update({"D1": {"name": "D1", "ngay": "2026-09-03"},
                                       "D2": {"name": "D2", "ngay": "2026-09-17"}})
F.bang("SX Khac Phuc").update({
    "CAR-1": {"name": "CAR-1", "ngay": "2026-09-06", "mo_ta": "Lưới rách", "trang_thai": "Đóng", "han": "2026-09-15",
              "ngay_xong": "2026-09-14", "kiem_ngay": "2026-09-20", "hieu_luc": "Có hiệu lực"},
    "CAR-2": {"name": "CAR-2", "ngay": "2026-09-01", "mo_ta": "Thùng hở", "trang_thai": "Đóng", "han": "2026-09-10",
              "ngay_xong": "2026-09-18", "kiem_ngay": "2026-09-22", "hieu_luc": "Có hiệu lực"},
    "CAR-3": {"name": "CAR-3", "ngay": "2026-09-02", "mo_ta": "x", "trang_thai": "Đóng", "kiem_ngay": "2026-09-23"},
    "CAR-4": {"name": "CAR-4", "ngay": "2026-08-01", "mo_ta": "Đèn kho", "trang_thai": "Mở", "han": "2026-08-30"}})
F.bang("SX Thiet Bi Do").update({
    "LS-01-M1": {"name": "LS-01-M1", "ten": "Lưới M1", "loai": "Lưới sàng, rây", "thanh_ly": 0, "chu_ky_thang": 12},
    "RY-01": {"name": "RY-01", "ten": "Rây", "loai": "Lưới sàng, rây", "thanh_ly": 0, "chu_ky_thang": 12}})

# ═══ 3. Chỉ số ════════════════════════════════════════════════════════════
print("\n-- chỉ số tháng 9/2026 --")
F.vai("ISO Manager")
r = A.so_lieu()
b = {x["ma"]: x for x in r["bang"]}
kiem("mặc định tháng trước (09/2026), cắt cuối tháng", (r["thang"], r["cat"]) == ("2026-09", "2026-09-30"),
     (r["thang"], r["cat"]))
kiem("bảng có các tháng từ đầu năm (T01–T09)", list(b["su_co"]["thang"]) == BC.thang_tu_dau_nam("2026-09"))
x = b["ty_le_luot"]
kiem("lượt hoàn tất: T9 = 5 lượt chính / (3 lượt × 3 ngày SX) = 55,6% (lượt bổ sung không tính, ngày có phiếu "
     "sản xuất mà không đi lượt vẫn là ngày SX); T8 100%; lũy kế 8/12 = 66,7%",
     x["thang"]["2026-09"] == 55.6 and x["thang"]["2026-08"] == 100.0 and x["nam"] == 66.7
     and x["thang"]["2026-01"] is None and x["ky"] == 55.6, x)
kiem("ghi đúng giờ T9: 5/6 lượt (tính cả lượt bổ sung) = 83,3%", b["ty_le_dung_gio"]["thang"]["2026-09"] == 83.3)
kiem("ngày SX thiếu lượt T9 = 2 (02/09 có 2 lượt, 03/09 không lượt); tháng không sản xuất = 0, không phải —",
     b["ngay_thieu_luot"]["thang"]["2026-09"] == 2 and b["ngay_thieu_luot"]["thang"]["2026-03"] == 0
     and b["nhap_lai_giay"]["ky"] == 1)
kiem("sự cố T9 = 2 (không tính diễn tập), mức Cao 1; T8 1; lũy kế 3; tháng không có = 0",
     b["su_co"]["thang"]["2026-09"] == 2 and b["su_co_cao"]["ky"] == 1 and b["su_co"]["thang"]["2026-08"] == 1
     and b["su_co"]["nam"] == 3 and b["su_co"]["thang"]["2026-05"] == 0)
kiem("sự cố đóng đúng hạn T9 = 1/2 (SC-2 còn mở đã quá 7 ngày = trễ) = 50%; T8 0% (đóng sau 16 ngày); lũy kế 33,3%",
     b["su_co_dung_han"]["thang"]["2026-09"] == 50.0 and b["su_co_dung_han"]["thang"]["2026-08"] == 0.0
     and b["su_co_dung_han"]["nam"] == 33.3, b["su_co_dung_han"])
kiem("khiếu nại T9 = 1 (Issue thường không tính, khiếu nại tháng 10 không vào báo cáo tháng 9)",
     b["khieu_nai"]["ky"] == 1 and b["khieu_nai"]["nam"] == 1)
kiem("kiểm nghiệm đạt T9 = 1/2 = 50%, lũy kế 2/3 = 66,7%", b["kn_dat"]["ky"] == 50.0 and b["kn_dat"]["nam"] == 66.7)
kiem("xuất xưởng duyệt T9 = 2/3 (theo NGÀY DUYỆT — kiểm 30/08 duyệt 03/09 tính tháng 9; phiếu cũ không có ngày "
     "duyệt lấy ngày kiểm; chờ duyệt không tính)", b["xx_duyet"]["ky"] == 66.7 and b["xx_duyet"]["thang"]["2026-08"] is None)
kiem("rework 1, động vật gây hại 2", b["rework"]["ky"] == 1 and b["dong_vat"]["ky"] == 2)
kiem("khắc phục đúng hạn T9 = 1/2 (theo ngày làm xong ≤ hạn; phiếu không đặt hạn không tính)",
     b["kp_dung_han"]["ky"] == 50.0)
kiem("tại ngày lập: thiết bị còn hạn 100%, kiểm nghiệm đạt còn hạn 1/2 = 50%, chưa có NCC → —",
     b["tb_con_han"]["ky"] == 100.0 and b["kn_con_han"]["ky"] == 50.0 and b["ncc_duyet"]["ky"] is None
     and b["tb_con_han"]["thang"] == {})
o = {x["ma"]: x for x in A.so_lieu("2026-10")["bang"]}
kiem("tháng đang chạy (10/2026): tính tới hết hôm qua — lượt hôm nay chưa vào", o["ty_le_luot"]["ky"] == 100.0
     and A.so_lieu("2026-10")["cat"] == "2026-10-08")
for i, ten in enumerate(("Đầu sáng", "Đầu sáng", "Trưa", "Cuối chiều")):    # ngày cũ trước D95: hai ca
    luot(f"J{i}", "2026-07-10", ten)
kiem("ngày cũ có 4 lượt (hai ca trước D95) → vẫn tối đa 100%, không vượt", {x["ma"]: x for x in A.so_lieu(
    "2026-09")["bang"]}["ty_le_luot"]["thang"]["2026-07"] == 100.0)
for i in range(4):
    R.pop(f"J{i}")
kiem("tháng sau → chặn (chưa có số liệu)", "chưa có số liệu" in (thu(lambda: A.so_lieu("2026-11")) or ""))

# ═══ 4. Chỉ tiêu ══════════════════════════════════════════════════════════
print("\n-- chỉ tiêu ATTP năm --")


def ct(**k):
    return A.luu_chi_tieu(json.dumps(dict({"nam": 2026}, **k)))


ct(chi_so="su_co_cao", so_sanh="≤", muc_tieu=0, ten="Không có sự cố mức Cao")
ct(chi_so="ty_le_luot", muc_tieu=95)
ct(chi_so="khieu_nai", so_sanh="≤", muc_tieu=2)
ct(chi_so="tb_con_han", so_sanh="≥", muc_tieu=100)
kiem("chỉ số lạ → chặn", "Chọn chỉ số" in (thu(lambda: ct(chi_so="xyz", muc_tieu=1)) or ""))
kiem("mục tiêu % ngoài 0 – 100 → chặn", "0 – 100" in (thu(lambda: ct(chi_so="kn_dat", muc_tieu=120)) or ""))
kiem("trùng chỉ số trong năm → chặn", "đã có chỉ tiêu" in (thu(lambda: ct(chi_so="khieu_nai", muc_tieu=1)) or ""))
kiem("thiếu mục tiêu → chặn", "mục tiêu" in (thu(lambda: ct(chi_so="rework", muc_tieu="")) or "").lower())
c = {x["chi_so"]: x for x in A.so_lieu("2026-09")["chi_tieu"]}
kiem("tỷ lệ lượt không ghi so sánh → mặc định ≥; 55,6% < 95% → Không đạt cả tháng lẫn lũy kế",
     c["ty_le_luot"]["so_sanh"] == "≥" and c["ty_le_luot"]["dat_ky"] is False and c["ty_le_luot"]["dat_nam"] is False)
kiem("sự cố Cao ≤ 0: tháng có 1 → Không đạt; tên theo văn bản giữ nguyên",
     c["su_co_cao"]["dat_ky"] is False and c["su_co_cao"]["ten"] == "Không có sự cố mức Cao")
kiem("khiếu nại ≤ 2: 1 → Đạt; thiết bị còn hạn (tại ngày lập) ≥ 100 → Đạt",
     c["khieu_nai"]["dat_ky"] is True and c["khieu_nai"]["dat_nam"] is True and c["tb_con_han"]["dat_ky"] is True)
nm = next(x for x in F.bang(BC.PT).values() if x["chi_so"] == "khieu_nai")["name"]
A.luu_chi_tieu(json.dumps({"name": nm, "ngung": 1}))
kiem("chỉ tiêu ngừng không đánh giá nữa (vẫn còn trong danh sách quản lý)",
     "khieu_nai" not in {x["chi_so"] for x in A.so_lieu("2026-09")["chi_tieu"]}
     and nm in {x["name"] for x in A.so_lieu("2026-09")["ds_chi_tieu"]})
kiem("ngừng rồi thì đặt lại chỉ tiêu mới cho chỉ số đó được", thu(lambda: ct(chi_so="khieu_nai", muc_tieu=1)) is None)
kiem("chỉ tiêu năm khác không lẫn vào", thu(lambda: A.luu_chi_tieu(json.dumps(
    {"nam": 2027, "chi_so": "su_co_cao", "muc_tieu": 0}))) is None
     and len(A.so_lieu("2026-09")["chi_tieu"]) == 4)

# ═══ 5. Bản in, độ bền, quyền ═════════════════════════════════════════════
print("\n-- báo cáo in, một loại hồ sơ lỗi, quyền --")
if F.jinja2:
    h = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", A.in_bao_cao("2026-09").split("</style>")[1]))
    kiem("báo cáo tháng: tiêu đề, ngày cắt, chỉ tiêu (KHÔNG ĐẠT), chỉ số T01–T09 + lũy kế, tại ngày lập",
         all(s in h for s in ("tháng 09/2026", "Số liệu tới hết 30/09/2026", "Không có sự cố mức Cao", "KHÔNG ĐẠT",
                              "T01", "T09", "Lũy kế", "55,6%", "66,7%", "Tại ngày lập")), h[:500])
    kiem("danh sách tháng: sự cố (bỏ diễn tập), khiếu nại, khắc phục (đóng trong tháng + đang quá hạn), kiểm nghiệm",
         "SC-1" in h and "SC-2" in h and "SC-3" not in h and "Bánh mốc" in h and "CAR-1" in h and "CAR-4" in h
         and "KN-2" in h and "Không đạt" in h)
    kiem("việc đang treo tại ngày lập (từ Tổng quan ATTP) và chỗ ký Giám đốc", "Việc đang treo" in h and "Giám đốc" in h)
    # W41 (D170): báo cáo tháng là BM.01.12 "Báo cáo phân tích dữ liệu tháng" — mã, lần BH ghi cứng tới W42.
    hn = " ".join(h.replace("&nbsp;", " ").split())
    kiem("W41/W42: đầu trang chung — 'Báo cáo phân tích dữ liệu tháng' (QT.01 mục 5.7), mã BM.01.12, lần BH 01; ô ký",
         "Báo cáo phân tích dữ liệu tháng (QT.01 mục 5.7) — tháng 09/2026" in hn and "BM.01.12 Lần BH: 01" in hn
         and "Báo cáo an toàn thực phẩm" not in h and "Trưởng Ban ISO (lập)" in h and "Giám đốc (đã xem)" in h,
         h[:300])
goc = FR.get_all


def hong(dt, *a, **k):
    if dt == "Issue":
        raise Exception("Unknown column custom_khieu_nai")
    return goc(dt, *a, **k)


FR.get_all = hong
b2 = {x["ma"]: x for x in A.so_lieu("2026-09")["bang"]}
h2 = A.in_bao_cao("2026-09") if F.jinja2 else ""
FR.get_all = goc
kiem("site chưa có trường khiếu nại → chỉ số khiếu nại trống (—), không phải 0; chỉ số khác vẫn đủ",
     b2["khieu_nai"]["ky"] is None and b2["khieu_nai"]["thang"]["2026-03"] is None and b2["su_co"]["ky"] == 2
     and (not F.jinja2 or "Chưa có trên app" in h2))
for vai, duoc in (("SX QC", False), ("Production Manager", False), ("SX Quan Ly", True)):
    F.vai(vai)
    kiem(f"{vai}: {'xem / đặt chỉ tiêu / in được' if duoc else 'không xem, không đặt chỉ tiêu, không in'}",
         all((thu(f) is None) == duoc for f in (A.so_lieu, lambda: A.in_bao_cao("2026-09"),
                                                lambda: A.luu_chi_tieu(json.dumps({"nam": 2026, "chi_so": "rework",
                                                                                   "muc_tieu": 3})))))
F.vai("ISO Manager")

# ═══ 6. Gói hồ sơ cho đoàn, màn hình ═════════════════════════════════════
print("\n-- gói hồ sơ, màn hình --")
P.execute()
P.execute()
dm = [x for x in F.bang(HS.PT).values() if x.get("bieu_mau") == "BC.THANG"]
kiem("patch d151: báo cáo tháng vào danh mục hồ sơ (nhóm Hệ thống quản lý), chạy lại không nhân đôi",
     len(dm) == 1 and dm[0]["nhom"] == "Hệ thống quản lý" and "BC.THANG" in HS.BIEU_MAU)
if F.jinja2:
    g = HSA._in("BC.THANG", F.getdate("2026-08-01"), F.getdate("2026-10-09"))
    kiem("gói zip: mỗi tháng trong kỳ một báo cáo (tháng đang chạy tính tới hôm qua)",
         [x[0] for x in g] == ["2026-08.html", "2026-09.html", "2026-10.html"] and "tháng 09/2026" in g[1][1])
    F.dat_ngay("2026-11-01")
    g = HSA._in("BC.THANG", F.getdate("2026-10-01"), F.getdate("2026-11-01"))
    F.dat_ngay("2026-10-09")
    kiem("ngày 01/11: tháng 11 chưa có ngày nào xong → gói chỉ có báo cáo tháng 10, không lỗi",
         [x[0] for x in g] == ["2026-10.html"])
kiem("patch có trong patches.txt", "sx.patches.d151_bao_cao" in open("sx/patches.txt", encoding="utf-8").read())
qj = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
ui = open("sx/public/sx/components/qcui.js", encoding="utf-8").read()
kiem("route #/qc/baocao; nút 'Báo cáo' trong tab Xem xét", "baocao: '/assets/sx/sx/views/qc_baocao.js'" in qj
     and "['baocao', 'Báo cáo']" in ui and "'baocao'" in qj.split("const XEM_XET")[1].split("\n")[0])
js = open("sx/public/sx/views/qc_baocao.js", encoding="utf-8").read()
kiem("màn báo cáo: chọn tháng, in, thêm / sửa / xoá chỉ tiêu", all(s in js for s in (
    "sx.api.qc_baocao.so_lieu", "sx.api.qc_baocao.in_bao_cao", "sx.api.qc_baocao.luu_chi_tieu",
    "sx.api.qc_baocao.xoa_chi_tieu", "tabXemXet('baocao')")))
kiem("W41: màn cùng tên, mã với bản in (BM.01.12 Báo cáo phân tích dữ liệu tháng)",
     "Báo cáo phân tích dữ liệu tháng ${" in js and "BM.01.12 · số liệu tới hết" in js and "Báo cáo ATTP tháng" not in js)

F.ket_thuc("BAOCAO")
