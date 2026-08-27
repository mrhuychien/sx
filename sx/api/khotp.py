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
from frappe.utils import add_days, cint, flt, getdate, nowdate

from sx.config.roles import guard_card
from sx.utils import get_settings, items_tp, nhom_tp

# Khoảng ngày dùng CHUNG cho "còn được nhập": danh sách chờ nhận, nút tải, và
# lần kiểm lúc duyệt. Ba chỗ lấy ba khoảng khác nhau thì màn hình mời nhập một
# số mà lúc duyệt lại bảo vượt trần.
SO_NGAY_TRAN = 30


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


def tach_uom(tong, uoms):
    """Đổi một TỔNG theo đơn vị kho ra bậc lớn trước: 255 hộp -> 21 thùng 3 hộp.

    Trả None khi không chia khớp tuyệt đối. Thà không chia còn hơn chia ra một tổng
    khác tổng ban đầu — số này đi thẳng vào tồn kho. Bản sao đúng logic của tachUom()
    trong soluong.js: hai đầu phải ra cùng một cách chia, không thì thủ kho thấy số
    nhảy sau khi lưu.
    """
    ds = [u for u in (uoms or []) if u.get("uom") and flt(u.get("he_so")) > 0]
    tong = flt(tong)
    if len(ds) <= 1 or tong <= 0:
        return None
    bac = sorted(ds, key=lambda u: -flt(u["he_so"]))
    ra = []
    con = tong
    for i, u in enumerate(bac):
        h = flt(u["he_so"])
        # Bậc nhỏ nhất ôm phần dư; các bậc trên chỉ lấy phần chia chẵn.
        sl = int(round(con / h)) if i == len(bac) - 1 else int(con / h + 1e-9)
        if sl > 0:
            ra.append({"uom": u["uom"], "sl": sl, "he_so": h})
        con -= sl * h
    lai = sum(r["sl"] * r["he_so"] for r in ra)
    return ra if abs(lai - tong) < 1e-6 else None


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
        # Gửi luôn để màn hình mở ra là thấy hàng vừa đóng — thêm một lượt gọi nữa
        # chỉ để lấy danh sách này là bắt thủ kho chờ hai lần.
        "cho_nhan": cho_nhan()["rows"],
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
             "lap_uom": _doc_json(r.get("lap_uom")),
             "dem_uom": _doc_json(r.get("dem_uom")),
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
    co_uom = _co_chi_tiet_uom()
    cu = {r.item: (flt(r.so_lap), r.get("lap_uom")) for r in doc.dong}
    doc.set("dong", [])
    for r in (json.loads(rows) if isinstance(rows, str) else rows) or []:
        item = r.get("item")
        if not item:
            continue
        so_dem = flt(r.get("so_dem"))
        lap_cu, lap_uom_cu = cu.get(item, (so_dem, None))
        so_lap = flt(r.get("so_lap")) if r.get("so_lap") is not None else lap_cu
        dong = {"item": item, "so_lap": so_lap, "so_dem": so_dem,
                "ghi_chu": r.get("ghi_chu")}
        if co_uom:
            dong["lap_uom"] = (_ghi_json(r.get("lap_uom"))
                               if r.get("lap_uom") is not None else lap_uom_cu)
            dong["dem_uom"] = _ghi_json(r.get("dem_uom"))
        doc.append("dong", dong)
    if ghi_chu is not None:
        doc.ghi_chu = ghi_chu
    doc.flags.ignore_permissions = True
    try:
        doc.save()
    except Exception:
        # Lỗi ORM ở đây rơi ra client thành 500 trống trơn — người dùng chỉ thấy
        # "duyệt không được", không có gì để lần. Ghi log rồi ném lại câu đọc được.
        frappe.log_error(title=f"sua_phieu {name} hỏng", message=frappe.get_traceback())
        frappe.throw(
            _("Không lưu được phiếu {0}. Thường là do site chưa chạy "
              "`bench migrate` sau lần cập nhật gần nhất. Chi tiết trong Error Log.")
            .format(name)
        )
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


