"""Phiếu kiểm kê kho thành phẩm theo HSD (D154; D188: chốt = đặt lại toàn kho).

ĐANG ĐẾM (nháp): thủ kho / quản lý ghi số đếm theo (mã, HSD in trên hộp) ở màn Nhập kho → Kiểm kê. Mã
nào đã có dòng là mã đã đếm; dòng không HSD số 0 = đã đếm, không còn hộp nào.

CHỐT (submit — thủ kho / quản lý, D155): ĐẶT LẠI TOÀN KHO theo số đếm (D188) — số đếm thay tồn của từng mã; thành
phẩm có tồn trong kho mà không đếm thì số đếm là 0 (về 0); sau chốt mỗi (mã, HSD) đúng một lô chuẩn …-HSDddmmyy (lô
cũ, kể cả lô có HSD mà không chuẩn, gộp về lô chuẩn). sx/kiem_ke.py tính kế hoạch từng lô, ở đây kiểm rồi sinh
chứng từ kho:
  · mỗi mã có hàng phải chuyển lô: một Stock Entry Repack riêng — tiêu lô cũ, ra lô theo HSD. Repack chia
    giá vốn đầu vào cho đầu ra, nên một phiếu một mã (gộp nhiều mã là trộn giá vốn của mã này sang mã kia).
    Truy xuất ngược từ lô HSD đi qua chính phiếu này về lô cũ, rồi về ngày sản xuất.
  · một Material Issue cho phần THIẾU, một Material Receipt cho phần THỪA (kèm bù lô âm về 0) — chênh lệch
    kiểm kê vào tài khoản điều chỉnh kho như mọi phiếu kiểm kê.
  · hàng ĐÃ HẾT HẠN (HSD trước ngày chốt) mà phải chuyển lô: ERPNext không cho Repack đụng lô hết hạn, nên phần
    đó đi đường xuất + nhập (sx/kiem_ke.chia_chung_tu). Phiếu NHẬP vào lô hết hạn ERPNext cũng chặn
    (StockController.validate_serialized_batch: "The batch … has already expired") — D190: tạm bỏ HSD của lô đó
    lúc ghi phiếu nhập, ghi xong trả lại ngay (tam_bo_hsd / tra_hsd).
Lô theo HSD nhận hàng được đánh dấu custom_kiem_ke = hàng TỒN CŨ, bán không cần phiếu xuất xưởng — TRỪ lô của hàng
làm từ ngày áp dụng BM.08.04 mà chưa duyệt (chua_duyet_xx): D188 không chặn chốt nữa (đặt lại kho phải chốt được),
lô đó vẫn vào kho nhưng không đánh dấu — bán phải có BM.08.04 duyệt; QC thấy nó ở màn Xuất xưởng (Lô chờ kiểm).

MÃ CHƯA QUẢN LÝ LÔ (D189): mã tắt "Has Batch No" mà đã có chứng từ kho — ERPNext cấm bật lại (Item.cant_change) — và
mã có lô mà còn tồn KHÔNG gắn lô (dữ liệu cũ) vẫn đếm theo HSD như mã khác. Chốt CHUYỂN mã sang quản lý lô: tồn không
lô về 0 (phiếu xuất / nhập không lô, ghi lúc mã còn tắt lô), bật lô thẳng trong DB (tồn không lô vừa về 0 nên không còn
hàng nào kẹt), rồi số đếm vào lô theo HSD ở phiếu nhập (giá vốn đang chạy của mã). Cờ lô là của MÃ, áp mọi kho (D191):
tồn không lô của mã ở KHO KHÁC (cửa hàng, xưởng) cũng xử lý luôn — kho dương chuyển nguyên số vào lô "tồn cũ" (chưa rõ
HSD) ngay tại kho đó, kho âm đưa về 0; chỉ kho của công ty khác mới chặn. Mỗi lần đổi cờ ghi vào ds_se ({"dt": "Item"})
để huỷ phiếu trả lại như cũ.

Chặn chốt khi mã đã đếm có chứng từ kho SAU lúc đếm (bán, nhập, huỷ phiếu…): số đếm không còn khớp sổ — đếm
lại mã đó; mã chưa đếm (sắp về 0) có chứng từ SAU lúc bắt đầu kiểm kê → phải đếm (hoặc bấm Không còn). Huỷ
phiếu đã chốt (Desk) = huỷ các chứng từ kho theo thứ tự ngược (trả cờ quản lý lô đã đổi).

BÁN THÀNH PHẨM (D155, loai = "Bán thành phẩm", Kho BTP / Kho xưởng): hàng rời tính kg, lô theo ngày làm / lô
rang, không có HSD — CÂN TỪNG LÔ. Mỗi (mã, lô) một dòng; lô đã cân thì số cân thay số sổ của lô đó, lô chưa cân
giữ nguyên (sx/kiem_ke.lap_ke_hoach_lo). Chỉ sinh Material Issue (thiếu) / Material Receipt (thừa, bù lô âm) —
không chuyển lô. Chứng từ sau lúc cân xét theo TỪNG LÔ: xưởng vẫn chạy lô khác thì không chặn lô đã cân.
"""

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime, getdate, now_datetime, nowdate

from sx.kiem_ke import chia_chung_tu, co_thay_doi, lap_ke_hoach, lap_ke_hoach_lo, theo_lo

DANG_DEM, DA_CHOT, DA_HUY = "Đang đếm", "Đã chốt", "Đã huỷ"
TP, BTP = "Thành phẩm", "Bán thành phẩm"

