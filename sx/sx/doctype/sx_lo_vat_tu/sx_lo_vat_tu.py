import frappe
from frappe.model.document import Document


class SXLoVatTu(Document):
    """Lô đường/dầu đang mở — mỗi vật tư chỉ 1 lô dang_mo=1 tại 1 thời điểm."""

    def on_update(self):
        if self.dang_mo:
            # Đóng mọi lô khác cùng vật tư (1 lô hiện hành / vật tư)
            frappe.db.set_value(
                "SX Lo Vat Tu",
                {"vat_tu": self.vat_tu, "dang_mo": 1, "name": ("!=", self.name)},
                "dang_mo",
                0,
            )
