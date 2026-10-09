"""Phiếu rework BM.15.01 (W19, D145) — phần tính, đọc dữ liệu qua frappe.

Đưa hàng đem rework (bánh vỡ, hàng trả về đã xử lý…) vào một mẻ sản xuất. Hai luật cứng theo
tài liệu 08/10:
  · KHÔNG QUÁ 10% khối lượng mẻ (rework / khối lượng mẻ, mẻ tính cả phần rework);
  · KHÔNG đưa hàng CÓ LẠC vào sản phẩm KHÔNG LẠC (dị ứng — cờ "Có lạc" của bộ tự công bố W28).
Sữa bột vào sản phẩm không sữa: chỉ cảnh báo (tài liệu chưa nói chặn) — nhãn phải đúng.

Phiếu sự cố quyết định "Rework (BM.15.01)" chỉ đóng được khi đã có phiếu rework gắn với nó.
"""

import re
from datetime import datetime, time, timedelta

import frappe
from frappe.utils import cint, flt, get_datetime, getdate

PT, SP = "SX Rework", "SX San Pham Cong Bo"
TOI_DA = 10.0          # % khối lượng mẻ
QD_REWORK = "Rework (BM.15.01)"
# W32 (D164): ô "QLSX quyết định" — người có vai quản lý sản xuất (Giám đốc SX Quan Ly cũng được).
QLSX_VAI = ("Production Manager", "SX Quan Ly")


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


def phut(t):
    """Giờ trong ngày → số phút từ 0 giờ. Nhận "HH:MM[:SS]", time, datetime, timedelta (DB trả ô Time là
    timedelta). Trống / sai → None."""
    if t is None or t == "":
        return None
    if isinstance(t, timedelta):
        return int(t.total_seconds() // 60) % (24 * 60)
    if isinstance(t, (time, datetime)):
        return t.hour * 60 + t.minute
    m = re.match(r"^\s*(\d{1,2})[:hH.](\d{2})", str(t))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        return None
    return int(m.group(1)) * 60 + int(m.group(2))


def gio(t):
    """Giờ để hiện / in: "07:05". Trống → ""."""
    p = phut(t)
    return "" if p is None else f"{p // 60:02d}:{p % 60:02d}"


def kiem_gio(p, bay_gio):
    """Giờ rework, QLSX quyết định (W32) — hàm thuần → {"loi": [...], "canh_bao": [...]}.
    `p` = {ngay, gio_bat_dau, gio_ket_thuc, qlsx_quyet_dinh, qlsx_luc}; giờ dạng "HH:MM[:SS]" / time / timedelta.

    · Rework trong cùng ngày (QT.15 mục 4): giờ kết thúc không trước giờ bắt đầu.
    · Giờ QLSX quyết định phải có người quyết định, không ở tương lai.
    · QT.15 mục 6: QLSX quyết định TRƯỚC khi làm — quyết định sau giờ bắt đầu chỉ cảnh báo (ghi bù từ giấy)."""
    loi, canh = [], []
    a, b = phut(p.get("gio_bat_dau")), phut(p.get("gio_ket_thuc"))
    for f, g in (("gio_bat_dau", a), ("gio_ket_thuc", b)):
        if p.get(f) not in (None, "") and g is None:
            loi.append("Ghi giờ rework dạng giờ:phút (vd 07:30).")
    if a is not None and b is not None and b < a:
        loi.append("Giờ kết thúc rework trước giờ bắt đầu — rework trong cùng ngày sản xuất, kiểm lại giờ.")
    luc = p.get("qlsx_luc")
    if luc and not p.get("qlsx_quyet_dinh"):
        loi.append("Có giờ QLSX quyết định mà chưa chọn QLSX.")
    if luc and get_datetime(luc) > get_datetime(bay_gio):
        loi.append("Giờ QLSX quyết định không được sau bây giờ.")
    if luc and a is not None and p.get("ngay") and getdate(luc) == getdate(p["ngay"]) and phut(get_datetime(luc)) > a:
        canh.append("QLSX quyết định sau giờ bắt đầu rework — QT.15: QLSX quyết định trước khi làm.")
    return {"loi": loi, "canh_bao": canh}


def la_qlsx(user):
    """User có vai quản lý sản xuất (QLSX) hoặc Giám đốc."""
    try:
        return bool(frappe.db.exists("Has Role", {"parent": user, "parenttype": "User", "role": ("in", QLSX_VAI)}))
    except Exception:
        return False


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
