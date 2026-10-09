"""Định nghĩa một sổ ghi theo dòng (W43, D172) — mã biểu mẫu, cột như giấy, vai ghi / xác nhận / xem. Luật ở
sx/qc/so.py. Chặn ở đây nên chặn cả Desk: khóa cột hợp lệ, không trùng; Select phải có lựa chọn; Link chỉ tới
DocType code cho phép; cột hạn phải là ngày; hàm riêng phải có tên trong code (không chạy biểu thức người gõ)."""

import frappe
from frappe import _
from frappe.model.document import Document

from sx.qc import so as SO


class SXSo(Document):
    def before_insert(self):
        # autoname = field:ma đặt tên TRƯỚC validate — chuẩn hoá ở đây (như SX Thiet Bi Do).
        self.ma = (self.ma or "").strip().upper()

    def validate(self):
        self.ma = (self.ma or "").strip().upper()
        self.ten = (self.ten or "").strip()
        self.tinh_toan = (self.tinh_toan or "").strip()
        for c in self.get("cot") or []:
            c.key = (c.key or "").strip()
            c.nhan = (c.nhan or "").strip()
        if self.xem_cuoi_thang and not (self.nhan_xem_thang or "").strip():
            self.nhan_xem_thang = SO.NHAN_XEM_MAC_DINH
        loi = SO.loi_dinh_nghia(SO.dinh_nghia_tu_doc(self))
        if loi:
            frappe.throw(_("Định nghĩa sổ {0}: {1}").format(self.ma, " ".join(loi)))
        if not self.is_new():
            self._kiem_khoa_dang_dung()

    def _kiem_khoa_dang_dung(self):
        """Bỏ / đổi khóa một cột đã có dữ liệu thì dòng cũ mang khóa lạ — không sửa được nữa. Chặn: thêm cột mới,
        đổi nhãn thì được; khóa đang dùng giữ nguyên."""
        cu = self.get_doc_before_save()
        if not cu:
            return
        con = {c.key for c in self.get("cot") or []}
        mat = [c.get("key") for c in cu.get("cot") or [] if c.get("key") not in con]
        if mat and frappe.db.exists(SO.PT_DONG, {"so": self.name}):
            frappe.throw(_("Sổ {0} đã có dòng ghi — không bỏ / đổi khóa cột {1}. Đổi nhãn, thêm cột mới thì được.")
                         .format(self.ma, ", ".join(mat)))
