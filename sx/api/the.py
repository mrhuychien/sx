"""Danh sách mã quét của công nhân — để in thẻ QR (D63).

Chỉ trả DỮ LIỆU. Mã QR vẽ ngay trên máy bằng `vendor/qrcode.js`, vì hai lý do:
site không chắc có thư viện QR của Python, và in được cả khi mất mạng.

Mã dùng `employee_number` nếu có, không thì Employee ID — cái nào cũng là thứ người
ta vốn đã có, khỏi phát sinh mã thứ hai cho cùng một người. QR không kén ký tự như
mã vạch một chiều nên tên mã kiểu gì cũng mã hoá được.
"""

import frappe

from sx.config.roles import guard_card


@frappe.whitelist()
def danh_sach_the():
    """[{ten, ma}] cho toàn bộ công nhân công khoán, sắp theo tên."""
    guard_card("vaohop")
    from sx.api.portal import _nhan_vien_vao_hop

    ds, _cb = _nhan_vien_vao_hop()
    return [
        {
            "ten": e.get("employee_name") or e["name"],
            "ma": str(e.get("employee_number") or e["name"]).strip(),
        }
        for e in ds
    ]
