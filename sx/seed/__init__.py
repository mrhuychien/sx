"""Seed Item + BOM tầng 1/2 từ workbook định mức RVHG (Phase 0 bán tự động).

Chạy TRÊN SITE, sau khi đã có Company + 3 Warehouse + SX Settings:

    bench --site a.rongvanghoanggia.com execute sx.seed.seed_all --kwargs "{'dry_run': 1}"
    bench --site a.rongvanghoanggia.com execute sx.seed.seed_all

`dry_run=1` chỉ in kế hoạch, KHÔNG ghi gì. Chạy lại nhiều lần an toàn (idempotent):
Item/BOM đã có -> bỏ qua, không ghi đè số liệu người dùng đã sửa tay.

KHÔNG ship BOM qua `fixtures/`: fixtures import theo alphabet tên file, chạy full
validate, không kiểm soát được thứ tự phụ thuộc (hỗn hợp màu phải Active TRƯỚC
đường hoán màu; bột nền trước bột bánh) và BOM là doctype submittable — rất dễ
chết `install-app`. Seed bằng method chủ động gọi thì kiểm soát được thứ tự + báo
lỗi rõ ràng.

Nguồn số liệu: sx/seed/rvhg_v3.json (sinh tự động từ workbook, không sửa tay).
BOM tầng 3 (SKU) KHÔNG seed — workbook chưa có số liệu (CH-13).
"""

import json
import os

import frappe
from frappe import _
from frappe.utils import flt

DATA_FILE = "rvhg_v3.json"


def _data():
    path = os.path.join(os.path.dirname(__file__), DATA_FILE)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _company():
    cong_ty = frappe.db.get_single_value("SX Settings", "cong_ty")
    if not cong_ty:
        cong_ty = frappe.defaults.get_defaults().get("company") or frappe.db.get_value(
            "Company", {}, "name"
        )
    if not cong_ty:
        frappe.throw(_("Chưa có Company nào — tạo Company rồi điền SX Settings trước khi seed."))
    return cong_ty


def _uom(ten):
    """UOM phải tồn tại trước khi tạo Item (vd 'Lít' không có sẵn trên site mới)."""
    if frappe.db.exists("UOM", ten):
        return ten
    frappe.get_doc({"doctype": "UOM", "uom_name": ten, "enabled": 1}).insert(
        ignore_permissions=True
    )
    return ten


def _item_group(ten):
    """Item Group: dùng nhóm chuẩn ERPNext, fallback 'All Item Groups' nếu site không có."""
    if frappe.db.exists("Item Group", ten):
        return ten
    return frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"


# ─────────────────────────────────────────────────────────── Item ──


def seed_items(dry_run=0, bao_cao=None):
    """Tạo Item còn thiếu. Item đã có -> chỉ bù custom_sx_nhom / custom_batch_prefix
    khi đang TRỐNG (không ghi đè giá trị người dùng đã đặt)."""
    bao_cao = bao_cao if bao_cao is not None else _bao_cao_moi()
    data = _data()
    for it in data["items"]:
        ten = it["item_code"]
        if frappe.db.exists("Item", ten):
            bu = {}
            for field, val in (
                ("custom_sx_nhom", it["nhom"]),
                ("custom_batch_prefix", it.get("prefix") or None),
            ):
                if val and not frappe.db.get_value("Item", ten, field):
                    bu[field] = val
            if bu and not dry_run:
                frappe.db.set_value("Item", ten, bu)
            bao_cao["item_bo_qua"].append(f"{ten}{' (bù ' + ','.join(bu) + ')' if bu else ''}")
            continue

        if dry_run:
            bao_cao["item_tao"].append(f"{ten} [{it['nhom']}, {it['uom']}]")
            continue

        uom = _uom(it["uom"])
        doc = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": ten,
                "item_name": ten,
                "item_group": _item_group(it["item_group"]),
                "stock_uom": uom,
                "is_stock_item": 1 if it.get("is_stock") else 0,
                # has_batch_no + create_new_batch=0: mã lô do code/người nhập đặt tường
                # minh (lô NCC khi mua, lô R / {prefix}-DDMMYY khi sản xuất) — chặn
                # ERPNext tự sinh batch rác, giữ kỷ luật truy xuất D5/D13.
                "has_batch_no": 1 if it.get("has_batch") else 0,
                "create_new_batch": 0,
                "custom_sx_nhom": it["nhom"],
                "custom_batch_prefix": it.get("prefix") or None,
                "description": it.get("ghi_chu") or ten,
            }
        )
        doc.flags.ignore_permissions = True
        doc.insert()
        bao_cao["item_tao"].append(ten)
    return bao_cao


# ─────────────────────────────────────────────────────────── BOM ──


def _thu_tu_bom(boms):
    """Topo sort: BOM sinh ra item X phải chạy TRƯỚC BOM dùng X làm nguyên liệu
    (hỗn hợp màu -> đường hoán màu; bột nền -> bột bánh/bột đậu)."""
    by_out = {b["item"]: b for b in boms}
    xong, thu_tu, dang_xu_ly = set(), [], set()

    def _di(b):
        key = b["bom"]
        if key in xong or key in dang_xu_ly:
            return
        dang_xu_ly.add(key)
        for r in b["rm"]:
            cha = by_out.get(r["item"])
            if cha and cha["bom"] != key:
                _di(cha)
        dang_xu_ly.discard(key)
        if key not in xong:
            xong.add(key)
            thu_tu.append(b)

    for b in boms:
        _di(b)
    return thu_tu


