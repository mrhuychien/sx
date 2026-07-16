"""Ham dung chung app sx (v2) — yield BOM T1, don gia vao hop, sinh ma lo."""

import frappe
from frappe import _
from frappe.utils import flt, getdate


def get_settings():
    """Doc SX Settings (Single) — get_cached_doc cho re."""
    return frappe.get_cached_doc("SX Settings")


def get_bom_tang_1():
    """BOM active/default cua item bot BTP. Yield suy tu day (D7 — 1 nguon su that)."""
    settings = get_settings()
    if not settings.item_bot:
        frappe.throw(_("Chưa cấu hình Item bột BTP trong SX Settings"))
    bom = frappe.db.get_value(
        "BOM",
        {"item": settings.item_bot, "is_active": 1, "is_default": 1, "docstatus": 1},
        "name",
    )
    if not bom:
        frappe.throw(_("Chưa có BOM active cho item bột {0}").format(settings.item_bot))
    return bom


def get_yield_tang_1():
    """kg bột ra / kg đậu vào (BOM T1 ra 1 Kg bột, RM = đậu xanh)."""
    bom = frappe.get_cached_doc("BOM", get_bom_tang_1())
    tong_rm_kg = sum(flt(row.stock_qty) for row in bom.items)
    if not tong_rm_kg:
        frappe.throw(_("BOM tầng 1 {0} không có nguyên liệu").format(bom.name))
    return flt(bom.quantity) / tong_rm_kg


def get_item_dau():
    """Item đậu xanh = RM đầu tiên của BOM T1 (không cấu hình riêng — 1 nguồn sự thật)."""
    bom = frappe.get_cached_doc("BOM", get_bom_tang_1())
    return bom.items[0].item_code


def get_bom_active(item_code):
    """BOM active/default của 1 item (hỗn hợp hoặc SKU TP)."""
    return frappe.db.get_value(
        "BOM", {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1}, "name"
    )


def get_don_gia_vao_hop(san_pham, phuong_thuc, ngay):
    """Lookup đơn giá lương vào hộp (spec 3.6).

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


def _unique_suffix(goc, exists_fn):
    ma = goc
    dem = 1
    while exists_fn(ma):
        dem += 1
        ma = f"{goc}-{dem}"
    return ma


def sinh_lo_rang(ngay_rang):
    """Mã lô rang `R-DDMMYY` theo ngày rang; trùng (SX Xuat Dau hoặc Batch) -> hậu tố -2, -3."""
    goc = f"R-{getdate(ngay_rang).strftime('%d%m%y')}"
    return _unique_suffix(
        goc,
        lambda ma: frappe.db.exists("SX Xuat Dau", {"lo_rang": ma, "docstatus": ("<", 2)})
        or frappe.db.exists("Batch", ma),
    )


def sinh_ma_lo_hh(item_code, ngay):
    """Batch hỗn hợp `{custom_batch_prefix}-{YYYYMMDD}` (spec 3.9)."""
    prefix = frappe.db.get_value("Item", item_code, "custom_batch_prefix")
    if not prefix:
        frappe.throw(_("Item {0} chưa có custom_batch_prefix").format(item_code))
    goc = f"{prefix}-{getdate(ngay).strftime('%Y%m%d')}"
    return _unique_suffix(goc, lambda ma: frappe.db.exists("Batch", ma))


def sinh_ma_lo_tp(item_code, ngay):
    """Batch TP `{custom_batch_prefix}-{DDMMYY}` (spec 3.9)."""
    prefix = frappe.db.get_value("Item", item_code, "custom_batch_prefix")
    if not prefix:
        frappe.throw(_("Item {0} chưa có custom_batch_prefix").format(item_code))
    goc = f"{prefix}-{getdate(ngay).strftime('%d%m%y')}"
    return _unique_suffix(goc, lambda ma: frappe.db.exists("Batch", ma))
