// View Nhập kho (#/nhapkho) — thủ kho nhận TP từ xưởng vào Kho TP (D51).

import { el } from '/assets/sx/sx/lib/dom.js';

export async function render({ container, cards, mountCard }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);
  wrap.appendChild(el('h1', 'sx-h1', 'Nhập kho thành phẩm'));
  for (const c of cards) await mountCard(c, wrap);
}
