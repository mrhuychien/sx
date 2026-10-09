"""Một vải ủ trong danh mục (W29, D163) — name = mã vải (V01-A).

QLSX / Ban ISO khai vải và đổi Đang dùng ↔ Dự phòng. Đã loại thì CHỈ qua dòng "Loại vải" của sổ giặt
BM.08.05 (sx/qc/vai_u.tinh_vai ghi thẳng, không qua đây) — loại vải tay ở danh mục là mất dòng sổ mà
HD.08.02 mục 8 đòi. Vải không bao giờ bị xoá vì loại: mã vải nằm trong hồ sơ 2 năm.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from sx.qc import vai_u as VU


class SXVaiU(Document):
    def before_insert(self):
        self.ma = VU.chuan_ma(self.ma)

    def validate(self):
        if not self.ma:
            frappe.throw(_("Ghi mã vải (vd V01-A)."))
        if not (self.thung or "").strip():
            self.thung = VU.thung_cua(self.ma)
        cu = None if self.is_new() else self.get_doc_before_save()
        truoc = cu.get("trang_thai") if cu else None
        if self.trang_thai == VU.DA_LOAI and truoc != VU.DA_LOAI:
            frappe.throw(_("Loại vải thì ghi một dòng \"Loại vải\" trong sổ giặt vải ủ (BM.08.05) — app tự chuyển "
                           "vải sang Đã loại."))
        if truoc == VU.DA_LOAI and self.trang_thai != VU.DA_LOAI:
            frappe.throw(_("Vải {0} đã loại theo sổ giặt (dòng {1}). Vải thay mới khâu lại mã này thì ghi dòng "
                           "Nhập vải mới; loại nhầm thì sửa / xoá dòng đó.").format(self.ma, self.dong_loai or "—"))
