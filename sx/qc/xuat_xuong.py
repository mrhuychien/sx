"""Kiểm tra xuất xưởng theo lô — BM.08.04 (W08, D137; theo phiếu giấy lần BH 01: W31, D159).

Một phiếu = một lô thành phẩm = (sản phẩm, HSD) (W05). QC kiểm đúng phiếu giấy lần BH 01:
  A. Hồ sơ của lô A1–A5 — Đ / K (A4 thêm KAD). App tra hồ sơ và GỢI Ý kết quả, QC vẫn bấm
     (mẫu lưu A5 chấm sẵn như trước — kiểm tự động);
  B. Kiểm thành phẩm B1–B6 — 5 mẫu ở 5 thùng khác nhau, mỗi mẫu một ô (B2 ghi số cân, gam;
     dòng khác Đ / K) + kết luận dòng;
  C. Kết luận — Cho xuất xưởng / Giữ lại chờ xử lý / Không cho xuất;
rồi GỬI DUYỆT; Trưởng Ban ISO / người được giao DUYỆT — không phải chính QC đã kiểm lô đó.
Quản lý sản xuất ký ô thứ ba (người + giờ) — không bắt buộc để duyệt.

Chỉ "Đã duyệt + Cho xuất xưởng" mới mở cửa (= "Đạt" cũ ở mọi chỗ chặn). Lô chưa có phiếu đó:
  · thủ kho không duyệt được phiếu nhập kho có lô đó (SX Phieu Nhap TP.before_submit);
  · không bán được (sx/api/xuatxuong.kiem_ban) — trừ hàng tồn trước ngày áp dụng.
Giữ lại chờ xử lý: xử lý xong kiểm lại trên phiếu MỚI. Không cho xuất: lô huỷ, không rework
(QT.15) — không lập phiếu mới được; duyệt nhầm thì người có quyền thu hồi duyệt. Hai kết luận
này luôn kèm phiếu sự cố BM.08.02 (QC chọn phiếu có sẵn, không thì app lập lúc gửi duyệt).

Phiếu trước D159 (8 mục tạm "1".."8") giữ nguyên mục đã ghi — bảng con lưu cả nội dung;
patch d159 đổi kết luận cũ: Đạt → Cho xuất xưởng, Không đạt → Không cho xuất.

File này chỉ đọc doctype của module QC + Batch / Item — không import gì ngoài frappe và module
qc (ranh giới module). Phần tra chứng từ kho (ngày nghiền, ngày rang, nguyên liệu của lô) ở
sx/api/xuatxuong.py.
"""

import frappe
from frappe import _
from frappe.utils import cint, getdate

from sx.qc import muc as M

PT = "SX Kiem Tra Xuat Xuong"
NHAP, CHO, DUYET, TRA = "Nháp", "Chờ duyệt", "Đã duyệt", "Trả lại"
DAT, KHONG_DAT, KAD = "Đạt", "Không đạt", "Không áp dụng"
CHO_XUAT, GIU_LAI, KHONG_XUAT = "Cho xuất xưởng", "Giữ lại chờ xử lý", "Không cho xuất"
KET_LUAN = (CHO_XUAT, GIU_LAI, KHONG_XUAT)
# Kết luận trước D159. Patch d159 đổi trong DB; đọc qua kl() để phiếu chưa đổi vẫn đúng.
KET_LUAN_CU = {DAT: CHO_XUAT, KHONG_DAT: KHONG_XUAT}
SO_MAU = 5
LAN_BH = "01 — 21/9/2026"
D, K = "Đ", "K"          # ô mẫu B1, B3–B6
LUOT_DU = 3              # "đủ 3 lượt" — Đầu sáng (hoặc Tuần), Trưa, Cuối chiều; lượt Bổ sung không bù

