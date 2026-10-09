"""Whitelisted API portal /sx (v3). Guard theo card-capability (config/roles.py).

Dữ liệu doc chuẩn chỉ trả field whitelist (Employee: name, employee_name).
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from sx.config.roles import (
    ROLE_VIEWS,
    allowed_views,
    co_so,
    guard_card,
    is_super,
    landing_view,
    user_roles,
    view_cards,
)
from sx.sx.doctype.sx_bang_vao_hop.sx_bang_vao_hop import CONG_NHAT
from sx.utils import (
    bang_don_gia,
    dat_ten_hien_thi,
    don_gia_ap_dung,
    get_bom_active,
    get_dau_items,
    get_settings,
    items_tp,
    nap_bom,
    ton_bin,
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
    """Cho phép mọi role SX (boot / phiếu ngày dùng chung).

    Lấy thẳng từ ROLE_VIEWS chứ không chép tay danh sách role: thêm role mới mà
    quên sửa chỗ này thì người ta đăng nhập được, thấy tab của mình, bấm vào là
    "không có quyền vào portal" — lỗi trông như hỏng app chứ không như thiếu cấu hình.
    """
    roles = user_roles()
    if is_super(roles) or roles & set(ROLE_VIEWS):
        return
    frappe.throw(_("Bạn không có quyền vào portal sản xuất."), frappe.PermissionError)


# ─────────────────────────────────────────────────────────────── boot ──


# Danh mục theo màn (D121): get_boot chỉ trả phần NHẸ theo ngày; danh mục của
# từng màn tải riêng, MỘT lần, khi màn đó mở. Quản lý mở màn Quản lý không còn phải
# chờ dựng danh mục báo mẻ + vào hộp (bảng giá, nhân viên, mã quét…) mà màn đó
# không dùng tới. Shell giữ phần đã tải trong store.boot.
PHAN = ("ghiso", "vaohop", "quet")
# Màn nào cần phần nào. Khớp với PHAN_VIEW trong shell.js.
VIEW_PHAN = {"ghiso": ["ghiso"], "vaohop": ["vaohop"], "nhapkho": ["quet"]}


def _phan_duoc(roles, super_):
    """Phần danh mục user được lấy — cùng điều kiện quyền như trước D121."""
    ra = set()
    if super_ or "SX Ghi So" in roles:
        ra.add("ghiso")
    if super_ or "SX Vao Hop" in roles:
        ra |= {"vaohop", "quet"}
    if "SX Thu Kho" in roles:
        ra.add("quet")      # quét hộp ở màn Nhập kho — trước D121 thủ kho không có
    return ra


def _doc_phan(phan):
    if phan is None:
        return None
    if isinstance(phan, str):
        import json

        phan = json.loads(phan) if phan.strip().startswith("[") else [phan]
    return {p for p in phan if p in PHAN}


def _danh_muc(phan, ngay_xem, roles, super_):
    """Dựng các phần danh mục được yêu cầu (đã lọc theo quyền)."""
    ra = {}
    phan = set(phan)
    if "vaohop" in phan:
        phan.add("quet")        # màn Ghi hộp quét thẻ người + mã hộp
    phan &= _phan_duoc(roles, super_)

    def _items_nhom(nhom, kem_co_me=True):
        out = frappe.get_all(
            "Item", filters={"custom_sx_nhom": nhom, "disabled": 0},
            fields=["name", "item_name"], order_by="item_name",
        )
        if kem_co_me:
            # D120: một truy vấn BOM cho cả nhóm + cỡ mẻ đọc qua cache tài liệu,
            # thay cho 2 truy vấn mỗi mã.
            bom_cua = nap_bom([it["name"] for it in out])
            for it in out:
                bom = bom_cua.get(it["name"])
                it["co_me_chuan_kg"] = (
                    flt(frappe.get_cached_value("BOM", bom, "custom_co_me_chuan_kg")) if bom else 0
                )
        return out

    if "ghiso" in phan:
        ra["loai_dau"] = get_dau_items()
        ra["items_nau"] = _items_nhom("BTP-Phu")       # 3 đường hoán (màu gộp thẳng vào BOM)
        ra["items_bot_banh"] = _items_nhom("BTP-Banh")  # 8 bột bánh
        ra["items_bot_dau"] = _items_nhom("BTP-Bot-SP")  # 8 bột đậu

    nv = None
    if "vaohop" in phan:
        settings = get_settings()
        ra["items_tp"] = items_tp(["name", "item_name", "item_group"])
        ra["tien_an_ca"] = flt(settings.get("tien_an_ca"))
        ra["tien_an_dem"] = flt(settings.get("tien_an_dem"))
        ra["danh_muc_khoan"] = _danh_muc_khoan(ngay_xem)
        ra["sp_gan_day"] = _sp_gan_day()
        ra["bang_don_gia"] = bang_don_gia(ngay_xem)
        ra["nhan_vien"], canh_bao_nv = _nhan_vien_vao_hop()
        nv = ra["nhan_vien"]
        if canh_bao_nv:
            ra["canh_bao_nhan_vien"] = canh_bao_nv
    if "quet" in phan:
        if nv is None:
            nv, _cb = _nhan_vien_vao_hop()
        ra["ma_quet"] = _ma_quet(nv)
    ra["phan"] = sorted(phan)
    return ra


@frappe.whitelist()
def get_boot(ngay=None, phan=None):
    """Context khởi động: views/cards theo role, phiếu ngày, bảng vào hộp của ngày.

    `ngay` = ngày đang XEM (D25). Bỏ trống -> hôm nay. Cho phép mở lại ngày cũ để
    đối chiếu / sửa; ngày đã chốt trả về read-only (docstatus 1) cho tới khi huỷ chốt.

    `phan` (D121) = danh sách phần danh mục kèm theo ("ghiso" / "vaohop" / "quet").
    Bỏ trống (client cũ trước D121) -> mọi phần user được lấy, như trước.
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
    cs = co_so(roles)

    boot = {
        "user": frappe.session.user,
        "is_quan_ly": super_,
        # D132: Trưởng Ban ISO (hoặc quản lý) — tab Xem xét / Truy xuất trong màn QC.
        "la_iso": super_ or "ISO Manager" in roles,
        # W43: tab Sổ chỉ với người được giao sổ — cùng cách tính như trang /sx.
        "views": allowed_views(roles, cs),
        "viewCards": view_cards(roles, cs),
        "landing": landing_view(roles, cs),
        "hom_nay": hom_nay,
        "ngay_xem": ngay_xem,
        "la_hom_nay": ngay_xem == hom_nay,
        "ngay_sx": ngay_sx,
        "bang_vao_hop": _bang_summary(ngay_sx["name"]) if ngay_sx else None,
    }
    yeu_cau = _doc_phan(phan)
    boot.update(_danh_muc(PHAN if yeu_cau is None else yeu_cau, ngay_xem, roles, super_))
    return boot


