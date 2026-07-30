// View Vào hộp (#/vaohop) — QC#2. Lắp từ card vaohop + suco + chotngay.

import { el } from '/assets/sx/sx/lib/dom.js';

export async function render({ container, viewName, cards, mountCard, boot }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);
  // KHÔNG có tiêu đề trang: thanh ngày đã nói ngày, khối mực đầu thẻ đã nói
  // "VÀO HỘP HÔM NAY". Thêm h1 nữa là lặp ba lần và ăn mất một dòng màn hình.
  const ngay = boot.ngay_sx;
  if (ngay && ngay.docstatus === 1) {
    wrap.appendChild(el('div', 'sx-badge sx-badge-ok sx-tu-canh', 'Đã chốt'));
  }
  for (const c of cards) {
    await mountCard(c, wrap);
  }
}
