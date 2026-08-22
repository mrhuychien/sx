// In thẻ QR cho công nhân (D63) — dựng HTML ngay trên máy rồi mở tab in.
//
// QR vẽ bằng vendor/qrcode.js (MIT), không phụ thuộc thư viện Python nào trên site
// và chạy được cả khi mất mạng. Vẽ ra <table> ô đen/trắng thay vì ảnh: in nét ở
// mọi độ phân giải, không lệ thuộc canvas hay data-URI.

import qrcode from '/assets/sx/sx/vendor/qrcode.js';

const VIEN = 4;   // vùng trắng quanh mã, chuẩn QR đòi tối thiểu 4 ô

function veQR(text, oPx) {
  // Mức sửa lỗi M: chịu được ~15% bẩn/xước — thẻ đeo trong xưởng bột thì cần.
  const qr = qrcode(0, 'M');
  qr.addData(String(text));
  qr.make();
  const n = qr.getModuleCount();
  const canh = (n + VIEN * 2) * oPx;
  let o = `<table class="qr" style="width:${canh}px;height:${canh}px"><tbody>`;
  for (let y = -VIEN; y < n + VIEN; y++) {
    o += '<tr>';
    for (let x = -VIEN; x < n + VIEN; x++) {
      const den = y >= 0 && y < n && x >= 0 && x < n && qr.isDark(y, x);
      o += `<td class="${den ? 'd' : 's'}"></td>`;
    }
    o += '</tr>';
  }
  return `${o}</tbody></table>`;
}

const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

/** Dựng trang in từ [{ten, ma}] và mở tab mới. Trả false nếu bị chặn pop-up. */
export function moTrangInThe(ds) {
  const the = ds.map((e) => `
    <div class="the">
      <div class="ten">${esc(e.ten)}</div>
      ${veQR(e.ma, 3)}
      <div class="ma">${esc(e.ma)}</div>
    </div>`).join('');

  const html = `<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Thẻ quét công nhân</title><style>
 body { font-family: Arial, sans-serif; margin: 8mm; }
 .luoi { display: flex; flex-wrap: wrap; gap: 5mm; }
 .the { width: 54mm; border: 1px solid #999; border-radius: 3mm; padding: 3mm;
   text-align: center; page-break-inside: avoid; }
 .ten { font-size: 12pt; font-weight: 700; margin-bottom: 2mm;
   white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
 .qr { border-collapse: collapse; margin: 0 auto; table-layout: fixed; }
 .qr td { padding: 0; }
 .qr td.d { background: #000; }
 .qr td.s { background: #fff; }
 .ma { font-family: monospace; font-size: 9pt; letter-spacing: 1px; margin-top: 1.5mm; }
 .huongdan { margin-bottom: 5mm; font-size: 10pt; color: #444; }
 @media print { .huongdan { display: none } }
</style></head><body>
<div class="huongdan">In thử MỘT thẻ và quét thử trước khi in cả ${ds.length} cái.
 In ở 100% (không "fit to page"), và để chế độ in màu/độ nét cao — QR co giãn lệch
 tỉ lệ là máy quét đọc sai.</div>
<div class="luoi">${the}</div>
</body></html>`;

  // Blob thay vì điều hướng: giữ nguyên trang đang nhập liệu (QC hay bị ngắt
  // quãng), và chạy được cả khi mất mạng vì HTML dựng ngay tại máy.
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
  const w = window.open(url, '_blank');
  setTimeout(() => URL.revokeObjectURL(url), 60000);
  return !!w;
}
