"""D100: phiếu QC cũ — giữ nguyên nghĩa khi thêm số máy và cờ lạc.

Từ D100 mục về lạc (B1, B2, B7) chỉ áp dụng khi lượt có làm vị có lạc, và ô máy
2/3 chỉ áp dụng khi có ghi số máy đang chạy. Phiếu trước D100 không có hai thứ
đó; để nguyên 0 thì mọi phiếu cũ có bột bỗng "không áp dụng" phần lạc — tờ in
lại tháng cũ mất hẳn mấy dòng đã ghi thật.

Nên: phiếu có bột → co_lac = can_thu_lac = 1 (đúng như lúc ghi, phần lạc hiện
với mọi lượt có bột). Số máy rỗng/0 → 1. Không qua ORM: phiếu đã submit không save
được, và đây không phải sửa nội dung phiếu. Frappe chạy patch MỘT lần lúc migrate
— lúc đó mọi phiếu trong DB đều là phiếu trước D100.
"""

import frappe

SO_MAY = ("so_may_rang", "so_may_nghien", "so_may_goi_bot")


def execute():
    if not frappe.db.table_exists("SX QC Round"):
        return
    cot = frappe.db.get_table_columns("SX QC Round")
    if "co_lac" in cot and "can_thu_lac" in cot:
        frappe.db.sql("""
            UPDATE `tabSX QC Round`
               SET co_lac = 1, can_thu_lac = 1
             WHERE co_san_xuat_bot = 1
        """)
    for c in SO_MAY:
        if c in cot:
            frappe.db.sql(f"UPDATE `tabSX QC Round` SET `{c}` = 1 "
                          f"WHERE IFNULL(`{c}`, 0) < 1")
