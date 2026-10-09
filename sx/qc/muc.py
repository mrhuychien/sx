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

# ── Phiên bản bộ mục (D129) ───────────────────────────────────────────────
# Bản giấy BM.08.01 sửa đổi thì bộ mục đổi. Phiếu đã ghi theo bộ cũ phải giữ
# NGUYÊN bộ cũ: thêm mục mới vào phiếu tháng trước là tờ in ra một hàng "chưa
# kiểm" mà hôm đó mục ấy chưa tồn tại; bỏ mục cũ khỏi phiếu cũ là mất số đã ghi.
# Mỗi phiếu nhớ phiên bản lúc mở (SX QC Round.phien_ban — phiếu trước D129 để
# trống, đọc là 1); mỗi mục có `tu` (từ phiên bản) / `den` (tới, không gồm).
#   1  bản đầu (D85 … D128)
#   2  W01/W02 08/10/2026: 1e chuyển đổi trong ngày, 4b thùng/khay cát, 5 Ủ, 7 rây
#      kiểm RY-01 (hạt thô, dị vật), B7c vệ sinh chuyển đổi sữa; bỏ T11 quả chuẩn
#      (sang quản lý thiết bị đo — W17)
PHIEN_BAN = 2

# ── Lượt ──────────────────────────────────────────────────────────────────
# MỘT NGÀY BA LƯỢT, không chia ca (D95). Trước D95 là 3 lượt × 2 ca Sáng/Chiều;
# nhà máy đổi sang ba mốc cố định trong ngày, mỗi mốc có hạn chót riêng — xem
# khung giờ trong sx/qc/nguong.py.
DAU_SANG = "Đầu sáng"
TRUA = "Trưa"
CUOI_CHIEU = "Cuối chiều"
TUAN = "Tuần"
# W23 (D147): lượt RIÊNG ngoài ba lượt trong ngày — đi lại sau mất điện / sự cố máy. Không có
# khung giờ, không tính vào "đủ 3 lượt", một ngày có thể nhiều lượt; bộ mục như lượt Trưa
# (các phép đo đang sản xuất). Phải ghi lý do.
BO_SUNG = "Bổ sung"
LY_DO_BO_SUNG = ("Mất điện", "Sự cố máy", "Khác")
LUOT = (DAU_SANG, TRUA, CUOI_CHIEU, TUAN, BO_SUNG)

# Ba ô trên màn Hôm nay, theo thứ tự trong ngày. Tuần KHÔNG nằm đây: nó chiếm
# chỗ của Đầu sáng vào thứ Hai chứ không phải ô thứ tư.
LUOT_TRONG_NGAY = (DAU_SANG, TRUA, CUOI_CHIEU)

# Lượt Tuần LÀ lượt đầu sáng thứ Hai, không phải lượt thứ tư trong ngày (spec
# 1.1.6). Mọi chỗ hỏi "có phải lượt đầu ngày không" phải hỏi qua tuple này.
DAU_NGAY_HOAC_TUAN = (DAU_SANG, TUAN)

# Tên lượt trước D95 → tên mới. Patch d95 dùng bảng này đổi phiếu cũ; giữ ở đây
# để mọi chỗ cần đọc dữ liệu cũ tra cùng một bảng.
DOI_TEN_CU = {"Đầu ca": DAU_SANG, "Giữa ca": TRUA, "Cuối ca": CUOI_CHIEU}

