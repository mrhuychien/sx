"""Seed Item + BOM tầng 1/2 từ workbook định mức RVHG (Phase 0 bán tự động).

Chạy TRÊN SITE, sau khi đã có Company + 3 Warehouse + SX Settings:

    bench --site a.rongvanghoanggia.com execute sx.seed.seed_all --kwargs "{'dry_run': 1}"
    bench --site a.rongvanghoanggia.com execute sx.seed.seed_all

`dry_run=1` chỉ in kế hoạch, KHÔNG ghi gì. Chạy lại nhiều lần an toàn (idempotent):
Item/BOM đã có -> bỏ qua, không ghi đè số liệu người dùng đã sửa tay.

KHÔNG ship BOM qua `fixtures/`: fixtures import theo alphabet tên file, chạy full
validate, không kiểm soát được thứ tự phụ thuộc (bột nền phải Active TRƯỚC
đường hoán màu; bột nền trước bột bánh) và BOM là doctype submittable — rất dễ
chết `install-app`. Seed bằng method chủ động gọi thì kiểm soát được thứ tự + báo
lỗi rõ ràng.

Nguồn số liệu: sx/seed/rvhg_v6.json (sinh tự động từ workbook v6 — 16/16 câu hỏi đã
chốt; không sửa tay file JSON, sửa workbook rồi trích lại).

Tên item = cột A sheet DANH MUC ITEM = tên THẬT trên ERPNext (quy ước RVHG: ID = tên
tiếng Việt có dấu, D15). Tên trong công thức (cột B) chỉ là alias — đã map sẵn khi
trích, gồm các quyết định CH-04 (Sữa dừa = Bột sữa dừa), CH-14 (Đường kính VN =
Đường nghệ an), CH-15 (Đường TQ = Đường Gluco China), CH-16 (hương liệu quy Kg).

BOM tầng 3 (SKU) KHÔNG seed — CH-13 đã chốt: chủ đầu tư tự tạo BOM trên ERPNext.
"""

import json
import os

import frappe
from frappe import _
from frappe.utils import cint, flt

