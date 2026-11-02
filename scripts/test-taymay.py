"""D224 — seed bảng giá vào hộp: mọi thành phẩm hai cách làm Tay / Máy, giá tạm 1 đồng.

Vì sao phải có bài này: seed sửa thẳng bảng giá — tiền công của cả xưởng. Hỏng im lặng theo mấy hướng:
  · sửa đè bảng đang dùng (ngày cũ tính lại theo giá tạm) thay vì lập bảng mới từ ngày chọn;
  · bảng mới thiếu dòng của mã khác (tra giá chỉ đọc MỘT bảng → mã đó thành "chưa khai giá");
  · đè mất giá Tay / Máy người ta đã nhập; tạo trùng cách làm khi site đã có "máy" chữ thường;
  · đổi bảng trong khi bảng vào hộp chưa chốt còn dòng không cách làm → lưu lại thành 0 đồng, áp giá không được.

Nạp sx/seed/don_gia.py + sx.seed._dry THẬT, frappe giả; bảng kết quả chạy qua kiem_dong THẬT của SX Bang Don Gia.
Chạy: python3 scripts/test-taymay.py   (verify.sh gọi sẵn)
"""

import copy
import datetime
import importlib.util
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class D(dict):
    __getattr__ = dict.get

    def __setattr__(self, k, v):
        self[k] = v


class Throw(Exception):
    pass


def ngay(s):
    return datetime.date.fromisoformat(s)


DB, GHI, SET = {}, [], []
TP = []                      # items_tp: [(mã, tên)] — đã xếp theo tên như hàm thật


def _khop(r, f):
    for k, v in (f or {}).items():
        cur = r.get(k)
        if isinstance(v, tuple):
            op, val = v
            if op == ">=" and not (cur is not None and cur >= val):
                return False
            if op == "<" and not (cur is not None and cur < val):
                return False
            if op == "in" and cur not in val:
                return False
        elif cur != v:
            return False
    return True


def get_all(dt, filters=None, fields=None, **k):
    return [D({f: r.get(f) for f in (fields or r.keys())}) for r in DB.get(dt, []) if _khop(r, filters)]


def get_value(dt, f, fields=None, as_dict=False, **k):
    if isinstance(f, str):            # tìm theo tên: MariaDB không phân biệt hoa thường
        rows = [r for r in DB.get(dt, []) if r["name"].lower() == f.lower()]
    else:
        rows = [r for r in DB.get(dt, []) if _khop(r, f)]
    if not rows:
        return None
    if as_dict:
        return D({x: rows[0].get(x) for x in fields})
    return rows[0].get(fields)


class Bang:
    """SX Bang Don Gia giả: dong + append / set / save (lưu vào DB, ghi lại lần lưu)."""

    def __init__(self, **kw):
        self.name, self.hieu_luc_tu, self.ghi_chu, self.dong = None, None, None, []
        self.flags = D()
        self.__dict__.update(kw)

    def append(self, f, d):
        getattr(self, f).append(D(d, idx=len(getattr(self, f)) + 1))

    def set(self, f, v):
        setattr(self, f, list(v))

    def save(self):
        if not self.name:
            self.name = f"DG-{self.hieu_luc_tu.isoformat()}"
            if any(r["name"] == self.name for r in DB["SX Bang Don Gia"]):
                raise Throw(f"Duplicate entry {self.name}")      # như Frappe: tên bảng theo ngày hiệu lực
        GHI.append(self.name)
        DB["SX Bang Don Gia"] = [r for r in DB["SX Bang Don Gia"] if r["name"] != self.name] + [
            {"name": self.name, "hieu_luc_tu": self.hieu_luc_tu, "docstatus": 0, "ghi_chu": self.ghi_chu,
             "doc": copy.deepcopy(self)}]


class CachLam(D):
    def insert(self, set_name=None, ignore_permissions=None):
        GHI.append(("SX Cach Lam", set_name))
        DB["SX Cach Lam"].append({"name": set_name, "disabled": 0, "mo_ta": self.get("mo_ta")})


def get_doc(dt, name=None):
    if isinstance(dt, dict):
        return CachLam(dt)
    assert dt == "SX Bang Don Gia", dt
    return copy.deepcopy(next(r["doc"] for r in DB[dt] if r["name"] == name))


frappe = types.ModuleType("frappe")
frappe._dict = D
frappe.get_all = get_all
frappe.get_doc = get_doc
frappe.new_doc = lambda dt: Bang()
frappe.throw = lambda msg, *a, **k: (_ for _ in ()).throw(Throw(msg))
frappe.msgprint = lambda *a, **k: None
frappe.db = types.SimpleNamespace(get_value=get_value,
                                  set_value=lambda dt, n, f, v: SET.append((dt, n, f, v)))
