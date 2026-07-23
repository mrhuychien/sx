"""API + hook tầng 1: xuất đậu (sinh lô R) và nhập bột (Manufacture T1, trừ đậu FIFO).

Đậu chỉ trừ kho tại đây (D7). WO của nhập bột KHÔNG gắn custom_ngay_sx (độc lập
với phiếu ngày) — tra ngược qua SX Nhap Bot.lo_rang.
"""

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate

from sx.api.mfg import cancel_doc, tao_batch, tao_se_manufacture, tao_wo
from sx.config.roles import guard_card
from sx.utils import get_bot_from_dau, get_settings


# ─────────────────────────────────────────────── whitelisted ──


@frappe.whitelist()
def xuat_dau(loai_dau, dau_kg, ngay_rang=None):
    """Tạo + submit SX Xuat Dau -> sinh mã lô R (hiển thị TO để ghi thẻ, D13)."""
    guard_card("xuatdau")
    doc = frappe.new_doc("SX Xuat Dau")
    doc.ngay_xuat = nowdate()
    doc.ngay_rang = getdate(ngay_rang) if ngay_rang else add_days(nowdate(), 1)
    doc.loai_dau = loai_dau
    doc.dau_kg = flt(dau_kg)
    doc.insert()
    doc.submit()
    return {"name": doc.name, "lo_rang": doc.lo_rang, "ngay_rang": str(doc.ngay_rang)}


@frappe.whitelist()
def nhap_bot(xuat_dau):
    """Tạo + submit SX Nhap Bot — WO+SE Manufacture T1 chạy trong on_submit."""
    guard_card("nhapbot")
    doc = frappe.new_doc("SX Nhap Bot")
    doc.ngay_nhap = nowdate()
    doc.xuat_dau = xuat_dau
    doc.insert()
    doc.submit()
    doc.reload()
    return {"name": doc.name, "lo_rang": doc.lo_rang, "bot_kg": flt(doc.bot_kg), "batch": doc.batch_bot}


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
