"""D221 — phiếu POS: dòng bán quá số còn của lô đang gắn → chia sang các lô khác (một gói lô nhiều lô).
D222 — hoá đơn bán trừ kho / phiếu giao cũng vậy: lô người lập chọn luôn lấy trước, ghi lùi ngày lấy số nhỏ hơn giữa lúc
ghi sổ và hiện tại, gửi xong báo lại các dòng đã chia.

Lỗi thật (22/10/2026): mã còn hai lô, bán một lần số lượng mà phải gộp hai lô mới đủ → POS báo lô âm. Màn POS của
ERPNext gắn mỗi dòng MỘT lô (chọn lúc số lượng còn là 1), tăng số lượng lô vẫn vậy; lúc thanh toán ERPNext dựng gói lô
một lô cho cả dòng → "Batch No … has negative stock".

Bài này nạp sx/api/pos_lo.py THẬT; phía ERPNext giả đúng phần hook gọi tới: get_available_batches (số còn từng lô, đã
xếp HSD gần trước; lúc ghi sổ / hiện tại), SerialBatchCreation (ghi lại gói lô được dựng), lô thu hồi / chưa duyệt xuất
xưởng, HSD của lô, msgprint. Kiểm thêm dòng
sau khi chia đúng là dòng mà ERPNext on_submit KHÔNG dựng gói lô từ ô batch_no nữa (điều kiện chép nguyên văn).

Chạy: python3 scripts/test-poslo.py   (verify.sh gọi sẵn)
"""

import importlib.util
import os
import sys
import types
from collections import OrderedDict
from datetime import date, datetime

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class _dict(dict):
    __getattr__ = dict.get

    def __setattr__(self, k, v):
        self[k] = v


frappe = types.ModuleType("frappe")
frappe._dict = _dict
fu = types.ModuleType("frappe.utils")
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.cint = lambda v: int(float(v or 0))
fu.getdate = lambda d: d if isinstance(d, date) else datetime.strptime(str(d)[:10], "%Y-%m-%d").date()
frappe.utils = fu
frappe._ = lambda s: s
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu

TON = {}          # (mã, kho) → OrderedDict {lô: số còn} lúc ghi sổ — đã xếp HSD gần trước
TON_NAY = {}      # (mã, kho) → số còn hiện tại (hỏi không kèm ngày giờ); không có thì như lúc ghi sổ
GOI_TON = []      # các lần hỏi số còn
GOI = []          # các gói lô đã dựng
THU_HOI, CHUA_DUYET = set(), set()
HSD = {"SEN-A": date(2027, 3, 1), "SEN-B": date(2027, 4, 5)}
HOI_LO = []       # các lần đọc Batch (HSD cho lời báo)
MSG = []          # msgprint


def get_available_batches(kwargs):
    GOI_TON.append(dict(kwargs))
    k = (kwargs["item_code"], kwargs["warehouse"])
    if not kwargs.get("posting_date") and k in TON_NAY:
        return OrderedDict(TON_NAY[k])
    return OrderedDict(TON.get(k, {}))


def get_all(dt, filters=None, fields=None):
    assert dt == "Batch" and fields == ["name", "expiry_date"], (dt, fields)
    HOI_LO.append(list(filters["name"][1]))
    return [_dict(name=b, expiry_date=HSD.get(b)) for b in filters["name"][1]]


frappe.get_all = get_all
frappe.msgprint = lambda msg, title=None, indicator=None: MSG.append(_dict(msg=msg, title=title, indicator=indicator))


class SerialBatchCreation:
    def __init__(self, args):
        self.args = dict(args)

    def make_serial_and_batch_bundle(self):
        GOI.append(self.args)
        return _dict(name=f"SABB-{len(GOI)}")


def mod(ten, **k):
    m = types.ModuleType(ten)
    m.__dict__.update(k)
    sys.modules[ten] = m
    return m


