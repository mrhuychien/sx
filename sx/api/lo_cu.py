"""Chứng từ lập TRƯỚC lúc mã được bật quản lý lô (D198).

Kiểm kê thành phẩm bật lô cho mã chưa quản lý lô (D189, D191) bằng cách ghi thẳng Item.has_batch_no. Từ lúc đó mọi
phiếu xuất của mã phải có lô — kể cả những chứng từ CŨ còn treo, lập khi mã chưa có lô:
  · phiếu POS lập trước lúc bật lô: đóng ca POS mới gộp thành Sales Invoice trừ kho, ghi sổ đúng giờ của phiếu POS;
  · hoá đơn bán / phiếu giao cũ (vd tháng 8) huỷ để sửa rồi gửi lại.
Dòng của chúng không có lô; ERPNext đòi lô (tự chọn lô thì ở thời điểm đó lô chưa có hàng), kiểm tra W06 của app
(banhang.kiem_lo_ban) chặn "Chưa chọn lô" → không đóng được ca POS, không gửi lại được hoá đơn.

Ở đây: Sales Invoice / Delivery Note trừ kho có dòng KHÔNG lô của mã đã bật lô, mà mọi dòng của mã đó ghi sổ TRƯỚC lúc
bật lô (hoá đơn gộp từ POS: xét giờ của từng phiếu POS) → trong lúc gửi / huỷ, mã tạm TẮT lô rồi bật lại ngay (cùng
giao dịch, như D189) → ghi sổ KHÔNG lô, đúng như lúc lập. Lúc bật lô của mã đọc từ nhật ký phiếu kiểm kê đã chốt
(ds_se: dòng Item has_batch_no 0 → 1; lúc bấm chốt).

D199: dòng của chứng từ đó mà lại MANG lô (sửa hoá đơn cũ trên Desk — hộp chọn lô của ERPNext tự điền lô HSD sớm nhất)
thì lô sai chắc chắn: lô của mã chỉ có hàng từ lúc bật lô, ghi sổ ngày cũ thì ERPNext báo "Batch No … has negative
stock". Lúc gửi: bỏ lô khỏi dòng (xoá gói lô nháp), rồi tạm tắt lô như trên; báo lại đã bỏ lô nào.

Hoá đơn gộp từ POS (đóng ca) gộp MỌI phiếu POS của một khách trong ca — có thể lẫn phiếu lập sau lúc bật lô (đã có
lô), hoặc phiếu lập sau lúc bật lô mà máy POS còn nhớ mã chưa có lô (không lô). Mã đó không tắt lô được (dòng có lô
thành hỏng) → gán lô cho các dòng không lô: lô tồn cũ trước (D191 — hàng không lô ở kho đó lúc bật lô vào lô này), rồi
HSD sớm nhất; một lô đủ số cả dòng, tính theo tồn lúc ghi sổ hoá đơn. Không ai chọn lô lúc đóng ca — để trống thì không
đóng ca được. Riêng phiếu POS lập TRƯỚC lúc bật lô bán ở chính kho đã kiểm kê: số đếm đã trừ phần đó, gán lô là trừ hai
lần → chặn, nói cách tách.

Ghi sổ muộn như vậy để lại phần KHÔNG LÔ khác 0 sau lúc bật lô (lúc bật, phần không lô đã về 0 / vào lô theo số lúc
đó). "Dọn tồn không lô" (quản lý — thẻ Kiểm kê) đưa phần đó về 0:
  · kho đã kiểm kê bật lô (số đếm là tồn thật lúc chốt): phiếu ĐIỀU CHỈNH không lô — âm → nhập bù, dương → xuất;
  · kho khác (cửa hàng, xưởng — D191 chuyển nguyên số vào lô tồn cũ, không đếm): ĐỔI với lô — âm → xuất từ lô tồn cũ
    (thiếu thì lô HSD sớm nhất) rồi nhập vào phần không lô; dương → xuất phần không lô, nhập vào lô tồn cũ. Không đổi
    tổng tồn.
Danh sách in cho kế toán đọc lại từ chính các phiếu đã ghi.
"""

import json
import re
from datetime import datetime

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, get_time, getdate, now_datetime

