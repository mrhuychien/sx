import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

from sx.utils import get_bot_from_dau, get_yield_bot

# on_submit / on_cancel gắn qua hooks -> sx.api.tang1 (chạy Manufacture T1).


class SXNhapBot(Document):
    """Nhập bột lô R vào Kho BTP. Manufacture T1 nằm ở api/tang1 (D7).

    Từ 28/07: KHÔNG còn card thao tác trên portal — chốt ngày TỰ tạo phiếu này cho
    mọi lô R rang hôm trước (chot._tu_nhap_bot). Vẫn tạo tay được trên Desk khi cần.
    """

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
            frappe.throw(_("Lô {0} đã được nhập bột ở phiếu {1}.").format(xd.lo_rang, trung))

        self.lo_rang = xd.lo_rang
        item_bot, bom = get_bot_from_dau(xd.loai_dau)
        self.item_bot = item_bot
        # D7: bột không cân — suy theo yield BOM T1
        self.bot_kg = flt(flt(xd.dau_kg) * get_yield_bot(bom, xd.loai_dau), 2)
        if self.bot_kg <= 0:
            frappe.throw(_("Bột tính ra 0 kg — kiểm tra phiếu xuất đậu / BOM tầng 1"))
