"""API màn Khiếu nại (QC → Sự cố → Khiếu nại KH) — sổ BM.11.01 trên Issue (W13, D135).

Luật nghiệp vụ (tìm lô theo HSD, ai được đóng, đóng phải đủ gì) nằm ở sx/qc/khieu_nai.py
trong `validate` của Issue — chặn cả đường Desk. Ở đây chỉ đọc / ghi cho màn hình.

Ai dùng: người vào được module QC (QC, Ban ISO, QLSX, quản trị). Issue ghi bằng
`ignore_permissions` SAU khi đã chốt quyền ở đây: role QC không có quyền Issue chuẩn của
ERPNext (Support Team), và cấp nguyên role đó là mở cả phân hệ hỗ trợ cho QC.
"""

import html
import json
import re

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, nowdate

from sx.api.qc import _guard_qc, _khoang, _nhan_lo
from sx.qc.khieu_nai import DONG, MO
from sx.qc.nguong import nguong
from sx.qc.quyen import duoc_dong_su_co

PHAN_LOAI = ("Cảm quan (mùi, vị, màu)", "Dị vật", "Vi sinh / mốc / hỏng", "Dị ứng",
             "Bao bì / nhãn", "Khối lượng / số lượng", "Giao hàng / dịch vụ", "Khác")
KENH = ("Điện thoại", "Zalo / tin nhắn", "Trực tiếp", "Đại lý / nhà phân phối", "Email", "Khác")
KET_LUAN = ("Có lỗi của nhà máy", "Không phải lỗi của nhà máy", "Chưa xác định được")
# Phân loại mà mối nguy chạm tới người ăn: lập phiếu sự cố ngay, mức Cao.
NGUY_HIEM = ("Dị vật", "Vi sinh / mốc / hỏng", "Dị ứng")

TRUONG = ["name", "subject", "status", "opening_date", "customer", "customer_name",
          "custom_lien_he_kn", "custom_kenh_kn", "custom_san_pham", "custom_hsd", "custom_lo",
          "custom_so_luong_kn", "custom_phan_loai_kn", "custom_muc_do_kn", "custom_ket_luan_kn",
          "custom_xu_ly_kh", "custom_su_co", "custom_dong_boi_kn", "custom_dong_luc_kn",
          "description", "creation"]

# Ô sửa được từ màn hình (key payload -> field Issue)
SUA = {"lien_he": "custom_lien_he_kn", "kenh": "custom_kenh_kn", "san_pham": "custom_san_pham",
       "hsd": "custom_hsd", "so_luong": "custom_so_luong_kn", "phan_loai": "custom_phan_loai_kn",
       "muc_do": "custom_muc_do_kn", "ket_luan": "custom_ket_luan_kn", "xu_ly": "custom_xu_ly_kh",
       "khach": "customer"}


def _html(t):
    """Chữ người gõ → HTML an toàn cho ô Text Editor của Issue."""
    return html.escape((t or "").strip()).replace("\n", "<br>")