def seed_boms(dry_run=0, bo_qua_gia_dinh=0, bao_cao=None):
    """Tạo + submit BOM tầng 1/2 theo thứ tự phụ thuộc. BOM active/default đã có
    cho item nào -> bỏ qua item đó.

    bo_qua_gia_dinh=1: KHÔNG tạo các BOM còn giả định (vd BOM bột đậu đen — CH-09).
    """
    bao_cao = bao_cao if bao_cao is not None else _bao_cao_moi()
    data = _data()
    cong_ty = _company()

    for b in _thu_tu_bom(data["boms"]):
        item = b["item"]
        if b.get("gia_dinh"):
            bao_cao["canh_bao"].append(f"{b['bom']}: {b['gia_dinh']}")
            if bo_qua_gia_dinh:
                bao_cao["bom_bo_qua"].append(f"{b['bom']} (giả định — bỏ qua theo yêu cầu)")
                continue

        da_co = frappe.db.get_value(
            "BOM", {"item": item, "is_active": 1, "is_default": 1, "docstatus": 1}, "name"
        )
        if da_co:
            bao_cao["bom_bo_qua"].append(f"{b['bom']} -> đã có {da_co}")
            continue

        thieu = [r["item"] for r in b["rm"] if not frappe.db.exists("Item", r["item"])]
        if not frappe.db.exists("Item", item):
            thieu.append(item)
        if thieu:
            bao_cao["loi"].append(
                f"{b['bom']}: thiếu Item {', '.join(sorted(set(thieu)))} — chạy seed_items trước"
            )
            continue

        if dry_run:
            bao_cao["bom_tao"].append(
                f"{b['bom']} -> {item} qty={b['qty']} {b['uom']} ({len(b['rm'])} NL)"
                + (f" cỡ mẻ={b['co_me_chuan_kg']}" if b.get("co_me_chuan_kg") else "")
            )
            continue

        doc = frappe.get_doc(
            {
                "doctype": "BOM",
                "item": item,
                "quantity": flt(b["qty"]),
                "uom": _uom(b["uom"]),
                "company": cong_ty,
                "is_active": 1,
                "is_default": 1,
                "with_operations": 0,
                "rm_cost_as_per": "Valuation Rate",
                "custom_co_me_chuan_kg": flt(b.get("co_me_chuan_kg") or 0),
                "items": [
                    {
                        "item_code": r["item"],
                        "qty": flt(r["qty"]),
                        "uom": _uom(r["uom"]),
                    }
                    for r in b["rm"]
                ],
            }
        )
        doc.flags.ignore_permissions = True
        doc.insert()
        doc.submit()
        bao_cao["bom_tao"].append(f"{b['bom']} -> {doc.name}")
    return bao_cao


# ─────────────────────────────────────────────────────────── chạy ──


def _bao_cao_moi():
    return {
        "item_tao": [], "item_bo_qua": [], "bom_tao": [], "bom_bo_qua": [],
        "canh_bao": [], "loi": [],
    }


def seed_all(dry_run=0, bo_qua_gia_dinh=0):
    """Seed Item + BOM tầng 1/2 rồi in báo cáo. dry_run=1 để xem trước, không ghi."""
    dry_run = int(dry_run or 0)
    data = _data()
    bao_cao = _bao_cao_moi()
    seed_items(dry_run=dry_run, bao_cao=bao_cao)
    seed_boms(dry_run=dry_run, bo_qua_gia_dinh=int(bo_qua_gia_dinh or 0), bao_cao=bao_cao)

    print("=" * 72)
    print(f"SEED ĐỊNH MỨC RVHG — nguồn: {data['nguon']}")
    print(f"Chế độ: {'DRY RUN (không ghi gì)' if dry_run else 'GHI THẬT'}")
    print("=" * 72)
    for nhan, khoa in (
        ("ITEM sẽ tạo" if dry_run else "ITEM đã tạo", "item_tao"),
        ("ITEM bỏ qua (đã có)", "item_bo_qua"),
        ("BOM sẽ tạo" if dry_run else "BOM đã tạo", "bom_tao"),
        ("BOM bỏ qua", "bom_bo_qua"),
    ):
        print(f"\n── {nhan}: {len(bao_cao[khoa])}")
        for x in bao_cao[khoa]:
            print(f"   • {x}")
    if bao_cao["canh_bao"]:
        print(f"\n⚠ CẢNH BÁO ({len(bao_cao['canh_bao'])}):")
        for x in bao_cao["canh_bao"]:
            print(f"   ! {x}")
    if bao_cao["loi"]:
        print(f"\n✗ LỖI ({len(bao_cao['loi'])}):")
        for x in bao_cao["loi"]:
            print(f"   ✗ {x}")

    print("\n── CÒN PHẢI LÀM TAY (workbook chưa có / câu hỏi chưa chốt):")
    print("   • BOM tầng 3 (SKU đóng gói) + Item TP + bao bì — CH-13, chặn chốt ngày nhánh TP")
    for ch in data["cau_hoi_chua_chot"]:
        print(f"   • {ch}")
    print("   • Manufacturing Settings: Backflush = BOM, Overproduction 5%,")
    print("     GIỮ TẮT 'Validate Components Quantities Per BOM' (xung đột FIFO tách lô)")
    print("   • Tồn đầu (Stock Reconciliation, batch TON-DDMMYY) + SX Don Gia Vao Hop")
    print("   • Purchase Receipt NVL PHẢI có batch = lô NCC (điều kiện FIFO truy xuất D5)")
    print("=" * 72)

    if not dry_run:
        frappe.db.commit()
    return bao_cao
