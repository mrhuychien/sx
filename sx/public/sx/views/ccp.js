// V2 CCP (#/ccp) — numpad nhiệt độ + GHI; list hôm nay badge Đạt/Lệch;
// lệch -> bắt nhập hành động khắc phục ngay trong modal.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatNumber, formatTime } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';

export async function render({ container, boot, refresh, call }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);

  if (!boot.ngay_sx) {
    wrap.innerHTML = '<div class="sx-card sx-card-center">Chưa mở ngày sản xuất — chưa ghi CCP được.</div>';
    return;
  }
  const ngay = boot.ngay_sx;
  const s = boot.settings;

  wrap.innerHTML = `
    <h1 class="sx-h1">Giám sát rang (CCP)</h1>
    <div class="sx-card sx-card-center">
      <div class="sx-field-label">Giới hạn: ${formatNumber(s.ccp_nhiet_min, 1)}–${formatNumber(s.ccp_nhiet_max, 1)} °C
        · ghi mỗi ${formatNumber(s.tan_suat_ghi_ccp_phut)} phút</div>
      <div class="sx-numpad-display sx-ccp-display"><span class="sx-numpad-value" id="sx-ccp-value">0</span><span class="sx-numpad-unit">°C</span></div>
      <div class="sx-numpad-grid" id="sx-ccp-pad"></div>
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-ccp-ghi">GHI NHIỆT ĐỘ</button>
    </div>
    <div class="sx-card">
      <div class="sx-field-label">Hôm nay (${(boot.ccp_list || []).length} lần)</div>
      <div id="sx-ccp-list"></div>
    </div>
  `;

  let value = '';
  const display = wrap.querySelector('#sx-ccp-value');
  const paint = () => { display.textContent = value || '0'; };
  const pad = wrap.querySelector('#sx-ccp-pad');
  ['7', '8', '9', '4', '5', '6', '1', '2', '3', ',', '0', '⌫'].forEach((k) => {
    const btn = el('button', 'sx-numpad-key');
    btn.type = 'button';
    btn.textContent = k;
    btn.addEventListener('click', () => {
      if (k === '⌫') value = value.slice(0, -1);
      else if (k === ',') { if (!value.includes('.')) value = (value || '0') + '.'; }
      else if (value.replace('.', '').length < 5) value += k;
      paint();
    });
    pad.appendChild(btn);
  });

  paintList(wrap, boot.ccp_list || []);

  wrap.querySelector('#sx-ccp-ghi').addEventListener('click', async (e) => {
    const nhiet = parseFloat(value || '0');
    if (!nhiet) { toastErr('Nhập nhiệt độ trước.'); return; }
    const btn = e.currentTarget;
    btn.disabled = true;
    try {
      const r = await call('sx.api.portal.ghi_ccp', { ngay_sx: ngay.name, nhiet_do_c: nhiet });
      if (r.can_hanh_dong) {
        openHanhDong(ngay, nhiet, r, call, refresh, container);
      } else {
        toast(r.dat ? `Đã ghi ${formatNumber(nhiet, 1)}°C — ĐẠT.` : 'Đã ghi.');
        value = ''; paint();
        const b = await refresh();
        paintList(wrap, b.ccp_list || []);
      }
    } catch (err) {
      toastErr(err.message);
    } finally {
      btn.disabled = false;
    }
  });
}

function paintList(wrap, list) {
  const node = wrap.querySelector('#sx-ccp-list');
  node.innerHTML = list.map((r) => `
    <div class="sx-row-item">
      <span class="sx-badge ${r.dat ? 'sx-badge-ok' : 'sx-badge-err'}">${r.dat ? 'Đạt' : 'Lệch'}</span>
      <b>${esc(formatNumber(r.nhiet_do_c, 1))}°C</b>
      <span class="sx-muted">${esc(formatTime(r.thoi_diem))}</span>
      ${!r.dat && r.hanh_dong_khac_phuc ? `<div class="sx-muted">↳ ${esc(r.hanh_dong_khac_phuc)}</div>` : ''}
    </div>`).join('') || '<div class="sx-muted">Chưa ghi lần nào.</div>';
}

function openHanhDong(ngay, nhiet, r, call, refresh, container) {
  const m = openModal({ title: '⚠ Nhiệt độ LỆCH giới hạn' });
  m.body.innerHTML = `
    <div class="sx-modal-msg">${esc(formatNumber(nhiet, 1))}°C nằm ngoài
      ${esc(formatNumber(r.min, 1))}–${esc(formatNumber(r.max, 1))}°C.
      Nhập hành động khắc phục để ghi nhận (bắt buộc — hồ sơ HACCP).</div>
    <textarea class="sx-textarea" id="sx-hanh-dong" rows="3"
      placeholder="VD: hạ ga, đảo đều, kiểm tra lại sau 10 phút"></textarea>
    <button type="button" class="sx-btn sx-btn-danger sx-btn-big" id="sx-hanh-dong-luu">GHI NHẬN LỆCH + HÀNH ĐỘNG</button>
  `;
  m.body.querySelector('#sx-hanh-dong-luu').addEventListener('click', async (e) => {
    const hanhDong = m.body.querySelector('#sx-hanh-dong').value.trim();
    if (!hanhDong) { toastErr('Phải nhập hành động khắc phục.'); return; }
    e.currentTarget.disabled = true;
    try {
      await call('sx.api.portal.ghi_ccp', {
        ngay_sx: ngay.name, nhiet_do_c: nhiet, hanh_dong: hanhDong,
      });
      toast('Đã ghi nhận lệch + hành động khắc phục.');
      m.close();
      await refresh();
      window.location.reload();
    } catch (err) {
      e.target.disabled = false;
      toastErr(err.message);
    }
  });
}
