"""D138 (W09 + W10) — nhà cung cấp được duyệt BM.07.02, tiếp nhận nguyên liệu BM.07.03
trên phiếu nhập mua.

Vì sao phải có bài này:
  · Ai có quyền ghi Supplier tự tích "Đã duyệt", hay duyệt khi hồ sơ thiếu / hết hạn →
    danh sách BM.07.02 là danh sách tự khai.
  · Chặn nhầm mua hàng (tài liệu nói CHỈ CẢNH BÁO) → thủ kho không nhập được hàng.
  · Hàng nhập khẩu không COA lô, NCC trong nước không có phiếu kiểm nghiệm năm còn hạn,
    lạc không có aflatoxin mà vẫn "Đạt" → lô thực phẩm vào kho không giấy tờ.
  · Lô Không đạt / Cách ly nhập chung kho nguyên liệu → bị lấy đi sản xuất.
  · Cát rang bị đòi giấy tờ thực phẩm → thủ kho không nhập được cát.

Nạp sx/qc/ncc.py, sx/qc/tiep_nhan.py, sx/api/qc_ncc.py, sx/api/qc.py THẬT; frappe giả.
Chạy: python3 scripts/test-ncc.py   (verify.sh gọi sẵn)
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
SUPPLIER = {}
HO_SO = []            # SX Ho So NCC: {parent, parenttype, loai_ho_so, so_hieu, het_han}
DA_TAO = []           # SX Su Co
BAO = []
NHOM = {"Lạc nhân": "Nguyên liệu", "Nguyên liệu": None, "Đỗ xanh": "Nguyên liệu", "Cát": None}
NHOM_ITEM = {"LAC-01": "Lạc nhân", "DX-01": "Đỗ xanh", "CAT-01": "Cát"}
CAI_DAT_QC = {}
SX_SET = {"kho_cach_ly": "Kho cách ly - RV"}
VAI = {"ISO Manager"}
NGUOI = {"u": "iso@x"}


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v

    def set(self, k, v):
        self[k] = v


class ScDoc(Doc):
    def append(self, f, r):
        self.setdefault(f, []).append(Doc(r))

    def insert(self, **kw):
        self["name"] = f"SC-{len(DA_TAO) + 1:04d}"
        DA_TAO.append(self)
        return self


def _so(x):
    return str(x) if x is not None else ""


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "in" and x not in m:
                return False
            if op == "is" and m == "set" and not x:
                return False
        elif _so(x) != _so(v):
            return False
    return True


def get_all(dt, filters=None, fields=None, pluck=None, order_by=None, limit=None, **k):
    nguon = {"Supplier": [dict({"disabled": 0}, **x) for x in SUPPLIER.values()],
             "SX Ho So NCC": HO_SO}.get(dt, [])
    ra = [Doc(h) for h in nguon if _khop(h, filters)]
    return [h.get(pluck) for h in ra] if pluck else ra


def _get_value(dt, n, fld=None, as_dict=False, **k):
    h = SUPPLIER.get(n) if dt == "Supplier" else None
    if h is None:
        return None
    if isinstance(fld, (list, tuple)):
        d = Doc({c: h.get(c) for c in fld})
        return d if as_dict else tuple(d.values())
    return h.get(fld)


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
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_doc = lambda d, n=None: ScDoc(d)
frappe.get_cached_doc = lambda dt: Doc(SX_SET if dt == "SX Settings" else CAI_DAT_QC)
frappe.get_cached_value = lambda dt, ten, truong: (NHOM.get(ten) if dt == "Item Group" else NHOM_ITEM.get(ten))
frappe.get_meta = lambda dt: types.SimpleNamespace(has_field=lambda f: True)
frappe.render_template = lambda p, ctx: _render(p, ctx)
frappe.db = types.SimpleNamespace(
    get_value=_get_value,
    exists=lambda dt, dk: any(x.get("khoa_cu") == dk.get("khoa_cu") for x in DA_TAO),
)
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
N = nap("sx.qc.ncc", "sx/qc/ncc.py")
T = nap("sx.qc.tiep_nhan", "sx/qc/tiep_nhan.py")
for t in ("san_pham", "su_co", "xuat", "nhac"):
    nap(f"sx.qc.{t}", f"sx/qc/{t}.py")
nap("sx.api.qc", "sx/api/qc.py")
A = nap("sx.api.qc_ncc", "sx/api/qc_ncc.py")

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


def vai(*v, u=None):
    VAI.clear(); VAI.update(v)
    NGUOI["u"] = u or {"ISO Manager": "iso@x"}.get(v[0], "kho@x")


def hs(*loai, het=None):
    return [Doc(loai_ho_so=x, so_hieu=f"{i + 1}/2026", het_han=het) for i, x in enumerate(loai)]


# ═══ 1. Bộ hồ sơ theo loại NCC ═════════════════════════════════════════════
print("\n-- bộ hồ sơ theo loại NCC (BM.07.02) --")
kiem("thực phẩm đủ (ĐKKD + ATTP + công bố) → đủ", N.thieu_ho_so(N.TP, hs(N.DKKD, N.ATTP, N.CONG_BO)) == [])
kiem("HACCP / ISO 22000 thay được giấy ATTP", N.thieu_ho_so(N.TP, hs(N.DKKD, N.HACCP, N.CONG_BO)) == [])
t = N.thieu_ho_so(N.TP, hs(N.DKKD))
kiem("thiếu → nói đúng nhóm còn thiếu", any("ATTP" in x and "HACCP" in x for x in t)
     and N.CONG_BO in t, t)
t = N.thieu_ho_so(N.TP, hs(N.DKKD, N.ATTP, N.CONG_BO, het=date(2026, 1, 1)))
kiem("giấy hết hạn → coi như thiếu, ghi '(hết hạn)'", len(t) == 3 and all("hết hạn" in x for x in t), t)
kiem("CÁT RANG chỉ cần hợp đồng / đơn hàng + ĐKKD", N.thieu_ho_so(N.CAT, hs(N.HOP_DONG, N.DKKD)) == []
     and N.thieu_ho_so(N.CAT, hs(N.DKKD)) == [N.HOP_DONG])
kiem("dịch vụ / khác → không đòi gì", N.thieu_ho_so(N.DV, []) == [])
kiem("chưa chọn loại → nói ra", N.thieu_ho_so("", hs(N.DKKD)) == ["Chưa chọn loại nhà cung cấp"])
p = N.pkn_con_han(hs(N.PKN, het=date(2026, 12, 31)) + hs(N.PKN, het=date(2026, 9, 1)), HOM_NAY)
kiem("phiếu kiểm nghiệm năm: lấy phiếu còn hạn", p and p["het_han"] == date(2026, 12, 31))
kiem("… hết hạn hết → None", N.pkn_con_han(hs(N.PKN, het=date(2026, 9, 1)), HOM_NAY) is None)

print("\n-- duyệt NCC trên Supplier (cả Desk) --")


class SupDoc(Doc):
    def is_new(self):
        return self["name"] not in SUPPLIER

    def has_value_changed(self, f):
        return (SUPPLIER.get(self["name"]) or {}).get(f) != self.get(f)


def sup(name, **k):
    return SupDoc(name=name, supplier_name=name, **k)


vai("Purchase User", u="mua@x")
d = sup("NCC-DX", custom_loai_ncc=N.TP, custom_nguon_goc=N.TRONG_NUOC, custom_ncc_duyet=1,
        custom_ho_so_ncc=hs(N.DKKD, N.ATTP, N.CONG_BO))
loi = thu(lambda: N.validate_supplier(d))
kiem("người mua hàng tự tích 'Đã duyệt' → chặn", loi and "Ban ISO" in loi, loi or "")
vai("ISO Manager")
d = sup("NCC-DX", custom_loai_ncc=N.TP, custom_nguon_goc=N.TRONG_NUOC, custom_ncc_duyet=1,
        custom_ho_so_ncc=hs(N.DKKD))
loi = thu(lambda: N.validate_supplier(d))
kiem("Ban ISO duyệt khi hồ sơ thiếu → chặn, liệt kê", loi and "ATTP" in loi and N.CONG_BO in loi, loi or "")
d["custom_ho_so_ncc"] = hs(N.DKKD, N.ATTP, N.CONG_BO, N.PKN)
d["custom_ho_so_ncc"][3]["het_han"] = date(2026, 12, 31)
kiem("đủ hồ sơ → duyệt, ghi ngày + người", thu(lambda: N.validate_supplier(d)) is None
     and (d["custom_ngay_duyet_ncc"], d["custom_duyet_ncc_boi"]) == (HOM_NAY, "iso@x"))
SUPPLIER["NCC-DX"] = dict(d)
HO_SO[:] = [dict(r, parent="NCC-DX", parenttype="Supplier") for r in d["custom_ho_so_ncc"]]
BAO.clear()
d2 = sup("NCC-DX", **{k: v for k, v in d.items() if k not in ("name", "supplier_name")})
d2["custom_ho_so_ncc"] = hs(N.DKKD)
kiem("NCC đã duyệt bị sửa thiếu hồ sơ → không tự bỏ duyệt, nhưng CẢNH BÁO",
     thu(lambda: N.validate_supplier(d2)) is None and any("thiếu" in b for b in BAO))
vai("Purchase User", u="mua@x")
d3 = sup("NCC-DX", **{k: v for k, v in d.items() if k not in ("name", "supplier_name")})
d3["custom_ncc_duyet"] = 0
kiem("người mua tự bỏ duyệt → chặn", thu(lambda: N.validate_supplier(d3)) is not None)
vai("ISO Manager")
kiem("Ban ISO bỏ duyệt → được, xoá ngày duyệt", thu(lambda: N.validate_supplier(d3)) is None
     and d3["custom_ngay_duyet_ncc"] is None)

print("\n-- mua hàng: chỉ CẢNH BÁO --")
SUPPLIER.update({
    "NCC-NK": {"name": "NCC-NK", "custom_loai_ncc": N.TP, "custom_nguon_goc": N.NHAP_KHAU, "custom_ncc_duyet": 0},
    "NCC-CAT": {"name": "NCC-CAT", "custom_loai_ncc": N.CAT, "custom_nguon_goc": N.TRONG_NUOC, "custom_ncc_duyet": 1},
    "NCC-DV": {"name": "NCC-DV", "custom_loai_ncc": N.DV, "custom_ncc_duyet": 0},
    "NCC-MOI": {"name": "NCC-MOI", "custom_loai_ncc": "", "custom_ncc_duyet": 0},
})
HO_SO += [{"parent": "NCC-CAT", "parenttype": "Supplier", "loai_ho_so": N.HOP_DONG},
          {"parent": "NCC-CAT", "parenttype": "Supplier", "loai_ho_so": N.DKKD}]


def mua(sup_, dt="Purchase Order"):
    BAO.clear()
    d = Doc(doctype=dt, supplier=sup_, supplier_name=sup_, transaction_date=str(HOM_NAY))
    loi = thu(lambda: N.canh_bao_mua(d))
    return loi, " ".join(BAO)


loi, bao = mua("NCC-NK")
kiem("NCC chưa duyệt → cảnh báo, KHÔNG chặn", loi is None and "CHƯA được duyệt" in bao, bao)
kiem("NCC chưa phân loại → cảnh báo", "chưa phân loại" in mua("NCC-MOI")[1])
kiem("NCC đã duyệt, đủ hồ sơ → im", mua("NCC-DX")[1] == "" and mua("NCC-CAT")[1] == "")
kiem("NCC dịch vụ → không xét", mua("NCC-DV")[1] == "")
HO_SO[3]["het_han"] = date(2026, 9, 30)          # PKN hết hạn không làm thiếu bộ hồ sơ TP
HO_SO[0]["het_han"] = date(2026, 9, 30)          # ĐKKD hết hạn → thiếu
kiem("đã duyệt nhưng giấy hết hạn → cảnh báo", "hết hạn" in mua("NCC-DX", "Purchase Invoice")[1])
HO_SO[0]["het_han"] = None
HO_SO[3]["het_han"] = date(2026, 12, 31)

# ═══ 2. Tiếp nhận BM.07.03 trên phiếu nhập mua (W10) ════════════════════════
print("\n-- tiếp nhận trên phiếu nhập mua: giấy tờ theo nguồn --")


def dong(item="DX-01", **kw):
    d = Doc({"idx": kw.pop("idx", 1), "item_code": item, "item_name": item, "qty": 100, "uom": "kg",
             "warehouse": "Kho NVL - RV"})
    for k, v in kw.items():
        d[f"custom_{k}" if k not in ("batch_no",) else k] = v
    return d


def phieu(sup_, *ds, dt="Purchase Receipt", **k):
    return Doc({"doctype": dt, "name": "PR-0001", "supplier": sup_, "posting_date": "2026-10-08",
                "items": list(ds), **k})


def nhan(p):
    BAO.clear()
    T.validate(p)
    return p["items"]


r = nhan(phieu("NCC-NK", dong(coa_vi_sinh="Không", ket_luan="Đạt", cam_quan_dat="Đạt")))[0]
kiem("NHẬP KHẨU không COA lô → ép Cách ly + nhập kho cách ly",
     r["custom_ket_luan"] == "Cách ly" and r["warehouse"] == "Kho cách ly - RV", (r["custom_ket_luan"], r["warehouse"]))
kiem("… ô Giấy tờ lô ghi rõ, và BÁO cho người lập", "COA lô: KHÔNG" in r["custom_giay_to"]
     and any("nhập khẩu phải có COA" in b for b in BAO))
r = nhan(phieu("NCC-NK", dong(coa_vi_sinh="Có", ket_luan="Đạt", cam_quan_dat="Đạt")))[0]
kiem("nhập khẩu có COA lô → giữ Đạt, kho NVL", (r["custom_ket_luan"], r["warehouse"]) == ("Đạt", "Kho NVL - RV")
     and "COA lô: có" in r["custom_giay_to"])
r = nhan(phieu("NCC-DX", dong(coa_vi_sinh="Không", ket_luan="Đạt", cam_quan_dat="Đạt")))[0]
kiem("trong nước có phiếu kiểm nghiệm năm còn hạn → Đạt, ghi số + hạn PKN",
     r["custom_ket_luan"] == "Đạt" and "kiểm nghiệm năm 4/2026" in r["custom_giay_to"] and "31/12/2026" in r["custom_giay_to"],
     r["custom_giay_to"])
HO_SO[3]["het_han"] = date(2026, 9, 30)
r = nhan(phieu("NCC-DX", dong(coa_vi_sinh="Không", ket_luan="Đạt", cam_quan_dat="Đạt")))[0]
kiem("trong nước, PKN năm HẾT HẠN, lô không COA → Cách ly", r["custom_ket_luan"] == "Cách ly"
     and "THIẾU phiếu kiểm nghiệm" in r["custom_giay_to"])
r = nhan(phieu("NCC-DX", dong(coa_vi_sinh="Có", ket_luan="Đạt", cam_quan_dat="Đạt")))[0]
kiem("… có COA lô thay cho PKN năm → Đạt", r["custom_ket_luan"] == "Đạt")
HO_SO[3]["het_han"] = date(2026, 12, 31)
r = nhan(phieu("NCC-CAT", dong("CAT-01", coa_vi_sinh="Không", ket_luan="Đạt", cam_quan_dat="Đạt")))[0]
kiem("CÁT RANG: không đòi COA / giấy tờ thực phẩm", r["custom_ket_luan"] == "Đạt"
     and "không yêu cầu giấy tờ" in r["custom_giay_to"])
r = nhan(phieu("NCC-NK", dong(coa_vi_sinh="Không", ket_luan="Không đạt", cam_quan_dat="Không đạt")))[0]
kiem("đã Không đạt thì giữ Không đạt (không hạ xuống Cách ly), vẫn vào kho cách ly",
     (r["custom_ket_luan"], r["warehouse"]) == ("Không đạt", "Kho cách ly - RV"))

print("\n-- aflatoxin --")
CAI_DAT_QC["nhom_can_aflatoxin"] = [Doc(item_group="Lạc nhân")]
r = nhan(phieu("NCC-DX", dong("LAC-01", coa_vi_sinh="Có", aflatoxin="Không", ket_luan="Đạt", cam_quan_dat="Đạt")))[0]
kiem("nhóm cần aflatoxin mà không có kết quả → Cách ly", r["custom_ket_luan"] == "Cách ly"
     and "Aflatoxin: Không" in r["custom_giay_to"])
r = nhan(phieu("NCC-DX", dong("LAC-01", coa_vi_sinh="Có", aflatoxin="Có", ket_luan="Đạt", cam_quan_dat="Đạt")))[0]
kiem("có kết quả aflatoxin → Đạt", r["custom_ket_luan"] == "Đạt")
r = nhan(phieu("NCC-DX", dong("DX-01", coa_vi_sinh="Có", ket_luan="Đạt", cam_quan_dat="Đạt")))[0]
kiem("nhóm không khai cần aflatoxin → không đòi", r["custom_ket_luan"] == "Đạt" and "Aflatoxin" not in r["custom_giay_to"])
CAI_DAT_QC.clear()
r = nhan(phieu("NCC-DX", dong("LAC-01", coa_vi_sinh="Có", aflatoxin="Không", ket_luan="Đạt", cam_quan_dat="Đạt")))[0]
kiem("chưa khai nhóm nào → luật aflatoxin không chạy (không đoán)", r["custom_ket_luan"] == "Đạt")

print("\n-- đường đi: kho cách ly, trả hàng, hoá đơn không trừ kho --")
SX_SET["kho_cach_ly"] = None
p = phieu("NCC-NK", dong(coa_vi_sinh="Không", ket_luan="Đạt", cam_quan_dat="Đạt"))
nhan(p)
kiem("chưa khai kho cách ly → vẫn Cách ly + báo đang nhập chung kho",
     p["items"][0]["warehouse"] == "Kho NVL - RV" and any("Chưa khai Kho cách ly" in b for b in BAO))
SX_SET["kho_cach_ly"] = "Kho cách ly - RV"
p = phieu("NCC-NK", dong(coa_vi_sinh="Không", ket_luan="Đạt", cam_quan_dat="Đạt"), is_return=1)
nhan(p)
kiem("phiếu TRẢ HÀNG cho NCC → không áp luật tiếp nhận mới", p["items"][0]["warehouse"] == "Kho NVL - RV"
     and not p["items"][0].get("custom_giay_to"))
p = phieu("NCC-NK", dong(coa_vi_sinh="Không", ket_luan="Đạt", cam_quan_dat="Đạt"), dt="Purchase Invoice", update_stock=0)
nhan(p)
kiem("hoá đơn mua KHÔNG trừ kho (lập sau phiếu nhập) → không đổi kho", p["items"][0]["warehouse"] == "Kho NVL - RV")
p = phieu("NCC-NK", dong(coa_vi_sinh="Không", ket_luan="Đạt", cam_quan_dat="Đạt"), dt="Purchase Invoice", update_stock=1)
nhan(p)
kiem("hoá đơn mua CÓ trừ kho (đường cũ) → kiểm như phiếu nhập", p["items"][0]["custom_ket_luan"] == "Cách ly"
     and p["items"][0]["warehouse"] == "Kho cách ly - RV")

print("\n-- duyệt phiếu nhập: NCC thực phẩm phải kiểm mọi dòng --")
DA_TAO.clear()
p = phieu("NCC-DX", dong("DX-01", idx=1), dong("LAC-01", idx=2, ket_luan="Đạt", ncc_lo="L-1"))
loi = thu(lambda: T.on_submit(p))
kiem("NCC thực phẩm: dòng chưa kiểm tiếp nhận → chặn duyệt", loi and "1 (DX-01)" in loi, loi or "")
p = phieu("NCC-MOI", dong("DX-01", idx=1))
kiem("NCC chưa phân loại: dòng không kiểm → qua (giai đoạn chuyển tiếp)", thu(lambda: T.on_submit(p)) is None)
p = phieu("NCC-NK", dong("DX-01", idx=1, ket_luan="Cách ly", ncc_lo="NK-9", batch_no="DX-NK-9", do_am=12.5))
T.on_submit(p)
kiem("lô Cách ly → phiếu sự cố gắn đúng lô NCC (W11)", len(DA_TAO) == 1 and DA_TAO[0]["nguon"] == "Tiếp nhận NL"
     and [x["batch"] for x in DA_TAO[0].get("ds_lo", [])] == ["DX-NK-9"])

# ═══ 3. Danh sách NCC được duyệt + cấu hình ═══════════════════════════════
print("\n-- danh sách BM.07.02, cấu hình --")
ds = {x["ncc"]: x for x in A.ds_ncc()}
kiem("danh sách: NCC đã phân loại, trạng thái + hồ sơ thiếu + PKN",
     set(ds) == {"NCC-DX", "NCC-NK", "NCC-CAT", "NCC-DV"} and ds["NCC-NK"]["duyet"] is False
     and ds["NCC-NK"]["thieu"] and "4/2026" in ds["NCC-DX"]["pkn"], sorted(ds))
if jinja2:
    html = A.in_ds_ncc()
    chu = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", html.split("</style>")[1]))
    kiem("bản in BM.07.02: tiêu đề, NCC chưa duyệt in đậm chữ CHƯA, chỗ ký",
         "BM.07.02" in chu and "CHƯA duyệt" in chu and "Trưởng Ban ISO" in chu, chu[:200])
vai("SX QC", u="qc@x")
kiem("QC xem được danh sách, KHÔNG in bản ký (việc của Ban ISO)", thu(lambda: A.ds_ncc()) is None
     and thu(lambda: A.in_ds_ncc()) is not None)
cf = {(f["dt"], f["fieldname"]): f for f in json.load(open("sx/fixtures/custom_field.json", encoding="utf-8"))}
kiem("Supplier: loại, nguồn, đã duyệt, hồ sơ (bảng SX Ho So NCC)",
     cf[("Supplier", "custom_loai_ncc")]["options"].split("\n")[1:] == list(N.LOAI)
     and cf[("Supplier", "custom_nguon_goc")]["options"].split("\n")[1:] == [N.TRONG_NUOC, N.NHAP_KHAU]
     and cf[("Supplier", "custom_ho_so_ncc")]["options"] == "SX Ho So NCC")
hs_j = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_ho_so_ncc/sx_ho_so_ncc.json", encoding="utf-8"))["fields"]}
kiem("loại hồ sơ trong DocType khớp hằng số code",
     set(hs_j["loai_ho_so"]["options"].split("\n")) >= {N.DKKD, N.ATTP, N.HACCP, N.CONG_BO, N.PKN, N.PKN_BB, N.HOP_DONG})
kiem("Purchase Receipt có đủ ô QC tiếp nhận như hoá đơn mua + ô giấy tờ lô",
     all(("Purchase Receipt Item", f) in cf for f in ("custom_ncc_lo", "custom_coa_vi_sinh", "custom_aflatoxin",
                                                       "custom_do_am", "custom_ket_luan", "custom_giay_to"))
     and ("Purchase Receipt", "custom_nguoi_kiem") in cf)
hk = open("sx/hooks.py", encoding="utf-8").read()
kiem("hook: Purchase Receipt kiểm tiếp nhận + cảnh báo NCC; Supplier.validate; Purchase Order cảnh báo",
     '"Purchase Receipt": {' in hk and '"Supplier": {"validate": "sx.qc.ncc.validate_supplier"}' in hk
     and '"Purchase Order": {"validate": "sx.qc.ncc.canh_bao_mua"}' in hk and hk.count("sx.qc.ncc.canh_bao_mua") == 3)
st = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_qc_setting/sx_qc_setting.json", encoding="utf-8"))["fields"]}
kiem("SX QC Setting: nhóm hàng cần aflatoxin", st["nhom_can_aflatoxin"]["fieldtype"] == "Table MultiSelect")
kiem("màn Xem xét có nút in BM.07.02", "sx.api.qc_ncc.in_ds_ncc" in open("sx/public/sx/views/qc_review.js", encoding="utf-8").read())

print(f"\n{'NCC-OK' if not hong else f'NCC-FAIL ({hong})'}")
sys.exit(1 if hong else 0)