fu = types.ModuleType("frappe.utils")
fu.getdate = lambda x=None: (x if isinstance(x, datetime.date) else ngay(str(x)[:10])) if x else ngay("2026-11-02")
fu.nowdate = lambda: "2026-11-02"
fu.add_days = lambda d, n: fu.getdate(d) + datetime.timedelta(days=n)
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
frappe.utils = fu
frappe.__dict__["_"] = lambda s: s
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
mm, md = types.ModuleType("frappe.model"), types.ModuleType("frappe.model.document")
md.Document = object
sys.modules["frappe.model"], sys.modules["frappe.model.document"] = mm, md

for g in ("sx",):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m
ut = types.ModuleType("sx.utils")
ut.GIA_TAM = 1
ut.items_tp = lambda fields=None: [D(name=c, item_name=t) for c, t in TP]


def _bang_don_gia(d):
    """Như sx.utils.bang_don_gia: bảng hiệu lực gần nhất trước (hoặc đúng) ngày; không có thì bảng sớm nhất."""
    ds = sorted((r for r in DB["SX Bang Don Gia"] if r["docstatus"] < 2), key=lambda r: r["hieu_luc_tu"])
    truoc = [r for r in ds if r["hieu_luc_tu"] <= d]
    return (truoc[-1] if truoc else ds[0])["name"] if ds else None


ut.bang_don_gia = _bang_don_gia
sys.modules["sx.utils"] = ut


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


nap("sx.seed", "sx/seed/__init__.py")
S = nap("sx.seed.don_gia", "sx/seed/don_gia.py")
BDG = nap("bdg", "sx/sx/doctype/sx_bang_don_gia/sx_bang_don_gia.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct and not dk else ''}")


def dong(sp, cl, gia, ten=None):
    return D(san_pham=sp, ten_san_pham=ten, cach_lam=cl, don_gia=gia, ghi_chu=None)


def lam_moi(*, cach=(), bang_cu=True):
    GHI.clear()
    SET.clear()
    TP[:] = [("TP-DUA", "Bánh đậu xanh dừa"), ("TP-SEN", "Bánh đậu xanh sen"), ("TP-LE", "Hộp lễ 100g")]
    DB.clear()
    DB["SX Cach Lam"] = [{"name": "Làm tay", "disabled": 0}] + [dict(c) for c in cach]
    DB["SX Bang Don Gia"] = []
    if bang_cu:
        b = Bang(name="DG-2026-08-01", hieu_luc_tu=ngay("2026-08-01"),
                 dong=[dong("BOT-X", None, 100), dong("TP-SEN", None, 500), dong("TP-SEN", "Làm tay", 600),
                       dong("TP-DUA", "Tay", 700), dong("TP-CU", None, 300)])
        DB["SX Bang Don Gia"].append({"name": b.name, "hieu_luc_tu": b.hieu_luc_tu, "docstatus": 0, "doc": b})
    for t in ("SX Ngay San Xuat", "SX Bang Vao Hop", "SX Bang Vao Hop Item", "SX No Don Gia"):
        DB[t] = []


def bang(ten):
    return next(r["doc"] for r in DB["SX Bang Don Gia"] if r["name"] == ten)


def khoa(b):
    return [(r.san_pham, r.cach_lam or "", r.don_gia) for r in b.dong]


def chay(**k):
    kq = S.xu_ly(**k)
    return kq, S.bao_cao(kq)


print("-- xem trước (gọi trần) --")
lam_moi()
kq, bc = chay()
kiem("gọi trần = XEM TRƯỚC: không tạo cách làm, không ghi bảng", not GHI and not SET and kq["dry_run"], GHI)
kiem("… cách làm Tay, Máy sẽ tạo mới", [(c["ten"], c["moi"]) for c in kq["cach"]] == [("Tay", True), ("Máy", True)])
kiem("… lập bảng mới từ hôm nay, chép bảng đang áp dụng", (kq["bang"], kq["goc"], kq["so_chep"]) == (None, "DG-2026-08-01", 5))
kiem("… thêm 5 dòng giá tạm (dừa Máy; sen Tay, Máy; hộp lễ Tay, Máy), giữ giá Tay thật của dừa",
     [(d["san_pham"], d["cach_lam"]) for d in kq["them"]]
     == [("TP-DUA", "Máy"), ("TP-SEN", "Tay"), ("TP-SEN", "Máy"), ("TP-LE", "Tay"), ("TP-LE", "Máy")]
     and [(d["san_pham"], d["cach_lam"], d["don_gia"]) for d in kq["giu"]] == [("TP-DUA", "Tay", 700.0)], kq["them"])
