"""Thiết bị đo, hiệu chuẩn BM.06.01–06.04 (W17, D143) — phần tính, đọc dữ liệu qua frappe.

Danh mục thiết bị (BM.06.01): đồng hồ nhiệt (BM.06.02, 1 lần / năm), nam châm (BM.06.03),
lưới sàng, rây (BM.06.04 — LS-01 riêng cho máy rang M1, M2, M3), cân (theo hạn ghi trên
giấy kiểm định). Mỗi lần kiểm là một phiếu SX Kiem Thiet Bi.

Hạn kế tiếp = lần kiểm gần nhất + chu kỳ (tháng), hoặc hạn ghi trên giấy hiệu chuẩn / kiểm
định nếu có; cân luôn theo hạn giấy kiểm định gần nhất. Chưa kiểm lần nào → hạn đầu (SX QC
Setting, mặc định 31/10/2026 — tài liệu 08/10).
Không đạt hoặc quá hạn → NGỪNG DÙNG và lập phiếu sự cố BM.08.02 (nguồn Thiết bị đo). Quá
hạn do lịch chạy nền mỗi ngày quét — một phiếu gộp cho các thiết bị mới quá hạn hôm đó.
Kiểm lại Đạt → thiết bị dùng lại.
"""

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

TB, KT = "SX Thiet Bi Do", "SX Kiem Thiet Bi"
DONG_HO, NAM_CHAM, LUOI, CAN, KHAC = "Đồng hồ nhiệt", "Nam châm", "Lưới sàng, rây", "Cân", "Khác"
LOAI = (DONG_HO, NAM_CHAM, LUOI, CAN, KHAC)
# Biểu mẫu theo loại (BM.06.01 là danh mục). Cân / khác nằm trong danh mục, không có tờ riêng.
BIEU_MAU = {DONG_HO: "BM.06.02", NAM_CHAM: "BM.06.03", LUOI: "BM.06.04"}
# Chu kỳ mặc định (tháng) khi thiết bị để trống. Đồng hồ nhiệt 1 năm theo tài liệu; nam châm,
# lưới sàng 12 tháng (chốt 09/10/2026 — thiết bị nào khác thì Ban ISO sửa chu kỳ của nó). Cân: hạn
# là hạn ghi trên giấy kiểm định; 12 tháng chỉ để dự phòng khi chưa có giấy nào.
CHU_KY = {DONG_HO: 12, NAM_CHAM: 12, LUOI: 12, CAN: 12, KHAC: 12}
HAN_DAU = date(2026, 10, 31)
DANG_DUNG, NGUNG_HONG, NGUNG_HAN, THANH_LY = ("Đang dùng", "Ngừng — không đạt",
                                              "Ngừng — quá hạn", "Thanh lý")
DAT, KHONG_DAT = "Đạt", "Không đạt"
NOI_BO = "Kiểm tra nội bộ"
SAP_DEN = 30   # ngày: báo "sắp đến hạn"


def cong_thang(d, n):
    """Ngày + n tháng (31/01 + 1 tháng = 28/02 hoặc 29/02) — không cần frappe.utils."""
    d = getdate(d)
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def chu_ky(tb):
    """Tháng. Ô Int trống trên Desk là 0 → hiểu là "theo loại"."""
    v = cint(tb.get("chu_ky_thang"))
    return v if v > 0 else CHU_KY.get(tb.get("loai"), 12)


def han_ke_tiep(tb, cuoi, han_dau=HAN_DAU, giay=None):
    """Hạn kiểm kế tiếp — hàm thuần.
    `cuoi` = phiếu kiểm gần nhất ({ngay, han_giay}), `giay` = phiếu gần nhất CÓ hạn giấy.
    · Cân: hạn ghi trên giấy kiểm định gần nhất — lần kiểm nội bộ bằng quả chuẩn không kéo
      dài hạn kiểm định pháp lý. Chưa có giấy nào → lần kiểm cuối + chu kỳ.
    · Thiết bị khác: lần kiểm gần nhất — có hạn giấy (hiệu chuẩn ngoài) thì lấy hạn giấy,
      không thì ngày kiểm + chu kỳ.
    · Chưa kiểm lần nào: hạn đầu (31/10/2026)."""
    if tb.get("loai") == CAN and giay and giay.get("han_giay"):
        return getdate(giay["han_giay"])
    if not cuoi:
        return getdate(han_dau)
    if cuoi.get("han_giay"):
        return getdate(cuoi["han_giay"])
    return cong_thang(cuoi["ngay"], chu_ky(tb))


