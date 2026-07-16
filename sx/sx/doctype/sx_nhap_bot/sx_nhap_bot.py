import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

from sx.utils import get_settings, get_yield_tang_1


class SXNhapBot(Document):
    """Nhập bột lô R vào Kho BTP (tổ trộn, D14). GATE-C = phương án A:
    submit -> Batch (batch_id = lo_rang) + Stock Entry Material Receipt vào Kho BTP.
    Đậu KHÔNG trừ realtime — cân đối bằng kiểm kê định kỳ (D4)."""

    def validate(self):
        xd = frappe.get_doc("SX Xuat Dau", self.xuat_dau)
        if xd.docstatus != 1:
            frappe.throw(_("Phiếu xuất đậu {0} chưa submit").format(self.xuat_dau))
        if getdate(xd.ngay_rang) > getdate(nowdate()):
            frappe.throw(
                _("Lô {0} rang ngày {1} — chưa tới ngày rang, chưa nhập bột được.").format(
                    xd.lo_rang, frappe.utils.formatdate(xd.ngay_rang)
                )
            )
        trung = frappe.db.exists(
            "SX Nhap Bot",
            {"xuat_dau": self.xuat_dau, "docstatus": ("<", 2), "name": ("!=", self.name)},
        )
        if trung:
            frappe.throw(
                _("Lô {0} đã được nhập bột ở phiếu {1}.").format(xd.lo_rang, trung)
            )
        self.lo_rang = xd.lo_rang
        # D7: bột không cân — suy theo yield BOM T1
        self.bot_kg = flt(flt(xd.dau_kg) * get_yield_tang_1(), 2)
        if self.bot_kg <= 0:
            frappe.throw(_("Bột tính ra 0 kg — kiểm tra phiếu xuất đậu / BOM T1"))

    def on_submit(self):
        settings = get_settings()
        for f, label in (("item_bot", "Item bột BTP"), ("kho_btp", "Kho BTP"), ("cong_ty", "Công ty")):
            if not settings.get(f):
                frappe.throw(_("SX Settings chưa cấu hình: {0}").format(label))

        batch = frappe.get_doc(
            {
                "doctype": "Batch",
                "batch_id": self.lo_rang,
                "item": settings.item_bot,
                "custom_lo_rang": self.lo_rang,
            }
        )
        batch.flags.ignore_permissions = True
        batch.insert()

        se = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "purpose": "Material Receipt",
                "company": settings.cong_ty,
                "set_posting_time": 1,
                "posting_date": str(self.ngay_nhap),
                "to_warehouse": settings.kho_btp,
                "items": [
                    {
                        "item_code": settings.item_bot,
                        "qty": self.bot_kg,
                        "t_warehouse": settings.kho_btp,
                        "use_serial_batch_fields": 1,
                        "batch_no": batch.name,
                        # Bột BTP không định giá phase 1 (costing ngoài scope) — cho phép rate 0
                        "allow_zero_valuation_rate": 1,
                    }
                ],
            }
        )
        se.flags.ignore_permissions = True
        se.insert()
        se.submit()

        self.db_set("batch_bot", batch.name)
        self.db_set("se_nhap", se.name)

    def on_cancel(self):
        if self.se_nhap:
            se = frappe.get_doc("Stock Entry", self.se_nhap)
            if se.docstatus == 1:
                se.flags.ignore_permissions = True
                se.cancel()
        # Batch giữ nguyên nếu đã có ledger khác; nếu chưa dùng thì vẫn vô hại
        self.db_set("se_nhap", None)
