"""D87: gộp sự cố tổ Ghi sổ vào sổ chung SX Su Co — chuyển đúng, chạy lại an toàn.

Vì sao phải có bài này: đây là thay đổi đụng vào LUỒNG ĐANG CHẠY THẬT. Tổ Ghi
sổ bấm "+ Ghi sự cố" mỗi ca; hỏng ở đây thì hoặc sự cố không được ghi (im lặng,
vì màn hình vẫn hiện toast "Đã ghi"), hoặc patch chạy lại lúc migrate và nhân
đôi cả sổ — mà sổ nhân đôi thì không ai phát hiện bằng mắt.

Chốt bốn thứ:
  1. ghi_su_co đẻ ra SX Su Co, KHÔNG ghi vào bảng con cũ nữa.
  2. Dữ liệu trả về cho màn hình giữ nguyên hình dạng cũ (card suco.js không đổi).
  3. Patch chuyển đủ dòng, đúng ngày của phiếu, và mang khoá để nhận ra.
  4. Chạy patch lần thứ hai KHÔNG đẻ thêm bản ghi nào.

Chạy: python3 scripts/test-sucogop.py   (verify.sh gọi sẵn)
"""

import importlib.util
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

BANG = {"SX Su Co": [], "SX Su Co Item": [], "SX Ngay San Xuat": []}
IN_RA = []


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v

    def get(self, k, d=None):
        return dict.get(self, k, d)

    def append(self, k, v):
        self.setdefault(k, []).append(Doc(v))
        return self[k][-1]

    def insert(self, **kw):
        dt = self["doctype"]
        self["name"] = f'{dt[:6]}-{len(BANG[dt]) + 1:04d}'
        self["creation"] = "2026-09-14 08:00:00"
        BANG[dt].append(self)
        return self

    def save(self):
        return self


def _khop(h, filters):
    for truong, dk in (filters or {}).items():
        v = h.get(truong)
        if isinstance(dk, (list, tuple)):
            toan, moc = dk
            if toan == "in" and v not in moc:
                return False
            if toan == "is" and (moc == "set") != bool(v):
                return False
        elif v != dk:
            return False
    return True


def get_all(dt, filters=None, fields=None, pluck=None, order_by=None, **k):
    ra = [Doc(h) for h in BANG.get(dt, []) if _khop(h, filters)]
    if pluck:
        return [h.get(pluck) for h in ra]
    return ra


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.get_all = get_all
frappe.get_doc = lambda d: (Doc(d) if isinstance(d, dict)
                            else next(Doc(x) for x in BANG["SX Ngay San Xuat"]
                                      if x["name"] == d))
frappe.__dict__["_"] = lambda s: s
frappe.db = types.SimpleNamespace(
    table_exists=lambda t: t in BANG,
    commit=lambda: None,
    get_value=lambda dt, ten, truong=None, as_dict=False: _get_value(dt, ten, truong, as_dict),
)
frappe.utils = types.ModuleType("frappe.utils")
frappe.utils.cint = lambda v: int(float(v or 0))
frappe.utils.flt = lambda v, p=None: float(v or 0)
frappe.utils.now = lambda: "2026-09-14 08:00:00"
frappe.session = types.SimpleNamespace(user="ghiso@rvhg.vn")
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = frappe.utils


def _get_value(dt, ten, truong, as_dict):
    hang = next((h for h in BANG.get(dt, [])
                 if h["name"] == (ten if isinstance(ten, str) else None)), None)
    if not hang:
        return None
    if as_dict:
        return Doc({t: hang.get(t) for t in truong})
    if isinstance(truong, (list, tuple)):
        return [hang.get(t) for t in truong]
    return hang.get(truong)


def nap(ten, duong_dan, goi=()):
    for g in goi:
        if g not in sys.modules:
            m = types.ModuleType(g)
            m.__path__ = []
            sys.modules[g] = m
    sp = importlib.util.spec_from_file_location(ten, duong_dan)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mod
    sp.loader.exec_module(mod)
    return mod


# portal.py kéo theo cả app — chỉ cần hai hàm nên nạp riêng chúng bằng exec.
import ast  # noqa: E402

src = open("sx/api/portal.py", encoding="utf-8").read()
cay = ast.parse(src)
lay = {"ghi_su_co", "su_co_cua_ngay"}
than = ast.Module(body=[n for n in cay.body
                        if isinstance(n, ast.FunctionDef) and n.name in lay],
                  type_ignores=[])
ns = {"frappe": frappe, "cint": frappe.utils.cint, "_": lambda s: s,
      "guard_card": lambda c: None}
exec(compile(than, "portal", "exec"), ns)          # noqa: S102
P = types.SimpleNamespace(**ns)

PATCH = nap("sx.patches.d87_gop_su_co", "sx/patches/d87_gop_su_co.py",
            ("sx", "sx.patches"))

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


BANG["SX Ngay San Xuat"] = [
    {"name": "SXN-2026-09-12-01", "ngay": "2026-09-12", "docstatus": 0, "su_co": []},
    {"name": "SXN-2026-09-13-01", "ngay": "2026-09-13", "docstatus": 1, "su_co": []},
]

