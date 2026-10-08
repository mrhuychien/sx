"""Hàm dùng chung app sx (v3).

Nguồn sự thật đơn: yield + danh mục đỗ suy từ BOM; prefix mã lô từ Item; không
cấu hình trùng lặp. FIFO toàn tuyến — không ai chọn lô (D5).
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate


def get_settings():
    """SX Settings (Single)."""
    return frappe.get_cached_doc("SX Settings")


# ───────────────────────────── nhớ tạm trong MỘT request (D120) ──
#
# Các màn tải trang gọi get_bom_active / items_tp / get_bot_from_dau trong VÒNG LẶP
# — mỗi lần một truy vấn, 80–1000 truy vấn cho một lần mở màn. Nhớ trong
# frappe.local: hết request là mất, không bao giờ trả số cũ của lần mở trước.
# BOM / Item đổi GIỮA request (hiếm: submit BOM rồi đọc lại) thì hook xoa_nho xoá.


def nho(ten):
    """dict nhớ tạm tên `ten` của request hiện tại. Không có frappe.local (test
    giả) thì trả dict mới mỗi lần — tức là không nhớ, hành vi y như cũ."""
    loc = getattr(frappe, "local", None)
    if loc is None:
        return {}
    try:
        d = loc.sx_nho
    except AttributeError:
        d = {}
        try:
            loc.sx_nho = d
        except Exception:
            return {}
    return d.setdefault(ten, {})


def xoa_nho(doc=None, method=None):
    """Hook BOM / Item: dữ liệu vừa đổi -> bỏ mọi thứ đã nhớ trong request này."""
    loc = getattr(frappe, "local", None)
    if loc is not None and getattr(loc, "sx_nho", None):
        loc.sx_nho = {}


def get_bom_active(item_code):
    """BOM active/default (docstatus 1) của 1 item, hoặc None. Nhớ theo request."""
    m = nho("bom")
    if item_code in m:
        return m[item_code]
    m[item_code] = frappe.db.get_value(
        "BOM",
        {"item": item_code, "is_active": 1, "is_default": 1, "docstatus": 1},
        "name",
    )
    return m[item_code]


def nap_bom(items):
    """Nạp BOM active của CẢ danh sách bằng MỘT truy vấn vào bộ nhớ request — gọi
    trước vòng lặp có get_bom_active. Trả {item: bom | None}."""
    m = nho("bom")
    thieu = [i for i in dict.fromkeys(items or []) if i and i not in m]
    if thieu:
        co = {b.item: b.name for b in frappe.get_all(
            "BOM", filters={"item": ("in", thieu), "is_active": 1, "is_default": 1,
                            "docstatus": 1},
            fields=["item", "name"])}
        for i in thieu:
            m[i] = co.get(i)
    return {i: m.get(i) for i in (items or [])}


def ton_bin(items, kho):
    """{item: actual_qty} tại MỘT kho cho cả danh sách — một truy vấn thay vì
    một get_value Bin cho mỗi mã."""
    items = [i for i in dict.fromkeys(items or []) if i]
    if not items or not kho:
        return {}
    return {b.item_code: flt(b.actual_qty) for b in frappe.get_all(
        "Bin", filters={"item_code": ("in", items), "warehouse": kho},
        fields=["item_code", "actual_qty"])}


def ton_cac_lo(batches):
    """{(batch, kho): số tồn} cho cả danh sách lô — MỘT truy vấn thay cho
    get_batch_qty từng lô (mỗi lần là một lượt quét sổ cái).

    ERPNext v15+ ghi lô trong Serial and Batch Bundle; SLE có thể để trống batch_no.
    Gom cả hai đường, số lượng lấy theo dòng của đúng lô trong bundle.
    """
    batches = [b for b in dict.fromkeys(batches or []) if b]
    if not batches:
        return {}
    rows = frappe.db.sql(
        """select coalesce(e.batch_no, sle.batch_no) as b, sle.warehouse as w,
                  sum(coalesce(e.qty, sle.actual_qty)) as q
             from `tabStock Ledger Entry` sle
             left join `tabSerial and Batch Entry` e
               on e.parent = sle.serial_and_batch_bundle
            where sle.is_cancelled = 0
              and (sle.batch_no in %(b)s or e.batch_no in %(b)s)
            group by coalesce(e.batch_no, sle.batch_no), sle.warehouse""",
        {"b": tuple(batches)}, as_dict=True)
    tap = set(batches)
    return {(r.b, r.w): flt(r.q) for r in rows if r.b in tap}


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
    nap_bom(bot_items)
    for bot in bot_items:
        bom = get_bom_active(bot)
        if not bom:
            continue
        dau, _qty = _dau_rm_cua_bom(bom)
        if dau and dau not in seen:
            seen[dau] = {
                "name": dau,
                "item_name": frappe.get_cached_value("Item", dau, "item_name") or dau,
                "prefix": frappe.get_cached_value("Item", dau, "custom_batch_prefix") or dau,
            }
    return list(seen.values())


def get_bot_from_dau(loai_dau):
    """Suy item bột nền + BOM T1 từ loại đỗ (BTP-Bot có loai_dau là RM).

    Trả (item_bot, bom_name). Không tìm được -> throw rõ ràng. Nhớ theo request
    (lưu đồ gọi 2 lần cho MỖI lô — D120).
    """
    m = nho("bot_tu_dau")
    if loai_dau in m:
        return m[loai_dau]
    bot_items = frappe.get_all(
        "Item", filters={"custom_sx_nhom": "BTP-Bot", "disabled": 0}, pluck="name"
    )
    nap_bom(bot_items)
    for bot in bot_items:
        bom = get_bom_active(bot)
        if not bom:
            continue
        dau, _qty = _dau_rm_cua_bom(bom)
        if dau == loai_dau:
            m[loai_dau] = (bot, bom)
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


PREFIX_TOI_DA = 10      # mã lô được chép tay ra thẻ — dài hơn là chép sai


def _khong_dau(s):
    import unicodedata
    s = str(s or "").replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def rut_gon_ma(ma):
    """Mã hàng → prefix NGẮN để chép tay (D103). Hàm thuần.

    Mã đã ngắn, không dấu, không khoảng trắng (TP-SEN, BDS) thì giữ nguyên. Còn lại:
    bỏ dấu, lấy CHỮ ĐẦU mỗi từ và giữ nguyên cụm có SỐ (300g, 40g) vì đó thường là
    thứ phân biệt hai quy cách của cùng một vị:
        "Bánh đậu xanh sen 300g"  → BDXS300G
        "Chè đậu đen cốt dừa"     → CDDCD
        "Lạc"                     → LAC
    """
    import re
    ma = str(ma or "").strip()
    if ma and len(ma) <= PREFIX_TOI_DA and ma.isascii() and " " not in ma:
        return ma
    tu = [t for t in re.split(r"[^0-9A-Za-z]+", _khong_dau(ma).upper()) if t]
    if not tu:
        return ma[:PREFIX_TOI_DA]
    if len(tu) == 1:
        return tu[0][:PREFIX_TOI_DA]
    ra = "".join(t if any(c.isdigit() for c in t) else t[0] for t in tu)
    return ra[:PREFIX_TOI_DA]


def prefix_lo(item_code):
    """Prefix mã lô: `custom_batch_prefix` nếu có; không thì RÚT GỌN mã hàng và LƯU
    lại vào Item (D102/D103).

    Lưu lại vì hai lý do: lần sau ra cùng một prefix dù ai đổi quy tắc rút gọn, và
    người dùng thấy nó trên Desk để sửa nếu muốn. Hai mã rút gọn trùng nhau
    (Bột đậu sữa / Bánh đậu sen…) thì mã sau thêm số 2, 3 — hai mặt hàng chung một
    đầu mã lô là tự gây nhầm lô.
    """
    prefix = (frappe.db.get_value("Item", item_code, "custom_batch_prefix") or "").strip()
    if prefix:
        return prefix
    goc = rut_gon_ma(item_code) or str(item_code)
    prefix, n = goc, 1
    while frappe.db.exists("Item", {"custom_batch_prefix": prefix, "name": ("!=", item_code)}):
        n += 1
        prefix = f"{goc[:PREFIX_TOI_DA - len(str(n))]}{n}"
    frappe.db.set_value("Item", item_code, "custom_batch_prefix", prefix,
                        update_modified=False)
    return prefix


def sinh_lo_rang(loai_dau, ngay_rang):
    """Mã lô rang `{prefix}-DDMMYY(ngay_rang)`. Unique.

    Prefix lấy từ Item BỘT NỀN tương ứng (R / RD) — đúng ngữ nghĩa: batch bột nền
    CHÍNH LÀ mã lô rang (D13), nên prefix thuộc về item bột, không phải item đỗ.
    Fallback prefix trên item đỗ nếu site có tự đặt.
    """
    item_bot = None
    try:
        item_bot, _bom = get_bot_from_dau(loai_dau)
    except Exception:
        item_bot = None
    prefix = (frappe.db.get_value("Item", item_bot, "custom_batch_prefix")
              if item_bot else None)
    if not prefix:
        prefix = frappe.db.get_value("Item", loai_dau, "custom_batch_prefix")
    if not prefix:
        # D102: không ai điền prefix thì rút gọn mã item bột nền (đúng ngữ nghĩa:
        # batch bột nền là mã lô rang), không có bột nền thì mã item đỗ.
        prefix = prefix_lo(item_bot or loai_dau)
    goc = f"{prefix}-{getdate(ngay_rang).strftime('%d%m%y')}"
    return _unique_suffix(
        goc,
        lambda ma: frappe.db.exists("SX Xuat Dau", {"lo_rang": ma, "docstatus": ("<", 2)})
        or frappe.db.exists("Batch", ma),
    )


def sinh_ma_lo(item_code, ngay):
    """Batch `{prefix}-DDMMYY`; trùng -> -2, -3 (D13). Prefix: xem prefix_lo (D102).

    Lô đã có nhưng CHƯA DÙNG (của chính mã này, mọi giao dịch đã huỷ) thì dùng lại
    (D104): huỷ phiếu nhập rồi duyệt lại trong ngày phải ra đúng SEN-290926, không
    phải SEN-290926-2 — mã lô ghi trên thẻ hàng là cái đầu tiên.
    """
    goc = f"{prefix_lo(item_code)}-{getdate(ngay).strftime('%d%m%y')}"
    return _unique_suffix(
        goc, lambda ma: frappe.db.exists("Batch", ma) and not lo_chua_dung(ma, item_code))


def ma_lo_hsd(item_code, hsd):
    """Mã lô THÀNH PHẨM theo HSD (W05, D131): mỗi (sản phẩm, HSD) đúng MỘT lô.

    `{prefix}-HSD{DDMMYY}`. Cùng mã + cùng HSD (nhập hai phiếu, hai ngày khác nhau)
    là CÙNG lô — người cầm hộp chỉ có HSD in trên hộp, truy xuất theo đúng thứ đó.
    Người dùng không thấy mã này (W05: ẩn mã lô) — chỉ thấy sản phẩm + HSD. Trùng mã
    của mặt hàng KHÁC (hai prefix trùng) thì thêm -2, -3.
    """
    goc = f"{prefix_lo(item_code)}-HSD{getdate(hsd).strftime('%d%m%y')}"
    return _unique_suffix(goc, lambda ma: frappe.db.exists("Batch", ma)
                          and frappe.db.get_value("Batch", ma, "item") != item_code)


def la_lo_hsd(batch):
    """Lô thành phẩm sinh theo HSD (từ D131) — NSX của nó là ngày vào hộp thật."""
    return "-HSD" in str(batch or "")


def lo_chua_dung(ma, item_code):
    """Batch `ma` của `item_code` và không còn giao dịch kho nào còn hiệu lực."""
    if frappe.db.get_value("Batch", ma, "item") != item_code:
        return False
    if frappe.db.exists("Stock Ledger Entry", {"batch_no": ma, "is_cancelled": 0}):
        return False
    # ERPNext v15+ ghi lô trong Serial and Batch Bundle, SLE có thể để trống batch_no.
    try:
        dung = frappe.db.sql(
            """select 1 from `tabSerial and Batch Entry` e
                 join `tabSerial and Batch Bundle` b on b.name = e.parent
                where e.batch_no = %s and b.docstatus = 1
                  and ifnull(b.is_cancelled, 0) = 0 limit 1""", (ma,))
    except Exception:
        return False          # không chắc thì coi như đã dùng — sinh mã mới cho an toàn
    return not dung


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
              "<b>bench --site &lt;site&gt; execute sx.seed.seed_btp_dau "
              "--kwargs \"{{'dry_run': 0}}\"</b> (tạo Đỗ ủ / Đỗ vỡ cho mọi loại đỗ). "
              "Gọi trần chỉ XEM TRƯỚC, không tạo gì.").format(ten)
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
    m = nho("nhom_tp")
    if "x" in m:
        return list(m["x"])
    settings = get_settings()
    goc = [r.item_group for r in (settings.get("nhom_tp") or []) if r.item_group]
    if not goc:
        m["x"] = []
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
    m["x"] = list(dict.fromkeys(ra))
    return list(m["x"])


def items_tp(fields=None, filters=None):
    """Mọi Item được coi là thành phẩm. `fields` mặc định [name, item_name, stock_uom].

    Một chỗ duy nhất trả lời câu "cái gì là thành phẩm" — trước D64 câu này được
    viết lại ở 4 nơi, nên thêm cách đánh dấu thứ hai là phải sửa cả 4.
    """
    fields = fields or ["name", "item_name", "stock_uom"]
    # Nhớ theo request (D120): get_boot gọi 3 lần, luu_do_btp/truy xuất gọi lại nữa.
    m = nho("items_tp")
    khoa = (tuple(fields), repr(sorted((filters or {}).items())))
    if khoa in m:
        return [frappe._dict(x) for x in m[khoa]]
    loc = {"disabled": 0}
    loc.update(filters or {})
    nhom = nhom_tp()
    if not nhom:
        loc["custom_sx_nhom"] = "TP"
        ra = frappe.get_all("Item", filters=loc, fields=fields, order_by="item_name")
    else:
        ra = frappe.get_all(
            "Item", filters=loc,
            or_filters=[["custom_sx_nhom", "=", "TP"], ["item_group", "in", nhom]],
            fields=fields, order_by="item_name",
        )
    m[khoa] = ra
    return [frappe._dict(x) for x in ra]


# ─────────────────────────── HẠN SỬ DỤNG THEO BỘ TỰ CÔNG BỐ (W28 / D127) ──
#
# Hạn dùng khai theo THÁNG trên sản phẩm tự công bố (bánh 9, bột và chè 12), mã hàng
# gắn về sản phẩm qua Item.custom_sp_cong_bo. Mã chưa gắn thì rơi về "Shelf Life In
# Days" của Item như trước D127 — không đoán số tháng cho mã không ai khai.

TRUONG_CONG_BO = ["name", "so_cong_bo", "ten_san_pham", "loai", "tccs", "han_dung_thang",
                  "quy_cach", "co_lac", "co_sua_bot", "co_dua", "ngung_san_xuat"]


def nap_cong_bo(items):
    """{item: dict sản phẩm tự công bố | None} — HAI truy vấn cho cả danh sách, nhớ
    theo request. Site chưa migrate (chưa có field / DocType) thì coi như chưa gắn."""
    m = nho("cong_bo")
    thieu = [i for i in dict.fromkeys(items or []) if i and i not in m]
    if thieu:
        for i in thieu:
            m[i] = None
        try:
            gan = {r.name: r.custom_sp_cong_bo for r in frappe.get_all(
                "Item", filters={"name": ("in", thieu), "custom_sp_cong_bo": ("is", "set")},
                fields=["name", "custom_sp_cong_bo"]) if r.get("custom_sp_cong_bo")}
            sp = {r.name: dict(r) for r in frappe.get_all(
                "SX San Pham Cong Bo", filters={"name": ("in", list(set(gan.values())))},
                fields=TRUONG_CONG_BO)} if gan else {}
        except Exception:
            gan, sp = {}, {}
        for i, ten in gan.items():
            m[i] = sp.get(ten)
    return {i: m.get(i) for i in (items or [])}


def cong_bo_cua(item):
    """Sản phẩm tự công bố của một mã hàng (dict) hoặc None."""
    return nap_cong_bo([item]).get(item) if item else None


def han_dung(item, shelf_life=None):
    """("thang", n) theo bộ tự công bố; mã chưa gắn thì ("ngay", Shelf Life In Days);
    không có gì thì None — nơi gọi bắt người ta nhập HSD theo bao bì.

    `shelf_life` = số ngày đã đọc sẵn (danh mục đọc cả loạt) — khỏi tra lại từng mã."""
    cb = cong_bo_cua(item)
    if cb and cint(cb.get("han_dung_thang")) > 0:
        return ("thang", cint(cb["han_dung_thang"]))
    if shelf_life is None:
        shelf_life = frappe.get_cached_value("Item", item, "shelf_life_in_days") if item else 0
    so = cint(shelf_life)
    return ("ngay", so) if so > 0 else None


def hsd_tu_nsx(item, nsx):
    """HSD = NSX + hạn dùng (tháng theo lịch, hoặc ngày). None khi chưa khai hạn dùng."""
    from frappe.utils import add_days, add_months

    h = han_dung(item)
    if not h or not nsx:
        return None
    d = getdate(nsx)
    return str(add_months(d, h[1]) if h[0] == "thang" else add_days(d, h[1]))


def nsx_tu_hsd(item, hsd):
    """NSX = HSD − hạn dùng (W05): lô thành phẩm sinh theo HSD in trên hộp, NSX suy
    ngược ra chứ không lấy ngày nhập kho. None khi chưa khai hạn dùng."""
    from frappe.utils import add_days, add_months

    h = han_dung(item)
    if not h or not hsd:
        return None
    d = getdate(hsd)
    return str(add_months(d, -h[1]) if h[0] == "thang" else add_days(d, -h[1]))


# ─────────────────────────────────────── ĐƠN GIÁ KHOÁN THEO THÁNG (D67) ──


def bang_don_gia(ngay=None):
    """Tên bảng đơn giá ÁP DỤNG cho một ngày. Không có bảng nào -> None.

    Bảng có hiệu lực gần nhất TRƯỚC (hoặc đúng) ngày đó. Không có bảng nào hiệu lực
    trước ngày đó thì lấy bảng SỚM NHẤT: xưởng lập bảng đầu tiên hôm nay rồi chấm
    bù cho hôm qua là chuyện bình thường, mà để rơi về "không có giá" thì tiền công
    hôm qua ra 0 — im lặng và sai.

    docstatus < 2 chứ không phải = 1: từ D80 bảng không còn submit, bảng mới nằm ở
    docstatus 0 còn bảng cũ lập trước D80 vẫn đang ở docstatus 1.
    """
    d = getdate(ngay or nowdate())
    m = nho("bang_don_gia")          # D120: sổ nợ giá gọi lại cho từng ngày
    if str(d) in m:
        return m[str(d)]
    ten = frappe.db.get_value(
        "SX Bang Don Gia",
        {"hieu_luc_tu": ("<=", d), "docstatus": ("<", 2)},
        "name", order_by="hieu_luc_tu desc",
    )
    if not ten:
        ten = frappe.db.get_value(
            "SX Bang Don Gia", {"docstatus": ("<", 2)}, "name", order_by="hieu_luc_tu asc")
    m[str(d)] = ten
    return ten


def don_gia_ap_dung(ngay=None):
    """{(san_pham, cach_lam): don_gia} của bảng áp dụng cho `ngay`.

    Đọc MỘT LẦN cho cả bảng rồi tra trong bộ nhớ: bảng vào hộp có hàng trăm dòng,
    mỗi dòng một truy vấn là bốn trăm truy vấn cho một lần lưu.
    Dòng để trống cách làm nằm dưới khoá `(san_pham, "")` — giá chung.
    """
    ten = bang_don_gia(ngay)
    if not ten:
        return {}
    m = nho("don_gia")               # D120: nhiều ngày chung một bảng
    if ten not in m:
        m[ten] = {
            (r.san_pham, r.cach_lam or ""): flt(r.don_gia)
            for r in frappe.get_all(
                "SX Bang Don Gia Item", filters={"parent": ten, "parenttype": "SX Bang Don Gia"},
                fields=["san_pham", "cach_lam", "don_gia"],
            )
        }
    return dict(m[ten])


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
