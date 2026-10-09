"""Nhật ký cát rang BM.08.03 — phần tính, đọc dữ liệu qua frappe.

W20 (D141): mỗi ngày có rang một dòng. W32 (D164): theo HD.08.03 + BM.08.03 viết lại 07/10 — MỖI VIỆC MỘT DÒNG:
nhập cát / rang khô đưa dùng / bổ sung / loại cát / vệ sinh thùng, khay. Cột giấy: ngày, việc, nguồn + số
BM.07.03, khối lượng kg, thùng số / nhãn ngày, số ngày đã dùng (khi bổ sung, loại) + lý do loại, người làm /
QC ký (người ghi). Sàng lại hằng ngày ghi BM.08.01 mục 4, không ghi ở đây.

SỐ NGÀY ĐÃ DÙNG do app đếm: số NGÀY CÓ RANG (có lượt kiểm ghi nhiệt độ rang ở máy nào đó) kể từ lần thay toàn
bộ gần nhất — dòng "Rang khô đưa dùng", tính cả hôm đó nếu hôm đó có rang. Cát bổ sung chỉ bù hao hụt, KHÔNG
tính lại ngày. Đã loại mà chưa đưa cát mới vào → không có cát đang dùng.

Dòng sổ cũ (D141, trước D164) giữ nguyên, đánh dấu `so_cu`: ngày của chúng là ngày có rang, số ngày đã dùng
của dòng cũ cuối cùng là mốc để đếm tiếp.

Đổi NGUỒN cát (nhập cát của NCC khác lần nhập trước) → kiểm kim loại nặng một lần trước khi dùng và lưu một lọ
mẫu: nhắc tới khi dòng đó có kết quả Đạt và đã tích lọ mẫu. Kết quả Không đạt → phiếu sự cố. Số ngày tối đa
của cát chưa chốt (C19): SX QC Setting.cat_so_ngay_toi_da để 0 thì chỉ đếm, không nhắc.
"""

from datetime import timedelta

import frappe
from frappe.utils import cint, flt, getdate

PT = "SX Nhat Ky Cat"
LUOT = "SX QC Round"
KLN_DAT, KLN_HONG, KLN_GUI = "Đạt", "Không đạt", "Đã gửi mẫu"
NHAP, RANG_KHO, BO_SUNG, LOAI, VE_SINH = "Nhập cát", "Rang khô đưa dùng", "Bổ sung", "Loại cát", "Vệ sinh thùng, khay"
VIEC = (NHAP, RANG_KHO, BO_SUNG, LOAI, VE_SINH)
CAN_KL = (NHAP, RANG_KHO, BO_SUNG)        # phải ghi khối lượng
CO_NGUON = (NHAP, RANG_KHO, BO_SUNG)      # ghi nguồn cát (nhập: bắt buộc; đưa dùng, bổ sung: mặc định nguồn nhập gần nhất)
DEM = (BO_SUNG, LOAI)                     # giấy: "khi bổ sung hoặc loại, ghi số ngày đã dùng của cát trong máy"
# Cùng một ngày: loại cát cũ trước, rồi mới đưa cát mới vào, rồi bổ sung.
THU_TU = {NHAP: 0, VE_SINH: 1, LOAI: 2, RANG_KHO: 3, BO_SUNG: 4}
# Nhiệt độ rang của từng máy (W16): ghi ở máy nào cũng là ngày có rang.
RANG = ("rang_nhiet_do", "rang_nhiet_do_m2", "rang_nhiet_do_m3")
TRUONG_DEM = ["name", "ngay", "viec", "so_cu", "so_ngay_dung", "so_ngay_dau", "ncc_cat", "ten_ncc", "creation"]
# Có rang mà sổ không có cát đang dùng: chỉ soi chừng này ngày (xa hơn là lịch sử, chỗ của nó là Xem xét tháng).
SO_NGAY_SOI = 7


def xep(x):
    return (str(getdate(x["ngay"])), THU_TU.get(x.get("viec"), 5), str(x.get("creation") or ""))


def dem_ngay(dong, ngay_rang, d):
    """Số ngày đã dùng của cát trong máy, tính tới hết ngày `d`. Hàm thuần.

    `dong` = các dòng sổ [{ngay, viec, so_cu, so_ngay_dung, so_ngay_dau, creation}];
    `ngay_rang` = các ngày có rang. None = không có cát đang dùng (chưa đưa dùng lần nào, hoặc đã loại mà
    chưa đưa cát mới vào).

    Mốc = dòng "Rang khô đưa dùng" mới nhất: đếm từ hôm đó, cộng số ngày khai tay của dòng đó (`so_ngay_dau` —
    chỉ dòng đưa dùng đầu sổ: cát đã dùng từ trước khi có sổ). Có dòng sổ cũ từ mốc trở đi thì đếm tiếp từ số
    ngày của dòng cũ cuối cùng."""
    d = getdate(d)
    ds = sorted((x for x in dong if getdate(x["ngay"]) <= d), key=xep)
    moc = max((i for i, x in enumerate(ds) if x.get("viec") == RANG_KHO), default=None)
    if any(x.get("viec") == LOAI for x in ds[(moc + 1 if moc is not None else 0):]):
        return None
    cu = [x for x in ds[(moc or 0):] if cint(x.get("so_cu"))]
    if cu:
        goc, tu = cint(cu[-1].get("so_ngay_dung")), getdate(cu[-1]["ngay"])
    elif moc is not None:
        goc, tu = cint(ds[moc].get("so_ngay_dau")), getdate(ds[moc]["ngay"]) - timedelta(days=1)
    else:
        return None
    return goc + sum(1 for r in {str(getdate(x)) for x in ngay_rang} if tu < getdate(r) <= d)


