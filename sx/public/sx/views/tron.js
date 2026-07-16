// View Tổ trộn (#/tron) — (1) Nhập bột: list lô R chờ -> tap -> xác nhận (mã lô TO).
// (2) Báo mẻ cuối ngày: thẻ 9 loại hỗn hợp, numpad số mẻ, lưu.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatKg, formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, call, refresh }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);

  const ngay = boot.ngay_sx;
  const daChot = ngay && ngay.docstatus === 1;
  const soMe = {};
  ((ngay && ngay.bao_me) || []).forEach((r) => { soMe[r.hon_hop] = r.so_me; });

  wrap.innerHTML = `
    <h1 class="sx-h1">Tổ trộn</h1>
    <div class="sx-card">
      <div class="sx-field-label">1 · Nhập bột vào kho (lô R chờ nhận)</div>
      <div id="sx-nb-list"></div>
    </div>
    <div class="sx-card">
      <div class="sx-field-label">2 · Báo mẻ hôm nay ${daChot ? '(đã chốt — chỉ xem)' : '(bấm thẻ để nhập số mẻ)'}</div>
      <div class="sx-sp-card-grid" id="sx-bm-grid"></div>
      ${daChot ? '' : '<button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-bm-luu">LƯU BÁO MẺ</button>'}
    </div>
  `;

  // ── nhập bột
  const nbList = wrap.querySelector('#sx-nb-list');
  nbList.innerHTML = (boot.lo_cho_nhap_bot || []).map((l) => `
    <div class="sx-row-item">
      <b>${esc(l.lo_rang)}</b> · rang ${esc(l.ngay_rang)} · ${esc(l.so_bao)} bao (${esc(formatKg(l.dau_kg))})
      <button type="button" class="sx-btn sx-btn-warn sx-nb-btn" data-xd="${esc(l.name)}" data-lo="${esc(l.lo_rang)}">NHẬN BỘT</button>
    </div>`).join('') || '<div class="sx-muted">Không có lô nào chờ nhập.</div>';
  nbList.querySelectorAll('.sx-nb-btn').forEach((btn) => {
    btn.addEventListener('click', () => xacNhanNhapBot(btn.dataset.xd, btn.dataset.lo, call, refresh));
  });

  // ── báo mẻ
  const grid = wrap.querySelector('#sx-bm-grid');
  function paintGrid() {
    grid.innerHTML = '';
    (boot.items_hh || []).forEach((it) => {
      const sm = soMe[it.name] || 0;
      const btn = el('button', `sx-sp-card${sm > 0 ? ' sx-sp-card-on' : ''}`);
      btn.type = 'button';
      btn.innerHTML = `<div class="sx-sp-card-name">${esc(it.item_name || it.name)}</div>
        <div class="${sm > 0 ? 'sx-sp-card-count' : 'sx-muted'}">${sm > 0 ? `${sm} mẻ` : '—'}</div>
        <div class="sx-muted">mẻ ${esc(formatNumber(it.co_me_chuan_kg, 1))} kg</div>`;
      if (!daChot) {
        btn.addEventListener('click', () => {
          openNumpad({
            title: `${it.item_name || it.name} — số mẻ hôm nay`,
            initial: soMe[it.name] || '',
            unit: 'mẻ',
            onOk: (v) => { soMe[it.name] = Math.round(v); paintGrid(); },
          });
        });
      }
      grid.appendChild(btn);
    });
    if (!(boot.items_hh || []).length) {
      grid.innerHTML = '<div class="sx-muted">Chưa có Item nhóm BTP-HH — quản lý khai báo trên Desk.</div>';
    }
  }
  paintGrid();

  const luuBtn = wrap.querySelector('#sx-bm-luu');
  if (luuBtn) {
    luuBtn.addEventListener('click', async () => {
      luuBtn.disabled = true;
      try {
        const phieu = ngay || await call('sx.api.portal.get_or_create_ngay', {});
        const rows = Object.entries(soMe)
          .filter(([, v]) => v > 0)
          .map(([hon_hop, so_me]) => ({ hon_hop, so_me }));
        await call('sx.api.portal.bao_me', { ngay_sx: phieu.name, rows: JSON.stringify(rows) });
        toast('Đã lưu báo mẻ.');
        await refresh();
        window.location.reload();
      } catch (e) {
        luuBtn.disabled = false;
        toastErr(e.message);
      }
    });
  }
}

function xacNhanNhapBot(xuatDau, loRang, call, refresh) {
  const m = openModal({ title: 'Nhận bột vào kho' });
  m.body.innerHTML = `
    <div class="sx-lot-display">${esc(loRang)}</div>
    <div class="sx-modal-msg" style="text-align:center">Xác nhận đã nhận bột lô này từ khâu nghiền?<br>
      Hệ thống tự tính kg theo định mức — không cần cân.</div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nb-ok">✓ NHẬN BỘT LÔ NÀY</button>
  `;
  m.body.querySelector('#sx-nb-ok').addEventListener('click', async (e) => {
    e.currentTarget.disabled = true;
    try {
      const r = await call('sx.api.portal.nhap_bot', { xuat_dau: xuatDau });
      m.close();
      toast(`Đã nhập ${formatNumber(r.bot_kg, 1)} kg bột — lô ${r.lo_rang}.`);
      await refresh();
      window.location.reload();
    } catch (err) {
      e.target.disabled = false;
      toastErr(err.message);
    }
  });
}
