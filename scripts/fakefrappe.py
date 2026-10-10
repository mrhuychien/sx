"""Frappe giả dùng chung cho các bài test P3 (D143+) — nạp module THẬT của sx trên một "DB" là dict.

Đủ cho controller + API của module QC: get_all (lọc, sắp nhiều khoá, chọn cột như frappe), get_value,
exists, set_value, get_doc / insert / save / delete_doc chạy đúng vòng đời (before_insert → đặt tên →
validate → lưu → on_update; on_trash → xoá → after_delete), db_set, render_template bằng jinja2 (nếu
có). Ngày hôm nay, người dùng, vai đổi được giữa chừng.

Dùng:
    import fakefrappe as F
    F.cai()                                  # trước khi nạp module sx
    M = F.nap("sx.qc.thiet_bi", "sx/qc/thiet_bi.py")
    F.dang_ky("SX Thiet Bi Do", Lop, ten_theo="ma")
"""

import copy
import glob
import importlib.util
import json
import os
import sys
import types
from datetime import date, datetime, time, timedelta

DB = {}
CAI_DAT = {}           # doc SX QC Setting (get_cached_doc / get_single)
CAI_DAT_SX = {}        # doc SX Settings
BAO = []               # msgprint
NGUOI = {"u": "qc@x", "roles": ["SX QC"]}
NGAY = {"d": date(2026, 10, 9)}
LOP = {}               # doctype → lớp controller
CON = {}               # (doctype cha, ô bảng con) → doctype con — xem bang_con()
TEN_THEO = {}          # doctype → field đặt tên (autoname field:x)
SO = {"n": 0}
try:
    import jinja2
except ImportError:  # pragma: no cover
    jinja2 = None


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


def bang(dt):
    return DB.setdefault(dt, {})


def hom_nay():
    return NGAY["d"]


def dat_ngay(d):
    NGAY["d"] = d if isinstance(d, date) else date.fromisoformat(str(d))


def vai(*roles, u=None):
    NGUOI["roles"] = list(roles)
    NGUOI["u"] = u or {"SX QC": "qc@x", "ISO Manager": "iso@x", "SX QC Packing": "goi@x",
                       "SX Quan Ly": "ql@x"}.get(roles[0] if roles else "", "x@x")


def _s(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.isoformat()
    return str(v if v is not None else "")


def _so_sanh(x, m):
    try:
        return float(x), float(m)
    except (TypeError, ValueError):
        return _s(x), _s(m)


def khop(h, f):
    if isinstance(f, (list, tuple)):          # [[dt, field, op, val]] / [[field, op, val]]
        f = {c[-3]: (c[-2], c[-1]) for c in f}
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, (tuple, list)) and len(v) == 2 and isinstance(v[0], str) and v[0] in (
                "between", "<", "<=", ">", ">=", "!=", "in", "not in", "is", "like", "="):
            op, m = v
            if op == "between":
                if not (_s(m[0]) <= _s(x)[:len(_s(m[0]))] and _s(x)[:len(_s(m[1]))] <= _s(m[1])):
                    return False
            elif op == "is":
                if (m == "set") != bool(x):
                    return False
            elif op == "in":
                if x not in m and _s(x) not in [_s(i) for i in m]:
                    return False
            elif op == "not in":
                if x in m or _s(x) in [_s(i) for i in m]:
                    return False
            elif op == "like":
                if str(m).strip("%").lower() not in _s(x).lower():
                    return False
            elif op == "!=":
                if _s(x) == _s(m):
                    return False
            elif op == "=":
                if _s(x) != _s(m):
                    return False
            else:
                if x is None or x == "":
                    return False
                a, b = _so_sanh(x, m) if not isinstance(m, (date, datetime)) and "-" not in _s(m) else (_s(x), _s(m))
                if not {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]:
                    return False
        elif _s(x) != _s(v):
            # Check / Int trống trên frappe là 0 (NOT NULL DEFAULT 0) — bản ghi tạo không đặt ô đó
            # vẫn khớp bộ lọc = 0.
            if not ((x is None or x == "") and _s(v) == "0"):
                return False
    return True


