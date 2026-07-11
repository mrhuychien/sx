import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class SXSettings(Document):
    """Cấu hình app sx (Single). Yield bột KHÔNG ở đây — suy từ BOM tầng 1."""

    def validate(self):
        if (
            self.ccp_nhiet_min
            and self.ccp_nhiet_max
            and flt(self.ccp_nhiet_min) >= flt(self.ccp_nhiet_max)
        ):
            frappe.throw(_("Giới hạn CCP: min phải nhỏ hơn max"))
