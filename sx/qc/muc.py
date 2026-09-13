"""Danh mục mục kiểm BM.08.01 — NGUỒN DUY NHẤT cho DocType, API và màn hình.

Vì sao phải gom một chỗ: cùng một mục "Rang: nhiệt độ" xuất hiện ở BỐN nơi —
field trong DocType JSON, ma trận áp dụng gửi cho máy QC, luật sinh sự cố lúc
submit, và tờ A4 in cho auditor. Khai bốn lần thì sớm muộn bốn bản lệch nhau, mà
kiểu lệch tệ nhất là im lặng: mục biến mất khỏi màn hình nên không ai ghi, tờ in
vẫn có ô trống, không lỗi nào hiện ra.

Đổi bộ mục kiểm (bản giấy sửa đổi) = sửa DUY NHẤT file này + thêm field vào
sx_qc_round.json. scripts/test-qc.py chốt hai bên khớp nhau.

RANH GIỚI MODULE: file này KHÔNG import gì từ `sx` ngoài thư viện chuẩn — cả
module qc phải bê nguyên sang app khác được (xem sx/qc/README.md).
"""

# ── Lượt ──────────────────────────────────────────────────────────────────
DAU_CA = "Đầu ca"
GIUA_CA = "Giữa ca"
CUOI_CA = "Cuối ca"
TUAN = "Tuần"
LUOT = (DAU_CA, GIUA_CA, CUOI_CA, TUAN)

# Lượt Tuần LÀ lượt đầu ca thứ Hai, không phải lượt thứ tư trong ngày (spec 1.1.6).
# Mọi chỗ hỏi "có phải đầu ca không" phải hỏi qua hàm này, đừng so chuỗi.
DAU_CA_HOAC_TUAN = (DAU_CA, TUAN)

CA = ("Sáng", "Chiều")

# ── Công đoạn (cho phiếu sự cố) ───────────────────────────────────────────
# 10 công đoạn mà spec ghim theo SỐ trong luật map tự động (2,3,4,6,7,8,10,12,
# 13,14) là chắc chắn. Sáu cái còn lại chỉ dùng khi người ta tự chọn tay —
# TÊN của chúng cần Ban ISO xác nhận lại theo HD.08.01, đánh dấu ở đây để
# không ai tưởng đã chốt.
CONG_DOAN = [
    "1 Tiếp nhận, ngâm đỗ",      # cần xác nhận tên
    "2 Luộc",
    "3 Rang",
    "4 Sàng cát",
    "5 Ủ",                       # cần xác nhận tên
    "6 Vỡ đỗ, nam châm",
    "7 Nghiền",
    "8 Kho bột",
    "9 Trộn",                    # cần xác nhận tên
    "10 Ủ sau trộn",
    "11 Ép khuôn",               # cần xác nhận tên
    "12 Cân, khối lượng tịnh",
    "13 Hàn túi",
    "14 Nhãn, HSD",
    "15 Đóng thùng",             # cần xác nhận tên
    "16 Lưu kho thành phẩm",     # cần xác nhận tên
    "PRP",
    "Bột: tiếp nhận",
    "Bột: nhặt lạc",
    "Bột: rang lạc",
    "Bột: xay đường",
    "Bột: trộn",
    "Bột: đóng túi",
    "Bột: đóng thùng",
]

LOAI_SU_CO = ("oPRP", "PRP", "Dị ứng", "Hiệu chỉnh hồ sơ", "Khác")
MUC_DO = ("Thường", "Cao")
NGUON = ("Vòng kiểm QC", "Tiếp nhận NL", "Khiếu nại", "Phát hiện khác")
QUYET_DINH_SP = ("Dùng lại sau xử lý", "Rework (BM.15.01)",
                 "Chuyển mục đích khác", "Loại bỏ", "Không ảnh hưởng sản phẩm")

# Tri-state: RỖNG là một giá trị có nghĩa ("chưa kiểm"), không phải "chưa lưu".
# Đây là lý do mọi mục Đ/K là Select chứ không phải Check — Check chỉ có 0/1,
# mà 0 thì không phân biệt nổi "kiểm rồi, không đạt" với "chưa kiểm".
DAT = "Đạt"
KHONG_DAT = "Không đạt"
TRI_STATE = f"\n{DAT}\n{KHONG_DAT}"

