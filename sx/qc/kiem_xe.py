"""Kiểm tra phương tiện vận chuyển — BM.09.01 (W14, D139).

Ghi NGAY trên chứng từ của chuyến hàng (tài liệu 08/10): hoá đơn bán TRỪ KHO (nhà máy không
dùng Delivery Note) và phiếu nhập mua (chuyến nhận nguyên liệu). Bốn mục + kết luận; mục nào
Không đạt thì kết luận Không đạt (ép, nói ra).

  · Bán: kết luận trống → chặn duyệt hoá đơn ("chưa kiểm xe"); Không đạt → chặn ("không xếp
    hàng lên xe không đạt" — đổi xe, kiểm lại).
  · Nhận nguyên liệu (NCC thực phẩm / phụ gia / bao bì tiếp xúc thực phẩm): kết luận trống →
    chặn duyệt phiếu; xe Không đạt → hàng đã tới sân, không chặn được — ÉP mọi dòng sang
    Cách ly (tiep_nhan đưa vào kho cách ly). NCC loại khác / chưa phân loại: không bắt.
Tắt được ở SX QC Setting → "Bắt kiểm xe BM.09.01". Phiếu trả hàng: không xét.
"""

import frappe
from frappe import _
from frappe.utils import cint

from sx.qc import ncc as NCC

DAT, KHONG_DAT = "Đạt", "Không đạt"
MUC = (("custom_xe_sach", "Thùng xe sạch, khô, không mùi lạ"),
       ("custom_xe_khong_chung", "Không chở chung hoá chất / hàng gây nhiễm"),
       ("custom_xe_con_trung", "Không có dấu hiệu côn trùng, động vật gây hại"),
       ("custom_xe_che_chan", "Thùng kín / có bạt che mưa nắng"))
NCC_CAN = (NCC.TP, NCC.PHU_GIA, NCC.BB_TX)


def _bat():
    try:
        v = frappe.get_cached_doc("SX QC Setting").get("bat_buoc_kiem_xe")
    except Exception:
        return True
    return True if v is None else bool(cint(v))


def ap_dung(doc):
    """Chứng từ này có phải chuyến hàng phải kiểm xe không."""
    if cint(doc.get("is_return")):
        return False
    if doc.doctype == "Sales Invoice":
        return bool(cint(doc.get("update_stock")))
    if doc.doctype == "Purchase Receipt":
        return NCC.thong_tin(doc.get("supplier")).get("loai") in NCC_CAN
    return False


def ket_luan(doc):
    """Kết luận theo mục — hàm thuần. Mục nào Không đạt → Không đạt; đủ bốn mục Đạt mà
    chưa kết luận → Đạt; còn lại giữ nguyên người kiểm ghi."""
    gia_tri = [doc.get(f) for f, _n in MUC]
    if KHONG_DAT in gia_tri:
        return KHONG_DAT
    if all(v == DAT for v in gia_tri) and not doc.get("custom_xe_ket_luan"):
        return DAT
    return doc.get("custom_xe_ket_luan") or ""


def validate(doc, method=None):
    if not ap_dung(doc):
        return
    kl = ket_luan(doc)
    if kl == KHONG_DAT and doc.get("custom_xe_ket_luan") != KHONG_DAT:
        frappe.msgprint(_("Kiểm xe: có mục Không đạt → kết luận Không đạt."), indicator="orange", alert=True)
    doc.custom_xe_ket_luan = kl
    if kl and not doc.get("custom_xe_nguoi_kiem"):
        doc.custom_xe_nguoi_kiem = frappe.session.user
    if doc.doctype == "Purchase Receipt" and kl == KHONG_DAT:
        doi = []
        for r in doc.get("items") or []:
            if r.get("custom_ket_luan") not in ("Không đạt", "Cách ly"):
                r.custom_ket_luan = "Cách ly"
                doi.append(str(r.idx))
        if doi:
            frappe.msgprint(_("Xe giao hàng KHÔNG ĐẠT kiểm tra — dòng {0} chuyển Cách ly.").format(
                ", ".join(doi)), indicator="orange", title=_("Kiểm xe BM.09.01"))


def before_submit(doc, method=None):
    if not _bat() or not ap_dung(doc):
        return
    kl = doc.get("custom_xe_ket_luan")
    if not kl:
        frappe.throw(_("Chưa kiểm xe (BM.09.01) — ghi biển số, bốn mục kiểm và kết luận ở mục "
                       "\"Kiểm tra phương tiện vận chuyển\" trước khi duyệt."), title=_("Kiểm xe"))
    if not (doc.get("custom_xe_bien_so") or "").strip():
        frappe.throw(_("Chưa ghi biển số xe (BM.09.01)."), title=_("Kiểm xe"))
    if doc.doctype == "Sales Invoice" and kl == KHONG_DAT:
        frappe.throw(_("Xe {0} KHÔNG ĐẠT kiểm tra — không xếp hàng lên xe này. Đổi xe (hoặc làm "
                       "sạch) rồi kiểm lại.").format(doc.get("custom_xe_bien_so") or ""),
                     title=_("Kiểm xe"))
