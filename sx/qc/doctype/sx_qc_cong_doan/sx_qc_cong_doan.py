"""Công đoạn sản xuất cho phiếu sự cố (W04, D130).

Tên phải khớp QT.08 / KH.HACCP — bánh 16, bột 11 công đoạn. Đổi tên một công đoạn
đã dùng thì dùng RENAME chứ không sửa ô tên: tên là khoá (autoname field:ten), nên
Rename là để Frappe cập nhật mọi phiếu sự cố cũ đang trỏ tới nó — đúng việc "sửa tên
trên phiếu sự cố cũ" mà không phải chạy patch nào.

Vòng kiểm không tìm công đoạn theo tên mà theo MÃ (`ma`, đặt một lần) — đổi tên
thoải mái mà sự cố tự sinh vẫn gắn đúng công đoạn.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class SXQCCongDoan(Document):
    def validate(self):
        self.ten = " ".join((self.ten or "").split())
        if not self.ten:
            frappe.throw(_("Chưa có tên công đoạn."))
        if self.ma:
            self.ma = self.ma.strip()

    def after_rename(self, old, new, merge=False):
        dong = _("{0} → {1} ({2}, {3})").format(
            old, new, frappe.session.user, now_datetime().strftime("%d/%m/%Y %H:%M"))
        cu = frappe.db.get_value("SX QC Cong Doan", new, "ten_cu") or ""
        frappe.db.set_value("SX QC Cong Doan", new, "ten_cu",
                            (cu + "\n" + dong).strip(), update_modified=False)
