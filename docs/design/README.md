# Bản thiết kế giao diện — nguồn để đối chiếu

> ⚠️ **TỪ D53, APP KHÔNG CÒN CHẠY HỆ THIẾT KẾ TRONG THƯ MỤC NÀY.**
> Chủ đầu tư yêu cầu chuyển sang phong cách **NPP "4 mùa"** (portal `/npp`), tài liệu
> ở skill `frappe-portal-spa/references/design-system.md`, mục 17 ghi riêng lần
> chuyển này. `shell.css` hiện tại viết theo hệ đó — kính mờ, nền gradient theo mùa,
> thẻ trắng bo tròn, accent đổi theo mùa.
>
> Thư mục này GIỮ LẠI làm hồ sơ: nó là nguồn của D38–D50, và phần lớn quyết định
> BỐ CỤC (lưu đồ xếp dọc, thẻ công nhân 2 cột, tiêu đề 2 tầng ở bàn số, lô gập lại)
> vẫn còn nguyên — D53 chỉ thay lớp NHÌN, không thay bố cục. Đừng dùng file ở đây
> để "sửa màu cho đúng thiết kế" nữa.

File gốc từ Claude Design (chủ đầu tư gửi 30/07). Giữ trong repo để phiên làm việc sau
không phải gửi lại, và để đối chiếu khi sửa giao diện.

| File | Là gì |
|---|---|
| `xuong-sx-app-1a.dc.html` | **Bản đang áp dụng.** 3 màn (Vào hộp · Báo số · Quản lý) + các modal |
| `xuong-sx-redesign.dc.html` | Bản khác, **chưa đối chiếu** — hỏi chủ đầu tư trước khi dùng |
| `support.js` | Runtime của Claude Design; chỉ cần để mở file `.dc.html` trong trình duyệt |
| `_ds/modernist-*/` | Hệ thiết kế Modernist (styles.css + readme + token) |
| `ban-so-numpad.png` | Ảnh render màn bàn số — bản chụp chuẩn nhất để so |

Mở xem: mở thẳng `xuong-sx-app-1a.dc.html` bằng trình duyệt (cần mạng để tải font +
Lucide icon).

## Đã áp tới đâu

| Phần | Trạng thái |
|---|---|
| Bảng màu · font · độ bo · phẳng | ⛔ thay bằng hệ NPP ở D53 |
| Bàn số (kicker, chip, ô nền mực, gợi ý) | ✅ D39 |
| Màn **Vào hộp** | ✅ D40 |
| Màn **Ghi số** (thẻ lô có thanh tiến độ) | ⬜ chưa |
| Màn **Quản lý** (biểu đồ cột, sản lượng theo loại) | ⬜ chưa |

## Hai chỗ CỐ Ý làm khác bản thiết kế

Ghi lại để lần sau không ai "sửa lại cho đúng thiết kế" rồi làm hỏng:

1. **Chữ phụ dùng `#6f6862` (5.4:1), không phải `#8a827a` (3.7:1) của bản thiết kế.**
   Nhãn nhóm 12px, không phải 10px. Chính readme hệ Modernist viết: *"accent-to-ground
   tuned to at least 3:1 — enough for icons, large text and interface chrome, **not for
   body copy** — use a deep ramp step for paragraph-size text"*. QC đọc màn này giữa
   xưởng, nắng chói qua cửa, 3.7:1 là mất chữ.

2. **Vùng chạm 48px trở lên, không phải 44px.** QC đeo găng hoặc tay ẩm.

Ngoài hai chỗ đó, bám sát bản thiết kế.
