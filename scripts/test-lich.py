"""D108 — lịch tháng ở tab Ghi hộp / Ghi sổ / Nhập kho.

Lịch chỉ đọc, nhưng sai thì sai kiểu dễ tin: ô trống mà thật ra đã ghi (QC đi ghi
lại lần hai), hoặc ô có số mà là số của phiếu đã huỷ / phiếu nháp chưa vào kho,
hoặc công nhật bị tính là "người".

Nạp sx/api/lich.py và sx/config/roles.py THẬT; frappe là giả.
Chạy: python3 scripts/test-lich.py   (verify.sh gọi sẵn)
"""

import importlib.util
import os
import re
import sys
import types
from datetime import date

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

D = date
BANG = {}
VAI = {"SX Vao Hop"}


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "in" and x not in m:
                return False
            if op == "<" and not (x or 0) < m:
                return False
            if op == "between" and not (m[0] <= x <= m[1]):
                return False
        elif x != v:
            return False
    return True


def get_all(dt, filters=None, fields=None, pluck=None, **k):
    ra = [Doc(h) for h in BANG.get(dt, []) if _khop(h, filters)]
    return [h.get(pluck) for h in ra] if pluck else ra


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.get_roles = lambda u=None: list(VAI)
frappe.session = types.SimpleNamespace(user="qc1@x")
frappe.get_all = get_all
frappe.db = types.SimpleNamespace(count=lambda dt, f=None: len(get_all(dt, f)))
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.getdate = lambda x=None: x if isinstance(x, date) else date.fromisoformat(str(x)[:10])
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
L = nap("sx.api.lich", "sx/api/lich.py")

BANG.update({
    "Item": [{"name": "TP-SEN", "item_name": "Bánh sen"}, {"name": "TP-TT", "item_name": "Bánh TT"},
             {"name": "BB", "item_name": "Bột bánh"}, {"name": "DX", "item_name": "Đỗ xanh"}],
    "SX Ngay San Xuat": [
        {"name": "N1", "ngay": D(2026, 10, 1), "docstatus": 1, "chot_vaohop": 1, "chot_ghiso": 1},
        {"name": "N2", "ngay": D(2026, 10, 2), "docstatus": 0, "chot_vaohop": 0, "chot_ghiso": 0},
        {"name": "N2-HUY", "ngay": D(2026, 10, 2), "docstatus": 2, "chot_vaohop": 1, "chot_ghiso": 1},
        {"name": "N3", "ngay": D(2026, 10, 3), "docstatus": 1, "chot_vaohop": 1, "chot_ghiso": 0},
        {"name": "N9", "ngay": D(2026, 9, 30), "docstatus": 0, "chot_vaohop": 0, "chot_ghiso": 0},
    ],
    "SX Bang Vao Hop": [
        {"name": "B1", "ngay_sx": "N1", "docstatus": 1}, {"name": "B2", "ngay_sx": "N2", "docstatus": 0},
        {"name": "B2-HUY", "ngay_sx": "N2-HUY", "docstatus": 2}, {"name": "B9", "ngay_sx": "N9", "docstatus": 0},
    ],
    "SX Bang Vao Hop Item": [
        {"parent": "B1", "parenttype": "SX Bang Vao Hop", "nhan_vien": "NV1", "ten_nhan_vien": "An",
         "san_pham": "TP-SEN", "so_hop": 100, "cong_nhat": 0, "nguoi_ghi": "qc1@x"},
        {"parent": "B1", "parenttype": "SX Bang Vao Hop", "nhan_vien": "NV2", "ten_nhan_vien": "Bình",
         "san_pham": "TP-SEN", "so_hop": 80, "cong_nhat": 0, "nguoi_ghi": "qc1@x"},
        {"parent": "B1", "parenttype": "SX Bang Vao Hop", "nhan_vien": None, "ten_nhan_vien": None,
         "san_pham": "TP-SEN", "so_hop": 50, "cong_nhat": 1, "nguoi_ghi": "qc1@x"},
        {"parent": "B2", "parenttype": "SX Bang Vao Hop", "nhan_vien": "NV1", "ten_nhan_vien": "An",
         "san_pham": "TP-TT", "so_hop": 30, "cong_nhat": 0, "nguoi_ghi": "qc1@x"},
        {"parent": "B1", "parenttype": "SX Bang Vao Hop", "nhan_vien": "NV3", "ten_nhan_vien": "Cúc",
         "san_pham": "TP-SEN", "so_hop": 40, "cong_nhat": 0, "nguoi_ghi": "qc2@x"},
        {"parent": "B2-HUY", "parenttype": "SX Bang Vao Hop", "nhan_vien": "NV1", "ten_nhan_vien": "An",
         "san_pham": "TP-TT", "so_hop": 999, "cong_nhat": 0, "nguoi_ghi": "qc1@x"},
        {"parent": "B9", "parenttype": "SX Bang Vao Hop", "nhan_vien": "NV1", "ten_nhan_vien": "An",
         "san_pham": "TP-TT", "so_hop": 7, "cong_nhat": 0, "nguoi_ghi": "qc1@x"},
    ],
    "SX Bao Me": [
        {"parent": "N1", "parenttype": "SX Ngay San Xuat", "item_btp": "BB", "so_me": 3, "tong_kg": 342},
        {"parent": "N1", "parenttype": "SX Ngay San Xuat", "item_btp": "BB", "so_me": 1.5, "tong_kg": 171},
        {"parent": "N2-HUY", "parenttype": "SX Ngay San Xuat", "item_btp": "BB", "so_me": 9, "tong_kg": 9},
        {"parent": "N2", "parenttype": "SX Ngay San Xuat", "item_btp": "BB", "so_me": 0, "tong_kg": 0},
    ],
    "SX Bao Can": [{"parent": "N1", "parenttype": "SX Ngay San Xuat", "item_bot_banh": "BB", "so_me": 4}],
    "SX Xuat Dau": [{"ngay_rang": D(2026, 10, 1), "docstatus": 1, "loai_dau": "DX", "dau_kg": 500,
                     "lo_rang": "R-011026"}],
    "SX Su Co": [{"ngay_san_xuat": "N1"}],
    "SX Phieu Nhap TP": [
        {"name": "PN1", "ngay": D(2026, 10, 1), "docstatus": 1, "tong_dem": 120, "nguoi_duyet": "tk"},
        {"name": "PN2", "ngay": D(2026, 10, 1), "docstatus": 1, "tong_dem": 30, "nguoi_duyet": "tk"},
        {"name": "PN3", "ngay": D(2026, 10, 2), "docstatus": 0, "tong_dem": 77},
        {"name": "PN4", "ngay": D(2026, 10, 2), "docstatus": 2, "tong_dem": 55},
    ],
    "SX Phieu Nhap TP Item": [
        {"parent": "PN1", "parenttype": "SX Phieu Nhap TP", "item": "TP-SEN", "ten": "Bánh sen",
         "so_dem": 100, "dvt": "Hộp"},
        {"parent": "PN1", "parenttype": "SX Phieu Nhap TP", "item": "TP-TT", "ten": "Bánh TT",
         "so_dem": 20, "dvt": "Hộp"},
        {"parent": "PN2", "parenttype": "SX Phieu Nhap TP", "item": "TP-SEN", "ten": "Bánh sen",
         "so_dem": 30, "dvt": "Hộp"},
    ],
})

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


