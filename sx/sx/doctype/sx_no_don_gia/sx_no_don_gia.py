"""Sổ nợ đơn giá — sản lượng vào hộp đã chốt lúc mã hàng CHƯA khai đơn giá (D99).

Một dòng = một (ngày sản xuất, mã hàng, cách làm) chốt Vào hộp mà bảng đơn giá áp
dụng hôm đó chưa có giá. Lương khoán của những người làm mã đó đã nằm trong phiếu
lương tháng, nhưng ở mức 0 đồng — sổ này nhớ hộ để giá được bù vào sau.

Chuyển trạng thái chỉ đi qua sx/api/nogia.py (ap_gia / bo_qua_no_gia) và qua lúc
huỷ chốt Vào hộp — không sửa tay trên Desk: đổi sang "Đã cập nhật" mà phiếu lương
vẫn 0 đồng là sổ nói đã trả mà công nhân chưa được trả.
"""

import frappe
from frappe import _
from frappe.model.document import Document

TRANG_THAI_DONG = ("Đã cập nhật", "Bỏ qua", "Đã huỷ")


class SXNoDonGia(Document):
    def validate(self):
        if self.trang_thai == "Bỏ qua" and not (self.ly_do or "").strip():
            frappe.throw(_("Bỏ qua khoản nợ đơn giá thì phải ghi lý do."))
        if self.trang_thai == "Đã cập nhật" and not self.bang_don_gia:
            frappe.throw(_("Chưa áp giá vào phiếu lương — dùng nút Áp giá, đừng đổi "
                           "trạng thái tay."))
