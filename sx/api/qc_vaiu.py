"""API màn "Sổ giặt vải ủ" BM.08.05 (QC → Hôm nay → 🧺) — W29, D163.

Mỗi việc một dòng: giặt định kỳ / giặt ngoài lịch / nhập vải mới / loại vải. QC ghi hộ người giặt và
KÝ; QLSX, Ban ISO khai danh mục vải; Trưởng Ban ISO xem tháng. Luật ở sx/qc/vai_u.py và controller
SX Giat Vai / SX Vai U (chặn cả Desk).
"""

import json
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime, nowdate

from sx.api.qc import GHI_DUOC, ISO, QLSX, _guard_ghi, _guard_manager, _guard_qc, _roles, _sieu
from sx.qc import vai_u as VU
from sx.qc.quyen import la_iso

TRUONG = ["name", "ngay", "viec", "so_luong", "ly_do", "gio_soi_lai", "gio_vot", "so_phut", "phoi_tai",
          "cat_luc", "nguoi_lam", "ghi_boi", "su_co", "qc_ky_boi", "qc_ky_luc", "xem_boi", "xem_luc",
          "xem_nhan_xet", "creation"]
TRUONG_VAI = ["name", "thung", "trang_thai", "ngay_nhap", "dong_nhap", "ngay_loai", "ly_do_loai", "dong_loai",
              "ghi_chu"]
KHAI_VAI = {QLSX, ISO}
SO_NGAY_SU_CO = 30     # phiếu sự cố gắn được vào dòng sổ: lập trong chừng này ngày


def _thang(thang=None):
    dau = getdate(f"{thang}-01") if thang else getdate(nowdate()).replace(day=1)
    cuoi = dau.replace(day=28) + timedelta(days=4)
    return dau, cuoi - timedelta(days=cuoi.day)


def _guard_khai():
    """Khai / sửa danh mục vải: QLSX, Ban ISO (HD.08.02 mục 10: QLSX bố trí đủ vải)."""
    _guard_qc()
    if not (_sieu() or _roles() & KHAI_VAI):
        frappe.throw(_("Chỉ QLSX hoặc Ban ISO khai danh mục vải ủ."), frappe.PermissionError)


def _ten_nguoi(u, nho):
    if not u:
        return ""
    if u not in nho:
        nho[u] = frappe.db.get_value("User", u, "full_name") or u
    return nho[u]


def _dong(x, ma, nho):
    # so_phut tính lại từ hai ô giờ: ô Int trên DB không để trống được (thiếu giờ thì lưu 0).
    return dict(x, ngay=str(x.ngay), gio_soi_lai=VU.gio(x.gio_soi_lai), gio_vot=VU.gio(x.gio_vot),
                so_phut=VU.so_phut(x.gio_soi_lai, x.gio_vot),
                cat_luc=str(x.cat_luc or "")[:16], qc_ky_luc=str(x.qc_ky_luc or "")[:16],
                xem_luc=str(x.xem_luc or "")[:16], creation=str(x.creation or "")[:10],
                so_luong=cint(x.so_luong), vai=ma.get(x.name, []),
                ten_ky=_ten_nguoi(x.qc_ky_boi, nho), ten_xem=_ten_nguoi(x.xem_boi, nho))


def _ds(tu, den):
    """Dòng sổ từ `tu` tới `den` (cũ trước), kèm mã vải và tên người ký."""
    ds = frappe.get_all(VU.PT, filters={"ngay": ("between", [str(tu), str(den)])}, fields=TRUONG,
                        order_by="ngay asc, creation asc")
    ma = VU.ma_cua([x.name for x in ds])
    nho = {}
    return [_dong(x, ma, nho) for x in ds]


def _xem(ds):
    """Lần Trưởng Ban ISO xem gần nhất trong các dòng."""
    x = max((x for x in ds if x["xem_luc"]), key=lambda x: x["xem_luc"], default=None)
    return {"boi": x["xem_boi"], "ten": x["ten_xem"], "luc": x["xem_luc"],
            "nhan_xet": x.get("xem_nhan_xet") or ""} if x else None


def _su_co_gan(hom_nay):
    try:
        return [dict(x, ngay=str(x.ngay), mo_ta=(x.mo_ta or "")[:80]) for x in frappe.get_all(
            "SX Su Co", filters={"ngay": (">=", str(hom_nay - timedelta(days=SO_NGAY_SU_CO)))},
            fields=["name", "ngay", "mo_ta"], order_by="ngay desc", limit=30)]
    except Exception:
        return []


