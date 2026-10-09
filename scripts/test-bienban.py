"""W45 (D174) — khung "Biên bản": 18 phiếu giấy là dữ liệu khai báo (SX Mau Bien Ban), lập / ký nhiều cấp / kéo dữ liệu.

Vì sao phải có bài này:
  · Ký là chữ ký điện tử (C23): ký sai thứ tự, một người ký hai ô, sửa được sau khi đủ chữ ký → biên bản mất giá trị.
  · Ô ký tay (văn bản gửi ra ngoài, có người ngoài): chưa có bản scan mà khóa → hồ sơ thiếu chữ ký thật.
  · Bản chụp số liệu: biên bản họp tuần ghi "3 sự cố" phải giữ 3 dù sau này có phiếu mới.
  · Việc giao phải thành việc định kỳ có hạn (hộp nhắc sẵn có); dòng Không phù hợp → BM.01.07 gắn ngược.
  · Đánh giá nội bộ (QT.01): chuyên gia không đánh giá bộ phận mình; Trưởng Ban ISO không làm trưởng đoàn; 01.08, 01.09
    tự gom / đếm từ checklist của đợt.
  · BM.HACCP.01 bột kéo đủ 11 công đoạn; danh sách công đoạn đổi → nhắc xác nhận lại sơ đồ.

Nạp sx/qc/bien_ban.py, controller mẫu / biên bản / việc định kỳ / khắc phục, sx/api/qc_bienban.py, patch d174 THẬT trên
frappe giả (fakefrappe); seed thật sx/qc/seed/bien_ban.json.
Chạy: python3 scripts/test-bienban.py   (verify.sh gọi sẵn)
"""

import base64
import json
import os
import sys
import tempfile
import types
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

FR = F.cai()
Q = F.nap_qc()
SO = sys.modules["sx.qc.so"]
NH = sys.modules["sx.qc.nhac"]
KP = sys.modules["sx.qc.khac_phuc"]
VD = sys.modules["sx.qc.viec_dinh_ky"]
for g in ("sx.config",):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m
F.nap("sx.config.roles", "sx/config/roles.py")
AT = F.nap("sx.qc.attp", "sx/qc/attp.py")
HS = F.nap("sx.qc.ho_so", "sx/qc/ho_so.py")
F.nap("sx.qc.bao_cao", "sx/qc/bao_cao.py")
F.nap("sx.qc.mau_in", "sx/qc/mau_in.py")
TLA = F.nap("sx.api.qc_tailieu", "sx/api/qc_tailieu.py")
BB = F.nap("sx.qc.bien_ban", "sx/qc/bien_ban.py")
A = F.nap("sx.api.qc_bienban", "sx/api/qc_bienban.py")
C_MAU = F.nap("c_mau", "sx/qc/doctype/sx_mau_bien_ban/sx_mau_bien_ban.py")
C_BB = F.nap("c_bb", "sx/qc/doctype/sx_bien_ban/sx_bien_ban.py")
C_VD = F.nap("c_vd", "sx/qc/doctype/sx_viec_dinh_ky/sx_viec_dinh_ky.py")
C_KP = F.nap("c_kp", "sx/qc/doctype/sx_khac_phuc/sx_khac_phuc.py")
C_HS = F.nap("c_hs", "sx/qc/doctype/sx_ho_so_danh_muc/sx_ho_so_danh_muc.py")
st_ = types.ModuleType("sx.setup")
st_.dam_bao_role = lambda: []
sys.modules["sx.setup"] = st_
P = F.nap("sx.patches.d174_bien_ban", "sx/patches/d174_bien_ban.py")
F.dang_ky(BB.PT, C_MAU.SXMauBienBan, ten_theo="ma")
F.dang_ky(BB.PT_BB, C_BB.SXBienBan)
F.dang_ky(VD.PT, C_VD.SXViecDinhKy)
F.dang_ky(KP.PT, C_KP.SXKhacPhuc)
F.dang_ky(HS.PT, C_HS.SXHoSoDanhMuc)
for f, con in (("phan", BB.PT_PHAN), ("ky", BB.PT_KY_MAU), ("vai_lap", BB.PT_VAI), ("vai_xem", BB.PT_VAI)):
    F.bang_con(BB.PT, f, con)
for f, con in (("ky", BB.PT_KY), ("lien_quan", BB.PT_LQ), ("viec", BB.PT_VIEC), ("tep_kem", BB.PT_TEP)):
    F.bang_con(BB.PT_BB, f, con)
F.bang_con(VD.PT, "ds_lan", "SX Viec Dinh Ky Lan")
kiem, thu = F.kiem, F.thu
TMP = tempfile.mkdtemp()


class TepGia(F.Document):
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
F.dat_ngay("2026-10-09")

NGUOI = {"iso@x": ("Nguyễn Huy Chiến", ["ISO Manager"]), "gd@x": ("Đào Văn Tiến", ["SX Quan Ly"]),
         "qc@x": ("Đào Quang Công", ["SX QC"]), "ql@x": ("Khương Thị Minh Lý", ["Production Manager"]),
         "kho@x": ("Nguyễn Thị Nga", ["SX Thu Kho"]), "hc@x": ("Hoàng Hành Chính", ["SX Hanh Chinh"]),
         "cd@x": ("Ngô Văn Trường", ["SX Co Dien"]), "bv@x": ("Vũ Bảo Vệ", ["SX Bao Ve"])}
for u, (ten, vs) in NGUOI.items():
    F.bang("User")[u] = {"name": u, "full_name": ten, "enabled": 1}
    for v in vs:
        F.bang("Has Role")[f"{u}-{v}"] = {"name": f"{u}-{v}", "parent": u, "parenttype": "User", "role": v}
for r in ("ISO Manager", "SX Quan Ly", "SX QC", "SX QC Packing", "Production Manager", "SX Thu Kho", "Warehouse",
          "SX Co Dien", "SX Hanh Chinh"):
    F.bang("Role")[r] = {"name": r}
FR.get_roles = lambda u=None: list(NGUOI[u][1]) if u and u in NGUOI else list(F.NGUOI["roles"])


def la(u):
    F.NGUOI["u"], F.NGUOI["roles"] = u, list(NGUOI[u][1])


def them(dt, **x):
    F.SO["n"] += 1
    n = x.pop("name", None) or f"{dt[:4]}-{F.SO['n']}"
    F.bang(dt)[n] = dict(x, name=n)
    return n


def pdf():
    return base64.b64encode(b"%PDF-1.4 ky tay").decode()


SEED = json.load(open("sx/qc/seed/bien_ban.json", encoding="utf-8"))
W45 = ["BM.01.11", "BM.01.10", "BM.01.05", "BM.01.06", "BM.01.08", "BM.01.09", "BM.04.01", "BM.04.02",
       "BM.HACCP.01", "BM.HACCP.02", "BM.14.01", "BM.14.02", "BM.02.01", "BM.02.02", "BM.02.03", "BM.02.05",
       "BM.03.04", "BM.PRP.02"]

# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- mẫu: seed 18 phiếu, luật định nghĩa --")
kiem("seed: đúng 18 mẫu md W45, mã duy nhất", [x["ma"] for x in SEED] == W45)
loi = {x["ma"]: BB.loi_mau(dict(x, phan=[dict(p) for p in x["phan"]])) for x in SEED}
kiem("18 mẫu seed hợp lệ (phần, cột, hàm kéo / tính có trong code, ô ký có người ký)", not any(loi.values()), loi)
kiem("mọi hàm kéo seed dùng có trong NGUON / CHON_NGUON; md nêu đủ 15 khóa",
     {p["nguon"] for x in SEED for p in x["phan"] if p.get("nguon")} <= set(BB.NGUON) | set(BB.CHON_NGUON)
     and {"su_co_ky", "khieu_nai_ky", "khac_phuc_mo", "nhac_cao", "viec_bien_ban_truoc", "bc_thang", "dgnb_ket_qua",
          "thay_doi_ky", "rui_ro_ben_quan_tam", "kiem_nghiem_nam", "cong_doan_banh", "cong_doan_bot", "oprp_banh",
          "oprp_bot", "dien_tap_truy_xuat", "lo_thu_hoi", "dong_vat_ky"} <= set(BB.NGUON))
ky_tay = {x["ma"] for x in SEED if any(s.get("ky_tay") for s in x["ky"])}
kiem("ký tay mặc định: BM.02.01, 02.02 (Giám đốc gửi ra ngoài), PRP.02 (nhà thầu); 03.04 khi có đơn vị ngoài",
     ky_tay == {"BM.02.01", "BM.02.02", "BM.PRP.02"}
     and next(x for x in SEED if x["ma"] == "BM.03.04")["ky_tay_khi"] == "co_don_vi_ngoai")
SAI = {"chu_ky_lap": "Ngày", "phan": [
    {"key": "Đầu", "kieu": "Văn bản", "cot": []},
    {"key": "a", "kieu": "Kéo dữ liệu", "nguon": "eval(x)"},
    {"key": "b", "kieu": "Việc giao", "cot": [{"key": "viec", "nhan": "V", "kieu": "Text"}]},
    {"key": "c", "kieu": "Bảng", "cot": [{"key": "k", "nhan": "K", "kieu": "Int"}], "tinh": "tong_xyz"},
    {"key": "d", "kieu": "Bảng", "cot": [{"key": "k", "nhan": "K", "kieu": "Data"}], "chi_khi": "khong_co"}],
    "ky": [{"vai_tro": "Ai đó"}]}
ls = " ".join(BB.loi_mau(SAI))
kiem("mẫu sai: chu kỳ, khóa phần có dấu, hàm kéo lạ, Việc giao thiếu cột, hàm tính lạ, 'chỉ khi' không phải ô Check, "
     "ô ký không ai ký được",
     all(x in ls for x in ("Chu kỳ lập", "Khóa phần 'Đầu'", "eval(x)", "phu_trach (User)", "tong_xyz", "chỉ khi",
                           "Ô ký Ai đó")), ls)

print("\n-- nội dung: câu in sẵn, dòng thêm, bắt buộc lúc gửi --")
m11 = next(x for x in SEED if x["ma"] == "BM.01.11")
p_nd = next(p for p in m11["phan"] if p["key"] == "noi_dung")
nd0 = BB.noi_dung_dau(m11["phan"], {"gio": "8:00"})
kiem("BM.01.11: 8 câu in sẵn a–h cố định; đầu phiếu lấy giá trị lúc lập",
     [r["ma"] for r in nd0["noi_dung"]["dong"]] == list("abcdefgh")
     and all(r["_co_dinh"] for r in nd0["noi_dung"]["dong"]) and nd0["dau"]["gia_tri"] == {"gio": "8:00"})
gui_ = [dict(r, tinh_hinh="ổn", noi_dung="SỬA CÂU") for r in nd0["noi_dung"]["dong"]]
v, e = BB.sach_phan(p_nd, {"dong": gui_}, nd0["noi_dung"])
kiem("câu in sẵn không sửa được (chữ gửi lên bị bỏ), ô trả lời lưu", not e and v["dong"][0]["noi_dung"].startswith(
    "Việc giao") and v["dong"][0]["tinh_hinh"] == "ổn", v["dong"][0])
v, e = BB.sach_phan(p_nd, {"dong": gui_[1:]}, nd0["noi_dung"])
kiem("bỏ câu in sẵn → lỗi", any("không bỏ được câu in sẵn" in x for x in e), e)
v, e = BB.sach_phan(p_nd, {"dong": gui_ + [{"tinh_hinh": "thêm"}]}, nd0["noi_dung"])
kiem("Danh sách kiểm không 'cho thêm dòng' → dòng thêm bị chặn", any("không thêm dòng" in x for x in e), e)
p_tp = next(p for p in m11["phan"] if p["key"] == "thanh_phan")
v, e = BB.sach_phan(p_tp, {"dong": [{"ho_ten": "A", "_id": "t5"}, {}, {"ho_ten": "B", "la": 1}]})
kiem("Bảng: dòng trống bỏ, id giữ, cột lạ báo lỗi", [r.get("_id") for r in v["dong"]] == ["t5", "t1"]
     and any("cột lạ la" in x for x in e), (v, e))
th = BB.thieu(m11["phan"], nd0)
kiem("gửi ký khi chưa ghi: thiếu thành phần tham dự + 8 câu chưa có tình hình, ý kiến; phần BM.01.12 chỉ khi họp đầu "
     "tháng thì không đòi", any("Thành phần tham dự: chưa có dòng" in x for x in th)
     and sum("Tình hình, ý kiến" in x for x in th) == 8)
m34 = next(x for x in SEED if x["ma"] == "BM.03.04")
nd34 = BB.noi_dung_dau(m34["phan"], {"dt1": 1})
th34 = BB.thieu(m34["phan"], nd34)
kiem("BM.03.04: chỉ chấm tiêu chí của nội dung đã tích (DT-1 → 3 dòng, DT-2/DT-3 bỏ)",
     sum("3. Đánh giá theo tiêu chí" in x and "Kết quả thực tế" in x for x in th34) == 3, th34)
m141 = next(x for x in SEED if x["ma"] == "BM.14.01")
p141 = m141["phan"][0]
v, e = BB.sach_phan(p141, {"dong": [{"doi_tuong": "X", "kieu_gian_lan": "Y", "k": "3", "a": "2", "diem": 1},
                                    {"doi_tuong": "Z", "kieu_gian_lan": "W", "k": "1"}]})
kiem("BM.14.01: Điểm = K × A do app tính (gõ tay bị tính đè); thiếu A → chưa có điểm; mức ≥ 6 cao, 3–4 TB",
     v["dong"][0]["diem"] == 6 and "diem" not in v["dong"][1] and BB.muc_kxa(6) == "cao" and BB.muc_kxa(4)
     == "trung_binh" and BB.muc_kxa(2) == "thap", v)
