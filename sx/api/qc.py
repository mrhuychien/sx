"""API module QC (BM.08.01 / BM.08.02) — mọi method whitelist đều có chốt quyền.

RANH GIỚI MODULE (spec §Bước 0): file này KHÔNG import gì từ phần còn lại của
app `sx` — không sx.utils, không sx.config.roles, không sx.api.*. Quyền tự chốt
bằng _guard_* ngay dưới đây. Mục đích: tách module qc thành app riêng sau này chỉ
là chuyển thư mục, không phải gỡ từng sợi dây.

Vì vậy tên role bị khai HAI chỗ (đây và sx/config/roles.py). scripts/test-qc.py
chốt hai bên khớp nhau — khai hai lần mà không ai canh thì sớm muộn lệch.

Ba vai, ba quyền khác nhau, và chỗ khác nhau là chỗ có giá trị:
  QC chế biến / QC đóng gói  ghi lượt, ghi xử lý sự cố — KHÔNG đóng được sự cố
  Production Manager          đọc lượt, ghi xử lý sự cố
  ISO Manager                 đóng sự cố, đánh dấu đã xem xét, xem dashboard
Người ghi không tự duyệt: cả giá trị của bước kiểm nằm ở chỗ đó.
"""

import json

import frappe
from frappe import _
from frappe.utils import (
    add_days,
    cint,
    flt,
    get_datetime,
    getdate,
    now_datetime,
    nowdate,
)

from sx.qc import muc as M
from sx.qc import nhac as _nhac
from sx.qc import xuat
from sx.qc.nguong import nguong
from sx.qc.su_co import canh_bao, phat_hien

QC = "SX QC"
QC_GOI = "SX QC Packing"
ISO = "ISO Manager"
QLSX = "Production Manager"
SIEU = {"SX Quan Ly", "System Manager", "Administrator"}

VAO_DUOC = {QC, QC_GOI, ISO, QLSX}
GHI_DUOC = {QC, QC_GOI}

SO_NGAY_MAC_DINH = 30      # cửa sổ mặc định cho list / dashboard


def _roles():
    return set(frappe.get_roles())


def _sieu(roles=None):
    return bool((roles or _roles()) & SIEU)


def _guard_qc():
    """Vào được module QC (đọc)."""
    roles = _roles()
    if _sieu(roles) or roles & VAO_DUOC:
        return
    frappe.throw(_("Bạn không có quyền vào phần QC."), frappe.PermissionError)


def _guard_ghi():
    """Ghi vòng kiểm. QLSX và Ban ISO CHỈ ĐỌC — người xem xét không tự ghi."""
    roles = _roles()
    if _sieu(roles) or roles & GHI_DUOC:
        return
    frappe.throw(
        _("Chỉ QC chế biến / QC đóng gói mới ghi được vòng kiểm."),
        frappe.PermissionError)


def _guard_manager():
    """Đóng sự cố, đánh dấu đã xem xét, xem dashboard."""
    roles = _roles()
    if _sieu(roles) or ISO in roles:
        return
    frappe.throw(
        _("Chỉ Trưởng Ban ISO mới làm được việc này — người ghi không tự duyệt."),
        frappe.PermissionError)


def _cua_minh(doc):
    """Lượt này có phải của mình không (hoặc mình là người xem xét)."""
    u = frappe.session.user
    return (_sieu() or ISO in _roles()
            or u in (doc.qc_user, doc.qc_goi_user))


def _lay_round(name, de_ghi=False):
    doc = frappe.get_doc("SX QC Round", name)
    if de_ghi:
        _guard_ghi()
        if not _cua_minh(doc):
            frappe.throw(
                _("Lượt này của {0} — bạn không sửa được. Mỗi lượt một người ghi, "
                  "đó là cách biết ai đã đứng ở đó.").format(doc.qc_user),
                frappe.PermissionError)
        if doc.docstatus != 0:
            frappe.throw(_("Lượt đã hoàn tất — không sửa được nữa."))
    return doc


