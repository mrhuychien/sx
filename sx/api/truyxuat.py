"""Truy xuất nguồn gốc 2 chiều (D115) — card "truyxuat" trên màn Quản lý.

═══ ĐẦU VÀO — đúng thứ người cầm hộp có trong tay ═══
    Mã vạch / chọn loại sản phẩm  +  HSD in trên hộp      →  lô thành phẩm
    hoặc gõ thẳng mã lô (của bất kỳ thứ gì: TP, bột, lô đỗ NCC…)

Từ D114 lô TP mang Batch.expiry_date = HSD in trên bao bì, nên (sản phẩm, HSD) tìm
ra lô. Lệch ngày (in tay sai một ngày) thì gợi ý các lô HSD gần đó, không im lặng.

═══ TRUY NGƯỢC — lô này làm từ gì ═══
Theo đúng chứng từ kho: Stock Entry nơi lô là thành phẩm → các dòng nguyên liệu
(batch_no ghi trên Stock Entry Detail, chọn FIFO lúc sinh phiếu — mfg._gan_batch_fifo)
→ nguyên liệu là BTP thì đệ quy tiếp → lá là lô NCC, tra ngược ra hoá đơn mua / nhà
cung cấp / kết luận tiếp nhận BM.07.03.

═══ QUÁ TRÌNH — ai làm, hôm đó QC thấy gì ═══
Lô bột có ngày sản xuất thật (Batch.custom_ngay_sx). Lô TP thì KHÔNG — thành phẩm
vào kho theo phiếu nhập, không gắn bảng vào hộp nào (D62). Nên phần vào hộp khớp
THEO NGÀY: các ngày vào hộp mã đó từ lần nhập kho trước tới ngày nhập lô này. Màn
hình nói rõ đó là khớp theo ngày, không phải theo lô.

═══ TRUY XUÔI — đi đâu, bán cho ai ═══
Sổ cái kho của lô (Stock Ledger Entry + Serial and Batch Bundle): phiếu giao / hoá
đơn bán → khách hàng; xuất khác; còn tồn ở đâu. Lô không phải TP thì đi xuôi qua các
phiếu sản xuất đã dùng nó tới tận lô TP, rồi tới khách — đây là câu hỏi lúc THU HỒI:
"lô đỗ này có vấn đề, những hộp nào, ai đã mua".
"""

import json
import math

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, nowdate

from sx.config.roles import guard_card
from sx.utils import items_tp, la_lo_hsd

SAU_TOI_DA = 8          # tầng đệ quy — chuỗi thật sâu nhất ~5 (TP→bột bánh→bột nền→vỡ→ủ→đỗ)
NGAY_VAO_HOP_TOI_DA = 7  # cửa sổ khớp vào hộp theo ngày khi không có lần nhập trước
HSD_LECH = 7             # gợi ý lô có HSD lệch ± chừng này ngày khi không khớp đúng
BAN = ("Delivery Note", "Sales Invoice", "POS Invoice")
MUA = ("Purchase Receipt", "Purchase Invoice")


# ═══════════════════════════════ tìm lô ═══════════════════════════════

@frappe.whitelist()
def danh_muc():
    """Thành phẩm để chọn + bảng mã vạch → mã hàng (tra ngay trên máy khi quét)."""
    guard_card("truyxuat")
    from sx.api.portal import _ma_quet

    return {
        "sp": [{"item": i.name, "ten": i.item_name or i.name} for i in items_tp()],
        "ma_quet": {"sp": _ma_quet([])["sp"]},
    }


def _ma_tu_vach(q):
    """Chuỗi quét / gõ là mã vạch hoặc mã hàng → item_code, không thì None."""
    q = (q or "").strip()
    if not q:
        return None
    ma = frappe.db.get_value("Item Barcode", {"barcode": q}, "parent")
    if not ma and q.startswith("0"):           # EAN-13 đọc thành UPC-A thừa số 0
        ma = frappe.db.get_value("Item Barcode", {"barcode": q[1:]}, "parent")
    if not ma and frappe.db.exists("Item", q):
        ma = q
    return ma


@frappe.whitelist()
def tim_lo(item=None, hsd=None, q=None):
    """Danh sách lô khớp. Trả {lo:[...], gan_dung: bool, item}.

    `q` là mã lô (đúng hoặc một phần) — hoặc mã vạch, khi đó coi như chọn sản phẩm.
    `item` + `hsd`: đúng HSD; không có thì các lô HSD lệch ≤ HSD_LECH ngày, gắn cờ
    gan_dung để màn hình nói ra "không có lô đúng HSD này".
    """
    guard_card("truyxuat")
    q = (q or "").strip()
    if q:
        if frappe.db.exists("Batch", q):
            return {"lo": _dong_lo([q]), "gan_dung": False, "item": None}
        ma = _ma_tu_vach(q)
        if ma:
            item = ma
        else:
            ten = frappe.get_all("Batch", filters={"name": ("like", f"%{q}%")},
                                 pluck="name", order_by="creation desc", limit=30)
            return {"lo": _dong_lo(ten), "gan_dung": False, "item": None}

    loc = {}
    if item:
        loc["item"] = item
    elif not hsd:
        frappe.throw(_("Chọn sản phẩm, nhập HSD, hoặc gõ mã lô."))
    else:
        # Chỉ có HSD: giới hạn trong thành phẩm — HSD của lô đỗ NCC trùng ngày thì
        # không phải thứ người cầm hộp đang tìm.
        loc["item"] = ("in", [i.name for i in items_tp(["name"])] or [""])
    gan_dung = False
    if hsd:
        hsd = str(getdate(hsd))
        ten = frappe.get_all("Batch", filters={**loc, "expiry_date": hsd},
                             pluck="name", order_by="creation desc", limit=50)
        if not ten:
            gan_dung = True
            ten = frappe.get_all(
                "Batch", filters={**loc, "expiry_date": ("between", (
                    str(add_days(hsd, -HSD_LECH)), str(add_days(hsd, HSD_LECH))))},
                pluck="name", order_by="expiry_date", limit=50)
    else:
        ten = frappe.get_all("Batch", filters=loc, pluck="name",
                             order_by="creation desc", limit=30)
    return {"lo": _dong_lo(ten), "gan_dung": gan_dung, "item": item}


