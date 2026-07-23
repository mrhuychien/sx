import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class SXDonGiaVaoHop(Document):
    """Bảng giá lương vào hộp. Cho phép đơn giá 0 (SKU không tính lương SP)."""

    def validate(self):
        if flt(self.don_gia) < 0:
            frappe.throw(_("Đơn giá không được âm"))
