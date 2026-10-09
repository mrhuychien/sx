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

# D108: lịch tháng chỉ đọc nhưng dễ tin — ô trống mà đã ghi, hay số của phiếu đã
# huỷ / chưa duyệt, là người ta đi ghi lại lần hai hoặc tin một con số không có thật.
python3 scripts/test-lich.py > /tmp/sx-lich.log 2>&1 \
  && tail -1 /tmp/sx-lich.log \
  || { cat /tmp/sx-lich.log; loi=1; }

# D109: ảnh lưu mẫu nén trên máy. Nén không tới thì ảnh 4 MB đi thẳng lên server
# (chậm, bị từ chối, đầy ổ); nén quá tay thì không đọc được chữ HSD — lý do chụp.
node scripts/test-anh.mjs > /tmp/sx-anh.log 2>&1 \
  && tail -1 /tmp/sx-anh.log \
  || { cat /tmp/sx-anh.log; loi=1; }

# D110: thẻ phiếu lương chỉ đọc nhưng là TIỀN LƯƠNG — phiếu đã huỷ lọt vào tổng,
# hay người ngoài quản lý mở được, đều là sai người ta tin và đọc to.
python3 scripts/test-luong.py > /tmp/sx-luong.log 2>&1 \
  && tail -1 /tmp/sx-luong.log \
  || { cat /tmp/sx-luong.log; loi=1; }

# D111: nút copy sản lượng từng hỏng im lặng (hàm ngoài render gọi biến trong render).
# Bấm đúng nút trong Chromium thật và đọc lại clipboard.
node scripts/test-copy.mjs > /tmp/sx-copy.log 2>&1 \
  && tail -1 /tmp/sx-copy.log \
  || { cat /tmp/sx-copy.log; loi=1; }

# D113: hai QC ghi vào hộp cùng ngày. Trước D113 lần lưu của người này XOÁ dòng của
# người kia (ghi đè cả bảng) mà không ai biết.
python3 scripts/test-ghihop.py > /tmp/sx-ghihop.log 2>&1 \
  && tail -1 /tmp/sx-ghihop.log \
  || { cat /tmp/sx-ghihop.log; loi=1; }

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

# D114: lô thành phẩm vào kho PHẢI có HSD. Hỏng thì im lặng — duyệt vẫn qua, lô
# vẫn có số, chỉ là không ai biết hộp nào sắp hết hạn cho tới khi khách trả về.
python3 scripts/test-hsd.py > /tmp/sx-hsd.log 2>&1 \
  && tail -1 /tmp/sx-hsd.log \
  || { cat /tmp/sx-hsd.log; loi=1; }

# D115: truy xuất hỏng là hỏng IM LẶNG — cây vẫn đẹp, chỉ thiếu đúng nhánh / đúng
# khách cần gọi lúc thu hồi.
python3 scripts/test-truyxuat.py > /tmp/sx-tx.log 2>&1 \
  && tail -1 /tmp/sx-tx.log \
  || { cat /tmp/sx-tx.log; loi=1; }

# D116: mã chưa có giá vốn — báo hết một lần bằng tiếng Việt TRƯỚC khi sinh phiếu
# kho, khai giá chỉ cho mã đang thiếu.
python3 scripts/test-giavon.py > /tmp/sx-gv.log 2>&1 \
  && tail -1 /tmp/sx-gv.log \
  || { cat /tmp/sx-gv.log; loi=1; }

# D120: chậm kiểu N+1 chỉ lộ ra khi dữ liệu đã nhiều. Đếm truy vấn với dữ liệu nhỏ
# và lớn — phải bằng nhau.
python3 scripts/test-tocdo.py > /tmp/sx-tocdo.log 2>&1 \
  && tail -1 /tmp/sx-tocdo.log \
  || { cat /tmp/sx-tocdo.log; loi=1; }

# D122: vào hộp Tết — một lần lưu ra phiếu nháp + công nhật; không được nửa chừng.
python3 scripts/test-tet.py > /tmp/sx-tet.log 2>&1 \
  && tail -1 /tmp/sx-tet.log \
  || { cat /tmp/sx-tet.log; loi=1; }

# D123: bỏ chốt — kho + lương tự đồng bộ ngầm. Hỏng là hỏng IM LẶNG (kho lệch báo mẻ
# mà không ai bấm gì để thấy), nên kiểm kỹ phần chênh / rút / lỗi từng mã.
python3 scripts/test-dongbo.py > /tmp/sx-dongbo.log 2>&1 \
  && tail -1 /tmp/sx-dongbo.log \
  || { cat /tmp/sx-dongbo.log; loi=1; }

