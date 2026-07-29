// Card Lưu đồ tồn BTP tầng 2/3 (D32) — 2 nhánh bánh đậu xanh / bột đậu.
//
// Khác card tầng 1: ở đây KHÔNG có nút công đoạn. Bột bánh / bột đậu sinh khi báo mẻ
// và bị trừ lúc TP vào hộp (backflush — D8), nên đây là màn hình ĐỌC: thấy hàng đang
// đọng ở khúc nào trước khi quyết định hôm nay trộn gì.

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
  const chang = n.chang.map((c, i) => `
    ${i ? '<div class="sx-lb-mui">→</div>' : ''}
    <div class="sx-lb-o">
      <div class="sx-lb-nhan">${esc(c.nhan)}${
        c.dung_chung ? '<span class="sx-lb-chung">dùng chung</span>' : ''}</div>
      ${veItems(c.items)}
    </div>`).join('');
  return `
    <div class="sx-lb-nhanh">
      <div class="sx-lb-ten">${esc(n.ten)}</div>
      <div class="sx-lb-day">
        ${chang}
        <div class="sx-lb-mui">→</div>
        <div class="sx-lb-o sx-lb-tp">
          <div class="sx-lb-nhan">Thành phẩm</div>
          <div class="sx-lb-tong">${esc(formatNumber(n.tp.tong, 0))}</div>
          <div class="sx-lb-phu">${esc(n.tp.so_sku)}/${esc(n.tp.tong_sku)} SKU còn hàng</div>
        </div>
      </div>
    </div>`;
}

function veItems(items) {
  if (!items || !items.length) {
    return '<div class="sx-lb-trong">chưa khai item</div>';
  }
  // Hết hàng vẫn phải hiện: "loại này đang 0" là thông tin, không phải thứ để giấu.
  return `<table class="sx-lb-bang">${items.map((it) => `
    <tr class="${it.am ? 'sx-lb-am' : ''}${Number(it.ton) ? '' : ' sx-lb-het'}">
      <td>${esc(it.ten)}</td>
      <td class="sx-lb-so">${esc(formatKg(it.ton))}</td>
      <td class="sx-lb-me">${it.so_me != null ? `${esc(formatNumber(it.so_me, 1))} mẻ` : ''}</td>
    </tr>`).join('')}</table>`;
}
