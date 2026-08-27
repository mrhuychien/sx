"""Kiểm phần NGUY HIỂM của seed: số học lô, giá vốn, và cờ dry_run.

Vì sao phải có bài này (D76):
  - seed_ton_dau so tồn theo TỔNG cả kho nhưng ghi số cho RIÊNG một lô, nên tồn 500
    ở lô NCC + ghi 800 vào lô TD- là tổng 1300 — 500 kg hàng ma vào sổ kho.
  - Giá vốn đọc ở Item master (hay để trống) rồi bịa 1000, định giá lại tồn thật.
  - `cint("true")` ra 0 nên ý "xem trước" thành GHI THẬT; `if "0"` truthy nên ý "ghi
    thật" thành không làm gì mà báo cáo vẫn nói đã làm.
Cả ba đều là chứng từ kho đã submit, không có nút hoàn tác.

Chạy: python3 scripts/test-seed.py   (verify.sh gọi sẵn)

Nạp module seed THẬT với một frappe giả tối thiểu — chép logic ra đây rồi test bản
chép là test chính mình, không phải test code chạy trên site.
"""
import os
import sys

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import datetime
import importlib.util
import types

class D(dict):
    __getattr__ = dict.get

class Throw(Exception): pass

def _khop(row, f):
    for k, v in (f or {}).items():
        cur = row.get(k)
        if isinstance(v, (tuple, list)) and len(v) == 2:
            op, val = v
            if op == "in" and cur not in val: return False
            if op == "like":
                if not str(cur or "").startswith(val.rstrip("%")): return False
            if op == "<" and not (cur is not None and cur < val): return False
        elif cur != v: return False
    return True

DB = {}
SR = []            # phiếu kiểm kê đã tạo

frappe = types.ModuleType("frappe")
def get_all(dt, filters=None, fields=None, pluck=None, **kw):
    rows = [r for r in DB.get(dt, []) if _khop(r, filters)]
    if pluck: return [r.get(pluck) for r in rows]
    return [D({k: r.get(k) for k in (fields or r.keys())}) for r in rows]
def get_value(dt, filters=None, fieldname=None, **kw):
    if isinstance(filters, str): filters = {"name": filters}
    rows = [r for r in DB.get(dt, []) if _khop(r, filters)]
    if not rows: return None
    if isinstance(fieldname, (list, tuple)):
        return D({k: rows[0].get(k) for k in fieldname})
    return rows[0].get(fieldname)
def sql(q, args=None, **kw):
    # chỉ một câu: tổng actual_qty của (item, kho, lô)
    it, kho, lo = args
    t = sum(float(r.get("actual_qty") or 0) for r in DB.get("Stock Ledger Entry", [])
            if r.get("item_code") == it and r.get("warehouse") == kho
            and r.get("batch_no") == lo and not r.get("is_cancelled"))
    return [[t]]
frappe.get_all = get_all
frappe.db = types.SimpleNamespace(
    get_value=get_value, exists=lambda dt, n: bool(get_value(dt, n, "name")),
    set_value=lambda *a, **k: None, sql=sql, commit=lambda: None,
    get_single_value=lambda dt, f: None, count=lambda dt, f=None: len(DB.get(dt, [])))
frappe.get_cached_value = lambda dt, n, f, **k: get_value(dt, n, f)
def _throw(msg, *a, **k): raise Throw(msg)
frappe.throw = _throw
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.get_meta = lambda dt: types.SimpleNamespace(
    has_field=lambda f: True, get_field=lambda f: True)
frappe.session = types.SimpleNamespace(user="Administrator")
frappe.defaults = types.SimpleNamespace(get_defaults=lambda: {})
frappe.log_error = lambda **k: None
class Doc(dict):
    def __init__(s, dt): super().__init__(doctype=dt, items=[]); s.flags = types.SimpleNamespace()
    def __getattr__(s, k): return s.get(k)
    def __setattr__(s, k, v):
        if k == "flags": object.__setattr__(s, k, v)
        else: s[k] = v
    def append(s, f, row): s.setdefault(f, []).append(row)
    def insert(s): s["name"] = f"{s['doctype']}-{len(SR)+1}"
    def submit(s): s["docstatus"] = 1; SR.append(s)
def new_doc(dt):
    d = Doc(dt)
    if dt == "Stock Reconciliation": d["items"] = []
    return d
frappe.new_doc = new_doc
frappe.get_doc = lambda x, n=None: (new_doc(x["doctype"]) if isinstance(x, dict) else None)
class Obj:
    """.items phải là DỮ LIỆU, không phải method của dict — nên dùng object thường."""
    def __init__(s, d):
        for k, v in d.items(): object.__setattr__(s, k, v)
    def __getattr__(s, k): return None