@frappe.whitelist()
def danh_muc(phan, ngay=None):
    """Danh mục của một màn, tải khi màn đó mở lần đầu (D121). Cùng quyền như get_boot."""
    _any_sx_guard()
    roles = user_roles()
    return _danh_muc(_doc_phan(phan) or set(), str(getdate(ngay)) if ngay else nowdate(),
                     roles, is_super(roles))


def _ngay_summary(ten):
    if not ten:
        return None
    doc = frappe.get_doc("SX Ngay San Xuat", ten)
    return {
        "name": doc.name,
        "ngay": str(doc.ngay),
        "docstatus": doc.docstatus,
        "trang_thai": doc.trang_thai,
        # D123: không còn chốt — thay bằng trạng thái đồng bộ kho / lương.
        "dong_bo": {
            "gs": {"cho": cint(doc.get("can_dong_bo_gs")), "loi": doc.get("loi_dong_bo_gs")},
            "vh": {"cho": cint(doc.get("can_dong_bo_vh")), "loi": doc.get("loi_dong_bo_vh")},
        },
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
        "su_co": su_co_cua_ngay(doc.name),
    }


def _xem_het_vao_hop():
    """Quản lý thấy / sửa mọi dòng vào hộp; QC chỉ dòng mình ghi (D113).
    Nhớ theo request — được hỏi cho MỖI dòng bảng (D120)."""
    from sx.utils import nho

    m = nho("quyen")
    if "xem_het_vh" not in m:
        m["xem_het_vh"] = is_super(user_roles())
    return m["xem_het_vh"]


def _cua_toi(r, u=None):
    return _xem_het_vao_hop() or r.get("nguoi_ghi") == (u or frappe.session.user)