def trang_thai(tb, cuoi, hom_nay, han_dau=HAN_DAU, giay=None):
    """(trạng thái, hạn) — hàm thuần. Thanh lý giữ nguyên; lần kiểm gần nhất Không đạt →
    ngừng; quá hạn → ngừng; còn lại đang dùng."""
    han = han_ke_tiep(tb, cuoi, han_dau, giay)
    if cint(tb.get("thanh_ly")):
        return THANH_LY, han
    if cuoi and cuoi.get("ket_qua") == KHONG_DAT:
        return NGUNG_HONG, han
    if getdate(hom_nay) > han:
        return NGUNG_HAN, han
    return DANG_DUNG, han


def _so(v):
    """"12,5" / 12.5 → 12.5; trống → None; không phải số → False."""
    t = str(v if v is not None else "").strip().replace(",", ".")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return False


def danh_gia(p):
    """Đánh giá một phiếu kiểm theo loại thiết bị — hàm thuần.
    → {"thieu": [ô chưa ghi], "hong": [lý do Không đạt], "sai_so": số | None}.
    Có lý do hỏng thì phiếu PHẢI là Không đạt (controller ép)."""
    loai, thieu, hong, sai_so = p.get("loai"), [], [], None
    if loai == DONG_HO:
        # Ô chữ chứ không Float: 0 °C (nước đá) là điểm đo thật, còn Float trống cũng ra 0.
        cap = []
        for i in (1, 2):
            c, d = _so(p.get(f"chuan_{i}")), _so(p.get(f"doc_{i}"))
            if c is False or d is False:
                thieu.append(f"điểm {i}: nhập số")
            elif (c is None) != (d is None):
                thieu.append(f"điểm {i}: đủ cả nhiệt độ chuẩn và số đồng hồ đọc")
            elif c is not None:
                cap.append((c, d))
        if not cap and not thieu:
            thieu.append("ít nhất một điểm đo (nhiệt độ chuẩn + đồng hồ đọc)")
        elif cap:
            sai_so = round(max(abs(d - c) for c, d in cap), 2)
            cho = float(p.get("sai_so_cho_phep") or 2)
            if sai_so > cho:
                hong.append(f"sai số {sai_so:g} °C vượt ± {cho:g} °C")
    tieu_chi = {NAM_CHAM: (("be_mat", "bề mặt nam châm"), ("luc_hut", "lực hút")),
                LUOI: (("nguyen_ven", "không rách, thủng"), ("mat_luoi", "mắt lưới"), ("khung", "khung, mối hàn"))}
    for f, ten in tieu_chi.get(loai, ()):
        if not p.get(f):
            thieu.append(ten)
        elif p.get(f) == KHONG_DAT:
            hong.append(f"{ten} không đạt")
    if loai == CAN and p.get("hinh_thuc") == "Kiểm định bên ngoài":
        if not p.get("so_giay"):
            thieu.append("số giấy kiểm định")
        if not p.get("han_giay"):
            thieu.append("hạn ghi trên giấy kiểm định")
    return {"thieu": thieu, "hong": hong, "sai_so": sai_so}


def co_chung_chi(ds, user, ngay):
    """Người này có chứng chỉ còn hạn vào ngày kiểm không (W17 (f)) — hàm thuần."""
    d = getdate(ngay)
    return any(r.get("user") == user and r.get("hinh_thuc") == "Chứng chỉ"
               and (not r.get("han") or getdate(r["han"]) >= d) for r in ds or [])


def han_dau():
    try:
        v = frappe.get_cached_doc("SX QC Setting").get("thiet_bi_han_dau")
    except Exception:
        v = None
    return getdate(v) if v else HAN_DAU


def lan_cuoi(ten, co_giay=False):
    loc = {"thiet_bi": ten}
    if co_giay:
        loc["han_giay"] = ("is", "set")
    ds = frappe.get_all(KT, filters=loc, fields=["name", "ngay", "ket_qua", "han_giay"],
                        order_by="ngay desc, creation desc", limit=1)
    return ds[0] if ds else None


def cap_nhat(ten, hom_nay=None):
    """Ghi lại tóm tắt trên thiết bị (lần kiểm cuối, kết quả, hạn, trạng thái) — sau mỗi lần
    ghi / sửa / xoá phiếu kiểm, và mỗi ngày (lịch chạy nền)."""
    tb = frappe.db.get_value(TB, ten, ["name", "loai", "chu_ky_thang", "thanh_ly", "trang_thai",
                                       "han_kiem"], as_dict=True)
    if not tb:
        return None
    cuoi = lan_cuoi(ten)
    tt, han = trang_thai(tb, cuoi, hom_nay or nowdate(), han_dau(), lan_cuoi(ten, True))
    frappe.db.set_value(TB, ten, {
        "trang_thai": tt, "han_kiem": han,
        "lan_kiem_cuoi": cuoi.ngay if cuoi else None,
        "ket_qua_cuoi": cuoi.ket_qua if cuoi else "",
        "phieu_cuoi": cuoi.name if cuoi else None,
    }, update_modified=False)
    return tt