@frappe.whitelist()
def tong_quan(thang=None):
    """Dòng sổ của tháng (mới trước), danh mục vải, lần giặt gần nhất, cài đặt, quyền của người xem."""
    _guard_qc()
    dau, cuoi = _thang(thang)
    hom_nay = getdate(nowdate())
    ds = _ds(dau, cuoi)
    vai = frappe.get_all(VU.VAI, fields=TRUONG_VAI, order_by="name asc")
    nh = VU.nhac(hom_nay)
    phoi = frappe.get_all(VU.PT, filters={"phoi_tai": ("is", "set")}, fields=["phoi_tai"],
                          order_by="ngay desc, creation desc", limit=1)
    roles = _roles()
    return {
        "thang": dau.strftime("%Y-%m"), "hom_nay": str(hom_nay),
        "ds": list(reversed(ds)),
        "vai": [dict(x, ma=x.name, ngay_nhap=str(x.ngay_nhap or ""), ngay_loai=str(x.ngay_loai or "")) for x in vai],
        "lan_cuoi": nh.get("lan_cuoi"), "chu_ky": nh.get("chu_ky") or VU.CHU_KY,
        "cai_dat": VU.cai_dat(),
        "phoi_tai": phoi[0].phoi_tai if phoi else "",
        "xem": _xem(ds), "chua_xem": sum(1 for x in ds if not x["xem_luc"]),
        "chua_ky": sum(1 for x in ds if not x["qc_ky_luc"]),
        "su_co": _su_co_gan(hom_nay),
        "viec": list(VU.VIEC), "phut_soi": VU.PHUT_SOI,
        "duoc_ghi": bool(_sieu(roles) or roles & GHI_DUOC),
        "duoc_khai_vai": bool(_sieu(roles) or roles & KHAI_VAI),
        "duoc_xem_thang": bool(_sieu(roles) or ISO in roles),
        "la_iso": la_iso(),
        "user": frappe.session.user,
    }


def _ds_ma(v):
    """Mã vải từ màn: danh sách hoặc chuỗi "V01-A, V01-B" → [mã chuẩn], bỏ trùng, giữ thứ tự."""
    if isinstance(v, str):
        v = v.replace(";", ",").split(",")
    ra = []
    for m in v or []:
        m = VU.chuan_ma(m)
        if m and m not in ra:
            ra.append(m)
    return ra


def _gio(v):
    p = VU.gio(v)
    return f"{p}:00" if p else None


def _luc(v):
    """"2026-10-09T15:30" (ô datetime-local) → "2026-10-09 15:30:00"."""
    v = str(v or "").strip().replace("T", " ")
    if not v:
        return None
    return v if len(v) > 16 else f"{v[:16]}:00"


@frappe.whitelist()
def ghi(payload):
    """Ghi / sửa một dòng; `ky` = 1 thì QC ký luôn (đủ điều kiện ký mới lưu).

    Nhập vải mới: mã chưa có trong danh mục thì thêm vào (Dự phòng) TRƯỚC khi lưu dòng — ô mã vải là
    liên kết tới danh mục. Việc khác: mã phải có sẵn (QLSX / Ban ISO khai)."""
    _guard_ghi()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    doc = frappe.get_doc(VU.PT, p["name"]) if p.get("name") else frappe.get_doc({"doctype": VU.PT})
    ma = _ds_ma(p.get("vai"))
    doc.ngay = getdate(p.get("ngay") or nowdate())
    doc.viec = p.get("viec") or ""
    doc.so_luong = max(0, cint(p.get("so_luong")))
    doc.ly_do = (p.get("ly_do") or "").strip()
    doc.gio_soi_lai = _gio(p.get("gio_soi_lai"))
    doc.gio_vot = _gio(p.get("gio_vot"))
    doc.phoi_tai = (p.get("phoi_tai") or "").strip()
    doc.cat_luc = _luc(p.get("cat_luc"))
    doc.nguoi_lam = (p.get("nguoi_lam") or "").strip()
    doc.su_co = p.get("su_co") or None
    x = dict(doc.as_dict(), vai=ma)
    # Báo lỗi dòng TRƯỚC khi thêm vải vào danh mục — dòng hỏng thì danh mục không đổi.
    loi = VU.loi_dong(x, nowdate()) or (VU.loi_ky(x) if cint(p.get("ky")) else None)
    if loi:
        frappe.throw(_(loi))
    thieu = [m for m in ma if not frappe.db.exists(VU.VAI, m)]
    if thieu and doc.viec != VU.NHAP:
        frappe.throw(_("Vải {0} chưa có trong danh mục — QLSX / Ban ISO khai ở tab Danh mục vải (vải mới mua về "
                       "thì chọn việc Nhập vải mới).").format(", ".join(thieu)))
    for m in thieu:
        frappe.get_doc({"doctype": VU.VAI, "ma": m, "trang_thai": VU.DU_PHONG, "ngay_nhap": doc.ngay}).insert(
            ignore_permissions=True)
    doc.set("vai", [{"vai": m} for m in ma])
    if cint(p.get("ky")) and not doc.qc_ky_luc:
        doc.qc_ky_boi = frappe.session.user
        doc.qc_ky_luc = now_datetime()
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return {"name": doc.name, "so_phut": doc.so_phut, "da_ky": bool(doc.qc_ky_luc), "vai_moi": thieu,
            "chua_ky_duoc": None if doc.qc_ky_luc else VU.loi_ky(dict(doc.as_dict(), vai=ma))}


