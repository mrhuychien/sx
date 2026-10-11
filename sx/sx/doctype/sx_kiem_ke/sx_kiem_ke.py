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
    đó đi đường xuất + nhập (sx/kiem_ke.chia_chung_tu).
Lô theo HSD nhận hàng được đánh dấu custom_kiem_ke = hàng TỒN CŨ, bán không cần phiếu xuất xưởng — TRỪ lô của hàng
làm từ ngày áp dụng BM.08.04 mà chưa duyệt (chua_duyet_xx): D188 không chặn chốt nữa (đặt lại kho phải chốt được),
lô đó vẫn vào kho nhưng không đánh dấu — bán phải có BM.08.04 duyệt; QC thấy nó ở màn Xuất xưởng (Lô chờ kiểm).

Chặn chốt khi mã đã đếm có chứng từ kho SAU lúc đếm (bán, nhập, huỷ phiếu…): số đếm không còn khớp sổ — đếm
lại mã đó; mã chưa đếm (sắp về 0) có chứng từ SAU lúc bắt đầu kiểm kê → phải đếm (hoặc bấm Không còn). Huỷ
phiếu đã chốt (Desk) = huỷ các chứng từ kho theo thứ tự ngược.

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
            self.flags.ton_khong_lo = {}
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
        # Mã quản lý lô mà có tồn KHÔNG gắn lô (dữ liệu cũ lỗi) không chuyển / xuất theo lô được — để riêng,
        # kiem_truoc_chot báo. Mã không quản lý lô: tồn của nó vốn không lô — về 0 bằng phiếu xuất không lô.
        self.flags.ton_khong_lo = {i: flt(sum(l["qty"] for l in lots.get(i, []) if not l["batch"]), 6)
                                   for i in items if i in co_lo and any(not l["batch"] for l in lots.get(i, []))}
        ke = {i: lap_ke_hoach([l for l in lots.get(i, []) if l["batch"] or i not in co_lo], dem[i],
                              lambda h, i=i: nsx_tu_hsd(i, h)) for i in items}
        ten_lo = {}
        for i, k in ke.items():
            for h in sorted({x["hsd"] for x in k["chuyen"]} | {x["hsd"] for x in k["nhap"]}):
                ten_lo[(i, h)] = ma_lo_hsd(i, h)
        return ke, ten_lo, ten

    def _ten(self, item):
        """Tên mã cho câu báo lỗi: tên trên Item (lap_ke đã tra) > tên trên dòng > mã."""
        t = (getattr(self.flags, "ten_ma", None) or {}).get(item)
        return t or next((r.ten for r in self.dong or [] if r.item == item and r.ten), None) or item

    def kiem_truoc_chot(self, ke):
        """Lỗi chặn chốt: [chuỗi]. Rỗng = chốt được."""
        loi = []
        if not ke:
            return [_("Chưa đếm mã nào.")]
        if self.la_btp():
            return self._kiem_btp(ke)
        # Mã tắt "Has Batch No" mà đã có giao dịch kho thì ERPNext không cho bật lô nữa (mfg.dam_bao_quan_ly_lo)
        # — không có lô thì không mang HSD được. Mã chưa từng có giao dịch thì lúc chốt tự bật. Chỉ chặn mã có SỐ
        # ĐẾM: mã không lô đếm 0 / chưa đếm thì về 0 bằng phiếu xuất không lô (D188).
        co_so = [i for i, k in ke.items() if k["dem"] > 0]
        khong_lo = [i.item_name or i.name for i in frappe.get_all(
            "Item", filters={"name": ("in", co_so or [""]), "has_batch_no": 0}, fields=["name", "item_name"])
            if frappe.db.exists("Stock Ledger Entry", {"item_code": i.name, "is_cancelled": 0})]
        if khong_lo:
            loi.append(_("Mã không quản lý theo lô — không ghi HSD được, bỏ khỏi phiếu: {0}.").format(
                ", ".join(khong_lo)))
        le = getattr(self.flags, "ton_khong_lo", None) or {}
        if le:
            loi.append(_("Mã có tồn KHÔNG gắn lô trong kho — kiểm kê HSD không chuyển được phần đó, sửa tồn trên "
                         "Desk trước: {0}.").format(", ".join(f"{self._ten(i)} ({_so(q)})" for i, q in sorted(le.items()))))
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
        for i in sorted(ke, key=lambda x: ten.get(x, x)):
            bang = theo_lo(ke[i], lambda h, i=i: ten_lo[(i, h)])
            for b, g in sorted(bang.items(), key=lambda x: (x[1]["hsd"] or "", x[0] or "")):
                self.append("lo", {"item": i, "ten": ten.get(i, i), "batch": b, "hsd": g["hsd"],
                                   "so_truoc": g["truoc"], "so_sau": g["sau"],
                                   "chenh": flt(g["sau"] - g["truoc"], 6), "viec": mo_ta_viec(g["viec"])})
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
        cong_ty = get_settings().cong_ty
        chung_tu = []

        for (i, h), b in sorted(ten_lo.items()):
            tao_batch(i, b, nsx=nsx_tu_hsd(i, h), hsd=h)

        gia = {i: gia_von_hien(i, self.kho) for i, k in ke.items() if co_thay_doi(k)}

        def zero(i):
            return {} if gia.get(i, 0) > 0 else {"allow_zero_valuation_rate": 1}

        def lo_cua(b):
            return {"use_serial_batch_fields": 1, "batch_no": b} if b else {}

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
            se.insert()
            se.submit()
            chung_tu.append({"dt": "Stock Entry", "name": se.name})
            return se

        ct = chia_chung_tu(ke, nowdate())

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

        # 3. Thừa (vào lô theo HSD) + bù lô âm + đích của phần chuyển hết hạn — giá vốn đang chạy của mã.
        def vao(i, b, so):
            d = {"item_code": i, "qty": so, "t_warehouse": self.kho, **lo_cua(b)}
            d.update({"basic_rate": gia[i]} if gia.get(i, 0) > 0 else {"allow_zero_valuation_rate": 1})
            return d

        nhap = [vao(x["item"], x["batch"] or (ten_lo[(x["item"], x["hsd"])] if x["hsd"] else None), x["so"])
                for x in ct["nhap"]]
        if nhap:
            phieu("Material Receipt", _("Kiểm kê {0}: nhập điều chỉnh phần THỪA (đếm thấy, sổ không có), bù lô "
                                        "âm; hàng hết hạn chuyển lô đi đường xuất / nhập.").format(self.name), nhap)

        # 4. Lô nhận hàng tồn cũ — bán không cần phiếu xuất xưởng (xuatxuong.kiem_ban). Lô của hàng làm từ ngày áp
        #    dụng BM.08.04 chưa duyệt: không đánh dấu — bán phải có phiếu duyệt (chua_duyet_xx).
        chua_xx = set(self.chua_duyet_xx(ke)) if not self.la_btp() else set()
        for b in sorted({b for k, b in ten_lo.items() if k not in chua_xx}):
            if not frappe.db.get_value("Batch", b, "custom_kiem_ke"):
                frappe.db.set_value("Batch", b, "custom_kiem_ke", self.name, update_modified=False)
        self.db_set("ds_se", json.dumps(chung_tu), update_modified=False)

    def before_cancel(self):
        # Các Stock Entry của phiếu trỏ ngược về phiếu (custom_kiem_ke) và bị huỷ ngay trong on_cancel — đừng để
        # kiểm tra liên kết của Frappe chặn huỷ vì chính chúng.
        self.ignore_linked_doctypes = ("Stock Entry", "Batch")

    def on_cancel(self):
        """Huỷ = huỷ đúng những chứng từ kho phiếu này sinh ra, thứ tự ngược (nhập thừa trước, rồi xuất
        thiếu, rồi các phiếu chuyển lô) để không bước nào rút hàng chưa có."""
        from sx.api.mfg import cancel_doc

        log = []
        for ct in reversed(json.loads(self.ds_se or "[]")):
            cancel_doc(ct.get("dt"), ct.get("name"), log)
        for b in frappe.get_all("Batch", filters={"custom_kiem_ke": self.name}, pluck="name"):
            frappe.db.set_value("Batch", b, "custom_kiem_ke", None, update_modified=False)
        self.db_set("trang_thai", DA_HUY, update_modified=False)
        if log:
            self.db_set("ghi_chu", ((self.ghi_chu or "") + "\n[Huỷ] " + "; ".join(log)).strip(),
                        update_modified=False)