def nguon_dang_dung(dong, d):
    """(mã NCC, tên NCC) của cát đang dùng tới ngày `d`: nguồn của dòng đưa dùng / bổ sung / nhập mới nhất
    có ghi nguồn (dòng cũ cũng tính). Hàm thuần."""
    for x in sorted((x for x in dong if getdate(x["ngay"]) <= getdate(d)), key=xep, reverse=True):
        if x.get("ncc_cat") and (x.get("viec") in CO_NGUON or cint(x.get("so_cu"))):
            return x["ncc_cat"], x.get("ten_ncc") or x["ncc_cat"]
    return "", ""


def doi_nguon(ds):
    """Đánh dấu đổi nguồn cho các dòng NHẬP CÁT theo thứ tự thời gian. Hàm thuần.
    `ds` = [{name, ngay, viec, so_cu, ncc_cat, doi_nguon, creation}] → {name: 0/1} của các dòng nhập cát.
    Nhập từ NCC khác NCC của lần nhập trước (dòng sổ cũ cũng là "lần trước") = đổi nguồn. Dòng sổ cũ giữ
    nguyên dấu đổi nguồn của nó."""
    truoc, ra = "", {}
    for x in sorted(ds, key=xep):
        n = x.get("ncc_cat") or ""
        if x.get("viec") == NHAP and not cint(x.get("so_cu")):
            ra[x["name"]] = 1 if (truoc and n and n != truoc) else 0
        if n and (x.get("viec") == NHAP or cint(x.get("so_cu"))):
            truoc = n
    return ra


def ngay_rang(tu, den):
    """Ngày có rang trong [tu, den]: ngày có lượt kiểm (chưa huỷ) ghi nhiệt độ rang ở máy nào đó."""
    loc = {"ngay": ("between", [str(getdate(tu)), str(getdate(den))]), "docstatus": ("<", 2)}
    try:
        ds = frappe.get_all(LUOT, filters=loc, fields=["ngay"] + list(RANG))
    except Exception:          # site chưa có ô nhiệt độ máy 2, 3 (trước W16)
        ds = frappe.get_all(LUOT, filters=loc, fields=["ngay", RANG[0]])
    return {str(getdate(x.ngay)) for x in ds if any(flt(x.get(f)) > 0 for f in RANG)}


def dong_tu_moc(d, bo=None, moc_tai=None):
    """Các dòng sổ cần để đếm mọi ngày từ `moc_tai` (mặc định `d`) tới `d`: từ dòng "Rang khô đưa dùng" mới nhất
    tính tới `moc_tai` (cả sổ nếu chưa có) cho tới `d`. Bỏ dòng `bo`."""
    loc = {"viec": RANG_KHO, "ngay": ("<=", str(getdate(moc_tai or d))), "name": ("!=", bo or "")}
    moc = frappe.get_all(PT, filters=loc, fields=["ngay"], order_by="ngay desc", limit=1)
    f = {"ngay": ("between", [str(getdate(moc[0].ngay)), str(getdate(d))]) if moc else ("<=", str(getdate(d))),
         "name": ("!=", bo or "")}
    return frappe.get_all(PT, filters=f, fields=TRUONG_DEM, order_by="ngay asc, creation asc")


def so_ngay(d, bo=None, them=None):
    """Số ngày đã dùng của cát trong máy tới hết ngày `d` (None = không có cát đang dùng). `them` = dòng đang
    lưu (chưa có trong DB), `bo` = dòng bỏ ra (đang sửa / xoá)."""
    ds = dong_tu_moc(d, bo) + ([them] if them else [])
    if not ds:
        return None
    return dem_ngay(ds, ngay_rang(min(getdate(x["ngay"]) for x in ds), d), d)


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


def nhac(hom_nay):
    """Dữ liệu cho hộp nhắc QC (chữ do hàm thuần ở sx/qc/nhac.py viết). Chưa migrate → {}.

    {co_du_lieu, dang_dung, so_ngay, ncc, toi_da, cho_kln, rang_khong_cat}: `rang_khong_cat` = ngày có rang đầu
    tiên trong 7 ngày qua mà sổ không có cát đang dùng (chưa ghi lần đưa cát vào máy) — None nếu không có."""
    d = getdate(hom_nay)
    dau = d - timedelta(days=SO_NGAY_SOI)
    try:
        ds = dong_tu_moc(d, moc_tai=dau)
        cho = cho_kln(frappe.get_all(PT, filters={"doi_nguon": 1},
                                     fields=["name", "ngay", "ncc_cat", "ten_ncc", "doi_nguon", "kln",
                                             "luu_lo_mau"], order_by="ngay asc"))
        rang = ngay_rang(min([getdate(x["ngay"]) for x in ds] + [dau]), d)
    except Exception:
        return {}
    so = dem_ngay(ds, rang, d) if ds else None
    trong = sorted(x for x in rang if str(dau) <= x <= str(d) and dem_ngay(ds, rang, x) is None)
    return {
        "co_du_lieu": bool(ds),
        "dang_dung": so is not None,
        "so_ngay": so or 0,
        "ncc": nguon_dang_dung(ds, d)[1],
        "toi_da": toi_da(),
        "rang_khong_cat": trong[0] if trong else None,
        "cho_kln": [{"ngay": str(x.ngay), "ncc": x.ten_ncc or x.ncc_cat, "kln": x.kln or "",
                     "lo_mau": cint(x.luu_lo_mau)} for x in cho],
    }