frappe.get_cached_doc = lambda dt, n: Obj(next(
    (r for r in DB.get(dt, []) if r.get("name") == n), {}))
frappe.utils = types.ModuleType("frappe.utils")
def getdate(x=None):
    if x is None: return datetime.date(2026, 8, 27)
    if isinstance(x, datetime.date): return x
    return datetime.date.fromisoformat(str(x))
frappe.utils.getdate = getdate
frappe.utils.add_days = lambda d, n: getdate(d) + datetime.timedelta(days=n)
def _cint(v, default=0):
    try: return int(v)
    except Exception:
        try: return int(float(v))
        except Exception: return default
frappe.utils.cint = _cint
frappe.utils.flt = lambda v, p=None: (round(float(v or 0), p) if p is not None else float(v or 0))
frappe.utils.nowdate = lambda: "2026-08-27"
frappe.utils.formatdate = lambda d: str(d)
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = frappe.utils
frappe.__dict__["_"] = lambda s: s

utils = types.ModuleType("sx.utils")
utils.get_settings = lambda: D({"cong_ty": "RVHG", "kho_nvl": "Kho NVL - R"})
utils.get_dau_items = lambda: []
utils.ten_btp_dau = lambda a, b: f"{a} {b}"
sx = types.ModuleType("sx"); sx.__path__ = []
for n, m in [("sx", sx), ("sx.utils", utils)]:
    sys.modules[n] = m

spec = importlib.util.spec_from_file_location("sx.seed", "sx/seed/__init__.py")
seed = importlib.util.module_from_spec(spec); sys.modules["sx.seed"] = seed
spec.loader.exec_module(seed)


def dung_db(bin_qty, lo, gia_bin=None, gia_item=None, gia_mua=None, co_lo=1):
    DB.clear(); SR.clear()
    DB["Item"] = [{"name": "Đỗ xanh", "has_batch_no": co_lo, "is_stock_item": 1,
                   "custom_sx_nhom": "NVL", "valuation_rate": gia_item,
                   "last_purchase_rate": gia_mua, "stock_uom": "Kg"}]
    DB["BOM"] = [{"name": "BOM-1", "item": "Bột nền", "is_active": 1, "is_default": 1,
                  "docstatus": 1, "company": "RVHG",
                  "items": [D({"item_code": "Đỗ xanh", "stock_qty": 40})]}]
    DB["Bin"] = [{"item_code": "Đỗ xanh", "warehouse": "Kho NVL - R",
                  "actual_qty": bin_qty, "valuation_rate": gia_bin}]
    DB["Batch"] = [{"name": k, "batch_id": k, "item": "Đỗ xanh"} for k in lo]
    DB["Company"] = [{"name": "RVHG"}]
    DB["Item Group"] = [{"name": "All Item Groups", "is_group": 1},
                        {"name": "Consumable", "is_group": 0}]
    DB["Stock Ledger Entry"] = [
        {"item_code": "Đỗ xanh", "warehouse": "Kho NVL - R", "batch_no": k,
         "actual_qty": v, "is_cancelled": 0} for k, v in lo.items()]

hong = 0
def kiem(ten, dieu_kien, chi_tiet=""):
    global hong
    if not dieu_kien: hong += 1
    print(f"  {'ok  ' if dieu_kien else 'HỎNG'} {ten}{(' — ' + chi_tiet) if chi_tiet else ''}")

MUC_TIEU = 40 * 20  # 1 BOM × 40kg × 20 mẻ = 800

print("A. Item CÓ LÔ, tồn 500 ở lô NCC, mục tiêu 800")
dung_db(500, {"NCC-A": 500}, gia_bin=25000)
seed.seed_ton_dau(dry_run=0)
r = SR[0]["items"][0]
kiem("ghi vào lô TD phần THIẾU (300), không phải 800", r["qty"] == 300, f"qty={r['qty']}")
kiem("tổng kho sau khi ghi = 800", 500 + r["qty"] == MUC_TIEU)
kiem("giá vốn lấy từ Bin (25000)", r["valuation_rate"] == 25000, f"={r['valuation_rate']}")

print("\nB. Đã có lô TD cũ 200 + lô NCC 300, mục tiêu 800")
dung_db(500, {"TD-010126": 200, "NCC-A": 300}, gia_bin=25000)
seed.seed_ton_dau(dry_run=0)
r = SR[0]["items"][0]
kiem("lô TD được đặt về 500 (800 − 300 lô khác)", r["qty"] == 500, f"qty={r['qty']}")
kiem("tổng kho sau khi ghi = 800", 300 + r["qty"] == MUC_TIEU)