def _su_co(mo_ta, muc_do="Cao"):
    sc = frappe.get_doc({"doctype": "SX Su Co", "ngay": getdate(nowdate()), "nguon": "Thiết bị đo",
                         "loai": "Khác", "muc_do": muc_do, "trang_thai": "Mở", "mo_ta": mo_ta[:1000]})
    # Người kiểm có thể không có quyền tạo phiếu sự cố trên Desk, nhưng thiết bị hỏng /
    # quá hạn PHẢI có phiếu — như lô không đạt xuất xưởng.
    sc.insert(ignore_permissions=True)
    return sc.name


def lap_su_co_khong_dat(phieu):
    """Phiếu kiểm Không đạt → phiếu sự cố (một lần mỗi phiếu kiểm)."""
    return _su_co(_("Thiết bị {0} ({1}) KHÔNG ĐẠT khi kiểm ngày {2} ({3}) — ngừng dùng, sửa / thay, "
                    "kiểm lại trước khi dùng; xem lại số đo từ lần kiểm Đạt trước.{4}").format(
        phieu.thiet_bi, phieu.ten_thiet_bi or "", getdate(phieu.ngay).strftime("%d/%m/%Y"), phieu.name,
        (" " + phieu.ghi_chu) if phieu.get("ghi_chu") else ""))


def quet_qua_han():
    """Lịch chạy nền mỗi ngày: cập nhật trạng thái mọi thiết bị; thiết bị MỚI quá hạn (chưa
    lập phiếu cho hạn này) → một phiếu sự cố gộp, ghi lại hạn đã lập phiếu."""
    try:
        ds = frappe.get_all(TB, filters={"thanh_ly": 0}, fields=["name", "ten", "qua_han_su_co_han"])
    except Exception:
        return None
    moi = []
    for x in ds:
        tt = cap_nhat(x.name)
        han = frappe.db.get_value(TB, x.name, "han_kiem")
        if tt == NGUNG_HAN and str(x.qua_han_su_co_han or "") != str(han or ""):
            moi.append((x, han))
    if not moi:
        return None
    ten = _su_co(_("{0} thiết bị đo QUÁ HẠN kiểm / hiệu chuẩn — ngừng dùng tới khi kiểm lại Đạt: {1}").format(
        len(moi), "; ".join(f"{x.name} {x.ten or ''} (hạn {getdate(h).strftime('%d/%m/%Y')})".strip()
                            for x, h in moi)))
    for x, h in moi:
        frappe.db.set_value(TB, x.name, {"qua_han_su_co": ten, "qua_han_su_co_han": h}, update_modified=False)
    return ten


def cac_lan_cuoi():
    """({thiết bị: phiếu gần nhất}, {thiết bị: phiếu gần nhất có hạn giấy}) — một truy vấn."""
    cuoi, giay = {}, {}
    for k in frappe.get_all(KT, fields=["name", "thiet_bi", "ngay", "ket_qua", "han_giay"],
                            order_by="ngay asc, creation asc"):
        cuoi[k.thiet_bi] = k
        if k.han_giay:
            giay[k.thiet_bi] = k
    return cuoi, giay


def nhac(hom_nay):
    """Dữ liệu cho hộp nhắc QC. Chưa migrate → {}."""
    d = getdate(hom_nay)
    try:
        ds = frappe.get_all(TB, filters={"thanh_ly": 0}, fields=["name", "ten", "loai", "chu_ky_thang",
                                                               "thanh_ly"])
        cuoi, giay = cac_lan_cuoi()
    except Exception:
        return {}
    hd = han_dau()
    qua, sap, hong = [], [], []
    for x in ds:
        tt, han = trang_thai(x, cuoi.get(x.name), d, hd, giay.get(x.name))
        if tt == NGUNG_HONG:
            hong.append({"ma": x.name, "ten": x.ten})
        elif tt == NGUNG_HAN:
            qua.append({"ma": x.name, "ten": x.ten, "han": str(han)})
        elif (han - d).days <= SAP_DEN:
            sap.append({"ma": x.name, "ten": x.ten, "han": str(han)})
    co_loai = {x.loai for x in ds}
    return {"qua_han": qua, "sap_den": sorted(sap, key=lambda x: x["han"]), "khong_dat": hong,
            "thieu_loai": [l for l in (DONG_HO, NAM_CHAM, LUOI, CAN) if l not in co_loai],
            "han_dau": str(hd)}
