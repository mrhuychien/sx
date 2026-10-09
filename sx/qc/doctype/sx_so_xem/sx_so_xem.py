"""Một lần xem xét cuối tháng của một sổ (W43, D172) — ghi qua sx/api/qc_so.xem_thang. Dòng ghi bù SAU lần xem
thì tháng đó lại chờ xem (sx/qc/so.thang_chua_xem)."""

import frappe
from frappe import _
from frappe.model.document import Document

from sx.qc import so as SO


class SXSoXem(Document):
    def validate(self):
        try:
            SO.tinh_thang(self.thang)
        except ValueError:
            frappe.throw(_("Tháng dạng YYYY-MM (vd 2026-10)."))
        if not getattr(frappe.flags, "sx_so", False) and not self.is_new():
            frappe.throw(_("Lần xem xét đã ghi — không sửa. Xem lại thì bấm Đã xem tháng lần nữa trên màn Sổ."))