def _khoang(tu=None, den=None):
    den = getdate(den) if den else getdate(nowdate())
    tu = getdate(tu) if tu else add_days(den, -SO_NGAY_MAC_DINH + 1)
    return tu, den


# ───────────────────────────────────────────────────────────── hôm nay ──


@frappe.whitelist()
def get_today(ngay=None):
    """Trạng thái các lượt của một ngày + gợi ý lượt kế tiếp + ma trận áp dụng."""
    _guard_qc()
    d = getdate(ngay) if ngay else getdate(nowdate())
    la_thu_hai = d.weekday() == 0

    rounds = frappe.get_all(
        "SX QC Round",
        filters={"ngay": d, "docstatus": ("<", 2)},
        fields=["name", "ca", "luot", "docstatus", "started_at", "finished_at",
                "ghi_muon", "nhap_lai_tu_giay", "co_san_xuat_bot",
                "so_muc_ap_dung", "so_muc_da_cham", "qc_user", "reviewed_on"],
        order_by="creation",
    )

    # "Hôm nay có bột" mặc định theo chính ngày đó: lượt trước đã bật thì lượt sau
    # bật sẵn — QC không phải nhớ bật lại ở từng lượt.
    co_bot = 1 if any(cint(r["co_san_xuat_bot"]) for r in rounds) else 0

    theo_ca = {}
    for ca in M.CA:
        cua_ca = {r["luot"]: r for r in rounds if r["ca"] == ca}
        ds = []
        for luot in (M.DAU_CA, M.GIUA_CA, M.CUOI_CA):
            # Thứ Hai: ô "Đầu ca" chính là lượt Tuần, không phải thêm một lượt nữa.
            thuc = M.TUAN if (luot == M.DAU_CA and la_thu_hai) else luot
            r = cua_ca.get(thuc) or cua_ca.get(luot)
            ds.append({
                "o": luot,
                "luot": (r or {}).get("luot") or thuc,
                "round": r,
                "so_muc": len(M.muc_cham((r or {}).get("luot") or thuc, co_bot)),
            })
        theo_ca[ca] = ds

    mo = frappe.get_all("SX Su Co", filters={"trang_thai": "Mở"},
                        fields=["name", "ngay"])
    han = cint(nguong()["su_co_qua_han_ngay"])
    return {
        "ngay": str(d),
        "hom_nay": nowdate(),
        "la_thu_hai": la_thu_hai,
        "co_san_xuat_bot": co_bot,
        "ca": list(M.CA),
        "theo_ca": theo_ca,
        "su_co_mo": len(mo),
        "su_co_qua_han": sum(
            1 for s in mo if getdate(nowdate()) > add_days(getdate(s["ngay"]), han)),
        "ma_tran": M.ma_tran(co_bot),
        "muc": M.MUC,
        "buoc": [{"ma": a, "ten": b, "oprp": c, "ghi": e} for a, b, c, e in M.BUOC],
        "nguong": {k: v for k, v in nguong().items() if k != "khung"},
        # Khung giờ hiện ngay trên thẻ lượt: QC biết mình còn bao lâu trước khi
        # lượt bị gắn cờ ghi muộn, thay vì biết sau khi đã bị gắn.
        "khung": {ca: {l: [str(x or "") for x in v]
                       for l, v in cua.items()}
                  for ca, cua in nguong()["khung"].items()},
        "user": frappe.session.user,
        "la_qc_goi": QC_GOI in _roles() and QC not in _roles(),
        "duoc_ghi": bool(_sieu() or _roles() & GHI_DUOC),
        "duoc_duyet": bool(_sieu() or ISO in _roles()),
    }


