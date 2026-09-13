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
import glob, os, sys
loi = []
# Quét MỌI module (sx/<module>/doctype), không chỉ module SX — thêm module mới
# mà quên là migrate chết trên site nhà máy chứ không chết ở đây.
for base in sorted(glob.glob("sx/*/doctype")):
    if not os.path.exists(os.path.join(os.path.dirname(base), "__init__.py")):
        loi.append(f"DOCTYPE-FAIL {base}: module thiếu __init__.py")
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d)
        if not os.path.isdir(p) or d == "__pycache__":
            continue
        for f in ("__init__.py", f"{d}.json", f"{d}.py"):
            if not os.path.exists(os.path.join(p, f)):
                loi.append(f"DOCTYPE-FAIL {base}/{d}: thiếu {f}")
# Module khai trong thư mục phải có trong modules.txt, và ngược lại.
khai = {x.strip() for x in open("sx/modules.txt", encoding="utf-8") if x.strip()}
tren_dia = {os.path.basename(os.path.dirname(b)).upper() for b in glob.glob("sx/*/doctype")}
if not {k.upper() for k in khai} >= tren_dia:
    loi.append(f"DOCTYPE-FAIL modules.txt thiếu: {tren_dia - {k.upper() for k in khai}}")
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

# Cắt lệch vùng ô ngắm trông y hệt "camera mờ": soi mãi không ăn, không lỗi nào hiện
# ra. Sai lặng lẽ thì phải chặn bằng test.
node scripts/test-quet.mjs > /tmp/sx-quet.log 2>&1 \
  && tail -1 /tmp/sx-quet.log \
  || { cat /tmp/sx-quet.log; loi=1; }

# Toàn bộ việc quét trên iPhone dựa vào bộ đọc đóng gói trong repo. Nó hỏng thì triệu
# chứng là "soi mãi không ăn", không lỗi nào hiện ra — phải chặn bằng test.
node scripts/test-mavach.mjs > /tmp/sx-mavach.log 2>&1 \
  && tail -1 /tmp/sx-mavach.log \
  || { cat /tmp/sx-mavach.log; loi=1; }

# Bảng đơn giá sai là tiền lương sai, mà sai âm thầm: màn hình vẫn ghi được sản lượng
# bình thường, chỉ có con số tiền là khác.
python3 scripts/test-dongia.py > /tmp/sx-dongia.log 2>&1 \
  && tail -1 /tmp/sx-dongia.log \
  || { cat /tmp/sx-dongia.log; loi=1; }

# Màn tạo tài khoản là chỗ DUY NHẤT app cấp quyền cho người khác, và mã QR trên thẻ
# là thứ ai cầm cũng vào được. Hỏng ở đây không hiện ra như một lỗi.
python3 scripts/test-nguoidung.py > /tmp/sx-nd.log 2>&1 \
  && tail -1 /tmp/sx-nd.log \
  || { cat /tmp/sx-nd.log; loi=1; }

# Import map hỏng KHÔNG báo lỗi ở chỗ nó hỏng: thừa dấu phẩy là trình duyệt vứt cả
# khối, mọi module nạp bản CŨ trong cache, và triệu chứng là "sửa rồi mà máy nó
# vẫn thế".
python3 scripts/test-importmap.py > /tmp/sx-im.log 2>&1 \
  && tail -1 /tmp/sx-im.log \
  || { cat /tmp/sx-im.log; loi=1; }

# Module QC: sót một luật sinh sự cố thì lượt vẫn hoàn tất, màn hình vẫn xanh,
# chỉ là chỗ không đạt kia không thành phiếu và không ai đi xử lý.
python3 scripts/test-qc.py > /tmp/sx-qc.log 2>&1 \
  && tail -1 /tmp/sx-qc.log \
  || { cat /tmp/sx-qc.log; loi=1; }

# Phân quyền hỏng không hiện ra như một lỗi: nới nhầm thì mọi thứ vẫn chạy, chỉ là
# QC bấm được nút đáng lẽ không được bấm.
python3 scripts/test-quyen.py > /tmp/sx-quyen.log 2>&1 \
  && tail -1 /tmp/sx-quyen.log \
  || { cat /tmp/sx-quyen.log; loi=1; }

exit $loi
