"""Thư viện tài liệu (W42, D171) — luật dùng chung cho controller, API, bản in.

Thay sổ đăng ký Excel, thư mục bản mềm, phát bản giấy, ký nhận giấy:
  · BM.01.01 đề nghị soạn mới / sửa đổi / hủy bỏ / áp dụng (SX De Nghi Tai Lieu) — Trưởng Ban ISO xem xét,
    Giám đốc duyệt, người đề nghị không tự duyệt, khóa sau duyệt;
  · đợt ban hành = quyết định + Phụ lục 1 (tài liệu) — bấm Ban hành là đẩy bản cũ vào lịch sử, ghi bản mới,
    Hủy bỏ → Hết hiệu lực, tạo yêu cầu đọc cho người thuộc nơi nhận (Phụ lục 3);
  · BM.01.02 / BM.01.03 app tự lập từ thư viện; BM.01.13 theo đợt, có giờ "Đã đọc, hiểu" thay chữ ký (C28).
Căn cứ QT.01 phần kiểm soát tài liệu; QĐ ban hành 21/9/2026.

Không gộp với SX Ho So Danh Muc: danh mục hồ sơ là "bằng chứng cho đoàn", thư viện là "tài liệu đang hiệu
lực" — hai bên nối qua mã biểu mẫu.

Hàm thuần không đọc DB (test gọi thẳng). `nhac(hom_nay)` đọc DB, lỗi / chưa migrate → {}.
"""

import json
import os
import re
from datetime import date, datetime, timedelta

import frappe

PT = "SX Tai Lieu"
PT_NN = "SX Noi Nhan"
PT_DN = "SX De Nghi Tai Lieu"
PT_DOT = "SX Dot Ban Hanh"
PT_DOC = "SX Tai Lieu Doc"

DU_THAO, HIEN_HANH, HET = "Dự thảo", "Hiện hành", "Hết hiệu lực"
TRANG_THAI = (DU_THAO, HIEN_HANH, HET)
NOI_BO, BEN_NGOAI = "Nội bộ", "Bên ngoài"
NGUON = (NOI_BO, BEN_NGOAI)
KHAC = "Khác"
BM_PM = "Biểu mẫu trên phần mềm"
TL_NGOAI = "Tài liệu bên ngoài"
LOAI = ("Sổ tay", "Chính sách", "Mục tiêu", "Quy trình", "Hướng dẫn", "Quy định", "Kế hoạch", "Kế hoạch HACCP",
        "PRP", "Sơ đồ", "Phụ lục", "Phương án", "Biểu mẫu", BM_PM, "Tờ trình", TL_NGOAI, KHAC)
HINH_THUC = ("Bản mềm", "Bản giấy", "Niêm yết", "Bản gốc + bản mềm")

# Đề nghị BM.01.01
SOAN_MOI, SUA_DOI, HUY_BO, AP_DUNG = "Soạn mới", "Sửa đổi", "Hủy bỏ", "Áp dụng tài liệu bên ngoài"
LOAI_YC = (SOAN_MOI, SUA_DOI, HUY_BO, AP_DUNG)
NHAP, CHO_XET, CHO_DUYET, DA_DUYET, TRA_LAI, HUY = "Nháp", "Chờ xem xét", "Chờ duyệt", "Đã duyệt", "Trả lại", "Hủy"
TT_DN = (NHAP, CHO_XET, CHO_DUYET, DA_DUYET, TRA_LAI, HUY)
# (trạng thái, việc) → trạng thái mới. Không có trong bảng = không được.
CHUYEN = {
    (NHAP, "gui"): CHO_XET, (TRA_LAI, "gui"): CHO_XET,
    (CHO_XET, "xem_xet"): CHO_DUYET, (CHO_XET, "tra_lai"): TRA_LAI,
    (CHO_DUYET, "duyet"): DA_DUYET, (CHO_DUYET, "tra_lai"): TRA_LAI,
    (NHAP, "huy"): HUY, (TRA_LAI, "huy"): HUY, (CHO_XET, "huy"): HUY, (CHO_DUYET, "huy"): HUY,
}
SUA_DUOC = (NHAP, TRA_LAI)          # người đề nghị sửa nội dung khi phiếu còn ở tay mình

