"""API màn "Kế hoạch kiểm nghiệm" KH.KN.01 (QC → Hôm nay → 🧪) — W18, D144.

Kế hoạch theo sản phẩm (bộ tự công bố W28), cát chỉ khi đổi nguồn (nhật ký cát W20), gửi mẫu,
ghi kết quả, bản in. Luật ở sx/qc/kiem_nghiem.py và controller SX Kiem Nghiem.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from sx.api.qc import GHI_DUOC, ISO, _guard_qc, _roles, _sieu
from sx.qc import kiem_nghiem as KN
from sx.qc.quyen import la_iso

TRUONG = ["name", "doi_tuong", "san_pham", "ten_san_pham", "nhat_ky_cat", "mo_ta_mau", "ngay_gui", "phong_kn",
          "chi_tieu", "lan_sau", "ket_qua", "ngay_kq", "so_phieu", "ghi_chu", "nguoi_ghi", "su_co", "creation"]
GUI = ("doi_tuong", "san_pham", "nhat_ky_cat", "mo_ta_mau", "phong_kn", "chi_tieu", "ghi_chu")


def _duoc_ghi():
    return bool(_sieu() or _roles() & GHI_DUOC or ISO in _roles())


def _guard_kn():
    _guard_qc()
    if not _duoc_ghi():
        frappe.throw(_("Chỉ QC hoặc Ban ISO ghi phiếu kiểm nghiệm."), frappe.PermissionError)


def _dong(x):
    return dict(x, ngay_gui=str(x.ngay_gui or ""), ngay_kq=str(x.ngay_kq or ""), lan_sau=str(x.lan_sau or ""),
                creation=str(x.creation or "")[:10])


@frappe.whitelist()
def tong_quan(nam=None):
    _guard_qc()
    d = getdate(nowdate())
    nam = cint(nam) or d.year
    phieu = frappe.get_all(KN.PT, filters={"ngay_gui": ("between", [f"{nam}-01-01", f"{nam}-12-31"])},
                           fields=TRUONG, order_by="ngay_gui desc, creation desc")
    return {"ke_hoach": KN.ke_hoach(d), "cat": KN.cat_cho_kiem(), "phieu": [_dong(x) for x in phieu],
            "nam": nam, "hom_nay": str(d), "han_dau": str(KN.han_dau()), "sap_den": KN.SAP_DEN,
            "cho_lau": KN.CHO_LAU, "doi_tuong": ["Sản phẩm", "Cát rang", "Nguyên liệu", "Nước", "Khác"],
            "duoc_ghi": _duoc_ghi(), "la_iso": la_iso(), "user": frappe.session.user}


@frappe.whitelist()
def gui_mau(payload):
    """Ghi một lần gửi mẫu (kết quả ghi sau, hoặc ghi luôn nếu đã có)."""
    _guard_kn()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    doc = frappe.get_doc({"doctype": KN.PT, "ngay_gui": getdate(p.get("ngay_gui") or nowdate()),
                          **{f: (p.get(f) or "").strip() or None for f in GUI}})
    doc.doi_tuong = doc.doi_tuong or KN.SAN_PHAM
    if doc.doi_tuong == KN.CAT and doc.nhat_ky_cat:
        if frappe.db.exists(KN.PT, {"nhat_ky_cat": doc.nhat_ky_cat}):
            frappe.throw(_("Lần đổi nguồn cát này đã có phiếu gửi mẫu — mở phiếu đó ghi kết quả."))
    _ket_qua(doc, p)
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "lan_sau": str(doc.lan_sau or ""), "su_co": doc.su_co}


def _ket_qua(doc, p):
    if "ket_qua" in p:
        if p.get("ket_qua") and p["ket_qua"] not in (KN.DAT, KN.KHONG_DAT):
            frappe.throw(_("Kết quả không hợp lệ."))
        doc.ket_qua = p.get("ket_qua") or ""
    if p.get("ngay_kq"):
        doc.ngay_kq = getdate(p["ngay_kq"])
    if "so_phieu" in p:
        doc.so_phieu = (p.get("so_phieu") or "").strip()


@frappe.whitelist()
def ghi_ket_qua(name, payload):
    _guard_kn()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    doc = frappe.get_doc(KN.PT, name)
    _ket_qua(doc, p)
    if p.get("ghi_chu"):
        doc.ghi_chu = p["ghi_chu"].strip()
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "ket_qua": doc.ket_qua, "su_co": doc.su_co}


@frappe.whitelist()
def lich_su(san_pham):
    _guard_qc()
    return [_dong(x) for x in frappe.get_all(KN.PT, filters={"san_pham": san_pham}, fields=TRUONG,
                                             order_by="ngay_gui desc, creation desc", limit=20)]


@frappe.whitelist()
def xoa(name):
    """Ghi nhầm: người ghi xoá được trong ngày ghi; Ban ISO xoá được bất cứ lúc nào."""
    _guard_kn()
    x = frappe.db.get_value(KN.PT, name, ["nguoi_ghi", "creation"], as_dict=True)
    if not x:
        frappe.throw(_("Không có phiếu {0}.").format(name))
    if not la_iso() and not (x.nguoi_ghi == frappe.session.user and getdate(x.creation) == getdate(nowdate())):
        frappe.throw(_("Chỉ người ghi (trong ngày) hoặc Ban ISO xoá được phiếu này."), frappe.PermissionError)
    frappe.delete_doc(KN.PT, name, ignore_permissions=True)
    return {"name": name}


@frappe.whitelist()
def in_kh_kn01(nam=None):
    """KH.KN.01 — kế hoạch kiểm nghiệm năm: từng sản phẩm, tháng dự kiến, các lần gửi, kết quả."""
    _guard_qc()
    d = getdate(nowdate())
    nam = cint(nam) or d.year
    kh = KN.ke_hoach(d)
    phieu = frappe.get_all(KN.PT, filters={"ngay_gui": ("between", [f"{nam}-01-01", f"{nam}-12-31"])},
                           fields=TRUONG, order_by="ngay_gui asc")
    theo = {}
    for p in phieu:
        theo.setdefault(p.san_pham or "", []).append(p)
    return frappe.render_template("sx/qc/kh_kn01.html", {
        "nam": nam, "ngay": str(d), "kh": [dict(x, thang=KN.thang_du_kien(x), phieu=theo.get(x["san_pham"], []))
                                           for x in kh],
        "khac": [p for p in phieu if p.doi_tuong != KN.SAN_PHAM], "cat": KN.cat_cho_kiem()})
