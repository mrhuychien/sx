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
# D56: thủ kho là NGƯỜI THỨ HAI đếm lại hàng trước khi vào kho. Tách role riêng vì
# cả giá trị của bước này nằm ở chỗ người duyệt KHÁC người lập.
THU_KHO = "SX Thu Kho"

# ── Module QC (BM.08.01/02) ────────────────────────────────────────────────
# Bốn vai mới, tách khỏi "SX Vao Hop" (đang gọi là QC vào hộp): người đi kiểm
# chế biến không phải người chấm hộp. Frappe cộng dồn role nên ai kiêm cả hai
# thì gán cả hai — không chỗ nào trong code giả định "mỗi người đúng một role".
# Tên role khai LẦN NỮA trong sx/api/qc.py (module qc không import file này, để
# tách ra app riêng được). scripts/test-qc.py chốt hai bên khớp nhau.
QC = "SX QC"                      # QC chế biến — đi 3 lượt/ca
QC_GOI = "SX QC Packing"          # QC đóng gói — ghi mục 11–13, B4–B6
ISO = "ISO Manager"               # Trưởng Ban ISO — đóng sự cố, xem xét
QLSX = "Production Manager"       # QLSX — đọc, ghi xử lý sự cố
KHO_NL = "Warehouse"              # thủ kho nguyên liệu — BM.07.03 (P1)

# Role "siêu quyền" — thấy mọi view/card
SUPER_ROLES = {QUAN_LY, "System Manager", "Administrator"}

# view nào role nào được vào
ROLE_VIEWS = {
    GHI_SO: ["ghiso"],
    VAO_HOP: ["vaohop", "nhapkho"],
    THU_KHO: ["nhapkho"],
    QUAN_LY: ["ghiso", "vaohop", "nhapkho", "qc", "quanly"],
    QC: ["qc"],
    QC_GOI: ["qc"],
    ISO: ["qc"],
    QLSX: ["qc"],
}

MOI_VIEW = ["ghiso", "vaohop", "nhapkho", "qc", "quanly"]

# view lắp từ những card nào (thứ tự hiển thị).
# D33: hai màn NHẬP LIỆU chỉ giữ việc phải gõ. Chốt ngày (hành động chốt sổ) và lưu đồ
# tồn BTP (màn hình theo dõi) chuyển hẳn sang Quản lý — quanly giờ vừa dashboard vừa
# lắp card, không còn là view standalone.
VIEW_CARDS = {
    "ghiso": ["luutrinh", "baome", "baocan", "suco"],
    # D83: màn Ghi hộp của QC chỉ còn đúng việc chấm hộp. Báo sự cố về tổ Ghi sổ.
    "vaohop": ["vaohop"],
    "nhapkho": ["nhapkhotp"],
    # Màn QC là view standalone: nó tự dựng cả 5 màn con (#/qc, /round/:name,
    # /incidents, /history, /review) và tự chốt quyền trong sx/api/qc.py.
    "qc": [],
    # qcnhac đứng ĐẦU: việc QC đang treo phải đập vào mắt trước cả nút chốt ngày.
    "quanly": ["qcnhac", "chotngay", "luutrinhbtp", "nguoidung"],
}

# card nào role nào được GỌI API (chốt bảo mật thật — không phải ẩn tab)
CARD_ROLES = {
    "xuatdau": [GHI_SO],
    "luutrinh": [GHI_SO],   # lưu đồ tầng 1 (D31) — thay card xuất đậu cũ
    "luutrinhbtp": [QUAN_LY],   # lưu đồ tồn BTP tầng 2/3 (D32) — chỉ đọc, màn Quản lý
    "baome": [GHI_SO],
    "baocan": [GHI_SO],
    "suco": [GHI_SO],
    "vaohop": [VAO_HOP],
    # D33: chốt ngày về tay QUẢN LÝ. QC#2 chỉ nhập bảng vào hộp; ai chốt sổ là người
    # khác — vừa gọn màn nhập liệu, vừa tách vai đúng §2.1 (người nhập ≠ người chốt).
    # Lập phiếu nháp: người ở xưởng. DUYỆT: chỉ THU_KHO/QUAN_LY — chốt trong
    # khotp._duoc_duyet(), không phải ở đây (card này cả hai bên đều mở được).
    "nhapkhotp": [VAO_HOP, THU_KHO, QUAN_LY],
    "chotngay": [QUAN_LY],
    # Tạo tài khoản là cấp quyền cho người khác — chỉ quản lý, và danh sách role gán
    # được bị đóng cứng trong sx/api/nguoidung.py.
    "nguoidung": [QUAN_LY],
    # Hộp nhắc việc QC trên dashboard quản lý. Không chứa gì bí mật — nó chỉ
    # đếm lại những thứ chính người đó có quyền xem.
    "qcnhac": [QUAN_LY],
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
        return list(MOI_VIEW)
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