def _bang_summary(ngay_sx):
    ten = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": ngay_sx, "docstatus": ("<", 2)}, "name"
    )
    if not ten:
        return None
    doc = frappe.get_doc("SX Bang Vao Hop", ten)
    # D113: QC chỉ thấy dòng MÌNH ghi — tổng cũng chỉ là phần của mình.
    dong = [r for r in doc.dong if _cua_toi(r)]
    return {
        "name": doc.name,
        "docstatus": doc.docstatus,
        "xem_het": _xem_het_vao_hop(),
        "tong_hop": sum(cint(r.so_hop) for r in dong),
        "tong_tien": sum(flt(r.thanh_tien) for r in dong),
        "dong": [
            # Dòng công nhật đi ra với mã giả CONG_NHAT (D101) — màn Ghi hộp coi nó
            # như một "người" để chấm cùng một cách, và gửi lại đúng mã đó.
            {"nhan_vien": CONG_NHAT if cint(r.get("cong_nhat")) else r.nhan_vien,
             "ten_nhan_vien": _("Công nhật") if cint(r.get("cong_nhat")) else r.ten_nhan_vien,
             "cong_nhat": cint(r.get("cong_nhat")),
             "san_pham": r.san_pham, "cach_lam": r.cach_lam, "so_hop": r.so_hop,
             "don_gia": r.don_gia, "thanh_tien": r.thanh_tien,
             # name = mã dòng: máy gửi lại để server biết sửa / xoá ĐÚNG dòng nào.
             "name": r.name, "nguoi_ghi": r.get("nguoi_ghi")}
            for r in dong
        ],
        "an_ca": [
            {"nhan_vien": r.nhan_vien, "an_ca": cint(r.an_ca), "an_dem": cint(r.an_dem)}
            for r in (doc.get("an_ca") or [])
        ],
    }


def _sp_gan_day():
    """Mã hàng ghi gần đây (14 ngày) — hiện đầu danh sách chọn, đỡ phải tìm."""
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
        fields=["san_pham"],
        order_by="creation desc",
    )
    seen = []
    for r in rows:
        if r.san_pham and r.san_pham not in seen:
            seen.append(r.san_pham)
    return seen[:12]


def _danh_muc_khoan(ngay):
    """Danh mục QC chọn khi ghi bảng vào hộp (D68): MÃ HÀNG, kèm các CÁCH LÀM có giá.

    Nguồn giá là bảng đơn giá áp dụng cho `ngay`. Trả về mọi Item thành phẩm chứ
    không chỉ mã đã khai giá — mã chưa khai giá vẫn ghi được (đánh dấu `chua_gia`),
    vì chặn QC lại giữa xưởng vì một dòng chưa khai giá là bắt cả chuyền dừng.

    `cach_lam` rỗng và `gia_chung` có giá  -> màn nhập khỏi hỏi thêm bước nào.
    `cach_lam` một phần tử, không giá chung -> tự chọn luôn.
    Còn lại -> hỏi cách làm, vì hai cách làm hai đơn giá khác nhau.
    """
    bang = don_gia_ap_dung(ngay) if ngay else {}
    # Gom cách làm theo mã MỘT lần (D120) — cach_lam_cua quét cả bảng cho mỗi mã.
    cach_theo_ma = {}
    for (sp, cl) in bang:
        if cl:
            cach_theo_ma.setdefault(sp, set()).add(cl)
    ds = []
    for it in items_tp(["name", "item_name", "stock_uom"]):
        cach = sorted(cach_theo_ma.get(it.name, ()))
        chung = bang.get((it.name, ""))
        ds.append({
            "item": it.name,
            "ten": it.item_name or it.name,
            "dvt": it.stock_uom or "",
            "cach_lam": [{"ten": c, "don_gia": flt(bang[(it.name, c)])} for c in cach],
            "gia_chung": flt(chung) if chung is not None else None,
            "chua_gia": not cach and chung is None,
        })
    return ds