kiem("BM.14.01 seed: 14 dòng, đường gluco / bột nghệ chưa chấm để trống",
     len(BB.noi_dung_dau([p141])["danh_gia"]["dong"]) == 14
     and all("k" not in r for r in BB.noi_dung_dau([p141])["danh_gia"]["dong"] if r["doi_tuong"] in ("Đường gluco",
                                                                                                    "Bột nghệ")))

print("\n-- ký: thứ tự, một người một ô, ký tay --")
KY = [{"vai_tro": "Thư ký", "nguoi_lap": 1, "thu_tu": 1, "bat_buoc": 1},
      {"vai_tro": "Trưởng Ban ISO", "role": "ISO Manager", "thu_tu": 2, "bat_buoc": 1},
      {"vai_tro": "Giám đốc", "role": "SX Quan Ly", "thu_tu": 3, "bat_buoc": 1}]
s, ms = BB.o_ky_cua(KY, "iso@x", ["ISO Manager"], "qc@x")
kiem("chưa tới lượt: Trưởng Ban ISO ký trước Thư ký → chặn", s is None and "đang chờ Thư ký" in ms, ms)
s, ms = BB.o_ky_cua(KY, "kho@x", ["SX Thu Kho"], "qc@x")
kiem("người không có ô → báo không có ô ký", s is None and "không có ô ký" in ms, ms)
s, _m = BB.o_ky_cua(KY, "qc@x", ["SX QC"], "qc@x")
s.update(user="qc@x", ky_luc="2026-10-09 10:00")
s2, ms = BB.o_ky_cua(KY, "qc@x", ["SX QC", "ISO Manager"], "qc@x")
kiem("người lập ký ô Thư ký; cùng người (có cả vai ISO) không ký ô thứ hai", s is KY[0] and s2 is None
     and "không ký hai ô" in ms, ms)
kiem("chưa đủ chữ ký → chưa khóa", not BB.du_chu_ky(KY, None))
for x, u in ((KY[1], "iso@x"), (KY[2], "gd@x")):
    x.update(user=u, ky_luc="2026-10-09 11:00")
kiem("đủ ô bắt buộc → khóa được", BB.du_chu_ky(KY, None))
KT = [{"vai_tro": "Giám đốc", "role": "SX Quan Ly", "thu_tu": 1, "bat_buoc": 1, "ky_tay": 1}]
kiem("ô ký tay: không ai ký trên app; chưa có bản scan thì không khóa, có thì khóa",
     BB.o_ky_cua(KT, "gd@x", ["SX Quan Ly"], "iso@x")[0] is None and not BB.du_chu_ky(KT, None)
     and BB.du_chu_ky(KT, "/private/files/a.pdf"))
kiem("BM.03.04: tích 'có đơn vị PCCC bên ngoài' → cần bản ký tay dù mọi ô ký trên app",
     BB.can_ky_tay(KY, {"co_don_vi_ngoai": 1}, "co_don_vi_ngoai") and not BB.du_chu_ky(KY, None, {"co_don_vi_ngoai": 1},
                                                                                       "co_don_vi_ngoai"))
kiem("số biên bản theo năm: 01/BB-ISO, tiếp 03/BB-ISO; không ký hiệu → 01/2026",
     BB.so_bien_ban([], "BB-ISO", 2026) == "01/BB-ISO" and BB.so_bien_ban(["01/BB-ISO", "02/BB-ISO"], "BB-ISO", 2026)
     == "03/BB-ISO" and BB.so_bien_ban([], None, 2026) == "01/2026")
kiem("kỳ kéo dữ liệu: họp tuần không có lần trước → 7 ngày; có lần trước → từ sau lần đó",
     BB.ky_du_lieu("Tuần", "2026-10-09") == (date(2026, 10, 3), date(2026, 10, 9))
     and BB.ky_du_lieu("Tuần", "2026-10-09", "2026-09-25") == (date(2026, 9, 26), date(2026, 10, 9)))

print("\n-- đánh giá nội bộ: độc lập (QT.01), gom checklist --")
KH = {"chuyen_gia": {"dong": [
    {"chuyen_gia": "hc@x", "trach_nhiem": "Trưởng đoàn", "ky_hieu": "A", "bo_phan": "Hành chính"},
    {"chuyen_gia": "qc@x", "trach_nhiem": "Thành viên", "ky_hieu": "B", "bo_phan": "QC"},
    {"chuyen_gia": "cd@x", "trach_nhiem": "Thành viên", "ky_hieu": "C", "bo_phan": "Cơ điện"}]},
      "chi_tiet": {"dong": [{"thoi_gian": "8:30", "noi_dung": "Kho", "bo_phan": "Kho", "chuyen_gia": "A"},
                            {"thoi_gian": "8:30", "noi_dung": "QC", "bo_phan": "qc", "chuyen_gia": "B, C"}]}}
ld = BB.loi_doc_lap(KH, FR.get_roles)
kiem("chuyên gia B (QC) đánh giá bộ phận QC → chặn (so không dấu, không hoa thường)",
     len(ld) == 1 and "Chuyên gia B thuộc qc" in ld[0], ld)
KH2 = json.loads(json.dumps(KH))
KH2["chuyen_gia"]["dong"][0]["chuyen_gia"] = "iso@x"
KH2["chi_tiet"]["dong"][1]["chuyen_gia"] = "C"
kiem("Trưởng Ban ISO làm trưởng đoàn → chặn", any("không làm trưởng đoàn" in x for x in
                                                   BB.loi_doc_lap(KH2, FR.get_roles)))
KH2["chuyen_gia"]["dong"][0]["trach_nhiem"] = "Thành viên"
kiem("gửi ký phải có đúng một trưởng đoàn", any("đúng một trưởng đoàn" in x for x in
                                                 BB.loi_doc_lap(KH2, FR.get_roles, du=True)))
kiem("checklist BM.01.06: không phải chuyên gia → chặn; chuyên gia QC đánh giá QC → chặn; đánh giá Kho → được",
     "Chỉ chuyên gia" in BB.loi_checklist(KH, "kho@x", "Kho") and "không đánh giá bộ phận của mình"
     in BB.loi_checklist(KH, "qc@x", "QC") and BB.loi_checklist(KH, "qc@x", "Kho") is None)
dem, ly = BB.tong_hop_dgnb([{"bo_phan": "Kho", "dong": [{"yeu_cau": "FIFO", "ket_luan": "KPH"},
                                                       {"yeu_cau": "Nhãn", "ket_luan": "Lưu ý", "bang_chung": "mờ"}]},
                            {"bo_phan": "QC", "dong": [{"yeu_cau": "Lượt", "ket_luan": "PH"}]}])
kiem("tổng hợp: đếm KPH / Lưu ý theo bộ phận, dòng Lưu ý thành điểm lưu ý (kèm bằng chứng, trách nhiệm = bộ phận)",
     dem == {"Kho": {"kph": 1, "luu_y": 1}, "QC": {"kph": 0, "luu_y": 0}}
     and ly == [{"noi_dung": "Nhãn — mờ", "trach_nhiem": "Kho"}], (dem, ly))

