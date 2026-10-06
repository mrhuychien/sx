"""D99 — vào hộp mã CHƯA có đơn giá: vẫn chốt được, nhưng ghi nợ để bù giá sau.

Vì sao phải có bài này: tiền ở đây là LƯƠNG của công nhân. Hỏng theo hai hướng
đều im lặng:

  · Mất nợ — chốt xong lương 0 đồng mà không dòng nợ nào được ghi, hoặc duyệt phiếu
    lương khi còn nợ (khoá cứng 0 đồng). Tới lúc cầm phiếu lương mới lộ.
  · Áp sai — điền giá vào dòng của ngày khác / mã khác, đè giá đã có, sửa phiếu
    lương ĐÃ DUYỆT, hoặc lấy giá từ bảng không áp dụng cho ngày đó (chốt lại ngày
    đó sẽ ra số khác).

Nạp sx/api/nogia.py, sx/utils.py (tra giá thật), sx/config/roles.py, controller
SX No Don Gia và SX Phieu Luong THẬT; frappe là giả.

Chạy: python3 scripts/test-nogia.py   (verify.sh gọi sẵn)
"""

import ast
import importlib.util
import json
import os
import re
import sys
import types
from datetime import date

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# ── thế giới giả ─────────────────────────────────────────────────────────
BANG_GIA = []      # [{name, hieu_luc_tu, gia: {(sp, cl): don_gia}}]
NO = []            # SX No Don Gia
PHIEU = {}         # SX Phieu Luong
BANG_VH = {}       # SX Bang Vao Hop
NGAY = {}          # SX Ngay San Xuat
SET_ROW = []       # set_value lên dòng bảng vào hộp
VAI = {"SX Quan Ly"}
ITEM = {"TP-A": "Bánh A", "TP-B": "Bánh B", "TP-C": "Bánh C", "TP-D": "Bánh D"}


class Loi(Exception):
    pass


class Doc(dict):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        dict.__setitem__(self, "_flags", types.SimpleNamespace(ignore_permissions=False))

    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        if k == "flags":
            return dict.__getitem__(self, "_flags")
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v

    def db_set(self, k, v=None, **kw):
        if isinstance(k, dict):
            self.update(k)
        else:
            self[k] = v


class NoDoc(Doc):
    def insert(self, **kw):
        self["name"] = f"NG-{len(NO) + 1:04d}"
        N.SXNoDonGia.validate(self)
        NO.append(self)
        return self

    def save(self):
        N.SXNoDonGia.validate(self)
        return self


class PhieuDoc(Doc):
    luu = 0

    def save(self):
        self["luu"] = (self.get("luu") or 0) + 1
        for r in self.chi_tiet:
            r.thanh_tien = float(r.don_gia or 0) * int(r.so_luong or 0)
        return self


def _khop(h, f):
    for k, v in (f or {}).items():
        hv = h.get(k)
        if isinstance(v, tuple):
            op, x = v
            if op == "<=" and not (hv <= x):
                return False
            if op == "<" and not (hv < x):
                return False
            if op == "!=" and hv == x:
                return False
            continue
        if str(hv) != str(v) if isinstance(v, date) or isinstance(hv, date) else hv != v:
            return False
    return True


def _get_all(dt, filters=None, fields=None, order_by=None, pluck=None, **k):
    if dt == "SX No Don Gia":
        ds = [h for h in NO if _khop(h, filters)]
    elif dt == "SX Bang Don Gia Item":
        b = next((x for x in BANG_GIA if x["name"] == filters["parent"]), None)
        ds = [Doc(san_pham=sp, cach_lam=cl or None, don_gia=g)
              for (sp, cl), g in (b["gia"].items() if b else [])]
    else:
        ds = []
    if pluck:
        return [h[pluck] for h in ds]
    return [Doc(h) for h in ds]


def _get_value(dt, f, field=None, order_by=None, **kw):
    if dt == "SX Bang Don Gia":
        ds = [b for b in BANG_GIA if _khop(b, {k: v for k, v in f.items() if k != "docstatus"})]
        ds.sort(key=lambda b: b["hieu_luc_tu"], reverse="desc" in (order_by or ""))
        return ds[0]["name"] if ds else None
    if dt == "Item":
        return ITEM.get(f)
    if dt == "SX Ngay San Xuat":
        return NGAY[f].get(field)
    if dt == "SX Phieu Luong":
        return None
    return None


