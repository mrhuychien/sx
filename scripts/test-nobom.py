"""D97 — nhập kho thành phẩm CHƯA có BOM: vẫn nhập được, nhưng ghi nợ để bù sau.

Vì sao phải có bài này: cơ chế này cố tình NỚI một cái chặn cũ. Nới sai theo hai
hướng đều im lặng:

  · Nới quá tay — hàng vào kho mà khoản nợ nguyên liệu không được ghi, hoặc ghi mà
    huỷ phiếu không xoá nợ. Tồn bột / bao bì trên sổ lệch vĩnh viễn, kiểm kê nào
    cũng "thiếu" mà không ai nhớ ra vì sao.
  · Bù sai — trừ nguyên liệu hai lần, trừ sai số, hoặc thủ kho tự bù được. Bù là
    ghi chứng từ kho thật.

Nạp controller SX Phieu Nhap TP, SX No BOM và sx/api/khotp.py THẬT; frappe và các
hàm sinh chứng từ kho là giả (đếm lại được đã gọi gì, với số nào).

Chạy: python3 scripts/test-nobom.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import sys
import types
from datetime import date

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# ── thế giới giả ─────────────────────────────────────────────────────────
BOM = {"TP-A": "BOM-A"}                                   # TP-B chưa có BOM
DINH_MUC = {"BOM-A": {"BOT": 0.5, "HOP": 1.0}}           # / 1 hộp
TON = {("BOT", "KHO-BTP"): 1000.0, ("HOP", "KHO-NVL"): 1000.0}
GIA_BIN = {}
GIA_ITEM = {"TP-B": 12000.0}
NO = []                                                   # bảng SX No BOM
SE = []                                                   # phiếu kho đã sinh
HUY = []                                                  # phiếu kho đã huỷ
VAI = {"SX Quan Ly"}
TON_AM = [False]


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v

    def db_set(self, k, v=None, **kw):
        if isinstance(k, dict):
            self.update(k)
        else:
            self[k] = v


class NoDoc(Doc):
    @property
    def flags(self):
        return types.SimpleNamespace()

    def insert(self, **kw):
        self["name"] = f"NB-{len(NO) + 1:04d}"
        NO.append(self)
        return self

    def save(self):
        N.SXNoBOM.validate(self)
        return self


def _khop(h, f):
    for k, v in (f or {}).items():
        if h.get(k) != v:
            return False
    return True


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.msgprint = lambda *a, **k: None
# D114: mã hàng có Shelf Life — HSD tự điền, không chặn duyệt (test-hsd.py lo phần đó).
frappe.get_cached_value = lambda dt, n, f=None: 180 if f == "shelf_life_in_days" else None
frappe.session = types.SimpleNamespace(user="ql@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = lambda dt, filters=None, fields=None, order_by=None, **k: [
    Doc(h) for h in (NO if dt == "SX No BOM" else []) if _khop(h, filters)]
frappe.get_doc = lambda x, n=None: (NoDoc(x) if isinstance(x, dict)
                                    else next(h for h in NO if h["name"] == n))


def _get_value(dt, f, field=None, **kw):
    if dt == "Bin":
        k = (f["item_code"], f["warehouse"])
        return GIA_BIN.get(k) if field == "valuation_rate" else TON.get(k, 0)
    if dt == "Item":
        return GIA_ITEM.get(f)
    return None


def _set_value(dt, name, vals, v=None, **kw):
    h = next(x for x in NO if x["name"] == name)
    h.update(vals if isinstance(vals, dict) else {vals: v})


frappe.db = types.SimpleNamespace(get_value=_get_value, set_value=_set_value)
frappe.__dict__["_"] = lambda s: s
frappe.utils = types.ModuleType("frappe.utils")
frappe.utils.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
frappe.utils.cint = lambda v: int(float(v or 0))
frappe.utils.getdate = lambda x=None: (date.fromisoformat(str(x)[:10]) if x else date(2026, 9, 28))
frappe.utils.nowdate = lambda: "2026-09-28"
frappe.utils.add_days = lambda d, n: d
frappe.utils.now_datetime = lambda: "2026-09-28 10:00:00"
frappe.utils.now = lambda: "2026-09-28 10:00:00"
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = frappe.utils
mdl = types.ModuleType("frappe.model"); mdl.__path__ = []
dm = types.ModuleType("frappe.model.document"); dm.Document = Doc
sys.modules["frappe.model"] = mdl
sys.modules["frappe.model.document"] = dm

for g in ("sx", "sx.api", "sx.config", "sx.sx", "sx.sx.doctype"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m

ut = types.ModuleType("sx.utils")
ut.get_bom_active = lambda item: BOM.get(item)
ut.get_settings = lambda: Doc({"cong_ty": "RVHG", "kho_nvl": "KHO-NVL",
                               "kho_btp": "KHO-BTP", "kho_tp": "KHO-TP"})
ut.sinh_ma_lo = lambda item, ngay: f"{item}-{str(ngay)[8:10]}{str(ngay)[5:7]}"
ut.cho_phep_ton_am = lambda: TON_AM[0]
ut.items_tp = lambda *a: []
ut.nhom_tp = lambda: []
sys.modules["sx.utils"] = ut

chot = types.ModuleType("sx.api.chot")
chot._kho_nguon = lambda it, s: "KHO-BTP" if it == "BOT" else "KHO-NVL"
chot._nhu_cau_bom = lambda bom, qty: {k: v * float(qty) for k, v in DINH_MUC[bom].items()}
sys.modules["sx.api.chot"] = chot

mfg = types.ModuleType("sx.api.mfg")


def _se(loai, **kw):
    d = Doc({"name": f"SE-{len(SE) + 1:03d}", "loai": loai, **kw})
    SE.append(d)
    return d


mfg.tao_batch = lambda item, lo, **k: lo
mfg.tao_wo = lambda *a, **k: _se("WO", item=a[1], qty=a[2])
mfg.tao_se_manufacture = lambda wo, qty, batch, **k: _se("Manufacture", item=wo.item, qty=qty)
mfg.tao_se_nhap_thang = lambda ct, item, qty, kho, batch, gia=0, **k: _se(
    "Material Receipt", item=item, qty=qty, kho=kho, batch=batch, gia=gia)
mfg.tao_se_xuat_bu = lambda ct, nhu_cau, kho_nguon, **k: _se(
    "Material Issue", nhu_cau=dict(nhu_cau), kho={i: kho_nguon(i) for i in nhu_cau})
mfg.cancel_doc = lambda dt, name, log=None: HUY.append(name)
sys.modules["sx.api.mfg"] = mfg


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


R = nap("sx.config.roles", "sx/config/roles.py")
K = nap("sx.api.khotp", "sx/api/khotp.py")
P = nap("sx.sx.doctype.sx_phieu_nhap_tp.sx_phieu_nhap_tp",
        "sx/sx/doctype/sx_phieu_nhap_tp/sx_phieu_nhap_tp.py")
N = nap("sx.sx.doctype.sx_no_bom.sx_no_bom", "sx/sx/doctype/sx_no_bom/sx_no_bom.py")

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
        return str(e)


def phieu(*dong):
    d = P.SXPhieuNhapTP({"name": "SXNTP-0001", "ngay": "2026-09-20", "kho_dich": "KHO-TP",
                         "dong": [Doc(x, idx=i + 1) for i, x in enumerate(dong)],
                         "ds_se": None, "flags": {}})
    return d


def lam_sach():
    NO.clear(); SE.clear(); HUY.clear()
    VAI.clear(); VAI.add("SX Quan Ly")
    TON_AM[0] = False


# ═══ 1. Duyệt phiếu có dòng thiếu BOM ════════════════════════════════════
print("-- duyệt phiếu: một dòng có BOM, một dòng chưa có --")
lam_sach()
p = phieu({"item": "TP-A", "ten": "A", "so_dem": 100, "dvt": "Hộp"},
          {"item": "TP-B", "ten": "B", "so_dem": 40, "dvt": "Hộp"})
kiem("kiểm tồn KHÔNG chặn vì dòng thiếu BOM", thu(p.kiem_ton_nguyen_lieu) is None)
loi = thu(p.on_submit)
kiem("duyệt KHÔNG chặn vì dòng thiếu BOM", loi is None, loi or "")
loai = [(x["loai"], x.get("item")) for x in SE]
kiem("dòng có BOM đi đường cũ (Work Order + Manufacture)",
     ("WO", "TP-A") in loai and ("Manufacture", "TP-A") in loai, str(loai))
kiem("dòng thiếu BOM nhập thẳng (Material Receipt), KHÔNG qua Manufacture",
     ("Material Receipt", "TP-B") in loai and ("Manufacture", "TP-B") not in loai)
kiem("dòng thiếu BOM không trừ nguyên liệu nào",
     not any(x["loai"] == "Material Issue" for x in SE))
nr = [x for x in SE if x["loai"] == "Material Receipt"][0]
kiem("nhập đúng số THỦ KHO ĐẾM, đúng kho, có lô theo ngày",
     (nr["qty"], nr["kho"], nr["batch"]) == (40, "KHO-TP", "TP-B-2009"),
     str((nr["qty"], nr["kho"], nr["batch"])))
kiem("ghi đúng MỘT dòng nợ", len(NO) == 1, str(len(NO)))
no = NO[0]
kiem("nợ trỏ về đúng phiếu, dòng, lô, phiếu kho nhập tạm",
     (no["phieu_nhap"], no["dong_idx"], no["batch"], no["se_nhap"])
     == ("SXNTP-0001", 2, "TP-B-2009", nr["name"]))
kiem("nợ mở ở trạng thái Chờ BOM, đúng số lượng",
     (no["trang_thai"], no["so_luong"]) == ("Chờ BOM", 40))
kiem("phiếu kho nhập tạm được ghi vào ds_se (huỷ phiếu là thu hồi được)",
     nr["name"] in p["ds_se"])

print("\n-- giá vốn tạm: không bịa --")
lam_sach(); GIA_BIN[("TP-B", "KHO-TP")] = 15000.0
phieu({"item": "TP-B", "so_dem": 5}).on_submit()
kiem("ưu tiên giá vốn đang chạy ở kho", NO[0]["gia_tam"] == 15000.0, str(NO[0]["gia_tam"]))
lam_sach(); GIA_BIN.clear()
phieu({"item": "TP-B", "so_dem": 5}).on_submit()
kiem("không có thì lấy giá trên Item", NO[0]["gia_tam"] == 12000.0)
lam_sach(); GIA_ITEM.pop("TP-B")
phieu({"item": "TP-B", "so_dem": 5}).on_submit()
kiem("không có gì cả thì 0 — không bịa giá", NO[0]["gia_tam"] == 0)
GIA_ITEM["TP-B"] = 12000.0

# ═══ 2. Hạch toán bù ═════════════════════════════════════════════════════
print("\n-- hạch toán bù --")
lam_sach()
phieu({"item": "TP-C", "so_dem": 100}).on_submit()
phieu({"item": "TP-C", "so_dem": 60}).on_submit()
loi = thu(lambda: K.hach_toan_bu("TP-C"))
kiem("chưa có BOM → không bù được, và nói phải làm gì",
     loi and "chưa có BOM" in loi, loi or "")
BOM["TP-C"] = "BOM-C"; DINH_MUC["BOM-C"] = {"BOT": 0.5, "HOP": 1.0}
VAI.clear(); VAI.add("SX Thu Kho")
loi = thu(lambda: K.hach_toan_bu("TP-C"))
kiem("THỦ KHO không tự bù được (bù là ghi chứng từ kho)", loi is not None)
VAI.clear(); VAI.add("SX Quan Ly")
TON[("BOT", "KHO-BTP")] = 50.0          # cần 80 kg
so_se_truoc = len(SE)
loi = thu(lambda: K.hach_toan_bu("TP-C"))
kiem("thiếu bột → chặn, và kiểm GỘP (2 dòng cần 80 kg, tồn 50)",
     loi and "BOT" in loi and "80" in loi, loi or "")
kiem("chặn thì KHÔNG ghi phiếu kho nào", len(SE) == so_se_truoc)
kiem("và không dòng nợ nào đổi trạng thái",
     all(x["trang_thai"] == "Chờ BOM" for x in NO))
TON[("BOT", "KHO-BTP")] = 1000.0
kq = K.hach_toan_bu("TP-C")
xuat = [x for x in SE if x["loai"] == "Material Issue"]
kiem("mỗi dòng nợ MỘT phiếu trừ riêng (huỷ phiếu nhập nào thì huỷ đúng phiếu bù đó)",
     len(xuat) == 2 and kq["so_dong"] == 2, str(len(xuat)))
kiem("trừ đúng BOM × số đã nhập",
     [x["nhu_cau"] for x in xuat] == [{"BOT": 50.0, "HOP": 100.0},
                                      {"BOT": 30.0, "HOP": 60.0}],
     str([x["nhu_cau"] for x in xuat]))
kiem("rút đúng kho nguồn (bột từ BTP, hộp từ NVL)",
     xuat[0]["kho"] == {"BOT": "KHO-BTP", "HOP": "KHO-NVL"})
kiem("nợ chuyển Đã hạch toán bù, ghi BOM + phiếu bù + ai làm",
     all((x["trang_thai"], x["bom"], bool(x["se_bu"]), x["xu_ly_boi"])
         == ("Đã hạch toán bù", "BOM-C", True, "ql@x") for x in NO))
loi = thu(lambda: K.hach_toan_bu("TP-C"))
kiem("bấm bù lần hai → không trừ thêm lần nào", loi is not None
     and len([x for x in SE if x["loai"] == "Material Issue"]) == 2)

# ═══ 3. Bỏ qua ═══════════════════════════════════════════════════════════
print("\n-- bỏ qua một dòng nợ --")
lam_sach()
phieu({"item": "TP-B", "so_dem": 7}).on_submit()
kiem("thiếu lý do → chặn", thu(lambda: K.bo_qua_no(NO[0]["name"], "  ")) is not None)
VAI.clear(); VAI.add("SX Thu Kho")
kiem("thủ kho không bỏ qua được",
     thu(lambda: K.bo_qua_no(NO[0]["name"], "hàng trả về")) is not None)
VAI.clear(); VAI.add("SX Quan Ly")
K.bo_qua_no(NO[0]["name"], "hàng trả về từ đại lý")
kiem("có lý do → Bỏ qua, không trừ nguyên liệu nào",
     NO[0]["trang_thai"] == "Bỏ qua"
     and not any(x["loai"] == "Material Issue" for x in SE))
kiem("không bỏ qua được lần hai",
     thu(lambda: K.bo_qua_no(NO[0]["name"], "x")) is not None)
kiem("sổ nợ không cho đặt 'Đã hạch toán bù' tay mà không có phiếu bù",
     thu(lambda: N.SXNoBOM.validate(Doc({"trang_thai": "Đã hạch toán bù"}))) is not None)

# ═══ 4. Huỷ phiếu nhập ═══════════════════════════════════════════════════
print("\n-- huỷ phiếu nhập có dòng nợ --")
lam_sach()
p = phieu({"item": "TP-B", "so_dem": 9})
p.on_submit()
p["ds_se"] = json.dumps([{"dt": "Stock Entry", "name": x["name"]} for x in SE])
p.on_cancel()
kiem("nợ còn mở → Đã huỷ", NO[0]["trang_thai"] == "Đã huỷ")
kiem("phiếu kho nhập tạm bị thu hồi", NO[0]["se_nhap"] in HUY)

lam_sach()
BOM.pop("TP-C", None)                      # lúc nhập: CHƯA có BOM
p = phieu({"item": "TP-C", "so_dem": 10})
p.on_submit()
BOM["TP-C"] = "BOM-C"                      # sau đó mới có BOM → bù
K.hach_toan_bu("TP-C")
se_bu = NO[0]["se_bu"]
p["ds_se"] = json.dumps([{"dt": "Stock Entry", "name": NO[0]["se_nhap"]}])
p.on_cancel()
kiem("nợ ĐÃ BÙ → huỷ luôn phiếu trừ bù (không thì kho mất bột oan)", se_bu in HUY,
     str(HUY))
kiem("và nợ đó chuyển Đã huỷ", NO[0]["trang_thai"] == "Đã huỷ")

# ═══ 5. Sổ nợ gom theo mã ════════════════════════════════════════════════
print("\n-- sổ nợ trên màn hình --")
lam_sach()
BOM.pop("TP-C", None)
phieu({"item": "TP-B", "so_dem": 3}).on_submit()
phieu({"item": "TP-B", "so_dem": 4}).on_submit()
BOM["TP-D"] = "BOM-A"
NO.append(NoDoc({"name": "NB-X", "item": "TP-D", "ten": "D", "so_luong": 2, "dvt": "",
                 "ngay": "2026-09-27", "trang_thai": "Chờ BOM", "gia_tam": 1}))
dl = K.so_no_bom()
kiem("gom theo mã hàng, cộng số lượng",
     {g["item"]: g["so_luong"] for g in dl["nhom"]} == {"TP-B": 7.0, "TP-D": 2.0})
kiem("mã ĐÃ có BOM đứng đầu (xử lý được ngay)", dl["nhom"][0]["item"] == "TP-D")
kiem("báo nợ quá 7 ngày", next(g for g in dl["nhom"] if g["item"] == "TP-B")["lau"])
kiem("quản lý thấy nút xử lý", dl["duoc_xu_ly"])
VAI.clear(); VAI.add("SX Thu Kho")
kiem("thủ kho xem được nhưng không có nút xử lý", not K.so_no_bom()["duoc_xu_ly"])

print("NOBOM-FAIL ({} ca)".format(hong) if hong else "NOBOM-OK")
sys.exit(1 if hong else 0)