@frappe.whitelist()
def start_round(ngay, ca, luot, co_san_xuat_bot=0, nhap_lai_tu_giay=0):
    """Mở lượt. Đã có bản nháp thì trả lại chính nó, không đẻ bản thứ hai."""
    _guard_ghi()
    d = getdate(ngay)
    cung = list(M.DAU_CA_HOAC_TUAN) if luot in M.DAU_CA_HOAC_TUAN else [luot]
    co = frappe.get_all("SX QC Round",
                        filters={"ngay": d, "ca": ca, "luot": ("in", cung),
                                 "docstatus": ("<", 2)},
                        fields=["name", "docstatus"], limit=1)
    if co:
        if co[0]["docstatus"] == 1:
            frappe.throw(_("Lượt {0} ca {1} ngày {2} đã hoàn tất rồi.").format(
                luot, ca, d))
        return chi_tiet_round(co[0]["name"])

    doc = frappe.get_doc({
        "doctype": "SX QC Round",
        "ngay": d, "ca": ca, "luot": luot,
        "co_san_xuat_bot": cint(co_san_xuat_bot),
        "nhap_lai_tu_giay": cint(nhap_lai_tu_giay),
        "qc_user": frappe.session.user,
    })
    doc.insert()
    return chi_tiet_round(doc.name)


def _truoc_do(doc):
    """Giá trị nhiệt độ / vòng quay của lượt LIỀN TRƯỚC, để QC đối chiếu.

    Không phải để chép lại — để thấy "lượt trước 262, giờ 248" ngay lúc đứng ở
    máy rang, chứ không phải lúc đọc báo cáo cuối tháng.
    """
    ds = frappe.get_all(
        "SX QC Round",
        filters={"docstatus": 1, "ngay": ("<=", doc.ngay), "name": ("!=", doc.name)},
        fields=["name", "ngay", "ca", "luot", "rang_nhiet_do", "rang_vong_quay",
                "finished_at"],
        order_by="ngay desc, finished_at desc", limit=1)
    return ds[0] if ds else None


@frappe.whitelist()
def chi_tiet_round(name):
    """Toàn bộ một lượt: giá trị, mục áp dụng, sự cố, quyền của người đang xem."""
    _guard_qc()
    doc = frappe.get_doc("SX QC Round", name)
    co_bot = cint(doc.co_san_xuat_bot)
    ap = [m["f"] for m in M.muc_ap_dung(doc.luot, co_bot)]
    return {
        "name": doc.name,
        "ngay": str(doc.ngay), "ca": doc.ca, "luot": doc.luot,
        "co_san_xuat_bot": co_bot,
        "nhap_lai_tu_giay": cint(doc.nhap_lai_tu_giay),
        "docstatus": doc.docstatus,
        "started_at": str(doc.started_at or ""),
        "finished_at": str(doc.finished_at or ""),
        "duration_min": cint(doc.duration_min),
        "ghi_muon": cint(doc.ghi_muon),
        "reviewed_by": doc.reviewed_by, "reviewed_on": str(doc.reviewed_on or ""),
        "ghi_chu": doc.ghi_chu or "",
        "qc_user": doc.qc_user, "qc_goi_user": doc.qc_goi_user,
        "ap_dung": ap,
        "gia_tri": {f: doc.get(f) for f in ap},
        "da_cham": cint(doc.so_muc_da_cham),
        "phai_cham": cint(doc.so_muc_ap_dung),
        "su_co": [{"name": r.incident, "muc": r.muc, "mo_ta": r.mo_ta}
                  for r in doc.su_co],
        # Xem trước: lệch nào SẼ thành sự cố nếu hoàn tất ngay bây giờ. QC thấy
        # trước thì còn kịp đi xem lại máy, thay vì hoàn tất xong mới biết.
        "se_thanh_su_co": [{"muc": k, "mo_ta": mt, "muc_do": md}
                           for k, _cd, _l, md, mt in phat_hien(doc)],
        "canh_bao": canh_bao(doc),
        "truoc_do": _truoc_do(doc),
        "duoc_ghi": doc.docstatus == 0 and bool(_sieu() or _roles() & GHI_DUOC)
                    and _cua_minh(doc),
        # Ghi được KHÁC chốt được: QC đóng gói ghi mục của mình trên bản nháp của
        # người khác, nhưng người chốt lượt phải là người đã đi hết lượt đó.
        "duoc_chot": doc.docstatus == 0 and bool(_sieu() or QC in _roles()),
    }


# ────────────────────────────────────────────────────────────── ghi lượt ──


