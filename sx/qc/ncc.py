"""Nhà cung cấp được duyệt — BM.07.02 (W09, D138).

Supplier có ba ô mới: LOẠI NCC (quyết định bộ hồ sơ phải có), NGUỒN (trong nước / nhập
khẩu — quyết định giấy tờ từng lô khi tiếp nhận, W10) và bảng HỒ SƠ (giấy tờ + hạn).
Tích "Đã duyệt" = Trưởng Ban ISO / người được giao xác nhận hồ sơ đủ — chặn ở validate
nếu thiếu / hết hạn, chặn cả Desk.

Mua của NCC chưa duyệt: CHỈ CẢNH BÁO, không chặn (tài liệu 08/10) — đơn mua, phiếu nhập
mua, hoá đơn mua đều báo. Cát rang chỉ cần hợp đồng hoặc đơn hàng + ĐKKD.

Bộ hồ sơ theo loại dưới đây là bản TẠM theo quy định chung (chưa có bản BM.07.02 để chép):
sửa HO_SO_CAN là đổi luật, không đổi dữ liệu.
"""

import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime, nowdate

from sx.qc.quyen import duoc_dong_su_co

TP = "Nguyên liệu thực phẩm"
PHU_GIA = "Phụ gia / hương liệu"
BB_TX = "Bao bì tiếp xúc thực phẩm"
BB_NGOAI = "Bao bì ngoài"
CAT = "Cát rang"
DV = "Dịch vụ / khác"
LOAI = (TP, PHU_GIA, BB_TX, BB_NGOAI, CAT, DV)
THUC_PHAM = (TP, PHU_GIA)              # loại phải có giấy tờ thực phẩm khi tiếp nhận (W10)
TRONG_NUOC, NHAP_KHAU = "Trong nước", "Nhập khẩu"

DKKD = "Đăng ký kinh doanh"
ATTP = "Giấy chứng nhận cơ sở đủ điều kiện ATTP"
HACCP = "Chứng nhận HACCP / ISO 22000"
CONG_BO = "Bản công bố sản phẩm"
PKN = "Phiếu kiểm nghiệm sản phẩm (năm)"
PKN_BB = "Phiếu kiểm nghiệm bao bì (năm)"
HOP_DONG = "Hợp đồng / đơn hàng"

# loại NCC -> [nhóm giấy tờ]; mỗi nhóm là các loại hồ sơ THAY THẾ nhau (có một là đủ).
HO_SO_CAN = {
    TP: [(DKKD,), (ATTP, HACCP), (CONG_BO,)],
    PHU_GIA: [(DKKD,), (ATTP, HACCP), (CONG_BO,)],
    BB_TX: [(DKKD,), (PKN_BB,)],
    BB_NGOAI: [(DKKD,)],
    CAT: [(HOP_DONG,), (DKKD,)],          # tài liệu 08/10: hợp đồng hoặc đơn hàng + ĐKKD
    DV: [],
}


def _con_han(r, ngay):
    return not r.get("het_han") or getdate(r["het_han"]) >= getdate(ngay)


def thieu_ho_so(loai, ho_so, ngay=None):
    """Nhóm giấy tờ còn thiếu (hoặc chỉ có bản hết hạn) cho loại NCC — hàm thuần.
    [] = đủ. Loại chưa chọn → ["Chưa chọn loại NCC"]."""
    ngay = ngay or nowdate()
    if not loai:
        return [_("Chưa chọn loại nhà cung cấp")]
    co = {r.get("loai_ho_so") for r in ho_so or [] if _con_han(r, ngay)}
    het = {r.get("loai_ho_so") for r in ho_so or [] if not _con_han(r, ngay)}
    ra = []
    for nhom in HO_SO_CAN.get(loai, []):
        if co & set(nhom):
            continue
        ten = " hoặc ".join(nhom)
        ra.append(_("{0} (hết hạn)").format(ten) if het & set(nhom) else ten)
    return ra


def pkn_con_han(ho_so, ngay):
    """Phiếu kiểm nghiệm năm còn hạn ở ngày tiếp nhận → dòng hồ sơ đó; không có → None."""
    ds = [r for r in ho_so or [] if r.get("loai_ho_so") == PKN and _con_han(r, ngay)]
    return max(ds, key=lambda r: str(r.get("het_han") or "9999")) if ds else None


