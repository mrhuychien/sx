"""W42 (D171) — thư viện tài liệu: BM.01.01 đề nghị, đợt ban hành, xác nhận đã đọc, BM.01.02 / 01.03 / 01.13.

Vì sao phải có bài này:
  · Ban hành sai là cả xưởng dùng nhầm bản: bản cũ phải vào lịch sử (tra được), bản mới thành Hiện hành, tài liệu
    hủy bỏ hết hiệu lực — và bản Hiện hành KHÔNG sửa tay được (kể cả Desk), chỉ đổi qua ban hành.
  · Người đề nghị tự duyệt là mất ý nghĩa BM.01.01; ký điện tử phải ghi người + giờ + chức danh, khóa sau ký (C23).
  · "Đã đọc, hiểu" thay chữ ký nhận tài liệu giấy (C28): chỉ bấm được sau khi mở tệp, đúng người thuộc nơi nhận,
    đã xác nhận thì không sửa / xóa.
  · Người không thuộc nơi nhận không xem, không tải được tệp (C27) — tệp là tệp riêng tư.
  · Nạp bộ tài liệu 21/9/2026 (79 + 21 tài liệu, Phụ lục 3) chạy lại không nhân đôi, không đè chỗ Ban ISO đã sửa.
  · Đầu trang in chung lấy mã / lần BH từ thư viện, kể cả mã biểu mẫu nằm trong tài liệu khác (BM.08.05 → HD.08.02).

Nạp sx/qc/tai_lieu.py, mau_in.py, controller, sx/api/qc_tailieu.py THẬT trên frappe giả; seed thật ở
scripts/du_lieu/ (bản chép seed_tai_lieu*.json, seed_phan_phoi.json của gói giao việc 09/10/2026).
Chạy: python3 scripts/test-tailieu.py   (verify.sh gọi sẵn)
"""

import base64
import json
import os
import re
import sys
import tempfile
import types
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

FR = F.cai()
Q = F.nap_qc()
TL = sys.modules["sx.qc.tai_lieu"]
NH = sys.modules["sx.qc.nhac"]
for g in ("sx.config",):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m
R = F.nap("sx.config.roles", "sx/config/roles.py")
HS = F.nap("sx.qc.ho_so", "sx/qc/ho_so.py")
MI = F.nap("sx.qc.mau_in", "sx/qc/mau_in.py")
C_TL = F.nap("c_tl", "sx/qc/doctype/sx_tai_lieu/sx_tai_lieu.py")
C_DN = F.nap("c_dn", "sx/qc/doctype/sx_de_nghi_tai_lieu/sx_de_nghi_tai_lieu.py")
C_DOT = F.nap("c_dot", "sx/qc/doctype/sx_dot_ban_hanh/sx_dot_ban_hanh.py")
C_DOC = F.nap("c_doc", "sx/qc/doctype/sx_tai_lieu_doc/sx_tai_lieu_doc.py")
C_NN = F.nap("c_nn", "sx/qc/doctype/sx_noi_nhan/sx_noi_nhan.py")
C_HS = F.nap("c_hs", "sx/qc/doctype/sx_ho_so_danh_muc/sx_ho_so_danh_muc.py")
A = F.nap("sx.api.qc_tailieu", "sx/api/qc_tailieu.py")
F.dang_ky(TL.PT, C_TL.SXTaiLieu)
F.dang_ky(TL.PT_DN, C_DN.SXDeNghiTaiLieu)
F.dang_ky(TL.PT_DOT, C_DOT.SXDotBanHanh)
F.dang_ky(TL.PT_DOC, C_DOC.SXTaiLieuDoc)
F.dang_ky(TL.PT_NN, C_NN.SXNoiNhan, ten_theo="ten")
F.dang_ky(HS.PT, C_HS.SXHoSoDanhMuc)
for cha, o, con in ((TL.PT, "phan_phoi", "SX Tai Lieu Noi Nhan"), (TL.PT, "ma_bieu_mau", "SX Tai Lieu Bieu Mau"),
                    (TL.PT, "tep_kem", "SX Tai Lieu Tep"), (TL.PT, "lich_su", "SX Tai Lieu Lan"),
                    (TL.PT_NN, "vai", "SX Noi Nhan Vai"), (TL.PT_DOT, "ds", "SX Dot Ban Hanh Muc"),
                    (TL.PT_DOT, "ho_so", "SX Tai Lieu Tep")):
    F.bang_con(cha, o, con)
kiem, thu = F.kiem, F.thu
TMP = tempfile.mkdtemp()


class TepGia(F.Document):
    """File của frappe: lưu nội dung ra đĩa, có file_url riêng tư."""

    def before_insert(self):
        ten = f"{F.SO['n']}-{self.file_name}"
        with open(os.path.join(TMP, ten), "wb") as fh:
            fh.write(self.content)
        self.file_url = f"/private/files/{ten}"
        self.content = None

    def get_full_path(self):
        return os.path.join(TMP, self.file_url.rsplit("/", 1)[-1])


F.dang_ky("File", TepGia)
FR.local = types.SimpleNamespace(response=types.SimpleNamespace())
PDF = base64.b64encode(b"%PDF-1.4 ban da ky").decode()
PNG = base64.b64encode(b"\x89PNG anh so do").decode()
F.dat_ngay("2026-10-09")

# Người dùng, vai
NGUOI = {"qc@x": ("Nguyễn Thị QC", ["SX QC"]), "goi@x": ("Lê QC Gói", ["SX QC Packing"]),
         "iso@x": ("Nguyễn Huy Chiến", ["ISO Manager"]), "gd@x": ("Giám Đốc", ["SX Quan Ly"]),
         "ql@x": ("Trần QLSX", ["Production Manager"]), "cd@x": ("Phạm Cơ Điện", ["SX Co Dien"]),
         "hc@x": ("Hoàng Hành Chính", ["SX Hanh Chinh"]), "gs@x": ("Vũ Ghi Sổ", ["SX Ghi So"]),
         "mh@x": ("Đỗ Mua Hàng", ["Purchase User"]), "nghi@x": ("Người Đã Nghỉ", ["SX QC"])}
for u, (ten, vs) in NGUOI.items():
    F.bang("User")[u] = {"name": u, "full_name": ten, "enabled": 0 if u == "nghi@x" else 1}
    for v in vs:
        F.bang("Has Role")[f"{u}-{v}"] = {"name": f"{u}-{v}", "parent": u, "parenttype": "User", "role": v}