# ── Công đoạn (cho phiếu sự cố) ───────────────────────────────────────────
# Từ D130 (W04) danh mục công đoạn là DocType "SX QC Cong Doan" — Ban ISO sửa tên
# cho khớp QT.08 / KH.HACCP (bánh 16, bột 11), thêm công đoạn còn thiếu. Đổi tên
# bằng Rename trên Desk: Frappe cập nhật luôn mọi phiếu sự cố cũ trỏ tới nó.
#
# Bảng dưới là BẢN GỐC để tạo sẵn (patch d130) và để vòng kiểm biết mục nào thuộc
# công đoạn nào: mục kiểm trỏ tới công đoạn bằng TÊN GỐC (cột 2); lúc sinh sự cố,
# tên gốc → MÃ (cột 1) → tên HIỆN TẠI trong DocType. Đổi tên không làm vòng kiểm lạc.
# (mã, tên gốc, dây chuyền, thứ tự)
CONG_DOAN_GOC = [
    ("1", "1 Tiếp nhận, ngâm đỗ", "Bánh", 1),
    ("2", "2 Luộc", "Bánh", 2),
    ("3", "3 Rang", "Bánh", 3),
    ("4", "4 Sàng cát", "Bánh", 4),
    ("5", "5 Ủ", "Bánh", 5),
    ("6", "6 Vỡ đỗ, nam châm", "Bánh", 6),
    ("7", "7 Nghiền", "Bánh", 7),
    ("8", "8 Kho bột", "Bánh", 8),
    ("9", "9 Trộn", "Bánh", 9),
    ("10", "10 Ủ sau trộn", "Bánh", 10),
    ("11", "11 Ép khuôn", "Bánh", 11),
    ("12", "12 Cân, khối lượng tịnh", "Bánh", 12),
    ("13", "13 Hàn túi", "Bánh", 13),
    ("14", "14 Nhãn, HSD", "Bánh", 14),
    ("15", "15 Đóng thùng", "Bánh", 15),
    ("16", "16 Lưu kho thành phẩm", "Bánh", 16),
    ("PRP", "PRP", "Chung", 0),
    ("bot-tiep-nhan", "Bột: tiếp nhận", "Bột", 1),
    ("bot-nhat-lac", "Bột: nhặt lạc", "Bột", 2),
    ("bot-rang-lac", "Bột: rang lạc", "Bột", 3),
    ("bot-xay-duong", "Bột: xay đường", "Bột", 4),
    ("bot-tron", "Bột: trộn", "Bột", 5),
    ("bot-dong-tui", "Bột: đóng túi", "Bột", 6),
    ("bot-dong-thung", "Bột: đóng thùng", "Bột", 7),
]
CONG_DOAN = [t[1] for t in CONG_DOAN_GOC]
MA_CONG_DOAN = {t[1]: t[0] for t in CONG_DOAN_GOC}

LOAI_SU_CO = ("oPRP", "PRP", "Dị ứng", "Hiệu chỉnh hồ sơ", "Khác")
MUC_DO = ("Thường", "Cao")
NGUON = ("Vòng kiểm QC", "Tiếp nhận NL", "Khiếu nại", "Kiểm tra xuất xưởng",
         "Hàng trả về", "Kiểm xe", "Động vật gây hại", "Thiết bị đo",
         "Kết quả kiểm nghiệm", "Nhật ký cát", "Đánh giá nội bộ", "Phát hiện khác",
         "Nhật ký chuyền")
# Nguồn CHỌN TAY khi lập phiếu trên màn QC (W11, D134). "Vòng kiểm QC", "Tiếp nhận
# NL", "Nhật ký chuyền" do hệ thống tự gắn khi sinh phiếu — chọn tay thì phiếu mang
# nguồn đó mà không có vòng kiểm / hoá đơn / phiếu ngày nào đứng sau, sổ nói dối.
NGUON_TAY = ("Phát hiện khác", "Khiếu nại", "Kiểm tra xuất xưởng", "Hàng trả về",
             "Kiểm xe", "Động vật gây hại", "Thiết bị đo", "Kết quả kiểm nghiệm",
             "Nhật ký cát", "Đánh giá nội bộ")
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
    ("5",  "Ủ",                "",        ""),
    ("6",  "Vỡ đỗ · Nam châm", "",        ""),
    ("7",  "Nghiền",           "oPRP-2",  ""),
    ("8",  "Kho bột",          "oPRP-3",  ""),
    ("10", "Ủ sau trộn",       "",        ""),
    ("12", "Đóng gói",         "oPRP-4",  "QC đóng gói ghi"),
    ("C",  "Lượt tuần",        "",        "thứ Hai"),
    ("B",  "Bột đậu",          "",        "hôm nay có bột"),
]

# Công đoạn TẮT ĐƯỢC khi hôm đó không chạy (D107): hôm không rang đỗ thì mục 3
# không có gì để kiểm. Không tắt được:
#   A  PRP đầu ca  — kiểm cái XƯỞNG (vệ sinh, công nhân, côn trùng), không phải dây chuyền
#   8  Kho bột     — thùng bột nằm trong kho dù hôm nay có nghiền hay không
#   C  Lượt tuần   — lịch tuần, không theo sản xuất
#   B  Bột đậu     — đã có công tắc riêng "có sản xuất bột"
BUOC_TAT_DUOC = ("2", "3", "4", "5", "6", "7", "10", "12")


def _oprp_buoc(ma):
    """Mã oPRP của một bước ("" nếu bước đó không phải oPRP)."""
    return next((o for m, _t, o, _g in BUOC if m == ma), "")


# oPRP của phần bột (W03, D128). Dây chuyền bánh gắn oPRP theo công đoạn (BUOC);
# phần bột gắn theo MỤC, cùng loại kiểm soát với bánh: xử lý nhiệt (rang lạc) như
# luộc/rang đỗ → oPRP-1; hàn kín bao gói như đóng gói bánh → oPRP-4.
# Ban ISO đối chiếu KH.HACCP dây chuyền bột — khác thì sửa đúng hai hằng số này.
OPRP_NHIET = "oPRP-1"
OPRP_GOI = "oPRP-4"


