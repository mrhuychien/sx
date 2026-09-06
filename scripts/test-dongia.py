"""Kiểm bảng đơn giá khoán: bung nhiều mã cùng lúc, và chọn bảng theo ngày hiệu lực.

Vì sao phải có bài này (D80):
  - Bung "chọn nhiều mã" sai một chút là bảng có hai dòng cùng khoá (mã + cách làm),
    lúc đó tra giá lấy dòng nào là chuyện may rủi — mà đó là tiền lương thật.
  - Chọn bảng theo ngày sai là cả ngày công tính theo giá của bảng khác, hoặc ra 0.
    Cả hai đều sai âm thầm: màn hình vẫn ghi được, chỉ có số tiền là sai.

Chạy: python3 scripts/test-dongia.py   (verify.sh gọi sẵn)

Nạp controller + utils THẬT với một frappe giả tối thiểu.
"""

import datetime
import importlib.util
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class D(dict):
    __getattr__ = dict.get


class Throw(Exception):
    pass


DB = {}


def _khop(row, f):
    for k, v in (f or {}).items():
        cur = row.get(k)
        if isinstance(v, (tuple, list)) and len(v) == 2:
            op, val = v
            if op == "!=" and cur == val:
                return False
            if op == "<" and not (cur is not None and cur < val):
                return False
            if op == "<=" and not (cur is not None and cur <= val):
                return False
            if op == "is" and val == "not set" and cur:
                return False
        elif cur != v:
            return False
    return True


frappe = types.ModuleType("frappe")


def get_all(dt, filters=None, fields=None, pluck=None, order_by=None, **kw):
    rows = [r for r in DB.get(dt, []) if _khop(r, filters)]
    if order_by:
        khoa = order_by.split()[0]
        rows = sorted(rows, key=lambda r: (r.get(khoa) is None, r.get(khoa)),
                      reverse=order_by.strip().lower().endswith("desc"))
    if pluck:
        return [r.get(pluck) for r in rows]
    return [D({k: r.get(k) for k in (fields or r.keys())}) for r in rows]


def get_value(dt, filters=None, fieldname=None, order_by=None, **kw):
    if isinstance(filters, str):
        filters = {"name": filters}
    rows = get_all(dt, filters=filters, order_by=order_by)
    if not rows:
        return None
    return rows[0].get(fieldname)


frappe.get_all = get_all
frappe.db = types.SimpleNamespace(
    get_value=get_value,
    exists=lambda dt, f=None: bool(get_value(dt, f, "name")),
    count=lambda dt, f=None: len(get_all(dt, filters=f)),
    set_value=lambda *a, **k: None, sql=lambda *a, **k: [], commit=lambda: None,
    get_single_value=lambda dt, f: None,
    table_exists=lambda dt: dt in DB, has_column=lambda dt, c: True,
)
frappe.throw = lambda msg, *a, **k: (_ for _ in ()).throw(Throw(msg))
frappe.msgprint = lambda *a, **k: None
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.get_cached_value = lambda dt, n, f, **k: get_value(dt, n, f)
frappe.get_cached_doc = frappe.get_doc = lambda *a, **k: None
frappe.utils = types.ModuleType("frappe.utils")


def getdate(x=None):
    if x is None:
        return datetime.date(2026, 9, 6)
    if isinstance(x, datetime.datetime):
        return x.date()
    if isinstance(x, datetime.date):
        return x
    return datetime.date.fromisoformat(str(x)[:10])


frappe.utils.getdate = getdate
frappe.utils.nowdate = lambda: "2026-09-06"
frappe.utils.cint = lambda v: int(v) if str(v).strip().lstrip("-").isdigit() else 0
frappe.utils.flt = lambda v, p=None: (
    round(float(v or 0), p) if p is not None else float(v or 0))