def _sap(ds, order_by):
    for phan in reversed([p.strip() for p in (order_by or "").split(",") if p.strip()]):
        bits = phan.split()
        f = bits[0].split(".")[-1].strip("`")
        ds.sort(key=lambda r: _s(r.get(f)), reverse=len(bits) > 1 and bits[1].lower() == "desc")
    return ds


def get_all(dt, filters=None, fields=None, order_by=None, limit=None, limit_page_length=None, pluck=None,
            or_filters=None, **k):
    ds = [Doc(x) for x in bang(dt).values() if khop(x, filters)]
    if or_filters:
        ds = [x for x in ds if any(khop(x, {a: b}) for a, b in (or_filters.items() if isinstance(or_filters, dict)
                                                                 else [(c[-3], (c[-2], c[-1])) for c in or_filters]))]
    _sap(ds, order_by or "")
    n = limit or limit_page_length
    if n:
        ds = ds[:n]
    if pluck:
        return [x.get(pluck) for x in ds]
    if fields and fields != ["*"]:
        return [Doc({f.split(" as ")[-1].strip(): x.get(f.split(" as ")[0].strip()) for f in fields}) for x in ds]
    return ds


def get_value(dt, ten, fld=None, as_dict=False, **k):
    if isinstance(ten, dict):
        h = next((x for x in bang(dt).values() if khop(x, ten)), None)
    else:
        h = bang(dt).get(ten)
    if h is None:
        return None
    if fld is None:
        fld = "name"
    if isinstance(fld, str):
        return h.get(fld)
    d = Doc({c: h.get(c) for c in fld})
    return d if as_dict else tuple(d.values())


# Doctype Single: không có bảng riêng ("tabSX Settings") — như frappe thật, table_exists trả False.
DON = {"SX Settings", "SX QC Setting", "Stock Settings"}


def exists(dt, ten=None):
    if dt == "DocType":                      # mọi doctype của app coi như đã migrate
        return ten
    if isinstance(ten, dict):
        h = next((x for x in bang(dt).values() if khop(x, ten)), None)
        return h["name"] if h else None
    return ten if ten in bang(dt) else None


def set_value(dt, ten, f, v=None, update_modified=True):
    dd = f if isinstance(f, dict) else {f: v}
    _kiem_ghi(dt, ten, dd)
    bang(dt)[ten].update(dd)


def _kiem_ghi(dt, ten, dd):
    """set_value / db_set: ô varchar quá dài → lỗi (frappe không kiểm nhưng MariaDB strict chặn)."""
    m = meta(dt)
    for k, v in dd.items():
        if k in m:
            kiem_do_dai(dt, m[k], v, ten)


def count(dt, f=None):
    return len(get_all(dt, f))


def sx_dau_trang(ma, ten=None):
    """Hàm Jinja của đầu trang in chung (W42) — như hooks.py đăng ký trên site; nạp sx/qc/mau_in.py thật."""
    for t in ("tai_lieu", "mau_in"):
        if f"sx.qc.{t}" not in sys.modules:
            nap(f"sx.qc.{t}", f"sx/qc/{t}.py")
    return sys.modules["sx.qc.mau_in"].sx_dau_trang(ma, ten)


def render_template(path, ctx):
    if jinja2 is None:
        return ""
    fu_in = types.SimpleNamespace(formatdate=lambda v, f=None: getdate(v).strftime(
        "%d/%m" if f == "dd/MM" else ("%m/%Y" if f == "MM/yyyy" else "%d/%m/%Y")))
    env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    env.globals["sx_dau_trang"] = sx_dau_trang
    return env.get_template(path).render(frappe=types.SimpleNamespace(utils=fu_in), **ctx)


def getdate(x=None):
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10]) if x else hom_nay()


