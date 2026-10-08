# Module QC — BM.08.01 / BM.08.02

Toàn bộ phần QC nằm trong module này để sau muốn tách thành app riêng thì chỉ
phải chuyển thư mục + sửa `modules.txt` + viết patch rename, không phải viết lại.

```
sx/qc/muc.py            danh mục mục kiểm + ma trận áp dụng   ← nguồn duy nhất
sx/qc/nguong.py         đọc SX QC Setting, có mặc định an toàn
sx/qc/su_co.py          luật "lệch → sự cố"
sx/qc/day_sheet.html    tờ A4 cho auditor
sx/qc/doctype/...       5 DocType
sx/api/qc.py            method whitelist (không import gì từ phần còn lại của sx)
sx/public/sx/views/qc*.js + qc.css     màn hình, prefix class `sx-qc-`
scripts/test-qc.py      chốt mọi thứ trên khớp nhau
```

## Chỗ lệch so với SPEC — đã chốt với chủ đầu tư, ghi lại để không ai "sửa lại cho đúng spec"

| Spec viết | Ở đây | Vì sao |
|---|---|---|
| `ca_san_xuat` Link tới DocType ca; 3 lượt × 2 ca | **một ngày ba lượt, không chia ca** (D95): Đầu sáng trước 08:30 · Trưa trước 14:00 · Cuối chiều trước 20:00 | Nhà máy chốt lịch này ngày 28/9. Trường `ca` giữ lại (ẩn) chỉ cho phiếu trước D95; patch `d95_qc_mot_ngay_ba_luot` đổi tên lượt cũ (Đầu ca / Giữa ca / Cuối ca) sang tên mới trên phiếu đã có. Có thêm `ngay_san_xuat` Link tuỳ chọn chỉ để nối hồ sơ. |
| BM.07.03 gắn custom field lên **Purchase Receipt** | gắn lên **Purchase Invoice** | Kho nguyên liệu nhập thẳng bằng Purchase Invoice, không lập Purchase Receipt. Bám spec ở đây nghĩa là dựng một chứng từ không ai lập. |
| BM.07.03 để kết luận ở đầu phiếu | kết luận ở **từng dòng hàng** | BM.07.03 kiểm theo LÔ. Một hoá đơn có ba mặt hàng ba lô; một ô kết luận chung thì cái lô có vấn đề biến mất trong đó. Chỉ `nguoi_kiem` và `ghi_chu_qc` ở đầu phiếu. |
| Bảng màu riêng `--sxqc-*`, font Be Vietnam Pro | bố cục theo bản thiết kế, **màu và font theo `sx`** | Một app không nên có hai phong cách. Kích thước chạm, thứ tự mục, thanh đáy cố định giữ nguyên như thiết kế. |
| Role `Warehouse` | có tạo | Trùng vai với `SX Thu Kho` nhưng vẫn tạo theo yêu cầu; một người gán cả hai được. |

## D87 — một sổ sự cố cho cả nhà máy

Trước đó có HAI chỗ ghi sự cố: bảng con `SX Su Co Item` trên phiếu ngày (tổ Ghi
sổ bấm "+ Ghi sự cố") và `SX Su Co` (QC). Hai sổ nghĩa là hai chỗ phải nhớ đi
xem, và cái không ai nhớ thì không ai đóng. Đã gộp về `SX Su Co`:

- `portal.ghi_su_co` ghi thẳng vào `SX Su Co`, nguồn **Nhật ký chuyền**.
  Chữ ký method và khoá hàng chờ ngoại tuyến giữ nguyên — điện thoại còn sự cố
  nằm trong hàng chờ từ hôm qua vẫn gửi lên được sau khi deploy.
- Hai bảng phân loại sống song song và **không** trộn vào nhau: `loai`
  (oPRP / PRP / Dị ứng…) cho QC, `loai_chuyen` (Hỏng máy / Mất điện…) cho tổ Ghi
  sổ. Hai tổ nhìn sự cố theo hai cách; nhập một danh sách là mất nghĩa cả hai.
- `phut_dung` chuyển sang theo — dashboard quản lý vẫn cộng được phút dừng chuyền.
- `sx/patches/d87_gop_su_co.py` chép dữ liệu cũ sang, **không xoá** bảng con.
  Mỗi dòng mang khoá `<phiếu>#<idx>` nên `bench migrate` chạy lại bao nhiêu lần
  cũng không nhân đôi. Bản ghi cũ đóng sẵn — để Mở hết thì sổ mới mở ra đã có
  hàng trăm phiếu quá hạn và không ai đọc nó nữa.
- Bảng con cũ đổi thành read-only trên Desk, có ghi chú chỉ sang đây.

## P1 — Tiếp nhận nguyên liệu (BM.07.03)

