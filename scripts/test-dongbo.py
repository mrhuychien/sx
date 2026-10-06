"""D123 — bỏ CHỐT, đồng bộ ngầm kho + lương (sx/api/dongbo.py).

Đồng bộ chạy ngầm nên hỏng là hỏng IM LẶNG: kho lệch báo mẻ mà không ai bấm gì để
thấy. Test dựng các tình huống thật:
  · ngày đầu: ghi đủ, đúng thứ tự topo (đường hoán trước bột bánh);
  · báo thêm mẻ: chỉ ghi PHẦN CHÊNH, cùng lô, mã khác không bị đụng;
  · bớt mẻ: rút chứng từ mới nhất rồi ghi lại phần thiếu;
  · rút không được (bột đã dùng) / thiếu tồn / thiếu giá vốn: lỗi ghi lên ngày, mã khác
    vẫn đồng bộ, sổ cái khớp đúng DB;
  · lương: ghi đè ngày, gỡ người không còn, nợ giá đối chiếu chứ không huỷ-tạo lại;
  · dấu chờ / lỗi / thử lại / job dự phòng; xoá ngày rút hết.

Nạp sx/api/dongbo.py THẬT; frappe + các module khác là giả có trạng thái.
Chạy: python3 scripts/test-dongbo.py   (verify.sh gọi sẵn)
"""

import copy
import importlib.util
import json
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class Loi(Exception):
    pass


