"""D141 (W20, W12) — nhật ký cát rang BM.08.03 và xem xét tháng theo ngày sản xuất.

Vì sao phải có bài này:
  · Số ngày cát đã dùng là con số app TỰ ĐẾM — ghi bù một ngày cũ, sửa ngày, xoá một dòng
    mà chuỗi sau không tính lại thì sổ nói sai mà không ai thấy.
  · Đổi nguồn cát mà không nhắc kiểm kim loại nặng / lưu lọ mẫu → mất đúng cái tài liệu đòi.
  · Kim loại nặng Không đạt mà không thành phiếu sự cố → lô đã rang bằng cát đó không ai xem.
  · Dòng Ban ISO đã ký mà QC vẫn sửa được → chữ ký xem xét vô nghĩa.
  · Tỷ lệ hoàn tất lượt chia cho MỌI ngày lịch (Chủ nhật, ngày chưa tới) → tháng nào cũng
    "thiếu" mà không ai làm sai; ngày CÓ sản xuất mà QC bỏ trắng thì lại không lộ ra.

Nạp sx/qc/cat.py, controller SX Nhat Ky Cat, sx/api/qc_cat.py, sx/api/qc.py, sx/qc/nhac.py
THẬT; frappe giả. Chạy: python3 scripts/test-cat.py   (verify.sh gọi sẵn)
"""

import copy
import importlib.util
import json
import os
import re
import sys
import types
from datetime import date, datetime, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

HOM_NAY = date(2026, 10, 8)        # thứ Năm
NGUOI = {"u": "qc@x", "roles": ["SX QC"]}
CAI_DAT = {"cat_so_ngay_toi_da": 0}
BAO = []
DB = {}
SO = {"n": 0}


def bang(dt):
    return DB.setdefault(dt, {})


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


def _s(v):
    return str(v)[:10] if isinstance(v, (date, datetime)) else str(v if v is not None else "")


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "between" and not (_s(m[0]) <= _s(x) <= _s(m[1])):
                return False
            if op == "<" and not (x is not None and (_s(x) < _s(m) if k == "ngay" else float(x) < float(m))):
                return False
            if op == "<=" and not _s(x) <= _s(m):
                return False
            if op == ">=" and not _s(x) >= _s(m):
                return False
            if op == "!=" and _s(x) == _s(m):
                return False
            if op == "is" and m == "not set" and x:
                return False
            if op == "is" and m == "set" and not x:
                return False
            if op == "in" and x not in m:
                return False
        elif _s(x) != _s(v):
            return False
    return True


def get_all(dt, filters=None, fields=None, order_by=None, limit=None, pluck=None, **k):
    ds = [Doc(x) for x in bang(dt).values() if _khop(x, filters)]
    if order_by:
        f, *chieu = order_by.split(",")[0].split()
        ds.sort(key=lambda x: _s(x.get(f)), reverse=bool(chieu) and chieu[0].lower() == "desc")
    if limit:
        ds = ds[:limit]
    if pluck:
        return [x.get(pluck) for x in ds]
    if fields:                                   # như frappe: chỉ trả cột hỏi, cột không có = None
        return [Doc({f: x.get(f) for f in fields}) for x in ds]
    return ds


def _get_value(dt, ten, fld=None, as_dict=False, **k):
    if isinstance(ten, dict):
        h = next((x for x in bang(dt).values() if _khop(x, ten)), None)
    else:
        h = bang(dt).get(ten)
    if h is None:
        return None
    if isinstance(fld, str):
        return h.get(fld)
    d = Doc({c: h.get(c) for c in fld})
    return d if as_dict else tuple(d.values())


def _exists(dt, ten=None):
    if isinstance(ten, dict):
        h = next((x for x in bang(dt).values() if _khop(x, ten)), None)
        return h["name"] if h else None
    return ten if ten in bang(dt) else None


def _set_value(dt, ten, f, v=None, update_modified=True):
    bang(dt)[ten].update(f if isinstance(f, dict) else {f: v})


try:
    import jinja2
except ImportError:
    jinja2 = None