# Phiếu giấy BM.08.04 lần BH 01 — chép đúng chữ (mã, nội dung / chỉ tiêu, yêu cầu). Sửa đổi
# lần sau thì sửa ở đây; phiếu cũ giữ nguyên chữ đã lưu trong bảng con.
MUC_A = (
    ("A1", "Vòng kiểm QC BM.08.01: ngày sản xuất (bánh: mục 10–13; bột: phần B); ngày nghiền bột "
           "đậu dùng cho lô (cả bánh và bột: mục 6–8); ngày rang đỗ tương ứng (mục 2–5)",
     "Đủ 3 lượt (cả ngày nghiền và ngày rang tương ứng); các mục oPRP đạt, hoặc mục không đạt đã "
     "có BM.08.02"),
    ("A2", "Phiếu sự cố BM.08.02 liên quan đến lô",
     "Không có, hoặc đã có quyết định xử lý sản phẩm (sản phẩm bị ảnh hưởng đã tách ra)"),
    ("A3", "Nguyên liệu, bao bì dùng cho lô (BM.07.03)", "Các lô đang dùng đã được tiếp nhận đạt"),
    ("A4", "Bột vị không lạc trộn, đóng gói sau Chè đậu đen cốt dừa (máy trộn, máy đóng gói vừa chạy "
           "Chè): thử nhanh protein lạc trên máy sau vệ sinh chuyển đổi, trước khi chạy lô (BM.08.01 "
           "mục B7, oPRP-9)",
     "Âm tính. KAD: lô bánh, lô Chè đậu đen cốt dừa, hoặc máy không chạy Chè trước lô"),
    ("A5", "Mẫu lưu (QĐ.01 lần 02)", "Đã lấy mẫu lưu đúng lô, có nhãn"),
)
MUC_B = (
    ("B1", "Cảm quan", "Màu, mùi, vị, trạng thái đặc trưng của sản phẩm; không mốc, không vón ẩm, "
                       "không dị vật (theo TCCS 01, 02, 03 mục 3.2)"),
    ("B2", "Khối lượng tịnh (g)", "Ghi số cân; không thấp hơn khối lượng ghi trên nhãn quá sai số cho "
                                  "phép; cân đã kiểm định"),
    ("B3", "Bao gói, mối hàn", "Túi, gói kín, không rách, không hở; hộp không móp, bẩn; hộp nhựa nắp kín"),
    ("B4", "Nhãn", "Đúng sản phẩm, vị, quy cách; đủ nội dung bắt buộc (NSX, HSD, dinh dưỡng; TCCS mục "
                   "5.2); bột: có cảnh báo chất gây dị ứng theo thành phần (lạc, sữa, dừa)"),
    ("B5", "HSD in trên bao bì", "Đúng HSD của lô, rõ, không nhòe, đủ trên gói / hộp"),
    ("B6", "Thùng carton", "Sạch, nguyên vẹn, nhãn thùng và HSD đúng, đủ số lượng"),
)
MUC = MUC_A + MUC_B
MA_A = tuple(m[0] for m in MUC_A)
MA_B = tuple(m[0] for m in MUC_B)
KAD_DUOC = ("A4",)       # chỉ A4 có ô KAD trên giấy
MAU_SO = ("B2",)         # ô mẫu ghi số cân (g)
XU_LY = {
    CHO_XUAT: "Lô đạt toàn bộ mục A và B. Nhập kho thành phẩm, được phép xuất hàng.",
    GIU_LAI: "Có mục không đạt sửa được (đóng gói lại, dán lại nhãn, loại đơn vị lỗi) hoặc rework theo "
             "danh mục QT.15 (BM.15.01). Lập BM.08.02; kiểm lại sau xử lý trên phiếu mới.",
    KHONG_XUAT: "Có mục ảnh hưởng an toàn thực phẩm. Cách ly, BM.08.02; Trưởng Ban ISO quyết định loại "
                "bỏ, hủy; không rework (QT.15).",
}


def kl(v):
    """Kết luận theo bộ chữ lần BH 01 (phiếu trước D159 ghi Đạt / Không đạt)."""
    return KET_LUAN_CU.get(v, v) if v else v


def la_moi(ds_muc):
    """Phiếu theo bản giấy lần BH 01 (mục A1…B6). Phiếu trước D159 có mục "1".."8"."""
    return any(str(r.get("ma") or "") in MA_A + MA_B for r in ds_muc or [])


def _k(item, hsd):
    return (item, str(getdate(hsd)) if hsd else None)


def theo_lo(cap):
    """{(item, 'YYYY-MM-DD'): phiếu đại diện} cho các cặp (sản phẩm, HSD).

    Phiếu đại diện = phiếu Đã duyệt + Cho xuất xưởng nếu có; không thì phiếu mới nhất. Phiếu
    'Đã duyệt + Giữ lại' cũ không che phiếu kiểm lại sau xử lý."""
    cap = {_k(i, h) for i, h in cap if i and h}
    if not cap:
        return {}
    try:
        ds = frappe.get_all(PT, filters={"san_pham": ("in", list({i for i, _h in cap})),
                                         "hsd": ("in", list({h for _i, h in cap}))},
                            fields=["name", "san_pham", "hsd", "trang_thai", "ket_luan", "creation",
                                    "qc_kiem", "nguoi_duyet"],
                            order_by="creation asc")
    except Exception:          # chưa migrate D137
        return {}
    ra = {}
    for x in ds:
        k = _k(x.san_pham, x.hsd)
        if k not in cap:
            continue
        if da_duyet(ra.get(k)):
            continue
        ra[k] = x
    return ra