for r in set(R.VAI_MAC_DINH):
    F.bang("Role")[r] = {"name": r}


def la(u):
    F.NGUOI["u"], F.NGUOI["roles"] = u, list(NGUOI[u][1])


def seed(f):
    return json.load(open(f"scripts/du_lieu/{f}", encoding="utf-8"))


SEED = {"tai_lieu": seed("seed_tai_lieu.json"), "ngoai": seed("seed_tai_lieu_ngoai.json"),
        "phan_phoi": seed("seed_phan_phoi.json")}

# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- chuẩn hoá sổ đăng ký, phân phối, quyền xem (hàm thuần) --")
kiem("loại: 'Biểu mẫu/Danh mục' → Biểu mẫu, 'Quy trình + biểu mẫu' → Quy trình, 'Kế hoạch HACCP' giữ, "
     "'Tài liệu PCCC' → Khác",
     (TL.chuan_loai("Biểu mẫu/Danh mục"), TL.chuan_loai("Quy trình + biểu mẫu"), TL.chuan_loai("Kế hoạch HACCP"),
      TL.chuan_loai("Hướng dẫn + biểu mẫu"), TL.chuan_loai("Tài liệu PCCC"), TL.chuan_loai("Tài liệu"))
     == ("Biểu mẫu", "Quy trình", "Kế hoạch HACCP", "Hướng dẫn", "Khác", "Khác"))
kiem("ngày d/m/yyyy; '—' là trống; mã tài liệu bên ngoài = số hiệu trước dấu ';'",
     TL.ngay_seed("21/9/2026") == "2026-09-21" and TL.ngay_seed("08/08/2017") == "2017-08-08"
     and TL.ngay_seed("—") is None and TL.lan_seed("—") == "" and TL.ma_ngoai("QCVN 01-1:2024/BYT; Bộ Y tế")
     == "QCVN 01-1:2024/BYT" and TL.ten_noi_nhan("Ban ISO (bản gốc)") == "Ban ISO")
KH = TL.ke_hoach_nap(SEED["tai_lieu"], SEED["ngoai"], SEED["phan_phoi"])
noi = [x for x in KH["tai_lieu"] if x["nguon"] == TL.NOI_BO]
kiem("kế hoạch nạp: 79 tài liệu sổ đăng ký + PLK, BCSX (biểu mẫu trên phần mềm, C25) + 21 bên ngoài; 3 ảnh; 1 đợt;"
     " 4 hồ sơ đợt; 1 hồ sơ; 10 nơi nhận; không lỗi",
     (len(noi), len(KH["tai_lieu"]) - len(noi), len(KH["anh"]), bool(KH["dot"]), len(KH["ho_so_dot"]), len(KH["ho_so"]),
      len(KH["noi_nhan"]), KH["loi"]) == (81, 21, 3, True, 4, 1, 10, []),
     (len(noi), len(KH["anh"]), KH["loi"]))
kiem("PLK, BCSX: loại 'Biểu mẫu trên phần mềm', trỏ màn app #/ghiso",
     [(x["loai"], TL.man_app(x)) for x in noi if x["ma"] in ("PLK", "BCSX")] == [(TL.BM_PM, "#/ghiso")] * 2)
pp = KH["phan_phoi"]
kiem("Phụ lục 3: mã biểu mẫu kèm (BM.08.05 → HD.08.02), 'stt:9' (sơ đồ tổ chức, không mã), '*' (toàn bộ)",
     "QC" in pp["HD.08.02"] and "Hành chính – Văn thư" in pp["stt:9"] and "Toàn bộ người lao động" in pp["CS.ATTP"]
     and all("Ban ISO" in v for v in pp.values()) and "QC" not in pp["QT.06"], pp["HD.08.02"])
nn_seed = {x["ten"]: x for x in KH["noi_nhan"]}
kiem("nơi nhận: Ban ISO (bản gốc) → 'Ban ISO', hình thức 'Bản gốc + bản mềm'; toàn bộ người lao động = mọi tài khoản",
     nn_seed["Ban ISO"]["hinh_thuc"] == "Bản gốc + bản mềm" and nn_seed["Toàn bộ người lao động"]["moi_nguoi"] == 1
     and nn_seed["Cơ điện"]["vai"] == ["SX Co Dien"])
ngoai = [x for x in KH["tai_lieu"] if x["nguon"] == TL.BEN_NGOAI]
kiem("tài liệu bên ngoài: nhóm A/B/C như BM.01.03, soát xét = ngày cập nhật danh mục 21/9/2026; bộ phận quản lý "
     "là nơi nhận (Hành chính giữ luật PCCC)",
     sorted({x["nhom_thu_muc"][:2] for x in ngoai}) == ["A.", "B.", "C."]
     and {x["ngay_soat_xet"] for x in ngoai} == {"2026-09-21"}
     and "Hành chính – Văn thư" in pp["55/2024/QH15"], sorted({x["nhom_thu_muc"] for x in ngoai}))
DS_NN = [{"ten": "QC", "vai": ["SX QC", "SX QC Packing"]}, {"ten": "Toàn bộ", "vai": [], "moi_nguoi": 1},
         {"ten": "Cơ điện", "vai": ["SX Co Dien"]}]
kiem("nơi nhận của tôi theo role; 'mọi tài khoản' gồm cả người không có vai riêng",
     TL.noi_nhan_cua({"SX QC"}, DS_NN) == {"QC", "Toàn bộ"} and TL.noi_nhan_cua({"SX Ghi So"}, DS_NN) == {"Toàn bộ"})
kiem("quyền xem (C27): ISO thấy cả bản hết hiệu lực; người thường chỉ Hiện hành phân phối cho mình",
     TL.duoc_xem({"trang_thai": TL.HET, "phan_phoi": []}, set(), True)
     and TL.duoc_xem({"trang_thai": TL.HIEN_HANH, "phan_phoi": ["QC"]}, {"QC"}, False)
     and not TL.duoc_xem({"trang_thai": TL.HET, "phan_phoi": ["QC"]}, {"QC"}, False)
     and not TL.duoc_xem({"trang_thai": TL.HIEN_HANH, "phan_phoi": ["Cơ điện"]}, {"QC"}, False))
kiem("người phải đọc: role của nơi nhận; 'mọi tài khoản' = mọi tài khoản app; bỏ Administrator",
     TL.nguoi_nhan(["QC"], DS_NN, {"SX QC": {"a", "Administrator"}, "SX QC Packing": {"b"}}, {"z"}) == {"a", "b"}
     and TL.nguoi_nhan(["Toàn bộ"], DS_NN, {}, {"x", "y"}) == {"x", "y"})
