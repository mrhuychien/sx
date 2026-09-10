"""Kiểm phần TẠO TÀI KHOẢN: chuẩn hoá số, sinh mật khẩu, và vòng đời mã QR (D81).

Vì sao phải có bài này: đây là màn duy nhất trong app CẤP QUYỀN cho người khác, và
mã QR trên thẻ là một thứ bearer credential — ai cầm tờ giấy là vào được. Hỏng ở đây
không hiện ra màn hình như một lỗi; nó hiện ra sáu tháng sau dưới dạng một tài khoản
không ai nhớ đã tạo.

Bốn thứ phải đúng, và cả bốn đều im lặng khi sai:
  · Cùng một người viết số kiểu nào cũng ra CÙNG một tài khoản (không thì hai tài
    khoản cho một người, mà lương thì tính theo tài khoản).
  · Mật khẩu đủ mạnh và không có ký tự dễ đọc nhầm khi chép tay.
  · Mã QR lưu BĂM, dùng MỘT lần, có hạn, huỷ được.
  · Không cấp được role ngoài danh sách của app này, không đụng được tài khoản của
    người ngoài app.

Chạy: python3 scripts/test-nguoidung.py   (verify.sh gọi sẵn)
"""

import datetime
import hashlib
import importlib.util
import os
import re
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


class D(dict):
    __getattr__ = dict.get


class Throw(Exception):
    pass


DB = {"User": [], "Has Role": [], "SX Ma Dang Nhap": []}
XOA = []


def _khop(row, f):
    for k, v in (f or {}).items():
        cur = row.get(k)
        if isinstance(v, (tuple, list)) and len(v) == 2:
            op, val = v
            if op == "in" and cur not in val:
                return False
            if op == "not in" and cur in val:
                return False
            if op == "like" and not re.fullmatch(val.replace("%", ".*"), str(cur or "")):
                return False
            if op == "is" and val == "not set" and cur:
                return False
            if op == "<" and not (cur is not None and cur < val):
                return False
        elif cur != v:
            return False
    return True


frappe = types.ModuleType("frappe")


def get_all(dt, filters=None, fields=None, pluck=None, **kw):
    rows = [r for r in DB.get(dt, []) if _khop(r, filters)]
    if pluck:
        return [r.get(pluck) for r in rows]
    return [D({k: r.get(k) for k in (fields or r.keys())}) for r in rows]


def get_value(dt, filters=None, fieldname=None, as_dict=False, **kw):
    if isinstance(filters, str):
        filters = {"name": filters}
    rows = get_all(dt, filters=filters)
    if not rows:
        return None
    if as_dict or isinstance(fieldname, (list, tuple)):
        return D({k: rows[0].get(k) for k in (fieldname or rows[0].keys())})
    return rows[0].get(fieldname)


def set_value(dt, name, field, val=None, **kw):
    for r in DB.get(dt, []):
        if r.get("name") == name:
            if isinstance(field, dict):
                r.update(field)
            else:
                r[field] = val


class Doc(D):
    """Giữ THAM CHIẾU tới hàng gốc: db_set trong Frappe ghi thẳng xuống DB, nên bản
    giả cũng phải ghi xuyên xuống, không thì test tưởng app không đánh dấu gì."""

    def __init__(s, d, goc=None):
        super().__init__(d)
        s._goc = goc
        s.flags = types.SimpleNamespace()

    def insert(s):
        dt = s["doctype"]
        s.setdefault("name", s.get("email") or f"{dt}-{len(DB.setdefault(dt, [])) + 1}")
        DB.setdefault(dt, []).append(s)
        for r in s.get("roles") or []:
            DB["Has Role"].append({"parent": s["name"], "role": r["role"]})
        return s

    def save(s):
        return s

    def db_set(s, f, v, **kw):
        s[f] = v
        if s._goc is not None:
            s._goc[f] = v


frappe.get_all = get_all
def _get_doc(x, n=None):
    if isinstance(x, dict):
        return Doc(x)
    goc = next(r for r in DB.get(x, []) if r.get("name") == n)
    return Doc(goc, goc)


frappe.get_doc = _get_doc
frappe.db = types.SimpleNamespace(
    get_value=get_value, set_value=set_value,
    exists=lambda dt, f=None: bool(get_value(dt, f, "name")),
    commit=lambda: None,
)
frappe.delete_doc = lambda dt, n, **kw: (
    XOA.append((dt, n)),
    DB.__setitem__(dt, [r for r in DB.get(dt, []) if r.get("name") != n]))
frappe.throw = lambda msg, *a, **k: (_ for _ in ()).throw(Throw(msg))
frappe.msgprint = lambda *a, **k: None
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.session = types.SimpleNamespace(user="quanly@x.com")
frappe.get_roles = lambda u=None: [r["role"] for r in DB["Has Role"] if r["parent"] == u]
frappe.get_meta = lambda dt: types.SimpleNamespace(has_field=lambda f: True)
frappe.get_cached_doc = lambda *a, **k: D({})
frappe.utils = types.ModuleType("frappe.utils")
frappe.utils.now_datetime = lambda: datetime.datetime(2026, 9, 10, 8, 0, 0)
frappe.utils.add_days = lambda d, n: d + datetime.timedelta(days=n)
frappe.utils.cint = lambda v: int(v) if str(v).strip().lstrip("-").isdigit() else 0
frappe.utils.get_url = lambda: "https://test.rongvanghoanggia.com"
frappe.utils.nowdate = lambda: "2026-09-10"
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = frappe.utils
frappe.__dict__["_"] = lambda s: s

