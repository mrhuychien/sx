"""Tổng quan ATTP (W22, D148) — #/qc/attp, một màn cho Trưởng Ban ISO, Giám đốc.

Số liệu lấy từ các module QC sẵn có; đèn và câu chữ ở sx/qc/attp.py (thuần). Đèn tính từ chính
bộ số liệu của hộp nhắc (sx.api.qc._du_lieu_nhac) — tổng quan và hộp nhắc không thể nói hai điều.

Kỳ số liệu: 30 ngày tới HÔM QUA — hôm nay còn đang làm, tính vào thì sáng nào cũng "thiếu lượt".
Việc treo (hộp nhắc) và trạng thái hôm nay tính tới hôm nay.

Mảng nào site chưa migrate / lỗi → None, thẻ hiện "chưa có số liệu": một mảng hỏng không được làm
trống cả màn. Thu hồi, diễn tập truy xuất, khiếu nại đọc theo tên doctype (module qc không import
phần sx khác).
"""

import frappe
from frappe.utils import add_days, cint, flt, getdate, nowdate

from sx.api import qc as Q
from sx.api.qc_ncc import _ds as _ds_ncc
from sx.qc import attp as A
from sx.qc import khac_phuc as KP
from sx.qc import kiem_nghiem as KN
from sx.qc import kiem_xe as KX
from sx.qc import muc as M
from sx.qc import nhac as NH
from sx.qc import rework as RW
from sx.qc import tai_lieu as TL
from sx.qc import thiet_bi as TBM
from sx.qc import vai_u as VU
from sx.qc import viec_dinh_ky as VD
from sx.qc.khieu_nai import MO as KHIEU_NAI_MO
from sx.qc.nguong import nguong

SO_NGAY = 30
DIEN_TAP = "SX Dien Tap Truy Xuat"


def _thu(f):
    try:
        return f()
    except Exception:
        return None


def _vong_kiem(d, tu, den, dl):
    kpi = Q.dashboard(str(tu), str(den))
    hom = [r for r in dl["luot"] if str(r.get("ngay")) == str(d)]
    xong = {M.DAU_SANG if r.get("luot") == M.TUAN else r.get("luot") for r in hom if r.get("docstatus") == 1}
    return {"ty_le": kpi["ty_le_hoan_tat"], "so_luot": kpi["so_luot"], "can_co": kpi["can_co"],
            "ngay_thieu": len(kpi["ngay_thieu"]), "ghi_muon": kpi["ghi_muon"],
            "chua_xem_xet": kpi["chua_xem_xet"], "so_bo_sung": kpi["so_bo_sung"],
            "hom_nay_xong": len(xong & set(M.LUOT_TRONG_NGAY)),
            "hom_nay_sx": bool(Q._ngay_san_xuat(d, d, hom))}


def _su_co(d, tu, den):
    han = cint(nguong()["su_co_qua_han_ngay"])
    mo = frappe.get_all("SX Su Co", filters={"trang_thai": "Mở", "dien_tap": 0}, fields=["ngay", "muc_do"])
    ky = frappe.get_all("SX Su Co", filters={"ngay": ("between", [tu, den])}, fields=["dien_tap"])
    return {"mo": len(mo), "qua_han": sum(1 for x in mo if (d - getdate(x["ngay"])).days > han),
            "cao": sum(1 for x in mo if x.get("muc_do") == "Cao"),
            "ky": sum(1 for x in ky if not cint(x.get("dien_tap"))),
            "dien_tap": sum(1 for x in ky if cint(x.get("dien_tap")))}


def _khac_phuc(d, tu, den):
    ds = frappe.get_all(KP.PT, fields=["trang_thai", "han", "ngay", "kiem_ngay"])
    trong = lambda x: bool(x) and tu <= getdate(x) <= den  # noqa: E731
    return {"mo": sum(1 for x in ds if x.get("trang_thai") != KP.DONG),
            "qua_han": sum(1 for x in ds if KP.qua_han(x, d)),
            "cho_kiem": sum(1 for x in ds if x.get("trang_thai") == KP.CHO_KIEM),
            "lap_ky": sum(1 for x in ds if trong(x.get("ngay"))),
            "dong_ky": sum(1 for x in ds if x.get("trang_thai") == KP.DONG and trong(x.get("kiem_ngay")))}


def _khieu_nai(d, tu, den):
    han = cint(nguong()["su_co_qua_han_ngay"])
    mo = [getdate(x.get("opening_date") or x.get("creation")) for x in frappe.get_all(
        "Issue", filters={"custom_khieu_nai": 1, "status": ("in", list(KHIEU_NAI_MO))},
        fields=["opening_date", "creation"])]
    return {"mo": len(mo), "qua_han": sum(1 for x in mo if (d - x).days > han),
            "lau_nhat": max(((d - x).days for x in mo), default=0),
            "ky": frappe.db.count("Issue", {"custom_khieu_nai": 1, "opening_date": ("between", [tu, den])})}


