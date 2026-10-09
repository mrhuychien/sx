"""Phiếu hành động khắc phục BM.01.07 (W24, D150) — phiếu gọn, gắn với sự cố.

Một phiếu đi ba bước:
  1. MỞ — mô tả điều không phù hợp (lấy từ phiếu sự cố), nguyên nhân gốc, hành động khắc phục, người
     làm, hạn. Ai vào được màn QC đều ghi được (QC, QLSX, Ban ISO) — như phần xử lý của phiếu sự cố.
  2. CHỜ KIỂM TRA — đã làm xong: ghi kết quả, ngày xong.
  3. ĐÓNG — Trưởng Ban ISO / người được giao (sx/qc/quyen.py) kiểm tra HIỆU LỰC: có hiệu lực thì đóng;
     chưa hiệu lực thì phiếu quay về Mở (đếm số lần làm lại), làm tiếp cho tới khi có hiệu lực.
Hành động khắc phục là xoá NGUYÊN NHÂN để việc không lặp lại — khác "xử lý ngay" của phiếu sự cố
(xử lý sản phẩm, máy lúc phát hiện). Vì vậy đóng phiếu sự cố không chờ phiếu khắc phục, và ngược lại —
chốt 09/10/2026: không bắt buộc sự cố nào (kể cả mức Cao) phải có phiếu khắc phục mới đóng.

Mỗi sự cố tối đa một phiếu khắc phục chưa đóng; số phiếu ghi ngược vào ô "Số CAR" của sự cố.
Hộp nhắc: phiếu Mở quá hạn (mức cao), phiếu chờ kiểm tra hiệu lực quá CHO_KIEM ngày.
W45 (D174): nguồn "Thẩm tra" — phiếu lập từ dòng Không đạt của báo cáo thẩm tra BM.04.02 (khung Biên bản).
"""

import frappe
from frappe.utils import getdate

PT = "SX Khac Phuc"
MO, CHO_KIEM, DONG = "Mở", "Chờ kiểm tra", "Đóng"
TRANG_THAI = (MO, CHO_KIEM, DONG)
SU_CO = "Sự cố"
NGUON = (SU_CO, "Khiếu nại", "Đánh giá nội bộ", "Đánh giá bên ngoài", "Xem xét của lãnh đạo", "Thẩm tra", "Khác")
CO_HIEU_LUC, CHUA_HIEU_LUC = "Có hiệu lực", "Chưa hiệu lực"
CHO_KIEM_TOI_DA = 7     # ngày chờ Ban ISO kiểm tra hiệu lực thì lên hộp nhắc


def qua_han(x, hom_nay):
    """Phiếu Mở đã quá hạn hoàn thành — hàm thuần."""
    return x.get("trang_thai") == MO and bool(x.get("han")) and getdate(x["han"]) < getdate(hom_nay)


def thieu_de_gui(x):
    """Ô còn thiếu để báo "đã thực hiện" (chuyển Chờ kiểm tra) — hàm thuần."""
    ten = {"nguyen_nhan": "Nguyên nhân", "hanh_dong": "Hành động khắc phục", "ket_qua": "Kết quả thực hiện",
           "ngay_xong": "Ngày hoàn thành"}
    return [v for k, v in ten.items() if not str(x.get(k) or "").strip()]


def nhac(hom_nay):
    """Dữ liệu hộp nhắc: {qua_han: [...], cho_kiem: [...]}. Chưa migrate → {}."""
    d = getdate(hom_nay)
    try:
        ds = frappe.get_all(PT, filters={"trang_thai": ("in", [MO, CHO_KIEM])},
                            fields=["name", "trang_thai", "han", "ngay_xong", "mo_ta", "su_co"], order_by="han asc")
    except Exception:
        return {}
    return {"qua_han": [{"name": x.name, "han": str(x.han), "mo_ta": x.mo_ta or ""} for x in ds if qua_han(x, d)],
            "cho_kiem": [{"name": x.name, "ngay_xong": str(x.ngay_xong or "")} for x in ds
                         if x.trang_thai == CHO_KIEM
                         and (d - getdate(x.ngay_xong or d)).days > CHO_KIEM_TOI_DA]}