kiem("đề nghị: gửi → chờ xem xét → chờ duyệt → đã duyệt; trả lại; đã duyệt không hủy, không duyệt thẳng từ nháp",
     TL.chuyen(TL.NHAP, "gui") == TL.CHO_XET and TL.chuyen(TL.CHO_XET, "xem_xet") == TL.CHO_DUYET
     and TL.chuyen(TL.CHO_DUYET, "duyet") == TL.DA_DUYET and TL.chuyen(TL.CHO_DUYET, "tra_lai") == TL.TRA_LAI
     and TL.chuyen(TL.TRA_LAI, "gui") == TL.CHO_XET and TL.chuyen(TL.DA_DUYET, "huy") is None
     and TL.chuyen(TL.NHAP, "duyet") is None)

# ═══ 2. Nạp bộ tài liệu ═══════════════════════════════════════════════════
print("\n-- nạp bộ tài liệu 21/9/2026: hai lần ra cùng kết quả --")
la("qc@x")
kiem("QC không nạp bộ được", "Nạp bộ" in (thu(lambda: A.nap_bo(json.dumps(SEED))) or ""))
la("iso@x")
r1 = A.nap_bo(json.dumps(SEED))
dem = lambda dt: len(F.bang(dt))  # noqa: E731
kiem("lần 1: 81 nội bộ + 21 bên ngoài, 10 nơi nhận, 1 đợt Đã ban hành, 4 hồ sơ đợt, 1 hồ sơ danh mục; mọi tài liệu "
     "được phân phối",
     (r1["tao"]["tai_lieu"], r1["tao"]["ngoai"], r1["tao"]["noi_nhan"], r1["tao"]["dot"], r1["tao"]["ho_so_dot"],
      r1["tao"]["ho_so"], r1["tao"]["phan_phoi"]) == (81, 21, 10, 1, 4, 1, 102), r1["tao"])
anh = {x["ma"]: x for x in F.bang(TL.PT).values()}
kiem("tài liệu Hiện hành, mã chuẩn, biểu mẫu kèm, ngày, lần BH; ảnh sơ đồ vào tệp kèm SĐ.02 (2), SĐ.03 (1)",
     anh["BM.08.01"]["trang_thai"] == TL.HIEN_HANH and [b["ma"] for b in anh["BM.08.01"]["ma_bieu_mau"]]
     == ["BM.08.01", "BM.08.02"] and anh["HD.08.02"]["ma_bieu_mau"][0]["man_app"] == "#/qc/vaiu"
     and str(anh["QT.08"]["ngay_hieu_luc"]) == "2026-09-22" and anh["QT.08"]["lan_ban_hanh"] == "02"
     and len(anh["SĐ.02"]["tep_kem"]) == 2 and len(anh["SĐ.03"]["tep_kem"]) == 1)
dot0 = next(iter(F.bang(TL.PT_DOT).values()))
kiem("đợt 21/9/2026: Đã ban hành, hiệu lực 22/9, chưa có số QĐ, 68 tài liệu ngày 21/9, hành động theo sổ; "
     "không tạo yêu cầu đọc (đã phổ biến giấy 22/9)",
     dot0["trang_thai"] == TL.DA_BAN_HANH and str(dot0["ngay_hieu_luc"]) == "2026-09-22" and not dot0.get("so_quyet_dinh")
     and len(dot0["ds"]) == 68 and dem(TL.PT_DOC) == 0
     and {m["hanh_dong"] for m in dot0["ds"]} == {TL.BH_MOI, TL.BH_SUA, TL.BH_LAI}, len(dot0["ds"]))
kiem("tài liệu của đợt trỏ về đợt; tài liệu 'Giữ nguyên' (08/08/2017) không trong đợt",
     anh["QT.08"]["dot_ban_hanh"] == dot0["name"] and not anh["BM.01.05"].get("dot_ban_hanh"))
hs = [x for x in F.bang(HS.PT).values() if x["ma"] == A.MA_NAP_HS]
kiem("hồ sơ vận hành trước audit 17/9 → danh mục hồ sơ (tệp đính kèm, Hệ thống quản lý)",
     len(hs) == 1 and hs[0]["nguon"] == HS.TEP and hs[0]["nhom"] == "Hệ thống quản lý")
can = r1["can_tep"]
kiem("cần 85 tệp (81 PDF tài liệu + 3 ảnh + QĐ + 4 hồ sơ đợt + 1 hồ sơ … trừ PLK / BCSX không tệp), chưa tệp nào có",
     len(can) == 79 + 3 + 1 + 4 + 1 and not any(x["co"] for x in can), len(can))
# Ban ISO sửa phân phối một tài liệu, rồi lỡ nạp lại
ten_qt06 = anh["QT.06"]["name"]
la("iso@x")
A.luu_tai_lieu(json.dumps({"name": ten_qt06, "phan_phoi": ["Ban ISO", "Cơ điện"]}))
truoc = {dt: dem(dt) for dt in (TL.PT, TL.PT_NN, TL.PT_DOT, HS.PT, "SX Tai Lieu Tep", "SX Tai Lieu Noi Nhan")}
r2 = A.nap_bo(json.dumps(SEED))
kiem("lần 2: không tạo thêm gì, không đè phân phối Ban ISO đã sửa",
     {dt: dem(dt) for dt in truoc} == truoc and not any(r2["tao"][k] for k in ("tai_lieu", "ngoai", "noi_nhan", "dot"))
     and [r["noi_nhan"] for r in F.bang(TL.PT)[ten_qt06]["phan_phoi"]] == ["Ban ISO", "Cơ điện"], r2["tao"])
# tải tệp
qd = next(x for x in can if x["khoa"].startswith("qd:"))
hd0801 = next(x for x in can if x["tep"].startswith("HD.08.01"))
kiem("tải tệp: sai tên (tệp khác) → từ chối; sai chữ ký đầu tệp → từ chối",
     "không phải tệp" in (thu(lambda: A.nap_tep(hd0801["khoa"], "Khac.pdf", PDF)) or "")
     and "không khớp" in (thu(lambda: A.nap_tep(hd0801["khoa"], hd0801["tep"], PNG)) or ""))
for x in can:
    A.nap_tep(x["khoa"], x["tep"], PNG if x["tep"].endswith(".png") else PDF)
