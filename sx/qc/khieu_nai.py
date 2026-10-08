"""Sổ khiếu nại khách hàng BM.11.01 — ghi trên Issue của ERPNext (W13, D135).

Một khiếu nại = một Issue có tích "Là khiếu nại khách hàng" (custom_khieu_nai). Gắn LÔ
theo HSD: người khiếu nại chỉ cầm hộp, trên hộp chỉ có HSD — nên ô nhập là Sản phẩm +
HSD, app tự tìm lô (từ W05 mỗi (sản phẩm, HSD) là một lô). Có lô thì:
  · mẫu lưu của lô được GIỮ khi khiếu nại còn mở (sx/qc/giu_mau.py);
  · thẻ lô trong Truy xuất liệt kê khiếu nại của lô.

Luật ở `validate` (chặn cả đường Desk):
  · lô gắn phải là lô của đúng sản phẩm;
  · ĐÓNG (Resolved / Closed) phải có kết luận + xử lý với khách, và chỉ Trưởng Ban
    ISO / người được giao (sx/qc/quyen.py) — như phiếu sự cố (W11).

Issue không phải khiếu nại (ai đó dùng Issue cho việc khác) thì không đụng tới.
Không import gì ngoài frappe và module qc (ranh giới module).
"""

import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime

from sx.qc.quyen import duoc_dong_su_co

MO = ("Open", "Replied", "On Hold")
DONG = ("Resolved", "Closed")


def tim_lo(san_pham, hsd):
    """Lô của (sản phẩm, HSD) — None khi chưa có (hàng trước W05, gõ nhầm HSD…).
    Nhiều lô cùng HSD (dữ liệu cũ) thì lấy lô tạo sớm nhất: lô chính của ngày đó."""
    if not san_pham or not hsd:
        return None
    ds = frappe.get_all("Batch", filters={"item": san_pham, "expiry_date": getdate(hsd)},
                        pluck="name", order_by="creation asc", limit=1)
    return ds[0] if ds else None


def _doi(doc, truong):
    if doc.is_new():
        return True
    return doc.has_value_changed(truong)


def validate(doc, method=None):
    if not cint(doc.get("custom_khieu_nai")):
        return
    gan_lo(doc)
    if doc.status in DONG and _doi(doc, "status"):
        if getattr(frappe.flags, "in_scheduler", False) and not doc.is_new():
            # ERPNext tự đóng Issue "Replied" sau N ngày (auto_close_tickets). Khiếu nại
            # thì không tự đóng: chưa có kết luận là còn việc — giữ trạng thái cũ, im lặng
            # (ném lỗi ở đây là chặn luôn việc tự đóng các Issue khác cùng lượt).
            cu = doc.get_doc_before_save()
            doc.status = cu.status if cu else "Open"
            return
        if not duoc_dong_su_co():
            frappe.throw(_("Chỉ Trưởng Ban ISO hoặc người được giao mới đóng được khiếu nại — "
                           "người tiếp nhận không tự đóng."), frappe.PermissionError)
        thieu = []
        if not doc.get("custom_ket_luan_kn"):
            thieu.append(_("Kết luận"))
        if not (doc.get("custom_xu_ly_kh") or "").strip():
            thieu.append(_("Xử lý với khách"))
        if thieu:
            frappe.throw(_("Chưa đóng được khiếu nại — còn thiếu: {0}.").format(", ".join(thieu)))
        doc.custom_dong_boi_kn = frappe.session.user
        doc.custom_dong_luc_kn = now_datetime()
    elif doc.status in MO and not doc.is_new() and doc.has_value_changed("status"):
        # Mở lại khiếu nại đã đóng: cũng là việc của người có quyền đóng.
        cu = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
        if cu and cu.status in DONG and not duoc_dong_su_co():
            frappe.throw(_("Chỉ Trưởng Ban ISO hoặc người được giao mới mở lại được khiếu nại."),
                         frappe.PermissionError)
        doc.custom_dong_boi_kn = None
        doc.custom_dong_luc_kn = None


def gan_lo(doc):
    """Sản phẩm + HSD → lô; có lô mà thiếu sản phẩm / HSD → điền từ lô; lô khác mã → chặn."""
    if doc.get("custom_lo"):
        b = frappe.db.get_value("Batch", doc.custom_lo, ["item", "expiry_date"], as_dict=True)
        if not b:
            frappe.throw(_("Không thấy lô {0}.").format(doc.custom_lo))
        if doc.get("custom_san_pham") and b.item != doc.custom_san_pham:
            # Đổi sản phẩm / HSD sau khi đã có lô: tìm lại theo cặp mới thay vì chặn.
            moi = tim_lo(doc.custom_san_pham, doc.get("custom_hsd"))
            if not moi:
                frappe.throw(_("Lô {0} là của mã {1}, không phải {2}.").format(
                    doc.custom_lo, b.item, doc.custom_san_pham))
            doc.custom_lo = moi
            return
        if (doc.get("custom_hsd") and b.expiry_date
                and getdate(doc.custom_hsd) != getdate(b.expiry_date)):
            doc.custom_lo = tim_lo(doc.get("custom_san_pham") or b.item, doc.custom_hsd)
            return
        doc.custom_san_pham = doc.get("custom_san_pham") or b.item
        doc.custom_hsd = doc.get("custom_hsd") or b.expiry_date
        return
    doc.custom_lo = tim_lo(doc.get("custom_san_pham"), doc.get("custom_hsd"))


def dang_mo():
    """Khiếu nại đang mở có lô / HSD — cho giữ mẫu: [{name, lo: [mã lô], san_pham, hsd}].
    Khớp mẫu theo LÔ, hoặc đúng SẢN PHẨM + HSD (mẫu ghi tay không gắn lô) — không khớp
    theo chữ như phiếu sự cố: khiếu nại biết rõ sản phẩm nào, giữ nhầm mã khác cùng HSD
    là tủ mẫu đầy thứ không ai cần. Site chưa có các trường khiếu nại → []."""
    try:
        ds = frappe.get_all("Issue", filters={"custom_khieu_nai": 1, "status": ("in", list(MO))},
                            fields=["name", "custom_lo", "custom_san_pham", "custom_hsd"])
    except Exception:
        return []
    return [{"name": x["name"], "lo": [x["custom_lo"]] if x.get("custom_lo") else [],
             "san_pham": x.get("custom_san_pham"), "hsd": x.get("custom_hsd")}
            for x in ds if x.get("custom_lo") or (x.get("custom_san_pham") and x.get("custom_hsd"))]