# ── Bước trên màn hình (gom mục theo trình tự công đoạn của HD.08.01) ─────
# (ma, tên hiển thị, nhãn oPRP, ghi chú nhóm)
BUOC = [
    ("A",  "Đầu ca",           "",        ""),
    ("2",  "Luộc",             "oPRP-1",  ""),
    ("3",  "Rang",             "oPRP-1",  ""),
    ("4",  "Sàng cát",         "oPRP-2",  ""),
    ("6",  "Vỡ đỗ · Nam châm", "",        ""),
    ("7",  "Nghiền",           "oPRP-2",  ""),
    ("8",  "Kho bột",          "oPRP-3",  ""),
    ("10", "Ủ sau trộn",       "",        ""),
    ("12", "Đóng gói",         "oPRP-4",  "QC đóng gói ghi"),
    ("C",  "Lượt tuần",        "",        "thứ Hai"),
    ("B",  "Bột đậu",          "",        "hôm nay có bột"),
]


def _m(f, so, nhan, buoc, cd, kieu="chon", ap=None, goi=False, bot=False,
       dv="", goi_y="", batbuoc=False, phu=False):
    """Một mục kiểm.

    ap   = tuple lượt áp dụng, None = mọi lượt
    phu  = ô đi kèm một mục khác (vật bắt được, giờ thử…). Vẫn ghi, vẫn in ra,
           nhưng KHÔNG tính vào "đã chấm x/y" và để trống không phải giải trình —
           đếm chúng là bắt QC giải thích vì sao không có mạt kim loại.
    bot  = chỉ áp dụng khi hôm đó CÓ sản xuất bột
    goi  = do QC đóng gói ghi (QC chế biến vẫn thấy, chỉ là không phải việc mình)
    """
    return {"f": f, "so": so, "nhan": nhan, "buoc": buoc, "cd": cd, "kieu": kieu,
            "ap": tuple(ap) if ap else None, "goi": goi, "bot": bot,
            "dv": dv, "goi_y": goi_y, "batbuoc": batbuoc, "phu": phu}


