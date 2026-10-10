"""Xuất hồ sơ theo dõi cho đoàn kiểm tra (D176) — màn ISO → Xuất báo cáo (#/iso/xuat).

Trưởng Ban ISO chọn biểu mẫu + kỳ → Excel (mỗi tờ in một sheet + Mục lục) hoặc PDF (gộp một tệp: bìa mục lục,
bookmark từng biểu mẫu). Nội dung là CHÍNH bản in của từng biểu mẫu (qc_hoso._in — cùng tờ trong gói zip cho đoàn);
luật dựng ở sx/qc/xuat_bao_cao.py.

Dựng NỀN: PDF nhiều biểu mẫu × nhiều tháng là hàng trăm trang — quá thời gian một lần gọi web. Bấm xuất = ghi một lần
xuất (SX Xuat Bao Cao, Đang chờ) + xếp job sau commit; màn hỏi lại trạng thái tới khi Xong thì hiện nút tải. Hàng đợi
máy chủ không chạy (worker dừng) thì màn cho bấm CHẠY NGAY — dựng luôn trong lần gọi đó.
Mỗi lần xuất được giữ lại (ai, lúc nào, kỳ, biểu mẫu, ghi chú đoàn) — biết đã đưa gì cho đoàn nào. Quyền: Trưởng
Ban ISO, quản trị (_guard_manager — như hồ sơ đánh giá).
"""

import json

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, nowdate

from sx.api import qc as Q
from sx.api import qc_hoso
from sx.qc import ho_so as HS
from sx.qc import mau_in as MI
from sx.qc import xuat_bao_cao as XB

TRUONG = ["name", "kieu", "tu", "den", "ghi_chu", "trang_thai", "so_bieu_mau", "so_to", "kich_thuoc", "bat_dau_luc",
          "xong_luc", "loi", "ten_tep", "tep", "owner", "creation", "ket_qua"]
GAN_DAY = 30            # số lần xuất gần nhất hiện trên màn
TOI_DA_GHI_CHU = 140


def _ho_ten(u):
    return frappe.db.get_value("User", u, "full_name") or u


def _khung(dt):
    """{mã: tên} của biểu mẫu khai trên site (SX Mau Bien Ban W45, SX So W43) còn dùng. Chưa migrate → {}."""
    try:
        return {x.name: x.ten or x.name for x in frappe.get_all(dt, filters={"ngung": 0}, fields=["name", "ten"])}
    except Exception:
        return {}


def _bieu_mau():
    """({mã: tên} chọn được, mã biên bản, mã sổ): biểu mẫu app (ho_so.BIEU_MAU) + mẫu biên bản / sổ site tự khai."""
    bb, so = _khung("SX Mau Bien Ban"), _khung("SX So")
    ds = {k: v[0] for k, v in HS.BIEU_MAU.items()}
    for k, v in list(bb.items()) + list(so.items()):
        ds.setdefault(k, v)
    return ds, set(bb), set(so)


def _dong(x):
    d = {f: x.get(f) for f in TRUONG if f not in ("tep", "ket_qua")}
    for f in ("tu", "den"):
        d[f] = str(d[f] or "")[:10]
    for f in ("bat_dau_luc", "xong_luc", "creation"):
        d[f] = str(d[f] or "")[:19]
    d["co_tep"] = bool(x.get("tep"))
    d["nguoi"] = _ho_ten(x.get("owner"))
    try:
        d["ket_qua"] = json.loads(x.get("ket_qua") or "[]")
    except ValueError:
        d["ket_qua"] = []
    return d


def _gan_day():
    return [_dong(x) for x in frappe.get_all(XB.PT, fields=TRUONG, order_by="creation desc", limit=GAN_DAY)]


