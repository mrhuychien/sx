"""Nhập kho thành phẩm — thủ kho NHẬN hàng từ xưởng (D51).

═══ NGHIỆP VỤ: vì sao cần phiếu này khi chốt ngày đã nhập kho rồi ═══

Chốt ngày sinh lệnh SX tầng 3 và nhập TP thẳng vào Kho TP (D11). Đó là số theo
SỔ SÁCH: "hôm nay bảng vào hộp ghi 1.240 hộp nên kho có 1.240 hộp".

Thực tế xưởng khác: hộp đóng xong nằm ở khu vực đóng gói, thủ kho đếm rồi mới
nhận vào kho. Hai con số đó lệch nhau là bình thường (hộp lỗi bị loại, hộp còn
trên bàn chưa xếp pallet, chênh lệch đếm).

Phiếu này ghi lại LẦN NHẬN THẬT đó: chuyển kho Xưởng → Kho TP theo số thủ kho
đếm, có ghi rõ lệch bao nhiêu so với sổ.

D56: phiếu đi qua HAI TAY. Người ở xưởng LẬP phiếu nháp (điền sẵn số theo sổ), thủ
kho đi đếm thật, sửa số rồi DUYỆT — duyệt mới sinh phiếu kho. Ghi thẳng một bước
thì không ai kiểm ai, mà cả lý do tồn tại của phiếu này là để có người thứ hai đếm.

⚠️ ĐỂ PHIẾU NÀY CÓ NGHĨA, tầng 3 phải nhập TP vào KHO XƯỞNG chứ không phải Kho TP.
Đổi ở SX Settings → "Kho nhận TP từ tầng 3". Chưa đổi thì TP vào Kho TP ngay lúc
chốt, khu vực đóng gói không có gì để nhận, và card sẽ nói đúng như vậy thay vì
hiện danh sách rỗng không lý do.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from sx.config.roles import guard_card
from sx.utils import get_settings, kho_xuong


def _kho_nguon(settings=None):
    """Kho đang giữ TP chờ thủ kho nhận. Chưa cấu hình -> Kho Xưởng."""
    settings = settings or get_settings()
    return settings.get("kho_tp_cho_nhan") or kho_xuong(settings)


@frappe.whitelist()
def ton_cho_nhap():
    """TP đang chờ nhận ở kho nguồn, kèm số theo SỔ hôm nay để đối chiếu."""
    guard_card("nhapkhotp")
    settings = get_settings()
    nguon, dich = _kho_nguon(settings), settings.kho_tp
    if not dich:
        frappe.throw(_("SX Settings chưa cấu hình Kho TP."))

    rows = []
    for it in frappe.get_all(
        "Item", filters={"custom_sx_nhom": "TP", "disabled": 0},
        fields=["name", "item_name", "stock_uom"], order_by="item_name",
    ):
        ton = flt(frappe.db.get_value(
            "Bin", {"item_code": it.name, "warehouse": nguon}, "actual_qty"))
        if abs(ton) < 1e-9:
            continue
        rows.append({
            "item": it.name,
            "ten": it.item_name or it.name,
            "dvt": it.stock_uom or "",
            "cho_nhan": flt(ton, 0),
        })
    rows.sort(key=lambda r: -r["cho_nhan"])
    return {"kho_nguon": nguon, "kho_dich": dich, "rows": rows,
            "cung_kho": nguon == dich}


@frappe.whitelist()
def tao_phieu_nhap(rows=None, ngay=None, ghi_chu=None):
    """Lập PHIẾU NHÁP từ hàng đang chờ ở khu đóng gói.

    `rows` bỏ trống -> lấy trọn hàng đang chờ, điền sẵn số đếm = số theo sổ (phần
    lớn khớp; thủ kho chỉ sửa chỗ lệch). Mỗi lúc chỉ cho MỘT phiếu nháp: hai phiếu
    nháp cùng lấy một vũng hàng thì duyệt cái sau sẽ thiếu, mà lúc lập không ai thấy.
    """
    guard_card("nhapkhotp")
    settings = get_settings()
    nguon, dich = _kho_nguon(settings), settings.kho_tp
    if nguon == dich:
        frappe.throw(
            _("Kho nguồn và Kho TP đang là cùng một kho ({0}) nên không có gì để "
              "chuyển. Vào SX Settings đặt 'Kho nhận TP từ tầng 3' là kho khu đóng "
              "gói, rồi chốt ngày lại.").format(dich)
        )
    nhap = frappe.db.get_value("SX Phieu Nhap TP", {"docstatus": 0}, "name")
    if nhap:
        frappe.throw(
            _("Đang có phiếu nháp {0} chưa duyệt. Duyệt hoặc xoá phiếu đó trước — "
              "hai phiếu nháp cùng lấy một lô hàng sẽ vênh nhau.").format(nhap)
        )

    cho = {r["item"]: r for r in ton_cho_nhap()["rows"]}
    ds = json.loads(rows) if isinstance(rows, str) else rows
    if not ds:
        ds = [{"item": k, "so_luong": v["cho_nhan"]} for k, v in cho.items()]
    if not ds:
        frappe.throw(_("Khu đóng gói ({0}) không có hàng chờ nhận.").format(nguon))

    doc = frappe.new_doc("SX Phieu Nhap TP")
    doc.ngay = ngay or nowdate()
    doc.kho_nguon, doc.kho_dich = nguon, dich
    doc.nguoi_lap = frappe.session.user
    doc.ghi_chu = ghi_chu
    for r in ds:
        item = r.get("item")
        doc.append("dong", {
            "item": item,
            "so_theo_so": flt((cho.get(item) or {}).get("cho_nhan")),
            "so_dem": flt(r.get("so_luong")),
        })
    doc.flags.ignore_permissions = True
    doc.insert()
    return chi_tiet_phieu(doc.name)


@frappe.whitelist()
def chi_tiet_phieu(name):
    guard_card("nhapkhotp")
    doc = frappe.get_doc("SX Phieu Nhap TP", name)
    return {
        "name": doc.name, "ngay": str(doc.ngay), "docstatus": doc.docstatus,
        "trang_thai": doc.trang_thai, "kho_nguon": doc.kho_nguon,
        "kho_dich": doc.kho_dich, "nguoi_lap": doc.nguoi_lap,
        "nguoi_duyet": doc.nguoi_duyet,
        "duyet_luc": str(doc.duyet_luc) if doc.duyet_luc else None,
        "ghi_chu": doc.ghi_chu,
        "tong_dem": flt(doc.tong_dem, 0), "tong_lech": flt(doc.tong_lech, 0),
        "duoc_duyet": _duoc_duyet(),
        "dong": [
            {"item": r.item, "ten": r.ten or r.item, "dvt": r.dvt or "",
             "so_theo_so": flt(r.so_theo_so, 0), "so_dem": flt(r.so_dem, 0),
             "lech": flt(r.lech, 0), "ghi_chu": r.ghi_chu}
            for r in doc.dong
        ],
    }


@frappe.whitelist()
def phieu_dang_mo():
    """Phiếu nháp đang chờ duyệt (nếu có) + 5 phiếu đã duyệt gần nhất."""
    guard_card("nhapkhotp")
    nhap = frappe.db.get_value("SX Phieu Nhap TP", {"docstatus": 0}, "name")
    gan_day = frappe.get_all(
        "SX Phieu Nhap TP", filters={"docstatus": 1},
        fields=["name", "ngay", "tong_dem", "tong_lech", "nguoi_duyet"],
        order_by="creation desc", limit=5,
    )
    return {
        "nhap": chi_tiet_phieu(nhap) if nhap else None,
        "gan_day": [{**g, "ngay": str(g["ngay"])} for g in gan_day],
        "duoc_duyet": _duoc_duyet(),
    }


@frappe.whitelist()
def sua_phieu(name, rows, ghi_chu=None):
    """Thủ kho sửa số ĐẾM trên phiếu nháp. Chỉ sửa được khi còn nháp."""
    guard_card("nhapkhotp")
    doc = frappe.get_doc("SX Phieu Nhap TP", name)
    if doc.docstatus != 0:
        frappe.throw(_("Phiếu {0} đã duyệt — không sửa được. Huỷ phiếu rồi lập lại.")
                     .format(name))
    theo_item = {r.get("item"): flt(r.get("so_luong"))
                 for r in (json.loads(rows) if isinstance(rows, str) else rows)}
    for r in doc.dong:
        if r.item in theo_item:
            r.so_dem = theo_item[r.item]
    if ghi_chu is not None:
        doc.ghi_chu = ghi_chu
    doc.flags.ignore_permissions = True
    doc.save()
    return chi_tiet_phieu(doc.name)


@frappe.whitelist()
def duyet_phieu(name):
    """THỦ KHO duyệt: submit phiếu -> sinh phiếu kho chuyển khu đóng gói → Kho TP."""
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
    """Huỷ phiếu: nháp thì xoá, đã duyệt thì cancel (thu hồi phiếu kho đã sinh)."""
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


def phieu_sau_khi_chot(chot_luc):
    """Phiếu ĐÃ DUYỆT sinh sau mốc thời gian này — dùng để chặn huỷ chốt ngày.

    Không so theo `ngay_sx` vì hàng ở khu đóng gói là hàng chung nhiều ngày, lấy ra
    theo FIFO: phiếu nhận sau khi chốt ngày X thì CÓ THỂ đã lấy hàng của ngày X đi.
    Chặn theo thời gian là chặt hơn và không cần đoán.
    """
    if not chot_luc:
        return []
    return [
        r.name for r in frappe.get_all(
            "SX Phieu Nhap TP",
            filters={"docstatus": 1, "creation": (">=", chot_luc)},
            fields=["name"], order_by="creation",
        )
    ]