def _ts_cuoi(doc, fieldname):
    """client_ts mới nhất đã ghi cho một mục (None nếu chưa ghi lần nào)."""
    ts = [r.client_ts for r in doc.log if r.fieldname == fieldname and r.client_ts]
    return max(get_datetime(t) for t in ts) if ts else None


@frappe.whitelist()
def save_round(name, values, client_ts=None):
    """Lưu từng mục vừa gõ. Gửi lại nhiều lần vẫn ra một kết quả.

    XUNG ĐỘT: QC chế biến và QC đóng gói ghi CÙNG một bản ghi, hai điện thoại,
    có khi một máy đang ngoại tuyến. Nên client chỉ gửi những mục NÓ vừa đổi, kèm
    giờ trên máy nó; server bỏ qua giá trị nào có giờ CŨ HƠN giá trị đang lưu của
    chính mục đó. Gửi cả cục rồi ghi đè là cách QC gói xoá mất số QC chế biến vừa
    ghi, mà không ai thấy gì cả.
    """
    doc = _lay_round(name, de_ghi=True)
    if isinstance(values, str):
        values = json.loads(values)
    if not isinstance(values, dict):
        frappe.throw(_("Dữ liệu gửi lên không đúng định dạng."))

    ts = get_datetime(client_ts) if client_ts else now_datetime()
    ap = {m["f"] for m in M.muc_ap_dung(doc.luot, cint(doc.co_san_xuat_bot))}
    da_ghi, bo_qua = [], []
    for f, v in values.items():
        if f in ("ghi_chu", "co_san_xuat_bot"):
            # Hai ô này không phải mục kiểm nên không nằm trong ma trận, nhưng
            # vẫn phải ghi được: bật "hôm nay có bột" giữa lượt là chuyện thật.
            pass
        elif f not in ap:
            # Mục không thuộc lượt này: bỏ, đừng ghi lén vào ô không ai xem.
            bo_qua.append(f)
            continue
        cu = _ts_cuoi(doc, f)
        if cu and cu > ts:
            bo_qua.append(f)
            continue
        doc.set(f, v)
        doc.append("log", {"fieldname": f, "gia_tri": ("" if v is None else str(v)),
                           "client_ts": ts, "server_ts": now_datetime(),
                           "boi": frappe.session.user})
        da_ghi.append(f)

    # QC đóng gói mở lượt của người khác ra ghi mục 11–13 → ghi tên vào phiếu.
    if (QC_GOI in _roles() and frappe.session.user != doc.qc_user
            and not doc.qc_goi_user):
        doc.qc_goi_user = frappe.session.user
    doc.save()
    return {"name": doc.name, "da_ghi": da_ghi, "bo_qua": bo_qua,
            "da_cham": cint(doc.so_muc_da_cham),
            "phai_cham": cint(doc.so_muc_ap_dung),
            "luc": str(now_datetime())}


@frappe.whitelist()
def submit_round(name):
    """Hoàn tất lượt: validate → submit → sinh sự cố.

    Chặn QC đóng gói NGAY TỪ ĐÂY thay vì để Frappe văng "Insufficient Permission
    for SX QC Round": người đứng giữa xưởng đọc câu đó xong không biết phải làm
    gì, còn câu dưới thì nói thẳng ra là đi gọi ai.
    """
    doc = _lay_round(name, de_ghi=True)
    if not (_sieu() or QC in _roles()):
        frappe.throw(
            _("Bạn ghi được các mục đóng gói, nhưng chốt lượt là việc của QC chế "
              "biến — người đã đi hết lượt này ({0}). Báo họ bấm Hoàn tất.")
            .format(doc.qc_user), frappe.PermissionError)
    doc.submit()
    doc.reload()
    return {
        "name": doc.name,
        "ghi_muon": cint(doc.ghi_muon),
        "duration_min": cint(doc.duration_min),
        "su_co": [{"name": r.incident, "muc": r.muc, "mo_ta": r.mo_ta}
                  for r in doc.su_co],
    }


