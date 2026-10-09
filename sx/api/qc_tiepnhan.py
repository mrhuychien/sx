"""Màn "Tiếp nhận NL" của QC trên điện thoại — BM.07.03 + kiểm xe BM.09.01 (W33, D160).

QC chế biến (vai SX QC) không vào Desk, mà phần QC của tiếp nhận nằm trên PHIẾU NHẬP MUA
(Purchase Receipt, W10) / hoá đơn mua có trừ kho (đường cũ trước D138). Màn này ghi ĐÚNG các ô
custom có sẵn của dòng hàng (lô NCC, CQ/CO, COA vi sinh, aflatoxin, độ ẩm, cảm quan, kết luận) và
đầu phiếu (người kiểm, ghi chú QC, kiểm xe) — không đụng số lượng, đơn giá, kho. Lưu bằng
doc.save() nên các hook validate chạy y như trên Desk (kiem_xe → tiep_nhan → ncc): xe không đạt ép
Cách ly, thiếu COA / giấy tờ / độ ẩm vượt ngưỡng ép Cách ly, lô Không đạt / Cách ly vào kho cách
ly, "Đạt" mà cảm quan Không đạt bị chặn. Lời cảnh báo của các hook trả về cho màn hình hiện ra
(cổng chỉ đọc thông báo của server khi có lỗi).

Chỉ phiếu NHÁP: duyệt (submit) là việc của thủ kho — on_submit đòi đủ kết luận, sinh phiếu sự
cố. Ảnh (hàng, giấy tờ lô, xe) ghi được cả sau khi duyệt: ảnh là bằng chứng, không phải số liệu.
Cách tạm cho site chưa cập nhật: gán thêm role Stock User cho tài khoản QC để vào Desk (README).
"""

import base64
import binascii
import json
import re

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

from sx.api.qc import ANH_BYTE_TOI_DA, ANH_MOT_LAN, GHI_DUOC, _guard_ghi, _guard_qc, _kieu_anh, _roles, _sieu
from sx.qc import kiem_xe as KX
from sx.qc import ncc as NCC
from sx.qc import tiep_nhan as TN
from sx.qc.nguong import nguong

SO_NGAY = 14
LOAI = ("Purchase Receipt", "Purchase Invoice")
ANH_TOI_DA = 8
# Ô QC của dòng hàng = đúng custom field có sẵn (sx/fixtures/custom_field.json — test đối chiếu).
#   None = chữ tự do · "so" = số · tuple = lựa chọn của ô Select
O_DONG = {
    "custom_ncc_lo": None,
    "custom_co_cq": ("", "Có", "Không"),
    "custom_coa_vi_sinh": ("", "Có", "Không", "Không yêu cầu"),
    "custom_aflatoxin": ("", "Có", "Không", "Không yêu cầu"),
    "custom_do_am": "so",
    "custom_cam_quan_dat": ("", TN.DAT, TN.KHONG_DAT),
    "custom_ket_luan": ("", TN.DAT, TN.KHONG_DAT, TN.CACH_LY),
}
XE_CHU = ("custom_xe_bien_so", "custom_xe_don_vi", "custom_xe_tai_xe", "custom_xe_ghi_chu")
# Ô lựa chọn Đạt / Không đạt của mọi phiên bản bộ mục (W34, D165) — mỗi phiếu chỉ ghi các mục của phiên bản nó.
XE_CHON = tuple(f for pb in sorted(KX.MUC_THEO_PB) for f, _c, _y in KX.MUC_THEO_PB[pb]) + ("custom_xe_ket_luan",)


def _duoc_ghi():
    return bool(_sieu() or _roles() & GHI_DUOC)


def _lay(doctype, name, ghi=False):
    if doctype not in LOAI:
        frappe.throw(_("Chỉ kiểm tiếp nhận trên phiếu nhập mua / hoá đơn mua có trừ kho."))
    doc = frappe.get_doc(doctype, name)
    if cint(doc.get("is_return")) or (doctype == "Purchase Invoice" and not cint(doc.get("update_stock"))):
        frappe.throw(_("{0} không nhập kho hàng mua — không kiểm tiếp nhận ở đây.").format(name))
    if doc.docstatus == 2:
        frappe.throw(_("{0} đã huỷ.").format(name))
    if ghi and doc.docstatus != 0:
        frappe.throw(_("{0} đã duyệt — phần QC đã khoá. Cần sửa thì thủ kho huỷ phiếu rồi lập lại.")
                     .format(name))
    return doc


