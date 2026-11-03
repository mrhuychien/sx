"""Lô nguyên liệu mua — tự tạo lô ERPNext từ ô Lô NCC lúc duyệt phiếu nhập mua / hoá đơn mua có trừ kho (D226).

Mã nguyên liệu quản lý theo lô: seed bật Has Batch No và TẮT Automatically Create New Batch — mã lô phải là số lô NCC
in trên bao bì (truy xuất, thu hồi, BM.07.03 lấy NSX / HSD theo lô), không để ERPNext đặt mã rác. Trước D226 người lập
phiếu phải tự tạo Batch cho từng dòng ở Desk; quên là lúc duyệt ERPNext báo "Serial No / Batch No are mandatory for
Item …" — tiếng Anh, từng mã một — trong khi QC đã ghi đúng số lô đó ở ô Lô NCC.

Chạy ở before_submit: sau validate, TRƯỚC on_submit của ERPNext (make_bundle_using_old_serial_batch_fields đọc ô
Batch No của dòng để lập bundle). Mỗi dòng mã có lô chưa chọn Batch No / bundle:
  · có Lô NCC → nhập vào lô đã có của (mã, số lô NCC) nếu cùng HSD; chưa có thì tạo lô: tên = số lô NCC, tên đã
    dùng (lô của mã khác, hoặc cùng mã mà khác HSD) thì thêm -2, -3… như lô tồn đầu TD-. NSX / HSD lô NCC →
    Batch.manufacturing_date / expiry_date; NCC và chứng từ nguồn ghi vào lô.
  · không có Lô NCC → gom lại, báo MỘT lần đủ các dòng bằng tiếng Việt.
Kiểm hết rồi mới tạo: một dòng hỏng là không tạo lô nào. Lô tạo trong cùng giao dịch với lần duyệt — duyệt hỏng ở bước
sau thì lô rút theo; lưu nháp không tạo lô, phiếu nháp bị xoá không để lại lô rác.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

TRUONG_MA = ["has_batch_no", "has_serial_no", "is_stock_item", "create_new_batch", "has_expiry_date",
             "shelf_life_in_days"]
TRUONG_LO = ["name", "item", "expiry_date", "manufacturing_date", "disabled", "creation"]


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
    """Số lô NCC → tên lô: gộp khoảng trắng, bỏ < > (Frappe cấm trong tên), chừa chỗ cho hậu tố -N."""
    lo = str(lo or "").replace("<", " ").replace(">", " ")
    return " ".join(lo.split())[:130]


def _vn(d):
    return getdate(d).strftime("%d/%m/%Y")


def _co_o_lo_ncc():
    """Batch.custom_ncc_lo có chưa — site chưa migrate D226 thì chỉ tìm lô theo tên, đừng văng lỗi SQL lúc duyệt."""
    try:
        return bool(frappe.get_meta("Batch").has_field("custom_ncc_lo"))
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
        return _("mã bắt buộc HSD (Item tích Has Expiry Date) mà chưa ghi HSD lô NCC")
    return None


def _lo_da_co(item, lo, co_o):
    """Các lô đang dùng được của (mã, số lô NCC): lô app tạo (ô Lô NCC của lô) + lô tạo tay đặt tên đúng số lô."""
    ds = frappe.get_all("Batch", filters={"item": item, "custom_ncc_lo": lo, "disabled": 0},
                        fields=TRUONG_LO + ["custom_ncc_lo"], order_by="creation asc") if co_o else []
    tay = frappe.db.get_value("Batch", lo, TRUONG_LO + (["custom_ncc_lo"] if co_o else []), as_dict=True)
    if tay and tay.get("item") == item and not cint(tay.get("disabled")):
        ds.append(tay)          # lô app tạo đúng tên số lô thì có hai lần trong ds — vô hại, min() chọn một
    return ds


def lo_cho(doc, item, lo, nsx=None, hsd=None):
    """(tên lô, mới tạo?) cho dòng (mã, số lô NCC đã sach(), NSX, HSD).

    Cùng mã + cùng số lô NCC + HSD không vênh (một bên chưa có HSD cũng tính là khớp) = cùng một lô NCC giao nhiều
    chuyến → nhập thêm vào lô đó, điền HSD / NSX còn trống. HSD vênh = lô khác trùng số (NCC quay vòng số lô) → lô mới."""
    co_o = _co_o_lo_ncc()
    nsx = getdate(nsx) if nsx else None
    hsd = getdate(hsd) if hsd else None
    hop = [b for b in _lo_da_co(item, lo, co_o)
           if not (hsd and b.get("expiry_date") and getdate(b.get("expiry_date")) != hsd)]
    if hop:
        b = min(hop, key=lambda x: (0 if (hsd and x.get("expiry_date")) else 1, str(x.get("creation") or "")))
        bu = {}
        if hsd and not b.get("expiry_date"):
            bu["expiry_date"] = hsd
        if nsx and not b.get("manufacturing_date"):
            bu["manufacturing_date"] = nsx
        if co_o and not b.get("custom_ncc_lo"):
            bu["custom_ncc_lo"] = lo
        if bu:
            frappe.db.set_value("Batch", b.name, bu, update_modified=False)
        return b.name, False
    ten, n = lo, 1
    while frappe.db.exists("Batch", ten):
        n += 1
        ten = f"{lo}-{n}"
    moi = {"doctype": "Batch", "batch_id": ten, "item": item, "supplier": doc.get("supplier") or None}
    if doc.name and frappe.db.exists(doc.doctype, doc.name):
        # Chứng từ nguồn của lô. Lập + duyệt một lượt (API / nhập dữ liệu) thì lúc này phiếu chưa vào DB — gắn vào là
        # Frappe báo "Could not find Source Document Name" và chặn duyệt.
        moi.update(reference_doctype=doc.doctype, reference_name=doc.name)
    if co_o:
        moi["custom_ncc_lo"] = lo
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
    nho, viec, thieu, sai = {}, [], [], []
    for r in doc.get("items") or []:
        if not r.get("item_code"):
            continue
        if r.item_code not in nho:
            nho[r.item_code] = frappe.db.get_value("Item", r.item_code, TRUONG_MA, as_dict=True) or {}
        ma = nho[r.item_code]
        if not can_lo(r, ma):
            continue
        ten = f"{r.idx} ({r.item_code})"
        lo = sach(r.get("custom_ncc_lo"))
        if not lo:
            if not cint(ma.get("create_new_batch")):     # mã bật Automatically Create New Batch: ERPNext tự sinh lô
                thieu.append(ten)
            continue
        loi = kiem_ngay(r, ma, ngay_nhap)
        if loi:
            sai.append(_("dòng {0}: {1}").format(ten, loi))
            continue
        viec.append((r, lo))
    if thieu or sai:
        cau = []
        if thieu:
            cau.append(_("Chưa có số lô cho {0}: {1}.").format(
                _("dòng") if len(thieu) == 1 else _("các dòng"), ", ".join(thieu)))
            cau.append(_("Mã nguyên liệu quản lý theo lô: ghi số lô in trên bao bì vào ô <b>Lô NCC</b> (QC ghi ở màn "
                         "Tiếp nhận NL, hoặc gõ ngay trên dòng hàng), kèm NSX / HSD — duyệt phiếu thì app tự tạo lô. "
                         "Đã có lô sẵn thì chọn ở ô Batch No."))
        if sai:
            cau.append(_("Ngày của lô NCC chưa đúng — {0}. Sửa ô NSX / HSD lô NCC của dòng đó rồi duyệt lại.").format(
                "; ".join(sai)))
        frappe.throw("<br><br>".join(cau), title=_("Thiếu lô nguyên liệu"))
    bao = []
    for r, lo in viec:
        ten_lo, moi = lo_cho(doc, r.item_code, lo, r.get("custom_ncc_nsx"), r.get("custom_ncc_hsd"))
        r.batch_no = ten_lo
        r.use_serial_batch_fields = 1
        bao.append(_("• dòng {0} ({1}): lô <b>{2}</b>{3}").format(
            r.idx, r.item_code, ten_lo, _(" — tạo mới") if moi else _(" — nhập thêm vào lô đã có")))
    if bao:
        frappe.msgprint("<br>".join(bao), title=_("Đã gán lô theo Lô NCC"), indicator="green")