VIEC = {"chuyen_di": "chuyển {so} sang lô HSD {hsd}", "nhan": "nhận {so} từ lô {lo}",
        "nhan_kl": "nhận {so} từ tồn không lô",
        "thieu": "xuất thiếu {so}", "thua": "nhập thừa {so}", "bu_am": "bù lô âm {so}",
        "thu_hoi": "đang thu hồi — không kiểm ({so})"}


def _vn(d):
    return getdate(d).strftime("%d/%m/%y") if d else ""


def _so(x):
    x = flt(x, 3)
    return str(int(x)) if x == int(x) else str(x)


def mo_ta_viec(viec):
    """[(loại, hsd | lô | None, số)] → câu ngắn cho biên bản. Không có việc gì = khớp sổ."""
    if not viec:
        return _("khớp sổ — giữ nguyên")
    ra = []
    for loai, x, so in viec:
        if loai == "nhan" and not x:
            loai = "nhan_kl"
        ra.append(VIEC[loai].format(so=_so(so), hsd=_vn(x) if loai == "chuyen_di" else "", lo=x or ""))
    return "; ".join(ra)


def _so_lo(kho, items):
    """[{item, b, q}] — tồn theo (mã, lô) tại một kho, từ sổ cái kho.

    ERPNext v15+ ghi lô trong Serial and Batch Bundle, SLE có thể để trống batch_no — gom cả hai đường như
    sx.utils.ton_cac_lo, số lượng lấy theo dòng của đúng lô trong bundle (dòng xuất mang số âm)."""
    return frappe.db.sql(
        """select sle.item_code as item, coalesce(e.batch_no, sle.batch_no) as b,
                  sum(coalesce(e.qty, sle.actual_qty)) as q
             from `tabStock Ledger Entry` sle
             left join `tabSerial and Batch Entry` e
               on e.parent = sle.serial_and_batch_bundle
            where sle.is_cancelled = 0 and sle.warehouse = %(kho)s and sle.item_code in %(items)s
            group by sle.item_code, coalesce(e.batch_no, sle.batch_no)""",
        {"kho": kho, "items": tuple(items)}, as_dict=True)


def ton_lo(kho, items):
    """{item: [{batch, qty, hsd, ngay, thu_hoi, chuan}]} — tồn từng lô của các mã tại MỘT kho. `ngay` = NSX
    của lô (không có thì ngày tạo lô). Mã không quản lý lô: batch None."""
    from sx.utils import la_lo_hsd

    items = [i for i in dict.fromkeys(items or []) if i]
    if not items or not kho:
        return {}
    rows = _so_lo(kho, items)
    lo = list({r.b for r in rows if r.b})
    info = {}
    if lo:
        truong = ["name", "expiry_date", "manufacturing_date", "creation"]
        try:
            ds = frappe.get_all("Batch", filters={"name": ("in", lo)}, fields=truong + ["custom_thu_hoi"])
        except Exception:           # chưa migrate W26
            ds = frappe.get_all("Batch", filters={"name": ("in", lo)}, fields=truong)
        info = {b.name: b for b in ds}
    ra = {}
    for r in rows:
        q = flt(r.q, 6)
        if abs(q) < 1e-9:
            continue
        b = info.get(r.b) if r.b else None
        ra.setdefault(r.item, []).append({
            "batch": r.b, "qty": q,
            "hsd": str(getdate(b.expiry_date)) if b and b.get("expiry_date") else None,
            "ngay": str(getdate(b.get("manufacturing_date") or b.get("creation"))) if b else None,
            "thu_hoi": bool(b and cint(b.get("custom_thu_hoi"))),
            "chuan": la_lo_hsd(r.b),
        })
    return ra


def ton_kho_khac(items, kho):
    """{item: [(kho, số)]} — tồn của các mã ở mọi kho KHÁC `kho` (Bin), bỏ số ~0. Cờ lô là của mã, áp mọi kho: bật lô
    cho mã thì tồn không lô ở các kho này cũng phải vào lô (D191), không thì phiếu nào xuất / bán phần đó cũng đòi lô."""
    items = [i for i in dict.fromkeys(items or []) if i]
    if not items:
        return {}
    ra = {}
    for b in frappe.get_all("Bin", filters={"item_code": ("in", items), "warehouse": ("!=", kho)},
                            fields=["item_code", "warehouse", "actual_qty"]):
        if abs(flt(b.actual_qty)) > 1e-9:
            ra.setdefault(b.item_code, []).append((b.warehouse, flt(b.actual_qty, 6)))
    return {i: sorted(v) for i, v in ra.items()}


def cong_ty_kho(khos):
    """{kho: công ty} của các kho."""
    khos = [k for k in dict.fromkeys(khos or []) if k]
    if not khos:
        return {}
    return {w.name: w.company for w in frappe.get_all("Warehouse", filters={"name": ("in", khos)},
                                                       fields=["name", "company"])}


def ma_lo_ton_cu(item):
    """D191: lô "tồn cũ — chưa rõ HSD" của mã: hàng KHÔNG LÔ ở các kho khác (cửa hàng, xưởng) lúc mã bật lô vào lô
    này — một lô mỗi mã, dùng chung mọi kho (lô là của mã, tồn tính theo từng kho)."""
    from sx.utils import _unique_suffix, prefix_lo

    return _unique_suffix(f"{prefix_lo(item)}-TONCU", lambda ma: frappe.db.exists("Batch", ma)
                          and frappe.db.get_value("Batch", ma, "item") != item)