def _ncc(supplier, nho):
    if supplier not in nho:
        nho[supplier] = NCC.thong_tin(supplier) or {}
    return nho[supplier]


@frappe.whitelist()
def ds_tiep_nhan():
    """Phiếu nhập mua NHÁP 14 ngày gần nhất (gồm hoá đơn mua có trừ kho): phiếu chờ kiểm trước, rồi
    phiếu đã kiểm đủ đang chờ thủ kho duyệt. Đủ = có người kiểm + mọi dòng có kết luận + đã kiểm xe
    (khi phải kiểm): luật W10 tự ép Cách ly ngay lúc kho lập phiếu (thiếu aflatoxin…), nên "dòng có
    kết luận" chưa có nghĩa là QC đã nhìn lô đó. NCC dịch vụ không kiểm tiếp nhận — không hiện."""
    _guard_qc()
    tu = add_days(getdate(nowdate()), -(SO_NGAY - 1))
    ds, nho = [], {}
    for dt in LOAI:
        loc = {"docstatus": 0, "is_return": 0, "posting_date": (">=", tu)}
        truong = ["name", "supplier", "supplier_name", "posting_date", "custom_nguoi_kiem"]
        if dt == "Purchase Invoice":
            loc["update_stock"] = 1
        else:
            truong += ["custom_xe_ket_luan", "custom_xe_bien_so"]
        try:
            phieu = frappe.get_all(dt, filters=loc, fields=truong, order_by="posting_date desc", limit=200)
        except Exception:          # site chưa có field QC (chưa migrate W10 / W14)
            continue
        if not phieu:
            continue
        dem = {}
        for r in frappe.get_all(f"{dt} Item", filters={"parenttype": dt, "parent": ("in", [p.name for p in phieu])},
                                fields=["parent", "custom_ket_luan"]):
            x = dem.setdefault(r.parent, [0, 0])
            x[0] += 1
            x[1] += 1 if r.custom_ket_luan else 0
        for p in phieu:
            ncc = _ncc(p.supplier, nho)
            if ncc.get("loai") == NCC.DV:
                continue
            n, kl = dem.get(p.name, (0, 0))
            xe = dt == "Purchase Receipt" and ncc.get("loai") in KX.NCC_CAN
            ds.append({"doctype": dt, "name": p.name, "ncc": p.supplier_name or p.supplier,
                       "loai_ncc": ncc.get("loai") or "", "ngay": str(p.posting_date or ""), "so_dong": n,
                       "da_kl": kl, "xe_can": xe, "xe_kl": p.get("custom_xe_ket_luan") or "",
                       "bien_so": p.get("custom_xe_bien_so") or "", "nguoi_kiem": p.get("custom_nguoi_kiem") or "",
                       "xong": bool(n and kl == n and p.get("custom_nguoi_kiem")
                                    and (not xe or p.get("custom_xe_ket_luan")))})
    ds.sort(key=lambda x: (x["xong"], -getdate(x["ngay"]).toordinal() if x["ngay"] else 0))
    return {"ds": ds, "duoc_ghi": _duoc_ghi(), "so_ngay": SO_NGAY}


def _anh(doc):
    try:
        return frappe.get_all("File", filters={"attached_to_doctype": doc.doctype, "attached_to_name": doc.name},
                              fields=["name", "file_name", "file_url"], order_by="creation asc")
    except Exception:
        return []


