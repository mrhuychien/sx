"""Sổ giặt vải ủ BM.08.05 (W29, D163) — phần tính, đọc dữ liệu qua frappe.

HD.08.02 lần BH 01: vải cotton trắng / mộc bọc thùng gỗ ủ đỗ (công đoạn 5), mỗi thùng vải riêng, mã
theo thùng (thùng 01: V01-A, V01-B). Giặt, đun sôi ≥ 10 phút TÍNH TỪ LÚC NƯỚC SÔI LẠI, 1 lần/tuần vào
ngày cố định và ngay khi vải bẩn, ẩm; vải mới giặt, đun sôi trước lần dùng đầu; vải hỏng thì loại.

Mỗi việc một dòng SX Giat Vai: giặt định kỳ / giặt ngoài lịch / nhập vải mới / loại vải. Người giặt
(có thể không có tài khoản) làm, QC ghi hộ và KÝ — giặt mà đun chưa đủ 10 phút thì QC không ký được.
Trưởng Ban ISO xem cả tháng. Danh mục vải SX Vai U do QLSX / Ban ISO khai — app KHÔNG khai sẵn (C31: số
thùng, số vải HD.08.02 còn để trống); chưa khai vải nào Đang dùng thì không nhắc giặt.

Kiểm vải hằng ngày ghi ở BM.08.01 mục 5, không ghi hai nơi. Thẩm tra 3 tháng đầu (nấm men, nấm mốc bột
sau nghiền) là việc kiểm nghiệm (W35), không làm ở đây.
"""

import re
from datetime import datetime, time, timedelta

import frappe
from frappe.utils import cint, getdate

PT = "SX Giat Vai"
VAI = "SX Vai U"
CON = "SX Giat Vai Ma"
ST = "SX QC Setting"

DINH_KY, NGOAI_LICH, NHAP, LOAI = "Giặt định kỳ", "Giặt ngoài lịch", "Nhập vải mới", "Loại vải"
VIEC = (DINH_KY, NGOAI_LICH, NHAP, LOAI)
GIAT = (DINH_KY, NGOAI_LICH)
CAN_LY_DO = (NGOAI_LICH, LOAI)
DANG_DUNG, DU_PHONG, DA_LOAI = "Đang dùng", "Dự phòng", "Đã loại"
TRANG_THAI = (DANG_DUNG, DU_PHONG, DA_LOAI)
THU = ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật")

PHUT_SOI = 10          # HD.08.02 mục 6: giữ sôi ít nhất 10 phút tính từ lúc nước sôi lại
CHU_KY = 7             # mục 6: 1 lần/tuần
# Thẩm tra không đạt (mục 9) → giặt, đun sôi sau mỗi lần dùng. Một lần ủ tối đa 48 giờ, nên quá 2 ngày
# chưa giặt là đã có lần dùng bị bỏ qua.
CHU_KY_MOI_LAN = 2
CHO_KY = 1             # dòng chờ QC ký quá chừng này ngày thì nhắc
NGAY_XEM = 5           # tháng trước phải được Trưởng Ban ISO xem trước hết ngày này của tháng sau


def chuan_ma(s):
    """" v01-a " → "V01-A": mã vải so khớp không phân biệt hoa thường, khoảng trắng."""
    return re.sub(r"\s+", "", str(s or "")).upper()


def thung_cua(ma):
    """Số thùng đọc từ mã vải theo HD.08.02: "V01-A" → "01". Mã khác mẫu đó → ""."""
    m = re.match(r"^V(\d+)-", chuan_ma(ma))
    return m.group(1) if m else ""


