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

exit $loi