for g in ("erpnext", "erpnext.stock", "erpnext.stock.doctype", "erpnext.stock.doctype.batch", "sx", "sx.api"):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m
mod("erpnext.stock.doctype.batch.batch", get_available_batches=get_available_batches)
mod("erpnext.stock.serial_batch_bundle", SerialBatchCreation=SerialBatchCreation)
mod("erpnext.stock.utils", get_combine_datetime=lambda d, t: f"{d} {t}")
mod("sx.api.thuhoi", lo_dang_thu_hoi=lambda ds: {b: _dict(name=b) for b in ds if b in THU_HOI})
mod("sx.api.xuatxuong", lo_chua_duyet=lambda ds: {b: _dict(name=b) for b in ds if b in CHUA_DUYET})
mod("sx.api.kiemke", so_vn=lambda x: ("%g" % x).replace(".", ","))

sp = importlib.util.spec_from_file_location("sx.api.pos_lo", "sx/api/pos_lo.py")
PL = importlib.util.module_from_spec(sp)
sys.modules["sx.api.pos_lo"] = PL
sp.loader.exec_module(PL)

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct and not dk else ''}")


def dong(name, item="TP-SEN", lo="SEN-A", qty=1, kho="CH Ba", **k):
    return _dict(dict(name=name, idx=int(name[1:]), item_code=item, batch_no=lo, qty=qty, stock_qty=k.pop("stock_qty", qty),
                      conversion_factor=k.pop("cf", 1), warehouse=kho, use_serial_batch_fields=1,
                      serial_and_batch_bundle=None, **k))


def phieu(*rows, **k):
    d = dict(doctype="POS Invoice", name="POS-1", company="RVHG", posting_date="2026-10-22", posting_time="10:00:00",
             is_return=0, items=list(rows), flags=_dict())
    d.update(k)
    return _dict(d)


def lam(*rows, **k):
    GOI.clear()
    GOI_TON.clear()
    d = phieu(*rows, **k)
    PL.chia_lo(d)
    return d


def hd(*rows, **k):
    """Hoá đơn bán trừ kho trên Desk."""
    return lam(*rows, **dict(dict(doctype="Sales Invoice", name="ACC-SINV-1", update_stock=1), **k))


def erpnext_dung_o_lo(row):
    """erpnext/controllers/stock_controller.py (16.15.1) make_bundle_using_old_serial_batch_fields — dòng nào còn bị
    dựng gói lô từ ô batch_no / serial_no lúc on_submit (chép nguyên điều kiện)."""
    if not row.serial_no and not row.batch_no and not row.get("rejected_serial_no"):
        return False
    if not row.use_serial_batch_fields and (row.serial_no or row.batch_no or row.get("rejected_serial_no")):
        row.use_serial_batch_fields = 1
    return bool(row.use_serial_batch_fields and (not row.serial_and_batch_bundle
                                                 and not row.get("rejected_serial_and_batch_bundle")))


print("-- chia (hàm thuần) --")
kiem("lấy theo đúng thứ tự đưa vào cho tới đủ", PL.chia(6, [("A", 3), ("B", 5)]) == {"A": 3, "B": 3})
kiem("lô đầu đủ thì chỉ lô đầu", PL.chia(2, [("A", 3), ("B", 5)]) == {"A": 2})
kiem("bỏ lô số còn ≤ 0", PL.chia(4, [("A", 0), ("X", -2), ("B", 5)]) == {"B": 4})
kiem("cộng lại không đủ → None (không chia nửa vời)", PL.chia(9, [("A", 3), ("B", 5)]) is None)
kiem("một lô xuất hiện hai lần thì cộng dồn", PL.chia(4, [("A", 1), ("A", 2), ("B", 5)]) == {"A": 3, "B": 1})

