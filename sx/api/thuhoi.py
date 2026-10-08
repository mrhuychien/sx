"""Hàng trả về vào kho riêng, khoá xuất lô thu hồi (W26, D136).

HÀNG TRẢ VỀ (Sales Invoice / Delivery Note trả hàng có trừ kho) nhập vào KHO HÀNG TRẢ
VỀ (SX Settings → kho_hang_tra_ve), không vào lại kho bán: hàng khách trả là hàng chưa
biết tình trạng. Muốn bán lại thì QC đánh giá rồi chuyển kho (Stock Entry) — bán thẳng
từ kho trả về bị chặn.

LÔ THU HỒI: Ban ISO / quản lý bấm "Thu hồi lô" trên thẻ lô (Truy xuất) → Batch có cờ
custom_thu_hoi. Từ lúc đó MỌI chứng từ đưa lô ra khỏi kho bị chặn lúc submit:
  · bán (Sales Invoice trừ kho, Delivery Note, POS Invoice) — trừ phiếu TRẢ HÀNG (đó
    chính là hàng thu hồi quay về);
  · Stock Entry: chỉ cho CHUYỂN vào kho hàng trả về / kho cách ly, hoặc XUẤT HUỶ
    (Material Issue). Đưa vào sản xuất / đóng gói lại / chuyển sang kho khác → chặn.

Chặn ở cả before_submit (lô chọn bằng ô batch_no / bundle có sẵn) lẫn on_submit (lô do
ERPNext TỰ CHỌN khi dòng để trống — bundle chỉ sinh ra trong on_submit; ném lỗi ở đây
cuộn lại cả chứng từ). Gỡ cờ thu hồi: chỉ Ban ISO / người được giao (cả Desk).
"""

import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime

from sx.config.roles import guard_card
from sx.qc.quyen import duoc_dong_su_co
from sx.utils import get_settings

BAN = ("Sales Invoice", "Delivery Note", "POS Invoice")
SE_DUOC = ("Material Issue",)          # xuất huỷ lô thu hồi: được


def _kho(settings=None):
    s = settings or get_settings()
    return s.get("kho_hang_tra_ve") or None


def _kho_cach_ly(settings=None):
    s = settings or get_settings()
    return s.get("kho_cach_ly") or None


# ═════════════════════════════════ hàng trả về ═════════════════════════════════

def kho_tra_ve(doc, method=None):
    """validate: phiếu trả hàng có trừ kho → mọi dòng hàng tồn kho nhập vào kho trả về."""
    if not cint(doc.get("is_return")):
        return
    if doc.doctype == "Sales Invoice" and not cint(doc.get("update_stock")):
        return
    kho = _kho()
    if not kho:
        frappe.msgprint(_("Chưa khai Kho hàng trả về (SX Settings) — hàng trả về đang nhập "
                          "lại kho bán, lẫn với hàng tốt."), indicator="orange",
                        title=_("Hàng trả về"))
        return
    doi = []
    for r in doc.get("items") or []:
        if not r.get("item_code") or not cint(frappe.get_cached_value("Item", r.item_code,
                                                                      "is_stock_item")):
            continue
        if r.get("warehouse") != kho:
            r.warehouse = kho
            doi.append(str(r.idx))
    if doi:
        frappe.msgprint(_("Hàng trả về nhập vào {0} (dòng {1}) — QC đánh giá rồi mới chuyển "
                          "về kho bán.").format(kho, ", ".join(doi)), indicator="blue",
                        alert=True)


# ═════════════════════════════════ lô thu hồi ══════════════════════════════════

def _lo_cac_dong(doc, bang=("items", "packed_items")):
    """[(dòng, mã lô)] — lô ở ô batch_no và trong Serial and Batch Bundle của dòng."""
    ra, theo_bundle = [], {}
    for f in bang:
        for r in doc.get(f) or []:
            if r.get("batch_no"):
                ra.append((r, r.batch_no))
            if r.get("serial_and_batch_bundle"):
                theo_bundle.setdefault(r.serial_and_batch_bundle, []).append(r)
    if theo_bundle:
        for e in frappe.get_all("Serial and Batch Entry",
                                filters={"parent": ("in", list(theo_bundle))},
                                fields=["parent", "batch_no"]):
            for r in theo_bundle.get(e.parent, []):
                if e.batch_no and (r, e.batch_no) not in ra:
                    ra.append((r, e.batch_no))
    return ra


