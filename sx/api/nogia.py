"""Sổ nợ đơn giá vào hộp (D99).

QC ghi được mã chưa khai giá (D68 — chặn lại giữa xưởng là bắt cả chuyền dừng), và
chốt Vào hộp cũng không chặn. Nhưng trước D99, chốt xong thì lương khoán của mã đó
nằm trong phiếu lương tháng ở mức 0 đồng và KHÔNG AI NHỚ phải bù — tới lúc công nhân
cầm phiếu lương mới lộ.

Từ D99, lúc chốt Vào hộp mọi (mã hàng, cách làm) không tra được giá ghi thành một
dòng nợ. Khai giá xong ở SX Bang Don Gia, quản lý bấm Áp giá: giá được điền vào
đúng những dòng 0 đồng của ngày đó trong phiếu lương tháng (và bảng vào hộp đã chốt,
để báo cáo khớp), không phải huỷ chốt rồi chốt lại cả ngày.

Nguồn giá DUY NHẤT vẫn là bảng đơn giá áp dụng cho ngày sản xuất — không cho gõ tay
một con số ở đây. Gõ tay thì hai nơi giữ giá, chốt lại ngày đó sẽ ra số khác.

Xem + xử lý: CHỈ QUẢN LÝ (card nogia) — áp giá là sửa lương của người khác.

MỐC TÍNH NỢ (D229): lệnh bench `bo_no_truoc` Bỏ qua (giữ 0 đồng, có lý do) mọi khoản nợ đang chờ giá của ngày sản xuất
trước mốc và đặt mốc vào SX Settings (no_gia_tu_ngay) — từ đó đồng bộ lương của ngày trước mốc không sinh / sửa nợ đơn
giá nữa (lưu lại bảng vào hộp tháng cũ không làm nợ đã bỏ hiện lại).
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from sx.config.roles import guard_card
from sx.utils import bang_don_gia, don_gia_ap_dung, get_settings, tra_don_gia

CHO = "Chờ giá"
BO_QUA = "Bỏ qua"
NGAY_NO_LAU = 7
TRUONG_MOC = "no_gia_tu_ngay"       # SX Settings — D229
LY_DO_MOC = "Bỏ nợ trước {0} — chỉ tính nợ đơn giá từ {0} (D229)"


def gom_thieu_gia(dong, bang_gia):
    """{(san_pham, cach_lam): {"so_hop", "nguoi"}} của các dòng KHÔNG tra được giá.

    Hàm thuần: tra bằng đúng hàm mà bảng vào hộp dùng lúc tính tiền, nên "thiếu giá"
    ở đây và "tính 0 đồng" ở bảng không bao giờ lệch nhau.

    `dong` là dòng bảng con của Frappe (bang.dong) — CHỈ đọc bằng r.get(...): dòng con
    không subscript được, r["san_pham"] là TypeError "'SXBangVaoHopItem' object is not
    subscriptable" → cả lần ghi phiếu lương của ngày bị rút lại (D202).
    """
    ra = {}
    for r in dong:
        sp, so = r.get("san_pham"), cint(r.get("so_hop"))
        if not sp or so <= 0:
            continue
        if cint(r.get("cong_nhat")):
            continue   # công nhật không trả khoán → không có gì để nợ giá (D101)
        if tra_don_gia(bang_gia, sp, r.get("cach_lam")) is not None:
            continue
        g = ra.setdefault((sp, r.get("cach_lam") or ""), {"so_hop": 0, "nguoi": set()})
        g["so_hop"] += so
        g["nguoi"].add(r.get("nhan_vien"))
    return ra


def ghi_no_gia(doc, bang):
    """Gọi TRONG giao dịch chốt Vào hộp: mỗi (mã, cách làm) thiếu giá thành một dòng
    nợ. Chốt vỡ thì rollback kéo theo — không có nợ mồ côi của một lần chốt hỏng."""
    ngay = getdate(doc.ngay)
    thieu = gom_thieu_gia(bang.dong, don_gia_ap_dung(ngay))
    if not thieu:
        return []
    ten_bang = bang_don_gia(ngay)
    ds = []
    for (sp, cl), g in sorted(thieu.items()):
        no = frappe.get_doc({
            "doctype": "SX No Don Gia",
            "san_pham": sp,
            "ten_san_pham": frappe.db.get_value("Item", sp, "item_name") or sp,
            "cach_lam": cl or None,
            "so_hop": g["so_hop"],
            "so_nguoi": len(g["nguoi"]),
            "trang_thai": CHO,
            "ngay": ngay,
            "ngay_sx": doc.name,
            "bang_vao_hop": bang.name,
            "bang_don_gia": ten_bang,
        })
        no.flags.ignore_permissions = True
        no.insert()
        ds.append(no.name)
    return ds


def huy_no_gia(ngay_sx):
    """Huỷ chốt Vào hộp: dòng lương 0 đồng đã bị gỡ khỏi phiếu lương, nên nợ của
    lần chốt đó cũng hết nghĩa. Chốt lại sẽ tra giá lại từ đầu — còn thiếu thì sinh
    nợ mới. Nợ đã áp giá / bỏ qua giữ nguyên làm dấu vết."""
    ds = frappe.get_all("SX No Don Gia", filters={"ngay_sx": ngay_sx, "trang_thai": CHO},
                        pluck="name")
    for n in ds:
        frappe.db.set_value("SX No Don Gia", n, "trang_thai", "Đã huỷ")
    return ds


def go_lien_ket_no_gia(bang_vao_hop=None, ngay_sx=None):
    """Bảng vào hộp / phiếu ngày SẮP BỊ XOÁ (D206): gỡ các dòng nợ đơn giá trỏ vào nó — không thì Frappe chặn xoá
    ("Cannot delete or cancel because SX Bang Vao Hop … is linked with SX No Don Gia …"). Xoá dòng cuối ở màn Ghi
    hộp là xoá luôn bảng nháp (D106), nên lỗi này gặp ngay khi bảng có mã chưa khai giá.

    Nợ đang chờ giá thì huỷ — không còn dòng nào để trả. Nợ đã áp giá / bỏ qua / huỷ giữ nguyên làm dấu vết (ngày,
    mã, số hộp vẫn còn), chỉ bỏ ô liên kết. Gọi từ on_trash: Frappe chạy on_trash TRƯỚC khi kiểm tra liên kết."""
    truong, ten = ("bang_vao_hop", bang_vao_hop) if bang_vao_hop else ("ngay_sx", ngay_sx)
    if not ten:
        return []
    ds = frappe.get_all("SX No Don Gia", filters={truong: ten}, fields=["name", "trang_thai"])
    for x in ds:
        vals = {truong: None}
        if x.trang_thai == CHO:
            vals["trang_thai"] = "Đã huỷ"
        frappe.db.set_value("SX No Don Gia", x.name, vals, update_modified=False)
    return [x.name for x in ds]


def canh_bao_no_gia(ngay_sx):
    """Câu cảnh báo sau khi chốt — nói rõ đã GHI NỢ, không phải "đã tính 0 đồng"."""
    ds = frappe.get_all("SX No Don Gia", filters={"ngay_sx": ngay_sx, "trang_thai": CHO},
                        fields=["san_pham", "ten_san_pham", "cach_lam", "so_hop"])
    if not ds:
        return []
    ma = ", ".join(
        "{0}{1} ({2} hộp)".format(x.ten_san_pham or x.san_pham,
                                  " · " + x.cach_lam if x.cach_lam else "", cint(x.so_hop))
        for x in ds)
    return [_("{0} mã chưa có đơn giá: {1}. Lương khoán các mã này đang 0 đồng và đã "
              "ghi vào SỔ NỢ ĐƠN GIÁ — khai giá ở bảng đơn giá rồi bấm Áp giá ở màn "
              "Quản lý.").format(len(ds), ma)]


def _khop(r, no):
    return (r.san_pham == no.san_pham and (r.cach_lam or "") == (no.cach_lam or "")
            and str(getdate(r.ngay)) == str(getdate(no.ngay)))


def _phieu_cua_ngay(ngay_sx):
    raw = frappe.db.get_value("SX Ngay San Xuat", ngay_sx, "salary_products_json")
    return [g.get("phieu") for g in json.loads(raw or "[]") if g.get("phieu")]


def _ap_mot(no, gia):
    """Điền giá vào phiếu lương + bảng vào hộp của MỘT dòng nợ. Trả (tiền, lỗi)."""
    phieu = []
    for ten in _phieu_cua_ngay(no.ngay_sx):
        if not frappe.db.exists("SX Phieu Luong", ten):
            continue
        p = frappe.get_doc("SX Phieu Luong", ten)
        dong = [r for r in p.chi_tiet if _khop(r, no) and not flt(r.don_gia)]
        if dong:
            phieu.append((p, dong))
    da_duyet = [p.name for p, _d in phieu if p.docstatus != 0]
    if da_duyet:
        return 0, _("{0} ngày {1}: phiếu lương {2} đã duyệt — huỷ duyệt rồi áp giá "
                    "lại.").format(no.san_pham, no.ngay, ", ".join(da_duyet))

    tien = 0.0
    for p, dong in phieu:
        for r in dong:
            r.don_gia = gia
            tien += gia * cint(r.so_luong)
        p.flags.ignore_permissions = True
        p.save()

    # Bảng vào hộp đã submit — sửa thẳng DB cho báo cáo khớp phiếu lương. Chỉ đụng
    # dòng 0 đồng của đúng mã đó; dòng khác giữ nguyên.
    if no.bang_vao_hop and frappe.db.exists("SX Bang Vao Hop", no.bang_vao_hop):
        b = frappe.get_doc("SX Bang Vao Hop", no.bang_vao_hop)
        tong = 0.0
        for r in b.dong:
            if (r.san_pham == no.san_pham and (r.cach_lam or "") == (no.cach_lam or "")
                    and not flt(r.don_gia)):
                r.don_gia = gia
                r.thanh_tien = gia * cint(r.so_hop)
                frappe.db.set_value("SX Bang Vao Hop Item", r.name,
                                    {"don_gia": gia, "thanh_tien": r.thanh_tien})
            tong += flt(r.thanh_tien)
        b.db_set("tong_tien", tong, update_modified=False)
        if no.ngay_sx:
            frappe.db.set_value("SX Ngay San Xuat", no.ngay_sx, "tong_luong_sp", tong)

    frappe.db.set_value("SX No Don Gia", no.name, {
        "trang_thai": "Đã cập nhật", "don_gia": gia, "thanh_tien": tien,
        "bang_don_gia": bang_don_gia(no.ngay),
        "xu_ly_boi": frappe.session.user, "xu_ly_luc": frappe.utils.now_datetime(),
    })
    return tien, None


@frappe.whitelist()
def so_no_gia():
    """Nợ đang mở, GOM THEO (mã, cách làm) — khai một giá là trả được nợ của mọi
    ngày đã chốt mã đó. Mã đã có giá lên đầu (áp được ngay), rồi nợ lâu nhất."""
    guard_card("nogia")
    ds = frappe.get_all(
        "SX No Don Gia", filters={"trang_thai": CHO},
        fields=["name", "san_pham", "ten_san_pham", "cach_lam", "so_hop", "so_nguoi",
                "ngay", "ngay_sx"],
        order_by="ngay asc, creation asc")
    hom_nay = getdate(nowdate())
    gia_ngay = {}
    nhom = {}
    for x in ds:
        k = str(getdate(x.ngay))
        if k not in gia_ngay:
            gia_ngay[k] = (bang_don_gia(x.ngay), don_gia_ap_dung(x.ngay))
        ten_bang, bang = gia_ngay[k]
        gia = tra_don_gia(bang, x.san_pham, x.cach_lam)
        g = nhom.setdefault((x.san_pham, x.cach_lam or ""), {
            "san_pham": x.san_pham, "ten": x.ten_san_pham or x.san_pham,
            "cach_lam": x.cach_lam or "", "so_hop": 0, "tien": 0.0, "dong": [],
            "so_co_gia": 0, "bang": [],
        })
        g["so_hop"] += cint(x.so_hop)
        if gia is not None:
            g["so_co_gia"] += 1
            g["tien"] += flt(gia) * cint(x.so_hop)
        if ten_bang and ten_bang not in g["bang"]:
            g["bang"].append(ten_bang)
        g["dong"].append({
            "name": x.name, "ngay": k, "so_hop": cint(x.so_hop),
            "so_nguoi": cint(x.so_nguoi), "gia": gia, "bang": ten_bang,
        })
    ra = []
    for g in nhom.values():
        g["so_ngay"] = (hom_nay - getdate(g["dong"][0]["ngay"])).days
        g["lau"] = g["so_ngay"] > NGAY_NO_LAU
        g["co_gia"] = g["so_co_gia"] > 0
        ra.append(g)
    ra.sort(key=lambda g: (not g["co_gia"], -g["so_ngay"]))
    return {"nhom": ra, "tong_dong": len(ds), "ngay_no_lau": NGAY_NO_LAU}


@frappe.whitelist()
def ap_gia(san_pham, cach_lam=None):
    """Áp giá cho MỌI dòng nợ đang mở của một (mã, cách làm) mà giờ đã tra được giá.

    Dòng nào vẫn chưa có giá (bảng áp dụng ngày đó chưa khai) thì để nguyên; dòng
    nào có phiếu lương đã duyệt thì bỏ qua và nói rõ — sửa lương đã duyệt là quyết
    định của người làm lương. Không dòng nào áp được thì báo lỗi, không im lặng.
    """
    guard_card("nogia")
    cl = cach_lam or ""
    ds = [x for x in frappe.get_all(
        "SX No Don Gia", filters={"san_pham": san_pham, "trang_thai": CHO},
        fields=["name", "san_pham", "cach_lam", "ngay", "ngay_sx", "bang_vao_hop"],
        order_by="ngay asc, creation asc") if (x.cach_lam or "") == cl]
    if not ds:
        frappe.throw(_("{0} không còn khoản nợ đơn giá nào đang mở.").format(san_pham))

    xong, tien, chua_gia, loi = [], 0.0, [], []
    for no in ds:
        gia = tra_don_gia(don_gia_ap_dung(no.ngay), no.san_pham, no.cach_lam)
        if gia is None:
            chua_gia.append(str(no.ngay))
            continue
        t, e = _ap_mot(no, flt(gia))
        if e:
            loi.append(e)
            continue
        xong.append(no.name)
        tien += t
    if not xong:
        ly_do = loi[:]
        if chua_gia:
            ly_do.insert(0, _("Bảng đơn giá áp dụng cho ngày {0} vẫn chưa khai giá {1}{2}.")
                         .format(", ".join(chua_gia), san_pham,
                                 _(" (cách làm {0})").format(cl) if cl else ""))
        frappe.throw("<br>".join(ly_do))
    return {"so_dong": len(xong), "tien": tien, "chua_gia": chua_gia, "loi": loi}


@frappe.whitelist()
def bo_qua_no_gia(name, ly_do=None):
    """Đóng MỘT dòng nợ mà giữ 0 đồng — bắt buộc lý do (hàng mẫu, làm thử…)."""
    guard_card("nogia")
    if not (ly_do or "").strip():
        frappe.throw(_("Bỏ qua khoản nợ thì phải ghi lý do — cuối tháng công nhân hỏi "
                       "vì sao mã này 0 đồng thì phải có câu trả lời."))
    no = frappe.get_doc("SX No Don Gia", name)
    if no.trang_thai != CHO:
        frappe.throw(_("Khoản nợ {0} đã ở trạng thái {1}.").format(name, no.trang_thai))
    _bo_qua(no, ly_do.strip())
    return {"name": name}


def _bo_qua(no, ly_do):
    no.trang_thai = BO_QUA
    no.ly_do = ly_do
    no.xu_ly_boi = frappe.session.user
    no.xu_ly_luc = frappe.utils.now_datetime()
    no.flags.ignore_permissions = True
    no.save()


def chan_duyet_phieu_luong(phieu):
    """Duyệt phiếu lương còn dòng đang nợ giá là khoá cứng khoản nợ ở 0 đồng
    (áp giá không sửa được phiếu đã duyệt). Chặn và nói mã nào, ngày nào."""
    ton = []
    for r in phieu.chi_tiet:
        if flt(r.don_gia):
            continue
        f = {"trang_thai": CHO, "ngay": r.ngay, "san_pham": r.san_pham}
        for x in frappe.get_all("SX No Don Gia", filters=f, fields=["name", "cach_lam"]):
            if (x.cach_lam or "") == (r.cach_lam or ""):
                ton.append("• {0} ngày {1} ({2})".format(r.san_pham, r.ngay, x.name))
    if ton:
        frappe.throw(_("Phiếu lương còn dòng đang NỢ ĐƠN GIÁ (0 đồng):") + "<br>"
                     + "<br>".join(sorted(set(ton))) + "<br><br>"
                     + _("Khai giá rồi Áp giá ở màn Quản lý, hoặc Bỏ qua có lý do, "
                         "trước khi duyệt."))


# ═══════════════════════════ mốc tính nợ (D229) ═══════════════════════════

def moc_tinh_no():
    """Ngày bắt đầu tính nợ đơn giá (SX Settings → no_gia_tu_ngay) — None: tính mọi ngày."""
    v = get_settings().get(TRUONG_MOC)
    return getdate(v) if v else None


def truoc_moc(ngay):
    """Ngày sản xuất TRƯỚC mốc tính nợ: sổ nợ đơn giá của ngày đó đã khoá — đồng bộ không thêm / sửa / huỷ nợ."""
    moc = moc_tinh_no()
    return bool(moc) and getdate(ngay) < moc


def bo_no_truoc(tu_ngay=None, chay=0):
    """bench: Bỏ qua mọi khoản nợ đơn giá ĐANG CHỜ GIÁ của ngày sản xuất trước `tu_ngay` (mặc định đầu tháng này) và
    đặt mốc tính nợ = `tu_ngay` — gọi trần là xem trước:
      bench --site site1.local execute sx.api.nogia.bo_no_truoc                          # xem trước
      bench --site site1.local execute sx.api.nogia.bo_no_truoc --kwargs "{'chay': 1}"   # làm thật
    KHÔNG whitelist: chỉ chạy bằng bench (xoá nợ hàng loạt là quyết định về lương, không phải nút trên màn)."""
    print(bao_cao_bo_no(xu_ly_bo_no(tu_ngay, chay)))


def _ngay_moc(tu_ngay):
    hom_nay = getdate(nowdate())
    if not tu_ngay:
        return hom_nay.replace(day=1)
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(tu_ngay).strip()):
            raise ValueError
        moc = getdate(str(tu_ngay).strip())
        if not moc:                         # '0000-00-00': Frappe trả None thay vì báo lỗi
            raise ValueError
    except Exception:
        frappe.throw(_("tu_ngay phải có dạng YYYY-MM-DD (vd. '2026-11-01'), nhận được: {0}").format(tu_ngay))
    if moc > hom_nay:
        frappe.throw(_("Mốc {0} chưa tới — mốc sau hôm nay là bỏ luôn nợ của những ngày đang làm.").format(
            moc.strftime("%d/%m/%Y")))
    return moc


def xu_ly_bo_no(tu_ngay=None, chay=0):
    """Xem trước (chay=0) / làm thật (chay=1) — trả dict cho báo cáo và test."""
    if not frappe.get_meta("SX Settings").has_field(TRUONG_MOC):
        frappe.throw(_("SX Settings chưa có ô mốc tính nợ — chạy bench --site site1.local migrate trước."))
    moc = _ngay_moc(tu_ngay)
    moc_cu = moc_tinh_no()
    ds = frappe.get_all("SX No Don Gia", filters={"trang_thai": CHO, "ngay": ("<", moc)},
                        fields=["name", "san_pham", "ten_san_pham", "cach_lam", "so_hop", "ngay"],
                        order_by="ngay asc, creation asc")
    con = frappe.db.count("SX No Don Gia", {"trang_thai": CHO, "ngay": (">=", moc)})
    ly_do = LY_DO_MOC.format(moc.strftime("%d/%m/%Y"))
    if cint(chay):
        for x in ds:
            _bo_qua(frappe.get_doc("SX No Don Gia", x.name), ly_do)
        frappe.db.set_single_value("SX Settings", TRUONG_MOC, str(moc))
        frappe.clear_document_cache("SX Settings", "SX Settings")
    nhom = {}
    for x in ds:
        g = nhom.setdefault((x.san_pham, x.cach_lam or ""), {
            "san_pham": x.san_pham, "ten": x.ten_san_pham or x.san_pham, "cach_lam": x.cach_lam or "",
            "so_hop": 0, "ngay": []})
        g["so_hop"] += cint(x.so_hop)
        g["ngay"].append(getdate(x.ngay))
    return {"chay": cint(chay), "moc": moc, "moc_cu": moc_cu, "ly_do": ly_do, "dong": [x.name for x in ds],
            "nhom": sorted(nhom.values(), key=lambda g: (g["ten"], g["cach_lam"])), "con": cint(con)}


def bao_cao_bo_no(kq):
    """Báo cáo tiếng Việt của bo_no_truoc."""
    dmy = lambda d: d.strftime("%d/%m/%Y")
    so = lambda n: f"{n:,}".replace(",", ".")
    moc = dmy(kq["moc"])
    ra = [_("BỎ NỢ ĐƠN GIÁ TRƯỚC {0} — ĐÃ GHI").format(moc) if kq["chay"] else
          _("BỎ NỢ ĐƠN GIÁ TRƯỚC {0} — XEM TRƯỚC, chưa ghi gì (làm thật: thêm --kwargs \"{{'chay': 1}}\")").format(moc),
          _("Mốc tính nợ: {0} (trước đó: {1})").format(moc, dmy(kq["moc_cu"]) if kq["moc_cu"] else _("chưa đặt"))]
    if kq["dong"]:
        ngay = sorted(d for g in kq["nhom"] for d in g["ngay"])
        ra.append(_("{0} khoản nợ đang chờ giá trước mốc — {1} mã, {2} hộp, ngày {3} → {4}:").format(
            len(kq["dong"]), len({g["san_pham"] for g in kq["nhom"]}), so(sum(g["so_hop"] for g in kq["nhom"])),
            dmy(ngay[0]), dmy(ngay[-1])))
        for g in kq["nhom"]:
            ten = g["ten"] if g["ten"] == g["san_pham"] else "{0} ({1})".format(g["ten"], g["san_pham"])
            ds_ngay = ", ".join(d.strftime("%d/%m") for d in g["ngay"][:10]) + (", …" if len(g["ngay"]) > 10 else "")
            ra.append(_("  • {0}{1} — {2} ngày, {3} hộp: {4}").format(
                ten, " · " + g["cach_lam"] if g["cach_lam"] else "", len(g["ngay"]), so(g["so_hop"]), ds_ngay))
        ra.append((_("→ đã chuyển sang Bỏ qua") if kq["chay"] else _("→ sẽ chuyển sang Bỏ qua"))
                  + _(", lý do \"{0}\".").format(kq["ly_do"]))
        ra.append(_("  Lương khoán các dòng này GIỮ 0 đồng trong phiếu lương — muốn trả thì sửa phiếu lương trên Desk."))
    else:
        ra.append(_("Không có khoản nợ nào đang chờ giá trước {0}.").format(moc))
    ra.append(_("Giữ nguyên {0} khoản nợ từ {1} trở đi.").format(kq["con"], moc))
    ra.append((_("Đã đặt mốc") if kq["chay"] else _("Làm thật sẽ đặt mốc"))
              + _(" ở SX Settings: lưu lại / sửa bảng vào hộp của ngày trước {0} KHÔNG sinh nợ đơn giá mới.").format(moc))
    return "\n".join(ra)
