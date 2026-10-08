"""API màn "Động vật gây hại" (QC → Hôm nay → 🐀) — W15, D140.

Ghi dấu hiệu theo trạm (quét QR / gõ mã), tuần này, khu có dấu hiệu hai tuần liền, bản in
BM.PRP.03 (tuần) và BM.PRP.01 (tháng). Phần tính ở sx/qc/dong_vat.py.
"""

import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from sx.api.qc import GHI_DUOC, ISO, _guard_ghi, _guard_qc, _roles, _sieu
from sx.qc import dong_vat as DV

PT, TR = "SX Dau Hieu Dong Vat", "SX Tram Dong Vat"


def _tram():
    # R01–R21 trước rồi C01–C19 — đúng thứ tự trên sơ đồ / tài liệu (sắp chữ cái thì C lên trước).
    return sorted(frappe.get_all(TR, filters={"ngung": 0}, fields=["name", "ma", "loai", "khu", "vi_tri"]),
                  key=lambda t: (not t.ma.startswith("R"), t.ma))


def _phieu(tu, den):
    return frappe.get_all(PT, filters={"ngay": ("between", [str(tu), str(den)])},
                          fields=["name", "tram", "khu", "ngay", "dau_hieu", "so_luong", "xu_ly",
                                  "nguoi_ghi", "creation"], order_by="ngay desc, creation desc")


@frappe.whitelist()
def tong_quan(ngay=None):
    """Trạm (nhóm theo khu) + phiếu tuần này + khu có dấu hiệu hai tuần liền."""
    _guard_qc()
    d = getdate(ngay or nowdate())
    w = DV.thu_hai(d)
    tram = _tram()
    gan = _phieu(w - timedelta(days=14), w + timedelta(days=6))
    lan_cuoi = {}
    for p in gan:
        lan_cuoi.setdefault(p.tram, str(p.ngay))
    tuan = [p for p in gan if getdate(p.ngay) >= w]
    return {
        "tuan_tu": str(w), "tuan_den": str(w + timedelta(days=6)),
        "tram": [dict(t, lan_cuoi=lan_cuoi.get(t.ma, ""), tuan_nay=sum(1 for p in tuan if p.tram == t.ma))
                 for t in tram],
        "phieu_tuan": [dict(p, ngay=str(p.ngay), creation=str(p.creation)) for p in tuan],
        "canh_bao": DV.khu_hai_tuan([{"ngay": p.ngay, "khu": p.khu, "tram": p.tram} for p in gan], d),
        "dau_hieu": DV.DAU_HIEU,
        "duoc_ghi": bool(_sieu() or _roles() & GHI_DUOC),
        "la_iso": bool(_sieu() or ISO in _roles()),
        "user": frappe.session.user, "hom_nay": nowdate(),
    }


@frappe.whitelist()
def tim_tram(q):
    """Mã quét / gõ → trạm. Không có → báo rõ."""
    _guard_qc()
    ma = DV.ma_tram(q)
    t = frappe.db.get_value(TR, {"ma": ma}, ["ma", "loai", "khu", "vi_tri", "ngung"], as_dict=True) if ma else None
    if not t:
        frappe.throw(_("Không có trạm \"{0}\" — mã đúng dạng R01–R21, C01–C19.").format(q))
    if cint(t.ngung):
        frappe.throw(_("Trạm {0} đã ngừng dùng.").format(t.ma))
    return t


@frappe.whitelist()
def ghi_dau_hieu(payload):
    _guard_ghi()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    t = tim_tram(p.get("tram"))
    if not p.get("dau_hieu"):
        frappe.throw(_("Chọn loại dấu hiệu."))
    doc = frappe.get_doc({"doctype": PT, "tram": t.ma, "ngay": getdate(p.get("ngay") or nowdate()),
                          "dau_hieu": p["dau_hieu"], "so_luong": cint(p.get("so_luong")) or None,
                          "xu_ly": (p.get("xu_ly") or "").strip(), "ghi_chu": (p.get("ghi_chu") or "").strip()})
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "tram": t.ma, "khu": doc.khu}


@frappe.whitelist()
def xoa_dau_hieu(name):
    """Ghi nhầm: người ghi xoá được trong ngày; Ban ISO xoá được bất cứ lúc nào."""
    _guard_qc()
    x = frappe.db.get_value(PT, name, ["nguoi_ghi", "ngay"], as_dict=True)
    if not x:
        frappe.throw(_("Không có phiếu {0}.").format(name))
    iso = _sieu() or ISO in _roles()
    if not iso and not (x.nguoi_ghi == frappe.session.user and getdate(x.ngay) == getdate(nowdate())):
        frappe.throw(_("Chỉ người ghi (trong ngày) hoặc Ban ISO xoá được phiếu này."),
                     frappe.PermissionError)
    frappe.delete_doc(PT, name, ignore_permissions=True)
    return {"name": name}


@frappe.whitelist()
def in_prp03(ngay=None):
    """BM.PRP.03 — theo dõi động vật gây hại theo trạm, MỘT tuần (thứ Hai → Chủ nhật)."""
    _guard_qc()
    w = DV.thu_hai(getdate(ngay or nowdate()))
    ds = _phieu(w, w + timedelta(days=6))
    theo = {}
    for p in ds:
        theo.setdefault(p.tram, []).append(p)
    return frappe.render_template("sx/qc/prp03.html", {
        "tu": str(w), "den": str(w + timedelta(days=6)), "tram": _tram(), "theo": theo,
        "canh_bao": DV.khu_hai_tuan([{"ngay": p.ngay, "khu": p.khu, "tram": p.tram}
                                     for p in _phieu(w - timedelta(days=14), w + timedelta(days=6))],
                                    w + timedelta(days=6))})


@frappe.whitelist()
def in_prp01(thang=None):
    """BM.PRP.01 — tổng hợp tháng: lưới trạm × tuần, số dấu hiệu mỗi ô."""
    _guard_qc()
    dau = getdate(f"{thang}-01") if thang else getdate(nowdate()).replace(day=1)
    cuoi = (dau.replace(day=28) + timedelta(days=4))
    cuoi = cuoi - timedelta(days=cuoi.day)
    tuan, t = [], DV.thu_hai(dau)
    while t <= cuoi:
        tuan.append(t)
        t += timedelta(days=7)
    ds = _phieu(tuan[0], tuan[-1] + timedelta(days=6))
    o = {}
    for p in ds:
        k = (p.tram, str(DV.thu_hai(p.ngay)))
        o[k] = o.get(k, 0) + 1
    return frappe.render_template("sx/qc/prp01.html", {
        "thang": dau.strftime("%m/%Y"), "tuan": [str(x) for x in tuan], "tram": _tram(), "o": o,
        "tong": len([p for p in ds if dau <= getdate(p.ngay) <= cuoi]),
        "canh_bao": DV.chuoi_lien_tuan([{"ngay": p.ngay, "khu": p.khu, "tram": p.tram} for p in ds])})
