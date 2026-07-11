import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime, time_diff_in_hours

from sx.utils import get_settings


class SXGhiNhanCCP(Document):
    """Sổ giám sát CCP rang liên tục (D5: không có mẻ rang, ghi định kỳ)."""

    def validate(self):
        self.chan_sua_sau_24h()
        self.danh_gia_dat()

    def danh_gia_dat(self):
        settings = get_settings()
        nhiet_min = flt(settings.ccp_nhiet_min)
        nhiet_max = flt(settings.ccp_nhiet_max)
        self.dat = 1 if nhiet_min <= flt(self.nhiet_do_c) <= nhiet_max else 0

    def chan_sua_sau_24h(self):
        # Kỷ luật hồ sơ CCP: không sửa sau 24h, trừ SX Quan Ly (spec 2.2)
        if self.is_new():
            return
        if "SX Quan Ly" in frappe.get_roles() or "System Manager" in frappe.get_roles():
            return
        if time_diff_in_hours(now_datetime(), self.creation) > 24:
            frappe.throw(
                _("Bản ghi CCP quá 24h không được sửa (kỷ luật hồ sơ). "
                  "Liên hệ SX Quan Ly nếu cần điều chỉnh.")
            )
