"""Nguồn cấu hình chung role → view → card (spec §6.1, §6.2).

Chuyển giao tương lai (đưa card về đúng tổ sản xuất) = sửa DUY NHẤT file này:
thêm role, map lại card. UI đọc views/viewCards từ context; API guard đọc CARD_ROLES.
Không sửa JS, không sửa từng method.
"""

import frappe
from frappe import _

QUAN_LY = "SX Quan Ly"
GHI_SO = "SX Ghi So"
VAO_HOP = "SX Vao Hop"

# Role "siêu quyền" — thấy mọi view/card
SUPER_ROLES = {QUAN_LY, "System Manager", "Administrator"}

# view nào role nào được vào
ROLE_VIEWS = {
    GHI_SO: ["ghiso"],
    VAO_HOP: ["vaohop"],
    QUAN_LY: ["ghiso", "vaohop", "quanly"],
}

# view lắp từ những card nào (thứ tự hiển thị)
VIEW_CARDS = {
    "ghiso": ["xuatdau", "nhapbot", "baome", "baocan", "suco"],
    "vaohop": ["vaohop", "suco", "chotngay"],
    "quanly": ["quanly"],
}

# card nào role nào được GỌI API (chốt bảo mật thật — không phải ẩn tab)
CARD_ROLES = {
    "xuatdau": [GHI_SO],
    "nhapbot": [GHI_SO],
    "baome": [GHI_SO],
    "baocan": [GHI_SO],
    "suco": [GHI_SO, VAO_HOP],
    "vaohop": [VAO_HOP],
    "chotngay": [VAO_HOP],
    "quanly": [],  # chỉ super roles
}


def user_roles():
    return set(frappe.get_roles())


def is_super(roles=None):
    return bool((roles or user_roles()) & SUPER_ROLES)


def allowed_views(roles=None):
    """Danh sách view user được vào (super = tất cả), giữ thứ tự ổn định."""
    roles = roles or user_roles()
    if is_super(roles):
        return ["ghiso", "vaohop", "quanly"]
    out = []
    for r in roles:
        for v in ROLE_VIEWS.get(r, []):
            if v not in out:
                out.append(v)
    return out


def view_cards(roles=None):
    """{view: [card...]} user được thấy = VIEW_CARDS lọc theo card user được phép."""
    roles = roles or user_roles()
    super_ = is_super(roles)
    out = {}
    for v in allowed_views(roles):
        cards = []
        for c in VIEW_CARDS.get(v, []):
            if super_ or roles & set(CARD_ROLES.get(c, [])):
                cards.append(c)
        out[v] = cards
    return out


def landing_view(roles=None):
    roles = roles or user_roles()
    if is_super(roles):
        return "quanly"
    views = allowed_views(roles)
    return views[0] if views else None


def guard_card(card):
    """Chặn nếu user không được gọi API của card này (super roles luôn qua)."""
    roles = user_roles()
    if is_super(roles):
        return
    if not (roles & set(CARD_ROLES.get(card, []))):
        frappe.throw(
            _("Bạn không có quyền thao tác '{0}'.").format(card), frappe.PermissionError
        )
