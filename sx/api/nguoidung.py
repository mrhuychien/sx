"""Tạo tài khoản portal cho QC bằng SỐ ĐIỆN THOẠI (D81).

Xưởng không có email. Bắt mỗi công nhân lập một hộp thư chỉ để đăng nhập là bắt một
việc không ai làm, nên tài khoản định danh bằng số điện thoại: số đó vừa là tên đăng
nhập, vừa là thứ họ vốn đã nhớ. Frappe bắt buộc User phải có email, nên email được
sinh ra từ chính số đó (`0912345678@<tên miền>`) — chỉ để cho đủ chỗ, không ai gửi
thư tới đó.

═══ MẬT KHẨU VÀ QR ĐĂNG NHẬP ═══
Thẻ in ra có ba thứ: số điện thoại (tên đăng nhập), mật khẩu, và một QR đăng nhập.
  · QR = đường vào NHANH cho lần đầu: quét là vào thẳng portal, không phải gõ gì.
  · Mật khẩu = đường vào LÂU DÀI, dùng mãi.
QR chỉ dùng ĐƯỢC MỘT LẦN và có hạn. Tờ giấy có QR đăng nhập là giấy tờ tuỳ thân: rơi
ra ngoài thì ai nhặt được cũng vào được. Một lần + có hạn giới hạn thiệt hại, và còn
để lại dấu — QC bảo "quét không vào" nghĩa là có người quét trước rồi.
Quét xong mà máy mất phiên thì QC đăng nhập bằng số điện thoại + mật khẩu, hoặc quản
lý cấp QR mới.

═══ CHỈ TẠO ĐƯỢC ROLE CỦA APP NÀY ═══
Danh sách role gán được bị đóng cứng trong ROLE_CHO_PHEP. Quản lý xưởng tạo được QC,
thủ kho, người ghi sổ — KHÔNG tạo được System Manager. Một màn "tạo user" mà gán được
role tuỳ ý là một cửa leo thang quyền, dù người bấm là ai.
"""

import hashlib
import re
import secrets

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_url, now_datetime

from sx.config.roles import GHI_SO, QUAN_LY, THU_KHO, VAO_HOP, guard_card

# Role gán được từ màn này. QUAN_LY có trong danh sách vì xưởng cần người thay ca,
# nhưng không có role nào của Frappe lõi — xem docstring.
ROLE_CHO_PHEP = {
    VAO_HOP: "QC vào hộp",
    GHI_SO: "Ghi sổ",
    THU_KHO: "Thủ kho",
    QUAN_LY: "Quản lý",
}

# Mã QR sống bao lâu. Đủ để in thẻ hôm nay, phát cho ca sau; không đủ để một tờ giấy
# rơi trong xưởng ba tháng vẫn còn mở được cửa.
SO_NGAY_MA = 14

# Bỏ 0 O o, 1 l I i: mật khẩu này người ta CHÉP TAY từ tờ giấy, đọc nhầm một ký tự
# là gọi điện hỏi lại quản lý.
#
# Viết THẲNG từng bảng chữ, không dựng bằng .upper()/.lower() từ một chuỗi chung:
# .lower() của "…KLM…" đẻ lại đúng chữ `l` vừa loại ra. Đã dính thật lúc viết hàm này,
# và bài test bắt được.
CHU_HOA = "ABCDEFGHJKLMNPQRSTUVWXYZ"      # không I, không O
CHU_THUONG = "abcdefghjkmnpqrstuvwxyz"    # không i, không l, không o
CHU_SO = "23456789"                       # không 0, không 1
KHO_KY_TU = CHU_HOA + CHU_THUONG + CHU_SO


def _ten_mien():
    """Tên miền ghép vào email giả. Lấy từ SX Settings nếu có khai."""
    from sx.utils import get_settings

    tm = (get_settings().get("ten_mien_user") or "").strip().lstrip("@")
    return tm or "sx.local"


def chuan_sdt(sdt):
    """Chuẩn hoá số điện thoại VN về dạng 0xxxxxxxxx, hoặc throw.

    Nhận cả '+84 912 345 678', '84912345678', '0912.345.678' — người ta lưu danh bạ
    mỗi người một kiểu, mà cùng một người thì phải ra cùng một tài khoản.
    """
    so = re.sub(r"[^0-9+]", "", str(sdt or ""))
    if so.startswith("+84"):
        so = "0" + so[3:]
    elif so.startswith("84") and len(so) >= 11:
        so = "0" + so[2:]
    so = so.lstrip("+")
    if not re.fullmatch(r"0\d{9,10}", so):
        frappe.throw(
            _("Số điện thoại '{0}' không hợp lệ. Cần 10 số bắt đầu bằng 0 "
              "(ví dụ 0912345678).").format(sdt)
        )
    return so


