"""Mẫu lưu nào đang bị GIỮ — không được huỷ (W07, D133).

Hai lý do giữ:
  · người dùng bấm "Giữ lại" (khiếu nại / điều tra chưa có phiếu) — ghi lý do;
  · lô của mẫu có phiếu sự cố / khiếu nại ĐANG MỞ: phiếu gắn đúng lô (bảng Lô liên quan
    `SX Su Co Lo`, W11), hoặc ô "lô ảnh hưởng" ghi mã lô / HSD của lô đó. Khớp theo chữ
    là CỐ Ý rộng tay: giữ nhầm một mẫu thêm vài tuần không hại gì, huỷ nhầm mẫu đang
    cần cho khiếu nại thì hết đường. Phiếu DIỄN TẬP không giữ mẫu.
  · khiếu nại khách hàng BM.11.01 đang mở (Issue, W13): đúng lô, hoặc đúng sản phẩm +
    HSD (sx/qc/khieu_nai.py).

Hàm thuần nhất có thể; chỉ đọc SX Su Co. Không import gì ngoài frappe (ranh giới module).
"""

import frappe
from frappe import _
from frappe.utils import cint, getdate


def _cac_cach_ghi_hsd(hsd):
    if not hsd:
        return []
    d = getdate(hsd)
    return [d.strftime("%d/%m/%Y"), d.strftime("%d/%m/%y"), d.strftime("%d.%m.%Y"),
            d.strftime("%d-%m-%Y"), str(d)]


def _khop_chu(chu, mau):
    chu = str(chu or "").lower()
    if not chu:
        return False
    if mau.get("batch") and str(mau["batch"]).lower() in chu:
        return True
    return any(c.lower() in chu for c in _cac_cach_ghi_hsd(mau.get("hsd")))


def _cung_sp_hsd(k, m):
    return bool(k.get("san_pham") and k.get("hsd") and m.get("san_pham") and m.get("hsd")
                and k["san_pham"] == m["san_pham"] and getdate(k["hsd"]) == getdate(m["hsd"]))


def ly_do_giu(ds_mau, su_co_mo=None, khieu_nai_mo=None):
    """{tên mẫu: lý do giữ} cho các mẫu trong `ds_mau` (dict: name, batch, hsd,
    san_pham, giu_lai, ly_do_giu). `su_co_mo` = phiếu sự cố đang mở, `khieu_nai_mo` =
    khiếu nại BM.11.01 đang mở (W13) — đọc từ DB nếu không truyền."""
    ra = {}
    for m in ds_mau:
        if cint(m.get("giu_lai")):
            ra[m["name"]] = _("Giữ lại: {0}").format((m.get("ly_do_giu") or "").strip() or "—")
    con = [m for m in ds_mau if m["name"] not in ra and (m.get("batch") or m.get("hsd"))]
    if not con:
        return ra
    if su_co_mo is None:
        su_co_mo = su_co_dang_mo()
    if khieu_nai_mo is None:
        from sx.qc.khieu_nai import dang_mo

        khieu_nai_mo = dang_mo()
    for m in con:
        khop = [s["name"] for s in su_co_mo
                if (m.get("batch") and m["batch"] in (s.get("lo") or ()))
                or _khop_chu(s.get("lo_anh_huong"), m)]
        khop += [k["name"] for k in khieu_nai_mo
                 if (m.get("batch") and m["batch"] in (k.get("lo") or ())) or _cung_sp_hsd(k, m)]
        if khop:
            ra[m["name"]] = _("Lô có sự cố / khiếu nại đang mở: {0}").format(", ".join(khop[:3]))
    return ra


def su_co_dang_mo():
    """Phiếu sự cố đang mở, KHÔNG diễn tập: [{name, lo_anh_huong, nguon, lo: [mã lô]}].
    Site chưa migrate D134 (chưa có cờ diễn tập / bảng lô) thì đọc phần có được."""
    try:
        ds = frappe.get_all("SX Su Co", filters={"trang_thai": "Mở", "dien_tap": 0},
                            fields=["name", "lo_anh_huong", "nguon"])
    except Exception:
        ds = frappe.get_all("SX Su Co", filters={"trang_thai": "Mở"},
                            fields=["name", "lo_anh_huong", "nguon"])
    if not ds:
        return []
    try:
        dong = frappe.get_all("SX Su Co Lo", filters={"parenttype": "SX Su Co",
                                                      "parent": ("in", [x["name"] for x in ds])},
                              fields=["parent", "batch"])
    except Exception:
        dong = []
    lo = {}
    for r in dong:
        lo.setdefault(r["parent"], []).append(r["batch"])
    return [dict(x, lo=lo.get(x["name"], [])) for x in ds]