def _dong_lo(ten):
    if not ten:
        return []
    ds = frappe.get_all(
        "Batch", filters={"name": ("in", list(ten))},
        fields=["name", "item", "item_name", "manufacturing_date", "expiry_date",
                "batch_qty", "creation"],
        order_by="creation desc")
    tp = {i.name for i in items_tp(["name"])}
    # la_tp: màn hình hiện lô thành phẩm bằng HSD, KHÔNG bằng mã lô (W05 — ẩn mã lô).
    return [{"batch": b.name, "item": b.item, "ten": b.item_name or b.item,
             "nsx": _d(b.manufacturing_date), "hsd": _d(b.expiry_date),
             "ton": flt(b.batch_qty, 3), "la_tp": b.item in tp} for b in ds]


def _nhan_lo(ctx, batch):
    """Nhãn một lô cho người đọc: lô thành phẩm có HSD → "HSD dd/mm/yyyy" (W05 —
    người cầm hộp chỉ có HSD); lô khác (bột, đỗ NCC…) giữ mã lô."""
    t = ctx.thong_tin(batch)
    return _("HSD {0}").format(_vn(t["hsd"])) if t.get("la_tp") and t.get("hsd") else batch


def _vn(iso):
    """"2026-10-04" -> "04/10/2026" cho câu chữ hiện ra màn hình."""
    y, m, d = str(iso)[:10].split("-")
    return f"{d}/{m}/{y}"


def _d(v):
    return str(v)[:10] if v else None


# ═══════════════════════════════ một lô ═══════════════════════════════

@frappe.whitelist()
def lo(batch):
    """Toàn bộ hồ sơ của một lô: ngược, quá trình, xuôi."""
    guard_card("truyxuat")
    if not batch or not frappe.db.exists("Batch", batch):
        frappe.throw(_("Không tìm thấy lô {0}.").format(batch))
    ctx = _Ctx()
    goc = ctx.thong_tin(batch)
    ghi_chu = []

    nguoc = ctx.nguoc(batch, goc["item"], set(), 0)
    nhap = _phieu_nhap_cua(batch)
    if goc["la_tp"]:
        no = frappe.db.get_value("SX No BOM", {"batch": batch},
                                 ["name", "trang_thai", "se_bu"], as_dict=True)
        if no:
            ghi_chu.append(_(
                "Lô này nhập kho lúc mã hàng CHƯA có BOM (sổ nợ {0}, {1}). Nguyên liệu "
                "{2} — không truy được đúng lô bột đã dùng.").format(
                    no.name, no.trang_thai,
                    _("trừ bù FIFO tại ngày hạch toán bù") if no.se_bu
                    else _("chưa trừ")))
            if no.se_bu:
                nguoc = ctx.nguyen_lieu_cua_se(no.se_bu, set([batch]), 1)

    so_cai = _so_cai(batch)
    can_bang = _can_bang(batch, so_cai)
    xuoi = None if goc["la_tp"] else ctx.xuoi(batch, set(), 0)
    qua_trinh, cua_so = _qua_trinh(goc, nhap, nguoc)
    if goc["la_tp"] and cua_so and cua_so[0] == cua_so[1] and la_lo_hsd(batch):
        ghi_chu.append(_(
            "Vào hộp ngày {0} = NSX của lô (HSD − hạn dùng): ai đóng mã này hôm đó.")
            .format(_vn(cua_so[0])))
    elif goc["la_tp"] and cua_so:
        ghi_chu.append(_(
            "Vào hộp khớp THEO NGÀY ({0} → {1}): những ngày đóng mã này trước khi nhập "
            "lô. Thành phẩm không gắn bảng vào hộp nào nên không khớp được theo lô.")
            .format(_vn(cua_so[0]), _vn(cua_so[1])))
    if not nguoc and not goc["la_ncc"]:
        ghi_chu.append(_("Không tìm thấy phiếu sản xuất nào sinh ra lô này — lô nhập "
                         "tay trên Desk, hoặc chứng từ đã huỷ."))

    khach = _khach_tong(so_cai, xuoi)
    for k in khach:
        # W05: khách nhận lô thành phẩm nào — nói bằng HSD, không bằng mã lô.
        k["lo"] = [_nhan_lo(ctx, b) for b in k["lo"]]
    return {
        "lo": goc,
        "nhap_kho": nhap,
        "nguon": nguoc,
        "ncc": ctx.ncc(batch) if goc["la_ncc"] else None,
        "qua_trinh": qua_trinh,
        "ban": _ban(so_cai),
        "xuoi": xuoi,
        "khach": khach,
        "can_bang": can_bang,
        "luu_mau": _luu_mau(goc, cua_so),
        "su_co_lo": _su_co_theo_lo(batch),
        "khieu_nai_lo": _khieu_nai_theo_lo(batch),
        "thu_hoi": _thu_hoi(batch),
        "ghi_chu": ghi_chu,
    }


