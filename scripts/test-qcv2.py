"""D129 — bộ mục BM.08.01 bản 2 (W01) + rây kiểm RY-01 (W02).

Hỏng ở đây là hỏng IM LẶNG theo ba hướng:
  · Phiếu cũ bị chen mục mới (tờ in tháng trước tự dưng có hàng "chưa kiểm") hoặc
    mất mục cũ (T11 đã ghi biến khỏi tờ in) — hồ sơ đã chốt đổi nghĩa.
  · Mục mới không hiện ở đúng lượt → không ai ghi, không sinh sự cố.
  · Dị vật trên rây / vệ sinh chuyển đổi không đạt mà không thành phiếu sự cố.

Nạp sx/qc/muc.py, su_co.py, nguong.py, controller SX QC Round, sx/api/qc.py THẬT.
Chạy: python3 scripts/test-qcv2.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import re
import sys
import types
from datetime import date, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

LUOT = []          # SX QC Round
LM = []            # SX QC Luu Mau
FILE = []          # File (ảnh lưu mẫu)
ITEM = [{"name": "Chè đậu đen cốt dừa", "item_name": "Chè đậu đen cốt dừa",
         "custom_sx_nhom": "BTP-Bot-SP", "disabled": 0},
        {"name": "BDS", "item_name": "Bột đậu sữa dừa có đường",
         "custom_sx_nhom": "BTP-Bot-SP", "disabled": 0},
        {"name": "BDM", "item_name": "Bột đậu matcha có đường",
         "custom_sx_nhom": "BTP-Bot-SP", "disabled": 0},
        {"name": "TP-SEN", "item_name": "Bánh đậu xanh sen", "custom_sx_nhom": "TP",
         "disabled": 0}]
CAI_DAT = {}
VAI = {"SX QC"}
SQL = []
HOM_NAY = date(2026, 9, 29)


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v

    def set(self, k, v):
        self[k] = v


def _bang(dt):
    return {"SX QC Round": LUOT, "SX QC Luu Mau": LM, "Item": ITEM, "File": FILE}.get(dt, [])


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "<" and not (x or 0) < m:
                return False
            if op == "<=" and not (str(x) <= str(m)):
                return False
            if op == "in" and x not in m:
                return False
            if op == "!=" and x == m:
                return False
        elif str(x) != str(v):
            return False
    return True


def get_all(dt, filters=None, fields=None, pluck=None, limit=None, order_by=None, **k):
    ra = [Doc(h) for h in _bang(dt) if _khop(h, filters)]
    if (order_by or "").startswith("han_luu asc"):
        ra.sort(key=lambda h: str(h.get("han_luu")))
    if limit:
        ra = ra[:limit]
    return [h.get(pluck) for h in ra] if pluck else ra


class FileDoc(Doc):
    def insert(self, **kw):
        self["name"] = f"F{len(FILE) + 1}"
        self["file_url"] = f"/private/files/{self['file_name']}"
        self["file_size"] = len(self["content"])
        FILE.append(self)
        return self


def _get_doc(x, n=None):
    if isinstance(x, dict):
        if x.get("doctype") == "File":
            return FileDoc(x)
        return (LMDoc if x.get("doctype") == "SX QC Luu Mau" else Doc)(x)
    h = next(h for h in _bang(x) if h["name"] == n)
    # Như Frappe thật: get_doc đọc ra BẢN SAO; chỉ save() mới ghi lại. Trả thẳng
    # object trong bảng thì một lần save hỏng vẫn để lại trạng thái đã đổi.
    return LMDoc(h) if x == "SX QC Luu Mau" else h


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.session = types.SimpleNamespace(user="qc@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_doc = _get_doc
frappe.get_cached_doc = lambda dt: Doc(CAI_DAT)
frappe.get_meta = lambda dt: types.SimpleNamespace(has_field=lambda f: True)
frappe.db = types.SimpleNamespace(
    get_value=lambda dt, f, fld=None, **k: next(
        (h.get(fld) for h in _bang(dt) if (h["name"] == f if isinstance(f, str)
                                            else _khop(h, f))), None),
    count=lambda dt, f=None: len(get_all(dt, f)),
    table_exists=lambda dt: True,
    get_table_columns=lambda dt: ["co_lac", "can_thu_lac", "so_may_rang",
                                  "so_may_nghien", "so_may_goi_bot"],
    sql=lambda q, *a, **k: SQL.append(" ".join(q.split())),
    set_value=lambda dt, n, f, v=None, **k: next(
        h for h in _bang(dt) if h["name"] == n).update(f if isinstance(f, dict) else {f: v}),
)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.getdate = lambda x=None: (x if isinstance(x, date) else
                             date.fromisoformat(str(x)[:10]) if x else HOM_NAY)
fu.nowdate = lambda: str(HOM_NAY)
fu.add_days = lambda d, n: fu.getdate(d) + timedelta(days=n)
fu.get_datetime = lambda x=None: x
fu.get_time = lambda x=None: x
fu.time_diff_in_seconds = lambda a, b: 0
fu.now_datetime = lambda: "2026-09-29 10:00:00"
fu.formatdate = str
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
mdl = types.ModuleType("frappe.model"); mdl.__path__ = []
dm = types.ModuleType("frappe.model.document"); dm.Document = Doc
sys.modules["frappe.model"] = mdl
sys.modules["frappe.model.document"] = dm

for g in ("sx", "sx.qc", "sx.api", "sx.qc.doctype", "sx.patches"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


M = nap("sx.qc.muc", "sx/qc/muc.py")
NG = nap("sx.qc.nguong", "sx/qc/nguong.py")
nap("sx.qc.san_pham", "sx/qc/san_pham.py")
SC = nap("sx.qc.su_co", "sx/qc/su_co.py")
nap("sx.qc.xuat", "sx/qc/xuat.py")
nap("sx.qc.nhac", "sx/qc/nhac.py")
R = nap("sx.qc.doctype.sx_qc_round.sx_qc_round",
        "sx/qc/doctype/sx_qc_round/sx_qc_round.py")
LMC = nap("sx.qc.doctype.sx_qc_luu_mau.sx_qc_luu_mau",
          "sx/qc/doctype/sx_qc_luu_mau/sx_qc_luu_mau.py")
Q = nap("sx.api.qc", "sx/api/qc.py")


class LMDoc(Doc):
    def insert(self, **kw):
        LMC.SXQCLuuMau.validate(self)
        self["name"] = f"LM-{len(LM) + 1:04d}"
        LM.append(self)
        return self

    def save(self, **kw):
        LMC.SXQCLuuMau.validate(self)
        next(h for h in LM if h["name"] == self["name"]).update(self)
        return self


hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


def thu(fn):
    try:
        fn()
        return None
    except Loi as e:
        return str(e) or type(e).__name__


def ap(luot="Trưa", **kw):
    return {m["f"] for m in M.muc_ap_dung(luot, Doc(kw))}



def ap_pb(luot, pb, **kw):
    return {m["f"] for m in M.muc_ap_dung(luot, Doc(phien_ban=pb, **kw))}


def sc(**kw):
    kw.setdefault("luot", "Đầu sáng")
    kw.setdefault("phien_ban", 2)
    return SC.phat_hien(Doc(kw))


# ═══ 1. Phiên bản bộ mục ════════════════════════════════════════════════
print("-- phiên bản: phiếu cũ giữ bộ cũ, phiếu mới theo bộ mới --")
MOI = {"a5_chuyen_doi", "thung_khay_cat_sach", "u_thung_vai_sach", "hat_tho", "di_vat_ray"}
kiem("bộ mục hiện hành là bản 2", M.PHIEN_BAN == 2)
kiem("phiếu trước D129 (phiên bản trống) KHÔNG có mục mới",
     not (MOI & ap_pb("Tuần", 0)), str(MOI & ap_pb("Tuần", 0)))
kiem("phiếu trước D129 vẫn có T11 quả chuẩn (số đã ghi không biến mất)",
     "t11_can_qua_chuan" in ap_pb("Tuần", 0))
kiem("phiếu bản 2 có đủ mục mới ở lượt Tuần", MOI <= ap_pb("Tuần", 2), str(MOI - ap_pb("Tuần", 2)))
kiem("phiếu bản 2 KHÔNG có T11 (chuyển sang quản lý thiết bị đo — W17)",
     "t11_can_qua_chuan" not in ap_pb("Tuần", 2))
d = Doc(luot="Trưa", ngay="2026-10-08")
R.SXQCRound.before_insert(d)
kiem("mở phiếu mới → ghi phiên bản hiện hành", d.phien_ban == M.PHIEN_BAN)
d = Doc(luot="Trưa", ngay="2026-10-08", phien_ban=1)
R.SXQCRound.before_insert(d)
kiem("phiếu đã có phiên bản (Desk / nhập lại) → giữ nguyên", d.phien_ban == 1)

print("\n-- W01: mục mới đúng lượt --")
for l in ("Đầu sáng", "Trưa", "Cuối chiều", "Tuần"):
    kiem(f"1e chuyển đổi trong ngày có ở lượt {l}", "a5_chuyen_doi" in ap_pb(l, 2))
    kiem(f"5 thùng ủ, vải ủ có ở lượt {l}", "u_thung_vai_sach" in ap_pb(l, 2))
kiem("4b thùng, khay cát sạch chỉ lượt Đầu sáng / Tuần",
     "thung_khay_cat_sach" in ap_pb("Đầu sáng", 2) and "thung_khay_cat_sach" in ap_pb("Tuần", 2)
     and "thung_khay_cat_sach" not in ap_pb("Trưa", 2))
kiem("mục 4 cũ thành 4a, mục mới 4b cùng công đoạn Sàng cát",
     M.THEO_F["luoi_sang_nguyen_ven"]["so"] == "4a" and M.THEO_F["thung_khay_cat_sach"]["buoc"] == "4")
kiem("công đoạn 5 Ủ tắt được khi không chạy",
     "5" in M.BUOC_TAT_DUOC and "u_thung_vai_sach" not in ap_pb("Trưa", 2, buoc_nghi="5"))
kiem("bước 5 đứng giữa 4 Sàng cát và 6 Vỡ đỗ",
     [b[0] for b in M.BUOC].index("5") == [b[0] for b in M.BUOC].index("4") + 1)
kiem("nhãn mục 5 nói VẢI ủ, không phải khăn phủ",
     "vải ủ" in M.THEO_F["u_thung_vai_sach"]["nhan"] and "khăn" not in M.THEO_F["u_thung_vai_sach"]["nhan"])
kiem("B5 nhắc hộp nhựa", "hộp nhựa" in M.THEO_F["b5_nhan_di_ung"]["nhan"])

print("\n-- W01: mục chuyển đổi (1e, B7c) --")
cd = M.THEO_F["a5_chuyen_doi"]
kiem("'Không có chuyển đổi' là câu trả lời (đã chấm)", M.co_ghi(cd, "Không có chuyển đổi"))
kiem("để trống = chưa kiểm", not M.co_ghi(cd, ""))
kiem("1e Không đạt → sự cố Dị ứng mức Thường",
     [(x[0], x[2], x[3]) for x in sc(a5_chuyen_doi="Không đạt")]
     == [("a5_chuyen_doi", "Dị ứng", "Thường")], str(sc(a5_chuyen_doi="Không đạt")))
kiem("1e Đạt / Không có → không sự cố",
     not sc(a5_chuyen_doi="Đạt") and not sc(a5_chuyen_doi="Không có chuyển đổi"))
kiem("1e trên phiếu bản 1 không xét (mục chưa tồn tại)",
     not sc(a5_chuyen_doi="Không đạt", phien_ban=1))
kiem("4b Không đạt → sự cố PRP", [x[2] for x in sc(thung_khay_cat_sach="Không đạt")] == ["PRP"])
kiem("5 Không đạt → sự cố PRP", [x[2] for x in sc(luot="Trưa", u_thung_vai_sach="Không đạt")] == ["PRP"])

print("\n-- W01: B7c vệ sinh chuyển đổi sữa --")
kiem("có bột, không vị có sữa → không có B7c",
     "b7_ve_sinh_sua" not in ap_pb("Trưa", 2, co_san_xuat_bot=1))
kiem("có vị có sữa → có B7c", "b7_ve_sinh_sua" in ap_pb("Trưa", 2, co_san_xuat_bot=1, co_sua=1))
kiem("lượt trước làm vị có sữa → lượt này có B7c",
     "b7_ve_sinh_sua" in ap_pb("Trưa", 2, co_san_xuat_bot=1, can_ve_sinh_sua=1))
kiem("B7c Không đạt → Dị ứng",
     [x[2] for x in sc(luot="Trưa", co_san_xuat_bot=1, co_sua=1, b7_ve_sinh_sua="Không đạt")]
     == ["Dị ứng"])
kiem("luật lượt trước giống thử lạc", M.can_ve_sinh_sua(0, "Trưa", [("Đầu sáng", 1)]) == 1
     and M.can_ve_sinh_sua(0, "Đầu sáng", [("Trưa", 1)]) == 0)
# Controller: cờ sữa từ sản phẩm tự công bố / danh sách Setting
ITEM.append({"name": "BDN", "item_name": "Bột đậu nành sữa", "custom_sx_nhom": "BTP-Bot-SP",
             "disabled": 0, "custom_sp_cong_bo": "SPCB-011"})
SP_GIA = [{"name": "SPCB-011", "co_lac": 0, "co_sua_bot": 1, "co_dua": 0}]
_ga = frappe.get_all
frappe.get_all = lambda dt, *a, **k: ([Doc(x) for x in SP_GIA] if dt == "SX San Pham Cong Bo"
                                     else _ga(dt, *a, **k))
LUOT.clear()
d = R.SXQCRound(Doc(name="QC-1", ngay="2026-10-08", luot="Trưa", co_san_xuat_bot=1,
                    san_pham_bot="BDN", phien_ban=2))
R.SXQCRound.tinh_boi_canh(d)
kiem("vị gắn sản phẩm 'có sữa bột' → co_sua = 1, B7c bật", d.co_sua == 1 and d.can_ve_sinh_sua == 1)
d = R.SXQCRound(Doc(name="QC-2", ngay="2026-10-08", luot="Trưa", co_san_xuat_bot=1,
                    san_pham_bot="BDS", phien_ban=2))
R.SXQCRound.tinh_boi_canh(d)
kiem("vị không gắn, không có trong danh sách → co_sua = 0", d.co_sua == 0)
CAI_DAT["bot_co_sua"] = "Bột đậu sữa dừa có đường"
R.SXQCRound.tinh_boi_canh(d)
kiem("vị có trong 'Vị bột có sữa bột' ở Setting → co_sua = 1", d.co_sua == 1)
CAI_DAT.pop("bot_co_sua")
d = R.SXQCRound(Doc(name="QC-3", ngay="2026-10-08", luot="Trưa", co_san_xuat_bot=0,
                    san_pham_bot="BDN", co_sua=1, can_ve_sinh_sua=1))
R.SXQCRound.tinh_boi_canh(d)
kiem("tắt bột → cờ sữa về 0", d.co_sua == 0 and d.can_ve_sinh_sua == 0)
frappe.get_all = _ga

print("\n-- W02: rây kiểm RY-01 theo máy nghiền M1 / M2 --")
kiem("máy nghiền mang mã M1 / M2", M.ten_may_so("nghien", 1) == "M1" and M.ten_may_so("nghien", 2) == "M2")
kiem("nhóm chưa có mã (máy rang) vẫn là 'máy k'", M.ten_may_so("rang", 3) == "máy 3")
kiem("7a / 7b / 7c theo từng máy, máy 2 đi sau trọn máy 1",
     [m["f"] for m in M.MUC if m["may"] == "nghien"]
     == ["do_min_dat", "hat_tho", "di_vat_ray", "do_min_dat_m2", "hat_tho_m2", "di_vat_ray_m2"])
kiem("máy 1 giữ fieldname cũ do_min_dat (phiếu cũ đọc nguyên)", M.THEO_F["do_min_dat"]["so"] == "7a")
kiem("nhãn máy 2 ghi M2", M.THEO_F["hat_tho_m2"]["nhan"].endswith("M2"))
kiem("hạt thô là ô ĐẾM: 0 hạt = đã kiểm (cả ô máy 2)",
     M.co_ghi(M.THEO_F["hat_tho"], 0) and M.co_ghi(M.THEO_F["hat_tho_m2"], 0))
kiem("chưa có ngưỡng hạt thô → 5 hạt KHÔNG thành sự cố", not sc(hat_tho=5))
cb = SC.canh_bao(Doc(luot="Đầu sáng", phien_ban=2, hat_tho=5))
kiem("… nhưng có cảnh báo ghi M1", any("5 hạt thô" in c and "M1" in c for c in cb), str(cb))
CAI_DAT["hat_tho_toi_da"] = "0"
kiem("ngưỡng '0' (không cho hạt nào) là ngưỡng THẬT → 1 hạt = sự cố oPRP-2",
     [(x[2],) for x in sc(hat_tho=1)] == [("oPRP",)])
kiem("ngưỡng 0, 0 hạt → không sự cố", not sc(hat_tho=0))
CAI_DAT["hat_tho_toi_da"] = "3"
kiem("ngưỡng 3: máy 2 có 4 hạt → sự cố ghi M2",
     [x[0] for x in sc(so_may_nghien=2, hat_tho_m2=4)] == ["hat_tho_m2"]
     and "M2" in sc(so_may_nghien=2, hat_tho_m2=4)[0][4])
CAI_DAT["hat_tho_toi_da"] = ""
kiem("ô ngưỡng để trống → chưa đặt (không phải 0)", NG.nguong()["hat_tho_toi_da"] is None)
CAI_DAT.pop("hat_tho_toi_da")
r = sc(di_vat_ray=1)
kiem("có dị vật trên rây → sự cố oPRP mức CAO, ghi M1",
     [(x[2], x[3]) for x in r] == [("oPRP", "Cao")] and "M1" in r[0][4], str(r))
kiem("máy 2 không chạy → dị vật ghi nhầm ở ô máy 2 không thành sự cố",
     not sc(so_may_nghien=1, di_vat_ray_m2=1))
kiem("ô dị vật là ô đi kèm (không tính vào x/y)", M.THEO_F["di_vat_ray"]["phu"])

print("\n-- tờ in / CSV / JSON --")
kiem("tờ in: mục chuyển đổi in Đ / K / KCĐ",
     [Q._in_gia_tri(cd, v) for v in ("Đạt", "Không đạt", "Không có chuyển đổi", "")]
     == ["Đ", "K", "KCĐ", "—"])
kiem("CSV: mục chuyển đổi in đủ chữ", Q._in_csv(cd, "Không có chuyển đổi") == "Không có chuyển đổi")
ds = open("sx/qc/day_sheet.html", encoding="utf-8").read()
kiem("tờ in có chú thích KCĐ", "KCĐ = không có chuyển đổi" in ds)
qsrc = open("sx/api/qc.py", encoding="utf-8").read()
kiem("tờ in bỏ hàng của mục không có trong bộ mục nào của ngày (T11 sau D129)",
     "M.con_hieu_luc(m, pb) for pb in pb_ngay" in qsrc)
jd = {f["fieldname"]: f for f in json.load(open(
    "sx/qc/doctype/sx_qc_round/sx_qc_round.json", encoding="utf-8"))["fields"]}
kiem("phiếu có ô phiên bản (chỉ đọc)", jd["phien_ban"]["fieldtype"] == "Int"
     and jd["phien_ban"].get("read_only"))
kiem("cờ sữa do server tính (chỉ đọc)", jd["co_sua"].get("read_only") and jd["can_ve_sinh_sua"].get("read_only"))
kiem("mục chuyển đổi: ba lựa chọn + trống",
     jd["a5_chuyen_doi"]["options"].split("\n") == ["", "Không có chuyển đổi", "Đạt", "Không đạt"])
kiem("có section 5. Ủ", "section_buoc_5" in jd)
st = {f["fieldname"]: f for f in json.load(open(
    "sx/qc/doctype/sx_qc_setting/sx_qc_setting.json", encoding="utf-8"))["fields"]}
kiem("Setting: ngưỡng hạt thô là ô chữ (để trống được, 0 là ngưỡng thật)",
     st["hat_tho_toi_da"]["fieldtype"] == "Data")
kiem("Setting: danh sách vị có sữa bột", "bot_co_sua" in st)

print("\n-- màn hình --")
rj = open("sx/public/sx/views/qc_round.js", encoding="utf-8").read()
kiem("màn lượt vẽ mục chuyển đổi bằng ba nút", "m.kieu === 'chon_cd'" in rj and "const CD = [" in rj)
kiem("màn lượt hiện mã máy (M1 / M2)", "tenMay(nm, m.may_so)" in rj)
kiem("thanh tiến độ coi hạt thô (cả máy 2) là ô đếm", "'hat_tho'" in rj and "m.goc || m.f" in rj)
uj = open("sx/public/sx/components/qcui.js", encoding="utf-8").read()
kiem("ô số: hạt thô có nút − / +", "'hat_tho'].includes(goc)" in uj)
kiem("ô số rang lạc tô đỏ cả khi vượt trần (W03)", "`${k}_max`" in uj)
kiem("get_today gửi mã máy", '"ma": list(M.MA_MAY.get(n, ()))' in qsrc)

print()
if hong:
    print(f"QCV2-HỎNG ({hong})")
    sys.exit(1)
print("QCV2-OK")
