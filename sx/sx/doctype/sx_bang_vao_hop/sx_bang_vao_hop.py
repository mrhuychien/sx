import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from sx.utils import get_activity_type, get_don_gia_activity


class SXBangVaoHop(Document):
    """Bảng vào hộp — sản lượng TP + lương sản phẩm theo NGƯỜI (cả 2 nhánh bánh/bột)."""

    def validate(self):
        self.validate_duy_nhat()
        self.gop_theo_nguoi()
        self.tinh_tien()

    def gop_theo_nguoi(self):
        """Xếp các dòng của CÙNG một công nhân liền nhau (D26).

        Công nhân tự đối chiếu sản lượng của mình — dòng nằm rải rác thì rất khó dò.
        Sắp theo tên rồi tới loại công việc; đánh lại idx cho khớp thứ tự hiển thị.
        """
        ten = {}

        def _ten(nv):
            if nv not in ten:
                ten[nv] = frappe.db.get_value("Employee", nv, "employee_name") or nv
            return ten[nv]

        dong = sorted(
            self.dong,
            key=lambda r: (_ten(r.nhan_vien), r.activity_type or "", r.san_pham or ""),
        )
        for i, r in enumerate(dong, start=1):
            r.idx = i
        self.dong = dong

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
            # Đơn vị tính lương khoán là LOẠI CÔNG VIỆC (D23). Có SKU thì SKU quyết
            # định loại (map Item.custom_activity_type) — khỏi lệch tay.
            if row.san_pham:
                row.activity_type = get_activity_type(row.san_pham)
            if not row.activity_type:
                frappe.throw(
                    _("Dòng {0}: chưa chọn loại công việc khoán (Activity Type).")
                    .format(row.idx)
                )
            # Đơn giá luôn tính server-side từ Activity Type — client không sửa được.
            row.don_gia = get_don_gia_activity(row.activity_type)
            row.thanh_tien = flt(row.don_gia) * cint(row.so_hop)
            tong_hop += cint(row.so_hop)
            tong_tien += flt(row.thanh_tien)
        self.tong_hop = tong_hop
        self.tong_tien = tong_tien
