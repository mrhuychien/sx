"""Kiểm xe BM.09.01 — màn #/qc/kiemxe (W34, D165) và sổ in theo tháng (W14, D139).

Dữ liệu nằm trên chứng từ của chuyến hàng (sx/qc/kiem_xe.py): hoá đơn bán trừ kho + phiếu nhập
mua. Thủ kho ghi kiểm xe trên Desk; QC kiểm ngẫu nhiên ít nhất 1 chuyến/tuần → đóng dấu "QC kiểm"
(người + giờ) ở đây — xe nguyên liệu thì QC ghi luôn trên màn Tiếp nhận NL; Trưởng Ban ISO bấm
"Đã xem tháng". Hai dấu này là ô cho phép sau duyệt, ghi bằng db.set_value: không đụng số liệu
chứng từ, không chạy lại luật của hoá đơn; `modified` đổi để Desk đang mở bản cũ không lưu đè.
"""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, nowdate

from sx.api.qc import GHI_DUOC, ISO, _guard_ghi, _guard_manager, _guard_qc, _khoang, _roles, _sieu
from sx.qc import kiem_xe as KX
from sx.qc.quyen import la_iso

CHIEU = {"Sales Invoice": "Giao hàng", "Purchase Receipt": "Nhận nguyên liệu"}
CON = {"Sales Invoice": "Sales Invoice Item", "Purchase Receipt": "Purchase Receipt Item"}
TRUONG = (["name", "posting_date", "docstatus", "doi_tac", "custom_xe_phien_ban", "custom_xe_bien_so",
           "custom_xe_don_vi", "custom_xe_tai_xe", "custom_xe_ket_luan", "custom_xe_nguoi_kiem", "custom_xe_ghi_chu",
           "custom_xe_qc_kiem", "custom_xe_qc_luc", "custom_xe_qc_nhan_xet", "custom_xe_xem_boi", "custom_xe_xem_luc"]
          + [f for pb in sorted(KX.MUC_THEO_PB) for f, _c, _y in KX.MUC_THEO_PB[pb]])


def _thang(thang=None):
    dau = getdate(f"{thang}-01") if thang else getdate(nowdate()).replace(day=1)
    cuoi = dau.replace(day=28) + timedelta(days=4)
    return dau, cuoi - timedelta(days=cuoi.day)


def _ten(u, nho):
    if not u:
        return ""
    if u not in nho:
        nho[u] = frappe.db.get_value("User", u, "full_name") or u
    return nho[u]


def _hsd(d):
    d = getdate(d)
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def _hang(ds):
    """Hàng trên từng chuyến — cột "Hàng, số lượng, HSD": {chứng từ: ["Tên · 40 Hộp · HSD 15/04/2027"]}.
    Lô ở ô batch_no hoặc trong Serial and Batch Bundle của dòng; HSD = hạn của lô."""
    ra = {}
    for dt in KX.LOAI:
        ten = [x.name for x in ds if x.doctype == dt]
        if not ten:
            continue
        try:
            dong = frappe.get_all(CON[dt], filters={"parenttype": dt, "parent": ("in", ten)},
                                  fields=["parent", "idx", "item_code", "item_name", "qty", "uom", "batch_no",
                                          "serial_and_batch_bundle"], order_by="idx asc")
            goi = {r.serial_and_batch_bundle for r in dong if r.serial_and_batch_bundle and not r.batch_no}
            lo_goi = {}
            for e in (frappe.get_all("Serial and Batch Entry", filters={"parent": ("in", list(goi))},
                                     fields=["parent", "batch_no"]) if goi else []):
                lo_goi.setdefault(e.parent, []).append(e.batch_no)
            lo = {r.batch_no for r in dong if r.batch_no} | {b for v in lo_goi.values() for b in v if b}
            han = {b.name: b.expiry_date for b in (frappe.get_all(
                "Batch", filters={"name": ("in", list(lo))}, fields=["name", "expiry_date"]) if lo else [])}
        except Exception:          # site thiếu bảng lô (cài riêng module qc) — vẫn in tên, số lượng
            continue
        for r in dong:
            cac_lo = [r.batch_no] if r.batch_no else lo_goi.get(r.serial_and_batch_bundle) or []
            hsd = ", ".join(_hsd(han[b]) for b in cac_lo if han.get(b)) or ", ".join(b for b in cac_lo if b)
            sl = f"{flt(r.qty):g} {r.uom or ''}".strip()
            ra.setdefault(r.parent, []).append(" · ".join(
                p for p in (r.item_name or r.item_code, sl, f"HSD {hsd}" if hsd else "") if p))
    return ra


