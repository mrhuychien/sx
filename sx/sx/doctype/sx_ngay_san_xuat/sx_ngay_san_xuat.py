import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from sx.utils import get_bom_active


class SXNgaySanXuat(Document):
    """Phiếu ngày sản xuất v3 — gắn báo mẻ / báo cán / sự cố; chốt sổ cuối ngày.
    Đơn vị ghi nhận NGÀY × LOẠI (D3), không có ca (D12)."""

    def validate(self):
        self.validate_duy_nhat_ngay()
        # D123: không còn chốt — báo mẻ LUÔN sửa được; chứng từ kho tự đồng bộ theo
        # (sx/api/dongbo.py). Ngày cũ đã submit (trước D123) được patch mở lại.
        if self.docstatus == 0:
            self.tinh_bao_me()
            self.validate_bao_can()
        self.sync_trang_thai()

    def on_update(self):
        """Báo mẻ đổi (portal hay Desk) -> ngày cần đồng bộ kho (D123)."""
        truoc = self.get_doc_before_save()
        chu_ky = lambda d: sorted((r.item_btp, flt(r.tong_kg)) for r in (d.bao_me if d else []))
        if chu_ky(truoc) != chu_ky(self):
            from sx.api.dongbo import danh_dau
            danh_dau(self.name, "gs")

    def on_trash(self):
        """Xoá phiếu ngày -> rút chứng từ kho đã ghi, gỡ lương, huỷ nợ giá (D123)."""
        from sx.api.dongbo import go_het
        go_het(self)

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
        """D123: không còn chốt — phiếu ngày luôn là bản đang chạy."""
        if self.docstatus == 0:
            self.trang_thai = "Đang chạy"

    def before_submit(self):
        frappe.throw(_("Từ D123 không còn chốt ngày — số liệu tự đồng bộ vào kho và "
                       "phiếu lương, sửa lúc nào cũng được."))

    def on_cancel(self):
        # Chuỗi huỷ ngược nằm ở hook sx.api.chot.on_cancel_ngay (đọc ds_wo_se)
        self.db_set("trang_thai", "Đã huỷ", update_modified=False)
