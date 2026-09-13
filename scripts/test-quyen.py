"""Ma trận QUYỀN: mỗi role vào được màn nào, gọi được method nào (D82).

Vì sao phải có bài này: phân quyền hỏng KHÔNG hiện ra như một lỗi. Nới nhầm thì mọi
thứ vẫn chạy — chỉ là QC bấm được nút duyệt phiếu của chính mình, và không ai biết
cho tới lúc đối chiếu kho. Siết nhầm thì QC đứng giữa xưởng bấm mãi không được.

Chốt ba thứ:
  1. Mỗi role thấy đúng những màn/card của nó (sx/config/roles.py).
  2. MỌI method whitelist đều có chốt quyền — thêm một method quên guard_card là
     mở một cửa hậu, mà cửa đó im lặng.
  3. Quyền DUYỆT phiếu nhập kho tách khỏi quyền LẬP: người lập không tự duyệt được
     phiếu của mình — cả giá trị của bước kiểm đếm nằm ở chỗ đó.

Chạy: python3 scripts/test-quyen.py   (verify.sh gọi sẵn)
"""

import ast
import importlib.util
import os
import pathlib
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

VAI = {}    # role của "user" đang giả lập

frappe = types.ModuleType("frappe")
frappe.get_roles = lambda u=None: list(VAI)
frappe.throw = lambda msg, *a, **k: (_ for _ in ()).throw(PermissionError(msg))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = PermissionError
frappe.get_all = lambda *a, **k: []
frappe.db = types.SimpleNamespace(get_value=lambda *a, **k: None,
                                  get_single_value=lambda *a, **k: None)
frappe.get_meta = lambda dt: types.SimpleNamespace(get_field=lambda f: True,
                                                   has_field=lambda f: True)
frappe.session = types.SimpleNamespace(user="ai@do.com")
frappe.utils = types.ModuleType("frappe.utils")
for ten, ham in [("cint", lambda v: int(v or 0)), ("flt", lambda v, p=None: float(v or 0)),
                 ("get_datetime", lambda x=None: x), ("now_datetime", lambda: None),
                 ("format_datetime", lambda *a: ""), ("get_time", lambda x=None: x),
                 ("time_diff_in_seconds", lambda a, b: 0),
                 ("getdate", lambda x=None: x), ("nowdate", lambda: "2026-09-10"),
                 ("add_days", lambda d, n: d), ("now_datetime", lambda: None),
                 ("get_url", lambda: "https://x"), ("formatdate", lambda d: str(d))]:
    setattr(frappe.utils, ten, ham)
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = frappe.utils
frappe.__dict__["_"] = lambda s: s

sx = types.ModuleType("sx")
sx.__path__ = []
sys.modules["sx"] = sx
cfg = types.ModuleType("sx.config")
cfg.__path__ = []
sys.modules["sx.config"] = cfg
spec = importlib.util.spec_from_file_location("sx.config.roles", "sx/config/roles.py")
R = importlib.util.module_from_spec(spec)
sys.modules["sx.config.roles"] = R
spec.loader.exec_module(R)

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


def nhu_la(*roles):
    VAI.clear()
    VAI.update({r: 1 for r in roles})


def goi_duoc(card):
    try:
        R.guard_card(card)
        return True
    except PermissionError:
        return False


# ── 1. QC: đúng những gì đã chốt ────────────────────────────────────────
print("-- QC (SX Vao Hop): vào dữ liệu Ghi hộp + tạo phiếu nhập kho nháp --")
nhu_la(R.VAO_HOP)
kiem("thấy màn Ghi hộp", "vaohop" in R.allowed_views())
kiem("thấy màn Nhập kho", "nhapkho" in R.allowed_views())
kiem("KHÔNG thấy màn Ghi sổ", "ghiso" not in R.allowed_views())
kiem("KHÔNG thấy màn Quản lý", "quanly" not in R.allowed_views())
kiem("không phải super role", not R.is_super())

kiem("gọi được API ghi hộp", goi_duoc("vaohop"))
kiem("gọi được API phiếu nhập kho", goi_duoc("nhapkhotp"))
for card, viec in [("chotngay", "chốt ngày"), ("quanly", "dashboard quản lý"),
                   ("nguoidung", "tạo tài khoản"), ("luutrinhbtp", "lưu đồ tồn BTP"),
                   ("xuatdau", "xuất đậu"), ("baome", "báo mẻ"), ("baocan", "báo cán"),
                   ("suco", "báo sự cố")]:
    kiem(f"KHÔNG gọi được {viec}", not goi_duoc(card))

