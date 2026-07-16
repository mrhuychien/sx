"""Whitelisted API cho portal SPA /sx (v2 — 4 điểm nhập liệu).

Mọi method: guard role ở dòng đầu (spec §4). Dữ liệu doc chuẩn chỉ trả
field trong whitelist (Employee: name, employee_name).
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from sx.api.common import QUAN_LY, THU_KHO, TO_DONG_GOI, TO_TRON, _guard
from sx.utils import (
    get_bom_active,
    get_don_gia_vao_hop,
    get_item_dau,
    get_settings,
    get_yield_tang_1,
)


# ─────────────────────────────────────────────────────────────── boot ──


@frappe.whitelist()
def get_boot():
    """Context khởi động portal theo role: phiếu ngày, danh mục, lô đậu FIFO,
    lô vật tư đang mở, lô R chờ nhập bột, nhân viên (whitelist field)."""
    _guard([THU_KHO, TO_TRON, TO_DONG_GOI, QUAN_LY])
    roles = set(frappe.get_roles())
    la_quan_ly = bool(roles & {QUAN_LY, "System Manager"})
    hom_nay = nowdate()
    settings = get_settings()

    ngay_sx = _ngay_summary(
        frappe.db.get_value(
            "SX Ngay San Xuat", {"ngay": hom_nay, "docstatus": ("<", 2)}, "name"
        )
    )

    # Danh mục hỗn hợp (BTP-HH) + cỡ mẻ chuẩn từ BOM
    items_hh = frappe.get_all(
        "Item", filters={"custom_sx_nhom": "BTP-HH", "disabled": 0},
        fields=["name", "item_name"], order_by="name",
    )
    for it in items_hh:
        bom = get_bom_active(it["name"])
        it["co_me_chuan_kg"] = (
            flt(frappe.db.get_value("BOM", bom, "custom_co_me_chuan_kg")) if bom else 0
        )

    items_tp = frappe.get_all(
        "Item", filters={"custom_sx_nhom": "TP", "disabled": 0},
        fields=["name", "item_name"], order_by="item_name",
    )

    may = frappe.get_all(
        "SX May", filters={"dang_dung": 1},
        fields=["name", "ten_may", "cong_suat_dinh_muc"], order_by="name",
    )

    # Lô đậu tồn theo FIFO (gợi ý lô cũ nhất cho thủ kho)
    lo_dau = []
    if roles & {THU_KHO, QUAN_LY, "System Manager"}:
        try:
            from erpnext.stock.doctype.batch.batch import get_batch_qty

            item_dau = get_item_dau()
            for b in get_batch_qty(item_code=item_dau, warehouse=settings.kho_nvl) or []:
                if flt(b.get("qty")) > 0:
                    lo_dau.append({"batch": b.get("batch_no"), "qty": flt(b.get("qty"), 1)})
        except Exception:
            # Chưa có BOM T1 / settings (trước Phase 0) — portal vẫn mở được
            lo_dau = []

    lo_vat_tu = frappe.get_all(
        "SX Lo Vat Tu", filters={"dang_mo": 1},
        fields=["name", "vat_tu", "item", "lo_ncc", "ngay_mo"],
    )

    xuat_dau_gan_day = frappe.get_all(
        "SX Xuat Dau", filters={"docstatus": 1},
        fields=["name", "lo_rang", "ngay_rang", "lo_dau_ncc", "so_bao", "dau_kg"],
        order_by="ngay_rang desc", limit=10,
    )

    lo_cho_nhap_bot = _lo_cho_nhap_bot() if roles & {TO_TRON, QUAN_LY, "System Manager"} else []

    nhan_vien = []
    if roles & {TO_DONG_GOI, QUAN_LY, "System Manager"}:
        # Whitelist field: KHÔNG lộ lương/CCCD (spec §4)
        nhan_vien = frappe.get_all(
            "Employee", filters={"status": "Active"},
            fields=["name", "employee_name"], order_by="employee_name",
        )

    return {
        "user": frappe.session.user,
        "is_quan_ly": la_quan_ly,
        "is_thu_kho": bool(roles & {THU_KHO, QUAN_LY, "System Manager"}),
        "is_to_tron": bool(roles & {TO_TRON, QUAN_LY, "System Manager"}),
        "is_to_dong_goi": bool(roles & {TO_DONG_GOI, QUAN_LY, "System Manager"}),
        "hom_nay": hom_nay,
        "ngay_sx": ngay_sx,
        "bang_vao_hop": _bang_vao_hop_summary(ngay_sx["name"]) if ngay_sx else None,
        "items_hh": items_hh,
        "items_tp": items_tp,
        "may": may,
        "lo_dau": lo_dau,
        "lo_vat_tu": lo_vat_tu,
        "xuat_dau_gan_day": xuat_dau_gan_day,
        "lo_cho_nhap_bot": lo_cho_nhap_bot,
        "nhan_vien": nhan_vien,
        "settings": {"kl_bao_dau_kg": flt(settings.kl_bao_dau_kg)},
    }


def _ngay_summary(ten):
    if not ten:
        return None
    doc = frappe.get_doc("SX Ngay San Xuat", ten)
    return {
        "name": doc.name,
        "ngay": str(doc.ngay),
        "docstatus": doc.docstatus,
        "trang_thai": doc.trang_thai,
        "tong_hop_tp": doc.tong_hop_tp,
        "tong_luong_sp": doc.tong_luong_sp,
        "bao_me": [
            {
                "hon_hop": r.hon_hop,
                "so_me": r.so_me,
                "co_me_kg": r.co_me_kg,
                "tong_kg": r.tong_kg,
                "batch_hh": r.batch_hh,
            }
            for r in doc.bao_me
        ],
        "cong_suat_may": [
            {"may": r.may, "so_thung": r.so_thung, "nguoi_chay": r.nguoi_chay}
            for r in doc.cong_suat_may
        ],
        "su_co": [
            {
                "thoi_diem": str(r.thoi_diem),
                "loai": r.loai,
                "mo_ta": r.mo_ta,
                "phut_dung": r.phut_dung,
            }
            for r in doc.su_co
        ],
    }


def _bang_vao_hop_summary(ngay_sx):
    ten = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": ngay_sx, "docstatus": ("<", 2)}, "name"
    )
    if not ten:
        return None
    doc = frappe.get_doc("SX Bang Vao Hop", ten)
    return {
        "name": doc.name,
        "docstatus": doc.docstatus,
        "tong_hop": doc.tong_hop,
        "tong_tien": doc.tong_tien,
        "dong": [
            {
                "nhan_vien": r.nhan_vien,
                "ten_nhan_vien": r.ten_nhan_vien,
                "san_pham": r.san_pham,
                "phuong_thuc": r.phuong_thuc,
                "so_hop": r.so_hop,
                "don_gia": r.don_gia,
                "thanh_tien": r.thanh_tien,
            }
            for r in doc.dong
        ],
    }


def _lo_cho_nhap_bot():
    """Lô R đã tới ngày rang, chưa có SX Nhap Bot docstatus<2."""
    da_nhap = frappe.get_all(
        "SX Nhap Bot", filters={"docstatus": ("<", 2)}, pluck="xuat_dau"
    )
    filters = {"docstatus": 1, "ngay_rang": ("<=", nowdate())}
    if da_nhap:
        filters["name"] = ("not in", da_nhap)
    return frappe.get_all(
        "SX Xuat Dau",
        filters=filters,
        fields=["name", "lo_rang", "ngay_rang", "so_bao", "dau_kg"],
        order_by="ngay_rang",
    )


# ─────────────────────────────────────────────────────────── thủ kho ──


@frappe.whitelist()
def xuat_dau(lo_dau, so_bao, kl_bao=0, ngay_rang=None):
    """Tạo + submit SX Xuat Dau -> sinh mã lô R (hiển thị TO để ghi thẻ, D13)."""
    _guard([THU_KHO, QUAN_LY])
    doc = frappe.new_doc("SX Xuat Dau")
    doc.ngay_xuat = nowdate()
    doc.ngay_rang = getdate(ngay_rang) if ngay_rang else add_days(nowdate(), 1)
    doc.lo_dau_ncc = lo_dau
    doc.so_bao = cint(so_bao)
    doc.kl_bao_kg = flt(kl_bao) or flt(get_settings().kl_bao_dau_kg)
    doc.insert()
    doc.submit()
    return {
        "name": doc.name,
        "lo_rang": doc.lo_rang,
        "ngay_rang": str(doc.ngay_rang),
        "dau_kg": flt(doc.dau_kg),
    }


@frappe.whitelist()
def mo_lo_vat_tu(vat_tu, item, lo_ncc=None):
    """Mở lô đường/dầu mới (controller tự đóng lô cũ cùng vật tư)."""
    _guard([THU_KHO, QUAN_LY])
    doc = frappe.new_doc("SX Lo Vat Tu")
    doc.vat_tu = vat_tu
    doc.item = item
    doc.lo_ncc = lo_ncc
    doc.ngay_mo = nowdate()
    doc.dang_mo = 1
    doc.insert()
    return {"name": doc.name, "vat_tu": doc.vat_tu, "item": doc.item}


# ─────────────────────────────────────────────────────────── tổ trộn ──


@frappe.whitelist()
def list_lo_cho_nhap_bot():
    """Lô R đã rang, chưa nhập bột — cho tổ trộn chọn."""
    _guard([TO_TRON, QUAN_LY])
    return _lo_cho_nhap_bot()


@frappe.whitelist()
def nhap_bot(xuat_dau):
    """Tạo + submit SX Nhap Bot: Batch = lô R + Material Receipt vào Kho BTP (GATE-C=A)."""
    _guard([TO_TRON, QUAN_LY])
    doc = frappe.new_doc("SX Nhap Bot")
    doc.ngay_nhap = nowdate()
    doc.xuat_dau = xuat_dau
    doc.insert()
    doc.submit()
    doc.reload()
    return {
        "name": doc.name,
        "lo_rang": doc.lo_rang,
        "bot_kg": flt(doc.bot_kg),
        "batch": doc.batch_bot,
    }


@frappe.whitelist()
def get_or_create_ngay(ngay=None):
    """Lấy (hoặc tạo draft) phiếu ngày — chỗ gắn báo mẻ / công suất / vào hộp."""
    _guard([TO_TRON, TO_DONG_GOI, QUAN_LY])
    ngay = getdate(ngay) if ngay else getdate(nowdate())
    ten = frappe.db.get_value(
        "SX Ngay San Xuat", {"ngay": ngay, "docstatus": ("<", 2)}, "name"
    )
    if not ten:
        doc = frappe.new_doc("SX Ngay San Xuat")
        doc.ngay = ngay
        doc.insert()
        ten = doc.name
    return _ngay_summary(ten)


@frappe.whitelist()
def bao_me(ngay_sx, rows):
    """Upsert child bao_me trên phiếu ngày draft. rows = [{hon_hop, so_me}]."""
    _guard([TO_TRON, QUAN_LY])
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    if doc.docstatus != 0:
        frappe.throw(_("Phiếu ngày đã chốt — không sửa báo mẻ được"))
    doc.set("bao_me", [])
    for r in frappe.parse_json(rows) or []:
        if cint(r.get("so_me")) > 0:
            doc.append("bao_me", {"hon_hop": r.get("hon_hop"), "so_me": cint(r.get("so_me"))})
    doc.save()
    return _ngay_summary(doc.name)


# ─────────────────────────────────────────────────────── tổ đóng gói ──


@frappe.whitelist()
def cong_suat_may(ngay_sx, rows):
    """Upsert child cong_suat_may. rows = [{may, so_thung, nguoi_chay?}]."""
    _guard([TO_DONG_GOI, QUAN_LY])
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    if doc.docstatus != 0:
        frappe.throw(_("Phiếu ngày đã chốt — không sửa công suất máy được"))
    doc.set("cong_suat_may", [])
    for r in frappe.parse_json(rows) or []:
        if cint(r.get("so_thung")) > 0:
            doc.append(
                "cong_suat_may",
                {
                    "may": r.get("may"),
                    "so_thung": cint(r.get("so_thung")),
                    "nguoi_chay": r.get("nguoi_chay"),
                },
            )
    doc.save()
    return _ngay_summary(doc.name)


@frappe.whitelist()
def luu_bang_vao_hop(ngay_sx, rows):
    """Upsert DRAFT SX Bang Vao Hop (auto-save). Đơn giá luôn tính lại server-side."""
    _guard([TO_DONG_GOI, QUAN_LY])
    if frappe.db.get_value("SX Ngay San Xuat", ngay_sx, "docstatus") != 0:
        frappe.throw(_("Phiếu ngày đã chốt — không sửa bảng vào hộp được"))
    ten = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": ngay_sx, "docstatus": 0}, "name"
    )
    doc = frappe.get_doc("SX Bang Vao Hop", ten) if ten else frappe.new_doc("SX Bang Vao Hop")
    doc.ngay_sx = ngay_sx
    doc.set("dong", [])
    for r in frappe.parse_json(rows) or []:
        doc.append(
            "dong",
            {
                "nhan_vien": r.get("nhan_vien"),
                "san_pham": r.get("san_pham"),
                "phuong_thuc": r.get("phuong_thuc"),
                "so_hop": cint(r.get("so_hop")),
            },
        )
    doc.save()
    return _bang_vao_hop_summary(ngay_sx)


@frappe.whitelist()
def ghi_su_co(ngay_sx, loai, mo_ta=None, phut_dung=0):
    """Append 1 dòng sự cố vào phiếu ngày draft."""
    _guard([TO_DONG_GOI, TO_TRON, QUAN_LY])
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    if doc.docstatus != 0:
        frappe.throw(_("Phiếu ngày đã chốt — không ghi thêm sự cố được"))
    doc.append(
        "su_co",
        {
            "thoi_diem": frappe.utils.now(),
            "loai": loai,
            "mo_ta": mo_ta,
            "phut_dung": cint(phut_dung),
        },
    )
    doc.save()
    return {"so_su_co": len(doc.su_co)}


# ─────────────────────────────────────────────────────────── quản lý ──


@frappe.whitelist()
def dashboard(tu_ngay=None, den_ngay=None):
    """KPI quản lý: sản lượng theo SKU, năng suất/người, công suất máy, sự cố,
    tồn hỗn hợp (cảnh báo âm = quên báo mẻ)."""
    _guard([QUAN_LY])
    den_ngay = getdate(den_ngay or nowdate())
    tu_ngay = getdate(tu_ngay) if tu_ngay else add_days(den_ngay, -6)
    so_ngay = (den_ngay - tu_ngay).days + 1

    phieu = frappe.get_all(
        "SX Ngay San Xuat",
        filters={"ngay": ("between", (tu_ngay, den_ngay)), "docstatus": 1},
        fields=["name", "ngay", "tong_hop_tp", "tong_luong_sp"],
        order_by="ngay",
    )
    ds_phieu = [p.name for p in phieu]

    san_luong_sku, nang_suat, cong_suat, su_co, phut_dung = [], [], [], [], 0
    if ds_phieu:
        bang = frappe.get_all(
            "SX Bang Vao Hop", filters={"ngay_sx": ("in", ds_phieu), "docstatus": 1},
            pluck="name",
        )
        if bang:
            rows = frappe.get_all(
                "SX Bang Vao Hop Item",
                filters={"parent": ("in", bang), "parenttype": "SX Bang Vao Hop"},
                fields=["nhan_vien", "ten_nhan_vien", "san_pham", "so_hop", "thanh_tien"],
            )
            gop_sku, gop_nv = {}, {}
            for r in rows:
                s = gop_sku.setdefault(r.san_pham, {"san_pham": r.san_pham, "so_hop": 0})
                s["so_hop"] += cint(r.so_hop)
                g = gop_nv.setdefault(
                    r.nhan_vien,
                    {"nhan_vien": r.nhan_vien, "ten": r.ten_nhan_vien, "so_hop": 0, "tien": 0.0},
                )
                g["so_hop"] += cint(r.so_hop)
                g["tien"] += flt(r.thanh_tien)
            san_luong_sku = sorted(gop_sku.values(), key=lambda x: -x["so_hop"])
            nang_suat = sorted(gop_nv.values(), key=lambda x: -x["so_hop"])

        cs_rows = frappe.get_all(
            "SX Cong Suat May",
            filters={"parent": ("in", ds_phieu), "parenttype": "SX Ngay San Xuat"},
            fields=["may", "so_thung"],
        )
        gop_may = {}
        for r in cs_rows:
            m = gop_may.setdefault(r.may, {"may": r.may, "so_thung": 0})
            m["so_thung"] += cint(r.so_thung)
        for m in gop_may.values():
            dinh_muc = cint(frappe.db.get_value("SX May", m["may"], "cong_suat_dinh_muc"))
            m["dinh_muc_ky"] = dinh_muc * so_ngay
            m["pct"] = flt(m["so_thung"] / m["dinh_muc_ky"] * 100, 1) if m["dinh_muc_ky"] else None
        cong_suat = sorted(gop_may.values(), key=lambda x: x["may"])

        su_co = frappe.get_all(
            "SX Su Co Item",
            filters={"parent": ("in", ds_phieu), "parenttype": "SX Ngay San Xuat"},
            fields=["loai", "phut_dung", "mo_ta", "thoi_diem"],
        )
        phut_dung = sum(cint(r.phut_dung) for r in su_co)

    # Tồn hỗn hợp hiện tại — âm = đóng gói nhiều hơn trộn tích luỹ (quên báo mẻ)
    settings = get_settings()
    ton_hh = []
    for it in frappe.get_all("Item", filters={"custom_sx_nhom": "BTP-HH"}, pluck="name"):
        qty = flt(
            frappe.db.get_value(
                "Bin", {"item_code": it, "warehouse": settings.kho_btp}, "actual_qty"
            )
        )
        ton_hh.append({"item": it, "ton_kg": flt(qty, 1), "am": qty < 0})

    try:
        yield_dm = flt(get_yield_tang_1(), 4)
    except Exception:
        yield_dm = None

    return {
        "tu_ngay": str(tu_ngay),
        "den_ngay": str(den_ngay),
        "phieu": [
            {
                "name": p.name,
                "ngay": str(p.ngay),
                "tong_hop_tp": cint(p.tong_hop_tp),
                "tong_luong_sp": flt(p.tong_luong_sp),
            }
            for p in phieu
        ],
        "san_luong_sku": san_luong_sku,
        "nang_suat_vao_hop": nang_suat,
        "cong_suat_may": cong_suat,
        "su_co": [
            {
                "loai": r.loai,
                "phut_dung": cint(r.phut_dung),
                "mo_ta": r.mo_ta,
                "thoi_diem": str(r.thoi_diem),
            }
            for r in su_co
        ],
        "phut_dung": phut_dung,
        "ton_hon_hop": ton_hh,
        "yield_dinh_muc": yield_dm,
    }


@frappe.whitelist()
def truy_xuat(batch_tp):
    """Chuỗi truy xuất ngược: batch TP -> hỗn hợp -> lô rang R -> lô đậu NCC (spec §1)."""
    _guard([QUAN_LY])
    settings = get_settings()
    if not frappe.db.exists("Batch", batch_tp):
        frappe.throw(_("Không tìm thấy batch {0}").format(batch_tp))
    batch_doc = frappe.db.get_value(
        "Batch", batch_tp, ["item", "creation"], as_dict=True
    )

    ket_qua = {
        "batch_tp": batch_tp,
        "item_tp": batch_doc.item,
        "hon_hop": [],
    }

    # SE T3: batch TP là thành phẩm
    se_t3 = frappe.get_all(
        "Stock Entry Detail",
        filters={"batch_no": batch_tp, "is_finished_item": 1, "docstatus": 1},
        pluck="parent",
    )
    for se in set(se_t3):
        rm_hh = frappe.get_all(
            "Stock Entry Detail",
            filters={"parent": se, "is_finished_item": 0, "docstatus": 1},
            fields=["item_code", "batch_no", "qty"],
        )
        for rm in rm_hh:
            if frappe.get_cached_value("Item", rm.item_code, "custom_sx_nhom") != "BTP-HH":
                continue
            hh = {
                "se_t3": se,
                "item": rm.item_code,
                "batch": rm.batch_no,
                "kg": flt(rm.qty, 2),
                "bot": [],
            }
            # SE T2: batch hỗn hợp là thành phẩm -> RM bột
            if rm.batch_no:
                se_t2 = frappe.get_all(
                    "Stock Entry Detail",
                    filters={"batch_no": rm.batch_no, "is_finished_item": 1, "docstatus": 1},
                    pluck="parent",
                )
                for se2 in set(se_t2):
                    rm_bot = frappe.get_all(
                        "Stock Entry Detail",
                        filters={
                            "parent": se2,
                            "is_finished_item": 0,
                            "item_code": settings.item_bot,
                            "docstatus": 1,
                        },
                        fields=["batch_no", "qty"],
                    )
                    for b in rm_bot:
                        lo_rang = (
                            frappe.db.get_value("Batch", b.batch_no, "custom_lo_rang")
                            or b.batch_no
                        )
                        xd = frappe.db.get_value(
                            "SX Xuat Dau",
                            {"lo_rang": lo_rang, "docstatus": 1},
                            ["name", "lo_dau_ncc", "ngay_rang", "so_bao"],
                            as_dict=True,
                        )
                        hh["bot"].append(
                            {
                                "se_t2": se2,
                                "batch_bot": b.batch_no,
                                "kg": flt(b.qty, 2),
                                "lo_rang": lo_rang,
                                "xuat_dau": xd.name if xd else None,
                                "lo_dau_ncc": xd.lo_dau_ncc if xd else None,
                                "ngay_rang": str(xd.ngay_rang) if xd else None,
                            }
                        )
            ket_qua["hon_hop"].append(hh)

    return ket_qua
