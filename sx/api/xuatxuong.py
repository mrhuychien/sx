"""API màn "Xuất xưởng" (QC → Xuất xưởng) + chốt chặn bán lô chưa duyệt — BM.08.04 (W08, D137).

Luật phiếu (trạng thái, ai duyệt, người kiểm không tự duyệt) ở controller SX Kiem Tra
Xuat Xuong; tra cứu trạng thái lô ở sx/qc/xuat_xuong.py. File này lo hai việc của
phía SẢN XUẤT — nên nằm ngoài module qc và được import khotp:
  · danh sách lô CHỜ KIỂM: hàng đã vào hộp chưa nhập kho (khotp.con_theo_hsd) + dòng
    của phiếu nhập kho nháp (gồm hộp Tết);
  · chốt bán: hoá đơn / phiếu giao lô thành phẩm chưa duyệt xuất xưởng → chặn.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from sx.api.qc import GHI_DUOC, _guard_ghi, _guard_qc, _roles, _sieu
from sx.qc import xuat_xuong as XX
from sx.qc.quyen import duoc_duyet_xuat_xuong
from sx.utils import get_settings, items_tp, nsx_tu_hsd

SO_NGAY = 30


def _bat(s=None):
    s = s or get_settings()
    v = s.get("chan_nhap_chua_xuat_xuong")
    return True if v is None else bool(cint(v))


def tu_ngay(s=None):
    s = s or get_settings()
    return getdate(s.get("xuat_xuong_tu_ngay")) if s.get("xuat_xuong_tu_ngay") else None


def _vn(d):
    return getdate(d).strftime("%d/%m/%Y") if d else ""


# ═══════════════════════════════════ chốt chặn ═══════════════════════════════════

def chan_nhap_kho(phieu):
    """Gọi từ SX Phieu Nhap TP.before_submit: lô (mã, HSD) chưa duyệt xuất xưởng → chặn."""
    s = get_settings()
    if not _bat(s):
        return
    tn = tu_ngay(s)
    if tn and phieu.get("ngay") and getdate(phieu.ngay) < tn:
        return
    cap = [(r.item, r.hsd) for r in phieu.get("dong") or [] if flt(r.so_dem) > 0 and r.get("hsd")]
    thieu = XX.chua_duyet(cap)
    if not thieu:
        return
    ten = {r.item: r.ten or r.item for r in phieu.get("dong") or []}
    frappe.throw(
        _("Lô chưa được duyệt kiểm tra xuất xưởng (BM.08.04) — chưa nhập kho được:") + "<br>"
        + "<br>".join(_("• {0} · HSD {1} — {2}").format(ten.get(i, i), _vn(h), XX.mo_ta(p))
                      for i, h, p in thieu)
        + "<br><br>" + _("QC kiểm ở màn QC → Xuất xưởng, Trưởng Ban ISO / người được giao duyệt."),
        title=_("Chờ duyệt xuất xưởng"))


def kiem_ban(doc, method=None):
    """before_submit + on_submit của Sales Invoice (trừ kho) / Delivery Note / POS Invoice:
    lô thành phẩm tạo từ ngày áp dụng mà chưa duyệt xuất xưởng → chặn. Trả hàng: qua."""
    if cint(doc.get("is_return")):
        return
    if doc.doctype == "Sales Invoice" and not cint(doc.get("update_stock")):
        return
    s = get_settings()
    if not _bat(s):
        return
    from sx.api.thuhoi import _lo_cac_dong

    cap = _lo_cac_dong(doc)
    if not cap:
        return
    tp = {i.name for i in items_tp(["name"])}
    loc = {"name": ("in", list({b for _r, b in cap}))}
    truong = ["name", "item", "item_name", "expiry_date", "creation"]
    try:
        ds = frappe.get_all("Batch", filters=loc, fields=truong + ["custom_kiem_ke"])
    except Exception:                 # chưa migrate D154
        ds = frappe.get_all("Batch", filters=loc, fields=truong)
    lo = {b.name: b for b in ds}
    tn = tu_ngay(s)
    can = []
    for r, b in cap:
        x = lo.get(b)
        if not x or x.item not in tp or not x.expiry_date:
            continue
        if tn and getdate(x.creation) < tn:
            continue                  # tồn cũ trước ngày áp dụng BM.08.04
        if x.get("custom_kiem_ke"):
            continue                  # D154: tồn cũ chuyển sang lô theo HSD lúc chốt kiểm kê
        can.append((r, x))
    if not can:
        return
    thieu = {(i, h) for i, h, _p in XX.chua_duyet([(x.item, x.expiry_date) for _r, x in can])}
    sai = [(r, x) for r, x in can if (x.item, str(getdate(x.expiry_date))) in thieu]
    if sai:
        frappe.throw(_("Lô chưa được duyệt xuất xưởng (BM.08.04) — chưa bán / giao được:") + "<br>"
                     + "<br>".join(_("• Dòng {0}: {1} HSD {2}").format(r.idx, x.item_name or x.item,
                                                                        _vn(x.expiry_date))
                                   for r, x in sai), title=_("Chờ duyệt xuất xưởng"))


def trang_thai_cac_lo(cap):
    """{(item, 'YYYY-MM-DD'): {name, trang_thai, ket_luan, duyet, chu}} — cho màn nhập kho."""
    p = XX.theo_lo(cap)
    ra = {}
    for i, h in cap:
        if not i or not h:
            continue
        k = (i, str(getdate(h)))
        x = p.get(k)
        ra[k] = {"name": x.name if x else "", "duyet": XX.da_duyet(x), "chu": XX.mo_ta(x)}
    return ra


# ═══════════════════════════════════ màn hình ════════════════════════════════════

def _duoc_ghi():
    return bool(_sieu() or _roles() & GHI_DUOC)


def _cho_kiem():
    """[(item, hsd, nsx, so_luong, nguon)] — lô có hàng chờ nhập kho, chưa có phiếu hiệu lực."""
    from sx.api.khotp import con_theo_hsd

    den = getdate(nowdate())
    gom = {}
    for item, ds in con_theo_hsd(add_days(den, -SO_NGAY + 1), den).items():
        for g in ds:
            if g.get("hsd"):
                k = (item, str(getdate(g["hsd"])))
                x = gom.setdefault(k, {"so_luong": 0.0, "nsx": g.get("nsx"), "nguon": _("đã vào hộp")})
                x["so_luong"] += flt(g.get("con"))
    for r in frappe.get_all("SX Phieu Nhap TP Item",
                            filters={"parenttype": "SX Phieu Nhap TP", "docstatus": 0},
                            fields=["item", "hsd", "so_dem", "so_lap"]):
        if not r.hsd:
            continue
        k = (r.item, str(getdate(r.hsd)))
        if k not in gom:
            gom[k] = {"so_luong": flt(r.so_dem) or flt(r.so_lap), "nsx": None,
                      "nguon": _("phiếu nhập kho nháp")}
    if not gom:
        return []
    p = XX.theo_lo(list(gom))
    ra = []
    for (item, hsd), x in gom.items():
        cu = p.get((item, hsd))
        if cu and not (cu.trang_thai == XX.DUYET and cu.ket_luan == XX.KHONG_DAT):
            continue                  # đã có phiếu hiệu lực
        ra.append((item, hsd, x["nsx"] or nsx_tu_hsd(item, hsd), x["so_luong"], x["nguon"]))
    return ra


@frappe.whitelist()
def ds_xuat_xuong():
    """Lô chờ kiểm + phiếu đang mở + phiếu đã duyệt 30 ngày."""
    _guard_qc()
    cho = _cho_kiem()
    ten = {i.name: (i.item_name or i.name, i.stock_uom or "") for i in frappe.get_all(
        "Item", filters={"name": ("in", list({c[0] for c in cho}) or [""])},
        fields=["name", "item_name", "stock_uom"])}
    tu = add_days(getdate(nowdate()), -SO_NGAY)
    phieu = [x for x in frappe.get_all(
        XX.PT, fields=["name", "san_pham", "ten_san_pham", "hsd", "nsx", "trang_thai", "ket_luan",
                       "so_luong", "dvt", "qc_kiem", "kiem_luc", "nguoi_duyet", "duyet_luc",
                       "y_kien_duyet", "su_co", "batch", "modified"],
        order_by="modified desc", limit=300)
        if x.trang_thai != XX.DUYET or getdate(x.get("duyet_luc") or x.get("modified")) >= tu]
    for x in phieu:
        for k in ("hsd", "nsx", "kiem_luc", "duyet_luc", "modified"):
            x[k] = str(x.get(k) or "")
    return {
        "cho_kiem": sorted(({"item": i, "ten": ten.get(i, (i, ""))[0], "dvt": ten.get(i, ("", ""))[1],
                             "hsd": h, "nsx": str(n or ""), "so_luong": flt(sl, 2), "nguon": ng}
                            for i, h, n, sl, ng in cho), key=lambda x: (x["hsd"], x["ten"])),
        "phieu": phieu,
        "duoc_ghi": _duoc_ghi(), "duoc_duyet": duoc_duyet_xuat_xuong(),
        "user": frappe.session.user,
        "chan": _bat(), "tu_ngay": str(tu_ngay() or ""),
    }


def _dict(doc):
    ai = frappe.session.user
    d = {k: doc.get(k) for k in ("name", "san_pham", "ten_san_pham", "hsd", "nsx", "trang_thai",
                                 "ket_luan", "batch", "so_luong", "dvt", "so_mau", "ho_so", "ghi_chu",
                                 "qc_kiem", "kiem_luc", "nguoi_duyet", "duyet_luc", "y_kien_duyet",
                                 "su_co")}
    for k in ("hsd", "nsx", "kiem_luc", "duyet_luc"):
        d[k] = str(d[k] or "")
    d["ds_muc"] = [{"ma": r.ma, "noi_dung": r.noi_dung, "ket_qua": r.ket_qua or "",
                    "ghi_chu": r.ghi_chu or ""} for r in doc.get("ds_muc") or []]
    d["sua"] = _duoc_ghi() and doc.trang_thai in (XX.NHAP, XX.TRA)
    d["duyet"] = (duoc_duyet_xuat_xuong() and doc.trang_thai == XX.CHO and doc.qc_kiem != ai)
    d["tu_kiem"] = doc.trang_thai == XX.CHO and doc.qc_kiem == ai
    return d


@frappe.whitelist()
def lap_phieu(san_pham, hsd, so_luong=None, dvt=None):
    """Mở phiếu cho một lô: đã có phiếu hiệu lực thì trả phiếu đó (bấm hai lần không đẻ
    hai phiếu). Phiếu mới tự tra hồ sơ lô (lượt BM.08.01 ngày NSX, sự cố mở, mẫu lưu)
    và chấm sẵn mục 1 / 8 khi có căn cứ — QC vẫn sửa được."""
    _guard_ghi()
    cu = XX.theo_lo([(san_pham, hsd)]).get((san_pham, str(getdate(hsd))))
    if cu and not (cu.trang_thai == XX.DUYET and cu.ket_luan == XX.KHONG_DAT):
        return _dict(frappe.get_doc(XX.PT, cu.name))
    nsx = nsx_tu_hsd(san_pham, hsd)
    hs = XX.ho_so_lo(san_pham, hsd, nsx)
    doc = frappe.get_doc({"doctype": XX.PT, "san_pham": san_pham, "hsd": getdate(hsd), "nsx": nsx,
                          "trang_thai": XX.NHAP, "so_luong": flt(so_luong) or None,
                          "dvt": dvt or frappe.db.get_value("Item", san_pham, "stock_uom"),
                          "ho_so": hs["chu"]})
    for ma, nd in XX.MUC:
        kq = hs["muc1"] if ma == "1" else (hs["muc8"] if ma == "8" else None)
        doc.append("ds_muc", {"ma": ma, "noi_dung": nd, "ket_qua": kq or ""})
    doc.insert(ignore_permissions=True)
    return _dict(doc)


@frappe.whitelist()
def xem_phieu(name):
    _guard_qc()
    return _dict(frappe.get_doc(XX.PT, name))


def _ghi(doc, p):
    theo_ma = {str(x.get("ma")): x for x in p.get("ds_muc") or []}
    for r in doc.ds_muc:
        x = theo_ma.get(str(r.ma))
        if x is not None:
            kq = x.get("ket_qua") or ""
            if kq not in ("", XX.DAT, XX.KHONG_DAT, "Không áp dụng"):
                frappe.throw(_("Kết quả không hợp lệ ở mục {0}.").format(r.ma))
            r.ket_qua, r.ghi_chu = kq, (x.get("ghi_chu") or "").strip()
    for k in ("ket_luan", "ghi_chu", "dvt"):
        if k in p:
            doc.set(k, p[k] or None)
    for k in ("so_mau",):
        if k in p:
            doc.set(k, cint(p[k]))
    if "so_luong" in p:
        doc.so_luong = flt(p["so_luong"]) or None


@frappe.whitelist()
def luu_phieu(name, payload):
    """QC ghi kết quả — chỉ khi phiếu Nháp / Trả lại (Chờ duyệt thì rút lại trước)."""
    _guard_ghi()
    doc = frappe.get_doc(XX.PT, name)
    if doc.trang_thai not in (XX.NHAP, XX.TRA):
        frappe.throw(_("Phiếu đang {0} — không sửa được.").format(doc.trang_thai.lower()))
    _ghi(doc, json.loads(payload) if isinstance(payload, str) else dict(payload or {}))
    doc.save(ignore_permissions=True)
    return _dict(doc)


@frappe.whitelist()
def gui_duyet(name, payload=None):
    _guard_ghi()
    doc = frappe.get_doc(XX.PT, name)
    if doc.trang_thai not in (XX.NHAP, XX.TRA):
        frappe.throw(_("Phiếu đang {0}.").format(doc.trang_thai.lower()))
    if payload:
        _ghi(doc, json.loads(payload) if isinstance(payload, str) else dict(payload))
    doc.trang_thai = XX.CHO
    doc.save(ignore_permissions=True)
    return _dict(doc)


@frappe.whitelist()
def rut_lai(name):
    """QC rút phiếu đang chờ duyệt về Nháp để sửa."""
    _guard_ghi()
    doc = frappe.get_doc(XX.PT, name)
    if doc.trang_thai != XX.CHO:
        frappe.throw(_("Chỉ rút lại được phiếu đang chờ duyệt."))
    doc.trang_thai = XX.NHAP
    doc.save(ignore_permissions=True)
    return _dict(doc)


@frappe.whitelist()
def duyet_phieu(name, dong_y=1, y_kien=None):
    """Duyệt (dong_y=1) / trả lại (0) — quyền và "không tự duyệt" chốt ở controller."""
    _guard_qc()
    doc = frappe.get_doc(XX.PT, name)
    doc.y_kien_duyet = (y_kien or "").strip() or doc.y_kien_duyet
    doc.trang_thai = XX.DUYET if cint(dong_y) else XX.TRA
    doc.save(ignore_permissions=True)
    return _dict(doc)


@frappe.whitelist()
def in_phieu(name):
    """HTML A4 — phiếu kiểm tra xuất xưởng BM.08.04."""
    _guard_qc()
    return frappe.render_template("sx/qc/xuat_xuong.html", {"d": frappe.get_doc(XX.PT, name)})