frappe.utils.add_days = lambda d, n: getdate(d) + datetime.timedelta(days=n)
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = frappe.utils
frappe.__dict__["_"] = lambda s: s
mm = types.ModuleType("frappe.model")
md = types.ModuleType("frappe.model.document")


class Document:
    pass


md.Document = Document
sys.modules["frappe.model"] = mm
sys.modules["frappe.model.document"] = md

sx = types.ModuleType("sx")
sx.__path__ = []
sys.modules["sx"] = sx
spec = importlib.util.spec_from_file_location("sx.utils", "sx/utils.py")
utils = importlib.util.module_from_spec(spec)
sys.modules["sx.utils"] = utils
spec.loader.exec_module(utils)

spec2 = importlib.util.spec_from_file_location(
    "bdg", "sx/sx/doctype/sx_bang_don_gia/sx_bang_don_gia.py")
bdg = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(bdg)


class Bang(bdg.SXBangDonGia):
    """Doc giả: chỉ cần append + các field controller đụng tới."""

    def __init__(self, **kw):
        self.name = kw.pop("name", "DG-MOI")
        self.hieu_luc_tu = kw.pop("hieu_luc_tu", None)
        self.dong = []
        self.them_ma = []
        self.them_cach_lam = None
        self.them_don_gia = 0
        for k, v in kw.items():
            setattr(self, k, v)

    def append(self, field, row):
        r = D(row)
        r["idx"] = len(getattr(self, field)) + 1
        getattr(self, field).append(r)
        return r


hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


def ma(*ds):
    return [D({"san_pham": s}) for s in ds]


def khoa(b):
    return sorted((r.san_pham, r.cach_lam or "", float(r.don_gia)) for r in b.dong)


print("-- bung nhiều mã cùng lúc --")
b = Bang()
b.them_ma = ma("BD-SR-300", "BD-TX-300", "BD-TH-300")
b.them_don_gia = 450
b.validate()
kiem("3 mã -> 3 dòng cùng giá", khoa(b) == [
    ("BD-SR-300", "", 450.0), ("BD-TH-300", "", 450.0), ("BD-TX-300", "", 450.0)],
    str(khoa(b)))
kiem("ô chọn nhiều mã được xoá sạch sau khi bung",
     b.them_ma == [] and b.them_cach_lam is None and float(b.them_don_gia) == 0)

b.them_ma = ma("BD-SR-300", "BD-CM-300")
b.them_don_gia = 500
b.validate()
kiem("mã đã có -> ĐỔI GIÁ, không tạo dòng trùng", len(b.dong) == 4, f"{len(b.dong)} dòng")
kiem("giá mã cũ được cập nhật",
     [float(r.don_gia) for r in b.dong if r.san_pham == "BD-SR-300"] == [500.0])
kiem("mã chưa có -> thêm dòng mới",
     [float(r.don_gia) for r in b.dong if r.san_pham == "BD-CM-300"] == [500.0])

b2 = Bang()
b2.them_ma = ma("A", "A", "B", "A")
b2.them_don_gia = 100
b2.validate()
kiem("chọn trùng mã trong cùng một lần -> chỉ một dòng mỗi mã", len(b2.dong) == 2,
     str(khoa(b2)))

b3 = Bang()
b3.dong = []
b3.append("dong", {"san_pham": "A", "cach_lam": None, "don_gia": 100})
b3.them_ma = ma("A")
b3.them_cach_lam = "Máy hỗ trợ"
b3.them_don_gia = 130
b3.validate()
kiem("cùng mã nhưng KHÁC cách làm -> là dòng riêng", khoa(b3) == [
    ("A", "", 100.0), ("A", "Máy hỗ trợ", 130.0)], str(khoa(b3)))