# ── Máy chạy song song (D100) ─────────────────────────────────────────────
# Xưởng có 3 máy rang đỗ, 2 máy nghiền, 3 máy đóng gói bột — nhưng không phải
# ngày nào cũng chạy đủ. Mục gắn nhóm máy thì MÁY 1 dùng đúng fieldname cũ (phiếu
# trước D100 vẫn đọc nguyên), máy 2/3 là field `<f>_m2`, `<f>_m3`. Số máy đang
# chạy nằm trên phiếu (field đếm bên dưới), mặc định 1; QC bấm "+ Thêm máy" khi
# có thêm máy chạy. Máy không chạy thì các ô của nó KHÔNG áp dụng — không phải
# "để trống cần giải trình".
# nhóm: (tên hiển thị, số máy tối đa, fieldname đếm trên SX QC Round)
NHOM_MAY = {
    "rang": ("Máy rang đỗ", 3, "so_may_rang"),
    "nghien": ("Máy nghiền bột", 2, "so_may_nghien"),
    "goi_bot": ("Máy đóng gói bột", 3, "so_may_goi_bot"),
}

# MÃ MÁY THẬT (W02/W16): rây kiểm ghi theo máy nghiền M1 / M2; nhiệt độ, vòng quay ghi
# theo máy rang M1 / M2 / M3 (W16, tài liệu 08/10). Ba máy gói bột CHƯA có mã (chờ Cơ
# điện, C10) — vẫn hiện "máy 1/2/3"; có mã thì điền tuple vào đây là nhãn đổi theo. Chỉ
# đổi NHÃN: fieldname không đổi (máy 1 = field gốc, máy k = `<f>_mk`).
MA_MAY = {
    "rang": ("M1", "M2", "M3"),
    "nghien": ("M1", "M2"),
}


def ten_may_so(nhom, k):
    """Nhãn máy thứ k của một nhóm: mã thật nếu có ("M2"), không thì "máy 2"."""
    ma = MA_MAY.get(nhom) or ()
    return ma[k - 1] if 0 < k <= len(ma) else f"máy {k}"

# ── Lạc (D100) ────────────────────────────────────────────────────────────
# Mục về LẠC chỉ áp dụng khi hôm đó làm vị có lạc (chè đậu đen cốt dừa). Hai
# nghĩa khác nhau, tách hai cờ:
#   LAC_LAM  nhặt / rang lạc — chỉ khi lượt này có làm vị có lạc
#   LAC_DOI  thử nhanh lạc sau chuyển đổi — cả khi lượt này có vị có lạc, LẪN
#            khi một lượt TRƯỚC trong ngày có: sáng làm chè đậu đen, trưa đổi sang
#            sữa dừa thì chính lượt trưa mới là lúc phải thử.
LAC_LAM = "lam"
LAC_DOI = "doi"

# Sữa (D129, W01): ô vệ sinh chuyển đổi sau vị có SỮA BỘT — cùng luật với thử lạc
# sau chuyển đổi: lượt này hoặc một lượt trước trong ngày có làm vị có sữa bột.
SUA_DOI = "doi"


def _m(f, so, nhan, buoc, cd, kieu="chon", ap=None, goi=False, bot=False,
       dv="", goi_y="", batbuoc=False, phu=False, ngan="", may=None, lac=None,
       oprp=None, sua=None, loai=None, tu=1, den=None):
    """Một mục kiểm.

    ap   = tuple lượt áp dụng, None = mọi lượt
    ngan = nhãn rút gọn cho MÀN HÌNH. Tờ in A4 luôn dùng `nhan` đầy đủ vì
           auditor cầm nó so với BM.08.01 bản giấy; còn trên điện thoại một
           nhãn 6 chữ xuống dòng bốn lần làm hàng cao gấp đôi, cả lượt phải
           cuộn thêm một màn. Bỏ trống thì dùng luôn `nhan`.
    phu  = ô đi kèm một mục khác (vật bắt được, giờ thử…). Vẫn ghi, vẫn in ra,
           nhưng KHÔNG tính vào "đã chấm x/y" và để trống không phải giải trình —
           đếm chúng là bắt QC giải thích vì sao không có mạt kim loại.
    bot  = chỉ áp dụng khi hôm đó CÓ sản xuất bột
    goi  = do QC đóng gói ghi (QC chế biến vẫn thấy, chỉ là không phải việc mình)
    may  = nhóm máy (NHOM_MAY) — mục này ghi riêng cho từng máy đang chạy
    lac  = LAC_LAM / LAC_DOI — chỉ áp dụng khi có làm vị có lạc (xem trên)
    oprp = mã oPRP của riêng mục này (W03). Bỏ trống = theo bước (BUOC) — dây
           chuyền bánh gắn oPRP theo công đoạn; phần bột gắn theo từng mục.
    sua  = SUA_DOI — chỉ áp dụng khi có làm vị có sữa bột (lượt này / lượt trước)
    loai = loại sự cố khi mục Không đạt, nếu khác loại suy từ công đoạn (PRP…)
    tu, den = phiên bản bộ mục mục này có mặt: [tu, den) — xem PHIEN_BAN
    """
    return {"f": f, "so": so, "nhan": nhan, "ngan": ngan or nhan, "buoc": buoc, "cd": cd, "kieu": kieu,
            "ap": tuple(ap) if ap else None, "goi": goi, "bot": bot,
            "dv": dv, "goi_y": goi_y, "batbuoc": batbuoc, "phu": phu,
            "may": may, "may_so": 1 if may else 0, "goc": f, "lac": lac,
            "oprp": oprp or _oprp_buoc(buoc), "sua": sua, "loai": loai,
            "tu": tu, "den": den}


