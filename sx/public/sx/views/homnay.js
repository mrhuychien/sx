// V1 Hôm nay (#/) — chưa mở ngày: form mở ngày; đã mở: thẻ trạng thái + Sự cố + CHỐT NGÀY.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatKg, formatNumber, formatVND, phutTuLuc } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, ctx, refresh, call }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);

  if (!boot.ngay_sx) {
    if (!ctx.isToTruong) {
      wrap.innerHTML = '<div class="sx-card sx-card-center">Chưa mở ngày sản xuất.<br>Chờ tổ trưởng mở ngày.</div>';
      return;
    }
    renderMoNgay(wrap, boot, call, async () => {
      await refresh();
      window.location.reload();
    });
    return;
  }

  renderTrangThai(wrap, boot, ctx, call, refresh);
}

// ───────────────────────────────────────── form mở ngày ──

function renderMoNgay(wrap, boot, call, done) {
  const state = {
    chay_tang_1: false,
    so_bao: 0,
    kl_bao: boot.settings.kl_bao_dau_kg || 50,
    sp: new Set(),
  };

  wrap.innerHTML = `
    <h1 class="sx-h1">Mở ngày sản xuất</h1>
    <div class="sx-card">
      <button type="button" class="sx-toggle" id="sx-toggle-rang">
        <span class="sx-toggle-label">Có rang bột hôm nay</span>
        <span class="sx-toggle-knob"></span>
      </button>
      <div id="sx-rang-detail" style="display:none">
        <div class="sx-field-label">Số bao đậu đưa vào</div>
        <div class="sx-stepper">
          <button type="button" class="sx-stepper-btn" id="sx-bao-minus">−</button>
          <div class="sx-stepper-value" id="sx-bao-value">0</div>
          <button type="button" class="sx-stepper-btn" id="sx-bao-plus">+</button>
        </div>
        <div class="sx-field-label">Khối lượng/bao (kg) — bấm để sửa</div>
        <button type="button" class="sx-value-btn" id="sx-kl-bao"></button>
      </div>
    </div>
    <div class="sx-card">
      <div class="sx-field-label">Sản phẩm đóng hộp hôm nay</div>
      <div class="sx-sp-grid" id="sx-sp-grid"></div>
    </div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-mo-ngay">MỞ NGÀY</button>
  `;

  const toggle = wrap.querySelector('#sx-toggle-rang');
  const rangDetail = wrap.querySelector('#sx-rang-detail');
  toggle.addEventListener('click', () => {
    state.chay_tang_1 = !state.chay_tang_1;
    toggle.classList.toggle('sx-toggle-on', state.chay_tang_1);
    rangDetail.style.display = state.chay_tang_1 ? '' : 'none';
  });

  const baoValue = wrap.querySelector('#sx-bao-value');
  wrap.querySelector('#sx-bao-minus').addEventListener('click', () => {
    state.so_bao = Math.max(0, state.so_bao - 1);
    baoValue.textContent = state.so_bao;
  });
  wrap.querySelector('#sx-bao-plus').addEventListener('click', () => {
    state.so_bao += 1;
    baoValue.textContent = state.so_bao;
  });

  const klBtn = wrap.querySelector('#sx-kl-bao');
  const paintKl = () => { klBtn.textContent = `${formatNumber(state.kl_bao, 1)} kg`; };
  paintKl();
  klBtn.addEventListener('click', () => {
    openNumpad({
      title: 'Khối lượng/bao (kg)',
      initial: state.kl_bao,
      allowDecimal: true,
      unit: 'kg',
      onOk: (v) => { if (v > 0) state.kl_bao = v; paintKl(); },
    });
  });

  const grid = wrap.querySelector('#sx-sp-grid');
  (boot.items_tp || []).forEach((it) => {
    const btn = el('button', 'sx-sp-chip');
    btn.type = 'button';
    btn.innerHTML = esc(it.item_name || it.name);
    btn.addEventListener('click', () => {
      if (state.sp.has(it.name)) state.sp.delete(it.name);
      else state.sp.add(it.name);
      btn.classList.toggle('sx-sp-chip-on', state.sp.has(it.name));
    });
    grid.appendChild(btn);
  });
  if (!(boot.items_tp || []).length) {
    grid.innerHTML = '<div class="sx-muted">Chưa có Item nhóm TP — quản lý cần khai báo trên Desk.</div>';
  }

  wrap.querySelector('#sx-mo-ngay').addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    if (state.chay_tang_1 && state.so_bao <= 0) { toastErr('Nhập số bao đậu trước.'); return; }
    btn.disabled = true;
    try {
      await call('sx.api.portal.mo_ngay', {
        chay_tang_1: state.chay_tang_1 ? 1 : 0,
        so_bao: state.so_bao,
        kl_bao: state.kl_bao,
        ds_san_pham: JSON.stringify([...state.sp]),
      });
      toast('Đã mở ngày sản xuất.');
      await done();
    } catch (err) {
      btn.disabled = false;
      toastErr(err.message);
    }
  });
}