r3 = A.nap_bo(json.dumps(SEED))
kiem("đủ tệp: chạy lại báo mọi tệp đã có (chạy lại thì bỏ qua cái đã có)", all(x["co"] for x in r3["can_tep"])
     and len(r3["can_tep"]) == len(can))
kiem("QĐ đợt vào ô QĐ đã ký (đợt đã ban hành vẫn nhận tệp nạp); ảnh vào tệp kèm",
     F.bang(TL.PT_DOT)[dot0["name"]]["tep_qd"] and all(r.get("tep") for r in F.bang(TL.PT)[anh["SĐ.02"]["name"]]["tep_kem"]))

# ═══ 3. Đầu trang in chung ════════════════════════════════════════════════
print("\n-- đầu trang in chung: mã, lần BH từ thư viện --")
kiem("mã tài liệu: lần BH, ngày BH của bản Hiện hành", (lambda d: (d["lan_ban_hanh"], d["ngay_ban_hanh"], d["kem"]))(
    MI.sx_dau_trang("BM.08.04", "Phiếu kiểm tra xuất xưởng")) == ("01", "21/09/2026", ""))
kiem("mã biểu mẫu kèm: BM.08.05 → lần BH của HD.08.02, ghi 'kèm HD.08.02'",
     (lambda d: (d["lan_ban_hanh"], d["kem"]))(MI.sx_dau_trang("BM.08.05", "Sổ giặt vải ủ")) == ("01", "HD.08.02"))
kiem("không có trong thư viện: trả mã, tên truyền vào, lần BH trống; tên công ty mặc định / theo Setting",
     MI.sx_dau_trang("BM.99.99", "Lạ")["lan_ban_hanh"] == "" and MI.sx_dau_trang("BM.99.99", "Lạ")["ma"] == "BM.99.99"
     and MI.sx_dau_trang("X")["cong_ty"] == "CÔNG TY CỔ PHẦN HOÀNG GIANG")
F.CAI_DAT["ten_cong_ty"] = "CÔNG TY CP HOÀNG GIANG (thử)"
kiem("… tên công ty sửa ở SX QC Setting", MI.sx_dau_trang("X")["cong_ty"] == "CÔNG TY CP HOÀNG GIANG (thử)")
F.CAI_DAT.pop("ten_cong_ty")
if F.jinja2:
    h = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", Q.in_so_luu_mau("2026-10")))
    kiem("bản in thật (SLM) đọc lần BH, ngày BH từ thư viện", "SLM Lần BH: 02 Ngày BH: 21/09/2026" in h, h[:300])

# ═══ 4. Quyền xem, mở tệp, đã đọc ═════════════════════════════════════════
print("\n-- quyền xem, tải tệp, đã đọc --")
la("qc@x")
d_qc = A.ds()
ma_qc = {x["ma"] for x in d_qc["ds"]}
kiem("QC thấy đúng tài liệu phân phối cho QC (HD.08.01, BM.08.01…) + Chính sách ATTP; không thấy QT.06",
     {"HD.08.01", "BM.08.01", "HD.08.02", "CS.ATTP", "SĐ.02"} <= ma_qc and "QT.06" not in ma_qc
     and "MT.ATTP" not in ma_qc and d_qc["cua_toi"] == ["QC", "Toàn bộ người lao động"], sorted(ma_qc)[:6])
kiem("không lộ đường dẫn tệp riêng tư cho người thường; có cờ có tệp; biểu mẫu → màn ghi app",
     all("tep" not in x for x in d_qc["ds"]) and next(x for x in d_qc["ds"] if x["ma"] == "HD.08.02")["co_tep"]
     and next(x for x in d_qc["ds"] if x["ma"] == "BM.08.01")["man_app"] == "#/qc")
la("gs@x")
kiem("Ghi sổ (không có trong Phụ lục 3): chỉ Chính sách ATTP (niêm yết, toàn bộ người lao động)",
     [x["ma"] for x in A.ds()["ds"]] == ["CS.ATTP"])
kiem("… không tải được tệp HD.08.01 (không thuộc nơi nhận)",
     "không phân phối" in (thu(lambda: A.tai_tep(anh["HD.08.01"]["name"])) or ""))
la("mh@x")
kiem("Mua hàng (role chuẩn Purchase User): QT.07, BM.07.01, BM.07.02, HD.07.01 + Chính sách",
     sorted(x["ma"] for x in A.ds()["ds"]) == ["BM.07.01", "BM.07.02", "CS.ATTP", "HD.07.01", "QT.07"])
la("qc@x")
A.tai_tep(anh["HD.08.01"]["name"])
kiem("QC tải HD.08.01: trả nội dung PDF, mở ngay trong trình duyệt",
     FR.local.response.filecontent == b"%PDF-1.4 ban da ky" and FR.local.response.display_content_as == "inline"
     and FR.local.response.type == "download")
kiem("bản cũ (lan): chỉ Ban ISO", "chỉ Trưởng Ban ISO" in (thu(lambda: A.tai_tep(anh["HD.08.01"]["name"], lan="00")) or ""))
la("iso@x")
d_iso = A.ds(tat_ca=1)
kiem("Ban ISO 'Tất cả': mọi tài liệu (102), có ghi chú, nơi nhận",
     len(d_iso["ds"]) == 102 and d_iso["la_iso"] and len(d_iso["noi_nhan"]) == 10)

# ═══ 5. Khóa bản Hiện hành ════════════════════════════════════════════════
print("\n-- bản Hiện hành không sửa tay --")
doc = FR.get_doc(TL.PT, anh["HD.08.01"]["name"])
doc.lan_ban_hanh = "99"
kiem("đổi lần BH bằng tay (kể cả Desk) → chặn", "chỉ đổi qua Ban hành" in (thu(doc.save) or ""))
doc = FR.get_doc(TL.PT, anh["HD.08.01"]["name"])
doc.tep = "/private/files/khac.pdf"
kiem("đổi PDF bằng tay → chặn", "chỉ đổi qua Ban hành" in (thu(doc.save) or ""))
doc = FR.get_doc(TL.PT, anh["HD.08.01"]["name"])
doc.append("lich_su", {"lan_ban_hanh": "00"})
kiem("thêm dòng lịch sử bằng tay → chặn", "chỉ đổi qua Ban hành" in (thu(doc.save) or ""))
doc = FR.get_doc(TL.PT, anh["HD.08.01"]["name"])
doc.ten = "Hướng dẫn vòng kiểm QC (sửa tên)"
kiem("sửa tên, ghi chú (Trưởng Ban ISO) thì được", thu(doc.save) is None)
kiem("tài liệu mới tạo tay là Dự thảo; tạo thẳng Hiện hành → chặn",
     "Dự thảo" in (thu(lambda: FR.get_doc({"doctype": TL.PT, "ten": "Thử", "trang_thai": TL.HIEN_HANH}).insert()) or ""))
