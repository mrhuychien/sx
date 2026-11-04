"""D101 — kho nhận vượt số chấm vào hộp: ghi nợ thay vì chặn; công nhật chấm riêng.

Vì sao phải có bài này: cả hai thay đổi đụng tới TIỀN và TỒN KHO, và hỏng theo
cách im lặng:

  · Công nhật lọt vào lương khoán — một người tự dưng có thêm hộp, hoặc dòng công
    nhật sinh "nợ đơn giá" cho một thứ không bao giờ trả khoán.
  · Công nhật KHÔNG vào trần nhập kho — thì mọi hộp công nhật đều thành nợ oan.
  · Nới chặn mà quên ghi nợ — kho nhận 300, chấm 250, 50 hộp chấm sót biến mất.
  · Nợ không tự trừ khi chấm bù, hoặc trừ sai thứ tự — sổ nợ đầy thứ đã xong, rồi
    không ai đọc nữa.

Nạp controller SX Bang Vao Hop, SX Phieu Nhap TP, SX No Vao Hop, sx/api/khotp.py,
sx/api/nogia.py, sx/api/portal.py (luu_bang_vao_hop) và sx/api/chot.py
(_ghi_luong_khoan) THẬT; frappe và chứng từ kho là giả.

Chạy: python3 scripts/test-novaohop.py   (verify.sh gọi sẵn)
"""

import ast
import importlib.util
import json
import os
import re
import sys
import types
from datetime import date, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

HOM_NAY = date(2026, 9, 29)
BANG = {}          # SX Bang Vao Hop: name -> doc
NGAY = []          # SX Ngay San Xuat
PHIEU = []         # SX Phieu Nhap TP (đã duyệt / nháp)
NO = []            # SX No Vao Hop
NO_GIA = []        # SX No Don Gia (D206: trỏ vào bảng vào hộp)
VAI = {"SX Quan Ly"}
MSG = []


class Loi(Exception):
    pass


class _dict(dict):
    """Như frappe._dict: thuộc tính và .get() là CÙNG một chỗ."""
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

    def set(self, k, v):
        self[k] = v

    def append(self, k, v):
        r = Doc(v)                   # như Frappe: trả lại chính dòng vừa thêm
        self.setdefault(k, []).append(r)
        return r

    def db_set(self, k, v=None, **kw):
        if isinstance(k, dict):
            self.update(k)
        else:
            self[k] = v


class NoDoc(Doc):
    def insert(self, **kw):
        self["name"] = f"NV-{len(NO) + 1:04d}"
        NO.append(self)
        return self

    def save(self, **kw):
        NVH.SXNoVaoHop.validate(self)
        next(h for h in NO if h["name"] == self["name"]).update(self)
        return self


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "in" and x not in m:
                return False
            if op == ">=" and not str(x) >= str(m):
                return False
            if op == "<" and not (x or 0) < m:
                return False
            if op == "between" and not (str(m[0]) <= str(x) <= str(m[1])):
                return False
        elif str(x) != str(v):
            return False
    return True


def _hang(dt):
    if dt == "SX Ngay San Xuat":
        return NGAY
    if dt == "SX Bang Vao Hop":
        return list(BANG.values())
    if dt == "SX Bang Vao Hop Item":
        return [dict(r, parent=b["name"], parenttype="SX Bang Vao Hop")
                for b in BANG.values() for r in b["dong"]]
    if dt == "SX Phieu Nhap TP":
        return PHIEU
    if dt == "SX Phieu Nhap TP Item":
        return [dict(r, parent=p["name"], parenttype="SX Phieu Nhap TP")
                for p in PHIEU for r in p["dong"]]
    if dt == "SX No Vao Hop":
        return NO
    if dt == "SX No Don Gia":
        return NO_GIA
    return []


def get_all(dt, filters=None, fields=None, pluck=None, order_by=None, **k):
    ra = [Doc(h) for h in _hang(dt) if _khop(h, filters)]
    if dt == "SX No Vao Hop" and order_by:
        ra.sort(key=lambda h: (str(h.get("ngay")), h.get("name")))
    return [h.get(pluck) for h in ra] if pluck else ra


def _get_value(dt, f, field=None, **kw):
    if dt == "SX Phieu Nhap TP":
        p = next((x for x in PHIEU if x["name"] == f), None)
        return p.get(field) if p else None
    if dt == "SX Ngay San Xuat":
        return next((x.get(field) for x in NGAY if x["name"] == f), None)
    if dt == "Employee":
        return {"NV1": "An", "NV2": "Bình"}.get(f)
    if isinstance(f, dict):
        h = next(iter(get_all(dt, f)), None)
        return h.get(field) if h else None
    return None


