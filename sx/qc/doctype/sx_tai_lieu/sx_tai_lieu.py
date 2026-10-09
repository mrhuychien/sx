"""Một tài liệu của thư viện (W42, D171). Luật ở sx/qc/tai_lieu.py.

Bản Hiện hành / Hết hiệu lực: lần BH, ngày, PDF, trạng thái, đợt và lịch sử chỉ đổi qua Ban hành (API đặt cờ
frappe.flags.sx_ban_hanh) — không sửa tay, kể cả trên Desk. Tên, phân phối, ghi chú Trưởng Ban ISO sửa được."""

import frappe
from frappe import _
from frappe.model.document import Document

from sx.qc import tai_lieu as TL


class SXTaiLieu(Document):
    def validate(self):
        self.ma = " ".join((self.ma or "").split())
        self.ten = " ".join((self.ten or "").split())
        if not self.ten:
            frappe.throw(_("Nhập tên tài liệu."))
        self.loai = self.loai or TL.KHAC                 # như mặc định của DocType
        self.nguon = self.nguon or TL.NOI_BO
        self.trang_thai = self.trang_thai or TL.DU_THAO
        for f, ds in (("loai", TL.LOAI), ("nguon", TL.NGUON), ("trang_thai", TL.TRANG_THAI)):
            if self.get(f) not in ds:
                frappe.throw(_("{0} phải là {1}.").format(f, " / ".join(ds)))
        if self.ma and frappe.db.exists(TL.PT, {"ma": self.ma, "name": ("!=", self.name)}):
            frappe.throw(_("Mã {0} đã có ở tài liệu khác — mỗi mã một tài liệu.").format(self.ma))
        if self.thuoc and self.thuoc == self.name:
            frappe.throw(_("Tài liệu không thuộc chính nó."))
        co = getattr(frappe.flags, "sx_ban_hanh", False)
        cu = self.get_doc_before_save()
        if cu and cu.get("trang_thai") in (TL.HIEN_HANH, TL.HET) and not co:
            doi = TL.doi_khoa(cu, self)
            if doi:
                frappe.throw(_("Tài liệu đã ban hành: {0} chỉ đổi qua Ban hành (màn Tài liệu → Ban hành), không "
                               "sửa tay.").format(", ".join(doi)))
        elif not cu and self.trang_thai != TL.DU_THAO and not co:
            frappe.throw(_("Tài liệu mới là Dự thảo — ban hành qua một đợt ban hành."))
