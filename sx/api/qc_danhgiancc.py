"""API phiếu đánh giá nhà cung cấp BM.07.01 (W44, D173) — màn #/so/BM.07.01 (một thẻ trong màn Sổ).

Ai làm gì: Mua hàng (Purchase User / Purchase Manager) lập, chấm, gửi; QC (SX QC) cùng chấm và ký phiếu vật tư loại 1;
Giám đốc (SX Quan Ly) duyệt hoặc trả lại; Trưởng Ban ISO xem mọi phiếu, lập thay được. Người chấm không tự ký QC,
không tự duyệt. Ký điện tử (C23): người + giờ, phiếu khóa sau duyệt; bản in ghi "Ký trên phần mềm: Họ tên, giờ".
Luật chấm điểm, kết luận ở sx/qc/danh_gia_ncc.py; controller SX Danh Gia NCC chặn cả Desk.
"""

import json

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, nowdate

from sx.api.qc_tailieu import _ky_in
from sx.config.roles import SUPER_ROLES
from sx.qc import danh_gia_ncc as DG
from sx.qc import ncc as NCC

TRUONG = ["name", "supplier", "ten_ncc", "ngay", "hinh_thuc", "phan_loai", "nguon", "trang_thai", "tong", "ket_luan",
          "ket_qua", "han_danh_gia_lai", "nguoi_danh_gia", "owner", "creation"]
DAU = ("mat_hang", "dia_chi", "nguoi_lien_he", "mst", "ngay", "hinh_thuc", "phan_loai", "nguon", "ghi_chu")
DANG_MO = (DG.NHAP, DG.CHO_QC, DG.CHO_DUYET, DG.TRA_LAI)


# ── Quyền ────────────────────────────────────────────────────────────────────────────────────

def _roles():
    return set(frappe.get_roles())


def _guard_dg():
    """Vào BM.07.01: Mua hàng, QC, Giám đốc, Trưởng Ban ISO, siêu quyền — trả roles của người gọi."""
    roles = _roles()
    if roles & (DG.VAI_XEM | SUPER_ROLES):
        return roles
    frappe.throw(_("Bạn không có quyền vào phiếu đánh giá nhà cung cấp (BM.07.01)."), frappe.PermissionError)


def _quyen(roles, doc=None):
    """Việc người gọi làm được (trên phiếu `doc` nếu có)."""
    admin = bool(roles & {"System Manager", "Administrator"})
    lap = bool(roles & DG.MUA) or DG.ISO in roles or bool(roles & SUPER_ROLES)
    q = {"lap": lap, "qc": bool(roles & DG.QC_KY) or admin, "duyet": bool(roles & DG.GIAM_DOC) or admin}
    if doc is not None:
        tt = doc.get("trang_thai")
        q["sua"] = lap and tt in DG.SUA_DUOC
        q["gui"] = q["sua"]
        q["qc_ky"] = q["qc"] and tt == DG.CHO_QC
        q["duyet"] = q["duyet"] and tt == DG.CHO_DUYET
        q["tra_lai"] = q["qc_ky"] or q["duyet"]
        q["xoa"] = q["sua"] and (doc.get("owner") == frappe.session.user or DG.ISO in roles or admin)
    return q


def _lay(name):
    if not name or not frappe.db.exists(DG.PT, name):
        frappe.throw(_("Không có phiếu đánh giá {0}.").format(name))
    return frappe.get_doc(DG.PT, name)


def _luu(doc):
    """Lưu qua API — cờ cho controller biết trạng thái / chữ ký đổi đúng luồng."""
    frappe.flags.sx_dgncc = True
    try:
        if doc.is_new():
            doc.insert(ignore_permissions=True)
        else:
            doc.save(ignore_permissions=True)
    finally:
        frappe.flags.sx_dgncc = False
    return doc


def _p(payload):
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    if not isinstance(p, dict):
        frappe.throw(_("Dữ liệu gửi lên không đúng định dạng."))
    return p


# ── Đọc ──────────────────────────────────────────────────────────────────────────────────────