def mat_khau_moi(n=10):
    """Mật khẩu ngẫu nhiên ĐỌC ĐƯỢC: có đủ chữ hoa/thường/số, không có ký tự dễ nhìn
    nhầm, và không có ký tự đặc biệt (bàn phím điện thoại phải chuyển bảng mới gõ)."""
    rd = secrets.SystemRandom()
    # Ép có đủ ba loại rồi mới bốc phần còn lại: bốc ngẫu nhiên trơn thì thỉnh thoảng
    # ra mật khẩu toàn chữ thường, và chính sách mật khẩu của site có thể chặn.
    ds = [rd.choice(CHU_HOA), rd.choice(CHU_THUONG), rd.choice(CHU_SO)]
    ds += [rd.choice(KHO_KY_TU) for _ in range(max(0, n - len(ds)))]
    rd.shuffle(ds)
    return "".join(ds)


def _bam(ma):
    return hashlib.sha256(str(ma).encode("utf-8")).hexdigest()


def _kiem_quyen():
    """Chỉ quản lý xưởng. guard_card đã cho super roles đi qua."""
    guard_card("nguoidung")


def _email_cua(sdt):
    return f"{sdt}@{_ten_mien()}"


def _tim_user(sdt):
    """User của số điện thoại này, tìm cả theo username lẫn email giả."""
    return (
        frappe.db.get_value("User", {"username": sdt}, "name")
        or frappe.db.get_value("User", _email_cua(sdt), "name")
    )


# ─────────────────────────────────────────────── cấp mã đăng nhập ──


