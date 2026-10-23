"""Chứng từ bán: dòng bán nhiều hơn số còn của lô đang gắn → tự chia sang các lô khác (D221 phiếu POS; D222 hoá đơn bán
trừ kho, phiếu giao).

ERPNext gắn MỖI DÒNG MỘT LÔ (ô batch_no): chọn mã là nó điền lô đầu tiên còn hàng — lúc đó số lượng mới là 1
(erpnext/stock/get_item_details.update_stock; màn POS và hoá đơn / phiếu giao trên Desk như nhau) — rồi tăng số lượng thì
dòng vẫn mang lô đó; người lập chọn tay cũng chỉ một ô lô. Màn POS chỉ kiểm TỔNG tồn của mã, không kiểm từng lô; tới lúc
gửi ERPNext dựng gói lô MỘT lô cho cả số lượng của dòng (on_submit) và báo lô âm ("Batch No … has negative stock") — dù
các lô cộng lại thừa đủ.

Ở đây (before_submit, trước khi ERPNext dựng gói lô): dòng có lô mà lô đó không đủ — số còn ERPNext tính (đã trừ phiếu
POS khác chưa đóng ca, hàng giữ chỗ; bỏ lô hết hạn), trừ tiếp phần các dòng trước của chính phiếu này; chứng từ đặt tay
ngày giờ ghi sổ thì lấy số nhỏ hơn giữa lúc ghi sổ và hiện tại — thì lấy hết phần còn của lô đó, phần thiếu lấy lần lượt
các lô khác theo HSD gần trước (FEFO). Lô đang thu hồi (W26) / chưa duyệt xuất xưởng (W08) xếp sau cùng: chỉ đụng tới khi
lô bán được không đủ — để chốt bán báo đúng lý do thay cho "lô âm". Phiếu POS: cả lô đang gắn bị khoá cũng xuống cuối
(ERPNext tự gắn, thu ngân không chọn). Hoá đơn / phiếu giao: lô đang gắn luôn lấy trước (W06 — người lập chọn theo thùng
hàng giao; lô đó bị khoá thì chốt bán chặn, không lặng lẽ đổi lô), gửi xong báo lại các dòng đã chia (bao_chia) để đối
chiếu. Ghi thành MỘT gói lô (Serial and Batch Bundle) nhiều lô cho dòng đó: dòng, giá, tiền không đổi; đóng ca gộp hoá
đơn mang nguyên gói lô sang hoá đơn bán. Các lô cộng lại vẫn không đủ thì để nguyên — ERPNext báo như cũ.

Không xét: phiếu trả hàng; hoá đơn không trừ kho; hoá đơn gộp từ POS lúc đóng ca (dòng đã mang lô từ phiếu POS / lo_cu
gán lô; các phiếu POS đang gộp còn tính là hàng giữ chỗ).
"""

from collections import OrderedDict

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

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


def _xet(doc):
    """Chứng từ cần chia lô (xem đầu module)."""
    if cint(doc.get("is_return")):
        return False
    if doc.doctype == "Sales Invoice":
        return bool(cint(doc.get("update_stock")) and not cint(doc.get("is_consolidated")))
    return True


def chia_lo(doc, method=None):
    """Hook before_submit của POS Invoice, Sales Invoice, Delivery Note."""
    if not _xet(doc):
        return
    giu = doc.doctype != "POS Invoice"
    ton, dung, da_chia = {}, {}, []
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
        co_b = dict(con).get(b, 0.0)
        if co_b + EPS >= can:
            da[b] = da.get(b, 0.0) + can
            continue
        khoa = _lo_khoa([x for x, _q in con])
        # sorted giữ thứ tự HSD gần trước của ERPNext cho các lô cùng hạng
        phan = chia(can, sorted(con, key=lambda x: (not (giu and x[0] == b), x[0] in khoa, x[0] != b)))
        if not phan:
            continue
        r.serial_and_batch_bundle = _tao_goi(doc, r, can, phan)
        r.batch_no = None
        r.use_serial_batch_fields = 0
        for x, q in phan.items():
            da[x] = da.get(x, 0.0) + q
        da_chia.append(frappe._dict(idx=r.get("idx"), ten=r.get("item_name") or r.item_code, can=can, lo=b, con=co_b,
                                    phan=phan))
    if da_chia:
        doc.flags.sx_chia_lo = da_chia


