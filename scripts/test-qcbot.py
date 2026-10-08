"""D98 — "Hôm nay có sản xuất bột": bật lên phải DÍNH, và lượt đang dở phải nhận được.

Hai lỗi thật đã có trước D98, cả hai đều im lặng:

  1. Nút trên màn Hôm nay chỉ đổi một biến trong trình duyệt. Server suy "có bột"
     từ việc đã có lượt nào bật bột chưa — đầu ngày chưa có lượt nào thì bật lên
     không lưu vào đâu cả; mở lượt khác hay tải lại trang là nút tự về KHÔNG.
  2. Lượt đã mở thì không có chỗ nào bật bột. Dây chuyền bột chạy từ 10h mà lượt
     Trưa mở lúc 9h là mất hẳn phần B của lượt đó.

Nạp sx/api/qc.py THẬT với frappe giả có bảng SX QC Round và SX QC Ngay.
Chạy: python3 scripts/test-qcbot.py   (verify.sh gọi sẵn)
"""

import importlib.util
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

LUOT = []          # SX QC Round
NGAY = []          # SX QC Ngay
VAI = {"SX QC"}
DA_LUU = []


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v

    def save(self):
        DA_LUU.append(self["name"])
        return self

    def insert(self, **kw):
        if self.get("doctype") == "SX QC Ngay":
            self["name"] = f"N{len(NGAY) + 1}"
            NGAY.append(self)
        else:
            self["name"] = f"QC-{len(LUOT) + 1:04d}"
            LUOT.append(self)
        return self


def _bang(dt):
    return {"SX QC Round": LUOT, "SX QC Ngay": NGAY}.get(dt, [])


def _khop(h, f):
    for k, v in (f or {}).items():
        x = h.get(k)
        if isinstance(v, tuple):
            op, m = v
            if op == "<" and not (x or 0) < m:
                return False
            if op == "in" and x not in m:
                return False
        elif x != v:
            return False
    return True


def get_all(dt, filters=None, fields=None, pluck=None, limit=None, **k):
    ra = [Doc(h) for h in _bang(dt) if _khop(h, filters)]
    if limit:
        ra = ra[:limit]
    return [h.get(pluck) for h in ra] if pluck else ra


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
frappe.session = types.SimpleNamespace(user="qc@x")
frappe.get_roles = lambda u=None: list(VAI)
frappe.get_all = get_all
frappe.get_doc = lambda x, n=None: (Doc(x) if isinstance(x, dict)
                                    else next(h for h in _bang(x) if h["name"] == n))
frappe.get_cached_doc = lambda dt: None
frappe.db = types.SimpleNamespace(
    get_value=lambda dt, f, fld=None, **k: next(
        (h.get(fld) for h in _bang(dt) if _khop(h, f)), None),
    set_value=lambda dt, n, vals, **k: next(
        h for h in _bang(dt) if h["name"] == n).update(vals),
)
frappe.__dict__["_"] = lambda s: s
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
fu.flt = lambda v, p=None: float(v or 0)
from datetime import date as _date  # noqa: E402


class Ngay(_date):
    """date so sánh được với chuỗi 'YYYY-MM-DD' — bảng giả lưu ngày dạng chuỗi."""
    def __eq__(self, o):
        return str(self) == str(o)[:10]

    def __ne__(self, o):
        return not self.__eq__(o)

    __hash__ = _date.__hash__


def _getdate(x=None):
    y, m, d = map(int, str(x or "2026-09-28")[:10].split("-"))
    return Ngay(y, m, d)


fu.getdate = _getdate
fu.nowdate = lambda: "2026-09-28"
fu.add_days = lambda d, n: d
fu.get_datetime = lambda x=None: x
fu.now_datetime = lambda: "2026-09-28 10:00:00"
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
nap("sx.qc.nguong", "sx/qc/nguong.py")
nap("sx.qc.quyen", "sx/qc/quyen.py")
nap("sx.qc.san_pham", "sx/qc/san_pham.py")
nap("sx.qc.su_co", "sx/qc/su_co.py")
nap("sx.qc.xuat", "sx/qc/xuat.py")
nap("sx.qc.nhac", "sx/qc/nhac.py")
Q = nap("sx.api.qc", "sx/api/qc.py")
# chi_tiet_round đọc cả trăm thứ không liên quan tới bài này — thay bằng bản gọn.
Q.chi_tiet_round = lambda name: {"name": name, "co_san_xuat_bot": next(
    h for h in LUOT if h["name"] == name)["co_san_xuat_bot"]}

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


