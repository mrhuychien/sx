"""D210 — hook đo tốc độ (sx/do_toc.py): Server-Timing CHỈ khi trình duyệt xin đo.

Vì sao phải có bài này: hai hook chạy quanh MỌI yêu cầu của site. Hỏng theo hướng nào cũng tệ —
  · ném lỗi → mọi trang / API của site hỏng theo;
  · quên gỡ bộ đếm SQL, hay bọc cả khi không xin đo → mọi câu SQL chậm thêm, chồng bọc qua từng yêu cầu;
  · số đo sai (đếm thiếu câu lỗi, thời gian SQL lớn hơn tổng) → đọc bảng đo ra kết luận sai, sửa nhầm chỗ.
frappe giả tối thiểu: frappe.local (request, db), frappe._dict. Chạy: python3 scripts/test-dotoc.py
"""

import importlib.util
import os
import re
import sys
import time
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct and not dk else ''}")


class _dict(dict):
    __getattr__ = dict.get

    def __setattr__(self, k, v):
        self[k] = v


class Db:
    """Như frappe.database.Database: execute_query là phương thức của LỚP."""
    def __init__(self):
        self.goi = []

    def execute_query(self, query, values=None):
        self.goi.append(query)
        time.sleep(0.004)
        if "LOI" in query:
            raise RuntimeError("lỗi SQL giả")
        return f"kq:{query}"


class Rq:
    def __init__(self, headers=None, args=None):
        self.headers = headers or {}
        self.args = args or {}


class Res:
    def __init__(self):
        self.headers = {}


fr = types.ModuleType("frappe")
fr._dict = _dict
fr.local = types.SimpleNamespace()
sys.modules["frappe"] = fr
sp = importlib.util.spec_from_file_location("sx.do_toc", "sx/do_toc.py")
D = importlib.util.module_from_spec(sp)
sp.loader.exec_module(D)


def yeu_cau(headers=None, args=None, co_db=True):
    fr.local = types.SimpleNamespace(request=Rq(headers, args))
    if co_db:
        fr.local.db = Db()
    return fr.local


TIMING = re.compile(r'^sx;dur=(\d+\.\d), sql;dur=(\d+\.\d);desc="(\d+)"$')

print("-- yêu cầu bình thường: không đo, không bọc, không thêm header --")
L = yeu_cau()
D.bat_dau()
kiem("không bọc execute_query (vẫn là phương thức của lớp)", "execute_query" not in L.db.__dict__)
r = Res()
D.ket_thuc(response=r, request=L.request)
kiem("không thêm Server-Timing", "Server-Timing" not in r.headers, r.headers)

print("\n-- lời gọi API có X-Sx-Do --")
L = yeu_cau({"X-Sx-Do": "1"})
D.bat_dau()
kiem("bọc execute_query của ĐÚNG đối tượng db của yêu cầu", "execute_query" in L.db.__dict__)
kq = [L.db.execute_query("select 1"), L.db.execute_query("select 2", {"a": 1})]
try:
    L.db.execute_query("select LOI")
    loi = None
except RuntimeError as e:
    loi = str(e)
kiem("giá trị trả về / lỗi của câu SQL đi xuyên qua nguyên vẹn", kq == ["kq:select 1", "kq:select 2"]
     and loi == "lỗi SQL giả" and L.db.goi == ["select 1", "select 2", "select LOI"], (kq, loi))
time.sleep(0.01)
r = Res()
D.ket_thuc(response=r, request=L.request)
m = TIMING.match(r.headers.get("Server-Timing", ""))
kiem("Server-Timing: sx;dur=…, sql;dur=…;desc=\"số câu\"", bool(m), r.headers)
if m:
    tong, sql, n = float(m.group(1)), float(m.group(2)), int(m.group(3))
    kiem("đếm đủ 3 câu (cả câu lỗi), SQL ≥ 3 × 4 ms, tổng ≥ SQL + 10 ms ngủ ngoài SQL",
         n == 3 and sql >= 12 and tong >= sql + 10, (tong, sql, n))
kiem("gỡ bộ đếm sau yêu cầu (về lại phương thức của lớp)", "execute_query" not in L.db.__dict__)
kiem("hết dấu đo của yêu cầu", getattr(fr.local, "sx_do", "x") is None)

print("\n-- trang /sx?do=1 --")
L = yeu_cau(args={"do": "1"})
D.bat_dau()
L.db.execute_query("select 3")
r = Res()
D.ket_thuc(response=r, request=L.request)
kiem("trang HTML có ?do=1 cũng được đo", (TIMING.match(r.headers.get("Server-Timing", "")) or [None, 0, 0, "0"])[3]
     == "1", r.headers)
L = yeu_cau(args={"do": "0"})
D.bat_dau()
r = Res()
D.ket_thuc(response=r, request=L.request)
kiem("?do=0 / tham số khác: không đo", "Server-Timing" not in r.headers and "execute_query" not in L.db.__dict__)

print("\n-- không bao giờ ném lỗi --")
fr.local = types.SimpleNamespace()                       # chưa có request (job nền, lệnh bench)
try:
    D.bat_dau()
    D.ket_thuc(response=Res())
    ok = True
except Exception as e:  # noqa: BLE001
    ok = repr(e)
kiem("không có request: không lỗi, không đo", ok is True, ok)
L = yeu_cau({"X-Sx-Do": "1"}, co_db=False)               # chưa kết nối DB
D.bat_dau()
r = Res()
D.ket_thuc(response=r, request=L.request)
kiem("không có db: vẫn đo được thời gian máy chủ, bỏ phần SQL",
     re.match(r"^sx;dur=\d+\.\d$", r.headers.get("Server-Timing", "")), r.headers)


class RqHong:
    @property
    def headers(self):
        raise RuntimeError("request hỏng")


fr.local = types.SimpleNamespace(request=RqHong(), db=Db())
try:
    D.bat_dau()
    D.ket_thuc(response=None)
    ok = True
except Exception as e:  # noqa: BLE001
    ok = repr(e)
kiem("request hỏng / response None: nuốt lỗi, không bọc gì", ok is True and "execute_query" not in fr.local.db.__dict__,
     ok)
L = yeu_cau({"X-Sx-Do": "1"})
D.bat_dau()
D.ket_thuc(response=None)
kiem("response None: vẫn gỡ bộ đếm", "execute_query" not in L.db.__dict__)

print("\n-- dây nối trong hooks.py --")
hooks = open("sx/hooks.py", encoding="utf-8").read()
kiem("before_request có sx.do_toc.bat_dau (sau bản vá ERPNext), after_request có sx.do_toc.ket_thuc",
     'before_request = ["sx.va_erpnext.va", "sx.do_toc.bat_dau"]' in hooks
     and 'after_request = ["sx.do_toc.ket_thuc"]' in hooks)

print("DOTOC-OK" if not hong else f"DOTOC: {hong} HỎNG")
sys.exit(1 if hong else 0)
