"""Cờ dị ứng theo bộ tự công bố (W28) — đọc cho module QC.

Mã hàng gắn về "SX San Pham Cong Bo" qua Item.custom_sp_cong_bo; sản phẩm mang cờ
có lạc / có sữa bột / có dừa. QC dùng để biết vị bột nào bật ô thử lạc (B7) và ô
vệ sinh chuyển đổi sữa.

RANH GIỚI MODULE: chỉ đọc bằng frappe, không import gì từ phần còn lại của `sx`.
Site chưa có DocType / field (module qc cài riêng, hoặc chưa migrate) thì mọi cờ
là 0 — khi đó danh sách "Vị bột có lạc" trong SX QC Setting vẫn chạy như trước.
"""

import frappe
from frappe.utils import cint

KHONG = {"lac": 0, "sua": 0, "dua": 0}


def co_di_ung(items):
    """{item: {"lac", "sua", "dua"}} cho các mã đã gắn sản phẩm tự công bố."""
    items = [i for i in dict.fromkeys(items or []) if i]
    if not items:
        return {}
    try:
        gan = {r.name: r.custom_sp_cong_bo for r in frappe.get_all(
            "Item", filters={"name": ("in", items), "custom_sp_cong_bo": ("is", "set")},
            fields=["name", "custom_sp_cong_bo"]) if r.get("custom_sp_cong_bo")}
        if not gan:
            return {}
        sp = {r.name: r for r in frappe.get_all(
            "SX San Pham Cong Bo", filters={"name": ("in", list(set(gan.values())))},
            fields=["name", "co_lac", "co_sua_bot", "co_dua"])}
    except Exception:
        return {}
    ra = {}
    for i, ten in gan.items():
        s = sp.get(ten)
        if s:
            ra[i] = {"lac": cint(s.co_lac), "sua": cint(s.co_sua_bot), "dua": cint(s.co_dua)}
    return ra