# Đợt ban hành
DOT_NHAP, DA_BAN_HANH = "Nháp", "Đã ban hành"
BH_MOI, BH_SUA, BH_LAI, BH_HUY, BH_GIU = ("Ban hành mới", "Sửa đổi – thay thế", "Ban hành lại – thay thế",
                                          "Hủy bỏ", "Giữ nguyên")
HANH_DONG = (BH_MOI, BH_SUA, BH_LAI, BH_HUY, BH_GIU)
RA_BAN_MOI = (BH_MOI, BH_SUA, BH_LAI)          # ra bản mới → tài liệu nội bộ phải có PDF đã ký
HD_CUA_YC = {SOAN_MOI: BH_MOI, SUA_DOI: BH_SUA, HUY_BO: BH_HUY, AP_DUNG: BH_MOI}

# Bản hiện hành chỉ đổi qua API ban hành (cờ frappe.flags.sx_ban_hanh) — không sửa tay, kể cả trên Desk.
KHOA = ("lan_ban_hanh", "ngay_ban_hanh", "ngay_hieu_luc", "tep", "trang_thai", "dot_ban_hanh")
COT_LICH_SU = ("lan_ban_hanh", "ngay_ban_hanh", "ngay_hieu_luc", "het_hieu_luc_tu", "tep", "ban_scan", "dot_ban_hanh",
               "tom_tat_thay_doi")
# D176: bản scan (bản gốc đã ký, đóng dấu) của bản HIỆN HÀNH — Trưởng Ban ISO gắn / thay bất cứ lúc nào (không thuộc
# KHOA); ra bản mới thì bản scan cũ theo bản cũ vào lịch sử, bản mới chờ scan mới.
SCAN = ("ban_scan", "scan_luc", "scan_boi")

NGAY_NHAC_DOC = 7       # đợt ban hành quá chừng này ngày mà còn người chưa xác nhận đọc
NGAY_NHAC_DN = 7        # đề nghị chờ xem xét / duyệt quá chừng này ngày
THANG_SOAT_XET = 12     # tài liệu bên ngoài: QT.01 — soát xét ít nhất 1 lần / năm
ROUTE = "#/tailieu"

# Mã biểu mẫu / tài liệu có màn ghi trên app → route. Bấm một biểu mẫu trong thư viện là sang màn ghi.
# Mã không có ở đây là biểu mẫu giấy.
MAN_APP = {
    "BM.01.01": "#/tailieu/denghi", "BM.01.02": ROUTE, "BM.01.03": ROUTE, "BM.01.13": "#/tailieu/banhanh",
    "BM.01.07": "#/qc/khacphuc", "BM.01.12": "#/qc/baocao", "BM.02.04": "#/qc/truyxuat",
    "BM.06.01": "#/qc/thietbi", "BM.06.02": "#/qc/thietbi", "BM.06.03": "#/qc/thietbi", "BM.06.04": "#/qc/thietbi",
    "BM.07.03": "#/qc/tiepnhan", "BM.08.01": "#/qc", "BM.08.02": "#/qc/incidents", "BM.08.03": "#/qc/cat",
    "BM.08.04": "#/qc/xuatxuong", "BM.08.05": "#/qc/vaiu", "BM.09.01": "#/qc/kiemxe", "BM.11.01": "#/qc/khieunai",
    "BM.15.01": "#/qc/rework", "SLM": "#/qc/luumau", "BM.PRP.01": "#/qc/dvgh", "BM.PRP.03": "#/qc/dvgh",
    "KH.KN.01": "#/qc/kiemnghiem", "PLK": "#/ghiso", "BCSX": "#/ghiso",
}
# C25: biểu mẫu chỉ có trên phần mềm (không có mẫu giấy) — vào thư viện và BM.01.02, trỏ tới màn app.
BIEU_MAU_PM = (("PLK", "Phiếu theo dõi sản lượng sản xuất (phiếu lương công nhân)"),
               ("BCSX", "Báo cáo sản lượng sản xuất"))
NHOM_PM = "QT.08 Quản lý sản xuất"


# ── Chuẩn hoá dữ liệu nạp ────────────────────────────────────────────────────────────────────

