"""Xác nhận đã đọc — một dòng mỗi người × tài liệu × lần ban hành (W42, D171).

Thay chữ ký nhận tài liệu trên biên bản phổ biến giấy (C28): mở PDF rồi bấm "Đã đọc, hiểu". Đã xác nhận thì
không sửa, không xóa — dòng này là bằng chứng phổ biến tài liệu."""

import frappe
from frappe import _
from frappe.model.document import Document

COT = ("tai_lieu", "lan_ban_hanh", "dot_ban_hanh", "user", "ho_ten", "vai", "mo_luc", "doc_luc")


class SXTaiLieuDoc(Document):
    def validate(self):
        cu = self.get_doc_before_save()
        if cu and cu.get("doc_luc") and any(str(cu.get(f) or "") != str(self.get(f) or "") for f in COT):
            frappe.throw(_("Đã xác nhận đọc — không sửa."))

    def on_trash(self):
        if self.doc_luc:
            frappe.throw(_("Không xóa xác nhận đã đọc — đó là bằng chứng phổ biến tài liệu."))
