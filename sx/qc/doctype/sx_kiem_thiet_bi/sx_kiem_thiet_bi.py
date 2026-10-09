"""Một lần kiểm / hiệu chuẩn / kiểm định thiết bị đo — BM.06.02–06.04 (W17, D143).

Chặn ở đây nên chặn cả Desk:
  · ghi đủ tiêu chí của loại thiết bị; một tiêu chí Không đạt / sai số vượt cho phép → ép
    Không đạt (thiết bị ngừng dùng, app lập phiếu sự cố BM.08.02);
  · cân kiểm định bên ngoài phải có số giấy + hạn (hạn kiểm kế tiếp lấy từ đó);
  · Setting chọn "Giữ chứng chỉ" → người tự kiểm đồng hồ nhiệt phải có chứng chỉ còn hạn.
Ghi / sửa / xoá phiếu → tóm tắt + trạng thái trên thiết bị tính lại.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate

from sx.qc import thiet_bi as TBM


class SXKiemThietBi(Document):
    def validate(self):
        tb = frappe.db.get_value(TBM.TB, self.thiet_bi, ["loai", "ten"], as_dict=True)
        if not tb:
            frappe.throw(_("Không có thiết bị {0}.").format(self.thiet_bi))
        if tb.loai == TBM.SAN_XUAT:
            frappe.throw(_("{0} là thiết bị sản xuất — không hiệu chuẩn. Bảo dưỡng, sửa chữa ghi ở sổ BM.06.05; "
                           "đồng hồ nhiệt, nam châm, lưới gắn trên máy là thiết bị đo riêng trong danh mục.").format(
                self.thiet_bi))
        self.loai, self.ten_thiet_bi = tb.loai, tb.ten
        if getdate(self.ngay) > getdate(nowdate()):
            frappe.throw(_("Ngày kiểm không được sau hôm nay."))
        if self.is_new():
            self.nguoi_kiem = frappe.session.user
        if self.loai == TBM.DONG_HO and not self.sai_so_cho_phep:
            self.sai_so_cho_phep = 2        # ô Float trống = 0 = "không cho sai số nào" — không phải ý ai
        dg = TBM.danh_gia(self.as_dict())
        if dg["thieu"]:
            frappe.throw(_("Chưa ghi: {0}.").format(", ".join(dg["thieu"])))
        self.sai_so = dg["sai_so"]
        if not dg["hong"] and self.ket_qua not in (TBM.DAT, TBM.KHONG_DAT):
            frappe.throw(_("Chọn kết quả Đạt / Không đạt."))
        if dg["hong"] and self.ket_qua != TBM.KHONG_DAT:
            self.ket_qua = TBM.KHONG_DAT
            frappe.msgprint(_("Kết quả ghi Không đạt: {0}.").format("; ".join(dg["hong"])),
                            indicator="orange", alert=True)
        self.kiem_chung_chi()

    def kiem_chung_chi(self):
        """W17 (f) — chốt 09/10/2026: Đào tạo nội bộ (chỉ lưu biên bản). Setting đổi sang "Giữ chứng chỉ"
        thì chặn người tự kiểm chưa có chứng chỉ còn hạn."""
        if self.loai != TBM.DONG_HO or (self.hinh_thuc or TBM.NOI_BO) != TBM.NOI_BO:
            return
        try:
            st = frappe.get_cached_doc("SX QC Setting")
        except Exception:
            return
        if st.get("chung_chi_dong_ho") != "Giữ chứng chỉ":
            return
        if not TBM.co_chung_chi(st.get("nguoi_kiem_dong_ho"), self.nguoi_kiem or frappe.session.user, self.ngay):
            frappe.throw(_("Người kiểm đồng hồ nhiệt phải có chứng chỉ còn hạn (SX QC Setting → Biên bản đào tạo / "
                           "chứng chỉ người kiểm). Hiệu chuẩn bên ngoài thì chọn hình thức Hiệu chuẩn bên ngoài."),
                         frappe.PermissionError)

    def on_update(self):
        if self.ket_qua == TBM.KHONG_DAT and not self.su_co:
            self.db_set("su_co", TBM.lap_su_co_khong_dat(self), update_modified=False)
        cu = self.get_doc_before_save()
        if cu and cu.get("thiet_bi") and cu.thiet_bi != self.thiet_bi:
            TBM.cap_nhat(cu.thiet_bi)
        TBM.cap_nhat(self.thiet_bi)

    def after_delete(self):
        TBM.cap_nhat(self.thiet_bi)
