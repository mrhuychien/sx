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
QC#2             : SX Bang Vao Hop (lương SP theo người × SKU) + CHỐT NGÀY
Chốt ngày        : chot_ngay → T1 TỰ NHẬP BỘT lô R rang hôm trước (Manufacture: trừ đỗ
                              FIFO Kho NVL → bột Kho BTP, batch = lô R). Đỗ CHỈ trừ ở đây (D7)
                            → T2 (topo-sort: đường hoán → bột bánh/bột đậu, WO+SE,
                              bột nền FIFO lô R cũ nhất)
                            → T3 (WO+SE TP theo SKU, bột bánh/bột đậu FIFO) → SalaryProduct
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

**Còn phải làm tay:** BOM **tầng 3 + Item TP + bao bì** (CH-13 chốt: chủ đầu tư tự tạo trên
ERPNext — **chặn chốt ngày nhánh TP**), Manufacturing Settings, tồn đầu, `SX Don Gia Vao Hop`,
2 user tablet — xem `docs/CODER-PACK.md` §8.

## Thay đổi 28/07 (sau khi chạy thử trên site)

- **D17 — bỏ BTP "Hỗn hợp màu đỏ/vàng":** màu + nước cho thẳng vào BOM đường hoán khoai
  môn/cốm theo đúng tỉ lệ. Bớt 2 item + 2 BOM + 2 lần báo mẻ/ngày.
- **D18 — bỏ card "Nhập bột":** chốt ngày tự nhập bột cho lô R **rang hôm trước**
  (đã qua khâu nghiền). QC không bấm; kho + truy xuất + trừ đỗ giữ nguyên. Lô R còn đọng
  (rang lâu mà chưa vào kho) hiện ở dashboard quản lý để phát hiện bất thường.

## Trạng thái build v3 (P0→P7)

- ✅ P0/P1 scaffold + DocType (6 + 4 child) + controllers
- ✅ P2 fixtures (3 role, custom fields, validator 0 ERROR)
- ✅ P3 config/roles.py + api (mfg / tang1 / portal / chot)
- ✅ P4 portal card-based (7 card, 3 view) · P5 Print Formats
- ✅ P6 verify: `py_compile` + `node --check` + `validate_shipped_docs.py` 0 ERROR + review đối kháng
- ⏳ P7 deploy + Phase 0 data + Acceptance test (spec §10) — cần chạy TRÊN SITE

## Gate duy nhất còn lại

**GATE-B** — schema SalaryProduct (app lam-luong): chạy
`bench --site a.rongvanghoanggia.com console` → `frappe.get_meta("SalaryProduct").as_dict()`
(thử cả "Salary Product"), chốt mapping. Code dùng **mapping adaptive**
(`_FIELD_CANDIDATES` trong `sx/api/chot.py`) — map được thì chạy, không map được thì chốt ngày
báo lỗi rõ + rollback. Sau khi chốt, sửa thành mapping cứng. Thiếu chỗ chứa `phuong_thuc` →
duyệt custom field.

> GATE-A (định mức) đã giải quyết = workbook v6 + chủ đầu tư tự nhập Phase 0 (§8).
> GATE-C (kho tầng 1) đã chốt = phương án B (D7): đậu trừ tại Nhập bột.

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
