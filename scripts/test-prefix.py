"""D102 — prefix mã lô: có custom_batch_prefix thì dùng, KHÔNG có thì dùng mã hàng.

Trước D102 thiếu prefix là chặn cứng: thành phẩm mới tạo mà quên điền là thủ kho
không duyệt được phiếu nhập. Hỏng lại theo hai hướng: chặn lại (quay về lỗi cũ),
hoặc bỏ qua prefix đã điền (mã lô ngắn người ta cố ý đặt bị thay bằng mã dài).

Nạp sx/utils.py THẬT; frappe là giả.
Chạy: python3 scripts/test-prefix.py   (verify.sh gọi sẵn)
"""

import importlib.util
import os
import sys
import types
from datetime import date

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

PREFIX = {"TP-SEN": "SEN", "BOT-DX": "R", "TP-MOI": None, "TP-TRONG": "  "}
BATCH = set()


class Loi(Exception):
    pass


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw(Loi(str(m)))
frappe.__dict__["_"] = lambda s: s
frappe.db = types.SimpleNamespace(
    get_value=lambda dt, n, f=None, **k: PREFIX.get(n) if f == "custom_batch_prefix" else None,
    exists=lambda dt, x=None: (x in BATCH) if isinstance(x, str) else False)
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: float(v or 0)
fu.getdate = lambda x=None: x if isinstance(x, date) else date.fromisoformat(str(x)[:10])
fu.nowdate = lambda: "2026-09-29"
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
sp = importlib.util.spec_from_file_location("sx.utils", "sx/utils.py")
U = importlib.util.module_from_spec(sp)
sp.loader.exec_module(U)

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


D = date(2026, 9, 29)
kiem("có prefix → dùng prefix", U.sinh_ma_lo("TP-SEN", D) == "SEN-290926")
kiem("KHÔNG có prefix → dùng mã hàng, không chặn", U.sinh_ma_lo("TP-MOI", D) == "TP-MOI-290926")
kiem("prefix toàn khoảng trắng coi như chưa điền", U.prefix_lo("TP-TRONG") == "TP-TRONG")
BATCH.add("TP-MOI-290926")
kiem("trùng lô vẫn thêm đuôi -2", U.sinh_ma_lo("TP-MOI", D) == "TP-MOI-290926-2")
U.get_bot_from_dau = lambda d: ("BOT-DX", "BOM-1") if d == "DX" else (_ for _ in ()).throw(Loi("x"))
kiem("lô rang: prefix của bột nền", U.sinh_lo_rang("DX", D).startswith("R-290926"))
PREFIX["BOT-DX"] = None
kiem("lô rang: bột nền chưa có prefix → mã bột nền",
     U.sinh_lo_rang("DX", D).startswith("BOT-DX-290926"))
kiem("lô rang: không suy được bột nền → mã đỗ", U.sinh_lo_rang("DO-LA", D).startswith("DO-LA-290926"))

print("PREFIX-OK" if not hong else f"PREFIX: {hong} HỎNG")
sys.exit(1 if hong else 0)
