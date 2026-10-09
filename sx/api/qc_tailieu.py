"""API thư viện tài liệu (#/tailieu) — W42, D171. Luật ở sx/qc/tai_lieu.py.

Mọi vai có tài khoản app đều vào (C27): người thường thấy tài liệu Hiện hành phân phối cho nơi nhận của mình;
Trưởng Ban ISO, siêu quyền thấy hết, cả bản cũ, Hết hiệu lực. Đề nghị BM.01.01: SX Quan Ly, ISO, QLSX, QC, QC
đóng gói, Cơ điện, Hành chính lập; Trưởng Ban ISO xem xét; Giám đốc (SX Quan Ly) duyệt; người đề nghị không tự
duyệt. Đợt ban hành: Trưởng Ban ISO lập, Trưởng Ban ISO / Giám đốc bấm ban hành. Nạp bộ tài liệu (một lần):
Trưởng Ban ISO, System Manager.

Tệp tài liệu là tệp RIÊNG TƯ — tải qua tai_tep (GET, kiểm quyền rồi trả nội dung, mở ngay trong trình duyệt),
không đưa đường dẫn /private ra màn người thường. Mở tệp (mo) ghi giờ mở lần đầu; "Đã đọc, hiểu" chỉ bấm được
sau khi đã mở (C28 — thay chữ ký nhận tài liệu giấy).
Ký điện tử (C23): gửi / xem xét / duyệt / ban hành ghi người + giờ + chức danh lúc ký, khóa sau ký; bản in ghi
"Ký trên phần mềm: Họ tên, dd/mm/yyyy hh:mm".
"""

import base64
import binascii
import json

import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime, nowdate

from sx.config.roles import NHAN_ROLE, QUAN_LY, ROLE_VIEWS, SUPER_ROLES
from sx.qc import tai_lieu as TL

ISO = "ISO Manager"
SM = "System Manager"
# Ai lập được đề nghị BM.01.01 (md W42: SX Quan Ly, ISO, QLSX, QC, QC đóng gói, Cơ điện, Hành chính — C24).
LAP_DE_NGHI = {QUAN_LY, ISO, "Production Manager", "SX QC", "SX QC Packing", "SX Co Dien", "SX Hanh Chinh"}
TEP_TOI_DA = 10 * 1024 * 1024
DAU_TEP = {"pdf": b"%PDF", "png": b"\x89PNG", "jpg": b"\xff\xd8", "jpeg": b"\xff\xd8", "docx": b"PK\x03\x04",
           "doc": b"\xd0\xcf\x11\xe0"}
TRUONG = ["name", "ma", "ten", "loai", "nguon", "trang_thai", "nhom_thu_muc", "thu_muc", "thu_tu", "thuoc",
          "lan_ban_hanh", "ngay_ban_hanh", "ngay_hieu_luc", "dot_ban_hanh", "tep", "can_xac_nhan",
          "so_hieu_co_quan", "noi_dung_ap_dung", "dan_chieu", "bo_phan_quan_ly", "ngay_soat_xet", "ghi_chu"]
TRUONG_DN = ["name", "loai_yeu_cau", "tai_lieu", "ma_de_xuat", "ten_de_xuat", "lan_ban_hanh", "ngay_hieu_luc",
             "trang_thai", "nguoi_de_nghi", "ho_ten_de_nghi", "chuc_danh_de_nghi", "bo_phan", "ngay_de_nghi",
             "gui_luc", "ly_do", "noi_dung", "bo_phan_tac_dong", "tep_du_thao", "nguoi_soan_thao", "ngay_hoan_thanh",
             "y_kien_xem_xet", "xem_xet_boi", "xem_xet_ten", "xem_xet_chuc_danh", "xem_xet_luc", "y_kien_duyet",
             "duyet_boi", "duyet_ten", "duyet_chuc_danh", "duyet_luc", "dot_ban_hanh", "nhat_ky", "owner", "creation"]
SUA_DN = ("loai_yeu_cau", "tai_lieu", "ma_de_xuat", "ten_de_xuat", "lan_ban_hanh", "ngay_hieu_luc", "bo_phan",
          "ngay_de_nghi", "ly_do", "noi_dung", "bo_phan_tac_dong", "nguoi_soan_thao", "ngay_hoan_thanh")
NGAY_DN = ("ngay_hieu_luc", "ngay_de_nghi", "ngay_hoan_thanh")
SUA_TL = ("ma", "ten", "loai", "nhom_thu_muc", "thu_muc", "thuoc", "ghi_chu", "can_xac_nhan", "so_hieu_co_quan",
          "noi_dung_ap_dung", "dan_chieu", "bo_phan_quan_ly")
SUA_DOT = ("so_quyet_dinh", "ngay_ban_hanh", "ngay_hieu_luc", "tao_yeu_cau_doc", "ghi_chu")
MA_NAP_HS = "HSVH.17-9-2026"


# ── Quyền ────────────────────────────────────────────────────────────────────────────────────

def _roles():
    return set(frappe.get_roles())


def _sieu(roles=None):
    return bool((roles if roles is not None else _roles()) & SUPER_ROLES)


def _la_iso(roles=None):
    roles = roles if roles is not None else _roles()
    return _sieu(roles) or ISO in roles


def _guard_tai_lieu():
    """Vào thư viện: mọi vai có tài khoản app (ROLE_VIEWS) — trả roles của người gọi."""
    roles = _roles()
    if _sieu(roles) or roles & set(ROLE_VIEWS):
        return roles
    frappe.throw(_("Bạn không có quyền vào thư viện tài liệu."), frappe.PermissionError)


def _guard_iso():
    roles = _guard_tai_lieu()
    if not _la_iso(roles):
        frappe.throw(_("Chỉ Trưởng Ban ISO làm được việc này."), frappe.PermissionError)
    return roles


def _guard_nap():
    roles = _guard_tai_lieu()
    if not (_la_iso(roles) or SM in roles):
        frappe.throw(_("Nạp bộ tài liệu: Trưởng Ban ISO hoặc System Manager."), frappe.PermissionError)
    return roles


def _chuc_danh(roles, viec=None):
    """Chức danh lúc ký (C23): duyệt = Giám đốc (SX Quan Ly), xem xét = Trưởng Ban ISO; còn lại theo vai."""
    if viec == "duyet" and QUAN_LY in roles:
        return "Giám đốc"
    if viec == "xem_xet" and ISO in roles:
        return NHAN_ROLE[ISO]
    ten = [t for r, t in NHAN_ROLE.items() if r in roles and r != SM]
    return ", ".join(ten) or ("Quản trị hệ thống" if SM in roles or "Administrator" in roles else "")


def _ho_ten(u=None):
    u = u or frappe.session.user
    return frappe.db.get_value("User", u, "full_name") or u


def _ngay(x):
    return str(x or "")[:10]


def _luc(x):
    return str(x or "")[:16]


# ── Dữ liệu chung ────────────────────────────────────────────────────────────────────────────

def _ds_noi_nhan():
    ds = frappe.get_all(TL.PT_NN, fields=["name", "ten", "moi_nguoi", "hinh_thuc", "thu_tu", "ghi_chu"],
                        order_by="thu_tu asc")
    vai = {}
    for r in frappe.get_all("SX Noi Nhan Vai", filters={"parenttype": TL.PT_NN}, fields=["parent", "role"]):
        vai.setdefault(r.parent, []).append(r.role)
    return [dict(x, ten=x.ten or x.name, vai=vai.get(x.name, [])) for x in ds]


def _con(dt, f=None):
    """{tài liệu: [dòng con]} của một bảng con SX Tai Lieu."""
    ra = {}
    for r in frappe.get_all(dt, filters={"parenttype": TL.PT}, fields=f or ["*"], order_by="idx asc"):
        ra.setdefault(r.parent, []).append(r)
    return ra


def _dong(x, pp, bm, iso):
    """Một tài liệu cho màn hình — không đưa đường dẫn tệp riêng tư ra ngoài."""
    d = {f: x.get(f) for f in TRUONG if f != "tep"}
    d.update(ngay_ban_hanh=_ngay(x.ngay_ban_hanh), ngay_hieu_luc=_ngay(x.ngay_hieu_luc),
             ngay_soat_xet=_ngay(x.ngay_soat_xet), co_tep=bool(x.tep), phan_phoi=pp.get(x.name, []),
             ma_bieu_mau=[{"ma": b.ma, "ten": b.ten or "", "man_app": b.man_app or ""} for b in bm.get(x.name, [])])
    d["man_app"] = TL.man_app(d)
    if not iso:
        for f in ("ghi_chu", "thu_muc"):
            d.pop(f, None)
    return d


