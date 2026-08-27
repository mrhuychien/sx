"""www page controller portal /sx (v3) — bơm SX_CONTEXT (views/cards theo role)."""

import json

import frappe

from sx.config.roles import allowed_views, is_super, landing_view, view_cards

# Build marker chống "shell cũ" (LUẬT VÀNG #2 — frappe-portal-spa)
SHELL_BUILD = "sx-60"

ALLOWED_ROLES = {"SX Ghi So", "SX Vao Hop", "SX Thu Kho", "SX Quan Ly",
                 "System Manager", "Administrator"}


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/sx"
        raise frappe.Redirect

    roles = set(frappe.get_roles())
    if roles.isdisjoint(ALLOWED_ROLES):
        frappe.throw(
            frappe._("Bạn không có quyền vào portal sản xuất."), frappe.PermissionError
        )

    context.no_cache = 1
    # Cache-bust token = SHELL_BUILD (đổi theo DEPLOY, không phải mỗi request).
    # no_cache=1 giữ HTML /sx luôn render tươi → bump SHELL_BUILD lúc deploy là bust
    # ngay (never-stale, LUẬT VÀNG #1) NHƯNG cho phép browser cache ~15 module JS +
    # CSS giữa các lần reload trong cùng 1 build (khác với now() re-mint mỗi request).
    asset_version = SHELL_BUILD
    context.asset_version = asset_version
    context.shell_build = SHELL_BUILD
    context.sx_context = json.dumps(
        {
            "user": frappe.session.user,
            "isQuanLy": is_super(roles),
            "views": allowed_views(roles),
            "viewCards": view_cards(roles),
            "landing": landing_view(roles),
            "assetVersion": asset_version,
            "build": SHELL_BUILD,
            "csrfToken": frappe.sessions.get_csrf_token(),
        }
    )
    return context
