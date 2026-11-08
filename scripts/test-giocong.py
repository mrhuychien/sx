"""D225 — công khoán làm theo giờ (33.000đ/giờ): chốt ngày ghi vào phiếu lương NHƯ lương sản phẩm.

Vì sao phải có bài này: tiền giờ là tiền lương. Hỏng im lặng theo mấy hướng:
  · người CHỈ làm theo giờ (không vào hộp, không ăn ca) bị bỏ qua lúc ghi phiếu lương — ngày đó mất trắng;
  · tiền giờ thành một khoản riêng: Chủ nhật không nhân 1,2, không vào thâm niên (đã chốt: tính NHƯ lương sản phẩm);
  · chốt lại ngày thì dòng giờ cũ + mới cộng dồn; bỏ giờ mà dòng giờ cũ còn nằm trên phiếu;
  · dòng sản phẩm mất mã hàng vẫn lọt (ô Mã hàng hết bắt buộc trên form vì dòng giờ không có mã).

Chạy ĐÚNG mã: _co_gi_de_ghi / _ghi_luong_khoan / _thay_ngay chép nguyên từ sx/api/chot.py (không nạp cả module nặng),
controller SX Phieu Luong THẬT; frappe giả.
Chạy: python3 scripts/test-giocong.py   (verify.sh gọi sẵn)
"""

import ast
import importlib.util
import os
import sys
import types
from datetime import date

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


TRUOC = {}       # (employee, tháng, năm) → lương SP tháng trước (thâm niên)

frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw(Loi(str(m)))
frappe.__dict__["_"] = lambda s: s
frappe.db = types.SimpleNamespace(
    exists=lambda *a, **k: None,
    get_value=lambda dt, f, fld=None, **k: TRUOC.get((f["employee"], f["thang"], f["nam"])))
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.getdate = lambda x=None: x if isinstance(x, date) else date.fromisoformat(str(x)[:10])
fu.formatdate = lambda d: str(d)
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
mm, md = types.ModuleType("frappe.model"), types.ModuleType("frappe.model.document")
md.Document = object
sys.modules["frappe.model"], sys.modules["frappe.model.document"] = mm, md
for g in ("sx", "sx.sx", "sx.sx.doctype", "sx.sx.doctype.sx_phieu_luong", "sx.sx.doctype.sx_bang_vao_hop"):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m


def hang_that(tep, ten):
    """ĐÚNG giá trị một hằng trong tệp nguồn (D233: MUC_GIO của bảng vào hộp) — không chép tay vào test."""
    for n in ast.parse(open(tep, encoding="utf-8").read()).body:
        if isinstance(n, ast.Assign) and any(getattr(t, "id", None) == ten for t in n.targets):
            return ast.literal_eval(n.value)
    raise AssertionError(ten)


bvh = types.ModuleType("sx.sx.doctype.sx_bang_vao_hop.sx_bang_vao_hop")
bvh.MUC_GIO = hang_that("sx/sx/doctype/sx_bang_vao_hop/sx_bang_vao_hop.py", "MUC_GIO")
sys.modules[bvh.__name__] = bvh
ut = types.ModuleType("sx.utils")
ut.get_settings = lambda: D()        # mặc định = mức đang dùng: ăn ca 20.000, hệ số ngày lễ 1,2, thâm niên 5%
sys.modules["sx.utils"] = ut

sp = importlib.util.spec_from_file_location("sx.sx.doctype.sx_phieu_luong.sx_phieu_luong",
                                            "sx/sx/doctype/sx_phieu_luong/sx_phieu_luong.py")
PL = importlib.util.module_from_spec(sp)
sp.loader.exec_module(PL)


class Phieu(PL.SXPhieuLuong):
    """SX Phieu Luong giả: dòng con là D; save() chạy validate THẬT."""

    def __init__(self, **kw):
        self.__dict__.update(dict(name=None, employee="NV1", ten_nhan_vien=None, thang=11, nam=2026, docstatus=0,
                                  ngay_san_xuat=0, ho_tro=0, bao_hiem=0, tinh_thuong_tham_nien=1, chi_tiet=[],
                                  dong=[], phat=[], flags=D()))
        self.__dict__.update(kw)

    def get(self, k, d=None):
        return self.__dict__.get(k, d)

    def append(self, f, v):
        r = D(v)
        getattr(self, f).append(r)
        return r

    def set(self, f, v):
        setattr(self, f, list(v))

    def save(self):
        self.validate()


def ham_that(tep, ten, **g):
    """ĐÚNG mã một hàm trong tệp nguồn — test chạy mã thật."""
    goc = open(tep, encoding="utf-8").read()
    fn = next(n for n in ast.parse(goc).body if isinstance(n, ast.FunctionDef) and n.name == ten)
    ns = dict(g)
    exec(compile(ast.Module([fn], []), tep, "exec"), ns)
    return ns[ten]