KIEU_BAN = ("Sales Invoice", "Delivery Note")
GHI_CHU = "Dọn tồn không lô sau bật lô"
LAN = re.compile(r"\[(DL-\d{6}-\d{6})\]")
EPS = 1e-6


def moc_bat_lo():
    """{mã: {luc, phieu, kho, lo_cu, se}} — mã đã được kiểm kê bật quản lý lô: lúc bật (giờ bấm chốt), phiếu kiểm
    kê, kho đã đếm, lô tồn cũ (D191), các phiếu kho của lần chốt đó. Nhiều lần → lần sớm nhất. Nhớ theo request."""
    nho = getattr(frappe.local, "sx_moc_bat_lo", None)
    if nho is not None:
        return nho
    ra = {}
    for p in frappe.get_all("SX Kiem Ke", filters={"docstatus": 1, "ds_se": ("like", '%"dt": "Item"%')},
                            fields=["name", "kho", "chot_luc", "modified", "ds_se"], order_by="chot_luc asc"):
        ds = json.loads(p.ds_se or "[]")
        dau = {}
        for x in ds:
            if x.get("dt") == "Item" and x.get("name"):
                dau.setdefault(x["name"], x)
        se = {x.get("name") for x in ds if x.get("dt") != "Item"}
        for i, x in dau.items():
            # Lần đổi cờ ĐẦU TIÊN là 1 → 0: mã vốn có lô, chỉ tạm tắt lúc chốt (D189 "le") — không phải bật lô.
            if i in ra or not (p.chot_luc or p.modified) or cint((x.get("has_batch_no") or [1])[0]):
                continue
            lo_cu = next((y.get("lo_cu") for y in ds if y.get("dt") == "Item" and y.get("name") == i
                          and y.get("lo_cu")), None)
            ra[i] = {"luc": get_datetime(p.chot_luc or p.modified), "phieu": p.name, "kho": p.kho, "lo_cu": lo_cu,
                     "se": se}
    frappe.local.sx_moc_bat_lo = ra
    return ra


def _luc(d):
    """Giờ ghi sổ của chứng từ."""
    return datetime.combine(getdate(d.get("posting_date")), get_time(d.get("posting_time") or "00:00:00"))


def _gop_pos(doc):
    """Hoá đơn gộp từ POS lúc đóng ca (không phải trả hàng)."""
    return doc.doctype == "Sales Invoice" and cint(doc.get("is_consolidated")) and not cint(doc.get("is_return"))


def _phan_loai(doc):
    """{mã: {co, co_truoc, truoc, sau}} — dòng của các mã đã bật lô (còn đang có lô) trong chứng từ trừ kho:
    co / co_truoc = đã gắn lô (batch / bundle), ghi sổ từ / trước lúc bật lô; truoc / sau = không lô, ghi sổ trước / từ
    lúc bật lô. Hoá đơn gộp từ POS: giờ của từng phiếu POS."""
    if doc.doctype not in KIEU_BAN:
        return {}
    if doc.doctype == "Sales Invoice" and not cint(doc.get("update_stock")):
        return {}
    moc = moc_bat_lo()
    dong = [r for r in doc.get("items") or [] if r.get("item_code") in moc]
    if not dong:
        return {}
    luc = _luc(doc)
    pos = {}
    if cint(doc.get("is_consolidated")):
        ten = list({r.get("pos_invoice") for r in dong if r.get("pos_invoice")})
        if ten:
            pos = {p.name: _luc(p) for p in frappe.get_all("POS Invoice", filters={"name": ("in", ten)},
                                                             fields=["name", "posting_date", "posting_time"])}
    co_lo = {i: cint(frappe.db.get_value("Item", i, "has_batch_no")) for i in {r.get("item_code") for r in dong}}
    ra = {}
    for r in dong:
        i = r.get("item_code")
        if not co_lo[i]:
            continue
        x = ra.setdefault(i, {"co": [], "co_truoc": [], "truoc": [], "sau": []})
        truoc = (pos.get(r.get("pos_invoice")) or luc) < moc[i]["luc"]
        if r.get("batch_no") or r.get("serial_and_batch_bundle"):
            x["co_truoc" if truoc else "co"].append(r)
        else:
            x["truoc" if truoc else "sau"].append(r)
    return ra