MUC = [
    # ── A: PRP đầu ca ────────────────────────────────────────────────────
    _m("a1_ve_sinh", "1a", "Vệ sinh đầu ca: xưởng, bề mặt, thiết bị sạch khô",
       "A", "PRP", ap=DAU_CA_HOAC_TUAN,
       goi_y="đã vệ sinh chuyển đổi sau lạc / dừa / sữa"),
    _m("a2_cong_nhan", "1b", "Công nhân: bảo hộ, tay, trang sức, không ốm",
       "A", "PRP", ap=DAU_CA_HOAC_TUAN),
    _m("a3_dong_vat", "1c", "Không dấu hiệu động vật gây hại",
       "A", "PRP", ap=DAU_CA_HOAC_TUAN),
    _m("a4_hoa_chat", "1d", "Không hoá chất/dầu trong khu SX; không rò dầu",
       "A", "PRP", ap=DAU_CA_HOAC_TUAN),

    # ── B: dây chuyền bánh ───────────────────────────────────────────────
    _m("luoc_soi_du", "2", "Sôi liên tục, đỗ chín nổi", "2", "2 Luộc"),
    _m("rang_nhiet_do", "3a", "Nhiệt độ rang", "3", "3 Rang", kieu="nguyen",
       dv="°C", goi_y="≥ 255 · ngoài 255–270 cảnh báo vận hành", batbuoc=True),
    _m("rang_vong_quay", "3b", "Vòng quay lồng rang", "3", "3 Rang", kieu="so",
       dv="v/ph", goi_y="6,2 – 7,0"),
    _m("rang_mau_dat", "3c", "Hạt vàng hoa cau", "3", "3 Rang"),
    _m("luoi_sang_nguyen_ven", "4", "Lưới sàng cát / sàng lại nguyên vẹn",
       "4", "4 Sàng cát"),
    _m("nam_cham_da_kiem", "6", "Nam châm đã kiểm, vệ sinh",
       "6", "6 Vỡ đỗ, nam châm", ap=DAU_CA_HOAC_TUAN),
    _m("nam_cham_vat", "6b", "Vật bắt được", "6", "6 Vỡ đỗ, nam châm",
       kieu="chu", ap=DAU_CA_HOAC_TUAN, goi_y="để trống nếu không có", phu=True),
    _m("nam_cham_mat_kim_loai", "6c", "Có mạt kim loại",
       "6", "6 Vỡ đỗ, nam châm", kieu="co_khong", ap=DAU_CA_HOAC_TUAN,
       goi_y="tích = tạo sự cố", phu=True),
    _m("do_min_dat", "7", "Độ mịn đạt, rây 0,2 mm", "7", "7 Nghiền"),
    _m("thung_bot_qua_han", "8", "Thùng bột quá 2 ngày / hở nắp",
       "8", "8 Kho bột", kieu="nguyen", dv="thùng",
       goi_y="0 thùng = đạt · > 0 tạo sự cố"),
    _m("thung_u_day_kin", "10", "Thùng ủ sau trộn đậy kín", "10", "10 Ủ sau trộn"),
    _m("kl_tinh_dat", "11", "Khối lượng tịnh đạt", "12",
       "12 Cân, khối lượng tịnh", goi=True),
    _m("moi_han_kin", "12", "Mối hàn túi kín", "12", "13 Hàn túi", goi=True,
       ap=(GIUA_CA, CUOI_CA)),
    _m("nhan_hsd_dung", "13", "Nhãn, HSD đúng lô", "12", "14 Nhãn, HSD", goi=True),

    # ── C: lượt tuần ─────────────────────────────────────────────────────
    _m("t1_be_nuoc", "T1", "Bể nước sạch, có nắp", "C", "PRP", ap=(TUAN,)),
    _m("t2_so_bay_dau_hieu", "T2", "Trạm bẫy có dấu hiệu", "C", "PRP",
       kieu="nguyen", ap=(TUAN,), dv="trạm", goi_y="> 0 chỉ cảnh báo, không tự sự cố"),
    _m("t3_luoi_chan", "T3", "Lưới chắn côn trùng", "C", "PRP", ap=(TUAN,)),
    _m("t4_den_kinh", "T4", "Đèn, kính có bảo vệ", "C", "PRP", ap=(TUAN,)),
    _m("t5_tu_hoa_chat", "T5", "Tủ hoá chất khoá, có nhãn", "C", "PRP", ap=(TUAN,)),
    _m("t6_kho", "T6", "Kho: kê cao, cách tường", "C", "PRP", ap=(TUAN,)),
    _m("t7_rac_cong", "T7", "Rác, cống thoát", "C", "PRP", ap=(TUAN,)),
    _m("t8_bon_rua_tay", "T8", "Bồn rửa tay: xà phòng, khăn", "C", "PRP", ap=(TUAN,)),
    _m("t9_thiet_bi", "T9", "Thiết bị: không rỉ, không rò dầu", "C", "PRP", ap=(TUAN,)),
    _m("t10_khoa", "T10", "Khoá cửa, kho", "C", "PRP", ap=(TUAN,)),
    _m("t11_can_qua_chuan", "T11", "Cân: quả chuẩn đạt", "C", "PRP", ap=(TUAN,)),

    # ── D: dây chuyền bột ────────────────────────────────────────────────
    _m("san_pham_bot", "B0", "Vị đang sản xuất", "B", "Bột: trộn",
       kieu="chu", bot=True, goi_y="để truy xuất lô", phu=True),
    _m("b1_lac_sach", "B1", "Lạc trước rang: đã sàng, không mốc/hỏng/sạn",
       "B", "Bột: nhặt lạc", bot=True),
    _m("b2_rang_lac_nhiet", "B2a", "Rang lạc: nhiệt độ", "B", "Bột: rang lạc",
       kieu="nguyen", bot=True, dv="°C", goi_y="ngưỡng lấy từ SX QC Setting"),
    _m("b2_rang_lac_phut", "B2b", "Rang lạc: thời gian mẻ", "B", "Bột: rang lạc",
       kieu="nguyen", bot=True, dv="phút", goi_y="ngưỡng lấy từ SX QC Setting"),
    _m("b2_lac_chin", "B2c", "Lạc chín vàng đều", "B", "Bột: rang lạc", bot=True),
    _m("b3_cong_thuc", "B3", "Đường xay, rây; cân đúng công thức",
       "B", "Bột: xay đường", bot=True),
    _m("b4_moi_han_tui", "B4", "Mối hàn túi 40 g kín, 5 túi", "B", "Bột: đóng túi",
       bot=True, goi=True, ap=(GIUA_CA, CUOI_CA)),
    _m("b5_nhan_di_ung", "B5", "Nhãn đúng sản phẩm, HSD, cảnh báo lạc/sữa",
       "B", "Bột: đóng túi", bot=True),
    _m("b6_kl_tui", "B6", "KL tịnh túi 40 g", "B", "Bột: đóng túi",
       bot=True, goi=True),
    _m("b7_chuyen_doi", "B7", "Chuyển đổi sau chè đậu đen cốt dừa — thử nhanh lạc",
       "B", "Bột: trộn", kieu="chon3", bot=True,
       goi_y="Dương tính → sự cố Dị ứng, mức Cao"),
    _m("b7_gio", "B7b", "Giờ thử", "B", "Bột: trộn", kieu="gio", bot=True, phu=True),
]

