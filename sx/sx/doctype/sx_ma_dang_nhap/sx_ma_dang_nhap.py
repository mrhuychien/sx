"""Mã đăng nhập một lần cho QC (D81) — thứ nằm trong QR trên thẻ.

Lưu BĂM chứ không lưu mã gốc, đúng như lưu mật khẩu: ai đọc được bảng này cũng không
đăng nhập được bằng nó. Mã gốc chỉ tồn tại đúng một lần, lúc in thẻ.

Dùng MỘT LẦN rồi chết, và có hạn. Tờ giấy có QR đăng nhập là một thứ giấy tờ tuỳ
thân: rơi ra ngoài thì ai nhặt được cũng vào được. Một lần + có hạn giới hạn thiệt
hại, và còn để lại dấu: QC bảo "quét không vào" nghĩa là có người quét trước rồi.
"""

import frappe
from frappe.model.document import Document


class SXMaDangNhap(Document):
    pass


def don_ma_cu():
    """Xoá mã hết hạn quá 30 ngày. Gọi tay khi cần dọn, không gắn scheduler: bảng này
    mỗi lần cấp thẻ mới có một dòng, một xưởng 45 người thì cả năm chưa tới nghìn dòng."""
    cu = frappe.utils.add_days(frappe.utils.nowdate(), -30)
    for ten in frappe.get_all(
        "SX Ma Dang Nhap", filters={"het_han": ("<", cu)}, pluck="name"
    ):
        frappe.delete_doc("SX Ma Dang Nhap", ten, force=True, ignore_permissions=True)
