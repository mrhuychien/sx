"""Phiếu đánh giá nhà cung cấp — BM.07.01 lần BH 02 (W44, D173). DocType riêng SX Danh Gia NCC.

Phần A — hồ sơ pháp lý, an toàn thực phẩm (7 mục như giấy): app TỰ ĐIỀN lúc lập phiếu từ bảng hồ sơ của nhà cung
cấp (Supplier → SX Ho So NCC, W09): có hồ sơ còn hạn → Có (số, ngày, hiệu lực chép sang); chỉ có bản hết hạn / không
có → Không; mục không áp dụng → KAD. Người chấm xem lại từng mục. Mục 1–6 áp dụng mà không "Có" (hoặc hiệu lực đã
qua ngày đánh giá) → thiếu phần A → kết luận buộc Loại bỏ.
  · Áp dụng theo giấy: 1, 2 mọi NCC; 3 loại 1; 4 loại 1 nhập khẩu; 5 loại 1 trong nước; 6 đỗ xanh, đỗ đen, lạc,
    dầu (app không biết NCC bán gì — người chấm chọn, KAD được); 7 không bắt buộc, cho điểm mục V.
  · Cát rang: chỉ cần hợp đồng hoặc đơn hàng + ĐKKD (QT.07) — mục 3–6 KAD.
Phần B — điểm: I chất lượng 10 / 5 / 0, II dịch vụ 10 / 5 / 0, III giá cả 10 / 4, IV tiến độ 10 / 6 / 0, V giấy chứng
nhận 2 / 0 (theo mục A7). Tổng tối đa 42. Đánh giá lại: gợi ý điểm I từ tỷ lệ lô Không đạt trong 12 tháng (BM.07.03
trên phiếu nhập mua / hoá đơn mua trừ kho + phiếu sự cố BM.08.02 gắn lô của NCC): 0 % → 10, < 10 % → 5, ≥ 10 % → 0.
Kết luận app tính: Chấp nhận = đủ phần A, tổng 30–42, điểm I ≥ 5; Xem xét = tổng 20–29 (Giám đốc quyết định);
Loại bỏ = tổng < 20, hoặc điểm I < 5, hoặc thiếu phần A.
Luồng: Mua hàng chấm, gửi → vật tư loại 1: QC cùng chấm, ký → Giám đốc (SX Quan Ly) duyệt; phiếu Xem xét thì Giám
đốc chọn Chấp nhận / Không chấp nhận. Duyệt Chấp nhận: hạn đánh giá lại = ngày duyệt + 12 tháng.
Nối Supplier (C26, sx/qc/ncc.py): từ ngày áp dụng (SX QC Setting), tích "Đã duyệt" phải có phiếu Chấp nhận còn hạn;
NCC duyệt trước ngày đó chỉ bị nhắc đánh giá lại (hạn lần đầu ở Setting — Lịch biểu mẫu: tháng 12/2026). Mua của
NCC chưa duyệt vẫn chỉ cảnh báo.

Phần thuần ở đầu (test gọi thẳng); phần đọc DB ở cuối.
"""

from datetime import date

import frappe
from frappe.utils import cint, getdate

from sx.qc import ncc as NCC
from sx.qc.thiet_bi import cong_thang

PT, PT_A = "SX Danh Gia NCC", "SX Danh Gia NCC Ho So"
MA = "BM.07.01"
LAN_DAU, LAI_NAM, LAI_DOT_XUAT = "Đánh giá lần đầu", "Đánh giá lại hằng năm", "Đánh giá lại đột xuất"
HINH_THUC = (LAN_DAU, LAI_NAM, LAI_DOT_XUAT)
LOAI_1, LOAI_2 = "Vật tư loại 1 (ảnh hưởng ATTP)", "Vật tư loại 2"
PHAN_LOAI = (LOAI_1, LOAI_2)
NGUON = (NCC.NHAP_KHAU, NCC.TRONG_NUOC)
CO, KHONG, KAD = "Có", "Không", "KAD"
CHAP_NHAN, XEM_XET, LOAI_BO = "Chấp nhận", "Xem xét", "Loại bỏ"
KHONG_CHAP_NHAN = "Không chấp nhận"            # Giám đốc quyết định phiếu Xem xét
NHAP, CHO_QC, CHO_DUYET, DA_DUYET, TRA_LAI = "Nháp", "Chờ QC", "Chờ duyệt", "Đã duyệt", "Trả lại"
TRANG_THAI = (NHAP, CHO_QC, CHO_DUYET, DA_DUYET, TRA_LAI)
SUA_DUOC = (NHAP, TRA_LAI)
THANG_LAI = 12               # đánh giá lại hằng năm (QT.07 sửa đổi 01)
BAO_TRUOC = 30               # ngày — nhắc trước hạn đánh giá lại
HAN_DAU = date(2026, 12, 31)  # NCC duyệt trước C26 chưa có phiếu: Lịch biểu mẫu 21/9/2026 — đánh giá lại T12/2026

