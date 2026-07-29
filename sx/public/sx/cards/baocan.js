// Card Báo cán — thẻ 8 bột bánh, numpad số mẻ cán (theo dõi tiến độ, KHÔNG chứng từ kho, D8).

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatNumber, nhanNgay } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, call, ensureNgay, reload }) {
  container.className = 'sx-card';
  const ngay = boot.ngay_sx;
  const daChot = ngay && ngay.docstatus === 1;
  const items = boot.items_bot_banh || [];
  const soMe = {};
  ((ngay && ngay.bao_can) || []).forEach((r) => { soMe[r.item_bot_banh] = r.so_me; });

  container.innerHTML = `
    <div class="sx-field-label">Báo cán ${nhanNgay(boot)} ${daChot ? '(đã chốt)' : '(bột bánh)'}</div>
    <div class="sx-sp-card-grid" id="sx-bc-grid"></div>
    ${daChot ? '' : '<button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-bc-luu">LƯU BÁO CÁN</button>'}
  `;
  const grid = container.querySelector('#sx-bc-grid');

  function paintGrid() {
    grid.innerHTML = '';
    items.forEach((it) => {
      const sm = soMe[it.name] || 0;
      const btn = el('button', `sx-sp-card${sm > 0 ? ' sx-sp-card-on' : ''}`);
      btn.type = 'button';
      btn.innerHTML = `<div class="sx-sp-card-name">${esc(it.item_name || it.name)}</div>
        <div class="${sm > 0 ? 'sx-sp-card-count' : 'sx-muted'}">${sm > 0 ? `${formatNumber(sm, 1)} mẻ` : '—'}</div>`;
      if (!daChot) {
        btn.addEventListener('click', () => {
          openNumpad({
            title: `${it.item_name || it.name} — số mẻ cán`, initial: soMe[it.name] || '',
            allowDecimal: true, unit: 'mẻ',
            onOk: (v) => { soMe[it.name] = v; paintGrid(); },
          });
        });
      }
      grid.appendChild(btn);
    });
    if (!items.length) grid.innerHTML = '<div class="sx-muted">Chưa có Item bột bánh (khai trên Desk).</div>';
  }
  paintGrid();

  const luuBtn = container.querySelector('#sx-bc-luu');
  if (luuBtn) {
    luuBtn.addEventListener('click', async () => {
      luuBtn.disabled = true;
      try {
        const ng = await ensureNgay();
        const rows = Object.entries(soMe)
          .filter(([, v]) => v > 0)
          .map(([item_bot_banh, so_me]) => ({ item_bot_banh, so_me }));
        await call('sx.api.portal.bao_can', { ngay_sx: ng.name, rows: JSON.stringify(rows) });
        toast('Đã lưu báo cán.');
        reload();
      } catch (e) {
        luuBtn.disabled = false;
        toastErr(e.message);
      }
    });
  }
}
