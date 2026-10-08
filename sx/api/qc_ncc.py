"""Danh sách nhà cung cấp được duyệt — BM.07.02 (W09, D138), cho Ban ISO in / xem.

Luật duyệt (loại NCC → bộ hồ sơ, ai được tích "Đã duyệt") ở sx/qc/ncc.py — chặn cả Desk.
Ở đây chỉ đọc ra danh sách + bản in A4.
"""

import frappe
from frappe.utils import getdate, nowdate

from sx.api.qc import _guard_manager, _guard_qc
from sx.qc import ncc as NCC


def _ds(ngay):
    try:
        ds = frappe.get_all("Supplier", filters={"disabled": 0, "custom_loai_ncc": ("is", "set")},
                            fields=["name", "supplier_name", "custom_loai_ncc", "custom_nguon_goc",
                                    "custom_ncc_duyet", "custom_ngay_duyet_ncc", "custom_duyet_ncc_boi"],
                            order_by="custom_loai_ncc asc, supplier_name asc")
        ho_so = frappe.get_all("SX Ho So NCC", filters={"parenttype": "Supplier",
                                                         "parent": ("in", [s.name for s in ds] or [""])},
                               fields=["parent", "loai_ho_so", "so_hieu", "het_han"])
    except Exception:
        return []
    theo = {}
    for h in ho_so:
        theo.setdefault(h.parent, []).append(h)
    ra = []
    for s in ds:
        hs = theo.get(s.name, [])
        pkn = NCC.pkn_con_han(hs, ngay)
        ra.append({"ncc": s.name, "ten": s.supplier_name or s.name, "loai": s.custom_loai_ncc,
                   "nguon": s.custom_nguon_goc or "", "duyet": bool(s.custom_ncc_duyet),
                   "ngay_duyet": str(s.custom_ngay_duyet_ncc or ""), "duyet_boi": s.custom_duyet_ncc_boi or "",
                   "thieu": NCC.thieu_ho_so(s.custom_loai_ncc, hs, ngay),
                   "pkn": (f'{pkn.get("so_hieu") or ""} · hạn {getdate(pkn["het_han"]).strftime("%d/%m/%Y")}'
                           if pkn and pkn.get("het_han") else ("có" if pkn else ""))})
    return ra


@frappe.whitelist()
def ds_ncc():
    """Danh sách NCC đã phân loại + trạng thái duyệt / hồ sơ thiếu — cho màn Xem xét."""
    _guard_qc()
    return _ds(getdate(nowdate()))


@frappe.whitelist()
def in_ds_ncc():
    """HTML A4 ngang — danh sách nhà cung cấp được duyệt BM.07.02."""
    _guard_manager()
    ngay = getdate(nowdate())
    return frappe.render_template("sx/qc/ds_ncc.html", {"ds": _ds(ngay), "ngay": str(ngay)})
