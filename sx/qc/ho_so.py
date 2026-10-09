"""Danh mục hồ sơ cho đoàn đánh giá (W27, D149).

Ban ISO giữ một DANH MỤC: mỗi dòng một hồ sơ / văn bản — mã, tên, nhóm, căn cứ pháp lý, nằm ở đâu
(app tự lập / tệp scan đính kèm / bản giấy), hạn. App gắn cờ:
  · Đỏ  — chỗ đoàn sẽ ghi lỗi: văn bản hết hạn; bắt buộc mà chưa có bản scan; mảng hồ sơ trên app đang
          đèn Đỏ ở Tổng quan ATTP (quá hạn, chưa xử lý…); sản phẩm chưa có số tự công bố.
  · Vàng — cần xem trước khi đoàn tới: sắp hết hạn (60 ngày); văn bản đã có bản thay thế mà chưa ngừng;
          mảng hồ sơ đèn Vàng; sản phẩm thiếu TCCS, hoặc TCCS chưa có văn bản ban hành trong danh mục.
Rồi đóng GÓI ZIP cho đoàn: mục lục (cờ, căn cứ, chỗ tìm) + bản in các biểu mẫu app lập trong kỳ + tệp scan.

Nguồn pháp lý đổi 08/10/2026: CV 21/CV-HGC thay CV 10; TCCS 01 theo QĐ 11; TCCS 03 theo QĐ 12 — patch
d149 tạo sẵn các dòng này. Công cụ lập danh mục bản gốc (ngoài app) không có trong repo, nên danh mục còn
lại Ban ISO nhập trên màn Hồ sơ đánh giá.

Hàm THUẦN: không đọc DB. Test gọi thẳng.
"""

import re
import unicodedata
from datetime import date, timedelta

PT = "SX Ho So Danh Muc"
DO, VANG = "do", "vang"
APP, TEP, GIAY = "App lập", "Tệp đính kèm", "Bản giấy"
NGUON = (APP, TEP, GIAY)
NHOM = ("Pháp lý", "Sản phẩm", "Hệ thống quản lý", "Điều kiện nhà xưởng (PRP)", "Kiểm soát sản xuất",
        "Nhà cung cấp, nguyên liệu", "Truy xuất, sự cố, khiếu nại", "Thiết bị đo", "Khác")
SAP_HET = 60            # ngày — văn bản sắp hết hạn thì cờ Vàng
TOI_DA_THANG = 24       # gói zip tối đa chừng này tháng

