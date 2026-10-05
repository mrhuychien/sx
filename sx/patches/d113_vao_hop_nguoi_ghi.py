"""D113: dòng vào hộp có NGƯỜI GHI — gán cho các dòng cũ.

Từ D113 mỗi QC chỉ thấy / sửa dòng mình ghi. Dòng cũ chưa có người ghi thì không ai
thấy ngoài quản lý, và lần lưu kế tiếp của QC cũng không đụng tới — an toàn nhưng
"biến mất" khỏi màn của người đã ghi. Gán bằng người TẠO bảng (owner): trước D113
mỗi ngày thường một QC ghi, và đó là người gần đúng nhất.

SQL thẳng: bảng đã chốt (submit) không save lại được, và đây không phải sửa nội dung.
Chạy lại vô hại: chỉ đụng dòng còn trống người ghi.
"""

import frappe


def execute():
    if not frappe.db.table_exists("SX Bang Vao Hop Item"):
        return
    cot = frappe.db.get_table_columns("SX Bang Vao Hop Item")
    if "nguoi_ghi" not in cot:
        return
    frappe.db.sql("""
        UPDATE `tabSX Bang Vao Hop Item` i
          JOIN `tabSX Bang Vao Hop` b ON b.name = i.parent
           SET i.nguoi_ghi = b.owner,
               i.ghi_luc = IFNULL(i.ghi_luc, i.creation)
         WHERE i.parenttype = 'SX Bang Vao Hop'
           AND IFNULL(i.nguoi_ghi, '') = ''
    """)
