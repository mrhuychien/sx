import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from sx.utils import get_activity_va_don_gia


class SXBangVaoHop(Document):
    """Bảng vào hộp — sản lượng TP + lương sản phẩm theo NGƯỜI (cả 2 nhánh bánh/bột)."""

    def validate(self):
        self.validate_duy_nhat()
        self.tinh_tien()

    def validate_duy_nhat(self):
        # 1 bảng docstatus<2 mỗi phiếu ngày
        trung = frappe.db.exists(
            "SX Bang Vao Hop",
            {"ngay_sx": self.ngay_sx, "docstatus": ("<", 2), "name": ("!=", self.name)},
        )
        if trung:
            frappe.throw(
                _("Phiếu ngày {0} đã có bảng vào hộp {1}.").format(self.ngay_sx, trung)
            )

    def tinh_tien(self):
        tong_hop = 0
        tong_tien = 0.0
        for row in self.dong:
            if cint(row.so_hop) <= 0:
                frappe.throw(_("Dòng {0}: số hộp phải > 0").format(row.idx))
            # Loại công việc + đơn giá luôn lấy server-side từ Activity Type
            # (nguồn giá duy nhất) — client không tự điền, không sửa được.
            row.activity_type, row.don_gia = get_activity_va_don_gia(row.san_pham)
            row.thanh_tien = flt(row.don_gia) * cint(row.so_hop)
            tong_hop += cint(row.so_hop)
            tong_tien += flt(row.thanh_tien)
        self.tong_hop = tong_hop
        self.tong_tien = tong_tien
