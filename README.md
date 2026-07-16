# sx — Portal Sản Xuất RVHG (v2)

Custom app Frappe/ERPNext v16: số hoá + **truy xuất nguồn gốc** sản xuất bánh &
bột đậu xanh RVHG. Pipeline lệch ngày, BOM 3 tầng (Bột → Hỗn hợp → TP),
**4 điểm nhập liệu** cho công nhân lowtech, truy xuất mức **ngày × loại**.

- Spec đầy đủ: [`docs/CODER-PACK.md`](docs/CODER-PACK.md) (v2 — thay thế hoàn toàn v1)
- Site đích: `a.rongvanghoanggia.com`
- Phương pháp: nextcode + skills `frappe-app-build-profile` / `nextcode-build` /
  `frappe-portal-spa` / `frappe-app-shipping-gotchas`

## Kiến trúc nhanh

```
Thủ kho (D-1)  : SX Xuat Dau  → sinh lô rang R (neo lô đậu NCC)  + SX Lo Vat Tu (đường/dầu)
Tổ trộn (D+1)  : SX Nhap Bot  → Batch bột = lô R, Material Receipt vào Kho BTP (GATE-C=A)
Tổ trộn (cuối ngày): báo mẻ (child SX Bao Me trên phiếu ngày)
Tổ đóng gói    : SX Cong Suat May + SX Bang Vao Hop (lương SP theo người×SKU)
Chốt ngày      : chot_ngay → T2 (WO+SE hỗn hợp, bột FIFO lô R cũ nhất)
                            → T3 (WO+SE TP theo SKU, hỗn hợp FIFO) → SalaryProduct
Truy xuất      : TP → Hỗn hợp → lô rang R → lô đậu NCC (portal.truy_xuat + report v16)
```

Roles: `SX Thu Kho` / `SX To Tron` / `SX To Dong Goi` / `SX Quan Ly`.
Portal `/sx`: 4 view theo role (thukho / tron / donggoi / quanly), numpad phím to,
mã lô hiển thị **cực to** để ghi thẻ tay (D13), chốt ngày modal 2 bước.

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

## Trạng thái build v2 (P0→P7)

- ✅ P0 scaffold · P1 DocType (8 + 4 child) + controllers · P2 fixtures (validator 0 ERROR)
- ✅ P3 API (`api/portal.py` 13 method, `api/chot.py` T2+T3) · P4 portal SPA 4 view · P5 Print Formats
- ✅ P6 verify: `py_compile` + `node --check` + `validate_shipped_docs.py` 0 ERROR
- ⏳ P7 deploy + Phase 0 data + Acceptance test (spec §10) — cần chạy TRÊN SITE
  (môi trường build không có bench/site).

## Gates (spec §12)

1. **GATE-A** — trước Phase 0: số liệu BOM thật (yield T1; 9 công thức hỗn hợp +
   cỡ mẻ chuẩn; định mức gam hỗn hợp/hộp + bao bì từng SKU; đơn giá vào hộp
   2 phương thức). Chủ đầu tư cung cấp, không bịa.
2. **GATE-B** — SalaryProduct (app lam-luong): chạy
   `bench --site a.rongvanghoanggia.com console` →
   `frappe.get_meta("SalaryProduct").as_dict()`, chốt mapping. Code hiện dùng
   **mapping adaptive** (`_FIELD_CANDIDATES` trong `sx/api/chot.py`) — map được
   thì chạy, không map được thì chốt ngày báo lỗi rõ + rollback. Sau khi chốt,
   sửa thành mapping cứng. Thiếu chỗ chứa `phuong_thuc` → duyệt custom field.
3. **GATE-C** — kiến trúc kho T1: **đã chốt mặc định A** (SX Nhap Bot =
   Material Receipt bột vào Kho BTP; đậu không trừ realtime, cân đối bằng
   kiểm kê định kỳ — D4). Muốn đổi sang B (Manufacture T1 trừ đậu ngay tại
   nhập bột) thì chỉ sửa `sx_nhap_bot.py::on_submit`.

## Ghi chú kỹ thuật quan trọng

- WO sinh từ code luôn `use_multi_level_bom=0` — BOM 3 tầng, multi-level sẽ
  explode ngược phá kiến trúc (gotcha #11 kho skills).
- RM batch pick FIFO qua `use_serial_batch_fields=1` + `batch_no` (bundle tự
  sinh khi submit — đối chiếu source erpnext v16, gotcha #12).
- `chot_ngay` bọc try/except + rollback + báo đúng bước hỏng; huỷ ngược đọc
  `ds_wo_se` đảo thứ tự (gotcha #13).
- Bột nhập kho với `allow_zero_valuation_rate=1` (costing ngoài scope phase 1).

## Acceptance test

Kịch bản pipeline lệch ngày 9 bước trong `docs/CODER-PACK.md` §10 —
pass hết trên site dev mới coi là xong.