def _ten(u):
    return (frappe.db.get_value("User", u, "full_name") or u) if u else ""


def _ra(doc, roles):
    """Một phiếu cho màn hình: đầu phiếu, phần A (kèm chữ hồ sơ như giấy), phần B (mức điểm), kết quả tính, ký, quyền."""
    d = doc.as_dict()
    t = DG.tinh(d)
    a = []
    for r in doc.get("ho_so") or []:
        tt = int(r.get("tt") or 0)
        ten, ap_chu, kad, _l = DG.MUC_A.get(tt, ("", "", False, ()))
        a.append({"tt": tt, "ten": ten, "ap_dung": ap_chu, "co_kad": kad,
                  "ap": DG.ap_dung(tt, doc.phan_loai, doc.nguon, doc.loai_ncc), "ket_qua": r.get("ket_qua") or "",
                  "so_ngay": r.get("so_ngay") or "", "hieu_luc": str(r.get("hieu_luc") or "")})
    return {
        **{f: (str(d.get(f)) if d.get(f) is not None else "") for f in (
            "name", "supplier", "ten_ncc", "loai_ncc", "ngay", "hinh_thuc", "phan_loai", "nguon", "trang_thai",
            "mat_hang", "dia_chi", "nguoi_lien_he", "mst", "ghi_chu", "goi_y_i", "diem_i", "diem_ii", "diem_iii",
            "diem_iv", "quyet_dinh", "ket_qua", "han_danh_gia_lai", "y_kien_qc", "y_kien_gd")},
        "ho_so": a,
        "muc_b": [{"k": k, "so": v[0], "ten": v[1], "muc": [{"nhan": m, "diem": dm} for m, dm in v[2]],
                   "tu_tinh": k not in DG.CHAM_TAY} for k, v in DG.MUC_B.items()],
        "diem_v": t["diem_v"], "tong": t["tong"], "toi_da": DG.TOI_DA, "thieu_a": t["thieu"], "du_diem": t["du"],
        "ket_luan": t["ket_luan"] or "",
        "ky": {"danh_gia": _ky_in(_ten(doc.nguoi_danh_gia), doc.danh_gia_luc) if doc.nguoi_danh_gia else "",
               "qc": _ky_in(_ten(doc.qc_ky), doc.qc_luc) if doc.qc_ky else "",
               "duyet": _ky_in(_ten(doc.duyet_boi), doc.duyet_luc) if doc.duyet_boi else ""},
        "can_qc": doc.phan_loai == DG.LOAI_1,
        "lua_chon": {"hinh_thuc": list(DG.HINH_THUC), "phan_loai": list(DG.PHAN_LOAI), "nguon": list(DG.NGUON)},
        "quyen": _quyen(roles, doc),
        "hom_nay": str(getdate(nowdate())),
    }


@frappe.whitelist()
def ds(q=None):
    """Màn danh sách: việc của tôi (chờ QC ký / chờ duyệt / phiếu trả lại, nháp của tôi), nhà cung cấp (đã duyệt
    BM.07.02 hay chưa, phiếu đã duyệt gần nhất, hạn đánh giá lại, phiếu đang mở), các phiếu gần đây."""
    roles = _guard_dg()
    nay = getdate(nowdate())
    q_ = _quyen(roles)
    user = frappe.session.user
    phieu = frappe.get_all(DG.PT, fields=TRUONG, order_by="creation desc", limit=300)
    for p in phieu:
        for f in ("ngay", "han_danh_gia_lai", "creation"):
            p[f] = str(p.get(f) or "")
    theo = DG.phieu_duyet()
    mo = {}
    for p in phieu:
        if p.trang_thai in DANG_MO:
            mo.setdefault(p.supplier, p.name)
    k = (q or "").strip().lower()
    ncc = []
    for s in DG.ds_ncc():
        if k and k not in f"{s['name']} {s['ten']}".lower():
            continue
        t = DG.trang_thai_ncc(theo.get(s["name"]) or [], nay)
        ncc.append(dict(s, danh_gia=t, dang_mo=mo.get(s["name"]) or ""))
    viec = [p for p in phieu if (p.trang_thai == DG.CHO_QC and q_["qc"]) or (p.trang_thai == DG.CHO_DUYET
                                                                            and q_["duyet"])
            or (p.trang_thai in DG.SUA_DUOC and p.owner == user and q_["lap"])]
    return {"ncc": ncc, "viec": viec, "phieu": phieu[:50], "quyen": q_, "hom_nay": str(nay),
            "hinh_thuc": list(DG.HINH_THUC), "bao_truoc": DG.BAO_TRUOC}