def thu(fn):
    try:
        return fn(), None
    except Loi as e:
        return None, str(e)


print("-- lịch Ghi hộp --")
t = L.thang("vaohop", 2026, 10)
kiem("ngày 1: khoán + công nhật = 230 hộp, đã chốt",
     t["ngay"]["2026-10-01"]["so"] == 230 and t["ngay"]["2026-10-01"]["chot"] == 1, str(t["ngay"]))
kiem("ngày 2: bảng đã HUỶ không cộng vào (chỉ 30)", t["ngay"]["2026-10-02"]["so"] == 30)
kiem("ngày chốt mà 0 hộp vẫn có ô (tô đã chốt)", t["ngay"].get("2026-10-03", {}).get("chot") == 1)
kiem("ngày không ghi gì → không có ô (không ghi 0)", "2026-10-04" not in t["ngay"])
kiem("không lẫn tháng khác (30/09)", "2026-09-30" not in t["ngay"] and t["tong"] == 260)
c = L.chi_tiet("vaohop", "2026-10-01")
mh = next(k for k in c["khoi"] if k["ten"] == "Theo mã hàng")["dong"]
ng = next(k for k in c["khoi"] if k["ten"] == "Theo người")["dong"]
kiem("chi tiết theo mã: tách khoán / công nhật",
     mh == [{"trai": "Bánh sen", "phai": 230, "phu": "khoán 180 · công nhật 50"}], str(mh))
kiem("chi tiết theo người: công nhật KHÔNG là một người", [x["trai"] for x in ng] == ["An", "Bình"])
kiem("chips: đã chốt, công nhật, số người",
     c["chips"] == ["đã chốt Vào hộp", "công nhật 50 hộp", "2 người"], str(c["chips"]))
kiem("ngày trống: không khối nào, không lỗi", L.chi_tiet("vaohop", "2026-10-20")["khoi"] == [])

print("\n-- D113: mỗi QC chỉ thấy phần mình ghi --")
kiem("QC1 không thấy 40 hộp QC2 ghi (tổng ngày 1 vẫn 230)",
     L.thang("vaohop", 2026, 10)["ngay"]["2026-10-01"]["so"] == 230)
