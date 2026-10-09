"""www page controller portal /sx (v3) — bơm SX_CONTEXT (views/cards theo role)."""

import json

import frappe

from sx.config.roles import (
    ROLE_VIEWS,
    allowed_views,
    is_super,
    landing_view,
    vai_tro_hien,
    view_cards,
)

# Build marker chống "shell cũ" (LUẬT VÀNG #2 — frappe-portal-spa)
SHELL_BUILD = "sx-113"

# Lấy từ ROLE_VIEWS: thêm role mới ở một chỗ, trang /sx cho vào ngay. Chép tay
# danh sách này là cách tạo ra người dùng có role, có tab, mà mở /sx thì bị đá ra.
ALLOWED_ROLES = set(ROLE_VIEWS) | {"System Manager", "Administrator"}


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
            # Cho menu tài khoản trên header (D96): ai đang cầm máy, vai trò gì.
            # Một điện thoại hay bị chuyền tay giữa hai QC — phải nhìn là biết
            # đang đăng nhập bằng tài khoản ai trước khi ghi số.
            "fullName": frappe.utils.get_fullname(frappe.session.user),
            "vaiTro": vai_tro_hien(roles),
            "deskAccess": frappe.db.get_value(
                "User", frappe.session.user, "user_type") == "System User",
            "isQuanLy": is_super(roles),
            "views": allowed_views(roles),
            "viewCards": view_cards(roles),
            "landing": landing_view(roles),
            "assetVersion": asset_version,
            "build": SHELL_BUILD,
            "csrfToken": frappe.sessions.get_csrf_token(),
        }
    )
    context.sx_boot = _boot_nhung()
    return context


def _boot_nhung():
    """Boot của HÔM NAY nhúng thẳng vào HTML (D120).

    Trước đây trình duyệt phải tải xong HTML → shell.js + các module → MỚI gọi
    get_boot → chờ server lần nữa → mới vẽ được gì. Nhúng sẵn là bỏ hẳn một vòng
    hỏi-đáp, và vòng đó bắt đầu muộn (sau khi tải module). Hỏng thì trả "null":
    shell tự gọi get_boot như cũ, trang không được chết vì phần tăng tốc này.
    """
    try:
        from sx.api.portal import VIEW_PHAN, get_boot

        # D121: chỉ kèm danh mục của màn MỞ ĐẦU — màn khác tự tải khi được mở.
        man = landing_view(set(frappe.get_roles()))
        boot = get_boot(phan=VIEW_PHAN.get(man, []))
        # </script> trong chuỗi dữ liệu sẽ đóng thẻ script sớm — thoát "</".
        return frappe.as_json(boot, indent=None).replace("</", "<\\/")
    except Exception:
        frappe.log_error(title="sx: nhúng boot vào /sx hỏng", message=frappe.get_traceback())
        return "null"
