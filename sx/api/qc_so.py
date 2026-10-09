"""API màn Sổ (#/so, #/so/<mã>) — W43, D172. Luật ở sx/qc/so.py; controller SX So Dong chặn cả Desk.

Mọi vai có tài khoản app vào được; mỗi người chỉ thấy sổ mình có quyền — vai ghi / xác nhận / chỉ xem / xem xét
cuối tháng của định nghĩa sổ, cộng siêu quyền; Trưởng Ban ISO xem mọi sổ. Ký điện tử (C23): ghi, xác nhận, xem xét
tháng lưu người + giờ, khóa sau ký; bản in ghi "Ký trên phần mềm: Họ tên, dd/mm/yyyy hh:mm".
Tệp đính kèm là tệp riêng tư — tải qua `tep` (GET, kiểm quyền xem sổ).
"""

import json
import unicodedata
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime, nowdate

from sx.api.qc_tailieu import _doc_tep, _ky_in, _luu_tep, _tep_b64
from sx.config.roles import ROLE_VIEWS, SUPER_ROLES
from sx.qc import so as SO
from sx.qc import thiet_bi as TBM

ISO = "ISO Manager"
TRUONG_DONG = ["name", "so", "ngay", "trang_thai", "tom_tat", "han_gan_nhat", "du_lieu", "nguoi_ghi", "ghi_luc",
               "xac_nhan_boi", "xac_nhan_luc", "y_kien_xac_nhan", "ly_do_ngung", "su_co", "tep", "ban_ky_tay",
               "creation"]
DUOI_TEP = ("pdf", "png", "jpg", "jpeg")
TEN_VIEC = {"xem": "xem", "ghi": "ghi", "xac_nhan": "xác nhận", "xem_thang": "xem xét cuối tháng"}
TRUONG_MAN = ("ma", "ten", "kieu", "quy_trinh", "mang", "nhan_xac_nhan", "xem_cuoi_thang", "nhan_xem_thang",
              "tinh_toan", "nhom_theo", "dau_trang_ghi_chu", "ghi_chu", "cot")


# ── Quyền ────────────────────────────────────────────────────────────────────────────────────

def _roles():
    return set(frappe.get_roles())


def _sieu(roles):
    return bool(roles & SUPER_ROLES)


def _la_iso(roles):
    return _sieu(roles) or ISO in roles


def _guard_so():
    """Vào màn Sổ: mọi vai có tài khoản app (ROLE_VIEWS) hoặc siêu quyền — trả roles của người gọi."""
    roles = _roles()
    if _sieu(roles) or roles & set(ROLE_VIEWS):
        return roles
    frappe.throw(_("Bạn không có quyền vào màn Sổ."), frappe.PermissionError)


def _so(ma, roles, viec="xem"):
    """(định nghĩa, quyền) của sổ `ma` — chặn khi không có quyền `viec`."""
    dn = SO.dinh_nghia(ma)
    if not dn:
        frappe.throw(_("Không có sổ {0}.").format(ma))
    q = SO.quyen(dn, roles, _sieu(roles))
    if not q.get(viec):
        frappe.throw(_("Bạn không có quyền {0} sổ {1}.").format(TEN_VIEC.get(viec, viec), dn["ma"]),
                     frappe.PermissionError)
    return dn, q


def _dong_doc(name):
    if not name or not frappe.db.exists(SO.PT_DONG, name):
        frappe.throw(_("Không có dòng sổ {0}.").format(name))
    return frappe.get_doc(SO.PT_DONG, name)


def _p(payload):
    return json.loads(payload) if isinstance(payload, str) else dict(payload or {})


def _luu(doc):
    """Lưu qua API: bật cờ cho controller (trạng thái, người ký chỉ đổi ở đây)."""
    frappe.flags.sx_so = True
    try:
        if doc.is_new():
            doc.insert(ignore_permissions=True)
        else:
            doc.save(ignore_permissions=True)
    finally:
        frappe.flags.sx_so = False
    return doc


def _ten(u, nho):
    if not u:
        return ""
    if u not in nho:
        nho[u] = frappe.db.get_value("User", u, "full_name") or u
    return nho[u]