class _Ctx:
    """Bộ nhớ đệm trong MỘT lần tra — cây xuôi của một lô đỗ có thể chạm cùng một
    lô bột qua nhiều nhánh, tra lại mỗi lần là hàng trăm truy vấn thừa."""

    def __init__(self):
        self._tp = None
        self._lo = {}
        self._ncc = {}

    def la_tp(self, item):
        if self._tp is None:
            self._tp = {i.name for i in items_tp(["name"])}
        return item in self._tp

    def thong_tin(self, batch):
        if batch in self._lo:
            return self._lo[batch]
        b = frappe.db.get_value(
            "Batch", batch,
            ["name", "item", "item_name", "manufacturing_date", "expiry_date",
             "custom_ngay_sx", "batch_qty", "stock_uom"], as_dict=True) or frappe._dict()
        nhom = frappe.get_cached_value("Item", b.item, "custom_sx_nhom") or ""
        ngay_sx = frappe.db.get_value("SX Ngay San Xuat", b.custom_ngay_sx, "ngay") \
            if b.custom_ngay_sx else None
        la_tp = self.la_tp(b.item)
        ra = {"batch": batch, "item": b.item, "ten": b.item_name or b.item, "nhom": nhom,
              "nsx": _d(b.manufacturing_date), "hsd": _d(b.expiry_date),
              "ngay_sx": _d(ngay_sx), "phieu_ngay": b.custom_ngay_sx,
              "ton": flt(b.batch_qty, 3), "dvt": b.stock_uom or "",
              "la_tp": la_tp,
              # Lá của cây: không phải hàng tự làm → hàng mua về.
              "la_ncc": not la_tp and not nhom.startswith("BTP")}
        xd = frappe.db.get_value(
            "SX Xuat Dau", {"lo_rang": batch, "docstatus": 1},
            ["name", "loai_dau", "ngay_rang", "dau_kg"], as_dict=True)
        if xd:
            ra["rang"] = {"phieu": xd.name, "loai_dau": xd.loai_dau,
                          "ngay": _d(xd.ngay_rang), "kg": flt(xd.dau_kg, 2)}
        self._lo[batch] = ra
        return ra

    # ─────────────── ngược ───────────────
    def nguoc(self, batch, item, visited, sau):
        if sau > SAU_TOI_DA or batch in visited:
            return []
        visited = visited | {batch}
        se = set(frappe.get_all(
            "Stock Entry Detail",
            filters={"batch_no": batch, "is_finished_item": 1, "docstatus": 1},
            pluck="parent"))
        ra = []
        for s in sorted(se):
            ra.extend(self.nguyen_lieu_cua_se(s, visited, sau))
        return ra

    def nguyen_lieu_cua_se(self, se, visited, sau):
        gop = {}
        for r in frappe.get_all(
                "Stock Entry Detail",
                filters={"parent": se, "is_finished_item": 0, "docstatus": 1,
                         "s_warehouse": ("is", "set")},
                fields=["item_code", "item_name", "batch_no", "qty", "stock_uom"]):
            k = (r.item_code, r.batch_no or "")
            g = gop.setdefault(k, {"item": r.item_code, "ten": r.item_name or r.item_code,
                                   "batch": r.batch_no, "so": 0.0, "dvt": r.stock_uom or "",
                                   "se": se})
            g["so"] += flt(r.qty)
        ra = []
        for g in gop.values():
            g["so"] = flt(g["so"], 3)
            if g["batch"] and g["batch"] in visited:
                # Chứng từ vòng (A làm ra B, B lại làm ra A): hiện một lần, đánh dấu,
                # không đi tiếp — đi tiếp là cây vô tận.
                g.update(lap=True, nhom=self.thong_tin(g["batch"])["nhom"])
            elif g["batch"]:
                tt = self.thong_tin(g["batch"])
                g.update({k: tt.get(k) for k in ("nhom", "nsx", "hsd", "ngay_sx", "rang")})
                if tt["la_ncc"]:
                    g["ncc"] = self.ncc(g["batch"])
                else:
                    g["con"] = self.nguoc(g["batch"], g["item"], visited, sau + 1)
            else:
                g["nhom"] = frappe.get_cached_value("Item", g["item"], "custom_sx_nhom") or ""
                g["khong_lo"] = True
            ra.append(g)
        ra.sort(key=lambda x: (not str(x.get("nhom") or "").startswith("BTP"), x["ten"]))
        return ra

    # ─────────────── nhà cung cấp ───────────────
    def ncc(self, batch):
        """Lô hàng mua: nhà cung cấp, chứng từ, kết luận tiếp nhận BM.07.03."""
        if batch in self._ncc:
            return self._ncc[batch]
        ra = None
        for m in _so_cai(batch):
            if m["loai"] in MUA and m["so"] > 0:
                v = frappe.db.get_value(m["loai"], m["chung_tu"],
                                        ["supplier", "supplier_name"], as_dict=True) or {}
                ra = {"ncc": v.get("supplier"), "ten_ncc": v.get("supplier_name") or v.get("supplier"),
                      "loai_ct": m["loai"], "chung_tu": m["chung_tu"], "ngay": m["ngay"]}
                if m["loai"] in ("Purchase Invoice", "Purchase Receipt"):
                    ra.update(_qc_tiep_nhan(m["chung_tu"], batch, m["loai"]))
                ra.update(_ncc_duyet(v.get("supplier")))
                break
        if not ra:
            # Lô tạo tay / nhập tồn đầu: Batch có thể vẫn ghi NCC + chứng từ gốc.
            b = frappe.db.get_value("Batch", batch, ["supplier", "reference_doctype",
                                                     "reference_name"], as_dict=True) or {}
            if b.get("supplier") or b.get("reference_name"):
                ra = {"ncc": b.get("supplier"), "ten_ncc": b.get("supplier"),
                      "loai_ct": b.get("reference_doctype"), "chung_tu": b.get("reference_name"),
                      "ngay": None}
        self._ncc[batch] = ra
        return ra

    # ─────────────── xuôi ───────────────
    def xuoi(self, batch, visited, sau):
        """Những lô được làm RA từ lô này, tới tận thành phẩm (kèm bán cho ai)."""
        if sau > SAU_TOI_DA or batch in visited:
            return []
        visited = visited | {batch}
        se = set(frappe.get_all(
            "Stock Entry Detail",
            filters={"batch_no": batch, "is_finished_item": 0, "docstatus": 1,
                     "s_warehouse": ("is", "set")},
            pluck="parent"))
        ra = {}
        for s in sorted(se):
            da_dung = flt(sum(flt(r.qty) for r in frappe.get_all(
                "Stock Entry Detail",
                filters={"parent": s, "batch_no": batch, "is_finished_item": 0},
                fields=["qty"])), 3)
            ra_lo = frappe.get_all(
                "Stock Entry Detail",
                filters={"parent": s, "is_finished_item": 1, "docstatus": 1},
                fields=["batch_no", "item_code", "qty"])
            if not ra_lo:
                # Phiếu trừ bù cho thành phẩm nhập lúc chưa có BOM (D97): không có
                # dòng thành phẩm, lô TP nằm trên sổ nợ.
                no = frappe.db.get_value("SX No BOM", {"se_bu": s},
                                         ["batch", "item", "so_luong"], as_dict=True)
                if no and no.batch:
                    ra_lo = [frappe._dict(batch_no=no.batch, item_code=no.item,
                                          qty=no.so_luong, bu=1)]
            for r in ra_lo:
                if not r.batch_no:
                    continue
                n = ra.get(r.batch_no)
                if n:
                    n["dung"] = flt(n["dung"] + da_dung, 3)
                    continue
                tt = self.thong_tin(r.batch_no)
                if r.batch_no in visited:
                    ra[r.batch_no] = {"batch": r.batch_no, "item": tt["item"], "ten": tt["ten"],
                                      "la_tp": tt["la_tp"], "se": s, "dung": da_dung, "lap": True}
                    continue
                n = {k: tt.get(k) for k in ("batch", "item", "ten", "nhom", "nsx", "hsd",
                                            "ngay_sx", "la_tp", "dvt")}
                n.update({"se": s, "dung": da_dung, "bu": bool(r.get("bu"))})
                if tt["la_tp"]:
                    sc = _so_cai(r.batch_no)
                    n["ban"] = _ban(sc)
                else:
                    n["con"] = self.xuoi(r.batch_no, visited, sau + 1)
                ra[r.batch_no] = n
        return sorted(ra.values(), key=lambda x: (x.get("nsx") or "", x["batch"]))