print("\nC. Item KHÔNG lô, tồn 100, mục tiêu 800")
dung_db(100, {}, gia_bin=25000, co_lo=0)
seed.seed_ton_dau(dry_run=0)
r = SR[0]["items"][0]
kiem("đặt tuyệt đối 800", r["qty"] == MUC_TIEU, f"qty={r['qty']}")
kiem("không gắn lô", "batch_no" not in r)

print("\nD. Đã đủ tồn -> không sinh phiếu")
dung_db(900, {"NCC-A": 900}, gia_bin=25000)
seed.seed_ton_dau(dry_run=0)
kiem("không có phiếu nào", not SR)

print("\nE. Không có giá vốn ở đâu -> DỪNG, không ghi")
dung_db(0, {}, co_lo=0)
try:
    seed.seed_ton_dau(dry_run=0); kiem("phải throw", False)
except Throw as e:
    kiem("throw và nêu tên item", "Đỗ xanh" in str(e))
    kiem("không sinh phiếu nào", not SR)

print("\nF. Có giá vốn ở Item (master) khi Bin trống")
dung_db(0, {}, gia_item=18000, co_lo=0)
seed.seed_ton_dau(dry_run=0)
kiem("dùng 18000", SR[0]["items"][0]["valuation_rate"] == 18000)

print("\nG. Cố ý dựng site thử: truyền gia_mac_dinh")
dung_db(0, {}, co_lo=0)
seed.seed_ton_dau(dry_run=0, gia_mac_dinh=1000)
kiem("dùng giá bịa 1000 khi được yêu cầu", SR[0]["items"][0]["valuation_rate"] == 1000)

print("\nH. Cờ dry_run")
dung_db(500, {"NCC-A": 500}, gia_bin=25000)
seed.seed_ton_dau()
kiem("gọi trần = XEM TRƯỚC, không ghi", not SR)
dung_db(500, {"NCC-A": 500}, gia_bin=25000)
seed.seed_ton_dau(dry_run="true")
kiem("dry_run='true' = XEM TRƯỚC (trước đây cint('true')=0 -> ghi thật)", not SR)
dung_db(500, {"NCC-A": 500}, gia_bin=25000)
seed.seed_ton_dau(dry_run="yes")
kiem("dry_run='yes' = xem trước", not SR)
dung_db(500, {"NCC-A": 500}, gia_bin=25000)
try:
    seed.seed_ton_dau(dry_run="co le"); kiem("giá trị vô nghĩa phải DỪNG", False)
except Throw:
    kiem("dry_run='co le' -> throw, không ghi gì", not SR)
dung_db(500, {"NCC-A": 500}, gia_bin=25000)
seed.seed_ton_dau(dry_run="0")
kiem("dry_run='0' (chuỗi) = ghi thật", len(SR) == 1)
dung_db(500, {"NCC-A": 500}, gia_bin=25000)
seed.seed_ton_dau(dry_run="1")
kiem("dry_run='1' (chuỗi) = xem trước", not SR)

print("\nI. BOM không mặc định KHÔNG được cộng vào nhu cầu")
dung_db(0, {}, gia_bin=9000, co_lo=0)
DB["BOM"].append({"name": "BOM-THU", "item": "Bột nền", "is_active": 1, "is_default": 0,
                  "docstatus": 1, "company": "RVHG",
                  "items": [D({"item_code": "Đỗ xanh", "stock_qty": 40})]})
seed.seed_ton_dau(dry_run=0)
kiem("mục tiêu vẫn 800 chứ không phải 1600",
     SR[0]["items"][0]["qty"] == MUC_TIEU, f"qty={SR[0]['items'][0]['qty']}")

print("\nJ. seed_all gọi trần phải là XEM TRƯỚC và không ghi gì")
dung_db(0, {}, gia_bin=9000, co_lo=0)
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    bc = seed.seed_all()
out = buf.getvalue()
kiem("in ra chế độ DRY RUN", "DRY RUN" in out, out.split("Chế độ:")[-1].split("\n")[0].strip())
kiem("không sinh chứng từ kho nào", not SR)
kiem("có liệt kê item sẽ tạo", len(bc["item_tao"]) > 0, f"{len(bc['item_tao'])} item")
canh = " | ".join(bc["canh_bao"])
kiem("NÓI RA khi phải đoán Công ty", "chưa điền Công ty" in canh)
kiem("NÓI RA khi phải đoán Item Group",
     "không có Item Group" in canh, canh[:80])

print("\nK. dry_run vô nghĩa ở seed_all cũng DỪNG")
dung_db(0, {}, gia_bin=9000, co_lo=0)
try:
    with contextlib.redirect_stdout(io.StringIO()):
        seed.seed_all(dry_run="co le")
    kiem("phải throw", False)
except Throw:
    kiem("seed_all('co le') -> throw", True)

print("SEED-FAIL ({} ca)".format(hong) if hong else "SEED-OK")
sys.exit(1 if hong else 0)
