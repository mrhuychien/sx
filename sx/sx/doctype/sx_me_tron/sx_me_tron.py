import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from sx.utils import get_settings


class SXMeTron(Document):
    """Hồ sơ phối trộn theo mẻ — hồ sơ chất lượng, backflush kho theo BOM (D3)."""

    def before_insert(self):
        # Mẻ số auto đếm theo ngay_sx
        self.me_so = (
            frappe.db.count("SX Me Tron", {"ngay_sx": self.ngay_sx, "docstatus": ("<", 2)}) + 1
        )

    def validate(self):
        self.tinh_lech()
        self.canh_bao_lech()

    def tinh_lech(self):
        tong_dinh_muc = 0.0
        tong_lech = 0.0
        dung = 1
        for row in self.nguyen_lieu:
            if row.thuc_can_kg is None:
                row.thuc_can_kg = row.dinh_muc_kg
            row.lech_kg = flt(row.thuc_can_kg) - flt(row.dinh_muc_kg)
            row.lech_pct = (
                flt(row.lech_kg) / flt(row.dinh_muc_kg) * 100 if flt(row.dinh_muc_kg) else 0
            )
            tong_dinh_muc += flt(row.dinh_muc_kg)
            tong_lech += abs(flt(row.lech_kg))
            if flt(row.lech_kg, 4) != 0:
                dung = 0
        self.tong_lech_pct = tong_lech / tong_dinh_muc * 100 if tong_dinh_muc else 0
        self.dung_cong_thuc = dung

    def canh_bao_lech(self):
        nguong = flt(get_settings().me_tron_nguong_canh_bao_pct) or 2
        if flt(self.tong_lech_pct) > nguong:
            # Chỉ cảnh báo, không chặn (D3: lệch ghi nhận + cảnh báo)
            frappe.msgprint(
                _("Tổng lệch {0}% vượt ngưỡng cảnh báo {1}%. Vẫn lưu được — "
                  "trôi số sẽ xử lý bằng kiểm kê BTP định kỳ.").format(
                    flt(self.tong_lech_pct, 2), nguong
                ),
                indicator="orange",
                title=_("Lệch công thức"),
            )