kiem("… bỏ giá chung + cách làm khác của thành phẩm (kèm giá cũ); dòng mã không phải thành phẩm giữ nguyên",
     [(x["san_pham"], x["cach_lam"], x["don_gia"]) for x in kq["bo"]] == [("TP-SEN", "", 500.0), ("TP-SEN", "Làm tay", 600.0)]
     and kq["ngoai"] == 2, kq["bo"])
kiem("báo cáo: XEM TRƯỚC, bảng mới từ 02/11/2026, giá cũ để đối chiếu, bước tiếp",
     "XEM TRƯỚC" in bc and "lập bảng mới hiệu lực từ 02/11/2026, chép 5 dòng từ DG-2026-08-01" in bc
     and "• Bánh đậu xanh sen (TP-SEN) — giá chung 500" in bc and "• Bánh đậu xanh sen (TP-SEN) — Làm tay 600" in bc
     and "• Bánh đậu xanh dừa — Tay 700" in bc and "+ thêm 5 dòng giá tạm 1 đồng" in bc
     and "{'dry_run': 0}" in bc and "Dòng còn 1 đồng = CHƯA có giá" in bc and "Áp giá" in bc, bc)

print("\n-- ghi thật --")
kq, bc = chay(dry_run=0)
kiem("tạo cách làm Tay, Máy (có mô tả)", [g for g in GHI if isinstance(g, tuple)] == [("SX Cach Lam", "Tay"),
                                                                                    ("SX Cach Lam", "Máy")]
     and [c.get("mo_ta") for c in DB["SX Cach Lam"][1:]] == ["Làm tay", "Làm bằng máy"], DB["SX Cach Lam"])
moi = bang("DG-2026-11-02")
kiem("lập bảng DG-2026-11-02 hiệu lực từ hôm nay, ghi chú nói giá tạm + chép từ bảng nào",
     moi.hieu_luc_tu == ngay("2026-11-02") and "Giá 1 đồng = giá tạm" in moi.ghi_chu and "DG-2026-08-01" in moi.ghi_chu
     and kq["da_ghi"] == "DG-2026-11-02", moi.ghi_chu)
kiem("dòng bảng mới: mã khác giữ nguyên (đầu bảng), rồi từng thành phẩm theo tên — Tay rồi Máy",
     khoa(moi) == [("BOT-X", "", 100.0), ("TP-CU", "", 300.0),
                   ("TP-DUA", "Tay", 700.0), ("TP-DUA", "Máy", 1),
                   ("TP-SEN", "Tay", 1), ("TP-SEN", "Máy", 1),
                   ("TP-LE", "Tay", 1), ("TP-LE", "Máy", 1)], khoa(moi))
kiem("… dòng thêm có tên hàng", [r.ten_san_pham for r in moi.dong if r.don_gia == 1]
     == ["Bánh đậu xanh dừa", "Bánh đậu xanh sen", "Bánh đậu xanh sen", "Hộp lễ 100g", "Hộp lễ 100g"])
kiem("bảng cũ giữ nguyên (ngày trước đó vẫn tính giá cũ)", khoa(bang("DG-2026-08-01"))
     == [("BOT-X", "", 100), ("TP-SEN", "", 500), ("TP-SEN", "Làm tay", 600), ("TP-DUA", "Tay", 700), ("TP-CU", "", 300)])
kt = BDG.SXBangDonGia.__new__(BDG.SXBangDonGia)
kt.dong = [D(r, idx=i + 1) for i, r in enumerate(moi.dong)]
try:
    kt.kiem_dong()
    loi = None
except Throw as e:
    loi = str(e)
kiem("bảng kết quả qua kiem_dong THẬT của SX Bang Don Gia (giá > 0, không trùng mã + cách làm)", loi is None, loi)
kiem("báo cáo: đã ghi bảng, chỗ nhập giá thật", "✓ Đã ghi bảng DG-2026-11-02." in bc
     and "SX Bang Don Gia → DG-2026-11-02" in bc and "XEM TRƯỚC" not in bc, bc)

