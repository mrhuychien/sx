"""Một chỉ tiêu ATTP năm (W25, D151): chỉ số app tự tính + so sánh + mục tiêu. Luật ở sx/qc/bao_cao.py."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from sx.qc import bao_cao as BC


class SXChiTieuATTP(Document):
    def validate(self):
        if self.chi_so not in BC.MA:
            frappe.throw(_("Chọn chỉ số app tự tính."))
        if not 2020 <= cint(self.nam) <= 2100:
            frappe.throw(_("Năm không hợp lệ."))
        if self.so_sanh not in (BC.GE, BC.LE):
            self.so_sanh = BC.so_sanh_mac_dinh(self.chi_so)
        if self.muc_tieu is None or str(self.muc_tieu).strip() == "":
            frappe.throw(_("Nhập mục tiêu."))
        if flt(self.muc_tieu) < 0 or (BC.la_ty_le(self.chi_so) and flt(self.muc_tieu) > 100):
            frappe.throw(_("Mục tiêu của chỉ số % phải trong 0 – 100."))
        self.ten_chi_so = BC.MA[self.chi_so][1]
        self.ten = (self.ten or "").strip()
        if not cint(self.ngung):
            trung = frappe.get_all(BC.PT, filters={"nam": cint(self.nam), "chi_so": self.chi_so, "ngung": 0,
                                                   "name": ("!=", self.name or "")}, pluck="name", limit=1)
            if trung:
                frappe.throw(_("Năm {0} đã có chỉ tiêu cho chỉ số này — sửa chỉ tiêu đó.").format(cint(self.nam)))
