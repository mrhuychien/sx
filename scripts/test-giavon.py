"""D116 — mã nguyên liệu chưa có giá vốn (Vani…) làm chốt Ghi sổ văng lỗi ERPNext.

ERPNext báo "Valuation Rate for the Item Vani, is required…" bằng tiếng Anh, TỪNG MÃ
MỘT, giữa lúc đang sinh phiếu kho. Giờ:
  · kiểm TRƯỚC, liệt kê HẾT mã thiếu giá một lần, câu tiếng Việt chỉ cách sửa;
  · BTP làm ra trong cùng lần chốt không bị coi là thiếu giá;
  · quản lý khai giá ngay trên thẻ Chốt ngày (Item.valuation_rate) — chỉ cho mã đang
    THIẾU, giá ≤ 0 bị chặn, có comment lưu vết.

Nạp sx/api/mfg.py + sx/api/chot.py THẬT; frappe / ERPNext là giả.
Chạy: python3 scripts/test-giavon.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class Loi(Exception):
    pass


class _dict(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


D = _dict
ITEM = {
    "VANI": D(item_name="Vani", stock_uom="Kg", valuation_rate=0, is_stock_item=1,
              last_purchase_rate=0, standard_rate=850000, custom_sx_nhom="NVL"),
    "MAU": D(item_name="Màu", stock_uom="Kg", valuation_rate=0, is_stock_item=1,
             custom_sx_nhom="NVL"),
    "DUONG": D(item_name="Đường", stock_uom="Kg", valuation_rate=0, is_stock_item=1,
               custom_sx_nhom="NVL"),
    "DAU": D(item_name="Dầu", stock_uom="Kg", valuation_rate=42000, is_stock_item=1,
             custom_sx_nhom="NVL"),
    "MUOI": D(item_name="Muối", stock_uom="Kg", valuation_rate=0, is_stock_item=1,
              custom_sx_nhom="NVL"),
    "NUOC": D(item_name="Nước", is_stock_item=0, custom_sx_nhom="NVL"),
    "DUONG-HOAN": D(item_name="Đường hoán", stock_uom="Kg", valuation_rate=0,
                    is_stock_item=1, custom_sx_nhom="BTP-Phu"),
    "BOT-BANH": D(item_name="Bột bánh", is_stock_item=1, custom_sx_nhom="BTP-Banh"),
    "BOT-DAU": D(item_name="Bột đậu", stock_uom="Kg", is_stock_item=1, custom_sx_nhom="BTP-Bot-SP"),
    "BOT-NEN": D(item_name="Bột nền", stock_uom="Kg", is_stock_item=1, custom_sx_nhom="BTP-Bot"),
    "DX-U": D(item_name="Đỗ ủ", is_stock_item=1, custom_sx_nhom="BTP-Dau"),
    "DX-V": D(item_name="Đỗ vỡ", is_stock_item=1, custom_sx_nhom="BTP-Dau"),
    "DAU-XANH": D(item_name="Đỗ xanh", stock_uom="Kg", is_stock_item=1, custom_sx_nhom="NVL",
                  last_purchase_rate=31000),
    "BOT-MOI": D(item_name="Bột chưa làm bao giờ", stock_uom="Kg", is_stock_item=1,
                 custom_sx_nhom="BTP-Bot"),
}
BIN = {("DUONG", "NVL"): 18000}                 # có giá vốn đang chạy
SLE_GIA = {"MUOI"}                               # từng nhập có giá ở kho khác
GIA_MUA = {}                                     # Item Price buying
BOM = {
    "BOM-DH": types.SimpleNamespace(quantity=10, items=[D(item_code="DUONG", stock_qty=10),
                                    D(item_code="MAU", stock_qty=0.1)]),
    "BOM-BB": types.SimpleNamespace(quantity=100, items=[D(item_code="DUONG-HOAN", stock_qty=20),
                                     D(item_code="VANI", stock_qty=0.2),
                                     D(item_code="MAU", stock_qty=0.1),
                                     D(item_code="DAU", stock_qty=5),
                                     D(item_code="MUOI", stock_qty=1),
                                     D(item_code="NUOC", stock_qty=30)]),
}
BOM["BOM-BD"] = types.SimpleNamespace(quantity=50, items=[D(item_code="BOT-NEN", stock_qty=40),
                                                          D(item_code="DUONG-HOAN", stock_qty=10)])
BOM_CUA = {"DUONG-HOAN": "BOM-DH", "BOT-BANH": "BOM-BB", "BOT-DAU": "BOM-BD"}
# Rang → tách vỏ → nghiền: Repack, không BOM — giá theo phiếu gần nhất (số cân thật).
SED = [
    D(parent="SE-R", item_code="DAU-XANH", qty=100, is_finished_item=0, docstatus=1, s_warehouse="X"),
    D(parent="SE-R", item_code="DX-U", qty=120, is_finished_item=1, docstatus=1),
    D(parent="SE-T", item_code="DX-U", qty=120, is_finished_item=0, docstatus=1, s_warehouse="X"),
    D(parent="SE-T", item_code="DX-V", qty=90, is_finished_item=1, docstatus=1),
    D(parent="SE-N", item_code="DX-V", qty=90, is_finished_item=0, docstatus=1, s_warehouse="X"),
    D(parent="SE-N", item_code="BOT-NEN", qty=88, is_finished_item=1, docstatus=1),
]


def get_all(dt, filters=None, fields=None, pluck=None, limit=None, **k):
    if dt != "Stock Entry Detail":
        return []
    ra = []
    for h in SED:
        ok = True
        for kk, v in (filters or {}).items():
            if isinstance(v, tuple):
                ok = ok and bool(h.get(kk))
            elif h.get(kk) != v:
                ok = False
        if ok:
            ra.append(D(h))
    ra.reverse()                                      # order_by creation desc
    return ra[:limit] if limit else ra
COMMENT = []
VAI = {"SX Quan Ly"}


def get_value(dt, f, field=None, as_dict=False, **k):
    if dt == "Bin":
        if "warehouse" not in f:                      # kho bất kỳ có giá
            return next((g for (i, _k), g in BIN.items() if i == f["item_code"] and g > 0), None)
        return BIN.get((f["item_code"], f["warehouse"]))
    if dt == "Stock Ledger Entry":
        return 25000 if f["item_code"] in SLE_GIA and f.get("valuation_rate") == (">", 0) else None
    if dt == "Item Price":
        return GIA_MUA.get(f["item_code"])
    if dt == "Item":
        h = ITEM.get(f) or {}
        if isinstance(field, (list, tuple)):
            return D({x: h.get(x) for x in field}) if as_dict else tuple(h.get(x) for x in field)
        return h.get(field)
    return None


def exists(dt, f=None):
    if dt == "Stock Ledger Entry":
        if f.get("valuation_rate") == (">", 0):
            return f["item_code"] in SLE_GIA
        return f["item_code"] in SLE_GIA | {"MAU"}     # Màu: chỉ từng nhập giá 0
    if dt == "Item":
        return f in ITEM
    return False


def set_value(dt, n, k, v=None, **kw):
    ITEM[n][k] = v


class ItemDoc:
    def __init__(self, n):
        self.n = n

    def add_comment(self, loai, text):
        COMMENT.append((self.n, text))


frappe = types.ModuleType("frappe")
frappe._dict = _dict
frappe.throw = lambda m, e=None, title=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.session = types.SimpleNamespace(user="ql@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_cached_value = lambda dt, n, f=None: get_value(dt, n, f)
frappe.get_cached_doc = lambda dt, n: BOM[n]
frappe.get_all = get_all
frappe.get_doc = lambda dt, n=None: ItemDoc(n) if dt == "Item" else (NGAY2 if n == "SXN-2" else NGAY)
frappe.clear_document_cache = lambda *a: None
frappe.db = types.SimpleNamespace(get_value=get_value, exists=exists, set_value=set_value,
                                  rollback=lambda: None)
frappe.log_error = lambda **k: None
frappe.get_traceback = lambda: ""
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.cint = lambda v: int(float(v or 0))
fu.getdate = lambda x=None: x
fu.now_datetime = lambda: "2026-10-06 10:00"
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.api", "sx.config"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m
ut = types.ModuleType("sx.utils")
ut.get_settings = lambda: D(kho_nvl="NVL", kho_btp="BTP")
ut.get_bom_active = lambda i: BOM_CUA.get(i)
ut.cho_phep_ton_am = lambda: True
ut.sinh_ma_lo = lambda *a: "LO"
ut.topo_rank_by_bom = lambda ds: {}
sys.modules["sx.utils"] = ut
ng = types.ModuleType("sx.api.nogia")
ng.canh_bao_no_gia = ng.ghi_no_gia = ng.huy_no_gia = lambda *a, **k: None
sys.modules["sx.api.nogia"] = ng


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


nap("sx.config.roles", "sx/config/roles.py")
M = nap("sx.api.mfg", "sx/api/mfg.py")
C = nap("sx.api.chot", "sx/api/chot.py")
NGAY2 = None
NGAY = D(name="SXN-1", ngay="2026-10-06", docstatus=0, chot_ghiso=0,
         bao_me=[D(item_btp="DUONG-HOAN", tong_kg=10), D(item_btp="BOT-BANH", tong_kg=100)],
         bao_can=[], su_co=[])

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


def thu(fn):
    try:
        return fn(), None
    except Loi as e:
        return None, e


print("-- có giá vốn không (đúng thứ tự dự phòng của ERPNext) --")
kiem("giá vốn đang chạy ở kho", M.co_gia_von("DUONG", "NVL"))
kiem("Valuation Rate trên Item", M.co_gia_von("DAU", "NVL"))
kiem("từng nhập có giá ở kho khác", M.co_gia_von("MUOI", "NVL"))
kiem("chưa có gì → thiếu", not M.co_gia_von("VANI", "NVL"))
GIA_MUA["VANI"] = 900000
kiem("có giá mua trong Item Price → đủ", M.co_gia_von("VANI", "NVL"))
GIA_MUA.clear()
kiem("giá chuẩn (standard_rate) KHÔNG phải giá vốn → vẫn thiếu", not M.co_gia_von("VANI", "NVL"))

print("\n-- danh sách thiếu của ngày --")
ds = C._thieu_gia_von_ngay(NGAY, ut.get_settings())
kiem("đúng các mã thiếu: Vani + Màu (Màu cần ở 2 công thức → 1 dòng)",
     [d["item"] for d in ds] == ["MAU", "VANI"], [d["item"] for d in ds])
kiem("đường hoán làm ra cùng lần chốt → không bị coi là thiếu",
     all(d["item"] != "DUONG-HOAN" for d in ds))
kiem("nước (không quản lý kho) không bị hỏi giá", all(d["item"] != "NUOC" for d in ds))
v = next(d for d in ds if d["item"] == "VANI")
kiem("gợi ý giá lấy giá chuẩn trên Item, kèm ĐVT", v["goi_y"] == 850000 and v["dvt"] == "Kg", v)
kiem("không có gì để gợi ý → None (không bịa)", next(d for d in ds if d["item"] == "MAU")["goi_y"] is None)

print("\n-- chốt Ghi sổ chặn TRƯỚC khi sinh phiếu kho --")
C._kiem_chua_chot = C._validate_chung = C._kiem_ton_kho = lambda *a, **k: None
sinh = []
C._chot_tang_2 = lambda doc, ct: (sinh.append(1), (_ for _ in ()).throw(Loi("dừng sau tầng 2")))
_, e = thu(lambda: C.chot_ghiso("SXN-1"))
kiem("báo lỗi tiếng Việt, liệt kê HẾT mã thiếu", e and "Vani" in str(e) and "Màu" in str(e)
     and "2 mã" in str(e), e)
kiem("… chỉ cách sửa (khai giá / Valuation Rate)", e and "KHAI GIÁ VỐN" in str(e)
     and "Valuation Rate" in str(e))
kiem("… và CHƯA sinh phiếu kho nào", sinh == [])

print("\n-- khai giá vốn --")
VAI.clear(); VAI.add("SX Vao Hop")
_, e = thu(lambda: C.khai_gia_von(json.dumps([{"item": "VANI", "gia": 1}])))
kiem("không phải quản lý → bị chặn", isinstance(e, frappe.PermissionError), type(e).__name__)
VAI.clear(); VAI.add("SX Quan Ly")
_, e = thu(lambda: C.khai_gia_von(json.dumps([{"item": "VANI", "gia": 0}])))
kiem("giá 0 → chặn", e is not None and ITEM["VANI"]["valuation_rate"] == 0)
r = C.khai_gia_von(json.dumps([{"item": "VANI", "gia": 820000}, {"item": "DAU", "gia": 1},
                               {"item": "KHONG-CO", "gia": 5}]))
kiem("ghi Valuation Rate cho mã đang thiếu", ITEM["VANI"]["valuation_rate"] == 820000)
kiem("mã ĐÃ có giá vốn không bị ghi đè", ITEM["DAU"]["valuation_rate"] == 42000)
kiem("trả về đúng mã đã khai", r["da_khai"] == ["VANI"], r)
kiem("lưu vết bằng comment trên Item", COMMENT and COMMENT[0][0] == "VANI" and "820000" in COMMENT[0][1])
ds = C._thieu_gia_von_ngay(NGAY, ut.get_settings())
kiem("khai xong → Vani hết thiếu, còn Màu", [d["item"] for d in ds] == ["MAU"])
C.khai_gia_von([{"item": "MAU", "gia": 300000}])
_, e = thu(lambda: C.chot_ghiso("SXN-1"))
kiem("khai đủ → chốt đi tiếp tới bước sinh phiếu kho", sinh == [1], e)

print("\n-- D118: bán thành phẩm TỰ TÍNH giá từ nguyên liệu, không hỏi --")
GIA_MUA.clear(); COMMENT.clear()
cap = {("BOT-NEN", "BTP"), ("DUONG-HOAN", "BTP")}
r = M.xet_gia_von(cap)
kiem("đỗ xanh chưa có giá → hỏi ĐỖ XANH, không hỏi bột nền", [d["item"] for d in r["hoi"]]
     == ["DAU-XANH"], [d["item"] for d in r["hoi"]])
kiem("… gợi ý giá mua gần nhất của đỗ", r["hoi"][0]["goi_y"] == 31000)
kiem("đường hoán tính từ đường (giá kho 18000) + màu (đã khai 300000) theo BOM",
     [(d["item"], d["gia"]) for d in r["tu_tinh"]] == [("DUONG-HOAN", 21000.0)], r["tu_tinh"])
SLE_GIA.add("DAU-XANH")                               # đã nhập mua đỗ giá 25000
r = M.xet_gia_von(cap)
g = {d["item"]: d["gia"] for d in r["tu_tinh"]}
kiem("có giá đỗ → không hỏi gì", r["hoi"] == [], r["hoi"])
kiem("bột nền = giá đỗ × hao hụt thật qua rang/tách vỏ/nghiền (25000×100/88)",
     g.get("BOT-NEN") == round(25000 * 100 / 88, 2), g)
r = M.xet_gia_von({("BOT-DAU", "BTP")})
kiem("bột đậu (BOM gồm bột nền + đường hoán) tính lồng nhiều tầng",
     r["hoi"] == [] and r["tu_tinh"][0]["gia"] == round((40 * 25000 * 100 / 88 + 10 * 21000) / 50, 2),
     r["tu_tinh"])
r = M.xet_gia_von({("BOT-MOI", "BTP")})
kiem("bán thành phẩm chưa từng làm, không BOM → đành hỏi chính nó",
     [d["item"] for d in r["hoi"]] == ["BOT-MOI"] and not r["tu_tinh"])
M.ghi_gia_tu_tinh([{"item": "BOT-NEN", "gia": 28409.09}])
kiem("ghi giá tự tính vào Item + comment nói rõ TỰ TÍNH",
     ITEM["BOT-NEN"]["valuation_rate"] == 28409.09 and "TỰ TÍNH" in COMMENT[-1][1])
kiem("đã có giá thì thôi, không tính lại", M.xet_gia_von({("BOT-NEN", "BTP")}) == {"hoi": [], "tu_tinh": []})
ITEM["BOT-NEN"]["valuation_rate"] = 0
SLE_GIA.discard("DAU-XANH")
NGAY2 = D(name="SXN-2", bao_me=[D(item_btp="BOT-DAU", tong_kg=50)])
ds = C._thieu_gia_von_ngay(NGAY2, ut.get_settings())
kiem("chốt ngày làm bột đậu: chỉ hỏi đỗ xanh", [d["item"] for d in ds] == ["DAU-XANH"],
     [d["item"] for d in ds])
SLE_GIA.add("DAU-XANH")
sinh.clear()
_, e = thu(lambda: C.chot_ghiso("SXN-2"))
kiem("chốt: giá bột nền tự ghi TRƯỚC khi sinh phiếu kho, không hỏi ai",
     sinh == [1] and ITEM["BOT-NEN"]["valuation_rate"] == round(25000 * 100 / 88, 2),
     (sinh, ITEM["BOT-NEN"]["valuation_rate"]))

print()
if hong:
    print(f"GIAVON-HỎNG ({hong})")
    sys.exit(1)
print("GIAVON-OK")