def _can_doc(u=None):
    """Yêu cầu đọc chưa xác nhận của người dùng — chỉ của lần ban hành đang hiện hành."""
    u = u or frappe.session.user
    rows = frappe.get_all(TL.PT_DOC, filters={"user": u, "doc_luc": ("is", "not set")},
                          fields=["name", "tai_lieu", "ma", "ten_tai_lieu", "lan_ban_hanh", "dot_ban_hanh", "mo_luc",
                                  "creation"], order_by="creation asc")
    if not rows:
        return []
    hien = {x.name: x for x in frappe.get_all(TL.PT, filters={"name": ("in", [r.tai_lieu for r in rows])},
                                              fields=["name", "lan_ban_hanh", "trang_thai", "tep"])}
    ra = []
    for r in rows:
        t = hien.get(r.tai_lieu)
        if t and t.trang_thai == TL.HIEN_HANH and (r.lan_ban_hanh or "") == (t.lan_ban_hanh or ""):
            ra.append({"name": r.name, "tai_lieu": r.tai_lieu, "ma": r.ma or "", "ten": r.ten_tai_lieu or "",
                       "lan_ban_hanh": r.lan_ban_hanh or "", "dot_ban_hanh": r.dot_ban_hanh or "",
                       "mo_luc": _luc(r.mo_luc), "ngay": _ngay(r.creation), "co_tep": bool(t.tep)})
    return ra


def _xem_duoc(tl, roles):
    """tl: SX Tai Lieu (doc) — người gọi xem được không (C27)."""
    pp = [r.noi_nhan for r in (tl.get("phan_phoi") or [])]
    return TL.duoc_xem({"trang_thai": tl.trang_thai, "phan_phoi": pp},
                       TL.noi_nhan_cua(roles, _ds_noi_nhan()), _la_iso(roles))


def _cho_ky(roles):
    """W45: biên bản đang tới lượt người gọi ký — "Chờ tôi ký" ở đầu màn. Nạp muộn (chưa migrate → [])."""
    try:
        from sx.qc import bien_ban
        return bien_ban.cho_toi(frappe.session.user, roles)
    except Exception:
        return []


def _co_bien_ban(roles):
    """W45: hiện tab Biên bản — người lập / xem được ít nhất một mẫu, hoặc có biên bản mình lập / phải ký."""
    try:
        from sx.qc import bien_ban
        return bien_ban.co_bien_ban(frappe.session.user, roles, _sieu(roles))
    except Exception:
        return False


# ── Thư viện ─────────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def ds(tat_ca=0):
    """Của tôi (mặc định): tài liệu Hiện hành phân phối cho nơi nhận của mình + "Cần đọc". Tất cả (Trưởng Ban
    ISO, siêu quyền; tat_ca=1): mọi tài liệu, mọi trạng thái."""
    roles = _guard_tai_lieu()
    iso = _la_iso(roles)
    nn = _ds_noi_nhan()
    cua_toi = TL.noi_nhan_cua(roles, nn)
    pp = {k: [r.noi_nhan for r in v] for k, v in _con("SX Tai Lieu Noi Nhan", ["parent", "noi_nhan"]).items()}
    bm = _con("SX Tai Lieu Bieu Mau", ["parent", "ma", "ten", "man_app"])
    tat = iso and cint(tat_ca)
    ra = []
    for x in frappe.get_all(TL.PT, fields=TRUONG, order_by="thu_tu asc, ma asc"):
        if tat or TL.duoc_xem({"trang_thai": x.trang_thai, "phan_phoi": pp.get(x.name, [])}, cua_toi, False):
            ra.append(_dong(x, pp, bm, iso))
    return {"ds": ra, "can_doc": _can_doc(), "cho_ky": _cho_ky(roles), "bien_ban": _co_bien_ban(roles),
            "cua_toi": sorted(cua_toi), "la_iso": iso,
            "duoc_de_nghi": bool(_sieu(roles) or roles & LAP_DE_NGHI), "duoc_nap": iso or SM in roles,
            "noi_nhan": [{"ten": x["ten"], "hinh_thuc": x.get("hinh_thuc") or "", "vai": x["vai"],
                          "moi_nguoi": cint(x.get("moi_nguoi"))} for x in nn] if iso else [],
            "loai": list(TL.LOAI), "user": frappe.session.user, "hom_nay": nowdate()}


@frappe.whitelist()
def xem(name):
    """Một tài liệu: thông tin, biểu mẫu kèm, tệp kèm, phân phối; Trưởng Ban ISO thêm các lần trước."""
    roles = _guard_tai_lieu()
    tl = frappe.get_doc(TL.PT, name)
    if not _xem_duoc(tl, roles):
        frappe.throw(_("Tài liệu này không phân phối cho bạn."), frappe.PermissionError)
    iso = _la_iso(roles)
    x = frappe._dict({f: tl.get(f) for f in TRUONG})
    d = _dong(x, {name: [r.noi_nhan for r in tl.get("phan_phoi") or []]},
              {name: tl.get("ma_bieu_mau") or []}, iso)
    d["tep_kem"] = [{"i": i, "mo_ta": r.mo_ta or "", "co_tep": bool(r.tep)} for i, r in enumerate(tl.get("tep_kem") or [])]
    d["lich_su"] = [{"lan_ban_hanh": r.lan_ban_hanh or "", "ngay_ban_hanh": _ngay(r.ngay_ban_hanh),
                     "ngay_hieu_luc": _ngay(r.ngay_hieu_luc), "het_hieu_luc_tu": _ngay(r.het_hieu_luc_tu),
                     "dot_ban_hanh": r.dot_ban_hanh or "", "tom_tat_thay_doi": r.tom_tat_thay_doi or "",
                     "co_tep": bool(r.tep)} for r in (tl.get("lich_su") or [])] if iso else []
    doc = frappe.get_all(TL.PT_DOC, filters={"tai_lieu": name, "user": frappe.session.user,
                                             "lan_ban_hanh": tl.lan_ban_hanh or ""},
                         fields=["name", "mo_luc", "doc_luc"], limit=1)
    d["cua_toi"] = {"can_doc": bool(doc), "mo_luc": _luc(doc[0].mo_luc), "doc_luc": _luc(doc[0].doc_luc)} \
        if doc else {"can_doc": False}
    if iso:
        d["so_doc"] = frappe.db.count(TL.PT_DOC, {"tai_lieu": name, "lan_ban_hanh": tl.lan_ban_hanh or ""})
        d["da_doc"] = frappe.db.count(TL.PT_DOC, {"tai_lieu": name, "lan_ban_hanh": tl.lan_ban_hanh or "",
                                                  "doc_luc": ("is", "set")})
    return d


def _url_tep(name, kem=None, lan=None):
    q = f"name={name}" + (f"&kem={cint(kem)}" if kem not in (None, "") else "") + (f"&lan={lan}" if lan else "")
    return f"/api/method/sx.api.qc_tailieu.tai_tep?{q}"


@frappe.whitelist()
def mo(name, kem=None, lan=None):
    """Bấm mở tệp: ghi giờ mở lần đầu của yêu cầu đọc (nếu có) — "Đã đọc, hiểu" chỉ bấm được sau đó. Trả đường
    tải tệp (GET tai_tep). Ghi ở đây (POST) chứ không ở tai_tep: GET không commit."""
    roles = _guard_tai_lieu()
    tl = frappe.get_doc(TL.PT, name)
    if not _xem_duoc(tl, roles):
        frappe.throw(_("Tài liệu này không phân phối cho bạn."), frappe.PermissionError)
    if kem in (None, "") and not lan:
        for r in frappe.get_all(TL.PT_DOC, filters={"tai_lieu": name, "user": frappe.session.user,
                                                    "lan_ban_hanh": tl.lan_ban_hanh or "", "mo_luc": ("is", "not set")},
                                pluck="name"):
            frappe.db.set_value(TL.PT_DOC, r, "mo_luc", now_datetime())
    return {"url": _url_tep(name, kem, lan)}


def _doc_tep(url):
    """(nội dung, tên tệp) của tệp đính kèm — đọc byte trên đĩa (PDF, ảnh)."""
    ten = frappe.db.get_value("File", {"file_url": url}, "name")
    if not ten:
        frappe.throw(_("Không tìm thấy tệp trên hệ thống."))
    f = frappe.get_doc("File", ten)
    with open(f.get_full_path(), "rb") as fh:
        return fh.read(), f.file_name or url.rsplit("/", 1)[-1]


@frappe.whitelist()
def tai_tep(name, kem=None, lan=None):
    """Tải / xem tệp (GET, trình duyệt mở thẳng): kiểm quyền xem tài liệu rồi trả nội dung tệp riêng tư.
    `kem` = số thứ tự tệp kèm; `lan` = lần ban hành cũ (chỉ Trưởng Ban ISO, siêu quyền)."""
    roles = _guard_tai_lieu()
    tl = frappe.get_doc(TL.PT, name)
    if not _xem_duoc(tl, roles):
        frappe.throw(_("Tài liệu này không phân phối cho bạn."), frappe.PermissionError)
    url = tl.tep
    if kem not in (None, ""):
        kem_ds = tl.get("tep_kem") or []
        url = kem_ds[cint(kem)].tep if 0 <= cint(kem) < len(kem_ds) else None
    elif lan:
        if not _la_iso(roles):
            frappe.throw(_("Bản cũ: chỉ Trưởng Ban ISO xem."), frappe.PermissionError)
        url = next((r.tep for r in reversed(tl.get("lich_su") or []) if (r.lan_ban_hanh or "") == lan), None)
    if not url:
        frappe.throw(_("Tài liệu chưa có tệp."))
    nd, ten = _doc_tep(url)
    frappe.local.response.filename = ten
    frappe.local.response.filecontent = nd
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "inline"