# Ai làm gì (roles): Mua hàng lập, chấm; QC cùng chấm vật tư loại 1; Giám đốc duyệt; Trưởng Ban ISO xem, lập thay.
MUA = {"Purchase User", "Purchase Manager"}
QC_KY = {"SX QC"}
GIAM_DOC = {"SX Quan Ly"}
ISO = "ISO Manager"
VAI_XEM = MUA | QC_KY | GIAM_DOC | {ISO, "System Manager", "Administrator"}

# Phần A theo giấy: tt → (hồ sơ, áp dụng (chữ in), có ô KAD, loại hồ sơ NCC để tự điền).
MUC_A = {
    1: ("Giấy chứng nhận đăng ký doanh nghiệp / hộ kinh doanh (ĐKKD) của NCC", "Mọi NCC", False, (NCC.DKKD,)),
    2: ("Hợp đồng ký với NCC trước lần đặt hàng đầu tiên (vật tư loại 2: có thể là đơn hàng)", "Mọi NCC", False,
        (NCC.HOP_DONG,)),
    3: ("Hồ sơ tự công bố sản phẩm; bao bì tiếp xúc trực tiếp thực phẩm: bản công bố hợp quy / công bố phù hợp quy "
        "định ATTP", "Loại 1", True, (NCC.CONG_BO,)),
    4: ("Hàng nhập khẩu: COA theo từng lô (NCC cam kết gửi kèm mỗi lần giao)", "Loại 1 nhập khẩu", True, ()),
    5: ("Hàng trong nước: phiếu kiểm nghiệm định kỳ hằng năm của nhà sản xuất, còn hiệu lực", "Loại 1 trong nước",
        True, (NCC.PKN, NCC.PKN_BB)),
    6: ("Đỗ xanh nhập khẩu: cung cấp bộ chứng từ từng lô (CO, kiểm dịch thực vật, hun trùng, giấy kiểm tra ATTP nhập "
        "khẩu); đỗ đen (trong nước): phiếu kiểm nghiệm định kỳ hằng năm; lạc: phiếu kiểm nghiệm có aflatoxin còn hiệu "
        "lực; dầu: COA peroxit theo lô (HD.07.01)", "Đỗ xanh, đỗ đen, lạc, dầu", True, ()),
    7: ("Giấy chứng nhận cơ sở đủ điều kiện ATTP, ISO 22000, HACCP, FSSC 22000 hoặc ISO 9001 (nếu có)",
        "Không bắt buộc (điểm mục V, phần B)", False, (NCC.ATTP, NCC.HACCP)),
}
BAT_BUOC_A = (1, 2, 3, 4, 5, 6)

# Phần B: khóa ô → (số La Mã, chỉ tiêu, [(mức, điểm)]). V không chấm tay — theo mục A7.
MUC_B = {
    "diem_i": ("I", "Chất lượng (lần đầu: theo mẫu / lô thử; đánh giá lại: theo BM.07.03, BM.08.02 trong năm)",
               (("Luôn đạt", 10), ("Dưới 10% không đạt", 5), ("Trên 10% không đạt", 0))),
    "diem_ii": ("II", "Dịch vụ", (("Tốt", 10), ("Bình thường", 5), ("Kém", 0))),
    "diem_iii": ("III", "Giá cả", (("Phù hợp", 10), ("Không phù hợp", 4))),
    "diem_iv": ("IV", "Tiến độ giao hàng", (("Tốt", 10), ("Chậm 15%", 6), ("Chậm 20%", 0))),
    "diem_v": ("V", "Giấy chứng nhận ATTP / hệ thống quản lý (cơ sở đủ điều kiện ATTP, ISO 22000, HACCP, FSSC 22000, "
               "ISO 9001)", (("Có", 2), ("Không", 0))),
}
CHAM_TAY = ("diem_i", "diem_ii", "diem_iii", "diem_iv")
TOI_DA = sum(max(d for _m, d in x[2]) for x in MUC_B.values())       # 42