def _ncc_duyet(supplier):
    """NCC đã duyệt BM.07.02 chưa (W09) — cho khối Nhà cung cấp trên thẻ lô."""
    from sx.qc.ncc import thong_tin

    t = thong_tin(supplier)
    return {"ncc_duyet": t.get("duyet"), "ncc_loai": t.get("loai") or ""} if t else {}


def _qc_tiep_nhan(pi, batch, dt="Purchase Invoice"):
    """Kết luận tiếp nhận của DÒNG chứng từ mua chứa lô (BM.07.03, sx/qc/tiep_nhan) —
    hoá đơn mua (đường cũ) hoặc phiếu nhập mua (W10, D138)."""
    cot = ["item_code", "batch_no", "custom_ncc_lo", "custom_ket_luan", "custom_coa_vi_sinh"]
    try:
        dong = frappe.get_all(f"{dt} Item", filters={"parent": pi}, fields=cot + ["custom_giay_to"])
    except Exception:
        try:
            dong = frappe.get_all(f"{dt} Item", filters={"parent": pi}, fields=cot)
        except Exception:
            return {}   # site chưa có field QC tiếp nhận
    item = frappe.db.get_value("Batch", batch, "item")
    r = next((d for d in dong if d.batch_no == batch), None) \
        or next((d for d in dong if d.item_code == item), None)
    if not r:
        return {}
    return {"lo_ncc": r.custom_ncc_lo, "ket_luan": r.custom_ket_luan,
            "coa": r.custom_coa_vi_sinh, "giay_to": r.get("custom_giay_to") or ""}


# ═══════════════════════════════ sổ cái lô ═══════════════════════════════

def _so_cai(batch):
    """Mọi lần lô ra / vào kho còn hiệu lực: [{loai, chung_tu, ngay, kho, so}].

    ERPNext v15+ ghi lô trong Serial and Batch Bundle — SLE có thể để trống batch_no
    và chỉ trỏ tới bundle. Gom CẢ hai đường, số lượng lấy theo dòng của đúng lô
    trong bundle (một bundle có thể chứa nhiều lô).
    """
    rows = frappe.db.sql(
        """select sle.voucher_type, sle.voucher_no, sle.posting_date, sle.warehouse,
                  sle.actual_qty, sle.batch_no, e.qty as qty_lo, sle.creation
             from `tabStock Ledger Entry` sle
             left join `tabSerial and Batch Entry` e
               on e.parent = sle.serial_and_batch_bundle and e.batch_no = %(b)s
            where sle.is_cancelled = 0
              and (sle.batch_no = %(b)s or e.batch_no = %(b)s)
            order by sle.posting_date, sle.creation""", {"b": batch}, as_dict=True)
    gop = {}
    for r in rows:
        so = flt(r.qty_lo) if r.qty_lo is not None else flt(r.actual_qty)
        k = (r.voucher_type, r.voucher_no, r.warehouse)
        g = gop.setdefault(k, {"loai": r.voucher_type, "chung_tu": r.voucher_no,
                               "ngay": _d(r.posting_date), "kho": r.warehouse, "so": 0.0})
        g["so"] += so
    return [dict(g, so=flt(g["so"], 3)) for g in gop.values() if abs(g["so"]) > 1e-9]


