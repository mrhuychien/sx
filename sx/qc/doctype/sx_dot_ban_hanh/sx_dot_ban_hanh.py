"""Đợt ban hành = quyết định + Phụ lục 1 (tài liệu) (W42, D171). Luật ở sx/qc/tai_lieu.py.

Nháp → Đã ban hành chỉ qua API ban hành (cờ frappe.flags.sx_ban_hanh). Đã ban hành là khóa: số QĐ, ngày, QĐ
scan, danh sách tài liệu không đổi nữa — chỉ thêm hồ sơ của đợt (biên bản phổ biến có chữ ký…) và ghi chú."""

import frappe
from frappe import _
from frappe.model.document import Document

from sx.qc import tai_lieu as TL


class SXDotBanHanh(Document):
    def validate(self):
        if self.trang_thai not in (TL.DOT_NHAP, TL.DA_BAN_HANH):
            frappe.throw(_("Trạng thái đợt không hợp lệ."))
        for m in self.get("ds") or []:
            if m.hanh_dong not in TL.HANH_DONG:
                frappe.throw(_("Hành động phải là {0}.").format(" / ".join(TL.HANH_DONG)))
        co = getattr(frappe.flags, "sx_ban_hanh", False)
        cu = self.get_doc_before_save()
        if cu:
            if cu.get("trang_thai") != self.trang_thai and not co:
                frappe.throw(_("Ban hành bằng nút BAN HÀNH ở màn Tài liệu → Ban hành."))
            if cu.get("trang_thai") == TL.DA_BAN_HANH and not co and TL.doi_dot(cu, self):
                frappe.throw(_("Đợt {0} đã ban hành — chỉ thêm hồ sơ của đợt và ghi chú.").format(self.name))
        elif self.trang_thai != TL.DOT_NHAP and not co:
            frappe.throw(_("Đợt mới là Nháp."))