def _nguoi_cuoi(doc):
    """Người sửa dữ liệu gần nhất (Danh mục) — người đó không tự xác nhận."""
    sua = [r for r in doc.get("sua_doi") or [] if r.get("hanh_dong") == "Sửa"]
    return sua[-1].get("nguoi") if sua else None


def _khong_dau(s):
    s = unicodedata.normalize("NFKD", str(s or "").replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


# ── Dữ liệu cho màn hình ─────────────────────────────────────────────────────────────────────

def _dn_man(dn):
    d = {f: dn.get(f) for f in TRUONG_MAN}
    d["cot"] = [dict(c, lua_chon=SO.lua_chon(c)) for c in dn["cot"]]
    d["cot_tinh"] = list(SO.TINH_COT.get(dn.get("tinh_toan"), ()))      # app tính — phiếu không cho nhập
    return d


def _nhan_link(dn, ds):
    """{giá trị: nhãn} cho mọi ô Link / User của các dòng (tra mỗi giá trị một lần)."""
    nl = {}
    for c in dn["cot"]:
        if c.get("kieu") not in ("Link", "User"):
            continue
        dt = c.get("link_doctype") if c.get("kieu") == "Link" else "User"
        for du in ds:
            v = du.get(c["key"])
            if v and str(v) not in nl:
                x = SO.tra(dt, str(v))
                nl[str(v)] = (x or {}).get("nhan") or ""
    return nl


def _sua_cua(ten):
    """{dòng: [lần sửa]} của các dòng."""
    ra = {}
    for r in frappe.get_all(SO.PT_SUA, filters={"parenttype": SO.PT_DONG, "parent": ("in", ten or [""])},
                            fields=["parent", "luc", "nguoi", "hanh_dong", "truoc", "sau", "idx"], order_by="idx asc"):
        ra.setdefault(r.parent, []).append(r)
    return ra


def _cac_dong(dn, q, roles, ds, nay):
    """Các dòng cho màn hình / bản in: dữ liệu, chữ hiển thị từng ô, hạn, người ký, việc người xem được làm."""
    user = frappe.session.user
    du = {x.name: SO.doc_json(x.du_lieu) for x in ds}
    nl = _nhan_link(dn, du.values())
    sua = _sua_cua([x.name for x in ds])
    nho = {}
    la_iso = _la_iso(roles)
    ra = []
    for x in ds:
        d = {f: x.get(f) for f in TRUONG_DONG if f != "du_lieu"}
        s = sua.get(x.name, [])
        cuoi = next((r.nguoi for r in reversed(s) if r.hanh_dong == "Sửa"), None)
        dong = dict(x, nguoi_cuoi=cuoi)
        d.update(ngay=str(x.ngay)[:10], ghi_luc=str(x.ghi_luc or "")[:16], xac_nhan_luc=str(x.xac_nhan_luc or "")[:16],
                 han_gan_nhat=str(x.han_gan_nhat or "")[:10], creation=str(x.creation or "")[:16],
                 du_lieu=du[x.name], hien={c["key"]: SO.hien(c, du[x.name].get(c["key"]), nl) for c in dn["cot"]},
                 han=SO.cac_han(dn["cot"], du[x.name], nay), ten_ghi=_ten(x.nguoi_ghi, nho),
                 ten_xac_nhan=_ten(x.xac_nhan_boi, nho),
                 ky_ghi=_ky_in(_ten(x.nguoi_ghi, nho), x.ghi_luc),
                 ky_xac_nhan=_ky_in(_ten(x.xac_nhan_boi, nho), x.xac_nhan_luc),
                 sua_doi=[{"luc": str(r.luc or "")[:16], "ten": _ten(r.nguoi, nho), "hanh_dong": r.hanh_dong,
                           "truoc": SO.doc_json(r.truoc), "sau": SO.doc_json(r.sau)} for r in s],
                 duoc_sua=not SO.loi_sua(dn, dong, user, q, nay),
                 duoc_xac_nhan=not SO.loi_xac_nhan(dong, user, q),
                 duoc_ngung=not SO.loi_ngung(dn, dong, user, q, la_iso, nay, "-"))
        ra.append(d)
    return ra, nl


def _khoang(tu, den, nay):
    """Khoảng ngày xem / in của sổ Ghi theo dòng: mặc định tháng này."""
    tu = getdate(tu) if tu else nay.replace(day=1)
    den = getdate(den) if den else SO.tinh_thang(tu.strftime("%Y-%m"))[1]
    if den < tu:
        frappe.throw(_("Khoảng ngày không hợp lệ."))
    return tu, den


def _xem_thang(ma, thang, ds_thang):
    """Lần xem xét gần nhất của tháng + có dòng ghi sau đó (cần xem lại) không."""
    x = frappe.get_all(SO.PT_XEM, filters={"so": ma, "thang": thang}, fields=["xem_boi", "xem_luc", "nhan_xet"],
                       order_by="xem_luc desc", limit=1)
    if not x:
        return None
    x = x[0]
    luc = str(x.xem_luc or "")[:19]
    ten = frappe.db.get_value("User", x.xem_boi, "full_name") or x.xem_boi
    return {"boi": x.xem_boi, "ten": ten, "luc": luc[:16], "nhan_xet": x.nhan_xet or "", "ky": _ky_in(ten, x.xem_luc),
            "can_xem_lai": any(str(d.get("ghi_luc") or "")[:19] > luc for d in ds_thang)}


def _lay(dn, tu=None, den=None, ngung=0):
    """Dòng của sổ: Ghi theo dòng theo khoảng ngày (mọi trạng thái); Danh mục toàn bộ (Ngừng khi `ngung`)."""
    loc = {"so": dn["name"]}
    if dn["kieu"] == SO.GHI_THEO_DONG:
        loc["ngay"] = ("between", [str(tu), str(den)])
    elif not cint(ngung):
        loc["trang_thai"] = ("!=", SO.NGUNG)
    return frappe.get_all(SO.PT_DONG, filters=loc, fields=TRUONG_DONG, order_by="ngay asc, creation asc")


# ── Danh sách sổ, xem một sổ ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def ds_so():
    """Các sổ người xem có quyền: số dòng tháng này (Danh mục: đang dùng), chờ xác nhận, hạn cần nhắc, tháng chưa
    xem xét; BM.06.05 thêm thiết bị chờ kiểm lại, máy quá hạn bảo dưỡng."""
    roles = _guard_so()
    nay = getdate(nowdate())
    dau, cuoi = SO.tinh_thang(nay.strftime("%Y-%m"))
    nh = {x["ma"]: x for x in (SO.nhac(nay).get("ds") or [])}
    ra = []
    for dn in SO.ds_dinh_nghia():
        q = SO.quyen(dn, roles, _sieu(roles))
        if not q["xem"]:
            continue
        if dn["kieu"] == SO.GHI_THEO_DONG:
            n = frappe.db.count(SO.PT_DONG, {"so": dn["name"], "ngay": ("between", [str(dau), str(cuoi)]),
                                             "trang_thai": ("!=", SO.NGUNG)})
        else:
            n = frappe.db.count(SO.PT_DONG, {"so": dn["name"], "trang_thai": ("!=", SO.NGUNG)})
        x = nh.get(dn["name"]) or {}
        ra.append({"ma": dn["name"], "ten": dn.get("ten") or "", "kieu": dn["kieu"], "quy_trinh": dn.get("quy_trinh"),
                   "mang": dn.get("mang"), "nhan_xac_nhan": dn.get("nhan_xac_nhan") or "", "quyen": q, "so_dong": n,
                   "cho": frappe.db.count(SO.PT_DONG, {"so": dn["name"], "trang_thai": SO.DA_GHI})
                   if q["co_xac_nhan"] else 0,
                   "han": len(x.get("han") or []), "chua_xem": x.get("chua_xem") or [],
                   "kiem_lai": len(x.get("kiem_lai") or []), "bao_duong": len(x.get("bao_duong") or [])})
    if SO.vao_bm0701(roles, _sieu(roles)):
        ra.append(_the_bm0701(roles, nay))
        ra.sort(key=lambda s: s["ma"])
    return {"ds": ra, "la_iso": _la_iso(roles), "hom_nay": str(nay), "user": frappe.session.user}


def _the_bm0701(roles, nay):
    """Thẻ BM.07.01 (W44, D173) trong danh sách sổ — mở màn riêng #/so/BM.07.01 (views/danhgiancc.js)."""
    from sx.api.qc_danhgiancc import _quyen
    from sx.qc import danh_gia_ncc as DG
    nh = DG.nhac(nay) or {}
    q = _quyen(roles)
    cho = len(nh.get("cho_qc") or []) * q["qc"] + len(nh.get("cho_duyet") or []) * q["duyet"]
    con = sum(1 for v in DG.phieu_duyet().values() if DG.co_chap_nhan(v, nay))
    return {"ma": DG.MA, "ten": "Phiếu đánh giá nhà cung cấp", "kieu": "Phiếu", "quy_trinh": "QT.07", "mang": "ncc",
            "nhan_xac_nhan": "QC ký / Giám đốc duyệt", "quyen": q, "so_dong": con, "cho": cho,
            "han": sum(len(nh.get(k) or []) for k in ("qua_han", "sap_han", "chua_co")), "chua_xem": [],
            "kiem_lai": 0, "bao_duong": 0}


@frappe.whitelist()
def xem(so, tu=None, den=None, q=None, ngung=0):
    """Một sổ: định nghĩa (cột, nhãn), quyền, các dòng (Ghi theo dòng: khoảng ngày, mặc định tháng này; Danh mục:
    đang dùng, `ngung` = 1 thì cả dòng đã ngừng), tìm `q` (không dấu), lần xem xét tháng, nhắc riêng BM.06.05."""
    roles = _guard_so()
    dn, quyen = _so(so, roles, "xem")
    nay = getdate(nowdate())
    tu, den = _khoang(tu, den, nay) if dn["kieu"] == SO.GHI_THEO_DONG else (None, None)
    ds = _lay(dn, tu, den, ngung)
    dong, _nl = _cac_dong(dn, quyen, roles, ds, nay)
    if q:
        k = _khong_dau(q).strip()
        dong = [d for d in dong if k in _khong_dau(" ".join([d.get("tom_tat") or ""] + list(d["hien"].values())))]
    xem_thang = None
    if dn["kieu"] == SO.GHI_THEO_DONG and cint(dn.get("xem_cuoi_thang")):
        xem_thang = _xem_thang(dn["name"], tu.strftime("%Y-%m"), [d for d in dong if str(d["ngay"])[:7]
                                                                   == tu.strftime("%Y-%m")])
    rieng = {"kiem_lai": [], "bao_duong": []}
    if dn.get("tinh_toan") == SO.BAO_DUONG:
        x = next((s for s in (SO.nhac(nay).get("ds") or []) if s["ma"] == dn["name"]), {})
        rieng = {"kiem_lai": x.get("kiem_lai") or [], "bao_duong": x.get("bao_duong") or []}
    return {"dn": _dn_man(dn), "quyen": quyen, "ds": dong, "tu": str(tu or ""), "den": str(den or ""),
            "xem_thang": xem_thang, "la_iso": _la_iso(roles), "hom_nay": str(nay), "user": frappe.session.user,
            "ten_user": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user, **rieng}


@frappe.whitelist()
def goi_y(so, key):
    """Lựa chọn cho ô Link / User khi ghi: [{v, nhan, loai, an_ma}] — Link lọc theo `lua_chon` (ô loai), bỏ bản ghi
    đã bỏ (thiết bị thanh lý, nhân viên đã nghỉ); `an_ma` (nhân viên): xếp, hiện theo họ tên. User: tài khoản đang
    dùng có vai của app."""
    roles = _guard_so()
    dn, _q = _so(so, roles, "ghi")
    c = next((c for c in dn["cot"] if c.get("key") == key), None)
    if not c or c.get("kieu") not in ("Link", "User"):
        frappe.throw(_("Cột {0} không chọn từ danh sách.").format(key))
    if c["kieu"] == "User":
        u = sorted(set(frappe.get_all("Has Role", filters={"parenttype": "User", "role": ("in", sorted(ROLE_VIEWS))},
                                      pluck="parent")))
        ds = frappe.get_all("User", filters={"name": ("in", u or [""]), "enabled": 1}, fields=["name", "full_name"],
                            order_by="full_name asc")
        return [{"v": x.name, "nhan": x.full_name or x.name, "loai": None} for x in ds]
    cfg = SO.LINK_DUOC[c["link_doctype"]]
    o = ["name", cfg["nhan"]] + ([cfg["loai"]] if cfg.get("loai") else [])
    lc = SO.lua_chon(c)
    ra = []
    an = 1 if cfg.get("an_ma") else 0
    for x in frappe.get_all(c["link_doctype"], fields=o + list(cfg.get("bo") or {}),
                            order_by=f"{cfg['nhan']} asc, name asc" if an else "name asc"):
        if any(str(x.get(k)) == str(v) for k, v in (cfg.get("bo") or {}).items()):
            continue
        loai = x.get(cfg["loai"]) if cfg.get("loai") else None
        if lc and loai not in lc:
            continue
        ra.append({"v": x.name, "nhan": x.get(cfg["nhan"]) or "", "loai": loai, "an_ma": an})
    return ra


# ── Ghi, sửa, xác nhận, ngừng ────────────────────────────────────────────────────────────────

@frappe.whitelist()
def ghi(so, payload):
    """Ghi một dòng: {ngay, du_lieu: {khóa cột: giá trị}, su_co}. Kiểm dữ liệu ở controller (kiểu, bắt buộc, lựa
    chọn, không khóa lạ); sổ Ghi theo dòng không ghi ngày sau hôm nay."""
    roles = _guard_so()
    dn, _q = _so(so, roles, "ghi")
    p = _p(payload)
    doc = frappe.get_doc({"doctype": SO.PT_DONG, "so": dn["name"], "ngay": getdate(p.get("ngay") or nowdate()),
                          "du_lieu": SO.ghi_json(p.get("du_lieu") or {}), "trang_thai": SO.DA_GHI,
                          "nguoi_ghi": frappe.session.user, "ghi_luc": now_datetime(), "su_co": p.get("su_co") or None})
    _luu(doc)
    return {"name": doc.name, "tom_tat": doc.tom_tat, "trang_thai": doc.trang_thai, "kiem_lai": _canh_kiem_lai(dn, doc)}


@frappe.whitelist()
def sua(name, payload):
    """Sửa một dòng (dữ liệu, ngày, phiếu sự cố). Ghi theo dòng: người ghi, trong ngày, khi chưa xác nhận. Danh mục:
    người có quyền ghi; dòng đã xác nhận về Đã ghi chờ xác nhận lại. Mỗi lần sửa nối vào sua_doi (trước / sau)."""
    roles = _guard_so()
    doc = _dong_doc(name)
    dn, q = _so(doc.so, roles, "xem")
    nay = getdate(nowdate())
    loi = SO.loi_sua(dn, doc.as_dict(), frappe.session.user, q, nay)
    if loi:
        frappe.throw(_(loi), frappe.PermissionError if not q["ghi"] else frappe.ValidationError)
    p = _p(payload)
    cu = SO.doc_json(doc.du_lieu)
    sach, loi = SO.kiem_du_lieu(dn["cot"], SO.bo_sung(dn, p["du_lieu"] if "du_lieu" in p else cu, SO.tra), SO.tra)
    if loi:
        frappe.throw(_("{0}: {1}").format(dn["ma"], " ".join(loi)))
    ngay = getdate(p["ngay"]) if p.get("ngay") else getdate(doc.ngay)
    truoc = {"ngay": str(getdate(doc.ngay)), "du_lieu": cu}
    sau = {"ngay": str(ngay), "du_lieu": sach}
    su_co = (p.get("su_co") or None) if "su_co" in p else (doc.su_co or None)
    if truoc == sau and su_co == (doc.su_co or None):
        return {"name": doc.name, "doi": 0, "tom_tat": doc.tom_tat}
    if su_co != (doc.su_co or None):
        truoc["su_co"], sau["su_co"] = doc.su_co or None, su_co
    if dn["kieu"] == SO.DANH_MUC and doc.trang_thai == SO.DA_XAC_NHAN:
        truoc["xac_nhan"] = {"boi": doc.xac_nhan_boi, "luc": str(doc.xac_nhan_luc or "")[:19]}
        doc.trang_thai, doc.xac_nhan_boi, doc.xac_nhan_luc, doc.y_kien_xac_nhan = SO.DA_GHI, None, None, None
    doc.ngay, doc.du_lieu, doc.su_co = ngay, SO.ghi_json(sach), su_co
    doc.append("sua_doi", {"luc": now_datetime(), "nguoi": frappe.session.user, "hanh_dong": "Sửa",
                           "truoc": SO.ghi_json(truoc), "sau": SO.ghi_json(sau)})
    _luu(doc)
    return {"name": doc.name, "doi": 1, "tom_tat": doc.tom_tat, "trang_thai": doc.trang_thai,
            "kiem_lai": _canh_kiem_lai(dn, doc)}


def _canh_kiem_lai(dn, doc):
    """BM.06.05: dòng có thiết bị đo phải kiểm lại mà chưa có lần kiểm từ ngày đó → câu nhắc cho màn hình."""
    if dn.get("tinh_toan") != SO.BAO_DUONG or doc.trang_thai == SO.NGUNG:
        return None
    du = SO.doc_json(doc.du_lieu)
    ma = du.get(SO.BD_KIEM_LAI)
    if not ma:
        return None
    tb = {x.name: x for x in frappe.get_all(TBM.TB, filters={"name": ma}, fields=["name", "ten", "loai", "thanh_ly"])}
    k = TBM.lan_cuoi(ma)
    x = SO.can_kiem_lai([{"name": doc.name, "ngay": doc.ngay, "du_lieu": du}], tb, {ma: k.ngay} if k else {})
    if not x:
        return None
    x = x[0]
    return (f"{x['ma']} {x['ten']} phải kiểm lại theo {x['bieu_mau'] or 'BM.06.0x'} trước khi dùng (QT.06) — ghi phiếu "
            f"ở màn Thiết bị đo; app nhắc tới khi có phiếu kiểm.")


@frappe.whitelist()
def xac_nhan(name, y_kien=None):
    """Xác nhận một dòng (vd QC kiểm máy trước khi chạy lại): người có vai xác nhận, không phải người ghi / sửa gần
    nhất; xác nhận xong dòng Ghi theo dòng khóa."""
    roles = _guard_so()
    doc = _dong_doc(name)
    dn, q = _so(doc.so, roles, "xem")
    loi = SO.loi_xac_nhan(dict(doc.as_dict(), nguoi_cuoi=_nguoi_cuoi(doc)), frappe.session.user, q)
    if loi:
        frappe.throw(_(loi), frappe.PermissionError if not q["xac_nhan"] else frappe.ValidationError)
    doc.trang_thai, doc.xac_nhan_boi, doc.xac_nhan_luc = SO.DA_XAC_NHAN, frappe.session.user, now_datetime()
    doc.y_kien_xac_nhan = (y_kien or "").strip() or None
    _luu(doc)
    return {"name": doc.name, "trang_thai": doc.trang_thai, "xac_nhan_luc": str(doc.xac_nhan_luc)[:16],
            "kiem_lai": _canh_kiem_lai(dn, doc)}


@frappe.whitelist()
def ngung(name, ly_do=None):
    """Ngừng một dòng (không xóa): Danh mục — đối tượng không dùng nữa; Ghi theo dòng — ghi nhầm. Phải có lý do;
    dòng vẫn trên sổ (bản in gạch đi)."""
    roles = _guard_so()
    doc = _dong_doc(name)
    dn, q = _so(doc.so, roles, "xem")
    loi = SO.loi_ngung(dn, doc.as_dict(), frappe.session.user, q, _la_iso(roles), getdate(nowdate()), ly_do)
    if loi:
        frappe.throw(_(loi))
    truoc = {"trang_thai": doc.trang_thai}
    doc.trang_thai, doc.ly_do_ngung = SO.NGUNG, ly_do.strip()
    doc.append("sua_doi", {"luc": now_datetime(), "nguoi": frappe.session.user, "hanh_dong": "Ngừng",
                           "truoc": SO.ghi_json(truoc), "sau": SO.ghi_json({"trang_thai": SO.NGUNG,
                                                                            "ly_do": doc.ly_do_ngung})})
    _luu(doc)
    return {"name": doc.name, "trang_thai": doc.trang_thai}


@frappe.whitelist()
def xem_thang(so, thang, nhan_xet=None):
    """Xem xét cuối tháng (sổ có xem_cuoi_thang): Trưởng Ban ISO, siêu quyền, vai xem xét tháng của sổ. Mỗi lần
    bấm là một bản ghi (người + giờ + nhận xét); dòng ghi bù sau đó → tháng lại chờ xem."""
    roles = _guard_so()
    dn, _q = _so(so, roles, "xem_thang")
    try:
        dau, cuoi = SO.tinh_thang(thang)
    except ValueError:
        frappe.throw(_("Tháng dạng YYYY-MM (vd 2026-10)."))
    if dau > getdate(nowdate()):
        frappe.throw(_("Tháng {0} chưa tới.").format(dau.strftime("%m/%Y")))
    n = frappe.db.count(SO.PT_DONG, {"so": dn["name"], "ngay": ("between", [str(dau), str(cuoi)])})
    if not n:
        frappe.throw(_("Tháng {0} không có dòng nào.").format(dau.strftime("%m/%Y")))
    doc = frappe.get_doc({"doctype": SO.PT_XEM, "so": dn["name"], "thang": thang, "so_dong": n,
                          "xem_boi": frappe.session.user, "xem_luc": now_datetime(),
                          "nhan_xet": (nhan_xet or "").strip() or None})
    _luu(doc)
    return {"name": doc.name, "thang": dau.strftime("%m/%Y"), "so_dong": n}


# ── Tệp ──────────────────────────────────────────────────────────────────────────────────────

def _url_tep(doc, key):
    if key in ("tep", "ban_ky_tay"):
        return doc.get(key)
    return SO.doc_json(doc.du_lieu).get(key)


@frappe.whitelist()
def tai_len(so, ten, noi_dung, name=None, dich=None):
    """Tải một tệp (PDF / ảnh ≤ 10 MB, kiểm chữ ký đầu tệp) lên tệp riêng tư.
    · `dich` trống: tệp cho ô Attach của dòng đang ghi → trả file_url để đưa vào du_lieu.
    · `dich` = "tep" / "ban_ky_tay" + `name`: gắn vào dòng (bản ký tay scan, tệp kèm) — người có quyền ghi sổ hoặc
      Trưởng Ban ISO, kể cả dòng đã khóa (thêm bằng chứng, không đổi dữ liệu); nối vào sua_doi."""
    roles = _guard_so()
    dn, q = _so(so, roles, "xem")
    if not (q["ghi"] or (dich and _la_iso(roles))):
        frappe.throw(_("Bạn không có quyền ghi sổ {0}.").format(dn["ma"]), frappe.PermissionError)
    b = _tep_b64(ten, noi_dung, DUOI_TEP)
    if not dich:
        return {"url": _luu_tep(SO.PT, dn["name"], ten, b)}
    if dich not in ("tep", "ban_ky_tay"):
        frappe.throw(_("Chỗ gắn tệp không hợp lệ."))
    doc = _dong_doc(name)
    if doc.so != dn["name"] or doc.trang_thai == SO.NGUNG:
        frappe.throw(_("Dòng {0} không gắn tệp được.").format(name))
    url = _luu_tep(SO.PT_DONG, doc.name, ten, b)
    truoc = {dich: doc.get(dich)}
    doc.set(dich, url)
    doc.append("sua_doi", {"luc": now_datetime(), "nguoi": frappe.session.user, "hanh_dong": "Đính kèm",
                           "truoc": SO.ghi_json(truoc), "sau": SO.ghi_json({dich: url})})
    _luu(doc)
    return {"url": url, "name": doc.name}


@frappe.whitelist()
def tep(name, key):
    """Xem / tải tệp của một dòng (GET, trình duyệt mở thẳng) — người xem được sổ."""
    roles = _guard_so()
    doc = _dong_doc(name)
    _so(doc.so, roles, "xem")
    url = _url_tep(doc, key)
    if not url:
        frappe.throw(_("Dòng chưa có tệp này."))
    nd, ten = _doc_tep(url)
    frappe.local.response.filename = ten
    frappe.local.response.filecontent = nd
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "inline"


# ── In ───────────────────────────────────────────────────────────────────────────────────────

def theo_nhom(dn, dong):
    """Dòng cho bản in, đánh số TT. Sổ có `nhom_theo` (cột Select): gom theo thứ tự lựa chọn, chèn dòng tiêu đề
    nhóm {_nhom}, đánh số lại trong nhóm; dòng chưa chọn nhóm ở cuối."""
    k = dn.get("nhom_theo")
    c = next((c for c in dn["cot"] if c.get("key") == k), None) if k else None
    if not c:
        return [dict(x, stt=i) for i, x in enumerate(dong, 1)]
    ra = []
    nhom = SO.lua_chon(c)
    for ten in nhom + [None]:
        if ten is None:
            cua = [x for x in dong if x["du_lieu"].get(k) not in nhom]
        else:
            cua = [x for x in dong if x["du_lieu"].get(k) == ten]
        if not cua:
            continue
        ra.append({"_nhom": ten or "(chưa chọn nhóm)"})
        ra += [dict(x, stt=i) for i, x in enumerate(cua, 1)]
    return ra


def html_so(dn, tu=None, den=None, nam=None):
    """Bản in một sổ (không kiểm quyền — gọi sau khi đã kiểm). Ghi theo dòng: các dòng trong khoảng (mặc định tháng
    này), dòng ngừng in gạch; Danh mục: các dòng đang dùng tại lúc in."""
    nay = getdate(nowdate())
    gtd = dn["kieu"] == SO.GHI_THEO_DONG
    tu, den = _khoang(tu, den, nay) if gtd else (None, None)
    ds = _lay(dn, tu, den)
    dong, _nl = _cac_dong(dn, SO.quyen(dn, ()), set(), ds, nay)
    luoi = {c["key"]: SO.lua_chon(c) for c in dn["cot"] if c.get("kieu") == "MultiSelect" and len(SO.lua_chon(c)) <= 12}
    xem = None
    if gtd and cint(dn.get("xem_cuoi_thang")):
        t = tu.strftime("%Y-%m")
        xem = _xem_thang(dn["name"], t, [d for d in dong if str(d["ngay"])[:7] == t])
    mot_thang = gtd and tu.strftime("%Y-%m") == den.strftime("%Y-%m") and tu.day == 1
    return frappe.render_template("sx/qc/so.html", {
        "dn": dn, "ds": theo_nhom(dn, dong), "so_dong": len(dong), "tu": str(tu or ""), "den": str(den or ""),
        "luoi": luoi, "xem": xem,
        "gtd": gtd, "thang": tu.strftime("%m/%Y") if mot_thang else "", "nam": cint(nam) or nay.year,
        "ngay_in": str(nay), "so_ngung": 0 if gtd else frappe.db.count(SO.PT_DONG, {"so": dn["name"],
                                                                                  "trang_thai": SO.NGUNG})})


@frappe.whitelist()
def in_so(so, tu=None, den=None, nam=None):
    """Bản in một sổ — đầu trang chung (W42), dòng hướng dẫn, bảng cột như giấy, ô xác nhận (ký trên phần mềm),
    khối xem xét cuối tháng. Ghi theo dòng: theo khoảng ngày (mặc định tháng này); Danh mục: hiện hành."""
    roles = _guard_so()
    dn, _q = _so(so, roles, "xem")
    return html_so(dn, tu, den, nam)


def in_ho_so(ma, tu, den):
    """[(tên tệp, html)] cho gói hồ sơ đoàn đánh giá (W27): Ghi theo dòng — mỗi tháng có dòng một bản; Danh mục — bản
    hiện hành lúc tải gói. Gọi từ sx/api/qc_hoso._in (đã kiểm quyền ở đó)."""
    dn = SO.dinh_nghia(ma)
    if not dn:
        return []
    if dn["kieu"] == SO.DANH_MUC:
        return [("danh-muc.html", html_so(dn))]
    ra = []
    a = getdate(tu).replace(day=1)
    while a <= getdate(den):
        t = a.strftime("%Y-%m")
        dau, cuoi = SO.tinh_thang(t)
        if frappe.db.count(SO.PT_DONG, {"so": dn["name"], "ngay": ("between", [str(dau), str(cuoi)])}):
            ra.append((f"{t}.html", html_so(dn, dau, cuoi)))
        a = cuoi + timedelta(days=1)
    return ra
