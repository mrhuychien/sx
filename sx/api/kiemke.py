"""API thẻ "Kiểm kê kho thành phẩm" (D154) — màn Nhập kho + Quản lý.

Thủ kho / quản lý ĐẾM: mỗi mã một hay nhiều dòng (HSD in trên hộp → số), ghi thẳng vào phiếu kiểm kê nháp
(SX Kiem Ke) — tải lại trang, đổi máy vẫn còn. CHỐT chỉ quản lý (người đếm khác người chốt, như chốt ngày
D33): số đếm thay tồn của các mã đã đếm, lô cũ chưa có HSD chuyển sang lô theo HSD, thừa / thiếu ghi điều
chỉnh kho. Kế hoạch: sx/kiem_ke.py; kiểm + sinh chứng từ: controller SX Kiem Ke.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, nowdate

from sx.config.roles import QUAN_LY, guard_card, is_super, user_roles
from sx.kiem_ke import chia_chung_tu, so_chung_tu
from sx.utils import get_settings, items_tp, nap_cong_bo

CARD = "kiemke"
PT = "SX Kiem Ke"
GAN_DAY = 5


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


def _duoc_chot():
    roles = user_roles()
    return bool(is_super(roles) or QUAN_LY in roles)


def _kho():
    k = get_settings().get("kho_tp")
    if not k:
        frappe.throw(_("SX Settings chưa cấu hình Kho TP."))
    return k


def _h(v):
    return str(getdate(v)) if v else None


def _nhap(kho):
    ten = frappe.db.get_value(PT, {"docstatus": 0, "kho": kho}, "name", order_by="creation desc")
    return frappe.get_doc(PT, ten) if ten else None


def _phieu(name):
    """Phiếu kiểm kê ĐANG ĐẾM — chốt / huỷ rồi thì không ghi nữa."""
    if not name or not frappe.db.exists(PT, name):
        frappe.throw(_("Không thấy phiếu kiểm kê {0}.").format(name or ""))
    d = frappe.get_doc(PT, name)
    if d.docstatus != 0:
        frappe.throw(_("Phiếu kiểm kê {0} đã chốt / huỷ — không ghi thêm được.").format(name))
    return d


def _canh_bao():
    """Điều nên biết trước khi đếm / chốt — không chặn."""
    ra = []
    nhap = frappe.get_all("SX Phieu Nhap TP", filters={"docstatus": 0}, pluck="name")
    if nhap:
        ra.append(_("Còn {0} phiếu nhập kho nháp chưa duyệt ({1}): hàng đó chưa vào sổ — đếm vào là thành THỪA. "
                    "Duyệt trước, hoặc để riêng, không đếm.").format(len(nhap), ", ".join(nhap[:3])))
    return ra


@frappe.whitelist()
def tong_quan():
    """Trạng thái thẻ: phiếu đang đếm (nếu có) + từng mã: sổ theo HSD, số đã đếm."""
    guard_card(CARD)
    from sx.api.khotp import _doc_json, _han_dung_js, _nap_uom, _uom_cua
    from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import ton_lo

    kho = _kho()
    p = _nhap(kho)
    tp = {i.name: i for i in items_tp(["name", "item_name", "stock_uom", "shelf_life_in_days",
                                        "has_batch_no"])}
    lots = ton_lo(kho, list(tp))
    dem = {}
    for r in (p.dong if p else []) or []:
        dem.setdefault(r.item, []).append(r)
    hien = [i for i in tp if lots.get(i)] + [i for i in dem if i not in lots]
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
        hang.append({
            **mo_ta(item),
            "so_sach": flt(so_sach, 3), "chua_hsd": flt(chua, 3), "thu_hoi": flt(thu_hoi, 3),
            "theo_hsd": [{"hsd": h, "so": flt(q, 3)} for h, q in sorted(theo.items())],
            # Mã tắt quản lý lô thì không mang HSD được (bán / nhập không lô).
            "khong_lo": bool(i is not None and not i.get("has_batch_no")) or any(not l["batch"] for l in ls),
            "da_dem": item in dem,
            "dem": [{"hsd": _h(r.hsd), "so": flt(r.so_dem, 3), "chi_tiet": _doc_json(r.chi_tiet),
                     "nguoi": r.nguoi_dem, "luc": str(r.dem_luc or "")[:16]} for r in dong],
            "tong_dem": flt(sum(flt(r.so_dem) for r in dong), 3),
        })
    # Thứ tự CỐ ĐỊNH theo tên: đếm xong một dòng mã không nhảy chỗ (thẻ lọc "chưa đếm" khi cần).
    hang.sort(key=lambda x: (x["khong_lo"], x["ten"]))
    ra = {
        "kho": kho, "duoc_chot": _duoc_chot(), "hom_nay": nowdate(), "hang": hang,
        "phieu": None, "danh_muc": [],
        "gan_day": [dict(x, ngay=str(x.ngay)) for x in frappe.get_all(
            PT, filters={"docstatus": ("in", [1, 2]), "kho": kho},
            fields=["name", "ngay", "trang_thai", "so_ma", "tong_so_sach", "tong_dem", "tong_lech", "nguoi_chot"],
            order_by="creation desc", limit=GAN_DAY)],
        "canh_bao": _canh_bao(),
    }
    if p:
        ra["phieu"] = {"name": p.name, "ngay": str(p.ngay), "nguoi_lap": p.nguoi_lap,
                       "bat_dau_luc": str(p.bat_dau_luc or "")[:16],
                       "duoc_huy": bool(_duoc_chot() or p.nguoi_lap == frappe.session.user)}
        # "+ MÃ KHÁC": thành phẩm không có trên sổ kho này nhưng đếm thấy.
        ra["danh_muc"] = [mo_ta(i) for i in tp if i not in hien]
    return ra


@frappe.whitelist()
def bat_dau():
    """Mở phiếu kiểm kê (mỗi kho một phiếu đang đếm)."""
    guard_card(CARD)
    kho = _kho()
    if not _nhap(kho):
        d = frappe.get_doc({"doctype": PT, "ngay": nowdate(), "kho": kho, "nguoi_lap": frappe.session.user,
                            "bat_dau_luc": now_datetime(), "trang_thai": "Đang đếm"})
        d.flags.ignore_permissions = True
        d.insert()
    return tong_quan()


def _luu(d):
    d.flags.ignore_permissions = True
    d.save()
    return tong_quan()


@frappe.whitelist()
def ghi(name, item, hsd=None, so_dem=0, chi_tiet=None, hsd_cu=None):
    """Ghi một dòng đếm (mã, HSD). `hsd_cu` = HSD của dòng đang sửa (đổi HSD / đổi số); không có = dòng mới.
    Sửa về 0 là bỏ dòng. Có chi tiết thùng / hộp thì TỔNG tính lại từ chi tiết (như phiếu nhập kho)."""
    guard_card(CARD)
    from sx.api.khotp import _ghi_json
    from sx.sx.doctype.sx_phieu_nhap_tp.sx_phieu_nhap_tp import _tong_tu_uom

    d = _phieu(name)
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


@frappe.whitelist()
def het_hang(name, item):
    """Đã đếm, không còn hộp nào của mã này trong kho → chốt sẽ đưa tồn của mã về 0."""
    guard_card(CARD)
    d = _phieu(name)
    tp = {i.name: i.item_name or i.name for i in items_tp(["name", "item_name"])}
    d.set("dong", [r for r in d.dong or [] if r.item != item])
    d.append("dong", {"item": item, "ten": tp.get(item, item), "hsd": None, "so_dem": 0,
                      "nguoi_dem": frappe.session.user, "dem_luc": now_datetime()})
    return _luu(d)


@frappe.whitelist()
def dem_lai(name, item):
    """Bỏ mọi dòng đếm của mã — mã trở về "chưa đếm" (vd có chứng từ kho sau lúc đếm)."""
    guard_card(CARD)
    d = _phieu(name)
    d.set("dong", [r for r in d.dong or [] if r.item != item])
    return _luu(d)


def _tom_tat(ke, ten):
    ma = []
    for i, k in sorted(ke.items(), key=lambda x: ten.get(x[0], x[0])):
        ma.append({
            "item": i, "ten": ten.get(i, i), "so_sach": k["so_sach"], "dem": k["dem"],
            "lech": flt(k["dem"] - k["so_sach"], 6),
            "chuyen": flt(sum(x["so"] for x in k["chuyen"]), 6),
            "lo_cu": len({x["tu"] for x in k["chuyen"]}),
            "lo_moi": len({x["hsd"] for x in k["chuyen"]} | {x["hsd"] for x in k["nhap"]}),
            "thieu": flt(sum(x["so"] for x in k["xuat"]), 6),
            "thua": flt(sum(x["so"] for x in k["nhap"]), 6),
            "bu_am": flt(sum(x["so"] for x in k["bu_am"]), 6),
            "thu_hoi": flt(sum(x["so"] for x in k["bo_qua"]), 6),
        })
    return ma


@frappe.whitelist()
def xem_truoc(name):
    """Chốt thì sẽ làm gì (không ghi gì): từng mã sổ → đếm, chuyển lô, thiếu, thừa; lỗi chặn; cảnh báo."""
    guard_card(CARD)
    from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import ton_lo

    d = _phieu(name)
    ke, _ten_lo, ten = d.lap_ke()
    ma = _tom_tat(ke, ten)
    canh = _canh_bao()
    tp = [i.name for i in items_tp(["name"])]
    chua = [i for i, ls in ton_lo(d.kho, tp).items()
            if i not in ke and any(l["batch"] and not l["hsd"] and not l["thu_hoi"] and l["qty"] > 0 for l in ls)]
    if chua:
        canh.append(_("{0} mã còn lô chưa có HSD mà chưa đếm — chốt lần này giữ nguyên các mã đó.").format(len(chua)))
    return {
        "name": d.name, "ma": ma, "loi": d.kiem_truoc_chot(ke), "canh_bao": canh, "duoc_chot": _duoc_chot(),
        "tong": {"so_ma": len(ma), "so_sach": flt(sum(x["so_sach"] for x in ma), 6),
                 "dem": flt(sum(x["dem"] for x in ma), 6),
                 "thieu": flt(sum(x["thieu"] for x in ma), 6), "thua": flt(sum(x["thua"] for x in ma), 6),
                 "chuyen": flt(sum(x["chuyen"] for x in ma), 6),
                 "phieu_kho": so_chung_tu(chia_chung_tu(ke, nowdate()))},
    }


@frappe.whitelist()
def chot(name):
    """Chốt kiểm kê — chỉ quản lý. Sinh chứng từ kho trong controller (một giao dịch: lỗi là cuộn lại hết)."""
    guard_card(CARD)
    if not _duoc_chot():
        frappe.throw(_("Chỉ quản lý chốt kiểm kê — thủ kho đếm xong thì báo quản lý."), frappe.PermissionError)
    d = _phieu(name)
    d.flags.ignore_permissions = True
    d.submit()
    return {"name": d.name, "so_ma": d.so_ma, "tong_so_sach": d.tong_so_sach, "tong_dem": d.tong_dem,
            "tong_lech": d.tong_lech, "so_phieu_kho": len(json.loads(d.ds_se or "[]"))}


@frappe.whitelist()
def huy(name):
    """Bỏ phiếu đang đếm (chưa chốt thì chưa có gì vào kho). Quản lý hoặc người lập."""
    guard_card(CARD)
    d = _phieu(name)
    if not (_duoc_chot() or d.nguoi_lap == frappe.session.user):
        frappe.throw(_("Chỉ quản lý hoặc người lập phiếu bỏ được phiếu kiểm kê."), frappe.PermissionError)
    frappe.delete_doc(PT, d.name, ignore_permissions=True)
    return tong_quan()


@frappe.whitelist()
def bien_ban(name):
    """HTML biên bản kiểm kê để in: từng mã sổ → đếm → lệch, số đếm theo HSD, kết quả từng lô, chỗ ký."""
    guard_card(CARD)
    if not name or not frappe.db.exists(PT, name):
        frappe.throw(_("Không thấy phiếu kiểm kê {0}.").format(name or ""))
    d = frappe.get_doc(PT, name)
    ten, dem, so_sach = {}, {}, {}
    for r in d.dong or []:
        ten[r.item] = r.ten
        dem.setdefault(r.item, []).append({"hsd": r.hsd, "so": flt(r.so_dem, 3)})
    thieu = [i for i, t in ten.items() if not t]
    if thieu:                         # dòng sửa tay trên Desk có thể chưa có tên
        ten.update({i.name: i.item_name for i in frappe.get_all(
            "Item", filters={"name": ("in", thieu)}, fields=["name", "item_name"])})
    ten = {i: t or i for i, t in ten.items()}
    if d.docstatus == 0:
        # Bản nháp: số sổ sách tính tới lúc in — để soát trước khi chốt.
        ke, _ten_lo, _t = d.lap_ke()
        so_sach = {i: k["so_sach"] for i, k in ke.items()}
    else:
        # Đã chốt: sổ trước = tồn các lô lúc chốt, trừ lô đang thu hồi (để riêng, không kiểm).
        from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import VIEC

        bo = VIEC["thu_hoi"].split(" —")[0]
        for r in d.lo or []:
            if bo not in (r.viec or ""):
                so_sach[r.item] = so_sach.get(r.item, 0.0) + flt(r.so_truoc)
    ma = []
    for i in sorted(ten, key=lambda x: ten[x]):
        dm = flt(sum(x["so"] for x in dem.get(i, [])), 3)
        ss = flt(so_sach.get(i, 0.0), 3) if d.docstatus != 2 else None
        ma.append({"item": i, "ten": ten[i], "dem": sorted((x for x in dem.get(i, []) if x["hsd"]),
                                                            key=lambda x: str(x["hsd"])),
                   "tong_dem": dm, "so_sach": ss, "lech": flt(dm - ss, 3) if ss is not None else None})
    tong = {"dem": flt(sum(m["tong_dem"] for m in ma), 3),
            "so_sach": flt(sum(m["so_sach"] or 0 for m in ma), 3) if d.docstatus != 2 else None}
    tong["lech"] = flt(tong["dem"] - tong["so_sach"], 3) if tong["so_sach"] is not None else None
    se = [x.get("name") for x in json.loads(d.ds_se or "[]")]
    return frappe.render_template("sx/sx/doctype/sx_kiem_ke/bien_ban.html", {
        "d": d, "ma": ma, "tong": tong, "se": se, "cong_ty": get_settings().get("cong_ty") or "",
        "nhap": d.docstatus == 0, "huy": d.docstatus == 2,
        "vn": lambda x: getdate(x).strftime("%d/%m/%Y") if x else "", "so": so_vn,
    })