print("\n-- phiếu POS: dòng bán quá số còn của lô đang gắn --")
TON[("TP-SEN", "CH Ba")] = OrderedDict([("SEN-A", 3), ("SEN-B", 5)])
r = dong("r1", lo="SEN-A", qty=6)
d = lam(r)
kiem("bán 6 mà lô đang gắn (SEN-A) còn 3, lô kia còn 5 → MỘT gói lô hai lô: SEN-A 3 + SEN-B 3",
     len(GOI) == 1 and GOI[0]["batches"] == {"SEN-A": 3, "SEN-B": 3} and GOI[0]["qty"] == 6, GOI)
kiem("… gói lô xuất kho, gắn đúng phiếu / dòng / kho / ngày giờ ghi phiếu, NHÁP (phiếu gửi thì gửi theo)",
     GOI[0]["type_of_transaction"] == "Outward" and GOI[0]["voucher_type"] == "POS Invoice"
     and GOI[0]["voucher_no"] == "POS-1" and GOI[0]["voucher_detail_no"] == "r1" and GOI[0]["warehouse"] == "CH Ba"
     and GOI[0]["item_code"] == "TP-SEN" and GOI[0]["company"] == "RVHG"
     and GOI[0]["posting_datetime"] == "2026-10-22 10:00:00" and GOI[0]["do_not_submit"], GOI[0])
kiem("… dòng mang gói lô, bỏ ô lô (dòng, giá, số lượng không đổi)", r.serial_and_batch_bundle == "SABB-1"
     and r.batch_no is None and r.use_serial_batch_fields == 0 and r.qty == 6, r)
kiem("… ERPNext on_submit KHÔNG dựng thêm gói một lô từ ô batch_no cho dòng đó", not erpnext_dung_o_lo(r))
kiem("số còn hỏi đúng cách ERPNext tự chọn lô: theo HSD gần trước, tại thời điểm ghi phiếu",
     GOI_TON[0]["based_on"] == "Expiry" and GOI_TON[0]["posting_date"] == "2026-10-22"
     and GOI_TON[0]["posting_time"] == "10:00:00" and GOI_TON[0]["company"] == "RVHG", GOI_TON)

r = dong("r1", lo="SEN-A", qty=3)
lam(r)
kiem("lô đang gắn đủ → để nguyên (ERPNext tự dựng gói một lô như cũ)", not GOI and r.batch_no == "SEN-A"
     and r.serial_and_batch_bundle is None and r.use_serial_batch_fields == 1 and erpnext_dung_o_lo(r))

r = dong("r1", lo="SEN-B", qty=6)
lam(r)
kiem("lô đang gắn lấy TRƯỚC (thu ngân / ERPNext đã chọn), phần thiếu theo HSD gần trước: SEN-B 5 + SEN-A 1",
     list(GOI[0]["batches"].items()) == [("SEN-B", 5), ("SEN-A", 1)], GOI)

r1, r2 = dong("r1", lo="SEN-A", qty=2), dong("r2", lo="SEN-A", qty=4)
lam(r1, r2)
kiem("hai dòng cùng mã: dòng sau trừ phần dòng trước đã lấy (SEN-A còn 1) → SEN-A 1 + SEN-B 3",
     r1.batch_no == "SEN-A" and r1.serial_and_batch_bundle is None and len(GOI) == 1
     and GOI[0]["batches"] == {"SEN-A": 1, "SEN-B": 3} and GOI[0]["voucher_detail_no"] == "r2", GOI)
kiem("… số còn của một (mã, kho) chỉ hỏi một lần cho cả phiếu", len(GOI_TON) == 1, GOI_TON)

r1, r2 = dong("r1", lo="SEN-A", qty=5), dong("r2", lo="SEN-A", qty=3)
lam(r1, r2)
kiem("dòng trước đã chia sang lô khác (SEN-A 3 + SEN-B 2) → dòng sau lấy phần còn lại của SEN-B (3)",
     [g["batches"] for g in GOI] == [{"SEN-A": 3, "SEN-B": 2}, {"SEN-B": 3}], GOI)