def _chu(h):
    """HTML của ô Text Editor → chữ thường (màn hình, bản in)."""
    t = re.sub(r"<br\s*/?>|</p>|</div>", "\n", h or "", flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", t)).strip()


def _ten_sp(items):
    if not items:
        return {}
    return {x.name: x.item_name or x.name for x in frappe.get_all(
        "Item", filters={"name": ("in", list(items))}, fields=["name", "item_name"])}


def _dong(x, ten_sp, han):
    hom_nay = getdate(nowdate())
    mo = x.status in MO
    return {
        "name": x.name, "status": x.status, "mo": mo,
        "ngay": str(x.opening_date or str(x.creation)[:10]),
        "khach": x.customer_name or x.customer or "", "customer": x.customer or "",
        "lien_he": x.custom_lien_he_kn or "", "kenh": x.custom_kenh_kn or "",
        "san_pham": x.custom_san_pham or "", "ten_sp": ten_sp.get(x.custom_san_pham, ""),
        "hsd": str(x.custom_hsd) if x.custom_hsd else "", "lo": x.custom_lo or "",
        "nhan_lo": _nhan_lo(x.custom_hsd, x.custom_lo) if (x.custom_hsd or x.custom_lo) else "",
        "so_luong": x.custom_so_luong_kn or "", "phan_loai": x.custom_phan_loai_kn or "",
        "muc_do": x.custom_muc_do_kn or "Thường", "ket_luan": x.custom_ket_luan_kn or "",
        "xu_ly": x.custom_xu_ly_kh or "", "su_co": x.custom_su_co or "",
        "mo_ta": _chu(x.description), "tieu_de": x.subject or "",
        "dong_boi": x.custom_dong_boi_kn or "",
        "dong_luc": str(x.custom_dong_luc_kn or "")[:16],
        "qua_han": bool(mo and hom_nay > add_days(getdate(x.opening_date or nowdate()), han)),
    }


@frappe.whitelist()
def list_khieu_nai(trang_thai="Mở", tu=None, den=None):
    """Khiếu nại đang mở (mọi ngày — cái đang mở thì không được trôi khỏi màn hình),
    hoặc đã đóng trong khoảng ngày. Kèm danh mục cho form và cờ quyền đóng."""
    _guard_qc()
    loc = {"custom_khieu_nai": 1}
    if trang_thai == "Đóng":
        tu, den = _khoang(tu, den)
        loc.update(status=("in", list(DONG)), opening_date=("between", [tu, den]))
    else:
        loc["status"] = ("in", list(MO))
    ds = frappe.get_all("Issue", filters=loc, fields=TRUONG,
                        order_by="opening_date desc, creation desc", limit=300)
    ten = _ten_sp({x.custom_san_pham for x in ds if x.custom_san_pham})
    han = cint(nguong()["su_co_qua_han_ngay"])
    return {"danh_sach": [_dong(x, ten, han) for x in ds],
            "so_mo": frappe.db.count("Issue", {"custom_khieu_nai": 1, "status": ("in", list(MO))}),
            "duoc_dong": duoc_dong_su_co(),
            "phan_loai": list(PHAN_LOAI), "kenh": list(KENH), "ket_luan": list(KET_LUAN),
            "nguy_hiem": list(NGUY_HIEM)}


@frappe.whitelist()
def tim_khach(q):
    """Khách hàng theo mã / tên — ô chọn khách của form khiếu nại."""
    _guard_qc()
    q = (q or "").strip()
    if len(q) < 2:
        return []
    k = f"%{q}%"
    return [{"customer": x.name, "ten": x.customer_name or x.name} for x in frappe.get_all(
        "Customer", filters={"disabled": 0},
        or_filters={"name": ("like", k), "customer_name": ("like", k)},
        fields=["name", "customer_name"], order_by="customer_name", limit=20)]


def _tieu_de(p, ten_sp):
    ai = (p.get("khach_ten") or p.get("lien_he") or p.get("khach") or "").strip()
    t = _("Khiếu nại {0}").format(ten_sp or p.get("san_pham") or "").strip()
    return (f"{t} — {ai}" if ai else t)[:140]


def _lap_su_co(kn):
    """Phiếu sự cố (BM.08.02) để điều tra một khiếu nại: nguồn Khiếu nại, gắn lô."""
    sc = frappe.get_doc({
        "doctype": "SX Su Co", "ngay": kn.opening_date or nowdate(), "nguon": "Khiếu nại",
        "loai": "Dị ứng" if kn.get("custom_phan_loai_kn") == "Dị ứng" else "Khác",
        "muc_do": kn.get("custom_muc_do_kn") or "Thường",
        "mo_ta": _("Khiếu nại {0}: {1}").format(kn.name, _chu(kn.description) or kn.subject)[:1000],
        "so_luong": kn.get("custom_so_luong_kn") or "", "trang_thai": "Mở",
        "khoa_cu": f"Issue#{kn.name}",
    })
    if kn.get("custom_lo"):
        sc.append("ds_lo", {"batch": kn.custom_lo, "so_luong": kn.get("custom_so_luong_kn") or ""})
    # Người ghi khiếu nại có thể không có quyền tạo phiếu sự cố trên Desk, nhưng khiếu
    # nại cần điều tra thì phiếu PHẢI ra — như vòng kiểm / tiếp nhận NL sinh phiếu.
    sc.insert(ignore_permissions=True)
    kn.db_set("custom_su_co", sc.name, update_modified=False)
    return sc.name


@frappe.whitelist()
def them_khieu_nai(payload):
    """Ghi một khiếu nại. `lap_su_co` = 1 → lập luôn phiếu sự cố điều tra (màn hình tự
    bật khi phân loại nguy hiểm / mức Cao). Trả {name, su_co, lo}."""
    _guard_qc()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    if not (p.get("mo_ta") or "").strip():
        frappe.throw(_("Chưa ghi nội dung khiếu nại."))
    if not (p.get("khach") or p.get("lien_he") or "").strip():
        frappe.throw(_("Chưa ghi khách hàng / người khiếu nại."))
    if p.get("phan_loai") and p["phan_loai"] not in PHAN_LOAI:
        frappe.throw(_("Phân loại không hợp lệ: {0}").format(p["phan_loai"]))
    if p.get("khach") and not frappe.db.exists("Customer", p["khach"]):
        frappe.throw(_("Không có khách hàng {0} trong danh mục — ghi vào ô Người khiếu nại / "
                       "liên hệ.").format(p["khach"]))
    ten_sp = _ten_sp([p["san_pham"]]).get(p["san_pham"]) if p.get("san_pham") else ""
    muc_do = "Cao" if (p.get("muc_do") == "Cao" or p.get("phan_loai") in NGUY_HIEM) else "Thường"
    doc = frappe.get_doc({
        "doctype": "Issue", "subject": _tieu_de(p, ten_sp), "status": "Open",
        "opening_date": getdate(p.get("ngay") or nowdate()),
        "description": _html(p.get("mo_ta")),
        "custom_khieu_nai": 1, "custom_muc_do_kn": muc_do,
        **{SUA[k]: v for k, v in p.items() if k in SUA and k not in ("muc_do", "ket_luan", "xu_ly")
           and v not in (None, "")},
    })
    if p.get("khach"):
        # fetch_from của Issue chỉ chạy khi lưu; điền luôn để sổ in đúng tên khách.
        doc.customer_name = frappe.db.get_value("Customer", p["khach"], "customer_name") or p["khach"]
    doc.insert(ignore_permissions=True)
    su_co = None
    if cint(p.get("lap_su_co")) or muc_do == "Cao":
        su_co = _lap_su_co(doc)
    return {"name": doc.name, "su_co": su_co, "lo": doc.get("custom_lo") or ""}


@frappe.whitelist()
def sua_khieu_nai(name, payload):
    """Ghi kết luận / xử lý / sửa thông tin. Không đổi trạng thái ở đây."""
    _guard_qc()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    doc = _lay(name)
    if doc.status in DONG and not duoc_dong_su_co():
        frappe.throw(_("Khiếu nại đã đóng — nhờ Ban ISO mở lại nếu cần sửa."),
                     frappe.PermissionError)
    for k, f in SUA.items():
        if k in p:
            doc.set(f, p[k] or None)
    if "mo_ta" in p and (p["mo_ta"] or "").strip():
        doc.description = _html(p["mo_ta"])
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "lo": doc.get("custom_lo") or ""}


