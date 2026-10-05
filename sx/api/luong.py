"""Thẻ "Phiếu lương" trên màn Quản lý — XEM NHANH, chỉ đọc (D110).

Phiếu lương (SX Phieu Luong) tự ghi khi chốt Vào hộp; trước D110 muốn xem phải mở
Desk. Thẻ này trả lời hai câu hay hỏi nhất ngay trên điện thoại: "tháng này mỗi
người được bao nhiêu" và "người này làm những gì, ngày nào".

Không sửa, không duyệt ở đây: sửa lương là việc làm trên Desk, có lịch sử phiên
bản. Số tiền lấy NGUYÊN từ phiếu (controller đã tính lúc lưu), không tính lại —
hai nơi tính là hai con số.

Quyền: card "phieuluong" — chỉ Quản lý (lương của người khác).
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from sx.config.roles import guard_card

PL = "SX Phieu Luong"


def _no_gia(employee_thang):
    """{employee: số dòng 0 đồng đang nợ đơn giá} — để thẻ cảnh báo trước khi duyệt."""
    ra = {}
    if not frappe.db.table_exists("SX No Don Gia"):
        return ra
    for ten, thang, nam in employee_thang:
        n = frappe.db.sql("""
            select count(*) from `tabSX Phieu Luong Chi Tiet` c
              join `tabSX No Don Gia` n on n.san_pham = c.san_pham and n.ngay = c.ngay
                   and ifnull(n.cach_lam, '') = ifnull(c.cach_lam, '') and n.trang_thai = 'Chờ giá'
             where c.parent = %s and c.parenttype = %s and ifnull(c.don_gia, 0) = 0""",
                          (ten, PL))
        if n and n[0][0]:
            ra[ten] = cint(n[0][0])
    return ra


@frappe.whitelist()
def thang(nam, thang, q=None):
    """Phiếu lương một tháng: mỗi người một dòng + tổng cả tháng."""
    guard_card("phieuluong")
    nam, thang = cint(nam), cint(thang)
    if not (1 <= thang <= 12 and 2000 <= nam <= 2100):
        frappe.throw(_("Tháng không hợp lệ."))
    loc = {"thang": thang, "nam": nam, "docstatus": ("<", 2)}
    ds = frappe.get_all(
        PL, filters=loc,
        fields=["name", "employee", "ten_nhan_vien", "trang_thai", "docstatus", "ngay_cong",
                "luong_san_pham", "tien_an", "tong_tien", "tong_khau_tru", "luong_thuc_nhan"],
        order_by="ten_nhan_vien asc")
    if q:
        k = q.strip().lower()
        ds = [x for x in ds if k in (x.ten_nhan_vien or "").lower() or k in (x.employee or "").lower()]
    no = _no_gia([(x.name, thang, nam) for x in ds])
    for x in ds:
        x["no_gia"] = no.get(x.name, 0)
        x["da_duyet"] = cint(x.docstatus) == 1
    return {
        "nam": nam, "thang": thang, "danh_sach": ds,
        "tong": {
            "so_nguoi": len(ds),
            "luong_san_pham": sum(flt(x.luong_san_pham) for x in ds),
            "thuc_nhan": sum(flt(x.luong_thuc_nhan) for x in ds),
            "da_duyet": sum(1 for x in ds if x.da_duyet),
            "no_gia": sum(1 for x in ds if x.no_gia),
        },
    }


@frappe.whitelist()
def chi_tiet(name):
    """Một phiếu: các khoản, sản phẩm gộp theo mã, từng ngày, lỗi phạt."""
    guard_card("phieuluong")
    p = frappe.get_doc(PL, name)
    sp = {}
    for r in p.chi_tiet:
        k = (r.san_pham, r.cach_lam or "", flt(r.don_gia))
        g = sp.setdefault(k, {"ten": r.ten_san_pham or r.san_pham, "cach_lam": r.cach_lam or "",
                              "don_gia": flt(r.don_gia), "so_luong": 0, "thanh_tien": 0.0})
        g["so_luong"] += cint(r.so_luong)
        g["thanh_tien"] += flt(r.thanh_tien)
    khoan = [
        (_("Lương sản phẩm"), p.luong_san_pham), (_("Tiền ăn ca + ăn đêm"), p.tien_an),
        (_("Chuyên cần"), p.chuyen_can), (_("Hỗ trợ ngày công"), p.ho_tro_ngay_cong),
        (_("Thưởng thâm niên"), p.thuong_tham_nien), (_("Hỗ trợ khác"), p.ho_tro),
    ]
    tru = [(_("Tiền phạt"), p.tien_phat), (_("Bảo hiểm"), p.bao_hiem)]
    return {
        "name": p.name, "employee": p.employee, "ten": p.ten_nhan_vien or p.employee,
        "thang": cint(p.thang), "nam": cint(p.nam), "trang_thai": p.trang_thai,
        "da_duyet": p.docstatus == 1,
        "ngay_cong": flt(p.ngay_cong), "ngay_san_xuat": flt(p.ngay_san_xuat),
        "cong": [{"ten": t, "tien": flt(v)} for t, v in khoan if flt(v)],
        "tru": [{"ten": t, "tien": flt(v)} for t, v in tru if flt(v)],
        "tong_tien": flt(p.tong_tien), "tong_khau_tru": flt(p.tong_khau_tru),
        "thuc_nhan": flt(p.luong_thuc_nhan),
        "san_pham": sorted(sp.values(), key=lambda g: -g["thanh_tien"]),
        "ngay": [{"ngay": str(getdate(r.ngay)), "thu": r.thu, "an_ca": cint(r.an_ca),
                  "an_dem": cint(r.an_dem), "luong_sp": flt(r.luong_sp), "he_so": flt(r.he_so),
                  "thu_nhap": flt(r.thu_nhap_ngay)} for r in p.dong],
        "phat": [{"ly_do": r.ly_do, "tien": flt(r.thanh_tien)} for r in p.phat],
        "ghi_chu": p.ghi_chu or "",
    }
