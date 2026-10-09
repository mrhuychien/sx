"""D133 (W07) — lưu mẫu 1 năm từ NSX, gắn lô, giữ mẫu của lô có sự cố, huỷ tháng
có Ban ISO xác nhận.

Vì sao phải có bài này: mọi lỗi ở đây đều IM LẶNG cho tới đúng ngày cần mẫu.
  · Hạn lưu tính sai (180 ngày, hay từ ngày lấy thay vì NSX) → mẫu bị huỷ trong
    lúc sản phẩm cùng lô còn hạn trên kệ — khách khiếu nại thì tủ trống.
  · Mẫu của lô đang có sự cố / khiếu nại lọt vào đợt huỷ → mất bằng chứng.
  · QC tự huỷ được → "Ban ISO xác nhận" chỉ còn trên giấy.
  · Đợt huỷ ghi "đã huỷ" cả mẫu đã lấy ra / đang giữ → biên bản nói dối.

Nạp sx/api/qc.py, sx/qc/giu_mau.py, nhac.py, nguong.py, controller SX QC Luu Mau,
patch d133 THẬT; frappe là giả. Biên bản in bằng jinja2 thật (nếu máy có).
Chạy: python3 scripts/test-luumau.py   (verify.sh gọi sẵn)
"""

import calendar
import importlib.util
import json
import os
import re
import sys
import types
from datetime import date, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

HOM_NAY = date(2026, 10, 8)
LM = []            # SX QC Luu Mau
DOT = []           # SX QC Dot Huy Mau
DOT_ITEM = []      # SX QC Dot Huy Mau Item (dòng con — đọc qua DOT[i]["ds"])
SU_CO = []         # SX Su Co
SU_CO_LO = []      # SX Su Co Lo — bảng Lô liên quan của phiếu sự cố (W11, D134)
BATCH = [
    {"name": "SEN-HSD270405", "item": "TP-SEN", "manufacturing_date": date(2026, 7, 5),
     "expiry_date": date(2027, 4, 5), "batch_qty": 120, "disabled": 0},
    {"name": "SEN-HSD270301", "item": "TP-SEN", "manufacturing_date": date(2026, 6, 1),
     "expiry_date": date(2027, 3, 1), "batch_qty": 0, "disabled": 0},
    {"name": "SEN-CU", "item": "TP-SEN", "manufacturing_date": None,
     "expiry_date": None, "batch_qty": 5, "disabled": 0},          # lô cũ chưa có HSD
    {"name": "SEN-TAT", "item": "TP-SEN", "manufacturing_date": date(2026, 1, 1),
     "expiry_date": date(2026, 10, 1), "batch_qty": 0, "disabled": 1},
    {"name": "DUA-HSD270210", "item": "TP-DUA", "manufacturing_date": date(2026, 5, 10),
     "expiry_date": date(2027, 2, 10), "batch_qty": 40, "disabled": 0},
    {"name": "BOT-HSD250228", "item": "TP-BOT", "manufacturing_date": date(2024, 2, 29),
     "expiry_date": date(2025, 2, 28), "batch_qty": 1, "disabled": 0},
]
ITEM = [{"name": "TP-SEN", "item_name": "Bánh đậu xanh sen"},
        {"name": "TP-DUA", "item_name": "Bánh đậu xanh dừa"},
        {"name": "TP-BOT", "item_name": "Bột đậu xanh dinh dưỡng"}]
CAI_DAT = {}
VAI = {"SX QC"}
NGUOI = {"u": "qc@x"}
DA_MIGRATE = {"v": True}     # False = site chưa migrate D134 (chưa có cờ diễn tập / bảng lô)


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
    return {"SX QC Luu Mau": LM, "SX QC Dot Huy Mau": DOT, "SX QC Dot Huy Mau Item": DOT_ITEM,
            "SX Su Co": SU_CO, "SX Su Co Lo": SU_CO_LO, "Batch": BATCH,
            "Item": ITEM}.get(dt, [])


def _so(x):
    return str(x) if x is not None else ""


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "<=" and not (x is not None and _so(x) <= _so(m)):
                return False
            if op == "in" and x not in m:
                return False
            if op == "is" and m == "set" and not x:
                return False
            if op == "like":
                if m.strip("%").lower() not in _so(x).lower():
                    return False
        elif _so(x) != _so(v):
            return False
    return True


def get_all(dt, filters=None, fields=None, pluck=None, limit=None, order_by=None,
            or_filters=None, **k):
    if not DA_MIGRATE["v"] and (dt == "SX Su Co Lo" or (dt == "SX Su Co" and "dien_tap" in (filters or {}))):
        raise Loi("Unknown column 'dien_tap' / bảng SX Su Co Lo chưa có")
    ra = [Doc(h) for h in _bang(dt) if _khop(h, filters)]
    if or_filters:
        ra = [h for h in ra if any(_khop(h, {kk: vv}) for kk, vv in or_filters.items())]
    ob = (order_by or "").split(",")[0].strip()
    if ob:
        cot, *chieu = ob.split()
        ra.sort(key=lambda h: _so(h.get(cot)), reverse=bool(chieu and chieu[0] == "desc"))
    if limit:
        ra = ra[:limit]
    return [h.get(pluck) for h in ra] if pluck else ra


