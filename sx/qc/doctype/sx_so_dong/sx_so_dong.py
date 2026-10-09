"""Một dòng sổ (W43, D172). Luật ở sx/qc/so.py; ghi / sửa / xác nhận / ngừng qua sx/api/qc_so.py (kiểm quyền theo
định nghĩa sổ). Chặn ở đây nên chặn cả Desk:
  · dữ liệu kiểm theo cột của sổ (kiểu, bắt buộc, lựa chọn, không khóa lạ); tóm tắt, hạn gần nhất tự lập;
  · sổ Ghi theo dòng: ngày không sau hôm nay;
  · trạng thái, người ghi / xác nhận, lý do ngừng chỉ đổi qua API (cờ frappe.flags.sx_so);
  · dòng Ngừng, dòng Ghi theo dòng đã xác nhận: không đổi ngày, dữ liệu, sổ.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

from sx.qc import so as SO

CHI_API = ("trang_thai", "nguoi_ghi", "ghi_luc", "xac_nhan_boi", "xac_nhan_luc", "y_kien_xac_nhan", "ly_do_ngung")
NOI_DUNG = ("so", "ngay", "du_lieu")


class SXSoDong(Document):
    def validate(self):
        dn = SO.dinh_nghia(self.so)
        if not dn:
            frappe.throw(_("Không có sổ {0}.").format(self.so))
        self.ngay = getdate(self.ngay or nowdate())
        if dn["kieu"] == SO.GHI_THEO_DONG and self.ngay > getdate(nowdate()):
            frappe.throw(_("Ngày ghi sổ không được sau hôm nay."))
        du = SO.bo_sung(dn, SO.doc_json(self.du_lieu), SO.tra)
        sach, loi = SO.kiem_du_lieu(dn["cot"], du, SO.tra)
        if loi:
            frappe.throw(_("{0}: {1}").format(dn["ma"], " ".join(loi)))
        self.du_lieu = SO.ghi_json(sach)
        self.tom_tat = SO.tom_tat(dn["cot"], sach, SO.nhan_link(dn["cot"], sach))
        self.han_gan_nhat = SO.han_gan_nhat(dn["cot"], sach)
        self.trang_thai = self.trang_thai or SO.DA_GHI
        self._kiem_khoa(dn)

    def _kiem_khoa(self, dn):
        if getattr(frappe.flags, "sx_so", False):
            return
        cu = None if self.is_new() else self.get_doc_before_save()
        if self.is_new():
            if self.trang_thai != SO.DA_GHI or self.xac_nhan_luc or self.ly_do_ngung:
                frappe.throw(_("Dòng sổ mới ghi qua app (màn Sổ)."))
            return
        if not cu:
            return
        doi = [f for f in CHI_API if str(cu.get(f) or "") != str(self.get(f) or "")]
        if doi:
            frappe.throw(_("Trạng thái, người ghi, xác nhận, ngừng của dòng sổ chỉ đổi trên app (màn Sổ)."))
        khoa = cu.get("trang_thai") == SO.NGUNG or (dn["kieu"] == SO.GHI_THEO_DONG
                                                    and cu.get("trang_thai") == SO.DA_XAC_NHAN)
        if khoa and any(str(cu.get(f) or "") != str(self.get(f) or "") for f in NOI_DUNG):
            frappe.throw(_("Dòng {0} {1} — khóa, không sửa được.").format(
                self.name, "đã ngừng" if cu.get("trang_thai") == SO.NGUNG else "đã xác nhận"))