def ngay_seed(s):
    """'21/9/2026' → '2026-09-21'; '—', '' → None."""
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$", str(s or ""))
    return f"{int(m[3]):04d}-{int(m[2]):02d}-{int(m[1]):02d}" if m else None


def lan_seed(s):
    s = " ".join(str(s or "").split())
    return "" if s in ("—", "-", "–") else s


def chuan_loai(s):
    """Loại trong sổ đăng ký → Select: 'Biểu mẫu/Danh mục' → Biểu mẫu, 'Quy trình + biểu mẫu' → Quy trình…
    Không khớp loại nào ('Tài liệu', 'Tài liệu PCCC') → Khác."""
    s = " ".join(str(s or "").split())
    if s in LOAI:
        return s
    for x in sorted(LOAI, key=len, reverse=True):
        if s.startswith(x) and not s[len(x):len(x) + 1].isalnum():
            return x
    return KHAC


def ten_noi_nhan(s):
    """'Ban ISO (bản gốc)' → 'Ban ISO' (bản gốc nói ở ô hình thức)."""
    return re.sub(r"\s*\(bản gốc\)\s*$", "", " ".join(str(s or "").split()))


def hinh_thuc_seed(s):
    s = " ".join(str(s or "").split())
    return s if s in HINH_THUC else ("Bản gốc + bản mềm" if "gốc" in s.lower() else "Bản giấy")


def ma_ngoai(so_hieu):
    """Mã của tài liệu bên ngoài = số hiệu (phần trước dấu ';' — sau là cơ quan ban hành)."""
    return " ".join(str(so_hieu or "").split(";")[0].split())


def khoa_tl(x):
    """Khoá nhận ra một tài liệu giữa các lần nạp: mã; tài liệu nội bộ không mã thì 'stt:N' (dòng của sổ đăng
    ký — như Phụ lục 3 ghi)."""
    if x.get("ma"):
        return x["ma"]
    return f"{'stt' if (x.get('nguon') or NOI_BO) == NOI_BO else 'ngoai'}:{x.get('thu_tu')}"


DAI_O = 140   # ô Data / Link / Select của frappe là varchar(140): dài hơn thì frappe chặn khi lưu (D181)


def gon(s, toi_da=DAI_O, tach=" "):
    """Chuỗi ≤ toi_da ký tự cho ô Data: quá thì cắt ở dấu tách cuối cùng còn vừa, thêm '…'."""
    s = " ".join(str(s or "").split())
    if len(s) <= toi_da:
        return s
    cat = s[:toi_da - 1]
    i = cat.rfind(tach)
    return (cat[:i] if i > 0 else cat).rstrip(" ,;:–-") + "…"


def ten_va_chi_tiet(s, toi_da=DAI_O):
    """Tên trong seed → (tên ≤ toi_da cho ô Data, câu chi tiết cho ô Ghi chú — '' nếu tên vừa). "Tên: liệt kê…"
    tách ở ': ' đầu tiên (D181 — "Hồ sơ vận hành trước audit 17/9: Kế hoạch kiểm nghiệm …" dài 190 ký tự)."""
    s = " ".join(str(s or "").split())
    if len(s) <= toi_da:
        return s, ""
    dau, _x, sau = s.partition(": ")
    if sau and dau and len(dau) <= toi_da:
        return dau, f"Gồm: {sau}"
    return gon(s, toi_da), f"Tên đầy đủ: {s}"


def seed_nap():
    """Bộ tài liệu ban hành 21/9/2026 ĐI KÈM APP (D180): sổ đăng ký, BM.01.03, Phụ lục 3 — sx/qc/seed/. Trước D180
    Ban ISO phải tự tìm và chọn 3 tệp .json này trên máy; giờ màn Nạp bộ chỉ còn một nút."""
    goc = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed")

    def doc(ten):
        with open(os.path.join(goc, ten), encoding="utf-8") as f:
            return json.load(f)

    return {"tai_lieu": doc("tai_lieu.json"), "ngoai": doc("tai_lieu_ngoai.json"), "phan_phoi": doc("phan_phoi.json")}


