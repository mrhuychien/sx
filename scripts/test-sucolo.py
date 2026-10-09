"""D134 (W11) — phiếu sự cố BM.08.02: gắn lô, cờ diễn tập, nguồn mới, chỉ người có
quyền mới đóng.

Vì sao phải có bài này:
  · Trước D134 luật "chỉ Ban ISO đóng phiếu" chỉ nằm ở sx/api/qc.py. Trên Desk, ai có
    quyền ghi (QC, QLSX, tổ Ghi sổ) đổi Trạng thái = Đóng là xong — cửa hậu im lặng.
  · Cờ diễn tập đổi được sau khi lập = giấu được một sự cố thật khỏi số liệu.
  · Lô gắn sai / không điền HSD thì giữ mẫu (W07), truy xuất, thu hồi đều trượt.

Nạp sx/api/qc.py, sx/qc/quyen.py, controller SX Su Co, sx/qc/xuat.py, patch d134 THẬT;
frappe là giả. Mẫu in BM.08.02 dựng bằng jinja2 thật (nếu máy có).
Chạy: python3 scripts/test-sucolo.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import re
import sys
import types
from datetime import date, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

HOM_NAY = date(2026, 10, 8)
SU_CO = {}          # name -> dict (bản đã lưu)
SU_CO_LO = []       # dòng con đã lưu (parent, batch, ...)
BATCH = [
    {"name": "SEN-HSD270405", "item": "TP-SEN", "item_name": "Bánh đậu xanh sen",
     "expiry_date": date(2027, 4, 5), "manufacturing_date": date(2026, 7, 5), "batch_qty": 120,
     "disabled": 0, "creation": "2026-07-05"},
    {"name": "DUA-HSD270405", "item": "TP-DUA", "item_name": "Bánh đậu xanh dừa",
     "expiry_date": date(2027, 4, 5), "manufacturing_date": date(2026, 7, 5), "batch_qty": 30,
     "disabled": 0, "creation": "2026-07-06"},
    {"name": "DX-NCC-0912", "item": "NL-DX", "item_name": "Đỗ xanh tách vỏ",
     "expiry_date": None, "manufacturing_date": None, "batch_qty": 800, "disabled": 0,
     "creation": "2026-09-12"},
    {"name": "SEN-CU-TAT", "item": "TP-SEN", "item_name": "Bánh đậu xanh sen",
     "expiry_date": date(2027, 4, 5), "manufacturing_date": None, "batch_qty": 0, "disabled": 1,
     "creation": "2026-01-01"},
]
ITEM = [{"name": "TP-SEN", "item_name": "Bánh đậu xanh sen", "has_batch_no": 1},
        {"name": "TP-DUA", "item_name": "Bánh đậu xanh dừa", "has_batch_no": 1},
        {"name": "NL-DX", "item_name": "Đỗ xanh tách vỏ", "has_batch_no": 1}]
CAI_DAT = {}
VAI = {"SX QC"}
NGUOI = {"u": "qc@x"}
SQL_COT = {"lo_tp": True}       # cột cũ của D133 còn trong bảng SX Su Co
SQL_LO_TP = []                  # (name, lo_tp) như trong DB


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


class Dong(Doc):
    pass


class Document(Doc):
    """Giả Frappe Document đủ cho controller: is_new, has_value_changed, append, set."""

    def append(self, f, row):
        r = Dong(row) if not isinstance(row, Dong) else row
        self.setdefault(f, []).append(r)
        return r

    def set(self, k, v):
        if isinstance(v, list):
            self[k] = [Dong(x) if not isinstance(x, Dong) else x for x in v]
        else:
            self[k] = v

    def is_new(self):
        return not self.get("name") or self["name"] not in SU_CO

    def has_value_changed(self, f):
        cu = SU_CO.get(self.get("name")) or {}
        return cu.get(f) != self.get(f)

    def insert(self, **kw):
        self["name"] = self.get("name") or f"SC-{len(SU_CO) + 1:04d}"
        type(self).validate(self)
        self._luu()
        return self

    def save(self, **kw):
        type(self).validate(self)
        self._luu()
        return self

    def _luu(self):
        SU_CO[self["name"]] = {k: v for k, v in self.items() if k != "ds_lo"}
        SU_CO_LO[:] = [r for r in SU_CO_LO if r["parent"] != self["name"]]
        for i, r in enumerate(self.get("ds_lo") or []):
            SU_CO_LO.append(dict(r, parent=self["name"], parenttype="SX Su Co", idx=i + 1))


def _bang(dt):
    if dt == "SX Su Co":
        return [dict(v) for v in SU_CO.values()]
    return {"SX Su Co Lo": SU_CO_LO, "Batch": BATCH, "Item": ITEM}.get(dt, [])


def _so(x):
    return str(x) if x is not None else ""


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "in" and x not in m:
                return False
            if op == "between" and not (_so(m[0]) <= _so(x) <= _so(m[1])):
                return False
            if op == "like" and m.strip("%").lower() not in _so(x).lower():
                return False
            if op == "!=" and x == m:
                return False
        elif _so(x) != _so(v):
            return False
    return True


def get_all(dt, filters=None, fields=None, pluck=None, limit=None, order_by=None,
            or_filters=None, **k):
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


def _get_value(dt, f, fld=None, as_dict=False, **k):
    h = next((h for h in _bang(dt) if (h["name"] == f if isinstance(f, str) else _khop(h, f))), None)
    if h is None:
        return None
    if isinstance(fld, (list, tuple)):
        d = Doc({c: h.get(c) for c in fld})
        return d if as_dict else tuple(d.values())
    return h.get(fld)


def _get_doc(x, n=None):
    if isinstance(x, dict):
        if x.get("doctype") == "SX Su Co":
            return SC_C.SXSuCo(x)
        if x.get("doctype") == "SX Su Co Lo":
            return LoDoc(x)
        return Doc(x)
    if x == "SX Su Co":
        d = SC_C.SXSuCo(dict(SU_CO[n]))
        d["ds_lo"] = [Dong(r) for r in SU_CO_LO if r["parent"] == n]
        return d
    raise Loi(f"get_doc {x}")


class LoDoc(Doc):
    def db_insert(self):
        SU_CO_LO.append(dict(self))


def _sql(q, *a, **k):
    if "lo_tp" in q:
        return [Doc(name=n, lo_tp=v) for n, v in SQL_LO_TP if v]
    return []


try:
    import jinja2
except ImportError:
    jinja2 = None

frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, **k: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})


class _Phien:
    user = property(lambda s: NGUOI["u"])


frappe.session = _Phien()
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_doc = _get_doc
frappe.get_cached_doc = lambda dt: Doc(CAI_DAT)
frappe.get_meta = lambda dt: types.SimpleNamespace(has_field=lambda f: True)
frappe.db = types.SimpleNamespace(
    get_value=_get_value,
    count=lambda dt, f=None: len(get_all(dt, f)),
    exists=lambda dt, f=None: bool(get_all(dt, f if isinstance(f, dict) else {"name": f})),
    table_exists=lambda dt: True,
    has_column=lambda dt, c: SQL_COT.get(c, False),
    sql=_sql,
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
fu.now_datetime = lambda: "2026-10-08 10:00:00"
fu.formatdate = str
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
mdl = types.ModuleType("frappe.model"); mdl.__path__ = []
dm = types.ModuleType("frappe.model.document"); dm.Document = Document
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
nap("sx.qc.nguong", "sx/qc/nguong.py")
QY = nap("sx.qc.quyen", "sx/qc/quyen.py")
nap("sx.qc.san_pham", "sx/qc/san_pham.py")
nap("sx.qc.su_co", "sx/qc/su_co.py")
X = nap("sx.qc.xuat", "sx/qc/xuat.py")
nap("sx.qc.nhac", "sx/qc/nhac.py")
nap("sx.qc.khieu_nai", "sx/qc/khieu_nai.py")
nap("sx.qc.giu_mau", "sx/qc/giu_mau.py")
nap("sx.qc.rework", "sx/qc/rework.py")
SC_C = nap("sx.qc.doctype.sx_su_co.sx_su_co", "sx/qc/doctype/sx_su_co/sx_su_co.py")
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
P = nap("sx.patches.d134_su_co_lo", "sx/patches/d134_su_co_lo.py")

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


def lap(**kw):
    p = {"mo_ta": "Bánh sen vỡ góc", "loai": "Khác", **kw}
    return Q.add_incident(json.dumps(p))


# ═══ 1. Lập phiếu: nguồn, lô, diễn tập ═════════════════════════════════════
print("\n-- lập phiếu tay: nguồn, lô liên quan, diễn tập --")
n1 = lap(ds_lo=["SEN-HSD270405", {"batch": "DX-NCC-0912", "so_luong": "50 kg"}, "SEN-HSD270405", ""])
kiem("lập được, nguồn mặc định 'Phát hiện khác'", SU_CO[n1]["nguon"] == "Phát hiện khác")
dong = [r for r in SU_CO_LO if r["parent"] == n1]
kiem("lô gắn đúng, bỏ dòng trùng + dòng trống", [r["batch"] for r in dong] == ["SEN-HSD270405", "DX-NCC-0912"],
     [r["batch"] for r in dong])
kiem("mã hàng / tên / HSD điền từ lô (API chỉ gửi mã lô)",
     (dong[0]["item"], dong[0]["ten"], dong[0]["hsd"]) == ("TP-SEN", "Bánh đậu xanh sen", date(2027, 4, 5)))
kiem("số lượng ảnh hưởng giữ theo dòng", dong[1]["so_luong"] == "50 kg")
loi = thu(lambda: lap(ds_lo=["KHONG-CO"]))
kiem("lô không có → chặn", loi and "Không thấy lô" in loi, loi or "")
loi = thu(lambda: lap(nguon="Vòng kiểm QC"))
kiem("nguồn hệ thống tự gắn (Vòng kiểm QC) → không chọn tay được", loi and "không hợp lệ" in loi, loi or "")
for ng in ("Khiếu nại", "Kiểm tra xuất xưởng", "Hàng trả về", "Kiểm xe", "Động vật gây hại",
           "Thiết bị đo", "Kết quả kiểm nghiệm", "Nhật ký cát", "Đánh giá nội bộ"):
    kiem(f"nguồn mới chọn tay được: {ng}", thu(lambda: lap(nguon=ng)) is None)
n_dt = lap(dien_tap=1, nguon="Khiếu nại", mo_ta="Diễn tập thu hồi lô HSD 05/04/2027")
kiem("QC lập phiếu DIỄN TẬP được", SU_CO[n_dt]["dien_tap"] == 1)

# ═══ 2. Chỉ người có quyền mới đóng — cả đường Desk ═══════════════════════
print("\n-- đóng / mở lại: chỉ Ban ISO hoặc người được giao --")
loi = thu(lambda: Q.close_incident(n1, "Loại bỏ"))
kiem("QC đóng qua màn QC → chặn", loi and "người ghi không tự duyệt" in loi, loi or "")
d = Q.frappe.get_doc("SX Su Co", n1) if hasattr(Q, "frappe") else _get_doc("SX Su Co", n1)
d.trang_thai, d.xu_ly_ngay, d.quyet_dinh_sp = "Đóng", "Cô lập 20 hộp", "Loại bỏ"
loi = thu(lambda: d.save())
kiem("QC đổi Trạng thái = Đóng trên DESK → chặn (cửa hậu trước D134)",
     loi and "Ban ISO" in loi and SU_CO[n1]["trang_thai"] == "Mở", loi or "")
loi = thu(lambda: SC_C.SXSuCo({"doctype": "SX Su Co", "ngay": "2026-10-08", "mo_ta": "x",
                               "trang_thai": "Đóng", "xu_ly_ngay": "x",
                               "quyet_dinh_sp": "Loại bỏ"}).insert())
kiem("QC lập phiếu MỚI ở trạng thái Đóng → chặn", loi and "Ban ISO" in loi, loi or "")
vai("Production Manager")
d = _get_doc("SX Su Co", n1)
d.trang_thai, d.xu_ly_ngay, d.quyet_dinh_sp = "Đóng", "Cô lập", "Loại bỏ"
kiem("QLSX (có quyền ghi Desk) đóng → chặn", thu(lambda: d.save()) is not None)
vai("ISO Manager")
Q.update_incident(n1, json.dumps({"xu_ly_ngay": "Cô lập 20 hộp"}))
loi = thu(lambda: Q.close_incident(n1, "Loại bỏ"))
kiem("Ban ISO đóng được", loi is None and SU_CO[n1]["trang_thai"] == "Đóng", loi or "")
vai("SX QC")
loi = thu(lambda: Q.reopen_incident(n1, "x"))
kiem("QC mở lại → chặn", loi is not None and SU_CO[n1]["trang_thai"] == "Đóng")
d = _get_doc("SX Su Co", n1)
d.trang_thai = "Mở"
kiem("QC mở lại trên Desk → chặn", thu(lambda: d.save()) is not None)
vai("SX QC", u="to.truong@x")
CAI_DAT["nguoi_dong_su_co"] = [Doc(user="to.truong@x")]
kiem("người được GIAO (SX QC Setting) mở lại được", thu(lambda: Q.reopen_incident(n1, "kiểm lại")) is None
     and SU_CO[n1]["trang_thai"] == "Mở")
kiem("… list báo duoc_dong cho người được giao", Q.list_incidents()["duoc_dong"] is True)
vai("SX QC", u="qc2@x")
kiem("QC khác (không được giao) → duoc_dong = False", Q.list_incidents()["duoc_dong"] is False)
CAI_DAT.clear()
vai("SX QC")
d = _get_doc("SX Su Co", n1)
d.xu_ly_ngay = "Cô lập 20 hộp, báo QLSX"
kiem("QC vẫn sửa nội dung phiếu đang mở (không đổi trạng thái)", thu(lambda: d.save()) is None)

print("\n-- cờ diễn tập: đổi sau khi lập chỉ người có quyền --")
loi = thu(lambda: Q.update_incident(n1, json.dumps({"dien_tap": 1})))
kiem("QC bật cờ diễn tập cho phiếu THẬT → chặn (giấu sự cố khỏi số liệu)",
     loi and "Diễn tập" in loi and not SU_CO[n1].get("dien_tap"), loi or "")
vai("ISO Manager")
kiem("Ban ISO đổi cờ được", thu(lambda: Q.update_incident(n_dt, json.dumps({"dien_tap": 0}))) is None
     and SU_CO[n_dt]["dien_tap"] == 0)
Q.update_incident(n_dt, json.dumps({"dien_tap": 1}))
vai("SX QC")

print("\n-- sửa lô liên quan --")
Q.update_incident(n1, json.dumps({"ds_lo": ["DUA-HSD270405"]}))
kiem("gửi ds_lo → thay cả bảng", [r["batch"] for r in SU_CO_LO if r["parent"] == n1] == ["DUA-HSD270405"])
Q.update_incident(n1, json.dumps({"xu_ly_ngay": "x"}))
kiem("không gửi ds_lo → giữ nguyên lô", [r["batch"] for r in SU_CO_LO if r["parent"] == n1] == ["DUA-HSD270405"])

# ═══ 3. Đọc ra: list, tìm lô, dashboard ════════════════════════════════════
print("\n-- list_incidents, tim_lo, dashboard --")
kq = Q.list_incidents()
theo = {s["name"]: s for s in kq["danh_sach"]}
kiem("lô thành phẩm hiện bằng HSD, không hiện mã lô (W05)",
     theo[n1]["ds_lo"][0]["nhan"] == "HSD 05/04/2027" and theo[n1]["ds_lo"][0]["ten"] == "Bánh đậu xanh dừa")
n2 = lap(ds_lo=["DX-NCC-0912"])
kiem("lô nguyên liệu không HSD hiện bằng mã lô",
     next(s for s in Q.list_incidents()["danh_sach"] if s["name"] == n2)["ds_lo"][0]["nhan"]
     == "DX-NCC-0912")
kiem("có cờ diễn tập (số) và danh sách nguồn chọn tay",
     theo[n_dt]["dien_tap"] == 1 and kq["nguon_tay"] == list(M.NGUON_TAY)
     and "Vòng kiểm QC" not in kq["nguon_tay"])
r = Q.tim_lo("05/04/2027")
kiem("tìm theo HSD gõ dd/mm/yyyy → mọi lô HSD đó, bỏ lô đã tắt",
     sorted(x["batch"] for x in r) == ["DUA-HSD270405", "SEN-HSD270405"], [x["batch"] for x in r])
kiem("… HSD gõ tắt 5/4/27 cũng ra", len(Q.tim_lo("5/4/27")) == 2)
kiem("tìm theo tên sản phẩm", [x["batch"] for x in Q.tim_lo("dừa")] == ["DUA-HSD270405"])
kiem("tìm theo mã lô NCC", [x["batch"] for x in Q.tim_lo("NCC-09")] == ["DX-NCC-0912"])
kiem("theo sản phẩm (san_pham=) → lô của mã đó", [x["batch"] for x in Q.tim_lo(san_pham="TP-SEN")]
     == ["SEN-HSD270405"])
kiem("gõ rỗng → không trả gì", Q.tim_lo("") == [])
vai("SX Vao Hop")
kiem("người ngoài QC không tìm lô được", thu(lambda: Q.tim_lo("dừa")) is not None)
vai("ISO Manager")
db = Q.dashboard("2026-10-01", "2026-10-31")
so_that = sum(1 for v in SU_CO.values() if not v.get("dien_tap"))
kiem("dashboard: phiếu diễn tập không tính vào số sự cố, đếm riêng",
     db["so_dien_tap"] == 1 and sum(x["so"] for x in db["theo_loai"]) == so_that, db["so_dien_tap"])
vai("SX QC")

# ═══ 4. CSV, mẫu in ═══════════════════════════════════════════════════════
print("\n-- CSV và mẫu in BM.08.02 --")
hang = X.dong_su_co(theo[n1])
kiem("CSV: đủ cột như tiêu đề", len(hang) == len(X.COT_SU_CO))
kiem("CSV: cột Lô liên quan in HSD + tên", hang[X.COT_SU_CO.index("Lô liên quan")]
     == "HSD 05/04/2027 Bánh đậu xanh dừa", hang)
kiem("CSV: cột Diễn tập = 1 / trống", X.dong_su_co(theo[n_dt])[X.COT_SU_CO.index("Diễn tập")] == "1"
     and hang[X.COT_SU_CO.index("Diễn tập")] == "")
if jinja2:
    pf = next(x for x in json.load(open("sx/fixtures/print_format.json", encoding="utf-8"))
              if x["name"] == "SX Su Co BM0802")
    fu_in = types.SimpleNamespace(formatdate=lambda v, f=None: fu.getdate(v).strftime("%d/%m/%Y"),
                                  format_datetime=lambda v, f=None: str(v))
    doc = _get_doc("SX Su Co", n_dt)
    doc["ds_lo"] = [types.SimpleNamespace(**r) for r in SU_CO_LO if r["parent"] == n_dt] or [
        types.SimpleNamespace(batch="SEN-HSD270405", hsd=date(2027, 4, 5), ten="Bánh đậu xanh sen",
                              so_luong="20 hộp")]
    html = jinja2.Environment().from_string(pf["html"]).render(
        doc=doc, frappe=types.SimpleNamespace(utils=fu_in))
    chu = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", html.split("</style>")[1]))
    kiem("mẫu in: tiêu đề có DIỄN TẬP, lô in bằng HSD", "DIỄN TẬP" in chu and "HSD 05/04/2027" in chu,
         chu[:200])

# ═══ 5. Patch d134 ════════════════════════════════════════════════════════
print("\n-- patch d134: ô lo_tp (D133) → bảng lô --")
SQL_LO_TP[:] = [(n2, "SEN-HSD270405"), (n1, "DUA-HSD270405"), (n_dt, "KHONG-CO-LO")]
truoc = len(SU_CO_LO)
P.execute()
kiem("chép lo_tp thành một dòng bảng lô (điền tên, HSD)",
     any(r["parent"] == n2 and r["batch"] == "SEN-HSD270405" and r["hsd"] == date(2027, 4, 5)
         for r in SU_CO_LO))
kiem("lô đã có trong bảng → không chép trùng", sum(1 for r in SU_CO_LO if r["parent"] == n1) == 1)
kiem("lô không còn tồn tại → bỏ qua", not any(r["batch"] == "KHONG-CO-LO" for r in SU_CO_LO))
sau = len(SU_CO_LO)
P.execute()
kiem("chạy lại vô hại", len(SU_CO_LO) == sau == truoc + 1)
SQL_COT["lo_tp"] = False
SQL_LO_TP[:] = [(n2, "DUA-HSD270405")]
P.execute()
kiem("site chưa từng có cột lo_tp → không làm gì", len(SU_CO_LO) == sau)
kiem("patch có trong patches.txt", "sx.patches.d134_su_co_lo" in open("sx/patches.txt", encoding="utf-8").read())

# ═══ 6. DocType + màn hình ════════════════════════════════════════════════
print("\n-- DocType và màn hình --")


def truong(p):
    return {f["fieldname"]: f for f in json.load(open(p, encoding="utf-8"))["fields"]}


sc = truong("sx/qc/doctype/sx_su_co/sx_su_co.json")
kiem("Sự cố: bảng Lô liên quan → SX Su Co Lo; bỏ ô lo_tp", sc["ds_lo"]["fieldtype"] == "Table"
     and sc["ds_lo"]["options"] == "SX Su Co Lo" and "lo_tp" not in sc)
kiem("Sự cố: cờ Diễn tập (Check, mặc định 0)", sc["dien_tap"]["fieldtype"] == "Check"
     and sc["dien_tap"].get("default") == "0")
kiem("Sự cố: lựa chọn Nguồn = đúng M.NGUON (chọn tay ⊂ nguồn)",
     sc["nguon"]["options"].split("\n") == list(M.NGUON) and set(M.NGUON_TAY) <= set(M.NGUON))
lo = truong("sx/qc/doctype/sx_su_co_lo/sx_su_co_lo.json")
kiem("Bảng lô: lô Link Batch bắt buộc; mã hàng / tên / HSD chỉ đọc",
     lo["batch"]["options"] == "Batch" and lo["batch"].get("reqd")
     and all(lo[f].get("read_only") for f in ("item", "ten", "hsd")))
st = truong("sx/qc/doctype/sx_qc_setting/sx_qc_setting.json")
kiem("Setting: người được giao đóng sự cố (Table MultiSelect)",
     st["nguoi_dong_su_co"]["fieldtype"] == "Table MultiSelect"
     and st["nguoi_dong_su_co"]["options"] == "SX QC Nguoi Duoc Giao"
     and truong("sx/qc/doctype/sx_qc_nguoi_duoc_giao/sx_qc_nguoi_duoc_giao.json")["user"]["options"] == "User")
src = open("sx/qc/doctype/sx_su_co/sx_su_co.py", encoding="utf-8").read()
kiem("controller dùng chung luật quyền với API (sx/qc/quyen.py)", "duoc_dong_su_co" in src
     and "duoc_dong_su_co" in open("sx/api/qc.py", encoding="utf-8").read())
js = open("sx/public/sx/views/qc_incidents.js", encoding="utf-8").read()
for m in sorted(set(re.findall(r"sx\.api\.qc\.(\w+)", js))):
    kiem(f"màn Sự cố gọi method có thật: {m}", callable(getattr(Q, m, None)))
kiem("màn Sự cố: gắn lô (tim_lo), chọn nguồn, cờ diễn tập, gửi ds_lo",
     all(t in js for t in ("tim_lo", "nguon_tay", "dien_tap", "ds_lo: kLo.lay()")))
kiem("màn Sự cố: cờ diễn tập trên phiếu đã lập chỉ hiện cho người được đóng",
     "dl.duoc_dong ? oCheck(" in js)

print(f"\n{'SUCOLO-OK' if not hong else f'SUCOLO-FAIL ({hong})'}")
sys.exit(1 if hong else 0)