def _phut(t):
    """Giờ trong ngày → số phút từ 0 giờ. Nhận "HH:MM[:SS]", time, timedelta (DB trả ô Time là
    timedelta). Trống / sai → None."""
    if t is None or t == "":
        return None
    if isinstance(t, timedelta):
        return int(t.total_seconds() // 60) % (24 * 60)
    if isinstance(t, (time, datetime)):
        return t.hour * 60 + t.minute
    m = re.match(r"^\s*(\d{1,2})[:hH.](\d{2})", str(t))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def so_phut(soi, vot):
    """Số phút đun sôi = giờ vớt − giờ sôi lại. Vớt qua nửa đêm thì cộng 24 giờ. Thiếu một đầu → None."""
    a, b = _phut(soi), _phut(vot)
    if a is None or b is None:
        return None
    return (b - a) % (24 * 60)


def gio(t):
    """Giờ để in: "07:05". Trống → ""."""
    p = _phut(t)
    return "" if p is None else f"{p // 60:02d}:{p % 60:02d}"


def loi_dong(x, hom_nay):
    """Lỗi chặn GHI một dòng (hàm thuần) → câu báo, hoặc None.
    `x` = {ngay, viec, vai: [mã], so_luong, ly_do, nguoi_lam, gio_soi_lai, gio_vot, cat_luc}."""
    if x.get("viec") not in VIEC:
        return "Chọn việc: giặt định kỳ / giặt ngoài lịch / nhập vải mới / loại vải."
    if not x.get("ngay"):
        return "Chọn ngày."
    if getdate(x["ngay"]) > getdate(hom_nay):
        return "Ngày ghi sổ giặt vải ủ không được sau hôm nay."
    if not x.get("vai") and cint(x.get("so_luong")) <= 0:
        return "Ghi mã vải (V01-A…) hoặc số lượng vải."
    if cint(x.get("so_luong")) < 0:
        return "Số lượng vải không được âm."
    if x.get("viec") in CAN_LY_DO and not (x.get("ly_do") or "").strip():
        return f"{x['viec']}: ghi lý do (vải ẩm, có mùi, ố, rách, dính dấu chuột, côn trùng…)."
    if not (x.get("nguoi_lam") or "").strip():
        return "Ghi tên người làm (người giặt)."
    for f, ten in (("gio_soi_lai", "giờ sôi lại"), ("gio_vot", "giờ vớt")):
        if x.get(f) not in (None, "") and _phut(x.get(f)) is None:
            return f"Ghi {ten} dạng giờ:phút (vd 07:05)."
    if x.get("cat_luc") and getdate(x["cat_luc"]) < getdate(x["ngay"]):
        return "Giờ cất vải (khô hẳn) không được trước ngày giặt."
    return None


def loi_ky(x):
    """Lỗi chặn QC KÝ một dòng (hàm thuần) → câu báo, hoặc None.

    · Giặt (định kỳ, ngoài lịch): phải có giờ sôi lại → giờ vớt đủ 10 phút, chỗ phơi, giờ cất (vải
      khô hẳn mới cất — HD.08.02 mục 7).
    · Nhập vải mới, loại vải: không bắt đun sôi; nhưng đã ghi giờ đun thì cũng phải đủ 10 phút — một lần
      đun 7 phút ghi trên sổ là bằng chứng làm sai, không phải chi tiết thừa."""
    giat = x.get("viec") in GIAT
    n = so_phut(x.get("gio_soi_lai"), x.get("gio_vot"))
    if n is None and (giat or x.get("gio_soi_lai") or x.get("gio_vot")):
        return "Chưa ghi đủ giờ sôi lại và giờ vớt — chưa ký được."
    if n is not None and n < PHUT_SOI:
        return (f"Đun sôi mới {n} phút — đun lại cho đủ {PHUT_SOI} phút tính từ lúc nước sôi lại, "
                f"ghi giờ mới rồi ký.")
    if giat and not (x.get("phoi_tai") or "").strip():
        return "Chưa ghi chỗ phơi — chưa ký được."
    if giat and not x.get("cat_luc"):
        return "Chưa ghi giờ vải khô hẳn, cất — vải còn ẩm thì không cất, chưa ký được."
    return None


def thang_qua_han_xem(hom_nay):
    """Ngày đầu của tháng ĐẦU TIÊN chưa tới hạn xem xét: tháng M phải được Trưởng Ban ISO xem trước hết
    ngày NGAY_XEM của tháng M+1. Dòng có ngày TRƯỚC mốc này mà chưa xem là quá hạn."""
    d = getdate(hom_nay)
    dau = d.replace(day=1)
    if d.day > NGAY_XEM:
        return dau
    return (dau - timedelta(days=1)).replace(day=1)


def ma_cua(ten):
    """Mã vải của các dòng sổ: {tên dòng: [mã theo thứ tự ghi]}."""
    ten = list(ten or [])
    ra = {t: [] for t in ten}
    if ten:
        for x in frappe.get_all(CON, filters={"parenttype": PT, "parent": ("in", ten)},
                                fields=["parent", "vai", "idx"], order_by="idx asc"):
            ra.setdefault(x.parent, []).append(x.vai)
    return ra


def su_kien(ma):
    """Dòng Nhập vải mới / Loại vải MỚI NHẤT (theo ngày, rồi lúc ghi) có mã `ma` — None nếu không có."""
    cha = sorted(set(frappe.get_all(CON, filters={"parenttype": PT, "vai": ma}, pluck="parent")))
    if not cha:
        return None
    ds = frappe.get_all(PT, filters={"name": ("in", cha), "viec": ("in", (NHAP, LOAI))},
                        fields=["name", "ngay", "viec", "ly_do", "creation"], order_by="ngay desc, creation desc",
                        limit=1)
    return ds[0] if ds else None


def tinh_vai(ds_ma):
    """Trạng thái danh mục của các mã theo dòng nhập / loại MỚI NHẤT trong sổ — gọi sau khi lưu, sửa, xoá
    một dòng nhập hoặc loại (ghi bù, sửa ngày, xoá dòng thì danh mục theo lại).

    · Mới nhất là Loại vải → Đã loại, ghi ngày, lý do, dòng loại.
    · Mới nhất là Nhập vải mới → vải đang Đã loại về Dự phòng (vải thay mới khâu lại đúng mã của thùng —
      HD.08.02 mục 8); ghi ngày nhập, dòng nhập. Đang dùng / Dự phòng thì giữ (QLSX đổi).
    · Không còn dòng nào → bỏ dấu loại (và ngày nhập lấy từ dòng đã mất); vải đang Đã loại về Dự phòng."""
    for ma in sorted({m for m in ds_ma if m}):
        v = frappe.db.get_value(VAI, ma, ["trang_thai", "ngay_nhap", "dong_nhap", "ngay_loai", "ly_do_loai",
                                          "dong_loai"], as_dict=True)
        if not v:
            continue
        x = su_kien(ma)
        if x and x.viec == LOAI:
            moi = {"trang_thai": DA_LOAI, "ngay_loai": str(getdate(x.ngay)), "ly_do_loai": x.ly_do or "",
                   "dong_loai": x.name}
        else:
            moi = {"ngay_loai": None, "ly_do_loai": None, "dong_loai": None, "dong_nhap": x.name if x else None}
            if v.trang_thai == DA_LOAI:
                moi["trang_thai"] = DU_PHONG
            if x:
                moi["ngay_nhap"] = str(getdate(x.ngay))
            elif v.dong_nhap:          # ngày nhập lấy từ dòng nhập vừa bị xoá / bỏ mã → không còn căn cứ
                moi["ngay_nhap"] = None
        doi = {k: g for k, g in moi.items() if str(v.get(k) or "") != str(g or "")}
        if doi:
            frappe.db.set_value(VAI, ma, doi, update_modified=False)


def cai_dat():
    """{thu_giat, noi_giat, nguoi_giat, giat_moi_lan} từ SX QC Setting — để trống được (C31)."""
    try:
        s = frappe.get_cached_doc(ST)
    except Exception:
        return {"thu_giat": "", "noi_giat": "", "nguoi_giat": "", "giat_moi_lan": 0}
    return {"thu_giat": s.get("vai_u_thu_giat") or "", "noi_giat": s.get("vai_u_noi_giat") or "",
            "nguoi_giat": s.get("vai_u_nguoi_giat") or "", "giat_moi_lan": cint(s.get("vai_u_giat_moi_lan"))}


def nhac(hom_nay):
    """Dữ liệu cho hộp nhắc QC (chữ do sx/qc/nhac.py viết). Chưa migrate → {}.

    {dang_dung, lan_cuoi, chu_ky, giat_moi_lan, thu_giat, hom_nay_la_ngay_giat, hom_nay_da_giat,
     cho_ky: [{name, ngay, viec}], chua_xem: ["YYYY-MM"]}

    Lần giặt tính chu kỳ: dòng Giặt định kỳ. Đang giặt sau mỗi lần dùng (thẩm tra không đạt) thì giặt
    ngoài lịch cũng tính — lúc đó mọi lần giặt đều là lần giặt theo quy định."""
    d = getdate(hom_nay)
    cd = cai_dat()
    giat = GIAT if cd["giat_moi_lan"] else (DINH_KY,)
    try:
        dang = frappe.db.count(VAI, {"trang_thai": DANG_DUNG})
        cuoi = frappe.get_all(PT, filters={"viec": ("in", giat), "ngay": ("<=", str(d))},
                              fields=["ngay"], order_by="ngay desc", limit=1)
        hom = frappe.get_all(PT, filters={"viec": ("in", giat), "ngay": str(d)}, pluck="name")
        cho = frappe.get_all(PT, filters={"qc_ky_luc": ("is", "not set")},
                             fields=["name", "ngay", "viec", "creation"], order_by="ngay asc")
        chua = frappe.get_all(PT, filters={"xem_luc": ("is", "not set"),
                                           "ngay": ("<", str(thang_qua_han_xem(d)))}, pluck="ngay")
    except Exception:
        return {}
    thu = cd["thu_giat"]
    return {
        "dang_dung": cint(dang),
        "lan_cuoi": str(cuoi[0].ngay) if cuoi else None,
        "chu_ky": CHU_KY_MOI_LAN if cd["giat_moi_lan"] else CHU_KY,
        "giat_moi_lan": cd["giat_moi_lan"],
        "thu_giat": thu,
        "hom_nay_la_ngay_giat": thu in THU and THU.index(thu) == d.weekday(),
        "hom_nay_da_giat": bool(hom),
        # Chờ tính từ lúc GHI (dòng ghi bù từ sổ giấy không bị nhắc ngay hôm ghi).
        "cho_ky": [{"name": x.name, "ngay": str(x.ngay), "viec": x.viec} for x in cho
                   if (d - getdate(x.creation)).days > CHO_KY],
        "chua_xem": sorted({str(x)[:7] for x in chua}),
    }