def ke_hoach_nap(seed_tl, seed_ngoai=None, seed_pp=None):
    """Seed (sổ đăng ký 21/9/2026, BM.01.03, Phụ lục 3) → việc phải làm, chưa đụng DB.

    {tai_lieu: [...], anh: [...], dot: {...} | None, ho_so_dot: [...], ho_so: [...], noi_nhan: [...],
     phan_phoi: {khoá tài liệu: [nơi nhận]}, loi: [...]}"""
    tl, anh, ho_so_dot, ho_so, loi = [], [], [], [], []
    dot = None
    for x in seed_tl or []:
        k = x.get("kieu_nap")
        if k == "tai_lieu":
            tl.append({
                "ma": (x.get("ma_chuan") or "").strip(), "ten": " ".join(str(x.get("ten") or "").split()),
                "loai": chuan_loai(x.get("loai")), "nguon": NOI_BO, "thu_muc": x.get("thu_muc") or "",
                "nhom_thu_muc": x.get("nhom_thu_muc") or "", "thu_tu": int(x.get("stt") or 0),
                "lan_ban_hanh": lan_seed(x.get("lan_ban_hanh")), "ngay_ban_hanh": ngay_seed(x.get("ngay_ban_hanh")),
                "ngay_hieu_luc": ngay_seed(x.get("ngay_hieu_luc")), "tep_goc": x.get("tep") or "",
                "hanh_dong": x.get("trang_thai") if x.get("trang_thai") in HANH_DONG else BH_GIU,
                "ghi_chu": x.get("ghi_chu") or "", "can_xac_nhan": 1,
                "ma_bieu_mau": [{"ma": m, "man_app": MAN_APP.get(m, "")} for m in (x.get("ma_bieu_mau_kem") or [])]})
        elif k == "anh":
            anh.append({"gan_vao": (x.get("gan_vao") or "").strip(), "tep_goc": x.get("tep") or "",
                        "mo_ta": " ".join(str(x.get("ten") or "").split())})
        elif k == "dot":
            dot = {"ten": x.get("ten") or "", "ngay_ban_hanh": ngay_seed(x.get("ngay_ban_hanh")),
                   "ngay_hieu_luc": ngay_seed(x.get("ngay_hieu_luc")), "tep_goc": x.get("tep") or "",
                   "ghi_chu": x.get("ghi_chu") or ""}
        elif k == "ho_so_dot":
            ho_so_dot.append({"tep_goc": x.get("tep") or "", "mo_ta": " ".join(str(x.get("ten") or "").split())})
        elif k == "ho_so":
            ten, chi_tiet = ten_va_chi_tiet(x.get("ten"))
            ho_so.append({"ten": ten, "chi_tiet": chi_tiet, "tep_goc": x.get("tep") or "",
                          "ngay": ngay_seed(x.get("ngay_ban_hanh"))})
        else:
            loi.append(f"Dòng {x.get('stt')}: kiểu nạp lạ '{k}' — bỏ qua")
    for ma, ten in BIEU_MAU_PM:
        tl.append({"ma": ma, "ten": ten, "loai": BM_PM, "nguon": NOI_BO, "thu_muc": "", "nhom_thu_muc": NHOM_PM,
                   "thu_tu": 0, "lan_ban_hanh": "", "ngay_ban_hanh": None, "ngay_hieu_luc": None, "tep_goc": "",
                   "hanh_dong": BH_GIU, "ghi_chu": "Chỉ có trên phần mềm, không có mẫu giấy (C25).",
                   "can_xac_nhan": 0, "ma_bieu_mau": [{"ma": ma, "man_app": MAN_APP.get(ma, "")}]})
    ngoai = seed_ngoai or {}
    # Lần soát xét = ngày cập nhật của bản BM.01.03 đã nạp ("…, cập nhật 21/9/2026"); không ghi thì để trống.
    m = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", str(ngoai.get("nguon") or ""))
    soat = ngay_seed(m[1]) if m else None
    nhom_ngoai = {}           # nhóm theo thứ tự xuất hiện → "A. …", "B. …" như BM.01.03 giấy
    for x in ngoai.get("ds") or []:
        n = " ".join(str(x.get("nhom") or "").split())
        if n not in nhom_ngoai:
            nhom_ngoai[n] = n if re.match(r"^[A-H]\. ", n) else f"{'ABCDEFGH'[len(nhom_ngoai) % 8]}. {n}"
        tl.append({"ma": ma_ngoai(x.get("so_hieu_co_quan")), "ten": " ".join(str(x.get("ten") or "").split()),
                   "loai": TL_NGOAI, "nguon": BEN_NGOAI, "thu_muc": "", "nhom_thu_muc": nhom_ngoai[n],
                   "thu_tu": int(x.get("stt") or 0), "lan_ban_hanh": "", "ngay_ban_hanh": None, "ngay_hieu_luc": None,
                   "tep_goc": "", "hanh_dong": BH_GIU, "ghi_chu": "", "can_xac_nhan": 0, "ma_bieu_mau": [],
                   "so_hieu_co_quan": x.get("so_hieu_co_quan") or "", "noi_dung_ap_dung": x.get("noi_dung_ap_dung") or "",
                   "dan_chieu": x.get("dan_chieu") or "", "bo_phan_quan_ly": x.get("bo_phan") or "",
                   "ngay_soat_xet": soat})
    # Mã trùng → báo, giữ dòng đầu (mã phải duy nhất).
    gap, con = set(), []
    for x in tl:
        if x["ma"] and x["ma"] in gap:
            loi.append(f"Mã {x['ma']} trùng — bỏ dòng '{x['ten']}'")
            continue
        gap.add(x["ma"])
        con.append(x)
    tl = con
    noi_nhan, phan_phoi = [], {}
    for i, x in enumerate((seed_pp or {}).get("ds") or [], 1):
        ten = ten_noi_nhan(x.get("noi_nhan"))
        vai = [v for v in (x.get("vai") or []) if v and v != "*"]
        noi_nhan.append({"ten": ten, "vai": vai, "moi_nguoi": 1 if "*" in (x.get("vai") or []) else 0,
                         "hinh_thuc": hinh_thuc_seed(x.get("hinh_thuc")), "thu_tu": i})
        for khoa in tim_phan_phoi(x.get("tai_lieu") or [], tl, loi, ten):
            phan_phoi.setdefault(khoa, []).append(ten)
    ten_nn = {x["ten"] for x in noi_nhan}
    for x in tl:            # tài liệu bên ngoài: bộ phận quản lý là nơi nhận (khi trùng tên nơi nhận)
        bp = " ".join(str(x.get("bo_phan_quan_ly") or "").split())
        if x["nguon"] == BEN_NGOAI and bp in ten_nn and bp not in phan_phoi.get(khoa_tl(x), []):
            phan_phoi.setdefault(khoa_tl(x), []).append(bp)
    return {"tai_lieu": tl, "anh": anh, "dot": dot, "ho_so_dot": ho_so_dot, "ho_so": ho_so, "noi_nhan": noi_nhan,
            "phan_phoi": phan_phoi, "loi": loi}


