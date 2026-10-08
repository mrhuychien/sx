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
from sx.qc.san_pham import co_di_ung
from sx.qc.su_co import canh_bao, phat_hien

QC = "SX QC"
QC_GOI = "SX QC Packing"
ISO = "ISO Manager"
QLSX = "Production Manager"
SIEU = {"SX Quan Ly", "System Manager", "Administrator"}

VAO_DUOC = {QC, QC_GOI, ISO, QLSX}
GHI_DUOC = {QC, QC_GOI}

SO_NGAY_MAC_DINH = 30      # cửa sổ mặc định cho list / dashboard

# Nhóm hàng của các vị BỘT — đúng danh mục tab "Bột đậu" ở card Báo mẻ (D100).
# Đọc thẳng field custom_sx_nhom trên Item bằng frappe, không import sx.utils:
# module qc vẫn bê đi được, chỉ mang theo một hằng số.
NHOM_BOT = "BTP-Bot-SP"

# Mục ghi được qua save_round dù không phải mục kiểm (không nằm trong ma trận).
TRUONG_PHU = ("ghi_chu", "co_san_xuat_bot", "buoc_nghi") \
    + tuple(t[2] for t in M.NHOM_MAY.values())


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
        fields=["name", "luot", "docstatus", "started_at", "finished_at",
                "ghi_muon", "nhap_lai_tu_giay", "co_san_xuat_bot",
                "so_muc_ap_dung", "so_muc_da_cham", "qc_user", "reviewed_on"],
        order_by="creation",
    )

    # "Hôm nay có bột" là chuyện của CẢ NGÀY (D98) — đọc từ SX QC Ngay, xem
    # muc.co_bot_ngay. Trước D98 suy từ các lượt, nên bật lúc đầu ngày (chưa có
    # lượt nào) là không lưu vào đâu cả, tải lại trang là mất.
    co_bot = M.co_bot_ngay(_co_bot_ban_ghi(d), rounds)

    # Ba ô trong ngày (D95 — không còn chia ca). Ngày cũ trước D95 có thể có hai
    # phiếu cùng tên lượt (ca Sáng + ca Chiều); ô chỉ hiện phiếu MỞ SAU CÙNG, đủ
    # để biết lượt đó đã có người đi — chi tiết từng phiếu xem ở Lịch sử.
    theo_luot = {r["luot"]: r for r in rounds}
    o_luot = []
    for luot in M.LUOT_TRONG_NGAY:
        # Thứ Hai: ô "Đầu sáng" chính là lượt Tuần, không phải thêm một lượt nữa.
        thuc = M.TUAN if (luot == M.DAU_SANG and la_thu_hai) else luot
        r = theo_luot.get(thuc) or theo_luot.get(luot)
        if luot == M.DAU_SANG and not r:
            r = theo_luot.get(M.TUAN)
        o_luot.append({
            "o": luot,
            "luot": (r or {}).get("luot") or thuc,
            "round": r,
            "so_muc": len(M.muc_cham((r or {}).get("luot") or thuc, co_bot)),
        })

    mo = frappe.get_all("SX Su Co", filters={"trang_thai": "Mở"},
                        fields=["name", "ngay"])
    han = cint(nguong()["su_co_qua_han_ngay"])
    return {
        "ngay": str(d),
        "hom_nay": nowdate(),
        "la_thu_hai": la_thu_hai,
        "co_san_xuat_bot": co_bot,
        "o_luot": o_luot,
        "su_co_mo": len(mo),
        "su_co_qua_han": sum(
            1 for s in mo if getdate(nowdate()) > add_days(getdate(s["ngay"]), han)),
        "ma_tran": M.ma_tran(co_bot),
        "muc": M.MUC,
        "loai_bot": _loai_bot(),
        "nhom_may": {n: {"ten": t[0], "toi_da": t[1], "truong": t[2],
                         "ma": list(M.MA_MAY.get(n, ()))}
                     for n, t in M.NHOM_MAY.items()},
        "buoc_tat_duoc": list(M.BUOC_TAT_DUOC),
        "buoc": [{"ma": a, "ten": b, "oprp": c, "ghi": e} for a, b, c, e in M.BUOC],
        "nguong": {k: v for k, v in nguong().items() if k != "khung"},
        # Khung giờ hiện ngay trên thẻ lượt: QC biết mình còn bao lâu trước khi
        # lượt bị gắn cờ ghi muộn, thay vì biết sau khi đã bị gắn.
        "khung": {l: [str(x or "") for x in v]
                  for l, v in nguong()["khung"].items()},
        "user": frappe.session.user,
        "la_qc_goi": QC_GOI in _roles() and QC not in _roles(),
        "duoc_ghi": bool(_sieu() or _roles() & GHI_DUOC),
        "duoc_duyet": bool(_sieu() or ISO in _roles()),
    }


