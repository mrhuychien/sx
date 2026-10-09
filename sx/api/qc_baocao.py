"""Báo cáo tháng ATTP, chỉ tiêu ATTP (W25, D151) — #/qc/baocao, nút trong tab Xem xét.

Chỉ số từng tháng từ đầu năm tới tháng báo cáo + chỉ số tại ngày lập + chỉ tiêu Ban ISO đặt
(sx/qc/bao_cao.py). Số liệu tính tới HÔM QUA: tháng đang chạy dừng ở hôm qua (hôm nay còn đang làm).
Mỗi loại hồ sơ đọc MỘT lần cho cả năm rồi chia theo tháng — báo cáo 12 tháng không được thành vài trăm
truy vấn. Loại hồ sơ nào site chưa có (chưa migrate) thì chỉ số đó trống "—", chỉ số khác vẫn đủ.
"""

import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from sx.api import qc as Q
from sx.api import qc_attp
from sx.api.qc_ncc import _ds as _ds_ncc
from sx.qc import bao_cao as BC
from sx.qc import khac_phuc as KP
from sx.qc import kiem_nghiem as KN
from sx.qc import muc as M
from sx.qc import thiet_bi as TBM
from sx.qc.nguong import nguong
from sx.qc.quyen import la_iso

DEM = ("ngay_thieu_luot", "nhap_lai_giay", "su_co", "su_co_cao", "khieu_nai", "rework", "dong_vat")
TY_LE = ("ty_le_luot", "ty_le_dung_gio", "su_co_dung_han", "kn_dat", "xx_duyet", "kp_dung_han")
# Chỉ số → loại hồ sơ nó đọc: hồ sơ đó lỗi (chưa migrate) thì các chỉ số này trống, không phải 0.
NGUON = {"luot": ("ty_le_luot", "ty_le_dung_gio", "ngay_thieu_luot", "nhap_lai_giay"),
         "su_co": ("su_co", "su_co_cao", "su_co_dung_han"), "khieu_nai": ("khieu_nai",), "kn": ("kn_dat",),
         "xx": ("xx_duyet",), "rework": ("rework",), "dong_vat": ("dong_vat",), "kp": ("kp_dung_han",)}


def _ky(thang=None):
    """(YYYY-MM, đầu năm, đầu tháng, ngày cắt). Mặc định tháng trước; ngày cắt = cuối tháng, không quá hôm qua."""
    hom_qua = getdate(nowdate()) - timedelta(days=1)
    if thang:
        try:
            dau = getdate(f"{str(thang)[:7]}-01")
        except Exception:
            frappe.throw(_("Tháng không hợp lệ: {0}").format(thang))
    else:
        dau = (getdate(nowdate()).replace(day=1) - timedelta(days=1)).replace(day=1)
    cuoi = (dau.replace(day=28) + timedelta(days=4))
    cuoi = cuoi - timedelta(days=cuoi.day)
    if dau > hom_qua:
        frappe.throw(_("Tháng {0} chưa có số liệu — báo cáo tính tới hết hôm qua.").format(dau.strftime("%m/%Y")))
    return f"{dau.year}-{dau.month:02d}", dau.replace(month=1), dau, min(cuoi, hom_qua)


def _t(x):
    return str(x)[:7] if x else None


def _khung(thang):
    """{YYYY-MM: {chỉ số: 0 / (0, 0)}} cho mọi tháng từ đầu năm — tháng không có việc gì là 0, không phải trống."""
    return {t: dict({m: 0 for m in DEM}, **{m: (0, 0) for m in TY_LE}) for t in BC.thang_tu_dau_nam(thang)}


def _luot(tt, nam_dau, cat):
    rounds = frappe.get_all("SX QC Round", filters={"ngay": ("between", [nam_dau, cat]), "docstatus": 1},
                            fields=["ngay", "luot", "ghi_muon", "nhap_lai_tu_giay"])
    nhap = frappe.get_all("SX QC Round", filters={"ngay": ("between", [nam_dau, cat]), "docstatus": 0},
                          fields=["ngay"])
    ngay_sx = Q._ngay_san_xuat(nam_dau, cat, list(rounds) + list(nhap))
    chinh = {}
    for r in rounds:
        if r.get("luot") != M.BO_SUNG:       # W23: lượt bổ sung không thay lượt nào
            chinh[str(r["ngay"])] = chinh.get(str(r["ngay"]), 0) + 1
    can = len(M.LUOT_TRONG_NGAY)
    for t, o in tt.items():
        sx_t = [d for d in ngay_sx if d[:7] == t]
        r_t = [r for r in rounds if _t(r["ngay"]) == t]
        so = sum(n for d, n in chinh.items() if d[:7] == t)
        o["ty_le_luot"] = (min(so, can * len(sx_t)), can * len(sx_t))
        o["ty_le_dung_gio"] = (len(r_t) - sum(cint(r.get("ghi_muon")) for r in r_t), len(r_t))
        o["ngay_thieu_luot"] = sum(1 for d in sx_t if chinh.get(d, 0) < can)
        o["nhap_lai_giay"] = sum(cint(r.get("nhap_lai_tu_giay")) for r in r_t)


