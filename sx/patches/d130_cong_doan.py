"""D130 (W04): danh mục công đoạn thành DocType "SX QC Cong Doan".

Tạo từ bảng gốc muc.CONG_DOAN_GOC (24 công đoạn: bánh 16, PRP, bột 7) — tên y như
ô Select cũ của phiếu sự cố, nên mọi phiếu cũ vẫn trỏ đúng sau khi ô đó thành Link.
Giá trị lạ đang nằm trên phiếu cũ (gõ tay trên Desk…) cũng được tạo, dây chuyền
"Chung", không mã — để không phiếu nào trỏ vào hư không.

Patch CHÉP bảng gốc chứ không import muc.py: patch là ảnh chụp tại D130.
Chạy lại vô hại: công đoạn có rồi (theo mã, hoặc theo tên) thì bỏ qua.
"""

import frappe

GOC = [
    ("1", "1 Tiếp nhận, ngâm đỗ", "Bánh", 1),
    ("2", "2 Luộc", "Bánh", 2),
    ("3", "3 Rang", "Bánh", 3),
    ("4", "4 Sàng cát", "Bánh", 4),
    ("5", "5 Ủ", "Bánh", 5),
    ("6", "6 Vỡ đỗ, nam châm", "Bánh", 6),
    ("7", "7 Nghiền", "Bánh", 7),
    ("8", "8 Kho bột", "Bánh", 8),
    ("9", "9 Trộn", "Bánh", 9),
    ("10", "10 Ủ sau trộn", "Bánh", 10),
    ("11", "11 Ép khuôn", "Bánh", 11),
    ("12", "12 Cân, khối lượng tịnh", "Bánh", 12),
    ("13", "13 Hàn túi", "Bánh", 13),
    ("14", "14 Nhãn, HSD", "Bánh", 14),
    ("15", "15 Đóng thùng", "Bánh", 15),
    ("16", "16 Lưu kho thành phẩm", "Bánh", 16),
    ("PRP", "PRP", "Chung", 0),
    ("bot-tiep-nhan", "Bột: tiếp nhận", "Bột", 1),
    ("bot-nhat-lac", "Bột: nhặt lạc", "Bột", 2),
    ("bot-rang-lac", "Bột: rang lạc", "Bột", 3),
    ("bot-xay-duong", "Bột: xay đường", "Bột", 4),
    ("bot-tron", "Bột: trộn", "Bột", 5),
    ("bot-dong-tui", "Bột: đóng túi", "Bột", 6),
    ("bot-dong-thung", "Bột: đóng thùng", "Bột", 7),
]


def _tao(ten, day_chuyen, thu_tu, ma=None):
    frappe.get_doc({"doctype": "SX QC Cong Doan", "ten": ten, "day_chuyen": day_chuyen,
                    "thu_tu": thu_tu, "ma": ma}).insert(ignore_permissions=True)


def execute():
    if not frappe.db.table_exists("SX QC Cong Doan"):
        return
    for ma, ten, dc, tt in GOC:
        if frappe.db.exists("SX QC Cong Doan", {"ma": ma}) or frappe.db.exists("SX QC Cong Doan", ten):
            continue
        _tao(ten, dc, tt, ma)
    if not frappe.db.table_exists("SX Su Co"):
        return
    for ten in frappe.db.sql_list(
            "select distinct cong_doan from `tabSX Su Co` where ifnull(cong_doan, '') != ''"):
        if not frappe.db.exists("SX QC Cong Doan", ten):
            _tao(ten, "Chung", 99)