def _set_value(dt, name, vals, v=None, **kw):
    vals = vals if isinstance(vals, dict) else {vals: v}
    if dt == "SX No Don Gia":
        next(x for x in NO if x["name"] == name).update(vals)
    elif dt == "SX Bang Vao Hop Item":
        SET_ROW.append((name, dict(vals)))
    elif dt == "SX Ngay San Xuat":
        NGAY[name].update(vals)


def _exists(dt, name=None):
    return {"SX Phieu Luong": PHIEU, "SX Bang Vao Hop": BANG_VH}.get(dt, {}).get(name) is not None


def _get_doc(x, n=None):
    if isinstance(x, dict):
        return NoDoc(x)
    if x == "SX No Don Gia":
        return next(h for h in NO if h["name"] == n)
    return {"SX Phieu Luong": PHIEU, "SX Bang Vao Hop": BANG_VH}[x][n]


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.msgprint = lambda *a, **k: None
frappe.session = types.SimpleNamespace(user="ql@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = _get_all
frappe.get_doc = _get_doc
frappe.get_cached_doc = lambda *a, **k: Doc()
frappe.db = types.SimpleNamespace(get_value=_get_value, set_value=_set_value, exists=_exists,
                                  get_single_value=lambda *a, **k: None)
frappe.__dict__["_"] = lambda s: s
frappe.utils = types.ModuleType("frappe.utils")
frappe.utils.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
frappe.utils.cint = lambda v: int(float(v or 0))
frappe.utils.getdate = lambda x=None: (x if isinstance(x, date) else
                                       date.fromisoformat(str(x)[:10]) if x else date(2026, 9, 28))
frappe.utils.nowdate = lambda: "2026-09-28"
frappe.utils.now_datetime = lambda: "2026-09-28 10:00:00"
frappe.utils.formatdate = str
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = frappe.utils
mdl = types.ModuleType("frappe.model"); mdl.__path__ = []
dm = types.ModuleType("frappe.model.document"); dm.Document = Doc
sys.modules["frappe.model"] = mdl
sys.modules["frappe.model.document"] = dm

for g in ("sx", "sx.api", "sx.config", "sx.sx", "sx.sx.doctype"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


U = nap("sx.utils", "sx/utils.py")
R = nap("sx.config.roles", "sx/config/roles.py")
G = nap("sx.api.nogia", "sx/api/nogia.py")
N = nap("sx.sx.doctype.sx_no_don_gia.sx_no_don_gia",
        "sx/sx/doctype/sx_no_don_gia/sx_no_don_gia.py")
L = nap("sx.sx.doctype.sx_phieu_luong.sx_phieu_luong",
        "sx/sx/doctype/sx_phieu_luong/sx_phieu_luong.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


def thu(fn):
    try:
        fn()
        return None
    except Loi as e:
        return str(e) or type(e).__name__


D20, D21 = date(2026, 9, 20), date(2026, 9, 21)


def dong_vh(i, nv, sp, sl, cl=None):
    return Doc(name=f"VH-{i}", nhan_vien=nv, san_pham=sp, so_hop=sl, cach_lam=cl,
               don_gia=0, thanh_tien=0)


def lam_sach():
    for x in (BANG_GIA, NO, SET_ROW):
        x.clear()
    PHIEU.clear(); BANG_VH.clear(); NGAY.clear()
    VAI.clear(); VAI.add("SX Quan Ly")
    # Bảng giá áp dụng từ 01/09: A có giá chung, C chỉ có giá "Máy", D giá chung.
    BANG_GIA.append({"name": "BG-09", "hieu_luc_tu": date(2026, 9, 1),
                     "gia": {("TP-A", ""): 1000.0, ("TP-C", "Máy"): 800.0,
                             ("TP-D", ""): 500.0}})


def dung_ngay(ten, ngay, dong):
    """Một ngày đã chốt vào hộp: bảng (đã tính giá như controller) + phiếu lương."""
    bang = U.don_gia_ap_dung(ngay)
    for r in dong:
        r.name = f"{ten}/{r.name}"
        g = U.tra_don_gia(bang, r.san_pham, r.cach_lam)
        r.don_gia = g or 0
        r.thanh_tien = r.don_gia * r.so_hop
    b = Doc(name=f"BVH-{ten}", dong=dong, tong_tien=sum(r.thanh_tien for r in dong))
    BANG_VH[b.name] = b
    ds = []
    for nv in sorted({r.nhan_vien for r in dong}):
        p = PHIEU.get(f"PL-{nv}") or PhieuDoc(name=f"PL-{nv}", docstatus=0, chi_tiet=[])
        PHIEU[p.name] = p
        for r in dong:
            if r.nhan_vien == nv:
                p.chi_tiet.append(Doc(ngay=ngay, san_pham=r.san_pham, cach_lam=r.cach_lam,
                                      so_luong=r.so_hop, don_gia=r.don_gia))
        ds.append({"phieu": p.name, "employee": nv, "ngay": str(ngay)})
    NGAY[ten] = {"ngay": ngay, "salary_products_json": json.dumps(ds), "tong_luong_sp": b.tong_tien}
    G.ghi_no_gia(Doc(name=ten, ngay=ngay), b)
    return b


# ═══ 1. Gom dòng thiếu giá ═══════════════════════════════════════════════
print("-- gom dòng thiếu giá: dùng đúng luật tra giá của bảng vào hộp --")
lam_sach()
bg = U.don_gia_ap_dung(D20)
thieu = G.gom_thieu_gia([
    dong_vh(1, "NV1", "TP-A", 10),            # có giá chung
    dong_vh(2, "NV1", "TP-B", 20),            # không có giá
    dong_vh(3, "NV2", "TP-B", 5),             # cùng mã, người khác → cộng
    dong_vh(4, "NV1", "TP-C", 7, "Tay"),      # C chỉ có giá Máy, không giá chung
    dong_vh(5, "NV2", "TP-C", 3, "Máy"),      # có giá
    dong_vh(6, "NV2", "TP-D", 4, "Tay"),      # rơi về giá chung → có giá
], bg)
kiem("chỉ đúng hai (mã, cách làm) thiếu giá",
     set(thieu) == {("TP-B", ""), ("TP-C", "Tay")}, str(sorted(thieu)))
kiem("cộng số hộp, đếm người KHÁC NHAU",
     (thieu[("TP-B", "")]["so_hop"], len(thieu[("TP-B", "")]["nguoi"])) == (25, 2))
kiem("mã có cách làm rơi về giá chung thì KHÔNG nợ", ("TP-D", "Tay") not in thieu)

# ═══ 2. Chốt ghi nợ ══════════════════════════════════════════════════════
print("\n-- chốt vào hộp: ghi nợ --")
lam_sach()
b20 = dung_ngay("NSX-20", D20, [dong_vh(1, "NV1", "TP-A", 10), dong_vh(2, "NV1", "TP-B", 20),
                                dong_vh(3, "NV2", "TP-B", 5), dong_vh(4, "NV2", "TP-C", 7, "Tay")])
kiem("mỗi (mã, cách làm) thiếu giá một dòng nợ", len(NO) == 2, str(len(NO)))
nb = next(x for x in NO if x.san_pham == "TP-B")
kiem("nợ trỏ đúng ngày, phiếu ngày, bảng vào hộp, bảng giá áp dụng",
     (nb.ngay, nb.ngay_sx, nb.bang_vao_hop, nb.bang_don_gia) == (D20, "NSX-20", "BVH-NSX-20", "BG-09"))
kiem("nợ Chờ giá, đúng số hộp và số người",
     (nb.trang_thai, nb.so_hop, nb.so_nguoi) == ("Chờ giá", 25, 2))
cb = G.canh_bao_no_gia("NSX-20")
kiem("cảnh báo sau chốt nói ĐÃ GHI NỢ và nêu tên mã",
     len(cb) == 1 and "SỔ NỢ ĐƠN GIÁ" in cb[0] and "Bánh B" in cb[0], cb[0] if cb else "")
dung_ngay("NSX-21", D21, [dong_vh(1, "NV1", "TP-B", 8)])
kiem("ngày khác chốt cùng mã → dòng nợ RIÊNG", len(NO) == 3)
lam_sach()
dung_ngay("NSX-20", D20, [dong_vh(1, "NV1", "TP-A", 10)])
kiem("đủ giá thì không ghi nợ, không cảnh báo", not NO and not G.canh_bao_no_gia("NSX-20"))

# ═══ 3. Sổ nợ + áp giá ═══════════════════════════════════════════════════
print("\n-- sổ nợ và áp giá --")
lam_sach()
dung_ngay("NSX-20", D20, [dong_vh(1, "NV1", "TP-A", 10), dong_vh(2, "NV1", "TP-B", 20),
                          dong_vh(3, "NV2", "TP-B", 5)])
dung_ngay("NSX-21", D21, [dong_vh(1, "NV1", "TP-B", 8)])
s = G.so_no_gia()
g = s["nhom"][0]
kiem("gom theo mã: một nhóm, hai ngày, 33 hộp",
     (len(s["nhom"]), len(g["dong"]), g["so_hop"]) == (1, 2, 33))
kiem("chưa khai giá → nói đúng bảng phải khai", not g["co_gia"] and g["bang"] == ["BG-09"])
loi = thu(lambda: G.ap_gia("TP-B"))
kiem("áp khi chưa có giá → báo lỗi, không im lặng", loi and "chưa khai giá" in loi, loi or "")
kiem("… và không đụng gì", all(x.trang_thai == "Chờ giá" for x in NO)
     and not any(p.get("luu") for p in PHIEU.values()))

# Bảng MỚI hiệu lực sau ngày sản xuất có giá: KHÔNG áp — chốt lại ngày đó sẽ tra
# bảng cũ, hai con số lệch nhau.
BANG_GIA.append({"name": "BG-10", "hieu_luc_tu": date(2026, 10, 1), "gia": {("TP-B", ""): 9999.0}})
kiem("giá ở bảng hiệu lực SAU ngày sản xuất không được tính",
     not G.so_no_gia()["nhom"][0]["co_gia"])
BANG_GIA.pop()

BANG_GIA[0]["gia"][("TP-B", "")] = 1500.0
g = G.so_no_gia()["nhom"][0]
kiem("khai giá xong → sổ báo áp được, ước đúng tiền",
     g["co_gia"] and g["tien"] == 33 * 1500.0, str(g["tien"]))
kq = G.ap_gia("TP-B")
kiem("áp cả hai ngày", kq["so_dong"] == 2 and kq["tien"] == 33 * 1500.0, str(kq))
pl1 = PHIEU["PL-NV1"]
gia_nv1 = sorted((str(r.ngay), r.san_pham, r.don_gia) for r in pl1.chi_tiet)
kiem("phiếu lương: dòng 0 đồng của TP-B được điền, dòng TP-A giữ nguyên",
     gia_nv1 == [("2026-09-20", "TP-A", 1000.0), ("2026-09-20", "TP-B", 1500.0),
                 ("2026-09-21", "TP-B", 1500.0)], str(gia_nv1))
kiem("phiếu lương được LƯU (controller tính lại tổng)", pl1.get("luu") and
     PHIEU["PL-NV2"].get("luu"))
kiem("bảng vào hộp đã chốt: dòng TP-B có giá, tổng tiền tính lại",
     ("NSX-20/VH-2", {"don_gia": 1500.0, "thanh_tien": 30000.0}) in SET_ROW
     and BANG_VH["BVH-NSX-20"].tong_tien == 10000 + 25 * 1500.0,
     str(BANG_VH["BVH-NSX-20"].tong_tien))
kiem("phiếu ngày: tổng lương SP khớp bảng", NGAY["NSX-20"]["tong_luong_sp"] == 47500.0)
kiem("không dòng bảng vào hộp nào của mã khác bị ghi",
     {n for n, _v in SET_ROW} == {"NSX-20/VH-2", "NSX-20/VH-3", "NSX-21/VH-1"}, str(SET_ROW))
kiem("nợ Đã cập nhật, ghi giá + tiền + người xử lý",
     all((x.trang_thai, x.don_gia, x.xu_ly_boi) == ("Đã cập nhật", 1500.0, "ql@x") for x in NO)
     and next(x for x in NO if x.ngay == D20).thanh_tien == 25 * 1500.0)
kiem("sổ trống sau khi áp", not G.so_no_gia()["nhom"])

print("\n-- giá lấy theo bảng áp dụng NGÀY SẢN XUẤT, không phải hôm nay --")
lam_sach()
dung_ngay("NSX-20", D20, [dong_vh(2, "NV1", "TP-B", 10)])
BANG_GIA[0]["gia"][("TP-B", "")] = 1500.0
# Bảng mới từ 25/09 (trước hôm nay 28/09) tăng giá — ngày 20/09 vẫn theo giá cũ.
BANG_GIA.append({"name": "BG-0925", "hieu_luc_tu": date(2026, 9, 25),
                 "gia": {("TP-B", ""): 2000.0}})
G.ap_gia("TP-B")
kiem("ngày 20/09 áp giá bảng BG-09 (1500), không phải bảng hiện hành",
     [r.don_gia for r in PHIEU["PL-NV1"].chi_tiet] == [1500.0]
     and NO[0].bang_don_gia == "BG-09", str([r.don_gia for r in PHIEU["PL-NV1"].chi_tiet]))

print("\n-- không đè giá đã có, không sửa phiếu đã duyệt --")
lam_sach()
dung_ngay("NSX-20", D20, [dong_vh(2, "NV1", "TP-B", 20)])
# Người làm lương đã tự sửa tay một dòng khác cùng mã (ngày khác) — không được đè.
PHIEU["PL-NV1"].chi_tiet.append(Doc(ngay=D21, san_pham="TP-B", cach_lam=None, so_luong=3,
                                    don_gia=777.0))
BANG_GIA[0]["gia"][("TP-B", "")] = 1500.0
G.ap_gia("TP-B")
kiem("dòng ngày khác (đã có giá) giữ nguyên",
     [r.don_gia for r in PHIEU["PL-NV1"].chi_tiet if r.ngay == D21] == [777.0])

lam_sach()
dung_ngay("NSX-20", D20, [dong_vh(2, "NV1", "TP-B", 20), dong_vh(3, "NV2", "TP-B", 5)])
PHIEU["PL-NV2"]["docstatus"] = 1
BANG_GIA[0]["gia"][("TP-B", "")] = 1500.0
loi = thu(lambda: G.ap_gia("TP-B"))
kiem("có phiếu lương đã duyệt → báo rõ phiếu nào", loi and "PL-NV2" in loi and "đã duyệt" in loi,
     loi or "")
kiem("… và KHÔNG áp nửa vời cho phiếu còn lại",
     not PHIEU["PL-NV1"].get("luu") and NO[0].trang_thai == "Chờ giá")

# ═══ 4. Cách làm ═════════════════════════════════════════════════════════
print("\n-- cách làm tách riêng --")
lam_sach()
dung_ngay("NSX-20", D20, [dong_vh(1, "NV1", "TP-C", 7, "Tay"), dong_vh(2, "NV1", "TP-B", 2)])
BANG_GIA[0]["gia"][("TP-C", "Tay")] = 600.0
loi = thu(lambda: G.ap_gia("TP-C"))
kiem("áp mã mà không nói cách làm → không đụng nợ của cách làm Tay", loi is not None)
kq = G.ap_gia("TP-C", "Tay")
kiem("áp đúng cách làm", kq["so_dong"] == 1 and
     [r.don_gia for r in PHIEU["PL-NV1"].chi_tiet if r.san_pham == "TP-C"] == [600.0])
kiem("nợ của mã khác vẫn mở", next(x for x in NO if x.san_pham == "TP-B").trang_thai == "Chờ giá")

# ═══ 5. Bỏ qua, huỷ chốt ═════════════════════════════════════════════════
print("\n-- bỏ qua / huỷ chốt --")
lam_sach()
dung_ngay("NSX-20", D20, [dong_vh(2, "NV1", "TP-B", 20), dong_vh(4, "NV1", "TP-C", 7, "Tay")])
nb, nc = NO
kiem("bỏ qua không lý do → chặn", "lý do" in (thu(lambda: G.bo_qua_no_gia(nb.name, " ")) or ""))
G.bo_qua_no_gia(nb.name, "hàng mẫu")
kiem("bỏ qua có lý do → Bỏ qua", (nb.trang_thai, nb.ly_do) == ("Bỏ qua", "hàng mẫu"))
kiem("bỏ qua lần hai → chặn", thu(lambda: G.bo_qua_no_gia(nb.name, "x")) is not None)
G.huy_no_gia("NSX-20")
kiem("huỷ chốt: nợ đang mở → Đã huỷ", nc.trang_thai == "Đã huỷ")
kiem("huỷ chốt: nợ đã xử lý giữ nguyên làm dấu vết", nb.trang_thai == "Bỏ qua")

# ═══ 6. Duyệt phiếu lương ════════════════════════════════════════════════
print("\n-- duyệt phiếu lương khi còn nợ --")
lam_sach()
dung_ngay("NSX-20", D20, [dong_vh(1, "NV1", "TP-A", 10), dong_vh(2, "NV1", "TP-B", 20)])
p = PHIEU["PL-NV1"]
loi = thu(lambda: L.SXPhieuLuong.before_submit(p))
kiem("còn dòng nợ đơn giá → KHÔNG duyệt được, nêu mã", loi and "TP-B" in loi, loi or "")
BANG_GIA[0]["gia"][("TP-B", "")] = 1500.0
G.ap_gia("TP-B")
kiem("áp giá xong → duyệt được", thu(lambda: L.SXPhieuLuong.before_submit(p)) is None)
lam_sach()
dung_ngay("NSX-20", D20, [dong_vh(2, "NV1", "TP-B", 20)])
G.bo_qua_no_gia(NO[0].name, "làm thử")
kiem("bỏ qua có lý do → duyệt được (0 đồng là quyết định có ghi lại)",
     thu(lambda: L.SXPhieuLuong.before_submit(PHIEU["PL-NV1"])) is None)

# ═══ 7. Quyền ════════════════════════════════════════════════════════════
print("\n-- quyền --")
for vai in ("SX Thu Kho", "SX Vao Hop", "SX Ghi So"):
    VAI.clear(); VAI.add(vai)
    loi = [thu(f) for f in (G.so_no_gia, lambda: G.ap_gia("TP-B"),
                            lambda: G.bo_qua_no_gia("NG-0001", "x"))]
    kiem(f"{vai} không xem / áp / bỏ qua được",
         all(e and "quyền" in e for e in loi), str(loi))
kiem("card nogia nằm ở màn Quản lý", "nogia" in R.VIEW_CARDS["quanly"])
kiem("card nogia chỉ mở cho Quản lý", R.CARD_ROLES.get("nogia") == [R.QUAN_LY])
shell = open("sx/public/sx/shell.js", encoding="utf-8").read()
kiem("shell.js biết đường dẫn card", "nogia: '/assets/sx/sx/cards/nogia.js'" in shell)
card = open("sx/public/sx/cards/nogia.js", encoding="utf-8").read()
for m in re.findall(r"sx\.api\.nogia\.(\w+)", card):
    kiem(f"card gọi method có thật: {m}", callable(getattr(G, m, None)))

# ═══ 8. Dây nối trong đồng bộ ngầm (D123 — thay chốt / huỷ chốt) ═════════════
print("\n-- dây nối trong sx/api/dongbo.py --")
src_db = open("sx/api/dongbo.py", encoding="utf-8").read()
cay = ast.parse(src_db)
ham = {f.name: f for f in cay.body if isinstance(f, ast.FunctionDef)}


def goi_trong(ten_ham, goi):
    return [n for n in ast.walk(ham[ten_ham]) if isinstance(n, ast.Call)
            and (getattr(n.func, "id", None) == goi or getattr(n.func, "attr", None) == goi)]


vh = ham["dong_bo_vaohop"]
thu_khoi = [n for n in ast.walk(vh) if isinstance(n, ast.Try)]
trong_try = any(getattr(getattr(n, "func", None), "id", None) == "_dong_bo_no_gia"
                for t_ in thu_khoi for s_ in t_.body for n in ast.walk(s_))
kiem("đồng bộ lương: nợ giá cùng savepoint (vỡ là hoàn tác cả nợ)", bool(trong_try))
seg = ast.get_source_segment(src_db, vh)
kiem("nợ giá đối chiếu SAU khi ghi lương",
     seg.index("_ghi_luong_khoan(") < seg.index("_dong_bo_no_gia("))
kiem("xoá ngày huỷ nợ giá", bool(goi_trong("go_het", "huy_no_gia")))
seg_no = ast.get_source_segment(src_db, ham["_dong_bo_no_gia"])
kiem("đối chiếu nợ KHÔNG huỷ-tạo lại mỗi lần lưu (giữ nợ còn thiếu)",
     "huy_no_gia" not in seg_no and "if (sp, cl) in dang:" in seg_no)

# ═══ 9. DocType ══════════════════════════════════════════════════════════
dt = json.load(open("sx/sx/doctype/sx_no_don_gia/sx_no_don_gia.json", encoding="utf-8"))
tt = next(f for f in dt["fields"] if f["fieldname"] == "trang_thai")["options"].split("\n")
kiem("trạng thái DocType khớp code", set(tt) == {G.CHO, *N.TRANG_THAI_DONG}, str(tt))

print('NOGIA-OK' if not hong else f'NOGIA: {hong} HỎNG')
sys.exit(1 if hong else 0)
