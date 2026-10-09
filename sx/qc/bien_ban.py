"""Khung "Biên bản" (W45, D174) — lập, ký nhiều cấp, kéo dữ liệu. 18 phiếu giấy là DỮ LIỆU khai báo (SX Mau Bien Ban),
không làm 18 màn riêng.

Mẫu = các phần theo thứ tự in (SX Mau Bien Ban Phan) + các ô ký theo thứ tự ký (SX Mau Bien Ban Ky). Kiểu phần:
  · Văn bản        các ô (cột như SX So Cot) — phần khóa "dau" là đầu phiếu (giờ, địa điểm, chủ trì…);
  · Bảng           bảng nhiều dòng; dòng in sẵn chỉ là gợi ý — sửa, thêm, xóa được;
  · Danh sách kiểm câu in sẵn (cột "hoi" không sửa, dòng không bỏ được) + ô trả lời; cột kết luận ≤ 3 lựa chọn hiện
                   thành nút; dòng Không phù hợp (KPH / Không / Không đạt / cần điều chỉnh) → nút "Lập BM.01.07";
  · Kéo dữ liệu    BẢN CHỤP số liệu app lúc lập (sự cố, khiếu nại, BM.01.07…) — số liệu sau này đổi không làm đổi biên
                   bản; "Kéo lại" chỉ khi còn Nháp / Trả lại;
  · Việc giao      bảng việc (viec, phu_trach = tài khoản, han): ký đủ thì mỗi dòng thành một SX Viec Dinh Ky
                   "Một lần" (hộp nhắc sẵn có nhắc hạn).
Phần Bảng / Danh sách kiểm có `nguon` thì dòng lấy từ hàm kéo (vd BM.HACCP.01 kéo công đoạn của dây chuyền).
Hàm kéo, hàm tính là KHÓA CỐ ĐỊNH trong code (NGUON, TINH) — không chạy biểu thức người dùng gõ.

Biên bản (SX Bien Ban): Nháp → Chờ ký → Đã ký đủ; người ký trả lại (ghi ý kiến) → Trả lại (sửa, gửi lại; chữ ký vòng
trước bỏ). Ký theo `thu_tu`; một người không ký hai ô; ô "người lập" do người lập ký, ô có vai do người có vai đó ký.
Ô ký tay (người ngoài, văn bản gửi ra ngoài — C23) không ký trên app: in, ký, tải bản scan; chưa có bản scan thì không
khóa. Đủ chữ ký → khóa. Lúc lập, các phần của mẫu được CHÉP vào biên bản (dinh_nghia) — sửa mẫu sau này không làm đổi
biên bản đã lập.

Đánh giá nội bộ (4 mẫu nối nhau): BM.01.05 kế hoạch (chuyên gia không đánh giá bộ phận của mình; Trưởng Ban ISO
không làm trưởng đoàn — QT.01) → BM.01.06 checklist từng bộ phận (lập từ kế hoạch đã duyệt; "Chép câu hỏi từ đợt
trước") → BM.01.08 tự gom các dòng Lưu ý → BM.01.09 tự đếm KPH / Lưu ý theo bộ phận.
BM.HACCP.01: danh sách công đoạn (SX QC Cong Doan) của một dây chuyền đổi sau lần xác nhận gần nhất → nhắc xác
nhận lại sơ đồ tại hiện trường (KH.HACCP mục 5.5).

Phần thuần ở đầu (test gọi thẳng); phần đọc DB ở cuối. Module qc: không import phần SX — lô thu hồi, nhắc mức cao,
báo cáo tháng do API truyền hàm vào (`ctx["ham"]`).
"""

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timedelta

import frappe
from frappe.utils import cint, getdate

from sx.qc import so as SO

PT, PT_PHAN, PT_KY_MAU = "SX Mau Bien Ban", "SX Mau Bien Ban Phan", "SX Mau Bien Ban Ky"
PT_BB, PT_KY, PT_LQ, PT_VIEC, PT_TEP = ("SX Bien Ban", "SX Bien Ban Ky", "SX Bien Ban Lien Quan", "SX Bien Ban Viec",
                                        "SX Bien Ban Tep")
PT_VAI = "SX So Vai"
VAN_BAN, BANG, DS_KIEM, KEO, VIEC_GIAO = "Văn bản", "Bảng", "Danh sách kiểm", "Kéo dữ liệu", "Việc giao"
KIEU_PHAN = (VAN_BAN, BANG, DS_KIEM, KEO, VIEC_GIAO)
CO_DONG = (BANG, DS_KIEM, VIEC_GIAO)          # phần lưu nhiều dòng
TUAN, THANG, NAM, PHAT_SINH = "Tuần", "Tháng", "Năm", "Khi phát sinh"
CHU_KY = (TUAN, THANG, NAM, PHAT_SINH)
KY_NGAY = {TUAN: 7, THANG: 31, NAM: 365, PHAT_SINH: 30}   # kỳ kéo dữ liệu khi chưa có biên bản trước
NHAP, CHO_KY, DA_KY, TRA_LAI = "Nháp", "Chờ ký", "Đã ký đủ", "Trả lại"
TRANG_THAI = (NHAP, CHO_KY, DA_KY, TRA_LAI)
SUA_DUOC = (NHAP, TRA_LAI)
CHO_KY_NGAY = 3              # chờ ký quá chừng này ngày → nhắc (md W45)
DAU = "dau"                  # khóa phần đầu phiếu
KHONG_PHU_HOP = ("KPH", "Không", "Không đạt", "cần điều chỉnh")
LUU_Y = "Lưu ý"
COT_VIEC = ("viec", "phu_trach", "han")      # cột bắt buộc của phần Việc giao
KHOA_RIENG = {"name", "_id"}
ISO, GIAM_DOC = "ISO Manager", "SX Quan Ly"
NGUON_CAR = ("Sự cố", "Khiếu nại", "Đánh giá nội bộ", "Đánh giá bên ngoài", "Xem xét của lãnh đạo", "Thẩm tra", "Khác")
TRUONG_DOAN = "Trưởng đoàn"

# Mã mẫu có luật riêng trong code.
HOP_ISO, XEM_XET_LD = "BM.01.11", "BM.01.10"
DGNB_KH, DGNB_CL, DGNB_LY, DGNB_BC = "BM.01.05", "BM.01.06", "BM.01.08", "BM.01.09"
DGNB_CON = (DGNB_CL, DGNB_LY, DGNB_BC)        # lập từ một kế hoạch BM.01.05 đã duyệt (đợt đánh giá)
THAM_TRA_KH, THAM_TRA_BC = "BM.04.01", "BM.04.02"
THU_HOI_KH, THU_HOI_BC = "BM.02.01", "BM.02.02"
SO_DO = "BM.HACCP.01"

# Dây chuyền ↔ công đoạn (SX QC Cong Doan.day_chuyen) ↔ mốc xác nhận sơ đồ bằng giấy trước khi có app.
BANH, BOT = "Bánh", "Bột"
SO_DO_GIAY = {BANH: date(2026, 9, 22)}       # KH.HACCP.01: xác nhận 01/9/2026 và 22/9/2026 (biên bản họp Ban ISO)
# Bột: KH.HACCP.02 mục 5.5 — sơ đồ 11 công đoạn còn chờ Ban ISO xác nhận tại xưởng → chưa có mốc, nhắc ngay.
# Patch d174 ghi mốc bánh = danh mục công đoạn lúc triển khai (SX QC Setting.so_do_moc).

# oPRP hiện hành (md mục 3): bánh 1, 2; bột 5–9 (oPRP-3, 4 chuyển xuống PRP; oPRP-8 chỉ còn nhãn).
OPRP = {
    BANH: (("oPRP-1", "VSV gây bệnh dạng sinh dưỡng trong đỗ", "Luộc sôi đến chín; rang 240–280 °C"),
           ("oPRP-2", "Cát, sạn, kim loại, tạp chất", "Sàng cát, lọc sạn, nam châm NC-01, NC-02, rây RY-01; rây kiểm "
                                                       "< 0,2 mm")),
    BOT: (("oPRP-5", "VSV trong phụ liệu bột, sữa bột, dừa sấy", "Hồ sơ lô / kiểm nghiệm năm của NCC"),
          ("oPRP-6", "Aflatoxin trong lạc", "NCC duyệt có hồ sơ aflatoxin; nhặt, sàng loại hạt mốc"),
          ("oPRP-7", "Salmonella trong lạc", "Rang 150–180 °C, 30–40 phút"),
          ("oPRP-8", "Nhãn sai, thiếu cảnh báo dị ứng", "Kiểm nhãn mỗi lượt"),
          ("oPRP-9", "Nhiễm chéo lạc, sữa", "Trình tự sản xuất; vệ sinh chuyển đổi; thử nhanh protein lạc (3 lần âm "
                                            "tính khi thiết lập)")),
}

# Hàm tính có tên (phần trỏ tới bằng `tinh`).
K_X_A, LOC_DIEN_TAP, TY_LE_THU_HOI = "k_x_a", "loc_dien_tap", "ty_le_thu_hoi"
TINH = {
    K_X_A: "Điểm = K × A (QT.14: ≥ 6 cao, 3–4 trung bình, 1–2 thấp).",
    LOC_DIEN_TAP: "Chỉ chấm dòng của nội dung đã diễn tập (DT-1 / DT-2 / DT-3 tích ở đầu phiếu).",
    TY_LE_THU_HOI: "Tỷ lệ thu hồi = số lượng thu hồi được / số lượng đã xuất × 100 %.",
}
TINH_COT = {K_X_A: ("diem",), TY_LE_THU_HOI: ("ty_le",)}     # cột do app tính — không nhập


# ── Chữ, ngày ─────────────────────────────────────────────────────────────────────────────

def khong_dau(s):
    s = unicodedata.normalize("NFKD", str(s or "").replace("đ", "d").replace("Đ", "D"))
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip().lower()


def ngay_vn(s):
    return SO.ngay_vn(s)


def _ngay(v):
    return v if isinstance(v, date) and not isinstance(v, datetime) else getdate(v)


def _trong(v):
    return SO._trong(v)


def _ngan(s, toi_da=160):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= toi_da else s[:toi_da - 1] + "…"


# ── Định nghĩa mẫu ────────────────────────────────────────────────────────────────────────

def doc_json(v, mac_dinh=None):
    """Ô JSON → giá trị (chuỗi hoặc đã giải); hỏng → mặc định."""
    if isinstance(v, (dict, list)):
        return v
    try:
        x = json.loads(v) if v not in (None, "") else mac_dinh
    except (TypeError, ValueError):
        return mac_dinh
    return x if x is not None else mac_dinh


