"""Phiếu hành động khắc phục BM.01.07 (W24, D150) — #/qc/khacphuc, nút thứ ba trong tab Sự cố.

Lập từ phiếu sự cố (nút trên phiếu sự cố) hoặc lập tay (đánh giá nội bộ, đoàn, xem xét lãnh đạo…).
Luật trạng thái ở controller (sx/qc/doctype/sx_khac_phuc) — chặn cả đường Desk; ở đây chỉ đi lấy,
ghi dữ liệu. Ai vào được màn QC đều ghi được nội dung; kiểm tra hiệu lực / đóng / mở lại là Ban ISO
hoặc người được giao.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from sx.api.qc import _guard_qc
from sx.qc import khac_phuc as KP
from sx.qc.quyen import duoc_dong_su_co, la_iso

TRUONG = ["name", "ngay", "nguon", "su_co", "trang_thai", "lap_boi", "mo_ta", "nguyen_nhan", "hanh_dong",
          "nguoi_thuc_hien", "han", "ket_qua", "ngay_xong", "ket_qua_boi", "hieu_luc", "nhan_xet", "kiem_boi",
          "kiem_ngay", "so_lan", "creation"]
SUA = ("nguon", "mo_ta", "nguyen_nhan", "hanh_dong", "nguoi_thuc_hien", "han", "ket_qua", "ngay_xong")
NGAY = ("ngay", "han", "ngay_xong", "kiem_ngay")


def _su_co(ten):
    if not ten:
        return {}
    try:
        return {x.name: x for x in frappe.get_all("SX Su Co", filters={"name": ("in", list(ten))},
                                                    fields=["name", "ngay", "mo_ta", "muc_do", "trang_thai"])}
    except Exception:
        return {}


def _dong(x, d, sc):
    r = dict(x)
    for f in NGAY:
        r[f] = str(x.get(f)) if x.get(f) else ""
    r["creation"] = str(x.get("creation") or "")[:10]
    r["so_lan"] = cint(x.get("so_lan"))
    r["qua_han"] = KP.qua_han(x, d)
    s = sc.get(x.get("su_co")) if x.get("su_co") else None
    r["su_co_info"] = {"ngay": str(s.ngay), "mo_ta": s.mo_ta or "", "muc_do": s.muc_do or "",
                       "trang_thai": s.trang_thai} if s else None
    return r


@frappe.whitelist()
def tong_quan():
    """Mọi phiếu (500 phiếu gần nhất) kèm đếm theo trạng thái, quá hạn; quyền kiểm tra hiệu lực."""
    _guard_qc()
    d = getdate(nowdate())
    ds = frappe.get_all(KP.PT, fields=TRUONG, order_by="ngay desc, creation desc", limit=500)
    sc = _su_co({x.su_co for x in ds if x.su_co})
    ra = [_dong(x, d, sc) for x in ds]
    return {"ds": ra, "dem": dict({t: sum(1 for x in ra if x["trang_thai"] == t) for t in KP.TRANG_THAI},
                                  qua_han=sum(1 for x in ra if x["qua_han"])),
            "nguon": list(KP.NGUON), "duoc_kiem": bool(duoc_dong_su_co()), "hom_nay": str(d),
            "user": frappe.session.user}


@frappe.whitelist()
def lap(payload):
    """Lập phiếu. Có `su_co` mà sự cố đó đã có phiếu chưa đóng → trả lại chính phiếu đó (bấm hai lần
    không đẻ hai phiếu); phiếu mới lấy sẵn mô tả / nguyên nhân / hành động đã ghi trên sự cố."""
    _guard_qc()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    moi = {"doctype": KP.PT, "ngay": nowdate(), "trang_thai": KP.MO, "nguon": p.get("nguon") or "Khác"}
    if p.get("su_co"):
        co = frappe.get_all(KP.PT, filters={"su_co": p["su_co"], "trang_thai": ("!=", KP.DONG)}, pluck="name", limit=1)
        if co:
            return {"name": co[0], "da_co": 1}
        sc = frappe.db.get_value("SX Su Co", p["su_co"], ["mo_ta", "nguyen_nhan", "hanh_dong_khac_phuc"], as_dict=True)
        if not sc:
            frappe.throw(_("Không có phiếu sự cố {0}.").format(p["su_co"]))
        moi.update(nguon=KP.SU_CO, su_co=p["su_co"], mo_ta=sc.mo_ta, nguyen_nhan=sc.nguyen_nhan,
                   hanh_dong=sc.hanh_dong_khac_phuc)
    for f in SUA:
        if (p.get(f) or "") != "" and f != "nguon":
            moi[f] = p[f]
    doc = frappe.get_doc(moi)
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "da_co": 0}


@frappe.whitelist()
def luu(name, payload, gui=0):
    """Ghi nội dung; `gui` = 1 → báo đã thực hiện (chuyển Chờ kiểm tra — controller đòi đủ ô)."""
    _guard_qc()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    doc = frappe.get_doc(KP.PT, name)
    for f in SUA:
        if f in p:
            v = p[f]
            if f in NGAY:
                v = v or None
            elif isinstance(v, str):
                v = v.strip()
            doc.set(f, v)
    if cint(gui):
        doc.trang_thai = KP.CHO_KIEM
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "trang_thai": doc.trang_thai}


@frappe.whitelist()
def rut_lai(name):
    """Người làm rút lại phiếu đã báo xong (Chờ kiểm tra → Mở) khi Ban ISO chưa kiểm."""
    _guard_qc()
    doc = frappe.get_doc(KP.PT, name)
    if doc.trang_thai != KP.CHO_KIEM:
        frappe.throw(_("Chỉ rút lại được phiếu đang chờ kiểm tra."))
    doc.trang_thai = KP.MO
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "trang_thai": doc.trang_thai}


def _ghi_nhan_xet(doc, nhan, nd):
    dong = f"[{getdate(nowdate()).strftime('%d/%m/%Y')} · {nhan}] {(nd or '').strip()}".strip()
    doc.nhan_xet = f"{(doc.nhan_xet or '').strip()}\n{dong}".strip()


@frappe.whitelist()
def kiem_tra(name, hieu_luc, nhan_xet=None):
    """Ban ISO kiểm tra hiệu lực: Có hiệu lực → Đóng; Chưa hiệu lực → về Mở (phải ghi làm gì tiếp)."""
    _guard_qc()
    if not duoc_dong_su_co():
        frappe.throw(_("Chỉ Trưởng Ban ISO hoặc người được giao mới kiểm tra hiệu lực."), frappe.PermissionError)
    if hieu_luc not in (KP.CO_HIEU_LUC, KP.CHUA_HIEU_LUC):
        frappe.throw(_("Chọn kết luận: Có hiệu lực / Chưa hiệu lực."))
    if hieu_luc == KP.CHUA_HIEU_LUC and not (nhan_xet or "").strip():
        frappe.throw(_("Chưa hiệu lực: ghi nhận xét — làm gì tiếp."))
    doc = frappe.get_doc(KP.PT, name)
    if doc.trang_thai != KP.CHO_KIEM:
        frappe.throw(_("Phiếu chưa báo đã thực hiện — chưa kiểm tra hiệu lực được."))
    doc.hieu_luc = hieu_luc
    _ghi_nhan_xet(doc, hieu_luc, nhan_xet)
    doc.trang_thai = KP.DONG if hieu_luc == KP.CO_HIEU_LUC else KP.MO
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "trang_thai": doc.trang_thai}


@frappe.whitelist()
def mo_lai(name, ly_do=None):
    """Mở lại phiếu đã đóng (việc lặp lại, kiểm tra sau thấy chưa ổn) — Ban ISO, phải ghi lý do."""
    _guard_qc()
    if not duoc_dong_su_co():
        frappe.throw(_("Chỉ Trưởng Ban ISO hoặc người được giao mới mở lại được."), frappe.PermissionError)
    if not (ly_do or "").strip():
        frappe.throw(_("Ghi lý do mở lại."))
    doc = frappe.get_doc(KP.PT, name)
    if doc.trang_thai != KP.DONG:
        frappe.throw(_("Phiếu đang mở."))
    _ghi_nhan_xet(doc, "Mở lại", ly_do)
    doc.trang_thai = KP.MO
    doc.save(ignore_permissions=True)
    return {"name": doc.name, "trang_thai": doc.trang_thai}


@frappe.whitelist()
def xoa(name):
    """Người lập xoá được trong ngày (phiếu chưa đóng); Ban ISO lúc nào cũng được."""
    _guard_qc()
    doc = frappe.get_doc(KP.PT, name)
    if not la_iso():
        if doc.lap_boi != frappe.session.user:
            frappe.throw(_("Phiếu của {0} — bạn không xoá được.").format(doc.lap_boi), frappe.PermissionError)
        if doc.trang_thai == KP.DONG or str(doc.creation or "")[:10] != str(getdate(nowdate())):
            frappe.throw(_("Chỉ xoá được phiếu chưa đóng, lập trong hôm nay — nhờ Ban ISO."), frappe.PermissionError)
    frappe.delete_doc(KP.PT, name, ignore_permissions=True)
    return {"ok": 1}


def in_phieu(ds):
    """HTML các phiếu BM.01.07 (mỗi phiếu một trang) — dùng cho nút in và gói hồ sơ cho đoàn (W27)."""
    sc = _su_co({x.su_co for x in ds if x.get("su_co")})
    return '<div style="page-break-after:always"></div>'.join(
        frappe.render_template("sx/qc/bm0107.html", {"d": x, "sc": sc.get(x.get("su_co"))}) for x in ds)


@frappe.whitelist()
def in_bm0107(name):
    """HTML A4 — phiếu hành động khắc phục BM.01.07."""
    _guard_qc()
    return in_phieu([frappe.get_doc(KP.PT, name)])
