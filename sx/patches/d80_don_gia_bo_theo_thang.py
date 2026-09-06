"""D80: bảng đơn giá bỏ ràng buộc theo tháng — điền hieu_luc_tu, gỡ trạng thái submit.

Bảng cũ (D67) đặt tên theo tháng và được SUBMIT để khoá. Từ D80 bảng không còn
submit nữa; nếu để nguyên docstatus=1 thì trên Desk chúng thành chứng từ đã duyệt
của một doctype không submit được — mở ra không sửa được mà cũng không huỷ được.

Bảng đã CANCEL (docstatus=2) thì để yên: đó là bảng người ta cố ý bỏ, kéo về nháp
là làm nó sống lại và tranh chỗ với bảng đang dùng.
"""

import frappe


def execute():
    if not frappe.db.table_exists("SX Bang Don Gia"):
        return
    if not frappe.db.has_column("SX Bang Don Gia", "hieu_luc_tu"):
        return

    # 1) hieu_luc_tu suy từ dữ liệu cũ: ưu tiên ap_dung_tu, không có thì ngày 1 của
    #    tháng/năm, không có nữa thì ngày tạo bảng.
    for b in frappe.get_all(
        "SX Bang Don Gia",
        filters={"hieu_luc_tu": ("is", "not set")},
        fields=["name", "thang", "nam", "ap_dung_tu", "creation"],
    ):
        ngay = b.ap_dung_tu
        if not ngay and b.nam and b.thang:
            ngay = f"{int(b.nam):04d}-{int(b.thang):02d}-01"
        if not ngay:
            ngay = frappe.utils.getdate(b.creation)
        frappe.db.set_value("SX Bang Don Gia", b.name, "hieu_luc_tu", ngay,
                            update_modified=False)

    # 2) docstatus 1 -> 0. Doctype không còn submittable nên 1 là trạng thái kẹt.
    frappe.db.sql("""
        UPDATE `tabSX Bang Don Gia` SET docstatus = 0 WHERE docstatus = 1
    """)

    # 3) Hai bảng trùng ngày hiệu lực thì bảng cũ hơn lùi lại một ngày, để cả hai
    #    cùng tồn tại được (field unique). Bảng mới nhất giữ đúng ngày của nó.
    trung = frappe.db.sql("""
        SELECT hieu_luc_tu FROM `tabSX Bang Don Gia`
        GROUP BY hieu_luc_tu HAVING COUNT(*) > 1
    """, as_dict=True)
    for t in trung:
        ds = frappe.get_all(
            "SX Bang Don Gia", filters={"hieu_luc_tu": t.hieu_luc_tu},
            fields=["name"], order_by="creation desc")
        for i, b in enumerate(ds[1:], start=1):
            frappe.db.set_value(
                "SX Bang Don Gia", b.name, "hieu_luc_tu",
                frappe.utils.add_days(t.hieu_luc_tu, -i), update_modified=False)

    frappe.db.commit()