def _su_co(tt, nam_dau, cat):
    han = cint(nguong()["su_co_qua_han_ngay"])
    nay = getdate(nowdate())
    for x in frappe.get_all("SX Su Co", filters={"ngay": ("between", [nam_dau, cat]), "dien_tap": 0},
                            fields=["ngay", "muc_do", "trang_thai", "dong_ngay"]):
        o = tt.get(_t(x["ngay"]))
        if o is None:
            continue
        o["su_co"] += 1
        o["su_co_cao"] += 1 if x.get("muc_do") == "Cao" else 0
        if x.get("trang_thai") == "Đóng" and x.get("dong_ngay"):
            o["su_co_dung_han"] = (o["su_co_dung_han"][0] + ((getdate(x["dong_ngay"]) - getdate(x["ngay"])).days <= han),
                                   o["su_co_dung_han"][1] + 1)
        elif (nay - getdate(x["ngay"])).days > han:      # còn mở, đã quá hạn → trễ
            o["su_co_dung_han"] = (o["su_co_dung_han"][0], o["su_co_dung_han"][1] + 1)


def _dem_theo(tt, ma, ngay_ds):
    for n in ngay_ds:
        o = tt.get(_t(n))
        if o is not None:
            o[ma] += 1


def _ty_le_theo(tt, ma, cap):
    """`cap` = [(ngày, đạt?)] → cộng (tử, mẫu) vào tháng của ngày."""
    for n, dat in cap:
        o = tt.get(_t(n))
        if o is not None:
            o[ma] = (o[ma][0] + (1 if dat else 0), o[ma][1] + 1)


def _theo_thang(thang, nam_dau, cat):
    """{YYYY-MM: {chỉ số: giá trị thô}} từ đầu năm tới tháng báo cáo (cắt ở `cat`)."""
    tt = _khung(thang)
    giua = ("between", [nam_dau, cat])
    viec = {
        "luot": lambda: _luot(tt, nam_dau, cat),
        "su_co": lambda: _su_co(tt, nam_dau, cat),
        "khieu_nai": lambda: _dem_theo(tt, "khieu_nai", frappe.get_all(
            "Issue", filters={"custom_khieu_nai": 1, "opening_date": giua}, pluck="opening_date")),
        "kn": lambda: _ty_le_theo(tt, "kn_dat", [(x["ngay_kq"], x["ket_qua"] == KN.DAT) for x in frappe.get_all(
            KN.PT, filters={"doi_tuong": KN.SAN_PHAM, "ngay_kq": giua, "ket_qua": ("is", "set")},
            fields=["ngay_kq", "ket_qua"])]),
        "xx": lambda: _ty_le_theo(tt, "xx_duyet", [
            (x.get("duyet_luc") or x.get("kiem_luc"), x["trang_thai"] == "Đã duyệt") for x in frappe.get_all(
                "SX Kiem Tra Xuat Xuong", filters={"trang_thai": ("in", ["Đã duyệt", "Trả lại"])},
                fields=["trang_thai", "duyet_luc", "kiem_luc"])
            if (x.get("duyet_luc") or x.get("kiem_luc"))
            and nam_dau <= getdate(x.get("duyet_luc") or x.get("kiem_luc")) <= cat]),
        "rework": lambda: _dem_theo(tt, "rework", frappe.get_all("SX Rework", filters={"ngay": giua}, pluck="ngay")),
        "dong_vat": lambda: _dem_theo(tt, "dong_vat", frappe.get_all(
            "SX Dau Hieu Dong Vat", filters={"ngay": giua}, pluck="ngay")),
        # Đúng hạn = ngày làm xong (không phải ngày Ban ISO kiểm) ≤ hạn; phiếu không đặt hạn không tính.
        "kp": lambda: _ty_le_theo(tt, "kp_dung_han", [
            (x["kiem_ngay"], getdate(x.get("ngay_xong") or x["kiem_ngay"]) <= getdate(x["han"])) for x in frappe.get_all(
                KP.PT, filters={"trang_thai": KP.DONG, "kiem_ngay": giua}, fields=["kiem_ngay", "ngay_xong", "han"])
            if x.get("han")]),
    }
    for nguon, f in viec.items():
        try:
            f()
        except Exception:
            for o in tt.values():
                for ma in NGUON[nguon]:
                    o[ma] = None
    return tt


def _hien_tai(d):
    """Chỉ số tại ngày lập (tử, mẫu)."""
    ra = {}
    try:
        tb = TBM.nhac(d)
        if tb:
            tong = frappe.db.count(TBM.TB, {"thanh_ly": 0})
            ra["tb_con_han"] = (tong - len(tb.get("qua_han") or []) - len(tb.get("khong_dat") or []), tong)
    except Exception:
        pass
    try:
        kh = KN.ke_hoach(d)
        ra["kn_con_han"] = (sum(1 for x in kh if x["ket_qua"] == KN.DAT and x["trang_thai"] in (KN.DAT_TT, KN.DEN_HAN)),
                            len(kh))
    except Exception:
        pass
    try:
        ds = _ds_ncc(d)
        ra["ncc_duyet"] = (sum(1 for x in ds if x["duyet"]), len(ds))
    except Exception:
        pass
    return ra


