"""Báo cáo tháng, chỉ tiêu ATTP (W25, D151) — số liệu cho mục tiêu ATTP và họp xem xét của lãnh đạo.

Hai lớp:
  · CHỈ SỐ — app tự tính từ hồ sơ trên app, cố định trong code (CHI_SO): theo THÁNG (lượt kiểm, sự cố,
    khiếu nại, kiểm nghiệm, xuất xưởng, rework, động vật gây hại, khắc phục) hoặc TẠI NGÀY LẬP (thiết bị đo,
    kiểm nghiệm còn hạn, nhà cung cấp đã duyệt). Chỉ số % giữ dạng (tử, mẫu) để cộng lũy kế năm cho đúng —
    lấy trung bình các tỷ lệ tháng là sai khi có tháng ít ngày sản xuất.
  · CHỈ TIÊU — mục tiêu ATTP năm do Ban ISO đặt (SX Chi Tieu ATTP): chỉ số nào, ≥ / ≤ bao nhiêu. App so
    tháng và lũy kế năm → Đạt / Không đạt. Văn bản mục tiêu ATTP chưa có trong app nên không có chỉ tiêu
    mặc định — Ban ISO nhập theo văn bản; chưa nhập thì báo cáo vẫn đủ bảng chỉ số.

Hàm THUẦN: không đọc DB. Test gọi thẳng.
"""

PT = "SX Chi Tieu ATTP"
CAO, THAP = "cao", "thap"              # hướng tốt của chỉ số
THANG, HIEN_TAI = "thang", "hien_tai"  # tính theo tháng / tại ngày lập
GE, LE = "≥", "≤"

# (mã, tên, đơn vị, kiểu, hướng tốt)
CHI_SO = (
    ("ty_le_luot", "Lượt kiểm hoàn tất (3 lượt / ngày sản xuất)", "%", THANG, CAO),
    ("ty_le_dung_gio", "Lượt kiểm ghi đúng khung giờ", "%", THANG, CAO),
    ("ngay_thieu_luot", "Ngày sản xuất thiếu lượt kiểm", "ngày", THANG, THAP),
    ("nhap_lai_giay", "Lượt nhập lại từ bản giấy", "lượt", THANG, THAP),
    ("su_co", "Sự cố (không tính diễn tập)", "phiếu", THANG, THAP),
    ("su_co_cao", "Sự cố mức Cao", "phiếu", THANG, THAP),
    ("su_co_dung_han", "Sự cố đóng đúng hạn", "%", THANG, CAO),
    ("khieu_nai", "Khiếu nại khách hàng", "vụ", THANG, THAP),
    ("kn_dat", "Mẫu kiểm nghiệm sản phẩm đạt", "%", THANG, CAO),
    ("xx_duyet", "Lô kiểm xuất xưởng được duyệt", "%", THANG, CAO),
    ("rework", "Phiếu rework", "phiếu", THANG, THAP),
    ("dong_vat", "Lần thấy dấu hiệu động vật gây hại", "lần", THANG, THAP),
    ("kp_dung_han", "Phiếu khắc phục hoàn thành đúng hạn", "%", THANG, CAO),
    ("tb_con_han", "Thiết bị đo còn hạn kiểm / hiệu chuẩn", "%", HIEN_TAI, CAO),
    ("kn_con_han", "Sản phẩm có kết quả kiểm nghiệm đạt còn hạn", "%", HIEN_TAI, CAO),
    ("ncc_duyet", "Nhà cung cấp đã duyệt", "%", HIEN_TAI, CAO),
)
MA = {x[0]: x for x in CHI_SO}


def la_ty_le(ma):
    return MA[ma][2] == "%"


def so_sanh_mac_dinh(ma):
    return GE if MA[ma][4] == CAO else LE


def gia_tri(v):
    """Số để so / hiển thị: tỷ lệ (tử, mẫu) → % một chữ số (mẫu 0 → None); số đếm giữ nguyên."""
    if v is None:
        return None
    if isinstance(v, (tuple, list)):
        t, m = v
        return round(t * 100.0 / m, 1) if m else None
    return v


def cong(a, b):
    """Cộng lũy kế: tỷ lệ cộng tử / mẫu, số đếm cộng thẳng; None (tháng chưa có số liệu) bỏ qua."""
    if a is None:
        return b
    if b is None:
        return a
    if isinstance(a, (tuple, list)):
        return (a[0] + b[0], a[1] + b[1])
    return a + b


def luy_ke(theo_thang, ma):
    """Lũy kế năm của một chỉ số tháng: cộng các tháng có số liệu."""
    tong = None
    for gt in theo_thang.values():
        tong = cong(tong, gt.get(ma))
    return tong


def danh_gia(gt, so_sanh, muc_tieu):
    """Đạt (True) / Không đạt (False) / chưa có số liệu (None)."""
    if gt is None or muc_tieu is None:
        return None
    return gt >= muc_tieu if so_sanh == GE else gt <= muc_tieu


def hien(v, don_vi):
    """96.7 → "96,7%"; 3 → "3"; None → "—"."""
    if v is None:
        return "—"
    s = f"{v:g}" if isinstance(v, float) else str(v)
    return s.replace(".", ",") + ("%" if don_vi == "%" else "")


def thang_tu_dau_nam(thang):
    """"2026-04" → ["2026-01", "2026-02", "2026-03", "2026-04"]."""
    nam, t = (int(x) for x in str(thang)[:7].split("-"))
    return [f"{nam}-{i:02d}" for i in range(1, t + 1)]


def bang(theo_thang, hien_tai, thang):
    """[{ma, ten, don_vi, kieu, huong, thang: {YYYY-MM: số}, ky, nam}] — bảng chỉ số của báo cáo.
    `theo_thang` = {YYYY-MM: {mã: giá trị thô}}; `hien_tai` = {mã: giá trị thô} (tại ngày lập)."""
    cac = thang_tu_dau_nam(thang)
    ra = []
    for ma, ten, dv, kieu, huong in CHI_SO:
        if kieu == THANG:
            tt = {t: gia_tri((theo_thang.get(t) or {}).get(ma)) for t in cac}
            ky, nam = tt.get(thang), gia_tri(luy_ke({t: theo_thang.get(t) or {} for t in cac}, ma))
        else:
            tt, ky = {}, gia_tri(hien_tai.get(ma))
            nam = ky
        ra.append({"ma": ma, "ten": ten, "don_vi": dv, "kieu": kieu, "huong": huong, "thang": tt, "ky": ky,
                   "nam": nam})
    return ra


def chi_tieu(ds, bang_cs):
    """Đánh giá từng chỉ tiêu (đang dùng) theo tháng báo cáo và lũy kế năm."""
    theo = {x["ma"]: x for x in bang_cs}
    ra = []
    for c in ds:
        if c.get("ngung") or c.get("chi_so") not in theo:
            continue
        cs = theo[c["chi_so"]]
        ss = c.get("so_sanh") or so_sanh_mac_dinh(c["chi_so"])
        mt = c.get("muc_tieu")
        ra.append(dict(c, ten=c.get("ten") or cs["ten"], so_sanh=ss, don_vi=cs["don_vi"], kieu=cs["kieu"],
                       ky=cs["ky"], nam=cs["nam"], dat_ky=danh_gia(cs["ky"], ss, mt),
                       dat_nam=danh_gia(cs["nam"], ss, mt)))
    return ra
