"""D110 — thẻ Phiếu lương xem nhanh trên màn Quản lý (sx/api/luong.py).

Chỉ đọc, nhưng là TIỀN LƯƠNG: sai thì sai kiểu người ta tin và đọc to cho công
nhân. Canh: phiếu đã huỷ không lọt vào tổng; số lấy nguyên từ phiếu (không tính
lại khác đi); dòng nợ đơn giá được cảnh báo; chỉ quản lý mở được.

Chạy: python3 scripts/test-luong.py   (verify.sh gọi sẵn)
"""

import importlib.util
import os
import re
import sys
import types
from datetime import date

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

VAI = {"SX Quan Ly"}
NO_GIA = {}            # phiếu -> số dòng nợ giá (giả kết quả SQL)


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)


def phieu(name, ten, ds=0, **kw):
    base = dict(name=name, employee=name.replace("PL-", "HR-"), ten_nhan_vien=ten, thang=10,
                nam=2026, docstatus=ds, trang_thai="Đã duyệt" if ds == 1 else "Nháp",
                ngay_cong=20, ngay_san_xuat=22, luong_san_pham=0, tien_an=0, chuyen_can=0,
                ho_tro_ngay_cong=0, thuong_tham_nien=0, ho_tro=0, tien_phat=0, bao_hiem=0,
                tong_tien=0, tong_khau_tru=0, luong_thuc_nhan=0, chi_tiet=[], dong=[], phat=[],
                ghi_chu="")
    base.update(kw)
    return Doc(base)


PHIEU = [
    phieu("PL-1", "Nguyễn Thị An", 1, luong_san_pham=5_000_000, tien_an=400_000, chuyen_can=300_000,
          tong_tien=5_700_000, bao_hiem=200_000, tong_khau_tru=200_000, luong_thuc_nhan=5_500_000,
          chi_tiet=[Doc(ngay=date(2026, 10, 1), san_pham="TP-SEN", ten_san_pham="Bánh sen",
                        cach_lam=None, so_luong=100, don_gia=1200, thanh_tien=120_000),
                    Doc(ngay=date(2026, 10, 2), san_pham="TP-SEN", ten_san_pham="Bánh sen",
                        cach_lam=None, so_luong=80, don_gia=1200, thanh_tien=96_000),
                    Doc(ngay=date(2026, 10, 2), san_pham="TP-SEN", ten_san_pham="Bánh sen",
                        cach_lam="Máy", so_luong=50, don_gia=900, thanh_tien=45_000)],
          dong=[Doc(ngay=date(2026, 10, 4), thu="Chủ nhật", an_ca=1, an_dem=0, luong_sp=96_000,
                    he_so=1.2, thu_nhap_ngay=135_200)],
          phat=[Doc(ly_do="Hộp móp", thanh_tien=20_000)]),
    phieu("PL-2", "Trần Văn Bình", 0, luong_san_pham=3_000_000, luong_thuc_nhan=3_100_000),
    phieu("PL-3", "Lê Huỷ", 2, luong_san_pham=9_999_999, luong_thuc_nhan=9_999_999),
    phieu("PL-9", "Tháng khác", 0, thang=9, luong_thuc_nhan=1),
]


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            if v[0] == "<" and not x < v[1]:
                return False
        elif x != v:
            return False
    return True


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = lambda dt, filters=None, **k: sorted(
    [Doc(h) for h in PHIEU if _khop(h, filters)], key=lambda h: h.ten_nhan_vien)
frappe.get_doc = lambda dt, n: next(h for h in PHIEU if h.name == n)
frappe.db = types.SimpleNamespace(table_exists=lambda dt: True,
                                  sql=lambda q, a=None: [(t, NO_GIA[t]) for t in a[0] if NO_GIA.get(t)])
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: float(v or 0)
fu.getdate = lambda x=None: x
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.api", "sx.config"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


R = nap("sx.config.roles", "sx/config/roles.py")
L = nap("sx.api.luong", "sx/api/luong.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


def thu(fn):
    try:
        return fn(), None
    except Loi as e:
        return None, str(e)


print("-- danh sách tháng --")
NO_GIA["PL-2"] = 3
t = L.thang(2026, 10)
kiem("chỉ phiếu tháng 10, bỏ phiếu ĐÃ HUỶ", [x["name"] for x in t["danh_sach"]] == ["PL-1", "PL-2"],
     str([x["name"] for x in t["danh_sach"]]))
kiem("tổng thực nhận / lương SP lấy nguyên từ phiếu",
     t["tong"]["thuc_nhan"] == 8_600_000 and t["tong"]["luong_san_pham"] == 8_000_000, str(t["tong"]))
kiem("đếm đã duyệt", t["tong"]["da_duyet"] == 1 and t["danh_sach"][0]["da_duyet"])
kiem("phiếu còn dòng nợ đơn giá được đánh dấu",
     t["danh_sach"][1]["no_gia"] == 3 and t["tong"]["no_gia"] == 1)
kiem("tìm theo tên (không phân biệt hoa thường)",
     [x["name"] for x in L.thang(2026, 10, q="bình")["danh_sach"]] == ["PL-2"])
kiem("tháng lạ → chặn", thu(lambda: L.thang(2026, 13))[1] is not None)

print("\n-- chi tiết một phiếu --")
c = L.chi_tiet("PL-1")
kiem("sản phẩm gộp theo mã + cách làm + đơn giá",
     [(x["cach_lam"], x["so_luong"], x["thanh_tien"]) for x in c["san_pham"]]
     == [("", 180, 216_000), ("Máy", 50, 45_000)], str(c["san_pham"]))
kiem("chỉ hiện khoản khác 0", [x["ten"] for x in c["cong"]]
     == ["Lương sản phẩm", "Tiền ăn ca + ăn đêm", "Chuyên cần"], str(c["cong"]))
kiem("khấu trừ tách riêng", c["tru"] == [{"ten": "Bảo hiểm", "tien": 200_000}], str(c["tru"]))
kiem("thực nhận đúng phiếu", c["thuc_nhan"] == 5_500_000)
kiem("từng ngày kèm hệ số Chủ nhật", c["ngay"][0]["he_so"] == 1.2 and c["ngay"][0]["thu_nhap"] == 135_200)
kiem("lỗi phạt", c["phat"] == [{"ly_do": "Hộp móp", "tien": 20_000}])

print("\n-- quyền --")
for vai in ("SX Vao Hop", "SX Thu Kho", "SX Ghi So", "SX QC"):
    VAI.clear(); VAI.add(vai)
    kiem(f"{vai} không xem được lương", thu(lambda: L.thang(2026, 10))[1] is not None
         and thu(lambda: L.chi_tiet("PL-1"))[1] is not None)
VAI.clear(); VAI.add("SX Quan Ly")
kiem("thẻ phiếu lương nằm ở màn Quản lý, chỉ quản lý",
     "phieuluong" in R.VIEW_CARDS["quanly"] and R.CARD_ROLES["phieuluong"] == [R.QUAN_LY])
js = open("sx/public/sx/cards/phieuluong.js", encoding="utf-8").read()
for m in sorted(set(re.findall(r"sx\.api\.luong\.(\w+)", js))):
    kiem(f"card gọi method có thật: {m}", callable(getattr(L, m, None)))
kiem("shell.js biết đường dẫn card",
     "phieuluong: '/assets/sx/sx/cards/phieuluong.js'" in open("sx/public/sx/shell.js").read())

print("LUONG-OK" if not hong else f"LUONG: {hong} HỎNG")
sys.exit(1 if hong else 0)
