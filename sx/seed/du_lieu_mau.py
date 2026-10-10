"""Dữ liệu QC MẪU cho site THỬ (D177) — từ 22/9/2026 tới nay, để tập huấn, xem màn ISO, thử xuất báo cáo (D176).

KHÔNG BAO GIỜ CHẠY TRÊN SITE THẬT. Hồ sơ ISO do máy sinh ra mà nằm cạnh hồ sơ thật là hồ sơ giả: tờ in ra không khác
tờ QC ghi, đoàn kiểm tra không phân biệt được. Nên lệnh tự chặn ở hai chốt, chốt nào cũng đủ dừng:
  · site tên site1.local (site thật) → dừng;
  · site_config chưa bật `sx_du_lieu_mau` (`bench --site <site thử> set-config sx_du_lieu_mau 1`) → dừng — site chép từ
    bản sao lưu mà chưa ai bật cờ này cũng không chạy.
Mọi bản ghi mẫu do hai tài khoản mẫu ghi (qc.mau@sx.local, iso.mau@sx.local — không mật khẩu, tên hiện "… Mẫu (dữ
liệu mẫu)"), ô ghi chú / xử lý ghi "Dữ liệu mẫu (site thử)" — nhìn tờ in là biết; xoa() xoá sạch theo hai tài khoản đó.

Sinh gì (ngày làm việc thứ Hai → thứ Bảy, Chủ nhật nghỉ trừ khi chu_nhat=1):
  BM.08.01  ba lượt mỗi ngày (thứ Hai lượt Tuần thay Đầu sáng), ghi MỌI mục áp dụng, số trong ngưỡng (SX QC Setting);
            bột thứ Ba / Năm / Bảy (thứ Năm vị có lạc nếu có → B1, B2, B7); bộ mục theo PHIÊN BẢN của ngày đó (bản 1
            trước 08/10, bản 2 ngày 08/10, bản 3 từ 09/10 — tờ tháng 9 không có nam châm NC-02 lắp 06/10); Ban ISO
            xem xét các tuần đã qua (thứ Hai tuần sau)
  BM.08.02  `su_co` phiếu sự cố sinh từ lượt kiểm (mặc định 2: lưới sàng, thùng bột quá hạn) — QC ghi xử lý, ISO đóng
  BM.08.03  nhật ký cát: nhập + rang khô đưa dùng (máy chưa có cát), bổ sung mỗi 6 ngày rang, vệ sinh thùng / khay thứ
            Bảy, thay cát khi đủ số ngày tối đa (SX QC Setting); Ban ISO xem cùng lúc xem xét lượt
  BM.08.05  giặt vải ủ định kỳ mỗi tuần (ngày giặt ở SX QC Setting, trống = thứ Bảy), QC ký; Ban ISO xem tháng đã qua.
            Danh mục vải trống thì khai 4 vải mẫu V01-A, V01-B, V02-A, V02-B
  BM.08.04  lô thành phẩm của phiếu nhập kho ĐÃ DUYỆT trong kỳ: lấy mẫu lưu (sổ lưu mẫu), QC kiểm, Ban ISO duyệt —
            trước giờ thủ kho duyệt phiếu nhập (luồng thật). Lô mà hồ sơ gợi ý Không đạt thì bỏ (không bấm Đạt đè lên)
Không sinh: sản lượng (báo mẻ, phiếu kho, nhập kho — chỉ ĐỌC phiếu nhập kho để biết lô); tiếp nhận NL, kiểm xe (gắn
chứng từ thật); thiết bị đo (hạn đầu tiên 31/10/2026); động vật gây hại (chỉ ghi khi thấy dấu hiệu); sổ ghi theo dòng,
biên bản, kiểm nghiệm.

NGÀY NÀO ĐÃ CÓ THÌ THÔI: ngày đã có lượt kiểm (thật hay mẫu) không sinh lượt; sổ cát chỉ sinh TRƯỚC dòng thật đầu tiên
trong kỳ, ngày đã có dòng cát thì thôi; tuần đã có lần giặt vải, lô đã có phiếu xuất xưởng thì bỏ qua. Chạy lại không
đẻ thêm gì.

Ghi qua ĐÚNG API của màn QC (start_round → save_round → submit_round, qc_cat.ghi, qc_vaiu.ghi, xuatxuong.lap_phieu…):
dữ liệu mẫu đi qua mọi luật như QC bấm thật — thiếu ô thì không hoàn tất được, lệch ngưỡng thì ra sự cố. API đặt giờ
theo đồng hồ máy chủ lúc chạy lệnh, nên sau đó giờ bắt đầu / hoàn tất lượt, giờ ghi từng ô, giờ lập, ký, duyệt được
chỉnh về đúng ngày, trong khung giờ của lượt; cờ ghi muộn tính lại bằng chính luật của lượt. Số ngẫu nhiên theo hạt
(`hat`) + ngày: xoá đi chạy lại ra đúng số cũ.

    bench --site sx-thu.local execute sx.seed.du_lieu_mau.tao                              # XEM TRƯỚC
    bench --site sx-thu.local execute sx.seed.du_lieu_mau.tao --kwargs "{'dry_run': 0}"    # GHI
    bench --site sx-thu.local execute sx.seed.du_lieu_mau.xoa --kwargs "{'dry_run': 0}"    # XOÁ dữ liệu mẫu
Cách dựng site thử từ bản sao lưu: README, mục D177.
"""

import json
import random
import re
from datetime import date, datetime, time, timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, now_datetime

from sx.api import qc as Q
from sx.api import qc_cat as QCAT
from sx.api import qc_vaiu as QVAI
from sx.qc import cat as CAT
from sx.qc import muc as M
from sx.qc import so as SO
from sx.qc import vai_u as VU
from sx.qc import xuat_xuong as XX
from sx.qc.nguong import nguong
from sx.seed import _dry

SITE_THAT = ("site1.local",)
CO_CHO_PHEP = "sx_du_lieu_mau"         # khoá site_config bật trên site thử
TU = "2026-09-22"

QC_MAU = "qc.mau@sx.local"
ISO_MAU = "iso.mau@sx.local"
HO_MAU = "Mẫu (dữ liệu mẫu)"
# tài khoản: (tên, vai) — QC ghi cả mục đóng gói; Ban ISO xem xét, đóng sự cố, duyệt xuất xưởng (không tự duyệt)
NGUOI_MAU = {QC_MAU: ("QC", ("SX QC", "SX QC Packing")), ISO_MAU: ("Ban ISO", ("ISO Manager",))}
GHI_CHU = "Dữ liệu mẫu (site thử)"

PHAN = ("luot", "su_co", "cat", "vai", "xuat")
TEN_PHAN = {"luot": "BM.08.01 vòng kiểm", "su_co": "BM.08.02 sự cố", "cat": "BM.08.03 nhật ký cát",
            "vai": "BM.08.05 giặt vải ủ", "xuat": "BM.08.04 xuất xưởng + sổ lưu mẫu"}
