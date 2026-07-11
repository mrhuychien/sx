"""Ham dung chung cho app sx — 1 nguon su that cho yield BOM tang 1 va don gia vao hop."""

import frappe
from frappe import _
from frappe.utils import flt, getdate


def get_settings():
    """Doc SX Settings (Single) — dung get_cached_doc cho re."""
    return frappe.get_cached_doc("SX Settings")


def get_bom_tang_1():
    """Tra ve BOM active/default cua item BTP (bot nguyen chat).

    Yield bot KHONG cau hinh trong SX Settings — suy tu BOM nay (D4, 1 nguon su that).
    """
    settings = get_settings()
    if not settings.item_btp:
        frappe.throw(_("Chưa cấu hình Item bột BTP trong SX Settings"))
    bom = frappe.db.get_value(
        "BOM",
        {"item": settings.item_btp, "is_active": 1, "is_default": 1, "docstatus": 1},
        "name",
    )
    if not bom:
        frappe.throw(_("Chưa có BOM active cho item bột BTP {0}").format(settings.item_btp))
    return bom


def get_yield_tang_1():
    """kg bột ra / kg đậu vào, suy từ BOM tầng 1 (BOM ra 1 Kg bột, RM = đậu xanh)."""
    bom = frappe.get_cached_doc("BOM", get_bom_tang_1())
    tong_rm_kg = sum(flt(row.stock_qty) for row in bom.items)
    if not tong_rm_kg:
        frappe.throw(_("BOM tầng 1 {0} không có nguyên liệu").format(bom.name))
    return flt(bom.quantity) / tong_rm_kg


def get_don_gia_vao_hop(san_pham, phuong_thuc, ngay):
    """Lookup đơn giá lương vào hộp theo rule spec 2.5.

    Match (san_pham, phuong_thuc) trước, fallback (san_pham trống, phuong_thuc);
    lấy bản hieu_luc_tu lớn nhất <= ngày SX. Không có giá -> throw rõ ràng.
    """
    ngay = getdate(ngay)
    for filters in (
        {"san_pham": san_pham, "phuong_thuc": phuong_thuc},
        {"san_pham": ("in", ("", None)), "phuong_thuc": phuong_thuc},
    ):
        filters["hieu_luc_tu"] = ("<=", ngay)
        row = frappe.get_all(
            "SX Don Gia Vao Hop",
            filters=filters,
            fields=["don_gia"],
            order_by="hieu_luc_tu desc",
            limit=1,
        )
        if row:
            return flt(row[0].don_gia)
    frappe.throw(
        _("Chưa có đơn giá vào hộp cho sản phẩm {0} / phương thức {1} (hiệu lực đến {2}). "
          "Quản lý cần thêm SX Don Gia Vao Hop trước.").format(san_pham, phuong_thuc, ngay)
    )


def sinh_ma_lo(item_code, ngay):
    """Sinh batch_id `{custom_batch_prefix}-{DDMMYY}`, trùng thì hậu tố -2, -3 (spec 2.7)."""
    prefix = frappe.db.get_value("Item", item_code, "custom_batch_prefix")
    if not prefix:
        frappe.throw(_("Item {0} chưa có custom_batch_prefix để sinh mã lô").format(item_code))
    ngay = getdate(ngay)
    goc = f"{prefix}-{ngay.strftime('%d%m%y')}"
    batch_id = goc
    dem = 1
    while frappe.db.exists("Batch", batch_id):
        dem += 1
        batch_id = f"{goc}-{dem}"
    return batch_id
