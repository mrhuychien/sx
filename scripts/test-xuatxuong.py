"""D137 (W08) — kiểm tra xuất xưởng theo lô BM.08.04; D159 (W31) — theo phiếu giấy lần BH 01.

Vì sao phải có bài này: đây là CỔNG cuối trước khi hàng rời xưởng.
  · Người đã kiểm lô tự duyệt luôn (kể cả khi người đó có role Ban ISO) → bước duyệt chỉ
    còn là dấu tích. Tài liệu 08/10 ghi rõ: người duyệt không phải QC đã kiểm lô đó.
  · Lô chưa duyệt vẫn nhập kho / vẫn bán được → phiếu BM.08.04 là giấy tờ cho có.
  · Chặn nhầm tồn cũ (nhập trước khi có BM.08.04) → cả kho thành phẩm đứng hình sau khi
    cập nhật.
  · Lô duyệt Không đạt mà không ra phiếu sự cố → không ai xử lý lô đó.
  · (W31) Phiếu khác bản giấy: thiếu mục, 5 mẫu thành 1 ô, "Giữ lại" lọt qua chốt chặn như "Đạt",
    lô "Không cho xuất" (huỷ) lại được lập phiếu kiểm lại; gợi ý hồ sơ chấm thay QC.

Nạp controller SX Kiem Tra Xuat Xuong, sx/qc/xuat_xuong.py, sx/api/xuatxuong.py,
sx/api/thuhoi.py, sx/api/qc.py, nhac.py, patch d137 / d152 / d159 THẬT; frappe giả; cây truy xuất
(sx/api/truyxuat._Ctx) giả theo từng phiếu kho.
Chạy: python3 scripts/test-xuatxuong.py   (verify.sh gọi sẵn)
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
DB = {"SX Kiem Tra Xuat Xuong": {}, "SX Su Co": {}}
BATCH = [
    {"name": "SEN-HSD270405", "item": "TP-SEN", "item_name": "Bánh đậu xanh sen",
     "expiry_date": date(2027, 4, 5), "creation": "2026-10-08 10:00"},
    {"name": "SEN-CU-270101", "item": "TP-SEN", "item_name": "Bánh đậu xanh sen",
     "expiry_date": date(2027, 1, 1), "creation": "2026-04-01 10:00"},      # tồn cũ
    {"name": "BOT-NEN-01", "item": "BOT-NEN", "item_name": "Bột đỗ nền",
     "expiry_date": date(2026, 10, 20), "creation": "2026-10-08 09:00"},    # không phải TP
]
ITEM = [{"name": "TP-SEN", "item_name": "Bánh đậu xanh sen", "stock_uom": "Hộp"},
        {"name": "TP-DUA", "item_name": "Bánh đậu xanh dừa", "stock_uom": "Hộp"},
        {"name": "BOT-NEN", "item_name": "Bột đỗ nền", "stock_uom": "Kg"}]
ROUND = []          # SX QC Round: {ngay, luot, docstatus, b7_chuyen_doi}
LUU_MAU = []        # SX QC Luu Mau: {name, san_pham, hsd, lo}
NGAY_SX = []        # SX Ngay San Xuat: {name, ngay, docstatus}
SE = []             # Stock Entry: {name, custom_ngay_sx, posting_date, docstatus}
SED = []            # Stock Entry Detail: {parent, batch_no, is_finished_item, docstatus}
SU_CO_LO = []       # SX Su Co Lo: {parent, parenttype, batch}
CAY = {}            # cây nguyên liệu giả của từng phiếu kho: {se: [nút như truyxuat._Ctx]}
CONG_BO = {}        # sản phẩm tự công bố giả: {item: {loai, co_lac, quy_cach}}
NHAP_NHAP = []      # SX Phieu Nhap TP Item của phiếu nháp
CON = {}            # khotp.con_theo_hsd giả: {item: [{hsd, nsx, con}]}
SETTINGS = {"chan_nhap_chua_xuat_xuong": 1, "xuat_xuong_tu_ngay": date(2026, 10, 8)}
CAI_DAT_QC = {}
VAI = {"SX QC"}
NGUOI = {"u": "qc@x"}


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
    TIEN_TO = {"SX Kiem Tra Xuat Xuong": "XX-2026-", "SX Su Co": "SC-2026-"}

    def _bang(self):
        return DB[self["doctype"]]

    def append(self, f, row):
        r = row if isinstance(row, Dong) else Dong(row)
        self.setdefault(f, []).append(r)
        return r

    def is_new(self):
        return not self.get("name") or self["name"] not in self._bang()

    def get_doc_before_save(self):
        cu = self._bang().get(self.get("name"))
        return Doc(cu) if cu else None

    def has_value_changed(self, f):
        return (self._bang().get(self.get("name")) or {}).get(f) != self.get(f)

    def _validate(self):
        v = getattr(type(self), "validate", None)
        if v:
            v(self)

    def insert(self, **kw):
        if not self.get("name"):
            self["name"] = f"{self.TIEN_TO[self['doctype']]}{len(self._bang()) + 1:04d}"
        self._validate()
        self._luu()
        return self

    def save(self, **kw):
        self._validate()
        self._luu()
        return self

    def _luu(self):
        if self["doctype"] == "SX Su Co":
            self.setdefault("dien_tap", 0)       # mặc định của DocType
        self._bang()[self["name"]] = {k: ([dict(r) for r in v] if isinstance(v, list) else v)
                                      for k, v in self.items()}
        u = getattr(type(self), "on_update", None)
        if u:
            u(self)

    def db_set(self, f, v=None, **kw):
        self.update(f if isinstance(f, dict) else {f: v})
        self._bang()[self["name"]].update(f if isinstance(f, dict) else {f: v})


def _bang(dt):
    if dt in DB:
        return [dict(v) for v in DB[dt].values()]
    return {"Batch": BATCH, "Item": ITEM, "SX QC Round": ROUND, "SX QC Luu Mau": LUU_MAU,
            "SX Phieu Nhap TP Item": NHAP_NHAP, "SX Ngay San Xuat": NGAY_SX, "Stock Entry": SE,
            "Stock Entry Detail": SED, "SX Su Co Lo": SU_CO_LO}.get(dt, [])


def _so(x):
    return str(x) if x is not None else ""


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "in" and x not in m and _so(x) not in [_so(i) for i in m]:
                return False
            if op == "!=" and _so(x) == _so(m):
                return False
            if op == "like" and m.strip("%").lower() not in _so(x).lower():
                return False
        elif _so(x) != _so(v):
            return False
    return True


def get_all(dt, filters=None, fields=None, pluck=None, limit=None, order_by=None, **k):
    ra = [Doc(h) for h in _bang(dt) if _khop(h, filters)]
    ob = (order_by or "").split(",")[0].strip()
    if ob:
        cot, *chieu = ob.split()
        ra.sort(key=lambda h: _so(h.get(cot)), reverse=bool(chieu and chieu[0] == "desc"))
    if limit:
        ra = ra[:limit]
    return [h.get(pluck) for h in ra] if pluck else ra


def _get_value(dt, f, fld=None, as_dict=False, **k):
    h = next((h for h in _bang(dt) if (h.get("name") == f if isinstance(f, str) else _khop(h, f))), None)
    if h is None:
        return None
    if isinstance(fld, (list, tuple)):
        d = Doc({c: h.get(c) for c in fld})
        return d if as_dict else tuple(d.values())
    return h.get(fld)


def _get_doc(x, n=None):
    if isinstance(x, dict):
        if x.get("doctype") == "SX Kiem Tra Xuat Xuong":
            return XXC.SXKiemTraXuatXuong(x)
        return Document(x)
    if x == "SX Kiem Tra Xuat Xuong":
        d = XXC.SXKiemTraXuatXuong(dict(DB[x][n]))
        d["ds_muc"] = [Dong(r) for r in DB[x][n].get("ds_muc") or []]
        return d
    raise Loi(x)


try:
    import jinja2
except ImportError:
    jinja2 = None


def _render(path, ctx):
    if jinja2 is None:
        return ""
    fu_in = types.SimpleNamespace(formatdate=lambda v, f=None: fu.getdate(v).strftime("%d/%m/%Y"),
                                  format_datetime=lambda v, f=None: str(v))
    env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
    return env.get_template(path).render(frappe=types.SimpleNamespace(utils=fu_in), **ctx)


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, **k: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.msgprint = lambda *a, **k: None
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})


class _Phien:
    user = property(lambda s: NGUOI["u"])


frappe.session = _Phien()
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_doc = _get_doc
frappe.get_single = lambda dt: Doc(SETTINGS)
frappe.get_cached_doc = lambda dt: Doc(CAI_DAT_QC)
frappe.get_meta = lambda dt: types.SimpleNamespace(has_field=lambda f: True)
frappe.render_template = lambda p, ctx: _render(p, ctx)
frappe.db = types.SimpleNamespace(
    get_value=_get_value, count=lambda dt, f=None: len(get_all(dt, f)),
    exists=lambda dt, f=None: True if dt == "DocType" else bool(get_all(dt, f if isinstance(f, dict) else {"name": f})),
    # Như frappe thật: doctype Single (SX Settings) không có bảng riêng — D137 bản đầu hỏng đúng chỗ này.
    table_exists=lambda dt: dt != "SX Settings",
    set_single_value=lambda dt, f, v: SETTINGS.update({f: v}),
    set_value=lambda dt, n, f, v=None, **k: DB[dt][n].update(f if isinstance(f, dict) else {f: v}),
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
fu.now_datetime = lambda: "2026-10-08 15:00:00"
fu.formatdate = str
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
mdl = types.ModuleType("frappe.model"); mdl.__path__ = []
dm = types.ModuleType("frappe.model.document"); dm.Document = Document
sys.modules["frappe.model"] = mdl
sys.modules["frappe.model.document"] = dm
for g in ("sx", "sx.qc", "sx.api", "sx.config", "sx.qc.doctype", "sx.patches"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m
ut = types.ModuleType("sx.utils")
ut.get_settings = lambda: Doc(SETTINGS)
ut.items_tp = lambda fields=None, **k: [Doc(name="TP-SEN"), Doc(name="TP-DUA")]
ut.nsx_tu_hsd = lambda item, hsd: str(fu.getdate(hsd) - timedelta(days=274)) if hsd else None
ut.cong_bo_cua = lambda item: CONG_BO.get(item)
sys.modules["sx.utils"] = ut
tx = types.ModuleType("sx.api.truyxuat")


class _Ctx:
    def nguyen_lieu_cua_se(self, se, visited, sau):
        return CAY.get(se, [])


tx._Ctx = _Ctx
sys.modules["sx.api.truyxuat"] = tx
kh = types.ModuleType("sx.api.khotp")
kh.con_theo_hsd = lambda tu, den, tru_phieu=None: CON
sys.modules["sx.api.khotp"] = kh


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


nap("sx.config.roles", "sx/config/roles.py")
nap("sx.qc.muc", "sx/qc/muc.py")
nap("sx.qc.nguong", "sx/qc/nguong.py")
nap("sx.qc.quyen", "sx/qc/quyen.py")
nap("sx.qc.san_pham", "sx/qc/san_pham.py")
nap("sx.qc.su_co", "sx/qc/su_co.py")
nap("sx.qc.xuat", "sx/qc/xuat.py")
NH = nap("sx.qc.nhac", "sx/qc/nhac.py")
XX = nap("sx.qc.xuat_xuong", "sx/qc/xuat_xuong.py")
XXC = nap("sx.qc.doctype.sx_kiem_tra_xuat_xuong.sx_kiem_tra_xuat_xuong",
          "sx/qc/doctype/sx_kiem_tra_xuat_xuong/sx_kiem_tra_xuat_xuong.py")
nap("sx.qc.dong_vat", "sx/qc/dong_vat.py")
nap("sx.qc.cat", "sx/qc/cat.py")
nap("sx.qc.so_do", "sx/qc/so_do.py")
nap("sx.qc.thiet_bi", "sx/qc/thiet_bi.py")
nap("sx.qc.kiem_nghiem", "sx/qc/kiem_nghiem.py")
nap("sx.qc.viec_dinh_ky", "sx/qc/viec_dinh_ky.py")
nap("sx.qc.khac_phuc", "sx/qc/khac_phuc.py")
nap("sx.qc.vai_u", "sx/qc/vai_u.py")
nap("sx.qc.ncc", "sx/qc/ncc.py")
nap("sx.qc.kiem_xe", "sx/qc/kiem_xe.py")
nap("sx.qc.tai_lieu", "sx/qc/tai_lieu.py")
nap("sx.qc.tiep_nhan", "sx/qc/tiep_nhan.py")
Q = nap("sx.api.qc", "sx/api/qc.py")
nap("sx.api.thuhoi", "sx/api/thuhoi.py")
A = nap("sx.api.xuatxuong", "sx/api/xuatxuong.py")
P = nap("sx.patches.d137_xuat_xuong", "sx/patches/d137_xuat_xuong.py")
P3 = nap("sx.patches.d159_xuat_xuong_lan_bh01", "sx/patches/d159_xuat_xuong_lan_bh01.py")

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


def cham_moi(d, kl="Cho xuất xưởng", hong=(), mau_k=(), **them):
    """Payload chấm đủ phiếu lần BH 01: A Đạt (A4 KAD), B 5 mẫu Đ (B2 số cân); `hong` = mục
    Không đạt, `mau_k` = dòng B có mẫu 1 ghi K."""
    ds = []
    for r in d["ds_muc"]:
        ma = r["ma"]
        x = {"ma": ma, "ket_qua": "Không đạt" if ma in hong else ("Không áp dụng" if ma == "A4" else "Đạt")}
        if ma.startswith("B"):
            x["mau"] = (["150,5", "151", "149.8", "150", "150.2"] if ma == "B2"
                        else ["K" if ma in mau_k else "Đ"] + ["Đ"] * 4)
        ds.append(x)
    p = {"ds_muc": ds, "ket_luan": kl}
    p.update(them)
    return json.dumps(p)


def dong(name, ma):
    return next(r for r in DB["SX Kiem Tra Xuat Xuong"][name]["ds_muc"] if r["ma"] == ma)


# ═══ 1. Lập phiếu theo bản giấy lần BH 01, tra hồ sơ lô ═══════════════════
print("\n-- lập phiếu BM.08.04 lần BH 01: đủ mục A1–A5, B1–B6, đúng chữ bản giấy --")
NSX = date(2026, 7, 5)           # HSD 05/04/2027 − 274 ngày (nsx_tu_hsd giả)
ROUND[:] = ([{"ngay": NSX, "luot": l, "docstatus": 1} for l in ("Đầu sáng", "Trưa", "Cuối chiều")]
            + [{"ngay": date(2026, 7, 3), "luot": l, "docstatus": 1} for l in ("Tuần", "Trưa", "Cuối chiều")]
            + [{"ngay": date(2026, 7, 2), "luot": l, "docstatus": 1} for l in ("Đầu sáng", "Trưa", "Cuối chiều")])
ROUND[1]["b7_chuyen_doi"] = "Âm tính"
LUU_MAU[:] = [{"name": "LM-0007", "san_pham": "TP-SEN", "hsd": date(2027, 4, 5)}]
NGAY_SX[:] = [{"name": "SXN-0705", "ngay": NSX, "docstatus": 1}]
SE[:] = [{"name": "SE-T2-0705", "custom_ngay_sx": "SXN-0705", "posting_date": NSX, "docstatus": 1},
         {"name": "SE-NGHIEN-R0702", "posting_date": date(2026, 7, 3), "docstatus": 1},
         {"name": "SE-HUY-R0702", "posting_date": date(2026, 7, 1), "docstatus": 2}]
SED[:] = [{"parent": "SE-NGHIEN-R0702", "batch_no": "R-0702", "is_finished_item": 1, "docstatus": 1},
          {"parent": "SE-HUY-R0702", "batch_no": "R-0702", "is_finished_item": 1, "docstatus": 2}]
CAY["SE-T2-0705"] = [
    {"item": "BOT-NEN", "ten": "Bột đỗ nền", "batch": "R-0702", "nhom": "BTP-Bot",
     "rang": {"ngay": "2026-07-02", "loai_dau": "Đỗ xanh"},
     "con": [{"item": "DX-VO", "ten": "Đỗ xanh vỡ", "batch": "R-0702-V", "nhom": "BTP-Dau",
              "con": [{"item": "DX", "ten": "Đỗ xanh", "batch": "DX-NCC-01", "ncc": {"ket_luan": "Đạt"}}]}]},
    {"item": "DUONG", "ten": "Đường", "batch": "DUONG-01", "ncc": {"ket_luan": "Đạt"}},
    {"item": "TUI", "ten": "Túi PE", "batch": None, "khong_lo": True},
    {"item": "BOT-NEN", "ten": "Bột đỗ nền", "batch": "R-0702", "lap": True},
]
CONG_BO.update({"TP-SEN": {"loai": "Bánh", "co_lac": 0, "quy_cach": "Hộp 250 g\nThùng 20 hộp"},
                "TP-DUA": {"loai": "Bột", "co_lac": 0}})
d = A.lap_phieu("TP-SEN", "2027-04-05", 120, "Hộp")
x = DB["SX Kiem Tra Xuat Xuong"][d["name"]]
kiem("phiếu mới: Nháp, A1–A5 rồi B1–B6, tên sản phẩm, NSX tính từ HSD, gắn lô có sẵn, 5 mẫu",
     x["trang_thai"] == "Nháp" and [r["ma"] for r in x["ds_muc"]] == [m[0] for m in XX.MUC]
     == ["A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3", "B4", "B5", "B6"]
     and x["ten_san_pham"] == "Bánh đậu xanh sen" and x["nsx"] == "2026-07-05"
     and x["batch"] == "SEN-HSD270405" and x["so_mau"] == 5 and d["moi"] is True, (x["nsx"], x["batch"]))
kiem("chép đúng chữ bản giấy (nội dung + yêu cầu lưu trong bảng con)",
     "oPRP-9" in dong(d["name"], "A4")["noi_dung"] and dong(d["name"], "A4")["yeu_cau"].startswith("Âm tính. KAD")
     and "(lạc, sữa, dừa)" in dong(d["name"], "B4")["yeu_cau"]
     and dong(d["name"], "B2")["noi_dung"] == "Khối lượng tịnh (g)"
     and "mục 6–8" in dong(d["name"], "A1")["noi_dung"] and "QĐ.01 lần 02" in dong(d["name"], "A5")["noi_dung"])
kiem("đầu phiếu: quy cách theo bộ tự công bố (dòng đầu), ngày nghiền / ngày rang tra từ chứng từ kho ngày SX",
     (x["quy_cach"], x["ngay_nghien"], x["ngay_rang"]) == ("Hộp 250 g", "2026-07-03", "2026-07-02"),
     (x["quy_cach"], x["ngay_nghien"], x["ngay_rang"]))
goi = {r["ma"]: r["goi_y"] for r in x["ds_muc"] if r["ma"][0] == "A"}
kiem("gợi ý: A1 Đạt (3 ngày đủ 3 lượt, Tuần = đầu sáng), A2 Đạt (không sự cố), A3 Đạt, A4 KAD (bánh), A5 Đạt",
     goi == {"A1": "Đạt", "A2": "Đạt", "A3": "Đạt", "A4": "Không áp dụng", "A5": "Đạt"}, goi)
kiem("QC vẫn bấm: A1–A4 để trống, chỉ A5 (mẫu lưu, kiểm tự động) chấm sẵn; mục B trống",
     [r["ket_qua"] for r in x["ds_muc"]] == ["", "", "", "", "Đạt"] + [""] * 6)
cc = {r["ma"]: r["can_cu"] for r in x["ds_muc"] if r["ma"][0] == "A"}
kiem("căn cứ từng mục: số lượt từng ngày, nguyên liệu tiếp nhận, hàng không theo lô, mẫu lưu",
     "ngày SX 05/07/2026: 3 lượt" in cc["A1"] and "nghiền 03/07/2026: 3 lượt" in cc["A1"]
     and "rang 02/07/2026: 3 lượt" in cc["A1"] and "2 lô tiếp nhận Đạt" in cc["A3"] and "Túi PE" in cc["A3"]
     and "LM-0007" in cc["A5"] and "A3 · " in x["ho_so"], cc)
kiem("bấm lập lần hai → trả đúng phiếu cũ, không đẻ phiếu thứ hai",
     A.lap_phieu("TP-SEN", "2027-04-05")["name"] == d["name"] and len(DB["SX Kiem Tra Xuat Xuong"]) == 1)
d2 = A.lap_phieu("TP-DUA", "2027-04-05")
x2 = DB["SX Kiem Tra Xuat Xuong"][d2["name"]]
goi2 = {r["ma"]: r["goi_y"] for r in x2["ds_muc"] if r["ma"][0] == "A"}
kiem("lô bột không lạc: A4 theo B7 ngày SX (âm tính → Đạt); chưa lấy mẫu lưu → A5 trống, căn cứ nói CHƯA lấy",
     goi2["A4"] == "Đạt" and goi2["A5"] == "" and dong(d2["name"], "A5")["ket_qua"] == ""
     and "CHƯA lấy" in x2["ho_so"] and x2["quy_cach"] is None, goi2)
loi = thu(lambda: XXC.SXKiemTraXuatXuong({"doctype": "SX Kiem Tra Xuat Xuong", "san_pham": "TP-SEN",
                                          "hsd": "2027-04-05", "trang_thai": "Nháp"}).insert())
kiem("lập tay phiếu thứ hai cho cùng lô (Desk) → chặn", loi and d["name"] in loi, loi or "")
loi = thu(lambda: XXC.SXKiemTraXuatXuong({"doctype": "SX Kiem Tra Xuat Xuong", "san_pham": "TP-SEN",
                                          "hsd": "2027-05-01", "trang_thai": "Đã duyệt",
                                          "ket_luan": "Cho xuất xưởng"}).insert())
kiem("lập phiếu mới thẳng 'Đã duyệt' → chặn", loi and "Nháp" in loi, loi or "")
tay = XXC.SXKiemTraXuatXuong({"doctype": "SX Kiem Tra Xuat Xuong", "san_pham": "TP-DUA", "hsd": "2027-07-07",
                              "trang_thai": "Nháp"})
tay.insert()
kiem("lập tay trên Desk → vẫn đủ 11 mục bản giấy, 5 mẫu",
     [r["ma"] for r in tay["ds_muc"]] == [m[0] for m in XX.MUC] and tay["so_mau"] == 5
     and tay["ds_muc"][0]["yeu_cau"].startswith("Đủ 3 lượt"))
del DB["SX Kiem Tra Xuat Xuong"][tay["name"]]

print("\n-- gợi ý hồ sơ lô: từng trường hợp --")


def hs(item="TP-DUA", hsd="2027-04-05", nsx=NSX, nghien=(date(2026, 7, 3),), rang=(date(2026, 7, 2),), **k):
    return XX.ho_so_lo(item, hsd, nsx, nghien, rang, **k)


ROUND.append({"ngay": NSX, "luot": "Bổ sung", "docstatus": 1})
kiem("lượt Bổ sung không tính vào 'đủ 3 lượt'", XX.so_luot(NSX) == 3)
ROUND[2]["docstatus"] = 0
h = hs(loai="Bánh")
kiem("ngày SX thiếu lượt (Cuối chiều chưa hoàn tất, Bổ sung không bù) → A1 KHÔNG gợi ý, căn cứ ghi (thiếu)",
     h["goi_y"]["A1"] is None and "ngày SX 05/07/2026: 2 lượt (thiếu)" in h["can_cu"]["A1"], h["can_cu"]["A1"])
ROUND[2]["docstatus"] = 1
h = hs(rang=(), loai="Bánh")
kiem("chưa có ngày rang → A1 không gợi ý, nhắc ghi ngày rồi TRA LẠI",
     h["goi_y"]["A1"] is None and "chưa có ngày rang" in h["can_cu"]["A1"], h["can_cu"]["A1"])
h = hs(nsx=None, loai="Bánh")
kiem("chưa tính được NSX → A1 không gợi ý", h["goi_y"]["A1"] is None and "NSX" in h["can_cu"]["A1"])
ROUND[1]["b7_chuyen_doi"] = "Dương tính"
kiem("bột không lạc, B7 ngày SX dương tính → A4 gợi ý Không đạt", hs(loai="Bột")["goi_y"]["A4"] == "Không đạt")
ROUND[1]["b7_chuyen_doi"] = "Không có chuyển đổi"
h = hs(loai="Bột")
kiem("ngày SX không chuyển đổi sau Chè → A4 KAD (máy không chạy Chè trước lô)",
     h["goi_y"]["A4"] == "Không áp dụng" and "không chạy Chè" in h["can_cu"]["A4"], h["can_cu"]["A4"])
ROUND[1]["b7_chuyen_doi"] = "Âm tính"
kiem("lô Chè / vị có lạc → A4 KAD; mã chưa gắn bộ tự công bố → không gợi ý",
     hs(loai="Chè")["goi_y"]["A4"] == "Không áp dụng" and hs(loai="Bột", co_lac=1)["goi_y"]["A4"] == "Không áp dụng"
     and hs(loai=None)["goi_y"]["A4"] is None)
kiem("bột mà ngày SX chưa có lượt hoàn tất → A4 không gợi ý",
     hs(nsx=date(2026, 7, 9), loai="Bột")["goi_y"]["A4"] is None)
DB["SX Su Co"]["SC-NGAY"] = {"name": "SC-NGAY", "ngay": date(2026, 7, 3), "nguon": "Vòng kiểm QC", "dien_tap": 0,
                             "trang_thai": "Mở", "quyet_dinh_sp": None, "mo_ta": "NC-02 M1 không hút"}
DB["SX Su Co"]["SC-TAP"] = {"name": "SC-TAP", "ngay": NSX, "nguon": "Vòng kiểm QC", "dien_tap": 1,
                            "trang_thai": "Mở", "quyet_dinh_sp": None, "mo_ta": "diễn tập"}
DB["SX Su Co"]["SC-NCC"] = {"name": "SC-NCC", "ngay": NSX, "nguon": "Tiếp nhận NL", "dien_tap": 0,
                            "trang_thai": "Mở", "quyet_dinh_sp": None, "mo_ta": "lô đường"}
h = hs(loai="Bánh")
kiem("A2: sự cố vòng kiểm NGÀY NGHIỀN chưa quyết định sản phẩm → gợi ý Không đạt, ghi số phiếu "
     "(diễn tập / nguồn khác không gắn lô thì không tính)",
     h["goi_y"]["A2"] == "Không đạt" and h["su_co"]["A2"] == "SC-NGAY" and "SC-TAP" not in h["can_cu"]["A2"]
     and "SC-NCC" not in h["can_cu"]["A2"] and "CHƯA quyết định" in h["can_cu"]["A2"], h)
DB["SX Su Co"]["SC-NGAY"]["quyet_dinh_sp"] = "Không ảnh hưởng sản phẩm"
h = hs(loai="Bánh")
kiem("… đã quyết định sản phẩm → A2 Đạt, vẫn ghi số phiếu",
     h["goi_y"]["A2"] == "Đạt" and h["su_co"]["A2"] == "SC-NGAY", h)
SU_CO_LO[:] = [{"parent": "SC-NCC", "parenttype": "SX Su Co", "batch": "SEN-HSD270405"}]
h = hs(item="TP-SEN", batch="SEN-HSD270405", loai="Bánh")
kiem("A2: sự cố GẮN LÔ (bảng Lô liên quan) chưa quyết định → Không đạt, chỉ đúng phiếu đó",
     h["goi_y"]["A2"] == "Không đạt" and h["su_co"]["A2"] == "SC-NCC", h)
SU_CO_LO.clear()
for k in ("SC-NGAY", "SC-TAP", "SC-NCC"):
    del DB["SX Su Co"][k]

print("\n-- A3: nguyên liệu theo chứng từ kho ngày SX --")
A3 = lambda: A._tra_nguon(NSX)   # noqa: E731
ng = A3()
kiem("tra chứng từ ngày SX: lô bột nền → ngày rang + ngày nghiền (phiếu SINH RA lô, bỏ phiếu đã huỷ); lá → NCC",
     ng["co"] and ng["rang"] == {"R-0702": "2026-07-02"} and ng["nghien"] == {"R-0702": {"2026-07-03"}}
     and set(ng["nvl"]) == {"DX-NCC-01", "DUONG-01"} and ng["khong_lo"] == ["Túi PE"], ng)
SE.append({"name": "SE-NGHIEN2-R0702", "posting_date": date(2026, 7, 4), "docstatus": 1})
SED.append({"parent": "SE-NGHIEN2-R0702", "batch_no": "R-0702", "is_finished_item": 1, "docstatus": 1})
DB["SX Kiem Tra Xuat Xuong"]["XX-TAM"] = {"doctype": "SX Kiem Tra Xuat Xuong", "name": "XX-TAM", "san_pham": "TP-SEN",
                                          "hsd": "2027-04-05", "nsx": "2026-07-05", "ds_muc": [{"ma": "A1"}]}
tam = _get_doc("SX Kiem Tra Xuat Xuong", "XX-TAM")
A._goi_y(tam, lap=True)
kiem("lô bột nền nghiền hai ngày → A1 xét CẢ HAI ngày, ô ngày nghiền ghi ngày sớm nhất",
     tam["ngay_nghien"] == "2026-07-03" and "nghiền 03/07/2026" in tam["ds_muc"][0]["can_cu"]
     and "nghiền 04/07/2026: 0 lượt (thiếu)" in tam["ds_muc"][0]["can_cu"], tam["ds_muc"][0]["can_cu"])
del DB["SX Kiem Tra Xuat Xuong"]["XX-TAM"]
SE.pop(); SED.pop()
CAY["SE-T2-0705"][1]["ncc"] = {"ket_luan": "Cách ly"}
h = {"goi_y": {}, "can_cu": {}}
A._a3(h, A3())
kiem("một lô nguyên liệu Cách ly → A3 gợi ý Không đạt, nêu lô",
     h["goi_y"]["A3"] == "Không đạt" and "Đường (DUONG-01): Cách ly" in h["can_cu"]["A3"], h)
CAY["SE-T2-0705"][1]["ncc"] = None
h = {"goi_y": {}, "can_cu": {}}
A._a3(h, A3())
kiem("lô chưa có kết luận tiếp nhận → A3 không gợi ý, nêu lô",
     h["goi_y"]["A3"] is None and "chưa có kết luận tiếp nhận: Đường (DUONG-01)" in h["can_cu"]["A3"], h)
CAY["SE-T2-0705"][1]["ncc"] = {"ket_luan": "Đạt"}
h = {"goi_y": {}, "can_cu": {}}
A._a3(h, A._tra_nguon(date(2026, 7, 9)))
goc_cay = _Ctx.nguyen_lieu_cua_se
_Ctx.nguyen_lieu_cua_se = lambda self, se, v, sau: (_ for _ in ()).throw(KeyError("custom_ngay_sx"))
ng = A._tra_nguon(NSX)
kiem("site thiếu field sản xuất (tra chứng từ lỗi) → không văng lỗi, coi như chưa có chứng từ (không giữ nửa vời)",
     ng == {"co": False, "rang": {}, "nghien": {}, "nvl": {}, "khong_lo": []}, ng)
_Ctx.nguyen_lieu_cua_se = goc_cay
kiem("ngày SX chưa chốt Ghi sổ (không có phiếu kho) → A3 không gợi ý, QC tự đối chiếu",
     h["goi_y"]["A3"] is None and "chưa chốt Ghi sổ" in h["can_cu"]["A3"]
     and A._tra_nguon(None)["co"] is False, h)

# ═══ 2. Gửi duyệt ═════════════════════════════════════════════════════════
print("\n-- ghi phiếu: ô mẫu, KAD, kết luận --")
loi = thu(lambda: A.gui_duyet(d["name"]))
kiem("chưa chấm → chặn, nói mục chưa chấm VÀ dòng chưa đủ 5 mẫu",
     loi and "Còn mục chưa chấm: A1, A2, A3, A4, B1" in loi and "Chưa ghi đủ 5 mẫu: B1, B2" in loi, loi or "")
kiem("KAD chỉ ở A4 (bản giấy): KAD ở A1 → chặn", "A1" in (thu(lambda: A.luu_phieu(d["name"], json.dumps(
    {"ds_muc": [{"ma": "A1", "ket_qua": "Không áp dụng"}]}))) or ""))
kiem("ô mẫu lạ → chặn: B1 'X', B2 âm, B2 chữ",
     all(thu(lambda v=v, ma=ma: A.luu_phieu(d["name"], json.dumps({"ds_muc": [{"ma": ma, "mau": [v]}]})))
         for ma, v in (("B1", "X"), ("B2", "-5"), ("B2", "abc"))))
A.luu_phieu(d["name"], json.dumps({"ds_muc": [{"ma": "B2", "mau": ["150,5", " 151 ", "", "149.80", "0150"]},
                                              {"ma": "B3", "mau": ["đ", "d", "k", "Đ"]}]}))
kiem("ô mẫu chuẩn hoá: số cân dấu phẩy → chấm, bỏ số 0 thừa; Đ / K không phân biệt hoa thường; thiếu ô = trống",
     A.xem_phieu(d["name"])["ds_muc"][6]["mau"] == ["150.5", "151", "", "149.8", "150"]
     and A.xem_phieu(d["name"])["ds_muc"][7]["mau"] == ["Đ", "Đ", "K", "Đ", ""])
DB["SX Su Co"]["SC-A3"] = {"name": "SC-A3", "ngay": HOM_NAY, "nguon": "Tiếp nhận NL", "dien_tap": 0}
A.luu_phieu(d["name"], json.dumps({"ds_muc": [{"ma": "A1", "mau": ["Đ", "K"]}, {"ma": "A3", "su_co": "SC-A3"}]}))
kiem("ô mẫu chỉ ở mục B, số phiếu chỉ ở A2 — gửi kèm mục khác thì bỏ qua",
     dong(d["name"], "A1").get("mau_1") in (None, "") and dong(d["name"], "A3").get("su_co") in (None, ""))
del DB["SX Su Co"]["SC-A3"]
kiem("kết luận lạ → chặn", thu(lambda: A.luu_phieu(d["name"], json.dumps({"ket_luan": "Tốt"}))) is not None)
kiem("ngày nghiền ở tương lai → chặn", thu(lambda: A.luu_phieu(d["name"], json.dumps(
    {"ngay_nghien": "2026-10-09"}))) is not None)
kiem("số phiếu sự cố không có thật → chặn", thu(lambda: A.luu_phieu(d["name"], json.dumps(
    {"su_co": "SC-KHONG-CO"}))) is not None)

print("\n-- gửi duyệt: đủ mục, đủ mẫu, kết luận khớp --")
loi = thu(lambda: A.gui_duyet(d["name"], cham_moi(d, mau_k=("B3",))))
kiem("mẫu K mà kết luận dòng Đạt → chặn", loi and "Có mẫu K mà kết luận dòng Đạt: B3" in loi, loi or "")
loi = thu(lambda: A.gui_duyet(d["name"], cham_moi(d, hong=("B3",), mau_k=("B3",))))
kiem("Cho xuất xưởng mà có mục Không đạt → chặn",
     loi and "Cho xuất xưởng phải đạt toàn bộ mục A và B — mục Không đạt: B3" in loi, loi or "")
loi = thu(lambda: A.gui_duyet(d["name"], cham_moi(d, kl="Giữ lại chờ xử lý")))
kiem("Giữ lại mà không có mục Không đạt, không ghi lý do → chặn", loi and "ghi lý do" in loi, loi or "")
p = json.loads(cham_moi(d))
p["ds_muc"][9]["mau"] = ["Đ", "Đ", "Đ", "Đ"]
loi = thu(lambda: A.gui_duyet(d["name"], json.dumps(p)))
kiem("thiếu một mẫu (4/5) → chặn", loi and "Chưa ghi đủ 5 mẫu: B5" in loi, loi or "")
kiem("chưa gửi được thì không lập phiếu sự cố", not DB["SX Su Co"])
r = A.gui_duyet(d["name"], cham_moi(d))
kiem("đủ → Chờ duyệt, ghi QC kiểm + giờ, kết luận Cho xuất xưởng",
     r["trang_thai"] == "Chờ duyệt" and r["qc_kiem"] == "qc@x" and r["ket_luan"] == "Cho xuất xưởng")
kiem("Cho xuất xưởng → không lập phiếu sự cố", not DB["SX Su Co"] and not r["su_co"])
kiem("phiếu chờ duyệt: QC không sửa thẳng được", thu(lambda: A.luu_phieu(d["name"], cham_moi(d))) is not None)
kiem("… người kiểm thấy 'không tự duyệt', không có nút duyệt", r["tu_kiem"] and not r["duyet"])

# ═══ 3. Duyệt, ký Quản lý sản xuất ════════════════════════════════════════
print("\n-- ô ký Quản lý sản xuất (không bắt buộc để duyệt) --")
try:
    A.ky_qlsx(d["name"])
    kiem("QC ký ô QLSX → chặn", False)
except frappe.PermissionError:
    kiem("QC ký ô QLSX → chặn (PermissionError)", True)
vai("Production Manager", u="qlsx@x")
kiem("QLSX thấy nút ký", A.xem_phieu(d["name"])["ky_qlsx"] is True)
r = A.ky_qlsx(d["name"])
kiem("QLSX ký → ghi người + giờ", r["qlsx"] == "qlsx@x" and r["qlsx_luc"] and r["ky_qlsx"] is False)
kiem("ký lần hai → chặn", "đã có chữ ký" in (thu(lambda: A.ky_qlsx(d["name"])) or ""))
kiem("phiếu Nháp → QLSX chưa ký được", "gửi duyệt" in (thu(lambda: A.ky_qlsx(d2["name"])) or ""))

print("\n-- duyệt: Ban ISO / người được giao, KHÔNG phải QC đã kiểm --")
vai("SX QC", u="qc2@x")
loi = thu(lambda: A.duyet_phieu(d["name"]))
kiem("QC KHÁC (không phải người kiểm, không phải Ban ISO) duyệt → chặn", loi and "Ban ISO" in loi, loi or "")
vai("SX QC")
vai("ISO Manager", u="qc@x")
loi = thu(lambda: A.duyet_phieu(d["name"]))
kiem("có role Ban ISO nhưng CHÍNH là người kiểm lô → vẫn chặn", loi and "không tự duyệt" in loi, loi or "")
vai("ISO Manager")
kiem("Ban ISO thấy nút duyệt", A.xem_phieu(d["name"])["duyet"] is True)
loi = thu(lambda: A.duyet_phieu(d["name"], 0))
kiem("trả lại không ý kiến → chặn", loi and "ý kiến" in loi, loi or "")
A.duyet_phieu(d["name"], 0, "Cân lại khối lượng 5 mẫu")
x = DB["SX Kiem Tra Xuat Xuong"][d["name"]]
kiem("trả lại → QC sửa được lại; chữ ký QLSX xoá (nội dung sắp đổi)",
     x["trang_thai"] == "Trả lại" and not x["qlsx"] and not x["qlsx_luc"])
vai("SX QC")
kiem("… QC thấy phiếu sửa được", A.xem_phieu(d["name"])["sua"] is True)
A.gui_duyet(d["name"], cham_moi(d))
vai("ISO Manager", u="truong.ban@x")
CAI_DAT_QC["nguoi_duyet_xuat_xuong"] = [Doc(user="pho.qc@x")]
vai("SX QC", u="pho.qc@x")
kiem("người được GIAO (không phải người kiểm) duyệt được", thu(lambda: A.duyet_phieu(d["name"])) is None
     and DB["SX Kiem Tra Xuat Xuong"][d["name"]]["nguoi_duyet"] == "pho.qc@x")
CAI_DAT_QC.clear()
vai("Production Manager", u="qlsx@x")
kiem("QLSX ký được cả sau khi duyệt (không đổi nội dung phiếu đã khoá)",
     thu(lambda: A.ky_qlsx(d["name"])) is None and DB["SX Kiem Tra Xuat Xuong"][d["name"]]["qlsx"] == "qlsx@x")
vai("SX QC")
kiem("phiếu đã duyệt: QC không sửa / không lưu được",
     thu(lambda: A.luu_phieu(d["name"], cham_moi(d))) is not None)
dd = _get_doc("SX Kiem Tra Xuat Xuong", d["name"])
dd.ghi_chu = "sửa lén trên Desk"
kiem("… kể cả sửa trên Desk", thu(lambda: dd.save()) is not None)
vai("SX QC", u="qc2@x")
kiem("duyệt phiếu không ở trạng thái chờ → chặn (QC khác cũng vậy)", thu(lambda: A.duyet_phieu(d["name"])) is not None)

vai("ISO Manager")
loi = thu(lambda: A.duyet_phieu(d2["name"]))
kiem("Ban ISO duyệt phiếu còn Nháp (QC chưa gửi) → chặn", loi and "chờ duyệt" in loi, loi or "")

print("\n-- Giữ lại chờ xử lý: phiếu sự cố lúc gửi, lô vẫn bị chặn, kiểm lại trên phiếu mới --")
vai("SX QC")
r2 = A.gui_duyet(d2["name"], cham_moi(d2, kl="Giữ lại chờ xử lý", hong=("B4",), ghi_chu="Dán lại nhãn"))
sc = DB["SX Su Co"].get(r2["su_co"] or "", {})
kiem("Giữ lại → app lập BM.08.02 NGAY lúc gửi duyệt (nguồn Kiểm tra xuất xưởng, mức Thường, mục hỏng, lô theo HSD)",
     sc.get("nguon") == "Kiểm tra xuất xưởng" and sc.get("muc_do") == "Thường" and d2["name"] in sc.get("mo_ta", "")
     and "B4" in sc["mo_ta"] and "Dán lại nhãn" in sc["mo_ta"] and "HSD 05/04/2027" in sc.get("lo_anh_huong", ""),
     sc)
vai("ISO Manager")
A.duyet_phieu(d2["name"], 1, "Đồng ý giữ lại, dán lại nhãn")
kiem("duyệt Giữ lại → không lập thêm phiếu sự cố", len(DB["SX Su Co"]) == 1)
kiem("lô Giữ lại vẫn bị chặn như chưa duyệt",
     [(i, h) for i, h, _p in XX.chua_duyet([("TP-DUA", "2027-04-05")])] == [("TP-DUA", "2027-04-05")]
     and XX.mo_ta(XX.theo_lo([("TP-DUA", "2027-04-05")])[("TP-DUA", "2027-04-05")])
     == "đã duyệt — Giữ lại chờ xử lý")
vai("SX QC")
d3 = A.lap_phieu("TP-DUA", "2027-04-05")
x3 = DB["SX Kiem Tra Xuat Xuong"][d3["name"]]
kiem("sau Giữ lại: lập phiếu KIỂM LẠI được; A2 thấy phiếu sự cố của lần kiểm trước (chưa quyết định → Không đạt)",
     d3["name"] != d2["name"] and dong(d3["name"], "A2")["goi_y"] == "Không đạt"
     and dong(d3["name"], "A2")["su_co"] == r2["su_co"], dong(d3["name"], "A2"))
kiem("… danh sách chọn phiếu sự cố của lô có phiếu đó",
     [x["name"] for x in d3["su_co_lo"]] == [r2["su_co"]], d3["su_co_lo"])
vai("ISO Manager")
cu2 = _get_doc("SX Kiem Tra Xuat Xuong", d2["name"])
cu2.y_kien_duyet = "Đồng ý giữ lại — đã dán lại nhãn 40 hộp"
kiem("lưu lại phiếu Giữ lại cũ (đã có phiếu kiểm lại) → không bị coi là phiếu trùng", thu(cu2.save) is None)
vai("SX QC")
DB["SX Su Co"][r2["su_co"]]["quyet_dinh_sp"] = "Dùng lại sau xử lý"
DB["SX Su Co"][r2["su_co"]]["trang_thai"] = "Đóng"
LUU_MAU.append({"name": "LM-0009", "san_pham": "TP-DUA", "hsd": date(2027, 4, 5)})
DB["SX Su Co"]["SC-QC-CHON"] = {"name": "SC-QC-CHON", "ngay": HOM_NAY, "nguon": "Phát hiện khác", "dien_tap": 0}
r3 = A.tra_ho_so(d3["name"], json.dumps({"ds_muc": [{"ma": "A1", "ket_qua": "Đạt"}, {"ma": "A2", "su_co": "SC-QC-CHON"}],
                                         "ngay_rang": "2026-07-01", "ngay_nghien": "2026-07-04"}))
kiem("TRA LẠI HỒ SƠ: không đè số phiếu QC đã chọn ở A2; xét đúng ngày nghiền QC sửa",
     r3["ds_muc"][1]["su_co"] == "SC-QC-CHON" and "nghiền 04/07/2026" in r3["ds_muc"][0]["can_cu"]
     and "nghiền 03/07/2026" not in r3["ds_muc"][0]["can_cu"], r3["ds_muc"][:2])
kiem("TRA LẠI HỒ SƠ: lưu cái QC đang chấm, dùng ngày QC sửa, A2 thành Đạt khi đã quyết định, A5 chấm khi vừa lấy mẫu",
     r3["ds_muc"][0]["ket_qua"] == "Đạt" and r3["ngay_rang"] == "2026-07-01"
     and "rang 01/07/2026: 0 lượt (thiếu)" in r3["ds_muc"][0]["can_cu"] and r3["ds_muc"][0]["goi_y"] == ""
     and r3["ds_muc"][1]["goi_y"] == "Đạt" and r3["ds_muc"][4]["ket_qua"] == "Đạt", r3["ds_muc"][:5])
kiem("tra lại hồ sơ không áp cho phiếu đã gửi", thu(lambda: A.tra_ho_so(d["name"])) is not None)
d5 = A.lap_phieu("TP-DUA", "2027-03-03")
A.gui_duyet(d5["name"], cham_moi(d5, kl="Giữ lại chờ xử lý", hong=("B6",)))
vai("ISO Manager")
A.duyet_phieu(d5["name"], 0, "Thùng đủ — kiểm lại B6")
vai("SX QC")
sc5 = DB["SX Kiem Tra Xuat Xuong"][d5["name"]]["su_co"]
r5 = A.tra_ho_so(d5["name"])
kiem("phiếu bị trả lại sau Giữ lại: phiếu sự cố CỦA CHÍNH NÓ vẫn tính ở A2 (phải có quyết định SP rồi mới cho xuất)",
     r5["ds_muc"][1]["goi_y"] == "Không đạt" and sc5 in r5["ds_muc"][1]["can_cu"], r5["ds_muc"][1])
del DB["SX Kiem Tra Xuat Xuong"][d5["name"]], DB["SX Su Co"][sc5]

print("\n-- Không cho xuất: mức Cao, lô huỷ — không lập phiếu kiểm lại --")
d4 = A.lap_phieu("TP-SEN", "2027-02-01")
DB["SX Su Co"]["SC-CO-SAN"] = {"name": "SC-CO-SAN", "ngay": HOM_NAY, "nguon": "Vòng kiểm QC", "dien_tap": 0,
                               "trang_thai": "Mở", "mo_ta": "dị vật"}
n_sc = len(DB["SX Su Co"])
r4 = A.gui_duyet(d4["name"], cham_moi(d4, kl="Không cho xuất", hong=("B1",), mau_k=("B1",), su_co="SC-CO-SAN"))
kiem("QC chọn phiếu sự cố có sẵn → gắn đúng phiếu đó, không lập thêm",
     r4["su_co"] == "SC-CO-SAN" and len(DB["SX Su Co"]) == n_sc)
A.rut_lai(d4["name"])
r4 = A.gui_duyet(d4["name"], cham_moi(d4, kl="Không cho xuất", hong=("B1",), mau_k=("B1",), su_co=""))
sc4 = DB["SX Su Co"].get(r4["su_co"] or "", {})
kiem("bỏ chọn → app lập phiếu mới, Không cho xuất mức Cao", sc4.get("muc_do") == "Cao"
     and "KHÔNG CHO XUẤT" in sc4.get("mo_ta", "") and len(DB["SX Su Co"]) == n_sc + 1, sc4)
vai("ISO Manager")
A.duyet_phieu(d4["name"], 1, "Huỷ lô")
vai("SX QC")
kiem("lô Không cho xuất: bấm KIỂM lại → trả đúng phiếu đã duyệt, không lập phiếu mới",
     A.lap_phieu("TP-SEN", "2027-02-01")["name"] == d4["name"])
loi = thu(lambda: XXC.SXKiemTraXuatXuong({"doctype": "SX Kiem Tra Xuat Xuong", "san_pham": "TP-SEN",
                                          "hsd": "2027-02-01", "trang_thai": "Nháp"}).insert())
kiem("… lập tay trên Desk cũng chặn, nói thu hồi duyệt nếu nhầm",
     loi and "Không cho xuất" in loi and "thu hồi" in loi, loi or "")
kiem("… và vẫn chặn nhập kho / bán", XX.chua_duyet([("TP-SEN", "2027-02-01")]) != [])

DB["SX Kiem Tra Xuat Xuong"]["XX-THU"] = {"name": "XX-THU", "san_pham": "TP-SEN", "hsd": "2027-04-05",
                                           "trang_thai": "Nháp", "ket_luan": "", "creation": "2026-10-09"}
kiem("lô có phiếu Cho xuất xưởng + phiếu mới hơn (dữ liệu nhập tay) → vẫn tính theo phiếu đã duyệt",
     XX.theo_lo([("TP-SEN", "2027-04-05")])[("TP-SEN", "2027-04-05")].name == d["name"])
del DB["SX Kiem Tra Xuat Xuong"]["XX-THU"]

print("\n-- đường Desk: luật gửi duyệt nằm ở controller --")
dk = XXC.SXKiemTraXuatXuong({"doctype": "SX Kiem Tra Xuat Xuong", "san_pham": "TP-DUA", "hsd": "2027-08-08",
                             "trang_thai": "Nháp"})
dk.insert()
for r in dk["ds_muc"]:
    r["ket_qua"] = "Không áp dụng" if r["ma"] in ("A1", "A4") else "Đạt"
    if r["ma"].startswith("B"):
        for i in range(1, 6):
            r[f"mau_{i}"] = "150" if r["ma"] == "B2" else "Đ"
dk["ket_luan"], dk["trang_thai"] = "Cho xuất xưởng", "Chờ duyệt"
loi = thu(dk.save)
kiem("Desk: KAD ngoài A4 → chặn gửi duyệt", loi and "Chỉ A4 được chấm KAD: A1" in loi, loi or "")
dk["ds_muc"][0]["ket_qua"] = "Đạt"
dk["ket_luan"] = "Tốt"
loi = thu(dk.save)
kiem("Desk: kết luận ngoài ba lựa chọn → chặn", loi and "Kết luận không hợp lệ: Tốt" in loi, loi or "")
dk["ket_luan"] = "Đạt"
kiem("Desk: ghi kết luận kiểu cũ 'Đạt' → đổi thành Cho xuất xưởng, gửi được",
     thu(dk.save) is None and DB["SX Kiem Tra Xuat Xuong"][dk["name"]]["ket_luan"] == "Cho xuất xưởng"
     and DB["SX Kiem Tra Xuat Xuong"][dk["name"]]["trang_thai"] == "Chờ duyệt")
del DB["SX Kiem Tra Xuat Xuong"][dk["name"]]

print("\n-- phiếu cũ (trước D159): giữ mục đã ghi, kết luận đổi bộ chữ --")
MUC_CU = [{"ma": str(i), "noi_dung": f"Mục tạm {i}", "ket_qua": "Đạt", "ghi_chu": ""} for i in range(1, 9)]
DB["SX Kiem Tra Xuat Xuong"]["XX-CU-1"] = {
    "doctype": "SX Kiem Tra Xuat Xuong", "name": "XX-CU-1", "san_pham": "TP-DUA", "hsd": "2027-01-15",
    "ten_san_pham": "Bánh đậu xanh dừa", "trang_thai": "Đã duyệt", "ket_luan": "Đạt", "so_mau": 3,
    "qc_kiem": "qc@x", "nguoi_duyet": "iso@x", "creation": "2026-10-08", "ds_muc": [dict(r) for r in MUC_CU]}
DB["SX Kiem Tra Xuat Xuong"]["XX-CU-2"] = {
    "doctype": "SX Kiem Tra Xuat Xuong", "name": "XX-CU-2", "san_pham": "TP-DUA", "hsd": "2027-01-16",
    "ten_san_pham": "Bánh đậu xanh dừa", "trang_thai": "Nháp", "ket_luan": "", "so_mau": 0,
    "creation": "2026-10-08", "ds_muc": [dict(r, ket_qua="") for r in MUC_CU]}
kiem("phiếu cũ 'Đạt' chưa chạy patch → vẫn tính là Cho xuất xưởng (không chặn nhầm lô đã duyệt)",
     XX.chua_duyet([("TP-DUA", "2027-01-15")]) == [])
kiem("… danh sách màn hình đọc chữ mới", next(x for x in A.ds_xuat_xuong()["phieu"] if x["name"] == "XX-CU-1")
     ["ket_luan"] == "Cho xuất xưởng")
P3.execute()
kiem("patch d159: Đạt → Cho xuất xưởng (phiếu khác để nguyên); chạy lại vô hại",
     DB["SX Kiem Tra Xuat Xuong"]["XX-CU-1"]["ket_luan"] == "Cho xuất xưởng"
     and DB["SX Kiem Tra Xuat Xuong"][d2["name"]]["ket_luan"] == "Giữ lại chờ xử lý"
     and thu(P3.execute) is None and "sx.patches.d159_xuat_xuong_lan_bh01" in open("sx/patches.txt", encoding="utf-8").read())
DB["SX Kiem Tra Xuat Xuong"]["XX-CU-3"] = dict(DB["SX Kiem Tra Xuat Xuong"]["XX-CU-1"], name="XX-CU-3",
                                               hsd="2027-01-17", ket_luan="Không đạt")
P3.execute()
kiem("patch d159: Không đạt → Không cho xuất", DB["SX Kiem Tra Xuat Xuong"]["XX-CU-3"]["ket_luan"] == "Không cho xuất")
c2 = A.xem_phieu("XX-CU-2")
kiem("mở phiếu cũ → form cũ (moi = False), giữ 8 mục tạm", c2["moi"] is False and len(c2["ds_muc"]) == 8)
kiem("phiếu cũ không tra lại hồ sơ theo bản giấy", "trước lần BH 01" in (thu(lambda: A.tra_ho_so("XX-CU-2")) or ""))
loi = thu(lambda: A.gui_duyet("XX-CU-2", json.dumps({"ds_muc": [{"ma": str(i), "ket_qua": "Đạt"} for i in range(1, 9)],
                                                      "ket_luan": "Cho xuất xưởng"})))
kiem("phiếu cũ gửi duyệt theo luật cũ: thiếu số mẫu → chặn", loi and "số mẫu" in loi, loi or "")
loi = thu(lambda: A.gui_duyet("XX-CU-2", json.dumps({
    "ds_muc": [{"ma": str(i), "ket_qua": "Không đạt" if i == 3 else "Đạt"} for i in range(1, 9)],
    "ket_luan": "Cho xuất xưởng", "so_mau": 2})))
kiem("phiếu cũ: Cho xuất xưởng mà có mục Không đạt → chặn", loi and "Cho xuất xưởng nhưng có mục Không đạt" in loi,
     loi or "")
loi = thu(lambda: A.gui_duyet("XX-CU-2", json.dumps({
    "ds_muc": [{"ma": str(i), "ket_qua": "Không áp dụng" if i == 1 else "Đạt"} for i in range(1, 9)],
    "ket_luan": "Cho xuất xưởng", "so_mau": 2})))
kiem("… KAD ở phiếu cũ vẫn ghi được như trước; đủ thì qua",
     loi is None and DB["SX Kiem Tra Xuat Xuong"]["XX-CU-2"]["trang_thai"] == "Chờ duyệt"
     and DB["SX Kiem Tra Xuat Xuong"]["XX-CU-2"]["so_mau"] == 2, loi or "")
for k in ("XX-CU-1", "XX-CU-2", "XX-CU-3"):
    del DB["SX Kiem Tra Xuat Xuong"][k]

# ═══ 4. Chốt chặn nhập kho / bán ═══════════════════════════════════════════
print("\n-- chặn nhập kho lô chưa duyệt --")


def phieu(ngay="2026-10-08", *dong):
    return Doc(ngay=ngay, dong=[Doc(item=i, ten=i, hsd=h, so_dem=s) for i, h, s in dong])


kiem("lô đã duyệt Đạt → nhập kho được",
     thu(lambda: A.chan_nhap_kho(phieu("2026-10-08", ("TP-SEN", "2027-04-05", 100)))) is None)
loi = thu(lambda: A.chan_nhap_kho(phieu("2026-10-08", ("TP-SEN", "2027-04-05", 100),
                                        ("TP-DUA", "2027-04-05", 50), ("TP-DUA", "2027-06-01", 10))))
kiem("lô chưa duyệt → chặn, nói từng lô đang ở bước nào (lô đã duyệt TP-SEN không bị kể)",
     loi and "QC đang kiểm" in loi and "chưa kiểm xuất xưởng" in loi and "05/04/2027" in loi
     and "TP-DUA" in loi and "TP-SEN" not in loi, loi or "")
kiem("dòng số đếm 0 → không xét",
     thu(lambda: A.chan_nhap_kho(phieu("2026-10-08", ("TP-DUA", "2027-06-01", 0)))) is None)
kiem("phiếu nhập TRƯỚC ngày áp dụng → không chặn",
     thu(lambda: A.chan_nhap_kho(phieu("2026-10-07", ("TP-DUA", "2027-06-01", 10)))) is None)
SETTINGS["chan_nhap_chua_xuat_xuong"] = 0
kiem("tắt ở SX Settings → không chặn",
     thu(lambda: A.chan_nhap_kho(phieu("2026-10-08", ("TP-DUA", "2027-06-01", 10)))) is None)
SETTINGS["chan_nhap_chua_xuat_xuong"] = 1
src = open("sx/sx/doctype/sx_phieu_nhap_tp/sx_phieu_nhap_tp.py", encoding="utf-8").read()
kiem("phiếu nhập kho TP: before_submit gọi kiểm xuất xưởng SAU khi điền HSD",
     src.index("self.kiem_hsd()") < src.index("self.kiem_xuat_xuong()") < src.index("self.kiem_tran_da_cham()")
     and "chan_nhap_kho(self)" in src)

print("\n-- chặn bán lô chưa duyệt --")


def hd(lo, **k):
    return Doc(doctype=k.pop("dt", "Sales Invoice"), update_stock=k.pop("us", 1), is_return=k.pop("tra", 0),
               items=[Doc(idx=1, item_code="x", batch_no=lo, warehouse="Kho TP")])


kiem("bán lô đã duyệt → qua", thu(lambda: A.kiem_ban(hd("SEN-HSD270405"))) is None)
BATCH.append({"name": "DUA-HSD270405", "item": "TP-DUA", "item_name": "Bánh đậu xanh dừa",
              "expiry_date": date(2027, 4, 5), "creation": "2026-10-09 08:00"})
loi = thu(lambda: A.kiem_ban(hd("DUA-HSD270405")))
kiem("bán lô TP chưa duyệt (tạo từ ngày áp dụng) → chặn", loi and "chưa được duyệt xuất xưởng" in loi, loi or "")
kiem("Delivery Note / POS cũng chặn", thu(lambda: A.kiem_ban(hd("DUA-HSD270405", dt="Delivery Note"))) is not None
     and thu(lambda: A.kiem_ban(hd("DUA-HSD270405", dt="POS Invoice"))) is not None)
kiem("lô tồn cũ (tạo trước ngày áp dụng) → qua", thu(lambda: A.kiem_ban(hd("SEN-CU-270101"))) is None)
BATCH.append({"name": "DUA-HSD270301", "item": "TP-DUA", "item_name": "Bánh đậu xanh dừa",
              "expiry_date": date(2027, 3, 1), "creation": "2026-10-09 09:00", "custom_kiem_ke": "KK-2026-001"})
kiem("lô theo HSD nhận hàng tồn cũ lúc chốt kiểm kê (D154, tạo sau ngày áp dụng) → qua",
     thu(lambda: A.kiem_ban(hd("DUA-HSD270301"))) is None)
kiem("hàng không phải thành phẩm → qua", thu(lambda: A.kiem_ban(hd("BOT-NEN-01"))) is None)
kiem("trả hàng / hoá đơn không trừ kho → qua", thu(lambda: A.kiem_ban(hd("DUA-HSD270405", tra=1))) is None
     and thu(lambda: A.kiem_ban(hd("DUA-HSD270405", us=0))) is None)
SETTINGS["chan_nhap_chua_xuat_xuong"] = 0
kiem("tắt ở SX Settings → qua", thu(lambda: A.kiem_ban(hd("DUA-HSD270405"))) is None)
SETTINGS["chan_nhap_chua_xuat_xuong"] = 1
kiem("trạng thái lô cho màn nhập kho: đã duyệt / chưa",
     A.trang_thai_cac_lo([("TP-SEN", "2027-04-05"), ("TP-DUA", "2027-06-01")])
     == {("TP-SEN", "2027-04-05"): {"name": d["name"], "duyet": True, "chu": "đã duyệt — Cho xuất xưởng"},
         ("TP-DUA", "2027-06-01"): {"name": "", "duyet": False, "chu": "chưa kiểm xuất xưởng"}})

# ═══ 5. Danh sách màn hình ════════════════════════════════════════════════
print("\n-- danh sách lô chờ kiểm --")
CON.update({"TP-SEN": [{"hsd": "2027-04-05", "nsx": "2026-07-06", "con": 20}],
            "TP-DUA": [{"hsd": "2027-06-01", "nsx": "2026-09-01", "con": 30},
                       {"hsd": None, "nsx": None, "con": 3}]})
NHAP_NHAP[:] = [{"parenttype": "SX Phieu Nhap TP", "docstatus": 0, "item": "TP-DUA", "hsd": "2027-06-02",
                 "so_dem": 0, "so_lap": 12}]
ds = A.ds_xuat_xuong()
cho = {(c["item"], c["hsd"]): c for c in ds["cho_kiem"]}
kiem("chờ kiểm = hàng đã vào hộp chưa nhập kho + dòng phiếu nhập nháp (hộp Tết…)",
     set(cho) == {("TP-DUA", "2027-06-01"), ("TP-DUA", "2027-06-02")}, sorted(cho))
kiem("lô đã có phiếu hiệu lực (TP-SEN đã duyệt) không hiện lại", ("TP-SEN", "2027-04-05") not in cho)
kiem("số lượng + nguồn", cho[("TP-DUA", "2027-06-01")]["so_luong"] == 30
     and cho[("TP-DUA", "2027-06-02")]["so_luong"] == 12)
kiem("cờ quyền: QC ghi được, không duyệt", (ds["duoc_ghi"], ds["duoc_duyet"]) == (True, False))
vai("SX Vao Hop")
kiem("người ngoài QC không vào được", thu(lambda: A.ds_xuat_xuong()) is not None)
vai("ISO Manager")
kiem("Ban ISO không tự lập phiếu kiểm (việc của QC)", thu(lambda: A.lap_phieu("TP-DUA", "2027-06-01")) is not None)
vai("SX QC")
if jinja2:
    def chu_in(name):
        html = A.in_phieu(name)
        return re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", html.split("</style>")[1]).replace("&nbsp;", " "))

    chu = chu_in(d["name"])
    kiem("phiếu in lần BH 01: đầu phiếu như giấy (mã, lần BH, quy cách, NSX, HSD, ngày nghiền / rang)",
         "BM.08.04" in chu and "Lần BH: 01 — 21/9/2026" in chu and "Bánh đậu xanh sen" in chu
         and "Hộp 250 g" in chu and "05/07/2026" in chu and "05/04/2027" in chu
         and "Ngày nghiền bột đậu 03/07/2026; ngày rang 02/07/2026" in chu, chu[:400])
    kiem("… A1–A5 có ô Đ / K (A4 thêm KAD) đã đánh dấu, B1–B6 đủ 5 mẫu số cân",
         "A4" in chu and "oPRP-9" in chu and "☑ KAD" in chu and "☑ Đ" in chu
         and "150.5 151 149.8 150 150.2" in chu and "Mẫu 5" in chu, chu)
    kiem("… kết luận ba lựa chọn, đánh dấu đúng Cho xuất xưởng; ba ô ký (QC, Quản lý sản xuất, người duyệt)",
         "☑ Cho xuất xưởng" in chu and "☐ Giữ lại chờ xử lý" in chu and "☐ Không cho xuất" in chu
         and "Quản lý sản xuất" in chu and "qlsx@x" in chu and "pho.qc@x" in chu
         and "Người duyệt cho xuất (TB ISO hoặc người được giao)" in chu, chu[-700:])
    chu = chu_in(d4["name"])
    kiem("phiếu Không cho xuất in số BM.08.02 ở đúng dòng kết luận",
         "☑ Không cho xuất" in chu and f"BM.08.02 số {DB['SX Kiem Tra Xuat Xuong'][d4['name']]['su_co']}" in chu, chu[-700:])
    DB["SX Kiem Tra Xuat Xuong"]["XX-CU-9"] = {
        "doctype": "SX Kiem Tra Xuat Xuong", "name": "XX-CU-9", "san_pham": "TP-DUA", "hsd": "2027-01-15",
        "ten_san_pham": "Bánh đậu xanh dừa", "trang_thai": "Đã duyệt", "ket_luan": "Đạt", "so_mau": 3,
        "qc_kiem": "qc@x", "nguoi_duyet": "iso@x", "ho_so": "BM.08.01 ngày 05/07: 3 lượt",
        "ds_muc": [{"ma": "1", "noi_dung": "Hồ sơ lô: vòng kiểm", "ket_qua": "Đạt", "ghi_chu": "đủ"}]}
    chu = chu_in("XX-CU-9")
    kiem("phiếu cũ in đúng bố cục cũ, mục đã ghi, kết luận đổi chữ",
         "Mẫu tạm trước lần BH 01" in chu and "Hồ sơ lô: vòng kiểm" in chu and "Cho xuất xưởng — ĐÃ DUYỆT" in chu
         and "Lần BH: 01" not in chu, chu)
    del DB["SX Kiem Tra Xuat Xuong"]["XX-CU-9"]

# ═══ 6. Nhắc, patch, cấu hình ═════════════════════════════════════════════
print("\n-- nhắc, patch, cấu hình --")
kiem("nhắc: phiếu chờ duyệt hôm nay → mức thường", NH._nhac_xuat_xuong(HOM_NAY, {"cho_duyet": 2, "lau_nhat": "2026-10-08"})[0]["muc_do"] == "thuong")
kiem("nhắc: chờ từ hôm qua → mức CAO (hàng đứng ngoài kho)",
     NH._nhac_xuat_xuong(HOM_NAY, {"cho_duyet": 1, "lau_nhat": "2026-10-07"})[0]["muc_do"] == "cao")
kiem("không có phiếu chờ → không nhắc", NH._nhac_xuat_xuong(HOM_NAY, {}) == [])
SETTINGS["xuat_xuong_tu_ngay"] = None
P.execute()
kiem("patch: chưa khai ngày áp dụng → đặt hôm nay (tồn cũ không bị chặn)", SETTINGS["xuat_xuong_tu_ngay"] == "2026-10-08")
SETTINGS["xuat_xuong_tu_ngay"] = date(2026, 9, 1)
P.execute()
kiem("patch: đã khai → để nguyên", SETTINGS["xuat_xuong_tu_ngay"] == date(2026, 9, 1))
kiem("patch có trong patches.txt", "sx.patches.d137_xuat_xuong" in open("sx/patches.txt", encoding="utf-8").read())
P2 = nap("sx.patches.d152_bu_ngay_xuat_xuong", "sx/patches/d152_bu_ngay_xuat_xuong.py")
SETTINGS["xuat_xuong_tu_ngay"] = None
P2.execute()
kiem("D152 chạy bù (site đã chạy D137 bản hỏng): ngày áp dụng còn trống → đặt hôm nay; SX Settings là "
     "Single (không có bảng riêng) vẫn chạy", SETTINGS["xuat_xuong_tu_ngay"] == "2026-10-08")
SETTINGS["xuat_xuong_tu_ngay"] = date(2026, 9, 1)
P2.execute()
kiem("D152: đã khai → để nguyên", SETTINGS["xuat_xuong_tu_ngay"] == date(2026, 9, 1)
     and "sx.patches.d152_bu_ngay_xuat_xuong" in open("sx/patches.txt", encoding="utf-8").read())
j = {f["fieldname"]: f for f in json.load(open(
    "sx/qc/doctype/sx_kiem_tra_xuat_xuong/sx_kiem_tra_xuat_xuong.json", encoding="utf-8"))["fields"]}
kiem("DocType: trạng thái khớp code, người kiểm / duyệt / ký QLSX chỉ đọc",
     j["trang_thai"]["options"].split("\n") == [XX.NHAP, XX.CHO, XX.DUYET, XX.TRA]
     and all(j[f].get("read_only") for f in ("qc_kiem", "nguoi_duyet", "duyet_luc", "kiem_luc", "su_co",
                                              "qlsx", "qlsx_luc")))
kiem("DocType: kết luận đúng ba lựa chọn của bản giấy; quy cách, ngày nghiền, ngày rang",
     j["ket_luan"]["options"].split("\n") == [""] + list(XX.KET_LUAN)
     and j["ngay_nghien"]["fieldtype"] == j["ngay_rang"]["fieldtype"] == "Date" and "quy_cach" in j)
jc = {f["fieldname"]: f for f in json.load(open(
    "sx/qc/doctype/sx_kiem_tra_xuat_xuong_muc/sx_kiem_tra_xuat_xuong_muc.json", encoding="utf-8"))["fields"]}
kiem("bảng con: 5 ô mẫu, yêu cầu, số phiếu BM.08.02, gợi ý / căn cứ chỉ đọc; nội dung đủ dài cho chữ bản giấy",
     all(jc[f"mau_{i}"]["fieldtype"] == "Data" for i in range(1, 6)) and jc["su_co"]["options"] == "SX Su Co"
     and jc["goi_y"].get("read_only") and jc["can_cu"].get("read_only")
     and jc["noi_dung"]["fieldtype"] == jc["yeu_cau"]["fieldtype"] == "Small Text"
     and jc["ket_qua"]["options"].split("\n") == ["", XX.DAT, XX.KHONG_DAT, XX.KAD]
     and max(len(m[1]) for m in XX.MUC) > 140)
st = {f["fieldname"]: f for f in json.load(open("sx/sx/doctype/sx_settings/sx_settings.json", encoding="utf-8"))["fields"]}
kiem("SX Settings: bật chốt (mặc định bật) + ngày áp dụng",
     st["chan_nhap_chua_xuat_xuong"].get("default") == "1" and st["xuat_xuong_tu_ngay"]["fieldtype"] == "Date")
qs = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_qc_setting/sx_qc_setting.json", encoding="utf-8"))["fields"]}
kiem("SX QC Setting: người được giao duyệt BM.08.04", qs["nguoi_duyet_xuat_xuong"]["options"] == "SX QC Nguoi Duoc Giao")
hk = open("sx/hooks.py", encoding="utf-8").read()
kiem("hook: kiem_ban ở before_submit + on_submit của SI / DN / POS",
     hk.count("sx.api.xuatxuong.kiem_ban") == 6)
js = open("sx/public/sx/views/qc_xuatxuong.js", encoding="utf-8").read()
for m in sorted(set(re.findall(r"sx\.api\.xuatxuong\.(\w+)", js))):
    kiem(f"màn Xuất xưởng gọi method có thật: {m}", callable(getattr(A, m, None)))
nk = open("sx/public/sx/cards/nhapkhotp.js", encoding="utf-8").read()
kiem("màn nhập kho báo trạng thái BM.08.04 từng dòng trước khi duyệt", "veXx(x)" in nk
     and '"xx":' in open("sx/api/khotp.py", encoding="utf-8").read())

print(f"\n{'XUATXUONG-OK' if not hong else f'XUATXUONG-FAIL ({hong})'}")
sys.exit(1 if hong else 0)