class D(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


ST = {}          # trạng thái "DB" — savepoint chụp / khôi phục toàn bộ dict này


def lam_sach():
    globals().get("LO_DEM", {}).clear()
    ST.clear()
    ST.update(ngay={}, docs={}, dem=0, enq=[], luong=[], go=[], no=[], gia_ghi=[],
              rut_hong=set(), thieu_ton=set(), hoi=[], tu_tinh=[], luong_hong=None,
              savepoints={})


lam_sach()


class NgayDoc(D):
    def db_set(self, k, v=None, **kw):
        vals = k if isinstance(k, dict) else {k: v}
        self.update(vals)
        ST["ngay"][self["name"]].update(vals)


def ngay(name="SXN-1", bao_me=(), **k):
    d = D(name=name, ngay="2026-10-06", docstatus=0, can_dong_bo_gs=0, can_dong_bo_vh=0,
          loi_dong_bo_gs=None, loi_dong_bo_vh=None, so_cai_ghiso=None,
          salary_products_json=None, bao_me=[D(r, name=f"bm{i}") for i, r in enumerate(bao_me)], **k)
    ST["ngay"][name] = d
    return d


def get_doc(dt, n=None):
    if dt == "SX Ngay San Xuat":
        return NgayDoc(copy.deepcopy(ST["ngay"][n]))
    if dt == "SX Bang Vao Hop":
        return ST["bang"]
    raise AssertionError(dt)


def get_value(dt, f, field=None, as_dict=False, **k):
    if dt == "SX Ngay San Xuat":
        n = ST["ngay"].get(f)
        if not n:
            return None
        if isinstance(field, list):
            return D({x: n.get(x) for x in field}) if as_dict else tuple(n.get(x) for x in field)
        return n.get(field)
    if dt == "SX Bang Vao Hop":
        return ST.get("bang", {}).get("name")
    if dt == "Item":
        return {"BB": "Bột bánh", "DH": "Đường hoán", "BD": "Bột đậu"}.get(f, f)
    return None


def set_value(dt, n, k, v=None, **kw):
    vals = k if isinstance(k, dict) else {k: v}
    if dt == "SX Ngay San Xuat":
        ST["ngay"][n].update(vals)
    elif dt == "SX No Don Gia":
        next(x for x in ST["no"] if x["name"] == n).update(vals)
    elif dt == "SX Bao Me":
        for d in ST["ngay"].values():
            for r in d["bao_me"]:
                if r["name"] == n:
                    r.update(vals)


def savepoint(ten):
    ST["savepoints"][ten] = copy.deepcopy({k: v for k, v in ST.items() if k != "savepoints"})


def rollback(save_point=None):
    snap = ST["savepoints"].pop(save_point)
    sp = ST["savepoints"]
    ST.clear()
    ST.update(copy.deepcopy(snap))
    ST["savepoints"] = sp


def get_all(dt, filters=None, fields=None, pluck=None, or_filters=None, limit=None, **k):
    if dt == "SX No Don Gia":
        return [D(x) for x in ST["no"] if x["ngay_sx"] == filters["ngay_sx"]
                and x["trang_thai"] == filters["trang_thai"]]
    if dt == "SX Ngay San Xuat":
        ra = [n for n in ST["ngay"].values() if n["docstatus"] < 2
              and (n.get("can_dong_bo_gs") or n.get("can_dong_bo_vh"))]
        return [n["name"] for n in ra]
    return []


class NoDoc(D):
    @property
    def flags(self):
        return D()

    def insert(self):
        self["name"] = f"NO-{len(ST['no']) + 1}"
        ST["no"].append(D(self))


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, **k: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.ValidationError = Loi
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.session = types.SimpleNamespace(user="ql@x")
frappe.get_roles = lambda u=None: ["SX Quan Ly"]
frappe.local = types.SimpleNamespace(message_log=["cũ"])
frappe.get_doc = lambda dt, n=None: NoDoc(dt) if isinstance(dt, dict) else get_doc(dt, n)
frappe.get_all = get_all
frappe.enqueue = lambda m, **k: ST["enq"].append((m, k))
frappe.log_error = lambda **k: None
frappe.get_traceback = lambda: ""
frappe.db = types.SimpleNamespace(
    get_value=get_value, set_value=set_value, savepoint=savepoint, rollback=rollback,
    exists=lambda dt, n=None: n in ST["ngay"], sql=lambda *a, **k: None, commit=lambda: None)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.cint = lambda v: int(float(v or 0))
fu.getdate = lambda x=None: x
fu.now_datetime = lambda: "2026-10-06 10:00"
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
for g in ("sx", "sx.api", "sx.config"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m

# ── giả các module app ──
BOM = {"DH": {"DUONG": 1.0}, "BB": {"DH": 0.2, "BOT-NEN": 0.8}, "BD": {"BOT-NEN": 1.0}}


def moi_ten(tien_to):
    ST["dem"] += 1
    return f"{tien_to}-{ST['dem']}"


mfg = types.ModuleType("sx.api.mfg")


def tao_batch(item, ma, ngay_sx=None):
    return ma


def tao_wo(cty, item, qty, bom, **k):
    ten = moi_ten("WO")
    ST["docs"][ten] = D(dt="Work Order", item=item, qty=qty, docstatus=1)
    return D(name=ten)


def tao_se(wo, qty, lo, kho_nguon=None, **k):
    item = ST["docs"][wo["name"]].item
    if item in ST["thieu_ton"]:
        raise Loi("Không đủ tồn: cần thêm nguyên liệu")
    ten = moi_ten("SE")
    ST["docs"][ten] = D(dt="Stock Entry", item=item, qty=qty, lo=lo, docstatus=1)
    return D(name=ten)


def cancel_doc(dt, n, log=None):
    if n in ST["rut_hong"]:
        raise Loi(f"Lô của {n} đã được dùng — rút ra sẽ âm kho")
    if n in ST["docs"]:
        ST["docs"][n]["docstatus"] = 2


mfg.tao_batch, mfg.tao_wo, mfg.tao_se_manufacture, mfg.cancel_doc = tao_batch, tao_wo, tao_se, cancel_doc
mfg.xet_gia_von = lambda cap: {"hoi": list(ST["hoi"]), "tu_tinh": list(ST["tu_tinh"])}
mfg.ghi_gia_tu_tinh = lambda ds: ST["gia_ghi"].extend(ds)
sys.modules["sx.api.mfg"] = mfg
ch = types.ModuleType("sx.api.chot")
ch._kho_nguon = lambda it, s: "BTP" if it in BOM else "NVL"
ch._nhu_cau_bom = lambda bom, q: {k: v * q for k, v in BOM[bom].items()}
ch._co_gi_de_ghi = lambda b: bool(b and (b.dong or b.get("an_ca")))


def ghi_luong(doc, bang):
    if ST["luong_hong"]:
        raise Loi(ST["luong_hong"])
    ds = sorted({r.nhan_vien for r in bang.dong if not r.get("cong_nhat")})
    ST["luong"].append(ds)
    return [{"phieu": f"PL-{nv}", "employee": nv, "ngay": doc.ngay} for nv in ds]


ch._ghi_luong_khoan = ghi_luong
ch._go_luong_khoan = lambda ds: ST["go"].append([g["employee"] for g in ds])
sys.modules["sx.api.chot"] = ch
ng = types.ModuleType("sx.api.nogia")
ng.CHO = "Chờ giá"
ng.huy_no_gia = lambda n: [x.update(trang_thai="Đã huỷ") for x in ST["no"] if x["ngay_sx"] == n]


def gom_thieu(dong, gia):
    ra = {}
    for r in dong:
        if r.san_pham not in gia and not r.get("cong_nhat"):
            g = ra.setdefault((r.san_pham, ""), {"so_hop": 0, "nguoi": set()})
            g["so_hop"] += r.so_hop
            g["nguoi"].add(r.nhan_vien)
    return ra


ng.gom_thieu_gia = gom_thieu
sys.modules["sx.api.nogia"] = ng
ut = types.ModuleType("sx.utils")
ut.get_bom_active = lambda i: i if i in BOM else None
ut.get_settings = lambda: D(cong_ty="C", kho_nvl="NVL", kho_btp="BTP")
LO_DEM = {}


def sinh_ma_lo(item, ngay):
    """Như thật: lô đã có (đã dùng) thì sinh hậu tố mới — để test bắt được việc
    KHÔNG dùng lại lô của mã trong ngày."""
    LO_DEM[item] = LO_DEM.get(item, 0) + 1
    return f"{item}-061026" + ("" if LO_DEM[item] == 1 else f"-{LO_DEM[item]}")


ut.sinh_ma_lo = sinh_ma_lo
ut.topo_rank_by_bom = lambda ds: {"DH": 0, "BOT-NEN": 0, "BB": 1, "BD": 1}
ut.bang_don_gia = lambda ngay: "BDG-1"
ut.don_gia_ap_dung = lambda ngay: {"SEN": 1000}
sys.modules["sx.utils"] = ut
ro = types.ModuleType("sx.config.roles")
ro.guard_card = lambda c: None
sys.modules["sx.config.roles"] = ro


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


B = nap("sx.api.dongbo", "sx/api/dongbo.py")
hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


def so_cai(n="SXN-1"):
    return json.loads(ST["ngay"][n]["so_cai_ghiso"] or "[]")


def hieu_luc(item=None):
    """Chứng từ SE còn hiệu lực (docstatus 1) theo mã."""
    return {k: v for k, v in ST["docs"].items() if v.dt == "Stock Entry" and v.docstatus == 1
            and (item is None or v.item == item)}


def dong_bo(n="SXN-1"):
    return B.dong_bo_ghiso(get_doc("SX Ngay San Xuat", n))


def bao_me(n, **kg):
    ST["ngay"][n]["bao_me"] = [D(name=f"bm-{i}", item_btp=i, tong_kg=v) for i, v in kg.items()]


print("-- ghi sổ: lần đầu --")
lam_sach()
ngay(bao_me=[{"item_btp": "BB", "tong_kg": 100}, {"item_btp": "DH", "tong_kg": 10}])
loi = dong_bo()
sc = so_cai()
kiem("không lỗi", loi == [], loi)
kiem("ghi đủ hai mã, ĐƯỜNG HOÁN TRƯỚC bột bánh (topo)", [e["item"] for e in sc] == ["DH", "BB"], sc)
kiem("số kg đúng báo mẻ", [e["kg"] for e in sc] == [10, 100])
kiem("danh sách chứng từ phẳng cho thẻ chứng từ / truy xuất",
     len(json.loads(ST["ngay"]["SXN-1"]["ds_wo_se_ghiso"])) == 4)
kiem("mã lô hiện lên dòng báo mẻ", [r["batch"] for r in ST["ngay"]["SXN-1"]["bao_me"]] == ["BB-061026", "DH-061026"])
n_ct = len(ST["docs"])
kiem("chạy lại khi không đổi gì → không sinh / rút chứng từ nào", dong_bo() == [] and len(ST["docs"]) == n_ct)
lam_sach()
ngay(bao_me=[{"item_btp": "BB", "tong_kg": 100}, {"item_btp": "DH", "tong_kg": 10}])
goc = ut.topo_rank_by_bom
ut.topo_rank_by_bom = lambda ds: {"BB": 0, "DH": 1}
dong_bo()
ut.topo_rank_by_bom = goc
kiem("thứ tự ghi đi THEO topo (đổi hạng → đổi thứ tự)", [e["item"] for e in so_cai()] == ["BB", "DH"])
lam_sach()
ngay(bao_me=[{"item_btp": "BB", "tong_kg": 100}, {"item_btp": "DH", "tong_kg": 10}])
dong_bo()

print("\n-- báo thêm mẻ: chỉ ghi phần chênh --")
bao_me("SXN-1", BB=150, DH=10)
dong_bo()
bb = [e for e in so_cai() if e["item"] == "BB"]
kiem("bột bánh ghi THÊM 50, không rút cái cũ", [e["kg"] for e in bb] == [100, 50]
     and len(hieu_luc("BB")) == 2, bb)
kiem("… cùng một lô trong ngày", {e["batch"] for e in bb} == {"BB-061026"})
kiem("đường hoán không đổi → không đụng", len(hieu_luc("DH")) == 1
     and all(v.docstatus == 1 for v in ST["docs"].values() if v.item == "DH"))

print("\n-- bớt mẻ: rút mới nhất rồi ghi lại phần thiếu --")
bao_me("SXN-1", BB=120, DH=10)
dong_bo()
bb = [e for e in so_cai() if e["item"] == "BB"]
kiem("100 cũ giữ, 50 rút, ghi lại 20", [e["kg"] for e in bb] == [100, 20], bb)
kiem("chứng từ còn hiệu lực đúng bằng sổ cái", sorted(v.qty for v in hieu_luc("BB").values()) == [20, 100])
bao_me("SXN-1", BB=120)
dong_bo()
kiem("xoá hẳn dòng đường hoán → rút hết chứng từ đường hoán", not hieu_luc("DH")
     and all(e["item"] != "DH" for e in so_cai()))

print("\n-- không rút được (bột đã dùng): lỗi, mã khác vẫn chạy --")
bb_se = [e["se"] for e in so_cai() if e["item"] == "BB"]
ST["rut_hong"].add(bb_se[-1])
bao_me("SXN-1", BB=50, BD=30)
truoc = [e for e in so_cai() if e["item"] == "BB"]
loi = dong_bo()
kiem("lỗi nói rõ mã + lý do", len(loi) == 1 and loi[0].startswith("Bột bánh:") and "đã được dùng" in loi[0], loi)
kiem("sổ cái bột bánh giữ nguyên (khớp DB vì savepoint hoàn tác)",
     [e for e in so_cai() if e["item"] == "BB"] == truoc
     and sorted(v.qty for v in hieu_luc("BB").values()) == [20, 100])
kiem("bột đậu (mã khác) vẫn được ghi", [e["kg"] for e in so_cai() if e["item"] == "BD"] == [30])
kiem("tin nhắn msgprint của lần hỏng không trôi sang lần sau", frappe.local.message_log == [])
ST["rut_hong"].clear()

print("\n-- rút được một phần rồi mới hỏng: sổ cái phải khớp DB --")
lam_sach()
ngay(bao_me=[{"item_btp": "BB", "tong_kg": 100}])
dong_bo()
bao_me("SXN-1", BB=120)
dong_bo()
bao_me("SXN-1", BB=110)          # rút 20 (được) rồi ghi lại 10 (thiếu tồn -> hỏng)
ST["thieu_ton"].add("BB")
loi = dong_bo()
kiem("lỗi thiếu tồn", loi and "Không đủ tồn" in loi[0], loi)
kiem("sổ cái giữ [100, 20] — khớp đúng chứng từ còn hiệu lực sau hoàn tác",
     [e["kg"] for e in so_cai()] == [100, 20]
     and sorted(v.qty for v in hieu_luc("BB").values()) == [20, 100],
     ([e["kg"] for e in so_cai()], sorted(v.qty for v in hieu_luc("BB").values())))

print("\n-- thiếu tồn khi ghi thêm --")
lam_sach()
ngay(bao_me=[{"item_btp": "BB", "tong_kg": 40}, {"item_btp": "DH", "tong_kg": 5}])
ST["thieu_ton"].add("BB")
loi = dong_bo()
kiem("lỗi thiếu tồn ghi theo mã", loi == ["Bột bánh: Không đủ tồn: cần thêm nguyên liệu"], loi)
kiem("không để lại WO mồ côi của mã hỏng", all(v.item != "BB" for v in ST["docs"].values()))
kiem("đường hoán vẫn ghi", [e["item"] for e in so_cai()] == ["DH"])

print("\n-- giá vốn --")
lam_sach()
ngay(bao_me=[{"item_btp": "BB", "tong_kg": 40}])
ST["hoi"] = [{"item": "VANI", "ten": "Vani"}]
ST["tu_tinh"] = [{"item": "BOT-NEN", "gia": 28000}]
loi = dong_bo()
kiem("thiếu giá NVL → không ghi phần tăng, báo đúng một câu chỉ cách sửa",
     not so_cai() and len(loi) == 1 and "Vani" in loi[0] and "Thử lại" in loi[0], loi)
kiem("BTP tự tính giá vẫn được ghi (không hỏi ai)", ST["gia_ghi"] == [{"item": "BOT-NEN", "gia": 28000}])
ST["hoi"] = []
kiem("khai giá xong → lần sau ghi được", dong_bo() == [] and [e["kg"] for e in so_cai()] == [40])

print("\n-- vào hộp: phiếu lương + nợ giá --")
lam_sach()
ngay()
ST["bang"] = D(name="BVH-1", dong=[D(nhan_vien="An", san_pham="SEN", so_hop=100, thanh_tien=100000),
                                   D(nhan_vien="Bình", san_pham="MOI", so_hop=30, thanh_tien=0),
                                   D(cong_nhat=1, san_pham="MOI", so_hop=20, thanh_tien=0)])
doc = get_doc("SX Ngay San Xuat", "SXN-1")
kiem("không lỗi", B.dong_bo_vaohop(doc) == [])
n = ST["ngay"]["SXN-1"]
kiem("ghi phiếu lương các người trong bảng", ST["luong"][-1] == ["An", "Bình"])
kiem("tổng ngày (cả công nhật) + tiền", n["tong_hop_tp"] == 150 and n["tong_luong_sp"] == 100000, n)
kiem("nợ giá mã chưa có giá (không tính công nhật)", [(x.san_pham, x.so_hop, x.trang_thai)
                                                     for x in ST["no"]] == [("MOI", 30, "Chờ giá")])
ST["bang"]["dong"] = [D(nhan_vien="An", san_pham="SEN", so_hop=120, thanh_tien=120000),
                      D(nhan_vien="An", san_pham="MOI", so_hop=10, thanh_tien=0)]
B.dong_bo_vaohop(get_doc("SX Ngay San Xuat", "SXN-1"))
kiem("người không còn trong bảng → gỡ ngày khỏi phiếu lương của họ", ST["go"][-1] == ["Bình"], ST["go"])
kiem("nợ giá CẬP NHẬT tại chỗ, không huỷ-tạo lại", [(x.name, x.so_hop, x.trang_thai) for x in ST["no"]]
     == [("NO-1", 10, "Chờ giá")], ST["no"])
ST["bang"]["dong"] = [D(nhan_vien="An", san_pham="SEN", so_hop=120, thanh_tien=120000)]
B.dong_bo_vaohop(get_doc("SX Ngay San Xuat", "SXN-1"))
kiem("hết thiếu giá → huỷ nợ", ST["no"][0]["trang_thai"] == "Đã huỷ")
ST["luong_hong"] = "Phiếu lương PL-An tháng 10 ĐÃ DUYỆT"
truoc = copy.deepcopy(ST["ngay"]["SXN-1"])
loi = B.dong_bo_vaohop(get_doc("SX Ngay San Xuat", "SXN-1"))
kiem("phiếu lương đã duyệt → lỗi rõ ràng", loi == ["Phiếu lương PL-An tháng 10 ĐÃ DUYỆT"], loi)
kiem("… và không để nửa vời (tổng / danh sách lương giữ như trước)",
     ST["ngay"]["SXN-1"]["salary_products_json"] == truoc["salary_products_json"])

print("\n-- dấu chờ, chạy, lỗi, thử lại --")
lam_sach()
ngay(bao_me=[{"item_btp": "DH", "tong_kg": 5}])
ST["ngay"]["SXN-1"]["loi_dong_bo_gs"] = "lỗi cũ"
B.danh_dau("SXN-1", "gs")
n = ST["ngay"]["SXN-1"]
kiem("lưu → đánh dấu chờ + xoá lỗi cũ (số liệu mới có thể đã sửa được)",
     n["can_dong_bo_gs"] == 1 and n["loi_dong_bo_gs"] is None)
kiem("xếp job nền chống trùng theo ngày", ST["enq"] and ST["enq"][-1][1]["job_id"] == "sx-dongbo-SXN-1"
     and ST["enq"][-1][1]["deduplicate"] and ST["enq"][-1][1]["enqueue_after_commit"], ST["enq"])
B.chay("SXN-1")
kiem("chạy xong → hết dấu, đã ghi kho", n["can_dong_bo_gs"] == 0 and so_cai() and n.get("dong_bo_luc"))
bao_me("SXN-1", DH=5, BB=40)
ST["thieu_ton"].add("BB")
B.danh_dau("SXN-1", "gs", chay_ngay=False)
B.chay("SXN-1")
n = ST["ngay"]["SXN-1"]          # savepoint hoàn tác thay cả dict — đọc lại
kiem("lỗi → giữ dấu chờ + ghi lỗi lên ngày", n["can_dong_bo_gs"] == 1 and "Bột bánh" in (n["loi_dong_bo_gs"] or ""), n)
ST["thieu_ton"].clear()
B.chay_tat_ca()
kiem("job dự phòng KHÔNG tự thử lại ngày đang lỗi", "BB" not in [e["item"] for e in so_cai()])
r = B.thu_lai("SXN-1")
kiem("quản lý bấm Thử lại → chạy cả phần lỗi, hết lỗi", "BB" in [e["item"] for e in so_cai()]
     and r["gs"] == {"cho": 0, "loi": None}, r)
B.danh_dau("SXN-1", "gs", chay_ngay=False)
bao_me("SXN-1", DH=5, BB=60)
B.chay_tat_ca()
kiem("job dự phòng làm ngày còn dấu (job nền bị lỡ)", sum(e["kg"] for e in so_cai() if e["item"] == "BB") == 60)
kiem("ngày không tồn tại → bỏ qua, không lỗi", B.chay("KHONG-CO") is None)

print("\n-- xoá ngày: rút hết --")
doc = get_doc("SX Ngay San Xuat", "SXN-1")
doc["salary_products_json"] = json.dumps([{"phieu": "PL-An", "employee": "An"}])
B.go_het(doc)
kiem("mọi chứng từ ghi sổ bị rút", not hieu_luc())
kiem("gỡ lương ngày đó", ST["go"][-1] == ["An"])

print("\n-- dây nối --")
hk = open("sx/hooks.py", encoding="utf-8").read()
kiem("lưu / xoá bảng vào hộp → đồng bộ lương", '"sx.api.dongbo.sau_luu_bang"' in hk
     and '"on_trash": "sx.api.dongbo.sau_luu_bang"' in hk)
kiem("job dự phòng 5 phút", '"*/5 * * * *": ["sx.api.dongbo.chay_tat_ca"]' in hk)
kiem("không còn hook huỷ chốt cũ", "on_cancel_ngay" not in hk)
c = open("sx/sx/doctype/sx_ngay_san_xuat/sx_ngay_san_xuat.py", encoding="utf-8").read()
kiem("báo mẻ đổi (portal hay Desk) → đánh dấu đồng bộ kho", 'danh_dau(self.name, "gs")' in c)
kiem("xoá phiếu ngày → rút chứng từ", "go_het(self)" in c)
kiem("không còn khoá sửa báo mẻ sau chốt", "chan_sua_bao_me" not in c)
pt = open("sx/api/portal.py", encoding="utf-8").read()
kiem("API sửa báo mẻ / bảng không còn chặn theo cờ chốt",
     'if cint(d) == 2:' in pt and '"chot_vaohop": 1' not in pt)
cht = open("sx/api/chot.py", encoding="utf-8").read()
kiem("API chốt cũ chỉ còn trả câu 'không còn chốt'", "def _da_bo(" in cht
     and "def chot_ghiso(" not in cht and "def huy_chot_ngay(" not in cht)
kiem("patch mở lại ngày đã chốt có trong patches.txt", "sx.patches.d123_bo_chot" in open("sx/patches.txt").read())

print()
if hong:
    print(f"DONGBO-HỎNG ({hong})")
    sys.exit(1)
print("DONGBO-OK")
