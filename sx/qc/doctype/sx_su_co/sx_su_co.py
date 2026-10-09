"""Phiếu sự cố (BM.08.02).

Không submittable, `track_changes = 1`: sự cố sống lâu, qua tay nhiều người
(QC ghi xử lý ngay → QLSX ghi nguyên nhân → Ban ISO đóng), nên cái cần là VẾT
SỬA chứ không phải khoá sau khi ký. Ai sửa gì lúc nào nằm trong Version.

Hai luật nằm trong controller (chặn cả đường Desk):
  · KHÔNG ĐÓNG ĐƯỢC PHIẾU RỖNG. Đóng mà chưa ghi xử lý ngay và chưa quyết định với
    sản phẩm thì tờ phiếu chỉ còn là dấu tích "đã xong" — đúng cái mà hệ thống này
    sinh ra để tránh.
  · CHỈ NGƯỜI CÓ QUYỀN MỚI ĐÓNG / MỞ LẠI (W11, D134): Trưởng Ban ISO, quản trị, hoặc
    người được giao trong SX QC Setting (sx/qc/quyen.py). Trước D134 luật này chỉ nằm
    ở sx/api/qc.py — trên Desk thì QC / QLSX có quyền ghi là tự đóng được phiếu.
    Cờ "Diễn tập" cũng vậy: đổi sau khi lập là cách giấu một sự cố thật khỏi số liệu.

Lô liên quan (W11): bảng `ds_lo`. Mã hàng / tên / HSD điền lại từ lô mỗi lần lưu, bỏ
dòng trùng lô.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, getdate, now_datetime, nowdate

from sx.qc import rework as RW
from sx.qc.nguong import nguong
from sx.qc.quyen import duoc_dong_su_co


class SXSuCo(Document):
    def validate(self):
        self.kiem_quyen()
        self.gan_lo()
        self.qua_han = cint(self.tinh_qua_han())
        if self.trang_thai == "Đóng":
            self.kiem_du_de_dong()
            if not self.dong_boi:
                self.dong_boi = frappe.session.user
                self.dong_ngay = now_datetime()
        else:
            # Mở lại thì xoá dấu đóng cũ, đừng để lại "đóng bởi X" trên phiếu đang mở
            self.dong_boi = None
            self.dong_ngay = None

    def _doi(self, truong):
        if self.is_new():
            return bool(self.get(truong)) and self.get(truong) not in ("Mở", 0, "0")
        return self.has_value_changed(truong)

    def kiem_quyen(self):
        """Đóng / mở lại / đổi cờ diễn tập: chỉ người có quyền (sx/qc/quyen.py).
        Phiếu MỚI lập ở trạng thái Mở, không cờ diễn tập — ai cũng lập được; phiếu
        mới lập thẳng Đóng thì cũng phải là người có quyền."""
        if duoc_dong_su_co():
            return
        if self._doi("trang_thai"):
            frappe.throw(_("Chỉ Trưởng Ban ISO hoặc người được giao mới đóng / mở lại được "
                           "phiếu sự cố — người ghi không tự duyệt."), frappe.PermissionError)
        if not self.is_new() and self.has_value_changed("dien_tap"):
            frappe.throw(_("Chỉ Trưởng Ban ISO hoặc người được giao mới đổi được cờ Diễn tập "
                           "sau khi lập phiếu."), frappe.PermissionError)

    def gan_lo(self):
        """Điền mã hàng / tên / HSD của từng lô; bỏ dòng trống, dòng trùng lô."""
        thay = []
        da = set()
        for r in self.get("ds_lo") or []:
            if not r.batch or r.batch in da:
                continue
            b = frappe.db.get_value("Batch", r.batch, ["item", "item_name", "expiry_date"],
                                    as_dict=True)
            if not b:
                frappe.throw(_("Không thấy lô {0}.").format(r.batch))
            r.item, r.ten, r.hsd = b.item, b.item_name or b.item, b.expiry_date
            da.add(r.batch)
            thay.append(r)
        if len(thay) != len(self.get("ds_lo") or []):
            self.set("ds_lo", thay)

    def kiem_du_de_dong(self):
        thieu = []
        if not (self.xu_ly_ngay or "").strip():
            thieu.append(_("Xử lý ngay"))
        if not self.quyet_dinh_sp:
            thieu.append(_("Quyết định với sản phẩm"))
        # W19 (D145): quyết định rework thì phải có phiếu rework BM.15.01 gắn với sự cố này.
        if self.quyet_dinh_sp == RW.QD_REWORK and not self.is_new() and not RW.co_phieu_cua_su_co(self.name):
            thieu.append(_("phiếu rework BM.15.01 (lập trên màn QC → Rework, chọn phiếu sự cố này)"))
        if thieu:
            frappe.throw(_("Chưa đóng được phiếu — còn thiếu: {0}.").format(
                ", ".join(thieu)))

    def tinh_qua_han(self):
        if self.trang_thai == "Đóng" or not self.ngay:
            return 0
        han = cint(nguong()["su_co_qua_han_ngay"])
        return 1 if getdate(nowdate()) > add_days(getdate(self.ngay), han) else 0
