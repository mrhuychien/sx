"""D136 (W26) — hàng trả về vào kho riêng, khoá xuất lô thu hồi.

Vì sao phải có bài này: cả hai lỗi đều im lặng cho tới ngày thật sự cần.
  · Hàng khách trả nhập lại kho bán → lẫn với hàng tốt, bán tiếp cho khách khác.
  · Lô đang thu hồi vẫn bán / giao / đưa vào sản xuất được — vì dòng chọn lô qua
    bundle, vì ERPNext TỰ chọn lô FIFO (bundle chỉ có trong on_submit), hay vì chứng
    từ đi đường Stock Entry thay vì hoá đơn.
  · Ai có quyền ghi Batch trên Desk gỡ cờ thu hồi.

Nạp sx/api/thuhoi.py, sx/config/roles.py, sx/qc/quyen.py, patch d136 THẬT; frappe giả.
Chạy: python3 scripts/test-thuhoi.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import re
import sys
import types
from datetime import date

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

BATCH = {
    "SEN-HSD270405": {"name": "SEN-HSD270405", "item": "TP-SEN", "item_name": "Bánh đậu xanh sen",
                      "expiry_date": date(2027, 4, 5), "batch_qty": 120, "custom_thu_hoi": 0},
    "SEN-HSD270410": {"name": "SEN-HSD270410", "item": "TP-SEN", "item_name": "Bánh đậu xanh sen",
                      "expiry_date": date(2027, 4, 10), "batch_qty": 80, "custom_thu_hoi": 0},
}
SBE = []                         # Serial and Batch Entry: {parent, batch_no}
SU_CO = {}
KHO = []                         # Warehouse
SETTINGS = {"kho_hang_tra_ve": "Kho hàng trả về - RV", "kho_cach_ly": "Kho cách ly - RV",
            "kho_tp": "Kho TP - RV", "cong_ty": "RVHG"}
STOCK = {"TP-SEN": 1, "PHI-VC": 0}
VAI = {"SX Quan Ly"}
NGUOI = {"u": "ql@x"}
BAO = []
CAI_DAT_QC = {}
CHUA_MIGRATE = {"v": False}


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v

    def set(self, k, v):
        self[k] = v


def _so(x):
    return str(x) if x is not None else ""


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "in" and x not in m:
                return False
        elif _so(x) != _so(v):
            return False
    return True


def _bang(dt):
    return {"Batch": list(BATCH.values()), "Serial and Batch Entry": SBE,
            "SX Su Co": list(SU_CO.values()), "Warehouse": KHO}.get(dt, [])


def get_all(dt, filters=None, fields=None, pluck=None, limit=None, order_by=None, **k):
    if CHUA_MIGRATE["v"] and dt == "Batch" and "custom_thu_hoi" in (filters or {}):
        raise Loi("Unknown column custom_thu_hoi")
    ra = [Doc(h) for h in _bang(dt) if _khop(h, filters)]
    if limit:
        ra = ra[:limit]
    return [h.get(pluck) for h in ra] if pluck else ra


def _get_value(dt, f, fld=None, as_dict=False, **k):
    h = next((h for h in _bang(dt) if (h.get("name") == f if isinstance(f, str) else _khop(h, f))), None)
    if h is None:
        return None
    if isinstance(fld, (list, tuple)):
        d = Doc({c: h.get(c) for c in fld})
        return d if as_dict else tuple(d.values())
    return h.get(fld)


def _set_value(dt, n, f, v=None, **k):
    h = next(h for h in _bang(dt) if h["name"] == n)
    h.update(f if isinstance(f, dict) else {f: v})


class ScDoc(Doc):
    def append(self, f, r):
        self.setdefault(f, []).append(Doc(r))

    def insert(self, **k):
        self["name"] = f"SC-2026-{len(SU_CO) + 1:04d}"
        SU_CO[self["name"]] = self
        return self


class KhoDoc(Doc):
    def insert(self, **k):
        self["name"] = f'{self["warehouse_name"]} - RV'
        KHO.append(self)
        return self


class SettingsDoc(Doc):
    flags = types.SimpleNamespace()

    def save(self, **k):
        SETTINGS.update({k_: v for k_, v in self.items()})


def _get_doc(x, n=None):
    if isinstance(x, dict):
        return {"SX Su Co": ScDoc, "Warehouse": KhoDoc}.get(x.get("doctype"), Doc)(x)
    raise Loi(x)


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, **k: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.msgprint = lambda m, **k: BAO.append(str(m))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})


class _Phien:
    user = property(lambda s: NGUOI["u"])


frappe.session = _Phien()
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_doc = _get_doc
frappe.get_single = lambda dt: SettingsDoc(SETTINGS)
frappe.get_cached_doc = lambda dt: Doc(CAI_DAT_QC)
frappe.get_cached_value = lambda dt, n, f: STOCK.get(n, 0) if f == "is_stock_item" else None
frappe.db = types.SimpleNamespace(
    get_value=_get_value, set_value=_set_value,
    exists=lambda dt, f=None: bool(get_all(dt, f if isinstance(f, dict) else {"name": f})),
    table_exists=lambda dt: True,
)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.getdate = lambda x=None: (x if isinstance(x, date) else
                             date.fromisoformat(str(x)[:10]) if x else date(2026, 10, 8))
fu.now_datetime = lambda: "2026-10-08 10:00:00"
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.api", "sx.config", "sx.qc", "sx.patches"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m
ut = types.ModuleType("sx.utils")
ut.get_settings = lambda: Doc(SETTINGS)
sys.modules["sx.utils"] = ut


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


nap("sx.config.roles", "sx/config/roles.py")
nap("sx.qc.nguong", "sx/qc/nguong.py")
nap("sx.qc.quyen", "sx/qc/quyen.py")
T = nap("sx.api.thuhoi", "sx/api/thuhoi.py")
P = nap("sx.patches.d136_kho_tra_ve", "sx/patches/d136_kho_tra_ve.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


def thu(f):
    try:
        f()
    except Exception as e:  # noqa: BLE001
        return str(e) or type(e).__name__
    return None


def vai(*v, u=None):
    VAI.clear(); VAI.update(v)
    NGUOI["u"] = u or {"ISO Manager": "iso@x", "SX Quan Ly": "ql@x"}.get(v[0], "x@x")


def ct(dt, dong, **k):
    return Doc(doctype=dt, items=[Doc(idx=i + 1, **r) for i, r in enumerate(dong)], **k)


# ═══ 1. Hàng trả về ═══════════════════════════════════════════════════════
print("\n-- hàng trả về vào kho riêng --")
d = ct("Sales Invoice", [{"item_code": "TP-SEN", "warehouse": "Kho TP - RV"},
                         {"item_code": "PHI-VC", "warehouse": None}], is_return=1, update_stock=1)
T.kho_tra_ve(d)
kiem("trả hàng có trừ kho → dòng hàng tồn kho nhập Kho hàng trả về",
     d["items"][0]["warehouse"] == "Kho hàng trả về - RV")
kiem("dòng phí / dịch vụ (không tồn kho) không đụng", d["items"][1]["warehouse"] is None)
kiem("báo cho người lập biết", any("Kho hàng trả về" in b for b in BAO))
d = ct("Sales Invoice", [{"item_code": "TP-SEN", "warehouse": "Kho TP - RV"}], is_return=1, update_stock=0)
T.kho_tra_ve(d)
kiem("trả hàng KHÔNG trừ kho (chỉ ghi giảm công nợ) → không đụng", d["items"][0]["warehouse"] == "Kho TP - RV")
d = ct("Delivery Note", [{"item_code": "TP-SEN", "warehouse": "Kho TP - RV"}], is_return=1)
T.kho_tra_ve(d)
kiem("phiếu giao trả về → kho trả về", d["items"][0]["warehouse"] == "Kho hàng trả về - RV")
d = ct("Sales Invoice", [{"item_code": "TP-SEN", "warehouse": "Kho TP - RV"}], is_return=0, update_stock=1)
T.kho_tra_ve(d)
kiem("hoá đơn bán thường → không đụng", d["items"][0]["warehouse"] == "Kho TP - RV")
SETTINGS["kho_hang_tra_ve"] = None
BAO.clear()
d = ct("Sales Invoice", [{"item_code": "TP-SEN", "warehouse": "Kho TP - RV"}], is_return=1, update_stock=1)
T.kho_tra_ve(d)
kiem("chưa khai kho trả về → cảnh báo, không chặn", d["items"][0]["warehouse"] == "Kho TP - RV"
     and any("Chưa khai Kho hàng trả về" in b for b in BAO))
SETTINGS["kho_hang_tra_ve"] = "Kho hàng trả về - RV"
loi = thu(lambda: T.kiem_xuat(ct("Sales Invoice", [{"item_code": "TP-SEN", "warehouse": "Kho hàng trả về - RV",
                                                     "batch_no": "SEN-HSD270410"}], update_stock=1)))
kiem("bán thẳng từ kho trả về → chặn", loi and "kho hàng trả về" in loi, loi or "")

# ═══ 2. Khoá xuất lô thu hồi ══════════════════════════════════════════════
print("\n-- khoá xuất lô thu hồi --")
BATCH["SEN-HSD270405"].update(custom_thu_hoi=1, custom_ly_do_thu_hoi="Dị vật — khiếu nại ISS-12")
ban = lambda dt="Sales Invoice", **k: ct(dt, [  # noqa: E731
    {"item_code": "TP-SEN", "warehouse": "Kho TP - RV", "batch_no": "SEN-HSD270410"},
    {"item_code": "TP-SEN", "warehouse": "Kho TP - RV", **k}], update_stock=1)
loi = thu(lambda: T.kiem_xuat(ban(batch_no="SEN-HSD270405")))
kiem("hoá đơn trừ kho chọn lô thu hồi (ô batch_no) → chặn, nói dòng + HSD",
     loi and "THU HỒI" in loi and "Dòng 2" in loi and "05/04/2027" in loi, loi or "")
SBE[:] = [{"parent": "SABB-1", "batch_no": "SEN-HSD270405"}]
kiem("lô thu hồi nằm trong Serial and Batch Bundle → chặn",
     thu(lambda: T.kiem_xuat(ban(serial_and_batch_bundle="SABB-1"))) is not None)
SBE[:] = [{"parent": "SABB-2", "batch_no": "SEN-HSD270410"}]
kiem("bundle toàn lô bình thường → qua", thu(lambda: T.kiem_xuat(ban(serial_and_batch_bundle="SABB-2"))) is None)
SBE[:] = [{"parent": "SABB-AUTO", "batch_no": "SEN-HSD270405"}]
d = ban()
kiem("before_submit: dòng chưa có lô (ERPNext sẽ tự chọn) → chưa biết, cho qua", thu(lambda: T.kiem_xuat(d)) is None)
d["items"][1]["serial_and_batch_bundle"] = "SABB-AUTO"      # on_submit: ERPNext đã tự chọn lô
kiem("on_submit: ERPNext TỰ chọn trúng lô thu hồi → chặn (cuộn lại cả chứng từ)",
     thu(lambda: T.kiem_xuat(d)) is not None)
for dt in ("Delivery Note", "POS Invoice"):
    kiem(f"{dt} giao lô thu hồi → chặn", thu(lambda: T.kiem_xuat(ban(dt, batch_no="SEN-HSD270405"))) is not None)
d = ban(batch_no="SEN-HSD270405")
d["update_stock"] = 0
kiem("hoá đơn không trừ kho → không xét", thu(lambda: T.kiem_xuat(d)) is None)
d = ban(batch_no="SEN-HSD270405")
d["is_return"] = 1
kiem("phiếu TRẢ HÀNG của lô thu hồi (hàng đang về) → qua", thu(lambda: T.kiem_xuat(d)) is None)


def se(purpose, s, t, lo="SEN-HSD270405"):
    return Doc(doctype="Stock Entry", purpose=purpose,
               items=[Doc(idx=1, item_code="TP-SEN", s_warehouse=s, t_warehouse=t, batch_no=lo)])


kiem("Stock Entry: xuất huỷ (Material Issue) lô thu hồi → được",
     thu(lambda: T.kiem_xuat(se("Material Issue", "Kho TP - RV", None))) is None)
kiem("chuyển lô thu hồi vào kho hàng trả về → được",
     thu(lambda: T.kiem_xuat(se("Material Transfer", "Kho TP - RV", "Kho hàng trả về - RV"))) is None)
kiem("chuyển lô thu hồi vào kho cách ly → được",
     thu(lambda: T.kiem_xuat(se("Material Transfer", "Kho TP - RV", "Kho cách ly - RV"))) is None)
loi = thu(lambda: T.kiem_xuat(se("Material Transfer", "Kho TP - RV", "Kho đại lý - RV")))
kiem("chuyển lô thu hồi sang kho khác → chặn", loi and "kho cách ly" in loi, loi or "")
kiem("đưa lô thu hồi vào sản xuất / đóng gói lại → chặn",
     thu(lambda: T.kiem_xuat(se("Manufacture", "Kho TP - RV", None))) is not None
     and thu(lambda: T.kiem_xuat(se("Repack", "Kho TP - RV", None))) is not None)
kiem("dòng NHẬP (chỉ kho đích) của lô thu hồi → không xét",
     thu(lambda: T.kiem_xuat(se("Material Receipt", None, "Kho TP - RV"))) is None)
kiem("lô không thu hồi → mọi đường đều qua",
     thu(lambda: T.kiem_xuat(se("Manufacture", "Kho TP - RV", None, lo="SEN-HSD270410"))) is None)
CHUA_MIGRATE["v"] = True
kiem("site chưa migrate cột thu hồi → không chặn nhầm, không vỡ",
     thu(lambda: T.kiem_xuat(ban(batch_no="SEN-HSD270405"))) is None)
CHUA_MIGRATE["v"] = False

# ═══ 3. Bật / gỡ thu hồi ══════════════════════════════════════════════════
print("\n-- bật / gỡ thu hồi --")
BATCH["SEN-HSD270405"].update(custom_thu_hoi=0)
vai("SX QC")
kiem("QC không thu hồi được (không có thẻ Truy xuất)", thu(lambda: T.thu_hoi_lo("SEN-HSD270405", "x")) is not None)
vai("ISO Manager")
kiem("thiếu lý do → chặn", "lý do" in (thu(lambda: T.thu_hoi_lo("SEN-HSD270405", " ")) or ""))
r = T.thu_hoi_lo("SEN-HSD270405", "Dị vật nhựa — 3 khiếu nại")
b = BATCH["SEN-HSD270405"]
kiem("thu hồi: bật cờ, ghi lý do, người, giờ", (b["custom_thu_hoi"], b["custom_thu_hoi_boi"]) == (1, "iso@x")
     and "Dị vật" in b["custom_ly_do_thu_hoi"])
sc = SU_CO[r["su_co"]]
kiem("không chỉ phiếu nào → tự lập phiếu sự cố mức Cao gắn đúng lô",
     sc["muc_do"] == "Cao" and [x["batch"] for x in sc["ds_lo"]] == ["SEN-HSD270405"]
     and b["custom_su_co_thu_hoi"] == r["su_co"])
kiem("thu hồi lần hai → chặn", "đang thu hồi" in (thu(lambda: T.thu_hoi_lo("SEN-HSD270405", "x")) or ""))
kiem("chỉ phiếu sự cố không có → chặn",
     thu(lambda: T.thu_hoi_lo("SEN-HSD270410", "x", su_co="SC-KHONG-CO")) is not None)
r2 = T.thu_hoi_lo("SEN-HSD270410", "cùng mẻ", su_co=r["su_co"])
kiem("chỉ đúng phiếu có sẵn → dùng phiếu đó, không lập thêm", r2["su_co"] == r["su_co"] and len(SU_CO) == 1)
ds = T.ds_thu_hoi()
kiem("danh sách lô đang thu hồi", sorted(x["batch"] for x in ds) == ["SEN-HSD270405", "SEN-HSD270410"])
kiem("thông tin thẻ lô: đang thu hồi + được gỡ", T.thong_tin("SEN-HSD270405")["dang"] is True
     and T.thong_tin("SEN-HSD270405")["duoc"] is True)
kiem("gỡ không lý do → chặn", thu(lambda: T.go_thu_hoi("SEN-HSD270410", "")) is not None)
T.go_thu_hoi("SEN-HSD270410", "thu hồi nhầm lô")
kiem("gỡ: tắt cờ, lý do cũ còn + dòng gỡ (lịch sử)", BATCH["SEN-HSD270410"]["custom_thu_hoi"] == 0
     and "cùng mẻ" in BATCH["SEN-HSD270410"]["custom_ly_do_thu_hoi"]
     and "[Gỡ" in BATCH["SEN-HSD270410"]["custom_ly_do_thu_hoi"])
kiem("gỡ lô không thu hồi → chặn", thu(lambda: T.go_thu_hoi("SEN-HSD270410", "x")) is not None)
vai("SX Quan Ly")
kiem("quản lý (SX Quan Ly) thu hồi được", thu(lambda: T.thu_hoi_lo("SEN-HSD270410", "x")) is None)


class BatchDoc(Doc):
    def is_new(self):
        return False

    def has_value_changed(self, f):
        return BATCH[self["name"]].get(f) != self.get(f)


vai("Stock User", u="kho@x")
d = BatchDoc(BATCH["SEN-HSD270405"], custom_thu_hoi=0)
kiem("Desk: thủ kho tự gỡ cờ thu hồi trên Batch → chặn", thu(lambda: T.kiem_sua_batch(d)) is not None)
d = BatchDoc(BATCH["SEN-HSD270405"], batch_qty=5)
kiem("Desk: sửa ô khác của Batch → không vướng", thu(lambda: T.kiem_sua_batch(d)) is None)
vai("ISO Manager")
d = BatchDoc(BATCH["SEN-HSD270405"], custom_thu_hoi=0)
kiem("Desk: Ban ISO gỡ cờ được", thu(lambda: T.kiem_sua_batch(d)) is None)

# ═══ 4. Patch d136 ════════════════════════════════════════════════════════
print("\n-- patch d136: tạo kho trả về / kho cách ly --")
SETTINGS.update(kho_hang_tra_ve=None, kho_cach_ly="Kho CL tự tạo - RV")
KHO[:] = [{"name": "Kho TP - RV", "warehouse_name": "Kho TP", "company": "RVHG", "parent_warehouse": "Kho - RV"},
          {"name": "Kho hàng trả về - RV", "warehouse_name": "Kho hàng trả về", "company": "RVHG"}]
P.execute()
kiem("kho cùng tên đã có → dùng lại, không tạo trùng", SETTINGS["kho_hang_tra_ve"] == "Kho hàng trả về - RV"
     and len(KHO) == 2)
kiem("ô đã khai → để nguyên", SETTINGS["kho_cach_ly"] == "Kho CL tự tạo - RV")
SETTINGS.update(kho_hang_tra_ve=None, kho_cach_ly=None)
KHO[:] = KHO[:1]
P.execute()
kiem("chưa có → tạo cạnh kho TP (cùng kho cha) và khai vào Settings",
     SETTINGS["kho_hang_tra_ve"] == "Kho hàng trả về - RV" and SETTINGS["kho_cach_ly"] == "Kho cách ly - RV"
     and all(k.get("parent_warehouse") == "Kho - RV" for k in KHO[1:]))
n = len(KHO)
P.execute()
kiem("chạy lại vô hại", len(KHO) == n)
SETTINGS.update(kho_hang_tra_ve=None, cong_ty=None)
P.execute()
kiem("chưa khai công ty → không làm gì", SETTINGS["kho_hang_tra_ve"] is None)
kiem("patch có trong patches.txt", "sx.patches.d136_kho_tra_ve" in open("sx/patches.txt", encoding="utf-8").read())

# ═══ 5. Cấu hình ══════════════════════════════════════════════════════════
print("\n-- cấu hình, hook, màn hình --")
st = {f["fieldname"]: f for f in json.load(open("sx/sx/doctype/sx_settings/sx_settings.json",
                                                 encoding="utf-8"))["fields"]}
kiem("SX Settings: kho hàng trả về + kho cách ly (Link Warehouse)",
     st["kho_hang_tra_ve"]["options"] == st["kho_cach_ly"]["options"] == "Warehouse")
cf = {f["fieldname"]: f for f in json.load(open("sx/fixtures/custom_field.json", encoding="utf-8"))
      if f["dt"] == "Batch"}
kiem("Batch có cờ thu hồi + lý do / phiếu / người / giờ (chỉ đọc trừ cờ)",
     {"custom_thu_hoi", "custom_ly_do_thu_hoi", "custom_su_co_thu_hoi", "custom_thu_hoi_boi",
      "custom_thu_hoi_luc"} <= set(cf) and all(cf[f].get("read_only") for f in
                                                ("custom_ly_do_thu_hoi", "custom_thu_hoi_boi", "custom_thu_hoi_luc")))
hk = open("sx/hooks.py", encoding="utf-8").read()
for dt in ("Sales Invoice", "Delivery Note", "POS Invoice", "Stock Entry"):
    khoi = re.search(r'"%s": \{(.*?)\}' % dt, hk, re.S)
    kiem(f"hook {dt}: kiem_xuat cả before_submit lẫn on_submit",
         khoi and khoi.group(1).count("sx.api.thuhoi.kiem_xuat") == 2)
for dt in ("Sales Invoice", "Delivery Note"):
    khoi = re.search(r'"%s": \{(.*?)\}' % dt, hk, re.S)
    kiem(f"hook trả hàng (validate) cho {dt}",
         khoi is not None and re.search(r'"validate": \[?[^\]]*"sx\.api\.thuhoi\.kho_tra_ve"',
                                        khoi.group(1)) is not None)
kiem("hook Batch.validate chặn gỡ cờ trên Desk", '"Batch": {"validate": "sx.api.thuhoi.kiem_sua_batch"}' in hk)
kiem("W06 vẫn còn: bán phải chọn lô", hk.count("sx.api.banhang.kiem_lo_ban") == 2)
js = open("sx/public/sx/cards/truyxuat.js", encoding="utf-8").read()
for m in sorted(set(re.findall(r"sx\.api\.thuhoi\.(\w+)", js))):
    kiem(f"thẻ Truy xuất gọi method có thật: thuhoi.{m}", callable(getattr(T, m, None)))
kiem("thẻ lô: dải đỏ LÔ ĐANG THU HỒI + nút thu hồi / gỡ (chỉ người được)",
     "LÔ ĐANG THU HỒI" in js and "d.thu_hoi.duoc ? () => moThuHoi" in js)

print(f"\n{'THUHOI-OK' if not hong else f'THUHOI-FAIL ({hong})'}")
sys.exit(1 if hong else 0)
