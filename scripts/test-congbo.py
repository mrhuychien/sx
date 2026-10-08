"""D127 (W28) — danh mục sản phẩm tự công bố: hạn dùng theo tháng, cờ dị ứng.

Hỏng theo hướng nguy hiểm, và im lặng:
  · HSD cộng theo NGÀY thay vì tháng → lô bánh 9 tháng in HSD lệch vài ngày so với
    bao bì; truy xuất theo HSD in trên hộp không ra lô nào.
  · NSX tính ngược sai → lô vào kho mang ngày sản xuất không có thật.
  · Mã chưa gắn sản phẩm mà bị đoán số tháng → HSD bịa.
  · Cờ lạc của sản phẩm không tới được QC → ô thử lạc (B7) không hiện, bỏ bước
    kiểm dị ứng mà hồ sơ vẫn trông đủ.

Nạp sx/utils.py, sx/qc/san_pham.py, patch d127 THẬT; frappe giả.
Chạy: python3 scripts/test-congbo.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import subprocess
import sys
import types
from datetime import date, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class D(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)


ITEM = {
    "BANH-SEN": D(name="BANH-SEN", custom_sp_cong_bo="SPCB-001", shelf_life_in_days=180),
    "CHE-DEN": D(name="CHE-DEN", custom_sp_cong_bo="SPCB-010", shelf_life_in_days=0),
    "BOT-MOI": D(name="BOT-MOI", custom_sp_cong_bo=None, shelf_life_in_days=200),
    "KHONG-GI": D(name="KHONG-GI", custom_sp_cong_bo=None, shelf_life_in_days=0),
}
SP = {
    "SPCB-001": D(name="SPCB-001", so_cong_bo="01/2023", ten_san_pham="Bánh sen", loai="Bánh",
                  han_dung_thang=9, co_lac=0, co_sua_bot=0, co_dua=0),
    "SPCB-010": D(name="SPCB-010", so_cong_bo="10/2021", ten_san_pham="Chè đậu đen cốt dừa",
                  loai="Chè", han_dung_thang=12, co_lac=1, co_sua_bot=0, co_dua=1),
}
DEM = {"get_all": 0}


def get_all(dt, filters=None, fields=None, **k):
    DEM["get_all"] += 1
    f = filters or {}
    if dt == "Item":
        ds = [x for n, x in ITEM.items() if n in f.get("name", ("in", []))[1]]
        if "custom_sp_cong_bo" in f:
            ds = [x for x in ds if x.custom_sp_cong_bo]
        return ds
    if dt == "SX San Pham Cong Bo":
        return [x for n, x in SP.items() if n in f["name"][1]]
    return []


def _gd(x=None):
    return x if isinstance(x, date) else date.fromisoformat(str(x)[:10])


def _add_months(d, n):
    d = _gd(d)
    t = d.month - 1 + n
    y, m = d.year + t // 12, t % 12 + 1
    import calendar
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


frappe = types.ModuleType("frappe")
frappe.get_all = get_all
frappe.get_cached_value = lambda dt, n, f=None: ITEM[n].get(f) if n in ITEM else None
frappe.__dict__["_"] = lambda s: s
frappe.local = types.SimpleNamespace()
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: float(v or 0)
fu.getdate = _gd
fu.nowdate = lambda: "2026-10-08"
fu.add_days = lambda d, n: _gd(d) + timedelta(days=n)
fu.add_months = _add_months
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.qc"):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


U = nap("sx.utils", "sx/utils.py")
Q = nap("sx.qc.san_pham", "sx/qc/san_pham.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


print("-- hạn dùng: theo THÁNG khi mã gắn sản phẩm tự công bố --")
kiem("bánh gắn sản phẩm 9 tháng → ('thang', 9), KHÔNG lấy Shelf Life 180 ngày",
     U.han_dung("BANH-SEN") == ("thang", 9), U.han_dung("BANH-SEN"))
kiem("chè gắn sản phẩm 12 tháng", U.han_dung("CHE-DEN") == ("thang", 12))
kiem("mã chưa gắn → rơi về Shelf Life (ngày)", U.han_dung("BOT-MOI") == ("ngay", 200))
kiem("mã chưa gắn, chưa khai gì → None (không bịa)", U.han_dung("KHONG-GI") is None)
kiem("HSD = NSX + 9 tháng theo LỊCH (08/10/2026 → 08/07/2027)",
     U.hsd_tu_nsx("BANH-SEN", "2026-10-08") == "2027-07-08", U.hsd_tu_nsx("BANH-SEN", "2026-10-08"))
kiem("cuối tháng không tràn: 31/05/2026 + 9 tháng → 28/02/2027",
     U.hsd_tu_nsx("BANH-SEN", "2026-05-31") == "2027-02-28")
kiem("NSX = HSD − 9 tháng (W05): HSD 08/07/2027 → NSX 08/10/2026",
     U.nsx_tu_hsd("BANH-SEN", "2027-07-08") == "2026-10-08")
kiem("NSX = HSD − 12 tháng cho chè", U.nsx_tu_hsd("CHE-DEN", "2027-10-08") == "2026-10-08")
kiem("mã theo ngày: NSX = HSD − Shelf Life", U.nsx_tu_hsd("BOT-MOI", "2027-01-01")
     == str(date(2027, 1, 1) - timedelta(days=200)))
kiem("chưa khai hạn dùng → NSX None (nơi gọi lấy ngày nhập)", U.nsx_tu_hsd("KHONG-GI", "2027-01-01") is None)
kiem("Shelf Life đọc sẵn được dùng, khỏi tra lại",
     U.han_dung("KHONG-GI", 30) == ("ngay", 30))

print("\n-- đọc cả loạt: không N+1 --")
U.xoa_nho()
DEM["get_all"] = 0
r = U.nap_cong_bo(list(ITEM))
kiem("4 mã → đúng 2 truy vấn (Item + sản phẩm)", DEM["get_all"] == 2, DEM["get_all"])
U.nap_cong_bo(list(ITEM))
kiem("gọi lại trong cùng request → không truy vấn thêm (nhớ theo request)", DEM["get_all"] == 2)
kiem("mã gắn → dict sản phẩm, mã không gắn → None",
     r["BANH-SEN"]["so_cong_bo"] == "01/2023" and r["BOT-MOI"] is None)

print("\n-- QC: cờ dị ứng theo sản phẩm (B0 / B7) --")
du = Q.co_di_ung(["BANH-SEN", "CHE-DEN", "BOT-MOI"])
kiem("chè đậu đen cốt dừa: có lạc + có dừa", du.get("CHE-DEN") == {"lac": 1, "sua": 0, "dua": 1}, du)
kiem("mã không gắn sản phẩm không có trong kết quả (QC rơi về danh sách ở Setting)",
     "BOT-MOI" not in du)
frappe.get_all = lambda *a, **k: (_ for _ in ()).throw(Exception("chưa migrate"))
kiem("site chưa có DocType → {} chứ không văng lỗi giữa lượt kiểm", Q.co_di_ung(["X"]) == {})
frappe.get_all = get_all
rd = open("sx/qc/doctype/sx_qc_round/sx_qc_round.py", encoding="utf-8").read()
kiem("lượt kiểm tính cờ lạc từ sản phẩm (OR với danh sách Setting)",
     "co_di_ung(chon)" in rd and 'du.get(c, {}).get("lac")' in rd)
ap = open("sx/api/qc.py", encoding="utf-8").read()
kiem("danh mục vị bột (B0) gắn cờ lạc theo sản phẩm", "co_di_ung([x.name for x in ds])" in ap)

print("\n-- DocType + gắn mã hàng --")
jd = json.load(open("sx/sx/doctype/sx_san_pham_cong_bo/sx_san_pham_cong_bo.json", encoding="utf-8"))
f = {x["fieldname"]: x for x in jd["fields"]}
for ten in ("so_cong_bo", "ten_san_pham", "loai", "tccs", "han_dung_thang", "quy_cach",
            "co_lac", "co_sua_bot", "co_dua"):
    kiem(f"có trường {ten}", ten in f)
kiem("số bản tự công bố là duy nhất", f["so_cong_bo"].get("unique") == 1)
kiem("form sản phẩm liệt kê mã hàng gắn về (Connections)",
     any(x["link_doctype"] == "Item" and x["link_fieldname"] == "custom_sp_cong_bo"
         for x in jd["links"]))
cf = [x for x in json.load(open("sx/fixtures/custom_field.json", encoding="utf-8"))
      if x["fieldname"] == "custom_sp_cong_bo"]
kiem("Item có trường gắn sản phẩm tự công bố", len(cf) == 1 and cf[0]["dt"] == "Item"
     and cf[0]["options"] == "SX San Pham Cong Bo")

print("\n-- controller: hạn dùng mặc định theo loại --")
fm = types.ModuleType("frappe.model")
fm.__path__ = []
fd = types.ModuleType("frappe.model.document")


class Doc(D):
    def __setattr__(self, k, v):
        self[k] = v


fd.Document = Doc
sys.modules["frappe.model"] = fm
sys.modules["frappe.model.document"] = fd


class Loi(Exception):
    pass


frappe.throw = lambda m, *a, **k: (_ for _ in ()).throw(Loi(m))
C = nap("sx.sx.doctype.sx_san_pham_cong_bo.sx_san_pham_cong_bo",
        "sx/sx/doctype/sx_san_pham_cong_bo/sx_san_pham_cong_bo.py")
for loai, mong in (("Bánh", 9), ("Bột", 12), ("Chè", 12)):
    d = C.SXSanPhamCongBo(so_cong_bo=" 01/2023 ", ten_san_pham="x", loai=loai, han_dung_thang=0)
    C.SXSanPhamCongBo.validate(d)
    kiem(f"{loai} bỏ trống hạn dùng → {mong} tháng", d.han_dung_thang == mong)
kiem("… và số bản được cắt khoảng trắng thừa", d.so_cong_bo == "01/2023")
d = C.SXSanPhamCongBo(so_cong_bo="x", ten_san_pham="x", loai="Bánh", han_dung_thang=270)
try:
    C.SXSanPhamCongBo.validate(d)
    kiem("gõ 270 (ngày) vào ô tháng → chặn", False)
except Loi:
    kiem("gõ 270 (ngày) vào ô tháng → chặn", True)

print("\n-- patch: 16 sản phẩm theo danh sách 08/10/2026 --")
src = open("sx/patches/d127_san_pham_cong_bo.py", encoding="utf-8").read()
ns = {}
exec(src.split("import frappe")[1].split("def execute")[0], ns)   # noqa: S102
ds = ns["DS"]
kiem("đúng 16 sản phẩm", len(ds) == 16, len(ds))
kiem("số bản không trùng", len({x[0] for x in ds}) == 16)
kiem("8 bánh 01–08/2023, 9 tháng",
     [x[0] for x in ds if x[2] == "Bánh"] == [f"{i:02d}/2023" for i in range(1, 9)]
     and all(x[3] == 9 for x in ds if x[2] == "Bánh"))
kiem("bột và chè 12 tháng", all(x[3] == 12 for x in ds if x[2] != "Bánh"))
kiem("Bột đậu xanh dinh dưỡng 09/2021, Chè đậu đen cốt dừa 10/2021",
     ("09/2021", "Bột đậu xanh dinh dưỡng") in [(x[0], x[1]) for x in ds]
     and ("10/2021", "Chè đậu đen cốt dừa") in [(x[0], x[1]) for x in ds])
kiem("6 bột 01–06/HOANGGIANG/2026",
     sum(1 for x in ds if x[0].endswith("/HOANGGIANG/2026")) == 6)
kiem("patch không tự gắn mã hàng (gắn sai là bật ô thử lạc nhầm vị)", "custom_sp_cong_bo" not in src)
kiem("patch có trong patches.txt",
     "sx.patches.d127_san_pham_cong_bo" in open("sx/patches.txt", encoding="utf-8").read())

print("\n-- màn hình: HSD mặc định cộng THÁNG theo lịch --")
js = open("sx/public/sx/cards/nhapkhotp.js", encoding="utf-8").read()
ham = ""
for ten in ("hsdTu", "congNgay", "congThang"):
    i = js.index(f"export function {ten}(")
    j = js.index("\n}\n", i) + 3
    ham += js[i:j].replace("export ", "") + "\n"
out = subprocess.run(["node", "-e", ham + """
console.log(JSON.stringify([
  hsdTu('2026-10-08', {han_dung_thang: 9, han_dung: 0}),
  hsdTu('2026-05-31', {han_dung_thang: 9}),
  hsdTu('2026-10-08', {han_dung: 30}),
  hsdTu('2026-10-08', {han_dung: 0, han_dung_thang: 0}),
]));"""], capture_output=True, text=True)
kq = json.loads(out.stdout or "null")
kiem("JS: 9 tháng → 08/07/2027; cuối tháng → 28/02/2027; 30 ngày; không khai → null",
     kq == ["2027-07-08", "2027-02-28", "2026-11-07", None], kq or out.stderr[:200])
vh = open("sx/public/sx/cards/vaohoptet.js", encoding="utf-8").read()
kiem("màn Vào hộp Tết dùng cùng hàm", "hsdTu(ngay, sp(item))" in vh)
kp = open("sx/api/khotp.py", encoding="utf-8").read()
kiem("danh mục nhập kho gửi han_dung_thang", "_han_dung_js(i.name" in kp
     and '"han_dung_thang"' in kp)

print()
if hong:
    print(f"CONGBO-HỎNG ({hong})")
    sys.exit(1)
print("CONGBO-OK")
