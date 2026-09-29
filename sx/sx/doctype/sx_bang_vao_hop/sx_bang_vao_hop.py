import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from sx.utils import don_gia_ap_dung, tra_don_gia

# Mã giả cho dòng CÔNG NHẬT ở ranh giới API (D101): màn Ghi hộp coi công nhật như
# một "người" trong danh sách để QC chấm cùng một cách; trong DB thì dòng đó có
# nhan_vien rỗng + cong_nhat = 1. Chuyển đổi chỉ ở sx/api/portal.py.
CONG_NHAT = "CONG_NHAT"


class SXBangVaoHop(Document):
    """Bảng vào hộp — sản lượng TP + lương sản phẩm theo NGƯỜI (cả 2 nhánh bánh/bột).

    Từ D68 đơn vị ghi là MÃ HÀNG (× cách làm), không còn Activity Type. Lý do: cùng
    một mã hàng làm tay hay có máy hỗ trợ thì đơn giá khác nhau, mà Activity Type
    của ERPNext không mang được chiều đó — nó lại còn giữ đơn giá trong một field
    duy nhất, đổi giá là lương tháng cũ tính lại sai.
    """

    def validate(self):
        self.validate_duy_nhat()
        self.validate_nguoi()
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
            # Công nhật xuống cuối: bảng đọc theo người, công nhật không phải người.
            key=lambda r: (1 if cint(r.cong_nhat) else 0,
                           "" if cint(r.cong_nhat) else _ten(r.nhan_vien),
                           r.san_pham or "", r.cach_lam or ""),
        )
        for i, r in enumerate(dong, start=1):
            r.idx = i
        self.dong = dong

    def validate_nguoi(self):
        """Dòng khoán phải có người; dòng công nhật thì KHÔNG gắn người (D101).

        Công nhật gắn tên một người là lương khoán của người đó tự dưng có thêm
        hộp — đúng cái lỗi mà tách công nhật ra để tránh.
        """
        for r in self.dong:
            if cint(r.cong_nhat):
                r.nhan_vien = None
                r.ten_nhan_vien = None
            elif not r.nhan_vien:
                frappe.throw(_("Dòng {0}: chưa chọn công nhân.").format(r.idx))

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
        """Đơn giá LUÔN tra server-side từ bảng đơn giá áp dụng cho ngày đó — client
        gửi giá lên cũng bị ghi đè. Giá là tiền lương thật của người ta."""
        ngay = frappe.db.get_value("SX Ngay San Xuat", self.ngay_sx, "ngay")
        bang = don_gia_ap_dung(ngay) if ngay else {}
        thieu = []
        tong_hop = 0
        tong_tien = 0.0
        for row in self.dong:
            if cint(row.so_hop) <= 0:
                frappe.throw(_("Dòng {0}: số hộp phải > 0").format(row.idx))
            if not row.san_pham:
                frappe.throw(_("Dòng {0}: chưa chọn mã hàng.").format(row.idx))
            tong_hop += cint(row.so_hop)
            if cint(row.cong_nhat):
                # Sản lượng thật của xưởng, nhưng trả theo ngày công ở chỗ khác —
                # không đơn giá, không tiền, không cảnh báo thiếu giá.
                row.don_gia = 0
                row.thanh_tien = 0
                continue
            gia = tra_don_gia(bang, row.san_pham, row.cach_lam)
            if gia is None:
                thieu.append("• {0}{1}".format(
                    row.san_pham,
                    _(" (cách làm {0})").format(row.cach_lam) if row.cach_lam else ""))
                gia = 0
            row.don_gia = gia
            row.thanh_tien = flt(row.don_gia) * cint(row.so_hop)
            tong_tien += flt(row.thanh_tien)
        self.tong_hop = tong_hop
        self.tong_tien = tong_tien

        # Thiếu giá thì CHO LƯU nhưng nói to: QC đang đứng giữa xưởng, chặn họ lại
        # vì một dòng chưa khai giá là bắt cả chuyền dừng. Giá bổ sung sau, lưu lại
        # bảng là tính lại đúng. Nhưng im lặng để giá 0 thì tới cuối tháng mới lộ.
        if thieu:
            # Nêu ĐÍCH DANH bảng đang dùng: từ D80 có thể có nhiều bảng theo ngày hiệu
            # lực, nói "chưa khai giá" mà không nói khai ở bảng nào là bắt đi mò.
            from sx.utils import bang_don_gia
            ten_bang = bang_don_gia(ngay) if ngay else None
            ten_bang = _("(bảng {0})").format(ten_bang) if ten_bang else _("(chưa có bảng nào)")
            frappe.msgprint(
                _("Chưa khai đơn giá khoán {0} cho:").format(ten_bang)
                + "<br>" + "<br>".join(sorted(set(thieu)))
                + "<br><br>" + _("Các dòng này đang tính 0 đồng. Khai giá ở "
                                 "SX Bang Don Gia rồi lưu lại bảng vào hộp. Chốt "
                                 "trước khi có giá cũng được: các mã này vào SỔ NỢ "
                                 "ĐƠN GIÁ, áp giá sau ở màn Quản lý."),
                title=_("Thiếu đơn giá"), indicator="orange",
            )
