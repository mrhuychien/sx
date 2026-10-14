"""D207 — dọn âm trong lịch sử lô (sx.api.lo_am.don): câu SQL chạy THẬT trên SQLite, phiếu kho do một ERPNext giả
kiểm ĐÚNG ba điều ERPNext 16 kiểm khi ghi phiếu có lô:
  · xuất: tồn lô tại giờ ghi sổ không được âm (set_incoming_rate → validate_negative_batch);
  · xuất: cộng dồn CẢ LỊCH SỬ lô ở kho theo (giờ ghi sổ, giờ tạo) không được có điểm âm (get_batchwise_available_qty);
  · ghi lùi: không có phiếu Stock Reconciliation của lô đó ghi sau (check_future_entries_exists);
  · nhập vào lô hết hạn: chặn (validate_serialized_batch — D190).
Ca thật (14/10/2026): TH170-TONCU ở CH Tuệ Tĩnh còn 63 mà âm 3 lúc 12/10 14:36:08 → POS không bán được.

Chạy: python3 scripts/test-loam.py   (verify.sh gọi sẵn)
"""

import ast
import contextlib
import importlib.util
import io
import os
import re
import sqlite3
import sys
import types
from datetime import date, datetime

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(GOC)

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


class _dict(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


class Loi(Exception):
    pass


# ── SQLite đóng vai MariaDB ──
con = sqlite3.connect(":memory:", isolation_level=None)
con.row_factory = sqlite3.Row
con.executescript("""
create table `tabStock Ledger Entry` (name text, item_code text, warehouse text, batch_no text,
  serial_and_batch_bundle text, actual_qty real, posting_datetime text, creation text, is_cancelled int, docstatus int,
  voucher_type text, voucher_no text);
create table `tabSerial and Batch Entry` (parent text, item_code text, warehouse text, batch_no text, qty real,
  posting_datetime text, creation text, is_cancelled int, docstatus int, type_of_transaction text, voucher_type text);
create table `tabSerial and Batch Bundle` (name text, item_code text, warehouse text, voucher_type text,
  voucher_no text, docstatus int, is_cancelled int, type_of_transaction text, posting_datetime text);
""")
con.execute("begin")


def sql(q, args=None, as_dict=False):
    args = dict(args or {})
    q2 = re.sub(r"%\((\w+)\)s", lambda m: f":{m.group(1)}", q)
    rows = con.execute(q2, args).fetchall()
    return [_dict(dict(r)) for r in rows] if as_dict else [tuple(r) for r in rows]


DEM = {"bundle": 0, "sle": 0, "tao": 0, "se": 0}


def _tao():
    DEM["tao"] += 1
    return f"2026-10-14 10:00:{DEM['tao']:02d}"


def vao(item, kho, lo, q, luc, tao=None, loai="Stock Entry", phieu=None, huy=0, voucher_type=None):
    """Một dòng sổ kho có lô qua Serial and Batch Bundle (như ERPNext v15+)."""
    DEM["bundle"] += 1
    sb = f"SABB-{DEM['bundle']}"
    kieu = "Inward" if q > 0 else "Outward"
    tao = tao or _tao()
    con.execute("insert into `tabSerial and Batch Bundle` values (?,?,?,?,?,?,?,?,?)",
                (sb, item, kho, voucher_type or loai, phieu, 1, huy, kieu, luc))
    con.execute("insert into `tabSerial and Batch Entry` values (?,?,?,?,?,?,?,?,?,?,?)",
                (sb, item, kho, lo, q, luc, tao, huy, 1, kieu, voucher_type or loai))
    DEM["sle"] += 1
    con.execute("insert into `tabStock Ledger Entry` values (?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"SLE-{DEM['sle']}", item, kho, None, sb, q, luc, tao, huy, 1, loai, phieu))


def cu(item, kho, lo, q, luc, tao=None, loai="Stock Entry", phieu=None):
    """Dòng sổ kho kiểu cũ: batch_no ngay trên sổ kho, không có bundle."""
    DEM["sle"] += 1
    con.execute("insert into `tabStock Ledger Entry` values (?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"SLE-{DEM['sle']}", item, kho, lo, None, q, luc, tao or _tao(), 0, 1, loai, phieu))


def get_datetime(x=None):
    if isinstance(x, datetime):
        return x
    if isinstance(x, date):
        return datetime(x.year, x.month, x.day)
    return datetime.fromisoformat(str(x))


def getdate(x=None):
    if x is None:
        return date(2026, 10, 14)
    return x if isinstance(x, date) and not isinstance(x, datetime) else get_datetime(x).date()


HSD = {"E1-HET": "2026-09-30"}          # HSD lô (Batch.expiry_date)
TEN = {"TH170": "Bánh TH 170g", "X1": "Bánh X1"}
SE_DS, LOI_SE = [], {}
CHO_AM = {"v": False}                    # Stock Settings.allow_negative_stock_for_batch


def _get_value(dt, name, field=None, *a, **k):
    if dt == "Batch" and field == "expiry_date":
        return HSD.get(name)
    if dt == "Warehouse" and field == "company":
        return "Công ty cổ phần Hoàng Giang"
    return None


def _set_value(dt, name, field, v=None, **k):
    if dt == "Batch" and field == "expiry_date":
        HSD[name] = v


def _savepoint(ten):
    con.execute(f"savepoint {ten}")


def _rollback(save_point=None):
    con.execute(f"rollback to savepoint {save_point}")


def _lich_su(item, kho, lo):
    """Cộng dồn như ERPNext get_batchwise_available_qty (viết riêng ở đây — không dùng lại hàm của lệnh dọn)."""
    rows = sql("""select e.qty as q, e.posting_datetime as luc, e.creation as tao from `tabSerial and Batch Entry` e
                   join `tabStock Ledger Entry` s on s.serial_and_batch_bundle = e.parent
                  where s.is_cancelled = 0 and e.is_cancelled = 0 and e.docstatus = 1 and e.item_code = :i
                    and e.warehouse = :w and e.batch_no = :b and e.type_of_transaction in ('Inward', 'Outward')
                    and e.voucher_type != 'Pick List'""", {"i": item, "w": kho, "b": lo}, as_dict=True)
    rows += sql("""select actual_qty as q, posting_datetime as luc, creation as tao from `tabStock Ledger Entry`
                    where is_cancelled = 0 and docstatus = 1 and serial_and_batch_bundle is null and item_code = :i
                      and warehouse = :w and batch_no = :b""", {"i": item, "w": kho, "b": lo}, as_dict=True)
    return sorted(rows, key=lambda r: (get_datetime(r.luc), get_datetime(r.tao)))


class StockEntry:
    """Như Document Stock Entry: thuộc tính thường, bảng con `items` (không phải dict — se.items là bảng dòng)."""

    def __init__(self, **k):
        self.items, self.flags, self.name = [], types.SimpleNamespace(), None
        self.__dict__.update(k)

    def append(self, k, v):
        r = _dict(v)
        getattr(self, k).append(r)
        return r

    def insert(self):
        DEM["se"] += 1
        self.name = f"STE-D{DEM['se']}"
        SE_DS.append(self)

    def submit(self):
        luc = f"{self.posting_date} {self.posting_time}"
        for r in self.items:
            kho, xuat = r.t_warehouse or r.s_warehouse, bool(r.s_warehouse)
            if LOI_SE.get(r.item_code) == self.purpose:
                raise Loi(f"lỗi giả ở {self.purpose}")
            if not xuat and HSD.get(r.batch_no) and getdate(HSD[r.batch_no]) < getdate(luc):
                raise Loi(f"Row #1: The batch {r.batch_no} has already expired.")
            if sql("""select 1 from `tabSerial and Batch Bundle` p
                        join `tabSerial and Batch Entry` e on e.parent = p.name
                       where p.item_code = :i and p.warehouse = :w and e.batch_no = :b and p.docstatus = 1
                         and p.is_cancelled = 0 and p.voucher_type = 'Stock Reconciliation'
                         and p.posting_datetime > :l""",
                   {"i": r.item_code, "w": kho, "b": r.batch_no, "l": luc}):
                raise Loi("Batches Exists In Future Transaction(s)")
            vao(r.item_code, kho, r.batch_no, -r.qty if xuat else r.qty, luc, loai="Stock Entry", phieu=self.name)
            if xuat:
                ds = _lich_su(r.item_code, kho, r.batch_no)
                tai = sum(x.q for x in ds if get_datetime(x.luc) <= get_datetime(luc))
                if round(tai, 3) < 0:
                    raise Loi(f"Batch No {r.batch_no} of an Item {r.item_code} has negative stock of quantity {tai}")
                ton = 0.0
                for x in ds:
                    ton += x.q
                    if round(ton, 3) < 0 and not CHO_AM["v"]:
                        raise Loi(f"The Batch {r.batch_no} of an item {r.item_code} has negative stock in the "
                                  f"warehouse {kho} as of {x.luc}")


fr = types.ModuleType("frappe")
fr._dict = _dict
fr._ = lambda s: s
fr.db = types.SimpleNamespace(sql=sql, get_value=_get_value, set_value=_set_value, savepoint=_savepoint,
                              rollback=_rollback)
fr.get_precision = lambda dt, f: 3
fr.get_all = lambda dt, filters=None, fields=None, **k: [
    _dict(name=i, item_name=TEN.get(i, i)) for i in (filters or {}).get("name", ("in", []))[1] if i]
fr.new_doc = lambda dt: StockEntry()
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.get_datetime = get_datetime
fu.getdate = getdate
fu.nowdate = lambda: "2026-10-14"
fu.now_datetime = lambda: datetime(2026, 10, 14, 10, 0, 0)
fr.utils = fu
sys.modules.update({"frappe": fr, "frappe.utils": fu})
for g in ("sx", "sx.api", "sx.sx", "sx.sx.doctype", "sx.sx.doctype.sx_kiem_ke"):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m
kk = types.ModuleType("sx.api.kiemke")
kk.so_vn = lambda q: f"{float(q):g}"
mfg = types.ModuleType("sx.api.mfg")
mfg.gia_von_hien = lambda item, kho=None: 50000.0
mfg.loai_phieu_kho = lambda purpose="Manufacture": purpose
sys.modules.update({"sx.api.kiemke": kk, "sx.api.mfg": mfg})
# tam_bo_hsd / tra_hsd THẬT (D190) — lấy đúng mã trong tệp, không nạp cả controller kiểm kê
goc = open("sx/sx/doctype/sx_kiem_ke/sx_kiem_ke.py", encoding="utf-8").read()
kke = types.ModuleType("sx.sx.doctype.sx_kiem_ke.sx_kiem_ke")
kke.__dict__.update(frappe=fr, getdate=getdate, nowdate=fu.nowdate)
for n in ast.parse(goc).body:
    if isinstance(n, ast.FunctionDef) and n.name in ("tam_bo_hsd", "tra_hsd"):
        exec(compile(ast.Module([n], []), "sx_kiem_ke.py", "exec"), kke.__dict__)
sys.modules["sx.sx.doctype.sx_kiem_ke.sx_kiem_ke"] = kke

sp = importlib.util.spec_from_file_location("sx.api.lo_am", "sx/api/lo_am.py")
L = importlib.util.module_from_spec(sp)
sys.modules["sx.api.lo_am"] = L
sp.loader.exec_module(L)

TT, TP = "CH Tuệ Tĩnh - HGC", "Thành phẩm - HGC"
# A. ca thật: bán 3 lúc 14:36:08 (hoá đơn gộp lập lúc 21:00) trước khi lô tồn cũ vào sổ (17:00:00.5 — giờ có lẻ giây)
vao("TH170", TT, "TH170-TONCU", -3, "2026-10-12 14:36:08", "2026-10-12 21:00:00", "Sales Invoice", "SINV-1")
vao("TH170", TT, "TH170-TONCU", 40, "2026-10-12 17:00:00.500000", "2026-10-12 17:30:00", "Stock Entry", "STE-KK")
vao("TH170", TT, "TH170-TONCU", -10, "2026-10-12 21:00:00", "2026-10-12 21:00:01", "Sales Invoice", "SINV-2")
vao("TH170", TT, "TH170-TONCU", 36, "2026-10-13 09:00:00", "2026-10-13 09:00:00", "Stock Entry", "STE-CK")
# B. hai lần âm (−3 rồi −5): dọn một lần theo lần âm sâu nhất
for q, h in ((5, "08:00"), (-8, "09:00"), (4, "10:00"), (-6, "11:00"), (10, "12:00")):
    vao("TH170", TT, "LOT-B", q, f"2026-10-10 {h}:00", f"2026-10-10 {h}:00", "Stock Entry", f"STE-B{h}")
# B2. hai lần âm, lần SÂU hơn đến TRƯỚC (−5 rồi −2): vẫn nhập theo −5 (lấy lần cuối thì chỉ bù 2 → còn âm 3)
for q, h in ((5, "08:00"), (-10, "09:00"), (6, "10:00"), (-3, "11:00"), (10, "12:00")):
    vao("B2", TP, "B2-SAU", q, f"2026-10-10 {h}:00", f"2026-10-10 {h}:00", "Stock Entry", f"STE-B2{h}")
# C. không âm
vao("H24", TP, "H24-OK", 10, "2026-10-01 08:00:00")
vao("H24", TP, "H24-OK", -10, "2026-10-02 08:00:00")
# D. âm tới hiện tại (thiếu hàng thật)
vao("H24", TP, "H24-AM", 2, "2026-10-10 08:00:00")
vao("H24", TP, "H24-AM", -5, "2026-10-11 08:00:00", loai="Sales Invoice", phieu="SINV-D")
# E. dòng kiểu cũ (batch_no trên sổ kho) lẫn bundle
cu("X1", TP, "X1-CU", -2, "2026-10-10 08:00:00", phieu="STE-X0")
vao("X1", TP, "X1-CU", 10, "2026-10-10 09:00:00", phieu="STE-X1")
# F. dòng đã huỷ / Pick List không tính
vao("H24", TP, "H24-HUY", 5, "2026-10-10 08:00:00")
vao("H24", TP, "H24-HUY", -10, "2026-10-10 09:00:00", huy=1)
vao("H24", TP, "H24-HUY", -10, "2026-10-10 09:30:00", voucher_type="Pick List")
# G. có Stock Reconciliation ghi sau điểm âm
vao("S1", TP, "S1-KK", -1, "2026-10-10 08:00:00")
vao("S1", TP, "S1-KK", 5, "2026-10-10 09:00:00")
vao("S1", TP, "S1-KK", 1, "2026-10-12 08:00:00", loai="Stock Reconciliation", phieu="MAT-RECO-1")
# H. lô đã hết hạn (HSD 30/09) có điểm âm 05/10
vao("E1", TP, "E1-HET", -2, "2026-10-05 08:00:00")
vao("E1", TP, "E1-HET", 10, "2026-10-05 09:00:00")
# I. hai dòng CÙNG giờ ghi sổ: ERPNext xếp theo giờ tạo — dòng xuất tạo trước → âm (dù dòng nhập được ghi vào sổ trước)
vao("T2", TP, "T2-CUNG", 5, "2026-10-11 10:00:00", "2026-10-11 10:05:00", phieu="STE-T2N")
vao("T2", TP, "T2-CUNG", -5, "2026-10-11 10:00:00", "2026-10-11 10:01:00", phieu="STE-T2X")
vao("T2", TP, "T2-CUNG", 3, "2026-10-11 11:00:00", "2026-10-11 11:00:00", phieu="STE-T2B")
# K. hết âm nhờ một phiếu ghi NGÀY TƯƠNG LAI (20/10): tới hôm nay lô vẫn âm → không dọn
vao("K1", TP, "K1-TL", -2, "2026-10-13 08:00:00")
vao("K1", TP, "K1-TL", 5, "2026-10-20 08:00:00")
con.execute("commit")
con.execute("begin")


def ton(item, kho, lo):
    return round(sum(x.q for x in _lich_su(item, kho, lo)), 3)


def so_sle():
    return sql("select count(*) from `tabStock Ledger Entry`")[0][0]


print("-- xem trước: tìm đúng điểm âm như ERPNext --")
truoc = so_sle()
r = L.xu_ly()
lo = {x["lo"]: x for x in r["lo_am"]}
bq = {x["lo"]: x for x in r["bo_qua"]}
kiem("xem trước không ghi gì", so_sle() == truoc and r["chay"] == 0)
kiem("đúng các lô cần dọn (âm trong quá khứ, nay hết âm)",
     sorted(lo) == ["B2-SAU", "E1-HET", "LOT-B", "T2-CUNG", "TH170-TONCU", "X1-CU"], sorted(lo))
kiem("cùng giờ ghi sổ → xếp theo giờ tạo như ERPNext: dòng xuất tạo trước làm âm 5",
     (lo["T2-CUNG"]["am_nhat"], lo["T2-CUNG"]["am_tu"], lo["T2-CUNG"]["xuat_luc"])
     == (-5.0, "Stock Entry STE-T2X", "2026-10-11 10:00:00"), lo["T2-CUNG"])
a = lo["TH170-TONCU"]
kiem("ca thật: âm 3 lúc 12/10 14:36:08 do SINV-1, tồn nay 63, tên hàng",
     (a["am_nhat"], a["am_luc"], a["am_tu"], a["ton_nay"], a["ten"])
     == (-3.0, "2026-10-12 14:36:08", "Sales Invoice SINV-1", 63.0, "Bánh TH 170g"), a)
kiem("nhập 3 lúc 14:36:07; xuất lại lúc lô hết âm — 17:00:00.5 làm tròn LÊN 17:00:01 (không đứng trước dòng đó)",
     (a["nhap"], a["nhap_luc"], a["xuat_luc"], a["het_tu"])
     == (3.0, "2026-10-12 14:36:07", "2026-10-12 17:00:01", "Stock Entry STE-KK"), a)
b = lo["LOT-B"]
kiem("hai lần âm: dọn MỘT lần theo lần âm sâu nhất (−5), từ lần âm đầu tới lần hết âm cuối",
     (b["am_nhat"], b["nhap"], b["nhap_luc"], b["xuat_luc"])
     == (-5.0, 5.0, "2026-10-10 08:59:59", "2026-10-10 12:00:00"),
     b)
b2 = lo["B2-SAU"]
kiem("lần âm sâu đến trước lần âm nông: vẫn theo lần sâu nhất (−5), xuất lúc hết âm lần cuối",
     (b2["am_nhat"], b2["nhap"], b2["nhap_luc"], b2["xuat_luc"])
     == (-5.0, 5.0, "2026-10-10 08:59:59", "2026-10-10 12:00:00"), b2)
kiem("dòng kiểu cũ (batch_no trên sổ kho) cộng chung với bundle", lo["X1-CU"]["am_nhat"] == -2.0, lo["X1-CU"])
kiem("lô không âm / dòng đã huỷ / Pick List: không có trong danh sách",
     "H24-OK" not in lo and "H24-HUY" not in lo and "H24-HUY" not in bq)
kiem("lô đang âm tới hiện tại: KHÔNG dọn, nói lý do", "H24-AM" in bq and "âm tới hiện tại" in bq["H24-AM"]["ly_do"],
     bq.get("H24-AM"))
kiem("chỉ hết âm nhờ phiếu ghi ngày tương lai: hôm nay vẫn âm → KHÔNG dọn; tồn tính tới HÔM NAY (−2, không +3)",
     "K1-TL" in bq and "K1-TL" not in lo and bq["K1-TL"]["ton_nay"] == -2.0
     and bq["K1-TL"]["ly_do"].startswith("lô đang âm tới hiện tại (-2) — chỉ hết âm nhờ Stock Entry")
     and "NGÀY TƯƠNG LAI 2026-10-20 08:00:00" in bq["K1-TL"]["ly_do"], bq.get("K1-TL"))
kiem("lô âm tới dòng cuối: lý do không nhắc phiếu tương lai",
     bq["H24-AM"]["ly_do"].startswith("lô đang âm tới hiện tại (-3) — thiếu hàng thật"), bq["H24-AM"]["ly_do"])
kiem("có Stock Reconciliation ghi sau điểm âm: KHÔNG dọn, chỉ đúng phiếu đó",
     "S1-KK" in bq and "MAT-RECO-1" in bq["S1-KK"]["ly_do"], bq.get("S1-KK"))
kiem("lọc theo mã / lô", [x["lo"] for x in L.xu_ly(item="TH170")["lo_am"]] == ["LOT-B", "TH170-TONCU"]
     and [x["lo"] for x in L.xu_ly(lo="X1-CU")["lo_am"]] == ["X1-CU"])

bc = L.bao_cao(r).split("\n")
kiem("báo cáo xem trước: đầu đề XEM TRƯỚC + cách làm thật, số lô, từng lô một dòng điểm âm + một dòng cặp phiếu",
     bc[0].startswith("DỌN ÂM LỊCH SỬ LÔ — XEM TRƯỚC") and "{'chay': 1}" in bc[0] and "Lô dọn được: 6" in bc
     and "  5. TH170 Bánh TH 170g | CH Tuệ Tĩnh - HGC | lô TH170-TONCU: âm 3 lúc 2026-10-12 14:36:08 (Sales Invoice "
         "SINV-1), tồn nay 63" in bc
     and "     → nhập 3 lúc 2026-10-12 14:36:07, xuất lại 3 lúc 2026-10-12 17:00:01 (lô hết âm nhờ Stock Entry STE-KK)"
     in bc, bc)
kiem("báo cáo xem trước: lô không dọn kèm lý do; chưa có dòng phiếu đã ghi / bước tiếp",
     "Không dọn — phải xử lý tay: 3" in bc and any(x.startswith("    lý do: lô đang âm tới hiện tại") for x in bc)
     and not any("đã ghi" in x or "Bước tiếp" in x for x in bc), bc)
ra = io.StringIO()
with contextlib.redirect_stdout(ra):
    tra = L.don()
kiem("lệnh bench don(): IN báo cáo, trả None (bench in giá trị trả về thành JSON \\uXXXX một dòng)",
     tra is None and ra.getvalue().rstrip("\n").split("\n") == bc and so_sle() == truoc, (tra, ra.getvalue()[:200]))

print("\n-- làm thật --")
ton_truoc = {k: ton(*k) for k in [("TH170", TT, "TH170-TONCU"), ("TH170", TT, "LOT-B"), ("X1", TP, "X1-CU"),
                                  ("E1", TP, "E1-HET"), ("T2", TP, "T2-CUNG"), ("B2", TP, "B2-SAU")]}
LOI_SE["X1"] = "Material Issue"           # lô X1: phiếu xuất hỏng → bỏ cả lô đó (kể cả phiếu nhập đã ghi)
rx = L.xu_ly(lo="X1-CU", chay=1)
kiem("lọc đúng lô lỗi (không lô nào bị bỏ qua): vẫn báo còn lô chưa dọn, GIỮ bật — không bảo 'đã hết âm'",
     rx["lo_am"][0].get("loi") and not rx["bo_qua"] and "Còn 1 lô" in rx["con_viec"], rx)
r = L.xu_ly(chay=1)
lo = {x["lo"]: x for x in r["lo_am"]}
kiem("mỗi lô một cặp phiếu nhập + xuất (ERPNext giả kiểm đủ: tồn lúc ghi, lịch sử, kiểm kê sau, lô hết hạn)",
     all(lo[k].get("phieu_nhap") and lo[k].get("phieu_xuat")
         for k in ("TH170-TONCU", "LOT-B", "B2-SAU", "E1-HET", "T2-CUNG")),
     {k: (v.get("phieu_nhap"), v.get("phieu_xuat"), v.get("loi")) for k, v in lo.items()})
se = {s.name: s for s in SE_DS}
pa = se[lo["TH170-TONCU"]["phieu_nhap"]]
px = se[lo["TH170-TONCU"]["phieu_xuat"]]
kiem("phiếu nhập: Material Receipt 3 vào đúng lô, ghi 12/10 14:36:07, giá vốn hiện tại, ghi chú D207",
     (pa.purpose, pa.posting_date, pa.posting_time, pa.items[0].qty, pa.items[0].batch_no,
      pa.items[0].t_warehouse, pa.items[0].basic_rate, pa.remarks.startswith(L.GHI_CHU))
     == ("Material Receipt", "2026-10-12", "14:36:07", 3.0, "TH170-TONCU", TT, 50000.0, True), vars(pa))
kiem("phiếu xuất: Material Issue 3 khỏi đúng lô, ghi 12/10 17:00:01",
     (px.purpose, px.posting_date, px.posting_time, px.items[0].qty, px.items[0].s_warehouse)
     == ("Material Issue", "2026-10-12", "17:00:01", 3.0, TT), vars(px))
kiem("tồn hiện tại KHÔNG ĐỔI", all(ton(*k) == v for k, v in ton_truoc.items() if k[0] != "X1"),
     {k: (v, ton(*k)) for k, v in ton_truoc.items()})
kiem("lô hết hạn: nhập được (tạm bỏ HSD lúc ghi), HSD trả lại nguyên", lo["E1-HET"].get("phieu_nhap")
     and HSD["E1-HET"] == "2026-09-30", HSD)
kiem("lô X1 lỗi: báo lỗi, rút lại CẢ phiếu nhập của lô đó; lô khác vẫn dọn",
     "lỗi giả" in (lo["X1-CU"].get("loi") or "") and ton("X1", TP, "X1-CU") == 8.0
     and len(_lich_su("X1", TP, "X1-CU")) == 2, lo["X1-CU"])
kiem("còn lô lỗi / không dọn được → bảo GIỮ 'Allow Negative Stock for Batch' bật",
     "Còn 4 lô" in r["con_viec"] and "BẬT" in r["con_viec"], r["con_viec"])
bc = L.bao_cao(r).split("\n")
kiem("báo cáo làm thật: phiếu đã ghi từng lô, lô lỗi nói rõ không ghi gì, bước tiếp",
     bc[0] == "DỌN ÂM LỊCH SỬ LÔ — LÀM THẬT"
     and f"     ✓ đã ghi: phiếu nhập {pa.name}, phiếu xuất {px.name}" in bc
     and "     ✗ LỖI — lô này không ghi gì: lỗi giả ở Material Issue" in bc
     and bc[-1] == "Bước tiếp: " + r["con_viec"], bc)
LOI_SE.clear()
r2 = L.xu_ly()
kiem("chạy lại: chỉ còn lô lỗi lần trước + hai lô không dọn được", [x["lo"] for x in r2["lo_am"]] == ["X1-CU"]
     and sorted(x["lo"] for x in r2["bo_qua"]) == ["H24-AM", "K1-TL", "S1-KK"], r2)
r3 = L.xu_ly(chay=1)
kiem("chạy lại làm thật: dọn nốt, hết điểm âm (trừ lô âm tới hiện tại / vướng kiểm kê — vẫn bảo giữ bật)",
     not L.xu_ly()["lo_am"] and "Còn 3 lô" in r3["con_viec"], r3["con_viec"])
r4 = L.xu_ly(item="TH170", chay=1)
kiem("mã đã sạch (có lọc): không ghi gì, KHÔNG bảo tắt ngay — bảo chạy lại không lọc cho chắc",
     not r4["lo_am"] and not r4["bo_qua"] and "KHÔNG lọc" in r4["con_viec"], r4)
r4b, r4c = L.xu_ly(lo="LOT-B", chay=1), L.xu_ly(kho=TT, chay=1)
kiem("lọc theo lô / theo kho cũng vậy", all(not x["lo_am"] and "KHÔNG lọc" in x["con_viec"] for x in (r4b, r4c)),
     (r4b, r4c))
con.execute("delete from `tabSerial and Batch Entry` where batch_no in ('H24-AM', 'S1-KK', 'K1-TL')")
r5 = L.xu_ly(chay=1)
kiem("không còn lô nào âm: báo có thể tắt lại 'Allow Negative Stock for Batch'",
     not r5["lo_am"] and not r5["bo_qua"] and "có thể tắt lại" in r5["con_viec"], r5)
kiem("báo cáo khi sạch: không lô nào âm + bước tiếp",
     L.bao_cao(r5).split("\n")[1:] == ["Không lô nào có điểm âm trong lịch sử.", "Bước tiếp: " + r5["con_viec"]],
     L.bao_cao(r5).split("\n"))
CHO_AM["v"] = False
ok = True
try:
    StockEntry(posting_date="2026-10-14", posting_time="11:00:00", purpose="Material Issue", name="POS-14-10",
               items=[_dict(item_code="TH170", s_warehouse=TT, batch_no="TH170-TONCU", qty=1)]).submit()
except Loi as e:
    ok = str(e)
kiem("sau khi dọn: bán TH170-TONCU hôm nay KHÔNG còn báo âm lịch sử (ERPNext giả, đã tắt cho phép âm lô)",
     ok is True, ok)

print("LOAM-OK" if not hong else f"LOAM: {hong} HỎNG")
sys.exit(1 if hong else 0)