r = dong("r1", lo="SEN-A", qty=9)
lam(r)
kiem("các lô cộng lại vẫn không đủ (8 < 9) → để nguyên, ERPNext báo như cũ", not GOI and r.batch_no == "SEN-A"
     and r.serial_and_batch_bundle is None)

TON[("TP-SEN", "CH Ba")] = OrderedDict([("SEN-A", 3), ("SEN-X", 10), ("SEN-Y", 4), ("SEN-B", 5)])
THU_HOI.add("SEN-X")
CHUA_DUYET.add("SEN-Y")
r = dong("r1", lo="SEN-A", qty=8)
lam(r)
kiem("lô đang thu hồi / chưa duyệt xuất xưởng xếp sau cùng dù HSD gần hơn: SEN-A 3 + SEN-B 5",
     GOI[0]["batches"] == {"SEN-A": 3, "SEN-B": 5}, GOI)
r = dong("r1", lo="SEN-A", qty=12)
lam(r)
kiem("… lô bán được không đủ mới đụng tới lô bị khoá (để chốt thu hồi / BM.08.04 báo đúng lý do)",
     list(GOI[0]["batches"].items()) == [("SEN-A", 3), ("SEN-B", 5), ("SEN-X", 4)], GOI)
r = dong("r1", lo="SEN-X", qty=12)
lam(r)
kiem("… lô đang gắn bị khoá cũng xuống cuối", list(GOI[0]["batches"].items())[:2] == [("SEN-A", 3), ("SEN-B", 5)], GOI)
THU_HOI.clear()
CHUA_DUYET.clear()

TON[("TP-SEN", "CH Ba")] = OrderedDict([("SEN-A", 3), ("SEN-B", 5)])
r = dong("r1", lo="SEN-HET", qty=4)
lam(r)
kiem("lô đang gắn không còn trong số còn (hết hạn / hết hàng) → lấy các lô khác theo HSD: SEN-A 3 + SEN-B 1",
     GOI[0]["batches"] == {"SEN-A": 3, "SEN-B": 1}, GOI)

TON[("TP-SEN", "CH Ba")] = OrderedDict([("SEN-A", 5), ("SEN-B", 10)])
r = dong("r1", lo="SEN-A", qty=1, stock_qty=12, cf=12, uom="Thùng")
lam(r)
kiem("bán theo thùng: tính theo số đơn vị kho (1 thùng = 12 hộp) → SEN-A 5 + SEN-B 7, gói lô 12",
     GOI[0]["batches"] == {"SEN-A": 5, "SEN-B": 7} and GOI[0]["qty"] == 12 and r.qty == 1, GOI)
r = dong("r1", lo="SEN-A", qty=1, stock_qty=0, cf=12)
lam(r)
kiem("… dòng chưa có số đơn vị kho thì lấy số lượng × hệ số", GOI and GOI[0]["qty"] == 12, GOI)
r = dong("r1", lo="SEN-A", qty=7, stock_qty=0, cf=None)
lam(r)
kiem("… thiếu cả hệ số thì hệ số 1: bán 7 → SEN-A 5 + SEN-B 2", GOI and GOI[0]["batches"] == {"SEN-A": 5, "SEN-B": 2}, GOI)

TON[("BOT-DX", "CH Ba")] = OrderedDict([("BOT-A", 0.3), ("BOT-B", 0.5)])


def gan(a, b):
    return a.keys() == b.keys() and all(abs(a[x] - b[x]) < 1e-6 for x in a)


r = dong("r1", item="BOT-DX", lo="BOT-A", qty=0.7)
lam(r)
kiem("bán lẻ theo kg: 0,7 kg mà lô đang gắn còn 0,3 → BOT-A 0,3 + BOT-B 0,4 (không làm tròn mất phần lẻ)",
     GOI and gan(GOI[0]["batches"], {"BOT-A": 0.3, "BOT-B": 0.4}), GOI)
