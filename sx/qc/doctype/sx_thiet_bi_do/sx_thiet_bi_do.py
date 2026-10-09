"""Thiết bị đo trong danh mục BM.06.01 (W17, D143). Luật ở sx/qc/thiet_bi.py."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, nowdate

from sx.qc import thiet_bi as TBM


class SXThietBiDo(Document):
    def before_insert(self):
        # autoname = field:ma đặt tên TRƯỚC validate — chuẩn hoá ở đây (như trạm động vật).
        self.ma = (self.ma or "").strip().upper()

    def validate(self):
        self.ma = (self.ma or "").strip().upper()
        if not self.ma:
            frappe.throw(_("Nhập mã thiết bị."))
        if cint(self.chu_ky_thang) < 0:
            frappe.throw(_("Chu kỳ kiểm không âm."))
        cuoi = None if self.is_new() else TBM.lan_cuoi(self.name)
        giay = None if self.is_new() else TBM.lan_cuoi(self.name, True)
        self.trang_thai, self.han_kiem = TBM.trang_thai(self.as_dict(), cuoi, nowdate(), TBM.han_dau(), giay)
