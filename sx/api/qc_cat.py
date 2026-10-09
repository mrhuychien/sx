"""API màn "Nhật ký cát rang" BM.08.03 (QC → Hôm nay → ♨) — W20 (D141), W32 (D164): mỗi việc một dòng.

Nhập cát / rang khô đưa dùng / bổ sung / loại cát / vệ sinh thùng, khay — một dòng. App đếm số ngày cát đã
dùng (ngày có rang kể từ lần thay toàn bộ), nhắc kiểm kim loại nặng + lưu lọ mẫu khi đổi nguồn cát. Luật ở
sx/qc/cat.py và controller SX Nhat Ky Cat (chặn cả Desk).
"""

import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from sx.api.qc import GHI_DUOC, _guard_ghi, _guard_qc, _roles, _sieu
from sx.qc import cat as CAT
from sx.qc.quyen import la_iso

TRUONG = ["name", "ngay", "viec", "so_cu", "ncc_cat", "ten_ncc", "so_bm0703", "khoi_luong", "thung", "thay_cat",
          "so_ngay_dung", "so_ngay_dau", "ly_do_loai", "doi_nguon", "kln", "so_phieu_kln", "luu_lo_mau",
          "ve_sinh_thung", "ve_sinh_khay", "cam_quan", "ghi_chu", "nguoi_lam", "nguoi_ghi", "su_co", "xem_boi",
          "xem_luc", "creation"]
GHI = ("ncc_cat", "so_bm0703", "thung", "ly_do_loai", "cam_quan", "nguoi_lam", "ghi_chu")


def _thang(thang=None):
    dau = getdate(f"{thang}-01") if thang else getdate(nowdate()).replace(day=1)
    cuoi = dau.replace(day=28) + timedelta(days=4)
    return dau, cuoi - timedelta(days=cuoi.day)


def _dong(x):
    return dict(x, ngay=str(x.ngay), xem_luc=str(x.xem_luc or "")[:16], creation=str(x.get("creation") or "")[:10],
                viec=x.get("viec") or "", so_cu=cint(x.get("so_cu")), khoi_luong=flt(x.get("khoi_luong")))


def _ds(tu, den):
    return frappe.get_all(CAT.PT, filters={"ngay": ("between", [str(tu), str(den)])}, fields=TRUONG,
                          order_by="ngay asc, creation asc")


def _ncc_cat():
    """NCC loại Cát rang (W09) để chọn nguồn. Site chưa có field phân loại → []."""
    try:
        return frappe.get_all("Supplier", filters={"custom_loai_ncc": "Cát rang", "disabled": 0},
                              fields=["name", "supplier_name", "custom_ncc_duyet"], order_by="supplier_name asc")
    except Exception:
        return []


def hien_tai(d):
    """Cát đang dùng tới ngày `d`: {so_ngay (None = không có cát đang dùng), ncc, ten_ncc, ngay_thay, thung,
    ngay_loai (đã loại mà chưa đưa cát mới), dau_so (sổ chưa có mốc nào — dòng đưa dùng đầu tiên khai số ngày)}."""
    ds = CAT.dong_tu_moc(d)
    so = CAT.dem_ngay(ds, CAT.ngay_rang(min(getdate(x.ngay) for x in ds), d), d) if ds else None
    xep = sorted(ds, key=CAT.xep)
    moc = next((x for x in reversed(xep) if x.viec == CAT.RANG_KHO), None)
    loai = next((x for x in reversed(xep) if x.viec == CAT.LOAI), None)
    ncc, ten = CAT.nguon_dang_dung(ds, d)
    return {"so_ngay": so, "ncc": ncc, "ten_ncc": ten, "ngay_thay": str(moc.ngay) if moc else None,
            "ngay_loai": str(loai.ngay) if (loai and so is None) else None,
            "dau_so": not (moc or any(cint(x.so_cu) for x in ds))}


@frappe.whitelist()
def tong_quan(thang=None):
    """Dòng của tháng (mới trước), cát đang dùng, đổi nguồn còn thiếu, danh sách nguồn, nguồn nhập gần nhất."""
    _guard_qc()
    dau, cuoi = _thang(thang)
    hom_nay = getdate(nowdate())
    cho = CAT.cho_kln(frappe.get_all(CAT.PT, filters={"doi_nguon": 1}, fields=TRUONG, order_by="ngay asc"))
    nhap = frappe.get_all(CAT.PT, filters={"viec": CAT.NHAP, "ngay": ("<=", str(hom_nay))}, fields=["ncc_cat"],
                          order_by="ngay desc, creation desc", limit=1)
    return {
        "thang": dau.strftime("%Y-%m"), "hom_nay": str(hom_nay),
        "ds": [_dong(x) for x in reversed(_ds(dau, cuoi))],
        "hien_tai": hien_tai(hom_nay),
        "nguon_nhap": nhap[0].ncc_cat if nhap else "",
        "cho_kln": [_dong(x) for x in cho],
        "ncc": [dict(x, duyet=cint(x.custom_ncc_duyet)) for x in _ncc_cat()],
        "viec": list(CAT.VIEC),
        "toi_da": CAT.toi_da(),
        "duoc_ghi": bool(_sieu() or _roles() & GHI_DUOC),
        "la_iso": la_iso(),
        "user": frappe.session.user,
    }