def _cap_ma(user):
    """Sinh mã một lần, lưu BĂM, trả link đầy đủ để nhét vào QR.

    Huỷ mọi mã cũ CHƯA DÙNG của người này: cấp thẻ mới mà thẻ cũ vẫn mở được cửa thì
    thu hồi thẻ cũ không còn nghĩa gì.
    """
    _xoa_ma(user, chi_chua_dung=True)
    ma = secrets.token_urlsafe(32)
    het = add_days(now_datetime(), SO_NGAY_MA)
    doc = frappe.get_doc({
        "doctype": "SX Ma Dang Nhap",
        "nguoi_dung": user,
        "ma_bam": _bam(ma),
        "het_han": het,
        "nguoi_tao": frappe.session.user,
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    return {"link": f"{get_url()}/vao?k={ma}", "het_han": str(het)}


def _xoa_ma(user, chi_chua_dung=False):
    """Xoá mã của một người. Xoá từng doc chứ không db.delete với bộ lọc 'is not set':
    dạng lọc đó chỉ chắc chắn chạy ở get_all."""
    loc = {"nguoi_dung": user}
    if chi_chua_dung:
        loc["da_dung_luc"] = ("is", "not set")
    for ten in frappe.get_all("SX Ma Dang Nhap", filters=loc, pluck="name"):
        frappe.delete_doc("SX Ma Dang Nhap", ten, force=True, ignore_permissions=True)


def doi_ma_lay_user(ma):
    """Đổi mã trong QR lấy user, và ĐÁNH DẤU ĐÃ DÙNG. Sai/hết hạn -> None.

    Trả về (user, ly_do): ly_do để trang /vao nói đúng chuyện gì đã xảy ra, vì "mã
    sai" và "mã đã có người quét" dẫn tới hai việc khác nhau.
    """
    if not ma:
        return None, "trong"
    ten = frappe.db.get_value("SX Ma Dang Nhap", {"ma_bam": _bam(ma)}, "name")
    if not ten:
        return None, "sai"
    doc = frappe.get_doc("SX Ma Dang Nhap", ten)
    if doc.da_dung_luc:
        return None, "da_dung"
    if doc.het_han and now_datetime() > doc.het_han:
        return None, "het_han"
    if not frappe.db.get_value("User", doc.nguoi_dung, "enabled"):
        return None, "khoa"
    doc.db_set("da_dung_luc", now_datetime(), update_modified=False)
    frappe.db.commit()
    return doc.nguoi_dung, ""


# ─────────────────────────────────────────────────────── API card ──


@frappe.whitelist()
def danh_sach():
    """Tài khoản portal đang có, kèm role SX và lần đăng nhập gần nhất."""
    _kiem_quyen()
    ds = frappe.get_all(
        "User",
        filters={"user_type": "System User", "name": ("not in", ["Administrator", "Guest"])},
        fields=["name", "full_name", "username", "mobile_no", "enabled", "last_login"],
        order_by="full_name asc",
        limit_page_length=0,
    )
    vai = {}
    for r in frappe.get_all(
        "Has Role", filters={"role": ("in", list(ROLE_CHO_PHEP))},
        fields=["parent", "role"], limit_page_length=0,
    ):
        vai.setdefault(r.parent, []).append(r.role)

    ra = []
    for u in ds:
        if u.name not in vai:
            continue        # tài khoản không thuộc app này -> không bày ra đây
        ra.append({
            "user": u.name,
            "ten": u.full_name or u.name,
            "sdt": u.username or u.mobile_no or "",
            "roles": sorted(vai[u.name]),
            "nhan_roles": ", ".join(ROLE_CHO_PHEP[r] for r in sorted(vai[u.name])),
            "bat": bool(cint(u.enabled)),
            "lan_cuoi": str(u.last_login) if u.last_login else None,
        })
    return {"rows": ra, "roles": [{"ma": k, "ten": v} for k, v in ROLE_CHO_PHEP.items()]}


@frappe.whitelist()
def tao_user(sdt, ho_ten=None, role=VAO_HOP):
    """Tạo tài khoản portal từ số điện thoại. Trả mật khẩu + link QR (một lần)."""
    _kiem_quyen()
    if role not in ROLE_CHO_PHEP:
        frappe.throw(_("Role '{0}' không cấp được từ màn này.").format(role))
    so = chuan_sdt(sdt)
    if _tim_user(so):
        frappe.throw(
            _("Số {0} đã có tài khoản. Muốn cấp lại mật khẩu thì bấm 'Cấp lại' ở dòng "
              "của người đó.").format(so)
        )

    ten = (ho_ten or "").strip() or so
    mk = mat_khau_moi()
    doc = frappe.get_doc({
        "doctype": "User",
        "email": _email_cua(so),
        "username": so,
        "mobile_no": so,
        "first_name": ten,
        "enabled": 1,
        # System User vì role SX đang chạy trên site là role của System User
        # (desk_access=0 nên vẫn không vào được Desk). Website User dùng bộ quyền
        # khác hẳn, đổi kiểu ở đây là QC đăng nhập được mà không ghi được gì.
        "user_type": "System User",
        "send_welcome_email": 0,
        "new_password": mk,
        "roles": [{"role": role}],
    })
    doc.flags.ignore_permissions = True
    doc.insert()

    ma = _cap_ma(doc.name)
    return {
        "user": doc.name, "sdt": so, "ten": ten, "role": role,
        "nhan_role": ROLE_CHO_PHEP[role], "mat_khau": mk, **ma,
    }


@frappe.whitelist()
def cap_lai(user, doi_mat_khau=1):
    """Cấp lại thẻ: QR mới, và mật khẩu mới nếu muốn.

    Mật khẩu cũ KHÔNG đọc lại được (Frappe lưu băm, đúng như phải thế), nên "in lại
    thẻ y hệt" là việc không làm được. Mất thẻ thì cấp mật khẩu mới.
    """
    _kiem_quyen()
    _kiem_user_cua_app(user)
    ra = {"user": user}
    if cint(doi_mat_khau):
        mk = mat_khau_moi()
        u = frappe.get_doc("User", user)
        u.new_password = mk
        u.flags.ignore_permissions = True
        u.save()
        ra["mat_khau"] = mk
    ra.update(_cap_ma(user))
    thong_tin = frappe.db.get_value(
        "User", user, ["full_name", "username", "mobile_no"], as_dict=True) or {}
    ra["ten"] = thong_tin.get("full_name") or user
    ra["sdt"] = thong_tin.get("username") or thong_tin.get("mobile_no") or ""
    return ra


@frappe.whitelist()
def bat_tat(user, bat):
    """Khoá / mở lại tài khoản. Khoá thì huỷ luôn mã QR chưa dùng."""
    _kiem_quyen()
    _kiem_user_cua_app(user)
    if user == frappe.session.user:
        frappe.throw(_("Không tự khoá tài khoản của chính mình."))
    bat = cint(bat)
    frappe.db.set_value("User", user, "enabled", bat)
    if not bat:
        _xoa_ma(user)
    return {"user": user, "bat": bool(bat)}


def _kiem_user_cua_app(user):
    """Chỉ đụng được tài khoản CÓ role của app này.

    Không có bước này thì màn 'tạo user cho QC' đổi được mật khẩu của Administrator.
    """
    if not frappe.db.exists("User", user):
        frappe.throw(_("Không có tài khoản {0}.").format(user))
    co = frappe.get_all(
        "Has Role", filters={"parent": user, "role": ("in", list(ROLE_CHO_PHEP))},
        limit=1)
    if not co:
        frappe.throw(
            _("Tài khoản {0} không thuộc app sản xuất — không sửa được từ màn này.")
            .format(user)
        )
    if "System Manager" in frappe.get_roles(user) and user != frappe.session.user:
        frappe.throw(
            _("Tài khoản {0} có quyền System Manager. Sửa nó phải làm trong Desk, "
              "không làm từ màn này.").format(user)
        )


@frappe.whitelist()
def goi_y_ten(sdt):
    """Gợi ý họ tên từ danh sách Employee theo số điện thoại — khỏi gõ lại."""
    _kiem_quyen()
    so = chuan_sdt(sdt)
    # So 9 số cuối: danh bạ mỗi nơi lưu một kiểu (+84 / 0 / có dấu chấm), phần đuôi
    # mới là thứ chắc chắn giống nhau.
    duoi = so[-9:]
    if not frappe.get_meta("Employee").has_field("cell_number"):
        return {"ten": None}
    e = frappe.get_all(
        "Employee", filters={"cell_number": ("like", f"%{duoi}")},
        fields=["name", "employee_name"], limit=1)
    return {"ten": e[0].employee_name, "employee": e[0].name} if e else {"ten": None}


