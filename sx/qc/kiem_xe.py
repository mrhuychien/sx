"""Kiểm tra phương tiện vận chuyển — BM.09.01 (W14 D139, W34 D165).

Ghi NGAY trên chứng từ của chuyến hàng (tài liệu 08/10): hoá đơn bán TRỪ KHO (nhà máy không
dùng Delivery Note) và phiếu nhập mua (chuyến nhận nguyên liệu). Các mục + kết luận; mục nào
Không đạt thì kết luận Không đạt (ép, nói ra).

  · Bán: kết luận trống → chặn duyệt hoá đơn ("chưa kiểm xe"); Không đạt → chặn ("không xếp
    hàng lên xe không đạt" — đổi xe, kiểm lại).
  · Nhận nguyên liệu (NCC thực phẩm / phụ gia / bao bì tiếp xúc thực phẩm): kết luận trống →
    chặn duyệt phiếu; xe Không đạt → hàng đã tới sân, không chặn được — ÉP mọi dòng sang
    Cách ly (tiep_nhan đưa vào kho cách ly). NCC loại khác / chưa phân loại: không bắt.
Tắt được ở SX QC Setting → "Bắt kiểm xe BM.09.01". Phiếu trả hàng: không xét.

W34 (D165) — QT.09 lần BH 01:
  · Mục 5.2: năm mục Sạch khô · Mùi · Kín/che · Hàng chung · Sàn; lái xe ký (ô tên lái xe). Bộ mục
    có PHIÊN BẢN như sx/qc/muc.py: chuyến nhớ phiên bản lúc ghi (custom_xe_phien_ban) — chuyến ghi
    trước D165 giữ bốn mục cũ, Desk hiện và tờ in in đúng bốn mục cũ.
  · Mục 4: QC kiểm ngẫu nhiên ít nhất 1 chuyến/tuần — ô "QC kiểm" (người + giờ) trên chuyến
    (sx/api/qc_kiemxe.py, màn Tiếp nhận NL); nhắc khi tuần (thứ Hai – Chủ nhật) có chuyến mà chưa
    chuyến nào QC kiểm. Trưởng Ban ISO xem BM.09.01 hằng tháng — "Đã xem tháng".
"""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, getdate

from sx.qc import ncc as NCC

DAT, KHONG_DAT = "Đạt", "Không đạt"

# ── Phiên bản bộ mục (D165) ─────────────────────────────────────────────────
# Mỗi mục: (field, tên cột trên tờ BM.09.01, yêu cầu — QT.09 mục 5.1).
#   1  W14 (D139): bốn mục theo bản dự thảo QT.09
#   2  W34 (D165): QT.09 lần BH 01 mục 5.2 — năm mục, đúng cột giấy
MUC_THEO_PB = {
    1: (("custom_xe_sach", "Thùng xe sạch, khô, không mùi lạ", "Thùng xe sạch, khô, không mùi lạ"),
        ("custom_xe_khong_chung", "Không chở chung hoá chất / hàng gây nhiễm",
         "Không chở chung hoá chất / hàng gây nhiễm"),
        ("custom_xe_con_trung", "Không có dấu hiệu côn trùng, động vật gây hại",
         "Không có dấu hiệu côn trùng, động vật gây hại"),
        ("custom_xe_che_chan", "Thùng kín / có bạt che mưa nắng", "Thùng kín / có bạt che mưa nắng")),
    2: (("custom_xe_sach_kho", "Sạch khô", "Thùng xe sạch, khô; không côn trùng, không nước đọng"),
        ("custom_xe_mui", "Mùi", "Không mùi lạ (hoá chất, xăng dầu, cá, thuốc lá)"),
        ("custom_xe_kin_che", "Kín/che", "Kín hoặc có mui, bạt che kín mưa nắng; thùng không thủng, không dột"),
        ("custom_xe_hang_chung", "Hàng chung",
         "Không chở chung hoá chất, phân bón, hàng có mùi, động vật, hàng bẩn; hàng khác phải khô sạch, ngăn cách"),
        ("custom_xe_san", "Sàn", "Sàn không đinh, không vật sắc, không hàng cũ rơi vãi")),
}
PHIEN_BAN = 2
MUC = MUC_THEO_PB[PHIEN_BAN]
NCC_CAN = (NCC.TP, NCC.PHU_GIA, NCC.BB_TX)

