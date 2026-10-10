# sx — Portal Sản Xuất RVHG (v3)

Custom app Frappe/ERPNext v16: số hoá + **truy xuất nguồn gốc** sản xuất RVHG — 2 nhánh
**bánh đậu xanh** (8 loại ruột) và **bột đậu** (8 công thức). Pipeline lệch ngày, BOM 3 tầng,
**công nhân 0 chạm** — 2 QC nhập toàn bộ số liệu. Truy xuất mức **ngày × loại**, FIFO tự động
toàn tuyến (không ai chọn lô).

- **Bản thiết kế giao diện**: [`docs/design/`](docs/design/) — file gốc + đã áp tới đâu
- Spec đầy đủ: [`docs/CODER-PACK.md`](docs/CODER-PACK.md) (v3 — thay thế hoàn toàn v1/v2)
- Site đích: `a.rongvanghoanggia.com`
- Phương pháp: nextcode + skills `frappe-app-build-profile` / `nextcode-build` /
  `frappe-portal-spa` / `frappe-app-shipping-gotchas`

## Kiến trúc nhanh

```
QC#1 (chiều D-1) : SX Xuat Dau  → sinh lô rang R (nhập thẳng kg, D6)
D → D+1          : rang → nghiền                              (0 thao tác — D18)
QC#1 (cuối ngày) : báo mẻ (child SX Bao Me: nấu đường hoán + trộn bột bánh/bột đậu) + báo cán
QC#2             : SX Bang Vao Hop (lương khoán: người × loại công việc) + CHỐT NGÀY
Chốt ngày        : chot_ngay → T1 TỰ NHẬP BỘT lô R rang hôm trước (Manufacture: trừ đỗ
                              FIFO Kho NVL → bột Kho BTP, batch = lô R). Đỗ CHỈ trừ ở đây (D7)
                            → T2 (topo-sort: đường hoán → bột bánh/bột đậu, WO+SE,
                              bột nền FIFO lô R cũ nhất)
                            → T3 (WO+SE TP cho dòng CÓ SKU, bột bánh/bột đậu FIFO)
                            → SalaryProduct (mọi dòng, kể cả chưa gắn SKU)
Truy xuất            : TP → bột bánh/bột đậu → lô R → lô đậu NCC (+ đường hoán → lô đường NCC)
```

9 role, 5 view (`ghiso` / `vaohop` / `nhapkho` / `qc` / `quanly`) — mỗi view lắp từ CARD theo
`sx/config/roles.py`. Portal `/sx` card-based. Numpad phím
to, mã lô hiển thị **cực to** để ghi thẻ tay (D13), chốt ngày modal 2 bước.

## ⚠️ Tính độc lập (spec §2.1 — rủi ro đã cân nhắc, chủ đầu tư chấp nhận)

Người nhập số liệu sản xuất là **QC** — vai trò kép. Hai điều kiện giảm thiểu bắt buộc:
1. **2 QC tách vai:** `ghiso@rvhg` (ghi số) ≠ `vaohop@rvhg` (vào hộp + chốt ngày). Không tài
   khoản chung. Mọi DocType `SX *` bật `track_changes` (bằng chứng ai nhập gì).
2. **Người thẩm tra hồ sơ bên app `iso` (làm sau) KHÔNG được là người đã nhập số bên `sx`.**

Lộ trình dài hạn: chuyển dần từng card về đúng tổ sản xuất — chỉ cần sửa `sx/config/roles.py`
(ROLE_VIEWS / VIEW_CARDS / CARD_ROLES), KHÔNG sửa UI, KHÔNG sửa từng method API.

## Cài vào SITE MỚI — thứ tự đầy đủ

Bỏ sót một bước ở đây thì triệu chứng hiện ra ở tận bước sau và trông không liên quan
gì tới nguyên nhân, nên làm đúng thứ tự.

```bash
# 0. ERPNext phải có trước (required_apps = frappe + erpnext)
cd ~/frappe-bench
bench get-app https://github.com/mrhuychien/sx
bench --site $SITE install-app sx
bench build --app sx
```

**1. Dữ liệu nền — dựng TRƯỚC khi seed** (trên Desk):

| Cần có | Ghi chú |
|---|---|
| Company | |
| 4 Warehouse | NVL · BTP · TP · Xưởng |
| `SX Settings` | Công ty + 4 kho + `Tên miền cho email tài khoản` (bỏ trống = `sx.local`, **đừng dùng tên miền thật đang nhận thư**) |

Thiếu `SX Settings` thì seed dừng và nói thiếu ô nào — nó không đoán.

**2. Seed định mức** (Item + BOM tầng 1/2) — xem mục dưới.

**3. Module QC (BM.08.01 / BM.08.02)** — mở `SX QC Setting` trên Desk:

- **`Nhóm hàng bắt buộc có COA vi sinh`** — khai bằng Item Group thật trên site (dừa sấy /
  sữa bột / phụ liệu bột). **Bỏ trống thì luật COA KHÔNG chạy**, cố ý: đoán vài tên nhóm
  thì hoặc chặn nhầm hàng tốt, hoặc cho qua đúng thứ cần chặn.
- Ngưỡng có sẵn mặc định an toàn (rang ≥ 255 °C, trần vận hành 270, vòng quay 6,2–7,0,
  thùng bột quá hạn 0, ghi muộn 45 phút, sự cố quá hạn 7 ngày). Kiểm lại cho khớp nhà máy.
- **Một ngày ba lượt** (D95, không chia ca): hạn chót *Đầu sáng* 08:30 · *Trưa* 14:00 ·
  *Cuối chiều* 20:00. Khung của mỗi lượt bắt đầu từ hạn chót lượt trước, nên làm Trưa lúc
  07:00 cũng bị gắn cờ — đó là ghi sớm cho xong, không phải kiểm trưa.
- **Ngưỡng rang lạc để TRỐNG** cho tới khi thẩm định xong. Trống thì hệ thống chỉ ghi số,
  không tự sinh sự cố — bịa ngưỡng ra để "có cho đủ" là sinh báo động giả mỗi ngày rồi
  không ai đọc sổ sự cố nữa.

**4. Gán role.** 9 role ship sẵn qua fixtures; gán cho đúng người:

`SX Ghi So` · `SX Vao Hop` · `SX Thu Kho` · `SX Quan Ly` ·
`SX QC` · `SX QC Packing` · `ISO Manager` · `Production Manager` · `Warehouse`

Frappe cộng dồn role nên ai kiêm nhiều vai thì gán nhiều role — không chỗ nào trong code
giả định "mỗi người đúng một role". Tài khoản cho người ở xưởng tạo bằng **số điện thoại**
qua `Quản lý → Tài khoản portal` (xem mục dưới), không tạo tay trên Desk.

**5. Còn phải làm tay** — không có thì màn tương ứng trống hoặc chốt ngày bị chặn:

- **BOM tầng 3 + Item TP + bao bì** → chặn chốt ngày nhánh thành phẩm
- **Activity Type + `SX Bang Don Gia`** → không có thì bảng vào hộp trống
- Manufacturing Settings: Backflush = BOM, Overproduction 5%, **giữ tắt** *Validate
  Components Quantities Per BOM*
- Purchase Receipt NVL phải có batch = lô NCC (điều kiện FIFO truy xuất)
- Tồn đầu — chạy thử thì dùng `seed_ton_dau` ở mục dưới

**6. Kiểm lại:** mở `/sx` bằng một tài khoản đã gán role, thấy đúng số tab của vai đó.

## Deploy (sau mỗi lần pull code mới)

```bash
cd ~/frappe-bench/apps/sx && git pull && cd ~/frappe-bench
bench --site site1.local migrate      # CHỈ khi bản mới đổi DocType / patch / fixtures
bench restart                         # nạp lại Python — chỉ web + worker, KHÔNG đụng Redis
```

- **Không cần `bench build`.** App không đóng gói JS: `/assets/sx` là liên kết thẳng tới
  `sx/public`, sửa file là có ngay. `bench build` chỉ cần **một lần** lúc cài site mới.
- **Đừng dùng `sudo supervisorctl restart all`**: lệnh đó khởi động lại cả Redis cache — nơi
  giữ phiên đăng nhập đang chạy. `bench restart` thì không đụng Redis.
- Màn `/sx` tự báo khi máy đang chạy bản cũ (số build trên góc) — kéo xuống để tải lại.

**Vì sao trước đây mỗi lần deploy là người dùng bị đăng xuất (D105).** Role của app nằm
trong fixtures; Frappe nạp fixtures ở MỌI lần `migrate` bằng cách xoá rồi tạo lại từng
role. Tạo lại role là Frappe tính lại kiểu tài khoản (System / Website User) của mọi người
giữ role đó, và ai bị đổi kiểu là bị xoá hết phiên (`frappe/core/doctype/user/user.py`).
Từ D105 role không còn là fixture: `sx.setup.dam_bao_role` chạy sau install / migrate và
chỉ **tạo role còn thiếu**, không đụng role đã có — nên chỉnh Desk access cho một role
trên site cũng được giữ nguyên qua các lần deploy.

Muốn biết chắc ai bị đăng xuất và vì sao — Frappe ghi lý do vào Activity Log:

```bash
bench --site site1.local mariadb -e "select creation, subject from \`tabActivity Log\`
  where operation='Logout' order by creation desc limit 20;"
```

## Seed định mức (Item + BOM tầng 1/2) — ship sẵn trong app

Định mức đi kèm app (`sx/seed/rvhg_v6.json`, sinh tự động từ
`docs/RVHG_dinh_muc_BOM_v6.xlsx` — **16/16 câu hỏi đã chốt**). Sau khi có Company +
3 Warehouse + `SX Settings`:

```bash
bench --site $SITE execute sx.seed.seed_all                            # xem trước (mặc định)
bench --site $SITE execute sx.seed.seed_all --kwargs "{'dry_run': 0}"  # ghi thật
```

Tạo **49 Item** (14 đã có trên site → chỉ bù custom field; 35 tạo mới) + **21 BOM tầng 1/2**
(đúng thứ tự phụ thuộc: bột nền + đường hoán → bột bánh/bột đậu), submit +
active/default, điền `custom_co_me_chuan_kg` cho 19 loại được báo mẻ (BOM **đã có sẵn** mà thiếu
cỡ mẻ thì seed **bù + ghi cảnh báo**; nếu đã có số khác workbook thì giữ số trên site và cảnh
báo). **Idempotent** — chạy lại an toàn, không ghi đè số đã sửa tay. Seed **chặn ngay** nếu
Custom Field của app chưa sync (`bench migrate` trước), và **cảnh báo** khi item có sẵn đang tắt
`has_batch_no` / lệch `is_stock_item` / lệch ĐVT. BOM **không** ship qua `fixtures/` (import theo alphabet +
full validate + submittable → dễ chết `install-app`).

Tên item lấy theo tên **thật trên ERPNext** (cột A workbook), đã áp các quyết định đã chốt:
Sữa dừa = Bột sữa dừa, Đường kính VN = **Đường nghệ an**, Đường TQ = **Đường Gluco China**,
hương liệu quy **1 lít = 1 kg** (ĐVT Kg).

## Ai làm được gì

| | Ghi sổ | Ghi hộp | Nhập kho | QC | Quản lý |
|---|---|---|---|---|---|
| **SX Ghi So** | ✓ xuất đậu, báo mẻ, báo cán, sự cố | | | | |
| **SX Vao Hop** (QC vào hộp) | | ✓ chấm hộp, ăn ca | ✓ **lập + sửa phiếu NHÁP** | | |
| **SX Thu Kho** | | | ✓ đếm lại, **DUYỆT**, huỷ phiếu đã duyệt | | |
| **SX QC** (QC chế biến) | | | | ✓ đi lượt, **chốt lượt**, ghi xử lý sự cố | |
| **SX QC Packing** (QC đóng gói) | | | | ✓ ghi mục đóng gói — **không chốt lượt** | |
| **Production Manager** | | | | ✓ đọc, ghi xử lý sự cố | |
| **ISO Manager** | | | | ✓ **đóng sự cố**, ký đã xem xét, dashboard | |
| **Warehouse** | | | | ✓ kiểm nguyên liệu đầu vào trên Purchase Invoice | |
| **SX Quan Ly** | ✓ | ✓ | ✓ | ✓ | ✓ chốt ngày, dashboard, truy xuất, tài khoản |

Thêm hai tab cho mọi vai: **📚 Tài liệu** (W42 — thấy tài liệu phân phối cho mình) và **📒 Sổ** (W43 — chỉ hiện khi
được giao ít nhất một sổ; quyền ghi / xác nhận / xem theo từng sổ). Vai mới C24 `SX Co Dien`, `SX Hanh Chinh`,
`SX Bao Ve` chỉ có hai tab này — xem mục D171, D172. Mua hàng (`Purchase User`) có tab Sổ để lập phiếu đánh giá nhà
cung cấp BM.07.01 (D173). Biên bản (D174): ai có ô ký thấy "Chờ tôi ký" ở đầu màn Tài liệu và tab Biên bản ở đó.

**QC chế biến ≠ QC vào hộp** — hai người, hai việc, hai role. Ai làm cả hai thì gán cả hai.

**Ghi được ≠ chốt được**: QC đóng gói ghi mục 11–13 trên bản nháp của người khác, nhưng
người chốt lượt phải là người đã đi hết lượt đó.

**Người ghi không tự duyệt**: QC không duyệt phiếu nhập kho mình lập; QC không đóng được
phiếu sự cố. Cả giá trị của mấy bước đó nằm ở chỗ người duyệt khác người lập.

**Báo sự cố là việc của tổ Ghi sổ**, không nằm trên màn của QC — màn Ghi hộp chỉ còn
đúng việc chấm hộp.

**QC không tự duyệt được phiếu mình lập** — cả giá trị của bước kiểm đếm nằm ở chỗ
người duyệt khác người lập. QC **xoá được phiếu nháp của chính mình** (chưa có gì vào
kho); huỷ phiếu **đã duyệt** là thu hồi chứng từ kho nên chỉ thủ kho/quản lý.

Ma trận này có bài kiểm riêng: `scripts/test-quyen.py`, `verify.sh` gọi sẵn. Nó cũng
chốt rằng **mọi method whitelist đều có guard** — thêm một method quên `guard_card`
là mở một cửa hậu im lặng.

## Menu tài khoản (nút chữ viết tắt trên header)

Cạnh nút chọn mùa có nút tài khoản — chữ viết tắt tên người đang đăng nhập. Điện thoại
xưởng hay chuyền tay giữa hai QC, nên **ai đang cầm máy phải nhìn thấy được ở mọi màn**.
Bấm vào: tên, số điện thoại, vai trò; *Đổi mật khẩu*; *Mở Desk* (chỉ người có quyền
Desk); *Đăng xuất*.

**Đăng xuất khi còn thao tác chưa gửi** (mất mạng lúc ghi) thì không đăng xuất trơn:
chọn *gửi ngay rồi đăng xuất*, hoặc *bỏ các thao tác đó* qua hai bước xác nhận. Lý do:
hàng chờ ngoại tuyến nằm trong trình duyệt chứ không nằm trong tài khoản. Từ D96 mỗi thao
tác xếp hàng ghi tên người xếp, và app **không bao giờ gửi thao tác của người này dưới tên
người khác** — người sau đăng nhập vào cùng máy sẽ thấy nó bị giữ lại, chờ đúng chủ đăng
nhập lại để gửi. Đăng xuất cũng xoá bản số liệu lưu trên máy của người vừa ra.

## Tài khoản cho QC (`Quản lý → Tài khoản portal`)

Xưởng không có email, nên tài khoản định danh bằng **số điện thoại** — số đó vừa là
tên đăng nhập, vừa là thứ họ vốn đã nhớ.

Nhập số → app tự đặt mật khẩu và cấp một **mã QR đăng nhập** → bấm **IN THẺ** → đưa
tận tay. QC quét QR là vào thẳng portal, không gõ gì.

- **Mã QR dùng được MỘT lần** và hết hạn sau 14 ngày. Tờ giấy có QR đăng nhập là giấy
  tờ tuỳ thân: rơi ra ngoài thì ai nhặt được cũng vào được. Một lần + có hạn giới hạn
  thiệt hại, và còn để lại dấu — QC bảo "quét không vào" nghĩa là có người quét trước.
- **Mật khẩu là đường vào lâu dài**, in cùng trên thẻ, dùng mãi.
- Mật khẩu và QR **chỉ hiện đúng một lần** ngay sau khi tạo (Frappe lưu băm, không ai
  đọc lại được). Lỡ đóng thì bấm **Cấp lại** — mật khẩu mới, thẻ mới.
- Chỉ gán được **role của app này** (QC vào hộp / Ghi sổ / Thủ kho / Quản lý). Không
  tạo được System Manager, và không sửa được tài khoản không thuộc app.
- Tên miền ghép vào email giả khai ở `SX Settings → Tên miền cho email tài khoản`
  (bỏ trống = `sx.local`). **Đừng dùng tên miền thật đang nhận thư.**

## Nhập kho thành phẩm CHƯA có BOM — sổ nợ BOM (D97)

Trước D97 một mã hàng mới chưa kịp làm định mức là thủ kho **không duyệt được** phiếu
nhập, hàng đứng ngoài kho, và người ta tìm cách lách. Giờ:

| Dòng trên phiếu | Lúc duyệt |
|---|---|
| **có BOM** | như cũ: Work Order + Manufacture, trừ bột + bao bì |
| **chưa có BOM** | vẫn **nhập kho** (Material Receipt, có lô theo ngày) nhưng **CHƯA trừ nguyên liệu** — ghi một dòng vào **sổ nợ BOM** (`SX No BOM`) |

Màn nhập kho gắn nhãn *chưa có BOM* ngay trên dòng, và câu xác nhận lúc duyệt nói rõ
mã nào sẽ ghi nợ — thủ kho không phát hiện sau qua một dòng lạ.

**Sổ nợ BOM** (card trên màn Nhập kho và Quản lý, tự ẩn khi không nợ gì) gom theo mã hàng:

- **Hạch toán bù** — khi mã đó đã có BOM. Trừ bột + bao bì theo BOM × số đã nhập, mỗi lần
  nhập một phiếu kho riêng. Kiểm tồn gộp trước; thiếu thì không ghi gì cả.
- **Bỏ qua** — từng dòng, **bắt buộc lý do** — khi thật sự không có tiêu hao (hàng trả
  về nhập lại…).
- Chỉ **Quản lý** xử lý; thủ kho xem được.
- Huỷ phiếu nhập thì nợ → *Đã huỷ*; nợ đã bù thì huỷ luôn phiếu trừ bù.

**Hai cái giá phải trả, biết trước để không bất ngờ:**

1. **Tồn bột / bao bì trên sổ cao hơn thực tế** đúng bằng phần đang nợ, cho tới khi bù.
   Nợ quá 7 ngày card tô đỏ.
2. **Lô thành phẩm nhập tạm không truy ngược được tới đúng lô bột** đã dùng: lúc bù,
   nguyên liệu trừ theo FIFO ở ngày bù chứ không phải ngày sản xuất. Và nếu mã hàng chưa
   có giá vốn nào, lô đó vào kho **giá 0** (không bịa giá) — card ghi rõ để kế toán biết.

BTP (báo mẻ) **vẫn bắt buộc BOM** — không phải vì cứng nhắc: số kg của một mẻ được tính
từ cỡ mẻ ghi trên BOM, không có BOM thì không có con số nào để ghi.

## Vào hộp mã CHƯA có đơn giá — sổ nợ đơn giá (D99)

QC ghi được mã chưa khai giá từ trước (chặn giữa xưởng là dừng chuyền), nhưng chốt Vào
hộp xong thì lương khoán mã đó nằm trong phiếu lương tháng ở **0 đồng** và không ai nhớ
phải bù. Giờ lúc **chốt Vào hộp**, mỗi (ngày, mã hàng, cách làm) không tra được giá ghi
một dòng vào **sổ nợ đơn giá** (`SX No Don Gia`), và hộp cảnh báo sau khi chốt nói rõ mã nào.

**Sổ nợ đơn giá** (card màn Quản lý, tự ẩn khi không nợ gì) gom theo mã + cách làm:

- **Khai giá ở `SX Bang Don Gia`** — đúng **bảng áp dụng cho ngày sản xuất** (card ghi tên
  bảng). Giá ở bảng hiệu lực *sau* ngày đó không được tính: chốt lại ngày đó sẽ tra bảng
  cũ, hai con số sẽ lệch. Không có ô gõ giá tay ở card — một nguồn giá duy nhất.
- **Áp giá** — điền giá vào đúng những dòng 0 đồng của ngày đó trong phiếu lương tháng
  (và bảng vào hộp đã chốt, tổng lương phiếu ngày) — không phải huỷ chốt cả ngày.
  Dòng đã có giá không bị đè.
- Phiếu lương **đã duyệt** thì không áp (báo tên phiếu) — huỷ duyệt trước. Ngược lại,
  **không duyệt được phiếu lương** còn dòng đang nợ giá: duyệt là khoá cứng 0 đồng.
- **Bỏ qua** — từng ngày, **bắt buộc lý do** (hàng mẫu, làm thử…) — giữ 0 đồng.
- Huỷ chốt Vào hộp / huỷ chốt ngày: nợ đang mở → *Đã huỷ*; chốt lại tra giá từ đầu.
- Chỉ **Quản lý** xem và xử lý.

## Thẻ Phiếu lương trên màn Quản lý (D110)

Thẻ **💰 Phiếu lương** (gập sẵn, sau thẻ Chốt ngày), chỉ Quản lý. ‹ › đổi tháng; tổng
thực nhận / lương SP / số phiếu đã duyệt; ô tìm tên; mỗi người một dòng (thực nhận, lương
SP, ngày công, nhãn *đã duyệt* / *nợ giá*). Bấm một người → các khoản (cộng → tổng thu
nhập → trừ → thực nhận), sản phẩm trong tháng gộp theo mã (số lượng × đơn giá), từng ngày
(ăn ca/đêm, hệ số Chủ nhật), lỗi phạt; nút **Mở trên Desk để sửa / duyệt**.

Chỉ đọc: số lấy nguyên từ phiếu (không tính lại), phiếu đã huỷ không tính. Sửa / duyệt
vẫn trên Desk (`sx/api/luong.py`).

## Lịch tháng ở tab Ghi hộp / Ghi sổ / Nhập kho (D108)

Cuối mỗi tab có thẻ **📅 … cả tháng** (gập sẵn, bấm để mở — nhớ trạng thái mở theo tab).
Ô ngày chỉ hiện **một con số**; ô trống = chưa ghi; viền xanh = đã chốt; ‹ › đổi tháng.

| Tab | Ô ngày | Bấm vào ngày |
|---|---|---|
| Ghi hộp | số hộp (khoán + công nhật) | theo mã (tách khoán / công nhật), theo người, trạng thái chốt — nút **Mở ngày này để sửa** |
| Ghi sổ | số mẻ trộn | báo mẻ (mẻ, kg), báo cán, rang đỗ, số sự cố — nút **Mở ngày này để sửa** |
| Nhập kho | số đã nhập (chỉ phiếu **đã duyệt**) | theo mã, từng phiếu |

Phiếu ngày / bảng / phiếu nhập đã huỷ không tính. Chỉ đọc; ai vào được tab nào thì xem
được lịch tab đó (`sx/api/lich.py`).

## Huỷ phiếu nhập kho đã duyệt (D104)

Màn Nhập kho → **Phiếu đã duyệt gần đây** → bấm một phiếu → xem chi tiết. Thủ kho /
quản lý có hai nút (QC chỉ xem):

- **HUỶ & LẬP LẠI** — huỷ rồi lập ngay phiếu nháp mới chép sẵn các dòng (cùng ngày), sửa
  số sai rồi duyệt lại. Dùng cho lý do hay gặp nhất: đếm sai một dòng. Ẩn khi đang có
  phiếu nháp khác (mỗi lúc chỉ một phiếu nháp).
- **HUỶ PHIẾU** — chỉ huỷ.

Cả hai **bắt buộc lý do** (ghi vào phiếu). Huỷ = rút hàng khỏi kho TP, trả lại bột +
bao bì đã trừ, nợ BOM / nợ vào hộp của phiếu → *Đã huỷ*, số "chờ nhận" hiện lại.
**Kiểm trước** hàng còn đủ trong kho (theo lô; mã không lô theo tồn mã): đã bán / xuất
bớt thì không huỷ, báo rõ mã, lô, còn bao nhiêu — phải huỷ chứng từ xuất trước. Duyệt lại
trong ngày ra **đúng mã lô cũ** (lô của phiếu đã huỷ không còn hàng thì được dùng lại),
không thành `…-2`.

## Nạp bộ tài liệu lần đầu gọn lại: một nút danh mục, chọn thẳng tai_lieu_pdf.zip (D180)

Màn 📦 NẠP BỘ TÀI LIỆU (Tài liệu → Ban hành, `#/tailieu/nap`) trước đây bắt Ban ISO tự tìm và chọn 3 tệp kỹ thuật
`.json`, giải nén `tai_lieu_pdf.zip` rồi chọn cả 88 tệp, tải lại trang giữa chừng là mất chỗ dở (phải bấm lại bước 1
mới tải tiếp được), nút NẠP BỘ thì nằm đó mãi kể cả khi đã nạp xong. Giờ:

- **Danh mục đi kèm app** — sổ đăng ký 21/9/2026, BM.01.03, Phụ lục 3 chuyển từ `scripts/du_lieu/seed_*.json` vào
  `sx/qc/seed/` (`tai_lieu.json`, `tai_lieu_ngoai.json`, `phan_phoi.json`). Bước ① chỉ còn một nút **NẠP DANH MỤC**,
  không chọn tệp nào. Ô "Tạo yêu cầu Đã đọc, hiểu" mặc định tắt (đã phổ biến bản giấy 22/9).
- Bước ② **chọn thẳng `tai_lieu_pdf.zip`, không cần giải nén** — app mở zip ngay trên máy (`lib/zip.js`, không thư
  viện ngoài), khớp tên, tải lần lượt những tệp còn thiếu (≤ 10 MB/tệp, kiểm chữ ký đầu tệp như cũ). Vẫn chọn được các
  tệp PDF, PNG rời. Chọn zip khi chưa nạp danh mục → app tự nạp danh mục luôn.
- **Mở màn là thấy đã tới đâu** (`tinh_trang_nap`, chỉ đọc): x/y tài liệu nội bộ, bên ngoài, nơi nhận, đợt 21/9, x/y
  tệp và tên các tệp còn thiếu. Tải lại trang, mở lại hôm sau vẫn đúng chỗ dở.
