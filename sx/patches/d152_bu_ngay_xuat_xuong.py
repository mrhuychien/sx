"""D152: chạy bù D137 — đặt "Áp dụng BM.08.04 từ ngày" = ngày cập nhật nếu còn trống.

D137 bản đầu kiểm `table_exists("SX Settings")`, mà SX Settings là doctype Single (không có bảng riêng) nên
patch không làm gì: ngày áp dụng trống → mọi lô thành phẩm tồn từ trước W08 bị chặn bán. Site đã chạy D137 thì
Frappe không chạy lại nó — patch này làm lại đúng việc đó. Đã khai ngày thì để nguyên. Chạy lại vô hại.
"""

from sx.patches.d137_xuat_xuong import execute as d137


def execute():
    d137()
