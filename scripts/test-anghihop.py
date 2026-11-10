"""D235 — ẩn công khoán khỏi bảng ghi hộp (vẫn là công khoán, tính lương kiểu khác): Hà, Lập, Phúc.

Vì sao phải có bài này: danh sách công nhân của màn Ghi hộp là danh sách TRẢ LƯƠNG khoán. Hỏng im lặng theo mấy hướng:
  · ẩn ở màn Ghi hộp mà bảng mã quét / in thẻ QR vẫn còn — quét thẻ là ghi được hộp cho người đã ẩn;
  · lệnh ẩn theo TÊN ẩn nhầm người: hai người cùng tên "Hà", gõ không dấu, gõ một phần tên;
  · một tên sai mà hai tên đúng vẫn được ghi — ra lệnh lần hai là thành ẩn lệch;
  · người sắp ẩn đã được ghi hộp / chấm ăn tháng này: phần đó vẫn vào lương khoán, ẩn rồi thì hết chỗ bỏ chấm ăn;
  · site chưa migrate (chưa có bảng ẩn) mà màn Ghi hộp gãy.

Nạp sx/api/portal.py, sx/api/the.py, sx/config/roles.py và dat_ten_hien_thi (sx/utils.py) THẬT; frappe giả.
Chạy: python3 scripts/test-anghihop.py   (verify.sh gọi sẵn)
"""

import ast
import contextlib
import importlib.util
import io
import json
import os
import sys
import types
import unicodedata
from datetime import date

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class Loi(Exception):
    pass


class _dict(dict):
    __getattr__ = dict.get

    def __setattr__(self, k, v):
        self[k] = v


HOM_NAY = date(2026, 11, 10)
VAI = {"SX Vao Hop"}
CO_O = {"an_ghi_hop": True}            # SX Settings đã migrate (có bảng ẩn)?


def nv(ma, ten, so=None, loai="Công khoán", trang="Active"):
    return _dict(name=ma, employee_name=ten, employee_number=so, employment_type=loai, status=trang)


DB = {}


def dat_du_lieu(nhan_vien, ngay=(), bang=(), hop=(), an=(), phieu=()):
    DB.clear()
    DB["Employee"] = list(nhan_vien)
    DB["SX Ngay San Xuat"] = [_dict(r) for r in ngay]
    DB["SX Bang Vao Hop"] = [_dict(r) for r in bang]
    DB["SX Bang Vao Hop Item"] = [_dict(r) for r in hop]
    DB["SX Bang Vao Hop An Ca"] = [_dict(r) for r in an]
    DB["SX Phieu Luong"] = [_dict(r) for r in phieu]


def _khop(r, loc):
    for k, v in (loc or {}).items():
        x = r.get(k)
        if isinstance(v, (tuple, list)):
            op, val = v
            if op == "in" and x not in val:
                return False
            if op == "not in" and x in val:
                return False
            if op == "<" and not x < val:
                return False
            if op == ">=" and not x >= val:
                return False
        elif x != v:
            return False
    return True


TRUY = []


def get_all(dt, filters=None, fields=None, order_by=None, pluck=None, **k):
    TRUY.append((dt, filters))
    ds = [r for r in DB.get(dt, []) if _khop(r, filters)]
    if order_by == "employee_name":
        ds.sort(key=lambda r: r.get("employee_name") or "")
    if pluck:
        return [r.get(pluck) for r in ds]
    return [_dict({f: r.get(f) for f in fields}) if fields else _dict(r) for r in ds]


class Settings(_dict):
    """SX Settings (Single) giả: get_settings đọc bản này; get_doc + save ghi lại (đếm số lần lưu)."""

    def append(self, k, v):
        r = _dict(v)
        self.setdefault(k, []).append(r)
        return r

    def save(self):
        LUU.append(json.loads(json.dumps({k: v for k, v in self.items() if k != "flags"}, default=str)))
        return self


SET = Settings()
LUU = []