kiem("… và chi tiết không có người QC2 chấm",
     "Cúc" not in str(L.chi_tiet("vaohop", "2026-10-01")))
VAI.clear(); VAI.add("SX Quan Ly")
kiem("Quản lý thấy cả hai QC (270)", L.thang("vaohop", 2026, 10)["ngay"]["2026-10-01"]["so"] == 270)
VAI.clear(); VAI.add("SX Vao Hop")
frappe.session.user = "qc2@x"
kiem("QC2 chỉ thấy 40 hộp của mình", L.thang("vaohop", 2026, 10)["ngay"]["2026-10-01"]["so"] == 40)
frappe.session.user = "qc1@x"

print("\n-- lịch Ghi sổ --")
VAI.clear(); VAI.add("SX Ghi So")
t = L.thang("ghiso", 2026, 10)
kiem("ô = số mẻ trộn (3 + 1,5); phiếu ngày đã huỷ không tính; dòng 0 mẻ không thành ô '0'",
     t["ngay"]["2026-10-01"]["so"] == 4.5 and "2026-10-02" not in t["ngay"], str(t["ngay"]))
c = L.chi_tiet("ghiso", "2026-10-01")
ten_khoi = [k["ten"] for k in c["khoi"]]
kiem("chi tiết: báo mẻ, báo cán, rang đỗ", ten_khoi == ["Báo mẻ trộn", "Báo cán", "Rang đỗ"], str(ten_khoi))
kiem("báo mẻ gộp theo bột, kèm kg", c["khoi"][0]["dong"] == [
    {"trai": "Bột bánh", "phai": 4.5, "phu": "513 kg"}], str(c["khoi"][0]["dong"]))
kiem("chips: chốt, kg, sự cố", c["chips"] == ["đã chốt Ghi sổ", "513 kg", "1 sự cố"], str(c["chips"]))
kiem("rang đỗ: kg + lô", c["khoi"][2]["dong"] == [{"trai": "Đỗ xanh", "phai": "500 kg", "phu": "lô R-011026"}])

print("\n-- lịch Nhập kho --")
VAI.clear(); VAI.add("SX Thu Kho")
t = L.thang("nhapkho", 2026, 10)
kiem("chỉ phiếu ĐÃ DUYỆT (nháp và đã huỷ không tính)",
     t["ngay"] == {"2026-10-01": {"so": 150, "phu": 2, "chot": 0}}, str(t["ngay"]))
c = L.chi_tiet("nhapkho", "2026-10-01")
kiem("chi tiết theo mã gộp hai phiếu", c["khoi"][0]["dong"][0] == {"trai": "Bánh sen", "phai": "130 Hộp"},
     str(c["khoi"][0]["dong"]))
kiem("… và liệt kê từng phiếu", [x["trai"] for x in c["khoi"][1]["dong"]] == ["PN1", "PN2"])

print("\n-- quyền --")
VAI.clear(); VAI.add("SX Ghi So")
kiem("Ghi sổ không xem lịch Ghi hộp", thu(lambda: L.thang("vaohop", 2026, 10))[1] is not None)
VAI.clear(); VAI.add("SX Thu Kho")
kiem("Thủ kho không xem lịch Ghi sổ", thu(lambda: L.chi_tiet("ghiso", "2026-10-01"))[1] is not None)
VAI.clear(); VAI.add("SX Quan Ly")
kiem("Quản lý xem được cả ba", all(thu(lambda l=l: L.thang(l, 2026, 10))[1] is None
                                   for l in ("vaohop", "ghiso", "nhapkho")))
kiem("loại lạ → chặn", thu(lambda: L.thang("xoa", 2026, 10))[1] is not None)
kiem("tháng lạ → chặn", thu(lambda: L.thang("vaohop", 2026, 13))[1] is not None)

print("\n-- dây nối --")
for v, c_ in (("vaohop", "lichvaohop"), ("ghiso", "lichghiso"), ("nhapkho", "lichnhapkho")):
    kiem(f"tab {v} có card {c_}", c_ in R.VIEW_CARDS[v])
shell = open("sx/public/sx/shell.js", encoding="utf-8").read()
kiem("shell.js biết đường dẫn ba card", all(f"{c_}: '/assets/sx/sx/cards/{c_}.js'" in shell
                                            for c_ in ("lichvaohop", "lichghiso", "lichnhapkho")))
comp = open("sx/public/sx/components/lichthang.js", encoding="utf-8").read()
for m in sorted(set(re.findall(r"sx\.api\.lich\.(\w+)", comp))):
    kiem(f"component gọi method có thật: {m}", callable(getattr(L, m, None)))