def _render(path, ctx):
    if jinja2 is None:
        return ""
    fu_in = types.SimpleNamespace(formatdate=lambda v, f=None: fu.getdate(v).strftime(
        "%d/%m" if f == "dd/MM" else "%d/%m/%Y"))
    return jinja2.Environment(loader=jinja2.FileSystemLoader(".")).get_template(path).render(
        frappe=types.SimpleNamespace(utils=fu_in), **ctx)


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, **k: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.msgprint = lambda m, **k: BAO.append(str(m))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})


class _Phien:
    user = property(lambda s: NGUOI["u"])


frappe.session = _Phien()
frappe.get_roles = lambda u=None: list(NGUOI["roles"])
frappe.get_all = get_all
frappe.get_list = get_all
frappe.render_template = lambda p, ctx: _render(p, ctx)
frappe.get_cached_doc = lambda dt, *a: Doc(CAI_DAT)
frappe.db = types.SimpleNamespace(get_value=_get_value, exists=_exists, set_value=_set_value,
                                  table_exists=lambda dt: True, count=lambda dt, f=None: len(get_all(dt, f)))
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.getdate = lambda x=None: (x.date() if isinstance(x, datetime) else x if isinstance(x, date)
                             else date.fromisoformat(str(x)[:10]) if x else HOM_NAY)
fu.nowdate = lambda: str(HOM_NAY)
fu.today = fu.nowdate
fu.add_days = lambda d, n: fu.getdate(d) + timedelta(days=n)
fu.add_months = lambda d, n: fu.getdate(d)
fu.now_datetime = lambda: datetime(2026, 10, 8, 10, 0, 0)
fu.get_datetime = lambda x=None: x
fu.date_diff = lambda a, b: (fu.getdate(a) - fu.getdate(b)).days
frappe.utils = fu


class Document:
    """Document giả: insert / save chạy validate → lưu → on_update; delete chạy on_trash."""

    def __init__(self, d=None):
        self.__dict__["_d"] = dict(d or {})
        self.__dict__["_moi"] = "name" not in self._d
        self.__dict__["_cu"] = None if self._moi else copy.deepcopy(self._d)

    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.__dict__["_d"].get(k)

    def __setattr__(self, k, v):
        self.__dict__["_d"][k] = v

    def get(self, k, d=None):
        return self._d.get(k, d)

    def set(self, k, v):
        self._d[k] = v

    def update(self, d):
        self._d.update(d)

    def as_dict(self):
        return Doc(self._d)

    def is_new(self):
        return self._moi

    def get_doc_before_save(self):
        return Doc(self._cu) if self._cu else None

    def db_set(self, f, v=None, update_modified=True):
        dd = f if isinstance(f, dict) else {f: v}
        self._d.update(dd)
        bang(self._d["doctype"])[self._d["name"]].update(dd)

    def _luu(self):
        self.validate()
        dt = self._d["doctype"]
        if self._moi:
            SO["n"] += 1
            self._d["name"] = f"CAT-2026-{SO['n']:05d}"
            self._d.setdefault("creation", str(HOM_NAY) + " 09:00:00")
        if dt == "SX Nhat Ky Cat" and self._d.get("ncc_cat"):
            self._d["ten_ncc"] = (bang("Supplier").get(self._d["ncc_cat"]) or {}).get("supplier_name")
        bang(dt)[self._d["name"]] = dict(self._d)
        if hasattr(type(self), "on_update"):
            self.on_update()
        self.__dict__["_moi"] = False
        self.__dict__["_cu"] = copy.deepcopy(self._d)
        return self

    def insert(self, ignore_permissions=False):
        return self._luu()

    def save(self, ignore_permissions=False):
        return self._luu()


class SuCo(Doc):
    def insert(self, ignore_permissions=False):
        n = f"SC-2026-{len(bang('SX Su Co')) + 1:04d}"
        self["name"] = n
        bang("SX Su Co")[n] = dict(self)
        return self


md = types.ModuleType("frappe.model.document")
md.Document = Document
sys.modules["frappe.model"] = types.ModuleType("frappe.model")
sys.modules["frappe.model.document"] = md
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.qc", "sx.api"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


nap("sx.qc.muc", "sx/qc/muc.py")
nap("sx.qc.nguong", "sx/qc/nguong.py")
nap("sx.qc.quyen", "sx/qc/quyen.py")
for t in ("san_pham", "su_co", "xuat"):
    nap(f"sx.qc.{t}", f"sx/qc/{t}.py")
