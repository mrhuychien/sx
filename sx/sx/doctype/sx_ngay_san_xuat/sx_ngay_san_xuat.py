import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from sx.utils import get_settings, get_yield_tang_1


class SXNgaySanXuat(Document):
    """Phiếu ngày sản xuất — xương sống, đơn vị ghi nhận NGÀY (D9: không có ca)."""

    def validate(self):
        self.validate_duy_nhat_ngay()
        self.tinh_tang_1()
        self.sync_trang_thai()

    def validate_duy_nhat_ngay(self):
        # Duy nhất 1 phiếu docstatus<2 mỗi ngày
        trung = frappe.db.exists(
            "SX Ngay San Xuat",
            {"ngay": self.ngay, "docstatus": ("<", 2), "name": ("!=", self.name)},
        )
        if trung:
            frappe.throw(
                _("Ngày {0} đã có phiếu {1}. Mỗi ngày chỉ mở được 1 phiếu.").format(
                    frappe.utils.formatdate(self.ngay), trung
                )
            )

    def tinh_tang_1(self):
        if not self.chay_tang_1:
            self.so_bao_dau = 0
            self.dau_vao_kg = 0
            self.btp_du_kien_kg = 0
            return
        if not self.kl_bao_kg:
            self.kl_bao_kg = flt(get_settings().kl_bao_dau_kg)
        self.dau_vao_kg = flt(self.so_bao_dau) * flt(self.kl_bao_kg)
        self.btp_du_kien_kg = flt(self.dau_vao_kg * get_yield_tang_1(), 2)

    def sync_trang_thai(self):
        if self.docstatus == 0:
            self.trang_thai = "Đang chạy"

    def before_submit(self):
        # Submit CHỈ qua sx.api.chot.chot_ngay — chặn submit tay từ Desk (spec 2.1)
        if not self.flags.tu_chot_ngay:
            frappe.throw(
                _("Không submit trực tiếp. Dùng nút CHỐT NGÀY trên portal /sx "
                  "(hoặc method sx.api.chot.chot_ngay).")
            )
        self.trang_thai = "Đã chốt"

    def on_cancel(self):
        # Chuỗi huỷ ngược (SE/WO/SalaryProduct) nằm ở hook sx.api.chot.on_cancel_ngay
        self.db_set("trang_thai", "Đã huỷ", update_modified=False)
