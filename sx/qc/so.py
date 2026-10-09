"""Khung "Sổ" ghi theo dòng (W43, D172) — luật chung cho các sổ giấy chuyển lên app.

Một sổ = một định nghĩa SX So: mã biểu mẫu, cột như giấy (SX So Cot), vai ghi / xác nhận / chỉ xem / xem xét cuối
tháng. Mỗi lần ghi là một dòng SX So Dong — dữ liệu theo cột lưu JSON, kiểm theo định nghĩa: đúng kiểu, đủ ô bắt
buộc, đúng lựa chọn, không nhận khóa lạ. Hai kiểu sổ:
  · Ghi theo dòng (sổ sự kiện — bảo dưỡng, khách vào xưởng, dịch bệnh): người ghi sửa được TRONG NGÀY khi chưa xác
    nhận; xác nhận xong là khóa. Người xác nhận không phải người ghi. Ghi nhầm → Ngừng (có lý do), ghi dòng mới.
  · Danh mục (mỗi dòng một đối tượng — thiết bị PCCC, thiết bị kiểm định): sửa được, nhưng mọi lần sửa nối vào
    `sua_doi` (trước / sau); bỏ dòng = Ngừng, không xóa. Sửa dòng đã xác nhận → về Đã ghi, chờ xác nhận lại.
Quyền theo định nghĩa sổ cộng siêu quyền; Trưởng Ban ISO xem mọi sổ (API sx/api/qc_so.py kiểm).

Nhắc (mảng theo `mang` của sổ, chữ ở sx/qc/nhac.py): cột hạn đến / quá hạn; quá `nhac_khong_ghi_ngay` ngày không
có dòng; dòng chờ xác nhận quá 2 ngày; tháng trước chưa xem xét sau ngày 5 (sổ có `xem_cuoi_thang`).
Hàm riêng theo khóa `tinh_toan` (không chạy biểu thức người dùng gõ): `bao_duong` — BM.06.05 nối danh mục thiết bị
BM.06.01; sửa thiết bị đo / chọn "cần kiểm lại" → nhắc kiểm lại theo BM.06.02–06.04 (QT.06), máy sản xuất quá hạn
bảo dưỡng định kỳ. W44 (D173): `rr_abcd` — BM.05.02 RR = A + B + C + D, cấp độ; `suc_khoe` — BM.PRP.07 hạn khám lại
= ngày khám + 12 tháng. Danh mục kính BM.PRP.05 có vật → mục T4 lượt Tuần tích từng vật (ds_vat_kinh, t4_theo_vat).

Phần thuần (kiểm dữ liệu, quyền, khóa, tóm tắt, hạn, nhắc BM.06.05) không đọc DB — test gọi thẳng; phần đọc DB ở
cuối. Module qc: không import phần SX khác — siêu quyền do API truyền vào.
"""

import json
import math
import re
from datetime import date, datetime, timedelta

import frappe
from frappe.utils import cint, getdate

from sx.qc import muc as M
from sx.qc import thiet_bi as TBM

PT, PT_COT, PT_VAI, PT_DONG, PT_SUA, PT_XEM = ("SX So", "SX So Cot", "SX So Vai", "SX So Dong", "SX So Dong Sua",
                                               "SX So Xem")
GHI_THEO_DONG, DANH_MUC = "Ghi theo dòng", "Danh mục"
DA_GHI, DA_XAC_NHAN, NGUNG = "Đã ghi", "Đã xác nhận", "Ngừng"
KIEU = ("Data", "Date", "Datetime", "Time", "Int", "Float", "Select", "MultiSelect", "Check", "Text", "Link",
        "Attach", "User")
# Mã thẻ ở Tổng quan ATTP (= khóa của sx/qc/attp.LINH_VUC — test-so chốt khớp) + thẻ "Sổ khác".
SO_KHAC = "so_khac"
MANG = ("vong_kiem", "su_co", "khac_phuc", "khieu_nai", "xuat_xuong", "truy_xuat", "thiet_bi", "kiem_nghiem", "cat",
        "vai_u", "dong_vat", "ncc", "kiem_xe", "luu_mau", "rework", "viec_dinh_ky", "tai_lieu", "bien_ban", SO_KHAC)
ISO = "ISO Manager"
VAI_O = ("vai_ghi", "vai_xac_nhan", "vai_xem", "vai_xem_thang")
KHOA_DANH_RIENG = {"ngay", "name"}       # ô của chính dòng sổ — cột không được trùng
DAI_DATA, DAI_TEXT = 140, 2000
CHO_XAC_NHAN_NGAY = 2      # dòng chờ xác nhận quá chừng này ngày thì nhắc (md W43)
NGAY_XEM = 5               # tháng M phải được xem xét trước hết ngày 5 tháng M+1
NHAN_XEM_MAC_DINH = "Trưởng Ban ISO xem xét cuối tháng"

# DocType mà cột Link được trỏ tới: ô làm nhãn, ô so với `lua_chon` của cột, bản ghi bỏ khỏi danh sách chọn,
# `an_ma` = hiện nhãn thay cho mã (mã nhân viên HR-EMP-… không ai đọc; mã thiết bị thì in kèm như giấy).
LINK_DUOC = {
    TBM.TB: {"nhan": "ten", "loai": "loai", "bo": {"thanh_ly": 1}},
    "Employee": {"nhan": "employee_name", "loai": None, "bo": {"status": "Left"}, "an_ma": 1},     # W44: BM.PRP.07
}