print("\n-- chạy lại --")
GHI.clear()
kq, bc = chay(dry_run=0)
kiem("chạy lại: bảng ngày đó đã đủ → không ghi gì, không tạo lại cách làm", not GHI and not kq["doi"], GHI)
kiem("… báo cáo nói đã đủ", "đã đủ Tay / Máy cho mọi thành phẩm — giữ nguyên" in bc and "Không có gì phải ghi" in bc, bc)
b = bang("DG-2026-11-02")
b.dong[4].don_gia = 900                          # quản lý nhập giá thật cho sen Tay
b.ghi_chu = "Giá tháng 11 — đã nhập sen Tay"
TP.append(("TP-MOI", "Mứt dừa"))                 # thêm một thành phẩm mới
GHI.clear()
kq, bc = chay(dry_run=0)
b = bang("DG-2026-11-02")
kiem("có thành phẩm mới: sửa ĐÚNG bảng ngày đó (không lập bảng thứ hai), giữ giá đã nhập, thêm mã mới — đủ, không trùng",
     GHI == ["DG-2026-11-02"] and khoa(b) == [("BOT-X", "", 100.0), ("TP-CU", "", 300.0),
                                              ("TP-DUA", "Tay", 700.0), ("TP-DUA", "Máy", 1.0),
                                              ("TP-SEN", "Tay", 900.0), ("TP-SEN", "Máy", 1.0),
                                              ("TP-LE", "Tay", 1.0), ("TP-LE", "Máy", 1.0),
                                              ("TP-MOI", "Tay", 1), ("TP-MOI", "Máy", 1)]
     and len(DB["SX Bang Don Gia"]) == 2, (GHI, khoa(b)))
kiem("… giữ ghi chú người ta đã sửa trên bảng đó", b.ghi_chu == "Giá tháng 11 — đã nhập sen Tay", b.ghi_chu)
kiem("… \"giữ giá đã có\" chỉ kể giá thật (dòng còn 1 đồng không phải giá đã nhập)",
     [(d["san_pham"], d["cach_lam"], d["don_gia"]) for d in kq["giu"]] == [("TP-DUA", "Tay", 700.0), ("TP-SEN", "Tay", 900.0)],
     kq["giu"])
kiem("… báo cáo: sửa bảng đã có, giữ giá đã nhập", "sửa DG-2026-11-02 (đã có bảng hiệu lực đúng từ 02/11/2026)" in bc
     and "Bánh đậu xanh sen — Tay 900" in bc, bc)

print("\n-- dừng khi có dòng sẽ mất giá --")
lam_moi()
DB["SX Ngay San Xuat"] = [{"name": "NSX-01", "ngay": ngay("2026-11-01")}, {"name": "NSX-02", "ngay": ngay("2026-11-02")},
                          {"name": "NSX-03", "ngay": ngay("2026-11-03")}]
DB["SX Bang Vao Hop"] = [{"name": "BVH-01", "ngay_sx": "NSX-01", "docstatus": 0},    # trước ngày đổi: không sao
                         {"name": "BVH-02", "ngay_sx": "NSX-02", "docstatus": 0},
                         {"name": "BVH-03", "ngay_sx": "NSX-03", "docstatus": 1}]    # đã chốt: giá đã lưu
DB["SX Bang Vao Hop Item"] = [
    {"parent": "BVH-01", "parenttype": "SX Bang Vao Hop", "idx": 1, "san_pham": "TP-SEN", "cach_lam": None},
    {"parent": "BVH-02", "parenttype": "SX Bang Vao Hop", "idx": 1, "san_pham": "TP-SEN", "cach_lam": None},
    {"parent": "BVH-02", "parenttype": "SX Bang Vao Hop", "idx": 2, "san_pham": "TP-SEN", "cach_lam": "Tay"},
    {"parent": "BVH-02", "parenttype": "SX Bang Vao Hop", "idx": 3, "san_pham": "TP-LE", "cach_lam": None,
     "cong_nhat": 1},
    {"parent": "BVH-02", "parenttype": "SX Bang Vao Hop", "idx": 4, "san_pham": "BOT-X", "cach_lam": None},
    {"parent": "BVH-03", "parenttype": "SX Bang Vao Hop", "idx": 1, "san_pham": "TP-SEN", "cach_lam": None}]
DB["SX No Don Gia"] = [{"name": "NG-1", "ngay": ngay("2026-11-02"), "san_pham": "TP-DUA", "cach_lam": "Làm tay",
                        "trang_thai": "Chờ giá"},
                       {"name": "NG-2", "ngay": ngay("2026-11-02"), "san_pham": "TP-DUA", "cach_lam": None,
                        "trang_thai": "Đã cập nhật"},
                       {"name": "NG-3", "ngay": ngay("2026-10-30"), "san_pham": "TP-SEN", "cach_lam": None,
                        "trang_thai": "Chờ giá"}]
