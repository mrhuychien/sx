"""Lịch việc định kỳ cho hồ sơ giấy (W21, D146) — việc năm / quý / tháng lên hộp nhắc QC.

Mỗi việc một bản ghi SX Viec Dinh Ky: tên, chu kỳ, hạn lần tới, nhắc trước bao nhiêu ngày. Bấm
"Đã làm" → ghi lần làm (ngày, người, ghi chú) và dời hạn sang kỳ sau TÍNH TỪ HẠN CŨ (việc
tháng 11 hằng năm làm muộn vẫn là tháng 11 năm sau); việc "Một lần" làm xong thì ngừng.
Patch tạo sẵn hai việc tài liệu 08/10 nêu: thử khôi phục dữ liệu (T11/2026), thay bóng đèn bẫy
côn trùng (T3/2027).

W35 (D166): thêm chu kỳ "2 năm"; hạn để trống được khi chưa biết — hiện "Chưa đặt hạn" và hộp nhắc
nói ra, không im lặng. Kiểm nghiệm KH.KN.01 ngoài thành phẩm (nước, nguyên liệu, bao bì, thẩm tra vải
ủ) là việc định kỳ có ô "mẫu của" (doi_tuong_kn): nhắc ở mảng Kiểm nghiệm, và LẦN LÀM = phiếu gửi mẫu
(SX Kiem Nghiem gắn việc) — không bấm "Đã làm" tay; xoá phiếu thì lần làm bỏ theo.
"""

import frappe
from frappe.utils import cint, getdate

from sx.qc.thiet_bi import cong_thang

PT = "SX Viec Dinh Ky"
KN_PT = "SX Kiem Nghiem"           # đọc theo tên — module này không import kiem_nghiem
THANG = {"Năm": 12, "2 năm": 24, "Quý": 3, "Tháng": 1, "Một lần": 0}
QUA_HAN, SAP_DEN, CON_HAN, NGUNG, CHUA_HAN = "Quá hạn", "Sắp đến hạn", "Còn hạn", "Ngừng", "Chưa đặt hạn"
# "Mẫu của" của việc kiểm nghiệm — khớp SX Kiem Nghiem.doi_tuong (sản phẩm, cát có kế hoạch riêng).
DOI_TUONG_KN = ("Nước", "Nguyên liệu", "Khác")
TAN_SUAT = {"Năm": "1 lần / năm", "2 năm": "2 năm / lần", "Quý": "1 lần / quý", "Tháng": "1 lần / tháng",
            "Một lần": "một lần"}


def ke_tiep(han, chu_ky):
    """Hạn kỳ sau tính từ hạn cũ; "Một lần" → None (xong là hết)."""
    n = THANG.get(chu_ky or "Năm", 12)
    return cong_thang(han, n) if n else None


def trang_thai(v, hom_nay):
    """(trạng thái, số ngày còn) — hàm thuần. `v` = {han, bao_truoc, ngung}."""
    if cint(v.get("ngung")):
        return NGUNG, None
    if not v.get("han"):
        return CHUA_HAN, None
    con = (getdate(v["han"]) - getdate(hom_nay)).days
    if con < 0:
        return QUA_HAN, con
    if con <= (cint(v.get("bao_truoc")) or 14):
        return SAP_DEN, con
    return CON_HAN, con


def ghi_lan(doc, ngay, ghi_chu="", phieu_kn=None):
    """Ghi một lần làm vào việc `doc` (chưa lưu): dời hạn sang kỳ sau tính từ hạn cũ — chưa đặt hạn thì từ
    ngày làm; "Một lần" làm xong thì ngừng."""
    doc.append("ds_lan", {"ngay": ngay, "nguoi": frappe.session.user, "han_ky": doc.han, "ghi_chu": ghi_chu,
                          "phieu_kn": phieu_kn})
    doc.lan_cuoi = ngay
    moi = ke_tiep(doc.han or ngay, doc.chu_ky)
    if moi:
        doc.han = moi
    else:
        doc.ngung = 1


def bo_lan(doc, phieu_kn):
    """Bỏ lần làm của phiếu gửi mẫu `phieu_kn` (phiếu bị xoá / gắn sang việc khác) — chưa lưu. Là lần cuối thì
    trả hạn về kỳ hạn của lần đó và mở lại việc "Một lần". Không có → False."""
    ds = list(doc.get("ds_lan") or [])
    lan = next((r for r in ds if r.get("phieu_kn") == phieu_kn), None)
    if lan is None:
        return False
    con = [r for r in ds if r is not lan]
    doc.set("ds_lan", con)
    if lan is ds[-1]:
        doc.han = lan.get("han_ky")
        doc.lan_cuoi = con[-1].get("ngay") if con else None
        if doc.chu_ky == "Một lần":
            doc.ngung = 0
    return True


def viec_kn(hom_nay):
    """Việc kiểm nghiệm (có ô mẫu của) cho màn Kiểm nghiệm: trạng thái + phiếu gửi mẫu gần nhất. Chưa migrate → []."""
    try:
        ds = frappe.get_all(PT, filters={"doi_tuong_kn": ("is", "set")},
                            fields=["name", "ten", "chu_ky", "han", "bao_truoc", "ngung", "doi_tuong_kn", "mo_ta",
                                    "ho_so", "lan_cuoi"], order_by="ngung asc, han asc")
        phieu = {}
        for p in frappe.get_all(KN_PT, filters={"viec_dinh_ky": ("in", [v.name for v in ds])},
                                fields=["name", "viec_dinh_ky", "ngay_gui", "ket_qua", "so_phieu"],
                                order_by="ngay_gui asc, creation asc") if ds else []:
            phieu[p.viec_dinh_ky] = p
    except Exception:
        return []
    ra = []
    for v in ds:
        tt, con = trang_thai(v, hom_nay)
        p = phieu.get(v.name)
        ra.append(dict(v, han=str(v.han or ""), lan_cuoi=str(v.lan_cuoi or ""), trang_thai=tt, con=con,
                       tan_suat=TAN_SUAT.get(v.chu_ky) or v.chu_ky or "",
                       phieu_cuoi={"name": p.name, "ngay_gui": str(p.ngay_gui), "ket_qua": p.ket_qua or "",
                                   "so_phieu": p.so_phieu or ""} if p else None))
    return ra


def nhac(hom_nay):
    """Việc quá hạn / sắp đến hạn / chưa đặt hạn cho hộp nhắc QC; việc kiểm nghiệm tách riêng (mảng Kiểm
    nghiệm): {qua_han, sap_den, chua_han, kiem_nghiem: {qua_han, sap_den, chua_han}}. Chưa migrate → {}."""
    try:
        ds = frappe.get_all(PT, filters={"ngung": 0},
                            fields=["name", "ten", "han", "bao_truoc", "ngung", "chu_ky", "doi_tuong_kn"],
                            order_by="han asc")
    except Exception:
        return {}
    ra = {"qua_han": [], "sap_den": [], "chua_han": [], "kiem_nghiem": {"qua_han": [], "sap_den": [], "chua_han": []}}
    khoa = {QUA_HAN: "qua_han", SAP_DEN: "sap_den", CHUA_HAN: "chua_han"}
    for v in ds:
        tt, con = trang_thai(v, hom_nay)
        if tt in khoa:
            (ra["kiem_nghiem"] if v.get("doi_tuong_kn") else ra)[khoa[tt]].append(
                {"name": v.name, "ten": v.ten, "han": str(v.han or ""), "con": con,
                 "doi_tuong_kn": v.get("doi_tuong_kn") or ""})
    return ra