# ── Kiểm như Document._validate của frappe v16 (D181) ─────────────────────────────────────────────
# Trước D181 bản giả lưu mọi giá trị — nạp bộ tài liệu chạy được trên test nhưng trên site frappe chặn: "Tên hồ sơ /
# văn bản … will get truncated, as max characters allowed is 140". Giờ insert / save / submit kiểm theo DocType JSON
# của app (sx/*/doctype): ô bắt buộc, ô Select đúng lựa chọn, ô varchar (Data, Link, Select… = 140 hoặc `length`)
# không quá dài — cả dòng bảng con; set_value / db_set kiểm độ dài (MariaDB strict cũng chặn). DocType ngoài app
# (User, Item…) không có JSON → không kiểm.
VARCHAR = {"Data", "Link", "Dynamic Link", "Select", "Read Only", "Color", "Icon", "Phone", "Autocomplete"}
BANG = {"Table", "Table MultiSelect"}
META = {}


class CharacterLengthExceededError(Loi):
    pass


class MandatoryError(Loi):
    pass


def meta(dt):
    """{fieldname: field} của DocType trong app (đọc JSON một lần); không có → {}."""
    if not META:
        goc = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sx")
        for p in glob.glob(os.path.join(goc, "*", "doctype", "*", "*.json")):
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict) and d.get("doctype") == "DocType":
                META[d["name"]] = {x["fieldname"]: x for x in d.get("fields") or [] if x.get("fieldname")}
        META.setdefault("", {})
    return META.get(dt) or {}


def _lua_chon(f):
    return [] if not f.get("options") else str(f["options"]).split("\n")


def _co_mac_dinh(f):
    """frappe đặt sẵn cho bản mới: `default`; Select chưa có default → lựa chọn đầu (có thể là rỗng)."""
    return bool(f.get("default")) or (f["fieldtype"] == "Select" and bool(_lua_chon(f)) and bool(_lua_chon(f)[0]))


def kiem_do_dai(dt, f, v, ten, dong=None):
    if f["fieldtype"] not in VARCHAR or v is None:
        return
    toi_da = int(f.get("length") or 0) or 140
    if len(str(v)) > toi_da:
        noi = f"{dt}, Row {dong}" if dong else f"{dt} {ten}"
        raise CharacterLengthExceededError(f"{noi}: '{f.get('label') or f['fieldname']}' ({v}) will get truncated, as "
                                           f"max characters allowed is {toi_da}")


def kiem_doc(dt, d, bo_bat_buoc=False):
    """Như Document._validate: thiếu ô bắt buộc → MandatoryError; Select ngoài lựa chọn → lỗi; quá dài → lỗi.
    Dòng bảng con kiểm đủ ba thứ."""
    m = meta(dt)
    if not m:
        return
    thieu = []
    viec = [(dt, m, d, None)]
    for k, f in m.items():
        if f["fieldtype"] in BANG and f.get("options"):
            viec += [(f["options"], meta(f["options"]), r, i) for i, r in enumerate(d.get(k) or [], 1)
                     if isinstance(r, dict)]
    for dt_x, m_x, x, dong in viec:
        for k, f in m_x.items():
            if not f.get("reqd") or f["fieldtype"] == "Check":
                continue
            v = x.get(k)
            if (v in (None, [], "") or not str(v).strip()) and not (v is None and _co_mac_dinh(f)):
                thieu.append(k if dong is None else f"{dt_x} dòng {dong}: {k}")
    if thieu and not bo_bat_buoc:
        raise MandatoryError(f"[{dt}, {d.get('name')}]: {', '.join(thieu)}")
    for dt_x, m_x, x, dong in viec:
        for k, f in m_x.items():
            v = x.get(k)
            if f["fieldtype"] == "Select" and k != "naming_series" and v and _lua_chon(f):
                if str(v).strip() not in _lua_chon(f):
                    cac = '", "'.join(_lua_chon(f))
                    raise Loi(f"{f'Row #{dong}: ' if dong else ''}{f.get('label') or k} cannot be \"{v}\". It "
                              f"should be one of \"{cac}\"")
        for k, f in m_x.items():
            kiem_do_dai(dt_x, f, x.get(k), d.get("name"), dong)


def _dong_con(v):
    """Như frappe: bảng con truyền vào bằng list dict thành các dòng có thuộc tính (r.ten_o)."""
    if isinstance(v, list) and any(isinstance(r, dict) for r in v):
        return [Doc(r) if isinstance(r, dict) and not isinstance(r, Doc) else r for r in v]
    return v


