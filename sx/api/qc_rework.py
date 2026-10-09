"""API màn "Rework" BM.15.01 (QC → Hôm nay → ♻) — W19, D145.

Lập phiếu rework (chặn > 10% khối lượng mẻ, chặn hàng có lạc vào sản phẩm không lạc — luật ở
sx/qc/rework.py + controller), danh sách tháng, bản in.
"""

import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from sx.api.qc import GHI_DUOC, ISO, QLSX, _guard_qc, _roles, _sieu
from sx.qc import rework as RW
from sx.qc.quyen import la_iso

TRUONG = ["name", "ngay", "su_co", "sp_nguon", "mo_ta_nguon", "ly_do", "kl_rework", "nguon_co_lac", "nguon_co_sua",
          "sp_dich", "me", "ngay_sx", "kl_me", "ty_le", "dich_co_lac", "dich_co_sua", "ket_qua", "ghi_chu",
          "nguoi_lap", "creation"]


def _duoc_ghi():
    return bool(_sieu() or _roles() & (GHI_DUOC | {ISO, QLSX}))


def _thang(thang=None):
    dau = getdate(f"{thang}-01") if thang else getdate(nowdate()).replace(day=1)
    cuoi = dau.replace(day=28) + timedelta(days=4)
    return dau, cuoi - timedelta(days=cuoi.day)


def _san_pham():
    try:
        return frappe.get_all(RW.SP, filters={"ngung_san_xuat": 0},
                              fields=["name", "so_cong_bo", "ten_san_pham", "co_lac", "co_sua_bot"],
                              order_by="so_cong_bo asc")
    except Exception:
        return []


@frappe.whitelist()
def tong_quan(thang=None):
    _guard_qc()
    dau, cuoi = _thang(thang)
    sp = {x.name: x for x in _san_pham()}
    ds = frappe.get_all(RW.PT, filters={"ngay": ("between", [str(dau), str(cuoi)])}, fields=TRUONG,
                        order_by="ngay desc, creation desc")
    ten = lambda n: (f"{sp[n].so_cong_bo} · {sp[n].ten_san_pham}" if n in sp else n)  # noqa: E731
    su_co = frappe.get_all("SX Su Co", filters={"trang_thai": "Mở"}, fields=["name", "ngay", "mo_ta", "quyet_dinh_sp"],
                           order_by="ngay desc", limit=50)
    return {"thang": dau.strftime("%Y-%m"), "hom_nay": nowdate(), "toi_da": RW.TOI_DA,
            "san_pham": list(sp.values()),
            "ds": [dict(x, ngay=str(x.ngay), ngay_sx=str(x.ngay_sx or ""), creation=str(x.creation or "")[:10],
                        ten_nguon=ten(x.sp_nguon), ten_dich=ten(x.sp_dich)) for x in ds],
            "su_co": [dict(x, ngay=str(x.ngay), mo_ta=(x.mo_ta or "")[:80]) for x in su_co],
            "duoc_ghi": _duoc_ghi(), "la_iso": la_iso(), "user": frappe.session.user}


@frappe.whitelist()
def lap_phieu(payload):
    """Lập phiếu rework. Vượt 10% / lạc vào sản phẩm không lạc → controller chặn."""
    _guard_qc()
    if not _duoc_ghi():
        frappe.throw(_("Chỉ QC, QLSX hoặc Ban ISO lập phiếu rework."), frappe.PermissionError)
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    doc = frappe.get_doc({
        "doctype": RW.PT, "ngay": getdate(p.get("ngay") or nowdate()), "su_co": p.get("su_co") or None,
        "sp_nguon": p.get("sp_nguon"), "mo_ta_nguon": (p.get("mo_ta_nguon") or "").strip(),
        "ly_do": (p.get("ly_do") or "").strip(), "kl_rework": flt(p.get("kl_rework")),
        "sp_dich": p.get("sp_dich"), "me": (p.get("me") or "").strip(),
        "ngay_sx": getdate(p["ngay_sx"]) if p.get("ngay_sx") else None, "kl_me": flt(p.get("kl_me")),
        "ket_qua": (p.get("ket_qua") or "").strip(), "ghi_chu": (p.get("ghi_chu") or "").strip()})
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "ty_le": doc.ty_le}


@frappe.whitelist()
def xoa(name):
    """Lập nhầm: người lập xoá được trong ngày; Ban ISO xoá được bất cứ lúc nào."""
    _guard_qc()
    x = frappe.db.get_value(RW.PT, name, ["nguoi_lap", "creation"], as_dict=True)
    if not x:
        frappe.throw(_("Không có phiếu {0}.").format(name))
    if not la_iso() and not (x.nguoi_lap == frappe.session.user and getdate(x.creation) == getdate(nowdate())):
        frappe.throw(_("Chỉ người lập (trong ngày) hoặc Ban ISO xoá được phiếu rework."), frappe.PermissionError)
    frappe.delete_doc(RW.PT, name, ignore_permissions=True)
    return {"name": name}


@frappe.whitelist()
def in_bm1501(thang=None):
    """BM.15.01 — các phiếu rework trong tháng (A4 ngang)."""
    _guard_qc()
    dau, cuoi = _thang(thang)
    sp = {x.name: x for x in _san_pham()}
    ds = frappe.get_all(RW.PT, filters={"ngay": ("between", [str(dau), str(cuoi)])}, fields=TRUONG,
                        order_by="ngay asc, creation asc")
    return frappe.render_template("sx/qc/bm1501.html", {
        "thang": dau.strftime("%m/%Y"), "toi_da": RW.TOI_DA,
        "ds": [dict(x, ten_nguon=(f"{sp[x.sp_nguon].so_cong_bo} · {sp[x.sp_nguon].ten_san_pham}"
                                  if x.sp_nguon in sp else x.sp_nguon),
                    ten_dich=(f"{sp[x.sp_dich].so_cong_bo} · {sp[x.sp_dich].ten_san_pham}"
                              if x.sp_dich in sp else x.sp_dich)) for x in ds]})

