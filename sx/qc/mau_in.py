"""Đầu trang in chung (W42, D171) — khối 3 cột như giấy: tên công ty · tên biểu mẫu · mã / lần BH / ngày.

Mã, lần ban hành lấy từ thư viện tài liệu: bản Hiện hành có `ma` đúng mã, hoặc có mã đó trong bảng biểu mẫu
kèm (BM.08.05 nằm trong HD.08.02 → lần BH của HD.08.02). Tài liệu sửa đổi qua đợt ban hành là đầu trang mọi
bản in đổi theo — không phải sửa từng template. Chưa nạp thư viện / không thấy mã: trả mã và tên truyền vào,
lần BH trống (template tự điền lần BH cũ nếu có) — app chưa nạp thư viện vẫn in được.

Template gọi qua macro sx/qc/_dau_trang.html; hàm `sx_dau_trang` đăng ký vào Jinja ở hooks.py (jinja.methods).
"""

import frappe

from sx.qc import tai_lieu as TL

# Tên công ty mặc định trên đầu trang; sửa được ở SX QC Setting → "Tên công ty trên đầu trang in".
CONG_TY = "CÔNG TY CỔ PHẦN HOÀNG GIANG"
# Site THỬ có dữ liệu mẫu (cờ `sx_du_lieu_mau` trong site_config — D177). Bản ghi mẫu không mang ghi chú riêng (D179),
# nên mọi tờ in / tệp xuất của site đó mang dòng này trên đầu trang: tờ giấy rời khỏi máy vẫn tự nói nó từ đâu ra.
# Site thật không bật cờ → không bao giờ hiện.
BAN_THU = "Bản in từ site thử — có dữ liệu mẫu, không phải hồ sơ chính thức"
CO_DU_LIEU_MAU = "sx_du_lieu_mau"
TRUONG = ["name", "ma", "ten", "lan_ban_hanh", "ngay_ban_hanh"]


def ten_cong_ty():
    try:
        return (frappe.db.get_single_value("SX QC Setting", "ten_cong_ty") or "").strip() or CONG_TY
    except Exception:
        return CONG_TY


def co_du_lieu_mau():
    """Site này có bật cờ dữ liệu mẫu không (chỉ site thử — lệnh sinh dữ liệu mẫu tự chặn site thật)."""
    try:
        v = (frappe.conf or {}).get(CO_DU_LIEU_MAU)
    except Exception:
        return False
    return str(v if v is not None else "").strip().lower() in ("1", "true", "yes", "y", "co", "có")


def _ngay(x):
    s = str(x or "")[:10]
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}" if len(s) == 10 else ""


def sx_dau_trang(ma, ten=None):
    """{ma, ten, lan_ban_hanh, ngay_ban_hanh, kem, cong_ty, site_thu} — `kem` = mã tài liệu chứa biểu mẫu khi tìm
    qua bảng biểu mẫu kèm (HD.08.02 chứa BM.08.05); `site_thu` = dòng BAN_THU trên site thử, "" trên site thật."""
    ra = {"ma": ma or "", "ten": ten or "", "lan_ban_hanh": "", "ngay_ban_hanh": "", "kem": "",
          "cong_ty": ten_cong_ty(), "site_thu": BAN_THU if co_du_lieu_mau() else ""}
    if not ma:
        return ra
    try:
        tl = frappe.get_all(TL.PT, filters={"ma": ma, "trang_thai": TL.HIEN_HANH}, fields=TRUONG, limit=1)
        if not tl:
            cha = frappe.get_all("SX Tai Lieu Bieu Mau", filters={"ma": ma, "parenttype": TL.PT}, pluck="parent")
            tl = frappe.get_all(TL.PT, filters={"name": ("in", cha), "trang_thai": TL.HIEN_HANH}, fields=TRUONG,
                                order_by="thu_tu asc", limit=1) if cha else []
    except Exception:            # chưa migrate W42
        return ra
    if tl:
        x = tl[0]
        ra.update(lan_ban_hanh=x.get("lan_ban_hanh") or "", ngay_ban_hanh=_ngay(x.get("ngay_ban_hanh")),
                  kem=x.get("ma") if x.get("ma") and x.get("ma") != ma else "", ten=ten or x.get("ten") or "")
    return ra
