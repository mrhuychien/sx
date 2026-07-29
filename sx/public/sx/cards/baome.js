// Card Báo mẻ — 3 tab (Nấu / Bột bánh / Bột đậu), mỗi thẻ numpad số mẻ (cho 0.5).

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatNumber, nhanNgay } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, call, ensureNgay, reload }) {
  container.className = 'sx-card';
  const ngay = boot.ngay_sx;
  const daChot = ngay && ngay.docstatus === 1;
  const soMe = {};
  ((ngay && ngay.bao_me) || []).forEach((r) => { soMe[r.item_btp] = r.so_me; });

  const tabs = [
    { key: 'nau', label: 'Nấu', items: boot.items_nau || [] },
    { key: 'banh', label: 'Bột bánh', items: boot.items_bot_banh || [] },
    { key: 'dau', label: 'Bột đậu', items: boot.items_bot_dau || [] },
  ];
  let active = 'nau';

  container.innerHTML = `
    <div class="sx-field-label">Báo mẻ ${nhanNgay(boot)} ${daChot ? '(đã chốt — chỉ xem)' : ''}</div>
    <div class="sx-sp-grid" id="sx-bm-tabs"></div>
    <div class="sx-sp-card-grid" id="sx-bm-grid"></div>
    ${daChot ? '' : '<button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-bm-luu">LƯU BÁO MẺ</button>'}
  `;
  const tabBar = container.querySelector('#sx-bm-tabs');
  const grid = container.querySelector('#sx-bm-grid');

  function paintGrid() {
    const items = (tabs.find((t) => t.key === active) || {}).items || [];
    grid.innerHTML = '';
    items.forEach((it) => {
      const sm = soMe[it.name] || 0;
      const btn = el('button', `sx-sp-card${sm > 0 ? ' sx-sp-card-on' : ''}`);
      btn.type = 'button';
      btn.innerHTML = `<div class="sx-sp-card-name">${esc(it.item_name || it.name)}</div>
        <div class="${sm > 0 ? 'sx-sp-card-count' : 'sx-muted'}">${sm > 0 ? `${formatNumber(sm, 1)} mẻ` : '—'}</div>
        <div class="sx-muted">mẻ ${esc(formatNumber(it.co_me_chuan_kg, 1))} kg</div>`;
      if (!daChot) {
        btn.addEventListener('click', () => {
          openNumpad({
            title: `${it.item_name || it.name} — số mẻ`, initial: soMe[it.name] || '',
            allowDecimal: true, unit: 'mẻ',
            onOk: (v) => { soMe[it.name] = v; paintGrid(); },
          });
        });
      }
      grid.appendChild(btn);
    });
    if (!items.length) grid.innerHTML = '<div class="sx-muted">Chưa có Item nhóm này (khai trên Desk).</div>';
  }

  tabs.forEach((t) => {
    const b = el('button', `sx-sp-chip${t.key === active ? ' sx-sp-chip-on' : ''}`);
    b.type = 'button';
    b.textContent = `${t.label} (${t.items.length})`;
    b.addEventListener('click', () => {
      active = t.key;
      tabBar.querySelectorAll('.sx-sp-chip').forEach((x) => x.classList.remove('sx-sp-chip-on'));
      b.classList.add('sx-sp-chip-on');
      paintGrid();
    });
    tabBar.appendChild(b);
  });
  paintGrid();

  const luuBtn = container.querySelector('#sx-bm-luu');
  if (luuBtn) {
    luuBtn.addEventListener('click', async () => {
      luuBtn.disabled = true;
      try {
        const ng = await ensureNgay();
        const rows = Object.entries(soMe)
          .filter(([, v]) => v > 0)
          .map(([item_btp, so_me]) => ({ item_btp, so_me }));
        await call('sx.api.portal.bao_me', { ngay_sx: ng.name, rows: JSON.stringify(rows) });
        toast('Đã lưu báo mẻ.');
        reload();
      } catch (e) {
        luuBtn.disabled = false;
        toastErr(e.message);
      }
    });
  }
}