def tim_phan_phoi(ma_ds, tl, loi=None, noi=""):
    """Danh sách mã ở Phụ lục 3 → khoá tài liệu. Mã tìm theo `ma` hoặc mã biểu mẫu kèm (BM.08.05 → HD.08.02);
    'stt:N' = tài liệu không mã dòng N; '*' = toàn bộ."""
    ra = []
    for m in ma_ds:
        m = " ".join(str(m or "").split())
        if m == "*":
            ds = [khoa_tl(x) for x in tl]
        elif m.startswith("stt:"):
            ds = [khoa_tl(x) for x in tl if x["nguon"] == NOI_BO and not x["ma"] and str(x["thu_tu"]) == m[4:]]
        else:
            ds = [khoa_tl(x) for x in tl if x["ma"] == m] or [
                khoa_tl(x) for x in tl if any(b["ma"] == m for b in x.get("ma_bieu_mau") or [])]
        if not ds and loi is not None:
            loi.append(f"Phụ lục 3 — {noi}: không tìm thấy tài liệu '{m}'")
        ra += [k for k in ds if k not in ra]
    return ra


# ── Quyền xem, phân phối ─────────────────────────────────────────────────────────────────────

def noi_nhan_cua(roles, ds_noi_nhan):
    """Tên các nơi nhận mà người có `roles` thuộc về (C27): role của nơi nhận, hoặc nơi nhận 'mọi tài khoản'."""
    roles = set(roles or [])
    return {x["ten"] for x in ds_noi_nhan if x.get("moi_nguoi") or roles & set(x.get("vai") or [])}