# ── Phần A ────────────────────────────────────────────────────────────────────────────────

def ap_dung(tt, phan_loai, nguon, loai_ncc=None):
    """Mục A `tt` có áp dụng không: True / False / None (mục 6 — app không biết NCC bán gì, người chấm chọn)."""
    if tt in (1, 2, 7):
        return True
    if phan_loai != LOAI_1 or loai_ncc == NCC.CAT:      # cát rang: hợp đồng / đơn hàng + ĐKKD (QT.07)
        return False
    if tt == 3:
        return True
    if tt == 4:
        return nguon == NCC.NHAP_KHAU
    if tt == 5:
        return nguon == NCC.TRONG_NUOC
    return None


def _ngay(x):
    return getdate(x) if x else None


def _ngay_vn(x):
    return getdate(x).strftime("%d/%m/%Y") if x else ""


def tu_dien(ho_so, phan_loai, nguon, loai_ncc, ngay):
    """7 dòng phần A tự điền từ bảng hồ sơ NCC ({loai_ho_so, so_hieu, ngay_cap, het_han}) tại ngày đánh giá."""
    d = getdate(ngay)
    ra = []
    for tt, (_ten, _ap_chu, _kad, loai_hs) in MUC_A.items():
        ap = ap_dung(tt, phan_loai, nguon, loai_ncc)
        dong = {"tt": tt, "ap_dung": MUC_A[tt][1], "ket_qua": "", "so_ngay": "", "hieu_luc": None}
        if ap is False:
            dong["ket_qua"] = KAD
        elif loai_hs:
            cung = [r for r in ho_so or [] if r.get("loai_ho_so") in loai_hs]
            con = [r for r in cung if not r.get("het_han") or getdate(r["het_han"]) >= d]
            r = max(con, key=lambda r: str(r.get("het_han") or "9999")) if con else (
                max(cung, key=lambda r: str(r.get("het_han") or "")) if cung else None)
            dong["ket_qua"] = CO if con else KHONG
            if r:
                dong["so_ngay"] = " ".join(x for x in (r.get("so_hieu") or "", f"ngày {_ngay_vn(r['ngay_cap'])}"
                                                       if r.get("ngay_cap") else "") if x)[:140]
                dong["hieu_luc"] = str(getdate(r["het_han"])) if r.get("het_han") else None
        ra.append(dong)
    return ra


def thieu_a(dong, phan_loai, nguon, loai_ncc, ngay):
    """[câu] — mục bắt buộc (1–6) áp dụng mà chưa "Có" hoặc hiệu lực đã qua ngày đánh giá. Mục 6 ghi KAD là người
    chấm xác nhận không áp dụng."""
    d = getdate(ngay)
    theo = {cint(r.get("tt")): r for r in dong or []}
    ra = []
    for tt in BAT_BUOC_A:
        r = theo.get(tt) or {}
        ap = ap_dung(tt, phan_loai, nguon, loai_ncc)
        kq = r.get("ket_qua") or ""
        if ap is False or (ap is None and kq == KAD):
            continue
        if kq != CO:
            ra.append(f"Mục {tt}: {'chưa chấm' if not kq else kq}")
        elif r.get("hieu_luc") and getdate(r["hieu_luc"]) < d:
            ra.append(f"Mục {tt}: hết hiệu lực {_ngay_vn(r['hieu_luc'])}")
    return ra