def da_duyet(p):
    """Lô được nhập kho / bán: phiếu Đã duyệt + Cho xuất xưởng."""
    return bool(p and p.trang_thai == DUYET and kl(p.ket_luan) == CHO_XUAT)


def mo_lai_duoc(p):
    """Lập được phiếu MỚI cho lô: chưa có phiếu, hoặc phiếu đại diện đã duyệt 'Giữ lại chờ xử lý'
    (xử lý xong kiểm lại trên phiếu mới). 'Không cho xuất' thì không — lô huỷ, không rework."""
    return not p or (p.trang_thai == DUYET and kl(p.ket_luan) == GIU_LAI)


def mo_ta(p):
    """Câu ngắn cho người đọc: lô này đang ở đâu trong BM.08.04."""
    if not p:
        return _("chưa kiểm xuất xưởng")
    if p.trang_thai == DUYET:
        return _("đã duyệt — {0}").format(kl(p.ket_luan) or "?")
    return {NHAP: _("QC đang kiểm"), CHO: _("chờ Ban ISO duyệt"),
            TRA: _("bị trả lại, QC kiểm lại")}.get(p.trang_thai, p.trang_thai)


def chua_duyet(cap):
    """[(item, hsd, phiếu|None)] — các lô trong `cap` CHƯA được duyệt cho xuất xưởng."""
    p = theo_lo(cap)
    ra, da = [], set()
    for i, h in cap:
        if not i or not h:
            continue
        k = _k(i, h)
        if k in da:
            continue
        da.add(k)
        if not da_duyet(p.get(k)):
            ra.append((i, k[1], p.get(k)))
    return ra


# ═══════════════════════════════ hồ sơ lô (gợi ý mục A) ═══════════════════════════════

def _vn(d):
    return getdate(d).strftime("%d/%m/%Y")


def _ngay(ds):
    return sorted({str(getdate(x)) for x in ds or () if x})


def so_luot(ngay):
    """Số lượt CHÍNH đã hoàn tất của một ngày — Tuần là lượt đầu sáng thứ Hai, Bổ sung không bù."""
    try:
        ds = frappe.get_all("SX QC Round", filters={"ngay": getdate(ngay), "docstatus": 1}, pluck="luot")
    except Exception:
        return 0
    return len({M.DAU_SANG if x == M.TUAN else x for x in ds if x in M.LUOT_TRONG_NGAY + (M.TUAN,)})


def su_co_lien_quan(item, hsd, batch=None, ngay=()):
    """Phiếu sự cố liên quan lô (A2), không tính diễn tập: gắn lô (bảng Lô liên quan / ô lô ảnh
    hưởng), phiếu sự cố của mọi phiếu BM.08.04 của lô (kể cả phiếu đang ghi — bị trả lại sau "Giữ
    lại" thì phiếu sự cố đó vẫn phải có quyết định xử lý sản phẩm rồi mới cho xuất), sự cố vòng
    kiểm các ngày làm ra lô (ngày SX, nghiền, rang — mục không đạt sinh BM.08.02 lúc hoàn tất lượt)."""
    ten = set()
    try:
        if batch:
            ten |= set(frappe.get_all("SX Su Co Lo", filters={"parenttype": "SX Su Co", "batch": batch},
                                      pluck="parent"))
            ten |= set(frappe.get_all("SX Su Co", filters={"lo_anh_huong": ("like", f"%{batch}%")},
                                      pluck="name"))
        if item and hsd:
            ten |= {x for x in frappe.get_all(PT, filters={"san_pham": item, "hsd": getdate(hsd)},
                                              pluck="su_co") if x}
        if ngay:
            ten |= set(frappe.get_all("SX Su Co", filters={"ngay": ("in", list(ngay)),
                                                          "nguon": "Vòng kiểm QC"}, pluck="name"))
        if not ten:
            return []
        return frappe.get_all("SX Su Co", filters={"name": ("in", sorted(ten)), "dien_tap": 0},
                              fields=["name", "ngay", "trang_thai", "quyet_dinh_sp", "mo_ta"],
                              order_by="ngay asc")
    except Exception:          # chưa migrate W11
        return []


def _mau_luu(item, hsd):
    try:
        lm = frappe.get_all("SX QC Luu Mau", filters={"san_pham": item, "hsd": getdate(hsd)},
                            pluck="name", limit=3)
        if not lm:
            lm = frappe.get_all("SX QC Luu Mau", filters={
                "san_pham": item, "lo": ("like", f"%{_vn(hsd)}%")}, pluck="name", limit=3)
    except Exception:
        lm = []
    return lm


