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
from sx.utils import get_settings


@frappe.whitelist()
def danh_muc_tp():
    """Danh mục thành phẩm để chọn khi lập phiếu, kèm mã vạch để quét."""
    guard_card("nhapkhotp")
    ds = frappe.get_all(
        "Item", filters={"custom_sx_nhom": "TP", "disabled": 0},
        fields=["name", "item_name", "stock_uom"], order_by="item_name",
    )
    return [{"item": i.name, "ten": i.item_name or i.name, "dvt": i.stock_uom or ""}
            for i in ds]


@frappe.whitelist()
def phieu_dang_mo():
    """Phiếu nháp đang chờ duyệt (nếu có) + danh mục TP để lập phiếu mới."""
    guard_card("nhapkhotp")
    settings = get_settings()
    if not settings.get("kho_tp"):
        frappe.throw(_("SX Settings chưa cấu hình Kho TP."))
    nhap = frappe.db.get_value("SX Phieu Nhap TP", {"docstatus": 0}, "name")
    return {
        "nhap": chi_tiet_phieu(nhap) if nhap else None,
        "kho_tp": settings.kho_tp,
        "danh_muc": danh_muc_tp(),
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
        if so > 0:
            doc.append("dong", {"item": r.get("item"), "so_lap": so, "so_dem": so})
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
    cu = {r.item: flt(r.so_lap) for r in doc.dong}
    doc.set("dong", [])
    for r in (json.loads(rows) if isinstance(rows, str) else rows) or []:
        item = r.get("item")
        if not item:
            continue
        so_dem = flt(r.get("so_dem"))
        so_lap = flt(r.get("so_lap")) if r.get("so_lap") is not None else cu.get(item, so_dem)
        doc.append("dong", {"item": item, "so_lap": so_lap, "so_dem": so_dem,
                            "ghi_chu": r.get("ghi_chu")})
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
