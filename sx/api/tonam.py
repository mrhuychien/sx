"""Dọn TỒN ÂM thành phẩm ở Kho Xưởng sản xuất (D193) — trong thẻ "Kiểm kê kho" (thành phẩm).

Số âm không có thật: trước đây chuyển thành phẩm từ Xưởng sản xuất sang Kho TP bằng phiếu chuyển kho mà không ghi sản
xuất vào Xưởng — hàng vào Kho TP đúng số, chỉ Xưởng âm. Ở đây đưa TỪNG DÒNG ÂM (mã × lô) của thành phẩm ở Kho Xưởng
sản xuất (SX Settings → kho_xuong, không lấy kho thay thế) về 0 bằng phiếu nhập điều chỉnh, theo giá vốn của kho đó —
bút toán điều chỉnh kho, in danh sách cho kế toán. Chỉ kho này: cửa hàng, Kho TP (kiểm kê lo) và mọi kho khác không đụng.

  · Phần dương giữ nguyên — chỉ dòng âm về 0.
  · Dòng âm có lô: nhập bù đúng lô đó (lô hết hạn: tạm bỏ HSD lúc ghi, như kiểm kê — D190).
  · Dòng âm KHÔNG lô của mã đang quản lý lô (dữ liệu cũ): ERPNext đòi lô cho mọi phiếu của mã đó — tạm tắt lô của mã
    trong lúc ghi phần không lô, ghi xong bật lại ngay (cùng giao dịch, như kiểm kê — D189).
  · Một phiếu Material Receipt (mã có cả dòng không lô lẫn dòng có lô thì thêm một phiếu cho phần có lô). Ghi chú phiếu
    bắt đầu bằng GHI_CHU + mã lần dọn — danh sách in đọc lại từ chính các phiếu đó.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime

from sx.api.kiemke import CARD, _la_quan_ly, so_vn
from sx.config.roles import guard_card
from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import _so_lo, cong_ty_kho, tam_bo_hsd, tra_hsd, xoa_cache_ma
from sx.utils import get_settings, items_tp

GHI_CHU = "Dọn tồn âm thành phẩm"
LAN = re.compile(r"\[(DA-\d{6}-\d{6})\]")
EPS = 1e-6


def _kho():
    """(kho xưởng, lỗi) — Kho Xưởng sản xuất ở SX Settings; chưa đặt / đặt trùng Kho TP / kho công ty khác thì lỗi."""
    s = get_settings()
    kho = s.get("kho_xuong")
    if not kho:
        return None, _("Chưa đặt Kho Xưởng sản xuất ở SX Settings (ô kho_xuong).")
    if kho == s.get("kho_tp"):
        return None, _("Kho Xưởng sản xuất đang đặt trùng Kho TP — kho TP do kiểm kê lo, không dọn ở đây.")
    cty = cong_ty_kho([kho]).get(kho)
    if cty and s.get("cong_ty") and cty != s.get("cong_ty"):
        return None, _("{0} thuộc công ty {1} — phiếu kho của {2} không ghi sang được.").format(kho, cty, s.get("cong_ty"))
    return kho, None


def _dong_am(kho):
    """[{item, ten, batch, hsd, so (âm), co_lo, gia, gia_tri}] — các dòng âm của thành phẩm ở kho."""
    from sx.api.mfg import gia_von_hien

    tp = {i.name: i for i in items_tp(["name", "item_name", "has_batch_no"], filters={"disabled": ("in", [0, 1])})}
    if not tp:
        return []
    am = [r for r in _so_lo(kho, list(tp)) if flt(r.q, 6) < -EPS]
    if not am:
        return []
    hsd = {b.name: b.expiry_date for b in frappe.get_all(
        "Batch", filters={"name": ("in", [r.b for r in am if r.b] or [""])}, fields=["name", "expiry_date"])}
    gia, ra = {}, []
    for r in sorted(am, key=lambda r: (tp[r.item].item_name or r.item, r.b or "")):
        if r.item not in gia:
            gia[r.item] = flt(gia_von_hien(r.item, kho))
        x = {"item": r.item, "ten": tp[r.item].item_name or r.item, "batch": r.b or None,
             "hsd": str(getdate(hsd[r.b])) if r.b and hsd.get(r.b) else None, "so": flt(r.q, 6),
             "co_lo": bool(tp[r.item].get("has_batch_no")), "gia": gia[r.item]}
        x["gia_tri"] = flt(-x["so"] * x["gia"], 2)
        ra.append(x)
    return ra


def _tong(dong):
    return {"so_dong": len(dong), "so_ma": len({x["item"] for x in dong}),
            "so_luong": flt(sum(-x["so"] for x in dong), 6), "gia_tri": flt(sum(x["gia_tri"] for x in dong), 2)}


def _lan_gan_day(n=5):
    """Các lần dọn trước: [{lan, ngay, phieu: [...]}], mới nhất trước."""
    ra = {}
    for se in frappe.get_all("Stock Entry", filters={"docstatus": 1, "remarks": ("like", f"{GHI_CHU}%")},
                             fields=["name", "remarks", "posting_date", "creation"], order_by="creation desc",
                             limit=200):
        m = LAN.search(se.remarks or "")
        if not m:
            continue
        g = ra.setdefault(m.group(1), {"lan": m.group(1), "ngay": str(se.posting_date or "")[:10], "phieu": []})
        g["phieu"].append(se.name)
    return sorted(ra.values(), key=lambda g: g["lan"], reverse=True)[:n]


@frappe.whitelist()
def ds_am():
    """Xem trước: các dòng âm của thành phẩm ở Kho Xưởng sản xuất, giá vốn, giá trị."""
    guard_card(CARD)
    kho, loi = _kho()
    dong = _dong_am(kho) if kho else []
    return {"kho": kho, "loi": loi, "dong": dong, "tong": _tong(dong), "duoc_don": _la_quan_ly(),
            "lan_truoc": _lan_gan_day()}


@frappe.whitelist()
def don_am():
    """Dọn: mỗi dòng âm về 0 bằng phiếu nhập điều chỉnh (giá vốn của kho). Chỉ quản lý — bút toán điều chỉnh kho.
    Tính lại danh sách ngay lúc dọn (không tin số máy gửi)."""
    guard_card(CARD)
    if not _la_quan_ly():
        frappe.throw(_("Chỉ quản lý dọn tồn âm — đây là bút toán điều chỉnh kho."), frappe.PermissionError)
    from sx.api.mfg import loai_phieu_kho

    kho, loi = _kho()
    if loi:
        frappe.throw(loi)
    dong = _dong_am(kho)
    if not dong:
        frappe.throw(_("Không còn tồn âm thành phẩm nào ở {0}.").format(kho))
    lan = now_datetime().strftime("DA-%d%m%y-%H%M%S")
    cong_ty = get_settings().cong_ty
    phieu, giu = [], []

    def ghi(ds):
        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Receipt"
        se.stock_entry_type = loai_phieu_kho("Material Receipt")
        se.company = cong_ty
        se.remarks = _("{0} [{1}] ở {2}: tồn âm do chuyển ra mà chưa ghi sản xuất / nhập vào kho này — đưa về 0 (điều "
                       "chỉnh kho).").format(GHI_CHU, lan, kho)
        for x in ds:
            d = {"item_code": x["item"], "qty": flt(-x["so"], 6), "t_warehouse": kho}
            if x["batch"]:
                d.update({"use_serial_batch_fields": 1, "batch_no": x["batch"]})
            d.update({"basic_rate": x["gia"]} if x["gia"] > 0 else {"allow_zero_valuation_rate": 1})
            se.append("items", d)
        se.flags.ignore_permissions = True
        het = tam_bo_hsd(se.items)
        try:
            se.insert()
            se.submit()
        finally:
            tra_hsd(het)
        giu.append(se)               # giữ tới hết request — id phiếu không bị phiếu sau dùng lại (xoa_cache_ma)
        phieu.append(se.name)

    def dat_lo(i, co):
        frappe.db.set_value("Item", i, "has_batch_no", co, update_modified=False)
        xoa_cache_ma(i)

    # Dòng KHÔNG lô của mã đang quản lý lô: ghi lúc mã tạm tắt lô, xong bật lại ngay — trước phiếu có lô.
    tat = sorted({x["item"] for x in dong if not x["batch"] and x["co_lo"]})
    for i in tat:
        dat_lo(i, 0)
    if any(not x["batch"] for x in dong):
        ghi([x for x in dong if not x["batch"]])
    for i in tat:
        dat_lo(i, 1)
    if any(x["batch"] for x in dong):
        ghi([x for x in dong if x["batch"]])
    return {"kho": kho, "lan": lan, "phieu": phieu, **_tong(dong)}


@frappe.whitelist()
def bien_ban(phieu):
    """HTML danh sách dọn tồn âm để in cho kế toán — đọc lại từ chính các phiếu nhập đã ghi."""
    guard_card(CARD)
    ds = json.loads(phieu) if isinstance(phieu, str) and phieu.strip().startswith("[") else (
        phieu if isinstance(phieu, list) else [x.strip() for x in str(phieu or "").split(",") if x.strip()])
    if not ds:
        frappe.throw(_("Chưa chọn phiếu nào."))
    se = []
    for n in ds:
        d = frappe.get_doc("Stock Entry", n) if frappe.db.exists("Stock Entry", n) else None
        if not d or not str(d.remarks or "").startswith(GHI_CHU):
            frappe.throw(_("{0} không phải phiếu dọn tồn âm.").format(n))
        se.append(d)
    ten = {i.name: i.item_name for i in frappe.get_all(
        "Item", filters={"name": ("in", list({r.get("item_code") for d in se for r in d.items}) or [""])},
        fields=["name", "item_name"])}
    kho = {}
    for d in se:
        for r in d.items:
            gia = flt(r.get("basic_rate"))
            kho.setdefault(r.get("t_warehouse"), []).append({
                "ten": ten.get(r.get("item_code")) or r.get("item_code"), "batch": r.get("batch_no"),
                "so": flt(r.get("qty"), 6), "gia": gia, "gia_tri": flt(flt(r.get("qty")) * gia, 2), "phieu": d.name})
    nhom = [{"kho": k, "dong": sorted(v, key=lambda x: (x["ten"], x["batch"] or "")),
             "so_luong": flt(sum(x["so"] for x in v), 6), "gia_tri": flt(sum(x["gia_tri"] for x in v), 2)}
            for k, v in sorted(kho.items())]
    m = LAN.search(se[0].remarks or "")
    return frappe.render_template("sx/sx/doctype/sx_kiem_ke/don_am.html", {
        "nhom": nhom, "se": [d.name for d in se], "lan": m.group(1) if m else "",
        "ngay": getdate(se[0].posting_date).strftime("%d/%m/%Y") if se[0].get("posting_date") else "",
        "tong": {"so_dong": sum(len(g["dong"]) for g in nhom), "so_luong": flt(sum(g["so_luong"] for g in nhom), 6),
                 "gia_tri": flt(sum(g["gia_tri"] for g in nhom), 2)},
        "cong_ty": get_settings().get("cong_ty") or "", "so": so_vn,
    })