# ═══ 1. Ghi sự cố mới ════════════════════════════════════════════════════
print("-- tổ Ghi sổ bấm '+ Ghi sự cố' --")
kq = P.ghi_su_co("SXN-2026-09-12-01", "Mất điện", "mất 40 phút cả xưởng", 40)
kiem("đẻ ra bản ghi trong sổ chung", len(BANG["SX Su Co"]) == 1)
sc = BANG["SX Su Co"][0]
kiem("nguồn = Nhật ký chuyền", sc["nguon"] == "Nhật ký chuyền", str(sc.get("nguon")))
kiem("giữ loại của tổ Ghi sổ", sc["loai_chuyen"] == "Mất điện")
kiem("giữ số phút dừng chuyền", sc["phut_dung"] == 40)
kiem("lấy NGÀY của phiếu, không phải hôm nay", sc["ngay"] == "2026-09-12",
     str(sc.get("ngay")))
kiem("nối về phiếu ngày", sc["ngay_san_xuat"] == "SXN-2026-09-12-01")
kiem("mở sẵn, chờ người xử lý", sc["trang_thai"] == "Mở")
kiem("KHÔNG ghi vào bảng con cũ nữa", not BANG["SX Su Co Item"])

# ═══ 2. Hình dạng dữ liệu cho màn hình không đổi ══════════════════════════
print("\n-- card suco.js đọc được y như trước --")
ds = P.su_co_cua_ngay("SXN-2026-09-12-01")
kiem("trả đúng 1 dòng", len(ds) == 1)
kiem("có đủ loai / mo_ta / phut_dung (card đang đọc ba ô này)",
     set(ds[0]) >= {"loai", "mo_ta", "phut_dung", "thoi_diem"}, str(sorted(ds[0])))
kiem("loai hiển thị là loại của tổ Ghi sổ", ds[0]["loai"] == "Mất điện")
kiem("ngày khác thì không lẫn sang", not P.su_co_cua_ngay("SXN-2026-09-13-01"))

# ═══ 3. Phiếu ngày đã chốt thì chặn ══════════════════════════════════════
print("\n-- phiếu ngày đã chốt --")
try:
    P.ghi_su_co("SXN-2026-09-13-01", "Hỏng máy", "", 0)
    kiem("chặn ghi vào phiếu đã chốt", False)
except Loi as e:
    kiem("chặn ghi vào phiếu đã chốt", "đã chốt" in str(e), str(e))
kiem("và không để lại bản ghi rác", len(BANG["SX Su Co"]) == 1)

# ═══ 4. Patch chuyển dữ liệu cũ ══════════════════════════════════════════
print("\n-- patch chuyển bảng con cũ sang --")
BANG["SX Su Co Item"] = [
    {"name": "i1", "parent": "SXN-2026-09-12-01", "idx": 1,
     "parenttype": "SX Ngay San Xuat", "thoi_diem": "2026-09-12 09:00:00",
     "loai": "Hỏng máy", "mo_ta": "kẹt băng tải", "phut_dung": 15},
    {"name": "i2", "parent": "SXN-2026-09-13-01", "idx": 1,
     "parenttype": "SX Ngay San Xuat", "thoi_diem": "2026-09-13 10:00:00",
     "loai": "Thiếu NVL", "mo_ta": "", "phut_dung": 0},
    {"name": "i3", "parent": "SXN-DA-XOA", "idx": 1,
     "parenttype": "SX Ngay San Xuat", "thoi_diem": "2026-09-01 10:00:00",
     "loai": "Khác", "mo_ta": "phiếu ngày đã bị xoá", "phut_dung": 5},
]
PATCH.execute()
moi = [x for x in BANG["SX Su Co"] if x.get("khoa_cu")]
kiem("chuyển 2 dòng có phiếu ngày còn sống", len(moi) == 2, str(len(moi)))
kiem("BỎ QUA dòng mất phiếu ngày, không bịa ngày hôm nay",
     not any(x.get("khoa_cu", "").startswith("SXN-DA-XOA") for x in moi))
kiem("mỗi dòng mang khoá <phiếu>#<idx>",
     sorted(x["khoa_cu"] for x in moi)
     == ["SXN-2026-09-12-01#1", "SXN-2026-09-13-01#1"])
kiem("lấy đúng ngày của phiếu, không phải ngày chạy patch",
     {x["khoa_cu"]: x["ngay"] for x in moi}
     == {"SXN-2026-09-12-01#1": "2026-09-12", "SXN-2026-09-13-01#1": "2026-09-13"})
kiem("mô tả rỗng vẫn có nội dung (mo_ta là reqd)",
     all((x["mo_ta"] or "").strip() for x in moi),
     str([x["mo_ta"] for x in moi]))
kiem("đóng sẵn — sổ mới không mở ra đã đầy phiếu quá hạn",
     all(x["trang_thai"] == "Đóng" for x in moi))
kiem("không đụng tới sự cố ghi mới hôm nay",
     BANG["SX Su Co"][0]["trang_thai"] == "Mở")

# ═══ 5. Chạy lại patch ═══════════════════════════════════════════════════
print("\n-- migrate chạy lại lần nữa (chuyện bình thường) --")
truoc = len(BANG["SX Su Co"])
PATCH.execute()
PATCH.execute()
kiem("chạy thêm hai lần vẫn đúng ngần ấy bản ghi",
     len(BANG["SX Su Co"]) == truoc, f"{truoc} → {len(BANG['SX Su Co'])}")

print("\n-- dữ liệu gốc --")
kiem("bảng con cũ KHÔNG bị xoá (còn để đối chiếu)",
     len(BANG["SX Su Co Item"]) == 3)

print("SUCOGOP-FAIL ({} ca)".format(hong) if hong else "SUCOGOP-OK")
sys.exit(1 if hong else 0)
