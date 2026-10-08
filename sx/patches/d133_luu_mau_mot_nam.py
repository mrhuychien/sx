"""D133 (W07): lưu mẫu 1 năm — kéo dài hạn lưu của mẫu ĐANG LƯU.

Trước D133 hạn lưu mặc định = ngày lấy + 180 ngày. Mẫu đang nằm trong tủ mà hạn còn
ngắn hơn ngày lấy + 12 tháng thì nâng lên ngày lấy + 12 tháng (mẫu cũ không gắn lô nên
không có NSX — ngày lấy mẫu là mốc gần NSX nhất). Không rút ngắn hạn nào, không đụng
mẫu đã lấy ra / đã huỷ. Chạy lại vô hại.
"""

import frappe
from frappe.utils import add_months, getdate


def execute():
    if not frappe.db.table_exists("SX QC Luu Mau"):
        return
    for m in frappe.get_all("SX QC Luu Mau", filters={"trang_thai": "Đang lưu"},
                            fields=["name", "ngay_lay", "han_luu"]):
        if not m.ngay_lay:
            continue
        moi = add_months(getdate(m.ngay_lay), 12)
        if not m.han_luu or getdate(m.han_luu) < moi:
            frappe.db.set_value("SX QC Luu Mau", m.name, "han_luu", moi, update_modified=False)
