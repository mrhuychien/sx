"""D137 (W08) — kiểm tra xuất xưởng theo lô BM.08.04.

Vì sao phải có bài này: đây là CỔNG cuối trước khi hàng rời xưởng.
  · Người đã kiểm lô tự duyệt luôn (kể cả khi người đó có role Ban ISO) → bước duyệt chỉ
    còn là dấu tích. Tài liệu 08/10 ghi rõ: người duyệt không phải QC đã kiểm lô đó.
  · Lô chưa duyệt vẫn nhập kho / vẫn bán được → phiếu BM.08.04 là giấy tờ cho có.
  · Chặn nhầm tồn cũ (nhập trước khi có BM.08.04) → cả kho thành phẩm đứng hình sau khi
    cập nhật.
  · Lô duyệt Không đạt mà không ra phiếu sự cố → không ai xử lý lô đó.

Nạp controller SX Kiem Tra Xuat Xuong, sx/qc/xuat_xuong.py, sx/api/xuatxuong.py,
sx/api/thuhoi.py, sx/api/qc.py, nhac.py, patch d137 THẬT; frappe giả.
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
ROUND = []          # SX QC Round: {ngay, docstatus}
LUU_MAU = []        # SX QC Luu Mau: {name, san_pham, hsd, lo}
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
            "SX Phieu Nhap TP Item": NHAP_NHAP}.get(dt, [])


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
    exists=lambda dt, f=None: bool(get_all(dt, f if isinstance(f, dict) else {"name": f})),
    table_exists=lambda dt: True,
    set_single_value=lambda dt, f, v: SETTINGS.update({f: v}),
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
sys.modules["sx.utils"] = ut
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
Q = nap("sx.api.qc", "sx/api/qc.py")
nap("sx.api.thuhoi", "sx/api/thuhoi.py")
A = nap("sx.api.xuatxuong", "sx/api/xuatxuong.py")
P = nap("sx.patches.d137_xuat_xuong", "sx/patches/d137_xuat_xuong.py")

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


def cham_het(d, kq="Đạt"):
    return json.dumps({"ds_muc": [{"ma": r["ma"], "ket_qua": kq} for r in d["ds_muc"]],
                       "ket_luan": kq, "so_mau": 5})


# ═══ 1. Lập phiếu, hồ sơ lô ═══════════════════════════════════════════════
print("\n-- lập phiếu BM.08.04, tự tra hồ sơ lô --")
ROUND[:] = [{"ngay": date(2026, 7, 5), "docstatus": 1}] * 3
LUU_MAU[:] = [{"name": "LM-0007", "san_pham": "TP-SEN", "hsd": date(2027, 4, 5)}]
d = A.lap_phieu("TP-SEN", "2027-04-05", 120, "Hộp")
x = DB["SX Kiem Tra Xuat Xuong"][d["name"]]
kiem("phiếu mới: Nháp, đủ mục, tên sản phẩm, NSX tính từ HSD, gắn lô có sẵn",
     x["trang_thai"] == "Nháp" and len(x["ds_muc"]) == len(XX.MUC)
     and x["ten_san_pham"] == "Bánh đậu xanh sen" and x["nsx"] == "2026-07-05"
     and x["batch"] == "SEN-HSD270405", (x["nsx"], x["batch"]))
kiem("hồ sơ lô: số lượt BM.08.01 ngày NSX, sự cố mở, mẫu lưu",
     "3 lượt" in x["ho_so"] and "LM-0007" in x["ho_so"], x["ho_so"])
kiem("có căn cứ → chấm sẵn mục 1 (hồ sơ) và 8 (mẫu lưu), mục khác để QC chấm",
     [r["ket_qua"] for r in x["ds_muc"]] == ["Đạt", "", "", "", "", "", "", "Đạt"])
kiem("bấm lập lần hai → trả đúng phiếu cũ, không đẻ phiếu thứ hai",
     A.lap_phieu("TP-SEN", "2027-04-05")["name"] == d["name"] and len(DB["SX Kiem Tra Xuat Xuong"]) == 1)
ROUND.clear(); LUU_MAU.clear()
d2 = A.lap_phieu("TP-DUA", "2027-04-05")
x2 = DB["SX Kiem Tra Xuat Xuong"][d2["name"]]
kiem("thiếu lượt / chưa lấy mẫu lưu → KHÔNG chấm sẵn, hồ sơ nói CHƯA lấy",
     [r["ket_qua"] for r in x2["ds_muc"]] == [""] * len(XX.MUC) and "CHƯA lấy" in x2["ho_so"])
loi = thu(lambda: XXC.SXKiemTraXuatXuong({"doctype": "SX Kiem Tra Xuat Xuong", "san_pham": "TP-SEN",
                                          "hsd": "2027-04-05", "trang_thai": "Nháp"}).insert())
kiem("lập tay phiếu thứ hai cho cùng lô (Desk) → chặn", loi and d["name"] in loi, loi or "")
loi = thu(lambda: XXC.SXKiemTraXuatXuong({"doctype": "SX Kiem Tra Xuat Xuong", "san_pham": "TP-SEN",
                                          "hsd": "2027-05-01", "trang_thai": "Đã duyệt",
                                          "ket_luan": "Đạt"}).insert())
kiem("lập phiếu mới thẳng 'Đã duyệt' → chặn", loi and "Nháp" in loi, loi or "")

# ═══ 2. Gửi duyệt ═════════════════════════════════════════════════════════
print("\n-- gửi duyệt: đủ mục, kết luận, số mẫu --")
loi = thu(lambda: A.gui_duyet(d["name"]))
kiem("chưa chấm đủ → chặn, nói mục nào", loi and "Còn mục chưa chấm" in loi and "2" in loi, loi or "")
p = json.loads(cham_het(d))
p["ds_muc"][2]["ket_qua"] = "Không đạt"
loi = thu(lambda: A.gui_duyet(d["name"], json.dumps(p)))
kiem("kết luận Đạt mà có mục Không đạt → chặn", loi and "Kết luận Đạt nhưng có mục Không đạt" in loi, loi or "")
p = json.loads(cham_het(d)); p["so_mau"] = 0
kiem("chưa ghi số mẫu → chặn", "số mẫu" in (thu(lambda: A.gui_duyet(d["name"], json.dumps(p))) or ""))
kiem("kết quả lạ → chặn", thu(lambda: A.luu_phieu(d["name"], json.dumps(
    {"ds_muc": [{"ma": "2", "ket_qua": "Tốt"}]}))) is not None)
r = A.gui_duyet(d["name"], cham_het(d))
kiem("đủ → Chờ duyệt, ghi QC kiểm + giờ", r["trang_thai"] == "Chờ duyệt" and r["qc_kiem"] == "qc@x")
kiem("phiếu chờ duyệt: QC không sửa thẳng được", thu(lambda: A.luu_phieu(d["name"], cham_het(d))) is not None)
kiem("… người kiểm thấy 'không tự duyệt', không có nút duyệt", r["tu_kiem"] and not r["duyet"])

# ═══ 3. Duyệt ═════════════════════════════════════════════════════════════
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
kiem("trả lại → QC sửa được lại", DB["SX Kiem Tra Xuat Xuong"][d["name"]]["trang_thai"] == "Trả lại")
vai("SX QC")
kiem("… QC thấy phiếu sửa được", A.xem_phieu(d["name"])["sua"] is True)
A.gui_duyet(d["name"], cham_het(d))
vai("ISO Manager", u="truong.ban@x")
CAI_DAT_QC["nguoi_duyet_xuat_xuong"] = [Doc(user="pho.qc@x")]
vai("SX QC", u="pho.qc@x")
kiem("người được GIAO (không phải người kiểm) duyệt được", thu(lambda: A.duyet_phieu(d["name"])) is None
     and DB["SX Kiem Tra Xuat Xuong"][d["name"]]["nguoi_duyet"] == "pho.qc@x")
CAI_DAT_QC.clear()
vai("SX QC")
kiem("phiếu đã duyệt: QC không sửa / không lưu được",
     thu(lambda: A.luu_phieu(d["name"], cham_het(d))) is not None)
dd = _get_doc("SX Kiem Tra Xuat Xuong", d["name"])
dd.ghi_chu = "sửa lén trên Desk"
kiem("… kể cả sửa trên Desk", thu(lambda: dd.save()) is not None)
vai("SX QC", u="qc2@x")
kiem("duyệt phiếu không ở trạng thái chờ → chặn (QC khác cũng vậy)", thu(lambda: A.duyet_phieu(d["name"])) is not None)

vai("ISO Manager")
loi = thu(lambda: A.duyet_phieu(d2["name"]))
kiem("Ban ISO duyệt phiếu còn Nháp (QC chưa gửi) → chặn", loi and "chờ duyệt" in loi, loi or "")

print("\n-- duyệt Không đạt → phiếu sự cố; kiểm lại sau rework --")
vai("SX QC")
A.gui_duyet(d2["name"], cham_het(d2, "Không đạt"))
vai("ISO Manager")
A.duyet_phieu(d2["name"], 1, "Nhãn in sai HSD")
x2 = DB["SX Kiem Tra Xuat Xuong"][d2["name"]]
sc = DB["SX Su Co"].get(x2.get("su_co") or "", {})
kiem("lô Không đạt → tự lập phiếu sự cố (nguồn Kiểm tra xuất xưởng, mức Cao)",
     sc.get("nguon") == "Kiểm tra xuất xưởng" and sc.get("muc_do") == "Cao" and d2["name"] in sc.get("mo_ta", ""))
vai("SX QC")
d3 = A.lap_phieu("TP-DUA", "2027-04-05")
kiem("sau Không đạt: lập phiếu KIỂM LẠI được (rework)", d3["name"] != d2["name"])

DB["SX Kiem Tra Xuat Xuong"]["XX-THU"] = {"name": "XX-THU", "san_pham": "TP-SEN", "hsd": "2027-04-05",
                                           "trang_thai": "Nháp", "ket_luan": "", "creation": "2026-10-09"}
kiem("lô có phiếu Đạt + phiếu mới hơn (dữ liệu nhập tay) → vẫn tính theo phiếu Đạt",
     XX.theo_lo([("TP-SEN", "2027-04-05")])[("TP-SEN", "2027-04-05")].name == d["name"])
del DB["SX Kiem Tra Xuat Xuong"]["XX-THU"]

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
kiem("hàng không phải thành phẩm → qua", thu(lambda: A.kiem_ban(hd("BOT-NEN-01"))) is None)
kiem("trả hàng / hoá đơn không trừ kho → qua", thu(lambda: A.kiem_ban(hd("DUA-HSD270405", tra=1))) is None
     and thu(lambda: A.kiem_ban(hd("DUA-HSD270405", us=0))) is None)
SETTINGS["chan_nhap_chua_xuat_xuong"] = 0
kiem("tắt ở SX Settings → qua", thu(lambda: A.kiem_ban(hd("DUA-HSD270405"))) is None)
SETTINGS["chan_nhap_chua_xuat_xuong"] = 1
kiem("trạng thái lô cho màn nhập kho: đã duyệt / chưa",
     A.trang_thai_cac_lo([("TP-SEN", "2027-04-05"), ("TP-DUA", "2027-06-01")])
     == {("TP-SEN", "2027-04-05"): {"name": d["name"], "duyet": True, "chu": "đã duyệt — Đạt"},
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
    html = A.in_phieu(d["name"])
    chu = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", html.split("</style>")[1]))
    kiem("phiếu in BM.08.04: sản phẩm, HSD, mục, kết luận CHO XUẤT XƯỞNG, chỗ ký",
         "BM.08.04" in chu and "Bánh đậu xanh sen" in chu and "05/04/2027" in chu
         and "CHO XUẤT XƯỞNG" in chu and "Trưởng Ban ISO" in chu, chu[:300])

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
j = {f["fieldname"]: f for f in json.load(open(
    "sx/qc/doctype/sx_kiem_tra_xuat_xuong/sx_kiem_tra_xuat_xuong.json", encoding="utf-8"))["fields"]}
kiem("DocType: trạng thái khớp code, người kiểm / duyệt chỉ đọc",
     j["trang_thai"]["options"].split("\n") == [XX.NHAP, XX.CHO, XX.DUYET, XX.TRA]
     and all(j[f].get("read_only") for f in ("qc_kiem", "nguoi_duyet", "duyet_luc", "kiem_luc", "su_co")))
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
