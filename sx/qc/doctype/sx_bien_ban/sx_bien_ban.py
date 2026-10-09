"""Biên bản (W45, D174) — lập, sửa, gửi ký, ký, trả lại qua sx/api/qc_bienban.py (kiểm vai, thứ tự ký). Chặn ở đây nên
chặn cả Desk:
  · mọi lần lưu phải đi qua API (cờ frappe.flags.sx_bb) — Desk chỉ đọc;
  · biên bản Đã ký đủ là KHÓA: không đổi nội dung, ngày, chữ ký, bản ký tay (kể cả qua API) — chỉ thêm phiếu liên quan
    (BM.01.07 lập từ dòng không phù hợp) và nối việc giao với việc định kỳ.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from sx.qc import bien_ban as BB

KHOA = ("mau", "ngay", "tieu_de", "noi_dung", "dinh_nghia", "ban_ky_tay", "nguoi_lap", "so")


def _ky(doc):
    return [(r.get("vai_tro"), r.get("user"), str(r.get("ky_luc") or "")) for r in doc.get("ky") or []]


class SXBienBan(Document):
    def validate(self):
        if not getattr(frappe.flags, "sx_bb", False):
            frappe.throw(_("Biên bản lập, sửa, ký trên app (QC → Xem xét → Biên bản)."), frappe.PermissionError)
        self.trang_thai = self.trang_thai or BB.NHAP
        if self.trang_thai not in BB.TRANG_THAI:
            frappe.throw(_("Trạng thái biên bản không hợp lệ."))
        cu = None if self.is_new() else self.get_doc_before_save()
        if cu is not None and cu.get("trang_thai") == BB.DA_KY:
            doi = [f for f in KHOA if str(cu.get(f) or "") != str(self.get(f) or "")]
            if doi or self.trang_thai != BB.DA_KY or _ky(cu) != _ky(self):
                frappe.throw(_("Biên bản {0} đã ký đủ — khóa, không sửa được.").format(self.name))
