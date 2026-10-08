"""Lưu mẫu — mẫu thành phẩm giữ lại theo lô để đối chiếu khi có khiếu nại (D100, D133).

Một bản ghi = một lần lấy mẫu của một lô. Bốn trạng thái:
  Đang lưu   nằm trong tủ mẫu
  Chờ huỷ    nằm trong một đợt huỷ tháng, chờ Ban ISO xác nhận (W07)
  Đã lấy ra  mang đi dùng (khiếu nại, gửi kiểm nghiệm…) — BẮT BUỘC lý do
  Đã huỷ     Ban ISO xác nhận đợt huỷ; huỷ TRƯỚC hạn thì bắt buộc lý do

W07: mẫu gắn LÔ (chọn theo HSD) → NSX / HSD lấy từ lô, hạn lưu mặc định NSX + 12 tháng.
Mẫu đang bị GIỮ (bấm "Giữ lại", hoặc lô có sự cố / khiếu nại đang mở — sx/qc/giu_mau.py)
không huỷ được, kể cả đường Desk.

Vì sao bắt lý do: giá trị của tủ mẫu nằm ở chỗ khi khách khiếu nại lô X thì mẫu
lô X còn đó. Mẫu biến mất mà không ai ghi vì sao thì tủ mẫu chỉ còn là cái tủ.

Chuyển trạng thái đi qua sx/api/qc.py (xu_ly_luu_mau) — validate ở đây chặn cả
đường Desk.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate

DANG_LUU = "Đang lưu"
CHO_HUY = "Chờ huỷ"
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
        self.gan_lo()
        co_ly_do = bool((self.ly_do or "").strip())
        if self.trang_thai == DA_LAY_RA and not co_ly_do:
            frappe.throw(_("Lấy mẫu ra thì phải ghi lý do (khiếu nại nào, gửi kiểm "
                           "nghiệm ở đâu…)."))
        if (self.trang_thai == DA_HUY and not co_ly_do
                and getdate(self.han_luu) > getdate(nowdate())):
            frappe.throw(_("Mẫu chưa hết hạn lưu ({0}) — huỷ sớm thì phải ghi lý do.")
                         .format(frappe.utils.formatdate(self.han_luu)))
        if cint(self.get("giu_lai")) and not (self.get("ly_do_giu") or "").strip():
            frappe.throw(_("Giữ lại mẫu thì phải ghi lý do (khiếu nại nào, điều tra gì…)."))
        if self.trang_thai == CHO_HUY and not self.get("dot_huy"):
            frappe.throw(_("Mẫu chờ huỷ phải nằm trong một đợt huỷ."))
        doi = getattr(self, "has_value_changed", None)
        if self.trang_thai in (DA_HUY, CHO_HUY) and (doi("trang_thai") if callable(doi) else True):
            from sx.qc.giu_mau import ly_do_giu

            giu = ly_do_giu([{"name": self.name or "_", "batch": self.get("batch"),
                              "hsd": self.get("hsd"), "giu_lai": self.get("giu_lai"),
                              "ly_do_giu": self.get("ly_do_giu")}])
            if giu:
                frappe.throw(_("Mẫu đang được GIỮ, không huỷ được — {0}").format(
                    next(iter(giu.values()))))

    def gan_lo(self):
        """Mẫu gắn lô (W07): NSX / HSD lấy từ lô; lô phải là lô của đúng sản phẩm."""
        if not self.get("batch"):
            return
        b = frappe.db.get_value("Batch", self.batch, ["item", "manufacturing_date",
                                                      "expiry_date"], as_dict=True)
        if not b:
            frappe.throw(_("Không thấy lô {0}.").format(self.batch))
        if self.san_pham and b.item != self.san_pham:
            frappe.throw(_("Lô đã chọn là của mã khác ({0}), không phải {1}.").format(
                b.item, self.san_pham))
        self.nsx = b.manufacturing_date
        self.hsd = b.expiry_date
