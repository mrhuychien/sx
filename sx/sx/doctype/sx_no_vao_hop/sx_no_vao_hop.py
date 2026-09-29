"""Sổ nợ vào hộp — kho nhận NHIỀU HƠN số QC đã chấm vào hộp (D101).

Trước D101 thủ kho duyệt phiếu nhập vượt số chấm là bị CHẶN (D70). Chặn giữ cho
kho khớp chấm công, nhưng làm hàng thật đứng ngoài kho chỉ vì QC chưa kịp chấm —
và hàng do bộ phận CÔNG NHẬT đóng thì không có chỗ nào chấm cả.

Từ D101: công nhật được chấm ngay ở màn Ghi hộp (dòng "Công nhật", không tính
khoán), nên vào hộp là số đếm ĐẦY ĐỦ của xưởng. Kho nhận vượt số đó thì vẫn duyệt,
phần vượt ghi thành một dòng nợ ở đây — nghĩa duy nhất: CHẤM SÓT.

Nợ tự giảm khi QC chấm bù (xem sx/api/khotp.py doi_soat_no_vao_hop — cùng công
thức "đã chấm − đã nhận" với trần nhập kho), về 0 thì tự đóng. Không có nút "đã
chấm bù" bấm tay: bấm tay được thì đóng được mà không chấm.
"""

import frappe
from frappe import _
from frappe.model.document import Document

CHO = "Chờ chấm"
TRANG_THAI_DONG = ("Đã chấm bù", "Bỏ qua", "Đã huỷ")


class SXNoVaoHop(Document):
    def validate(self):
        if self.trang_thai == "Bỏ qua" and not (self.ly_do or "").strip():
            frappe.throw(_("Bỏ qua khoản nợ vào hộp thì phải ghi lý do."))
