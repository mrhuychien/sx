"""D130 (W04) — danh mục công đoạn sửa được, đổi tên lan sang phiếu sự cố cũ.

Hỏng theo hướng nguy hiểm:
  · Ô công đoạn đổi sang Link mà danh mục thiếu một tên đang có trên phiếu cũ →
    phiếu đó không lưu lại được nữa ("Could not find Công đoạn").
  · Ban ISO đổi tên công đoạn cho khớp QT.08 → vòng kiểm vẫn sinh sự cố với TÊN
    CŨ (không còn trong danh mục) — lỗi lúc hoàn tất lượt giữa xưởng.
  · Bảng gốc trong muc.py và bảng chép trong patch lệch nhau.

Nạp sx/qc/muc.py, su_co.py, patch d130, controller THẬT; frappe giả.
Chạy: python3 scripts/test-congdoan.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class D(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


CD = {}           # name -> D(ten, day_chuyen, thu_tu, ma, ngung, ten_cu)
SU_CO_CU = ["3 Rang", "PRP", "Hỏng máy chuyền (gõ tay)", ""]
TAO = []


class Doc(D):
    def insert(self, **k):
        if self.get("doctype") == "SX QC Cong Doan":
            CD[self["ten"]] = D(self, name=self["ten"], ngung=0)
        else:
            TAO.append(self)
            self["name"] = f"SC-{len(TAO)}"
        return self

    def set(self, k, v):
        self[k] = v

    def append(self, k, v):
        self.setdefault(k, []).append(D(v))


def exists(dt, f=None):
    if dt != "SX QC Cong Doan":
        return False
    if isinstance(f, dict):
        return any(all(x.get(k) == v for k, v in f.items()) for x in CD.values())
    return f in CD


def get_value(dt, f, fld=None, **k):
    if dt == "SX QC Cong Doan":
        x = next((x for x in CD.values() if all(x.get(a) == b for a, b in f.items())), None) \
            if isinstance(f, dict) else CD.get(f)
        return x.get(fld) if x else None
    return None


def get_all(dt, filters=None, fields=None, **k):
    if dt == "SX QC Cong Doan":
        return [D(x) for x in CD.values() if not x.get("ngung")]
    return []


frappe = types.ModuleType("frappe")
frappe.get_doc = lambda d, n=None: Doc(d)
frappe.get_all = get_all
frappe.throw = lambda m, *a, **k: (_ for _ in ()).throw(Exception(m))
frappe.session = types.SimpleNamespace(user="iso@x")
frappe.db = types.SimpleNamespace(
    exists=exists, get_value=get_value, table_exists=lambda dt: True,
    sql_list=lambda q, *a: [x for x in SU_CO_CU if x],
    set_value=lambda dt, n, f, v=None, **k: CD[n].update({f: v}))
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: float(v or 0)
fu.now_datetime = lambda: __import__("datetime").datetime(2026, 10, 8, 9, 30)
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu
fm = types.ModuleType("frappe.model"); fm.__path__ = []
fd = types.ModuleType("frappe.model.document"); fd.Document = D
sys.modules["frappe.model"] = fm
sys.modules["frappe.model.document"] = fd
for g in ("sx", "sx.qc", "sx.patches"):
    m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m


def nap(ten, p):
    sp = importlib.util.spec_from_file_location(ten, p)
    mo = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mo
    sp.loader.exec_module(mo)
    return mo


M = nap("sx.qc.muc", "sx/qc/muc.py")
nap("sx.qc.nguong", "sx/qc/nguong.py")
nap("sx.qc.quyen", "sx/qc/quyen.py")
frappe.get_cached_doc = lambda dt: D()
SC = nap("sx.qc.su_co", "sx/qc/su_co.py")
P = nap("sx.patches.d130_cong_doan", "sx/patches/d130_cong_doan.py")
C = nap("sx.qc.doctype.sx_qc_cong_doan.sx_qc_cong_doan",
        "sx/qc/doctype/sx_qc_cong_doan/sx_qc_cong_doan.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


print("-- bảng gốc --")
kiem("mọi mục kiểm trỏ tới công đoạn có MÃ",
     all(m["cd"] in M.MA_CONG_DOAN for m in M.MUC),
     [m["f"] for m in M.MUC if m["cd"] not in M.MA_CONG_DOAN])
kiem("bảng chép trong patch khớp muc.CONG_DOAN_GOC", P.GOC == M.CONG_DOAN_GOC)
kiem("mã không trùng", len({t[0] for t in M.CONG_DOAN_GOC}) == len(M.CONG_DOAN_GOC))
kiem("bánh đủ 16 công đoạn", sum(1 for t in M.CONG_DOAN_GOC if t[2] == "Bánh") == 16)
kiem("tên gốc = các lựa chọn của ô Select cũ (phiếu cũ trỏ đúng sau khi thành Link)",
     M.CONG_DOAN == [t[1] for t in M.CONG_DOAN_GOC])

print("\n-- patch: tạo danh mục, không để phiếu cũ trỏ vào hư không --")
P.execute()
kiem("tạo đủ 24 công đoạn gốc + 1 giá trị lạ trên phiếu cũ", len(CD) == 25, len(CD))
kiem("giá trị lạ trên phiếu cũ được tạo (dây chuyền Chung, không mã)",
     CD.get("Hỏng máy chuyền (gõ tay)", {}).get("day_chuyen") == "Chung"
     and not CD["Hỏng máy chuyền (gõ tay)"].get("ma"))
kiem("tên trùng ô cũ của phiếu sự cố", "3 Rang" in CD and CD["3 Rang"]["ma"] == "3")
P.execute()
kiem("chạy lại không nhân đôi", len(CD) == 25)

print("\n-- đổi tên: vòng kiểm vẫn gắn đúng công đoạn --")
kiem("chưa đổi tên → giữ tên gốc", SC.ten_cong_doan("3 Rang") == "3 Rang")
cu = CD.pop("3 Rang")
CD["3 Rang đỗ"] = D(cu, name="3 Rang đỗ", ten="3 Rang đỗ")      # = Rename trên Desk
kiem("Ban ISO đổi '3 Rang' → '3 Rang đỗ': sự cố mới mang tên mới (tra theo mã)",
     SC.ten_cong_doan("3 Rang") == "3 Rang đỗ")
d = Doc(name="QC-1", ngay="2026-10-08", luot="Đầu sáng", phien_ban=2, rang_nhiet_do=235)
SC.tao_tu_vong_kiem(d)
kiem("phiếu sự cố tự sinh ghi tên công đoạn hiện tại",
     [x["cong_doan"] for x in TAO] == ["3 Rang đỗ"], [x.get("cong_doan") for x in TAO])
kiem("tên không có trong bảng gốc → giữ nguyên", SC.ten_cong_doan("Lạ") == "Lạ")
r = C.SXQCCongDoan(name="3 Rang đỗ", ten="3 Rang đỗ")
C.SXQCCongDoan.after_rename(r, "3 Rang", "3 Rang đỗ")
kiem("đổi tên ghi lịch sử (tên cũ → mới, ai)",
     "3 Rang → 3 Rang đỗ (iso@x" in (CD["3 Rang đỗ"].get("ten_cu") or ""))

print("\n-- danh sách chọn khi ghi sự cố --")
Q = types.SimpleNamespace()
src = open("sx/api/qc.py", encoding="utf-8").read()
i = src.index("def _ds_cong_doan():")
j = src.index("\n\n\n", i)
ns = {"frappe": frappe, "cint": fu.cint, "M": M}
exec(src[i:j], ns)   # noqa: S102 — chạy đúng hàm thật
CD["10 Ủ sau trộn"]["ngung"] = 1
ds = ns["_ds_cong_doan"]()
kiem("bánh trước, bột sau, PRP / Chung cuối", ds[0].startswith("1 ") and ds.index("Bột: tiếp nhận")
     > ds.index("16 Lưu kho thành phẩm") and ds.index("PRP") > ds.index("Bột: đóng thùng"), ds[:3])
kiem("công đoạn đã ngừng không hiện để chọn", "10 Ủ sau trộn" not in ds)
CD.clear()
kiem("chưa có danh mục → dùng bảng gốc", ns["_ds_cong_doan"]() == M.CONG_DOAN)

print("\n-- DocType --")
jd = json.load(open("sx/qc/doctype/sx_qc_cong_doan/sx_qc_cong_doan.json", encoding="utf-8"))
f = {x["fieldname"]: x for x in jd["fields"]}
kiem("đổi tên được (allow_rename) và tên là khoá (field:ten)",
     jd.get("allow_rename") == 1 and jd.get("autoname") == "field:ten")
kiem("mã chỉ đặt một lần, không trùng", f["ma"].get("set_only_once") == 1 and f["ma"].get("unique") == 1)
kiem("Ban ISO sửa được", any(p["role"] == "ISO Manager" and p.get("write") for p in jd["permissions"]))
sc = {x["fieldname"]: x for x in json.load(open(
    "sx/qc/doctype/sx_su_co/sx_su_co.json", encoding="utf-8"))["fields"]}
kiem("phiếu sự cố: công đoạn là Link tới danh mục (Rename lan sang phiếu cũ)",
     sc["cong_doan"]["fieldtype"] == "Link" and sc["cong_doan"]["options"] == "SX QC Cong Doan")
kiem("patch có trong patches.txt", "sx.patches.d130_cong_doan" in open("sx/patches.txt").read())

print()
if hong:
    print(f"CONGDOAN-HỎNG ({hong})")
    sys.exit(1)
print("CONGDOAN-OK")
