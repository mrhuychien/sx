"""Phiếu rework BM.15.01 (W19, D145) — phần tính, đọc dữ liệu qua frappe.

Đưa hàng đem rework (bánh vỡ, hàng trả về đã xử lý…) vào một mẻ sản xuất. Hai luật cứng theo
tài liệu 08/10:
  · KHÔNG QUÁ 10% khối lượng mẻ (rework / khối lượng mẻ, mẻ tính cả phần rework);
  · KHÔNG đưa hàng CÓ LẠC vào sản phẩm KHÔNG LẠC (dị ứng — cờ "Có lạc" của bộ tự công bố W28).
Sữa bột vào sản phẩm không sữa: chỉ cảnh báo (tài liệu chưa nói chặn) — nhãn phải đúng.

Phiếu sự cố quyết định "Rework (BM.15.01)" chỉ đóng được khi đã có phiếu rework gắn với nó.
"""

import frappe
from frappe.utils import cint, flt

PT, SP = "SX Rework", "SX San Pham Cong Bo"
TOI_DA = 10.0          # % khối lượng mẻ
QD_REWORK = "Rework (BM.15.01)"


def ty_le(kl_rework, kl_me):
    """% rework trên khối lượng mẻ, 2 chữ số. Mẻ 0 → None."""
    me = flt(kl_me)
    return round(flt(kl_rework) * 100.0 / me, 2) if me > 0 else None


def kiem(p, nguon, dich):
    """Hàm thuần → {"loi": [lý do chặn], "canh_bao": [...], "ty_le": %}.
    `p` = {kl_rework, kl_me}; `nguon` / `dich` = {co_lac, co_sua_bot, ten} của sản phẩm."""
    loi, canh = [], []
    kr, km = flt(p.get("kl_rework")), flt(p.get("kl_me"))
    if kr <= 0:
        loi.append("Khối lượng đem rework phải lớn hơn 0.")
    if km <= 0:
        loi.append("Khối lượng mẻ phải lớn hơn 0.")
    tl = ty_le(kr, km)
    if kr > 0 and km > 0:
        if kr > km:
            loi.append("Khối lượng rework lớn hơn cả mẻ — kiểm lại số.")
        elif tl > TOI_DA:
            loi.append(f"Rework {tl:g}% khối lượng mẻ — vượt {TOI_DA:g}% (tối đa {km * TOI_DA / 100:g} kg cho mẻ "
                       f"{km:g} kg).")
    if nguon and dich:
        if cint(nguon.get("co_lac")) and not cint(dich.get("co_lac")):
            loi.append(f"Hàng CÓ LẠC ({nguon.get('ten') or ''}) không được đưa vào sản phẩm KHÔNG LẠC "
                       f"({dich.get('ten') or ''}) — dị ứng.")
        if cint(nguon.get("co_sua_bot")) and not cint(dich.get("co_sua_bot")):
            canh.append(f"Hàng có sữa bột đưa vào sản phẩm không có sữa bột ({dich.get('ten') or ''}) — kiểm lại "
                        f"nhãn cảnh báo dị ứng.")
    return {"loi": loi, "canh_bao": canh, "ty_le": tl}


def san_pham(ten):
    """{co_lac, co_sua_bot, ten} của một sản phẩm tự công bố, None nếu không có."""
    if not ten:
        return None
    try:
        r = frappe.db.get_value(SP, ten, ["co_lac", "co_sua_bot", "ten_san_pham", "so_cong_bo"], as_dict=True)
    except Exception:
        return None
    if not r:
        return None
    return {"co_lac": cint(r.co_lac), "co_sua_bot": cint(r.co_sua_bot),
            "ten": f"{r.so_cong_bo + ' · ' if r.so_cong_bo else ''}{r.ten_san_pham or ten}"}


def co_phieu_cua_su_co(su_co):
    """Phiếu sự cố này đã có phiếu rework chưa. Chưa migrate → coi như có (đừng chặn đóng)."""
    try:
        return bool(frappe.db.exists(PT, {"su_co": su_co}))
    except Exception:
        return True