kiem("mã trùng tài liệu khác → chặn",
     "đã có" in (thu(lambda: FR.get_doc({"doctype": TL.PT, "ma": "QT.08", "ten": "Trùng"}).insert()) or ""))

# ═══ 6. Đề nghị BM.01.01 ══════════════════════════════════════════════════
print("\n-- đề nghị BM.01.01: lập, ký gửi, xem xét, duyệt, khóa --")
la("gs@x")
kiem("Ghi sổ không lập đề nghị", "chưa được lập" in (thu(lambda: A.de_nghi_luu(json.dumps(
    {"loai_yeu_cau": "Sửa đổi", "tai_lieu": anh["CS.ATTP"]["name"]}))) or ""))
la("qc@x")
dn = A.de_nghi_luu(json.dumps({"loai_yeu_cau": "Sửa đổi", "tai_lieu": anh["HD.08.01"]["name"], "lan_ban_hanh": "02",
                               "bo_phan": "QC", "noi_dung": "Bỏ đo độ ẩm nhận đỗ"}))["name"]
x = F.bang(TL.PT_DN)[dn]
kiem("QC lập đề nghị sửa đổi: Nháp, người yêu cầu + họ tên, tên / mã lấy theo tài liệu",
     x["trang_thai"] == TL.NHAP and x["nguoi_de_nghi"] == "qc@x" and x["ho_ten_de_nghi"] == "Nguyễn Thị QC"
     and x["ma_de_xuat"] == "HD.08.01" and x["ten_de_xuat"].startswith("Hướng dẫn"))
kiem("gửi thiếu lý do → chặn", "lý do" in (thu(lambda: A.de_nghi_gui(dn)) or ""))
A.de_nghi_luu(json.dumps({"name": dn, "ly_do": "W40: bỏ đo độ ẩm"}))
A.de_nghi_gui(dn)
x = F.bang(TL.PT_DN)[dn]
kiem("ký gửi (C23): giờ + chức danh 'QC chế biến'; nhật ký; Chờ xem xét",
     x["trang_thai"] == TL.CHO_XET and x["chuc_danh_de_nghi"] == "QC chế biến" and x["gui_luc"]
     and "gửi đề nghị" in x["nhat_ky"])
kiem("đã gửi: không sửa nội dung (kể cả Desk)", "chỉ sửa khi" in (thu(lambda: A.de_nghi_luu(json.dumps(
    {"name": dn, "ly_do": "khác"}))) or ""))
d = FR.get_doc(TL.PT_DN, dn)
d.ly_do = "sửa trên Desk"
kiem("… sửa trên Desk cũng chặn", "chỉ sửa nội dung khi bị trả lại" in (thu(d.save) or ""))
d = FR.get_doc(TL.PT_DN, dn)
d.trang_thai = TL.DA_DUYET
kiem("đổi trạng thái trên Desk → chặn", "bằng nút" in (thu(d.save) or ""))
la("gd@x")
kiem("Giám đốc không duyệt khi Ban ISO chưa xem xét", "không duyệt được" in (thu(lambda: A.de_nghi_duyet(dn)) or ""))
la("iso@x")
kiem("Ban ISO trả lại phải ghi lý do", "lý do" in (thu(lambda: A.de_nghi_xem_xet(dn, 0, "")) or ""))
A.de_nghi_xem_xet(dn, 0, "Ghi rõ mục nào")
la("qc@x")
A.de_nghi_luu(json.dumps({"name": dn, "noi_dung": "Bỏ đo độ ẩm nhận đỗ, lạc (mục 3)"}))
A.de_nghi_gui(dn)
la("iso@x")
A.de_nghi_xem_xet(dn, 1, "Đồng ý")
x = F.bang(TL.PT_DN)[dn]
kiem("trả lại → QC sửa, gửi lại → Ban ISO đồng ý: Chờ duyệt, ký 'Trưởng Ban ISO' + giờ",
     x["trang_thai"] == TL.CHO_DUYET and x["xem_xet_chuc_danh"] == "Trưởng Ban ISO" and x["xem_xet_ten"]
     == "Nguyễn Huy Chiến" and x["nhat_ky"].count("[") == 4, x["nhat_ky"])
kiem("Ban ISO (không phải Giám đốc) không duyệt", "Giám đốc" in (thu(lambda: A.de_nghi_duyet(dn)) or ""))
la("gd@x")
A.de_nghi_duyet(dn, 1, "")
x = F.bang(TL.PT_DN)[dn]
kiem("Giám đốc duyệt: Đã duyệt, chức danh 'Giám đốc'", x["trang_thai"] == TL.DA_DUYET
     and x["duyet_chuc_danh"] == "Giám đốc" and x["duyet_boi"] == "gd@x")
kiem("đã duyệt → khóa: không hủy, không sửa", "không hủy" in (thu(lambda: A.de_nghi_huy(dn)) or "")
     and "chỉ sửa" in (thu(lambda: A.de_nghi_luu(json.dumps({"name": dn, "ly_do": "x"}))) or ""))
dn_gd = A.de_nghi_luu(json.dumps({"loai_yeu_cau": "Soạn mới", "ten_de_xuat": "Quy định dùng điện thoại trong xưởng",
                                  "ma_de_xuat": "QĐ.02", "ly_do": "Phòng vệ thực phẩm"}))["name"]
A.de_nghi_gui(dn_gd)
la("iso@x")
A.de_nghi_xem_xet(dn_gd, 1, "")
la("gd@x")
kiem("người đề nghị không tự duyệt (Giám đốc tự đề nghị)", "không tự duyệt" in (thu(lambda: A.de_nghi_duyet(dn_gd)) or ""))
F.bang("Has Role")["gd2"] = {"name": "gd2", "parent": "pgd@x", "parenttype": "User", "role": "SX Quan Ly"}
F.bang("User")["pgd@x"] = {"name": "pgd@x", "full_name": "Phó Giám Đốc", "enabled": 1}
F.NGUOI["u"], F.NGUOI["roles"] = "pgd@x", ["SX Quan Ly"]
A.de_nghi_duyet(dn_gd, 1, "")
la("cd@x")
dn_huy = A.de_nghi_luu(json.dumps({"loai_yeu_cau": "Hủy bỏ", "tai_lieu": anh["BM.06.05"]["name"],
                                   "ly_do": "Thay bằng sổ trên app (W43)"}))["name"]