def _ma_quet(nhan_vien):
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

    ma_sku = {i.name for i in items_tp(["name"])}
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
    """D123: không còn chốt — chỉ chặn khi phiếu ngày không còn (đã huỷ / đã xoá).
    Giữ tên hàm để các nơi gọi cũ không phải đổi."""
    d = frappe.db.get_value("SX Ngay San Xuat", ngay_sx, "docstatus")
    if d is None:
        frappe.throw(_("Không tìm thấy phiếu ngày {0}.").format(ngay_sx))
    if cint(d) == 2:
        frappe.throw(_("Phiếu ngày đã huỷ — không {0} được.").format(viec))


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
    """Ghi một sự cố của tổ Ghi sổ.

    D87: ghi vào DocType `SX Su Co` — MỘT sổ sự cố cho cả nhà máy, không phải
    một bảng con riêng của phiếu ngày nữa. Lý do: hai chỗ ghi sự cố nghĩa là hai
    chỗ phải nhớ đi xem, và cái không ai nhớ thì không ai đóng. Bảng con cũ
    (`SX Su Co Item`) giữ nguyên dữ liệu lịch sử, patch d87 chuyển sang, không
    ai ghi vào đó nữa.

    Chữ ký method và khoá hàng chờ ngoại tuyến GIỮ NGUYÊN: điện thoại đang có
    sự cố nằm trong hàng chờ từ hôm qua vẫn phải gửi lên được sau khi deploy.
    """
    guard_card("suco")
    # Sự cố thuộc nửa Ghi sổ (nó là nhật ký chuyền), nhưng ghi thêm sự cố KHÔNG
    # sinh chứng từ kho nào — chỉ chặn khi cả ngày đã khoá hẳn.
    d = frappe.db.get_value("SX Ngay San Xuat", ngay_sx, ["docstatus", "ngay"],
                            as_dict=True)
    if not d:
        frappe.throw(_("Không tìm thấy phiếu ngày {0}").format(ngay_sx))
    if d.docstatus != 0:
        frappe.throw(_("Phiếu ngày đã chốt — không ghi thêm sự cố được"))
    sc = frappe.get_doc({
        "doctype": "SX Su Co",
        "ngay": d.ngay,
        "nguon": "Nhật ký chuyền",
        "loai_chuyen": loai,
        "loai": "Khác",
        "phut_dung": cint(phut_dung),
        "mo_ta": mo_ta or loai,
        "ngay_san_xuat": ngay_sx,
        "trang_thai": "Mở",
    })
    sc.insert()
    return {"so_su_co": len(su_co_cua_ngay(ngay_sx)), "name": sc.name}


def su_co_cua_ngay(ngay_sx):
    """Sự cố Nhật ký chuyền của một phiếu ngày, dạng cũ để màn hình khỏi phải đổi."""
    return [
        {"thoi_diem": str(r.creation), "loai": r.loai_chuyen or r.loai,
         "mo_ta": r.mo_ta, "phut_dung": cint(r.phut_dung), "name": r.name,
         "trang_thai": r.trang_thai}
        for r in frappe.get_all(
            "SX Su Co", filters={"ngay_san_xuat": ngay_sx},
            fields=["name", "creation", "loai", "loai_chuyen", "mo_ta",
                    "phut_dung", "trang_thai"],
            order_by="creation")
    ]


