"""Sản phẩm theo bộ tự công bố (W28) — 16 sản phẩm, mỗi mã hàng gắn về một cái.

Vì sao một danh mục riêng chứ không ghi thẳng lên Item: hồ sơ ATTP nói theo SẢN
PHẨM TỰ CÔNG BỐ (16 cái), còn kho nói theo MÃ HÀNG (nhiều quy cách của cùng một
sản phẩm là nhiều mã). Kế hoạch kiểm nghiệm năm đếm theo sản phẩm; HSD, cờ lạc /
sữa / dừa thì mã nào cũng phải biết. Ghi một lần ở đây, mã hàng tra về.

Dùng ở:
  · HSD lúc nhập kho (sx.utils.han_dung): HSD = NSX + số tháng, NSX = HSD − số tháng
  · QC vòng kiểm: vị bột có lạc / có sữa bột → bật ô thử lạc, vệ sinh chuyển đổi
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

HAN_MAC_DINH = {"Bánh": 9, "Bột": 12, "Chè": 12}


class SXSanPhamCongBo(Document):
    def validate(self):
        self.so_cong_bo = " ".join((self.so_cong_bo or "").split())
        self.ten_san_pham = " ".join((self.ten_san_pham or "").split())
        if cint(self.han_dung_thang) <= 0:
            md = HAN_MAC_DINH.get(self.loai)
            if not md:
                frappe.throw(_("Chưa có hạn sử dụng (tháng)."))
            self.han_dung_thang = md
        if cint(self.han_dung_thang) > 60:
            frappe.throw(_("Hạn sử dụng {0} tháng — kiểm lại (nhập theo THÁNG, không "
                           "phải ngày).").format(self.han_dung_thang))

    def on_update(self):
        from sx.utils import xoa_nho

        xoa_nho()