def _b7(ngay):
    """Kết quả thử nhanh lạc B7 của các lượt đã hoàn tất trong ngày."""
    try:
        return [x for x in frappe.get_all("SX QC Round", filters={"ngay": getdate(ngay), "docstatus": 1},
                                          pluck="b7_chuyen_doi") if x]
    except Exception:
        return []


def ho_so_lo(item, hsd, nsx, nghien=(), rang=(), batch=None, loai=None, co_lac=0):
    """Tra hồ sơ lô — gợi ý A1, A2, A4, A5 (A3 tra chứng từ kho, ở sx/api/xuatxuong.py).

    nghien / rang = ngày nghiền bột đậu, ngày rang đỗ dùng cho lô (có thể nhiều ngày);
    loai = Bánh / Bột / Chè, co_lac theo bộ tự công bố (W28).
    Trả {"goi_y": {mã: kết quả | None}, "can_cu": {mã: câu}, "su_co": {mã: số phiếu}}."""
    goi, can, sc = {}, {}, {}
    nghien, rang = _ngay(nghien), _ngay(rang)
    sx = str(getdate(nsx)) if nsx else None

    # A1 — đủ 3 lượt ở ngày SX, ngày nghiền, ngày rang
    if not sx:
        goi["A1"] = None
        can["A1"] = _("Chưa tính được NSX (mã chưa khai hạn dùng) — QC tự đối chiếu BM.08.01.")
    else:
        phan, du = [], True
        for nhan, ds in ((_("ngày SX"), [sx]), (_("nghiền"), nghien), (_("rang"), rang)):
            for d in ds:
                so = so_luot(d)
                du = du and so >= LUOT_DU
                phan.append(_("{0} {1}: {2} lượt{3}").format(
                    nhan, _vn(d), so, "" if so >= LUOT_DU else _(" (thiếu)")))
        if not nghien or not rang:
            phan.append(_("chưa có ngày {0} — ghi ngày rồi bấm TRA LẠI").format(
                " / ".join(x for x, ds in ((_("nghiền"), nghien), (_("rang"), rang)) if not ds)))
            du = False
        goi["A1"] = DAT if du else None
        can["A1"] = "BM.08.01 — " + " · ".join(phan)

    # A2 — sự cố liên quan lô: không có, hoặc đã có quyết định xử lý sản phẩm
    lq = su_co_lien_quan(item, hsd, batch, [x for x in [sx] + nghien + rang if x])
    chua = [x for x in lq if not x.get("quyet_dinh_sp")]
    if not lq:
        goi["A2"], can["A2"] = DAT, _("Không có phiếu sự cố liên quan lô.")
    else:
        goi["A2"] = KHONG_DAT if chua else DAT
        sc["A2"] = (chua or lq)[0].name
        can["A2"] = "; ".join(_("{0} {1}: {2}").format(
            x.name, x.trang_thai or "", x.get("quyet_dinh_sp") or _("CHƯA quyết định sản phẩm")) for x in lq)

    # A4 — thử nhanh lạc sau Chè (B7, oPRP-9): chỉ bột vị không lạc
    if loai == "Bánh":
        goi["A4"], can["A4"] = KAD, _("Lô bánh — KAD.")
    elif loai == "Chè" or cint(co_lac):
        goi["A4"], can["A4"] = KAD, _("Lô Chè đậu đen cốt dừa / vị có lạc — KAD.")
    elif loai == "Bột" and sx:
        b7 = _b7(sx)
        if M.B7_DUONG in b7:
            goi["A4"], can["A4"] = KHONG_DAT, _("B7 ngày SX {0}: DƯƠNG TÍNH.").format(_vn(sx))
        elif M.B7_AM in b7:
            goi["A4"], can["A4"] = DAT, _("B7 ngày SX {0}: âm tính.").format(_vn(sx))
        elif so_luot(sx):
            goi["A4"] = KAD
            can["A4"] = _("Ngày SX {0} không có chuyển đổi sau Chè (B7) — máy không chạy Chè trước lô.") \
                .format(_vn(sx))
        else:
            goi["A4"], can["A4"] = None, _("Ngày SX {0} chưa có lượt kiểm hoàn tất.").format(_vn(sx))
    else:
        goi["A4"] = None
        can["A4"] = _("Mã hàng chưa gắn sản phẩm tự công bố (Bánh / Bột / Chè) — QC tự xét.")

    # A5 — mẫu lưu đúng lô (kiểm tự động như trước D159)
    lm = _mau_luu(item, hsd)
    goi["A5"] = DAT if lm else None
    can["A5"] = _("Mẫu lưu: {0}").format(", ".join(lm)) if lm else _("Mẫu lưu: CHƯA lấy")
    return {"goi_y": goi, "can_cu": can, "su_co": sc}


