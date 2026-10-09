"""D148 (W22) — màn Tổng quan ATTP cho Trưởng Ban ISO, Giám đốc.

Vì sao phải có bài này:
  · Đèn tổng quan tính bằng bộ luật riêng → một ngày nó nói "xanh" trong khi hộp nhắc báo quá hạn.
  · Mục nhắc mới thêm mà quên gắn mảng → việc treo biến mất khỏi tổng quan, không ai thấy.
  · Lô đang thu hồi, khiếu nại quá hạn, NCC chưa duyệt — hộp nhắc không theo dõi, tổng quan phải có.
  · Một mảng lỗi (chưa migrate) làm hỏng cả màn của Giám đốc.

Nạp sx/qc/attp.py, sx/qc/nhac.py, sx/api/qc.py, sx/api/qc_attp.py THẬT; frappe giả (fakefrappe).
Chạy: python3 scripts/test-attp.py   (verify.sh gọi sẵn)
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

F.cai()
Q = F.nap_qc()
NH = sys.modules["sx.qc.nhac"]
for t in ("khieu_nai", "ncc", "rework", "attp"):
    F.nap(f"sx.qc.{t}", f"sx/qc/{t}.py")
F.nap("sx.api.qc_ncc", "sx/api/qc_ncc.py")
A = sys.modules["sx.qc.attp"]
API = F.nap("sx.api.qc_attp", "sx/api/qc_attp.py")
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")
MA = [x[0] for x in A.LINH_VUC]

# ═══ 1. Luật đèn (hàm thuần) ═══════════════════════════════════════════════
print("\n-- đèn, gom theo mảng (hàm thuần) --")
CAO = {"muc_do": "cao", "tieu_de": "c", "chi_tiet": "", "route": "#/qc"}
TH = {"muc_do": "thuong", "tieu_de": "t", "chi_tiet": "", "route": "#/qc"}
kiem("không việc treo → Xanh; có việc thường → Vàng; có việc mức cao → Đỏ",
     (A.den([]), A.den([TH]), A.den([TH, CAO])) == (A.XANH, A.VANG, A.DO))
r = A.tong_hop([dict(TH, nhom="cat"), dict(TH, nhom="thiet_bi"), dict(CAO, nhom="thiet_bi")], {})
th = {x["ma"]: x for x in r["linh_vuc"]}
kiem("mục nhắc vào đúng thẻ theo `nhom`; mảng không số liệu vẫn hiện, số '–'",
     len(th["thiet_bi"]["nhac"]) == 2 and len(th["cat"]["nhac"]) == 1 and th["rework"]["so"] == "–"
     and th["rework"]["nhan_so"] == "chưa có số liệu" and len(r["linh_vuc"]) == len(A.LINH_VUC))
kiem("thẻ đỏ lên đầu, rồi vàng, rồi xanh; cùng màu giữ thứ tự danh mục; việc mức cao đứng trước",
     [x["ma"] for x in r["linh_vuc"]][:2] == ["thiet_bi", "cat"]
     and [x["ma"] for x in r["linh_vuc"]][2:] == [m for m in MA if m not in ("thiet_bi", "cat")]
     and th["thiet_bi"]["nhac"][0]["muc_do"] == "cao" and r["dem"] == {"do": 1, "vang": 1, "xanh": len(MA) - 2})
kiem("số kiểu tờ giấy: 99.25 → 99,25; 15.0 → 15", A._so(99.25) == "99,25" and A._so(15.0) == "15")


def them(ma, s):
    return {x["ma"]: x for x in A.tong_hop([], {ma: s})["linh_vuc"]}[ma]


t = them("khieu_nai", {"mo": 2, "qua_han": 1, "lau_nhat": 12, "ky": 3})
kiem("khiếu nại quá hạn xử lý → Đỏ (hộp nhắc không theo dõi khiếu nại)", t["den"] == A.DO
     and "1 khiếu nại quá hạn" in t["nhac"][0]["tieu_de"] and "12 ngày" in " ".join(t["dong"]), t)
kiem("khiếu nại mở chưa quá hạn → Vàng; không có → Xanh",
     them("khieu_nai", {"mo": 1, "qua_han": 0})["den"] == A.VANG and them("khieu_nai", {"mo": 0})["den"] == A.XANH)
dt_ok = {"ngay": "2026-08-01", "dat": 1, "can_bang_pt": 99.25, "so_ngay": 69}
kiem("lô đang thu hồi → Đỏ", them("truy_xuat", {"thu_hoi": 1, "dien_tap": dt_ok})["den"] == A.DO)
t = them("truy_xuat", {"thu_hoi": 0, "dien_tap": dt_ok})
kiem("diễn tập gần đây, đạt → Xanh, dòng nói ngày + cân bằng", t["den"] == A.XANH
     and t["dong"] == ["Diễn tập gần nhất 01/08/2026 — cân bằng 99,25% (đạt)"], t["dong"])
kiem("chưa diễn tập lần nào / quá 12 tháng / lần gần nhất chưa đạt 98% → Vàng",
     them("truy_xuat", {"thu_hoi": 0, "dien_tap": None})["den"] == A.VANG
     and them("truy_xuat", {"dien_tap": dict(dt_ok, so_ngay=366)})["den"] == A.VANG
     and them("truy_xuat", {"dien_tap": dict(dt_ok, so_ngay=365)})["den"] == A.XANH
     and "chưa đạt" in them("truy_xuat", {"dien_tap": dict(dt_ok, dat=0, can_bang_pt=96)})["nhac"][0]["tieu_de"])
t = them("ncc", {"tong": 5, "duyet": 3, "thieu": 1})
kiem("NCC chưa duyệt / thiếu hồ sơ → Vàng, không bao giờ Đỏ (W09 chỉ cảnh báo)", t["den"] == A.VANG
     and len(t["nhac"]) == 2 and t["so"] == "3/5" and them("ncc", {"tong": 2, "duyet": 2})["den"] == A.XANH)

# Mọi mục hộp nhắc phải mang một mảng có trong danh mục — mục mới quên gắn là biến khỏi tổng quan.
luot = [{"name": "Q1", "ngay": "2026-10-08", "luot": "Đầu sáng", "docstatus": 1},
        {"name": "Q2", "ngay": "2026-10-01", "luot": "Trưa", "docstatus": 0},
        {"name": "Q3", "ngay": "2026-09-20", "luot": "Trưa", "docstatus": 1, "reviewed_on": None},
        {"name": "Q4", "ngay": "2026-10-08", "luot": "Trưa", "docstatus": 1, "b2_rang_lac_nhiet": 160,
         "t2_so_bay_dau_hieu": 2}]
ds = NH.tinh("2026-10-09", luot, [{"name": "S", "ngay": "2026-09-01", "trang_thai": "Mở"}], {},
             bot_nen=[{"batch": "B", "ngay": "2026-10-01", "ton": 3}],
             luu_mau={"den_han": 2, "lau_nhat": "2026-10-01", "dot_cho": [{"name": "D", "lap_luc": "2026-10-01"}]},
             xuat_xuong={"cho_duyet": 1, "lau_nhat": "2026-10-07"},
             dong_vat={"co_du_lieu": True, "khu_hai_tuan": [{"khu": "Kho", "tram": ["R01"], "tuan": ["2026-09-28", "2026-10-05"]}]},
             cat={"co_du_lieu": True, "dang_dung": True, "rang_khong_cat": "2026-10-07",
                  "cho_kln": [{"ngay": "2026-10-01", "ncc": "x", "kln": "", "lo_mau": 0}], "so_ngay": 50, "toi_da": 30},
             thiet_bi={"qua_han": [{"ma": "DH-01", "han": "2026-10-01"}], "khong_dat": [{"ma": "NC-01"}],
                       "sap_den": [{"ma": "LS-01", "han": "2026-10-20"}], "thieu_loai": ["Cân"], "han_dau": "2026-10-31"},
             kiem_nghiem={"qua_han": [{"ten": "a", "han": "2026-10-01"}], "den_han": [{"ten": "b", "han": "2026-10-20"}],
                          "cho_lau": [{"ten": "c"}], "khong_dat": [{"ten": "d"}]},
             viec_dinh_ky={"qua_han": [{"ten": "x", "han": "2026-10-01", "con": -8}],
                           "sap_den": [{"ten": "y", "han": "2026-10-20", "con": 11}]},
             khac_phuc={"qua_han": [{"name": "CAR-1", "han": "2026-10-01"}],
                        "cho_kiem": [{"name": "CAR-2", "ngay_xong": "2026-09-20"}]})
# Nhà máy chưa ghi dấu hiệu theo trạm (W15) → nhắc bẫy cũ theo lượt tuần, cũng phải có mảng.
ds += NH.tinh("2026-10-09", [{"name": "T1", "ngay": "2026-09-28", "luot": "Tuần", "docstatus": 1,
                              "t2_so_bay_dau_hieu": 2},
                             {"name": "T2", "ngay": "2026-10-05", "luot": "Tuần", "docstatus": 1,
                              "t2_so_bay_dau_hieu": 1}], [], {}, dong_vat={})
kiem("nhắc bẫy cũ (chưa có dữ liệu trạm) thuộc mảng động vật gây hại",
     next(x for x in ds if "Bẫy chuột" in x["tieu_de"])["nhom"] == "dong_vat")
nhom = {x.get("nhom") for x in ds}
kiem(f"hộp nhắc: {len(ds)} mục, mục nào cũng gắn một mảng có trong danh mục tổng quan",
     len(ds) >= 15 and nhom <= set(MA) and None not in nhom, sorted(str(x) for x in nhom))
kiem("mảng của mục nhắc: bột nền → vòng kiểm (mục 8 kho bột), xuất xưởng, cát, việc định kỳ…",
     {x["route"]: x["nhom"] for x in ds}["#/qc/xuatxuong"] == "xuat_xuong"
     and next(x for x in ds if "bột nền" in x["tieu_de"])["nhom"] == "vong_kiem"
     and {"cat", "thiet_bi", "kiem_nghiem", "viec_dinh_ky", "dong_vat", "luu_mau", "su_co", "khac_phuc"} <= nhom)

# ═══ 2. API: số liệu 13 mảng ═══════════════════════════════════════════════
print("\n-- tong_quan: số liệu từng mảng --")


def luot_(n, ngay, ten, ds=1, **k):
    F.bang("SX QC Round")[n] = dict({"name": n, "ngay": ngay, "luot": ten, "docstatus": ds, "ghi_muon": 0,
                                     "nhap_lai_tu_giay": 0, "reviewed_on": "2026-10-09", "creation": f"{ngay} 08:00:00",
                                     "finished_at": datetime.fromisoformat(f"{ngay} 09:00:00")}, **k)


for ngay, ds_l in (("2026-10-05", ("Tuần", "Trưa", "Cuối chiều")), ("2026-10-07", ("Đầu sáng", "Trưa", "Cuối chiều")),
                   ("2026-10-08", ("Đầu sáng", "Trưa"))):
    for ten in ds_l:
        luot_(f"QC-{ngay}-{ten}", ngay, ten)
luot_("QC-HN", "2026-10-09", "Đầu sáng")
luot_("QC-HN2", "2026-10-09", "Trưa", ds=0)
F.bang("SX Su Co").update({
    "SC-1": {"name": "SC-1", "ngay": "2026-09-20", "trang_thai": "Mở", "muc_do": "Cao", "xu_ly_ngay": "cô lập lô",
             "dien_tap": 0},
    "SC-2": {"name": "SC-2", "ngay": "2026-10-01", "trang_thai": "Đóng", "muc_do": "Thường", "dien_tap": 1},
    "SC-3": {"name": "SC-3", "ngay": "2026-10-07", "trang_thai": "Mở", "muc_do": "Thường", "xu_ly_ngay": "x",
             "dien_tap": 0},
    "SC-4": {"name": "SC-4", "ngay": "2026-10-08", "trang_thai": "Mở", "muc_do": "Cao", "xu_ly_ngay": "x",
             "dien_tap": 1}})
F.bang("Issue").update({
    "ISS-1": {"name": "ISS-1", "custom_khieu_nai": 1, "status": "Open", "opening_date": "2026-10-05"},
    "ISS-2": {"name": "ISS-2", "custom_khieu_nai": 1, "status": "Closed", "opening_date": "2026-09-15"},
    "ISS-3": {"name": "ISS-3", "custom_khieu_nai": 0, "status": "Open", "opening_date": "2026-09-01"},
    "ISS-4": {"name": "ISS-4", "custom_khieu_nai": 1, "status": "Closed", "opening_date": "2026-08-01"}})
F.bang("SX Kiem Tra Xuat Xuong").update({
    "XX-1": {"name": "XX-1", "trang_thai": "Chờ duyệt", "kiem_luc": "2026-10-08 10:00:00"},
    "XX-2": {"name": "XX-2", "trang_thai": "Đã duyệt", "kiem_luc": "2026-10-02 10:00:00"},
    "XX-3": {"name": "XX-3", "trang_thai": "Trả lại", "kiem_luc": "2026-10-03 10:00:00"}})
F.bang("Batch").update({"LO-1": {"name": "LO-1", "custom_thu_hoi": 1}, "LO-2": {"name": "LO-2", "custom_thu_hoi": 0}})
F.bang("SX Dien Tap Truy Xuat").update({
    "DT-0": {"name": "DT-0", "ngay": "2026-03-01", "ket_thuc": "2026-03-01 10:30:00", "dat": 0, "can_bang_pt": 95},
    "DT-1": {"name": "DT-1", "ngay": "2026-08-01", "ket_thuc": "2026-08-01 10:30:00", "dat": 1, "can_bang_pt": 99.25},
    "DT-2": {"name": "DT-2", "ngay": "2026-09-30", "ket_thuc": None, "dat": 0, "can_bang_pt": 0}})
F.bang("SX Thiet Bi Do").update({
    "LS-01-M1": {"name": "LS-01-M1", "ten": "Lưới sàng M1", "loai": "Lưới sàng, rây", "thanh_ly": 0, "chu_ky_thang": 12},
    "RY-01": {"name": "RY-01", "ten": "Rây kiểm", "loai": "Lưới sàng, rây", "thanh_ly": 0, "chu_ky_thang": 12},
    "CU-01": {"name": "CU-01", "ten": "Cân cũ", "loai": "Cân", "thanh_ly": 1}})
F.bang("SX San Pham Cong Bo").update({
    f"SP-{i}": {"name": f"SP-{i}", "ten_san_pham": f"Bánh {i}", "so_cong_bo": f"0{i}/2023", "ngung_san_xuat": 0}
    for i in (1, 2, 3, 4)})
F.bang("SX Kiem Nghiem").update({
    "KN-1": {"name": "KN-1", "doi_tuong": "Sản phẩm", "san_pham": "SP-1", "ngay_gui": "2026-03-01", "ket_qua": "Đạt"},
    "KN-2": {"name": "KN-2", "doi_tuong": "Sản phẩm", "san_pham": "SP-2", "ngay_gui": "2026-10-01", "ket_qua": ""},
    "KN-4": {"name": "KN-4", "doi_tuong": "Sản phẩm", "san_pham": "SP-4", "ngay_gui": "2025-09-01", "ket_qua": "Đạt"}})
# Dòng sổ cũ (D141: mỗi ngày có rang một dòng — D164 đánh dấu so_cu): cát ngày thứ 12 hôm 08/10.
F.bang("SX Nhat Ky Cat")["CAT-1"] = {"name": "CAT-1", "ngay": "2026-10-08", "so_ngay_dung": 12, "so_cu": 1,
                                     "ncc_cat": "NCC-CAT", "ten_ncc": "Cát Sông Lô", "doi_nguon": 0}
F.bang("SX Dau Hieu Dong Vat")["DV-1"] = {"name": "DV-1", "ngay": "2026-10-06", "tram": "R05", "khu": "Kho NL"}
F.bang("Supplier").update({
    "NCC-CAT": {"name": "NCC-CAT", "supplier_name": "Cát Sông Lô", "disabled": 0, "custom_loai_ncc": "Cát rang",
                "custom_ncc_duyet": 1},
    "NCC-BB": {"name": "NCC-BB", "supplier_name": "In Bao Bì", "disabled": 0, "custom_loai_ncc": "Bao bì ngoài",
               "custom_ncc_duyet": 0}})
F.bang("SX Ho So NCC").update({
    "H1": {"name": "H1", "parenttype": "Supplier", "parent": "NCC-CAT", "loai_ho_so": "Hợp đồng / đơn hàng"},
    "H2": {"name": "H2", "parenttype": "Supplier", "parent": "NCC-CAT", "loai_ho_so": "Đăng ký kinh doanh"}})
F.bang("SX QC Luu Mau").update({
    f"LM-{i}": {"name": f"LM-{i}", "trang_thai": "Đang lưu", "han_luu": "2027-06-01"} for i in (1, 2, 3)})
F.bang("SX QC Luu Mau")["LM-9"] = {"name": "LM-9", "trang_thai": "Đã huỷ", "han_luu": "2026-01-01"}
F.bang("SX Rework").update({
    "RW-1": {"name": "RW-1", "ngay": "2026-10-02", "ty_le": 8.0},
    "RW-2": {"name": "RW-2", "ngay": "2026-10-06", "ty_le": 4.5},
    "RW-0": {"name": "RW-0", "ngay": "2026-08-30", "ty_le": 9.9}})
F.bang("SX Viec Dinh Ky").update({
    "VD-1": {"name": "VD-1", "ten": "Thử khôi phục dữ liệu", "han": "2026-11-30", "bao_truoc": 30, "ngung": 0,
             "chu_ky": "Năm"},
    "VD-2": {"name": "VD-2", "ten": "Thay bóng đèn bẫy", "han": "2026-10-01", "bao_truoc": 30, "ngung": 0,
             "chu_ky": "Năm"},
    "VD-3": {"name": "VD-3", "ten": "Việc đã ngừng", "han": "2026-10-20", "bao_truoc": 30, "ngung": 1,
             "chu_ky": "Năm"}})

F.vai("ISO Manager")
r = API.tong_quan()
th = {x["ma"]: x for x in r["linh_vuc"]}
kiem("kỳ số liệu 30 ngày tới HÔM QUA (hôm nay còn đang làm)", (r["ngay"], r["tu"], r["den"])
     == ("2026-10-09", "2026-09-09", "2026-10-08"), (r["tu"], r["den"]))
v = th["vong_kiem"]
kiem("vòng kiểm: 8/9 lượt (3 ngày SX) = 88,9%; hôm nay 1/3 xong (bản nháp không tính); 08/10 thiếu lượt → Vàng",
     v["so"] == "88,9%" and v["nhan_so"] == "lượt đủ · 8/9" and v["dong"][0] == "Hôm nay 1/3 lượt đã xong"
     and v["dong"][1] == "1 ngày sản xuất thiếu lượt" and v["den"] == A.VANG
     and any("thiếu lượt" in x["tieu_de"] for x in v["nhac"]), v)
s = th["su_co"]
kiem("sự cố: 2 mở (bỏ phiếu diễn tập đang mở), 1 quá hạn, 1 mức Cao → Đỏ; diễn tập đếm riêng",
     s["den"] == A.DO and s["so"] == "2"
     and s["dong"] == ["1 quá hạn · 1 mức Cao", "2 phiếu mới trong kỳ · 2 phiếu diễn tập"], s["dong"])
k = th["khieu_nai"]
kiem("khiếu nại: 1 đang mở (Issue không phải khiếu nại không tính), 2 mới trong kỳ (bỏ cái 08/2026) → Vàng",
     k["den"] == A.VANG and k["so"] == "1" and k["dong"] == ["2 khiếu nại mới trong kỳ", "Mở lâu nhất 4 ngày"], k)
x = th["xuat_xuong"]
kiem("xuất xưởng: 1 phiếu chờ duyệt từ hôm qua → Đỏ (luật hộp nhắc); 1 duyệt, 1 trả lại",
     x["den"] == A.DO and x["so"] == "1" and x["dong"] == ["1 lô đã duyệt · 1 trả lại trong kỳ"], x)
t = th["truy_xuat"]
kiem("truy xuất: 1 lô đang thu hồi → Đỏ; diễn tập gần nhất là lần ĐÃ XONG (bỏ lần đang dở)",
     t["den"] == A.DO and t["so"] == "1" and "01/08/2026" in t["dong"][0] and "99,25%" in t["dong"][0], t)
b = th["thiet_bi"]
kiem("thiết bị: 2 trong danh mục (bỏ thanh lý), hạn đầu 31/10 sắp đến → Vàng, nói loại chưa khai",
     b["so"] == "2" and b["den"] == A.VANG and "2 sắp đến hạn" in b["dong"][0] and "đồng hồ nhiệt" in b["dong"][1], b)
n = th["kiem_nghiem"]
kiem("kiểm nghiệm: 1/4 đạt còn hạn (Đạt từ 09/2025 đã quá 12 tháng không tính); quá hạn → Đỏ",
     n["so"] == "1/4" and n["dong"] == ["1 quá hạn · 1 đến hạn · 1 chờ kết quả · 0 không đạt"] and n["den"] == A.DO, n)
c = th["cat"]
kiem("cát: 12 ngày đang dùng, nguồn Cát Sông Lô → Xanh", c["so"] == "12" and c["den"] == A.XANH
     and c["dong"] == ["Nguồn: Cát Sông Lô"], c)
kiem("động vật gây hại: 1 lần thấy, không khu nào 2 tuần liền → Xanh", th["dong_vat"]["so"] == "1"
     and th["dong_vat"]["den"] == A.XANH)
kiem("NCC: 1/2 đã duyệt, 1 thiếu hồ sơ → Vàng", th["ncc"]["so"] == "1/2" and th["ncc"]["den"] == A.VANG
     and th["ncc"]["dong"] == ["1 thiếu / hết hạn hồ sơ"], th["ncc"])
kiem("lưu mẫu: 3 mẫu đang lưu → Xanh", th["luu_mau"]["so"] == "3" and th["luu_mau"]["den"] == A.XANH)
kiem("rework: 2 phiếu trong kỳ (bỏ phiếu ngoài kỳ), cao nhất 8%", th["rework"]["so"] == "2"
     and th["rework"]["dong"] == ["Cao nhất 8% khối lượng mẻ (tối đa 10%)"], th["rework"])
kiem("việc định kỳ: 1 quá hạn → Đỏ; 'tiếp theo' là việc chưa tới hạn (bỏ việc quá hạn, việc đã ngừng)",
     th["viec_dinh_ky"]["so"] == "1" and th["viec_dinh_ky"]["den"] == A.DO
     and th["viec_dinh_ky"]["dong"] == ["Tiếp theo: Thử khôi phục dữ liệu — 30/11/2026"], th["viec_dinh_ky"])
kiem("vải ủ (W29): chưa khai vải, chưa ghi sổ giặt → '–', không nhắc gì (C31) → Xanh",
     th["vai_u"]["so"] == "–" and th["vai_u"]["den"] == A.XANH and th["vai_u"]["bieu_mau"] == "BM.08.05",
     th["vai_u"])
kiem("kiểm xe (W34): chưa có chuyến nào ghi kiểm xe → '–', không nhắc gì → Xanh",
     th["kiem_xe"]["so"] == "–" and th["kiem_xe"]["den"] == A.XANH and th["kiem_xe"]["bieu_mau"] == "BM.09.01"
     and th["kiem_xe"]["route"] == "#/qc/kiemxe", th["kiem_xe"])
kiem("đếm đèn 5 đỏ · 4 vàng · 7 xanh; thẻ đỏ lên đầu theo thứ tự danh mục",
     r["dem"] == {"do": 5, "vang": 4, "xanh": 7}
     and [x["ma"] for x in r["linh_vuc"][:5]] == ["su_co", "xuat_xuong", "truy_xuat", "kiem_nghiem", "viec_dinh_ky"],
     r["dem"])
F.vai("SX QC")
hop = Q.nhac()["ds"]
F.vai("ISO Manager")
# Mục cảnh báo riêng của tổng quan (khiếu nại, thu hồi, NCC) không mang `nhom`; mọi mục còn lại phải
# là ĐÚNG các mục của hộp nhắc — không thiếu, không thừa, không lặp.
kiem("CÙNG NGUỒN với hộp nhắc: các mục nhắc trên thẻ = đúng danh sách hộp nhắc, mỗi mục một lần",
     len(hop) >= 4 and sorted(x["tieu_de"] for x in hop)
     == sorted(x["tieu_de"] for t in r["linh_vuc"] for x in t["nhac"] if x.get("nhom")),
     [x["tieu_de"] for x in hop])

hn = {n: F.bang("SX QC Round").pop(n) for n in ("QC-HN", "QC-HN2")}
kiem("hôm nay chưa có lượt, không có phiếu ngày sản xuất → nói 'chưa có sản xuất', không phải 0/3",
     {x["ma"]: x for x in API.tong_quan()["linh_vuc"]}["vong_kiem"]["dong"][0]
     == "Hôm nay chưa có sản xuất / chưa có lượt nào")
F.bang("SX Ngay San Xuat")["SXN-1"] = {"name": "SXN-1", "ngay": "2026-10-09", "docstatus": 0}
kiem("hôm nay CÓ phiếu ngày sản xuất mà chưa đi lượt nào → 0/3",
     {x["ma"]: x for x in API.tong_quan()["linh_vuc"]}["vong_kiem"]["dong"][0] == "Hôm nay 0/3 lượt đã xong")
F.bang("SX Ngay San Xuat").clear()
F.bang("SX QC Round").update(hn)

# W32 (D164): loại cát mà chưa ghi cát mới đưa vào máy → thẻ không nói số ngày.
F.bang("SX Nhat Ky Cat")["CAT-2"] = {"name": "CAT-2", "ngay": "2026-10-09", "viec": "Loại cát", "ly_do_loai": "đủ ngày",
                                     "creation": "2026-10-09 08:00:00"}
c = {x["ma"]: x for x in API.tong_quan()["linh_vuc"]}["cat"]
kiem("cát đã loại, chưa ghi cát mới → thẻ cát '–', nói không có cát đang dùng",
     c["so"] == "–" and "không có cát đang dùng" in c["nhan_so"], c)
F.bang("SX Nhat Ky Cat").pop("CAT-2")

# W34 (D165): kiểm xe — tuần ĐÃ HẾT có chuyến / có chuyến QC kiểm; tuần đang chạy chưa tính vào tỉ số.
def _xe(dt, ten, ngay, **k):
    F.bang(dt)[ten] = {"name": ten, "posting_date": ngay, "docstatus": 1, "is_return": 0, "update_stock": 1,
                       "custom_xe_ket_luan": "Đạt", **k}


_xe("Sales Invoice", "SI-1", "2026-09-16")                                   # tuần 14/09: không QC
_xe("Sales Invoice", "SI-2", "2026-09-30", custom_xe_qc_kiem="qc@x")         # tuần 28/09: có QC
_xe("Purchase Receipt", "PR-1", "2026-10-01", custom_xe_ket_luan="Không đạt")
_xe("Sales Invoice", "SI-3", "2026-10-06")                                   # tuần này: chưa tính
_xe("Sales Invoice", "SI-4", "2026-09-02")                                   # tuần 31/08: ngoài kỳ
_xe("Sales Invoice", "SI-7", "2026-09-08")              # tuần 07/09 (tuần đầu kỳ): tính tuần, không tính chuyến
_xe("Sales Invoice", "SI-5", "2026-10-02", is_return=1)                      # trả hàng: không phải chuyến
_xe("Sales Invoice", "SI-6", "2026-10-02", update_stock=0)                   # không trừ kho
k = {x["ma"]: x for x in API.tong_quan()["linh_vuc"]}["kiem_xe"]
kiem("kiểm xe: 1/3 tuần đã hết có QC kiểm; 4 chuyến trong kỳ, 1 xe không đạt; tuần này chưa QC, tháng 9 "
     "chưa xem (đã qua ngày 5) → Vàng, hai nhắc",
     k["so"] == "1/3" and k["dong"] == ["4 chuyến · 1 xe không đạt"] and k["den"] == A.VANG
     and [x["tieu_de"] for x in k["nhac"]] == ["Tuần này 1 chuyến hàng, chưa chuyến nào QC kiểm xe",
                                               "Kiểm xe BM.09.01 tháng 09/2026 chưa được Trưởng Ban ISO xem"], k)
for b in ("Sales Invoice", "Purchase Receipt"):
    F.bang(b).clear()

# ═══ 3. Một mảng hỏng không làm trống cả màn; quyền ══════════════════════
print("\n-- mảng lỗi, quyền --")
goc = API._rework
API._rework = lambda *a: 1 / 0
r2 = API.tong_quan()
API._rework = goc
th2 = {x["ma"]: x for x in r2["linh_vuc"]}
kiem("mảng rework lỗi → thẻ 'chưa có số liệu', các thẻ còn lại vẫn đủ số",
     th2["rework"]["so"] == "–" and th2["rework"]["nhan_so"] == "chưa có số liệu"
     and th2["cat"]["so"] == "12" and th2["su_co"]["den"] == A.DO)
F.bang("SX Dien Tap Truy Xuat").clear()
t = {x["ma"]: x for x in API.tong_quan()["linh_vuc"]}["truy_xuat"]
kiem("chưa diễn tập lần nào → thêm cảnh báo; lô thu hồi vẫn giữ Đỏ, đứng trước",
     t["den"] == A.DO and [x["tieu_de"] for x in t["nhac"]] == ["1 lô đang thu hồi, khoá xuất tới khi gỡ",
                                          "Chưa diễn tập truy xuất lần nào"]
     and t["dong"] == ["Chưa có lần diễn tập truy xuất nào trên app"], t)
for vai, duoc in (("SX QC", False), ("Production Manager", False), ("SX QC Packing", False),
                  ("SX Quan Ly", True), ("ISO Manager", True)):
    F.vai(vai)
    kiem(f"{vai}: {'xem được' if duoc else 'không xem được'}", (thu(API.tong_quan) is None) == duoc)
F.vai("SX QC")

# ═══ 4. Màn hình ══════════════════════════════════════════════════════════
print("\n-- màn hình --")
qj = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
kiem("route #/qc/attp; tab Xem xét (người duyệt) mở vào Tổng quan, sáng cả ở Xem xét tháng",
     "attp: '/assets/sx/sx/views/qc_attp.js'" in qj and "tabs.push(['attp', 'Xem xét'])" in qj
     and "const XEM_XET = ['attp', 'review', 'baocao', 'hoso']" in qj)
js = open("sx/public/sx/views/qc_attp.js", encoding="utf-8").read()
rv = open("sx/public/sx/views/qc_review.js", encoding="utf-8").read()
kiem("màn tổng quan gọi qc_attp.tong_quan, hai nút Tổng quan / Xem xét tháng ở cả hai màn",
     "sx.api.qc_attp.tong_quan" in js and "tabXemXet('attp')" in js and "tabXemXet('review')" in rv)
kiem("card QC trên màn Quản lý có nút sang Tổng quan ATTP", "#/qc/attp" in open(
    "sx/public/sx/cards/qcnhac.js", encoding="utf-8").read())

F.ket_thuc("ATTP")
