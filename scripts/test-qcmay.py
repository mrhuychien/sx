"""D100 — phần bột QC: chọn vị, lạc theo vị, máy chạy song song, nhiệt độ hàn, lưu mẫu.

Vì sao phải có bài này: mọi thứ ở đây quyết định MỤC NÀO HIỆN RA trên lượt kiểm,
và mục không hiện ra thì không ai ghi, không in, không sinh sự cố — im lặng.

  · Lạc: B1/B2/B7 chỉ hiện khi làm vị có lạc. Sai về phía ẩn là bỏ bước kiểm
    DỊ ỨNG mà hồ sơ trông vẫn đủ. Và B7 (thử lạc sau chuyển đổi) phải hiện cả ở
    lượt SAU lượt làm chè đậu đen — chuyển đổi xảy ra ở đó.
  · Máy: máy 2/3 chỉ áp dụng khi đang chạy. Ô máy 2 ghi 240 °C phải sinh sự cố
    y như máy 1; máy không chạy thì không bắt giải trình ô trống.
  · Lưu mẫu: mẫu biến mất khỏi tủ phải có lý do.

Nạp sx/qc/muc.py, su_co.py, nguong.py, controller SX QC Round / SX QC Luu Mau,
patch d100 và sx/api/qc.py THẬT; frappe là giả.
Chạy: python3 scripts/test-qcmay.py   (verify.sh gọi sẵn)
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


def _add_months(d, n):
    import calendar
    d = fu.getdate(d)
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


fu.add_months = _add_months
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
nap("sx.qc.quyen", "sx/qc/quyen.py")
nap("sx.qc.san_pham", "sx/qc/san_pham.py")
SC = nap("sx.qc.su_co", "sx/qc/su_co.py")
nap("sx.qc.xuat", "sx/qc/xuat.py")
nap("sx.qc.nhac", "sx/qc/nhac.py")
nap("sx.qc.khieu_nai", "sx/qc/khieu_nai.py")
nap("sx.qc.giu_mau", "sx/qc/giu_mau.py")
R = nap("sx.qc.doctype.sx_qc_round.sx_qc_round",
        "sx/qc/doctype/sx_qc_round/sx_qc_round.py")
LMC = nap("sx.qc.doctype.sx_qc_luu_mau.sx_qc_luu_mau",
          "sx/qc/doctype/sx_qc_luu_mau/sx_qc_luu_mau.py")
nap("sx.qc.dong_vat", "sx/qc/dong_vat.py")
nap("sx.qc.cat", "sx/qc/cat.py")
nap("sx.qc.so_do", "sx/qc/so_do.py")
nap("sx.qc.thiet_bi", "sx/qc/thiet_bi.py")
nap("sx.qc.kiem_nghiem", "sx/qc/kiem_nghiem.py")
nap("sx.qc.viec_dinh_ky", "sx/qc/viec_dinh_ky.py")
nap("sx.qc.khac_phuc", "sx/qc/khac_phuc.py")
nap("sx.qc.vai_u", "sx/qc/vai_u.py")
nap("sx.qc.ncc", "sx/qc/ncc.py")
nap("sx.qc.kiem_xe", "sx/qc/kiem_xe.py")
nap("sx.qc.tai_lieu", "sx/qc/tai_lieu.py")
nap("sx.qc.so", "sx/qc/so.py")
Q = nap("sx.api.qc", "sx/api/qc.py")
P = nap("sx.patches.d100_qc_may_va_lac", "sx/patches/d100_qc_may_va_lac.py")


class LMDoc(LMC.SXQCLuuMau):      # có gan_lo() như controller thật
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


# ═══ 1. Máy chạy song song ═══════════════════════════════════════════════
print("-- máy: ô máy 2/3 sinh từ ô máy 1, đúng thứ tự --")
for nhom, (ten, toi_da, truong) in M.NHOM_MAY.items():
    goc = [m["f"] for m in M.MUC if m["may"] == nhom and m["may_so"] == 1]
    du = all(f"{f}_m{k}" in M.THEO_F for f in goc for k in range(2, toi_da + 1))
    kiem(f"{ten}: đủ ô cho {toi_da} máy", goc and du, str(goc))
    kiem(f"{ten}: không có máy thứ {toi_da + 1}",
         not any(f"{f}_m{toi_da + 1}" in M.THEO_F for f in goc))
thu_tu = [m["f"] for m in M.MUC if m["may"] == "rang"]
kiem("hết máy 1 rồi mới sang máy 2 (không xen nhiệt độ ba máy)",
     thu_tu[:4] == ["rang_nhiet_do", "rang_vong_quay", "rang_nhiet_do_m2",
                    "rang_vong_quay_m2"], str(thu_tu))
kiem("máy 2 giữ luật của máy 1 (bắt buộc, kiểu, ngưỡng theo ô gốc)",
     M.THEO_F["rang_nhiet_do_m2"]["batbuoc"] and M.THEO_F["rang_nhiet_do_m2"]["goc"]
     == "rang_nhiet_do")
kiem("có ô nhiệt độ hàn cho máy đóng gói bột",
     M.THEO_F["b8_nhiet_han"]["kieu"] == "nguyen" and M.THEO_F["b8_nhiet_han"]["may"]
     == "goi_bot")

print("\n-- máy: chỉ máy đang chạy mới áp dụng --")
a1 = ap(so_may_rang=1)
kiem("1 máy rang → không có ô máy 2", "rang_nhiet_do" in a1 and "rang_nhiet_do_m2" not in a1)
a2 = ap(so_may_rang=2)
kiem("2 máy rang → có máy 2, không có máy 3",
     "rang_nhiet_do_m2" in a2 and "rang_nhiet_do_m3" not in a2)
kiem("số máy vượt tối đa bị kẹp lại", M.so_may(9, "nghien") == 2 and M.so_may(0, "rang") == 1)
kiem("phiếu cũ (số máy rỗng) = 1 máy", "do_min_dat_m2" not in ap())
kiem("máy đóng gói bột chỉ áp dụng khi có bột",
     "b8_nhiet_han" not in ap(so_may_goi_bot=3)
     and {"b8_nhiet_han", "b8_nhiet_han_m3"} <= ap(co_san_xuat_bot=1, so_may_goi_bot=3))
cham2 = {m["f"] for m in M.muc_cham("Trưa", Doc(so_may_rang=2))}
kiem("máy 2 tính vào 'đã chấm x/y' khi đang chạy", "rang_nhiet_do_m2" in cham2)
kiem("gọi kiểu cũ (số 0/1) không đổi nghĩa: không có máy 2",
     not any(m["may_so"] > 1 for m in M.muc_ap_dung("Trưa", 1)))

print("\n-- máy: sự cố theo từng máy --")
CAI_DAT.clear()


def sc(**kw):
    d = Doc({"luot": "Trưa", "co_san_xuat_bot": 1, **kw})
    return SC.phat_hien(d)


r = sc(so_may_rang=2, rang_nhiet_do=260, rang_nhiet_do_m2=235)
kiem("máy 2 rang 235 °C → sự cố CAO, nói rõ máy rang M2 (W16)",
     len(r) == 1 and r[0][0] == "rang_nhiet_do_m2" and r[0][3] == "Cao"
     and "M2" in r[0][4], str(r))
kiem("máy 2 KHÔNG chạy thì số cũ trong ô đó không sinh sự cố",
     not sc(so_may_rang=1, rang_nhiet_do=260, rang_nhiet_do_m2=235))
r = sc(so_may_rang=2, rang_vong_quay_m2=9)
kiem("vòng quay máy 2 ngoài khoảng → sự cố", [x[0] for x in r] == ["rang_vong_quay_m2"])
r = sc(so_may_nghien=2, do_min_dat_m2="Không đạt")
kiem("máy nghiền 2 không đạt độ mịn → sự cố ghi mã máy M2 (W02)",
     len(r) == 1 and "M2" in r[0][4], str(r))
cb = SC.canh_bao(Doc({"luot": "Trưa", "so_may_rang": 3, "rang_nhiet_do_m3": 285}))
kiem("máy 3 vượt trần vận hành → cảnh báo nói rõ máy rang M3 (W16)",
     any("M3" in c for c in cb), str(cb))

print("\n-- nhiệt độ hàn máy đóng gói bột --")
# W03 (D128): hàn túi 150–190 °C là MẶC ĐỊNH. W38 (D168): mối hàn túi bột là PRP (D128 từng xếp oPRP).
kiem("mặc định 150–190: 90 °C → sự cố PRP",
     [x[2] for x in sc(b8_nhiet_han=90, so_may_goi_bot=1)] == ["PRP"])
kiem("mặc định 150–190: 170 °C → không sự cố", not sc(b8_nhiet_han=170))
kiem("mặc định 150–190: 195 °C → sự cố", len(sc(b8_nhiet_han=195)) == 1)
CAI_DAT.update(han_nhiet_min=140, han_nhiet_max=180)
kiem("thấp hơn ngưỡng → sự cố", [x[0] for x in sc(b8_nhiet_han=120)] == ["b8_nhiet_han"])
kiem("cao hơn ngưỡng (máy 3) → sự cố ghi máy 3",
     [x[0] for x in sc(so_may_goi_bot=3, b8_nhiet_han_m3=200)] == ["b8_nhiet_han_m3"]
     and "máy 3" in sc(so_may_goi_bot=3, b8_nhiet_han_m3=200)[0][4])
kiem("trong khoảng → không sự cố", not sc(b8_nhiet_han=160))
kiem("0 = chưa đo, không phải 0 °C", not sc(b8_nhiet_han=0))
CAI_DAT.clear()
CAI_DAT.update(han_nhiet_min=140)
kiem("chỉ sửa một đầu → đầu kia giữ mặc định (190)",
     not sc(b8_nhiet_han=145) and sc(b8_nhiet_han=100) and sc(b8_nhiet_han=400))
CAI_DAT.clear()

# ═══ 2. Lạc theo vị ══════════════════════════════════════════════════════
print("\n-- lạc: chỉ khi làm vị có lạc --")
LAC_LAM = {m["f"] for m in M.MUC if m.get("lac") == M.LAC_LAM}
LAC_DOI = {m["f"] for m in M.MUC if m.get("lac") == M.LAC_DOI}
kiem("B1, B2a/b/c là mục lạc; B7 + giờ thử là mục chuyển đổi",
     LAC_LAM == {"b1_lac_sach", "b2_rang_lac_nhiet", "b2_rang_lac_phut", "b2_lac_chin"}
     and LAC_DOI == {"b7_chuyen_doi", "b7_gio"})
kiem("có bột, KHÔNG có vị lạc → không mục lạc nào, phần bột khác vẫn có",
     not (LAC_LAM | LAC_DOI) & ap(co_san_xuat_bot=1)
     and "b3_cong_thuc" in ap(co_san_xuat_bot=1))
kiem("có vị lạc → đủ mục lạc", (LAC_LAM | LAC_DOI) <= ap(co_san_xuat_bot=1, co_lac=1))
kiem("chỉ phải thử chuyển đổi → B7 có, nhặt/rang lạc không",
     LAC_DOI <= ap(co_san_xuat_bot=1, can_thu_lac=1)
     and not LAC_LAM & ap(co_san_xuat_bot=1, can_thu_lac=1))
kiem("tắt bột thì cờ lạc cũng vô nghĩa", not (LAC_LAM | LAC_DOI) & ap(co_lac=1))
kiem("B0 (loại bột) tính vào 'đã chấm' — bật bột phải nói vị gì",
     "san_pham_bot" in {m["f"] for m in M.muc_cham("Trưa", Doc(co_san_xuat_bot=1))})

LAC = ["Chè đậu đen cốt dừa"]
kiem("khớp theo mã", M.co_lac_trong(["Chè đậu đen cốt dừa"], {}, LAC) == 1)
kiem("khớp theo TÊN, không phân biệt hoa thường / khoảng trắng",
     M.co_lac_trong(["CDD"], {"CDD": "chè  đậu đen CỐT DỪA"}, LAC) == 1)
kiem("vị khác → không lạc", M.co_lac_trong(["BDS"], {"BDS": "Bột đậu sữa dừa"}, LAC) == 0)
kiem("tên có dấu phẩy không bị tách thành hai vị",
     M.tach_chon("Bột đậu, sữa dừa\nBDM") == ["Bột đậu, sữa dừa", "BDM"])

print("\n-- lạc: B7 ở lượt SAU lượt làm chè đậu đen --")
kiem("sáng làm chè, trưa không → trưa vẫn phải thử",
     M.can_thu_lac(0, "Trưa", [("Đầu sáng", 1)]) == 1)
kiem("lượt Tuần tính như Đầu sáng", M.can_thu_lac(0, "Cuối chiều", [("Tuần", 1)]) == 1)
kiem("chiều mới làm chè → sáng KHÔNG phải thử (chưa có gì để chuyển đổi)",
     M.can_thu_lac(0, "Đầu sáng", [("Cuối chiều", 1)]) == 0)
kiem("không lượt nào làm chè → không thử", M.can_thu_lac(0, "Trưa", [("Đầu sáng", 0)]) == 0)

print("\n-- server tính cờ lạc, số máy (không nhận từ máy QC) --")
CAI_DAT.clear()


def validate(**kw):
    d = R.SXQCRound(Doc({"name": kw.pop("name", "QC-X"), "ngay": "2026-09-29",
                         "luot": "Trưa", "docstatus": 0, **kw}))
    d.kiem_trung = lambda: None
    R.SXQCRound.validate(d)
    return d


d = validate(co_san_xuat_bot=1, san_pham_bot="BDS\nChè đậu đen cốt dừa", co_lac=0)
kiem("chọn chè đậu đen → co_lac = 1 (dù máy QC gửi 0)", d.co_lac == 1 and d.can_thu_lac == 1)
d = validate(co_san_xuat_bot=1, san_pham_bot="BDS", co_lac=1, can_thu_lac=1)
kiem("chỉ sữa dừa → co_lac = 0 (máy QC không tự bật được)", d.co_lac == 0 and d.can_thu_lac == 0)
CAI_DAT["bot_co_lac"] = "Bột đậu matcha có đường"
d = validate(co_san_xuat_bot=1, san_pham_bot="BDM")
kiem("danh sách vị có lạc lấy từ SX QC Setting (khớp theo tên)", d.co_lac == 1)
d = validate(co_san_xuat_bot=1, san_pham_bot="Chè đậu đen cốt dừa")
kiem("đã khai cài đặt thì dùng đúng cài đặt, không cộng mặc định", d.co_lac == 0)
CAI_DAT.clear()
LUOT.append(Doc({"name": "QC-1", "ngay": "2026-09-29", "luot": "Đầu sáng",
                 "docstatus": 1, "co_lac": 1}))
d = validate(co_san_xuat_bot=1, san_pham_bot="BDS")
kiem("lượt sáng làm chè → lượt trưa (chỉ sữa dừa) phải thử lạc",
     d.co_lac == 0 and d.can_thu_lac == 1)
kiem("… và B7 có trong mục phải chấm", d.so_muc_ap_dung == len(M.muc_cham("Trưa", d))
     and "b7_chuyen_doi" in {m["f"] for m in M.muc_cham("Trưa", d)})
LUOT.clear()
d = validate(co_san_xuat_bot=0, san_pham_bot="Chè đậu đen cốt dừa")
kiem("không có bột → hai cờ lạc về 0", d.co_lac == 0 and d.can_thu_lac == 0)
d = validate(so_may_rang=7, so_may_nghien=0, so_may_goi_bot="2")
kiem("số máy kẹp trong [1, tối đa]",
     (d.so_may_rang, d.so_may_nghien, d.so_may_goi_bot) == (3, 1, 2))

# ═══ 3. API: danh mục vị, lượt mới nhận lại vị + số máy ══════════════════
print("\n-- API: danh mục vị bột và lượt mới --")
lb = Q._loai_bot()
kiem("danh mục vị = nhóm BTP-Bot-SP (đúng tab Bột đậu của Báo mẻ)",
     {x["item"] for x in lb} == {"Chè đậu đen cốt dừa", "BDS", "BDM"}, str(lb))
kiem("vị có lạc được đánh dấu", [x["item"] for x in lb if x["lac"]] == ["Chè đậu đen cốt dừa"])
LUOT.append(Doc({"name": "QC-1", "ngay": "2026-09-29", "luot": "Đầu sáng", "docstatus": 0,
                 "creation": "1", "san_pham_bot": "BDS", "so_may_rang": 2,
                 "so_may_nghien": 1, "so_may_goi_bot": 3}))
tr = Q._luot_truoc_cung_ngay("2026-09-29", "Trưa")
kiem("lượt trưa nhận vị + số máy của lượt sáng",
     tr and tr.san_pham_bot == "BDS" and tr.so_may_rang == 2)
kiem("lượt sáng không nhận gì từ lượt sau", Q._luot_truoc_cung_ngay("2026-09-29", "Đầu sáng") is None)
LUOT.clear()
kiem("số máy ghi được qua save_round (không bị coi là 'mục lạ')",
     set(Q.TRUONG_PHU) >= {"so_may_rang", "so_may_nghien", "so_may_goi_bot", "ghi_chu"})
kiem("tờ in: ô B0 in số vị", Q._in_gia_tri(M.THEO_F["san_pham_bot"], "A\nB") == "2 vị")
kiem("CSV: ô B0 in đủ tên", Q._in_csv(M.THEO_F["san_pham_bot"], "A\nB") == "A; B")

# ═══ 4. Lưu mẫu ══════════════════════════════════════════════════════════
print("\n-- lưu mẫu --")


def tao(**kw):
    p = {"san_pham": "TP-SEN", "so_luong": 2, "lo": "HSD 29/03/2027", **kw}
    return Q.tao_luu_mau(json.dumps(p))


r = tao()
x = LM[-1]
kiem("hạn lưu mặc định = ngày lấy + 12 tháng (W07; mẫu không gắn lô)",
     x.han_luu == date(2027, 9, 29), str(x.han_luu))
kiem("ghi tên sản phẩm, người lấy, trạng thái Đang lưu",
     (x.ten_san_pham, x.lay_boi, x.trang_thai) == ("Bánh đậu xanh sen", "qc@x", "Đang lưu"))
CAI_DAT["luu_mau_so_thang"] = 6
tao()
kiem("số tháng lưu lấy từ SX QC Setting", LM[-1].han_luu == date(2027, 3, 29))
CAI_DAT["luu_mau_so_ngay"] = 30
tao()
kiem("ô số NGÀY cũ không còn tác dụng", LM[-1].han_luu == date(2027, 3, 29))
CAI_DAT.clear()
kiem("số lượng 0 → chặn", "lớn hơn 0" in (thu(lambda: tao(so_luong=0)) or ""))
kiem("hạn lưu trước ngày lấy → chặn",
     thu(lambda: tao(ngay_lay="2026-09-29", han_luu="2026-09-01")) is not None)
kiem("chưa chọn sản phẩm → chặn", thu(lambda: tao(san_pham="")) is not None)

n = LM[0].name
kiem("lấy ra không lý do → chặn",
     "lý do" in (thu(lambda: Q.xu_ly_luu_mau(n, "lay_ra")) or ""))
kiem("… và mẫu vẫn Đang lưu", LM[0].trang_thai == "Đang lưu")
loi = thu(lambda: Q.xu_ly_luu_mau(n, "huy", "mốc"))
kiem("QC KHÔNG tự huỷ mẫu được (W07: Ban ISO xác nhận) — kể cả có lý do",
     loi is not None and "Ban ISO" in loi and LM[0].trang_thai == "Đang lưu", loi or "")
VAI.clear(); VAI.add("ISO Manager")
kiem("Ban ISO huỷ TRƯỚC hạn không lý do → chặn",
     "lý do" in (thu(lambda: Q.xu_ly_luu_mau(n, "huy")) or ""))
kiem("… và mẫu vẫn Đang lưu", LM[0].trang_thai == "Đang lưu")
kiem("Ban ISO KHÔNG lấy mẫu ra được (việc của QC)",
     thu(lambda: Q.xu_ly_luu_mau(n, "lay_ra", "x")) is not None)
VAI.clear(); VAI.add("SX QC")
Q.xu_ly_luu_mau(n, "lay_ra", "khiếu nại KH Hà Nội")
kiem("lấy ra có lý do → Đã lấy ra, ghi người + giờ",
     (LM[0].trang_thai, LM[0].xu_ly_boi) == ("Đã lấy ra", "qc@x"))
kiem("xử lý lần hai → chặn",
     "đã ở trạng thái" in (thu(lambda: Q.xu_ly_luu_mau(n, "lay_ra", "x")) or ""))
LM[1].han_luu = HOM_NAY
VAI.clear(); VAI.add("ISO Manager")
kiem("Ban ISO: hết hạn thì huỷ không cần lý do",
     thu(lambda: Q.xu_ly_luu_mau(LM[1].name, "huy")) is None
     and LM[1].trang_thai == "Đã huỷ")
VAI.clear(); VAI.add("SX QC")
kiem("thao tác lạ → chặn", thu(lambda: Q.xu_ly_luu_mau(LM[-1].name, "xoa")) is not None)
LM.clear()
tao(); tao()
LM[0].han_luu = HOM_NAY + timedelta(days=60)
LM[1].han_luu = HOM_NAY - timedelta(days=1)
kq = Q.list_luu_mau()
kiem("mẫu đến hạn đứng đầu, có cờ đến hạn",
     kq["danh_sach"][0]["den_han"] and not kq["danh_sach"][1]["den_han"])

print("\n-- ảnh lưu mẫu (D109) --")
import base64 as _b64  # noqa: E402

JPG = _b64.b64encode(b"\xff\xd8\xff\xe0" + b"x" * 2000).decode()
PNG = _b64.b64encode(b"\x89PNG\r\n\x1a\n" + b"y" * 100).decode()
LM.clear(); FILE.clear()
tao()
n = LM[0].name
kq = Q.them_anh_luu_mau(n, json.dumps([JPG, "data:image/png;base64," + PNG]))
kiem("gắn 2 ảnh: File RIÊNG TƯ, gắn đúng mẫu, đúng đuôi",
     [(f["file_name"], f["is_private"], f["attached_to_name"]) for f in FILE]
     == [(f"{n}-1.jpg", 1, n), (f"{n}-2.png", 1, n)], str(FILE))
kiem("ảnh đầu thành ảnh đại diện (thumbnail)", LM[0].anh == FILE[0]["file_url"])
Q.them_anh_luu_mau(n, json.dumps([JPG]))
kiem("thêm ảnh sau: đánh số tiếp, KHÔNG đổi ảnh đại diện",
     FILE[-1]["file_name"] == f"{n}-3.jpg" and LM[0].anh == FILE[0]["file_url"])
kiem("xem ảnh: trả đủ 3 ảnh theo thứ tự", [a["url"] for a in Q.anh_luu_mau(n)]
     == [f["file_url"] for f in FILE])
loi = thu(lambda: Q.them_anh_luu_mau(n, json.dumps([_b64.b64encode(b"%PDF-1.4 xx").decode()])))
kiem("tệp không phải ảnh → chặn", loi and "không phải ảnh" in loi, loi or "")
loi = thu(lambda: Q.them_anh_luu_mau(n, json.dumps(["@@@ hỏng"])))
kiem("base64 hỏng → chặn", loi and "hỏng" in loi, loi or "")
to = _b64.b64encode(b"\xff\xd8\xff" + b"z" * (Q.ANH_BYTE_TOI_DA + 1)).decode()
loi = thu(lambda: Q.them_anh_luu_mau(n, json.dumps([to])))
kiem("ảnh chưa nén (quá 1,5 MB) → chặn", loi and "quá lớn" in loi, loi or "")
loi = thu(lambda: Q.them_anh_luu_mau(n, json.dumps([JPG] * (Q.ANH_MOT_LAN + 1))))
kiem("quá số ảnh một lần → chặn", loi is not None)
truoc = len(FILE)
loi = thu(lambda: Q.them_anh_luu_mau(n, json.dumps([JPG, "@@@"])))
kiem("một ảnh hỏng → KHÔNG lưu ảnh nào của lần đó", loi and len(FILE) == truoc)
Q.them_anh_luu_mau(n, json.dumps([JPG] * 4))           # 3 + 4 = 7 ảnh
loi = thu(lambda: Q.them_anh_luu_mau(n, json.dumps([JPG, JPG])))
kiem("quá 8 ảnh một mẫu → chặn", loi and "tối đa" in loi, loi or "")
VAI.clear(); VAI.add("ISO Manager")
loi = thu(lambda: Q.them_anh_luu_mau(n, json.dumps([JPG])))
kiem("Ban ISO xem được ảnh nhưng KHÔNG thêm được", loi is not None
     and thu(lambda: Q.anh_luu_mau(n)) is None)
VAI.clear(); VAI.add("SX QC")
lmjs2 = open("sx/public/sx/views/qc_luumau.js", encoding="utf-8").read()
kiem("form lấy mẫu có chụp ảnh + nén trước khi gửi",
     "📷 CHỤP ẢNH" in lmjs2 and "nenAnh(" in lmjs2 and "capture', 'environment'" in lmjs2)
kiem("lưu mẫu TRƯỚC rồi mới gửi ảnh (ảnh hỏng không mất lần lấy mẫu)",
     lmjs2.index("sx.api.qc.tao_luu_mau") < lmjs2.index("guiAnh(api, r.name"))

print("\n-- lưu mẫu: quyền --")
for vai, duoc in (("SX QC Packing", True), ("ISO Manager", False),
                  ("Production Manager", False), ("SX Vao Hop", False)):
    VAI.clear(); VAI.add(vai)
    loi = thu(lambda: tao())
    kiem(f"{vai} {'lấy' if duoc else 'KHÔNG lấy'} được mẫu", (loi is None) == duoc, loi or "")
VAI.clear(); VAI.add("ISO Manager")
kiem("Ban ISO vẫn XEM được tủ mẫu", thu(lambda: Q.list_luu_mau()) is None)
VAI.clear(); VAI.add("SX Vao Hop")
kiem("người ngoài QC không xem được", thu(lambda: Q.list_luu_mau()) is not None)
VAI.clear(); VAI.add("SX QC")

# ═══ 5. Patch phiếu cũ ═══════════════════════════════════════════════════
print("\n-- patch d100: phiếu cũ giữ nguyên nghĩa --")
SQL.clear()
P.execute()
kiem("phiếu cũ có bột → bật cờ lạc (phần lạc vẫn hiện như lúc ghi)",
     any("SET co_lac = 1, can_thu_lac = 1" in q and "co_san_xuat_bot = 1" in q for q in SQL))
kiem("số máy rỗng → 1", sum("= 1 WHERE IFNULL" in q for q in SQL) == 3)
kiem("patch có trong patches.txt", "sx.patches.d100_qc_may_va_lac"
     in open("sx/patches.txt", encoding="utf-8").read())

# ═══ 6. DocType + màn hình ═══════════════════════════════════════════════
print("\n-- DocType và màn hình --")
jd = {f["fieldname"]: f for f in json.load(open(
    "sx/qc/doctype/sx_qc_round/sx_qc_round.json", encoding="utf-8"))["fields"]}
kiem("phiếu có ô số máy, mặc định 1",
     all(jd.get(t[2], {}).get("default") == "1" for t in M.NHOM_MAY.values()))
kiem("cờ lạc chỉ đọc (server tính)", jd["co_lac"].get("read_only") and jd["can_thu_lac"].get("read_only"))
kiem("B0 đủ dài cho nhiều vị", jd["san_pham_bot"]["fieldtype"] == "Small Text")
kiem("ô đo nhiệt độ hàn không mặc định 0",
     not any(jd[f].get("default") for f in jd if f.startswith("b8_nhiet_han")))
st_ = {f["fieldname"] for f in json.load(open(
    "sx/qc/doctype/sx_qc_setting/sx_qc_setting.json", encoding="utf-8"))["fields"]}
kiem("SX QC Setting có ngưỡng hàn, vị có lạc, số tháng lưu mẫu",
     {"han_nhiet_min", "han_nhiet_max", "bot_co_lac", "luu_mau_so_thang"} <= st_)
lmj = json.load(open("sx/qc/doctype/sx_qc_luu_mau/sx_qc_luu_mau.json", encoding="utf-8"))
kiem("trạng thái lưu mẫu khớp controller",
     next(f for f in lmj["fields"] if f["fieldname"] == "trang_thai")["options"].split("\n")
     == [LMC.DANG_LUU, LMC.CHO_HUY, LMC.DA_LAY_RA, LMC.DA_HUY])

qcjs = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
# D137 (W08): tab "Lưu mẫu" nằm trong tab Xuất xưởng (hai nút Kiểm xuất xưởng / Lưu mẫu).
kiem("vào được màn Lưu mẫu: route + nút trong tab Xuất xưởng",
     "luumau: '/assets/sx/sx/views/qc_luumau.js'" in qcjs and "['xuatxuong', 'Xuất xưởng']" in qcjs
     and "['luumau', 'Lưu mẫu']" in open("sx/public/sx/components/qcui.js", encoding="utf-8").read())
lmjs = open("sx/public/sx/views/qc_luumau.js", encoding="utf-8").read()
for m in sorted(set(re.findall(r"sx\.api\.qc\.(\w+)", lmjs))):
    kiem(f"màn Lưu mẫu gọi method có thật: {m}", callable(getattr(Q, m, None)))
rjs = open("sx/public/sx/views/qc_round.js", encoding="utf-8").read()
kiem("màn lượt vẽ được ô chọn vị bột", "m.kieu === 'chon_bot'" in rjs and "oChonBot" in rjs)
kiem("màn lượt có nút thêm máy + máy nghỉ", "nutThemMay" in rjs and "Máy này nghỉ" in rjs)
ui = open("sx/public/sx/components/qcui.js", encoding="utf-8").read()
kiem("ô máy 2/3 tô màu theo ngưỡng của ô gốc", "trangThaiSo(goc," in ui)
kiem("ô nhiệt độ hàn có ngưỡng trên màn hình", "'b8_nhiet_han'" in ui)

# ═══ 7. Công đoạn không chạy (D107) ═══════════════════════════════════════
print("\n-- công đoạn không chạy --")
LUOT.clear(); CAI_DAT.clear()
kiem("tắt Rang → mọi mục Rang (cả máy 2) không áp dụng",
     not {m["f"] for m in M.MUC if m["buoc"] == "3"} & ap(buoc_nghi="3", so_may_rang=2))
kiem("… các bước khác vẫn nguyên", "luoc_soi_du" in ap(buoc_nghi="3")
     and "do_min_dat" in ap(buoc_nghi="3"))
kiem("không tắt được PRP đầu ca / kho bột / lượt tuần dù gõ tay mã",
     {"a1_ve_sinh", "thung_bot_qua_han"} <= ap("Đầu sáng", buoc_nghi="A\n8\nC")
     and "t1_be_nuoc" in ap("Tuần", buoc_nghi="C"))
kiem("chuẩn hoá: bỏ mã lạ, đúng thứ tự quy trình",
     M.buoc_nghi("12\nX\n3\nA\n2") == ["2", "3", "12"])
kiem("nhiệt độ rang KHÔNG còn bắt buộc khi Rang không chạy",
     not any(m["batbuoc"] for m in M.muc_cham("Trưa", Doc(buoc_nghi="3"))))
kiem("số cũ trong ô Rang không sinh sự cố khi Rang không chạy",
     not sc(buoc_nghi="3", rang_nhiet_do=200) and sc(rang_nhiet_do=200))
kiem("vật bắt ở nam châm không cảnh báo khi Vỡ đỗ không chạy",
     not SC.canh_bao(Doc(luot="Đầu sáng", buoc_nghi="6", nam_cham_vat="ốc vít"))
     and SC.canh_bao(Doc(luot="Đầu sáng", nam_cham_vat="ốc vít")))
d = validate(buoc_nghi="12\nA\n3")
kiem("server lọc lúc lưu: chỉ giữ bước tắt được", d.buoc_nghi == "3\n12", repr(d.buoc_nghi))
kiem("… và số mục phải chấm giảm theo", d.so_muc_ap_dung == len(M.muc_cham("Trưa", d))
     and d.so_muc_ap_dung < len(M.muc_cham("Trưa", Doc())))
kiem("ghi được qua save_round (có nhật ký)", "buoc_nghi" in Q.TRUONG_PHU)
LUOT.append(Doc({"name": "QC-1", "ngay": "2026-09-29", "luot": "Đầu sáng", "docstatus": 1,
                 "creation": "1", "buoc_nghi": "3", "san_pham_bot": None}))
tr = Q._luot_truoc_cung_ngay("2026-09-29", "Trưa")
kiem("lượt sau trong ngày nhận lại công đoạn nghỉ", tr and tr.buoc_nghi == "3")
LUOT.clear()
jd2 = {f["fieldname"]: f for f in json.load(open(
    "sx/qc/doctype/sx_qc_round/sx_qc_round.json", encoding="utf-8"))["fields"]}
kiem("phiếu có ô công đoạn không chạy", jd2.get("buoc_nghi", {}).get("fieldtype") == "Small Text")
rjs2 = open("sx/public/sx/views/qc_round.js", encoding="utf-8").read()
kiem("màn lượt có hàng chọn công đoạn không chạy, gửi qua doiVaVeLai",
     "doiVaVeLai('buoc_nghi'" in rjs2 and "hom.buoc_tat_duoc" in rjs2)
html = open("sx/qc/day_sheet.html", encoding="utf-8").read()
kiem("tờ in BM.08.01 ghi rõ công đoạn không chạy", "Công đoạn không chạy" in html)

print("QCMAY-OK" if not hong else f"QCMAY: {hong} HỎNG")
sys.exit(1 if hong else 0)