@frappe.whitelist()
def nhac(ngay=None):
    """Việc QC đang treo — để HIỆN trên dashboard, không gửi đi đâu.

    Ai mở cũng gọi được (QC, QLSX, Ban ISO, quản lý): danh sách này không chứa
    gì bí mật, và giấu nó khỏi chính người phải làm thì nó vô nghĩa.
    """
    _guard_qc()
    d = getdate(ngay) if ngay else getdate(nowdate())
    tu = add_days(d, -max(_nhac.SO_NGAY_SOI, _nhac.NGAY_CHUA_XEM_XET) - 7)
    luot = frappe.get_all(
        "SX QC Round",
        filters={"ngay": ("between", [tu, d]), "docstatus": ("<", 2)},
        fields=["name", "ngay", "ca", "luot", "docstatus", "reviewed_on",
                "t2_so_bay_dau_hieu", "b2_rang_lac_nhiet"])
    # Sự cố KHÔNG giới hạn cửa sổ ngày: cái quá hạn ba tháng mới đúng là cái
    # phải hiện lên, mà nó thì nằm ngoài mọi cửa sổ hợp lý.
    su_co = frappe.get_all("SX Su Co", filters={"trang_thai": "Mở"},
                           fields=["name", "ngay", "trang_thai", "xu_ly_ngay",
                                   "muc_do"])
    return {"ngay": str(d), "ds": _nhac.tinh(d, luot, su_co, nguong())}


@frappe.whitelist()
def list_rounds(tu=None, den=None, ca=None):
    _guard_qc()
    tu, den = _khoang(tu, den)
    dk = {"ngay": ("between", [tu, den]), "docstatus": ("<", 2)}
    if ca:
        dk["ca"] = ca
    return frappe.get_all(
        "SX QC Round", filters=dk,
        fields=["name", "ngay", "ca", "luot", "docstatus", "ghi_muon",
                "nhap_lai_tu_giay", "finished_at", "duration_min", "qc_user",
                "reviewed_on", "so_muc_ap_dung", "so_muc_da_cham"],
        order_by="ngay desc, ca, creation")


# ───────────────────────────────────────────────────────────────── sự cố ──


def _dong_su_co(ds):
    han = cint(nguong()["su_co_qua_han_ngay"])
    hom_nay = getdate(nowdate())
    for s in ds:
        # Tính lại lúc ĐỌC: "quá hạn" là hàm của hôm nay, không phải của lúc lưu.
        s["qua_han"] = (1 if s["trang_thai"] == "Mở"
                        and hom_nay > add_days(getdate(s["ngay"]), han) else 0)
        s["ngay"] = str(s["ngay"])
    return ds


@frappe.whitelist()
def list_incidents(trang_thai=None, tu=None, den=None, loai=None, cong_doan=None):
    _guard_qc()
    tu, den = _khoang(tu, den)
    dk = {"ngay": ("between", [tu, den])}
    if trang_thai:
        dk["trang_thai"] = trang_thai
    if loai:
        dk["loai"] = loai
    if cong_doan:
        dk["cong_doan"] = cong_doan
    ds = frappe.get_all(
        "SX Su Co", filters=dk,
        fields=["name", "ngay", "ca", "nguon", "qc_round", "muc", "cong_doan",
                "loai", "muc_do", "mo_ta", "trang_thai", "xu_ly_ngay",
                "quyet_dinh_sp", "nguoi_xu_ly", "dong_boi", "dong_ngay",
                "lo_anh_huong", "so_luong", "nguyen_nhan", "hanh_dong_khac_phuc",
                "car_so"],
        order_by="ngay desc, creation desc")
    return {"danh_sach": _dong_su_co(ds),
            "duoc_dong": bool(_sieu() or ISO in _roles()),
            "cong_doan": M.CONG_DOAN, "loai": list(M.LOAI_SU_CO),
            "quyet_dinh_sp": list(M.QUYET_DINH_SP)}


