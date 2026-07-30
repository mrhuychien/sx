// View Ghi số (#/ghiso) — QC#1 vòng ghi số. Lắp từ các card theo viewCards (config).
//
// PHÂN CẤP (D36): bốn thẻ KHÔNG ngang hàng nhau về tần suất dùng.
//   luutrinh — bấm nhiều lần mỗi ngày, là lý do QC mở màn này  -> mở sẵn, nằm trên
//   baome / baocan — mỗi ngày một lần, cuối ca                 -> gập, mở khi cần
//   suco     — mấy ngày một lần                                -> gập
// Dàn đều cả bốn thì việc chính chìm lẫn với việc phụ và phải cuộn mới thấy.

import { el } from '/assets/sx/sx/lib/dom.js';

// Thẻ nào gập lại + nhãn hiện trên thanh gập. Thẻ không có trong bảng này = mở sẵn.
const GAP = {
  baome: '🍲 Báo mẻ — nấu + trộn',
  baocan: '🥖 Báo cán bột bánh',
  suco: '⚠️ Sự cố dừng chuyền',
};

export async function render({ container, viewName, cards, mountCard, boot }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);
  const ngay = boot.ngay_sx;
  wrap.appendChild(el('h1', 'sx-h1', 'Ghi số — chu trình ngày'
    + (ngay && ngay.docstatus === 1 ? ' <span class="sx-badge sx-badge-ok">Đã chốt</span>' : '')));

  // CHU TRÌNH NGÀY dạng stepper dọc (bản thiết kế): số thứ tự trong vòng tròn, nối
  // bằng vạch dọc. Ghi số là việc theo TRÌNH TỰ trong ngày, không phải 4 thẻ rời —
  // stepper nói ra thứ tự đó, và nhìn là biết đang ở bước nào.
  const chuTrinh = el('div', 'sx-pipe');
  wrap.appendChild(chuTrinh);

  for (let i = 0; i < cards.length; i++) {
    const c = cards[i];
    const buoc = el('div', 'sx-pipe-buoc');
    const cot = el('div', 'sx-pipe-cot');
    const so = el('div', 'sx-pipe-so', String(i + 1));
    cot.appendChild(so);
    if (i < cards.length - 1) cot.appendChild(el('div', 'sx-pipe-vach'));
    buoc.appendChild(cot);

    const than = el('div', 'sx-pipe-than');
    buoc.appendChild(than);
    chuTrinh.appendChild(buoc);

    if (!GAP[c]) {
      await mountCard(c, than);          // việc chính: mở sẵn
      continue;
    }
    const fold = el('details', 'sx-fold');
    const sum = el('summary', 'sx-fold-head');
    sum.textContent = GAP[c];
    fold.appendChild(sum);
    const slot = el('div', 'sx-fold-body');
    fold.appendChild(slot);
    than.appendChild(fold);
    await mountCard(c, slot);
  }
}
