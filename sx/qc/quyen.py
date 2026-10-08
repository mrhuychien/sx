"""Ai được làm những việc DUYỆT của module QC (W11, D134).

Một chỗ cho cả controller (đường Desk) lẫn sx/api/qc.py (đường màn QC): luật quyền
viết hai nơi thì sớm muộn lệch nhau, và chỗ lệch luôn là cửa hậu.

Đóng / mở lại phiếu sự cố, đổi cờ diễn tập: Trưởng Ban ISO (role ISO Manager), quản
trị (SX Quan Ly / System Manager), hoặc người được giao trong SX QC Setting.
Người GHI phiếu không tự đóng phiếu của mình — đó là cả lý do có bước đóng.
"""

import frappe

from sx.qc.nguong import nguong

ISO = "ISO Manager"
SIEU = {"SX Quan Ly", "System Manager", "Administrator"}


def _vai(user=None):
    return set(frappe.get_roles(user) if user else frappe.get_roles())


def duoc_dong_su_co(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    vai = _vai(user)
    if vai & SIEU or ISO in vai:
        return True
    return user in (nguong().get("nguoi_dong_su_co") or [])


def duoc_duyet_xuat_xuong(user=None):
    """Duyệt phiếu kiểm tra xuất xưởng BM.08.04 (W08): Trưởng Ban ISO hoặc người được giao.
    KHÔNG gồm quản trị SX Quan Ly mặc định — tài liệu ghi đúng hai người; muốn thêm ai
    thì giao ở SX QC Setting. Điều kiện "không phải QC đã kiểm lô" xét ở controller."""
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    if ISO in _vai(user):
        return True
    return user in (nguong().get("nguoi_duyet_xuat_xuong") or [])