def lo_dang_thu_hoi(ds):
    """{mã lô: {ly_do, item, hsd}} cho các lô đang thu hồi trong `ds`. Chưa migrate → {}."""
    ds = [b for b in set(ds) if b]
    if not ds:
        return {}
    try:
        return {b.name: b for b in frappe.get_all(
            "Batch", filters={"name": ("in", ds), "custom_thu_hoi": 1},
            fields=["name", "item", "item_name", "expiry_date", "custom_ly_do_thu_hoi"])}
    except Exception:
        return {}


def _nhan(b):
    if b.get("expiry_date"):
        return _("{0} HSD {1}").format(b.item_name or b.item, getdate(b.expiry_date).strftime("%d/%m/%Y"))
    return f"{b.item_name or b.item} · {b.name}"


def kiem_xuat(doc, method=None):
    """before_submit + on_submit của chứng từ xuất: chặn lô thu hồi, chặn bán từ kho trả về."""
    if doc.doctype in BAN:
        if cint(doc.get("is_return")):
            return
        if doc.doctype == "Sales Invoice" and not cint(doc.get("update_stock")):
            return
        kho = _kho()
        if kho:
            tu_kho = [r for r in doc.get("items") or [] if r.get("warehouse") == kho]
            if tu_kho:
                frappe.throw(_("Không bán thẳng từ kho hàng trả về ({0}) — dòng {1}. QC đánh giá "
                               "rồi chuyển kho (Stock Entry) trước khi bán lại.").format(
                    kho, ", ".join(str(r.idx) for r in tu_kho)), title=_("Hàng trả về"))
        cap = _lo_cac_dong(doc)
        th = lo_dang_thu_hoi([b for _r, b in cap])
        sai = [(r, th[b]) for r, b in cap if b in th]
        if sai:
            frappe.throw(_("Lô đang THU HỒI — không bán / giao được:") + "<br>" + "<br>".join(
                _("• Dòng {0}: {1} — {2}").format(r.idx, _nhan(b), b.custom_ly_do_thu_hoi or "")
                for r, b in sai), title=_("Lô thu hồi"))
        return
    if doc.doctype != "Stock Entry":
        return
    cap = [(r, b) for r, b in _lo_cac_dong(doc, ("items",)) if r.get("s_warehouse")]
    th = lo_dang_thu_hoi([b for _r, b in cap])
    if not th:
        return
    if doc.get("purpose") in SE_DUOC:
        return
    duoc_vao = {k for k in (_kho(), _kho_cach_ly()) if k}
    sai = [(r, th[b]) for r, b in cap if b in th
           and not (doc.get("purpose") == "Material Transfer" and r.get("t_warehouse") in duoc_vao)]
    if sai:
        frappe.throw(_("Lô đang THU HỒI — chỉ được chuyển vào kho hàng trả về / kho cách ly, hoặc "
                       "xuất huỷ (Material Issue):") + "<br>" + "<br>".join(
            _("• Dòng {0}: {1}").format(r.idx, _nhan(b)) for r, b in sai), title=_("Lô thu hồi"))


def kiem_sua_batch(doc, method=None):
    """Batch.validate: bật / gỡ cờ thu hồi trên Desk chỉ Ban ISO / người được giao."""
    if doc.is_new():
        return
    if doc.has_value_changed("custom_thu_hoi") and not duoc_dong_su_co():
        frappe.throw(_("Chỉ Trưởng Ban ISO hoặc người được giao mới thu hồi / gỡ thu hồi lô."),
                     frappe.PermissionError)


# ═════════════════════════════════ API thẻ lô ══════════════════════════════════

def _guard():
    guard_card("truyxuat")
    if not duoc_dong_su_co():
        frappe.throw(_("Chỉ Trưởng Ban ISO hoặc người được giao mới thu hồi / gỡ thu hồi lô."),
                     frappe.PermissionError)