print("\n-- sơ đồ công đoạn, nhắc --")
CDB = [{"ten": "1 Tiếp nhận", "thu_tu": 1}, {"ten": "2 Luộc", "thu_tu": 2}]
vt = BB.van_tay(CDB)
kiem("sơ đồ: đúng lần xác nhận → không nhắc; đổi tên / thêm → nhắc; bột chưa xác nhận → nhắc",
     BB.so_do_can_xac_nhan({"Bánh": CDB}, {"Bánh": {"ngay": "2026-09-22", "van_tay": vt}}) == []
     and BB.so_do_can_xac_nhan({"Bánh": CDB + [{"ten": "3 Rang", "thu_tu": 3}]},
                               {"Bánh": {"ngay": "2026-09-22", "van_tay": vt}})[0]["ly_do"].startswith(
         "danh sách công đoạn đổi sau lần xác nhận 22/09/2026")
     and "chưa có biên bản xác nhận" in BB.so_do_can_xac_nhan({"Bột": CDB}, {})[0]["ly_do"])
MAU_DS = [{"name": "BM.01.11", "ten": "Biên bản họp Ban ISO", "chu_ky_lap": "Tuần", "creation": "2026-09-20"}]
BBD = [{"name": "BB-1", "mau": "BM.01.11", "so": "01/BB-ISO", "ngay": "2026-09-28", "trang_thai": "Chờ ký",
        "nguoi_lap": "qc@x", "gui_luc": "2026-09-28 16:00", "ky": [dict(KY[0], user="qc@x", ky_luc="x"),
                                                                    dict(KY[1], user=None, ky_luc=None)]}]
n = BB.nhac_thuan("2026-10-09", MAU_DS, BBD, "iso@x", ["ISO Manager"])
kiem("nhắc: chờ Trưởng Ban ISO ký (của tôi), chờ ký 11 ngày > 3, họp tuần quá 7 ngày",
     n["cho_toi"][0]["vai_tro"] == "Trưởng Ban ISO" and n["cho_lau"][0]["so_ngay"] == 11
     and n["cho_lau"][0]["cho"] == "Trưởng Ban ISO" and n["den_han"][0]["so_ngay"] == 11, n)
nh = [x for x in NH.tinh("2026-10-09", [], [], {}, bien_ban=n) if x["nhom"] == "bien_ban"]
kiem("hộp nhắc mảng bien_ban: chờ bạn ký (route biên bản), chờ ký quá 3 ngày, họp Ban ISO",
     len(nh) == 3 and nh[0]["route"] == "#/qc/bienban/BB-1" and "quá 3 ngày" in nh[1]["tieu_de"]
     and "BM.01.11" in nh[2]["tieu_de"], nh)
kiem("mảng bien_ban có ở Tổng quan ATTP và mảng của sổ; 18 biểu mẫu vào danh mục hồ sơ; BM.01.07 có nguồn Thẩm tra",
     "bien_ban" in [x[0] for x in AT.LINH_VUC] and set(SO.MANG) == {x[0] for x in AT.LINH_VUC}
     and set(W45) <= set(HS.BIEU_MAU) and "Thẩm tra" in KP.NGUON
     and "Thẩm tra" in next(f for f in json.load(open("sx/qc/doctype/sx_khac_phuc/sx_khac_phuc.json"))["fields"]
                            if f["fieldname"] == "nguon")["options"])

# ═══ 2. Patch d174 ════════════════════════════════════════════════════════
print("\n-- patch d174: mẫu, việc năm, công đoạn bột, mốc sơ đồ, hồ sơ --")
for i, (ma, ten, tt) in enumerate([(str(k), f"{k} Bước {k}", k) for k in range(1, 17)]):
    F.bang("SX QC Cong Doan")[ten] = {"name": ten, "ten": ten, "day_chuyen": "Bánh", "thu_tu": tt, "ma": ma,
                                       "ngung": 0, "modified": "2026-10-01"}
F.bang("SX QC Cong Doan")["PRP"] = {"name": "PRP", "ten": "PRP", "day_chuyen": "Chung", "thu_tu": 0, "ngung": 0}
for ma, ten, tt in (("bot-tiep-nhan", "Bột: tiếp nhận", 1), ("bot-nhat-lac", "Bột: nhặt lạc", 2),
                    ("bot-rang-lac", "Bột: rang lạc", 3), ("bot-xay-duong", "Bột: xay đường", 9),
                    ("bot-tron", "Bột: trộn", 5), ("bot-dong-tui", "Bột: đóng túi", 6),
                    ("bot-dong-thung", "Bột: đóng thùng", 7)):
    F.bang("SX QC Cong Doan")[ten] = {"name": ten, "ten": ten, "day_chuyen": "Bột", "thu_tu": tt, "ma": ma,
                                       "ngung": 0}
F.dang_ky("SX QC Cong Doan", None, ten_theo="ten")
F.LOP.pop("SX QC Cong Doan", None)
P.execute()
kiem("tạo đủ 18 mẫu biên bản; mẫu dùng controller (định nghĩa hợp lệ)",
     sorted(F.bang(BB.PT)) == sorted(W45) and BB.mau("BM.01.11")["ky"][1]["role"] == "ISO Manager")
bot = sorted((x["thu_tu"], x["ten"]) for x in F.bang("SX QC Cong Doan").values() if x["day_chuyen"] == "Bột")
kiem("bột: thêm 4 công đoạn theo sơ đồ KH.HACCP.02 → 11; thứ tự D130 đổi theo sơ đồ, thứ tự Ban ISO đã sửa giữ nguyên",
     len(bot) == 11 and (2, "Bột: bột đậu xanh bán thành phẩm") in bot and (4, "Bột: nhặt lạc") in bot
     and (9, "Bột: xay đường") in bot and (11, "Bột: xuất hàng, phân phối") in bot, bot)
vd = {x["ten"]: x for x in F.bang(VD.PT).values()}
kiem("6 việc định kỳ năm theo Lịch biểu mẫu, ô hồ sơ = mã biên bản đóng việc",
     len(vd) == 6 and vd["Xem xét của lãnh đạo (BM.01.10)"]["han"] == "2026-12-31"
     and {x["ho_so"] for x in vd.values()} == {"BM.01.10", "BM.01.09", "BM.04.02", "BM.03.04", "BM.02.05", "BM.14.01"})
moc = json.loads(F.CAI_DAT["so_do_moc"])
kiem("mốc sơ đồ: bánh = danh mục lúc chạy patch (xác nhận giấy 22/09/2026); bột chưa có",
     list(moc) == ["Bánh"] and moc["Bánh"]["ngay"] == "2026-09-22")
hs = {x["ma"]: x for x in F.bang(HS.PT).values()}
kiem("BM.01.04: 18 dòng hồ sơ; BM.01.10, 04.x, 14.x lưu 3 năm; PRP.02 lưu tại xưởng",
     set(W45) <= set(hs) and hs["BM.01.10"]["thoi_gian_luu"] == "3 năm" and hs["BM.04.02"]["thoi_gian_luu"] == "3 năm"
     and hs["BM.01.11"]["thoi_gian_luu"] == "2 năm" and hs["BM.PRP.02"]["nguoi_luu"] == "Xưởng sản xuất")
