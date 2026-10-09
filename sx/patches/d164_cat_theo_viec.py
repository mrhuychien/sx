"""D164 (W32): nhật ký cát BM.08.03 chuyển sang MỖI VIỆC MỘT DÒNG — đánh dấu dòng cũ (mỗi ngày có rang một dòng).

Dòng cũ giữ nguyên số liệu (số ngày đã dùng, nguồn, đổi nguồn, kim loại nặng, vệ sinh, xem xét), chỉ thêm:
  · so_cu = 1 — ngày của nó là ngày có rang, số ngày đã dùng của dòng cũ cuối cùng là mốc để đếm tiếp;
  · việc tương ứng: thay cát → "Rang khô đưa dùng"; vệ sinh thùng / khay → "Vệ sinh thùng, khay"; còn lại để trống
    (ngày có rang, không có việc gì với cát).
Ghi thẳng DB, không qua validate (dòng Ban ISO đã xem xét bị khoá). Chạy lại vô hại — dòng đã đánh dấu thì bỏ qua.
"""

import frappe
from frappe.utils import cint

from sx.qc import cat as CAT


def viec_cu(x):
    if cint(x.get("thay_cat")):
        return CAT.RANG_KHO
    if cint(x.get("ve_sinh_thung")) or cint(x.get("ve_sinh_khay")):
        return CAT.VE_SINH
    return ""


def execute():
    if not frappe.db.table_exists(CAT.PT):
        return
    for x in frappe.get_all(CAT.PT, filters={"so_cu": 0, "viec": ("is", "not set")},
                            fields=["name", "thay_cat", "ve_sinh_thung", "ve_sinh_khay"]):
        frappe.db.set_value(CAT.PT, x.name, {"so_cu": 1, "viec": viec_cu(x)}, update_modified=False)