NH = nap("sx.qc.nhac", "sx/qc/nhac.py")
nap("sx.qc.dong_vat", "sx/qc/dong_vat.py")
CAT = nap("sx.qc.cat", "sx/qc/cat.py")
nap("sx.qc.so_do", "sx/qc/so_do.py")
nap("sx.qc.thiet_bi", "sx/qc/thiet_bi.py")
nap("sx.qc.kiem_nghiem", "sx/qc/kiem_nghiem.py")
nap("sx.qc.viec_dinh_ky", "sx/qc/viec_dinh_ky.py")
nap("sx.qc.khac_phuc", "sx/qc/khac_phuc.py")
Q = nap("sx.api.qc", "sx/api/qc.py")
A = nap("sx.api.qc_cat", "sx/api/qc_cat.py")
CTL = nap("cat_ctl", "sx/qc/doctype/sx_nhat_ky_cat/sx_nhat_ky_cat.py")


def get_doc(a, b=None):
    if isinstance(a, dict):
        return SuCo(a) if a["doctype"] == "SX Su Co" else CTL.SXNhatKyCat(a)
    d = dict(copy.deepcopy(bang(a)[b]), doctype=a)
    return CTL.SXNhatKyCat(d) if a == CAT.PT else Document(d)


def delete_doc(dt, ten, **k):
    d = get_doc(dt, ten)
    d.on_trash()
    bang(dt).pop(ten)


frappe.get_doc = get_doc
frappe.delete_doc = delete_doc

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


def thu(f):
    try:
        f()
    except Exception as e:  # noqa: BLE001
        return str(e) or type(e).__name__
    return None


def vai(*r, u=None):
    NGUOI["roles"] = list(r)
    NGUOI["u"] = u or {"SX QC": "qc@x", "ISO Manager": "iso@x"}.get(r[0], "x@x")


bang("Supplier").update({
    "CAT-A": {"name": "CAT-A", "supplier_name": "Cát sông Lô", "custom_loai_ncc": "Cát rang",
              "custom_ncc_duyet": 1, "disabled": 0},
    "CAT-B": {"name": "CAT-B", "supplier_name": "Cát Minh Anh", "custom_loai_ncc": "Cát rang",
              "custom_ncc_duyet": 1, "disabled": 0},
    "DX-1": {"name": "DX-1", "supplier_name": "NCC đỗ", "custom_loai_ncc": "Nguyên liệu thực phẩm",
             "custom_ncc_duyet": 1, "disabled": 0}})
bang("SX QC Cong Doan")["3 Rang"] = {"name": "3 Rang"}


def ghi(**k):
    return A.ghi(json.dumps(k))


def so():
    """{ngày: (số ngày, nguồn, thay, đổi)} của cả sổ."""
    return {_s(x["ngay"]): (x["so_ngay_dung"], x["ncc_cat"], x["thay_cat"], x["doi_nguon"])
            for x in bang(CAT.PT).values()}


def ten(ngay):
    return next(n for n, x in bang(CAT.PT).items() if _s(x["ngay"]) == ngay)


# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- đếm ngày cát, đổi nguồn (hàm thuần) --")
kt = CAT.ke_tiep
kiem("dòng đầu sổ không thay cát: giữ số ngày khai tay; khai 0 / trống → 1",
     kt(None, {"ncc_cat": "A", "so_ngay_dung": 5})["so_ngay_dung"] == 5 and kt(None, {"ncc_cat": "A"})["so_ngay_dung"] == 1)
kiem("dòng sau: cộng 1, nguồn bỏ trống thì giữ nguồn cát đang dùng",
     kt({"ncc_cat": "A", "so_ngay_dung": 5}, {}) == {"so_ngay_dung": 6, "ncc_cat": "A", "thay_cat": 0, "doi_nguon": 0})
kiem("thay cát CÙNG nguồn: về 1, không phải đổi nguồn",
     kt({"ncc_cat": "A", "so_ngay_dung": 9}, {"ncc_cat": "A", "thay_cat": 1})
     == {"so_ngay_dung": 1, "ncc_cat": "A", "thay_cat": 1, "doi_nguon": 0})