F.bang(BB.PT)["BM.01.11"]["ten"] = "Biên bản họp Ban ISO (Ban ISO sửa)"
P.execute()
kiem("chạy lại vô hại: không tạo trùng, không đè mẫu Ban ISO đã sửa",
     len(F.bang(BB.PT)) == 18 and len(F.bang(VD.PT)) == 6 and len(bot) == 11
     and F.bang(BB.PT)["BM.01.11"]["ten"].endswith("(Ban ISO sửa)"))
F.bang(BB.PT)["BM.01.11"]["ten"] = "Biên bản họp Ban ISO"
d = P.doc_mau(dict(m11, phan=m11["phan"] + [{"key": "x", "kieu": "Kéo dữ liệu", "nguon": "os.system"}], ma="BM.TEST"))
kiem("controller mẫu chặn hàm kéo lạ (cả Desk)", "os.system" in (thu(lambda: F.get_doc(d).insert()) or ""))

# ═══ 3. API ═══════════════════════════════════════════════════════════════
print("\n-- họp Ban ISO tuần: lập, bản chụp, gửi, ký đúng thứ tự, trả lại, khóa, việc giao --")
them("SX Su Co", name="SC-1", ngay="2026-10-05", trang_thai="Mở", muc_do="Cao", loai="oPRP", mo_ta="Rang 235 °C")
them("SX Su Co", name="SC-2", ngay="2026-10-01", trang_thai="Đóng", muc_do="Thường", loai="PRP", mo_ta="Bẫy",
     dong_ngay="2026-10-07 09:00")
them("SX Su Co", name="SC-0", ngay="2026-09-01", trang_thai="Mở", muc_do="Thường", loai="PRP", mo_ta="Cũ")
them("Issue", name="ISS-1", custom_khieu_nai=1, opening_date="2026-10-06", status="Open", subject="Bánh mốc",
     customer="Đại lý A", custom_lo="2027-07-01")
them("SX Khac Phuc", name="CAR-0", ngay="2026-09-01", nguon="Sự cố", trang_thai="Mở", han="2026-09-30", mo_ta="Quá hạn")
la("bv@x")
kiem("Bảo vệ (không có mẫu nào) không lập được họp Ban ISO",
     "không lập được" in (thu(lambda: A.lap({"mau": "BM.01.11"})) or ""))
la("qc@x")
r = A.lap({"mau": "BM.01.11", "ngay": "2026-10-09", "dau": {"gio": "8:00", "dia_diem": "Phòng họp"}})
kiem("ô đầu phiếu lạ bị chặn", "ô lạ" in (thu(lambda: A.lap({"mau": "BM.01.11", "dau": {"xyz": 1}})) or ""))
x = A.xem(r["name"])
sc = x["noi_dung"]["su_co"]["keo"]
kiem("lập: số 01/BB-ISO; kéo sự cố trong kỳ 03–09/10 (SC-1 mở mới, SC-2 đóng, SC-0 + SC-1 còn mở), khiếu nại, "
     "BM.01.07 quá hạn",
     r["so"] == "01/BB-ISO" and [y["phieu"] for y in sc["dong"]] == ["SC-1", "SC-2", "SC-0", "SC-1"]
     and sc["tu"] == "2026-10-03" and x["noi_dung"]["khieu_nai"]["keo"]["dong"][0]["phieu"] == "ISS-1"
     and x["noi_dung"]["khac_phuc"]["keo"]["dong"][0]["phieu"] == "CAR-0", sc)
kiem("phần BM.01.12 (chỉ họp đầu tháng) không kéo, không hiện", "bc_thang" not in x["noi_dung"]
     and x["ap_dung"]["bc_thang"] is False)
them("SX Su Co", name="SC-3", ngay="2026-10-09", trang_thai="Mở", muc_do="Thường", loai="PRP", mo_ta="Mới")
kiem("BẢN CHỤP: sự cố mới sau lúc lập không làm đổi biên bản", len(A.xem(r["name"])["noi_dung"]["su_co"]["keo"]["dong"])
     == 4)
kiem("chưa ghi đủ → không gửi ký", "Chưa gửi ký được" in (thu(lambda: A.gui(r["name"])) or ""))
nd = x["noi_dung"]
nd["thanh_phan"] = {"dong": [{"ho_ten": "Nguyễn Huy Chiến", "chuc_danh": "Trưởng Ban ISO"}, {"ho_ten": "Đào Quang Công"}]}
for y in nd["noi_dung"]["dong"]:
    y["tinh_hinh"] = f"Mục {y['ma']}: đã xem"
nd["viec_giao"] = {"dong": [{"viec": "Hiệu chỉnh đồng hồ M2", "phu_trach": "cd@x", "han": "2026-10-12"},
                            {"viec": "Đóng SC-1", "phu_trach": "iso@x", "han": "2026-10-20"}]}
x = A.luu(r["name"], {"noi_dung": nd})
kiem("kéo lại khi Nháp: sự cố mới vào bản chụp", len(A.keo_lai(r["name"], "su_co")["noi_dung"]["su_co"]["keo"]["dong"])
     == 6)
A.gui(r["name"])
la("iso@x")
kiem("Trưởng Ban ISO ký trước Thư ký → chặn", "đang chờ Thư ký" in (thu(lambda: A.ky(r["name"])) or ""))
la("ql@x")
kiem("QLSX không có ô → không xem / ký được? (Ban ISO xem được biên bản họp: QLSX có vai lập nên xem, không ký)",
     A.xem(r["name"])["quyen"]["ky"] is False and "không có ô ký" in (thu(lambda: A.ky(r["name"])) or ""))
la("qc@x")
A.ky(r["name"], "đã ghi đủ")
kiem("Thư ký ký rồi không ký tiếp ô chủ trì", "không ký hai ô" in (thu(lambda: A.ky(r["name"])) or ""))
la("iso@x")
kiem("trả lại phải ghi ý kiến", "ghi ý kiến" in (thu(lambda: A.tra_lai(r["name"], " ")) or ""))
x = A.tra_lai(r["name"], "Ghi rõ người làm mục d")
kiem("trả lại → Trả lại, chữ ký vòng này bỏ, ý kiến ghi kèm giờ, người",
     x["trang_thai"] == "Trả lại" and not any(s["ky_luc"] for s in x["ky"]) and "Ghi rõ người làm mục d"
     in x["y_kien_tra_lai"] and "Nguyễn Huy Chiến" in x["y_kien_tra_lai"])
