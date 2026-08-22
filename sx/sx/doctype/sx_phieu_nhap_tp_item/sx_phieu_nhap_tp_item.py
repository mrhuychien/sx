from frappe.model.document import Document


class SXPhieuNhapTPItem(Document):
    """Một dòng phiếu nhận TP: số theo sổ ↔ số thủ kho ĐẾM, và phần lệch (D56).

    Không có logic riêng — `lech` và tổng do phiếu cha tính trong validate, để
    một chỗ duy nhất quyết định con số."""

    pass
