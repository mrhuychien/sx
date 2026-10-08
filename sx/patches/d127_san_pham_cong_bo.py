"""D127 (W28): tạo sẵn 16 sản phẩm theo bộ tự công bố.

Chỉ ghi những gì danh sách 08/10/2026 đã nói chắc: số bản, loại, hạn dùng (bánh 9
tháng, bột và chè 12 tháng), tên của hai sản phẩm đã biết. Mười bốn tên còn lại để
"điền tên" cho Ban ISO sửa theo bản công bố — không bịa tên.

Chạy lại vô hại: số bản nào đã có thì bỏ qua (kể cả khi người ta đã sửa tên / cờ).
Không tự gắn mã hàng: gắn sai là QC bật ô thử lạc cho nhầm vị.
"""

import frappe

DS = (
    [(f"{i:02d}/2023", f"Bánh {i:02d}/2023 — điền tên theo bản công bố", "Bánh", 9, {})
     for i in range(1, 9)]
    + [("09/2021", "Bột đậu xanh dinh dưỡng", "Bột", 12, {}),
       # Chè đậu đen cốt dừa: có dừa (cốt dừa) và lạc (BOM hiện có Lạc — cùng lý do
       # nó là vị có lạc mặc định của QC từ D100).
       ("10/2021", "Chè đậu đen cốt dừa", "Chè", 12, {"co_dua": 1, "co_lac": 1})]
    + [(f"{i:02d}/HOANGGIANG/2026", f"Bột {i:02d}/HOANGGIANG/2026 — điền tên theo bản công bố",
        "Bột", 12, {}) for i in range(1, 7)]
)


def execute():
    if not frappe.db.table_exists("SX San Pham Cong Bo"):
        return
    for so, ten, loai, han, co in DS:
        if frappe.db.exists("SX San Pham Cong Bo", {"so_cong_bo": so}):
            continue
        frappe.get_doc({"doctype": "SX San Pham Cong Bo", "so_cong_bo": so,
                        "ten_san_pham": ten, "loai": loai, "han_dung_thang": han,
                        **co}).insert(ignore_permissions=True)
