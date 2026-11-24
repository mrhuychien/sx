"""D241: 27/7 và 24/11 tính như Chủ nhật (lương sản phẩm ngày × hệ số), cạnh 1/1 đã có.

1. Điền ô SX Settings → "Ngày tính như Chủ nhật" = 01/01, 27/07, 24/11 nếu đang trống: người mở SX Settings thấy đủ
   danh sách đang áp dụng. (Ô trống vẫn tính theo mặc định đó — nhưng ai thấy ô trống rồi gõ thêm một ngày thì ba ngày
   mặc định mất, không ai báo.) Đã có giá trị thì để nguyên.
2. Tính lại phiếu lương NHÁP có ngày đi làm rơi vào ngày tính như Chủ nhật mà hệ số chưa đúng — vd ngày 24/11 đã chốt
   trước khi cập nhật: phiếu chỉ tự tính lại khi có lần chốt sau của chính người đó. Phiếu đã duyệt / đã huỷ: không đụng.
Chạy lại vô hại (ô đã có giá trị, phiếu đã đúng hệ số thì không lưu).
"""

import frappe
from frappe.utils import flt

from sx.sx.doctype.sx_phieu_luong.sx_phieu_luong import NGAY_NHU_CHU_NHAT, _cau_hinh, _la_ngay_he_so

TRUONG = "ngay_nhu_chu_nhat"


def phieu_can_tinh_lai(dong, cf):
    """Dòng ngày (parent, ngay, he_so) của phiếu NHÁP → tên phiếu có ngày hưởng hệ số mà hệ số đang lệch, theo thứ tự
    gặp, không trùng. Hàm thuần."""
    ra = []
    for r in dong:
        if r["parent"] in ra or not _la_ngay_he_so(r["ngay"], cf["ngay_he_so"]):
            continue
        if abs(flt(r["he_so"]) - flt(cf["he_so_le"])) > 1e-9:
            ra.append(r["parent"])
    return ra


def execute():
    if not frappe.db.exists("DocType", "SX Settings"):
        return
    if not str(frappe.db.get_single_value("SX Settings", TRUONG) or "").strip():
        frappe.db.set_single_value("SX Settings", TRUONG, NGAY_NHU_CHU_NHAT)
        frappe.clear_document_cache("SX Settings", "SX Settings")
        print(f"D241: SX Settings → Ngày tính như Chủ nhật = {NGAY_NHU_CHU_NHAT}")

    cf = _cau_hinh()
    dong = frappe.get_all("SX Phieu Luong Ngay",
                          filters={"parenttype": "SX Phieu Luong", "docstatus": 0},
                          fields=["parent", "ngay", "he_so"], order_by="parent asc, ngay asc")
    so, loi = 0, []
    for ten in phieu_can_tinh_lai(dong, cf):
        try:
            frappe.get_doc("SX Phieu Luong", ten).save(ignore_permissions=True)
            so += 1
        except Exception as e:       # một phiếu hỏng không làm hỏng cả lần migrate — ghi ra để người xem
            loi.append(f"{ten}: {e}")
    frappe.db.commit()
    print(f"D241: tính lại {so} phiếu lương nháp có ngày tính như Chủ nhật")
    for x in loi:
        print(f"D241: KHÔNG tính lại được {x}")
