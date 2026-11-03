"""Lô nguyên liệu mua — tự tạo lô ERPNext lúc duyệt phiếu nhập mua / hoá đơn mua có trừ kho (D226, D227).

Mã nguyên liệu quản lý theo lô (seed bật Has Batch No, TẮT Automatically Create New Batch — không để ERPNext đặt mã
rác). Trước D226 người lập phiếu phải tự tạo Batch cho từng dòng ở Desk; quên là lúc duyệt ERPNext báo "Serial No /
Batch No are mandatory for Item …" — tiếng Anh, từng mã một.

Mã lô (D227) = {viết tắt NCC}-{prefix mã hàng}-{DDMMYY ngày nhập}, vd HLABC-HC-031126: đọc lên là biết hàng của ai,
hàng gì, về ngày nào — không phụ thuộc số lô NCC (bao bì không in, số dài, NCC quay vòng số). Số lô NCC QC ghi (ô Lô
NCC) vẫn lưu vào lô để truy ngược về NCC.
  · viết tắt NCC: ô "Viết tắt (mã lô)" của NCC; trống thì rút gọn tên NCC (bỏ "Công ty TNHH", "Thương mại"…) và LƯU
    lại — như prefix mã hàng (D102/D103): lần sau ra đúng chữ đó, sửa được trên Desk; hai NCC trùng chữ thì NCC sau
    thêm số;
  · prefix mã hàng: sx.utils.prefix_lo (ô Prefix mã lô của Item; trống thì rút gọn mã hàng và lưu);
  · ngày nhập = ngày ghi sổ (posting_date) của phiếu.
Cùng NCC + cùng mã + cùng ngày mà số lô NCC / HSD không vênh (một bên trống cũng tính là khớp) = một lô: nhập thêm vào
lô đó, điền ô còn trống. Vênh (hai lô NCC khác nhau về cùng ngày) → lô -2, -3…

Chạy ở before_submit: sau validate, TRƯỚC on_submit của ERPNext (make_bundle_using_old_serial_batch_fields đọc ô Batch
No của dòng để lập bundle). Dòng đã chọn Batch No / có bundle giữ nguyên. NSX / HSD sai → báo MỘT lần đủ các dòng, chưa
tạo lô nào. Lô tạo cùng giao dịch với lần duyệt — duyệt hỏng ở bước sau thì lô rút theo; lưu nháp không tạo lô.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

TRUONG_MA = ["has_batch_no", "has_serial_no", "is_stock_item", "has_expiry_date", "shelf_life_in_days"]
TRUONG_LO = ["name", "item", "expiry_date", "manufacturing_date", "disabled", "creation"]
VIET_TAT_TOI_DA = 8          # mã lô chép tay ra bao / thẻ kho — dài là chép sai
# Cụm chỉ loại hình / ngành nghề trong tên NCC — bỏ khi rút gọn (so không dấu, chữ thường, cả cụm). Không cụm nào là
# đầu của cụm khác, nên thứ tự không quan trọng ("Công ty TNHH" = "cong ty" rồi "tnhh").
LOAI_HINH = tuple(tuple(c.split()) for c in (
    "cong ty", "cty", "tnhh", "co phan", "cp", "mot thanh vien", "hai thanh vien", "mtv", "doanh nghiep tu nhan",
    "dntn", "ho kinh doanh", "hkd", "chi nhanh", "tap doan", "thuong mai", "tm", "dich vu", "dv", "san xuat", "sx",
    "xuat nhap khau", "xnk", "dau tu", "phat trien", "co so", "cua hang", "va"))


def nhap_kho(doc):
    """Phiếu nhập mua, hoặc hoá đơn mua có trừ kho. Phiếu trả hàng NCC: lô lấy từ phiếu gốc, không tạo."""
    if cint(doc.get("is_return")):
        return False
    return doc.doctype == "Purchase Receipt" or bool(cint(doc.get("update_stock")))


def can_lo(r, ma):
    """Dòng này lúc duyệt ERPNext sẽ đòi lô mà chưa có (`ma` = cờ của Item, xem TRUONG_MA)."""
    if not ma or not cint(ma.get("has_batch_no")) or cint(ma.get("has_serial_no")) or not cint(ma.get("is_stock_item")):
        return False
    if r.get("batch_no") or r.get("serial_and_batch_bundle") or r.get("rejected_serial_and_batch_bundle"):
        return False
    if r.get("from_warehouse"):          # nhận chuyển nội bộ: lô đi theo kho nguồn
        return False
    return flt(r.get("qty")) > 0 or flt(r.get("rejected_qty")) > 0


def sach(lo):
    """Số lô NCC gõ tay → gộp khoảng trắng."""
    return " ".join(str(lo or "").split())[:140]


def _vn(d):
    return getdate(d).strftime("%d/%m/%Y")


def _co_o(dt, f):
    """Ô custom của D226 / D227 đã có chưa — site chưa migrate thì bỏ qua ô đó, đừng văng lỗi SQL lúc duyệt."""
    try:
        return bool(frappe.get_meta(dt).has_field(f))
    except Exception:
        return False


def kiem_ngay(r, ma, ngay_nhap):
    """Câu báo lỗi ngày của MỘT dòng (None = ổn). Hàm thuần — `r` là dict-like."""
    nsx = getdate(r.get("custom_ncc_nsx")) if r.get("custom_ncc_nsx") else None
    hsd = getdate(r.get("custom_ncc_hsd")) if r.get("custom_ncc_hsd") else None
    if nsx and hsd and hsd <= nsx:
        # Xét TRƯỚC quá hạn: gõ đảo hai ô thì HSD cũng "đã qua ngày nhập", nhưng câu này mới chỉ đúng chỗ sai.
        return _("HSD {0} không sau NSX {1} — gõ đảo hai ô?").format(_vn(hsd), _vn(nsx))
    if hsd and ngay_nhap and hsd < ngay_nhap:
        # Như ERPNext ("The batch … has already expired") — lô chọn tay hết hạn cũng bị chặn y vậy.
        return _("HSD {0} đã qua ngày nhập {1}").format(_vn(hsd), _vn(ngay_nhap))
    if nsx and ngay_nhap and nsx > ngay_nhap:
        return _("NSX {0} sau ngày nhập {1}").format(_vn(nsx), _vn(ngay_nhap))
    if not hsd and cint(ma.get("has_expiry_date")) and not cint(ma.get("shelf_life_in_days")):
        return _("mã bắt buộc HSD (Item tích Has Expiry Date) mà chưa ghi HSD")
    return None


def rut_gon_ncc(ten):
    """Tên NCC → viết tắt NGẮN cho mã lô. Hàm thuần.

    Bỏ dấu, bỏ cụm loại hình / ngành nghề, lấy CHỮ ĐẦU mỗi từ; giữ nguyên cụm viết hoa sẵn (ABC — tên riêng viết tắt)
    và cụm có số. Tên chỉ một từ thì giữ cả từ:
        "Công ty TNHH Hương liệu ABC"                 → HLABC
        "Công ty CP Thực phẩm Á Châu"                 → TPAC
        "Công ty TNHH Thương mại và Dịch vụ Minh Phát" → MP
        "Vinamilk"                                    → VINAMILK
    """
    from sx.utils import _khong_dau

    s = _khong_dau(ten)
    tu = [t for t in re.split(r"[^0-9A-Za-z]+", s) if t]
    thuong = [t.lower() for t in tu]
    con, i = [], 0
    while i < len(tu):
        bo = next((len(c) for c in LOAI_HINH if tuple(thuong[i:i + len(c)]) == c), 0)
        if bo:
            i += bo
            continue
        con.append(tu[i])
        i += 1
    con = con or tu
    if not con:
        return ""
    if len(con) == 1:
        return con[0].upper()[:VIET_TAT_TOI_DA]
    co_thuong = any(c.islower() for c in s)      # tên gõ toàn chữ hoa thì không biết cụm nào là viết tắt sẵn
    ra = "".join(t if any(c.isdigit() for c in t) or (co_thuong and t.isupper()) else t[0] for t in con)
    return ra.upper()[:VIET_TAT_TOI_DA]


def viet_tat_ncc(supplier, luu=True):
    """Viết tắt NCC trong mã lô: ô Viết tắt (mã lô) của NCC; trống thì rút gọn tên NCC và (luu) LƯU lại vào ô đó."""
    from sx.utils import _khong_dau

    if not supplier:
        return "NCC"
    co = _co_o("Supplier", "custom_viet_tat")
    v = frappe.db.get_value("Supplier", supplier, "custom_viet_tat") if co else None
    v = re.sub(r"[^0-9A-Z]+", "", _khong_dau(v or "").upper())      # người gõ "hl abc" → HLABC (tên lô không dấu cách)
    if v:
        return v
    goc = rut_gon_ncc(frappe.db.get_value("Supplier", supplier, "supplier_name") or supplier) or "NCC"
    if not (luu and co):
        return goc
    v, n = goc, 1
    while frappe.db.exists("Supplier", {"custom_viet_tat": v, "name": ("!=", supplier)}):
        n += 1
        v = f"{goc[:VIET_TAT_TOI_DA - len(str(n))]}{n}"
    frappe.db.set_value("Supplier", supplier, "custom_viet_tat", v, update_modified=False)
    return v


def ten_goc(doc, item, luu=True):
    """Mã lô gốc (chưa hậu tố -N) của dòng mã `item` trên phiếu `doc`. luu=False: chỉ xem trước (màn QC) — không
    ghi viết tắt / prefix vào NCC, Item."""
    from sx.utils import prefix_lo, rut_gon_ma

    if luu:
        sp = prefix_lo(item)
    else:
        sp = (frappe.db.get_value("Item", item, "custom_batch_prefix") or "").strip() or rut_gon_ma(item)
    ngay = getdate(doc.get("posting_date") or nowdate()).strftime("%d%m%y")
    return f"{viet_tat_ncc(doc.get('supplier'), luu)}-{sp}-{ngay}"


def _ho_lo(item, goc, co_o):
    """Các lô đang dùng được của mã này tên `goc` hoặc `goc-N` (cùng NCC + mã + ngày nhập), cũ trước."""
    # LIKE chỉ để khỏi tải mọi lô của mã; đúng họ lô (goc / goc-N, không phải lô tay "goc-A") là ở fullmatch.
    ds = frappe.get_all("Batch", filters={"item": item, "name": ("like", f"{goc}%"), "disabled": 0},
                        fields=TRUONG_LO + (["custom_ncc_lo"] if co_o else []), order_by="creation asc")
    return [b for b in ds if re.fullmatch(re.escape(goc) + r"(-\d+)?", b.name)]


def lo_cho(doc, item, lo_ncc=None, nsx=None, hsd=None):
    """(tên lô, mới tạo?) cho một dòng (mã, số lô NCC đã sach(), NSX, HSD) của phiếu `doc`."""
    co_o = _co_o("Batch", "custom_ncc_lo")
    nsx = getdate(nsx) if nsx else None
    hsd = getdate(hsd) if hsd else None
    goc = ten_goc(doc, item)
    hop = []
    for b in _ho_lo(item, goc, co_o):
        if hsd and b.get("expiry_date") and getdate(b.get("expiry_date")) != hsd:
            continue
        cu = (b.get("custom_ncc_lo") or "").strip()
        if lo_ncc and cu and cu.casefold() != lo_ncc.casefold():
            continue
        # khớp hẳn (cùng HSD, cùng số lô NCC) đứng trước khớp nhờ một bên trống
        hop.append(((0 if hsd and b.get("expiry_date") else 1) + (0 if lo_ncc and cu else 1),
                    str(b.get("creation") or ""), b))
    if hop:
        b = min(hop, key=lambda x: x[:2])[2]
        bu = {}
        if hsd and not b.get("expiry_date"):
            bu["expiry_date"] = hsd
        if nsx and not b.get("manufacturing_date"):
            bu["manufacturing_date"] = nsx
        if co_o and lo_ncc and not b.get("custom_ncc_lo"):
            bu["custom_ncc_lo"] = lo_ncc
        if bu:
            frappe.db.set_value("Batch", b.name, bu, update_modified=False)
        return b.name, False
    ten, n = goc, 1
    while frappe.db.exists("Batch", ten):
        n += 1
        ten = f"{goc}-{n}"
    moi = {"doctype": "Batch", "batch_id": ten, "item": item, "supplier": doc.get("supplier") or None}
    if doc.name and frappe.db.exists(doc.doctype, doc.name):
        # Chứng từ nguồn của lô. Lập + duyệt một lượt (API / nhập dữ liệu) thì lúc này phiếu chưa vào DB — gắn vào là
        # Frappe báo "Could not find Source Document Name" và chặn duyệt.
        moi.update(reference_doctype=doc.doctype, reference_name=doc.name)
    if co_o and lo_ncc:
        moi["custom_ncc_lo"] = lo_ncc
    b = frappe.get_doc(moi)
    if hsd:
        b.expiry_date = hsd
    if nsx:
        b.manufacturing_date = nsx
    b.flags.ignore_permissions = True        # người duyệt phiếu mua chưa chắc có quyền tạo Batch — lô là việc của hệ thống
    b.insert()
    if not nsx and b.get("manufacturing_date"):
        # Batch tự đặt NSX = hôm nay: với hàng mua đó là ngày NHẬN, không phải NSX in trên bao bì — để trống, đừng bịa
        # lên sổ BM.07.03.
        frappe.db.set_value("Batch", b.name, "manufacturing_date", None, update_modified=False)
    return b.name, True


def tao_lo(doc, method=None):
    """before_submit của Purchase Receipt / Purchase Invoice (hooks.py)."""
    if not nhap_kho(doc):
        return
    ngay_nhap = getdate(doc.get("posting_date")) if doc.get("posting_date") else None
    nho, viec, sai = {}, [], []
    for r in doc.get("items") or []:
        if not r.get("item_code"):
            continue
        if r.item_code not in nho:
            nho[r.item_code] = frappe.db.get_value("Item", r.item_code, TRUONG_MA, as_dict=True) or {}
        ma = nho[r.item_code]
        if not can_lo(r, ma):
            continue
        loi = kiem_ngay(r, ma, ngay_nhap)
        if loi:
            sai.append(_("dòng {0} ({1}): {2}").format(r.idx, r.item_code, loi))
            continue
        viec.append(r)
    if sai:
        frappe.throw(_("Ngày của lô chưa đúng — {0}.<br><br>Sửa ô NSX / HSD lô NCC của dòng đó (màn Tiếp nhận NL, hoặc "
                       "trên dòng hàng) rồi duyệt lại. Chưa tạo lô nào.").format("; ".join(sai)),
                     title=_("Lô nguyên liệu"))
    bao = []
    for r in viec:
        ten_lo, moi = lo_cho(doc, r.item_code, sach(r.get("custom_ncc_lo")), r.get("custom_ncc_nsx"),
                             r.get("custom_ncc_hsd"))
        r.batch_no = ten_lo
        r.use_serial_batch_fields = 1
        bao.append(_("• dòng {0} ({1}): lô <b>{2}</b>{3}").format(
            r.idx, r.item_code, ten_lo, _(" — tạo mới") if moi else _(" — nhập thêm vào lô đã có")))
    if bao:
        frappe.msgprint("<br>".join(bao), title=_("Đã gán lô (NCC + mã hàng + ngày nhập)"), indicator="green")