def tam_bo_hsd(dong):
    """D190: ERPNext không cho NHẬP vào lô đã hết hạn (StockController.validate_serialized_batch — mọi phiếu trừ
    xuất / chuyển kho), kể cả phiếu nhập điều chỉnh. Hàng hết hạn vẫn nằm trong kho, vào sổ thì phải nhập được — tạm bỏ
    HSD của các lô đó trong lúc ghi phiếu; nơi gọi trả lại ngay sau bằng tra_hsd (cùng giao dịch: lỗi giữa chừng thì
    cuộn lại cả). `dong` = các dòng phiếu kho (batch_no). Trả {lô: HSD cũ}."""
    hom_nay = getdate(nowdate())
    ra = {}
    for d in dong:
        b = d.get("batch_no")
        if not b or b in ra:
            continue
        h = frappe.db.get_value("Batch", b, "expiry_date")
        if h and getdate(h) < hom_nay:
            ra[b] = h
    for b in ra:
        frappe.db.set_value("Batch", b, "expiry_date", None, update_modified=False)
    return ra


def tra_hsd(het):
    for b, h in (het or {}).items():
        frappe.db.set_value("Batch", b, "expiry_date", h, update_modified=False)


def xoa_cache_ma(item):
    """Bỏ cache của Item sau khi đổi has_batch_no thẳng trong DB: cache tài liệu (ERPNext đọc cờ lô qua
    get_cached_value lúc ghi sổ kho) và cache theo request (StockController.is_serial_batch_item nhớ theo (phiếu, mã),
    khoá theo id phiếu — phiếu sau có thể trùng id phiếu trước)."""
    try:
        frappe.clear_document_cache("Item", item)
    except Exception:
        pass
    rc = getattr(getattr(frappe, "local", None), "request_cache", None)
    if rc is not None:
        try:
            rc.clear()
        except Exception:
            pass