def _xuat_xuong(tu, den, dl):
    ky = frappe.get_all("SX Kiem Tra Xuat Xuong", filters={"kiem_luc": ("between", [tu, den])},
                        fields=["trang_thai"])
    return {"cho_duyet": cint((dl.get("xuat_xuong") or {}).get("cho_duyet")),
            "duyet": sum(1 for x in ky if x.get("trang_thai") == "Đã duyệt"),
            "tra_lai": sum(1 for x in ky if x.get("trang_thai") == "Trả lại")}


def _truy_xuat(d):
    thu_hoi = _thu(lambda: frappe.db.count("Batch", {"custom_thu_hoi": 1})) or 0
    dt = frappe.get_all(DIEN_TAP, filters={"ket_thuc": ("is", "set")}, fields=["ngay", "dat", "can_bang_pt"],
                        order_by="ngay desc, ket_thuc desc", limit=1)
    return {"thu_hoi": thu_hoi,
            "dien_tap": {"ngay": str(dt[0]["ngay"]), "dat": cint(dt[0].get("dat")),
                         "can_bang_pt": flt(dt[0].get("can_bang_pt"), 2),
                         "so_ngay": (d - getdate(dt[0]["ngay"])).days} if dt else None}


def _thiet_bi(dl):
    tb = dl.get("thiet_bi")
    if not tb:                    # {} = chưa migrate
        return None
    return {"dang_dung": frappe.db.count(TBM.TB, {"thanh_ly": 0}), "qua_han": len(tb.get("qua_han") or []),
            "khong_dat": len(tb.get("khong_dat") or []), "sap_den": len(tb.get("sap_den") or []),
            "thieu_loai": list(tb.get("thieu_loai") or [])}


def _kiem_nghiem(d):
    kh = KN.ke_hoach(d)
    dem = lambda tt: sum(1 for x in kh if x["trang_thai"] == tt)  # noqa: E731
    return {"tong": len(kh), "qua_han": dem(KN.QUA_HAN), "den_han": dem(KN.DEN_HAN), "cho_kq": dem(KN.CHO_KQ),
            "khong_dat": dem(KN.HONG),
            # Đạt còn hạn = lần gửi gần nhất Đạt, chưa tới hạn lần sau (kể cả đang trong cửa sổ đến hạn).
            "dat": sum(1 for x in kh if x["ket_qua"] == KN.DAT and x["trang_thai"] in (KN.DAT_TT, KN.DEN_HAN))}


def _cat(dl):
    c = dl.get("cat")
    if not c:
        return None
    return {"co_du_lieu": c.get("co_du_lieu"), "dang_dung": bool(c.get("dang_dung")), "so_ngay": cint(c.get("so_ngay")),
            "ncc": c.get("ncc") or "", "toi_da": cint(c.get("toi_da")), "cho_kln": len(c.get("cho_kln") or [])}


def _vai_u(tu, den, dl):
    v = dl.get("vai_u")
    if not v:                     # {} = chưa migrate
        return None
    dem = {tt: frappe.db.count(VU.VAI, {"trang_thai": tt}) for tt in VU.TRANG_THAI}
    return {"dang_dung": dem[VU.DANG_DUNG], "du_phong": dem[VU.DU_PHONG], "da_loai": dem[VU.DA_LOAI],
            "so_lan": frappe.db.count(VU.PT, {"viec": ("in", VU.GIAT), "ngay": ("between", [tu, den])}),
            "lan_cuoi": v.get("lan_cuoi"), "chu_ky": cint(v.get("chu_ky")),
            "cho_ky": frappe.db.count(VU.PT, {"qc_ky_luc": ("is", "not set")})}


def _dong_vat(tu, den, dl):
    return {"dau_hieu": frappe.db.count("SX Dau Hieu Dong Vat", {"ngay": ("between", [tu, den])}),
            "khu_hai_tuan": len((dl.get("dong_vat") or {}).get("khu_hai_tuan") or [])}


def _kiem_xe(d, tu, den, dl):
    """Chuyến trong kỳ, xe không đạt; tuần (thứ Hai – Chủ nhật) ĐÃ HẾT có chuyến / có chuyến QC kiểm (W34) —
    tuần đang chạy chưa tính: QC còn tới Chủ nhật."""
    if not dl.get("kiem_xe"):         # {} = chưa migrate
        return None
    ds = KX.chuyen(KX.thu_hai(tu), den, ["name", "posting_date", "custom_xe_ket_luan", "custom_xe_qc_kiem"])
    trong = [x for x in ds if getdate(tu) <= getdate(x.posting_date) <= getdate(den)]
    tuan = KX.theo_tuan([x for x in ds if getdate(x.posting_date) < KX.thu_hai(d)])
    return {"so_chuyen": len(trong), "khong_dat": sum(1 for x in trong if x.custom_xe_ket_luan == KX.KHONG_DAT),
            "tuan": len(tuan), "tuan_qc": sum(1 for v in tuan.values() if v["so_qc"])}