def dat_settings(an=None, migrate=True):
    SET.clear()
    SET.update(nguon_cong_khoan="Employment Type", gia_tri_cong_khoan="Công khoán", flags=_dict())
    CO_O["an_ghi_hop"] = migrate
    if migrate:
        SET["an_ghi_hop"] = [_dict(employee=e, ten_nhan_vien=t) for e, t in (an or [])]
    LUU.clear()


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.session = types.SimpleNamespace(user="qc@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_doc = lambda dt, n=None: SET if dt == "SX Settings" else None
frappe.get_meta = lambda dt: types.SimpleNamespace(
    has_field=lambda f: (CO_O["an_ghi_hop"] if f == "an_ghi_hop" else f == "employee_number"))
frappe.db = types.SimpleNamespace(exists=lambda *a, **k: True)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: float(v or 0)
fu.getdate = lambda x=None: x if isinstance(x, date) else (HOM_NAY if x is None else date.fromisoformat(str(x)[:10]))
fu.nowdate = lambda: str(HOM_NAY)
fu.add_days = lambda d, n: d
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.api", "sx.config", "sx.sx", "sx.sx.doctype", "sx.sx.doctype.sx_bang_vao_hop"):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m
bvh = types.ModuleType("sx.sx.doctype.sx_bang_vao_hop.sx_bang_vao_hop")
bvh.CONG_NHAT, bvh.KHOAN_CHUNG = "CONG_NHAT", "KHOAN_CHUNG"
sys.modules[bvh.__name__] = bvh


def ham_that(tep, ten, **g):
    """ĐÚNG mã một hàm trong tệp nguồn — test chạy mã thật."""
    goc = open(tep, encoding="utf-8").read()
    fn = next(n for n in ast.parse(goc).body if isinstance(n, ast.FunctionDef) and n.name == ten)
    ns = dict(g)
    exec(compile(ast.Module([fn], []), tep, "exec"), ns)
    return ns[ten]


ut = types.ModuleType("sx.utils")
for ten in ("bang_don_gia", "don_gia_ap_dung", "get_bom_active", "get_dau_items", "nap_bom", "ton_bin"):
    setattr(ut, ten, lambda *a, **k: None)
ut.items_tp = lambda *a, **k: []
ut.get_settings = lambda: SET
ut.dat_ten_hien_thi = ham_that("sx/utils.py", "dat_ten_hien_thi")
ut.don_gia_gio = lambda: 33000.0
ut.don_gia_gio_2 = lambda: 30000.0
sys.modules["sx.utils"] = ut


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


R = nap("sx.config.roles", "sx/config/roles.py")
PT = nap("sx.api.portal", "sx/api/portal.py")
THE = nap("sx.api.the", "sx/api/the.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct and not dk else ''}")


def thu(fn):
    try:
        return fn(), None
    except Loi as e:
        return None, str(e)


XUONG = [nv("HR-01", "Nguyễn Văn An", "101"), nv("HR-02", "Trần Thị Hà", "102"), nv("HR-03", "Lê Văn Lập", "103"),
         nv("HR-04", "Phạm Hồng Phúc", "104"), nv("HR-05", "Đỗ Thị Nga", "105"),
         nv("HR-06", "Vũ Văn Bình", "106", loai="Hành chính"), nv("HR-07", "Hoàng Văn Cường", "107", trang="Left")]
BA = [("HR-02", "Trần Thị Hà"), ("HR-03", "Lê Văn Lập"), ("HR-04", "Phạm Hồng Phúc")]


def ten_ngan(ds):
    return {e["name"]: e["ten_hien_thi"] for e in ds}


print("-- danh sách công nhân của bảng ghi hộp --")
dat_du_lieu(XUONG)
dat_settings()
ds, cb = PT._nhan_vien_vao_hop()
kiem("chưa ẩn ai: đủ công khoán Active (không lẫn hành chính / đã nghỉ)",
     ten_ngan(ds) == {"HR-01": "An", "HR-02": "Hà", "HR-03": "Lập", "HR-04": "Phúc", "HR-05": "Nga"} and cb is None,
     ten_ngan(ds))
dat_settings(an=BA)
ds, cb = PT._nhan_vien_vao_hop()
kiem("ẩn Hà, Lập, Phúc → bảng ghi hộp chỉ còn An, Nga", ten_ngan(ds) == {"HR-01": "An", "HR-05": "Nga"}, ten_ngan(ds))
kiem("… lọc ngay trong truy vấn Employee (không lọc tay sau khi lấy hết)",
     next(f for dt, f in reversed(TRUY) if dt == "Employee").get("name") == ("not in", ["HR-02", "HR-03", "HR-04"]),
     TRUY[-1])
ds_ca, _cb = PT._nhan_vien_vao_hop(ca_nguoi_an=True)
kiem("ca_nguoi_an=True (lệnh dò tên) → còn cả người đã ẩn", len(ds_ca) == 5, ten_ngan(ds_ca))
kiem("… danh sách thường không bị lẫn (ẩn vẫn ẩn)", len(PT._nhan_vien_vao_hop()[0]) == 2)
dat_settings(an=BA + [(None, None), ("", "")])
try:
    con = ten_ngan(PT._nhan_vien_vao_hop()[0])
except TypeError as ex:                 # sorted([None, "HR-02"]) — gãy cả màn Ghi hộp
    con = f"lỗi: {ex}"
kiem("dòng trống ở bảng ẩn (chưa chọn người) không làm gãy, không ẩn thêm ai",
     con == {"HR-01": "An", "HR-05": "Nga"}, con)
dat_settings(migrate=False)
kiem("site CHƯA migrate (chưa có bảng ẩn) → như cũ, không lỗi", len(PT._nhan_vien_vao_hop()[0]) == 5)

print("\n-- một chỗ lọc cho cả mã quét và in thẻ QR --")
dat_settings(an=BA)
PT._danh_muc_khoan = lambda ngay: []
PT._sp_gan_day = lambda: []
dm = PT._danh_muc({"vaohop", "quet"}, "2026-11-10", set(VAI), False)
kiem("màn Ghi hộp (boot): không có Hà, Lập, Phúc", sorted(e["name"] for e in dm["nhan_vien"]) == ["HR-01", "HR-05"],
     [e["name"] for e in dm["nhan_vien"]])
kiem("bảng mã quét: quét thẻ Hà (102 / HR-02) không ra ai — không ghi hộp được cho người đã ẩn",
     not ({"102", "HR-02", "103", "HR-03", "104", "HR-04"} & set(dm["ma_quet"]["nv"]))
     and dm["ma_quet"]["nv"].get("101") == "HR-01", dm["ma_quet"]["nv"])
the = THE.danh_sach_the()
kiem("in thẻ QR: chỉ An, Nga", [t["ten"] for t in the] == ["Nguyễn Văn An", "Đỗ Thị Nga"], the)

print("\n-- lệnh an_ghi_hop: xem trước / ghi --")
dat_du_lieu(XUONG)
dat_settings()
kq = PT.xu_ly_an_ghi_hop("Hà, Lập, Phúc")
kiem("xem trước: đúng ba người, CHƯA ghi gì", [e["name"] for e in kq["nguoi"]] == ["HR-02", "HR-03", "HR-04"]
     and kq["se_an"] == ["HR-02", "HR-03", "HR-04"] and not kq["ghi"] and LUU == [] and SET["an_ghi_hop"] == [], kq)
kq = PT.xu_ly_an_ghi_hop("Hà, Lập, Phúc", chay=1)
kiem("chay=1 → lưu SX Settings MỘT lần, ba dòng (mã + họ tên)", kq["ghi"] and len(LUU) == 1
     and [(r["employee"], r["ten_nhan_vien"]) for r in LUU[0]["an_ghi_hop"]] == BA, LUU)
kiem("… lưu qua save() của doc (có lịch sử phiên bản), bỏ qua quyền vì là lệnh bench",
     SET["flags"].get("ignore_permissions") is True)
kiem("… sau đó bảng ghi hộp không còn họ", ten_ngan(PT._nhan_vien_vao_hop()[0]) == {"HR-01": "An", "HR-05": "Nga"})
kq = PT.xu_ly_an_ghi_hop("Hà, Lập, Phúc", chay=1)
kiem("chạy lại → không thêm dòng trùng, không lưu nữa", not kq["ghi"] and len(LUU) == 1 and len(SET["an_ghi_hop"]) == 3
     and kq["da_an"] == ["HR-02", "HR-03", "HR-04"], kq)
dat_settings()
nfd = unicodedata.normalize("NFD", "Hà")
kq = PT.xu_ly_an_ghi_hop([f"  {nfd.upper()} ", "lê   văn lập", "104"])
kiem("gõ HOA / dấu cách thừa / bộ gõ dấu tổ hợp (NFD) / họ tên đầy đủ / mã chấm công → vẫn khớp đúng người",
     [e["name"] for e in kq["nguoi"]] == ["HR-02", "HR-03", "HR-04"] and not kq["khong"] and not kq["mo_ho"], kq)
kq = PT.xu_ly_an_ghi_hop("HR-02; Hà\nTrần Thị Hà")
kiem("cùng một người gõ ba kiểu → một người, không ghi trùng", [e["name"] for e in kq["nguoi"]] == ["HR-02"], kq)

print("\n-- tên sai / trùng tên: KHÔNG ghi ai --")
kq = PT.xu_ly_an_ghi_hop("Hà, Lập, Phuc", chay=1)
kiem("gõ thiếu dấu \"Phuc\" → không thấy; hai tên đúng cũng KHÔNG ghi (tránh ẩn lệch)",
     kq["khong"] == ["Phuc"] and not kq["ghi"] and LUU == [] and SET["an_ghi_hop"] == [], kq)
kq = PT.xu_ly_an_ghi_hop("Thị Hà, Văn, Hà Thị")
kiem("gõ một đoạn họ tên (\"Thị Hà\", \"Văn\") không đoán gần đúng — không thấy, không thành mơ hồ",
     kq["khong"] == ["Thị Hà", "Văn", "Hà Thị"] and not kq["nguoi"] and not kq["mo_ho"], kq)
kq = PT.xu_ly_an_ghi_hop("Vũ Văn Bình, Hoàng Văn Cường")
kiem("người ngoài nhóm công khoán / đã nghỉ → không thấy", kq["khong"] == ["Vũ Văn Bình", "Hoàng Văn Cường"], kq)
dat_du_lieu(XUONG + [nv("HR-08", "Nguyễn Thu Hà", "108")])
kq = PT.xu_ly_an_ghi_hop("Hà, Lập", chay=1)
kiem("hai người tên Hà (màn hiện \"Hà Trần\", \"Hà Nguyễn\") → gõ \"Hà\" là mơ hồ, liệt kê cả hai, không ghi ai",
     [m["ten"] for m in kq["mo_ho"]] == ["Hà"] and sorted(e["name"] for e in kq["mo_ho"][0]["nguoi"])
     == ["HR-02", "HR-08"] and not kq["ghi"] and LUU == [], kq)
bc = PT.bao_cao_an_ghi_hop(kq)
kiem("… báo cáo ghi tên đang hiện + họ tên + mã của từng người trùng để gõ lại",
     "\"Hà Trần\" = Trần Thị Hà (HR-02)" in bc and "\"Hà Nguyễn\" = Nguyễn Thu Hà (HR-08)" in bc
     and "CHƯA ẨN AI" in bc, bc)
kq = PT.xu_ly_an_ghi_hop("Hà Trần, Lập", chay=1)
kiem("gõ đúng tên đang hiện \"Hà Trần\" → ẩn đúng Trần Thị Hà", kq["ghi"]
     and [r["employee"] for r in SET["an_ghi_hop"]] == ["HR-02", "HR-03"], SET["an_ghi_hop"])
kiem("… Nguyễn Thu Hà còn lại, tên ngắn lại thành \"Hà\" (không còn ai trùng)",
     ten_ngan(PT._nhan_vien_vao_hop()[0]).get("HR-08") == "Hà", ten_ngan(PT._nhan_vien_vao_hop()[0]))

print("\n-- chặn --")
dat_du_lieu(XUONG)
dat_settings(migrate=False)
kiem("site chưa migrate → báo chạy migrate, không ghi",
     "migrate" in (thu(lambda: PT.xu_ly_an_ghi_hop("Hà", 1))[1] or "")
     and LUU == [])
dat_settings()
kiem("không có tên → báo cách gõ", "Chưa có tên" in (thu(lambda: PT.xu_ly_an_ghi_hop(" , ", 1))[1] or ""))
goc = open("sx/api/portal.py", encoding="utf-8").read()
kiem("lệnh KHÔNG whitelist (chỉ chạy bằng bench)", "@frappe.whitelist()\ndef an_ghi_hop" not in goc
     and "@frappe.whitelist()\ndef xu_ly_an_ghi_hop" not in goc and "def an_ghi_hop(" in goc)

print("\n-- báo dữ liệu tháng này của người sắp ẩn --")
N3, N4, N_CU = date(2026, 11, 3), date(2026, 11, 4), date(2026, 10, 30)
dat_du_lieu(XUONG,
            ngay=[dict(name="NSX-03", ngay=N3), dict(name="NSX-04", ngay=N4), dict(name="NSX-CU", ngay=N_CU)],
            bang=[dict(name="BVH-03", ngay_sx="NSX-03", docstatus=0),
                  dict(name="BVH-04", ngay_sx="NSX-04", docstatus=0),
                  dict(name="BVH-CU", ngay_sx="NSX-CU", docstatus=0)],
            hop=[dict(parent="BVH-03", parenttype="SX Bang Vao Hop", nhan_vien="HR-02"),
                 dict(parent="BVH-03", parenttype="SX Bang Vao Hop", nhan_vien="HR-02"),
                 dict(parent="BVH-03", parenttype="SX Bang Vao Hop", nhan_vien="HR-01"),
                 dict(parent="BVH-CU", parenttype="SX Bang Vao Hop", nhan_vien="HR-02")],
            an=[dict(parent="BVH-04", parenttype="SX Bang Vao Hop", nhan_vien="HR-02", an_ca=1, an_dem=0, so_gio=0,
                     so_gio_2=0),
                dict(parent="BVH-04", parenttype="SX Bang Vao Hop", nhan_vien="HR-04", an_ca=0, an_dem=0, so_gio=0,
                     so_gio_2=0),
                dict(parent="BVH-03", parenttype="SX Bang Vao Hop", nhan_vien="HR-03", an_ca=0, an_dem=0, so_gio=0,
                     so_gio_2=2)],
            phieu=[dict(name="PL-HA-11", employee="HR-02", thang=11, nam=2026, docstatus=0, luong_san_pham=150000),
                   dict(name="PL-HA-10", employee="HR-02", thang=10, nam=2026, docstatus=1, luong_san_pham=90000)])
dat_settings()
kq = PT.xu_ly_an_ghi_hop("Hà, Lập, Phúc")
d = kq["du_lieu"]
kiem("Hà: 2 dòng ghi hộp (03/11) + chấm ăn (04/11) + phiếu lương tháng 11 — bỏ ngày tháng trước, phiếu tháng trước",
     (d["HR-02"]["hop"], d["HR-02"]["an"], d["HR-02"]["ngay"], [p.name for p in d["HR-02"]["phieu"]])
     == (2, 1, [N3, N4], ["PL-HA-11"]), d["HR-02"])
kiem("Lập: chỉ làm theo giờ mức 2 cũng tính là đã được ghi", (d["HR-03"]["an"], d["HR-03"]["ngay"]) == (1, [N3]),
     d["HR-03"])
kiem("Phúc: dòng chấm theo người toàn số 0 → không tính", d["HR-04"] == {"hop": 0, "an": 0, "ngay": [], "phieu": []},
     d["HR-04"])
bc = PT.bao_cao_an_ghi_hop(kq)
kiem("báo cáo xem trước: tiêu đề, từng người \"sẽ ẩn\" kèm tên đang hiện, cách ghi thật",
     "XEM TRƯỚC" in bc and "Hà → Trần Thị Hà (HR-02), tên trên màn Ghi hộp \"Hà\": sẽ ẩn" in bc
     and "'chay': 1" in bc, bc)
kiem("… cảnh báo Hà: số dòng, ngày, phiếu lương — và dọn TRƯỚC khi ẩn",
     "⚠ Hà: tháng này đã có 2 dòng ghi hộp, 1 ngày chấm ăn / làm theo giờ, phiếu lương PL-HA-11 (nháp, lương SP "
     "150.000 đ) — ngày 03/11, 04/11" in bc and "dọn TRƯỚC khi ẩn" in bc, bc)
kiem("… Phúc không có gì → không cảnh báo", "⚠ Phúc" not in bc, bc)
ra = io.StringIO()
with contextlib.redirect_stdout(ra):
    PT.an_ghi_hop("Hà, Lập, Phúc", chay=1)
kiem("lệnh bench in báo cáo ĐÃ GHI + cách hiện lại", "ĐÃ GHI vào SX Settings" in ra.getvalue()
     and "Đã ẩn 3 người" in ra.getvalue() and "xoá dòng" in ra.getvalue() and len(LUU) == 1, ra.getvalue())

print("\n-- DocType --")
st = json.load(open("sx/sx/doctype/sx_settings/sx_settings.json", encoding="utf-8"))
o = next(f for f in st["fields"] if f["fieldname"] == "an_ghi_hop")
kiem("SX Settings có bảng an_ghi_hop (SX Cong Khoan An) trong field_order",
     o["fieldtype"] == "Table" and o["options"] == "SX Cong Khoan An" and "an_ghi_hop" in st["field_order"])
ck = json.load(open("sx/sx/doctype/sx_cong_khoan_an/sx_cong_khoan_an.json", encoding="utf-8"))
f = {x["fieldname"]: x for x in ck["fields"]}
kiem("bảng con: chọn Employee (bắt buộc) + họ tên tự lấy, hiện cả hai trên lưới",
     ck["istable"] == 1 and f["employee"]["options"] == "Employee" and f["employee"].get("reqd") == 1
     and f["ten_nhan_vien"].get("fetch_from") == "employee.employee_name"
     and all(x.get("in_list_view") for x in f.values()))

print()
print("ANGHIHOP-HỎNG ({})".format(hong) if hong else "ANGHIHOP-OK")
sys.exit(1 if hong else 0)
