"""Ô chọn nhiều mã hàng cùng lúc cho bảng đơn giá (D80).

Bảng con một cột, chỉ để làm ô "Table MultiSelect" — nơi gõ vài chục mã hàng rồi
gán chung một đơn giá. Không lưu gì lâu dài: controller bảng đơn giá bung nó ra
thành các dòng thật rồi xoá sạch ô này.
"""

from frappe.model.document import Document


class SXBangDonGiaMa(Document):
    pass