la("qc@x")
nd = x["noi_dung"]
nd["noi_dung"]["dong"][3]["tinh_hinh"] = "CAR-0 quá hạn — Cơ điện làm"
A.luu(r["name"], {"noi_dung": nd})
A.gui(r["name"])
A.ky(r["name"])
la("iso@x")
x = A.ky(r["name"], "Đồng ý")
vds = [F.bang(VD.PT)[v["viec_dinh_ky"]] for v in x["viec"]]
kiem("ký đủ → Đã ký đủ; 2 việc giao thành việc định kỳ 'Một lần' (hạn, người, hồ sơ = số biên bản)",
     x["trang_thai"] == "Đã ký đủ" and len(vds) == 2 and all(v["chu_ky"] == "Một lần" for v in vds)
     and vds[0]["han"] == "2026-10-12" and vds[0]["phu_trach"] == "Ngô Văn Trường"
     and vds[0]["ho_so"] == "BM.01.11 số 01/BB-ISO", vds)
kiem("việc giao lên hộp nhắc việc định kỳ (hạn 12/10 còn 3 ngày)",
     any(y["name"] == vds[0]["name"] for y in VD.nhac("2026-10-09")["sap_den"]))
kiem("khóa: không sửa qua API", thu(lambda: A.luu(r["name"], {"noi_dung": {}})) is not None)
doc = F.get_doc(BB.PT_BB, r["name"])
doc.tieu_de = "sửa"
kiem("khóa: lưu ngoài API (Desk) bị chặn; có cờ API mà đổi nội dung cũng chặn",
     "trên app" in (thu(lambda: doc.save()) or "") and "khóa" in (thu(lambda: A._luu(doc)) or ""))
kiem("bản in: đầu trang, số, phần theo thứ tự, 'Ký trên phần mềm: Họ tên', bản chụp ghi giờ kéo",
     all(s in A.in_bb(r["name"]) for s in ("BM.01.11", "Số: 01/BB-ISO", "1. Thành phần tham dự",
                                           "Ký trên phần mềm: Đào Quang Công", "Ký trên phần mềm: Nguyễn Huy Chiến",
                                           "Số liệu app lúc lập", "SC-1")))
F.dat_ngay("2026-10-16")
la("qc@x")
v1 = F.get_doc(VD.PT, vds[0]["name"])
VD.ghi_lan(v1, "2026-10-12", "xong")
v1.save()
r2 = A.lap({"mau": "BM.01.11", "ngay": "2026-10-16"})
x2 = A.xem(r2["name"])
kiem("họp tuần sau: số 02/BB-ISO, kỳ từ 10/10; việc giao chưa xong của lần trước tự kéo sang (1 việc — việc đã làm bỏ)",
     r2["so"] == "02/BB-ISO" and x2["noi_dung"]["su_co"]["keo"]["tu"] == "2026-10-10"
     and [y["viec"] for y in x2["noi_dung"]["viec_truoc"]["keo"]["dong"]] == ["Đóng SC-1"], x2["noi_dung"]["viec_truoc"])
la("bv@x")
kiem("Bảo vệ không xem được biên bản họp Ban ISO", thu(lambda: A.xem(r2["name"])) is not None
     and A.ds()["ds"] == [])

print("\n-- ký tay: BM.02.01, BM.03.04 --")
la("iso@x")
r3 = A.lap({"mau": "BM.02.01", "dau": {"ten_san_pham": "Bánh đậu xanh 250 g", "han_su_dung": "2027-07-01",
                                       "muc_do": "Mức độ B", "so_luong_da_xuat": 120}})
kiem("số kế hoạch thu hồi theo ký hiệu KHTHSP", r3["so"] == "01/KHTHSP")
x3 = A.gui(r3["name"])
kiem("chỉ ô Giám đốc ký tay → Chờ ký, Giám đốc không ký trên app", x3["trang_thai"] == "Chờ ký" and x3["can_ky_tay"]
     and x3["quyen"]["ky_tay"])
la("gd@x")
kiem("Giám đốc bấm ký → không có ô ký trên app", "không có ô ký" in (thu(lambda: A.ky(r3["name"])) or ""))
la("iso@x")
x3 = A.tai_ky_tay(r3["name"], "kh-thu-hoi.pdf", pdf())
kiem("tải bản scan đã ký → Đã ký đủ", x3["trang_thai"] == "Đã ký đủ" and x3["co_ky_tay"])
r4 = A.lap({"mau": "BM.02.02", "goc": r3["name"]})
x4 = A.xem(r4["name"])
kiem("BM.02.02 lập từ BM.02.01: số, ngày kế hoạch, sản phẩm, mức độ, số lượng đã xuất chép sang",
     x4["noi_dung"]["dau"]["gia_tri"]["so_ke_hoach"] == "01/KHTHSP"
     and x4["noi_dung"]["ket_qua"]["gia_tri"]["muc_do"] == "B"
     and x4["noi_dung"]["ket_qua"]["gia_tri"]["so_luong_da_xuat"] == 120)
nd4 = x4["noi_dung"]
nd4["ket_qua"]["gia_tri"].update(so_luong_thu_hoi=90, ket_luan="Thu hồi đạt", ty_le=1)
kiem("tỷ lệ thu hồi do app tính (90 / 120 = 75 %)",
     A.luu(r4["name"], {"noi_dung": nd4})["noi_dung"]["ket_qua"]["gia_tri"]["ty_le"] == 75.0)
A.gui(r4["name"])
x4 = A.tai_ky_tay(r4["name"], "bc.pdf", pdf())
kiem("BM.02.02: có bản scan mà ô Trưởng Ban ISO chưa ký → còn Chờ ký", x4["trang_thai"] == "Chờ ký" and x4["co_ky_tay"])
x4 = A.tra_lai(r4["name"], "Bổ sung nguyên nhân")
kiem("trả lại bỏ luôn bản scan (nội dung sẽ sửa — phải ký tay lại)", x4["trang_thai"] == "Trả lại" and not x4["co_ky_tay"])
la("cd@x")
r5 = A.lap({"mau": "BM.03.04", "dau": {"dt1": 1, "co_don_vi_ngoai": 1, "don_vi_ngoai": "PC07"}})
x5 = A.xem(r5["name"])
nd5 = x5["noi_dung"]
nd5["nguoi_tham_gia"] = {"dong": [{"ho_ten": "Cả xưởng"}]}
for y in nd5["tieu_chi"]["dong"]:
    if y["ma"] == "DT-1":
        y.update(ket_qua_thuc_te="ổn", dat="Đạt")
nd5["ket_luan"] = {"gia_tri": {"ket_luan": "Đạt"}}
A.luu(r5["name"], {"noi_dung": nd5})
A.gui(r5["name"])
for u in ("cd@x", "iso@x", "hc@x", "gd@x"):
    la(u)
    x5 = A.ky(r5["name"])
kiem("BM.03.04 có đơn vị PCCC ngoài: 4 ô ký trên app đủ mà chưa có bản ký tay → còn Chờ ký",
     x5["trang_thai"] == "Chờ ký" and x5["can_ky_tay"] and all(k["ky_luc"] for k in x5["ky"]))
la("cd@x")
kiem("người lập tải bản scan → Đã ký đủ", A.tai_ky_tay(r5["name"], "dien-tap.jpg", base64.b64encode(
    b"\xff\xd8anh").decode())["trang_thai"] == "Đã ký đủ")
