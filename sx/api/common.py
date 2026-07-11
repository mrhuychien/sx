"""Guard quyền dùng chung cho mọi whitelisted method của app sx.

Method-mediated permission (spec muc 3): To Truong / Tram Rang KHÔNG có DocPerm
trên Employee/Work Order/Stock Entry/Batch — mọi truy cập đi qua whitelisted
method: guard role xong mới thao tác bằng ignore_permissions, và chỉ trả về
field trong whitelist.
"""

import frappe
from frappe import _

QUAN_LY = "SX Quan Ly"
TO_TRUONG = "SX To Truong"
TRAM_RANG = "SX Tram Rang"


def _guard(roles):
    """Chặn nếu user hiện tại không có role nào trong danh sách (System Manager luôn qua)."""
    user_roles = set(frappe.get_roles())
    allowed = set(roles) | {"System Manager"}
    if user_roles.isdisjoint(allowed):
        frappe.throw(
            _("Bạn không có quyền thực hiện thao tác này (cần role: {0}).").format(
                ", ".join(roles)
            ),
            frappe.PermissionError,
        )
