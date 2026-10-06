// View Vào hộp Tết (#/tet) — D122. Một thẻ làm trọn việc: xem cards/vaohoptet.js.

import { el } from '/assets/sx/sx/lib/dom.js';

export async function render({ container, cards, mountCard }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);
  await Promise.all(cards.map((c) => mountCard(c, wrap)));
}