@frappe.whitelist()
def add_incident(payload):
    """Sự cố phát hiện ngoài vòng kiểm (nguồn 'Phát hiện khác')."""
    _guard_qc()
    if isinstance(payload, str):
        payload = json.loads(payload)
    cho_phep = {"ngay", "ca", "cong_doan", "loai", "muc_do", "mo_ta",
                "lo_anh_huong", "so_luong", "xu_ly_ngay", "nguyen_nhan"}
    doc = frappe.get_doc(dict(
        {k: v for k, v in payload.items() if k in cho_phep},
        doctype="SX Su Co",
        nguon=payload.get("nguon") or "Phát hiện khác",
        trang_thai="Mở",
        ngay=payload.get("ngay") or nowdate(),
    ))
    doc.insert()
    return doc.name


@frappe.whitelist()
def update_incident(name, payload):
    """Ghi xử lý / nguyên nhân / hành động. KHÔNG đổi được trạng thái ở đây."""
    _guard_qc()
    if isinstance(payload, str):
        payload = json.loads(payload)
    doc = frappe.get_doc("SX Su Co", name)
    if doc.trang_thai == "Đóng" and not (_sieu() or ISO in _roles()):
        frappe.throw(_("Phiếu đã đóng — nhờ Ban ISO mở lại nếu cần sửa."),
                     frappe.PermissionError)
    # trang_thai KHÔNG nằm trong danh sách này: đóng phiếu đi cửa close_incident,
    # nơi có _guard_manager. Cho nó vào đây là mở cửa hậu cho chính người ghi.
    cho_phep = {"xu_ly_ngay", "nguyen_nhan", "hanh_dong_khac_phuc",
                "lo_anh_huong", "so_luong", "cong_doan", "loai", "muc_do",
                "quyet_dinh_sp", "car_so"}
    for k, v in payload.items():
        if k in cho_phep:
            doc.set(k, v)
    if not doc.nguoi_xu_ly:
        doc.nguoi_xu_ly = frappe.session.user
    doc.save()
    return {"name": doc.name}


@frappe.whitelist()
def close_incident(name, quyet_dinh_sp=None, car_so=None):
    """Đóng phiếu sự cố — chỉ Ban ISO, và chỉ khi đã ghi đủ xử lý."""
    _guard_manager()
    doc = frappe.get_doc("SX Su Co", name)
    if quyet_dinh_sp:
        doc.quyet_dinh_sp = quyet_dinh_sp
    if car_so:
        doc.car_so = car_so
    doc.trang_thai = "Đóng"
    doc.save()          # controller chặn nếu thiếu xử lý ngay / quyết định SP
    return {"name": doc.name, "dong_ngay": str(doc.dong_ngay or "")}


@frappe.whitelist()
def reopen_incident(name, ly_do=None):
    """Mở lại phiếu đã đóng — chỉ Ban ISO, và ghi lý do vào hành động khắc phục."""
    _guard_manager()
    doc = frappe.get_doc("SX Su Co", name)
    doc.trang_thai = "Mở"
    if ly_do:
        doc.hanh_dong_khac_phuc = ((doc.hanh_dong_khac_phuc or "")
                                   + f"\n[Mở lại] {ly_do}").strip()
    doc.save()
    return {"name": doc.name}


# ─────────────────────────────────────────────────── xem xét & dashboard ──


@frappe.whitelist()
def review_rounds(tu=None, den=None):
    """Ban ISO đánh dấu đã xem xét. Sau đó lượt KHOÁ, không huỷ được nữa."""
    _guard_manager()
    tu, den = _khoang(tu, den)
    ds = frappe.get_all("SX QC Round",
                        filters={"ngay": ("between", [tu, den]), "docstatus": 1,
                                 "reviewed_on": ("is", "not set")},
                        pluck="name")
    luc = now_datetime()
    for n in ds:
        doc = frappe.get_doc("SX QC Round", n)
        # db_set: reviewed_* là field read-only trên bản ĐÃ SUBMIT, save() sẽ bị
        # chặn. Đây là ghi chữ ký xem xét, không đụng số liệu của lượt.
        doc.db_set({"reviewed_by": frappe.session.user, "reviewed_on": luc},
                   update_modified=False)
    return {"so_luot": len(ds), "den": str(den)}


