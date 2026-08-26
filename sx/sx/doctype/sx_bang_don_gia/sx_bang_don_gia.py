"""Bảng đơn giá khoán theo THÁNG (D67).

Đơn giá khoán phụ thuộc hai chiều: MÃ HÀNG và CÁCH LÀM (làm tay / máy hỗ trợ…),
và đổi theo tháng — trong cùng một tháng thì không đổi. Vì vậy mỗi tháng một bảng,
submit xong là khoá.

Vì sao mỗi tháng một bảng thay vì một field giá trên Item:
Field trên Item chỉ giữ giá HIỆN TẠI. Sang tháng sau sửa giá là toàn bộ lương đã
chấm tháng trước bị tính lại theo giá mới — sai, và sai âm thầm. Bảng theo tháng thì
lương tháng nào đọc bảng tháng đó, sửa giá tháng này không đụng gì tới tháng trước.

Dòng để trống `cach_lam` = giá chung cho mã hàng đó. Tra thì ưu tiên dòng khớp đúng
cách làm, không có mới rơi về dòng chung.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate


class SXBangDonGia(Document):
    def validate(self):
        if not 1 <= cint(self.thang) <= 12:
            frappe.throw(_("Tháng phải từ 1 đến 12."))
        if not 2000 <= cint(self.nam) <= 2999:
            frappe.throw(_("Năm không hợp lệ."))
        self.ap_dung_tu = getdate(f"{cint(self.nam):04d}-{cint(self.thang):02d}-01")

        trung = frappe.db.exists(
            "SX Bang Don Gia",
            {"thang": self.thang, "nam": self.nam, "docstatus": ("<", 2),
             "name": ("!=", self.name)},
        )
        if trung:
            frappe.throw(
                _("Tháng {0}/{1} đã có bảng đơn giá {2}. Mỗi tháng chỉ một bảng — "
                  "sửa bảng đó, hoặc huỷ rồi lập lại.").format(self.thang, self.nam, trung)
            )

        thay = set()
        for r in self.dong:
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
        if self.docstatus == 0:
            self.trang_thai = "Nháp"

    def before_submit(self):
        if not self.dong:
            frappe.throw(_("Bảng đơn giá rỗng — không submit."))
        self.trang_thai = "Đang áp dụng"

    def on_cancel(self):
        self.db_set("trang_thai", "Đã huỷ", update_modified=False)
