"""D194: truy vấn tồn theo (mã, lô) của kiểm kê (sx_kiem_ke._so_lo; D195: _sle_khoang) chạy THẬT trên SQLite — test giả khác đều thay
_so_lo bằng số dựng sẵn nên không thấy lỗi SQL.

Lỗi gốc: cộng actual_qty của sổ cái kho. Phiếu Stock Reconciliation (tồn đầu kỳ, kiểm kê trên ERPNext) ghi actual_qty
= 0 và đặt số tồn ở qty_after_transaction → tồn 6.265 hiện thành −6.331. Nay tổng của mã = qty_after_transaction của
dòng cuối (như ERPNext), lô cộng từ Serial and Batch Entry / batch_no cũ, phần chênh là tồn không lô.
Chạy: python3 scripts/test-tonlo-sql.py
"""
import importlib.util
import os
import re
import sqlite3
import sys
import types

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, GOC)

# frappe giả tối thiểu: db.sql chạy trên SQLite (đổi %(x)s → :x, tuple → danh sách), _dict, flt
class _dict(dict):
    __getattr__ = dict.get
con = sqlite3.connect(":memory:")
con.row_factory = sqlite3.Row
con.executescript("""
create table `tabStock Ledger Entry` (name text, item_code text, warehouse text, batch_no text, serial_and_batch_bundle text,
  actual_qty real, qty_after_transaction real, posting_datetime text, creation text, is_cancelled int, voucher_type text);
create table `tabSerial and Batch Entry` (parent text, batch_no text, qty real);
""")
def sql(q, args=None, as_dict=False):
    args = dict(args or {})
    def mo(m):
        k = m.group(1)
        v = args[k]
        if isinstance(v, tuple):
            ks = []
            for j, x in enumerate(v):
                args[f"{k}{j}"] = x; ks.append(f":{k}{j}")
            return "(" + ", ".join(ks) + ")"
        return f":{k}"
    q2 = re.sub(r"%\((\w+)\)s", mo, q)
    args = {k: v for k, v in args.items() if not isinstance(v, tuple)}
    rows = con.execute(q2, args).fetchall()
    return [_dict(dict(r)) for r in rows] if as_dict else [tuple(r) for r in rows]
fr = types.ModuleType("frappe"); fr._dict = _dict; fr.db = types.SimpleNamespace(sql=sql)
fu = types.ModuleType("frappe.utils")
fu.flt = lambda x, p=None: round(float(x or 0), p) if p is not None else float(x or 0)
for n in ("add_days", "cint", "get_datetime", "getdate", "now_datetime", "nowdate"):
    setattr(fu, n, lambda *a, **k: None)
fr.utils = fu; fr._ = lambda s: s
fm = types.ModuleType("frappe.model"); fmd = types.ModuleType("frappe.model.document"); fmd.Document = object
sys.modules.update({"frappe": fr, "frappe.utils": fu, "frappe.model": fm, "frappe.model.document": fmd})
spec = importlib.util.spec_from_file_location("sx_kiem_ke", os.path.join(GOC, "sx/sx/doctype/sx_kiem_ke/sx_kiem_ke.py"))
K = importlib.util.module_from_spec(spec); spec.loader.exec_module(K)
ins = lambda *r: con.execute("insert into `tabStock Ledger Entry` values (?,?,?,?,?,?,?,?,?,?,?)", r)
# 1) mã không lô: tồn đầu bằng Stock Reconciliation (actual 0, qat 12596), rồi bán 6331 → ERP 6265
ins("s1", "SR170", "TP", None, None, 0, 12596, "2026-01-01 08:00:00", "2026-01-01 08:00:00", 0, "Stock Reconciliation")
ins("s2", "SR170", "TP", None, None, -6331, 6265, "2026-05-01 08:00:00", "2026-05-01 08:00:00", 0, "Sales Invoice")
ins("s2x", "SR170", "TP", None, None, -999, 5266, "2026-05-02 08:00:00", "2026-05-02 08:00:00", 1, "Sales Invoice")   # đã huỷ
ins("s3", "SR170", "KHAC", None, None, 50, 50, "2026-05-01 08:00:00", "2026-05-01 08:00:00", 0, "Stock Entry")      # kho khác
# 2) mã có lô: nhập 100 lô A (bundle), bán 30 lô A, dư 5 không lô (dữ liệu cũ)
ins("b1", "LOT", "TP", None, "SB1", 100, 100, "2026-06-01 08:00:00", "2026-06-01 08:00:00", 0, "Stock Entry")
con.execute("insert into `tabSerial and Batch Entry` values ('SB1','A',100)")
ins("b2", "LOT", "TP", None, "SB2", -30, 70, "2026-06-02 08:00:00", "2026-06-02 08:00:00", 0, "Sales Invoice")
con.execute("insert into `tabSerial and Batch Entry` values ('SB2','A',-30)")
ins("b3", "LOT", "TP", None, None, 5, 75, "2026-06-03 08:00:00", "2026-06-03 08:00:00", 0, "Stock Entry")
ins("b4", "LOT", "TP", "B-OLD", None, 7, 82, "2026-06-04 08:00:00", "2026-06-04 08:00:00", 0, "Stock Entry")      # lô ghi kiểu cũ
# 3) cùng giờ ghi sổ: dòng tạo sau là dòng cuối
ins("c1", "TIE", "TP", None, None, 10, 10, "2026-07-01 08:00:00", "2026-07-01 08:00:00", 0, "Stock Entry")
ins("c2", "TIE", "TP", None, None, -4, 6, "2026-07-01 08:00:00", "2026-07-01 08:00:05", 0, "Sales Invoice")
r = sorted((x.item, x.b or "", x.q) for x in K._so_lo("TP", ["SR170", "LOT", "TIE"]))
assert r == [("LOT", "", 5.0), ("LOT", "A", 70.0), ("LOT", "B-OLD", 7.0), ("SR170", "", 6265.0), ("TIE", "", 6.0)], r
r = sorted((x.item, x.b or "", x.q) for x in K._so_lo("TP", ["SR170", "LOT"], den="2026-06-02 12:00:00"))
assert r == [("LOT", "A", 70.0), ("SR170", "", 6265.0)], r
r = sorted((x.item, x.b or "", x.q) for x in K._so_lo("TP", ["SR170"], den="2026-03-01 00:00:00"))
assert r == [("SR170", "", 12596.0)], r
# D195: dòng sổ cái theo khoảng ghi sổ (tu, den] — mỗi lô một dòng (bundle tách theo lô), bỏ phiếu huỷ / kho khác
con.execute("alter table `tabStock Ledger Entry` add column voucher_no text")
con.execute("update `tabStock Ledger Entry` set voucher_no = upper(name)")
r = [(x.item, x.b, x.q, x.vn) for x in K._sle_khoang(["TP"], ["LOT"], tu="2026-06-01 12:00:00")]
assert r == [("LOT", "A", -30.0, "B2"), ("LOT", None, 5.0, "B3"), ("LOT", "B-OLD", 7.0, "B4")], r
r = [(x.kho, x.item, x.b, x.q, x.vt, x.luc) for x in K._sle_khoang(["TP"], ["SR170", "LOT"], tu="2026-04-01 00:00:00",
                                                                    den="2026-06-01 08:00:00")]
assert r == [("TP", "SR170", None, -6331.0, "Sales Invoice", "2026-05-01 08:00:00"),
             ("TP", "LOT", "A", 100.0, "Stock Entry", "2026-06-01 08:00:00")], r
assert K._sle_khoang([], ["LOT"]) == [] and K._sle_khoang(["TP"], []) == []
print("TONLO-SQL-OK")