# Biểu mẫu app tự lập: mã → (tên, mảng ở Tổng quan ATTP — đèn của mảng là cờ của hồ sơ; None = không có đèn)
BIEU_MAU = {
    "BM.08.01": ("Vòng kiểm hằng ngày", "vong_kiem"),
    "BM.08.02": ("Sổ phiếu sự cố", "su_co"),
    "BM.01.07": ("Phiếu hành động khắc phục", "khac_phuc"),
    "BM.08.03": ("Nhật ký cát rang", "cat"),
    "BM.08.04": ("Kiểm tra xuất xưởng theo lô", "xuat_xuong"),
    "BM.08.05": ("Sổ giặt vải ủ", "vai_u"),
    "BM.11.01": ("Sổ khiếu nại khách hàng", "khieu_nai"),
    "BM.15.01": ("Phiếu rework", "rework"),
    "BM.06.01": ("Danh mục thiết bị sản xuất và thiết bị đo", "thiet_bi"),
    "BM.06.02": ("Kiểm tra đồng hồ nhiệt", "thiet_bi"),
    "BM.06.03": ("Kiểm tra nam châm", "thiet_bi"),
    "BM.06.04": ("Kiểm tra lưới sàng, rây", "thiet_bi"),
    "KH.KN.01": ("Kế hoạch kiểm nghiệm", "kiem_nghiem"),
    "BM.07.02": ("Danh sách nhà cung cấp được duyệt", "ncc"),
    "BM.07.03": ("Sổ kiểm tra chất lượng vật tư, nguyên liệu nhập vào", "ncc"),
    "BM.09.01": ("Kiểm tra xe", "kiem_xe"),
    "BM.PRP.03": ("Động vật gây hại — tuần", "dong_vat"),
    "BM.PRP.01": ("Động vật gây hại — tháng", "dong_vat"),
    "BM.02.04": ("Diễn tập truy xuất (phụ lục)", "truy_xuat"),
    "SLM": ("Sổ lưu mẫu sản phẩm", "luu_mau"),
    "HUY_MAU": ("Biên bản huỷ mẫu lưu", "luu_mau"),
    "TU_CONG_BO": ("Danh mục sản phẩm tự công bố", None),
    "BC.THANG": ("Báo cáo ATTP tháng, chỉ tiêu ATTP", None),
    # W42 (D171): thư viện tài liệu — app tự lập BM.01.02 / BM.01.03; BM.01.13 theo đợt ban hành trong kỳ.
    "BM.01.02": ("Danh mục tài liệu nội bộ", "tai_lieu"),
    "BM.01.03": ("Danh mục tài liệu bên ngoài", "tai_lieu"),
    "BM.01.13": ("Biên bản phổ biến tài liệu, danh sách phân phối", "tai_lieu"),
    # W43 (D172): sổ ghi theo dòng (SX So) — bản in theo tháng (Ghi theo dòng) / danh mục hiện hành (Danh mục).
    "BM.06.05": ("Sổ bảo dưỡng, sửa chữa thiết bị", "thiet_bi"),
    "BM.PRP.06": ("Sổ theo dõi khách, nhà thầu vào xưởng", "so_khac"),
    "BM.03.01": ("Sổ quản lý thiết bị PCCC", "so_khac"),
    "BM.03.02": ("Sổ theo dõi tình hình phát sinh dịch bệnh", "so_khac"),
    "BM.03.03": ("Sổ quản lý thiết bị kiểm định an toàn", "so_khac"),
    # W44 (D173): danh mục có hạn (SX So kiểu Danh mục — in danh mục hiện hành), phiếu đánh giá nhà cung cấp (phiếu
    # đã duyệt trong kỳ), chính danh mục hồ sơ này (trong gói zip là tệp 00-MUC-LUC.html).
    "BM.PRP.04": ("Danh mục hóa chất", "so_khac"),
    "BM.PRP.05": ("Danh mục kính, nhựa giòn", "so_khac"),
    "BM.PRP.07": ("Danh sách theo dõi khám sức khỏe, tập huấn kiến thức ATTP", "so_khac"),
    "BM.05.01": ("Bảng xác định các bên quan tâm", "so_khac"),
    "BM.05.02": ("Bảng xác định rủi ro và kế hoạch kiểm soát rủi ro", "so_khac"),
    "BM.07.01": ("Phiếu đánh giá nhà cung cấp", "ncc"),
    "BM.01.04": ("Danh mục hồ sơ", None),
}
MUC_LUC = "BM.01.04"        # dòng này trong gói = tệp 00-MUC-LUC.html


def _d(x):
    if isinstance(x, date):
        return x
    y, m, d = str(x)[:10].split("-")
    return date(int(y), int(m), int(d))


def ngay_vn(x):
    return _d(x).strftime("%d/%m/%Y")


def chuan_ma(s):
    """So khớp mã văn bản: bỏ khoảng trắng, chữ hoa — "CV 10" ≡ "cv10"."""
    return re.sub(r"\s+", "", str(s or "")).upper()


def _co_mang(x, den_mang):
    """Cờ từ đèn của mảng ở Tổng quan ATTP — kèm việc treo đầu tiên làm lý do."""
    mang = BIEU_MAU.get(x.get("bieu_mau") or "", (None, None))[1]
    t = (den_mang or {}).get(mang) if mang else None
    if not t or t.get("den") not in (DO, VANG):
        return []
    viec = "; ".join(n["tieu_de"] for n in (t.get("nhac") or [])[:2])
    return [(t["den"], f"Tổng quan ATTP — {t.get('ten', mang)} đang "
                       f"{'Đỏ' if t['den'] == DO else 'Vàng'}" + (f": {viec}" if viec else ""))]


def _co_san_pham(san_pham, ma_co):
    """Bản tự công bố: số công bố, TCCS từng sản phẩm (W28) + văn bản ban hành TCCS có trong danh mục."""
    ra = []
    thieu_cb = [s for s in san_pham if not (s.get("so_cong_bo") or "").strip()]
    if thieu_cb:
        ra.append((DO, f"{len(thieu_cb)} sản phẩm chưa có số tự công bố: "
                       + ", ".join(s.get("ten_san_pham") or s["name"] for s in thieu_cb[:5])))
    thieu_tc = [s for s in san_pham if not (s.get("tccs") or "").strip()]
    if thieu_tc:
        ra.append((VANG, f"{len(thieu_tc)} sản phẩm chưa ghi TCCS áp dụng: "
                         + ", ".join(s.get("so_cong_bo") or s["name"] for s in thieu_tc[:5])))
    khong_vb = sorted({s["tccs"].strip() for s in san_pham if (s.get("tccs") or "").strip()
                       and chuan_ma(s["tccs"]) not in ma_co})
    if khong_vb:
        ra.append((VANG, f"{', '.join(khong_vb)} chưa có trong danh mục (văn bản ban hành TCCS)"))
    return ra