def duoc_xem(tl, cua_toi, la_iso):
    """Ban ISO, siêu quyền thấy mọi tài liệu (cả bản cũ, hết hiệu lực); người khác thấy tài liệu Hiện hành
    được phân phối cho nơi nhận của mình."""
    if la_iso:
        return True
    return tl.get("trang_thai") == HIEN_HANH and bool(set(tl.get("phan_phoi") or []) & set(cua_toi))


def nguoi_nhan(phan_phoi, ds_noi_nhan, user_cua_role, user_app):
    """User phải đọc tài liệu phân phối cho `phan_phoi`: người giữ role của nơi nhận; nơi nhận 'mọi tài
    khoản' = mọi tài khoản app (`user_app`)."""
    ra = set()
    for x in ds_noi_nhan:
        if x["ten"] not in phan_phoi:
            continue
        if x.get("moi_nguoi"):
            ra |= set(user_app)
        for r in x.get("vai") or []:
            ra |= set(user_cua_role.get(r) or ())
    return ra - {"Administrator", "Guest"}


def man_app(tl):
    """Route màn ghi của tài liệu: biểu mẫu kèm có màn app, không thì mã tài liệu."""
    for b in tl.get("ma_bieu_mau") or []:
        if b.get("man_app"):
            return b["man_app"]
    return MAN_APP.get(tl.get("ma") or "", "")


def doi_khoa(cu, moi):
    """Ô của bản hiện hành bị đổi (cu, moi: doc hoặc dict) — rỗng nếu không đổi gì bị khoá."""
    doi = [f for f in KHOA if _s(_lay(cu, f)) != _s(_lay(moi, f))]
    if _bang_ls(_lay(cu, "lich_su")) != _bang_ls(_lay(moi, "lich_su")):
        doi.append("lich_su")
    return doi


# Đợt đã ban hành: chỉ thêm hồ sơ của đợt (biên bản phổ biến có chữ ký…) và ghi chú.
KHOA_DOT = ("so_quyet_dinh", "ngay_ban_hanh", "ngay_hieu_luc", "tep_qd", "tao_yeu_cau_doc", "trang_thai",
            "ban_hanh_boi", "ban_hanh_luc")
COT_DOT = ("tai_lieu", "ma", "ten", "hanh_dong", "lan_ban_hanh_moi", "tep_moi", "de_nghi")
# Đề nghị đã gửi: nội dung chỉ sửa khi còn ở tay người đề nghị (Nháp / Trả lại).
NOI_DUNG_DN = ("loai_yeu_cau", "tai_lieu", "ma_de_xuat", "ten_de_xuat", "lan_ban_hanh", "ngay_hieu_luc", "bo_phan",
               "ngay_de_nghi", "ly_do", "noi_dung", "bo_phan_tac_dong", "tep_du_thao", "nguoi_soan_thao",
               "ngay_hoan_thanh")


def doi_dot(cu, moi):
    doi = [f for f in KHOA_DOT if _s(_lay(cu, f)) != _s(_lay(moi, f))]
    bang = [[tuple(_s(_lay(r, c)) for c in COT_DOT) for r in (_lay(d, "ds") or [])] for d in (cu, moi)]
    if bang[0] != bang[1]:
        doi.append("ds")
    return doi


def doi_noi_dung(cu, moi):
    return [f for f in NOI_DUNG_DN if _s(_lay(cu, f)) != _s(_lay(moi, f))]


def _lay(d, f):
    return d.get(f) if hasattr(d, "get") else getattr(d, f, None)


def _s(v):
    return str(v)[:10] if isinstance(v, (date, datetime)) else str(v or "")


def _bang_ls(ds):
    return [tuple(_s(_lay(r, c)) for c in COT_LICH_SU) for r in (ds or [])]


# ── Ban hành ─────────────────────────────────────────────────────────────────────────────────