def _ban(so_cai):
    """Chia sổ cái lô thành: bán (theo khách), xuất khác, còn tồn theo kho."""
    ban, khac, ton = [], [], {}
    for m in so_cai:
        ton[m["kho"]] = flt(ton.get(m["kho"], 0) + m["so"], 3)
        if m["loai"] in BAN:
            v = frappe.db.get_value(m["loai"], m["chung_tu"],
                                    ["customer", "customer_name"], as_dict=True) or {}
            ban.append({**m, "so": -m["so"], "khach": v.get("customer"),
                        "ten_khach": v.get("customer_name") or v.get("customer"),
                        "tra_lai": m["so"] > 0})
        elif m["so"] < 0:
            khac.append({**m, "so": -m["so"],
                         "muc_dich": frappe.db.get_value(m["loai"], m["chung_tu"], "purpose")
                         if m["loai"] == "Stock Entry" else None})
    return {
        "ban": ban, "khac": khac,
        "ton": [{"kho": k, "so": v} for k, v in ton.items() if abs(v) > 1e-9],
        "da_ban": flt(sum(b["so"] for b in ban), 3),
        "nhap": flt(sum(m["so"] for m in so_cai
                        if m["so"] > 0 and m["loai"] not in BAN), 3),
    }


def _khach_tong(so_cai, xuoi):
    """Danh sách khách gộp — lô gốc bán thẳng hoặc qua mọi lô TP làm ra từ nó.
    Đây là danh sách phải gọi khi thu hồi."""
    gop = {}

    def them(ds, lo_tp):
        for b in ds:
            k = b.get("khach") or b.get("ten_khach") or "?"
            g = gop.setdefault(k, {"khach": b.get("khach"), "ten_khach": b.get("ten_khach"),
                                   "so": 0.0, "lo": set(), "lan_cuoi": None})
            g["so"] += b["so"]
            g["lo"].add(lo_tp)
            if b.get("ngay") and (not g["lan_cuoi"] or b["ngay"] > g["lan_cuoi"]):
                g["lan_cuoi"] = b["ngay"]

    def di(ds):
        for n in ds or []:
            if n.get("ban"):
                them(n["ban"]["ban"], n["batch"])
            di(n.get("con"))

    if so_cai is not None and xuoi is None:
        them(_ban(so_cai)["ban"], None)
    di(xuoi)
    return sorted(({**g, "so": flt(g["so"], 3), "lo": sorted(x for x in g["lo"] if x)}
                   for g in gop.values()), key=lambda g: -g["so"])


# ═══════════════════════════════ cân bằng lô (W06) ═══════════════════════════════

DAT_CAN_BANG = 98.0
CHUYEN_KHO = ("Material Transfer", "Material Transfer for Manufacture", "Send to Subcontractor")


def _mau_cua_lo(batch):
    """Tổng số lượng mẫu đã lấy từ lô (mẫu lưu gắn lô — W07). Mẫu lấy ra khỏi hộp
    nhưng KHÔNG trừ kho, nên khi đếm thực tế phải cộng lại mới đủ."""
    try:
        if not frappe.get_meta("SX QC Luu Mau").has_field("batch"):
            return 0.0
        return flt(sum(flt(x.so_luong) for x in frappe.get_all(
            "SX QC Luu Mau", filters={"batch": batch}, fields=["so_luong"])), 3)
    except Exception:
        return 0.0


def _can_bang(batch, so_cai, ton_thuc_te=None):
    """Bảng cân bằng lô (W06): sản xuất / nhập = đã bán + xuất khác + tồn (+ mẫu).

    Chuyển kho không tính (ra kho này = vào kho kia). Không đếm thực tế thì lấy tồn
    sổ sách — mẫu lưu đã nằm trong tồn sổ (lấy mẫu không trừ kho) nên không cộng
    thêm. Có số đếm thực tế (diễn tập) thì: tìm thấy = bán + xuất khác + tồn đếm +
    mẫu đã lấy. Đạt khi ≥ 98%.
    """
    se = [m["chung_tu"] for m in so_cai if m["loai"] == "Stock Entry"]
    muc = {r.name: r.purpose for r in frappe.get_all(
        "Stock Entry", filters={"name": ("in", se)}, fields=["name", "purpose"])} if se else {}
    sx = ban = khac = 0.0
    for m in so_cai:
        if m["loai"] in BAN:
            ban -= m["so"]                         # bán ghi âm; trả lại ghi dương → trừ
        elif m["loai"] == "Stock Entry" and muc.get(m["chung_tu"]) in CHUYEN_KHO:
            continue
        elif m["so"] > 0:
            sx += m["so"]
        else:
            khac -= m["so"]
    ton = sum(m["so"] for m in so_cai)
    mau = _mau_cua_lo(batch)
    dem = ton_thuc_te not in (None, "")
    tim = ban + khac + ((flt(ton_thuc_te) + mau) if dem else ton)
    pt = round(tim * 100.0 / sx, 1) if sx > 1e-9 else None
    return {"san_xuat": flt(sx, 3), "da_ban": flt(ban, 3), "xuat_khac": flt(khac, 3),
            "ton_so_sach": flt(ton, 3), "mau_luu": mau,
            "ton_thuc_te": flt(ton_thuc_te, 3) if dem else None,
            "tim_thay": flt(tim, 3), "chenh_lech": flt(sx - tim, 3), "pt": pt,
            "dat": bool(pt is not None and pt >= DAT_CAN_BANG), "nguong": DAT_CAN_BANG}