def ghi_json(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


def cot_cua(p):
    """Cột / ô của một phần (đã sắp theo thu_tu như SX So Cot)."""
    c = doc_json(p.get("cot"), [])
    return SO.cot_sap([dict(x) for x in c if isinstance(x, dict)]) if isinstance(c, list) else []


def cot_hoi(p):
    return [c for c in cot_cua(p) if cint(c.get("hoi"))]


def cot_tinh(p):
    return set(TINH_COT.get(p.get("tinh") or "", ()))


def cot_nhap(p):
    """Cột người dùng nhập: bỏ cột do app tính."""
    t = cot_tinh(p)
    return [c for c in cot_cua(p) if c.get("key") not in t]


def cot_ket_luan(p):
    """Cột kết luận của Danh sách kiểm: cột Select (không phải câu hỏi) đầu tiên có ≤ 3 lựa chọn — hiện thành nút."""
    for c in cot_cua(p):
        if c.get("kieu") == "Select" and not cint(c.get("hoi")) and 0 < len(SO.lua_chon(c)) <= 3:
            return c
    return None


def la_khong_phu_hop(v):
    return str(v or "").strip() in KHONG_PHU_HOP


def tach_dong_mau(p):
    """Dòng in sẵn của một phần → [{_id, _co_dinh, _tieu_de?, cột: ô}]. Ô nối bằng " | " theo thứ tự cột; dòng bắt
    đầu "# " là tiêu đề nhóm."""
    cot = cot_cua(p)
    ra = []
    for i, dong in enumerate([x for x in str(p.get("dong_mau") or "").split("\n") if x.strip()], 1):
        tieu_de = dong.lstrip().startswith("# ")
        o = [x.strip() for x in (dong.lstrip()[2:] if tieu_de else dong).split("|")]
        r = {"_id": f"m{i}", "_co_dinh": 1}
        if tieu_de:
            r["_tieu_de"] = 1
        for c, v in zip(cot, o):
            if v != "":
                r[c["key"]] = v
        ra.append(r)
    return ra


def _cac_o(m):
    """{khóa: cột} các ô của phần đầu phiếu (Văn bản khóa "dau")."""
    p = next((x for x in m.get("phan") or [] if x.get("key") == DAU), None)
    return {c["key"]: c for c in cot_cua(p)} if p else {}


def loi_mau(m):
    """Lỗi của một mẫu biên bản (controller SX Mau Bien Ban — chặn cả Desk) → [câu báo]."""
    loi = []
    if m.get("chu_ky_lap") not in CHU_KY:
        loi.append("Chu kỳ lập: Tuần / Tháng / Năm / Khi phát sinh.")
    if (m.get("nguon_car") or "") and m["nguon_car"] not in NGUON_CAR:
        loi.append(f"Nguồn BM.01.07 '{m['nguon_car']}' không hợp lệ.")
    phan = m.get("phan") or []
    if not phan:
        loi.append("Mẫu phải có ít nhất một phần.")
    gap = set()
    for p in phan:
        k, ten = str(p.get("key") or ""), p.get("tieu_de") or p.get("key")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", k):
            loi.append(f"Khóa phần '{k}': chữ thường không dấu, số, gạch dưới; bắt đầu bằng chữ.")
        elif k in gap:
            loi.append(f"Khóa phần '{k}' bị trùng.")
        gap.add(k)
        kieu = p.get("kieu")
        if kieu not in KIEU_PHAN:
            loi.append(f"Phần {ten}: kiểu '{kieu}' không hợp lệ.")
            continue
        raw = doc_json(p.get("cot"), [])
        if not isinstance(raw, list) or any(not isinstance(x, dict) for x in raw):
            loi.append(f"Phần {ten}: cột phải là danh sách JSON.")
            continue
        cot = cot_cua(p)
        if cot:
            loi += [f"Phần {ten}: {x}" for x in SO.loi_dinh_nghia({"kieu": SO.GHI_THEO_DONG, "mang": SO.SO_KHAC,
                                                                     "cot": cot})]
        elif kieu in CO_DONG or (kieu == VAN_BAN and k == DAU):
            loi.append(f"Phần {ten}: chưa khai cột.")
        nguon = p.get("nguon") or ""
        if nguon and nguon not in NGUON and nguon not in CHON_NGUON:
            loi.append(f"Phần {ten}: hàm kéo '{nguon}' không có trong code (có: {', '.join(sorted(NGUON))}).")
        if kieu == KEO and not nguon:
            loi.append(f"Phần {ten}: kiểu Kéo dữ liệu phải chọn hàm kéo.")
        if (p.get("tinh") or "") and p["tinh"] not in TINH:
            loi.append(f"Phần {ten}: hàm tính '{p['tinh']}' không có trong code (có: {', '.join(TINH)}).")
        for c in cot_tinh(p):
            if cot and c not in {x.get("key") for x in cot}:
                loi.append(f"Phần {ten}: hàm {p['tinh']} cần cột '{c}'.")
        if kieu == VIEC_GIAO:
            co = {c.get("key"): c.get("kieu") for c in cot}
            if co.get("viec") not in ("Data", "Text") or co.get("phu_trach") != "User" or co.get("han") != "Date":
                loi.append(f"Phần {ten}: Việc giao phải có cột viec (chữ), phu_trach (User), han (Date).")
        if kieu == DS_KIEM and not cot_ket_luan(p) and not any(not cint(c.get("hoi")) for c in cot):
            loi.append(f"Phần {ten}: Danh sách kiểm phải có ít nhất một cột trả lời.")
        if kieu == KEO and (p.get("dong_mau") or "").strip():
            loi.append(f"Phần {ten}: Kéo dữ liệu không có dòng in sẵn.")
    o_dau = _cac_o(m)
    for p in phan:
        ck = p.get("chi_khi") or ""
        if ck and (o_dau.get(ck) or {}).get("kieu") != "Check":
            loi.append(f"Phần {p.get('tieu_de') or p.get('key')}: 'chỉ khi' phải là khóa một ô Check của đầu phiếu.")
    tk = m.get("ky_tay_khi") or ""
    if tk and (o_dau.get(tk) or {}).get("kieu") != "Check":
        loi.append("Buộc ký tay khi: phải là khóa một ô Check của đầu phiếu.")
    ky = m.get("ky") or []
    if not ky:
        loi.append("Mẫu phải có ít nhất một ô ký.")
    for s in ky:
        ten = s.get("vai_tro") or "?"
        if not (s.get("role") or cint(s.get("nguoi_lap")) or cint(s.get("ky_tay"))
                or str(ten).startswith(TRUONG_DOAN)):
            loi.append(f"Ô ký {ten}: chọn vai được ký, hoặc tích Người lập ký / Ký tay.")
    return loi


# ── Nội dung ──────────────────────────────────────────────────────────────────────────────

def phan_ap_dung(p, dau):
    """Phần có `chi_khi` chỉ dùng khi ô đó ở đầu phiếu được tích."""
    ck = p.get("chi_khi")
    return not ck or bool(cint((dau or {}).get(ck)))


def dong_ap_dung(p, r, dau):
    """Dòng của Danh sách kiểm có phải chấm không: dòng tiêu đề thì không; BM.03.04 (loc_dien_tap) chỉ dòng của nội
    dung đã tích (DT-1 → ô dt1)."""
    if cint(r.get("_tieu_de")):
        return False
    if p.get("tinh") == LOC_DIEN_TAP:
        m = re.fullmatch(r"DT-(\d+)", str(r.get("ma") or "").strip())
        if m:
            return bool(cint((dau or {}).get(f"dt{m.group(1)}")))
    return True


def gia_tri_dau(nd):
    return dict(((nd or {}).get(DAU) or {}).get("gia_tri") or {})


def muc_kxa(diem):
    """Mức của Điểm = K × A (QT.14 mục 5.2): ≥ 6 cao, 3–4 trung bình, 1–2 thấp; chưa chấm → ""."""
    try:
        d = int(diem)
    except (TypeError, ValueError):
        return ""
    return "cao" if d >= 6 else ("trung_binh" if d >= 3 else "thap")


def tinh_phan(p, gia_tri):
    """Áp hàm tính của phần lên giá trị đã sạch (dòng hoặc ô Văn bản) — giá trị gõ tay ở cột tính bị tính đè."""
    t = p.get("tinh") or ""
    if t == K_X_A:
        for r in gia_tri.get("dong") or []:
            try:
                k, a = int(str(r.get("k")).strip()), int(str(r.get("a")).strip())
                r["diem"] = k * a if 1 <= k <= 3 and 1 <= a <= 3 else None
            except (TypeError, ValueError):
                r["diem"] = None
            if r.get("diem") is None:
                r.pop("diem", None)
    elif t == TY_LE_THU_HOI:
        g = gia_tri.get("gia_tri") or {}
        try:
            xuat, ve = float(g.get("so_luong_da_xuat") or 0), float(g.get("so_luong_thu_hoi") or 0)
        except (TypeError, ValueError):
            xuat = ve = 0
        if xuat > 0 and ve >= 0 and g.get("so_luong_thu_hoi") not in (None, ""):
            g["ty_le"] = round(ve / xuat * 100, 2)
        else:
            g.pop("ty_le", None)
    return gia_tri


def _sach_o(c, v, tra, loi, nhan):
    g, e = SO.chuan_gia_tri(c, v, tra)
    if e:
        loi.append(f"{nhan}: {e}" if nhan else e)
        return None
    return g


def _id_moi(da_co):
    i = 1
    while f"t{i}" in da_co:
        i += 1
    da_co.add(f"t{i}")
    return f"t{i}"


def sach_phan(p, moi, cu=None, tra=None):
    """(giá trị sạch của một phần, [lỗi kiểu]) — KHÔNG kiểm ô bắt buộc (Nháp lưu dở được; đủ ô kiểm lúc gửi ký).
    `moi` = giá trị client gửi; `cu` = giá trị đang lưu (Danh sách kiểm giữ câu in sẵn; Kéo dữ liệu giữ bản chụp)."""
    kieu, ten = p.get("kieu"), p.get("tieu_de") or p.get("key")
    moi, cu = dict(moi or {}), dict(cu or {})
    loi = []
    if kieu == KEO:
        return ({"keo": cu["keo"]} if cu.get("keo") else {}), loi
    cot = cot_nhap(p)
    if kieu == VAN_BAN:
        if not cot_cua(p):
            s = str(moi.get("chu") or "").strip()
            if len(s) > 20000:
                loi.append(f"{ten}: dài quá.")
            return ({"chu": s} if s else {}), loi
        g = moi.get("gia_tri") or {}
        if not isinstance(g, dict):
            return {}, [f"{ten}: dữ liệu không hợp lệ."]
        la = sorted(k for k in g if k not in {c["key"] for c in cot_cua(p)})
        if la:
            loi.append(f"{ten}: ô lạ {', '.join(la)}.")
        sach = {}
        for c in cot:
            v = _sach_o(c, g.get(c["key"]), tra, loi, "")
            if v is not None:
                sach[c["key"]] = v
        return tinh_phan(p, {"gia_tri": sach}), loi
    # Phần nhiều dòng.
    ds = moi.get("dong") or []
    if not isinstance(ds, list) or any(not isinstance(r, dict) for r in ds):
        return {}, [f"{ten}: danh sách dòng không hợp lệ."]
    hoi = {c["key"] for c in cot_hoi(p)} if kieu == DS_KIEM else set()
    cu_dong = {r.get("_id"): r for r in (cu.get("dong") or []) if r.get("_id")}
    co_dinh = {k for k, r in cu_dong.items() if cint(r.get("_co_dinh"))}
    da_co = set(co_dinh)                               # id đã dùng trong lần lưu này (+ id câu cố định)
    khoa = {c["key"] for c in cot_cua(p)}
    ra, thay = [], set()
    for i, r in enumerate(ds, 1):
        rid = r.get("_id")
        goc = cu_dong.get(rid) if rid in co_dinh else None
        if goc is not None:
            if rid in thay:
                loi.append(f"{ten}: dòng {i} lặp.")
                continue
            thay.add(rid)
        elif kieu == DS_KIEM and not cint(p.get("them_dong")):
            loi.append(f"{ten}: không thêm dòng ngoài các câu in sẵn.")
            continue
        la = sorted(k for k in r if not str(k).startswith("_") and k not in khoa and k not in KHOA_RIENG)
        if la:
            loi.append(f"{ten} dòng {i}: cột lạ {', '.join(la)}.")
        if goc is not None and cint(goc.get("_tieu_de")):
            ra.append(dict(goc))
            continue
        x = {}
        for c in cot:
            k = c["key"]
            if goc is not None and k in hoi:
                if not _trong(goc.get(k)):
                    x[k] = goc[k]
                continue
            v = _sach_o(c, r.get(k), tra, loi, f"{ten} dòng {i}")
            if v is not None:
                x[k] = v
        if goc is None and not x:
            continue                                   # dòng thêm còn trống — bỏ
        if goc is not None:
            x.update({k: goc[k] for k in goc if str(k).startswith("_")})
        else:
            hop = bool(rid) and re.fullmatch(r"t\d{1,4}", str(rid)) and rid not in da_co
            x["_id"] = rid if hop else _id_moi(da_co)
            da_co.add(x["_id"])
        ra.append(x)
    if kieu == DS_KIEM:
        mat = [cu_dong[k] for k in co_dinh if k not in thay]
        if mat:
            loi.append(f"{ten}: không bỏ được câu in sẵn ({len(mat)} dòng).")
    gia_tri = {"dong": ra}
    if cu.get("keo"):
        gia_tri["keo"] = cu["keo"]
    return tinh_phan(p, gia_tri), loi


def sach_noi_dung(dn_phan, moi, cu=None, tra=None):
    """(nội dung sạch, [lỗi]) của cả biên bản — chỉ phần có trong định nghĩa; phần không gửi thì giữ như cũ."""
    moi, cu = dict(moi or {}), dict(cu or {})
    la = sorted(k for k in moi if k not in {p.get("key") for p in dn_phan})
    loi = [f"Phần lạ: {', '.join(la)}."] if la else []
    ra = {}
    for p in dn_phan:
        k = p["key"]
        if k not in moi:
            if k in cu:
                ra[k] = cu[k]
            continue
        v, e = sach_phan(p, moi[k], cu.get(k), tra)
        loi += e
        if v:
            ra[k] = v
    return ra, loi


def thieu(dn_phan, nd):
    """[câu báo] các ô / dòng bắt buộc còn trống — kiểm lúc gửi ký."""
    dau = gia_tri_dau(nd)
    ra = []
    for p in dn_phan:
        if not phan_ap_dung(p, dau) or p.get("kieu") == KEO:
            continue
        ten = p.get("tieu_de") or p.get("key")
        v = nd.get(p["key"]) or {}
        cot = [c for c in cot_nhap(p) if cint(c.get("bat_buoc"))]
        if p.get("kieu") == VAN_BAN:
            g = v.get("gia_tri") or {}
            for c in cot:
                if (not cint(g.get(c["key"]))) if c.get("kieu") == "Check" else _trong(g.get(c["key"])):
                    ra.append(f"{ten}: chưa ghi {c.get('nhan')}.")
            continue
        dong = [r for r in v.get("dong") or [] if not cint(r.get("_tieu_de"))]
        if cint(p.get("bat_buoc")) and not dong:
            ra.append(f"{ten}: chưa có dòng nào.")
        for i, r in enumerate(v.get("dong") or [], 1):
            if p.get("kieu") == DS_KIEM and not dong_ap_dung(p, r, dau):
                continue
            for c in cot:
                if (not cint(r.get(c["key"]))) if c.get("kieu") == "Check" else _trong(r.get(c["key"])):
                    ra.append(f"{ten} dòng {i}: chưa ghi {c.get('nhan')}.")
    return ra


def dong_kph(dn_phan, nd):
    """[{phan, dong (_id), stt, cau, ket_luan}] — các dòng Không phù hợp của Danh sách kiểm (nút Lập BM.01.07)."""
    dau = gia_tri_dau(nd)
    ra = []
    for p in dn_phan:
        if p.get("kieu") != DS_KIEM or not phan_ap_dung(p, dau):
            continue
        kl = cot_ket_luan(p)
        if not kl:
            continue
        hoi = cot_hoi(p) or [c for c in cot_cua(p) if c is not kl][:1]
        for i, r in enumerate((nd.get(p["key"]) or {}).get("dong") or [], 1):
            if dong_ap_dung(p, r, dau) and la_khong_phu_hop(r.get(kl["key"])):
                cau = " — ".join(str(r.get(c["key"])) for c in hoi if not _trong(r.get(c["key"])))
                ra.append({"phan": p["key"], "dong": r.get("_id"), "stt": i, "cau": cau, "ket_luan": r[kl["key"]]})
    return ra


def mo_ta_kph(ma, so, p, r, ngay):
    """Mô tả điều không phù hợp ghi sang BM.01.07 — câu hỏi, kết luận, bằng chứng / ghi chú của dòng."""
    cot = cot_cua(p)
    phan = [f"{c.get('nhan')}: {r[c['key']]}" for c in cot if not _trong(r.get(c["key"]))]
    return _ngan(f"{ma} số {so} ngày {ngay_vn(ngay)} — {p.get('tieu_de') or p['key']}: " + "; ".join(phan), 1000)


# ── Ký ────────────────────────────────────────────────────────────────────────────────────

def ky_sap(ky):
    return sorted(ky or [], key=lambda s: (cint(s.get("thu_tu")) or 10 ** 6, cint(s.get("idx"))))


def can_ky_tay(ky, dau, ky_tay_khi=""):
    """Biên bản cần bản ký tay (scan): có ô ký tay, hoặc ô `ky_tay_khi` ở đầu phiếu được tích (BM.03.04 có đơn vị
    PCCC bên ngoài)."""
    return any(cint(s.get("ky_tay")) for s in ky or []) or bool(ky_tay_khi and cint((dau or {}).get(ky_tay_khi)))


def duoc_ky(s, user, roles, nguoi_lap):
    """Người này ký được ô `s` không (chưa xét thứ tự)."""
    if cint(s.get("ky_tay")):
        return False
    if s.get("user") and not s.get("ky_luc"):
        return s["user"] == user                       # ô đã gán người (trưởng đoàn của kế hoạch ĐGNB)
    if cint(s.get("nguoi_lap")):
        return bool(user) and user == nguoi_lap
    return bool(s.get("role")) and s["role"] in set(roles or ())


def o_ky_cua(ky, user, roles, nguoi_lap):
    """(ô người này ký bây giờ — chính phần tử của `ky`, câu báo) — ô chưa ký sớm nhất người này được ký, mọi ô bắt
    buộc trước nó đã ký. Ô ký tay không xếp hàng (ký trên giấy, khóa khi có bản scan)."""
    ds = ky_sap(ky)
    if any(s.get("ky_luc") and s.get("user") == user and not cint(s.get("ky_tay")) for s in ds):
        return None, "Bạn đã ký một ô của biên bản này — một người không ký hai ô."
    con = [s for s in ds if not cint(s.get("ky_tay")) and not s.get("ky_luc")]
    if not any(duoc_ky(s, user, roles, nguoi_lap) for s in con):
        return None, "Bạn không có ô ký nào còn trống trên biên bản này."
    for s in con:
        if duoc_ky(s, user, roles, nguoi_lap):
            return s, None
        if cint(s.get("bat_buoc")):
            return None, f"Chưa tới lượt bạn — đang chờ {s.get('vai_tro') or 'ô trước'} ký."
    return None, "Bạn không có ô ký nào còn trống trên biên bản này."


def o_cho(ky):
    """Ô bắt buộc (ký trên app) đang chờ ký — để hiện "chờ ai"."""
    return next((s for s in ky_sap(ky) if not cint(s.get("ky_tay")) and cint(s.get("bat_buoc"))
                 and not s.get("ky_luc")), None)


def du_chu_ky(ky, ban_ky_tay, dau=None, ky_tay_khi=""):
    """Đủ chữ ký để khóa: mọi ô bắt buộc ký trên app đã ký; cần ký tay thì phải có bản scan."""
    if any(cint(s.get("bat_buoc")) and not cint(s.get("ky_tay")) and not s.get("ky_luc") for s in ky or []):
        return False
    return not can_ky_tay(ky, dau, ky_tay_khi) or bool(ban_ky_tay)


def so_bien_ban(da_co, ky_hieu, nam):
    """Số kế tiếp trong năm của một mẫu: `da_co` = các số đã cấp ("05/BB-ISO"…)."""
    n = max((int(m.group(1)) for x in da_co or [] for m in [re.match(r"\s*(\d+)", str(x or ""))] if m), default=0)
    return f"{n + 1:02d}/{ky_hieu or nam}"


def ky_du_lieu(chu_ky, ngay, truoc=None):
    """(từ, đến) kỳ kéo dữ liệu: từ sau biên bản cùng mẫu lần trước tới ngày lập; chưa có lần trước / Khi phát sinh →
    theo chu kỳ (tuần 7 ngày, tháng 31, năm 365, khi phát sinh 30)."""
    d = _ngay(ngay)
    if truoc and chu_ky != PHAT_SINH and _ngay(truoc) < d:
        return _ngay(truoc) + timedelta(days=1), d
    return d - timedelta(days=KY_NGAY.get(chu_ky, 30) - 1), d


# ── Việc giao ─────────────────────────────────────────────────────────────────────────────

def viec_tu_noi_dung(dn_phan, nd):
    """[{noi_dung, phu_trach, nguoi, han, phan, dong}] — mỗi dòng Việc giao một việc; ô hạn (cột `han`) ở phần khác có
    giá trị → một việc theo dõi (thẩm tra lại, diễn tập lại…)."""
    dau = gia_tri_dau(nd)
    ra = []
    for p in dn_phan:
        if not phan_ap_dung(p, dau) or p.get("kieu") == KEO:
            continue
        v = nd.get(p["key"]) or {}
        ten = p.get("tieu_de") or p["key"]
        if p.get("kieu") == VIEC_GIAO:
            for i, r in enumerate(v.get("dong") or [], 1):
                if _trong(r.get("viec")):
                    continue
                ra.append({"noi_dung": _ngan(r["viec"], 1000), "phu_trach": r.get("phu_trach") or None,
                           "han": r.get("han") or None, "phan": p["key"], "dong": i, "nguoi": None})
            continue
        han = [c for c in cot_cua(p) if cint(c.get("han")) and c.get("kieu") == "Date"]
        if not han:
            continue
        if p.get("kieu") == VAN_BAN:
            g = v.get("gia_tri") or {}
            for c in han:
                if not _trong(g.get(c["key"])):
                    ra.append({"noi_dung": _ngan(f"{ten}: {c.get('nhan')}", 1000), "phu_trach": None,
                               "han": g[c["key"]], "phan": p["key"], "dong": 0, "nguoi": None})
            continue
        dau_cot = [c for c in cot_cua(p) if c.get("kieu") in ("Data", "Text") and not cint(c.get("han"))]
        tn = next((c for c in cot_cua(p) if c.get("key") in ("trach_nhiem", "nguoi_thuc_hien")), None)
        for i, r in enumerate(v.get("dong") or [], 1):
            if p.get("kieu") == DS_KIEM and not dong_ap_dung(p, r, dau):
                continue
            mo_ta = " — ".join(str(r[c["key"]]) for c in dau_cot[:2] if not _trong(r.get(c["key"])))
            for c in han:
                if not _trong(r.get(c["key"])):
                    ra.append({"noi_dung": _ngan(f"{c.get('nhan')}: {mo_ta}" if mo_ta else c.get("nhan"), 1000),
                               "phu_trach": None, "han": r[c["key"]], "phan": p["key"], "dong": i,
                               "nguoi": (str(r.get(tn["key"])) if tn and not _trong(r.get(tn["key"])) else None)})
    return ra


def khop_ho_so(ho_so, ma):
    """Ô "Hồ sơ / biểu mẫu" của một việc định kỳ có đúng mã này (tách theo , ; /) không."""
    return not _trong(ho_so) and str(ma).upper() in {x.strip().upper() for x in re.split(r"[,;/]", str(ho_so))}


# ── Đánh giá nội bộ ───────────────────────────────────────────────────────────────────────

def chuyen_gia(nd_kh):
    """Các chuyên gia của kế hoạch BM.01.05: [{user, trach_nhiem, ky_hieu, bo_phan}]."""
    return [{"user": r.get("chuyen_gia"), "trach_nhiem": r.get("trach_nhiem") or "", "ky_hieu": r.get("ky_hieu") or "",
             "bo_phan": r.get("bo_phan") or ""}
            for r in ((nd_kh or {}).get("chuyen_gia") or {}).get("dong") or [] if r.get("chuyen_gia")]


def truong_doan(nd_kh):
    return next((x for x in chuyen_gia(nd_kh) if x["trach_nhiem"] == TRUONG_DOAN), None)


def _cg_cua_o(o, cgs):
    """Chuyên gia nhắc tới trong ô "Chuyên gia đánh giá" của một dòng lịch: "Tất cả…" → mọi người; còn lại ký hiệu
    (A, B…) hoặc tên tài khoản, cách nhau bởi , ; / hoặc khoảng trắng."""
    s = khong_dau(o)
    if not s:
        return []
    if s.startswith("tat ca"):
        return list(cgs)
    tu = {x for x in re.split(r"[,;/\s]+", s) if x}
    return [x for x in cgs if khong_dau(x["ky_hieu"]) in tu or khong_dau(x["user"]) in tu]


def bo_phan_cua(nd_kh, cg):
    """Bộ phận chuyên gia `cg` được phân đánh giá trong lịch BM.01.05."""
    cgs = chuyen_gia(nd_kh)
    ra = []
    for r in ((nd_kh or {}).get("chi_tiet") or {}).get("dong") or []:
        bp = str(r.get("bo_phan") or "").strip()
        if bp and cg in _cg_cua_o(r.get("chuyen_gia"), cgs) and bp not in ra:
            ra.append(bp)
    return ra


def loi_doc_lap(nd_kh, roles_cua=None, du=False):
    """Tính độc lập của đoàn đánh giá nội bộ (QT.01): chuyên gia không đánh giá bộ phận của mình; Trưởng Ban ISO
    (người biên soạn hệ thống) không làm trưởng đoàn; `du` (gửi ký) → phải có đúng một trưởng đoàn."""
    cgs = chuyen_gia(nd_kh)
    loi = []
    td = [x for x in cgs if x["trach_nhiem"] == TRUONG_DOAN]
    if du and len(td) != 1:
        loi.append("Kế hoạch đánh giá phải có đúng một trưởng đoàn (Giám đốc chỉ định khi phê duyệt).")
    for x in td:
        if roles_cua and ISO in set(roles_cua(x["user"]) or ()):
            loi.append(f"{x['user']} là Trưởng Ban ISO (người biên soạn hệ thống) — không làm trưởng đoàn (QT.01).")
    for r in ((nd_kh or {}).get("chi_tiet") or {}).get("dong") or []:
        bp = khong_dau(r.get("bo_phan"))
        if not bp:
            continue
        for x in _cg_cua_o(r.get("chuyen_gia"), cgs):
            if khong_dau(x["bo_phan"]) == bp:
                loi.append(f"Chuyên gia {x['ky_hieu'] or x['user']} thuộc {r['bo_phan']} — không đánh giá bộ phận "
                           f"của mình (QT.01).")
    return list(dict.fromkeys(loi))


def loi_checklist(nd_kh, user, bo_phan):
    """Lập / sửa BM.01.06: người lập phải là chuyên gia của kế hoạch và không thuộc bộ phận được đánh giá."""
    cg = next((x for x in chuyen_gia(nd_kh) if x["user"] == user), None)
    if not cg:
        return "Chỉ chuyên gia có tên trong kế hoạch BM.01.05 lập checklist của đợt."
    if bo_phan and khong_dau(cg["bo_phan"]) and khong_dau(cg["bo_phan"]) == khong_dau(bo_phan):
        return f"Bạn thuộc {cg['bo_phan']} — không đánh giá bộ phận của mình (QT.01)."
    return None


def tong_hop_dgnb(checklist):
    """Gom các BM.01.06 của một đợt. `checklist` = [{bo_phan, dong: [{yeu_cau, ket_luan, bang_chung}]}].
    → ({bộ phận: {kph, luu_y}}, [dòng Lưu ý {noi_dung, trach_nhiem}])."""
    dem, luu_y = {}, []
    for c in checklist:
        bp = str(c.get("bo_phan") or "").strip() or "—"
        d = dem.setdefault(bp, {"kph": 0, "luu_y": 0})
        for r in c.get("dong") or []:
            kl = str(r.get("ket_luan") or "").strip()
            if kl == "KPH":
                d["kph"] += 1
            elif kl == LUU_Y:
                d["luu_y"] += 1
                nd = str(r.get("yeu_cau") or "").strip()
                if r.get("bang_chung"):
                    nd = f"{nd} — {r['bang_chung']}" if nd else str(r["bang_chung"])
                luu_y.append({"noi_dung": _ngan(nd, 2000), "trach_nhiem": bp})
    return dem, luu_y


# ── Sơ đồ công đoạn (BM.HACCP.01) ─────────────────────────────────────────────────────────

def ten_cong_doan(x):
    """"3 Rang" giữ nguyên; "Bột: rang lạc" → "3 Bột: rang lạc" (số theo thứ tự trên sơ đồ)."""
    ten = str(x.get("ten") or x.get("name") or "").strip()
    return ten if re.match(r"\d", ten) else f"{cint(x.get('thu_tu'))} {ten}".strip()


def van_tay(ds):
    """Dấu vân tay danh sách công đoạn của một dây chuyền (thứ tự + tên) — đổi là phải xác nhận lại sơ đồ."""
    s = "\n".join(ten_cong_doan(x) for x in sorted(ds, key=lambda x: (cint(x.get("thu_tu")), str(x.get("ten")))))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


def day_chuyen_cua(dau):
    """Dây chuyền chọn ở đầu phiếu: BM.HACCP.01 ô san_pham, BM.HACCP.02 ô ke_hoach."""
    v = khong_dau((dau or {}).get("san_pham") or (dau or {}).get("ke_hoach"))
    if not v:
        return None
    return BANH if (v.startswith("banh") or v.startswith("kh.haccp.01")) else BOT


def so_do_can_xac_nhan(cong_doan, xac_nhan):
    """[{day_chuyen, ly_do, ngay}] — dây chuyền phải xác nhận lại sơ đồ tại hiện trường (hàm thuần).
    `cong_doan` = {dây chuyền: [{ten, thu_tu}]} (đang dùng); `xac_nhan` = {dây chuyền: {ngay, van_tay}} — BM.HACCP.01 ký
    đủ gần nhất, hoặc mốc lúc triển khai (SX QC Setting.so_do_moc: bánh đã xác nhận bằng giấy 22/9/2026). Danh sách
    công đoạn đổi (thêm, ngừng, đổi tên, đổi thứ tự) so với lần xác nhận → nhắc; chưa xác nhận lần nào (bột) → nhắc."""
    ra = []
    for dc in (BANH, BOT):
        ds = cong_doan.get(dc) or []
        if not ds:
            continue
        x = xac_nhan.get(dc)
        if not x:
            ra.append({"day_chuyen": dc, "ly_do": f"chưa có biên bản xác nhận sơ đồ {len(ds)} công đoạn", "ngay": None})
        elif x.get("van_tay") != van_tay(ds):
            ra.append({"day_chuyen": dc, "ly_do": f"danh sách công đoạn đổi sau lần xác nhận {ngay_vn(x['ngay'])}",
                       "ngay": str(x["ngay"])})
    return ra


# ── Đọc DB ────────────────────────────────────────────────────────────────────────────────

TRUONG_MAU = ("ma", "ten", "quy_trinh", "lan_ban_hanh", "chu_ky_lap", "ngung", "nhan_ngay", "ky_hieu_so", "goc_mau",
              "ky_tay_khi", "nguon_car", "ghi_chu", "creation")
TRUONG_PHAN = ("key", "tieu_de", "kieu", "cot", "dong_mau", "nguon", "tinh", "chi_khi", "bat_buoc", "them_dong", "idx")
TRUONG_KY = ("vai_tro", "role", "nguoi_lap", "thu_tu", "bat_buoc", "ky_tay", "idx")


def mau_tu_doc(doc):
    """SX Mau Bien Ban (doc) → dict thuần (phan đã giải cột JSON)."""
    m = {f: doc.get(f) for f in TRUONG_MAU}
    m["name"] = doc.get("name") or m["ma"]
    m["phan"] = [dict({f: r.get(f) for f in TRUONG_PHAN}, cot=cot_cua(r)) for r in doc.get("phan") or []]
    m["ky"] = ky_sap([{f: r.get(f) for f in TRUONG_KY} for r in doc.get("ky") or []])
    for o in ("vai_lap", "vai_xem"):
        m[o] = sorted({r.get("role") for r in doc.get(o) or [] if r.get("role")})
    return m


def mau(ma):
    if not ma or not frappe.db.exists(PT, ma):
        return None
    return mau_tu_doc(frappe.get_doc(PT, ma))


def ds_mau(ngung=False):
    """Mọi mẫu (dict thuần, đủ phần / ô ký / vai) — mỗi bảng một lượt truy vấn."""
    ds = frappe.get_all(PT, filters={} if ngung else {"ngung": 0}, fields=["name"] + list(TRUONG_MAU),
                        order_by="ma asc")
    ten = [x.name for x in ds] or [""]
    phan, ky, vai = {}, {}, {}
    for r in frappe.get_all(PT_PHAN, filters={"parenttype": PT, "parent": ("in", ten)},
                            fields=["parent"] + list(TRUONG_PHAN), order_by="idx asc"):
        phan.setdefault(r.parent, []).append(dict({f: r.get(f) for f in TRUONG_PHAN}, cot=cot_cua(r)))
    for r in frappe.get_all(PT_KY_MAU, filters={"parenttype": PT, "parent": ("in", ten)},
                            fields=["parent"] + list(TRUONG_KY)):
        ky.setdefault(r.parent, []).append({f: r.get(f) for f in TRUONG_KY})
    for r in frappe.get_all(PT_VAI, filters={"parenttype": PT, "parent": ("in", ten)},
                            fields=["parent", "parentfield", "role"]):
        vai.setdefault((r.parent, r.parentfield), set()).add(r.role)
    ra = []
    for x in ds:
        m = {f: x.get(f) for f in TRUONG_MAU}
        m.update(name=x.name, phan=sorted(phan.get(x.name, []), key=lambda p: cint(p.get("idx"))),
                 ky=ky_sap(ky.get(x.name, [])), vai_lap=sorted(vai.get((x.name, "vai_lap"), ())),
                 vai_xem=sorted(vai.get((x.name, "vai_xem"), ())))
        ra.append(m)
    return ra


def dinh_nghia_bb(doc):
    """Bản chụp định nghĩa của một biên bản (phần lúc lập); biên bản cũ thiếu bản chụp → đọc mẫu hiện tại."""
    d = doc_json(doc.get("dinh_nghia"), {}) or {}
    if not d.get("phan"):
        m = mau(doc.get("mau")) or {}
        d = chup_mau(m)
    return d


def chup_mau(m):
    """Phần của mẫu chép vào biên bản lúc lập (không kèm vai — quyền theo mẫu hiện tại)."""
    return {"ma": m.get("ma") or m.get("name"), "ten": m.get("ten"), "quy_trinh": m.get("quy_trinh"),
            "lan_ban_hanh": m.get("lan_ban_hanh"), "nhan_ngay": m.get("nhan_ngay") or "Ngày",
            "ky_hieu_so": m.get("ky_hieu_so"), "ky_tay_khi": m.get("ky_tay_khi"), "nguon_car": m.get("nguon_car"),
            "goc_mau": m.get("goc_mau"), "chu_ky_lap": m.get("chu_ky_lap"),
            "phan": [{f: p.get(f) for f in TRUONG_PHAN if f != "idx"} for p in m.get("phan") or []]}


# ── Hàm kéo dữ liệu (bản chụp) ────────────────────────────────────────────────────────────
# Mỗi hàm nhận ctx = {ngay, tu, den, mau, dau, bien_ban, goc (nội dung biên bản gốc), ham: {nhac, bc_thang, lo_thu_hoi}}
# → {cot: [{key, nhan}], dong: [{key: chữ}], ghi_chu} (chữ đã định dạng — bản chụp in ra y như lúc lập).

def _bc(cot, dong, ghi_chu="", **k):
    return dict({"cot": [{"key": a, "nhan": b} for a, b in cot], "dong": dong, "ghi_chu": ghi_chu}, **k)


def _ky_chu(ctx):
    return f"{ngay_vn(ctx['tu'])} – {ngay_vn(ctx['den'])}"


def keo_su_co_ky(ctx):
    tu, den = ctx["tu"], ctx["den"]
    f = ["name", "ngay", "trang_thai", "muc_do", "loai", "mo_ta", "dong_ngay", "dien_tap"]
    moi = frappe.get_all("SX Su Co", filters={"ngay": ("between", [tu, den])}, fields=f, order_by="ngay asc")
    dong = frappe.get_all("SX Su Co", filters={"trang_thai": "Đóng", "dong_ngay": ("between", [tu, den])}, fields=f,
                          order_by="dong_ngay asc")
    mo = frappe.get_all("SX Su Co", filters={"trang_thai": "Mở"}, fields=f, order_by="ngay asc")

    def h(nhom, x):
        return {"nhom": nhom, "phieu": x.name, "ngay": ngay_vn(x.ngay),
                "muc_do": x.muc_do or "", "noi_dung": _ngan(f"{'[DIỄN TẬP] ' if cint(x.dien_tap) else ''}"
                                                           f"{x.loai or ''}: {x.mo_ta or ''}".strip(": "), 140),
                "trang_thai": x.trang_thai or ""}
    ds = [h("Mở mới trong kỳ", x) for x in moi] + [h("Đóng trong kỳ", x) for x in dong] + [h("Còn mở", x) for x in mo]
    return _bc((("nhom", "Nhóm"), ("phieu", "Phiếu"), ("ngay", "Ngày"), ("muc_do", "Mức"), ("noi_dung", "Nội dung"),
                ("trang_thai", "Trạng thái")), ds,
               f"Kỳ {_ky_chu(ctx)}: {len(moi)} phiếu mở mới, {len(dong)} đóng, {len(mo)} còn mở (BM.08.02).")


def keo_khieu_nai_ky(ctx):
    tu, den = ctx["tu"], ctx["den"]
    f = ["name", "opening_date", "status", "subject", "customer", "custom_lo", "custom_san_pham", "resolution_date"]
    mo_ky = frappe.get_all("Issue", filters={"custom_khieu_nai": 1, "opening_date": ("between", [tu, den])}, fields=f,
                           order_by="opening_date asc")
    dong = [x for x in frappe.get_all("Issue", filters={"custom_khieu_nai": 1,
                                                         "status": ("in", ["Resolved", "Closed"])}, fields=f)
            if x.get("resolution_date") and tu <= getdate(x.resolution_date) <= den]
    con = frappe.get_all("Issue", filters={"custom_khieu_nai": 1, "status": ("in", ["Open", "Replied", "On Hold"])},
                         fields=f, order_by="opening_date asc")

    def h(nhom, x):
        return {"nhom": nhom, "phieu": x.name, "ngay": ngay_vn(x.opening_date), "khach": x.customer or "",
                "noi_dung": _ngan(" · ".join(str(v) for v in (x.subject, x.custom_san_pham, x.custom_lo) if v), 140),
                "trang_thai": x.status or ""}
    ds = [h("Mở trong kỳ", x) for x in mo_ky] + [h("Đóng trong kỳ", x) for x in dong] + [h("Còn mở", x) for x in con]
    return _bc((("nhom", "Nhóm"), ("phieu", "Phiếu"), ("ngay", "Ngày"), ("khach", "Khách"), ("noi_dung", "Nội dung"),
                ("trang_thai", "Trạng thái")), ds,
               f"Kỳ {_ky_chu(ctx)}: {len(mo_ky)} khiếu nại mới, {len(dong)} đóng, {len(con)} còn mở (BM.11.01).")


def keo_khac_phuc_mo(ctx):
    den = ctx["den"]
    ds = frappe.get_all("SX Khac Phuc", filters={"trang_thai": ("in", ["Mở", "Chờ kiểm tra"])},
                        fields=["name", "ngay", "nguon", "mo_ta", "han", "trang_thai", "nguoi_thuc_hien"],
                        order_by="han asc")
    ra = []
    for x in ds:
        qua = x.trang_thai == "Mở" and x.han and getdate(x.han) < den
        if not (qua or x.trang_thai == "Chờ kiểm tra"):
            continue
        ra.append({"phieu": x.name, "nguon": x.nguon or "", "noi_dung": _ngan(x.mo_ta, 140),
                   "nguoi": x.nguoi_thuc_hien or "", "han": ngay_vn(x.han) if x.han else "",
                   "tinh_trang": f"quá hạn {(den - getdate(x.han)).days} ngày" if qua else "chờ kiểm tra hiệu lực"})
    return _bc((("phieu", "Phiếu"), ("nguon", "Nguồn"), ("noi_dung", "Không phù hợp"), ("nguoi", "Người làm"),
                ("han", "Hạn"), ("tinh_trang", "Tình trạng")), ra,
               f"{sum(1 for x in ra if x['tinh_trang'].startswith('quá'))} phiếu quá hạn, "
               f"{sum(1 for x in ra if x['tinh_trang'].startswith('chờ'))} chờ kiểm tra hiệu lực (BM.01.07).")


def keo_nhac_cao(ctx):
    f = (ctx.get("ham") or {}).get("nhac")
    ds = [x for x in (f() if f else []) if x.get("muc_do") == "cao"]
    return _bc((("tieu_de", "Việc đang treo (mức cao)"), ("chi_tiet", "Chi tiết")),
               [{"tieu_de": x.get("tieu_de") or "", "chi_tiet": _ngan(x.get("chi_tiet"), 200)} for x in ds],
               f"{len(ds)} mục nhắc mức cao lúc lập biên bản.")


def _viec_cua(ten_bb):
    """Việc giao chưa xong của các biên bản (đọc trạng thái việc định kỳ đã tạo)."""
    rows = frappe.get_all(PT_VIEC, filters={"parenttype": PT_BB, "parent": ("in", ten_bb or [""])},
                          fields=["parent", "noi_dung", "phu_trach", "nguoi", "han", "viec_dinh_ky", "xong"],
                          order_by="idx asc")
    vd = {x.name: x for x in frappe.get_all("SX Viec Dinh Ky", filters={"name": ("in", [r.viec_dinh_ky for r in rows
                                                                                          if r.viec_dinh_ky] or [""])},
                                             fields=["name", "ngung", "lan_cuoi"])}
    ra = []
    for r in rows:
        v = vd.get(r.viec_dinh_ky)
        if cint(r.xong) or (v and (cint(v.ngung) or v.lan_cuoi)):
            continue
        ra.append(r)
    return ra


def keo_viec_bien_ban_truoc(ctx):
    """Việc giao chưa xong của biên bản cùng mẫu lần trước (BM.01.11: kèm hành động BM.01.10 chưa xong)."""
    mau_ds = [ctx["mau"]] + ([XEM_XET_LD] if ctx["mau"] == HOP_ISO else [])
    ten, so = [], {}
    for m in mau_ds:
        loc = {"mau": m, "trang_thai": DA_KY, "ngay": ("<=", ctx["ngay"])}
        if ctx.get("bien_ban"):
            loc["name"] = ("!=", ctx["bien_ban"])
        ds = frappe.get_all(PT_BB, filters=loc, fields=["name", "so", "ngay", "mau"], order_by="ngay desc, creation desc")
        chon = ds[:1] if m == ctx["mau"] else ds
        for x in chon:
            ten.append(x.name)
            so[x.name] = f"{x.mau} số {x.so}"
    nguoi = {}
    ra = []
    for r in _viec_cua(ten):
        if r.phu_trach and r.phu_trach not in nguoi:
            nguoi[r.phu_trach] = frappe.db.get_value("User", r.phu_trach, "full_name") or r.phu_trach
        con = (getdate(r.han) - ctx["ngay"]).days if r.han else None
        ra.append({"bien_ban": so.get(r.parent, r.parent), "viec": _ngan(r.noi_dung, 200),
                   "nguoi": nguoi.get(r.phu_trach) or r.nguoi or "", "han": ngay_vn(r.han) if r.han else "",
                   "tinh_trang": "" if con is None else (f"quá hạn {-con} ngày" if con < 0 else f"còn {con} ngày")})
    return _bc((("bien_ban", "Biên bản"), ("viec", "Việc chưa xong"), ("nguoi", "Người thực hiện"), ("han", "Hạn"),
                ("tinh_trang", "Tình trạng")), ra, f"{len(ra)} việc giao chưa xong.")


def keo_bc_thang(ctx):
    from sx.qc import bao_cao as BC
    d = ctx["ngay"]
    t = (d.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    f = (ctx.get("ham") or {}).get("bc_thang")
    dl = f(t) if f else None
    if not dl:
        return _bc((), [], "", loi="Chưa lấy được báo cáo tháng.")
    ra = [{"chi_so": x["ten"], "thang": BC.hien(x["ky"], x["don_vi"]), "nam": BC.hien(x["nam"], x["don_vi"])}
          for x in dl.get("bang") or []]
    return _bc((("chi_so", "Chỉ số (BM.01.12)"), ("thang", f"Tháng {t[5:7]}/{t[:4]}"), ("nam", "Lũy kế năm")), ra,
               f"Báo cáo phân tích dữ liệu tháng {t[5:7]}/{t[:4]} (BM.01.12).")


def _nd_bb(name):
    return doc_json(frappe.db.get_value(PT_BB, name, "noi_dung"), {}) or {}


def keo_dgnb_ket_qua(ctx):
    x = frappe.get_all(PT_BB, filters={"mau": DGNB_BC, "trang_thai": DA_KY}, fields=["name", "so", "ngay"],
                       order_by="ngay desc, creation desc", limit=1)
    if not x:
        return _bc((), [], "Chưa có báo cáo đánh giá nội bộ BM.01.09 ký đủ trên app.")
    nd = _nd_bb(x[0].name)
    ra = [{"bo_phan": r.get("bo_phan") or "", "kph": str(r.get("so_kph") or 0), "luu_y": str(r.get("so_luu_y") or 0)}
          for r in (nd.get("noi_dung") or {}).get("dong") or []]
    kl = ((nd.get("ket_luan") or {}).get("gia_tri") or {})
    return _bc((("bo_phan", "Bộ phận được đánh giá"), ("kph", "KPH"), ("luu_y", "Lưu ý")), ra,
               _ngan(f"BM.01.09 số {x[0].so} ngày {ngay_vn(x[0].ngay)}. Kết luận: {kl.get('ket_luan') or '…'}"
                     + (f" Kiến nghị: {kl['kien_nghi']}" if kl.get("kien_nghi") else ""), 1500))


def keo_thay_doi_ky(ctx):
    tu, den = ctx["tu"], ctx["den"]
    ra = []
    for x in frappe.get_all("SX De Nghi Tai Lieu", filters={"trang_thai": "Đã duyệt"},
                            fields=["name", "loai_yeu_cau", "ma_de_xuat", "ten_de_xuat", "duyet_luc"],
                            order_by="duyet_luc asc"):
        if x.duyet_luc and tu <= getdate(x.duyet_luc) <= den:
            ra.append({"loai": "BM.01.01", "so": x.name, "ngay": ngay_vn(x.duyet_luc),
                       "noi_dung": _ngan(f"{x.loai_yeu_cau or ''}: {x.ma_de_xuat or ''} {x.ten_de_xuat or ''}", 160)})
    for x in frappe.get_all("SX Dot Ban Hanh", filters={"trang_thai": "Đã ban hành",
                                                       "ngay_ban_hanh": ("between", [tu, den])},
                            fields=["name", "so_quyet_dinh", "ngay_ban_hanh"], order_by="ngay_ban_hanh asc"):
        n = frappe.db.count("SX Dot Ban Hanh Muc", {"parenttype": "SX Dot Ban Hanh", "parent": x.name})
        ra.append({"loai": "Đợt ban hành", "so": x.name, "ngay": ngay_vn(x.ngay_ban_hanh),
                   "noi_dung": f"QĐ {x.so_quyet_dinh or '…'} — {n} tài liệu"})
    return _bc((("loai", "Loại"), ("so", "Số"), ("ngay", "Ngày"), ("noi_dung", "Nội dung")), ra,
               f"Kỳ {_ky_chu(ctx)}: thay đổi tài liệu đã duyệt, đợt ban hành.")


def keo_rui_ro_ben_quan_tam(ctx):
    ra = []
    for ma in ("BM.05.02", "BM.05.01"):
        for x in frappe.get_all(SO.PT_DONG, filters={"so": ma, "trang_thai": ("!=", SO.NGUNG)},
                                fields=["name", "du_lieu"], order_by="creation asc"):
            du = SO.doc_json(x.du_lieu)
            if ma == "BM.05.02":
                if du.get("cap_do") != "Cấp độ 1":
                    continue
                ra.append({"bang": "BM.05.02 cấp độ 1", "noi_dung": _ngan(f"{du.get('rui_ro') or ''} "
                                                                          f"({du.get('hoat_dong') or ''})", 200),
                           "danh_gia": f"RR = {du.get('rr') or '…'}",
                           "bien_phap": _ngan(du.get("bien_phap"), 200), "trach_nhiem": du.get("trach_nhiem") or ""})
            else:
                ra.append({"bang": f"BM.05.01 {du.get('nhom') or ''}".strip(),
                           "noi_dung": _ngan(f"{du.get('ben_quan_tam') or ''}: {du.get('noi_dung_tuan_thu') or ''}", 200),
                           "danh_gia": "", "bien_phap": _ngan(du.get("cach_dap_ung"), 200),
                           "trach_nhiem": du.get("trach_nhiem") or ""})
    return _bc((("bang", "Bảng"), ("noi_dung", "Rủi ro / bên quan tâm"), ("danh_gia", "Đánh giá"),
                ("bien_phap", "Biện pháp / cách đáp ứng"), ("trach_nhiem", "Trách nhiệm")), ra,
               f"{sum(1 for x in ra if x['bang'].startswith('BM.05.02'))} rủi ro cấp độ 1; "
               f"{sum(1 for x in ra if x['bang'].startswith('BM.05.01'))} bên quan tâm.")


def keo_kiem_nghiem_nam(ctx):
    dau = ctx["ngay"].replace(month=1, day=1)
    ds = frappe.get_all("SX Kiem Nghiem", filters={"ngay_gui": ("between", [dau, ctx["den"]])},
                        fields=["name", "doi_tuong", "ten_san_pham", "mo_ta_mau", "ngay_gui", "ket_qua", "ngay_kq",
                                "so_phieu"], order_by="ngay_gui asc")
    ra = [{"doi_tuong": x.doi_tuong or "", "mau": _ngan(x.ten_san_pham or x.mo_ta_mau, 120),
           "ngay_gui": ngay_vn(x.ngay_gui), "ket_qua": x.ket_qua or "chờ kết quả",
           "ngay_kq": ngay_vn(x.ngay_kq) if x.ngay_kq else "", "so_phieu": x.so_phieu or ""} for x in ds]
    return _bc((("doi_tuong", "Đối tượng"), ("mau", "Mẫu"), ("ngay_gui", "Gửi"), ("ket_qua", "Kết quả"),
                ("ngay_kq", "Ngày KQ"), ("so_phieu", "Số phiếu")), ra,
               f"Năm {dau.year}: {len(ra)} mẫu gửi, {sum(1 for x in ra if x['ket_qua'] == 'Đạt')} đạt, "
               f"{sum(1 for x in ra if x['ket_qua'] == 'Không đạt')} không đạt.")


def ds_cong_doan(day_chuyen):
    ds = frappe.get_all("SX QC Cong Doan", filters={"day_chuyen": day_chuyen, "ngung": 0},
                        fields=["name", "ten", "thu_tu", "ma", "modified"])
    return sorted(ds, key=lambda x: (cint(x.get("thu_tu")), str(x.get("ten") or "")))


def _keo_cong_doan(dc):
    ds = ds_cong_doan(dc)
    return _bc((("cong_doan", "Công đoạn (số, tên theo sơ đồ)"),),
               [{"cong_doan": ten_cong_doan(x)} for x in ds],
               f"Dây chuyền {dc.lower()}: {len(ds)} công đoạn đang dùng (danh mục công đoạn của app).",
               day_chuyen=dc, van_tay=van_tay(ds))


def keo_cong_doan_banh(ctx):
    return _keo_cong_doan(BANH)


def keo_cong_doan_bot(ctx):
    return _keo_cong_doan(BOT)


def _keo_oprp(dc):
    return _bc((("oprp", "oPRP"), ("moi_nguy", "Mối nguy"), ("bien_phap", "Biện pháp kiểm soát, giới hạn")),
               [{"oprp": a, "moi_nguy": b, "bien_phap": c} for a, b, c in OPRP[dc]],
               "oPRP hiện hành: bánh oPRP-1, 2 (KH.HACCP.01); bột oPRP-5 đến 9 (KH.HACCP.02).", day_chuyen=dc)


def keo_oprp_banh(ctx):
    return _keo_oprp(BANH)


def keo_oprp_bot(ctx):
    return _keo_oprp(BOT)


def keo_dien_tap_truy_xuat(ctx):
    ds = frappe.get_all("SX Dien Tap Truy Xuat", filters={"ket_thuc": ("is", "set"), "ngay": ("<=", ctx["den"])},
                        fields=["name", "ngay", "lo", "ten_san_pham", "hsd", "so_phut", "can_bang_pt", "dat", "so_khach",
                                "so_ncc"], order_by="ngay desc, ket_thuc desc", limit=3)
    ra = [{"phieu": x.name, "ngay": ngay_vn(x.ngay), "lo": f"{x.ten_san_pham or ''} {x.lo or ''}".strip(),
           "hsd": ngay_vn(x.hsd) if x.hsd else "", "phut": str(cint(x.so_phut)),
           "can_bang": f"{float(x.can_bang_pt or 0):g}%".replace(".", ","),
           "ket_qua": "Đạt" if cint(x.dat) else "Chưa đạt",
           "khach_ncc": f"{cint(x.so_khach)} khách · {cint(x.so_ncc)} NCC"} for x in ds]
    return _bc((("phieu", "Phiếu (BM.02.04)"), ("ngay", "Ngày"), ("lo", "Sản phẩm, lô"), ("hsd", "HSD"),
                ("phut", "Phút truy xuất"), ("can_bang", "Cân bằng"), ("ket_qua", "Cân bằng ≥ 98%"),
                ("khach_ncc", "Truy được")), ra,
               "Diễn tập truy xuất trên app gần nhất (tab Truy xuất). Tiêu chí: truy ngược, truy xuôi mỗi chiều ≤ 2 giờ; "
               "cân bằng khối lượng ≥ 98%." if ra else "Chưa có lần diễn tập truy xuất nào trên app.")


def keo_lo_thu_hoi(ctx):
    f = (ctx.get("ham") or {}).get("lo_thu_hoi")
    ds = f() if f else []
    ra = []
    for lo in ds:
        ban = lo.get("ban") or [{"khach": "—", "so": 0}]
        for i, b in enumerate(ban):
            ra.append({"lo": f"{lo.get('ten') or ''} — lô {lo.get('batch')}" if i == 0 else "",
                       "hsd": ngay_vn(lo.get("hsd")) if i == 0 and lo.get("hsd") else "",
                       "khach": b.get("khach") or "", "da_ban": f"{float(b.get('so') or 0):g}",
                       "tra_ve": f"{float(b.get('tra_ve') or 0):g}" if b.get("tra_ve") else "",
                       "ton": f"{float(lo.get('ton') or 0):g}" if i == 0 else ""})
    return _bc((("lo", "Sản phẩm, lô"), ("hsd", "HSD"), ("khach", "Khách"), ("da_ban", "Đã bán"),
                ("tra_ve", "Đã thu về"), ("ton", "Tồn kho")), ra,
               f"{len(ds)} lô đang có cờ thu hồi." if ds else "Không có lô nào đang có cờ thu hồi.")


def keo_dong_vat_ky(ctx):
    ds = frappe.get_all("SX Dau Hieu Dong Vat", filters={"ngay": ("between", [ctx["tu"], ctx["den"]])},
                        fields=["tram", "khu", "ngay", "dau_hieu", "so_luong"], order_by="ngay asc")
    theo = {}
    for x in ds:
        t = theo.setdefault(x.tram or "—", {"khu": x.khu or "", "lan": 0, "sl": 0, "dh": [], "cuoi": None})
        t["lan"] += 1
        t["sl"] += cint(x.so_luong)
        if x.dau_hieu and x.dau_hieu not in t["dh"]:
            t["dh"].append(x.dau_hieu)
        t["cuoi"] = x.ngay
    ra = [{"tram": k, "khu": v["khu"], "lan": str(v["lan"]), "so_luong": str(v["sl"]), "dau_hieu": "; ".join(v["dh"]),
           "cuoi": ngay_vn(v["cuoi"])} for k, v in sorted(theo.items())]
    return _bc((("tram", "Trạm"), ("khu", "Khu"), ("lan", "Lần thấy"), ("so_luong", "Số lượng"),
                ("dau_hieu", "Dấu hiệu"), ("cuoi", "Gần nhất")), ra,
               f"Kỳ {_ky_chu(ctx)}: {len(ds)} lần ghi dấu hiệu ở {len(ra)} trạm (BM.PRP.03).")


def _checklist_dot(goc):
    ds = frappe.get_all(PT_BB, filters={"mau": DGNB_CL, "goc": goc}, fields=["name", "trang_thai"],
                        order_by="ngay asc, creation asc")
    ra = []
    for x in ds:
        nd = _nd_bb(x.name)
        ra.append({"bo_phan": gia_tri_dau(nd).get("bo_phan") or "",
                   "dong": [r for p in nd.values() if isinstance(p, dict) for r in p.get("dong") or []
                            if r.get("ket_luan")], "trang_thai": x.trang_thai})
    return ra


def keo_dgnb_luu_y(ctx):
    cl = _checklist_dot(ctx.get("goc_ten")) if ctx.get("goc_ten") else []
    _dem, luu_y = tong_hop_dgnb(cl)
    return _bc((("noi_dung", "Nội dung"), ("trach_nhiem", "Trách nhiệm")), luu_y,
               f"Gom từ {len(cl)} checklist BM.01.06 của đợt: {len(luu_y)} điểm lưu ý.")


def keo_dgnb_dem(ctx):
    cl = _checklist_dot(ctx.get("goc_ten")) if ctx.get("goc_ten") else []
    dem, _l = tong_hop_dgnb(cl)
    ra = [{"bo_phan": bp, "so_kph": d["kph"], "so_luu_y": d["luu_y"]} for bp, d in dem.items()]
    return _bc((("bo_phan", "Bộ phận"), ("so_kph", "KPH"), ("so_luu_y", "Lưu ý")), ra,
               f"Đếm từ {len(cl)} checklist BM.01.06 của đợt.")


def keo_dgnb_doan(ctx):
    nd = ctx.get("goc") or {}
    ra = []
    for x in chuyen_gia(nd):
        ten = frappe.db.get_value("User", x["user"], "full_name") or x["user"]
        ra.append({"ho_ten": ten, "chuc_danh": x["trach_nhiem"], "nhom": x["ky_hieu"],
                   "bo_phan_duoc_danh_gia": ", ".join(bo_phan_cua(nd, x))})
    return _bc((("ho_ten", "Họ tên"), ("chuc_danh", "Chức danh"), ("nhom", "Nhóm"),
                ("bo_phan_duoc_danh_gia", "Bộ phận được đánh giá")), ra, "Theo kế hoạch BM.01.05 của đợt.")


NGUON = {
    "su_co_ky": ("Phiếu sự cố mở, đóng, còn mở trong kỳ (BM.08.02)", keo_su_co_ky),
    "khieu_nai_ky": ("Khiếu nại mở, đóng trong kỳ (BM.11.01)", keo_khieu_nai_ky),
    "khac_phuc_mo": ("BM.01.07 quá hạn, chờ kiểm tra hiệu lực", keo_khac_phuc_mo),
    "nhac_cao": ("Mục nhắc mức cao hiện tại", keo_nhac_cao),
    "viec_bien_ban_truoc": ("Việc giao chưa xong của biên bản trước", keo_viec_bien_ban_truoc),
    "bc_thang": ("Bảng chỉ số BM.01.12 tháng trước, lũy kế năm", keo_bc_thang),
    "dgnb_ket_qua": ("Kết quả đánh giá nội bộ BM.01.09 gần nhất", keo_dgnb_ket_qua),
    "thay_doi_ky": ("BM.01.01 đã duyệt, đợt ban hành trong kỳ", keo_thay_doi_ky),
    "rui_ro_ben_quan_tam": ("BM.05.02 rủi ro cấp độ 1, BM.05.01 bên quan tâm", keo_rui_ro_ben_quan_tam),
    "kiem_nghiem_nam": ("Kết quả kiểm nghiệm trong năm", keo_kiem_nghiem_nam),
    "cong_doan_banh": ("Công đoạn dây chuyền bánh (SX QC Cong Doan)", keo_cong_doan_banh),
    "cong_doan_bot": ("Công đoạn dây chuyền bột (SX QC Cong Doan)", keo_cong_doan_bot),
    "oprp_banh": ("oPRP hiện hành bánh (1, 2)", keo_oprp_banh),
    "oprp_bot": ("oPRP hiện hành bột (5–9)", keo_oprp_bot),
    "dien_tap_truy_xuat": ("Diễn tập truy xuất trên app (thời gian, cân bằng)", keo_dien_tap_truy_xuat),
    "lo_thu_hoi": ("Lô có cờ thu hồi, đã bán theo khách, đã thu về", keo_lo_thu_hoi),
    "dong_vat_ky": ("Dấu hiệu động vật gây hại theo trạm trong kỳ", keo_dong_vat_ky),
    "dgnb_luu_y": ("Các điểm Lưu ý của checklist BM.01.06 trong đợt", keo_dgnb_luu_y),
    "dgnb_dem": ("Số KPH / Lưu ý theo bộ phận (BM.01.06 trong đợt)", keo_dgnb_dem),
    "dgnb_doan": ("Thành phần đoàn theo kế hoạch BM.01.05", keo_dgnb_doan),
}
# Nguồn theo dây chuyền chọn ở đầu phiếu (BM.HACCP.01 / 02).
CHON_NGUON = {"cong_doan": {BANH: "cong_doan_banh", BOT: "cong_doan_bot"},
              "oprp": {BANH: "oprp_banh", BOT: "oprp_bot"}}


def khoa_nguon(nguon, dau):
    """Khóa hàm kéo thật của một phần: khóa trực tiếp, hoặc chọn theo dây chuyền ở đầu phiếu."""
    if nguon in CHON_NGUON:
        dc = day_chuyen_cua(dau)
        return CHON_NGUON[nguon].get(dc) if dc else None
    return nguon if nguon in NGUON else None


def keo(nguon, ctx, luc):
    """Bản chụp của một hàm kéo — lỗi (chưa migrate, thiếu dữ liệu) thành dòng báo, không làm hỏng biên bản."""
    k = khoa_nguon(nguon, ctx.get("dau"))
    if not k:
        return {"nguon": nguon, "luc": luc, "cot": [], "dong": [],
                "ghi_chu": "Chọn dây chuyền / kế hoạch ở đầu phiếu rồi bấm Kéo lại."}
    try:
        x = NGUON[k][1](ctx)
    except Exception as e:  # noqa: BLE001 — một nguồn hỏng không chặn lập biên bản
        x = {"cot": [], "dong": [], "ghi_chu": f"Không kéo được dữ liệu ({type(e).__name__})."}
    return dict(x, nguon=k, ten=NGUON[k][0], luc=luc, tu=str(ctx.get("tu") or ""), den=str(ctx.get("den") or ""))


def ap_keo(p, snap, cu=None):
    """Giá trị của một phần từ bản chụp: Kéo dữ liệu → {keo}; Bảng / Việc giao → dòng thường (sửa được); Danh sách
    kiểm → câu cố định (_co_dinh) giữ ô trả lời cũ nếu cùng câu."""
    meta = {k: v for k, v in snap.items() if k != "dong"}
    if p.get("kieu") == KEO:
        return {"keo": snap}
    khoa = {c["key"] for c in cot_cua(p)}
    dong = [{k: v for k, v in r.items() if k in khoa and not _trong(v)} for r in snap.get("dong") or []]
    if p.get("kieu") == DS_KIEM:
        hoi = [c["key"] for c in cot_hoi(p)]
        cu_theo = {tuple(str(r.get(k)) for k in hoi): r for r in ((cu or {}).get("dong") or [])}
        ra = []
        for i, r in enumerate(dong, 1):
            c = cu_theo.get(tuple(str(r.get(k)) for k in hoi)) or {}
            x = {k: v for k, v in c.items() if not str(k).startswith("_") and k not in hoi}
            x.update(r)
            x.update({"_id": f"k{i}", "_co_dinh": 1})
            ra.append(x)
        them = [r for r in ((cu or {}).get("dong") or []) if not cint(r.get("_co_dinh"))]
        return {"dong": ra + them, "keo": meta}
    return {"dong": [dict(r, _id=f"t{i}") for i, r in enumerate(dong, 1)], "keo": meta}


def noi_dung_dau(dn_phan, dau=None):
    """Nội dung ban đầu của biên bản: dòng in sẵn; đầu phiếu theo `dau` (đã sạch)."""
    ra = {}
    for p in dn_phan:
        if p.get("kieu") == VAN_BAN and p["key"] == DAU and dau:
            ra[DAU] = {"gia_tri": dict(dau)}
        elif p.get("kieu") in CO_DONG and (p.get("dong_mau") or "").strip():
            dong = tach_dong_mau(p)
            if p.get("kieu") != DS_KIEM:            # Bảng / Việc giao: dòng in sẵn là gợi ý, sửa xóa được
                dong = [dict({k: v for k, v in r.items() if not k.startswith("_")}, _id=f"t{i}")
                        for i, r in enumerate(dong, 1) if not cint(r.get("_tieu_de"))]
            ra[p["key"]] = tinh_phan(p, {"dong": dong})
    return ra


# ── Quyền ─────────────────────────────────────────────────────────────────────────────────

def quyen_mau(m, roles, sieu=False):
    """{lap, xem} theo mẫu (chưa xét biên bản cụ thể)."""
    roles = set(roles or ())
    hon = bool(sieu or ISO in roles)
    lap = hon or bool(roles & set(m.get("vai_lap") or ()))
    xem = lap or bool(roles & set(m.get("vai_xem") or ()))
    return {"lap": lap, "xem": xem}


def co_o_ky(ky, user, roles, nguoi_lap):
    """Người này có ô ký (đã ký, được gán, hay có vai của ô) trên biên bản không — để xem được biên bản mình ký."""
    roles = set(roles or ())
    for s in ky or []:
        if user and s.get("user") == user:
            return True
        if s.get("user") or cint(s.get("ky_tay")):
            continue
        if (cint(s.get("nguoi_lap")) and user and user == nguoi_lap) or (s.get("role") and s["role"] in roles):
            return True
    return False


def quyen_bb(bb, m, user, roles, sieu=False, chuyen_gia_dot=()):
    """{xem, sua, gui, ky, tra_lai, ky_tay, xoa, car} của người này trên biên bản `bb` (dict thuần)."""
    roles = set(roles or ())
    hon = bool(sieu or ISO in roles)
    qm = quyen_mau(m or {}, roles, sieu)
    nl = bb.get("nguoi_lap")
    la_nl = bool(user) and user == nl
    ky = bb.get("ky") or []
    xem = hon or la_nl or qm["xem"] or co_o_ky(ky, user, roles, nl) or user in set(chuyen_gia_dot or ())
    tt = bb.get("trang_thai") or NHAP
    sua = (la_nl or hon) and tt in SUA_DUOC
    o, _l = o_ky_cua(ky, user, roles, nl) if tt == CHO_KY else (None, None)
    dau = gia_tri_dau(bb.get("noi_dung") or {})
    tk = can_ky_tay(ky, dau, (bb.get("dinh_nghia") or {}).get("ky_tay_khi"))
    return {"xem": bool(xem), "sua": bool(sua), "gui": bool(sua), "ky": o is not None, "tra_lai": o is not None,
            "ky_tay": bool(tk and tt == CHO_KY and (la_nl or hon) and not bb.get("ban_ky_tay")),
            "xoa": bool(sua and not any(s.get("ky_luc") for s in ky)),
            "car": bool(xem and (la_nl or hon or roles & {"SX QC", "Production Manager", GIAM_DOC}))}


# ── Nhắc ──────────────────────────────────────────────────────────────────────────────────

def cho_ky_cua(ds, user, roles):
    """Biên bản Chờ ký mà người này đang tới lượt ký: [{name, mau, so, ten_mau, ngay, vai_tro, gui_luc}].
    `ds` = [{name, mau, so, ten_mau, ngay, nguoi_lap, gui_luc, ky: [...]}]."""
    ra = []
    for x in ds:
        s, _l = o_ky_cua(x.get("ky") or [], user, roles, x.get("nguoi_lap"))
        if s is not None:
            ra.append({"name": x["name"], "mau": x.get("mau"), "so": x.get("so") or "", "ten_mau": x.get("ten_mau") or "",
                       "ngay": str(x.get("ngay") or ""), "vai_tro": s.get("vai_tro") or "",
                       "gui_luc": str(x.get("gui_luc") or "")[:16]})
    return ra


def nhac_thuan(hom_nay, mau_ds, bb_ds, user=None, roles=(), so_do=None):
    """Dữ liệu hộp nhắc mảng Biên bản (hàm thuần):
      · cho_toi  — biên bản đang tới lượt người mở màn ký;
      · cho_lau  — chờ ký quá CHO_KY_NGAY ngày (chờ ai; thiếu bản ký tay);
      · den_han  — mẫu lập theo Tuần / Tháng (BM.01.11 họp Ban ISO tuần) quá kỳ chưa có biên bản;
      · so_do    — dây chuyền phải xác nhận lại sơ đồ (BM.HACCP.01).
    Năm (BM.01.10, ĐGNB, thẩm tra, diễn tập) nhắc qua việc định kỳ."""
    nay = _ngay(hom_nay)
    cho = [x for x in bb_ds if x.get("trang_thai") == CHO_KY]
    cho_lau = []
    for x in cho:
        g = x.get("gui_luc")
        if not g or (nay - getdate(g)).days <= CHO_KY_NGAY:
            continue
        s = o_cho(x.get("ky"))
        cho_lau.append({"name": x["name"], "mau": x.get("mau"), "so": x.get("so") or "", "ngay_gui": str(getdate(g)),
                        "so_ngay": (nay - getdate(g)).days,
                        "cho": (s or {}).get("vai_tro") or ("bản ký tay (scan)" if not x.get("ban_ky_tay") else "")})
    den_han = []
    for m in mau_ds:
        n = {TUAN: 7, THANG: 31}.get(m.get("chu_ky_lap"))
        if not n or cint(m.get("ngung")):
            continue
        cuoi = max((getdate(x["ngay"]) for x in bb_ds if x.get("mau") == m["name"]), default=None)
        moc = cuoi or getdate(m.get("creation") or nay)
        if (nay - moc).days > n:
            den_han.append({"ma": m["name"], "ten": m.get("ten") or "", "lan_cuoi": cuoi.isoformat() if cuoi else None,
                            "so_ngay": (nay - moc).days, "chu_ky": m.get("chu_ky_lap")})
    return {"cho_toi": cho_ky_cua(cho, user, roles) if user else [],
            "cho_lau": sorted(cho_lau, key=lambda x: -x["so_ngay"]), "den_han": den_han, "so_do": so_do or []}


def _ky_theo(ten):
    ra = {}
    for r in frappe.get_all(PT_KY, filters={"parenttype": PT_BB, "parent": ("in", ten or [""])},
                            fields=["parent"] + [f for f in TRUONG_KY if f != "idx"] + ["idx", "user", "ky_luc"]):
        ra.setdefault(r.parent, []).append(dict(r))
    return ra


def ds_bb_nhe(filters=None):
    """Biên bản (ô chính + ô ký) — cho danh sách, nhắc; không đọc nội dung."""
    ds = frappe.get_all(PT_BB, filters=filters or {}, fields=["name", "mau", "ten_mau", "so", "ngay", "tieu_de",
                                                              "trang_thai", "nguoi_lap", "gui_luc", "ky_du_luc",
                                                              "ban_ky_tay", "goc", "creation"],
                        order_by="ngay desc, creation desc")
    ky = _ky_theo([x.name for x in ds])
    return [dict(x, ky=ky_sap(ky.get(x.name, []))) for x in ds]


def moc_so_do():
    """Mốc xác nhận sơ đồ lúc triển khai (SX QC Setting.so_do_moc — patch d174 ghi): {dây chuyền: {ngay, van_tay}}."""
    try:
        v = doc_json(frappe.db.get_single_value("SX QC Setting", "so_do_moc"), {}) or {}
    except Exception:
        return {}
    return {k: x for k, x in v.items() if isinstance(x, dict) and x.get("van_tay")}


def xac_nhan_so_do():
    """{dây chuyền: {ngay, van_tay}} — BM.HACCP.01 ký đủ gần nhất của từng dây chuyền (vân tay trong bản chụp); chưa
    có thì mốc lúc triển khai."""
    ra = moc_so_do()
    for x in frappe.get_all(PT_BB, filters={"mau": SO_DO, "trang_thai": DA_KY}, fields=["name", "ngay", "noi_dung"],
                            order_by="ngay asc, creation asc"):
        nd = doc_json(x.noi_dung, {}) or {}
        for v in nd.values():
            k = (v or {}).get("keo") if isinstance(v, dict) else None
            if k and k.get("day_chuyen") and k.get("van_tay"):
                ra[k["day_chuyen"]] = {"ngay": str(x.ngay), "van_tay": k["van_tay"]}
    return ra


def so_do_nhac(hom_nay):
    try:
        cd = {dc: ds_cong_doan(dc) for dc in (BANH, BOT)}
        return so_do_can_xac_nhan(cd, xac_nhan_so_do())
    except Exception:
        return []


def cho_toi(user, roles):
    """Biên bản đang chờ người này ký (đầu màn Tài liệu, hộp nhắc). Chưa migrate → []."""
    try:
        return cho_ky_cua(ds_bb_nhe({"trang_thai": CHO_KY}), user, roles)
    except Exception:
        return []


def co_bien_ban(user, roles, sieu=False):
    """Người này có việc ở khung Biên bản không (tab Biên bản ở màn Tài liệu). Chưa migrate → False."""
    roles = set(roles or ())
    try:
        if not frappe.db.table_exists(PT_BB):
            return False
        if sieu or ISO in roles:
            return True
        if any(quyen_mau(m, roles, sieu)["xem"] for m in ds_mau()):
            return True
        if frappe.get_all(PT_BB, filters={"nguoi_lap": user}, limit=1):
            return True
        return any(co_o_ky(x.get("ky"), user, roles, x.get("nguoi_lap")) for x in ds_bb_nhe())
    except Exception:
        return False


def nhac(hom_nay, user=None, roles=()):
    """Dữ liệu hộp nhắc (chữ ở sx/qc/nhac.py). Chưa migrate → {}."""
    try:
        mau_ds = ds_mau()
        if not mau_ds:
            return {}
        bb = ds_bb_nhe()
    except Exception:
        return {}
    return nhac_thuan(hom_nay, mau_ds, bb, user, roles, so_do_nhac(hom_nay))
