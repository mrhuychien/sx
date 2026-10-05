"""Lịch tháng cho ba tab nhập liệu: Ghi hộp, Ghi sổ, Nhập kho (D108).

Mỗi tab một ô lịch: ô ngày chỉ hiện MỘT con số (số hộp / số mẻ / số nhập kho),
bấm vào thì xem chi tiết ngày đó. Không phải báo cáo — là chỗ để nhìn ra NGAY
"hôm nào chưa ghi", "hôm nào số lạ", rồi bấm vào xem.

Chi tiết trả về cùng một khuôn cho cả ba loại ({chips, khoi: [{ten, dong}]}), nên
màn hình chỉ có MỘT cách vẽ — thêm loại thứ tư là thêm một hàm ở đây.

Chỉ đọc. Quyền: mỗi loại một card (roles.CARD_ROLES), ai vào được tab nào thì
xem được lịch của tab đó.
"""

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from sx.config.roles import guard_card, is_super, user_roles

CARD = {"vaohop": "lichvaohop", "ghiso": "lichghiso", "nhapkho": "lichnhapkho"}
DON_VI = {"vaohop": "hộp", "ghiso": "mẻ", "nhapkho": "sp"}


def _kiem(loai):
    if loai not in CARD:
        frappe.throw(_("Loại lịch không hợp lệ: {0}").format(loai))
    guard_card(CARD[loai])


def _khoang(nam, thang):
    nam, thang = cint(nam), cint(thang)
    if not (1 <= thang <= 12 and 2000 <= nam <= 2100):
        frappe.throw(_("Tháng không hợp lệ."))
    return date(nam, thang, 1), date(nam, thang, calendar.monthrange(nam, thang)[1])


def _ten_hang(ma):
    ma = [m for m in set(ma) if m]
    if not ma:
        return {}
    return {i.name: i.item_name or i.name for i in frappe.get_all(
        "Item", filters={"name": ("in", ma)}, fields=["name", "item_name"])}


def _ngay_sx(tu, den):
    """{name: row} phiếu ngày còn hiệu lực trong khoảng (bỏ phiếu đã huỷ)."""
    return {r.name: r for r in frappe.get_all(
        "SX Ngay San Xuat", filters={"ngay": ("between", (tu, den)), "docstatus": ("<", 2)},
        fields=["name", "ngay", "chot_ghiso", "chot_vaohop", "docstatus"])}


def _dong_vao_hop(ten_ngay):
    bang = {b.name: b.ngay_sx for b in frappe.get_all(
        "SX Bang Vao Hop", filters={"ngay_sx": ("in", list(ten_ngay)), "docstatus": ("<", 2)},
        fields=["name", "ngay_sx"])} if ten_ngay else {}
    if not bang:
        return [], bang
    return frappe.get_all(
        "SX Bang Vao Hop Item",
        filters={"parent": ("in", list(bang)), "parenttype": "SX Bang Vao Hop"},
        fields=["parent", "nhan_vien", "ten_nhan_vien", "san_pham", "cach_lam", "so_hop",
                "cong_nhat", "nguoi_ghi"]), bang


def _dong_cua_toi(dong):
    """D113: QC chỉ thấy dòng mình ghi — lịch cũng vậy. Quản lý thấy hết."""
    if is_super(user_roles()):
        return dong
    u = frappe.session.user
    return [r for r in dong if r.get("nguoi_ghi") == u]


def _phieu_nhap(tu, den):
    return {p.name: p for p in frappe.get_all(
        "SX Phieu Nhap TP", filters={"ngay": ("between", (tu, den)), "docstatus": 1},
        fields=["name", "ngay", "tong_dem", "nguoi_duyet", "duyet_luc"])}


# ═══════════════════════════════════════════════════════════════ tháng ══