sx = types.ModuleType("sx")
sx.__path__ = []
utils = types.ModuleType("sx.utils")
utils.get_settings = lambda: D({"ten_mien_user": ""})
cfg = types.ModuleType("sx.config")
cfg.__path__ = []
roles = types.ModuleType("sx.config.roles")
roles.QUAN_LY, roles.GHI_SO = "SX Quan Ly", "SX Ghi So"
roles.VAO_HOP, roles.THU_KHO = "SX Vao Hop", "SX Thu Kho"
roles.guard_card = lambda c: None
api = types.ModuleType("sx.api")
api.__path__ = []
for n, m in [("sx", sx), ("sx.utils", utils), ("sx.config", cfg),
             ("sx.config.roles", roles), ("sx.api", api)]:
    sys.modules[n] = m

spec = importlib.util.spec_from_file_location("sx.api.nguoidung", "sx/api/nguoidung.py")
nd = importlib.util.module_from_spec(spec)
sys.modules["sx.api.nguoidung"] = nd
spec.loader.exec_module(nd)

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


print("-- chuẩn hoá số điện thoại: một người = một tài khoản --")
for vao in ["0912345678", "+84912345678", "84912345678", "0912.345.678",
            " 0912 345 678 ", "0912-345-678"]:
    got = nd.chuan_sdt(vao)
    kiem(f"{vao!r}", got == "0912345678", f"ra {got}")
kiem("số máy bàn 11 chữ số vẫn nhận", nd.chuan_sdt("02838221234") == "02838221234")

print("\n-- số sai thì DỪNG, không tạo tài khoản rác --")
for xau in ["", "091234", "1912345678", "abcdefghij", "09123456789012", None]:
    try:
        nd.chuan_sdt(xau)
        kiem(f"{xau!r} phải bị chặn", False)
    except Throw:
        kiem(f"{xau!r} bị chặn", True)

print("\n-- mật khẩu: chép tay được, mà vẫn đủ mạnh --")
mks = [nd.mat_khau_moi() for _ in range(300)]
kiem("đủ dài", all(len(m) == 10 for m in mks))
kiem("luôn có chữ hoa, chữ thường và số",
     all(any(c.isupper() for c in m) and any(c.islower() for c in m)
         and any(c.isdigit() for c in m) for m in mks))
xau_de_nham = set("0Oo1lIi")
kiem("không có ký tự dễ đọc nhầm (0 O o 1 l I i)",
     all(not (set(m) & xau_de_nham) for m in mks),
     "lọt: " + "".join(sorted({c for m in mks for c in m if c in xau_de_nham}))
     if any(set(m) & xau_de_nham for m in mks) else "300 mật khẩu đều sạch")
kiem("không trùng nhau (ngẫu nhiên thật)", len(set(mks)) == len(mks))
kiem("không có ký tự đặc biệt", all(m.isalnum() for m in mks))

print("\n-- tạo tài khoản --")
r = nd.tao_user("+84 912 345 678", "Nguyễn Thị Nga", "SX Vao Hop")
kiem("số được chuẩn hoá", r["sdt"] == "0912345678")
kiem("username = số điện thoại",
     get_value("User", {"username": "0912345678"}, "name") is not None)
kiem("email ghép từ số + tên miền mặc định",
     r["user"] == "0912345678@sx.local", r["user"])
kiem("có role đã chọn",
     any(h["parent"] == r["user"] and h["role"] == "SX Vao Hop" for h in DB["Has Role"]))
kiem("trả về mật khẩu để in thẻ", bool(r.get("mat_khau")))
kiem("link QR trỏ đúng trang /vao", str(r["link"]).startswith(
    "https://test.rongvanghoanggia.com/vao?k="), r["link"])

print("\n-- mã QR: lưu BĂM, không lưu mã gốc --")
ma_goc = r["link"].split("k=")[1]
luu = DB["SX Ma Dang Nhap"][0]
kiem("bảng KHÔNG chứa mã gốc, chỉ chứa băm", ma_goc not in str(luu))
kiem("lưu đúng SHA-256 của mã",
     luu["ma_bam"] == hashlib.sha256(ma_goc.encode()).hexdigest())
kiem("mã đủ dài để không đoán được", len(ma_goc) >= 40, f"{len(ma_goc)} ký tự")

