"""Bảng đơn giá khoán (D67, bỏ ràng buộc theo tháng ở D80).

Đơn giá khoán phụ thuộc hai chiều: MÃ HÀNG và CÁCH LÀM (làm tay / máy hỗ trợ…).
Dòng để trống `cach_lam` = giá chung cho mã hàng đó; tra thì ưu tiên dòng khớp đúng
cách làm, không có mới rơi về dòng chung.

═══ VÌ SAO BỎ "MỖI THÁNG MỘT BẢNG" (D80) ═══
Bản đầu bắt mỗi tháng lập một bảng mới và submit để khoá. Thực tế giá đứng yên
nhiều tháng liền, nên mỗi đầu tháng lại phải lập một bảng y hệt tháng trước — một
việc thừa mà quên là cả tháng tiền công tính 0.

Nay MỘT bảng là đủ: sửa giá ngay trên bảng đó, lưu là áp dụng. Ai muốn giữ giá cũ
để đối chiếu thì lập bảng thứ hai với `hieu_luc_tu` mới — ngày sản xuất nào dùng
bảng có hiệu lực gần nhất TRƯỚC ngày đó (xem sx.utils.bang_don_gia).

Bảng cũng không còn submit: "thay đổi thì tự cập nhật" mà bắt cancel + amend mới
sửa được giá thì không ai sửa, người ta đi ghi tay ra giấy.

Số tiền ĐÃ CHẤM không bị sửa theo: bảng vào hộp lưu `don_gia`/`thanh_tien` ngay lúc
ghi, sửa bảng giá chỉ ảnh hưởng những lần chấm/lưu SAU đó.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate


class SXBangDonGia(Document):
    def validate(self):
        self.hieu_luc_tu = getdate(self.hieu_luc_tu or nowdate())
        self.them_hang_loat()
        self.kiem_dong()
        self.kiem_trung_ngay()

    def kiem_trung_ngay(self):
        trung = frappe.db.get_value(
            "SX Bang Don Gia",
            {"hieu_luc_tu": self.hieu_luc_tu, "name": ("!=", self.name)},
            "name",
        )
        if trung:
            frappe.throw(
                _("Đã có bảng {0} hiệu lực từ đúng ngày này. Sửa thẳng bảng đó, hoặc "
                  "đổi ngày hiệu lực của bảng này.").format(trung)
            )

    def kiem_dong(self):
        thay = set()
        for r in self.dong:
            if not r.san_pham:
                frappe.throw(_("Dòng {0}: chưa chọn mã hàng.").format(r.idx))
            if flt(r.don_gia) <= 0:
                frappe.throw(_("Dòng {0}: đơn giá phải > 0.").format(r.idx))
            khoa = (r.san_pham, r.cach_lam or "")
            if khoa in thay:
                frappe.throw(
                    _("Dòng {0}: {1} + cách làm {2} bị khai hai lần. Trùng khoá thì "
                      "không biết lấy giá nào.").format(
                        r.idx, r.san_pham, r.cach_lam or _("(chung)"))
                )
            thay.add(khoa)

    def them_hang_loat(self):
        """Bung ô "chọn nhiều mã" thành các dòng thật rồi xoá sạch ô đó.

        Nhiều mã chỉ khác vị mà gia công y hệt nhau (sầu riêng / trà xanh / thượng
        hạng cùng quy cách 300g), nên gõ từng dòng một là chép tay hai chục lần cùng
        một con số. Chọn cả cụm, điền một giá, lưu.

        Bung ở SERVER chứ không phải bằng nút bấm trên Desk: làm ở đây thì nhập qua
        Data Import hay qua API cũng chạy đúng như nhau, mà không phải nuôi thêm một
        bản logic bằng JavaScript.

        Mã đã có dòng thì CẬP NHẬT giá, không tạo dòng trùng — trùng khoá là bảng tự
        mâu thuẫn, và kiem_dong() sẽ chặn ngay sau đây.
        """
        ds = [r.san_pham for r in (self.them_ma or []) if r.san_pham]
        if not ds:
            # Điền giá mà quên chọn mã: nói ra, đừng lặng lẽ nuốt con số vừa gõ.
            if flt(self.them_don_gia) > 0 or self.them_cach_lam:
                frappe.throw(
                    _("Mục 'Thêm nhiều mã cùng lúc' có đơn giá/cách làm nhưng CHƯA "
                      "chọn mã hàng nào. Chọn mã, hoặc xoá trống mục đó rồi lưu lại.")
                )
            return

        gia = flt(self.them_don_gia)
        if gia <= 0:
            frappe.throw(
                _("Đã chọn {0} mã hàng để thêm hàng loạt nhưng chưa điền đơn giá.")
                .format(len(ds))
            )
        cach = self.them_cach_lam or None
        khoa_cach = cach or ""
        co = {(r.san_pham, r.cach_lam or ""): r for r in self.dong}

        them, sua = [], []
        for sp in dict.fromkeys(ds):        # bỏ trùng, giữ nguyên thứ tự đã chọn
            cu = co.get((sp, khoa_cach))
            if cu is None:
                self.append("dong", {"san_pham": sp, "cach_lam": cach, "don_gia": gia})
                them.append(sp)
            elif flt(cu.don_gia) != gia:
                cu.don_gia = gia
                sua.append(sp)

        self.them_ma = []
        self.them_cach_lam = None
        self.them_don_gia = 0

        phan = []
        if them:
            phan.append(_("thêm {0} mã").format(len(them)))
        if sua:
            phan.append(_("đổi giá {0} mã").format(len(sua)))
        frappe.msgprint(
            _("Thêm hàng loạt: {0}{1}.").format(
                ", ".join(phan) or _("không có gì thay đổi"),
                _(" (cách làm {0})").format(cach) if cach else _(" (giá chung)"),
            ),
            indicator="green", alert=True,
        )

    def on_trash(self):
        # Xoá bảng cuối cùng là mọi lần chấm sau đó ra tiền công 0 mà không ai biết.
        con = frappe.db.count("SX Bang Don Gia") - 1
        if con <= 0:
            frappe.throw(
                _("Đây là bảng đơn giá DUY NHẤT. Xoá nó thì mọi lần chấm vào hộp sau "
                  "này ra tiền công 0. Lập bảng mới trước, rồi hãy xoá bảng này.")
            )


def _thang_nam_cu(doc):
    """Suy hieu_luc_tu từ tháng/năm của bảng cũ (D67). Dùng trong patch d80."""
    if not (cint(doc.get("nam")) and cint(doc.get("thang"))):
        return None
    return getdate(f"{cint(doc['nam']):04d}-{cint(doc['thang']):02d}-01")
