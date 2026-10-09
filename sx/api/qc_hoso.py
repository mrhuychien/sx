"""Hồ sơ cho đoàn đánh giá (W27, D149) — #/qc/hoso, tab Xem xét.

Danh mục (SX Ho So Danh Muc) + cờ Đỏ / Vàng (sx/qc/ho_so.py; đèn của các mảng lấy từ Tổng quan ATTP) +
GÓI ZIP cho đoàn: mục lục HTML (cờ, căn cứ, chỗ tìm), bản in các biểu mẫu app lập trong kỳ, tệp scan.

Một biểu mẫu in lỗi thì mục lục ghi lỗi đó và gói vẫn tải được — đoàn đang ngồi chờ thì một tờ hỏng
không được chặn cả gói. Bản in gọi đúng các hàm in sẵn có của từng màn (cùng tờ người ta vẫn in).
"""

import base64
import binascii
import html
import io
import json
import zipfile

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, now_datetime, nowdate

from sx.api import qc as Q
from sx.api import qc_attp
from sx.qc import ho_so as HS
from sx.qc.quyen import la_iso

TRUONG = ["name", "ma", "ten", "nhom", "nguon", "bieu_mau", "can_cu", "thay_the", "ngay_ban_hanh", "het_han",
          "tep", "noi_luu", "bat_buoc", "ngung", "thu_tu", "ghi_chu"]
SUA = ("ma", "ten", "nhom", "nguon", "bieu_mau", "can_cu", "thay_the", "ngay_ban_hanh", "het_han", "noi_luu",
       "bat_buoc", "ngung", "thu_tu", "ghi_chu")
SP = "SX San Pham Cong Bo"
XX = "SX Kiem Tra Xuat Xuong"
DIEN_TAP = "SX Dien Tap Truy Xuat"
NGAT_TRANG = '<div style="page-break-after:always"></div>'
TEP_TOI_DA = 10 * 1024 * 1024
# Đuôi tệp scan nhận → chữ ký đầu tệp. docx / xlsx là zip (PK…), doc / xls là OLE.
DUOI = {"pdf": (b"%PDF",), "png": (b"\x89PNG",), "jpg": (b"\xff\xd8",), "jpeg": (b"\xff\xd8",),
        "webp": (b"RIFF",), "docx": (b"PK\x03\x04",), "xlsx": (b"PK\x03\x04",),
        "doc": (b"\xd0\xcf\x11\xe0",), "xls": (b"\xd0\xcf\x11\xe0",)}


def _ky(tu=None, den=None):
    """Kỳ của gói: mặc định 3 tháng gần nhất (từ đầu tháng của 2 tháng trước tới hôm nay)."""
    den = getdate(den) if den else getdate(nowdate())
    if tu:
        tu = getdate(tu)
    else:
        t = den.replace(day=1)
        for _i in range(2):
            t = add_days(t, -1).replace(day=1)
        tu = t
    if tu > den:
        frappe.throw(_("Từ ngày phải trước đến ngày."))
    if len(HS.thang_trong(tu, den)) > HS.TOI_DA_THANG:
        frappe.throw(_("Gói tối đa {0} tháng — chia làm nhiều gói.").format(HS.TOI_DA_THANG))
    return tu, den


def _danh_muc(d):
    ds = frappe.get_all(HS.PT, fields=TRUONG)
    try:
        den_mang = {x["ma"]: x for x in qc_attp.tong_quan(str(d))["linh_vuc"]}
    except Exception:
        den_mang = {}
    try:
        sp = frappe.get_all(SP, filters={"ngung_san_xuat": 0}, fields=["name", "ten_san_pham", "so_cong_bo", "tccs"])
    except Exception:
        sp = []
    for x in ds:
        for f in ("ngay_ban_hanh", "het_han"):
            x[f] = str(x[f]) if x.get(f) else ""
        x["bat_buoc"], x["ngung"] = cint(x.get("bat_buoc")), cint(x.get("ngung"))
    return HS.gan_co(ds, d, den_mang, sp)


@frappe.whitelist()
def tong_quan():
    """Danh mục kèm cờ, kỳ mặc định của gói, danh sách chọn cho form."""
    Q._guard_manager()
    d = getdate(nowdate())
    tu, den = _ky()
    kq = _danh_muc(d)
    return {"ds": kq["ds"], "dem": kq["dem"], "nhom": list(HS.NHOM), "nguon": list(HS.NGUON),
            "bieu_mau": [{"ma": k, "ten": v[0]} for k, v in HS.BIEU_MAU.items()], "sap_het": HS.SAP_HET,
            "hom_nay": str(d), "tu": str(tu), "den": str(den), "duoc_sua": bool(la_iso())}


