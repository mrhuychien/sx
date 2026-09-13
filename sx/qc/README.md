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
| BM.07.03 gắn custom field lên **Purchase Receipt** | sẽ gắn lên **Purchase Invoice** | Kho nguyên liệu nhập thẳng bằng Purchase Invoice, không lập Purchase Receipt. (P1, chưa làm.) |
| Bảng màu riêng `--sxqc-*`, font Be Vietnam Pro | bố cục theo bản thiết kế, **màu và font theo `sx`** | Một app không nên có hai phong cách. Kích thước chạm, thứ tự mục, thanh đáy cố định giữ nguyên như thiết kế. |
| Role `Warehouse` | có tạo | Trùng vai với `SX Thu Kho` nhưng vẫn tạo theo yêu cầu; một người gán cả hai được. |

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
