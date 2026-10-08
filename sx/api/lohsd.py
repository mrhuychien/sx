"""Lô thành phẩm CŨ chưa có HSD (W05, D131) — thẻ "Lô cũ chưa có HSD".

Trước D114 lô thành phẩm vào kho không mang HSD; trước D131 lô sinh theo NGÀY NHẬP
chứ không theo HSD. Lô không HSD thì truy xuất theo HSD in trên hộp không ra, xuất
FEFO và báo cận date bỏ sót. Thẻ này liệt kê các lô đó — lô còn tồn trước — kèm HSD
GỢI Ý = NSX (hoặc ngày tạo lô) + hạn dùng của mã; người soát theo bao bì rồi ghi.

Không tự ghi hàng loạt ở patch: HSD in trên hộp là sự thật, gợi ý chỉ là ước tính
(lô cũ sinh theo ngày NHẬP, có thể chứa hàng đóng vài ngày khác nhau).
Không ghi đè HSD đã có: thẻ chỉ điền chỗ TRỐNG.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from sx.config.roles import guard_card
from sx.utils import hsd_tu_nsx, items_tp, nap_cong_bo

CARD = "lohsd"
TOI_DA = 500


def _lo_trong(tp, ca_het_hang=False):
    if not tp:
        return []
    loc = {"item": ("in", tp), "expiry_date": ("is", "not set")}
    if not ca_het_hang:
        loc["batch_qty"] = (">", 0)
    return frappe.get_all(
        "Batch", filters=loc,
        fields=["name", "item", "item_name", "manufacturing_date", "batch_qty", "creation",
                "stock_uom"],
        order_by="creation asc", limit=TOI_DA)


@frappe.whitelist()
def danh_sach(ca_het_hang=0):
    """Lô TP chưa có HSD: mặc định chỉ lô CÒN TỒN (cái cần trước); `ca_het_hang=1`
    thêm lô đã bán hết (vẫn cần HSD để truy xuất khách đã mua)."""
    guard_card(CARD)
    tp = [i.name for i in items_tp(["name"])]
    ds = _lo_trong(tp, bool(cint(ca_het_hang)))
    nap_cong_bo(list({b.item for b in ds}))
    rows = []
    for b in ds:
        nsx = b.manufacturing_date or getdate(b.creation)
        rows.append({
            "batch": b.name, "item": b.item, "ten": b.item_name or b.item,
            "nsx": str(getdate(nsx)), "co_nsx": bool(b.manufacturing_date),
            "ton": flt(b.batch_qty, 3), "dvt": b.stock_uom or "",
            # Gợi ý = NSX + hạn dùng của mã (W28). None = mã chưa khai hạn dùng.
            "goi_y": hsd_tu_nsx(b.item, nsx),
        })
    rows.sort(key=lambda r: (r["ton"] <= 0, r["nsx"], r["ten"]))
    return {
        "rows": rows,
        "con_ton": sum(1 for r in rows if r["ton"] > 0),
        "het_hang": sum(1 for r in rows if r["ton"] <= 0) if cint(ca_het_hang)
        else (frappe.db.count("Batch", {"item": ("in", tp), "expiry_date": ("is", "not set"),
                                        "batch_qty": ("<=", 0)}) if tp else 0),
    }


@frappe.whitelist()
def dat_hsd(rows):
    """Ghi HSD cho các lô cũ. `rows` = [{batch, hsd}]. Chỉ điền lô CHƯA có HSD."""
    guard_card(CARD)
    rows = json.loads(rows) if isinstance(rows, str) else (rows or [])
    tp = {i.name for i in items_tp(["name"])}
    xong, loi = [], []
    for r in rows:
        b, h = r.get("batch"), r.get("hsd")
        if not b or not h:
            continue
        info = frappe.db.get_value("Batch", b, ["item", "item_name", "manufacturing_date",
                                                "expiry_date", "creation"], as_dict=True)
        if not info:
            loi.append(_("Không thấy lô {0}.").format(b))
            continue
        ten = info.item_name or info.item
        if info.item not in tp:
            loi.append(_("{0}: không phải thành phẩm.").format(ten))
            continue
        if info.expiry_date:
            loi.append(_("{0}: lô đã có HSD {1} — không ghi đè.").format(
                ten, frappe.utils.formatdate(info.expiry_date)))
            continue
        # Lô không có NSX thì so với ngày tạo lô — HSD trước cả ngày hàng vào kho là gõ nhầm.
        nsx = info.manufacturing_date or (getdate(info.creation) if info.creation else None)
        if nsx and getdate(h) <= getdate(nsx):
            loi.append(_("{0}: HSD {1} không sau ngày sản xuất / nhập {2}.").format(
                ten, frappe.utils.formatdate(h), frappe.utils.formatdate(nsx)))
            continue
        frappe.db.set_value("Batch", b, "expiry_date", str(getdate(h)))
        xong.append(b)
    return {"xong": len(xong), "loi": loi}