kiem("bản in BM.03.04: chỉ in tiêu chí DT-1, có ô bên ngoài ký tay", (lambda h: "Phát hiện, báo động" in h
     and "Ghi giờ mất điện" not in h and "Bên ngoài tham gia" in h)(A.in_bb(r5["name"])))

print("\n-- thẩm tra: BM.04.02 từ BM.04.01, dòng Không đạt → BM.01.07 --")
la("iso@x")
r6 = A.lap({"mau": "BM.04.01"})
x6 = A.xem(r6["name"])
for y in x6["noi_dung"]["ke_hoach"]["dong"]:
    y["thoi_gian"] = "2026-10-20"
A.luu(r6["name"], {"noi_dung": {"ke_hoach": {"dong": x6["noi_dung"]["ke_hoach"]["dong"][:5]}}})
A.gui(r6["name"])
A.ky(r6["name"])
la("gd@x")
A.ky(r6["name"])
la("qc@x")
la("iso@x")
r6n = A.lap({"mau": "BM.04.01"})
la("qc@x")
kiem("BM.04.02 không lập từ kế hoạch chưa duyệt / từ biên bản khác mẫu", all("đã ký đủ" in (thu(
    lambda g=g: A.lap({"mau": "BM.04.02", "goc": g})) or "") for g in (r6n["name"], r2["name"])))
r7 = A.lap({"mau": "BM.04.02", "goc": r6["name"], "dau": {"nguoi_tham_tra": "Đào Quang Công"}})
x7 = A.xem(r7["name"])
kiem("BM.04.02 lấy đúng 5 hạng mục của kế hoạch đã duyệt (câu cố định)",
     len(x7["noi_dung"]["bao_cao"]["dong"]) == 5 and all(y["_co_dinh"] for y in x7["noi_dung"]["bao_cao"]["dong"]))
for i, y in enumerate(x7["noi_dung"]["bao_cao"]["dong"]):
    y.update(ket_qua="Không đạt" if i == 1 else "Đạt", bang_chung="hồ sơ", thoi_gian_tham_tra_lai=(
        "2026-11-15" if i == 1 else None))
A.luu(r7["name"], {"noi_dung": x7["noi_dung"]})
A.gui(r7["name"])
A.ky(r7["name"])
la("iso@x")
x7 = A.ky(r7["name"])
kph = x7["kph"]
kiem("dòng Không đạt hiện ở danh sách không phù hợp; ngày thẩm tra lại thành việc định kỳ",
     len(kph) == 1 and kph[0]["stt"] == 2 and any("thẩm tra lại" in v["noi_dung"] for v in x7["viec"]))
c1 = A.lap_car(r7["name"], kph[0]["phan"], kph[0]["dong"])
car = F.bang(KP.PT)[c1["name"]]
kiem("Lập BM.01.07: nguồn Thẩm tra, mô tả có số biên bản + hạng mục; gắn ngược vào phiếu liên quan; bấm lại không đẻ "
     "phiếu thứ hai",
     car["nguon"] == "Thẩm tra" and "BM.04.02 số 01/2026" in car["mo_ta"] and car["trang_thai"] == "Mở"
     and A.xem(r7["name"])["kph"][0]["car"] == c1["name"]
     and A.lap_car(r7["name"], kph[0]["phan"], kph[0]["dong"]) == {"name": c1["name"], "da_co": 1})
dat_dong = x7["noi_dung"]["bao_cao"]["dong"][0]["_id"]
kiem("dòng Đạt → không lập BM.01.07", "không phải điểm không phù hợp" in (
    thu(lambda: A.lap_car(r7["name"], "bao_cao", dat_dong)) or ""))
vtt = next(v for v in F.bang(VD.PT).values() if v["ho_so"] == "BM.04.02")
kiem("việc định kỳ năm 'Thẩm tra hệ thống' (hồ sơ BM.04.02) tự ghi đã làm, hạn dời sang năm sau",
     vtt["han"] != "2026-12-15" and vtt.get("lan_cuoi"), vtt)

print("\n-- đánh giá nội bộ: 4 mẫu nối nhau --")
la("iso@x")
r8 = A.lap({"mau": "BM.01.05", "dau": {"thoi_gian_thuc_hien": "20/11/2026", "muc_dich": "ĐGNB",
                                        "tieu_chuan": "ISO 22000"}})
KHN = json.loads(json.dumps(KH))
kiem("lưu kế hoạch có chuyên gia đánh giá bộ phận mình → chặn",
     "không đánh giá bộ phận của mình" in (thu(lambda: A.luu(r8["name"], {"noi_dung": KHN})) or ""))
KHN["chi_tiet"]["dong"][1]["chuyen_gia"] = "C"
KHN["chi_tiet"]["dong"].append({"thoi_gian": "13:15", "noi_dung": "Cơ điện", "bo_phan": "Cơ điện", "chuyen_gia": "B"})
A.luu(r8["name"], {"noi_dung": KHN})
A.gui(r8["name"])
A.ky(r8["name"])
la("gd@x")
A.ky(r8["name"])
la("kho@x")
kiem("người ngoài đoàn không lập checklist", thu(lambda: A.lap({"mau": "BM.01.06", "goc": r8["name"],
                                                               "dau": {"bo_phan": "Kho"}})) is not None)
la("qc@x")
ml = A.mau_lap("BM.01.06")
kiem("chuyên gia B thấy kế hoạch của đợt, bộ phận được phân: Cơ điện",
     ml["goc"][0]["name"] == r8["name"] and ml["goc"][0]["bo_phan"] == ["Cơ điện"])
kiem("chuyên gia QC lập checklist cho bộ phận QC → chặn", "không đánh giá bộ phận của mình" in (
    thu(lambda: A.lap({"mau": "BM.01.06", "goc": r8["name"], "dau": {"bo_phan": "QC"}})) or ""))
r9 = A.lap({"mau": "BM.01.06", "goc": r8["name"], "dau": {"bo_phan": "Cơ điện"}})
x9 = A.xem(r9["name"])
kiem("checklist: tên chuyên gia tự điền; chưa có câu hỏi in sẵn", x9["noi_dung"]["dau"]["gia_tri"]["chuyen_gia"]
     == "Đào Quang Công" and not x9["noi_dung"].get("checklist"))
x9["noi_dung"]["checklist"] = {"dong": [{"yeu_cau": "Hiệu chuẩn đồng hồ nhiệt", "ket_luan": "KPH", "bang_chung": "M2"},
                                        {"yeu_cau": "Sổ bảo dưỡng", "ket_luan": "Lưu ý", "bang_chung": "thiếu chữ ký"},
                                        {"yeu_cau": "Nam châm", "ket_luan": "PH"}]}
A.luu(r9["name"], {"noi_dung": x9["noi_dung"]})
A.gui(r9["name"])
x9 = A.ky(r9["name"])
c2 = A.lap_car(r9["name"], x9["kph"][0]["phan"], x9["kph"][0]["dong"])
kiem("checklist ký đủ; KPH → BM.01.07 nguồn Đánh giá nội bộ", x9["trang_thai"] == "Đã ký đủ"
     and F.bang(KP.PT)[c2["name"]]["nguon"] == "Đánh giá nội bộ")
