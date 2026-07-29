"""API + hook tầng 1: xuất đậu (sinh lô R) và nhập bột (Manufacture T1, trừ đậu FIFO).

Đậu chỉ trừ kho tại đây (D7). WO của nhập bột KHÔNG gắn custom_ngay_sx (độc lập
với phiếu ngày) — tra ngược qua SX Nhap Bot.lo_rang.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from sx.api.mfg import cancel_doc, tao_batch, tao_se_manufacture, tao_wo
from sx.config.roles import guard_card
from sx.utils import get_bot_from_dau, get_settings, get_yield_bot


def lo_cho_nhap_bot(truoc_ngay=None):
    """Lô R đã rang xong, chưa nhập bột.

    truoc_ngay: chỉ lấy lô có ngay_rang < ngày này (dùng khi chốt ngày tự nhập —
    lô rang hôm trước mới qua khâu nghiền). None = lấy mọi lô đã tới ngày rang.
    Trả thêm item_bot + bot_kg (suy từ yield BOM T1) để bên gọi kiểm tồn trước.
    """
    filters = {"docstatus": 1, "trang_thai_bot": 0}
    filters["ngay_rang"] = ("<", getdate(truoc_ngay)) if truoc_ngay else ("<=", nowdate())
    rows = frappe.get_all(
        "SX Xuat Dau",
        filters=filters,
        fields=["name", "lo_rang", "ngay_rang", "loai_dau", "dau_kg"],
        order_by="ngay_rang",
    )
    for r in rows:
        try:
            item_bot, bom = get_bot_from_dau(r.loai_dau)
            r["item_bot"] = item_bot
            r["bot_kg"] = flt(flt(r.dau_kg) * get_yield_bot(bom, r.loai_dau), 2)
        except Exception:
            r["item_bot"], r["bot_kg"] = None, 0
    return rows


# ─────────────────────────────────────────────── whitelisted ──


@frappe.whitelist()
def xuat_dau(loai_dau, dau_kg, ngay_rang=None, ngay_xuat=None):
    """Tạo + submit SX Xuat Dau -> sinh mã lô R (hiển thị TO để ghi thẻ, D13).

    `ngay_xuat` = ngày đang xem trên portal (ghi bù cho ngày cũ — D25); bỏ trống = hôm nay.
    """
    guard_card("xuatdau")
    doc = frappe.new_doc("SX Xuat Dau")
    doc.ngay_xuat = getdate(ngay_xuat) if ngay_xuat else nowdate()
    doc.ngay_rang = getdate(ngay_rang) if ngay_rang else add_days(doc.ngay_xuat, 1)
    doc.loai_dau = loai_dau
    doc.dau_kg = flt(dau_kg)
    doc.insert()
    doc.submit()
    return {"name": doc.name, "lo_rang": doc.lo_rang, "ngay_rang": str(doc.ngay_rang)}


@frappe.whitelist()
def ds_xuat_dau(ngay=None):
    """Phiếu xuất đậu ĐÃ GHI trong ngày — để QC đối chiếu và sửa khi lỡ nhập sai (D25).

    Lọc theo ngày XUẤT (ngày QC bấm), không phải ngày rang.
    `sua_duoc` = chưa nhập bột (chưa trừ đỗ) -> huỷ được ngay trên portal.
    """
    guard_card("xuatdau")
    ngay = getdate(ngay) if ngay else nowdate()
    ds = frappe.get_all(
        "SX Xuat Dau",
        filters={"ngay_xuat": ngay, "docstatus": 1},
        fields=["name", "loai_dau", "dau_kg", "lo_rang", "ngay_rang", "trang_thai_bot"],
        order_by="creation",
    )
    for r in ds:
        r["ngay_rang"] = str(r["ngay_rang"])
        r["sua_duoc"] = not cint(r["trang_thai_bot"])
    return ds


@frappe.whitelist()
def huy_xuat_dau(name):
    """Huỷ 1 phiếu xuất đậu ghi nhầm. Chặn nếu đã nhập bột (đã trừ đỗ + có ledger):
    khi đó phải huỷ chốt ngày để thu hồi phiếu nhập bột trước."""
    guard_card("xuatdau")
    doc = frappe.get_doc("SX Xuat Dau", name)
    if cint(doc.trang_thai_bot):
        frappe.throw(
            _("Lô {0} đã nhập bột (đã trừ đỗ trong kho) — không huỷ trực tiếp được. "
              "Huỷ chốt ngày đã nhập bột lô này trước, rồi mới huỷ phiếu xuất đậu.")
            .format(doc.lo_rang)
        )
    if doc.docstatus != 1:
        frappe.throw(_("Phiếu {0} không ở trạng thái đã ghi.").format(name))
    doc.flags.ignore_permissions = True
    doc.cancel()
    return {"name": name, "lo_rang": doc.lo_rang}


def tao_nhap_bot(xuat_dau, ngay_nhap=None):
    """Tạo + submit SX Nhap Bot (WO+SE Manufacture T1 chạy trong on_submit).

    Dùng bởi chot_ngay (tự nhập bột lô rang hôm trước) — KHÔNG guard card ở đây,
    người gọi đã guard. Trả doc để bên gọi ghi vào ds_wo_se.
    """
    doc = frappe.new_doc("SX Nhap Bot")
    doc.ngay_nhap = getdate(ngay_nhap) if ngay_nhap else nowdate()
    doc.xuat_dau = xuat_dau
    doc.flags.ignore_permissions = True
    doc.insert()
    doc.submit()
    doc.reload()
    return doc


# ─────────────────────────────────────────────── hooks (doc_events) ──


def on_submit_nhap_bot(doc, method=None):
    """Manufacture T1: Batch bột (= lô R) -> WO -> SE (đậu FIFO Kho NVL -> bột Kho BTP)."""
    settings = get_settings()
    for f, label in (("cong_ty", "Công ty"), ("kho_nvl", "Kho NVL"), ("kho_btp", "Kho BTP")):
        if not settings.get(f):
            frappe.throw(_("SX Settings chưa cấu hình: {0}").format(label))

    xd = frappe.get_doc("SX Xuat Dau", doc.xuat_dau)
    item_bot, bom = get_bot_from_dau(xd.loai_dau)

    # Batch bột nền: batch_id = lô R (mắt xích tra ngược tới SX Nhap Bot)
    batch = tao_batch(item_bot, doc.lo_rang)
    wo = tao_wo(
        settings.cong_ty, item_bot, flt(doc.bot_kg), bom,
        source_wh=settings.kho_nvl, fg_wh=settings.kho_btp,
        ngay_sx=None, planned_date=doc.ngay_nhap,
    )
    se = tao_se_manufacture(
        wo, flt(doc.bot_kg), batch,
        kho_nguon=lambda _item: settings.kho_nvl,  # đậu FIFO từ Kho NVL
        ngay=doc.ngay_nhap, ngay_sx=None,
    )

    doc.db_set("wo", wo.name)
    doc.db_set("se", se.name)
    doc.db_set("batch_bot", batch)
    frappe.db.set_value("SX Xuat Dau", doc.xuat_dau, "trang_thai_bot", 1)


def on_cancel_nhap_bot(doc, method=None):
    """Huỷ ngược: SE -> WO; reset trang_thai_bot trên phiếu xuất."""
    log = []
    cancel_doc("Stock Entry", doc.se, log)
    cancel_doc("Work Order", doc.wo, log)
    if doc.xuat_dau and frappe.db.exists("SX Xuat Dau", doc.xuat_dau):
        frappe.db.set_value("SX Xuat Dau", doc.xuat_dau, "trang_thai_bot", 0)
    doc.db_set("se", None)
    doc.db_set("wo", None)
    if log:
        frappe.msgprint("; ".join(log))