kiem("nguồn KHÁC mà quên tích thay cát → tự thay + đổi nguồn",
     kt({"ncc_cat": "A", "so_ngay_dung": 9}, {"ncc_cat": "B"})
     == {"so_ngay_dung": 1, "ncc_cat": "B", "thay_cat": 1, "doi_nguon": 1})
kiem("dòng trước chưa có nguồn → ghi nguồn lần đầu không phải đổi nguồn",
     kt({"ncc_cat": "", "so_ngay_dung": 3}, {"ncc_cat": "B"})["doi_nguon"] == 0)
CK = CAT.cho_kln([{"doi_nguon": 1, "kln": "", "luu_lo_mau": 1}, {"doi_nguon": 1, "kln": "Đạt", "luu_lo_mau": 0},
                  {"doi_nguon": 1, "kln": "Đạt", "luu_lo_mau": 1}, {"doi_nguon": 1, "kln": "Không đạt"},
                  {"doi_nguon": 0, "kln": ""}])
kiem("đổi nguồn còn treo: chưa có KLN Đạt HOẶC chưa lọ mẫu; Không đạt đã thành sự cố → không treo",
     len(CK) == 2, CK)

# ═══ 2. Ghi sổ, chuỗi ngày ════════════════════════════════════════════════
print("\n-- ghi sổ, ghi bù, xoá, sửa ngày: cả chuỗi tính lại --")
vai("SX QC")
kiem("dòng đầu sổ phải có nguồn cát", "nguồn cát" in (thu(lambda: ghi(ngay="2026-10-01")) or ""))
r = ghi(ngay="2026-10-01", ncc_cat="CAT-A", so_ngay_dau=5, ve_sinh_thung=1, ve_sinh_khay=1, cam_quan="Đạt")
kiem("dòng đầu sổ: số ngày khai tay (cát dùng từ trước khi có app), người ghi tự điền",
     r["so_ngay_dung"] == 5 and bang(CAT.PT)[r["name"]]["nguoi_ghi"] == "qc@x", r)
ghi(ngay="2026-10-02")
ghi(ngay="2026-10-05", ncc_cat="CAT-A", thay_cat=1)
ghi(ngay="2026-10-06", so_ngay_dau=40)
r = ghi(ngay="2026-10-07", ncc_cat="CAT-B")
ghi(ngay="2026-10-08")
kiem("tự đếm; thay cát → 1; số khai tay ở dòng không phải đầu sổ bị bỏ qua; đổi NCC → đổi nguồn",
     so() == {"2026-10-01": (5, "CAT-A", 0, 0), "2026-10-02": (6, "CAT-A", 0, 0), "2026-10-05": (1, "CAT-A", 1, 0),
              "2026-10-06": (2, "CAT-A", 0, 0), "2026-10-07": (1, "CAT-B", 1, 1), "2026-10-08": (2, "CAT-B", 0, 0)}
     and r["doi_nguon"] == 1, so())
ghi(ngay="2026-10-03")
kiem("ghi bù 03/10 (không thay) → ngày thứ 7; dòng sau lần thay không đổi",
     so()["2026-10-03"][0] == 7 and so()["2026-10-05"][0] == 1 and so()["2026-10-06"][0] == 2)
vai("SX QC", u="qc2@x")
kiem("QC khác không xoá được dòng người khác", thu(lambda: A.xoa(ten("2026-10-05"))) is not None)
vai("SX QC")
A.xoa(ten("2026-10-05"))
kiem("xoá dòng thay cát 05/10 → 06/10 nối tiếp 03/10 thành ngày thứ 8; đổi nguồn 07/10 vẫn 1",
     so()["2026-10-06"][0] == 8 and so()["2026-10-07"][:2] == (1, "CAT-B"), so())
ghi(name=ten("2026-10-02"), ngay="2026-10-04")
kiem("dời ngày 02/10 → 04/10: chuỗi tính lại từ ngày SỚM hơn (03/10 = 6, 04/10 = 7, 06/10 = 8)",
     "2026-10-02" not in so() and so()["2026-10-03"][0] == 6 and so()["2026-10-04"][0] == 7
     and so()["2026-10-06"][0] == 8, so())