def ma_tam_tat_lo(doc, pl=None):
    """Mã cần tạm tắt lô lúc gửi / huỷ chứng từ: mọi dòng của mã KHÔNG lô và ghi sổ trước lúc bật lô. Mã có dòng đã gắn
    lô thì để nguyên (tắt lô là dòng đó hỏng)."""
    pl = _phan_loai(doc) if pl is None else pl
    return {i for i, x in pl.items() if x["truoc"] and not (x["co"] or x["co_truoc"] or x["sau"])}


def _so_ton(r):
    """Số của dòng theo đơn vị tồn kho."""
    return flt(r.get("stock_qty")) or flt(r.get("qty")) * (flt(r.get("conversion_factor")) or 1)


def _lo_cua_dong(r):
    """[(lô, số)] dòng đã gắn lô sẽ lấy — từ bundle (dòng xuất mang số âm) hoặc ô batch_no."""
    if r.get("serial_and_batch_bundle"):
        return [(e.batch_no, abs(flt(e.qty))) for e in frappe.get_all(
            "Serial and Batch Entry", filters={"parent": r.get("serial_and_batch_bundle")},
            fields=["batch_no", "qty"]) if e.batch_no]
    return [(r.get("batch_no"), _so_ton(r))] if r.get("batch_no") else []


def _gan_lo(doc, pl):
    """Hoá đơn gộp từ POS: gán lô cho dòng KHÔNG lô của mã không tắt lô được (xem đầu tệp). Mỗi dòng một lô đủ số cả
    dòng: lô tồn cũ trước, rồi HSD sớm nhất — bỏ lô đang thu hồi, lô hết hạn ở ngày ghi sổ; tồn của lô lấy số nhỏ hơn
    giữa lúc ghi sổ hoá đơn và hiện tại, trừ phần các dòng khác trong hoá đơn đã lấy. Dòng không gán được → chặn, nói
    lý do."""
    from sx.api.kiemke import so_vn
    from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import _so_lo, ma_lo_ton_cu

    moc = moc_bat_lo()
    luc, ngay = _luc(doc), getdate(doc.get("posting_date"))
    loi = []
    for i in sorted(pl):
        x = pl[i]
        dong = sorted(x["truoc"] + x["sau"], key=lambda r: cint(r.get("idx")))
        if not dong:
            continue
        lo_cu = moc[i].get("lo_cu") or ma_lo_ton_cu(i)
        truoc = {id(r) for r in x["truoc"]}
        con = {}
        for w in {r.get("warehouse") for r in dong + x["co"]}:
            nay = {r.b: flt(r.q) for r in _so_lo(w, [i]) if r.b and r.item == i}
            con[w] = {r.b: min(flt(r.q), nay.get(r.b, 0.0)) for r in _so_lo(w, [i], luc) if r.b and r.item == i}
        for r in x["co"]:
            for b, q in _lo_cua_dong(r):
                con[r.get("warehouse")][b] = con[r.get("warehouse")].get(b, 0.0) - q
        for r in dong:
            w, can = r.get("warehouse"), _so_ton(r)
            if can <= EPS:
                continue
            nhan = _("Dòng {0}: {1} (phiếu POS {2}, kho {3})").format(
                r.get("idx"), r.get("item_name") or i, r.get("pos_invoice") or "—", w)
            if id(r) in truoc and w == moc[i]["kho"]:
                loi.append(nhan + _(" — lập trước lúc kiểm kê {0} bật lô, bán ở chính kho đã kiểm kê: số đếm đã trừ "
                                    "phần này, gán lô là trừ hai lần.").format(moc[i]["phieu"]))
                continue
            chon = _lay_lo(i, [(b, q) for b, q in con[w].items() if q >= can - EPS], can, lo_cu, ngay)
            if not chon:
                loi.append(nhan + _(" — không lô nào ở kho đủ {0} (bỏ lô thu hồi, lô hết hạn).").format(so_vn(can)))
                continue
            r.batch_no, r.use_serial_batch_fields = chon[0]["batch"], 1
            con[w][r.batch_no] -= can
    if loi:
        frappe.throw(_("Hoá đơn gộp từ POS — chưa gán được lô cho mã đã bật quản lý lô:") + "<br>" + "<br>".join(
            f"• {x}" for x in loi) + "<br><br>" + _(
            "Kho đã kiểm kê: huỷ lần đóng ca này, huỷ các phiếu POS lập SAU lúc bật lô của mã đó (lập lại sau), đóng "
            "ca lại — phiếu lập trước lúc bật lô sẽ ghi không lô. Thiếu lô: kiểm tra tồn lô ở kho rồi đóng ca lại."),
            title=_("Không gán được lô"))


