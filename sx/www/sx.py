"""www page controller cho portal /sx — bơm SX_CONTEXT server-side."""

import json

import frappe

# Build marker chống "shell cũ" (LUẬT VÀNG #2 — frappe-portal-spa)
SHELL_BUILD = "sx-1"

ALLOWED_ROLES = {"SX To Truong", "SX Tram Rang", "SX Quan Ly", "System Manager"}


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
    # assetVersion: cache-bust view động (withV) — an toàn URL/JSON
    asset_version = frappe.utils.now().replace(" ", "T").replace(":", "-")
    context.asset_version = asset_version
    context.shell_build = SHELL_BUILD
    context.sx_context = json.dumps(
        {
            "user": frappe.session.user,
            "isQuanLy": bool(roles & {"SX Quan Ly", "System Manager"}),
            "isToTruong": bool(roles & {"SX To Truong", "SX Quan Ly", "System Manager"}),
            "isTramRang": "SX Tram Rang" in roles,
            "assetVersion": asset_version,
            "build": SHELL_BUILD,
            "csrfToken": frappe.sessions.get_csrf_token(),
        }
    )
    return context
