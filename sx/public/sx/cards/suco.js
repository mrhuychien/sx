// Card Sự cố — nút ghi sự cố (loại + mô tả + phút dừng). Dùng chung ghi số & vào hộp.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, call, ensureNgay, reload }) {
  container.className = 'sx-card';
  const ngay = boot.ngay_sx;
  const daChot = ngay && ngay.docstatus === 1;
  const suCo = (ngay && ngay.su_co) || [];
  container.innerHTML = `
    <div class="sx-field-label">Sự cố hôm nay (${suCo.length})</div>
    ${suCo.map((s) => `<div class="sx-row-item"><b>${esc(s.loai)}</b> ${esc(s.mo_ta || '')}
      ${s.phut_dung ? `<span class="sx-muted">· dừng ${esc(s.phut_dung)} phút</span>` : ''}</div>`).join('')
      || '<div class="sx-muted">Chưa có sự cố.</div>'}
    ${daChot ? '' : '<button type="button" class="sx-btn sx-btn-warn" id="sx-sc-open">+ Ghi sự cố</button>'}
  `;
  const btn = container.querySelector('#sx-sc-open');
  if (btn) btn.addEventListener('click', () => openSuCo(call, ensureNgay, reload));
}

function openSuCo(call, ensureNgay, reload) {
  const m = openModal({ title: 'Ghi sự cố' });
  const state = { loai: 'Hỏng máy', phut: 0 };
  m.body.innerHTML = `
    <div class="sx-field-label">Loại sự cố</div>
    <div class="sx-sp-grid" id="sx-sc-loai"></div>
    <div class="sx-field-label">Mô tả (không bắt buộc)</div>
    <textarea class="sx-textarea" id="sx-sc-mota" rows="2"></textarea>
    <div class="sx-field-label">Dừng chuyền (phút)</div>
    <button type="button" class="sx-value-btn" id="sx-sc-phut">0 phút</button>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-sc-luu">LƯU SỰ CỐ</button>
  `;
  const grid = m.body.querySelector('#sx-sc-loai');
  ['Hỏng máy', 'Thiếu NVL', 'Mất điện', 'Chất lượng', 'Khác'].forEach((loai) => {
    const b = el('button', `sx-sp-chip${loai === state.loai ? ' sx-sp-chip-on' : ''}`);
    b.type = 'button';
    b.textContent = loai;
    b.addEventListener('click', () => {
      state.loai = loai;
      grid.querySelectorAll('.sx-sp-chip').forEach((x) => x.classList.remove('sx-sp-chip-on'));
      b.classList.add('sx-sp-chip-on');
    });
    grid.appendChild(b);
  });
  const phutBtn = m.body.querySelector('#sx-sc-phut');
  phutBtn.addEventListener('click', () => {
    openNumpad({
      title: 'Dừng chuyền (phút)', initial: state.phut, unit: 'phút',
      onOk: (v) => { state.phut = Math.round(v); phutBtn.textContent = `${state.phut} phút`; },
    });
  });
  m.body.querySelector('#sx-sc-luu').addEventListener('click', async (e) => {
    e.currentTarget.disabled = true;
    try {
      const ngay = await ensureNgay();
      await call('sx.api.portal.ghi_su_co', {
        ngay_sx: ngay.name, loai: state.loai,
        mo_ta: m.body.querySelector('#sx-sc-mota').value, phut_dung: state.phut,
      });
      toast('Đã ghi sự cố.');
      m.close();
      reload();
    } catch (err) {
      e.target.disabled = false;
      toastErr(err.message);
    }
  });
}
