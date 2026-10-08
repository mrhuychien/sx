"""Bán hàng trừ kho phải ghi ĐÚNG LÔ thành phẩm (W06, D132).

Truy xuất xuôi ("lô này bán cho ai") chỉ đúng khi mỗi dòng bán ghi đúng lô (HSD) đã
giao. ERPNext v16 mặc định TỰ CHỌN lô khi dòng bán bỏ trống (Stock Settings → Auto
Create Serial and Batch Bundle For Outward, chọn FIFO / theo HSD) — hoá đơn vẫn qua,
nhưng lô ghi trên sổ là lô máy đoán, có thể khác lô trên thùng hàng đã giao. Đến lúc
thu hồi thì gọi nhầm khách.

Nên ở đây: hoá đơn bán TRỪ KHO (Sales Invoice có "Update Stock", hoặc Delivery Note)
mà dòng thành phẩm có quản lý lô chưa chọn lô → CHẶN lúc submit, nói rõ dòng nào.
Mã thành phẩm KHÔNG quản lý lô (mã cũ có giao dịch trước khi bật lô — D103) thì
không chọn lô được: không chặn (chặn là dừng bán), chỉ CẢNH BÁO để quản lý biết mã đó
mất truy xuất xuôi.

Tắt được ở SX Settings → "Bắt chọn lô khi bán thành phẩm" (mặc định bật).
Phiếu trả hàng (is_return) không xét: lô trả về lấy theo hoá đơn gốc.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from sx.utils import get_settings, items_tp


def _bat(settings):
    v = settings.get("chan_ban_thieu_lo")
    return True if v is None else bool(cint(v))      # chưa migrate → bật


def kiem_lo_ban(doc, method=None):
    if doc.doctype == "Sales Invoice" and not cint(doc.get("update_stock")):
        return
    if cint(doc.get("is_return")):
        return
    if not _bat(get_settings()):
        return
    tp = {i.name for i in items_tp(["name"])}
    thieu, khong_lo = [], []
    for r in doc.get("items") or []:
        if r.item_code not in tp or flt(r.get("qty")) <= 0:
            continue
        if not cint(frappe.get_cached_value("Item", r.item_code, "has_batch_no")):
            khong_lo.append(r)
            continue
        if not (r.get("batch_no") or r.get("serial_and_batch_bundle")):
            thieu.append(r)
    if thieu:
        frappe.throw(
            _("Chưa chọn lô (HSD) cho:") + "<br>"
            + "<br>".join(_("• Dòng {0}: {1}").format(r.idx, r.item_name or r.item_code)
                          for r in thieu)
            + "<br><br>" + _("Chọn đúng lô theo HSD in trên thùng hàng giao (ô Batch No / "
                             "Serial and Batch Bundle của dòng). Để trống thì ERPNext tự chọn "
                             "lô — có thể khác lô đã giao, truy xuất gọi nhầm khách."),
            title=_("Thiếu lô thành phẩm"))
    if khong_lo:
        frappe.msgprint(
            _("Các mã sau không quản lý theo lô nên KHÔNG ghi được lô bán ra — mất truy "
              "xuất xuôi (không biết khách nào nhận lô nào):") + "<br>"
            + "<br>".join(f"• {r.item_name or r.item_code}" for r in khong_lo)
            + "<br>" + _("Muốn truy xuất được: tạo mã hàng mới có tích 'Has Batch No'."),
            title=_("Bán mã không có lô"), indicator="orange")