def _dict(doc, bao=None):
    ncc = NCC.thong_tin(doc.get("supplier")) or {}
    ng = nguong()
    pkn = NCC.pkn_con_han(ncc.get("ho_so"), doc.get("posting_date") or nowdate())
    can_coa, can_af = set(ng.get("nhom_can_coa") or ()), set(ng.get("nhom_can_aflatoxin") or ())
    dong = []
    for r in doc.get("items") or []:
        nhom = set(TN._nhom_va_cha(TN._item_group(r.item_code), TN._tra_cha)) if r.item_code else set()
        d = {"name": r.name, "idx": r.idx, "item_code": r.item_code, "item_name": r.item_name or r.item_code,
             "qty": flt(r.qty, 3), "uom": r.get("uom") or r.get("stock_uom") or "", "kho": r.get("warehouse") or "",
             "batch_no": r.get("batch_no") or "", "giay_to": r.get("custom_giay_to") or "",
             "can_coa": bool(nhom & can_coa), "can_aflatoxin": bool(nhom & can_af)}
        for f, kieu in O_DONG.items():
            d[f] = (flt(r.get(f)) or None) if kieu == "so" else (r.get(f) or "")
        dong.append(d)
    xe = None
    if doc.doctype == "Purchase Receipt":
        muc = KX.muc(doc)
        xe = {"ap_dung": KX.ap_dung(doc), "pb": KX.phien_ban(doc),
              "muc": [{"f": f, "nhan": c, "yc": y} for f, c, y in muc],
              "nguoi_kiem": doc.get("custom_xe_nguoi_kiem") or "", "qc_kiem": doc.get("custom_xe_qc_kiem") or "",
              "qc_luc": str(doc.get("custom_xe_qc_luc") or "")[:16]}
        for f in XE_CHU + tuple(f for f, _c, _y in muc) + ("custom_xe_ket_luan",):
            xe[f] = doc.get(f) or ""
    return {
        "doctype": doc.doctype, "name": doc.name, "docstatus": doc.docstatus,
        "ngay": str(doc.get("posting_date") or ""), "ncc": doc.get("supplier_name") or doc.get("supplier"),
        "ncc_loai": ncc.get("loai") or "", "ncc_nguon": ncc.get("nguon") or "", "ncc_duyet": bool(ncc.get("duyet")),
        "pkn": ({"so_hieu": pkn.get("so_hieu") or "", "het_han": str(pkn.get("het_han") or "")} if pkn else None),
        "nguoi_kiem": doc.get("custom_nguoi_kiem") or "", "ghi_chu_qc": doc.get("custom_ghi_chu_qc") or "",
        "xe": xe, "dong": dong, "so_anh": len(_anh(doc)), "do_am_toi_da": flt(ng.get("do_am_toi_da")) or None,
        "lua_chon": {f: list(k[1:]) for f, k in O_DONG.items() if isinstance(k, tuple)},
        "sua": doc.docstatus == 0 and _duoc_ghi(), "them_anh": doc.docstatus < 2 and _duoc_ghi(),
        "bao": bao or [],
    }


@frappe.whitelist()
def xem_phieu(doctype, name):
    _guard_qc()
    return _dict(_lay(doctype, name))


def _chuan(f, kieu, v, r):
    if kieu is None:
        return str(v or "").strip()[:140] or None
    if kieu == "so":
        if v in (None, ""):
            return None
        try:
            so = float(str(v).replace(",", "."))
        except ValueError:
            so = -1
        if not 0 <= so <= 100:
            frappe.throw(_("Dòng {0} ({1}): độ ẩm phải từ 0 đến 100%.").format(r.idx, r.item_code))
        return so
    v = v or ""
    if v not in kieu:
        frappe.throw(_("Dòng {0} ({1}): giá trị không hợp lệ — {2}.").format(r.idx, r.item_code, v))
    return v or None


def _nhat_ky():
    return getattr(getattr(frappe, "local", None), "message_log", None)


def _bao_tu(tu):
    """Lời các hook vừa nói (msgprint) kể từ vị trí `tu` của nhật ký thông báo trong request."""
    ra = []
    for m in (_nhat_ky() or [])[tu:]:
        if isinstance(m, str):
            try:
                m = json.loads(m)
            except ValueError:
                m = {"message": m}
        chu = re.sub(r"<br\s*/?>", "\n", str((m or {}).get("message") or ""))
        chu = re.sub(r"<[^>]+>", "", chu).strip()
        if chu:
            ra.append(chu)
    return ra


