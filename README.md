# sx — Portal Sản Xuất RVHG (v3)

Custom app Frappe/ERPNext v16: số hoá + **truy xuất nguồn gốc** sản xuất RVHG — 2 nhánh
**bánh đậu xanh** (8 loại ruột) và **bột đậu** (8 công thức). Pipeline lệch ngày, BOM 3 tầng,
**công nhân 0 chạm** — 2 QC nhập toàn bộ số liệu. Truy xuất mức **ngày × loại**, FIFO tự động
toàn tuyến (không ai chọn lô).

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

3 role: `SX Ghi So` (QC#1) / `SX Vao Hop` (QC#2) / `SX Quan Ly`. Portal `/sx` card-based,
3 view (ghiso / vaohop / quanly) — mỗi view lắp từ CARD theo `sx/config/roles.py`. Numpad phím
to, mã lô hiển thị **cực to** để ghi thẻ tay (D13), chốt ngày modal 2 bước.

## ⚠️ Tính độc lập (spec §2.1 — rủi ro đã cân nhắc, chủ đầu tư chấp nhận)

Người nhập số liệu sản xuất là **QC** — vai trò kép. Hai điều kiện giảm thiểu bắt buộc:
1. **2 QC tách vai:** `ghiso@rvhg` (ghi số) ≠ `vaohop@rvhg` (vào hộp + chốt ngày). Không tài
   khoản chung. Mọi DocType `SX *` bật `track_changes` (bằng chứng ai nhập gì).
2. **Người thẩm tra hồ sơ bên app `iso` (làm sau) KHÔNG được là người đã nhập số bên `sx`.**

Lộ trình dài hạn: chuyển dần từng card về đúng tổ sản xuất — chỉ cần sửa `sx/config/roles.py`
(ROLE_VIEWS / VIEW_CARDS / CARD_ROLES), KHÔNG sửa UI, KHÔNG sửa từng method API.

## Cài đặt

```bash
cd ~/frappe-bench
bench get-app https://github.com/mrhuychien/sx
bench --site a.rongvanghoanggia.com install-app sx
```

## Deploy (sau mỗi lần pull code mới)

```bash
bench --site a.rongvanghoanggia.com migrate   # custom field / schema mới
bench build --app sx                          # đẩy JS/CSS ra /assets
bench restart                                 # nạp lại Python
```

## Seed định mức (Item + BOM tầng 1/2) — ship sẵn trong app

Định mức đi kèm app (`sx/seed/rvhg_v6.json`, sinh tự động từ
`docs/RVHG_dinh_muc_BOM_v6.xlsx` — **16/16 câu hỏi đã chốt**). Sau khi có Company +
3 Warehouse + `SX Settings`:

```bash
bench --site a.rongvanghoanggia.com execute sx.seed.seed_all --kwargs "{'dry_run': 1}"  # xem trước
bench --site a.rongvanghoanggia.com execute sx.seed.seed_all                            # ghi thật
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
  cộng dồn. Huỷ ngày chỉ **gỡ dòng ngày đó**, các ngày khác giữ nguyên. Không đụng
  `tienanca`/`andem`/chuyên cần/bảo hiểm.

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
