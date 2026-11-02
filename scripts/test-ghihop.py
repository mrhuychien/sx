"""D113 — hai QC ghi vào hộp cùng một ngày: mỗi người chỉ thấy / sửa phần mình,
và KHÔNG ai làm mất dòng của người kia.

Lỗi thật trước D113: mỗi lần lưu máy gửi CẢ danh sách nó đang thấy và server thay
HẾT bảng. QC A mở màn 8h, QC B ghi 10 dòng 8h05, 8h10 A chấm thêm một người →
10 dòng của B biến mất, không báo gì. Mất mạng còn tệ hơn: hàng chờ gửi lại bản
cũ đè lên mọi thứ.

Nạp sx/api/portal.py (luu_bang_vao_hop, _bang_summary), controller SX Bang Vao Hop
và sx/config/roles.py THẬT; frappe giả có dòng con được đặt mã khi lưu như thật.
Chạy: python3 scripts/test-ghihop.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import re
import sys
import types
from datetime import date

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

VAI = {"SX Vao Hop"}
BANG = {}            # name -> doc (DB giả)
SO = {"dong": 0}


class Loi(Exception):
    pass


class _dict(dict):
    __getattr__ = dict.get

    def __setattr__(self, k, v):
        self[k] = v


class Row(_dict):
    def update(self, d):
        dict.update(self, d)


class Doc(_dict):
    @property
    def flags(self):
        return self.setdefault("_flags", _dict())

    def append(self, k, v):
        r = Row(v)
        self.setdefault(k, []).append(r)
        return r

    def set(self, k, v):
        self[k] = list(v)

    def get(self, k, d=None):
        return dict.get(self, k, d)


def _nap_bang(n):
    d = BANG[n]
    b = BangDoc({k: v for k, v in d.items() if k not in ("dong", "an_ca")})
    b["dong"] = [Row(r) for r in d.get("dong", [])]
    b["an_ca"] = [Row(r) for r in d.get("an_ca", [])]
    return b


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.msgprint = lambda *a, **k: None
frappe.session = types.SimpleNamespace(user="qcA@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.parse_json = lambda x: json.loads(x) if isinstance(x, str) else x
frappe.get_doc = lambda dt, n=None: _nap_bang(n)
frappe.new_doc = lambda dt: BangDoc(name="BVH-1", dong=[], an_ca=[])
frappe.get_all = lambda *a, **k: []
frappe.db = types.SimpleNamespace(
    get_value=lambda dt, f, fld=None, **k: (
        next((n for n, d in BANG.items() if d.get("ngay_sx") == f.get("ngay_sx")), None)
        if dt == "SX Bang Vao Hop" else (date(2026, 10, 5) if dt == "SX Ngay San Xuat" else None)),
    exists=lambda *a, **k: None)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: float(v or 0)
fu.getdate = lambda x=None: x
fu.nowdate = lambda: "2026-10-05"
fu.add_days = lambda d, n: d
fu.now_datetime = lambda: "2026-10-05 10:00:00"
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
for ten in ("bang_don_gia", "cach_lam_cua", "dat_ten_hien_thi", "get_bom_active", "get_dau_items",
            "get_settings", "items_tp"):
    setattr(ut, ten, lambda *a, **k: None)
ut.don_gia_ap_dung = lambda ngay=None: {("SEN", ""): 1000.0, ("TT", ""): 800.0}
ut.tra_don_gia = lambda b, sp, cl=None: b.get((sp, cl or ""), b.get((sp, "")))
ut.nho = lambda ten: {}   # D120: bộ nhớ request — test giả không nhớ
GIA_GIO = [33000.0]      # D225: SX Settings → đơn giá làm theo giờ
ut.don_gia_gio = lambda: GIA_GIO[0]
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
BVH = nap("sx.sx.doctype.sx_bang_vao_hop.sx_bang_vao_hop",
          "sx/sx/doctype/sx_bang_vao_hop/sx_bang_vao_hop.py")
BVH.SXBangVaoHop.validate_duy_nhat = lambda self: None


class BangDoc(BVH.SXBangVaoHop):
    """Như Frappe: get_doc đọc BẢN SAO; save() mới ghi lại và đặt mã cho dòng mới."""

    def is_new(self):
        return self["name"] not in BANG

    def save(self):
        self.validate()
        for r in self["dong"]:
            if not r.get("name"):
                SO["dong"] += 1
                r["name"] = f"row-{SO['dong']}"
        BANG[self["name"]] = json.loads(json.dumps({k: v for k, v in self.items() if k != "_flags"},
                                                   default=str))
        return self

    def delete(self, **k):
        BANG.pop(self["name"], None)



BVH.SXBangVaoHop.gop_theo_nguoi = lambda self: None
PT = nap("sx.api.portal", "sx/api/portal.py")
PT._chan_neu_chot = lambda *a: None

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


def la(user, vai="SX Vao Hop"):
    frappe.session.user = user
    VAI.clear(); VAI.add(vai)


def luu(rows, biet=None, an_ca=None):
    return PT.luu_bang_vao_hop("NSX-1", json.dumps(rows),
                               an_ca=None if an_ca is None else json.dumps(an_ca),
                               biet=None if biet is None else json.dumps(biet))


def dong(nv, sp, sl, name=None):
    return {"name": name, "nhan_vien": nv, "san_pham": sp, "so_hop": sl}


def tat_ca():
    return BANG["BVH-1"]["dong"] if "BVH-1" in BANG else []


print("-- hai QC ghi cùng lúc không mất dòng của nhau --")
la("qcA@x")
a = luu([dong("NV1", "SEN", 100), dong("NV2", "SEN", 80)], biet=[])
biet_a = [r["name"] for r in a["dong"]]
kiem("QC A ghi 2 dòng, mỗi dòng mang người ghi + mã",
     len(biet_a) == 2 and all(r["nguoi_ghi"] == "qcA@x" for r in a["dong"]))
la("qcB@x")
b = luu([dong("NV3", "TT", 50)], biet=[])
kiem("QC B KHÔNG thấy dòng của A", [r["nhan_vien"] for r in b["dong"]] == ["NV3"])
kiem("… tổng của B chỉ là phần B", b["tong_hop"] == 50)
la("qcA@x")
a = luu([dong("NV1", "SEN", 100, biet_a[0]), dong("NV2", "SEN", 80, biet_a[1]),
         dong("NV4", "SEN", 30)], biet=biet_a)
kiem("A (màn hình cũ, không biết dòng của B) chấm thêm → dòng của B VẪN CÒN",
     sorted(r["nhan_vien"] for r in tat_ca()) == ["NV1", "NV2", "NV3", "NV4"],
     str([r["nhan_vien"] for r in tat_ca()]))
kiem("A thấy 3 dòng của mình", sorted(r["nhan_vien"] for r in a["dong"]) == ["NV1", "NV2", "NV4"])
biet_a = [r["name"] for r in a["dong"]]

print("\n-- sửa / xoá chỉ dòng của mình --")
nv2 = next(r for r in a["dong"] if r["nhan_vien"] == "NV2")
a = luu([dict(dong(r["nhan_vien"], r["san_pham"], r["so_hop"], r["name"]))
         for r in a["dong"] if r["nhan_vien"] != "NV2"], biet=biet_a)
kiem("A xoá dòng NV2 của mình → mất đúng dòng đó",
     sorted(r["nhan_vien"] for r in tat_ca()) == ["NV1", "NV3", "NV4"])
biet_a = [r["name"] for r in a["dong"]]
dong_b = next(r for r in tat_ca() if r["nhan_vien"] == "NV3")["name"]
luu([dong(r["nhan_vien"], r["san_pham"], 999 if r["nhan_vien"] == "NV1" else r["so_hop"], r["name"])
     for r in a["dong"]] + [dong("NV3", "TT", 1, dong_b)], biet=biet_a + [dong_b])
kiem("A sửa số dòng của mình được", next(r for r in tat_ca() if r["nhan_vien"] == "NV1")["so_hop"] == 999)
kiem("A gửi mã dòng của B → bị bỏ qua: không sửa, không nhân bản",
     [r["so_hop"] for r in tat_ca() if r["nhan_vien"] == "NV3"] == [50])
kiem("A không xoá được dòng của B dù có trong 'biet'",
     any(r["nhan_vien"] == "NV3" for r in tat_ca()))

print("\n-- máy bản cũ (không gửi 'biet') --")
la("qcB@x")
luu([], biet=None)
kiem("chỉ xoá phần của chính người gửi, không đụng dòng người khác",
     sorted(r["nhan_vien"] for r in tat_ca()) == ["NV1", "NV4"])

print("\n-- mất mạng: hàng chờ gửi lại rồi máy gửi tiếp → không nhân đôi --")
la("qcB@x")
luu([dong("NV5", "TT", 20), dong("NV6", "TT", 20)], biet=[])     # bản hàng chờ gửi lại
luu([dong("NV5", "TT", 20), dong("NV6", "TT", 20), dong("NV7", "TT", 5)], biet=[])
kiem("hai dòng đã lên từ hàng chờ không bị thêm lần hai; dòng mới vẫn vào",
     sorted(r["nhan_vien"] for r in tat_ca() if r["nguoi_ghi"] == "qcB@x") == ["NV5", "NV6", "NV7"],
     str([r["nhan_vien"] for r in tat_ca()]))

print("\n-- quản lý thấy / sửa tất cả, nhưng cũng không xoá dòng chưa biết --")
la("ql@x", "SX Quan Ly")
q = PT._bang_summary("NSX-1")
kiem("quản lý thấy mọi dòng của cả hai QC", len(q["dong"]) == len(tat_ca()) and q["xem_het"])
biet_q = [r["name"] for r in q["dong"]]
la("qcA@x")
luu([dong(r["nhan_vien"], r["san_pham"], r["so_hop"], r["name"])
     for r in PT._bang_summary("NSX-1")["dong"]] + [dong("NV8", "SEN", 9)],
    biet=[r["name"] for r in PT._bang_summary("NSX-1")["dong"]])
la("ql@x", "SX Quan Ly")
luu([dong(r["nhan_vien"], r["san_pham"], r["so_hop"], r["name"]) for r in q["dong"]
     if r["nhan_vien"] != "NV7"], biet=biet_q)
kiem("quản lý xoá dòng của QC B được", not any(r["nhan_vien"] == "NV7" for r in tat_ca()))
kiem("dòng A vừa thêm SAU lúc quản lý mở màn vẫn còn", any(r["nhan_vien"] == "NV8" for r in tat_ca()))
kiem("dòng quản lý sửa giữ người ghi gốc", all(r["nguoi_ghi"] in ("qcA@x", "qcB@x") for r in tat_ca()))

print("\n-- ăn ca: gộp theo người, chỉ gửi phần vừa đổi --")
la("qcA@x")
luu([dong(r["nhan_vien"], r["san_pham"], r["so_hop"], r["name"]) for r in PT._bang_summary("NSX-1")["dong"]],
    biet=[r["name"] for r in PT._bang_summary("NSX-1")["dong"]], an_ca=[{"nhan_vien": "NV1", "an_ca": 1}])
la("qcB@x")
luu([dong(r["nhan_vien"], r["san_pham"], r["so_hop"], r["name"]) for r in PT._bang_summary("NSX-1")["dong"]],
    biet=[r["name"] for r in PT._bang_summary("NSX-1")["dong"]], an_ca=[{"nhan_vien": "NV5", "an_dem": 1}])
an = {r["nhan_vien"]: (r["an_ca"], r["an_dem"]) for r in BANG["BVH-1"]["an_ca"]}
kiem("A chấm NV1, B chấm NV5 → cả hai còn", an == {"NV1": (1, 0), "NV5": (0, 1)}, str(an))
la("qcA@x")
luu([dong(r["nhan_vien"], r["san_pham"], r["so_hop"], r["name"]) for r in PT._bang_summary("NSX-1")["dong"]],
    biet=[r["name"] for r in PT._bang_summary("NSX-1")["dong"]], an_ca=[{"nhan_vien": "NV1", "an_ca": 0, "an_dem": 0}])
an = {r["nhan_vien"] for r in BANG["BVH-1"]["an_ca"]}
kiem("A bỏ chấm NV1 → chỉ NV1 mất, NV5 của B còn", an == {"NV5"}, str(an))

print("\n-- dây nối --")
js = open("sx/public/sx/cards/vaohop.js", encoding="utf-8").read()
kiem("màn Ghi hộp gửi mã dòng + 'biet'", "biet: JSON.stringify(biet)" in js and "name: x.name || null" in js)
kiem("màn Ghi hộp chỉ gửi ăn ca vừa đổi", "an_ca: JSON.stringify(doiAn)" in js)
kiem("mất mạng: không xoá trắng màn hình khi lưu vào hàng chờ", "if (r && r._hang_cho)" in js)
pt = open("sx/patches/d113_vao_hop_nguoi_ghi.py", encoding="utf-8").read()
kiem("patch gán người ghi cho dòng cũ = người tạo bảng",
     "SET i.nguoi_ghi = b.owner" in pt and "sx.patches.d113_vao_hop_nguoi_ghi"
     in open("sx/patches.txt").read())

print("\n-- D121: danh mục theo màn, tải khi màn mở --")
GOI = []
PT.get_dau_items = lambda: GOI.append("ghiso") or ["dau"]
PT._items_nhom = None
PT.items_tp = lambda *a, **k: GOI.append("vaohop") or []
PT._danh_muc_khoan = lambda ngay: []
PT._sp_gan_day = lambda: []
PT.bang_don_gia = lambda ngay=None: "BDG"
PT._nhan_vien_vao_hop = lambda: (GOI.append("nhan_vien") or [{"name": "NV1"}], None)
PT._ma_quet = lambda nv: GOI.append("quet") or {"nv": {}, "sp": {"893": "SEN"}}
PT.get_settings = lambda: types.SimpleNamespace(get=lambda k, d=None: 0)
PT.nap_bom = lambda items: {}
frappe.get_all = lambda *a, **k: []
dm = PT._danh_muc
VAI.clear(); VAI.add("SX Quan Ly")
GOI.clear()
r = dm(set(), "2026-10-06", set(VAI), True)
kiem("màn Quản lý: không dựng danh mục nào", GOI == [] and r["phan"] == [], (GOI, r))
GOI.clear()
r = dm({"ghiso"}, "2026-10-06", set(VAI), True)
kiem("màn Ghi sổ: chỉ danh mục báo mẻ", GOI == ["ghiso"] and "loai_dau" in r
     and "items_tp" not in r and r["phan"] == ["ghiso"], (GOI, sorted(r)))
GOI.clear()
r = dm({"vaohop"}, "2026-10-06", set(VAI), True)
kiem("D225: danh mục Ghi hộp kèm đơn giá làm theo giờ (bàn số hiện thành tiền)", r.get("don_gia_gio") == 33000.0, r)
kiem("màn Ghi hộp: danh mục vào hộp + mã quét (không kèm báo mẻ)", "items_tp" in r
     and "ma_quet" in r and "loai_dau" not in r
     and "ghiso" not in GOI, sorted(r))
VAI.clear(); VAI.add("SX Thu Kho")
GOI.clear()
r = dm({"quet", "vaohop", "ghiso"}, "2026-10-06", set(VAI), False)
kiem("thủ kho: được bảng mã quét (trước D121 không có), KHÔNG được danh mục khác",
     "ma_quet" in r and "items_tp" not in r and "loai_dau" not in r and r["phan"] == ["quet"],
     sorted(r))
VAI.clear(); VAI.add("SX Ghi So")
r = dm({"vaohop", "quet"}, "2026-10-06", set(VAI), False)
kiem("tổ Ghi sổ không lấy được danh mục vào hộp / mã quét", r == {"phan": []}, r)
kiem("client cũ (không gửi phan) → đủ mọi phần được phép như trước",
     PT._doc_phan(None) is None and PT._doc_phan('["ghiso","la"]') == {"ghiso"})
sh = open("sx/public/sx/shell.js", encoding="utf-8").read()
kiem("shell và server dùng CÙNG bảng màn → phần",
     "const PHAN_VIEW = { ghiso: ['ghiso'], vaohop: ['vaohop'], nhapkho: ['quet'] };" in sh
     and PT.VIEW_PHAN == {"ghiso": ["ghiso"], "vaohop": ["vaohop"], "nhapkho": ["quet"]})

print("\n-- D225: làm theo giờ (bảng chấm theo người) --")
BANG.clear()
la("qcA@x")


def nguoi(nv):
    return next((r for r in BANG["BVH-1"]["an_ca"] if r["nhan_vien"] == nv), None)


def gio_luu(an_ca, rows=None):
    return luu(rows if rows is not None else [dong("NV1", "SEN", 10)], biet=[r["name"] for r in tat_ca()],
               an_ca=an_ca)


gio_luu([{"nhan_vien": "NV2", "so_gio": 2.5}])
g = nguoi("NV2")
kiem("ghi 2,5 giờ cho NV2 (chưa vào hộp, chưa ăn): có dòng người, đơn giá chốt từ Settings, tiền = giờ × giá",
     g and (g["so_gio"], g["don_gia_gio"], g["tien_gio"], g["an_ca"], g["an_dem"]) == (2.5, 33000.0, 82500.0, 0, 0),
     g)
kiem("… tổng tiền bảng cộng tiền giờ (10 hộp SEN × 1000 + 82.500)", BANG["BVH-1"]["tong_tien"] == 92500.0,
     BANG["BVH-1"]["tong_tien"])
sm = PT._bang_summary("NSX-1")
kiem("… màn Ghi hộp nhận lại số giờ + tiền giờ", [(x["nhan_vien"], x["so_gio"], x["tien_gio"]) for x in sm["an_ca"]]
     == [("NV2", 2.5, 82500.0)], sm["an_ca"])
gio_luu([{"nhan_vien": "NV2", "an_ca": 1, "an_dem": 0}])
g = nguoi("NV2")
kiem("máy bản cũ chấm ăn (không gửi khoá so_gio) → GIỮ số giờ đã ghi", (g["an_ca"], g["so_gio"]) == (1, 2.5), g)
gio_luu([{"nhan_vien": "NV2", "an_dem": 1}])
g = nguoi("NV2")
kiem("chỉ gửi khoá vừa đổi: bật ăn đêm không xoá ăn ca / số giờ", (g["an_ca"], g["an_dem"], g["so_gio"]) == (1, 1, 2.5),
     g)
GIA_GIO[0] = 35000.0
gio_luu([{"nhan_vien": "NV2", "so_gio": 3}, {"nhan_vien": "NV9", "so_gio": 1}])
kiem("đổi đơn giá ở Settings: người đã có giờ GIỮ giá lúc ghi lần đầu (33.000), người mới ghi theo giá mới",
     (nguoi("NV2")["don_gia_gio"], nguoi("NV2")["tien_gio"], nguoi("NV9")["don_gia_gio"])
     == (33000.0, 99000.0, 35000.0), (nguoi("NV2"), nguoi("NV9")))
gio_luu([{"nhan_vien": "NV9", "so_gio": 0}])
kiem("số giờ 0 = bỏ: người chỉ có giờ thì mất dòng", nguoi("NV9") is None, BANG["BVH-1"]["an_ca"])
gio_luu([{"nhan_vien": "NV2", "so_gio": 0}])
g = nguoi("NV2")
kiem("… người còn chấm ăn thì giữ dòng, bỏ giờ + bỏ luôn đơn giá (ghi lại sẽ theo giá Settings lúc đó)",
     g and (g["an_ca"], g["so_gio"], g["don_gia_gio"], g["tien_gio"]) == (1, 0, 0, 0), g)
gio_luu([{"nhan_vien": "NV2", "so_gio": 1.5}])
kiem("… ghi lại → đơn giá Settings hiện tại", nguoi("NV2")["don_gia_gio"] == 35000.0, nguoi("NV2"))
GIA_GIO[0] = 33000.0
try:
    gio_luu([{"nhan_vien": "NV2", "so_gio": 25}])
    loi = ""
except Loi as e:
    loi = str(e)
kiem("quá 24 giờ → báo lỗi, không lưu", "từ 0 đến 24" in loi, loi)
kiem("… số cũ giữ nguyên", nguoi("NV2")["so_gio"] == 1.5)
gio_luu([{"nhan_vien": "CONG_NHAT", "so_gio": 3}, {"nhan_vien": "KHOAN_CHUNG", "so_gio": 3}])
kiem("công nhật / công khoán chung không phải một người → không ghi giờ",
     not nguoi("CONG_NHAT") and not nguoi("KHOAN_CHUNG") and not nguoi(None))
luu([], biet=[r["name"] for r in tat_ca()], an_ca=[{"nhan_vien": "NV2", "an_ca": 0, "an_dem": 0}])
kiem("xoá hết dòng hộp, bỏ chấm ăn mà còn giờ → GIỮ bảng (giờ là tiền công)", "BVH-1" in BANG
     and nguoi("NV2") and nguoi("NV2")["so_gio"] == 1.5, BANG.get("BVH-1"))
js = open("sx/public/sx/cards/vaohop.js", encoding="utf-8").read()
kiem("màn Ghi hộp: lối Làm theo giờ, bàn số giờ lẻ, gửi khoá so_gio vừa đổi",
     "⏱ LÀM THEO GIỜ" in js and "allowDecimal: true" in js and "['an_ca', 'an_dem', 'so_gio']" in js)

print("GHIHOP-OK" if not hong else f"GHIHOP: {hong} HỎNG")
sys.exit(1 if hong else 0)
