import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from sx.utils import sinh_lo_rang


class SXXuatDau(Document):
    """Phiếu xuất đậu D-1 -> sinh lô rang (neo gốc truy xuất). Nhập thẳng kg (D6).

    Không tạo Stock Entry (đậu trừ tại Nhập bột — D7). Phiếu là neo lô đậu ↔ lô R
    và nguồn cho list "lô chờ nhập bột".
    """

    def validate(self):
        if flt(self.dau_kg) <= 0:
            frappe.throw(_("Đậu xuất (kg) phải > 0"))
        if not self.lo_rang:
            self.lo_rang = sinh_lo_rang(self.loai_dau, self.ngay_rang)