kq, bc = chay(dry_run=0)
kiem("bảng vào hộp chưa chốt từ hôm nay có dòng thành phẩm không cách làm → DỪNG, không ghi gì", not GHI and kq["chan"])
kiem("… chỉ đúng các dòng sẽ mất giá: bảng chưa chốt từ ngày đổi (không công nhật, không mã ngoài thành phẩm, "
     "không dòng đã Tay), sổ nợ đang chờ giá từ ngày đổi",
     [x["noi"] for x in kq["chan"]] == ["bảng vào hộp BVH-02 dòng 1", "sổ nợ đơn giá NG-1"], kq["chan"])
kiem("… báo cáo: DỪNG, liệt kê, gợi ý chạy từ ngày sau dòng cuối", "⚠ DỪNG — KHÔNG GHI GÌ" in bc
     and "02/11/2026 · bảng vào hộp BVH-02 dòng 1: Bánh đậu xanh sen — giá chung" in bc
     and "02/11/2026 · sổ nợ đơn giá NG-1: Bánh đậu xanh dừa — Làm tay" in bc
     and "'tu_ngay': '2026-11-03'" in bc and "Đã ghi" not in bc, bc)
kq, bc = chay(dry_run=1)
kiem("xem trước cũng báo DỪNG (để biết trước khi ghi)", kq["chan"] and "⚠ DỪNG" in bc and not GHI)
kq, bc = chay(dry_run=0, tu_ngay="2026-11-03")
kiem("chạy từ ngày sau (03/11): ghi được, bảng DG-2026-11-03", kq["da_ghi"] == "DG-2026-11-03" and not kq["chan"], kq)

print("\n-- cách làm đã có trên site --")
lam_moi(cach=[{"name": "máy", "disabled": 0}, {"name": "Tay", "disabled": 1}])
kq, bc = chay(dry_run=0)
kiem("site có \"máy\" chữ thường: dùng đúng tên đó, không tạo trùng; \"Tay\" đang tắt → bật lại",
     [(c["ten"], c["moi"], c["tat"]) for c in kq["cach"]] == [("Tay", False, True), ("máy", False, False)]
     and not [g for g in GHI if isinstance(g, tuple)] and SET == [("SX Cach Lam", "Tay", "disabled", 0)], (kq["cach"], SET))
kiem("… dòng bảng mới dùng tên \"máy\" của site", ("TP-SEN", "máy", 1) in khoa(bang("DG-2026-11-02")))
kiem("… báo cáo nói rõ", "Tay (bật lại) · máy (đã có)" in bc, bc)

print("\n-- trường hợp biên --")
lam_moi(bang_cu=False)
kq, bc = chay(dry_run=0)
kiem("chưa có bảng giá nào: lập bảng đầu tiên chỉ có thành phẩm × Tay / Máy",
     khoa(bang("DG-2026-11-02")) == [(c, cl, 1) for c, _t in TP for cl in ("Tay", "Máy")]
     and "lập bảng đầu tiên" in bc, bc)
lam_moi(cach=[{"name": "Tay", "disabled": 0}, {"name": "Máy", "disabled": 0}])
b = bang("DG-2026-08-01")
b.dong = [dong("BOT-X", None, 100)] + [dong(c, cl, 800) for c, _t in TP for cl in ("Tay", "Máy")]
kq, bc = chay(dry_run=0)
kiem("bảng đang dùng đã đủ Tay / Máy, không gì phải bỏ: KHÔNG lập bảng trùng y hệt", not GHI and not kq["doi"]
     and "DG-2026-08-01 đã đủ Tay / Máy" in bc, (GHI, bc))
DB["SX Cach Lam"][2]["disabled"] = 1                     # "Máy" đang tắt
kq, bc = chay(dry_run=0)
kiem("… mà cách làm Máy đang tắt: chỉ bật lại cách làm, vẫn không lập bảng", SET == [("SX Cach Lam", "Máy", "disabled", 0)]
     and not GHI and kq["doi"] and not kq["doi_bang"] and "✓ Đã ghi cách làm." in bc, (SET, GHI, bc))
lam_moi()
kq, bc = chay(dry_run=0, tu_ngay="2026-07-01")
kiem("ngày đổi trước mọi bảng: chép từ bảng sớm nhất (như tra giá)", kq["goc"] == "DG-2026-08-01"
     and kq["da_ghi"] == "DG-2026-07-01", kq)
try:
    S.xu_ly(dry_run="có lẽ")
    loi = None
except Throw as e:
    loi = str(e)
kiem("dry_run lạ → dừng, không đoán (quy ước sx.seed)", loi and "không hiểu được" in loi, loi)

print()
print("TAYMAY-HỎNG ({})".format(hong) if hong else "TAYMAY-OK")
sys.exit(1 if hong else 0)