r = dong("r1", item="BOT-DX", lo="BOT-A", qty=0.4)
lam(r)
kiem("… dòng dưới 1 kg cũng chia: 0,4 → BOT-A 0,3 + BOT-B 0,1", GOI and gan(GOI[0]["batches"], {"BOT-A": 0.3, "BOT-B": 0.1}),
     GOI)
r = dong("r1", item="BOT-DX", lo="BOT-A", qty=0.9)
lam(r)
kiem("… các lô cộng lại 0,8 < 0,9 — thiếu 0,1 vẫn là thiếu → để nguyên", not GOI and r.batch_no == "BOT-A", GOI)

TON[("TP-SEN", "CH Le")] = OrderedDict([("SEN-A", 9)])
r1, r2 = dong("r1", lo="SEN-A", qty=6, kho="CH Ba"), dong("r2", lo="SEN-A", qty=6, kho="CH Le")
lam(r1, r2)
kiem("kho khác tính số còn riêng: dòng ở CH Le (SEN-A còn 9) để nguyên", len(GOI) == 1
     and GOI[0]["voucher_detail_no"] == "r1" and r2.batch_no == "SEN-A" and len(GOI_TON) == 2, GOI)

r = dong("r1", lo="SEN-A", qty=12)
lam(r, is_return=1)
kiem("phiếu trả hàng: không xét", not GOI and not GOI_TON and r.batch_no == "SEN-A")
r = dong("r1", lo="SEN-A", qty=12)
r.serial_and_batch_bundle = "SABB-CO"
lam(r)
kiem("dòng đã có gói lô (thu ngân chọn nhiều lô): không đụng", not GOI and r.serial_and_batch_bundle == "SABB-CO")
lam(dong("r1", lo=None, qty=12), dong("r2", qty=0), dong("r3", kho=None, qty=40))
kiem("dòng không lô / số lượng 0 / không kho: bỏ qua, không hỏi số còn", not GOI and not GOI_TON)

print("\n-- D222: hoá đơn bán trừ kho / phiếu giao --")
TON[("TP-SEN", "CH Ba")] = OrderedDict([("SEN-A", 3), ("SEN-B", 5)])
r = dong("r1", lo="SEN-A", qty=6)
d = hd(r)
kiem("hoá đơn bán trừ kho: bán 6 mà lô đang chọn còn 3 → một gói lô SEN-A 3 + SEN-B 3, gắn đúng hoá đơn / dòng",
     len(GOI) == 1 and GOI[0]["batches"] == {"SEN-A": 3, "SEN-B": 3} and GOI[0]["voucher_type"] == "Sales Invoice"
     and GOI[0]["voucher_no"] == "ACC-SINV-1" and GOI[0]["voucher_detail_no"] == "r1" and r.batch_no is None
     and r.serial_and_batch_bundle == "SABB-1", GOI)
kiem("… ERPNext (Sales Invoice on_submit, trừ kho) không dựng thêm gói một lô cho dòng đó", not erpnext_dung_o_lo(r))
kiem("… nhớ dòng đã chia để gửi xong báo lại (dòng không có tên hàng thì lấy mã)",
     [(x.idx, x.ten, x.lo, x.con, x.can, x.phan) for x in d.flags.sx_chia_lo]
     == [(1, "TP-SEN", "SEN-A", 3, 6, {"SEN-A": 3, "SEN-B": 3})], d.flags)
r = dong("r1", lo="SEN-A", qty=3)
d = hd(r)
kiem("… lô đang chọn đủ: để nguyên, không nhớ gì", not GOI and r.batch_no == "SEN-A" and not d.flags.sx_chia_lo, d.flags)
r = dong("r1", lo="SEN-A", qty=6)
lam(r, doctype="Delivery Note", name="MAT-DN-1")
kiem("phiếu giao cũng chia", GOI and GOI[0]["voucher_type"] == "Delivery Note"
     and GOI[0]["batches"] == {"SEN-A": 3, "SEN-B": 3}, GOI)