ghi(ngay="2026-10-03", thay_cat=1)
kiem("sửa 03/10 thành thay cát → các ngày sau đếm lại (04/10 = 2, 06/10 = 3)", so()["2026-10-03"][0] == 1
     and so()["2026-10-04"][0] == 2 and so()["2026-10-06"][0] == 3, so())
r = ghi(ngay="2026-10-08", ve_sinh_thung=1)
kiem("ghi lại một ngày đã có → SỬA dòng đó, không lập dòng thứ hai",
     len([x for x in so() if x == "2026-10-08"]) == 1 and bang(CAT.PT)[r["name"]]["ve_sinh_thung"] == 1)
kiem("hai dòng cùng ngày trên Desk → chặn", "đã có nhật ký cát" in (thu(
    lambda: CTL.SXNhatKyCat({"doctype": CAT.PT, "ngay": "2026-10-08", "ncc_cat": "CAT-B"}).insert()) or ""))
kiem("ngày sau hôm nay → chặn", "sau hôm nay" in (thu(lambda: ghi(ngay="2026-10-09", ncc_cat="CAT-B")) or ""))
BAO.clear()
ghi(ngay="2026-10-08", ncc_cat="DX-1")
kiem("nguồn không phải NCC loại Cát rang → báo (không chặn — W09)", any("Cát rang" in b for b in BAO), BAO)
ghi(ngay="2026-10-08", ncc_cat="CAT-B")
vai("ISO Manager")
kiem("Ban ISO không ghi nhật ký (người xem xét không tự ghi)", thu(lambda: ghi(ngay="2026-10-08")) is not None)

# ═══ 3. Đổi nguồn: kim loại nặng, lọ mẫu, sự cố ════════════════════════════
print("\n-- đổi nguồn: kim loại nặng, lọ mẫu, sự cố --")
vai("SX QC")
q = A.tong_quan()
kiem("tổng quan: cát đang dùng (08/10, ngày thứ 2, Cát Minh Anh), đổi nguồn 07/10 còn treo, lần thay gần nhất",
     q["hien_tai"]["ngay"] == "2026-10-08" and q["hien_tai"]["so_ngay_dung"] == 2 and q["ngay_thay"] == "2026-10-07"
     and [x["ngay"] for x in q["cho_kln"]] == ["2026-10-07"] and q["hom_nay_co"] == ten("2026-10-08")
     and q["hom_nay_dong"]["name"] == ten("2026-10-08") and A.tong_quan("2026-09")["hom_nay_dong"]["ngay"] == "2026-10-08",
     (q["hien_tai"], q["ngay_thay"], q["cho_kln"]))
kiem("… danh sách nguồn chỉ NCC loại Cát rang; đầu sổ 01/10; QC ghi được, không phải ISO",
     sorted(x["name"] for x in q["ncc"]) == ["CAT-A", "CAT-B"]
     and q["ngay_dau_so"] == "2026-10-01" and q["duoc_ghi"] and not q["la_iso"], q["ncc"])
kiem("ghi kết quả vào dòng KHÔNG đổi nguồn → chặn",
     "không phải lần đổi nguồn" in (thu(lambda: A.cap_nhat_kln(ten("2026-10-08"), json.dumps({"kln": "Đạt"}))) or ""))
A.cap_nhat_kln(ten("2026-10-07"), json.dumps({"kln": "Đã gửi mẫu"}))
dv = CAT.nhac(HOM_NAY)
m = [x for x in NH.tinh(HOM_NAY, [], [], {}, cat=dv) if x["route"] == "#/qc/cat"]
kiem("đã gửi mẫu, chưa lọ mẫu → nhắc mức thường, nói rõ thiếu gì",
     len(m) == 1 and m[0]["muc_do"] == "thuong" and "chờ kết quả kim loại nặng" in m[0]["tieu_de"]
     and "chưa lưu lọ mẫu" in m[0]["tieu_de"], m)
