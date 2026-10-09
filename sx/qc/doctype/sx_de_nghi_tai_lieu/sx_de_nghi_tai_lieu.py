"""Đề nghị soạn mới / sửa đổi / hủy bỏ / áp dụng tài liệu — BM.01.01 (W42, D171). Luật ở sx/qc/tai_lieu.py.

Nháp → Chờ xem xét (Trưởng Ban ISO) → Chờ duyệt (Giám đốc) → Đã duyệt; Trả lại về người đề nghị; Hủy. Trạng
thái chỉ đổi bằng nút trên màn Tài liệu (API đặt cờ frappe.flags.sx_de_nghi); người đề nghị không tự duyệt;
đã duyệt / đã hủy là khóa; đã gửi thì nội dung chỉ sửa khi bị trả lại."""

import frappe
from frappe import _
from frappe.model.document import Document

from sx.qc import tai_lieu as TL


class SXDeNghiTaiLieu(Document):
    def validate(self):
        if self.loai_yeu_cau not in TL.LOAI_YC:
            frappe.throw(_("Loại yêu cầu phải là {0}.").format(" / ".join(TL.LOAI_YC)))
        if self.trang_thai not in TL.TT_DN:
            frappe.throw(_("Trạng thái không hợp lệ."))
        if self.loai_yeu_cau in (TL.SUA_DOI, TL.HUY_BO) and not self.tai_lieu:
            frappe.throw(_("{0}: chọn tài liệu.").format(self.loai_yeu_cau))
        if self.loai_yeu_cau in (TL.SOAN_MOI, TL.AP_DUNG) and not (self.ten_de_xuat or "").strip():
            frappe.throw(_("Ghi tên tài liệu đề nghị."))
        co = getattr(frappe.flags, "sx_de_nghi", False)
        cu = self.get_doc_before_save()
        if cu:
            if cu.get("trang_thai") != self.trang_thai and not co:
                frappe.throw(_("Trạng thái đề nghị đổi bằng nút trên màn Tài liệu → Đề nghị."))
            if cu.get("trang_thai") in (TL.DA_DUYET, TL.HUY) and not co:
                frappe.throw(_("Đề nghị {0} đã {1} — khóa.").format(self.name, cu.get("trang_thai").lower()))
            if cu.get("trang_thai") not in TL.SUA_DUOC and not co and TL.doi_noi_dung(cu, self):
                frappe.throw(_("Đề nghị đã gửi — chỉ sửa nội dung khi bị trả lại."))
        elif self.trang_thai != TL.NHAP and not co:
            frappe.throw(_("Đề nghị mới là Nháp."))
        if self.trang_thai == TL.DA_DUYET and self.duyet_boi and self.duyet_boi == self.nguoi_de_nghi:
            frappe.throw(_("Người đề nghị không tự duyệt."))