class Document:
    """Document giả. Thuộc tính đọc / ghi vào dict; vòng đời như frappe."""

    def __init__(self, d=None):
        self.__dict__["_d"] = {k: _dong_con(v) for k, v in dict(d or {}).items()}
        self.__dict__["_moi"] = "name" not in self._d or self._d.get("__moi")
        self.__dict__["_cu"] = None if self._moi else copy.deepcopy(self._d)
        self.__dict__["flags"] = types.SimpleNamespace()

    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.__dict__["_d"].get(k)

    def __setattr__(self, k, v):
        self.__dict__["_d"][k] = v

    def get(self, k, d=None):
        v = self._d.get(k, d)
        return d if v is None and d is not None else v

    def set(self, k, v):
        self._d[k] = _dong_con(v)

    def append(self, k, v):
        self._d.setdefault(k, []).append(Doc(v) if isinstance(v, dict) else v)

    def update(self, d):
        self._d.update({k: _dong_con(v) for k, v in dict(d).items()})

    def as_dict(self):
        return Doc(self._d)

    def is_new(self):
        return self._moi

    def get_doc_before_save(self):
        return Doc(self._cu) if self._cu else None

    def has_value_changed(self, f):
        return (self._cu or {}).get(f) != self._d.get(f)

    def db_set(self, f, v=None, update_modified=True):
        dd = f if isinstance(f, dict) else {f: v}
        _kiem_ghi(self._d["doctype"], self._d["name"], dd)
        self._d.update(dd)
        bang(self._d["doctype"])[self._d["name"]].update(dd)

    def _goi(self, ten):
        h = getattr(type(self), ten, None)
        if h:
            h(self)

    def insert(self, ignore_permissions=False, **k):
        self._goi("before_insert")
        dt = self._d["doctype"]
        if TEN_THEO.get(dt):
            self._d["name"] = self._d.get(TEN_THEO[dt])
        else:
            SO["n"] += 1
            self._d["name"] = self._d.get("name") or f"{''.join(w[0] for w in dt.split())}-{SO['n']:05d}"
        if self._d["name"] in bang(dt):           # như frappe: DuplicateEntryError
            raise Loi(f"Duplicate entry {dt} {self._d['name']}")
        self._d.setdefault("creation", f"{hom_nay().isoformat()} 09:00:{SO['n'] % 60:02d}")
        self._d.setdefault("owner", NGUOI["u"])
        if self._d.get("docstatus") is None:      # frappe: bản mới là nháp (0), không phải NULL
            self._d["docstatus"] = 0
        if k.get("ignore_mandatory"):
            self.flags.ignore_mandatory = True
        return self._luu()

    def save(self, ignore_permissions=False, **k):
        return self._luu()

    def _luu(self):
        self._goi("validate")
        dt = self._d["doctype"]
        kiem_doc(dt, self._d, getattr(self.flags, "ignore_mandatory", False))
        _dat_ten_con(dt, self._d)
        bang(dt)[self._d["name"]] = copy.deepcopy(self._d)
        _chep_con(dt, self._d)
        self._goi("on_update")
        self.__dict__["_moi"] = False
        self.__dict__["_cu"] = copy.deepcopy(self._d)
        return self

    def delete(self, **k):
        delete_doc(self._d["doctype"], self._d["name"])

    def submit(self, **k):
        """Như frappe: docstatus 1 → validate → before_submit → lưu → on_submit."""
        self._d["docstatus"] = 1
        self._goi("validate")
        self._goi("before_submit")
        kiem_doc(self._d["doctype"], self._d, getattr(self.flags, "ignore_mandatory", False))
        bang(self._d["doctype"])[self._d["name"]] = copy.deepcopy(self._d)
        self._goi("on_submit")
        return self

    def cancel(self, **k):
        self._d["docstatus"] = 2
        self._goi("before_cancel")
        bang(self._d["doctype"])[self._d["name"]] = copy.deepcopy(self._d)
        self._goi("on_cancel")
        return self