@frappe.whitelist()
def da_doc(name):
    """Bấm "Đã đọc, hiểu" (C28): chỉ sau khi đã mở tệp; đã xác nhận thì không sửa, không xóa."""
    _guard_tai_lieu()
    tl = frappe.get_doc(TL.PT, name)
    r = frappe.get_all(TL.PT_DOC, filters={"tai_lieu": name, "user": frappe.session.user,
                                           "lan_ban_hanh": tl.lan_ban_hanh or ""},
                       fields=["name", "mo_luc", "doc_luc"], limit=1)
    if not r:
        frappe.throw(_("Bạn không có yêu cầu đọc tài liệu này."))
    if r[0].doc_luc:
        return {"name": name, "doc_luc": _luc(r[0].doc_luc)}
    if not r[0].mo_luc and tl.tep:
        frappe.throw(_("Mở tài liệu ra đọc trước, rồi mới bấm Đã đọc, hiểu."))
    luc = now_datetime()
    frappe.db.set_value(TL.PT_DOC, r[0].name, "doc_luc", luc)
    return {"name": name, "doc_luc": _luc(luc)}


@frappe.whitelist()
def luu_tai_lieu(payload):
    """Trưởng Ban ISO sửa tên, loại, nhóm, phân phối, biểu mẫu kèm, ghi chú, phần tài liệu bên ngoài — lần BH,
    ngày, PDF, trạng thái chỉ đổi qua Ban hành. Không có `name` = thêm tài liệu BÊN NGOÀI (BM.01.03)."""
    _guard_iso()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    if p.get("name"):
        tl = frappe.get_doc(TL.PT, p["name"])
    else:
        tl = frappe.get_doc({"doctype": TL.PT, "nguon": TL.BEN_NGOAI, "loai": TL.TL_NGOAI,
                             "trang_thai": TL.HIEN_HANH, "can_xac_nhan": 0, "ngay_soat_xet": nowdate()})
    for f in SUA_TL:
        if f in p:
            v = p[f]
            tl.set(f, cint(v) if f == "can_xac_nhan" else ((v or "").strip() if isinstance(v, str) else v) or None)
    if "phan_phoi" in p:
        co = {x["ten"] for x in _ds_noi_nhan()}
        la = [n for n in p.get("phan_phoi") or [] if n not in co]
        if la:
            frappe.throw(_("Không có nơi nhận: {0}.").format(", ".join(la)))
        tl.set("phan_phoi", [{"noi_nhan": n} for n in dict.fromkeys(p.get("phan_phoi") or [])])
    if "ma_bieu_mau" in p:
        tl.set("ma_bieu_mau", [{"ma": (b.get("ma") or "").strip(), "ten": (b.get("ten") or "").strip(),
                                "man_app": (b.get("man_app") or TL.MAN_APP.get((b.get("ma") or "").strip(), ""))}
                               for b in p.get("ma_bieu_mau") or [] if (b.get("ma") or "").strip()])
    frappe.flags.sx_ban_hanh = tl.is_new()      # tài liệu bên ngoài vào thẳng Hiện hành
    try:
        if tl.is_new():
            tl.insert(ignore_permissions=True)
        else:
            tl.save(ignore_permissions=True)
    finally:
        frappe.flags.sx_ban_hanh = False
    return {"name": tl.name}


@frappe.whitelist()
def soat_xet(names=None):
    """Trưởng Ban ISO soát xét tài liệu bên ngoài (QT.01 — ít nhất 1 lần / năm): ghi ngày soát xét hôm nay.
    names trống = mọi tài liệu bên ngoài đang hiện hành."""
    _guard_iso()
    if isinstance(names, str):
        names = json.loads(names) if names.strip().startswith("[") else [names]
    ds_ = [n for n in (names or []) if n]
    loc = {"nguon": TL.BEN_NGOAI, "trang_thai": TL.HIEN_HANH}
    if ds_:
        loc["name"] = ("in", list(ds_))
    ten = frappe.get_all(TL.PT, filters=loc, pluck="name")
    for n in ten:
        frappe.db.set_value(TL.PT, n, "ngay_soat_xet", getdate(nowdate()))
    return {"so": len(ten), "ngay": nowdate()}


# ── Đề nghị BM.01.01 ─────────────────────────────────────────────────────────────────────────

def _guard_lap():
    roles = _guard_tai_lieu()
    if not (_sieu(roles) or roles & LAP_DE_NGHI):
        frappe.throw(_("Vai của bạn chưa được lập đề nghị tài liệu — báo Trưởng Ban ISO."), frappe.PermissionError)
    return roles


def _dn(x):
    d = {f: x.get(f) for f in TRUONG_DN}
    for f in ("ngay_hieu_luc", "ngay_de_nghi", "ngay_hoan_thanh", "creation"):
        d[f] = _ngay(d.get(f))
    for f in ("gui_luc", "xem_xet_luc", "duyet_luc"):
        d[f] = _luc(d.get(f))
    d["co_tep"] = bool(d.pop("tep_du_thao", None))
    return d


@frappe.whitelist()
def de_nghi_ds():
    """Đề nghị: Trưởng Ban ISO, Giám đốc thấy tất cả; người khác thấy đề nghị của mình."""
    roles = _guard_tai_lieu()
    iso, u = _la_iso(roles), frappe.session.user
    ds_ = [_dn(x) for x in frappe.get_all(TL.PT_DN, fields=TRUONG_DN, order_by="creation desc")
           if iso or u in (x.nguoi_de_nghi, x.owner)]
    cua_toi = TL.noi_nhan_cua(roles, _ds_noi_nhan())
    pp = {k: [r.noi_nhan for r in v] for k, v in _con("SX Tai Lieu Noi Nhan", ["parent", "noi_nhan"]).items()}
    tl = [{"name": x.name, "ma": x.ma or "", "ten": x.ten, "nguon": x.nguon, "lan_ban_hanh": x.lan_ban_hanh or ""}
          for x in frappe.get_all(TL.PT, filters={"trang_thai": TL.HIEN_HANH},
                                  fields=["name", "ma", "ten", "nguon", "lan_ban_hanh", "trang_thai"],
                                  order_by="thu_tu asc, ma asc")
          if iso or TL.duoc_xem({"trang_thai": x.trang_thai, "phan_phoi": pp.get(x.name, [])}, cua_toi, False)]
    return {"ds": ds_, "tai_lieu": tl, "loai_yc": list(TL.LOAI_YC), "la_iso": iso, "la_gd": _sieu(roles),
            "duoc_lap": bool(_sieu(roles) or roles & LAP_DE_NGHI), "user": u, "hom_nay": nowdate()}


def _dn_cua(name, roles, sua=False):
    doc = frappe.get_doc(TL.PT_DN, name)
    u = frappe.session.user
    if not (_la_iso(roles) or u in (doc.nguoi_de_nghi, doc.owner)):
        frappe.throw(_("Đề nghị của người khác."), frappe.PermissionError)
    if sua and doc.trang_thai not in TL.SUA_DUOC:
        frappe.throw(_("Đề nghị đang {0} — chỉ sửa khi còn Nháp hoặc bị Trả lại.").format(doc.trang_thai.lower()))
    return doc


@frappe.whitelist()
def de_nghi_luu(payload):
    """Lập / sửa đề nghị (Nháp, Trả lại). Sửa đổi / Hủy bỏ: tên, mã lấy theo tài liệu nếu bỏ trống."""
    roles = _guard_lap()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    if p.get("name"):
        doc = _dn_cua(p["name"], roles, sua=True)
    else:
        doc = frappe.get_doc({"doctype": TL.PT_DN, "trang_thai": TL.NHAP, "nguoi_de_nghi": frappe.session.user,
                              "ho_ten_de_nghi": _ho_ten(), "ngay_de_nghi": getdate(nowdate())})
    for f in SUA_DN:
        if f in p:
            v = p.get(f)
            v = (v.strip() if isinstance(v, str) else v) or None
            doc.set(f, getdate(v) if (f in NGAY_DN and v) else v)
    if doc.tai_lieu:
        t = frappe.db.get_value(TL.PT, doc.tai_lieu, ["ma", "ten"], as_dict=True) or {}
        doc.ma_de_xuat = doc.ma_de_xuat or t.get("ma")
        doc.ten_de_xuat = doc.ten_de_xuat or t.get("ten")
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return {"name": doc.name}