@frappe.whitelist()
def tong_quan():
    """Biểu mẫu chọn được (theo nhóm danh mục hồ sơ), kỳ mặc định (3 tháng như gói zip), các lần xuất gần đây."""
    Q._guard_manager()
    ds, bb, so = _bieu_mau()
    nhom_cua = {}
    for x in frappe.get_all(HS.PT, filters={"nguon": HS.APP, "ngung": 0}, fields=["bieu_mau", "nhom"],
                            order_by="thu_tu asc"):
        if x.bieu_mau and x.bieu_mau not in nhom_cua:
            nhom_cua[x.bieu_mau] = x.nhom
    tu, den = qc_hoso._ky()
    return {"nhom": XB.nhom_bieu_mau(ds, nhom_cua, HS.NHOM, bb, so), "tu": str(tu), "den": str(den),
            "hom_nay": nowdate(), "ds": _gan_day(), "kieu": list(XB.KIEU), "toi_da_thang": XB.TOI_DA_THANG,
            "user": frappe.session.user}


@frappe.whitelist()
def xuat(payload):
    """Ghi một lần xuất {bieu_mau: [mã], tu, den, kieu, ghi_chu} rồi xếp job dựng tệp."""
    Q._guard_manager()
    p = json.loads(payload) if isinstance(payload, str) else dict(payload or {})
    if p.get("kieu") not in XB.KIEU:
        frappe.throw(_("Chọn xuất Excel hay PDF."))
    if not p.get("tu") or not p.get("den"):
        frappe.throw(_("Chọn kỳ: từ ngày, đến ngày."))
    tu, den = getdate(p["tu"]), getdate(p["den"])
    if tu > den:
        frappe.throw(_("Từ ngày phải trước đến ngày."))
    if len(HS.thang_trong(tu, den)) > XB.TOI_DA_THANG:
        frappe.throw(_("Kỳ xuất tối đa {0} tháng — chia làm nhiều lần xuất.").format(XB.TOI_DA_THANG))
    ma = list(dict.fromkeys(str(x).strip() for x in p.get("bieu_mau") or [] if str(x or "").strip()))
    if not ma:
        frappe.throw(_("Chọn ít nhất một biểu mẫu."))
    co, _bb, _so = _bieu_mau()
    la = [m for m in ma if m not in co]
    if la:
        frappe.throw(_("Không có biểu mẫu {0} trên app.").format(", ".join(la)))
    doc = frappe.get_doc({"doctype": XB.PT, "kieu": p["kieu"], "tu": tu, "den": den, "trang_thai": XB.CHO,
                          "ghi_chu": " ".join(str(p.get("ghi_chu") or "").split())[:TOI_DA_GHI_CHU],
                          "bieu_mau": json.dumps(ma, ensure_ascii=False), "so_bieu_mau": len(ma)})
    doc.insert(ignore_permissions=True)
    _xep(doc.name)
    return {"name": doc.name, "trang_thai": XB.CHO}


def _xep(name):
    try:
        frappe.enqueue("sx.api.qc_xuatbc.chay", queue="long", timeout=1800, name=name,
                       job_id=f"sx-xuatbc-{name}", deduplicate=True, enqueue_after_commit=True)
    except Exception:
        # Không có Redis / worker: lần xuất nằm Đang chờ — màn cho bấm CHẠY NGAY.
        frappe.log_error(title="sx: không xếp được job xuất báo cáo", message=frappe.get_traceback())


@frappe.whitelist()
def trang_thai(names):
    """Trạng thái các lần xuất đang chờ / đang dựng (màn hỏi lại mỗi vài giây)."""
    Q._guard_manager()
    ds = json.loads(names) if isinstance(names, str) else list(names or [])
    if not ds:
        return []
    return [_dong(x) for x in frappe.get_all(XB.PT, filters={"name": ("in", ds)}, fields=TRUONG)]


def _to(bm, tu, den):
    """[(tên tệp, nội dung)] — các tờ in của một biểu mẫu trong kỳ (BM.01.04: danh mục hồ sơ hiện hành)."""
    if bm == XB.MUC_LUC:
        return [(f"{bm}.html", qc_hoso._trang(f"{bm} — Danh mục hồ sơ", qc_hoso.in_bm0104()))]
    return qc_hoso._in(bm, tu, den)