def loi_a(dong, phan_loai, nguon, loai_ncc):
    """[câu] — dòng phần A sai luật giấy: mục 1, 2, 7 chỉ Có / Không; mục 3–5 áp dụng thì không ghi KAD được."""
    ra = []
    for r in dong or []:
        tt, kq = cint(r.get("tt")), r.get("ket_qua") or ""
        if tt not in MUC_A:
            ra.append(f"Mục {tt} không có trong phiếu.")
        elif kq not in ("", CO, KHONG, KAD):
            ra.append(f"Mục {tt}: chọn Có / Không / KAD.")
        elif kq == KAD and not MUC_A[tt][2]:
            ra.append(f"Mục {tt}: chỉ Có / Không (giấy không có ô KAD).")
        elif kq == KAD and ap_dung(tt, phan_loai, nguon, loai_ncc):
            ra.append(f"Mục {tt} áp dụng cho {MUC_A[tt][1].lower()} — chọn Có / Không.")
    return ra


# ── Phần B, kết luận ──────────────────────────────────────────────────────────────────────

def diem_hop_le(k, v):
    """Điểm ô `k` là một mức in sẵn trên giấy (I: 10 / 5 / 0…). Trống / chữ / mức lạ → False."""
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return False
    return n in {d for _m, d in MUC_B[k][2]}


def diem_v(dong):
    """Điểm mục V theo mục A7: có giấy chứng nhận (Có, còn hiệu lực ở cột A) → 2, không → 0."""
    r = next((r for r in dong or [] if cint(r.get("tt")) == 7), {})
    return 2 if r.get("ket_qua") == CO else 0


def ket_luan(du_a, i, tong):
    """Kết luận theo giấy. Loại bỏ trước: thiếu phần A, điểm chất lượng < 5, tổng < 20."""
    if not du_a or cint(i) < 5 or cint(tong) < 20:
        return LOAI_BO
    return CHAP_NHAN if cint(tong) >= 30 else XEM_XET


def tinh(doc):
    """{diem_v, tong, thieu, ket_luan, du} của một phiếu (dict / Document). `du` = đủ 4 điểm chấm tay — chưa đủ thì
    chưa kết luận (None)."""
    dong = [dict(r) if not isinstance(r, dict) else r for r in doc.get("ho_so") or []]
    v = diem_v(dong)
    du = all(diem_hop_le(k, doc.get(k)) for k in CHAM_TAY)
    tong = sum(cint(doc.get(k)) for k in CHAM_TAY) + v
    thieu = thieu_a(dong, doc.get("phan_loai"), doc.get("nguon"), doc.get("loai_ncc"), doc.get("ngay"))
    return {"diem_v": v, "tong": tong, "thieu": thieu, "du": du,
            "ket_luan": ket_luan(not thieu, doc.get("diem_i"), tong) if du else None}


def goi_y_diem_i(so_lo, khong_dat):
    """Gợi ý điểm I khi đánh giá lại: tỷ lệ lô Không đạt 12 tháng — 0 % → 10, < 10 % → 5, ≥ 10 % → 0. Không có lô →
    None (chấm theo mẫu / lô thử)."""
    if not so_lo:
        return None
    ty = khong_dat / so_lo
    return 10 if ty == 0 else (5 if ty < 0.10 else 0)


def ket_qua_duyet(ket_luan_app, quyet_dinh):
    """Kết quả cuối khi Giám đốc duyệt: Chấp nhận / Loại bỏ — phiếu Xem xét theo quyết định của Giám đốc."""
    if ket_luan_app == CHAP_NHAN:
        return CHAP_NHAN
    if ket_luan_app == XEM_XET:
        return CHAP_NHAN if quyet_dinh == CHAP_NHAN else LOAI_BO
    return LOAI_BO


def han_lai(ngay_duyet):
    return cong_thang(getdate(ngay_duyet), THANG_LAI)


def phan_loai_mac_dinh(loai_ncc):
    """Phân loại QT.07 gợi ý từ loại NCC (W09): nguyên liệu, phụ gia, bao bì tiếp xúc, cát rang → loại 1."""
    return LOAI_1 if loai_ncc in (NCC.TP, NCC.PHU_GIA, NCC.BB_TX, NCC.CAT) else LOAI_2


