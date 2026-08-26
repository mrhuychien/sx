import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

from sx.utils import don_gia_theo_thang, tra_don_gia


class SXBangVaoHop(Document):
    """Bảng vào hộp — sản lượng TP + lương sản phẩm theo NGƯỜI (cả 2 nhánh bánh/bột).

    Từ D68 đơn vị ghi là MÃ HÀNG (× cách làm), không còn Activity Type. Lý do: cùng
    một mã hàng làm tay hay có máy hỗ trợ thì đơn giá khác nhau, mà Activity Type
    của ERPNext không mang được chiều đó — nó lại còn giữ đơn giá trong một field
    duy nhất, đổi giá là lương tháng cũ tính lại sai.
    """

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
            key=lambda r: (_ten(r.nhan_vien), r.san_pham or "", r.cach_lam or ""),
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
        """Đơn giá LUÔN tra server-side từ bảng đơn giá của THÁNG đó — client gửi
        giá lên cũng bị ghi đè. Giá là tiền lương thật của người ta."""
        ngay = frappe.db.get_value("SX Ngay San Xuat", self.ngay_sx, "ngay")
        bang = don_gia_theo_thang(ngay) if ngay else {}
        thieu = []
        tong_hop = 0
        tong_tien = 0.0
        for row in self.dong:
            if cint(row.so_hop) <= 0:
                frappe.throw(_("Dòng {0}: số hộp phải > 0").format(row.idx))
            if not row.san_pham:
                frappe.throw(_("Dòng {0}: chưa chọn mã hàng.").format(row.idx))
            gia = tra_don_gia(bang, row.san_pham, row.cach_lam)
            if gia is None:
                thieu.append("• {0}{1}".format(
                    row.san_pham,
                    _(" (cách làm {0})").format(row.cach_lam) if row.cach_lam else ""))
                gia = 0
            row.don_gia = gia
            row.thanh_tien = flt(row.don_gia) * cint(row.so_hop)
            tong_hop += cint(row.so_hop)
            tong_tien += flt(row.thanh_tien)
        self.tong_hop = tong_hop
        self.tong_tien = tong_tien

        # Thiếu giá thì CHO LƯU nhưng nói to: QC đang đứng giữa xưởng, chặn họ lại
        # vì một dòng chưa khai giá là bắt cả chuyền dừng. Giá bổ sung sau, lưu lại
        # bảng là tính lại đúng. Nhưng im lặng để giá 0 thì tới cuối tháng mới lộ.
        if thieu:
            ten_bang = _("tháng {0}").format(getdate(ngay).strftime("%m/%Y")) if ngay else ""
            frappe.msgprint(
                _("Chưa khai đơn giá khoán {0} cho:").format(ten_bang)
                + "<br>" + "<br>".join(sorted(set(thieu)))
                + "<br><br>" + _("Các dòng này đang tính 0 đồng. Khai giá ở "
                                 "SX Bang Don Gia rồi lưu lại bảng vào hộp."),
                title=_("Thiếu đơn giá"), indicator="orange",
            )