def lam_sach():
    LUOT.clear(); NGAY.clear(); DA_LUU.clear()
    VAI.clear(); VAI.add("SX QC")


def luot(luot_, docstatus=0, bot=0, **kw):
    d = Doc({"doctype": "SX QC Round", "ngay": "2026-09-28", "luot": luot_,
             "docstatus": docstatus, "co_san_xuat_bot": bot, "qc_user": "qc@x", **kw})
    return d.insert()


def co_bot_hom_nay():
    return Q.get_today("2026-09-28")["co_san_xuat_bot"]


# ═══ 1. Hàm thuần ════════════════════════════════════════════════════════
print("-- cờ bột là chuyện của NGÀY --")
kiem("có bản ghi ngày thì bản ghi quyết định (tắt vẫn là tắt dù lượt cũ có bột)",
     M.co_bot_ngay(0, [{"co_san_xuat_bot": 1}]) == 0)
kiem("chưa có bản ghi (ngày trước D98) thì suy từ các lượt như cũ",
     M.co_bot_ngay(None, [{"co_san_xuat_bot": 1}]) == 1
     and M.co_bot_ngay(None, []) == 0)
kiem("đếm đúng mục bột đã ghi (bỏ qua ô đo = 0 là chưa đo)",
     [m["f"] for m in M.muc_bot_da_ghi({"b1_lac_sach": "Đạt", "b2_rang_lac_nhiet": 0,
                                        "luoc_soi_du": "Đạt"})] == ["b1_lac_sach"])

# ═══ 2. Lỗi 1: bật đầu ngày phải DÍNH ════════════════════════════════════
print("\n-- lỗi 1: bật lúc đầu ngày, chưa có lượt nào --")
lam_sach()
kiem("ban đầu: KHÔNG", co_bot_hom_nay() == 0)
Q.dat_co_bot("2026-09-28", 1)
kiem("bật xong, hỏi lại server (như tải lại trang) → vẫn CÓ", co_bot_hom_nay() == 1)
kiem("lưu vào bản ghi cấp ngày, ghi ai bật",
     len(NGAY) == 1 and NGAY[0]["cap_nhat_boi"] == "qc@x")
r = Q.start_round("2026-09-28", "Đầu sáng")
kiem("mở lượt SAU khi bật mà không gửi cờ → lượt có phần bột (server lấy theo ngày)",
     LUOT[-1]["co_san_xuat_bot"] == 1)
Q.dat_co_bot("2026-09-28", 1)
kiem("bật lần hai không đẻ bản ghi ngày thứ hai", len(NGAY) == 1)

# ═══ 3. Lỗi 2: lượt đang dở phải nhận được bột ═══════════════════════════
print("\n-- lỗi 2: lượt đã mở rồi mới bắt đầu làm bột --")
lam_sach()
xong = luot("Đầu sáng", docstatus=1)
dang = luot("Trưa")
Q.dat_co_bot("2026-09-28", 1)
kiem("bật ở màn Hôm nay → lượt ĐANG DỞ có phần bột", dang["co_san_xuat_bot"] == 1)
kiem("và được save (để tính lại 'đã chấm x / y')", dang["name"] in DA_LUU)
kiem("lượt ĐÃ HOÀN TẤT giữ nguyên (8h chưa làm bột là đúng sự thật)",
     xong["co_san_xuat_bot"] == 0 and xong["name"] not in DA_LUU)