@frappe.whitelist()
def start_round(ngay, luot, co_san_xuat_bot=None, nhap_lai_tu_giay=0, ca=None):
    """Mở lượt. Đã có bản nháp thì trả lại chính nó, không đẻ bản thứ hai.

    `ca` BỎ QUA (D95 — không còn chia ca). Vẫn nhận tham số này vì điện thoại
    đang mở sẵn bản JS cũ sẽ còn gửi nó cho tới lần tải lại trang; không nhận thì
    Frappe văng "unexpected keyword argument" và QC không mở được lượt nào.
    """
    _guard_ghi()
    d = getdate(ngay)
    luot = M.DOI_TEN_CU.get(luot, luot)   # bản JS cũ gửi "Đầu ca"/"Giữa ca"/…
    if luot not in M.LUOT:
        frappe.throw(_("Lượt không hợp lệ: {0}").format(luot))
    cung = list(M.DAU_NGAY_HOAC_TUAN) if luot in M.DAU_NGAY_HOAC_TUAN else [luot]
    co = frappe.get_all("SX QC Round",
                        filters={"ngay": d, "luot": ("in", cung),
                                 "docstatus": ("<", 2)},
                        fields=["name", "docstatus"], limit=1)
    if co:
        if co[0]["docstatus"] == 1:
            frappe.throw(_("Lượt {0} ngày {1} đã hoàn tất rồi.").format(luot, d))
        return chi_tiet_round(co[0]["name"])

    if co_san_xuat_bot is None or co_san_xuat_bot == "":
        # Không nói gì thì theo cờ của ngày — đó mới là nguồn sự thật (D98).
        co_san_xuat_bot = M.co_bot_ngay(_co_bot_ban_ghi(d), frappe.get_all(
            "SX QC Round", filters={"ngay": d, "docstatus": ("<", 2)},
            fields=["co_san_xuat_bot"]))
    moi = {
        "doctype": "SX QC Round",
        "ngay": d, "luot": luot,
        "co_san_xuat_bot": cint(co_san_xuat_bot),
        "nhap_lai_tu_giay": cint(nhap_lai_tu_giay),
        "qc_user": frappe.session.user,
    }
    truoc = _luot_truoc_cung_ngay(d, luot)
    if truoc:
        for _n, (_t, _max, truong) in M.NHOM_MAY.items():
            moi[truong] = truoc.get(truong) or 1
        # Công đoạn nghỉ buổi sáng thường nghỉ cả ngày (D107).
        moi["buoc_nghi"] = truoc.get("buoc_nghi")
        if cint(co_san_xuat_bot) and truoc.get("san_pham_bot"):
            moi["san_pham_bot"] = truoc.san_pham_bot
    doc = frappe.get_doc(moi)
    doc.insert()
    return chi_tiet_round(doc.name)


def _loai_bot():
    """Các vị bột để bấm chọn ở B0 — [{item, ten, lac}]. Rỗng nếu site chưa có
    field custom_sx_nhom (module qc cài riêng): khi đó ô B0 cho gõ tay."""
    try:
        if not frappe.get_meta("Item").has_field("custom_sx_nhom"):
            return []
        ds = frappe.get_all("Item", filters={"custom_sx_nhom": NHOM_BOT, "disabled": 0},
                            fields=["name", "item_name"], order_by="item_name")
    except Exception:
        return []
    lac = nguong()["bot_co_lac"]
    du = co_di_ung([x.name for x in ds])          # W28: cờ của sản phẩm tự công bố
    return [{"item": x.name, "ten": x.item_name or x.name,
             "lac": 1 if (M.co_lac_trong([x.name], {x.name: x.item_name}, lac)
                          or du.get(x.name, {}).get("lac")) else 0} for x in ds]


def _luot_truoc_cung_ngay(d, luot):
    """Lượt gần nhất TRƯỚC `luot` trong ngày — để lượt mới nhận lại vị bột và số
    máy đang chạy. Dây chuyền không đổi máy mỗi lượt; bắt QC chọn lại từ đầu mỗi
    lượt là mời họ bỏ qua cho nhanh."""
    t = M.thu_tu_luot(luot)
    ds = [r for r in frappe.get_all(
        "SX QC Round", filters={"ngay": d, "docstatus": ("<", 2)},
        fields=["name", "luot", "creation", "san_pham_bot", "buoc_nghi"]
        + [x[2] for x in M.NHOM_MAY.values()])
        if M.thu_tu_luot(r.luot) < t]
    ds.sort(key=lambda r: (M.thu_tu_luot(r.luot), str(r.creation or "")))
    return ds[-1] if ds else None


def _co_bot_ban_ghi(d):
    """Giá trị cờ bột trên SX QC Ngay của ngày `d`, None nếu chưa có bản ghi."""
    r = frappe.get_all("SX QC Ngay", filters={"ngay": d},
                       fields=["co_san_xuat_bot"], limit=1)
    return cint(r[0]["co_san_xuat_bot"]) if r else None


def _ghi_co_bot_ngay(d, co_bot):
    ten = frappe.db.get_value("SX QC Ngay", {"ngay": d}, "name")
    vals = {"co_san_xuat_bot": cint(co_bot), "cap_nhat_boi": frappe.session.user,
            "cap_nhat_luc": now_datetime()}
    if ten:
        frappe.db.set_value("SX QC Ngay", ten, vals)
    else:
        frappe.get_doc({"doctype": "SX QC Ngay", "ngay": d, **vals}).insert()


def _hoi_truoc_khi_tat(docs):
    """Lượt nào sắp bị TẮT bột mà đã ghi mục bột rồi → [(lượt, [nhãn mục])].

    Tắt không xoá giá trị — nó nằm lại trong DB — nhưng mấy ô đó biến khỏi màn
    hình, khỏi tờ in, và không còn sinh sự cố. Phải hỏi trước, không làm lặng lẽ.
    """
    ra = []
    for doc in docs:
        da = M.muc_bot_da_ghi({m["f"]: doc.get(m["f"]) for m in M.MUC})
        if da:
            ra.append({"luot": doc.luot, "name": doc.name,
                       "muc": [f'{m["so"]} {m.get("ngan") or m["nhan"]}' for m in da]})
    return ra


@frappe.whitelist()
def dat_co_bot(ngay, co_bot, ep=0):
    """Bật / tắt "hôm nay có sản xuất bột" cho CẢ NGÀY (D98).

    Đổi luôn mọi lượt ĐANG LÀM DỞ trong ngày. KHÔNG đụng lượt đã hoàn tất: lượt
    Đầu sáng xong lúc 8h mà 10h mới bắt đầu làm bột thì lượt đó đúng là không có
    phần bột — sửa ngược nó là sửa hồ sơ đã chốt.

    Tắt mà có lượt dở đã ghi mục bột → trả `can_xac_nhan` và KHÔNG đổi gì, trừ khi
    `ep=1` (người dùng đã xác nhận).
    """
    _guard_ghi()
    d = getdate(ngay)
    co_bot = cint(co_bot)
    nhap = [frappe.get_doc("SX QC Round", n) for n in frappe.get_all(
        "SX QC Round", filters={"ngay": d, "docstatus": 0}, pluck="name")]
    doi = [x for x in nhap if cint(x.co_san_xuat_bot) != co_bot]
    if not co_bot and not cint(ep):
        hoi = _hoi_truoc_khi_tat(doi)
        if hoi:
            return {"can_xac_nhan": True, "luot": hoi}
    _ghi_co_bot_ngay(d, co_bot)
    for x in doi:
        x.co_san_xuat_bot = co_bot
        x.save()          # validate tính lại "đã chấm x / y" theo ma trận mới
    return {"co_bot": co_bot, "luot_doi": [x.name for x in doi]}