def _dong(x, nho, hom_nay=None, hang=None):
    pb = KX.phien_ban(x)
    return {
        "doctype": x.doctype, "name": x.name, "ngay": str(x.posting_date), "chieu": CHIEU[x.doctype],
        "doi_tac": x.get("doi_tac") or "", "nhap": not x.docstatus, "pb": pb,
        "bien_so": x.custom_xe_bien_so or "", "don_vi": x.custom_xe_don_vi or "", "tai_xe": x.custom_xe_tai_xe or "",
        "muc": [{"f": f, "cot": c, "yc": y, "gt": x.get(f) or ""} for f, c, y in KX.MUC_THEO_PB[pb]],
        "ket_luan": x.custom_xe_ket_luan or "", "xu_ly": x.custom_xe_ghi_chu or "",
        "nguoi_kiem": x.custom_xe_nguoi_kiem or "", "ten_nguoi_kiem": _ten(x.custom_xe_nguoi_kiem, nho),
        "qc_kiem": x.custom_xe_qc_kiem or "", "ten_qc": _ten(x.custom_xe_qc_kiem, nho),
        "qc_luc": str(x.custom_xe_qc_luc or "")[:16], "qc_nhan_xet": x.custom_xe_qc_nhan_xet or "",
        "xem_boi": x.custom_xe_xem_boi or "", "ten_xem": _ten(x.custom_xe_xem_boi, nho),
        "xem_luc": str(x.custom_xe_xem_luc or "")[:16],
        "duoc_qc": bool(hom_nay and not x.custom_xe_qc_kiem and KX.duoc_qc_kiem(x.posting_date, hom_nay)),
        "hang": (hang or {}).get(x.name, []),
    }


def _xem(ds):
    """Lần Trưởng Ban ISO xem gần nhất trong các chuyến."""
    x = max((x for x in ds if x["xem_luc"]), key=lambda x: x["xem_luc"], default=None)
    return {"boi": x["xem_boi"], "ten": x["ten_xem"], "luc": x["xem_luc"]} if x else None


def _mot(doctype, name):
    """Một chuyến đã ghi kiểm xe (hoá đơn bán trừ kho / phiếu nhập mua, chưa huỷ, không phải trả hàng)."""
    if doctype not in KX.LOAI:
        frappe.throw(_("Kiểm xe chỉ ghi trên hoá đơn bán trừ kho / phiếu nhập mua."))
    x = frappe.db.get_value(doctype, name, ["name", "posting_date", "docstatus", "is_return", "custom_xe_ket_luan",
                                            "custom_xe_qc_kiem", "custom_xe_qc_luc", "custom_xe_xem_luc"]
                            + (["update_stock"] if doctype == "Sales Invoice" else []), as_dict=True)
    if not x:
        frappe.throw(_("Không có {0}.").format(name))
    if x.docstatus == 2 or x.is_return or (doctype == "Sales Invoice" and not x.update_stock):
        frappe.throw(_("{0} không phải chuyến hàng phải kiểm xe (đã huỷ / trả hàng / không trừ kho).").format(name))
    if not x.custom_xe_ket_luan:
        frappe.throw(_("{0} chưa ghi kiểm xe — thủ kho ghi biển số, năm mục và kết luận trên chứng từ trước.")
                     .format(name))
    return x