@frappe.whitelist()
def thu_hoi_lo(batch, ly_do, su_co=None):
    """Thu hồi một lô: khoá xuất ngay. Không chỉ ra phiếu sự cố / khiếu nại nào thì lập
    phiếu sự cố mới (nguồn Phát hiện khác, mức Cao, gắn lô) — thu hồi phải có hồ sơ."""
    _guard()
    ly_do = (ly_do or "").strip()
    if not ly_do:
        frappe.throw(_("Ghi lý do thu hồi."))
    b = frappe.db.get_value("Batch", batch, ["name", "item", "item_name", "expiry_date",
                                             "custom_thu_hoi"], as_dict=True)
    if not b:
        frappe.throw(_("Không thấy lô {0}.").format(batch))
    if cint(b.custom_thu_hoi):
        frappe.throw(_("Lô {0} đang thu hồi rồi.").format(_nhan(b)))
    if su_co and not frappe.db.exists("SX Su Co", su_co):
        frappe.throw(_("Không thấy phiếu sự cố {0}.").format(su_co))
    if not su_co:
        sc = frappe.get_doc({
            "doctype": "SX Su Co", "ngay": getdate(), "nguon": "Phát hiện khác", "loai": "Khác",
            "muc_do": "Cao", "trang_thai": "Mở",
            "mo_ta": _("Thu hồi lô {0}: {1}").format(_nhan(b), ly_do)[:1000],
        })
        sc.append("ds_lo", {"batch": batch})
        sc.insert(ignore_permissions=True)
        su_co = sc.name
    frappe.db.set_value("Batch", batch, {
        "custom_thu_hoi": 1, "custom_ly_do_thu_hoi": ly_do, "custom_su_co_thu_hoi": su_co,
        "custom_thu_hoi_boi": frappe.session.user, "custom_thu_hoi_luc": now_datetime()})
    return {"batch": batch, "su_co": su_co}


@frappe.whitelist()
def go_thu_hoi(batch, ly_do):
    """Gỡ thu hồi (đã xử lý xong / thu hồi nhầm) — bắt buộc lý do, ghi nối vào lý do cũ."""
    _guard()
    ly_do = (ly_do or "").strip()
    if not ly_do:
        frappe.throw(_("Ghi lý do gỡ thu hồi."))
    b = frappe.db.get_value("Batch", batch, ["custom_thu_hoi", "custom_ly_do_thu_hoi"], as_dict=True)
    if not b or not cint(b.custom_thu_hoi):
        frappe.throw(_("Lô {0} không đang thu hồi.").format(batch))
    frappe.db.set_value("Batch", batch, {
        "custom_thu_hoi": 0,
        "custom_ly_do_thu_hoi": ((b.custom_ly_do_thu_hoi or "") + "\n" + _(
            "[Gỡ {0} — {1}] {2}").format(getdate().strftime("%d/%m/%Y"), frappe.session.user,
                                         ly_do)).strip()})
    return {"batch": batch}


@frappe.whitelist()
def ds_thu_hoi():
    """Các lô đang thu hồi — cho đầu thẻ Truy xuất."""
    guard_card("truyxuat")
    try:
        ds = frappe.get_all("Batch", filters={"custom_thu_hoi": 1},
                            fields=["name", "item", "item_name", "expiry_date", "batch_qty",
                                    "custom_ly_do_thu_hoi", "custom_thu_hoi_luc",
                                    "custom_su_co_thu_hoi"],
                            order_by="custom_thu_hoi_luc desc", limit=50)
    except Exception:
        return []
    return [{"batch": b.name, "ten": b.item_name or b.item,
             "hsd": str(b.expiry_date) if b.expiry_date else "", "ton": b.batch_qty or 0,
             "ly_do": (b.custom_ly_do_thu_hoi or "").split("\n")[0],
             "luc": str(b.custom_thu_hoi_luc or "")[:10], "su_co": b.custom_su_co_thu_hoi or ""}
            for b in ds]


def thong_tin(batch):
    """Trạng thái thu hồi của một lô — cho thẻ lô (truyxuat.lo). Chưa migrate → không thu hồi."""
    try:
        b = frappe.db.get_value("Batch", batch, ["custom_thu_hoi", "custom_ly_do_thu_hoi",
                                                 "custom_thu_hoi_luc", "custom_thu_hoi_boi",
                                                 "custom_su_co_thu_hoi"], as_dict=True) or {}
    except Exception:
        b = {}
    return {"dang": bool(cint(b.get("custom_thu_hoi"))),
            "ly_do": b.get("custom_ly_do_thu_hoi") or "",
            "luc": str(b.get("custom_thu_hoi_luc") or "")[:16], "boi": b.get("custom_thu_hoi_boi") or "",
            "su_co": b.get("custom_su_co_thu_hoi") or "", "duoc": duoc_dong_su_co()}
