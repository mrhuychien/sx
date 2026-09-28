"""Sổ nợ BOM — thành phẩm đã nhập kho khi CHƯA có BOM (D97).

Một dòng = một dòng phiếu nhập kho được duyệt lúc mã hàng chưa có BOM active.
Hàng đã vào kho (Material Receipt, có lô theo ngày) nhưng nguyên liệu CHƯA bị
trừ — tồn bột / bao bì trên sổ đang cao hơn thực tế đúng bằng phần nợ này.

Vì sao là một DocType riêng chứ không phải một cờ trên phiếu nhập: nợ sống lâu
hơn phiếu (tạo BOM có khi mất vài tuần), được xử lý theo MÃ HÀNG chứ không theo
phiếu, và cần danh sách lọc được — "đang nợ những gì, nợ bao lâu rồi".

Chuyển trạng thái chỉ đi qua sx/api/khotp.py (hach_toan_bu / bo_qua_no) và qua
lúc huỷ phiếu nhập — không sửa tay trên Desk: đổi trạng thái mà không sinh / huỷ
chứng từ kho đi kèm là sổ nói một đằng, kho một nẻo.
"""

import frappe
from frappe import _
from frappe.model.document import Document

TRANG_THAI_DONG = ("Đã hạch toán bù", "Bỏ qua", "Đã huỷ")


class SXNoBOM(Document):
    def validate(self):
        if self.trang_thai == "Bỏ qua" and not (self.ly_do or "").strip():
            frappe.throw(_("Bỏ qua khoản nợ BOM thì phải ghi lý do."))
        if self.trang_thai == "Đã hạch toán bù" and not self.se_bu:
            frappe.throw(_("Chưa có phiếu kho trừ nguyên liệu — dùng nút Hạch toán bù, "
                           "đừng đổi trạng thái tay."))