A.cap_nhat_kln(ten("2026-10-07"), json.dumps({"kln": "", "luu_lo_mau": 1}))
m = [x for x in NH.tinh(HOM_NAY, [], [], {}, cat=CAT.nhac(HOM_NAY)) if x["route"] == "#/qc/cat"]
kiem("chưa gửi mẫu kim loại nặng → mức CAO", len(m) == 1 and m[0]["muc_do"] == "cao", m)
vai("ISO Manager")
r = A.cap_nhat_kln(ten("2026-10-07"), json.dumps({"kln": "Không đạt", "so_phieu_kln": "KN-77"}))
sc = bang("SX Su Co").get(r["su_co"] or "") or {}
kiem("Ban ISO ghi kết quả được; Không đạt → phiếu sự cố Nhật ký cát, mức Cao, công đoạn 3 Rang, nói nguồn + phiếu",
     sc.get("nguon") == "Nhật ký cát" and sc.get("muc_do") == "Cao" and sc.get("cong_doan") == "3 Rang"
     and "Cát Minh Anh" in sc.get("mo_ta", "") and "KN-77" in sc.get("mo_ta", ""), sc)
A.cap_nhat_kln(ten("2026-10-07"), json.dumps({"kln": "Không đạt", "so_phieu_kln": "KN-77b"}))
kiem("lưu lại lần nữa → KHÔNG lập phiếu thứ hai", len(bang("SX Su Co")) == 1)
kiem("Không đạt rồi thì hết treo (đã thành sự cố)", not CAT.nhac(HOM_NAY)["cho_kln"])
A.cap_nhat_kln(ten("2026-10-07"), json.dumps({"kln": "Đạt", "luu_lo_mau": 1}))
vai("SX QC")

# ═══ 4. Nhắc: ngày có rang thiếu nhật ký, số ngày tối đa ═════════════════════
print("\n-- nhắc: ngày có rang thiếu nhật ký, tối đa (C19) --")
c = CAT.nhac(HOM_NAY, {"2026-10-01", "2026-10-02", "2026-10-07", "2026-10-08", "2026-09-20"})
kiem("ngày có rang (theo lượt ghi nhiệt độ rang) mà không có dòng → thiếu; cửa sổ 7 ngày; hôm nay có dòng → không",
     c["thieu"] == ["2026-10-02"] and not c["hom_nay_chua"], c["thieu"])
A.xoa(ten("2026-10-08"))
c = CAT.nhac(HOM_NAY, {"2026-10-08"})
m = NH.tinh(HOM_NAY, [], [], {}, cat=c)
kiem("hôm nay có rang mà chưa ghi → nhắc trong ngày", c["hom_nay_chua"]
     and any(x["tieu_de"].startswith("Hôm nay có rang") for x in m))
ghi(ngay="2026-10-08", ve_sinh_thung=1, ve_sinh_khay=1)
kiem("C19 chưa chốt (tối đa = 0) → chỉ đếm, KHÔNG nhắc số ngày",
     not [x for x in NH.tinh(HOM_NAY, [], [], {}, cat=CAT.nhac(HOM_NAY)) if "tối đa" in x["tieu_de"]])
CAI_DAT["cat_so_ngay_toi_da"] = 2
m = [x for x in NH.tinh(HOM_NAY, [], [], {}, cat=CAT.nhac(HOM_NAY)) if "tối đa" in x["tieu_de"]]
kiem("điền tối đa (khi C19 chốt) → tới ngưỡng thì nhắc thay cát", len(m) == 1 and "2 ngày" in m[0]["tieu_de"], m)
CAI_DAT["cat_so_ngay_toi_da"] = 0
qcpy = open("sx/api/qc.py", encoding="utf-8").read()
kiem("sx.api.qc.nhac lấy ngày có rang từ nhiệt độ rang của lượt và truyền vào nhắc cát",
     '"rang_nhiet_do"])' in qcpy and "_cat.nhac(d, rang)" in qcpy)

bang(CAT.PT)[ten("2026-10-01")]["creation"] = "2026-10-01 08:00:00"
loi = thu(lambda: A.xoa(ten("2026-10-01")))
kiem("người ghi không xoá được dòng ghi từ hôm trước (chỉ Ban ISO)", loi and "Ban ISO" in loi, loi)

# ═══ 5. Ban ISO xem xét tháng (W12) ═══════════════════════════════════════
print("\n-- xem xét tháng: ngày sản xuất, nhật ký cát, chữ ký --")


def luot(ngay, ten_l, ds=1, **k):
    n = f"QC-{ngay}-{ten_l}"
    bang("SX QC Round")[n] = {"name": n, "ngay": ngay, "luot": ten_l, "docstatus": ds, "ghi_muon": 0,
                              "nhap_lai_tu_giay": 0, "reviewed_on": None, "rang_nhiet_do": 260, **k}