- Nạp đủ → "✓ Đã nạp đủ bộ tài liệu", nút 📦 NẠP BỘ ở tab Ban hành / Tất cả **ẩn đi**.
- Zip có mật khẩu, ZIP64, trình duyệt quá cũ → báo rõ; khi đó giải nén rồi chọn các tệp như trước.
- `nap_bo(payload)` vẫn nhận một bộ seed khác `{tai_lieu, ngoai, phan_phoi}` (bench / test); bỏ trống = bộ đi kèm app.
- Build **sx-141**. Không đổi DocType: `git pull` → `bench restart` (không cần migrate). Test: `test-tailieu.py`,
  `test-tailieu.mjs` (zip thật: nén / không nén, thư mục, tệp lạ, tệp quá 10 MB, zip hỏng).

## Dữ liệu mẫu bỏ ghi chú từng bản ghi; tờ in site thử có một dòng nhận biết (D179)

- Bản ghi do lệnh dữ liệu mẫu (D177) sinh ra **không còn** ghi chú "Dữ liệu mẫu (site thử)", tiền tố "[Dữ liệu mẫu]" ở
  phiếu sự cố, chữ "(mẫu)" ở tên người làm / chỗ phơi / vị trí tủ mẫu — màn hình tập huấn trông như ghi thật. Hai tài
  khoản mẫu tên gọn **QC Mẫu**, **Ban ISO Mẫu** (tài khoản tạo trước D179 tự đổi tên khi chạy lại `tao`).
- Thay vào đó, **site bật cờ `sx_du_lieu_mau`** (chỉ site thử) in **một dòng** trên đầu mọi tờ in — "Bản in từ site thử —
  có dữ liệu mẫu, không phải hồ sơ chính thức" — và ở đầu Mục lục / bìa của tệp xuất Excel / PDF. Tờ giấy rời khỏi máy
  vẫn tự nói nó từ site thử. Site thật không có cờ → không bao giờ hiện (`sx/qc/mau_in.py`, macro đầu trang chung).
- Site thử đã chạy lệnh trước D179: xoá rồi sinh lại — cùng hạt nên ra đúng số cũ, chỉ bỏ ghi chú:
  `… execute sx.seed.du_lieu_mau.xoa --kwargs "{'dry_run': 0}"` rồi `… execute sx.seed.du_lieu_mau.tao --kwargs "{'dry_run': 0}"`.
- Không đổi DocType, không đổi JS. Test: `test-dulieumau.py`, phần site thử trong `test-xuatbc.py`.

## Truy xuất: lượt lệch theo luật sự cố, cát / vải ủ ngày rang, phiếu BM.08.04 của lô (D178)

Hồ sơ một lô (thẻ Truy xuất ở màn Quản lý, màn ISO) và phụ lục diễn tập BM.02.04:

- **Lượt QC "đạt hết" phải là đạt hết thật.** Trước đây màn chỉ dò chữ "Không đạt" — lượt rang 235 °C, nam châm bắt
  mạt kim loại, thùng bột quá hạn, dị vật trên rây, thử nhanh lạc dương tính vẫn hiện "✓ đạt hết" (phiếu sự cố nằm
  riêng bên dưới). Giờ chỗ lệch tính bằng **đúng luật sinh sự cố** của vòng kiểm (`sx/qc/su_co.phat_hien`) — hiện
  "Lệch: …" bằng câu đọc được, lệch mức Cao ghi "Lệch mức CAO". Lượt nháp: tính trên những gì đã ghi.
- **Ngày rang** có thêm hai dòng PRP của công đoạn rang – ủ:
  - 🔥 **Cát rang** (BM.08.03): cát trong máy đã dùng bao nhiêu ngày tới hôm đó, nguồn cát, kết quả kim loại nặng của
    lần đổi sang nguồn đó; quá số ngày tối đa (Setting) / sổ không có cát đang dùng hôm đó thì báo đỏ. Xưởng chưa dùng
    sổ cát thì không hiện gì.
  - 🧺 **Vải ủ** (BM.08.05): lần giặt gần nhất tới hôm đó (theo luật chu kỳ của sổ), cách mấy ngày, đun sôi mấy phút,
    QC đã ký chưa, quá chu kỳ chưa. Chưa khai vải thì không hiện gì.
- **Khối 🧾 Kiểm tra xuất xưởng BM.08.04** của lô thành phẩm: mọi phiếu theo (sản phẩm, HSD), cũ trước — trạng thái,
  kết luận, QC kiểm / người duyệt và giờ, mục Không đạt, phiếu sự cố, ý kiến duyệt. Lô chưa có phiếu: ghi rõ.
- **Diễn tập BM.02.04**: ảnh chụp lúc kết thúc lưu thêm phiếu BM.08.04; phụ lục in "lệch: …", cát / vải ngày rang và
  mục "4. Kiểm tra xuất xưởng" (truy xuôi thành mục 5). Ảnh chụp diễn tập cũ in như trước.
- Build **sx-140**. Không đổi DocType: `git pull` → `bench restart` (không cần migrate). Test: `test-truyxuat.py`.

## Dữ liệu QC mẫu 22/9 → nay cho site THỬ (D177)

Để tập huấn QC / Ban ISO, xem màn ISO, thử xuất báo cáo Excel / PDF với số liệu đủ một tháng. **Không bao giờ chạy trên
site thật**: hồ sơ do máy sinh nằm cạnh hồ sơ thật là hồ sơ giả — tờ in ra không khác tờ QC ghi. Lệnh tự dừng nếu
site là `site1.local`, hoặc site chưa bật cờ `sx_du_lieu_mau` trong site_config (cả xem trước lẫn xoá).

**Dựng site thử từ bản sao lưu** (trong `~/frappe-bench`; site thật vẫn chạy bình thường):

```bash
bench --site site1.local backup --with-files            # 3 tệp mới nhất trong sites/site1.local/private/backups/
bench new-site sx-thu.local --admin-password '<mk>' --db-root-password '<mk root MariaDB>'
bench --site sx-thu.local restore sites/site1.local/private/backups/<…>-database.sql.gz \
  --with-public-files sites/site1.local/private/backups/<…>-files.tar \
  --with-private-files sites/site1.local/private/backups/<…>-private-files.tar --db-root-password '<mk root>'
bench --site sx-thu.local migrate
bench --site sx-thu.local set-config mute_emails 1      # site thử có người dùng thật: không gửi thư
bench --site sx-thu.local scheduler disable             # không chạy việc nền (nhắc, đồng bộ) trên bản chép
bench --site sx-thu.local set-config sx_du_lieu_mau 1   # cờ dữ liệu mẫu — CHỈ site thử
```

Mở site thử bằng đúng tên `sx-thu.local`: máy tính thêm dòng `<IP máy chủ> sx-thu.local` vào tệp hosts (máy chủ có
nginx thì `bench setup nginx` rồi `sudo systemctl reload nginx`). Đăng nhập như site thật (bản sao mang theo tài khoản).

**Chạy** (gọi trần = xem trước, như seed định mức):

```bash
bench --site sx-thu.local execute sx.seed.du_lieu_mau.tao                              # XEM TRƯỚC: in kế hoạch
bench --site sx-thu.local execute sx.seed.du_lieu_mau.tao --kwargs "{'dry_run': 0}"    # GHI
bench --site sx-thu.local execute sx.seed.du_lieu_mau.xoa --kwargs "{'dry_run': 0}"    # XOÁ toàn bộ dữ liệu mẫu
```

Tham số: `tu` (mặc định `'2026-09-22'`), `den` (mặc định hôm nay), `su_co` (số phiếu sự cố mẫu, mặc định 2), `phan`
(`'luot,su_co,cat,vai,xuat'` — chọn phần), `chu_nhat` (1 = Chủ nhật cũng làm), `hat` (đổi số ngẫu nhiên).

- **Ngày nào đã có thì thôi**: ngày đã có lượt kiểm (thật hay mẫu) không sinh lượt; sổ cát chỉ sinh trước dòng thật đầu
  tiên trong kỳ; tuần đã có lần giặt vải, lô đã có phiếu xuất xưởng / mẫu lưu thì bỏ qua. Chạy lại không đẻ thêm gì.
- **BM.08.01**: thứ Hai → thứ Bảy, ba lượt (thứ Hai lượt Tuần thay Đầu sáng; hôm nay chỉ lượt đã qua giờ), ghi đủ mọi mục
  áp dụng, số trong ngưỡng SX QC Setting; bột thứ Ba / Năm / Bảy (thứ Năm sáng làm vị có lạc → B1, B2, trưa thử nhanh lạc
  B7 âm tính); T4 theo từng vật BM.PRP.05; bộ mục theo **phiên bản của ngày đó** (bản 1 trước 08/10, 2 ngày 08/10, 3 từ
  09/10 — tờ tháng 9 không có ô NC-02); Ban ISO mẫu xem xét các tuần đã qua.
- **BM.08.02**: 2 phiếu sự cố sinh đúng luật từ lượt kiểm (lưới sàng không đạt, thùng bột quá hạn) — QC mẫu ghi xử lý,
  Ban ISO mẫu đóng sáng hôm sau.
- **BM.08.03** nhật ký cát: nhập + rang khô đưa dùng (máy chưa có cát), bổ sung mỗi 6 ngày rang (app tự đếm), vệ sinh
  thùng / khay thứ Bảy, thay cát khi đủ số ngày tối đa ở Setting. **BM.08.05**: giặt định kỳ mỗi tuần đúng ngày giặt ở
  Setting (trống = thứ Bảy), QC ký, Ban ISO xem tháng đã qua; danh mục vải trống thì khai 4 vải mẫu V01-A … V02-B.
- **BM.08.04 + sổ lưu mẫu**: lô của phiếu nhập kho **đã duyệt** trong kỳ chưa có phiếu: lấy mẫu lưu, QC kiểm (A theo gợi
  ý hồ sơ lô, B2 cân quanh khối lượng trên quy cách), Ban ISO duyệt — giờ đặt trước lúc thủ kho duyệt phiếu nhập (đúng
  luồng thật). Lô mà hồ sơ gợi ý Không đạt (vd sự cố chưa quyết định) thì bỏ, không bấm Đạt đè lên.
- **Không sinh**: sản lượng (báo mẻ, phiếu kho, nhập kho — chỉ đọc phiếu nhập để biết lô), tiếp nhận NL, kiểm xe, thiết
  bị đo (hạn đầu 31/10/2026), động vật gây hại, sổ ghi theo dòng, biên bản, kiểm nghiệm.
- Ghi qua đúng API của màn QC (dữ liệu mẫu qua mọi luật như QC bấm thật), rồi chỉnh giờ (bắt đầu / hoàn tất lượt, giờ
  từng ô, ký, duyệt) về đúng ngày, trong khung lượt. Mọi bản ghi của hai tài khoản mẫu `qc.mau@sx.local`,
  `iso.mau@sx.local` (không mật khẩu, tên "QC Mẫu", "Ban ISO Mẫu") — `xoa` xoá đúng theo hai tài khoản đó, kể cả dòng
  con, rồi xoá hai tài khoản. Từ D179 bản ghi không mang ghi chú "dữ liệu mẫu" (xem mục D179).
- Code: `sx/seed/du_lieu_mau.py` (không whitelist — chỉ chạy bằng `bench execute`). Không đổi DocType, không đổi JS:
  site thật **không cần** migrate / build gì. Test: `test-dulieumau.py`.

## Màn ISO riêng, xuất báo cáo Excel / PDF cho đoàn, bản scan tài liệu (D176)

**Lên main 10/10/2026 cùng đợt D171–D176.** Có DocType mới, ô mới → phải
`bench --site site1.local migrate`.

- **Màn ISO** (tab dưới 🛡️ ISO, `#/iso`) — Trưởng Ban ISO mở app là vào đây; quản lý cũng thấy. Tab: Tổng quan ·
  Xem xét tháng · Báo cáo · **Xuất báo cáo** · Hồ sơ đánh giá · Biên bản · Truy xuất · Tài liệu (sang thư viện). Các màn
  con dùng lại đúng màn cũ (một chỗ code, `sx/public/sx/views/iso.js`).
- **Màn QC giữ việc nhập liệu**: người có màn ISO không còn tab Xem xét / Truy xuất ở QC. Đường cũ `#/qc/attp`,
  `#/qc/review`, `#/qc/bienban/<x>`… (hộp nhắc, thẻ Tổng quan, trang đã đánh dấu) tự chuyển sang `#/iso/…`; người không
  có màn ISO (QLSX, QC mở biên bản phải ký) vẫn xem trong QC như cũ.
- **Xuất báo cáo cho đoàn kiểm tra** (`#/iso/xuat`): chọn biểu mẫu (theo nhóm của danh mục hồ sơ BM.01.04, ô tìm, chọn
  cả nhóm; mỗi biểu mẫu ghi sẽ ra tờ nào) + kỳ (chọn nhanh tháng / quý / năm, tối đa 24 tháng) + ghi chú đoàn → **Excel**
  hoặc **PDF**. Nội dung là chính bản in của từng biểu mẫu — cùng tờ trong gói zip (`qc_hoso._in`), không có bản số liệu
  thứ hai để lệch với giấy.
  - Excel: sheet **Mục lục** (kỳ, người xuất, ghi chú; mỗi biểu mẫu → các tờ, bấm sang sheet; kỳ trống / in lỗi ghi rõ)
    + mỗi tờ in một sheet dựng lại đúng bảng: ô gộp, tiêu đề đậm, ô chắc là số thì thành số; chữ "=…" giữ là chữ (không
    thành công thức trong Excel của đoàn); thiết lập in A4 ngang / dọc theo tờ.
  - PDF: một tệp — bìa mục lục có số trang + bookmark từng biểu mẫu; mỗi biểu mẫu dựng đúng khổ tờ in (A4 ngang / dọc,
    lề theo `@page`), bảng rộng thu nhỏ cho vừa. Dùng wkhtmltopdf của Frappe (như in PDF trên Desk) — máy chủ thiếu thì
    lần xuất PDF báo Lỗi kèm lý do, Excel vẫn xuất được.
  - Dựng **nền** (job hàng `long`): lần xuất hiện ngay ở "Các lần xuất" — Đang chờ / Đang tạo → Xong (**TẢI VỀ**) / Lỗi
    (lý do, LÀM LẠI). Hàng đợi máy chủ không chạy thì sau 20 giây có **CHẠY NGAY**. Một biểu mẫu in lỗi không làm hỏng cả
    tệp. Mỗi lần xuất được giữ lại (DocType `SX Xuat Bao Cao`): ai, lúc nào, kỳ, biểu mẫu, cho đoàn nào; xoá được (cả tệp).
  - Luật dựng ở `sx/qc/xuat_bao_cao.py` (hàm thuần), API `sx/api/qc_xuatbc.py` (Trưởng Ban ISO, quản lý).
- **Bản scan tài liệu** (thư viện `#/tailieu`): mỗi tài liệu có ô **bản scan bản gốc đã ký, đóng dấu** (PDF / ảnh
  ≤ 10 MB). Trưởng Ban ISO gắn / thay / bỏ ở chi tiết tài liệu (ghi người + giờ gắn); ai xem được tài liệu thì mở được bản
  scan. Tab Tất cả: đếm bản scan "đã có / cần có", lọc **Chưa có bản scan**, thẻ ghi có / chưa có. Ban hành bản mới thì
  bản scan cũ vào lịch sử cùng bản cũ (Ban ISO mở được), bản mới chờ scan mới; lịch sử không sửa tay được.
- Build **sx-139**. Deploy (cùng đợt D171–D176): `git pull` → `bench --site site1.local migrate` → `bench restart`.
- Test: `test-xuatbc.py` (Excel thật bằng openpyxl — máy test thiếu thì `pip install --user openpyxl`; PDF giả lập),
  `test-iso.mjs`, phần bản scan trong `test-tailieu.py` / `test-tailieu.mjs`.

## Sửa lỗi migrate ở patch d161 (D175)

- Patch `d161_rang_240_280` đổi công đoạn "9 Trộn" → "9 Nấu đường, trộn" bằng
  `frappe.rename_doc(..., ignore_permissions=True)`. Hàm `frappe.rename_doc` công khai của Frappe (v15, v16)
  **không có** tham số `ignore_permissions` (chỉ hàm bên trong `frappe.model.rename_doc` có), nên `bench migrate`
  **dừng ở patch d161** với `TypeError: rename_doc() got an unexpected keyword argument 'ignore_permissions'`.
  Đã bỏ tham số đó — migrate chạy bằng Administrator nên không cần; `force=True` giữ nguyên; tắt thông báo và việc
  dựng lại tìm kiếm (không đẩy việc vào hàng đợi giữa lúc migrate).
- Bài test cũ thay `frappe.rename_doc` bằng hàm giả nhận mọi tham số (`**k`) nên lỗi lọt qua. Hàm giả giờ có
  **đúng chữ ký v16** — truyền tham số lạ là test đỏ như trên site. Đã rà mọi lời gọi hàm Frappe / ERPNext trong app
  với chữ ký bản v16: chỉ có chỗ này sai.
- Lần migrate hỏng đã rollback patch d161 (Frappe chỉ ghi Patch Log khi patch chạy xong; patch chạy lại vô hại) nên
  chỉ cần: `git pull` → `bench --site site1.local migrate` → `bench restart`. Lần này chạy lại d161 rồi d162 … d169,
  đồng bộ fixtures và các hook sau migrate.
- Kiểm sau migrate (`bench --site site1.local console`):
  `frappe.db.exists("Patch Log", {"patch": "sx.patches.d169_bo_thau_rua_be"})` có;
  `frappe.db.exists("SX QC Cong Doan", "9 Nấu đường, trộn")` có (trừ khi site đã tự đặt tên khác cho công đoạn 9);
  `frappe.db.get_single_value("SX QC Setting", "rang_nhiet_min")` là 240 (hoặc số site đã tự chỉnh).

## Khung Biên bản — họp Ban ISO, xem xét lãnh đạo, đánh giá nội bộ, thẩm tra, HACCP, thu hồi, diễn tập (D174 — W45)

**Lên main 10/10/2026 cùng đợt D171–D176** (C22 định để sau đợt Orion kiểm tra lại; đưa lên sớm theo yêu cầu). Có DocType mới → phải `bench --site site1.local migrate`.

- **18 phiếu giấy là dữ liệu, không phải 18 màn**: `SX Mau Bien Ban` (phần + ô ký + vai lập / xem), seed
  `sx/qc/seed/bien_ban.json` (soạn từ `seed_bieu_mau_giay.json`), patch `d174_bien_ban` tạo mẫu còn thiếu (mẫu Ban ISO
  đã sửa trên Desk không đè). Kiểu phần: **Văn bản** (ô), **Bảng** (dòng in sẵn chỉ là gợi ý — sửa, thêm, xóa),
  **Danh sách kiểm** (câu in sẵn không sửa / bỏ được, kết luận ≤ 3 lựa chọn là nút), **Kéo dữ liệu** (bản chụp lúc lập),
  **Việc giao**. Hàm kéo / hàm tính là khóa cố định trong `sx/qc/bien_ban.py` (`NGUON`, `TINH`) — không chạy biểu thức.
- **Biên bản** `SX Bien Ban` (`BB-.YYYY.-.####`, số riêng theo mẫu: `01/BB-ISO`, `01/KHTHSP`, `01/2026`…): Nháp → Chờ ký
  → Đã ký đủ; người đang tới lượt ký **trả lại** (bắt ghi ý kiến) → sửa, gửi lại (chữ ký vòng trước, bản scan bỏ). Lúc
  lập, các phần của mẫu được chép vào biên bản — sửa mẫu không đổi biên bản cũ. Desk chỉ đọc; ký đủ là khóa (cả API).
- **Ký** (C23): theo thứ tự ô; ô "người lập" (Thư ký, Người lập, Chuyên gia), ô có vai (Trưởng Ban ISO = ISO Manager,
  Giám đốc = SX Quan Ly, QLSX, QC, Thủ kho, Hành chính), ô trưởng đoàn = người trưởng đoàn trong kế hoạch ĐGNB; **một
  người không ký hai ô**. **Ký tay** (in, ký, tải scan — chưa có scan thì không khóa): BM.02.01, 02.02 (Giám đốc gửi ra
  ngoài), BM.PRP.02 (nhà thầu), BM.03.04 khi tích "có đơn vị PCCC bên ngoài".
- **Kéo dữ liệu** (bản chụp, "Kéo lại" chỉ khi Nháp / Trả lại): sự cố, khiếu nại trong kỳ (từ sau biên bản cùng mẫu
  lần trước), BM.01.07 quá hạn / chờ kiểm tra, nhắc mức cao, việc giao chưa xong của biên bản trước (họp Ban ISO kèm
  hành động BM.01.10), BM.01.12 tháng trước (họp đầu tháng — tích ô), kết quả BM.01.09, thay đổi tài liệu, rủi ro cấp
  độ 1, kiểm nghiệm trong năm, công đoạn theo dây chuyền, oPRP hiện hành, diễn tập truy xuất, lô thu hồi (đã bán theo
  khách, đã thu về), dấu hiệu động vật theo trạm.
- **Việc giao**: ký đủ thì mỗi dòng (và mỗi ô hạn: thẩm tra lại, diễn tập lại, kiểm lại sau dịch vụ…) thành một
  `SX Viec Dinh Ky` "Một lần" (hạn, người, hồ sơ = số biên bản) → hộp nhắc sẵn có. Việc định kỳ năm có ô hồ sơ đúng mã
  biên bản đóng việc (BM.01.10, BM.01.09, BM.04.02, BM.03.04, BM.02.05, BM.14.01) tự ghi "đã làm" khi biên bản ký đủ.
- **Dòng Không phù hợp** (KPH / Không / Không đạt / cần điều chỉnh) → nút **LẬP BM.01.07** (nguồn theo mẫu: Đánh giá
  nội bộ, Thẩm tra — nguồn mới của BM.01.07 —, Xem xét của lãnh đạo, Khác), gắn ngược vào phiếu liên quan.
- **Đánh giá nội bộ**: BM.01.05 (chuyên gia chọn theo tài khoản + bộ phận công tác; chặn chuyên gia đánh giá bộ phận
  mình, Trưởng Ban ISO làm trưởng đoàn; Giám đốc ký = chỉ định trưởng đoàn) → BM.01.06 (chỉ chuyên gia của kế hoạch đã
  duyệt; "Chép câu hỏi từ đợt trước"; giấy không có ô ký — app cho chuyên gia ký xác nhận) → BM.01.08 tự gom Lưu ý →
  BM.01.09 tự đếm KPH / Lưu ý theo bộ phận. BM.04.02 lập từ BM.04.01 đã duyệt; BM.02.02 từ BM.02.01; BM.02.05 từ 02.03.
- **BM.HACCP.01**: chọn dây chuyền → kéo danh mục công đoạn. Patch thêm 4 công đoạn bột theo sơ đồ 11 công đoạn
  KH.HACCP.02 mục 5.5 (bột đậu xanh / đậu đen bán thành phẩm, lưu kho, xuất hàng) và đổi thứ tự 7 công đoạn cũ theo sơ
  đồ (chỉ khi thứ tự vẫn của D130). Mốc bánh = danh mục lúc migrate (coi như đã xác nhận giấy 22/9/2026, lưu ở
  `SX QC Setting.so_do_moc`); danh mục một dây chuyền đổi sau lần xác nhận → hộp nhắc. Bột chưa xác nhận → nhắc ngay.
- **Màn**: QC → Xem xét → **Biên bản** (`#/qc/bienban`); mọi vai: Tài liệu → "Chờ tôi ký" + tab Biên bản
  (`#/tailieu/bienban`). In chung `sx/qc/bien_ban.html` (đầu trang W42, "Ký trên phần mềm: Họ tên, giờ" / ô trống ký
  tay). Gói hồ sơ: mỗi biên bản ký đủ trong kỳ một tệp; BM.01.04 có 18 dòng mới.
- **Nhắc** (mảng mới "Biên bản" ở Tổng quan ATTP): biên bản chờ bạn ký, chờ ký quá 3 ngày, họp Ban ISO quá 7 ngày chưa
  có biên bản, sơ đồ dây chuyền phải xác nhận lại. Biên bản năm nhắc qua 6 việc định kỳ patch tạo theo Lịch biểu mẫu
  21/9/2026: xem xét lãnh đạo 31/12/2026, ĐGNB 30/11/2026, thẩm tra 15/12/2026, diễn tập PCCC 30/11/2026, diễn tập truy
  xuất 24/9/2027, QT.14 24/9/2027.
- **Dữ liệu cần nhập / kiểm sau migrate**: ô ký "Đội trưởng Đội PCCC cơ sở" (BM.03.04) giao vai Hành chính, "Thủ kho /
  Kế toán bán hàng" (BM.02.05) giao vai Thủ kho — đổi vai trên Desk (SX Mau Bien Ban) nếu người khác ký; vai lập họp Ban
  ISO = thành viên Ban ISO theo QĐ 21/9/2026 + Hành chính. Tên công đoạn bánh trên app khác tên trong KH.HACCP.01 mục
  5.5 (vd 11 "Ép khuôn" ↔ "Cán lại") — biên bản BM.HACCP.01 đầu tiên ghi "khác sơ đồ" rồi sửa qua BM.01.01.

## Danh mục có hạn, T4 theo vật, BM.01.04, đánh giá nhà cung cấp BM.07.01 (D173 — W44)

**Lên main 10/10/2026 cùng đợt D171–D176** (C22 định để sau đợt Orion kiểm tra lại; đưa lên sớm theo yêu cầu).

