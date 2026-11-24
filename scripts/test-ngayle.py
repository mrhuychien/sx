"""D241 — ngày tính như Chủ nhật: 27/7 và 24/11 (cạnh 1/1) — lương sản phẩm ngày × hệ số.

Vì sao phải có bài này: hệ số là TIỀN LƯƠNG. Hỏng im lặng theo mấy hướng:
  · 24/11/2026 là thứ Ba — quy tắc cũ chỉ nhìn Chủ nhật / 1-1 nên ngày đó không nhân hệ số, phiếu trông vẫn đủ;
  · ô cấu hình gõ sai (24/111, 31/04) mà lặng lẽ bỏ qua → công nhân đi làm ngày đó mất hệ số;
  · ô trống phải về mặc định (1/1, 27/7, 24/11), không phải "không ngày nào";
  · ngày 24/11 đã chốt trước khi cập nhật: phiếu nháp không tự tính lại → patch tính lại ĐÚNG phiếu cần, không đụng
    phiếu đã duyệt, một phiếu hỏng không làm hỏng cả lần migrate.

Chạy ĐÚNG mã: controller SX Phieu Luong, SX Settings, patch d241 THẬT; frappe giả.
Chạy: python3 scripts/test-ngayle.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
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


CAI = {}         # SX Settings giả — get_settings() trả dict này

frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, title=None: (_ for _ in ()).throw(Loi(str(m)))
frappe.__dict__["_"] = lambda s: s
frappe.db = types.SimpleNamespace(exists=lambda *a, **k: None, get_value=lambda *a, **k: None)
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
for g in ("sx", "sx.sx", "sx.sx.doctype", "sx.sx.doctype.sx_phieu_luong", "sx.sx.doctype.sx_settings", "sx.patches"):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m
ut = types.ModuleType("sx.utils")
ut.get_settings = lambda: D(CAI)
sys.modules["sx.utils"] = ut


def nap(ten, tep):
    sp = importlib.util.spec_from_file_location(ten, tep)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mod
    sp.loader.exec_module(mod)
    return mod


PL = nap("sx.sx.doctype.sx_phieu_luong.sx_phieu_luong", "sx/sx/doctype/sx_phieu_luong/sx_phieu_luong.py")
ST = nap("sx.sx.doctype.sx_settings.sx_settings", "sx/sx/doctype/sx_settings/sx_settings.py")
PA = nap("sx.patches.d241_ngay_nhu_chu_nhat", "sx/patches/d241_ngay_nhu_chu_nhat.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{f' — {ct}' if ct and not dk else ''}")


class Phieu(PL.SXPhieuLuong):
    """SX Phieu Luong giả: dòng con là D; save() chạy validate THẬT."""

    def __init__(self, **kw):
        self.__dict__.update(dict(name=None, employee="NV1", ten_nhan_vien=None, thang=11, nam=2026, docstatus=0,
                                  ngay_san_xuat=0, ho_tro=0, bao_hiem=0, tinh_thuong_tham_nien=0, chi_tiet=[],
                                  dong=[], phat=[], flags=D()))
        self.__dict__.update(kw)

    def get(self, k, d=None):
        return self.__dict__.get(k, d)

    def append(self, f, v):
        r = D(v)
        getattr(self, f).append(r)
        return r

    def save(self):
        self.validate()


def sp(ngay, tien, **kw):
    """Dòng chi tiết sản phẩm `tien` đồng (100 hộp × đơn giá)."""
    return D(dict(ngay=ngay, san_pham="SEN", cach_lam=None, so_luong=100, don_gia=tien / 100, theo_gio=0, so_gio=0), **kw)


def gio(ngay, so_gio, don_gia=33000):
    return D(ngay=ngay, san_pham=None, cach_lam=None, so_luong=0, don_gia=don_gia, theo_gio=1, so_gio=so_gio)


def he_so(p):
    return {str(r.ngay): r.he_so for r in p.dong}


CN, T2, T3 = date(2026, 11, 22), date(2026, 11, 23), date(2026, 11, 24)
assert (CN.weekday(), T2.weekday(), T3.weekday()) == (6, 0, 1)       # 24/11/2026 là thứ Ba — không phải Chủ nhật
assert date(2026, 7, 27).weekday() != 6 and date(2027, 11, 24).weekday() != 6 and date(2026, 9, 2).weekday() != 6

print("-- đọc ô \"Ngày tính như Chủ nhật\" --")
hn, rg, sai = PL.doc_ngay_he_so(PL.NGAY_NHU_CHU_NHAT)
kiem("mặc định = 01/01, 27/07, 24/11 — mọi năm, không ngày riêng năm, không mục sai",
     (hn, rg, sai) == ({(1, 1), (27, 7), (24, 11)}, set(), []), (hn, rg, sai))
hn, rg, sai = PL.doc_ngay_he_so("2/9; 30-04\n01.05  17/02/2026,,29/02")
kiem("dd/mm mọi năm, dd/mm/yyyy riêng năm; ngăn bằng , ; xuống dòng, khoảng trắng; ngày / - . đều được; 29/02 mọi năm",
     hn == {(2, 9), (30, 4), (1, 5), (29, 2)} and rg == {date(2026, 2, 17)} and sai == [], (hn, rg, sai))
hn, rg, sai = PL.doc_ngay_he_so("24/111, 31/04, 30/2, 29/02/2027, 0/1, 24/11/26, abc, 24/11")
kiem("mục sai: tháng / ngày không có thật, 29/02 năm không nhuận, năm 2 số, chữ — còn mục đúng vẫn lấy",
     sai == ["24/111", "31/04", "30/2", "29/02/2027", "0/1", "24/11/26", "abc"] and hn == {(24, 11)}, sai)
kiem("ô trống / None → không có ngày nào, không mục sai (mặc định do nơi gọi quyết)",
     PL.doc_ngay_he_so("") == (set(), set(), []) and PL.doc_ngay_he_so(None) == (set(), set(), []))

print("\n-- ngày hưởng hệ số --")
la = PL._la_ngay_he_so
kiem("mặc định: 24/11/2026 (thứ Ba), 27/07/2026 (thứ Hai), 01/01 → hưởng hệ số; mọi năm (24/11/2027, 27/07/2027)",
     all(la(x) for x in (T3, date(2026, 7, 27), date(2027, 1, 1), date(2027, 11, 24), date(2027, 7, 27))))
kiem("… ngày thường không (23/11, 25/11, 28/07), Chủ nhật vẫn có (26/07/2026 là Chủ nhật)",
     not any(la(x) for x in (T2, date(2026, 11, 25), date(2026, 7, 28))) and la(CN) and la(date(2026, 7, 26)))
tuy = PL.doc_ngay_he_so("02/09, 17/02/2026")
kiem("danh sách riêng (02/09, 17/02/2026): 2/9 mọi năm, 17/02 chỉ năm 2026; 24/11 hết hệ số; Chủ nhật luôn có",
     la(date(2026, 9, 2), tuy) and la(date(2030, 9, 2), tuy) and la(date(2026, 2, 17), tuy)
     and not la(date(2027, 2, 17), tuy) and not la(T3, tuy) and la(CN, tuy))
kiem("danh sách không có ngày nào → chỉ Chủ nhật", la(CN, (set(), set(), [])) and not la(date(2026, 1, 1), (set(), set(), [])))
kiem("nhận chuỗi ngày (như đọc từ DB)", la("2026-11-24") and not la("2026-11-23"))

print("\n-- phiếu lương: tính hệ số theo SX Settings --")


def lam_phieu():
    p = Phieu(chi_tiet=[sp(CN, 100_000), sp(T2, 100_000), sp(T3, 100_000), gio(T3, 2)],
              dong=[D(ngay=CN, an_ca=1, an_dem=0), D(ngay=T2, an_ca=1, an_dem=0), D(ngay=T3, an_ca=1, an_dem=0)])
    p.save()
    return p


CAI.clear()
p = lam_phieu()
n3 = next(r for r in p.dong if r.ngay == T3)
kiem("SX Settings chưa có ô (site chưa migrate) → mặc định: 24/11 nhân 1,2 như Chủ nhật, 23/11 không",
     he_so(p) == {str(CN): 1.2, str(T2): 1.0, str(T3): 1.2}, he_so(p))
kiem("… 24/11: lương SP (hộp + 2 giờ × 33.000) × 1,2 + ăn ca; tiền ăn KHÔNG nhân",
     (n3.luong_sp, n3.thu_nhap_ngay) == (166_000.0, 166_000 * 1.2 + 20_000), n3)
kiem("… lương sản phẩm tháng = Σ (lương SP × hệ số)",
     abs(p.luong_san_pham - (100_000 * 1.2 + 100_000 + 166_000 * 1.2)) < 1e-6, p.luong_san_pham)
CAI.update(ngay_nhu_chu_nhat="   ")
kiem("ô chỉ có khoảng trắng = trống → mặc định", he_so(lam_phieu())[str(T3)] == 1.2)
CAI.update(ngay_nhu_chu_nhat="02/09")
kiem("SX Settings ghi 02/09 → 24/11 hết hệ số (danh sách là của SX Settings, không cộng thêm mặc định)",
     he_so(lam_phieu()) == {str(CN): 1.2, str(T2): 1.0, str(T3): 1.0})
CAI.update(ngay_nhu_chu_nhat="23/11/2026, 24/11", he_so_ngay_le=1.5)
kiem("hệ số SX Settings 1,5 áp cho cả Chủ nhật lẫn ngày tính như Chủ nhật (23/11/2026 riêng năm, 24/11 mọi năm)",
     he_so(lam_phieu()) == {str(CN): 1.5, str(T2): 1.5, str(T3): 1.5})
CAI.clear()

print("\n-- SX Settings: chặn lưu ngày gõ sai --")


class CaiDat(ST.SXSettings):
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def get(self, k, d=None):
        return self.__dict__.get(k, d)


def luu(v):
    try:
        CaiDat(ngay_nhu_chu_nhat=v).validate()
    except Loi as e:
        return str(e)


kiem("danh sách đúng / ô trống → lưu được", luu("01/01, 27/07, 24/11") is None and luu("") is None and luu(None) is None)
e = luu("01/01, 24/111, 31/04")
kiem("gõ sai → chặn, nói đúng mục sai và cách ghi", e and "24/111, 31/04" in e and "dd/mm" in e and "01/01" not in
     e.split(":")[1].split("không phải")[0], e)

print("\n-- patch d241: điền ô + tính lại phiếu nháp --")
cf = PL._cau_hinh()
dong = [D(parent="P1", ngay=date(2026, 11, 23), he_so=1.0), D(parent="P1", ngay=T3, he_so=1.0),
        D(parent="P2", ngay=T3, he_so=1.2), D(parent="P3", ngay=T2, he_so=1.0),
        D(parent="P4", ngay=date(2026, 7, 27), he_so=1), D(parent="P1", ngay=date(2027, 11, 24), he_so=1.0),
        D(parent="P5", ngay=CN, he_so=1.2), D(parent="P6", ngay="2026-11-24", he_so=None)]
kiem("phiếu cần tính lại: có ngày hưởng hệ số mà hệ số lệch (P1 24/11 hệ số 1, P4 27/7, P6 hệ số trống); P2, P5 đã "
     "đúng, P3 ngày thường — không; mỗi phiếu một lần", PA.phieu_can_tinh_lai(dong, cf) == ["P1", "P4", "P6"],
     PA.phieu_can_tinh_lai(dong, cf))

GHI, LUU, LOC, XOA_CACHE, COMMIT = {}, [], [], [], []


class PhieuDB:
    def __init__(self, ten):
        self.ten = ten

    def save(self, ignore_permissions=False):
        if self.ten == "P4":
            raise Loi("Ngày 27/07/2026 không thuộc tháng 8/2026.")
        LUU.append((self.ten, ignore_permissions))


def chay_patch(gia_tri):
    GHI.clear(); LUU.clear(); LOC.clear(); XOA_CACHE.clear(); COMMIT.clear()
    CAI.clear()
    if gia_tri is not None:
        CAI["ngay_nhu_chu_nhat"] = gia_tri

    def dat(dt, f, v):
        GHI[(dt, f)] = v
        CAI[f] = v

    frappe.db = types.SimpleNamespace(
        exists=lambda dt, n=None: dt == "DocType" and n == "SX Settings",
        get_single_value=lambda dt, f: CAI.get(f),
        set_single_value=dat,
        commit=lambda: COMMIT.append(1))
    frappe.clear_document_cache = lambda dt, n=None: XOA_CACHE.append((dt, n))
    frappe.get_all = lambda dt, filters=None, fields=None, order_by=None: (LOC.append((dt, filters)), dong)[1]
    frappe.get_doc = lambda dt, n: PhieuDB(n)
    PA.execute()


chay_patch(None)
kiem("ô trống → điền 01/01, 27/07, 24/11, xoá cache SX Settings",
     GHI == {("SX Settings", "ngay_nhu_chu_nhat"): PL.NGAY_NHU_CHU_NHAT}
     and XOA_CACHE == [("SX Settings", "SX Settings")], (GHI, XOA_CACHE))
kiem("chỉ đọc dòng ngày của phiếu NHÁP (docstatus 0) — phiếu đã duyệt / huỷ không đụng",
     LOC == [("SX Phieu Luong Ngay", {"parenttype": "SX Phieu Luong", "docstatus": 0})], LOC)
kiem("lưu lại đúng phiếu cần (P1, P6), bỏ quyền; P4 lỗi khi lưu → báo, KHÔNG dừng migrate; commit",
     LUU == [("P1", True), ("P6", True)] and COMMIT, LUU)
chay_patch("02/09")
kiem("ô đã có giá trị → để nguyên; tính theo giá trị đó (24/11 không còn là ngày hệ số → không phiếu nào cần lưu)",
     GHI == {} and LUU == [], (GHI, LUU))
CAI.clear()

print("\n-- cấu hình --")
st = json.load(open("sx/sx/doctype/sx_settings/sx_settings.json", encoding="utf-8"))
o = {f["fieldname"]: f for f in st["fields"]}
fo = st["field_order"]
kiem("SX Settings: ô Ngày tính như Chủ nhật (Small Text) ngay sau hệ số; mặc định trùng hằng NGAY_NHU_CHU_NHAT",
     o["ngay_nhu_chu_nhat"]["fieldtype"] == "Small Text" and fo.index("ngay_nhu_chu_nhat") == fo.index("he_so_ngay_le") + 1
     and o["ngay_nhu_chu_nhat"]["default"] == PL.NGAY_NHU_CHU_NHAT
     and "Bỏ trống = " + PL.NGAY_NHU_CHU_NHAT in o["ngay_nhu_chu_nhat"]["description"])
kiem("… nhãn hệ số không còn ghi \"1-1\" (giờ áp cho mọi ngày trong danh sách)",
     "1-1" not in o["he_so_ngay_le"]["label"] and "ngày lễ" in o["he_so_ngay_le"]["label"])
pt = open("sx/patches.txt", encoding="utf-8").read()
kiem("patch d241 ở post_model_sync (ô SX Settings phải có trước khi patch ghi)",
     pt.index("sx.patches.d241_ngay_nhu_chu_nhat") > pt.index("[post_model_sync]"))

print("NGAYLE-HỎNG ({})".format(hong) if hong else "NGAYLE-OK")
sys.exit(1 if hong else 0)