def trang_thai_ncc(phieu, hom_nay):
    """Trạng thái đánh giá của một NCC từ các phiếu ĐÃ DUYỆT (mới nhất trước): {phieu, ket_qua, han, con (ngày)} |
    None khi chưa có phiếu duyệt."""
    if not phieu:
        return None
    p = phieu[0]
    han = _ngay(p.get("han_danh_gia_lai"))
    return {"phieu": p.get("name"), "ket_qua": p.get("ket_qua"), "ngay": str(p.get("ngay") or ""),
            "han": str(han) if han else None, "con": (han - getdate(hom_nay)).days if han else None}


def co_chap_nhan(phieu, hom_nay):
    """Phiếu đã duyệt mới nhất là Chấp nhận và còn hạn đánh giá lại."""
    t = trang_thai_ncc(phieu, hom_nay)
    return bool(t and t["ket_qua"] == CHAP_NHAN and t["con"] is not None and t["con"] >= 0)


def nhac_thuan(ncc, phieu_theo, cho, hom_nay, han_dau):
    """Dữ liệu nhắc mảng ncc (chữ ở sx/qc/nhac.py). `ncc` = [{name, ten, loai, duyet}] NCC đã phân loại (trừ dịch
    vụ); `phieu_theo` = {ncc: [phiếu đã duyệt, mới nhất trước]}; `cho` = phiếu chờ QC / chờ duyệt.
    → {qua_han, sap_han, chua_co (NCC đã duyệt chưa có phiếu — hạn lần đầu), chap_nhan_chua_duyet, loai_bo_dang_duyet,
       cho_qc, cho_duyet, han_dau}."""
    nay = getdate(hom_nay)
    ra = {"qua_han": [], "sap_han": [], "chua_co": [], "chap_nhan_chua_duyet": [], "loai_bo_dang_duyet": [],
          "cho_qc": [p for p in cho if p.get("trang_thai") == CHO_QC],
          "cho_duyet": [p for p in cho if p.get("trang_thai") == CHO_DUYET], "han_dau": str(han_dau)}
    for s in ncc:
        t = trang_thai_ncc(phieu_theo.get(s["name"]) or [], nay)
        x = {"ncc": s["name"], "ten": s.get("ten") or s["name"]}
        if t is None:
            if s.get("duyet") and (han_dau - nay).days <= BAO_TRUOC:
                ra["chua_co"].append(dict(x, con=(han_dau - nay).days))
            continue
        if t["ket_qua"] == LOAI_BO:
            if s.get("duyet"):
                ra["loai_bo_dang_duyet"].append(dict(x, phieu=t["phieu"]))
            continue
        if not s.get("duyet"):
            if t["con"] is not None and t["con"] >= 0:
                ra["chap_nhan_chua_duyet"].append(dict(x, phieu=t["phieu"]))
            continue
        if t["con"] is not None and t["con"] < 0:
            ra["qua_han"].append(dict(x, han=t["han"], con=t["con"]))
        elif t["con"] is not None and t["con"] <= BAO_TRUOC:
            ra["sap_han"].append(dict(x, han=t["han"], con=t["con"]))
    for k in ("qua_han", "sap_han"):
        ra[k].sort(key=lambda x: x["han"])
    return ra


# ── Đọc DB ────────────────────────────────────────────────────────────────────────────────

def ngay_ap_dung():
    """Ngày áp dụng C26 (SX QC Setting) — trống / chưa migrate → None (chưa chặn)."""
    try:
        v = frappe.get_cached_doc("SX QC Setting").get("ncc_ngay_ap_dung_bm0701")
    except Exception:
        v = None
    return getdate(v) if v else None


def han_dau():
    try:
        v = frappe.get_cached_doc("SX QC Setting").get("ncc_han_danh_gia_dau")
    except Exception:
        v = None
    return getdate(v) if v else HAN_DAU


def phieu_duyet(supplier=None):
    """{ncc: [phiếu đã duyệt, mới nhất trước]}. Chưa migrate → {}."""
    loc = {"trang_thai": DA_DUYET}
    if supplier:
        loc["supplier"] = supplier
    try:
        ds = frappe.get_all(PT, filters=loc, fields=["name", "supplier", "ngay", "ket_qua", "han_danh_gia_lai",
                                                      "duyet_luc"], order_by="duyet_luc desc, creation desc")
    except Exception:
        return {}
    ra = {}
    for x in ds:
        ra.setdefault(x.supplier, []).append(x)
    return ra


