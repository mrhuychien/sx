"""D123: bỏ CHỐT — mở lại ngày đã chốt và chuyển sang đồng bộ ngầm.

1. Phiếu ngày / bảng vào hộp ĐÃ SUBMIT (chốt cũ) về NHÁP bằng SQL — hai doctype này
   không có sổ cái riêng; submit chỉ để khoá sửa. Chứng từ kho / phiếu lương đã sinh
   GIỮ NGUYÊN và được ghi vào sổ cái đồng bộ, nên lần sửa sau chỉ điều chỉnh phần chênh.
2. so_cai_ghiso dựng từ báo mẻ đã chốt (dòng có SE còn hiệu lực).
3. Ngày có số liệu mà CHƯA từng chốt:
     · trong 3 ngày gần đây  -> đánh dấu cần đồng bộ, job chạy luôn;
     · cũ hơn                -> đánh dấu + ghi lỗi "ngày cũ chưa từng chốt" để KHÔNG tự
                                ghi kho hàng loạt; quản lý xem lại rồi bấm Thử lại.
Chạy lại vô hại: chỉ đụng ngày chưa có sổ cái / còn cờ chốt cũ.
"""

import json

import frappe
from frappe.utils import add_days, cint, flt, getdate, nowdate

GAN_DAY = 3
CU = "Ngày cũ chưa từng chốt trước khi bỏ chốt (D123) — kiểm lại số liệu rồi bấm Thử lại trên lịch Đồng bộ."


def execute():
    if not frappe.db.has_column("SX Ngay San Xuat", "so_cai_ghiso"):
        return
    for dt, con in (("SX Ngay San Xuat", ("SX Bao Me", "SX Bao Can", "SX Su Co Item")),
                    ("SX Bang Vao Hop", ("SX Bang Vao Hop Item", "SX Bang Vao Hop An Ca"))):
        ds = frappe.get_all(dt, filters={"docstatus": 1}, pluck="name")
        if not ds:
            continue
        frappe.db.sql(f"update `tab{dt}` set docstatus=0 where name in %s", (tuple(ds),))
        for c in con:
            if frappe.db.table_exists(c):
                frappe.db.sql(f"update `tab{c}` set docstatus=0 where parent in %s "
                              f"and parenttype=%s", (tuple(ds), dt))

    moc = getdate(add_days(nowdate(), -GAN_DAY))
    for n in frappe.get_all("SX Ngay San Xuat", filters={"docstatus": 0},
                            fields=["name", "ngay", "chot_ghiso", "chot_vaohop", "so_cai_ghiso",
                                    "salary_products_json"]):
        vals = {"trang_thai": "Đang chạy"}
        cu = getdate(n.ngay) < moc
        me = frappe.get_all("SX Bao Me", filters={"parent": n.name, "parenttype": "SX Ngay San Xuat"},
                            fields=["item_btp", "tong_kg", "batch", "wo", "se"], order_by="idx")
        if cint(n.chot_ghiso) and not n.so_cai_ghiso:
            vals["so_cai_ghiso"] = json.dumps([
                {"item": r.item_btp, "kg": flt(r.tong_kg, 3), "batch": r.batch, "wo": r.wo, "se": r.se}
                for r in me if r.se and frappe.db.get_value("Stock Entry", r.se, "docstatus") == 1])
        elif not cint(n.chot_ghiso) and me and not n.so_cai_ghiso:
            vals["can_dong_bo_gs"] = 1
            if cu:
                vals["loi_dong_bo_gs"] = CU
        co_bang = frappe.db.exists("SX Bang Vao Hop", {"ngay_sx": n.name, "docstatus": 0})
        if not cint(n.chot_vaohop) and co_bang and not n.salary_products_json:
            vals["can_dong_bo_vh"] = 1
            if cu:
                vals["loi_dong_bo_vh"] = CU
        vals["chot_ghiso"] = 0
        vals["chot_vaohop"] = 0
        frappe.db.set_value("SX Ngay San Xuat", n.name, vals, update_modified=False)
    frappe.db.commit()