A.de_nghi_gui(dn_huy)
la("iso@x")
A.de_nghi_xem_xet(dn_huy, 1, "")
la("gd@x")
A.de_nghi_duyet(dn_huy, 1, "")
la("qc@x")
kiem("QC chỉ thấy đề nghị của mình", [x["name"] for x in A.de_nghi_ds()["ds"]] == [dn])
if F.jinja2:
    h = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", A.in_bm0101(dn)))
    kiem("in BM.01.01: ☒ Sửa đổi, tên, mã, lý do; 'Ký trên phần mềm: Họ tên, ngày giờ' người yêu cầu, Ban ISO, "
         "Giám đốc", "☒ Sửa đổi" in h and "HD.08.01" in h and "Ký trên phần mềm: Nguyễn Thị QC, 09/10/2026 10:00" in h
         and "Ký trên phần mềm: Nguyễn Huy Chiến" in h and "Ký trên phần mềm: Giám Đốc" in h, h[:400])

# ═══ 7. Đợt ban hành ══════════════════════════════════════════════════════
print("\n-- đợt ban hành: kéo đề nghị, PDF, ban hành, lịch sử, yêu cầu đọc --")
la("qc@x")
kiem("QC không lập đợt", "Ban hành" in (thu(lambda: A.dot_luu("{}")) or ""))
la("iso@x")
dot = A.dot_luu(json.dumps({"ngay_ban_hanh": "2026-10-09", "ngay_hieu_luc": "2026-10-12"}))["name"]
r = A.dot_keo_de_nghi(dot)
d = F.bang(TL.PT_DOT)[dot]
kiem("kéo 3 đề nghị đã duyệt: Sửa đổi → 'Sửa đổi – thay thế', Soạn mới → 'Ban hành mới', Hủy bỏ → 'Hủy bỏ'; "
     "đề nghị gắn đợt",
     r["them"] == 3 and [m["hanh_dong"] for m in d["ds"]] == [TL.BH_SUA, TL.BH_MOI, TL.BH_HUY]
     and F.bang(TL.PT_DN)[dn]["dot_ban_hanh"] == dot)
kiem("kéo lần nữa không nhân đôi", A.dot_keo_de_nghi(dot)["them"] == 0)
loi = thu(lambda: A.ban_hanh(dot)) or ""
kiem("chưa ban hành được: thiếu số QĐ, QĐ scan, PDF bản mới (nói từng dòng); hủy bỏ không cần PDF",
     "số quyết định" in loi and "quyết định đã ký" in loi and "HD.08.01: thiếu PDF" in loi and "BM.06.05" not in loi,
     loi)
ds_ = [dict(m, row=m["name"]) for m in d["ds"]]
ds_[1].update(phan_phoi="QC, Xưởng sản xuất (QLSX), Không có", loai="Quy định")
A.dot_luu(json.dumps({"name": dot, "so_quyet_dinh": "15/QĐ-HG", "ds": ds_}))
for m in F.bang(TL.PT_DOT)[dot]["ds"]:
    if m["hanh_dong"] != TL.BH_HUY:
        A.dot_tep(dot, f"row:{m['name']}", "ban_moi.pdf", PDF)
kiem("tải PDF dòng: chỉ PDF", "Chỉ nhận" in (thu(lambda: A.dot_tep(dot, "qd", "qd.png", PNG)) or ""))
A.dot_tep(dot, "qd", "qd.pdf", PDF)
kiem("lưu lại đợt giữ PDF đã tải của dòng", all(m.get("tep_moi") for m in F.bang(TL.PT_DOT)[dot]["ds"]
                                                 if m["hanh_dong"] != TL.BH_HUY))
d = FR.get_doc(TL.PT_DOT, dot)
d.trang_thai = TL.DA_BAN_HANH
kiem("bấm Đã ban hành trên Desk → chặn", "BAN HÀNH" in (thu(d.save) or ""))
F.bang(TL.PT_DOC).clear()
truoc = dict(F.bang(TL.PT)[anh["HD.08.01"]["name"]])
r = A.ban_hanh(dot)
sau = F.bang(TL.PT)[anh["HD.08.01"]["name"]]
kiem("ban hành: HD.08.01 lần 02, hiệu lực 12/10, đợt mới; bản cũ (lần 01, PDF cũ) vào lịch sử, hết hiệu lực từ 12/10",
     sau["lan_ban_hanh"] == "02" and str(sau["ngay_hieu_luc"]) == "2026-10-12" and sau["dot_ban_hanh"] == dot
     and sau["lich_su"][-1]["lan_ban_hanh"] == "01" and sau["lich_su"][-1]["tep"] == truoc["tep"]
     and str(sau["lich_su"][-1]["het_hieu_luc_tu"]) == "2026-10-12" and sau["tep"] != truoc["tep"], sau["lich_su"])
huy = F.bang(TL.PT)[anh["BM.06.05"]["name"]]
kiem("Hủy bỏ → Hết hiệu lực (giữ bản cuối để tra; bản cuối vào lịch sử)",
     huy["trang_thai"] == TL.HET and huy["lan_ban_hanh"] == "01" and huy["lich_su"][-1]["het_hieu_luc_tu"]
     and huy["dot_ban_hanh"] == dot)
moi = next(x for x in F.bang(TL.PT).values() if x.get("ma") == "QĐ.02")
kiem("Ban hành mới: tạo tài liệu QĐ.02 Hiện hành, loại, nơi nhận theo dòng (bỏ tên không có), phải xác nhận đọc",
     moi["trang_thai"] == TL.HIEN_HANH and moi["loai"] == "Quy định" and moi["can_xac_nhan"] == 1
     and [x["noi_nhan"] for x in moi["phan_phoi"]] == ["QC", "Xưởng sản xuất (QLSX)"] and not moi.get("lich_su"))
dd = F.bang(TL.PT_DOT)[dot]
kiem("đợt khóa: Đã ban hành, ký người + giờ; dòng mới trỏ tài liệu vừa tạo",
     dd["trang_thai"] == TL.DA_BAN_HANH and dd["ban_hanh_ten"] == "Nguyễn Huy Chiến" and dd["ban_hanh_luc"]
     and all(m.get("tai_lieu") for m in dd["ds"]))
