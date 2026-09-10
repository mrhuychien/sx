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

/** Mở một trang HTML dựng sẵn trong tab mới. Trả false nếu bị chặn pop-up. */
function moTrang(html) {
  // Blob thay vì điều hướng: giữ nguyên trang đang nhập liệu (QC hay bị ngắt
  // quãng), và chạy được cả khi mất mạng vì HTML dựng ngay tại máy.
  const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
  const w = window.open(url, '_blank');
  setTimeout(() => URL.revokeObjectURL(url), 60000);
  return !!w;
}

const KHUNG = `
 body { font-family: Arial, sans-serif; margin: 8mm; }
 .luoi { display: flex; flex-wrap: wrap; gap: 5mm; }
 .qr { border-collapse: collapse; margin: 0 auto; table-layout: fixed; }
 .qr td { padding: 0; }
 .qr td.d { background: #000; }
 .qr td.s { background: #fff; }
 .huongdan { margin-bottom: 5mm; font-size: 10pt; color: #444; }
 @media print { .huongdan { display: none } }`;

/**
 * Thẻ ĐĂNG NHẬP cho một tài khoản portal (D81).
 *
 * Ba thứ trên một tờ, vì chúng phục vụ ba tình huống khác nhau:
 *   · QR      — lần đầu, quét là vào thẳng. DÙNG MỘT LẦN.
 *   · SĐT     — tên đăng nhập, dùng mãi.
 *   · Mật khẩu— đường vào khi máy mất phiên, hoặc đổi điện thoại.
 * In mật khẩu ra giấy là đánh đổi có ý thức: xưởng không có email để gửi, mà bắt
 * quản lý đọc mật khẩu qua điện thoại thì sai một ký tự là gọi lại lần nữa.
 */
export function moTrangInDangNhap(ds) {
  const the = ds.map((e) => `
    <div class="the">
      <div class="ten">${esc(e.ten)}</div>
      <div class="vai">${esc(e.nhan_role || '')}</div>
      ${veQR(e.link, 3)}
      <div class="nhac">Quét để vào lần đầu · dùng được MỘT lần${
  e.het_han ? ` · hết hạn ${esc(veNgay(e.het_han))}` : ''}</div>
      <div class="o">
        <div class="nhan">Số điện thoại</div>
        <div class="gt">${esc(e.sdt)}</div>
        <div class="nhan">Mật khẩu</div>
        <div class="gt mk">${esc(e.mat_khau || '(không đổi)')}</div>
      </div>
      <div class="chan">Giữ tờ này như giữ chìa khoá.</div>
    </div>`).join('');

  return moTrang(`<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Thẻ đăng nhập</title><style>${KHUNG}
 .the { width: 62mm; border: 1px solid #999; border-radius: 3mm; padding: 4mm;
   text-align: center; page-break-inside: avoid; }
 .ten { font-size: 13pt; font-weight: 700; }
 .vai { font-size: 9pt; color: #555; margin-bottom: 2mm; }
 .nhac { font-size: 7.5pt; color: #555; margin: 1.5mm 0 2mm; line-height: 1.3; }
 .o { border-top: 1px dashed #bbb; padding-top: 2mm; text-align: left; }
 .nhan { font-size: 7.5pt; color: #666; text-transform: uppercase; letter-spacing: .5px; }
 .gt { font-family: monospace; font-size: 12pt; font-weight: 700; margin-bottom: 1.5mm;
   letter-spacing: 1px; word-break: break-all; }
 .gt.mk { font-size: 14pt; }
 .chan { margin-top: 2mm; font-size: 7.5pt; color: #888; }
</style></head><body>
<div class="huongdan">Cắt rời từng thẻ, đưa TẬN TAY người dùng. Trên thẻ có mật khẩu
 — đừng để lại trên bàn. Mã QR chỉ quét được một lần; quét xong thẻ vẫn giữ lại vì
 còn số điện thoại và mật khẩu để đăng nhập sau này.</div>
<div class="luoi">${the}</div>
</body></html>`);
}

/** "2026-09-24 15:00:00" -> "24/09" */
function veNgay(iso) {
  const d = String(iso || '').slice(0, 10).split('-');
  return d.length === 3 ? `${d[2]}/${d[1]}` : String(iso || '');
}

/** Dựng trang in từ [{ten, ma}] và mở tab mới. Trả false nếu bị chặn pop-up. */
export function moTrangInThe(ds) {
  const the = ds.map((e) => `
    <div class="the">
      <div class="ten">${esc(e.ten)}</div>
      ${veQR(e.ma, 3)}
      <div class="ma">${esc(e.ma)}</div>
    </div>`).join('');

  const html = `<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Thẻ quét công nhân</title><style>${KHUNG}
 .the { width: 54mm; border: 1px solid #999; border-radius: 3mm; padding: 3mm;
   text-align: center; page-break-inside: avoid; }
 .ten { font-size: 12pt; font-weight: 700; margin-bottom: 2mm;
   white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
 .ma { font-family: monospace; font-size: 9pt; letter-spacing: 1px; margin-top: 1.5mm; }
</style></head><body>
<div class="huongdan">In thử MỘT thẻ và quét thử trước khi in cả ${ds.length} cái.
 In ở 100% (không "fit to page"), và để chế độ in màu/độ nét cao — QR co giãn lệch
 tỉ lệ là máy quét đọc sai.</div>
<div class="luoi">${the}</div>
</body></html>`;
  return moTrang(html);
}
