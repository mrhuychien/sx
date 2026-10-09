"""Phiếu hành động khắc phục BM.01.07 (W24, D150). Luật ở sx/qc/khac_phuc.py; ở đây chặn cả đường Desk:

  · Phiếu từ sự cố phải gắn phiếu sự cố; mỗi sự cố tối đa một phiếu khắc phục chưa đóng.
  · Báo "đã thực hiện" (→ Chờ kiểm tra) phải có nguyên nhân, hành động, kết quả, ngày xong.
  · Kiểm tra hiệu lực, đóng, mở lại: Trưởng Ban ISO / người được giao (sx/qc/quyen.py) — người làm
    không tự xác nhận việc mình làm đã có hiệu lực. Chưa hiệu lực → về Mở, đếm số lần làm lại.
  · Số phiếu ghi ngược vào ô "Số CAR" của phiếu sự cố.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, nowdate

from sx.qc import khac_phuc as KP
from sx.qc.quyen import duoc_dong_su_co

QUYEN = _("Chỉ Trưởng Ban ISO hoặc người được giao mới kiểm tra hiệu lực / đóng / mở lại phiếu khắc phục — "
          "người làm không tự xác nhận.")


class SXKhacPhuc(Document):
    def validate(self):
        self.mo_ta = (self.mo_ta or "").strip()
        if not self.mo_ta:
            frappe.throw(_("Ghi điều không phù hợp (mô tả)."))
        if self.nguon not in KP.NGUON:
            frappe.throw(_("Chọn nguồn của phiếu khắc phục."))
        if self.trang_thai not in KP.TRANG_THAI:
            frappe.throw(_("Trạng thái không hợp lệ."))
        if self.nguon == KP.SU_CO and not self.su_co:
            frappe.throw(_("Phiếu khắc phục từ sự cố: chọn phiếu sự cố."))
        if self.su_co:
            if not frappe.db.exists("SX Su Co", self.su_co):
                frappe.throw(_("Không có phiếu sự cố {0}.").format(self.su_co))
            if self.trang_thai != KP.DONG:
                trung = frappe.get_all(KP.PT, filters={"su_co": self.su_co, "trang_thai": ("!=", KP.DONG),
                                                       "name": ("!=", self.name or "")}, pluck="name", limit=1)
                if trung:
                    frappe.throw(_("Sự cố {0} đã có phiếu khắc phục {1} chưa đóng.").format(self.su_co, trung[0]))
        if self.ngay_xong and getdate(self.ngay_xong) > getdate(nowdate()):
            frappe.throw(_("Ngày hoàn thành sau hôm nay."))
        if self.han and self.ngay and getdate(self.han) < getdate(self.ngay):
            frappe.throw(_("Hạn hoàn thành trước ngày lập phiếu."))
        if not self.lap_boi:
            self.lap_boi = frappe.session.user
        self.kiem_trang_thai()

    def kiem_trang_thai(self):
        cu = self.get_doc_before_save()
        tt_cu = cu.trang_thai if cu else KP.MO
        tt = self.trang_thai
        if cu and tt == tt_cu == KP.DONG and not duoc_dong_su_co():
            frappe.throw(_("Phiếu khắc phục đã đóng — nhờ Ban ISO mở lại nếu cần sửa."), frappe.PermissionError)
        # Kết luận / nhận xét kiểm tra là chữ của Ban ISO — người làm không ghi hộ (kể cả lúc lập trên Desk).
        doi_kiem = ((self.has_value_changed("hieu_luc") or self.has_value_changed("nhan_xet")) if cu
                    else bool(self.hieu_luc or (self.nhan_xet or "").strip()))
        if doi_kiem and not duoc_dong_su_co():
            frappe.throw(QUYEN, frappe.PermissionError)
        if tt == tt_cu:
            return
        if tt == KP.CHO_KIEM and tt_cu == KP.MO:
            thieu = KP.thieu_de_gui(self.as_dict())
            if thieu:
                frappe.throw(_("Chưa báo đã thực hiện được — còn thiếu: {0}.").format(", ".join(thieu)))
            self.ket_qua_boi = frappe.session.user
            self.hieu_luc = None          # chờ lần kiểm tra mới
            return
        if not duoc_dong_su_co():
            # Người làm chỉ được RÚT LẠI phiếu mình vừa báo xong (Chờ kiểm tra → Mở) khi chưa ai kiểm.
            if tt == KP.MO and tt_cu == KP.CHO_KIEM and not self.hieu_luc:
                return
            frappe.throw(QUYEN, frappe.PermissionError)
        if tt == KP.DONG:
            thieu = KP.thieu_de_gui(self.as_dict())
            if thieu:
                frappe.throw(_("Chưa đóng được — còn thiếu: {0}.").format(", ".join(thieu)))
            if self.hieu_luc != KP.CO_HIEU_LUC:
                frappe.throw(_("Đóng phiếu khắc phục khi đã kiểm tra: Có hiệu lực."))
            self.kiem_boi, self.kiem_ngay = frappe.session.user, nowdate()
        elif tt == KP.MO and tt_cu == KP.CHO_KIEM and self.hieu_luc == KP.CHUA_HIEU_LUC:
            if not (self.nhan_xet or "").strip():
                frappe.throw(_("Chưa hiệu lực: ghi nhận xét — làm gì tiếp."))
            self.so_lan = cint(self.so_lan) + 1
            self.ngay_xong = None
            self.kiem_boi, self.kiem_ngay = frappe.session.user, nowdate()
        elif tt_cu == KP.DONG:          # mở lại phiếu đã đóng
            self.hieu_luc = None

    def on_update(self):
        cu = self.get_doc_before_save()
        if cu and cu.su_co and cu.su_co != self.su_co:
            _bo_so_car(cu.su_co, self.name)
        if self.su_co and frappe.db.get_value("SX Su Co", self.su_co, "car_so") != self.name:
            frappe.db.set_value("SX Su Co", self.su_co, "car_so", self.name, update_modified=False)

    def on_trash(self):
        if self.su_co:
            _bo_so_car(self.su_co, self.name)


def _bo_so_car(su_co, ten):
    if frappe.db.get_value("SX Su Co", su_co, "car_so") == ten:
        frappe.db.set_value("SX Su Co", su_co, "car_so", None, update_modified=False)
