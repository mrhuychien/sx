"""Phiếu sự cố (BM.08.02).

Không submittable, `track_changes = 1`: sự cố sống lâu, qua tay nhiều người
(QC ghi xử lý ngay → QLSX ghi nguyên nhân → Ban ISO đóng), nên cái cần là VẾT
SỬA chứ không phải khoá sau khi ký. Ai sửa gì lúc nào nằm trong Version.

Một luật duy nhất nằm trong controller: KHÔNG ĐÓNG ĐƯỢC PHIẾU RỖNG. Đóng mà
chưa ghi xử lý ngay và chưa quyết định với sản phẩm thì tờ phiếu chỉ còn là
dấu tích "đã xong" — đúng cái mà hệ thống này sinh ra để tránh. Quyền ĐÓNG
(chỉ ISO Manager) chốt ở sx/api/qc.py, không ở đây: controller không biết lời
gọi đến từ màn hình nào.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, getdate, now_datetime, nowdate

from sx.qc.nguong import nguong


class SXSuCo(Document):
    def validate(self):
        self.qua_han = cint(self.tinh_qua_han())
        if self.trang_thai == "Đóng":
            self.kiem_du_de_dong()
            if not self.dong_boi:
                self.dong_boi = frappe.session.user
                self.dong_ngay = now_datetime()
        else:
            # Mở lại thì xoá dấu đóng cũ, đừng để lại "đóng bởi X" trên phiếu đang mở
            self.dong_boi = None
            self.dong_ngay = None

    def kiem_du_de_dong(self):
        thieu = []
        if not (self.xu_ly_ngay or "").strip():
            thieu.append(_("Xử lý ngay"))
        if not self.quyet_dinh_sp:
            thieu.append(_("Quyết định với sản phẩm"))
        if thieu:
            frappe.throw(_("Chưa đóng được phiếu — còn thiếu: {0}.").format(
                ", ".join(thieu)))

    def tinh_qua_han(self):
        if self.trang_thai == "Đóng" or not self.ngay:
            return 0
        han = cint(nguong()["su_co_qua_han_ngay"])
        return 1 if getdate(nowdate()) > add_days(getdate(self.ngay), han) else 0
