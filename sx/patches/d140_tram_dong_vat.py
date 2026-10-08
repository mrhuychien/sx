"""D140 (W15): tạo sẵn 40 trạm động vật gây hại R01–R21 (bẫy chuột), C01–C19 (côn trùng).

Khu / vị trí để trống — Ban ISO điền theo sơ đồ đặt trạm (Desk → SX Tram Dong Vat). Trạm
đã có thì bỏ qua (giữ khu / vị trí đã khai). Chạy lại vô hại.
"""

import frappe

from sx.qc.dong_vat import DS_TRAM


def execute():
    if not frappe.db.table_exists("SX Tram Dong Vat"):
        return
    for ma in DS_TRAM:
        if frappe.db.exists("SX Tram Dong Vat", ma):
            continue
        frappe.get_doc({"doctype": "SX Tram Dong Vat", "ma": ma,
                        "loai": "Bẫy chuột" if ma.startswith("R") else "Bẫy côn trùng"}).insert(
            ignore_permissions=True)
