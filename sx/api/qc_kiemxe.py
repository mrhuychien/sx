"""Sổ kiểm tra phương tiện vận chuyển BM.09.01 theo tháng (W14, D139).

Dữ liệu nằm trên chứng từ của chuyến hàng (sx/qc/kiem_xe.py): hoá đơn bán trừ kho + phiếu
nhập mua đã duyệt. Ở đây chỉ gom lại thành một tờ in cho hồ sơ.
"""

import frappe

from sx.api.qc import _guard_qc, _khoang
from sx.qc.kiem_xe import MUC

TRUONG = ["name", "posting_date", "custom_xe_bien_so", "custom_xe_tai_xe", "custom_xe_ket_luan",
          "custom_xe_nguoi_kiem", "custom_xe_ghi_chu"] + [f for f, _n in MUC]


def _chuyen(tu, den):
    ra = []
    for dt, ai, loc in (("Sales Invoice", "customer_name", {"update_stock": 1}),
                        ("Purchase Receipt", "supplier_name", {})):
        try:
            ds = frappe.get_all(dt, filters={"docstatus": 1, "is_return": 0,
                                             "posting_date": ("between", [tu, den]),
                                             "custom_xe_ket_luan": ("is", "set"), **loc},
                                fields=TRUONG + [ai], order_by="posting_date asc")
        except Exception:          # chưa migrate D139
            continue
        for x in ds:
            ra.append(dict(x, chieu="Giao hàng" if dt == "Sales Invoice" else "Nhận nguyên liệu",
                           doi_tac=x.get(ai) or "", ngay=str(x.posting_date)))
    ra.sort(key=lambda x: (x["ngay"], x["name"]))
    return ra


@frappe.whitelist()
def in_so_kiem_xe(tu=None, den=None):
    """HTML A4 ngang — mọi chuyến hàng đã kiểm xe trong khoảng ngày."""
    _guard_qc()
    tu, den = _khoang(tu, den)
    return frappe.render_template("sx/qc/so_kiem_xe.html", {
        "tu": str(tu), "den": str(den), "ds": _chuyen(tu, den), "muc": MUC})
