"""Guard quyền dùng chung cho whitelisted method app sx (v2).

Method-mediated permission (spec §4): 3 tổ KHÔNG có DocPerm trên
Employee/Work Order/Stock Entry/Batch/SalaryProduct — mọi truy cập qua
whitelisted method: guard role -> thao tác ignore_permissions -> chỉ trả
field trong whitelist.
"""

import frappe
from frappe import _

QUAN_LY = "SX Quan Ly"
THU_KHO = "SX Thu Kho"
TO_TRON = "SX To Tron"
TO_DONG_GOI = "SX To Dong Goi"

ALL_SX_ROLES = (THU_KHO, TO_TRON, TO_DONG_GOI, QUAN_LY)


def _guard(roles):
    """Chặn nếu user không có role nào trong danh sách (System Manager luôn qua)."""
    user_roles = set(frappe.get_roles())
    allowed = set(roles) | {"System Manager"}
    if user_roles.isdisjoint(allowed):
        frappe.throw(
            _("Bạn không có quyền thực hiện thao tác này (cần role: {0}).").format(
                ", ".join(roles)
            ),
            frappe.PermissionError,
        )
