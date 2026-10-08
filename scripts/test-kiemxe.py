"""D139 (W14) — kiểm tra phương tiện vận chuyển BM.09.01 trên hoá đơn bán trừ kho và chuyến
nhận nguyên liệu (phiếu nhập mua).

Vì sao phải có bài này:
  · Hoá đơn bán trừ kho duyệt được khi chưa kiểm xe / xe Không đạt → BM.09.01 trống tháng.
  · Một mục Không đạt mà kết luận vẫn "Đạt" → hồ sơ tự mâu thuẫn.
  · Xe giao nguyên liệu bẩn mà lô vẫn vào kho dùng → kiểm xe chỉ là thủ tục.
  · Bắt kiểm xe cả hoá đơn không trừ kho / phiếu trả hàng / NCC dịch vụ → thủ kho bị chặn vô lý.

Nạp sx/qc/kiem_xe.py, sx/qc/ncc.py, sx/qc/tiep_nhan.py, sx/api/qc_kiemxe.py THẬT; frappe giả.
Chạy: python3 scripts/test-kiemxe.py   (verify.sh gọi sẵn)
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
SUPPLIER = {"NCC-DX": {"name": "NCC-DX", "custom_loai_ncc": "Nguyên liệu thực phẩm",
                       "custom_nguon_goc": "Trong nước", "custom_ncc_duyet": 1},
            "NCC-BB": {"name": "NCC-BB", "custom_loai_ncc": "Bao bì tiếp xúc thực phẩm", "custom_ncc_duyet": 1},
            "NCC-DV": {"name": "NCC-DV", "custom_loai_ncc": "Dịch vụ / khác"},
            "NCC-MOI": {"name": "NCC-MOI", "custom_loai_ncc": ""}}
CHUNG_TU = {"Sales Invoice": [], "Purchase Receipt": []}
CAI_DAT_QC = {}
BAO = []
NGUOI = {"u": "kho@x"}


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
            if op == "between" and not (str(m[0]) <= str(x) <= str(m[1])):
                return False
            if op == "is" and m == "set" and not x:
                return False
        elif str(x if x is not None else "") != str(v):
            return False
    return True


def get_all(dt, filters=None, fields=None, order_by=None, **k):
    if dt in CHUNG_TU:
        return [Doc(x) for x in CHUNG_TU[dt] if _khop(x, filters)]
    return []


def _get_value(dt, n, fld=None, as_dict=False, **k):
    h = SUPPLIER.get(n) if dt == "Supplier" else None
    if h is None:
        return None
    d = Doc({c: h.get(c) for c in fld})
    return d if as_dict else tuple(d.values())


try:
    import jinja2
except ImportError:
    jinja2 = None


def _render(path, ctx):
    if jinja2 is None:
        return ""
    fu_in = types.SimpleNamespace(formatdate=lambda v, f=None: fu.getdate(v).strftime("%d/%m/%Y"))
    return jinja2.Environment(loader=jinja2.FileSystemLoader(".")).get_template(path).render(
        frappe=types.SimpleNamespace(utils=fu_in), **ctx)


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, **k: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.msgprint = lambda m, **k: BAO.append(str(m))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})


class _Phien:
    user = property(lambda s: NGUOI["u"])


frappe.session = _Phien()
frappe.get_roles = lambda u=None: ["SX QC"]
frappe.get_all = get_all
frappe.get_cached_doc = lambda dt: Doc(CAI_DAT_QC if dt == "SX QC Setting" else {"kho_cach_ly": "Kho cách ly - RV"})
frappe.get_cached_value = lambda dt, ten, truong: None
frappe.render_template = lambda p, ctx: _render(p, ctx)
frappe.db = types.SimpleNamespace(get_value=_get_value, exists=lambda *a, **k: False)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.getdate = lambda x=None: (x if isinstance(x, date) else
                             date.fromisoformat(str(x)[:10]) if x else HOM_NAY)
fu.nowdate = lambda: str(HOM_NAY)
fu.add_days = lambda d, n: fu.getdate(d) + timedelta(days=n)
fu.now_datetime = lambda: "2026-10-08 10:00:00"
fu.get_datetime = lambda x=None: x
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.qc", "sx.api"):
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
nap("sx.qc.ncc", "sx/qc/ncc.py")
K = nap("sx.qc.kiem_xe", "sx/qc/kiem_xe.py")
T = nap("sx.qc.tiep_nhan", "sx/qc/tiep_nhan.py")
for t in ("san_pham", "su_co", "xuat", "nhac"):
    nap(f"sx.qc.{t}", f"sx/qc/{t}.py")
nap("sx.qc.dong_vat", "sx/qc/dong_vat.py")
nap("sx.api.qc", "sx/api/qc.py")
A = nap("sx.api.qc_kiemxe", "sx/api/qc_kiemxe.py")

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


DAT4 = {f: "Đạt" for f, _n in K.MUC}


def hd(**k):
    return Doc({"doctype": "Sales Invoice", "name": "SINV-1", "update_stock": 1, "is_return": 0,
                "items": [Doc(idx=1, item_code="TP-SEN")], **k})


def pr(sup="NCC-DX", **k):
    return Doc({"doctype": "Purchase Receipt", "name": "PR-1", "supplier": sup, "is_return": 0,
                "posting_date": "2026-10-08", "items": [Doc(idx=1, item_code="DX-01", warehouse="Kho NVL - RV"),
                                                        Doc(idx=2, item_code="DX-02", warehouse="Kho NVL - RV",
                                                            custom_ket_luan="Không đạt")], **k})


def chay(d):
    K.validate(d)
    return thu(lambda: K.before_submit(d))


# ═══ 1. Hoá đơn bán trừ kho ═══════════════════════════════════════════════
print("\n-- hoá đơn bán trừ kho --")
loi = chay(hd())
kiem("chưa kiểm xe → không duyệt được hoá đơn", loi and "Chưa kiểm xe" in loi, loi or "")
d = hd(custom_xe_bien_so="29C-123.45", **DAT4)
kiem("đủ bốn mục Đạt → kết luận tự Đạt, ghi người kiểm, duyệt được",
     chay(d) is None and (d["custom_xe_ket_luan"], d["custom_xe_nguoi_kiem"]) == ("Đạt", "kho@x"))
d = hd(**DAT4)
kiem("thiếu biển số → chặn", "biển số" in (chay(d) or ""))
d = hd(custom_xe_bien_so="29C-123.45", custom_xe_ket_luan="Đạt", **dict(DAT4, custom_xe_con_trung="Không đạt"))
loi = chay(d)
kiem("một mục Không đạt mà ghi kết luận Đạt → ép Không đạt, báo, và CHẶN bán",
     d["custom_xe_ket_luan"] == "Không đạt" and loi and "không xếp hàng" in loi
     and any("Không đạt" in b for b in BAO), loi or "")
d = hd(custom_xe_bien_so="29C", custom_xe_ket_luan="Đạt")
kiem("chưa chấm hết mục nhưng người kiểm tự kết luận → giữ kết luận đó", chay(d) is None
     and d["custom_xe_ket_luan"] == "Đạt")
kiem("hoá đơn KHÔNG trừ kho → không bắt kiểm xe", chay(hd(update_stock=0)) is None)
kiem("phiếu trả hàng → không bắt", chay(hd(is_return=1)) is None)
CAI_DAT_QC["bat_buoc_kiem_xe"] = 0
kiem("tắt ở SX QC Setting → không chặn", chay(hd()) is None)
CAI_DAT_QC.clear()

# ═══ 2. Chuyến nhận nguyên liệu ═══════════════════════════════════════════
print("\n-- chuyến nhận nguyên liệu (phiếu nhập mua) --")
kiem("NCC thực phẩm: chưa kiểm xe → không duyệt được phiếu nhập", "Chưa kiểm xe" in (chay(pr()) or ""))
kiem("NCC bao bì tiếp xúc thực phẩm cũng bắt", "Chưa kiểm xe" in (chay(pr("NCC-BB")) or ""))
kiem("NCC dịch vụ / chưa phân loại → không bắt", chay(pr("NCC-DV")) is None and chay(pr("NCC-MOI")) is None)
d = pr(custom_xe_bien_so="15C-777", **DAT4)
kiem("xe Đạt → duyệt được, dòng hàng giữ nguyên", chay(d) is None and d["items"][0].get("custom_ket_luan") is None)
d = pr(custom_xe_bien_so="15C-777", **dict(DAT4, custom_xe_sach="Không đạt"))
loi = chay(d)
kiem("xe giao hàng KHÔNG ĐẠT → không chặn (hàng đã tới sân), mọi dòng chuyển Cách ly",
     loi is None and d["items"][0]["custom_ket_luan"] == "Cách ly")
kiem("… dòng đã Không đạt giữ nguyên Không đạt", d["items"][1]["custom_ket_luan"] == "Không đạt")
BAO.clear()
T.validate(d)
kiem("… và tiếp nhận đưa dòng Cách ly vào kho cách ly (thứ tự hook: kiểm xe trước)",
     d["items"][0]["warehouse"] == "Kho cách ly - RV")
hk = open("sx/hooks.py", encoding="utf-8").read()
khoi = re.search(r'"Purchase Receipt": \{(.*?)\n    \}', hk, re.S).group(1)
kiem("hook Purchase Receipt: kiem_xe.validate đứng TRƯỚC tiep_nhan.validate, có before_submit",
     khoi.index("sx.qc.kiem_xe.validate") < khoi.index("sx.qc.tiep_nhan.validate")
     and '"before_submit": "sx.qc.kiem_xe.before_submit"' in khoi)
khoi = re.search(r'"Sales Invoice": \{(.*?)\},\n', hk, re.S).group(1)
kiem("hook Sales Invoice: kiem_xe.validate + before_submit", "sx.qc.kiem_xe.validate" in khoi
     and "sx.qc.kiem_xe.before_submit" in khoi)
kiem("không móc vào Delivery Note (nhà máy không dùng)", "kiem_xe" not in re.search(
    r'"Delivery Note": \{(.*?)\},\n', hk, re.S).group(1))

# ═══ 3. Sổ BM.09.01 + cấu hình ════════════════════════════════════════════
print("\n-- sổ kiểm xe tháng, cấu hình --")
CHUNG_TU["Sales Invoice"] = [
    {"name": "SINV-9", "posting_date": "2026-10-02", "docstatus": 1, "is_return": 0, "update_stock": 1,
     "customer_name": "Đại lý Nam Định", "custom_xe_bien_so": "29C-123.45", "custom_xe_ket_luan": "Đạt",
     "custom_xe_nguoi_kiem": "kho@x", **DAT4},
    {"name": "SINV-8", "posting_date": "2026-10-03", "docstatus": 1, "is_return": 0, "update_stock": 0,
     "customer_name": "KH không trừ kho", "custom_xe_ket_luan": "Đạt"}]
CHUNG_TU["Purchase Receipt"] = [
    {"name": "PR-7", "posting_date": "2026-10-01", "docstatus": 1, "is_return": 0, "supplier_name": "NCC Đỗ",
     "custom_xe_bien_so": "15C-777", "custom_xe_ket_luan": "Không đạt", **dict(DAT4, custom_xe_sach="Không đạt")}]
ds = A._chuyen(date(2026, 10, 1), date(2026, 10, 31))
kiem("sổ gom hoá đơn bán trừ kho + phiếu nhập, theo ngày; bỏ hoá đơn không trừ kho",
     [x["name"] for x in ds] == ["PR-7", "SINV-9"] and ds[0]["chieu"] == "Nhận nguyên liệu", [x["name"] for x in ds])
if jinja2:
    chu = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", A.in_so_kiem_xe("2026-10-01", "2026-10-31").split("</style>")[1]))
    kiem("bản in BM.09.01: biển số, khách / NCC, mục Không đạt, chỗ ký",
         "BM.09.01" in chu and "29C-123.45" in chu and "NCC Đỗ" in chu and "Không đạt" in chu
         and "Trưởng Ban ISO" in chu, chu[:200])
cf = {(f["dt"], f["fieldname"]): f for f in json.load(open("sx/fixtures/custom_field.json", encoding="utf-8"))}
for dt in ("Sales Invoice", "Purchase Receipt"):
    kiem(f"{dt}: đủ ô kiểm xe (biển số, 4 mục, kết luận, người kiểm chỉ đọc)",
         all((dt, f) in cf for f in ["custom_xe_bien_so", "custom_xe_ket_luan", "custom_xe_nguoi_kiem"]
             + [f for f, _n in K.MUC]) and cf[(dt, "custom_xe_nguoi_kiem")].get("read_only"))
st = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_qc_setting/sx_qc_setting.json", encoding="utf-8"))["fields"]}
kiem("SX QC Setting: bắt kiểm xe (mặc định bật)", st["bat_buoc_kiem_xe"].get("default") == "1")
kiem("màn Xem xét có nút in BM.09.01", "sx.api.qc_kiemxe.in_so_kiem_xe" in open(
    "sx/public/sx/views/qc_review.js", encoding="utf-8").read())

print(f"\n{'KIEMXE-OK' if not hong else f'KIEMXE-FAIL ({hong})'}")
sys.exit(1 if hong else 0)
