"""D114 — HSD cho lô thành phẩm lúc nhập kho.

Trước D114 lô TP vào kho không có hạn dùng: Batch.expiry_date trống, báo cáo cận
date / xuất FEFO / tem lô đều mù. Hỏng theo hướng im lặng:
  · duyệt được phiếu mà lô không có HSD → lại như cũ, không ai thấy;
  · sửa số đếm (sua_phieu, tải từ vào hộp) làm rơi mất HSD thủ kho đã gõ;
  · HSD gõ không ghi được vào Batch (lô mới, hoặc lô dùng lại sau khi huỷ);
  · mặc định tính sai (không theo Shelf Life, hoặc bịa khi mã chưa khai).

Nạp sx/api/khotp.py, sx/api/mfg.py và controller SX Phieu Nhap TP THẬT; frappe giả.
Phần JS (congNgay / congThang) chạy bằng node trên đúng mã trong nhapkhotp.js.
Chạy: python3 scripts/test-hsd.py   (verify.sh gọi sẵn)
"""

import datetime as dt
import importlib.util
import json
import os
import re
import subprocess
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

PHIEU = {}
SHELF = {"TP-SEN": 180, "TP-CU": 0}
BATCH = {}              # batch_id -> dict
LO_GOI = []             # các lần on_submit gọi tao_batch
VAI = {"SX Thu Kho"}


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


class PhieuDoc(Doc):
    def insert(self):
        self["name"] = f"PN-{len(PHIEU) + 1}"
        self.setdefault("docstatus", 0)
        P.SXPhieuNhapTP.validate(self)
        PHIEU[self["name"]] = Doc(json.loads(json.dumps(self)), dong=[Doc(r) for r in self["dong"]])
        return self

    def save(self):
        for i, r in enumerate(self["dong"], 1):
            r["idx"] = i
        P.SXPhieuNhapTP.validate(self)
        PHIEU[self["name"]] = PhieuDoc(self, dong=[Doc(r) for r in self["dong"]])
        return self


class BatchDoc(Doc):
    def insert(self):
        self["name"] = self["batch_id"]
        BATCH[self["name"]] = dict(self)
        return self


def get_doc(d, n=None):
    if isinstance(d, dict):
        return BatchDoc(d)
    p = PHIEU[n]
    return PhieuDoc(p, dong=[Doc(r) for r in p["dong"]])    # bản sao như Frappe


def get_all(d, filters=None, fields=None, pluck=None, **k):
    return []


def _get_value(d, f, field=None, **k):
    if d == "Batch":
        b = BATCH.get(f)
        if not b:
            return None
        if isinstance(field, list):
            return tuple(b.get(x) for x in field)
        return b.get(field)
    return None


def _set_value(d, n, k, v=None, **kw):
    if d == "Batch":
        BATCH[n].update(k if isinstance(k, dict) else {k: v})


