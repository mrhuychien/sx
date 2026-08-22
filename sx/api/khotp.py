"""Phiếu nhập kho thành phẩm — PHIẾU NÀY LÀ CHỨNG TỪ SINH TỒN KHO TP (D59).

═══ LUỒNG ═══
    QC chấm vào hộp  →  chốt Vào hộp  →  QC lập PHIẾU NHÁP nhập kho
    →  thủ kho đếm thật, sửa số  →  DUYỆT  →  hàng vào Kho TP, tồn cập nhật

Chấm vào hộp là việc ĐỘC LẬP: nó ghi công cho từng người và tính lương khoán, nó
KHÔNG đụng tới kho. Thành phẩm chỉ trở thành tồn kho khi thủ kho duyệt. Trước lúc
đó, trong sổ chưa có hộp nào — đúng như ngoài đời, hộp còn nằm trên bàn chưa ai nhận.

═══ HAI CON SỐ, HAI CHỨNG TỪ (D59) ═══
Một phiếu duyệt sinh tối đa hai chứng từ cho mỗi SKU:

  1. SỐ THEO BẢNG (số QC chấm)  →  Work Order + SE Manufacture
     Trừ bột bánh/bột đậu + bao bì theo BOM, nhập TP vào Kho TP.
     Dùng số BẢNG chứ không phải số đếm vì nguyên liệu đã tiêu thụ THẬT cho toàn bộ
     số hộp đã đóng — kể cả hộp sau đó bị loại.

  2. PHẦN LỆCH (bảng − đếm, nếu > 0)  →  SE Material Issue, lý do "hộp lỗi"
     Xuất đúng lô vừa nhập ra khỏi kho.

Tồn Kho TP sau cùng = số thủ kho ĐẾM. Nguyên liệu tiêu thụ = cho số đã ĐÓNG.
Cả hai đều đúng, và số hộp hỏng hiện ra thành một chứng từ có lý do thay vì biến mất.

Nhập THIẾU thì cho (hộp lỗi là chuyện thật). Nhập THỪA hơn bảng thì CHẶN: thừa
nghĩa là bảng vào hộp ghi sót, phải sửa bảng chứ không phải nhập bừa vào kho.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from sx.config.roles import guard_card
from sx.utils import get_settings


def _bang_cua_ngay(ngay_sx):
    """Bảng vào hộp của ngày — LẤY CẢ BẢN NHÁP (D60).

    Không bắt phải chốt Vào hộp trước mới lập được phiếu nhập kho: chấm vào hộp và
    nhận hàng là hai việc của hai người, hàng có thể được chuyển vào kho ngay giữa
    ca. Chỗ nguy hiểm — số trên bảng còn đổi sau khi thủ kho cầm phiếu đi đếm — được
    xử lý ở lúc DUYỆT (đối chiếu lại, lệch thì chặn), chứ không phải bằng cách cấm.
    """
    ten = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": ngay_sx, "docstatus": ("<", 2)},
        "name", order_by="docstatus desc")
    return frappe.get_doc("SX Bang Vao Hop", ten) if ten else None


def _tong_theo_sku(bang):
    """{item_tp: số hộp} từ bảng vào hộp.

    Dòng KHÔNG gắn SKU bị bỏ qua: đó là loại công việc chưa gắn Item TP (D23), chỉ
    tính lương khoán chứ không sinh thành phẩm."""
    ra = {}
    for r in bang.dong:
        if r.san_pham and cint(r.so_hop) > 0:
            ra[r.san_pham] = ra.get(r.san_pham, 0) + cint(r.so_hop)
    return ra


def _da_nhan(ngay_sx):
    """{item: số hộp ĐÃ vào kho} của ngày — cộng theo SỐ ĐẾM của phiếu đã duyệt,
    vì chính số đếm là số Work Order đã chạy và đã nhập kho.

    Có nó thì nhận NHIỀU LẦN trong ngày mới đúng: đóng được bao nhiêu chuyển bấy
    nhiêu, phiếu sau chỉ lấy phần CÒN LẠI, không nhập trùng phần đã nhận."""
    ra = {}
    for name in frappe.get_all(
        "SX Phieu Nhap TP", filters={"ngay_sx": ngay_sx, "docstatus": 1}, pluck="name"
    ):
        for r in frappe.get_all(
            "SX Phieu Nhap TP Item", filters={"parent": name},
            fields=["item", "so_dem"],
        ):
            ra[r.item] = ra.get(r.item, 0) + flt(r.so_dem)
    return ra


def _con_lai(ngay_sx):
    """{item: số hộp chưa nhập kho} = bảng vào hộp − đã nhận."""
    bang = _bang_cua_ngay(ngay_sx)
    if not bang:
        return {}, None
    tong = _tong_theo_sku(bang)
    da = _da_nhan(ngay_sx)
    con = {}
    for item, so in tong.items():
        du = flt(so) - flt(da.get(item, 0))
        if du > 1e-6:
            con[item] = du
    return con, bang


@frappe.whitelist()
def cho_lap_phieu(ngay_sx=None):
    """Ngày còn hàng chưa nhập kho -> số liệu để lập phiếu nháp."""
    guard_card("nhapkhotp")
    settings = get_settings()
    if not settings.get("kho_tp"):
        frappe.throw(_("SX Settings chưa cấu hình Kho TP."))

    nhap = frappe.db.get_value(
        "SX Phieu Nhap TP", {"docstatus": 0}, ["name", "ngay_sx"], as_dict=True)
    if nhap:
        return {"nhap": chi_tiet_phieu(nhap.name), "kho_tp": settings.kho_tp,
                "cho_lap": [], "duoc_duyet": _duoc_duyet()}

    cho = []
    for d in frappe.get_all(
        "SX Ngay San Xuat",
        filters={"docstatus": ("<", 2)},
        fields=["name", "ngay", "chot_vaohop"], order_by="ngay desc", limit=30,
    ):
        con, _bang = _con_lai(d.name)
        if not con:
            continue
        cho.append({
            "ngay_sx": d.name, "ngay": str(d.ngay),
            "tong": sum(con.values()), "so_loai": len(con),
            "da_chot": cint(d.chot_vaohop),
        })
    return {"nhap": None, "kho_tp": settings.kho_tp, "cho_lap": cho,
            "duoc_duyet": _duoc_duyet()}


@frappe.whitelist()
def tao_phieu_nhap(ngay_sx, ghi_chu=None):
    """QC lập PHIẾU NHÁP cho phần hàng của một ngày CHƯA nhập kho.

    Không bắt ngày phải chốt Vào hộp trước (D60) — chấm vào hộp và nhận hàng là hai
    việc của hai người. Bù lại, lúc DUYỆT sẽ đối chiếu lại với bảng: bảng đổi sau
    khi lập phiếu thì chặn, để thủ kho không bao giờ duyệt theo số cũ.

    Mỗi ngày chỉ MỘT phiếu nháp; nhận nhiều lần trong ngày thì duyệt phiếu này rồi
    lập phiếu tiếp cho phần còn lại.
    """
    guard_card("nhapkhotp")
    settings = get_settings()
    if not settings.get("kho_tp"):
        frappe.throw(_("SX Settings chưa cấu hình Kho TP."))

    ngay = frappe.db.get_value(
        "SX Ngay San Xuat", ngay_sx, ["name", "ngay", "docstatus"], as_dict=True)
    if not ngay:
        frappe.throw(_("Không tìm thấy phiếu ngày {0}.").format(ngay_sx))
    if ngay.docstatus == 2:
        frappe.throw(_("Phiếu ngày {0} đã huỷ.").format(ngay_sx))
    nhap = frappe.db.get_value(
        "SX Phieu Nhap TP", {"ngay_sx": ngay_sx, "docstatus": 0}, "name")
    if nhap:
        frappe.throw(_("Ngày này đang có phiếu nháp {0} chưa duyệt.").format(nhap))

    con, bang = _con_lai(ngay_sx)
    if not bang:
        frappe.throw(
            _("Ngày {0} chưa có bảng vào hộp.").format(
                frappe.utils.formatdate(ngay.ngay))
        )
    if not con:
        frappe.throw(
            _("Ngày {0} không còn hàng chưa nhập kho — bảng vào hộp trống, hoặc "
              "phiếu trước đã nhận hết.").format(frappe.utils.formatdate(ngay.ngay))
        )

    doc = frappe.new_doc("SX Phieu Nhap TP")
    doc.ngay = ngay.ngay
    doc.ngay_sx = ngay_sx
    doc.kho_dich = settings.kho_tp
    doc.nguoi_lap = frappe.session.user
    doc.ghi_chu = ghi_chu
    for item, so in sorted(con.items(), key=lambda x: -x[1]):
        # Điền sẵn số đếm = số theo bảng: phần lớn khớp, thủ kho chỉ sửa chỗ lệch.
        doc.append("dong", {"item": item, "so_theo_so": so, "so_dem": so})
    doc.flags.ignore_permissions = True
    doc.insert()
    return chi_tiet_phieu(doc.name)


@frappe.whitelist()
def lam_moi_phieu(name):
    """Nạp lại cột "Theo bảng" theo bảng vào hộp HIỆN TẠI (giữ số đếm đã gõ).

    QC vẫn đang chấm trong lúc thủ kho đi đếm, nên con số tham chiếu cũ hay lệch.
    Không bắt buộc bấm — số đếm mới là số vào kho — nhưng bấm thì đối chiếu dễ hơn.
    """
    guard_card("nhapkhotp")
    doc = frappe.get_doc("SX Phieu Nhap TP", name)
    if doc.docstatus != 0:
        frappe.throw(_("Phiếu {0} đã duyệt — không làm mới được.").format(name))
    con, _bang = _con_lai(doc.ngay_sx)
    cu = {r.item: flt(r.so_dem) for r in doc.dong}
    doc.set("dong", [])
    for item, so in sorted(con.items(), key=lambda x: -x[1]):
        # Giữ nguyên số đếm đã gõ, KHÔNG cắt theo bảng: bảng là tham chiếu, còn số
        # đếm là hàng thủ kho đã sờ tay vào.
        doc.append("dong", {"item": item, "so_theo_so": so,
                            "so_dem": cu.get(item, so)})
    doc.flags.ignore_permissions = True
    doc.save()
    return chi_tiet_phieu(doc.name)


@frappe.whitelist()
def chi_tiet_phieu(name):
    guard_card("nhapkhotp")
    doc = frappe.get_doc("SX Phieu Nhap TP", name)
    return {
        "name": doc.name, "ngay": str(doc.ngay), "ngay_sx": doc.ngay_sx,
        "docstatus": doc.docstatus, "trang_thai": doc.trang_thai,
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


def phieu_cua_ngay(ngay_sx):
    """Phiếu nhập kho (nháp hoặc đã duyệt) của một ngày — dùng để chặn huỷ chốt."""
    return [
        r.name for r in frappe.get_all(
            "SX Phieu Nhap TP",
            filters={"ngay_sx": ngay_sx, "docstatus": ("<", 2)},
            fields=["name"], order_by="creation",
        )
    ]


