"""Trang /vao — đổi mã QR trên thẻ lấy một phiên đăng nhập rồi vào thẳng portal (D81).

Đường đi: QC quét QR trên thẻ -> trình duyệt mở /vao?k=<mã> -> trang này đổi mã lấy
user, mở phiên, chuyển tiếp sang /sx. QC không gõ gì.

Mã dùng MỘT LẦN. Sai/hết hạn/đã dùng thì KHÔNG chuyển tiếp mà hiện đúng lý do, kèm
đường vào bằng số điện thoại + mật khẩu — người đứng giữa xưởng cần biết phải làm gì
tiếp, không phải một chữ "lỗi".
"""

import frappe

from sx.api.nguoidung import doi_ma_lay_user

no_cache = 1

LY_DO = {
    "trong": "Đường dẫn thiếu mã. Quét lại QR trên thẻ.",
    "sai": "Mã này không đúng. Có thể thẻ đã cũ, hoặc quét nhầm mã khác.",
    "da_dung": "Mã đã được dùng rồi. Mã đăng nhập chỉ dùng được MỘT LẦN — "
               "nếu bạn chưa từng quét thẻ này thì báo quản lý cấp thẻ mới.",
    "het_han": "Mã đã hết hạn. Nhờ quản lý cấp thẻ mới.",
    "khoa": "Tài khoản đang bị khoá. Liên hệ quản lý.",
}


def get_context(context):
    context.no_cache = 1
    ma = (frappe.form_dict.get("k") or "").strip()

    # Đang đăng nhập sẵn thì khỏi đốt mã — vào thẳng, và mã vẫn còn cho lần sau.
    if frappe.session.user and frappe.session.user != "Guest":
        _di_toi_portal()

    user, ly_do = doi_ma_lay_user(ma)
    if not user:
        context.loi = LY_DO.get(ly_do, LY_DO["sai"])
        return context

    _mo_phien(user)
    _di_toi_portal()
    return context


def _mo_phien(user):
    """Mở phiên cho `user` bằng LoginManager của chính request này.

    Không tự dựng LoginManager mới: bản dựng trong request đã gắn với cookie/session
    của request đó. Frappe đổi tên hàm giữa các phiên bản nên thử `login_as` trước,
    rồi mới tới cách đặt user + post_login.
    """
    lm = getattr(frappe.local, "login_manager", None)
    if lm is None:
        frappe.throw(frappe._("Không mở được phiên đăng nhập trên site này."))
    if hasattr(lm, "login_as"):
        lm.login_as(user)
    else:
        lm.user = user
        lm.post_login()


def _di_toi_portal():
    frappe.local.flags.redirect_location = "/sx"
    raise frappe.Redirect
