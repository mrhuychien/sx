"""Whitelisted API cho portal SPA /sx.

Mọi method: guard role ở dòng đầu (spec mục 3 — method-mediated permission).
Dữ liệu doc chuẩn (Employee, BOM...) chỉ trả về field trong whitelist.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from sx.api.common import QUAN_LY, TO_TRUONG, TRAM_RANG, _guard
from sx.utils import get_settings, get_yield_tang_1


# ─────────────────────────────────────────────────────────────── boot ──


@frappe.whitelist()
def get_boot():
    """Context khởi động portal: phiếu ngày hôm nay, list Item TP, settings công khai,
    lần ghi CCP gần nhất, danh sách nhân viên (chỉ name + employee_name)."""
    _guard([TO_TRUONG, TRAM_RANG, QUAN_LY])
    roles = set(frappe.get_roles())
    hom_nay = nowdate()

    ngay_sx = None
    ten_phieu = frappe.db.get_value(
        "SX Ngay San Xuat", {"ngay": hom_nay, "docstatus": ("<", 2)}, "name"
    )
    if ten_phieu:
        # ignore_permissions: Tram Rang chỉ có read nhưng cần đủ context — field đã whitelist
        doc = frappe.get_doc("SX Ngay San Xuat", ten_phieu)
        ngay_sx = {
            "name": doc.name,
            "ngay": str(doc.ngay),
            "docstatus": doc.docstatus,
            "trang_thai": doc.trang_thai,
            "chay_tang_1": doc.chay_tang_1,
            "so_bao_dau": doc.so_bao_dau,
            "kl_bao_kg": doc.kl_bao_kg,
            "dau_vao_kg": doc.dau_vao_kg,
            "btp_du_kien_kg": doc.btp_du_kien_kg,
            "tong_hop": doc.tong_hop,
            "tong_luong_sp": doc.tong_luong_sp,
            "san_pham_tang_2": [
                {"san_pham": r.san_pham, "so_hop_thuc_te": r.so_hop_thuc_te}
                for r in doc.san_pham_tang_2
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

    ccp_list = []
    so_me_tron = 0
    bang_vao_hop = None
    if ten_phieu:
        ccp_list = frappe.get_all(
            "SX Ghi Nhan CCP",
            filters={"ngay_sx": ten_phieu},
            fields=["name", "thoi_diem", "nhiet_do_c", "dat", "hanh_dong_khac_phuc"],
            order_by="thoi_diem desc",
            limit=50,
        )
        so_me_tron = frappe.db.count(
            "SX Me Tron", {"ngay_sx": ten_phieu, "docstatus": ("<", 2)}
        )
        bang_vao_hop = _bang_vao_hop_summary(ten_phieu)

    settings = get_settings()
    items_tp = frappe.get_all(
        "Item",
        filters={"custom_sx_nhom": "TP", "disabled": 0},
        fields=["name", "item_name"],
    )
    # Cỡ mẻ chuẩn lấy từ BOM active của từng SP (1 nguồn sự thật)
    for it in items_tp:
        it["co_me_chuan_kg"] = flt(
            frappe.db.get_value(
                "BOM",
                {"item": it["name"], "is_active": 1, "is_default": 1, "docstatus": 1},
                "custom_co_me_chuan_kg",
            )
        )

    nhan_vien = []
    if roles & {TO_TRUONG, QUAN_LY, "System Manager"}:
        # Whitelist field: KHÔNG lộ lương/CCCD (spec mục 3)
        nhan_vien = frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=["name", "employee_name"],
            order_by="employee_name",
        )

    return {
        "user": frappe.session.user,
        "is_quan_ly": bool(roles & {QUAN_LY, "System Manager"}),
        "is_to_truong": bool(roles & {TO_TRUONG, QUAN_LY, "System Manager"}),
        "is_tram_rang": TRAM_RANG in roles,
        "hom_nay": hom_nay,
        "ngay_sx": ngay_sx,
        "ccp_list": ccp_list,
        "so_me_tron": so_me_tron,
        "bang_vao_hop": bang_vao_hop,
        "items_tp": items_tp,
        "nhan_vien": nhan_vien,
        "settings": {
            "ccp_nhiet_min": flt(settings.ccp_nhiet_min),
            "ccp_nhiet_max": flt(settings.ccp_nhiet_max),
            "tan_suat_ghi_ccp_phut": cint(settings.tan_suat_ghi_ccp_phut) or 60,
            "kl_bao_dau_kg": flt(settings.kl_bao_dau_kg),
            "me_tron_nguong_canh_bao_pct": flt(settings.me_tron_nguong_canh_bao_pct) or 2,
        },
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


# ─────────────────────────────────────────────────────────── mở ngày ──


@frappe.whitelist()
def mo_ngay(chay_tang_1=0, so_bao=0, kl_bao=0, ds_san_pham=None):
    """Tạo phiếu SX Ngay San Xuat draft cho hôm nay. Chặn nếu ngày đã có phiếu."""
    _guard([TO_TRUONG, QUAN_LY])
    ds_san_pham = frappe.parse_json(ds_san_pham or "[]")
    doc = frappe.new_doc("SX Ngay San Xuat")
    doc.ngay = nowdate()
    doc.chay_tang_1 = cint(chay_tang_1)
    doc.so_bao_dau = cint(so_bao)
    doc.kl_bao_kg = flt(kl_bao) or flt(get_settings().kl_bao_dau_kg)
    for sp in ds_san_pham:
        doc.append("san_pham_tang_2", {"san_pham": sp})
    doc.insert()  # To Truong có create DocPerm — không cần ignore_permissions
    return {"name": doc.name, "ngay": str(doc.ngay), "btp_du_kien_kg": doc.btp_du_kien_kg}


# ─────────────────────────────────────────────────────────────── CCP ──


@frappe.whitelist()
def ghi_ccp(ngay_sx, nhiet_do_c, ghi_chu=None, hanh_dong=None):
    """Ghi 1 bản ghi CCP. Nhiệt lệch mà chưa có hành động khắc phục -> trả
    can_hanh_dong=True (KHÔNG insert) để portal mở modal bắt nhập ngay."""
    _guard([TRAM_RANG, TO_TRUONG, QUAN_LY])
    settings = get_settings()
    nhiet_min, nhiet_max = flt(settings.ccp_nhiet_min), flt(settings.ccp_nhiet_max)
    nhiet = flt(nhiet_do_c)
    dat = nhiet_min <= nhiet <= nhiet_max

    if not dat and not (hanh_dong or "").strip():
        return {"can_hanh_dong": True, "dat": False, "min": nhiet_min, "max": nhiet_max}

    doc = frappe.new_doc("SX Ghi Nhan CCP")
    doc.ngay_sx = ngay_sx
    doc.nhiet_do_c = nhiet
    doc.ghi_chu = ghi_chu
    doc.hanh_dong_khac_phuc = hanh_dong
    doc.insert()
    return {"name": doc.name, "dat": bool(doc.dat), "min": nhiet_min, "max": nhiet_max}


# ──────────────────────────────────────────────────────────── mẻ trộn ──


@frappe.whitelist()
def prefill_me_tron(san_pham, co_me_kg=None):
    """Từ BOM active của SP: lấy dòng custom_nl_tron=1, scale theo tỉ trọng trong
    nhóm trộn × cỡ mẻ -> rows định mức (spec 5.3)."""
    _guard([TO_TRUONG, QUAN_LY])
    bom_name = frappe.db.get_value(
        "BOM", {"item": san_pham, "is_active": 1, "is_default": 1, "docstatus": 1}, "name"
    )
    if not bom_name:
        frappe.throw(_("Sản phẩm {0} chưa có BOM active").format(san_pham))
    bom = frappe.get_cached_doc("BOM", bom_name)
    co_me_chuan = flt(bom.custom_co_me_chuan_kg)
    co_me = flt(co_me_kg) or co_me_chuan
    if not co_me:
        frappe.throw(
            _("BOM {0} chưa điền cỡ mẻ chuẩn (custom_co_me_chuan_kg)").format(bom_name)
        )

    nhom_tron = [r for r in bom.items if cint(r.get("custom_nl_tron"))]
    if not nhom_tron:
        frappe.throw(
            _("BOM {0} chưa đánh dấu dòng NL nhóm trộn (custom_nl_tron)").format(bom_name)
        )
    tong_kg = sum(flt(r.stock_qty) for r in nhom_tron)
    rows = [
        {
            "item": r.item_code,
            "item_name": r.item_name,
            "dinh_muc_kg": flt(flt(r.stock_qty) / tong_kg * co_me, 3),
        }
        for r in nhom_tron
    ]
    return {
        "bom": bom_name,
        "co_me_kg": co_me,
        "co_me_chuan_kg": co_me_chuan,
        "rows": rows,
    }


@frappe.whitelist()
def luu_me_tron(payload):
    """Insert + submit SX Me Tron từ payload portal."""
    _guard([TO_TRUONG, QUAN_LY])
    data = frappe.parse_json(payload)
    doc = frappe.new_doc("SX Me Tron")
    doc.ngay_sx = data.get("ngay_sx")
    doc.san_pham = data.get("san_pham")
    doc.bom = data.get("bom")
    doc.co_me_kg = flt(data.get("co_me_kg"))
    for r in data.get("nguyen_lieu") or []:
        doc.append(
            "nguyen_lieu",
            {
                "item": r.get("item"),
                "dinh_muc_kg": flt(r.get("dinh_muc_kg")),
                "thuc_can_kg": flt(r.get("thuc_can_kg", r.get("dinh_muc_kg"))),
                "batch_no": r.get("batch_no"),
            },
        )
    doc.insert()
    doc.submit()
    return {
        "name": doc.name,
        "me_so": doc.me_so,
        "dung_cong_thuc": bool(doc.dung_cong_thuc),
        "tong_lech_pct": flt(doc.tong_lech_pct, 2),
    }


# ──────────────────────────────────────────────────────────── vào hộp ──


@frappe.whitelist()
def luu_bang_vao_hop(payload):
    """Upsert DRAFT SX Bang Vao Hop (auto-save từng dòng từ portal).
    Đơn giá luôn lookup server-side trong controller — client gửi gì cũng bị tính lại."""
    _guard([TO_TRUONG, QUAN_LY])
    data = frappe.parse_json(payload)
    ngay_sx = data.get("ngay_sx")
    if not ngay_sx:
        frappe.throw(_("Thiếu phiếu ngày"))
    if frappe.db.get_value("SX Ngay San Xuat", ngay_sx, "docstatus") != 0:
        frappe.throw(_("Phiếu ngày đã chốt — không sửa được bảng vào hộp"))

    ten = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": ngay_sx, "docstatus": 0}, "name"
    )
    doc = frappe.get_doc("SX Bang Vao Hop", ten) if ten else frappe.new_doc("SX Bang Vao Hop")
    doc.ngay_sx = ngay_sx
    doc.set("dong", [])
    for r in data.get("dong") or []:
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


# ───────────────────────────────────────────────────────────── sự cố ──


@frappe.whitelist()
def ghi_su_co(ngay_sx, loai, mo_ta=None, phut_dung=0):
    """Append 1 dòng sự cố vào phiếu ngày draft."""
    _guard([TO_TRUONG, QUAN_LY])
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


# ──────────────────────────────────────────────────────────── dashboard ──


@frappe.whitelist()
def dashboard(tu_ngay=None, den_ngay=None):
    """Số liệu quản lý (V5): sản lượng, yield, %CCP đạt, phút dừng, năng suất vào hộp/người."""
    _guard([QUAN_LY])
    den_ngay = getdate(den_ngay or nowdate())
    tu_ngay = getdate(tu_ngay) if tu_ngay else frappe.utils.add_days(den_ngay, -6)

    phieu = frappe.get_all(
        "SX Ngay San Xuat",
        filters={"ngay": ("between", (tu_ngay, den_ngay)), "docstatus": 1},
        fields=[
            "name", "ngay", "dau_vao_kg", "btp_thuc_te_kg", "tong_hop", "tong_luong_sp",
        ],
        order_by="ngay",
    )
    ds_phieu = [p.name for p in phieu]

    # %CCP đạt trong kỳ
    ccp_tong = ccp_dat = 0
    if ds_phieu:
        ccp_tong = frappe.db.count("SX Ghi Nhan CCP", {"ngay_sx": ("in", ds_phieu)})
        ccp_dat = frappe.db.count(
            "SX Ghi Nhan CCP", {"ngay_sx": ("in", ds_phieu), "dat": 1}
        )

    # Phút dừng sự cố — child table, query qua parent đã lọc
    phut_dung = 0
    su_co = []
    if ds_phieu:
        su_co = frappe.get_all(
            "SX Su Co Item",
            filters={"parent": ("in", ds_phieu), "parenttype": "SX Ngay San Xuat"},
            fields=["loai", "phut_dung", "mo_ta", "thoi_diem"],
        )
        phut_dung = sum(cint(r.phut_dung) for r in su_co)

    # Năng suất vào hộp theo người (chỉ bảng đã submit)
    nang_suat = []
    if ds_phieu:
        bang = frappe.get_all(
            "SX Bang Vao Hop", filters={"ngay_sx": ("in", ds_phieu), "docstatus": 1},
            pluck="name",
        )
        if bang:
            rows = frappe.get_all(
                "SX Bang Vao Hop Item",
                filters={"parent": ("in", bang), "parenttype": "SX Bang Vao Hop"},
                fields=["nhan_vien", "ten_nhan_vien", "so_hop", "thanh_tien"],
            )
            gop = {}
            for r in rows:
                g = gop.setdefault(
                    r.nhan_vien,
                    {"nhan_vien": r.nhan_vien, "ten": r.ten_nhan_vien, "so_hop": 0, "tien": 0.0},
                )
                g["so_hop"] += cint(r.so_hop)
                g["tien"] += flt(r.thanh_tien)
            nang_suat = sorted(gop.values(), key=lambda g: -g["so_hop"])

    tong_dau = sum(flt(p.dau_vao_kg) for p in phieu)
    tong_btp = sum(flt(p.btp_thuc_te_kg) for p in phieu)
    return {
        "tu_ngay": str(tu_ngay),
        "den_ngay": str(den_ngay),
        "phieu": [
            {
                "name": p.name,
                "ngay": str(p.ngay),
                "dau_vao_kg": flt(p.dau_vao_kg),
                "btp_thuc_te_kg": flt(p.btp_thuc_te_kg),
                "tong_hop": cint(p.tong_hop),
                "tong_luong_sp": flt(p.tong_luong_sp),
            }
            for p in phieu
        ],
        "yield_dinh_muc": flt(get_yield_tang_1(), 4),
        "yield_thuc": flt(tong_btp / tong_dau, 4) if tong_dau else 0,
        "ccp_tong": ccp_tong,
        "ccp_dat": ccp_dat,
        "ccp_pct_dat": flt(ccp_dat / ccp_tong * 100, 1) if ccp_tong else None,
        "phut_dung": phut_dung,
        "su_co": [
            {
                "loai": r.loai,
                "phut_dung": cint(r.phut_dung),
                "mo_ta": r.mo_ta,
                "thoi_diem": str(r.thoi_diem),
            }
            for r in su_co
        ],
        "nang_suat_vao_hop": nang_suat,
    }
