// View Vào hộp (#/vaohop) — QC#2. Lắp từ card vaohop + suco + chotngay.

import { el } from '/assets/sx/sx/lib/dom.js';

export async function render({ container, viewName, cards, mountCard, boot }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);
  const ngay = boot.ngay_sx;
  wrap.appendChild(el('h1', 'sx-h1',
    `Vào hộp${ngay ? ` — ${ngay.ngay}` : ''}`
    + (ngay && ngay.docstatus === 1 ? ' <span class="sx-badge sx-badge-ok">Đã chốt</span>' : '')));
  for (const c of cards) {
    await mountCard(c, wrap);
  }
}
