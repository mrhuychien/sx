"""Vá lỗi của ERPNext ngay trong tiến trình — không sửa code ERPNext (D205).

Mỗi bản vá ghi rõ: lỗi gì, ở bản nào, vì sao vá đúng chỗ đó. Áp MỘT lần mỗi tiến trình qua hook
before_request / before_job (sx/hooks.py). Không đặt ở hooks.py hay sx/__init__.py: Frappe giữ hooks
trong cache, tiến trình mới không nhất thiết import lại app trước khi phục vụ yêu cầu.

1. get_item_details → update_stock khi KHÔNG kèm phiếu (doc=None)
   erpnext/stock/get_item_details.py (16.15.1 — vẫn còn ở 16.50): Stock Settings bật "Tự tạo gói Serial / Lô cho
   xuất kho" thì với phiếu POS (POS Invoice), mã CÓ LÔ, ERPNext tự chọn lô; trong vòng lặp chọn lô nó đọc
   doc.get("selling_price_list") mà không xét doc có hay không. Màn POS / app khác gọi get_item_details chỉ với
   ctx → AttributeError "'NoneType' object has no attribute 'get'": mã nào đã bật lô (kiểm kê 12/10/2026, D189)
   là không thêm vào giỏ POS được. Vá: doc rỗng → phiếu tạm {items: [], selling_price_list: bảng giá của ctx},
   CHỈ trong update_stock — đúng như có phiếu mà phiếu chưa có dòng nào (lô tự chọn như thường, giá theo lô tra
   theo bảng giá đang bán). Các bước khác của get_item_details (ngày, thuế, quy tắc giá) vẫn thấy doc=None như cũ.
"""

import frappe

_DA_VA = False


def va(*args, **kwargs):
    """Hook before_request / before_job: áp các bản vá, một lần mỗi tiến trình. Không bao giờ ném lỗi ra —
    hook này chạy trước MỌI yêu cầu, hỏng ở đây là hỏng cả site."""
    global _DA_VA
    if _DA_VA:
        return
    _DA_VA = True
    try:
        _va_update_stock()
    except Exception:
        frappe.log_error(title="sx: không áp được bản vá ERPNext (D205)", message=frappe.get_traceback())


def _va_update_stock():
    try:
        from erpnext.stock import get_item_details as gid
    except ImportError:
        return
    goc = getattr(gid, "update_stock", None)
    if goc is None or getattr(goc, "_sx_va", False):
        return

    def update_stock(ctx, out, doc=None):
        if doc is None:
            doc = frappe._dict(items=[], selling_price_list=ctx.get("price_list") or ctx.get("selling_price_list"))
        return goc(ctx, out, doc)

    update_stock._sx_va = True
    update_stock.__wrapped__ = goc
    gid.update_stock = update_stock
