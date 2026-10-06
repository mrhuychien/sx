// View Ghi số (#/ghiso) — QC#1 vòng ghi số. Lắp từ các card theo viewCards (config).
//
// PHÂN CẤP (D36): bốn thẻ KHÔNG ngang hàng nhau về tần suất dùng.
//   luutrinh — bấm nhiều lần mỗi ngày, là lý do QC mở màn này  -> mở sẵn, nằm trên
//   baome / baocan — mỗi ngày một lần, cuối ca                 -> gập, mở khi cần
//   suco     — mấy ngày một lần                                -> gập
// Dàn đều cả bốn thì việc chính chìm lẫn với việc phụ và phải cuộn mới thấy.

import { el, esc } from '/assets/sx/sx/lib/dom.js';

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
  // D123: không còn chốt — chỉ báo khi đồng bộ kho lỗi.
  const loi = ngay && ngay.dong_bo && ngay.dong_bo.gs && ngay.dong_bo.gs.loi;
  wrap.appendChild(el('h1', 'sx-h1', 'Ghi sổ'
    + (loi ? ' <span class="sx-badge sx-badge-err">Lỗi đồng bộ kho</span>' : '')));
  if (loi) wrap.appendChild(el('div', 'sx-warn-text', esc(loi)));

  // Song song (D120): mountCard giữ chỗ đồng bộ nên thứ tự vẫn đúng.
  const dang = [];
  for (const c of cards) {
    if (!GAP[c]) {
      dang.push(mountCard(c, wrap));        // việc chính: mở sẵn
      continue;
    }
    // <details> gốc: gập/mở không cần JS, bàn phím và trình đọc màn hình hiểu sẵn
    const fold = el('details', 'sx-fold');
    const sum = el('summary', 'sx-fold-head');
    sum.textContent = GAP[c];
    fold.appendChild(sum);
    const slot = el('div', 'sx-fold-body');
    fold.appendChild(slot);
    wrap.appendChild(fold);
    dang.push(mountCard(c, slot));
  }
  await Promise.all(dang);
}