la("hc@x")
r10 = A.lap({"mau": "BM.01.06", "goc": r8["name"], "dau": {"bo_phan": "Kho"}})
x10 = A.chep_cau_hoi(r10["name"])
kiem("Chép câu hỏi từ đợt trước: 3 câu (chỉ câu hỏi, không chép kết luận); bấm lại không chép trùng",
     x10["da_chep"] == 3 and all("ket_luan" not in y for y in x10["noi_dung"]["checklist"]["dong"])
     and A.chep_cau_hoi(r10["name"])["da_chep"] == 0)
nd10 = x10["noi_dung"]
nd10["checklist"]["dong"][0].update(ket_luan="Lưu ý", bang_chung="FIFO chưa dán nhãn")
A.luu(r10["name"], {"noi_dung": nd10})
la("iso@x")
r11 = A.lap({"mau": "BM.01.08", "goc": r8["name"]})
x11 = A.xem(r11["name"])
kiem("BM.01.08 tự gom 2 điểm lưu ý từ checklist của đợt; ô ký là trưởng đoàn của kế hoạch",
     [y["trach_nhiem"] for y in x11["noi_dung"]["luu_y"]["dong"]] == ["Cơ điện", "Kho"]
     and x11["ky"][0]["user"] == "hc@x" and x11["ky"][0]["gan"] == 1, x11["noi_dung"]["luu_y"])
A.gui(r11["name"])
kiem("Trưởng Ban ISO không ký ô trưởng đoàn", thu(lambda: A.ky(r11["name"])) is not None)
la("hc@x")
kiem("trưởng đoàn ký → Đã ký đủ", A.ky(r11["name"])["trang_thai"] == "Đã ký đủ")
r12 = A.lap({"mau": "BM.01.09", "goc": r8["name"]})
x12 = A.xem(r12["name"])
kiem("BM.01.09: đếm KPH / Lưu ý theo bộ phận, thành phần đoàn theo kế hoạch, thời gian đánh giá chép sang",
     {y["bo_phan"]: (y["so_kph"], y["so_luu_y"]) for y in x12["noi_dung"]["noi_dung"]["dong"]}
     == {"Cơ điện": (1, 1), "Kho": (0, 1)}
     and [y["ho_ten"] for y in x12["noi_dung"]["thanh_phan"]["dong"]][0] == "Hoàng Hành Chính"
     and x12["noi_dung"]["dau"]["gia_tri"]["thoi_gian_danh_gia"] == "20/11/2026", x12["noi_dung"])

print("\n-- BM.HACCP.01 bột: kéo đủ 11 công đoạn, nhắc sơ đồ --")
F.dat_ngay("2026-10-17")
la("iso@x")
so_do = [y["day_chuyen"] for y in BB.so_do_nhac("2026-10-17")]
kiem("trước biên bản: nhắc xác nhận sơ đồ bột; bánh khớp mốc → không nhắc", so_do == ["Bột"], so_do)
r13 = A.lap({"mau": "BM.HACCP.01", "dau": {"san_pham": "Các sản phẩm bột đậu (KH.HACCP.02 mục 5.5)"}})
x13 = A.xem(r13["name"])
cd = [y["cong_doan"] for y in x13["noi_dung"]["cong_doan"]["dong"]]
kiem("BM.HACCP.01 bột kéo đủ 11 công đoạn theo sơ đồ (số thứ tự + tên)",
     len(cd) == 11 and cd[0] == "1 Bột: tiếp nhận" and cd[10] == "11 Bột: xuất hàng, phân phối", cd)
for y in x13["noi_dung"]["cong_doan"]["dong"]:
    y.update(thuc_te="đúng", dung_so_do=1)
x13["noi_dung"]["ket_luan"] = {"gia_tri": {"ket_luan": "Sơ đồ đúng thực tế"}}
A.luu(r13["name"], {"noi_dung": x13["noi_dung"]})
A.gui(r13["name"])
for u in ("ql@x", "qc@x", "iso@x"):
    la(u)
    x13 = A.ky(r13["name"])
kiem("QLSX → QC → Trưởng Ban ISO ký đủ; hết nhắc sơ đồ bột", x13["trang_thai"] == "Đã ký đủ"
     and BB.so_do_nhac("2026-10-17") == [])
them("SX QC Cong Doan", name="Bột: sấy", ten="Bột: sấy", day_chuyen="Bột", thu_tu=12, ngung=0)
F.bang("SX QC Cong Doan")["2 Bước 2"]["ten"] = "2 Luộc đỗ"
kiem("thêm công đoạn bột, đổi tên công đoạn bánh → nhắc xác nhận lại cả hai dây chuyền",
     [y["day_chuyen"] for y in BB.so_do_nhac("2026-10-17")] == ["Bánh", "Bột"])
r14 = A.lap({"mau": "BM.HACCP.02", "dau": {"ke_hoach": "KH.HACCP.02 các sản phẩm bột đậu", "lan_tham_dinh": "Lần đầu"}})
kiem("BM.HACCP.02 bột kéo oPRP-5 đến 9", [y["oprp"] for y in A.xem(r14["name"])["noi_dung"]["tham_dinh"]["dong"]]
     == ["oPRP-5", "oPRP-6", "oPRP-7", "oPRP-8", "oPRP-9"])

print("\n-- nối: hộp nhắc, Tài liệu 'Chờ tôi ký', gói hồ sơ --")
la("hc@x")
r15 = A.lap({"mau": "BM.01.11", "ngay": "2026-10-17"})
x15 = A.xem(r15["name"])
nd15 = x15["noi_dung"]
nd15["thanh_phan"] = {"dong": [{"ho_ten": "A"}]}
for y in nd15["noi_dung"]["dong"]:
    y["tinh_hinh"] = "ok"
A.luu(r15["name"], {"noi_dung": nd15})
A.gui(r15["name"])
A.ky(r15["name"])
la("iso@x")
kiem("Tài liệu: 'Chờ tôi ký' của Trưởng Ban ISO có họp Ban ISO 17/10; tab Biên bản hiện",
     any(y["name"] == r15["name"] for y in TLA._cho_ky({"ISO Manager"})) and TLA._co_bien_ban({"ISO Manager"}))
dl = Q._du_lieu_nhac(date(2026, 10, 17))
nh = [y for y in NH.tinh(date(2026, 10, 17), **dl) if y["nhom"] == "bien_ban"]
kiem("hộp nhắc QC (dữ liệu thật): biên bản chờ bạn ký + sơ đồ bánh / bột", any("chờ bạn ký" in y["tieu_de"] for y in nh)
     and sum("sơ đồ" in y["tieu_de"] for y in nh) == 2, nh)
tep = A.in_ho_so("BM.01.11", "2026-10-01", "2026-10-31")
kiem("gói hồ sơ: chỉ biên bản ký đủ trong kỳ (1 họp Ban ISO)", len(tep) == 1 and "01/BB-ISO" in tep[0][1], [t for t, _h in tep])

F.ket_thuc("BIENBAN")
