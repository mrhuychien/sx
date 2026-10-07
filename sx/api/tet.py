"""Vào hộp Tết (D122) — một màn, một lần lưu.

═══ VÌ SAO TÁCH RIÊNG ═══
Mùa Tết xưởng thuê thêm người đóng hộp quà theo công nhật. Luồng thường cần ba bước
của ba người: QC chấm từng người ở Ghi hộp → lập phiếu nhập kho → thủ kho duyệt.
Hàng Tết không tính khoán theo người, nên bước chấm từng người là thừa. Ở đây QC Tết
ghi MỘT lần: mã hàng, số (thùng + hộp), HSD in trên hộp. Bấm lưu thì:

  1. sinh PHIẾU NHẬP KHO NHÁP (nguon = "Tết", mỗi dòng có HSD) — thủ kho đếm và
     DUYỆT ở màn Nhập kho như mọi phiếu khác. Duyệt mới vào kho (người lập ≠ người
     duyệt, giữ nguyên nguyên tắc của D56);
  2. ghi SẢN LƯỢNG CÔNG NHẬT vào bảng vào hộp của ngày — để đối chiếu vào hộp /
     nhập kho khớp, và duyệt phiếu không sinh "nợ vào hộp" (D101).

Cả hai trong MỘT giao dịch: hỏng một là không có gì. Xoá phiếu nháp (QC Tết hoặc thủ
kho) thì dòng công nhật đi kèm cũng bị xoá (SXPhieuNhapTP.on_trash → go_cong_nhat).
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime, nowdate

from sx.config.roles import guard_card, is_super, user_roles
from sx.utils import get_settings, items_tp

NGUON = "Tết"
CARD = "vaohoptet"


def _bung(goc):
    """Nhóm + mọi nhóm con (cây nested set)."""
    ra = set(goc)
    for g in goc:
        try:
            lft, rgt = frappe.db.get_value("Item Group", g, ["lft", "rgt"])
            ra.update(frappe.get_all("Item Group", filters={"lft": (">", lft), "rgt": ("<", rgt)},
                                     pluck="name"))
        except Exception:
            pass   # cây hỏng -> vẫn dùng đúng nhóm đã chọn
    return ra


def nhom_tet():
    """Item Group là HÀNG TẾT, đã bung nhánh con. SX Settings → "Nhóm Hàng Tết";
    để trống thì tự nhận nhóm có tên chứa "Tết" (đa số xưởng đặt sẵn "Hàng Tết")."""
    goc = [r.item_group for r in (get_settings().get("nhom_tet") or []) if r.item_group]
    if not goc:
        goc = frappe.get_all("Item Group", filters={"item_group_name": ("like", "%Tết%")},
                             pluck="name")
    return _bung(goc) if goc else set()


def hang_tet(fields):
    """Thành phẩm Tết. Chưa có nhóm Tết nào thì trả MỌI thành phẩm + cờ để màn hình
    nhắc cấu hình — thà thấy dư còn hơn QC Tết đứng nhìn danh sách rỗng."""
    nhom = nhom_tet()
    ds = items_tp(list(dict.fromkeys(list(fields) + ["item_group"])))
    if not nhom:
        return ds, False
    return [i for i in ds if i.get("item_group") in nhom], True


@frappe.whitelist()
def danh_muc():
    """Hàng Tết chọn được: tên, ĐVT kho, các đơn vị đếm (thùng/hộp), số ngày hạn
    dùng (điền sẵn HSD) + bảng mã vạch → mã hàng để quét."""
    guard_card(CARD)
    from sx.api.khotp import _nap_uom, _uom_cua
    from sx.api.portal import _ma_quet

    ds, co_nhom = hang_tet(["name", "item_name", "stock_uom", "shelf_life_in_days"])
    _nap_uom([i.name for i in ds])
    return {
        "rows": [{"item": i.name, "ten": i.item_name or i.name, "dvt": i.stock_uom or "",
                  "uoms": _uom_cua(i.name, i.stock_uom),
                  "han_dung": cint(i.get("shelf_life_in_days"))} for i in ds],
        "ma_quet": {"sp": _ma_quet([])["sp"]},   # đủ mọi TP: quét nhầm mã thường thì báo rõ
        "chua_co_nhom": not co_nhom,
    }


def _phieu_ngay(ngay):
    """Phiếu ngày SX của `ngay` (tạo nháp nếu chưa có)."""
    ten = frappe.db.get_value("SX Ngay San Xuat", {"ngay": ngay, "docstatus": ("<", 2)}, "name")
    if ten:
        return ten
    doc = frappe.new_doc("SX Ngay San Xuat")
    doc.ngay = ngay
    doc.flags.ignore_permissions = True
    doc.insert()
    return doc.name


@frappe.whitelist()
def luu(rows, ngay=None, ghi_chu=None):
    """Lưu một lần: phiếu nhập kho NHÁP + dòng công nhật. Trả tóm tắt phiếu.

    `rows` = [{item, so, chi_tiet?, hsd?}] — `so` theo ĐVT kho (hộp), `chi_tiet` là
    cách chia thùng/hộp (để thủ kho đếm theo đúng cách xếp), `hsd` để trống thì lấy
    ngày + Shelf Life của mã; mã chưa khai Shelf Life thì bắt buộc nhập.
    """
    guard_card(CARD)
    from sx.api.khotp import _ghi_json
    from sx.api.portal import _chan_neu_chot
    from sx.sx.doctype.sx_phieu_nhap_tp.sx_phieu_nhap_tp import hsd_goi_y

    settings = get_settings()
    if not settings.get("kho_tp"):
        frappe.throw(_("SX Settings chưa cấu hình Kho TP."))
    ngay = getdate(ngay or nowdate())
    rows = json.loads(rows) if isinstance(rows, str) else (rows or [])
    tp = {i.name: i for i in hang_tet(["name", "item_name"])[0]}

    dong, loi = [], []
    for i, r in enumerate(rows, 1):
        item = r.get("item")
        so = flt(r.get("so"))
        if not item:
            continue
        if item not in tp:
            loi.append(_("Dòng {0}: {1} không phải hàng Tết.").format(i, item))
            continue
        ten = tp[item].item_name or item
        if so <= 0:
            continue
        if so != int(so):
            loi.append(_("Dòng {0} ({1}): số hộp phải là số nguyên.").format(i, ten))
            continue
        hsd = r.get("hsd") or hsd_goi_y(item, ngay)
        if not hsd:
            loi.append(_("Dòng {0} ({1}): chưa có HSD — nhập theo HSD in trên hộp.").format(i, ten))
            continue
        if getdate(hsd) <= ngay:
            loi.append(_("Dòng {0} ({1}): HSD phải sau ngày nhập.").format(i, ten))
            continue
        dong.append({"item": item, "ten": ten, "so": int(so), "ct": _ghi_json(r.get("chi_tiet")),
                     "hsd": str(getdate(hsd))})
    if loi:
        frappe.throw("<br>".join(loi), title=_("Chưa lưu được"))
    if not dong:
        frappe.throw(_("Chưa có dòng nào có số lượng."))

    # 1. Công nhật vào bảng vào hộp của ngày
    ngay_sx = _phieu_ngay(ngay)
    _chan_neu_chot(ngay_sx, "vaohop", _("ghi công nhật Tết"))
    ten_bang = frappe.db.get_value("SX Bang Vao Hop", {"ngay_sx": ngay_sx, "docstatus": 0}, "name")
    bang = frappe.get_doc("SX Bang Vao Hop", ten_bang) if ten_bang else frappe.new_doc("SX Bang Vao Hop")
    bang.ngay_sx = ngay_sx
    u, luc = frappe.session.user, now_datetime()
    moi = [bang.append("dong", {"cong_nhat": 1, "nhan_vien": None, "san_pham": d["item"],
                                "so_hop": d["so"], "nguoi_ghi": u, "ghi_luc": luc})
           for d in dong]
    bang.flags.ignore_permissions = True
    bang.save()

    # 2. Phiếu nhập kho NHÁP — thủ kho duyệt ở màn Nhập kho
    p = frappe.new_doc("SX Phieu Nhap TP")
    p.ngay = ngay
    p.kho_dich = settings.kho_tp
    p.nguoi_lap = u
    p.nguon = NGUON
    p.ghi_chu = ghi_chu or _("Vào hộp Tết — công nhật đã ghi ở bảng {0}.").format(bang.name)
    p.vao_hop_tet = json.dumps([{"bang": bang.name, "dong": r.name} for r in moi])
    for d in dong:
        p.append("dong", {"item": d["item"], "so_lap": d["so"], "so_dem": d["so"],
                          "lap_uom": d["ct"], "dem_uom": d["ct"], "hsd": d["hsd"]})
    p.flags.ignore_permissions = True
    p.insert()
    return {"phieu": p.name, "bang": bang.name, "tong": sum(d["so"] for d in dong),
            "so_dong": len(dong)}


def go_cong_nhat(phieu):
    """Xoá dòng công nhật sinh cùng phiếu Tết (phiếu nháp bị xoá). Bảng đã chốt Vào
    hộp thì giữ nguyên — đã thành lương / số liệu chốt, không lặng lẽ sửa."""
    try:
        ds = json.loads(phieu.get("vao_hop_tet") or "[]")
    except (ValueError, TypeError):
        return
    theo_bang = {}
    for x in ds:
        if x.get("bang") and x.get("dong"):
            theo_bang.setdefault(x["bang"], set()).add(x["dong"])
    for ten, dong in theo_bang.items():
        if not frappe.db.exists("SX Bang Vao Hop", {"name": ten, "docstatus": 0}):
            continue
        b = frappe.get_doc("SX Bang Vao Hop", ten)
        b.set("dong", [r for r in b.dong if r.name not in dong])
        b.flags.ignore_permissions = True
        if not b.dong and not b.get("an_ca"):
            b.delete(ignore_permissions=True)     # như D106: bảng rỗng thì xoá hẳn
        else:
            b.save()


def _cua_toi(nguoi_lap):
    return is_super(user_roles()) or nguoi_lap == frappe.session.user


@frappe.whitelist()
def gan_day(limit=20):
    """Phiếu Tết gần đây của người này (quản lý: của mọi người) + trạng thái duyệt."""
    guard_card(CARD)
    loc = {"nguon": NGUON}
    if not is_super(user_roles()):
        loc["nguoi_lap"] = frappe.session.user
    ds = frappe.get_all("SX Phieu Nhap TP", filters=loc,
                        fields=["name", "ngay", "docstatus", "tong_dem", "nguoi_lap",
                                "nguoi_duyet", "trang_thai"],
                        order_by="creation desc", limit=cint(limit) or 20)
    if not ds:
        return []
    dong = {}
    for r in frappe.get_all("SX Phieu Nhap TP Item",
                            filters={"parent": ("in", [x.name for x in ds]),
                                     "parenttype": "SX Phieu Nhap TP"},
                            fields=["parent", "item", "ten", "so_dem", "hsd"], order_by="idx"):
        dong.setdefault(r.parent, []).append({"ten": r.ten or r.item, "so": flt(r.so_dem),
                                              "hsd": str(r.hsd) if r.hsd else None})
    return [{"name": x.name, "ngay": str(x.ngay), "docstatus": x.docstatus,
             "trang_thai": {0: _("Chờ thủ kho duyệt"), 1: _("Đã nhập kho"),
                            2: _("Đã huỷ")}.get(x.docstatus),
             "tong": flt(x.tong_dem), "nguoi_duyet": x.nguoi_duyet,
             "duoc_xoa": x.docstatus == 0 and _cua_toi(x.nguoi_lap),
             "dong": dong.get(x.name, [])} for x in ds]


@frappe.whitelist()
def xoa(name):
    """Xoá phiếu Tết NHÁP (ghi nhầm) — kéo theo dòng công nhật của nó."""
    guard_card(CARD)
    p = frappe.get_doc("SX Phieu Nhap TP", name)
    if p.get("nguon") != NGUON:
        frappe.throw(_("Phiếu {0} không phải phiếu Tết.").format(name))
    if p.docstatus != 0:
        frappe.throw(_("Phiếu {0} thủ kho đã duyệt — nhờ thủ kho huỷ ở màn Nhập kho.")
                     .format(name))
    if not _cua_toi(p.nguoi_lap):
        frappe.throw(_("Chỉ người lập phiếu (hoặc quản lý) mới xoá được."), frappe.PermissionError)
    p.delete(ignore_permissions=True)
    return {"ok": 1}