PHIEU = {}
chung = dict(cint=fu.cint, flt=fu.flt, getdate=fu.getdate, frappe=frappe, _=lambda s: s)
thay_ngay = ham_that("sx/api/chot.py", "_thay_ngay", **chung)
gio_cua_nguoi = ham_that("sx/api/chot.py", "_gio_cua", **chung)
ghi_luong = ham_that("sx/api/chot.py", "_ghi_luong_khoan", _thay_ngay=thay_ngay, _gio_cua=gio_cua_nguoi,
                     _phieu_luong_thang=lambda nv, ngay: PHIEU.setdefault(nv, Phieu(name=f"PL-{nv}", employee=nv)),
                     **chung)
co_gi = ham_that("sx/api/chot.py", "_co_gi_de_ghi", _gio_cua=gio_cua_nguoi, **chung)

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct and not dk else ''}")


def thu(fn):
    try:
        fn()
        return None
    except Loi as e:
        return str(e)


CN = date(2026, 11, 1)          # Chủ nhật — hệ số 1,2
T2 = date(2026, 11, 2)


def bang(*an, dong=None):
    dong = dong if dong is not None else [D(idx=1, nhan_vien="NV1", san_pham="SEN", cach_lam=None, so_hop=100,
                                          don_gia=1000, cong_nhat=0, khoan_chung=0)]
    return D(dong=dong, an_ca=list(an), tong_hop=sum(r.so_hop for r in dong))


def nguoi(nv, an_ca=0, gio=0, gia=33000, gio2=0, gia2=30000):
    return D(nhan_vien=nv, an_ca=an_ca, an_dem=0, so_gio=gio, don_gia_gio=gia if gio else 0,
             so_gio_2=gio2, don_gia_gio_2=gia2 if gio2 else 0)


def gio_cua(p, ngay=None):
    return [(r.ngay, r.so_gio, r.don_gia, r.thanh_tien) for r in p.chi_tiet
            if r.get("theo_gio") and (ngay is None or r.ngay == ngay)]


print("-- có gì để ghi lương --")
kiem("bảng CHỈ có người làm theo giờ (không hộp, không ăn ca) vẫn phải ghi lương",
     co_gi(D(tong_hop=0, an_ca=[nguoi("NV2", gio=1.5)])))
kiem("… không giờ, không ăn, không hộp → không ghi", not co_gi(D(tong_hop=0, an_ca=[nguoi("NV2")])))

print("\n-- chốt ngày Chủ nhật: ghi phiếu lương --")
TRUOC[("NV1", 10, 2026)] = 1_000_000
ds = ghi_luong(D(ngay=CN), bang(nguoi("NV1", an_ca=1, gio=2), nguoi("NV2", gio=3.5), nguoi("NV3", an_ca=1)))
kiem("ghi đủ 3 người: NV1 (hộp + giờ + ăn), NV2 CHỈ làm theo giờ, NV3 chỉ ăn ca",
     sorted(g["employee"] for g in ds) == ["NV1", "NV2", "NV3"], ds)
p1, p2, p3 = PHIEU["NV1"], PHIEU["NV2"], PHIEU["NV3"]
kiem("NV1: một dòng làm theo giờ 2 giờ × 33.000 = 66.000 (đơn giá chốt trên bảng vào hộp)",
     gio_cua(p1) == [(CN, 2.0, 33000.0, 66000.0)], gio_cua(p1))
h = next(r for r in p1.chi_tiet if r.get("theo_gio"))
kiem("… dòng giờ không mang mã hàng / cách làm / số lượng; cột Tên hàng ghi \"Làm theo giờ\"",
     (h.san_pham, h.cach_lam, h.so_luong, h.ten_san_pham) == (None, None, 0, "Làm theo giờ"), h)
n1 = next(r for r in p1.dong if r.ngay == CN)
kiem("lương SP ngày = hộp + giờ (100.000 + 66.000); Chủ nhật nhân 1,2 CẢ tiền giờ; cộng ăn ca",
     (n1.luong_sp, n1.he_so, n1.thu_nhap_ngay) == (166000.0, 1.2, 166000 * 1.2 + 20000), n1)
kiem("lương sản phẩm tháng gồm tiền giờ (đã nhân hệ số)", p1.luong_san_pham == 166000 * 1.2, p1.luong_san_pham)
kiem("thâm niên tính trên lương SP có tiền giờ: 5% × (199.200 + 1.000.000 tháng trước)",
     abs(p1.thuong_tham_nien - 0.05 * (166000 * 1.2 + 1_000_000)) < 1e-6, p1.thuong_tham_nien)
n2 = next(r for r in p2.dong if r.ngay == CN)
kiem("NV2 chỉ làm theo giờ: có dòng ngày, 3,5 giờ × 33.000 × 1,2, không ăn ca",
     gio_cua(p2) == [(CN, 3.5, 33000.0, 115500.0)] and (n2.luong_sp, n2.thu_nhap_ngay, n2.an_ca)
     == (115500.0, 115500 * 1.2, 0), (gio_cua(p2), n2))
kiem("NV3 chỉ ăn ca: không có dòng giờ", gio_cua(p3) == [] and next(r for r in p3.dong if r.ngay == CN).an_ca == 1)