@frappe.whitelist()
def thang(loai, nam, thang):
    """{ngay: {"YYYY-MM-DD": {so, phu, chot}}, tong, don_vi} — một số mỗi ngày."""
    _kiem(loai)
    tu, den = _khoang(nam, thang)
    o = {}

    def cong(ngay, so, phu=None, chot=None):
        k = str(getdate(ngay))
        x = o.setdefault(k, {"so": 0, "phu": 0, "chot": 0})
        x["so"] += flt(so)
        if phu:
            x["phu"] += flt(phu)
        if chot:
            x["chot"] = 1

    if loai == "nhapkho":
        for p in _phieu_nhap(tu, den).values():
            cong(p.ngay, p.tong_dem, phu=1)            # phu = số phiếu
    else:
        ngay = _ngay_sx(tu, den)
        if loai == "vaohop":
            dong, bang = _dong_vao_hop(ngay)
            for r in _dong_cua_toi(dong):
                n = ngay[bang[r.parent]]
                cong(n.ngay, r.so_hop, phu=r.so_hop if cint(r.cong_nhat) else 0)
            for n in ngay.values():                    # ngày đã chốt mà 0 hộp vẫn tô
                if cint(n.chot_vaohop):
                    cong(n.ngay, 0, chot=1)
        else:
            if ngay:
                for r in frappe.get_all(
                        "SX Bao Me", filters={"parent": ("in", list(ngay)),
                                              "parenttype": "SX Ngay San Xuat"},
                        fields=["parent", "so_me", "tong_kg"]):
                    cong(ngay[r.parent].ngay, r.so_me, phu=r.tong_kg)   # phu = kg
            for n in ngay.values():
                if cint(n.chot_ghiso):
                    cong(n.ngay, 0, chot=1)

    # Ngày không có gì thì không gửi: ô trống trên lịch NÓI "chưa ghi", đừng ghi 0.
    o = {k: v for k, v in o.items() if v["so"] or v["chot"]}
    return {"nam": tu.year, "thang": tu.month, "ngay": o,
            "tong": sum(v["so"] for v in o.values()), "don_vi": DON_VI[loai]}


# ═════════════════════════════════════════════════════════════ chi tiết ══

def _kg(x):
    """513.0 → '513', 171.5 → '171.5' — số kg đọc trên điện thoại, không cần '.0'."""
    return f"{flt(x, 1):g}"


def _khoi(ten, dong):
    return {"ten": ten, "dong": dong} if dong else None


@frappe.whitelist()
def chi_tiet(loai, ngay):
    """Chi tiết một ngày, khuôn chung: {ngay, so, don_vi, chips[], khoi[{ten, dong[]}]}.

    dong = {trai, phai, phu?} — trái là tên, phải là con số, phụ là dòng nhỏ dưới tên.
    """
    _kiem(loai)
    d = getdate(ngay)
    ra = {"ngay": str(d), "don_vi": DON_VI[loai], "chips": [], "khoi": [], "so": 0}
    {"vaohop": _ct_vao_hop, "ghiso": _ct_ghi_so, "nhapkho": _ct_nhap_kho}[loai](d, ra)
    ra["khoi"] = [k for k in ra["khoi"] if k]
    return ra


def _ct_vao_hop(d, ra):
    ngay = _ngay_sx(d, d)
    dong, _b = _dong_vao_hop(ngay)
    dong = _dong_cua_toi(dong)
    if any(cint(n.chot_vaohop) for n in ngay.values()):
        ra["chips"].append(_("đã chốt Vào hộp"))
    elif ngay:
        ra["chips"].append(_("chưa chốt"))
    ten = _ten_hang(r.san_pham for r in dong)
    theo_ma, theo_nguoi, cn = {}, {}, 0
    for r in dong:
        sl = cint(r.so_hop)
        g = theo_ma.setdefault(r.san_pham, {"khoan": 0, "cn": 0})
        if cint(r.cong_nhat):
            g["cn"] += sl
            cn += sl
            continue
        g["khoan"] += sl
        p = theo_nguoi.setdefault(r.nhan_vien, {"ten": r.ten_nhan_vien or r.nhan_vien,
                                                "sl": 0, "ma": []})
        p["sl"] += sl
        p["ma"].append(f"{ten.get(r.san_pham, r.san_pham)}{' · ' + r.cach_lam if r.cach_lam else ''}"
                       f" {sl}")
    ra["so"] = sum(cint(r.so_hop) for r in dong)
    if cn:
        ra["chips"].append(_("công nhật {0} hộp").format(cn))
    if theo_nguoi:
        ra["chips"].append(_("{0} người").format(len(theo_nguoi)))
    ra["khoi"].append(_khoi(_("Theo mã hàng"), [
        {"trai": ten.get(ma, ma), "phai": g["khoan"] + g["cn"],
         "phu": _("khoán {0} · công nhật {1}").format(g["khoan"], g["cn"]) if g["cn"] else None}
        for ma, g in sorted(theo_ma.items(), key=lambda x: -(x[1]["khoan"] + x[1]["cn"]))]))
    ra["khoi"].append(_khoi(_("Theo người"), [
        {"trai": p["ten"], "phai": p["sl"], "phu": ", ".join(p["ma"])}
        for p in sorted(theo_nguoi.values(), key=lambda x: x["ten"])]))