@frappe.whitelist()
def tong_quan(thang=None):
    """Chuyến của tháng (mới trước) kèm hàng; các tuần thứ Hai – Chủ nhật của tháng: số chuyến, số chuyến QC
    kiểm; lần Trưởng Ban ISO xem tháng; quyền của người xem."""
    _guard_qc()
    dau, cuoi = _thang(thang)
    hom_nay = getdate(nowdate())
    t2 = KX.thu_hai(dau)
    try:
        ds = KX.chuyen(t2, KX.thu_hai(cuoi) + timedelta(days=6), TRUONG)
    except Exception:          # chưa migrate D165
        ds = []
    trong = [x for x in ds if dau <= getdate(x.posting_date) <= cuoi]
    nho, hang = {}, _hang(trong)
    dong = [_dong(x, nho, hom_nay, hang) for x in trong]
    tuan = KX.theo_tuan(ds)
    roles = _roles()
    ds_tuan = []
    while t2 <= cuoi:
        v = tuan.get(t2) or {}
        ds_tuan.append({"tu": str(t2), "den": str(t2 + timedelta(days=6)), "so_chuyen": v.get("so_chuyen", 0),
                        "so_qc": v.get("so_qc", 0), "nay": t2 <= hom_nay <= t2 + timedelta(days=6),
                        "qua": t2 + timedelta(days=6) < hom_nay})
        t2 += timedelta(days=7)
    return {
        "thang": dau.strftime("%Y-%m"), "hom_nay": str(hom_nay), "tu": str(dau), "den": str(cuoi),
        "ds": list(reversed(dong)), "tuan": list(reversed(ds_tuan)),
        "xem": _xem(dong), "chua_xem": sum(1 for x in dong if not x["nhap"] and not x["xem_luc"]),
        "so_nhap": sum(1 for x in dong if x["nhap"]),
        "so_ngay_qc": KX.SO_NGAY_QC,
        "duoc_ghi": bool(_sieu(roles) or roles & GHI_DUOC),
        "duoc_xem_thang": bool(_sieu(roles) or ISO in roles),
        "la_iso": la_iso(),
        "user": frappe.session.user,
    }


@frappe.whitelist()
def qc_kiem(doctype, name, nhan_xet=None):
    """QC kiểm ngẫu nhiên chuyến này (QT.09 mục 4): đóng dấu người + giờ, kèm nhận xét nếu thấy khác người
    kiểm. Chỉ chuyến trong SO_NGAY_QC ngày — kiểm xe là kiểm lúc xếp / nhận hàng."""
    _guard_ghi()
    x = _mot(doctype, name)
    if x.custom_xe_qc_kiem:
        frappe.throw(_("Chuyến {0} đã có QC kiểm ({1}).").format(name, x.custom_xe_qc_kiem))
    if not KX.duoc_qc_kiem(x.posting_date, nowdate()):
        frappe.throw(_("Chuyến ngày {0}: QC đóng dấu kiểm trong {1} ngày kể từ ngày chuyến (kiểm lúc xếp / nhận "
                       "hàng) — không ký bù chuyến cũ.").format(_hsd(x.posting_date), KX.SO_NGAY_QC))
    luc = now_datetime()
    frappe.db.set_value(doctype, name, {"custom_xe_qc_kiem": frappe.session.user, "custom_xe_qc_luc": luc,
                                        "custom_xe_qc_nhan_xet": (nhan_xet or "").strip()[:500] or None})
    return {"name": name, "qc_kiem": frappe.session.user, "qc_luc": str(luc)[:16]}