// ───────────────────────────────────────── thẻ trạng thái ──

function renderTrangThai(wrap, boot, ctx, call, refresh) {
  const ngay = boot.ngay_sx;
  const daChot = ngay.docstatus === 1;
  const ccpCount = (boot.ccp_list || []).length;
  const ccpGanNhat = ccpCount ? boot.ccp_list[0].thoi_diem : null;
  const phut = ccpGanNhat ? phutTuLuc(ccpGanNhat) : null;
  const ccpQuaHan = ngay.chay_tang_1 && !daChot
    && (phut == null || phut > boot.settings.tan_suat_ghi_ccp_phut);
  const bang = boot.bang_vao_hop;

  wrap.innerHTML = `
    <h1 class="sx-h1">Hôm nay ${esc(ngay.ngay)}
      <span class="sx-badge ${daChot ? 'sx-badge-ok' : 'sx-badge-run'}">${esc(ngay.trang_thai || '')}</span>
    </h1>
    <div class="sx-kpi-grid">
      <div class="sx-card sx-kpi">
        <div class="sx-kpi-label">Đậu vào</div>
        <div class="sx-kpi-value">${ngay.chay_tang_1 ? esc(formatKg(ngay.dau_vao_kg)) : 'Không rang'}</div>
        ${ngay.chay_tang_1 ? `<div class="sx-muted">Bột dự kiến ${esc(formatKg(ngay.btp_du_kien_kg))}</div>` : ''}
      </div>
      <div class="sx-card sx-kpi ${ccpQuaHan ? 'sx-kpi-warn' : ''}">
        <div class="sx-kpi-label">Ghi CCP</div>
        <div class="sx-kpi-value">${ccpCount} lần</div>
        ${ccpQuaHan ? '<div class="sx-warn-text">⚠ Quá hạn ghi — vào tab CCP ghi ngay</div>' : ''}
      </div>
      <div class="sx-card sx-kpi">
        <div class="sx-kpi-label">Mẻ trộn</div>
        <div class="sx-kpi-value">${boot.so_me_tron || 0} mẻ</div>
      </div>
      <div class="sx-card sx-kpi">
        <div class="sx-kpi-label">Vào hộp ${daChot ? '' : '(tạm)'}</div>
        <div class="sx-kpi-value">${formatNumber(daChot ? ngay.tong_hop : (bang ? bang.tong_hop : 0))} hộp</div>
        <div class="sx-muted">${esc(formatVND(daChot ? ngay.tong_luong_sp : (bang ? bang.tong_tien : 0)))}</div>
      </div>
    </div>
    <div class="sx-card">
      <div class="sx-field-label">Sự cố hôm nay (${(ngay.su_co || []).length})</div>
      <div id="sx-su-co-list">${(ngay.su_co || []).map((s) => `
        <div class="sx-row-item">
          <b>${esc(s.loai)}</b> ${esc(s.mo_ta || '')}
          ${s.phut_dung ? `<span class="sx-muted">· dừng ${esc(s.phut_dung)} phút</span>` : ''}
        </div>`).join('') || '<div class="sx-muted">Chưa có sự cố.</div>'}
      </div>
      ${!daChot && ctx.isToTruong ? '<button type="button" class="sx-btn sx-btn-warn" id="sx-btn-su-co">+ Ghi sự cố</button>' : ''}
    </div>
    ${!daChot && ctx.isToTruong ? '<button type="button" class="sx-btn sx-btn-danger sx-btn-big" id="sx-btn-chot">CHỐT NGÀY</button>' : ''}
    ${daChot ? '<div class="sx-card sx-card-center">✅ Ngày đã chốt. Kho + lương sản phẩm đã ghi nhận.</div>' : ''}
  `;

  const suCoBtn = wrap.querySelector('#sx-btn-su-co');
  if (suCoBtn) suCoBtn.addEventListener('click', () => openSuCo(ngay, call, refresh));

  const chotBtn = wrap.querySelector('#sx-btn-chot');
  if (chotBtn) {
    chotBtn.addEventListener('click', () => {
      confirm2Step({
        title: 'Chốt ngày sản xuất',
        message: 'Chốt ngày sẽ ghi kho (WO/SE), sinh lương sản phẩm và KHOÁ phiếu. '
          + 'Kiểm tra đủ: CCP, mẻ trộn, bảng vào hộp trước khi chốt.',
        confirmLabel: 'CHỐT NGÀY',
        onConfirm: async () => {
          try {
            const r = await call('sx.api.chot.chot_ngay', { ngay_sx: ngay.name });
            toast(`Đã chốt ngày — ${formatNumber(r.tong_hop)} hộp.`);
            await refresh();
            window.location.reload();
          } catch (e) {
            toastErr(e.message);
            throw e;
          }
        },
      });
    });
  }
}

