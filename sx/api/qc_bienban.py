"""API khung Biên bản (W45, D174) — màn #/qc/bienban (QC → Xem xét → Biên bản) và #/tailieu/bienban (mọi vai: biên
bản mình lập / phải ký; "Chờ tôi ký" ở đầu màn Tài liệu). Luật ở sx/qc/bien_ban.py; controller SX Bien Ban chặn cả
Desk (chỉ API, khóa sau ký đủ).

Ai làm gì: lập theo vai lập của mẫu (Trưởng Ban ISO, siêu quyền luôn lập được; checklist / tổng hợp đánh giá nội bộ:
chuyên gia có tên trong kế hoạch); người lập (hoặc Trưởng Ban ISO) sửa khi Nháp / Trả lại, gửi ký; ký theo thứ tự ô ký
của mẫu — ô "người lập" do người lập ký, ô có vai do người có vai đó ký, ô trưởng đoàn do trưởng đoàn của kế hoạch ký;
một người không ký hai ô; người đang tới lượt ký trả lại được (ghi ý kiến). Ký điện tử (C23): người + giờ + chức danh,
khóa khi đủ chữ ký; ô ký tay (người ngoài, văn bản gửi ra ngoài): in, ký, tải bản scan — chưa có bản scan thì không
khóa. Ký đủ → việc giao thành việc định kỳ "Một lần"; việc định kỳ năm có ô hồ sơ đúng mã mẫu được ghi "đã làm".
Tệp đính kèm là tệp riêng tư — tải qua `tai_tep` (GET, kiểm quyền xem biên bản).
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime, nowdate

from sx.api.qc_tailieu import _chuc_danh, _doc_tep, _ky_in, _luu_tep, _tep_b64
from sx.config.roles import ROLE_VIEWS, SUPER_ROLES
from sx.qc import bien_ban as BB
from sx.qc import khac_phuc as KP
from sx.qc import so as SO
from sx.qc import viec_dinh_ky as VD

DUOI_TEP = ("pdf", "png", "jpg", "jpeg")
VD_PT = "SX Viec Dinh Ky"


# ── Quyền ────────────────────────────────────────────────────────────────────────────────────

def _roles():
    return set(frappe.get_roles())


def _sieu(roles):
    return bool(roles & SUPER_ROLES)


def _guard_bb():
    """Vào biên bản: mọi vai có tài khoản app (ROLE_VIEWS) hoặc siêu quyền — trả roles của người gọi. Quyền từng việc
    (lập, sửa, ký) kiểm theo mẫu và biên bản."""
    roles = _roles()
    if _sieu(roles) or roles & set(ROLE_VIEWS):
        return roles
    frappe.throw(_("Bạn không có quyền vào biên bản."), frappe.PermissionError)


def _p(payload):
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    if not isinstance(p, dict):
        frappe.throw(_("Dữ liệu gửi lên không đúng định dạng."))
    return p


def _lay(name):
    if not name or not frappe.db.exists(BB.PT_BB, name):
        frappe.throw(_("Không có biên bản {0}.").format(name))
    return frappe.get_doc(BB.PT_BB, name)


def _luu(doc):
    """Lưu qua API — cờ cho controller (Desk chỉ đọc)."""
    frappe.flags.sx_bb = True
    try:
        if doc.is_new():
            doc.insert(ignore_permissions=True)
        else:
            doc.save(ignore_permissions=True)
    finally:
        frappe.flags.sx_bb = False
    return doc


_TEN = {}


def _ten(u):
    if not u:
        return ""
    if u not in _TEN:
        _TEN[u] = frappe.db.get_value("User", u, "full_name") or u
    return _TEN[u]


def _nd(doc):
    return BB.doc_json(doc.get("noi_dung"), {}) or {}


def _ky_ds(doc):
    return [r for r in doc.get("ky") or []]


def _goc_nd(doc):
    return (BB.doc_json(frappe.db.get_value(BB.PT_BB, doc.goc, "noi_dung"), {}) or {}) if doc.get("goc") else {}


def _cg_dot(doc):
    """Chuyên gia (tài khoản) của đợt đánh giá nội bộ mà biên bản thuộc về — họ xem được kế hoạch và các phiếu của đợt."""
    if doc.get("mau") == BB.DGNB_KH:
        return {x["user"] for x in BB.chuyen_gia(_nd(doc))}
    if doc.get("mau") in BB.DGNB_CON and doc.get("goc"):
        return {x["user"] for x in BB.chuyen_gia(_goc_nd(doc))}
    return set()


def _bb_dict(doc):
    return {"name": doc.name, "mau": doc.mau, "trang_thai": doc.trang_thai, "nguoi_lap": doc.nguoi_lap,
            "ky": [dict(r) if isinstance(r, dict) else r.as_dict() for r in _ky_ds(doc)], "noi_dung": _nd(doc),
            "dinh_nghia": BB.dinh_nghia_bb(doc), "ban_ky_tay": doc.ban_ky_tay}


def _quyen(doc, roles, m=None):
    m = m if m is not None else (BB.mau(doc.mau) or {})
    return BB.quyen_bb(_bb_dict(doc), m, frappe.session.user, roles, _sieu(roles), _cg_dot(doc))


def _can(doc, roles, viec):
    q = _quyen(doc, roles)
    if not q.get(viec):
        ten = {"xem": "xem", "sua": "sửa", "gui": "gửi ký", "ky": "ký", "tra_lai": "trả lại", "xoa": "xóa",
               "car": "lập BM.01.07 từ"}.get(viec, viec)
        frappe.throw(_("Bạn không {0} được biên bản {1} ({2}).").format(ten, doc.name, doc.trang_thai),
                     frappe.PermissionError)
    return q


# ── Danh sách ────────────────────────────────────────────────────────────────────────────────

def _dot_cg():
    """{kế hoạch BM.01.05: {tài khoản chuyên gia}} — để chuyên gia thấy các phiếu của đợt mình."""
    ra = {}
    for x in frappe.get_all(BB.PT_BB, filters={"mau": BB.DGNB_KH}, fields=["name", "noi_dung"]):
        ra[x.name] = {c["user"] for c in BB.chuyen_gia(BB.doc_json(x.noi_dung, {}) or {})}
    return ra


def _xem_nhe(x, m, user, roles, sieu, dot):
    if sieu or BB.ISO in roles or x.get("nguoi_lap") == user:
        return True
    if BB.quyen_mau(m or {}, roles, sieu)["xem"] or BB.co_o_ky(x.get("ky"), user, roles, x.get("nguoi_lap")):
        return True
    ke_hoach = x["name"] if x.get("mau") == BB.DGNB_KH else x.get("goc")
    return user in dot.get(ke_hoach, ())


def _dong_ds(x, user, roles):
    s = BB.o_cho(x.get("ky"))
    o, _l = BB.o_ky_cua(x.get("ky") or [], user, roles, x.get("nguoi_lap")) if x.get("trang_thai") == BB.CHO_KY \
        else (None, None)
    tay = any(cint(k.get("ky_tay")) for k in x.get("ky") or [])
    return {"name": x["name"], "mau": x.get("mau"), "ten_mau": x.get("ten_mau") or "", "so": x.get("so") or "",
            "ngay": str(x.get("ngay") or ""), "tieu_de": x.get("tieu_de") or "", "trang_thai": x.get("trang_thai"),
            "nguoi_lap": _ten(x.get("nguoi_lap")), "cho": (s or {}).get("vai_tro") if x.get("trang_thai") == BB.CHO_KY
            else "", "thieu_ky_tay": bool(x.get("trang_thai") == BB.CHO_KY and tay and not x.get("ban_ky_tay")),
            "toi_ky": o is not None, "goc": x.get("goc") or ""}


@frappe.whitelist()
def ds(mau=None, trang_thai=None):
    """Mẫu (lập được không, đếm) + biên bản người gọi xem được (mới trước) + "Chờ tôi ký"."""
    roles = _guard_bb()
    user, sieu = frappe.session.user, _sieu(roles)
    mau_ds = {m["name"]: m for m in BB.ds_mau()}
    dot = _dot_cg()
    bb = [x for x in BB.ds_bb_nhe() if _xem_nhe(x, mau_ds.get(x["mau"]), user, roles, sieu, dot)]
    cg = {k for k, v in dot.items() if user in v}
    ra_mau = []
    for ten, m in mau_ds.items():
        cua = [x for x in bb if x["mau"] == ten]
        lap = BB.quyen_mau(m, roles, sieu)["lap"] or (ten in BB.DGNB_CON and bool(cg))
        if not (lap or cua or BB.quyen_mau(m, roles, sieu)["xem"]):
            continue
        ra_mau.append({"ma": ten, "ten": m.get("ten") or "", "chu_ky_lap": m.get("chu_ky_lap"),
                       "quy_trinh": m.get("quy_trinh") or "", "goc_mau": m.get("goc_mau") or "", "lap": lap,
                       "so": len(cua), "cho_ky": sum(1 for x in cua if x["trang_thai"] == BB.CHO_KY),
                       "nhap": sum(1 for x in cua if x["trang_thai"] in BB.SUA_DUOC),
                       "lan_cuoi": max((str(x["ngay"]) for x in cua), default="")})
    loc = [x for x in bb if (not mau or x["mau"] == mau) and (not trang_thai or x["trang_thai"] == trang_thai)]
    return {"mau": ra_mau, "ds": [_dong_ds(x, user, roles) for x in loc[:300]],
            "cho_toi": BB.cho_ky_cua([x for x in bb if x["trang_thai"] == BB.CHO_KY], user, roles),
            "trang_thai": list(BB.TRANG_THAI), "la_iso": bool(sieu or BB.ISO in roles), "user": user,
            "hom_nay": nowdate()}


@frappe.whitelist()
def cho_toi():
    """Biên bản đang tới lượt người gọi ký — đầu màn Tài liệu."""
    roles = _guard_bb()
    return BB.cho_toi(frappe.session.user, roles)


@frappe.whitelist()
def nguoi():
    """Tài khoản đang dùng có vai của app — cho ô "người thực hiện", "chuyên gia" (kiểu User)."""
    _guard_bb()
    u = sorted(set(frappe.get_all("Has Role", filters={"parenttype": "User", "role": ("in", sorted(ROLE_VIEWS))},
                                  pluck="parent")))
    ds_ = frappe.get_all("User", filters={"name": ("in", u or [""]), "enabled": 1}, fields=["name", "full_name"],
                         order_by="full_name asc")
    return [{"v": x.name, "nhan": x.full_name or x.name} for x in ds_]


# ── Lập ──────────────────────────────────────────────────────────────────────────────────────

def _phan_dau(dn_phan):
    return next((p for p in dn_phan if p.get("key") == BB.DAU and p.get("kieu") == BB.VAN_BAN), None)


def _dn_man(dn):
    """Các phần cho màn hình: cột kèm lựa chọn tách sẵn, cột câu hỏi, cột kết luận, cột app tính."""
    ra = []
    for p in dn.get("phan") or []:
        cot = [dict(c, lua_chon=SO.lua_chon(c)) for c in BB.cot_cua(p)]
        kl = BB.cot_ket_luan(p)
        ra.append(dict({k: p.get(k) for k in ("key", "tieu_de", "kieu", "nguon", "tinh", "chi_khi", "bat_buoc",
                                                "them_dong")}, cot=cot, ket_luan=kl["key"] if kl else None,
                       cot_tinh=sorted(BB.cot_tinh(p)),
                       nguon_ten=(BB.NGUON.get(p.get("nguon") or "") or ("",))[0]))
    return ra


@frappe.whitelist()
def mau_lap(ma):
    """Thông tin để lập một biên bản: ô đầu phiếu, biên bản gốc chọn được (BM.04.02 ← 04.01…), bộ phận được phân
    (checklist BM.01.06), có lần trước để chép không."""
    roles = _guard_bb()
    m = BB.mau(ma)
    if not m or cint(m.get("ngung")):
        frappe.throw(_("Không có mẫu biên bản {0} (hoặc đã ngừng).").format(ma))
    user = frappe.session.user
    dn = BB.chup_mau(m)
    goc = []
    if m.get("goc_mau"):
        for x in frappe.get_all(BB.PT_BB, filters={"mau": m["goc_mau"], "trang_thai": BB.DA_KY},
                                fields=["name", "so", "ngay", "tieu_de", "noi_dung"], order_by="ngay desc", limit=30):
            nd = BB.doc_json(x.noi_dung, {}) or {}
            g = {"name": x.name, "so": x.so or "", "ngay": str(x.ngay), "tieu_de": x.tieu_de or ""}
            if ma in BB.DGNB_CON:
                cg = next((c for c in BB.chuyen_gia(nd) if c["user"] == user), None)
                if not (cg or _sieu(roles) or BB.ISO in roles):
                    continue
                g["bo_phan"] = BB.bo_phan_cua(nd, cg) if cg else sorted({
                    str(r.get("bo_phan")).strip() for r in (nd.get("chi_tiet") or {}).get("dong") or []
                    if str(r.get("bo_phan") or "").strip()})
            goc.append(g)
    lap = BB.quyen_mau(m, roles, _sieu(roles))["lap"] or (ma in BB.DGNB_CON and bool(goc))
    if not lap:
        frappe.throw(_("Bạn không lập được {0}.").format(ma), frappe.PermissionError)
    co_bang = any(p.get("kieu") == BB.BANG and not p.get("nguon") for p in dn["phan"])
    truoc = frappe.get_all(BB.PT_BB, filters={"mau": ma, "trang_thai": BB.DA_KY}, fields=["name", "so", "ngay"],
                           order_by="ngay desc", limit=1) if co_bang else []
    p_dau = _phan_dau(dn["phan"])
    return {"ma": ma, "ten": m.get("ten") or "", "nhan_ngay": dn["nhan_ngay"], "goc_mau": m.get("goc_mau") or "",
            "can_goc": ma in BB.DGNB_CON, "goc": goc,
            "dau": [dict(c, lua_chon=SO.lua_chon(c)) for c in BB.cot_nhap(p_dau)] if p_dau else [],
            "chep": {"name": truoc[0].name, "so": truoc[0].so, "ngay": str(truoc[0].ngay)} if truoc else None,
            "ghi_chu": m.get("ghi_chu") or "", "hom_nay": nowdate()}


def _truoc(mau, ngay, bo=None):
    """Ngày biên bản cùng mẫu gần nhất trước `ngay` (kỳ kéo dữ liệu)."""
    loc = {"mau": mau, "ngay": ("<", str(getdate(ngay)))}
    if bo:
        loc["name"] = ("!=", bo)
    x = frappe.get_all(BB.PT_BB, filters=loc, fields=["ngay"], order_by="ngay desc", limit=1)
    return x[0].ngay if x else None


def _ham():
    """Hàm phần SX truyền vào hàm kéo (module qc không import phần SX)."""
    def nhac():
        from sx.api import qc as Q
        from sx.qc import nhac as NH
        d = getdate(nowdate())
        return NH.tinh(d, **Q._du_lieu_nhac(d))

    def bc_thang(t):
        from sx.api import qc_baocao
        return qc_baocao._du_lieu(t)

    return {"nhac": nhac, "bc_thang": bc_thang, "lo_thu_hoi": _lo_thu_hoi}


def _lo_thu_hoi():
    """Lô đang có cờ thu hồi: đã bán theo khách, đã thu về (hóa đơn trả lại), tồn — sổ cái lô của màn Truy xuất."""
    from sx.api import truyxuat as TX
    ra = []
    for b in frappe.get_all("Batch", filters={"custom_thu_hoi": 1},
                            fields=["name", "item", "item_name", "expiry_date", "batch_qty"],
                            order_by="custom_thu_hoi_luc desc", limit=20):
        theo = {}
        for x in TX._ban(TX._so_cai(b.name))["ban"]:
            k = x.get("ten_khach") or x.get("khach") or "?"
            g = theo.setdefault(k, {"khach": k, "so": 0.0, "tra_ve": 0.0})
            if x.get("tra_lai"):
                g["tra_ve"] += -float(x["so"] or 0)
            else:
                g["so"] += float(x["so"] or 0)
        ra.append({"batch": b.name, "ten": b.item_name or b.item, "hsd": str(b.expiry_date or ""),
                   "ton": b.batch_qty or 0, "ban": list(theo.values())})
    return ra


def _ctx(mau_ma, chu_ky, ngay, dau, ten=None, goc=None):
    tu, den = BB.ky_du_lieu(chu_ky, ngay, _truoc(mau_ma, ngay, ten))
    return {"ngay": getdate(ngay), "tu": tu, "den": den, "mau": mau_ma, "dau": dau or {}, "bien_ban": ten,
            "goc": (BB.doc_json(frappe.db.get_value(BB.PT_BB, goc, "noi_dung"), {}) or {}) if goc else {},
            "goc_ten": goc, "ham": _ham()}


def _keo_tat_ca(dn, nd, ctx, chi=None):
    """Kéo (lại) các phần có hàm kéo — bản chụp vào nội dung."""
    luc = str(now_datetime())[:16]
    dau = BB.gia_tri_dau(nd)
    for p in dn["phan"]:
        if not p.get("nguon") or (chi and p["key"] != chi) or not BB.phan_ap_dung(p, dau):
            continue
        snap = BB.keo(p["nguon"], dict(ctx, dau=dau), luc)
        nd[p["key"]] = BB.ap_keo(p, snap, nd.get(p["key"]))
    return nd


def _tu_goc(ma, nd, goc_doc, user):
    """Chép từ biên bản gốc (luật theo mã mẫu): BM.04.02 ← hạng mục BM.04.01; BM.02.02 ← số, ngày, số lượng của
    BM.02.01; BM.01.06 ← tên chuyên gia; BM.01.09 ← thời gian của kế hoạch."""
    gnd = BB.doc_json(goc_doc.noi_dung, {}) or {}
    gdau = BB.gia_tri_dau(gnd)
    dau = nd.setdefault(BB.DAU, {}).setdefault("gia_tri", {})
    if ma == BB.THAM_TRA_BC:
        rows = [r for r in (gnd.get("ke_hoach") or {}).get("dong") or [] if r.get("hang_muc") or r.get("noi_dung")]
        if rows:
            nd["bao_cao"] = {"dong": [dict({k: r[k] for k in ("hang_muc", "noi_dung") if r.get(k)}, _id=f"m{i}",
                                           _co_dinh=1) for i, r in enumerate(rows, 1)]}
    elif ma == BB.THU_HOI_BC:
        dau.setdefault("so_ke_hoach", goc_doc.so or goc_doc.name)
        dau.setdefault("ngay_ke_hoach", str(goc_doc.ngay))
        kq = nd.setdefault("ket_qua", {}).setdefault("gia_tri", {})
        sp = " — ".join(x for x in (gdau.get("ten_san_pham"), f"HSD {BB.ngay_vn(gdau['han_su_dung'])}"
                                    if gdau.get("han_su_dung") else "") if x)
        if sp:
            kq.setdefault("san_pham_so_lo", sp)
        if str(gdau.get("muc_do") or "").startswith("Mức độ "):
            kq.setdefault("muc_do", gdau["muc_do"][-1])
        if gdau.get("so_luong_da_xuat") not in (None, ""):
            kq.setdefault("so_luong_da_xuat", gdau["so_luong_da_xuat"])
    elif ma == BB.DGNB_CL:
        dau.setdefault("chuyen_gia", _ten(user))
    elif ma == BB.DGNB_BC:
        if gdau.get("thoi_gian_thuc_hien"):
            dau.setdefault("thoi_gian_danh_gia", gdau["thoi_gian_thuc_hien"])
    return nd


def _chep_bang(dn, nd, ten_truoc):
    """Chép các Bảng (không kéo dữ liệu) của biên bản cùng mẫu lần trước — BM.14.01 / 14.02 xem xét lại hằng năm."""
    cu = BB.doc_json(frappe.db.get_value(BB.PT_BB, ten_truoc, "noi_dung"), {}) or {}
    for p in dn["phan"]:
        if p.get("kieu") == BB.BANG and not p.get("nguon") and (cu.get(p["key"]) or {}).get("dong"):
            nd[p["key"]] = BB.tinh_phan(p, {"dong": [dict({k: v for k, v in r.items() if not k.startswith("_")},
                                                          _id=f"t{i}")
                                                     for i, r in enumerate(cu[p["key"]]["dong"], 1)]})
    return nd


def _roles_cua(u):
    return frappe.get_roles(u) if u else []


def _kiem_rieng(ma, nd, doc_goc_nd, nguoi_lap, du=False):
    """Luật riêng theo mẫu — đánh giá nội bộ (QT.01)."""
    loi = []
    if ma == BB.DGNB_KH:
        loi += BB.loi_doc_lap(nd, _roles_cua, du)
    elif ma == BB.DGNB_CL:
        e = BB.loi_checklist(doc_goc_nd, nguoi_lap, BB.gia_tri_dau(nd).get("bo_phan"))
        if e:
            loi.append(e)
    return loi


@frappe.whitelist()
def lap(payload):
    """Lập biên bản: {mau, ngay, tieu_de, dau: {ô đầu phiếu}, goc, chep}. Kéo dữ liệu ngay lúc lập (bản chụp)."""
    roles = _guard_bb()
    p = _p(payload)
    user = frappe.session.user
    m = BB.mau(p.get("mau"))
    if not m or cint(m.get("ngung")):
        frappe.throw(_("Không có mẫu biên bản {0} (hoặc đã ngừng).").format(p.get("mau")))
    ma = m["name"]
    goc_doc = None
    if p.get("goc"):
        goc_doc = _lay(p["goc"])
        if goc_doc.mau != m.get("goc_mau") or goc_doc.trang_thai != BB.DA_KY:
            frappe.throw(_("Biên bản gốc phải là {0} đã ký đủ.").format(m.get("goc_mau") or "…"))
    elif ma in BB.DGNB_CON:
        frappe.throw(_("Chọn kế hoạch đánh giá nội bộ BM.01.05 đã duyệt (đợt đánh giá)."))
    goc_nd = BB.doc_json(goc_doc.noi_dung, {}) or {} if goc_doc else {}
    la_cg = bool(goc_doc and ma in BB.DGNB_CON and any(c["user"] == user for c in BB.chuyen_gia(goc_nd)))
    if not (BB.quyen_mau(m, roles, _sieu(roles))["lap"] or la_cg):
        frappe.throw(_("Bạn không lập được {0}.").format(ma), frappe.PermissionError)
    ngay = getdate(p.get("ngay") or nowdate())
    if ngay > getdate(nowdate()):
        frappe.throw(_("Ngày biên bản không được sau hôm nay."))
    dn = BB.chup_mau(m)
    p_dau = _phan_dau(dn["phan"])
    dau = {}
    if p_dau:
        v, loi = BB.sach_phan(p_dau, {"gia_tri": p.get("dau") or {}}, None, SO.tra)
        if loi:
            frappe.throw(" ".join(loi))
        dau = v.get("gia_tri") or {}
    nd = BB.noi_dung_dau(dn["phan"], dau)
    if goc_doc:
        nd = _tu_goc(ma, nd, goc_doc, user)
    if cint(p.get("chep")):
        truoc = frappe.get_all(BB.PT_BB, filters={"mau": ma, "trang_thai": BB.DA_KY}, pluck="name",
                               order_by="ngay desc", limit=1)
        if truoc:
            nd = _chep_bang(dn, nd, truoc[0])
    loi = _kiem_rieng(ma, nd, goc_nd, user)
    if loi:
        frappe.throw(" ".join(loi))
    nd = _keo_tat_ca(dn, nd, _ctx(ma, m.get("chu_ky_lap"), ngay, dau, None, goc_doc.name if goc_doc else None))
    td = BB.truong_doan(goc_nd) if goc_doc and ma in BB.DGNB_CON else None
    ky = []
    for s in m["ky"]:
        r = {k: s.get(k) for k in ("vai_tro", "role", "nguoi_lap", "thu_tu", "bat_buoc", "ky_tay")}
        if td and str(s.get("vai_tro") or "").startswith(BB.TRUONG_DOAN):
            r.update(user=td["user"], gan=1)
        ky.append(r)
    nam = ngay.year
    da_co = frappe.get_all(BB.PT_BB, filters={"mau": ma, "ngay": ("between", [f"{nam}-01-01", f"{nam}-12-31"])},
                           pluck="so")
    doc = frappe.get_doc({"doctype": BB.PT_BB, "mau": ma, "ten_mau": m.get("ten"), "ngay": ngay,
                          "so": BB.so_bien_ban(da_co, m.get("ky_hieu_so"), nam),
                          "tieu_de": (p.get("tieu_de") or "").strip() or f"{m.get('ten')} {BB.ngay_vn(ngay)}",
                          "trang_thai": BB.NHAP, "nguoi_lap": user, "goc": goc_doc.name if goc_doc else None,
                          "noi_dung": BB.ghi_json(nd), "dinh_nghia": BB.ghi_json(dn), "ky": ky})
    _luu(doc)
    return {"name": doc.name, "so": doc.so}


# ── Xem ──────────────────────────────────────────────────────────────────────────────────────

def _ra(doc, roles):
    dn = BB.dinh_nghia_bb(doc)
    nd = _nd(doc)
    q = _quyen(doc, roles)
    dau = BB.gia_tri_dau(nd)
    cho = BB.o_cho(_ky_ds(doc)) if doc.trang_thai == BB.CHO_KY else None
    lq = [{"loai": r.loai, "ten": r.ten, "ghi_chu": r.ghi_chu or ""} for r in doc.get("lien_quan") or []]
    car = {r["ghi_chu"]: r["ten"] for r in lq if r["loai"] == KP.PT and r["ghi_chu"]}
    kph = [dict(x, car=car.get(f"{x['phan']}:{x['dong']}")) for x in BB.dong_kph(dn["phan"], nd)]
    goc = frappe.db.get_value(BB.PT_BB, doc.goc, ["name", "mau", "so"], as_dict=True) if doc.goc else None
    return {
        "name": doc.name, "mau": doc.mau, "ten_mau": doc.ten_mau or dn.get("ten") or "", "so": doc.so or "",
        "ngay": str(doc.ngay or ""), "tieu_de": doc.tieu_de or "", "trang_thai": doc.trang_thai,
        "nguoi_lap": doc.nguoi_lap, "ten_nguoi_lap": _ten(doc.nguoi_lap), "gui_luc": str(doc.gui_luc or "")[:16],
        "ky_du_luc": str(doc.ky_du_luc or "")[:16], "y_kien_tra_lai": doc.y_kien_tra_lai or "",
        "goc": {"name": goc.name, "mau": goc.mau, "so": goc.so or ""} if goc else None,
        "nhan_ngay": dn.get("nhan_ngay") or "Ngày", "quy_trinh": dn.get("quy_trinh") or "",
        "phan": _dn_man(dn), "noi_dung": nd,
        "ap_dung": {p["key"]: BB.phan_ap_dung(p, dau) for p in dn["phan"]},
        "dong_ap_dung": {p["key"]: [r.get("_id") for r in (nd.get(p["key"]) or {}).get("dong") or []
                                    if BB.dong_ap_dung(p, r, dau)] for p in dn["phan"] if p.get("kieu") == BB.DS_KIEM},
        "ky": [{"vai_tro": s.vai_tro or "", "ten": s.ten or (_ten(s.user) if s.user else ""), "user": s.user or "",
                "chuc_danh": s.chuc_danh or "", "ky_luc": str(s.ky_luc or "")[:16], "y_kien": s.y_kien or "",
                "ky_tay": cint(s.ky_tay), "bat_buoc": cint(s.bat_buoc), "gan": cint(s.get("gan")),
                "cho": bool(cho is not None and s is cho)} for s in BB.ky_sap(_ky_ds(doc))],
        "can_ky_tay": BB.can_ky_tay(_ky_ds(doc), dau, dn.get("ky_tay_khi")), "co_ky_tay": bool(doc.ban_ky_tay),
        "lien_quan": lq, "kph": kph,
        "viec": [{"noi_dung": r.noi_dung or "", "nguoi": _ten(r.phu_trach) if r.phu_trach else (r.nguoi or ""),
                  "han": str(r.han or ""), "viec_dinh_ky": r.viec_dinh_ky or "", "xong": cint(r.xong)}
                 for r in doc.get("viec") or []],
        "tep_kem": [{"i": i, "mo_ta": r.mo_ta or "", "luc": str(r.luc or "")[:16], "nguoi": _ten(r.nguoi)}
                    for i, r in enumerate(doc.get("tep_kem") or [])],
        "quyen": q, "user": frappe.session.user, "hom_nay": nowdate(),
        "chep_cau_hoi": bool(q.get("sua") and any(p.get("kieu") == BB.DS_KIEM and cint(p.get("them_dong"))
                                                  for p in dn["phan"]) and doc.mau == BB.DGNB_CL),
    }


@frappe.whitelist()
def xem(name):
    roles = _guard_bb()
    doc = _lay(name)
    _can(doc, roles, "xem")
    return _ra(doc, roles)


# ── Sửa, kéo lại, gửi ────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def luu(name, payload):
    """Ghi nội dung (Nháp / Trả lại): {ngay?, tieu_de?, noi_dung: {phần: giá trị}} — phần không gửi giữ nguyên; câu in
    sẵn, bản chụp kéo dữ liệu không đổi được; ô sai kiểu bị chặn, ô bắt buộc kiểm lúc gửi ký."""
    roles = _guard_bb()
    doc = _lay(name)
    _can(doc, roles, "sua")
    p = _p(payload)
    dn = BB.dinh_nghia_bb(doc)
    nd, loi = BB.sach_noi_dung(dn["phan"], p.get("noi_dung") or {}, _nd(doc), SO.tra)
    if "ngay" in p:
        ngay = getdate(p["ngay"] or nowdate())
        if ngay > getdate(nowdate()):
            loi.append("Ngày biên bản không được sau hôm nay.")
        doc.ngay = ngay
    if "tieu_de" in p:
        doc.tieu_de = (p.get("tieu_de") or "").strip() or doc.tieu_de
    loi += _kiem_rieng(doc.mau, nd, _goc_nd(doc), doc.nguoi_lap)
    if loi:
        frappe.throw(" ".join(loi))
    doc.noi_dung = BB.ghi_json(nd)
    _luu(doc)
    return _ra(doc, roles)


@frappe.whitelist()
def keo_lai(name, phan=None):
    """Kéo lại dữ liệu (Nháp / Trả lại) — bản chụp mới theo đầu phiếu, ngày hiện tại của biên bản."""
    roles = _guard_bb()
    doc = _lay(name)
    _can(doc, roles, "sua")
    dn = BB.dinh_nghia_bb(doc)
    nd = _nd(doc)
    ctx = _ctx(doc.mau, dn.get("chu_ky_lap"), doc.ngay, BB.gia_tri_dau(nd), doc.name, doc.goc)
    doc.noi_dung = BB.ghi_json(_keo_tat_ca(dn, nd, ctx, phan or None))
    _luu(doc)
    return _ra(doc, roles)


@frappe.whitelist()
def chep_cau_hoi(name):
    """Checklist BM.01.06: chép câu hỏi từ checklist gần nhất (ưu tiên cùng bộ phận) — chỉ câu hỏi, không chép kết
    luận, bằng chứng; câu đã có thì bỏ qua."""
    roles = _guard_bb()
    doc = _lay(name)
    _can(doc, roles, "sua")
    dn = BB.dinh_nghia_bb(doc)
    nd = _nd(doc)
    bp = BB.khong_dau(BB.gia_tri_dau(nd).get("bo_phan"))
    ds_ = frappe.get_all(BB.PT_BB, filters={"mau": doc.mau, "name": ("!=", doc.name)}, fields=["name", "noi_dung"],
                         order_by="ngay desc, creation desc", limit=50)
    chon = next((x for x in ds_ if bp and BB.khong_dau(BB.gia_tri_dau(BB.doc_json(x.noi_dung, {})).get("bo_phan"))
                 == bp), None) or (ds_[0] if ds_ else None)
    if not chon:
        frappe.throw(_("Chưa có checklist nào trước để chép."))
    cu = BB.doc_json(chon.noi_dung, {}) or {}
    them = 0
    for p in dn["phan"]:
        if p.get("kieu") != BB.DS_KIEM or not cint(p.get("them_dong")):
            continue
        hoi = [c["key"] for c in BB.cot_hoi(p)]
        dong = list((nd.get(p["key"]) or {}).get("dong") or [])
        co = {tuple(str(r.get(k) or "") for k in hoi) for r in dong}
        moi = []
        for r in (cu.get(p["key"]) or {}).get("dong") or []:
            k = tuple(str(r.get(c) or "") for c in hoi)
            if any(k) and k not in co:
                co.add(k)
                moi.append({c: r[c] for c in hoi if r.get(c)})
        if moi:
            v, loi = BB.sach_phan(p, {"dong": dong + moi}, nd.get(p["key"]), SO.tra)
            if loi:
                frappe.throw(" ".join(loi))
            nd[p["key"]] = v
            them += len(moi)
    doc.noi_dung = BB.ghi_json(nd)
    _luu(doc)
    return dict(_ra(doc, roles), da_chep=them, chep_tu=chon.name)


@frappe.whitelist()
def gui(name):
    """Gửi ký: đủ ô bắt buộc → Chờ ký (khóa nội dung tới khi ký đủ hoặc bị trả lại)."""
    roles = _guard_bb()
    doc = _lay(name)
    _can(doc, roles, "gui")
    dn = BB.dinh_nghia_bb(doc)
    nd = _nd(doc)
    loi = BB.thieu(dn["phan"], nd) + _kiem_rieng(doc.mau, nd, _goc_nd(doc), doc.nguoi_lap, du=True)
    if loi:
        frappe.throw(_("Chưa gửi ký được — {0}").format(" ".join(loi[:8]) + (" …" if len(loi) > 8 else "")))
    doc.trang_thai = BB.CHO_KY
    doc.gui_luc = now_datetime()
    for s in _ky_ds(doc):
        s.ky_luc = None
        s.ten = s.chuc_danh = s.y_kien = None
        if not cint(s.get("gan")):
            s.user = None
    if BB.du_chu_ky(_ky_ds(doc), doc.ban_ky_tay, BB.gia_tri_dau(nd), dn.get("ky_tay_khi")):
        _khoa(doc, dn, nd)
    _luu(doc)
    return _ra(doc, roles)


# ── Ký, trả lại, ký tay ─────────────────────────────────────────────────────────────────────

def _ghi_viec(doc, dn, nd):
    """Ký đủ: mỗi việc giao (và ô hạn) thành một việc định kỳ "Một lần" — hộp nhắc sẵn có nhắc hạn."""
    rows = []
    nl = _ten(doc.nguoi_lap)
    for v in BB.viec_tu_noi_dung(dn["phan"], nd):
        nguoi = _ten(v["phu_trach"]) if v.get("phu_trach") else (v.get("nguoi") or nl)
        vd = frappe.get_doc({"doctype": VD_PT, "ten": BB._ngan(f"{v['noi_dung']} ({doc.mau} số {doc.so})", 140),
                             "chu_ky": "Một lần", "han": v.get("han") or None, "bao_truoc": 7, "phu_trach": nguoi,
                             "ho_so": f"{doc.mau} số {doc.so}",
                             "mo_ta": BB._ngan(f"Việc giao — {doc.ten_mau} số {doc.so} ngày {BB.ngay_vn(doc.ngay)} "
                                               f"({doc.name}): {v['noi_dung']}", 2000)})
        vd.insert(ignore_permissions=True)
        rows.append({"noi_dung": v["noi_dung"], "phu_trach": v.get("phu_trach"), "nguoi": v.get("nguoi"),
                     "han": v.get("han") or None, "viec_dinh_ky": vd.name, "phan": v.get("phan"),
                     "dong": v.get("dong")})
    doc.set("viec", rows)


def _danh_dau_dinh_ky(doc):
    """Việc định kỳ năm (ĐGNB, xem xét lãnh đạo, thẩm tra, diễn tập…) có ô hồ sơ đúng mã mẫu → ghi lần làm."""
    for v in frappe.get_all(VD_PT, filters={"ngung": 0, "chu_ky": ("!=", "Một lần")}, fields=["name", "ho_so"]):
        if not BB.khop_ho_so(v.ho_so, doc.mau):
            continue
        vd = frappe.get_doc(VD_PT, v.name)
        if any(doc.name in str(r.get("ghi_chu") or "") for r in vd.get("ds_lan") or []):
            continue
        VD.ghi_lan(vd, doc.ngay, f"{doc.mau} số {doc.so} ({doc.name}) ký đủ")
        vd.save(ignore_permissions=True)


def _khoa(doc, dn, nd):
    doc.trang_thai = BB.DA_KY
    doc.ky_du_luc = now_datetime()
    _ghi_viec(doc, dn, nd)
    _danh_dau_dinh_ky(doc)


@frappe.whitelist()
def ky(name, y_kien=""):
    """Ký ô tới lượt (người + giờ + chức danh, C23); đủ chữ ký → khóa."""
    roles = _guard_bb()
    doc = _lay(name)
    if doc.trang_thai != BB.CHO_KY:
        frappe.throw(_("Biên bản {0} đang {1} — không ký được.").format(doc.name, (doc.trang_thai or "").lower()))
    user = frappe.session.user
    s, loi = BB.o_ky_cua(_ky_ds(doc), user, roles, doc.nguoi_lap)
    if s is None:
        frappe.throw(loi, frappe.PermissionError)
    s.user = user
    s.ten = _ten(user)
    s.chuc_danh = _chuc_danh(roles)
    s.ky_luc = now_datetime()
    s.y_kien = (y_kien or "").strip() or None
    dn = BB.dinh_nghia_bb(doc)
    nd = _nd(doc)
    if BB.du_chu_ky(_ky_ds(doc), doc.ban_ky_tay, BB.gia_tri_dau(nd), dn.get("ky_tay_khi")):
        _khoa(doc, dn, nd)
    _luu(doc)
    return _ra(doc, roles)


@frappe.whitelist()
def tra_lai(name, y_kien=""):
    """Người đang tới lượt ký trả lại (ghi ý kiến) → Trả lại: người lập sửa, gửi lại; chữ ký vòng này, bản ký tay
    bỏ."""
    roles = _guard_bb()
    doc = _lay(name)
    if doc.trang_thai != BB.CHO_KY:
        frappe.throw(_("Biên bản {0} không ở trạng thái chờ ký.").format(doc.name))
    s, loi = BB.o_ky_cua(_ky_ds(doc), frappe.session.user, roles, doc.nguoi_lap)
    if s is None:
        frappe.throw(loi, frappe.PermissionError)
    if not (y_kien or "").strip():
        frappe.throw(_("Trả lại: ghi ý kiến."))
    luc = now_datetime()
    dong = f"[{getdate(luc).strftime('%d/%m/%Y')} {str(luc)[11:16]} · {_ten(frappe.session.user)} — " \
           f"{s.vai_tro}] {y_kien.strip()}"
    doc.y_kien_tra_lai = f"{doc.y_kien_tra_lai}\n{dong}" if doc.y_kien_tra_lai else dong
    doc.trang_thai = BB.TRA_LAI
    doc.ban_ky_tay = None
    for r in _ky_ds(doc):
        r.ky_luc = None
        r.ten = r.chuc_danh = r.y_kien = None
        if not cint(r.get("gan")):
            r.user = None
    _luu(doc)
    return _ra(doc, roles)


@frappe.whitelist()
def tai_ky_tay(name, ten, noi_dung):
    """Tải bản scan đã ký tay (PDF / ảnh ≤ 10 MB) khi Chờ ký — người lập / Trưởng Ban ISO; đủ chữ ký trên app thì
    khóa."""
    roles = _guard_bb()
    doc = _lay(name)
    q = _quyen(doc, roles)
    if not q.get("ky_tay"):
        frappe.throw(_("Biên bản {0} không cần / chưa nhận bản ký tay lúc này.").format(doc.name),
                     frappe.PermissionError)
    doc.ban_ky_tay = _luu_tep(BB.PT_BB, doc.name, ten, _tep_b64(ten, noi_dung, DUOI_TEP))
    dn = BB.dinh_nghia_bb(doc)
    nd = _nd(doc)
    if BB.du_chu_ky(_ky_ds(doc), doc.ban_ky_tay, BB.gia_tri_dau(nd), dn.get("ky_tay_khi")):
        _khoa(doc, dn, nd)
    _luu(doc)
    return _ra(doc, roles)


# ── Tệp kèm, BM.01.07, xóa ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def them_tep(name, ten, noi_dung, mo_ta=""):
    """Thêm tệp kèm (ảnh hiện trường, bằng chứng — PDF / ảnh ≤ 10 MB) khi biên bản chưa ký đủ."""
    roles = _guard_bb()
    doc = _lay(name)
    q = _quyen(doc, roles)
    if doc.trang_thai == BB.DA_KY or not (q.get("sua") or (doc.trang_thai == BB.CHO_KY and (
            doc.nguoi_lap == frappe.session.user or _sieu(roles) or BB.ISO in roles))):
        frappe.throw(_("Chỉ người lập / Trưởng Ban ISO thêm tệp khi biên bản chưa ký đủ."), frappe.PermissionError)
    url = _luu_tep(BB.PT_BB, doc.name, ten, _tep_b64(ten, noi_dung, DUOI_TEP))
    doc.append("tep_kem", {"mo_ta": (mo_ta or "").strip() or ten, "tep": url, "luc": now_datetime(),
                           "nguoi": frappe.session.user})
    _luu(doc)
    return _ra(doc, roles)


@frappe.whitelist()
def tai_tep(name, i=None, ky_tay=0):
    """Tải tệp kèm / bản ký tay (GET, mở thẳng trong trình duyệt) — người xem được biên bản."""
    roles = _guard_bb()
    doc = _lay(name)
    _can(doc, roles, "xem")
    if cint(ky_tay):
        url = doc.ban_ky_tay
    else:
        ds_ = doc.get("tep_kem") or []
        url = ds_[cint(i)].tep if i not in (None, "") and 0 <= cint(i) < len(ds_) else None
    if not url:
        frappe.throw(_("Không có tệp."))
    nd, ten = _doc_tep(url)
    frappe.local.response.filename = ten
    frappe.local.response.filecontent = nd
    frappe.local.response.type = "download"
    frappe.local.response.display_content_as = "inline"


@frappe.whitelist()
def lap_car(name, phan, dong):
    """Dòng Không phù hợp của Danh sách kiểm → lập BM.01.07 (nguồn theo mẫu: Đánh giá nội bộ, Thẩm tra…), gắn ngược vào
    phiếu liên quan. Dòng đã có phiếu → trả phiếu đó."""
    roles = _guard_bb()
    doc = _lay(name)
    _can(doc, roles, "car")
    khoa = f"{phan}:{dong}"
    co = next((r.ten for r in doc.get("lien_quan") or [] if r.loai == KP.PT and r.ghi_chu == khoa), None)
    if co:
        return {"name": co, "da_co": 1}
    dn = BB.dinh_nghia_bb(doc)
    p = next((x for x in dn["phan"] if x.get("key") == phan and x.get("kieu") == BB.DS_KIEM), None)
    nd = _nd(doc)
    r = next((x for x in ((nd.get(phan) or {}).get("dong") or []) if x.get("_id") == dong), None) if p else None
    kl = BB.cot_ket_luan(p) if p else None
    if not r or not kl or not BB.la_khong_phu_hop(r.get(kl["key"])):
        frappe.throw(_("Dòng này không phải điểm không phù hợp."))
    nguon = dn.get("nguon_car") if dn.get("nguon_car") in KP.NGUON else "Khác"
    car = frappe.get_doc({"doctype": KP.PT, "ngay": nowdate(), "trang_thai": KP.MO, "nguon": nguon,
                          "mo_ta": BB.mo_ta_kph(doc.mau, doc.so, p, r, doc.ngay), "lap_boi": frappe.session.user})
    car.insert(ignore_permissions=True)
    doc.append("lien_quan", {"loai": KP.PT, "ten": car.name, "ghi_chu": khoa})
    _luu(doc)
    return {"name": car.name, "da_co": 0}


@frappe.whitelist()
def xoa(name):
    """Xóa biên bản Nháp / Trả lại chưa ai ký — người lập, Trưởng Ban ISO."""
    roles = _guard_bb()
    doc = _lay(name)
    _can(doc, roles, "xoa")
    if frappe.get_all(BB.PT_BB, filters={"goc": doc.name}, pluck="name", limit=1):
        frappe.throw(_("Đã có biên bản lập từ biên bản này — không xóa được."))
    frappe.flags.sx_bb = True
    try:
        frappe.delete_doc(BB.PT_BB, doc.name, ignore_permissions=True)
    finally:
        frappe.flags.sx_bb = False
    return {"ok": 1}


# ── In ───────────────────────────────────────────────────────────────────────────────────────

def _in_dict(doc):
    """Dữ liệu bản in: các phần theo thứ tự (chỉ phần áp dụng, dòng áp dụng), ô ký "Ký trên phần mềm: Họ tên, giờ"
    hoặc ô trống ký tay."""
    dn = BB.dinh_nghia_bb(doc)
    nd = _nd(doc)
    dau = BB.gia_tri_dau(nd)
    phan = []
    for p in dn["phan"]:
        if not BB.phan_ap_dung(p, dau):
            continue
        v = nd.get(p["key"]) or {}
        cot = BB.cot_cua(p)
        x = {"key": p["key"], "tieu_de": p.get("tieu_de") or "", "kieu": p.get("kieu"), "cot": cot,
             "keo": v.get("keo") or None, "ten_nguon": (BB.NGUON.get((v.get("keo") or {}).get("nguon") or "")
                                                         or ("",))[0]}
        if p.get("kieu") == BB.VAN_BAN:
            g = v.get("gia_tri") or {}
            x["o"] = [{"nhan": c.get("nhan"), "gt": SO.hien(c, g.get(c["key"]), {}) if c.get("kieu") != "User"
                       else _ten(g.get(c["key"])), "check": c.get("kieu") == "Check", "co": bool(cint(g.get(c["key"])))
                       if c.get("kieu") == "Check" else None} for c in cot]
            x["chu"] = v.get("chu") or ""
        elif p.get("kieu") in BB.CO_DONG:
            dong = []
            for r in v.get("dong") or []:
                if p.get("kieu") == BB.DS_KIEM and not cint(r.get("_tieu_de")) and not BB.dong_ap_dung(p, r, dau):
                    continue
                dong.append({"tieu_de": bool(cint(r.get("_tieu_de"))), "muc": BB.muc_kxa(r.get("diem"))
                             if p.get("tinh") == BB.K_X_A else "",
                             "o": [(_ten(r.get(c["key"])) if c.get("kieu") == "User" else
                                    SO.hien(c, r.get(c["key"]), {})) for c in cot]})
            x["dong"] = dong
        phan.append(x)
    ky = []
    for s in BB.ky_sap(_ky_ds(doc)):
        if cint(s.ky_tay):
            ky.append({"vai_tro": s.vai_tro, "chu": "Ký tay — bản scan đính kèm" if doc.ban_ky_tay else "", "tay": 1})
        else:
            ky.append({"vai_tro": s.vai_tro, "chu": _ky_in(s.ten or _ten(s.user), s.ky_luc) if s.ky_luc else "",
                       "chuc_danh": s.chuc_danh or "", "y_kien": s.y_kien or "", "tay": 0})
    return {"name": doc.name, "ma": doc.mau, "ten": doc.ten_mau or dn.get("ten") or "", "so": doc.so or "",
            "ngay": str(doc.ngay or ""), "nhan_ngay": dn.get("nhan_ngay") or "Ngày", "tieu_de": doc.tieu_de or "",
            "trang_thai": doc.trang_thai, "lan": dn.get("lan_ban_hanh") or "", "phan": phan, "ky": ky,
            "ky_tay_them": bool(BB.can_ky_tay(_ky_ds(doc), dau, dn.get("ky_tay_khi"))
                                and not any(cint(s.ky_tay) for s in _ky_ds(doc))),
            "co_ky_tay": bool(doc.ban_ky_tay), "nguoi_lap": _ten(doc.nguoi_lap),
            "lien_quan": [{"loai": r.loai, "ten": r.ten} for r in doc.get("lien_quan") or []],
            "tep_kem": [r.mo_ta or "" for r in doc.get("tep_kem") or []],
            "y_kien_tra_lai": doc.y_kien_tra_lai or ""}


def _html(doc):
    return frappe.render_template("sx/qc/bien_ban.html", {"d": _in_dict(doc)})


@frappe.whitelist()
def in_bb(name):
    roles = _guard_bb()
    doc = _lay(name)
    _can(doc, roles, "xem")
    return _html(doc)


def in_ho_so(ma, tu, den):
    """[(tên tệp, html)] — mỗi biên bản ký đủ của mẫu `ma` trong kỳ một tệp (gói hồ sơ, sx/api/qc_hoso.py)."""
    import re
    ra = []
    for n in frappe.get_all(BB.PT_BB, filters={"mau": ma, "trang_thai": BB.DA_KY, "ngay": ("between", [tu, den])},
                            pluck="name", order_by="ngay asc, creation asc"):
        doc = frappe.get_doc(BB.PT_BB, n)
        ten = re.sub(r"[^A-Za-z0-9.-]+", "-", f"{doc.ngay}-{doc.so or n}").strip("-")
        ra.append((f"{ten}.html", _html(doc)))
    return ra
