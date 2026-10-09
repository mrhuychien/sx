"""Một lần gửi mẫu kiểm nghiệm — KH.KN.01 (W18, D144). Luật ở sx/qc/kiem_nghiem.py.

  · Sản phẩm phải chọn sản phẩm trong bộ tự công bố; ngày gửi không sau hôm nay; ngày kết quả
    không trước ngày gửi; có kết quả mà chưa ghi ngày → ngày hôm nay.
  · Lần sau = ngày gửi + 12 tháng (sản phẩm).
  · Không đạt → phiếu sự cố (nguồn Kết quả kiểm nghiệm, mức Cao) một lần. Mẫu cát gắn nhật ký
    cát → kết quả chép sang nhật ký, phiếu sự cố do nhật ký cát lập (không trùng).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

from sx.qc import kiem_nghiem as KN


class SXKiemNghiem(Document):
    def validate(self):
        hn = getdate(nowdate())
        if getdate(self.ngay_gui) > hn:
            frappe.throw(_("Ngày gửi mẫu không được sau hôm nay."))
        if self.doi_tuong == KN.SAN_PHAM and not self.san_pham:
            frappe.throw(_("Chọn sản phẩm (bộ tự công bố)."))
        if self.doi_tuong != KN.SAN_PHAM:
            self.san_pham = None
            self.ten_san_pham = None
        elif not self.ten_san_pham:
            self.ten_san_pham = frappe.db.get_value(KN.SP, self.san_pham, "ten_san_pham") or self.san_pham
        if self.doi_tuong != KN.CAT:
            self.nhat_ky_cat = None
        if self.ket_qua and not self.ngay_kq:
            self.ngay_kq = hn
        if self.ngay_kq and getdate(self.ngay_kq) < getdate(self.ngay_gui):
            frappe.throw(_("Ngày có kết quả không được trước ngày gửi mẫu."))
        if self.ngay_kq and getdate(self.ngay_kq) > hn:
            frappe.throw(_("Ngày có kết quả không được sau hôm nay."))
        self.lan_sau = KN.lan_sau(self.ngay_gui) if self.doi_tuong == KN.SAN_PHAM else None
        if self.is_new():
            self.nguoi_ghi = frappe.session.user

    def on_update(self):
        if self.doi_tuong == KN.CAT and self.nhat_ky_cat:
            sc = KN.dong_bo_cat(self)
            if sc and sc != self.su_co:
                self.db_set("su_co", sc, update_modified=False)
            return
        if self.ket_qua == KN.KHONG_DAT and not self.su_co:
            ten = self.ten_san_pham or self.san_pham or self.doi_tuong
            sc = frappe.get_doc({
                "doctype": "SX Su Co", "ngay": getdate(nowdate()), "nguon": "Kết quả kiểm nghiệm",
                "loai": "Khác", "muc_do": "Cao", "trang_thai": "Mở",
                "mo_ta": _("Kết quả kiểm nghiệm KHÔNG ĐẠT: {0}{1} — gửi mẫu {2}{3}{4}. Xem lại lô, lưu mẫu, "
                           "quyết định xử lý sản phẩm.").format(
                    ten, f" ({self.mo_ta_mau})" if self.mo_ta_mau else "",
                    getdate(self.ngay_gui).strftime("%d/%m/%Y"),
                    _(", phiếu {0}").format(self.so_phieu) if self.so_phieu else "",
                    _(", chỉ tiêu: {0}").format(self.chi_tieu) if self.chi_tieu else "")[:1000],
            })
            # Người ghi có thể không có quyền tạo phiếu sự cố trên Desk, nhưng kết quả không đạt
            # PHẢI có phiếu.
            sc.insert(ignore_permissions=True)
            self.db_set("su_co", sc.name, update_modified=False)