def _dat_lo(item, co):
    from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import xoa_cache_ma

    frappe.db.set_value("Item", item, "has_batch_no", cint(co), update_modified=False)
    xoa_cache_ma(item)


def _bo_lo(r):
    """D199: bỏ lô khỏi dòng ghi sổ trước lúc bật lô — ô batch_no, gói lô nháp (xoá, như ERPNext bỏ lô khỏi dòng nháp).
    Gói lô đã gửi thì để nguyên (trả None). Trả các lô đã bỏ."""
    sb = r.get("serial_and_batch_bundle")
    co_goi = bool(sb) and bool(frappe.db.exists("Serial and Batch Bundle", sb))
    if co_goi and cint(frappe.db.get_value("Serial and Batch Bundle", sb, "docstatus")) != 0:
        return None
    lo = [b for b, _q in _lo_cua_dong(r)] if co_goi else []
    if r.get("batch_no") and r.batch_no not in lo:
        lo.append(r.batch_no)
    r.batch_no, r.serial_and_batch_bundle, r.use_serial_batch_fields = None, None, 0
    if co_goi:
        frappe.delete_doc("Serial and Batch Bundle", sb, ignore_permissions=True, force=True)
    return lo


def tam_tat_lo(doc, method=None):
    """before_submit / before_cancel của Sales Invoice, Delivery Note: chứng từ lập trước lúc mã bật lô ghi sổ KHÔNG lô
    — tạm tắt lô của các mã đó (bat_lai_lo bật lại ngay sau, cùng giao dịch). Lúc gửi: dòng ghi sổ trước lúc bật lô mà
    mang lô thì bỏ lô (D199); hoá đơn gộp từ POS: gán lô cho dòng không lô của các mã còn lại (_gan_lo)."""
    pl = _phan_loai(doc)
    bo = []
    if cint(doc.get("docstatus")) == 1:
        for i, x in pl.items():
            giu = []
            for r in x["co_truoc"]:
                lo = _bo_lo(r)
                if lo is None:
                    giu.append(r)
                    continue
                x["truoc"].append(r)
                bo.append(_("Dòng {0}: {1} — lô {2}").format(r.get("idx"), r.get("item_name") or i,
                                                              ", ".join(lo) or "—"))
            x["co_truoc"] = giu
    if bo:
        ngay = getdate(doc.get("posting_date")).strftime("%d/%m/%Y")
        frappe.msgprint(_("Chứng từ ghi sổ ngày {0}, trước lúc kiểm kê bật quản lý lô cho mã — lô lúc đó chưa có hàng. "
                          "Đã bỏ lô, ghi KHÔNG lô như lúc lập:").format(ngay) + "<br>" + "<br>".join(
            f"• {x}" for x in bo), title=_("Bỏ lô ở chứng từ cũ"), indicator="orange")
    ma = sorted(ma_tam_tat_lo(doc, pl))
    if cint(doc.get("docstatus")) == 1 and _gop_pos(doc):
        _gan_lo(doc, {i: x for i, x in pl.items() if i not in ma})
    doc.flags.sx_tam_tat_lo = ma
    for i in ma:
        _dat_lo(i, 0)


def bat_lai_lo(doc, method=None):
    """on_submit / on_cancel: bật lại lô cho các mã tam_tat_lo đã tắt."""
    for i in getattr(doc.flags, "sx_tam_tat_lo", None) or []:
        _dat_lo(i, 1)
    doc.flags.sx_tam_tat_lo = []


# ─────────────────────────────────────────── dọn phần không lô còn lại ──