LOAI = ("Sales Invoice", "Purchase Receipt")
DOI_TAC = {"Sales Invoice": "customer_name", "Purchase Receipt": "supplier_name"}
# QC đóng dấu "QC kiểm" cho chuyến trong chừng này ngày kể từ ngày chuyến: kiểm xe là kiểm lúc xếp / nhận
# hàng — ghi bù qua cuối tuần được, dồn ký chuyến tuần trước để xoá nhắc thì không.
SO_NGAY_QC = 2
# Tháng M phải được Trưởng Ban ISO xem trước hết ngày này của tháng M+1 (như sổ giặt vải ủ BM.08.05).
NGAY_XEM = 5


def _bat():
    try:
        v = frappe.get_cached_doc("SX QC Setting").get("bat_buoc_kiem_xe")
    except Exception:
        return True
    return True if v is None else bool(cint(v))


def ap_dung(doc):
    """Chứng từ này có phải chuyến hàng phải kiểm xe không."""
    if cint(doc.get("is_return")):
        return False
    if doc.doctype == "Sales Invoice":
        return bool(cint(doc.get("update_stock")))
    if doc.doctype == "Purchase Receipt":
        return NCC.thong_tin(doc.get("supplier")).get("loai") in NCC_CAN
    return False


def phien_ban(doc):
    """Phiên bản bộ mục của chuyến. Ô trống / 0 (chuyến chưa lưu lần nào từ D165): đã có giá trị ở mục
    cũ → 1 (chép từ chuyến cũ cũng vậy), còn lại → bộ hiện hành."""
    pb = cint(doc.get("custom_xe_phien_ban"))
    if pb in MUC_THEO_PB:
        return pb
    return 1 if any(doc.get(f) for f, _c, _y in MUC_THEO_PB[1]) else PHIEN_BAN


def muc(doc):
    """Bộ mục của chuyến: ((field, cột, yêu cầu), …)."""
    return MUC_THEO_PB[phien_ban(doc)]


def ket_luan(doc):
    """Kết luận theo mục — hàm thuần. Mục nào Không đạt → Không đạt; đủ các mục Đạt mà
    chưa kết luận → Đạt; còn lại giữ nguyên người kiểm ghi."""
    gia_tri = [doc.get(f) for f, _c, _y in muc(doc)]
    if KHONG_DAT in gia_tri:
        return KHONG_DAT
    if all(v == DAT for v in gia_tri) and not doc.get("custom_xe_ket_luan"):
        return DAT
    return doc.get("custom_xe_ket_luan") or ""


def validate(doc, method=None):
    # Phiên bản ghi cho MỌI chứng từ (kể cả chưa phải kiểm): Desk hiện bộ mục theo ô này.
    doc.custom_xe_phien_ban = phien_ban(doc)
    if not ap_dung(doc):
        return
    kl = ket_luan(doc)
    if kl == KHONG_DAT and doc.get("custom_xe_ket_luan") != KHONG_DAT:
        frappe.msgprint(_("Kiểm xe: có mục Không đạt → kết luận Không đạt."), indicator="orange", alert=True)
    doc.custom_xe_ket_luan = kl
    if kl and not doc.get("custom_xe_nguoi_kiem"):
        doc.custom_xe_nguoi_kiem = frappe.session.user
    if doc.doctype == "Purchase Receipt" and kl == KHONG_DAT:
        doi = []
        for r in doc.get("items") or []:
            if r.get("custom_ket_luan") not in ("Không đạt", "Cách ly"):
                r.custom_ket_luan = "Cách ly"
                doi.append(str(r.idx))
        if doi:
            frappe.msgprint(_("Xe giao hàng KHÔNG ĐẠT kiểm tra — dòng {0} chuyển Cách ly.").format(
                ", ".join(doi)), indicator="orange", title=_("Kiểm xe BM.09.01"))


def before_submit(doc, method=None):
    if not _bat() or not ap_dung(doc):
        return
    kl = doc.get("custom_xe_ket_luan")
    if not kl:
        frappe.throw(_("Chưa kiểm xe (BM.09.01) — ghi biển số, các mục kiểm và kết luận ở mục "
                       "\"Kiểm tra phương tiện vận chuyển\" trước khi duyệt."), title=_("Kiểm xe"))
    if not (doc.get("custom_xe_bien_so") or "").strip():
        frappe.throw(_("Chưa ghi biển số xe (BM.09.01)."), title=_("Kiểm xe"))
    if doc.doctype == "Sales Invoice" and kl == KHONG_DAT:
        frappe.throw(_("Xe {0} KHÔNG ĐẠT kiểm tra — không xếp hàng lên xe này. Đổi xe (hoặc làm "
                       "sạch) rồi kiểm lại.").format(doc.get("custom_xe_bien_so") or ""),
                     title=_("Kiểm xe"))
    if phien_ban(doc) < 2:          # chuyến ghi theo bộ mục cũ: luật cũ
        return
    if not (doc.get("custom_xe_tai_xe") or "").strip():
        frappe.throw(_("Chưa ghi tên lái xe — lái xe ký xác nhận kết quả kiểm (QT.09 mục 5.2)."), title=_("Kiểm xe"))
    if kl == KHONG_DAT and not (doc.get("custom_xe_ghi_chu") or "").strip():
        frappe.throw(_("Xe không đạt — ghi xử lý (vệ sinh lại rồi kiểm lại / từ chối xe, đã báo QLSX, lý do) "
                       "ở ô \"Xử lý / ghi chú kiểm xe\" (BM.09.01)."), title=_("Kiểm xe"))