def _dung(doc):
    """(bytes, tên tệp, các biểu mẫu kèm số tờ / lỗi). Một biểu mẫu in lỗi thì ghi lỗi đó (mục lục / bìa nói rõ),
    tệp vẫn ra đủ phần còn lại — như gói zip."""
    tu, den = getdate(doc.tu), getdate(doc.den)
    co, _bb, _so = _bieu_mau()
    bm = []
    for ma in json.loads(doc.bieu_mau or "[]"):
        x = {"ma": ma, "ten": co.get(ma, ma), "to": [], "loi": ""}
        try:
            x["to"] = _to(ma, tu, den)
        except Exception as e:  # noqa: BLE001 — một tờ hỏng không chặn cả tệp
            x["loi"] = str(e) or type(e).__name__
        bm.append(x)
    dong = [f"Kỳ: {HS.ngay_vn(tu)} – {HS.ngay_vn(den)}",
            f"Xuất lúc {now_datetime().strftime('%d/%m/%Y %H:%M')} · người xuất: {_ho_ten(doc.owner)}"]
    # D179 → D185: site có dữ liệu mẫu → dòng nhận biết ở CHÂN TRANG mọi trang / mọi sheet (cả tờ CSV, bìa, Mục lục).
    dau = {"tieu_de": "HỒ SƠ THEO DÕI — XUẤT CHO ĐOÀN KIỂM TRA",
           "dong": dong + ([f"Ghi chú: {doc.ghi_chu}"] if doc.ghi_chu else []),
           "chan": MI.BAN_THU if MI.in_ban_thu() else ""}
    if doc.kieu == XB.EXCEL:
        import openpyxl

        nd = XB.dung_excel(openpyxl, dau, bm)
    else:
        for x in bm:
            x["to"] = [_html_cua(x, t, h, tu, den) for t, h in x["to"]]
        nd = XB.dung_pdf(_lam_pdf, _writer, dau, bm)
    return nd, XB.ten_tep(doc.kieu, tu, den), bm


def _html_cua(x, ten, nd, tu, den):
    """PDF cần HTML: tờ CSV (sổ sự cố BM.08.02) → bảng có đầu trang chung (hs_bang.html, như diễn tập trong gói)."""
    if not str(ten).lower().endswith(".csv"):
        return ten, nd
    k = XB.tach_csv(nd if isinstance(nd, str) else nd.decode("utf-8-sig", "replace"))
    hang = [[o["text"] for o in h] for h in k[0][1]] if k else []
    cot, hang = (hang[0], hang[1:]) if hang else ([], [])
    return (ten[:-4] + ".html", qc_hoso._trang(f"{x['ma']} — {x['ten']}", qc_hoso._bang(
        x["ten"], f"{HS.ngay_vn(tu)} – {HS.ngay_vn(den)}", cot, hang, x["ma"])))


def _writer():
    from pypdf import PdfWriter

    return PdfWriter()


def _lam_pdf(html, tuy_chon, writer):
    """Một lượt wkhtmltopdf (frappe.utils.pdf.get_pdf) thêm trang vào writer. smart_shrinking (Frappe v16): bảng rộng
    hơn khổ giấy thì thu nhỏ cho vừa thay vì cắt mất cột."""
    import inspect

    from frappe.utils.pdf import get_pdf

    k = {"output": writer}
    if "smart_shrinking" in inspect.signature(get_pdf).parameters:
        k["smart_shrinking"] = True
    get_pdf(html, tuy_chon, **k)


