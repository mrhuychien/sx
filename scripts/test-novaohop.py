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
frappe.db = types.SimpleNamespace(
    get_value=_get_value, set_value=_set_value,
    exists=lambda dt, f=None: next(iter(get_all(dt, f)), None) and "x")
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
ut.tra_don_gia = lambda b, sp, cl=None: b.get((sp, cl or ""), b.get((sp, "")) if cl else None)
ut.bang_don_gia = lambda ngay=None: "BG-1"
ut.get_bom_active = lambda item: "BOM-" + item
ut.get_settings = lambda: Doc({"cong_ty": "RVHG", "kho_nvl": "NVL", "kho_btp": "BTP",
                               "kho_tp": "TP"})
ut.items_tp = lambda *a, **k: []
ut.nhom_tp = lambda: []
ut.sinh_ma_lo = lambda item, ngay: f"{item}-LO"
ut.cho_phep_ton_am = lambda: True
for ten in ("cach_lam_cua", "dat_ten_hien_thi", "get_dau_items", "topo_rank_by_bom",
            "loai_phieu_kho"):
    setattr(ut, ten, lambda *a, **k: None)
ut.nho = lambda ten: {}   # D120: bộ nhớ request — test giả không nhớ
ut.nap_bom = lambda items: {i: ut.get_bom_active(i) for i in (items or [])} if hasattr(ut, "get_bom_active") else {}
ut.ton_bin = lambda items, kho: {}
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
    for x in (NGAY, PHIEU, NO, MSG, SE):
        x.clear()
    BANG.clear()
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
p = phieu({"item": "TP-B", "ten": "Bánh B", "so_dem": 12},
          {"item": "TP-B", "ten": "Bánh B", "so_dem": 3})
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
kiem("hook gắn vào lưu + chốt bảng vào hộp",
     '"SX Bang Vao Hop": {"on_update": "sx.api.khotp.doi_soat_sau_cham"' in hk
     and '"on_submit": "sx.api.khotp.doi_soat_sau_cham"' in hk)

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
nk = open("sx/public/sx/cards/nhapkhotp.js", encoding="utf-8").read()
kiem("màn nhập kho báo phần vượt trước khi duyệt", "Nhận VƯỢT số đã chấm" in nk)
dt = json.load(open("sx/sx/doctype/sx_no_vao_hop/sx_no_vao_hop.json", encoding="utf-8"))
tt = next(f for f in dt["fields"] if f["fieldname"] == "trang_thai")["options"].split("\n")
kiem("trạng thái DocType khớp code", set(tt) == {NVH.CHO, *NVH.TRANG_THAI_DONG}, str(tt))
it = {f["fieldname"]: f for f in json.load(open(
    "sx/sx/doctype/sx_bang_vao_hop_item/sx_bang_vao_hop_item.json"))["fields"]}
kiem("dòng vào hộp có cờ công nhật; người không bắt buộc ở tầng DocType",
     "cong_nhat" in it and not it["nhan_vien"].get("reqd"))

print("NOVAOHOP-OK" if not hong else f"NOVAOHOP: {hong} HỎNG")
sys.exit(1 if hong else 0)
