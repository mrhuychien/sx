"""API thẻ "Kiểm kê kho" — màn Nhập kho + Quản lý.

THÀNH PHẨM (D154, Kho TP): ĐẾM theo HSD in trên hộp — mỗi mã một hay nhiều dòng (HSD → số thùng / hộp). Chốt =
ĐẶT LẠI TOÀN KHO theo số đếm (D188): mỗi (mã, HSD) đúng một lô, mã có tồn mà không đếm về 0, lô cũ chuyển sang lô
theo HSD, thừa / thiếu ghi điều chỉnh kho.

BÁN THÀNH PHẨM (D155, Kho BTP / Kho xưởng): hàng rời tính kg — CÂN TỪNG LÔ. Lô đã cân thì số cân thay số sổ của
lô đó, lô chưa cân giữ nguyên. Chốt: thiếu / thừa từng lô ghi điều chỉnh kho.

Mỗi lần LƯU ghi thẳng vào phiếu kiểm kê nháp (SX Kiem Ke) — tải lại trang, đổi máy vẫn còn. CHỐT: thủ kho hoặc
quản lý (D155 — trước chỉ quản lý). Bỏ phiếu đang đếm: quản lý hoặc người lập. Kế hoạch: sx/kiem_ke.py; kiểm +
sinh chứng từ: controller SX Kiem Ke.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate, now_datetime, nowdate

from sx.config.roles import QUAN_LY, THU_KHO, guard_card, is_super, user_roles
from sx.kiem_ke import theo_lo
from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import BTP, TP, cong_ty_kho, ton_kho_khac, ton_lo
from sx.utils import get_settings, items_tp, kho_xuong, nap_cong_bo

CARD = "kiemke"
PT = "SX Kiem Ke"
GAN_DAY = 5
LO_KHAC = 30
MA_LO_HOP_LE = re.compile(r"^[A-Z0-9][A-Z0-9._/-]{0,39}$")   # mã lô chép tay ra thẻ: chữ, số, - . / _
# Nhóm bán thành phẩm (Item.custom_sx_nhom) theo thứ tự trên chuyền — thẻ xếp mã theo thứ tự này.
NHOM_BTP = {"BTP-Dau": "Đỗ ủ / đỗ vỡ", "BTP-Bot": "Bột nền", "BTP-Phu": "Đường hoán", "BTP-Banh": "Bột bánh",
            "BTP-Bot-SP": "Bột đậu"}


def so_vn(x):
    """1234.5 → "1.234,5" — kiểu số người Việt đọc trên giấy."""
    if x is None:
        return ""
    x = flt(x, 3)
    nguyen = int(abs(x))
    le = round(abs(x) - nguyen, 3)
    s = f"{nguyen:,}".replace(",", ".")
    if le > 1e-9:
        s += "," + f"{le:.3f}"[2:].rstrip("0")
    return ("-" if x < 0 else "") + s


def _la_quan_ly(roles=None):
    roles = roles if roles is not None else user_roles()
    return bool(is_super(roles) or QUAN_LY in roles)


def _duoc_chot():
    """Thủ kho chốt luôn (D155): kho do thủ kho giữ — đếm xong chốt ngay, không phải chờ quản lý vào."""
    roles = user_roles()
    return bool(_la_quan_ly(roles) or THU_KHO in roles)


def cac_kho():
    """Các kho kiểm kê được: [{kho, loai, nhan}] — Kho TP đếm theo HSD; Kho BTP, Kho xưởng cân theo lô."""
    s = get_settings()
    ra = []
    if s.get("kho_tp"):
        ra.append({"kho": s.kho_tp, "loai": TP, "nhan": _("Thành phẩm")})
    if s.get("kho_btp"):
        ra.append({"kho": s.kho_btp, "loai": BTP, "nhan": _("Bán thành phẩm")})
    kx = kho_xuong(s)
    if kx and kx != s.get("kho_btp"):
        ra.append({"kho": kx, "loai": BTP, "nhan": _("Kho xưởng")})
    return ra


def _chon_kho(kho=None, loai=None):
    ds = cac_kho()
    if not ds:
        frappe.throw(_("SX Settings chưa cấu hình Kho TP / Kho BTP."))
    if not kho:
        return ds[0]
    k = next((x for x in ds if x["kho"] == kho and (not loai or x["loai"] == loai)), None)
    if not k:
        frappe.throw(_("Không kiểm kê kho {0} ở đây.").format(kho))
    return k


def _h(v):
    return str(getdate(v)) if v else None


def _loai(d):
    return d.get("loai") or TP


def _nhap(kho, loai=TP):
    """Phiếu đang đếm của kho — mỗi kho, mỗi loại một phiếu."""
    for r in frappe.get_all(PT, filters={"docstatus": 0, "kho": kho}, fields=["name", "loai"],
                            order_by="creation desc"):
        if _loai(r) == loai:
            return frappe.get_doc(PT, r.name)
    return None


def _phieu(name):
    """Phiếu kiểm kê ĐANG ĐẾM — chốt / huỷ rồi thì không ghi nữa."""
    if not name or not frappe.db.exists(PT, name):
        frappe.throw(_("Không thấy phiếu kiểm kê {0}.").format(name or ""))
    d = frappe.get_doc(PT, name)
    if d.docstatus != 0:
        frappe.throw(_("Phiếu kiểm kê {0} đã chốt / huỷ — không ghi thêm được.").format(name))
    return d


def _td(p):
    """Thời điểm chốt sổ của phiếu (D195) — None: số sổ sách tính tới hiện tại."""
    return get_datetime(p.get("thoi_diem")) if p and p.get("thoi_diem") else None


@frappe.whitelist()
def dat_thoi_diem(name, thoi_diem=None):
    """Đặt / bỏ THỜI ĐIỂM CHỐT SỔ (D195) — thủ kho / quản lý. Không đụng số đếm: số sổ sách tính lại tới thời điểm
    đó, chốt ghi chứng từ kho lùi về đó. Để trống = lúc bấm chốt."""
    guard_card(CARD)
    if not _duoc_chot():
        frappe.throw(_("Chỉ thủ kho / quản lý đặt thời điểm chốt sổ."), frappe.PermissionError)
    d = _phieu(name)
    if thoi_diem:
        td = get_datetime(thoi_diem).replace(second=0, microsecond=0)
        loi = d.kiem_thoi_diem(td)
        if loi:
            frappe.throw("<br>".join(loi))
        d.thoi_diem = td
        d.ngay = td.date()
    else:
        d.thoi_diem = None
        d.ngay = getdate(d.bat_dau_luc or nowdate())
    return _luu(d)


def _canh_bao(kho, loai=TP):
    """Điều nên biết trước khi đếm / chốt — không chặn."""
    ra = []
    if loai == TP:
        nhap = frappe.get_all("SX Phieu Nhap TP", filters={"docstatus": 0}, pluck="name")
        if nhap:
            ra.append(_("Còn {0} phiếu nhập kho nháp chưa duyệt ({1}): hàng đó chưa vào sổ — đếm vào là thành THỪA. "
                        "Duyệt trước, hoặc để riêng, không đếm.").format(len(nhap), ", ".join(nhap[:3])))
        return ra
    if kho != get_settings().get("kho_btp"):
        return ra                     # kho xưởng: tầng 1 ghi sổ ngay lúc bấm công đoạn
    # Tầng 2 / 3 vào sổ lúc CHỐT NGÀY (D55): chưa chốt thì hàng trong Kho BTP chưa khớp sổ.
    ngay = frappe.get_all("SX Ngay San Xuat", filters={"docstatus": 0, "ngay": ("<=", nowdate())},
                          fields=["name", "ngay", "chot_ghiso", "chot_vaohop"], order_by="ngay")

    def ds(xs):
        return ", ".join(getdate(x.ngay).strftime("%d/%m") for x in xs[:4]) + (" …" if len(xs) > 4 else "")

    gs = [n for n in ngay if not cint(n.chot_ghiso)]
    vh = [n for n in ngay if not cint(n.chot_vaohop)]
    if gs:
        ra.append(_("{0} ngày sản xuất chưa chốt Ghi sổ ({1}): mẻ hôm đó chưa vào sổ — bột bánh / bột đậu chưa nhập, "
                    "bột nền / đường hoán chưa trừ; cân lúc này sẽ lệch. Chốt Ghi sổ trước rồi cân.").format(len(gs), ds(gs)))
    if vh:
        ra.append(_("{0} ngày chưa chốt Vào hộp ({1}): bột đã vào hộp chưa trừ sổ — cân thấy ít hơn sổ là thành THIẾU. "
                    "Chốt Vào hộp trước rồi cân.").format(len(vh), ds(vh)))
    return ra


def _gan_day(kho, loai):
    ds = frappe.get_all(PT, filters={"docstatus": ("in", [1, 2]), "kho": kho},
                        fields=["name", "ngay", "trang_thai", "loai", "so_ma", "tong_so_sach", "tong_dem", "tong_lech",
                                "nguoi_chot", "chot_luc"], order_by="creation desc", limit=GAN_DAY * 4)
    return [dict(x, ngay=str(x.ngay), chot_luc=str(x.chot_luc or "")[:16]) for x in ds if _loai(x) == loai][:GAN_DAY]


@frappe.whitelist()
def tong_quan(kho=None, loai=None):
    """Trạng thái thẻ cho MỘT kho: phiếu đang đếm (nếu có) + từng mã trên sổ, số đã đếm / cân."""
    guard_card(CARD)
    k = _chon_kho(kho, loai)
    p = _nhap(k["kho"], k["loai"])
    ra = (_hang_btp if k["loai"] == BTP else _hang_tp)(k["kho"], p)
    ra.update({
        "kho": k["kho"], "loai": k["loai"], "cac_kho": cac_kho(), "duoc_chot": _duoc_chot(), "hom_nay": nowdate(),
        "bay_gio": now_datetime().strftime("%Y-%m-%dT%H:%M"),
        "phieu": None, "gan_day": _gan_day(k["kho"], k["loai"]), "canh_bao": _canh_bao(k["kho"], k["loai"]),
    })
    if p:
        ra["phieu"] = {"name": p.name, "ngay": str(p.ngay), "nguoi_lap": p.nguoi_lap,
                       "bat_dau_luc": str(p.bat_dau_luc or "")[:16],
                       "thoi_diem": str(p.get("thoi_diem") or "")[:16],
                       "duoc_huy": bool(_la_quan_ly() or p.nguoi_lap == frappe.session.user)}
    return ra


def _hang_tp(kho, p):
    """Thành phẩm: sổ theo HSD + số đã đếm của từng mã; "+ MÃ KHÁC" khi đang đếm."""
    from sx.api.khotp import _doc_json, _han_dung_js, _nap_uom, _uom_cua

    tp = {i.name: i for i in items_tp(["name", "item_name", "stock_uom", "shelf_life_in_days",
                                        "has_batch_no"])}
    lots = ton_lo(kho, list(tp), _td(p))
    dem = {}
    for r in (p.dong if p else []) or []:
        dem.setdefault(r.item, []).append(r)
    hien = [i for i in tp if lots.get(i)] + [i for i in dem if i not in lots]
    # D189 / D191: mã tắt lô — chốt bật lô; tồn ở kho khác xử lý luôn lúc bật (báo trước trên dòng mã), riêng kho của
    # công ty khác thì không bật được.
    kk = ton_kho_khac([i for i in hien if tp.get(i) is not None and not tp[i].get("has_batch_no")], kho)
    cty, ck = get_settings().get("cong_ty"), cong_ty_kho([w for v in kk.values() for w, _q in v])
    _nap_uom(hien + (list(tp) if p else []))
    nap_cong_bo(hien + (list(tp) if p else []))

    def mo_ta(item):
        i = tp.get(item) or frappe._dict(name=item, item_name=item, stock_uom="", has_batch_no=1)
        return {"item": item, "ten": i.item_name or item, "dvt": i.stock_uom or "",
                "uoms": _uom_cua(item, i.stock_uom), **_han_dung_js(item, i.get("shelf_life_in_days"))}

    hang = []
    for item in hien:
        ls = lots.get(item, [])
        theo, chua, thu_hoi, so_sach = {}, 0.0, 0.0, 0.0
        for l in ls:
            if l["thu_hoi"]:
                thu_hoi += l["qty"]
                continue
            so_sach += l["qty"]
            if l["hsd"]:
                theo[l["hsd"]] = theo.get(l["hsd"], 0.0) + l["qty"]
            else:
                chua += l["qty"]
        i = tp.get(item)
        dong = sorted(dem.get(item, []), key=lambda r: _h(r.hsd) or "")
        tong = flt(sum(flt(r.so_dem) for r in dong), 3)
        hang.append({
            **mo_ta(item),
            "so_sach": flt(so_sach, 3), "chua_hsd": flt(chua, 3), "thu_hoi": flt(thu_hoi, 3),
            "theo_hsd": [{"hsd": h, "so": flt(q, 3)} for h, q in sorted(theo.items())],
            # Mã tắt quản lý lô / có tồn không gắn lô: vẫn đếm theo HSD — chốt chuyển sang quản lý lô (D189).
            "khong_lo": bool(i is not None and not i.get("has_batch_no")) or any(not l["batch"] for l in ls),
            "bat_lo": bool(i is not None and not i.get("has_batch_no")),
            "le_khong_lo": flt(sum(l["qty"] for l in ls if not l["batch"]), 3)
            if i is not None and i.get("has_batch_no") else 0.0,
            "kho_khac": [{"kho": w, "so": flt(q, 3), "cty_khac": bool(cty and ck.get(w) and ck[w] != cty)}
                         for w, q in kk.get(item, [])],
            "da_dem": item in dem,
            "dem": [{"hsd": _h(r.hsd), "so": flt(r.so_dem, 3), "chi_tiet": _doc_json(r.chi_tiet),
                     "nguoi": r.nguoi_dem, "luc": str(r.dem_luc or "")[:16]} for r in dong],
            "tong_dem": tong, "lech": flt(tong - so_sach, 3) if item in dem else 0.0,
        })
    # Thứ tự CỐ ĐỊNH theo tên: đếm xong một dòng mã không nhảy chỗ (thẻ lọc "chưa đếm" khi cần).
    hang.sort(key=lambda x: (x["khong_lo"], x["ten"]))
    # "+ MÃ KHÁC": thành phẩm không có trên sổ kho này nhưng đếm thấy.
    return {"hang": hang, "danh_muc": [mo_ta(i) for i in tp if i not in hien] if p else []}


def _items_btp():
    return frappe.get_all("Item", filters={"custom_sx_nhom": ("like", "BTP%"), "disabled": 0},
                          fields=["name", "item_name", "stock_uom", "has_batch_no", "custom_sx_nhom"])


def _mo_ta_btp(i):
    return {"item": i.name, "ten": i.item_name or i.name, "dvt": i.get("stock_uom") or "Kg",
            "nhom": NHOM_BTP.get(i.get("custom_sx_nhom"), i.get("custom_sx_nhom") or ""),
            "khong_lo": not cint(i.get("has_batch_no"))}


def _hang_btp(kho, p):
    """Bán thành phẩm: từng mã → từng lô trên sổ (kg, ngày lô) + số đã cân; lô đã cân mà sổ không có cũng hiện."""
    btp = {i.name: i for i in _items_btp()}
    lots = ton_lo(kho, list(btp), _td(p))
    can = {}
    for r in (p.dong if p else []) or []:
        can.setdefault(r.item, {})[r.batch or None] = r
    hien = [i for i in btp if lots.get(i)] + [i for i in can if i not in lots]
    ngoai = sorted({b for i, d in can.items() for b in d
                    if b and not any(l["batch"] == b for l in lots.get(i, []))})
    ngay_lo = {b.name: str(getdate(b.manufacturing_date or b.creation)) for b in frappe.get_all(
        "Batch", filters={"name": ("in", ngoai)}, fields=["name", "manufacturing_date", "creation"])} if ngoai else {}

    def mot_lo(b, so, ngay, thu_hoi, r):
        return {"batch": b, "so": flt(so, 3), "ngay": ngay, "thu_hoi": bool(thu_hoi),
                "can": flt(r.so_dem, 3) if r else None, "nguoi": r.nguoi_dem if r else None,
                "luc": str(r.dem_luc or "")[:16] if r else None}

    hang = []
    for item in hien:
        i = btp.get(item) or frappe._dict(name=item, item_name=next(
            (r.ten for r in can[item].values() if r.ten), item), has_batch_no=any(can[item]), custom_sx_nhom="")
        co_lo, da = cint(i.get("has_batch_no")), can.get(item, {})
        lo, le, thu_hoi = [], 0.0, 0.0
        for l in sorted(lots.get(item, []), key=lambda l: (l["ngay"] or "", l["batch"] or "")):
            if co_lo and not l["batch"]:
                le += l["qty"]        # tồn không gắn lô của mã quản lý lô: dữ liệu lỗi, không cân được
                continue
            if l["thu_hoi"]:
                thu_hoi += l["qty"]
            lo.append(mot_lo(l["batch"], l["qty"], l["ngay"], l["thu_hoi"], da.get(l["batch"])))
        for b, r in sorted(da.items(), key=lambda x: str(x[0] or "")):
            if not any(x["batch"] == b for x in lo):
                lo.append(mot_lo(b, 0.0, ngay_lo.get(b), False, r))
        xong = [x for x in lo if x["can"] is not None]
        hang.append({
            **_mo_ta_btp(i), "lo": lo, "le": flt(le, 3), "thu_hoi": flt(thu_hoi, 3),
            "so_sach": flt(sum(x["so"] for x in lo if not x["thu_hoi"]) + le, 3),
            "da_dem": bool(da), "tong_dem": flt(sum(x["can"] for x in xong), 3),
            "so_sach_dem": flt(sum(x["so"] for x in xong), 3),
            "lech": flt(sum(x["can"] - x["so"] for x in xong), 3),
            "con_chua": sum(1 for x in lo if x["can"] is None and not x["thu_hoi"]),
        })
    # Thứ tự chuyền (đỗ → bột nền → đường hoán → bột bánh → bột đậu), trong nhóm theo tên — cân xong không nhảy chỗ.
    thu_tu = list(NHOM_BTP.values())
    hang.sort(key=lambda x: (thu_tu.index(x["nhom"]) if x["nhom"] in thu_tu else len(thu_tu), x["ten"]))
    return {"hang": hang, "danh_muc": [_mo_ta_btp(i) for n, i in btp.items() if n not in hien] if p else []}


@frappe.whitelist()
def bat_dau(kho=None, loai=None):
    """Mở phiếu kiểm kê (mỗi kho, mỗi loại một phiếu đang đếm)."""
    guard_card(CARD)
    k = _chon_kho(kho, loai)
    if not _nhap(k["kho"], k["loai"]):
        d = frappe.get_doc({"doctype": PT, "ngay": nowdate(), "kho": k["kho"], "loai": k["loai"],
                            "nguoi_lap": frappe.session.user, "bat_dau_luc": now_datetime(), "trang_thai": "Đang đếm"})
        d.flags.ignore_permissions = True
        d.insert()
    return tong_quan(k["kho"], k["loai"])


def _luu(d):
    d.flags.ignore_permissions = True
    d.save()
    return tong_quan(d.kho, _loai(d))


@frappe.whitelist()
def ghi(name, item, hsd=None, so_dem=0, chi_tiet=None, hsd_cu=None):
    """THÀNH PHẨM: ghi một dòng đếm (mã, HSD). `hsd_cu` = HSD của dòng đang sửa (đổi HSD / đổi số); không có = dòng
    mới. Sửa về 0 là bỏ dòng. Có chi tiết thùng / hộp thì TỔNG tính lại từ chi tiết (như phiếu nhập kho)."""
    guard_card(CARD)
    from sx.api.khotp import _ghi_json
    from sx.sx.doctype.sx_phieu_nhap_tp.sx_phieu_nhap_tp import _tong_tu_uom

    d = _phieu(name)
    if d.la_btp():
        frappe.throw(_("Phiếu {0} là kiểm kê bán thành phẩm — cân theo lô.").format(name))
    tp = {i.name: i.item_name or i.name for i in items_tp(["name", "item_name"])}
    if item not in tp and not any(r.item == item for r in d.dong or []):
        frappe.throw(_("{0} không phải thành phẩm.").format(item))
    ct = _ghi_json(chi_tiet)
    so = _tong_tu_uom(ct, so_dem)
    h, cu = _h(hsd), _h(hsd_cu)
    if so < 0:
        frappe.throw(_("Số đếm không được âm."))
    if so > 0 and not h:
        frappe.throw(_("Chưa có HSD — ghi theo HSD in trên hộp."))
    dong = list(d.dong or [])
    sua = next((r for r in dong if r.item == item and _h(r.hsd) == cu), None) if hsd_cu else None
    if hsd_cu and not sua:
        frappe.throw(_("Dòng HSD {0} của mã này không còn — tải lại thẻ.").format(hsd_cu))
    trung = next((r for r in dong if r.item == item and r.hsd and _h(r.hsd) == h and r is not sua), None)
    if so > 0 and trung:
        frappe.throw(_("Mã này đã có dòng HSD {0} — sửa dòng đó.").format(getdate(h).strftime("%d/%m/%y")))
    if so <= 0:
        if not sua:
            frappe.throw(_("Chưa nhập số."))
        dong.remove(sua)
    else:
        # Có số thì bỏ dấu "không còn hàng" của mã.
        dong = [r for r in dong if not (r.item == item and not r.hsd)]
        moi = {"hsd": h, "so_dem": so, "chi_tiet": ct, "nguoi_dem": frappe.session.user, "dem_luc": now_datetime()}
        if sua:
            for k, v in moi.items():
                setattr(sua, k, v)
        else:
            d.set("dong", dong)
            d.append("dong", {"item": item, "ten": tp.get(item, item), **moi})
            return _luu(d)
    d.set("dong", dong)
    return _luu(d)


def _thu_hoi(b):
    try:
        return cint(frappe.db.get_value("Batch", b, "custom_thu_hoi"))
    except Exception:                 # chưa migrate W26
        return 0


def _ma_btp(d, item):
    """Item (kèm `ten`) của một mã bán thành phẩm, ghi vào phiếu kiểm kê BÁN THÀNH PHẨM — không thì báo."""
    if not d.la_btp():
        frappe.throw(_("Phiếu {0} là kiểm kê thành phẩm — đếm theo HSD in trên hộp.").format(d.name))
    it = frappe.db.get_value("Item", item, ["name", "item_name", "has_batch_no", "custom_sx_nhom"], as_dict=True)
    if not it or not str(it.custom_sx_nhom or "").startswith("BTP"):
        frappe.throw(_("{0} không phải bán thành phẩm.").format(item))
    it.ten = it.item_name or item
    return it


def _so_can(so_dem):
    so = flt(so_dem, 3)
    if so < 0:
        frappe.throw(_("Số cân không được âm."))
    return so


def _ghi_can(d, item, ten, b, so):
    """Số cân của (mã, lô) — có dòng rồi thì ghi đè, giờ cân mới."""
    r = next((x for x in d.dong or [] if x.item == item and (x.batch or None) == b), None)
    moi = {"so_dem": so, "nguoi_dem": frappe.session.user, "dem_luc": now_datetime()}
    if r:
        for k, v in moi.items():
            setattr(r, k, v)
    else:
        d.append("dong", {"item": item, "ten": ten, "batch": b, **moi})


@frappe.whitelist()
def ghi_lo(name, item, batch=None, so_dem=0):
    """BÁN THÀNH PHẨM: ghi số cân (kg) của một lô. 0 = lô đã hết. Cân lại = ghi đè, giờ cân mới."""
    guard_card(CARD)
    d = _phieu(name)
    it = _ma_btp(d, item)
    so = _so_can(so_dem)
    b = batch or None
    if cint(it.has_batch_no):
        if not b:
            frappe.throw(_("{0} quản lý theo lô — chọn lô rồi cân.").format(it.ten))
        if frappe.db.get_value("Batch", b, "item") != item:
            frappe.throw(_("Lô {0} không phải lô của {1}.").format(b, it.ten))
        if _thu_hoi(b):
            frappe.throw(_("Lô {0} đang THU HỒI — để riêng, không cân ở đây.").format(b))
    elif b:
        frappe.throw(_("{0} không quản lý theo lô — cân cả mã, không chọn lô.").format(it.ten))
    _ghi_can(d, item, it.ten, b, so)
    return _luu(d)


@frappe.whitelist()
def ghi_lo_moi(name, item, ma_lo=None, ngay=None, so_dem=0):
    """BÁN THÀNH PHẨM: cân thấy hàng của lô CHƯA CÓ trong hệ thống (D156) — tạo lô (Batch, NSX = ngày làm) và ghi
    số cân trong CÙNG một lần: bỏ ngang trước khi LƯU thì không đẻ lô rác.

    `ma_lo` = mã ghi trên thẻ hàng. Bỏ trống thì app đặt `{prefix}-KK{ddmmyy ngày làm}` (KK = sinh ở kiểm kê):
    không bao giờ trùng mã lô sản xuất (R-…, BBS-…) nên không nhập nhằng với lô thật làm cùng ngày; lô -KK của
    chính mã này mà chưa dùng (phiếu trước bỏ ngang) thì dùng lại — mã đã chép ra thẻ vẫn đúng. Mã gõ vào trùng
    lô đã có của chính mã này thì ghi vào lô đó; trùng lô của mã khác thì báo."""
    from sx.api.mfg import tao_batch
    from sx.utils import lo_chua_dung, prefix_lo

    guard_card(CARD)
    d = _phieu(name)
    it = _ma_btp(d, item)
    if not cint(it.has_batch_no):
        frappe.throw(_("{0} không quản lý theo lô — cân cả mã, không tạo lô.").format(it.ten))
    so = _so_can(so_dem)
    if so <= 0:
        frappe.throw(_("Lô mới phải có số cân."))
    nl = getdate(ngay) if ngay else getdate(nowdate())
    if nl > getdate(nowdate()):
        frappe.throw(_("Ngày làm {0} sau hôm nay.").format(nl.strftime("%d/%m/%y")))
    ma = re.sub(r"\s+", "", str(ma_lo or "")).upper()
    tu_dat = not ma
    if ma:
        if not MA_LO_HOP_LE.match(ma):
            frappe.throw(_("Mã lô {0}: chỉ gồm chữ, số và - . / _ (tối đa 40 ký tự).").format(ma))
        co = frappe.db.get_value("Batch", ma, ["name", "item", "disabled"], as_dict=True)
        if co and co.item != item:
            frappe.throw(_("Mã lô {0} đã là lô của {1} — đặt mã khác.").format(
                co.name, frappe.db.get_value("Item", co.item, "item_name") or co.item))
        if co and _thu_hoi(co.name):
            frappe.throw(_("Lô {0} đang THU HỒI — để riêng, không cân ở đây.").format(co.name))
        if co and cint(co.disabled):
            frappe.throw(_("Lô {0} đang bị khoá (Disabled) trên Desk — mở khoá lô hoặc đặt mã khác.").format(co.name))
        ma = co.name if co else ma
    else:
        dung = {r.batch for r in d.dong or [] if r.batch}
        goc = f"{prefix_lo(item)}-KK{nl.strftime('%d%m%y')}"
        ma, n = goc, 1
        while frappe.db.exists("Batch", ma) and (ma in dung or not lo_chua_dung(ma, item)):
            n += 1
            ma = f"{goc}-{n}"
    tao = not frappe.db.exists("Batch", ma)
    if tao:
        tao_batch(item, ma, nsx=nl)
        frappe.db.set_value("Batch", ma, "description", _(
            "Tạo lúc kiểm kê {0}: cân thấy hàng mà hệ thống chưa có lô.").format(d.name), update_modified=False)
    _ghi_can(d, item, it.ten, ma, so)
    ra = _luu(d)
    ra["lo_moi"] = {"batch": ma, "tao": tao, "tu_dat": tu_dat}
    return ra


@frappe.whitelist()
def bo_lo(name, item, batch=None):
    """BÁN THÀNH PHẨM: bỏ số cân của một lô (cân nhầm lô) — lô về chưa cân, chốt giữ nguyên số sổ của lô."""
    guard_card(CARD)
    d = _phieu(name)
    b = batch or None
    giu = [r for r in d.dong or [] if not (r.item == item and (r.batch or None) == b)]
    if len(giu) == len(d.dong or []):
        frappe.throw(_("Lô {0} chưa cân — tải lại thẻ.").format(b or ""))
    d.set("dong", giu)
    return _luu(d)


@frappe.whitelist()
def lo_khac(name, item, tim=None):
    """"+ LÔ KHÁC": lô của mã (mới nhất trước) không có trên sổ kho này — cân thấy hàng của lô đó."""
    guard_card(CARD)
    d = _phieu(name)
    co = {l["batch"] for l in ton_lo(d.kho, [item], _td(d)).get(item, [])}
    co |= {r.batch for r in d.dong or [] if r.item == item}
    f = {"item": item, "disabled": 0}
    if tim:
        f["name"] = ("like", f"%{tim}%")
    ds = frappe.get_all("Batch", filters=f, fields=["name", "manufacturing_date", "creation"],
                        order_by="creation desc", limit=LO_KHAC + len(co))
    return [{"batch": b.name, "ngay": str(getdate(b.manufacturing_date or b.creation))}
            for b in ds if b.name not in co][:LO_KHAC]


@frappe.whitelist()
def het_hang(name, item):
    """Đã đếm, không còn gì của mã này trong kho → chốt đưa tồn về 0. Thành phẩm: một dòng không HSD số 0; bán
    thành phẩm: mọi lô đang có trên sổ ghi cân 0 (lô thu hồi để riêng)."""
    guard_card(CARD)
    d = _phieu(name)
    ten = frappe.db.get_value("Item", item, "item_name") or item
    moi = {"item": item, "ten": ten, "so_dem": 0, "nguoi_dem": frappe.session.user, "dem_luc": now_datetime()}
    if d.la_btp():
        co_lo = cint(frappe.db.get_value("Item", item, "has_batch_no"))
        ds = [l["batch"] for l in ton_lo(d.kho, [item], _td(d)).get(item, [])
              if not l["thu_hoi"] and (l["batch"] or not co_lo)]
        if not ds:
            frappe.throw(_("{0} không còn lô nào trên sổ kho này.").format(ten))
        d.set("dong", [r for r in d.dong or [] if r.item != item])
        for b in ds:
            d.append("dong", dict(moi, batch=b))
    else:
        d.set("dong", [r for r in d.dong or [] if r.item != item])
        d.append("dong", dict(moi, hsd=None))
    return _luu(d)


@frappe.whitelist()
def dem_lai(name, item):
    """Bỏ mọi dòng đếm / cân của mã — mã trở về "chưa đếm" (vd có chứng từ kho sau lúc đếm)."""
    guard_card(CARD)
    d = _phieu(name)
    d.set("dong", [r for r in d.dong or [] if r.item != item])
    return _luu(d)


def _tom_tat(ke, ten, lo_can=None, chua=(), doi_lo=None):
    ma = []
    for i, k in sorted(ke.items(), key=lambda x: (x[0] in chua, ten.get(x[0], x[0]))):
        ma.append({
            "item": i, "ten": ten.get(i, i), "so_sach": k["so_sach"], "dem": k["dem"], "chua_dem": i in chua,
            "bat_lo": (doi_lo or {}).get(i) == "bat", "le_khong_lo": (doi_lo or {}).get(i) == "le",
            "lech": flt(k["dem"] - k["so_sach"], 6),
            "chuyen": flt(sum(x["so"] for x in k["chuyen"]), 6),
            "lo_cu": len({x["tu"] for x in k["chuyen"]}),
            "lo_moi": len({x["hsd"] for x in k["chuyen"]} | {x["hsd"] for x in k["nhap"]}),
            "thieu": flt(sum(x["so"] for x in k["xuat"]), 6),
            "thua": flt(sum(x["so"] for x in k["nhap"] + k.get("nhap_lo", [])), 6),
            "bu_am": flt(sum(x["so"] for x in k["bu_am"]), 6),
            "thu_hoi": flt(sum(x["so"] for x in k["bo_qua"]), 6),
            "lo_can": (lo_can or {}).get(i),
        })
    return ma


@frappe.whitelist()
def xem_truoc(name):
    """Chốt thì sẽ làm gì (không ghi gì): từng mã sổ → đếm, chuyển lô, thiếu, thừa; lỗi chặn; cảnh báo."""
    guard_card(CARD)
    d = _phieu(name)
    ke, ten_lo, ten = d.lap_ke()
    btp = d.la_btp()
    chua = set() if btp else (getattr(d.flags, "chua_dem", None) or set())
    doi = {} if btp else (getattr(d.flags, "doi_lo", None) or {})
    ma = _tom_tat(ke, ten, {i: len(v) for i, v in d.dem_theo_lo().items()} if btp else None, chua, doi)
    canh = _canh_bao(d.kho, _loai(d))

    def liet_ke(ds):
        ds = sorted(ds)
        return ", ".join(ds[:8]) + (" …" if len(ds) > 8 else "")

    if chua:
        canh.append(_("{0} mã có tồn trên sổ mà CHƯA ĐẾM — chốt sẽ đưa về 0 (xuất thiếu toàn bộ): {1}. Còn hàng thì "
                      "đếm mã đó trước khi chốt.").format(len(chua), liet_ke(ten.get(i, i) for i in chua)))
    if not btp:
        bat = [ten.get(i, i) for i, c in doi.items() if c == "bat"]
        if bat:
            canh.append(_("{0} mã chưa quản lý theo lô — chốt sẽ BẬT quản lý lô: tồn cũ không lô về 0, số đếm vào lô "
                          "theo HSD (giữ giá vốn). Từ sau chốt nhập / bán các mã này phải chọn lô như mã khác: {1}.")
                        .format(len(bat), liet_ke(bat)))
        le = [ten.get(i, i) for i, c in doi.items() if c == "le"]
        if le:
            canh.append(_("{0} mã có tồn KHÔNG gắn lô (dữ liệu cũ) — chốt đưa phần đó về 0, số đếm vào lô theo HSD: "
                          "{1}.").format(len(le), liet_ke(le)))
        # D191: tồn ở kho khác của mã bật lô — chốt xử lý luôn, nói rõ từng kho.
        kk = {i: v for i, v in (getattr(d.flags, "kho_khac", None) or {}).items() if doi.get(i) == "bat"}
        if kk:
            canh.append(_("{0} mã bật lô còn tồn ở kho khác (cờ lô là của mã, áp mọi kho) — chốt xử lý luôn: kho có hàng "
                          "chuyển NGUYÊN SỐ vào lô tồn cũ (chưa rõ HSD) ngay tại kho đó, vẫn bán được; kho đang âm (tồn "
                          "âm không có thật — thường do chuyển ra mà chưa ghi sản xuất / nhập vào kho đó) đưa về 0, ghi "
                          "điều chỉnh kho (báo kế toán): {1}.").format(len(kk), "; ".join(
                f"{ten.get(i, i)} ({', '.join(f'{w} {so_vn(q)} → ' + ('lô tồn cũ' if q > 0 else 'về 0') for w, q in v)})"
                for i, v in sorted(kk.items(), key=lambda x: ten.get(x[0], x[0])))))
        kc = getattr(d.flags, "kho_cty_khac", None) or {}
        giu = [ten.get(i, i) for i in kc if i in ke and ke[i]["dem"] <= 0]
        if giu:
            canh.append(_("{0} mã chưa quản lý theo lô còn tồn ở kho của công ty khác — chốt chỉ đưa tồn ở {1} về 0, mã "
                          "vẫn để không lô: {2}.").format(len(giu), d.kho, liet_ke(giu)))
        # D195: chốt lùi có mã bật lô — hai nhịp (SXKiemKe._bat_lui); nói rõ tồn hiện tại sẽ chia vào lô ra sao.
        td = _td(d)
        lui = d._bat_lui(ke) if td else {}
        if lui:
            co = [(i, x) for i, x in sorted(lui.items(), key=lambda x: ten.get(x[0], x[0])) if x["ct"]]
            canh.append(_("{0} mã bật quản lý lô mà chốt lùi: phần chênh lệch (đếm − sổ) ghi lùi về {1}, mã còn không lô; "
                          "chuyển tồn vào lô theo HSD làm LÚC BẤM CHỐT với tồn hiện tại — số đếm cộng / trừ chứng từ "
                          "không lô sau thời điểm chốt: bán / xuất trừ HSD sớm nhất trước, nhập theo HSD của phiếu nhập "
                          "thành phẩm (không rõ HSD → lô tồn cũ).{2}").format(
                len(lui), td.strftime("%d/%m/%Y %H:%M"), (" " + _("Có chứng từ sau thời điểm chốt: {0}.").format("; ".join(
                    f"{ten.get(i, i)} → " + (", ".join(
                        (f"HSD {getdate(h).strftime('%d/%m/%y')} {so_vn(q)}" if h else f"lô tồn cũ {so_vn(q)}")
                        for h, q in sorted(x["ket"].items(), key=lambda kv: kv[0] or "9999")) or "0")
                    for i, x in co[:8]) + (" …" if len(co) > 8 else ""))) if co else ""))
        xx = d.chua_duyet_xx(ke)
        if xx:
            canh.append(_("{0} lô của hàng làm từ ngày áp dụng BM.08.04 chưa duyệt xuất xưởng: {1}. Chốt vẫn đưa hàng "
                          "vào lô theo HSD nhưng CHƯA BÁN ĐƯỢC tới khi QC kiểm, Trưởng Ban ISO duyệt BM.08.04 (màn "
                          "QC → Xuất xưởng, mục Lô chờ kiểm).").format(
                len(xx), ", ".join(f"{ten.get(i, i)} HSD {getdate(h).strftime('%d/%m/%y')}" for i, h in xx[:6])
                + (" …" if len(xx) > 6 else "")))
    return {
        "name": d.name, "loai": _loai(d), "ma": ma, "loi": d.kiem_truoc_chot(ke), "canh_bao": canh,
        "duoc_chot": _duoc_chot(),
        "tong": {"so_ma": len(ma), "so_sach": flt(sum(x["so_sach"] for x in ma), 6),
                 "dem": flt(sum(x["dem"] for x in ma), 6),
                 "thieu": flt(sum(x["thieu"] for x in ma), 6), "thua": flt(sum(x["thua"] for x in ma), 6),
                 "chuyen": flt(sum(x["chuyen"] for x in ma), 6),
                 "so_lo": sum(x["lo_can"] or 0 for x in ma),
                 "ve_0": len(chua), "bat_lo": sum(1 for c in doi.values() if c == "bat"),
                 "kho_am": [] if btp else [{"ten": ten.get(i, i), "kho": w, "so": flt(q, 3)} for i, v in sorted(
                     (getattr(d.flags, "kho_khac", None) or {}).items()) if doi.get(i) == "bat" for w, q in v if q < 0],
                 "thoi_diem": str(d.get("thoi_diem") or "")[:16],
                 "bat_lui": 0 if btp or not _td(d) else len(d._bat_lui(ke)),
                 "phieu_kho": d.so_phieu_kho(ke, ten_lo)},
    }


@frappe.whitelist()
def chot(name):
    """Chốt kiểm kê — thủ kho / quản lý. Sinh chứng từ kho trong controller (một giao dịch: lỗi là cuộn lại hết)."""
    guard_card(CARD)
    if not _duoc_chot():
        frappe.throw(_("Chỉ thủ kho / quản lý chốt kiểm kê."), frappe.PermissionError)
    d = _phieu(name)
    d.flags.ignore_permissions = True
    d.submit()
    return {"name": d.name, "so_ma": d.so_ma, "tong_so_sach": d.tong_so_sach, "tong_dem": d.tong_dem,
            "tong_lech": d.tong_lech,
            "so_phieu_kho": sum(1 for x in json.loads(d.ds_se or "[]") if x.get("dt") != "Item")}


@frappe.whitelist()
def huy(name):
    """Bỏ phiếu đang đếm (chưa chốt thì chưa có gì vào kho). Quản lý hoặc người lập — bỏ phiếu là mất số người
    khác đã đếm, nên thủ kho chốt được nhưng không bỏ được phiếu người khác lập."""
    guard_card(CARD)
    d = _phieu(name)
    if not (_la_quan_ly() or d.nguoi_lap == frappe.session.user):
        frappe.throw(_("Chỉ quản lý hoặc người lập phiếu bỏ được phiếu kiểm kê."), frappe.PermissionError)
    kho, loai = d.kho, _loai(d)
    frappe.delete_doc(PT, d.name, ignore_permissions=True)
    return tong_quan(kho, loai)


@frappe.whitelist()
def huy_chot(name, ly_do=None):
    """HUỶ CHỐT, MỞ LẠI ĐẾM TIẾP (D196) — phiếu chốt nhầm / chốt khi chưa đếm xong: huỷ phiếu (đảo mọi chứng từ kho của
    lần chốt theo thứ tự ngược, trả cờ quản lý lô đã đổi — SXKiemKe.on_cancel; sau chốt mã vừa bật lô đã có chứng từ theo
    lô thì không huỷ được) rồi mở lại phiếu đang đếm với ĐÚNG các dòng đã đếm (số, người đếm, lúc đếm), lúc bắt đầu và
    thời điểm chốt sổ — đếm tiếp rồi chốt lại. Thủ kho / quản lý (người chốt được); bắt buộc lý do. Chỉ phiếu đã chốt mới
    nhất của kho (lần chốt sau tính trên số của lần trước); kho đang có phiếu đang đếm thì không mở thêm phiếu thứ hai."""
    guard_card(CARD)
    if not _duoc_chot():
        frappe.throw(_("Chỉ thủ kho / quản lý huỷ được phiếu kiểm kê đã chốt."), frappe.PermissionError)
    ly_do = str(ly_do or "").strip()
    if not ly_do:
        frappe.throw(_("Ghi lý do huỷ chốt."))
    if not name or not frappe.db.exists(PT, name):
        frappe.throw(_("Không thấy phiếu kiểm kê {0}.").format(name or ""))
    d = frappe.get_doc(PT, name)
    if d.docstatus != 1:
        frappe.throw(_("Phiếu kiểm kê {0} không ở trạng thái đã chốt.").format(name))
    loai = _loai(d)
    dang = _nhap(d.kho, loai)
    if dang:
        frappe.throw(_("{0} đang có phiếu kiểm kê {1} đang đếm — chốt hoặc bỏ phiếu đó trước, rồi mới huỷ chốt {2}.")
                     .format(d.kho, dang.name, name))
    sau = [x.name for x in frappe.get_all(PT, filters={"docstatus": 1, "kho": d.kho, "creation": (">", d.creation)},
                                          fields=["name", "loai"]) if _loai(x) == loai]
    if sau:
        frappe.throw(_("Sau phiếu {0} đã chốt phiếu {1} — lần chốt sau tính trên số của lần trước; huỷ phiếu đó trước.")
                     .format(name, ", ".join(sau)))
    dong = [{f: r.get(f) for f in ("item", "ten", "dvt", "batch", "hsd", "so_dem", "chi_tiet", "nguoi_dem", "dem_luc")}
            for r in d.dong or []]
    d.db_set("ghi_chu", ((d.ghi_chu or "") + "\n" + _("[Huỷ chốt {0} — {1}] {2}").format(
        now_datetime().strftime("%d/%m/%Y %H:%M"), frappe.session.user, ly_do)).strip(), update_modified=False)
    d.flags.ignore_permissions = True
    d.cancel()
    moi = frappe.get_doc({"doctype": PT, "ngay": d.ngay, "kho": d.kho, "loai": loai,
                          "nguoi_lap": d.nguoi_lap or frappe.session.user, "bat_dau_luc": d.bat_dau_luc,
                          "thoi_diem": d.get("thoi_diem"), "trang_thai": "Đang đếm", "dong": dong,
                          "ghi_chu": _("Mở lại từ phiếu đã huỷ chốt {0}: {1}").format(d.name, ly_do)})
    moi.flags.ignore_permissions = True
    moi.insert()
    ra = tong_quan(d.kho, loai)
    ra["huy_chot"] = {"cu": d.name, "moi": moi.name}
    return ra


def _ten_ma(d):
    ten = {r.item: r.ten for r in d.dong or []}
    thieu = [i for i, t in ten.items() if not t]
    if thieu:                         # dòng sửa tay trên Desk có thể chưa có tên
        ten.update({i.name: i.item_name for i in frappe.get_all(
            "Item", filters={"name": ("in", thieu)}, fields=["name", "item_name"])})
    return {i: t or i for i, t in ten.items()}


@frappe.whitelist()
def bien_ban(name):
    """HTML biên bản kiểm kê để in: từng mã sổ → đếm (cân) → lệch, kết quả từng lô, chỗ ký."""
    guard_card(CARD)
    if not name or not frappe.db.exists(PT, name):
        frappe.throw(_("Không thấy phiếu kiểm kê {0}.").format(name or ""))
    d = frappe.get_doc(PT, name)
    ten = _ten_ma(d)
    btp = d.la_btp()
    ma = _bien_ban_btp(d, ten) if btp else _bien_ban_tp(d, ten)
    tong = {"dem": flt(sum(m["tong_dem"] for m in ma), 3),
            "so_sach": flt(sum(m["so_sach"] or 0 for m in ma), 3) if d.docstatus != 2 else None,
            "so_lo": sum(len(m["dem"]) for m in ma)}
    tong["lech"] = flt(tong["dem"] - tong["so_sach"], 3) if tong["so_sach"] is not None else None
    ds = json.loads(d.ds_se or "[]")
    se = [x.get("name") for x in ds if x.get("dt") != "Item"]
    # D189: mã bật quản lý lô — nháp: sẽ bật khi chốt; đã chốt: mã có lần đổi cờ ĐẦU TIÊN là từ tắt lô; đã huỷ: cờ
    # đã trả lại, không ghi.
    bat = []
    if d.docstatus == 0:
        bat = [i for i, c in (getattr(d.flags, "doi_lo", None) or {}).items() if c == "bat"]
    elif d.docstatus == 1:
        dau = {}
        for x in ds:
            if x.get("dt") == "Item":
                dau.setdefault(x.get("name"), cint((x.get("has_batch_no") or [1])[0]))
        bat = [i for i, cu in dau.items() if not cu]
    ten_ma = {m["item"]: m["ten"] for m in ma}
    bat_lo = sorted(ten_ma.get(i) or i for i in bat)
    # D191: tồn ở kho khác của mã bật lô — nháp: sẽ làm; đã chốt: đã làm (ghi trong ds_se).
    kho_khac = []
    if d.docstatus == 0:
        for i, v in (getattr(d.flags, "kho_khac", None) or {}).items():
            if i in bat:
                kho_khac += [{"ten": ten_ma.get(i) or i, "kho": w, "so": q, "lo": None} for w, q in v]
    elif d.docstatus == 1:
        for x in ds:
            if x.get("dt") == "Item" and x.get("kho_khac"):
                kho_khac += [{"ten": ten_ma.get(x["name"]) or x["name"], "kho": w, "so": q, "lo": x.get("lo_cu")}
                             for w, q in x["kho_khac"]]
    kho_khac.sort(key=lambda k: (k["ten"], k["kho"]))
    return frappe.render_template("sx/sx/doctype/sx_kiem_ke/bien_ban.html", {
        "d": d, "ma": ma, "tong": tong, "se": se, "bat_lo": bat_lo, "kho_khac": kho_khac,
        "cong_ty": get_settings().get("cong_ty") or "",
        "nhap": d.docstatus == 0, "huy": d.docstatus == 2, "btp": btp,
        "vn": lambda x: getdate(x).strftime("%d/%m/%Y") if x else "", "so": so_vn,
    })


def _bien_ban_tp(d, ten):
    dem, so_sach = {}, {}
    for r in d.dong or []:
        dem.setdefault(r.item, []).append({"hsd": r.hsd, "so": flt(r.so_dem, 3)})
    ten = dict(ten)
    if d.docstatus == 0:
        # Bản nháp: số sổ sách tính tới lúc in — để soát trước khi chốt. D188: kế hoạch có cả mã chưa đếm (về 0).
        ke, _ten_lo, ten_ke = d.lap_ke()
        so_sach = {i: k["so_sach"] for i, k in ke.items()}
        for i in ke:
            ten.setdefault(i, ten_ke.get(i, i))
    else:
        # Đã chốt: sổ trước = tồn các lô lúc chốt, trừ lô đang thu hồi (để riêng, không kiểm). Mã chưa đếm đã về 0
        # (D188) chỉ có trong bảng lô — đưa vào danh sách mã.
        from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import VIEC

        bo = VIEC["thu_hoi"].split(" —")[0]
        for r in d.lo or []:
            if bo not in (r.viec or ""):
                so_sach[r.item] = so_sach.get(r.item, 0.0) + flt(r.so_truoc)
            ten.setdefault(r.item, r.ten or r.item)
    ma = []
    for i in sorted(ten, key=lambda x: (x not in dem, ten[x])):
        dm = flt(sum(x["so"] for x in dem.get(i, [])), 3)
        ss = flt(so_sach.get(i, 0.0), 3) if d.docstatus != 2 else None
        ma.append({"item": i, "ten": ten[i], "dem": sorted((x for x in dem.get(i, []) if x["hsd"]),
                                                            key=lambda x: str(x["hsd"])),
                   "tong_dem": dm, "so_sach": ss, "lech": flt(dm - ss, 3) if ss is not None else None,
                   "chua_dem": i not in dem})
    return ma


def _bien_ban_btp(d, ten):
    """Bán thành phẩm: từng lô đã cân — cân thật / sổ sách / lệch. Sổ của lô: bản nháp tính tới lúc in, đã chốt
    lấy bảng kết quả lô lúc chốt."""
    so_lo = {}
    if d.docstatus == 0:
        ke, _ten_lo, _t = d.lap_ke()
        for i, k in ke.items():
            for b, g in theo_lo(k, lambda h: None).items():
                so_lo[(i, b)] = g["truoc"]
    else:
        for r in d.lo or []:
            so_lo[(r.item, r.batch or None)] = flt(r.so_truoc)
    lo = {}
    for r in d.dong or []:
        b, c = r.batch or None, flt(r.so_dem, 3)
        ss = flt(so_lo.get((r.item, b), 0.0), 3) if d.docstatus != 2 else None
        lo.setdefault(r.item, []).append({"batch": b, "so": c, "so_sach": ss,
                                          "lech": flt(c - ss, 3) if ss is not None else None})
    ma = []
    for i in sorted(ten, key=lambda x: ten[x]):
        ds = sorted(lo.get(i, []), key=lambda x: str(x["batch"] or ""))
        dm = flt(sum(x["so"] for x in ds), 3)
        ss = flt(sum(x["so_sach"] for x in ds), 3) if d.docstatus != 2 else None
        ma.append({"item": i, "ten": ten[i], "dem": ds, "tong_dem": dm, "so_sach": ss,
                   "lech": flt(dm - ss, 3) if ss is not None else None})
    return ma