def chay(name):
    """Job: dựng tệp của một lần xuất. Lần xuất không còn Đang chờ (job trùng, đã CHẠY NGAY) thì thôi."""
    # Khoá dòng: job nền và CHẠY NGAY cùng lúc thì một bên chờ, đọc thấy Đang tạo rồi thôi — không dựng hai lần.
    frappe.db.sql(f"select name from `tab{XB.PT}` where name=%s for update", name)
    if frappe.db.get_value(XB.PT, name, "trang_thai") != XB.CHO:
        return
    frappe.db.set_value(XB.PT, name, {"trang_thai": XB.DANG, "bat_dau_luc": now_datetime(), "loi": None},
                        update_modified=False)
    frappe.db.commit()
    try:
        doc = frappe.get_doc(XB.PT, name)
        nd, ten, bm = _dung(doc)
        f = frappe.get_doc({"doctype": "File", "file_name": ten, "attached_to_doctype": XB.PT,
                            "attached_to_name": name, "is_private": 1, "content": nd})
        f.insert(ignore_permissions=True)
        frappe.db.set_value(XB.PT, name, {
            "trang_thai": XB.XONG, "tep": f.file_url, "ten_tep": ten, "kich_thuoc": len(nd),
            "so_to": sum(len(x["to"]) for x in bm if not x["loi"]), "xong_luc": now_datetime(),
            "ket_qua": json.dumps([{"ma": x["ma"], "ten": x["ten"], "so_to": 0 if x["loi"] else len(x["to"]),
                                    "loi": x["loi"]} for x in bm], ensure_ascii=False)}, update_modified=False)
        frappe.db.commit()
    except Exception as e:  # noqa: BLE001 — lỗi phải nằm trên lần xuất, không chỉ trong Error Log
        frappe.db.rollback()
        frappe.db.set_value(XB.PT, name, {"trang_thai": XB.LOI, "loi": (str(e) or type(e).__name__)[:1000],
                                          "xong_luc": now_datetime()}, update_modified=False)
        frappe.db.commit()
        frappe.log_error(title=f"sx: xuất báo cáo {name} hỏng", message=frappe.get_traceback())


@frappe.whitelist()
def chay_ngay(name):
    """Hàng đợi máy chủ không chạy: dựng luôn trong lần gọi này (chỉ lần xuất còn Đang chờ)."""
    Q._guard_manager()
    if frappe.db.get_value(XB.PT, name, "trang_thai") != XB.CHO:
        frappe.throw(_("Lần xuất {0} không còn ở trạng thái chờ.").format(name))
    chay(name)
    return _dong(frappe.get_all(XB.PT, filters={"name": name}, fields=TRUONG)[0])


@frappe.whitelist()
def lam_lai(name):
    """Lần xuất bị lỗi: đưa về Đang chờ và xếp job lại (cùng biểu mẫu, cùng kỳ)."""
    Q._guard_manager()
    if frappe.db.get_value(XB.PT, name, "trang_thai") != XB.LOI:
        frappe.throw(_("Chỉ làm lại lần xuất bị lỗi."))
    frappe.db.set_value(XB.PT, name, {"trang_thai": XB.CHO, "loi": None}, update_modified=False)
    _xep(name)
    return {"name": name, "trang_thai": XB.CHO}


@frappe.whitelist()
def tai(name):
    """Tải tệp đã xuất (GET, trình duyệt tải thẳng). Tệp riêng tư — chỉ qua hàm này, có kiểm quyền."""
    Q._guard_manager()
    x = frappe.db.get_value(XB.PT, name, ["trang_thai", "tep", "ten_tep"], as_dict=True)
    if not x or x.trang_thai != XB.XONG or not x.tep:
        frappe.throw(_("Lần xuất {0} chưa có tệp.").format(name))
    nd, _ten = qc_hoso._doc_tep(x.tep)
    frappe.local.response.filename = x.ten_tep or XB.ten_tep(XB.EXCEL, "", "")
    frappe.local.response.filecontent = nd
    frappe.local.response.type = "download"


@frappe.whitelist()
def xoa(name):
    """Xoá một lần xuất cùng tệp của nó (bản ghi đang dựng thì không xoá)."""
    Q._guard_manager()
    if frappe.db.get_value(XB.PT, name, "trang_thai") == XB.DANG:
        frappe.throw(_("Đang dựng tệp — xoá sau khi xong."))
    for f in frappe.get_all("File", filters={"attached_to_doctype": XB.PT, "attached_to_name": name}, pluck="name"):
        frappe.delete_doc("File", f, ignore_permissions=True)
    frappe.delete_doc(XB.PT, name, ignore_permissions=True)
    return {"ok": 1}