Custom field trên **Purchase Invoice** (đầu phiếu: người kiểm, ghi chú) và
**Purchase Invoice Item** (mỗi lô: lô NCC, CQ/CO, COA vi sinh, aflatoxin, độ ẩm,
cảm quan, kết luận). Logic ở `sx/qc/tiep_nhan.py`, móc qua `doc_events`.

Hai luật **ÉP** kết luận sang *Cách ly* — cổng an toàn thực phẩm, không phải gợi ý:

- nhóm hàng bắt buộc có COA vi sinh mà COA = *Không* (nhóm con cũng tính);
- độ ẩm vượt `do_am_toi_da` trong Setting.

Ép chứ không chặn lưu: hàng đã về tới sân, chặn lưu hoá đơn không làm hàng biến
mất — nó chỉ làm người ta bỏ trống ô QC cho xong việc. Nhưng luôn **nói ra**,
không sửa lặng lẽ ô người ta vừa gõ.

Hai luật **CHẶN**:

- kết luận *Đạt* trong khi cảm quan *Không đạt* — mâu thuẫn trên một hồ sơ an
  toàn thực phẩm, gần như chắc chắn là gõ nhầm dòng;
- duyệt hoá đơn khi có dòng đã kiểm dở mà **bỏ trống kết luận**. Đây là lỗ im
  lặng: luật sinh sự cố bám vào ô kết luận, nên bỏ trống nó là cách chắc chắn
  nhất để một lô có vấn đề vào kho không dấu vết. (Luật này spec không yêu cầu —
  thêm vào vì phát hiện lúc viết test.)

Duyệt hoá đơn → mỗi lô *Không đạt* / *Cách ly* thành một `SX Su Co` nguồn
*Tiếp nhận NL*; *Không đạt* mức Cao, *Cách ly* mức Thường. Huỷ rồi duyệt lại
không nhân đôi (khoá `<hoá đơn>#<dòng>`).

**Chưa khai `nhom_can_coa` trong Setting thì luật COA KHÔNG chạy** — cố ý:
đoán vài tên nhóm thì hoặc chặn nhầm hàng tốt, hoặc cho qua đúng thứ cần chặn.

Việc này làm trên **Desk**, nên role `Warehouse` có `desk_access = 1`. QC chế
biến vẫn ở điện thoại (desk_access = 0) — nếu muốn QC tự kiểm ở cửa nhận hàng
bằng điện thoại thì cần một màn riêng, chưa làm.

## Hồ sơ giấy cho Ban ISO

| Ở đâu | Làm gì |
|---|---|
| `#/qc/history`, nút 🖨 mỗi ngày | tờ A4 BM.08.01 của ngày đó |
| `#/qc/review`, **IN CẢ THÁNG** | gộp tờ ngày cả tháng, mỗi ngày một trang; ngày không có lượt nào thì bỏ qua chứ không in tờ trống |
| `#/qc/review`, **CSV vòng kiểm / CSV sự cố** | file cho Ban ISO phân tích |
| Desk, phiếu `SX Su Co` | Print Format BM.08.02 |

Trong CSV vòng kiểm có **ba thứ khác nhau** mà gộp lại là đếm sai — cả
`sx/qc/xuat.py` tồn tại để giữ chúng tách nhau:

| ô | nghĩa |
|---|---|
| `n/a` | mục không áp dụng ở lượt đó |
| rỗng | áp dụng mà **chưa kiểm** ← thứ Ban ISO cần đếm |
| `—` | số chưa đo |

Gộp `n/a` với ô rỗng là tỷ lệ bỏ sót trông đẹp hơn sự thật.

## "Hôm nay có sản xuất bột" (D98)

Là chuyện của **cả ngày**, lưu ở `SX QC Ngay` — không phải của từng lượt. Hai chỗ bật:

| Ở đâu | Tác dụng |
|---|---|
| màn `#/qc` — nút **CÓ / KHÔNG** | cả ngày: mọi lượt **đang làm dở** + mọi lượt mở sau có phần B. Lượt **đã hoàn tất giữ nguyên** (8h chưa làm bột là đúng sự thật) |
| trong một lượt — **BẬT BỘT / TẮT BỘT** | riêng lượt đó. Bật thì cờ của ngày bật theo; tắt thì chỉ lượt đó (bột có thể dừng giữa ngày rồi chạy lại) |

Tắt mà lượt đã ghi mục bột thì hỏi lại hai bước và liệt kê mục sẽ bị giấu. Giá trị
không bị xoá — bật lại là thấy.

Trước D98 cả hai đều hỏng mà không báo gì: nút ở màn Hôm nay chỉ đổi một biến trong
trình duyệt (tải lại trang là về KHÔNG), và lượt đã mở thì không có chỗ nào bật bột.

## Phần bột: vị, lạc, máy chạy song song, lưu mẫu (D100)