@frappe.whitelist()
def lap_su_co_khieu_nai(name):
    """Lập phiếu sự cố điều tra cho khiếu nại chưa có phiếu."""
    _guard_qc()
    doc = _lay(name)
    if doc.get("custom_su_co"):
        return {"su_co": doc.custom_su_co}
    return {"su_co": _lap_su_co(doc)}


@frappe.whitelist()
def dong_khieu_nai(name, ket_luan=None, xu_ly=None):
    """Đóng — Ban ISO / người được giao; phải có kết luận + xử lý với khách (validate)."""
    _guard_qc()
    doc = _lay(name)
    if ket_luan:
        doc.custom_ket_luan_kn = ket_luan
    if xu_ly:
        doc.custom_xu_ly_kh = xu_ly
    doc.status = "Closed"
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def mo_lai_khieu_nai(name, ly_do=None):
    _guard_qc()
    doc = _lay(name)
    doc.status = "Open"
    if (ly_do or "").strip():
        doc.custom_xu_ly_kh = ((doc.get("custom_xu_ly_kh") or "") + f"\n[Mở lại] {ly_do.strip()}").strip()
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}


def _lay(name):
    doc = frappe.get_doc("Issue", name)
    if not cint(doc.get("custom_khieu_nai")):
        frappe.throw(_("{0} không phải khiếu nại khách hàng.").format(name))
    return doc


@frappe.whitelist()
def in_so_khieu_nai(tu=None, den=None):
    """HTML A4 ngang — sổ khiếu nại BM.11.01 của một khoảng ngày (theo ngày nhận)."""
    _guard_qc()
    tu, den = _khoang(tu, den)
    ds = frappe.get_all("Issue", filters={"custom_khieu_nai": 1,
                                          "opening_date": ("between", [tu, den])},
                        fields=TRUONG, order_by="opening_date asc, creation asc")
    ten = _ten_sp({x.custom_san_pham for x in ds if x.custom_san_pham})
    han = cint(nguong()["su_co_qua_han_ngay"])
    return frappe.render_template("sx/qc/so_khieu_nai.html", {
        "tu": str(tu), "den": str(den), "ds": [_dong(x, ten, han) for x in ds]})


def theo_lo(batch):
    """Khiếu nại của một lô — cho thẻ lô trong Truy xuất. Lỗi (chưa migrate) → []."""
    try:
        b = frappe.db.get_value("Batch", batch, ["item", "expiry_date"], as_dict=True) or {}
        ds = frappe.get_all("Issue", filters={"custom_khieu_nai": 1, "custom_lo": batch},
                            fields=["name", "opening_date", "status", "custom_phan_loai_kn",
                                    "custom_muc_do_kn", "subject", "description"],
                            order_by="opening_date desc", limit=20)
        if b.get("item") and b.get("expiry_date"):
            co = {x.name for x in ds}
            ds += [x for x in frappe.get_all(
                "Issue", filters={"custom_khieu_nai": 1, "custom_san_pham": b["item"],
                                  "custom_hsd": b["expiry_date"]},
                fields=["name", "opening_date", "status", "custom_phan_loai_kn",
                        "custom_muc_do_kn", "subject", "description"], limit=20) if x.name not in co]
    except Exception:
        return []
    return [{"name": x.name, "ngay": str(x.opening_date or ""), "mo": x.status in MO,
             "trang_thai": _("Mở") if x.status in MO else _("Đóng"),
             "phan_loai": x.custom_phan_loai_kn or "", "muc_do": x.custom_muc_do_kn or "",
             "mo_ta": (_chu(x.description) or x.subject or "")[:160]} for x in ds]