def _ncc(d):
    ds = _ds_ncc(d)
    return {"tong": len(ds), "duyet": sum(1 for x in ds if x["duyet"]), "thieu": sum(1 for x in ds if x["thieu"])}


def _luu_mau(dl):
    lm = dl.get("luu_mau") or {}
    return {"dang_luu": frappe.db.count(Q.LM, {"trang_thai": "Đang lưu"}), "den_han": cint(lm.get("den_han")),
            "dot_cho": len(lm.get("dot_cho") or [])}


def _rework(tu, den):
    ds = frappe.get_all(RW.PT, filters={"ngay": ("between", [tu, den])}, fields=["ty_le"])
    return {"so": len(ds), "cao_nhat": max((flt(x.get("ty_le")) for x in ds), default=0)}


def _viec_dinh_ky(d, dl):
    vd = dl.get("viec_dinh_ky")
    if vd is None or vd == {}:
        return None
    tiep = frappe.get_all(VD.PT, filters={"ngung": 0, "han": (">=", str(d)), "doi_tuong_kn": ("is", "not set")},
                          fields=["ten", "han"], order_by="han asc", limit=1)
    return {"qua_han": len(vd.get("qua_han") or []),
            "tiep": {"ten": tiep[0]["ten"], "han": str(tiep[0]["han"])} if tiep else None}


def _tai_lieu(dl):
    """W42: tài liệu hiện hành, lượt chưa xác nhận đọc, đề nghị đang chờ, tài liệu bên ngoài (chưa soát xét)."""
    tl = dl.get("tai_lieu")
    if tl is None or tl == {}:
        return None
    ds = frappe.get_all(TL.PT, fields=["trang_thai", "nguon"])
    return {"tong": len(ds), "hien_hanh": sum(1 for x in ds if x.trang_thai == TL.HIEN_HANH),
            "ngoai": sum(1 for x in ds if x.nguon == TL.BEN_NGOAI and x.trang_thai == TL.HIEN_HANH),
            "chua_doc": frappe.db.count(TL.PT_DOC, {"doc_luc": ("is", "not set")}),
            "de_nghi": frappe.db.count(TL.PT_DN, {"trang_thai": ("in", [TL.CHO_XET, TL.CHO_DUYET])}),
            "soat_xet": len(tl.get("soat_xet") or [])}


@frappe.whitelist()
def tong_quan(ngay=None):
    """{linh_vuc: [thẻ], dem: {do, vang, xanh}, ngay, tu, den} — xem sx/qc/attp.py."""
    Q._guard_manager()
    d = getdate(ngay) if ngay else getdate(nowdate())
    tu, den = add_days(d, -SO_NGAY), add_days(d, -1)
    dl = Q._du_lieu_nhac(d)
    so = {
        "vong_kiem": _thu(lambda: _vong_kiem(d, tu, den, dl)),
        "su_co": _thu(lambda: _su_co(d, tu, den)),
        "khac_phuc": _thu(lambda: _khac_phuc(d, tu, den)),
        "khieu_nai": _thu(lambda: _khieu_nai(d, tu, den)),
        "xuat_xuong": _thu(lambda: _xuat_xuong(tu, den, dl)),
        "truy_xuat": _thu(lambda: _truy_xuat(d)),
        "thiet_bi": _thu(lambda: _thiet_bi(dl)),
        "kiem_nghiem": _thu(lambda: _kiem_nghiem(d)),
        "cat": _thu(lambda: _cat(dl)),
        "vai_u": _thu(lambda: _vai_u(tu, den, dl)),
        "dong_vat": _thu(lambda: _dong_vat(tu, den, dl)),
        "ncc": _thu(lambda: _ncc(d)),
        "kiem_xe": _thu(lambda: _kiem_xe(d, tu, den, dl)),
        "luu_mau": _thu(lambda: _luu_mau(dl)),
        "rework": _thu(lambda: _rework(tu, den)),
        "viec_dinh_ky": _thu(lambda: _viec_dinh_ky(d, dl)),
        "tai_lieu": _thu(lambda: _tai_lieu(dl)),
    }
    return dict(A.tong_hop(NH.tinh(d, **dl), so), ngay=str(d), tu=str(tu), den=str(den), so_ngay=SO_NGAY)