**B0 — loại bột.** Bấm chọn trong danh mục (Item nhóm `BTP-Bot-SP` — đúng tab
*Bột đậu* của card Báo mẻ), chọn được nhiều vị. Không cho gõ tay: gõ tay là ba cách
viết cho một vị, và cờ lạc sẽ trượt. Tính vào "đã chấm" — bật bột mà không nói vị gì
thì lô không truy được. Lượt mới trong ngày nhận lại vị + số máy của lượt trước.

**Lạc theo vị.** B1 (lạc sạch), B2a/b/c (rang lạc) chỉ hiện khi lượt đó có làm vị có
lạc. B7 (thử nhanh lạc sau chuyển đổi) hiện khi lượt đó **hoặc một lượt trước trong
ngày** có làm — chuyển đổi xảy ra ở lượt sau. Vị nào có lạc: *SX QC Setting → Vị bột có
lạc* (mỗi dòng một mã/tên; trống = Chè đậu đen cốt dừa). Hai cờ `co_lac` /
`can_thu_lac` do **server** tính lúc lưu, máy QC không gửi lên được.

**Máy chạy song song.** Máy rang đỗ ×3 (nhiệt độ, vòng quay), máy nghiền ×2 (độ mịn),
máy đóng gói bột ×3 (**nhiệt độ hàn** B8 — mới, mối hàn, khối lượng). Máy 1 giữ
fieldname cũ; máy 2/3 là `<field>_m2`, `<field>_m3`. Mặc định 1 máy; QC bấm
**+ THÊM MÁY …** khi có thêm máy chạy, **Máy này nghỉ** để bớt. Máy không chạy thì
ô của nó không áp dụng, không in, không đòi giải trình. Ô máy 2/3 theo đúng luật sự
cố của ô gốc. Ngưỡng nhiệt độ hàn: *SX QC Setting* — **chưa đặt thì chỉ ghi số**,
không bịa sự cố (như rang lạc).

**Lưu mẫu** (`SX QC Luu Mau`, tab *Lưu mẫu*). QC chế biến / đóng gói lấy mẫu và xử
lý; Ban ISO, QLSX xem. Hạn lưu mặc định = ngày lấy + *SX QC Setting → Lưu mẫu bao nhiêu
ngày* (trống = 180 — **con số tạm, Ban ISO cần chốt**). Lấy mẫu ra (khiếu nại, kiểm
nghiệm) và huỷ **trước hạn** bắt buộc lý do; hết hạn thì huỷ một bước.

**Ảnh lưu mẫu (D109).** Form *Lấy mẫu* có **📷 CHỤP ẢNH** (mở thẳng camera sau) và
**🖼 Ảnh có sẵn**, tối đa 4 ảnh một lần, 8 ảnh một mẫu. Ảnh được **nén ngay trên máy**
(`lib/anh.js`): cạnh dài 1600 px — vẫn đọc được chữ HSD — JPEG hạ chất lượng từng bậc tới
khi ≤ ~350 KB (ảnh 4–7 MB thường còn 100–300 KB); form hiện "x MB → y KB". Mẫu được lưu
TRƯỚC, ảnh gửi SAU — gửi ảnh hỏng không mất lần lấy mẫu; nút **📷 + ẢNH** trên thẻ mẫu để
chụp thêm / gửi lại. Server chỉ nhận JPEG/PNG/WebP ≤ 1,5 MB, lưu File **riêng tư** gắn vào
mẫu (ai đọc được phiếu mới mở được ảnh); ảnh đầu là thumbnail trên danh sách.

Phiếu trước D100: patch `d100_qc_may_va_lac` bật cờ lạc cho mọi phiếu có bột (phần
lạc vẫn hiện như lúc ghi) và đặt số máy = 1.

## Công đoạn không chạy (D107)

Hôm không rang đỗ (hay không luộc, không đóng gói…) thì mục của công đoạn đó không có gì
để kiểm. Trên màn lượt kiểm, hàng **"Công đoạn nào hôm nay không chạy?"**: bấm một bước
là các mục của nó rời khỏi lượt — không tính "phải chấm", không đòi lý do để trống, không
bắt buộc nhiệt độ rang, không sinh sự cố. Bấm lại để bật. Lượt sau trong ngày nhận lại.

- Tắt được: 2 Luộc, 3 Rang, 4 Sàng cát, 6 Vỡ đỗ · Nam châm, 7 Nghiền, 10 Ủ sau trộn,
  12 Đóng gói (`muc.BUOC_TAT_DUOC`).
- **Không** tắt được: PRP đầu ca (kiểm cái xưởng, không phải dây chuyền), 8 Kho bột (thùng
  bột vẫn nằm trong kho), lượt tuần. Bột đậu có công tắc riêng.
