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
    phieu("PL-2", "Trần Văn Bình", 0, luong_san_pham=3_000_000, luong_thuc_nhan=3_100_000,
          # D225: làm theo giờ — số lượng là số GIỜ, gộp theo đơn giá / giờ
          chi_tiet=[Doc(ngay=date(2026, 10, 1), san_pham="TP-SEN", ten_san_pham="Bánh sen", cach_lam=None,
                        so_luong=10, don_gia=1200, thanh_tien=12_000),
                    Doc(ngay=date(2026, 10, 1), theo_gio=1, so_gio=2.5, san_pham=None, ten_san_pham="Làm theo giờ",
                        cach_lam=None, so_luong=0, don_gia=33_000, thanh_tien=82_500),
                    Doc(ngay=date(2026, 10, 3), theo_gio=1, so_gio=1.5, san_pham=None, ten_san_pham="Làm theo giờ",
                        cach_lam=None, so_luong=0, don_gia=33_000, thanh_tien=49_500),
                    # D233: mức thứ hai — cùng ngày 03/10, đơn giá 30.000
                    Doc(ngay=date(2026, 10, 3), theo_gio=1, so_gio=2, san_pham=None, ten_san_pham="Làm theo giờ",
                        cach_lam=None, so_luong=0, don_gia=30_000, thanh_tien=60_000)],
          dong=[Doc(ngay=date(2026, 10, 1), thu="Thứ 5", an_ca=1, an_dem=0, luong_sp=94_500, he_so=1,
                    thu_nhap_ngay=114_500),
                Doc(ngay=date(2026, 10, 3), thu="Thứ 7", an_ca=0, an_dem=0, luong_sp=49_500, he_so=1,
                    thu_nhap_ngay=49_500)]),
    phieu("PL-3", "Lê Huỷ", 2, luong_san_pham=9_999_999, luong_thuc_nhan=9_999_999),
    phieu("PL-9", "Tháng khác", 0, thang=9, luong_thuc_nhan=1),
    # D234: một ngày làm những gì. Dòng chi tiết CỐ Ý lộn xộn như sau khi sửa tay trên Desk / chốt lại ngày cũ: dòng giờ
    # 30.000 đứng trước dòng giờ 33.000 và trước sản phẩm; một mã + cách làm + đơn giá hai dòng trong cùng ngày; mã ghi
    # trước có thành tiền NHỎ hơn mã ghi sau (thứ tự ghi ≠ thứ tự tiền); dòng nợ giá (0 đồng) cùng mã cùng giá khác cách
    # làm; ngày 02/08 (Chủ nhật) chỉ chấm ăn. Tháng 8 — không lẫn vào danh sách tháng 10 ở trên.
    phieu("PL-4", "Phạm Thị Dung", 0, thang=8,
          chi_tiet=[Doc(ngay=date(2026, 8, 3), theo_gio=1, so_gio=2, san_pham=None, ten_san_pham="Làm theo giờ",
                        cach_lam=None, so_luong=0, don_gia=30_000, thanh_tien=60_000),
                    Doc(ngay=date(2026, 8, 3), san_pham="TP-SEN", ten_san_pham="Bánh sen", cach_lam="Máy",
                        so_luong=40, don_gia=900, thanh_tien=36_000),
                    Doc(ngay=date(2026, 8, 4), san_pham="TP-TT", ten_san_pham="Bánh TT", cach_lam="Tay",
                        so_luong=30, don_gia=0, thanh_tien=0),
                    Doc(ngay=date(2026, 8, 4), san_pham="TP-TT", ten_san_pham="Bánh TT", cach_lam="Máy",
                        so_luong=12, don_gia=0, thanh_tien=0),
                    Doc(ngay=date(2026, 8, 3), theo_gio=1, so_gio=1.5, san_pham=None, ten_san_pham="Làm theo giờ",
                        cach_lam=None, so_luong=0, don_gia=33_000, thanh_tien=49_500),
                    Doc(ngay=date(2026, 8, 3), san_pham="TP-TT", ten_san_pham="Bánh TT", cach_lam="Tay",
                        so_luong=30, don_gia=2_000, thanh_tien=60_000),
                    Doc(ngay=date(2026, 8, 3), san_pham="TP-SEN", ten_san_pham="Bánh sen", cach_lam="Máy",
                        so_luong=10, don_gia=900, thanh_tien=9_000)],
          dong=[Doc(ngay=date(2026, 8, 2), thu="Chủ nhật", an_ca=1, an_dem=1, tien_an=30_000, luong_sp=0, he_so=1.2,
                    thu_nhap_ngay=30_000),
                Doc(ngay=date(2026, 8, 3), thu="Thứ 2", an_ca=1, an_dem=0, tien_an=20_000, luong_sp=214_500, he_so=1,
                    thu_nhap_ngay=234_500),
                Doc(ngay=date(2026, 8, 4), thu="Thứ 3", an_ca=0, an_dem=0, tien_an=0, luong_sp=0, he_so=1,
                    thu_nhap_ngay=0)]),
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
c = L.chi_tiet("PL-2")
gio = [x for x in c["san_pham"] if x.get("theo_gio")]
kiem("D225: làm theo giờ gộp MỘT dòng mỗi đơn giá / giờ — số lượng là số giờ (2,5 + 1,5); D233: mức 30.000 là dòng "
     "riêng ghi rõ đơn giá (quản lý thấy rõ mức)",
     sorted((x["ten"], x["so_luong"], x["don_gia"], x["thanh_tien"]) for x in gio)
     == [("Làm theo giờ", 2.0, 30_000, 60_000), ("Làm theo giờ", 4.0, 33_000, 132_000)]
     and len(c["san_pham"]) == 3, str(c["san_pham"]))