function openSuCo(ngay, call, refresh) {
  const m = openModal({ title: 'Ghi sự cố' });
  const state = { loai: 'Hỏng máy', phut: 0 };
  m.body.innerHTML = `
    <div class="sx-field-label">Loại sự cố</div>
    <div class="sx-sp-grid" id="sx-loai-grid"></div>
    <div class="sx-field-label">Mô tả (không bắt buộc)</div>
    <textarea class="sx-textarea" id="sx-su-co-mo-ta" rows="2"></textarea>
    <div class="sx-field-label">Dừng chuyền (phút) — bấm để nhập</div>
    <button type="button" class="sx-value-btn" id="sx-su-co-phut">0 phút</button>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-su-co-luu">LƯU SỰ CỐ</button>
  `;
  const grid = m.body.querySelector('#sx-loai-grid');
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
  const phutBtn = m.body.querySelector('#sx-su-co-phut');
  phutBtn.addEventListener('click', () => {
    openNumpad({
      title: 'Dừng chuyền (phút)',
      initial: state.phut,
      unit: 'phút',
      onOk: (v) => { state.phut = Math.round(v); phutBtn.textContent = `${state.phut} phút`; },
    });
  });
  m.body.querySelector('#sx-su-co-luu').addEventListener('click', async (e) => {
    e.currentTarget.disabled = true;
    try {
      await call('sx.api.portal.ghi_su_co', {
        ngay_sx: ngay.name,
        loai: state.loai,
        mo_ta: m.body.querySelector('#sx-su-co-mo-ta').value,
        phut_dung: state.phut,
      });
      toast('Đã ghi sự cố.');
      m.close();
      await refresh();
      window.location.reload();
    } catch (err) {
      e.target.disabled = false;
      toastErr(err.message);
    }
  });
}
