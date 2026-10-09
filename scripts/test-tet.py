"""D122 — Vào hộp Tết: một lần lưu = phiếu nhập kho NHÁP + sản lượng công nhật.

Hỏng theo hướng nguy hiểm:
  · phiếu nhập có mà công nhật không (hoặc ngược lại) — vào hộp / nhập kho lệch,
    duyệt phiếu sinh "nợ vào hộp" oan;
  · dòng sai (thiếu HSD, số lẻ) vẫn ghi được nửa chừng;
  · xoá phiếu nháp mà công nhật còn nằm lại — sản lượng ma;
  · người khác xoá được phiếu của mình, hoặc xoá phiếu thủ kho đã duyệt.

Nạp sx/api/tet.py THẬT; frappe + các module sx khác là giả.
Chạy: python3 scripts/test-tet.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import sys
import types
from datetime import date, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class Loi(Exception):
    pass


class D(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


DEM = {"bang": 0, "phieu": 0, "dong": 0}
BANG = {}       # name -> Doc bảng vào hộp
PHIEU = {}      # name -> Doc phiếu nhập
NGAY = {}       # name -> D(ngay, chot_vaohop, docstatus)
VAI = {"SX QC Tet"}
SHELF = {"TP-SEN": 180, "TP-TT": 0}
NHOM = {"TP-SEN": "Hộp quà Tết", "TP-TT": "Hàng Tết", "TP-THUONG": "Bánh thường"}
CAY = {"Hàng Tết": (10, 13), "Hộp quà Tết": (11, 12), "Bánh thường": (20, 21)}   # Hộp quà Tết ⊂ Hàng Tết
CAU_HINH = {"nhom_tet": []}


class Doc(D):
    def append(self, k, v):
        r = D(v)
        self.setdefault(k, []).append(r)
        return r

    def set(self, k, v):
        self[k] = v

    @property
    def flags(self):
        return self.setdefault("_flags", D())


class BangDoc(Doc):
    def save(self):
        if not self.get("name"):
            DEM["bang"] += 1
            self["name"] = f"BVH-{DEM['bang']}"
            self.setdefault("docstatus", 0)
        for r in self["dong"]:
            if not r.get("name"):
                DEM["dong"] += 1
                r["name"] = f"row{DEM['dong']}"
        BANG[self["name"]] = self

    def delete(self, **k):
        BANG.pop(self["name"], None)


class PhieuDoc(Doc):
    def insert(self):
        DEM["phieu"] += 1
        self["name"] = f"PN-{DEM['phieu']}"
        self.setdefault("docstatus", 0)
        self["tong_dem"] = sum(r["so_dem"] for r in self["dong"])
        PHIEU[self["name"]] = self

    def delete(self, **k):
        T.go_cong_nhat(self)          # = SXPhieuNhapTP.on_trash
        PHIEU.pop(self["name"])


def new_doc(dt):
    if dt == "SX Bang Vao Hop":
        return BangDoc(dong=[])
    if dt == "SX Phieu Nhap TP":
        return PhieuDoc(dong=[])
    if dt == "SX Ngay San Xuat":
        d = Doc()
        def ins():
            d["name"] = f"SXN-{d['ngay']}"
            NGAY[d["name"]] = D(ngay=d["ngay"], docstatus=0, chot_vaohop=0)
        d.insert = ins
        return d
    raise AssertionError(dt)


def get_doc(dt, n=None):
    return {"SX Bang Vao Hop": BANG, "SX Phieu Nhap TP": PHIEU}[dt][n]


def get_value(dt, f, field=None, **k):
    if dt == "Item Group":
        return CAY[f]
    if dt == "SX Ngay San Xuat":
        return next((n for n, x in NGAY.items() if x.ngay == f["ngay"] and x.docstatus < 2), None)
    if dt == "SX Bang Vao Hop":
        return next((n for n, b in BANG.items() if b.ngay_sx == f["ngay_sx"]
                     and b.get("docstatus", 0) == f["docstatus"]), None)
    return None


def exists(dt, f=None):
    if dt == "SX Bang Vao Hop":
        b = BANG.get(f["name"])
        return bool(b) and b.get("docstatus", 0) == f["docstatus"]
    return False


def get_all(dt, filters=None, fields=None, pluck=None, **k):
    if dt == "Item Group":
        if "item_group_name" in filters:
            return [g for g in CAY if "Tết" in g]
        lo, hi = filters["lft"][1], filters["rgt"][1]
        return [g for g, (l, r) in CAY.items() if l > lo and r < hi]
    if dt == "SX Phieu Nhap TP":
        ra = [D(name=p.name, ngay=p.ngay, docstatus=p.docstatus, tong_dem=p.tong_dem,
                nguoi_lap=p.nguoi_lap, nguon=p.nguon) for p in PHIEU.values()
              if all(p.get(kk) == v for kk, v in (filters or {}).items())]
        return ra
    if dt == "SX Phieu Nhap TP Item":
        ten = set(filters["parent"][1])
        return [D(r, parent=p.name) for p in PHIEU.values() if p.name in ten for r in p.dong]
    return []


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, title=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.session = types.SimpleNamespace(user="tet1@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.new_doc = new_doc
frappe.get_doc = get_doc
frappe.get_all = get_all
frappe.db = types.SimpleNamespace(get_value=get_value, exists=exists)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.flt = lambda v, p=None: float(v or 0)
fu.cint = lambda v: int(float(v or 0))
fu.getdate = lambda x=None: x if isinstance(x, date) else date.fromisoformat(str(x)[:10])
fu.nowdate = lambda: "2027-01-20"
fu.now_datetime = lambda: "2027-01-20 10:00"
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.api", "sx.config", "sx.sx", "sx.sx.doctype", "sx.sx.doctype.sx_phieu_nhap_tp"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m
ut = types.ModuleType("sx.utils")
ut.get_settings = lambda: D(kho_tp="Kho TP", nhom_tet=[D(item_group=g) for g in CAU_HINH["nhom_tet"]])
TEN = {"TP-SEN": "Bánh sen", "TP-TT": "Bánh TT", "TP-THUONG": "Bánh thường"}
ut.items_tp = lambda fields=None, **k: [D(name=i, item_name=TEN[i], item_group=NHOM[i], stock_uom="Hộp",
                                          shelf_life_in_days=SHELF.get(i, 0)) for i in TEN]
ut.nap_cong_bo = lambda items: {i: None for i in (items or [])}   # D127: chưa mã nào gắn
sys.modules["sx.utils"] = ut
kh = types.ModuleType("sx.api.khotp")
kh._ghi_json = lambda v: json.dumps(v) if v else None
kh._nap_uom = lambda items: None
kh._uom_cua = lambda item, dvt: [{"uom": "Thùng", "he_so": 12}, {"uom": "Hộp", "he_so": 1}]
kh._han_dung_js = lambda item, sl=None: {"han_dung": int(sl or 0), "han_dung_thang": 0}
sys.modules["sx.api.khotp"] = kh
po = types.ModuleType("sx.api.portal")


def _chan(ngay_sx, nua, viec):
    if NGAY[ngay_sx].chot_vaohop:
        raise Loi(f"Phần Vào hộp đã chốt — không {viec} được.")


po._chan_neu_chot = _chan
po._ma_quet = lambda nv: {"nv": {}, "sp": {"893": "TP-SEN"}}
sys.modules["sx.api.portal"] = po
ct = types.ModuleType("sx.sx.doctype.sx_phieu_nhap_tp.sx_phieu_nhap_tp")
ct.hsd_goi_y = lambda item, ngay: (str(fu.getdate(ngay) + timedelta(days=SHELF[item]))
                                   if SHELF.get(item) else None)
sys.modules["sx.sx.doctype.sx_phieu_nhap_tp.sx_phieu_nhap_tp"] = ct


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


R = nap("sx.config.roles", "sx/config/roles.py")
T = nap("sx.api.tet", "sx/api/tet.py")

hong = 0


def kiem(ten, dk, ct_=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct_)) if ct_ else ''}")


def thu(fn):
    try:
        return fn(), None
    except Loi as e:
        return None, e


def lam_sach():
    BANG.clear(); PHIEU.clear(); NGAY.clear()
    VAI.clear(); VAI.add("SX QC Tet")
    frappe.session.user = "tet1@x"


print("-- lưu một lần --")
lam_sach()
CT = [{"uom": "Thùng", "sl": 2, "he_so": 12}, {"uom": "Hộp", "sl": 3, "he_so": 1}]
r = T.luu(json.dumps([{"item": "TP-SEN", "so": 27, "chi_tiet": CT},
                      {"item": "TP-TT", "so": 10, "hsd": "2027-06-30"}]), "2027-01-20")
p = PHIEU[r["phieu"]]
kiem("tạo đúng MỘT phiếu nhập kho NHÁP, nguồn Tết", len(PHIEU) == 1 and p.docstatus == 0
     and p.nguon == "Tết" and p.kho_dich == "Kho TP", p.nguon)
kiem("mỗi dòng: số lập = số đếm, giữ cách chia thùng/hộp",
     [(d["item"], d["so_lap"], d["so_dem"]) for d in p.dong] == [("TP-SEN", 27, 27), ("TP-TT", 10, 10)]
     and json.loads(p.dong[0]["dem_uom"]) == CT)
kiem("HSD: mã có Shelf Life tự điền, mã gõ tay giữ nguyên",
     [d["hsd"] for d in p.dong] == ["2027-07-19", "2027-06-30"], [d["hsd"] for d in p.dong])
b = BANG[r["bang"]]
kiem("công nhật ghi vào bảng vào hộp của ngày (không gắn người)",
     [(x.cong_nhat, x.nhan_vien, x.san_pham, x.so_hop) for x in b.dong]
     == [(1, None, "TP-SEN", 27), (1, None, "TP-TT", 10)])
kiem("… ghi rõ ai ghi", all(x.nguoi_ghi == "tet1@x" for x in b.dong))
kiem("phiếu nhớ đúng các dòng công nhật của nó",
     json.loads(p.vao_hop_tet) == [{"bang": b.name, "dong": x.name} for x in b.dong])
kiem("tóm tắt trả về", r["tong"] == 37 and r["so_dong"] == 2, r)

print("\n-- lần lưu thứ hai cùng ngày: GỘP vào bảng có sẵn, phiếu mới --")
b.dong.insert(0, D(name="cua-qc-khac", nhan_vien="NV1", san_pham="TP-SEN", so_hop=50))
r2 = T.luu([{"item": "TP-SEN", "so": 12}], "2027-01-20")
kiem("cùng bảng vào hộp, giữ nguyên dòng của QC khác",
     r2["bang"] == r["bang"] and BANG[r["bang"]].dong[0].name == "cua-qc-khac"
     and len(BANG[r["bang"]].dong) == 4)
kiem("phiếu nháp thứ hai riêng", len(PHIEU) == 2 and r2["phieu"] != r["phieu"])

print("\n-- dòng sai: chặn TRƯỚC khi ghi gì --")
lam_sach()
for ten, rows in (
        ("mã không phải thành phẩm", [{"item": "BOT", "so": 5}]),
        ("thành phẩm thường, không phải hàng Tết", [{"item": "TP-THUONG", "so": 5, "hsd": "2027-06-01"}]),
        ("số hộp lẻ", [{"item": "TP-SEN", "so": 2.5}]),
        ("mã chưa khai Shelf Life mà không nhập HSD", [{"item": "TP-TT", "so": 5}]),
        ("HSD không sau ngày nhập", [{"item": "TP-SEN", "so": 5, "hsd": "2027-01-20"}]),
        ("không có dòng nào có số", [{"item": "TP-SEN", "so": 0}])):
    _, e = thu(lambda rows=rows: T.luu(rows, "2027-01-20"))
    kiem(f"{ten} → chặn", e is not None and not PHIEU and not BANG, e)
_, e = thu(lambda: T.luu([{"item": "TP-SEN", "so": 5}, {"item": "TP-TT", "so": 1}], "2027-01-20"))
kiem("một dòng sai → KHÔNG ghi cả dòng đúng (không nửa chừng)", e is not None and not PHIEU and not BANG)
kiem("… và báo đúng dòng", e is not None and "Dòng 2" in str(e) and "Bánh TT" in str(e), e)

print("\n-- ngày đã chốt Vào hộp --")
lam_sach()
NGAY["SXN-2027-01-20"] = D(ngay=date(2027, 1, 20), docstatus=0, chot_vaohop=1)
_, e = thu(lambda: T.luu([{"item": "TP-SEN", "so": 5}], "2027-01-20"))
kiem("đã chốt → chặn, không tạo phiếu", e is not None and not PHIEU, e)

print("\n-- xoá phiếu nháp kéo theo công nhật --")
lam_sach()
r = T.luu([{"item": "TP-SEN", "so": 27}, {"item": "TP-TT", "so": 3, "hsd": "2027-05-01"}], "2027-01-20")
BANG[r["bang"]].dong.append(D(name="khac", nhan_vien="NV9", san_pham="TP-TT", so_hop=8))
T.xoa(r["phieu"])
kiem("phiếu bị xoá", r["phieu"] not in PHIEU)
kiem("dòng công nhật của phiếu bị xoá, dòng khác giữ nguyên",
     [x.name for x in BANG[r["bang"]].dong] == ["khac"])
r = T.luu([{"item": "TP-SEN", "so": 5}], "2027-01-21")
T.xoa(r["phieu"])
kiem("bảng chỉ còn rỗng → xoá luôn bảng (như D106)", r["bang"] not in BANG)
r = T.luu([{"item": "TP-SEN", "so": 5}], "2027-01-22")
BANG[r["bang"]]["docstatus"] = 1
T.go_cong_nhat(PHIEU[r["phieu"]])
kiem("bảng đã chốt Vào hộp → KHÔNG lặng lẽ sửa", len(BANG[r["bang"]].dong) == 1)

print("\n-- ai xoá được --")
lam_sach()
r = T.luu([{"item": "TP-SEN", "so": 5}], "2027-01-20")
frappe.session.user = "tet2@x"
_, e = thu(lambda: T.xoa(r["phieu"]))
kiem("QC Tết khác KHÔNG xoá được phiếu của người khác", isinstance(e, frappe.PermissionError), e)
kiem("… và không thấy phiếu đó trong danh sách của mình", T.gan_day() == [])
VAI.add("SX Quan Ly")
kiem("quản lý thấy phiếu của mọi người", [x["name"] for x in T.gan_day()] == [r["phieu"]])
VAI.discard("SX Quan Ly")
frappe.session.user = "tet1@x"
PHIEU[r["phieu"]]["docstatus"] = 1
_, e = thu(lambda: T.xoa(r["phieu"]))
kiem("phiếu thủ kho đã duyệt → không xoá ở đây", e is not None and "thủ kho" in str(e), e)
kiem("trạng thái hiện đúng", T.gan_day()[0]["trang_thai"] == "Đã nhập kho"
     and not T.gan_day()[0]["duoc_xoa"])
PHIEU["PN-X"] = PhieuDoc(name="PN-X", docstatus=0, nguon=None, dong=[], nguoi_lap="tet1@x")
_, e = thu(lambda: T.xoa("PN-X"))
kiem("phiếu thường (không phải Tết) → không xoá ở màn này", e is not None and "Tết" in str(e), e)

print("\n-- chỉ bày HÀNG TẾT (D124) --")
lam_sach()
dm = T.danh_muc()
kiem("tự nhận nhóm tên chứa 'Tết' (cả nhóm con) — mã thường không lên",
     [r["item"] for r in dm["rows"]] == ["TP-SEN", "TP-TT"] and not dm["chua_co_nhom"], dm["rows"])
CAU_HINH["nhom_tet"] = ["Hộp quà Tết"]
kiem("SX Settings → Nhóm Hàng Tết được ưu tiên", [r["item"] for r in T.danh_muc()["rows"]] == ["TP-SEN"])
CAU_HINH["nhom_tet"] = ["Hàng Tết"]
kiem("chọn nhóm cha thì lấy luôn nhóm con", [r["item"] for r in T.danh_muc()["rows"]] == ["TP-SEN", "TP-TT"])
CAU_HINH["nhom_tet"] = []
cu = dict(CAY)
for g in [g for g in CAY if "Tết" in g]:
    CAY.pop(g)
dm = T.danh_muc()
kiem("chưa có nhóm Tết nào → bày mọi TP + cờ nhắc cấu hình",
     len(dm["rows"]) == 3 and dm["chua_co_nhom"])
CAY.update(cu)
kiem("mã quét vẫn đủ (quét nhầm mã thường thì báo 'không phải hàng Tết')", dm["ma_quet"]["sp"] == {"893": "TP-SEN"})
js = open("sx/public/sx/cards/vaohoptet.js", encoding="utf-8").read()
nk = open("sx/public/sx/cards/nhapkhotp.js", encoding="utf-8").read()
# Hành vi bàn số (gõ, đổi tab, HSD, trùng lô) chạy thật ở scripts/test-sohsd.mjs; đây chỉ soát dây nối.
kiem("chọn mã → vào thẳng bàn số MỘT MÀN, dùng chung với Nhập kho (moSoHsd, D153)",
     "import { hsdTu, moSoHsd, veNgayDu } from '/assets/sx/sx/cards/nhapkhotp.js'" in js
     and "return moSoHsd({" in js and "function themItem(item)" in js and "openSoLuong" not in js)
kiem("bàn số có tab đơn vị + ô HSD + kiểm HSD sau ngày nhập",
     "data-tab" in nk and 'id="sh-hsd"' in nk and "h <= ngay" in nk)

print("\n-- quyền + dây nối --")
VAI.clear(); VAI.add("SX Vao Hop")
_, e = thu(lambda: T.luu([{"item": "TP-SEN", "so": 1}]))
kiem("QC vào hộp thường KHÔNG dùng màn Tết", isinstance(e, frappe.PermissionError), e)
VAI.clear(); VAI.add("SX QC Tet")
kiem("role mới có trong VAI_MAC_DINH (site mới tự tạo, không vào Desk)",
     R.VAI_MAC_DINH.get("SX QC Tet") == 0)
kiem("role → tab 'tet' → thẻ vaohoptet", R.ROLE_VIEWS["SX QC Tet"] == ["tet"]
     and R.VIEW_CARDS["tet"] == ["vaohoptet"] and R.CARD_ROLES["vaohoptet"] == ["SX QC Tet"])
kiem("quản lý cũng vào được tab Tết", "tet" in R.ROLE_VIEWS["SX Quan Ly"] and "tet" in R.MOI_VIEW)
sh = open("sx/public/sx/shell.js", encoding="utf-8").read()
kiem("shell biết view + card", "tet: '/assets/sx/sx/views/tet.js'" in sh
     and "vaohoptet: '/assets/sx/sx/cards/vaohoptet.js'" in sh)
nd = open("sx/api/nguoidung.py", encoding="utf-8").read()
kiem("quản lý tạo được tài khoản QC Tết", 'QC_TET: "QC vào hộp Tết"' in nd)
kh_src = open("sx/api/khotp.py", encoding="utf-8").read()
kiem("hàng Tết chờ duyệt không bày lại ở 'chờ nhập kho' (không nhập hai lần)",
     '"nguon": "Tết"' in kh_src and "tet = [t for t in tet if t != tru_phieu]" in kh_src)
c = open("sx/sx/doctype/sx_phieu_nhap_tp/sx_phieu_nhap_tp.py", encoding="utf-8").read()
kiem("xoá phiếu ở bất cứ đâu (cả thủ kho) cũng kéo theo công nhật", "go_cong_nhat(self)" in c)

print()
if hong:
    print(f"TET-HỎNG ({hong})")
    sys.exit(1)
print("TET-OK")