DATA_FILE = "rvhg_v6.json"


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
            # Đối chiếu cờ kho/lô của item ĐÃ CÓ — KHÔNG tự sửa (Frappe chặn đổi
            # has_batch_no/is_stock_item khi đã có ledger), chỉ cảnh báo: thiếu batch
            # là vỡ FIFO-truy-xuất (D5), lệch is_stock_item là vỡ cân bằng BOM.
            hien = frappe.db.get_value(
                "Item", ten, ["has_batch_no", "is_stock_item", "stock_uom"], as_dict=True
            ) or {}
            if it.get("has_batch") and not cint(hien.get("has_batch_no")):
                bao_cao["canh_bao"].append(
                    f"Item '{ten}' ĐANG TẮT has_batch_no — cần bật để FIFO truy xuất lô "
                    f"chạy được (D5). Nếu item đã có ledger, Frappe chặn đổi: phải xử lý tay."
                )
            if cint(hien.get("is_stock_item")) != cint(it.get("is_stock", 1)):
                bao_cao["canh_bao"].append(
                    f"Item '{ten}' is_stock_item={hien.get('is_stock_item')} nhưng workbook "
                    f"cần {it.get('is_stock', 1)} — kiểm tra tay."
                )
            if hien.get("stock_uom") and hien["stock_uom"] != it["uom"]:
                bao_cao["canh_bao"].append(
                    f"Item '{ten}' ĐVT trên site = '{hien['stock_uom']}' nhưng workbook ghi "
                    f"'{it['uom']}' — BOM sẽ tính theo ĐVT trên site, đối chiếu lại."
                )
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
    (bột nền + đường hoán -> bột bánh/bột đậu)."""
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

    bo_qua_gia_dinh=1: KHÔNG tạo BOM nào bị đánh dấu giả định (v6 hiện KHÔNG có).
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
            # BOM nhập tay Phase 0 thường THIẾU custom_co_me_chuan_kg → báo mẻ sẽ bị
            # chặn (controller throw). Field không allow_on_submit nên Desk không sửa
            # được sau submit → bù bằng db_set (giá trị = qty của BOM, khớp mọi BOM
            # báo mẻ trong workbook), và luôn báo rõ ra bảng cảnh báo.
            can_co_me = flt(b.get("co_me_chuan_kg"))
            if can_co_me:
                dang_co = flt(frappe.db.get_value("BOM", da_co, "custom_co_me_chuan_kg"))
                if not dang_co:
                    if not dry_run:
                        frappe.db.set_value(
                            "BOM", da_co, "custom_co_me_chuan_kg", can_co_me,
                            update_modified=False,
                        )
                    bao_cao["canh_bao"].append(
                        f"BOM có sẵn {da_co} ({item}) THIẾU cỡ mẻ → đã bù {can_co_me} kg "
                        f"{'(dry-run: chưa ghi)' if dry_run else ''}".strip()
                    )
                elif abs(dang_co - can_co_me) > 1e-6:
                    bao_cao["canh_bao"].append(
                        f"BOM có sẵn {da_co} ({item}) cỡ mẻ = {dang_co} kg, workbook ghi "
                        f"{can_co_me} kg — GIỮ số trên site, đối chiếu lại nếu sai."
                    )
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


def _kiem_custom_field():
    """Chặn seed nếu Custom Field của app chưa sync.

    Frappe bỏ IM LẶNG key không có trong meta khi insert (get_valid_dict), nên thiếu
    field là 21 giá trị cỡ mẻ + nhóm SX bị mất trắng mà báo cáo vẫn "thành công".
    """
    thieu = [
        f"{dt}.{fn}"
        for dt, fn in (
            ("Item", "custom_sx_nhom"),
            ("Item", "custom_batch_prefix"),
            ("BOM", "custom_co_me_chuan_kg"),
        )
        if not frappe.get_meta(dt).has_field(fn)
    ]
    if thieu:
        frappe.throw(
            _("Chưa có Custom Field: {0}. Chạy `bench --site <site> migrate` (sync fixtures "
              "của app sx) TRƯỚC khi seed — nếu không, số liệu sẽ bị bỏ im lặng.").format(
                ", ".join(thieu)
            )
        )


def seed_stock_entry_type(dry_run=0, bao_cao=None):
    """Bảo đảm có Stock Entry Type chuẩn cho Manufacture (D28).

    ERPNext ship sẵn bản ghi này, nhưng site RVHG đã bị xoá/không có -> mọi phiếu
    kho Manufacture sinh ra trống `stock_entry_type` và chết ở validate. Core CHỈ
    tìm bản ghi khớp {purpose, is_standard=1} nên phải đúng cả 2 điều kiện.
    Idempotent: đã có thì bỏ qua, không đụng bản ghi tự đặt của site.
    """
    ket_qua = []
    # Manufacture (tầng 2/3) · Repack + Material Transfer (công đoạn tầng 1 — D31)
    for purpose in ("Manufacture", "Repack", "Material Transfer"):
        if frappe.db.get_value(
            "Stock Entry Type", {"purpose": purpose, "is_standard": 1}, "name"
        ):
            continue
        if frappe.db.exists("Stock Entry Type", purpose):
            # Bản ghi đúng tên nhưng thiếu tick chuẩn -> bật lại, không tạo trùng
            if not dry_run:
                frappe.db.set_value("Stock Entry Type", purpose, "is_standard", 1)
            ket_qua.append(f"Stock Entry Type '{purpose}': bật lại Is Standard")
            continue
        if not dry_run:
            # autoname = Prompt -> đặt tên qua __newname
            doc = frappe.new_doc("Stock Entry Type")
            doc.__newname = purpose
            doc.purpose = purpose
            doc.is_standard = 1
            doc.flags.ignore_permissions = True
            doc.insert()
        ket_qua.append(f"Stock Entry Type '{purpose}': tạo mới (is_standard=1)")
    if bao_cao is not None:
        bao_cao["canh_bao"].extend(ket_qua)
    return ket_qua


def seed_btp_dau(dry_run=0, bao_cao=None):
    """Tạo Item bán thành phẩm ĐỖ Ủ / ĐỖ VỠ cho mọi loại đỗ (D31).

    Luồng tầng 1 theo lưu đồ có 2 chặng trung gian nhìn thấy được ở kho xưởng.
    Tên suy từ tên đỗ ("Đỗ xanh" -> "Đỗ xanh ủ" / "Đỗ xanh vỡ"), ĐVT + nhóm item
    lấy theo chính item đỗ. Idempotent.
    """
    from sx.utils import get_dau_items, ten_btp_dau

    ket_qua = []
    for dau in get_dau_items():
        goc = frappe.db.get_value(
            "Item", dau["name"], ["stock_uom", "item_group"], as_dict=True
        ) or {}
        for chang in ("u", "vo"):
            ten = ten_btp_dau(dau["name"], chang)
            if frappe.db.exists("Item", ten):
                continue
            if not dry_run:
                doc = frappe.get_doc({
                    "doctype": "Item",
                    "item_code": ten,
                    "item_name": ten,
                    "item_group": goc.get("item_group") or _item_group("All Item Groups"),
                    "stock_uom": goc.get("stock_uom") or "Kg",
                    "is_stock_item": 1,
                    # Batch = lô R + hậu tố (mã lô do code đặt, không cho ERPNext tự sinh)
                    "has_batch_no": 1,
                    "create_new_batch": 0,
                    "custom_sx_nhom": "BTP-Dau",
                    "description": _("Bán thành phẩm tầng 1 — {0}").format(ten),
                })
                doc.flags.ignore_permissions = True
                doc.insert()
            ket_qua.append(f"Item '{ten}': tạo mới (BTP-Dau)")
    if bao_cao is not None:
        bao_cao["item_tao"].extend(ket_qua)
    if not dry_run and ket_qua:
        frappe.db.commit()
    for x in ket_qua:
        print("   •", x)
    if not ket_qua:
        print("   • Đã có đủ Item đỗ ủ / đỗ vỡ, không tạo thêm.")
    return ket_qua


def seed_all(dry_run=0, bo_qua_gia_dinh=0):
    """Seed Item + BOM tầng 1/2 rồi in báo cáo. dry_run=1 để xem trước, không ghi."""
    dry_run = int(dry_run or 0)
    _kiem_custom_field()
    data = _data()
    bao_cao = _bao_cao_moi()
    seed_stock_entry_type(dry_run=dry_run, bao_cao=bao_cao)
    seed_items(dry_run=dry_run, bao_cao=bao_cao)
    seed_boms(dry_run=dry_run, bo_qua_gia_dinh=int(bo_qua_gia_dinh or 0), bao_cao=bao_cao)
    # SAU seed_boms: danh mục đỗ suy từ BOM tầng 1 active
    seed_btp_dau(dry_run=dry_run, bao_cao=bao_cao)

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

    print("\n── QUYẾT ĐỊNH ĐÃ CHỐT (đã áp vào số liệu seed):")
    for q in data.get("quyet_dinh_da_chot", []):
        print(f"   ✔ {q}")
    print("\n── CÒN PHẢI LÀM TAY:")
    for x in data.get("con_lam_tay", []):
        print(f"   • {x}")
    print("=" * 72)

    if not dry_run:
        frappe.db.commit()
    return bao_cao