def _chuyen_dn(doc, viec, y_kien="", ky=None):
    """Đổi trạng thái đề nghị theo bảng CHUYEN, ghi nhật ký; `ky` = (tiền tố ô ký, chức danh)."""
    moi = TL.chuyen(doc.trang_thai, viec)
    if not moi:
        frappe.throw(_("Đề nghị đang {0} — không {1} được.").format(doc.trang_thai.lower(), {
            "gui": "gửi", "xem_xet": "xem xét", "duyet": "duyệt", "tra_lai": "trả lại", "huy": "hủy"}[viec]))
    luc, ten = now_datetime(), _ho_ten()
    if ky:
        tien_to, cd = ky
        if tien_to == "gui":
            # Gửi lại sau khi bị trả lại: chữ ký xem xét / duyệt của vòng trước không còn giá trị.
            doc.update({"gui_luc": luc, "chuc_danh_de_nghi": cd, "ho_ten_de_nghi": doc.ho_ten_de_nghi or ten,
                        **{f"{a}_{b}": None for a in ("xem_xet", "duyet") for b in ("boi", "ten", "chuc_danh", "luc")},
                        "y_kien_xem_xet": None, "y_kien_duyet": None})
        else:
            doc.update({f"{tien_to}_boi": frappe.session.user, f"{tien_to}_ten": ten,
                        f"{tien_to}_chuc_danh": cd, f"{tien_to}_luc": luc})
            if tien_to in ("xem_xet", "duyet"):
                doc.set("y_kien_" + tien_to, (y_kien or "").strip() or None)
    doc.trang_thai = moi
    doc.nhat_ky = TL.ghi_nhat_ky(doc.nhat_ky, luc, ten, {
        "gui": "gửi đề nghị", "xem_xet": "Ban ISO xem xét — chuyển duyệt", "duyet": "Giám đốc duyệt",
        "tra_lai": "trả lại", "huy": "hủy"}[viec], y_kien)
    frappe.flags.sx_de_nghi = True
    try:
        doc.save(ignore_permissions=True)
    finally:
        frappe.flags.sx_de_nghi = False
    return {"name": doc.name, "trang_thai": doc.trang_thai}


@frappe.whitelist()
def de_nghi_gui(name):
    """Người đề nghị ký gửi (ghi giờ + chức danh) → Chờ xem xét."""
    roles = _guard_lap()
    doc = _dn_cua(name, roles)
    if frappe.session.user not in (doc.nguoi_de_nghi, doc.owner):
        frappe.throw(_("Chỉ người đề nghị gửi đề nghị của mình."), frappe.PermissionError)
    if not (doc.ly_do or "").strip():
        frappe.throw(_("Ghi lý do đề nghị."))
    return _chuyen_dn(doc, "gui", ky=("gui", _chuc_danh(roles)))


@frappe.whitelist()
def de_nghi_xem_xet(name, dong_y=1, y_kien=""):
    """Trưởng Ban ISO xem xét: đồng ý → Chờ duyệt; không → Trả lại (ghi lý do)."""
    roles = _guard_iso()
    doc = frappe.get_doc(TL.PT_DN, name)
    if cint(dong_y):
        return _chuyen_dn(doc, "xem_xet", y_kien, ("xem_xet", _chuc_danh(roles, "xem_xet")))
    if not (y_kien or "").strip():
        frappe.throw(_("Trả lại: ghi lý do."))
    return _chuyen_dn(doc, "tra_lai", y_kien)


@frappe.whitelist()
def de_nghi_duyet(name, dong_y=1, y_kien=""):
    """Giám đốc (SX Quan Ly) duyệt: đồng ý → Đã duyệt (khóa); không → Trả lại. Người đề nghị không tự duyệt."""
    roles = _guard_tai_lieu()
    if not _sieu(roles):
        frappe.throw(_("Chỉ Giám đốc duyệt đề nghị tài liệu."), frappe.PermissionError)
    doc = frappe.get_doc(TL.PT_DN, name)
    if frappe.session.user == doc.nguoi_de_nghi:
        frappe.throw(_("Người đề nghị không tự duyệt."))
    if cint(dong_y):
        return _chuyen_dn(doc, "duyet", y_kien, ("duyet", _chuc_danh(roles, "duyet")))
    if not (y_kien or "").strip():
        frappe.throw(_("Trả lại: ghi lý do."))
    return _chuyen_dn(doc, "tra_lai", y_kien)


@frappe.whitelist()
def de_nghi_huy(name, ly_do=""):
    """Người đề nghị hoặc Trưởng Ban ISO hủy đề nghị chưa duyệt."""
    roles = _guard_tai_lieu()
    doc = _dn_cua(name, roles)
    return _chuyen_dn(doc, "huy", ly_do)


def _tep_b64(ten, noi_dung, duoi_cho):
    duoi = str(ten or "").rsplit(".", 1)[-1].lower() if "." in str(ten or "") else ""
    if duoi not in duoi_cho:
        frappe.throw(_("Chỉ nhận tệp {0}.").format(", ".join(f".{d}" for d in duoi_cho)))
    try:
        b = base64.b64decode(str(noi_dung or "").split(",")[-1], validate=True)
    except (binascii.Error, ValueError):
        frappe.throw(_("Tệp hỏng — chọn lại."))
    if not b or not b.startswith(DAU_TEP[duoi]):
        frappe.throw(_("Nội dung tệp không khớp đuôi .{0}.").format(duoi))
    if len(b) > TEP_TOI_DA:
        frappe.throw(_("Tệp quá lớn (tối đa 10 MB) — {0}.").format(ten))
    return b


def _luu_tep(dt, name, ten, b):
    f = frappe.get_doc({"doctype": "File", "file_name": ten, "attached_to_doctype": dt, "attached_to_name": name,
                        "is_private": 1, "content": b})
    f.insert(ignore_permissions=True)
    return f.file_url


@frappe.whitelist()
def de_nghi_tep(name, ten, noi_dung):
    """Gắn tệp dự thảo (PDF / Word ≤ 10 MB) vào đề nghị đang soạn."""
    roles = _guard_lap()
    doc = _dn_cua(name, roles, sua=True)
    url = _luu_tep(TL.PT_DN, name, ten, _tep_b64(ten, noi_dung, ("pdf", "docx", "doc")))
    frappe.db.set_value(TL.PT_DN, doc.name, "tep_du_thao", url)
    return {"name": name}


@frappe.whitelist()
def de_nghi_tai_tep(name):
    """Tải tệp dự thảo của đề nghị (GET) — người đề nghị, Trưởng Ban ISO, Giám đốc."""
    roles = _guard_tai_lieu()
    doc = _dn_cua(name, roles)
    if not doc.tep_du_thao:
        frappe.throw(_("Đề nghị chưa có tệp dự thảo."))
    nd, ten = _doc_tep(doc.tep_du_thao)
    frappe.local.response.filename = ten
    frappe.local.response.filecontent = nd
    frappe.local.response.type = "download"


def _ky_in(ten, luc):
    return f"Ký trên phần mềm: {ten}, {getdate(luc).strftime('%d/%m/%Y')} {str(luc)[11:16]}" if luc else ""


@frappe.whitelist()
def in_bm0101(name):
    """BM.01.01 — phiếu yêu cầu sửa đổi / biên soạn tài liệu; chữ ký điện tử ghi họ tên + giờ ký (C23)."""
    roles = _guard_tai_lieu()
    doc = _dn_cua(name, roles)
    d = _dn(doc)
    d.update(ky_de_nghi=_ky_in(doc.ho_ten_de_nghi, doc.gui_luc), ky_xem_xet=_ky_in(doc.xem_xet_ten, doc.xem_xet_luc),
             ky_duyet=_ky_in(doc.duyet_ten, doc.duyet_luc))
    return frappe.render_template("sx/qc/bm0101.html", {"d": d, "LOAI_YC": TL.LOAI_YC})


# ── Đợt ban hành ─────────────────────────────────────────────────────────────────────────────

def _guard_ban_hanh():
    roles = _guard_tai_lieu()
    if not _la_iso(roles):
        frappe.throw(_("Ban hành: Trưởng Ban ISO hoặc Giám đốc."), frappe.PermissionError)
    return roles


def _tien_do(dot):
    rows = frappe.get_all(TL.PT_DOC, filters={"dot_ban_hanh": dot},
                          fields=["user", "ho_ten", "vai", "ma", "ten_tai_lieu", "mo_luc", "doc_luc"],
                          order_by="ho_ten asc")
    nguoi = {}
    for r in rows:
        x = nguoi.setdefault(r.user, {"user": r.user, "ho_ten": r.ho_ten or r.user, "vai": r.vai or "", "tong": 0,
                                      "da": 0, "chua": []})
        x["tong"] += 1
        if r.doc_luc:
            x["da"] += 1
        else:
            x["chua"].append(r.ma or r.ten_tai_lieu)
    return {"tong": len(rows), "da": sum(1 for r in rows if r.doc_luc), "nguoi": len(nguoi),
            "nguoi_xong": sum(1 for x in nguoi.values() if x["da"] == x["tong"]),
            "chua_doc": [x for x in nguoi.values() if x["chua"]]}