@frappe.whitelist()
def dashboard(tu=None, den=None):
    """KPI cho Ban ISO. Câu hỏi phải trả lời được: hồ sơ có THẬT không."""
    _guard_manager()
    tu, den = _khoang(tu, den)
    rounds = frappe.get_all(
        "SX QC Round",
        filters={"ngay": ("between", [tu, den]), "docstatus": 1},
        fields=["name", "ngay", "ca", "luot", "ghi_muon", "nhap_lai_tu_giay",
                "duration_min", "rang_nhiet_do", "rang_vong_quay",
                "thung_bot_qua_han", "t2_so_bay_dau_hieu", "reviewed_on",
                "finished_at"],
        order_by="ngay, finished_at")
    su_co = frappe.get_all(
        "SX Su Co", filters={"ngay": ("between", [tu, den])},
        fields=["name", "ngay", "cong_doan", "loai", "muc_do", "trang_thai"])

    so_ngay = (getdate(den) - getdate(tu)).days + 1
    can_co = so_ngay * len(M.CA) * 3        # 3 lượt × 2 ca mỗi ngày
    ghi_muon = sum(1 for r in rounds if cint(r["ghi_muon"]))
    han = cint(nguong()["su_co_qua_han_ngay"])
    hom_nay = getdate(nowdate())
    return {
        "tu": str(tu), "den": str(den),
        "so_luot": len(rounds),
        "can_co": can_co,
        "ty_le_hoan_tat": round(len(rounds) * 100.0 / can_co, 1) if can_co else 0,
        "ty_le_dung_gio": (round((len(rounds) - ghi_muon) * 100.0 / len(rounds), 1)
                           if rounds else 0),
        "ghi_muon": ghi_muon,
        "nhap_lai_tu_giay": sum(1 for r in rounds if cint(r["nhap_lai_tu_giay"])),
        "chua_xem_xet": sum(1 for r in rounds if not r["reviewed_on"]),
        "su_co_mo": sum(1 for s in su_co if s["trang_thai"] == "Mở"),
        "su_co_qua_han": sum(
            1 for s in su_co if s["trang_thai"] == "Mở"
            and hom_nay > add_days(getdate(s["ngay"]), han)),
        "theo_cong_doan": _dem(su_co, "cong_doan"),
        "theo_loai": _dem(su_co, "loai"),
        "chuoi_rang": [{"ngay": str(r["ngay"]), "ca": r["ca"], "luot": r["luot"],
                        "nhiet": cint(r["rang_nhiet_do"]),
                        "vong": flt(r["rang_vong_quay"], 1)}
                       for r in rounds if cint(r["rang_nhiet_do"])],
        "thung_qua_han": sum(cint(r["thung_bot_qua_han"]) for r in rounds),
        "bay_co_dau_hieu": sum(cint(r["t2_so_bay_dau_hieu"]) for r in rounds),
    }


def _dem(ds, khoa):
    ra = {}
    for x in ds:
        k = x.get(khoa) or "—"
        ra[k] = ra.get(k, 0) + 1
    return sorted(({"ten": k, "so": v} for k, v in ra.items()),
                  key=lambda x: -x["so"])


# ──────────────────────────────────────────────────────────── tờ in ngày ──


@frappe.whitelist()
def day_sheet(ngay, ca=None):
    """HTML tờ ngày BM.08.01 để in / xuất PDF đưa auditor.

    Ba cột lượt trên một trang, đúng bố cục bản giấy — auditor cầm tờ này so với
    tập hồ sơ cũ mà không phải học đọc format mới.
    """
    _guard_qc()
    return _to_ngay(ngay, ca)


