"""D102/D103 — prefix mã lô tự có, tự ngắn; mã hàng chưa bật lô không làm kẹt nhập kho.

Hỏng theo những hướng im lặng:
  · Quay về chặn khi thiếu prefix → thủ kho lại không duyệt được mã mới.
  · Bỏ qua prefix đã điền → mã lô ngắn người ta cố ý đặt bị thay.
  · Rút gọn không ổn định / trùng giữa hai mặt hàng → hai sản phẩm chung đầu mã lô,
    chép tay ra thẻ là nhầm lô.
  · Item tắt "Has Batch No" → ERPNext báo "The selected item cannot have Batch" và
    nhập kho kẹt; hoặc tệ hơn, bật lô cho Item đã có giao dịch (ERPNext cấm).

Nạp sx/utils.py và sx/api/mfg.py THẬT; frappe là giả.
Chạy: python3 scripts/test-prefix.py   (verify.sh gọi sẵn)
"""

import importlib.util
import os
import sys
import types
from datetime import date

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

ITEM = {}          # name -> {custom_batch_prefix, has_batch_no}
BATCH = {}         # name -> item
SLE = set()        # item có giao dịch kho
MSG = []


class Loi(Exception):
    pass


def lam_sach():
    ITEM.clear(); BATCH.clear(); SLE.clear(); MSG.clear()
    for ma, px, lo in (("TP-SEN", "SEN", 1), ("BOT-DX", "R", 1), ("TP-MOI", None, 1),
                       ("TP-TRONG", "  ", 1),
                       ("Bánh đậu xanh sen 300g", None, 1),
                       ("Bột đậu xanh sữa 300g", None, 1),
                       ("Chè đậu đen cốt dừa", None, 0), ("TP-CU", None, 0)):
        ITEM[ma] = {"custom_batch_prefix": px, "has_batch_no": lo}


def _exists(dt, f=None):
    if dt == "Batch":
        return f in BATCH
    if dt == "Item" and isinstance(f, dict):
        return any(v.get("custom_batch_prefix") == f["custom_batch_prefix"]
                   and k != f["name"][1] for k, v in ITEM.items())
    if dt == "Stock Ledger Entry":
        return f["item_code"] in SLE
    return False


def _get_value(dt, n, f=None, **k):
    if dt == "Item":
        return ITEM.get(n, {}).get(f)
    if dt == "Batch":
        return BATCH.get(n) if f == "item" else None
    return None


def _set_value(dt, n, f, v=None, **k):
    ITEM[n][f] = v


class Doc(dict):
    def __getattr__(self, k):
        if k == "flags":
            return types.SimpleNamespace()
        return self.get(k)

    def insert(self):
        if not ITEM[self["item"]]["has_batch_no"]:
            raise Loi("The selected item cannot have Batch")   # như ERPNext thật
        BATCH[self["batch_id"]] = self["item"]
        self["name"] = self["batch_id"]
        return self


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw(Loi(str(m)))
frappe.msgprint = lambda m, **k: MSG.append(m)
frappe.__dict__["_"] = lambda s: s
frappe.get_doc = lambda d: Doc(d)
frappe.get_cached_value = lambda dt, n, f: ITEM.get(n, {}).get(f)
frappe.clear_document_cache = lambda dt, n: None
frappe.db = types.SimpleNamespace(get_value=_get_value, exists=_exists, set_value=_set_value)
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: float(v or 0)
fu.getdate = lambda x=None: x if isinstance(x, date) else date.fromisoformat(str(x)[:10])
fu.nowdate = lambda: "2026-09-29"
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