CHU_NHAT = 6
BOT_THU = (1, 3, 5)                    # thứ Ba, Năm, Bảy có sản xuất bột
THU_LAC = 3                            # thứ Năm làm vị có lạc (nếu danh mục bột có)
# Phiên bản bộ mục BM.08.01 theo ngày (sx/qc/muc.py PHIEN_BAN): ngày trước mốc đầu tiên là bản 1.
PB_TU = ((date(2026, 10, 9), 3), (date(2026, 10, 8), 2))

# Giờ đi lượt: (bắt đầu sớm nhất, bắt đầu muộn nhất, (phút làm ít nhất, nhiều nhất)) — hết lượt vẫn trong khung giờ
# của lượt (sx/qc/nguong.py: Đầu sáng → 08:30, Trưa 08:30–14:00, Cuối chiều 14:00–20:00) và dưới 45 phút.
GIO = {
    M.DAU_SANG: (time(7, 0), time(7, 45), (15, 30)),
    M.TUAN: (time(6, 50), time(7, 20), (25, 40)),
    M.TRUA: (time(10, 15), time(11, 30), (15, 30)),
    M.CUOI_CHIEU: (time(15, 30), time(16, 45), (15, 30)),
}

# Sự cố mẫu: một mục Không đạt ở lượt Trưa → lượt tự sinh phiếu BM.08.02 (đúng luật su_co.py) → QC ghi xử lý → Ban ISO
# đóng hôm sau. Hai kiểu luân phiên.
HONG = (
    {"f": "luoi_sang_nguyen_ven", "v": M.KHONG_DAT,
     "xu_ly_ngay": "Dừng sàng, thay lưới sàng dự phòng, sàng lại mẻ đỗ vừa ra.",
     "nguyen_nhan": "Lưới sàng mòn, rách mép sau thời gian dùng.",
     "hanh_dong_khac_phuc": "Kiểm lưới sàng mỗi lượt đầu sáng; thay lưới định kỳ.",
     "quyet_dinh_sp": "Dùng lại sau xử lý"},
    {"f": "thung_bot_qua_han", "v": 1,
     "xu_ly_ngay": "Tách thùng bột quá 2 ngày ra khu chờ xử lý, đậy kín, báo QLSX.",
     "nguyen_nhan": "Nghiền dư so với kế hoạch trộn trong ngày.",
     "hanh_dong_khac_phuc": "Nghiền theo kế hoạch trộn; ghi ngày nghiền trên nắp thùng bột.",
     "quyet_dinh_sp": "Loại bỏ"},
)

NGUOI_LAM_CAT = "Tổ rang (mẫu)"
CAT_NHAP_KG, CAT_DUA_KG, CAT_BO_SUNG_KG = 300, 120, (8, 15)
CAT_BO_SUNG_SAU = 6                    # bổ sung cát sau mỗi chừng này ngày có rang
CAT_VE_SINH_THU = 5                    # vệ sinh thùng, khay cát thứ Bảy
VAI_MAU = (("V01-A", "01"), ("V01-B", "01"), ("V02-A", "02"), ("V02-B", "02"))
VAI_THU_MAC_DINH = 5                   # giặt vải ủ thứ Bảy khi SX QC Setting chưa đặt ngày giặt
NGAY_XEM_THANG = 3                     # Ban ISO xem sổ vải tháng trước ngày 3 tháng sau
SO_MAU_LUU = 2


class BoQua(Exception):
    """Bỏ một lô xuất xưởng (hồ sơ gợi ý Không đạt) — không phải lỗi."""


# ═══════════════════════════════════════ chốt site ═══════════════════════════════════════

def _co_bat(v):
    return str(v if v is not None else "").strip().lower() in ("1", "true", "yes", "y", "co", "có")


def chot_site():
    """Dừng nếu đây là site thật, hoặc site chưa bật cờ dữ liệu mẫu. Trả tên site."""
    site = str(getattr(frappe.local, "site", None) or "")
    if site in SITE_THAT:
        frappe.throw(_("{0} là site THẬT — lệnh dữ liệu mẫu không bao giờ chạy ở đây (hồ sơ máy sinh nằm cạnh hồ sơ "
                       "thật là hồ sơ giả). Dựng site thử từ bản sao lưu: README, mục D177.").format(site))
    if not _co_bat((frappe.conf or {}).get(CO_CHO_PHEP)):
        frappe.throw(_("Site {0} chưa bật cờ dữ liệu mẫu. CHỈ trên site thử: bench --site {0} set-config {1} 1")
                     .format(site or "?", CO_CHO_PHEP))
    return site


def _la(u):
    frappe.set_user(u)


def _nguoi_mau():
    """Tạo (nếu chưa có) hai tài khoản mẫu đủ vai. Không đặt mật khẩu: không ai đăng nhập bằng chúng được."""
    for u, (ten, vai) in NGUOI_MAU.items():
        if frappe.db.exists("User", u):
            doc = frappe.get_doc("User", u)
            co = {r.get("role") for r in doc.get("roles") or []}
            thieu = [r for r in vai if r not in co]
            if thieu:
                doc.add_roles(*thieu)
            if not cint(doc.get("enabled")):
                frappe.db.set_value("User", u, "enabled", 1)
            continue
        frappe.get_doc({"doctype": "User", "email": u, "first_name": ten, "last_name": HO_MAU, "enabled": 1,
                        "user_type": "System User", "send_welcome_email": 0,
                        "roles": [{"role": r} for r in vai]}).insert(ignore_permissions=True)


# ═══════════════════════════════════════ giờ, số ═════════════════════════════════════════

def phien_ban(d):
    """Phiên bản bộ mục BM.08.01 có hiệu lực ngày `d`."""
    d = getdate(d)
    return next((pb for tu, pb in PB_TU if d >= tu), 1)


def _luc(d, t, rd=None, phut=0):
    """datetime ngày `d` giờ `t`, cộng thêm 0…phut phút ngẫu nhiên."""
    x = datetime.combine(getdate(d), t)
    return x + timedelta(minutes=rd.randint(0, phut), seconds=rd.randint(0, 59)) if rd else x


def _da_qua(t, bay_gio):
    """Giờ mẫu không được nằm sau lúc chạy lệnh (việc hôm nay ghi buổi sáng mà giờ mẫu là buổi chiều)."""
    return min(t, bay_gio - timedelta(minutes=2))


