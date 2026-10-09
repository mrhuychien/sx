"""Việc định kỳ cho hồ sơ giấy (W21, D146); việc kiểm nghiệm KH.KN.01 ngoài thành phẩm (W35, D166). Luật ở
sx/qc/viec_dinh_ky.py."""

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
            frappe.throw(_("Chu kỳ phải là {0}.").format(" / ".join(VD.THANG)))
        if self.doi_tuong_kn and self.doi_tuong_kn not in VD.DOI_TUONG_KN:
            frappe.throw(_("Mẫu kiểm nghiệm phải là {0}.").format(" / ".join(VD.DOI_TUONG_KN)))
        if cint(self.bao_truoc) < 0:
            frappe.throw(_("Số ngày nhắc trước không âm."))
        if not cint(self.bao_truoc):
            self.bao_truoc = 14