kiem("… từng ngày kèm số giờ của ngày (cộng mọi mức: 03/10 = 1,5 + 2)", [(x["ngay"], x["so_gio"]) for x in c["ngay"]]
     == [("2026-10-01", 2.5), ("2026-10-03", 3.5)], str(c["ngay"]))
kiem("… mã hàng có đúng tên dòng sản phẩm, không lẫn dòng giờ",
     [(x["ten"], x["so_luong"]) for x in c["san_pham"] if not x.get("theo_gio")] == [("Bánh sen", 10)])

print("\n-- D234: từng ngày làm những gì, đơn giá, thành tiền --")
c = L.chi_tiet("PL-4")
ng = {x["ngay"]: x for x in c["ngay"]}
dong_sp = lambda d: [(x["ten"], x["cach_lam"], x["so_luong"], x["don_gia"], x["thanh_tien"], bool(x.get("theo_gio")))
                     for x in ng[d]["sp"]]
kiem("ngày 03/08: sản phẩm của ĐÚNG ngày đó — số lượng, đơn giá, thành tiền; cùng mã + cách làm + đơn giá gộp một "
     "dòng (40 + 10); sản phẩm giữ thứ tự ghi (sen trước TT dù ít tiền hơn), làm theo giờ sau (giá cao trước) dù "
     "dòng giờ 30.000 ghi đầu tiên",
     dong_sp("2026-08-03") == [("Bánh sen", "Máy", 50, 900.0, 45_000.0, False),
                               ("Bánh TT", "Tay", 30, 2_000.0, 60_000.0, False),
                               ("Làm theo giờ", "", 1.5, 33_000.0, 49_500.0, True),
                               ("Làm theo giờ", "", 2.0, 30_000.0, 60_000.0, True)], str(dong_sp("2026-08-03")))
kiem("… cộng thành tiền các dòng của ngày = lương SP ngày trên phiếu (214.500)",
     sum(x["thanh_tien"] for x in ng["2026-08-03"]["sp"]) == ng["2026-08-03"]["luong_sp"] == 214_500)
kiem("… kèm tiền ăn và thu nhập ngày lấy nguyên từ phiếu (dòng cộng ngày trên thẻ)",
     (ng["2026-08-03"]["tien_an"], ng["2026-08-03"]["thu_nhap"]) == (20_000, 234_500), str(ng["2026-08-03"]))
kiem("ngày 04/08: dòng chưa có giá vẫn hiện — đơn giá 0, thành tiền 0 (thẻ ghi ⚠ chưa có giá); cùng mã cùng giá "
     "khác cách làm là HAI dòng",
     dong_sp("2026-08-04") == [("Bánh TT", "Tay", 30, 0.0, 0.0, False), ("Bánh TT", "Máy", 12, 0.0, 0.0, False)],
     str(dong_sp("2026-08-04")))
kiem("ngày 02/08 chỉ chấm ăn: không dòng sản phẩm, tiền ăn 30.000 = thu nhập ngày",
     ng["2026-08-02"]["sp"] == [] and (ng["2026-08-02"]["tien_an"], ng["2026-08-02"]["thu_nhap"]) == (30_000, 30_000),
     str(ng["2026-08-02"]))
kiem("ngày theo đúng thứ tự dòng ngày của phiếu", list(ng) == ["2026-08-02", "2026-08-03", "2026-08-04"], str(list(ng)))
sen = [x for x in c["san_pham"] if x["ten"] == "Bánh sen"]
kiem("sản phẩm trong tháng KHÔNG bị cộng hai lần khi tách thêm theo ngày (sen 50, không 100)",
     [(x["so_luong"], x["thanh_tien"]) for x in sen] == [(50, 45_000.0)], str(sen))
kiem("… tổng thành tiền cả tháng = tổng các ngày",
     sum(x["thanh_tien"] for x in c["san_pham"]) == sum(x["thanh_tien"] for d in c["ngay"] for x in d["sp"]) == 214_500)
c1 = L.chi_tiet("PL-1")
kiem("phiếu có ngày không có dòng chi tiết (04/10) → danh sách sản phẩm của ngày rỗng, không lỗi",
     c1["ngay"][0]["sp"] == [], str(c1["ngay"][0]))

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