print("\n-- D117: lịch chốt ngày --")
VAI.clear(); VAI.add("SX Quan Ly")
t = L.thang("chot", 2026, 10)
o = t["ngay"]
kiem("ngày chốt đủ hai nửa → xanh cả hai", o.get("2026-10-01", {}).get("gs") == 2
     and o["2026-10-01"]["vh"] == 2, o.get("2026-10-01"))
kiem("có báo mẻ + bảng vào hộp mà chưa chốt → cam cả hai (phiếu HUỶ cùng ngày không che)",
     o.get("2026-10-02", {}).get("gs") == 1 and o["2026-10-02"]["vh"] == 1, o.get("2026-10-02"))
kiem("chốt Vào hộp, không báo mẻ nào → GS xám, VH xanh",
     o.get("2026-10-03", {}).get("gs") == 0 and o["2026-10-03"]["vh"] == 2, o.get("2026-10-03"))
kiem("ngày tháng khác không lẫn vào", "2026-09-30" not in o)
kiem("đếm đúng số ngày còn nửa chưa chốt", t["tong"] == 1, t["tong"])
ct = L.chi_tiet("chot", "2026-10-01")
kiem("xem nhanh có cả báo mẻ lẫn vào hộp", any(k["ten"] == "Báo mẻ trộn" for k in ct["khoi"])
     and any(k["ten"].startswith("Vào hộp") for k in ct["khoi"]), [k["ten"] for k in ct["khoi"]])
kiem("… kèm phiếu ngày để vẽ nút chốt", (ct["phieu"] or {}).get("name") == "N1"
     and ct["phieu"]["chot_ghiso"] == 1, ct["phieu"])
kiem("chip trạng thái chốt không lặp (nút chốt đã nói)", not any("chốt" in c for c in ct["chips"]),
     ct["chips"])
kiem("ngày không có phiếu → phieu None", L.chi_tiet("chot", "2026-10-20")["phieu"] is None)
ct = L.chi_tiet("chot", "2026-10-02")
kiem("ngày có phiếu huỷ + phiếu mới → nút chốt theo phiếu MỚI", ct["phieu"]["name"] == "N2", ct["phieu"])
VAI.clear(); VAI.add("SX Ghi So")
kiem("tổ Ghi sổ không mở lịch chốt (chốt là việc quản lý)", thu(lambda: L.thang("chot", 2026, 10))[1] is not None)
VAI.clear(); VAI.add("SX Quan Ly")
kiem("màn Quản lý có thẻ lịch chốt, bỏ thẻ chốt theo ô ngày",
     "lichchot" in R.VIEW_CARDS["quanly"] and "chotngay" not in R.VIEW_CARDS["quanly"])
kiem("shell.js biết đường dẫn lichchot", "lichchot: '/assets/sx/sx/cards/lichchot.js'" in shell)
lc = open("sx/public/sx/cards/lichchot.js", encoding="utf-8").read()
kiem("lịch chốt dùng lại đúng phần nút chốt của chotngay (có bước khai giá vốn)",
     "veChot" in lc and "export function veChot" in open("sx/public/sx/cards/chotngay.js",
                                                         encoding="utf-8").read())

print("\n-- D119: bố cục máy tính màn Quản lý --")
ql = open("sx/public/sx/views/quanly.js", encoding="utf-8").read()
cot = re.findall(r"const COT_(?:TRAI|PHAI) = \[([^\]]*)\]", ql)
ten_cot = set(re.findall(r"'(\w+)'", " ".join(cot)))
kiem("thẻ xếp vào hai cột đều là thẻ có thật trong shell.js",
     ten_cot and all(f"{c}:" in shell for c in ten_cot - {"chotngay"}) and "chotngay:" in shell, sorted(ten_cot))
kiem("mọi thẻ của màn Quản lý đều được gắn (thẻ ngoài hai cột trải rộng bên dưới)",
     "COT_TRAI.includes(c) ? trai : (COT_PHAI.includes(c) ? phai : rong)" in ql)
kiem("biểu đồ vẽ SAU khi khung đã vào trang (lỗi cũ: luôn trống)",
     ql.index("body.innerHTML = `") < ql.index("veCot(d.phieu"))
css = open("sx/public/sx/shell.css", encoding="utf-8").read()
kiem("thanh trái chỉ từ 1024px — điện thoại giữ thanh dưới",
     "@media (min-width: 1024px)" in css and ".sx-nav-brand { display: none; }" in css)
kiem("shell chuyển thanh ngày lên header theo bề ngang thật", "matchMedia('(min-width: 1024px)')" in shell)

print("LICH-OK" if not hong else f"LICH: {hong} HỎNG")
sys.exit(1 if hong else 0)
