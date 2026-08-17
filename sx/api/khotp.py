"""Nhập kho thành phẩm — thủ kho NHẬN hàng từ xưởng (D51).

═══ NGHIỆP VỤ: vì sao cần phiếu này khi chốt ngày đã nhập kho rồi ═══

Chốt ngày sinh lệnh SX tầng 3 và nhập TP thẳng vào Kho TP (D11). Đó là số theo
SỔ SÁCH: "hôm nay bảng vào hộp ghi 1.240 hộp nên kho có 1.240 hộp".

Thực tế xưởng khác: hộp đóng xong nằm ở khu vực đóng gói, thủ kho đếm rồi mới
nhận vào kho. Hai con số đó lệch nhau là bình thường (hộp lỗi bị loại, hộp còn
trên bàn chưa xếp pallet, chênh lệch đếm).

Phiếu này ghi lại LẦN NHẬN THẬT đó: chuyển kho Xưởng → Kho TP theo số thủ kho
đếm, có ghi rõ lệch bao nhiêu so với sổ.

⚠️ ĐỂ PHIẾU NÀY CÓ NGHĨA, tầng 3 phải nhập TP vào KHO XƯỞNG chứ không phải Kho TP.
Đổi ở SX Settings → "Kho nhận TP từ tầng 3". Chưa đổi thì TP vào Kho TP ngay lúc
chốt, khu vực đóng gói không có gì để nhận, và card sẽ nói đúng như vậy thay vì
hiện danh sách rỗng không lý do.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from sx.api.mfg import tao_se_chuyen_kho
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
def nhap_kho_tp(rows, ngay=None, ghi_chu=None):
    """Ghi phiếu nhận: chuyển kho Xưởng → Kho TP theo số thủ kho ĐẾM.

    rows: JSON [{item, so_luong}]. Số 0 hoặc âm bị bỏ qua (không nhận gì thì
    không sinh dòng, chứ không phải ghi 0 vào phiếu).
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

    ds = json.loads(rows) if isinstance(rows, str) else (rows or [])
    can_nhan = [(r.get("item"), flt(r.get("so_luong"))) for r in ds
                if flt(r.get("so_luong")) > 0]
    if not can_nhan:
        frappe.throw(_("Chưa nhập số lượng nhận cho sản phẩm nào."))

    ket_qua, se_names = [], []
    for item, sl in can_nhan:
        ton = flt(frappe.db.get_value(
            "Bin", {"item_code": item, "warehouse": nguon}, "actual_qty"))
        if sl > ton + 1e-6:
            frappe.throw(
                _("{0}: khu đóng gói chỉ còn {1}, không nhận {2} được. "
                  "Đếm lại hoặc kiểm tra bảng vào hộp.").format(item, flt(ton, 0), flt(sl, 0))
            )
        se = tao_se_chuyen_kho(
            settings.cong_ty, item, sl, kho_di=nguon, kho_den=dich,
            ngay=ngay or nowdate(),
            ghi_chu=ghi_chu or _("Thủ kho nhận TP từ xưởng"),
            cong_doan="nhaptp",
        )
        se_names.append(se.name)
        ket_qua.append({"item": item, "so_luong": flt(sl, 0), "con_lai": flt(ton - sl, 0)})

    return {"se": se_names, "dong": ket_qua,
            "tong": flt(sum(x["so_luong"] for x in ket_qua), 0)}