@frappe.whitelist()
def doi_co_bot_luot(name, co_bot, ep=0):
    """Bật / tắt phần bột cho RIÊNG một lượt đang làm dở (D98).

    Bật ở đây thì cờ của NGÀY cũng bật theo: đang đi lượt mà thấy dây chuyền bột
    chạy thì các lượt sau trong ngày cũng phải có phần bột. Tắt thì chỉ lượt này —
    bột có thể dừng giữa ngày mà lượt sau vẫn chạy lại.
    """
    doc = _lay_round(name, de_ghi=True)
    co_bot = cint(co_bot)
    if not co_bot and cint(doc.co_san_xuat_bot) and not cint(ep):
        hoi = _hoi_truoc_khi_tat([doc])
        if hoi:
            return {"can_xac_nhan": True, "luot": hoi}
    doc.co_san_xuat_bot = co_bot
    doc.save()
    if co_bot:
        _ghi_co_bot_ngay(doc.ngay, 1)
    return chi_tiet_round(doc.name)


def _truoc_do(doc):
    """Giá trị nhiệt độ / vòng quay của lượt LIỀN TRƯỚC, để QC đối chiếu.

    Không phải để chép lại — để thấy "lượt trước 262, giờ 248" ngay lúc đứng ở
    máy rang, chứ không phải lúc đọc báo cáo cuối tháng.
    """
    ds = frappe.get_all(
        "SX QC Round",
        filters={"docstatus": 1, "ngay": ("<=", doc.ngay), "name": ("!=", doc.name)},
        fields=["name", "ngay", "luot", "rang_nhiet_do", "rang_vong_quay",
                "finished_at"],
        order_by="ngay desc, finished_at desc", limit=1)
    return ds[0] if ds else None


@frappe.whitelist()
def chi_tiet_round(name):
    """Toàn bộ một lượt: giá trị, mục áp dụng, sự cố, quyền của người đang xem."""
    _guard_qc()
    doc = frappe.get_doc("SX QC Round", name)
    co_bot = cint(doc.co_san_xuat_bot)
    ap = [m["f"] for m in M.muc_ap_dung(doc.luot, doc)]
    return {
        "so_may": M.boi_canh(doc)["may"],
        "buoc_nghi": M.buoc_nghi(doc.get("buoc_nghi")),
        "co_lac": cint(doc.get("co_lac")),
        "can_thu_lac": cint(doc.get("can_thu_lac")),
        "name": doc.name,
        "ngay": str(doc.ngay), "luot": doc.luot, "ca": doc.ca or "",
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
    ap = {m["f"] for m in M.muc_ap_dung(doc.luot, doc)}
    da_ghi, bo_qua = [], []
    for f, v in values.items():
        if f in TRUONG_PHU:
            # Không phải mục kiểm nên không nằm trong ma trận, nhưng vẫn phải ghi
            # được: bật bột / thêm máy giữa lượt là chuyện thật.
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
    # Đổi vị bột / số máy làm bộ mục áp dụng thay đổi → máy QC phải vẽ lại.
    ap_moi = {m["f"] for m in M.muc_ap_dung(doc.luot, doc)}
    return {"name": doc.name, "da_ghi": da_ghi, "bo_qua": bo_qua,
            "doi_muc": ap_moi != ap,
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
        fields=["name", "ngay", "luot", "docstatus", "reviewed_on",
                "t2_so_bay_dau_hieu", "b2_rang_lac_nhiet"])
    # Sự cố KHÔNG giới hạn cửa sổ ngày: cái quá hạn ba tháng mới đúng là cái
    # phải hiện lên, mà nó thì nằm ngoài mọi cửa sổ hợp lý.
    su_co = frappe.get_all("SX Su Co", filters={"trang_thai": "Mở"},
                           fields=["name", "ngay", "trang_thai", "xu_ly_ngay",
                                   "muc_do"])
    return {"ngay": str(d), "ds": _nhac.tinh(d, luot, su_co, nguong(), _bot_nen_ton(),
                                             _luu_mau_nhac(d))}


def _luu_mau_nhac(d):
    """Số mẫu đến hạn chưa vào đợt huỷ + đợt chờ Ban ISO (W07). Lỗi (chưa migrate) → {}."""
    try:
        ds, _g = _den_han_huy(d)
        return {"den_han": len(ds), "lau_nhat": str(ds[0].han_luu) if ds else None,
                "dot_cho": [dict(x, lap_luc=str(x.lap_luc or "")[:10]) for x in frappe.get_all(
                    DHM, filters={"trang_thai": "Chờ xác nhận"},
                    fields=["name", "thang", "lap_luc"])]}
    except Exception:
        return {}


# Nhóm hàng BỘT NỀN (đỗ nghiền, tầng 1) — đọc thẳng Item.custom_sx_nhom như NHOM_BOT.
NHOM_BOT_NEN = "BTP-Bot"


def _bot_nen_ton():
    """Lô bột nền còn tồn trên sổ kho: [{batch, ten, ngay, ton, dvt}] (W06). Ngày = ngày
    làm ra lô (manufacturing_date, không có thì ngày tạo lô). Site chưa có field nhóm
    SX (module qc cài riêng) → [] — không nhắc gì."""
    try:
        if not frappe.get_meta("Item").has_field("custom_sx_nhom"):
            return []
        items = frappe.get_all("Item", filters={"custom_sx_nhom": NHOM_BOT_NEN}, pluck="name")
        if not items:
            return []
        ds = frappe.get_all("Batch", filters={"item": ("in", items), "batch_qty": (">", 0)},
                            fields=["name", "item_name", "manufacturing_date", "creation",
                                    "batch_qty", "stock_uom"], limit=200)
    except Exception:
        return []
    return [{"batch": b.name, "ten": b.item_name, "ton": flt(b.batch_qty, 2),
             "dvt": b.stock_uom or "",
             "ngay": str(getdate(b.manufacturing_date or b.creation))} for b in ds]


@frappe.whitelist()
def list_rounds(tu=None, den=None, ca=None):
    """`ca` bỏ qua từ D95 — giữ tham số cho bản JS cũ đang mở trên điện thoại."""
    _guard_qc()
    tu, den = _khoang(tu, den)
    dk = {"ngay": ("between", [tu, den]), "docstatus": ("<", 2)}
    return frappe.get_all(
        "SX QC Round", filters=dk,
        fields=["name", "ngay", "luot", "ca", "docstatus", "ghi_muon",
                "nhap_lai_tu_giay", "finished_at", "duration_min", "qc_user",
                "reviewed_on", "so_muc_ap_dung", "so_muc_da_cham"],
        order_by="ngay desc, creation")


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


def _ds_cong_doan():
    """Công đoạn chọn được khi ghi sự cố — danh mục SX QC Cong Doan (W04), bỏ
    công đoạn đã ngừng; bánh trước, bột sau, PRP cuối, theo thứ tự trong dây chuyền.
    Chưa có danh mục (chưa migrate) thì dùng bảng gốc trong muc.py."""
    try:
        ds = frappe.get_all("SX QC Cong Doan", filters={"ngung": 0},
                            fields=["name", "day_chuyen", "thu_tu"])
    except Exception:
        ds = []
    if not ds:
        return list(M.CONG_DOAN)
    hang = {"Bánh": 0, "Bột": 1, "Chung": 2}
    ds.sort(key=lambda x: (hang.get(x.day_chuyen, 3), cint(x.thu_tu), x.name))
    return [x.name for x in ds]


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
        fields=["name", "ngay", "nguon", "qc_round", "muc", "cong_doan",
                "loai", "oprp", "muc_do", "mo_ta", "trang_thai", "xu_ly_ngay",
                "quyet_dinh_sp", "nguoi_xu_ly", "dong_boi", "dong_ngay",
                "lo_anh_huong", "so_luong", "nguyen_nhan", "hanh_dong_khac_phuc",
                "car_so"],
        order_by="ngay desc, creation desc")
    return {"danh_sach": _dong_su_co(ds),
            "duoc_dong": bool(_sieu() or ISO in _roles()),
            "cong_doan": _ds_cong_doan(), "loai": list(M.LOAI_SU_CO),
            "quyet_dinh_sp": list(M.QUYET_DINH_SP)}