def _dot_dict(dot):
    ma_tl = {x.name: x for x in frappe.get_all(TL.PT, filters={
        "name": ("in", [m.tai_lieu for m in dot.get("ds") or [] if m.tai_lieu])},
        fields=["name", "ma", "ten", "nguon", "lan_ban_hanh", "trang_thai"])} if dot.get("ds") else {}
    return {"name": dot.name, "so_quyet_dinh": dot.so_quyet_dinh or "", "ngay_ban_hanh": _ngay(dot.ngay_ban_hanh),
            "ngay_hieu_luc": _ngay(dot.ngay_hieu_luc), "trang_thai": dot.trang_thai, "co_qd": bool(dot.tep_qd),
            "tao_yeu_cau_doc": cint(dot.tao_yeu_cau_doc), "ghi_chu": dot.ghi_chu or "",
            "ban_hanh_ten": dot.ban_hanh_ten or "", "ban_hanh_luc": _luc(dot.ban_hanh_luc),
            "ds": [{"row": m.name, "tai_lieu": m.tai_lieu or "", "ma": m.ma or (ma_tl.get(m.tai_lieu) or {}).get("ma") or "",
                    "ten": m.ten or (ma_tl.get(m.tai_lieu) or {}).get("ten") or "", "loai": m.loai or "",
                    "hanh_dong": m.hanh_dong, "lan_ban_hanh_moi": m.lan_ban_hanh_moi or "",
                    "lan_hien": (ma_tl.get(m.tai_lieu) or {}).get("lan_ban_hanh") or "",
                    "nguon": (ma_tl.get(m.tai_lieu) or {}).get("nguon") or (
                        TL.BEN_NGOAI if m.loai == TL.TL_NGOAI else TL.NOI_BO),
                    "co_tep": bool(m.tep_moi), "de_nghi": m.de_nghi or "", "tom_tat": m.tom_tat or "",
                    "phan_phoi": m.phan_phoi or ""} for m in dot.get("ds") or []],
            "ho_so": [{"row": r.name, "mo_ta": r.mo_ta or "", "co_tep": bool(r.tep)} for r in dot.get("ho_so") or []]}


@frappe.whitelist()
def dot_ds():
    """Các đợt ban hành + đề nghị đã duyệt chưa vào đợt nào (để kéo vào đợt nháp)."""
    roles = _guard_ban_hanh()
    ds_ = []
    for x in frappe.get_all(TL.PT_DOT, fields=["name", "so_quyet_dinh", "ngay_ban_hanh", "ngay_hieu_luc",
                                               "trang_thai", "tep_qd", "ban_hanh_luc", "creation"],
                            order_by="creation desc"):
        so = frappe.db.count("SX Dot Ban Hanh Muc", {"parent": x.name, "parenttype": TL.PT_DOT})
        ds_.append({"name": x.name, "so_quyet_dinh": x.so_quyet_dinh or "", "ngay_ban_hanh": _ngay(x.ngay_ban_hanh),
                    "ngay_hieu_luc": _ngay(x.ngay_hieu_luc), "trang_thai": x.trang_thai, "co_qd": bool(x.tep_qd),
                    "so_dong": so, "tien_do": _tien_do(x.name) if x.trang_thai == TL.DA_BAN_HANH else None})
    cho = [_dn(x) for x in frappe.get_all(TL.PT_DN, filters={"trang_thai": TL.DA_DUYET,
                                                             "dot_ban_hanh": ("is", "not set")},
                                          fields=TRUONG_DN, order_by="duyet_luc asc")]
    nn = [x["ten"] for x in _ds_noi_nhan()]
    tl = [{"name": x.name, "ma": x.ma or "", "ten": x.ten, "nguon": x.nguon, "lan_ban_hanh": x.lan_ban_hanh or ""}
          for x in frappe.get_all(TL.PT, filters={"trang_thai": TL.HIEN_HANH},
                                  fields=["name", "ma", "ten", "nguon", "lan_ban_hanh"], order_by="thu_tu asc, ma asc")]
    return {"ds": ds_, "de_nghi_cho": cho, "noi_nhan": nn, "tai_lieu": tl, "hanh_dong": list(TL.HANH_DONG),
            "loai": list(TL.LOAI), "la_gd": _sieu(roles), "hom_nay": nowdate()}


@frappe.whitelist()
def dot_xem(name):
    _guard_ban_hanh()
    dot = frappe.get_doc(TL.PT_DOT, name)
    d = _dot_dict(dot)
    d["tien_do"] = _tien_do(name)
    nguon = {r["tai_lieu"]: r["nguon"] for r in d["ds"] if r["tai_lieu"]}
    d["thieu"] = TL.thieu_ban_hanh(dot, dot.get("ds") or [], nguon) if dot.trang_thai == TL.DOT_NHAP else []
    return d


def _gan_de_nghi(dot_name, cu, moi):
    """Đề nghị kéo vào / bỏ khỏi đợt: ghi / xóa ô đợt của đề nghị (đã duyệt nên phải đặt cờ)."""
    frappe.flags.sx_de_nghi = True
    try:
        for n in cu - moi:
            if frappe.db.get_value(TL.PT_DN, n, "dot_ban_hanh") == dot_name:
                frappe.db.set_value(TL.PT_DN, n, "dot_ban_hanh", None)
        for n in moi - cu:
            khac = frappe.db.get_value(TL.PT_DN, n, ["dot_ban_hanh", "trang_thai"], as_dict=True) or {}
            if khac.get("trang_thai") != TL.DA_DUYET:
                frappe.throw(_("Đề nghị {0} chưa được duyệt.").format(n))
            if khac.get("dot_ban_hanh") and khac.get("dot_ban_hanh") != dot_name:
                frappe.throw(_("Đề nghị {0} đã ở đợt {1}.").format(n, khac.get("dot_ban_hanh")))
            frappe.db.set_value(TL.PT_DN, n, "dot_ban_hanh", dot_name)
    finally:
        frappe.flags.sx_de_nghi = False


@frappe.whitelist()
def dot_luu(payload):
    """Lập / sửa đợt NHÁP: số QĐ, ngày, ghi chú, các dòng (giữ PDF đã tải của dòng cũ theo `row`)."""
    _guard_ban_hanh()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    if p.get("name"):
        dot = frappe.get_doc(TL.PT_DOT, p["name"])
        if dot.trang_thai != TL.DOT_NHAP:
            frappe.throw(_("Đợt đã ban hành — chỉ thêm hồ sơ của đợt."))
    else:
        dot = frappe.get_doc({"doctype": TL.PT_DOT, "trang_thai": TL.DOT_NHAP, "tao_yeu_cau_doc": 1})
    for f in SUA_DOT:
        if f in p:
            v = p.get(f)
            if f == "tao_yeu_cau_doc":
                v = cint(v)
            elif f in ("ngay_ban_hanh", "ngay_hieu_luc"):
                v = getdate(v) if v else None
            else:
                v = (v or "").strip() or None
            dot.set(f, v)
    de_nghi_cu = {m.de_nghi for m in dot.get("ds") or [] if m.de_nghi}
    if "ds" in p:
        cu = {m.name: m for m in dot.get("ds") or []}
        moi = []
        for r in p.get("ds") or []:
            if r.get("hanh_dong") not in TL.HANH_DONG:
                frappe.throw(_("Hành động phải là {0}.").format(" / ".join(TL.HANH_DONG)))
            m = {f: (r.get(f) or "").strip() if isinstance(r.get(f), str) else r.get(f)
                 for f in ("tai_lieu", "ma", "ten", "loai", "hanh_dong", "lan_ban_hanh_moi", "de_nghi", "tom_tat",
                           "phan_phoi")}
            if m.get("tai_lieu"):
                t = frappe.db.get_value(TL.PT, m["tai_lieu"], ["ma", "ten"], as_dict=True)
                if not t:
                    frappe.throw(_("Không có tài liệu {0}.").format(m["tai_lieu"]))
                m["ma"], m["ten"] = m.get("ma") or t.ma, m.get("ten") or t.ten
            goc = cu.get(r.get("row"))
            m["tep_moi"] = goc.tep_moi if goc else None
            moi.append({k: (v or None) for k, v in m.items()})
        dot.set("ds", moi)
    if dot.is_new():
        dot.insert(ignore_permissions=True)
    else:
        dot.save(ignore_permissions=True)
    _gan_de_nghi(dot.name, de_nghi_cu, {m.de_nghi for m in dot.get("ds") or [] if m.de_nghi})
    return {"name": dot.name}