def _du_lieu(thang=None):
    t, nam_dau, dau, cat = _ky(thang)
    bang = BC.bang(_theo_thang(t, nam_dau, cat), _hien_tai(getdate(nowdate())), t)
    ds_ct = frappe.get_all(BC.PT, filters={"nam": int(t[:4])},
                           fields=["name", "nam", "chi_so", "ten", "so_sanh", "muc_tieu", "ngung", "ghi_chu"],
                           order_by="creation asc")
    return {"thang": t, "nam": int(t[:4]), "dau": str(dau), "cat": str(cat), "bang": bang,
            "chi_tieu": BC.chi_tieu(ds_ct, bang), "ds_chi_tieu": ds_ct}


@frappe.whitelist()
def so_lieu(thang=None):
    """Bảng chỉ số (theo tháng từ đầu năm + lũy kế + tại ngày lập) và chỉ tiêu của năm."""
    Q._guard_manager()
    return dict(_du_lieu(thang), chi_so=[{"ma": x[0], "ten": x[1], "don_vi": x[2], "kieu": x[3]} for x in BC.CHI_SO],
                duoc_sua=bool(la_iso()), hom_nay=nowdate())


@frappe.whitelist()
def luu_chi_tieu(payload):
    """Thêm / sửa chỉ tiêu ATTP năm (Ban ISO, quản lý)."""
    Q._guard_manager()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    doc = frappe.get_doc(BC.PT, p["name"]) if p.get("name") else frappe.new_doc(BC.PT)
    for f in ("nam", "chi_so", "ten", "so_sanh", "ngung", "ghi_chu"):
        if f in p:
            doc.set(f, cint(p[f]) if f in ("nam", "ngung") else p[f])
    if "muc_tieu" in p:
        doc.muc_tieu = None if str(p["muc_tieu"]).strip() == "" else flt(p["muc_tieu"])
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return {"name": doc.name}


@frappe.whitelist()
def xoa_chi_tieu(name):
    Q._guard_manager()
    frappe.delete_doc(BC.PT, name, ignore_permissions=True)
    return {"ok": 1}


def _chi_tiet(dau, cat):
    """Danh sách trong tháng báo cáo: sự cố, khiếu nại, khắc phục, kết quả kiểm nghiệm."""
    giua = ("between", [dau, cat])
    ra = {}
    for ten, f in {
        "su_co": lambda: frappe.get_all("SX Su Co", filters={"ngay": giua, "dien_tap": 0}, order_by="ngay asc",
                                        fields=["name", "ngay", "cong_doan", "loai", "muc_do", "mo_ta", "trang_thai",
                                                "car_so"]),
        "khieu_nai": lambda: frappe.get_all("Issue", filters={"custom_khieu_nai": 1, "opening_date": giua},
                                            fields=["name", "opening_date", "customer_name", "custom_phan_loai_kn",
                                                    "status", "subject"], order_by="opening_date asc"),
        "khac_phuc": lambda: [x for x in frappe.get_all(
            KP.PT, fields=["name", "ngay", "mo_ta", "trang_thai", "han", "ngay_xong", "kiem_ngay", "hieu_luc"],
            order_by="ngay asc")
            if dau <= getdate(x["ngay"]) <= cat or (x.get("kiem_ngay") and dau <= getdate(x["kiem_ngay"]) <= cat)
            or KP.qua_han(x, getdate(nowdate()))],
        "kiem_nghiem": lambda: frappe.get_all(KN.PT, filters={"ngay_kq": giua, "ket_qua": ("is", "set")},
                                              fields=["name", "doi_tuong", "ten_san_pham", "mo_ta_mau", "ngay_gui",
                                                      "ngay_kq", "ket_qua", "so_phieu"], order_by="ngay_kq asc"),
    }.items():
        try:
            ra[ten] = f()
        except Exception:
            ra[ten] = None
    return ra


@frappe.whitelist()
def in_bao_cao(thang=None):
    """HTML A4 ngang — báo cáo ATTP tháng: chỉ tiêu, chỉ số 12 tháng, sự cố, khiếu nại, khắc phục, kiểm
    nghiệm, việc đang treo tại ngày lập. Cho họp xem xét của lãnh đạo."""
    Q._guard_manager()
    dl = _du_lieu(thang)
    try:
        treo = [x for x in qc_attp.tong_quan()["linh_vuc"] if x["den"] != "xanh"]
    except Exception:
        treo = []
    return frappe.render_template("sx/qc/bao_cao_thang.html", dict(
        dl, ct=_chi_tiet(getdate(dl["dau"]), getdate(dl["cat"])), treo=treo, hien=BC.hien,
        cac_thang=BC.thang_tu_dau_nam(dl["thang"]), lap_luc=now_datetime().strftime("%d/%m/%Y %H:%M"),
        nguoi=frappe.session.user, KP=KP))
