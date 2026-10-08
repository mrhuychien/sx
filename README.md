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
  và bấm một mã đều ra đủ dòng theo HSD. Thêm mã đã có dòng → hỏi sửa dòng nào hay
  **+ DÒNG HSD KHÁC**. Hai dòng cùng mã cùng HSD → duyệt bị chặn, bảo gộp.
- **Lô cũ chưa có HSD**: thẻ *Lô cũ chưa có HSD* (màn Nhập kho + Quản lý, tự ẩn khi hết) —
  liệt kê lô thành phẩm không HSD (còn tồn trước), HSD điền sẵn = NSX + hạn dùng; thủ kho
  soát theo bao bì rồi **GHI HSD**. Không ghi đè HSD đã có, không nhận HSD trước NSX.

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
  Bấm vào để sửa theo HSD in trên bao bì (có nút nhanh +3/+6/+9/+12 tháng).
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
