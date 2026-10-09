"""D142 (W16) — nhiệt độ, vòng quay theo máy rang M1 / M2 / M3, nhiệt độ hàn theo máy gói bột.

Vì sao phải có bài này:
  · Ba máy rang gộp chung thì một lồng quay chậm cả tháng vẫn nằm lọt trong trung bình —
    Ban ISO phải thấy TỪNG máy.
  · Máy đã tắt (số máy trên phiếu giảm) còn để lại số cũ trong DB; bước Rang nghỉ; hôm không
    làm bột — những số đó lọt vào thống kê là thống kê nói dối.
  · Đổi mã máy là đổi NHÃN: fieldname phải giữ nguyên (phiếu cũ đọc nguyên), nhãn trên Desk
    phải khớp nhãn trên màn hình / tờ in.
  · Truy vấn đòi một field không có trên SX QC Round → màn Xem xét chết trên site thật.

Nạp sx/qc/muc.py, sx/qc/so_do.py, sx/api/qc.py THẬT; frappe giả.
Chạy: python3 scripts/test-somay.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import sys
import types
from datetime import date, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

HOM_NAY = date(2026, 10, 8)
TRA_VE = {"rounds": []}


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None, **k: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.session = types.SimpleNamespace(user="qc@x")
frappe.get_roles = lambda u=None: ["SX QC"]
frappe.get_all = lambda dt, **k: [Doc(x) for x in TRA_VE["rounds"]] if dt == "SX QC Round" else []
frappe.get_cached_doc = lambda dt, *a: Doc()
frappe.db = types.SimpleNamespace(get_value=lambda *a, **k: None, exists=lambda *a, **k: None)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: round(float(v or 0), p) if p is not None else float(v or 0)
fu.getdate = lambda x=None: (x if isinstance(x, date) else date.fromisoformat(str(x)[:10]) if x else HOM_NAY)
fu.nowdate = lambda: str(HOM_NAY)
fu.add_days = lambda d, n: fu.getdate(d) + timedelta(days=n)
fu.add_months = lambda d, n: fu.getdate(d)
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


M = nap("sx.qc.muc", "sx/qc/muc.py")
NG = nap("sx.qc.nguong", "sx/qc/nguong.py")
nap("sx.qc.quyen", "sx/qc/quyen.py")
for t in ("san_pham", "su_co", "xuat", "nhac"):
    nap(f"sx.qc.{t}", f"sx/qc/{t}.py")
nap("sx.qc.dong_vat", "sx/qc/dong_vat.py")
nap("sx.qc.cat", "sx/qc/cat.py")
SD = nap("sx.qc.so_do", "sx/qc/so_do.py")
nap("sx.qc.thiet_bi", "sx/qc/thiet_bi.py")
nap("sx.qc.kiem_nghiem", "sx/qc/kiem_nghiem.py")
nap("sx.qc.viec_dinh_ky", "sx/qc/viec_dinh_ky.py")
nap("sx.qc.khac_phuc", "sx/qc/khac_phuc.py")
nap("sx.qc.vai_u", "sx/qc/vai_u.py")
Q = nap("sx.api.qc", "sx/api/qc.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


# ═══ 1. Mã máy: chỉ đổi nhãn ═══════════════════════════════════════════════
print("\n-- mã máy: máy rang M1–M3, máy gói bột chờ C10 --")
kiem("máy rang M1 / M2 / M3; máy nghiền M1 / M2 (W02) giữ nguyên",
     [M.ten_may_so("rang", k) for k in (1, 2, 3)] == ["M1", "M2", "M3"]
     and [M.ten_may_so("nghien", k) for k in (1, 2)] == ["M1", "M2"])
kiem("máy gói bột chưa có mã (C10) → 'máy k'", M.ten_may_so("goi_bot", 2) == "máy 2")
kiem("fieldname không đổi: máy 1 = field gốc, máy 2/3 = _m2/_m3",
     all(f in M.THEO_F for f in ("rang_nhiet_do", "rang_nhiet_do_m2", "rang_vong_quay_m3", "b8_nhiet_han_m3")))
kiem("nhãn ô máy 2/3: 'Nhiệt độ rang — M2', 'Máy đóng gói: nhiệt độ hàn — máy 2'",
     M.THEO_F["rang_nhiet_do_m2"]["nhan"].endswith("— M2") and M.THEO_F["rang_vong_quay_m3"]["nhan"].endswith("— M3")
     and M.THEO_F["b8_nhiet_han_m2"]["nhan"].endswith("— máy 2"))
dj = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_qc_round/sx_qc_round.json", encoding="utf-8"))["fields"]}
lech = [m["f"] for m in M.MUC if m.get("may_so", 1) > 1 and not (dj.get(m["f"], {}).get("label") or "").endswith(m["nhan"])]
kiem("nhãn trên Desk (JSON SX QC Round) khớp nhãn mục — đã chạy lại gen-qc-doctype.py", not lech, lech)
thieu = [f for f in SD.can_lay() if f not in dj and f not in ("name", "ngay")]
kiem("mọi field bảng số đo đọc đều CÓ trên SX QC Round (thiếu một field là màn Xem xét chết)", not thieu, thieu)

# ═══ 2. Tổng hợp theo máy ═════════════════════════════════════════════════
print("\n-- tổng hợp số đo theo máy (hàm thuần) --")
R = [
    {"luot": "Đầu sáng", "so_may_rang": 2, "rang_nhiet_do": 260, "rang_vong_quay": 6.5, "rang_nhiet_do_m2": 235,
     "rang_vong_quay_m2": 7.4, "rang_nhiet_do_m3": 300, "co_san_xuat_bot": 1, "so_may_goi_bot": 2,
     "b8_nhiet_han": 170, "b8_nhiet_han_m2": 195},
    {"luot": "Trưa", "so_may_rang": 3, "rang_nhiet_do": 265, "rang_vong_quay": 0, "rang_nhiet_do_m2": 258,
     "rang_nhiet_do_m3": 285, "rang_vong_quay_m3": 6.6, "co_san_xuat_bot": 0, "b8_nhiet_han": 120},
    {"luot": "Cuối chiều", "so_may_rang": 1, "buoc_nghi": "3", "rang_nhiet_do": 100},
]
ng = NG.MAC_DINH
kq = SD.tong_hop(R, ng)
bang = {(x["ten_may"], x["f"]): (x["so_lan"], x["thap"], x["cao"], x["duoi"], x["tren"]) for x in kq}
kiem("mỗi (máy, số đo) một dòng, đúng thứ tự máy rang M1 → M3 rồi máy gói bột",
     [(x["ten_may"], x["f"]) for x in kq] == [
         ("Máy rang đỗ M1", "rang_nhiet_do"), ("Máy rang đỗ M1", "rang_vong_quay"),
         ("Máy rang đỗ M2", "rang_nhiet_do"), ("Máy rang đỗ M2", "rang_vong_quay"),
         ("Máy rang đỗ M3", "rang_nhiet_do"), ("Máy rang đỗ M3", "rang_vong_quay"),
         ("Máy đóng gói bột 1", "b8_nhiet_han"), ("Máy đóng gói bột 2", "b8_nhiet_han")], [(x["ten_may"], x["f"]) for x in kq])
kiem("M1: hai lần đo nhiệt độ (260, 265); bước Rang nghỉ → số 100 không tính",
     bang[("Máy rang đỗ M1", "rang_nhiet_do")] == (2, 260, 265, 0, 0), bang[("Máy rang đỗ M1", "rang_nhiet_do")])
kiem("vòng quay 0 = chưa ghi, không tính", bang[("Máy rang đỗ M1", "rang_vong_quay")] == (1, 6.5, 6.5, 0, 0))
kiem("M2: 235 °C dưới ngưỡng 240 → 1 lần dưới; vòng quay 7,4 > 7,0 → 1 lần trên",
     bang[("Máy rang đỗ M2", "rang_nhiet_do")] == (2, 235, 258, 1, 0)
     and bang[("Máy rang đỗ M2", "rang_vong_quay")] == (1, 7.4, 7.4, 0, 1))
kiem("M3: lượt chỉ chạy 2 máy → số 300 cũ của M3 KHÔNG tính; 285 > trần vận hành 280 → 1 lần trên",
     bang[("Máy rang đỗ M3", "rang_nhiet_do")] == (1, 285, 285, 0, 1), bang[("Máy rang đỗ M3", "rang_nhiet_do")])
kiem("máy gói bột: hôm không làm bột → số hàn 120 không tính; máy 2 195 > 190 → 1 lần trên",
     bang[("Máy đóng gói bột 1", "b8_nhiet_han")] == (1, 170, 170, 0, 0)
     and bang[("Máy đóng gói bột 2", "b8_nhiet_han")] == (1, 195, 195, 0, 1))
kiem("ngưỡng lấy từ SX QC Setting (truyền vào), có đơn vị",
     next(x for x in kq if x["f"] == "rang_vong_quay")["lo"] == 6.2 and kq[0]["dv"] == "°C")
kiem("không có lượt nào → bảng rỗng", SD.tong_hop([], ng) == [])
b = SD.tong_hop([{"luot": "Trưa", "so_may_rang": 1, "rang_nhiet_do": 240, "rang_vong_quay": 7.0},
                 {"luot": "Trưa", "so_may_rang": 1, "rang_nhiet_do": 280, "rang_vong_quay": 6.2}], ng)
kiem("đúng bằng ngưỡng (240, 280, 6,2, 7,0) không phải ngoài ngưỡng — W37 rang đỗ 240–280 °C",
     all(x["duoi"] == 0 and x["tren"] == 0 for x in b) and len(b) == 2, b)
kiem("chỉ đọc các field can_lay() là đủ — ra y hệt khi có đủ mọi field (số máy, bước nghỉ, có bột…)",
     SD.tong_hop([{k: r.get(k) for k in SD.can_lay()} for r in R], ng) == kq)

# ═══ 3. API: lượt trước theo máy, dashboard ═════════════════════════════════
print("\n-- lượt trước theo máy, bảng trên màn Xem xét --")
TRA_VE["rounds"] = [{"name": "QC-1", "ngay": "2026-10-07", "luot": "Cuối chiều", "so_may_rang": 2,
                     "rang_nhiet_do": 262, "rang_vong_quay": 6.6, "rang_nhiet_do_m2": 258, "rang_vong_quay_m2": 6.9,
                     "rang_nhiet_do_m3": 300}]
t = Q._truoc_do(Doc({"name": "QC-2", "ngay": "2026-10-08"}))
kiem("lượt trước: từng máy rang đang chạy ở lượt đó (M1, M2 — không M3 đã tắt)",
     t["may"] == [{"may": "M1", "nhiet": 262, "vong": 6.6}, {"may": "M2", "nhiet": 258, "vong": 6.9}], t.get("may"))
qcpy = open("sx/api/qc.py", encoding="utf-8").read()
kiem("dashboard trả so_do_may từ lượt đã hoàn tất, đúng bộ field", '"so_do_may": _so_do.tong_hop(' in qcpy
     and "fields=_so_do.can_lay()" in qcpy)
rv = open("sx/public/sx/views/qc_review.js", encoding="utf-8").read()
kiem("màn Xem xét: bảng Số đo theo máy (máy, số đo, lần, thấp–cao, ngoài ngưỡng tô đỏ)",
     "kpi.so_do_may" in rv and "x.ten_may" in rv and "sx-qc-o-loi" in rv)
rj = open("sx/public/sx/views/qc_round.js", encoding="utf-8").read()
kiem("màn lượt: dòng 'Lượt trước' theo từng máy", "t.may" in rj and "x.may" in rj)

print(f"\n{'SOMAY-OK' if not hong else f'SOMAY-FAIL ({hong})'}")
sys.exit(1 if hong else 0)