- **5 danh mục trên khung Sổ** (`sx/qc/seed/so.json`, patch `d173_danh_muc_ncc` tạo sổ còn thiếu):

  | Sổ | Ghi | Xác nhận | Xem | Hàm riêng / ghi chú |
  |---|---|---|---|---|
  | BM.PRP.04 hóa chất | Cơ điện | Trưởng Ban ISO ("duyệt") | QC, QC gói, QLSX | MSDS (tệp), hạn hồ sơ báo trước 30 ngày |
  | BM.PRP.05 kính, nhựa giòn | Cơ điện | Trưởng Ban ISO | QC, QC gói, QLSX | nối mục T4 lượt Tuần (dưới) |
  | BM.PRP.07 khám sức khỏe, tập huấn | Hành chính | — | **không ai khác** | `suc_khoe`: hạn khám lại = ngày khám + 12 tháng khi để trống; nhân viên chọn từ Employee (người đã nghỉ không có trong danh sách, hiện họ tên); **dữ liệu cá nhân** (`rieng_tu`): chỉ Hành chính, Trưởng Ban ISO, Giám đốc xem — hộp nhắc chung chỉ ghi số mục + ngày hạn, không ghi tên |
  | BM.05.01 bên quan tâm | Ban ISO, QLSX | Giám đốc ("phê duyệt") | — | bản in gom theo 4 nhóm (cột `nhom_theo`), đánh số lại trong nhóm |
  | BM.05.02 rủi ro | Ban ISO, QLSX | Giám đốc | — | `rr_abcd`: chọn A, B, C, D (1–4), app tính **RR = A + B + C + D**, cấp độ 1 = 12–16, 2 = 10–11, 3 ≤ 9 (ô gõ tay bị tính đè, phiếu ghi không cho nhập) |

  Việc định kỳ "xác định lại bên quan tâm, rủi ro" hằng năm, hạn **15/12/2026** (Lịch biểu mẫu: T12/26, cùng tháng xem
  xét lãnh đạo), nhắc trước 30 ngày. Khung Sổ thêm: `nhom_theo` (gom bản in theo cột Select), `rieng_tu`, Link
  `Employee`, cột app tính (`TINH_COT`). Chọn thiết bị (BM.06.05) giờ bỏ đúng thiết bị đã thanh lý (bộ lọc cũ không
  chạy vì thiếu ô).
- **T4 lượt Tuần theo vật**: danh mục BM.PRP.05 có vật đang dùng → mục T4 "Đèn, kính có bảo vệ" mở danh sách vật, QC
  tích ✓ Đạt / ✕ Không từng vật (Không đạt ghi lý do). Lưu vào bảng con `vat_kinh` (`SX QC Round Vat`: dòng danh mục,
  mã, tên chép lại lúc tích) qua `save_round` khóa `vat_kinh:<dòng>` (mỗi vật một giờ ghi — hai máy, ngoại tuyến không
  đè nhau); **T4 = Không đạt nếu có vật Không đạt, Đạt khi mọi vật Đạt**, server tính, ô T4 gửi thẳng bị bỏ qua. Hoàn
  tất: **mỗi vật Không đạt một phiếu sự cố** PRP. Tờ BM.08.01 ghi từng vật (Đ / K). Danh mục trống → T4 tích một lần
  như cũ.
- **BM.01.04 Danh mục hồ sơ** (= `SX Ho So Danh Muc`): thêm **thời gian lưu**, **người lưu** (Vị trí lưu dùng ô cũ);
  nút **🖨 IN BM.01.04** ở màn Hồ sơ đánh giá theo cột giấy (tên hồ sơ, ký hiệu, vị trí lưu, thời gian lưu, người lưu,
  ghi ở đâu app / giấy, ghi chú; dòng tiêu đề nhóm; ngày cập nhật; không ô ký như giấy). Tệp `00-MUC-LUC.html` của gói
  zip dùng chung mẫu (thêm cờ, hạn, đường dẫn trong gói); dòng BM.01.04 trong gói trỏ tới chính tệp mục lục. Patch
  thêm dòng hồ sơ còn thiếu của biểu mẫu W29–W44 và **điền thời gian lưu, người lưu theo BM.01.04 giấy 21/9/2026 vào
  dòng còn trống** (dòng Ban ISO đã ghi giữ nguyên). Biên bản huỷ mẫu, CV 21 chưa có trên giấy → Ban ISO tự điền.
- **BM.07.01 Phiếu đánh giá nhà cung cấp** — DocType `SX Danh Gia NCC` (`DGNCC-.YYYY.-.####`), thẻ **BM.07.01** trong
  màn Sổ (`#/so/BM.07.01`, màn `views/danhgiancc.js`; Mua hàng `Purchase User` giờ có tab Sổ):
  - **Phần A** 7 mục như giấy, **tự điền** từ hồ sơ NCC (Supplier → hồ sơ NCC): còn hạn → Có + số, ngày, hiệu lực;
    hết hạn / không có → Không; mục không áp dụng (theo loại 1 / 2, nhập khẩu / trong nước; cát rang chỉ hợp đồng +
    ĐKKD) → KAD khóa; mục 6 (đỗ, lạc, dầu) người chấm chọn. Mục 1–6 áp dụng mà không Có / hết hiệu lực → thiếu phần A.
  - **Phần B** chọn mức như giấy: I 10 / 5 / 0, II 10 / 5 / 0, III 10 / 4, IV 10 / 6 / 0, V 2 / 0 (theo mục A7). Đánh
    giá lại: **gợi ý điểm I** từ lô 12 tháng (BM.07.03 trên phiếu nhập mua / hoá đơn mua trừ kho + phiếu sự cố sau nhận
    gắn lô): 0 % → 10, < 10 % → 5, ≥ 10 % → 0.
  - **Kết luận app tính**: Chấp nhận = đủ A, 30–42, I ≥ 5; Xem xét = 20–29; Loại bỏ = < 20, I < 5 hoặc thiếu A.
  - **Luồng**: Mua hàng lập, chấm, gửi → vật tư loại 1: QC cùng chấm, ký → Giám đốc (SX Quan Ly) duyệt (phiếu Xem
    xét: chọn Chấp nhận / Không chấp nhận) hoặc trả lại kèm ý kiến. Người chấm không tự ký QC / tự duyệt. Duyệt Chấp
    nhận → **hạn đánh giá lại = ngày duyệt + 12 tháng**. Duyệt xong là khóa (cả Desk); Desk chỉ đọc.
  - **C26** (`sx/qc/ncc.py`): từ **ngày áp dụng** (SX QC Setting → Đánh giá nhà cung cấp; patch điền ngày triển khai),
    tích "Đã duyệt" NCC phải có phiếu BM.07.01 **Chấp nhận còn hạn**. NCC duyệt trước ngày đó không bị chặn, chỉ nhắc
    đánh giá lại (hạn lần đầu ở Setting, mặc định **31/12/2026** — Lịch: T12/26). Mua của NCC chưa duyệt vẫn chỉ cảnh báo.
  - **Nhắc** (mảng Nhà cung cấp): quá / sắp đến hạn đánh giá lại (30 ngày), NCC duyệt trước C26 chưa có phiếu, phiếu
    Chấp nhận chưa vào BM.07.02, phiếu Loại bỏ mà NCC vẫn đang duyệt, phiếu chờ QC ký / chờ Giám đốc duyệt.
  - **In** `sx/qc/bm0701.html` theo giấy lần BH 02 (ô ☑, điểm ở dòng mức đã chọn, ba ô "Ký trên phần mềm"); gói hồ sơ
    zip: mỗi phiếu đã duyệt trong kỳ một tệp.
- **Mặc định đã chọn (§5 chưa trả lời)**: hạn xem xét BM.05.01 / 05.02 theo Lịch biểu mẫu (T12/2026), không theo
  "tháng 3" của bản tóm tắt; PRP.04 / PRP.05 do Trưởng Ban ISO duyệt từng dòng; BM.05.01 thêm cột app "cách đáp ứng";
  BM.05.02 thêm cột "loại" (hoạt động / bối cảnh bên ngoài / nội bộ); phân loại BM.07.01 gợi ý từ loại NCC (nguyên
  liệu, phụ gia, bao bì tiếp xúc, cát rang → loại 1); "Mã NCC trên phần mềm" = mã Supplier (NCC phải có trên hệ thống,
  chưa tích Đã duyệt, trước khi đánh giá); lô Cách ly không tính là không đạt khi gợi ý điểm I (ghi riêng trong gợi ý).
- Build **sx-137**. Deploy: `git pull` → `bench --site site1.local migrate` → `bench restart`.

## Sổ ghi theo dòng: BM.06.05, BM.PRP.06, BM.03.01, BM.03.02, BM.03.03 (D172 — W43)

**Lên main 10/10/2026 cùng đợt D171–D176** (C22 định để sau đợt Orion kiểm tra lại; đưa lên sớm theo yêu cầu). Một khung chung cho các sổ giấy "mỗi lần một dòng" —
thêm sổ mới chỉ khai định nghĩa (Desk → `SX So`), không sửa code màn hình.

- **Định nghĩa sổ** `SX So` (`field:ma`): mã, tên, kiểu **Ghi theo dòng** (sổ sự kiện) / **Danh mục** (mỗi dòng một
  đối tượng), mảng ở Tổng quan ATTP (`mang`), cột (`SX So Cot`: khóa, nhãn, kiểu Data / Date / Datetime / Time / Int /
  Float / Select / MultiSelect / Check / Text / Link / Attach / User, lựa chọn, bắt buộc, cột hạn + báo trước, hiện ở
  danh sách), vai ghi / xác nhận / chỉ xem / xem xét cuối tháng (Table MultiSelect role), nhãn bước xác nhận, xem xét
  cuối tháng, nhắc khi quá N ngày không ghi, dòng hướng dẫn in đầu sổ, hàm riêng `tinh_toan` (khóa có tên trong code,
  không chạy biểu thức người gõ). Controller chặn định nghĩa sai (khóa có dấu / trùng, Select không lựa chọn, Link
  ngoài danh sách cho phép, cột hạn không phải ngày) và chặn bỏ / đổi khóa cột đã có dữ liệu.
- **Dòng sổ** `SX So Dong` (`SOD-.YYYY.-.#####`): dữ liệu JSON kiểm theo cột (đúng kiểu, đủ ô bắt buộc — ô tích bắt
  buộc là phải tích, đúng lựa chọn, không nhận khóa lạ), tóm tắt + hạn gần nhất tự lập; người ghi + giờ, xác nhận
  (người + giờ + ý kiến, C23), lịch sử sửa `SX So Dong Sua` (trước / sau, nối thêm). **Ghi theo dòng**: người ghi sửa
  trong ngày khi chưa xác nhận, xác nhận xong là khóa; ghi nhầm → Ngừng có lý do (người ghi trong ngày, hoặc Trưởng
  Ban ISO), dòng vẫn trên sổ, bản in gạch. **Danh mục**: người có quyền ghi sửa được, mọi lần sửa có vết; dòng đã xác
  nhận bị sửa thì về chờ xác nhận lại; bỏ = Ngừng, không xóa. Người xác nhận không phải người ghi / người sửa gần nhất.
  Trạng thái, người ký chỉ đổi qua app — Desk chỉ đọc. Xem xét cuối tháng: `SX So Xem` (mỗi lần bấm một bản ghi);
  dòng ghi bù sau lần xem → tháng đó lại chờ xem.
- **Quyền**: theo định nghĩa sổ cộng siêu quyền; Trưởng Ban ISO xem mọi sổ, xem xét tháng mọi sổ có xem xét. Tab
  **📒 Sổ** (`#/so`, `#/so/<mã>`) có trong `ROLE_VIEWS` của mọi vai (đứng ngay trước Tài liệu), nhưng chỉ hiện với
  người được giao ít nhất một sổ (`sx.qc.so.co_so` — trang `/sx` và `get_boot` hỏi một lần). Cơ điện, Hành chính, Bảo
  vệ mở app vào Sổ (C24). QC vào qua ô **📒 Sổ khác** ở màn QC Hôm nay.
- **Màn** `#/so`: danh sách sổ mình có quyền (dòng tháng này / đang dùng, chờ xác nhận, hạn, tháng chưa xem, BM.06.05:
  thiết bị chờ kiểm lại, máy quá hạn bảo dưỡng). `#/so/<mã>`: tháng ◀ ▶ (Ghi theo dòng) hoặc "hiện cả dòng đã ngừng"
  (Danh mục), tìm không dấu, **+ GHI DÒNG** — phiếu sinh từ cột (ô chữ, giờ, tích, chọn, bàn số của `qcui.js`; nhiều
  lựa chọn bấm chip; Link / User chọn từ danh sách server lọc sẵn), bấm dòng → chi tiết, SỬA, ✓ XÁC NHẬN, NGỪNG DÒNG,
  tải bản ký tay (scan) / tệp kèm (tệp riêng tư, tải qua `sx.api.qc_so.tep` có kiểm quyền), lịch sử sửa; **ĐÃ XEM
  THÁNG**; **🖨 IN SỔ** — `sx/qc/so.html`: đầu trang chung (W42), dòng hướng dẫn, cột như giấy (ô nhiều lựa chọn ≤ 12
  mục vẽ thành lưới — 12 tháng kế hoạch BM.03.03), ô xác nhận "Ký trên phần mềm: Họ tên, giờ", khối xem xét cuối tháng.
- **5 sổ** (`sx/qc/seed/so.json`, patch `d172_so` chỉ tạo sổ còn thiếu — không đè định nghĩa Ban ISO đã sửa trên
  site; tự gọi `dam_bao_role` trước vì role C24 do after_migrate tạo SAU patch):

  | Sổ | Kiểu | Ghi | Xác nhận | Xem xét tháng | Ghi chú |
  |---|---|---|---|---|---|
  | BM.06.05 bảo dưỡng, sửa chữa | Ghi theo dòng | Cơ điện | QC, QC đóng gói ("QC kiểm trước chạy") | Trưởng Cơ điện (SX Co Dien), QLSX, ISO | mảng Thiết bị đo; QLSX xem |
  | BM.PRP.06 khách, nhà thầu | Ghi theo dòng | Bảo vệ, QLSX | — | Trưởng Ban ISO | khách khai sức khỏe = ô tích bắt buộc |
  | BM.03.01 thiết bị PCCC | Danh mục | Hành chính, Cơ điện | — | — | + cột app: ngày kiểm gần nhất, hạn kiểm / nạp (báo trước 30 ngày), số tem / giấy |
  | BM.03.02 dịch bệnh | Ghi theo dòng | Hành chính | — | Trưởng Ban ISO | ghi khi phát sinh |
  | BM.03.03 kiểm định an toàn | Danh mục | Hành chính, QLSX | — | — | 12 cột tháng → ô nhiều lựa chọn; + cột app như BM.03.01 |

  Cột "QC kiểm trước chạy (ký)" của BM.06.05 thành **bước xác nhận**; cột "TT" của sổ giấy là số thứ tự bản in; giờ
  dừng / bàn giao / vào / ra là ô giờ.
- **BM.06.05 + danh mục thiết bị BM.06.01** (hàm riêng `bao_duong`): `SX Thiet Bi Do` thêm loại **Thiết bị sản xuất**
  (BM.06.01 là "Danh mục thiết bị sản xuất và thiết bị đo") — không hiệu chuẩn, không hạn kiểm / quá hạn / sự cố; chu
  kỳ của máy là chu kỳ **bảo dưỡng** (trống = 6 tháng, QT.06). Patch tạo sẵn 3 máy có mã trong BM.06.01 (máy rang M1
  TBSX-2024-00003, M2 TBSX-2024-00002, máy rang lạc TBSX-2026-00001); máy chưa cấp mã (M3, máy hút ẩm…) QC / Ban ISO
  khai ở màn Thiết bị đo. Cột "Thiết bị" chọn từ danh mục; cột "Cần hiệu chuẩn / kiểm lại" chọn **thiết bị đo** (đồng
  hồ nhiệt, nam châm, lưới) — bản in ghi kèm BM.06.02 / 06.03 / 06.04; sửa chính một thiết bị đo mà chưa chọn thì app tự
  điền. Có thiết bị phải kiểm lại mà **chưa có phiếu kiểm từ ngày sửa** → nhắc mức **cao** ở mảng Thiết bị đo (QT.06:
  kiểm lại trước khi dùng) tới khi ghi phiếu BM.06.02–04; QC vẫn xác nhận được máy (màn báo kèm). Máy sản xuất quá chu kỳ
  chưa có dòng "Bảo dưỡng" (mốc: lần bảo dưỡng gần nhất, chưa có thì ngày khai máy) → nhắc. Màn Thiết bị đo hiện thẻ
  máy với hạn bảo dưỡng + nút SỔ BẢO DƯỠNG; bản in BM.06.01 có cả máy.
- **Nhắc** (mảng theo `mang` của sổ; thẻ mới **Sổ khác** ở Tổng quan ATTP cho sổ chung): cột hạn đã quá / còn ≤ số
  ngày báo trước; quá N ngày không ghi (sổ có đặt N — 5 sổ đầu đều 0, ghi khi phát sinh); dòng chờ xác nhận quá 2
  ngày; tháng đã qua ngày 5 chưa xem xét. Gói hồ sơ cho đoàn đánh giá (W27): mỗi sổ có trong `BIEU_MAU` (Select +
  patch thêm dòng danh mục hồ sơ), sổ Ghi theo dòng in theo tháng có dòng, Danh mục in bản hiện hành.
- **Giấy chưa có** (Ban ISO bổ sung mẫu khi sửa đổi): BM.03.01, BM.03.03 cột Ngày kiểm gần nhất, Hạn kiểm / nạp tiếp,
  Số tem / giấy kiểm định; BM.06.05 ghi rõ thiết bị đo phải kiểm lại (giấy chỉ ghi số BM). Mẫu BM.06.05 ghi người xem xét
  cuối tháng là Trưởng bộ phận Cơ điện, Lịch biểu mẫu ghi QLSX — app cho cả hai (bỏ bớt ở "Vai xem xét cuối tháng").
- Build **sx-136**. Deploy: `git pull` → `bench --site site1.local migrate` → `bench restart`.

## Thư viện tài liệu: đề nghị BM.01.01, đợt ban hành, xác nhận đã đọc, BM.01.02 / 01.03 / 01.13 (D171 — W42)

**Lên main 10/10/2026 cùng đợt D171–D176** (C22 định để sau đợt Orion kiểm tra lại; đưa lên sớm theo yêu cầu). Thay sổ đăng ký Excel, thư mục bản mềm, phát bản giấy, ký
nhận giấy. Căn cứ QT.01 phần kiểm soát tài liệu; QĐ ban hành 21/9/2026 (Phụ lục 1, Phụ lục 3).

- **Màn `#/tailieu`** (tab 📚 Tài liệu, cuối thanh dưới; lối vào thêm ở tab Xem xét của QC). Mọi vai có tài khoản app
  vào được: thêm `tailieu` vào `ROLE_VIEWS` mọi vai + `MOI_VIEW`; Mua hàng / Kinh doanh (role chuẩn `Purchase User`,
  `Sales User`) và Thủ kho NL (`Warehouse`) chỉ có tab này. Vai mới (C24): `SX Co Dien`, `SX Hanh Chinh`, `SX Bao Ve`
  (desk 0), gán được ở màn Người dùng.
  - **Của tôi**: "Cần đọc" trên cùng — 📄 MỞ ĐỌC (thẻ `<a>` trỏ thẳng tệp, mở tab mới) ghi giờ mở; xong mới bật
    **ĐÃ ĐỌC, HIỂU** (C28, thay ký nhận giấy). Dưới là tài liệu phân phối cho vai mình theo nhóm, ô tìm mã / tên / mã
    biểu mẫu; biểu mẫu có màn app → ✍ GHI TRÊN APP. QC mở HD.08.01 trong 2 lần bấm.
  - **Tất cả** (Ban ISO, siêu quyền): mọi trạng thái, nội bộ / bên ngoài, các lần ban hành trước (PDF cũ); sửa tên,
    nơi nhận, biểu mẫu kèm, "phải xác nhận đọc"; thêm tài liệu bên ngoài; ✓ ĐÃ SOÁT XÉT (BM.01.03); in BM.01.02, 01.03.
  - **Đề nghị** BM.01.01 (`SX De Nghi Tai Lieu`, `DNTL-.YYYY.-.###`): SX Quan Ly, ISO, QLSX, QC, QC đóng gói, Cơ điện,
    Hành chính lập → **ký gửi** → Trưởng Ban ISO xem xét (đồng ý / trả lại có lý do) → Giám đốc (SX Quan Ly) duyệt.
    Người đề nghị không tự duyệt; đã gửi chỉ sửa khi bị trả lại; đã duyệt / hủy là khóa; trạng thái không sửa được
    trên Desk. Ký điện tử (C23) = người + giờ + chức danh; nhật ký nối thêm, không sửa đè; in BM.01.01 có
    "Ký trên phần mềm: Họ tên, dd/mm/yyyy hh:mm".
  - **Ban hành** (`SX Dot Ban Hanh`, `DBH-.YYYY.-.##` = QĐ + Phụ lục 1): lập đợt, KÉO ĐỀ NGHỊ ĐÃ DUYỆT, thêm tài liệu
    (mới / sửa đổi / ban hành lại / hủy bỏ / giữ nguyên), tải PDF đã ký từng dòng, tải QĐ đã ký (scan), **BAN HÀNH**
    (Trưởng Ban ISO / Giám đốc): kiểm số QĐ, QĐ scan, PDF từng dòng nội bộ; rồi trong một giao dịch: bản cũ vào lịch
    sử (hết hiệu lực từ ngày hiệu lực của đợt), bản mới Hiện hành, Hủy bỏ → Hết hiệu lực, tài liệu mới được tạo (nơi
    nhận theo dòng); yêu cầu đọc cho người thuộc nơi nhận; đợt khóa (chỉ thêm hồ sơ: biên bản phổ biến có chữ ký…).
    Tiến độ đọc x/y, người chưa đọc; in **BM.01.13** (đọc trên phần mềm có giờ, chưa đọc / không tài khoản → ô ký tay).
- **DocType** (module QC): `SX Tai Lieu` (+ bảng `SX Tai Lieu Bieu Mau`, `… Tep`, `… Noi Nhan`, `… Lan`), `SX Noi Nhan`
  (+ `SX Noi Nhan Vai`), `SX De Nghi Tai Lieu`, `SX Dot Ban Hanh` (+ `SX Dot Ban Hanh Muc`), `SX Tai Lieu Doc`. Bản
  Hiện hành / Hết hiệu lực: lần BH, ngày, PDF, trạng thái, đợt, lịch sử chỉ đổi qua ban hành (cờ `frappe.flags`), kể
  cả trên Desk. Xác nhận đọc đã bấm: không sửa, không xóa. Mã duy nhất trong các tài liệu có mã.
- **Quyền xem (C27)**: người thường thấy tài liệu Hiện hành phân phối cho nơi nhận của mình (theo role của nơi nhận;
  "Toàn bộ người lao động" = mọi tài khoản app → Chính sách ATTP); Ban ISO, siêu quyền thấy hết, cả bản cũ. Tệp là tệp
  riêng tư, tải qua `sx.api.qc_tailieu.tai_tep` (GET, kiểm quyền) — `mo` (POST) ghi giờ mở.
- **Nạp bộ tài liệu (một lần)** — Tài liệu → Ban hành → 📦 NẠP BỘ: (1) NẠP DANH MỤC — bộ đi kèm app, `sx/qc/seed/`
  (D180; trước đó phải chọn 3 tệp `seed_*.json`); (2) chọn `tai_lieu_pdf.zip` (không cần giải nén — D180) hoặc các PDF,
  PNG → app khớp tên, tải (≤ 10 MB, kiểm chữ ký đầu tệp, bỏ qua tệp đã có). Tạo 79 tài liệu sổ đăng ký
  + PLK, BCSX ("Biểu mẫu trên phần mềm", C25) + 21 tài liệu bên ngoài (mã = số hiệu, nhóm A/B/C, soát xét 21/9/2026),
  10 nơi nhận theo Phụ lục 3, đợt 21/9/2026 "Đã ban hành" (không tạo yêu cầu đọc — đã phổ biến giấy 22/9; bật được),
  4 hồ sơ của đợt, hồ sơ vận hành trước audit 17/9 vào danh mục hồ sơ. Chạy lại không nhân đôi, không đè chỗ Ban ISO
  đã sửa (phân phối…). Ghi sổ, Vào hộp không có trong Phụ lục 3: chỉ thấy Chính sách ATTP tới khi Ban ISO phân phối
  thêm.
- **Đầu trang in chung**: `sx/qc/_dau_trang.html` (macro) + `sx/qc/mau_in.py` (`sx_dau_trang`, đăng ký Jinja ở
  `hooks.py`) — khối 3 cột như giấy: tên công ty (SX QC Setting → "Tên công ty trên đầu trang in", trống = CÔNG TY CỔ
  PHẦN HOÀNG GIANG) · tên biểu mẫu · mã / kèm / lần BH / ngày BH lấy từ thư viện (mã biểu mẫu nằm trong tài liệu khác:
  BM.08.05 → HD.08.02). Thay dòng `.ma` của mọi mẫu `sx/qc/*.html` và `dien_tap.html`; thư viện chưa có mã thì in lần BH
  ghi sẵn trước đây (hoặc chấm để ghi tay).
- **Nhắc** (mảng mới "Tài liệu" ở Tổng quan ATTP, route `#/tailieu`): đợt quá 7 ngày còn người chưa xác nhận đọc (theo
  đợt), đề nghị chờ xem xét / duyệt quá 7 ngày, tài liệu bên ngoài quá 12 tháng chưa soát xét, đợt nháp thiếu PDF.
  "Cần đọc" của từng người ở đầu màn Tài liệu. Không gửi email / Zalo (C29).
- Danh mục hồ sơ: thêm BM.01.02, BM.01.03, BM.01.13 (`BIEU_MAU` + Select; patch `d171_thu_vien_tai_lieu` thêm 3 dòng
  app lập) — gói zip có danh mục lúc tải và BM.01.13 của các đợt trong kỳ.
- Build **sx-135**. Deploy: `git pull` → `bench --site site1.local migrate` → `bench restart`; rồi Ban ISO
  nạp bộ tài liệu.

## Báo cáo tháng là BM.01.12 "Báo cáo phân tích dữ liệu tháng" (D170 — W41)

- Bản in báo cáo tháng (`sx.api.qc_baocao.in_bao_cao`) và màn `#/qc/baocao` đổi tiêu đề "Báo cáo an toàn thực phẩm
  tháng" / "Báo cáo ATTP tháng" thành **"Báo cáo phân tích dữ liệu tháng MM/YYYY"**; dòng mã in **"BM.01.12 · Lần BH
  01 · QT.01 mục 5.7"** — ghi cứng tới khi có đầu trang chung (W42) thì thay. Ô ký như giấy: **Trưởng Ban ISO (lập)**,
  **Giám đốc (đã xem)**. Nội dung, số liệu không đổi.
- Build **sx-134**. Không cần migrate (chỉ template, JS) — `bench restart` hoặc tải lại trang.

## Nước tại vòi, không bể; T10 khóa kho, tủ hóa chất (D169 — W39)