# ═══════════════════════════════ diễn tập truy xuất (W06) ═══════════════════════════════

DT = "SX Dien Tap Truy Xuat"
MAU_IN = "sx/sx/doctype/sx_dien_tap_truy_xuat/dien_tap.html"


def _dien_tap_dang():
    r = frappe.get_all(DT, filters={"nguoi": frappe.session.user, "ket_thuc": ("is", "not set")},
                       fields=["name", "bat_dau"], order_by="creation desc", limit=1)
    return {"name": r[0].name, "bat_dau": str(r[0].bat_dau)} if r else None


@frappe.whitelist()
def dien_tap_dang():
    """Lần diễn tập đang chạy của người này (tải lại trang không mất đồng hồ)."""
    guard_card("truyxuat")
    return _dien_tap_dang()


@frappe.whitelist()
def dien_tap_bat_dau():
    """Bấm giờ: giờ bắt đầu do SERVER ghi — đồng hồ máy không chỉnh được kết quả."""
    guard_card("truyxuat")
    dang = _dien_tap_dang()
    if dang:
        return dang
    d = frappe.get_doc({"doctype": DT, "ngay": nowdate(), "nguoi": frappe.session.user,
                        "bat_dau": now_datetime()})
    d.insert(ignore_permissions=True)
    return {"name": d.name, "bat_dau": str(d.bat_dau)}


@frappe.whitelist()
def dien_tap_huy(name):
    """Bỏ lần diễn tập CHƯA kết thúc (bấm nhầm). Đã kết thúc là hồ sơ — không xoá ở đây."""
    guard_card("truyxuat")
    d = frappe.get_doc(DT, name)
    if d.ket_thuc:
        frappe.throw(_("Diễn tập {0} đã kết thúc — là hồ sơ, không bỏ được.").format(name))
    d.delete(ignore_permissions=True)
    return {"ok": 1}


def _dem_ncc(cay):
    n = 0
    for x in cay or []:
        if x.get("batch") and not str(x.get("nhom") or "").startswith("BTP") and not x.get("con"):
            n += 1
        n += _dem_ncc(x.get("con"))
    return n


@frappe.whitelist()
def dien_tap_ket_thuc(name, batch, ton_thuc_te=None, ghi_chu=None):
    """Dừng đồng hồ ở lô vừa truy: ghi thời gian, bảng cân bằng (kèm tồn đếm thực
    tế nếu có), ảnh chụp kết quả truy để in phụ lục BM.02.04."""
    guard_card("truyxuat")
    d = frappe.get_doc(DT, name)
    if d.ket_thuc:
        frappe.throw(_("Diễn tập {0} đã kết thúc lúc {1}.").format(name, d.ket_thuc))
    kq = lo(batch)
    cb = _can_bang(batch, _so_cai(batch), ton_thuc_te)
    l = kq["lo"]
    xong = now_datetime()
    giay = (get_datetime(xong) - get_datetime(d.bat_dau)).total_seconds()
    d.update({
        "ket_thuc": xong, "so_phut": max(1, int(math.ceil(giay / 60.0))),
        "lo": batch, "item": l["item"], "ten_san_pham": l["ten"],
        "nsx": l.get("nsx"), "hsd": l.get("hsd"),
        "san_xuat": cb["san_xuat"], "da_ban": cb["da_ban"], "xuat_khac": cb["xuat_khac"],
        "ton_so_sach": cb["ton_so_sach"], "mau_luu": cb["mau_luu"],
        "ton_thuc_te": cb["ton_thuc_te"], "tim_thay": cb["tim_thay"],
        "chenh_lech": cb["chenh_lech"], "can_bang_pt": cb["pt"] or 0, "dat": 1 if cb["dat"] else 0,
        "so_khach": len(kq.get("khach") or []), "so_ncc": _dem_ncc(kq.get("nguon")),
        "so_ngay_sx": len(kq.get("qua_trinh") or []),
        "ghi_chu": (ghi_chu or "").strip() or d.ghi_chu,
        "ket_qua": json.dumps({k: kq.get(k) for k in ("lo", "nhap_kho", "nguon", "qua_trinh",
                                                      "khach", "ghi_chu", "can_bang")},
                              ensure_ascii=False, default=str),
    })
    d.save(ignore_permissions=True)
    return {"name": d.name, "so_phut": d.so_phut, "can_bang": cb}


@frappe.whitelist()
def in_dien_tap(name):
    """HTML tờ A4 — phụ lục BM.02.04 (kết quả diễn tập truy xuất)."""
    guard_card("truyxuat")
    d = frappe.get_doc(DT, name)
    kq = json.loads(d.ket_qua or "{}")
    return frappe.render_template(MAU_IN, {"d": d, "kq": kq, "nguong": DAT_CAN_BANG})


@frappe.whitelist()
def ds_dien_tap(limit=10):
    """Các lần diễn tập gần đây (để in lại)."""
    guard_card("truyxuat")
    return [dict(x, ngay=str(x.ngay)) for x in frappe.get_all(
        DT, filters={"ket_thuc": ("is", "set")},
        fields=["name", "ngay", "ten_san_pham", "hsd", "so_phut", "can_bang_pt", "dat", "nguoi"],
        order_by="creation desc", limit=cint(limit) or 10)]


# ═══════════════════════════════ phiếu nhập + quá trình ═══════════════════════════════