MUC = [
    # ── A: PRP đầu ca ────────────────────────────────────────────────────
    _m("a1_ve_sinh", "1a", "Vệ sinh đầu ca: xưởng, bề mặt, thiết bị sạch khô",
       "A", "PRP", ap=DAU_NGAY_HOAC_TUAN,
       goi_y="sạch khô; đã vệ sinh chuyển đổi sau lạc / dừa / sữa",
       ngan="Vệ sinh xưởng, bề mặt, thiết bị"),
    _m("a2_cong_nhan", "1b", "Công nhân: bảo hộ, tay, trang sức, không ốm",
       "A", "PRP", ap=DAU_NGAY_HOAC_TUAN,
       ngan="Công nhân: BHLĐ, tay, sức khoẻ", goi_y="không trang sức, không ốm"),
    _m("a3_dong_vat", "1c", "Không dấu hiệu động vật gây hại",
       "A", "PRP", ap=DAU_NGAY_HOAC_TUAN,
       ngan="Không dấu hiệu động vật gây hại"),
    _m("a4_hoa_chat", "1d", "Không hoá chất/dầu trong khu SX; không rò dầu",
       "A", "PRP", ap=DAU_NGAY_HOAC_TUAN,
       ngan="Hoá chất cất đúng nơi", goi_y="không hoá chất/dầu trong khu SX; không rò dầu"),
    # W01 (D129): chuyển đổi TRONG NGÀY xảy ra ở lượt nào cũng được (sau lạc / dừa
    # / sữa) nên mục này có ở cả ba lượt; không chuyển đổi thì bấm "Không có".
    _m("a5_chuyen_doi", "1e", "Vệ sinh chuyển đổi trong ngày (sau lạc / dừa / sữa)",
       "A", "PRP", kieu="chon_cd", loai="Dị ứng", tu=2,
       ngan="Vệ sinh chuyển đổi trong ngày", goi_y="sau lạc / dừa / sữa — không có thì bấm Không có"),

    # ── B: dây chuyền bánh ───────────────────────────────────────────────
    _m("luoc_soi_du", "2", "Sôi liên tục, đỗ chín nổi", "2", "2 Luộc"),
    _m("rang_nhiet_do", "3a", "Nhiệt độ rang", "3", "3 Rang", kieu="nguyen",
       dv="°C", goi_y="≥ 255 · ngoài 255–270 cảnh báo vận hành", batbuoc=True,
       may="rang"),
    _m("rang_vong_quay", "3b", "Vòng quay lồng rang", "3", "3 Rang", kieu="so",
       dv="v/ph", goi_y="6,2 – 7,0", may="rang"),
    _m("rang_mau_dat", "3c", "Hạt vàng hoa cau", "3", "3 Rang"),
    _m("luoi_sang_nguyen_ven", "4a", "Lưới sàng cát / sàng lại nguyên vẹn",
       "4", "4 Sàng cát",
       ngan="Lưới sàng nguyên vẹn", goi_y="sàng cát và sàng lại"),
    _m("thung_khay_cat_sach", "4b", "Thùng, khay cát sạch", "4", "4 Sàng cát",
       ap=DAU_NGAY_HOAC_TUAN, loai="PRP", tu=2),
    # W01 (D129): mục 5 trên bản giấy. Vải ủ (không phải "khăn phủ"). Chất vải, giặt
    # mỗi lần hay mỗi tuần, số tấm, giờ ủ tối đa: CHỜ quyết định — chỉ kiểm sạch/khô.
    _m("u_thung_vai_sach", "5", "Thùng ủ, vải ủ sạch, khô", "5", "5 Ủ",
       loai="PRP", tu=2, ngan="Thùng ủ, vải ủ sạch khô"),
    _m("nam_cham_da_kiem", "6", "Nam châm đã kiểm, vệ sinh",
       "6", "6 Vỡ đỗ, nam châm", ap=DAU_NGAY_HOAC_TUAN),
    _m("nam_cham_vat", "6b", "Vật bắt được", "6", "6 Vỡ đỗ, nam châm",
       kieu="chu", ap=DAU_NGAY_HOAC_TUAN, goi_y="để trống nếu không có", phu=True),
    _m("nam_cham_mat_kim_loai", "6c", "Có mạt kim loại",
       "6", "6 Vỡ đỗ, nam châm", kieu="co_khong", ap=DAU_NGAY_HOAC_TUAN,
       goi_y="tích = tạo sự cố", phu=True),
    # W02 (D129): rây kiểm RY-01 theo từng máy nghiền M1 / M2 — Đ/K, đếm hạt thô,
    # có dị vật. Máy 1 giữ fieldname cũ (do_min_dat) để phiếu trước D129 đọc nguyên.
    _m("do_min_dat", "7a", "Rây kiểm RY-01: độ mịn đạt (rây 0,2 mm)", "7", "7 Nghiền",
       may="nghien", ngan="Rây RY-01: độ mịn đạt"),
    _m("hat_tho", "7b", "Rây kiểm RY-01: số hạt thô trên rây", "7", "7 Nghiền",
       kieu="nguyen", dv="hạt", may="nghien", tu=2, ngan="Số hạt thô trên rây",
       goi_y="0 = không có hạt thô"),
    _m("di_vat_ray", "7c", "Rây kiểm RY-01: có dị vật", "7", "7 Nghiền",
       kieu="co_khong", may="nghien", tu=2, phu=True, ngan="Có dị vật trên rây",
       goi_y="tích = tạo sự cố"),
    _m("thung_bot_qua_han", "8", "Thùng bột quá 2 ngày / hở nắp",
       "8", "8 Kho bột", kieu="nguyen", dv="thùng",
       goi_y="0 thùng = đạt · > 0 tạo sự cố"),
    _m("thung_u_day_kin", "10", "Thùng ủ sau trộn đậy kín", "10", "10 Ủ sau trộn"),
    _m("kl_tinh_dat", "11", "Khối lượng tịnh đạt", "12",
       "12 Cân, khối lượng tịnh", goi=True),
    _m("moi_han_kin", "12", "Mối hàn túi kín", "12", "13 Hàn túi", goi=True,
       ap=(TRUA, CUOI_CHIEU)),
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
    # Bỏ từ phiên bản 2 (W01): cân theo hạn kiểm định ở quản lý thiết bị đo (W17).
    _m("t11_can_qua_chuan", "T11", "Cân: quả chuẩn đạt", "C", "PRP", ap=(TUAN,), den=2),

    # ── D: dây chuyền bột ────────────────────────────────────────────────
    # B0: bấm chọn trong danh mục bột của báo mẻ (D100), nhiều vị một lượt. Tính
    # vào "đã chấm": bật bột mà không nói làm vị gì thì lô không truy được.
    _m("san_pham_bot", "B0", "Loại bột đang sản xuất", "B", "Bột: trộn",
       kieu="chon_bot", bot=True, goi_y="bấm chọn — có thể nhiều vị"),
    _m("b1_lac_sach", "B1", "Lạc trước rang: đã sàng, không mốc/hỏng/sạn",
       "B", "Bột: nhặt lạc", bot=True, lac=LAC_LAM,
       ngan="Lạc sạch, không mốc/sạn", goi_y="đã sàng trước rang"),
    _m("b2_rang_lac_nhiet", "B2a", "Rang lạc: nhiệt độ", "B", "Bột: rang lạc",
       kieu="nguyen", bot=True, dv="°C", goi_y="150 – 180 °C",
       lac=LAC_LAM, oprp=OPRP_NHIET),
    _m("b2_rang_lac_phut", "B2b", "Rang lạc: thời gian mẻ", "B", "Bột: rang lạc",
       kieu="nguyen", bot=True, dv="phút", goi_y="30 – 40 phút",
       lac=LAC_LAM, oprp=OPRP_NHIET),
    _m("b2_lac_chin", "B2c", "Lạc chín vàng đều", "B", "Bột: rang lạc", bot=True,
       lac=LAC_LAM, oprp=OPRP_NHIET),
    _m("b3_cong_thuc", "B3", "Đường xay, rây; cân đúng công thức",
       "B", "Bột: xay đường", bot=True,
       ngan="Đúng công thức trộn", goi_y="đường xay, rây; cân đúng"),
    # Máy đóng gói bột (D100): nhiệt độ hàn + mối hàn + khối lượng, TỪNG MÁY.
    _m("b8_nhiet_han", "B8", "Máy đóng gói: nhiệt độ hàn", "B", "Bột: đóng túi",
       kieu="nguyen", bot=True, goi=True, dv="°C", may="goi_bot",
       ngan="Nhiệt độ hàn", goi_y="150 – 190 °C", oprp=OPRP_GOI),
    _m("b4_moi_han_tui", "B4", "Mối hàn túi 40 g kín, 5 túi", "B", "Bột: đóng túi",
       bot=True, goi=True, ap=(TRUA, CUOI_CHIEU), may="goi_bot", oprp=OPRP_GOI),
    _m("b6_kl_tui", "B6", "KL tịnh túi 40 g", "B", "Bột: đóng túi",
       bot=True, goi=True, may="goi_bot"),
    _m("b5_nhan_di_ung", "B5", "Nhãn đúng sản phẩm, HSD, cảnh báo lạc/sữa — túi 40 g, hộp nhựa",
       "B", "Bột: đóng túi", bot=True,
       ngan="Nhãn, HSD, cảnh báo lạc/sữa", goi_y="túi 40 g và hộp nhựa — đúng sản phẩm"),
    _m("b7_chuyen_doi", "B7", "Chuyển đổi sau chè đậu đen cốt dừa — thử nhanh lạc",
       "B", "Bột: trộn", kieu="chon3", bot=True, lac=LAC_DOI,
       goi_y="Dương tính → sự cố Dị ứng, mức Cao",
       ngan="Chuyển đổi sau chè — thử nhanh lạc"),
    _m("b7_gio", "B7b", "Giờ thử", "B", "Bột: trộn", kieu="gio", bot=True, phu=True,
       lac=LAC_DOI),
    _m("b7_ve_sinh_sua", "B7c", "Vệ sinh chuyển đổi sau vị có sữa bột", "B", "Bột: trộn",
       kieu="chon_cd", bot=True, sua=SUA_DOI, loai="Dị ứng", tu=2,
       ngan="Vệ sinh chuyển đổi sau vị có sữa", goi_y="không chuyển đổi thì bấm Không có"),
]