# ── QC kiểm ngẫu nhiên, Trưởng Ban ISO xem tháng ───────────────────────────


def duoc_qc_kiem(ngay, hom_nay):
    """Chuyến ngày `ngay` còn đóng dấu QC kiểm được vào `hom_nay` không."""
    n = (getdate(hom_nay) - getdate(ngay)).days
    return 0 <= n <= SO_NGAY_QC


def thu_hai(d):
    d = getdate(d)
    return d - timedelta(days=d.weekday())


def theo_tuan(ds):
    """{thứ Hai: {"so_chuyen", "so_qc"}} — hàm thuần; `ds` = [{posting_date, custom_xe_qc_kiem}]."""
    ra = {}
    for x in ds:
        t = ra.setdefault(thu_hai(x.get("posting_date")), {"so_chuyen": 0, "so_qc": 0})
        t["so_chuyen"] += 1
        t["so_qc"] += 1 if x.get("custom_xe_qc_kiem") else 0
    return ra


def thang_qua_han_xem(hom_nay):
    """Ngày đầu của tháng ĐẦU TIÊN chưa tới hạn xem xét: chuyến có ngày TRƯỚC mốc này mà Trưởng Ban ISO
    chưa xem là quá hạn."""
    d = getdate(hom_nay)
    dau = d.replace(day=1)
    if d.day > NGAY_XEM:
        return dau
    return (dau - timedelta(days=1)).replace(day=1)


def chuyen(tu, den, truong, da_duyet=False, loc_them=None):
    """Chuyến có ghi kiểm xe (đã có kết luận) từ `tu` tới `den`, theo ngày: hoá đơn bán trừ kho + phiếu
    nhập mua, không gồm phiếu trả hàng, phiếu huỷ; nháp có (chuyến đang xếp hàng) trừ khi `da_duyet`.
    `truong` có "doi_tac" → tên khách / NCC. Site chưa có field kiểm xe → lỗi của frappe (nơi gọi bắt)."""
    ra = []
    for dt in LOAI:
        loc = {"docstatus": 1 if da_duyet else ("<", 2), "is_return": 0,
               "posting_date": ("between", [str(tu), str(den)]), "custom_xe_ket_luan": ("is", "set"),
               **(loc_them or {})}
        if dt == "Sales Invoice":
            loc["update_stock"] = 1
        for x in frappe.get_all(dt, filters=loc, fields=[DOI_TAC[dt] if t == "doi_tac" else t for t in truong]):
            x = frappe._dict(x, doctype=dt)
            if "doi_tac" in truong:
                x.doi_tac = x.get(DOI_TAC[dt]) or ""
            ra.append(x)
    return sorted(ra, key=lambda x: (str(x.get("posting_date")), str(x.get("name") or "")))


def nhac(hom_nay):
    """Dữ liệu cho hộp nhắc QC (chữ do sx/qc/nhac.py viết). Site chưa migrate → {}.

    {tuan_nay, tuan_truoc: {tu, den, so_chuyen, so_qc}, chua_xem: ["YYYY-MM"]} — tuần thứ Hai – Chủ nhật."""
    d = getdate(hom_nay)
    t2 = thu_hai(d)
    try:
        tuan = theo_tuan(chuyen(t2 - timedelta(days=7), d, ["name", "posting_date", "custom_xe_qc_kiem"]))
        chua = chuyen("2000-01-01", thang_qua_han_xem(d) - timedelta(days=1), ["name", "posting_date"],
                      da_duyet=True, loc_them={"custom_xe_xem_luc": ("is", "not set")})
    except Exception:
        return {}

    def _t(m):
        v = tuan.get(m) or {}
        return {"tu": str(m), "den": str(m + timedelta(days=6)), "so_chuyen": v.get("so_chuyen", 0),
                "so_qc": v.get("so_qc", 0)}

    return {"tuan_nay": _t(t2), "tuan_truoc": _t(t2 - timedelta(days=7)),
            "chua_xem": sorted({str(x.posting_date)[:7] for x in chua})}