@frappe.whitelist()
def xem(name):
    roles = _guard_dg()
    return _ra(_lay(name), roles)


# ── Lập, chấm ────────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def lap(supplier, hinh_thuc=None):
    """Lập phiếu cho một NCC: phần A tự điền từ hồ sơ NCC; đánh giá lại thì gợi ý điểm I từ lô 12 tháng. NCC đang có
    phiếu chưa duyệt → mở phiếu đó (không lập phiếu thứ hai)."""
    roles = _guard_dg()
    if not _quyen(roles)["lap"]:
        frappe.throw(_("Mua hàng lập phiếu đánh giá nhà cung cấp."), frappe.PermissionError)
    s = frappe.db.get_value("Supplier", supplier, ["name", "supplier_name", "custom_loai_ncc", "custom_nguon_goc",
                                                   "tax_id", "mobile_no", "primary_address"], as_dict=True)
    if not s:
        frappe.throw(_("Không có nhà cung cấp {0}.").format(supplier))
    if s.custom_loai_ncc == NCC.DV:
        frappe.throw(_("Nhà cung cấp dịch vụ không đánh giá theo BM.07.01."))
    dang = frappe.get_all(DG.PT, filters={"supplier": s.name, "trang_thai": ("in", list(DANG_MO))}, pluck="name",
                          limit=1)
    if dang:
        return _ra(_lay(dang[0]), roles)
    nay = getdate(nowdate())
    da = DG.phieu_duyet(s.name).get(s.name) or []
    ht = hinh_thuc or (DG.LAI_NAM if da else DG.LAN_DAU)
    if ht not in DG.HINH_THUC:
        frappe.throw(_("Hình thức: {0}.").format(" / ".join(DG.HINH_THUC)))
    pl = DG.phan_loai_mac_dinh(s.custom_loai_ncc)
    nguon = s.custom_nguon_goc if s.custom_nguon_goc in DG.NGUON else NCC.TRONG_NUOC
    ho_so = frappe.get_all("SX Ho So NCC", filters={"parenttype": "Supplier", "parent": s.name},
                           fields=["loai_ho_so", "so_hieu", "ngay_cap", "het_han"])
    diem_i, goi_y = None, "Đánh giá lần đầu: chấm điểm chất lượng theo mẫu / lô thử."
    if ht != DG.LAN_DAU:
        so_lo, khong, goi_y = DG.lo_12_thang(s.name, nay)
        g = DG.goi_y_diem_i(so_lo, khong)
        if g is not None:
            diem_i, goi_y = str(g), f"{goi_y} → gợi ý {g} điểm."
    doc = frappe.get_doc({"doctype": DG.PT, "supplier": s.name, "ngay": nay, "hinh_thuc": ht, "phan_loai": pl,
                          "nguon": nguon, "mst": s.tax_id or None, "nguoi_lien_he": s.mobile_no or None,
                          "dia_chi": (s.primary_address or "").replace("<br>", ", ").strip(", ")[:140] or None,
                          "ho_so": DG.tu_dien(ho_so, pl, nguon, s.custom_loai_ncc, nay), "diem_i": diem_i,
                          "goi_y_i": goi_y, "trang_thai": DG.NHAP})
    _luu(doc)
    return _ra(doc, roles)


