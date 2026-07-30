// Card Lưu đồ tồn BTP tầng 2/3 (D32) — 2 nhánh bánh đậu xanh / bột đậu.
//
// Vẽ cùng nhịp với lưu đồ tầng 1: nhãn → SỐ TO → chi tiết, mũi tên nối các chặng.
// Khác card tầng 1 ở chỗ KHÔNG có nút công đoạn — bột bánh / bột đậu sinh khi báo mẻ
// và bị trừ lúc TP vào hộp (backflush — D8), nên đây là màn hình đọc.
// Loại tồn 0 bị lọc từ backend (D34); tồn âm vẫn hiện vì đó là lỗi cần thấy.

import { esc } from '/assets/sx/sx/lib/dom.js';
import { formatKg, formatNumber } from '/assets/sx/sx/lib/format.js';

export async function render({ container, call }) {
  container.className = 'sx-card';
  container.innerHTML = `
    <div class="sx-field-label">Tồn bán thành phẩm theo luồng</div>
    <div id="sx-lb-ds"><div class="sx-muted">Đang tải…</div></div>
  `;
  const box = container.querySelector('#sx-lb-ds');
  let r;
  try {
    r = await call('sx.api.portal.luu_do_btp');
  } catch (e) {
    box.innerHTML = `<div class="sx-warn-text">${esc(e.message || 'Không đọc được lưu đồ.')}</div>`;
    return;
  }
  const nhanh = (r && r.nhanh) || [];
  box.innerHTML = nhanh.length
    ? nhanh.map(veNhanh).join('')
    : '<div class="sx-muted">Chưa có bán thành phẩm nào (cần BOM tầng 2 trên Desk).</div>';
}

function veNhanh(n) {
  const tongNhanh = n.chang.reduce((a, c) => a + (Number(c.tong) || 0), 0);
  const o = n.chang.map((c, i) => veChang(c, i)).join('');
  return `
    <div class="sx-lb-nhanh">
      <div class="sx-lb-head">
        <b class="sx-lb-ten">${esc(n.ten)}</b>
        ${tongNhanh > 0
          ? `<span class="sx-lb-tag">${esc(formatKg(tongNhanh))} bán thành phẩm</span>`
          : '<span class="sx-lb-tag sx-lb-trong">chưa có hàng</span>'}
      </div>
      <div class="sx-lb-day">
        ${o}
        <div class="sx-lb-mui" aria-hidden="true"></div>
        ${veTP(n.tp)}
      </div>
    </div>`;
}

function veChang(c, i) {
  const tong = Number(c.tong) || 0;
  const am = (c.items || []).some((it) => it.am);
  return `
    ${i ? '<div class="sx-lb-mui" aria-hidden="true"></div>' : ''}
    <div class="sx-lb-o${tong > 0 ? ' sx-lb-co' : ''}${am ? ' sx-lb-canhbao' : ''}">
      <div class="sx-lb-nhan">${esc(c.nhan)}${
        c.dung_chung ? '<span class="sx-lb-chung">chung</span>' : ''}</div>
      <div class="sx-lb-so">${esc(formatKg(tong))}</div>
      ${veItems(c.items)}
    </div>`;
}

function veItems(items) {
  if (!items || !items.length) return '<div class="sx-lb-khong">hết hàng</div>';
  return `<div class="sx-lb-ct">${items.map((it) => `
    <div class="sx-lb-dong${it.am ? ' sx-lb-am' : ''}">
      <span class="sx-lb-ten-it" title="${esc(it.item)}">${esc(it.ten)}</span>
      <span class="sx-lb-kg">${esc(formatKg(it.ton))}${
        it.so_me != null ? `<i>${esc(formatNumber(it.so_me, 1))} mẻ</i>` : ''}</span>
    </div>`).join('')}</div>`;
}

function veTP(tp) {
  const co = Number(tp.tong) > 0;
  return `
    <div class="sx-lb-o sx-lb-tp${co ? ' sx-lb-co' : ''}">
      <div class="sx-lb-nhan">Thành phẩm</div>
      <div class="sx-lb-so">${esc(formatNumber(tp.tong, 0))}</div>
      <div class="sx-lb-khong">${esc(tp.so_sku)}/${esc(tp.tong_sku)} SKU còn hàng</div>
    </div>`;
}
