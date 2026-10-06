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

# Role của app và quyền vào Desk MẶC ĐỊNH khi tạo mới (D105).
#
# Trước D105 các role này nằm trong fixtures/role.json. Frappe nạp fixtures ở MỌI
# lần `bench migrate` bằng cách XOÁ rồi TẠO LẠI từng role (frappe/modules/
# import_file.py: delete_old_doc → insert). Role tạo lại thì Frappe coi như
# desk_access "vừa đổi" và tính lại kiểu tài khoản (System / Website User) của mọi
# người giữ role đó; người nào bị đổi kiểu là Frappe XOÁ HẾT PHIÊN của người đó
# (frappe/core/doctype/user/user.py: user_type đổi → clear_sessions). Thêm nữa,
# ai bật Desk cho một role SX trên site thì mỗi lần migrate bị fixtures đè về 0.
#
# Giờ: sx.setup.dam_bao_role chạy sau install / migrate và CHỈ TẠO role còn thiếu.
# Role đã có thì không đụng — chỉnh trên site là giữ nguyên.
# (tên role, desk_access khi tạo mới)
VAI_MAC_DINH = {
    "SX Ghi So": 0,
    "SX Vao Hop": 0,
    "SX Thu Kho": 0,
    "SX Quan Ly": 1,
    "SX QC": 0,
    "SX QC Packing": 0,
    "ISO Manager": 1,
    "Production Manager": 1,   # role chuẩn của ERPNext — thường đã có sẵn
    "Warehouse": 1,
}

# Role "siêu quyền" — thấy mọi view/card
SUPER_ROLES = {QUAN_LY, "System Manager", "Administrator"}

# Tên vai trò hiện cho NGƯỜI ĐỌC (menu tài khoản trên header). Tên role của
# Frappe là tiếng Anh / viết tắt không dấu — QC đứng giữa xưởng không cần biết
# "SX Vao Hop" là gì, họ cần đọc thấy "QC vào hộp".
NHAN_ROLE = {
    QUAN_LY: "Quản lý",
    GHI_SO: "Ghi sổ",
    VAO_HOP: "QC vào hộp",
    THU_KHO: "Thủ kho",
    QC: "QC chế biến",
    QC_GOI: "QC đóng gói",
    ISO: "Trưởng Ban ISO",
    QLSX: "Quản lý sản xuất",
    KHO_NL: "Thủ kho nguyên liệu",
    "System Manager": "Quản trị hệ thống",
}


def vai_tro_hien(roles=None):
    """Danh sách tên vai trò (tiếng Việt) của user — chỉ role của app này.

    Không liệt kê mọi role Frappe (Guest, All, Employee…): đọc một danh sách mười
    dòng thì không ai tìm được dòng nói mình làm gì.
    """
    roles = roles or user_roles()
    return [ten for r, ten in NHAN_ROLE.items() if r in roles]


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
    # lich*: lịch tháng đứng CUỐI mỗi tab nhập liệu, gập sẵn (D108).
    "ghiso": ["luutrinh", "baome", "baocan", "suco", "lichghiso"],
    # D83: màn Ghi hộp của QC chỉ còn đúng việc chấm hộp. Báo sự cố về tổ Ghi sổ.
    # novaohop (D101): kho nhận vượt số chấm — QC là người phải chấm bù.
    "vaohop": ["vaohop", "novaohop", "lichvaohop"],
    # nobom: sổ nợ BOM (D97) — thành phẩm nhập lúc chưa có định mức. Đặt ngay
    # dưới phiếu nhập để thủ kho thấy phần mình vừa nhập tạm đang nằm đâu.
    "nhapkho": ["nhapkhotp", "nobom", "lichnhapkho"],
    # Màn QC là view standalone: nó tự dựng cả 5 màn con (#/qc, /round/:name,
    # /incidents, /history, /review) và tự chốt quyền trong sx/api/qc.py.
    "qc": [],
    # qcnhac đứng ĐẦU: việc QC đang treo phải đập vào mắt trước cả nút chốt ngày.
    # nogia (D99): sổ nợ đơn giá vào hộp — lương khoán đang 0 đồng chờ khai giá.
    # phieuluong (D110): xem nhanh phiếu lương tháng — gập sẵn, sau thẻ chốt ngày.
    # truyxuat (D115): truy xuất nguồn gốc 2 chiều — thay ô "nhập mã batch" cũ.
    # lichchot (D117): chốt ngày bằng lịch tháng — bấm ngày, xem nhanh, chốt luôn.
    # Thay thẻ chotngay (vẫn giữ file: lịch dùng lại phần nút chốt của nó).
    "quanly": ["qcnhac", "nobom", "nogia", "novaohop", "lichchot", "truyxuat",
               "phieuluong", "luutrinhbtp", "nguoidung"],
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
    # Sổ nợ BOM: thủ kho XEM (phần mình nhập tạm), quản lý XỬ LÝ. Quyền xử lý chốt
    # riêng trong khotp._duoc_xu_ly_no — card mở cho cả hai, nút thì không.
    "nobom": [THU_KHO, QUAN_LY],
    # Sổ nợ đơn giá (D99): áp giá là SỬA LƯƠNG của người khác — chỉ quản lý.
    "nogia": [QUAN_LY],
    # Sổ nợ vào hộp (D101): QC vào hộp XEM (để chấm bù), quản lý thêm quyền BỎ QUA
    # — chốt riêng trong khotp._duoc_bo_qua_no_vh.
    "novaohop": [VAO_HOP, QUAN_LY],
    # Lịch tháng (D108): ai vào được tab nào thì xem được lịch tab đó. Chỉ đọc.
    # Phiếu lương (D110): lương của người khác — chỉ quản lý.
    "phieuluong": [QUAN_LY],
    # Truy xuất (D115): đọc xuyên mọi chứng từ (mua, sản xuất, bán, lương người
    # vào hộp) — chỉ quản lý.
    "truyxuat": [QUAN_LY],
    "lichvaohop": [VAO_HOP],
    "lichghiso": [GHI_SO],
    "lichnhapkho": [VAO_HOP, THU_KHO, QUAN_LY],
    "lichchot": [QUAN_LY],
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