U = nap("sx.utils", "sx/utils.py")
MFG = nap("sx.api.mfg", "sx/api/mfg.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


def thu(fn):
    try:
        return fn(), None
    except Loi as e:
        return None, str(e)


D = date(2026, 9, 29)

print("-- rút gọn mã hàng --")
kiem("mã đã ngắn, không dấu giữ nguyên", U.rut_gon_ma("TP-SEN") == "TP-SEN")
kiem("tên dài có dấu → chữ đầu + cụm số",
     U.rut_gon_ma("Bánh đậu xanh sen 300g") == "BDXS300G", U.rut_gon_ma("Bánh đậu xanh sen 300g"))
kiem("đ → D", U.rut_gon_ma("Chè đậu đen cốt dừa") == "CDDCD", U.rut_gon_ma("Chè đậu đen cốt dừa"))
kiem("một từ có dấu → bỏ dấu, viết hoa", U.rut_gon_ma("Lạc") == "LAC")
kiem("một từ rất dài → cắt ở giới hạn", U.rut_gon_ma("Bánhđậuxanhnướngsữa") == "BANHDAUXAN")
kiem("không bao giờ dài quá giới hạn",
     len(U.rut_gon_ma("Bột đậu xanh sữa dừa có đường không đường ít béo 1000g"))
     <= U.PREFIX_TOI_DA)

print("\n-- prefix mã lô --")
lam_sach()
kiem("có prefix → dùng prefix", U.sinh_ma_lo("TP-SEN", D) == "SEN-290926")
kiem("mã ngắn chưa có prefix → mã hàng", U.sinh_ma_lo("TP-MOI", D) == "TP-MOI-290926")
kiem("prefix toàn khoảng trắng coi như chưa điền", U.prefix_lo("TP-TRONG") == "TP-TRONG")
kiem("tên dài → mã lô ngắn", U.sinh_ma_lo("Bánh đậu xanh sen 300g", D) == "BDXS300G-290926")
kiem("prefix rút gọn được LƯU vào Item (lần sau y hệt, sửa được trên Desk)",
     ITEM["Bánh đậu xanh sen 300g"]["custom_batch_prefix"] == "BDXS300G")
ITEM["Bột đậu xanh sữa 300g"]["custom_batch_prefix"] = None
ITEM["Bánh đậu xanh sen 300g"]["custom_batch_prefix"] = "BDXS300G"
px = U.prefix_lo("Bột đậu xanh sữa 300g")
kiem("hai mặt hàng rút gọn TRÙNG nhau → mã sau thêm số, không chung đầu lô",
     px != "BDXS300G" and px.startswith("BDXS300") and len(px) <= U.PREFIX_TOI_DA, px)
BATCH["TP-MOI-290926"] = "TP-MOI"
kiem("trùng lô vẫn thêm đuôi -2", U.sinh_ma_lo("TP-MOI", D) == "TP-MOI-290926-2")
U.get_bot_from_dau = lambda d: ("BOT-DX", "BOM-1") if d == "DX" else (_ for _ in ()).throw(Loi("x"))
kiem("lô rang: prefix của bột nền", U.sinh_lo_rang("DX", D).startswith("R-290926"))
ITEM["BOT-DX"]["custom_batch_prefix"] = None
kiem("lô rang: bột nền chưa có prefix → mã bột nền",
     U.sinh_lo_rang("DX", D).startswith("BOT-DX-290926"))
ITEM["DO-LA"] = {"custom_batch_prefix": None}
kiem("lô rang: không suy được bột nền → mã đỗ", U.sinh_lo_rang("DO-LA", D).startswith("DO-LA-290926"))

print("\n-- Item chưa bật 'Has Batch No' --")
lam_sach()
lo, loi = thu(lambda: MFG.tao_batch("Chè đậu đen cốt dừa", "CDDCD-290926"))
kiem("chưa có giao dịch kho → tự bật lô, tạo lô được (hết lỗi 'cannot have Batch')",
     loi is None and lo == "CDDCD-290926" and ITEM["Chè đậu đen cốt dừa"]["has_batch_no"] == 1,
     loi or "")
SLE.add("TP-CU")
lo, loi = thu(lambda: MFG.tao_batch("TP-CU", "TP-CU-290926"))
kiem("ĐÃ có giao dịch → không bật (ERPNext cấm), nhập không lô, KHÔNG chặn",
     loi is None and lo is None and not ITEM["TP-CU"]["has_batch_no"], loi or "")
kiem("… và nói rõ ra là mất lô", MSG and "không quản lý theo lô" in MSG[-1])
kiem("mã đã có lô: không đụng gì", MFG.tao_batch("TP-SEN", "SEN-290926") == "SEN-290926"
     and ITEM["TP-SEN"]["has_batch_no"] == 1)

print("PREFIX-OK" if not hong else f"PREFIX: {hong} HỎNG")
sys.exit(1 if hong else 0)