def _chung_tu_gay_ra(item, kho, m):
    """Chứng từ ghi sổ phần không lô SAU lúc bật lô (trừ chính các phiếu của lần chốt bật lô) — để quản lý soát."""
    ra = []
    for s in frappe.get_all("Stock Ledger Entry", filters={
            "item_code": item, "warehouse": kho, "creation": (">", m["luc"]),
            "serial_and_batch_bundle": ("is", "not set"), "batch_no": ("is", "not set")},
            fields=["voucher_type", "voucher_no", "is_cancelled"], order_by="creation"):
        if s.voucher_no in m["se"]:
            continue
        t = f"{s.voucher_type} {s.voucher_no}" + (_(" (huỷ)") if cint(s.is_cancelled) else "")
        if t not in ra:
            ra.append(t)
    return ra


def _lay_lo(item, lots, can, lo_cu, ngay=None):
    """Lấy `can` từ các lô của mã ở một kho: lô tồn cũ trước, rồi HSD sớm nhất (bỏ lô đang thu hồi; có `ngay` thì bỏ cả
    lô hết hạn trước ngày đó — ERPNext chặn bán lô hết hạn). [{batch, so}]."""
    ten = [b for b, _q in lots]
    info = {b.name: b for b in frappe.get_all(
        "Batch", filters={"name": ("in", ten or [""])}, fields=["name", "expiry_date", "custom_thu_hoi"])}
    thu_tu = sorted(lots, key=lambda x: (x[0] != lo_cu, str((info.get(x[0]) or {}).get("expiry_date") or "9999"), x[0]))
    ra = []
    for b, q in thu_tu:
        if can <= EPS:
            break
        hsd = (info.get(b) or {}).get("expiry_date")
        if cint((info.get(b) or {}).get("custom_thu_hoi")) or (ngay and hsd and getdate(hsd) < getdate(ngay)):
            continue
        lay = min(q, can)
        ra.append({"batch": b, "so": flt(lay, 6)})
        can -= lay
    return ra


def _dong_du():
    """[{item, ten, kho, so, cach, lay, vao, thieu, gia, gia_tri, ct}] — phần KHÔNG LÔ khác 0 hiện tại của các mã đã bật
    lô, mỗi (mã, kho) một dòng. cach: "dieu_chinh" (kho đã kiểm kê) / "doi_lo" (kho khác). Bỏ kho của công ty khác —
    phiếu kho của công ty này không ghi vào đó được."""
    from sx.api.mfg import gia_von_hien
    from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import _so_lo, ma_lo_ton_cu
    from sx.utils import get_settings

    cty = get_settings().get("cong_ty")
    moc = moc_bat_lo()
    items = [i for i in moc if cint(frappe.db.get_value("Item", i, "has_batch_no"))]
    if not items:
        return []
    khos = sorted({b.warehouse for b in frappe.get_all("Bin", filters={"item_code": ("in", items)},
                                                        fields=["warehouse"]) if b.warehouse}
                  | {moc[i]["kho"] for i in items if moc[i]["kho"]})
    ten = {i.name: i.item_name for i in frappe.get_all("Item", filters={"name": ("in", items)},
                                                        fields=["name", "item_name"])}
    ra = []
    for w in khos:
        if cty and (frappe.db.get_value("Warehouse", w, "company") or cty) != cty:
            continue
        rows = _so_lo(w, items)
        lots = {}
        for r in rows:
            if r.b and flt(r.q) > EPS:
                lots.setdefault(r.item, []).append((r.b, flt(r.q)))
        for r in rows:
            q = flt(r.q, 6)
            if r.b or abs(q) <= EPS:
                continue
            i, m = r.item, moc[r.item]
            x = {"item": i, "ten": ten.get(i) or i, "kho": w, "so": q,
                 "cach": "dieu_chinh" if w == m["kho"] else "doi_lo", "lay": [], "vao": None, "thieu": 0.0,
                 "gia": flt(gia_von_hien(i, w)), "ct": _chung_tu_gay_ra(i, w, m)}
            if x["cach"] == "doi_lo":
                lo_cu = m.get("lo_cu") or ma_lo_ton_cu(i)
                if q < 0:
                    x["lay"] = _lay_lo(i, lots.get(i, []), -q, lo_cu)
                    x["thieu"] = flt(-q - sum(y["so"] for y in x["lay"]), 6)
                else:
                    x["vao"] = lo_cu
            x["gia_tri"] = flt(abs(q) * x["gia"], 2)
            ra.append(x)
    return sorted(ra, key=lambda x: (x["ten"], x["kho"]))


