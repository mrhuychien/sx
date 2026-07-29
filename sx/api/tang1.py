"""API + hook tầng 1: xuất đậu (sinh lô R) và nhập bột (Manufacture T1, trừ đậu FIFO).

Đậu chỉ trừ kho tại đây (D7). WO của nhập bột KHÔNG gắn custom_ngay_sx (độc lập
với phiếu ngày) — tra ngược qua SX Nhap Bot.lo_rang.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from sx.api.mfg import (
    cancel_doc,
    tao_batch,
    tao_se_chuyen_kho,
    tao_se_manufacture,
    tao_se_repack,
    tao_wo,
)
from sx.config.roles import guard_card
from sx.utils import (
    CONG_DOAN,
    batch_cua_chang,
    get_bot_from_dau,
    get_settings,
    get_yield_bot,
    item_cua_chang,
    kho_xuong,
)


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


# ═══════════════════ Luồng công đoạn tầng 1 theo lưu đồ (D31) ═══════════════════
#
# Đỗ (Kho NVL) --xuất kho--> Đỗ (Kho Xưởng) --luộc+rang--> ĐỖ Ủ --tách vỏ--> ĐỖ VỠ
#   --nghiền--> BỘT NỀN (Kho BTP)
#
# Mỗi công đoạn = 1 Stock Entry Repack, kg ra do QC cân thật. Tồn từng chặng đọc
# THẲNG từ kho (Bin/Batch) — không có state phụ để lệch.


def _tim_chang(ma):
    for cd in CONG_DOAN:
        if cd["ma"] == ma:
            return cd
    frappe.throw(_("Công đoạn '{0}' không có trong luồng sản xuất.").format(ma))


def _ton_batch(item, kho, batch=None):
    """Tồn của item tại kho (theo batch nếu có). Dùng để vẽ lưu đồ + chặn quá tay."""
    from erpnext.stock.doctype.batch.batch import get_batch_qty

    if batch:
        if not frappe.db.exists("Batch", batch):
            return 0.0
        return flt(get_batch_qty(batch_no=batch, item_code=item, warehouse=kho) or 0)
    return flt(
        frappe.db.get_value("Bin", {"item_code": item, "warehouse": kho}, "actual_qty")
    )


@frappe.whitelist()
def luu_do_lo(ngay=None):
    """Lưu đồ tầng 1: mỗi lô R đang chạy + tồn BTP từng chặng (D31).

    Lô nào còn tồn ở bất kỳ chặng nào (hoặc mới xuất kho trong 7 ngày) thì còn hiện.
    """
    guard_card("xuatdau")
    settings = get_settings()
    kho_x = kho_xuong(settings)
    ds = frappe.get_all(
        "SX Xuat Dau",
        filters={"docstatus": 1, "ngay_xuat": (">=", add_days(getdate(ngay or nowdate()), -14))},
        fields=["name", "lo_rang", "ngay_xuat", "ngay_rang", "loai_dau", "dau_kg",
                "trang_thai_bot"],
        order_by="ngay_rang desc, creation desc",
    )
    out = []
    for r in ds:
        chang = []
        con_lai = 0.0
        for ten_chang, nhan, kho in (
            ("dau", _("Đỗ ở xưởng"), kho_x),
            ("u", _("Đỗ ủ"), kho_x),
            ("vo", _("Đỗ vỡ"), kho_x),
            ("bot", _("Bột nền"), settings.kho_btp),
        ):
            try:
                item = item_cua_chang(r.loai_dau, ten_chang)
            except Exception:
                chang.append({"chang": ten_chang, "nhan": nhan, "item": None, "ton": 0,
                              "thieu_item": 1})
                continue
            batch = batch_cua_chang(r.lo_rang, ten_chang)
            # Đỗ chưa rang chưa có batch riêng -> đọc tồn tổng của item tại kho xưởng
            ton = _ton_batch(item, kho, batch if ten_chang != "dau" else None)
            if ten_chang != "dau":
                con_lai += ton
            chang.append({"chang": ten_chang, "nhan": nhan, "item": item,
                          "batch": batch, "ton": flt(ton, 2)})
        out.append({
            "name": r.name, "lo_rang": r.lo_rang, "loai_dau": r.loai_dau,
            "dau_kg": flt(r.dau_kg, 2), "ngay_xuat": str(r.ngay_xuat),
            "ngay_rang": str(r.ngay_rang), "da_nhap_bot": cint(r.trang_thai_bot),
            "chang": chang, "con_o_xuong": flt(con_lai, 2),
            "cong_doan": [{"ma": c["ma"], "ten": c["ten"]} for c in CONG_DOAN],
        })
    return {"kho_xuong": kho_x, "lo": out}


@frappe.whitelist()
def xuat_kho_dau(loai_dau, dau_kg, ngay_rang=None, ngay_xuat=None):
    """QC bấm 'Xuất kho đỗ': phiếu chuyển kho Nguyên liệu -> Xưởng + sinh lô R (D31).

    Đỗ FIFO theo lô NCC; lô R sinh ngay để QC ghi thẻ treo theo lô suốt tuyến.
    """
    guard_card("xuatdau")
    settings = get_settings()
    for f, label in (("cong_ty", "Công ty"), ("kho_nvl", "Kho NVL")):
        if not settings.get(f):
            frappe.throw(_("SX Settings chưa cấu hình: {0}").format(label))

    kq = xuat_dau(loai_dau, dau_kg, ngay_rang, ngay_xuat)
    se = tao_se_chuyen_kho(
        settings.cong_ty, loai_dau, flt(dau_kg),
        kho_di=settings.kho_nvl, kho_den=kho_xuong(settings),
        ngay=ngay_xuat or nowdate(),
        ghi_chu=_("Xuất đỗ ra xưởng — lô {0}").format(kq["lo_rang"]),
    )
    frappe.db.set_value("SX Xuat Dau", kq["name"], "se_xuat_kho", se.name)
    kq["se"] = se.name
    return kq


@frappe.whitelist()
def hoan_tat_cong_doan(xuat_dau_name, cong_doan, kg_ra=None, kg_vao=None, ngay=None):
    """Bấm 'Hoàn tất công đoạn' — chuyển BTP sang chặng kế tiếp (D31).

    kg_vao  bỏ trống = lấy TOÀN BỘ tồn của chặng trước (nút "Hoàn tất lô").
    kg_ra   bỏ trống = bằng kg_vao (không khai hao hụt); nghiền thì gợi ý theo
            yield BOM tầng 1 — QC vẫn sửa được.
    """
    guard_card("xuatdau")
    cd = _tim_chang(cong_doan)
    xd = frappe.get_doc("SX Xuat Dau", xuat_dau_name)
    if xd.docstatus != 1:
        frappe.throw(_("Phiếu xuất đỗ {0} không ở trạng thái đã ghi.").format(xuat_dau_name))

    settings = get_settings()
    kho_x = kho_xuong(settings)
    item_vao = item_cua_chang(xd.loai_dau, cd["vao"])
    item_ra = item_cua_chang(xd.loai_dau, cd["ra"])
    batch_vao = batch_cua_chang(xd.lo_rang, cd["vao"])
    batch_ra = batch_cua_chang(xd.lo_rang, cd["ra"])
    kho_ra = settings.kho_btp if cd["ra"] == "bot" else kho_x

    ton = _ton_batch(item_vao, kho_x, batch_vao if cd["vao"] != "dau" else None)
    vao = flt(kg_vao) if kg_vao else flt(ton)
    if vao <= 0:
        frappe.throw(
            _("Không còn {0} nào ở xưởng cho lô {1} — công đoạn trước đã làm chưa?")
            .format(item_vao, xd.lo_rang)
        )
    if vao > ton + 1e-6:
        frappe.throw(
            _("Lô {0} chỉ còn {1} kg {2} ở xưởng, không hoàn tất {3} kg được.")
            .format(xd.lo_rang, flt(ton, 2), item_vao, flt(vao, 2))
        )

    if kg_ra:
        ra = flt(kg_ra)
    elif cd["ra"] == "bot":
        _bot, bom = get_bot_from_dau(xd.loai_dau)
        ra = flt(vao * get_yield_bot(bom, xd.loai_dau), 2)
    else:
        ra = vao
    if ra <= 0:
        frappe.throw(_("Số kg ra phải lớn hơn 0."))

    tao_batch(item_ra, batch_ra, ngay_sx=None)
    se = tao_se_repack(
        settings.cong_ty,
        item_vao=item_vao, kg_vao=vao, kho_vao=kho_x,
        item_ra=item_ra, kg_ra=ra, kho_ra=kho_ra,
        batch_ra=batch_ra,
        batch_vao=batch_vao if cd["vao"] != "dau" else None,
        ngay=ngay or nowdate(),
        ghi_chu=_("{0} — lô {1}").format(cd["ten"], xd.lo_rang),
    )
    if cd["ra"] == "bot":
        # Giữ tương thích: cờ này chặn chốt ngày tự nhập bột lại lần nữa (D18)
        frappe.db.set_value("SX Xuat Dau", xd.name, "trang_thai_bot", 1)

    return {
        "lo_rang": xd.lo_rang, "cong_doan": cd["ten"],
        "kg_vao": flt(vao, 2), "kg_ra": flt(ra, 2),
        "item_ra": item_ra, "batch_ra": batch_ra, "se": se.name,
        "hao_hut": flt(vao - ra, 2),
    }
