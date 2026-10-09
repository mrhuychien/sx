"""Một lần gửi mẫu kiểm nghiệm — KH.KN.01 (W18, D144). Luật ở sx/qc/kiem_nghiem.py.

  · Sản phẩm phải chọn sản phẩm trong bộ tự công bố; ngày gửi không sau hôm nay; ngày kết quả
    không trước ngày gửi; có kết quả mà chưa ghi ngày → ngày hôm nay.
  · Lần sau = ngày gửi + 12 tháng (sản phẩm).
  · Không đạt → phiếu sự cố (nguồn Kết quả kiểm nghiệm, mức Cao) một lần. Mẫu cát gắn nhật ký
    cát → kết quả chép sang nhật ký, phiếu sự cố do nhật ký cát lập (không trùng).
  · W35 (D166): mẫu nước / nguyên liệu / khác gắn VIỆC kiểm nghiệm định kỳ (SX Viec Dinh Ky có ô mẫu
    của) → lưu phiếu là ghi lần làm của việc (hạn dời sang kỳ sau, "Một lần" thì ngừng); mẫu của lấy
    theo việc; bỏ gắn / xoá phiếu → lần làm bỏ theo.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, nowdate

from sx.qc import kiem_nghiem as KN
from sx.qc import viec_dinh_ky as VD


class SXKiemNghiem(Document):
    def validate(self):
        hn = getdate(nowdate())
        if self.doi_tuong in (KN.SAN_PHAM, KN.CAT):
            self.viec_dinh_ky = None
        elif self.viec_dinh_ky:
            kn = frappe.db.get_value(VD.PT, self.viec_dinh_ky, "doi_tuong_kn")
            if not kn:
                frappe.throw(_("Việc {0} không phải việc kiểm nghiệm (chưa chọn mẫu của).").format(self.viec_dinh_ky))
            self.doi_tuong = kn
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
        self._ghi_viec()
        if self.doi_tuong == KN.CAT and self.nhat_ky_cat:
            sc = KN.dong_bo_cat(self)
            if sc and sc != self.su_co:
                self.db_set("su_co", sc, update_modified=False)
            return
        if self.ket_qua == KN.KHONG_DAT and not self.su_co:
            ten = (self.ten_san_pham or self.san_pham
                   or (self.viec_dinh_ky and frappe.db.get_value(VD.PT, self.viec_dinh_ky, "ten")) or self.doi_tuong)
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

    def _ghi_viec(self):
        """Lần làm của việc kiểm nghiệm = phiếu này (một lần — lưu lại không ghi thêm); đổi việc thì bỏ lần ở
        việc cũ. Lần sau của phiếu = hạn mới của việc."""
        cu = (self.get_doc_before_save() or {}).get("viec_dinh_ky")
        if cu and cu != self.viec_dinh_ky and frappe.db.exists(VD.PT, cu):
            v = frappe.get_doc(VD.PT, cu)
            if VD.bo_lan(v, self.name):
                v.save(ignore_permissions=True)
        if not self.viec_dinh_ky:
            return
        v = frappe.get_doc(VD.PT, self.viec_dinh_ky)
        if not any(r.get("phieu_kn") == self.name for r in v.get("ds_lan") or []):
            VD.ghi_lan(v, getdate(self.ngay_gui), _("Gửi mẫu — phiếu {0}").format(self.name), self.name)
            v.save(ignore_permissions=True)
            self.db_set("lan_sau", None if cint(v.ngung) else v.han, update_modified=False)

    def on_trash(self):
        if self.viec_dinh_ky and frappe.db.exists(VD.PT, self.viec_dinh_ky):
            v = frappe.get_doc(VD.PT, self.viec_dinh_ky)
            if VD.bo_lan(v, self.name):
                v.save(ignore_permissions=True)