- Nước máy lấy thẳng tại vòi, không có bể chứa (PRP lần BH 02, SSOP 1). BM.08.01 lượt tuần: **T1** "Nước tại vòi
  trong, không mùi; vòi, ống không rò" (thay "Bể nước sạch, có nắp"), **T10** "Khóa kho, tủ hóa chất ngoài giờ" (thay
  "Khoá cửa, kho"). Giữ fieldname `t1_be_nuoc`, `t10_khoa` — phiếu cũ đọc nguyên, in ra chữ mới; nhãn Desk sinh lại.
- Patch `d169_bo_thau_rua_be`: việc định kỳ **thau rửa bể** (nếu site có khai) → **Ngừng** (`ngung=1`), không xoá —
  lần đã làm vẫn là hồ sơ. Nhận theo tên, không dấu: có thau / súc / rửa / vệ sinh và "bể", "bể nước", "bể chứa",
  "bồn nước"; không đụng bể ngâm, nước thải, bể phốt, bồn rửa tay. Migrate in ra việc nào đã ngừng; ngừng nhầm thì
  bỏ tích Ngừng ở màn Việc định kỳ.
- Cần `bench --site site1.local migrate` (nhãn, patch) rồi `bench restart`.

## Lưu bột, mối hàn túi: oPRP → PRP; rang lạc oPRP-7 (D168 — W38)

- Quyết định 09/10/2026: bánh chỉ còn **oPRP-1, oPRP-2** (số 3, 4 để trống); bột **oPRP-5 … oPRP-9**. Lưu bột 2 ngày
  và mối hàn túi, nắp hộp bột là **PRP**.
- BM.08.01: bước **8 Kho bột** và **12 Đóng gói** bỏ nhãn oPRP-3 / oPRP-4 (màn QC, tờ in, nhãn Desk sinh lại). Các mục
  thùng bột quá 2 ngày / hở nắp, mối hàn túi kín, B4 mối hàn túi 40 g, B8 nhiệt độ hàn khai `loai="PRP"` → lỗi ghi
  **sự cố PRP** (không mã oPRP); khối lượng tịnh, nhãn HSD (bước 12) → **Khác**. Rang lạc B2a/B2b/B2c → **oPRP-7**
  (`OPRP_NHIET`); `OPRP_GOI` bỏ.
- Mục kiểm, tần suất, ngưỡng không đổi; rây < 0,2 mm mỗi lượt giữ nguyên. Phiếu sự cố cũ giữ loại / mã đã ghi.
- Việc giao ghi "Khác"; làm theo §3 (lưu bột, mối hàn **là PRP**) nên ghi loại PRP — Select loại sự cố đã có PRP,
  cùng cách thùng ủ, vải ủ (D129).
- Cần `bench --site site1.local migrate` (nhãn bước, mô tả trường) rồi `bench restart`.

## In Sổ lưu mẫu SLM và sổ tiếp nhận BM.07.03 theo tháng; vào gói hồ sơ (D167 — W36)

- **Sổ lưu mẫu SLM** (lần BH 02, 21/9/2026) — `sx.api.qc.in_so_luu_mau(thang)`, A4 ngang, đúng 14 cột giấy: sản phẩm /
  vị, quy cách (dòng đầu ô Quy cách của bộ tự công bố), NSX, số lô (= HSD), ngày lưu, số lượng, vị trí, người lưu, ngày
  hủy dự kiến, tình trạng sử dụng mẫu, ngày hủy, người hủy, Trưởng Ban ISO xác nhận. Bảng 1: mẫu **lấy trong tháng** —
  mọi trạng thái (đang lưu, chờ huỷ, đã lấy ra "Lấy ra ngày: lý do", đang giữ "GIỮ — chưa hủy (lý do)"). Bảng 2: mẫu
  tháng trước **huỷ / lấy ra trong tháng**. Huỷ qua đợt: người hủy = QC đề xuất đợt (QĐ.01 mục 5.5: QC huỷ), xác nhận =
  Trưởng Ban ISO xác nhận đợt. Nút in: màn Lưu mẫu (ô chọn tháng), màn Xem xét tháng.
- **Sổ BM.07.03** (lần sửa đổi 01) — `sx.api.qc_tiepnhan.in_bm0703(thang)`, A4 ngang, đúng 12 cột giấy, **một dòng mỗi
  lô** từ phần QC của phiếu nhập mua / hoá đơn mua có trừ kho **đã duyệt** (dòng có kết luận tiếp nhận): ngày, vật tư,
  NCC, số lô NCC, ĐVT, số lượng, NSX / HSD (theo lô), COA lô / KN năm (ô Giấy tờ lô), nội dung kiểm (cảm quan,
  aflatoxin…), kết luận, người kiểm, ghi chú / xử lý (kho cách ly, phiếu sự cố, xe không đạt). Nút in: màn Tiếp nhận NL
  (ô chọn tháng), màn Xem xét tháng.
- Danh mục hồ sơ: thêm `SLM`, `BM.07.03` vào `BIEU_MAU` + Select của `SX Ho So Danh Muc`; patch
  `d167_ho_so_slm_bm0703` thêm hai dòng (app lập) nếu chưa có → gói zip có bản in từng tháng của kỳ.
- Cần `bench --site site1.local migrate` (Select mới, patch) rồi `bench restart`.

## Kiểm nghiệm nước, nguyên liệu, bao bì, thẩm tra vải ủ theo KH.KN.01; việc định kỳ 2 năm (D166 — W35)

- **Việc kiểm nghiệm định kỳ** = việc định kỳ (`SX Viec Dinh Ky`) có ô mới **"Kiểm nghiệm KH.KN.01 — mẫu của"** (Nước /
  Nguyên liệu / Khác). Patch `d166_viec_kiem_nghiem` tạo nếu chưa có (so theo tên, bỏ qua hoa thường / khoảng trắng)
  theo **KH.KN.01 lần BH 01**: nước sản xuất (mẫu nước tại vòi, QCVN 01-1:2024/BYT) — năm; đỗ xanh nhập khẩu (mẫu gộp
  ≥ 10 bao: aflatoxin B1, tổng, độ ẩm, kim loại nặng, BVTV, phosphine, ochratoxin A) — năm; lạc nhân (aflatoxin) — năm;
  dầu thực vật (peroxide, acid) — năm; thôi nhiễm bao bì tiếp xúc (QCVN 12-1/12-3) — **2 năm**; thẩm tra vải ủ (nấm
  men, nấm mốc bột sau nghiền, HD.08.02 mục 9) — 3 việc *Một lần* hạn 31/10, 30/11, 31/12/2026. Hạn lần đầu của việc
  năm = hạn đầu kiểm nghiệm ở SX QC Setting (KH.KN.01: "lần gửi mẫu đầu tiên trước 31/10/2026"); bao bì chưa biết lần
  gần nhất → **để trống**.
- Khác danh sách giao việc (theo KH.KN.01): nước ghi "nước sản xuất" (mẫu tại vòi); đỗ xanh nhập khẩu đủ chỉ tiêu của
  KH.KN.01; lạc nhân và dầu thực vật là **hai việc riêng** (chỉ tiêu khác nhau).
- **Màn Kiểm nghiệm** thêm khối **Nước · nguyên liệu · khác (KH.KN.01)**: trạng thái, tần suất, hạn, chỉ tiêu, phiếu gần
  nhất; **GỬI MẪU** gắn việc (mẫu của lấy theo việc, chỉ tiêu điền sẵn) → app ghi **lần làm** của việc (ngày gửi, phiếu)
  và dời hạn sang kỳ sau tính từ hạn cũ (chưa đặt hạn → từ ngày gửi); việc *Một lần* thì ngừng. Xoá phiếu (ghi nhầm) /
  đổi việc của phiếu → lần làm bỏ theo, hạn trả lại. Chờ kết quả → **GHI KẾT QUẢ**; Không đạt → phiếu sự cố nói tên việc.
  Bản in KH.KN.01 thêm bảng các việc này đúng cột giấy (đối tượng, chỉ tiêu, tần suất, căn cứ, gửi gần nhất, kết quả, lần
  kế tiếp).
- **Việc định kỳ**: thêm chu kỳ **2 năm**; **hạn để trống được** khi chưa biết → hiện "Chưa đặt hạn", hộp nhắc nói "N
  việc chưa đặt hạn" (không im lặng). Việc kiểm nghiệm không bấm "Đã làm" ở màn Việc định kỳ — nút chuyển sang màn
  Kiểm nghiệm (phiếu gửi mẫu là bằng chứng).
- **Hộp nhắc**: việc kiểm nghiệm vào mảng **Kiểm nghiệm** (Tổng quan ATTP): quá hạn gửi mẫu — mức cao; đến hạn trong số
  ngày nhắc trước (30); chưa đặt hạn. Thẻ "Việc định kỳ" không đếm việc kiểm nghiệm nữa.
- Cần `bench --site site1.local migrate` (ô mới, patch) rồi `bench restart`.

## Kiểm xe BM.09.01: năm mục QT.09, QC kiểm ngẫu nhiên, Trưởng Ban ISO xem tháng (D165 — W34)

- **Năm mục** theo QT.09 lần BH 01 mục 5.2, đúng cột giấy: *Sạch khô · Mùi · Kín/che · Hàng chung · Sàn* (mỗi mục có
  dòng yêu cầu 5.1 bên dưới), thêm ô **Đơn vị vận chuyển**, ô tài xế đổi thành **Lái xe (ký xác nhận)**, ô ghi chú thành
  **Xử lý / ghi chú kiểm xe**. Ghi trên hoá đơn bán trừ kho / phiếu nhập mua như D139. Duyệt chứng từ còn đòi **tên lái
  xe**; xe nhận nguyên liệu **Không đạt** phải ghi **xử lý** mới duyệt được (giấy: "K ở bất kỳ mục nào: ghi xử lý").
- **Phiên bản bộ mục** như `muc.py` (ô ẩn `custom_xe_phien_ban`): chuyến ghi trước D165 giữ **bốn mục cũ** (patch
  `d165_kiem_xe_phien_ban` đánh dấu phiên bản 1) — Desk hiện bốn ô cũ, tờ in in bảng riêng "bộ mục cũ". Chứng từ mới →
  năm mục.
- **Chép chứng từ (Duplicate) không mang kết quả kiểm xe theo**: mọi ô kiểm xe `no_copy` — chuyến mới phải kiểm lại xe
  (trước đây chép hoá đơn tuần trước là có sẵn "Đạt" + người kiểm). *Amend* vẫn giữ (cùng chuyến).
- **QC kiểm ngẫu nhiên ≥ 1 chuyến/tuần** (QT.09 mục 4): màn QC → Hôm nay → **🚚 Kiểm xe** (`#/qc/kiemxe`): mỗi tuần thứ
  Hai – Chủ nhật một dòng (vàng: tuần này chưa chuyến nào QC kiểm; đỏ: tuần đã hết mà không chuyến nào); các chuyến
  trong tháng; mở chuyến → xem năm mục người kiểm ghi, hàng + HSD → **QC ĐÃ KIỂM XE NÀY** (ô *QC kiểm* = người + giờ,
  kèm nhận xét). Chỉ chuyến trong **2 ngày** kể từ ngày chuyến (kiểm lúc xếp / nhận hàng — không ký bù chuyến tuần
  trước để xoá nhắc). Đóng dấu nhầm: người đóng dấu bỏ được trong ngày, Ban ISO bỏ được khi tháng chưa xem. Xe nguyên
  liệu: QC ghi kiểm xe trên màn **Tiếp nhận NL** là tính luôn *QC kiểm*.
- **Hộp nhắc**: "Tuần này N chuyến hàng, chưa chuyến nào QC kiểm xe"; tuần trước đã lỡ thì nhắc tới hết tuần này;
  "Kiểm xe BM.09.01 tháng MM chưa được Trưởng Ban ISO xem" (sau ngày 5 tháng sau). Tổng quan ATTP thêm mảng **Kiểm tra
  xe** (số tuần đã hết có QC kiểm / số tuần có chuyến, chuyến, xe không đạt); danh mục hồ sơ BM.09.01 lấy cờ từ mảng này.
- **Trưởng Ban ISO**: nút **ĐÃ XEM THÁNG** cuối màn Kiểm xe — ký mọi chuyến **đã duyệt** của tháng; chuyến duyệt sau đó
  làm tháng hiện lại "chưa xem". Dấu QC kiểm và dấu xem tháng là ô chỉ đọc, ghi được sau duyệt; ghi bằng
  `db.set_value` (không chạy lại luật hoá đơn; `modified` đổi để Desk đang mở bản cũ không lưu đè).
- **Bản in BM.09.01** (nút trên màn Kiểm xe và ở Xem xét tháng, gói hồ sơ zip): đúng cột giấy *Ngày · Biển số · Đơn vị VC
  · Hàng, số lượng, HSD · 5 mục (Đ/K) · Đạt · Xử lý · Người kiểm · Lái xe ký*; dòng *QC kiểm* ghi dưới người kiểm; chỉ
  chuyến đã duyệt; chân tờ: Trưởng Ban ISO xem từng tháng.
- Cần `bench --site site1.local migrate` (ô mới, patch) rồi `bench restart`.

## Nhật ký cát mỗi việc một dòng; rework thêm ô QLSX, giờ (D164 — W32)

- **Nhật ký cát BM.08.03** theo HD.08.03 (viết lại 07/10): bỏ "mỗi ngày có rang một dòng", giờ là **mỗi việc một
  dòng** — *Nhập cát* · *Rang khô đưa dùng* (thay toàn bộ) · *Bổ sung* · *Loại cát* · *Vệ sinh thùng, khay*. Cột giấy:
  ngày, việc, nguồn + số BM.07.03, khối lượng kg, thùng số / nhãn ngày, số ngày đã dùng + lý do loại, người làm / QC
  ghi. Nhập phải có nguồn; nhập, đưa dùng, bổ sung phải có kg; loại phải có lý do (nút chọn nhanh: đủ số ngày, màu sẫm,
  khét, vụn cháy, bụi…); vệ sinh nói thùng hay khay. Màn #/qc/cat: thẻ *Cát đang dùng*, 5 nút việc, các dòng của tháng.
- **Số ngày đã dùng** app đếm như trước nhưng theo **ngày có rang** (lượt kiểm ghi nhiệt độ rang ở máy nào đó, cả lượt
  đang dở) kể từ dòng *Rang khô đưa dùng* gần nhất; **bổ sung không tính lại ngày**; *Loại cát* → không có cát đang
  dùng tới khi ghi cát mới. Số ngày ghi vào dòng bổ sung / loại (giấy: "khi bổ sung hoặc loại, ghi số ngày đã dùng").
  Bổ sung / loại khi máy không có cát → chặn. Dòng đưa dùng **đầu sổ** khai cát đã dùng mấy ngày trước đó. Đưa cát mới
  mà chưa ghi loại cát cũ → nhắc (không chặn).
- **Đổi nguồn** = nhập cát của NCC khác lần nhập trước → nhắc kiểm kim loại nặng (trước khi dùng) + lưu lọ mẫu như cũ;
  đưa dùng / bổ sung cát nguồn đó khi chưa có kết quả Đạt → báo. Số ngày tối đa vẫn để 0 = chỉ đếm (C19).
- **Hộp nhắc**: bỏ nhắc "ngày có rang chưa ghi nhật ký" (không còn dòng hằng ngày); thêm "có rang mà nhật ký cát không
  có cát đang dùng" (7 ngày qua). Sàng lại hằng ngày vẫn ghi BM.08.01 mục 4.
- **Dòng cũ giữ nguyên** (patch `d164_cat_theo_viec`): đánh dấu *sổ cũ*, gán việc tương ứng — thay cát → *Rang khô đưa
  dùng*, vệ sinh → *Vệ sinh thùng, khay*, còn lại để trống (ngày có rang). Số ngày đếm tiếp từ dòng cũ cuối cùng.
- Xem xét tháng: chỉ dòng cát **sổ cũ** mới làm ra "ngày sản xuất" (dòng nhập / vệ sinh có thể rơi vào ngày nghỉ); mục
  nhật ký cát đếm theo việc + số ngày cát cuối kỳ. Bản in BM.08.03 đúng 7 cột giấy + dòng "Trưởng Ban ISO xem xét cuối
  tháng".
- **Rework BM.15.01**: thêm **QLSX quyết định** (người có vai QLSX / Giám đốc + giờ) và **giờ bắt đầu – kết thúc**.
  Chọn người không có vai QLSX → chặn; giờ kết thúc trước giờ bắt đầu → chặn; QLSX quyết định sau giờ bắt đầu → cảnh báo
  (QT.15: quyết định trước khi làm). Túi hở, hộp in sai (QC đóng gói tự quyết) để trống. Bản in thêm hai cột.
- Cần `bench --site site1.local migrate` (ô mới, patch) rồi `bench restart`.

## Sổ giặt vải ủ BM.08.05 (D163 — W29)

- Màn QC → Hôm nay → **🧺 Sổ giặt vải ủ** (`#/qc/vaiu`, ngay sau nhật ký cát), theo HD.08.02 lần BH 01. **Mỗi việc
  một dòng** (`SX Giat Vai`): *Giặt định kỳ* (1 lần/tuần) · *Giặt ngoài lịch* · *Nhập vải mới* · *Loại vải* — đúng cột
  giấy: ngày, việc, mã vải (V01-A…) hoặc số lượng, lý do, **đun sôi giờ sôi lại → giờ vớt (phút)**, phơi tại, khô hẳn
  cất lúc, người làm, QC ký.
- Người giặt có thể không có tài khoản: **QC ghi hộ** (ô *Người làm* điền sẵn người giặt trong cài đặt) và **ký**
  (*LƯU VÀ KÝ* hoặc *Lưu, ký sau*). App tính số phút đun = giờ vớt − giờ sôi lại (vớt qua nửa đêm vẫn đúng); giặt mà
  **dưới 10 phút → QC không ký được**, màn báo đỏ "đun lại cho đủ 10 phút" ngay khi gõ giờ. Ký giặt còn cần chỗ phơi và
  giờ cất (vải khô hẳn mới cất). Nhập / loại vải không bắt đun; đã ghi giờ đun thì cũng phải đủ 10 phút.
- Giặt định kỳ chọn sẵn **toàn bộ vải đang dùng**. Dòng đã QC ký hoặc Trưởng Ban ISO đã xem thì **khoá** (Ban ISO sửa /
  xoá trên Desk); người ghi xoá được dòng mình ghi trong ngày khi chưa ký.
- **Danh mục vải** (tab thứ hai, `SX Vai U`, tên = mã vải): QLSX / Ban ISO khai vải (thùng tự đọc từ mã: V01-A → 01),
  đổi *Đang dùng ↔ Dự phòng*. **App không khai sẵn vải** (C31: số thùng, số vải HD.08.02 còn để trống). *Nhập vải mới*
  với mã chưa có → app thêm vào danh mục (Dự phòng). *Loại vải* → vải chuyển **Đã loại** (không xoá — mã vải nằm trong
  hồ sơ 2 năm); loại tay ở danh mục bị chặn. Vải thay mới **khâu lại đúng mã** của thùng (HD.08.02 mục 8): ghi *Nhập
  vải mới* với mã đó → vải về Dự phòng. Sửa / xoá dòng nhập, loại thì danh mục tính lại theo dòng mới nhất.
- **Trưởng Ban ISO**: nút **ĐÃ XEM THÁNG MM/YYYY** + nhận xét — ký mọi dòng chưa xem của tháng (dòng ghi bù sau đó lại
  thành "chưa xem"). Bản in **🖨 IN BM.08.05** theo tháng, đúng cột giấy, dòng "Trưởng Ban ISO xem xét cuối tháng".
- **Hộp nhắc** (mảng mới *Vải ủ* ở Tổng quan ATTP): quá 7 ngày chưa có dòng Giặt định kỳ (quá 14 ngày: mức cao) —
  **chỉ khi đã khai ít nhất một vải Đang dùng**; hôm nay là ngày giặt cố định mà chưa ghi; dòng chờ QC ký quá 1 ngày;
  tháng đã qua ngày 5 của tháng sau mà Trưởng Ban ISO chưa xem.
- *SX QC Setting → Vải ủ*: ngày giặt cố định (thứ), nơi giặt, người giặt — để trống được (QLSX / Ban ISO điền khi chốt).
  **Giặt, đun sôi sau mỗi lần dùng**: bật khi thẩm tra (nấm men, nấm mốc bột sau nghiền — HD.08.02 mục 9) không đạt →
  nhắc khi quá 2 ngày chưa giặt, tính cả giặt ngoài lịch. Việc gửi mẫu thẩm tra 3 tháng đầu khai ở W35 (kiểm nghiệm).
- BM.08.05 vào danh mục hồ sơ cho đoàn đánh giá (patch `d163_vai_u`, chỉ thêm khi chưa có mã) và gói zip (mỗi tháng
  một tệp). Kiểm vải hằng ngày vẫn ghi BM.08.01 mục 5 — không ghi hai nơi.
- Cần `bench --site site1.local migrate` (3 DocType mới, ô cài đặt, patch) rồi `bench restart`.

## Bỏ đo độ ẩm khi nhận đỗ, lạc (D162 — W40)

- Quyết định 09/10/2026: tiếp nhận đỗ xanh, đỗ đen, lạc **chỉ cảm quan** (khô, không mốc); không đo độ ẩm, không mua
  máy đo ẩm — độ ẩm vào kiểm nghiệm năm (KH.KN.01).
- Ô **Độ ẩm (%)** trên dòng phiếu nhập mua / hoá đơn mua **ẩn** (fixtures; số đã ghi trước đây giữ nguyên). Màn
  *Tiếp nhận NL* của QC chỉ hiện ô độ ẩm khi site đặt ngưỡng, hoặc dòng đã có số cũ.
- *SX QC Setting → Độ ẩm tối đa* không còn mặc định 13%: **trống = không kiểm**. Patch `d162_bo_do_am`: còn đúng 13%
  thì để trống; site đã đặt số khác thì giữ. Luật "độ ẩm vượt ngưỡng → Cách ly" giữ lại cho site tự bật với nhóm hàng
  khác (đặt ngưỡng + hiện lại ô bằng Customize Form).
- Seed Thiết bị đo không có máy đo độ ẩm — không phải bỏ gì.
- Cần `bench --site site1.local migrate` (fixtures ẩn ô, patch) rồi `bench restart`.

## Rang đỗ 240–280 °C, bỏ aflatoxin từng lô đỗ / lạc (D161 — W37)

- Ngưỡng rang đỗ theo quyết định 09/10/2026: **≥ 240 °C** (dưới là sự cố oPRP-1 mức Cao), trần vận hành **280 °C**
  (vượt thì cảnh báo, không sự cố). Đổi ở mã (`sx/qc/nguong.py`), mặc định *SX QC Setting*, chữ gợi ý ô nhiệt độ
  rang (cả máy 2, 3) và số dự phòng trên màn QC.
- Patch `d161_rang_240_280`: site còn **đúng 255 / 270 cũ** thì đổi sang 240 / 280 (từng ô riêng); số site đã tự
  chỉnh thì giữ.
- *Nhóm hàng phải có kết quả aflatoxin khi tiếp nhận*: patch bỏ các nhóm **đỗ / đậu / lạc** — không kiểm aflatoxin
  từng lô nữa, chuyển vào kiểm nghiệm năm (KH.KN.01). Nhóm khác site đã khai thì giữ.
- Công đoạn 9 mang tên đúng QT.08 / KH.HACCP.01: **"9 Nấu đường, trộn"** (bản tạo sẵn là "9 Trộn"; đổi bằng Rename,
  phiếu sự cố cũ trỏ theo; site đã tự đặt tên khác thì giữ).
- Cần `bench --site site1.local migrate` (chạy patch, cập nhật mặc định / chữ gợi ý) rồi `bench restart`.

## Tiếp nhận nguyên liệu trên điện thoại cho QC (D160 — W33)

- QC chế biến (vai **SX QC**, không có Desk) kiểm tiếp nhận ngay trên app: màn QC → **Hôm nay** → nút
  **📦 Tiếp nhận NL** (`#/qc/tiepnhan`). Danh sách **phiếu nhập mua nháp 14 ngày** (cả hoá đơn mua có trừ kho —
  đường cũ): *Chờ kiểm* trước, *Đã kiểm đủ — chờ thủ kho duyệt* sau. NCC dịch vụ không hiện.
- Mở một phiếu: thông tin NCC (loại, nguồn, đã duyệt BM.07.02, phiếu kiểm nghiệm năm còn hạn) → **kiểm xe BM.09.01**
  cùng lúc với hàng (biển số, tài xế, các mục, kết luận — mục nào Không đạt thì kết luận Không đạt) → từng dòng: lô
  NCC, CQ/CO, COA vi sinh (báo khi nhóm hàng bắt buộc), aflatoxin (khi nhóm hàng phải có), độ ẩm, cảm quan, kết luận
  → ghi chú QC → ảnh hàng / giấy tờ / xe (nén trên máy, tối đa 8 ảnh một phiếu) → **LƯU KẾT QUẢ KIỂM**.
- Ghi **đúng các ô QC có sẵn** của phiếu (không đụng số lượng, đơn giá, kho) và lưu bằng `doc.save()` — luật chạy
  **y như trên Desk**: xe không đạt / thiếu COA / thiếu giấy tờ / thiếu aflatoxin → ép **Cách ly** và đưa vào kho cách
  ly; "Đạt" mà cảm quan Không đạt → chặn. Lời cảnh báo của luật hiện ngay trên đầu phiếu sau khi lưu.
- Chỉ phiếu **nháp**: thủ kho duyệt phiếu trên Desk như cũ (duyệt đòi đủ kết luận, sinh phiếu sự cố cho lô Không đạt /
  Cách ly). Phiếu đã duyệt chỉ xem + thêm ảnh. Ảnh xem qua app (file riêng tư của phiếu mua QC không mở thẳng được).
- *Đã kiểm đủ* = có người kiểm + mọi dòng có kết luận + đã kiểm xe (khi phải kiểm): luật W10 tự ép Cách ly ngay lúc kho
  lập phiếu (vd đỗ thiếu aflatoxin), nên dòng có kết luận chưa chắc đã được QC nhìn.
- **Cách tạm** cho site chưa cập nhật bản này: gán thêm role **Stock User** cho tài khoản QC để vào Desk ghi phần QC
  trên phiếu nhập mua (rộng quyền hơn cần — bỏ role đó sau khi cập nhật).
- Không có DocType mới — không cần migrate cho phần này; `bench restart` để nạp API mới.