lam_sach()
dang = luot("Trưa")
# Ngày ĐÃ CÓ bản ghi "không bột" (sáng tắt). Không có dòng này thì server tự suy
# cờ ngày từ lượt vừa bật, và bài kiểm vẫn xanh cả khi code quên bật cờ ngày.
Q._ghi_co_bot_ngay("2026-09-28", 0)
Q.doi_co_bot_luot(dang["name"], 1)
kiem("bật NGAY TRONG màn lượt → lượt đó có phần bột", dang["co_san_xuat_bot"] == 1)
kiem("…và cờ của NGÀY bật theo (lượt sau trong ngày cũng có bột)", co_bot_hom_nay() == 1)

# ═══ 4. Tắt: phải hỏi nếu đã ghi mục bột ═════════════════════════════════
print("\n-- tắt bột khi đã ghi mục bột --")
lam_sach()
dang = luot("Trưa", bot=1, b1_lac_sach="Đạt")
Q._ghi_co_bot_ngay("2026-09-28", 1)
kq = Q.dat_co_bot("2026-09-28", 0)
kiem("tắt cả ngày → KHÔNG đổi gì, hỏi lại trước", kq.get("can_xac_nhan")
     and dang["co_san_xuat_bot"] == 1 and co_bot_hom_nay() == 1)
kiem("và nói rõ mục nào sắp bị giấu",
     kq["luot"][0]["muc"] and kq["luot"][0]["muc"][0].startswith("B1"), str(kq))
Q.dat_co_bot("2026-09-28", 0, ep=1)
kiem("xác nhận rồi → tắt", dang["co_san_xuat_bot"] == 0 and co_bot_hom_nay() == 0)
kiem("giá trị đã ghi KHÔNG bị xoá (bật lại là thấy)", dang["b1_lac_sach"] == "Đạt")

lam_sach()
dang = luot("Trưa", bot=1, b1_lac_sach="Đạt")
Q._ghi_co_bot_ngay("2026-09-28", 1)
kq = Q.doi_co_bot_luot(dang["name"], 0)
kiem("tắt trong màn lượt khi đã ghi mục bột → hỏi lại", kq.get("can_xac_nhan")
     and dang["co_san_xuat_bot"] == 1)
Q.doi_co_bot_luot(dang["name"], 0, ep=1)
kiem("xác nhận → chỉ lượt này tắt, cờ NGÀY giữ nguyên (lượt sau có thể chạy lại bột)",
     dang["co_san_xuat_bot"] == 0 and co_bot_hom_nay() == 1)

lam_sach()
dang = luot("Trưa", bot=1)
Q.doi_co_bot_luot(dang["name"], 0)
kiem("chưa ghi mục bột nào → tắt luôn, không hỏi", dang["co_san_xuat_bot"] == 0)

# ═══ 5. Quyền ════════════════════════════════════════════════════════════
print("\n-- ai được bật --")
lam_sach()
VAI.clear(); VAI.add("ISO Manager")
try:
    Q.dat_co_bot("2026-09-28", 1)
    kiem("Ban ISO không bật được (người xem xét không ghi)", False)
except Loi:
    kiem("Ban ISO không bật được (người xem xét không ghi)", True)
kiem("và không để lại bản ghi ngày nào", not NGAY)

# ═══ 6. Màn hình nối đúng dây ════════════════════════════════════════════
# Lỗi 1 gốc là nút CHỈ đổi biến trong trình duyệt. Chốt rằng nó gọi server.
print("\n-- màn hình gọi server, không chỉ đổi biến --")
home = open("sx/public/sx/views/qc_home.js", encoding="utf-8").read()
tron = open("sx/public/sx/views/qc_round.js", encoding="utf-8").read()
kiem("nút ở màn Hôm nay gọi sx.api.qc.dat_co_bot", "sx.api.qc.dat_co_bot" in home)
kiem("không còn giữ cờ bột trong biến cục bộ st.co_bot", "st.co_bot" not in home)
kiem("màn lượt có nút gọi sx.api.qc.doi_co_bot_luot", "sx.api.qc.doi_co_bot_luot" in tron)
kiem("màn lượt gửi nốt số đang gõ trước khi đổi bột (đổi bột là tải lại lượt)",
     tron.index("await gui();") < tron.index("sx.api.qc.doi_co_bot_luot"))

print("QCBOT-FAIL ({} ca)".format(hong) if hong else "QCBOT-OK")
sys.exit(1 if hong else 0)
