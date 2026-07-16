// View Thủ kho (#/thukho) — Xuất đậu (chọn lô FIFO gợi ý -> stepper -> 1 tap)
// -> hiện MÃ LÔ R CỰC TO để ghi thẻ (D13). Mở lô đường/dầu. List xuất gần đây.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatKg, formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, call, refresh }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);

  wrap.innerHTML = `
    <h1 class="sx-h1">Thủ kho</h1>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-btn-xuat-dau">🫘 XUẤT ĐẬU CHO NGÀY MAI</button>
    <div class="sx-card">
      <div class="sx-field-label">Lô đường / dầu đang mở</div>
      <div id="sx-lo-vat-tu">${(boot.lo_vat_tu || []).map((l) => `
        <div class="sx-row-item"><b>${esc(l.vat_tu)}</b> — ${esc(l.item)}
          ${l.lo_ncc ? `· lô ${esc(l.lo_ncc)}` : ''} <span class="sx-muted">mở ${esc(l.ngay_mo)}</span></div>`).join('')
        || '<div class="sx-muted">Chưa mở lô nào.</div>'}
      </div>
      <button type="button" class="sx-btn sx-btn-warn" id="sx-btn-mo-lo">+ Mở lô đường/dầu mới</button>
    </div>
    <div class="sx-card">
      <div class="sx-field-label">Xuất đậu gần đây</div>
      ${(boot.xuat_dau_gan_day || []).map((x) => `
        <div class="sx-row-item"><b>${esc(x.lo_rang)}</b> · rang ${esc(x.ngay_rang)}
          · ${esc(x.so_bao)} bao (${esc(formatKg(x.dau_kg))}) · đậu ${esc(x.lo_dau_ncc)}</div>`).join('')
        || '<div class="sx-muted">Chưa có phiếu xuất đậu.</div>'}
    </div>
  `;

  wrap.querySelector('#sx-btn-xuat-dau').addEventListener('click', () => openXuatDau(boot, call, refresh));
  wrap.querySelector('#sx-btn-mo-lo').addEventListener('click', () => openMoLo(boot, call, refresh));
}

// ─────────────────────────────────────── xuất đậu ──

function openXuatDau(boot, call, refresh) {
  const m = openModal({ title: 'Xuất đậu cho ngày mai' });
  const state = {
    lo_dau: (boot.lo_dau && boot.lo_dau[0] && boot.lo_dau[0].batch) || null, // FIFO gợi ý
    so_bao: 0,
    kl_bao: boot.settings.kl_bao_dau_kg || 50,
  };
  m.body.innerHTML = `
    <div class="sx-field-label">Lô đậu (cũ nhất chọn sẵn — FIFO)</div>
    <div class="sx-sp-grid" id="sx-xd-lo"></div>
    <div class="sx-field-label">Số bao</div>
    <div class="sx-stepper">
      <button type="button" class="sx-stepper-btn" id="sx-xd-minus">−</button>
      <div class="sx-stepper-value" id="sx-xd-value">0</div>
      <button type="button" class="sx-stepper-btn" id="sx-xd-plus">+</button>
    </div>
    <div class="sx-field-label">KL/bao (kg) — bấm để sửa</div>
    <button type="button" class="sx-value-btn" id="sx-xd-kl"></button>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-xd-ok">XUẤT ĐẬU</button>
  `;
  const loGrid = m.body.querySelector('#sx-xd-lo');
  (boot.lo_dau || []).forEach((l, i) => {
    const b = el('button', `sx-sp-chip${l.batch === state.lo_dau ? ' sx-sp-chip-on' : ''}`);
    b.type = 'button';
    b.textContent = `${l.batch} (${formatNumber(l.qty, 0)} kg)${i === 0 ? ' ⭐' : ''}`;
    b.addEventListener('click', () => {
      state.lo_dau = l.batch;
      loGrid.querySelectorAll('.sx-sp-chip').forEach((x) => x.classList.remove('sx-sp-chip-on'));
      b.classList.add('sx-sp-chip-on');
    });
    loGrid.appendChild(b);
  });
  if (!(boot.lo_dau || []).length) {
    loGrid.innerHTML = '<div class="sx-muted">Không có lô đậu tồn — kiểm tra nhập kho NVL.</div>';
  }

  const valueNode = m.body.querySelector('#sx-xd-value');
  m.body.querySelector('#sx-xd-minus').addEventListener('click', () => {
    state.so_bao = Math.max(0, state.so_bao - 1);
    valueNode.textContent = state.so_bao;
  });
  m.body.querySelector('#sx-xd-plus').addEventListener('click', () => {
    state.so_bao += 1;
    valueNode.textContent = state.so_bao;
  });

  const klBtn = m.body.querySelector('#sx-xd-kl');
  const paintKl = () => { klBtn.textContent = `${formatNumber(state.kl_bao, 1)} kg`; };
  paintKl();
  klBtn.addEventListener('click', () => {
    openNumpad({
      title: 'KL/bao (kg)', initial: state.kl_bao, allowDecimal: true, unit: 'kg',
      onOk: (v) => { if (v > 0) state.kl_bao = v; paintKl(); },
    });
  });

  m.body.querySelector('#sx-xd-ok').addEventListener('click', async (e) => {
    if (!state.lo_dau) { toastErr('Chọn lô đậu trước.'); return; }
    if (state.so_bao <= 0) { toastErr('Số bao phải > 0.'); return; }
    e.currentTarget.disabled = true;
    try {
      const r = await call('sx.api.portal.xuat_dau', {
        lo_dau: state.lo_dau, so_bao: state.so_bao, kl_bao: state.kl_bao,
      });
      m.close();
      showLoRang(r, refresh);
    } catch (err) {
      e.target.disabled = false;
      toastErr(err.message);
    }
  });
}