## BM.08.04 theo phiếu giấy lần BH 01 (D159 — W31)

- Phiếu kiểm tra xuất xưởng mới theo đúng bản giấy **BM.08.04 lần BH 01 (21/9/2026)**: đầu phiếu thêm **quy cách**
  (điền sẵn dòng đầu "Quy cách đóng gói" của sản phẩm tự công bố), **ngày nghiền bột đậu**, **ngày rang đỗ**.
- **A. Hồ sơ của lô** A1–A5 (Đ / K, riêng A4 có KAD). App tra hồ sơ và ghi **gợi ý + căn cứ** dưới từng mục —
  **QC vẫn tự bấm** (chỉ A5 mẫu lưu chấm sẵn như trước):
  - A1: số lượt BM.08.01 đã hoàn tất ở ngày SX, **mọi** ngày nghiền, ngày rang (đủ 3 lượt chính — lượt Tuần tính là
    đầu sáng, lượt Bổ sung không bù). Ngày nghiền / rang tra từ chứng từ kho của **phiếu ngày NSX đã chốt Ghi sổ**:
    lô bột nền (= lô R) đã dùng → ngày rang (phiếu xuất đỗ), ngày phiếu kho sinh ra lô R. Chưa chốt ngày đó thì QC
    tự ghi ngày rồi bấm **↻ TRA LẠI HỒ SƠ LÔ**.
  - A2: phiếu sự cố liên quan lô — gắn lô, của các phiếu BM.08.04 của lô, sự cố vòng kiểm các ngày SX / nghiền /
    rang (không tính diễn tập). Còn phiếu **chưa quyết định xử lý sản phẩm** → gợi ý Không đạt, ghi số phiếu.
  - A3: nguyên liệu mua về đi vào các phiếu kho ngày SX (truy xuất ngược) — có lô Không đạt / Cách ly → gợi ý
    Không đạt; lô chưa có kết luận tiếp nhận → không gợi ý. Bao bì QC tự đối chiếu.
  - A4: bánh, Chè đậu đen cốt dừa, vị có lạc → KAD; bột vị không lạc theo B7 ngày SX (âm tính / dương tính /
    không chuyển đổi sau Chè → KAD).
- **B. Kiểm thành phẩm** B1–B6 × **5 mẫu ở 5 thùng**: chạm ô đổi — → Đ → K; B2 chạm ô mở bàn số ghi **số cân (g)**.
  Có mẫu K thì dòng tự thành Không đạt (gửi "Đạt" với mẫu K bị chặn); đủ 5 Đ thì gợi Đạt.
- **C. Kết luận** ba lựa chọn: **Cho xuất xưởng** (= "Đạt" cũ ở mọi chỗ chặn; phải đạt toàn bộ A và B) / **Giữ lại
  chờ xử lý** / **Không cho xuất**. Hai lựa chọn sau **luôn có phiếu sự cố BM.08.02**: QC chọn phiếu có sẵn, không
  thì app lập lúc **gửi duyệt** (Giữ lại mức Thường, Không cho xuất mức Cao) — số phiếu in ngay ở dòng kết luận.
  Không có mục Không đạt mà vẫn chọn hai kết luận này thì phải ghi lý do.
- Lô **Giữ lại** vẫn bị chặn nhập kho / bán như chưa duyệt; xử lý xong hiện lại ở *Lô chờ kiểm*, kiểm lại trên
  **phiếu mới**. Lô **Không cho xuất**: lô huỷ, không rework (QT.15) — không lập được phiếu mới (duyệt nhầm thì
  Trưởng Ban ISO thu hồi duyệt).
- **Ô ký thứ ba — Quản lý sản xuất** (tài khoản + giờ): nút *KÝ — QUẢN LÝ SẢN XUẤT* khi phiếu đã gửi / đã duyệt;
  không bắt buộc để duyệt. Phiếu bị trả lại / rút về sửa thì chữ ký QLSX xoá.
- Mẫu in A4 theo bố cục giấy (đầu phiếu, bảng A, bảng B 5 mẫu, C ba ô đánh dấu, ba ô ký).
- **Phiếu cũ** (8 mục tạm) giữ nguyên mục đã ghi, mở bằng form cũ, in bố cục cũ. Patch `d159_xuat_xuong_lan_bh01`
  đổi kết luận cũ: **Đạt → Cho xuất xưởng**, **Không đạt → Không cho xuất**.
- Cần `bench --site site1.local migrate` (ô mới ở SX Kiem Tra Xuat Xuong + bảng con, đổi lựa chọn kết luận, chạy
  patch) rồi `bench restart`.

## BM.08.01 bản 3: thùng ủ gỗ, ba nam châm (D158 — W30)

- Lượt mở từ bản này mang bộ mục **bản 3**; lượt đã mở trước giữ bộ cũ (tờ in các ngày trước không đổi).
- **Mục 5** theo bản giấy 09/10/2026 / HD.08.02: "Thùng ủ gỗ, vải ủ: sạch, khô, không mốc, không đọng nước, phủ
  kín; vải nguyên vẹn, đúng mã thùng; ủ ≤ 48 giờ" — chỉ lượt **Đầu sáng** (và lượt Tuần) như bản giấy và HD.08.01
  bảng 3; bản 2 hỏi mục 5 ở cả ba lượt.
- **Mục 6** tách ba nam châm: **NC-01** (máy vỡ đỗ), **NC-02 M1**, **NC-02 M2** (sau máy nghiền và rây RY-01). Mỗi
  nam châm: Đ/K "đã tháo, lau sạch, còn hút" · vật bắt được · có mạt kim loại. NC-02 đi theo máy nghiền đang chạy:
  một máy thì chỉ NC-02 M1; "+ THÊM MÁY NGHIỀN BỘT M2" (ở mục 6 hay mục 7 đều được) mở cả NC-02 M2 lẫn rây M2; tắt
  bước 7 (hôm không nghiền) thì không hỏi NC-02.
- Sự cố ghi đúng nam châm: K → oPRP mức Thường "Mục 6 nam châm NC-02 M2: Không đạt…"; mạt kim loại → oPRP mức Cao
  "Nam châm NC-01 bắt được mạt kim loại (vật: …)". Bước 6 mang nhãn **oPRP-2** như bản giấy (trước đây K ở nam châm
  vào loại "Khác"). Vật bắt được mà không phải kim loại → cảnh báo ghi tên nam châm.
- Tờ in ngày: phiếu bản 3 in ba dòng nam châm (dòng M2 chỉ khi máy M2 chạy); phiếu cũ in đúng một dòng như lúc ghi.
- **Dữ liệu cần nhập trên site (không phải code):** màn QC → Thiết bị đo (BM.06.01) khai hai nam châm **NC-02 M1**,
  **NC-02 M2**: nam châm thanh 11.000 Gauss, thay khi < 5.000 Gauss, lắp 06/10/2026, vị trí sau máy nghiền M1 / M2.
  NC-03 chỉ là đề xuất — không khai.
- Cần `bench --site site1.local migrate` (thêm ô mới vào SX QC Round) rồi `bench restart`.

## Sửa lỗi migrate ở danh mục hồ sơ (D157 — W46)

- Ô *Biểu mẫu app* (Select) của **SX Ho So Danh Muc** thiếu `BM.01.07` và `BC.THANG`, trong khi patch D150, D151
  thêm đúng hai dòng đó. Frappe kiểm Select ngay cả trong patch, nên `bench migrate` sau D150 **dừng ở patch
  d150** với lỗi `Biểu mẫu app cannot be "BM.01.07"`; màn Hồ sơ đánh giá cũng không lưu được dòng chọn hai mã này.
  Đã thêm hai mã. Test mới: các lựa chọn của ô này phải **bằng đúng** bảng `BIEU_MAU` (`sx/qc/ho_so.py`) — từ nay
  thêm biểu mẫu vào `BIEU_MAU` mà quên DocType là test đỏ.
- Migrate dừng ở một patch thì các patch sau nó (d151, d152…) và bước đồng bộ custom field (fixtures) của lần đó
  cũng chưa chạy. Patch chỉ được ghi "đã chạy" khi chạy xong, nên chỉ cần: `git pull` →
  `bench --site site1.local migrate` → `bench restart`.
- Kiểm sau migrate (`bench --site site1.local console`):
  `frappe.get_all("SX Ho So Danh Muc", filters={"bieu_mau": ("in", ["BM.01.07", "BC.THANG"])}, pluck="ma")` ra
  `BM.01.07` và `BC ATTP tháng`; `frappe.db.exists("Patch Log", {"patch": "sx.patches.d152_bu_ngay_xuat_xuong"})` có.

## Kiểm kê bán thành phẩm: tạo lô mới ngay lúc cân (D156)

- Màn kiểm kê **Bán thành phẩm / Kho xưởng** → ô **+ LÔ KHÁC / MỚI** của mã → **+ TẠO LÔ MỚI**: dùng khi cân thấy
  hàng mà hệ thống chưa có lô (thẻ ghi mã lạ, hoặc bao / thùng không có thẻ).
- Form: **Mã lô ghi trên thẻ** (đang tìm mã nào mà không thấy thì điền sẵn mã đó; chữ thường / khoảng trắng tự sửa)
  và **Ngày làm** (tự đọc từ mã nếu mã có ddmmyy, vd R-280926 → 28/09/26; không cho ngày sau hôm nay) → **TIẾP — CÂN
  LÔ NÀY** → bàn số kg → **LƯU**. Lô (Batch, NSX = ngày làm, ghi chú "tạo lúc kiểm kê KK-…") chỉ được tạo lúc LƯU số
  cân — bỏ ngang giữa chừng không đẻ lô rác.
- Bỏ trống mã thì app đặt **`{prefix}-KK{ngày làm}`** (vd `BBS-KK071026`; KK = sinh ở kiểm kê — không bao giờ trùng
  mã lô sản xuất làm cùng ngày) rồi hiện cửa sổ **Ghi mã này ra thẻ hàng** để chép ra thẻ. Lô thứ hai cùng ngày →
  `-2`; lô -KK chưa dùng (phiếu trước bỏ ngang) thì dùng lại đúng mã đã chép.
- Mã gõ trùng lô đang có của chính mã → cân vào lô đó; trùng lô của mã khác, lô thu hồi, lô bị khoá, ký tự lạ → báo.
- Chốt: lô mới là phần THỪA (sổ 0) → Material Receipt vào đúng lô đó, như mọi lô cân thấy mà sổ không có.
- Không cần migrate: `git pull` rồi `bench restart` (số build sx-124).

## Kiểm kê bán thành phẩm theo lô, thủ kho chốt luôn (D155)

- **Thủ kho chốt được kiểm kê** (cả thành phẩm lẫn bán thành phẩm) — không phải chờ quản lý. Bỏ phiếu đang đếm
  vẫn chỉ quản lý hoặc người lập (bỏ là mất số người khác đã đếm).
- Thẻ kiểm kê có thêm hàng chọn kho: **Thành phẩm** (Kho TP — đếm theo HSD như D154) · **Bán thành phẩm** (Kho BTP)
  · **Kho xưởng** (đỗ ủ / đỗ vỡ — chỉ hiện khi SX Settings có Kho xưởng riêng). Máy nhớ kho đang kiểm; mỗi kho một
  phiếu riêng, mở song song được.
- **Bán thành phẩm cân TỪNG LÔ (kg)**: mã xếp theo chuyền (đỗ → bột nền → đường hoán → bột bánh → bột đậu), mỗi lô
  trên sổ một ô **CÂN** (mã lô, ngày lô, số sổ). Bấm → bàn số kg có dấu phẩy, ô bên phải đọc lại sổ và lệch theo số
  đang gõ. Lô hết thật → **LÔ HẾT · 0** (LƯU khi chưa gõ số bị chặn — bấm nhầm là xoá sạch lô); lô cân nhầm → mở lại,
  **BỎ SỐ CÂN**. Cân thấy hàng của lô sổ kho này không có → **+ LÔ KHÁC** (các lô của mã, mới nhất trước, tìm theo mã
  lô); mã không có trên sổ → **+ MÃ KHÁC**. Mã không quản lý lô cân cả mã. **Không còn** = mọi lô trên sổ của mã cân 0.
- **Chốt**: lô đã cân thì số cân **thay số sổ của lô đó**; lô chưa cân **giữ nguyên** (khác thành phẩm — ở đó số đếm
  thay cả mã). Thiếu → Material Issue đúng lô, thừa / bù lô âm → Material Receipt đúng lô (giá vốn đang chạy của mã).
  Không chuyển lô, không đổi HSD, không đánh dấu "tồn cũ".
- **Không cho chốt khi**: lô đã cân có chứng từ kho **sau lúc cân** (xét theo từng lô — xưởng vẫn chạy lô khác thì
  không sao; lô bị chặn thì bấm lô đó cân lại); dòng thiếu lô của mã quản lý lô / dòng có lô của mã không lô (sửa trên
  Desk); lô đang thu hồi (để riêng). Tồn không gắn lô của mã có lô hiện riêng, không cân được — sửa trên Desk.
- **Nhắc** (không chặn) ở Kho BTP: ngày sản xuất chưa chốt **Ghi sổ** (mẻ chưa vào sổ — bột bánh / bột đậu chưa nhập,
  bột nền / đường hoán chưa trừ) hoặc chưa chốt **Vào hộp** (bột đã vào hộp chưa trừ sổ): chốt ngày trước rồi cân.
- Biên bản bán thành phẩm: từng lô cân thật / sổ sách / chênh lệch, điều chỉnh từng lô, chứng từ kho, chỗ ký.
- Cần `bench --site site1.local migrate` (thêm ô *Loại hàng* trên SX Kiem Ke, ô *Lô* trên dòng đếm — phiếu cũ tự là
  Thành phẩm) rồi `bench restart` (số build sx-123).

## Kiểm kê kho thành phẩm theo HSD (D154)

