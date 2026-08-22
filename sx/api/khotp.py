"""Phiếu nhập kho thành phẩm — CHỨNG TỪ ĐỘC LẬP, sinh ra tồn kho TP (D62).

═══ LUỒNG ═══
    Người lập (QC / tổ đóng gói)  →  ghi hàng chuyển sang kho: loại nào, bao nhiêu
    →  PHIẾU NHÁP
    Thủ kho  →  đếm thật, sửa số cho khớp  →  DUYỆT
    →  lệnh SX chạy theo SỐ ĐẾM, hàng vào Kho TP, tồn cập nhật

═══ KHÔNG LIÊN QUAN GÌ TỚI GHI HỘP ═══
Bảng vào hộp chấm công cho từng người để tính lương khoán. Phiếu này ghi hàng thật
chuyển vào kho. Hai việc, hai người, hai thời điểm — không cái nào là đầu vào của
cái nào, và không cái nào chặn cái nào.

Trước D62 tôi lấy bảng vào hộp làm số điền sẵn cho phiếu. Nghe thì tiện, nhưng nó
buộc hai việc vào nhau: chưa chấm xong thì không lập được phiếu, sửa bảng thì phiếu
lệch, và người dùng phải hiểu cả hai mới dùng được một. Bỏ hẳn.

Đối chiếu "vào hộp bao nhiêu / nhập kho bao nhiêu" là việc của BÁO CÁO bên Quản lý,
không phải của ràng buộc lúc nhập liệu.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from sx.config.roles import guard_card
from sx.utils import get_settings, items_tp, nhom_tp


@frappe.whitelist()
def danh_muc_tp():
    """Thành phẩm chọn được khi lập phiếu — xem sx.utils.items_tp: Item thuộc Item
    Group đã chọn trong SX Settings, HOẶC Item gắn "Nhóm SX" = TP.

    Rỗng thì kèm `goi_y`: những Item CÓ BOM active mà chưa được tính là TP, kèm Item
    Group của nó để chọn thẳng nhóm đó trong SX Settings. Bế tắc kiểu "không tìm thấy
    sản phẩm nào" mà không nói vì sao là bế tắc không lối ra.
    """
    guard_card("nhapkhotp")
    ds = items_tp()
    rows = [
        {"item": i.name, "ten": i.item_name or i.name, "dvt": i.stock_uom or "",
         "uoms": _uom_cua(i.name, i.stock_uom)}
        for i in ds
    ]
    if rows:
        return {"rows": rows, "goi_y": []}

    co_bom = frappe.get_all(
        "BOM", filters={"is_active": 1, "docstatus": 1}, pluck="item", distinct=True)
    da_chon = set(nhom_tp())
    goi_y = [
        {"item": i.name, "ten": i.item_name or i.name,
         "nhom": i.item_group or "", "nhom_sx": i.custom_sx_nhom or ""}
        for i in frappe.get_all(
            "Item", filters={"name": ("in", co_bom or [""]), "disabled": 0},
            fields=["name", "item_name", "item_group", "custom_sx_nhom"],
            order_by="item_group, item_name",
        )
        if (i.custom_sx_nhom or "") != "TP" and (i.item_group or "") not in da_chon
    ]
    # Gom theo Item Group: chọn MỘT nhóm trong SX Settings là xong cả cụm, nên phải
    # cho người dùng thấy cụm chứ không phải danh sách Item rời rạc.
    cum = {}
    for g in goi_y:
        cum.setdefault(g["nhom"] or "(chưa có nhóm hàng)", []).append(g["ten"])
    return {
        "rows": [],
        "goi_y": [{"nhom": k, "so_item": len(v), "vi_du": v[:3]}
                  for k, v in sorted(cum.items(), key=lambda x: -len(x[1]))][:20],
    }


def _uom_cua(item, stock_uom):
    """Các đơn vị đếm được của một Item, kèm hệ số quy về đơn vị kho.

    Thủ kho đếm theo cách hàng XẾP ngoài kho: 2 thùng 3 hộp, không phải 27 hộp.
    Bắt quy đổi trong đầu là chỗ sinh lỗi, mà lỗi ở đây là lệch tồn kho thật.

    Sắp hệ số GIẢM DẦN (thùng trước, hộp sau) — đúng thứ tự người ta đọc số khi đếm.
    Đơn vị kho luôn có mặt với hệ số 1 dù Item chưa khai bảng quy đổi.
    """
    ra = {}
    for r in frappe.get_all(
        "UOM Conversion Detail", filters={"parent": item},
        fields=["uom", "conversion_factor"],
    ):
        he_so = flt(r.conversion_factor)
        if r.uom and he_so > 0:
            ra[r.uom] = he_so
    if stock_uom:
        ra[stock_uom] = 1.0
    return [{"uom": u, "he_so": h}
            for u, h in sorted(ra.items(), key=lambda x: -x[1])]


@frappe.whitelist()
def phieu_dang_mo():
    """Phiếu nháp đang chờ duyệt (nếu có) + danh mục TP để lập phiếu mới."""
    guard_card("nhapkhotp")
    settings = get_settings()
    if not settings.get("kho_tp"):
        frappe.throw(_("SX Settings chưa cấu hình Kho TP."))
    nhap = frappe.db.get_value("SX Phieu Nhap TP", {"docstatus": 0}, "name")
    dm = danh_muc_tp()
    return {
        "nhap": chi_tiet_phieu(nhap) if nhap else None,
        "kho_tp": settings.kho_tp,
        "danh_muc": dm["rows"],
        "goi_y": dm["goi_y"],
        "duoc_duyet": _duoc_duyet(),
    }


@frappe.whitelist()
def tao_phieu_nhap(rows=None, ngay=None, ghi_chu=None):
    """Lập PHIẾU NHÁP. `rows` = [{item, so_luong}] — người lập tự ghi, không lấy từ
    đâu khác. Bỏ trống thì tạo phiếu rỗng rồi thêm dòng sau.

    Mỗi lúc chỉ MỘT phiếu nháp: hai phiếu cùng lúc thì hai người đếm chồng nhau và
    duyệt cái sau sẽ nhập trùng.
    """
    guard_card("nhapkhotp")
    settings = get_settings()
    if not settings.get("kho_tp"):
        frappe.throw(_("SX Settings chưa cấu hình Kho TP."))
    nhap = frappe.db.get_value("SX Phieu Nhap TP", {"docstatus": 0}, "name")
    if nhap:
        frappe.throw(
            _("Đang có phiếu nháp {0} chưa duyệt. Duyệt hoặc xoá phiếu đó trước.")
            .format(nhap)
        )

    doc = frappe.new_doc("SX Phieu Nhap TP")
    doc.ngay = ngay or nowdate()
    doc.kho_dich = settings.kho_tp
    doc.nguoi_lap = frappe.session.user
    doc.ghi_chu = ghi_chu
    for r in (json.loads(rows) if isinstance(rows, str) else rows) or []:
        so = flt(r.get("so_luong"))
        ct = _ghi_json(r.get("chi_tiet"))
        if so > 0:
            doc.append("dong", {"item": r.get("item"), "so_lap": so, "so_dem": so,
                                "lap_uom": ct, "dem_uom": ct})
    doc.flags.ignore_permissions = True
    doc.insert()
    return chi_tiet_phieu(doc.name)


@frappe.whitelist()
def chi_tiet_phieu(name):
    guard_card("nhapkhotp")
    doc = frappe.get_doc("SX Phieu Nhap TP", name)
    return {
        "name": doc.name, "ngay": str(doc.ngay), "docstatus": doc.docstatus,
        "trang_thai": doc.trang_thai, "kho_dich": doc.kho_dich,
        "nguoi_lap": doc.nguoi_lap, "nguoi_duyet": doc.nguoi_duyet,
        "duyet_luc": str(doc.duyet_luc) if doc.duyet_luc else None,
        "ghi_chu": doc.ghi_chu,
        "tong_dem": flt(doc.tong_dem, 0), "tong_lech": flt(doc.tong_lech, 0),
        "duoc_duyet": _duoc_duyet(),
        "dong": [
            {"item": r.item, "ten": r.ten or r.item, "dvt": r.dvt or "",
             "so_lap": flt(r.so_lap, 0), "so_dem": flt(r.so_dem, 0),
             "lap_uom": _doc_json(r.lap_uom), "dem_uom": _doc_json(r.dem_uom),
             "lech": flt(r.lech, 0), "ghi_chu": r.ghi_chu}
            for r in doc.dong
        ],
    }


@frappe.whitelist()
def phieu_gan_day(limit=5):
    guard_card("nhapkhotp")
    return [
        {**g, "ngay": str(g["ngay"])}
        for g in frappe.get_all(
            "SX Phieu Nhap TP", filters={"docstatus": 1},
            fields=["name", "ngay", "tong_dem", "tong_lech", "nguoi_duyet"],
            order_by="creation desc", limit=cint(limit) or 5,
        )
    ]


@frappe.whitelist()
def sua_phieu(name, rows, ghi_chu=None):
    """Ghi lại toàn bộ dòng của phiếu nháp.

    `rows` = [{item, so_lap?, so_dem}]. Gửi TRỌN danh sách mỗi lần (thêm / sửa / bớt
    đều qua đây) — gửi lại nhiều lần vẫn ra một kết quả, không cộng dồn.
    `so_lap` bỏ trống thì giữ số cũ: thủ kho sửa số đếm KHÔNG được đụng vào số người
    lập đã ghi, vì chỗ lệch giữa hai số mới là thứ đáng xem.
    """
    guard_card("nhapkhotp")
    doc = frappe.get_doc("SX Phieu Nhap TP", name)
    if doc.docstatus != 0:
        frappe.throw(_("Phiếu {0} đã duyệt — không sửa được. Huỷ phiếu rồi lập lại.")
                     .format(name))
    cu = {r.item: (flt(r.so_lap), r.lap_uom) for r in doc.dong}
    doc.set("dong", [])
    for r in (json.loads(rows) if isinstance(rows, str) else rows) or []:
        item = r.get("item")
        if not item:
            continue
        so_dem = flt(r.get("so_dem"))
        lap_cu, lap_uom_cu = cu.get(item, (so_dem, None))
        so_lap = flt(r.get("so_lap")) if r.get("so_lap") is not None else lap_cu
        lap_uom = (_ghi_json(r.get("lap_uom")) if r.get("lap_uom") is not None
                   else lap_uom_cu)
        doc.append("dong", {
            "item": item, "so_lap": so_lap, "so_dem": so_dem,
            "lap_uom": lap_uom, "dem_uom": _ghi_json(r.get("dem_uom")),
            "ghi_chu": r.get("ghi_chu"),
        })
    if ghi_chu is not None:
        doc.ghi_chu = ghi_chu
    doc.flags.ignore_permissions = True
    doc.save()
    return chi_tiet_phieu(doc.name)


@frappe.whitelist()
def duyet_phieu(name):
    """THỦ KHO duyệt: submit phiếu -> sinh chứng từ kho -> hàng vào Kho TP."""
    guard_card("nhapkhotp")
    if not _duoc_duyet():
        frappe.throw(
            _("Chỉ THỦ KHO (role SX Thu Kho) mới được duyệt phiếu nhập kho. Người "
              "lập phiếu không tự duyệt phiếu của mình được — đó là lý do phiếu này "
              "tồn tại."), frappe.PermissionError
        )
    doc = frappe.get_doc("SX Phieu Nhap TP", name)
    if doc.docstatus != 0:
        frappe.throw(_("Phiếu {0} không còn ở trạng thái nháp.").format(name))
    doc.flags.ignore_permissions = True
    doc.submit()
    return chi_tiet_phieu(doc.name)


@frappe.whitelist()
def huy_phieu(name, ly_do=None):
    """Huỷ phiếu: nháp thì xoá, đã duyệt thì cancel (thu hồi chứng từ đã sinh)."""
    guard_card("nhapkhotp")
    if not _duoc_duyet():
        frappe.throw(_("Chỉ THỦ KHO mới huỷ được phiếu nhập kho."),
                     frappe.PermissionError)
    doc = frappe.get_doc("SX Phieu Nhap TP", name)
    if doc.docstatus == 0:
        doc.flags.ignore_permissions = True
        doc.delete()
        return {"da_xoa": name}
    if doc.docstatus == 2:
        frappe.throw(_("Phiếu {0} đã huỷ rồi.").format(name))
    if ly_do:
        doc.db_set("ghi_chu", ((doc.ghi_chu or "") + "\n[Lý do huỷ] " + ly_do).strip(),
                   update_modified=False)
    doc.flags.ignore_permissions = True
    doc.cancel()
    return {"da_huy": name}


def _doc_json(v):
    if not v:
        return None
    try:
        return json.loads(v)
    except (ValueError, TypeError):
        return None


def _ghi_json(v):
    """Chi tiết ĐVT về dạng chuỗi JSON gọn. Rỗng -> None (dòng chỉ có một đơn vị)."""
    if not v:
        return None
    ds = json.loads(v) if isinstance(v, str) else v
    if not isinstance(ds, list):
        return None
    sach = [{"uom": d.get("uom"), "sl": flt(d.get("sl")), "he_so": flt(d.get("he_so") or 1)}
            for d in ds if d.get("uom") and flt(d.get("sl")) > 0]
    return json.dumps(sach, ensure_ascii=False) if sach else None


def _duoc_duyet():
    roles = set(frappe.get_roles())
    return bool(roles & {"SX Thu Kho", "SX Quan Ly", "System Manager", "Administrator"})


def phieu_da_duyet_sau(luc):
    """Phiếu ĐÃ DUYỆT sinh sau một mốc thời gian — dùng để chặn huỷ chốt Ghi sổ.

    Bột ở Kho BTP là bột chung nhiều mẻ, lấy ra theo FIFO, nên mọi phiếu duyệt sau
    mốc chốt đều CÓ THỂ đã tiêu thụ bột của mẻ đó. Chặn theo thời gian là chặt hơn
    và không phải đoán."""
    if not luc:
        return []
    return [
        r.name for r in frappe.get_all(
            "SX Phieu Nhap TP",
            filters={"docstatus": 1, "creation": (">=", luc)},
            fields=["name"], order_by="creation",
        )
    ]
