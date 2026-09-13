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
| `ca_san_xuat` Link tới DocType ca | `ca` Select `Sáng/Chiều` | App `sx` **không có** DocType ca sản xuất. `SX Ngay San Xuat` là theo NGÀY, không có field ca. Có thêm `ngay_san_xuat` Link tuỳ chọn chỉ để nối hồ sơ — module không đọc gì từ phiếu đó. |
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

## Chỗ còn phải hỏi Ban ISO

- **Tên 6 công đoạn** trong `muc.py: CONG_DOAN` có ghi `# cần xác nhận tên`
  (1, 5, 9, 11, 15, 16). Mười công đoạn còn lại là những cái spec ghim theo số
  trong luật map tự động nên chắc chắn đúng; sáu cái kia chỉ hiện khi người ta
  tự chọn tay trên phiếu sự cố.
- **Ngưỡng rang lạc** (`rang_lac_nhiet_min`, `rang_lac_phut_min`) đang để trống
  chờ thẩm định. Trống thì hệ thống chỉ ghi số, KHÔNG tự sinh sự cố — cố tình
  như vậy, xem chú thích trong `nguong.py`.
- Bản thiết kế có mục **"5 Ủ — thùng, khăn sạch khô"** mà spec không có
  fieldname. Chưa làm, vì bịa ra một field không có trên bản giấy BM.08.01 thì
  tờ in ra sẽ lệch với tập hồ sơ cũ.

## Hai chỗ khai trùng, có test canh

1. Tên role khai ở cả `sx/config/roles.py` và `sx/api/qc.py` (module qc không
   import sang phần còn lại của app).
2. Danh mục mục kiểm khai ở `sx/qc/muc.py`, DocType JSON **sinh ra** từ nó bằng
   `python3 scripts/gen-qc-doctype.py`.

`scripts/test-qc.py` chốt cả hai. Sửa một bên quên bên kia thì `verify.sh` kêu.