for ng in ("2026-10-01", "2026-10-05"):
    for t in ("Đầu sáng", "Trưa", "Cuối chiều"):
        luot(ng, t)
luot("2026-10-02", "Đầu sáng")
luot("2026-10-02", "Trưa", ghi_muon=1)
luot("2026-10-06", "Đầu sáng", ds=0)
for ng, ds in (("2026-10-01", 0), ("2026-10-02", 0), ("2026-10-03", 0), ("2026-10-04", 2), ("2026-10-10", 0)):
    bang("SX Ngay San Xuat")[f"SXN-{ng}"] = {"name": f"SXN-{ng}", "ngay": ng, "docstatus": ds}
bang("SX Su Co").update({
    "SC-9": {"name": "SC-9", "ngay": "2026-10-03", "trang_thai": "Mở", "dien_tap": 0, "cong_doan": "3 Rang",
             "loai": "Khác"},
    "SC-10": {"name": "SC-10", "ngay": "2026-10-03", "trang_thai": "Mở", "dien_tap": 1, "loai": "Khác"}})
vai("ISO Manager")
db = Q.dashboard("2026-10-01", "2026-10-31")
kiem("ngày sản xuất = có phiếu ngày SX (không tính phiếu huỷ) ∪ có lượt (cả lượt dở) ∪ có nhật ký cát, tới hôm nay",
     db["ngay_sx"] == ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06",
                       "2026-10-07", "2026-10-08"], db["ngay_sx"])
bang("SX Ngay San Xuat").update({"SXN-0920": {"name": "SXN-0920", "ngay": "2026-09-20", "docstatus": 2},
                                 "SXN-0921": {"name": "SXN-0921", "ngay": "2026-09-21", "docstatus": 0}})
luot("2026-09-22", "Đầu sáng", ds=0)
kiem("phiếu ngày SX đã huỷ không làm ra ngày sản xuất; ngày chỉ có lượt đang làm dở vẫn là ngày sản xuất",
     Q.dashboard("2026-09-20", "2026-09-22")["ngay_sx"] == ["2026-09-21", "2026-09-22"])
kiem("mẫu số = 3 lượt × 8 ngày sản xuất (không phải 31 ngày lịch); ngày chưa tới 10/10 không tính",
     db["can_co"] == 24 and db["so_ngay_sx"] == 8 and db["so_luot"] == 8 and db["ty_le_hoan_tat"] == 33.3,
     (db["can_co"], db["so_luot"], db["ty_le_hoan_tat"]))
kiem("ngày sản xuất thiếu lượt (kể cả ngày có báo mẻ mà QC không đi lượt nào)",
     db["ngay_thieu"] == ["2026-10-02", "2026-10-03", "2026-10-04", "2026-10-06", "2026-10-07", "2026-10-08"],
     db["ngay_thieu"])
kiem("theo ngày: sự cố thật (bỏ diễn tập), có nhật ký cát / thay cát",
     db["theo_ngay"]["2026-10-03"]["su_co"] == 1 and db["theo_ngay"]["2026-10-03"].get("cat") == "thay"
     and db["theo_ngay"]["2026-10-04"].get("cat") == "co" and "cat" not in db["theo_ngay"]["2026-10-02"],
     db["theo_ngay"])
cs = db["cat"]
kiem("tóm tắt nhật ký cát tháng: số ngày ghi, lần thay, chưa vệ sinh, đổi nguồn + KLN + lọ mẫu, chưa xem",
     (cs["so_ngay"], cs["so_lan_thay"], cs["chua_xem"], cs["so_ngay_cuoi"]) == (6, 2, 6, 2)
     and cs["chua_ve_sinh"] == 4 and cs["doi_nguon"] == [{"ngay": "2026-10-07", "ncc": "Cát Minh Anh", "kln": "Đạt",
                                                         "lo_mau": 1}], cs)
kq = Q.review_rounds("2026-10-01", "2026-10-31")
kiem("MỘT chữ ký xem xét: cả lượt lẫn nhật ký cát", kq["so_cat"] == 6 and all(
    x.get("xem_boi") == "iso@x" for x in bang(CAT.PT).values()), kq)
