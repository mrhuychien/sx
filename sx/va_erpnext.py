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

2. update_stock điền ô lô khi MỘT lô không đủ số của dòng (D223)
   Cùng hàm: dòng chưa có lô thì ERPNext đi lần các lô (theo Stock Settings) trừ dần số cần, và GHI ĐÈ ô lô mỗi vòng
   → dòng mang lô CUỐI CÙNG cần tới, không phải lô đầu. Gặp khi số lượng đã có lúc điền lô: hoá đơn / phiếu giao lập
   từ đơn hàng, lưu hoá đơn có dòng chưa chọn lô. Thật (23/10/2026): đơn 600 hộp, lô HSD 10/6 còn 11, 25/6 còn 31,
   10/7 còn 558 → dòng mang lô 10/7. Đơn 300 hộp thì lô 10/7 đủ → ghi cả 300 vào lô HSD xa nhất, không báo gì; hai lô
   cũ vẫn nằm trên sổ dù kho đã xuất. Vá: dòng cần hơn một lô thì ô lô = lô HSD GẦN NHẤT còn hàng (trừ phần các dòng
   khác của phiếu đã lấy, như ERPNext); lúc gửi sx.api.pos_lo chia phần thiếu theo HSD (D221 / D222). Giá theo lô (nếu
   có) theo lô mới. Lô người lập chọn, dòng một lô đủ số: không đụng. Bản vá lỗi thì giữ lô ERPNext chọn, ghi Error Log.
"""

import frappe
from frappe.utils import flt

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
        ra = goc(ctx, out, doc)
        try:
            _lo_hsd_gan(ctx, out, doc)
        except Exception:
            frappe.log_error(title="sx: vá ô lô tự điền (D223) lỗi — giữ lô ERPNext chọn", message=frappe.get_traceback())
        return ra

    update_stock._sx_va = True
    update_stock.__wrapped__ = goc
    gid.update_stock = update_stock


def _lo_hsd_gan(ctx, out, doc):
    """Bản vá 2 (đầu module): ERPNext vừa tự điền ô lô mà một lô không đủ số của dòng → lô HSD gần nhất còn hàng."""
    if (ctx.get("batch_no") or not out.get("batch_no") or out.get("has_serial_no")
            or flt(out.get("actual_batch_qty")) + 1e-9 >= flt(out.get("stock_qty"))):
        return
    from erpnext.stock.doctype.batch.batch import get_available_batches
    from erpnext.stock.get_item_details import filter_batches, get_batch_based_item_price

    kw = frappe._dict({"item_code": ctx.item_code, "warehouse": ctx.warehouse, "based_on": "Expiry",
                       "sabb_voucher_no": doc.get("name"), "sabb_voucher_detail_no": ctx.child_docname,
                       "sabb_voucher_type": ctx.doctype, "pick_reserved_items": True})
    if ctx.get("doctype") == "Delivery Note":
        kw["against_sales_order"] = ctx.get("against_sales_order")
    lo = get_available_batches(kw)
    filter_batches(lo, doc)
    dau = next(iter(lo), None)          # ERPNext chỉ trả lô còn hàng; filter_batches bỏ lô các dòng khác lấy hết
    if not dau:
        return
    out.update({"batch_no": dau, "actual_batch_qty": flt(lo[dau])})
    gia = get_batch_based_item_price({"price_list": doc.get("selling_price_list"), "uom": out.uom, "batch_no": dau},
                                     out.item_code)
    if gia:
        out.update({"rate": gia, "price_list_rate": gia})