print("\n-- vòng đời mã: dùng một lần --")
u, ly = nd.doi_ma_lay_user(ma_goc)
kiem("lần đầu: vào được", u == r["user"] and ly == "", f"{u} / {ly}")
u2, ly2 = nd.doi_ma_lay_user(ma_goc)
kiem("lần hai: BỊ CHẶN, và nói rõ đã dùng", u2 is None and ly2 == "da_dung", ly2)
kiem("mã sai", nd.doi_ma_lay_user("khong-phai-ma-that")[1] == "sai")
kiem("mã rỗng", nd.doi_ma_lay_user("")[1] == "trong")

print("\n-- hết hạn --")
r2 = nd.cap_lai(r["user"])
ma2 = r2["link"].split("k=")[1]
for m in DB["SX Ma Dang Nhap"]:
    if m["ma_bam"] == hashlib.sha256(ma2.encode()).hexdigest():
        m["het_han"] = datetime.datetime(2026, 9, 9, 0, 0, 0)
kiem("mã quá hạn không vào được", nd.doi_ma_lay_user(ma2)[1] == "het_han")

print("\n-- cấp lại thì mã CŨ chết ngay --")
r3 = nd.cap_lai(r["user"])
ma3 = r3["link"].split("k=")[1]
r4 = nd.cap_lai(r["user"])
kiem("mã của lần cấp trước bị huỷ", nd.doi_ma_lay_user(ma3)[1] == "sai")
kiem("mã mới nhất dùng được", nd.doi_ma_lay_user(r4["link"].split("k=")[1])[1] == "")
kiem("cấp lại có đổi mật khẩu", bool(r4.get("mat_khau")))

print("\n-- tài khoản bị khoá thì mã cũng không vào được --")
r5 = nd.cap_lai(r["user"])
set_value("User", r["user"], "enabled", 0)
kiem("khoá -> chặn, nói rõ lý do", nd.doi_ma_lay_user(r5["link"].split("k=")[1])[1] == "khoa")
set_value("User", r["user"], "enabled", 1)

print("\n-- KHÔNG leo thang quyền --")
try:
    nd.tao_user("0987654321", "Kẻ gian", "System Manager")
    kiem("gán System Manager phải bị chặn", False)
except Throw as e:
    kiem("gán System Manager bị chặn", True, str(e)[:50])
try:
    nd.tao_user("0987654321", "Kẻ gian", "Administrator")
    kiem("gán Administrator phải bị chặn", False)
except Throw:
    kiem("gán Administrator bị chặn", True)

DB["User"].append({"name": "sep@congty.com", "full_name": "Sếp", "enabled": 1,
                   "user_type": "System User"})
DB["Has Role"].append({"parent": "sep@congty.com", "role": "System Manager"})
for ten, ham in [("cap_lai", lambda: nd.cap_lai("sep@congty.com")),
                 ("bat_tat", lambda: nd.bat_tat("sep@congty.com", 0))]:
    try:
        ham()
        kiem(f"{ten} lên tài khoản ngoài app phải bị chặn", False)
    except Throw as e:
        kiem(f"{ten} lên tài khoản ngoài app bị chặn", True, str(e)[:45])

DB["Has Role"].append({"parent": "sep@congty.com", "role": "SX Quan Ly"})
try:
    nd.cap_lai("sep@congty.com")
    kiem("có role SX nhưng KIÊM System Manager -> vẫn chặn", False)
except Throw:
    kiem("có role SX nhưng KIÊM System Manager -> vẫn chặn", True)

print("\n-- không tạo trùng số, không tự khoá mình --")
try:
    nd.tao_user("0912345678", "Người khác", "SX Ghi So")
    kiem("số đã có tài khoản phải bị chặn", False)
except Throw as e:
    kiem("số đã có tài khoản bị chặn", True, str(e)[:45])

frappe.session.user = r["user"]
DB["Has Role"].append({"parent": r["user"], "role": "SX Vao Hop"})
try:
    nd.bat_tat(r["user"], 0)
    kiem("tự khoá mình phải bị chặn", False)
except Throw:
    kiem("tự khoá mình bị chặn", True)
frappe.session.user = "quanly@x.com"

print("\n-- khoá thì huỷ luôn mã chưa dùng --")
nd.cap_lai(r["user"])
truoc = len([m for m in DB["SX Ma Dang Nhap"] if m["nguoi_dung"] == r["user"]])
nd.bat_tat(r["user"], 0)
sau = len([m for m in DB["SX Ma Dang Nhap"] if m["nguoi_dung"] == r["user"]])
kiem("mã bị xoá sạch khi khoá", truoc > 0 and sau == 0, f"{truoc} -> {sau}")

print("\n-- danh sách chỉ bày tài khoản CỦA APP --")
set_value("User", r["user"], "enabled", 1)
DB["User"].append({"name": "ngoai@congty.com", "full_name": "Người ngoài", "enabled": 1,
                   "user_type": "System User"})
ds = nd.danh_sach()["rows"]
ten_ds = {x["user"] for x in ds}
kiem("tài khoản QC có trong danh sách", r["user"] in ten_ds)
kiem("tài khoản không có role SX bị loại", "ngoai@congty.com" not in ten_ds)

print("NGUOIDUNG-FAIL ({} ca)".format(hong) if hong else "NGUOIDUNG-OK")
sys.exit(1 if hong else 0)