def _ct_ghi_so(d, ra):
    ngay = _ngay_sx(d, d)
    if any(cint(n.chot_ghiso) for n in ngay.values()):
        ra["chips"].append(_("đã chốt Ghi sổ"))
    elif ngay:
        ra["chips"].append(_("chưa chốt"))
    me, can = [], []
    if ngay:
        loc = {"parent": ("in", list(ngay)), "parenttype": "SX Ngay San Xuat"}
        me = frappe.get_all("SX Bao Me", filters=loc, fields=["item_btp", "so_me", "tong_kg"])
        can = frappe.get_all("SX Bao Can", filters=loc, fields=["item_bot_banh", "so_me"])
    rang = frappe.get_all("SX Xuat Dau", filters={"ngay_rang": d, "docstatus": ("<", 2)},
                          fields=["loai_dau", "dau_kg", "lo_rang"])
    ten = _ten_hang([r.item_btp for r in me] + [r.item_bot_banh for r in can]
                    + [r.loai_dau for r in rang])

    def gop(ds, ma, so, kg=None):
        g = {}
        for r in ds:
            x = g.setdefault(r.get(ma), [0.0, 0.0])
            x[0] += flt(r.get(so))
            x[1] += flt(r.get(kg)) if kg else 0
        return g

    gme = gop(me, "item_btp", "so_me", "tong_kg")
    ra["so"] = sum(v[0] for v in gme.values())
    tong_kg = sum(v[1] for v in gme.values())
    if tong_kg:
        ra["chips"].append(_("{0} kg").format(_kg(tong_kg)))
    ra["khoi"].append(_khoi(_("Báo mẻ trộn"), [
        {"trai": ten.get(k, k), "phai": flt(v[0], 1), "phu": _("{0} kg").format(_kg(v[1]))}
        for k, v in sorted(gme.items(), key=lambda x: -x[1][0])]))
    ra["khoi"].append(_khoi(_("Báo cán"), [
        {"trai": ten.get(k, k), "phai": flt(v[0], 1)}
        for k, v in sorted(gop(can, "item_bot_banh", "so_me").items(), key=lambda x: -x[1][0])]))
    ra["khoi"].append(_khoi(_("Rang đỗ"), [
        {"trai": ten.get(r.loai_dau, r.loai_dau), "phai": f"{_kg(r.dau_kg)} kg",
         "phu": _("lô {0}").format(r.lo_rang) if r.lo_rang else None} for r in rang]))
    so_su_co = frappe.db.count("SX Su Co", {"ngay_san_xuat": ("in", list(ngay))}) if ngay else 0
    if so_su_co:
        ra["chips"].append(_("{0} sự cố").format(so_su_co))


def _ct_nhap_kho(d, ra):
    phieu = _phieu_nhap(d, d)
    dong = frappe.get_all(
        "SX Phieu Nhap TP Item",
        filters={"parent": ("in", list(phieu)), "parenttype": "SX Phieu Nhap TP"},
        fields=["parent", "item", "ten", "so_dem", "dvt"]) if phieu else []
    theo_ma = {}
    for r in dong:
        g = theo_ma.setdefault(r.item, {"ten": r.ten or r.item, "sl": 0.0, "dvt": r.dvt or ""})
        g["sl"] += flt(r.so_dem)
    ra["so"] = sum(g["sl"] for g in theo_ma.values())
    if phieu:
        ra["chips"].append(_("{0} phiếu đã duyệt").format(len(phieu)))
    ra["khoi"].append(_khoi(_("Theo mã hàng"), [
        {"trai": g["ten"], "phai": f"{flt(g['sl'], 0):g} {g['dvt']}".strip()}
        for g in sorted(theo_ma.values(), key=lambda x: -x["sl"])]))
    ra["khoi"].append(_khoi(_("Phiếu"), [
        {"trai": p.name, "phai": flt(p.tong_dem, 0),
         "phu": _("duyệt bởi {0}").format(p.nguoi_duyet) if p.nguoi_duyet else None}
        for p in sorted(phieu.values(), key=lambda x: str(x.duyet_luc or ""))]))
