"""Một ngày trong nhật ký cát rang BM.08.03 (W20, D141). Luật tính ở sx/qc/cat.py.

Chặn ở đây nên chặn cả đường Desk:
  · mỗi ngày một dòng, không ghi trước ngày;
  · số ngày cát đã dùng / nguồn / đổi nguồn do app tính — ghi bù, sửa ngày, xoá một dòng
    thì cả chuỗi sau nó tính lại;
  · dòng Ban ISO đã xem xét thì khoá (chỉ Ban ISO sửa / xoá) — riêng kết quả kim loại
    nặng, số phiếu, lọ mẫu vẫn cập nhật được vì kết quả về sau ngày ký;
  · kim loại nặng Không đạt → tự lập phiếu sự cố (nguồn Nhật ký cát, mức Cao).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

from sx.qc import cat as CAT
from sx.qc.quyen import la_iso

# Sửa được sau khi Ban ISO đã xem xét (kết quả phòng kiểm nghiệm về muộn).
SAU_XEM = ("kln", "so_phieu_kln", "luu_lo_mau")
SUA = ("ngay", "ncc_cat", "thay_cat", "ve_sinh_thung", "ve_sinh_khay", "cam_quan", "ghi_chu")


class SXNhatKyCat(Document):
    def validate(self):
        d = getdate(self.ngay)
        if d > getdate(nowdate()):
            frappe.throw(_("Ngày ghi nhật ký cát không được sau hôm nay."))
        trung = frappe.db.exists(CAT.PT, {"ngay": str(d), "name": ("!=", self.name or "")})
        if trung:
            frappe.throw(_("Ngày {0} đã có nhật ký cát ({1}) — mở dòng đó mà sửa.").format(
                d.strftime("%d/%m/%Y"), trung))
        cu = None if self.is_new() else self.get_doc_before_save()
        if cu and cu.get("xem_luc") and not la_iso():
            doi = [f for f in SUA if str(cu.get(f) or "") != str(self.get(f) or "")]
            if doi:
                frappe.throw(_("Dòng ngày {0} Ban ISO đã xem xét — chỉ Ban ISO sửa được (kết quả kim "
                               "loại nặng / lọ mẫu thì vẫn cập nhật được).").format(d.strftime("%d/%m/%Y")),
                             frappe.PermissionError)
        if self.is_new():
            self.nguoi_ghi = frappe.session.user
        self.update(CAT.ke_tiep(CAT.dong_truoc(d, self.name), self.as_dict()))
        if not self.ncc_cat:
            frappe.throw(_("Chọn nguồn cát (NCC loại Cát rang) — có nguồn thì app mới biết lúc nào "
                           "đổi nguồn để nhắc kiểm kim loại nặng."))
        self.canh_bao_ncc()

    def canh_bao_ncc(self):
        """NCC chưa phân loại Cát rang / chưa duyệt BM.07.02: chỉ báo (W09 — không chặn mua)."""
        try:
            n = frappe.db.get_value("Supplier", self.ncc_cat, ["custom_loai_ncc", "custom_ncc_duyet"],
                                    as_dict=True)
        except Exception:
            return
        if n and (n.custom_loai_ncc != "Cát rang" or not n.custom_ncc_duyet):
            frappe.msgprint(_("Nguồn cát {0} chưa là NCC loại Cát rang được duyệt (BM.07.02) — Ban ISO "
                              "duyệt NCC trên Desk.").format(self.ncc_cat), indicator="orange", alert=True)

    def on_update(self):
        cu = self.get_doc_before_save()
        tu = getdate(self.ngay)
        if cu and cu.get("ngay"):
            tu = min(tu, getdate(cu.ngay))
        CAT.tinh_lai(tu)
        if self.kln == CAT.KLN_HONG and not self.su_co:
            self.lap_su_co()

    def lap_su_co(self):
        ten = self.ten_ncc or self.ncc_cat
        sc = frappe.get_doc({
            "doctype": "SX Su Co", "ngay": getdate(), "nguon": "Nhật ký cát", "loai": "Khác",
            "muc_do": "Cao", "trang_thai": "Mở",
            "mo_ta": _("Cát nguồn {0} (thay ngày {1}, {2}) KHÔNG ĐẠT kim loại nặng{3}. Ngừng dùng cát này, "
                       "thay cát; xem lại các lô đã rang bằng cát này.").format(
                ten, getdate(self.ngay).strftime("%d/%m/%Y"), self.name,
                _(" — phiếu {0}").format(self.so_phieu_kln) if self.so_phieu_kln else ""),
        })
        if frappe.db.exists("SX QC Cong Doan", "3 Rang"):
            sc.cong_doan = "3 Rang"
        # Người ghi có thể không có quyền tạo phiếu sự cố trên Desk, nhưng cát không đạt
        # PHẢI có phiếu — như lô không đạt xuất xưởng.
        sc.insert(ignore_permissions=True)
        self.db_set("su_co", sc.name, update_modified=False)

    def on_trash(self):
        if self.xem_luc and not la_iso():
            frappe.throw(_("Dòng này Ban ISO đã xem xét — chỉ Ban ISO xoá được."), frappe.PermissionError)
        CAT.tinh_lai(self.ngay, bo=self.name)