def chap_nhan_con_han(supplier, hom_nay):
    return co_chap_nhan(phieu_duyet(supplier).get(supplier) or [], hom_nay)


def ds_ncc():
    """NCC đã phân loại, đang dùng, trừ dịch vụ: [{name, ten, loai, nguon, duyet}]. Chưa migrate → []."""
    try:
        ds = frappe.get_all("Supplier", filters={"disabled": 0, "custom_loai_ncc": ("is", "set")},
                            fields=["name", "supplier_name", "custom_loai_ncc", "custom_nguon_goc", "custom_ncc_duyet"],
                            order_by="supplier_name asc")
    except Exception:
        return []
    return [{"name": s.name, "ten": s.supplier_name or s.name, "loai": s.custom_loai_ncc,
             "nguon": s.custom_nguon_goc or "", "duyet": bool(cint(s.custom_ncc_duyet))}
            for s in ds if s.custom_loai_ncc != NCC.DV]


def lo_12_thang(supplier, ngay):
    """(số lô, số lô Không đạt, chữ) 12 tháng trước ngày đánh giá — BM.07.03 trên phiếu nhập mua / hoá đơn mua trừ
    kho đã duyệt (dòng có kết luận tiếp nhận) + phiếu sự cố BM.08.02 (không phải từ tiếp nhận) gắn lô của NCC."""
    den = getdate(ngay)
    tu = cong_thang(den, -THANG_LAI)
    so_lo, khong, cach_ly, lo = 0, 0, 0, set()
    for dt in ("Purchase Receipt", "Purchase Invoice"):
        loc = {"docstatus": 1, "is_return": 0, "supplier": supplier, "posting_date": ("between", [str(tu), str(den)])}
        if dt == "Purchase Invoice":
            loc["update_stock"] = 1
        try:
            phieu = frappe.get_all(dt, filters=loc, pluck="name")
            dong = frappe.get_all(f"{dt} Item", filters={"parenttype": dt, "parent": ("in", phieu)},
                                  fields=["custom_ket_luan", "batch_no"]) if phieu else []
        except Exception:
            continue
        for r in dong:
            if not r.custom_ket_luan:
                continue
            so_lo += 1
            khong += r.custom_ket_luan == "Không đạt"
            cach_ly += r.custom_ket_luan == "Cách ly"
            if r.batch_no:
                lo.add(r.batch_no)
    sc = 0
    if lo:
        try:
            cha = sorted({x.parent for x in frappe.get_all("SX Su Co Lo", filters={
                "parenttype": "SX Su Co", "batch": ("in", sorted(lo))}, fields=["parent"])})
            sc = len([x for x in frappe.get_all("SX Su Co", filters={"name": ("in", cha or [""])},
                                                fields=["name", "nguon", "ngay"])
                      if x.nguon != "Tiếp nhận NL" and x.ngay and tu <= getdate(x.ngay) <= den])
        except Exception:
            sc = 0
    khong += sc
    chu = (f"12 tháng: {so_lo} lô nhận, {khong} không đạt" + (f" (gồm {sc} phiếu sự cố sau nhận)" if sc else "")
           + (f", {cach_ly} cách ly" if cach_ly else "") + (f" — {khong * 100 / so_lo:.0f} %" if so_lo else ""))
    return so_lo, khong, chu if so_lo else "12 tháng: chưa có lô nhận nào có kết luận BM.07.03 — chấm theo mẫu / lô thử."


def nhac(hom_nay):
    """Dữ liệu nhắc mảng ncc. Chưa migrate → {}."""
    try:
        cho = frappe.get_all(PT, filters={"trang_thai": ("in", [CHO_QC, CHO_DUYET])},
                             fields=["name", "supplier", "ten_ncc", "trang_thai", "phan_loai", "danh_gia_luc"],
                             order_by="danh_gia_luc asc")
    except Exception:
        return {}
    return nhac_thuan(ds_ncc(), phieu_duyet(), cho, hom_nay, han_dau())
