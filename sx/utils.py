"""Hàm dùng chung app sx (v3).

Nguồn sự thật đơn: yield + danh mục đỗ suy từ BOM; prefix mã lô từ Item; không
cấu hình trùng lặp. FIFO toàn tuyến — không ai chọn lô (D5).
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate


def get_settings():
    """SX Settings (Single)."""
    return frappe.get_cached_doc("SX Settings")


def get_bom_active(item_code):
    """BOM active/default (docstatus 1) của 1 item, hoặc None."""
    return frappe.db.get_value(
        "BOM",
        {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
        "name",
    )


# ───────────────────────────────────── đỗ ↔ bột nền (suy từ BOM T1) ──


def _dau_rm_cua_bom(bom_name):
    """RM đỗ của 1 BOM bột nền = dòng NVL is_stock_item=1 (Nước non-stock bị loại).

    Trả (item_code_đỗ, stock_qty) hoặc (None, 0).
    """
    bom = frappe.get_cached_doc("BOM", bom_name)
    for r in bom.items:
        nhom = frappe.get_cached_value("Item", r.item_code, "custom_sx_nhom") or ""
        is_stock = cint(frappe.get_cached_value("Item", r.item_code, "is_stock_item"))
        if nhom == "NVL" and is_stock:
            return r.item_code, flt(r.stock_qty)
    return None, 0


def get_dau_items():
    """Danh sách item đỗ (RM trong các BOM active của item nhóm BTP-Bot).

    Trả [{name, item_name, prefix}]. Dùng cho portal lọc "loại đỗ".
    """
    seen = {}
    bot_items = frappe.get_all(
        "Item", filters={"custom_sx_nhom": "BTP-Bot", "disabled": 0}, pluck="name"
    )
    for bot in bot_items:
        bom = get_bom_active(bot)
        if not bom:
            continue
        dau, _qty = _dau_rm_cua_bom(bom)
        if dau and dau not in seen:
            seen[dau] = {
                "name": dau,
                "item_name": frappe.get_cached_value("Item", dau, "item_name") or dau,
                "prefix": frappe.get_cached_value("Item", dau, "custom_batch_prefix") or "",
            }
    return list(seen.values())


def get_bot_from_dau(loai_dau):
    """Suy item bột nền + BOM T1 từ loại đỗ (BTP-Bot có loai_dau là RM).

    Trả (item_bot, bom_name). Không tìm được -> throw rõ ràng.
    """
    bot_items = frappe.get_all(
        "Item", filters={"custom_sx_nhom": "BTP-Bot", "disabled": 0}, pluck="name"
    )
    for bot in bot_items:
        bom = get_bom_active(bot)
        if not bom:
            continue
        dau, _qty = _dau_rm_cua_bom(bom)
        if dau == loai_dau:
            return bot, bom
    frappe.throw(
        _("Không tìm thấy BOM bột nền (nhóm BTP-Bot) dùng đỗ {0} làm nguyên liệu. "
          "Kiểm tra lại BOM tầng 1 trên Desk.").format(loai_dau)
    )


def get_yield_bot(bom_name, dau_item):
    """kg bột ra / kg đỗ vào = bom.quantity / (stock_qty đỗ trong BOM). D7."""
    bom = frappe.get_cached_doc("BOM", bom_name)
    dau_qty = 0.0
    for r in bom.items:
        if r.item_code == dau_item:
            dau_qty += flt(r.stock_qty)
    if not dau_qty:
        frappe.throw(_("BOM {0} không có dòng đỗ {1}").format(bom_name, dau_item))
    return flt(bom.quantity) / dau_qty


# ───────────────────────────────────── đơn giá vào hộp ──


# Field chứa đơn giá trên Activity Type — ưu tiên custom (đặt riêng cho lương khoán)
# rồi mới tới field chuẩn ERPNext. Ghi đè được bằng SX Settings.field_don_gia_activity.
_FIELD_DON_GIA_ACTIVITY = (
    "custom_don_gia", "don_gia", "custom_rate", "custom_billing_rate",
    "billing_rate", "costing_rate", "rate",
)


def get_activity_type(san_pham):
    """Loại công việc khoán (Activity Type) của 1 SKU — map qua Item.custom_activity_type.

    Activity Type là LOẠI CÔNG VIỆC (vd "Vào hộp 300"), nhiều SKU cùng quy cách dùng
    chung một loại (TX300, SR300, TH300 → "Vào hộp 300").
    """
    act = frappe.db.get_value("Item", san_pham, "custom_activity_type")
    if not act:
        frappe.throw(
            _("Sản phẩm {0} chưa gán loại công việc khoán. Mở Item {0} trên Desk, điền "
              "'Loại công việc khoán' (Activity Type) rồi nhập lại.").format(san_pham)
        )
    return act


def get_don_gia_activity(activity_type, bat_buoc=True):
    """Đơn giá khoán/đơn vị lấy TỪ Activity Type (nguồn giá duy nhất).

    Tên field cấu hình được ở SX Settings; để trống thì tự dò theo thứ tự ứng viên.
    Cho phép giá 0 (công việc không tính lương sản phẩm).

    `bat_buoc=False` -> trả None thay vì throw (dùng khi liệt kê danh mục: throw dù
    có bọc try/except vẫn nhét message vào message_log và bắn popup lên portal).
    """
    field = (get_settings().get("field_don_gia_activity") or "").strip()
    meta = frappe.get_meta("Activity Type")
    if field:
        # Cấu hình tay: dùng ĐÚNG field đó, kể cả giá 0
        if meta.has_field(field):
            return flt(frappe.db.get_value("Activity Type", activity_type, field))
    else:
        # Tự dò: Activity Type chuẩn v16 có CẢ costing_rate lẫn billing_rate, thường
        # chỉ 1 cái được điền -> lấy giá trị KHÁC 0 đầu tiên, tránh vớ phải field rỗng.
        co_field = False
        for fn in _FIELD_DON_GIA_ACTIVITY:
            if meta.has_field(fn):
                co_field = True
                gia = flt(frappe.db.get_value("Activity Type", activity_type, fn))
                if gia:
                    return gia
        if co_field:
            return 0.0  # mọi field giá đều 0 -> công việc không tính lương sản phẩm
    if not bat_buoc:
        return None
    frappe.throw(
        _("Không đọc được đơn giá trên Activity Type {0}. Điền 'Field đơn giá trên "
          "Activity Type' trong SX Settings (các field hiện có: {1}).").format(
            activity_type,
            ", ".join(sorted(df.fieldname for df in meta.fields if df.fieldname)),
        )
    )


# ───────────────────────────────────── sinh mã lô ──


def dat_ten_hien_thi(nhan_vien):
    """Gán 'ten_hien_thi' NGẮN NHẤT mà không trùng, cho grid vào hộp.

    Nấc 1: chỉ TÊN            -> "Nga"
    Nấc 2: trùng tên -> + HỌ  -> "Nga Trương", "Nga Nguyễn"
    Nấc 3: vẫn trùng -> + tên đệm viết tắt -> "Nga Trương T."
    Nấc 4: cùng lắm -> tên đầy đủ.
    Sửa tại chỗ list dict (cần key employee_name, name) và trả lại chính nó.
    """

    def _tach(fullname):
        phan = [p for p in (fullname or "").split() if p]
        if not phan:
            return "", "", []
        return phan[-1], (phan[0] if len(phan) > 1 else ""), phan[1:-1]

    for nv in nhan_vien:
        nv["_ten"], nv["_ho"], nv["_dem"] = _tach(nv.get("employee_name"))
        nv["ten_hien_thi"] = nv["_ten"] or nv.get("employee_name") or nv.get("name")

    for nac in (2, 3, 4):
        nhom = {}
        for nv in nhan_vien:
            nhom.setdefault(nv["ten_hien_thi"], []).append(nv)
        for ds in nhom.values():
            if len(ds) < 2:
                continue
            for nv in ds:
                if nac == 2 and nv["_ho"]:
                    nv["ten_hien_thi"] = f"{nv['_ten']} {nv['_ho']}"
                elif nac == 3 and nv["_dem"]:
                    tat = "".join(d[0].upper() + "." for d in nv["_dem"])
                    nv["ten_hien_thi"] = f"{nv['_ten']} {nv['_ho']} {tat}".strip()
                elif nac == 4:
                    nv["ten_hien_thi"] = nv.get("employee_name") or nv.get("name")

    for nv in nhan_vien:
        for k in ("_ten", "_ho", "_dem"):
            nv.pop(k, None)
    return nhan_vien


def _unique_suffix(goc, exists_fn):
    ma, dem = goc, 1
    while exists_fn(ma):
        dem += 1
        ma = f"{goc}-{dem}"
    return ma


def sinh_lo_rang(loai_dau, ngay_rang):
    """Mã lô rang `{prefix}-DDMMYY(ngay_rang)`. Unique.

    Prefix lấy từ Item BỘT NỀN tương ứng (R / RD) — đúng ngữ nghĩa: batch bột nền
    CHÍNH LÀ mã lô rang (D13), nên prefix thuộc về item bột, không phải item đỗ.
    Fallback prefix trên item đỗ nếu site có tự đặt.
    """
    prefix = None
    try:
        item_bot, _bom = get_bot_from_dau(loai_dau)
        prefix = frappe.db.get_value("Item", item_bot, "custom_batch_prefix")
    except Exception:
        prefix = None
    if not prefix:
        prefix = frappe.db.get_value("Item", loai_dau, "custom_batch_prefix")
    if not prefix:
        frappe.throw(
            _("Chưa có prefix mã lô rang cho đỗ {0}. Đặt custom_batch_prefix (vd R / RD) "
              "trên Item bột nền tương ứng — hoặc trên chính Item đỗ.").format(loai_dau)
        )
    goc = f"{prefix}-{getdate(ngay_rang).strftime('%d%m%y')}"
    return _unique_suffix(
        goc,
        lambda ma: frappe.db.exists("SX Xuat Dau", {"lo_rang": ma, "docstatus": ("<", 2)})
        or frappe.db.exists("Batch", ma),
    )


def sinh_ma_lo(item_code, ngay):
    """Batch `{Item.custom_batch_prefix}-DDMMYY`; trùng -> -2, -3 (D13)."""
    prefix = frappe.db.get_value("Item", item_code, "custom_batch_prefix")
    if not prefix:
        frappe.throw(_("Item {0} chưa có custom_batch_prefix để sinh mã lô").format(item_code))
    goc = f"{prefix}-{getdate(ngay).strftime('%d%m%y')}"
    return _unique_suffix(goc, lambda ma: frappe.db.exists("Batch", ma))


# ───────────────────────────────────── topo sort theo BOM ──


def topo_rank_by_bom(item_codes):
    """Xếp hạng topo: item A là RM trong BOM(B) -> A đứng trước B.

    (màu → đường hoán → bột bánh/bột đậu). Trả dict {item: rank}; rank nhỏ = sinh trước.
    Có chu trình / không phụ thuộc -> giữ thứ tự ổn định.
    """
    items = list(dict.fromkeys(item_codes))  # dedupe giữ thứ tự
    tap = set(items)
    # edge A -> B nếu A là RM trong BOM active của B
    phu_thuoc = {b: set() for b in items}  # b phụ thuộc các item trong set (phải sinh trước)
    for b in items:
        bom = get_bom_active(b)
        if not bom:
            continue
        bom_doc = frappe.get_cached_doc("BOM", bom)
        for r in bom_doc.items:
            if r.item_code in tap and r.item_code != b:
                phu_thuoc[b].add(r.item_code)

    rank = {}
    dang_xu_ly = set()

    def _rank(item):
        if item in rank:
            return rank[item]
        if item in dang_xu_ly:
            return 0  # chặn chu trình
        dang_xu_ly.add(item)
        deps = phu_thuoc.get(item, set())
        r = 0 if not deps else max(_rank(d) for d in deps) + 1
        dang_xu_ly.discard(item)
        rank[item] = r
        return r

    for it in items:
        _rank(it)
    return rank


# ───────────────────────────────────── công đoạn tầng 1 (D31) ──

# Luồng sản xuất tầng 1 theo lưu đồ: đỗ (kho NVL) → xuất ra xưởng → luộc+rang →
# ĐỖ Ủ → tách vỏ → ĐỖ VỠ → nghiền → BỘT NỀN (kho BTP).
# Mỗi công đoạn là 1 Stock Entry Repack với kg ra do QC cân thật (không có định mức
# cố định để dựng BOM — hao hụt từng mẻ khác nhau).
CONG_DOAN = [
    {"ma": "rang", "ten": "Luộc + rang", "vao": "dau", "ra": "u"},
    {"ma": "tachvo", "ten": "Tách vỏ", "vao": "u", "ra": "vo"},
    {"ma": "nghien", "ten": "Nghiền bột", "vao": "vo", "ra": "bot"},
]

_HAU_TO_ITEM = {"u": "ủ", "vo": "vỡ"}
_HAU_TO_BATCH = {"u": "U", "vo": "V"}


def ten_btp_dau(loai_dau, chang):
    """Tên item BTP của 1 chặng: 'Đỗ xanh' + 'ủ' -> 'Đỗ xanh ủ' (D31)."""
    hau_to = _HAU_TO_ITEM.get(chang)
    if not hau_to:
        frappe.throw(_("Chặng {0} không có item trung gian.").format(chang))
    return f"{loai_dau} {hau_to}"


def item_cua_chang(loai_dau, chang):
    """Item ứng với 1 chặng của luồng. Thiếu item BTP -> chỉ rõ cách tạo."""
    if chang == "dau":
        return loai_dau
    if chang == "bot":
        return get_bot_from_dau(loai_dau)[0]
    ten = ten_btp_dau(loai_dau, chang)
    if not frappe.db.exists("Item", ten):
        frappe.throw(
            _("Chưa có Item bán thành phẩm '{0}'. Chạy trên site: "
              "<b>bench --site &lt;site&gt; execute sx.seed.seed_btp_dau</b> "
              "(tạo Đỗ ủ / Đỗ vỡ cho mọi loại đỗ).").format(ten)
        )
    return ten


def batch_cua_chang(lo_rang, chang):
    """Batch id của 1 chặng. Batch trong Frappe là DUY NHẤT toàn hệ thống nên
    item trung gian phải có hậu tố riêng; vẫn nhìn ra ngay thuộc lô R nào."""
    if chang == "bot":
        return lo_rang           # giữ nguyên quy ước cũ: batch bột nền = lô R (D13)
    hau_to = _HAU_TO_BATCH.get(chang)
    return f"{lo_rang}-{hau_to}" if hau_to else None


def kho_xuong(settings=None):
    """Kho giữ BTP đang dở dang ngoài xưởng; chưa cấu hình thì dùng Kho BTP."""
    settings = settings or get_settings()
    return settings.get("kho_xuong") or settings.get("kho_btp")


def cho_phep_ton_am():
    """Site có bật Stock Settings → 'Allow Negative Stock' không.

    Bật = chủ site CHẤP NHẬN cho kho âm (thường để chạy thử khi chưa nhập tồn đầu).
    Khi đó mọi chốt chặn "thiếu tồn" của app hạ xuống thành CẢNH BÁO — chặn tiếp
    là vô nghĩa vì ERPNext bên dưới đã cho ghi âm rồi.
    """
    return cint(frappe.db.get_single_value("Stock Settings", "allow_negative_stock"))


# ─────────────────────────────────────────── THÀNH PHẨM: ai là TP ──
#
# Có HAI cách đánh dấu, và cả hai đều tính:
#   1. SX Settings → "Nhóm hàng là thành phẩm": chọn Item Group, cả nhánh con tính
#      theo. Chọn một lần cho cả trăm Item.
#   2. Item → "Nhóm SX" (custom_sx_nhom) = TP: đánh dấu lẻ từng Item.
#
# Cách 1 sinh ra ở D64 vì cách 2 bắt chủ site vào sửa TỪNG Item — với vài chục SKU
# thì đó là buổi chiều ngồi bấm, và bấm sót một cái là nó biến mất khỏi màn nhập kho
# mà không ai biết vì sao. Giữ cả cách 2 vì nó vẫn đúng khi một Item nằm lạc nhóm.


def nhom_tp():
    """Danh sách Item Group được coi là thành phẩm, ĐÃ bung cả nhánh con.

    Bung nhánh con để chọn nhóm cha là xong: cây Item Group của ERPNext thường có
    "Thành phẩm > Bánh > ...", chọn "Thành phẩm" mà không lấy nhánh dưới thì gần như
    không khớp Item nào.
    """
    settings = get_settings()
    goc = [r.item_group for r in (settings.get("nhom_tp") or []) if r.item_group]
    if not goc:
        return []
    ra = list(goc)
    for g in goc:
        try:
            ra += frappe.get_all(
                "Item Group",
                filters={"lft": (">", frappe.db.get_value("Item Group", g, "lft")),
                         "rgt": ("<", frappe.db.get_value("Item Group", g, "rgt"))},
                pluck="name",
            )
        except Exception:
            pass   # cây nested set hỏng -> vẫn dùng được đúng nhóm đã chọn
    return list(dict.fromkeys(ra))


def items_tp(fields=None, filters=None):
    """Mọi Item được coi là thành phẩm. `fields` mặc định [name, item_name, stock_uom].

    Một chỗ duy nhất trả lời câu "cái gì là thành phẩm" — trước D64 câu này được
    viết lại ở 4 nơi, nên thêm cách đánh dấu thứ hai là phải sửa cả 4.
    """
    fields = fields or ["name", "item_name", "stock_uom"]
    loc = {"disabled": 0}
    loc.update(filters or {})
    nhom = nhom_tp()
    if not nhom:
        loc["custom_sx_nhom"] = "TP"
        return frappe.get_all("Item", filters=loc, fields=fields, order_by="item_name")
    return frappe.get_all(
        "Item", filters=loc,
        or_filters=[["custom_sx_nhom", "=", "TP"], ["item_group", "in", nhom]],
        fields=fields, order_by="item_name",
    )


# ─────────────────────────────────────── ĐƠN GIÁ KHOÁN THEO THÁNG (D67) ──


def bang_don_gia(ngay):
    """Tên bảng đơn giá ĐANG ÁP DỤNG cho một ngày. Không có -> None."""
    d = getdate(ngay)
    return frappe.db.get_value(
        "SX Bang Don Gia", {"thang": d.month, "nam": d.year, "docstatus": 1}, "name")


def don_gia_theo_thang(ngay):
    """{(san_pham, cach_lam): don_gia} của tháng chứa `ngay`.

    Đọc MỘT LẦN cho cả bảng rồi tra trong bộ nhớ: bảng vào hộp có hàng trăm dòng,
    mỗi dòng một truy vấn là bốn trăm truy vấn cho một lần lưu.
    Dòng để trống cách làm nằm dưới khoá `(san_pham, "")` — giá chung.
    """
    ten = bang_don_gia(ngay)
    if not ten:
        return {}
    return {
        (r.san_pham, r.cach_lam or ""): flt(r.don_gia)
        for r in frappe.get_all(
            "SX Bang Don Gia Item", filters={"parent": ten, "parenttype": "SX Bang Don Gia"},
            fields=["san_pham", "cach_lam", "don_gia"],
        )
    }


def tra_don_gia(bang, san_pham, cach_lam=None):
    """Tra đơn giá trong bảng đã đọc. Ưu tiên đúng cách làm, không có thì giá chung.

    Trả None khi không tra được — nơi gọi phải quyết định báo lỗi thế nào, vì câu
    báo lỗi ở bảng vào hộp khác câu ở màn quản lý.
    """
    if cach_lam and (san_pham, cach_lam) in bang:
        return bang[(san_pham, cach_lam)]
    if (san_pham, "") in bang:
        return bang[(san_pham, "")]
    return None


def cach_lam_cua(bang, san_pham):
    """Các cách làm khai giá cho một mã hàng, trong bảng đã đọc.

    Trả [] nghĩa là mã đó chỉ có giá chung — màn nhập liệu khỏi hỏi thêm bước nào.
    """
    return sorted({cl for (sp, cl) in bang if sp == san_pham and cl})
