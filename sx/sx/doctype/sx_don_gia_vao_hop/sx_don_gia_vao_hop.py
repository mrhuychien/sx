import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class SXDonGiaVaoHop(Document):
    """Bảng giá lương vào hộp — theo phương thức, override theo SKU nếu cần (D6)."""

    def validate(self):
        if flt(self.don_gia) <= 0:
            frappe.throw(_("Đơn giá phải > 0"))