class SXKiemKe(Document):
    def la_btp(self):
        return (self.loai or TP) == BTP

    # ─────────────────────────────── nháp ───────────────────────────────
    def validate(self):
        if self.docstatus == 0:
            self.trang_thai = DANG_DEM
        if self.la_btp():
            self._chuan_dong_lo()
        else:
            self._chuan_dong()

    def _chuan_dong_lo(self):
        """BTP: mỗi (mã, lô) một dòng; số ≥ 0 (0 = lô đã hết); lô phải là lô của chính mã đó."""
        giu = [r for r in self.dong or [] if r.item]
        lo = {b.name: b.item for b in frappe.get_all(
            "Batch", filters={"name": ("in", [r.batch for r in giu if r.batch] or [""])}, fields=["name", "item"])}
        thay = set()
        for r in giu:
            ten = r.ten or r.item
            if flt(r.so_dem) < 0:
                frappe.throw(_("Dòng {0} ({1}): số cân không được âm.").format(r.idx, ten))
            r.hsd = None
            if r.batch and lo.get(r.batch) != r.item:
                frappe.throw(_("Lô {0} không phải lô của {1}.").format(r.batch, ten))
            k = (r.item, r.batch or None)
            if k in thay:
                frappe.throw(_("{0} có hai dòng cùng lô {1} — gộp lại thành một dòng.").format(
                    ten, r.batch or _("(không lô)")))
            thay.add(k)
        self.set("dong", giu)

    def _chuan_dong(self):
        """Mỗi (mã, HSD) một dòng; số ≥ 0; số > 0 phải có HSD; mã đã có dòng số > 0 thì bỏ dòng "không còn"."""
        co_so = {r.item for r in self.dong or [] if flt(r.so_dem) > 0}
        thay, giu = set(), []
        for r in self.dong or []:
            if not r.item:
                continue
            so = flt(r.so_dem)
            ten = r.ten or r.item
            if so < 0:
                frappe.throw(_("Dòng {0} ({1}): số đếm không được âm.").format(r.idx, ten))
            if so > 0 and not r.hsd:
                frappe.throw(_("Dòng {0} ({1}): có số thì phải có HSD in trên hộp.").format(r.idx, ten))
            if so <= 0:
                if r.item in co_so:
                    continue
                r.hsd = None
            k = (r.item, str(getdate(r.hsd)) if r.hsd else None)
            if k in thay:
                frappe.throw(_("{0} có hai dòng cùng HSD {1} — gộp lại thành một dòng.").format(
                    ten, _vn(r.hsd) if r.hsd else _("(không còn hàng)")))
            thay.add(k)
            giu.append(r)
        self.set("dong", giu)

    def dem_theo_ma(self):
        """{item: {hsd: số}} — mã đã đếm. {} = đã đếm, không còn hộp nào."""
        ra = {}
        for r in self.dong or []:
            d = ra.setdefault(r.item, {})
            if r.hsd and flt(r.so_dem) > 0:
                h = str(getdate(r.hsd))
                d[h] = d.get(h, 0.0) + flt(r.so_dem)
        return ra

    def dem_theo_lo(self):
        """BTP: {item: {lô: số cân}} — lô đã cân (lô None = tồn không lô của mã)."""
        ra = {}
        for r in self.dong or []:
            d = ra.setdefault(r.item, {})
            d[r.batch or None] = d.get(r.batch or None, 0.0) + flt(r.so_dem)
        return ra

    # ─────────────────────────────── chốt ───────────────────────────────
    def lap_ke(self):
        """Kế hoạch ({item: kế hoạch}, {(item, hsd): lô nhận}, {item: tên}) — thành phẩm: mọi mã đã đếm + mọi
        thành phẩm có tồn mà chưa đếm (về 0, D188); bán thành phẩm: mã đã cân. Dùng chung cho xem trước (API) và
        chốt — một chỗ tính."""
        from sx.utils import items_tp, ma_lo_hsd, nsx_tu_hsd

        if self.la_btp():
            dem = self.dem_theo_lo()
            items = list(dem)
            ten = {i.name: i.item_name or i.name for i in frappe.get_all(
                "Item", filters={"name": ("in", items or [""])}, fields=["name", "item_name"])}
            self.flags.ten_ma = ten
            self.flags.doi_lo, self.flags.kho_khac, self.flags.kho_cty_khac = {}, {}, {}
            lots = ton_lo(self.kho, items)
            self.flags.lo_thu_hoi = {(i, l["batch"]) for i in items for l in lots.get(i, []) if l["thu_hoi"]}
            return {i: lap_ke_hoach_lo(lots.get(i, []), dem[i]) for i in items}, {}, ten

        dem = self.dem_theo_ma()
        # D188: chốt = ĐẶT LẠI TOÀN KHO — thành phẩm có tồn trong kho (trừ lô thu hồi) mà chưa đếm cũng vào kế
        # hoạch với số đếm 0 (về 0). Hàng không phải thành phẩm để trong kho này thì không đụng.
        tp = [i.name for i in items_tp(["name"])]
        lots = ton_lo(self.kho, list(dict.fromkeys(list(dem) + tp)))
        chua = [i for i in tp if i not in dem and any(
            abs(l["qty"]) > 1e-9 and not l["thu_hoi"] for l in lots.get(i, []))]
        for i in chua:
            dem[i] = {}
        self.flags.chua_dem = set(chua)
        items = list(dem)
        ten = {i.name: i.item_name or i.name for i in frappe.get_all(
            "Item", filters={"name": ("in", items or [""])}, fields=["name", "item_name"])}
        self.flags.ten_ma = ten
        co_lo = {i.name for i in frappe.get_all("Item", filters={"name": ("in", items or [""]), "has_batch_no": 1},
                                                fields=["name"])}
        self.flags.co_lo = co_lo
        # D189: mã tắt lô ("bat") và mã có lô mà còn tồn KHÔNG gắn lô ("le") — chốt chuyển sang quản lý lô: tồn
        # không lô vào kế hoạch như một lô cũ chưa có HSD (chuyển sang lô theo HSD / xuất thiếu / bù âm), on_submit
        # ghi phần đó lúc mã còn tắt lô rồi mới bật. D191: cờ lô là của mã — tồn của mã tắt lô ở kho khác cùng công
        # ty (kho_khac) xử lý luôn lúc bật (on_submit, chia_chung_tu); kho của công ty KHÁC (kho_cty_khac) thì phiếu
        # kho của kiểm kê không ghi sang được — mã đó không bật lô: có số đếm thì kiem_truoc_chot chặn, đếm 0 / chưa
        # đếm thì chỉ về 0 ở kho này, để nguyên không lô.
        from sx.utils import get_settings

        kk = ton_kho_khac([i for i in items if i not in co_lo], self.kho)
        cty, ck = get_settings().get("cong_ty"), cong_ty_kho([w for v in kk.values() for w, _q in v])
        khac = lambda w: bool(cty and ck.get(w) and ck[w] != cty)   # noqa: E731
        self.flags.kho_khac = {i: v for i, v in ((i, [(w, q) for w, q in v if not khac(w)]) for i, v in kk.items()) if v}
        self.flags.kho_cty_khac = {i: v for i, v in ((i, [(w, q) for w, q in v if khac(w)]) for i, v in kk.items()) if v}
        self.flags.doi_lo = {
            i: "le" if i in co_lo else "bat" for i in items
            if (i not in co_lo and not self.flags.kho_cty_khac.get(i))
            or (i in co_lo and any(not l["batch"] and abs(l["qty"]) > 1e-9 for l in lots.get(i, [])))}
        ke = {i: lap_ke_hoach(lots.get(i, []), dem[i], lambda h, i=i: nsx_tu_hsd(i, h)) for i in items}
        ten_lo = {}
        for i, k in ke.items():
            for h in sorted({x["hsd"] for x in k["chuyen"]} | {x["hsd"] for x in k["nhap"]}):
                ten_lo[(i, h)] = ma_lo_hsd(i, h)
        return ke, ten_lo, ten

    def _ten(self, item):
        """Tên mã cho câu báo lỗi: tên trên Item (lap_ke đã tra) > tên trên dòng đếm / bảng lô > mã."""
        t = (getattr(self.flags, "ten_ma", None) or {}).get(item)
        return t or next((r.ten for r in list(self.dong or []) + list(self.lo or []) if r.item == item and r.ten),
                         None) or item

    def kiem_truoc_chot(self, ke):
        """Lỗi chặn chốt: [chuỗi]. Rỗng = chốt được."""
        loi = []
        if not ke:
            return [_("Chưa đếm mã nào.")]
        if self.la_btp():
            return self._kiem_btp(ke)
        # D189: mã tắt lô có số đếm thì chốt phải bật lô (HSD nằm trên lô). D191: tồn ở kho khác cùng công ty xử lý
        # luôn lúc bật; chỉ kho của công ty KHÁC là không ghi sang được — bật lô thì phần đó kẹt.
        kc = getattr(self.flags, "kho_cty_khac", None) or {}
        ket = [i for i, k in ke.items() if k["dem"] > 0 and kc.get(i)]
        if ket:
            loi.append(_("Mã chưa quản lý theo lô — chốt phải bật lô để ghi HSD, nhưng mã còn tồn ở kho của CÔNG TY KHÁC "
                         "(phiếu kho của kiểm kê không ghi sang công ty khác; bật lô thì phần đó kẹt): {0}. Điều chỉnh tồn "
                         "ở kho đó về 0 trước, rồi chốt.").format(
                "; ".join(f"{self._ten(i)} — " + ", ".join(f"{w}: {_so(q)}" for w, q in kc[i]) for i in ket)))
        loi += self._giao_dich_sau_dem(list(ke))
        return loi

    def _kiem_btp(self, ke):
        """Lỗi chặn chốt của phiếu BÁN THÀNH PHẨM."""
        loi = []
        co_lo = {i.name for i in frappe.get_all(
            "Item", filters={"name": ("in", list(ke)), "has_batch_no": 1}, fields=["name"])}
        thieu_lo = sorted({r.item for r in self.dong or [] if not r.batch and r.item in co_lo})
        if thieu_lo:
            loi.append(_("Mã quản lý theo lô mà dòng cân không ghi lô — cân theo từng lô: {0}.").format(
                ", ".join(self._ten(i) for i in thieu_lo)))
        thua_lo = sorted({r.item for r in self.dong or [] if r.batch and r.item not in co_lo})
        if thua_lo:
            loi.append(_("Mã không quản lý theo lô mà dòng cân có ghi lô — bỏ lô ở dòng đó: {0}.").format(
                ", ".join(self._ten(i) for i in thua_lo)))
        th = getattr(self.flags, "lo_thu_hoi", None) or set()
        cham = sorted({(r.item, r.batch) for r in self.dong or [] if (r.item, r.batch) in th})
        if cham:
            loi.append(_("Lô đang THU HỒI không kiểm ở đây (để riêng, xử lý theo phiếu thu hồi): {0}.").format(
                ", ".join(f"{self._ten(i)} lô {b}" for i, b in cham)))
        return loi + self._giao_dich_sau_dem(list(ke))

    def _giao_dich_sau_dem(self, items):
        """Có chứng từ kho ở kho này SAU lúc đếm → số đếm không còn khớp sổ. Thành phẩm xét theo MÃ (số đếm thay cả
        mã; mốc = dòng đếm sớm nhất của mã); bán thành phẩm xét theo LÔ (mốc = lúc cân lô đó) — xưởng chạy lô khác
        thì lô đã cân vẫn đúng. Tính chứng từ MỚI (creation sau mốc, chưa huỷ) và chứng từ HUỶ sau mốc — không
        tính SLE chỉ bị repost lại giá (modified đổi mà số không đổi)."""
        lo_rieng = self.la_btp()
        moc = {}
        for r in self.dong or []:
            if r.item in items and r.dem_luc:
                k = (r.item, r.batch or None) if lo_rieng else r.item
                t = get_datetime(r.dem_luc)
                moc[k] = min(moc.get(k, t), t)
        chua = set() if lo_rieng else (getattr(self.flags, "chua_dem", None) or set()) & set(items)
        if chua and self.bat_dau_luc:
            # D188: mã chưa đếm sắp về 0 — mốc là lúc bắt đầu kiểm kê: hàng nhập / trả về sau đó có thể đang nằm
            # trong kho mà không ai đếm, về 0 là xoá mất.
            for i in chua:
                moc.setdefault(i, get_datetime(self.bat_dau_luc))
        if not moc:
            return []
        t0 = min(moc.values())
        ma = sorted({k[0] for k in moc} if lo_rieng else set(moc))
        truong = ["name", "item_code", "voucher_type", "voucher_no", "actual_qty", "creation", "modified",
                  "is_cancelled", "batch_no", "serial_and_batch_bundle"]
        gap = {}
        for f in ("creation", "modified"):
            for s in frappe.get_all("Stock Ledger Entry", filters={
                    "warehouse": self.kho, "item_code": ("in", ma), f: (">", t0)}, fields=truong):
                gap[s.name] = s
        phan = {}                      # SLE → [(lô, số)] — một SLE có thể chạm nhiều lô qua bundle
        if lo_rieng:
            goi = [s.serial_and_batch_bundle for s in gap.values() if s.get("serial_and_batch_bundle")]
            ent = {}
            if goi:
                for e in frappe.get_all("Serial and Batch Entry", filters={"parent": ("in", goi)},
                                        fields=["parent", "batch_no", "qty"]):
                    ent.setdefault(e.parent, []).append((e.batch_no or None, flt(e.qty)))
            for s in gap.values():
                phan[s.name] = ent.get(s.get("serial_and_batch_bundle")) or [(s.get("batch_no") or None,
                                                                              flt(s.actual_qty))]
        sau = {}
        for s in gap.values():
            for b, q in (phan[s.name] if lo_rieng else [(None, flt(s.actual_qty))]):
                k = (s.item_code, b) if lo_rieng else s.item_code
                t = moc.get(k)
                if not t:
                    continue
                moi, huy = get_datetime(s.creation) > t, cint(s.is_cancelled)
                if moi and not huy:
                    anh = q
                elif not moi and huy and get_datetime(s.modified) > t:
                    anh = -q
                else:
                    continue
                g = sau.setdefault(k, {})
                g[(s.voucher_type, s.voucher_no)] = g.get((s.voucher_type, s.voucher_no), 0.0) + anh
        loi = []
        for k, g in sorted(sau.items(), key=lambda x: str(x[0])):
            ct = [f"{vt} {vn} ({'+' if q > 0 else ''}{_so(q)})" for (vt, vn), q in sorted(g.items())
                  if abs(q) > 1e-9]
            if not ct:
                continue
            if lo_rieng:
                loi.append(_("{0} lô {1}: có chứng từ kho sau lúc cân — {2}. Cân lại lô này rồi chốt.").format(
                    self._ten(k[0]), k[1] or _("(không lô)"), ", ".join(ct)))
            elif k in chua:
                loi.append(_("{0}: chưa đếm mà có chứng từ kho sau lúc bắt đầu kiểm kê — {1}. Đếm mã này (hoặc bấm "
                             "KHÔNG CÒN) rồi chốt — chưa đếm thì chốt sẽ đưa về 0.").format(self._ten(k), ", ".join(ct)))
            else:
                loi.append(_("{0}: có chứng từ kho sau lúc đếm — {1}. Bấm ĐẾM LẠI mã này, đếm lại rồi chốt.")
                           .format(self._ten(k), ", ".join(ct)))
        return loi

    def chua_duyet_xx(self, ke):
        """[(item, hsd)] — lô theo HSD nhận hàng ở lần chốt này mà là hàng làm TỪ ngày áp dụng BM.08.04 trở đi,
        chưa có phiếu xuất xưởng duyệt. Lô nhận hàng ở kiểm kê là hàng TỒN CŨ (bán không cần phiếu) — riêng các lô
        này thì không: chốt vẫn đưa hàng vào lô (D188 — đặt lại kho không bị chặn) nhưng KHÔNG đánh dấu tồn cũ,
        bán phải có BM.08.04 duyệt (QC kiểm ở màn Xuất xưởng — Lô chờ kiểm). Chặn BM.08.04 tắt / chưa có ngày
        áp dụng → []."""
        from sx.api import xuatxuong as XXA
        from sx.qc import xuat_xuong as XX
        from sx.utils import get_settings, nsx_tu_hsd

        s = get_settings()
        if not XXA._bat(s):
            return []
        tn = XXA.tu_ngay(s)
        if not tn:
            return []
        cap = []
        for i, k in ke.items():
            for h in sorted({x["hsd"] for x in k["chuyen"]} | {x["hsd"] for x in k["nhap"]}):
                nsx = nsx_tu_hsd(i, h)
                if nsx and getdate(nsx) >= getdate(tn):
                    cap.append((i, h))
        return [(i, str(h)[:10]) for i, h, _p in XX.chua_duyet(cap)] if cap else []

    def before_submit(self):
        if self.trang_thai != DANG_DEM:
            frappe.throw(_("Phiếu kiểm kê {0} không còn ở trạng thái đang đếm.").format(self.name))
        ke, ten_lo, ten = self.lap_ke()
        loi = self.kiem_truoc_chot(ke)
        if loi:
            frappe.throw("<br>".join(loi), title=_("Chưa chốt được kiểm kê"))
        self.flags.ke, self.flags.ten_lo = ke, ten_lo
        self.set("lo", [])
        bat = {i for i, c in (getattr(self.flags, "doi_lo", None) or {}).items() if c == "bat"}
        for i in sorted(ke, key=lambda x: ten.get(x, x)):
            bang = theo_lo(ke[i], lambda h, i=i: ten_lo[(i, h)])
            for b, g in sorted(bang.items(), key=lambda x: (x[1]["hsd"] or "", x[0] or "")):
                viec = mo_ta_viec(g["viec"])
                if not b and i in bat:
                    viec += _("; mã chuyển sang quản lý lô")
                self.append("lo", {"item": i, "ten": ten.get(i, i), "batch": b, "hsd": g["hsd"],
                                   "so_truoc": g["truoc"], "so_sau": g["sau"],
                                   "chenh": flt(g["sau"] - g["truoc"], 6), "viec": viec})
        self.so_ma = len(ke)
        self.tong_so_sach = flt(sum(k["so_sach"] for k in ke.values()), 6)
        self.tong_dem = flt(sum(k["dem"] for k in ke.values()), 6)
        self.tong_lech = flt(self.tong_dem - self.tong_so_sach, 6)
        self.nguoi_chot = frappe.session.user
        self.chot_luc = now_datetime()
        self.trang_thai = DA_CHOT

    def on_submit(self):
        from sx.api.mfg import gia_von_hien, loai_phieu_kho, tao_batch
        from sx.utils import get_settings, nsx_tu_hsd

        ke, ten_lo = getattr(self.flags, "ke", None), getattr(self.flags, "ten_lo", None)
        if ke is None or ten_lo is None:
            ke, ten_lo, _ten = self.lap_ke()
        doi_lo = getattr(self.flags, "doi_lo", None) or {}
        cong_ty = get_settings().cong_ty
        chung_tu = []
        giu = []                      # giữ các phiếu kho tới hết request — id không bị phiếu sau dùng lại (xoa_cache_ma)

        # D191: tồn ở kho khác của mã bật lô — xử lý cùng lúc bật (chia_chung_tu: xuat_kl / nhap_kl / nhap_cu có `kho`).
        kk_bat = {i: v for i, v in (getattr(self.flags, "kho_khac", None) or {}).items() if doi_lo.get(i) == "bat"}
        ct = chia_chung_tu(ke, nowdate(), doi_lo, kk_bat)

        gia = {i: gia_von_hien(i, self.kho) for i, k in ke.items() if co_thay_doi(k)}
        # Giá vốn từng kho khác — lấy TRƯỚC khi xuất, để nhập lại vào lô tồn cũ đúng giá đã xuất.
        gia_kho = {(x["item"], x["kho"]): gia_von_hien(x["item"], x["kho"])
                   for x in ct["nhap_cu"] + ct["nhap_kl"] if x.get("kho")}

        def gia_cua(i, kho=None):
            return gia_kho.get((i, kho), 0) if kho else gia.get(i, 0)

        def zero(i, kho=None):
            return {} if gia_cua(i, kho) > 0 else {"allow_zero_valuation_rate": 1}

        def lo_cua(b):
            return {"use_serial_batch_fields": 1, "batch_no": b} if b else {}

        def vao(i, b, so, kho=None):
            d = {"item_code": i, "qty": so, "t_warehouse": kho or self.kho, **lo_cua(b)}
            g = gia_cua(i, kho)
            d.update({"basic_rate": g} if g > 0 else {"allow_zero_valuation_rate": 1})
            return d

        def phieu(purpose, ghi_chu, dong):
            se = frappe.new_doc("Stock Entry")
            se.purpose = purpose
            se.stock_entry_type = loai_phieu_kho(purpose)
            se.company = cong_ty
            se.custom_kiem_ke = self.name
            se.remarks = ghi_chu
            for d in dong:
                se.append("items", d)
            se.flags.ignore_permissions = True
            het = tam_bo_hsd(dong) if purpose == "Material Receipt" else {}
            try:
                se.insert()
                se.submit()
            finally:
                tra_hsd(het)
            giu.append(se)
            chung_tu.append({"dt": "Stock Entry", "name": se.name})
            return se

        # 0. D189: mã chuyển sang quản lý lô — tồn KHÔNG LÔ về 0 khi mã còn tắt lô (mã có lô mà còn tồn không lô thì tạm
        #    tắt), rồi bật lô. Phần đếm được vào lô theo HSD ở phiếu nhập bước 3, cùng giá vốn đang chạy của mã. D191:
        #    kể cả tồn ở kho khác (cửa hàng, xưởng) — kho dương nhập lại nguyên số vào lô tồn cũ ở bước 3, kho âm về 0.
        if doi_lo:
            for i in sorted(i for i, c in doi_lo.items() if c == "le"):
                self._dat_co_lo(i, 0, chung_tu)
            if ct["xuat_kl"]:
                phieu("Material Issue", _("Kiểm kê {0}: xuất hết tồn KHÔNG LÔ của mã chuyển sang quản lý lô (số đếm vào "
                                          "lô theo HSD; tồn ở kho khác nhập lại nguyên số vào lô tồn cũ — cùng kiểm "
                                          "kê).").format(self.name),
                      [{"item_code": x["item"], "qty": x["so"], "s_warehouse": x["kho"] or self.kho,
                        **zero(x["item"], x["kho"])} for x in ct["xuat_kl"]])
            if ct["nhap_kl"]:
                phieu("Material Receipt", _("Kiểm kê {0}: bù tồn KHÔNG LÔ đang âm về 0 trước khi chuyển mã sang quản lý "
                                            "lô.").format(self.name),
                      [vao(x["item"], None, x["so"], x["kho"]) for x in ct["nhap_kl"]])
            for i in sorted(doi_lo):
                self._dat_co_lo(i, 1, chung_tu, kho_khac=kk_bat.get(i))

        for (i, h), b in sorted(ten_lo.items()):
            tao_batch(i, b, nsx=nsx_tu_hsd(i, h), hsd=h)
        lo_cu = {}
        for i in sorted({x["item"] for x in ct["nhap_cu"]}):
            lo_cu[i] = tao_batch(i, ma_lo_ton_cu(i))
            if not lo_cu[i]:
                frappe.throw(_("Không tạo được lô tồn cũ cho {0} — mã chưa bật được quản lý lô.").format(self._ten(i)))
            frappe.db.set_value("Batch", lo_cu[i], "description", _(
                "Tồn cũ KHÔNG LÔ ở kho khác (cửa hàng, xưởng) lúc mã bật quản lý lô — kiểm kê {0}; chưa rõ HSD.").format(
                self.name), update_modified=False)
        for x in chung_tu:            # biên bản: lô tồn cũ của từng mã
            if x.get("dt") == "Item" and x.get("name") in lo_cu and x.get("kho_khac"):
                x["lo_cu"] = lo_cu[x["name"]]

        # 1. Chuyển lô cũ → lô theo HSD: mỗi mã một Repack (giá vốn không trộn giữa các mã).
        for i, ds in sorted(ct["repack"].items()):
            tu, den = {}, {}
            for x in ds:
                tu[x["tu"]] = tu.get(x["tu"], 0.0) + x["so"]
                den[x["hsd"]] = den.get(x["hsd"], 0.0) + x["so"]
            phieu("Repack", _("Kiểm kê {0}: chuyển hàng tồn của {1} từ lô cũ sang lô theo HSD in trên hộp.")
                  .format(self.name, i),
                  [{"item_code": i, "qty": flt(q, 6), "s_warehouse": self.kho, "use_serial_batch_fields": 1,
                    "batch_no": b, **zero(i)} for b, q in sorted(tu.items())]
                  + [{"item_code": i, "qty": flt(q, 6), "t_warehouse": self.kho, "is_finished_item": 1,
                      "use_serial_batch_fields": 1, "batch_no": ten_lo[(i, h)], **zero(i)}
                     for h, q in sorted(den.items())])

        # 2. Thiếu (sổ có, đếm không thấy) + nguồn của phần chuyển dính lô hết hạn.
        xuat = [{"item_code": x["item"], "qty": x["so"], "s_warehouse": self.kho, **lo_cua(x["batch"]),
                 **zero(x["item"])} for x in ct["xuat"]]
        if xuat:
            phieu("Material Issue", _("Kiểm kê {0}: xuất điều chỉnh phần THIẾU (sổ có, đếm không thấy); hàng hết "
                                      "hạn chuyển lô đi đường xuất / nhập.").format(self.name), xuat)

        # 3. Thừa (vào lô theo HSD) + bù lô âm + đích của phần chuyển hết hạn / chuyển từ tồn không lô (D189) — giá
        #    vốn đang chạy của mã.
        nhap = [vao(x["item"], x["batch"] or (ten_lo[(x["item"], x["hsd"])] if x["hsd"] else None), x["so"])
                for x in ct["nhap"]] + [vao(x["item"], lo_cu[x["item"]], x["so"], x["kho"]) for x in ct["nhap_cu"]]
        if nhap:
            phieu("Material Receipt", _("Kiểm kê {0}: nhập điều chỉnh phần THỪA (đếm thấy, sổ không có), bù lô "
                                        "âm; hàng hết hạn chuyển lô đi đường xuất / nhập.").format(self.name), nhap)

        # 4. Lô nhận hàng tồn cũ — bán không cần phiếu xuất xưởng (xuatxuong.kiem_ban). Lô của hàng làm từ ngày áp
        #    dụng BM.08.04 chưa duyệt: không đánh dấu — bán phải có phiếu duyệt (chua_duyet_xx).
        chua_xx = set(self.chua_duyet_xx(ke)) if not self.la_btp() else set()
        for b in sorted({b for k, b in ten_lo.items() if k not in chua_xx} | set(lo_cu.values())):
            if not frappe.db.get_value("Batch", b, "custom_kiem_ke"):
                frappe.db.set_value("Batch", b, "custom_kiem_ke", self.name, update_modified=False)
        self.db_set("ds_se", json.dumps(chung_tu), update_modified=False)

    def before_cancel(self):
        # Các Stock Entry của phiếu trỏ ngược về phiếu (custom_kiem_ke) và bị huỷ ngay trong on_cancel — đừng để
        # kiểm tra liên kết của Frappe chặn huỷ vì chính chúng.
        self.ignore_linked_doctypes = ("Stock Entry", "Batch")
        self._kiem_huy_doi_lo(json.loads(self.ds_se or "[]"))

    def _dat_co_lo(self, item, co, chung_tu, kho_khac=None):
        """D189: Item.has_batch_no = `co` ghi thẳng DB. ERPNext cấm đổi ô này khi mã đã có chứng từ kho
        (Item.cant_change) vì sợ tồn cũ không lô kẹt lại — ở đây tồn không lô của mã vừa về 0 ngay trước khi bật (mã
        còn tồn ở kho khác thì lap_ke không cho bật). Ghi vào ds_se để huỷ phiếu trả lại đúng như cũ."""
        cu = cint(frappe.db.get_value("Item", item, "has_batch_no"))
        if cu == cint(co):
            return
        frappe.db.set_value("Item", item, "has_batch_no", cint(co), update_modified=False)
        xoa_cache_ma(item)
        chung_tu.append({"dt": "Item", "name": item, "has_batch_no": [cu, cint(co)],
                         **({"kho_khac": [[w, flt(q, 6)] for w, q in kho_khac]} if kho_khac else {})})

    def _kiem_huy_doi_lo(self, ds):
        """D189: huỷ phiếu đã bật lô cho mã thì mã về lại KHÔNG lô — không được nếu sau lúc chốt mã đã có chứng từ kho
        khác (nhập / bán theo lô): hàng theo lô đó sẽ kẹt."""
        dau = {}
        for ct in ds:
            if ct.get("dt") == "Item":
                dau.setdefault(ct.get("name"), cint((ct.get("has_batch_no") or [1])[0]))
        tat = sorted(i for i, cu in dau.items() if not cu)
        if not tat:
            return
        cua_ta = {ct.get("name") for ct in ds if ct.get("dt") != "Item"}
        moc = self.chot_luc or self.modified
        for i in tat:
            khac = sorted({f"{r.voucher_type} {r.voucher_no}" for r in frappe.get_all(
                "Stock Ledger Entry", filters={"item_code": i, "is_cancelled": 0, "creation": (">=", moc)},
                fields=["voucher_type", "voucher_no"]) if r.voucher_no not in cua_ta})
            if khac:
                frappe.throw(_("Không huỷ được: phiếu này đã bật quản lý lô cho {0}, sau đó mã có chứng từ kho theo lô "
                               "({1}). Huỷ phiếu thì mã về lại không lô, hàng theo lô kẹt — huỷ các chứng từ đó trước.")
                             .format(self._ten(i), ", ".join(khac[:5]) + (" …" if len(khac) > 5 else "")))

    def on_cancel(self):
        """Huỷ = huỷ đúng những chứng từ kho phiếu này sinh ra, thứ tự ngược (nhập thừa trước, rồi xuất
        thiếu, rồi các phiếu chuyển lô) để không bước nào rút hàng chưa có. Cờ quản lý lô đã đổi (D189) trả lại
        đúng chỗ của nó trong thứ tự đó: tắt lô lại trước khi huỷ phiếu tồn không lô."""
        from sx.api.mfg import cancel_doc

        ds = json.loads(self.ds_se or "[]")
        log = []
        for ct in reversed(ds):
            if ct.get("dt") == "Item":
                cu = (ct.get("has_batch_no") or [None])[0]
                if cu is not None and frappe.db.exists("Item", ct.get("name")):
                    frappe.db.set_value("Item", ct["name"], "has_batch_no", cint(cu), update_modified=False)
                    xoa_cache_ma(ct["name"])
                    log.append(f"Item {ct['name']}: has_batch_no về {cint(cu)}")
                continue
            cancel_doc(ct.get("dt"), ct.get("name"), log)
        for b in frappe.get_all("Batch", filters={"custom_kiem_ke": self.name}, pluck="name"):
            frappe.db.set_value("Batch", b, "custom_kiem_ke", None, update_modified=False)
        self.db_set("trang_thai", DA_HUY, update_modified=False)
        if log:
            self.db_set("ghi_chu", ((self.ghi_chu or "") + "\n[Huỷ] " + "; ".join(log)).strip(),
                        update_modified=False)
