"""D95: QC một ngày ba lượt — đổi tên lượt trên phiếu đã có.

Trước D95: 3 lượt × 2 ca (Đầu ca / Giữa ca / Cuối ca, ca Sáng / Chiều).
Từ D95:    3 lượt trong ngày (Đầu sáng / Trưa / Cuối chiều), không chia ca.

Đổi GIÁ TRỊ LƯU chứ không chỉ đổi nhãn trên màn hình: để "Giữa ca" nằm trong
dữ liệu mà màn hình ghi "Trưa" thì CSV, tờ in, bộ lọc trên Desk mỗi chỗ nói một
kiểu, và người đọc sau này không biết hai chữ đó là một.

KHÔNG đụng vào:
  · trường `ca` của phiếu cũ — giữ nguyên để còn biết phiếu đó ghi ở ca nào;
  · số lượt trên một ngày cũ — ngày cũ có thể có hai phiếu "Đầu sáng" (ca Sáng
    + ca Chiều). Đó là hồ sơ đã chốt; gộp hay xoá bớt là sửa hồ sơ.

Không qua ORM (không save từng phiếu) vì phiếu đã submit thì save bị chặn, và vì
đây không phải một lần SỬA NỘI DUNG phiếu mà là đổi tên một danh mục. Chạy lại
bao nhiêu lần cũng vậy: tên cũ hết thì không còn gì để đổi.
"""

import frappe

DOI_TEN = {"Đầu ca": "Đầu sáng", "Giữa ca": "Trưa", "Cuối ca": "Cuối chiều"}


def execute():
    if not frappe.db.table_exists("SX QC Round"):
        return
    tong = 0
    for cu, moi in DOI_TEN.items():
        n = frappe.db.count("SX QC Round", {"luot": cu})
        if n:
            frappe.db.set_value("SX QC Round", {"luot": cu}, "luot", moi,
                                update_modified=False)
            tong += n
            print(f"D95: {n} phiếu lượt '{cu}' → '{moi}'")
    frappe.db.commit()
    print(f"D95: đổi tên lượt xong ({tong} phiếu)")
