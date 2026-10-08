"""D115 — truy xuất nguồn gốc 2 chiều (sx/api/truyxuat.py).

Truy xuất hỏng theo hướng nguy hiểm nhất là IM LẶNG: màn hình vẫn ra một cái cây
trông đầy đủ, chỉ thiếu đúng nhánh / đúng khách cần gọi lúc thu hồi. Test này dựng
một chuỗi thật: đỗ NCC → rang (ủ) → tách vỏ (vỡ) → nghiền (bột nền) → bột bánh
→ 2 lô thành phẩm + 1 lô nhập tạm chưa BOM → bán cho 2 khách (một qua bundle, một
qua batch_no trên SLE, có trả lại), và kiểm:
  · tìm lô bằng (sản phẩm, HSD) / mã vạch / mã lô, HSD lệch thì gợi ý gần đúng;
  · ngược tới tận NCC + kết luận tiếp nhận, nước (không lô) không làm gãy cây;
  · vào hộp khớp theo ngày đúng cửa sổ, công nhật gộp, mã khác không lẫn vào;
  · QC Không đạt hiện ra theo NHÃN; bán / trả lại / xuất khác / tồn đúng dấu;
  · xuôi từ lô đỗ tới MỌI lô TP (kể cả lô trừ bù nợ BOM) và gộp khách.

Nạp sx/api/truyxuat.py + sx/config/roles.py THẬT; frappe là giả.
Chạy: python3 scripts/test-truyxuat.py   (verify.sh gọi sẵn)
"""

import datetime as dt
import importlib.util
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class Loi(Exception):
    pass