# Hàm riêng có tên (định nghĩa sổ trỏ tới bằng `tinh_toan`).
BAO_DUONG, RR_ABCD, SUC_KHOE = "bao_duong", "rr_abcd", "suc_khoe"
TINH_TOAN = {
    BAO_DUONG: "Sổ bảo dưỡng, sửa chữa (BM.06.05): thiết bị theo danh mục BM.06.01; sửa thiết bị đo / chọn thiết bị "
               "cần kiểm lại → nhắc kiểm lại theo BM.06.02–06.04; máy sản xuất quá hạn bảo dưỡng định kỳ → nhắc.",
    RR_ABCD: "Bảng rủi ro (BM.05.02): RR = A + B + C + D (mỗi ô 1–4); cấp độ 1 = 12–16, cấp độ 2 = 10–11, "
             "cấp độ 3 ≤ 9.",
    SUC_KHOE: "Khám sức khỏe (BM.PRP.07): ghi ngày khám mà để trống hạn khám lại → hạn = ngày khám + 12 tháng "
              "(SSOP 5: khám 1 lần / năm).",
}
# Cột do hàm riêng tính — phiếu ghi không cho nhập, giá trị gõ tay bị tính đè.
TINH_COT = {RR_ABCD: ("rr", "cap_do")}
CAP_DO = ((12, "Cấp độ 1"), (10, "Cấp độ 2"), (0, "Cấp độ 3"))      # RR từ ngưỡng này trở lên → cấp độ
KHAM_LAI_THANG = 12
# Khóa cột mà hàm bao_duong đọc (định nghĩa trên site đổi khóa thì hàm không làm gì — không vỡ).
BD_THIET_BI, BD_LOAI, BD_KIEM_LAI = "thiet_bi", "loai", "can_hieu_chuan"
BD_SUA, BD_BAO_DUONG = "Sửa chữa", "Bảo dưỡng"
BD_CHU_KY = 6              # tháng — QT.06: thiết bị sản xuất bảo dưỡng định kỳ 6 tháng/lần
DO_KIEM_LAI = (TBM.DONG_HO, TBM.NAM_CHAM, TBM.LUOI)   # có tờ kiểm lại riêng BM.06.02 / 03 / 04


# ── Định nghĩa sổ ─────────────────────────────────────────────────────────────────────────

def lua_chon(c):
    """Lựa chọn của một cột: mỗi dòng một, bỏ dòng trống."""
    return [x.strip() for x in str(c.get("lua_chon") or "").split("\n") if x.strip()]


def cot_sap(cot):
    """Cột theo `thu_tu` (trống = sau cùng), cùng thứ tự thì theo dòng trên bảng."""
    return sorted(cot or [], key=lambda c: (cint(c.get("thu_tu")) or 10 ** 6, cint(c.get("idx"))))


def loi_dinh_nghia(dn):
    """Lỗi của một định nghĩa sổ (controller SX So — chặn cả Desk) → [câu báo]."""
    loi = []
    if dn.get("kieu") not in (GHI_THEO_DONG, DANH_MUC):
        loi.append("Kiểu sổ: Ghi theo dòng hoặc Danh mục.")
    if dn.get("mang") not in MANG:
        loi.append(f"Mảng không hợp lệ: {dn.get('mang')}.")
    if (dn.get("tinh_toan") or "") and dn["tinh_toan"] not in TINH_TOAN:
        loi.append(f"Hàm riêng '{dn['tinh_toan']}' không có trong code (có: {', '.join(TINH_TOAN)}).")
    cot = dn.get("cot") or []
    if not cot:
        loi.append("Sổ phải có ít nhất một cột.")
    gap = set()
    for c in cot:
        k, nhan = str(c.get("key") or ""), c.get("nhan") or c.get("key")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", k):
            loi.append(f"Khóa cột '{k}': chữ thường không dấu, số, gạch dưới; bắt đầu bằng chữ.")
        elif k in KHOA_DANH_RIENG:
            loi.append(f"Khóa cột '{k}' trùng ô của dòng sổ — đặt tên khác.")
        elif k in gap:
            loi.append(f"Khóa cột '{k}' bị trùng.")
        gap.add(k)
        kieu = c.get("kieu")
        if kieu not in KIEU:
            loi.append(f"Cột {nhan}: kiểu '{kieu}' không hợp lệ.")
        if kieu in ("Select", "MultiSelect") and not lua_chon(c):
            loi.append(f"Cột {nhan}: kiểu {kieu} phải có lựa chọn.")
        if kieu == "Link" and c.get("link_doctype") not in LINK_DUOC:
            loi.append(f"Cột {nhan}: Link chỉ trỏ tới {', '.join(LINK_DUOC)}.")
        if cint(c.get("han")) and kieu != "Date":
            loi.append(f"Cột {nhan}: chỉ cột kiểu Date mới là cột hạn.")
        if cint(c.get("bao_truoc")) < 0:
            loi.append(f"Cột {nhan}: báo trước không âm.")
    if cint(dn.get("nhac_khong_ghi_ngay")) < 0:
        loi.append("Số ngày nhắc không ghi không âm.")
    nt = dn.get("nhom_theo") or ""
    if nt and not any(c.get("key") == nt and c.get("kieu") == "Select" for c in cot):
        loi.append(f"Gom bản in theo '{nt}': phải là khóa một cột kiểu Select.")
    return loi


# ── Kiểm dữ liệu một dòng ─────────────────────────────────────────────────────────────────

def _trong(v):
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (list, tuple)) and not v)