@frappe.whitelist()
def bo_qc_kiem(doctype, name):
    """Đóng dấu nhầm chuyến: người đóng dấu bỏ được trong ngày; Ban ISO bỏ được khi tháng chưa xem."""
    _guard_qc()
    x = _mot(doctype, name)
    if not x.custom_xe_qc_kiem:
        frappe.throw(_("Chuyến {0} chưa có QC kiểm.").format(name))
    if x.custom_xe_xem_luc:
        frappe.throw(_("Chuyến {0} đã được Trưởng Ban ISO xem — giữ nguyên.").format(name))
    if not la_iso() and not (x.custom_xe_qc_kiem == frappe.session.user
                             and getdate(x.custom_xe_qc_luc) == getdate(nowdate())):
        frappe.throw(_("Chỉ người đóng dấu (trong ngày) hoặc Ban ISO bỏ được dấu QC kiểm."), frappe.PermissionError)
    frappe.db.set_value(doctype, name, {"custom_xe_qc_kiem": None, "custom_xe_qc_luc": None,
                                        "custom_xe_qc_nhan_xet": None})
    return {"name": name}


@frappe.whitelist()
def xem_thang(thang):
    """Trưởng Ban ISO: "Đã xem tháng MM/YYYY" — ký mọi chuyến ĐÃ DUYỆT của tháng chưa xem (QT.09 mục 4).
    Chuyến duyệt sau đó chưa được xem → hộp nhắc lại nhắc tháng đó."""
    _guard_manager()
    dau, cuoi = _thang(thang)
    if dau > getdate(nowdate()):
        frappe.throw(_("Tháng {0} chưa tới.").format(dau.strftime("%m/%Y")))
    ds = KX.chuyen(dau, cuoi, ["name", "posting_date"], da_duyet=True,
                   loc_them={"custom_xe_xem_luc": ("is", "not set")})
    if not ds:
        frappe.throw(_("Tháng {0} không có chuyến đã duyệt nào chưa xem.").format(dau.strftime("%m/%Y")))
    luc = now_datetime()
    for x in ds:
        frappe.db.set_value(x.doctype, x.name, {"custom_xe_xem_boi": frappe.session.user, "custom_xe_xem_luc": luc})
    return {"so": len(ds), "thang": dau.strftime("%m/%Y")}


def _xem_theo_thang(dong):
    """Chân tờ in: mỗi tháng có chuyến — ai xem, ngày nào; còn chuyến chưa xem thì nói số."""
    ra = {}
    for x in dong:
        t = ra.setdefault(x["ngay"][:7], {"thang": f"{x['ngay'][5:7]}/{x['ngay'][:4]}", "chua": 0, "ds": []})
        t["ds"].append(x)
        t["chua"] += 0 if x["xem_luc"] else 1
    return [dict(t, xem=_xem(t.pop("ds"))) for _k, t in sorted(ra.items())]


@frappe.whitelist()
def in_so_kiem_xe(tu=None, den=None):
    """BM.09.01 — A4 ngang, đúng cột giấy lần BH 01, mỗi chuyến ĐÃ DUYỆT một dòng. Chuyến ghi theo bộ mục
    cũ (trước D165) in bảng riêng với bốn mục cũ."""
    _guard_qc()
    tu, den = _khoang(tu, den)
    try:
        ds = KX.chuyen(tu, den, TRUONG, da_duyet=True)
    except Exception:          # chưa migrate
        ds = []
    nho, hang = {}, _hang(ds)
    dong = [_dong(x, nho, None, hang) for x in ds]
    bang = [{"pb": pb, "muc": [(f, c) for f, c, _y in KX.MUC_THEO_PB[pb]], "ds": [x for x in dong if x["pb"] == pb]}
            for pb in sorted(KX.MUC_THEO_PB, reverse=True)]
    return frappe.render_template("sx/qc/so_kiem_xe.html", {
        "tu": str(tu), "den": str(den), "ds": dong, "pb": KX.PHIEN_BAN,
        "bang": [b for b in bang if b["ds"] or b["pb"] == KX.PHIEN_BAN],
        "thang": tu.strftime("%m/%Y") if (tu, den) == _thang(tu.strftime("%Y-%m")) else "",
        "xem": _xem_theo_thang(dong)})