# D127 (W28): hạn dùng theo bộ tự công bố. Cộng ngày thay vì tháng thì HSD lệch bao
# bì vài ngày — truy xuất theo HSD in trên hộp không ra lô nào, và không lỗi nào hiện ra.
python3 scripts/test-congbo.py > /tmp/sx-congbo.log 2>&1 \
  && tail -1 /tmp/sx-congbo.log \
  || { cat /tmp/sx-congbo.log; loi=1; }

# D129 (W01/W02): bộ mục bản 2. Phiếu cũ bị chen mục mới / mất mục cũ, hay dị vật
# trên rây không thành sự cố — đều im lặng.
python3 scripts/test-qcv2.py > /tmp/sx-qcv2.log 2>&1 \
  && tail -1 /tmp/sx-qcv2.log \
  || { cat /tmp/sx-qcv2.log; loi=1; }

# D130 (W04): công đoạn thành danh mục, đổi tên lan sang phiếu cũ. Thiếu một tên đang
# có trên phiếu cũ là phiếu đó không lưu lại được; vòng kiểm sinh sự cố tên cũ là lỗi
# giữa lúc QC hoàn tất lượt.
python3 scripts/test-congdoan.py > /tmp/sx-congdoan.log 2>&1 \
  && tail -1 /tmp/sx-congdoan.log \
  || { cat /tmp/sx-congdoan.log; loi=1; }

# D131 (W05): lô thành phẩm theo HSD. Hai ngày đóng hộp dồn một dòng là nửa số hộp
# mang HSD sai; NSX lấy ngày nhập là "quá trình" khớp nhầm ngày — đều im lặng.
python3 scripts/test-lohsd.py > /tmp/sx-lohsd.log 2>&1 \
  && tail -1 /tmp/sx-lohsd.log \
  || { cat /tmp/sx-lohsd.log; loi=1; }

# D132 (W06): bán trừ kho thành phẩm phải chọn đúng lô. ERPNext tự chọn lô khi bỏ
# trống — hoá đơn vẫn qua, truy xuất xuôi gọi nhầm khách lúc thu hồi.
python3 scripts/test-banlo.py > /tmp/sx-banlo.log 2>&1 \
  && tail -1 /tmp/sx-banlo.log \
  || { cat /tmp/sx-banlo.log; loi=1; }

# D133 (W07): lưu mẫu. Hạn tính sai, mẫu lô đang khiếu nại lọt vào đợt huỷ, QC tự huỷ
# được hay biên bản ghi "đã huỷ" cả mẫu đã lấy ra — đều im lặng tới đúng ngày cần mẫu.
python3 scripts/test-luumau.py > /tmp/sx-luumau.log 2>&1 \
  && tail -1 /tmp/sx-luumau.log \
  || { cat /tmp/sx-luumau.log; loi=1; }

# D134 (W11): phiếu sự cố. Desk tự đóng phiếu, bật cờ diễn tập cho phiếu thật, lô gắn
# không điền HSD — đều là cửa hậu / lỗi im lặng.
python3 scripts/test-sucolo.py > /tmp/sx-sucolo.log 2>&1 \
  && tail -1 /tmp/sx-sucolo.log \
  || { cat /tmp/sx-sucolo.log; loi=1; }

# D135 (W13): sổ khiếu nại trên Issue. Lô tìm nhầm sản phẩm, người tiếp nhận tự đóng,
# dị vật không ra phiếu sự cố — đều không có lỗi nào hiện lên màn hình.
python3 scripts/test-khieunai.py > /tmp/sx-khieunai.log 2>&1 \
  && tail -1 /tmp/sx-khieunai.log \
  || { cat /tmp/sx-khieunai.log; loi=1; }

# D136 (W26): hàng trả về + lô thu hồi. Lô thu hồi lọt qua bundle / qua lô ERPNext tự
# chọn / qua Stock Entry, hay hàng trả về lẫn vào kho bán — đều im lặng.
python3 scripts/test-thuhoi.py > /tmp/sx-thuhoi.log 2>&1 \
  && tail -1 /tmp/sx-thuhoi.log \
  || { cat /tmp/sx-thuhoi.log; loi=1; }

# D137 (W08): kiểm tra xuất xưởng BM.08.04. Người kiểm tự duyệt, lô chưa duyệt vẫn nhập
# kho / bán được, hay chặn nhầm cả kho tồn cũ — đều là cổng cuối mở toang hoặc đóng sập.
python3 scripts/test-xuatxuong.py > /tmp/sx-xuatxuong.log 2>&1 \
  && tail -1 /tmp/sx-xuatxuong.log \
  || { cat /tmp/sx-xuatxuong.log; loi=1; }