def _mo_rong_may(ds):
    """Chèn các ô của máy 2, 3… ngay SAU khối máy 1 của cùng nhóm.

    Khối máy 1 = các mục liền nhau cùng nhóm máy. Chèn ngay sau khối đó để màn
    hình và tờ in đi đúng thứ tự QC đứng: hết máy 1 rồi sang máy 2, không phải
    nhiệt độ của ba máy rồi mới tới vòng quay của ba máy.
    """
    ra, i = [], 0
    while i < len(ds):
        m = ds[i]
        if not m["may"]:
            ra.append(m)
            i += 1
            continue
        j = i
        while j < len(ds) and ds[j]["may"] == m["may"]:
            j += 1
        khoi = ds[i:j]
        ra.extend(khoi)
        for k in range(2, NHOM_MAY[m["may"]][1] + 1):
            for g in khoi:
                ra.append(dict(g, f=f'{g["f"]}_m{k}', may_so=k,
                               nhan=f'{g["nhan"]} — {ten_may_so(m["may"], k)}'))
        i = j
    return ra


MUC = _mo_rong_may(MUC)

THEO_F = {m["f"]: m for m in MUC}

# b7 có bộ giá trị riêng (không phải Đạt/Không đạt) — khai một chỗ để DocType
# JSON, luật sinh sự cố và màn hình dùng chung.
B7_KHONG = "Không có chuyển đổi"
B7_AM = "Âm tính"
B7_DUONG = "Dương tính"
B7_OPTIONS = f"\n{B7_KHONG}\n{B7_AM}\n{B7_DUONG}"

