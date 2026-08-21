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
        # Sau khi CHỐT: không tính lại cỡ mẻ/tổng kg nữa. WO/SE đã sinh theo số cũ —
        # nếu ai sửa BOM giữa chừng, tính lại sẽ làm phiếu lệch chứng từ kho.
        # Từ D55 phiếu còn NHÁP khi mới chốt một nửa, nên không dựa vào docstatus
        # được nữa: mốc là cờ chot_ghiso.
        if self.docstatus == 0 and not cint(self.chot_ghiso):
            self.tinh_bao_me()
            self.validate_bao_can()
        else:
            self.chan_sua_bao_me()
        self.sync_trang_thai()

    def chan_sua_bao_me(self):
        """Chốt Ghi sổ rồi thì báo mẻ ĐÓNG BĂNG.

        Phiếu vẫn còn nháp (chờ chốt nốt Vào hộp) nên Frappe không tự khoá — mà
        chứng từ kho tầng 2 đã sinh theo đúng những con số này. Sửa được ở đây là
        phiếu một đằng, kho một nẻo, và không ai phát hiện ra."""
        truoc = self.get_doc_before_save()
        if not truoc:
            return
        cu = [(r.item_btp, flt(r.so_me), flt(r.tong_kg)) for r in truoc.bao_me]
        moi = [(r.item_btp, flt(r.so_me), flt(r.tong_kg)) for r in self.bao_me]
        if cu != moi:
            frappe.throw(
                _("Ngày {0} đã chốt Ghi sổ — báo mẻ không sửa được nữa (chứng từ kho "
                  "đã sinh theo số này). Huỷ chốt Ghi sổ trước nếu cần sửa.").format(self.name)
            )

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
        """Trạng thái đọc từ HAI CỜ, không từ docstatus (D55).

        Phiếu chốt một nửa vẫn là nháp; nếu cứ thấy nháp là ghi "Đang chạy" thì mỗi
        lần lưu lại xoá mất dấu vết đã chốt Ghi sổ."""
        if self.docstatus != 0:
            return
        xong = cint(self.chot_ghiso) + cint(self.chot_vaohop)
        self.trang_thai = ("Đang chạy", "Chốt một phần", "Đã chốt")[xong]

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
