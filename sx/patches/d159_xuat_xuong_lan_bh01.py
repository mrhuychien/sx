"""D159 (W31): BM.08.04 theo phiếu giấy lần BH 01 — đổi kết luận của phiếu cũ sang bộ chữ mới.

Đạt → Cho xuất xưởng, Không đạt → Không cho xuất (giao việc 09/10/2026). Ghi thẳng DB, không qua
validate: phiếu đã duyệt bị khoá, và ô Select đã đổi danh sách lựa chọn. Mục đã chấm của phiếu cũ
(8 mục tạm "1".."8") giữ nguyên. Chạy lại vô hại — không còn giá trị cũ thì không làm gì.
"""

import frappe

from sx.qc import xuat_xuong as XX


def execute():
    if not frappe.db.table_exists(XX.PT):
        return
    for cu, moi in XX.KET_LUAN_CU.items():
        for n in frappe.get_all(XX.PT, filters={"ket_luan": cu}, pluck="name"):
            frappe.db.set_value(XX.PT, n, "ket_luan", moi, update_modified=False)