# Mục chuyển đổi (D129: 1e, B7c): Không có chuyển đổi / Đạt / Không đạt. Không có
# là một câu trả lời (đã nhìn, hôm nay không đổi vị) — khác với để trống.
CD_OPTIONS = f"\n{B7_KHONG}\n{DAT}\n{KHONG_DAT}"

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
DEM = ("thung_bot_qua_han", "t2_so_bay_dau_hieu", "hat_tho")


def co_ghi(muc_, gia_tri):
    """Mục này đã được ghi chưa. Xem khối chú thích ngay trên."""
    if muc_["kieu"] == "co_khong":
        return True                      # checkbox: không tích cũng là một câu trả lời
    if gia_tri is None or gia_tri == "":
        return False
    if muc_["kieu"] in KIEU_SO and muc_.get("goc", muc_["f"]) not in DEM:
        try:
            return float(gia_tri) != 0
        except (TypeError, ValueError):
            return False
    return True


def _so(v, mac_dinh=0):
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return mac_dinh


def so_may(v, nhom):
    """Số máy đang chạy, kẹp trong [1, tối đa]. Rỗng / 0 = 1 máy (phiếu cũ)."""
    return min(max(_so(v), 1), NHOM_MAY[nhom][1])


def phien_ban(v):
    """Phiên bản bộ mục của một phiếu. Trống / 0 = 1 (phiếu trước D129)."""
    return _so(v) or 1


