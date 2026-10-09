"""API màn "Việc định kỳ" (QC → Hôm nay → 📅) — W21, D146. Luật ở sx/qc/viec_dinh_ky.py.

W35 (D166): chu kỳ 2 năm, hạn để trống được (chưa đặt hạn); việc kiểm nghiệm (có ô mẫu của) ghi lần làm
bằng phiếu gửi mẫu ở màn Kiểm nghiệm, không bấm "Đã làm" ở đây."""

import json

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from sx.api.qc import GHI_DUOC, ISO, _guard_qc, _roles, _sieu
from sx.qc import viec_dinh_ky as VD

TRUONG = ["name", "ten", "chu_ky", "han", "bao_truoc", "phu_trach", "ho_so", "ngung", "mo_ta", "lan_cuoi",
          "doi_tuong_kn"]


def _duoc_ghi():
    return bool(_sieu() or _roles() & GHI_DUOC or ISO in _roles())


def _guard_vd():
    _guard_qc()
    if not _duoc_ghi():
        frappe.throw(_("Chỉ QC hoặc Ban ISO ghi việc định kỳ."), frappe.PermissionError)


@frappe.whitelist()
def tong_quan():
    _guard_qc()
    d = getdate(nowdate())
    ds = []
    for v in frappe.get_all(VD.PT, fields=TRUONG, order_by="ngung asc, han asc"):
        tt, con = VD.trang_thai(v, d)
        lan = frappe.get_all("SX Viec Dinh Ky Lan", filters={"parent": v.name, "parenttype": VD.PT},
                             fields=["ngay", "nguoi", "ghi_chu", "han_ky", "phieu_kn"], order_by="idx desc", limit=5)
        ds.append(dict(v, han=str(v.han or ""), lan_cuoi=str(v.lan_cuoi or ""), trang_thai=tt, con=con,
                       lich_su=[dict(x, ngay=str(x.ngay or ""), han_ky=str(x.han_ky or "")) for x in lan]))
    return {"ds": ds, "chu_ky": list(VD.THANG), "doi_tuong_kn": list(VD.DOI_TUONG_KN), "hom_nay": str(d),
            "duoc_ghi": _duoc_ghi()}


@frappe.whitelist()
def luu(payload):
    """Thêm / sửa một việc định kỳ."""
    _guard_vd()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    doc = frappe.get_doc(VD.PT, p["name"]) if p.get("name") else frappe.get_doc({"doctype": VD.PT})
    for f in ("ten", "phu_trach", "ho_so", "mo_ta"):
        doc.set(f, (p.get(f) or "").strip())
    doc.chu_ky = p.get("chu_ky") or "Năm"
    doc.han = getdate(p["han"]) if p.get("han") else None          # chưa biết → "Chưa đặt hạn"
    doc.bao_truoc = cint(p.get("bao_truoc")) or 14
    doc.ngung = 1 if cint(p.get("ngung")) else 0
    if "doi_tuong_kn" in p:
        doc.doi_tuong_kn = p.get("doi_tuong_kn") or None
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return {"name": doc.name}


@frappe.whitelist()
def da_lam(name, payload=None):
    """Ghi một lần làm; dời hạn sang kỳ sau tính từ hạn cũ ("Một lần" → ngừng)."""
    _guard_vd()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    doc = frappe.get_doc(VD.PT, name)
    if cint(doc.ngung):
        frappe.throw(_("Việc này đã ngừng."))
    if doc.get("doi_tuong_kn"):
        frappe.throw(_("Việc kiểm nghiệm: ghi lần gửi mẫu ở màn Kiểm nghiệm (phiếu gửi mẫu là bằng chứng) — app "
                       "tự dời hạn."))
    ngay = getdate(p.get("ngay") or nowdate())
    if ngay > getdate(nowdate()):
        frappe.throw(_("Ngày làm không được sau hôm nay."))
    VD.ghi_lan(doc, ngay, (p.get("ghi_chu") or "").strip())
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "han": str(doc.han or ""), "ngung": cint(doc.ngung)}
