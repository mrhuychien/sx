"""D162 (W40): không đo độ ẩm khi nhận đỗ, lạc (quyết định 09/10/2026 — độ ẩm vào kiểm nghiệm năm KH.KN.01).

SX QC Setting → "Độ ẩm tối đa" còn đúng mặc định cũ 13% thì để trống (không kiểm); site đã tự đặt số khác
thì giữ. Ô Độ ẩm trên dòng phiếu nhập mua / hoá đơn mua ẩn qua fixtures (số đã ghi trước đây giữ nguyên).
Chạy lại vô hại.
"""

import frappe
from frappe.utils import flt

ST = "SX QC Setting"
CU = 13.0


def execute():
    if flt(frappe.db.get_single_value(ST, "do_am_toi_da")) == CU:
        frappe.db.set_single_value(ST, "do_am_toi_da", None)