print("\n-- chốt lại / ngày khác --")
ghi_luong(D(ngay=CN), bang(nguoi("NV1", an_ca=1, gio=2.5), nguoi("NV2", gio=3.5)))
kiem("chốt lại ngày (sửa 2 → 2,5 giờ): ghi ĐÈ, không cộng dồn dòng giờ", gio_cua(p1) == [(CN, 2.5, 33000.0, 82500.0)],
     gio_cua(p1))
ghi_luong(D(ngay=T2), bang(nguoi("NV1", gio=1, gia=35000), dong=[]))
kiem("ngày khác: dòng giờ riêng của ngày đó (đơn giá chốt lúc ghi của ngày đó), ngày Chủ nhật giữ nguyên",
     gio_cua(p1) == [(CN, 2.5, 33000.0, 82500.0), (T2, 1.0, 35000.0, 35000.0)], gio_cua(p1))
n = next(r for r in p1.dong if r.ngay == T2)
kiem("… thứ Hai không nhân hệ số", (n.luong_sp, n.he_so, n.thu_nhap_ngay) == (35000.0, 1.0, 35000.0), n)
ghi_luong(D(ngay=CN), bang(nguoi("NV1", an_ca=1, gio=0), nguoi("NV2", gio=3.5)))
kiem("bỏ giờ của NV1 rồi chốt lại → dòng giờ ngày đó mất, hộp còn", gio_cua(p1, CN) == []
     and [(r.san_pham, r.so_luong) for r in p1.chi_tiet if r.ngay == CN] == [("SEN", 100)], p1.chi_tiet)

print("\n-- D233: hai mức làm theo giờ (33.000 / 30.000) --")
kiem("bảng CHỈ có người làm giờ mức 2 vẫn phải ghi lương", co_gi(D(tong_hop=0, an_ca=[nguoi("NV5", gio2=2)])))
PHIEU.clear()
ghi_luong(D(ngay=CN), bang(nguoi("NV1", gio=2, gio2=3), nguoi("NV5", gio2=1.5), dong=[]))
kiem("NV1 làm cả hai mức → HAI dòng giờ, mỗi dòng đúng đơn giá chốt (2 × 33.000, 3 × 30.000)",
     gio_cua(PHIEU["NV1"]) == [(CN, 2.0, 33000.0, 66000.0), (CN, 3.0, 30000.0, 90000.0)], gio_cua(PHIEU["NV1"]))
n1 = next(r for r in PHIEU["NV1"].dong if r.ngay == CN)
kiem("… lương SP ngày = cộng cả hai mức, Chủ nhật nhân 1,2 cả hai", (n1.luong_sp, n1.thu_nhap_ngay)
     == (156000.0, 156000 * 1.2), n1)
kiem("NV5 chỉ làm giờ mức 2 → có phiếu, một dòng 1,5 × 30.000",
     gio_cua(PHIEU["NV5"]) == [(CN, 1.5, 30000.0, 45000.0)], gio_cua(PHIEU["NV5"]))
ghi_luong(D(ngay=CN), bang(nguoi("NV1", gio=2), dong=[]))
kiem("chốt lại sau khi bỏ giờ mức 2 → còn đúng một dòng mức 1 (ghi đè, không sót dòng mức 2 cũ)",
     gio_cua(PHIEU["NV1"]) == [(CN, 2.0, 33000.0, 66000.0)], gio_cua(PHIEU["NV1"]))
kiem("MUC_GIO: mức 1 = so_gio / don_gia_gio (D225, dữ liệu cũ đọc như cũ), mức 2 = so_gio_2 / don_gia_gio_2",
     [(k, kg) for k, kg, _h in bvh.MUC_GIO] == [("so_gio", "don_gia_gio"), ("so_gio_2", "don_gia_gio_2")]
     and [h for _k, _kg, h in bvh.MUC_GIO] == ["don_gia_gio", "don_gia_gio_2"])

print("\n-- kiểm dòng chi tiết --")
p = Phieu(chi_tiet=[D(ngay=T2, theo_gio=1, so_gio=0, don_gia=33000)])
kiem("dòng làm theo giờ mà 0 giờ → chặn", "chưa có số giờ" in (thu(p.save) or ""))
p = Phieu(chi_tiet=[D(ngay=T2, san_pham=None, so_luong=5, don_gia=1000)])
kiem("dòng sản phẩm mất mã hàng → chặn (ô Mã hàng hết bắt buộc trên form)", "chưa chọn mã hàng" in (thu(p.save) or ""))
p = Phieu(chi_tiet=[D(ngay=T2, san_pham="SEN", so_luong=5, so_gio=9, don_gia=1000)])
p.save()
kiem("dòng sản phẩm: số lượng × đơn giá, số giờ (lỡ điền) bỏ", (p.chi_tiet[0].thanh_tien, p.chi_tiet[0].so_gio)
     == (5000.0, 0), p.chi_tiet[0])

print()
print("GIOCONG-HỎNG ({})".format(hong) if hong else "GIOCONG-OK")
sys.exit(1 if hong else 0)