@frappe.whitelist()
def luu_phieu(doctype, name, payload):
    """QC ghi phần tiếp nhận — chỉ các ô QC của dòng + đầu phiếu. Lưu qua doc.save(): luật tiếp nhận
    và kiểm xe chạy y như trên Desk. Trả phiếu sau khi lưu + lời cảnh báo của luật (ép Cách ly…)."""
    _guard_ghi()
    doc = _lay(doctype, name, ghi=True)
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    theo = {str(x.get("name")): x for x in p.get("dong") or [] if x.get("name")}
    for r in doc.get("items") or []:
        x = theo.get(str(r.name))
        if not x:
            continue
        for f, kieu in O_DONG.items():
            if f in x:
                r.set(f, _chuan(f, kieu, x[f], r))
    if "ghi_chu_qc" in p:
        doc.custom_ghi_chu_qc = str(p.get("ghi_chu_qc") or "").strip() or None
    xe = p.get("xe") or {}
    if xe and doctype == "Purchase Receipt":
        for f in XE_CHU:
            if f in xe:
                doc.set(f, str(xe.get(f) or "").strip()[:140] or None)
        chon = tuple(f for f, _c, _y in KX.muc(doc)) + ("custom_xe_ket_luan",)
        for f in chon:          # chỉ các mục của phiên bản phiếu (D165) — ô của bộ khác bỏ qua
            if f in xe:
                if (xe.get(f) or "") not in ("", KX.DAT, KX.KHONG_DAT):
                    frappe.throw(_("Kiểm xe: giá trị không hợp lệ — {0}.").format(xe.get(f)))
                doc.set(f, xe.get(f) or None)
        doc.custom_xe_nguoi_kiem = frappe.session.user
        # QC kiểm xe nguyên liệu cùng lúc BM.07.03 (QT.09 mục 4) — tính là chuyến QC kiểm trong tuần (W34).
        if any(doc.get(f) for f in chon) and not doc.get("custom_xe_qc_kiem"):
            doc.custom_xe_qc_kiem = frappe.session.user
            doc.custom_xe_qc_luc = now_datetime()
    doc.custom_nguoi_kiem = frappe.session.user
    log = _nhat_ky()
    tu = len(log) if log is not None else 0
    doc.save(ignore_permissions=True)
    return _dict(doc, _bao_tu(tu))


@frappe.whitelist()
def them_anh(doctype, name, anh):
    """Ảnh hàng / giấy tờ lô / xe lúc tiếp nhận — File riêng tư gắn vào phiếu (Desk thấy ở phần đính
    kèm). `anh` = [base64 JPEG/PNG/WebP], nén sẵn trên máy (lib/anh.js)."""
    _guard_ghi()
    doc = _lay(doctype, name)
    ds = json.loads(anh) if isinstance(anh, str) else (anh or [])
    if not ds:
        frappe.throw(_("Chưa có ảnh nào."))
    if len(ds) > ANH_MOT_LAN:
        frappe.throw(_("Gửi tối đa {0} ảnh một lần.").format(ANH_MOT_LAN))
    co = len(_anh(doc))
    if co + len(ds) > ANH_TOI_DA:
        frappe.throw(_("Mỗi phiếu tối đa {0} ảnh — phiếu này đã có {1}.").format(ANH_TOI_DA, co))
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
            frappe.throw(_("Ảnh thứ {0} quá lớn ({1} KB) — máy chưa nén được ảnh này.").format(i, len(b) // 1024))
        goi.append((b, kieu))
    for i, (b, kieu) in enumerate(goi, start=co + 1):
        frappe.get_doc({"doctype": "File", "file_name": f"{name}-tiepnhan-{i}.{kieu}",
                        "attached_to_doctype": doctype, "attached_to_name": name,
                        "is_private": 1, "content": b}).insert(ignore_permissions=True)
    return {"name": name, "so_anh": co + len(goi)}


@frappe.whitelist()
def anh_phieu(doctype, name):
    """Ảnh của phiếu dạng data URI. QC không có quyền đọc Purchase Receipt trên Desk nên không mở được
    thẳng file riêng tư — đọc qua đây, sau guard."""
    _guard_qc()
    doc = _lay(doctype, name)
    ra = []
    for f in _anh(doc)[:ANH_TOI_DA]:
        b = frappe.get_doc("File", f.name).get_content()
        b = b.encode() if isinstance(b, str) else b
        kieu = _kieu_anh(b or b"")
        if kieu:
            mime = "jpeg" if kieu == "jpg" else kieu
            ra.append({"name": f.name, "url": f"data:image/{mime};base64,{base64.b64encode(b).decode()}"})
    return ra