def _phieu_nhap_cua(batch):
    """Phiếu nhập kho TP đã sinh ra lô này (qua Stock Entry ghi trong ds_se)."""
    se = set(frappe.get_all("Stock Entry Detail",
                            filters={"batch_no": batch, "docstatus": 1,
                                     "t_warehouse": ("is", "set")}, pluck="parent"))
    # W05 (D131): lô theo HSD — hai phiếu nhập cùng mã cùng HSD vào CÙNG lô. Phiếu
    # đầu tiên là "nhập kho", các phiếu sau liệt kê kèm.
    ra = None
    for s in sorted(se):
        p = frappe.get_all(
            "SX Phieu Nhap TP",
            filters={"ds_se": ("like", f'%"{s}"%'), "docstatus": 1},
            fields=["name", "ngay", "nguoi_lap", "nguoi_duyet", "duyet_luc", "kho_dich"],
            limit=1)
        if not p:
            continue
        p = p[0]
        if ra is None:
            ra = {"phieu": p.name, "ngay": _d(p.ngay), "nguoi_lap": p.nguoi_lap,
                  "nguoi_duyet": p.nguoi_duyet, "duyet_luc": str(p.duyet_luc or "")[:16],
                  "kho": p.kho_dich, "se": s, "them": []}
        elif p.name != ra["phieu"] and p.name not in [x["phieu"] for x in ra["them"]]:
            ra["them"].append({"phieu": p.name, "ngay": _d(p.ngay)})
    return ra


def _cua_so_vao_hop(item, nhap):
    """[từ, đến] các ngày vào hộp có thể nằm trong lô nhập ngày `nhap['ngay']`.

    Từ ngày của lần nhập TRƯỚC (cùng mã) — tính cả ngày đó, vì đóng chiều hôm đó có
    thể vào lô sau — tới ngày nhập lô này; không có lần trước thì lùi tối đa 7 ngày.
    """
    den = getdate(nhap["ngay"])
    truoc = frappe.db.sql(
        """select max(p.ngay) from `tabSX Phieu Nhap TP` p
             join `tabSX Phieu Nhap TP Item` d on d.parent = p.name
            where p.docstatus = 1 and d.item = %s and d.so_dem > 0
              and p.ngay <= %s and p.name != %s""",
        (item, den, nhap["phieu"]))
    truoc = truoc[0][0] if truoc and truoc[0][0] else None
    tu = add_days(den, -(NGAY_VAO_HOP_TOI_DA - 1))
    if truoc and getdate(truoc) > getdate(tu):
        tu = getdate(truoc)
    return str(getdate(tu)), str(den)


def _qua_trinh(goc, nhap, nguoc):
    """Các ngày làm ra lô, mỗi ngày: việc gì, ai vào hộp, QC lượt nào, sự cố gì."""
    ngay = {}

    def ngay_cua(d):
        return ngay.setdefault(d, {"ngay": d, "viec": [], "vao_hop": [], "qc": [],
                                   "su_co": []})

    def viec(d, ten):
        if d and ten not in ngay_cua(d)["viec"]:
            ngay_cua(d)["viec"].append(ten)

    cua_so = None
    if goc["la_tp"] and nhap:
        viec(nhap["ngay"], _("Nhập kho"))
        for x in nhap.get("them") or []:
            viec(x["ngay"], _("Nhập kho"))
        # W05 (D131): lô theo HSD có NSX = HSD − hạn dùng = ĐÚNG ngày vào hộp; lô cũ
        # (theo ngày nhập) mới phải khớp theo cửa sổ ngày.
        cua_so = ((goc["nsx"], goc["nsx"]) if la_lo_hsd(goc["batch"]) and goc.get("nsx")
                  else _cua_so_vao_hop(goc["item"], nhap))
        for d, ds in _vao_hop(goc["item"], *cua_so).items():
            viec(d, _("Vào hộp"))
            ngay_cua(d)["vao_hop"] = ds

    def di(ds):
        for n in ds or []:
            if n.get("ngay_sx"):
                viec(n["ngay_sx"], _("Làm {0}").format(n["ten"]))
            if n.get("rang"):
                viec(n["rang"]["ngay"], _("Rang {0}").format(n["rang"]["loai_dau"] or ""))
            di(n.get("con"))
    if goc.get("ngay_sx"):
        viec(goc["ngay_sx"], _("Làm {0}").format(goc["ten"]))
    if goc.get("rang"):
        viec(goc["rang"]["ngay"], _("Rang {0}").format(goc["rang"]["loai_dau"] or ""))
    di(nguoc)

    if ngay:
        ds = sorted(ngay)
        for r in _qc_cac_ngay(ds):
            ngay_cua(r.pop("ngay"))["qc"].append(r)
        for r in frappe.get_all(
                "SX Su Co", filters={"ngay": ("in", ds)},
                fields=["name", "ngay", "muc_do", "mo_ta", "trang_thai", "cong_doan", "nguon"],
                order_by="ngay"):
            ngay_cua(_d(r.ngay))["su_co"].append({
                "name": r.name, "muc_do": r.muc_do, "trang_thai": r.trang_thai,
                "cong_doan": r.cong_doan, "nguon": r.nguon,
                "mo_ta": (r.mo_ta or "")[:160]})
    return sorted(ngay.values(), key=lambda x: x["ngay"]), cua_so