def _gio_luot(rd, d, luot):
    sm, mu, (p1, p2) = GIO[luot]
    bd = datetime.combine(d, sm) + timedelta(
        minutes=rd.randint(0, (datetime.combine(d, mu) - datetime.combine(d, sm)).seconds // 60),
        seconds=rd.randint(0, 59))
    return bd, bd + timedelta(minutes=rd.randint(p1, p2), seconds=rd.randint(0, 59))


def _thu_hai_sau(d):
    d = getdate(d)
    return d + timedelta(days=7 - d.weekday())


def _khoang(ng):
    """Khoảng số mẫu cho mục đo — lùi vào trong ngưỡng đang đặt ở SX QC Setting (không tự sinh sự cố, không vượt trần
    vận hành)."""
    def k(lo, hi, le_lo, le_hi):
        a, b = lo + le_lo, hi - le_hi
        return (a, b) if a <= b else ((lo + hi) / 2, (lo + hi) / 2)

    return {
        "rang_nhiet_do": k(ng["rang_nhiet_min"], ng.get("rang_nhiet_max_van_hanh") or ng["rang_nhiet_min"] + 40, 6, 6),
        "rang_vong_quay": k(ng["vong_quay_min"], ng["vong_quay_max"], 0.1, 0.1),
        "b2_rang_lac_nhiet": k(ng.get("rang_lac_nhiet_min") or 150, ng.get("rang_lac_nhiet_max") or 180, 5, 5),
        "b2_rang_lac_phut": k(ng.get("rang_lac_phut_min") or 30, ng.get("rang_lac_phut_max") or 40, 2, 2),
        "b8_nhiet_han": k(ng.get("han_nhiet_min") or 150, ng.get("han_nhiet_max") or 190, 10, 10),
    }


def gia_tri(m, doc, luot, rd, kh, gio):
    """Giá trị mẫu của một mục kiểm — mọi giá trị đều đạt / trong ngưỡng. None = để trống (ô đi kèm không cần)."""
    g, k = m["goc"], m["kieu"]
    if k in ("chu", "chon_bot"):
        return None                     # vật bắt được: không có; B0 ghi ở lần lưu đầu
    if k == "chon":
        return M.DAT
    if k == "co_khong":
        return 0
    if k == "chon3":                    # B7: lượt đang làm chè thì chưa chuyển đổi; lượt sau thử nhanh âm tính
        return M.B7_KHONG if cint(doc.get("co_lac")) else M.B7_AM
    if k == "gio":
        return None if cint(doc.get("co_lac")) else gio.strftime("%H:%M:%S")
    if k == "chon_cd":
        if g == "b7_ve_sinh_sua":       # lượt sau vị có sữa: đã vệ sinh chuyển đổi
            return M.B7_KHONG if cint(doc.get("co_sua")) else M.DAT
        return M.DAT if (luot not in M.DAU_NGAY_HOAC_TUAN and rd.random() < 0.25) else M.B7_KHONG
    if g in M.DEM:
        return 0                        # đếm được 0: không thùng bột quá hạn, không trạm bẫy có dấu hiệu, không hạt thô
    if g in kh:
        lo, hi = kh[g]
        return round(rd.uniform(lo, hi), 1) if k == "so" else rd.randint(int(round(lo)), int(round(hi)))
    return None


def _bang_con(dt):
    return [f.options for f in frappe.get_meta(dt).get_table_fields()]


def _dat_gio_con(dt, name, bd, kt):
    """Dòng con (log từng ô, vật T4, sự cố của lượt…): giờ ghi rải đều từ `bd` tới `kt` theo thứ tự ghi."""
    for con in _bang_con(dt):
        ds = frappe.get_all(con, filters={"parent": name, "parenttype": dt}, fields=["name", "idx"],
                            order_by="idx asc")
        for i, r in enumerate(ds):
            t = (bd + (kt - bd) * (i + 1) / (len(ds) + 1)).replace(microsecond=0)
            v = {"creation": t, "modified": t}
            if "client_ts" in _truong(con):
                v.update(client_ts=t, server_ts=t + timedelta(seconds=1))
            frappe.db.set_value(con, r.name, v, update_modified=False)


def _truong(dt):
    return {f.fieldname for f in frappe.get_meta(dt).fields}


def _dat_gio_vet(dt, name, t):
    """Vết sửa (Version — track_changes) theo giờ mẫu, không phải giờ chạy lệnh."""
    for v in frappe.get_all("Version", filters={"ref_doctype": dt, "docname": name}, pluck="name"):
        frappe.db.set_value("Version", v, {"creation": t, "modified": t}, update_modified=False)


def _dat_gio(dt, name, tao, sua=None, them=None):
    v = {"creation": tao, "modified": sua or tao}
    v.update(them or {})
    frappe.db.set_value(dt, name, v, update_modified=False)
    _dat_gio_con(dt, name, tao, sua or tao)
    _dat_gio_vet(dt, name, sua or tao)


# ═══════════════════════════════════════ kế hoạch ════════════════════════════════════════

def _ngay(tu, den):
    d = tu
    while d <= den:
        yield d
        d += timedelta(days=1)


def _lam(d, chu_nhat):
    return cint(chu_nhat) or d.weekday() != CHU_NHAT


def _ke_hoach_luot(tu, den, hat, chu_nhat, bay_gio):
    """Ngày sinh lượt: [{ngay, luot: [(lượt, bắt đầu, hoàn tất)], bot, vi, may, hat}], ngày bỏ qua, ngày nghỉ."""
    co = {str(getdate(x)) for x in frappe.get_all(
        "SX QC Round", filters={"ngay": ("between", [str(tu), str(den)]), "docstatus": ("<", 2)}, pluck="ngay")}
    # Cờ "hôm nay có bột" QC đã đặt cho ngày (SX QC Ngay, D98) mà chưa đi lượt nào: theo cờ đó, không đặt lại.
    co_bot = {str(getdate(x.ngay)): cint(x.co_san_xuat_bot) for x in frappe.get_all(
        "SX QC Ngay", filters={"ngay": ("between", [str(tu), str(den)])}, fields=["ngay", "co_san_xuat_bot"])}
    loai_bot = Q._loai_bot()
    lac = [x["item"] for x in loai_bot if x.get("lac")]
    khong = [x["item"] for x in loai_bot if not x.get("lac")] or [x["item"] for x in loai_bot]
    ds, bo_qua, nghi = [], [], []
    for d in _ngay(tu, den):
        if not _lam(d, chu_nhat):
            nghi.append(str(d))
            continue
        if str(d) in co:
            bo_qua.append(str(d))
            continue
        rd = random.Random(f"{hat}|{d}")
        # Giờ của cả ba lượt rút trước, để số của ngày không phụ thuộc giờ chạy lệnh (hôm nay chỉ sinh lượt đã qua).
        gio = [(lt, *_gio_luot(rd, d, lt))
               for lt in (M.TUAN if d.weekday() == 0 else M.DAU_SANG, M.TRUA, M.CUOI_CHIEU)]
        bot = 1 if (loai_bot and (co_bot[str(d)] if str(d) in co_bot else d.weekday() in BOT_THU)) else 0
        vi = vi_sau = []
        if bot:
            vi = vi_sau = [khong[d.toordinal() % len(khong)]]
            if d.weekday() == THU_LAC and lac:
                vi = [lac[0]]             # sáng làm chè (có lạc), trưa đổi vị → lượt trưa thử nhanh lạc (B7)
        may = {"so_may_rang": rd.choice((1, 2, 2, 3)), "so_may_nghien": rd.choice((1, 2)),
               "so_may_goi_bot": rd.choice((1, 2)) if bot else 1}
        luot = [x for x in gio if x[2] < bay_gio]
        if luot:
            ds.append({"ngay": d, "luot": luot, "bot": bot, "vi": vi, "vi_sau": vi_sau, "may": may, "hat": f"{hat}|{d}",
                       "co_ngay": str(d) in co_bot})
    return ds, bo_qua, nghi


def _ke_hoach_su_co(ngay_ds, so):
    """{(ngày, lượt Trưa): kiểu hỏng} — rải đều trong kỳ, tránh hai ngày cuối (Ban ISO còn kịp đóng)."""
    chon = [x for x in ngay_ds[:-2] if any(lt == M.TRUA for lt, *_r in x["luot"])]
    so = min(cint(so), len(chon))
    ra = {}
    for i in range(so):
        x = chon[(i + 1) * len(chon) // (so + 1)]
        ra[(x["ngay"], M.TRUA)] = HONG[i % len(HONG)]
    return ra


def _ngay_rang(tu, den, ngay_ds):
    """Ngày có rang: ngày có lượt (đã có trong DB, hoặc sắp sinh) ghi nhiệt độ rang."""
    return sorted(set(CAT.ngay_rang(tu, den)) | {str(x["ngay"]) for x in ngay_ds})


def _ke_hoach_cat(tu, den, ngay_ds, hat, chu_nhat):
    """Các dòng nhật ký cát sẽ ghi: [{ngay, viec, …payload}], ngày dừng (trước dòng THẬT đầu tiên trong kỳ)."""
    that = frappe.get_all(CAT.PT, filters={"ngay": (">=", str(tu)), "owner": ("not in", list(NGUOI_MAU))},
                          fields=["ngay"], order_by="ngay asc", limit=1)
    dung = getdate(that[0].ngay) if that else None
    den = min(den, dung - timedelta(days=1)) if dung else den
    if den < tu:
        return [], dung
    co = {str(getdate(x)) for x in frappe.get_all(CAT.PT, filters={"ngay": ("between", [str(tu), str(den)])},
                                                  pluck="ngay")}
    rang = set(_ngay_rang(tu, den, ngay_ds))
    ncc = QCAT._ncc_cat()
    ncc = (next((x for x in ncc if cint(x.get("custom_ncc_duyet"))), None) or (ncc[0] if ncc else None))
    toi_da = CAT.toi_da()
    # Số ngày cát trong máy đã dùng tới HẾT HÔM TRƯỚC kỳ (None = máy chưa có cát); vòng dưới đếm tiếp từng ngày rang.
    dem = QCAT.hien_tai(tu - timedelta(days=1))["so_ngay"]
    ra = []
    for d in _ngay(tu, den):
        if not _lam(d, chu_nhat):
            continue
        rd = random.Random(f"{hat}|cat|{d}")
        trong = str(d) not in co          # ngày đã có dòng cát (thật hay mẫu) thì không ghi thêm
        viec = []
        if dem is None:
            if ncc:
                viec.append({"viec": CAT.NHAP, "ncc_cat": ncc.name, "khoi_luong": CAT_NHAP_KG})
            viec.append({"viec": CAT.RANG_KHO, "khoi_luong": CAT_DUA_KG, "thung": "Thùng 1",
                         "cam_quan": "Cát khô, sạch, không vón, không mùi lạ"})
            dem = 0
        elif toi_da and dem >= toi_da:
            viec.append({"viec": CAT.LOAI, "ly_do_loai": f"Đủ số ngày dùng ({dem} ngày)"})
            viec.append({"viec": CAT.RANG_KHO, "khoi_luong": CAT_DUA_KG, "thung": "Thùng 1",
                         "cam_quan": "Cát khô, sạch, không vón, không mùi lạ"})
            dem = 0
        if str(d) in rang:
            dem += 1
            if dem % CAT_BO_SUNG_SAU == 0:
                viec.append({"viec": CAT.BO_SUNG, "khoi_luong": rd.randint(*CAT_BO_SUNG_KG)})
        if d.weekday() == CAT_VE_SINH_THU:
            viec.append({"viec": CAT.VE_SINH, "ve_sinh_thung": 1, "ve_sinh_khay": 1})
        if trong:
            ra += [dict(v, ngay=str(d)) for v in viec]
    return ra, dung


def _ke_hoach_vai(tu, den, chu_nhat, bay_gio):
    """({vai_moi: [mã] | None, vai: [mã]}, [ngày giặt], [ngày bỏ qua], ghi chú)."""
    dang = frappe.get_all(VU.VAI, filters={"trang_thai": VU.DANG_DUNG}, pluck="name", order_by="name asc")
    moi = []
    if not dang:
        if frappe.db.count(VU.VAI):
            return {"vai_moi": [], "vai": []}, [], [], _("danh mục vải có vải nhưng không vải nào Đang dùng — bỏ qua")
        moi = [m for m, _t in VAI_MAU]
        dang = list(moi)
    thu = VU.cai_dat()["thu_giat"]
    thu = VU.THU.index(thu) if thu in VU.THU else VAI_THU_MAC_DINH
    giat, bo_qua = [], []
    for d in _ngay(tu, den):
        if d.weekday() != thu or not _lam(d, chu_nhat) or datetime.combine(d, time(18, 0)) >= bay_gio:
            continue
        dau = d - timedelta(days=d.weekday())
        if frappe.get_all(VU.PT, filters={"viec": ("in", list(VU.GIAT)),
                                          "ngay": ("between", [str(dau), str(dau + timedelta(days=6))])}, limit=1):
            bo_qua.append(str(d))
            continue
        giat.append(str(d))
    return {"vai_moi": moi, "vai": dang}, giat, bo_qua, ""


def _ke_hoach_xuat(tu, den):
    """Lô (sản phẩm, HSD) của phiếu nhập kho thành phẩm ĐÃ DUYỆT trong kỳ, chưa có phiếu BM.08.04 → [{item, hsd,
    so_luong, dvt, ngay}], số lô bỏ qua (đã có phiếu)."""
    try:
        ds = frappe.get_all("SX Phieu Nhap TP", filters={"docstatus": 1, "ngay": ("between", [str(tu), str(den)])},
                            fields=["name", "ngay", "duyet_luc"])
        phieu = {x.name: getdate(x.ngay) for x in ds}
        duyet = {x.name: x.get("duyet_luc") for x in ds}
    except Exception:
        return [], 0
    gom = {}
    loc = {"parenttype": "SX Phieu Nhap TP", "parent": ("in", list(phieu) or [""])}
    for r in frappe.get_all("SX Phieu Nhap TP Item", filters=loc, fields=["parent", "item", "hsd", "so_dem", "dvt"]):
        if not r.item or not r.hsd or not float(r.so_dem or 0) > 0:
            continue
        k = (r.item, str(getdate(r.hsd)))
        x = gom.setdefault(k, {"item": r.item, "hsd": k[1], "so_luong": 0.0, "dvt": r.dvt or "",
                               "ngay": phieu[r.parent], "duyet_nhap": None})
        x["so_luong"] += float(r.so_dem or 0)
        x["ngay"] = min(x["ngay"], phieu[r.parent])
        if duyet[r.parent]:
            x["duyet_nhap"] = min(x["duyet_nhap"] or get_datetime(duyet[r.parent]), get_datetime(duyet[r.parent]))
    co = XX.theo_lo(list(gom))
    ds = [x for k, x in sorted(gom.items(), key=lambda kx: (kx[1]["ngay"], kx[0])) if k not in co]
    return ds, len(gom) - len(ds)


# ═══════════════════════════════════════ ghi ═════════════════════════════════════════════

def _mot_luot(ngay, luot, bd, kt, kh, hong=None):
    """Đi một lượt như QC: mở → lưu số máy, vị bột → lưu mọi mục áp dụng → hoàn tất; rồi đặt giờ về đúng lượt.
    Trả (tên lượt, [phiếu sự cố lượt sinh ra])."""
    d = ngay["ngay"]
    rd = random.Random(f'{ngay["hat"]}|{luot}')
    name = Q.start_round(str(d), luot, co_san_xuat_bot=ngay["bot"])["name"]
    pb = phien_ban(d)
    if pb != M.PHIEN_BAN:
        # Bộ mục của NGÀY ĐÓ (D129): before_insert gắn bản hiện hành; đặt lại trước khi ghi mục nào.
        frappe.db.set_value("SX QC Round", name, "phien_ban", pb, update_modified=False)
    dau = dict(ngay["may"], ghi_chu=GHI_CHU)
    vi = ngay["vi"] if luot == ngay["luot"][0][0] else ngay["vi_sau"]
    if ngay["bot"] and vi:
        dau["san_pham_bot"] = "\n".join(vi)
    Q.save_round(name, json.dumps(dau, ensure_ascii=False), client_ts=str(bd + timedelta(minutes=1)))
    ct = Q.chi_tiet_round(name)
    doc = frappe.get_doc("SX QC Round", name)
    kinh = (ct.get("vat_kinh") or {}).get("ds") or []
    vals = {}
    for f in ct["ap_dung"]:
        if f in dau or f not in M.THEO_F:
            continue
        if f == SO.T4 and kinh:
            # T4 theo từng vật của danh mục kính, nhựa giòn BM.PRP.05 (W44): ô T4 do các vật quyết định.
            vals.update({f"{Q.VK}{v['vat']}": {"ket_qua": M.DAT} for v in kinh})
            continue
        v = gia_tri(M.THEO_F[f], doc, luot, rd, kh, bd + (kt - bd) / 2)
        if v is not None:
            vals[f] = v
    if hong and hong["f"] in ct["ap_dung"]:
        vals[hong["f"]] = hong["v"]
    Q.save_round(name, json.dumps(vals, ensure_ascii=False), client_ts=str(kt - timedelta(minutes=1)))
    su_co = [x["name"] for x in Q.submit_round(name).get("su_co") or []]
    # Giờ bắt đầu / hoàn tất là của lượt mẫu; ghi muộn tính lại bằng chính luật của lượt (khung giờ, số phút).
    doc = frappe.get_doc("SX QC Round", name)
    doc.finished_at, doc.duration_min = kt, int((kt - bd).total_seconds() // 60)
    _dat_gio("SX QC Round", name, bd, kt, {"started_at": bd, "finished_at": kt, "duration_min": doc.duration_min,
                                           "ghi_muon": cint(doc.tinh_ghi_muon())})
    for sc in su_co:
        _dat_gio("SX Su Co", sc, kt)
    return name, su_co


def _xu_ly_su_co(ten, hong, kt, bay_gio):
    """QC ghi xử lý ngay; Ban ISO đóng (quyết định sản phẩm) sáng ngày làm việc kế tiếp nếu đã tới giờ đó."""
    _la(QC_MAU)
    Q.update_incident(ten, json.dumps({k: f"[{GHI_CHU}] {hong[k]}" for k in
                                       ("xu_ly_ngay", "nguyen_nhan", "hanh_dong_khac_phuc")}, ensure_ascii=False))
    _dat_gio("SX Su Co", ten, kt, kt + timedelta(minutes=25))
    d = getdate(kt) + timedelta(days=1)
    while d.weekday() == CHU_NHAT:
        d += timedelta(days=1)
    dong = datetime.combine(d, time(9, 5))
    if dong >= bay_gio:
        return False
    _la(ISO_MAU)
    Q.close_incident(ten, quyet_dinh_sp=hong["quyet_dinh_sp"])
    _la(QC_MAU)
    _dat_gio("SX Su Co", ten, kt, dong, {"dong_ngay": dong})
    return True


def _ghi_luot(kh_luot, kh_su_co, bay_gio, kq):
    kh = _khoang(nguong())
    for ngay in kh_luot:
        d = ngay["ngay"]
        _la(QC_MAU)
        if ngay["bot"] and not ngay["co_ngay"]:
            Q.dat_co_bot(str(d), 1)        # QC bật "hôm nay có bột" đầu ngày (SX QC Ngay) như trên màn Hôm nay
            t = ngay["luot"][0][1] - timedelta(minutes=3)
            ten = frappe.db.get_value("SX QC Ngay", {"ngay": d}, "name")
            frappe.db.set_value("SX QC Ngay", ten, {"cap_nhat_luc": t, "creation": t, "modified": t},
                                update_modified=False)
        for luot, bd, kt in ngay["luot"]:
            hong = kh_su_co.get((d, luot))
            name, su_co = _mot_luot(ngay, luot, bd, kt, kh, hong)
            kq["luot"]["tao"] += 1
            if hong:
                for sc in su_co:
                    kq["su_co"]["tao"].append(sc)
                    if _xu_ly_su_co(sc, hong, kt, bay_gio):
                        kq["su_co"]["dong"] += 1
            else:
                kq["luot"]["su_co_la"] += su_co      # số mẫu trong ngưỡng mà vẫn ra sự cố: ngưỡng site lạ — báo
        frappe.db.commit()


def _xem_xet(bay_gio, hat):
    """Ban ISO xem xét lượt + nhật ký cát MẪU theo tuần — thứ Hai tuần sau, 16 giờ (như review_rounds, nhưng chỉ
    phiếu mẫu: phiếu thật trên site thử để nguyên). Tuần chưa hết thì chưa xem."""
    n = 0
    for x in frappe.get_all("SX QC Round", filters={"owner": QC_MAU, "docstatus": 1, "reviewed_on": ("is", "not set")},
                            fields=["name", "ngay"]):
        t = _luc(_thu_hai_sau(x.ngay), time(16, 0), random.Random(f"{hat}|xem|{_thu_hai_sau(x.ngay)}"), 30)
        if t < bay_gio:
            frappe.db.set_value("SX QC Round", x.name, {"reviewed_by": ISO_MAU, "reviewed_on": t},
                                update_modified=False)
            n += 1
    for x in frappe.get_all(CAT.PT, filters={"owner": QC_MAU, "xem_luc": ("is", "not set")}, fields=["name", "ngay"]):
        t = _luc(_thu_hai_sau(x.ngay), time(16, 0), random.Random(f"{hat}|xem|{_thu_hai_sau(x.ngay)}"), 30)
        if t < bay_gio:
            frappe.db.set_value(CAT.PT, x.name, {"xem_boi": ISO_MAU, "xem_luc": t}, update_modified=False)
    frappe.db.commit()
    return n


def _ghi_cat(kh_cat, bay_gio, kq):
    _la(QC_MAU)
    stt = {}
    for x in kh_cat:
        p = dict(x, nguoi_lam=NGUOI_LAM_CAT, ghi_chu=GHI_CHU)
        r = QCAT.ghi(json.dumps(p, ensure_ascii=False))
        i = stt[x["ngay"]] = stt.get(x["ngay"], -1) + 1
        t = _luc(x["ngay"], time(7, 30) if x["viec"] == CAT.NHAP else time(13, 30)) + timedelta(minutes=5 * i)
        _dat_gio(CAT.PT, r["name"], _da_qua(t, bay_gio))
        kq["cat"]["tao"] += 1
        frappe.db.commit()


def _ghi_vai(kh_vai, giat, tu, bay_gio, hat, kq):
    if kh_vai["vai_moi"]:
        _la(ISO_MAU)                     # khai danh mục vải: QLSX / Ban ISO
        for ma, thung in VAI_MAU:
            QVAI.luu_vai(json.dumps({"ma": ma, "thung": thung, "trang_thai": VU.DANG_DUNG, "moi": 1,
                                     "ngay_nhap": str(tu), "ghi_chu": GHI_CHU}, ensure_ascii=False))
            kq["vai"]["vai_tao"] += 1
        frappe.db.commit()
    cd = VU.cai_dat()
    _la(QC_MAU)
    for ngay in giat:
        d = getdate(ngay)
        rd = random.Random(f"{hat}|vai|{d}")
        soi = _luc(d, time(15, 0), rd, 15)
        vot = soi + timedelta(minutes=rd.randint(VU.PHUT_SOI + 2, VU.PHUT_SOI + 6))
        cat = _luc(d + timedelta(days=1), time(7, 30), rd, 20)
        if cat >= bay_gio:
            cat = datetime.combine(d, time(17, 45))
        r = QVAI.ghi(json.dumps({"ngay": ngay, "viec": VU.DINH_KY, "vai": kh_vai["vai"],
                                 "nguoi_lam": cd.get("nguoi_giat") or "Tổ vệ sinh (mẫu)",
                                 "phoi_tai": cd.get("noi_giat") or "Giàn phơi khu sơ chế (mẫu)",
                                 "gio_soi_lai": soi.strftime("%H:%M"), "gio_vot": vot.strftime("%H:%M"),
                                 "cat_luc": cat.strftime("%Y-%m-%d %H:%M"), "ky": 1}, ensure_ascii=False))
        _dat_gio(VU.PT, r["name"], vot + timedelta(minutes=10), cat + timedelta(minutes=5),
                 {"qc_ky_luc": cat + timedelta(minutes=5)})
        kq["vai"]["tao"] += 1
        frappe.db.commit()
    # Trưởng Ban ISO xem tháng đã qua (HD.08.02 mục 9) — chỉ dòng mẫu.
    for x in frappe.get_all(VU.PT, filters={"owner": QC_MAU, "xem_luc": ("is", "not set")}, fields=["name", "ngay"]):
        d = getdate(x.ngay)
        dau_sau = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        t = _luc(dau_sau.replace(day=NGAY_XEM_THANG), time(9, 0), random.Random(f"{hat}|xemvai|{dau_sau}"), 30)
        if t < bay_gio:
            frappe.db.set_value(VU.PT, x.name, {"xem_boi": ISO_MAU, "xem_luc": t,
                                                "xem_nhan_xet": f"Đã xem ({GHI_CHU})"}, update_modified=False)
    frappe.db.commit()


def _khoi_luong(quy_cach):
    """Khối lượng tịnh ghi trên nhãn (g) đọc từ quy cách ("Hộp 300 g", "túi 40g"); không đọc được → 100."""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:g|gr|gam|gram)\b", str(quy_cach or ""), re.IGNORECASE)
    return float(m.group(1).replace(",", ".")) if m else 100.0


def _gio_lo(lo, rd, bay_gio):
    """(lấy mẫu, QC kiểm xong, Ban ISO duyệt) — TRƯỚC lúc thủ kho duyệt phiếu nhập kho của lô: luồng thật là duyệt
    xuất xưởng rồi mới nhập kho được (chan_nhap_kho). Phiếu nhập không ghi giờ duyệt thì buổi sáng ngày nhập."""
    if lo.get("duyet_nhap"):
        duyet = get_datetime(lo["duyet_nhap"]) - timedelta(minutes=rd.randint(10, 30), seconds=rd.randint(0, 59))
    else:
        duyet = _da_qua(_luc(lo["ngay"], time(9, 0), rd, 30), bay_gio)
    kiem = duyet - timedelta(minutes=rd.randint(15, 40), seconds=rd.randint(0, 59))
    return kiem - timedelta(minutes=rd.randint(15, 30)), kiem, duyet


def _mot_lo(lo, hat, bay_gio):
    """Một lô: lấy mẫu lưu (nếu lô chưa có) → QC lập phiếu BM.08.04, chấm A theo gợi ý hồ sơ lô, 5 mẫu B đạt, Cho
    xuất xưởng → Ban ISO duyệt. Hồ sơ lô gợi ý Không đạt → BoQua (người gọi cuộn lại cả lô)."""
    from sx.api import xuatxuong as XXA

    rd = random.Random(f"{hat}|xuat|{lo['item']}|{lo['hsd']}")
    hsd = getdate(lo["hsd"])
    lay_luc, kiem, duyet = _gio_lo(lo, rd, bay_gio)
    lay = 0
    _la(QC_MAU)
    if not XX._mau_luu(lo["item"], hsd):
        b = frappe.get_all("Batch", filters={"item": lo["item"], "expiry_date": hsd}, pluck="name",
                           order_by="creation asc", limit=1)
        lm = Q.tao_luu_mau(json.dumps({"san_pham": lo["item"], "batch": b[0] if b else "",
                                       "lo": f"HSD {hsd.strftime('%d/%m/%Y')}", "so_luong": SO_MAU_LUU,
                                       "dvt": lo["dvt"] or "hộp", "vi_tri": "Tủ mẫu lưu (mẫu)",
                                       "ngay_lay": str(lay_luc.date()), "ghi_chu": GHI_CHU}, ensure_ascii=False))
        _dat_gio("SX QC Luu Mau", lm["name"], lay_luc)
        lay = 1
    p = XXA.lap_phieu(lo["item"], str(hsd), lo["so_luong"], lo["dvt"] or None)
    hong = [r["ma"] for r in p["ds_muc"] if r.get("goi_y") == XX.KHONG_DAT]
    if hong:
        raise BoQua(_("hồ sơ lô gợi ý Không đạt ({0})").format(", ".join(hong)))
    kl = _khoi_luong(p.get("quy_cach"))
    ds = []
    for r in p["ds_muc"]:
        ma = r["ma"]
        if ma in XX.MA_A:
            g = r.get("goi_y")
            ds.append({"ma": ma, "ket_qua": g if g in (XX.DAT, XX.KAD) else (XX.KAD if ma in XX.KAD_DUOC else XX.DAT)})
        elif ma in XX.MAU_SO:
            ds.append({"ma": ma, "ket_qua": XX.DAT,
                       "mau": [f"{kl + rd.uniform(0.3, 2.5):.1f}" for _i in range(XX.SO_MAU)]})
        elif ma in XX.MA_B:
            ds.append({"ma": ma, "ket_qua": XX.DAT, "mau": [XX.D] * XX.SO_MAU})
    XXA.gui_duyet(p["name"], json.dumps({"ds_muc": ds, "ket_luan": XX.CHO_XUAT, "ghi_chu": GHI_CHU},
                                        ensure_ascii=False))
    _la(ISO_MAU)
    XXA.duyet_phieu(p["name"], 1, f"Đồng ý cho xuất xưởng ({GHI_CHU})")
    _la(QC_MAU)
    _dat_gio(XX.PT, p["name"], lay_luc + timedelta(minutes=5), duyet, {"kiem_luc": kiem, "duyet_luc": duyet})
    return lay


def _ghi_xuat(kh_xuat, hat, bay_gio, kq):
    for lo in kh_xuat:
        try:
            lay = _mot_lo(lo, hat, bay_gio)
            frappe.db.commit()
            kq["xuat"]["tao"] += 1           # đếm sau commit: lô cuộn lại không được tính
            kq["xuat"]["mau_luu"] += lay
        except BoQua as e:
            frappe.db.rollback()
            kq["xuat"]["bo"].append(f"{lo['item']} HSD {lo['hsd']}: {e}")
        except Exception as e:  # noqa: BLE001 — một lô hỏng (dữ liệu thật lạ) không chặn các lô sau
            frappe.db.rollback()
            kq["xuat"]["bo"].append(f"{lo['item']} HSD {lo['hsd']}: LỖI {e}")


# ═══════════════════════════════════════ lệnh ════════════════════════════════════════════

def _phan(phan):
    if not phan:
        return list(PHAN)
    ds = [x.strip() for x in (phan.split(",") if isinstance(phan, str) else phan) if str(x).strip()]
    la = [x for x in ds if x not in PHAN]
    if la:
        frappe.throw(_("Phần không có: {0} — chọn trong {1}.").format(", ".join(la), ", ".join(PHAN)))
    return ds


def chay(dry_run=None, tu=TU, den=None, su_co=2, phan=None, hat=177, chu_nhat=0):
    """Lập kế hoạch (đọc DB) rồi — nếu không phải xem trước — ghi. Trả kết quả để in (bao_cao) / để test đọc."""
    site = chot_site()
    xem = _dry(dry_run)
    phan = _phan(phan)
    bay_gio = now_datetime()
    tu = getdate(tu)
    den = min(getdate(den) if den else getdate(bay_gio), getdate(bay_gio))
    if tu > den:
        frappe.throw(_("Từ ngày {0} sau đến ngày {1}.").format(tu, den))
    kh_luot, bo_qua, nghi = _ke_hoach_luot(tu, den, hat, chu_nhat, bay_gio)
    if "luot" not in phan:
        kh_luot = []
    kh_su_co = _ke_hoach_su_co(kh_luot, su_co) if "su_co" in phan else {}
    kh_cat, cat_dung = _ke_hoach_cat(tu, den, kh_luot, hat, chu_nhat) if "cat" in phan else ([], None)
    kh_vai, giat, vai_bo, vai_chu = _ke_hoach_vai(tu, den, chu_nhat, bay_gio) if "vai" in phan else (
        {"vai_moi": [], "vai": []}, [], [], "")
    kh_xuat, xuat_bo = _ke_hoach_xuat(tu, den) if "xuat" in phan else ([], 0)
    kq = {
        "site": site, "xem_truoc": xem, "tu": str(tu), "den": str(den), "phan": phan,
        "luot": {"ngay": [str(x["ngay"]) for x in kh_luot], "so_luot": sum(len(x["luot"]) for x in kh_luot),
                 "ngay_bot": sum(1 for x in kh_luot if x["bot"]), "bo_qua": bo_qua, "nghi": nghi, "tao": 0,
                 "su_co_la": []},
        "su_co": {"ke_hoach": [f"{d} {l}: {h['f']}" for (d, l), h in sorted(kh_su_co.items())], "tao": [], "dong": 0},
        "cat": {"ke_hoach": [f"{x['ngay']} {x['viec']}" for x in kh_cat], "dung": str(cat_dung or ""), "tao": 0},
        "vai": {"vai_moi": kh_vai["vai_moi"], "vai": kh_vai["vai"], "ke_hoach": giat, "bo_qua": vai_bo,
                "ghi_chu": vai_chu, "tao": 0, "vai_tao": 0},
        "xuat": {"ke_hoach": [f"{x['item']} HSD {x['hsd']}" for x in kh_xuat], "da_co": xuat_bo, "tao": 0,
                 "mau_luu": 0, "bo": []},
        "xem_xet": 0, "loi": [],
    }
    if xem:
        return kq
    co_mail = getattr(frappe.flags, "mute_emails", None)
    frappe.flags.mute_emails = True      # site thử chép từ site thật: không gửi thư cho người thật
    try:
        _nguoi_mau()
        frappe.db.commit()
        for ten, viec in (("luot", lambda: _ghi_luot(kh_luot, kh_su_co, bay_gio, kq)),
                          ("cat", lambda: _ghi_cat(kh_cat, bay_gio, kq)),
                          ("xem_xet", lambda: kq.__setitem__("xem_xet", _xem_xet(bay_gio, hat))),
                          ("vai", lambda: _ghi_vai(kh_vai, giat, tu, bay_gio, hat, kq)),
                          ("xuat", lambda: _ghi_xuat(kh_xuat, hat, bay_gio, kq))):
            try:
                viec()
            except Exception as e:  # noqa: BLE001 — ngày / dòng đang dở cuộn lại; phần đã ghi giữ nguyên
                frappe.db.rollback()
                kq["loi"].append(f"{TEN_PHAN.get(ten, ten)}: {e}")
    finally:
        frappe.flags.mute_emails = co_mail
        frappe.set_user("Administrator")
    return kq


def _ngan(ds, n=8):
    ds = list(ds)
    return ", ".join(ds[:n]) + (f" … (+{len(ds) - n})" if len(ds) > n else "")


def bao_cao(kq):
    """Chữ in ra màn hình sau lệnh tao."""
    xem = kq["xem_truoc"]
    l, s, c, v, x = kq["luot"], kq["su_co"], kq["cat"], kq["vai"], kq["xuat"]
    ra = [f"DỮ LIỆU QC MẪU — site {kq['site']} — " + ("XEM TRƯỚC (chưa ghi gì)" if xem else "ĐÃ GHI"),
          f"Kỳ {kq['tu']} → {kq['den']} · tài khoản mẫu: {QC_MAU}, {ISO_MAU}"]
    if "luot" in kq["phan"]:
        ra.append(f"{TEN_PHAN['luot']}: {len(l['ngay'])} ngày, {l['so_luot']} lượt (có bột {l['ngay_bot']} ngày)"
                  + ("" if xem else f" — đã ghi {l['tao']} lượt"))
        if l["bo_qua"]:
            ra.append(f"  bỏ qua {len(l['bo_qua'])} ngày đã có lượt: {_ngan(l['bo_qua'])}")
        if l["nghi"]:
            ra.append(f"  nghỉ Chủ nhật: {_ngan(l['nghi'])}")
        if l["su_co_la"]:
            ra.append(f"  CHÚ Ý: số mẫu trong ngưỡng mà lượt vẫn sinh sự cố ({_ngan(l['su_co_la'])}) — xem lại ngưỡng "
                      f"SX QC Setting của site")
    if "su_co" in kq["phan"]:
        ra.append(f"{TEN_PHAN['su_co']}: {len(s['ke_hoach'])} phiếu ({_ngan(s['ke_hoach'], 4)})"
                  + ("" if xem else f" — đã sinh {len(s['tao'])}, Ban ISO đóng {s['dong']}"))
    if "cat" in kq["phan"]:
        dung = f" (dừng trước {c['dung']}: sổ thật đã có dòng)" if c["dung"] else ""
        ra.append(f"{TEN_PHAN['cat']}: {len(c['ke_hoach'])} dòng{dung}" + ("" if xem else f" — đã ghi {c['tao']}"))
    if "vai" in kq["phan"]:
        ra.append(f"{TEN_PHAN['vai']}: {len(v['ke_hoach'])} lần giặt ({_ngan(v['ke_hoach'], 5)})"
                  + (f" · khai {len(v['vai_moi'])} vải mẫu" if v["vai_moi"] else "")
                  + (f" · {v['ghi_chu']}" if v["ghi_chu"] else "")
                  + (f" · bỏ qua tuần đã giặt: {_ngan(v['bo_qua'], 4)}" if v["bo_qua"] else "")
                  + ("" if xem else f" — đã ghi {v['tao']}"))
    if "xuat" in kq["phan"]:
        ra.append(f"{TEN_PHAN['xuat']}: {len(x['ke_hoach'])} lô"
                  + (f" · {x['da_co']} lô đã có phiếu" if x["da_co"] else "")
                  + ("" if xem else f" — đã duyệt {x['tao']} lô, lấy {x['mau_luu']} mẫu lưu"))
        for b in x["bo"]:
            ra.append(f"  bỏ lô {b}")
    if not xem:
        ra.append(f"Ban ISO xem xét {kq['xem_xet']} lượt (tuần đã qua).")
    for e in kq["loi"]:
        ra.append(f"LỖI — {e} (phần đã ghi giữ nguyên; sửa rồi chạy lại: ngày đã có thì bỏ qua)")
    ra.append("Không sinh: sản lượng, tiếp nhận NL / kiểm xe, thiết bị đo, động vật gây hại, sổ theo dòng, biên bản.")
    if xem:
        ra.append(f"Ghi thật: bench --site {kq['site']} execute sx.seed.du_lieu_mau.tao --kwargs \"{{'dry_run': 0}}\"")
    return "\n".join(ra)


def tao(dry_run=None, tu=TU, den=None, su_co=2, phan=None, hat=177, chu_nhat=0):
    """bench execute sx.seed.du_lieu_mau.tao — gọi trần = XEM TRƯỚC; dry_run=0 thì ghi."""
    print(bao_cao(chay(dry_run=dry_run, tu=tu, den=den, su_co=su_co, phan=phan, hat=hat, chu_nhat=chu_nhat)))


# ═══════════════════════════════════════ xoá ═════════════════════════════════════════════

# Mọi loại bản ghi lệnh tao có thể sinh (owner = tài khoản mẫu). Lượt đã hoàn tất / đã xem xét không xoá được qua Desk
# (đó là luật của hồ sơ thật) — dữ liệu mẫu thì xoá thẳng bảng, kèm dòng con, vết sửa, bình luận.
XOA = ("SX QC Round", "SX Su Co", "SX Nhat Ky Cat", "SX Giat Vai", "SX Vai U", "SX Kiem Tra Xuat Xuong",
       "SX QC Luu Mau", "SX QC Ngay")


def don(dry_run=None):
    """Đếm (xem trước) / xoá mọi bản ghi của hai tài khoản mẫu, rồi xoá (hoặc khoá) hai tài khoản."""
    site = chot_site()
    xem = _dry(dry_run)
    nguoi = list(NGUOI_MAU)
    dem, tu_cat = {}, None
    for dt in XOA:
        ten = frappe.get_all(dt, filters={"owner": ("in", nguoi)}, pluck="name")
        dem[dt] = len(ten)
        if xem or not ten:
            continue
        if dt == CAT.PT:
            tu_cat = min(getdate(x) for x in frappe.get_all(dt, filters={"name": ("in", ten)}, pluck="ngay"))
        for con in _bang_con(dt):
            frappe.db.delete(con, {"parenttype": dt, "parent": ("in", ten)})
        frappe.db.delete("Version", {"ref_doctype": dt, "docname": ("in", ten)})
        frappe.db.delete("Comment", {"reference_doctype": dt, "reference_name": ("in", ten)})
        frappe.db.delete(dt, {"name": ("in", ten)})
    tk = [u for u in nguoi if frappe.db.exists("User", u)]
    khoa = []
    if not xem:
        if tu_cat:
            # Dấu "đổi nguồn" của các lần nhập cát thật sau dòng mẫu tính lại (như xoá một dòng nhập trên màn).
            from sx.qc.doctype.sx_nhat_ky_cat.sx_nhat_ky_cat import tinh_nguon

            tinh_nguon(tu_cat)
        frappe.db.commit()
        for u in tk:
            try:
                frappe.delete_doc("User", u, ignore_permissions=True, force=True)
            except Exception:  # noqa: BLE001 — còn liên kết ở đâu đó: khoá tài khoản thay vì xoá
                frappe.db.rollback()
                frappe.db.set_value("User", u, "enabled", 0)
                khoa.append(u)
        frappe.db.commit()
    return {"site": site, "xem_truoc": xem, "dem": dem, "tai_khoan": tk, "khoa": khoa}


def xoa(dry_run=None):
    """bench execute sx.seed.du_lieu_mau.xoa — gọi trần = XEM TRƯỚC (đếm); dry_run=0 thì xoá."""
    kq = don(dry_run)
    ra = [f"XOÁ DỮ LIỆU QC MẪU — site {kq['site']} — " + ("XEM TRƯỚC (chưa xoá gì)" if kq["xem_truoc"] else "ĐÃ XOÁ")]
    ra += [f"  {dt}: {n}" for dt, n in kq["dem"].items() if n]
    if not any(kq["dem"].values()):
        ra.append("  (không có bản ghi mẫu nào)")
    if kq["tai_khoan"]:
        ra.append(("Tài khoản mẫu sẽ xoá: " if kq["xem_truoc"] else "Đã xoá tài khoản mẫu: ")
                  + ", ".join(u for u in kq["tai_khoan"] if u not in kq["khoa"]))
    if kq["khoa"]:
        ra.append("Không xoá được (còn liên kết) — đã khoá: " + ", ".join(kq["khoa"]))
    if kq["xem_truoc"]:
        ra.append(f"Xoá thật: bench --site {kq['site']} execute sx.seed.du_lieu_mau.xoa --kwargs \"{{'dry_run': 0}}\"")
    print("\n".join(ra))