- **Màn Nhập kho → thẻ "Kiểm kê kho thành phẩm"** (có cả ở màn Quản lý). Bấm **BẮT ĐẦU KIỂM KÊ** → app mở một phiếu
  kiểm kê (`SX Kiem Ke`, số KK-năm-###) và bày mọi thành phẩm đang có trong Kho TP: sổ sách, phần chưa có HSD, phần
  theo từng HSD, lô đang thu hồi (để riêng, không đếm).
- **Đếm**: đi từng mã, bấm **+ HSD** → cùng bàn số với Nhập kho (tab thùng / hộp + ô HSD in trên hộp; nút HSD nhanh
  là các HSD đang có trên sổ, không điền sẵn — phải đọc trên hộp). Mỗi HSD một dòng; bấm dòng để sửa, sửa về 0 là bỏ
  dòng; trùng HSD thì chặn. Mã không còn hộp nào → **Không còn**; đếm thấy mã không có trên sổ → **+ MÃ KHÁC**; hàng
  hết hạn vẫn đếm được. Mỗi lần LƯU ghi thẳng vào phiếu trên server — tải lại trang, đổi máy, hai người cùng đếm đều được.
- **Chốt — thủ kho hoặc quản lý** (D155; trước đó chỉ quản lý): **XEM TRƯỚC & CHỐT** cho thấy từng mã sổ → đếm, chuyển bao
  nhiêu từ lô cũ sang lô theo HSD, thiếu / thừa, số chứng từ kho sẽ sinh. Chốt thì số đếm **thay toàn bộ tồn của mã
  trong Kho TP** (mã chưa đếm giữ nguyên):
  - lô cũ chưa có HSD (và phần dư của lô có HSD mà đếm ít hơn) chuyển sang lô theo HSD (`…-HSDddmmyy`) bằng Stock
    Entry **Repack** — mỗi mã một phiếu, giá vốn đi theo hàng; truy xuất ngược từ lô HSD về lô cũ rồi về ngày sản
    xuất vẫn còn. Ghép HSD với lô cũ theo ngày: hộp làm ngày D chỉ nằm được trong lô nhập từ ngày D;
  - phần **thiếu** → Material Issue, phần **thừa** → Material Receipt (giá vốn đang chạy của mã) — chênh lệch vào tài
    khoản điều chỉnh kho;
  - lô đang thu hồi không đụng; hàng hết hạn mà phải chuyển lô thì đi xuất + nhập (ERPNext không cho Repack đụng lô
    hết hạn).
- **Không cho chốt khi**: mã đã đếm có chứng từ kho **sau lúc đếm** (bán, nhập, huỷ phiếu…) — bấm **Đếm lại** mã đó;
  HSD của hàng làm **từ ngày áp dụng BM.08.04** mà chưa duyệt xuất xưởng (đó không phải hàng tồn cũ — hàng chưa nhập
  kho thì nhập qua màn Nhập kho); mã không quản lý theo lô / có tồn không gắn lô. Còn phiếu nhập kho nháp thì nhắc
  (hàng đó chưa vào sổ — đếm vào là thành thừa).
- **Lô theo HSD nhận hàng tồn cũ** được đánh dấu `Batch.custom_kiem_ke` → bán **không cần phiếu xuất xưởng** BM.08.04
  (như tồn cũ trước ngày áp dụng). Truy xuất: lô cũ ghi "Kiểm kê KK-… — chuyển sang lô theo HSD"; thu hồi lô cũ hay
  lô nguyên liệu tới được cả khách mua lô HSD mới.
- **Biên bản kiểm kê**: bấm phiếu đã chốt (hoặc **In bản nháp** khi đang đếm) → A4: số đếm theo HSD, sổ sách, chênh
  lệch, điều chỉnh từng lô, số chứng từ kho, chỗ ký người kiểm kê / kế toán / quản lý.
- Huỷ phiếu đã chốt: trên Desk (SX Kiem Ke → Cancel) — các chứng từ kho huỷ theo thứ tự ngược, tồn về như trước (hàng
  của lô mới đã bán thì ERPNext không cho huỷ).
- Cần `bench --site site1.local migrate` (doctype SX Kiem Ke + custom field) rồi `bench restart`.

## Nhập kho: chọn sản phẩm là vào bàn số một màn (D153)

- Màn **Nhập kho thành phẩm** giờ như *Vào hộp Tết*: chọn sản phẩm (TÌM SẢN PHẨM, QUÉT HỘP, hay bấm mã ở
  "Vừa vào hộp") là vào thẳng **một bàn số**: tab **THÙNG / HỘP** (mỗi tab một số, tổng tự cộng theo hệ số
  quy đổi), ô **HSD in trên hộp** với nút +3T / +6T / +9T / +12T / *mặc định*, phím số, nút **LƯU · tổng**.
  Không còn cửa sổ số lượng rồi cửa sổ HSD riêng.
- Bấm **số** hay bấm **HSD** của một dòng trên phiếu đều mở cùng bàn số đó. Thủ kho sửa thì chỉ đổi số
  ĐẾM (dòng phụ "phiếu ghi N" để so); người lập sửa thì đổi cả số lập. Sửa về 0 là bỏ dòng.
- **Mỗi (mã, HSD) một dòng = một lô** (W05): chọn lại mã đã có dòng HSD mặc định → mở sửa dòng đó; dòng
  HSD khác của mã hiện thành ô "HSD dd/mm/yy · số ✎" ngay trên bàn số, bấm để chuyển sang sửa dòng đó;
  lưu trùng HSD một dòng khác thì báo ngay trên bàn số, không đợi tới lúc duyệt. Bỏ cửa sổ "sửa dòng nào
  / + DÒNG HSD KHÁC".
- Số > 0 thì phải có HSD, và HSD phải sau ngày nhập — trước đây thiếu HSD bị chặn lúc duyệt, giờ chặn ngay
  trên bàn số. Mã chưa khai hạn dùng thì ô HSD trống, gõ theo bao bì.
- *Vào hộp Tết* dùng chung bàn số này (`moSoHsd` trong `cards/nhapkhotp.js`), có thêm ô dòng khác và chặn
  trùng HSD (hai dòng một lô thì thủ kho không duyệt được phiếu Tết).
- Bàn số vừa một màn điện thoại (390×844 trở lên không phải cuộn); màn thấp hơn thì cuộn, nút LƯU dính đáy.
- Không cần migrate: `git pull` rồi `bench restart` (để số build mới sx-121 có hiệu lực).

## Chốt quyết định 09/10/2026, sửa patch D137 (D152)

- **Đã chốt**: người kiểm đồng hồ nhiệt theo *Đào tạo nội bộ* (W17 f — patch đặt vào SX QC Setting nếu còn
  trống); đóng sự cố không bắt buộc phiếu khắc phục; chu kỳ nam châm, lưới sàng 12 tháng; diễn tập truy xuất
  12 tháng. Ba mục sau đúng như app đang chạy — chỉ bỏ chữ "tạm".
- **Sửa lỗi D137 (W08)**: patch đặt "Áp dụng BM.08.04 từ ngày" kiểm `table_exists("SX Settings")`, nhưng SX
  Settings là doctype Single (không có bảng riêng) nên patch không làm gì → ngày áp dụng trống → hàng thành
  phẩm tồn từ trước W08 bị chặn bán. Đã sửa; **patch D152 chạy bù** (đặt = ngày cập nhật nếu còn trống) cho
  site đã chạy D137. Đã tự khai ngày thì để nguyên. Frappe giả trong test giờ cho doctype Single "không có
  bảng" như thật.

## Báo cáo tháng, chỉ tiêu ATTP (D151 — W25)

- Màn QC → tab **Xem xét** → nút **Báo cáo** (`#/qc/baocao`): chọn tháng (mặc định tháng trước; số liệu
  tính tới hết hôm qua) → chỉ tiêu ATTP năm (Đạt / Không đạt theo tháng và lũy kế năm), bảng **chỉ số từ
  đầu năm** (T01 → tháng báo cáo + lũy kế), nút **🖨 IN BÁO CÁO THÁNG** (A4 ngang, cho họp xem xét của lãnh
  đạo: chỉ tiêu, chỉ số, sự cố, khiếu nại, hành động khắc phục, kết quả kiểm nghiệm, việc đang treo, chỗ ký
  Ban ISO / Giám đốc).
- **Chỉ số** app tự tính: lượt kiểm hoàn tất (3 lượt / ngày sản xuất), ghi đúng khung giờ, ngày thiếu lượt,
  lượt nhập lại từ giấy, sự cố (bỏ diễn tập), sự cố mức Cao, sự cố đóng đúng hạn, khiếu nại, mẫu kiểm nghiệm
  đạt, lô xuất xưởng được duyệt, rework, dấu hiệu động vật gây hại, phiếu khắc phục đúng hạn; tại ngày lập:
  thiết bị đo còn hạn, sản phẩm có kết quả kiểm nghiệm đạt còn hạn, NCC đã duyệt. Tỷ lệ lũy kế cộng tử / mẫu
  (không lấy trung bình các tháng); tháng không có việc là 0; hồ sơ site chưa có thì "—".
- **Chỉ tiêu** (`SX Chi Tieu ATTP`): Ban ISO / quản lý đặt theo văn bản mục tiêu ATTP — chỉ số nào, ≥ / ≤,
  mục tiêu, năm; mỗi chỉ số một chỉ tiêu mỗi năm, ngừng được. App **không có chỉ tiêu mặc định**.
- Gói hồ sơ cho đoàn có thư mục báo cáo tháng (mỗi tháng trong kỳ một báo cáo; patch d151).

## Phiếu hành động khắc phục BM.01.07 (D150 — W24)

- Màn QC → tab **Sự cố** → nút **Khắc phục** (`#/qc/khacphuc`, doctype `SX Khac Phuc`, số CAR-YYYY-###).
  Lập từ phiếu sự cố (nút **+ LẬP PHIẾU KHẮC PHỤC** trong phiếu sự cố — lấy sẵn mô tả, nguyên nhân, hành
  động đã ghi) hoặc lập tay (đánh giá nội bộ, đoàn đánh giá, xem xét lãnh đạo…). Số phiếu tự ghi vào ô
  "Số CAR" của sự cố; mỗi sự cố tối đa một phiếu chưa đóng. Ô Số CAR gõ tay cũ vẫn hiện trên phiếu cũ.
- Ba bước: **Mở** (nguyên nhân gốc, hành động khắc phục, người thực hiện, hạn) → **Chờ kiểm tra** (bấm
  *ĐÃ THỰC HIỆN* — phải có nguyên nhân, hành động, kết quả, ngày xong) → **Đóng**: Trưởng Ban ISO / người
  được giao **kiểm tra hiệu lực**. *Chưa hiệu lực* → phiếu về Mở, đếm số lần làm lại, ghi làm gì tiếp.
  Người làm không tự ghi kết luận / tự đóng (chặn cả Desk); rút lại được khi Ban ISO chưa kiểm.
- Đóng phiếu sự cố **không** đòi phiếu khắc phục, kể cả sự cố mức Cao (chốt 09/10/2026) — hai phiếu độc lập.
- Hộp nhắc + Tổng quan ATTP (thẻ thứ 14 *Hành động khắc phục*): phiếu quá hạn (mức cao), phiếu chờ kiểm
  tra hiệu lực quá 7 ngày. In **BM.01.07** từng phiếu; gói hồ sơ cho đoàn có thư mục BM.01.07 (patch d150
  thêm dòng vào danh mục).

## Hồ sơ cho đoàn đánh giá (D149 — W27)

- Màn QC → tab **Xem xét** → nút **Hồ sơ đánh giá** (`#/qc/hoso`, doctype `SX Ho So Danh Muc`): danh mục
  hồ sơ / văn bản — mã, tên, nhóm, **căn cứ pháp lý**, thay thế văn bản nào, ngày ban hành, hạn, nằm ở đâu:
  **App lập** (gói tự in từ dữ liệu app), **Tệp đính kèm** (bản scan PDF / ảnh / Word / Excel ≤ 10 MB, tệp
  riêng tư) hoặc **Bản giấy** (ghi nơi lưu). Ban ISO / quản lý thêm, sửa, ngừng, xoá.
- Patch tạo sẵn theo nguồn pháp lý đổi ngày 08/10/2026: **CV 21/CV-HGC (thay CV 10)**, **TCCS 01 — ban
  hành theo QĐ 11**, **TCCS 03 — theo QĐ 12**, bản tự công bố 16 sản phẩm (W28) và mọi biểu mẫu app đang
  lập (BM.08.01–08.04, BM.11.01, BM.15.01, BM.06.01–06.04, KH.KN.01, BM.07.02, BM.09.01, BM.PRP.01/03,
  diễn tập truy xuất BM.02.04, biên bản huỷ mẫu). Văn bản khác (giấy chứng nhận, giấy phép…) Ban ISO nhập —
  công cụ lập danh mục bản gốc không có trong repo nên app không đoán.
- **Cờ Đỏ**: hết hạn; bắt buộc mà chưa có bản scan; mảng hồ sơ app đang Đỏ ở Tổng quan ATTP; sản phẩm chưa
  có số tự công bố. **Cờ Vàng**: sắp hết hạn (≤ 60 ngày); văn bản cũ đã có bản thay thế (CV 10) mà chưa
  Ngừng; mảng đang Vàng; sản phẩm chưa ghi TCCS hoặc TCCS chưa có văn bản trong danh mục; bản giấy chưa ghi
  nơi lưu.
- **⬇ TẢI GÓI ZIP** (kỳ mặc định 3 tháng, tối đa 24 tháng): `00-MUC-LUC.html` (căn cứ, chỗ tìm từng hồ
  sơ, cờ kèm lý do, chỗ ký) + mỗi hồ sơ một thư mục: bản in app trong kỳ (tờ ngày BM.08.01 theo tháng, sổ
  sự cố CSV, nhật ký cát…) và bản scan. Tờ nào in lỗi thì mục lục ghi "Không in được", gói vẫn tải được.

## Tổng quan ATTP (D148 — W22)

- Màn QC → tab **Xem xét** (Trưởng Ban ISO, quản lý / Giám đốc) giờ mở vào **Tổng quan ATTP**
  (`#/qc/attp`); *Xem xét tháng* là nút thứ hai ngay trên đầu. Card QC ở màn Quản lý có nút
  **TỔNG QUAN ATTP**.
- 14 thẻ, mỗi mảng hồ sơ một thẻ: vòng kiểm BM.08.01, sự cố BM.08.02, hành động khắc phục BM.01.07 (D150),
  khiếu nại BM.11.01, xuất xưởng
  BM.08.04, truy xuất / thu hồi, thiết bị đo BM.06, kiểm nghiệm KH.KN.01, cát rang BM.08.03, động vật
  gây hại, nhà cung cấp BM.07.02, lưu mẫu, rework BM.15.01, việc định kỳ. Mỗi thẻ: **đèn Đỏ / Vàng /
  Xanh**, con số chính, vài dòng số liệu **30 ngày tới hôm qua**, các việc đang treo; bấm thẻ sang đúng
  màn. Thẻ đỏ lên đầu.
- Đèn lấy từ **chính hộp nhắc** (mỗi mục nhắc gắn mảng): có việc mức cao → Đỏ, có việc treo → Vàng,
  không có → Xanh — tổng quan và hộp nhắc không thể nói hai điều. Thêm ba luật hộp nhắc chưa có:
  khiếu nại quá hạn xử lý (cùng số ngày với phiếu sự cố) → Đỏ, đang mở → Vàng; **lô đang thu hồi →
  Đỏ**; chưa diễn tập truy xuất / quá 12 tháng (chốt 09/10) / lần gần nhất chưa đạt 98% → Vàng; NCC chưa duyệt hoặc
  thiếu hồ sơ → Vàng (không bao giờ Đỏ — W09 chỉ cảnh báo).
- Mảng nào site chưa có dữ liệu / chưa migrate thì thẻ hiện "chưa có số liệu", các thẻ khác vẫn đủ.

## Nhập lại bản giấy, lượt Bổ sung (D147 — W23)

- **Nhập lại từ bản giấy** (mở một ngày cũ, như trước): cuối màn lượt có khối *Nhập lại từ bản giấy* —
  **giờ kiểm thực tế** theo tờ giấy (**bắt buộc** trước khi hoàn tất: giờ hoàn tất trên app là giờ nhập,
  không phải giờ kiểm) và **📷 chụp ảnh bản giấy** (tuỳ chọn, một ảnh, tệp riêng tư gắn lượt; gửi lại là
  thay, gửi được cả sau khi hoàn tất). Tờ ngày BM.08.01 có dòng *Giờ kiểm thực tế* (📷 = có ảnh).
- **Lượt Bổ sung** (màn Hôm nay → **+ LƯỢT BỔ SUNG**): sau mất điện / sự cố máy, đi thêm một lượt —
  **phải chọn lý do** (Mất điện / Sự cố máy / Khác + chi tiết). Bộ mục như lượt Trưa, không khung giờ,
  một ngày mở được nhiều lượt bổ sung (lượt còn dở thì bấm lại là mở lại nó).
- Lượt bổ sung **không thay** lượt nào: ba ô lượt, "đã làm x/3", ngày thiếu lượt (Xem xét tháng, hộp
  nhắc) chỉ đếm Đầu sáng / Trưa / Cuối chiều; Xem xét có thêm số lượt bổ sung. Tờ ngày in thêm cột
  *Bổ sung giờ mở · lý do*.

## Lịch việc định kỳ cho hồ sơ giấy (D146 — W21)

- Màn QC → Hôm nay → **📅 Việc định kỳ** (`#/qc/lichviec`, doctype `SX Viec Dinh Ky`): việc năm / quý /
  tháng / một lần — hạn lần tới, nhắc trước bao nhiêu ngày (mặc định 14), phụ trách, hồ sơ liên quan.
- Patch tạo sẵn hai việc tài liệu nêu: **thử khôi phục dữ liệu app** (hạn 30/11/2026) và **thay bóng đèn
  bẫy côn trùng** (31/03/2027), hằng năm, nhắc trước 30 ngày. Ban ISO / QC thêm việc khác.
- **ĐÃ LÀM**: ghi ngày, người, ghi chú / số biên bản; hạn **kỳ sau tính từ hạn cũ** (làm muộn vẫn giữ tháng
  cũ năm sau); việc một lần làm xong thì ngừng nhắc.
- Hộp nhắc màn Hôm nay: mỗi việc quá hạn một dòng **mức cao**, sắp đến hạn mức thường.

## Phiếu rework BM.15.01 (D145 — W19)

- Màn QC → Hôm nay → **♻ Rework** (`#/qc/rework`, doctype `SX Rework`): hàng đem rework (thuộc sản phẩm
  nào trong bộ tự công bố, lô / HSD, kg, lý do) → mẻ nhận (sản phẩm, mẻ / lô, ngày SX, khối lượng mẻ
  **tính cả phần rework**), gắn phiếu sự cố nếu có, kết quả.
- **Chặn** (cả Desk): rework **> 10% khối lượng mẻ** (nói rõ tối đa bao nhiêu kg); hàng **CÓ LẠC** đưa vào
  sản phẩm **KHÔNG LẠC** (cờ "Có lạc" của bộ tự công bố W28). Sữa bột vào sản phẩm không sữa: chỉ cảnh báo.
  Màn hình tính trước tỷ lệ + dị ứng, khoá nút khi vi phạm.
- Phiếu sự cố có quyết định **"Rework (BM.15.01)"** chỉ đóng được khi đã có phiếu rework gắn với nó.
- In **BM.15.01** theo tháng. Lập: QC, QLSX, Ban ISO; người lập xoá được trong ngày, Ban ISO lúc nào cũng được.

## Kế hoạch kiểm nghiệm KH.KN.01 (D144 — W18)

- Màn QC → Hôm nay → **🧪 Kiểm nghiệm** (`#/qc/kiemnghiem`): mỗi sản phẩm trong bộ tự công bố (W28,
  bỏ sản phẩm ngừng sản xuất) gửi mẫu **ít nhất 1 lần / năm** — lần sau = lần gửi gần nhất + 12 tháng;
  chưa gửi lần nào → hạn **31/10/2026** (*SX QC Setting → Hạn gửi mẫu lần đầu*).
- **GỬI MẪU** (`SX Kiem Nghiem`): ngày gửi, mẫu (lô / HSD), đơn vị kiểm nghiệm, chỉ tiêu; **GHI KẾT QUẢ**
  sau: Đạt / Không đạt, ngày, số phiếu. **Không đạt → phiếu sự cố** (nguồn Kết quả kiểm nghiệm, mức Cao).
  Trạng thái từng sản phẩm: Đạt / Đến hạn (30 ngày) / Quá hạn / Chờ kết quả / Không đạt — kiểm lại.
- **Cát rang chỉ kiểm khi đổi nguồn**: kế hoạch lấy các lần đổi nguồn còn thiếu kết quả kim loại nặng từ
  nhật ký cát (W20); **GỬI MẪU CÁT** gắn với lần đổi nguồn đó, kết quả chép sang nhật ký cát (phiếu sự
  cố do nhật ký cát lập — một phiếu). Mẫu nguyên liệu / nước / khác: **+ GỬI MẪU KHÁC**.
- Hộp nhắc: sản phẩm quá hạn, Không đạt chưa kiểm lại (cao); đến hạn 30 ngày; gửi mẫu ≥ 21 ngày chưa có
  kết quả. In **KH.KN.01** (năm): từng sản phẩm, TCCS, tháng dự kiến, các lần gửi, kết quả.

## Thiết bị đo, hiệu chuẩn BM.06.01–06.04 (D143 — W17)

- Màn QC → Hôm nay → **🌡 Thiết bị đo** (`#/qc/thietbi`): danh mục theo loại (đồng hồ nhiệt, nam châm,
  lưới sàng / rây, cân, khác) — `SX Thiet Bi Do`. Patch tạo sẵn **LS-01-M1/M2/M3** (lưới sàng từng máy
  rang) và **RY-01** (rây kiểm). Đồng hồ nhiệt, nam châm, cân: Ban ISO / QC thêm (hộp nhắc báo loại
  nào chưa khai).
- **GHI KIỂM TRA** (`SX Kiem Thiet Bi`), tiêu chí theo loại: đồng hồ nhiệt — 1–2 điểm đo so chuẩn (0 °C
  nước đá được), sai số > cho phép (mặc định ± 2 °C) → Không đạt; nam châm — bề mặt, lực hút (Gauss nếu
  có); lưới sàng / rây — không rách, mắt lưới, khung; cân — kiểm định bên ngoài phải có số giấy + hạn.
  Tiêu chí hỏng mà ghi Đạt → app ép Không đạt.
- **Hạn kiểm**: lần kiểm gần nhất + chu kỳ (mặc định 12 tháng — đồng hồ nhiệt 1 lần/năm theo tài liệu;
  nam châm, lưới sàng 12 tháng — chốt 09/10/2026, sửa từng thiết bị), hoặc hạn ghi trên giấy hiệu chuẩn; **cân
  theo hạn giấy kiểm định gần nhất** (kiểm nội bộ bằng quả chuẩn không kéo dài hạn). Chưa kiểm lần nào
  → hạn **31/10/2026** (*SX QC Setting → Hạn kiểm lần đầu*).
- **Không đạt hoặc quá hạn → NGỪNG DÙNG + phiếu sự cố BM.08.02** (nguồn Thiết bị đo, mức Cao): Không đạt
  lập ngay; quá hạn do lịch chạy nền mỗi ngày quét — một phiếu gộp cho các thiết bị mới quá hạn, không
  lập lại cho cùng hạn. Kiểm lại Đạt → dùng lại. Hộp nhắc: quá hạn / không đạt (cao), đến hạn 30 ngày.
- In **BM.06.01** (danh mục), **BM.06.02 / 06.03 / 06.04** (các lần kiểm trong năm).
- **Người kiểm đồng hồ nhiệt (W17 f) — chốt 09/10/2026: Đào tạo nội bộ** (patch D152 đặt vào *SX QC
  Setting → Người kiểm đồng hồ nhiệt*): app chỉ lưu biên bản đào tạo ở bảng ngay dưới. Đổi sang "Giữ chứng
  chỉ" thì người tự kiểm đồng hồ nhiệt (nội bộ) phải có chứng chỉ còn hạn trong bảng, không thì app chặn ghi.
  C20 (cân phối trộn): muốn theo dõi thì thêm ở màn Thiết bị đo, loại Cân — không cần sửa app.

## Số đo theo máy rang M1–M3, máy gói bột (D142 — W16)

- Máy rang đỗ mang mã **M1 / M2 / M3** (tài liệu 08/10): nhiệt độ, vòng quay lồng rang ghi theo
  từng máy trên lượt kiểm (đã có từ D100 — nay nhãn là mã máy: màn lượt, tờ in BM.08.01, câu sự cố,
  nhãn trên Desk). Chỉ đổi nhãn — fieldname giữ nguyên, phiếu cũ đọc nguyên. Máy nghiền vẫn M1 / M2.
- **Ba máy gói bột chưa có mã (chờ Cơ điện, C10)** → vẫn "máy 1/2/3". Có mã thì điền
  `MA_MAY["goi_bot"]` trong `sx/qc/muc.py` (rồi `python3 scripts/gen-qc-doctype.py`), nhãn đổi theo.
- Màn lượt: dòng **Lượt trước** ghi theo từng máy rang đang chạy ("M1 262 °C · 6,5 v/ph | M2 …").
- Màn **Xem xét**: bảng **Số đo theo máy** của tháng — mỗi máy rang × (nhiệt độ, vòng quay), mỗi
  máy gói bột × nhiệt độ hàn: số lần đo, thấp – cao, số lần dưới / trên ngưỡng (tô đỏ). Chỉ tính ô
  áp dụng ở lượt đó: máy đang chạy, bước Rang không nghỉ, hôm có làm bột (`sx/qc/so_do.py`).

## Nhật ký cát rang BM.08.03, xem xét tháng theo ngày sản xuất (D141 — W20, W12)

- Màn QC → Hôm nay → **♨ Nhật ký cát rang** (`#/qc/cat`, doctype `SX Nhat Ky Cat`): mỗi ngày có rang
  **một dòng** — nguồn cát (NCC loại *Cát rang*), có thay cát không, đã vệ sinh thùng / khay, cảm quan
  cát, ghi chú. Ghi lại một ngày đã có = sửa dòng đó. Ghi bù ngày cũ được (không ghi trước ngày).
- **App tự đếm số ngày cát đã dùng**: số dòng nhật ký kể từ lần thay cát gần nhất (tính cả hôm đó).
  Dòng đầu sổ khai tay cát đang dùng đã được mấy ngày. Ghi bù / sửa ngày / xoá một dòng → cả chuỗi sau
  tự tính lại. **Số ngày tối đa chưa chốt (C19)** → chỉ đếm, không nhắc; khi chốt thì điền *SX QC
  Setting → Cát dùng tối đa bao nhiêu ngày*, hộp nhắc tự báo thay cát.
- **Đổi nguồn cát** (chọn NCC khác cát đang dùng — app tự đánh dấu thay cát): màn báo đỏ, hộp nhắc QC
  nhắc **kiểm kim loại nặng** (chưa gửi mẫu = mức cao) và **lưu lọ mẫu** tới khi dòng đó có kết quả Đạt
  + tích lọ mẫu (nút *GHI KẾT QUẢ* — QC hoặc Ban ISO, kể cả sau khi tháng đã ký). Kết quả **Không đạt
  → tự lập phiếu sự cố** (nguồn Nhật ký cát, mức Cao, công đoạn 3 Rang).
- Ngày có lượt kiểm ghi **nhiệt độ rang** mà chưa có dòng nhật ký cát → hộp nhắc (hôm nay, và các ngày
  thiếu trong 7 ngày qua). Nguồn chưa là NCC Cát rang được duyệt → chỉ báo.
- **Xem xét tháng (Ban ISO)**: tỷ lệ "Lượt đã làm" chia cho **ngày sản xuất** (có phiếu ngày sản xuất,
  có lượt kiểm, hoặc có nhật ký cát — tới hôm nay), không còn chia cho mọi ngày lịch. Lưới tháng: ngày
  sản xuất thiếu lượt **✗ đỏ**, ngày không sản xuất "–" nhạt; cột **Sự cố** (đếm, bỏ diễn tập) và cột
  **Cát** (✓ có nhật ký, ↻ thay cát). Mục **Nhật ký cát rang** của tháng: số ngày ghi, số lần thay, ngày
  thiếu vệ sinh, cảm quan không đạt, đổi nguồn + kim loại nặng + lọ mẫu; **🖨 NHẬT KÝ CÁT (BM.08.03)**.
  Nút **ĐÃ XEM XÉT ĐẾN …** ký cả lượt kiểm lẫn dòng nhật ký cát; dòng đã ký chỉ Ban ISO sửa / xoá.

## Động vật gây hại theo trạm, BM.PRP.03 / BM.PRP.01 (D140 — W15)

- Danh mục **trạm** `SX Tram Dong Vat`: patch tạo sẵn **R01–R21** (bẫy chuột) và **C01–C19** (bẫy /
  đèn côn trùng). **Ban ISO khai khu + vị trí** từng trạm trên Desk theo sơ đồ đặt trạm (chưa khai
  khu thì mỗi trạm tự là một khu). Thêm trạm: R22…, C20…; bỏ trạm: tích *Ngừng dùng*.
- Màn QC → Hôm nay → **🐀 Động vật gây hại**: **QUÉT TEM TRẠM** (camera) hoặc **gõ mã** (`r5` = R05)
  → chọn loại dấu hiệu, số lượng, xử lý tại chỗ, ngày (ghi bù từ giấy được). Chỉ ghi **khi thấy**
  dấu hiệu — tuần nào trạm không có dòng nào thì trên sổ là "Không". Ghi nhầm: người ghi xoá được
  trong ngày, Ban ISO xoá lúc nào cũng được.
- **🖨 IN TEM QR TRẠM**: tem chứa URL `…/sx#/qc/dvgh/R05` — giơ camera điện thoại là mở thẳng phiếu
  của trạm đó (quét trong app cũng nhận). In 100%, quét thử một tem trước khi dán.
- **Nhắc gọi dịch vụ**: cùng **khu** có dấu hiệu **hai tuần liền** (tuần từ thứ Hai) → dòng đỏ trong
  hộp nhắc màn Hôm nay + đầu màn 🐀. Sáng thứ Hai chưa ai ghi thì cặp hai tuần vừa qua vẫn được
  nhắc. Đã ghi theo trạm thì nhắc cũ theo số trạm ở lượt tuần (T2) tự tắt. App chưa từng có nhắc
  "phun định kỳ" — không có gì để bỏ.
- **🖨 IN BM.PRP.03** (một tuần: từng trạm Có / Không, ngày, loại, xử lý, chỗ ký) và **🖨 IN BM.PRP.01**
  (tháng: lưới trạm × tuần, mọi chuỗi ≥ 2 tuần liền theo khu). Nút ‹ › trên đầu màn đổi tuần /
  tháng cần in.

## Kiểm xe BM.09.01 trên hoá đơn bán trừ kho và chuyến nhận nguyên liệu (D139 — W14)

- Mục **Kiểm tra phương tiện vận chuyển** trên **Sales Invoice** (bán trừ kho — nhà máy không dùng
  Delivery Note) và **Purchase Receipt** (chuyến nhận nguyên liệu): biển số, tài xế, 4 mục (thùng
  sạch / khô / không mùi lạ; không chở chung hoá chất; không dấu hiệu côn trùng / động vật gây hại;
  thùng kín / có bạt), kết luận, người kiểm (tự ghi).
- Mục nào Không đạt → kết luận **tự Không đạt** (báo). Đủ 4 mục Đạt → tự Đạt.
- **Bán**: chưa kiểm xe / thiếu biển số → không duyệt được hoá đơn; xe Không đạt → chặn ("không xếp
  hàng lên xe này"). **Nhận nguyên liệu** (NCC thực phẩm, phụ gia, bao bì tiếp xúc thực phẩm): chưa
  kiểm → không duyệt phiếu nhập; xe Không đạt → không chặn (hàng đã tới) mà **mọi dòng chuyển Cách
  ly** → vào kho cách ly. Hoá đơn không trừ kho, phiếu trả hàng, NCC loại khác: không bắt.
- Tắt ở *SX QC Setting → Bắt kiểm xe BM.09.01*. Màn QC → Xem xét → **🖨 KIỂM XE THÁNG (BM.09.01)**.

## Nhà cung cấp được duyệt BM.07.02, tiếp nhận nguyên liệu trên phiếu nhập mua (D138 — W09, W10)

- **Supplier** (Desk) có mục *Duyệt nhà cung cấp*: **loại NCC** (nguyên liệu thực phẩm, phụ gia /
  hương liệu, bao bì tiếp xúc thực phẩm, bao bì ngoài, **cát rang**, dịch vụ), **nguồn** (trong nước /
  nhập khẩu), bảng **hồ sơ** (`SX Ho So NCC`: loại giấy, số, hết hạn, bản chụp) và ô **Đã duyệt**.
- **Bộ hồ sơ theo loại** (`sx/qc/ncc.py`, `HO_SO_CAN` — bản tạm, chờ bản BM.07.02): thực phẩm /
  phụ gia = ĐKKD + giấy ATTP (hoặc HACCP / ISO 22000) + công bố; bao bì tiếp xúc = ĐKKD + phiếu kiểm
  nghiệm bao bì; bao bì ngoài = ĐKKD; **cát rang = hợp đồng hoặc đơn hàng + ĐKKD**; dịch vụ: không.
- Tích **Đã duyệt**: chỉ Ban ISO / người được giao, và chỉ khi hồ sơ đủ + còn hạn (chặn cả Desk).
  Mua của NCC chưa duyệt / chưa phân loại / hồ sơ hết hạn: đơn mua, phiếu nhập mua, hoá đơn mua
  **chỉ cảnh báo, không chặn**. Màn QC → Xem xét → **🖨 NCC ĐƯỢC DUYỆT (BM.07.02)**.
- **Tiếp nhận BM.07.03 chuyển sang phiếu nhập mua** (Purchase Receipt có đủ ô QC như hoá đơn mua;
  hoá đơn mua có trừ kho vẫn kiểm như cũ). Luật giấy tờ theo NCC, ghi vào ô *Giấy tờ lô*:
  **nhập khẩu** → COA từng lô; **trong nước** → phiếu kiểm nghiệm năm của NCC còn hạn (hoặc COA lô);
  thiếu → **ép Cách ly**. **Aflatoxin**: nhóm hàng khai ở *SX QC Setting → Nhóm hàng phải có kết
  quả aflatoxin* (trống = chưa áp). **Cát rang**: không đòi giấy tờ thực phẩm.
- Lô **Không đạt / Cách ly → tự nhập Kho cách ly** (SX Settings). NCC loại thực phẩm thì **mọi dòng**
  phải có kết luận tiếp nhận mới duyệt được phiếu (NCC chưa phân loại: chưa bắt, để chuyển tiếp).
  Phiếu sự cố lô không đạt gắn đúng lô NCC. Truy xuất: thẻ lô hiện NCC đã duyệt chưa + giấy tờ lô.

## Kiểm tra xuất xưởng theo lô BM.08.04 (D137 — W08)

- DocType **SX Kiem Tra Xuat Xuong**: một phiếu = một lô thành phẩm = (sản phẩm, HSD). Màn QC →
  tab **Xuất xưởng** (thay tab Lưu mẫu; bên trong hai nút *Kiểm xuất xưởng* / *Lưu mẫu*).
- **Lô chờ kiểm** = hàng đã vào hộp chưa nhập kho + dòng phiếu nhập kho nháp (gồm hộp Tết). QC
  bấm **KIỂM BM.08.04** → phiếu tự tra hồ sơ lô (lượt BM.08.01 ngày NSX, sự cố mở, mẫu lưu) và
  chấm sẵn mục 1 / 8 khi có căn cứ → chấm 8 mục (Đạt / Không đạt / KAD + ghi chú / số đo), số
  mẫu, kết luận → **GỬI DUYỆT**.
- **Duyệt / trả lại**: Trưởng Ban ISO hoặc người được giao (*SX QC Setting → Được duyệt phiếu kiểm
  tra xuất xưởng*), **không phải QC đã kiểm lô đó** (kể cả khi người đó có role Ban ISO). Trả lại
  bắt buộc ý kiến. Phiếu đã duyệt bị khoá. Duyệt **Không đạt** → tự lập phiếu sự cố (nguồn Kiểm
  tra xuất xưởng, mức Cao); lô kiểm lại sau rework thì lập phiếu mới.
- **Chặn nhập kho**: thủ kho không duyệt được phiếu nhập kho có lô chưa duyệt Đạt; màn nhập kho
  báo trạng thái BM.08.04 từng dòng trước khi bấm duyệt. **Chặn bán**: hoá đơn trừ kho / phiếu
  giao / POS lô thành phẩm chưa duyệt → chặn (kiểm cả lô ERPNext tự chọn).
- **Tồn cũ không bị chặn**: *SX Settings → Áp dụng BM.08.04 từ ngày* (patch `d137_xuat_xuong` đặt
  bằng ngày cập nhật) — phiếu nhập trước ngày đó, lô tạo trước ngày đó không cần phiếu. Tắt khẩn
  cấp: *Chặn nhập kho / bán lô chưa duyệt xuất xưởng*.
- Hộp nhắc QC: phiếu chờ duyệt (chờ từ hôm qua thì mức CAO). Mẫu in A4 BM.08.04 có chỗ ký.
- ~~8 mục kiểm là tạm~~ — từ D159 (W31) theo bản giấy lần BH 01, xem mục *BM.08.04 theo phiếu giấy lần BH 01*.

## Hàng trả về vào kho riêng, khoá xuất lô thu hồi (D136 — W26)

- **SX Settings**: *Kho hàng trả về*, *Kho cách ly* (patch `d136_kho_tra_ve` tạo hai kho cạnh kho
  thành phẩm nếu chưa khai; công ty đã có kho cùng tên thì dùng lại).
- **Hàng trả về**: Sales Invoice trả hàng có trừ kho / Delivery Note trả hàng → mọi dòng hàng tồn
  kho tự nhập *Kho hàng trả về* (báo cho người lập). **Bán thẳng từ kho trả về bị chặn** — QC
  đánh giá rồi chuyển kho (Stock Entry) mới bán lại.
- **Thu hồi lô**: thẻ lô trong Truy xuất → **⛔ Thu hồi lô này** (Ban ISO / quản lý / người được
  giao, bắt buộc lý do; không chọn phiếu có sẵn thì tự lập phiếu sự cố mức Cao gắn lô). Batch có
  cờ *Đang thu hồi*; đầu thẻ Truy xuất liệt kê các lô đang thu hồi, thẻ lô có dải đỏ.
- **Khoá xuất**: Sales Invoice trừ kho, Delivery Note, POS Invoice chứa lô thu hồi → chặn (phiếu
  trả hàng thì qua). Stock Entry: chỉ cho **chuyển vào kho trả về / kho cách ly** hoặc **xuất huỷ**
  (Material Issue); đưa vào sản xuất, đóng gói lại, chuyển kho khác → chặn. Kiểm cả lô chọn qua
  bundle và lô ERPNext **tự chọn** (kiểm lại ở on_submit, cuộn lại cả chứng từ).
- **Gỡ thu hồi**: bắt buộc lý do, ghi nối lịch sử; trên Desk chỉ Ban ISO / người được giao đổi được
  cờ (hook Batch.validate).

## Sổ khiếu nại khách hàng BM.11.01 trên Issue (D135 — W13)

- Khiếu nại = **Issue** của ERPNext có tích *Là khiếu nại khách hàng* (custom field module QC:
  người khiếu nại / liên hệ, kênh, sản phẩm, **HSD**, lô, số lượng, phân loại, mức độ, kết
  luận, xử lý với khách, phiếu sự cố). Issue dùng việc khác thì app không đụng tới.
- **Gắn lô theo HSD**: nhập sản phẩm + HSD in trên hộp → app tự tìm lô (đổi HSD / sản phẩm thì
  tìm lại); không có lô khớp thì vẫn ghi, màn hình báo "chưa rõ lô".
- Màn QC → **Sự cố** → nút **Khiếu nại KH**: ghi khiếu nại (khách trong danh mục hoặc ghi tay
  tên + số điện thoại), danh sách mở / đã đóng, quá 7 ngày chưa đóng thì gắn "quá hạn",
  **🖨 IN SỔ BM.11.01** (tháng này, A4 ngang, chỗ ký).
- Phân loại **dị vật / vi sinh / dị ứng** hoặc mức Cao → tự lập **phiếu sự cố điều tra**
  (nguồn Khiếu nại, gắn lô); loại khác thì tích "Lập phiếu sự cố" hoặc bấm sau.
- **Đóng** (Resolved / Closed): Trưởng Ban ISO / người được giao, phải có kết luận + xử lý với
  khách — chặn cả Desk. ERPNext tự đóng Issue "Replied" sau N ngày thì khiếu nại được giữ mở.
- Khiếu nại đang mở → **giữ mẫu lưu** của đúng lô / đúng sản phẩm + HSD (W07); thẻ lô trong
  Truy xuất có mục "Khiếu nại khách hàng của lô này".

## Phiếu sự cố BM.08.02: gắn lô, diễn tập, nguồn mới, quyền đóng (D134 — W11)

- **Lô liên quan**: bảng `ds_lo` (`SX Su Co Lo`) thay ô "Lô thành phẩm" một lô của D133 (patch
  `d134_su_co_lo` chép sang). Màn QC → Sự cố: gõ tên sản phẩm, **HSD** (05/04/2027, 5/4/27)
  hoặc mã lô để gắn; lô thành phẩm hiện bằng HSD, lô nguyên liệu bằng mã lô. Ô "lô ảnh
  hưởng" cũ thành ghi chú tự do. Phiếu đang mở → mẫu lưu của các lô này được giữ (W07);
  thẻ lô trong Truy xuất liệt kê phiếu gắn lô.
- **Cờ Diễn tập**: phiếu lập để diễn tập vẫn xử lý / đóng như thật nhưng không vào số liệu
  (dashboard đếm riêng `so_dien_tap`), không giữ mẫu. QC tích lúc lập; sau đó chỉ người được
  đóng phiếu đổi được (bật cờ cho phiếu thật = giấu sự cố).
- **Nguồn mới** (chọn tay khi lập): Khiếu nại, Kiểm tra xuất xưởng, Hàng trả về, Kiểm xe, Động
  vật gây hại, Thiết bị đo, Kết quả kiểm nghiệm, Nhật ký cát, Đánh giá nội bộ, Phát hiện khác.
  "Vòng kiểm QC", "Tiếp nhận NL", "Nhật ký chuyền" chỉ hệ thống gắn.
- **Chỉ người có quyền mới đóng / mở lại** — chặn ở controller nên cả **Desk**: Trưởng Ban ISO,
  quản trị, hoặc người được giao ở *SX QC Setting → Được đóng / mở lại phiếu sự cố*. Trước đây
  trên Desk ai có quyền ghi (QC, QLSX, tổ Ghi sổ) đổi Trạng thái = Đóng là xong.
- Mẫu in BM.08.02 và CSV sự cố có lô liên quan + dấu diễn tập.

## Lưu mẫu 1 năm từ NSX, gắn lô, giữ mẫu sự cố, huỷ tháng có Ban ISO (D133 — W07)

- **Hạn lưu = NSX + 12 tháng** (SX QC Setting → "Lưu mẫu bao nhiêu tháng"; ô số ngày cũ
  180 không còn dùng). Mẫu không gắn lô thì tính từ ngày lấy. Patch `d133_luu_mau_mot_nam`
  nâng hạn của mẫu **đang lưu** lên ngày lấy + 12 tháng (không rút ngắn hạn nào).
- **Gắn mẫu với lô**: form *Lấy mẫu* — chọn sản phẩm rồi bấm lô theo **HSD** in trên hộp
  (mã lô ẩn, như W05); NSX / HSD lấy từ lô, hạn lưu tự tính. Lô không có trong hệ thống
  thì ghi tay HSD như cũ.
- **Giữ mẫu**: mẫu của lô có phiếu sự cố / khiếu nại **đang mở** tự được giữ — phiếu gắn
  đúng lô (ô mới *Lô thành phẩm* trên SX Su Co) hoặc ô "lô ảnh hưởng" ghi HSD / mã lô
  (05/04/2027, 05/04/27, 05.04.2027…). Ngoài ra bấm **🔒 GIỮ LẠI** (bắt buộc lý do) cho khiếu
  nại / điều tra chưa có phiếu. Mẫu đang giữ không vào đợt huỷ, không huỷ được (cả Desk).
- **Huỷ hằng tháng có Ban ISO xác nhận**: QC **không huỷ lẻ** nữa — bấm **ĐỀ XUẤT HUỶ n MẪU
  ĐẾN HẠN** → đợt `SX QC Dot Huy Mau` (mẫu chuyển *Chờ huỷ*, vẫn trong tủ, vẫn lấy ra được
  nếu có khiếu nại). Trưởng Ban ISO **XÁC NHẬN ĐÃ HUỶ** (mẫu → Đã huỷ; mẫu vừa bị giữ tự
  trả về tủ) hoặc **TRẢ LẠI** (bắt buộc lý do). **🖨 BIÊN BẢN** in A4 có cột kết quả từng
  mẫu + chỗ ký. Ban ISO vẫn huỷ lẻ được một mẫu (hỏng, mốc — trước hạn thì bắt lý do).
- Nhắc việc QC: mẫu đến hạn chưa đề xuất, đợt chờ Ban ISO xác nhận.

## Truy xuất: cân bằng lô, diễn tập, bán phải chọn lô, bột nền quá hạn (D132 — W06)

- **Bảng cân bằng lô** (thẻ lô trong Truy xuất): sản xuất / nhập = đã bán (trừ trả lại) +
  xuất khác + tồn. Chuyển kho không tính. **Đạt ≥ 98%**. Có đếm thực tế (diễn tập) thì
  tính theo số đếm + mẫu lưu đã lấy (lấy mẫu không trừ kho).
- **Diễn tập truy xuất** (BM.02.04): nút **⏱ DIỄN TẬP TRUY XUẤT** — đồng hồ chạy (giờ bắt đầu
  do server ghi), tra như khi có khiếu nại thật, tới lô cần truy bấm **KẾT THÚC DIỄN TẬP Ở LÔ
  NÀY**, ghi tồn đếm thực tế (nếu có) → lưu `SX Dien Tap Truy Xuat` (thời gian, cân bằng,
  số khách / lô NCC, ảnh chụp kết quả) và mở **bản in A4 — Phụ lục BM.02.04**. "Lần trước"
  để in lại. Ban ISO dùng ở màn QC → tab **Truy xuất** (mới; tab Xem xét cũng hiện cho Ban
  ISO — trước đây chỉ quản lý thấy).
- **Bán phải chọn lô**: hoá đơn bán trừ kho (Sales Invoice có Update Stock) / phiếu giao —
  dòng thành phẩm có quản lý lô mà chưa chọn lô (HSD) thì **không submit được** (ERPNext tự
  chọn lô FIFO = lô máy đoán). Mã thành phẩm không quản lý lô: chỉ cảnh báo. Tắt ở SX Settings
  → "Bắt chọn lô khi bán thành phẩm". Trả hàng không xét.
- **Nhắc bột nền quá 2 ngày** (hộp nhắc QC, mức cao): lô nhóm `BTP-Bot` còn tồn trên sổ kho
  quá 2 ngày kể từ ngày làm ra lô.
- Chưa làm (chờ W08 / W10): nối lô NCC với BM.07.03 trên phiếu nhập mua, hiện BM.08.04.

## Lô thành phẩm theo HSD (D131 — W05)

- **Mỗi (sản phẩm, HSD) một lô.** Mã lô `{prefix}-HSD{DDMMYY}` — hai phiếu nhập cùng mã
  cùng HSD vào CÙNG lô. Người dùng không thấy mã lô: truy xuất, nhập kho nói bằng **HSD**
  (thứ in trên hộp).
- **NSX = HSD − hạn dùng** (bộ tự công bố, D127) — ngày làm ra hộp, không phải ngày nhập
  kho. Mã chưa khai hạn dùng thì NSX = ngày nhập như cũ. Truy xuất khớp "vào hộp" ĐÚNG
  ngày NSX cho lô theo HSD (lô cũ vẫn khớp theo cửa sổ ngày).
- **Tách dòng theo HSD**: "Vừa vào hộp" chia phần còn lại theo ngày đóng hộp (mới nhất
  trước — phần đã nhận là hàng đóng trước), mỗi ngày → một HSD → một dòng. Nút *Tải tất cả*
  và bấm một mã đều ra đủ dòng theo HSD. Thêm mã đã có dòng → mở bàn số, dòng HSD khác
  của mã là ô bấm trên đó (D153). Hai dòng cùng mã cùng HSD → bàn số chặn ngay; duyệt cũng
  chặn, bảo gộp.
- **Lô cũ chưa có HSD**: thẻ *Lô cũ chưa có HSD* (màn Nhập kho + Quản lý, tự ẩn khi hết) —
  liệt kê lô thành phẩm không HSD (còn tồn trước), HSD điền sẵn = NSX + hạn dùng; thủ kho
  soát theo bao bì rồi **GHI HSD**. Không ghi đè HSD đã có, không nhận HSD trước NSX.
  Hàng còn trong kho thì nên **kiểm kê** (D154): đếm theo HSD in trên hộp — một lô cũ có thể
  chứa hộp nhiều HSD, ghi một HSD cho cả lô là sai.

## Danh mục sản phẩm tự công bố (D127 — W28)

DocType **SX San Pham Cong Bo** (Desk → *SX San Pham Cong Bo*): 16 sản phẩm theo bộ tự
công bố — số bản, tên, loại (Bánh / Bột / Chè), TCCS áp dụng, **hạn sử dụng (tháng)**,
quy cách, cờ **có lạc / có sữa bột / có dừa**. Mỗi mã hàng gắn về một sản phẩm qua ô
**"Sản phẩm tự công bố"** trên Item (form sản phẩm có tab *Mã hàng* liệt kê mã đã gắn).

- `bench migrate` tạo sẵn 16 bản theo danh sách 08/10/2026: 8 bánh 01–08/2023 (9 tháng),
  Bột đậu xanh dinh dưỡng 09/2021, Chè đậu đen cốt dừa 10/2021 (có dừa, có lạc), 6 bột
  01–06/HOANGGIANG/2026 (12 tháng). **14 tên để "điền tên"** — Ban ISO sửa theo bản công
  bố, điền TCCS, quy cách, cờ dị ứng, rồi **gắn mã hàng** (patch không tự gắn: gắn sai là
  QC bật ô thử lạc cho nhầm vị).
- **HSD mặc định** lúc nhập kho / vào hộp Tết = ngày + **số tháng** của sản phẩm (cộng
  theo lịch: 31/05 + 9 tháng = 28/02). Mã chưa gắn sản phẩm thì vẫn theo "Shelf Life In
  Days" như cũ; không khai gì thì bắt nhập HSD theo bao bì.
- **QC**: vị bột gắn sản phẩm *có lạc* thì tự bật phần lạc (B1, B2, B7) — cộng thêm danh
  sách "Vị bột có lạc" trong SX QC Setting, không thay nó.

## Bỏ CHỐT — kho và lương tự đồng bộ (D123)

Không còn nút **Chốt Ghi sổ / Chốt Vào hộp / Huỷ chốt**. Báo mẻ, báo cán, bảng vào hộp
**sửa / xoá lúc nào cũng được**, kể cả ngày cũ.

- **Lưu báo mẻ** → vài giây sau hệ thống tự đưa chứng từ kho tầng 2 về khớp: báo thêm mẻ
  thì ghi **thêm phần chênh** (cùng lô của mã trong ngày), bớt mẻ thì rút chứng từ mới
  nhất của mã đó rồi ghi lại phần thiếu; mã không đổi không bị đụng.
- **Lưu bảng vào hộp** (Ghi hộp, Vào hộp Tết, Desk) → tự ghi đè ngày đó trong phiếu lương
  tháng, gỡ người không còn trong bảng, đối chiếu sổ nợ đơn giá.
- **Lịch "Đồng bộ kho & lương"** (màn Quản lý, thay lịch chốt): ô ngày có nhãn KHO / LƯƠNG —
  xanh = đã khớp, cam = đang chạy, **đỏ = lỗi** (thiếu tồn, thiếu giá vốn, bột đã dùng để
  nhập TP nên không rút được, phiếu lương đã duyệt…). Bấm ngày xem lỗi, **KHAI GIÁ VỐN**,
  **THỬ LẠI**. Đầu thẻ đếm số ngày đang lỗi.
- Chạy nền ngay sau khi lưu; lưới an toàn: job mỗi 5 phút (`scheduler_events`). Ngày đang
  lỗi không tự thử lại — sửa số liệu (lưu lại là xoá lỗi) hoặc bấm Thử lại.
- Cần worker + scheduler của bench đang chạy (`bench start` / supervisor như thường lệ).
- **Patch `d123_bo_chot`**: mở lại ngày / bảng đã chốt (chứng từ đã sinh GIỮ NGUYÊN, ghi vào
  sổ cái đồng bộ); ngày có số liệu chưa từng chốt trong 3 ngày gần đây thì tự đồng bộ,
  cũ hơn thì hiện đỏ "ngày cũ chưa từng chốt" chờ quản lý xem lại rồi bấm Thử lại.
- Cần `bench --site site1.local migrate`.

## Vào hộp Tết (D122) — một màn, một lần lưu

Vai trò mới **`SX QC Tet`** ("QC vào hộp Tết", không vào Desk) → tab **🧧 Vào hộp Tết**.
Quản lý tạo tài khoản ở thẻ Tài khoản portal (chọn vai "QC vào hộp Tết"); quản lý cũng
vào được tab này.

1. **+ THÊM MÃ HÀNG** (hoặc **QUÉT HỘP**) → nhập số theo **thùng + hộp**.
2. **HSD** tự điền = ngày + Shelf Life của mã; mã chưa khai thì hỏi ngay; bấm ô HSD để sửa
   theo HSD in trên hộp.
3. **LƯU — TẠO PHIẾU NHẬP KHO** (một lần) → cùng lúc:
   - **phiếu nhập kho NHÁP** (nguồn "Tết", mỗi dòng có HSD) — **thủ kho đếm và duyệt** ở
     màn Nhập kho như mọi phiếu; duyệt mới vào kho, có lô + HSD để truy xuất;
   - **sản lượng công nhật** vào bảng vào hộp của ngày (không tính khoán theo người).
- Phiếu nháp ghi nhầm: bấm ✕ ở "Phiếu Tết gần đây" (hoặc thủ kho xoá nháp) → xoá luôn
  dòng công nhật đi kèm. Phiếu đã duyệt thì thủ kho huỷ ở màn Nhập kho.
- Ngày đã chốt Vào hộp thì không ghi Tết vào ngày đó được.
- Màn Nhập kho: phiếu Tết có nhãn 🧧; nhiều phiếu nháp thì duyệt lần lượt (cũ trước).
  Hàng Tết đang chờ duyệt không hiện lại ở "vừa vào hộp, chưa nhập kho".
- Cần `bench --site site1.local migrate` (thêm cột `nguon` cho phiếu nhập + tạo role).

**D124 — chỉ hàng Tết, một bàn số.** Danh sách chọn/quét chỉ bày mã thuộc *SX Settings →
Nhóm Hàng Tết* (kể cả nhóm con); để trống thì tự lấy Item Group có tên chứa "Tết"; không có
nhóm nào thì bày mọi thành phẩm kèm dòng nhắc. Chọn mã là vào thẳng bàn số: tab THÙNG /
HỘP (mỗi tab một số, tổng tự cộng), ô HSD điền sẵn theo Shelf Life với nút +3/+6/+9/+12
tháng — bấm LƯU một lần là xong dòng. Server cũng chặn mã không phải hàng Tết.

## Tốc độ tải trang (D120)

- **Trình duyệt:** các thẻ trên một màn tải SONG SONG (trước: nối đuôi, 8 thẻ = 8 lần
  chờ); dữ liệu khởi động nhúng sẵn trong HTML; Google Fonts không còn chặn hiển thị.
- **Server:** bỏ truy vấn lặp theo từng mã / từng lô — BOM, tồn Bin, tồn theo lô, quy
  đổi ĐVT, nợ vào hộp, nợ giá phiếu lương đều đọc gộp một lần; nhớ tạm trong một
  request (`sx.utils.nho`, xoá khi BOM / Item / bảng đơn giá đổi). Lưu đồ tầng 1
  (tab Ghi sổ) từ ~12 truy vấn MỖI lô xuống ~8 truy vấn cho cả màn.
- **Index** cho các cột lọc nhiều (ngày, trạng thái nợ, `Stock Entry.custom_lo_rang`…)
  — cần `bench --site site1.local migrate` một lần.
- `scripts/test-tocdo.py` đếm truy vấn với dữ liệu nhỏ và lớn — phải bằng nhau.
- **D121 — danh mục theo màn:** `get_boot` chỉ còn phần nhẹ theo ngày; danh mục báo
  mẻ / vào hộp / mã quét tải MỘT lần khi màn cần nó mở (`portal.danh_muc`). Màn Quản lý
  không còn dựng danh mục nó không dùng. Thủ kho giờ có bảng mã quét (trước không có
  nên nút quét ở Nhập kho không tra được).
- **D121 — sổ nợ vào hộp chỉ đọc:** trừ nợ chạy lúc QC lưu / chốt bảng vào hộp (hook
  `SX Bang Vao Hop`), không còn ghi database mỗi lần mở thẻ.

## Giao diện máy tính (D119)

Thanh điều hướng **luôn ở đáy màn hình** (cả điện thoại lẫn máy tính). Từ 900px bề ngang:
thanh ngày nằm **trên header**. Màn **Quản lý** theo bản thiết kế: hai cột từ 1100px
(trái: QC treo việc, sổ nợ, lịch Chốt ngày — phải: Truy xuất, Phiếu lương, Tài khoản),
dưới là Tồn BTP theo luồng và khu **Theo dõi** (KPI, biểu đồ sản lượng + liên kết nhanh,
các bảng dạng lưới), chữ/nút gọn hơn cho chuột. Các màn nhập liệu giữ cỡ chữ và vùng
chạm lớn. Font Be Vietnam Pro.

## Chốt ngày bằng lịch tháng (D117)

Màn Quản lý: thẻ **📅 Chốt ngày** (thay thẻ chốt theo ô ngày cũ). Mỗi ô ngày có hai chấm
**GS** (Ghi sổ) và **VH** (Vào hộp): cam = có số liệu chưa chốt, xanh = đã chốt, xám =
không có gì. Đầu thẻ đếm số ngày còn chưa chốt. Bấm một ngày → xem nhanh báo mẻ, báo cán,
rang đỗ, vào hộp (theo mã, theo người) → thấy ổn bấm **CHỐT GHI SỔ / CHỐT VÀO HỘP** ngay
dưới (huỷ chốt cũng ở đó). Thiếu giá vốn thì hiện bước khai giá trước (D116).

## Mã nguyên liệu chưa có giá vốn (D116)

Lỗi ERPNext "Valuation Rate for the Item …, is required to do accounting entries" xảy ra
khi một mã (hay gặp: vani, màu, phụ gia) **chưa từng nhập mua có đơn giá** và Item cũng
chưa khai Valuation Rate — thường vì kho cho tồn âm nên dùng trước khi nhập.

- Bấm **CHỐT GHI SỔ**: nếu có mã như vậy, hiện cửa sổ **Khai giá vốn** liệt kê hết các mã,
  nhập giá ước tính mỗi đơn vị kho (điền sẵn theo giá mua / giá chuẩn trên Item nếu có) →
  **LƯU GIÁ & CHỐT TIẾP**. Giá ghi vào `Item.valuation_rate` (có comment lưu vết), chỉ
  cho mã đang thiếu; nhập mua có giá sau này sẽ thay giá này.
- **Bán thành phẩm không bao giờ bị hỏi giá** (D118): bột nền / đỗ ủ / đỗ vỡ tính từ giá
  đỗ theo hao hụt thật của phiếu rang → tách vỏ → nghiền gần nhất; đường hoán, bột bánh,
  bột đậu tính theo BOM từ giá nguyên liệu (lồng nhiều tầng). Chỉ hỏi nguyên liệu mua
  ngoài thật sự thiếu giá (đỗ xanh, vani…). Giá tự tính ghi vào Item.valuation_rate kèm
  comment "TỰ TÍNH", trong cùng giao dịch với lần chốt.
- Duyệt nhập kho TP gặp mã thiếu giá (bao bì…) thì báo rõ tên mã, nhờ quản lý khai.
- Trên Desk: Item → ô **Valuation Rate**. Tốt nhất vẫn là nhập mua (Purchase Invoice) có giá.

## Truy xuất nguồn gốc 2 chiều (D115) — thẻ "Truy xuất" ở màn Quản lý

**Tìm lô:** quét mã vạch hộp (hoặc chọn sản phẩm) + nhập **HSD in trên hộp** → ra lô.
HSD lệch (in sai 1 ngày) thì gợi ý các lô HSD ±7 ngày. Hoặc gõ mã lô (đủ hoặc một phần)
của bất kỳ thứ gì: lô TP, lô bột, lô đỗ / đường NCC. Bấm mã lô bất kỳ trong kết quả là
truy tiếp lô đó.

**Một lô thành phẩm hiện:**
- ⬅ **Nguồn gốc nguyên liệu**: bột bánh → bột nền (ngày rang, loại đỗ) → đỗ vỡ → đỗ ủ →
  lô đỗ NCC, đường, …; mỗi lô mua về kèm **nhà cung cấp, hoá đơn, lô NCC, kết luận tiếp
  nhận (BM.07.03)**. Theo đúng lô ghi trên phiếu kho (FIFO lúc sinh phiếu).
- 🏭 **Quá trình**: từng ngày (rang, làm bột, vào hộp, nhập kho) — ai vào hộp bao nhiêu
  hộp, lượt QC và mục **Không đạt**, sự cố.
- ➡ **Đi đâu**: bán cho ai (Delivery Note / Sales Invoice, có trả lại), xuất khác, còn tồn.
- 👥 **Khách đã nhận**, 🧪 **mẫu lưu**, ⚠ sự cố ghi theo lô.

**Một lô nguyên liệu / bán thành phẩm** (thu hồi): đi xuôi tới MỌI lô thành phẩm làm từ
nó, rồi gộp danh sách khách đã nhận — đây là danh sách phải gọi khi thu hồi.

**Giới hạn — màn hình nói ra, không giấu:**
- Thành phẩm không gắn bảng vào hộp nào → người vào hộp khớp **theo ngày**: các ngày đóng
  mã đó từ lần nhập kho trước (tối đa 7 ngày) tới ngày nhập lô.
- Lô nhập lúc **chưa có BOM** (sổ nợ BOM): nguyên liệu trừ bù FIFO ở ngày hạch toán, không
  phải đúng lô bột đã dùng.
- Phần "bán cho ai" chỉ có khi bán bằng Delivery Note / Sales Invoice trên ERPNext **có
  chọn lô**. Lô mua phải nhập bằng Purchase Invoice/Receipt có lô (README mục cài đặt).
- Lô TP nhập trước D114 không có HSD → tìm bằng mã lô.

Ô "nhập mã batch TP" cũ ở màn Quản lý đã thay bằng thẻ này. Không cần migrate.

## Hạn sử dụng (HSD) lô thành phẩm lúc nhập kho (D114)

- Mỗi dòng phiếu nhập kho có ô **HSD** (dưới tên sản phẩm). Mặc định = **ngày phiếu +
  "Shelf Life In Days"** của mã hàng (Item → tab Inventory); hiện chữ "· mặc định".
  Bấm vào để sửa theo HSD in trên bao bì (có nút nhanh +3/+6/+9/+12 tháng) — từ D153 là
  cùng bàn số với số thùng / hộp.
- Duyệt phiếu ghi vào lô ERPNext: `Batch.manufacturing_date` = ngày phiếu,
  `Batch.expiry_date` = HSD của dòng. Xem / lọc cận date ở Desk → Batch.
- Mã **chưa khai Shelf Life** mà thủ kho cũng chưa gõ HSD → **không duyệt được**, báo
  rõ dòng nào. Cách gỡ lâu dài: khai Shelf Life In Days cho mã đó một lần.
- HSD phải sau ngày nhập. Sửa số đếm, "Tải tất cả vào phiếu", "Huỷ & lập lại" đều giữ HSD.
- Lô nhập TRƯỚC D114 không có HSD — nếu cần thì sửa tay trên Desk (Batch → Expiry Date).
- Cần `bench --site site1.local migrate` (thêm cột `hsd` vào SX Phieu Nhap TP Item).

## Nhiều QC cùng ghi vào hộp (D113)

- **Mỗi QC chỉ thấy và sửa dòng mình ghi**; tổng trên màn Ghi hộp và lịch tháng của QC
  cũng chỉ là phần của họ. **Quản lý** thấy / sửa mọi dòng (mỗi dòng ghi tên người nhập).
- **Lưu kiểu gộp**: máy gửi các dòng của mình kèm mã dòng + danh sách mã đã biết; server
  chỉ xoá / sửa dòng của người gửi mà máy đó đã biết. Trước D113 máy gửi cả bảng và server
  thay hết — QC này lưu là **mất dòng của QC kia** mà không báo gì.
- Ăn ca gộp theo từng công nhân, chỉ gửi phần vừa đổi.
- Mất mạng: hàng chờ gửi lại không làm nhân đôi dòng; lưu vào hàng chờ không xoá trắng màn.
- Dòng cũ (trước D113): patch gán người ghi = người tạo bảng.
- Đánh đổi đã chọn: hai QC không thấy nhau nên có thể chấm trùng một người — phân công
  mỗi QC một nhóm người / một dãy bàn.

## Công nhật và nợ vào hộp (D101)

Xưởng có hai kiểu làm ra hộp: **công khoán** (trả theo hộp) và **công nhật** (trả theo
ngày). Trước D101 chỉ công khoán có chỗ chấm, và thủ kho **bị chặn** duyệt phiếu nhập
vượt số đã chấm (D70) — hàng công nhật đóng thì không bao giờ nhập kho được cho gọn.

**1. Công nhật chấm ở màn Ghi hộp.** Nút **★ Chấm hộp CÔNG NHẬT**: chọn mã → số hộp,
y như chấm một người. Dòng đó:
- tính vào tổng sản lượng và vào **trần nhập kho**;
- **không** tính lương khoán, không đơn giá, không nợ đơn giá, không chấm ăn ca;
- không gắn tên ai (DB: `cong_nhat = 1`, `nhan_vien` rỗng).

Vào hộp vì thế là **số đếm đầy đủ** của xưởng: khoán + công nhật.

**2. Kho nhận vượt số chấm → ghi nợ, không chặn.** Thủ kho duyệt phiếu nhập nhiều hơn số
đã chấm (khoán + công nhật, cùng khoảng 30 ngày như trần cũ) thì phiếu vẫn qua, hàng vẫn
vào kho; phần vượt thành một dòng **sổ nợ vào hộp** (`SX No Vao Hop`). Màn nhập kho nói
trước khi bấm duyệt. Mã chưa chấm lần nào cũng tính (trần 0).

**3. Nợ tự trừ khi chấm bù.** Card *Nợ vào hộp* (màn Ghi hộp cho QC, màn Quản lý): QC
chấm bù cho đúng người, hoặc dòng Công nhật nếu công nhật đóng — mở card là nợ tự trừ,
nợ cũ trả trước. **Không có nút "đã chấm bù"** bấm tay. Quản lý **Bỏ qua** được từng dòng
(bắt buộc lý do — hàng trả về nhập lại…). Huỷ phiếu nhập → nợ của phiếu *Đã huỷ*.

Nợ là **sổ gộp theo mã**, không theo ngày: chấm hôm nay cho hàng chưa chuyển kho cũng trừ
nợ hôm qua, rồi khi hàng đó vào kho sẽ sinh nợ mới. Tổng nợ luôn bằng đúng phần kho nhận
vượt số chấm.

## Module QC — kiểm tra chất lượng (BM.08.01 / BM.08.02)

Nằm gọn trong module `qc` để sau muốn tách thành app riêng chỉ là chuyển thư mục.
Chi tiết ở [`sx/qc/README.md`](sx/qc/README.md); ở đây chỉ nói cái cần biết khi cài.

| Màn | Việc |
|---|---|
| `#/qc` | ba thẻ lượt trong ngày (Đầu sáng / Trưa / Cuối chiều) kèm khung giờ, hộp nhắc việc đang treo |
| `#/qc/round/:id` | làm một lượt — một trang dài theo trình tự công đoạn, tự lưu, thanh đáy cố định |
| `#/qc/incidents` | sổ sự cố, ghi xử lý tại chỗ; nút **Đóng** chỉ hiện với Ban ISO |
| `#/qc/luumau` | **tủ lưu mẫu** (D100): lấy mẫu theo lô, mẫu đến hạn huỷ đứng đầu, tìm theo lô khi có khiếu nại |
| `#/qc/history` | dải tuần — chỗ thiếu tự lộ ra, kèm nút in tờ ngày A4 |
| `#/qc/review` | lưới tháng × lượt + KPI + ký *đã xem xét* + in cả tháng + xuất CSV |

Ba luật nằm trong code chứ không nằm trong lời dặn:

1. **Ghi tại chỗ** — server đặt giờ bắt đầu / hoàn tất, mỗi giá trị kèm giờ trên máy QC.
   Ghi muộn **không bị chặn**, chỉ gắn cờ: chặn thì người ta ghi bừa cho kịp giờ, mà đó
   mới là thứ phá hồ sơ.
2. **Để trống, không điền bù** — mục áp dụng mà bỏ trống thì phải có lý do trong ghi chú.
   Ép đủ ô là dạy người ta bấm *Đạt* cho xong.
3. **Lệch → sự cố** — Không đạt hoặc vượt ngưỡng thì lúc hoàn tất tự lập phiếu sự cố,
   gắn hai chiều với lượt. Không có nút bỏ qua.

Sự cố của tổ Ghi sổ (hỏng máy, mất điện…) **cũng vào cùng sổ** `SX Su Co` từ D87 — một sổ
cho cả nhà máy, vì hai sổ nghĩa là hai chỗ phải nhớ đi xem, và cái không ai nhớ thì không
ai đóng. Patch `d87_gop_su_co` chuyển dữ liệu cũ sang lúc `migrate`, chạy lại không nhân
đôi; bảng con cũ giữ nguyên để đối chiếu.

**Kiểm nguyên liệu đầu vào (BM.07.03)** gắn vào **Purchase Invoice** (không phải Purchase
Receipt — kho nguyên liệu ở đây nhập thẳng bằng hoá đơn mua). Kết luận nằm ở **từng dòng
hàng** vì một hoá đơn có thể ba mặt hàng ba lô. Lô *Không đạt* / *Cách ly* tự thành phiếu
sự cố khi duyệt hoá đơn.

## Bảng đơn giá khoán (`SX Bang Don Gia`)

Đơn giá khoán phụ thuộc **mã hàng × cách làm** (làm tay / máy hỗ trợ…). Dòng để trống
cách làm là **giá chung** cho mã đó.

- **Một bảng là đủ.** Giá đổi thì sửa ngay trên bảng đó, lưu là áp dụng — không phải
  lập lại mỗi tháng, và không phải submit.
- Muốn **giữ giá cũ để đối chiếu** thì lập bảng thứ hai với `Hiệu lực từ ngày` mới.
  Ngày sản xuất nào dùng bảng có hiệu lực gần nhất **trước** ngày đó. Chấm bù cho một
  ngày cũ hơn mọi bảng thì dùng bảng sớm nhất, không để rơi về "không có giá".
- **Thêm nhiều mã cùng lúc:** nhiều mã chỉ khác vị nhưng gia công y hệt nhau. Mục
  *Thêm nhiều mã cùng lúc* cho chọn cả cụm, điền một đơn giá, bấm Lưu — mỗi mã thành
  một dòng. Mã đã có thì cập nhật giá, không tạo dòng trùng.
- Số tiền **đã chấm không bị sửa theo**: bảng vào hộp lưu đơn giá và thành tiền ngay
  lúc ghi; sửa bảng giá chỉ ảnh hưởng những lần chấm sau đó.

## Nạp tồn đầu để chạy thử (`seed_ton_dau`)

Site mới chưa có tồn NVL thì chốt ngày sẽ chặn "không đủ tồn kho". Lệnh này nạp
tồn đầu cho **mọi NVL + bao bì xuất hiện trong BOM**, số lượng suy thẳng từ định mức
(cộng nhu cầu 1 mẻ của từng BOM active rồi nhân số mẻ) nên tỉ lệ giữa các NVL đúng
theo công thức thật:

```bash
SITE=site1.local
bench --site $SITE execute sx.seed.seed_ton_dau                              # xem trước (mặc định)
bench --site $SITE execute sx.seed.seed_ton_dau --kwargs "{'dry_run': 0}"    # ghi thật, 20 mẻ
bench --site $SITE execute sx.seed.seed_ton_dau --kwargs "{'so_me': 50, 'dry_run': 0}"
```

- **Gọi trần = xem trước** — in bảng dự kiến, không ghi gì. Cả module dùng chung một
  quy ước này; gõ giá trị không hiểu được (`'true'`, `'yes'`) thì lệnh DỪNG chứ không
  đoán, vì đoán sai ở đây là chứng từ kho đã submit.
- **Không bịa giá vốn.** Giá lấy theo thứ tự: giá vốn đang chạy của kho (Bin) →
  `Item.valuation_rate` → giá mua gần nhất. Không có gì cả thì lệnh dừng và liệt kê
  item để đi khai giá. Đang dựng site thử mà chấp nhận giá bịa thì thêm
  `'gia_mac_dinh': 1000`.
- **Item có lô: ghi đúng phần thiếu.** Phiếu kiểm kê đặt số lượng cho RIÊNG lô ghi
  trong dòng, nên lô `TD-` chỉ nhận `mục tiêu − tồn các lô khác`; tổng kho ra đúng
  mục tiêu chứ không cộng dồn.
- **Item đã đủ tồn thì bỏ qua**, chỉ nâng item đang thiếu lên mức mục tiêu — chạy trên
  site có số thật cũng không thổi bay tồn đang đúng.
- Sinh **1 Stock Reconciliation** (purpose *Stock Reconciliation*, chênh lệch vào Stock
  Adjustment). Không dùng *Opening Stock* vì purpose đó đòi tài khoản Temporary Opening
  mà nhiều site chưa lập.
- Item có lô tự tạo lô `TD-DDMMYY` (chạy lại thì tái dùng lô cũ, không đẻ thêm).
- Item chưa có `valuation_rate` lẫn giá mua gần nhất thì tạm dùng `gia_mac_dinh`
  (mặc định 1000) và **liệt kê rõ item nào** — sửa giá thật trên Item rồi chạy lại.

Cách này thay cho việc bật **Allow Negative Stock**: tồn âm làm giá vốn trôi và che mất
FIFO theo lô, tức là che đúng phần cần test.

**Còn phải làm tay:** Activity Type + đơn giá (**bắt buộc — không có thì bảng vào hộp trống**),
BOM **tầng 3 + Item TP + bao bì** + map `custom_activity_type` cho từng SKU (CH-13 chốt: chủ
đầu tư tự tạo trên ERPNext; chưa có thì vẫn ghi được lương khoán, chỉ **chưa sinh lệnh SX
nhánh TP** — D23), Manufacturing Settings, tồn đầu, 2 user tablet — xem `docs/CODER-PACK.md` §8.

## Thay đổi 28/07 (sau khi chạy thử trên site)

- **D17 — bỏ BTP "Hỗn hợp màu đỏ/vàng":** màu + nước cho thẳng vào BOM đường hoán khoai
  môn/cốm theo đúng tỉ lệ. Bớt 2 item + 2 BOM + 2 lần báo mẻ/ngày.
- **D20 — đơn giá khoán lấy từ Activity Type:** bỏ hẳn bảng giá riêng
  (`SX Don Gia Vao Hop`). Activity Type là *loại công việc* ("Vào hộp 300"), map từ Item
  qua `custom_activity_type` — nhiều SKU cùng quy cách dùng chung một loại. Một nguồn giá
  duy nhất; đổi giá chỉ sửa ở Activity Type.
- **D19 — bảng vào hộp gọn lại:** chỉ hiện công nhân **nhóm công khoán** (cấu hình ở
  `SX Settings`, chưa điền thì tự dò nhóm có tên chứa "khoán"), và chỉ hiện **tên gọi**
  — trùng tên mới thêm họ ("Nga Trương" / "Nga Nguyễn"), trùng cả họ thì viết tắt tên đệm
  ("Nga Trương T."). Tên đầy đủ xem được khi rê chuột.
- **D18 — bỏ card "Nhập bột":** chốt ngày tự nhập bột cho lô R **rang hôm trước**
  (đã qua khâu nghiền). QC không bấm; kho + truy xuất + trừ đỗ giữ nguyên. Lô R còn đọng
  (rang lâu mà chưa vào kho) hiện ở dashboard quản lý để phát hiện bất thường.
- **D21 — bỏ "phương thức" (Thủ công / Máy hỗ trợ):** đơn giá vốn theo Activity Type nên
  phương thức không ảnh hưởng lương.
- **D23 — bảng vào hộp ghi theo LOẠI CÔNG VIỆC, không phải theo SKU:** chạm công nhân → chọn
  **Activity Type** (hiện kèm đơn giá + số SKU) → nhập số lượng. SKU chỉ là chi tiết bên trong:
  loại **0 SKU** → ghi thẳng (chỉ tính lương, không sinh lệnh SX tầng 3); **1 SKU** → tự gán;
  **≥2 SKU** → hỏi thêm 1 bước. Nhờ vậy portal chạy được ngay cả khi Item TP + BOM tầng 3
  (Phase 0) chưa nhập — trước đây picker rỗng nên QC không ghi được gì.
- **D22 — lương khoán ghi thẳng vào `SalaryProduct`** (app lam-luong, GATE-B đã chốt):
  1 phiếu/người/**tháng** (PLK), child `luongkhoan` **1 dòng/ngày** với 6 slot
  `sp/sl/dg/tt` (`sp` = tên Activity Type). Chốt ngày **upsert đúng dòng ngày đó** và để phiếu
  ở **DRAFT** (`status = "Nháp"`) cho bộ phận lương duyệt cuối tháng — chốt lại = ghi đè, không
  cộng dồn. Huỷ ngày chỉ **gỡ dòng ngày đó**, các ngày khác giữ nguyên. Không đụng chuyên cần /
  bảo hiểm (ăn ca / ăn đêm từ 29/07 do QC chấm — xem D30).

## Thay đổi 29/07

- **D24 — huỷ chốt ngày để sửa:** chốt xong mới phát hiện sai thì bấm **HUỶ CHỐT NGÀY** trên
  thẻ Chốt ngày. Hệ thống thu hồi **toàn bộ** chứng từ kho của ngày đó (lệnh SX + phiếu kho
  tầng 3 → tầng 2 → phiếu nhập bột, hoàn lại đỗ) và **gỡ dòng lương khoán của ngày đó** khỏi
  phiếu lương tháng, rồi tự tạo lại **phiếu nháp giữ nguyên số liệu** để sửa. Sửa xong **phải
  chốt lại** thì kho + lương mới ghi lại. Không có đường nào sửa số đã chốt mà kho/lương
  không đổi theo.
- **D25 — thanh chọn ngày:** ◀ ▶ / chọn ngày / *Hôm nay* ngay trên đầu portal. Mọi thẻ (ghi số
  lẫn vào hộp) đọc theo ngày đang chọn, có nhãn `🔒 đã chốt` / `✎ ngày cũ`. Thẻ Xuất đậu giờ
  **liệt kê các phiếu đã ghi trong ngày** và huỷ được phiếu ghi nhầm (chỉ khi chưa nhập bột —
  đã nhập bột thì phải huỷ chốt ngày đó trước, vì đỗ đã trừ kho).
- **D26 — bảng vào hộp gộp theo người:** dòng của cùng một công nhân xếp liền nhau (sắp ở
  controller nên bản in và Desk cũng vậy), nhiều dòng thì có dòng *Cộng*. **Bấm vào số lượng
  để sửa tại chỗ** khi chưa chốt.
- **D27 — nút Copy sản lượng gửi nhóm:** copy ra text dán thẳng vào nhóm chat —
  `Khanh (Vào hộp 170: 29, Vào hộp 300: 50)`, mỗi người 1 dòng, kèm ngày + tổng. Công nhân tự
  theo dõi và đối chiếu.

- **D33 — dọn màn nhập liệu, chuyển việc theo dõi + chốt sổ sang Quản lý:**
  - **Chốt ngày** rời màn *Vào hộp* → sang màn **Quản lý**. QC#2 giờ chỉ nhập bảng vào hộp;
    người chốt sổ là quản lý. Vừa gọn màn nhập liệu, vừa siết đúng hướng §2.1 —
    **người nhập số không còn là người chốt sổ**. ⚠️ Đây là đảo lại D9: tài khoản
    `SX Vao Hop` KHÔNG chốt ngày được nữa, phải dùng tài khoản quản lý.
  - **Lưu đồ tồn BTP** rời màn *Ghi số* → sang **Quản lý**, thêm chặng đầu *Đỗ ở xưởng*.
  - Màn Quản lý giờ là **thẻ (chốt ngày + lưu đồ) ở trên, dashboard theo dõi ở dưới** —
    chốt ngày là việc làm mỗi ngày nên không để nó nằm dưới đáy sau 6 bảng thống kê.
  - Bỏ bảng *Tồn BTP hiện tại* ở dashboard vì thẻ lưu đồ đã hiện đủ và rõ hơn; banner
    cảnh báo tồn âm vẫn giữ.
  - Kết quả: màn *Ghi số* còn 4 thẻ, màn *Vào hộp* còn 2.
- **D32 — lưu đồ tồn bán thành phẩm 2 nhánh bánh / bột đậu:** thẻ **Tồn bán thành phẩm
  theo luồng** vẽ cả 2 dây chuyền tầng 2/3, mỗi chặng liệt kê từng loại kèm tồn thật:
  - *Bánh đậu xanh*: Bột nền + Đường hoán → **Bột bánh (8 loại)** → TP bánh hộp
  - *Bột đậu*: Bột nền → **Bột đậu (8 công thức)** → TP túi/hộp
  - Vẽ **cùng nhịp với lưu đồ tầng 1**: mỗi chặng là một ô *nhãn → số tổng to → chi tiết*,
    mũi tên nối các chặng, ô còn hàng thì nổi lên, ô hết hàng mờ đi
  - **Loại tồn 0 không hiện** (D34): 8 loại bột bánh mà ngày thường chỉ chạy 2-3 loại, liệt kê
    cả 8 thì phần đang có hàng chìm nghỉm. Tồn **âm vẫn hiện** và viền ô đỏ — đó là lỗi số
    liệu cần thấy ngay, không phải thứ để lọc đi
  - Bột bánh / bột đậu hiện thêm **quy ra số mẻ** (theo cỡ mẻ chuẩn của BOM) — nhìn là biết
    còn đủ mấy mẻ nữa
  - **Chỉ đọc, không có nút.** Tầng 2/3 không bấm công đoạn được: bột bánh/bột đậu sinh khi
    báo mẻ và bị trừ lúc TP vào hộp (backflush — D8)
- **D31 — thẻ ghi sổ chạy theo LƯU ĐỒ sản xuất, có tồn bán thành phẩm:** thay thẻ *Xuất đậu*
  bằng thẻ **Luồng sản xuất**. QC bấm **XUẤT KHO ĐỖ** → sinh phiếu chuyển kho *Nguyên liệu →
  Xưởng sản xuất* (đỗ FIFO theo lô NCC) và ra mã lô R để ghi thẻ. Mỗi lô hiện thành một dãy ô
  **Đỗ ở xưởng → Đỗ ủ → Đỗ vỡ → Bột nền**, mỗi ô ghi **tồn thật đọc từ kho**, ô nào còn hàng thì
  có nút công đoạn kế tiếp:
  - **Luộc + rang** → Đỗ ủ · **Tách vỏ** → Đỗ vỡ · **Nghiền bột** → Bột nền
  - Mỗi nút: *Hoàn tất cả lô* (lấy hết tồn) hoặc *Nhập số cụ thể* (kg vào + kg ra cân thật),
    hao hụt từng công đoạn được ghi nhận
  - Chứng từ sinh ra là **Stock Entry Repack** — không cần BOM cho các chặng này, vì hao hụt
    mỗi mẻ mỗi khác
  - Batch: `{lô R}-U` (đỗ ủ) · `{lô R}-V` (đỗ vỡ) · `{lô R}` (bột nền, giữ quy ước cũ) —
    Batch trong Frappe là duy nhất toàn hệ thống nên các chặng phải có hậu tố riêng
  - ⚠️ **Chốt ngày KHÔNG còn tự nhập bột** (đảo lại D18): đỗ giờ nằm ở kho Xưởng dưới dạng
    đỗ ủ/đỗ vỡ, tự nhập sẽ trừ sai item + sai kho. Chốt ngày **cảnh báo** lô nào chưa nghiền
    xong để QC không bỏ quên.
  - Cần chạy `sx.seed.seed_btp_dau` (tạo Item Đỗ ủ / Đỗ vỡ) và điền **SX Settings → Kho Xưởng
    sản xuất**; để trống thì dùng luôn Kho BTP.
- **D30 — chấm ăn ca / ăn đêm ngay trên bảng vào hộp:** nút **🍚 Chấm ăn ca / ăn đêm** mở danh
  sách công nhân công khoán, mỗi người 2 ô tick **Ca** / **Đêm** (có nút *Tất cả ăn ca* / *Bỏ
  hết*). Chốt ngày đổ thẳng vào **đúng dòng ngày** của phiếu lương khoán. Đơn giá lấy từ
  `SX Settings` → *Tiền ăn ca / Tiền ăn đêm*, QC **không nhập tiền**. Người chỉ được chấm ăn mà
  không vào hộp vẫn ra dòng lương. Chốt lại = ghi đè (bỏ tick rồi chốt lại thì về 0) — tức là
  **từ nay ăn ca/ăn đêm do QC chấm, bên lương không điền tay nữa**, điền tay sẽ bị chốt ngày ghi đè.
  Ghi theo đúng kiểu field bên app lương: ô **tick** thì đánh dấu 1/0 (tiền để bên lương quy đổi),
  ô **số tiền** thì ghi tiền và cộng vào `thunhapngay`.
- **D29 — danh sách chứng từ đã tạo:** thẻ Chốt ngày (khi ngày đã chốt) liệt kê **mọi chứng từ
  ngày đó sinh ra** — phiếu ngày, phiếu nhập bột, lệnh sản xuất, phiếu kho, lô (batch), bảng vào
  hộp, phiếu lương khoán — theo đúng thứ tự sinh, kèm mô tả 1 dòng (sản phẩm × số lượng, loại
  phiếu, lô + kg) và **link mở thẳng trên Desk**. Bản đã huỷ hiện mờ + gắn nhãn *đã huỷ*.
  Link chỉ hiện với người thật sự có quyền đọc chứng từ đó (QC không có DocPerm trên
  WO/SE/Batch nên chỉ thấy mã, không thấy link chết).
- **D28 — lỗi `Value missing for Stock Entry: Stock Entry Type`:** ERPNext v16 chỉ nhận
  `Stock Entry Type` có `purpose = Manufacture` **và tick `Is Standard`**; site thiếu bản ghi
  đó thì mọi phiếu kho sinh ra đều trống loại phiếu. App giờ tự dò (is_standard → cùng
  purpose → bản tên "Manufacture") và nếu vẫn không có thì báo **đúng chỗ phải tạo**, kiểm
  **trước khi** sinh chứng từ nên không còn bị nuốt thành "check Error Log". Tạo bản ghi
  chuẩn bằng 1 lệnh (idempotent, đã nằm sẵn trong `seed_all`):

  ```bash
  bench --site a.rongvanghoanggia.com execute sx.seed.seed_stock_entry_type
  bench --site a.rongvanghoanggia.com restart   # core cache bản ghi này
  ```

## Trạng thái build v3 (P0→P7)

- ✅ P0/P1 scaffold + DocType (6 + 4 child) + controllers
- ✅ P2 fixtures (3 role, custom fields, validator 0 ERROR)
- ✅ P3 config/roles.py + api (mfg / tang1 / portal / chot)
- ✅ P4 portal card-based (7 card, 3 view) · P5 Print Formats
- ✅ P6 verify: `bash scripts/verify.sh` + `validate_shipped_docs.py` 0 ERROR + review đối kháng
  - ⚠️ **Đừng dùng `node --check file.js`** cho code portal: file `.js` bị parse kiểu CommonJS
    và V8 lazy-parse thân hàm → **bỏ sót** lỗi cú pháp trong thân hàm (đã lọt lên site thật
    một lần). `scripts/verify.sh` copy sang `.mjs` rồi mới check → parse đúng ES module.
- ⏳ P7 deploy + Phase 0 data + Acceptance test (spec §10) — cần chạy TRÊN SITE

## Gate — đã đóng hết

- **GATE-A** (định mức) = workbook v6 + chủ đầu tư tự nhập Phase 0 (§8).
- **GATE-B** (schema SalaryProduct) = **đã chốt 28/07** theo field list thật lấy từ console;
  `sx/api/chot.py` map cứng đúng schema (xem D22 ở trên).
- **GATE-C** (kho tầng 1) = phương án B (D7): đậu trừ tại Nhập bột.

Còn lại chỉ là dữ liệu Phase 0 nhập tay + acceptance test §10 chạy trên site.

## Ghi chú kỹ thuật quan trọng

- WO sinh từ code luôn `use_multi_level_bom=0` — BOM 3 tầng, multi-level sẽ explode ngược phá
  kiến trúc (gotcha #11 kho skills).
- RM batch pick FIFO qua `use_serial_batch_fields=1` + `batch_no` (bundle tự sinh khi submit,
  đối chiếu source erpnext v16, gotcha #12). `sx/api/mfg.py` là helper dùng chung T1/T2/T3.
- Nước (`is_stock_item=0`) tự động bị loại khỏi Manufacture SE (`get_bom_items_as_dict`
  `include_non_stock_items=False`) — không sinh ledger, không vỡ. Vẫn để trong BOM cân bằng
  khối lượng (D15).
- `chot_ngay` bọc try/except + rollback + báo đúng bước hỏng; huỷ ngược đọc `ds_wo_se` đảo
  thứ tự (gotcha #13). `on_cancel_ngay` thu hồi cả `SX Nhap Bot` **do chính nó tạo** (có trong
  `ds_wo_se`), không đụng phiếu người dùng tự tạo. Validate nghiệp vụ
  (đã chốt / thiếu tồn / thiếu đơn giá) chạy NGOÀI try để lỗi nổi lên nguyên văn cho QC.
- Batch bột nền T1 idempotent (dùng lại đúng lô R khi huỷ + nhập lại) — giữ mắt xích truy xuất.
- ⚠️ **Phase 0:** GIỮ Manufacturing Settings › "Validate Components Quantities Per BOM" **TẮT**.
  Bật nó sẽ vỡ ngày FIFO trừ 1 NVL qua >1 lô (core v16 chỉ khớp dòng RM đầu, không cộng các
  dòng đã tách theo lô).

## Acceptance test

Kịch bản pipeline lệch ngày 9 bước trong `docs/CODER-PACK.md` §10 — pass hết trên site dev
mới coi là xong.