def thong_tin(supplier):
    """{duyet, loai, nguon, ho_so: [...]} của một NCC. Chưa migrate / không có → {}."""
    if not supplier:
        return {}
    try:
        s = frappe.db.get_value("Supplier", supplier, ["custom_ncc_duyet", "custom_loai_ncc",
                                                       "custom_nguon_goc"], as_dict=True)
        ho_so = frappe.get_all("SX Ho So NCC", filters={"parenttype": "Supplier", "parent": supplier},
                               fields=["loai_ho_so", "so_hieu", "ngay_cap", "het_han"])
    except Exception:
        return {}
    if not s:
        return {}
    return {"duyet": bool(cint(s.custom_ncc_duyet)), "loai": s.custom_loai_ncc or "",
            "nguon": s.custom_nguon_goc or "", "ho_so": ho_so}


# ── hook Supplier ──────────────────────────────────────────────────────────

def validate_supplier(doc, method=None):
    """Tích "Đã duyệt": người có quyền + hồ sơ đủ, còn hạn. Bỏ tích: người có quyền."""
    duyet = cint(doc.get("custom_ncc_duyet"))
    doi = bool(duyet) if doc.is_new() else doc.has_value_changed("custom_ncc_duyet")
    if not doi:
        if duyet:
            # Đã duyệt từ trước: sửa hồ sơ làm thiếu thì không tự bỏ duyệt (mua vẫn phải
            # chạy) — nhưng NÓI ra, để Ban ISO biết danh sách được duyệt đang sai.
            thieu = thieu_ho_so(doc.get("custom_loai_ncc"), doc.get("custom_ho_so_ncc"))
            if thieu:
                frappe.msgprint(_("NCC đang được duyệt nhưng hồ sơ thiếu / hết hạn: {0}").format(
                    "; ".join(thieu)), indicator="orange", title=_("Hồ sơ NCC"))
        return
    if not duoc_dong_su_co():
        frappe.throw(_("Chỉ Trưởng Ban ISO hoặc người được giao mới duyệt / bỏ duyệt nhà cung "
                       "cấp."), frappe.PermissionError)
    if duyet:
        thieu = thieu_ho_so(doc.get("custom_loai_ncc"), doc.get("custom_ho_so_ncc"))
        if thieu:
            frappe.throw(_("Chưa duyệt được — hồ sơ còn thiếu:") + "<br>"
                         + "<br>".join(f"• {x}" for x in thieu), title=_("Hồ sơ NCC"))
        doc.custom_ngay_duyet_ncc = getdate(nowdate())
        doc.custom_duyet_ncc_boi = frappe.session.user
    else:
        doc.custom_ngay_duyet_ncc = None
        doc.custom_duyet_ncc_boi = None


# ── hook chứng từ mua ──────────────────────────────────────────────────────

def canh_bao_mua(doc, method=None):
    """validate của Purchase Order / Purchase Receipt / Purchase Invoice: NCC chưa duyệt,
    chưa phân loại, hoặc hồ sơ hết hạn → CẢNH BÁO (không chặn mua)."""
    t = thong_tin(doc.get("supplier"))
    if not t or t["loai"] == DV:
        return
    ngay = doc.get("posting_date") or doc.get("transaction_date") or nowdate()
    if not t["loai"]:
        bao = _("chưa phân loại (Supplier → Duyệt NCC BM.07.02)")
    elif not t["duyet"]:
        bao = _("CHƯA được duyệt (BM.07.02)")
    else:
        thieu = thieu_ho_so(t["loai"], t["ho_so"], ngay)
        if not thieu:
            return
        bao = _("đã duyệt nhưng hồ sơ thiếu / hết hạn: {0}").format("; ".join(thieu))
    frappe.msgprint(_("Nhà cung cấp {0} {1}. Vẫn lưu được — báo Ban ISO bổ sung hồ sơ.").format(
        doc.get("supplier_name") or doc.get("supplier"), bao), indicator="orange",
        title=_("Nhà cung cấp"))
