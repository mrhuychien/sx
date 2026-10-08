"""D104 — huỷ phiếu nhập kho ĐÃ DUYỆT từ màn Nhập kho.

Trước D104 không có nút nào: thủ kho duyệt nhầm là phải nhờ người có quyền
System Manager vào Desk. Huỷ là THU HỒI chứng từ kho thật nên hỏng theo hướng
nguy hiểm:
  · huỷ khi hàng đã bán / xuất đi → ERPNext văng tiếng Anh về tồn âm, hoặc tồn âm;
  · huỷ không lý do → tháng sau đối chiếu tồn không ai giải thích được;
  · QC (người lập) tự huỷ phiếu đã duyệt → mất ý nghĩa "người khác duyệt";
  · "Huỷ & lập lại" đẻ hai phiếu nháp, hoặc làm mất dòng.

Nạp sx/api/khotp.py và controller SX Phieu Nhap TP THẬT; frappe / ERPNext là giả.
Chạy: python3 scripts/test-huyphieu.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

PHIEU = {}          # name -> doc
SED = []            # Stock Entry Detail
BIN = {}            # (item, kho) -> qty
LO = {}             # (batch, kho) -> qty
HUY_CT = []         # chứng từ kho đã huỷ
VAI = {"SX Thu Kho"}
TON_AM = [False]
MSG = []


class Loi(Exception):
    pass


class _dict(dict):
    __getattr__ = dict.get

    def __setattr__(self, k, v):
        self[k] = v


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        if k == "flags":
            return self.setdefault("_flags", _dict())
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v

    def append(self, k, v):
        r = Doc(v)
        self.setdefault(k, []).append(r)
        return r

    def db_set(self, k, v=None, **kw):
        self[k] = v


class PhieuDoc(Doc):
    def cancel(self):
        P.SXPhieuNhapTP.on_cancel(self)
        self["docstatus"] = 2

    def insert(self):
        self["name"] = f"PN-{len(PHIEU) + 1}"
        self.setdefault("docstatus", 0)
        PHIEU[self["name"]] = self
        return self

    def delete(self):
        PHIEU.pop(self["name"])


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple) and v[0] == "in":
            if x not in v[1]:
                return False
        elif x != v:
            return False
    return True


def get_all(dt, filters=None, fields=None, pluck=None, **k):
    src = {"SX Phieu Nhap TP": list(PHIEU.values()), "Stock Entry Detail": SED}.get(dt, [])
    ra = [Doc(h) for h in src if _khop(h, filters)]
    return [h.get(pluck) for h in ra] if pluck else ra


def _get_value(dt, f, field=None, **k):
    if dt == "SX Phieu Nhap TP":
        h = next(iter(get_all(dt, f)), None) if isinstance(f, dict) else PHIEU.get(f)
        return h.get(field) if h else None
    if dt == "Bin":
        return BIN.get((f["item_code"], f["warehouse"]), 0)
    return None


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.msgprint = lambda m, **k: MSG.append(m)
# D114: mã hàng có Shelf Life — HSD tự điền, không chặn duyệt (test-hsd.py lo phần đó).
frappe.get_cached_value = lambda dt, n, f=None: 180 if f == "shelf_life_in_days" else None
frappe.session = types.SimpleNamespace(user="thukho@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_doc = lambda dt, n=None: PHIEU[n]
frappe.new_doc = lambda dt: PhieuDoc(doctype=dt, dong=[])
frappe.db = types.SimpleNamespace(get_value=_get_value, rollback=lambda: None,
                                  set_value=lambda *a, **k: None)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.cint = lambda v: int(float(v or 0))
fu.getdate = lambda x=None: x
fu.nowdate = lambda: "2026-10-02"
fu.add_days = lambda d, n: d
fu.now_datetime = lambda: "2026-10-02 10:00:00"
fu.escape_html = lambda s: s
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
mdl = types.ModuleType("frappe.model"); mdl.__path__ = []
dm = types.ModuleType("frappe.model.document"); dm.Document = Doc
sys.modules["frappe.model"] = mdl
sys.modules["frappe.model.document"] = dm

for g in ("sx", "sx.api", "sx.config", "sx.sx", "sx.sx.doctype", "erpnext", "erpnext.stock",
          "erpnext.stock.doctype", "erpnext.stock.doctype.batch"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m
eb = types.ModuleType("erpnext.stock.doctype.batch.batch")
eb.get_batch_qty = lambda batch_no=None, warehouse=None, item_code=None: LO.get((batch_no, warehouse), 0)
sys.modules["erpnext.stock.doctype.batch.batch"] = eb
ut = types.ModuleType("sx.utils")
ut.get_bom_active = lambda i: "BOM-" + i
ut.get_settings = lambda: Doc(kho_tp="TP")
ut.items_tp = lambda *a, **k: []
ut.nhom_tp = lambda: []
ut.cho_phep_ton_am = lambda: TON_AM[0]
ut.nho = lambda ten: {}   # D120: bộ nhớ request — test giả không nhớ
ut.nap_bom = lambda items: {i: ut.get_bom_active(i) for i in (items or [])} if hasattr(ut, "get_bom_active") else {}
ut.ton_bin = lambda items, kho: {}
# D127: hạn dùng theo bộ tự công bố — bản giả: chưa mã nào gắn sản phẩm, rơi về
# Shelf Life (ngày) như trước. Logic thật kiểm ở scripts/test-congbo.py.
from datetime import date as _date_d127, timedelta as _td_d127


def _hsd_d127(item, ngay, dau=1):
    so = int(frappe.get_cached_value("Item", item, "shelf_life_in_days") or 0)
    if so <= 0 or not ngay:
        return None
    d = ngay if isinstance(ngay, _date_d127) else _date_d127.fromisoformat(str(ngay)[:10])
    return str(d + _td_d127(days=dau * so))


ut.hsd_tu_nsx = lambda item, nsx: _hsd_d127(item, nsx)
ut.nsx_tu_hsd = lambda item, hsd: _hsd_d127(item, hsd, -1)
ut.nap_cong_bo = lambda items: {i: None for i in (items or [])}
ut.cong_bo_cua = lambda item: None
ut.han_dung = lambda item, sl=None: (
    ("ngay", int(sl if sl is not None else frappe.get_cached_value("Item", item, "shelf_life_in_days") or 0))
    if int(sl if sl is not None else frappe.get_cached_value("Item", item, "shelf_life_in_days") or 0) > 0 else None)
sys.modules["sx.utils"] = ut
mfg = types.ModuleType("sx.api.mfg")
mfg.thieu_gia_von = lambda cap: []   # D116: giá vốn kiểm ở test-giavon.py
mfg.bao_thieu_gia_von = lambda ds, viec: None
mfg.xet_gia_von = lambda cap: {"hoi": [], "tu_tinh": []}
mfg.ghi_gia_tu_tinh = lambda ds: None
mfg.cancel_doc = lambda dt, n, log=None: HUY_CT.append(n)
sys.modules["sx.api.mfg"] = mfg


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


R = nap("sx.config.roles", "sx/config/roles.py")
K = nap("sx.api.khotp", "sx/api/khotp.py")
P = nap("sx.sx.doctype.sx_phieu_nhap_tp.sx_phieu_nhap_tp",
        "sx/sx/doctype/sx_phieu_nhap_tp/sx_phieu_nhap_tp.py")

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


def lam_sach():
    PHIEU.clear(); SED.clear(); BIN.clear(); LO.clear(); HUY_CT.clear(); MSG.clear()
    VAI.clear(); VAI.add("SX Thu Kho")
    TON_AM[0] = False
    p = PhieuDoc(name="PN-1", docstatus=1, ngay="2026-10-01", kho_dich="TP",
                 nguoi_lap="qc@x", ghi_chu="",
                 ds_se=json.dumps([{"dt": "Work Order", "name": "WO-1"},
                                   {"dt": "Stock Entry", "name": "SE-1"},
                                   {"dt": "Work Order", "name": "WO-2"},
                                   {"dt": "Stock Entry", "name": "SE-2"}]),
                 dong=[Doc(item="TP-SEN", ten="Sen", so_lap=100, so_dem=100, idx=1),
                       Doc(item="TP-CU", ten="Cũ", so_lap=30, so_dem=28, idx=2)])
    PHIEU["PN-1"] = p
    SED.extend([Doc(parent="SE-1", item_code="TP-SEN", batch_no="SEN-011026", qty=100,
                    t_warehouse="TP"),
                Doc(parent="SE-1", item_code="BOT", batch_no="B1", qty=30, t_warehouse=None),
                Doc(parent="SE-2", item_code="TP-CU", batch_no=None, qty=28, t_warehouse="TP")])
    LO[("SEN-011026", "TP")] = 100
    BIN[("TP-CU", "TP")] = 50
    return p


print("-- ai huỷ được, phải nói gì --")
lam_sach()
VAI.clear(); VAI.add("SX Vao Hop")
_, loi = thu(lambda: K.huy_phieu("PN-1", "đếm sai"))
kiem("QC (người lập) KHÔNG huỷ được phiếu đã duyệt", loi and "THỦ KHO" in loi, loi or "")
VAI.clear(); VAI.add("SX Thu Kho")
_, loi = thu(lambda: K.huy_phieu("PN-1", "  "))
kiem("không lý do → chặn", loi and "lý do" in loi, loi or "")
kiem("… và chưa thu hồi gì", not HUY_CT and PHIEU["PN-1"].docstatus == 1)
ct = K.chi_tiet_phieu("PN-1")
kiem("màn hình biết thủ kho được huỷ", ct["duoc_huy"] is True)
VAI.clear(); VAI.add("SX Vao Hop")
kiem("… QC thì không", K.chi_tiet_phieu("PN-1")["duoc_huy"] is False)
VAI.clear(); VAI.add("SX Thu Kho")

print("\n-- hàng đã ra khỏi kho thì không huỷ --")
LO[("SEN-011026", "TP")] = 40
_, loi = thu(lambda: K.huy_phieu("PN-1", "đếm sai"))
kiem("lô đã bán bớt → chặn, nói rõ mã, lô, còn bao nhiêu",
     loi and "SEN-011026" in loi and "còn 40" in loi, loi or "")
kiem("… và không thu hồi gì", not HUY_CT and PHIEU["PN-1"].docstatus == 1)
LO[("SEN-011026", "TP")] = 100
BIN[("TP-CU", "TP")] = 10
_, loi = thu(lambda: K.huy_phieu("PN-1", "đếm sai"))
kiem("mã không lô: tồn mã trong kho không đủ → chặn", loi and "TP-CU" in loi, loi or "")
TON_AM[0] = True
_, loi = thu(lambda: K.huy_phieu("PN-1", "đếm sai"))
kiem("site cho tồn âm → mã không lô không chặn", loi is None, loi or "")
kiem("… thu hồi đúng chứng từ, SE trước WO",
     HUY_CT == ["SE-2", "WO-2", "SE-1", "WO-1"], str(HUY_CT))
kiem("… lý do ghi vào phiếu", "[Lý do huỷ] đếm sai" in PHIEU["PN-1"].ghi_chu)

print("\n-- huỷ & lập lại --")
lam_sach()
kq, loi = thu(lambda: K.huy_phieu("PN-1", "đếm sai dòng Cũ", lap_lai=1))
moi = PHIEU.get((kq or {}).get("phieu_moi"))
kiem("lập phiếu nháp mới", loi is None and moi and moi.docstatus == 0, loi or str(kq))
kiem("… chép đủ dòng, đúng số đếm cũ",
     moi and [(r.item, r.so_dem) for r in moi.dong] == [("TP-SEN", 100), ("TP-CU", 28)])
kiem("… cùng ngày, ghi rõ lập lại từ phiếu nào",
     moi and moi.ngay == "2026-10-01" and "PN-1" in moi.ghi_chu)
lam_sach()
PHIEU["PN-9"] = PhieuDoc(name="PN-9", docstatus=0, dong=[])
kq, loi = thu(lambda: K.huy_phieu("PN-1", "x", lap_lai=1))
kiem("đang có phiếu nháp khác → vẫn huỷ, KHÔNG đẻ phiếu nháp thứ hai, và nói ra",
     loi is None and kq.get("phieu_moi") is None
     and sum(1 for p in PHIEU.values() if p.docstatus == 0) == 1 and MSG)
kiem("màn hình biết đang có phiếu nháp (ẩn nút lập lại)", K.chi_tiet_phieu("PN-1")["co_nhap"])

print("\n-- màn hình --")
js = open("sx/public/sx/cards/nhapkhotp.js", encoding="utf-8").read()
kiem("phiếu đã duyệt gần đây bấm được", "data-phieu=" in js and "moPhieuDaDuyet" in js)
kiem("có HUỶ PHIẾU và HUỶ & LẬP LẠI", "'HUỶ PHIẾU'" in js and "'HUỶ & LẬP LẠI'" in js)
kiem("gửi lý do + lập lại lên server", "ly_do: ta.value.trim(), lap_lai" in js)

print("HUYPHIEU-OK" if not hong else f"HUYPHIEU: {hong} HỎNG")
sys.exit(1 if hong else 0)