def _lan_gan_day(n=5):
    ra = {}
    for se in frappe.get_all("Stock Entry", filters={"docstatus": 1, "remarks": ("like", f"{GHI_CHU}%")},
                             fields=["name", "remarks", "posting_date"], order_by="creation desc", limit=200):
        m = LAN.search(se.remarks or "")
        if m:
            ra.setdefault(m.group(1), {"lan": m.group(1), "ngay": str(se.posting_date or "")[:10], "phieu": []})[
                "phieu"].append(se.name)
    return sorted(ra.values(), key=lambda g: g["lan"], reverse=True)[:n]


@frappe.whitelist()
def ds_du():
    """Xem trước: phần không lô còn lại của các mã đã bật lô, cách xử lý từng dòng."""
    from sx.api.kiemke import CARD, _la_quan_ly
    from sx.config.roles import guard_card

    guard_card(CARD)
    dong = _dong_du()
    return {"dong": dong, "duoc_don": _la_quan_ly(), "lan_truoc": _lan_gan_day(),
            "tong": {"so_dong": len(dong), "so_ma": len({x["item"] for x in dong}),
                     "dieu_chinh": flt(sum(x["gia_tri"] for x in dong if x["cach"] == "dieu_chinh"), 2)}}


@frappe.whitelist()
def don_du():
    """Dọn: mỗi dòng về 0 theo cách đã nói (tính lại ngay lúc dọn). Chỉ quản lý — có bút toán điều chỉnh kho."""
    from sx.api.kiemke import CARD, _la_quan_ly
    from sx.api.mfg import loai_phieu_kho, tao_batch
    from sx.config.roles import guard_card
    from sx.utils import get_settings

    guard_card(CARD)
    if not _la_quan_ly():
        frappe.throw(_("Chỉ quản lý dọn tồn không lô — có bút toán điều chỉnh kho."), frappe.PermissionError)
    dong = _dong_du()
    if not dong:
        frappe.throw(_("Không còn tồn không lô nào của mã đã bật lô."))
    lan = now_datetime().strftime("DL-%d%m%y-%H%M%S")
    cong_ty = get_settings().cong_ty
    phieu, giu = [], []

    def gia(x):
        return {"basic_rate": x["gia"]} if x["gia"] > 0 else {"allow_zero_valuation_rate": 1}

    def ghi(purpose, ds, viec):
        if not ds:
            return
        se = frappe.new_doc("Stock Entry")
        se.purpose = purpose
        se.stock_entry_type = loai_phieu_kho(purpose)
        se.company = cong_ty
        se.remarks = _("{0} [{1}]: {2} — phần không lô do chứng từ lập trước lúc bật lô mà ghi sổ / huỷ sau đó."
                       ).format(GHI_CHU, lan, viec)
        for d in ds:
            se.append("items", d)
        se.flags.ignore_permissions = True
        se.insert()
        se.submit()
        giu.append(se)            # giữ tới hết request — id phiếu không bị phiếu sau dùng lại (xoa_cache_ma)
        phieu.append(se.name)

    # 1. Phần KHÔNG lô (mã tạm tắt lô, cùng giao dịch): âm → nhập bù (kho khác: đúng số lấy được từ lô), dương → xuất.
    ma = sorted({x["item"] for x in dong})
    for i in ma:
        _dat_lo(i, 0)
    def bu(x):                    # số nhập bù phần không lô âm: điều chỉnh đủ số; đổi với lô thì đúng số lấy được từ lô
        return flt(-x["so"] if x["cach"] == "dieu_chinh" else sum(y["so"] for y in x["lay"]), 6)

    ghi("Material Receipt", [dict({"item_code": x["item"], "t_warehouse": x["kho"], "qty": bu(x)}, **gia(x))
                             for x in dong if x["so"] < 0 and bu(x) > EPS], _("nhập bù phần không lô âm"))
    ghi("Material Issue", [dict({"item_code": x["item"], "s_warehouse": x["kho"], "qty": x["so"]},
                                **({} if x["gia"] > 0 else {"allow_zero_valuation_rate": 1}))
                           for x in dong if x["so"] > 0], _("xuất phần không lô dương"))
    for i in ma:
        _dat_lo(i, 1)

    # 2. Kho khác — đổi với lô: phần đã bán / xuất trước lúc bật lô ra khỏi lô; phần thừa vào lô tồn cũ.
    vao = [x for x in dong if x["cach"] == "doi_lo" and x["so"] > 0]
    for x in vao:
        if not frappe.db.exists("Batch", x["vao"]):
            tao_batch(x["item"], x["vao"])
            frappe.db.set_value("Batch", x["vao"], "description", _(
                "Tồn KHÔNG LÔ chưa rõ HSD (dọn sau lúc bật lô — {0}).").format(lan), update_modified=False)
        if not frappe.db.get_value("Batch", x["vao"], "custom_kiem_ke"):
            frappe.db.set_value("Batch", x["vao"], "custom_kiem_ke", moc_bat_lo()[x["item"]]["phieu"],
                                update_modified=False)
    ghi("Material Issue", [dict({"item_code": x["item"], "s_warehouse": x["kho"], "qty": y["so"],
                                 "use_serial_batch_fields": 1, "batch_no": y["batch"]},
                                **({} if x["gia"] > 0 else {"allow_zero_valuation_rate": 1}))
                           for x in dong if x["cach"] == "doi_lo" and x["so"] < 0 for y in x["lay"]],
        _("xuất khỏi lô phần đã bán / xuất trước lúc bật lô"))
    ghi("Material Receipt", [dict({"item_code": x["item"], "t_warehouse": x["kho"], "qty": x["so"],
                                   "use_serial_batch_fields": 1, "batch_no": x["vao"]}, **gia(x)) for x in vao],
        _("nhập phần không lô dương vào lô tồn cũ"))
    return {"lan": lan, "phieu": phieu, "so_dong": len(dong), "so_ma": len(ma),
            "con_thieu": [{"ten": x["ten"], "kho": x["kho"], "so": x["thieu"]} for x in dong if x["thieu"] > EPS]}