card_qc = R.view_cards().get("vaohop", []) + R.view_cards().get("nhapkho", [])
kiem("card trên hai màn của QC đúng như khai — chỉ chấm hộp + phiếu nhập kho",
     sorted(card_qc) == ["nhapkhotp", "vaohop"], str(sorted(card_qc)))

# ── 2. Các role khác không lấn sân ──────────────────────────────────────
print("\n-- role khác --")
nhu_la(R.GHI_SO)
kiem("Ghi sổ: không vào màn Ghi hộp", "vaohop" not in R.allowed_views())
kiem("Ghi sổ: không lập được phiếu nhập kho", not goi_duoc("nhapkhotp"))
kiem("Ghi sổ: không chốt ngày được", not goi_duoc("chotngay"))
kiem("Ghi sổ: VẪN báo được sự cố", goi_duoc("suco"))
kiem("Ghi sổ: card sự cố vẫn trên màn của mình",
     "suco" in R.view_cards().get("ghiso", []))

nhu_la(R.THU_KHO)
kiem("Thủ kho: chỉ thấy màn Nhập kho", R.allowed_views() == ["nhapkho"],
     str(R.allowed_views()))
kiem("Thủ kho: không ghi hộp được", not goi_duoc("vaohop"))
kiem("Thủ kho: không tạo tài khoản được", not goi_duoc("nguoidung"))

nhu_la(R.QUAN_LY)
kiem("Quản lý: thấy mọi màn", R.allowed_views() == R.MOI_VIEW, str(R.allowed_views()))
kiem("Quản lý: tạo tài khoản được", goi_duoc("nguoidung"))

# ── QC chế biến (module qc) — KHÔNG lấn sang mấy màn nhập liệu cũ ──────
print("\n-- module QC: 4 vai, và chỗ khác nhau giữa chúng --")
for vai, ten in [(R.QC, "QC chế biến"), (R.QC_GOI, "QC đóng gói"),
                 (R.ISO, "Ban ISO"), (R.QLSX, "QLSX")]:
    nhu_la(vai)
    kiem(f"{ten}: thấy đúng màn QC", R.allowed_views() == ["qc"],
         str(R.allowed_views()))
    kiem(f"{ten}: không vào được màn nhập liệu cũ",
         not any(goi_duoc(c) for c in ["vaohop", "nhapkhotp", "chotngay",
                                       "nguoidung", "baome"]))
    kiem(f"{ten}: không phải super role", not R.is_super())

nhu_la()
kiem("không role nào: không vào được màn nào", R.allowed_views() == [])
kiem("không role nào: không gọi được gì", not any(
    goi_duoc(c) for c in ["vaohop", "nhapkhotp", "chotngay", "nguoidung"]))

# ── 3. Duyệt phiếu tách khỏi lập phiếu ──────────────────────────────────
print("\n-- duyệt phiếu nhập kho: người lập KHÔNG tự duyệt --")
ut = types.ModuleType("sx.utils")
for ten in ("get_settings", "items_tp", "nhom_tp", "get_bom_active", "cho_phep_ton_am",
            "sinh_ma_lo"):
    setattr(ut, ten, lambda *a, **k: None)
sys.modules["sx.utils"] = ut
api = types.ModuleType("sx.api")
api.__path__ = []
sys.modules["sx.api"] = api
sp = importlib.util.spec_from_file_location("sx.api.khotp", "sx/api/khotp.py")
K = importlib.util.module_from_spec(sp)
sys.modules["sx.api.khotp"] = K
sp.loader.exec_module(K)

nhu_la(R.VAO_HOP)
kiem("QC KHÔNG được duyệt", not K._duoc_duyet())
nhu_la(R.THU_KHO)
kiem("Thủ kho được duyệt", K._duoc_duyet())
nhu_la(R.QUAN_LY)
kiem("Quản lý được duyệt", K._duoc_duyet())
nhu_la(R.GHI_SO)
kiem("Ghi sổ KHÔNG được duyệt", not K._duoc_duyet())

# ── 4. Mọi method whitelist đều có chốt ─────────────────────────────────
print("\n-- không có cửa hậu: mọi method whitelist đều chốt quyền --")
# Module qc không import sx/config/roles.py (để tách thành app riêng được) nên
# nó có bộ chốt riêng. Vẫn phải có chốt — chỉ là tên khác.
CHOT = {"guard_card", "_kiem_quyen", "_any_sx_guard",
        "_guard_qc", "_guard_ghi", "_guard_manager"}
ho = []
tong = 0


