from frappe.model.document import Document


class SXCongKhoanAn(Document):
    """Một công khoán KHÔNG hiện ở bảng ghi hộp (D235) — vẫn là công khoán nhưng tính lương kiểu khác.
    Dòng của SX Settings → an_ghi_hop; sx.api.portal._nhan_vien_vao_hop đọc. Không có logic riêng."""

    pass