def ban_moi(tl, muc, dot):
    """Một dòng đợt áp lên tài liệu → (dòng lịch sử thêm | None, ô cập nhật). Hàm thuần.

    Ra bản mới (mới / sửa đổi / ban hành lại): bản đang hiện hành (nếu có) vào lịch sử, hết hiệu lực từ ngày
    hiệu lực của đợt; bản mới lấy lần BH, PDF của dòng, ngày của đợt. Hủy bỏ: bản đang có vào lịch sử, tài liệu
    Hết hiệu lực (giữ thông tin bản cuối để tra). Giữ nguyên: không đổi gì.
    Bản scan (D176) đi theo BẢN của nó: vào lịch sử cùng bản cũ; bản mới để trống chờ scan bản mới đã ký."""
    hd = _lay(muc, "hanh_dong")
    if hd == BH_GIU:
        return None, {}
    het_tu = _lay(dot, "ngay_hieu_luc") or _lay(dot, "ngay_ban_hanh")
    co_ban = bool(_lay(tl, "tep") or _lay(tl, "lan_ban_hanh") or _lay(tl, "ngay_ban_hanh"))
    ls = None
    if co_ban and _lay(tl, "trang_thai") == HIEN_HANH:
        ls = {"lan_ban_hanh": _lay(tl, "lan_ban_hanh") or "", "ngay_ban_hanh": _lay(tl, "ngay_ban_hanh"),
              "ngay_hieu_luc": _lay(tl, "ngay_hieu_luc"), "het_hieu_luc_tu": het_tu, "tep": _lay(tl, "tep") or "",
              "ban_scan": _lay(tl, "ban_scan") or "", "dot_ban_hanh": _lay(tl, "dot_ban_hanh") or None,
              "tom_tat_thay_doi": " ".join(str(_lay(muc, "tom_tat") or hd).split())}
    if hd == BH_HUY:
        return ls, {"trang_thai": HET, "dot_ban_hanh": _lay(dot, "name")}
    return ls, {"lan_ban_hanh": _lay(muc, "lan_ban_hanh_moi") or "", "ngay_ban_hanh": _lay(dot, "ngay_ban_hanh"),
                "ngay_hieu_luc": _lay(dot, "ngay_hieu_luc") or _lay(dot, "ngay_ban_hanh"),
                "tep": _lay(muc, "tep_moi") or "", "trang_thai": HIEN_HANH, "dot_ban_hanh": _lay(dot, "name"),
                "ban_scan": "", "scan_luc": None, "scan_boi": ""}


def thieu_ban_hanh(dot, ds, nguon_cua=None):
    """Lý do chưa ban hành được đợt (rỗng = được): số QĐ, QĐ đã ký scan, mỗi dòng ra bản mới của tài liệu
    nội bộ có PDF; Sửa đổi / Hủy bỏ phải chỉ ra tài liệu; mỗi tài liệu chỉ một dòng."""
    nguon_cua = nguon_cua or {}
    loi = []
    if not (_lay(dot, "so_quyet_dinh") or "").strip():
        loi.append("Chưa ghi số quyết định.")
    if not _lay(dot, "tep_qd"):
        loi.append("Chưa tải quyết định đã ký (scan).")
    if not _lay(dot, "ngay_ban_hanh"):
        loi.append("Chưa ghi ngày ban hành.")
    if not ds:
        loi.append("Đợt chưa có tài liệu nào.")
    gap = set()
    for i, m in enumerate(ds or [], 1):
        ten = _lay(m, "ma") or _lay(m, "ten") or f"dòng {i}"
        hd = _lay(m, "hanh_dong")
        if hd not in HANH_DONG:
            loi.append(f"{ten}: hành động không hợp lệ.")
            continue
        tl = _lay(m, "tai_lieu")
        if hd != BH_MOI and not tl:
            loi.append(f"{ten}: {hd} phải chọn tài liệu.")
        if hd == BH_MOI and not tl and not (_lay(m, "ten") or "").strip():
            loi.append(f"Dòng {i}: tài liệu mới phải có tên.")
        if tl:
            if tl in gap:
                loi.append(f"{ten}: tài liệu có hai dòng trong đợt.")
            gap.add(tl)
        ngoai = nguon_cua.get(tl) == BEN_NGOAI or (not tl and _lay(m, "loai") == TL_NGOAI)
        if hd in RA_BAN_MOI and not _lay(m, "tep_moi") and not ngoai:
            loi.append(f"{ten}: thiếu PDF bản mới đã ký.")
    return loi


# ── Đề nghị BM.01.01 ─────────────────────────────────────────────────────────────────────────

