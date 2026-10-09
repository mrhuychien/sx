"""API màn "Thiết bị đo" BM.06.01–06.04 (QC → Hôm nay → 🌡) — W17, D143.

Danh mục thiết bị, ghi một lần kiểm / hiệu chuẩn / kiểm định, lịch sử, bản in. Luật ở
sx/qc/thiet_bi.py và hai controller (chặn cả Desk).
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from sx.api.qc import GHI_DUOC, ISO, _guard_qc, _roles, _sieu
from sx.qc import thiet_bi as TBM
from sx.qc.quyen import la_iso

TRUONG_KT = ["name", "thiet_bi", "ten_thiet_bi", "loai", "ngay", "hinh_thuc", "chuan_1", "doc_1", "chuan_2",
             "doc_2", "sai_so_cho_phep", "sai_so", "be_mat", "luc_hut", "luc_hut_gauss", "nguyen_ven",
             "mat_luoi", "khung", "so_giay", "don_vi", "han_giay", "ket_qua", "ghi_chu", "nguoi_kiem",
             "su_co", "creation"]
GHI_KT = ("hinh_thuc", "chuan_1", "doc_1", "chuan_2", "doc_2", "be_mat", "luc_hut", "nguyen_ven", "mat_luoi",
          "khung", "so_giay", "don_vi", "ket_qua", "ghi_chu")
TEN_BM = {"BM.06.02": "Kiểm tra, hiệu chuẩn đồng hồ nhiệt", "BM.06.03": "Kiểm tra nam châm",
          "BM.06.04": "Kiểm tra lưới sàng, rây"}


def _duoc_ghi():
    return bool(_sieu() or _roles() & GHI_DUOC or ISO in _roles())


def _guard_tb():
    _guard_qc()
    if not _duoc_ghi():
        frappe.throw(_("Chỉ QC hoặc Ban ISO ghi thiết bị đo."), frappe.PermissionError)


def _ds_thiet_bi(hom_nay):
    hd = TBM.han_dau()
    cuoi, giay = TBM.cac_lan_cuoi()
    ra = []
    for t in frappe.get_all(TBM.TB, fields=["name", "ten", "loai", "vi_tri", "may", "chu_ky_thang", "thanh_ly",
                                            "ghi_chu", "qua_han_su_co"], order_by="name asc"):
        c = cuoi.get(t.name)
        tt, han = TBM.trang_thai(t, c, hom_nay, hd, giay.get(t.name))
        ra.append(dict(t, trang_thai=tt, han=str(han), con=(han - hom_nay).days, chu_ky=TBM.chu_ky(t),
                       lan_cuoi=str(c.ngay) if c else "", ket_qua_cuoi=c.ket_qua if c else "",
                       chua_kiem=not c, bieu_mau=TBM.BIEU_MAU.get(t.loai, "")))
    return ra


@frappe.whitelist()
def tong_quan():
    """Danh mục kèm trạng thái tính TẠI LÚC XEM (không đợi lịch chạy nền)."""
    _guard_qc()
    d = getdate(nowdate())
    try:
        cc = frappe.get_cached_doc("SX QC Setting").get("chung_chi_dong_ho") or ""
    except Exception:
        cc = ""
    return {"ds": _ds_thiet_bi(d), "loai": list(TBM.LOAI), "bieu_mau": TBM.BIEU_MAU, "han_dau": str(TBM.han_dau()),
            "hom_nay": str(d), "sap_den": TBM.SAP_DEN, "chung_chi": cc, "duoc_ghi": _duoc_ghi(),
            "la_iso": la_iso(), "user": frappe.session.user}


@frappe.whitelist()
def luu_thiet_bi(payload):
    """Thêm / sửa một thiết bị trong danh mục."""
    _guard_tb()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    if p.get("loai") not in TBM.LOAI:
        frappe.throw(_("Chọn loại thiết bị."))
    if not (p.get("ten") or "").strip():
        frappe.throw(_("Nhập tên thiết bị."))
    if p.get("name"):
        doc = frappe.get_doc(TBM.TB, p["name"])
    else:
        ma = (p.get("ma") or "").strip().upper()
        if frappe.db.exists(TBM.TB, ma):
            frappe.throw(_("Đã có thiết bị mã {0}.").format(ma))
        doc = frappe.get_doc({"doctype": TBM.TB, "ma": ma})
    for f in ("ten", "loai", "vi_tri", "may", "ghi_chu"):
        doc.set(f, (p.get(f) or "").strip())
    doc.chu_ky_thang = cint(p.get("chu_ky_thang"))
    doc.thanh_ly = 1 if cint(p.get("thanh_ly")) else 0
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return {"name": doc.name, "trang_thai": doc.trang_thai, "han": str(doc.han_kiem or "")}


@frappe.whitelist()
def lich_su(thiet_bi):
    _guard_qc()
    return [dict(x, ngay=str(x.ngay), han_giay=str(x.han_giay or ""), creation=str(x.creation or "")[:10])
            for x in frappe.get_all(TBM.KT, filters={"thiet_bi": thiet_bi}, fields=TRUONG_KT,
                                    order_by="ngay desc, creation desc", limit=20)]


@frappe.whitelist()
def ghi_kiem(payload):
    """Ghi một lần kiểm. Không đạt → thiết bị ngừng dùng + phiếu sự cố (controller)."""
    _guard_tb()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    if not frappe.db.exists(TBM.TB, p.get("thiet_bi") or ""):
        frappe.throw(_("Không có thiết bị {0}.").format(p.get("thiet_bi")))
    doc = frappe.get_doc({"doctype": TBM.KT, "thiet_bi": p["thiet_bi"],
                          "ngay": getdate(p.get("ngay") or nowdate()),
                          **{f: (str(p.get(f)).strip() if p.get(f) is not None else "") for f in GHI_KT}})
    doc.hinh_thuc = doc.hinh_thuc or TBM.NOI_BO
    if p.get("sai_so_cho_phep") not in (None, ""):
        doc.sai_so_cho_phep = float(str(p["sai_so_cho_phep"]).replace(",", "."))
    if p.get("luc_hut_gauss") not in (None, ""):
        doc.luc_hut_gauss = float(str(p["luc_hut_gauss"]).replace(",", "."))
    if p.get("han_giay"):
        doc.han_giay = getdate(p["han_giay"])
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "ket_qua": doc.ket_qua, "su_co": doc.su_co,
            "trang_thai": frappe.db.get_value(TBM.TB, doc.thiet_bi, "trang_thai")}


@frappe.whitelist()
def xoa_kiem(name):
    """Ghi nhầm: người ghi xoá được trong ngày ghi; Ban ISO xoá được bất cứ lúc nào."""
    _guard_tb()
    x = frappe.db.get_value(TBM.KT, name, ["nguoi_kiem", "creation"], as_dict=True)
    if not x:
        frappe.throw(_("Không có phiếu {0}.").format(name))
    if not la_iso() and not (x.nguoi_kiem == frappe.session.user
                             and getdate(x.creation) == getdate(nowdate())):
        frappe.throw(_("Chỉ người ghi (trong ngày) hoặc Ban ISO xoá được phiếu kiểm."), frappe.PermissionError)
    frappe.delete_doc(TBM.KT, name, ignore_permissions=True)
    return {"name": name}


@frappe.whitelist()
def in_bieu_mau(ma="BM.06.01", nam=None):
    """BM.06.01 danh mục thiết bị (hôm nay); BM.06.02–06.04 các lần kiểm của một năm."""
    _guard_qc()
    d = getdate(nowdate())
    if ma == "BM.06.01":
        return frappe.render_template("sx/qc/bm0601.html", {"ds": _ds_thiet_bi(d), "ngay": str(d)})
    loai = {v: k for k, v in TBM.BIEU_MAU.items()}.get(ma)
    if not loai:
        frappe.throw(_("Không có biểu mẫu {0}.").format(ma))
    nam = cint(nam) or d.year
    tb = frappe.get_all(TBM.TB, filters={"loai": loai}, pluck="name")
    ds = frappe.get_all(TBM.KT, filters={"thiet_bi": ("in", tb or [""]),
                                         "ngay": ("between", [f"{nam}-01-01", f"{nam}-12-31"])},
                        fields=TRUONG_KT, order_by="ngay asc, creation asc")
    return frappe.render_template("sx/qc/bm060x.html", {"ma": ma, "ten": TEN_BM[ma], "loai": loai, "nam": nam,
                                                        "ds": ds})