class Meta:
    def get_field(self, f):
        return True


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, title=None: (_ for _ in ()).throw(Loi(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.msgprint = lambda *a, **k: None
frappe.session = types.SimpleNamespace(user="thukho@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_doc = get_doc
frappe.get_meta = lambda d: Meta()
frappe.get_cached_value = lambda d, n, f=None: (
    SHELF.get(n, 0) if f == "shelf_life_in_days" else ("TP" if f == "has_batch_no" else None))
frappe.new_doc = lambda d: PhieuDoc(doctype=d, dong=[])
frappe.log_error = lambda **k: None
frappe.get_traceback = lambda: ""
frappe.db = types.SimpleNamespace(get_value=_get_value, set_value=_set_value,
                                  exists=lambda d, n=None: d == "Batch" and n in BATCH)
frappe.__dict__["_"] = lambda s: s


def _getdate(x=None):
    if isinstance(x, dt.date):
        return x
    return dt.date.fromisoformat(str(x)[:10])


fu = types.ModuleType("frappe.utils")
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.cint = lambda v: int(float(v or 0))
fu.getdate = _getdate
fu.nowdate = lambda: "2026-10-06"
fu.add_days = lambda d, n: _getdate(d) + dt.timedelta(days=n)
fu.now_datetime = lambda: "2026-10-06 10:00:00"
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
ut = types.ModuleType("sx.utils")
ut.get_bom_active = lambda i: "BOM-" + i
ut.get_settings = lambda: Doc(kho_tp="TP", cong_ty="C", kho_nvl="NVL")
ut.items_tp = lambda *a, **k: [Doc(name=i, item_name=i, stock_uom="Hộp",
                                   shelf_life_in_days=s) for i, s in SHELF.items()]
ut.nhom_tp = lambda: []
ut.sinh_ma_lo = lambda item, ngay: f"{item}-{_getdate(ngay):%d%m%y}"
ut.cho_phep_ton_am = lambda: False
ut.nho = lambda ten: {}   # D120: bộ nhớ request — test giả không nhớ
ut.nap_bom = lambda items: {i: ut.get_bom_active(i) for i in (items or [])} if hasattr(ut, "get_bom_active") else {}
ut.ton_bin = lambda items, kho: {}
sys.modules["sx.utils"] = ut


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


R = nap("sx.config.roles", "sx/config/roles.py")
M = nap("sx.api.mfg", "sx/api/mfg.py")
K = nap("sx.api.khotp", "sx/api/khotp.py")
P = nap("sx.sx.doctype.sx_phieu_nhap_tp.sx_phieu_nhap_tp",
        "sx/sx/doctype/sx_phieu_nhap_tp/sx_phieu_nhap_tp.py")
# Đường đi tới tồn kho (WO/SE/kiểm tồn) không phải việc của test này.
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
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


def thu(fn):
    try:
        return fn(), None
    except Loi as e:
        return None, str(e)


def phieu(*dong, ngay="2026-10-06"):
    d = [Doc(item=i, ten=i, so_lap=so, so_dem=so, idx=k, **x)
         for k, (i, so, x) in enumerate(dong, 1)]
    return P.SXPhieuNhapTP(name="PN-T", docstatus=0, ngay=ngay, kho_dich="TP", dong=d)


print("-- HSD mặc định = ngày nhập + Shelf Life --")
kiem("có Shelf Life 180 → +180 ngày", P.hsd_goi_y("TP-SEN", "2026-10-06") == "2027-04-04",
     P.hsd_goi_y("TP-SEN", "2026-10-06"))
kiem("chưa khai Shelf Life → None, không bịa", P.hsd_goi_y("TP-CU", "2026-10-06") is None)
kiem("danh mục TP kèm số ngày hạn dùng cho màn hình",
     {x["item"]: x["han_dung"] for x in K.danh_muc_tp()["rows"]} == {"TP-SEN": 180, "TP-CU": 0})

print("\n-- validate: HSD phải SAU ngày nhập --")
_, loi = thu(lambda: P.SXPhieuNhapTP.validate(phieu(("TP-SEN", 10, {"hsd": "2026-10-06"}))))
kiem("HSD = ngày nhập → chặn", bool(loi), loi or "")
_, loi = thu(lambda: P.SXPhieuNhapTP.validate(phieu(("TP-SEN", 10, {"hsd": "2026-10-01"}))))
kiem("HSD trước ngày nhập → chặn", bool(loi))
_, loi = thu(lambda: P.SXPhieuNhapTP.validate(phieu(("TP-SEN", 10, {"hsd": "2027-01-01"}))))
kiem("HSD sau ngày nhập → qua", loi is None, loi or "")

print("\n-- duyệt: dòng nhận > 0 phải có HSD --")
p = phieu(("TP-SEN", 10, {}), ("TP-CU", 5, {}))
_, loi = thu(lambda: P.SXPhieuNhapTP.before_submit(p))
kiem("mã chưa khai Shelf Life, chưa gõ HSD → chặn", bool(loi) and "TP-CU" in loi, loi or "")
kiem("… và chỉ ra cách gỡ (nhập theo bao bì / khai Shelf Life)",
     bool(loi) and "Shelf Life In Days" in loi and "bao bì" in loi)
kiem("… không kể tên dòng đã có mặc định", bool(loi) and "TP-SEN" not in loi)
p = phieu(("TP-SEN", 10, {}), ("TP-CU", 5, {"hsd": "2027-03-01"}), ("TP-CU", 0, {}))
_, loi = thu(lambda: P.SXPhieuNhapTP.before_submit(p))
kiem("gõ tay HSD cho mã chưa khai; dòng số 0 không cần HSD → duyệt qua", loi is None, loi or "")
kiem("dòng để trống được điền HSD mặc định", p.dong[0].hsd == "2027-04-04", p.dong[0].hsd)
kiem("HSD gõ tay giữ nguyên, không bị mặc định đè", p.dong[1].hsd == "2027-03-01")

print("\n-- duyệt ghi NSX + HSD vào Batch --")
BATCH.clear()
M.dam_bao_quan_ly_lo = lambda item: True
_tao_se = types.SimpleNamespace(name="SE-1")
M.tao_wo = lambda *a, **k: types.SimpleNamespace(name="WO-1")
M.tao_se_manufacture = lambda *a, **k: _tao_se
P.SXPhieuNhapTP.on_submit(p)
kiem("lô mới có expiry_date = HSD dòng",
     BATCH.get("TP-SEN-061026", {}).get("expiry_date") == "2027-04-04", str(BATCH))
kiem("lô mới có manufacturing_date = ngày nhập",
     BATCH.get("TP-SEN-061026", {}).get("manufacturing_date") == "2026-10-06")
kiem("dòng gõ tay → đúng HSD gõ tay", BATCH.get("TP-CU-061026", {}).get("expiry_date") == "2027-03-01")

# Lô dùng lại sau khi huỷ phiếu (sinh_ma_lo chỉ trả lô CHƯA DÙNG): HSD lần mới.
M.tao_batch("TP-SEN", "TP-SEN-061026", nsx="2026-10-06", hsd="2027-05-01")
kiem("lô dùng lại → HSD cập nhật theo lần nhập mới",
     BATCH["TP-SEN-061026"]["expiry_date"] == "2027-05-01")
M.tao_batch("TP-SEN", "TP-SEN-061026")
kiem("gọi không có HSD (bột nền, BTP) → không xoá HSD đang có",
     BATCH["TP-SEN-061026"]["expiry_date"] == "2027-05-01")

print("\n-- sửa phiếu không làm rơi HSD --")
PHIEU.clear()
VAI.clear(); VAI.add("SX Thu Kho")
nhap = PhieuDoc(name="PN-1", docstatus=0, ngay="2026-10-06", kho_dich="TP",
                dong=[Doc(item="TP-SEN", ten="Sen", so_lap=10, so_dem=10, idx=1, hsd="2027-02-01"),
                      Doc(item="TP-CU", ten="Cũ", so_lap=5, so_dem=5, idx=2)])
PHIEU["PN-1"] = nhap
ct = K.chi_tiet_phieu("PN-1")
d = {x["item"]: x for x in ct["dong"]}
kiem("chi tiết trả HSD đã gõ", d["TP-SEN"]["hsd"] == "2027-02-01")
kiem("chi tiết trả HSD mặc định để màn hình hiện sẵn", d["TP-SEN"]["hsd_goi_y"] == "2027-04-04")
kiem("mã chưa khai → hsd và hsd_goi_y đều None (màn hình báo thiếu)",
     d["TP-CU"]["hsd"] is None and d["TP-CU"]["hsd_goi_y"] is None)

ct = K.sua_phieu("PN-1", json.dumps([{"item": "TP-SEN", "so_dem": 9},
                                     {"item": "TP-CU", "so_dem": 5}]))
d = {x["item"]: x for x in ct["dong"]}
kiem("client cũ không gửi `hsd` → giữ HSD cũ", d["TP-SEN"]["hsd"] == "2027-02-01", str(d["TP-SEN"]))
ct = K.sua_phieu("PN-1", json.dumps([{"item": "TP-SEN", "so_dem": 9, "hsd": None},
                                     {"item": "TP-CU", "so_dem": 5, "hsd": "2027-06-30"}]))
d = {x["item"]: x for x in ct["dong"]}
kiem("gửi hsd rỗng → về mặc định", d["TP-SEN"]["hsd"] is None)
kiem("gửi hsd mới → lưu", d["TP-CU"]["hsd"] == "2027-06-30")
_, loi = thu(lambda: K.sua_phieu("PN-1", json.dumps([{"item": "TP-CU", "so_dem": 5,
                                                      "hsd": "2026-09-01"}])))
kiem("gửi HSD trước ngày nhập → chặn", bool(loi))

# Tải từ vào hộp dựng lại dòng — HSD đã gõ phải sống sót.
K.tran_con_lai = lambda tu, den, tru=None: {"TP-CU": 7}
ct = K.tai_tu_vao_hop("PN-1")
d = {x["item"]: x for x in ct["dong"]}
kiem("tải từ vào hộp → giữ HSD của mã được tải lại", d["TP-CU"]["hsd"] == "2027-06-30",
     str(d["TP-CU"]))

# Huỷ & lập lại chép cả HSD — lý do huỷ thường là đếm sai, không phải HSD sai.
cu = Doc(name="PN-9", ngay="2026-10-06", kho_dich="TP",
         dong=[Doc(item="TP-CU", so_lap=5, so_dem=5, hsd="2027-06-30")])
PHIEU.clear()
moi = K._lap_lai_tu(cu)
kiem("huỷ & lập lại → phiếu nháp mới giữ HSD", PHIEU[moi]["dong"][0].get("hsd") == "2027-06-30")

print("\n-- JS: tính ngày trên máy (dòng vừa thêm, nút +tháng) --")
src = open("sx/public/sx/cards/nhapkhotp.js", encoding="utf-8").read()
ham = "\n".join(re.search(r"export function %s\(.*?\n}\n" % t, src, re.S).group(0)
                .replace("export ", "") for t in ("congNgay", "congThang"))
js = ham + """
const ra = {
  n180: congNgay('2026-10-06', 180), n0: congNgay('2026-10-06', 0),
  nNull: congNgay('2026-10-06', undefined), nhuan: congNgay('2028-02-28', 1),
  t6: congThang('2026-10-06', 6), cuoi: congThang('2026-08-31', 6),
  nam: congThang('2026-12-15', 12), t3: congThang('2026-11-30', 3),
};
console.log(JSON.stringify(ra));
"""
out = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True,
                                check=True).stdout)
kiem("+180 ngày khớp server", out["n180"] == "2027-04-04", out["n180"])
kiem("Shelf Life 0 / thiếu → null (không bịa)", out["n0"] is None and out["nNull"] is None)
kiem("năm nhuận", out["nhuan"] == "2028-02-29")
kiem("+6 tháng", out["t6"] == "2027-04-06")
kiem("31/08 + 6 tháng → 28/02 (không tràn sang tháng 3)", out["cuoi"] == "2027-02-28", out["cuoi"])
kiem("+12 tháng qua năm", out["nam"] == "2027-12-15")
kiem("30/11 + 3 tháng → 28/02", out["t3"] == "2027-02-28", out["t3"])

print()
if hong:
    print(f"HSD-HỎNG ({hong})")
    sys.exit(1)
print("HSD-OK")
