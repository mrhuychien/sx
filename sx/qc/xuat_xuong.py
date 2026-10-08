"""Kiểm tra xuất xưởng theo lô — BM.08.04 (W08, D137).

Một phiếu = một lô thành phẩm = (sản phẩm, HSD) (W05). QC kiểm theo danh mục MUC rồi
GỬI DUYỆT; Trưởng Ban ISO / người được giao DUYỆT — không phải chính QC đã kiểm lô đó.
Lô chưa có phiếu "Đã duyệt + Đạt" thì:
  · thủ kho không duyệt được phiếu nhập kho có lô đó (SX Phieu Nhap TP.before_submit);
  · không bán được (sx/api/xuatxuong.kiem_ban) — trừ hàng tồn trước ngày áp dụng.

File này chỉ đọc doctype của module QC + Batch / Item / SX QC Luu Mau — không import gì
ngoài frappe và module qc (ranh giới module).
"""

import frappe
from frappe import _
from frappe.utils import cint, getdate

PT = "SX Kiem Tra Xuat Xuong"
NHAP, CHO, DUYET, TRA = "Nháp", "Chờ duyệt", "Đã duyệt", "Trả lại"
DAT, KHONG_DAT = "Đạt", "Không đạt"

# Danh mục mục kiểm BM.08.04. CHƯA có bản giấy để chép đúng chữ — đây là những điều
# phiếu kiểm tra xuất xưởng thực phẩm đóng gói luôn phải trả lời. Có bản giấy thì sửa
# chữ / thêm mục ở đây; phiếu cũ giữ nguyên mục đã ghi (bảng con lưu cả nội dung).
MUC = (
    ("1", "Hồ sơ lô: vòng kiểm BM.08.01 ngày sản xuất đủ, không sự cố mở"),
    ("2", "Cảm quan: màu, mùi, vị, trạng thái đặc trưng"),
    ("3", "Bao bì kín, không rách / phồng / ẩm"),
    ("4", "Nhãn đúng sản phẩm, đủ nội dung bắt buộc"),
    ("5", "NSX / HSD in rõ, đúng lô"),
    ("6", "Khối lượng tịnh đạt (cân mẫu)"),
    ("7", "Đóng thùng đúng quy cách, đủ số lượng"),
    ("8", "Đã lấy mẫu lưu của lô"),
)


def _k(item, hsd):
    return (item, str(getdate(hsd)) if hsd else None)


def theo_lo(cap):
    """{(item, 'YYYY-MM-DD'): phiếu đại diện} cho các cặp (sản phẩm, HSD).

    Phiếu đại diện = phiếu Đã duyệt + Đạt nếu có; không thì phiếu mới nhất. Phiếu
    'Đã duyệt + Không đạt' cũ không che phiếu kiểm lại sau rework."""
    cap = {_k(i, h) for i, h in cap if i and h}
    if not cap:
        return {}
    try:
        ds = frappe.get_all(PT, filters={"san_pham": ("in", list({i for i, _h in cap})),
                                         "hsd": ("in", list({h for _i, h in cap}))},
                            fields=["name", "san_pham", "hsd", "trang_thai", "ket_luan", "creation",
                                    "qc_kiem", "nguoi_duyet"],
                            order_by="creation asc")
    except Exception:          # chưa migrate D137
        return {}
    ra = {}
    for x in ds:
        k = _k(x.san_pham, x.hsd)
        if k not in cap:
            continue
        cu = ra.get(k)
        if cu and cu.trang_thai == DUYET and cu.ket_luan == DAT:
            continue
        ra[k] = x
    return ra


def da_duyet(p):
    return bool(p and p.trang_thai == DUYET and p.ket_luan == DAT)


def mo_ta(p):
    """Câu ngắn cho người đọc: lô này đang ở đâu trong BM.08.04."""
    if not p:
        return _("chưa kiểm xuất xưởng")
    if p.trang_thai == DUYET:
        return _("đã duyệt — {0}").format(p.ket_luan or "?")
    return {NHAP: _("QC đang kiểm"), CHO: _("chờ Ban ISO duyệt"),
            TRA: _("bị trả lại, QC kiểm lại")}.get(p.trang_thai, p.trang_thai)


def chua_duyet(cap):
    """[(item, hsd, phiếu|None)] — các lô trong `cap` CHƯA được duyệt xuất xưởng."""
    p = theo_lo(cap)
    ra, da = [], set()
    for i, h in cap:
        if not i or not h:
            continue
        k = _k(i, h)
        if k in da:
            continue
        da.add(k)
        if not da_duyet(p.get(k)):
            ra.append((i, k[1], p.get(k)))
    return ra


def ho_so_lo(item, hsd, nsx):
    """Tra hồ sơ của lô lúc lập phiếu — mục 1 và 8 có căn cứ, không chỉ QC nhớ.
    Trả {"chu": câu tóm tắt, "muc1": Đạt|None, "muc8": Đạt|None}."""
    phan, muc1, muc8 = [], None, None
    if nsx:
        try:
            so = frappe.db.count("SX QC Round", {"ngay": getdate(nsx), "docstatus": 1})
            mo = frappe.db.count("SX Su Co", {"ngay": getdate(nsx), "trang_thai": "Mở", "dien_tap": 0})
        except Exception:
            so, mo = 0, 0
        phan.append(_("BM.08.01 ngày {0}: {1} lượt hoàn tất · sự cố mở ngày đó: {2}").format(
            getdate(nsx).strftime("%d/%m/%Y"), so, mo))
        muc1 = DAT if (so >= 3 and not mo) else None
    else:
        phan.append(_("Chưa tính được NSX (mã chưa khai hạn dùng) — QC tự đối chiếu hồ sơ."))
    try:
        lm = frappe.get_all("SX QC Luu Mau", filters={"san_pham": item, "hsd": getdate(hsd)},
                            pluck="name", limit=3)
        if not lm:
            lm = frappe.get_all("SX QC Luu Mau", filters={
                "san_pham": item, "lo": ("like", f"%{getdate(hsd).strftime('%d/%m/%Y')}%")},
                pluck="name", limit=3)
    except Exception:
        lm = []
    phan.append(_("Mẫu lưu: {0}").format(", ".join(lm)) if lm else _("Mẫu lưu: CHƯA lấy"))
    muc8 = DAT if lm else None
    return {"chu": "\n".join(phan), "muc1": muc1, "muc8": muc8}


def can_ket_luan(doc):
    """Lỗi khi gửi duyệt: mục chưa chấm, kết luận thiếu / mâu thuẫn. [] = được gửi."""
    loi = []
    chua = [r.ma for r in doc.get("ds_muc") or [] if not r.get("ket_qua")]
    if chua:
        loi.append(_("Còn mục chưa chấm: {0}").format(", ".join(chua)))
    if not doc.get("ket_luan"):
        loi.append(_("Chưa có kết luận Đạt / Không đạt"))
    elif doc.ket_luan == DAT and any(r.get("ket_qua") == KHONG_DAT for r in doc.get("ds_muc") or []):
        loi.append(_("Kết luận Đạt nhưng có mục Không đạt"))
    if cint(doc.get("so_mau")) <= 0:
        loi.append(_("Chưa ghi số mẫu đã kiểm"))
    return loi