r = dong("r1", lo="SEN-A", qty=6)
hd(r, update_stock=0)
kiem("hoá đơn không trừ kho: không xét (không hỏi số còn, không dựng gói lô)", not GOI and not GOI_TON
     and r.batch_no == "SEN-A")
r = dong("r1", lo="SEN-A", qty=6)
hd(r, is_consolidated=1)
kiem("hoá đơn gộp từ POS lúc đóng ca: không xét (lô đã có từ phiếu POS / D198; phiếu POS đang gộp còn tính giữ chỗ)",
     not GOI and not GOI_TON and r.batch_no == "SEN-A")
r = dong("r1", lo="SEN-A", qty=6)
hd(r, is_return=1)
kiem("hoá đơn trả hàng: không xét", not GOI and not GOI_TON)
r = dong("r1", lo="SEN-A", qty=6)
lam(r, doctype="Delivery Note", is_return=1)
kiem("phiếu giao trả hàng: không xét", not GOI and not GOI_TON)

TON[("TP-SEN", "CH Ba")] = OrderedDict([("SEN-A", 3), ("SEN-X", 10), ("SEN-B", 5)])
THU_HOI.add("SEN-X")
r = dong("r1", lo="SEN-X", qty=12)
hd(r)
kiem("hoá đơn: lô người lập chọn đang thu hồi vẫn lấy TRƯỚC — chốt thu hồi chặn đúng lý do, không lặng lẽ đổi lô của "
     "thùng hàng đã giao", list(GOI[0]["batches"].items()) == [("SEN-X", 10), ("SEN-A", 2)], GOI)
r = dong("r1", lo="SEN-A", qty=12)
hd(r)
kiem("… lô khác đang thu hồi vẫn xếp sau cùng: SEN-A 3 + SEN-B 5 + SEN-X 4",
     list(GOI[0]["batches"].items()) == [("SEN-A", 3), ("SEN-B", 5), ("SEN-X", 4)], GOI)
r = dong("r1", lo="SEN-X", qty=12)
lam(r)
kiem("… phiếu POS: lô đang gắn bị khoá xuống cuối (ERPNext tự gắn, thu ngân không chọn)",
     list(GOI[0]["batches"].items())[:2] == [("SEN-A", 3), ("SEN-B", 5)], GOI)
THU_HOI.clear()

TON[("TP-SEN", "CH Ba")] = OrderedDict([("SEN-A", 5), ("SEN-D", 3), ("SEN-C", 4)])                   # lúc ghi sổ
TON_NAY[("TP-SEN", "CH Ba")] = OrderedDict([("SEN-A", 2), ("SEN-B", 10), ("SEN-C", 4)])              # hiện tại
r = dong("r1", lo="SEN-A", qty=5)
hd(r, set_posting_time=1, posting_date="2026-10-21")
kiem("hoá đơn ghi lùi ngày: số còn lấy nhỏ hơn giữa lúc ghi sổ và hiện tại — SEN-A lúc đó 5 nay 2, SEN-D nay hết, "
     "SEN-B nhập sau ngày đó → SEN-A 2 + SEN-C 3", GOI and list(GOI[0]["batches"].items()) == [("SEN-A", 2), ("SEN-C", 3)],
     GOI)
kiem("… hỏi lúc ghi sổ (kèm ngày giờ) rồi hiện tại (không kèm)", len(GOI_TON) == 2
     and GOI_TON[0]["posting_date"] == "2026-10-21" and not GOI_TON[1].get("posting_date")
     and GOI_TON[1]["based_on"] == "Expiry" and GOI_TON[1]["company"] == "RVHG", GOI_TON)
r = dong("r1", lo="SEN-A", qty=5)
hd(r)
kiem("… không đặt tay ngày giờ ghi sổ: chỉ hỏi lúc ghi sổ (SEN-A 5 đủ → để nguyên)", not GOI and len(GOI_TON) == 1
     and r.batch_no == "SEN-A", GOI_TON)