class LMDoc(Doc):
    """Bản sao như Frappe thật: get_doc đọc ra bản sao, chỉ save() mới ghi lại."""

    def insert(self, **kw):
        type(self).validate(self)
        self["name"] = f"LM-{len(LM) + 1:04d}"
        LM.append(Doc(self))
        return self

    def save(self, **kw):
        cu = next(h for h in LM if h["name"] == self["name"])
        self["_cu"] = dict(cu)
        type(self).validate(self)
        self.pop("_cu", None)
        cu.update(self)
        return self

    def has_value_changed(self, f):
        cu = self.get("_cu")
        return cu is None or cu.get(f) != self.get(f)


class DotDoc(Doc):
    def append(self, f, row):
        self.setdefault(f, []).append(Doc(row))

    def insert(self, **kw):
        self["name"] = f"HM-2026-{len(DOT) + 1:03d}"
        for i, r in enumerate(self.get("ds") or []):
            r["name"] = f"{self['name']}-r{i + 1}"
            r["parent"] = self["name"]
            r["parenttype"] = "SX QC Dot Huy Mau"
            DOT_ITEM.append(r)
        self["creation"] = f"2026-10-08 10:00:{len(DOT):02d}"
        DOT.append(self)
        return self

    def db_set(self, f, v=None, **kw):
        self.update(f if isinstance(f, dict) else {f: v})


def _get_doc(x, n=None):
    if isinstance(x, dict):
        if x.get("doctype") == "SX QC Luu Mau":
            return LMC.SXQCLuuMau(x)
        if x.get("doctype") == "SX QC Dot Huy Mau":
            return DotDoc(x)
        return Doc(x)
    if x == "SX QC Luu Mau":
        return LMC.SXQCLuuMau(dict(next(h for h in LM if h["name"] == n)))
    if x == "SX QC Dot Huy Mau":
        return next(h for h in DOT if h["name"] == n)
    raise Loi(f"get_doc {x}")


def _get_value(dt, f, fld=None, as_dict=False, **k):
    h = next((h for h in _bang(dt) if (h["name"] == f if isinstance(f, str) else _khop(h, f))), None)
    if h is None:
        return None
    if isinstance(fld, (list, tuple)):
        d = Doc({c: h.get(c) for c in fld})
        return d if as_dict else tuple(d.values())
    return h.get(fld)


def _set_value(dt, n, f, v=None, **k):
    h = next(h for h in _bang(dt) if h["name"] == n)
    h.update(f if isinstance(f, dict) else {f: v})


try:
    import jinja2
except ImportError:      # máy không có jinja2: bỏ phần biên bản, phần khác vẫn chạy
    jinja2 = None


def _render(path, ctx):
    if jinja2 is None:
        return ""
    env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    fu_in = types.SimpleNamespace(formatdate=lambda d, f=None: fu.getdate(d).strftime("%d/%m/%Y"),
                                  format_datetime=lambda d, f=None: str(d))
    return env.get_template(path).render(frappe=types.SimpleNamespace(utils=fu_in), **ctx)


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
class _PhienLam:
    user = property(lambda s: NGUOI["u"])


frappe.session = _PhienLam()
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_doc = _get_doc
frappe.get_cached_doc = lambda dt: Doc(CAI_DAT)
frappe.get_meta = lambda dt: types.SimpleNamespace(has_field=lambda f: True)
frappe.render_template = lambda p, ctx: _render("sx/" + p.split("sx/", 1)[1], ctx)
frappe.db = types.SimpleNamespace(
    get_value=_get_value,
    count=lambda dt, f=None: len(get_all(dt, f)),
    table_exists=lambda dt: True,
    set_value=_set_value,
)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.getdate = lambda x=None: (x if isinstance(x, date) else
                             date.fromisoformat(str(x)[:10]) if x else HOM_NAY)
fu.nowdate = lambda: str(HOM_NAY)
fu.add_days = lambda d, n: fu.getdate(d) + timedelta(days=n)


def _add_months(d, n):        # như frappe.utils.add_months (relativedelta): kẹp cuối tháng
    d = fu.getdate(d)
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


fu.add_months = _add_months
fu.get_datetime = lambda x=None: x
fu.get_time = lambda x=None: x
fu.time_diff_in_seconds = lambda a, b: 0
fu.now_datetime = lambda: "2026-10-08 10:00:00"
fu.formatdate = str
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
mdl = types.ModuleType("frappe.model"); mdl.__path__ = []
dm = types.ModuleType("frappe.model.document"); dm.Document = LMDoc
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


