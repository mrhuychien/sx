"""Trạm kiểm soát động vật gây hại (W15, D140) — danh mục, mã in trên tem QR tại trạm."""

import re

import frappe
from frappe import _
from frappe.model.document import Document


class SXTramDongVat(Document):
    def before_insert(self):
        # autoname = field:ma đặt tên TRƯỚC validate — chuẩn hoá ở đây thì "r22" gõ trên
        # Desk thành trạm R22 chứ không thành bản ghi tên "r22" mà mã lại là "R22".
        self.chuan_hoa()

    def validate(self):
        self.chuan_hoa()
        if not re.fullmatch(r"[RC]\d{2}", self.ma or ""):
            frappe.throw(_("Mã trạm dạng R01 (bẫy chuột) hoặc C01 (côn trùng) — app đọc mã quét / gõ "
                           "theo đúng dạng này."))
        if not self.loai:
            self.loai = "Bẫy chuột" if self.ma.startswith("R") else "Bẫy côn trùng"

    def chuan_hoa(self):
        self.ma = (self.ma or "").strip().upper()