@frappe.whitelist()
def luu(name, payload):
    """Lưu đầu phiếu, phần A, điểm I–IV. Mua hàng: phiếu Nháp / Trả lại; QC: phiếu Chờ QC (cùng chấm phần A, B)."""
    roles = _guard_dg()
    doc = _lay(name)
    q = _quyen(roles, doc)
    if not (q["sua"] or q["qc_ky"]):
        frappe.throw(_("Phiếu đang {0} — bạn không sửa được.").format(doc.trang_thai.lower()), frappe.PermissionError)
    p = _p(payload)
    for f in DAU if q["sua"] else ():
        if f in p:
            v = p[f]
            doc.set(f, (v.strip() if isinstance(v, str) else v) or None)
    if doc.ngay and getdate(doc.ngay) > getdate(nowdate()):
        frappe.throw(_("Ngày đánh giá không được sau hôm nay."))
    for k in DG.CHAM_TAY:
        if k in p:
            doc.set(k, str(p[k]) if p[k] not in (None, "") else None)
    if "ho_so" in p:
        theo = {int(r.get("tt") or 0): r for r in p["ho_so"] or []}
        for r in doc.ho_so:
            x = theo.get(int(r.tt or 0))
            if x is None:
                continue
            r.ket_qua = x.get("ket_qua") or None
            r.so_ngay = (str(x.get("so_ngay") or "").strip()[:140]) or None
            r.hieu_luc = x.get("hieu_luc") or None
    _luu(doc)
    return _ra(doc, roles)


@frappe.whitelist()
def gui(name):
    """Mua hàng gửi: đủ điểm I–IV, phần A không còn mục áp dụng bỏ trống → vật tư loại 1 chờ QC ký, loại 2 chờ Giám
    đốc duyệt."""
    roles = _guard_dg()
    doc = _lay(name)
    if not _quyen(roles, doc)["gui"]:
        frappe.throw(_("Phiếu đang {0} — không gửi được.").format(doc.trang_thai.lower()), frappe.PermissionError)
    t = DG.tinh(doc.as_dict())
    if not t["du"]:
        frappe.throw(_("Chưa chấm đủ điểm I–IV (phần B)."))
    trong = [int(r.tt) for r in doc.ho_so if not r.ket_qua]
    if trong:
        frappe.throw(_("Phần A còn mục chưa chấm: {0}.").format(", ".join(map(str, trong))))
    doc.trang_thai = DG.CHO_QC if doc.phan_loai == DG.LOAI_1 else DG.CHO_DUYET
    doc.nguoi_danh_gia, doc.danh_gia_luc = frappe.session.user, now_datetime()
    doc.qc_ky = doc.qc_luc = doc.y_kien_qc = None
    doc.duyet_boi = doc.duyet_luc = doc.quyet_dinh = None
    _luu(doc)
    return _ra(doc, roles)


# ── Ký, duyệt ────────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def qc_ky(name, y_kien=None):
    """QC cùng chấm vật tư loại 1 — ký (người + giờ) → chờ Giám đốc duyệt."""
    roles = _guard_dg()
    doc = _lay(name)
    if not _quyen(roles, doc)["qc_ky"]:
        frappe.throw(_("QC ký phiếu vật tư loại 1 khi phiếu chờ QC."), frappe.PermissionError)
    if frappe.session.user == doc.nguoi_danh_gia:
        frappe.throw(_("Người chấm không tự ký thay QC."), frappe.PermissionError)
    doc.qc_ky, doc.qc_luc = frappe.session.user, now_datetime()
    doc.y_kien_qc = (y_kien or "").strip() or None
    doc.trang_thai = DG.CHO_DUYET
    _luu(doc)
    return _ra(doc, roles)