def chu_ho_so(can_cu):
    """Ô Hồ sơ lô (chữ): mỗi mục một dòng, theo thứ tự A1…A5."""
    return "\n".join(f"{ma} · {can_cu[ma]}" for ma in MA_A if can_cu.get(ma))


# ═══════════════════════════════ ô mẫu, gửi duyệt ═══════════════════════════════

def chuan_mau(ma, v):
    """Một ô mẫu dòng B: B2 = số cân (g, > 0); dòng khác = Đ / K. Rỗng = chưa ghi."""
    v = str(v if v is not None else "").strip()
    if not v:
        return ""
    if ma in MAU_SO:
        try:
            so = float(v.replace(",", "."))
        except ValueError:
            so = 0
        if not 0 < so < 100000:
            frappe.throw(_("{0}: số cân không hợp lệ ({1}).").format(ma, v))
        return f"{so:g}"
    v = v.upper()
    v = D if v == "D" else v
    if v not in (D, K):
        frappe.throw(_("{0}: ô mẫu ghi Đ hoặc K.").format(ma))
    return v


def mau(r):
    return [str(r.get(f"mau_{i}") or "") for i in range(1, SO_MAU + 1)]


def can_ket_luan(doc):
    """Lỗi khi gửi duyệt: mục chưa chấm, mẫu thiếu, kết luận thiếu / mâu thuẫn. [] = được gửi."""
    ds = doc.get("ds_muc") or []
    if not la_moi(ds):
        return _can_ket_luan_cu(doc)
    loi = []
    chua = [r.ma for r in ds if not r.get("ket_qua")]
    if chua:
        loi.append(_("Còn mục chưa chấm: {0}").format(", ".join(chua)))
    sai = [r.ma for r in ds if r.get("ket_qua") == KAD and r.ma not in KAD_DUOC]
    if sai:
        loi.append(_("Chỉ A4 được chấm KAD: {0}").format(", ".join(sai)))
    thieu = [r.ma for r in ds if r.ma in MA_B and not all(mau(r))]
    if thieu:
        loi.append(_("Chưa ghi đủ {0} mẫu: {1}").format(SO_MAU, ", ".join(thieu)))
    vo = [r.ma for r in ds if r.ma in MA_B and r.ma not in MAU_SO and r.get("ket_qua") == DAT and K in mau(r)]
    if vo:
        loi.append(_("Có mẫu K mà kết luận dòng Đạt: {0}").format(", ".join(vo)))
    k = kl(doc.get("ket_luan"))
    hong = [r.ma for r in ds if r.get("ket_qua") == KHONG_DAT]
    if not k:
        loi.append(_("Chưa có kết luận: Cho xuất xưởng / Giữ lại chờ xử lý / Không cho xuất"))
    elif k not in KET_LUAN:
        loi.append(_("Kết luận không hợp lệ: {0}").format(k))
    elif k == CHO_XUAT and hong:
        loi.append(_("Cho xuất xưởng phải đạt toàn bộ mục A và B — mục Không đạt: {0}").format(", ".join(hong)))
    elif k != CHO_XUAT and not hong and not (doc.get("ghi_chu") or "").strip():
        loi.append(_("Kết luận {0} mà không có mục Không đạt — ghi lý do vào Ghi chú của QC.").format(k))
    return loi


def _can_ket_luan_cu(doc):
    """Phiếu trước D159 (8 mục tạm): luật cũ, kết luận theo bộ chữ mới."""
    loi = []
    ds = doc.get("ds_muc") or []
    chua = [r.ma for r in ds if not r.get("ket_qua")]
    if chua:
        loi.append(_("Còn mục chưa chấm: {0}").format(", ".join(chua)))
    k = kl(doc.get("ket_luan"))
    if not k:
        loi.append(_("Chưa có kết luận: Cho xuất xưởng / Giữ lại chờ xử lý / Không cho xuất"))
    elif k == CHO_XUAT and any(r.get("ket_qua") == KHONG_DAT for r in ds):
        loi.append(_("Cho xuất xưởng nhưng có mục Không đạt"))
    if cint(doc.get("so_mau")) <= 0:
        loi.append(_("Chưa ghi số mẫu đã kiểm"))
    return loi
