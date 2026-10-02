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

# Bàn số điền sẵn số hiện tại ở MỌI chỗ gọi. Phím đầu gõ nối vào đuôi thì tồn 120
# gõ 50 ra 12050 — không lỗi nào hiện ra, chỉ là số vô lý đi thẳng vào sổ kho.
node scripts/test-numpad.mjs > /tmp/sx-np.log 2>&1 \
  && tail -1 /tmp/sx-np.log \
  || { cat /tmp/sx-np.log; loi=1; }

# D97 cố tình NỚI cái chặn "phải có BOM mới nhập kho". Nới sai thì hàng vào kho
# mà khoản nợ nguyên liệu biến mất, hoặc bù hai lần — cả hai đều im lặng.
python3 scripts/test-nobom.py > /tmp/sx-nb.log 2>&1 \
  && tail -1 /tmp/sx-nb.log \
  || { cat /tmp/sx-nb.log; loi=1; }

# D99: mã chưa có đơn giá vẫn chốt được — nợ lương phải được ghi, áp giá phải đúng
# ngày / đúng mã / không đụng phiếu lương đã duyệt. Hỏng thì công nhân mất tiền
# trong im lặng.
python3 scripts/test-nogia.py > /tmp/sx-ng.log 2>&1 \
  && tail -1 /tmp/sx-ng.log \
  || { cat /tmp/sx-ng.log; loi=1; }

# D101 nới chặn "không nhập quá số chấm" và thêm dòng công nhật. Hỏng thì hoặc hộp
# chấm sót biến mất khỏi sổ, hoặc công nhật lọt vào lương khoán — cả hai im lặng.
python3 scripts/test-novaohop.py > /tmp/sx-nvh.log 2>&1 \
  && tail -1 /tmp/sx-nvh.log \
  || { cat /tmp/sx-nvh.log; loi=1; }

# D102: thiếu prefix mã lô thì dùng mã hàng. Quay về chặn là thủ kho lại không
# duyệt được phiếu nhập của mã mới; bỏ qua prefix đã điền là mã lô ngắn bị thay.
python3 scripts/test-prefix.py > /tmp/sx-px.log 2>&1 \
  && tail -1 /tmp/sx-px.log \
  || { cat /tmp/sx-px.log; loi=1; }

# D104: huỷ phiếu nhập kho đã duyệt là THU HỒI chứng từ kho thật. Hỏng thì huỷ
# được cả khi hàng đã bán (tồn âm), hoặc huỷ không ai nói vì sao.
python3 scripts/test-huyphieu.py > /tmp/sx-hp.log 2>&1 \
  && tail -1 /tmp/sx-hp.log \
  || { cat /tmp/sx-hp.log; loi=1; }

# Điện thoại xưởng chuyền tay giữa hai QC; hàng chờ nằm trong trình duyệt chứ không
# trong tài khoản. Gửi nhầm thao tác của người trước dưới tên người sau thì nhật ký
# ghi sai người mà không lỗi nào hiện ra.
node scripts/test-hangcho.mjs > /tmp/sx-hc.log 2>&1 \
  && tail -1 /tmp/sx-hc.log \
  || { cat /tmp/sx-hc.log; loi=1; }

# Hộp nhắc hỏng theo hai hướng và cả hai đều kết thúc ở chỗ không ai đọc nó nữa:
# nhắc thừa thì mắt tự bỏ qua vùng đó, nhắc thiếu thì mất đúng thứ nó sinh ra để bắt.
python3 scripts/test-nhac.py > /tmp/sx-nhac.log 2>&1 \
  && tail -1 /tmp/sx-nhac.log \
  || { cat /tmp/sx-nhac.log; loi=1; }

# "Có sản xuất bột" từng bật lên không dính (chỉ đổi biến trong trình duyệt) và lượt
# đang dở không nhận được phần bột. Cả hai đều im lặng — phần B cứ thế không ai ghi.
python3 scripts/test-qcbot.py > /tmp/sx-qcbot.log 2>&1 \
  && tail -1 /tmp/sx-qcbot.log \
  || { cat /tmp/sx-qcbot.log; loi=1; }

# D100 quyết định MỤC NÀO HIỆN RA trên lượt kiểm: vị có lạc, máy 2/3, nhiệt độ
# hàn. Mục không hiện thì không ai ghi, không in, không sinh sự cố — và sai về
# phía ẩn ở phần lạc là bỏ bước kiểm dị ứng mà hồ sơ trông vẫn đủ.
python3 scripts/test-qcmay.py > /tmp/sx-qcmay.log 2>&1 \
  && tail -1 /tmp/sx-qcmay.log \
  || { cat /tmp/sx-qcmay.log; loi=1; }

# BM.07.03 là một CỔNG. Nới nhầm thì lô dừa sấy không COA đi thẳng vào bánh và
# hồ sơ vẫn ghi "Đạt"; siết nhầm thì thủ kho bỏ trống ô QC cho xong việc, tức là
# cổng tự mở.
python3 scripts/test-tiepnhan.py > /tmp/sx-tn.log 2>&1 \
  && tail -1 /tmp/sx-tn.log \
  || { cat /tmp/sx-tn.log; loi=1; }

# D87 đụng vào luồng ĐANG CHẠY THẬT (tổ Ghi sổ bấm "+ Ghi sự cố" mỗi ca). Hỏng thì
# hoặc sự cố không được ghi trong im lặng, hoặc migrate chạy lại nhân đôi cả sổ.
python3 scripts/test-sucogop.py > /tmp/sx-scg.log 2>&1 \
  && tail -1 /tmp/sx-scg.log \
  || { cat /tmp/sx-scg.log; loi=1; }

# Phân quyền hỏng không hiện ra như một lỗi: nới nhầm thì mọi thứ vẫn chạy, chỉ là
# QC bấm được nút đáng lẽ không được bấm.
python3 scripts/test-quyen.py > /tmp/sx-quyen.log 2>&1 \
  && tail -1 /tmp/sx-quyen.log \
  || { cat /tmp/sx-quyen.log; loi=1; }

exit $loi