def boi_canh(x):
    """Những gì quyết định mục nào áp dụng, ngoài lượt: có bột, có lạc, có sữa,
    số máy, công đoạn nghỉ, phiên bản bộ mục.

    `x` là một phiếu (Document / dict có co_san_xuat_bot…) HOẶC một số 0/1 kiểu
    cũ = "có bột không". Số trần thì coi như vị có lạc đi cùng bột, mỗi nhóm một
    máy, và bộ mục HIỆN HÀNH — đúng nghĩa của mọi nơi gọi cũ (ma trận cho phiếu
    sắp mở), nên nơi gọi cũ không đổi nghĩa. Ô sữa (D129) chỉ bật theo phiếu thật.
    """
    if isinstance(x, dict) and "may" in x and "bot" in x:
        return x
    if x is None or isinstance(x, (int, float, str, bool)):
        b = 1 if _so(x) else 0
        return {"bot": b, "lac": b, "lac_doi": b, "sua_doi": 0,
                "may": {n: 1 for n in NHOM_MAY}, "nghi": frozenset(),
                "pb": PHIEN_BAN}
    g = x.get
    return {"nghi": frozenset(buoc_nghi(g("buoc_nghi"))),
            "bot": 1 if _so(g("co_san_xuat_bot")) else 0,
            "lac": 1 if _so(g("co_lac")) else 0,
            "lac_doi": 1 if (_so(g("can_thu_lac")) or _so(g("co_lac"))) else 0,
            "sua_doi": 1 if (_so(g("can_ve_sinh_sua")) or _so(g("co_sua"))) else 0,
            "may": {n: so_may(g(t[2]), n) for n, t in NHOM_MAY.items()},
            "pb": phien_ban(g("phien_ban"))}


def con_hieu_luc(muc, pb):
    """Mục có trong bộ mục phiên bản `pb` không."""
    return muc.get("tu", 1) <= pb and (not muc.get("den") or pb < muc["den"])


def ap_dung(muc, luot, bc):
    """Mục này có phải ghi ở lượt đó không (ma trận 1.1.5 + D100 + D129).

    `bc` = boi_canh(...) hoặc số 0/1 "có bột" kiểu cũ.
    """
    bc = boi_canh(bc)
    if not con_hieu_luc(muc, bc.get("pb", PHIEN_BAN)):
        return False
    if muc["buoc"] in bc.get("nghi", ()):
        return False
    if muc["bot"] and not bc["bot"]:
        return False
    if muc.get("lac") == LAC_LAM and not bc["lac"]:
        return False
    if muc.get("lac") == LAC_DOI and not bc["lac_doi"]:
        return False
    if muc.get("sua") == SUA_DOI and not bc.get("sua_doi"):
        return False
    if muc.get("may") and muc["may_so"] > bc["may"].get(muc["may"], 1):
        return False
    if muc["ap"] is None:
        return True
    return (TRUA if luot == BO_SUNG else luot) in muc["ap"]


def muc_ap_dung(luot, bc):
    bc = boi_canh(bc)
    return [m for m in MUC if ap_dung(m, luot, bc)]


def muc_cham(luot, bc):
    """Mục TÍNH VÀO tiến độ (bỏ ô đi kèm) — dùng cho thanh x/y và cho luật
    'để trống phải có lý do'."""
    return [m for m in muc_ap_dung(luot, bc) if not m["phu"]]


def buoc_nghi(v):
    """Giá trị ô 'công đoạn không chạy' → [mã bước] — CHỈ những bước tắt được,
    theo thứ tự quy trình. Mã lạ / bước không tắt được (A, 8, C, B) bị bỏ: không
    để một ô chữ tắt được phần PRP đầu ca."""
    chon = set(tach_chon(v))
    return [ma for ma, *_r in BUOC if ma in BUOC_TAT_DUOC and ma in chon]


