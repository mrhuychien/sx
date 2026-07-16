import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from sx.utils import get_item_dau, get_settings, sinh_lo_rang


class SXXuatDau(Document):
    """Phiếu xuất đậu D-1 -> sinh lô rang R. Neo gốc truy xuất lô đậu NCC ↔ lô R.

    Phase 1 KHÔNG tạo Stock Entry (đậu trừ qua kiểm kê định kỳ) — se_xuat để trống.
    """

    def validate(self):
        if cint(self.so_bao) <= 0:
            frappe.throw(_("Số bao phải > 0"))
        if not self.kl_bao_kg:
            self.kl_bao_kg = flt(get_settings().kl_bao_dau_kg)
        self.dau_kg = cint(self.so_bao) * flt(self.kl_bao_kg)
        self.validate_lo_dau()
        if not self.lo_rang:
            self.lo_rang = sinh_lo_rang(self.ngay_rang)

    def validate_lo_dau(self):
        # Lô NCC phải là batch của đúng item đậu (RM của BOM T1)
        item_dau = get_item_dau()
        item_cua_lo = frappe.db.get_value("Batch", self.lo_dau_ncc, "item")
        if item_cua_lo != item_dau:
            frappe.throw(
                _("Lô {0} thuộc item {1} — không phải đậu xanh ({2}).").format(
                    self.lo_dau_ncc, item_cua_lo, item_dau
                )
            )