// Mã lô R hiển thị CỰC TO để chép ra thẻ vật lý (D13)
function showLoRang(r, refresh) {
  const m = openModal({ title: 'Ghi mã này ra thẻ lô' });
  m.body.innerHTML = `
    <div class="sx-lot-display">${esc(r.lo_rang)}</div>
    <div class="sx-modal-msg" style="text-align:center">
      Rang ngày ${esc(r.ngay_rang)} · ${esc(formatKg(r.dau_kg))} đậu.<br>
      Chép mã trên vào thẻ, treo theo lô.</div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-lot-ok">✓ ĐÃ GHI THẺ</button>
  `;
  m.body.querySelector('#sx-lot-ok').addEventListener('click', async () => {
    m.close();
    toast(`Đã xuất đậu — lô ${r.lo_rang}.`);
    await refresh();
    window.location.reload();
  });
}

// ─────────────────────────────────────── mở lô đường/dầu ──

function openMoLo(boot, call, refresh) {
  const m = openModal({ title: 'Mở lô đường/dầu mới' });
  const state = { vat_tu: null, item: '' };
  m.body.innerHTML = `
    <div class="sx-field-label">Vật tư</div>
    <div class="sx-pt-grid">
      <button type="button" class="sx-btn sx-btn-ghost sx-btn-big" data-vt="Đường">🍬 Đường</button>
      <button type="button" class="sx-btn sx-btn-ghost sx-btn-big" data-vt="Dầu">🛢️ Dầu</button>
    </div>
    <div class="sx-field-label">Mã Item (quản lý cung cấp)</div>
    <input class="sx-textarea" id="sx-lo-item" placeholder="VD: DUONG-01">
    <div class="sx-field-label">Lô NCC (không bắt buộc)</div>
    <input class="sx-textarea" id="sx-lo-ncc" placeholder="Mã batch lô nhà cung cấp">
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-lo-ok">MỞ LÔ (đóng lô cũ)</button>
  `;
  m.body.querySelectorAll('[data-vt]').forEach((b) => {
    b.addEventListener('click', () => {
      state.vat_tu = b.dataset.vt;
      m.body.querySelectorAll('[data-vt]').forEach((x) => x.classList.remove('sx-btn-primary'));
      b.classList.add('sx-btn-primary');
    });
  });
  m.body.querySelector('#sx-lo-ok').addEventListener('click', async (e) => {
    const item = m.body.querySelector('#sx-lo-item').value.trim();
    if (!state.vat_tu || !item) { toastErr('Chọn vật tư + nhập mã Item.'); return; }
    e.currentTarget.disabled = true;
    try {
      await call('sx.api.portal.mo_lo_vat_tu', {
        vat_tu: state.vat_tu, item, lo_ncc: m.body.querySelector('#sx-lo-ncc').value.trim() || null,
      });
      toast(`Đã mở lô ${state.vat_tu} mới.`);
      m.close();
      await refresh();
      window.location.reload();
    } catch (err) {
      e.target.disabled = false;
      toastErr(err.message);
    }
  });
}