def _vao_hop(item, tu, den):
    """{ngày: [{ten, so_hop}]} — ai đóng mã này, bao nhiêu hộp, từng ngày."""
    ten_ngay = {r.name: _d(r.ngay) for r in frappe.get_all(
        "SX Ngay San Xuat", filters={"ngay": ("between", (tu, den)), "docstatus": ("<", 2)},
        fields=["name", "ngay"])}
    if not ten_ngay:
        return {}
    bang = {b.name: ten_ngay.get(b.ngay_sx) for b in frappe.get_all(
        "SX Bang Vao Hop", filters={"ngay_sx": ("in", list(ten_ngay)), "docstatus": ("<", 2)},
        fields=["name", "ngay_sx"])}
    if not bang:
        return {}
    gop = {}
    for r in frappe.get_all(
            "SX Bang Vao Hop Item",
            filters={"parent": ("in", list(bang)), "parenttype": "SX Bang Vao Hop",
                     "san_pham": item},
            fields=["parent", "nhan_vien", "ten_nhan_vien", "cong_nhat", "so_hop"]):
        d = bang.get(r.parent)
        ten = _("Công nhật") if r.cong_nhat else (r.ten_nhan_vien or r.nhan_vien or "?")
        k = (d, ten)
        gop[k] = gop.get(k, 0) + cint(r.so_hop)
    ra = {}
    for (d, ten), so in gop.items():
        ra.setdefault(d, []).append({"ten": ten, "so_hop": so})
    for ds in ra.values():
        ds.sort(key=lambda x: -x["so_hop"])
    return ra


KHONG_DAT = "Không đạt"


def _qc_cac_ngay(ds):
    """Lượt kiểm QC của các ngày + những mục Không đạt (nhãn đọc được)."""
    try:
        vong = frappe.get_all("SX QC Round",
                              filters={"ngay": ("in", ds), "docstatus": ("<", 2)},
                              fields=["*"], order_by="ngay, started_at")
        meta = frappe.get_meta("SX QC Round")
    except Exception:
        return []   # site chưa cài module QC
    ra = []
    for v in vong:
        hong = [meta.get_label(k) or k for k, x in v.items()
                if x == KHONG_DAT and not k.startswith("_")]
        ra.append({"ngay": _d(v.ngay), "name": v.name, "luot": v.luot,
                   "nop": v.docstatus == 1, "duyet": bool(v.get("reviewed_by")),
                   "khong_dat": hong})
    return ra


def _luu_mau(goc, cua_so):
    """Mẫu lưu của đúng sản phẩm: ghi đúng mã lô / HSD, hoặc lấy trong các ngày làm."""
    if not goc["la_tp"]:
        return []
    try:
        ds = frappe.get_all(
            "SX QC Luu Mau", filters={"san_pham": goc["item"]},
            fields=["name", "lo", "ngay_lay", "so_luong", "dvt", "trang_thai", "vi_tri",
                    "han_luu", "anh"],
            order_by="ngay_lay desc", limit=200)
    except Exception:
        return []
    khoa = {goc["batch"].lower()}
    if goc.get("hsd"):
        y, m, d = goc["hsd"].split("-")
        khoa |= {f"{d}/{m}/{y}", f"{d}/{m}/{y[2:]}", f"{d}{m}{y[2:]}", goc["hsd"]}
    ra = []
    for r in ds:
        lo = (r.lo or "").lower()
        ngay_lay = _d(r.ngay_lay)
        theo_lo = any(k.lower() in lo for k in khoa)
        theo_ngay = bool(cua_so and ngay_lay and cua_so[0] <= ngay_lay <= _cong_ngay(cua_so[1], 1))
        if theo_lo or theo_ngay:
            ra.append({"name": r.name, "lo": r.lo, "ngay_lay": ngay_lay,
                       "so_luong": flt(r.so_luong), "dvt": r.dvt, "trang_thai": r.trang_thai,
                       "vi_tri": r.vi_tri, "han_luu": _d(r.han_luu), "co_anh": bool(r.anh),
                       "khop": "lô" if theo_lo else "ngày"})
    return ra


def _cong_ngay(d, n):
    return str(getdate(add_days(d, n)))


def _thu_hoi(batch):
    """Trạng thái thu hồi của lô + cờ người đang xem có được bật / gỡ không (W26)."""
    from sx.api.thuhoi import thong_tin

    return thong_tin(batch)


def _khieu_nai_theo_lo(batch):
    """Khiếu nại khách hàng BM.11.01 của lô (W13) — đúng lô, hoặc đúng sản phẩm + HSD."""
    from sx.api.qc_khieunai import theo_lo

    return theo_lo(batch)


def _su_co_theo_lo(batch):
    """Sự cố của lô: gắn ở bảng Lô liên quan (W11), hoặc ghi tên lô trong ô "lô ảnh
    hưởng" (tiếp nhận NL Không đạt, phiếu cũ trước D134…). Phiếu diễn tập có cờ."""
    truong = ["name", "ngay", "nguon", "muc_do", "trang_thai", "mo_ta"]
    try:
        ds = frappe.get_all("SX Su Co", filters={"lo_anh_huong": ("like", f"%{batch}%")},
                            fields=truong + ["dien_tap"], order_by="ngay desc", limit=20)
        gan = frappe.get_all("SX Su Co Lo", filters={"parenttype": "SX Su Co", "batch": batch},
                             pluck="parent", limit=50)
        co = {r.name for r in ds}
        if set(gan) - co:
            ds += frappe.get_all("SX Su Co", filters={"name": ("in", list(set(gan) - co))},
                                 fields=truong + ["dien_tap"], order_by="ngay desc")
    except Exception:
        try:
            ds = frappe.get_all("SX Su Co", filters={"lo_anh_huong": ("like", f"%{batch}%")},
                                fields=truong, order_by="ngay desc", limit=20)
        except Exception:
            return []
    ds.sort(key=lambda r: str(r.ngay or ""), reverse=True)
    return [{"name": r.name, "ngay": _d(r.ngay), "nguon": r.nguon, "muc_do": r.muc_do,
             "trang_thai": r.trang_thai, "mo_ta": (r.mo_ta or "")[:160],
             "dien_tap": cint(r.get("dien_tap"))} for r in ds[:20]]
