// View Vào hộp (#/vaohop) — QC#2. Lắp từ card vaohop + novaohop + lịch.

import { el, esc } from '/assets/sx/sx/lib/dom.js';

export async function render({ container, viewName, cards, mountCard, boot }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);
  // KHÔNG có tiêu đề trang: thanh ngày đã nói ngày, khối mực đầu thẻ đã nói
  // "VÀO HỘP HÔM NAY". Thêm h1 nữa là lặp ba lần và ăn mất một dòng màn hình.
  const ngay = boot.ngay_sx;
  // D123: không còn chốt — chỉ báo khi đồng bộ phiếu lương lỗi.
  const loi = ngay && ngay.dong_bo && ngay.dong_bo.vh && ngay.dong_bo.vh.loi;
  if (loi) wrap.appendChild(el('div', 'sx-warn-text', `⚠ Lỗi ghi phiếu lương: ${esc(loi)}`));
  await Promise.all(cards.map((c) => mountCard(c, wrap)));   // song song (D120)
}