def _co_chi_tiet_uom():
    """Bảng con đã có cột chi tiết ĐVT chưa (D65).

    Deploy mà quên `bench migrate` thì field chưa có trong meta, và ghi vào nó là
    lỗi 500 trống trơn — người dùng chỉ thấy "duyệt không được". Thà chạy ở chế độ
    một đơn vị còn hơn chết cả nút bấm; và hàm này cũng là chỗ nói ra sự thật đó.
    """
    return bool(frappe.get_meta("SX Phieu Nhap TP Item").get_field("dem_uom"))


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


def _da_nhan_theo_ma(tu_ngay=None):
    """{item: đã nhận} — cộng số ĐẾM của mọi phiếu ĐÃ DUYỆT, để tính phần còn lại."""
    loc = {"docstatus": 1}
    if tu_ngay:
        loc["ngay"] = (">=", tu_ngay)
    ds = frappe.get_all("SX Phieu Nhap TP", filters=loc, pluck="name")
    ra = {}
    if not ds:
        return ra
    for r in frappe.get_all(
        "SX Phieu Nhap TP Item",
        filters={"parent": ("in", ds), "parenttype": "SX Phieu Nhap TP"},
        fields=["item", "so_dem"],
    ):
        ra[r.item] = ra.get(r.item, 0) + flt(r.so_dem)
    return ra


def _da_cham_theo_ma(tu_ngay, den_ngay):
    """{item: tổng đã chấm vào hộp} trong khoảng ngày — CẢ bảng nháp lẫn đã chốt.

    Lấy cả bảng nháp vì QC vẫn đang chấm khi hàng đã chuyển sang kho; đợi chốt mới
    cho tải là bắt thủ kho đứng chờ hết ca.
    """
    ngay = frappe.get_all(
        "SX Ngay San Xuat",
        filters={"ngay": ("between", (tu_ngay, den_ngay)), "docstatus": ("<", 2)},
        pluck="name",
    )
    if not ngay:
        return {}
    bang = frappe.get_all(
        "SX Bang Vao Hop",
        filters={"ngay_sx": ("in", ngay), "docstatus": ("<", 2)}, pluck="name")
    if not bang:
        return {}
    ra = {}
    for r in frappe.get_all(
        "SX Bang Vao Hop Item",
        filters={"parent": ("in", bang), "parenttype": "SX Bang Vao Hop"},
        fields=["san_pham", "so_hop"],
    ):
        if r.san_pham:
            ra[r.san_pham] = ra.get(r.san_pham, 0) + cint(r.so_hop)
    return ra


def tran_con_lai(tu_ngay, den_ngay, tru_phieu=None):
    """{item: còn được nhập} = đã chấm vào hộp − đã nhận.

    Đây là cái TRẦN của "chỉ được nhập trong số lượng đã chấm". `tru_phieu` là phiếu
    đang sửa: dòng của chính nó không tính vào phần đã nhận, nếu không sửa phiếu
    nháp lần thứ hai sẽ tự trừ mình.
    """
    cham = _da_cham_theo_ma(tu_ngay, den_ngay)
    # CÙNG khoảng ngày với số đã chấm. Lấy đã nhận từ đầu thời gian mà đã chấm chỉ
    # trong 7 ngày thì phiếu tháng trước trừ vào bảng chấm tuần này -> ra âm, mã hàng
    # biến mất khỏi danh sách "chờ nhận" dù xưởng vừa đóng xong.
    nhan = _da_nhan_theo_ma(tu_ngay)
    if tru_phieu and frappe.db.get_value("SX Phieu Nhap TP", tru_phieu, "docstatus") == 1:
        for r in frappe.get_all(
            "SX Phieu Nhap TP Item",
            filters={"parent": tru_phieu, "parenttype": "SX Phieu Nhap TP"},
            fields=["item", "so_dem"],
        ):
            nhan[r.item] = nhan.get(r.item, 0) - flt(r.so_dem)
    return {item: flt(so) - flt(nhan.get(item, 0)) for item, so in cham.items()}


