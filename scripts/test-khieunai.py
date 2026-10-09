"""D135 (W13) — sổ khiếu nại khách hàng BM.11.01 trên Issue, gắn lô theo HSD.

Vì sao phải có bài này:
  · Lô tìm sai (lô sản phẩm khác cùng HSD, lô cũ khi đã đổi HSD) → giữ nhầm mẫu, truy
    xuất gọi nhầm khách, mà màn hình vẫn hiện một mã lô trông hợp lệ.
  · Người tiếp nhận tự đóng khiếu nại, hoặc đóng khi chưa có kết luận / xử lý với khách
    → sổ BM.11.01 đầy dòng "đã đóng" không có nội dung.
  · Khiếu nại dị vật / vi sinh / dị ứng mà không ra phiếu sự cố → không ai điều tra.
  · ERPNext tự đóng Issue "Replied" sau N ngày — không được tự đóng khiếu nại.

Nạp sx/qc/khieu_nai.py, sx/api/qc_khieunai.py, sx/api/qc.py, sx/qc/giu_mau.py, controller
SX Su Co THẬT; frappe là giả. Sổ in dựng bằng jinja2 thật (nếu máy có).
Chạy: python3 scripts/test-khieunai.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import re
import sys
import types
from datetime import date, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

HOM_NAY = date(2026, 10, 8)
DB = {"Issue": {}, "SX Su Co": {}}
SU_CO_LO = []
BATCH = [
    {"name": "SEN-HSD270405", "item": "TP-SEN", "item_name": "Bánh đậu xanh sen",
     "expiry_date": date(2027, 4, 5), "creation": "2026-07-05 08:00", "disabled": 0, "batch_qty": 100},
    {"name": "SEN-CU-270405", "item": "TP-SEN", "item_name": "Bánh đậu xanh sen",
     "expiry_date": date(2027, 4, 5), "creation": "2026-07-06 08:00", "disabled": 0, "batch_qty": 1},
    {"name": "DUA-HSD270405", "item": "TP-DUA", "item_name": "Bánh đậu xanh dừa",
     "expiry_date": date(2027, 4, 5), "creation": "2026-07-05 09:00", "disabled": 0, "batch_qty": 50},
    {"name": "SEN-HSD270410", "item": "TP-SEN", "item_name": "Bánh đậu xanh sen",
     "expiry_date": date(2027, 4, 10), "creation": "2026-07-10 08:00", "disabled": 0, "batch_qty": 80},
]
ITEM = [{"name": "TP-SEN", "item_name": "Bánh đậu xanh sen", "disabled": 0, "has_variants": 0,
         "stock_uom": "hộp"},
        {"name": "TP-DUA", "item_name": "Bánh đậu xanh dừa", "disabled": 0, "has_variants": 0,
         "stock_uom": "hộp"}]
CUSTOMER = [{"name": "DL-NAM-DINH", "customer_name": "Đại lý Nam Định", "disabled": 0}]
CAI_DAT = {}
VAI = {"SX QC"}
NGUOI = {"u": "qc@x"}
CO = types.SimpleNamespace(in_scheduler=False)


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v

    def set(self, k, v):
        self[k] = v


class Dong(Doc):
    pass


class Document(Doc):
    """Giả Frappe Document: bản sao khi đọc, is_new / has_value_changed / before_save."""
    TIEN_TO = {"Issue": "ISS-2026-", "SX Su Co": "SC-2026-"}

    def _bang(self):
        return DB[self["doctype"]]

    def append(self, f, row):
        r = row if isinstance(row, Dong) else Dong(row)
        self.setdefault(f, []).append(r)
        return r

    def set(self, k, v):
        self[k] = [x if isinstance(x, Dong) else Dong(x) for x in v] if isinstance(v, list) else v

    def is_new(self):
        return not self.get("name") or self["name"] not in self._bang()

    def get_doc_before_save(self):
        cu = self._bang().get(self.get("name"))
        return Doc(cu) if cu else None

    def has_value_changed(self, f):
        cu = self._bang().get(self.get("name")) or {}
        return cu.get(f) != self.get(f)

    def _chay_validate(self):
        if self["doctype"] == "Issue":
            KN.validate(self)
        else:
            type(self).validate(self)

    def insert(self, **kw):
        if not self.get("name"):
            self["name"] = f"{self.TIEN_TO[self['doctype']]}{len(self._bang()) + 1:05d}"
        self._chay_validate()
        self._luu()
        return self

    def save(self, **kw):
        self._chay_validate()
        self._luu()
        return self

    def db_set(self, f, v=None, **kw):
        self.update(f if isinstance(f, dict) else {f: v})
        self._bang()[self["name"]].update(f if isinstance(f, dict) else {f: v})

    def _luu(self):
        self._bang()[self["name"]] = {k: v for k, v in self.items() if k != "ds_lo"}
        if self["doctype"] == "SX Su Co":
            SU_CO_LO[:] = [r for r in SU_CO_LO if r["parent"] != self["name"]]
            for r in self.get("ds_lo") or []:
                SU_CO_LO.append(dict(r, parent=self["name"], parenttype="SX Su Co"))


def _bang(dt):
    if dt in DB:
        return [dict(v) for v in DB[dt].values()]
    return {"Batch": BATCH, "Item": ITEM, "Customer": CUSTOMER, "SX Su Co Lo": SU_CO_LO}.get(dt, [])


def _so(x):
    return str(x) if x is not None else ""


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "in" and x not in m:
                return False
            if op == "between" and not (_so(m[0]) <= _so(x) <= _so(m[1])):
                return False
            if op == "like" and m.strip("%").lower() not in _so(x).lower():
                return False
        elif _so(x) != _so(v):
            return False
    return True


def get_all(dt, filters=None, fields=None, pluck=None, limit=None, order_by=None,
            or_filters=None, **k):
    ra = [Doc(h) for h in _bang(dt) if _khop(h, filters)]
    if or_filters:
        ra = [h for h in ra if any(_khop(h, {kk: vv}) for kk, vv in or_filters.items())]
    ob = (order_by or "").split(",")[0].strip()
    if ob:
        cot, *chieu = ob.split()
        ra.sort(key=lambda h: _so(h.get(cot)), reverse=bool(chieu and chieu[0] == "desc"))
    if limit:
        ra = ra[:limit]
    if fields:
        ra = [Doc({f: h.get(f) for f in fields}) for h in ra]
    return [h.get(pluck) for h in ra] if pluck else ra


def _get_value(dt, f, fld=None, as_dict=False, **k):
    h = next((h for h in _bang(dt) if (h["name"] == f if isinstance(f, str) else _khop(h, f))), None)
    if h is None:
        return None
    if isinstance(fld, (list, tuple)):
        d = Doc({c: h.get(c) for c in fld})
        return d if as_dict else tuple(d.values())
    return h.get(fld)


def _get_doc(x, n=None):
    if isinstance(x, dict):
        if x.get("doctype") == "SX Su Co":
            return SC_C.SXSuCo(x)
        return Document(x)
    if x in DB:
        goc = DB[x][n]
        d = (SC_C.SXSuCo if x == "SX Su Co" else Document)(dict(goc))
        if x == "SX Su Co":
            d["ds_lo"] = [Dong(r) for r in SU_CO_LO if r["parent"] == n]
        return d
    raise Loi(f"get_doc {x}")


try:
    import jinja2
except ImportError:
    jinja2 = None


def _render(path, ctx):
    if jinja2 is None:
        return ""
    fu_in = types.SimpleNamespace(formatdate=lambda v, f=None: fu.getdate(v).strftime("%d/%m/%Y"))
    env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    return env.get_template(path).render(frappe=types.SimpleNamespace(utils=fu_in), **ctx)


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, **k: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.flags = CO


class _Phien:
    user = property(lambda s: NGUOI["u"])


frappe.session = _Phien()
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_doc = _get_doc
frappe.get_cached_doc = lambda dt: Doc(CAI_DAT)
frappe.get_meta = lambda dt: types.SimpleNamespace(has_field=lambda f: True)
frappe.render_template = lambda p, ctx: _render(p, ctx)
frappe.db = types.SimpleNamespace(
    get_value=_get_value,
    count=lambda dt, f=None: len(get_all(dt, f)),
    exists=lambda dt, f=None: bool(get_all(dt, f if isinstance(f, dict) else {"name": f})),
    table_exists=lambda dt: True,
)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.getdate = lambda x=None: (x if isinstance(x, date) else
                             date.fromisoformat(str(x)[:10]) if x else HOM_NAY)
fu.nowdate = lambda: str(HOM_NAY)
fu.add_days = lambda d, n: fu.getdate(d) + timedelta(days=n)
fu.get_datetime = lambda x=None: x
fu.now_datetime = lambda: "2026-10-08 10:00:00"
fu.formatdate = str
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
mdl = types.ModuleType("frappe.model"); mdl.__path__ = []
dm = types.ModuleType("frappe.model.document"); dm.Document = Document
sys.modules["frappe.model"] = mdl
sys.modules["frappe.model.document"] = dm

for g in ("sx", "sx.qc", "sx.api", "sx.qc.doctype"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


M = nap("sx.qc.muc", "sx/qc/muc.py")
nap("sx.qc.nguong", "sx/qc/nguong.py")
nap("sx.qc.quyen", "sx/qc/quyen.py")
nap("sx.qc.san_pham", "sx/qc/san_pham.py")
nap("sx.qc.su_co", "sx/qc/su_co.py")
nap("sx.qc.xuat", "sx/qc/xuat.py")
nap("sx.qc.nhac", "sx/qc/nhac.py")
KN = nap("sx.qc.khieu_nai", "sx/qc/khieu_nai.py")
GM = nap("sx.qc.giu_mau", "sx/qc/giu_mau.py")
nap("sx.qc.rework", "sx/qc/rework.py")
SC_C = nap("sx.qc.doctype.sx_su_co.sx_su_co", "sx/qc/doctype/sx_su_co/sx_su_co.py")
nap("sx.qc.dong_vat", "sx/qc/dong_vat.py")
nap("sx.qc.cat", "sx/qc/cat.py")
nap("sx.qc.so_do", "sx/qc/so_do.py")
nap("sx.qc.thiet_bi", "sx/qc/thiet_bi.py")
nap("sx.qc.kiem_nghiem", "sx/qc/kiem_nghiem.py")
nap("sx.qc.viec_dinh_ky", "sx/qc/viec_dinh_ky.py")
nap("sx.qc.khac_phuc", "sx/qc/khac_phuc.py")
Q = nap("sx.api.qc", "sx/api/qc.py")
A = nap("sx.api.qc_khieunai", "sx/api/qc_khieunai.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


def thu(f):
    try:
        f()
    except Exception as e:  # noqa: BLE001
        return str(e) or type(e).__name__
    return None


def vai(*v, u=None):
    VAI.clear(); VAI.update(v)
    NGUOI["u"] = u or {"SX QC": "qc@x", "ISO Manager": "iso@x"}.get(v[0], "x@x")


def issue(**k):
    d = Document({"doctype": "Issue", "subject": "x", "status": "Open", "custom_khieu_nai": 1, **k})
    return d.insert()


# ═══ 1. Tìm lô theo (sản phẩm, HSD) — hook validate của Issue ══════════════
print("\n-- gắn lô theo HSD (Issue.validate) --")
d = issue(custom_san_pham="TP-SEN", custom_hsd="2027-04-05")
kiem("sản phẩm + HSD → lô; trùng HSD thì lô tạo SỚM nhất", d.custom_lo == "SEN-HSD270405", d.custom_lo)
d = issue(custom_san_pham="TP-DUA", custom_hsd="2027-04-05")
kiem("cùng HSD nhưng sản phẩm khác → đúng lô của sản phẩm đó", d.custom_lo == "DUA-HSD270405")
d = issue(custom_san_pham="TP-SEN", custom_hsd="2027-04-06")
kiem("HSD không có lô nào → để trống (không đoán)", not d.custom_lo)
d = issue(custom_lo="SEN-HSD270410")
kiem("chỉ chọn lô → điền sản phẩm + HSD từ lô",
     (d.custom_san_pham, d.custom_hsd) == ("TP-SEN", date(2027, 4, 10)))
d.custom_hsd = "2027-04-05"
d.save()
kiem("đổi HSD sau khi đã có lô → tìm lại lô theo HSD mới", d.custom_lo == "SEN-HSD270405", d.custom_lo)
d.custom_san_pham = "TP-DUA"
d.save()
kiem("đổi sản phẩm → lô của sản phẩm mới", d.custom_lo == "DUA-HSD270405", d.custom_lo)
loi = thu(lambda: issue(custom_lo="SEN-HSD270410", custom_san_pham="TP-DUA", custom_hsd="2027-04-10"))
kiem("lô của mã khác, không có lô thay thế → chặn", loi and "không phải" in loi, loi or "")
d = Document({"doctype": "Issue", "subject": "Hỏi giá", "status": "Open",
              "custom_san_pham": "TP-SEN", "custom_hsd": "2027-04-05"}).insert()
kiem("Issue KHÔNG phải khiếu nại → không đụng tới", not d.get("custom_lo"))
d.status = "Closed"
kiem("… và đóng tự do (luật đóng chỉ áp cho khiếu nại)", thu(lambda: d.save()) is None)

print("\n-- đóng / mở lại khiếu nại (cả Desk) --")
d = issue(custom_san_pham="TP-SEN", custom_hsd="2027-04-05")
d.status = "Closed"
loi = thu(lambda: d.save())
kiem("QC (người tiếp nhận) đóng → chặn", loi and "không tự đóng" in loi, loi or "")
vai("ISO Manager")
d = _get_doc("Issue", d.name)
d.status = "Closed"
loi = thu(lambda: d.save())
kiem("Ban ISO đóng khi thiếu kết luận + xử lý → chặn, nói thiếu gì",
     loi and "Kết luận" in loi and "Xử lý với khách" in loi, loi or "")
d.custom_ket_luan_kn, d.custom_xu_ly_kh = "Có lỗi của nhà máy", "Đổi 2 hộp mới"
kiem("đủ kết luận + xử lý → đóng được, ghi người + giờ đóng", thu(lambda: d.save()) is None
     and DB["Issue"][d.name]["custom_dong_boi_kn"] == "iso@x")
vai("SX QC")
d = _get_doc("Issue", d.name)
d.status = "Open"
kiem("QC mở lại → chặn", thu(lambda: d.save()) is not None)
vai("SX QC", u="truong.ca@x")
CAI_DAT["nguoi_dong_su_co"] = [Doc(user="truong.ca@x")]
d = _get_doc("Issue", d.name)
d.status = "Open"
kiem("người được GIAO mở lại được, xoá dấu đóng", thu(lambda: d.save()) is None
     and not DB["Issue"][d.name]["custom_dong_boi_kn"])
CAI_DAT.clear()
vai("SX QC")
d = _get_doc("Issue", d.name)
d.status = "Closed"
CO.in_scheduler = True
kiem("ERPNext TỰ đóng (scheduler) → giữ nguyên Mở, không ném lỗi",
     thu(lambda: d.save()) is None and DB["Issue"][d.name]["status"] == "Open")
CO.in_scheduler = False

# ═══ 2. API màn hình ══════════════════════════════════════════════════════
print("\n-- ghi khiếu nại qua màn QC --")
DB["Issue"].clear(); DB["SX Su Co"].clear(); SU_CO_LO.clear()


def ghi(**k):
    p = {"lien_he": "Chị Lan 0912xxx", "san_pham": "TP-SEN", "hsd": "2027-04-05",
         "mo_ta": "Bánh có vị chua", "phan_loai": "Cảm quan (mùi, vị, màu)", **k}
    return A.them_khieu_nai(json.dumps(p))


kiem("thiếu nội dung → chặn", "nội dung" in (thu(lambda: ghi(mo_ta="  ")) or ""))
kiem("thiếu khách / người khiếu nại → chặn", "khách hàng" in (thu(lambda: ghi(lien_he="")) or ""))
kiem("khách không có trong danh mục → chặn, chỉ ô liên hệ",
     "danh mục" in (thu(lambda: ghi(khach="KHACH-LA")) or ""))
kiem("phân loại lạ → chặn", thu(lambda: ghi(phan_loai="Linh tinh")) is not None)
r = ghi(khach="DL-NAM-DINH", khach_ten="Đại lý Nam Định", mo_ta="Bánh chua <script>x</script>\nđổi màu")
x = DB["Issue"][r["name"]]
kiem("ghi được: tích khiếu nại, tiêu đề có sản phẩm + khách, lô tự tìm",
     x["custom_khieu_nai"] == 1 and "Bánh đậu xanh sen" in x["subject"] and "Nam Định" in x["subject"]
     and r["lo"] == "SEN-HSD270405", x["subject"])
kiem("nội dung lưu dạng HTML an toàn (thẻ bị escape, xuống dòng giữ)",
     "&lt;script&gt;" in x["description"] and "<br>" in x["description"])
kiem("cảm quan, mức Thường, không tích → KHÔNG lập phiếu sự cố", r["su_co"] is None)
r2 = ghi(phan_loai="Dị vật", mo_ta="Có mảnh nhựa trong bánh")
sc = DB["SX Su Co"].get(r2["su_co"] or "") or {}
kiem("Dị vật → mức CAO + tự lập phiếu sự cố điều tra",
     DB["Issue"][r2["name"]]["custom_muc_do_kn"] == "Cao" and sc.get("nguon") == "Khiếu nại"
     and sc.get("muc_do") == "Cao", sc)
kiem("… phiếu sự cố gắn đúng lô, nối ngược về khiếu nại",
     [r_["batch"] for r_ in SU_CO_LO if r_["parent"] == r2["su_co"]] == ["SEN-HSD270405"]
     and DB["Issue"][r2["name"]]["custom_su_co"] == r2["su_co"])
r3 = ghi(phan_loai="Dị ứng", mo_ta="Khách dị ứng lạc")
kiem("Dị ứng → phiếu sự cố loại Dị ứng", DB["SX Su Co"][r3["su_co"]]["loai"] == "Dị ứng")
r4 = ghi(lap_su_co=1, phan_loai="Bao bì / nhãn")
kiem("tích 'lập phiếu sự cố' → có phiếu dù mức Thường", r4["su_co"] is not None)
r5 = ghi(hsd="2027-04-06")
kiem("HSD không khớp lô → vẫn ghi được, báo chưa có lô", r5["lo"] == "")

print("\n-- danh sách, sửa, đóng --")
kq = A.list_khieu_nai()
theo = {k["name"]: k for k in kq["danh_sach"]}
kiem("list: lô hiện bằng HSD, tên sản phẩm, nội dung chữ thường",
     theo[r["name"]]["nhan_lo"] == "HSD 05/04/2027" and theo[r["name"]]["ten_sp"] == "Bánh đậu xanh sen"
     and theo[r["name"]]["mo_ta"].startswith("Bánh chua <script>x</script>"))
kiem("list: đếm đang mở, QC không có quyền đóng", (kq["so_mo"], kq["duoc_dong"]) == (5, False))
DB["Issue"][r5["name"]]["opening_date"] = HOM_NAY - timedelta(days=9)
kiem("quá 7 ngày chưa đóng → cờ quá hạn",
     {k["name"]: k for k in A.list_khieu_nai()["danh_sach"]}[r5["name"]]["qua_han"] is True)
A.sua_khieu_nai(r["name"], json.dumps({"ket_luan": "Có lỗi của nhà máy", "xu_ly": "Đổi 3 hộp"}))
kiem("sửa: ghi kết luận + xử lý", DB["Issue"][r["name"]]["custom_xu_ly_kh"] == "Đổi 3 hộp")
kiem("QC đóng qua màn hình → chặn", thu(lambda: A.dong_khieu_nai(r["name"])) is not None)
vai("ISO Manager")
kiem("Ban ISO thấy được quyền đóng", A.list_khieu_nai()["duoc_dong"] is True)
kiem("Ban ISO đóng đủ nội dung → Closed", thu(lambda: A.dong_khieu_nai(r["name"])) is None
     and DB["Issue"][r["name"]]["status"] == "Closed")
kiem("đóng khi thiếu kết luận → chặn", thu(lambda: A.dong_khieu_nai(r5["name"])) is not None)
vai("SX QC")
loi = thu(lambda: A.sua_khieu_nai(r["name"], json.dumps({"xu_ly": "sửa lén"})))
kiem("khiếu nại đã đóng: QC không sửa được", loi and "đã đóng" in loi, loi or "")
kiem("lập phiếu sự cố lần hai → trả phiếu cũ, không đẻ thêm",
     A.lap_su_co_khieu_nai(r2["name"])["su_co"] == r2["su_co"] and len(DB["SX Su Co"]) == 3)
n_sc = A.lap_su_co_khieu_nai(r5["name"])["su_co"]
kiem("lập phiếu cho khiếu nại chưa có → có phiếu, nối ngược", DB["Issue"][r5["name"]]["custom_su_co"] == n_sc)
vai("ISO Manager")
A.mo_lai_khieu_nai(r["name"], "khách báo lại")
kiem("mở lại: Open, ghi lý do vào xử lý", DB["Issue"][r["name"]]["status"] == "Open"
     and "[Mở lại] khách báo lại" in DB["Issue"][r["name"]]["custom_xu_ly_kh"])
vai("SX QC")
DB["Issue"]["ISS-KHAC"] = {"name": "ISS-KHAC", "doctype": "Issue", "status": "Open", "subject": "x"}
kiem("Issue không phải khiếu nại → API từ chối", "không phải khiếu nại" in (thu(lambda: A.dong_khieu_nai("ISS-KHAC")) or ""))
vai("SX Vao Hop")
kiem("người ngoài QC không vào sổ khiếu nại", thu(lambda: A.list_khieu_nai()) is not None
     and thu(lambda: ghi()) is not None)
vai("SX QC")

print("\n-- giữ mẫu lưu, truy xuất theo lô --")
MAU = [{"name": "M1", "batch": "SEN-HSD270405", "hsd": date(2027, 4, 5), "san_pham": "TP-SEN"},
       {"name": "M2", "batch": None, "hsd": date(2027, 4, 5), "san_pham": "TP-SEN"},
       {"name": "M3", "batch": None, "hsd": date(2027, 4, 5), "san_pham": "TP-DUA"},
       {"name": "M4", "batch": "SEN-HSD270410", "hsd": date(2027, 4, 10), "san_pham": "TP-SEN"}]
giu = GM.ly_do_giu(MAU, su_co_mo=[])
kiem("khiếu nại mở → giữ mẫu đúng lô, và mẫu ghi tay đúng sản phẩm + HSD", {"M1", "M2"} <= set(giu), giu)
kiem("mẫu SẢN PHẨM KHÁC cùng HSD → không giữ; HSD khác → không giữ", not ({"M3", "M4"} & set(giu)))
for n in list(DB["Issue"]):
    DB["Issue"][n]["status"] = "Closed"
kiem("khiếu nại đã đóng → thôi giữ", GM.ly_do_giu(MAU, su_co_mo=[]) == {})
DB["Issue"][r["name"]]["status"] = "Open"
tl = A.theo_lo("SEN-HSD270405")
kiem("thẻ lô (Truy xuất): khiếu nại của lô, kể cả ghi theo sản phẩm + HSD",
     r["name"] in [k["name"] for k in tl] and len(tl) >= 3, [k["name"] for k in tl])
kiem("lô không có khiếu nại → rỗng", A.theo_lo("SEN-HSD270410") == [])

if jinja2:
    html = A.in_so_khieu_nai("2026-10-01", "2026-10-31")
    chu = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", html.split("</style>")[1]))
    kiem("sổ in BM.11.01: tiêu đề, khách, HSD, dòng chưa đóng, chỗ ký",
         "BM.11.01" in chu and "Đại lý Nam Định" in chu and "HSD 05/04/2027" in chu
         and "CHƯA ĐÓNG" in chu and "Trưởng Ban ISO" in chu, chu[:300])

# ═══ 3. Cấu hình ══════════════════════════════════════════════════════════
print("\n-- custom field, hook, màn hình --")
cf = {f["fieldname"]: f for f in json.load(open("sx/fixtures/custom_field.json", encoding="utf-8"))
      if f["dt"] == "Issue"}
kiem("Issue có đủ trường khiếu nại, module QC (fixtures giữ được)",
     {"custom_khieu_nai", "custom_san_pham", "custom_hsd", "custom_lo", "custom_ket_luan_kn",
      "custom_xu_ly_kh", "custom_su_co", "custom_phan_loai_kn"} <= set(cf)
     and all(f["module"] == "QC" for f in cf.values()))
kiem("ô lô Link Batch, ô sản phẩm Link Item", cf["custom_lo"]["options"] == "Batch"
     and cf["custom_san_pham"]["options"] == "Item")
kiem("lựa chọn trong fixture khớp danh mục API",
     cf["custom_phan_loai_kn"]["options"].split("\n")[1:] == list(A.PHAN_LOAI)
     and cf["custom_kenh_kn"]["options"].split("\n")[1:] == list(A.KENH)
     and cf["custom_ket_luan_kn"]["options"].split("\n")[1:] == list(A.KET_LUAN))
kiem("hook Issue.validate → sx.qc.khieu_nai.validate",
     '"Issue": {"validate": "sx.qc.khieu_nai.validate"}' in open("sx/hooks.py", encoding="utf-8").read())
js = open("sx/public/sx/views/qc_khieunai.js", encoding="utf-8").read()
for mod, ten in sorted(set(re.findall(r"sx\.api\.(qc_khieunai|qc)\.(\w+)", js))):
    kiem(f"màn Khiếu nại gọi method có thật: {mod}.{ten}",
         callable(getattr(A if mod == "qc_khieunai" else Q, ten, None)))
qcjs = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
kiem("route #/qc/khieunai, tab Sự cố sáng khi đang ở Khiếu nại",
     "khieunai: '/assets/sx/sx/views/qc_khieunai.js'" in qcjs and "dang === 'khieunai'" in qcjs)
kiem("hai màn Sự cố / Khiếu nại có nút chuyển qua lại",
     "tabSuCo('khieunai')" in js
     and "tabSuCo('incidents')" in open("sx/public/sx/views/qc_incidents.js", encoding="utf-8").read())

print(f"\n{'KHIEUNAI-OK' if not hong else f'KHIEUNAI-FAIL ({hong})'}")
sys.exit(1 if hong else 0)
