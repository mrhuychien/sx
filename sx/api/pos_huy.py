"""Lập lại hoá đơn bán từ các phiếu POS đã HUỶ (D201).

Tình huống (13/10/2026): ca POS ngày 12 không đóng được (D198–D200), thu ngân đã huỷ hết phiếu POS ngày 12 để làm lại.
ERPNext v16 chỉ cho lập / sửa đổi phiếu POS khi ca đang mở là ca mở TRONG NGÀY (SalesInvoice.validate_pos_opening_entry:
"POS Opening Entry … is outdated") — không sửa đổi (Amend) được phiếu POS ngày 12 nữa, lập phiếu mới trên màn POS thì
thành ngày 13.

Ở đây: gộp các phiếu POS đã huỷ thành hoá đơn bán (Sales Invoice) đúng như đóng ca sẽ làm — dùng chính mã gộp của
ERPNext (POS Invoice Merge Log.merge_pos_invoice_into): mỗi (POS Profile, khách) một hoá đơn gộp, ghi sổ lúc phiếu POS
cuối, trừ kho, thu tiền theo từng hình thức thanh toán, thuế như phiếu POS. Dòng giữ số phiếu POS gốc → hook D198–D200
xét giờ từng phiếu POS (phiếu trước lúc kiểm kê bật lô ghi không lô…). Dòng trỏ phiếu POS đã huỷ nên bỏ kiểm tra liên
kết của hoá đơn (ignore_links) — mọi giá trị chép từ phiếu POS đã hợp lệ lúc lập.

Chạy bằng bench, không gọi từ web:
  bench --site site1.local execute sx.api.pos_huy.lap_lai --kwargs "{'ngay': '2026-10-12'}"             # xem trước
  bench --site site1.local execute sx.api.pos_huy.lap_lai --kwargs "{'ngay': '2026-10-12', 'chay': 1}"   # làm thật
Chỉ lấy phiếu huỷ từ `huy_tu` (mặc định đầu ngày hôm nay — phiếu huỷ trước đó là huỷ thật, không lập lại), chưa có hoá
đơn lập lại (chạy lại an toàn). Phiếu trả hàng: liệt kê, không làm. Mỗi nhóm một điểm lưu (savepoint): nhóm lỗi thì bỏ
nhóm đó, báo lỗi, các nhóm khác vẫn làm. Ca POS ngày đó vẫn phải đóng (không còn phiếu nào) trên Desk.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, getdate, nowdate

from sx.api.lo_cu import _luc, moc_bat_lo


def _da_lap(ten):
    """Hoá đơn (đã gửi) đã lập lại từ phiếu POS `ten`."""
    for r in frappe.get_all("Sales Invoice Item", filters={"pos_invoice": ten}, fields=["parent"]):
        if cint(frappe.db.get_value("Sales Invoice", r.parent, "docstatus")) == 1:
            return r.parent
    return None


def _bat_lo(docs):
    """Mã đã kiểm kê bật lô có trong nhóm: số dòng ghi sổ trước / từ lúc bật lô (theo giờ phiếu POS)."""
    moc, ra = moc_bat_lo(), {}
    for d in docs:
        for r in d.get("items") or []:
            m = moc.get(r.get("item_code"))
            if m:
                x = ra.setdefault(r.get("item_code"), {"item": r.get("item_code"), "truoc": 0, "sau": 0})
                x["truoc" if _luc(d) < m["luc"] else "sau"] += 1
    return sorted(ra.values(), key=lambda x: x["item"])


def _lap(kh, docs):
    log = frappe.new_doc("POS Invoice Merge Log")
    log.customer = kh
    log.merge_invoices_based_on = "Customer"
    log.posting_date, log.posting_time = docs[-1].get("posting_date"), docs[-1].get("posting_time")
    si = log.merge_pos_invoice_into(log.get_new_sales_invoice(), docs)
    si.is_consolidated = 1
    si.set_posting_time = 1
    si.update_stock = 1
    ten = [d.name for d in docs]
    si.remarks = _("Lập lại từ {0} phiếu POS đã huỷ ngày {1} (ca không đóng được — D201): {2}").format(
        len(ten), getdate(docs[0].get("posting_date")).strftime("%d/%m/%Y"),
        ", ".join(ten[:30]) + (" …" if len(ten) > 30 else ""))
    si.flags.ignore_links = True
    si.insert()
    si.submit()
    return si.name


def lap_lai(ngay, pos_profile=None, chay=0, huy_tu=None):
    """Xem trước (chay=0) / lập hoá đơn gộp (chay=1) từ các phiếu POS ngày `ngay` đã huỷ — xem đầu tệp."""
    from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import xoa_cache_ma

    tu = get_datetime(huy_tu or nowdate())
    loc = {"docstatus": 2, "posting_date": getdate(ngay)}
    if pos_profile:
        loc["pos_profile"] = pos_profile
    nhom, bo_qua = {}, []
    for p in frappe.get_all("POS Invoice", filters=loc, order_by="posting_date asc, posting_time asc, name asc",
                            fields=["name", "pos_profile", "customer", "is_return", "modified"]):
        if get_datetime(p.modified) < tu:
            bo_qua.append({"phieu": p.name, "ly_do": _("huỷ lúc {0}, trước {1} — coi là huỷ thật").format(
                str(p.modified)[:16], str(tu)[:16])})
        elif cint(p.is_return):
            bo_qua.append({"phieu": p.name, "ly_do": _("phiếu trả hàng — làm tay")})
        elif _da_lap(p.name):
            bo_qua.append({"phieu": p.name, "ly_do": _("đã lập lại ở {0}").format(_da_lap(p.name))})
        else:
            nhom.setdefault((p.pos_profile or "", p.customer or ""), []).append(p.name)
    ra = []
    for (prof, kh), ten in sorted(nhom.items()):
        docs = [frappe.get_doc("POS Invoice", n) for n in ten]
        x = {"pos_profile": prof, "khach": kh, "so_phieu": len(docs), "phieu": ten,
             "tong": flt(sum(flt(d.get("grand_total")) for d in docs), 2),
             "tu": str(_luc(docs[0]))[:16], "den": str(_luc(docs[-1]))[:16], "bat_lo": _bat_lo(docs)}
        if cint(chay):
            frappe.db.savepoint("sx_pos_huy")
            try:
                x["hoa_don"] = _lap(kh, docs)
            except Exception as e:  # noqa: BLE001 — báo lỗi từng nhóm, các nhóm khác vẫn làm
                frappe.db.rollback(save_point="sx_pos_huy")
                for i in {r.get("item_code") for d in docs for r in d.get("items") or []}:
                    xoa_cache_ma(i)         # rollback về điểm lưu không chạy dọn cache của frappe (cờ lô tạm tắt)
                x["loi"] = " ".join(re.sub(r"<[^>]+>", " ", str(e)).split())
        ra.append(x)
    return {"ngay": str(getdate(ngay)), "chay": cint(chay), "huy_tu": str(tu)[:16], "hoa_don": ra, "bo_qua": bo_qua,
            "con_viec": _("Đóng ca POS ngày đó (không còn phiếu nào) trên Desk; sau đó thẻ Kiểm kê → Tồn không lô còn "
                          "lại của mã đã bật lô → DỌN.")}
