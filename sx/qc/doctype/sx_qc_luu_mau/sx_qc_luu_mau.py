"""Lưu mẫu — mẫu thành phẩm giữ lại theo lô để đối chiếu khi có khiếu nại (D100).

Một bản ghi = một lần lấy mẫu của một lô. Ba trạng thái:
  Đang lưu   nằm trong tủ mẫu
  Đã lấy ra  mang đi dùng (khiếu nại, gửi kiểm nghiệm…) — BẮT BUỘC lý do
  Đã huỷ     hết hạn lưu thì huỷ; huỷ TRƯỚC hạn thì bắt buộc lý do

Vì sao bắt lý do: giá trị của tủ mẫu nằm ở chỗ khi khách khiếu nại lô X thì mẫu
lô X còn đó. Mẫu biến mất mà không ai ghi vì sao thì tủ mẫu chỉ còn là cái tủ.

Chuyển trạng thái đi qua sx/api/qc.py (xu_ly_luu_mau) — validate ở đây chặn cả
đường Desk.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

DANG_LUU = "Đang lưu"
DA_LAY_RA = "Đã lấy ra"
DA_HUY = "Đã huỷ"


class SXQCLuuMau(Document):
    def validate(self):
        if flt(self.so_luong) <= 0:
            frappe.throw(_("Số lượng mẫu phải lớn hơn 0."))
        if not self.ngay_lay:
            self.ngay_lay = nowdate()
        if not self.han_luu:
            frappe.throw(_("Chưa có ngày lưu đến."))
        if getdate(self.han_luu) < getdate(self.ngay_lay):
            frappe.throw(_("Ngày lưu đến ({0}) trước ngày lấy mẫu ({1}).").format(
                self.han_luu, self.ngay_lay))
        if self.san_pham and not self.ten_san_pham:
            self.ten_san_pham = frappe.db.get_value(
                "Item", self.san_pham, "item_name") or self.san_pham
        co_ly_do = bool((self.ly_do or "").strip())
        if self.trang_thai == DA_LAY_RA and not co_ly_do:
            frappe.throw(_("Lấy mẫu ra thì phải ghi lý do (khiếu nại nào, gửi kiểm "
                           "nghiệm ở đâu…)."))
        if (self.trang_thai == DA_HUY and not co_ly_do
                and getdate(self.han_luu) > getdate(nowdate())):
            frappe.throw(_("Mẫu chưa hết hạn lưu ({0}) — huỷ sớm thì phải ghi lý do.")
                         .format(frappe.utils.formatdate(self.han_luu)))
