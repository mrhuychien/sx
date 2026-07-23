// Card Nhập bột — list lô R chờ nhận → tap → xác nhận (mã lô to) → Manufacture T1.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatKg, formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';

export async function render({ container, boot, call, reload }) {
  container.className = 'sx-card';
  const list = boot.lo_cho_nhap_bot || [];
  container.innerHTML = `
    <div class="sx-field-label">Nhập bột — lô R chờ nhận (${list.length})</div>
    <div id="sx-nb-list"></div>
  `;
  const node = container.querySelector('#sx-nb-list');
  node.innerHTML = list.map((l) => `
    <div class="sx-row-item">
      <b>${esc(l.lo_rang)}</b> · rang ${esc(l.ngay_rang)} · ${esc(l.loai_dau)} · ${esc(formatKg(l.dau_kg))}
      <button type="button" class="sx-btn sx-btn-warn sx-nb-btn" data-xd="${esc(l.name)}" data-lo="${esc(l.lo_rang)}">NHẬN</button>
    </div>`).join('') || '<div class="sx-muted">Không có lô nào chờ nhập.</div>';
  node.querySelectorAll('.sx-nb-btn').forEach((btn) => {
    btn.addEventListener('click', () => xacNhan(btn.dataset.xd, btn.dataset.lo, call, reload));
  });
}

function xacNhan(xuatDau, loRang, call, reload) {
  const m = openModal({ title: 'Nhận bột vào kho' });
  m.body.innerHTML = `
    <div class="sx-lot-display">${esc(loRang)}</div>
    <div class="sx-modal-msg" style="text-align:center">Xác nhận đã nhận bột lô này từ khâu nghiền?<br>
      Hệ thống tự tính kg theo định mức + trừ đậu FIFO.</div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nb-ok">✓ NHẬN BỘT LÔ NÀY</button>
  `;
  m.body.querySelector('#sx-nb-ok').addEventListener('click', async (e) => {
    e.currentTarget.disabled = true;
    try {
      const r = await call('sx.api.tang1.nhap_bot', { xuat_dau: xuatDau });
      m.close();
      toast(`Đã nhập ${formatNumber(r.bot_kg, 1)} kg bột — lô ${r.lo_rang}.`);
      reload();
    } catch (err) {
      e.target.disabled = false;
      toastErr(err.message);
    }
  });
}
