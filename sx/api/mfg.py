"""Helper Manufacture dùng chung (tang1 T1 + chot T2/T3).

Đọc từ source ERPNext v16 thật: make_stock_entry, get_batch_qty,
make_bundle_using_old_serial_batch_fields. FIFO qua use_serial_batch_fields=1 +
batch_no (bundle tự sinh khi submit). Non-stock (Nước) tự loại khỏi SE.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

CONG_TAC_LO = "enable_serial_and_batch_no_for_item"


def bat_lo_he_thong():
    """Bật công tắc lô của ERPNext v16 (D126): Stock Settings → "Activate Serial / Batch
    No for Item". Tắt thì MỌI phiếu kho có lô hỏng với câu "Please check the 'Activate
    Serial and Batch No for Item' checkbox…" — mà app này quản lý bột / thành phẩm theo
    lô từ D5. Patch của ERPNext chỉ bật khi site ĐÃ có Batch lúc nâng cấp, nên site
    dựng mới (chưa có lô nào) đứng ở trạng thái tắt.

    Gọi lúc migrate và trước mỗi lần tạo lô / ghi kho có lô; nhớ theo request.
    """
    try:
        from sx.utils import nho

        m = nho("bat_lo")
        if "x" in m:
            return
        m["x"] = 1
        if not frappe.get_meta("Stock Settings").has_field(CONG_TAC_LO):
            return      # ERPNext cũ chưa có công tắc này
        if cint(frappe.db.get_single_value("Stock Settings", CONG_TAC_LO)):
            return
        frappe.db.set_single_value("Stock Settings", CONG_TAC_LO, 1)
        frappe.db.set_default(CONG_TAC_LO, 1)
    except Exception:
        # Không bật được thì để phiếu kho tự báo lỗi gốc — đừng chặn thêm ở đây.
        pass


def dam_bao_quan_ly_lo(item_code):
    """Item có quản lý lô chưa; chưa thì bật nếu còn bật được (D103).

    ERPNext từ chối tạo Batch cho Item tắt "Has Batch No" — báo "The selected item
    cannot have Batch", QC / thủ kho đọc không hiểu, và nhập kho kẹt. Mã thành phẩm
    mới tạo trên Desk thường quên tích ô này.

      · Item CHƯA có giao dịch kho nào → bật luôn has_batch_no (ERPNext cho đổi).
      · ĐÃ có giao dịch → ERPNext cấm đổi. Không chặn nhập kho vì chuyện đó: trả
        False, nơi gọi nhập KHÔNG có lô, và nói rõ ra để người quản lý biết mã
        này mất truy xuất theo lô.
    """
    bat_lo_he_thong()
    if frappe.get_cached_value("Item", item_code, "has_batch_no"):
        return True
    co_gd = frappe.db.exists("Stock Ledger Entry",
                             {"item_code": item_code, "is_cancelled": 0})
    if not co_gd:
        frappe.db.set_value("Item", item_code, "has_batch_no", 1, update_modified=False)
        try:
            frappe.clear_document_cache("Item", item_code)
        except Exception:
            pass
        return True
    frappe.msgprint(
        _("Mã {0} không quản lý theo lô và đã có giao dịch kho, nên ERPNext không cho "
          "bật lô nữa — lần này nhập KHÔNG có số lô (mất truy xuất ngày × lô cho mã "
          "này). Muốn có lô: tạo mã hàng mới có tích 'Has Batch No'.").format(item_code),
        title=_("Nhập không có lô"), indicator="orange")
    return False


def tao_batch(item_code, batch_id, ngay_sx=None, nsx=None, hsd=None):
    """Batch tạo trước SE thành phẩm; batch_id đặt tay (D13).

    `nsx` / `hsd` (D114) → Batch.manufacturing_date / expiry_date. Lô thành phẩm
    PHẢI có HSD: không có thì báo cáo cận date, xuất FEFO và tem lô đều trống.

    Trả None khi Item không thể có lô (xem dam_bao_quan_ly_lo) — nơi gọi chuyển
    batch None vào phiếu kho là nhập không lô.

    Idempotent: nếu Batch cùng batch_id đã tồn tại (vd huỷ + nhập lại lô R — batch
    bột nền dùng lại đúng lô R để giữ mắt xích truy xuất), tái dùng thay vì insert
    (tránh DuplicateEntryError). Khác item -> lỗi rõ ràng.
    """
    if not dam_bao_quan_ly_lo(item_code):
        return None
    if frappe.db.exists("Batch", batch_id):
        cu = frappe.db.get_value("Batch", batch_id, "item")
        if cu != item_code:
            frappe.throw(
                _("Batch {0} đã tồn tại cho item khác ({1}), không dùng cho {2} được.").format(
                    batch_id, cu, item_code
                )
            )
        if hsd:
            # Lô dùng lại (huỷ phiếu rồi duyệt lại — sinh_ma_lo chỉ trả lô CHƯA
            # DÙNG): HSD là của lần nhập này, không phải lần đã huỷ.
            moi = {"expiry_date": hsd}
            if nsx:
                moi["manufacturing_date"] = nsx
            cu_hsd, cu_nsx = frappe.db.get_value(
                "Batch", batch_id, ["expiry_date", "manufacturing_date"])
            if str(cu_hsd or "") != str(hsd) or (nsx and str(cu_nsx or "") != str(nsx)):
                frappe.db.set_value("Batch", batch_id, moi)
        return batch_id
    batch = frappe.get_doc(
        {
            "doctype": "Batch",
            "batch_id": batch_id,
            "item": item_code,
            "custom_ngay_sx": ngay_sx,
        }
    )
    if nsx:
        batch.manufacturing_date = nsx
    if hsd:
        batch.expiry_date = hsd
    batch.flags.ignore_permissions = True
    batch.insert()
    return batch.name


def gia_von_hien(item_code, kho=None):
    """Giá vốn ERPNext sẽ dùng khi XUẤT mã này, 0 = không tìm ra (D116).

    Đi đúng thứ tự dự phòng của ERPNext (stock_ledger.get_valuation_rate): giá vốn
    đang chạy ở kho → giá của lần nhập gần nhất có giá → Item.valuation_rate → giá mua
    trong Item Price. Hết cả bốn thì submit phiếu kho văng "Valuation Rate for the
    Item … is required" — tiếng Anh, từng mã một, và giữa chừng lần chốt.
    """
    if kho:
        g = flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": kho},
                                    "valuation_rate"))
        if g > 0:
            return g
    g = flt(frappe.db.get_value("Bin", {"item_code": item_code, "valuation_rate": (">", 0)},
                                "valuation_rate"))
    if g > 0:
        return g
    g = flt(frappe.db.get_value(
        "Stock Ledger Entry",
        {"item_code": item_code, "is_cancelled": 0, "valuation_rate": (">", 0)},
        "valuation_rate", order_by="posting_date desc, creation desc"))
    if g > 0:
        return g
    g = flt(frappe.get_cached_value("Item", item_code, "valuation_rate"))
    if g > 0:
        return g
    return flt(frappe.db.get_value("Item Price", {"item_code": item_code, "buying": 1},
                                   "price_list_rate"))


def co_gia_von(item_code, kho):
    return gia_von_hien(item_code, kho) > 0


def _la_btp(item_code):
    return (frappe.get_cached_value("Item", item_code, "custom_sx_nhom") or "").startswith("BTP")


def _cong_thuc(item_code):
    """(số ra, [(mã vào, số vào)]) để tính giá một bán thành phẩm từ đầu vào.

    Có BOM → theo BOM (đường hoán, bột bánh…). Không BOM (đỗ ủ / đỗ vỡ / bột nền —
    công đoạn rang, tách vỏ, nghiền là Repack theo số cân thật) → theo phiếu GẦN NHẤT
    làm ra mã này: hao hụt thật của lần gần nhất, không phải một tỉ lệ đoán.
    """
    from sx.utils import get_bom_active

    bom = get_bom_active(item_code)
    if bom:
        b = frappe.get_cached_doc("BOM", bom)
        vao = [(r.item_code, flt(r.stock_qty)) for r in b.items
               if cint(frappe.get_cached_value("Item", r.item_code, "is_stock_item"))]
        return flt(b.quantity) or 1, vao
    ra = frappe.get_all("Stock Entry Detail",
                        filters={"item_code": item_code, "is_finished_item": 1, "docstatus": 1},
                        fields=["parent", "transfer_qty", "qty"],
                        order_by="creation desc", limit=1)
    if not ra:
        return None, []
    vao = [(r.item_code, flt(r.transfer_qty or r.qty)) for r in frappe.get_all(
        "Stock Entry Detail",
        filters={"parent": ra[0].parent, "is_finished_item": 0, "docstatus": 1,
                 "s_warehouse": ("is", "set")},
        fields=["item_code", "transfer_qty", "qty"])]
    return flt(ra[0].transfer_qty or ra[0].qty), vao


def _gia(item_code, kho, seen, sau):
    """(giá, {mã NVL thiếu giá}). Bán thành phẩm không có giá thì TÍNH từ đầu vào —
    bột đậu từ giá đỗ, đường hoán từ giá đường; chỉ nguyên liệu MUA NGOÀI mới phải hỏi."""
    g = gia_von_hien(item_code, kho)
    if g > 0:
        return g, set()
    if not _la_btp(item_code):
        return None, {item_code}
    if item_code in seen or sau > 8:
        return None, {item_code}
    ra, vao = _cong_thuc(item_code)
    if not ra or not vao:
        return None, {item_code}        # BTP chưa từng làm, không BOM — đành hỏi
    tong, thieu = 0.0, set()
    for ma, so in vao:
        g2, t2 = _gia(ma, None, seen | {item_code}, sau + 1)
        if g2 is None:
            thieu |= t2
        else:
            tong += so * g2
    if thieu:
        return None, thieu
    return (tong / ra) if tong > 0 else None, (set() if tong > 0 else {item_code})


def xet_gia_von(cap):
    """{hoi: [...], tu_tinh: [{item, gia}]} cho các (item, kho) trong `cap`.

    hoi     — nguyên liệu mua ngoài chưa có giá: người phải khai (D116).
    tu_tinh — bán thành phẩm chưa có giá nhưng tính được từ đầu vào (D118): ghi
              thẳng, không hỏi ai (ghi_gia_tu_tinh).
    """
    hoi, tu_tinh, da = {}, [], set()
    for item_code, kho in sorted(cap):
        if item_code in da or co_gia_von(item_code, kho):
            continue
        da.add(item_code)
        g, thieu = _gia(item_code, kho, set(), 0)
        if g:
            tu_tinh.append({"item": item_code, "gia": flt(g, 2)})
        for ma in thieu:
            hoi.setdefault(ma, None)
    ds = []
    for ma in sorted(hoi):
        i = frappe.db.get_value("Item", ma, ["item_name", "stock_uom",
                                             "last_purchase_rate", "standard_rate"],
                                as_dict=True) or frappe._dict()
        ds.append({"item": ma, "ten": i.item_name or ma, "dvt": i.stock_uom or "",
                   "goi_y": flt(i.last_purchase_rate) or flt(i.standard_rate) or None})
    return {"hoi": ds, "tu_tinh": tu_tinh}


def thieu_gia_von(cap):
    """Chỉ phần phải HỎI người (nguyên liệu mua ngoài) — xem xet_gia_von."""
    return xet_gia_von(cap)["hoi"]


def ghi_gia_tu_tinh(ds):
    """Ghi Item.valuation_rate cho bán thành phẩm tính từ nguyên liệu (D118).
    Chỉ là giá DỰ PHÒNG của ERPNext — lần sản xuất sau có giá thật thì giá thật thắng."""
    for d in ds:
        frappe.db.set_value("Item", d["item"], "valuation_rate", flt(d["gia"]))
        frappe.clear_document_cache("Item", d["item"])
        frappe.get_doc("Item", d["item"]).add_comment(
            "Comment", _("Giá vốn {0} / đơn vị kho TỰ TÍNH từ giá nguyên liệu (BOM hoặc "
                         "phiếu sản xuất gần nhất) — sx, lúc chốt.").format(d["gia"]))


def bao_thieu_gia_von(ds, viec):
    """Câu báo lỗi đọc được, liệt kê HẾT các mã một lần (ERPNext báo từng mã một)."""
    frappe.throw(
        _("Chưa {0} được: {1} mã chưa có giá vốn nên ERPNext không trừ kho được:").format(
            viec, len(ds)) + "<br>"
        + "<br>".join(f"• {d['ten']} ({d['item']})" for d in ds) + "<br><br>"
        + _("Cách sửa (một lần cho mỗi mã): quản lý bấm KHAI GIÁ VỐN ở thẻ Chốt ngày, "
            "hoặc trên Desk mở Item → ô Valuation Rate → nhập giá mỗi {0}. Tốt nhất là "
            "nhập mua (Purchase Invoice) có đơn giá.").format(_("đơn vị kho")),
        title=_("Thiếu giá vốn"))


def tao_wo(company, item_code, qty, bom_no, source_wh, fg_wh, ngay_sx=None, planned_date=None):
    """Work Order skip_transfer=1, use_multi_level_bom=0 (chặn explode BOM đa tầng)."""
    wo = frappe.get_doc(
        {
            "doctype": "Work Order",
            "company": company,
            "production_item": item_code,
            "qty": qty,
            "bom_no": bom_no,
            "skip_transfer": 1,
            "use_multi_level_bom": 0,
            "source_warehouse": source_wh,
            "fg_warehouse": fg_wh,
            "wip_warehouse": fg_wh,  # không dùng (skip_transfer) — chỉ thoả reqd
            "custom_ngay_sx": ngay_sx,
        }
    )
    if planned_date:
        wo.planned_start_date = str(planned_date)
    wo.flags.ignore_permissions = True
    wo.insert()
    wo.submit()
    return wo


def loai_phieu_kho(purpose="Manufacture"):
    """Tên Stock Entry Type ứng với `purpose` (D28).

    Core v16 (`StockEntry.set_stock_entry_type`) CHỈ tìm bản ghi
    `{purpose: X, is_standard: 1}`. Site nào lỡ bỏ tick "Is Standard", đổi tên hay
    xoá bản chuẩn thì SE sinh ra thiếu `stock_entry_type` -> chết ở validate với
    "Value missing for Stock Entry: Stock Entry Type" — không nói gì về nguyên nhân.
    Ở đây nới dần điều kiện rồi báo lỗi CHỈ ĐÚNG chỗ phải sửa.
    """
    ten = frappe.db.get_value(
        "Stock Entry Type", {"purpose": purpose, "is_standard": 1}, "name"
    )
    if not ten:  # có bản ghi đúng purpose nhưng không tick is_standard
        ten = frappe.db.get_value("Stock Entry Type", {"purpose": purpose}, "name")
    if not ten and frappe.db.exists("Stock Entry Type", purpose):
        ten = purpose  # bản ghi tên "Manufacture" nhưng purpose bị sửa
    if not ten:
        co = frappe.get_all("Stock Entry Type", pluck="name") or []
        frappe.throw(
            _("Site chưa có 'Stock Entry Type' nào cho mục đích {0}. Vào Desk → "
              "Stock Entry Type → New: Type = {0}, Purpose = {0}, tick 'Is Standard'. "
              "(Hiện có: {1})").format(purpose, ", ".join(co) or _("chưa có loại nào"))
        )
    return ten


def tao_se_manufacture(wo, qty, batch_fg, kho_nguon, ngay=None, ngay_sx=None):
    """SE Manufacture từ WO. kho_nguon(item_code)->warehouse cho từng RM (đổi kho
    nguồn per-item vì WO chỉ có 1 source_warehouse). RM pick batch FIFO; FG gắn batch."""
    from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry

    se = frappe.get_doc(make_stock_entry(wo.name, "Manufacture", qty))
    if not se.stock_entry_type:
        se.stock_entry_type = loai_phieu_kho("Manufacture")
    se.custom_ngay_sx = ngay_sx
    if ngay:
        se.set_posting_time = 1
        se.posting_date = str(ngay)

    for row in se.items:
        if row.get("is_finished_item"):
            row.serial_and_batch_bundle = None
            row.use_serial_batch_fields = 1
            row.batch_no = batch_fg
        elif row.s_warehouse:
            row.s_warehouse = kho_nguon(row.item_code)

    _gan_batch_fifo(se)

    se.flags.ignore_permissions = True
    se.insert()
    se.submit()
    return se


def tao_se_repack(cong_ty, item_vao, kg_vao, kho_vao, item_ra, kg_ra, kho_ra,
                  batch_ra=None, batch_vao=None, ngay=None, ghi_chu=None,
                  lo_rang=None, cong_doan=None):
    """Stock Entry Repack: đổi item A -> item B mà KHÔNG cần BOM (D31).

    Dùng cho các công đoạn tầng 1 (luộc+rang / tách vỏ / nghiền): mỗi công đoạn là
    một lần chuyển hoá có hao hụt, số kg ra do QC cân thật — không có định mức cố
    định để dựng BOM. Repack là purpose chuẩn của ERPNext cho đúng việc này.

    batch_vao=None -> tự pick FIFO. batch_ra bắt buộc nếu item ra có batch.
    """
    se = frappe.new_doc("Stock Entry")
    se.purpose = "Repack"
    se.stock_entry_type = loai_phieu_kho("Repack")
    se.company = cong_ty
    se.custom_lo_rang = lo_rang
    se.custom_cong_doan = cong_doan
    if ngay:
        se.set_posting_time = 1
        se.posting_date = str(ngay)
    if ghi_chu:
        se.remarks = ghi_chu

    se.append("items", {
        "item_code": item_vao, "qty": flt(kg_vao),
        "s_warehouse": kho_vao,
        **({"use_serial_batch_fields": 1, "batch_no": batch_vao} if batch_vao else {}),
    })
    se.append("items", {
        "item_code": item_ra, "qty": flt(kg_ra),
        "t_warehouse": kho_ra, "is_finished_item": 1,
        **({"use_serial_batch_fields": 1, "batch_no": batch_ra} if batch_ra else {}),
    })
    if not batch_vao:
        _gan_batch_fifo(se)

    se.flags.ignore_permissions = True
    se.insert()
    se.submit()
    return se


def tao_se_chuyen_kho(cong_ty, item, kg, kho_di, kho_den, ngay=None, ghi_chu=None,
                      lo_rang=None, cong_doan=None):
    """Stock Entry Material Transfer — xuất kho nguyên liệu ra xưởng (D31). FIFO lô."""
    se = frappe.new_doc("Stock Entry")
    se.purpose = "Material Transfer"
    se.stock_entry_type = loai_phieu_kho("Material Transfer")
    se.company = cong_ty
    se.custom_lo_rang = lo_rang
    se.custom_cong_doan = cong_doan
    if ngay:
        se.set_posting_time = 1
        se.posting_date = str(ngay)
    if ghi_chu:
        se.remarks = ghi_chu
    se.append("items", {
        "item_code": item, "qty": flt(kg),
        "s_warehouse": kho_di, "t_warehouse": kho_den,
    })
    _gan_batch_fifo(se)
    se.flags.ignore_permissions = True
    se.insert()
    se.submit()
    return se


def tao_se_nhap_thang(cong_ty, item, qty, kho, batch, gia=0, ngay=None, ghi_chu=None):
    """Material Receipt thành phẩm KHÔNG qua BOM — nhập kho khi chưa có định mức (D97).

    Hàng vào kho, có lô theo ngày như nhập bình thường (truy xuất ngày × loại vẫn
    còn), nhưng KHÔNG trừ nguyên liệu nào. Phần nguyên liệu đó được ghi nợ trong
    SX No BOM và trừ bù sau bằng tao_se_xuat_bu().

    `gia` = 0 thì cho phép giá vốn 0 (allow_zero_valuation_rate): bịa một đơn giá
    để "có cho đủ" là đưa số giả vào giá vốn hàng bán mà không ai biết.
    """
    se = frappe.new_doc("Stock Entry")
    se.purpose = "Material Receipt"
    se.stock_entry_type = loai_phieu_kho("Material Receipt")
    se.company = cong_ty
    if ngay:
        se.set_posting_time = 1
        se.posting_date = str(ngay)
    se.remarks = ghi_chu
    row = {"item_code": item, "qty": flt(qty), "t_warehouse": kho,
           "use_serial_batch_fields": 1, "batch_no": batch}
    if flt(gia) > 0:
        row["basic_rate"] = flt(gia)
    else:
        row["allow_zero_valuation_rate"] = 1
    se.append("items", row)
    se.flags.ignore_permissions = True
    se.insert()
    se.submit()
    return se


def tao_se_xuat_bu(cong_ty, nhu_cau, kho_nguon, ghi_chu=None):
    """Material Issue trừ nguyên liệu BÙ cho thành phẩm đã nhập lúc chưa có BOM.

    `nhu_cau` = {item_code: qty} (explode BOM × số đã nhập), `kho_nguon(item)` ->
    kho rút. Lô nguyên liệu chọn FIFO TẠI NGÀY BÙ, không phải ngày sản xuất thật —
    xem chú thích trong SX No BOM: lô thành phẩm nhập tạm không truy ngược được
    tới đúng lô bột, đó là cái giá của việc nhập khi chưa có định mức.
    """
    se = frappe.new_doc("Stock Entry")
    se.purpose = "Material Issue"
    se.stock_entry_type = loai_phieu_kho("Material Issue")
    se.company = cong_ty
    se.remarks = ghi_chu
    for item_code, qty in sorted(nhu_cau.items()):
        if flt(qty) <= 0:
            continue
        se.append("items", {"item_code": item_code, "qty": flt(qty),
                            "s_warehouse": kho_nguon(item_code)})
    if not se.items:
        return None
    _gan_batch_fifo(se)
    se.flags.ignore_permissions = True
    se.insert()
    se.submit()
    return se


def _gan_batch_fifo(se):
    """Gán batch FIFO cho dòng RM có has_batch_no; 1 dòng tách nhiều batch nếu cần.

    get_batch_qty trả batch theo chiến lược pick Stock Settings (mặc định FIFO) ->
    lô cũ nhất dùng trước (D5). Không đủ tồn theo lô -> throw rõ ràng.
    """
    from erpnext.stock.doctype.batch.batch import get_batch_qty

    bat_lo_he_thong()
    them = []
    for row in list(se.items):
        if row.get("is_finished_item") or not row.s_warehouse:
            continue
        if not frappe.get_cached_value("Item", row.item_code, "has_batch_no"):
            continue
        batches = get_batch_qty(item_code=row.item_code, warehouse=row.s_warehouse) or []
        con_lai = flt(row.qty)
        phan = []
        for b in batches:
            if con_lai <= 1e-9:
                break
            lay = min(flt(b.get("qty")), con_lai)
            if lay <= 0:
                continue
            phan.append((b.get("batch_no"), lay))
            con_lai -= lay
        if con_lai > 1e-6:
            from sx.utils import cho_phep_ton_am

            if not cho_phep_ton_am():
                frappe.throw(
                    _("Không đủ tồn theo lô cho {0} tại {1} (thiếu {2}).").format(
                        row.item_code, row.s_warehouse, flt(con_lai, 3)
                    )
                )
            # Cho tồn âm: item có batch VẪN bắt buộc khai lô, nên dồn phần thiếu vào
            # lô mới nhất (không có lô nào thì phải tạo/nhập lô trước — không đoán được).
            lo_am = phan[-1][0] if phan else frappe.db.get_value(
                "Batch", {"item": row.item_code}, "name", order_by="creation desc"
            )
            if not lo_am:
                ten = frappe.get_cached_value("Item", row.item_code, "item_name") or row.item_code
                frappe.throw(
                    _("{0} chưa có lô nào trong kho (chưa từng nhập / làm ra lần nào) nên "
                      "chưa trừ được. Bột nền: ghi xuất đỗ → rang → nghiền ra bột ở màn Rang "
                      "đỗ; hàng mua: nhập mua có lô (hoặc Stock Reconciliation tồn đầu). Xong "
                      "bấm Thử lại.").format(ten)
                )
            if phan and phan[-1][0] == lo_am:
                phan[-1] = (lo_am, phan[-1][1] + con_lai)
            else:
                phan.append((lo_am, con_lai))
            con_lai = 0
        if not phan:
            continue
        row.serial_and_batch_bundle = None
        row.use_serial_batch_fields = 1
        row.batch_no, row.qty = phan[0]
        for batch_no, qty in phan[1:]:
            mau = row.as_dict()
            for k in (
                "name", "idx", "parent", "parentfield", "parenttype",
                "owner", "creation", "modified", "modified_by", "docstatus",
                "serial_and_batch_bundle",
            ):
                mau.pop(k, None)
            mau.update({"qty": qty, "batch_no": batch_no, "use_serial_batch_fields": 1})
            them.append(mau)
    for mau in them:
        se.append("items", mau)


def cancel_doc(doctype, name, log=None):
    """Huỷ 1 chứng từ submitted (ignore_permissions sau guard nghiệp vụ)."""
    if not name or not frappe.db.exists(doctype, name):
        return
    d = frappe.get_doc(doctype, name)
    if d.docstatus == 1:
        d.flags.ignore_permissions = True
        d.cancel()
        if log is not None:
            log.append(f"Huỷ {doctype} {name}")
