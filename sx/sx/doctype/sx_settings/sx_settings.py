import frappe
from frappe import _
from frappe.model.document import Document


class SXSettings(Document):
    """Cấu hình app sx (Single): công ty + 3 kho. Yield từ BOM, prefix từ Item (D7/D10)."""

    def validate(self):
        # D241: ngày gõ sai (24/111, 31/04…) mà lặng lẽ bỏ qua thì công nhân đi làm ngày đó mất hệ số — chặn lưu, nói rõ.
        from sx.sx.doctype.sx_phieu_luong.sx_phieu_luong import doc_ngay_he_so

        sai = doc_ngay_he_so(self.get("ngay_nhu_chu_nhat"))[2]
        if sai:
            frappe.throw(_("Ô \"Ngày tính như Chủ nhật\": {0} không phải ngày có thật. Ghi dd/mm cho ngày đó mọi năm, "
                           "dd/mm/yyyy cho riêng một năm, cách nhau dấu phẩy — vd 01/01, 27/07, 24/11.").format(
                ", ".join(sai)), title=_("Ngày tính như Chủ nhật"))
