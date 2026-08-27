#!/usr/bin/env bash
# Kiểm tra cú pháp trước khi push. Chạy: bash scripts/verify.sh
#
# ⚠️ KHÔNG dùng `node --check file.js` cho code portal: file .js được parse ở chế
# độ CommonJS + V8 lazy-parse thân hàm → BỎ SÓT lỗi trong thân hàm (đã dính thật:
# "Identifier 'ten' has already been declared" lọt lên site). Phải parse ĐÚNG kiểu
# ES module bằng cách đổi đuôi .mjs.
set -u
cd "$(dirname "$0")/.."
loi=0

python3 -m py_compile $(find sx -name '*.py') && echo "PY-OK" || { echo "PY-FAIL"; loi=1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
n=0
for f in $(find sx/public -name '*.js' | sort); do
  cp "$f" "$tmp/t.mjs"
  if ! out=$(node --check "$tmp/t.mjs" 2>&1); then
    echo "JS-FAIL $f"; echo "$out" | head -5; loi=1
  fi
  n=$((n + 1))
done
[ $loi -eq 0 ] && echo "JS-OK ($n file, parse kiểu ES module)"

# Mỗi thư mục doctype phải đủ BA file. Thiếu `<ten>.py` thì py_compile không kêu
# (không có file để compile) mà `bench migrate` chết ngay ở bước sync với
# "ModuleNotFoundError" — đã dính thật ở D56.
python3 - <<'PYEOF'
import os, sys
loi, base = [], "sx/sx/doctype"
for d in sorted(os.listdir(base)):
    p = os.path.join(base, d)
    if not os.path.isdir(p) or d == "__pycache__":
        continue
    for f in ("__init__.py", f"{d}.json", f"{d}.py"):
        if not os.path.exists(os.path.join(p, f)):
            loi.append(f"DOCTYPE-FAIL {d}: thiếu {f}")
print("\n".join(loi) if loi else "DOCTYPE-OK")
sys.exit(1 if loi else 0)
PYEOF
[ $? -ne 0 ] && loi=1

# Bộ lọc fixtures trong hooks.py phải khớp nội dung fixtures/*.json — lệch thì lần
# `bench export-fixtures` sau lặng lẽ xoá bản ghi khỏi file (đã dính thật ở D56).
python3 scripts/soat-fixtures.py || loi=1

# openSoLuong dựng ô nhập TỪ `chi_tiet` và BỎ QUA `tong` khi chi_tiet không rỗng.
# Đưa chi_tiet của cột này kèm tổng của cột kia là ghi đè mất số thủ kho vừa đếm mà
# không báo gì (đã dính thật ở D72). Bắt buộc hai tham số lấy từ CÙNG một cặp helper.
python3 - <<'PYEOF'
import re, sys
f = "sx/public/sx/cards/nhapkhotp.js"
src = open(f, encoding="utf-8").read()
loi = []
for m in re.finditer(r"openSoLuong\(\{(.*?)\n\s*\}\)", src, re.S):
    than = m.group(1)
    dong = src[:m.start()].count("\n") + 1
    ct = re.search(r"chi_tiet:\s*([^,\n]+)", than)
    tg = re.search(r"tong:\s*([^,\n]+)", than)
    if not ct or not tg:
        loi.append(f"CAP-COT-FAIL {f}:{dong}: thiếu chi_tiet hoặc tong")
        continue
    a, b = ct.group(1), tg.group(1)
    # Cùng dùng helper vai trò, hoặc chi_tiet là null (dòng mới) -> hợp lệ.
    if "ctCua" in a and "soCua" in b:
        continue
    if a.strip() in ("null", "null,"):
        continue
    loi.append(f"CAP-COT-FAIL {f}:{dong}: chi_tiet={a.strip()} / tong={b.strip()} "
               "— phải cùng cặp ctCua/soCua")
print("\n".join(loi) if loi else "CAP-COT-OK")
sys.exit(1 if loi else 0)
PYEOF
[ $? -ne 0 ] && loi=1

# openSoLuong phải giữ đúng TỔNG kể cả khi bảng quy đổi ĐVT đổi sau lúc ghi phiếu
# (đổi tên đơn vị / sửa hệ số / xoá một bậc). Nạp hàm THẬT ra chạy, không chép logic.
node scripts/test-soluong.mjs > /tmp/sx-soluong.log 2>&1 \
  && tail -1 /tmp/sx-soluong.log \
  || { cat /tmp/sx-soluong.log; loi=1; }

# seed_ton_dau submit chứng từ kho THẬT và không có nút hoàn tác: số học lô, giá vốn
# và cờ dry_run phải đúng trước khi ai đó gõ lệnh đó trên site nhà máy.
python3 scripts/test-seed.py > /tmp/sx-seed.log 2>&1 \
  && tail -1 /tmp/sx-seed.log \
  || { cat /tmp/sx-seed.log; loi=1; }

exit $loi