@frappe.whitelist()
def dot_keo_de_nghi(name):
    """Kéo mọi đề nghị đã duyệt, chưa vào đợt nào, vào đợt nháp này (hành động theo loại yêu cầu)."""
    _guard_ban_hanh()
    dot = frappe.get_doc(TL.PT_DOT, name)
    if dot.trang_thai != TL.DOT_NHAP:
        frappe.throw(_("Đợt đã ban hành."))
    co = {m.de_nghi for m in dot.get("ds") or [] if m.de_nghi}
    them = 0
    for x in frappe.get_all(TL.PT_DN, filters={"trang_thai": TL.DA_DUYET, "dot_ban_hanh": ("is", "not set")},
                            fields=["name", "loai_yeu_cau", "tai_lieu", "ma_de_xuat", "ten_de_xuat", "lan_ban_hanh",
                                    "noi_dung", "ly_do"], order_by="duyet_luc asc"):
        if x.name in co:
            continue
        dot.append("ds", {"tai_lieu": x.tai_lieu, "ma": x.ma_de_xuat, "ten": x.ten_de_xuat,
                          "loai": TL.TL_NGOAI if x.loai_yeu_cau == TL.AP_DUNG else None,
                          "hanh_dong": TL.HD_CUA_YC[x.loai_yeu_cau], "lan_ban_hanh_moi": x.lan_ban_hanh,
                          "de_nghi": x.name, "tom_tat": " ".join(str(x.noi_dung or x.ly_do or "").split())[:500]})
        them += 1
    dot.save(ignore_permissions=True)
    _gan_de_nghi(dot.name, co, {m.de_nghi for m in dot.get("ds") or [] if m.de_nghi})
    return {"name": name, "them": them}


@frappe.whitelist()
def dot_tep(name, dich, ten, noi_dung):
    """Tải tệp cho đợt: dich = "qd" (quyết định đã ký, PDF), "row:<dòng>" (PDF bản mới đã ký của một dòng),
    "hs" (hồ sơ của đợt: biên bản phổ biến có chữ ký…, PDF / ảnh — thêm được cả sau khi đã ban hành)."""
    _guard_ban_hanh()
    dot = frappe.get_doc(TL.PT_DOT, name)
    if dich == "hs":
        url = _luu_tep(TL.PT_DOT, name, ten, _tep_b64(ten, noi_dung, ("pdf", "png", "jpg", "jpeg")))
        dot.append("ho_so", {"tep": url, "mo_ta": ten})
        dot.save(ignore_permissions=True)
        return {"name": name}
    if dot.trang_thai != TL.DOT_NHAP:
        frappe.throw(_("Đợt đã ban hành — chỉ thêm hồ sơ của đợt."))
    url = _luu_tep(TL.PT_DOT, name, ten, _tep_b64(ten, noi_dung, ("pdf",)))
    if dich == "qd":
        dot.tep_qd = url
    elif str(dich).startswith("row:"):
        m = next((m for m in dot.get("ds") or [] if m.name == dich[4:]), None)
        if not m:
            frappe.throw(_("Không có dòng {0} trong đợt.").format(dich[4:]))
        m.tep_moi = url
    else:
        frappe.throw(_("Tải tệp vào đâu?"))
    dot.save(ignore_permissions=True)
    return {"name": name}


@frappe.whitelist()
def dot_tai_tep(name, dich):
    """Xem tệp của đợt (GET): "qd", "row:<dòng>", "hs:<dòng>" — Trưởng Ban ISO, Giám đốc."""
    _guard_ban_hanh()
    dot = frappe.get_doc(TL.PT_DOT, name)
    if dich == "qd":
        url = dot.tep_qd
    else:
        loai, _x, row = str(dich).partition(":")
        bang = dot.get("ds" if loai == "row" else "ho_so") or []
        m = next((m for m in bang if m.name == row), None)
        url = (m.tep_moi if loai == "row" else m.tep) if m else None
    if not url:
        frappe.throw(_("Chưa có tệp."))
    nd, ten = _doc_tep(url)
    frappe.local.response.filename = ten
    frappe.local.response.filecontent = nd
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "inline"


@frappe.whitelist()
def dot_xoa(name):
    """Xóa đợt nháp lập nhầm (đề nghị trong đợt trả về chờ kéo vào đợt khác)."""
    _guard_ban_hanh()
    dot = frappe.get_doc(TL.PT_DOT, name)
    if dot.trang_thai != TL.DOT_NHAP:
        frappe.throw(_("Đợt đã ban hành — không xóa."))
    _gan_de_nghi(name, {m.de_nghi for m in dot.get("ds") or [] if m.de_nghi}, set())
    frappe.delete_doc(TL.PT_DOT, name, ignore_permissions=True)
    return {"name": name}


def _nguoi_dung(ds_nn):
    """({role: {user}}, {user app}, {user: (họ tên, chức danh)}) — tài khoản đang bật."""
    can = {r for x in ds_nn for r in x["vai"]}
    if any(x.get("moi_nguoi") for x in ds_nn):
        can |= set(ROLE_VIEWS)
    theo_role, vai_cua = {}, {}
    for r in frappe.get_all("Has Role", filters={"parenttype": "User", "role": ("in", sorted(can))},
                            fields=["parent", "role"]):
        theo_role.setdefault(r.role, set()).add(r.parent)
        vai_cua.setdefault(r.parent, set()).add(r.role)
    bat = {u.name: u for u in frappe.get_all("User", filters={"enabled": 1, "name": ("in", sorted(vai_cua))},
                                              fields=["name", "full_name"])}
    theo_role = {k: {u for u in v if u in bat} for k, v in theo_role.items()}
    app = {u for u, vs in vai_cua.items() if u in bat and vs & set(ROLE_VIEWS)}
    info = {u: (bat[u].full_name or u, _chuc_danh(vai_cua.get(u, set()))) for u in bat}
    return theo_role, app, info


def tao_yeu_cau_doc(ds_tl, dot_name):
    """Yêu cầu đọc cho người thuộc nơi nhận của từng tài liệu (phải xác nhận đã đọc), lần đang hiện hành.
    Yêu cầu chưa xác nhận của bản cũ hơn bỏ đi — người ta đọc bản mới. Trả số dòng tạo."""
    nn = _ds_noi_nhan()
    theo_role, app, info = _nguoi_dung(nn)
    tao = 0
    for tl in ds_tl:
        if not cint(tl.get("can_xac_nhan")) or tl.get("trang_thai") != TL.HIEN_HANH:
            continue
        lan = tl.get("lan_ban_hanh") or ""
        for r in frappe.get_all(TL.PT_DOC, filters={"tai_lieu": tl.name, "doc_luc": ("is", "not set")},
                                fields=["name", "lan_ban_hanh"]):
            if (r.lan_ban_hanh or "") != lan:
                frappe.delete_doc(TL.PT_DOC, r.name, ignore_permissions=True)
        co = set(frappe.get_all(TL.PT_DOC, filters={"tai_lieu": tl.name, "lan_ban_hanh": lan}, pluck="user"))
        for u in sorted(TL.nguoi_nhan([r.noi_nhan for r in tl.get("phan_phoi") or []], nn, theo_role, app) - co):
            if u not in info:
                continue
            frappe.get_doc({"doctype": TL.PT_DOC, "tai_lieu": tl.name, "ma": tl.ma, "ten_tai_lieu": tl.ten,
                            "lan_ban_hanh": lan, "dot_ban_hanh": dot_name, "user": u, "ho_ten": info[u][0],
                            "vai": info[u][1]}).insert(ignore_permissions=True)
            tao += 1
    return tao


def _bo_yeu_cau_chua_doc(tl_name):
    for r in frappe.get_all(TL.PT_DOC, filters={"tai_lieu": tl_name, "doc_luc": ("is", "not set")}, pluck="name"):
        frappe.delete_doc(TL.PT_DOC, r, ignore_permissions=True)


@frappe.whitelist()
def ban_hanh(name):
    """Ban hành đợt (Trưởng Ban ISO / Giám đốc): kiểm số QĐ, QĐ scan, PDF từng dòng; rồi trong MỘT giao dịch: bản
    cũ vào lịch sử, ghi bản mới, Hủy bỏ → Hết hiệu lực, tài liệu mới được tạo; yêu cầu đọc cho người thuộc nơi
    nhận; khóa đợt (ký: người + giờ)."""
    roles = _guard_ban_hanh()
    dot = frappe.get_doc(TL.PT_DOT, name)
    if dot.trang_thai != TL.DOT_NHAP:
        frappe.throw(_("Đợt {0} đã ban hành.").format(name))
    nguon = {x.name: x.nguon for x in frappe.get_all(TL.PT, filters={
        "name": ("in", [m.tai_lieu for m in dot.get("ds") or [] if m.tai_lieu])}, fields=["name", "nguon"])}
    loi = TL.thieu_ban_hanh(dot, dot.get("ds") or [], nguon)
    if loi:
        frappe.throw("<br>".join(loi))
    co_nn = {x["ten"] for x in _ds_noi_nhan()}
    moi = []
    frappe.flags.sx_ban_hanh = True
    try:
        for m in dot.get("ds") or []:
            if m.hanh_dong == TL.BH_GIU:
                continue
            if m.tai_lieu:
                tl = frappe.get_doc(TL.PT, m.tai_lieu)
            else:
                ngoai = m.loai == TL.TL_NGOAI
                tl = frappe.get_doc({
                    "doctype": TL.PT, "ma": m.ma, "ten": m.ten, "loai": m.loai or TL.KHAC,
                    "nguon": TL.BEN_NGOAI if ngoai else TL.NOI_BO, "trang_thai": TL.DU_THAO,
                    "can_xac_nhan": 0 if ngoai else 1, "ngay_soat_xet": dot.ngay_ban_hanh if ngoai else None,
                    "phan_phoi": [{"noi_nhan": n} for n in dict.fromkeys(
                        x.strip() for x in str(m.phan_phoi or "").split(",") if x.strip() in co_nn)]})
                tl.insert(ignore_permissions=True)
                m.tai_lieu = tl.name
            ls, cap = TL.ban_moi(tl, m, dot)
            if ls:
                tl.append("lich_su", ls)
            tl.update(cap)
            tl.save(ignore_permissions=True)
            if tl.trang_thai == TL.HIEN_HANH:
                moi.append(tl)
            else:
                _bo_yeu_cau_chua_doc(tl.name)
        dot.update({"trang_thai": TL.DA_BAN_HANH, "ban_hanh_boi": frappe.session.user, "ban_hanh_ten": _ho_ten(),
                    "ban_hanh_luc": now_datetime()})
        dot.save(ignore_permissions=True)
    finally:
        frappe.flags.sx_ban_hanh = False
    so = tao_yeu_cau_doc(moi, name) if cint(dot.tao_yeu_cau_doc) else 0
    return {"name": name, "trang_thai": dot.trang_thai, "so_tai_lieu": len(moi), "yeu_cau_doc": so,
            "chuc_danh": _chuc_danh(roles)}