- Tắt một bước đã ghi số thì hỏi lại trước. Mỗi lần bật / tắt vào nhật ký lượt (ai, lúc
  nào); tờ in BM.08.01 ghi "Công đoạn không chạy" để auditor hiểu vì sao cả hàng xám.

## Nhắc lịch — hiện trên dashboard, KHÔNG gửi đi đâu

`sx/qc/nhac.py` tính danh sách việc đang treo; hiện ở **ba chỗ, một bản duy nhất**:
đầu màn `#/qc` (QC), đầu màn `#/qc/review` (Ban ISO), và card `qcnhac` đứng đầu
`#/quanly` (quản lý). Một bản cho cả ba, cố ý — hai bản khác nhau là cách sinh ra
cuộc cãi "tôi có thấy gì đâu", và người thua luôn là tờ hồ sơ.

Không gửi email / Zalo: thứ gửi đi thì người ta tắt thông báo sau tuần thứ hai,
còn thứ nằm sẵn trên màn hình người ta mở mỗi sáng thì không tắt được. Cái giá
là nó chỉ nhắc khi có người mở màn — nên mỗi mục **phải nói đang treo bao lâu**,
không chỉ "có việc".

Mức **cao** chỉ có bốn thứ: sự cố quá hạn, sự cố mở mà chưa ghi xử lý, lượt tuần
bị bỏ, bẫy chuột có dấu hiệu hai tuần liền. Để cao hết thì không còn cao nữa.

Không có việc treo thì **không vẽ gì cả**: một hộp "mọi thứ ổn" nằm trên đầu
dashboard mỗi ngày sẽ dạy mắt bỏ qua đúng vùng đó, rồi hôm có việc thật cũng bỏ
qua nốt. Cùng lý do, hai chip "Sự cố mở / Quá hạn" ở cuối màn `#/qc` đã bỏ — hộp
nhắc nói cùng chuyện, nói kỹ hơn, và bấm vào cũng sang đúng màn đó.

Ca **không có lượt nào** thì không bị nhắc thiếu lượt: ca đó có thể đơn giản là
không sản xuất, mà đoán bừa rồi nhắc mỗi ngày là cách nhanh nhất để người ta bỏ
qua cả hộp.

## Chỗ còn phải hỏi Ban ISO

- **Tên 6 công đoạn** trong `muc.py: CONG_DOAN` có ghi `# cần xác nhận tên`
  (1, 5, 9, 11, 15, 16). Mười công đoạn còn lại là những cái spec ghim theo số
  trong luật map tự động nên chắc chắn đúng; sáu cái kia chỉ hiện khi người ta
  tự chọn tay trên phiếu sự cố.
- ~~Ngưỡng rang lạc chờ thẩm định~~ — đã chốt ở W03 (D128), xem mục dưới.
- Bản thiết kế có mục **"5 Ủ — thùng, khăn sạch khô"** mà spec không có
  fieldname. Chưa làm, vì bịa ra một field không có trên bản giấy BM.08.01 thì
  tờ in ra sẽ lệch với tập hồ sơ cũ.

## Ngưỡng phần bột và mã oPRP (D128 — W03)

- **Rang lạc 150–180 °C, 30–40 phút; hàn túi 150–190 °C** là mặc định trong code
  (`nguong.MAC_DINH`), sửa được ở *SX QC Setting* (thêm hai ô tối đa cho rang lạc).
  Ngoài khoảng → phiếu sự cố **oPRP** (hàn túi trước đây ghi "Khác").
- Phiếu sự cố có ô **Mã oPRP** (`oprp`): vòng kiểm tự ghi. Dây chuyền bánh theo công
  đoạn (Luộc/Rang oPRP-1, Sàng cát/Nghiền oPRP-2, Kho bột oPRP-3, Đóng gói oPRP-4);
  phần bột theo mục: rang lạc → **oPRP-1** (xử lý nhiệt), hàn túi B4/B8 → **oPRP-4**
  (hàn kín bao gói). Hai mã của phần bột là SUY theo cùng loại kiểm soát với bánh —
  Ban ISO đối chiếu KH.HACCP bột, khác thì sửa `OPRP_NHIET` / `OPRP_GOI` trong `muc.py`.
- Tờ in BM.08.02, danh sách sự cố, CSV đều hiện mã oPRP.

## Hai chỗ khai trùng, có test canh

1. Tên role khai ở cả `sx/config/roles.py` và `sx/api/qc.py` (module qc không
   import sang phần còn lại của app).
2. Danh mục mục kiểm khai ở `sx/qc/muc.py`, DocType JSON **sinh ra** từ nó bằng
   `python3 scripts/gen-qc-doctype.py`.

`scripts/test-qc.py` chốt cả hai. Sửa một bên quên bên kia thì `verify.sh` kêu.
