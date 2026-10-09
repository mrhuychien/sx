"""D146 (W21): tạo sẵn hai việc định kỳ tài liệu 08/10 nêu — thử khôi phục dữ liệu (T11/2026),
thay bóng đèn bẫy côn trùng (T3/2027). Hạn = cuối tháng đó, nhắc trước 30 ngày. Việc cùng tên đã
có thì bỏ qua (giữ hạn người ta đã sửa). Chạy lại vô hại.
"""

import frappe

DS = (
    ("Thử khôi phục dữ liệu app từ bản sao lưu", "Năm", "2026-11-30", "Quản trị app",
     "Khôi phục bản sao lưu gần nhất sang máy thử, mở app đối chiếu vài phiếu gần đây — ghi biên bản thử khôi phục."),
    ("Thay bóng đèn bẫy côn trùng", "Năm", "2027-03-31", "QC / bảo trì",
     "Thay bóng các đèn bẫy côn trùng (trạm C) — bóng giảm hiệu quả sau khoảng một năm; ghi ngày thay."),
)


def execute():
    if not frappe.db.table_exists("SX Viec Dinh Ky"):
        return
    for ten, chu_ky, han, phu_trach, mo_ta in DS:
        if frappe.db.exists("SX Viec Dinh Ky", {"ten": ten}):
            continue
        frappe.get_doc({"doctype": "SX Viec Dinh Ky", "ten": ten, "chu_ky": chu_ky, "han": han, "bao_truoc": 30,
                        "phu_trach": phu_trach, "mo_ta": mo_ta}).insert(ignore_permissions=True)