nap("sx.qc.muc", "sx/qc/muc.py")
NG = nap("sx.qc.nguong", "sx/qc/nguong.py")
nap("sx.qc.quyen", "sx/qc/quyen.py")
nap("sx.qc.san_pham", "sx/qc/san_pham.py")
nap("sx.qc.su_co", "sx/qc/su_co.py")
nap("sx.qc.xuat", "sx/qc/xuat.py")
NH = nap("sx.qc.nhac", "sx/qc/nhac.py")
nap("sx.qc.khieu_nai", "sx/qc/khieu_nai.py")
GM = nap("sx.qc.giu_mau", "sx/qc/giu_mau.py")
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
Q = nap("sx.api.qc", "sx/api/qc.py")
P = nap("sx.patches.d133_luu_mau_mot_nam", "sx/patches/d133_luu_mau_mot_nam.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


def thu(f):
    try:
        f()
    except Exception as e:  # noqa: BLE001
        return str(e) or type(e).__name__
    return None


def vai(*v, u=None):
    VAI.clear(); VAI.update(v)
    NGUOI["u"] = u or {"SX QC": "qc@x", "ISO Manager": "iso@x"}.get(v[0], "x@x")


def tao(**kw):
    p = {"san_pham": "TP-SEN", "so_luong": 2, **kw}
    return Q.tao_luu_mau(json.dumps(p))


def lm(name):
    return next(h for h in LM if h["name"] == name)


# ═══ 1. Hạn lưu: 1 năm từ NSX ═════════════════════════════════════════════
print("\n-- hạn lưu 12 tháng từ NSX, gắn lô --")
r = tao(batch="SEN-HSD270405")
x = lm(r["name"])
kiem("gắn lô → NSX / HSD lấy từ lô", (x["nsx"], x["hsd"]) == (date(2026, 7, 5), date(2027, 4, 5)))
kiem("hạn lưu = NSX + 12 tháng (KHÔNG phải ngày lấy + 180 ngày)",
     x["han_luu"] == date(2027, 7, 5), str(x["han_luu"]))
kiem("lô bỏ trống → tự ghi 'HSD dd/mm/yyyy' (tìm theo chữ vẫn ra)", x["lo"] == "HSD 05/04/2027", x["lo"])
r = tao(batch="SEN-HSD270405", lo="HSD 05/04/27 hộp 2")
kiem("lô ghi tay giữ nguyên", lm(r["name"])["lo"] == "HSD 05/04/27 hộp 2")
r = tao()
kiem("không gắn lô → hạn = ngày lấy + 12 tháng", lm(r["name"])["han_luu"] == date(2027, 10, 8))
r = tao(han_luu="2027-12-31", batch="SEN-HSD270405")
kiem("QC tự sửa hạn → dùng đúng ngày đã sửa", lm(r["name"])["han_luu"] == date(2027, 12, 31))
CAI_DAT["luu_mau_so_thang"] = 18
r = tao(batch="SEN-HSD270405")
kiem("số tháng lấy từ SX QC Setting", lm(r["name"])["han_luu"] == date(2028, 1, 5))
CAI_DAT.clear()
r = tao(san_pham="TP-BOT", batch="BOT-HSD250228", ngay_lay="2024-03-01")
kiem("NSX 29/02 + 12 tháng → 28/02 năm sau (kẹp cuối tháng)",
     lm(r["name"])["han_luu"] == date(2025, 2, 28), str(lm(r["name"])["han_luu"]))
loi = thu(lambda: tao(batch="DUA-HSD270210"))
kiem("lô của MÃ KHÁC → chặn", loi and "mã khác" in loi, loi or "")
loi = thu(lambda: tao(batch="KHONG-CO"))
kiem("lô không tồn tại → chặn", loi and "Không thấy lô" in loi, loi or "")
kiem("API: hạn mặc định trong list = hôm nay + 12 tháng, so_thang_luu = 12",
     (Q.list_luu_mau()["han_mac_dinh"], Q.list_luu_mau()["so_thang_luu"]) == ("2027-10-08", 12))

print("\n-- chọn lô khi lấy mẫu (lo_cua_sp) --")
ds = Q.lo_cua_sp("TP-SEN")
kiem("chỉ lô của đúng mã, có HSD, chưa tắt — HSD mới nhất trước",
     [d["batch"] for d in ds] == ["SEN-HSD270405", "SEN-HSD270301"], [d["batch"] for d in ds])
kiem("mỗi lô kèm NSX, HSD và hạn lưu NSX + 12 tháng",
     (ds[0]["hsd"], ds[0]["nsx"], ds[0]["han_luu"]) == ("2027-04-05", "2026-07-05", "2027-07-05"))
kiem("chưa chọn sản phẩm → rỗng", Q.lo_cua_sp("") == [])
vai("SX Vao Hop")
kiem("người ngoài QC không tra lô được", thu(lambda: Q.lo_cua_sp("TP-SEN")) is not None)
vai("SX QC")

# ═══ 2. Giữ mẫu ═══════════════════════════════════════════════════════════
print("\n-- giữ mẫu: hàm thuần ly_do_giu --")
M1 = {"name": "A", "batch": "SEN-HSD270405", "hsd": date(2027, 4, 5)}
M2 = {"name": "B", "batch": None, "hsd": None, "giu_lai": 1, "ly_do_giu": "KH Hà Nội báo mốc"}
M3 = {"name": "C", "batch": None, "hsd": None}
sc = lambda **k: {"name": "SC-1", "lo": [], "lo_anh_huong": "", **k}  # noqa: E731
kiem("bấm Giữ lại → giữ, kèm lý do", GM.ly_do_giu([M2], [])["B"] == "Giữ lại: KH Hà Nội báo mốc")
kiem("phiếu sự cố gắn đúng lô (bảng Lô liên quan) → giữ, nêu phiếu",
     "SC-1" in GM.ly_do_giu([M1], [sc(lo=["SEN-HSD270301", "SEN-HSD270405"])]).get("A", ""))
for chu in ("HSD 05/04/2027 vị sen", "hsd 05/04/27", "lô 05.04.2027", "05-04-2027", "2027-04-05",
            "lô SEN-HSD270405"):
    kiem(f"ô 'lô ảnh hưởng' ghi '{chu}' → giữ", "A" in GM.ly_do_giu([M1], [sc(lo_anh_huong=chu)]))
kiem("HSD khác → KHÔNG giữ", GM.ly_do_giu([M1], [sc(lo_anh_huong="HSD 06/04/2027")]) == {})
kiem("lô khác (bảng lô) → KHÔNG giữ", GM.ly_do_giu([M1], [sc(lo=["SEN-HSD270301"])]) == {})
kiem("mẫu không lô / không HSD: phiếu sự cố không khớp được → không giữ",
     GM.ly_do_giu([M3], [sc(lo_anh_huong="HSD 05/04/2027")]) == {})
kiem("không có phiếu nào mở → không giữ", GM.ly_do_giu([M1], []) == {})
SU_CO[:] = [{"name": "SC-9", "trang_thai": "Đóng", "dien_tap": 0, "lo_anh_huong": ""}]
SU_CO_LO[:] = [{"parent": "SC-9", "parenttype": "SX Su Co", "batch": "SEN-HSD270405"}]
kiem("phiếu ĐÃ ĐÓNG không giữ mẫu nữa (đọc từ DB)", GM.ly_do_giu([M1]) == {})
SU_CO[:] = [{"name": "SC-2", "trang_thai": "Mở", "dien_tap": 0,
             "lo_anh_huong": "HSD 05/04/2027", "nguon": "Khiếu nại"}]
DA_MIGRATE["v"] = False
kiem("site chưa migrate D134 → vẫn khớp theo chữ, không vỡ",
     "SC-2" in GM.ly_do_giu([M1]).get("A", ""))
DA_MIGRATE["v"] = True
SU_CO[:] = [{"name": "SC-3", "trang_thai": "Mở", "dien_tap": 1, "lo_anh_huong": "HSD 05/04/2027",
             "nguon": "Phát hiện khác"}]
SU_CO_LO[:] = [{"parent": "SC-3", "parenttype": "SX Su Co", "batch": "SEN-HSD270405"}]
kiem("phiếu DIỄN TẬP (kể cả gắn đúng lô) → KHÔNG giữ mẫu", GM.ly_do_giu([M1]) == {})
SU_CO[0]["dien_tap"] = 0
kiem("… cùng phiếu đó không diễn tập → giữ (đọc bảng lô từ DB)", "SC-3" in GM.ly_do_giu([M1]).get("A", ""))
SU_CO.clear(); SU_CO_LO.clear()

print("\n-- giữ mẫu qua API --")
LM.clear()
a = tao(batch="SEN-HSD270405", ngay_lay="2025-06-01", han_luu="2026-09-01")["name"]
b = tao(batch="SEN-HSD270301", ngay_lay="2025-06-01", han_luu="2026-09-01")["name"]
c = tao(ngay_lay="2025-06-01", han_luu="2026-10-08")["name"]          # đến hạn đúng hôm nay
d_ = tao(ngay_lay="2026-06-01", han_luu="2026-12-01")["name"]         # còn hạn
loi = thu(lambda: Q.giu_mau(c, 1, ""))
kiem("giữ không lý do → chặn", loi and "lý do" in loi, loi or "")
kiem("… và mẫu không bị đánh dấu giữ", not lm(c).get("giu_lai"))
Q.giu_mau(c, 1, "Khiếu nại đại lý Nam Định 03/10")
kiem("giữ có lý do → giu_lai = 1", lm(c)["giu_lai"] == 1 and "Nam Định" in lm(c)["ly_do_giu"])
SU_CO[:] = [{"name": "SC-7", "trang_thai": "Mở", "dien_tap": 0, "lo_anh_huong": "",
             "nguon": "Khiếu nại"}]
SU_CO_LO[:] = [{"parent": "SC-7", "parenttype": "SX Su Co", "batch": "SEN-HSD270405"}]
kq = Q.list_luu_mau()
theo = {x["name"]: x for x in kq["danh_sach"]}
kiem("list: mẫu của lô có khiếu nại mở → kèm lý do giữ", "SC-7" in (theo[a]["giu"] or ""))
kiem("list: mẫu bấm giữ → kèm lý do", "Nam Định" in (theo[c]["giu"] or ""))
kiem("list: số đến hạn KHÔNG tính mẫu đang giữ", kq["so_den_han"] == 1, kq["so_den_han"])
kiem("list: NSX / HSD trả dạng chuỗi", theo[a]["nsx"] == "2026-07-05" and theo[a]["hsd"] == "2027-04-05")
vai("SX Vao Hop")
kiem("người ngoài QC không giữ được", thu(lambda: Q.giu_mau(b, 1, "x")) is not None)
vai("ISO Manager")
kiem("Ban ISO giữ được (người xem xét khiếu nại)", thu(lambda: Q.giu_mau(d_, 1, "điều tra")) is None)
Q.giu_mau(d_, 0)
kiem("bỏ giữ → giu_lai = 0, lý do cũ còn (lịch sử)", lm(d_)["giu_lai"] == 0 and lm(d_)["ly_do_giu"])
vai("SX QC")

# ═══ 3. QC không tự huỷ; Ban ISO huỷ lẻ có luật ══════════════════════════════
print("\n-- quyền huỷ --")
kiem("list: QC không có quyền huỷ, có quyền ghi",
     (kq["duoc_huy"], kq["duoc_ghi"]) == (False, True))
loi = thu(lambda: Q.xu_ly_luu_mau(b, "huy", "hết hạn"))
kiem("QC huỷ lẻ → chặn, chỉ đường ĐỀ XUẤT HUỶ", loi and "ĐỀ XUẤT HUỶ" in loi, loi or "")
vai("ISO Manager")
kiem("list: Ban ISO có quyền huỷ", Q.list_luu_mau()["duoc_huy"] is True)
loi = thu(lambda: Q.xu_ly_luu_mau(a, "huy", "mốc"))
kiem("Ban ISO huỷ lẻ mẫu ĐANG GIỮ (lô có khiếu nại) → chặn", loi and "GIỮ" in loi, loi or "")
kiem("… mẫu vẫn Đang lưu", lm(a)["trang_thai"] == "Đang lưu")
vai("SX QC")

# ═══ 4. Đề xuất đợt huỷ ═══════════════════════════════════════════════════
print("\n-- đề xuất đợt huỷ tháng --")
vai("ISO Manager")
kiem("Ban ISO không tự đề xuất (người xác nhận không tự lập)",
     thu(lambda: Q.de_xuat_huy()) is not None)
vai("SX QC")
r = Q.de_xuat_huy("tháng 10")
dot = DOT[-1]
kiem("đợt chỉ gồm mẫu ĐẾN HẠN và KHÔNG bị giữ", [x["luu_mau"] for x in dot["ds"]] == [b],
     [x["luu_mau"] for x in dot["ds"]])
kiem("đợt: Chờ xác nhận, tháng 10/2026, ghi người lập",
     (dot["trang_thai"], dot["thang"], dot["lap_boi"]) == ("Chờ xác nhận", "10/2026", "qc@x"))
kiem("mẫu trong đợt → Chờ huỷ, gắn đợt (CHƯA huỷ)",
     (lm(b)["trang_thai"], lm(b)["dot_huy"]) == ("Chờ huỷ", dot["name"]))
kiem("mẫu đang giữ / còn hạn → vẫn Đang lưu",
     [lm(n)["trang_thai"] for n in (a, c, d_)] == ["Đang lưu"] * 3)
kiem("dòng đợt chép đủ thông tin cho biên bản",
     (dot["ds"][0]["ten_san_pham"], dot["ds"][0]["lo_hsd"]) == ("Bánh đậu xanh sen", "HSD 01/03/2027"))
loi = thu(lambda: Q.de_xuat_huy())
kiem("còn đợt chờ xác nhận → không đề xuất đợt mới", loi and "chờ Ban ISO" in loi, loi or "")
kq = Q.list_luu_mau(trang_thai="Chờ huỷ")
kiem("list: đợt chờ hiện kèm số mẫu", [(x["name"], x["so_mau"]) for x in kq["dot_cho"]]
     == [(dot["name"], 1)])
kiem("list tab Chờ huỷ: có mẫu của đợt", [x["name"] for x in kq["danh_sach"]] == [b])

print("\n-- Ban ISO xác nhận --")
kiem("QC không tự xác nhận đợt của mình", thu(lambda: Q.xac_nhan_huy(dot["name"])) is not None)
# Giữa lúc đề xuất và lúc xác nhận: một mẫu mới vào đợt sau, rồi lô đó có khiếu nại.
LM_THEM = tao(batch="SEN-HSD270301", ngay_lay="2025-06-01", han_luu="2026-09-02")["name"]
LM_RA = tao(ngay_lay="2025-06-01", han_luu="2026-09-03")["name"]
DOT.pop(); DOT_ITEM.clear()
for n in (b, LM_THEM, LM_RA):
    lm(n).update(trang_thai="Đang lưu", dot_huy=None)
Q.de_xuat_huy()
dot = DOT[-1]
kiem("đợt mới gồm 3 mẫu", len(dot["ds"]) == 3)
SU_CO.append({"name": "SC-8", "trang_thai": "Mở", "dien_tap": 0,
              "lo_anh_huong": "HSD 01/03/2027 — đại lý báo chua", "nguon": "Khiếu nại"})
Q.xu_ly_luu_mau(LM_RA, "lay_ra", "gửi kiểm nghiệm Quatest 3")
kiem("mẫu Chờ huỷ vẫn LẤY RA được (khiếu nại tới giữa chừng)", lm(LM_RA)["trang_thai"] == "Đã lấy ra")
vai("ISO Manager")
kiem("mẫu Chờ huỷ không huỷ lẻ được (đi theo đợt)",
     "đã ở trạng thái" in (thu(lambda: Q.xu_ly_luu_mau(b, "huy", "x")) or ""))
r = Q.xac_nhan_huy(dot["name"], 1, "đã đốt tại lò")
kiem("kết quả: 0 huỷ, 2 giữ (lô HSD 01/03/2027 vừa có khiếu nại), 1 đã lấy ra",
     (r["da_huy"], r["giu_lai"]) == (0, 2), r)
kiem("mẫu bị giữ → về Đang lưu, bỏ gắn đợt",
     [(lm(n)["trang_thai"], lm(n)["dot_huy"]) for n in (b, LM_THEM)] == [("Đang lưu", None)] * 2)
kiem("mẫu đã lấy ra giữ nguyên Đã lấy ra", lm(LM_RA)["trang_thai"] == "Đã lấy ra")
kq_dong = {x["luu_mau"]: x.get("ket_qua") for x in dot["ds"]}
kiem("dòng đợt ghi kết quả thật: Giữ lại — lý do / Đã lấy ra",
     kq_dong[b].startswith("Giữ lại") and "SC-8" in kq_dong[b] and kq_dong[LM_RA] == "Đã lấy ra",
     kq_dong)
kiem("đợt → Đã huỷ, ghi người + giờ xác nhận + ghi chú Ban ISO",
     (dot["trang_thai"], dot["xac_nhan_boi"]) == ("Đã huỷ", "iso@x")
     and "Ban ISO: đã đốt tại lò" in dot["ghi_chu"])
loi = thu(lambda: Q.xac_nhan_huy(dot["name"]))
kiem("xác nhận lần hai → chặn", loi and "không còn chờ" in loi, loi or "")

print("\n-- huỷ thật + trả lại --")
SU_CO.clear(); SU_CO_LO.clear()
vai("SX QC")
Q.de_xuat_huy()
dot = DOT[-1]
vai("ISO Manager")
loi = thu(lambda: Q.xac_nhan_huy(dot["name"], 0))
kiem("trả lại không lý do → chặn", loi and "lý do" in loi, loi or "")
Q.xac_nhan_huy(dot["name"], 0, "thiếu mẫu ngăn B3, kiểm lại tủ")
kiem("trả lại → mọi mẫu về Đang lưu, đợt 'Trả lại', ghi lý do",
     all(lm(x["luu_mau"])["trang_thai"] == "Đang lưu" for x in dot["ds"])
     and dot["trang_thai"] == "Trả lại" and "Ban ISO trả lại: thiếu mẫu" in dot["ghi_chu"]
     and all(x["ket_qua"] == "Trả lại" for x in dot["ds"]))
vai("SX QC")
Q.de_xuat_huy()
dot = DOT[-1]
vai("ISO Manager")
r = Q.xac_nhan_huy(dot["name"])
mau = [lm(x["luu_mau"]) for x in dot["ds"]]
kiem("khiếu nại lô đã ĐÓNG → mẫu lô đó hết giữ, vào đợt tiếp theo", a in [x["luu_mau"] for x in dot["ds"]])
kiem("đồng ý → mẫu Đã huỷ, ghi người xác nhận + lý do theo đợt",
     r["da_huy"] == len(mau) == 3
     and all(m_["trang_thai"] == "Đã huỷ" and m_["xu_ly_boi"] == "iso@x"
             and dot["name"] in m_["ly_do"] for m_ in mau), r)
kiem("mẫu bấm giữ / còn hạn không bị đụng",
     (lm(c)["trang_thai"], lm(d_)["trang_thai"]) == ("Đang lưu", "Đang lưu"))
vai("SX QC")
loi = thu(lambda: Q.de_xuat_huy())
kiem("hết mẫu đến hạn → không lập đợt rỗng", loi and "Không có mẫu" in loi, loi or "")

if jinja2:
    html = Q.in_bien_ban_huy(dot["name"])
    chu = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", html))
    kiem("biên bản: tên đợt, sản phẩm, cột Kết quả, số đã huỷ",
         dot["name"] in chu and "Bánh đậu xanh sen" in chu and "Kết quả" in chu
         and "đã huỷ 3 mẫu" in chu, chu.split("}")[-1][:400])
    kiem("biên bản: chỗ ký QC + Trưởng Ban ISO", "QC thực hiện huỷ" in chu and "Trưởng Ban ISO" in chu)
else:
    print("  (bỏ qua biên bản: máy không có jinja2)")

# ═══ 5. Controller chặn cả đường Desk ═════════════════════════════════════
print("\n-- controller (đường Desk) --")
d0 = LMC.SXQCLuuMau(dict(lm(c)))
d0.trang_thai = "Chờ huỷ"
loi = thu(lambda: d0.save())
kiem("Chờ huỷ mà không thuộc đợt nào → chặn", loi and "đợt huỷ" in loi, loi or "")
d0 = LMC.SXQCLuuMau(dict(lm(c)))
d0.trang_thai, d0.ly_do = "Đã huỷ", "dọn tủ"
loi = thu(lambda: d0.save())
kiem("Desk đổi thẳng mẫu ĐANG GIỮ sang Đã huỷ → chặn", loi and "GIỮ" in loi, loi or "")
d0 = LMC.SXQCLuuMau(dict(lm(c)))
d0.ghi_chu = "ngăn A2"
kiem("sửa ghi chú mẫu đang giữ (không đổi trạng thái) → không vướng", thu(lambda: d0.save()) is None)

# ═══ 6. Nhắc việc ═════════════════════════════════════════════════════════
print("\n-- nhắc việc --")
ra = NH._nhac_luu_mau(HOM_NAY, {"den_han": 3, "lau_nhat": "2026-09-01",
                                "dot_cho": [{"name": "HM-1", "thang": "10/2026",
                                             "lap_luc": "2026-10-01"}]})
kiem("đến hạn → nhắc ĐỀ XUẤT HUỶ, nói cái lâu nhất quá bao nhiêu ngày",
     "3 mẫu lưu" in ra[0]["tieu_de"] and "37 ngày" in ra[0]["chi_tiet"]
     and ra[0]["route"] == "#/qc/luumau", ra[0])
kiem("đợt chờ Ban ISO → nhắc, kèm số ngày chờ", "HM-1" in ra[1]["tieu_de"] and "7 ngày" in ra[1]["chi_tiet"])
kiem("không có gì → không nhắc", NH._nhac_luu_mau(HOM_NAY, {}) == [])
kiem("tinh() gộp nhắc lưu mẫu", any("mẫu lưu" in x["tieu_de"] for x in NH.tinh(
    HOM_NAY, [], [], NG.nguong_tu({}) if hasattr(NG, "nguong_tu") else Q.nguong(), None,
    {"den_han": 1, "lau_nhat": "2026-10-01"})))
LM.clear()
tao(ngay_lay="2025-06-01", han_luu="2026-10-01")
n = Q._luu_mau_nhac(HOM_NAY)
kiem("API: đếm mẫu đến hạn cho nhắc", (n["den_han"], n["lau_nhat"]) == (1, "2026-10-01"), n)
DA_MIGRATE["v"] = False
_cu = frappe.get_all
frappe.get_all = lambda *a, **k: (_ for _ in ()).throw(Loi("bảng chưa có"))
kiem("API nhắc: lỗi (chưa migrate) → {} chứ không vỡ màn QC", Q._luu_mau_nhac(HOM_NAY) == {})
frappe.get_all = _cu
DA_MIGRATE["v"] = True

# ═══ 7. Patch d133 ════════════════════════════════════════════════════════
print("\n-- patch d133: nâng hạn mẫu đang lưu lên 12 tháng --")
LM[:] = [
    Doc(name="P1", trang_thai="Đang lưu", ngay_lay=date(2026, 5, 1), han_luu=date(2026, 10, 28)),
    Doc(name="P2", trang_thai="Đang lưu", ngay_lay=date(2026, 5, 1), han_luu=date(2027, 12, 1)),
    Doc(name="P3", trang_thai="Đã huỷ", ngay_lay=date(2025, 1, 1), han_luu=date(2025, 6, 30)),
    Doc(name="P4", trang_thai="Đang lưu", ngay_lay=None, han_luu=date(2026, 11, 1)),
]
P.execute()
kiem("hạn 180 ngày → ngày lấy + 12 tháng", lm("P1")["han_luu"] == date(2027, 5, 1))
kiem("hạn dài hơn → giữ nguyên (không rút ngắn)", lm("P2")["han_luu"] == date(2027, 12, 1))
kiem("mẫu đã huỷ → không đụng", lm("P3")["han_luu"] == date(2025, 6, 30))
kiem("thiếu ngày lấy → bỏ qua", lm("P4")["han_luu"] == date(2026, 11, 1))
P.execute()
kiem("chạy lại vô hại", lm("P1")["han_luu"] == date(2027, 5, 1))
kiem("patch có trong patches.txt",
     "sx.patches.d133_luu_mau_mot_nam" in open("sx/patches.txt", encoding="utf-8").read())

# ═══ 8. DocType + màn hình ════════════════════════════════════════════════
print("\n-- DocType và màn hình --")


def truong(p):
    return {f["fieldname"]: f for f in json.load(open(p, encoding="utf-8"))["fields"]}


lmj = truong("sx/qc/doctype/sx_qc_luu_mau/sx_qc_luu_mau.json")
kiem("Lưu mẫu: lô = Link Batch; NSX / HSD chỉ đọc (lấy từ lô)",
     lmj["batch"]["options"] == "Batch" and lmj["nsx"].get("read_only") and lmj["hsd"].get("read_only"))
kiem("Lưu mẫu: có Giữ lại + lý do + đợt huỷ (Link, chỉ đọc)",
     lmj["giu_lai"]["fieldtype"] == "Check" and "ly_do_giu" in lmj
     and lmj["dot_huy"]["options"] == "SX QC Dot Huy Mau" and lmj["dot_huy"].get("read_only"))
kiem("Lưu mẫu: mọi trường API đọc đều có thật", set(Q.TRUONG_LM) <= set(lmj) | {"name"},
     set(Q.TRUONG_LM) - set(lmj) - {"name"})
dhj = json.load(open("sx/qc/doctype/sx_qc_dot_huy_mau/sx_qc_dot_huy_mau.json", encoding="utf-8"))
dh = {f["fieldname"]: f for f in dhj["fields"]}
kiem("Đợt huỷ: trạng thái khớp API", dh["trang_thai"]["options"].split("\n")
     == ["Chờ xác nhận", "Đã huỷ", "Trả lại"])
kiem("Đợt huỷ: bảng dòng → SX QC Dot Huy Mau Item, có cột Kết quả",
     dh["ds"]["options"] == "SX QC Dot Huy Mau Item" and "ket_qua" in truong(
         "sx/qc/doctype/sx_qc_dot_huy_mau_item/sx_qc_dot_huy_mau_item.json"))
quyen = {p["role"]: p for p in dhj["permissions"]}
kiem("Đợt huỷ trên Desk: Ban ISO sửa được, QC chỉ tạo / đọc (không tự đổi trạng thái)",
     quyen["ISO Manager"].get("write") and not quyen["SX QC"].get("write"))
scj = truong("sx/qc/doctype/sx_su_co/sx_su_co.json")
kiem("Sự cố có bảng Lô liên quan (W11) — phiếu gắn lô thì giữ đúng mẫu; bỏ ô lo_tp cũ",
     scj["ds_lo"]["options"] == "SX Su Co Lo" and "lo_tp" not in scj)
stj = truong("sx/qc/doctype/sx_qc_setting/sx_qc_setting.json")
kiem("Setting: số tháng lưu mặc định 12; ô số ngày cũ ẩn",
     stj["luu_mau_so_thang"].get("default") == "12" and stj["luu_mau_so_ngay"].get("hidden")
     and NG.MAC_DINH["luu_mau_so_thang"] == 12)
js = open("sx/public/sx/views/qc_luumau.js", encoding="utf-8").read()
for m in sorted(set(re.findall(r"sx\.api\.qc\.(\w+)", js))):
    kiem(f"màn Lưu mẫu gọi method có thật: {m}", callable(getattr(Q, m, None)))
kiem("màn Lưu mẫu: tab Chờ huỷ, nút ĐỀ XUẤT HUỶ, XÁC NHẬN / TRẢ LẠI, GIỮ LẠI, biên bản",
     all(t in js for t in ("'Chờ huỷ'", "ĐỀ XUẤT HUỶ", "XÁC NHẬN ĐÃ HUỶ", "TRẢ LẠI", "GIỮ LẠI",
                           "in_bien_ban_huy")))
kiem("màn Lưu mẫu: nút HUỶ MẪU lẻ chỉ hiện với người được huỷ (Ban ISO)",
     re.search(r"dl\.duoc_huy && !x\.giu\)\s*\{\s*const huy", js) is not None)
kiem("form lấy mẫu: hạn lưu KHÔNG gửi lên trừ khi người dùng tự sửa (server tính từ NSX)",
     "han_luu: ''" in js and "f.han_luu = han.value" in js)
kiem("form lấy mẫu: chọn lô qua lo_cua_sp, hiện HSD (không hiện mã lô)",
     "lo_cua_sp" in js and "`HSD ${esc(ngayVN(b.hsd))}" in js and "b.batch)}" not in js)
css = open("sx/public/sx/qc.css", encoding="utf-8").read()
kiem("CSS có kiểu cho thẻ Chờ huỷ + chip giữ", ".sx-qc-sc-cho" in css and ".sx-qc-tag-giu" in css)

print(f"\n{'LUUMAU-OK' if not hong else f'LUUMAU-FAIL ({hong})'}")
sys.exit(1 if hong else 0)