doc_ = list(F.bang(TL.PT_DOC).values())
u_hd = sorted(x["user"] for x in doc_ if x["tai_lieu"] == anh["HD.08.01"]["name"])
kiem("yêu cầu đọc đúng theo vai: HD.08.01 → QC, QC gói, QLSX, Ban ISO, Giám đốc (không người đã nghỉ, không Ghi "
     "sổ, không Cơ điện)", u_hd == sorted(["qc@x", "goi@x", "ql@x", "iso@x", "gd@x", "pgd@x"]), u_hd)
kiem("… lần BH, đợt, họ tên, vai ghi trên yêu cầu; tài liệu hủy bỏ không có yêu cầu đọc",
     all(x["lan_ban_hanh"] == "02" and x["dot_ban_hanh"] == dot for x in doc_ if x["tai_lieu"] == anh["HD.08.01"]["name"])
     and next(x for x in doc_ if x["user"] == "qc@x")["ho_ten"] == "Nguyễn Thị QC"
     and next(x for x in doc_ if x["user"] == "qc@x")["vai"] == "QC chế biến"
     and not any(x["tai_lieu"] == huy["name"] for x in doc_) and r["yeu_cau_doc"] == len(doc_))
kiem("đợt đã ban hành: không sửa số QĐ / dòng; hồ sơ của đợt vẫn thêm được (biên bản phổ biến có chữ ký)",
     "đã ban hành" in (thu(lambda: A.dot_luu(json.dumps({"name": dot, "so_quyet_dinh": "16/QĐ-HG"}))) or "")
     and thu(lambda: A.dot_tep(dot, "hs", "bien_ban_ky.pdf", PDF)) is None
     and len(F.bang(TL.PT_DOT)[dot]["ho_so"]) == 1)

# ═══ 8. Cần đọc, mở tệp, đã đọc ═══════════════════════════════════════════
print("\n-- Cần đọc: mở tệp rồi mới xác nhận; đã xác nhận không sửa / xóa --")
la("qc@x")
cd = A.ds()["can_doc"]
kiem("QC: 'Cần đọc' HD.08.01 lần 02 và QĐ.02", sorted(x["ma"] for x in cd) == ["HD.08.01", "QĐ.02"]
     and all(not x["mo_luc"] for x in cd), cd)
kiem("chưa mở tệp → không bấm Đã đọc được", "Mở tài liệu" in (thu(lambda: A.da_doc(anh["HD.08.01"]["name"])) or ""))
r = A.mo(anh["HD.08.01"]["name"])
kiem("mở tệp: ghi giờ mở lần đầu, trả đường tải tai_tep", r["url"].startswith("/api/method/sx.api.qc_tailieu.tai_tep?name=")
     and next(x for x in F.bang(TL.PT_DOC).values() if x["user"] == "qc@x" and x["ma"] == "HD.08.01")["mo_luc"])
A.da_doc(anh["HD.08.01"]["name"])
row = next(x for x in F.bang(TL.PT_DOC).values() if x["user"] == "qc@x" and x["ma"] == "HD.08.01")
kiem("Đã đọc, hiểu: ghi giờ; hết khỏi 'Cần đọc'", row["doc_luc"] and [x["ma"] for x in A.ds()["can_doc"]] == ["QĐ.02"])
dr = FR.get_doc(TL.PT_DOC, row["name"])
dr.doc_luc = None
kiem("đã xác nhận: không sửa (kể cả Desk)", "không sửa" in (thu(dr.save) or ""))
kiem("… không xóa", "Không xóa" in (thu(lambda: FR.delete_doc(TL.PT_DOC, row["name"])) or ""))
la("gs@x")
kiem("người không có yêu cầu đọc bấm Đã đọc → báo", "không có yêu cầu" in (thu(lambda: A.da_doc(anh["CS.ATTP"]["name"])) or ""))
la("iso@x")
td = A.tien_do_doc(dot)
kiem("tiến độ đọc của đợt: 1 lượt đã đọc, danh sách người chưa đọc kèm tài liệu",
     td["da"] == 1 and td["tong"] == len(doc_) and any(x["user"] == "qc@x" and x["chua"] == ["QĐ.02"]
                                                       for x in td["chua_doc"]), td["chua_doc"][:2])
# Sửa đổi tiếp HD.08.01 khi người khác chưa đọc lần 02 → yêu cầu cũ chưa xác nhận bỏ đi, xác nhận cũ giữ
la("qc@x")
dn3 = A.de_nghi_luu(json.dumps({"loai_yeu_cau": "Sửa đổi", "tai_lieu": anh["HD.08.01"]["name"], "lan_ban_hanh": "03",
                                "ly_do": "sửa tiếp"}))["name"]
A.de_nghi_gui(dn3)
la("iso@x")
A.de_nghi_xem_xet(dn3, 1, "")
la("gd@x")
A.de_nghi_duyet(dn3, 1, "")
la("iso@x")
dot2 = A.dot_luu(json.dumps({"ngay_ban_hanh": "2026-10-20", "ngay_hieu_luc": "2026-10-21", "so_quyet_dinh": "20/QĐ-HG"}))["name"]
A.dot_keo_de_nghi(dot2)
A.dot_tep(dot2, f"row:{F.bang(TL.PT_DOT)[dot2]['ds'][0]['name']}", "lan3.pdf", PDF)
A.dot_tep(dot2, "qd", "qd2.pdf", PDF)
A.ban_hanh(dot2)
hd = [x for x in F.bang(TL.PT_DOC).values() if x["tai_lieu"] == anh["HD.08.01"]["name"]]
kiem("lần 03: yêu cầu lần 02 chưa xác nhận bỏ đi; xác nhận lần 02 của QC giữ; mỗi người một yêu cầu lần 03",
     not [x for x in hd if x["lan_ban_hanh"] == "02" and not x.get("doc_luc")]
     and [x["user"] for x in hd if x["lan_ban_hanh"] == "02"] == ["qc@x"]
     and len([x for x in hd if x["lan_ban_hanh"] == "03"]) == len(u_hd)
     and len(F.bang(TL.PT)[anh["HD.08.01"]["name"]]["lich_su"]) == 2)

