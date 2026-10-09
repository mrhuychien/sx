"""D140 (W15) — động vật gây hại theo trạm R01–R21 / C01–C19, BM.PRP.03 tuần, BM.PRP.01 tháng.

Vì sao phải có bài này:
  · Cùng khu có dấu hiệu hai tuần liền mà không nhắc → xử lý tại chỗ không ăn cả tháng.
  · Sáng thứ Hai chưa ai ghi gì → cặp (hai tuần trước, tuần trước) vẫn phải nhắc.
  · Chuỗi hai tuần liền GIỮA tháng mà bản tổng hợp tháng chỉ nhìn tuần cuối → sổ thiếu.
  · Mã quét (URL trên tem) và mã gõ ("r5") phải ra cùng một trạm, ở máy và ở server.
  · Ghi nhầm thì xoá được, nhưng không phải ai cũng xoá được dấu hiệu thật.

Nạp sx/qc/dong_vat.py, sx/api/qc_dvgh.py, sx/qc/nhac.py, hai controller, patch THẬT; frappe giả.
Chạy: python3 scripts/test-dongvat.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import types
from datetime import date, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

HOM_NAY = date(2026, 10, 8)        # thứ Năm; tuần này bắt đầu 05/10
NGUOI = {"u": "qc@x", "roles": ["SX QC"]}
DB = {"SX Tram Dong Vat": {}, "SX Dau Hieu Dong Vat": {}}
CO_BANG = {"v": True}


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "between" and not (str(m[0]) <= str(x)[:10] <= str(m[1])):
                return False
            if op == ">=" and not str(x)[:10] >= str(m):
                return False
            if op == "!=" and str(x) == str(m):
                return False
        elif str(x if x is not None else "") != str(v if v is not None else ""):
            return False
    return True


def get_all(dt, filters=None, fields=None, order_by=None, limit=None, pluck=None, **k):
    if not CO_BANG["v"]:
        raise Loi("Table 'tabSX Dau Hieu Dong Vat' doesn't exist")
    ds = [Doc(x) for x in DB.get(dt, {}).values() if _khop(x, filters)]
    if order_by and order_by.startswith("ngay desc"):
        ds.sort(key=lambda x: (str(x.get("ngay")), str(x.get("creation"))), reverse=True)
    elif order_by and order_by.startswith("ma"):
        ds.sort(key=lambda x: x.get("ma"))
    if limit:
        ds = ds[:limit]
    if pluck:
        return [x.get(pluck) for x in ds]
    return ds


def _get_value(dt, ten, fld=None, as_dict=False, **k):
    bang = DB.get(dt, {})
    if isinstance(ten, dict):
        h = next((x for x in bang.values() if _khop(x, ten)), None)
    else:
        h = bang.get(ten)
    if h is None:
        return None
    if isinstance(fld, str):
        return h.get(fld)
    d = Doc({c: h.get(c) for c in fld})
    return d if as_dict else tuple(d.values())


try:
    import jinja2
except ImportError:
    jinja2 = None


def _render(path, ctx):
    if jinja2 is None:
        return ""
    fu_in = types.SimpleNamespace(formatdate=lambda v, f=None: fu.getdate(v).strftime(
        "%d/%m" if f == "dd/MM" else "%d/%m/%Y"))
    return jinja2.Environment(loader=jinja2.FileSystemLoader(".")).get_template(path).render(
        frappe=types.SimpleNamespace(utils=fu_in), **ctx)


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, **k: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.msgprint = lambda m, **k: None
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})


class _Phien:
    user = property(lambda s: NGUOI["u"])


frappe.session = _Phien()
frappe.get_roles = lambda u=None: list(NGUOI["roles"])
frappe.get_all = get_all
frappe.render_template = lambda p, ctx: _render(p, ctx)
frappe.db = types.SimpleNamespace(get_value=_get_value, exists=lambda dt, n=None: n in DB.get(dt, {}),
                                  table_exists=lambda dt: CO_BANG["v"])
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: float(v or 0)
fu.getdate = lambda x=None: (x if isinstance(x, date) else date.fromisoformat(str(x)[:10]) if x else HOM_NAY)
fu.nowdate = lambda: str(HOM_NAY)
fu.add_days = lambda d, n: fu.getdate(d) + timedelta(days=n)
fu.add_months = lambda d, n: fu.getdate(d)
fu.now_datetime = lambda: "2026-10-08 10:00:00"
fu.get_datetime = lambda x=None: x
fu.today = fu.nowdate
fu.date_diff = lambda a, b: (fu.getdate(a) - fu.getdate(b)).days
fu.format_date = lambda d, f=None: str(d)
frappe.utils = fu
SO = {"n": 0}


class Document:
    """Document giả: thuộc tính đọc / ghi vào dict, insert chạy before_insert → validate."""

    def __init__(self, d=None):
        self.__dict__["_d"] = dict(d or {})
        self.__dict__["_moi"] = True

    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.__dict__["_d"].get(k)

    def __setattr__(self, k, v):
        self.__dict__["_d"][k] = v

    def get(self, k, d=None):
        return self._d.get(k, d)

    def is_new(self):
        return self._moi

    def insert(self, ignore_permissions=False):
        if getattr(type(self), "before_insert", None):
            self.before_insert()
        dt = self._d["doctype"]
        if dt == "SX Tram Dong Vat":
            self._d["name"] = self._d.get("ma")
            self._d.setdefault("ngung", 0)          # Check: Frappe điền 0 lúc tạo
        self.validate()
        if dt == "SX Dau Hieu Dong Vat":
            SO["n"] += 1
            self._d["name"] = f"DV-2026-{SO['n']:05d}"
            self._d.setdefault("creation", f"2026-10-08 10:00:{SO['n']:02d}")
        DB[dt][self._d["name"]] = dict(self._d)
        self.__dict__["_moi"] = False
        return self


md = types.ModuleType("frappe.model.document")
md.Document = Document
sys.modules["frappe.model"] = types.ModuleType("frappe.model")
sys.modules["frappe.model.document"] = md
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.qc", "sx.api", "sx.patches"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


nap("sx.qc.muc", "sx/qc/muc.py")
nap("sx.qc.nguong", "sx/qc/nguong.py")
nap("sx.qc.quyen", "sx/qc/quyen.py")
for t in ("san_pham", "su_co", "xuat"):
    nap(f"sx.qc.{t}", f"sx/qc/{t}.py")
NH = nap("sx.qc.nhac", "sx/qc/nhac.py")
DV = nap("sx.qc.dong_vat", "sx/qc/dong_vat.py")
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
nap("sx.api.qc", "sx/api/qc.py")
A = nap("sx.api.qc_dvgh", "sx/api/qc_dvgh.py")
TRC = nap("tram_ctl", "sx/qc/doctype/sx_tram_dong_vat/sx_tram_dong_vat.py")
DHC = nap("dau_hieu_ctl", "sx/qc/doctype/sx_dau_hieu_dong_vat/sx_dau_hieu_dong_vat.py")
LOP = {"SX Tram Dong Vat": TRC.SXTramDongVat, "SX Dau Hieu Dong Vat": DHC.SXDauHieuDongVat}
frappe.get_doc = lambda d: LOP[d["doctype"]](d)
frappe.delete_doc = lambda dt, n, **k: DB[dt].pop(n)
P = nap("sx.patches.d140_tram_dong_vat", "sx/patches/d140_tram_dong_vat.py")

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


W = date(2026, 10, 5)          # thứ Hai tuần này
d = lambda w, n=0: str(W + timedelta(days=7 * w + n))   # noqa: E731 — w tuần so với tuần này


# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- hai tuần liền theo khu, mã trạm --")
kiem("thứ Hai của tuần", DV.thu_hai("2026-10-08") == W and DV.thu_hai("2026-10-11") == W
     and DV.thu_hai("2026-10-05") == W)


def hk(ds, ngay=HOM_NAY):
    return {x["khu"]: x for x in DV.khu_hai_tuan(ds, ngay)}


r = hk([{"ngay": d(-1), "khu": "Kho NL", "tram": "R01"}, {"ngay": d(0, 1), "khu": "Kho NL", "tram": "R02"}])
kiem("tuần trước + tuần này, cùng khu (khác trạm) → nhắc, gom đủ trạm",
     r.get("Kho NL", {}).get("tram") == ["R01", "R02"] and r["Kho NL"]["tuan"] == [d(-1), d(0)], r)
r = hk([{"ngay": d(-2), "khu": "Đóng gói", "tram": "C03"}, {"ngay": d(-1, 4), "khu": "Đóng gói", "tram": "C03"}],
       W)
kiem("sáng thứ Hai chưa ai ghi: hai tuần trước + tuần trước → VẪN nhắc", "Đóng gói" in r, r)
kiem("cách một tuần (−2, 0) → không nhắc", not hk([{"ngay": d(-2), "khu": "A", "tram": "R01"},
                                                   {"ngay": d(0), "khu": "A", "tram": "R01"}]))
kiem("chuỗi cũ (−3, −2) → hết nhắc", not hk([{"ngay": d(-3), "khu": "A", "tram": "R01"},
                                             {"ngay": d(-2), "khu": "A", "tram": "R01"}]))
kiem("hai khu khác nhau mỗi khu một tuần → không nhắc", not hk([{"ngay": d(-1), "khu": "A", "tram": "R01"},
                                                                 {"ngay": d(0), "khu": "B", "tram": "R02"}]))
r = hk([{"ngay": d(-1), "khu": "", "tram": "R07"}, {"ngay": d(0), "khu": None, "tram": "R07"},
        {"ngay": d(-1), "khu": "", "tram": "R08"}, {"ngay": d(0), "khu": "", "tram": "R09"}])
kiem("trạm chưa khai khu tự là một khu: R07 hai tuần → nhắc; R08 / R09 mỗi trạm một tuần → không",
     list(r) == ["trạm R07 (chưa khai khu)"], list(r))

cl = DV.chuoi_lien_tuan([{"ngay": d(-4), "khu": "A", "tram": "R01"}, {"ngay": d(-3), "khu": "A", "tram": "R02"},
                         {"ngay": d(-1), "khu": "A", "tram": "R01"}, {"ngay": d(0), "khu": "A", "tram": "R01"},
                         {"ngay": d(-4), "khu": "B", "tram": "C01"}, {"ngay": d(-2), "khu": "B", "tram": "C01"}])
kiem("bản tháng: mọi chuỗi ≥ 2 tuần liền (cả chuỗi giữa tháng), tách chuỗi đứt quãng, bỏ khu không liền",
     [(x["khu"], x["tuan"], x["tram"]) for x in cl]
     == [("A", [d(-4), d(-3)], ["R01", "R02"]), ("A", [d(-1), d(0)], ["R01"])], cl)
cl = DV.chuoi_lien_tuan([{"ngay": d(w), "khu": "A", "tram": "R01"} for w in (-3, -2, -1)])
kiem("ba tuần liền → MỘT chuỗi ba tuần", [len(x["tuan"]) for x in cl] == [3], cl)

MA = [("r5", "R05"), ("R05", "R05"), (" c 12 ", "C12"), ("C019", "C19"),
      ("https://rv.example/sx#/qc/dvgh/R05", "R05"), ("X05", ""), ("R123", ""), ("", ""), ("R", "")]
kiem("mã gõ / mã quét → mã trạm (server)", all(DV.ma_tram(q) == v for q, v in MA),
     [(q, DV.ma_tram(q)) for q, v in MA if DV.ma_tram(q) != v])
js = open("sx/public/sx/views/qc_dvgh.js", encoding="utf-8").read()
ham = re.search(r"export function maTram\(q\) \{.*?\n\}", js, re.S).group(0).replace("export ", "")
try:
    ra = subprocess.run(["node", "-e", ham + f"\nconsole.log(JSON.stringify({json.dumps([q for q, _v in MA])}"
                         ".map(maTram)))"], capture_output=True, text=True, timeout=20)
    kiem("… và ở máy (maTram trong qc_dvgh.js) ra y hệt server", json.loads(ra.stdout) == [v for _q, v in MA],
         ra.stdout + ra.stderr)
except FileNotFoundError:
    print("  (bỏ qua so mã ở máy — không có node)")

# ═══ 2. Danh mục trạm (patch) ═════════════════════════════════════════════
print("\n-- 40 trạm, controller trạm --")
P.execute()
kiem("patch tạo đủ 40 trạm R01–R21 (bẫy chuột), C01–C19 (côn trùng)",
     len(DB["SX Tram Dong Vat"]) == 40 and DB["SX Tram Dong Vat"]["R21"]["loai"] == "Bẫy chuột"
     and DB["SX Tram Dong Vat"]["C19"]["loai"] == "Bẫy côn trùng" and "R22" not in DB["SX Tram Dong Vat"])
DB["SX Tram Dong Vat"]["R01"]["khu"] = "Kho nguyên liệu"
P.execute()
kiem("chạy lại patch: không nhân đôi, giữ khu Ban ISO đã khai",
     len(DB["SX Tram Dong Vat"]) == 40 and DB["SX Tram Dong Vat"]["R01"]["khu"] == "Kho nguyên liệu")
CO_BANG["v"] = False
kiem("chưa migrate xong bảng → patch bỏ qua, không vỡ", thu(P.execute) is None)
CO_BANG["v"] = True
t = frappe.get_doc({"doctype": "SX Tram Dong Vat", "ma": " r22 "})
t.insert()
kiem("Desk gõ \"r22\" → trạm TÊN R22 (chuẩn hoá trước khi đặt tên), loại theo đầu mã",
     "R22" in DB["SX Tram Dong Vat"] and DB["SX Tram Dong Vat"]["R22"]["loai"] == "Bẫy chuột")
DB["SX Tram Dong Vat"].pop("R22")
kiem("mã sai dạng (K01, R1A) → chặn",
     all("dạng R01" in (thu(lambda m=m: frappe.get_doc({"doctype": "SX Tram Dong Vat", "ma": m}).insert()) or "")
         for m in ("K01", "R1A", "R100")))
DB["SX Tram Dong Vat"]["R01"].update(khu="Kho nguyên liệu", vi_tri="cửa cuốn")
for m in ("R02", "R03"):
    DB["SX Tram Dong Vat"][m]["khu"] = "Kho nguyên liệu"
for m in ("C01", "C02"):
    DB["SX Tram Dong Vat"][m]["khu"] = "Đóng gói"
DB["SX Tram Dong Vat"]["C19"]["ngung"] = 1

# ═══ 3. Ghi / xoá dấu hiệu ════════════════════════════════════════════════
print("\n-- ghi dấu hiệu theo trạm, quyền --")


def ghi(**k):
    return A.ghi_dau_hieu(json.dumps({"dau_hieu": DV.DAU_HIEU[0], **k}))


r = ghi(tram="https://rv.example/sx#/qc/dvgh/r1", so_luong="2", xu_ly=" thay mồi ")
p = DB["SX Dau Hieu Dong Vat"][r["name"]]
kiem("quét URL trên tem → ghi đúng trạm R01, chép khu, người ghi, ngày hôm nay, cắt khoảng trắng",
     (p["tram"], p["khu"], p["nguoi_ghi"], str(p["ngay"]), p["so_luong"], p["xu_ly"])
     == ("R01", "Kho nguyên liệu", "qc@x", "2026-10-08", 2, "thay mồi"), p)
kiem("chưa chọn loại dấu hiệu → chặn", "loại dấu hiệu" in (thu(lambda: A.ghi_dau_hieu(
    json.dumps({"tram": "R02"}))) or ""))
kiem("trạm không có → báo rõ dạng mã", "R01–R21" in (thu(lambda: ghi(tram="R55")) or ""))
kiem("trạm ngừng dùng → chặn", "ngừng" in (thu(lambda: ghi(tram="C19")) or ""))
kiem("ngày sau hôm nay → chặn", "sau hôm nay" in (thu(lambda: ghi(tram="R02", ngay="2026-10-09")) or ""))
kiem("số lượng âm → chặn", "không âm" in (thu(lambda: ghi(tram="R02", so_luong=-3)) or ""))
NGUOI.update(u="iso@x", roles=["ISO Manager"])
kiem("Ban ISO KHÔNG ghi dấu hiệu (người xem xét không tự ghi)",
     thu(lambda: ghi(tram="R02")) is not None)
NGUOI.update(u="kho@x", roles=["Stock User"])
kiem("người ngoài QC không xem được", thu(lambda: A.tong_quan()) is not None)
NGUOI.update(u="qc@x", roles=["SX QC"])

DB["SX Dau Hieu Dong Vat"].clear()
for tram, ngay, ai in [("R01", d(-1, 2), "qc@x"), ("R02", d(0, 1), "qc2@x"), ("C01", d(-2, 3), "qc@x"),
                       ("C02", d(-1), "qc@x"), ("R05", d(0, 3), "qc@x"), ("R06", d(-4), "qc@x")]:
    NGUOI["u"] = ai
    ghi(tram=tram, ngay=ngay)
NGUOI["u"] = "qc@x"
ten = {(x["tram"], str(x["ngay"])): n for n, x in DB["SX Dau Hieu Dong Vat"].items()}
kiem("người ghi xoá được dòng của mình TRONG NGÀY",
     thu(lambda: A.xoa_dau_hieu(ten[("R05", d(0, 3))])) is None and ten[("R05", d(0, 3))] not in DB["SX Dau Hieu Dong Vat"])
ghi(tram="R05", ngay=d(0, 3))
ten = {(x["tram"], str(x["ngay"])): n for n, x in DB["SX Dau Hieu Dong Vat"].items()}
DB["SX Dau Hieu Dong Vat"][ten[("R05", d(0, 3))]]["ngay"] = d(0, 1)   # ghi từ hôm qua
loi = thu(lambda: A.xoa_dau_hieu(ten[("R05", d(0, 3))]))
kiem("… qua ngày thì không xoá được nữa", loi and "Ban ISO" in loi, loi)
NGUOI["u"] = "qc2@x"
khac = ghi(tram="R03")["name"]               # QC khác ghi HÔM NAY
NGUOI["u"] = "qc@x"
kiem("QC khác không xoá được dòng của người khác (cùng ngày)",
     thu(lambda: A.xoa_dau_hieu(khac)) is not None and khac in DB["SX Dau Hieu Dong Vat"])
DB["SX Dau Hieu Dong Vat"].pop(khac)
NGUOI.update(u="iso@x", roles=["ISO Manager"])
kiem("Ban ISO xoá được bất cứ lúc nào", thu(lambda: A.xoa_dau_hieu(ten[("R05", d(0, 3))])) is None)
NGUOI.update(u="qc@x", roles=["SX QC"])

# ═══ 4. Tổng quan tuần + nhắc ═════════════════════════════════════════════
print("\n-- tuần này, nhắc gọi dịch vụ --")
q = A.tong_quan()
tram = {t["ma"]: t for t in q["tram"]}
kiem("tuần thứ Hai → Chủ nhật, chỉ trạm đang dùng (39), có lần ghi gần nhất / số lần tuần này",
     (q["tuan_tu"], q["tuan_den"]) == ("2026-10-05", "2026-10-11") and len(tram) == 39 and "C19" not in tram
     and tram["R01"]["lan_cuoi"] == d(-1, 2) and tram["R02"]["tuan_nay"] == 1 and tram["R01"]["tuan_nay"] == 0,
     (q["tuan_tu"], len(tram), tram["R01"]))
kiem("trạm R trước C (đúng thứ tự sơ đồ)", [t["ma"] for t in q["tram"]][:2] == ["R01", "R02"]
     and [t["ma"] for t in q["tram"]][21] == "C01")
kiem("dấu hiệu trong tuần: chỉ tuần này, mới nhất trước", [p["tram"] for p in q["phieu_tuan"]] == ["R02"],
     [p["tram"] for p in q["phieu_tuan"]])
kiem("khu Kho nguyên liệu (R01 tuần trước, R02 tuần này) → cảnh báo hai tuần liền; Đóng gói (C01 −2, C02 −1)"
     " → cũng cảnh báo", [c["khu"] for c in q["canh_bao"]] == ["Kho nguyên liệu", "Đóng gói"], q["canh_bao"])
kiem("QC được ghi, không phải ISO; danh sách loại dấu hiệu khớp doctype",
     q["duoc_ghi"] and not q["la_iso"] and q["dau_hieu"] == DV.DAU_HIEU)
NGUOI.update(u="iso@x", roles=["ISO Manager"])
q2 = A.tong_quan(d(-1))
kiem("Ban ISO xem được (không ghi), xem tuần cũ theo ngày", not q2["duoc_ghi"] and q2["la_iso"]
     and q2["tuan_tu"] == d(-1) and [p["tram"] for p in q2["phieu_tuan"]] == ["R01", "C02"],
     [p["tram"] for p in q2["phieu_tuan"]])
NGUOI.update(u="qc@x", roles=["SX QC"])

dv = DV.nhac(HOM_NAY)
ds = NH.tinh(HOM_NAY, [], [], {}, dong_vat=dv)
dvn = [x for x in ds if x["route"] == "#/qc/dvgh"]
kiem("hộp nhắc QC: mỗi khu hai tuần liền một dòng mức CAO → #/qc/dvgh, nói rõ trạm + gọi dịch vụ",
     len(dvn) == 2 and all(x["muc_do"] == "cao" for x in dvn) and "R01, R02" in dvn[0]["chi_tiet"]
     and "gọi đơn vị dịch vụ" in dvn[0]["chi_tiet"], dvn)
LUOT = [{"luot": "Tuần", "ngay": d(-1), "t2_so_bay_dau_hieu": 2}, {"luot": "Tuần", "ngay": d(0), "t2_so_bay_dau_hieu": 1}]
cu = lambda x: [m for m in x if m["tieu_de"].startswith("Bẫy chuột có dấu hiệu")]   # noqa: E731
kiem("đã ghi theo trạm → bỏ nhắc cũ theo số trạm ở lượt tuần (khỏi nhắc hai lần một chuyện)",
     not cu(NH.tinh(HOM_NAY, LUOT, [], {}, dong_vat=dv)))
kiem("chưa ghi theo trạm lần nào → nhắc cũ theo lượt tuần vẫn chạy",
     len(cu(NH.tinh(HOM_NAY, LUOT, [], {}, dong_vat={"co_du_lieu": False, "khu_hai_tuan": []}))) == 1
     and len(cu(NH.tinh(HOM_NAY, LUOT, [], {}))) == 1)
CO_BANG["v"] = False
kiem("bảng chưa có (chưa migrate) → nhac() trả {}, hộp nhắc không vỡ", DV.nhac(HOM_NAY) == {})
CO_BANG["v"] = True
qcpy = open("sx/api/qc.py", encoding="utf-8").read()
kiem("sx.api.qc.nhac truyền dữ liệu động vật gây hại vào nhắc", "_dong_vat.nhac(d)" in qcpy)
kiem("không có nhắc \"phun định kỳ\" nào trong app (tài liệu 08/10: bỏ)",
     not re.search(r"phun", open("sx/qc/nhac.py", encoding="utf-8").read(), re.I))

# ═══ 5. Bản in ════════════════════════════════════════════════════════════
print("\n-- BM.PRP.03 tuần, BM.PRP.01 tháng --")
if jinja2:
    def chu(html):
        return re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", html.split("</style>")[1]))

    h = chu(A.in_prp03(d(-1, 3)))
    kiem("BM.PRP.03: tuần, đủ 39 trạm, trạm có dấu hiệu ghi CÓ + ngày, trạm khác \"Không\", chỗ ký",
         "BM.PRP.03" in h and "28/09/2026" in h and h.count("Không") >= 36 and "R01 Kho nguyên liệu cửa cuốn CÓ dấu hiệu 30/09" in h
         and "Trưởng Ban ISO" in h, h[:300])
    kiem("… có cảnh báo khu hai tuần liền", "Đóng gói: có dấu hiệu hai tuần liền" in h, h[:300])
    DB["SX Dau Hieu Dong Vat"].clear()
    for tram, ngay in [("R01", "2026-09-02"), ("R02", "2026-09-09"), ("C01", "2026-09-30")]:
        ghi(tram=tram, ngay=ngay)
    h = chu(A.in_prp01("2026-09"))
    kiem("BM.PRP.01: tháng 09/2026, cột tuần từ thứ Hai 31/08 đến 28/09, đếm đủ 3 lần",
         "tháng 09/2026" in h and "BM.PRP.01" in h and "Tuần 31/08" in h and "Tuần 28/09" in h and "Tuần 05/10" not in h
         and "3 lần có dấu hiệu" in h, h[:300])
    kiem("… chuỗi hai tuần liền ĐẦU tháng (R01 02/09, R02 09/09) vẫn lên cảnh báo tháng",
         "Kho nguyên liệu: dấu hiệu 2 tuần liền (tuần 31/08 → 07/09" in h, h[:400])
    h = chu(A.in_prp01())
    kiem("BM.PRP.01 mặc định tháng này", "tháng 10/2026" in h, h[:120])
else:
    print("  (bỏ qua bản in — không có jinja2)")

# ═══ 6. Doctype, giao diện ════════════════════════════════════════════════
print("\n-- doctype, màn hình --")
dh = json.load(open("sx/qc/doctype/sx_dau_hieu_dong_vat/sx_dau_hieu_dong_vat.json", encoding="utf-8"))
fl = {f["fieldname"]: f for f in dh["fields"]}
kiem("loại dấu hiệu trong doctype = DV.DAU_HIEU", fl["dau_hieu"]["options"].split("\n") == DV.DAU_HIEU)
kiem("khu / người ghi chỉ đọc (app tự điền)", fl["khu"].get("read_only") and fl["nguoi_ghi"].get("read_only"))
tr = json.load(open("sx/qc/doctype/sx_tram_dong_vat/sx_tram_dong_vat.json", encoding="utf-8"))
quyen = {x["role"]: x for x in tr["permissions"]}
kiem("trạm: đặt tên theo mã, mã không đổi sau khi tạo; Ban ISO sửa khu / vị trí, QC chỉ đọc",
     tr["autoname"] == "field:ma" and {f["fieldname"]: f for f in tr["fields"]}["ma"].get("set_only_once")
     and quyen["ISO Manager"].get("write") and not quyen["SX QC"].get("write"))
kiem("patch có trong patches.txt", "sx.patches.d140_tram_dong_vat" in open("sx/patches.txt", encoding="utf-8").read())
qcjs = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
kiem("route #/qc/dvgh có tham số trạm (#/qc/dvgh/R05 — URL trên tem)",
     "dvgh: '/assets/sx/sx/views/qc_dvgh.js'" in qcjs and "phan[0] === 'dvgh'" in qcjs)
kiem("màn Hôm nay có nút sang #/qc/dvgh", "#/qc/dvgh" in open("sx/public/sx/views/qc_home.js", encoding="utf-8").read())
kiem("màn dvgh: quét tem bằng hàm tra (lấy mã cuối URL), mở thẳng phiếu trạm từ URL rồi bỏ mã khỏi địa chỉ",
     "tra: (k) =>" in js and "maTram(k)" in js and "replaceState" in js and "if (tham_so)" in js)
qj = open("sx/public/sx/components/quet.js", encoding="utf-8").read()
kiem("bộ quét nhận hàm tra thay cho bảng", "tra ? tra(key) : traBang(bang, key)" in qj)
ij = open("sx/public/sx/lib/inthe.js", encoding="utf-8").read()
kiem("in tem QR trạm: QR chứa URL, mã trạm in to", "export function moTrangInTram" in ij and "veQR(t.url" in ij
     and "/sx#/qc/dvgh/" in js)
kiem("nút in BM.PRP.03 / BM.PRP.01", "sx.api.qc_dvgh.in_prp03" in js and "sx.api.qc_dvgh.in_prp01" in js)

print(f"\n{'DONGVAT-OK' if not hong else f'DONGVAT-FAIL ({hong})'}")
sys.exit(1 if hong else 0)