def bao_chia(doc, method=None):
    """on_submit của Sales Invoice / Delivery Note — đứng cuối, gửi xong mới báo: các dòng chia_lo đã lấy thêm lô khác,
    để người lập đối chiếu với lô trên thùng hàng đã giao (truy xuất xuôi W06)."""
    ds = doc.flags.sx_chia_lo
    if not ds:
        return
    from sx.api.kiemke import so_vn

    hsd = {x.name: x.expiry_date for x in frappe.get_all(
        "Batch", filters={"name": ("in", sorted({b for x in ds for b in x.phan}))}, fields=["name", "expiry_date"])}

    def lo(b, q):
        return f"{b} {so_vn(q)}" + (f" (HSD {getdate(hsd[b]).strftime('%d/%m/%Y')})" if hsd.get(b) else "")

    frappe.msgprint(
        _("Lô đang chọn không đủ số bán — đã lấy thêm lô khác (HSD gần trước):") + "<br>" + "<br>".join(
            _("• Dòng {0} · {1}: bán {2}, lô {3} {4} → ghi {5}").format(
                x.idx, x.ten, so_vn(x.can), x.lo,
                _("chỉ còn {0}").format(so_vn(x.con)) if x.con > EPS else _("không còn hàng bán được"),
                " + ".join(lo(b, q) for b, q in x.phan.items()))
            for x in ds)
        + "<br><br>" + _("Đối chiếu với lô trên thùng hàng đã giao. Sai lô: huỷ chứng từ, chọn lại lô cho dòng (nhiều "
                         "lô thì chọn trong gói lô của dòng) rồi gửi lại."),
        title=_("Đã chia lô"), indicator="orange")


def _con_lai(doc, item, kho):
    """{lô: số còn} của mã tại kho lúc ghi phiếu, xếp HSD gần trước — đúng cách ERPNext tính khi tự chọn lô (đã trừ phiếu
    POS chưa đóng ca, hàng giữ chỗ; bỏ lô hết hạn / tắt). Chứng từ đặt tay ngày giờ ghi sổ (ghi lùi): lấy số nhỏ hơn giữa
    lúc ghi sổ và hiện tại — lô đã bán bớt sau lúc đó, lô có hàng sau lúc đó không lấy được."""
    from erpnext.stock.doctype.batch.batch import get_available_batches

    def hoi(**k):
        return get_available_batches(frappe._dict(item_code=item, warehouse=kho, company=doc.get("company"),
                                                  based_on="Expiry", **k))

    ra = hoi(posting_date=doc.get("posting_date"), posting_time=doc.get("posting_time"))
    if cint(doc.get("set_posting_time")):
        nay = hoi()
        ra = OrderedDict((b, min(flt(q), flt(nay.get(b)))) for b, q in ra.items())
    return ra


def _lo_khoa(ds):
    """Lô không bán được: đang thu hồi (W26) hoặc chưa duyệt xuất xưởng BM.08.04 (W08)."""
    from sx.api.thuhoi import lo_dang_thu_hoi
    from sx.api.xuatxuong import lo_chua_duyet

    return set(lo_dang_thu_hoi(ds)) | set(lo_chua_duyet(ds))


def _tao_goi(doc, r, can, phan):
    """Gói lô NHÁP nhiều lô cho dòng `r` (gửi cùng chứng từ: POS Invoice on_submit / sổ kho của hoá đơn) — tên gói."""
    from erpnext.stock.serial_batch_bundle import SerialBatchCreation
    from erpnext.stock.utils import get_combine_datetime

    return SerialBatchCreation({
        "item_code": r.item_code, "warehouse": r.warehouse, "company": doc.get("company"),
        "voucher_type": doc.doctype, "voucher_no": doc.name, "voucher_detail_no": r.name,
        "posting_datetime": get_combine_datetime(doc.get("posting_date"), doc.get("posting_time")),
        "qty": can, "type_of_transaction": "Outward", "batches": frappe._dict(phan), "do_not_submit": True,
    }).make_serial_and_batch_bundle().name