THEO_F = {m["f"]: m for m in MUC}

# b7 có bộ giá trị riêng (không phải Đạt/Không đạt) — khai một chỗ để DocType
# JSON, luật sinh sự cố và màn hình dùng chung.
B7_KHONG = "Không có chuyển đổi"
B7_AM = "Âm tính"
B7_DUONG = "Dương tính"
B7_OPTIONS = f"\n{B7_KHONG}\n{B7_AM}\n{B7_DUONG}"

# Mục có giá trị SỐ: rỗng khác 0. Người không đo được thì để trống + ghi lý do;
# gõ 0 là khẳng định "đo được, bằng 0". Đừng gộp hai cái đó lại.
KIEU_SO = ("so", "nguyen")


# ═══ Ô SỐ: 0 nghĩa là gì ═══════════════════════════════════════════════════
# Frappe KHÔNG cho Int/Float để trống — không ghi gì thì đọc ra 0. Với ô ĐẾM
# (thùng quá hạn, trạm bẫy) thì 0 là một con số thật: "đếm được 0". Với ô ĐO
# (nhiệt độ, vòng quay, phút rang) thì 0 là "chưa đo" — và nếu coi nó là số thật
# thì mọi lượt chưa kịp đo nhiệt độ đều tự sinh sự cố "nhiệt độ < 255", ngày nào
# cũng vài cái, rồi không ai thèm đọc phiếu sự cố nữa. Đó là cách một hệ thống
# ISO chết: không phải vì thiếu số liệu, mà vì quá nhiều báo động giả.
DEM = ("thung_bot_qua_han", "t2_so_bay_dau_hieu")


def co_ghi(muc_, gia_tri):
    """Mục này đã được ghi chưa. Xem khối chú thích ngay trên."""
    if muc_["kieu"] == "co_khong":
        return True                      # checkbox: không tích cũng là một câu trả lời
    if gia_tri is None or gia_tri == "":
        return False
    if muc_["kieu"] in KIEU_SO and muc_["f"] not in DEM:
        try:
            return float(gia_tri) != 0
        except (TypeError, ValueError):
            return False
    return True


def ap_dung(muc, luot, co_bot):
    """Mục này có phải ghi ở lượt đó không (ma trận 1.1.5)."""
    if muc["bot"] and not co_bot:
        return False
    if muc["ap"] is None:
        return True
    return luot in muc["ap"]


def muc_ap_dung(luot, co_bot):
    return [m for m in MUC if ap_dung(m, luot, co_bot)]


def muc_cham(luot, co_bot):
    """Mục TÍNH VÀO tiến độ (bỏ ô đi kèm) — dùng cho thanh x/y và cho luật
    'để trống phải có lý do'."""
    return [m for m in muc_ap_dung(luot, co_bot) if not m["phu"]]


def ma_tran(co_bot):
    """{lượt: [fieldname...]} — gửi cho máy QC để ẩn/hiện, server dùng để validate.

    Cùng một hàm sinh ra cả hai, nên màn hình không bao giờ hiện mục mà server
    không kiểm, và ngược lại.
    """
    return {l: [m["f"] for m in muc_ap_dung(l, co_bot)] for l in LUOT}
