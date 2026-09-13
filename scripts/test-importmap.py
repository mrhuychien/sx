"""Import map của /sx phải là JSON HỢP LỆ và khớp file trên đĩa.

Vì sao phải có bài này: import map hỏng KHÔNG báo lỗi ở chỗ nó hỏng. Thừa một
dấu phẩy là trình duyệt vứt cả khối map, rồi mọi module nạp thẳng không có `?v` —
app vẫn chạy, chỉ là chạy bằng BẢN CŨ trong cache, và triệu chứng là "sửa rồi mà
trên máy nó vẫn thế". Đúng loại lỗi tốn cả buổi.

Chốt ba thứ:
  1. Khối importmap parse được thành JSON.
  2. Mọi `from '/assets/sx/sx/...'` trong code đều có khoá trong map (không thì
     module đó không bao giờ được bust cache).
  3. Không khoá nào trỏ vào file đã xoá (bẫy đọc code — đã dính thật ở D84).

Chạy: python3 scripts/test-importmap.py
"""

import json
import os
import pathlib
import re
import sys

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


html = pathlib.Path("sx/www/sx.html").read_text(encoding="utf-8")
khoi = re.search(r'<script type="importmap">(.*?)</script>', html, re.S)
kiem("có khối importmap", bool(khoi))
if not khoi:
    print("IMPORTMAP-FAIL")
    sys.exit(1)

# {{ v }} là placeholder Jinja — thay bằng chuỗi thật rồi mới parse.
tho = khoi.group(1).replace("{{ v }}", "X")
try:
    data = json.loads(tho)
    loi = None
except ValueError as e:
    data, loi = None, str(e)
kiem("importmap là JSON hợp lệ", data is not None, loi or "")
if not data:
    print("IMPORTMAP-FAIL")
    sys.exit(1)

khoa = set(data.get("imports", {}))
kiem("mọi khoá đều tự trỏ về chính nó kèm ?v",
     all(v.startswith(f"{k}?v=") for k, v in data["imports"].items()),
     ", ".join(k for k, v in data["imports"].items() if not v.startswith(f"{k}?v=")))

tren_dia = {f"/assets/sx/sx/{p.relative_to('sx/public/sx')}"
            for p in pathlib.Path("sx/public/sx").rglob("*.js")}
chet = sorted(khoa - tren_dia)
kiem("không khoá nào trỏ vào file đã xoá", not chet, ", ".join(chet))

thieu = []
for f in sorted(pathlib.Path("sx/public/sx").rglob("*.js")):
    src = f.read_text(encoding="utf-8")
    for m in re.findall(r"from ['\"](/assets/sx/sx/[^'\"]+)['\"]", src):
        if m not in khoa:
            thieu.append(f"{f.name} → {m}")
kiem("mọi import tĩnh đều có trong map", not thieu, ", ".join(thieu))

print("IMPORTMAP-FAIL ({} ca)".format(hong) if hong else "IMPORTMAP-OK")
sys.exit(1 if hong else 0)