# ═══ 9. Bản in, nhắc, danh mục hồ sơ ══════════════════════════════════════
print("\n-- BM.01.02, BM.01.03, BM.01.13, nhắc, danh mục hồ sơ --")
if F.jinja2:
    h = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", A.in_bm0102()))
    kiem("BM.01.02: đầu trang, nhóm, mã, lần BH, ngày, nơi phân phối; Hết hiệu lực tách riêng; PLK trên phần mềm",
         "Danh mục tài liệu nội bộ" in h and "QT.08 Quản lý sản xuất" in h and "HD.08.01 03" in h
         and "BM.06.05" in h.split("Tài liệu đã hết hiệu lực")[1] and "BM.06.05" not in h.split("Tài liệu đã hết hiệu lực")[0]
         and "(biểu mẫu trên phần mềm)" in h, h[:300])
    h = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", A.in_bm0103()))
    kiem("BM.01.03: nhóm A/B/C, số hiệu cơ quan, dẫn chiếu, bộ phận; dòng soát xét",
         "A. TIÊU CHUẨN, HƯỚNG DẪN" in h and "QCVN 01-1:2024/BYT; Bộ Y tế" in h and "Hành chính – Văn thư" in h
         and "Lần soát xét gần nhất: 21/09/2026" in h, h[:300])
    h = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", A.in_bm0113(dot)))
    kiem("BM.01.13: QĐ, ngày áp dụng, tài liệu + nội dung chính; người đọc trên phần mềm có giờ, người chưa đọc ô ký "
         "tay; danh sách phân phối theo nơi nhận, hình thức",
         "15/QĐ-HG" in h and "12/10/2026" in h and "Đã đọc trên phần mềm lúc 10:00 ngày 09/10/2026" in h
         and "Ký: ……" in h and "Xưởng sản xuất (QLSX) Bản giấy" in h, h[:500])
F.dat_ngay("2026-10-20")
nh = TL.nhac("2026-10-20")
kiem("nhắc: đợt quá 7 ngày còn người chưa đọc (theo đợt, đếm người chưa đọc / tổng); đợt 21/9 (không yêu cầu đọc) "
     "không nhắc",
     [(x["dot"], x["chua"], x["tong"]) for x in nh["chua_doc"]] == [(dot, 3, 4), (dot2, 6, 6)], nh["chua_doc"])
F.dat_ngay("2026-10-15")
kiem("… chưa quá 7 ngày thì chưa nhắc", TL.nhac("2026-10-15")["chua_doc"] == [])
F.dat_ngay("2027-10-01")
kiem("nhắc: tài liệu bên ngoài quá 12 tháng chưa soát xét → cả 21", len(TL.nhac("2027-10-01")["soat_xet"]) == 21)
A.soat_xet()
kiem("Ban ISO bấm đã soát xét → hết nhắc", TL.nhac("2027-10-01")["soat_xet"] == [])
la("ql@x")
dn4 = A.de_nghi_luu(json.dumps({"loai_yeu_cau": "Sửa đổi", "tai_lieu": anh["QT.08"]["name"], "ly_do": "x"}))["name"]
A.de_nghi_gui(dn4)
F.dat_ngay("2027-10-09")
kiem("nhắc: đề nghị chờ xem xét quá 7 ngày", [x["name"] for x in TL.nhac("2027-10-09")["de_nghi"]] == [dn4])
la("iso@x")
dot3 = A.dot_luu(json.dumps({"ds": [{"tai_lieu": anh["QT.08"]["name"], "hanh_dong": TL.BH_SUA}]}))["name"]
kiem("nhắc: đợt nháp có dòng thiếu PDF", TL.nhac("2027-10-09")["dot_thieu"] == [{"dot": dot3, "thieu": 1}])
ds_nh = NH.tinh(F.hom_nay(), [], [], {}, tai_lieu=TL.nhac(F.hom_nay()))
tl_nh = [x for x in ds_nh if x["nhom"] == "tai_lieu"]
kiem("hộp nhắc mảng 'tai_lieu': 2 đợt chưa đọc, đề nghị chờ, đợt thiếu PDF — route #/tailieu…",
     len(tl_nh) == 4 and all(x["route"].startswith("#/tailieu") for x in tl_nh)
     and tl_nh[0]["route"] == f"#/tailieu/dot/{dot}", [x["tieu_de"] for x in tl_nh])
kiem("BIEU_MAU danh mục hồ sơ có BM.01.02 / 01.03 / 01.13 → mảng tai_lieu; Select khớp",
     all(HS.BIEU_MAU[m][1] == "tai_lieu" for m in ("BM.01.02", "BM.01.03", "BM.01.13"))
     and all(m in json.dumps(json.load(open("sx/qc/doctype/sx_ho_so_danh_muc/sx_ho_so_danh_muc.json",
                                            encoding="utf-8")), ensure_ascii=False)
             for m in ("BM.01.02", "BM.01.03", "BM.01.13")))
P = F.nap("sx.patches.d171_thu_vien_tai_lieu", "sx/patches/d171_thu_vien_tai_lieu.py")
P.execute()
P.execute()
kiem("patch d171: 3 dòng hồ sơ app lập, chạy lại không nhân đôi; có trong patches.txt",
     sorted(x["ma"] for x in F.bang(HS.PT).values() if x.get("nguon") == HS.APP) == ["BM.01.02", "BM.01.03", "BM.01.13"]
     and "sx.patches.d171_thu_vien_tai_lieu" in open("sx/patches.txt", encoding="utf-8").read())

# ═══ 10. Màn hình, cấu hình ═══════════════════════════════════════════════
print("\n-- dây nối màn hình --")
sh = open("sx/public/sx/shell.js", encoding="utf-8").read()
kiem("shell: view tailieu, tab 📚 Tài liệu, route con #/tailieu/…",
     "tailieu: '/assets/sx/sx/views/tailieu.js'" in sh and "registerPrefix('#/tailieu/'" in sh
     and "label: 'Tài liệu'" in sh)
kiem("lối vào từ tab Xem xét của QC", "['tailieu', 'Tài liệu']" in open("sx/public/sx/components/qcui.js",
                                                                     encoding="utf-8").read())
kiem("hooks: hàm Jinja sx_dau_trang cho đầu trang in chung",
     '"sx.qc.mau_in.sx_dau_trang"' in open("sx/hooks.py", encoding="utf-8").read())
mau = [f for f in os.listdir("sx/qc") if f.endswith(".html") and not f.startswith("_")]
thieu = [f for f in mau if 'import dau_trang' not in open(f"sx/qc/{f}", encoding="utf-8").read()]
kiem("mọi mẫu in sx/qc/*.html + diễn tập dùng đầu trang chung", not thieu and 'import dau_trang' in open(
    "sx/sx/doctype/sx_dien_tap_truy_xuat/dien_tap.html", encoding="utf-8").read(), thieu)

F.ket_thuc("TAILIEU")