@frappe.whitelist()
def month_sheets(tu, den, ca=None):
    """Gộp tờ ngày của cả khoảng thành MỘT tài liệu, mỗi ngày một trang.

    Ban ISO in cả tháng một lần để kẹp vào hồ sơ, không ai ngồi bấm in 30 lần.
    Ngày không có lượt nào thì BỎ QUA chứ không in tờ trống: tập hồ sơ dày thêm
    30 tờ giấy trắng chỉ làm người đọc khó tìm tờ có nội dung.
    """
    _guard_qc()
    tu, den = _khoang(tu, den)
    co = sorted({str(x) for x in frappe.get_all(
        "SX QC Round", filters={"ngay": ("between", [tu, den]), "docstatus": 1},
        pluck="ngay")})
    if not co:
        return ""
    ra = [_to_ngay(co[0], ca, kem_style=True)]
    ra += [_to_ngay(d, ca, kem_style=False) for d in co[1:]]
    return '<div style="page-break-after:always"></div>'.join(ra)


def _to_ngay(ngay, ca=None, kem_style=True):
    d = getdate(ngay)
    dk = {"ngay": d, "docstatus": 1}
    if ca:
        dk["ca"] = ca
    ds = frappe.get_all("SX QC Round", filters=dk, pluck="name",
                        order_by="ca, creation")
    rounds = [frappe.get_doc("SX QC Round", n) for n in ds]
    co_bot = 1 if any(cint(r.co_san_xuat_bot) for r in rounds) else 0

    cot = [{"doc": r, "ap": {m["f"] for m in M.muc_ap_dung(
        r.luot, cint(r.co_san_xuat_bot))}} for r in rounds]
    hang = []
    for ma, ten, oprp, _ghi in M.BUOC:
        muc_buoc = [m for m in M.MUC if m["buoc"] == ma
                    and (not m["bot"] or co_bot)]
        if not muc_buoc:
            continue
        hang.append({"buoc": True, "ten": f"{ma}. {ten}"
                     + (f" ({oprp})" if oprp else "")})
        for m in muc_buoc:
            hang.append({
                "buoc": False, "so": m["so"], "nhan": m["nhan"],
                "o": [("" if m["f"] not in c["ap"]
                       else _in_gia_tri(m, c["doc"].get(m["f"])))
                      for c in cot],
                "khong_ap": [m["f"] not in c["ap"] for c in cot],
            })
    return frappe.render_template("sx/qc/day_sheet.html", {
        "ngay": d, "rounds": rounds, "hang": hang, "co_bot": co_bot,
        "kem_style": kem_style,
        "su_co": frappe.get_all(
            "SX Su Co", filters={"ngay": d}, order_by="creation",
            fields=["name", "muc", "mo_ta", "muc_do", "trang_thai",
                    "xu_ly_ngay", "quyet_dinh_sp"]),
    })


@frappe.whitelist()
def export_csv(tu=None, den=None, loai="luot"):
    """CSV tháng cho Ban ISO: `loai` = 'luot' (ma trận ngày × mục) hoặc 'su_co'.

    Việc dựng CSV nằm ở sx/qc/xuat.py (hàm thuần, có test riêng) — đây chỉ đi
    lấy dữ liệu. Chỗ dễ sai của một file xuất không phải truy vấn mà là ý nghĩa
    của ô trống; xem chú thích đầu file đó.
    """
    _guard_qc()
    tu, den = _khoang(tu, den)
    if loai == "su_co":
        return xuat.thanh_csv(
            xuat.COT_SU_CO,
            [xuat.dong_su_co(s)
             for s in list_incidents(tu=tu, den=den)["danh_sach"]])
    ds = frappe.get_all("SX QC Round",
                        filters={"ngay": ("between", [tu, den]), "docstatus": 1},
                        pluck="name", order_by="ngay, ca, creation")
    return xuat.thanh_csv(
        xuat.tieu_de_luot(),
        [xuat.dong_luot(frappe.get_doc("SX QC Round", n), _in_gia_tri, cint)
         for n in ds])


def _in_gia_tri(m, v):
    if m["kieu"] == "co_khong":
        return "x" if cint(v) else ""
    if v is None or v == "":
        return "—"
    if m["kieu"] == "chon":
        return "Đ" if v == M.DAT else ("K" if v == M.KHONG_DAT else "—")
    if m["kieu"] in M.KIEU_SO and not M.co_ghi(m, v):
        return "—"
    return str(v)