def _set_value(dt, name, vals, v=None, **kw):
    vals = vals if isinstance(vals, dict) else {vals: v}
    if dt == "SX No Vao Hop":
        next(h for h in NO if h["name"] == name).update(vals)
    elif dt == "SX No Don Gia":
        next(h for h in NO_GIA if h["name"] == name).update(vals)


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.msgprint = lambda *a, **k: MSG.append(a[0] if a else k.get("msg"))
# D114: mã hàng có Shelf Life — HSD tự điền, không chặn duyệt (test-hsd.py lo phần đó).
frappe.get_cached_value = lambda dt, n, f=None: 180 if f == "shelf_life_in_days" else None
frappe.session = types.SimpleNamespace(user="ql@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.parse_json = lambda x: json.loads(x) if isinstance(x, str) else x
frappe.log_error = lambda *a, **k: None


def _get_doc(x, n=None):
    if isinstance(x, dict):
        return NoDoc(x) if x.get("doctype") == "SX No Vao Hop" else Doc(x)
    if x == "SX No Vao Hop":
        return NoDoc(next(h for h in NO if h["name"] == n))
    if x == "SX Bang Vao Hop":
        return BANG[n]
    raise KeyError(x)


frappe.get_doc = _get_doc
GHI_SINGLE = []
O_SETTINGS = {"no_vh_tu_ngay", "no_vh_mang_sang"}       # ô đã migrate
frappe.get_meta = lambda dt: types.SimpleNamespace(has_field=lambda f: dt == "SX Settings" and f in O_SETTINGS)
frappe.clear_document_cache = lambda dt, n=None: GHI_SINGLE.append(("xoá cache", dt, n))
frappe.db = types.SimpleNamespace(
    get_value=_get_value, set_value=_set_value,
    exists=lambda dt, f=None: next(iter(get_all(dt, f)), None) and "x",
    set_single_value=lambda dt, f, v: (SETTINGS.update({f: v}), GHI_SINGLE.append(("ghi", dt, f, v))))
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.cint = lambda v: int(float(v or 0))
fu.getdate = lambda x=None: (x if isinstance(x, date) else
                             date.fromisoformat(str(x)[:10]) if x else HOM_NAY)
fu.nowdate = lambda: str(HOM_NAY)
fu.add_days = lambda d, n: fu.getdate(d) + timedelta(days=n)
fu.now_datetime = lambda: "2026-09-29 10:00:00"
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
BANG_GIA = {("TP-A", ""): 1000.0}
ut.don_gia_ap_dung = lambda ngay=None: dict(BANG_GIA)
ut.GIA_TAM = 1                                    # D224: giá tạm 1 đồng = chưa có giá (như sx.utils)
ut.la_gia_tam = lambda g: float(g or 0) <= ut.GIA_TAM
ut.gia_hien = lambda g: 0.0 if ut.la_gia_tam(g) else float(g)


def _tra_don_gia(b, sp, cl=None):
    g = b[(sp, cl)] if cl and (sp, cl) in b else b.get((sp, ""))
    return None if g is None or ut.la_gia_tam(g) else g


ut.tra_don_gia = _tra_don_gia
ut.bang_don_gia = lambda ngay=None: "BG-1"
ut.get_bom_active = lambda item: "BOM-" + item
SETTINGS = {}      # D230: mốc tính nợ vào hộp + phần mang sang (SX Settings)
ut.get_settings = lambda: Doc({"cong_ty": "RVHG", "kho_nvl": "NVL", "kho_btp": "BTP",
                               "kho_tp": "TP", **SETTINGS})
ut.items_tp = lambda *a, **k: []
ut.nhom_tp = lambda: []
ut.sinh_ma_lo = lambda item, ngay: f"{item}-LO"
ut.ma_lo_hsd = lambda item, hsd: f"{item}-LO"      # W05: lô theo HSD — không phải chủ đề bài này
ut.cho_phep_ton_am = lambda: True
for ten in ("cach_lam_cua", "dat_ten_hien_thi", "get_dau_items", "topo_rank_by_bom",
            "loai_phieu_kho"):
    setattr(ut, ten, lambda *a, **k: None)
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
SE = []
mfg.tao_batch = lambda item, lo, **k: lo
mfg.tao_wo = lambda *a, **k: Doc(name=f"WO-{len(SE)}", item=a[1])
mfg.tao_se_manufacture = lambda wo, qty, batch, **k: SE.append(qty) or Doc(name=f"SE-{len(SE)}")
mfg.tao_se_nhap_thang = lambda *a, **k: Doc(name="SE-X")
mfg.cancel_doc = lambda dt, n, log=None: None
mfg.loai_phieu_kho = lambda *a: None
sys.modules["sx.api.mfg"] = mfg
# D137 (W08): chốt BM.08.04 có test riêng (test-xuatxuong) — ở đây coi như tắt.
_xx = types.ModuleType("sx.api.xuatxuong")
_xx.chan_nhap_kho = lambda phieu: None
_xx._bat = lambda s=None: False
_xx.tu_ngay = lambda s=None: None
_xx.trang_thai_cac_lo = lambda cap: {}
sys.modules["sx.api.xuatxuong"] = _xx


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


R = nap("sx.config.roles", "sx/config/roles.py")
BVH = nap("sx.sx.doctype.sx_bang_vao_hop.sx_bang_vao_hop",
          "sx/sx/doctype/sx_bang_vao_hop/sx_bang_vao_hop.py")
NG = nap("sx.api.nogia", "sx/api/nogia.py")
K = nap("sx.api.khotp", "sx/api/khotp.py")
C = nap("sx.api.chot", "sx/api/chot.py")
PT = nap("sx.api.portal", "sx/api/portal.py")
P = nap("sx.sx.doctype.sx_phieu_nhap_tp.sx_phieu_nhap_tp",
        "sx/sx/doctype/sx_phieu_nhap_tp/sx_phieu_nhap_tp.py")
NVH = nap("sx.sx.doctype.sx_no_vao_hop.sx_no_vao_hop",
          "sx/sx/doctype/sx_no_vao_hop/sx_no_vao_hop.py")

# Không kiểm ở bài này: trùng bảng (validate_duy_nhat) và tồn nguyên liệu lúc duyệt.
BVH.SXBangVaoHop.validate_duy_nhat = lambda self: None
P.SXPhieuNhapTP.kiem_ton_nguyen_lieu = lambda self: None


class BangMoi(BVH.SXBangVaoHop):
    def save(self):
        BVH.SXBangVaoHop.validate(self)
        BANG[self["name"]] = self
        return self

    def is_new(self):
        return self["name"] not in BANG

    def delete(self, **k):
        # Như frappe.delete_doc: on_trash TRƯỚC, rồi mới kiểm tra liên kết (D206).
        BVH.SXBangVaoHop.on_trash(self)
        lk = [x["name"] for x in NO_GIA if x.get("bang_vao_hop") == self["name"]]
        if lk:
            raise Loi(f"Cannot delete or cancel because SX Bang Vao Hop {self['name']} is linked with "
                      f"SX No Don Gia {lk[0]}")
        BANG.pop(self["name"])


hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


def thu(fn):
    try:
        fn()
        return None
    except Loi as e:
        return str(e) or type(e).__name__


def bang_vh(*dong, ngay=HOM_NAY, ten="NSX-1"):
    NGAY.append(Doc(name=ten, ngay=ngay, docstatus=0))
    b = BVH.SXBangVaoHop(Doc(name=f"BVH-{ten}", ngay_sx=ten, docstatus=0,
                             dong=[Doc(r, idx=i + 1) for i, r in enumerate(dong)]))
    BVH.SXBangVaoHop.validate(b)
    BANG[b.name] = b
    return b


def lam_sach():
    for x in (NGAY, PHIEU, NO, MSG, SE, NO_GIA, GHI_SINGLE):
        x.clear()
    BANG.clear()
    SETTINGS.clear()
    VAI.clear(); VAI.add("SX Quan Ly")


# ═══ 1. Dòng công nhật trong bảng vào hộp ════════════════════════════════
print("-- bảng vào hộp: dòng công nhật --")
lam_sach()
b = bang_vh({"nhan_vien": "NV1", "san_pham": "TP-A", "so_hop": 100},
            {"cong_nhat": 1, "nhan_vien": "NV2", "san_pham": "TP-A", "so_hop": 50},
            {"cong_nhat": 1, "san_pham": "TP-MOI", "so_hop": 20})
cn = [r for r in b.dong if r.cong_nhat]
kiem("dòng công nhật KHÔNG gắn người (kể cả khi gửi lên có tên)",
     all(r.nhan_vien is None for r in cn))
kiem("công nhật tính vào tổng sản lượng", b.tong_hop == 170, str(b.tong_hop))
kiem("công nhật không có tiền khoán", b.tong_tien == 100000.0 and all(
    r.don_gia == 0 and r.thanh_tien == 0 for r in cn), str(b.tong_tien))
kiem("công nhật mã chưa có giá KHÔNG báo thiếu đơn giá", not MSG, str(MSG))
kiem("công nhật xếp cuối bảng", [bool(r.cong_nhat) for r in b.dong] == [False, True, True])
kiem("dòng khoán thiếu người → chặn",
     "chưa chọn công nhân" in (thu(lambda: bang_vh(
         {"san_pham": "TP-A", "so_hop": 5}, ten="NSX-9")) or ""))

print("\n-- lương khoán, nợ đơn giá bỏ qua công nhật --")
kiem("công nhật mã chưa có giá không sinh nợ đơn giá",
     set(NG.gom_thieu_gia(b.dong, ut.don_gia_ap_dung())) == set())
DA_GHI = {}


class PL(Doc):
    def save(self):
        DA_GHI[self["employee"]] = self
        return self


C._phieu_luong_thang = lambda nv, ngay: PL(employee=nv, chi_tiet=[], dong=[])
C._ghi_luong_khoan(Doc(ngay=HOM_NAY), b)
kiem("phiếu lương chỉ có người làm khoán, không có ai vì công nhật",
     set(DA_GHI) == {"NV1"}, str(set(DA_GHI)))
kiem("… và số hộp khoán không cộng lẫn công nhật",
     [r.so_luong for r in DA_GHI["NV1"].chi_tiet] == [100])

print("\n-- API màn Ghi hộp: mã giả CONG_NHAT ↔ cờ cong_nhat --")
lam_sach()
NGAY.append(Doc(name="NSX-2", ngay=HOM_NAY, docstatus=0, chot_vaohop=0))
PT._chan_neu_chot = lambda *a: None
MOI = {}


def _new_doc(dt):
    d = BangMoi(Doc(name="BVH-NSX-2", dong=[], an_ca=[]))
    MOI["d"] = d
    return d


frappe.new_doc = _new_doc
VAI.clear(); VAI.add("SX Vao Hop")
kq = PT.luu_bang_vao_hop("NSX-2", json.dumps([
    {"nhan_vien": "NV1", "san_pham": "TP-A", "so_hop": 10},
    {"nhan_vien": BVH.CONG_NHAT, "san_pham": "TP-A", "so_hop": 7}]),
    an_ca=json.dumps([{"nhan_vien": BVH.CONG_NHAT, "an_ca": 1},
                      {"nhan_vien": "NV1", "an_ca": 1}]))
luu = MOI["d"]
kiem("lưu: mã giả thành cờ cong_nhat, không lưu người",
     [(r.nhan_vien, r.cong_nhat) for r in luu.dong] == [("NV1", 0), (None, 1)])
kiem("lưu: công nhật không được chấm ăn ca", [r.nhan_vien for r in luu.an_ca] == ["NV1"])
kiem("trả về: dòng công nhật mang lại mã giả cho màn hình",
     [(r["nhan_vien"], r["cong_nhat"]) for r in kq["dong"]] == [("NV1", 0), (BVH.CONG_NHAT, 1)])

print("\n-- xoá dòng CUỐI của một ngày (D106) --")
kq = PT.luu_bang_vao_hop("NSX-2", json.dumps([]), an_ca=json.dumps([{"nhan_vien": "NV1", "an_ca": 1}]))
kiem("xoá hết dòng nhưng còn chấm ăn ca → vẫn lưu được (bảng không bắt buộc có dòng)",
     kq and kq["dong"] == [] and len(BANG["BVH-NSX-2"].an_ca) == 1, str(kq))
kq = PT.luu_bang_vao_hop("NSX-2", json.dumps([]), an_ca=json.dumps([]))
kiem("xoá hết dòng, không chấm ăn → xoá luôn bảng nháp, không báo lỗi",
     kq is None and "BVH-NSX-2" not in BANG, str(kq))
jd = json.load(open("sx/sx/doctype/sx_bang_vao_hop/sx_bang_vao_hop.json", encoding="utf-8"))
kiem("bảng 'Chi tiết' không còn bắt buộc (hết lỗi 'Data missing in table Chi tiết')",
     not next(f for f in jd["fields"] if f["fieldname"] == "dong").get("reqd"))

print("\n-- D206: xoá dòng cuối khi bảng có nợ đơn giá --")
lam_sach()
NGAY.append(Doc(name="NSX-2", ngay=HOM_NAY, docstatus=0, chot_vaohop=0))
VAI.clear(); VAI.add("SX Vao Hop")
kq = PT.luu_bang_vao_hop("NSX-2", json.dumps([{"nhan_vien": "NV1", "san_pham": "TP-MOI", "so_hop": 6}]))
BANG["BVH-NSX-2"]["docstatus"] = 0
for i, r in enumerate(BANG["BVH-NSX-2"].dong):
    r["name"] = f"R{i}"
# đồng bộ lương (D202) đã ghi nợ đơn giá cho TP-MOI, trỏ vào bảng; thêm một nợ cũ đã áp giá
NO_GIA += [Doc(name="NG-1", bang_vao_hop="BVH-NSX-2", ngay_sx="NSX-2", trang_thai="Chờ giá"),
           Doc(name="NG-0", bang_vao_hop="BVH-NSX-2", ngay_sx="NSX-2", trang_thai="Đã cập nhật")]
loi = thu(lambda: PT.luu_bang_vao_hop("NSX-2", json.dumps([]), biet=json.dumps(["R0"])))
kiem("xoá dòng cuối: không còn lỗi 'is linked with SX No Don Gia', bảng nháp bị xoá",
     loi is None and "BVH-NSX-2" not in BANG, loi or "")
kiem("… nợ đang chờ giá Đã huỷ; mọi nợ bỏ liên kết bảng, nợ đã áp giá giữ trạng thái",
     [(x.name, x.trang_thai, x.bang_vao_hop) for x in NO_GIA]
     == [("NG-1", "Đã huỷ", None), ("NG-0", "Đã cập nhật", None)], str(NO_GIA))
VAI.clear(); VAI.add("SX Quan Ly")

# ═══ 2. Nhập kho vượt số chấm → nợ, không chặn ═══════════════════════════
print("\n-- nhập kho vượt số chấm: ghi nợ, KHÔNG chặn --")
lam_sach()
bang_vh({"nhan_vien": "NV1", "san_pham": "TP-A", "so_hop": 200},
        {"cong_nhat": 1, "san_pham": "TP-A", "so_hop": 50})
NHAP = {"n": 0}


def phieu(*dong, ngay=HOM_NAY):
    NHAP["n"] += 1
    p = P.SXPhieuNhapTP(Doc(name=f"PN-{NHAP['n']}", ngay=ngay, docstatus=0, kho_dich="TP",
                            ds_se=None, dong=[Doc(r, idx=i + 1) for i, r in enumerate(dong)]))
    PHIEU.append(p)
    return p


def duyet(p):
    P.SXPhieuNhapTP.before_submit(p)
    p["docstatus"] = 1
    P.SXPhieuNhapTP.on_submit(p)
    return p


p = phieu({"item": "TP-A", "ten": "Bánh A", "so_dem": 240})
kiem("nhận đúng / dưới số chấm (khoán + công nhật = 250) → không nợ",
     thu(lambda: duyet(p)) is None and not NO)
p = phieu({"item": "TP-A", "ten": "Bánh A", "so_dem": 30})
loi = thu(lambda: duyet(p))
kiem("nhận VƯỢT → duyệt vẫn qua (không chặn như D70)", loi is None, loi or "")
kiem("phần vượt thành đúng một dòng nợ, đúng số (240+30−250 = 20)",
     len(NO) == 1 and NO[0].so_luong == 20 and NO[0].con_lai == 20, str(NO))
kiem("nợ trỏ về phiếu, mã, ngày; trạng thái Chờ chấm",
     (NO[0].phieu_nhap, NO[0].item, NO[0].trang_thai) == ("PN-2", "TP-A", "Chờ chấm"))
kiem("hàng vẫn vào kho theo số đếm", SE[-1] == 30)
# W05 (D131): hai dòng cùng mã là hai HSD (hai lô) — cùng HSD thì bị chặn gộp.
p = phieu({"item": "TP-B", "ten": "Bánh B", "so_dem": 12, "hsd": "2027-06-01"},
          {"item": "TP-B", "ten": "Bánh B", "so_dem": 3, "hsd": "2027-06-02"})
duyet(p)
nb = [x for x in NO if x.item == "TP-B"]
kiem("mã chưa chấm lần nào → cả số nhận thành nợ, gộp hai dòng cùng mã",
     len(nb) == 1 and nb[0].so_luong == 15, str(nb))

print("\n-- màn nhập kho biết trước phần vượt --")
p = phieu({"item": "TP-A", "so_dem": 5}, {"item": "TP-A", "so_dem": 4})
v = K.vuot_so_cham(p.ngay, p.dong, p.name)
kiem("phiếu nháp: phần vượt tính GỘP theo mã", v == {"TP-A": 9.0}, str(v))
PHIEU.remove(p)

# ═══ 3. Chấm bù → nợ tự trừ ══════════════════════════════════════════════
print("\n-- chấm bù: nợ tự trừ, nợ cũ trả trước --")
lam_sach()
bang_vh({"nhan_vien": "NV1", "san_pham": "TP-A", "so_hop": 100}, ngay=HOM_NAY - timedelta(days=3))
duyet(phieu({"item": "TP-A", "so_dem": 110}, ngay=HOM_NAY - timedelta(days=2)))
duyet(phieu({"item": "TP-A", "so_dem": 5}, ngay=HOM_NAY - timedelta(days=1)))
kiem("hai lần vượt → hai dòng nợ 10 + 5", [x.con_lai for x in NO] == [10, 5], str(NO))
K.doi_soat_no_vao_hop()
kiem("chưa ai chấm bù → nợ giữ nguyên", [x.con_lai for x in NO] == [10, 5])
BANG["BVH-NSX-1"].dong.append(Doc(cong_nhat=1, san_pham="TP-A", so_hop=12))
K.doi_soat_no_vao_hop()
kiem("chấm bù 12 (dòng CÔNG NHẬT) → nợ cũ đóng, nợ mới còn 3",
     [(x.trang_thai, x.con_lai) for x in NO] == [("Đã chấm bù", 0), ("Chờ chấm", 3)],
     str([(x.trang_thai, x.con_lai) for x in NO]))
BANG["BVH-NSX-1"].dong.append(Doc(nhan_vien="NV2", san_pham="TP-A", so_hop=3))
# D121: mở thẻ CHỈ ĐỌC — đối soát chạy ở hook lưu bảng vào hộp.
truoc = [(x.trang_thai, x.con_lai) for x in NO]
K.so_no_vao_hop()
kiem("mở thẻ sổ nợ không ghi gì vào database (chỉ đọc)",
     [(x.trang_thai, x.con_lai) for x in NO] == truoc)
K.doi_soat_sau_cham(BANG["BVH-NSX-1"])          # hook on_update của SX Bang Vao Hop
kiem("QC lưu bảng (chấm bù nốt 3) → hook trừ hết nợ, mở card là thấy sạch",
     not K.so_no_vao_hop()["nhom"])
kiem("… và nợ đã đóng trong sổ", all(x.trang_thai == "Đã chấm bù" for x in NO))
hk = open("sx/hooks.py", encoding="utf-8").read()
kiem("hook gắn vào lưu bảng vào hộp (đối soát nợ + đồng bộ lương D123)",
     '"SX Bang Vao Hop": {"on_update": ["sx.api.khotp.doi_soat_sau_cham",' in hk
     and '"sx.api.dongbo.sau_luu_bang"]' in hk)

print("\n-- huỷ phiếu nhập, bỏ qua --")
lam_sach()
p = duyet(phieu({"item": "TP-C", "so_dem": 8}))
P.SXPhieuNhapTP.on_cancel(p)
kiem("huỷ phiếu nhập → nợ của phiếu Đã huỷ", NO[0].trang_thai == "Đã huỷ")
duyet(phieu({"item": "TP-C", "so_dem": 6}))
n = NO[-1].name
VAI.clear(); VAI.add("SX Vao Hop")
kiem("QC xem được sổ nợ (để chấm bù)", len(K.so_no_vao_hop()["nhom"]) == 1)
kiem("QC KHÔNG có quyền bỏ qua", not K.so_no_vao_hop()["duoc_bo_qua"]
     and thu(lambda: K.bo_qua_no_vao_hop(n, "x")) is not None)
VAI.clear(); VAI.add("SX Thu Kho")
kiem("thủ kho không mở được sổ nợ vào hộp", thu(lambda: K.so_no_vao_hop()) is not None)
VAI.clear(); VAI.add("SX Quan Ly")
kiem("bỏ qua không lý do → chặn", "lý do" in (thu(lambda: K.bo_qua_no_vao_hop(n, " ")) or ""))
K.bo_qua_no_vao_hop(n, "hàng trả về nhập lại")
kiem("quản lý bỏ qua có lý do", (NO[-1].trang_thai, NO[-1].ly_do) == ("Bỏ qua", "hàng trả về nhập lại"))

# ═══ 3b. D203: công khoán chung ════════════════════════════════════════
print("\n-- D203: dòng công khoán chung trong bảng vào hộp --")
lam_sach()
b = bang_vh({"nhan_vien": "NV1", "san_pham": "TP-A", "so_hop": 100},
            {"khoan_chung": 1, "nhan_vien": "NV2", "san_pham": "TP-A", "so_hop": 30},
            {"cong_nhat": 1, "san_pham": "TP-A", "so_hop": 50},
            {"khoan_chung": 1, "san_pham": "TP-MOI", "so_hop": 4})
kc = [r for r in b.dong if r.khoan_chung]
kiem("dòng công khoán chung KHÔNG gắn người (kể cả khi gửi lên có tên)", all(r.nhan_vien is None for r in kc))
kiem("công khoán chung tính tiền khoán theo đơn giá (khác công nhật)",
     [(r.san_pham, r.don_gia, r.thanh_tien) for r in kc] == [("TP-A", 1000.0, 30000.0), ("TP-MOI", 0, 0)]
     and b.tong_tien == 130000.0 and b.tong_hop == 184, str([(r.san_pham, r.thanh_tien) for r in kc]))
kiem("thứ tự: người → công khoán chung → công nhật",
     [("kc" if r.khoan_chung else "cn" if r.cong_nhat else r.nhan_vien) for r in b.dong] == ["NV1", "kc", "kc", "cn"])
kiem("dòng vừa công nhật vừa công khoán chung → chặn", "chỉ được một" in (thu(lambda: bang_vh(
    {"cong_nhat": 1, "khoan_chung": 1, "san_pham": "TP-A", "so_hop": 5}, ten="NSX-9")) or ""))
t = NG.gom_thieu_gia(b.dong, ut.don_gia_ap_dung())
kiem("công khoán chung mã chưa có giá → VÀO sổ nợ đơn giá (tiền khoán của tổ còn phải trả)",
     set(t) == {("TP-MOI", "")} and t[("TP-MOI", "")]["so_hop"] == 4, str(t))
DA_GHI.clear()
C._ghi_luong_khoan(Doc(ngay=HOM_NAY), b)
kiem("phiếu lương chỉ có người làm khoán — công khoán chung không vào phiếu lương của ai",
     set(DA_GHI) == {"NV1"} and [r.so_luong for r in DA_GHI["NV1"].chi_tiet] == [100], str(set(DA_GHI)))

print("\n-- D203: API màn Ghi hộp: mã giả KHOAN_CHUNG ↔ cờ khoan_chung --")
lam_sach()
NGAY.append(Doc(name="NSX-2", ngay=HOM_NAY, docstatus=0, chot_vaohop=0))
PT._chan_neu_chot = lambda *a: None
VAI.clear(); VAI.add("SX Vao Hop")
kq = PT.luu_bang_vao_hop("NSX-2", json.dumps([
    {"nhan_vien": "NV1", "san_pham": "TP-A", "so_hop": 10},
    {"nhan_vien": BVH.KHOAN_CHUNG, "san_pham": "TP-A", "so_hop": 7}]),
    an_ca=json.dumps([{"nhan_vien": BVH.KHOAN_CHUNG, "an_ca": 1}]))
luu = MOI["d"]
kiem("lưu: mã giả thành cờ khoan_chung, không lưu người, không phải công nhật",
     [(r.nhan_vien, r.cong_nhat, r.khoan_chung) for r in luu.dong] == [("NV1", 0, 0), (None, 0, 1)],
     str([(r.nhan_vien, r.cong_nhat, r.khoan_chung) for r in luu.dong]))
kiem("lưu: công khoán chung không được chấm ăn ca", not luu.an_ca)
kiem("trả về: dòng chung mang lại mã giả + tên cho màn hình",
     [(r["nhan_vien"], r["ten_nhan_vien"], r["khoan_chung"]) for r in kq["dong"]]
     == [("NV1", None, 0), (BVH.KHOAN_CHUNG, "Công khoán chung", 1)], str(kq["dong"]))
luu["docstatus"] = 0                                 # bảng nháp đã lưu — lần lưu sau tìm thấy nó
for i, r in enumerate(luu.dong):
    r["name"] = f"R{i}"
rows = [{"name": "R0", "nhan_vien": "NV1", "san_pham": "TP-A", "so_hop": 10},
        {"name": "R1", "nhan_vien": BVH.KHOAN_CHUNG, "san_pham": "TP-A", "so_hop": 9}]
PT.luu_bang_vao_hop("NSX-2", json.dumps(rows), biet=json.dumps(["R0", "R1"]))
kiem("sửa số dòng chung từ màn Ghi hộp: vẫn là dòng chung, đúng số mới",
     [(r.name, r.khoan_chung, r.nhan_vien, r.so_hop) for r in luu.dong] == [("R0", 0, "NV1", 10), ("R1", 1, None, 9)])
PT.luu_bang_vao_hop("NSX-2", json.dumps(rows[:1]), biet=json.dumps(["R0"]))
kiem("máy chưa biết dòng chung (vừa ghi từ thẻ sổ nợ) → lưu KHÔNG xoá mất nó",
     [r.name for r in luu.dong] == ["R0", "R1"])
PT.luu_bang_vao_hop("NSX-2", json.dumps(rows[:1]), biet=json.dumps(["R0", "R1"]))
kiem("máy đã biết mà bỏ dòng chung (bấm ✕) → xoá", [r.name for r in luu.dong] == ["R0"])

print("\n-- D203: Sổ nợ vào hộp → Ghi cho công khoán --")
BVH.SXBangVaoHop.save = BangMoi.save                 # bảng đã có của ngày: lưu như Frappe (validate rồi ghi)


def no_ma(item):
    return [(x.trang_thai, x.con_lai) for x in NO if x.item == item]


def dung_no():
    lam_sach()
    bang_vh({"nhan_vien": "NV1", "san_pham": "TP-A", "so_hop": 100}, ngay=HOM_NAY - timedelta(days=3))
    duyet(phieu({"item": "TP-A", "so_dem": 110}, ngay=HOM_NAY - timedelta(days=2)))
    duyet(phieu({"item": "TP-A", "so_dem": 7.2}, ngay=HOM_NAY - timedelta(days=1)))
    NGAY.append(Doc(name="NSX-H", ngay=HOM_NAY, docstatus=0))


dung_no()
VAI.clear(); VAI.add("SX Vao Hop")
s_ = K.so_no_vao_hop(str(HOM_NAY))
g = s_["nhom"][0]
kiem("thẻ sổ nợ: số hộp nguyên phải ghi (17,2 → 18, làm tròn LÊN), giá chung theo bảng đơn giá, QC được ghi",
     (g["so_hop"], g["gia_chung"], g["cach_lam"], s_["duoc_ghi_kc"]) == (18, 1000.0, [], True),
     str((g["so_hop"], g["gia_chung"], g["cach_lam"], s_["duoc_ghi_kc"])))
loi = thu(lambda: K.ghi_no_khoan_chung("NSX-H", "TP-A", 17))
kiem("số trên màn khác số nợ hiện tại → dừng, không ghi", "vừa đổi" in (loi or "") and not any(
    r.get("khoan_chung") for b_ in BANG.values() for r in b_.dong), loi or "")
MOI.clear()
kq = K.ghi_no_khoan_chung("NSX-H", "TP-A", 18)
bh = MOI["d"]
kiem("chưa có bảng ngày đó → lập bảng, một dòng ★ công khoán chung đúng số, ghi người bấm",
     [(r.khoan_chung, r.nhan_vien, r.san_pham, r.so_hop, r.nguoi_ghi) for r in bh.dong]
     == [(1, None, "TP-A", 18, "ql@x")] and bh.ngay_sx == "NSX-H", str(bh.dong))
kiem("… tính khoán theo đơn giá, trả về cho màn hình",
     (kq["so_hop"], kq["don_gia"], kq["thanh_tien"], kq["ngay"]) == (18, 1000.0, 18000.0, str(HOM_NAY)), str(kq))
kiem("… và nợ của mã về 0, đóng 'Đã chấm bù'", no_ma("TP-A") == [("Đã chấm bù", 0), ("Đã chấm bù", 0)],
     str(no_ma("TP-A")))
kiem("bấm lại (thẻ cũ) → không còn nợ, không ghi thêm dòng chung thứ hai",
     "không còn nợ" in (thu(lambda: K.ghi_no_khoan_chung("NSX-H", "TP-A", 18)) or "")
     and len([r for r in bh.dong if r.khoan_chung]) == 1)

dung_no()
bang_vh({"nhan_vien": "NV2", "san_pham": "TP-B", "so_hop": 1}, ten="NSX-T")
NGAY[-1]["ngay"] = HOM_NAY + timedelta(days=1)
kiem("ngày chưa tới → chặn", "chưa tới" in (thu(lambda: K.ghi_no_khoan_chung("NSX-T", "TP-A", 18)) or ""))
bang_vh({"nhan_vien": "NV2", "san_pham": "TP-B", "so_hop": 1}, ten="NSX-X")
NGAY[-1]["ngay"] = HOM_NAY - timedelta(days=40)
kiem("ngày quá xa khoản nợ (ngoài khoảng đối soát) → chặn, nói khoảng ngày được",
     "quá xa" in (thu(lambda: K.ghi_no_khoan_chung("NSX-X", "TP-A", 18)) or ""))
BANG["BVH-NSX-1"].dong.append(Doc(nhan_vien="NV2", san_pham="TP-A", so_hop=10))    # chấm bù, sổ nợ chưa đối soát
kiem("thẻ đang hiện nợ cũ (18) mà đã có người chấm bù 10 → đối soát trước, báo còn 8, không ghi thừa",
     "còn 8 hộp" in (thu(lambda: K.ghi_no_khoan_chung("NSX-H", "TP-A", 18)) or ""))
VAI.clear(); VAI.add("SX Thu Kho")
kiem("thủ kho không ghi được (không phải người ghi hộp)",
     "không có quyền" in (thu(lambda: K.ghi_no_khoan_chung("NSX-H", "TP-A", 8)) or ""))
VAI.clear(); VAI.add("SX Quan Ly")

dung_no()
goc_ds = K.doi_soat_no_vao_hop
K.doi_soat_no_vao_hop = lambda: []                   # giả sử đối soát không trừ được (sổ nợ lệch)
loi = thu(lambda: K.ghi_no_khoan_chung("NSX-H", "TP-A", 18))
K.doi_soat_no_vao_hop = goc_ds
kiem("ghi xong mà nợ không về 0 → báo lỗi (cả lần ghi bị rút lại), không để bấm lần hai trả khoán hai lần",
     "vẫn còn 17.2" in (loi or ""), loi or "")

print("\n-- D203: mã có nhiều cách làm --")
dung_no()
BANG_GIA.clear()
BANG_GIA.update({("TP-A", "Máy"): 800.0, ("TP-A", "Tay"): 1200.0})
g = K.so_no_vao_hop(str(HOM_NAY))["nhom"][0]
kiem("thẻ sổ nợ kèm các cách làm + giá, không có giá chung",
     (g["cach_lam"], g["gia_chung"]) == ([{"ten": "Máy", "don_gia": 800.0}, {"ten": "Tay", "don_gia": 1200.0}], None),
     str(g["cach_lam"]))
kiem("không chọn cách làm → chặn (mỗi cách một đơn giá)",
     "chọn cách làm" in (thu(lambda: K.ghi_no_khoan_chung("NSX-H", "TP-A", 18)) or ""))
kiem("cách làm không có trong bảng đơn giá → chặn",
     "không có cách làm" in (thu(lambda: K.ghi_no_khoan_chung("NSX-H", "TP-A", 18, "Xyz")) or ""))
kq = K.ghi_no_khoan_chung("NSX-H", "TP-A", 18, "Tay")
kiem("chọn Tay → dòng chung cách làm Tay, giá 1200", (kq["cach_lam"], kq["thanh_tien"]) == ("Tay", 21600.0), str(kq))
dung_no()
BANG_GIA.clear()
BANG_GIA.update({("TP-A", "Máy"): 800.0})
kq = K.ghi_no_khoan_chung("NSX-H", "TP-A", 18)
kiem("chỉ một cách làm, không giá chung → tự chọn", (kq["cach_lam"], kq["don_gia"]) == ("Máy", 800.0), str(kq))
dung_no()
BANG_GIA.clear()
BANG_GIA.update({("TP-A", "Máy"): 1.0, ("TP-A", "Tay"): 1.0, ("TP-A", ""): 1.0})
g = K.so_no_vao_hop(str(HOM_NAY))["nhom"][0]
kiem("D224: Tay / Máy giá tạm 1 đồng → thẻ vẫn kể hai cách làm, đơn giá 0 (màn hiện \"chưa có giá\"); giá chung tạm → "
     "không có giá chung", (g["cach_lam"], g["gia_chung"]) == ([{"ten": "Máy", "don_gia": 0.0},
                                                                 {"ten": "Tay", "don_gia": 0.0}], None), str(g))
kq = K.ghi_no_khoan_chung("NSX-H", "TP-A", 18, "Tay")
kiem("… chọn Tay → dòng chung 0 đồng (giá tạm KHÔNG vào tiền khoán), vào sổ nợ đơn giá",
     (kq["cach_lam"], kq["don_gia"], kq["thanh_tien"]) == ("Tay", 0.0, 0.0), str(kq))
dung_no()
BANG_GIA.clear()
kq = K.ghi_no_khoan_chung("NSX-H", "TP-A", 18)
kiem("mã chưa khai giá → vẫn ghi (0 đồng, vào sổ nợ đơn giá như dòng khoán)",
     (kq["so_hop"], kq["thanh_tien"]) == (18, 0.0) and no_ma("TP-A")[-1] == ("Đã chấm bù", 0), str(kq))
BANG_GIA.clear()
BANG_GIA.update({("TP-A", ""): 1000.0})

print("\n-- D203: nợ đã Bỏ qua không chặn việc trừ nợ còn lại --")
lam_sach()
bang_vh({"nhan_vien": "NV1", "san_pham": "TP-A", "so_hop": 100}, ngay=HOM_NAY - timedelta(days=3))
duyet(phieu({"item": "TP-A", "so_dem": 110}, ngay=HOM_NAY - timedelta(days=2)))     # nợ 10
NO.append(Doc(name="NV-CU", item="TP-A", ten="Bánh A", so_luong=30, con_lai=30, trang_thai="Bỏ qua",
              ly_do="hàng trả về", ngay=HOM_NAY - timedelta(days=40), phieu_nhap="PN-CU"))
K.doi_soat_no_vao_hop()
kiem("nợ Bỏ qua NGOÀI khoảng đối soát (phiếu nhập không còn trong 'đã nhận') → không trừ, nợ mở giữ nguyên",
     no_ma("TP-A")[0] == ("Chờ chấm", 10), str(no_ma("TP-A")))
lam_sach()
bang_vh({"nhan_vien": "NV1", "san_pham": "TP-A", "so_hop": 100}, ngay=HOM_NAY - timedelta(days=3))
duyet(phieu({"item": "TP-A", "so_dem": 130}, ngay=HOM_NAY - timedelta(days=2)))     # nợ A 30
duyet(phieu({"item": "TP-A", "so_dem": 20}, ngay=HOM_NAY - timedelta(days=1)))      # nợ B 20
K.bo_qua_no_vao_hop(NO[0].name, "hàng trả về nhập lại")
BANG["BVH-NSX-1"].dong.append(Doc(nhan_vien="NV2", san_pham="TP-A", so_hop=20))
K.doi_soat_no_vao_hop()
kiem("chấm bù đủ phần nợ còn mở (20) → nợ đó đóng, dù có nợ khác đã Bỏ qua trong khoảng",
     no_ma("TP-A") == [("Bỏ qua", 30), ("Đã chấm bù", 0)], str(no_ma("TP-A")))
lam_sach()
bang_vh({"nhan_vien": "NV1", "san_pham": "TP-A", "so_hop": 100}, ngay=HOM_NAY - timedelta(days=3))
duyet(phieu({"item": "TP-A", "so_dem": 130}, ngay=HOM_NAY - timedelta(days=2)))
K.bo_qua_no_vao_hop(NO[0].name, "hàng trả về nhập lại")
duyet(phieu({"item": "TP-A", "so_dem": 20}, ngay=HOM_NAY - timedelta(days=1)))
NGAY.append(Doc(name="NSX-H", ngay=HOM_NAY, docstatus=0))
kq = K.ghi_no_khoan_chung("NSX-H", "TP-A", 20)
kiem("… và Ghi cho công khoán trả hết nợ còn mở (không vướng phần Bỏ qua)",
     kq["so_hop"] == 20 and no_ma("TP-A") == [("Bỏ qua", 30), ("Đã chấm bù", 0)], str(no_ma("TP-A")))
VAI.clear(); VAI.add("SX Quan Ly")

# ═══ D230. Mốc tính nợ vào hộp: bỏ nợ trước mốc, mang sang hàng chấm chưa nhập ═══
print("\n-- D230: bỏ nợ vào hộp trước mốc, chỉ tính từ mốc --")
lam_sach()
HOM_NAY_GOC, now_goc = HOM_NAY, fu.now_datetime
fu.now_datetime = lambda: f"{HOM_NAY} 10:00:00"
NSX_DEM = {"n": 0}


def O(d):
    return date(2026, 10, d)


def N_(d):
    return date(2026, 11, d)


def hom_nay(d):
    global HOM_NAY
    HOM_NAY = d


def cham_vh(d, item, so):
    """QC chấm một mã một ngày (bảng riêng) — lưu bảng là đối soát nợ (hook)."""
    hom_nay(d)
    NSX_DEM["n"] += 1
    ten = f"NSX-D{NSX_DEM['n']}"
    bang_vh({"nhan_vien": "NV1", "san_pham": item, "so_hop": so}, ngay=d, ten=ten)
    K.doi_soat_no_vao_hop()
    return ten


def nhap_vh(d, item, so):
    hom_nay(d)
    ph = duyet(phieu({"item": item, "ten": item, "so_dem": so}, ngay=d))
    K.doi_soat_no_vao_hop()
    return ph


def no_cua(item):
    return sorted((str(x.ngay), x.trang_thai, x.con_lai) for x in NO if x.item == item)


# ── tháng 10 + 01–02/11, luật CŨ (chưa đặt mốc) ──
cham_vh(O(3), "TP-W", 10)                        # chấm 03/10, không bao giờ nhập kho
nhap_vh(O(12), "TP-A", 9940)                     # nhập lại tồn sau kiểm kê — không ai chấm
nhap_vh(O(15), "TP-D", 10)                       # hàng trả về nhập lại …
K.bo_qua_no_vao_hop(next(x for x in NO if x.item == "TP-D").name, "  hàng trả về ")  # … quản lý đã Bỏ qua
ph_g = nhap_vh(O(18), "TP-G", 5)                 # phiếu nhập rồi huỷ → nợ Đã huỷ
P.SXPhieuNhapTP.on_cancel(ph_g)
ph_g["docstatus"] = 2
cham_vh(O(20), "TP-A", 100)
nhap_vh(O(20), "TP-A", 100)                      # sản xuất bình thường — vẫn bị ghi nợ (cửa sổ âm vì 9.940)
nhap_vh(O(25), "TP-C", 20)                       # chấm sót 20 hộp
cham_vh(O(27), "TP-K", 20)                       # chấm 27/10 …
cham_vh(O(28), "TP-D", 15)                       # chấm, chưa nhập
nhap_vh(O(29), "TP-K", 20)                       # … nhập 29/10 (hàng 27/10)
cham_vh(O(30), "TP-K", 30)                       # chấm 30/10, chưa nhập
PHIEU.append(Doc(name="PN-TET", ngay=O(29), docstatus=0, nguon="Tết", dong=[Doc(item="TP-H", so_dem=12)]))
cham_vh(O(29), "TP-H", 12)                       # hàng Tết: phiếu nháp đã giữ chỗ
cham_vh(O(30), "TP-B", 40)                       # chấm 30/10 …
nsx_a31 = cham_vh(O(31), "TP-A", 50)             # chấm 31/10, chưa nhập
cham_vh(O(31), "TP-F", 70)                       # chấm 31/10, tới 04/11 vẫn chưa nhập
nhap_vh(N_(1), "TP-B", 40)                       # … 01/11 mới nhập kho
nhap_vh(N_(1), "TP-A", 50)
cham_vh(N_(2), "TP-A", 80)
cham_vh(N_(2), "TP-C", 30)                       # sản xuất tháng 11 — đối soát lấy trả nợ C tháng 10
nhap_vh(N_(2), "TP-A", 80)
nhap_vh(N_(2), "TP-C", 30)
nhap_vh(N_(2), "TP-E", 25)                       # chấm sót thật tháng 11
hom_nay(N_(4))
kiem("luật cũ: nợ tháng 10 của mã nhập lại tồn còn nguyên, tháng 11 nhập bao nhiêu nợ thêm bấy nhiêu",
     no_cua("TP-A") == [("2026-10-12", "Chờ chấm", 9710), ("2026-10-20", "Chờ chấm", 100),
                        ("2026-11-01", "Chờ chấm", 50), ("2026-11-02", "Chờ chấm", 80)], str(no_cua("TP-A")))
kiem("luật cũ: chấm tháng 11 bị lấy trả nợ tháng 10 → nợ chấm sót chuyển sang tháng 11",
     no_cua("TP-C") == [("2026-10-25", "Đã chấm bù", 0), ("2026-11-02", "Chờ chấm", 20)], str(no_cua("TP-C")))
goc = [dict(x) for x in NO]

loi = thu(lambda: K.xu_ly_bo_no_vh(tu_ngay="2026-11-05", chay=1))
kiem("mốc sau hôm nay → dừng (kiểm ngày dùng chung với D229)", loi and "chưa tới" in loi, loi or "")
O_SETTINGS.discard("no_vh_mang_sang")
loi = thu(lambda: K.xu_ly_bo_no_vh(chay=1))
O_SETTINGS.add("no_vh_mang_sang")
kiem("site chưa migrate đủ ô → dừng, bảo chạy migrate", loi and "migrate" in loi, loi or "")
kiem("… các lần dừng không ghi gì", [dict(x) for x in NO] == goc and not SETTINGS and not GHI_SINGLE)

kq = K.xu_ly_bo_no_vh()
kiem("mặc định mốc = đầu tháng này; xem trước KHÔNG ghi gì",
     kq["moc"] == N_(1) and kq["moc_cu"] is None and [dict(x) for x in NO] == goc and not SETTINGS
     and not GHI_SINGLE and kq["ve_0"] == [])
kiem("xem trước: đúng các nợ CHỜ CHẤM trước mốc (đã bỏ qua / đã huỷ / đã chấm bù không tính)",
     [(g["item"], g["con_lai"], g["ngay"]) for g in kq["nhom"]] == [("TP-A", 9810, [O(12), O(20)])], str(kq["nhom"]))
kiem("mang sang = hàng chấm trước mốc chưa nhập kho, theo ngày chấm (B 30/10, D sau phần đã Bỏ qua, F, W); Tết "
     "nháp giữ chỗ; mã nhập vượt lớn (A) bị che", [(m["item"], m["so"], m["ngay"]) for m in kq["mang"]]
     == [("TP-F", 70, [O(31)]), ("TP-B", 40, [O(30)]), ("TP-K", 30, [O(30)]), ("TP-D", 15, [O(28)]),
         ("TP-W", 10, [O(3)])], str(kq["mang"]))
bc = K.bao_cao_bo_no_vh(kq)
for cau in ("BỎ NỢ VÀO HỘP TRƯỚC 01/11/2026 — XEM TRƯỚC, chưa ghi gì (làm thật: thêm --kwargs \"{'chay': 1}\")",
            "Mốc tính nợ vào hộp: 01/11/2026 (trước đó: chưa đặt)",
            "2 khoản nợ đang chờ chấm trước mốc — 1 mã, 9.810 hộp, ngày 12/10/2026 → 20/10/2026:",
            "  • TP-A — 2 khoản, 9.810 hộp: 12/10, 20/10",
            "→ sẽ chuyển sang Bỏ qua, lý do \"Bỏ nợ vào hộp trước 01/11/2026 — chỉ tính nợ vào hộp từ 01/11/2026 (D230)\".",
            "Hàng chấm trước mốc mà chưa nhập kho — mang sang, nhập kho từ 01/11/2026 không thành nợ: 5 mã, 165 hộp:",
            "  • TP-F — 70 hộp (chấm 31/10)",
            "Nợ từ 01/11/2026 trở đi hiện có: 4 khoản, 175 hộp — làm thật sẽ đối soát lại theo mốc",
            "  • TP-A — 130 hộp\n",
            "Làm thật sẽ đặt mốc ở SX Settings: nợ vào hộp chỉ tính hàng chấm / nhập kho từ 01/11/2026"):
    kiem(f"báo cáo xem trước: {cau[:60]}", cau in bc, "" if cau in bc else bc)

MANG = ('{"TP-B": [["2026-10-30", 40.0]], "TP-D": [["2026-10-28", 15.0]], "TP-F": [["2026-10-31", 70.0]], '
        '"TP-K": [["2026-10-30", 30.0]], "TP-W": [["2026-10-03", 10.0]]}')
import contextlib
import io
ra_ = io.StringIO()
with contextlib.redirect_stdout(ra_):
    K.bo_no_vh_truoc(chay=1)
bc = ra_.getvalue()
LD = "Bỏ nợ vào hộp trước 01/11/2026 — chỉ tính nợ vào hộp từ 01/11/2026 (D230)"
kiem("làm thật: nợ chờ chấm trước mốc → Bỏ qua có lý do (giữ số còn nợ làm dấu vết)",
     no_cua("TP-A")[:2] == [("2026-10-12", "Bỏ qua", 9710), ("2026-10-20", "Bỏ qua", 100)]
     and all((x.ly_do, x.xu_ly_boi, x.xu_ly_luc) == (LD, "ql@x", "2026-11-04 10:00:00")
             for x in NO if x.item == "TP-A" and str(x.ngay) < "2026-11"),
     str(no_cua("TP-A")))
kiem("… nợ Bỏ qua cũ giữ lý do cũ (đã cắt khoảng trắng), nợ Đã huỷ / Đã chấm bù không đụng",
     next(x for x in NO if x.item == "TP-D").ly_do == "hàng trả về"
     and no_cua("TP-G") == [("2026-10-18", "Đã huỷ", 5)] and no_cua("TP-C")[0] == ("2026-10-25", "Đã chấm bù", 0))
kiem("… đặt mốc + phần mang sang ở SX Settings, xoá cache",
     SETTINGS == {"no_vh_tu_ngay": "2026-11-01", "no_vh_mang_sang": MANG}
     and ("xoá cache", "SX Settings", "SX Settings") in GHI_SINGLE, str(SETTINGS))
ok_ = (no_cua("TP-C")[1] == ("2026-11-02", "Đã chấm bù", 0)
       and no_cua("TP-A")[2:] == [("2026-11-01", "Đã chấm bù", 0), ("2026-11-02", "Chờ chấm", 50)])
kiem("đối soát lại ngay: chấm tháng 11 không còn bị trừ vào nợ cũ — nợ C tháng 11 về 0, nợ A chỉ còn phần "
     "hàng chấm 31/10 bị che (50)", ok_, "" if ok_ else str(NO))
kiem("… nợ chấm sót thật tháng 11 giữ nguyên", no_cua("TP-E") == [("2026-11-02", "Chờ chấm", 25)])
kiem("… thẻ nợ vào hộp chỉ còn nợ từ mốc",
     sorted((g["item"], g["con_lai"]) for g in K.so_no_vao_hop()["nhom"]) == [("TP-A", 50), ("TP-E", 25)])
for cau in ("BỎ NỢ VÀO HỘP TRƯỚC 01/11/2026 — ĐÃ GHI", "→ đã chuyển sang Bỏ qua",
            "Đối soát lại nợ từ 01/11/2026 theo mốc: 2 khoản về 0; còn 2 khoản, 75 hộp:",
            "  • TP-A — 50 hộp  ← mã vừa bỏ nợ cũ: thường là hàng chấm cuối tháng trước",
            "  • TP-E — 25 hộp\n", "Đã đặt mốc ở SX Settings"):
    kiem(f"báo cáo làm thật: {cau[:60]}", cau in bc, "" if cau in bc else bc)

# ── từ mốc: luật mới ──
kiem("phiếu nhập ghi ngày trước mốc → không sinh nợ",
     K.vuot_so_cham(O(30), [Doc(item="TP-Z", so_dem=9)]) == {})
kiem("phiếu ghi ĐÚNG ngày mốc → tính như thường (phần mang sang trừ vào, vượt thật vẫn nợ)",
     K.vuot_so_cham(N_(1), [Doc(item="TP-F", so_dem=75)]) == {"TP-F": 5.0})
kiem("phần mang sang hết hạn theo ngày chấm: W chấm 03/10 còn che phiếu 01/11, hết che từ 02/11",
     K.vuot_so_cham(N_(1), [Doc(item="TP-W", so_dem=10)]) == {}
     and K.vuot_so_cham(N_(2), [Doc(item="TP-W", so_dem=10)]) == {"TP-W": 10.0})
hom_nay(N_(3))
cham_vh(N_(3), "TP-B", 30)
nhap_vh(N_(3), "TP-B", 30)
kiem("mã có hàng chấm 30/10 nhập 01/11: chấm 03/11 nhập 03/11 → KHÔNG nợ (nhờ phần mang sang)",
     no_cua("TP-B") == [], str(no_cua("TP-B")))
cham_vh(N_(3), "TP-A", 60)
v_a = K.vuot_so_cham(N_(3), [Doc(item="TP-A", so_dem=60)])
nhap_vh(N_(3), "TP-A", 60)
kiem("mã nhập lại tồn tháng 10: chấm 60 nhập 60 ngày 03/11 → báo vượt đúng phần dư 50 (luật cũ: 60 — 9.940 còn trong "
     "cửa sổ), tổng nợ của mã KHÔNG tăng (dư 50 chỉ dời sang ngày mới)",
     v_a == {"TP-A": 50.0} and sum(c for d, t, c in no_cua("TP-A") if t == "Chờ chấm") == 50, f"{v_a} {no_cua('TP-A')}")
hom_nay(N_(4))
cn = {r["item"]: r for r in K.cho_nhan()["rows"]}
kiem("danh sách chờ nhập kho: hàng chấm trước mốc chưa nhập vẫn hiện (F 70, K 30, D 15; W 03/10 đã hết hạn)",
     {k: v["con"] for k, v in cn.items()} == {"TP-F": 70, "TP-K": 30, "TP-D": 15},
     str({k: v["con"] for k, v in cn.items()}))
kiem("… chia theo HSD đúng ngày chấm trước mốc (NSX 31/10)",
     [g["nsx"] for g in cn["TP-F"]["chia"]] == ["2026-10-31"], str(cn["TP-F"]["chia"]))
kiem("nhập phần mang sang → không nợ; nhập vượt thật → nợ đúng phần vượt",
     K.vuot_so_cham(N_(4), [Doc(item="TP-F", so_dem=70)]) == {}
     and K.vuot_so_cham(N_(4), [Doc(item="TP-F", so_dem=75)]) == {"TP-F": 5.0})
nhap_vh(N_(4), "TP-F", 75)
kiem("… duyệt thật: nợ 5", no_cua("TP-F") == [("2026-11-04", "Chờ chấm", 5)], str(no_cua("TP-F")))
cham_vh(N_(4), "TP-F", 5)
kiem("… QC chấm bù 5 → đối soát (có phần mang sang) trả hết nợ", no_cua("TP-F") == [("2026-11-04", "Đã chấm bù", 0)],
     str(no_cua("TP-F")))
NGAY.append(Doc(name="NSX-04", ngay=N_(4), docstatus=0))
loi = thu(lambda: K.ghi_no_khoan_chung(nsx_a31, "TP-A", 50))
kiem("Ghi cho công khoán vào ngày trước mốc → chặn, nói rõ mốc",
     loi and "trước mốc tính nợ vào hộp (01/11/2026)" in loi, loi or "")

kq2 = K.xu_ly_bo_no_vh(chay=1)
kiem("chạy lại: không còn gì để bỏ, mốc + phần mang sang y như cũ",
     kq2["dong"] == [] and kq2["moc_cu"] == N_(1) and SETTINGS["no_vh_mang_sang"] == MANG, str(kq2))
bc = K.bao_cao_bo_no_vh(kq2)
kiem("… báo cáo nói rõ", "Không có khoản nợ nào đang chờ chấm trước 01/11/2026." in bc
     and "(trước đó: 01/11/2026)" in bc and "→" not in bc.split("Mốc")[1].split("Hàng")[0], bc)

# ── cửa sổ quanh mốc ──
kiem("cửa sổ chạm vào trước mốc → bắt đầu ở mốc + phần mang sang CÒN trong cửa sổ (chấm 03/10 đã hết hạn)",
     K._cua_so(O(10), N_(4)) == (N_(1), {"TP-B": 40.0, "TP-D": 15.0, "TP-F": 70.0, "TP-K": 30.0})
     and K._cua_so(O(3), N_(1)) == (N_(1), {"TP-B": 40.0, "TP-D": 15.0, "TP-F": 70.0, "TP-K": 30.0, "TP-W": 10.0})
     and K._cua_so(O(29), N_(20)) == (N_(1), {"TP-B": 40.0, "TP-F": 70.0, "TP-K": 30.0}))
kiem("cửa sổ bắt đầu đúng mốc / sau mốc, hoặc nằm hẳn trước mốc → như cũ, không mang sang",
     K._cua_so(N_(1), N_(4)) == (N_(1), {}) and K._cua_so(N_(2), N_(4)) == (N_(2), {})
     and K._cua_so(O(1), O(31)) == (O(1), {}))
kiem("cửa sổ kết thúc ĐÚNG mốc → cắt ở mốc", K._cua_so(O(10), N_(1))[0] == N_(1))
SETTINGS["no_vh_mang_sang"] = "hỏng"
kiem("phần mang sang hỏng / không phải bảng mã → coi như không có", K._moc_vh() == (N_(1), {}))
SETTINGS["no_vh_mang_sang"] = "[1, 2]"
kiem("… (danh sách)", K._moc_vh() == (N_(1), {}))
SETTINGS["no_vh_mang_sang"] = '{"TP-B": [["2026-10-30", "40"]], "TP-X": [["sai", 1]], "TP-Y": 5}'
kiem("… dòng hỏng thì bỏ riêng dòng đó, số dạng chữ vẫn đọc", K._moc_vh() == (N_(1), {"TP-B": [(O(30), 40.0)]}),
     str(K._moc_vh()))
SETTINGS.clear()
kiem("chưa đặt mốc → luật cũ", K._moc_vh() == (None, {}) and K._cua_so(O(10), N_(4)) == (O(10), {}))

bc = K.bao_cao_bo_no_vh({"chay": 0, "moc": N_(1), "moc_cu": None, "ly_do": "x", "dong": [], "nhom": [], "ve_0": [],
                         "mang": [{"item": f"M{i:02d}", "ten": f"Bánh {i}", "so": 1.5, "ngay": [O(30), O(31)]}
                                  for i in range(16)],
                         "con": [{"item": f"C{i:02d}", "ten": f"C{i:02d}", "so": 1234.25, "khoan": 1, "bo_cu": True}
                                 for i in range(16)]})
bc15 = K.bao_cao_bo_no_vh({"chay": 1, "moc": N_(1), "moc_cu": N_(1), "ly_do": "x", "dong": [], "nhom": [],
                           "ve_0": [], "mang": [{"item": f"M{i:02d}", "ten": f"M{i:02d}", "so": 1, "ngay": [O(30)]}
                                                for i in range(15)],
                           "con": [{"item": f"C{i:02d}", "ten": f"C{i:02d}", "so": 2, "khoan": 1, "bo_cu": i == 0}
                                   for i in range(15)]})
kiem("báo cáo: đúng 15 mã thì in đủ, không gộp; làm thật gắn cờ mã vừa bỏ nợ cũ",
     "M14 — 1 hộp (chấm 30/10)" in bc15 and "C14 — 2 hộp" in bc15 and "… và" not in bc15
     and bc15.count("← mã vừa bỏ nợ cũ") == 1 and "  • C00 — 2 hộp  ← mã vừa bỏ nợ cũ" in bc15, bc15)
kiem("báo cáo: tên + mã, số lẻ có dấu phẩy, nghìn dấu chấm, quá 15 mã thì gộp; xem trước không gắn cờ",
     "  • Bánh 0 (M00) — 1,5 hộp (chấm 30/10, 31/10)" in bc and "  • C00 — 1.234,25 hộp\n" in bc and bc.count("… và 1 mã khác") == 2
     and "Bánh 15" not in bc and "C15" not in bc and "← mã vừa" not in bc and "16 khoản, 19.748 hộp" in bc, bc)
cay_k = ast.parse(open("sx/api/khotp.py", encoding="utf-8").read())
kiem("lệnh bỏ nợ vào hộp KHÔNG whitelist (chỉ chạy bằng bench)",
     all(not f.decorator_list for f in cay_k.body if isinstance(f, ast.FunctionDef)
         and f.name in ("bo_no_vh_truoc", "xu_ly_bo_no_vh", "bao_cao_bo_no_vh", "_mang_sang")))
st = json.load(open("sx/sx/doctype/sx_settings/sx_settings.json", encoding="utf-8"))
o_ = {f["fieldname"]: f for f in st["fields"]}
kiem("SX Settings có ô mốc (Date) + phần mang sang, chỉ đọc",
     (o_.get(K.TRUONG_MOC_VH, {}).get("fieldtype"), o_.get(K.TRUONG_MOC_VH, {}).get("read_only"),
      o_.get(K.TRUONG_MANG_SANG, {}).get("read_only")) == ("Date", 1, 1)
     and {K.TRUONG_MOC_VH, K.TRUONG_MANG_SANG} <= set(st["field_order"]))
SETTINGS.update(no_vh_tu_ngay="2026-11-01", no_vh_mang_sang=MANG)
NGAY.append(Doc(name="NSX-MOC", ngay=N_(1), docstatus=0))
MOI.clear()
kq_kc = K.ghi_no_khoan_chung("NSX-MOC", "TP-A", 50)
kiem("Ghi cho công khoán vào ĐÚNG ngày mốc → được, trả hết nợ còn lại của mã",
     kq_kc["so_hop"] == 50 and all(t != "Chờ chấm" for d, t, c in no_cua("TP-A")), str(no_cua("TP-A")))
hom_nay(N_(20))
K.xu_ly_bo_no_vh(tu_ngay="2026-11-15", chay=1)
mang_moi = json.loads(SETTINGS["no_vh_mang_sang"])
kiem("đặt mốc MỚI (15/11) khi đã có mốc cũ: phần mang sang cũ chưa nhập vẫn được mang tiếp (D 28/10, K 30/10), "
     "phần đã nhập trong tháng 11 thì thôi (F, B)",
     SETTINGS["no_vh_tu_ngay"] == "2026-11-15" and mang_moi.get("TP-D") == [["2026-10-28", 15.0]]
     and mang_moi.get("TP-K") == [["2026-10-30", 30.0]] and "TP-F" not in mang_moi and "TP-B" not in mang_moi,
     str(mang_moi))
kiem("… phần mang sang cũ đã hết hạn (W 03/10) không mang tiếp; tháng 10 vẫn không tính lại (A không thành 'chưa nhập')",
     "TP-W" not in mang_moi and "TP-A" not in mang_moi, str(mang_moi))
HOM_NAY, fu.now_datetime = HOM_NAY_GOC, now_goc
lam_sach()

# ═══ 4. Dây nối ══════════════════════════════════════════════════════════
print("\n-- dây nối --")
kiem("card nợ vào hộp ở màn Ghi hộp và Quản lý",
     "novaohop" in R.VIEW_CARDS["vaohop"] and "novaohop" in R.VIEW_CARDS["quanly"])
kiem("shell.js biết đường dẫn card",
     "novaohop: '/assets/sx/sx/cards/novaohop.js'" in open("sx/public/sx/shell.js").read())
card = open("sx/public/sx/cards/novaohop.js", encoding="utf-8").read()
for m in sorted(set(re.findall(r"sx\.api\.khotp\.(\w+)", card))):
    kiem(f"card gọi method có thật: {m}", callable(getattr(K, m, None)))
kiem("card không có nút 'đã chấm bù' bấm tay", "hach_toan" not in card
     and "da_cham_bu" not in card)
vh = open("sx/public/sx/cards/vaohop.js", encoding="utf-8").read()
kiem("màn Ghi hộp có nút chấm CÔNG NHẬT, cùng mã giả với server",
     f"const CONG_NHAT = '{BVH.CONG_NHAT}'" in vh and "sx-vh-congnhat" in vh)
kiem("công nhật không có nút ăn ca", "cn ? null : nutAnCa" in vh)
kiem("màn Ghi hộp biết mã giả công khoán chung, cùng mã với server",
     f"const KHOAN_CHUNG = '{BVH.KHOAN_CHUNG}'" in vh)
kiem("thẻ sổ nợ ghi vào NGÀY ĐANG XEM (ensureNgay) và tra giá theo ngày đó",
     "ctx.ensureNgay()" in card and "ngay: ngayXem" in card)
nk = open("sx/public/sx/cards/nhapkhotp.js", encoding="utf-8").read()
kiem("màn nhập kho báo phần vượt trước khi duyệt", "Nhận VƯỢT số đã chấm" in nk)
dt = json.load(open("sx/sx/doctype/sx_no_vao_hop/sx_no_vao_hop.json", encoding="utf-8"))
tt = next(f for f in dt["fields"] if f["fieldname"] == "trang_thai")["options"].split("\n")
kiem("trạng thái DocType khớp code", set(tt) == {NVH.CHO, *NVH.TRANG_THAI_DONG}, str(tt))
it = {f["fieldname"]: f for f in json.load(open(
    "sx/sx/doctype/sx_bang_vao_hop_item/sx_bang_vao_hop_item.json"))["fields"]}
kiem("dòng vào hộp có cờ công nhật; người không bắt buộc ở tầng DocType",
     "cong_nhat" in it and not it["nhan_vien"].get("reqd"))
kiem("dòng vào hộp có cờ công khoán chung (D203)", it.get("khoan_chung", {}).get("fieldtype") == "Check")

print("NOVAOHOP-OK" if not hong else f"NOVAOHOP: {hong} HỎNG")
sys.exit(1 if hong else 0)