def _ngay(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return date.fromisoformat(s[:10])


def _gio(v):
    m = re.fullmatch(r"(\d{1,2})[:hH.](\d{2})(?::\d{2})?", str(v).strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ValueError(v)
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def chuan_gia_tri(c, v, tra=None):
    """(giá trị chuẩn | None nếu trống, câu lỗi | None) của một ô theo kiểu cột.
    `tra(doctype, giá trị)` → bản ghi liên kết ({name, nhan, loai}) hoặc None — cho Link / User / Attach."""
    kieu, nhan = c.get("kieu") or "Data", c.get("nhan") or c.get("key")
    if kieu == "Check":
        if v in (1, "1", True, "true", "True", "on"):
            return 1, None
        if _trong(v) or v in (0, "0", False, "false", "False"):
            return None, None
        return None, f"{nhan}: chỉ có / không."
    if _trong(v):
        return None, None
    try:
        if kieu in ("Data", "Text"):
            s = str(v).strip()
            toi_da = DAI_DATA if kieu == "Data" else DAI_TEXT
            return (s, None) if len(s) <= toi_da else (None, f"{nhan}: dài quá {toi_da} ký tự.")
        if kieu == "Int":
            s = str(v).strip().replace(" ", "")
            if not re.fullmatch(r"-?\d+", s):
                return None, f"{nhan}: phải là số nguyên."
            return int(s), None
        if kieu == "Float":
            x = float(str(v).strip().replace(" ", "").replace(",", "."))
            return (x, None) if math.isfinite(x) else (None, f"{nhan}: phải là số.")
        if kieu == "Date":
            return _ngay(v).isoformat(), None
        if kieu == "Datetime":
            s = str(v).strip().replace("T", " ")
            d = _ngay(s[:10])
            return f"{d.isoformat()} {_gio(s[11:] or '00:00')}", None
        if kieu == "Time":
            return _gio(v), None
    except (ValueError, TypeError):
        return None, f"{nhan}: '{v}' không đúng kiểu {'ngày' if kieu == 'Date' else 'giờ' if kieu == 'Time' else 'số' if kieu == 'Float' else kieu}."
    if kieu == "Select":
        s = str(v).strip()
        return (s, None) if s in lua_chon(c) else (None, f"{nhan}: '{s}' không có trong lựa chọn.")
    if kieu == "MultiSelect":
        ds = v if isinstance(v, (list, tuple)) else re.split(r"[\n,;]", str(v))
        ds = [str(x).strip() for x in ds if str(x).strip()]
        la = [x for x in ds if x not in lua_chon(c)]
        if la:
            return None, f"{nhan}: '{', '.join(la)}' không có trong lựa chọn."
        return [x for x in lua_chon(c) if x in ds], None
    if kieu in ("Link", "User", "Attach"):
        s = str(v).strip()
        dt = c.get("link_doctype") if kieu == "Link" else ("User" if kieu == "User" else "File")
        if kieu == "Attach" and not s.startswith(("/private/files/", "/files/")):
            return None, f"{nhan}: tệp không hợp lệ."
        x = tra(dt, s) if tra else {"name": s}
        if not x:
            return None, f"{nhan}: không có '{s}'."
        if kieu == "Link" and lua_chon(c) and x.get("loai") not in lua_chon(c):
            return None, f"{nhan}: {s} là {x.get('loai') or '…'} — chỉ chọn {', '.join(lua_chon(c)).lower()}."
        return s, None
    return None, f"{nhan}: kiểu '{kieu}' không hợp lệ."


def kiem_du_lieu(cot, du_lieu, tra=None):
    """(dữ liệu sạch, [lỗi]) — đúng kiểu, đủ ô bắt buộc (ô Check bắt buộc = phải tích), đúng lựa chọn, không khóa lạ.
    Ô trống không lưu (JSON gọn; số 0 vẫn là số)."""
    if not isinstance(du_lieu, dict):
        return {}, ["Dữ liệu dòng sổ không hợp lệ."]
    cot = cot_sap(cot)
    co = {c.get("key") for c in cot}
    loi = []
    la = sorted(k for k in du_lieu if k not in co)
    if la:
        loi.append(f"Cột lạ không có trong sổ: {', '.join(la)}.")
    sach = {}
    for c in cot:
        v, e = chuan_gia_tri(c, du_lieu.get(c.get("key")), tra)
        if e:
            loi.append(e)
            continue
        if v is None:
            if cint(c.get("bat_buoc")):
                loi.append(f"Chưa tích: {c.get('nhan')}." if c.get("kieu") == "Check" else f"Chưa ghi: {c.get('nhan')}.")
            continue
        sach[c["key"]] = v
    return sach, loi


def doc_json(v):
    """Ô JSON của frappe → dict (chuỗi hoặc dict đều nhận; hỏng → {})."""
    if isinstance(v, dict):
        return dict(v)
    try:
        x = json.loads(v or "{}")
    except (TypeError, ValueError):
        return {}
    return x if isinstance(x, dict) else {}


def ghi_json(d):
    return json.dumps(d or {}, ensure_ascii=False, sort_keys=True)


def ngay_vn(s):
    s = str(s or "")[:10]
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}" if len(s) == 10 else ""


def hien(c, v, nhan_link=None):
    """Một ô để đọc (danh sách, bản in): ngày dd/mm/yyyy, Link kèm tên (nhân viên: chỉ họ tên), Check ✓, nhiều lựa
    chọn nối dấu phẩy."""
    if _trong(v):
        return ""
    k = c.get("kieu")
    if k == "Date":
        return ngay_vn(v)
    if k == "Datetime":
        return f"{ngay_vn(v)} {str(v)[11:16]}".strip()
    if k == "Check":
        return "✓" if cint(v) else ""
    if k == "MultiSelect":
        return ", ".join(v) if isinstance(v, (list, tuple)) else str(v)
    if k in ("Link", "User"):
        t = (nhan_link or {}).get(str(v)) or ""
        if k == "User" or (LINK_DUOC.get(c.get("link_doctype")) or {}).get("an_ma"):
            return t or str(v)
        return f"{v} {t}".strip()
    if k == "Float":
        return f"{float(v):g}".replace(".", ",")
    return str(v)


def tom_tat(cot, du_lieu, nhan_link=None):
    """Dòng tóm tắt (danh sách trên điện thoại, ô tìm): các cột `hien_ds` nối " · " — Check chỉ hiện nhãn khi tích."""
    phan = []
    for c in cot_sap(cot):
        if not cint(c.get("hien_ds")):
            continue
        v = du_lieu.get(c.get("key"))
        if c.get("kieu") == "Check":
            if cint(v):
                phan.append(c.get("nhan") or c["key"])
            continue
        s = hien(c, v, nhan_link)
        if s:
            phan.append(s)
    s = " · ".join(phan)
    return s if len(s) <= DAI_DATA else s[:DAI_DATA - 1] + "…"


def cac_han(cot, du_lieu, hom_nay):
    """[{key, nhan, han, con (ngày), bao_truoc}] của các cột hạn có giá trị — gần nhất trước."""
    nay = getdate(hom_nay)
    ra = []
    for c in cot_sap(cot):
        v = du_lieu.get(c.get("key"))
        if not cint(c.get("han")) or _trong(v):
            continue
        h = _ngay(v)
        ra.append({"key": c["key"], "nhan": c.get("nhan") or c["key"], "han": h.isoformat(), "con": (h - nay).days,
                   "bao_truoc": max(0, cint(c.get("bao_truoc")))})
    return sorted(ra, key=lambda x: x["han"])


def han_gan_nhat(cot, du_lieu):
    ds = cac_han(cot, du_lieu, date.today())
    return ds[0]["han"] if ds else None


def han_can_nhac(h):
    """Một hạn có phải nhắc không: quá hạn, hoặc còn ≤ `bao_truoc` ngày."""
    return h["con"] < 0 or h["con"] <= h["bao_truoc"]


# ── Quyền, khóa ───────────────────────────────────────────────────────────────────────────

def quyen(dn, roles, sieu=False):
    """{ghi, xac_nhan, xem, xem_thang, co_xac_nhan} của người có `roles` với sổ `dn` (vai_* = [role]).
    Siêu quyền được mọi việc; Trưởng Ban ISO xem mọi sổ, xem xét tháng mọi sổ có xem xét cuối tháng."""
    roles = set(roles or ())
    vai = {o: set(dn.get(o) or ()) for o in VAI_O}
    iso = ISO in roles
    co_xac_nhan = bool(vai["vai_xac_nhan"])
    ghi = bool(sieu or roles & vai["vai_ghi"])
    xac_nhan = co_xac_nhan and bool(sieu or roles & vai["vai_xac_nhan"])
    xem_thang = bool(cint(dn.get("xem_cuoi_thang"))) and bool(sieu or iso or roles & vai["vai_xem_thang"])
    xem = bool(sieu or iso or ghi or xac_nhan or xem_thang or roles & vai["vai_xem"])
    return {"ghi": ghi, "xac_nhan": xac_nhan, "xem": xem, "xem_thang": xem_thang, "co_xac_nhan": co_xac_nhan}


def _cung_ngay(luc, hom_nay):
    return bool(luc) and getdate(luc) == getdate(hom_nay)


def loi_sua(dn, dong, user, q, hom_nay):
    """Lỗi chặn SỬA một dòng → câu báo | None. `dong` = {trang_thai, nguoi_ghi, ghi_luc}."""
    if dong.get("trang_thai") == NGUNG:
        return "Dòng đã ngừng — không sửa được."
    if not q.get("ghi"):
        return "Bạn không có quyền ghi sổ này."
    if dn.get("kieu") == DANH_MUC:
        return None
    if dong.get("trang_thai") == DA_XAC_NHAN:
        return "Dòng đã xác nhận — khóa, không sửa được."
    if dong.get("nguoi_ghi") != user:
        return "Chỉ người ghi dòng này sửa được."
    if not _cung_ngay(dong.get("ghi_luc"), hom_nay):
        return ("Chỉ sửa được trong ngày ghi. Ghi nhầm thì báo Trưởng Ban ISO ngừng dòng (ghi lý do) rồi ghi dòng "
                "mới.")
    return None


def loi_xac_nhan(dong, user, q):
    """Lỗi chặn XÁC NHẬN → câu báo | None. `dong.nguoi_cuoi` = người ghi / sửa gần nhất (Danh mục)."""
    if not q.get("co_xac_nhan"):
        return "Sổ này không có bước xác nhận."
    if not q.get("xac_nhan"):
        return "Bạn không có quyền xác nhận sổ này."
    if dong.get("trang_thai") == NGUNG:
        return "Dòng đã ngừng."
    if dong.get("trang_thai") == DA_XAC_NHAN:
        return "Dòng đã xác nhận."
    if user in {dong.get("nguoi_ghi"), dong.get("nguoi_cuoi")} - {None, ""}:
        return "Người ghi không tự xác nhận dòng của mình — người khác xác nhận."
    return None


def loi_ngung(dn, dong, user, q, la_iso, hom_nay, ly_do):
    """Lỗi chặn NGỪNG một dòng → câu báo | None.
    Danh mục: người có quyền ghi hoặc Trưởng Ban ISO. Ghi theo dòng: người ghi trong ngày khi chưa xác nhận, hoặc
    Trưởng Ban ISO (siêu quyền) bất cứ lúc nào — dòng vẫn còn trên sổ, gạch đi, có lý do."""
    if dong.get("trang_thai") == NGUNG:
        return "Dòng đã ngừng."
    if not (ly_do or "").strip():
        return "Ghi lý do ngừng."
    if la_iso:
        return None
    if dn.get("kieu") == DANH_MUC:
        return None if q.get("ghi") else "Bạn không có quyền ghi sổ này."
    if (dong.get("nguoi_ghi") == user and dong.get("trang_thai") != DA_XAC_NHAN
            and _cung_ngay(dong.get("ghi_luc"), hom_nay)):
        return None
    return "Chỉ người ghi (trong ngày, khi chưa xác nhận) hoặc Trưởng Ban ISO ngừng được dòng này."


# ── Xem xét cuối tháng ─────────────────────────────────────────────────────────────────────

def moc_xem(hom_nay):
    """Ngày đầu của tháng ĐẦU TIÊN chưa tới hạn xem xét: tháng M phải được xem trước hết ngày NGAY_XEM của tháng
    M+1 — dòng có ngày TRƯỚC mốc này mà tháng của nó chưa xem là quá hạn."""
    d = getdate(hom_nay)
    dau = d.replace(day=1)
    return dau if d.day > NGAY_XEM else (dau - timedelta(days=1)).replace(day=1)


def thang_chua_xem(dong, xem, hom_nay):
    """["YYYY-MM"] các tháng đã tới hạn xem xét mà chưa xem, hoặc có dòng ghi SAU lần xem gần nhất (ghi bù).
    `dong` = [{ngay, ghi_luc}], `xem` = [{thang, xem_luc}]."""
    moc = moc_xem(hom_nay)
    cuoi_ghi = {}
    for x in dong:
        if getdate(x["ngay"]) >= moc:
            continue
        t = str(x["ngay"])[:7]
        g = str(x.get("ghi_luc") or "")[:19]
        cuoi_ghi[t] = max(cuoi_ghi.get(t, ""), g)
    lan_xem = {}
    for x in xem:
        lan_xem[x["thang"]] = max(lan_xem.get(x["thang"], ""), str(x.get("xem_luc") or "")[:19])
    return sorted(t for t, g in cuoi_ghi.items() if not lan_xem.get(t) or g > lan_xem[t])


def tinh_thang(thang):
    """"2026-10" → (1/10/2026, 31/10/2026); sai dạng → ValueError."""
    if not re.fullmatch(r"\d{4}-\d{2}", str(thang or "")):
        raise ValueError(thang)
    dau = date(int(thang[:4]), int(thang[5:7]), 1)
    sau = date(dau.year + (dau.month == 12), dau.month % 12 + 1, 1)
    return dau, sau - timedelta(days=1)


# ── Hàm riêng (`tinh_toan`): rr_abcd, suc_khoe, bao_duong ─────────────────────────────────

def rr_cap_do(a, b, c, d):
    """(RR, cấp độ) của BM.05.02 — mỗi tiêu chí 1–4 điểm; thiếu / sai một ô → (None, None)."""
    try:
        diem = [int(str(x).strip()) for x in (a, b, c, d)]
    except (TypeError, ValueError):
        return None, None
    if any(x < 1 or x > 4 for x in diem):
        return None, None
    rr = sum(diem)
    return rr, next(ten for nguong, ten in CAP_DO if rr >= nguong)


def bo_sung(dn, du_lieu, tra=None):
    """Hàm riêng trước khi kiểm dữ liệu.
    · bao_duong: SỬA một thiết bị đo (đồng hồ nhiệt, nam châm, lưới) mà chưa chọn thiết bị cần kiểm lại → điền chính
      thiết bị đó (QT.06: sau sửa chữa phải hiệu chuẩn / kiểm lại trước khi dùng).
    · rr_abcd: RR, cấp độ tính từ A, B, C, D (gõ tay bị tính đè).
    · suc_khoe: có ngày khám, chưa có hạn khám lại → ngày khám + 12 tháng."""
    du = dict(du_lieu or {})
    tt = dn.get("tinh_toan")
    if tt == RR_ABCD:
        rr, cap = rr_cap_do(du.get("a"), du.get("b"), du.get("c"), du.get("d"))
        for k, v in (("rr", rr), ("cap_do", cap)):
            if v is None:
                du.pop(k, None)
            else:
                du[k] = v
        return du
    if tt == SUC_KHOE:
        if not _trong(du.get("ngay_kham")) and _trong(du.get("han_kham_lai")):
            try:
                du["han_kham_lai"] = TBM.cong_thang(_ngay(du["ngay_kham"]), KHAM_LAI_THANG).isoformat()
            except (TypeError, ValueError):
                pass
        return du
    if tt != BAO_DUONG or not tra:
        return du
    if du.get(BD_LOAI) == BD_SUA and du.get(BD_THIET_BI) and _trong(du.get(BD_KIEM_LAI)):
        tb = tra(TBM.TB, str(du[BD_THIET_BI]).strip())
        if tb and tb.get("loai") in DO_KIEM_LAI and BD_KIEM_LAI in {c.get("key") for c in dn.get("cot") or []}:
            du[BD_KIEM_LAI] = tb["name"]
    return du


def can_kiem_lai(dong, tb, lan_kiem):
    """Dòng BM.06.05 có thiết bị phải kiểm lại mà CHƯA có lần kiểm nào từ ngày sửa (hàm thuần).
    `dong` = [{name, ngay, du_lieu}], `tb` = {mã: {ten, loai, thanh_ly}}, `lan_kiem` = {mã: ngày kiểm gần nhất}.
    → [{dong, ngay, ma, ten, bieu_mau}] — cũ trước."""
    ra = []
    for x in sorted(dong, key=lambda x: str(x["ngay"])):
        ma = (x.get("du_lieu") or {}).get(BD_KIEM_LAI)
        t = tb.get(ma) if ma else None
        if not t or cint(t.get("thanh_ly")):
            continue
        k = lan_kiem.get(ma)
        if k and getdate(k) >= getdate(x["ngay"]):
            continue
        ra.append({"dong": x["name"], "ngay": str(x["ngay"])[:10], "ma": ma, "ten": t.get("ten") or "",
                   "bieu_mau": TBM.BIEU_MAU.get(t.get("loai"), "")})
    return ra


def lich_bao_duong(dong, may, hom_nay):
    """Lịch bảo dưỡng định kỳ máy sản xuất (hàm thuần). `may` = {mã: {ten, chu_ky_thang, tao}} (máy loại Thiết bị
    sản xuất còn dùng), `dong` = [{ngay, du_lieu}] của sổ BM.06.05. Mốc = lần bảo dưỡng gần nhất trên sổ, chưa có
    thì ngày khai máy vào danh mục (máy mới khai không bị nhắc ngay). → [{ma, ten, han, lan_cuoi}] theo mã."""
    nay = getdate(hom_nay)
    cuoi = {}
    for x in dong:
        du = x.get("du_lieu") or {}
        if du.get(BD_LOAI) == BD_BAO_DUONG and du.get(BD_THIET_BI) in may:
            cuoi[du[BD_THIET_BI]] = max(cuoi.get(du[BD_THIET_BI], date.min), getdate(x["ngay"]))
    ra = []
    for ma, m in sorted(may.items()):
        moc = cuoi.get(ma) or getdate(m.get("tao") or nay)
        han = TBM.cong_thang(moc, cint(m.get("chu_ky_thang")) or BD_CHU_KY)
        ra.append({"ma": ma, "ten": m.get("ten") or "", "han": han.isoformat(),
                   "lan_cuoi": cuoi[ma].isoformat() if ma in cuoi else None})
    return ra


def qua_han_bao_duong(dong, may, hom_nay):
    """Máy quá hạn bảo dưỡng định kỳ — phần của lich_bao_duong có hạn trước hôm nay."""
    nay = getdate(hom_nay).isoformat()
    return [x for x in lich_bao_duong(dong, may, hom_nay) if x["han"] < nay]


# ── BM.PRP.05 ↔ mục T4 lượt Tuần (W44) ───────────────────────────────────────────────────────

KINH = "BM.PRP.05"          # danh mục kính, nhựa giòn — khóa cột đọc: ma, vat, vi_tri, bao_ve
T4 = "t4_den_kinh"          # mục "Đèn, kính có bảo vệ" của lượt Tuần (sx/qc/muc.py)


def ten_vat_kinh(du):
    """Nhãn một vật của BM.PRP.05: "Đèn huỳnh quang · Phòng đóng gói" (mã để riêng)."""
    return " · ".join(str(du.get(k)).strip() for k in ("vat", "vi_tri") if not _trong(du.get(k)))


def t4_theo_vat(dong, ds):
    """Giá trị T4 từ các vật đã tích. `dong` = [{vat, ket_qua}] của lượt; `ds` = [{vat}] danh mục đang dùng.
    Có vật Không đạt → Không đạt; mọi vật trong danh mục đều Đạt → Đạt; còn vật chưa tích → None (T4 chưa chấm —
    hoàn tất phải ghi lý do như mọi mục để trống)."""
    kq = {r.get("vat"): r.get("ket_qua") for r in dong or []}
    if any(v == M.KHONG_DAT for v in kq.values()):
        return M.KHONG_DAT
    if ds and all(kq.get(v["vat"]) == M.DAT for v in ds):
        return M.DAT
    return None


# ── Đọc DB ────────────────────────────────────────────────────────────────────────────────

TRUONG_DN = ("ma", "ten", "kieu", "quy_trinh", "mang", "ngung", "nhan_xac_nhan", "xem_cuoi_thang", "nhan_xem_thang",
             "nhac_khong_ghi_ngay", "tinh_toan", "nhom_theo", "rieng_tu", "dau_trang_ghi_chu", "ghi_chu", "creation")
TRUONG_COT = ("key", "nhan", "kieu", "lua_chon", "link_doctype", "bat_buoc", "han", "bao_truoc", "hien_ds", "thu_tu",
              "idx")


def dinh_nghia_tu_doc(doc):
    """SX So (doc) → dict thuần: ô chính, cot (đã sắp), vai_* = [role]."""
    d = {f: doc.get(f) for f in TRUONG_DN}
    d["name"] = doc.get("name") or d["ma"]
    d["cot"] = cot_sap([{f: r.get(f) for f in TRUONG_COT} for r in doc.get("cot") or []])
    for o in VAI_O:
        d[o] = sorted({r.get("role") for r in doc.get(o) or [] if r.get("role")})
    d["nhan_xem_thang"] = d.get("nhan_xem_thang") or NHAN_XEM_MAC_DINH
    return d


def dinh_nghia(ma):
    """Định nghĩa sổ `ma` (dict thuần) — không có → None."""
    if not ma or not frappe.db.exists(PT, ma):
        return None
    return dinh_nghia_tu_doc(frappe.get_doc(PT, ma))


def tra(dt, v):
    """Bản ghi một ô Link / User / Attach trỏ tới → {name, nhan, loai} | None (không có, user đã khóa)."""
    if dt == "User":
        x = frappe.db.get_value("User", v, ["name", "full_name", "enabled"], as_dict=True)
        return {"name": x.name, "nhan": x.full_name or x.name, "loai": None} if x and cint(x.enabled) else None
    if dt == "File":
        x = frappe.db.get_value("File", {"file_url": v}, ["name", "file_name"], as_dict=True)
        return {"name": x.name, "nhan": x.file_name or "", "loai": None} if x else None
    cfg = LINK_DUOC.get(dt)
    if not cfg:
        return None
    o = ["name", cfg["nhan"]] + ([cfg["loai"]] if cfg.get("loai") else [])
    x = frappe.db.get_value(dt, v, o, as_dict=True)
    if not x:
        return None
    loai = x.get(cfg["loai"]) if cfg.get("loai") else None
    nhan = x.get(cfg["nhan"]) or ""
    if dt == TBM.TB and TBM.BIEU_MAU.get(loai):          # thiết bị đo: kèm tờ kiểm lại (BM.06.02 / 03 / 04)
        nhan = f"{nhan} ({TBM.BIEU_MAU[loai]})".strip()
    return {"name": x.name, "nhan": nhan, "loai": loai}


def nhan_link(cot, du_lieu):
    """{giá trị: nhãn} cho các ô Link / User của một dòng (tóm tắt, bản in)."""
    ra = {}
    for c in cot or []:
        v = du_lieu.get(c.get("key"))
        if c.get("kieu") in ("Link", "User") and not _trong(v):
            x = tra(c.get("link_doctype") if c.get("kieu") == "Link" else "User", str(v))
            if x:
                ra[str(v)] = x.get("nhan") or ""
    return ra


def vao_bm0701(roles, sieu=False):
    """Thẻ BM.07.01 đánh giá nhà cung cấp (W44) ở màn Sổ: Mua hàng, QC, Giám đốc, Trưởng Ban ISO, siêu quyền — khi
    site đã có DocType. Nạp muộn: danh_gia_ncc kéo theo luật NCC."""
    try:
        from sx.qc import danh_gia_ncc as DG
        return bool(sieu or set(roles or ()) & DG.VAI_XEM) and bool(frappe.db.table_exists(DG.PT))
    except Exception:
        return False


def co_so(roles, sieu=False):
    """Người có các role này thấy ít nhất một sổ đang dùng (hoặc thẻ BM.07.01) không — để ẩn tab Sổ của người chưa
    được giao sổ nào. Chưa migrate → False."""
    if vao_bm0701(roles, sieu):
        return True
    try:
        ten = frappe.get_all(PT, filters={"ngung": 0}, pluck="name")
        if not ten:
            return False
        if sieu or ISO in set(roles or ()):
            return True
        return bool(frappe.get_all(PT_VAI, filters={"parenttype": PT, "parent": ("in", ten),
                                                    "role": ("in", sorted(roles or ()) or [""])}, limit=1))
    except Exception:
        return False


def _vai_theo_so(ten):
    ra = {t: {o: [] for o in VAI_O} for t in ten}
    for r in frappe.get_all(PT_VAI, filters={"parenttype": PT, "parent": ("in", ten or [""])},
                            fields=["parent", "parentfield", "role"]):
        if r.parentfield in VAI_O and r.parent in ra:
            ra[r.parent][r.parentfield].append(r.role)
    return ra


def _cot_theo_so(ten):
    ra = {t: [] for t in ten}
    for r in frappe.get_all(PT_COT, filters={"parenttype": PT, "parent": ("in", ten or [""])},
                            fields=["parent"] + list(TRUONG_COT)):
        ra.setdefault(r.parent, []).append({f: r.get(f) for f in TRUONG_COT})
    return {t: cot_sap(c) for t, c in ra.items()}


def ds_dinh_nghia(ngung=False):
    """Mọi định nghĩa sổ (dict thuần, có cot / vai_*) — một lượt truy vấn cho mỗi bảng."""
    loc = {} if ngung else {"ngung": 0}
    ds = frappe.get_all(PT, filters=loc, fields=["name"] + list(TRUONG_DN), order_by="ma asc")
    ten = [x.name for x in ds]
    cot, vai = _cot_theo_so(ten), _vai_theo_so(ten)
    ra = []
    for x in ds:
        d = {f: x.get(f) for f in TRUONG_DN}
        d.update(name=x.name, cot=cot.get(x.name, []), **{o: sorted(set(v)) for o, v in vai[x.name].items()})
        d["nhan_xem_thang"] = d.get("nhan_xem_thang") or NHAN_XEM_MAC_DINH
        ra.append(d)
    return ra


def _thiet_bi():
    """({mã: thiết bị}, {mã máy sản xuất còn dùng: {ten, chu_ky_thang, tao}})."""
    tb = {x.name: x for x in frappe.get_all(TBM.TB, fields=["name", "ten", "loai", "thanh_ly", "chu_ky_thang",
                                                            "creation"])}
    may = {k: {"ten": v.ten, "chu_ky_thang": v.chu_ky_thang, "tao": str(v.creation or "")[:10] or None}
           for k, v in tb.items() if v.loai == TBM.SAN_XUAT and not cint(v.thanh_ly)}
    return tb, may


def _bao_duong(dong, nay):
    """Nhắc riêng của sổ BM.06.05: thiết bị phải kiểm lại sau sửa chữa; máy quá hạn bảo dưỡng."""
    tb, may = _thiet_bi()
    cuoi, _giay = TBM.cac_lan_cuoi()
    lan = {k: v.ngay for k, v in cuoi.items()}
    return {"kiem_lai": can_kiem_lai(dong, tb, lan), "bao_duong": qua_han_bao_duong(dong, may, nay)}


def bao_duong_may(hom_nay):
    """{mã máy: {lan_cuoi, han}} theo các sổ có hàm bao_duong — cho danh mục BM.06.01. Lỗi / chưa migrate → {}."""
    try:
        so = frappe.get_all(PT, filters={"tinh_toan": BAO_DUONG, "ngung": 0}, pluck="name")
        dong = [{"name": x.name, "ngay": x.ngay, "du_lieu": doc_json(x.du_lieu)} for x in frappe.get_all(
            PT_DONG, filters={"so": ("in", so or [""]), "trang_thai": ("!=", NGUNG)}, fields=["name", "ngay", "du_lieu"],
            order_by="ngay asc, creation asc")]
        _tb, may = _thiet_bi()
    except Exception:
        return {}
    return {x["ma"]: x for x in lich_bao_duong(dong, may, hom_nay)}


def nhac(hom_nay):
    """Dữ liệu cho hộp nhắc (chữ do sx/qc/nhac.py viết). Chưa migrate → {}.

    {"ds": [{ma, ten, mang, nhan_xac_nhan, nhan_xem_thang, cho_nguong, rieng_tu, han: [{dong, tom_tat, nhan, han,
             con}], cho: [{name, ngay, tom_tat}], khong_ghi: {ngay_cuoi, so_ngay, nguong} | None,
             chua_xem: ["YYYY-MM"], kiem_lai: [...], bao_duong: [...]}]}
    Chỉ sổ đang dùng; dòng Ngừng không tính. Sổ dữ liệu cá nhân (`rieng_tu`, BM.PRP.07): tom_tat trống — hộp nhắc
    chung không ghi họ tên."""
    nay = getdate(hom_nay)
    try:
        dns = ds_dinh_nghia()
        if not dns:
            return {"ds": []}
        dong = frappe.get_all(PT_DONG, filters={"trang_thai": ("!=", NGUNG)},
                              fields=["name", "so", "ngay", "trang_thai", "tom_tat", "han_gan_nhat", "ghi_luc",
                                      "du_lieu"], order_by="ngay asc, creation asc")
        xem = frappe.get_all(PT_XEM, fields=["so", "thang", "xem_luc"])
    except Exception:
        return {}
    theo, xem_theo = {}, {}
    for x in dong:
        theo.setdefault(x.so, []).append(x)
    for x in xem:
        xem_theo.setdefault(x.so, []).append(x)
    ra = []
    for dn in dns:
        ds = theo.get(dn["name"], [])
        kin = bool(cint(dn.get("rieng_tu")))
        han = []
        for x in ds:
            if not x.han_gan_nhat:
                continue
            for h in cac_han(dn["cot"], doc_json(x.du_lieu), nay):
                if han_can_nhac(h):
                    han.append(dict(h, dong=x.name, tom_tat="" if kin else x.tom_tat or ""))
        co_xn = quyen(dn, ())["co_xac_nhan"]
        cho = []
        if co_xn:
            cho = [{"name": x.name, "ngay": str(x.ngay), "tom_tat": "" if kin else x.tom_tat or ""} for x in ds
                   if x.trang_thai == DA_GHI and x.ghi_luc and (nay - getdate(x.ghi_luc)).days > CHO_XAC_NHAN_NGAY]
        khong_ghi = None
        n = cint(dn.get("nhac_khong_ghi_ngay"))
        if n > 0 and dn.get("kieu") == GHI_THEO_DONG:
            cuoi = max((getdate(x.ngay) for x in ds), default=None)
            moc = cuoi or getdate(dn.get("creation") or nay)
            if (nay - moc).days > n:
                khong_ghi = {"ngay_cuoi": cuoi.isoformat() if cuoi else None, "so_ngay": (nay - moc).days, "nguong": n}
        chua_xem = thang_chua_xem([{"ngay": x.ngay, "ghi_luc": x.ghi_luc} for x in ds], xem_theo.get(dn["name"], []),
                                  nay) if cint(dn.get("xem_cuoi_thang")) else []
        rieng = {"kiem_lai": [], "bao_duong": []}
        if dn.get("tinh_toan") == BAO_DUONG:
            try:
                rieng = _bao_duong([{"name": x.name, "ngay": x.ngay, "du_lieu": doc_json(x.du_lieu)} for x in ds], nay)
            except Exception:
                pass
        ra.append({"ma": dn["name"], "ten": dn.get("ten") or "", "mang": dn.get("mang") or SO_KHAC,
                   "kieu": dn.get("kieu"), "nhan_xac_nhan": dn.get("nhan_xac_nhan") or "",
                   "nhan_xem_thang": dn.get("nhan_xem_thang") or NHAN_XEM_MAC_DINH, "cho_nguong": CHO_XAC_NHAN_NGAY,
                   "co_xac_nhan": co_xn, "rieng_tu": kin,
                   "han": sorted(han, key=lambda h: h["han"]), "cho": cho, "khong_ghi": khong_ghi,
                   "chua_xem": chua_xem, **rieng})
    return {"ds": ra}


def ds_vat_kinh():
    """[{vat (tên dòng sổ), ma, ten, bao_ve}] — vật đang dùng của danh mục BM.PRP.05, theo mã. Sổ chưa có / đã ngừng /
    chưa migrate → [] (mục T4 tích một lần như trước)."""
    try:
        if not frappe.db.exists(PT, KINH) or cint(frappe.db.get_value(PT, KINH, "ngung")):
            return []
        ds = frappe.get_all(PT_DONG, filters={"so": KINH, "trang_thai": ("!=", NGUNG)}, fields=["name", "du_lieu"],
                            order_by="creation asc")
    except Exception:
        return []
    ra = []
    for x in ds:
        du = doc_json(x.du_lieu)
        ra.append({"vat": x.name, "ma": "" if _trong(du.get("ma")) else str(du["ma"]).strip(),
                   "ten": ten_vat_kinh(du), "bao_ve": "" if _trong(du.get("bao_ve")) else str(du["bao_ve"]).strip()})
    return sorted(ra, key=lambda v: (v["ma"] == "", v["ma"], v["vat"]))