@frappe.whitelist()
def tien_do_doc(name):
    """Tiến độ xác nhận đọc của đợt: x/y lượt, người xong, danh sách chưa đọc."""
    _guard_ban_hanh()
    return _tien_do(name)


# ── Nạp bộ tài liệu (một lần) ────────────────────────────────────────────────────────────────

def _tim_tl(x):
    """Tài liệu đã nạp ứng với một dòng kế hoạch (theo mã; không mã thì theo dòng sổ đăng ký)."""
    if x["ma"]:
        return frappe.db.get_value(TL.PT, {"ma": x["ma"]}, "name")
    return frappe.db.get_value(TL.PT, {"nguon": x["nguon"], "thu_tu": x["thu_tu"], "ma": ("is", "not set")}, "name")


def _ke_hoach(payload):
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    return p, TL.ke_hoach_nap(p.get("tai_lieu") or [], p.get("ngoai") or {}, p.get("phan_phoi") or {})


@frappe.whitelist()
def nap_bo(payload):
    """Nạp sổ đăng ký 21/9/2026 (seed_tai_lieu), BM.01.03 (seed_tai_lieu_ngoai), Phụ lục 3 (seed_phan_phoi):
    tạo cái CHƯA CÓ — chạy lại không nhân đôi, không đè chỗ Ban ISO đã sửa. Trả các tệp còn phải tải
    (can_tep, khoá → nap_tep); tệp đã có thì `co`."""
    _guard_nap()
    p, kh = _ke_hoach(payload)
    tao = {"noi_nhan": 0, "tai_lieu": 0, "ngoai": 0, "dot": 0, "ho_so_dot": 0, "ho_so": 0, "phan_phoi": 0,
           "yeu_cau_doc": 0}
    for x in kh["noi_nhan"]:
        if frappe.db.exists(TL.PT_NN, x["ten"]):
            continue
        thieu = [r for r in x["vai"] if not frappe.db.exists("Role", r)]
        if thieu:
            kh["loi"].append(f"Nơi nhận {x['ten']}: site chưa có role {', '.join(thieu)} — thêm vai trên Desk rồi "
                             "sửa nơi nhận")
        frappe.get_doc({"doctype": TL.PT_NN, "ten": x["ten"], "hinh_thuc": x["hinh_thuc"], "thu_tu": x["thu_tu"],
                        "moi_nguoi": x["moi_nguoi"],
                        "vai": [{"role": r} for r in x["vai"] if r not in thieu]}).insert(ignore_permissions=True)
        tao["noi_nhan"] += 1
    ten_tl = {}
    frappe.flags.sx_ban_hanh = True
    try:
        for x in kh["tai_lieu"]:
            n = _tim_tl(x)
            if not n:
                d = {k: x.get(k) for k in ("ma", "ten", "loai", "nguon", "thu_muc", "nhom_thu_muc", "thu_tu",
                                           "lan_ban_hanh", "ngay_ban_hanh", "ngay_hieu_luc", "tep_goc", "ghi_chu",
                                           "can_xac_nhan", "so_hieu_co_quan", "noi_dung_ap_dung", "dan_chieu",
                                           "bo_phan_quan_ly", "ngay_soat_xet")}
                doc = frappe.get_doc(dict({k: v for k, v in d.items() if v not in (None, "")}, doctype=TL.PT,
                                          trang_thai=TL.HIEN_HANH, ma_bieu_mau=x["ma_bieu_mau"]))
                doc.insert(ignore_permissions=True)
                n = doc.name
                tao["ngoai" if x["nguon"] == TL.BEN_NGOAI else "tai_lieu"] += 1
            ten_tl[TL.khoa_tl(x)] = n
        co_nn = {x for x in frappe.get_all(TL.PT_NN, pluck="name")}
        for khoa, nns in kh["phan_phoi"].items():
            n = ten_tl.get(khoa)
            if not n:
                continue
            doc = frappe.get_doc(TL.PT, n)
            if doc.get("phan_phoi"):
                continue                      # Ban ISO đã phân phối — giữ
            doc.set("phan_phoi", [{"noi_nhan": t} for t in nns if t in co_nn])
            doc.save(ignore_permissions=True)
            tao["phan_phoi"] += 1
        for a in kh["anh"]:
            n = ten_tl.get(a["gan_vao"])
            if not n:
                continue
            doc = frappe.get_doc(TL.PT, n)
            if not any(r.tep_goc == a["tep_goc"] for r in doc.get("tep_kem") or []):
                doc.append("tep_kem", {"mo_ta": a["mo_ta"], "tep_goc": a["tep_goc"]})
                doc.save(ignore_permissions=True)
        dot_name = None
        if kh["dot"]:
            ma_nap = f"nap:{kh['dot']['ngay_ban_hanh']}"
            dot_name = frappe.db.get_value(TL.PT_DOT, {"ma_nap": ma_nap}, "name")
            if not dot_name:
                ngay = kh["dot"]["ngay_ban_hanh"]
                ds_dot = [x for x in kh["tai_lieu"] if x.get("ngay_ban_hanh") == ngay and ten_tl.get(TL.khoa_tl(x))]
                dot = frappe.get_doc({
                    "doctype": TL.PT_DOT, "trang_thai": TL.DA_BAN_HANH, "ngay_ban_hanh": ngay,
                    "ngay_hieu_luc": kh["dot"]["ngay_hieu_luc"], "ma_nap": ma_nap,
                    "tep_qd_goc": kh["dot"]["tep_goc"], "tao_yeu_cau_doc": cint(p.get("tao_yeu_cau_doc")),
                    "ghi_chu": " · ".join(t for t in (kh["dot"]["ten"], kh["dot"]["ghi_chu"]) if t),
                    "ban_hanh_boi": frappe.session.user, "ban_hanh_ten": _ho_ten(), "ban_hanh_luc": now_datetime(),
                    "ds": [{"tai_lieu": ten_tl[TL.khoa_tl(x)], "ma": x["ma"], "ten": x["ten"],
                            "hanh_dong": x["hanh_dong"], "lan_ban_hanh_moi": x["lan_ban_hanh"]} for x in ds_dot]})
                dot.insert(ignore_permissions=True)
                dot_name = dot.name
                tao["dot"] = 1
                for x in ds_dot:
                    frappe.db.set_value(TL.PT, ten_tl[TL.khoa_tl(x)], "dot_ban_hanh", dot_name)
                if cint(p.get("tao_yeu_cau_doc")):
                    tao["yeu_cau_doc"] = tao_yeu_cau_doc(
                        [frappe.get_doc(TL.PT, ten_tl[TL.khoa_tl(x)]) for x in ds_dot], dot_name)
            dot = frappe.get_doc(TL.PT_DOT, dot_name)
            them = [h for h in kh["ho_so_dot"] if not any(r.tep_goc == h["tep_goc"] for r in dot.get("ho_so") or [])]
            for h in them:
                dot.append("ho_so", {"mo_ta": h["mo_ta"], "tep_goc": h["tep_goc"]})
            if them:
                dot.save(ignore_permissions=True)
                tao["ho_so_dot"] += len(them)
    finally:
        frappe.flags.sx_ban_hanh = False
    for h in kh["ho_so"]:
        if frappe.db.exists("SX Ho So Danh Muc", {"ma": MA_NAP_HS}):
            continue
        frappe.get_doc({"doctype": "SX Ho So Danh Muc", "ma": MA_NAP_HS, "ten": h["ten"],
                        "nhom": "Hệ thống quản lý", "nguon": "Tệp đính kèm",
                        "ngay_ban_hanh": h.get("ngay"), "ghi_chu": f"Nạp từ bộ tài liệu — tệp {h['tep_goc']}",
                        "noi_luu": "Thư viện tài liệu (nạp bộ 21/9/2026)"}).insert(ignore_permissions=True)
        tao["ho_so"] += 1
    return {"tao": tao, "can_tep": _can_tep(kh, ten_tl, dot_name), "loi": kh["loi"]}