print("\n-- bung sai thì DỪNG, không nuốt --")
for ten, dung in [
    ("chọn mã mà quên giá", lambda: setattr(b4, "them_don_gia", 0)),
    ("điền giá mà quên chọn mã", None),
]:
    b4 = Bang()
    if dung:
        b4.them_ma = ma("A")
        dung()
    else:
        b4.them_don_gia = 300
    try:
        b4.validate()
        kiem(ten, False, "đáng lẽ phải throw")
    except Throw as e:
        kiem(ten, True, str(e)[:60])

print("\n-- trùng khoá vẫn bị chặn --")
b5 = Bang()
b5.append("dong", {"san_pham": "A", "cach_lam": None, "don_gia": 100})
b5.append("dong", {"san_pham": "A", "cach_lam": None, "don_gia": 200})
try:
    b5.validate()
    kiem("hai dòng cùng mã + cùng cách làm", False, "đáng lẽ phải throw")
except Throw:
    kiem("hai dòng cùng mã + cùng cách làm -> throw", True)

print("\n-- chọn bảng theo NGÀY HIỆU LỰC --")
DB["SX Bang Don Gia"] = [
    {"name": "DG-2026-01-01", "hieu_luc_tu": datetime.date(2026, 1, 1), "docstatus": 1},
    {"name": "DG-2026-06-15", "hieu_luc_tu": datetime.date(2026, 6, 15), "docstatus": 0},
    {"name": "DG-2026-09-01", "hieu_luc_tu": datetime.date(2026, 9, 1), "docstatus": 0},
]
for ngay, mong in [
    ("2026-09-06", "DG-2026-09-01"),
    ("2026-09-01", "DG-2026-09-01"),
    ("2026-08-31", "DG-2026-06-15"),
    ("2026-06-15", "DG-2026-06-15"),
    ("2026-02-02", "DG-2026-01-01"),
]:
    got = utils.bang_don_gia(ngay)
    kiem(f"ngày {ngay}", got == mong, f"ra {got}, mong {mong}")

kiem("bảng cũ lập trước D80 (docstatus=1) vẫn được dùng",
     utils.bang_don_gia("2026-03-03") == "DG-2026-01-01")

DB["SX Bang Don Gia"] = [
    {"name": "DG-2026-09-06", "hieu_luc_tu": datetime.date(2026, 9, 6), "docstatus": 0},
]
kiem("chấm bù ngày CŨ hơn mọi bảng -> dùng bảng sớm nhất, không ra rỗng",
     utils.bang_don_gia("2026-08-01") == "DG-2026-09-06",
     str(utils.bang_don_gia("2026-08-01")))

DB["SX Bang Don Gia"] = [
    {"name": "DG-HUY", "hieu_luc_tu": datetime.date(2026, 1, 1), "docstatus": 2},
]
kiem("bảng đã huỷ KHÔNG được dùng", utils.bang_don_gia("2026-09-06") is None)

DB["SX Bang Don Gia"] = []
kiem("chưa có bảng nào -> None", utils.bang_don_gia("2026-09-06") is None)

print("\n-- tra giá: ưu tiên đúng cách làm, không có thì giá chung --")
bang = {("A", ""): 100.0, ("A", "Máy"): 130.0, ("B", "Tay"): 90.0}
kiem("đúng cách làm", utils.tra_don_gia(bang, "A", "Máy") == 130.0)
kiem("cách làm lạ -> rơi về giá chung", utils.tra_don_gia(bang, "A", "Nướng") == 100.0)
kiem("không nêu cách làm -> giá chung", utils.tra_don_gia(bang, "A") == 100.0)
kiem("mã chỉ có giá theo cách làm, hỏi chung -> None",
     utils.tra_don_gia(bang, "B") is None)
kiem("mã lạ -> None", utils.tra_don_gia(bang, "Z") is None)
kiem("cach_lam_cua chỉ trả cách làm có khai giá",
     utils.cach_lam_cua(bang, "A") == ["Máy"])

print("DONGIA-FAIL ({} ca)".format(hong) if hong else "DONGIA-OK")
sys.exit(1 if hong else 0)
