"""D132 (W06) — bán trừ kho thành phẩm phải chọn đúng lô (HSD).

ERPNext v16 TỰ CHỌN lô khi dòng bán bỏ trống — hoá đơn vẫn qua, nhưng lô trên sổ là
lô máy đoán. Hỏng ở đây là hỏng im lặng: truy xuất xuôi chỉ ra nhầm khách lúc thu hồi.

Nạp sx/api/banhang.py THẬT; frappe giả.
Chạy: python3 scripts/test-banlo.py   (verify.sh gọi sẵn)
"""

import importlib.util
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class Loi(Exception):
    pass


class D(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)


CO_LO = {"TP-SEN": 1, "TP-CU": 0, "BOT": 1}
SETTING = {}
MSG = []
frappe = types.ModuleType("frappe")
frappe.throw = lambda m, *a, **k: (_ for _ in ()).throw(Loi(str(m)))
frappe.msgprint = lambda m, *a, **k: MSG.append(str(m))
frappe.get_cached_value = lambda d, n, f=None: CO_LO.get(n) if f == "has_batch_no" else None
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: float(v or 0)
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.api"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m
ut = types.ModuleType("sx.utils")
ut.get_settings = lambda: D(SETTING)
ut.items_tp = lambda fields=None, **k: [D(name="TP-SEN"), D(name="TP-CU")]
sys.modules["sx.utils"] = ut
sp = importlib.util.spec_from_file_location("sx.api.banhang", "sx/api/banhang.py")
B = importlib.util.module_from_spec(sp)
sp.loader.exec_module(B)

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


def hd(*dong, dt="Sales Invoice", update_stock=1, is_return=0):
    return D(doctype=dt, update_stock=update_stock, is_return=is_return,
             items=[D(idx=i, item_name=x[0], **dict(zip(("item_code", "qty", "batch_no",
                                                          "serial_and_batch_bundle"), x)))
                    for i, x in enumerate(dong, 1)])


def thu(doc):
    MSG.clear()
    try:
        B.kiem_lo_ban(doc)
        return None
    except Loi as e:
        return str(e)


print("-- hoá đơn bán trừ kho --")
loi = thu(hd(("TP-SEN", 10, None, None), ("TP-SEN", 5, "SEN-HSD080727", None)))
kiem("dòng thành phẩm có lô mà chưa chọn lô → CHẶN", loi is not None)
kiem("… nói đúng dòng", loi and "Dòng 1" in loi and "Dòng 2" not in loi, loi)
kiem("chọn lô bằng ô Batch No → qua", thu(hd(("TP-SEN", 10, "SEN-HSD080727", None))) is None)
kiem("chọn lô bằng Serial and Batch Bundle → qua", thu(hd(("TP-SEN", 10, None, "SABB-1"))) is None)
kiem("hàng không phải thành phẩm (bột) → không xét", thu(hd(("BOT", 10, None, None))) is None)
kiem("hoá đơn KHÔNG trừ kho → không xét", thu(hd(("TP-SEN", 10, None, None), update_stock=0)) is None)
kiem("phiếu trả hàng → không xét", thu(hd(("TP-SEN", -10, None, None), is_return=1)) is None)
kiem("phiếu giao hàng (Delivery Note) cũng xét",
     thu(hd(("TP-SEN", 10, None, None), dt="Delivery Note", update_stock=0)) is not None)
loi = thu(hd(("TP-CU", 10, None, None)))
kiem("mã thành phẩm KHÔNG quản lý lô → không chặn (chặn là dừng bán)…", loi is None)
kiem("… nhưng CẢNH BÁO mất truy xuất xuôi", MSG and "TP-CU" in MSG[0], MSG)
SETTING["chan_ban_thieu_lo"] = 0
kiem("tắt trong SX Settings → không chặn", thu(hd(("TP-SEN", 10, None, None))) is None)
SETTING.clear()
kiem("site chưa migrate (chưa có ô) → mặc định BẬT", thu(hd(("TP-SEN", 10, None, None))) is not None)
hk = open("sx/hooks.py", encoding="utf-8").read()
import re  # noqa: E402

for dt_ in ("Sales Invoice", "Delivery Note"):
    k_ = re.search(r'"%s": \{(.*?)\}' % dt_, hk, re.S)
    kiem(f"móc kiem_lo_ban vào before_submit của {dt_}",
         k_ is not None and re.search(r'"before_submit": \[?[^\]]*"sx\.api\.banhang\.kiem_lo_ban"',
                                      k_.group(1)) is not None)

print()
if hong:
    print(f"BANLO-HỎNG ({hong})")
    sys.exit(1)
print("BANLO-OK")
