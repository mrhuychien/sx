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