TON_NAY.clear()

print("\n-- D222: gửi xong báo lại --")
TON[("TP-SEN", "CH Ba")] = OrderedDict([("SEN-A", 3), ("SEN-B", 5), ("SEN-C", 4)])
r1 = dong("r1", lo="SEN-A", qty=6, item_name="Bánh đậu xanh sen")
r2 = dong("r2", lo="SEN-HET", qty=3, item_name="Bánh đậu xanh sen")
d = hd(r1, r2)
MSG.clear()
HOI_LO.clear()
PL.bao_chia(d)
m = MSG[0].msg if MSG else ""
kiem("báo một lần, màu cam, có tiêu đề", len(MSG) == 1 and MSG[0].indicator == "orange" and MSG[0].title, MSG)
kiem("… từng dòng: số dòng, tên hàng, số bán, lô đang chọn còn bao nhiêu, các lô đã ghi kèm HSD",
     "• Dòng 1 · Bánh đậu xanh sen: bán 6, lô SEN-A chỉ còn 3 → ghi SEN-A 3 (HSD 01/03/2027) + SEN-B 3 (HSD 05/04/2027)"
     in m, m)
kiem("… lô đang chọn không còn hàng bán được; lô không có HSD thì không ghi HSD",
     "• Dòng 2 · Bánh đậu xanh sen: bán 3, lô SEN-HET không còn hàng bán được → ghi SEN-B 2 (HSD 05/04/2027) + SEN-C 1"
     in m, m)
kiem("… nhắc đối chiếu thùng hàng đã giao", "Đối chiếu với lô trên thùng hàng đã giao" in m, m)
kiem("… đọc HSD một lần, đúng các lô đã ghi", HOI_LO == [["SEN-A", "SEN-B", "SEN-C"]], HOI_LO)
MSG.clear()
HOI_LO.clear()
PL.bao_chia(phieu(doctype="Sales Invoice"))
kiem("không dòng nào phải chia → không báo, không đọc gì", not MSG and not HOI_LO, MSG)

print("\n-- dây nối --")
ns = {}
exec(open("sx/hooks.py", encoding="utf-8").read(), ns)
de = ns["doc_events"]
kiem("hook before_submit của POS Invoice: chia lô ĐỨNG ĐẦU, rồi mới chốt thu hồi / xuất xưởng (xét đúng các lô sẽ ghi)",
     de["POS Invoice"]["before_submit"] == ["sx.api.pos_lo.chia_lo", "sx.api.thuhoi.kiem_xuat",
                                           "sx.api.xuatxuong.kiem_ban"])
kiem("… phiếu POS gửi xong không báo (thu ngân đang bán)", "sx.api.pos_lo.bao_chia" not in de["POS Invoice"]["on_submit"])
for dt in ("Sales Invoice", "Delivery Note"):
    ev = de[dt]
    kiem(f"{dt}: chia lô sau tạm tắt lô (D198) + chốt thiếu lô (W06), trước chốt thu hồi / xuất xưởng",
         ev["before_submit"][:5] == ["sx.api.lo_cu.tam_tat_lo", "sx.api.banhang.kiem_lo_ban", "sx.api.pos_lo.chia_lo",
                                     "sx.api.thuhoi.kiem_xuat", "sx.api.xuatxuong.kiem_ban"], ev["before_submit"])
    kiem(f"… {dt} gửi xong báo lại: sau các chốt on_submit, trước bật lại lô (D198 đứng cuối)",
         ev["on_submit"] == ["sx.api.thuhoi.kiem_xuat", "sx.api.xuatxuong.kiem_ban", "sx.api.pos_lo.bao_chia",
                             "sx.api.lo_cu.bat_lai_lo"], ev["on_submit"])

print()
if hong:
    print(f"POSLO-HỎNG ({hong})")
    sys.exit(1)
print("POSLO-OK")