class DocThuong(Doc):
    """Doc không có controller (SX Su Co, Item…): insert chỉ lưu."""

    def insert(self, ignore_permissions=False, **k):
        dt = self["doctype"]
        SO["n"] += 1
        self["name"] = self.get("name") or f"{''.join(w[0] for w in dt.split())}-{len(bang(dt)) + 1:04d}"
        self.setdefault("creation", f"{hom_nay().isoformat()} 09:00:00")
        kiem_doc(dt, self, k.get("ignore_mandatory"))
        bang(dt)[self["name"]] = dict(self)
        return self

    save = insert

    def db_set(self, f, v=None, update_modified=True):
        dd = f if isinstance(f, dict) else {f: v}
        _kiem_ghi(self["doctype"], self["name"], dd)
        self.update(dd)
        bang(self["doctype"])[self["name"]].update(dd)


def get_doc(a, b=None):
    if isinstance(a, dict):
        lop = LOP.get(a["doctype"])
        return lop(dict(a)) if lop else DocThuong(a)
    if b not in bang(a):
        raise Loi(f"{a} {b} not found")
    d = dict(copy.deepcopy(bang(a)[b]), doctype=a)
    lop = LOP.get(a)
    return lop(d) if lop else DocThuong(d)


def delete_doc(dt, ten, **k):
    d = get_doc(dt, ten)
    if hasattr(d, "_goi"):
        d._goi("on_trash")
    bang(dt).pop(ten)
    _chep_con(dt, {"name": ten}, xoa=True)
    if hasattr(d, "_goi"):
        d._goi("after_delete")


def bang_con(dt, f, dt_con):
    """Khai ô bảng con: lưu doc cha thì chép các dòng con ra bảng riêng (có parent, parenttype, parentfield,
    idx) như frappe thật — để get_all chạy được trên doctype con. Xoá doc cha thì xoá dòng con."""
    CON[(dt, f)] = dt_con


def _dat_ten_con(dt, d):
    """Như frappe: dòng con (bảng khai bằng bang_con) có `name` riêng, giữ nguyên qua các lần lưu."""
    for (cha, f), _con in CON.items():
        if cha != dt:
            continue
        for r in d.get(f) or []:
            if isinstance(r, dict) and not r.get("name"):
                SO["n"] += 1
                r["name"] = f"{d['name']}-{f}-{SO['n']}"


def _chep_con(dt, d, xoa=False):
    for (cha, f), con in CON.items():
        if cha != dt:
            continue
        b = bang(con)
        for k in [k for k, v in b.items() if v.get("parent") == d["name"] and v.get("parentfield") == f]:
            b.pop(k)
        for i, r in enumerate([] if xoa else (d.get(f) or []), 1):
            h = dict(r, parent=d["name"], parenttype=dt, parentfield=f, idx=i)
            h["name"] = r.get("name") or f"{d['name']}-{f}-{i}"
            b[h["name"]] = h


def dang_ky(dt, lop, ten_theo=None):
    LOP[dt] = lop
    if ten_theo:
        TEN_THEO[dt] = ten_theo