@frappe.whitelist()
def bien_ban(phieu):
    """HTML danh sách dọn tồn không lô để in cho kế toán — đọc lại từ chính các phiếu đã ghi."""
    from sx.api.kiemke import CARD, so_vn
    from sx.config.roles import guard_card
    from sx.utils import get_settings

    guard_card(CARD)
    ds = json.loads(phieu) if isinstance(phieu, str) and phieu.strip().startswith("[") else (
        phieu if isinstance(phieu, list) else [x.strip() for x in str(phieu or "").split(",") if x.strip()])
    if not ds:
        frappe.throw(_("Chưa chọn phiếu nào."))
    se = []
    for n in ds:
        d = frappe.get_doc("Stock Entry", n) if frappe.db.exists("Stock Entry", n) else None
        if not d or not str(d.remarks or "").startswith(GHI_CHU):
            frappe.throw(_("{0} không phải phiếu dọn tồn không lô.").format(n))
        se.append(d)
    ten = {i.name: i.item_name for i in frappe.get_all(
        "Item", filters={"name": ("in", list({r.get("item_code") for d in se for r in d.items}) or [""])},
        fields=["name", "item_name"])}
    dong = []
    for d in se:
        for r in d.items:
            vao = bool(r.get("t_warehouse"))
            g = flt(r.get("basic_rate"))
            dong.append({"kho": r.get("t_warehouse") or r.get("s_warehouse"),
                         "ten": ten.get(r.get("item_code")) or r.get("item_code"),
                         "lo": r.get("batch_no"), "so": flt(r.get("qty"), 6) * (1 if vao else -1),
                         "gia_tri": flt(flt(r.get("qty")) * g, 2) if vao else None, "phieu": d.name,
                         "viec": (d.remarks or "").split("]: ", 1)[-1].split(" — ")[0]})
    dong.sort(key=lambda x: (x["kho"] or "", x["ten"], x["lo"] or ""))
    m = LAN.search(se[0].remarks or "")
    return frappe.render_template("sx/sx/doctype/sx_kiem_ke/don_khong_lo.html", {
        "dong": dong, "se": [d.name for d in se], "lan": m.group(1) if m else "",
        "ngay": getdate(se[0].posting_date).strftime("%d/%m/%Y") if se[0].get("posting_date") else "",
        "cong_ty": get_settings().get("cong_ty") or "", "so": so_vn,
    })
