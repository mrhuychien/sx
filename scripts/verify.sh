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

exit $loi