@frappe.whitelist()
def add_incident(payload):
    """Sự cố phát hiện ngoài vòng kiểm (nguồn 'Phát hiện khác')."""
    _guard_qc()
    if isinstance(payload, str):
        payload = json.loads(payload)
    cho_phep = {"ngay", "cong_doan", "loai", "muc_do", "mo_ta",
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
        fields=["name", "ngay", "luot", "ghi_muon", "nhap_lai_tu_giay",
                "duration_min", "rang_nhiet_do", "rang_vong_quay",
                "thung_bot_qua_han", "t2_so_bay_dau_hieu", "reviewed_on",
                "finished_at"],
        order_by="ngay, finished_at")
    su_co = frappe.get_all(
        "SX Su Co", filters={"ngay": ("between", [tu, den])},
        fields=["name", "ngay", "cong_doan", "loai", "muc_do", "trang_thai"])

    so_ngay = (getdate(den) - getdate(tu)).days + 1
    can_co = so_ngay * len(M.LUOT_TRONG_NGAY)   # 3 lượt mỗi ngày (D95)
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
        "chuoi_rang": [{"ngay": str(r["ngay"]), "luot": r["luot"],
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
    # `ca` bỏ qua từ D95 — giữ tham số cho bản JS cũ đang mở trên điện thoại.
    """HTML tờ ngày BM.08.01 để in / xuất PDF đưa auditor.

    Ba cột lượt trên một trang, đúng bố cục bản giấy — auditor cầm tờ này so với
    tập hồ sơ cũ mà không phải học đọc format mới.
    """
    _guard_qc()
    return _to_ngay(ngay)


@frappe.whitelist()
def month_sheets(tu, den, ca=None):
    # `ca` bỏ qua từ D95.
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
    ra = [_to_ngay(co[0], kem_style=True)]
    ra += [_to_ngay(d, kem_style=False) for d in co[1:]]
    return '<div style="page-break-after:always"></div>'.join(ra)


def _thu_tu_luot(r):
    """Khoá sắp xếp: Đầu sáng/Tuần → Trưa → Cuối chiều, rồi theo lúc tạo.

    Không sắp theo `creation` trần: lượt nhập lại từ bản giấy có thể được tạo
    sau lượt Trưa của cùng ngày, và tờ in ra cột Trưa đứng trước cột Đầu sáng
    thì auditor đọc lệch cả trang.
    """
    luot = M.DAU_SANG if r.luot == M.TUAN else r.luot
    thu = (M.LUOT_TRONG_NGAY.index(luot) if luot in M.LUOT_TRONG_NGAY
           else len(M.LUOT_TRONG_NGAY))
    return (thu, str(r.creation or ""))


def _to_ngay(ngay, kem_style=True):
    d = getdate(ngay)
    ds = frappe.get_all("SX QC Round", filters={"ngay": d, "docstatus": 1},
                        pluck="name", order_by="creation")
    rounds = sorted((frappe.get_doc("SX QC Round", n) for n in ds), key=_thu_tu_luot)
    co_bot = 1 if any(cint(r.co_san_xuat_bot) for r in rounds) else 0

    cot = [{"doc": r, "ap": {m["f"] for m in M.muc_ap_dung(r.luot, r)}} for r in rounds]
    pb_ngay = {M.phien_ban(r.get("phien_ban")) for r in rounds} or {M.PHIEN_BAN}
    co_mat = set().union(*[c["ap"] for c in cot]) if cot else set()
    nhieu_may = {n for n in M.NHOM_MAY
                 if any(M.boi_canh(r)["may"][n] > 1 for r in rounds)}
    hang = []
    for ma, ten, oprp, _ghi in M.BUOC:
        # Dòng in ra: mục dây chuyền bánh luôn in (tờ giống bản giấy), còn máy
        # 2/3, phần bột, phần lạc chỉ in khi có lượt nào trong ngày áp dụng —
        # in sẵn ba máy trống thì auditor tưởng ba máy chạy mà không ai kiểm.
        # D129: mục không có trong bộ mục của BẤT KỲ lượt nào hôm đó (T11 đã bỏ, mục
        # mới chưa có) thì không in — hàng trống của một mục không tồn tại là sai.
        muc_buoc = [m for m in M.MUC if m["buoc"] == ma
                    and (m["f"] in co_mat
                         or (not m["bot"] and not m.get("lac") and not m.get("sua")
                             and m["may_so"] <= 1
                             and any(M.con_hieu_luc(m, pb) for pb in pb_ngay)))]
        if not muc_buoc:
            continue
        hang.append({"buoc": True, "ten": f"{ma}. {ten}"
                     + (f" ({oprp})" if oprp else "")})
        for m in muc_buoc:
            nhan = m["nhan"]
            if m["may_so"] == 1 and m["may"] in nhieu_may:
                nhan += f' — {M.ten_may_so(m["may"], 1)}'
            hang.append({
                "buoc": False, "so": m["so"], "nhan": nhan,
                "o": [("" if m["f"] not in c["ap"]
                       else _in_gia_tri(m, c["doc"].get(m["f"])))
                      for c in cot],
                "khong_ap": [m["f"] not in c["ap"] for c in cot],
            })
    loai_bot = [(r.luot, ", ".join(M.tach_chon(r.get("san_pham_bot"))))
                for r in rounds if cint(r.co_san_xuat_bot) and r.get("san_pham_bot")]
    # D107: ô xám của công đoạn nghỉ phải có lời giải thích trên tờ in — auditor
    # thấy cả hàng Rang trống mà không thấy chữ nào là hỏi ngay.
    ten_buoc = {ma: ten for ma, ten, *_r in M.BUOC}
    buoc_nghi = [(r.luot, ", ".join(f"{ma} {ten_buoc[ma]}" for ma in M.buoc_nghi(r.get("buoc_nghi"))))
                 for r in rounds if M.buoc_nghi(r.get("buoc_nghi"))]
    return frappe.render_template("sx/qc/day_sheet.html", {
        "ngay": d, "rounds": rounds, "hang": hang, "co_bot": co_bot,
        "loai_bot": loai_bot,
        "buoc_nghi": buoc_nghi,
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
                        pluck="name", order_by="ngay, creation")
    return xuat.thanh_csv(
        xuat.tieu_de_luot(),
        [xuat.dong_luot(frappe.get_doc("SX QC Round", n), _in_csv, cint)
         for n in ds])


def _in_csv(m, v):
    """CSV có chỗ: in đủ tên các vị thay cho "2 vị" của tờ A4, đủ chữ cho mục
    chuyển đổi thay cho "KCĐ"."""
    if m["kieu"] == "chon_bot":
        return "; ".join(M.tach_chon(v)) or "—"
    if m["kieu"] == "chon_cd":
        return v or "—"
    return _in_gia_tri(m, v)


def _in_gia_tri(m, v):
    if m["kieu"] == "co_khong":
        return "x" if cint(v) else ""
    if v is None or v == "":
        return "—"
    if m["kieu"] == "chon":
        return "Đ" if v == M.DAT else ("K" if v == M.KHONG_DAT else "—")
    if m["kieu"] == "chon_cd":
        # Ô A4 hẹp: KCĐ = không có chuyển đổi (chú thích cuối tờ).
        return {M.DAT: "Đ", M.KHONG_DAT: "K", M.B7_KHONG: "KCĐ"}.get(v, "—")
    if m["kieu"] == "chon_bot":
        # Ô trên tờ A4 chỉ rộng 34 px — in số vị, tên đầy đủ in ở dòng dưới bảng.
        n = len(M.tach_chon(v))
        return f"{n} vị" if n else "—"
    if m["kieu"] in M.KIEU_SO and not M.co_ghi(m, v):
        return "—"
    return str(v)


# ──────────────────────────────────────────────────────────── lưu mẫu (D100) ──
#
# Tab "Lưu mẫu": QC chế biến / đóng gói lấy mẫu và xử lý mẫu; QLSX, Ban ISO xem.
# Người đọc được = người vào được module QC — tủ mẫu không có gì bí mật, còn
# khi có khiếu nại thì ai cũng cần tra ra "mẫu lô này còn không, nằm ở đâu".

LM = "SX QC Luu Mau"
DHM = "SX QC Dot Huy Mau"


def _han_luu(goc):
    """Hạn lưu mặc định = NSX (hoặc ngày lấy) + số tháng ở Setting (W07: 12 tháng)."""
    from frappe.utils import add_months

    return add_months(getdate(goc), cint(nguong()["luu_mau_so_thang"]) or 12)


def _han_mac_dinh(ngay_lay):
    # Giữ tên cũ cho nơi gọi trước D133 — giờ tính theo THÁNG.
    return _han_luu(ngay_lay)


def _duoc_huy():
    """Huỷ mẫu là việc Ban ISO xác nhận (W07) — QC chỉ đề xuất đợt huỷ."""
    return bool(_sieu() or ISO in _roles())


def _giu(ds):
    from sx.qc.giu_mau import ly_do_giu

    return ly_do_giu([{"name": x.name, "batch": x.get("batch"), "hsd": x.get("hsd"),
                       "giu_lai": x.get("giu_lai"), "ly_do_giu": x.get("ly_do_giu")}
                      for x in ds])


TRUONG_LM = ["name", "san_pham", "ten_san_pham", "lo", "so_luong", "dvt", "ngay_lay",
             "han_luu", "vi_tri", "trang_thai", "lay_boi", "ly_do", "xu_ly_boi", "xu_ly_luc",
             "anh", "batch", "nsx", "hsd", "giu_lai", "ly_do_giu", "dot_huy"]


def _den_han_huy(hom_nay=None):
    """Mẫu Đang lưu đã hết hạn lưu và KHÔNG bị giữ — thứ được đưa vào đợt huỷ."""
    hom_nay = getdate(hom_nay or nowdate())
    ds = frappe.get_all(LM, filters={"trang_thai": "Đang lưu", "han_luu": ("<=", hom_nay)},
                        fields=TRUONG_LM, order_by="han_luu asc", limit=500)
    giu = _giu(ds)
    return [x for x in ds if x.name not in giu], giu


@frappe.whitelist()
def list_luu_mau(q=None, trang_thai="Đang lưu", limit=200):
    """Mẫu theo trạng thái (mặc định đang lưu), mẫu đến hạn huỷ lên đầu.

    Kèm gợi ý cho form lấy mẫu: sản phẩm và vị trí dùng gần đây — lấy mẫu là việc
    lặp lại hằng ngày với cùng vài sản phẩm, cùng vài ngăn tủ. W07: mẫu đang bị GIỮ
    (lô có sự cố / khiếu nại mở, hoặc bấm Giữ lại) kèm lý do; các đợt huỷ chờ Ban ISO.
    """
    _guard_qc()
    loc = {}
    if trang_thai:
        loc["trang_thai"] = trang_thai
    or_loc = None
    if q:
        k = f"%{q.strip()}%"
        or_loc = {"ten_san_pham": ("like", k), "san_pham": ("like", k),
                  "lo": ("like", k), "vi_tri": ("like", k)}
    ds = frappe.get_all(LM, filters=loc, or_filters=or_loc, fields=TRUONG_LM,
                        order_by="han_luu asc, ngay_lay desc", limit=cint(limit) or 200)
    hom_nay = getdate(nowdate())
    giu = _giu([x for x in ds if x.trang_thai in ("Đang lưu", "Chờ huỷ")])
    for x in ds:
        x["den_han"] = x.trang_thai == "Đang lưu" and getdate(x.han_luu) <= hom_nay
        x["con_ngay"] = (getdate(x.han_luu) - hom_nay).days
        x["giu"] = giu.get(x.name)
        for k in ("ngay_lay", "han_luu", "xu_ly_luc", "nsx", "hsd"):
            x[k] = str(x[k]) if x.get(k) else ""
    # Không cần sắp lại: đến hạn ⇔ han_luu ≤ hôm nay, nên han_luu tăng dần đã đưa
    # mẫu đến hạn lên đầu.

    gan_day = frappe.get_all(LM, fields=["san_pham", "ten_san_pham", "vi_tri", "dvt"],
                             order_by="creation desc", limit=60)
    sp, vt = {}, []
    for x in gan_day:
        if x.san_pham and x.san_pham not in sp:
            sp[x.san_pham] = {"item": x.san_pham, "ten": x.ten_san_pham or x.san_pham,
                              "dvt": x.dvt or ""}
        if x.vi_tri and x.vi_tri not in vt:
            vt.append(x.vi_tri)
    den_han, _g = _den_han_huy(hom_nay)
    return {
        "danh_sach": ds,
        "so_den_han": len(den_han),
        "goi_y_sp": list(sp.values())[:8],
        "goi_y_vi_tri": vt[:8],
        "so_thang_luu": cint(nguong()["luu_mau_so_thang"]) or 12,
        "han_mac_dinh": str(_han_luu(hom_nay)),
        "duoc_ghi": bool(_sieu() or _roles() & GHI_DUOC),
        "duoc_huy": _duoc_huy(),
        "dot_cho": [dict(d, so_mau=cint(frappe.db.count(
            "SX QC Dot Huy Mau Item", {"parent": d.name, "parenttype": DHM})))
            for d in frappe.get_all(DHM, filters={"trang_thai": "Chờ xác nhận"},
                                    fields=["name", "thang", "lap_boi", "lap_luc"],
                                    order_by="creation asc")],
    }


@frappe.whitelist()
def lo_cua_sp(san_pham):
    """Các lô của một sản phẩm để chọn khi lấy mẫu — hiện theo HSD (W05: ẩn mã lô),
    lô mới nhất trước. Kèm NSX và hạn lưu mặc định (NSX + 12 tháng)."""
    _guard_qc()
    if not san_pham:
        return []
    ds = frappe.get_all("Batch", filters={"item": san_pham, "expiry_date": ("is", "set"),
                                          "disabled": 0},
                        fields=["name", "manufacturing_date", "expiry_date", "batch_qty"],
                        order_by="expiry_date desc", limit=30)
    return [{"batch": b.name, "hsd": str(b.expiry_date), "nsx": str(b.manufacturing_date or ""),
             "ton": flt(b.batch_qty, 2),
             "han_luu": str(_han_luu(b.manufacturing_date or nowdate()))} for b in ds]


@frappe.whitelist()
def tim_hang(q):
    """Tìm sản phẩm theo mã / tên — cho ô chọn sản phẩm của form lấy mẫu."""
    _guard_qc()
    q = (q or "").strip()
    if len(q) < 2:
        return []
    k = f"%{q}%"
    return [{"item": x.name, "ten": x.item_name or x.name, "dvt": x.stock_uom or ""}
            for x in frappe.get_all(
                "Item", filters={"disabled": 0, "has_variants": 0},
                or_filters={"name": ("like", k), "item_name": ("like", k)},
                fields=["name", "item_name", "stock_uom"],
                order_by="item_name", limit=20)]


@frappe.whitelist()
def tao_luu_mau(payload):
    """Ghi một lần lấy mẫu. Hạn lưu bỏ trống = ngày lấy + số ngày ở SX QC Setting."""
    _guard_ghi()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    ngay_lay = getdate(p.get("ngay_lay") or nowdate())
    batch = (p.get("batch") or "").strip() or None
    nsx = frappe.db.get_value("Batch", batch, "manufacturing_date") if batch else None
    hsd = frappe.db.get_value("Batch", batch, "expiry_date") if batch else None
    lo = (p.get("lo") or "").strip()
    if batch and not lo and hsd:
        lo = _("HSD {0}").format(getdate(hsd).strftime("%d/%m/%Y"))   # tìm theo chữ vẫn ra
    doc = frappe.get_doc({
        "doctype": LM,
        "san_pham": p.get("san_pham"),
        "batch": batch,
        "lo": lo,
        "so_luong": flt(p.get("so_luong")),
        "dvt": (p.get("dvt") or "").strip() or "hộp",
        "vi_tri": (p.get("vi_tri") or "").strip(),
        "ngay_lay": ngay_lay,
        # W07: 1 năm (Setting) tính từ NSX của lô; không gắn lô thì từ ngày lấy.
        "han_luu": getdate(p.get("han_luu")) if p.get("han_luu") else _han_luu(nsx or ngay_lay),
        "ghi_chu": (p.get("ghi_chu") or "").strip(),
        "trang_thai": "Đang lưu",
        "lay_boi": frappe.session.user,
    })
    if not doc.san_pham:
        frappe.throw(_("Chưa chọn sản phẩm."))
    doc.insert()
    return {"name": doc.name, "han_luu": str(doc.han_luu)}


@frappe.whitelist()
def xu_ly_luu_mau(name, hanh_dong, ly_do=None):
    """Kết thúc lưu một mẫu: `hanh_dong` = 'huy' (hết hạn / huỷ sớm có lý do) hoặc
    'lay_ra' (dùng cho khiếu nại / kiểm nghiệm — bắt buộc lý do)."""
    _guard_qc()
    moi = {"huy": "Đã huỷ", "lay_ra": "Đã lấy ra"}.get(hanh_dong)
    if not moi:
        frappe.throw(_("Thao tác không hợp lệ: {0}").format(hanh_dong))
    if hanh_dong == "huy" and not _duoc_huy():
        # W07: huỷ mẫu là việc Ban ISO xác nhận. QC gom mẫu đến hạn thành đợt huỷ tháng.
        frappe.throw(_("Huỷ mẫu cần Trưởng Ban ISO xác nhận — mẫu đến hạn thì bấm ĐỀ XUẤT "
                       "HUỶ để gom vào đợt huỷ tháng."), frappe.PermissionError)
    if hanh_dong == "lay_ra":
        _guard_ghi()
    doc = frappe.get_doc(LM, name)
    # Mẫu đã vào đợt huỷ (Chờ huỷ) vẫn LẤY RA được — khiếu nại tới đúng lúc đó thì mẫu
    # phải đi được ngay, không đợi Ban ISO trả lại cả đợt. Huỷ thì chỉ từ Đang lưu.
    duoc_tu = ("Đang lưu", "Chờ huỷ") if hanh_dong == "lay_ra" else ("Đang lưu",)
    if doc.trang_thai not in duoc_tu:
        frappe.throw(_("Mẫu {0} đã ở trạng thái {1}.").format(name, doc.trang_thai))
    doc.trang_thai = moi
    doc.ly_do = (ly_do or "").strip() or doc.ly_do
    doc.xu_ly_boi = frappe.session.user
    doc.xu_ly_luc = now_datetime()
    doc.save()            # validate chặn thiếu lý do — cùng luật cho cả Desk
    return {"name": name, "trang_thai": moi}


@frappe.whitelist()
def giu_mau(name, giu=1, ly_do=None):
    """Bật / tắt "Giữ lại" một mẫu (W07) — khiếu nại / điều tra chưa có phiếu."""
    if not _duoc_huy():
        _guard_ghi()
    doc = frappe.get_doc(LM, name)
    doc.giu_lai = 1 if cint(giu) else 0
    doc.ly_do_giu = (ly_do or "").strip() if cint(giu) else doc.ly_do_giu
    doc.save()
    return {"name": name, "giu_lai": doc.giu_lai}


@frappe.whitelist()
def de_xuat_huy(ghi_chu=None):
    """QC gom MỌI mẫu đến hạn lưu (không bị giữ) thành một đợt huỷ tháng (W07).
    Mẫu chuyển "Chờ huỷ" — chưa huỷ cho tới khi Ban ISO xác nhận."""
    _guard_ghi()
    if frappe.get_all(DHM, filters={"trang_thai": "Chờ xác nhận"}, limit=1):
        frappe.throw(_("Còn đợt huỷ chờ Ban ISO xác nhận — xác nhận / trả lại đợt đó trước."))
    ds, _g = _den_han_huy()
    if not ds:
        frappe.throw(_("Không có mẫu nào đến hạn huỷ (mẫu đang bị giữ không tính)."))
    hom_nay = getdate(nowdate())
    d = frappe.get_doc({"doctype": DHM, "thang": hom_nay.strftime("%m/%Y"),
                        "trang_thai": "Chờ xác nhận", "lap_boi": frappe.session.user,
                        "lap_luc": now_datetime(), "ghi_chu": (ghi_chu or "").strip()})
    for x in ds:
        d.append("ds", {"luu_mau": x.name, "ten_san_pham": x.ten_san_pham or x.san_pham,
                        "lo_hsd": x.lo or (f"HSD {x.hsd}" if x.hsd else ""),
                        "so_luong": x.so_luong, "dvt": x.dvt, "ngay_lay": x.ngay_lay,
                        "han_luu": x.han_luu, "vi_tri": x.vi_tri})
    d.insert(ignore_permissions=True)
    for x in ds:
        frappe.db.set_value(LM, x.name, {"trang_thai": "Chờ huỷ", "dot_huy": d.name})
    return {"name": d.name, "so_mau": len(ds)}


@frappe.whitelist()
def xac_nhan_huy(dot, dong_y=1, ly_do=None):
    """Trưởng Ban ISO xác nhận đợt huỷ (W07). Đồng ý → mẫu "Đã huỷ", trừ mẫu bị GIỮ
    từ lúc đề xuất (lô vừa có sự cố / bấm giữ) — trả về Đang lưu và nói ra. Không đồng ý
    (bắt buộc lý do) → mọi mẫu về Đang lưu. Mỗi dòng của đợt ghi lại kết quả cho biên bản."""
    _guard_manager()
    d = frappe.get_doc(DHM, dot)
    if d.trang_thai != "Chờ xác nhận":
        frappe.throw(_("Đợt {0} không còn chờ xác nhận (đang: {1}).").format(dot, d.trang_thai))
    dong_y = cint(dong_y)
    ly_do = (ly_do or "").strip()
    if not dong_y and not ly_do:
        frappe.throw(_("Trả lại đợt huỷ thì phải ghi lý do."))
    ten = [r.luu_mau for r in d.ds]
    mau = {x.name: x for x in (frappe.get_all(LM, filters={"name": ("in", ten)},
                                              fields=TRUONG_LM) if ten else [])}
    luc = now_datetime()
    giu = _giu([x for x in mau.values() if x.trang_thai == "Chờ huỷ"]) if dong_y else {}
    dem = {"Đã huỷ": 0, "Giữ lại": 0, "Trả lại": 0}
    for r in d.ds:
        x = mau.get(r.luu_mau)
        if not x or x.trang_thai != "Chờ huỷ":
            # Đã lấy ra giữa chừng (khiếu nại) — ghi đúng việc đã xảy ra với mẫu.
            kq = x.trang_thai if x else _("Không còn bản ghi")
        elif not dong_y or x.name in giu:
            frappe.db.set_value(LM, x.name, {"trang_thai": "Đang lưu", "dot_huy": None})
            kq = "Trả lại" if not dong_y else "Giữ lại"
        else:
            frappe.db.set_value(LM, x.name, {
                "trang_thai": "Đã huỷ", "xu_ly_boi": frappe.session.user, "xu_ly_luc": luc,
                "ly_do": _("Huỷ định kỳ — đợt {0} (tháng {1}), Ban ISO xác nhận").format(
                    d.name, d.thang)})
            kq = "Đã huỷ"
        if kq in dem:
            dem[kq] += 1
        if x and x.name in giu:      # "Giữ lại: <lý do bấm giữ>" / "Giữ lại — lô có sự cố…"
            kq = giu[x.name] if giu[x.name].startswith("Giữ lại") else f"Giữ lại — {giu[x.name]}"
        frappe.db.set_value("SX QC Dot Huy Mau Item", r.name, "ket_qua", kq)
    if ly_do:
        ly_do = (_("Ban ISO: {0}") if dong_y else _("Ban ISO trả lại: {0}")).format(ly_do)
    d.db_set({"trang_thai": "Đã huỷ" if dong_y else "Trả lại",
              "xac_nhan_boi": frappe.session.user, "xac_nhan_luc": luc,
              "ghi_chu": "\n".join(t for t in ((d.ghi_chu or "").strip(), ly_do) if t)})
    return {"name": dot, "da_huy": dem["Đã huỷ"], "giu_lai": dem["Giữ lại"],
            "tra_lai": dem["Trả lại"], "giu": giu}


@frappe.whitelist()
def in_bien_ban_huy(dot):
    """HTML A4 — biên bản huỷ mẫu lưu của một đợt."""
    _guard_qc()
    d = frappe.get_doc(DHM, dot)
    return frappe.render_template("sx/qc/bien_ban_huy_mau.html", {"d": d})


# ─────────────────────────────────────────────────────── ảnh lưu mẫu (D109) ──
#
# Ảnh nén trên máy (lib/anh.js, ~300 KB) rồi gửi base64. Lưu thành File RIÊNG TƯ
# gắn vào phiếu lưu mẫu: chỉ người đọc được phiếu mới mở được ảnh.

ANH_MOT_LAN = 4               # ảnh tối đa một lần gửi
ANH_TOI_DA = 8                # ảnh tối đa một mẫu
ANH_BYTE_TOI_DA = 1536 * 1024  # 1,5 MB/ảnh SAU nén — lớn hơn là máy không nén được


def _kieu_anh(b):
    """'jpg' / 'png' / 'webp' theo chữ ký đầu file, None nếu không phải ảnh."""
    if b[:3] == b"\xff\xd8\xff":
        return "jpg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp"
    return None


def _anh_cua(name):
    return frappe.get_all("File", filters={"attached_to_doctype": LM, "attached_to_name": name},
                          fields=["name", "file_url", "file_size"], order_by="creation asc")


@frappe.whitelist()
def them_anh_luu_mau(name, anh):
    """Gắn ảnh vào một mẫu. `anh` = [base64 JPEG/PNG/WebP]. Ảnh đầu tiên của mẫu
    thành ảnh đại diện (field `anh`) để danh sách hiện thumbnail."""
    import base64
    import binascii

    _guard_ghi()
    ds = json.loads(anh) if isinstance(anh, str) else (anh or [])
    if not ds:
        frappe.throw(_("Chưa có ảnh nào."))
    if len(ds) > ANH_MOT_LAN:
        frappe.throw(_("Gửi tối đa {0} ảnh một lần.").format(ANH_MOT_LAN))
    doc = frappe.get_doc(LM, name)
    co = _anh_cua(name)
    if len(co) + len(ds) > ANH_TOI_DA:
        frappe.throw(_("Mỗi mẫu tối đa {0} ảnh — mẫu này đã có {1}.").format(ANH_TOI_DA, len(co)))

    goi = []
    for i, s in enumerate(ds, start=1):
        try:
            b = base64.b64decode(str(s).split(",")[-1], validate=True)
        except (binascii.Error, ValueError):
            frappe.throw(_("Ảnh thứ {0} hỏng — chụp lại.").format(i))
        kieu = _kieu_anh(b)
        if not kieu:
            frappe.throw(_("Tệp thứ {0} không phải ảnh.").format(i))
        if len(b) > ANH_BYTE_TOI_DA:
            frappe.throw(_("Ảnh thứ {0} quá lớn ({1} KB) — máy chưa nén được ảnh này.")
                         .format(i, len(b) // 1024))
        goi.append((b, kieu))

    urls = []
    for i, (b, kieu) in enumerate(goi, start=len(co) + 1):
        f = frappe.get_doc({
            "doctype": "File", "file_name": f"{name}-{i}.{kieu}",
            "attached_to_doctype": LM, "attached_to_name": name,
            "is_private": 1, "content": b,
        })
        f.insert(ignore_permissions=True)
        urls.append(f.file_url)
    if not doc.anh and urls:
        frappe.db.set_value(LM, name, "anh", urls[0], update_modified=False)
    return {"name": name, "anh": urls, "so_anh": len(co) + len(urls)}


@frappe.whitelist()
def anh_luu_mau(name):
    """Mọi ảnh của một mẫu — để xem lớn khi bấm vào thumbnail."""
    _guard_qc()
    return [{"url": f.file_url, "kb": cint(f.file_size) // 1024} for f in _anh_cua(name)]