@frappe.whitelist()
def duyet(name, quyet_dinh=None, y_kien=None):
    """Giám đốc duyệt. Phiếu Xem xét (20–29 điểm): chọn Chấp nhận / Không chấp nhận. Kết quả Chấp nhận → hạn đánh
    giá lại = hôm nay + 12 tháng. Phiếu khóa sau duyệt."""
    roles = _guard_dg()
    doc = _lay(name)
    if not _quyen(roles, doc)["duyet"]:
        frappe.throw(_("Giám đốc duyệt phiếu đang chờ duyệt."), frappe.PermissionError)
    if frappe.session.user in (doc.nguoi_danh_gia, doc.qc_ky):
        frappe.throw(_("Người chấm / ký phiếu không tự duyệt."), frappe.PermissionError)
    kl = DG.tinh(doc.as_dict())["ket_luan"]
    if kl is None:
        frappe.throw(_("Phiếu chưa đủ điểm — trả lại để Mua hàng chấm."))
    if kl == DG.XEM_XET and quyet_dinh not in (DG.CHAP_NHAN, DG.KHONG_CHAP_NHAN):
        frappe.throw(_("Phiếu Xem xét (20–29 điểm): Giám đốc chọn Chấp nhận hoặc Không chấp nhận."))
    nay = getdate(nowdate())
    doc.quyet_dinh = quyet_dinh if kl == DG.XEM_XET else None
    doc.ket_qua = DG.ket_qua_duyet(kl, quyet_dinh)
    doc.duyet_boi, doc.duyet_luc = frappe.session.user, now_datetime()
    doc.y_kien_gd = (y_kien or "").strip() or None
    doc.han_danh_gia_lai = DG.han_lai(nay) if doc.ket_qua == DG.CHAP_NHAN else None
    doc.trang_thai = DG.DA_DUYET
    _luu(doc)
    return _ra(doc, roles)


@frappe.whitelist()
def tra_lai(name, y_kien):
    """QC (phiếu chờ QC) hoặc Giám đốc (phiếu chờ duyệt) trả lại Mua hàng kèm ý kiến — bổ sung hồ sơ, giao lô thử…"""
    roles = _guard_dg()
    doc = _lay(name)
    q = _quyen(roles, doc)
    if not q["tra_lai"]:
        frappe.throw(_("Không trả lại được phiếu đang {0}.").format(doc.trang_thai.lower()), frappe.PermissionError)
    y = (y_kien or "").strip()
    if not y:
        frappe.throw(_("Ghi ý kiến trả lại (bổ sung gì, sửa gì)."))
    if q["qc_ky"]:
        doc.y_kien_qc = y
    else:
        doc.y_kien_gd = y
    doc.qc_ky = doc.qc_luc = None
    doc.trang_thai = DG.TRA_LAI
    _luu(doc)
    return _ra(doc, roles)


@frappe.whitelist()
def xoa(name):
    """Xoá phiếu nháp / trả lại (người lập, Trưởng Ban ISO) — phiếu đã gửi, đã duyệt là hồ sơ, không xoá."""
    roles = _guard_dg()
    doc = _lay(name)
    if not _quyen(roles, doc)["xoa"]:
        frappe.throw(_("Chỉ xoá được phiếu nháp / trả lại của mình."), frappe.PermissionError)
    frappe.delete_doc(DG.PT, doc.name, ignore_permissions=True)
    return {"ok": 1}


# ── In ───────────────────────────────────────────────────────────────────────────────────────

def html(doc):
    """Bản in BM.07.01 theo giấy (không kiểm quyền — gọi sau khi đã kiểm)."""
    d = _ra(doc, set())
    return frappe.render_template("sx/qc/bm0701.html", {"d": d, "MUC_B": DG.MUC_B, "CO": DG.CO, "KHONG": DG.KHONG,
                                                         "KAD": DG.KAD})


@frappe.whitelist()
def in_phieu(name):
    _guard_dg()
    return html(_lay(name))


def in_ho_so(tu, den):
    """Gói hồ sơ cho đoàn (W27): mỗi phiếu ĐÃ DUYỆT trong kỳ một tệp."""
    ds = frappe.get_all(DG.PT, filters={"trang_thai": DG.DA_DUYET, "duyet_luc": ("between", [str(tu), f"{den} 23:59:59"])},
                        pluck="name", order_by="duyet_luc asc")
    return [(f"{n}.html", html(frappe.get_doc(DG.PT, n))) for n in ds]