def gan_co(ds, hom_nay, den_mang=None, san_pham=()):
    """{ds: [dòng + co, ly_do: [{muc, nd}]], dem: {do, vang}} — dòng theo thứ tự nhóm, thứ tự, mã.

    `ds` = các dòng danh mục; `den_mang` = {mã mảng: thẻ Tổng quan ATTP}; `san_pham` = sản phẩm tự công
    bố còn sản xuất [{name, ten_san_pham, so_cong_bo, tccs}]."""
    nay = _d(hom_nay)
    con = [x for x in ds if not x.get("ngung")]
    ma_co = {chuan_ma(x.get("ma")) for x in con}
    # Văn bản cũ đã có bản thay thế (CV 10 → CV 21): dòng cũ còn để "đang dùng" là đoàn đọc nhầm căn cứ.
    bi_thay = {}
    for x in con:
        if (x.get("thay_the") or "").strip():
            bi_thay.setdefault(chuan_ma(x["thay_the"]), []).append(x.get("ma"))
    ra = []
    for x in ds:
        ly = []
        if not x.get("ngung"):
            if x.get("het_han"):
                con_ngay = (_d(x["het_han"]) - nay).days
                if con_ngay < 0:
                    ly.append((DO, f"Hết hạn {ngay_vn(x['het_han'])}"))
                elif con_ngay <= SAP_HET:
                    ly.append((VANG, f"Sắp hết hạn {ngay_vn(x['het_han'])} (còn {con_ngay} ngày)"))
            if x.get("nguon") == TEP and not x.get("tep"):
                ly.append((DO if x.get("bat_buoc") else VANG, "Chưa có bản scan đính kèm"))
            if x.get("nguon") == GIAY and not (x.get("noi_luu") or "").strip():
                ly.append((VANG, "Chưa ghi nơi lưu bản giấy"))
            if x.get("nguon") == APP:
                ly += _co_mang(x, den_mang)
                if x.get("bieu_mau") == "TU_CONG_BO":
                    ly += _co_san_pham(list(san_pham or ()), ma_co)
            moi = [m for m in bi_thay.get(chuan_ma(x.get("ma")), []) if chuan_ma(m) != chuan_ma(x.get("ma"))]
            if moi:
                ly.append((VANG, f"Đã có văn bản thay thế: {', '.join(moi)} — đánh dấu Ngừng"))
        muc = DO if any(m == DO for m, _l in ly) else (VANG if ly else None)
        ra.append(dict(x, co=muc, ly_do=[{"muc": m, "nd": l} for m, l in sorted(ly, key=lambda t: t[0] != DO)]))
    thu = {n: i for i, n in enumerate(NHOM)}
    ra.sort(key=lambda x: (thu.get(x.get("nhom"), len(NHOM)), int(x.get("thu_tu") or 0), str(x.get("ma") or "")))
    return {"ds": ra, "dem": {DO: sum(1 for x in ra if x["co"] == DO), VANG: sum(1 for x in ra if x["co"] == VANG)}}


# ── Kỳ của gói zip ────────────────────────────────────────────────────────────────────────

def thang_trong(tu, den):
    """["2026-07", "2026-08", …] — các tháng chạm khoảng [tu, den]."""
    a, b = _d(tu).replace(day=1), _d(den)
    ra = []
    while a <= b:
        ra.append(f"{a.year}-{a.month:02d}")
        a = date(a.year + (a.month == 12), a.month % 12 + 1, 1)
    return ra


def nam_trong(tu, den):
    return list(range(_d(tu).year, _d(den).year + 1))


def thu_hai_trong(tu, den):
    """Thứ Hai của các tuần chạm khoảng [tu, den]."""
    a, b = _d(tu), _d(den)
    t = a - timedelta(days=a.weekday())
    ra = []
    while t <= b:
        ra.append(t)
        t += timedelta(days=7)
    return ra


def slug(s, toi_da=60):
    """Tên tệp trong zip: bỏ dấu tiếng Việt, chỉ chữ / số / . _ - (máy nào giải nén cũng đọc được)."""
    s = unicodedata.normalize("NFKD", str(s or "").replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-.")
    return s[:toi_da] or "ho-so"