@frappe.whitelist()
def ghi(payload):
    """Ghi / sửa một dòng việc. Dòng sổ cũ (mỗi ngày một dòng, trước D164) giữ nguyên — không sửa qua đây."""
    _guard_ghi()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    doc = frappe.get_doc(CAT.PT, p["name"]) if p.get("name") else frappe.get_doc({"doctype": CAT.PT})
    if cint(doc.so_cu):
        frappe.throw(_("Dòng sổ cũ (mỗi ngày một dòng) giữ nguyên — việc mới thì ghi thành dòng mới. Kết quả kim "
                       "loại nặng / lọ mẫu: nút GHI KẾT QUẢ."))
    doc.ngay = getdate(p.get("ngay") or nowdate())
    doc.viec = p.get("viec") or ""
    for f in GHI:
        doc.set(f, (p.get(f) or "").strip() or None)
    doc.khoi_luong = flt(p.get("khoi_luong"))
    if "so_ngay_dau" in p:          # màn chỉ gửi khi hiện ô (dòng đưa dùng đầu sổ) — sửa dòng không làm mất số
        doc.so_ngay_dau = cint(p.get("so_ngay_dau"))
    for f in ("ve_sinh_thung", "ve_sinh_khay"):
        doc.set(f, 1 if cint(p.get(f)) else 0)
    _kln(doc, p)
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return {"name": doc.name, "viec": doc.viec, "so_ngay_dung": cint(doc.so_ngay_dung), "doi_nguon": cint(doc.doi_nguon),
            "su_co": doc.su_co, "so_ngay": hien_tai(getdate(nowdate()))["so_ngay"]}


def _kln(doc, p):
    if "kln" in p:
        if p.get("kln") and p["kln"] not in (CAT.KLN_GUI, CAT.KLN_DAT, CAT.KLN_HONG):
            frappe.throw(_("Kết quả kim loại nặng không hợp lệ."))
        doc.kln = p.get("kln") or ""
    if "so_phieu_kln" in p:
        doc.so_phieu_kln = (p.get("so_phieu_kln") or "").strip()
    if "luu_lo_mau" in p:
        doc.luu_lo_mau = 1 if cint(p.get("luu_lo_mau")) else 0


@frappe.whitelist()
def cap_nhat_kln(name, payload):
    """Kết quả kim loại nặng / lọ mẫu của một lần đổi nguồn — về sau ngày ghi, kể cả sau khi
    Ban ISO đã xem xét tháng. QC hoặc Ban ISO ghi."""
    _guard_qc()
    if not (_sieu() or _roles() & GHI_DUOC or la_iso()):
        frappe.throw(_("Chỉ QC hoặc Ban ISO ghi kết quả kim loại nặng."), frappe.PermissionError)
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    doc = frappe.get_doc(CAT.PT, name)
    if not cint(doc.doi_nguon):
        frappe.throw(_("Dòng {0} không phải lần đổi nguồn cát.").format(name))
    _kln(doc, {k: p[k] for k in ("kln", "so_phieu_kln", "luu_lo_mau") if k in p})
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "su_co": doc.su_co}


@frappe.whitelist()
def xoa(name):
    """Ghi nhầm: người ghi xoá được trong ngày; Ban ISO xoá được bất cứ lúc nào."""
    _guard_qc()
    x = frappe.db.get_value(CAT.PT, name, ["nguoi_ghi", "creation"], as_dict=True)
    if not x:
        frappe.throw(_("Không có dòng {0}.").format(name))
    if not la_iso() and not (x.nguoi_ghi == frappe.session.user
                             and getdate(x.creation) == getdate(nowdate())):
        frappe.throw(_("Chỉ người ghi (trong ngày) hoặc Ban ISO xoá được dòng này."), frappe.PermissionError)
    frappe.delete_doc(CAT.PT, name, ignore_permissions=True)
    return {"name": name}


@frappe.whitelist()
def in_bm0803(thang=None):
    """BM.08.03 — nhật ký cát rang của một tháng, mỗi việc một dòng (A4 ngang)."""
    _guard_qc()
    dau, cuoi = _thang(thang)
    ds = _ds(dau, cuoi)
    return frappe.render_template("sx/qc/bm0803.html", {
        "thang": dau.strftime("%m/%Y"), "ds": [_dong(x) for x in ds], "toi_da": CAT.toi_da(), "dem": CAT.DEM,
        "doi": [x for x in ds if cint(x.doi_nguon)],
        "xem": next((x for x in reversed(ds) if x.xem_boi), None)})
