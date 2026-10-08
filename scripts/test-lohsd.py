"""D131 (W05) — lô thành phẩm theo HSD: mỗi (sản phẩm, HSD) một lô, NSX tính ngược.

Hỏng theo hướng nguy hiểm, và im lặng:
  · Hai ngày đóng hộp (hai HSD) dồn vào MỘT dòng một HSD → một lô mang HSD sai cho
    nửa số hộp; truy xuất theo HSD in trên hộp không ra.
  · NSX = ngày nhập kho thay vì ngày làm ra → "quá trình" khớp nhầm ngày vào hộp.
  · Cùng mã cùng HSD mà ra hai lô (hai phiếu) → tồn theo lô bị xé, xuất FEFO sai.
  · Sửa / tải lại phiếu làm rơi số người lập, số đếm, HSD đã gõ của từng dòng.
  · Lô cũ chưa có HSD bị ghi đè, hoặc ghi HSD trước NSX.

Nạp sx/utils.py, sx/api/khotp.py, sx/api/lohsd.py, controller SX Phieu Nhap TP THẬT.
Chạy: python3 scripts/test-lohsd.py   (verify.sh gọi sẵn)
"""

import calendar
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


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
        r.setdefault("idx", len(self.get(k) or []) + 1)
        self.setdefault(k, []).append(r)
        return r

    def set(self, k, v):
        self[k] = v

    def db_set(self, k, v=None, **kw):
        self[k] = v


ITEM = {"TP-SEN": Doc(name="TP-SEN", item_name="Bánh sen", stock_uom="Hộp",
                      custom_batch_prefix="SEN", custom_sp_cong_bo="SPCB-001",
                      shelf_life_in_days=0),
        "TP-CU": Doc(name="TP-CU", item_name="Bánh cũ", stock_uom="Hộp",
                     custom_batch_prefix="CU", custom_sp_cong_bo=None, shelf_life_in_days=0),
        "TP-KHAC": Doc(name="TP-KHAC", item_name="Mã khác", stock_uom="Hộp",
                       custom_batch_prefix="SEN", custom_sp_cong_bo=None, shelf_life_in_days=0)}
SP = {"SPCB-001": Doc(name="SPCB-001", so_cong_bo="01/2023", han_dung_thang=9)}
BATCH = {}
PHIEU = {}
VAI = {"SX Thu Kho"}


class PhieuDoc(Doc):
    def save(self):
        for i, r in enumerate(self["dong"], 1):
            r["idx"] = i
        P.SXPhieuNhapTP.validate(self)
        PHIEU[self["name"]] = PhieuDoc(self, dong=[Doc(r) for r in self["dong"]])
        return self


class BatchDoc(Doc):
    def insert(self):
        self["name"] = self["batch_id"]
        BATCH[self["name"]] = dict(self, expiry_date=self.get("expiry_date"),
                                   manufacturing_date=self.get("manufacturing_date"))
        return self


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "in" and x not in m:
                return False
            if op == "is" and ((m == "set") != bool(x)):
                return False
            if op == ">" and not (float(x or 0) > m):
                return False
            if op == "<=" and not (float(x or 0) <= m):
                return False
        elif x != v:
            return False
    return True


def get_all(dt_, filters=None, fields=None, pluck=None, **k):
    nguon = {"Item": ITEM, "SX San Pham Cong Bo": SP, "Batch": BATCH}.get(dt_)
    if nguon is None:
        return []
    ra = [Doc(x) for x in nguon.values() if _khop(x, filters)]
    return [x.get(pluck) for x in ra] if pluck else ra


def get_value(dt_, f, field=None, as_dict=False, **k):
    nguon = {"Item": ITEM, "Batch": BATCH}.get(dt_, {})
    x = nguon.get(f) if isinstance(f, str) else next(
        (v for v in nguon.values() if _khop(v, f)), None)
    if not x:
        return None
    if isinstance(field, list):
        return Doc({c: x.get(c) for c in field}) if as_dict else tuple(x.get(c) for c in field)
    return x.get(field)


