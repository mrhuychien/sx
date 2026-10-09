"""Lịch việc định kỳ cho hồ sơ giấy (W21, D146) — việc năm / quý / tháng lên hộp nhắc QC.

Mỗi việc một bản ghi SX Viec Dinh Ky: tên, chu kỳ, hạn lần tới, nhắc trước bao nhiêu ngày. Bấm
"Đã làm" → ghi lần làm (ngày, người, ghi chú) và dời hạn sang kỳ sau TÍNH TỪ HẠN CŨ (việc
tháng 11 hằng năm làm muộn vẫn là tháng 11 năm sau); việc "Một lần" làm xong thì ngừng.
Patch tạo sẵn hai việc tài liệu 08/10 nêu: thử khôi phục dữ liệu (T11/2026), thay bóng đèn bẫy
côn trùng (T3/2027).
"""

import frappe
from frappe.utils import cint, getdate

from sx.qc.thiet_bi import cong_thang

PT = "SX Viec Dinh Ky"
THANG = {"Năm": 12, "Quý": 3, "Tháng": 1, "Một lần": 0}
QUA_HAN, SAP_DEN, CON_HAN, NGUNG = "Quá hạn", "Sắp đến hạn", "Còn hạn", "Ngừng"


def ke_tiep(han, chu_ky):
    """Hạn kỳ sau tính từ hạn cũ; "Một lần" → None (xong là hết)."""
    n = THANG.get(chu_ky or "Năm", 12)
    return cong_thang(han, n) if n else None


def trang_thai(v, hom_nay):
    """(trạng thái, số ngày còn) — hàm thuần. `v` = {han, bao_truoc, ngung}."""
    if cint(v.get("ngung")) or not v.get("han"):
        return NGUNG, None
    con = (getdate(v["han"]) - getdate(hom_nay)).days
    if con < 0:
        return QUA_HAN, con
    if con <= (cint(v.get("bao_truoc")) or 14):
        return SAP_DEN, con
    return CON_HAN, con


def nhac(hom_nay):
    """Việc quá hạn / sắp đến hạn cho hộp nhắc QC. Chưa migrate → {}."""
    try:
        ds = frappe.get_all(PT, filters={"ngung": 0}, fields=["name", "ten", "han", "bao_truoc", "ngung", "chu_ky"],
                            order_by="han asc")
    except Exception:
        return {}
    qua, sap = [], []
    for v in ds:
        tt, con = trang_thai(v, hom_nay)
        x = {"name": v.name, "ten": v.ten, "han": str(v.han), "con": con}
        if tt == QUA_HAN:
            qua.append(x)
        elif tt == SAP_DEN:
            sap.append(x)
    return {"qua_han": qua, "sap_den": sap}
