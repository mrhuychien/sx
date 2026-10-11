"""D187: bỏ những phần chỉ còn để đọc phiếu cũ (rà soát app theo sổ đăng ký tài liệu 21/9/2026).

  · SX QC Round: mọi phiếu về bộ mục bản 1. D187 gộp bản 1–3 cũ của BM.08.01 thành MỘT bộ mục hiện hành và bỏ T11
    "Cân: quả chuẩn", mục 5 thùng / vải ủ bản cũ, mục 6 một bộ nam châm (sx/qc/muc.py PHIEN_BAN). Phiếu ghi trước
    09/10/2026 nay đọc theo bộ mục hiện hành: mục có từ 08–09/10 để trống, ô cũ không còn trên màn / tờ in.
  · Ô "Độ ẩm (%)" trên dòng phiếu nhập mua / hoá đơn mua: xoá custom field (fixtures chỉ thêm, không tự xoá); ngưỡng
    "Độ ẩm tối đa" của SX QC Setting: xoá giá trị còn lại.
  · Ô ca (Sáng / Chiều) của SX QC Round, SX Su Co: chỉ bỏ khỏi DocType — không cần làm gì ở đây.
Frappe không xoá cột trong cơ sở dữ liệu khi bỏ field: số cũ còn nằm đó, app không đọc, không hiện nữa.
Chạy lại vô hại.
"""

import frappe

DO_AM = "custom_do_am"
DONG = ("Purchase Receipt Item", "Purchase Invoice Item")


def execute():
    if frappe.db.table_exists("SX QC Round"):
        n = frappe.db.count("SX QC Round", {"phien_ban": ("!=", 1)})
        if n:
            frappe.db.set_value("SX QC Round", {"phien_ban": ("!=", 1)}, "phien_ban", 1, update_modified=False)
        print(f"D187: {n} phiếu vòng kiểm về bộ mục bản 1")
    xoa = []
    for dt in DONG:
        ten = f"{dt}-{DO_AM}"
        if frappe.db.exists("Custom Field", ten):
            frappe.delete_doc("Custom Field", ten, ignore_permissions=True, force=True)
            xoa.append(ten)
    frappe.db.delete("Singles", {"doctype": "SX QC Setting", "field": "do_am_toi_da"})
    print(f"D187: xoá ô độ ẩm {', '.join(xoa) or '(không còn)'}; ngưỡng Độ ẩm tối đa đã dọn")
