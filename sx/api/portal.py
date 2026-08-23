"""Whitelisted API portal /sx (v3). Guard theo card-capability (config/roles.py).

Dữ liệu doc chuẩn chỉ trả field whitelist (Employee: name, employee_name).
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from sx.config.roles import (
    allowed_views,
    guard_card,
    is_super,
    landing_view,
    user_roles,
    view_cards,
)
from sx.utils import (
    dat_ten_hien_thi,
    get_bom_active,
    get_dau_items,
    get_don_gia_activity,
    get_settings,
    items_tp,
)

# Nguồn phân loại "công khoán" trên Employee -> fieldname tương ứng
_NGUON_CONG_KHOAN = {
    "Employment Type": "employment_type",
    "Designation": "designation",
    "Department": "department",
    "Branch": "branch",
}


def _do_nhom_cong_khoan():
    """Tự dò nhóm công khoán khi SX Settings chưa điền: tìm Employment Type /
    Designation có tên chứa 'khoán'. Trả (fieldname, giá trị) hoặc None."""
    for dt, field in (("Employment Type", "employment_type"), ("Designation", "designation")):
        if not frappe.db.exists("DocType", dt):
            continue
        for ten in frappe.get_all(dt, pluck="name"):
            if "khoán" in (ten or "").lower():
                return field, ten
    return None


def _nhan_vien_vao_hop():
    """Chỉ công nhân thuộc nhóm CÔNG KHOÁN mới hiện ở bảng vào hộp.

    Ưu tiên cấu hình SX Settings (nguồn + giá trị); chưa điền thì tự dò; dò không ra
    thì trả mọi nhân viên Active kèm cảnh báo (để không chặn vận hành).
    Trả (danh sách đã gán ten_hien_thi, cảnh báo|None).
    """
    settings = get_settings()
    field = _NGUON_CONG_KHOAN.get((settings.get("nguon_cong_khoan") or "").strip())
    gia_tri = (settings.get("gia_tri_cong_khoan") or "").strip()
    filters, canh_bao = {"status": "Active"}, None

    if field and gia_tri:
        filters[field] = gia_tri
    else:
        do = _do_nhom_cong_khoan()
        if do:
            filters[do[0]] = do[1]
        else:
            canh_bao = _(
                "Chưa xác định được nhóm công khoán — đang hiện MỌI nhân viên. "
                "Vào SX Settings điền 'Nguồn nhóm công khoán' + 'Giá trị nhóm công khoán'."
            )

    fields = ["name", "employee_name"]
    # employee_number là mã người ta vốn đã in trên thẻ/bảng công. Ưu tiên nó làm mã
    # quét để khỏi phát sinh mã thứ hai cho cùng một người.
    if frappe.get_meta("Employee").has_field("employee_number"):
        fields.append("employee_number")
    ds = frappe.get_all(
        "Employee", filters=filters, fields=fields, order_by="employee_name",
    )
    return dat_ten_hien_thi(ds), canh_bao


def _any_sx_guard():
    """Cho phép mọi role SX (boot / phiếu ngày dùng chung)."""
    roles = user_roles()
    if is_super(roles) or roles & {"SX Ghi So", "SX Vao Hop", "SX Thu Kho"}:
        return
    frappe.throw(_("Bạn không có quyền vào portal sản xuất."), frappe.PermissionError)


# ─────────────────────────────────────────────────────────────── boot ──


@frappe.whitelist()
def get_boot(ngay=None):
    """Context khởi động: views/cards theo role, phiếu ngày, danh mục 2 nhánh,
    lô chờ nhập bột, tồn BTP, nhân viên.

    `ngay` = ngày đang XEM (D25). Bỏ trống -> hôm nay. Cho phép mở lại ngày cũ để
    đối chiếu / sửa; ngày đã chốt trả về read-only (docstatus 1) cho tới khi huỷ chốt.
    """
    _any_sx_guard()
    roles = user_roles()
    super_ = is_super(roles)
    hom_nay = nowdate()
    ngay_xem = str(getdate(ngay)) if ngay else hom_nay

    ngay_sx = _ngay_summary(
        frappe.db.get_value(
            "SX Ngay San Xuat", {"ngay": ngay_xem, "docstatus": ("<", 2)}, "name"
        )
    )

    settings = get_settings()

    def _items_nhom(nhom, kem_co_me=True):
        out = frappe.get_all(
            "Item", filters={"custom_sx_nhom": nhom, "disabled": 0},
            fields=["name", "item_name"], order_by="item_name",
        )
        if kem_co_me:
            for it in out:
                bom = get_bom_active(it["name"])
                it["co_me_chuan_kg"] = (
                    flt(frappe.db.get_value("BOM", bom, "custom_co_me_chuan_kg")) if bom else 0
                )
        return out

    can_ghiso = super_ or "SX Ghi So" in roles
    can_vaohop = super_ or "SX Vao Hop" in roles

    boot = {
        "user": frappe.session.user,
        "is_quan_ly": super_,
        "views": allowed_views(roles),
        "viewCards": view_cards(roles),
        "landing": landing_view(roles),
        "hom_nay": hom_nay,
        "ngay_xem": ngay_xem,
        "la_hom_nay": ngay_xem == hom_nay,
        "ngay_sx": ngay_sx,
        "bang_vao_hop": _bang_summary(ngay_sx["name"]) if ngay_sx else None,
    }

    if can_ghiso:
        boot["loai_dau"] = get_dau_items()
        boot["items_nau"] = _items_nhom("BTP-Phu")       # 3 đường hoán (màu gộp thẳng vào BOM)
        boot["items_bot_banh"] = _items_nhom("BTP-Banh")  # 8 bột bánh
        boot["items_bot_dau"] = _items_nhom("BTP-Bot-SP")  # 8 bột đậu

    if can_vaohop:
        boot["items_tp"] = items_tp(["name", "item_name", "item_group"])
        boot["tien_an_ca"] = flt(settings.get("tien_an_ca"))
        boot["tien_an_dem"] = flt(settings.get("tien_an_dem"))
        boot["activity_types"] = _activity_vao_hop()
        boot["activity_gan_day"] = _activity_gan_day()
        boot["nhan_vien"], canh_bao_nv = _nhan_vien_vao_hop()
        if canh_bao_nv:
            boot["canh_bao_nhan_vien"] = canh_bao_nv
        boot["ma_quet"] = _ma_quet(boot["nhan_vien"], boot["activity_types"])

    return boot


def _ngay_summary(ten):
    if not ten:
        return None
    doc = frappe.get_doc("SX Ngay San Xuat", ten)
    return {
        "name": doc.name,
        "ngay": str(doc.ngay),
        "docstatus": doc.docstatus,
        "trang_thai": doc.trang_thai,
        "chot_ghiso": cint(doc.chot_ghiso),
        "chot_vaohop": cint(doc.chot_vaohop),
        "tong_hop_tp": doc.tong_hop_tp,
        "tong_luong_sp": doc.tong_luong_sp,
        "bao_me": [
            {"item_btp": r.item_btp, "so_me": r.so_me, "co_me_kg": r.co_me_kg,
             "tong_kg": r.tong_kg, "batch": r.batch}
            for r in doc.bao_me
        ],
        "bao_can": [
            {"item_bot_banh": r.item_bot_banh, "so_me": r.so_me, "ghi_chu": r.ghi_chu}
            for r in doc.bao_can
        ],
        "su_co": [
            {"thoi_diem": str(r.thoi_diem), "loai": r.loai, "mo_ta": r.mo_ta,
             "phut_dung": r.phut_dung}
            for r in doc.su_co
        ],
    }


def _bang_summary(ngay_sx):
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
            {"nhan_vien": r.nhan_vien, "ten_nhan_vien": r.ten_nhan_vien,
             "san_pham": r.san_pham, "so_hop": r.so_hop,
             "activity_type": r.activity_type,
             "don_gia": r.don_gia, "thanh_tien": r.thanh_tien}
            for r in doc.dong
        ],
        "an_ca": [
            {"nhan_vien": r.nhan_vien, "an_ca": cint(r.an_ca), "an_dem": cint(r.an_dem)}
            for r in (doc.get("an_ca") or [])
        ],
    }


def _activity_gan_day():
    """Loại công việc dùng gần đây (14 ngày) — chip "dùng gần đây" đầu picker."""
    bang = frappe.get_all(
        "SX Bang Vao Hop",
        filters={"creation": (">=", add_days(nowdate(), -14))},
        pluck="name",
    )
    if not bang:
        return []
    rows = frappe.get_all(
        "SX Bang Vao Hop Item",
        filters={"parent": ("in", bang), "parenttype": "SX Bang Vao Hop"},
        fields=["activity_type"],
        order_by="creation desc",
    )
    seen = []
    for r in rows:
        if r.activity_type and r.activity_type not in seen:
            seen.append(r.activity_type)
    return seen[:12]


def _activity_vao_hop():
    """Danh sách LOẠI CÔNG VIỆC KHOÁN + đơn giá + SKU thuộc loại đó.

    Đây là thứ QC chọn khi ghi bảng vào hộp (D23). SKU chỉ là chi tiết bên trong:
    - loại có 0 SKU  -> ghi thẳng sản lượng khoán (chưa tạo Item TP thì vẫn chạy được)
    - loại có 1 SKU  -> tự gán, QC không phải chọn
    - loại có ≥2 SKU -> hỏi thêm 1 bước để biết SKU nào (cần cho lệnh SX tầng 3)
    """
    sku_theo_act = {}
    for it in items_tp(["name", "item_name", "custom_activity_type"]):
        if it.custom_activity_type:
            sku_theo_act.setdefault(it.custom_activity_type, []).append(
                {"name": it.name, "item_name": it.item_name or it.name}
            )

    # Activity Type có field `disabled` hay không tuỳ phiên bản/custom -> hỏi meta
    loc = {"disabled": 0} if frappe.get_meta("Activity Type").has_field("disabled") else {}
    ds = []
    for act in frappe.get_all("Activity Type", filters=loc, pluck="name", order_by="name"):
        gia = get_don_gia_activity(act, bat_buoc=False)
        if gia is None:
            continue  # không đọc được đơn giá -> không dùng để ghi khoán
        ds.append({"name": act, "don_gia": gia, "sku": sku_theo_act.get(act, [])})
    return ds


def _ma_quet(nhan_vien, activities):
    """Bảng tra MÃ QUÉT → đối tượng, gửi kèm boot để tra NGAY TRÊN MÁY.

    Tra ở client chứ không gọi server mỗi lần quét vì hai lý do: quét phải phản hồi
    tức thì (đợi mạng giữa xưởng là mất luôn cái lợi của việc quét), và app phải
    dùng được khi mất mạng (D37) — bản boot đã nằm sẵn trong localStorage.

    Mã người: chấp nhận CẢ employee_number lẫn Employee ID. Nơi này chỉ có 45 người
    nên bảng rất nhỏ; đổi lại QC quét được bất kỳ thẻ nào đang có sẵn.

    Mã sản phẩm: lấy theo MỌI Item thành phẩm (items_tp), không phải chỉ SKU đã gắn
    loại công việc. Từ D64 thành phẩm xác định bằng Item Group, nên phần lớn Item
    không có `custom_activity_type` — lấy theo activity thì nút quét ở màn Nhập kho
    tra bảng rỗng và không quét được gì, mà lại im lặng.
    """
    nv = {}
    for e in nhan_vien:
        for ma in (e.get("employee_number"), e.get("name")):
            if ma:
                nv[str(ma).strip()] = e["name"]

    ma_sku = {s["name"] for a in activities for s in (a.get("sku") or [])}
    ma_sku |= {i.name for i in items_tp(["name"])}
    sp = {}
    if ma_sku:
        for b in frappe.get_all(
            "Item Barcode", filters={"parent": ("in", list(ma_sku))},
            fields=["barcode", "parent"],
        ):
            if b.barcode:
                sp[str(b.barcode).strip()] = b.parent
    # Quét thẳng mã Item cũng chạy — nhiều nơi in luôn item_code lên tem nội bộ
    for code in ma_sku:
        sp.setdefault(code, code)
    return {"nv": nv, "sp": sp}


# ─────────────────────────────────────────────── phiếu ngày ──


@frappe.whitelist()
def get_or_create_ngay(ngay=None):
    """Lấy (hoặc tạo draft) phiếu ngày — chỗ gắn báo mẻ / báo cán / vào hộp."""
    _any_sx_guard()
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


def _chan_neu_chot(ngay_sx, nua, viec):
    """Chặn sửa dữ liệu của NỬA đã chốt (D55).

    Từ D55 phiếu ngày còn NHÁP khi mới chốt một nửa, nên `docstatus != 0` không còn
    là dấu hiệu "đã chốt" nữa — phải đọc đúng cờ của nửa đó. Chốt rồi mà vẫn sửa
    được là phiếu một đằng chứng từ kho một nẻo.
    """
    d = frappe.db.get_value(
        "SX Ngay San Xuat", ngay_sx, ["docstatus", "chot_ghiso", "chot_vaohop"],
        as_dict=True)
    if not d:
        frappe.throw(_("Không tìm thấy phiếu ngày {0}.").format(ngay_sx))
    if d.docstatus == 2:
        frappe.throw(_("Phiếu ngày đã huỷ."))
    if d.docstatus == 1 or cint(d.get(f"chot_{nua}")):
        nhan = "Ghi sổ" if nua == "ghiso" else "Vào hộp"
        frappe.throw(
            _("Phần {0} của ngày này đã chốt — không {1} được nữa. Huỷ chốt {0} "
              "trước nếu cần sửa.").format(nhan, viec)
        )


@frappe.whitelist()
def bao_me(ngay_sx, rows):
    """Upsert child bao_me. rows = [{item_btp, so_me}]."""
    guard_card("baome")
    _chan_neu_chot(ngay_sx, "ghiso", _("sửa báo mẻ"))
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    doc.set("bao_me", [])
    for r in frappe.parse_json(rows) or []:
        if flt(r.get("so_me")) > 0:
            doc.append("bao_me", {"item_btp": r.get("item_btp"), "so_me": flt(r.get("so_me"))})
    doc.save()
    return _ngay_summary(doc.name)


@frappe.whitelist()
def bao_can(ngay_sx, rows):
    """Upsert child bao_can. rows = [{item_bot_banh, so_me, ghi_chu?}]."""
    guard_card("baocan")
    _chan_neu_chot(ngay_sx, "ghiso", _("sửa báo cán"))
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    doc.set("bao_can", [])
    for r in frappe.parse_json(rows) or []:
        if flt(r.get("so_me")) > 0:
            doc.append(
                "bao_can",
                {"item_bot_banh": r.get("item_bot_banh"), "so_me": flt(r.get("so_me")),
                 "ghi_chu": r.get("ghi_chu")},
            )
    doc.save()
    return _ngay_summary(doc.name)


@frappe.whitelist()
def ghi_su_co(ngay_sx, loai, mo_ta=None, phut_dung=0):
    """Append 1 dòng sự cố (QC nào cũng ghi được)."""
    guard_card("suco")
    # Sự cố thuộc nửa Ghi sổ (nó là nhật ký chuyền), nhưng ghi thêm sự cố KHÔNG
    # sinh chứng từ kho nào — chỉ chặn khi cả ngày đã khoá hẳn.
    d = frappe.db.get_value("SX Ngay San Xuat", ngay_sx, "docstatus")
    if d != 0:
        frappe.throw(_("Phiếu ngày đã chốt — không ghi thêm sự cố được"))
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    doc.append(
        "su_co",
        {"thoi_diem": frappe.utils.now(), "loai": loai, "mo_ta": mo_ta,
         "phut_dung": cint(phut_dung)},
    )
    doc.save()
    return {"so_su_co": len(doc.su_co)}


@frappe.whitelist()
def luu_bang_vao_hop(ngay_sx, rows, an_ca=None):
    """Upsert DRAFT SX Bang Vao Hop (auto-save). Đơn giá luôn tính lại server-side.

    `an_ca` = [{nhan_vien, an_ca, an_dem}] (D30). Bỏ qua (None) thì GIỮ NGUYÊN bảng
    chấm ăn đang có — client nào chỉ sửa sản lượng sẽ không vô tình xoá dấu chấm ăn.
    """
    guard_card("vaohop")
    _chan_neu_chot(ngay_sx, "vaohop", _("sửa bảng vào hộp"))
    ten = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": ngay_sx, "docstatus": 0}, "name"
    )
    doc = frappe.get_doc("SX Bang Vao Hop", ten) if ten else frappe.new_doc("SX Bang Vao Hop")
    doc.ngay_sx = ngay_sx
    doc.set("dong", [])
    for r in frappe.parse_json(rows) or []:
        doc.append(
            "dong",
            {"nhan_vien": r.get("nhan_vien"),
             "activity_type": r.get("activity_type"),
             "san_pham": r.get("san_pham") or None,
             "so_hop": cint(r.get("so_hop"))},
        )
    if an_ca is not None:
        doc.set("an_ca", [])
        for r in frappe.parse_json(an_ca) or []:
            if not (cint(r.get("an_ca")) or cint(r.get("an_dem"))):
                continue   # không chấm gì thì khỏi lưu dòng rỗng
            doc.append(
                "an_ca",
                {"nhan_vien": r.get("nhan_vien"),
                 "an_ca": cint(r.get("an_ca")),
                 "an_dem": cint(r.get("an_dem"))},
            )
    doc.flags.ignore_permissions = True
    doc.save()
    return _bang_summary(ngay_sx)


# ─────────────────────────────────────────────── dashboard ──


@frappe.whitelist()
def dashboard(tu_ngay=None, den_ngay=None):
    """KPI quản lý: sản lượng SKU, năng suất/người, mẻ trộn vs cán, tồn BTP, sự cố."""
    guard_card("quanly")
    den_ngay = getdate(den_ngay or nowdate())
    tu_ngay = getdate(tu_ngay) if tu_ngay else add_days(den_ngay, -6)

    # Lấy cả ngày mới chốt MỘT NỬA. Từ D55 phiếu ngày chỉ submit khi xong cả hai
    # nửa, nên lọc docstatus=1 làm sản lượng của ngày đã chốt Vào hộp (nhưng chưa
    # chốt Ghi sổ) biến mất khỏi dashboard — quản lý mở lên thấy hôm nay bằng 0.
    phieu = frappe.get_all(
        "SX Ngay San Xuat",
        filters={"ngay": ("between", (tu_ngay, den_ngay)), "docstatus": ("<", 2),
                 "chot_vaohop": 1},
        fields=["name", "ngay", "tong_hop_tp", "tong_luong_sp"],
        order_by="ngay",
    )
    ds_phieu = [p.name for p in phieu]

    san_luong_sku, nang_suat, su_co, phut_dung = [], [], [], 0
    rows = []
    if ds_phieu:
        bang = frappe.get_all(
            "SX Bang Vao Hop", filters={"ngay_sx": ("in", ds_phieu), "docstatus": 1},
            pluck="name",
        )
        if bang:
            rows = frappe.get_all(
                "SX Bang Vao Hop Item",
                filters={"parent": ("in", bang), "parenttype": "SX Bang Vao Hop"},
                fields=["nhan_vien", "ten_nhan_vien", "san_pham", "activity_type",
                        "so_hop", "thanh_tien"],
            )
            gop_sku, gop_nv = {}, {}
            for r in rows:
                # Chưa gắn SKU thì gom theo loại công việc (D23) — vẫn thấy sản lượng
                khoa = r.san_pham or r.activity_type
                s = gop_sku.setdefault(
                    khoa,
                    {"san_pham": khoa, "activity_type": r.activity_type,
                     "co_sku": bool(r.san_pham), "so_hop": 0},
                )
                s["so_hop"] += cint(r.so_hop)
                g = gop_nv.setdefault(
                    r.nhan_vien,
                    {"nhan_vien": r.nhan_vien, "ten": r.ten_nhan_vien, "so_hop": 0, "tien": 0.0},
                )
                g["so_hop"] += cint(r.so_hop)
                g["tien"] += flt(r.thanh_tien)
            san_luong_sku = sorted(gop_sku.values(), key=lambda x: -x["so_hop"])
            nang_suat = sorted(gop_nv.values(), key=lambda x: -x["so_hop"])

        su_co = frappe.get_all(
            "SX Su Co Item",
            filters={"parent": ("in", ds_phieu), "parenttype": "SX Ngay San Xuat"},
            fields=["loai", "phut_dung", "mo_ta", "thoi_diem"],
        )
        phut_dung = sum(cint(r.phut_dung) for r in su_co)

    doi_chieu = _vao_hop_vs_nhap_kho(rows, tu_ngay, den_ngay)

    # Mẻ trộn (bao_me) vs cán (bao_can) theo bột bánh — delta = cảnh báo
    tron_can = _tron_vs_can(ds_phieu)
    ton_btp = _ton_btp()
    # Lô R chưa nhập bột: chốt ngày tự nhập lô rang HÔM TRƯỚC, nên lô còn đọng lại
    # (rang đã lâu mà chưa vào kho) là dấu hiệu bất thường -> quản lý cần thấy.
    from sx.api.tang1 import lo_cho_nhap_bot
    lo_dong = lo_cho_nhap_bot()

    return {
        "tu_ngay": str(tu_ngay),
        "den_ngay": str(den_ngay),
        "phieu": [
            {"name": p.name, "ngay": str(p.ngay), "tong_hop_tp": cint(p.tong_hop_tp),
             "tong_luong_sp": flt(p.tong_luong_sp)}
            for p in phieu
        ],
        "doi_chieu_kho": doi_chieu,
        "san_luong_sku": san_luong_sku,
        "nang_suat_vao_hop": nang_suat,
        "tron_vs_can": tron_can,
        "ton_btp": ton_btp,
        "lo_cho_nhap_bot": [
            {"lo_rang": l["lo_rang"], "ngay_rang": str(l["ngay_rang"]),
             "loai_dau": l["loai_dau"], "dau_kg": flt(l["dau_kg"]), "bot_kg": flt(l.get("bot_kg"))}
            for l in lo_dong
        ],
        "su_co": [
            {"loai": r.loai, "phut_dung": cint(r.phut_dung), "mo_ta": r.mo_ta,
             "thoi_diem": str(r.thoi_diem)}
            for r in su_co
        ],
        "phut_dung": phut_dung,
    }


def _vao_hop_vs_nhap_kho(rows_vao_hop, tu_ngay, den_ngay):
    """Đối chiếu SỐ CHẤM VÀO HỘP với SỐ ĐÃ NHẬP KHO, theo từng SKU.

    Hai con số này KHÔNG ràng buộc nhau (D62 — hai chứng từ độc lập), và đúng là
    không nên ràng buộc: chấm vào hộp tính lương, nhập kho ghi tồn. Nhưng lệch nhiều
    thì có chuyện — hộp lỗi, hàng còn ở xưởng chưa chuyển, hoặc quên lập phiếu nhận.
    Đối chiếu là việc của BÁO CÁO, đặt đúng chỗ này thay vì chặn lúc nhập liệu.

    Lệch ÂM = vào hộp nhiều hơn nhập kho (bình thường nếu chưa chuyển hết).
    Lệch DƯƠNG = nhập kho nhiều hơn chấm — đáng xem, thường là chấm sót.
    """
    gop = {}
    for r in rows_vao_hop:
        if not r.get("san_pham"):
            continue
        g = gop.setdefault(r["san_pham"], {"item": r["san_pham"], "vao_hop": 0, "nhap_kho": 0})
        g["vao_hop"] += cint(r.get("so_hop"))

    phieu_kho = frappe.get_all(
        "SX Phieu Nhap TP",
        filters={"ngay": ("between", (tu_ngay, den_ngay)), "docstatus": 1},
        pluck="name",
    )
    if phieu_kho:
        for r in frappe.get_all(
            "SX Phieu Nhap TP Item",
            filters={"parent": ("in", phieu_kho), "parenttype": "SX Phieu Nhap TP"},
            fields=["item", "so_dem"],
        ):
            g = gop.setdefault(r.item, {"item": r.item, "vao_hop": 0, "nhap_kho": 0})
            g["nhap_kho"] += cint(r.so_dem)

    ten = {}
    if gop:
        ten = {
            i.name: (i.item_name or i.name)
            for i in frappe.get_all(
                "Item", filters={"name": ("in", list(gop))},
                fields=["name", "item_name"])
        }
    ra = []
    for g in gop.values():
        g["ten"] = ten.get(g["item"], g["item"])
        g["lech"] = g["nhap_kho"] - g["vao_hop"]
        ra.append(g)
    return sorted(ra, key=lambda x: (-abs(x["lech"]), -x["vao_hop"]))


def _tron_vs_can(ds_phieu):
    if not ds_phieu:
        return []
    tron = {}
    for r in frappe.get_all(
        "SX Bao Me", filters={"parent": ("in", ds_phieu), "parenttype": "SX Ngay San Xuat"},
        fields=["item_btp", "so_me"],
    ):
        tron[r.item_btp] = tron.get(r.item_btp, 0) + flt(r.so_me)
    can = {}
    for r in frappe.get_all(
        "SX Bao Can", filters={"parent": ("in", ds_phieu), "parenttype": "SX Ngay San Xuat"},
        fields=["item_bot_banh", "so_me"],
    ):
        can[r.item_bot_banh] = can.get(r.item_bot_banh, 0) + flt(r.so_me)
    items = set(tron) | set(can)
    out = []
    for it in sorted(items):
        me_tron = flt(tron.get(it, 0))
        me_can = flt(can.get(it, 0))
        out.append({"item": it, "me_tron": me_tron, "me_can": me_can,
                    "canh_bao": me_can > me_tron + 1e-6})
    return out


def _ton_btp():
    """Tồn BTP cho dashboard quản lý. BTP-Dau (đỗ ủ / đỗ vỡ — D31) nằm ở kho Xưởng,
    không phải kho BTP: đó là hàng đang dở dang ngoài chuyền, đọc đúng kho mới thấy."""
    from sx.utils import kho_xuong

    settings = get_settings()
    kho_x = kho_xuong(settings)
    out = []
    for nhom in ("BTP-Dau", "BTP-Bot", "BTP-Phu", "BTP-Banh", "BTP-Bot-SP"):
        kho = kho_x if nhom == "BTP-Dau" else settings.kho_btp
        for it in frappe.get_all("Item", filters={"custom_sx_nhom": nhom}, pluck="name"):
            qty = flt(
                frappe.db.get_value(
                    "Bin", {"item_code": it, "warehouse": kho}, "actual_qty"
                )
            )
            out.append({"item": it, "nhom": nhom, "kho": kho,
                        "ton_kg": flt(qty, 1), "am": qty < 0})
    return out


# ─────────────────────────── lưu đồ tồn BTP tầng 2/3 (D32) ──
#
# Tầng 2/3 KHÔNG có nút công đoạn như tầng 1: bột bánh / bột đậu sinh ra khi báo mẻ,
# và bị trừ lúc TP vào hộp (backflush — D8). Nên lưu đồ này ĐỌC, không bấm: cho QC
# thấy hàng đang đọng ở khúc nào trước khi quyết định hôm nay trộn gì.
#
#   Đỗ ─(tầng 1)→ BỘT NỀN ┬─→ BỘT BÁNH (8 loại) ─→ TP bánh hộp
#                          └─→ BỘT ĐẬU (8 công thức) ─→ TP bột túi/hộp
#   Đường ─→ ĐƯỜNG HOÁN (3) ─┘ (chỉ nhánh bánh)


def _ton_nhom(nhom, kho, kem_me=False):
    """Tồn từng item của 1 nhóm tại 1 kho — CHỈ loại đang có hàng (D34).

    Bỏ item tồn đúng 0: nhà máy có 8 loại bột bánh nhưng ngày thường chỉ chạy 2-3 loại,
    liệt kê cả 8 thì phần đang có hàng chìm nghỉm. Tồn ÂM thì VẪN HIỆN — đó là lỗi số
    liệu cần thấy ngay, không phải thứ để lọc đi.

    kem_me: quy ra số mẻ theo cỡ mẻ chuẩn BOM.
    """
    out = []
    for it in frappe.get_all(
        "Item", filters={"custom_sx_nhom": nhom, "disabled": 0},
        fields=["name", "item_name"], order_by="item_name",
    ):
        ton = flt(
            frappe.db.get_value(
                "Bin", {"item_code": it["name"], "warehouse": kho}, "actual_qty"
            )
        )
        if abs(ton) < 1e-6:
            continue
        dong = {"item": it["name"], "ten": it["item_name"] or it["name"],
                "ton": flt(ton, 1), "am": ton < 0}
        if kem_me:
            bom = get_bom_active(it["name"])
            co_me = flt(frappe.db.get_value("BOM", bom, "custom_co_me_chuan_kg")) if bom else 0
            dong["so_me"] = flt(ton / co_me, 1) if co_me else None
        out.append(dong)
    out.sort(key=lambda d: -d["ton"])   # nhiều hàng nhất lên trước
    return out


def _chang(nhan, items, dung_chung=0):
    """Một chặng của lưu đồ: nhãn + TỔNG kg (số to) + chi tiết loại đang có hàng."""
    return {
        "nhan": nhan,
        "dung_chung": cint(dung_chung),
        "tong": flt(sum(d["ton"] for d in items), 1),
        "so_loai": len(items),
        "items": items,
    }


def _tp_theo_nhanh():
    """Chia item TP về nhánh bánh / bột theo BOM tầng 3 (RM nào là bột bánh hay bột đậu).

    Không đoán theo tên SKU — tên đặt tay, đổi lúc nào không biết. BOM mới là sự thật.
    """
    nhanh = {"banh": [], "bot": []}
    for tp in [i.name for i in items_tp(["name"])]:
        bom = get_bom_active(tp)
        if not bom:
            continue
        for r in frappe.get_cached_doc("BOM", bom).items:
            nhom_rm = frappe.get_cached_value("Item", r.item_code, "custom_sx_nhom") or ""
            if nhom_rm == "BTP-Banh":
                nhanh["banh"].append(tp)
                break
            if nhom_rm == "BTP-Bot-SP":
                nhanh["bot"].append(tp)
                break
    return nhanh


def _ton_tp(ds_tp, kho):
    """Tồn TP: gộp thành 1 con số + đếm SKU còn hàng (liệt kê hết thì dài vô ích)."""
    tong, co_hang = 0.0, 0
    for tp in ds_tp:
        q = flt(frappe.db.get_value("Bin", {"item_code": tp, "warehouse": kho}, "actual_qty"))
        tong += q
        if q > 0:
            co_hang += 1
    return {"tong": flt(tong, 0), "so_sku": co_hang, "tong_sku": len(ds_tp)}


@frappe.whitelist()
def luu_do_btp():
    """Lưu đồ tồn bán thành phẩm 2 nhánh bánh / bột đậu (D32)."""
    guard_card("luutrinhbtp")
    from sx.utils import kho_xuong

    settings = get_settings()
    kho_btp, kho_tp = settings.kho_btp, settings.kho_tp
    tp = _tp_theo_nhanh()

    # Đỗ ủ / đỗ vỡ nằm ở kho Xưởng (D31) — vẫn là bán thành phẩm, quản lý phải thấy.
    # Chi tiết theo từng lô thì xem lưu đồ tầng 1 bên màn ghi số.
    dau_xuong = _ton_nhom("BTP-Dau", kho_xuong(settings))
    bot_nen = _ton_nhom("BTP-Bot", kho_btp)
    return {
        "nhanh": [
            {
                "ma": "banh", "ten": _("Bánh đậu xanh"),
                "chang": [
                    _chang(_("Đỗ ở xưởng"), dau_xuong, dung_chung=1),
                    _chang(_("Bột nền"), bot_nen, dung_chung=1),
                    _chang(_("Đường hoán"), _ton_nhom("BTP-Phu", kho_btp)),
                    _chang(_("Bột bánh"), _ton_nhom("BTP-Banh", kho_btp, kem_me=True)),
                ],
                "tp": _ton_tp(tp["banh"], kho_tp),
            },
            {
                "ma": "bot", "ten": _("Bột đậu"),
                "chang": [
                    _chang(_("Đỗ ở xưởng"), dau_xuong, dung_chung=1),
                    _chang(_("Bột nền"), bot_nen, dung_chung=1),
                    _chang(_("Bột đậu"), _ton_nhom("BTP-Bot-SP", kho_btp, kem_me=True)),
                ],
                "tp": _ton_tp(tp["bot"], kho_tp),
            },
        ],
    }


# ─────────────────────────────────────────────── truy xuất (đệ quy) ──


@frappe.whitelist()
def truy_xuat(batch_tp):
    """Chuỗi truy xuất ngược từ batch TP: TP → mẻ (BTP) → lô R → lô đậu/đường NCC.

    Đệ quy: với 1 batch, tìm SE nơi nó là FG, list RM batch; RM là BTP -> đệ quy tiếp;
    RM là NVL -> lá (lô NCC). Có visited + giới hạn độ sâu chống vòng lặp.
    """
    guard_card("quanly")
    if not frappe.db.exists("Batch", batch_tp):
        frappe.throw(_("Không tìm thấy batch {0}").format(batch_tp))
    item_tp = frappe.db.get_value("Batch", batch_tp, "item")
    return {
        "batch_tp": batch_tp,
        "item_tp": item_tp,
        "cay": _truy_xuat_batch(batch_tp, item_tp, set(), 0),
    }


def _truy_xuat_batch(batch, item, visited, depth):
    """Trả node {batch, item, nhom, nguon_lieu:[...]} — đệ quy xuống RM là BTP."""
    nhom = frappe.get_cached_value("Item", item, "custom_sx_nhom") or ""
    node = {"batch": batch, "item": item, "nhom": nhom, "nguon_lieu": []}
    if depth > 6 or batch in visited:
        return node
    visited = visited | {batch}

    # SE nơi batch này là thành phẩm (is_finished_item=1)
    se_list = frappe.get_all(
        "Stock Entry Detail",
        filters={"batch_no": batch, "is_finished_item": 1, "docstatus": 1},
        pluck="parent",
    )
    for se in set(se_list):
        rm = frappe.get_all(
            "Stock Entry Detail",
            filters={"parent": se, "is_finished_item": 0, "docstatus": 1},
            fields=["item_code", "batch_no", "qty"],
        )
        for r in rm:
            if not r.batch_no:
                continue
            rm_nhom = frappe.get_cached_value("Item", r.item_code, "custom_sx_nhom") or ""
            entry = {
                "se": se, "item": r.item_code, "batch": r.batch_no,
                "kg": flt(r.qty, 2), "nhom": rm_nhom,
            }
            if rm_nhom.startswith("BTP"):
                # BTP nội bộ -> đệ quy xuống (bột nền batch = lô R; đường hoán...)
                entry["con"] = _truy_xuat_batch(r.batch_no, r.item_code, visited, depth + 1)
                # Bột nền: nối tới phiếu xuất đậu + lô đậu NCC qua lo_rang = batch
                xd = frappe.db.get_value(
                    "SX Xuat Dau", {"lo_rang": r.batch_no, "docstatus": 1},
                    ["name", "loai_dau", "ngay_rang"], as_dict=True,
                )
                if xd:
                    entry["lo_rang"] = r.batch_no
                    entry["xuat_dau"] = xd.name
                    entry["loai_dau"] = xd.loai_dau
                    entry["lo_dau_ncc"] = _lo_dau_ncc_cua_lo_rang(r.batch_no)
            else:
                entry["lo_ncc"] = r.batch_no  # NVL -> lá (lô nhà cung cấp)
            node["nguon_lieu"].append(entry)
    return node


def _lo_dau_ncc_cua_lo_rang(lo_rang):
    """Lô đậu NCC đã trừ khi nhập bột lô R (RM đậu của SE T1 trong SX Nhap Bot)."""
    nb = frappe.db.get_value("SX Nhap Bot", {"lo_rang": lo_rang, "docstatus": 1}, ["se"], as_dict=True)
    if not nb or not nb.se:
        return None
    rm = frappe.get_all(
        "Stock Entry Detail",
        filters={"parent": nb.se, "is_finished_item": 0, "docstatus": 1},
        fields=["batch_no"],
    )
    return [r.batch_no for r in rm if r.batch_no]