class _dict(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


D = _dict
NHOM = {"DAU-XANH": "NVL", "DUONG": "NVL", "NUOC": "NVL", "HOP": "Bao Bi",
        "DX-U": "BTP-Dau", "DX-V": "BTP-Dau", "BOT-NEN": "BTP-Bot", "BOT-BANH": "BTP-Banh",
        "TP-SEN": "TP", "TP-KHAC": "TP"}
BANG = {
    "Item Barcode": [D(barcode="8930000000017", parent="TP-SEN")],
    "Item": [D(name=k) for k in NHOM],
    "Batch": [
        D(name="DX-NCC1", item="DAU-XANH", item_name="Đỗ xanh", expiry_date="2027-09-01", batch_qty=0, creation=1),
        D(name="DG-NCC", item="DUONG", item_name="Đường", batch_qty=0, creation=2),
        D(name="R-021026-U", item="DX-U", item_name="Đỗ ủ", creation=3),
        D(name="R-021026-V", item="DX-V", item_name="Đỗ vỡ", creation=4),
        D(name="R-021026", item="BOT-NEN", item_name="Bột nền", creation=5),
        D(name="BB-031026", item="BOT-BANH", item_name="Bột bánh", custom_ngay_sx="SXN-3", creation=6),
        D(name="SEN-061026", item="TP-SEN", item_name="Bánh sen", manufacturing_date="2026-10-06",
          expiry_date="2027-04-04", batch_qty=255, stock_uom="Hộp", creation=7),
        D(name="SEN-071026", item="TP-SEN", item_name="Bánh sen", manufacturing_date="2026-10-07",
          expiry_date="2027-04-05", batch_qty=0, creation=8),
        D(name="NB-1", item="TP-KHAC", item_name="Bánh khác", manufacturing_date="2026-10-08",
          expiry_date="2027-04-06", creation=9),
    ],
    "Stock Entry Detail": [
        # rang: đỗ NCC → ủ
        D(parent="SE-R", item_code="DAU-XANH", batch_no="DX-NCC1", qty=100, is_finished_item=0, docstatus=1, s_warehouse="X"),
        D(parent="SE-R", item_code="DX-U", batch_no="R-021026-U", qty=120, is_finished_item=1, docstatus=1, t_warehouse="X"),
        # tách vỏ
        D(parent="SE-T", item_code="DX-U", batch_no="R-021026-U", qty=120, is_finished_item=0, docstatus=1, s_warehouse="X"),
        D(parent="SE-T", item_code="DX-V", batch_no="R-021026-V", qty=90, is_finished_item=1, docstatus=1, t_warehouse="X"),
        # nghiền
        D(parent="SE-N", item_code="DX-V", batch_no="R-021026-V", qty=90, is_finished_item=0, docstatus=1, s_warehouse="X"),
        D(parent="SE-N", item_code="BOT-NEN", batch_no="R-021026", qty=88, is_finished_item=1, docstatus=1, t_warehouse="B"),
        # bột bánh: bột nền (2 dòng tách FIFO cùng lô → phải gộp) + đường + nước không lô
        D(parent="SE-BB", item_code="BOT-NEN", batch_no="R-021026", qty=30, is_finished_item=0, docstatus=1, s_warehouse="B"),
        D(parent="SE-BB", item_code="BOT-NEN", batch_no="R-021026", qty=20, is_finished_item=0, docstatus=1, s_warehouse="B"),
        D(parent="SE-BB", item_code="DUONG", batch_no="DG-NCC", qty=25, is_finished_item=0, docstatus=1, s_warehouse="N"),
        D(parent="SE-BB", item_code="NUOC", batch_no=None, qty=10, is_finished_item=0, docstatus=1, s_warehouse="N"),
        D(parent="SE-BB", item_code="BOT-BANH", batch_no="BB-031026", qty=80, is_finished_item=1, docstatus=1, t_warehouse="B"),
        # phế phẩm: dòng VÀO kho, không phải thành phẩm — không phải nguyên liệu
        D(parent="SE-BB", item_code="VO-DAU", batch_no="VO-1", qty=3, is_finished_item=0, docstatus=1, t_warehouse="B"),
        # phiếu HUỶ dùng cùng lô — không được tính
        D(parent="SE-HUYBO", item_code="BOT-NEN", batch_no="R-021026", qty=7, is_finished_item=0, docstatus=2, s_warehouse="B"),
        D(parent="SE-HUYBO", item_code="BOT-BANH", batch_no="BB-HUY", qty=7, is_finished_item=1, docstatus=2, t_warehouse="B"),
        # chuyển kho (không có thành phẩm) — xuôi phải bỏ qua
        D(parent="SE-CK", item_code="DAU-XANH", batch_no="DX-NCC1", qty=50, is_finished_item=0, docstatus=1, s_warehouse="N", t_warehouse="X"),
        # nhập kho TP
        D(parent="SE-TP", item_code="BOT-BANH", batch_no="BB-031026", qty=40, is_finished_item=0, docstatus=1, s_warehouse="B"),
        D(parent="SE-TP", item_code="HOP", batch_no=None, qty=400, is_finished_item=0, docstatus=1, s_warehouse="N"),
        D(parent="SE-TP", item_code="TP-SEN", batch_no="SEN-061026", qty=400, is_finished_item=1, docstatus=1, t_warehouse="TP"),
        D(parent="SE-TP2", item_code="BOT-BANH", batch_no="BB-031026", qty=5, is_finished_item=0, docstatus=1, s_warehouse="B"),
        D(parent="SE-TP2", item_code="TP-SEN", batch_no="SEN-071026", qty=50, is_finished_item=1, docstatus=1, t_warehouse="TP"),
        # nợ BOM: nhập thẳng + trừ bù không có dòng thành phẩm
        D(parent="SE-NB", item_code="TP-KHAC", batch_no="NB-1", qty=20, is_finished_item=0, docstatus=1, t_warehouse="TP"),
        D(parent="SE-BU", item_code="BOT-BANH", batch_no="BB-031026", qty=3, is_finished_item=0, docstatus=1, s_warehouse="B"),
    ],
    "SX No BOM": [D(name="NOBOM-1", batch="NB-1", item="TP-KHAC", so_luong=20, se_bu="SE-BU",
                    trang_thai="Đã hạch toán")],
    "SX Xuat Dau": [D(name="SXXD-1", lo_rang="R-021026", docstatus=1, loai_dau="DAU-XANH",
                      ngay_rang="2026-10-02", dau_kg=100)],
    "SX Ngay San Xuat": [D(name="SXN-1", ngay="2026-10-01", docstatus=1),
                         D(name="SXN-3", ngay="2026-10-03", docstatus=1),
                         D(name="SXN-5", ngay="2026-10-05", docstatus=0),
                         D(name="SXN-5H", ngay="2026-10-05", docstatus=2)],
    "SX Bang Vao Hop": [D(name="VH-1", ngay_sx="SXN-1", docstatus=1),
                        D(name="VH-5", ngay_sx="SXN-5", docstatus=0),
                        D(name="VH-5H", ngay_sx="SXN-5H", docstatus=2),
                        D(name="VH-5C", ngay_sx="SXN-5", docstatus=2)],
    "SX Bang Vao Hop Item": [
        D(parent="VH-5C", parenttype="SX Bang Vao Hop", ten_nhan_vien="Lan", san_pham="TP-SEN", so_hop=777),
        D(parent="VH-1", parenttype="SX Bang Vao Hop", ten_nhan_vien="Lan", san_pham="TP-SEN", so_hop=999),
        D(parent="VH-5", parenttype="SX Bang Vao Hop", ten_nhan_vien="Lan", san_pham="TP-SEN", so_hop=200),
        D(parent="VH-5", parenttype="SX Bang Vao Hop", ten_nhan_vien="Lan", san_pham="TP-SEN", so_hop=100),
        D(parent="VH-5", parenttype="SX Bang Vao Hop", cong_nhat=1, ten_nhan_vien=None, san_pham="TP-SEN", so_hop=50),
        D(parent="VH-5", parenttype="SX Bang Vao Hop", ten_nhan_vien="Hùng", san_pham="TP-KHAC", so_hop=100),
    ],
    "SX Phieu Nhap TP": [D(name="PN-2", ngay="2026-10-06", docstatus=1, nguoi_duyet="thukho@x",
                           nguoi_lap="qc@x", kho_dich="TP", duyet_luc="2026-10-06 16:00:00",
                           ds_se='[{"dt": "Work Order", "name": "WO-1"}, {"dt": "Stock Entry", "name": "SE-TP"}]')],
    "SX QC Round": [
        D(name="QC-5", ngay="2026-10-05", docstatus=1, luot="Đầu sáng", a1_ve_sinh="Không đạt",
          b2_kin="Đạt", reviewed_by="iso@x", started_at=1),
        D(name="QC-3", ngay="2026-10-03", docstatus=0, luot="Trưa", a1_ve_sinh="Đạt", started_at=1),
        D(name="QC-H", ngay="2026-10-05", docstatus=2, luot="Trưa", a1_ve_sinh="Không đạt", started_at=2),
    ],
    "SX Su Co": [D(name="SC-1", ngay="2026-10-03", muc_do="Nhẹ", mo_ta="Máy trộn kêu", trang_thai="Đóng"),
                 D(name="SC-9", ngay="2026-09-01", lo_anh_huong="DG-NCC", nguon="Tiếp nhận NL",
                   muc_do="Nặng", mo_ta="Đường ẩm")],
    "SX QC Luu Mau": [
        D(name="LM-1", san_pham="TP-SEN", lo="HSD 04/04/27", ngay_lay="2026-09-01"),
        D(name="LM-2", san_pham="TP-SEN", lo="", ngay_lay="2026-10-05"),
        D(name="LM-3", san_pham="TP-SEN", lo="", ngay_lay="2026-09-20"),
        D(name="LM-4", san_pham="TP-KHAC", lo="SEN-061026", ngay_lay="2026-10-05"),
    ],
    "Purchase Invoice Item": [
        D(parent="PI-1", item_code="DAU-XANH", batch_no="DX-NCC0", custom_ncc_lo="AP-0901",
          custom_ket_luan="Cách ly"),
        D(parent="PI-1", item_code="DAU-XANH", batch_no="DX-NCC1", custom_ncc_lo="AP-0925",
          custom_ket_luan="Đạt", custom_coa_vi_sinh="Có"),
        D(parent="PI-2", item_code="DUONG", batch_no=None, custom_ncc_lo="BH-77",
          custom_ket_luan="Không đạt"),
    ],
}
DOC = {("Purchase Invoice", "PI-1"): D(supplier="NCC-AP", supplier_name="NCC An Phát"),
       ("Purchase Invoice", "PI-2"): D(supplier="NCC-BH", supplier_name="Đường Biên Hoà"),
       ("Delivery Note", "DN-1"): D(customer="KH-HA", customer_name="Đại lý Hà"),
       ("Delivery Note", "DN-2"): D(customer="KH-HA", customer_name="Đại lý Hà"),
       ("Delivery Note", "DN-3"): D(customer="KH-HA", customer_name="Đại lý Hà"),
       ("Sales Invoice", "SI-1"): D(customer="KH-B", customer_name="Siêu thị B"),
       ("Stock Entry", "SE-HUY"): D(purpose="Material Issue")}
# (voucher_type, voucher_no, ngày, kho, actual_qty, batch_no trên SLE, qty trong bundle)
SLE = [
    ("Purchase Invoice", "PI-1", "2026-09-25", "N", 500, "DX-NCC1", None),
    ("Purchase Invoice", "PI-2", "2026-09-26", "N", 200, None, 200),        # qua bundle
    ("Purchase Invoice", "PI-2", "2026-09-26", "N", 999, None, None),       # bundle không chứa lô
    ("Stock Entry", "SE-TP", "2026-10-06", "TP", 400, "SEN-061026", None),
    ("Delivery Note", "DN-1", "2026-10-07", "TP", -100, "SEN-061026", None),
    ("Sales Invoice", "SI-1", "2026-10-08", "TP", -80, None, -50),          # bundle nhiều lô
    ("Delivery Note", "DN-2", "2026-10-09", "TP", 10, "SEN-061026", None),  # trả lại
    ("Stock Entry", "SE-HUY", "2026-10-09", "TP", -5, "SEN-061026", None),
    ("Stock Entry", "SE-TP2", "2026-10-07", "TP", 50, "SEN-071026", None),
    ("Delivery Note", "DN-3", "2026-10-08", "TP", -30, "SEN-071026", None),
]
SLE_LO = {"SI-1": "SEN-061026", "PI-2": "DG-NCC"}
VAI = {"SX Quan Ly"}


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, y = v
            if op == "in" and x not in y:
                return False
            if op == "is" and y == "set" and not x:
                return False
            if op == "like" and str(y).strip("%") not in str(x or ""):
                return False
            if op == "between" and not (x and y[0] <= str(x) <= y[1]):
                return False
            if op == "<" and not (x or 0) < y:
                return False
        elif x != v:
            return False
    return True


def get_all(d, filters=None, fields=None, pluck=None, limit=None, or_filters=None, **k):
    ra = [D(h) for h in BANG.get(d, []) if _khop(h, filters)]
    if limit:
        ra = ra[:limit]
    return [h.get(pluck) for h in ra] if pluck else ra


def get_value(d, f, field=None, as_dict=False, **k):
    if isinstance(f, dict):
        h = next(iter(get_all(d, f)), None)
    elif (d, f) in DOC:
        h = DOC[(d, f)]
    else:
        h = next((x for x in BANG.get(d, []) if x.get("name") == f), None)
    if not h:
        return None
    if isinstance(field, (list, tuple)):
        return D({x: h.get(x) for x in field}) if as_dict else tuple(h.get(x) for x in field)
    return h.get(field)


def sql(q, args=None, as_dict=False):
    if "Stock Ledger Entry" in q:
        b = args["b"]
        ra = []
        for i, (vt, vn, ng, kho, aq, bn, qlo) in enumerate(SLE):
            if bn == b or (qlo is not None and SLE_LO.get(vn) == b):
                ra.append(D(voucher_type=vt, voucher_no=vn, posting_date=ng, warehouse=kho,
                            actual_qty=aq, batch_no=bn, qty_lo=qlo if SLE_LO.get(vn) == b else None,
                            creation=i))
        return ra
    if "max(p.ngay)" in q:
        item, den, ten = args
        ds = [p["ngay"] for p in TRUOC if p["item"] == item and p["ngay"] <= str(den) and p["name"] != ten]
        return [(max(ds) if ds else None,)]
    raise AssertionError(q)


TRUOC = [{"name": "PN-1", "item": "TP-SEN", "ngay": "2026-10-04"},
         {"name": "PN-2", "item": "TP-SEN", "ngay": "2026-10-06"}]


class Meta:
    def get_label(self, f):
        return {"a1_ve_sinh": "Vệ sinh nhà xưởng"}.get(f)


frappe = types.ModuleType("frappe")
frappe._dict = _dict
frappe.throw = lambda m, e=None, **k: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.session = types.SimpleNamespace(user="ql@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_meta = lambda d: Meta()
frappe.get_cached_value = lambda d, n, f=None: NHOM.get(n) if f == "custom_sx_nhom" else None
frappe.db = types.SimpleNamespace(
    get_value=get_value, sql=sql,
    exists=lambda d, n=None: any(x.get("name") == n for x in BANG.get(d, [])))
frappe.__dict__["_"] = lambda s: s


def _gd(x=None):
    return x if isinstance(x, dt.date) else dt.date.fromisoformat(str(x)[:10])


fu = types.ModuleType("frappe.utils")
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.cint = lambda v: int(float(v or 0))
fu.getdate = _gd
fu.add_days = lambda d, n: _gd(d) + dt.timedelta(days=n)
fu.get_datetime = lambda x=None: x if isinstance(x, dt.datetime) else dt.datetime.fromisoformat(str(x))
fu.now_datetime = lambda: dt.datetime(2026, 10, 8, 9, 30)
fu.nowdate = lambda: "2026-10-08"
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.api", "sx.config"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m
ut = types.ModuleType("sx.utils")
ut.items_tp = lambda fields=None, **k: [D(name=i, item_name=i) for i, n in NHOM.items() if n == "TP"]
ut.nho = lambda ten: {}   # D120: bộ nhớ request — test giả không nhớ
ut.nap_bom = lambda items: {i: ut.get_bom_active(i) for i in (items or [])} if hasattr(ut, "get_bom_active") else {}
ut.ton_bin = lambda items, kho: {}
ut.la_lo_hsd = lambda b: "-HSD" in str(b or "")      # W05 (D131): lô TP theo HSD
sys.modules["sx.utils"] = ut
po = types.ModuleType("sx.api.portal")
po._ma_quet = lambda nv: {"nv": {}, "sp": {"8930000000017": "TP-SEN"}}
sys.modules["sx.api.portal"] = po


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


nap("sx.config.roles", "sx/config/roles.py")
T = nap("sx.api.truyxuat", "sx/api/truyxuat.py")

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
        return None, e


def tim(ds, **k):
    return next((x for x in ds if all(x.get(a) == b for a, b in k.items())), None)


def phang(ds, ra=None):
    ra = [] if ra is None else ra
    for x in ds or []:
        ra.append(x)
        phang(x.get("con"), ra)
    return ra


print("-- tìm lô --")
lo = lambda r: [x["batch"] for x in r["lo"]]
r = T.tim_lo(item="TP-SEN", hsd="2027-04-04")
kiem("sản phẩm + HSD đúng → đúng một lô", lo(r) == ["SEN-061026"] and not r["gan_dung"], lo(r))
r = T.tim_lo(item="TP-SEN", hsd="2027-04-10")
kiem("HSD lệch → gợi ý lô HSD gần, gắn cờ gần đúng", r["gan_dung"]
     and set(lo(r)) == {"SEN-061026", "SEN-071026"}, lo(r))
r = T.tim_lo(item="TP-SEN", hsd="2028-01-01")
kiem("HSD xa hẳn → rỗng, không bịa", lo(r) == [] and r["gan_dung"])
r = T.tim_lo(q="8930000000017", hsd="2027-04-05")
kiem("quét mã vạch + HSD → lô của đúng sản phẩm", lo(r) == ["SEN-071026"], lo(r))
r = T.tim_lo(q="08930000000017", hsd="2027-04-05")
kiem("mã vạch thừa số 0 đầu (UPC-A) vẫn ra", lo(r) == ["SEN-071026"], lo(r))
r = T.tim_lo(q="SEN-061026")
kiem("gõ đúng mã lô", lo(r) == ["SEN-061026"])
r = T.tim_lo(q="R-0210")
kiem("gõ một phần mã lô → các lô khớp", set(lo(r)) == {"R-021026", "R-021026-U", "R-021026-V"}, lo(r))
r = T.tim_lo(hsd="2027-09-01")
kiem("chỉ HSD → chỉ tìm trong thành phẩm (lô đỗ NCC trùng HSD không lẫn vào)", lo(r) == [], lo(r))
_, e = thu(lambda: T.tim_lo())
kiem("không nhập gì → báo cần nhập", e is not None)
VAI.clear(); VAI.add("SX Vao Hop")
_, e = thu(lambda: T.lo("SEN-061026"))
kiem("không phải quản lý → bị chặn", isinstance(e, frappe.PermissionError), type(e).__name__)
VAI.clear(); VAI.add("SX Quan Ly")

print("\n-- một lô thành phẩm: ngược --")
d = T.lo("SEN-061026")
kiem("thông tin lô: HSD / NSX", d["lo"]["hsd"] == "2027-04-04" and d["lo"]["nsx"] == "2026-10-06")
kiem("phiếu nhập kho tìm qua ds_se", (d["nhap_kho"] or {}).get("phieu") == "PN-2", d["nhap_kho"])
cay = phang(d["nguon"])
bb = tim(d["nguon"], batch="BB-031026")
kiem("tầng 1: bột bánh + hộp (bao bì không lô)", bb and tim(d["nguon"], item="HOP", khong_lo=True))
kiem("bột bánh mang ngày làm thật (custom_ngay_sx)", bb and bb["ngay_sx"] == "2026-10-03")
bn = [x for x in bb["con"] if x["batch"] == "R-021026"]
kiem("hai dòng FIFO cùng lô được GỘP (30+20=50)", len(bn) == 1 and bn[0]["so"] == 50, bn)
kiem("bột nền mang ngày rang + loại đỗ", bn and bn[0]["rang"]["ngay"] == "2026-10-02")
dx = tim(cay, batch="DX-NCC1")
kiem("đi hết bột nền → vỡ → ủ → lô đỗ NCC", dx is not None, [x["batch"] for x in cay])
kiem("lô đỗ: nhà cung cấp + kết luận tiếp nhận + lô NCC",
     dx and dx["ncc"]["ten_ncc"] == "NCC An Phát" and dx["ncc"]["ket_luan"] == "Đạt"
     and dx["ncc"]["lo_ncc"] == "AP-0925", dx and dx["ncc"])
dg = tim(cay, batch="DG-NCC")
kiem("đường mua qua bundle vẫn ra NCC; dòng HĐ không ghi lô → khớp theo mã hàng",
     dg and dg["ncc"]["ten_ncc"] == "Đường Biên Hoà" and dg["ncc"]["ket_luan"] == "Không đạt",
     dg and dg["ncc"])
kiem("nước không lô không làm gãy cây", tim(cay, item="NUOC", khong_lo=True) is not None)
kiem("phiếu HUỶ không lọt vào cây", tim(cay, batch="BB-HUY") is None)
kiem("phế phẩm (dòng vào kho của phiếu) không bị coi là nguyên liệu", tim(cay, batch="VO-1") is None)

print("\n-- quá trình --")
ng = {x["ngay"]: x for x in d["qua_trinh"]}
kiem("có ngày rang, ngày làm bột, ngày vào hộp, ngày nhập kho",
     {"2026-10-02", "2026-10-03", "2026-10-05", "2026-10-06"} <= set(ng), sorted(ng))
kiem("ngày ngoài cửa sổ vào hộp (01/10) không lẫn vào", "2026-10-01" not in ng)
vh = {x["ten"]: x["so_hop"] for x in ng["2026-10-05"]["vao_hop"]}
kiem("vào hộp gộp theo người, công nhật riêng, mã khác không lẫn",
     vh == {"Lan": 300, "Công nhật": 50}, vh)
kiem("bảng của phiếu ngày đã huỷ không tính", sum(vh.values()) == 350)
qc5 = ng["2026-10-05"]["qc"]
kiem("QC Không đạt hiện theo NHÃN, lượt đã huỷ bỏ qua",
     len(qc5) == 1 and qc5[0]["khong_dat"] == ["Vệ sinh nhà xưởng"] and qc5[0]["duyet"], qc5)
kiem("QC ngày làm bột hiện ra, đạt hết", ng["2026-10-03"]["qc"][0]["khong_dat"] == [])
kiem("sự cố ngày làm bột", [s["name"] for s in ng["2026-10-03"]["su_co"]] == ["SC-1"])
kiem("ghi chú nói rõ vào hộp khớp THEO NGÀY + cửa sổ",
     any("04/10/2026" in g and "06/10/2026" in g for g in d["ghi_chu"]), d["ghi_chu"])

print("\n-- xuôi: bán cho ai --")
b = d["ban"]
kh = {x["ten_khach"]: x["so"] for x in d["khach"]}
kiem("đã bán = 100 + 50 − 10 trả lại", b["da_ban"] == 140, b["da_ban"])
kiem("hoá đơn bán qua bundle lấy ĐÚNG phần của lô (50, không phải 80)",
     tim(b["ban"], chung_tu="SI-1")["so"] == 50)
kiem("trả lại gắn cờ", tim(b["ban"], chung_tu="DN-2")["tra_lai"])
kiem("khách gộp: Hà 90, Siêu thị B 50", kh == {"Đại lý Hà": 90, "Siêu thị B": 50}, kh)
kiem("xuất khác (huỷ hàng) tách riêng", [(x["chung_tu"], x["so"], x["muc_dich"]) for x in b["khac"]]
     == [("SE-HUY", 5, "Material Issue")], b["khac"])
kiem("tồn theo kho = 400 − 100 − 50 + 10 − 5", b["ton"] == [{"kho": "TP", "so": 255}], b["ton"])
kiem("số nhập = 400 (trả lại không tính là nhập)", b["nhap"] == 400, b["nhap"])
kiem("mẫu lưu: khớp theo HSD ghi tay + theo ngày; mã khác / ngày khác không lẫn",
     sorted(m["name"] for m in d["luu_mau"]) == ["LM-1", "LM-2"], [m["name"] for m in d["luu_mau"]])

print("\n-- xuôi từ lô đỗ NCC (thu hồi) --")
d = T.lo("DX-NCC1")
kiem("lô NCC: hiện nhà cung cấp", d["ncc"] and d["ncc"]["ten_ncc"] == "NCC An Phát")
x = phang(d["xuoi"])
tp = sorted(n["batch"] for n in x if n.get("la_tp"))
kiem("tới MỌI lô TP làm từ nó, kể cả lô trừ bù nợ BOM", tp == ["NB-1", "SEN-061026", "SEN-071026"], tp)
kiem("lô trừ bù gắn cờ", tim(x, batch="NB-1")["bu"])
kiem("chuyển kho (không có thành phẩm) không đẻ nhánh", all(n.get("se") != "SE-CK" for n in x))
kiem("phiếu HUỶ không đẻ nhánh", tim(x, batch="BB-HUY") is None)
kh = {k["ten_khach"]: k["so"] for k in d["khach"]}
kiem("khách gộp qua mọi lô: Hà 90+30, Siêu thị B 50",
     kh == {"Đại lý Hà": 120, "Siêu thị B": 50}, kh)
ha = tim(d["khach"], ten_khach="Đại lý Hà")
kiem("khách kèm lô TP đã nhận — nói bằng HSD, không bằng mã lô (W05)",
     ha["lo"] == ["HSD 04/04/2027", "HSD 05/04/2027"], ha["lo"])

print("\n-- sự cố theo lô + lô nhập tạm chưa BOM --")
d = T.lo("DG-NCC")
kiem("sự cố tiếp nhận ghi theo lô hiện ra", [s["name"] for s in d["su_co_lo"]] == ["SC-9"])
d = T.lo("NB-1")
kiem("lô nhập tạm: ghi chú nói rõ không truy đúng lô bột",
     any("CHƯA có BOM" in g for g in d["ghi_chu"]), d["ghi_chu"])
kiem("… nhưng vẫn cho thấy lô bột đã trừ bù", tim(d["nguon"], batch="BB-031026") is not None)

print("\n-- vòng lặp chứng từ không treo --")
BANG["Stock Entry Detail"] += [
    D(parent="SE-VONG", item_code="BOT-BANH", batch_no="BB-031026", qty=1, is_finished_item=0, docstatus=1, s_warehouse="B"),
    D(parent="SE-VONG", item_code="BOT-NEN", batch_no="R-021026", qty=1, is_finished_item=1, docstatus=1, t_warehouse="B")]
d = T.lo("SEN-061026")


def lap(ds, duong=()):
    """Có đường gốc→lá nào đi qua cùng một lô hai lần không."""
    for x in ds or []:
        b = x.get("batch")
        if b and b in duong and not (x.get("lap") and not x.get("con") and not x.get("ban")):
            return True
        if lap(x.get("con"), duong + (b,)):
            return True
    return False


kiem("A→B→A dừng lại, không lô nào lặp trên một nhánh (ngược)", not lap(d["nguon"], ("SEN-061026",)))
d = T.lo("DX-NCC1")
kiem("… cả chiều xuôi", not lap(d["xuoi"], ("DX-NCC1",)))
kiem("chỗ vòng được ĐÁNH DẤU (màn hình nói 'đã có ở trên')", any(x.get("lap") for x in phang(d["xuoi"])))

print("\n-- W06: bảng cân bằng lô --")
d = T.lo("SEN-061026")
cb = d["can_bang"]
kiem("sản xuất 400 = bán 140 (100 + 50 − 10 trả lại) + xuất khác 5 + tồn 255",
     (cb["san_xuat"], cb["da_ban"], cb["xuat_khac"], cb["ton_so_sach"], cb["tim_thay"])
     == (400, 140, 5, 255, 400), cb)
kiem("theo sổ sách → 100%, đạt", cb["pt"] == 100.0 and cb["dat"])
so_cai = T._so_cai("SEN-061026")
T._mau_cua_lo = lambda b: 3.0
c2 = T._can_bang("SEN-061026", so_cai, ton_thuc_te=250)
kiem("đếm thực tế 250 + mẫu lưu 3 → xác định 398 / 400 = 99,5% (đạt ≥ 98)",
     (c2["tim_thay"], c2["pt"], c2["dat"]) == (398, 99.5, True), c2)
c3 = T._can_bang("SEN-061026", so_cai, ton_thuc_te=200)
kiem("đếm thực tế 200 → 348 / 400 = 87% → KHÔNG đạt, chênh 52",
     (c3["pt"], c3["dat"], c3["chenh_lech"]) == (87.0, False, 52), c3)
c4 = T._can_bang("SEN-061026", so_cai)
kiem("không đếm thì mẫu lưu KHÔNG cộng thêm (đã nằm trong tồn sổ)", c4["tim_thay"] == 400)
BANG["Stock Entry"] = [D(name="SE-CK2", purpose="Material Transfer")]
c5 = T._can_bang("X", [{"loai": "Stock Entry", "chung_tu": "SE-TP", "so": 100, "kho": "TP"},
                       {"loai": "Stock Entry", "chung_tu": "SE-CK2", "so": -40, "kho": "TP"},
                       {"loai": "Stock Entry", "chung_tu": "SE-CK2", "so": 40, "kho": "CH"}])
kiem("chuyển kho không tính là sản xuất hay xuất khác", (c5["san_xuat"], c5["xuat_khac"]) == (100, 0), c5)
T._mau_cua_lo = lambda b: 0.0

print("\n-- W06: diễn tập truy xuất --")
import datetime as _dtt  # noqa: E402
import json  # noqa: E402
DTAP = {}


class DtDoc(D):
    def insert(self, **k):
        self["name"] = f"DT-{len(DTAP) + 1}"
        DTAP[self["name"]] = self
        return self

    def save(self, **k):
        DTAP[self["name"]] = self

    def delete(self, **k):
        DTAP.pop(self["name"], None)


_ga = frappe.get_all
frappe.get_all = lambda d, filters=None, **k: (
    [D(x) for x in DTAP.values() if all(
        (bool(x.get(a)) == (b[1] == "set")) if isinstance(b, tuple) and b[0] == "is" else x.get(a) == b
        for a, b in (filters or {}).items())] if d == "SX Dien Tap Truy Xuat" else _ga(d, filters, **k))
frappe.get_doc = lambda d, n=None: DtDoc(d) if isinstance(d, dict) else DTAP[n]
GIO = [_dtt.datetime(2026, 10, 8, 9, 0)]
fu.now_datetime = lambda: GIO[0]
T.now_datetime = lambda: GIO[0]
frappe.render_template = lambda t, ctx: f"{t}|{ctx['d']['name']}|{ctx['kq']['can_bang']['pt']}"
r = T.dien_tap_bat_dau()
kiem("bắt đầu: ghi giờ server, người diễn tập", DTAP[r["name"]]["bat_dau"] == GIO[0]
     and DTAP[r["name"]]["nguoi"] == "ql@x")
kiem("bấm lại khi đang chạy → trả đúng lần đang chạy, không đẻ lần thứ hai",
     T.dien_tap_bat_dau()["name"] == r["name"] and len(DTAP) == 1)
kiem("tải lại trang vẫn thấy lần đang chạy", (T.dien_tap_dang() or {}).get("name") == r["name"])
GIO[0] = _dtt.datetime(2026, 10, 8, 9, 22, 10)
kq = T.dien_tap_ket_thuc(r["name"], "SEN-061026", ton_thuc_te="250", ghi_chu="đếm kho TP")
dd = DTAP[r["name"]]
kiem("kết thúc: thời gian làm tròn lên phút (22 phút 10 giây → 23)", dd["so_phut"] == 23, dd["so_phut"])
kiem("ghi lô, sản phẩm, HSD", (dd["lo"], dd["hsd"]) == ("SEN-061026", "2027-04-04"))
kiem("ghi bảng cân bằng theo số đếm thực tế (140 + 5 + 250 = 395 / 400 = 98,8% đạt)",
     (dd["ton_thuc_te"], dd["can_bang_pt"], dd["dat"]) == (250, 98.8, 1),
     (dd["ton_thuc_te"], dd["can_bang_pt"], dd["dat"]))
kiem("đếm khách, lô nguyên liệu NCC truy được", dd["so_khach"] >= 1 and dd["so_ncc"] >= 1,
     (dd["so_khach"], dd["so_ncc"]))
kiem("ảnh chụp kết quả lưu lại (in lại tháng sau vẫn đúng)",
     json.loads(dd["ket_qua"])["lo"]["batch"] == "SEN-061026")
_, loi = thu(lambda: T.dien_tap_ket_thuc(r["name"], "SEN-061026"))
kiem("kết thúc lần hai → chặn (giữ đúng giờ lần đầu)", loi is not None)
_, loi = thu(lambda: T.dien_tap_huy(r["name"]))
kiem("lần đã kết thúc là hồ sơ — không bỏ được", loi is not None and r["name"] in DTAP)
kiem("không còn lần nào đang chạy", T.dien_tap_dang() is None)
kiem("in phụ lục BM.02.04 từ ảnh chụp", T.in_dien_tap(r["name"]).startswith(T.MAU_IN))
r2 = T.dien_tap_bat_dau()
T.dien_tap_huy(r2["name"])
kiem("bỏ lần chưa kết thúc (bấm nhầm)", r2["name"] not in DTAP)
VAI.clear(); VAI.add("ISO Manager")
kiem("Ban ISO dùng được truy xuất / diễn tập", T.dien_tap_dang() is None)
VAI.clear(); VAI.add("SX QC")
_, loi = thu(lambda: T.dien_tap_bat_dau())
kiem("QC thường không diễn tập được", loi is not None)
VAI.clear(); VAI.add("SX Quan Ly")
import jinja2  # noqa: E402
html = jinja2.Environment(loader=jinja2.FileSystemLoader("."), autoescape=True).get_template(
    T.MAU_IN).render(d=D(dd), kq=json.loads(dd["ket_qua"]), nguong=98.0,
                     frappe=types.SimpleNamespace(utils=types.SimpleNamespace(
                         formatdate=lambda x, f=None: str(x), format_datetime=lambda x, f=None: str(x))))
kiem("mẫu in A4 dựng được: phụ lục BM.02.04, cân bằng, kết luận, khách",
     "Phụ lục BM.02.04" in html and "Cân bằng lô" in html and "ĐẠT" in html and "Đại lý Hà" in html)
tx = open("sx/public/sx/cards/truyxuat.js", encoding="utf-8").read()
kiem("thẻ truy xuất: nút diễn tập, đồng hồ, kết thúc ở lô, in phụ lục",
     "DIỄN TẬP TRUY XUẤT" in tx and "dien_tap_ket_thuc" in tx and "in_dien_tap" in tx
     and "data-ketthuc" in tx)
qj = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
kiem("màn QC: tab Truy xuất + Xem xét cho Ban ISO (la_iso)",
     "truyxuat: '/assets/sx/sx/views/qc_truyxuat.js'" in qj and "api.boot.la_iso" in qj)
pt = open("sx/api/portal.py", encoding="utf-8").read()
kiem("boot có cờ la_iso", '"la_iso": super_ or "ISO Manager" in roles' in pt)

print()
if hong:
    print(f"TRUYXUAT-HỎNG ({hong})")
    sys.exit(1)
print("TRUYXUAT-OK")
