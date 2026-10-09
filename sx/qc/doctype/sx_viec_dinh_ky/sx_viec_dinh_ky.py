"""Việc định kỳ cho hồ sơ giấy (W21, D146). Luật ở sx/qc/viec_dinh_ky.py."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from sx.qc import viec_dinh_ky as VD


class SXViecDinhKy(Document):
    def validate(self):
        if not (self.ten or "").strip():
            frappe.throw(_("Nhập tên việc."))
        if self.chu_ky not in VD.THANG:
            frappe.throw(_("Chu kỳ phải là Năm / Quý / Tháng / Một lần."))
        if cint(self.bao_truoc) < 0:
            frappe.throw(_("Số ngày nhắc trước không âm."))
        if not cint(self.bao_truoc):
            self.bao_truoc = 14
