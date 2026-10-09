"""Nơi nhận tài liệu — Phụ lục 3 QĐ ban hành 21/9/2026, BM.01.13 (W42, D171).

Quyền xem tài liệu suy ra từ vai (role) của nơi nhận (C27); 'mọi tài khoản' = toàn bộ người lao động có tài
khoản app (Chính sách ATTP niêm yết)."""

import frappe
from frappe import _
from frappe.model.document import Document

from sx.qc import tai_lieu as TL


class SXNoiNhan(Document):
    def validate(self):
        self.ten = " ".join((self.ten or "").split())
        if not self.ten:
            frappe.throw(_("Nhập tên nơi nhận."))
        if self.hinh_thuc and self.hinh_thuc not in TL.HINH_THUC:
            frappe.throw(_("Hình thức phải là {0}.").format(" / ".join(TL.HINH_THUC)))