def chuyen(tt, viec):
    """Trạng thái mới của đề nghị sau một việc, None = không được."""
    return CHUYEN.get((tt, viec))


def ghi_nhat_ky(cu, luc, ai, viec, y_kien=""):
    """Nối một dòng '[dd/mm/yyyy hh:mm · Họ tên · việc] ý kiến' — không sửa đè (như BM.01.07)."""
    t = luc.strftime("%d/%m/%Y %H:%M") if isinstance(luc, datetime) else str(luc)
    dong = f"[{t} · {ai} · {viec}]" + (f" {' '.join(str(y_kien).split())}" if (y_kien or "").strip() else "")
    return (cu.rstrip() + "\n" + dong) if (cu or "").strip() else dong


# ── Nhắc (mảng tai_lieu) ─────────────────────────────────────────────────────────────────────

def _d(x):
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return date.fromisoformat(str(x)[:10])


def nhac(hom_nay):
    """{chua_doc: [{dot, so, ngay, chua, tong}], de_nghi: [{name, ten, trang_thai, tu}], soat_xet: [ma],
    dot_thieu: [{dot, thieu}]} — {} khi lỗi / chưa migrate."""
    try:
        d = _d(hom_nay)
        moc = d - timedelta(days=NGAY_NHAC_DOC)
        chua_doc = []
        for x in frappe.get_all(PT_DOT, filters={"trang_thai": DA_BAN_HANH}, fields=[
                "name", "so_quyet_dinh", "ngay_ban_hanh", "ban_hanh_luc"], order_by="ngay_ban_hanh asc"):
            if not x.ban_hanh_luc or _d(x.ban_hanh_luc) > moc:
                continue
            doc = frappe.get_all(PT_DOC, filters={"dot_ban_hanh": x.name}, fields=["doc_luc"])
            chua = sum(1 for r in doc if not r.doc_luc)
            if chua:
                chua_doc.append({"dot": x.name, "so": x.so_quyet_dinh or "", "ngay": str(x.ngay_ban_hanh or ""),
                                 "chua": chua, "tong": len(doc)})
        moc_dn = d - timedelta(days=NGAY_NHAC_DN)
        de_nghi = []
        for x in frappe.get_all(PT_DN, filters={"trang_thai": ("in", [CHO_XET, CHO_DUYET])}, fields=[
                "name", "ten_de_xuat", "trang_thai", "gui_luc", "xem_xet_luc"], order_by="gui_luc asc"):
            tu = x.xem_xet_luc if x.trang_thai == CHO_DUYET and x.xem_xet_luc else x.gui_luc
            if tu and _d(tu) <= moc_dn:
                de_nghi.append({"name": x.name, "ten": x.ten_de_xuat or "", "trang_thai": x.trang_thai,
                                "tu": str(tu)[:10]})
        han_sx = d - timedelta(days=round(THANG_SOAT_XET * 30.44))
        soat_xet = [x.ma or x.ten for x in frappe.get_all(PT, filters={"nguon": BEN_NGOAI, "trang_thai": HIEN_HANH},
                                                          fields=["ma", "ten", "ngay_soat_xet"], order_by="thu_tu asc")
                    if not x.ngay_soat_xet or _d(x.ngay_soat_xet) < han_sx]
        nguon = {x.name: x.nguon for x in frappe.get_all(PT, fields=["name", "nguon"])}
        dot_thieu = []
        for x in frappe.get_all(PT_DOT, filters={"trang_thai": DOT_NHAP}, pluck="name"):
            ds = frappe.get_all("SX Dot Ban Hanh Muc", filters={"parent": x, "parenttype": PT_DOT},
                                fields=["tai_lieu", "hanh_dong", "tep_moi", "loai"])
            thieu = sum(1 for m in ds if m.hanh_dong in RA_BAN_MOI and not m.tep_moi
                        and nguon.get(m.tai_lieu) != BEN_NGOAI and not (not m.tai_lieu and m.loai == TL_NGOAI))
            if thieu:
                dot_thieu.append({"dot": x, "thieu": thieu})
        return {"chua_doc": chua_doc, "de_nghi": de_nghi, "soat_xet": soat_xet, "dot_thieu": dot_thieu}
    except Exception:
        return {}
