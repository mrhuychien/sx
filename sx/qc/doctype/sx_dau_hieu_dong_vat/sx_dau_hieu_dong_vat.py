"""Một lần thấy dấu hiệu động vật gây hại tại một trạm (W15, D140)."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class SXDauHieuDongVat(Document):
    def validate(self):
        t = frappe.db.get_value("SX Tram Dong Vat", self.tram, ["khu", "ngung"], as_dict=True)
        if not t:
            frappe.throw(_("Không có trạm {0}.").format(self.tram))
        if self.is_new():
            self.khu = t.khu or ""
            self.nguoi_ghi = frappe.session.user
        if (self.so_luong or 0) < 0:
            frappe.throw(_("Số lượng không âm."))
        if self.ngay and getdate(self.ngay) > getdate(nowdate()):
            frappe.throw(_("Ngày thấy dấu hiệu không được sau hôm nay."))
