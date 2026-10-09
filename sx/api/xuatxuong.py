"""API màn "Xuất xưởng" (QC → Xuất xưởng) + chốt chặn bán lô chưa duyệt — BM.08.04 (W08, D137;
phiếu giấy lần BH 01: W31, D159).

Luật phiếu (trạng thái, ai duyệt, người kiểm không tự duyệt) ở controller SX Kiem Tra
Xuat Xuong; mục kiểm, kết luận, gợi ý hồ sơ lô ở sx/qc/xuat_xuong.py. File này lo các việc
của phía SẢN XUẤT — nên nằm ngoài module qc và được import khotp:
  · danh sách lô CHỜ KIỂM: hàng đã vào hộp chưa nhập kho (khotp.con_theo_hsd) + dòng
    của phiếu nhập kho nháp (gồm hộp Tết);
  · chốt bán: hoá đơn / phiếu giao lô thành phẩm chưa duyệt cho xuất xưởng → chặn;
  · tra chứng từ kho NGÀY SẢN XUẤT cho mục A (W31): lô bột nền đã dùng → ngày nghiền, ngày
    rang (A1); nguyên liệu mua về → kết luận tiếp nhận BM.07.03 (A3). Lô thành phẩm CHƯA nhập
    kho lúc QC kiểm nên không truy được từ lô — truy từ các phiếu kho của phiếu ngày NSX.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

from sx.api.qc import GHI_DUOC, QLSX, _guard_ghi, _guard_qc, _roles, _sieu
from sx.qc import tiep_nhan as TN
from sx.qc import xuat_xuong as XX
from sx.qc.quyen import duoc_duyet_xuat_xuong
from sx.utils import cong_bo_cua, get_settings, items_tp, nsx_tu_hsd

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
        if not XX.mo_lai_duoc(p.get((item, hsd))):
            continue                  # đã có phiếu hiệu lực (hoặc lô Không cho xuất)
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
        x["ket_luan"] = XX.kl(x.get("ket_luan")) or ""
    return {
        "cho_kiem": sorted(({"item": i, "ten": ten.get(i, (i, ""))[0], "dvt": ten.get(i, ("", ""))[1],
                             "hsd": h, "nsx": str(n or ""), "so_luong": flt(sl, 2), "nguon": ng}
                            for i, h, n, sl, ng in cho), key=lambda x: (x["hsd"], x["ten"])),
        "phieu": phieu,
        "duoc_ghi": _duoc_ghi(), "duoc_duyet": duoc_duyet_xuat_xuong(),
        "user": frappe.session.user,
        "chan": _bat(), "tu_ngay": str(tu_ngay() or ""),
    }


# ═══════════════════════════ hồ sơ lô từ chứng từ kho (W31) ═══════════════════════════

def _tra_nguon(nsx):
    """Chứng từ kho của phiếu ngày NSX (đã chốt Ghi sổ): đi ngược cây nguyên liệu (truy xuất,
    sx/api/truyxuat._Ctx) từ các phiếu kho đó.
      · lô bột nền = lô R (D13) → ngày rang (SX Xuat Dau), các ngày nghiền (phiếu kho sinh ra lô R);
      · lá của cây (hàng mua về) → kết luận tiếp nhận BM.07.03 của dòng chứng từ mua.
    Gom cả ngày, không tách theo mã: các vị cùng ngày dùng chung bột nền FIFO, kiểm thừa còn
    hơn sót. Chưa chốt ngày đó / không đọc được → "co" = False, QC tự đối chiếu."""
    def rong():
        return {"co": False, "rang": {}, "nghien": {}, "nvl": {}, "khong_lo": []}

    ra = rong()
    if not nsx:
        return ra
    try:
        from sx.api.truyxuat import _Ctx

        ngay = frappe.get_all("SX Ngay San Xuat", filters={"ngay": getdate(nsx), "docstatus": ("<", 2)},
                              pluck="name")
        se = frappe.get_all("Stock Entry", filters={"custom_ngay_sx": ("in", ngay), "docstatus": 1},
                            pluck="name") if ngay else []
        if not se:
            return ra
        ctx, khong_lo = _Ctx(), set()

        def di(ds):
            for n in ds or []:
                if n.get("rang"):
                    ra["rang"][n["batch"]] = n["rang"].get("ngay")
                if "ncc" in n:
                    ra["nvl"][n["batch"]] = {"ten": n.get("ten") or n.get("item"),
                                             "ket_luan": (n.get("ncc") or {}).get("ket_luan") or ""}
                elif n.get("khong_lo"):
                    khong_lo.add(n.get("ten") or n.get("item"))
                di(n.get("con"))

        for s in sorted(se):
            di(ctx.nguyen_lieu_cua_se(s, set(), 0))
        ra["khong_lo"] = sorted(khong_lo)
        if ra["rang"]:
            # Ngày nghiền = ngày phiếu kho SINH RA lô bột nền (repack nghiền D31, hoặc nhập bột T1).
            dong = frappe.get_all("Stock Entry Detail", filters={
                "batch_no": ("in", list(ra["rang"])), "is_finished_item": 1, "docstatus": 1},
                fields=["parent", "batch_no"])
            ngay_se = {x.name: x.posting_date for x in frappe.get_all(
                "Stock Entry", filters={"name": ("in", list({d.parent for d in dong}) or [""])},
                fields=["name", "posting_date"])}
            for d in dong:
                if ngay_se.get(d.parent):
                    ra["nghien"].setdefault(d.batch_no, set()).add(str(getdate(ngay_se[d.parent])))
        ra["co"] = True
    except Exception:          # site thiếu field / DocType sản xuất → QC tự đối chiếu, không nửa vời
        return rong()
    return ra


def _a3(hs, ng):
    """A3 — nguyên liệu dùng cho lô đã được tiếp nhận đạt (BM.07.03)."""
    if not ng["co"]:
        hs["goi_y"]["A3"] = None
        hs["can_cu"]["A3"] = _("Chưa có chứng từ kho của ngày SX (chưa chốt Ghi sổ) — QC tự đối chiếu "
                               "BM.07.03.")
        return
    nvl = ng["nvl"]
    hong = sorted(_("{0} ({1}): {2}").format(x["ten"], b, x["ket_luan"]) for b, x in nvl.items()
                  if x["ket_luan"] in (TN.KHONG_DAT, TN.CACH_LY))
    chua = sorted(_("{0} ({1})").format(x["ten"], b) for b, x in nvl.items() if not x["ket_luan"])
    dat = [b for b, x in nvl.items() if x["ket_luan"] == TN.DAT]
    phan = [_("{0} lô tiếp nhận Đạt").format(len(dat))]
    if hong:
        phan.append(_("KHÔNG ĐẠT / CÁCH LY: {0}").format("; ".join(hong)))
    if chua:
        phan.append(_("chưa có kết luận tiếp nhận: {0}").format("; ".join(chua)))
    if ng["khong_lo"]:
        phan.append(_("hàng không theo lô: {0}").format(", ".join(ng["khong_lo"])))
    phan.append(_("bao bì QC tự đối chiếu"))
    hs["goi_y"]["A3"] = XX.KHONG_DAT if hong else (XX.DAT if dat and not chua else None)
    hs["can_cu"]["A3"] = _("Nguyên liệu theo chứng từ kho ngày SX: ") + " · ".join(phan)


def _goi_y(doc, lap=False):
    """Điền gợi ý mục A (kết quả gợi ý, căn cứ, số phiếu A2) + ô Hồ sơ lô — KHÔNG chấm thay QC,
    trừ A5 mẫu lưu (kiểm tự động như trước D159). Lúc lập phiếu điền luôn ngày nghiền / ngày rang
    tra được (sớm nhất) và quy cách theo bộ tự công bố; QC sửa được."""
    sp = cong_bo_cua(doc.san_pham) or {}
    ng = _tra_nguon(doc.nsx)
    nghien = [doc.ngay_nghien] if doc.get("ngay_nghien") else sorted(set().union(*ng["nghien"].values()))
    rang = [doc.ngay_rang] if doc.get("ngay_rang") else list(ng["rang"].values())
    hs = XX.ho_so_lo(doc.san_pham, doc.hsd, doc.nsx, nghien, rang, doc.get("batch"), sp.get("loai"),
                     sp.get("co_lac"))
    _a3(hs, ng)
    if lap:
        doc.ngay_nghien = doc.get("ngay_nghien") or (min(str(getdate(x)) for x in nghien) if nghien else None)
        doc.ngay_rang = doc.get("ngay_rang") or (min(str(getdate(x)) for x in rang) if rang else None)
        doc.quy_cach = doc.get("quy_cach") or ((sp.get("quy_cach") or "").strip().split("\n")[0][:140] or None)
    for r in doc.ds_muc:
        if r.ma not in XX.MA_A:
            continue
        r.goi_y = hs["goi_y"].get(r.ma) or ""
        r.can_cu = hs["can_cu"].get(r.ma) or ""
        if hs["su_co"].get(r.ma) and not r.get("su_co"):
            r.su_co = hs["su_co"][r.ma]
        if r.ma == "A5" and r.goi_y == XX.DAT and not r.get("ket_qua"):
            r.ket_qua = XX.DAT
    doc.ho_so = XX.chu_ho_so(hs["can_cu"])


def _dict(doc):
    ai, roles = frappe.session.user, _roles()
    d = {k: doc.get(k) for k in ("name", "san_pham", "ten_san_pham", "quy_cach", "hsd", "nsx", "trang_thai",
                                 "ket_luan", "batch", "so_luong", "dvt", "so_mau", "ho_so", "ghi_chu",
                                 "ngay_nghien", "ngay_rang", "qc_kiem", "kiem_luc", "qlsx", "qlsx_luc",
                                 "nguoi_duyet", "duyet_luc", "y_kien_duyet", "su_co")}
    for k in ("hsd", "nsx", "kiem_luc", "duyet_luc", "ngay_nghien", "ngay_rang", "qlsx_luc"):
        d[k] = str(d[k] or "")
    d["ket_luan"] = XX.kl(d["ket_luan"]) or ""
    d["moi"] = XX.la_moi(doc.get("ds_muc"))
    d["ds_muc"] = [{"ma": r.ma, "noi_dung": r.noi_dung, "yeu_cau": r.get("yeu_cau") or "",
                    "ket_qua": r.ket_qua or "", "ghi_chu": r.ghi_chu or "", "mau": XX.mau(r),
                    "su_co": r.get("su_co") or "", "goi_y": r.get("goi_y") or "",
                    "can_cu": r.get("can_cu") or ""} for r in doc.get("ds_muc") or []]
    d["sua"] = _duoc_ghi() and doc.trang_thai in (XX.NHAP, XX.TRA)
    d["duyet"] = (duoc_duyet_xuat_xuong() and doc.trang_thai == XX.CHO and doc.qc_kiem != ai)
    d["tu_kiem"] = doc.trang_thai == XX.CHO and doc.qc_kiem == ai
    d["ky_qlsx"] = bool((_sieu(roles) or QLSX in roles) and doc.trang_thai in (XX.CHO, XX.DUYET)
                        and not doc.get("qlsx"))
    d["xu_ly"] = XX.XU_LY
    d["su_co_lo"] = []
    if d["sua"] and d["moi"]:
        ngay = [x for x in (doc.nsx, doc.get("ngay_nghien"), doc.get("ngay_rang")) if x]
        d["su_co_lo"] = [{"name": x.name, "trang_thai": x.trang_thai or "", "quyet_dinh_sp": x.quyet_dinh_sp or "",
                          "mo_ta": (x.mo_ta or "")[:90]}
                         for x in XX.su_co_lien_quan(doc.san_pham, doc.hsd, doc.get("batch"), ngay)]
    return d


@frappe.whitelist()
def lap_phieu(san_pham, hsd, so_luong=None, dvt=None):
    """Mở phiếu cho một lô: đã có phiếu hiệu lực thì trả phiếu đó (bấm hai lần không đẻ
    hai phiếu). Phiếu mới theo bản giấy lần BH 01 (A1–A5, B1–B6) và tự tra hồ sơ lô: gợi ý
    A1–A4 (QC vẫn bấm), chấm sẵn A5 khi đã lấy mẫu lưu."""
    _guard_ghi()
    cu = XX.theo_lo([(san_pham, hsd)]).get((san_pham, str(getdate(hsd))))
    if not XX.mo_lai_duoc(cu):
        return _dict(frappe.get_doc(XX.PT, cu.name))
    nsx = nsx_tu_hsd(san_pham, hsd)
    lo = frappe.get_all("Batch", filters={"item": san_pham, "expiry_date": getdate(hsd)},
                        pluck="name", order_by="creation asc", limit=1)
    doc = frappe.get_doc({"doctype": XX.PT, "san_pham": san_pham, "hsd": getdate(hsd), "nsx": nsx,
                          "trang_thai": XX.NHAP, "so_luong": flt(so_luong) or None,
                          "dvt": dvt or frappe.db.get_value("Item", san_pham, "stock_uom"),
                          "batch": lo[0] if lo else None})
    for ma, nd, yc in XX.MUC:
        doc.append("ds_muc", {"ma": ma, "noi_dung": nd, "yeu_cau": yc, "ket_qua": ""})
    _goi_y(doc, lap=True)
    doc.insert(ignore_permissions=True)
    return _dict(doc)


@frappe.whitelist()
def xem_phieu(name):
    _guard_qc()
    return _dict(frappe.get_doc(XX.PT, name))


def _ngay_da_qua(v, nhan):
    if not v:
        return None
    d = getdate(v)
    if d > getdate(nowdate()):
        frappe.throw(_("{0} {1} chưa tới.").format(nhan, _vn(d)))
    return str(d)


def _su_co_co_that(v):
    v = (v or "").strip()
    if not v:
        return None
    if not frappe.db.exists("SX Su Co", v):
        frappe.throw(_("Không thấy phiếu sự cố {0}.").format(v))
    return v


def _ghi(doc, p):
    moi = XX.la_moi(doc.ds_muc)
    theo_ma = {str(x.get("ma")): x for x in p.get("ds_muc") or []}
    for r in doc.ds_muc:
        x = theo_ma.get(str(r.ma))
        if x is None:
            continue
        kq = x.get("ket_qua") or ""
        hop = ("", XX.DAT, XX.KHONG_DAT) + ((XX.KAD,) if not moi or r.ma in XX.KAD_DUOC else ())
        if kq not in hop:
            frappe.throw(_("Kết quả không hợp lệ ở mục {0}.").format(r.ma))
        r.ket_qua = kq
        if "ghi_chu" in x:
            r.ghi_chu = (x.get("ghi_chu") or "").strip()[:140]
        if moi and r.ma in XX.MA_B and "mau" in x:
            m = list(x.get("mau") or [])
            for i in range(XX.SO_MAU):
                r.set(f"mau_{i + 1}", XX.chuan_mau(r.ma, m[i] if i < len(m) else ""))
        if moi and r.ma == "A2" and "su_co" in x:
            r.su_co = _su_co_co_that(x.get("su_co"))
    if "ket_luan" in p:
        k = XX.kl(p.get("ket_luan") or "")
        if k and k not in XX.KET_LUAN:
            frappe.throw(_("Kết luận không hợp lệ: {0}.").format(k))
        doc.ket_luan = k or None
    for k in ("ghi_chu", "dvt"):
        if k in p:
            doc.set(k, (p[k] or "").strip() or None)
    if "quy_cach" in p:
        doc.quy_cach = (p["quy_cach"] or "").strip()[:140] or None
    for k, nhan in (("ngay_nghien", _("Ngày nghiền")), ("ngay_rang", _("Ngày rang"))):
        if k in p:
            doc.set(k, _ngay_da_qua(p[k], nhan))
    if "su_co" in p:
        doc.su_co = _su_co_co_that(p["su_co"])
    if "so_mau" in p:
        doc.so_mau = cint(p["so_mau"])      # phiếu lần BH 01: controller đặt lại 5
    if "so_luong" in p:
        doc.so_luong = flt(p["so_luong"]) or None


def _payload(payload):
    return json.loads(payload) if isinstance(payload, str) else dict(payload or {})


@frappe.whitelist()
def luu_phieu(name, payload):
    """QC ghi kết quả — chỉ khi phiếu Nháp / Trả lại (Chờ duyệt thì rút lại trước)."""
    _guard_ghi()
    doc = frappe.get_doc(XX.PT, name)
    if doc.trang_thai not in (XX.NHAP, XX.TRA):
        frappe.throw(_("Phiếu đang {0} — không sửa được.").format(doc.trang_thai.lower()))
    _ghi(doc, _payload(payload))
    doc.save(ignore_permissions=True)
    return _dict(doc)


@frappe.whitelist()
def gui_duyet(name, payload=None):
    _guard_ghi()
    doc = frappe.get_doc(XX.PT, name)
    if doc.trang_thai not in (XX.NHAP, XX.TRA):
        frappe.throw(_("Phiếu đang {0}.").format(doc.trang_thai.lower()))
    if payload:
        _ghi(doc, _payload(payload))
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
def tra_ho_so(name, payload=None):
    """Tra lại hồ sơ lô (gợi ý A1–A5) — sau khi QC sửa ngày nghiền / ngày rang, hoặc vừa lấy mẫu
    lưu. Ghi luôn những gì QC đang chấm; không đổi kết quả QC đã bấm (trừ A5 còn trống)."""
    _guard_ghi()
    doc = frappe.get_doc(XX.PT, name)
    if doc.trang_thai not in (XX.NHAP, XX.TRA):
        frappe.throw(_("Phiếu đang {0} — không sửa được.").format(doc.trang_thai.lower()))
    if not XX.la_moi(doc.ds_muc):
        frappe.throw(_("Phiếu theo mẫu tạm trước lần BH 01 — không tra lại hồ sơ được."))
    if payload:
        _ghi(doc, _payload(payload))
    _goi_y(doc)
    doc.save(ignore_permissions=True)
    return _dict(doc)


@frappe.whitelist()
def ky_qlsx(name):
    """Quản lý sản xuất ký ô thứ ba của BM.08.04 (tài khoản + giờ) — sau khi QC gửi duyệt; không
    bắt buộc để duyệt. Ghi thẳng hai ô (không qua khoá phiếu đã duyệt: chữ ký không đổi nội dung)."""
    _guard_qc()
    if not (_sieu() or QLSX in _roles()):
        frappe.throw(_("Chỉ Quản lý sản xuất ký ô này."), frappe.PermissionError)
    doc = frappe.get_doc(XX.PT, name)
    if doc.trang_thai not in (XX.CHO, XX.DUYET):
        frappe.throw(_("QC gửi duyệt rồi Quản lý sản xuất mới ký."))
    if doc.get("qlsx"):
        frappe.throw(_("Phiếu đã có chữ ký Quản lý sản xuất ({0}).").format(doc.qlsx))
    doc.db_set({"qlsx": frappe.session.user, "qlsx_luc": now_datetime()})
    return _dict(doc)


@frappe.whitelist()
def in_phieu(name):
    """HTML A4 — phiếu kiểm tra xuất xưởng BM.08.04."""
    _guard_qc()
    return frappe.render_template("sx/qc/xuat_xuong.html", {"d": frappe.get_doc(XX.PT, name)})