# D138 (W09, W10): NCC được duyệt + tiếp nhận trên phiếu nhập mua. Tự duyệt NCC, chặn
# nhầm mua hàng, lô nhập khẩu không COA "Đạt", lô cách ly nhập chung kho — đều im lặng.
python3 scripts/test-ncc.py > /tmp/sx-ncc.log 2>&1 \
  && tail -1 /tmp/sx-ncc.log \
  || { cat /tmp/sx-ncc.log; loi=1; }

# D139 (W14): kiểm xe BM.09.01. Bán bằng xe không đạt, mục hỏng mà kết luận Đạt, xe nhận
# hàng bẩn mà lô vẫn vào kho dùng — đều im lặng.
python3 scripts/test-kiemxe.py > /tmp/sx-kiemxe.log 2>&1 \
  && tail -1 /tmp/sx-kiemxe.log \
  || { cat /tmp/sx-kiemxe.log; loi=1; }

# D140 (W15): động vật gây hại theo trạm. Khu dấu hiệu hai tuần liền không ai nhắc, chuỗi
# giữa tháng rơi khỏi BM.PRP.01, mã quét ở máy lệch mã ở server — đều im lặng.
python3 scripts/test-dongvat.py > /tmp/sx-dongvat.log 2>&1 \
  && tail -1 /tmp/sx-dongvat.log \
  || { cat /tmp/sx-dongvat.log; loi=1; }

# D141 (W20, W12): nhật ký cát rang + xem xét tháng theo ngày sản xuất. Số ngày cát không
# tính lại khi ghi bù / xoá, đổi nguồn không nhắc kim loại nặng, tỷ lệ lượt chia cho ngày
# lịch — đều im lặng.
python3 scripts/test-cat.py > /tmp/sx-cat.log 2>&1 \
  && tail -1 /tmp/sx-cat.log \
  || { cat /tmp/sx-cat.log; loi=1; }

# D142 (W16): số đo theo máy rang M1–M3 / máy gói bột. Số của máy đã tắt lọt vào thống kê,
# nhãn Desk lệch nhãn màn hình, field đọc không có trên phiếu — đều im lặng.
python3 scripts/test-somay.py > /tmp/sx-somay.log 2>&1 \
  && tail -1 /tmp/sx-somay.log \
  || { cat /tmp/sx-somay.log; loi=1; }

# D143 (W17): thiết bị đo BM.06. Hạn tính sai, cân bị kiểm nội bộ kéo dài hạn kiểm định, hỏng
# mà vẫn Đạt, quá hạn không ngừng dùng / không phiếu sự cố, phiếu sự cố lặp mỗi ngày — đều im lặng.
python3 scripts/test-thietbi.py > /tmp/sx-thietbi.log 2>&1 \
  && tail -1 /tmp/sx-thietbi.log \
  || { cat /tmp/sx-thietbi.log; loi=1; }

# D144 (W18): kế hoạch kiểm nghiệm KH.KN.01. Hạn 1 lần / năm tính sai, sản phẩm chưa gửi không có
# hạn, Không đạt không thành sự cố, mẫu cát không chép sang nhật ký / sự cố trùng — đều im lặng.
python3 scripts/test-kiemnghiem.py > /tmp/sx-kiemnghiem.log 2>&1 \
  && tail -1 /tmp/sx-kiemnghiem.log \
  || { cat /tmp/sx-kiemnghiem.log; loi=1; }

# D145 (W19): phiếu rework BM.15.01. Quá 10% mẻ, hàng có lạc vào sản phẩm không lạc, đóng sự cố
# quyết định rework mà chưa có phiếu — đều im lặng.
python3 scripts/test-rework.py > /tmp/sx-rework.log 2>&1 \
  && tail -1 /tmp/sx-rework.log \
  || { cat /tmp/sx-rework.log; loi=1; }

# D146 (W21): lịch việc định kỳ. Hạn trôi theo ngày làm, việc một lần nhắc mãi, thiếu hai việc
# tài liệu nêu — đều im lặng.
python3 scripts/test-lichviec.py > /tmp/sx-lichviec.log 2>&1 \
  && tail -1 /tmp/sx-lichviec.log \
  || { cat /tmp/sx-lichviec.log; loi=1; }

# D147 (W23): nhập lại bản giấy, lượt Bổ sung. Lượt nhập lại không giờ kiểm thật, mất điện lần hai
# không mở được lượt, lượt bổ sung đếm thay lượt chính / không lý do — đều im lặng.
python3 scripts/test-bosung.py > /tmp/sx-bosung.log 2>&1 \
  && tail -1 /tmp/sx-bosung.log \
  || { cat /tmp/sx-bosung.log; loi=1; }

exit $loi
