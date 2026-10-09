"""D143 (W17): tạo sẵn thiết bị đã biết tên trong tài liệu — lưới sàng LS-01 của từng máy rang
M1 / M2 / M3 và rây kiểm RY-01 (W02). Đồng hồ nhiệt, nam châm, cân: chưa biết số lượng / mã →
Ban ISO khai trên màn Thiết bị đo (hộp nhắc QC báo loại nào chưa có). Chạy lại vô hại.
"""

import frappe

DS = [(f"LS-01-M{k}", f"Lưới sàng LS-01 — máy rang M{k}", "Lưới sàng, rây", "4 Sàng cát", f"M{k}")
      for k in (1, 2, 3)] + [("RY-01", "Rây kiểm RY-01 (máy nghiền M1, M2)", "Lưới sàng, rây", "7 Nghiền", "")]


def execute():
    if not frappe.db.table_exists("SX Thiet Bi Do"):
        return
    for ma, ten, loai, vi_tri, may in DS:
        if frappe.db.exists("SX Thiet Bi Do", ma):
            continue
        frappe.get_doc({"doctype": "SX Thiet Bi Do", "ma": ma, "ten": ten, "loai": loai, "vi_tri": vi_tri,
                        "may": may}).insert(ignore_permissions=True)