kiem("ký lần hai → không còn gì", Q.review_rounds("2026-10-01", "2026-10-31")["so_cat"] == 0
     and Q.dashboard("2026-10-01", "2026-10-31")["cat"]["chua_xem"] == 0)
vai("SX QC")
loi = thu(lambda: ghi(ngay="2026-10-06", ve_sinh_khay=1))
kiem("dòng đã ký: QC không sửa được", loi and "Ban ISO đã xem xét" in loi, loi)
kiem("… nhưng kết quả kim loại nặng / lọ mẫu vẫn ghi được (kết quả về muộn)",
     thu(lambda: A.cap_nhat_kln(ten("2026-10-07"), json.dumps({"so_phieu_kln": "KN-78"}))) is None)
kiem("… và QC không xoá được", thu(lambda: A.xoa(ten("2026-10-08"))) is not None)
vai("ISO Manager")
kiem("Ban ISO sửa được dòng đã ký", thu(lambda: get_doc(CAT.PT, ten("2026-10-06")).save()) is None)

# ═══ 6. Bản in, doctype, giao diện ════════════════════════════════════════
print("\n-- BM.08.03, doctype, màn hình --")
if jinja2:
    h = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", A.in_bm0803("2026-10").split("</style>")[1]))
    kiem("BM.08.03: tháng, từng ngày (ngày thứ, thay, vệ sinh), đổi nguồn + KLN + lọ mẫu, ISO đã xem, chưa quy định tối đa",
         "BM.08.03" in h and "Tháng 10/2026" in h and "6 ngày ghi" in h and "(ĐỔI NGUỒN)" in h and "KN-78" in h
         and "Đã lưu" in h and "iso@x" in h and "chưa quy định" in h, h[:300])
else:
    print("  (bỏ qua bản in — không có jinja2)")
dj = json.load(open("sx/qc/doctype/sx_nhat_ky_cat/sx_nhat_ky_cat.json", encoding="utf-8"))
fl = {f["fieldname"]: f for f in dj["fields"]}
kiem("doctype: số ngày / đổi nguồn / người ghi / xem xét chỉ đọc (app điền); KLN có Không đạt",
     all(fl[f].get("read_only") for f in ("so_ngay_dung", "doi_nguon", "nguoi_ghi", "xem_boi", "xem_luc", "su_co"))
     and "Không đạt" in fl["kln"]["options"] and fl["ncc_cat"]["options"] == "Supplier")
st = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_qc_setting/sx_qc_setting.json", encoding="utf-8"))["fields"]}
kiem("SX QC Setting: cát dùng tối đa — mặc định 0 (C19 chưa chốt: chỉ đếm)", st["cat_so_ngay_toi_da"].get("default") == "0")
qcjs = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
kiem("route #/qc/cat", "cat: '/assets/sx/sx/views/qc_cat.js'" in qcjs)
kiem("màn Hôm nay có nút nhật ký cát", "#/qc/cat" in open("sx/public/sx/views/qc_home.js", encoding="utf-8").read())
cj = open("sx/public/sx/views/qc_cat.js", encoding="utf-8").read()
kiem("màn nhật ký cát: ghi, ghi bù, khai số ngày dòng đầu sổ, ghi kết quả KLN, xoá, in BM.08.03",
     all(x in cj for x in ("sx.api.qc_cat.ghi", "so_ngay_dau", "sx.api.qc_cat.cap_nhat_kln", "sx.api.qc_cat.xoa",
                           "sx.api.qc_cat.in_bm0803", "ĐỔI NGUỒN CÁT")))
rj = open("sx/public/sx/views/qc_review.js", encoding="utf-8").read()
kiem("màn Xem xét: tô đỏ ngày sản xuất thiếu lượt, cột Cát, mục nhật ký cát + in BM.08.03, chữ ký gồm cả cát",
     all(x in rj for x in ("kpi.ngay_sx", "sx-qc-o-loi", "<th>Cát</th>", "sx.api.qc_cat.in_bm0803", "kq.so_cat",
                           "ngày sản xuất")))

print(f"\n{'CAT-OK' if not hong else f'CAT-FAIL ({hong})'}")
sys.exit(1 if hong else 0)
