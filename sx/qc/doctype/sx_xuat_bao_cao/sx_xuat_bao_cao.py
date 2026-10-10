"""Một lần xuất hồ sơ theo dõi cho đoàn kiểm tra (D176). Dựng tệp ở job nền — sx/api/qc_xuatbc.py; luật dựng ở
sx/qc/xuat_bao_cao.py. Bản ghi giữ lại: ai xuất, lúc nào, kỳ nào, biểu mẫu nào, cho đoàn nào."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from sx.qc import xuat_bao_cao as XB


class SXXuatBaoCao(Document):
    def validate(self):
        if self.kieu not in XB.KIEU:
            frappe.throw(_("Kiểu tệp phải là {0}.").format(" / ".join(XB.KIEU)))
        if not self.tu or not self.den or getdate(self.tu) > getdate(self.den):
            frappe.throw(_("Kỳ xuất: từ ngày phải trước đến ngày."))
        self.trang_thai = self.trang_thai or XB.CHO
        if self.trang_thai not in XB.TRANG_THAI:
            frappe.throw(_("Trạng thái phải là {0}.").format(" / ".join(XB.TRANG_THAI)))
