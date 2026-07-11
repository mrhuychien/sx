# sx — Portal Sản Xuất RVHG

Custom app Frappe/ERPNext v16: số hoá sản xuất bánh & bột đậu xanh RVHG
(1 dây chuyền, 1 ca). Portal SPA tại `/sx` cho tổ trưởng + trạm rang,
dashboard cho quản lý.

- Spec đầy đủ: [`docs/CODER-PACK.md`](docs/CODER-PACK.md)
- Site đích: `a.rongvanghoanggia.com`
- Phương pháp: nextcode + skills `frappe-app-build-profile` / `nextcode-build` /
  `frappe-portal-spa` / `frappe-app-shipping-gotchas`

## Cấu trúc

```
sx/
  hooks.py            # doc_events + fixtures
  modules.txt         # module SX
  sx/doctype/         # 6 DocType + 4 child table (module SX)
  api/                # whitelisted methods (portal.py, chot.py)
  fixtures/           # Role + Custom Field + Print Format
  public/sx/          # SPA: shell.js, lib/, components/, views/, shell.css
  www/                # sx.py + sx.html (serve /sx)
```

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

## Trạng thái build (P0→P7)

- ✅ P0 scaffold · P1 DocType + controllers · P2 fixtures (validator 0 ERROR)
- ✅ P3 API (`api/portal.py`, `api/chot.py`) · P4 portal SPA `/sx` · P5 Print Formats
- ✅ P6 verify: `py_compile` + `node --check` + `validate_shipped_docs.py` 0 ERROR
- ⏳ P7 deploy + Phase 0 data + Acceptance test (mục 10 spec) — cần chạy TRÊN SITE
  (môi trường build này không có bench/site).

## ⚠️ Việc còn chờ Chiến (gates — spec mục 12)

1. **GATE-A** — dữ liệu nền Phase 0 (làm tay trên Desk, spec mục 8): số liệu BOM
   thật (định mức tầng 1, công thức trộn từng SKU, cỡ mẻ chuẩn), đơn giá vào hộp
   2 phương thức, giới hạn CCP °C, warehouse, item + `custom_sx_nhom` +
   `custom_batch_prefix`, `SX Settings`, 2 user tablet.
2. **GATE-B** — schema SalaryProduct (app lam-luong): chạy
   `bench --site a.rongvanghoanggia.com console` →
   `frappe.get_meta("SalaryProduct").as_dict()` (thử cả "Salary Product"),
   chốt mapping employee/ngày/sản phẩm/số lượng/đơn giá/thành tiền/phương thức.
   Code hiện tại dùng **mapping adaptive** (`_FIELD_CANDIDATES` trong
   `sx/api/chot.py`) — đọc meta lúc runtime, map được thì chạy, không map được
   thì chốt ngày báo lỗi rõ ràng + rollback (không nửa vời). Sau khi chốt
   GATE-B, sửa `_FIELD_CANDIDATES` thành mapping cứng đã duyệt.
   Nếu SalaryProduct chưa có chỗ chứa `phuong_thuc` → cần duyệt thêm custom field.

## Acceptance test

Kịch bản 1 ngày end-to-end (9 bước) trong `docs/CODER-PACK.md` mục 10 —
pass hết trên site dev mới coi là xong.
