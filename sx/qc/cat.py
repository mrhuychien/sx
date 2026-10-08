"""Nhật ký cát rang BM.08.03 (W20, D141) — phần tính, đọc dữ liệu qua frappe.

Mỗi ngày có rang ghi MỘT dòng SX Nhat Ky Cat: nguồn cát (NCC loại Cát rang), có thay cát
không, vệ sinh thùng / khay, cảm quan. App TỰ ĐẾM số ngày cát đang dùng: số dòng nhật ký
kể từ lần thay cát gần nhất, tính cả hôm đó. Dòng đầu tiên của sổ (cát đã dùng từ trước
khi có app) khai tay số ngày, các dòng sau tự cộng.

Số ngày tối đa của cát CHƯA CHỐT (C19) → chỉ đếm, không nhắc. SX QC Setting
.cat_so_ngay_toi_da để 0; khi chốt thì điền, hộp nhắc tự báo thay cát.

Đổi NGUỒN cát (thay bằng cát của NCC khác) → phải kiểm kim loại nặng và lưu một lọ mẫu:
nhắc tới khi dòng đó có kết quả Đạt và đã tích lọ mẫu. Kết quả Không đạt → phiếu sự cố.
"""

from datetime import timedelta

import frappe
from frappe.utils import cint, getdate

PT = "SX Nhat Ky Cat"
KLN_DAT, KLN_HONG, KLN_GUI = "Đạt", "Không đạt", "Đã gửi mẫu"
TRUONG = ["name", "ngay", "ncc_cat", "thay_cat", "so_ngay_dung", "doi_nguon"]


def ke_tiep(truoc, x):
    """Giá trị tính của dòng `x` khi dòng liền trước trong sổ là `truoc` (None = dòng đầu
    sổ). Hàm thuần → {so_ngay_dung, ncc_cat, thay_cat, doi_nguon}.

    · Nguồn bỏ trống = giữ nguồn của cát đang dùng.
    · Nguồn KHÁC nguồn cát đang dùng = thay cát + đổi nguồn (không có chuyện đổi NCC mà
      vẫn cát cũ).
    · Thay cát cùng nguồn = cát mới nhưng không phải đổi nguồn (không phải kiểm lại).
    · Dòng đầu sổ không thay cát: giữ số ngày khai tay (≥ 1)."""
    truoc = truoc or {}
    cu = truoc.get("ncc_cat") or ""
    ncc = x.get("ncc_cat") or cu
    thay = 1 if cint(x.get("thay_cat")) else 0
    doi = 1 if (cu and ncc and ncc != cu) else 0
    if doi:
        thay = 1
    if thay:
        so = 1
    elif truoc:
        so = cint(truoc.get("so_ngay_dung")) + 1
    else:
        so = max(1, cint(x.get("so_ngay_dung")))
    return {"so_ngay_dung": so, "ncc_cat": ncc, "thay_cat": thay, "doi_nguon": doi}


def dong_truoc(ngay, bo=None):
    """Dòng liền trước ngày `ngay` (bỏ dòng `bo`), None nếu là dòng đầu sổ."""
    ds = frappe.get_all(PT, filters={"ngay": ("<", str(getdate(ngay))), "name": ("!=", bo or "")},
                        fields=TRUONG, order_by="ngay desc", limit=1)
    return ds[0] if ds else None


def _gt(k, v):
    return (v or "") if k == "ncc_cat" else cint(v)


def tinh_lai(tu, bo=None):
    """Tính lại cả chuỗi từ ngày `tu` trở đi — ghi bù một ngày cũ, sửa ngày, xoá dòng thì
    số ngày / nguồn của MỌI dòng sau nó đổi theo. Bỏ dòng `bo` (đang bị xoá)."""
    t = dong_truoc(tu, bo)
    for x in frappe.get_all(PT, filters={"ngay": (">=", str(getdate(tu))), "name": ("!=", bo or "")},
                            fields=TRUONG, order_by="ngay asc"):
        moi = ke_tiep(t, x)
        doi = {k: v for k, v in moi.items() if _gt(k, x.get(k)) != _gt(k, v)}
        if doi:
            frappe.db.set_value(PT, x.name, doi, update_modified=False)
        t = dict(x, **moi)


def cho_kln(ds):
    """Dòng đổi nguồn còn thiếu kim loại nặng Đạt / lọ mẫu (Không đạt đã thành sự cố).
    Hàm thuần: `ds` = [{ngay, ncc_cat, ten_ncc, doi_nguon, kln, luu_lo_mau}]."""
    return [x for x in ds if cint(x.get("doi_nguon")) and x.get("kln") != KLN_HONG
            and (x.get("kln") != KLN_DAT or not cint(x.get("luu_lo_mau")))]


def toi_da():
    try:
        return cint(frappe.get_cached_doc("SX QC Setting").get("cat_so_ngay_toi_da"))
    except Exception:
        return 0


# Ngày có rang mà thiếu nhật ký: chỉ soi chừng này ngày — xa hơn là lịch sử, chỗ của nó là
# màn Xem xét tháng.
SO_NGAY_SOI = 7


def nhac(hom_nay, ngay_rang=()):
    """Dữ liệu cho hộp nhắc QC (chữ do hàm thuần ở sx/qc/nhac.py viết). Chưa migrate → {}.

    `ngay_rang`: các ngày có lượt kiểm ghi nhiệt độ rang — ngày đó có rang thì phải có dòng
    nhật ký cát. Ngày không ai ghi nhiệt độ rang thì không đoán."""
    d = getdate(hom_nay)
    tu = d - timedelta(days=SO_NGAY_SOI)
    try:
        cuoi = frappe.get_all(PT, filters={"ngay": ("<=", str(d))},
                              fields=["ngay", "so_ngay_dung", "ten_ncc", "ncc_cat"],
                              order_by="ngay desc", limit=1)
        co = {str(x) for x in frappe.get_all(PT, filters={"ngay": ("between", [str(tu), str(d)])},
                                              pluck="ngay")}
        cho = cho_kln(frappe.get_all(PT, filters={"doi_nguon": 1},
                                     fields=["name", "ngay", "ncc_cat", "ten_ncc", "doi_nguon", "kln",
                                             "luu_lo_mau"], order_by="ngay asc"))
    except Exception:
        return {}
    rang = {str(getdate(x)) for x in ngay_rang or ()}
    hien = cuoi[0] if cuoi else None
    return {
        "co_du_lieu": bool(hien),
        "so_ngay": cint(hien.so_ngay_dung) if hien else 0,
        "ncc": (hien.ten_ncc or hien.ncc_cat) if hien else "",
        "toi_da": toi_da(),
        "thieu": sorted(x for x in rang if str(tu) <= x < str(d) and x not in co),
        "hom_nay_chua": str(d) in rang and str(d) not in co,
        "cho_kln": [{"ngay": str(x.ngay), "ncc": x.ten_ncc or x.ncc_cat, "kln": x.kln or "",
                     "lo_mau": cint(x.luu_lo_mau)} for x in cho],
    }
