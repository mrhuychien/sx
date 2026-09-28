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
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from sx.config.roles import guard_card
from sx.utils import bang_don_gia, don_gia_ap_dung, tra_don_gia

CHO = "Chờ giá"
NGAY_NO_LAU = 7


def gom_thieu_gia(dong, bang_gia):
    """{(san_pham, cach_lam): {"so_hop", "nguoi"}} của các dòng KHÔNG tra được giá.

    Hàm thuần: tra bằng đúng hàm mà bảng vào hộp dùng lúc tính tiền, nên "thiếu giá"
    ở đây và "tính 0 đồng" ở bảng không bao giờ lệch nhau.
    """
    ra = {}
    for r in dong:
        if not r.get("san_pham") or cint(r.get("so_hop")) <= 0:
            continue
        if tra_don_gia(bang_gia, r["san_pham"], r.get("cach_lam")) is not None:
            continue
        g = ra.setdefault((r["san_pham"], r.get("cach_lam") or ""),
                          {"so_hop": 0, "nguoi": set()})
        g["so_hop"] += cint(r["so_hop"])
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
    no.trang_thai = "Bỏ qua"
    no.ly_do = ly_do.strip()
    no.xu_ly_boi = frappe.session.user
    no.xu_ly_luc = frappe.utils.now_datetime()
    no.flags.ignore_permissions = True
    no.save()
    return {"name": name}


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