def cai():
    """Cài frappe giả vào sys.modules (gọi một lần, trước khi nạp module sx)."""
    frappe = types.ModuleType("frappe")
    frappe.throw = lambda m, e=None, **k: (_ for _ in ()).throw((e or Loi)(str(m)))
    frappe.msgprint = lambda m, **k: BAO.append(str(m))
    frappe.whitelist = lambda *a, **k: (lambda f: f)
    frappe.PermissionError = type("PermissionError", (Loi,), {})
    frappe.DoesNotExistError = type("DoesNotExistError", (Loi,), {})
    frappe.ValidationError = Loi
    frappe.CharacterLengthExceededError = CharacterLengthExceededError
    frappe.MandatoryError = MandatoryError

    class _Phien:
        user = property(lambda s: NGUOI["u"])

    frappe.session = _Phien()
    frappe.flags = types.SimpleNamespace(in_scheduler=False)
    frappe.get_roles = lambda u=None: list(NGUOI["roles"])
    frappe.get_all = get_all
    frappe.get_cached_value = lambda dt, ten, f: get_value(dt, ten, f)
    frappe._dict = Doc
    frappe.get_list = get_all
    frappe.get_doc = get_doc
    frappe.new_doc = lambda dt: get_doc({"doctype": dt})
    frappe.delete_doc = delete_doc
    frappe.render_template = render_template
    frappe.get_cached_doc = lambda dt, *a: Doc(CAI_DAT if dt == "SX QC Setting" else CAI_DAT_SX)
    frappe.get_single = frappe.get_cached_doc
    frappe.get_meta = lambda dt: types.SimpleNamespace(has_field=lambda f: True, get_field=lambda f: None)
    frappe.db = types.SimpleNamespace(get_value=get_value, exists=exists, set_value=set_value, count=count,
                                      table_exists=lambda dt: dt not in DON, commit=lambda: None,
                                      get_single_value=lambda dt, f: (CAI_DAT if dt == "SX QC Setting"
                                                                      else CAI_DAT_SX).get(f),
                                      set_single_value=lambda dt, f, v: (CAI_DAT if dt == "SX QC Setting"
                                                                         else CAI_DAT_SX).__setitem__(f, v))
    frappe.__dict__["_"] = lambda s: s
    fu = types.ModuleType("frappe.utils")
    fu.cint = lambda v: int(float(v or 0)) if str(v or 0).strip() not in ("", "None") else 0
    fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
    fu.getdate = getdate
    fu.nowdate = lambda: hom_nay().isoformat()
    fu.today = fu.nowdate
    fu.add_days = lambda d, n: getdate(d) + timedelta(days=n)
    fu.add_months = lambda d, n: getdate(d)
    fu.now_datetime = lambda: datetime.combine(hom_nay(), datetime.min.time()).replace(hour=10)
    fu.now = lambda: fu.now_datetime().strftime("%Y-%m-%d %H:%M:%S")
    fu.get_datetime = lambda x=None: x if isinstance(x, datetime) else (
        datetime.fromisoformat(str(x)[:19]) if x else fu.now_datetime())
    fu.date_diff = lambda a, b: (getdate(a) - getdate(b)).days
    fu.get_time = lambda x: x.time() if isinstance(x, datetime) else (
        x if isinstance(x, time) else datetime.strptime(str(x)[:8], "%H:%M:%S").time())
    fu.time_diff_in_seconds = lambda a, b: (fu.get_datetime(a) - fu.get_datetime(b)).total_seconds()
    fu.format_date = lambda d, f=None: getdate(d).strftime("%d/%m/%Y")
    fu.formatdate = fu.format_date
    frappe.utils = fu
    md = types.ModuleType("frappe.model.document")
    md.Document = Document
    sys.modules["frappe"] = frappe
    sys.modules["frappe.utils"] = fu
    sys.modules["frappe.model"] = types.ModuleType("frappe.model")
    sys.modules["frappe.model.document"] = md
    for g in ("sx", "sx.qc", "sx.api", "sx.patches"):
        m = types.ModuleType(g)
        m.__path__ = []
        sys.modules[g] = m
    return frappe


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


def nap_qc():
    """Nạp chuỗi module QC mà sx/api/qc.py cần, theo đúng thứ tự phụ thuộc."""
    for t in ("muc", "nguong", "quyen", "san_pham", "su_co", "xuat", "nhac", "dong_vat", "cat", "so_do",
              "thiet_bi", "kiem_nghiem", "viec_dinh_ky", "khac_phuc", "vai_u", "ncc", "kiem_xe", "giu_mau",
              "tai_lieu", "mau_in", "so", "danh_gia_ncc"):
        nap(f"sx.qc.{t}", f"sx/qc/{t}.py")
    return nap("sx.api.qc", "sx/api/qc.py")


HONG = {"n": 0}


def kiem(ten, dk, ct=""):
    if not dk:
        HONG["n"] += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


def thu(f):
    try:
        f()
    except Exception as e:  # noqa: BLE001
        return str(e) or type(e).__name__
    return None


def ket_thuc(ten):
    print(f"\n{ten}-OK" if not HONG["n"] else f"\n{ten}-FAIL ({HONG['n']})")
    sys.exit(1 if HONG["n"] else 0)