@frappe.whitelist()
def luu_bang_vao_hop(ngay_sx, rows, an_ca=None, biet=None):
    """Lưu bảng vào hộp NHÁP (auto-save) — GỘP, không ghi đè cả bảng (D113).

    Hai QC ghi cùng một ngày. Trước D113 mỗi lần lưu máy gửi CẢ danh sách nó đang
    thấy và server THAY HẾT bảng: QC A mở màn lúc 8h, QC B ghi 10 dòng lúc 8h05,
    8h10 A chấm thêm một người → 10 dòng của B biến mất, không ai biết.

    Từ D113:
      · `rows` = mọi dòng CỦA NGƯỜI GỬI (quản lý: mọi dòng) mà máy đang có; dòng cũ
        mang `name`, dòng mới không có.
      · `biet` = các `name` máy đã nhận từ server lần trước. Server chỉ XOÁ dòng
        của người gửi nằm trong `biet` mà không còn trong `rows`. Dòng người khác,
        và dòng người gửi thêm từ máy khác (không có trong `biet`), giữ nguyên.
      · Máy bản cũ không gửi `biet` → coi như biết mọi dòng CỦA MÌNH (vẫn không
        đụng được dòng người khác).
      · `an_ca` = [{nhan_vien, an_ca, an_dem}] chỉ những người VỪA ĐỔI; gộp theo
        người, 0/0 là bỏ chấm. Bỏ qua (None) thì giữ nguyên.
    Đơn giá luôn tính lại server-side.
    """
    guard_card("vaohop")
    _chan_neu_chot(ngay_sx, "vaohop", _("sửa bảng vào hộp"))
    u = frappe.session.user
    ten = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": ngay_sx, "docstatus": 0}, "name"
    )
    doc = frappe.get_doc("SX Bang Vao Hop", ten) if ten else frappe.new_doc("SX Bang Vao Hop")
    doc.ngay_sx = ngay_sx

    biet = None if biet is None else set(frappe.parse_json(biet) or [])
    # Dòng người gửi ĐƯỢC đụng: của mình (quản lý: mọi dòng) VÀ máy đã biết.
    duoc_sua = {r.name for r in doc.dong if r.name and _cua_toi(r, u)
                and (biet is None or r.name in biet)}
    now = frappe.utils.now_datetime()
    sua, them = {}, []

    def _khoa(nv, cn, sp, cl, sl):
        return (None if cn else nv, 1 if cn else 0, sp or None, cl or None, cint(sl))

    # Dòng CỦA MÌNH mà máy CHƯA biết — thường là bản hàng chờ vừa gửi lại khi có
    # mạng (máy vẫn giữ các dòng đó mà chưa có mã). Dòng không mã trùng y hệt một
    # dòng như vậy thì là CÙNG một dòng, không thêm bản thứ hai.
    la = {}
    if biet is not None:
        for r in doc.dong:
            if r.name and r.name not in biet and _cua_toi(r, u):
                k = _khoa(r.nhan_vien, cint(r.get("cong_nhat")), r.san_pham, r.cach_lam, r.so_hop)
                la.setdefault(k, []).append(r.name)
    for r in frappe.parse_json(rows) or []:
        cn = r.get("nhan_vien") == CONG_NHAT or cint(r.get("cong_nhat"))
        vals = {"nhan_vien": None if cn else r.get("nhan_vien"),
                "cong_nhat": 1 if cn else 0,
                "san_pham": r.get("san_pham") or None,
                "cach_lam": r.get("cach_lam") or None,
                "so_hop": cint(r.get("so_hop"))}
        if r.get("name") in duoc_sua:
            sua[r["name"]] = vals
        elif r.get("name"):
            continue      # mã dòng không phải của mình / đã mất: KHÔNG tạo bản sao
        elif la.get(_khoa(vals["nhan_vien"], cn, vals["san_pham"], vals["cach_lam"],
                          vals["so_hop"])):
            la[_khoa(vals["nhan_vien"], cn, vals["san_pham"], vals["cach_lam"],
                     vals["so_hop"])].pop()      # đã có trên server — giữ nguyên
        else:
            them.append(dict(vals, nguoi_ghi=u, ghi_luc=now))
    con = []
    for r in doc.dong:
        if r.name in duoc_sua:
            if r.name not in sua:
                continue                      # người gửi đã xoá dòng này
            r.update(sua[r.name])
            if not r.get("nguoi_ghi"):
                r.nguoi_ghi = u
        con.append(r)
    doc.set("dong", con)
    for v in them:
        doc.append("dong", v)

    if an_ca is not None:
        hien = {r.nhan_vien: r for r in (doc.get("an_ca") or [])}
        for r in frappe.parse_json(an_ca) or []:
            nv = r.get("nhan_vien")
            if not nv or nv == CONG_NHAT:
                continue   # công nhật không phải một người — không chấm ăn ở đây
            hien[nv] = {"nhan_vien": nv, "an_ca": cint(r.get("an_ca")),
                        "an_dem": cint(r.get("an_dem"))}
        doc.set("an_ca", [])
        for nv, r in hien.items():
            g = r if isinstance(r, dict) else {"nhan_vien": nv, "an_ca": r.an_ca,
                                                "an_dem": r.an_dem}
            if cint(g["an_ca"]) or cint(g["an_dem"]):
                doc.append("an_ca", {"nhan_vien": nv, "an_ca": cint(g["an_ca"]),
                                     "an_dem": cint(g["an_dem"])})
    doc.flags.ignore_permissions = True
    # Xoá hết dòng mà cũng không chấm ăn ca → không còn gì để lưu: xoá luôn bảng
    # NHÁP thay vì giữ một bảng rỗng (D106). Trước D106 bảng bắt buộc có ít nhất một
    # dòng, nên xoá dòng CUỐI của một ngày báo "Data missing in table Chi tiết".
    if not doc.dong and not doc.get("an_ca"):
        if not doc.is_new():
            doc.delete(ignore_permissions=True)
        return None
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
        filters={"ngay": ("between", (tu_ngay, den_ngay)), "docstatus": ("<", 2)},
        fields=["name", "ngay", "tong_hop_tp", "tong_luong_sp"],
        order_by="ngay",
    )
    ds_phieu = [p.name for p in phieu]

    san_luong_sku, nang_suat, su_co, phut_dung = [], [], [], 0
    rows = []
    if ds_phieu:
        bang = frappe.get_all(
            "SX Bang Vao Hop", filters={"ngay_sx": ("in", ds_phieu), "docstatus": ("<", 2)},
            pluck="name",
        )
        if bang:
            rows = frappe.get_all(
                "SX Bang Vao Hop Item",
                filters={"parent": ("in", bang), "parenttype": "SX Bang Vao Hop"},
                fields=["nhan_vien", "ten_nhan_vien", "san_pham", "cach_lam",
                        "so_hop", "thanh_tien", "cong_nhat"],
            )
            gop_sku, gop_nv = {}, {}
            for r in rows:
                khoa = r.san_pham or _("(chưa chọn mã hàng)")
                s = gop_sku.setdefault(
                    khoa,
                    {"san_pham": khoa, "co_sku": bool(r.san_pham), "so_hop": 0},
                )
                s["so_hop"] += cint(r.so_hop)
                if cint(r.cong_nhat):
                    continue   # năng suất là theo NGƯỜI — công nhật không vào bảng này
                g = gop_nv.setdefault(
                    r.nhan_vien,
                    {"nhan_vien": r.nhan_vien, "ten": r.ten_nhan_vien, "so_hop": 0, "tien": 0.0},
                )
                g["so_hop"] += cint(r.so_hop)
                g["tien"] += flt(r.thanh_tien)
            san_luong_sku = sorted(gop_sku.values(), key=lambda x: -x["so_hop"])
            nang_suat = sorted(gop_nv.values(), key=lambda x: -x["so_hop"])

        # D87: đọc từ sổ sự cố chung. Phiếu ngày cũ (trước D87) đã được patch
        # chuyển sang nên không phải đọc hai nguồn rồi gộp.
        su_co = frappe.get_all(
            "SX Su Co", filters={"ngay_san_xuat": ("in", ds_phieu)},
            fields=["name", "loai", "loai_chuyen", "phut_dung", "mo_ta",
                    "creation", "trang_thai"],
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
            {"loai": r.loai_chuyen or r.loai, "phut_dung": cint(r.phut_dung),
             "mo_ta": r.mo_ta, "thoi_diem": str(r.creation),
             "trang_thai": r.trang_thai, "name": r.name}
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
        ds = frappe.get_all("Item", filters={"custom_sx_nhom": nhom}, pluck="name")
        ton = ton_bin(ds, kho)                 # D120: một truy vấn cho cả nhóm
        for it in ds:
            qty = flt(ton.get(it))
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
    ds = frappe.get_all(
        "Item", filters={"custom_sx_nhom": nhom, "disabled": 0},
        fields=["name", "item_name"], order_by="item_name",
    )
    ton_cua = ton_bin([it["name"] for it in ds], kho)     # D120: một truy vấn
    if kem_me:
        nap_bom([it["name"] for it in ds])
    for it in ds:
        ton = flt(ton_cua.get(it["name"]))
        if abs(ton) < 1e-6:
            continue
        dong = {"item": it["name"], "ten": it["item_name"] or it["name"],
                "ton": flt(ton, 1), "am": ton < 0}
        if kem_me:
            bom = get_bom_active(it["name"])
            co_me = flt(frappe.get_cached_value("BOM", bom, "custom_co_me_chuan_kg")) if bom else 0
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
    ds = [i.name for i in items_tp(["name"])]
    nap_bom(ds)                                           # D120
    for tp in ds:
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
    ton = ton_bin(ds_tp, kho)                             # D120: một truy vấn
    for tp in ds_tp:
        q = flt(ton.get(tp))
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


# Truy xuất lô: sx/api/truyxuat.py (D115).
