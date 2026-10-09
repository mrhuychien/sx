"""Một dòng danh mục hồ sơ cho đoàn đánh giá (W27, D149). Luật cờ ở sx/qc/ho_so.py."""

import frappe
from frappe import _
from frappe.model.document import Document

from sx.qc import ho_so as HS


class SXHoSoDanhMuc(Document):
    def validate(self):
        self.ma = (self.ma or "").strip()
        self.ten = (self.ten or "").strip()
        if not self.ma or not self.ten:
            frappe.throw(_("Nhập mã và tên hồ sơ."))
        for r in frappe.get_all(HS.PT, filters={"name": ("!=", self.name or "")}, fields=["name", "ma"]):
            if HS.chuan_ma(r.ma) == HS.chuan_ma(self.ma):
                frappe.throw(_("Đã có hồ sơ mã {0} trong danh mục.").format(r.ma))
        if self.nhom not in HS.NHOM:
            frappe.throw(_("Chọn nhóm hồ sơ."))
        if self.nguon not in HS.NGUON:
            frappe.throw(_("Chọn hồ sơ nằm ở đâu: app lập, tệp đính kèm hay bản giấy."))
        if self.nguon == HS.APP:
            if self.bieu_mau not in HS.BIEU_MAU:
                frappe.throw(_("Hồ sơ app lập: chọn biểu mẫu app."))
        else:
            self.bieu_mau = None
        if (self.thay_the or "").strip() and HS.chuan_ma(self.thay_the) == HS.chuan_ma(self.ma):
            frappe.throw(_("Văn bản không thay thế chính nó."))