def _can_tep(kh, ten_tl, dot_name):
    """[{khoa, tep, mo_ta, co}] — mọi tệp của bộ tài liệu và đã có trên app chưa."""
    ra = []
    for x in kh["tai_lieu"]:
        n = ten_tl.get(TL.khoa_tl(x))
        if n and x.get("tep_goc"):
            ra.append({"khoa": f"tl:{n}", "tep": x["tep_goc"], "mo_ta": x["ma"] or x["ten"],
                       "co": bool(frappe.db.get_value(TL.PT, n, "tep"))})
    for a in kh["anh"]:
        n = ten_tl.get(a["gan_vao"])
        if n:
            co = any(r.tep_goc == a["tep_goc"] and r.tep for r in frappe.get_doc(TL.PT, n).get("tep_kem") or [])
            ra.append({"khoa": f"kem:{n}", "tep": a["tep_goc"], "mo_ta": f"{a['gan_vao']} — ảnh", "co": co})
    if dot_name:
        dot = frappe.get_doc(TL.PT_DOT, dot_name)
        if kh["dot"] and kh["dot"]["tep_goc"]:
            ra.append({"khoa": f"qd:{dot_name}", "tep": kh["dot"]["tep_goc"], "mo_ta": "Quyết định ban hành",
                       "co": bool(dot.tep_qd)})
        for h in kh["ho_so_dot"]:
            co = any(r.tep_goc == h["tep_goc"] and r.tep for r in dot.get("ho_so") or [])
            ra.append({"khoa": f"hsdot:{dot_name}", "tep": h["tep_goc"], "mo_ta": h["mo_ta"], "co": co})
    for h in kh["ho_so"]:
        n = frappe.db.get_value("SX Ho So Danh Muc", {"ma": MA_NAP_HS}, ["name", "tep"], as_dict=True)
        if n:
            ra.append({"khoa": f"hs:{n.name}", "tep": h["tep_goc"], "mo_ta": h["ten"], "co": bool(n.tep)})
    return ra


@frappe.whitelist()
def nap_tep(khoa, ten, noi_dung):
    """Tải một tệp của bộ tài liệu (PDF / PNG ≤ 10 MB, kiểm chữ ký đầu tệp) vào đúng chỗ theo `khoa` của
    nap_bo; tên tệp phải đúng tên trong sổ đăng ký."""
    _guard_nap()
    loai, _x, n = str(khoa).partition(":")
    b = _tep_b64(ten, noi_dung, ("pdf", "png"))
    frappe.flags.sx_ban_hanh = True
    try:
        if loai == "tl":
            doc = frappe.get_doc(TL.PT, n)
            if doc.tep_goc != ten:
                frappe.throw(_("Tệp {0} không phải tệp của {1}.").format(ten, doc.ma or doc.ten))
            doc.tep = _luu_tep(TL.PT, n, ten, b)
            doc.save(ignore_permissions=True)
        elif loai == "kem":
            doc = frappe.get_doc(TL.PT, n)
            r = next((r for r in doc.get("tep_kem") or [] if r.tep_goc == ten), None)
            if not r:
                frappe.throw(_("Tệp {0} không phải ảnh kèm của {1}.").format(ten, doc.ma or doc.ten))
            r.tep = _luu_tep(TL.PT, n, ten, b)
            doc.save(ignore_permissions=True)
        elif loai in ("qd", "hsdot"):
            dot = frappe.get_doc(TL.PT_DOT, n)
            if loai == "qd":
                if dot.tep_qd_goc != ten:
                    frappe.throw(_("Tệp {0} không phải quyết định của đợt {1}.").format(ten, n))
                dot.tep_qd = _luu_tep(TL.PT_DOT, n, ten, b)
            else:
                r = next((r for r in dot.get("ho_so") or [] if r.tep_goc == ten), None)
                if not r:
                    frappe.throw(_("Tệp {0} không phải hồ sơ của đợt {1}.").format(ten, n))
                r.tep = _luu_tep(TL.PT_DOT, n, ten, b)
            dot.save(ignore_permissions=True)
        elif loai == "hs":
            hs = frappe.db.get_value("SX Ho So Danh Muc", n, ["name", "ghi_chu"], as_dict=True)
            if not hs or ten not in (hs.ghi_chu or ""):
                frappe.throw(_("Tệp {0} không phải hồ sơ {1}.").format(ten, n))
            frappe.db.set_value("SX Ho So Danh Muc", n, "tep", _luu_tep("SX Ho So Danh Muc", n, ten, b))
        else:
            frappe.throw(_("Không rõ tệp này gắn vào đâu."))
    finally:
        frappe.flags.sx_ban_hanh = False
    return {"khoa": khoa, "tep": ten}


# ── Bản in ───────────────────────────────────────────────────────────────────────────────────

def _nhom(ds_):
    """[(nhóm, [dòng])] giữ thứ tự sổ đăng ký."""
    ra = []
    for x in ds_:
        n = x.get("nhom_thu_muc") or "Khác"
        g = next((g for g in ra if g[0] == n), None)
        if not g:
            g = (n, [])
            ra.append(g)
        g[1].append(x)
    return ra


@frappe.whitelist()
def in_bm0102():
    """BM.01.02 Danh mục tài liệu nội bộ — app tự lập từ thư viện: tài liệu Hiện hành, theo nhóm."""
    _guard_tai_lieu()
    pp = {k: [r.noi_nhan for r in v] for k, v in _con("SX Tai Lieu Noi Nhan", ["parent", "noi_nhan"]).items()}
    ds_ = [dict(x, ngay_ban_hanh=_ngay(x.ngay_ban_hanh), ngay_hieu_luc=_ngay(x.ngay_hieu_luc),
                phan_phoi=pp.get(x.name, []))
           for x in frappe.get_all(TL.PT, filters={"nguon": TL.NOI_BO, "trang_thai": TL.HIEN_HANH}, fields=TRUONG,
                                   order_by="thu_tu asc, ma asc")]
    het = frappe.get_all(TL.PT, filters={"nguon": TL.NOI_BO, "trang_thai": TL.HET},
                         fields=["ma", "ten", "lan_ban_hanh", "dot_ban_hanh"], order_by="ma asc")
    return frappe.render_template("sx/qc/bm0102.html", {"nhom": _nhom(ds_), "tong": len(ds_), "het": het,
                                                        "ngay": nowdate(), "nguoi": _ho_ten()})


@frappe.whitelist()
def in_bm0103():
    """BM.01.03 Danh mục tài liệu bên ngoài — app tự lập: theo nhóm A/B/C, ngày soát xét."""
    _guard_tai_lieu()
    ds_ = [dict(x, ngay_soat_xet=_ngay(x.ngay_soat_xet))
           for x in frappe.get_all(TL.PT, filters={"nguon": TL.BEN_NGOAI, "trang_thai": TL.HIEN_HANH},
                                   fields=TRUONG, order_by="thu_tu asc, ma asc")]
    soat = max((x["ngay_soat_xet"] for x in ds_ if x["ngay_soat_xet"]), default="")
    return frappe.render_template("sx/qc/bm0103.html", {"nhom": _nhom(ds_), "tong": len(ds_), "soat": soat,
                                                        "ngay": nowdate(), "nguoi": _ho_ten()})


@frappe.whitelist()
def in_bm0113(name):
    """BM.01.13 theo đợt: QĐ, ngày áp dụng, tài liệu phổ biến; người nhận — "Đã đọc trên phần mềm lúc …" hoặc ô
    ký tay (người chưa xác nhận / không có tài khoản, C28); danh sách phân phối theo nơi nhận."""
    _guard_ban_hanh()
    dot = frappe.get_doc(TL.PT_DOT, name)
    d = _dot_dict(dot)
    nn = {x["ten"]: x for x in _ds_noi_nhan()}
    pp = {k: [r.noi_nhan for r in v] for k, v in _con("SX Tai Lieu Noi Nhan", ["parent", "noi_nhan"]).items()}
    phan_phoi = []
    for r in d["ds"]:
        if r["hanh_dong"] == TL.BH_GIU or not r["tai_lieu"]:
            continue
        for t in pp.get(r["tai_lieu"], []):
            phan_phoi.append({"ma": r["ma"] or r["ten"], "noi_nhan": t, "hinh_thuc": (nn.get(t) or {}).get("hinh_thuc", "")})
    doc = frappe.get_all(TL.PT_DOC, filters={"dot_ban_hanh": name},
                         fields=["user", "ho_ten", "vai", "ma", "ten_tai_lieu", "lan_ban_hanh", "doc_luc"],
                         order_by="ho_ten asc, ma asc")
    return frappe.render_template("sx/qc/bm0113.html", {
        "d": d, "doc": [dict(r, doc_luc=_luc(r.doc_luc)) for r in doc], "phan_phoi": phan_phoi,
        "ky_ban_hanh": _ky_in(dot.ban_hanh_ten, dot.ban_hanh_luc), "ngay": nowdate()})