@frappe.whitelist()
def ky(name):
    """QC ký một dòng. Giặt mà đun chưa đủ 10 phút / chưa ghi chỗ phơi, giờ cất → không ký được."""
    _guard_ghi()
    doc = frappe.get_doc(VU.PT, name)
    if doc.qc_ky_luc:
        frappe.throw(_("Dòng này đã ký ({0}).").format(doc.qc_ky_boi or ""))
    loi = VU.loi_ky(dict(doc.as_dict(), vai=[r.get("vai") for r in doc.get("vai") or []]))
    if loi:
        frappe.throw(_(loi))
    doc.qc_ky_boi = frappe.session.user
    doc.qc_ky_luc = now_datetime()
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "qc_ky_luc": str(doc.qc_ky_luc)[:16]}


@frappe.whitelist()
def xoa(name):
    """Ghi nhầm cả dòng: người ghi xoá được trong ngày (chưa ký); Ban ISO xoá được bất cứ lúc nào."""
    _guard_qc()
    x = frappe.db.get_value(VU.PT, name, ["ghi_boi", "creation", "qc_ky_luc"], as_dict=True)
    if not x:
        frappe.throw(_("Không có dòng {0}.").format(name))
    if not la_iso() and not (x.ghi_boi == frappe.session.user and not x.qc_ky_luc
                             and getdate(x.creation) == getdate(nowdate())):
        frappe.throw(_("Chỉ người ghi (trong ngày, khi chưa ký) hoặc Ban ISO xoá được dòng này."),
                     frappe.PermissionError)
    frappe.delete_doc(VU.PT, name, ignore_permissions=True)
    return {"name": name}


@frappe.whitelist()
def luu_vai(payload):
    """QLSX / Ban ISO khai một vải: mã, thùng, Đang dùng / Dự phòng, ngày nhập, ghi chú. Loại vải thì
    QC ghi dòng Loại vải trong sổ (controller SX Vai U chặn loại tay)."""
    _guard_khai()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    ma = VU.chuan_ma(p.get("ma"))
    if not ma:
        frappe.throw(_("Ghi mã vải (vd V01-A)."))
    doc = frappe.get_doc(VU.VAI, ma) if frappe.db.exists(VU.VAI, ma) else frappe.get_doc(
        {"doctype": VU.VAI, "ma": ma})
    if p.get("moi") and not doc.is_new():
        frappe.throw(_("Vải {0} đã có trong danh mục ({1}).").format(ma, (doc.trang_thai or "").lower()))
    doc.thung = (p.get("thung") or "").strip()
    doc.trang_thai = p.get("trang_thai") or doc.trang_thai or VU.DU_PHONG
    if "ngay_nhap" in p:
        doc.ngay_nhap = p.get("ngay_nhap") or None
    doc.ghi_chu = (p.get("ghi_chu") or "").strip()
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return {"ma": doc.name, "thung": doc.thung, "trang_thai": doc.trang_thai}


@frappe.whitelist()
def xoa_vai(ma):
    """Khai nhầm một vải: xoá khỏi danh mục khi chưa dòng sổ nào ghi tới nó. Đã vào sổ thì là hồ sơ —
    hỏng thì loại (dòng Loại vải), không xoá."""
    _guard_khai()
    if frappe.get_all(VU.CON, filters={"parenttype": VU.PT, "vai": ma}, limit=1):
        frappe.throw(_("Vải {0} đã có trong sổ giặt — không xoá được. Vải hỏng thì ghi dòng Loại vải.").format(ma))
    frappe.delete_doc(VU.VAI, ma, ignore_permissions=True)
    return {"ma": ma}


@frappe.whitelist()
def xem_thang(thang, nhan_xet=None):
    """Trưởng Ban ISO: "Đã xem tháng MM/YYYY" + nhận xét — ký mọi dòng chưa xem của tháng (HD.08.02 mục 9).
    Dòng ghi bù sau đó chưa được xem → hộp nhắc lại nhắc tháng đó."""
    _guard_manager()
    dau, cuoi = _thang(thang)
    if dau > getdate(nowdate()):
        frappe.throw(_("Tháng {0} chưa tới.").format(dau.strftime("%m/%Y")))
    ds = frappe.get_all(VU.PT, filters={"ngay": ("between", [str(dau), str(cuoi)]), "xem_luc": ("is", "not set")},
                        pluck="name")
    if not ds:
        frappe.throw(_("Tháng {0} không có dòng nào chưa xem.").format(dau.strftime("%m/%Y")))
    luc = now_datetime()
    for n in ds:
        frappe.db.set_value(VU.PT, n, {"xem_boi": frappe.session.user, "xem_luc": luc,
                                       "xem_nhan_xet": (nhan_xet or "").strip()}, update_modified=False)
    return {"so": len(ds), "thang": dau.strftime("%m/%Y")}


@frappe.whitelist()
def in_bm0805(thang=None):
    """BM.08.05 — sổ giặt vải ủ của một tháng, đúng cột giấy (A4 ngang)."""
    _guard_qc()
    dau, cuoi = _thang(thang)
    ds = _ds(dau, cuoi)
    return frappe.render_template("sx/qc/bm0805.html", {
        "thang": dau.strftime("%m/%Y"), "ds": ds, "xem": _xem(ds), "cd": VU.cai_dat(), "phut_soi": VU.PHUT_SOI})
