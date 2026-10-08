"""Lô liên quan của một phiếu sự cố (W11, D134) — bảng con, không có logic riêng.

Mã hàng / tên / HSD do controller SX Su Co điền lại từ lô mỗi lần lưu: đường API
chỉ gửi mã lô, và fetch_from chỉ chạy trên form Desk.
"""

from frappe.model.document import Document


class SXSuCoLo(Document):
    pass
