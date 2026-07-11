import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from sx.utils import get_don_gia_vao_hop


class SXBangVaoHop(Document):
    """Bảng vào hộp — công đoạn duy nhất tính lương sản phẩm theo NGƯỜI (D6)."""

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
        ngay = frappe.db.get_value("SX Ngay San Xuat", self.ngay_sx, "ngay")
        tong_hop = 0
        tong_tien = 0.0
        for row in self.dong:
            if cint(row.so_hop) <= 0:
                frappe.throw(
                    _("Dòng {0}: số hộp phải > 0").format(row.idx)
                )
            # Đơn giá luôn lookup server-side — client không tự điền được
            row.don_gia = get_don_gia_vao_hop(row.san_pham, row.phuong_thuc, ngay)
            row.thanh_tien = flt(row.don_gia) * cint(row.so_hop)
            tong_hop += cint(row.so_hop)
            tong_tien += flt(row.thanh_tien)
        self.tong_hop = tong_hop
        self.tong_tien = tong_tien