@frappe.whitelist()
def cho_nhan(so_ngay=None, den=None):
    """Mã hàng ĐÃ CHẤM VÀO HỘP mà CHƯA NHẬP KHO — danh sách để thủ kho bấm vào ghi số.

    Đây là câu trả lời cho "ghi hộp rồi mà nhập kho không thấy đâu": bảng vào hộp và
    phiếu nhập kho vẫn là hai chứng từ độc lập, nhưng màn nhập kho phải BÀY RA thứ
    xưởng vừa làm xong, chứ không bắt thủ kho tự nhớ hôm nay đóng những mã nào.

    Lấy cả bảng NHÁP (xem _da_cham_theo_ma) vì QC còn đang chấm khi hàng đã ra kho.
    """
    guard_card("nhapkhotp")
    den_ngay = getdate(den or nowdate())
    tu_ngay = add_days(den_ngay, -abs(cint(so_ngay) or SO_NGAY_TRAN) + 1)
    con = tran_con_lai(tu_ngay, den_ngay)
    ma = [k for k, v in con.items() if flt(v) > 1e-6]
    if not ma:
        return {"rows": [], "tu_ngay": str(tu_ngay), "den_ngay": str(den_ngay)}

    ten = {
        i.name: (i.item_name or i.name, i.stock_uom or "")
        for i in frappe.get_all(
            "Item", filters={"name": ("in", ma)}, fields=["name", "item_name", "stock_uom"])
    }
    rows = []
    for item in ma:
        t, dvt = ten.get(item, (item, ""))
        rows.append({"item": item, "ten": t, "dvt": dvt,
                     "uoms": _uom_cua(item, dvt), "con": flt(con[item], 0)})
    rows.sort(key=lambda x: -x["con"])
    return {"rows": rows, "tu_ngay": str(tu_ngay), "den_ngay": str(den_ngay)}


@frappe.whitelist()
def tai_tu_vao_hop(name, so_ngay=None):
    """Tải tổng theo mã hàng từ bảng vào hộp vào phiếu nháp (D70).

    Điền phần CÒN LẠI = đã chấm − đã nhận, trong `so_ngay` ngày gần đây. Thủ kho vẫn
    sửa được số, chỉ không vượt quá phần còn lại đó — "chỉ được nhập trong số lượng
    đã nhận". Chấm thêm thì lập phiếu tiếp cho phần mới.
    """
    guard_card("nhapkhotp")
    doc = frappe.get_doc("SX Phieu Nhap TP", name)
    if doc.docstatus != 0:
        frappe.throw(_("Phiếu {0} đã duyệt — không tải lại được.").format(name))
    den = getdate(doc.ngay)
    tu = add_days(den, -abs(cint(so_ngay) or SO_NGAY_TRAN) + 1)
    con = {k: v for k, v in tran_con_lai(tu, den, name).items() if v > 1e-6}
    if not con:
        frappe.throw(
            _("Không còn mã hàng nào chưa nhập kho trong {0} ngày gần đây "
              "(từ {1}). Hoặc chưa chấm vào hộp, hoặc đã nhận hết.").format(
                cint(so_ngay) or SO_NGAY_TRAN, frappe.utils.formatdate(tu))
        )
    co_uom = _co_chi_tiet_uom()
    cu = {r.item: flt(r.so_dem) for r in doc.dong}
    dvt = {i.name: i.stock_uom for i in frappe.get_all(
        "Item", filters={"name": ("in", list(con))}, fields=["name", "stock_uom"])}
    doc.set("dong", [])
    for item, so in sorted(con.items(), key=lambda x: -x[1]):
        so_lap = flt(so, 0)
        # Giữ số thủ kho đã đếm nếu có, nhưng không vượt trần mới.
        so_dem = min(cu.get(item, so_lap), so_lap)
        dong = {"item": item, "so_lap": so_lap, "so_dem": so_dem}
        if co_uom:
            # Chia sẵn ra thùng + hộp: thủ kho đang đứng đếm thùng, đưa 255 hộp là
            # bắt họ chia nhẩm rồi gõ lại.
            uoms = _uom_cua(item, dvt.get(item))
            dong["lap_uom"] = _ghi_json(tach_uom(so_lap, uoms))
            dong["dem_uom"] = _ghi_json(tach_uom(so_dem, uoms))
        doc.append("dong", dong)
    doc.flags.ignore_permissions = True
    doc.save()
    return chi_tiet_phieu(doc.name)