def exists(dt_, f=None):
    if dt_ == "Batch":
        return f in BATCH if isinstance(f, str) else False
    if dt_ == "Item" and isinstance(f, dict):
        return any(_khop(x, {k: v for k, v in f.items() if k != "name"})
                   and x["name"] != f.get("name", (None, None))[1] for x in ITEM.values())
    return False


def set_value(dt_, n, k, v=None, **kw):
    {"Batch": BATCH, "Item": ITEM}[dt_][n].update(k if isinstance(k, dict) else {k: v})


def _gd(x=None):
    return x if isinstance(x, dt.date) else dt.date.fromisoformat(str(x)[:10])


def _add_months(d, n):
    d = _gd(d)
    t = d.month - 1 + n
    y, m = d.year + t // 12, t % 12 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, title=None: (_ for _ in ()).throw(Loi(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.msgprint = lambda *a, **k: None
frappe.session = types.SimpleNamespace(user="thukho@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_doc = lambda d, n=None: (BatchDoc(d) if isinstance(d, dict)
                                    else PhieuDoc(PHIEU[n], dong=[Doc(r) for r in PHIEU[n]["dong"]]))
frappe.get_meta = lambda d: types.SimpleNamespace(get_field=lambda f: True, has_field=lambda f: True)
frappe.get_cached_value = lambda d, n, f=None: (ITEM.get(n) or {}).get(f) if d == "Item" else None
frappe.get_cached_doc = lambda d: Doc(kho_tp="TP", cong_ty="C", kho_nvl="NVL", nhom_tp=[])
frappe.local = types.SimpleNamespace()
frappe.log_error = lambda **k: None
frappe.db = types.SimpleNamespace(get_value=get_value, set_value=set_value, exists=exists,
                                  count=lambda dt_, f=None: len(get_all(dt_, f)))
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.cint = lambda v: int(float(v or 0))
fu.getdate = _gd
fu.nowdate = lambda: "2026-10-08"
fu.add_days = lambda d, n: _gd(d) + dt.timedelta(days=n)
fu.add_months = _add_months
fu.now_datetime = lambda: "2026-10-08 10:00:00"
fu.formatdate = lambda d: str(d)
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
mdl = types.ModuleType("frappe.model"); mdl.__path__ = []
dm = types.ModuleType("frappe.model.document"); dm.Document = Doc
sys.modules["frappe.model"] = mdl
sys.modules["frappe.model.document"] = dm
for g in ("sx", "sx.api", "sx.config", "sx.sx", "sx.sx.doctype"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


R = nap("sx.config.roles", "sx/config/roles.py")
U = nap("sx.utils", "sx/utils.py")
U.items_tp = lambda fields=None, **k: [Doc(x) for x in ITEM.values() if x["name"] != "TP-KHAC"]
U.get_bom_active = lambda i: "BOM-" + i
M = nap("sx.api.mfg", "sx/api/mfg.py")
M.dam_bao_quan_ly_lo = lambda item: True
K = nap("sx.api.khotp", "sx/api/khotp.py")
P = nap("sx.sx.doctype.sx_phieu_nhap_tp.sx_phieu_nhap_tp",
        "sx/sx/doctype/sx_phieu_nhap_tp/sx_phieu_nhap_tp.py")
L = nap("sx.api.lohsd", "sx/api/lohsd.py")
K.vuot_so_cham = lambda *a, **k: {}
K._uom_cua = lambda *a, **k: []
P.SXPhieuNhapTP.kiem_tran_da_cham = lambda self: None
P.SXPhieuNhapTP.kiem_ton_nguyen_lieu = lambda self: None
ch = types.ModuleType("sx.api.chot"); ch._kho_nguon = lambda i, s: "NVL"
sys.modules["sx.api.chot"] = ch

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
        return None, str(e)


print("-- mã lô theo HSD --")
kiem("(sản phẩm, HSD) → {prefix}-HSD{DDMMYY}", U.ma_lo_hsd("TP-SEN", "2027-07-08") == "SEN-HSD080727",
     U.ma_lo_hsd("TP-SEN", "2027-07-08"))
BATCH["SEN-HSD080727"] = {"name": "SEN-HSD080727", "item": "TP-SEN"}
kiem("lô đã có của CHÍNH mã đó → dùng lại (cùng HSD = cùng lô)",
     U.ma_lo_hsd("TP-SEN", "2027-07-08") == "SEN-HSD080727")
kiem("trùng mã lô của mặt hàng KHÁC (prefix trùng) → thêm -2",
     U.ma_lo_hsd("TP-KHAC", "2027-07-08") == "SEN-HSD080727-2")
BATCH.clear()
kiem("nhận ra lô theo HSD", U.la_lo_hsd("SEN-HSD080727") and not U.la_lo_hsd("SEN-081026"))

print("\n-- vừa vào hộp chia theo HSD (ngày đóng hộp → HSD) --")
CHAM = [("2026-10-01", "TP-SEN", 100), ("2026-10-02", "TP-SEN", 50), ("2026-10-03", "TP-SEN", 80),
        ("2026-10-02", "TP-CU", 20)]
K._cham_theo_ngay = lambda tu, den, items: [(_gd(d), i, so) for d, i, so in CHAM if i in items]
K.tran_con_lai = lambda tu, den, tru=None: {"TP-SEN": 110.0, "TP-CU": 20.0}
c = K.con_theo_hsd("2026-09-09", "2026-10-08")
kiem("phần còn lại gán cho ngày đóng MỚI NHẤT trước (đã nhận = hàng đóng trước)",
     [(g["nsx"], g["con"]) for g in c["TP-SEN"]] == [("2026-10-02", 30.0), ("2026-10-03", 80.0)],
     c["TP-SEN"])
kiem("mỗi ngày đóng một HSD = ngày + 9 tháng (theo lịch)",
     [g["hsd"] for g in c["TP-SEN"]] == ["2027-07-02", "2027-07-03"])
kiem("mã chưa khai hạn dùng → một nhóm, HSD None (thủ kho gõ theo bao bì)",
     [(g["hsd"], g["con"]) for g in c["TP-CU"]] == [(None, 20.0)])

print("\n-- tải từ vào hộp: mỗi HSD một dòng --")
PHIEU["PN-1"] = PhieuDoc(name="PN-1", docstatus=0, ngay="2026-10-08", kho_dich="TP", dong=[
    Doc(item="TP-SEN", ten="Bánh sen", so_lap=80, so_dem=75, hsd="2027-07-03", idx=1),
    Doc(item="TP-CU", ten="Bánh cũ", so_lap=20, so_dem=20, hsd="2027-05-01", idx=2),
    Doc(item="TP-TRA", ten="Hàng trả về", so_lap=3, so_dem=3, hsd="2027-01-01", idx=3)])
ct = K.tai_tu_vao_hop("PN-1")
dong = [(x["item"], x["hsd"], x["so_lap"], x["so_dem"]) for x in ct["dong"]]
kiem("bánh sen thành HAI dòng theo HSD", [d for d in dong if d[0] == "TP-SEN"]
     == [("TP-SEN", "2027-07-02", 30, 30), ("TP-SEN", "2027-07-03", 80, 75)], dong)
kiem("số thủ kho đã đếm giữ theo (mã, HSD) — 75 của dòng HSD 03/07",
     ("TP-SEN", "2027-07-03", 80, 75) in dong)
kiem("mã chưa khai hạn dùng: HSD thủ kho đã gõ được giữ", ("TP-CU", "2027-05-01", 20, 20) in dong)
kiem("dòng không có trong bảng chấm (hàng trả về) sống sót", any(d[0] == "TP-TRA" for d in dong))

print("\n-- sửa phiếu: số người lập theo (mã, HSD) --")
VAI.clear(); VAI.add("SX Thu Kho")
ct = K.sua_phieu("PN-1", json.dumps([
    {"item": "TP-SEN", "so_dem": 29, "hsd": "2027-07-02"},
    {"item": "TP-SEN", "so_dem": 70, "hsd": "2027-07-03"}]))
d = {x["hsd"]: x for x in ct["dong"]}
kiem("thủ kho sửa số đếm → số người lập GIỮ đúng dòng (30 / 80)",
     (d["2027-07-02"]["so_lap"], d["2027-07-03"]["so_lap"]) == (30, 80),
     [(x["hsd"], x["so_lap"], x["so_dem"]) for x in ct["dong"]])

print("\n-- duyệt: một lô mỗi (mã, HSD), NSX = HSD − hạn dùng --")
p = P.SXPhieuNhapTP(name="PN-2", docstatus=0, ngay="2026-10-08", kho_dich="TP", dong=[
    Doc(item="TP-SEN", ten="Bánh sen", so_lap=30, so_dem=30, hsd="2027-07-02", idx=1),
    Doc(item="TP-SEN", ten="Bánh sen", so_lap=80, so_dem=80, hsd="2027-07-02", idx=2)])
_, loi = thu(lambda: P.SXPhieuNhapTP.before_submit(p))
kiem("hai dòng cùng mã cùng HSD → chặn, bảo gộp lại", bool(loi) and "cùng một lô" in loi, loi)
p["dong"][1]["hsd"] = "2027-07-03"
_, loi = thu(lambda: P.SXPhieuNhapTP.before_submit(p))
kiem("cùng mã, HSD khác → qua", loi is None, loi)
M.tao_wo = lambda *a, **k: types.SimpleNamespace(name="WO-1")
M.tao_se_manufacture = lambda wo, qty, batch, **k: types.SimpleNamespace(name=f"SE-{batch}")
P.SXPhieuNhapTP.on_submit(p)
kiem("hai lô theo HSD", sorted(BATCH) == ["SEN-HSD020727", "SEN-HSD030727"], sorted(BATCH))
kiem("NSX = HSD − 9 tháng (02/07/2027 → 02/10/2026), KHÔNG phải ngày nhập 08/10",
     BATCH["SEN-HSD020727"]["manufacturing_date"] == "2026-10-02",
     BATCH["SEN-HSD020727"]["manufacturing_date"])
kiem("HSD ghi vào lô", BATCH["SEN-HSD030727"]["expiry_date"] == "2027-07-03")
p2 = P.SXPhieuNhapTP(name="PN-3", docstatus=0, ngay="2026-10-09", kho_dich="TP", dong=[
    Doc(item="TP-SEN", ten="Bánh sen", so_lap=5, so_dem=5, hsd="2027-07-03", idx=1)])
P.SXPhieuNhapTP.before_submit(p2)
P.SXPhieuNhapTP.on_submit(p2)
kiem("phiếu sau, cùng mã cùng HSD → vào ĐÚNG lô cũ, không đẻ lô mới",
     sorted(BATCH) == ["SEN-HSD020727", "SEN-HSD030727"]
     and json.loads(p2["ds_se"])[-1]["name"] == "SE-SEN-HSD030727")
p3 = P.SXPhieuNhapTP(name="PN-4", docstatus=0, ngay="2026-10-09", kho_dich="TP", dong=[
    Doc(item="TP-CU", ten="Bánh cũ", so_lap=5, so_dem=5, hsd="2027-05-01", idx=1)])
P.SXPhieuNhapTP.before_submit(p3)
P.SXPhieuNhapTP.on_submit(p3)
kiem("mã chưa khai hạn dùng → NSX lấy ngày nhập", BATCH["CU-HSD010527"]["manufacturing_date"]
     == "2026-10-09")

print("\n-- lô cũ chưa có HSD --")
BATCH.clear()
BATCH["SEN-290926"] = {"name": "SEN-290926", "item": "TP-SEN", "item_name": "Bánh sen",
                       "manufacturing_date": "2026-09-29", "expiry_date": None, "batch_qty": 40,
                       "creation": "2026-09-29 10:00:00", "stock_uom": "Hộp"}
BATCH["SEN-150926"] = {"name": "SEN-150926", "item": "TP-SEN", "item_name": "Bánh sen",
                       "manufacturing_date": None, "expiry_date": None, "batch_qty": 0,
                       "creation": "2026-09-15 08:00:00", "stock_uom": "Hộp"}
BATCH["SEN-HSD010727"] = {"name": "SEN-HSD010727", "item": "TP-SEN", "item_name": "Bánh sen",
                          "manufacturing_date": "2026-10-01", "expiry_date": "2027-07-01",
                          "batch_qty": 9, "creation": "2026-10-01", "stock_uom": "Hộp"}
BATCH["BOT-1"] = {"name": "BOT-1", "item": "BOT", "expiry_date": None, "batch_qty": 5,
                  "creation": "2026-10-01"}
ds = L.danh_sach()
kiem("mặc định chỉ lô thành phẩm CÒN TỒN, chưa có HSD", [r["batch"] for r in ds["rows"]] == ["SEN-290926"],
     ds["rows"])
kiem("gợi ý HSD = NSX + 9 tháng", ds["rows"][0]["goi_y"] == "2027-06-29")
kiem("đếm lô đã hết hàng chưa có HSD", ds["het_hang"] == 1)
ds = L.danh_sach(ca_het_hang=1)
kiem("bật 'lô đã hết hàng': thêm lô hết hàng, NSX trống thì lấy ngày tạo lô",
     [(r["batch"], r["nsx"], r["co_nsx"]) for r in ds["rows"]]
     == [("SEN-290926", "2026-09-29", True), ("SEN-150926", "2026-09-15", False)], ds["rows"])
kq = L.dat_hsd(json.dumps([{"batch": "SEN-290926", "hsd": "2027-06-30"},
                           {"batch": "SEN-HSD010727", "hsd": "2028-01-01"},
                           {"batch": "SEN-150926", "hsd": "2026-09-01"},
                           {"batch": "BOT-1", "hsd": "2027-01-01"}]))
kiem("ghi HSD cho lô trống", BATCH["SEN-290926"]["expiry_date"] == "2027-06-30" and kq["xong"] == 1, kq)
kiem("HSD trước ngày tạo lô (lô không có NSX) → từ chối", BATCH["SEN-150926"]["expiry_date"] is None)
kiem("lô đã có HSD → KHÔNG ghi đè", BATCH["SEN-HSD010727"]["expiry_date"] == "2027-07-01")
kiem("không phải thành phẩm → từ chối", BATCH["BOT-1"]["expiry_date"] is None)
kiem("… và nói ra từng lô không ghi được", len(kq["loi"]) == 3, kq["loi"])
VAI.clear(); VAI.add("SX Ghi So")
_, loi = thu(lambda: L.dat_hsd("[]"))
kiem("người ngoài thủ kho / quản lý không dùng được thẻ", loi is not None)
VAI.clear(); VAI.add("SX Thu Kho")
kiem("thẻ có quyền: thủ kho + quản lý", R.CARD_ROLES["lohsd"] == ["SX Thu Kho", "SX Quan Ly"]
     and "lohsd" in R.VIEW_CARDS["nhapkho"] and "lohsd" in R.VIEW_CARDS["quanly"])
sh = open("sx/public/sx/shell.js", encoding="utf-8").read()
kiem("shell biết thẻ lohsd", "lohsd: '/assets/sx/sx/cards/lohsd.js'" in sh)

print("\n-- màn nhập kho: mỗi (mã, HSD) một dòng --")
js = open("sx/public/sx/cards/nhapkhotp.js", encoding="utf-8").read()
kiem("thêm mã đã có dòng → hỏi sửa dòng nào hay thêm dòng HSD khác",
     "+ DÒNG HSD KHÁC" in js and "function themItem(item)" in js)
kiem("bấm 'vừa vào hộp' thêm đủ các dòng theo HSD", "function themTuVaoHop(d)" in js
     and "chiaCua(d)" in js)
kiem("tổng 'đã ghi' của một mã cộng mọi dòng của mã", "rows || []).filter((x) => x.item === d.item)" in js)
tx = open("sx/public/sx/cards/truyxuat.js", encoding="utf-8").read()
kiem("truy xuất: lô thành phẩm hiện HSD thay mã lô (ẩn mã lô)",
     "x.la_tp && x.hsd" in tx and "l.la_tp && l.hsd" in tx)

print()
if hong:
    print(f"LOHSD-HỎNG ({hong})")
    sys.exit(1)
print("LOHSD-OK")
