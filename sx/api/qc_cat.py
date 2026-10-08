"""API màn "Nhật ký cát rang" BM.08.03 (QC → Hôm nay → ♨) — W20, D141.

Mỗi ngày có rang một dòng; app tự đếm số ngày cát đã dùng, nhắc kiểm kim loại nặng + lưu
lọ mẫu khi đổi nguồn cát. Luật ở sx/qc/cat.py và controller SX Nhat Ky Cat (chặn cả Desk).
"""

import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from sx.api.qc import GHI_DUOC, _guard_ghi, _guard_qc, _roles, _sieu
from sx.qc import cat as CAT
from sx.qc.quyen import la_iso

TRUONG = ["name", "ngay", "ncc_cat", "ten_ncc", "thay_cat", "so_ngay_dung", "doi_nguon", "kln",
          "so_phieu_kln", "luu_lo_mau", "ve_sinh_thung", "ve_sinh_khay", "cam_quan", "ghi_chu",
          "nguoi_ghi", "su_co", "xem_boi", "xem_luc", "creation"]


def _thang(thang=None):
    dau = getdate(f"{thang}-01") if thang else getdate(nowdate()).replace(day=1)
    cuoi = dau.replace(day=28) + timedelta(days=4)
    return dau, cuoi - timedelta(days=cuoi.day)


def _dong(x):
    return dict(x, ngay=str(x.ngay), xem_luc=str(x.xem_luc or "")[:16], creation=str(x.get("creation") or "")[:10])


def _ds(tu, den):
    return frappe.get_all(CAT.PT, filters={"ngay": ("between", [str(tu), str(den)])}, fields=TRUONG,
                          order_by="ngay asc")


def _ncc_cat():
    """NCC loại Cát rang (W09) để chọn nguồn. Site chưa có field phân loại → []."""
    try:
        return frappe.get_all("Supplier", filters={"custom_loai_ncc": "Cát rang", "disabled": 0},
                              fields=["name", "supplier_name", "custom_ncc_duyet"], order_by="supplier_name asc")
    except Exception:
        return []


@frappe.whitelist()
def tong_quan(thang=None):
    """Dòng của tháng (mới trước), cát đang dùng, đổi nguồn còn thiếu, danh sách nguồn."""
    _guard_qc()
    dau, cuoi = _thang(thang)
    hom_nay = getdate(nowdate())
    hien = frappe.get_all(CAT.PT, filters={"ngay": ("<=", str(hom_nay))}, fields=TRUONG,
                          order_by="ngay desc", limit=1)
    hom = frappe.get_all(CAT.PT, filters={"ngay": str(hom_nay)}, fields=TRUONG, limit=1)
    dau_so = frappe.get_all(CAT.PT, fields=["ngay"], order_by="ngay asc", limit=1)
    thay = frappe.get_all(CAT.PT, filters={"thay_cat": 1, "ngay": ("<=", str(hom_nay))}, fields=["ngay"],
                          order_by="ngay desc", limit=1)
    cho = CAT.cho_kln(frappe.get_all(CAT.PT, filters={"doi_nguon": 1}, fields=TRUONG, order_by="ngay asc"))
    return {
        "thang": dau.strftime("%Y-%m"), "hom_nay": str(hom_nay),
        "ds": [_dong(x) for x in reversed(_ds(dau, cuoi))],
        "hien_tai": _dong(hien[0]) if hien else None,
        "hom_nay_co": hom[0].name if hom else None,
        "hom_nay_dong": _dong(hom[0]) if hom else None,
        "ngay_dau_so": str(dau_so[0].ngay) if dau_so else None,
        "ngay_thay": str(thay[0].ngay) if thay else None,
        "cho_kln": [_dong(x) for x in cho],
        "ncc": [dict(x, duyet=cint(x.custom_ncc_duyet)) for x in _ncc_cat()],
        "toi_da": CAT.toi_da(),
        "duoc_ghi": bool(_sieu() or _roles() & GHI_DUOC),
        "la_iso": la_iso(),
        "user": frappe.session.user,
    }


@frappe.whitelist()
def ghi(payload):
    """Ghi / sửa dòng của một ngày. Ngày đã có dòng thì SỬA dòng đó — không lập dòng thứ hai."""
    _guard_ghi()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    d = getdate(p.get("ngay") or nowdate())
    ten = p.get("name") or frappe.db.get_value(CAT.PT, {"ngay": str(d)}, "name")
    doc = frappe.get_doc(CAT.PT, ten) if ten else frappe.get_doc({"doctype": CAT.PT})
    doc.ngay = d
    doc.ncc_cat = (p.get("ncc_cat") or "").strip() or None
    for f in ("thay_cat", "ve_sinh_thung", "ve_sinh_khay"):
        doc.set(f, 1 if cint(p.get(f)) else 0)
    doc.cam_quan = p.get("cam_quan") or ""
    doc.ghi_chu = (p.get("ghi_chu") or "").strip()
    _kln(doc, p)
    # Dòng đầu sổ: cát đang dùng từ trước khi có app — người ghi khai đã dùng mấy ngày.
    # Dòng không phải đầu sổ thì controller tự đếm, số khai này bị bỏ qua (cat.ke_tiep).
    if cint(p.get("so_ngay_dau")) > 0:
        doc.so_ngay_dung = cint(p["so_ngay_dau"])
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return {"name": doc.name, "so_ngay_dung": doc.so_ngay_dung, "doi_nguon": cint(doc.doi_nguon),
            "su_co": doc.su_co}


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
    """Ghi nhầm ngày: người ghi xoá được trong ngày; Ban ISO xoá được bất cứ lúc nào."""
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
    """BM.08.03 — nhật ký cát rang của một tháng (A4 ngang)."""
    _guard_qc()
    dau, cuoi = _thang(thang)
    ds = _ds(dau, cuoi)
    return frappe.render_template("sx/qc/bm0803.html", {
        "thang": dau.strftime("%m/%Y"), "ds": ds, "toi_da": CAT.toi_da(),
        "doi": [x for x in ds if cint(x.doi_nguon)],
        "xem": next((x for x in reversed(ds) if x.xem_boi), None)})
