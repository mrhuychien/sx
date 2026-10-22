"""D221 — phiếu POS: dòng bán quá số còn của lô đang gắn → chia sang các lô khác (một gói lô nhiều lô).

Lỗi thật (22/10/2026): mã còn hai lô, bán một lần số lượng mà phải gộp hai lô mới đủ → POS báo lô âm. Màn POS của
ERPNext gắn mỗi dòng MỘT lô (chọn lúc số lượng còn là 1), tăng số lượng lô vẫn vậy; lúc thanh toán ERPNext dựng gói lô
một lô cho cả dòng → "Batch No … has negative stock".

Bài này nạp sx/api/pos_lo.py THẬT; phía ERPNext giả đúng phần hook gọi tới: get_available_batches (số còn từng lô, đã
xếp HSD gần trước), SerialBatchCreation (ghi lại gói lô được dựng), lô thu hồi / chưa duyệt xuất xưởng. Kiểm thêm dòng
sau khi chia đúng là dòng mà ERPNext on_submit KHÔNG dựng gói lô từ ô batch_no nữa (điều kiện chép nguyên văn).

Chạy: python3 scripts/test-poslo.py   (verify.sh gọi sẵn)
"""

import importlib.util
import os
import sys
import types
from collections import OrderedDict

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
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu

TON = {}          # (mã, kho) → OrderedDict {lô: số còn} — đã xếp HSD gần trước
GOI_TON = []      # các lần hỏi số còn
GOI = []          # các gói lô đã dựng
THU_HOI, CHUA_DUYET = set(), set()


def get_available_batches(kwargs):
    GOI_TON.append(dict(kwargs))
    return OrderedDict(TON.get((kwargs["item_code"], kwargs["warehouse"]), {}))


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
    return _dict(dict(name=name, idx=len(name), item_code=item, batch_no=lo, qty=qty, stock_qty=k.pop("stock_qty", qty),
                      conversion_factor=k.pop("cf", 1), warehouse=kho, use_serial_batch_fields=1,
                      serial_and_batch_bundle=None, **k))


def phieu(*rows, **k):
    d = dict(doctype="POS Invoice", name="POS-1", company="RVHG", posting_date="2026-10-22", posting_time="10:00:00",
             is_return=0, items=list(rows))
    d.update(k)
    return _dict(d)


def lam(*rows, **k):
    GOI.clear()
    GOI_TON.clear()
    d = phieu(*rows, **k)
    PL.chia_lo(d)
    return d


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

print("\n-- dây nối --")
H = open("sx/hooks.py", encoding="utf-8").read()
kiem("hook before_submit của POS Invoice: chia lô ĐỨNG ĐẦU, rồi mới chốt thu hồi / xuất xưởng (xét đúng các lô sẽ ghi)",
     '"POS Invoice": {"before_submit": ["sx.api.pos_lo.chia_lo", "sx.api.thuhoi.kiem_xuat", '
     '"sx.api.xuatxuong.kiem_ban"]' in H)

print()
if hong:
    print(f"POSLO-HỎNG ({hong})")
    sys.exit(1)
print("POSLO-OK")
