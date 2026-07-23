// Card Xuất đậu — 2 nút loại đỗ + numpad kg → mã lô R CỰC TO để ghi thẻ (D13).

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatKg, formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, call, reload }) {
  container.className = 'sx-card';
  container.innerHTML = `
    <div class="sx-field-label">Xuất đậu cho ngày mai</div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-xd-open">🫘 XUẤT ĐẬU</button>
  `;
  container.querySelector('#sx-xd-open').addEventListener('click', () => openXuatDau(boot, call, reload));
}

function openXuatDau(boot, call, reload) {
  const loaiDau = boot.loai_dau || [];
  if (!loaiDau.length) {
    toastErr('Chưa có loại đỗ (cần BOM bột nền trên Desk).');
    return;
  }
  const m = openModal({ title: 'Xuất đậu' });
  const state = { loai_dau: loaiDau[0].name, kg: 0 };
  m.body.innerHTML = `
    <div class="sx-field-label">Loại đỗ</div>
    <div class="sx-sp-grid" id="sx-xd-loai"></div>
    <div class="sx-field-label">Số kg đậu — bấm để nhập</div>
    <button type="button" class="sx-value-btn" id="sx-xd-kg">0 kg</button>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-xd-ok">XUẤT ĐẬU</button>
  `;
  const grid = m.body.querySelector('#sx-xd-loai');
  loaiDau.forEach((d, i) => {
    const b = el('button', `sx-sp-chip${i === 0 ? ' sx-sp-chip-on' : ''}`);
    b.type = 'button';
    b.textContent = d.item_name || d.name;
    b.addEventListener('click', () => {
      state.loai_dau = d.name;
      grid.querySelectorAll('.sx-sp-chip').forEach((x) => x.classList.remove('sx-sp-chip-on'));
      b.classList.add('sx-sp-chip-on');
    });
    grid.appendChild(b);
  });
  const kgBtn = m.body.querySelector('#sx-xd-kg');
  kgBtn.addEventListener('click', () => {
    openNumpad({
      title: 'Số kg đậu', initial: state.kg, allowDecimal: true, unit: 'kg',
      onOk: (v) => { state.kg = v; kgBtn.textContent = `${formatNumber(v, 1)} kg`; },
    });
  });
  m.body.querySelector('#sx-xd-ok').addEventListener('click', async (e) => {
    if (state.kg <= 0) { toastErr('Nhập số kg đậu.'); return; }
    e.currentTarget.disabled = true;
    try {
      const r = await call('sx.api.tang1.xuat_dau', { loai_dau: state.loai_dau, dau_kg: state.kg });
      m.close();
      showLoRang(r, reload);
    } catch (err) {
      e.target.disabled = false;
      toastErr(err.message);
    }
  });
}

function showLoRang(r, reload) {
  const m = openModal({ title: 'Ghi mã này ra thẻ lô' });
  m.body.innerHTML = `
    <div class="sx-lot-display">${esc(r.lo_rang)}</div>
    <div class="sx-modal-msg" style="text-align:center">Rang ngày ${esc(r.ngay_rang)}.<br>
      Chép mã trên vào thẻ, treo theo lô đậu.</div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-lot-ok">✓ ĐÃ GHI THẺ</button>
  `;
  m.body.querySelector('#sx-lot-ok').addEventListener('click', () => {
    m.close();
    toast(`Đã xuất đậu — lô ${r.lo_rang}.`);
    reload();
  });
}