@frappe.whitelist()
def luu(payload):
    """Thêm / sửa một dòng danh mục (Ban ISO, quản lý). Không đụng tệp scan — xem them_tep / bo_tep."""
    Q._guard_manager()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    doc = frappe.get_doc(HS.PT, p["name"]) if p.get("name") else frappe.new_doc(HS.PT)
    for f in SUA:
        if f in p:
            v = p[f]
            if f in ("bat_buoc", "ngung", "thu_tu"):
                v = cint(v)
            elif f in ("ngay_ban_hanh", "het_han", "bieu_mau"):
                v = v or None
            else:
                v = (v or "").strip() if isinstance(v, str) else v
            doc.set(f, v)
    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)
    return {"name": doc.name}


@frappe.whitelist()
def xoa(name):
    Q._guard_manager()
    frappe.delete_doc(HS.PT, name, ignore_permissions=True)
    return {"ok": 1}


@frappe.whitelist()
def them_tep(name, ten, noi_dung):
    """Gắn bản scan (pdf, ảnh, Word, Excel ≤ 10 MB) — tệp riêng tư gắn vào dòng danh mục; gắn lại là thay."""
    Q._guard_manager()
    if not frappe.db.exists(HS.PT, name):
        frappe.throw(_("Không có hồ sơ {0}.").format(name))
    duoi = str(ten or "").rsplit(".", 1)[-1].lower() if "." in str(ten or "") else ""
    if duoi not in DUOI:
        frappe.throw(_("Chỉ nhận tệp PDF, ảnh, Word, Excel."))
    try:
        b = base64.b64decode(str(noi_dung or "").split(",")[-1], validate=True)
    except (binascii.Error, ValueError):
        frappe.throw(_("Tệp hỏng — chọn lại."))
    if not b or not b.startswith(DUOI[duoi]):
        frappe.throw(_("Nội dung tệp không khớp đuôi .{0}.").format(duoi))
    if len(b) > TEP_TOI_DA:
        frappe.throw(_("Tệp quá lớn ({0} MB, tối đa 10 MB) — scan nhẹ hơn hoặc tách tệp.").format(len(b) // 1048576))
    f = frappe.get_doc({"doctype": "File", "file_name": f"{HS.slug(frappe.db.get_value(HS.PT, name, 'ma'))}.{duoi}",
                        "attached_to_doctype": HS.PT, "attached_to_name": name, "is_private": 1, "content": b})
    f.insert(ignore_permissions=True)
    frappe.db.set_value(HS.PT, name, "tep", f.file_url)
    return {"name": name, "tep": f.file_url}


@frappe.whitelist()
def bo_tep(name):
    Q._guard_manager()
    frappe.db.set_value(HS.PT, name, "tep", None)
    return {"name": name}


# ── Gói zip ──────────────────────────────────────────────────────────────────────────────

def _trang(tieu_de, than):
    """Tài liệu HTML tự đứng được (tự khai bảng mã — mở bằng trình duyệt nào cũng đúng chữ)."""
    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>{html.escape(tieu_de)}</title>'
            f"</head><body>{than}</body></html>")


def _cac_thang(tu, den):
    """[(YYYY-MM, từ, đến)] — tháng đầu / cuối cắt theo kỳ."""
    ra = []
    for t in HS.thang_trong(tu, den):
        a = getdate(f"{t}-01")
        b = add_days(a.replace(day=28), 4)
        b = add_days(b, -b.day)
        ra.append((t, max(a, tu), min(b, den)))
    return ra


def _bang(tieu_de, phu, cot, hang):
    return frappe.render_template("sx/qc/hs_bang.html", {"tieu_de": tieu_de, "phu": phu, "cot": cot, "hang": hang})


def _in(bm, tu, den):
    """[(tên tệp, nội dung)] — bản in của một biểu mẫu app trong kỳ. Kỳ không có gì → []."""
    thang = _cac_thang(tu, den)
    if bm == "BM.08.01":
        ra = []
        for t, a, b in thang:
            h = Q.month_sheets(str(a), str(b))
            if h:
                ra.append((f"{t}.html", _trang(f"BM.08.01 — {t}", h)))
        return ra
    if bm == "BM.08.02":
        return [("so-su-co.csv", Q.export_csv(str(tu), str(den), "su_co"))]
    if bm == "BM.01.07":
        from sx.api import qc_khacphuc
        from sx.qc import khac_phuc as KP
        ds = [frappe.get_doc(KP.PT, n) for n in frappe.get_all(
            KP.PT, filters={"ngay": ("between", [tu, den])}, pluck="name", order_by="ngay asc, creation asc")]
        return [("phieu-khac-phuc.html", _trang("BM.01.07 — hành động khắc phục", qc_khacphuc.in_phieu(ds)))] if ds else []
    if bm == "BM.08.03":
        from sx.api import qc_cat
        return [(f"{t}.html", _trang(f"BM.08.03 — {t}", qc_cat.in_bm0803(t))) for t, _a, _b in thang]
    if bm == "BM.08.05":
        from sx.api import qc_vaiu
        return [(f"{t}.html", _trang(f"BM.08.05 — {t}", qc_vaiu.in_bm0805(t))) for t, _a, _b in thang]
    if bm == "BM.08.04":
        ds = frappe.get_all(XX, filters={"trang_thai": "Đã duyệt", "kiem_luc": ("between", [tu, den])},
                            pluck="name", order_by="kiem_luc asc")
        if not ds:
            return []
        than = NGAT_TRANG.join(frappe.render_template("sx/qc/xuat_xuong.html", {"d": frappe.get_doc(XX, n)})
                               for n in ds)
        return [("phieu-da-duyet.html", _trang("BM.08.04 — kiểm tra xuất xưởng", than))]
    if bm == "BM.11.01":
        from sx.api import qc_khieunai
        return [("so-khieu-nai.html", _trang("BM.11.01", qc_khieunai.in_so_khieu_nai(str(tu), str(den))))]
    if bm == "BM.15.01":
        from sx.api import qc_rework
        return [(f"{t}.html", _trang(f"BM.15.01 — {t}", qc_rework.in_bm1501(t))) for t, _a, _b in thang]
    if bm in ("BM.06.01", "BM.06.02", "BM.06.03", "BM.06.04"):
        from sx.api import qc_thietbi
        if bm == "BM.06.01":
            return [("danh-muc.html", _trang("BM.06.01", qc_thietbi.in_bieu_mau(bm)))]
        return [(f"{n}.html", _trang(f"{bm} — {n}", qc_thietbi.in_bieu_mau(bm, n))) for n in HS.nam_trong(tu, den)]
    if bm == "KH.KN.01":
        from sx.api import qc_kiemnghiem
        return [(f"{n}.html", _trang(f"KH.KN.01 — {n}", qc_kiemnghiem.in_kh_kn01(n))) for n in HS.nam_trong(tu, den)]
    if bm == "BM.07.02":
        from sx.api import qc_ncc
        return [("ncc-duoc-duyet.html", _trang("BM.07.02", qc_ncc.in_ds_ncc()))]
    if bm == "BM.09.01":
        from sx.api import qc_kiemxe
        return [("so-kiem-xe.html", _trang("BM.09.01", qc_kiemxe.in_so_kiem_xe(str(tu), str(den))))]
    if bm in ("BM.PRP.03", "BM.PRP.01"):
        from sx.api import qc_dvgh
        if bm == "BM.PRP.03":
            return [(f"tuan-{t}.html", _trang(f"BM.PRP.03 — tuần {t}", qc_dvgh.in_prp03(str(t))))
                    for t in HS.thu_hai_trong(tu, den)]
        return [(f"{t}.html", _trang(f"BM.PRP.01 — {t}", qc_dvgh.in_prp01(t))) for t, _a, _b in thang]
    if bm == "BM.02.04":
        ds = frappe.get_all(DIEN_TAP, filters={"ngay": ("between", [tu, den]), "ket_thuc": ("is", "set")},
                            fields=["name", "ngay", "lo", "ten_san_pham", "hsd", "so_phut", "can_bang_pt", "dat"],
                            order_by="ngay asc")
        if not ds:
            return []
        hang = [[x["name"], HS.ngay_vn(x["ngay"]), x.get("ten_san_pham") or "", x.get("lo") or "",
                 HS.ngay_vn(x["hsd"]) if x.get("hsd") else "", cint(x.get("so_phut")),
                 f"{float(x.get('can_bang_pt') or 0):g}%", "Đạt" if cint(x.get("dat")) else "Chưa đạt"] for x in ds]
        return [("dien-tap.html", _trang("Diễn tập truy xuất", _bang(
            "Các lần diễn tập truy xuất", f"{HS.ngay_vn(tu)} – {HS.ngay_vn(den)} · bản in từng lần ở thẻ Truy xuất",
            ["Phiếu", "Ngày", "Sản phẩm", "Lô", "HSD", "Phút", "Cân bằng", "Kết quả"], hang)))]
    if bm == "HUY_MAU":
        ds = frappe.get_all(Q.DHM, filters={"trang_thai": "Đã huỷ", "xac_nhan_luc": ("between", [tu, den])},
                            pluck="name", order_by="xac_nhan_luc asc")
        return [(f"{HS.slug(n)}.html", _trang(f"Biên bản huỷ mẫu {n}", Q.in_bien_ban_huy(n))) for n in ds]
    if bm == "BC.THANG":
        from sx.api import qc_baocao
        hom_qua = add_days(getdate(nowdate()), -1)
        return [(f"{t}.html", _trang(f"Báo cáo ATTP {t}", qc_baocao.in_bao_cao(t))) for t, a, _b in thang
                if a.replace(day=1) <= hom_qua]
    if bm == "TU_CONG_BO":
        ds = frappe.get_all(SP, filters={"ngung_san_xuat": 0}, order_by="so_cong_bo asc",
                            fields=["so_cong_bo", "ten_san_pham", "loai", "tccs", "han_dung_thang", "quy_cach"])
        hang = [[x.get("so_cong_bo") or "", x.get("ten_san_pham") or "", x.get("loai") or "", x.get("tccs") or "",
                 f"{cint(x.get('han_dung_thang'))} tháng" if x.get("han_dung_thang") else "", x.get("quy_cach") or ""]
                for x in ds]
        return [("danh-muc-san-pham.html", _trang("Sản phẩm tự công bố", _bang(
            "Danh mục sản phẩm tự công bố", f"Lập ngày {HS.ngay_vn(getdate(nowdate()))}",
            ["Số bản tự công bố", "Tên sản phẩm", "Loại", "TCCS", "Hạn dùng", "Quy cách"], hang)))]
    return []


def _doc_tep(url):
    """(nội dung, tên tệp) của tệp đính kèm trên site."""
    ten = frappe.db.get_value("File", {"file_url": url}, "name")
    if not ten:
        raise ValueError(_("Không tìm thấy tệp {0} trên hệ thống").format(url))
    f = frappe.get_doc("File", ten)
    # Đọc BYTE trên đĩa: File.get_content() thử giải mã thành chữ (windows-1250 / 1252 nhận gần như mọi
    # dãy byte) — PDF / ảnh thành chuỗi rồi hỏng khi ghi vào zip.
    with open(f.get_full_path(), "rb") as fh:
        return fh.read(), f.file_name or url.rsplit("/", 1)[-1]


def _theo_nhom(ds):
    """[(nhóm, [dòng])] theo đúng thứ tự đã sắp (gan_co) — nhóm lạ (sửa tay trong DB) vẫn có mặt, ở cuối."""
    ra = []
    for x in ds:
        n = x.get("nhom") or "Khác"
        if not ra or ra[-1][0] != n:
            ra.append((n, []))
        ra[-1][1].append(x)
    return ra


@frappe.whitelist()
def tai_goi(tu=None, den=None):
    """Tải gói zip cho đoàn (GET, trình duyệt tải thẳng): 00-MUC-LUC.html + mỗi hồ sơ một thư mục."""
    Q._guard_manager()
    tu, den = _ky(tu, den)
    d = getdate(nowdate())
    kq = _danh_muc(d)
    con = [x for x in kq["ds"] if not x.get("ngung")]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, x in enumerate(con, 1):
            thu_muc = f"{i:02d}-{HS.slug(x['ma'])}"
            x["stt"], x["trong_goi"], x["loi"] = i, [], ""
            try:
                if x["nguon"] == HS.APP:
                    tep = _in(x.get("bieu_mau"), tu, den)
                elif x.get("tep"):
                    nd, ten = _doc_tep(x["tep"])
                    tep = [(HS.slug(ten, 80), nd)]
                else:
                    tep = []
                for ten, nd in tep:
                    z.writestr(f"{thu_muc}/{ten}", nd)
                    x["trong_goi"].append(f"{thu_muc}/{ten}")
            except Exception as e:  # noqa: BLE001 — một tờ hỏng không chặn cả gói
                x["loi"] = str(e) or type(e).__name__
        z.writestr("00-MUC-LUC.html", _trang("Danh mục hồ sơ ATTP", frappe.render_template(
            "sx/qc/ho_so_muc_luc.html", {
                "tu": HS.ngay_vn(tu), "den": HS.ngay_vn(den), "lap_luc": now_datetime().strftime("%d/%m/%Y %H:%M"),
                "nguoi": frappe.session.user, "dem": kq["dem"], "nhom": _theo_nhom(con),
                "ngung": [x for x in kq["ds"] if x.get("ngung")], "APP": HS.APP, "GIAY": HS.GIAY})))
    frappe.local.response.filename = f"ho-so-attp_{tu}_{den}.zip"
    frappe.local.response.filecontent = buf.getvalue()
    frappe.local.response.type = "download"
