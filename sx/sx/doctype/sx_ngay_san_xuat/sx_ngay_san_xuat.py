import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from sx.utils import get_bom_active


class SXNgaySanXuat(Document):
    """Phiếu ngày sản xuất v3 — gắn báo mẻ / báo cán / sự cố; chốt sổ cuối ngày.
    Đơn vị ghi nhận NGÀY × LOẠI (D3), không có ca (D12)."""

    def validate(self):
        self.validate_duy_nhat_ngay()
        self.tinh_bao_me()
        self.validate_bao_can()
        self.sync_trang_thai()

    def validate_duy_nhat_ngay(self):
        trung = frappe.db.exists(
            "SX Ngay San Xuat",
            {"ngay": self.ngay, "docstatus": ("<", 2), "name": ("!=", self.name)},
        )
        if trung:
            frappe.throw(
                _("Ngày {0} đã có phiếu {1}. Mỗi ngày chỉ 1 phiếu.").format(
                    frappe.utils.formatdate(self.ngay), trung
                )
            )

    def tinh_bao_me(self):
        # Cỡ mẻ đọc từ BOM của item BTP (custom_co_me_chuan_kg) — 1 nguồn sự thật (D4)
        for row in self.bao_me:
            if flt(row.so_me) <= 0:
                frappe.throw(_("Báo mẻ dòng {0}: số mẻ phải > 0").format(row.idx))
            bom = get_bom_active(row.item_btp)
            if not bom:
                frappe.throw(_("BTP {0} chưa có BOM active").format(row.item_btp))
            row.co_me_kg = flt(frappe.db.get_value("BOM", bom, "custom_co_me_chuan_kg"))
            if not row.co_me_kg:
                frappe.throw(
                    _("BOM {0} chưa điền cỡ mẻ chuẩn (custom_co_me_chuan_kg)").format(bom)
                )
            row.tong_kg = flt(row.so_me) * flt(row.co_me_kg)

    def validate_bao_can(self):
        for row in self.bao_can:
            if flt(row.so_me) <= 0:
                frappe.throw(_("Báo cán dòng {0}: số mẻ phải > 0").format(row.idx))

    def sync_trang_thai(self):
        if self.docstatus == 0:
            self.trang_thai = "Đang chạy"

    def before_submit(self):
        # Submit CHỈ qua sx.api.chot.chot_ngay (spec 3.3)
        if not self.flags.tu_chot_ngay:
            frappe.throw(
                _("Không submit trực tiếp. Dùng nút CHỐT NGÀY trên portal /sx "
                  "(hoặc method sx.api.chot.chot_ngay).")
            )
        self.trang_thai = "Đã chốt"

    def on_cancel(self):
        # Chuỗi huỷ ngược nằm ở hook sx.api.chot.on_cancel_ngay (đọc ds_wo_se)
        self.db_set("trang_thai", "Đã huỷ", update_modified=False)
