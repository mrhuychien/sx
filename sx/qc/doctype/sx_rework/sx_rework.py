"""Phiếu rework BM.15.01 (W19, D145). Luật ở sx/qc/rework.py — chặn ở đây nên chặn cả Desk:
quá 10% khối lượng mẻ, hàng có lạc vào sản phẩm không lạc."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

from sx.qc import rework as RW


class SXRework(Document):
    def validate(self):
        if getdate(self.ngay) > getdate(nowdate()):
            frappe.throw(_("Ngày phiếu rework không được sau hôm nay."))
        nguon, dich = RW.san_pham(self.sp_nguon), RW.san_pham(self.sp_dich)
        if not nguon:
            frappe.throw(_("Chọn hàng đem rework thuộc sản phẩm nào (bộ tự công bố) — cần cờ có lạc."))
        if not dich:
            frappe.throw(_("Chọn sản phẩm nhận rework (bộ tự công bố) — cần cờ có lạc."))
        kq = RW.kiem(self.as_dict(), nguon, dich)
        self.ty_le = kq["ty_le"]
        self.nguon_co_lac, self.nguon_co_sua = nguon["co_lac"], nguon["co_sua_bot"]
        self.dich_co_lac, self.dich_co_sua = dich["co_lac"], dich["co_sua_bot"]
        if kq["loi"]:
            frappe.throw("<br>".join(kq["loi"]))
        for c in kq["canh_bao"]:
            frappe.msgprint(c, indicator="orange", alert=True)
        if self.is_new():
            self.nguoi_lap = frappe.session.user
