"""Phiếu POS: dòng bán nhiều hơn số còn của lô đang gắn → tự chia sang các lô khác (D221).

Màn POS của ERPNext gắn MỖI DÒNG MỘT LÔ (ô batch_no): chọn mã là nó lấy lô đầu tiên còn hàng — lúc đó số lượng mới
là 1 (erpnext/stock/get_item_details.update_stock) — rồi tăng số lượng thì dòng vẫn mang lô đó. Màn POS chỉ kiểm TỔNG
tồn của mã, không kiểm từng lô; tới lúc thanh toán ERPNext dựng gói lô MỘT lô cho cả số lượng của dòng (on_submit) và
báo lô âm ("Batch No … has negative stock") — dù các lô cộng lại thừa đủ.

Ở đây (before_submit, trước khi ERPNext dựng gói lô): dòng có lô mà lô đó không đủ — số còn ERPNext tính (đã trừ phiếu
POS khác chưa đóng ca, hàng giữ chỗ; bỏ lô hết hạn), trừ tiếp phần các dòng trước của chính phiếu này — thì lấy hết
phần còn của lô đó, phần thiếu lấy lần lượt các lô khác theo HSD gần trước (FEFO). Lô đang thu hồi (W26) / chưa duyệt
xuất xưởng (W08) xếp sau cùng: chỉ đụng tới khi lô bán được không đủ — để chốt bán báo đúng lý do thay cho "lô âm".
Ghi thành MỘT gói lô (Serial and Batch Bundle) nhiều lô cho dòng đó: dòng, giá, tiền không đổi; đóng ca gộp hoá đơn
mang nguyên gói lô sang hoá đơn bán. Các lô cộng lại vẫn không đủ thì để nguyên — ERPNext báo như cũ. Phiếu trả hàng
không xét.
"""

import frappe
from frappe.utils import cint, flt

EPS = 1e-9


def chia(can, co):
    """Hàm thuần: lấy đủ `can` từ các lô `co` = [(lô, số còn)] theo đúng thứ tự đưa vào. Trả {lô: số}; None khi các
    lô cộng lại không đủ."""
    ra, con = {}, flt(can)
    for b, q in co:
        lay = min(flt(q), con)
        if lay > EPS:
            ra[b] = ra.get(b, 0.0) + lay
            con -= lay
    return ra if con <= EPS else None


def chia_lo(doc, method=None):
    """Hook before_submit của POS Invoice."""
    if cint(doc.get("is_return")):
        return
    ton, dung = {}, {}
    for r in doc.get("items") or []:
        b = r.get("batch_no")
        if not b or r.get("serial_and_batch_bundle") or not r.get("warehouse"):
            continue
        can = flt(r.get("stock_qty")) or flt(r.get("qty")) * (flt(r.get("conversion_factor")) or 1)
        if can <= EPS:
            continue
        k = (r.item_code, r.warehouse)
        if k not in ton:
            ton[k] = _con_lai(doc, r.item_code, r.warehouse)
        da = dung.setdefault(k, {})
        con = [(x, flt(q) - da.get(x, 0.0)) for x, q in ton[k].items()]
        if dict(con).get(b, 0.0) + EPS >= can:
            da[b] = da.get(b, 0.0) + can
            continue
        khoa = _lo_khoa([x for x, _q in con])
        thu_tu = sorted(range(len(con)), key=lambda i: (con[i][0] in khoa, con[i][0] != b, i))
        phan = chia(can, [con[i] for i in thu_tu])
        if not phan:
            continue
        r.serial_and_batch_bundle = _tao_goi(doc, r, can, phan)
        r.batch_no = None
        r.use_serial_batch_fields = 0
        for x, q in phan.items():
            da[x] = da.get(x, 0.0) + q


def _con_lai(doc, item, kho):
    """{lô: số còn} của mã tại kho lúc ghi phiếu, xếp HSD gần trước — đúng cách ERPNext tính khi tự chọn lô (đã trừ phiếu
    POS chưa đóng ca, hàng giữ chỗ; bỏ lô hết hạn / tắt)."""
    from erpnext.stock.doctype.batch.batch import get_available_batches

    return get_available_batches(frappe._dict({
        "item_code": item, "warehouse": kho, "company": doc.get("company"), "based_on": "Expiry",
        "posting_date": doc.get("posting_date"), "posting_time": doc.get("posting_time"),
    }))


def _lo_khoa(ds):
    """Lô không bán được: đang thu hồi (W26) hoặc chưa duyệt xuất xưởng BM.08.04 (W08)."""
    from sx.api.thuhoi import lo_dang_thu_hoi
    from sx.api.xuatxuong import lo_chua_duyet

    return set(lo_dang_thu_hoi(ds)) | set(lo_chua_duyet(ds))


def _tao_goi(doc, r, can, phan):
    """Gói lô NHÁP nhiều lô cho dòng `r` (POS Invoice on_submit gửi nó cùng phiếu) — tên gói."""
    from erpnext.stock.serial_batch_bundle import SerialBatchCreation
    from erpnext.stock.utils import get_combine_datetime

    return SerialBatchCreation({
        "item_code": r.item_code, "warehouse": r.warehouse, "company": doc.get("company"),
        "voucher_type": doc.doctype, "voucher_no": doc.name, "voucher_detail_no": r.name,
        "posting_datetime": get_combine_datetime(doc.get("posting_date"), doc.get("posting_time")),
        "qty": can, "type_of_transaction": "Outward", "batches": frappe._dict(phan), "do_not_submit": True,
    }).make_serial_and_batch_bundle().name
