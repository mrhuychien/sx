"""D120 — tốc độ tải: số truy vấn KHÔNG được tăng theo số dòng dữ liệu.

Chậm kiểu N+1 không hiện ra khi thử với 3 lô / 5 mã; nó hiện ra ở xưởng thật sau
ba tháng chạy, khi lưu đồ có 90 lô và mỗi lô 15 truy vấn. Test này đếm truy vấn của
các hàm nóng với dữ liệu NHỎ và LỚN — hai con số phải bằng nhau — và kiểm số liệu
vẫn đúng như cách tính cũ.

Nạp sx/utils.py + sx/api/tang1.py THẬT; frappe giả có đếm truy vấn.
Chạy: python3 scripts/test-tocdo.py   (verify.sh gọi sẵn)
"""

import importlib.util
import os
import sys
import types
from datetime import date, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

DEM = {"n": 0}
BANG = {}
TON = {}            # (batch, kho) -> qty
VAI = {"SX Ghi So"}


class _dict(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


D = _dict


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, y = v
            if op == "in" and x not in y:
                return False
            if op == ">=" and not (x and x >= y):
                return False
        elif x != v:
            return False
    return True


def get_all(dt, filters=None, fields=None, pluck=None, or_filters=None, **k):
    DEM["n"] += 1
    ra = [D(h) for h in BANG.get(dt, []) if _khop(h, filters)]
    return [h.get(pluck) for h in ra] if pluck else ra


def get_value(dt, f, field=None, **k):
    DEM["n"] += 1
    h = next(iter([D(x) for x in BANG.get(dt, []) if _khop(x, f)]), None) if isinstance(f, dict) \
        else next((D(x) for x in BANG.get(dt, []) if x.get("name") == f), None)
    return h.get(field) if h else None


def exists(dt, f=None):
    DEM["n"] += 1
    return any(x.get("name") == f for x in BANG.get(dt, []))


def sql(q, a=None, as_dict=False):
    DEM["n"] += 1
    assert "Stock Ledger Entry" in q
    return [D(b=b, w=w, q=v) for (b, w), v in TON.items() if b in a["b"]]


class Doc(D):
    pass


BOM_DOC = {"BOM-BN": types.SimpleNamespace(quantity=78, items=[D(item_code="DAU-X", stock_qty=100)])}
ITEM = {"DAU-X": D(custom_sx_nhom="NVL", is_stock_item=1, item_name="Đỗ xanh"),
        "BN-X": D(custom_sx_nhom="BTP-Bot", is_stock_item=1)}

frappe = types.ModuleType("frappe")
frappe._dict = _dict
frappe.local = types.SimpleNamespace()
frappe.throw = lambda m, e=None, **k: (_ for _ in ()).throw(Exception(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Exception,), {})
frappe.session = types.SimpleNamespace(user="qc@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_cached_doc = lambda dt, n=None: (D(kho_btp="BTP", kho_xuong="XUONG")
                                            if dt == "SX Settings" else BOM_DOC[n])
frappe.get_cached_value = lambda dt, n, f=None: (ITEM.get(n) or {}).get(f)
frappe.db = types.SimpleNamespace(get_value=get_value, exists=exists, sql=sql)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.cint = lambda v: int(float(v or 0))
fu.getdate = lambda x=None: x if isinstance(x, date) else date.fromisoformat(str(x)[:10])
fu.nowdate = lambda: "2026-10-06"
fu.add_days = lambda d, n: fu.getdate(d) + timedelta(days=n)
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.api", "sx.config"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m
mfg = types.ModuleType("sx.api.mfg")
for t in ("cancel_doc", "tao_batch", "tao_se_chuyen_kho", "tao_se_manufacture", "tao_se_repack", "tao_wo"):
    setattr(mfg, t, lambda *a, **k: None)
sys.modules["sx.api.mfg"] = mfg


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


nap("sx.config.roles", "sx/config/roles.py")
U = nap("sx.utils", "sx/utils.py")
T = nap("sx.api.tang1", "sx/api/tang1.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


def du_lieu(n):
    """n lô R của đỗ xanh: mỗi lô xuất 100 kg, đã rang 60 kg; ủ / vỡ / bột còn tồn."""
    BANG.clear(); TON.clear(); frappe.local.sx_nho = {}
    BANG["Item"] = [D(name="BN-X", custom_sx_nhom="BTP-Bot", disabled=0),
                    D(name="DAU-X ủ"), D(name="DAU-X vỡ")]
    BANG["BOM"] = [D(name="BOM-BN", item="BN-X", is_active=1, is_default=1, docstatus=1)]
    BANG["SX Xuat Dau"] = []
    BANG["Stock Entry"] = []
    BANG["Stock Entry Detail"] = []
    for i in range(n):
        lo = f"R-{i:03d}"
        BANG["SX Xuat Dau"].append(D(
            name=f"XD-{i}", docstatus=1, ngay_xuat=date(2026, 10, 1), ngay_rang=date(2026, 10, 1),
            lo_rang=lo, loai_dau="DAU-X", dau_kg=100, trang_thai_bot=0, se_xuat_kho=f"SE-X{i}"))
        BANG["Stock Entry"].append(D(name=f"SE-R{i}", docstatus=1, custom_lo_rang=lo,
                                     custom_cong_doan="rang"))
        BANG["Stock Entry Detail"].append(D(parent=f"SE-R{i}", item_code="DAU-X", qty=60,
                                            is_finished_item=0))
        TON[(f"{lo}-U", "XUONG")] = 10 + i
        TON[(f"{lo}-V", "XUONG")] = 5
        TON[(lo, "BTP")] = 20
        TON[(lo, "XUONG")] = 999        # bột nền ở NHẦM kho — không được tính


print("-- lưu đồ tầng 1: số truy vấn không tăng theo số lô --")
du_lieu(3)
DEM["n"] = 0
nho = T.luu_do_lo("2026-10-06")
n_nho = DEM["n"]
du_lieu(60)
DEM["n"] = 0
lon = T.luu_do_lo("2026-10-06")
n_lon = DEM["n"]
kiem("3 lô và 60 lô cùng số truy vấn", n_nho == n_lon, f"{n_nho} vs {n_lon}")
kiem("… và ít (≤ 15)", n_lon <= 15, n_lon)
lo = {x["lo_rang"]: {c["chang"]: c["ton"] for c in x["chang"]} for x in lon["lo"]}
kiem("đủ 60 lô", len(lo) == 60)
kiem("đỗ còn ở xưởng = xuất − đã rang (100 − 60)", lo["R-007"]["dau"] == 40, lo["R-007"])
kiem("tồn đỗ ủ theo đúng lô", lo["R-007"]["u"] == 17)
kiem("tồn bột nền chỉ tính ở Kho BTP", lo["R-007"]["bot"] == 20)
kiem("tỉ lệ gợi ý nghiền theo BOM (78/100)",
     next(c["ty_le"] for c in lon["lo"][0]["cong_doan"] if c["ma"] == "nghien") == 0.78)

print("\n-- bộ nhớ request --")
du_lieu(1)
DEM["n"] = 0
U.get_bom_active("BN-X"); U.get_bom_active("BN-X"); U.get_bom_active("BN-X")
kiem("get_bom_active cùng mã 3 lần → 1 truy vấn", DEM["n"] == 1, DEM["n"])
DEM["n"] = 0
U.nap_bom(["BN-X", "KHONG-CO", "KHAC"])
U.get_bom_active("KHONG-CO"); U.get_bom_active("KHAC")
kiem("nạp BOM cả danh sách → 1 truy vấn, mã không có BOM cũng nhớ (None)", DEM["n"] == 1, DEM["n"])
U.xoa_nho()
DEM["n"] = 0
U.get_bom_active("BN-X")
kiem("hook xoá nhớ (BOM / Item đổi) → đọc lại", DEM["n"] == 1)
BANG["Item"].append(D(name="TP1", custom_sx_nhom="TP", disabled=0))
DEM["n"] = 0
a = U.items_tp(["name"]); a[0]["sua"] = 1
b2 = U.items_tp(["name"]); b2[0]["sua2"] = 1
b = U.items_tp(["name"])
kiem("items_tp gọi lại trong request → không truy vấn thêm", DEM["n"] == 1, DEM["n"])
kiem("… và trả bản SAO (nơi gọi sửa không làm bẩn bản nhớ)", not any("sua" in x or "sua2" in x for x in b))
DEM["n"] = 0
TON.clear()
BANG["Bin"] = [D(item_code=f"I{i}", warehouse="K", actual_qty=i) for i in range(50)]
t = U.ton_bin([f"I{i}" for i in range(50)], "K")
kiem("tồn Bin 50 mã → 1 truy vấn", DEM["n"] == 1 and t["I7"] == 7, DEM["n"])

frappe.local = None
kiem("không có frappe.local (test giả / script) → vẫn chạy, chỉ là không nhớ",
     U.nho("x") == {} and U.get_bom_active("BN-X") == "BOM-BN")

print()
if hong:
    print(f"TOCDO-HỎNG ({hong})")
    sys.exit(1)
print("TOCDO-OK")