def ten_may(m):
    """' (máy k)' / ' (M2)' cho câu sự cố — rỗng với mục không theo máy."""
    return f' ({ten_may_so(m["may"], m["may_so"])})' if m.get("may") else ""


# ═══ Loại bột + lạc (D100) ═════════════════════════════════════════════════

def tach_chon(v):
    """Giá trị ô B0 → danh sách mã hàng. Lưu mỗi mã một dòng."""
    # Chỉ tách theo dòng, KHÔNG theo dấu phẩy: tên hàng có dấu phẩy là chuyện
    # thường, tách nhầm là "Bột đậu, sữa dừa" thành hai vị không tồn tại.
    return [x.strip() for x in str(v or "").split("\n") if x.strip()]


def _chuan(s):
    return " ".join(str(s or "").lower().split())


def co_lac_trong(chon, ten_theo_ma, ds_lac):
    """Trong các vị đã chọn có vị nào có lạc không.

    `ds_lac` là danh sách khai ở SX QC Setting (mã HOẶC tên hàng, không phân biệt
    hoa thường). Khớp theo cả mã lẫn tên: người khai cài đặt gõ tên họ nhìn thấy,
    còn phiếu lưu mã.
    """
    lac = {_chuan(x) for x in ds_lac if _chuan(x)}
    return 1 if any(_chuan(c) in lac or _chuan(ten_theo_ma.get(c)) in lac
                    for c in chon) else 0


def thu_tu_luot(luot):
    luot = DAU_SANG if luot == TUAN else luot
    return LUOT_TRONG_NGAY.index(luot) if luot in LUOT_TRONG_NGAY else len(LUOT_TRONG_NGAY)


def can_thu_lac(co_lac, luot, cac_luot_khac):
    """Lượt này có phải thử nhanh lạc (B7) không.

    Có nếu chính lượt này làm vị có lạc, HOẶC một lượt TRƯỚC trong ngày đã làm —
    chuyển đổi sau chè đậu đen xảy ra ở lượt sau, không phải lượt đang làm chè.
    `cac_luot_khac` = [(lượt, co_lac)] của các phiếu khác cùng ngày.
    """
    if co_lac:
        return 1
    t = thu_tu_luot(luot)
    return 1 if any(int(c or 0) and thu_tu_luot(l) < t for l, c in cac_luot_khac) else 0


def can_ve_sinh_sua(co_sua, luot, cac_luot_khac):
    """Lượt này có phải ghi ô vệ sinh chuyển đổi sau vị có sữa bột (B7c) không —
    cùng luật với thử lạc: lượt này hoặc một lượt TRƯỚC trong ngày có làm vị có sữa.
    `cac_luot_khac` = [(lượt, co_sua)]."""
    return can_thu_lac(co_sua, luot, cac_luot_khac)


def ma_tran(co_bot):
    """{lượt: [fieldname...]} — gửi cho máy QC để ẩn/hiện, server dùng để validate.

    Cùng một hàm sinh ra cả hai, nên màn hình không bao giờ hiện mục mà server
    không kiểm, và ngược lại.
    """
    bc = boi_canh(co_bot)
    return {l: [m["f"] for m in muc_ap_dung(l, bc)] for l in LUOT}


# ═══ Cờ "có sản xuất bột" (D98) ════════════════════════════════════════════

def co_bot_ngay(ban_ghi_ngay, rounds):
    """Hôm đó có sản xuất bột không.

    `ban_ghi_ngay` = giá trị cờ trên SX QC Ngay, None nếu ngày đó chưa có bản ghi.
    Có bản ghi thì bản ghi QUYẾT ĐỊNH — kể cả khi nó nói 0 mà có lượt cũ bật bột
    (người ta tắt đi vì bật nhầm). Chưa có bản ghi (ngày trước D98) thì suy từ các
    lượt như cũ, để lịch sử không đổi nghĩa.
    """
    if ban_ghi_ngay is not None:
        return 1 if int(ban_ghi_ngay or 0) else 0
    return 1 if any(int((r or {}).get("co_san_xuat_bot") or 0) for r in rounds) else 0


def muc_bot_da_ghi(gia_tri):
    """Mục phần bột ĐÃ CÓ GIÁ TRỊ trên một lượt — {fieldname: giá trị} → [mục].

    Dùng trước khi TẮT bột: tắt là mấy ô đó biến khỏi màn hình (giá trị vẫn nằm
    trong DB nhưng không ai thấy, không vào tờ in, không sinh sự cố). Người tắt
    phải biết mình đang giấu cái gì.
    """
    return [m for m in MUC if m["bot"] and m["kieu"] != "co_khong"
            and co_ghi(m, gia_tri.get(m["f"]))]