def _goi_trong(fn):
    return {getattr(c.func, "id", "") or getattr(c.func, "attr", "")
            for c in ast.walk(fn) if isinstance(c, ast.Call)}


for p in sorted(pathlib.Path("sx/api").glob("*.py")):
    cay = ast.parse(p.read_text(encoding="utf-8"))
    ham = [n for n in cay.body if isinstance(n, ast.FunctionDef)]
    # Chốt gián tiếp cũng là chốt: `_lay_round()` gọi `_guard_ghi()` bên trong
    # nên method nào đi qua nó là đã chốt. Chỉ nhận ĐÚNG MỘT tầng — sâu hơn thì
    # đọc code không còn thấy ngay cửa khoá ở đâu, mà đó mới là thứ cần thấy.
    chot_giap = {f.name for f in ham if _goi_trong(f) & CHOT}
    for fn in ham:
        if not any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "whitelist"
                   for d in fn.decorator_list):
            continue
        tong += 1
        if not (_goi_trong(fn) & (CHOT | chot_giap)):
            ho.append(f"{p.name}:{fn.name}")
kiem(f"cả {tong} method đều có chốt quyền", not ho, ", ".join(ho) or "không có cửa hậu")

# Trang www mặc định là CHO KHÁCH VÀO. Trang nào không tự đá Guest sang /login thì
# nội dung của nó công khai với cả internet — /vao là trang DUY NHẤT cố ý như vậy
# (nó phải nhận được người chưa đăng nhập, đó là việc của nó).
CONG_KHAI = {"vao.py"}
ho_hang = []
for p in sorted(pathlib.Path("sx/www").glob("*.py")):
    src = p.read_text(encoding="utf-8")
    da_chan = 'session.user == "Guest"' in src or "session.user == 'Guest'" in src
    if not da_chan and p.name not in CONG_KHAI:
        ho_hang.append(p.name)
kiem("chỉ /vao là trang không chặn khách",
     not ho_hang, ", ".join(ho_hang) or f"công khai đúng {sorted(CONG_KHAI)}")

# ── module qc: người ghi KHÔNG tự duyệt ───────────────────────────────
print("\n-- module QC: ba vai, ba quyền, và chỗ khác nhau là chỗ có giá trị --")
spq = importlib.util.spec_from_file_location("sx.api.qc", "sx/api/qc.py")
Q = importlib.util.module_from_spec(spq)
sys.modules["sx.api.qc"] = Q
sys.modules["sx.qc"] = types.ModuleType("sx.qc")
sys.modules["sx.qc"].__path__ = []
for ten_mod, ten_file in [("sx.qc.muc", "sx/qc/muc.py"),
                          ("sx.qc.nguong", "sx/qc/nguong.py"),
                          ("sx.qc.su_co", "sx/qc/su_co.py")]:
    sp2 = importlib.util.spec_from_file_location(ten_mod, ten_file)
    mod2 = importlib.util.module_from_spec(sp2)
    sys.modules[ten_mod] = mod2
    sp2.loader.exec_module(mod2)
spq.loader.exec_module(Q)


def qua(ham):
    try:
        ham()
        return True
    except PermissionError:
        return False


for vai, ten, vao, ghi, duyet in [
    (R.QC, "QC chế biến", True, True, False),
    (R.QC_GOI, "QC đóng gói", True, True, False),
    (R.QLSX, "QLSX", True, False, False),
    (R.ISO, "Ban ISO", True, False, True),
    (R.GHI_SO, "Ghi sổ (ngoài QC)", False, False, False),
    (R.VAO_HOP, "QC vào hộp (ngoài QC)", False, False, False),
]:
    nhu_la(vai)
    kiem(f"{ten}: vào phần QC = {vao}", qua(Q._guard_qc) is vao)
    kiem(f"{ten}: ghi vòng kiểm = {ghi}", qua(Q._guard_ghi) is ghi)
    kiem(f"{ten}: đóng sự cố / xem xét = {duyet}", qua(Q._guard_manager) is duyet)

kiem("tên role khai ở roles.py và api/qc.py khớp nhau",
     (Q.QC, Q.QC_GOI, Q.ISO, Q.QLSX) == (R.QC, R.QC_GOI, R.ISO, R.QLSX),
     f"{(Q.QC, Q.QC_GOI, Q.ISO, Q.QLSX)} vs {(R.QC, R.QC_GOI, R.ISO, R.QLSX)}")

print("QUYEN-FAIL ({} ca)".format(hong) if hong else "QUYEN-OK")
sys.exit(1 if hong else 0)
