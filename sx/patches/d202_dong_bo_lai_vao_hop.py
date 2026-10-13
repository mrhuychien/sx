"""D202: ghi lại phiếu lương các ngày dính lỗi "'SXBangVaoHopItem' object is not subscriptable".

Lỗi ở hàm gom mã thiếu đơn giá (sx/api/nogia.py gom_thieu_gia đọc dòng bảng con bằng r["san_pham"]): ngày nào bảng
vào hộp có mã chưa khai đơn giá thì cả lần ghi phiếu lương + sổ nợ đơn giá của ngày đó bị rút lại; ngày giữ dấu "cần
đồng bộ" + câu lỗi, mà job dự phòng 5 phút KHÔNG tự thử lại ngày đang lỗi. Ở đây chạy lại phần vào hộp của đúng các
ngày đó NGAY trong lúc migrate — tiến trình migrate chạy mã đã sửa (xếp job thì worker chưa restart còn chạy mã cũ,
lỗi lại). Không đụng phần ghi sổ kho, không đụng ngày lỗi khác. Chạy lại vô hại: hết ngày mang câu lỗi này.
"""

import frappe
from frappe.utils import now_datetime

LOI = "object is not subscriptable"


def execute():
    from sx.api.dongbo import NGAY, dong_bo_vaohop

    if not frappe.db.has_column(NGAY, "loi_dong_bo_vh"):
        return
    ds = frappe.get_all(NGAY, filters={"docstatus": ("<", 2), "loi_dong_bo_vh": ("like", f"%{LOI}%")},
                        pluck="name")
    con = []
    for ten in ds:
        try:
            frappe.db.sql(f"select name from `tab{NGAY}` where name=%s for update", ten)
            loi = dong_bo_vaohop(frappe.get_doc(NGAY, ten))
        except Exception as e:  # noqa: BLE001 — migrate không được chết vì một ngày
            frappe.db.rollback()
            loi = [str(e) or e.__class__.__name__]
        vals = ({"can_dong_bo_vh": 1, "loi_dong_bo_vh": "\n".join(loi)} if loi
                else {"can_dong_bo_vh": 0, "loi_dong_bo_vh": None})
        frappe.db.set_value(NGAY, ten, dict(vals, dong_bo_luc=now_datetime()), update_modified=False)
        frappe.db.commit()
        if loi:
            con.append(f"{ten}: {loi[0]}")
    print(f"D202: ghi lại phiếu lương vào hộp {len(ds) - len(con)}/{len(ds)} ngày"
          + "".join(f"\n  còn lỗi {x}" for x in con))
