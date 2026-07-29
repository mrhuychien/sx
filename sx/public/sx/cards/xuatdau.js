// Card Xuất đậu — 2 nút loại đỗ + numpad kg → mã lô R CỰC TO để ghi thẻ (D13).

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatKg, formatNumber, nhanNgay } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, call, refresh }) {
  container.className = 'sx-card';
  container.innerHTML = `
    <div class="sx-field-label">Xuất đậu ${nhanNgay(boot)} (rang ngày kế tiếp)</div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-xd-open">🫘 XUẤT ĐẬU</button>
    <div id="sx-xd-ds" class="sx-muted">Đang tải phiếu đã ghi…</div>
  `;
  container.querySelector('#sx-xd-open').addEventListener('click', () => openXuatDau(boot, call, refresh));
  await veDanhSach(container.querySelector('#sx-xd-ds'), boot, call, refresh);
}

// Danh sách phiếu xuất đậu đã ghi trong ngày — để QC đối chiếu và sửa khi nhập nhầm (D25)
async function veDanhSach(box, boot, call, refresh) {
  let ds = [];
  try {
    ds = await call('sx.api.tang1.ds_xuat_dau', boot.ngay_xem ? { ngay: boot.ngay_xem } : {});
  } catch (e) {
    box.textContent = e.message || 'Không đọc được danh sách xuất đậu.';
    return;
  }
  if (!ds.length) { box.textContent = 'Chưa xuất đậu.'; return; }
  box.className = '';
  box.innerHTML = `
    <table class="sx-table">
      <thead><tr><th>Lô rang</th><th>Loại đỗ</th><th>Kg</th><th></th></tr></thead>
      <tbody>${ds.map((r) => `
        <tr>
          <td><b>${esc(r.lo_rang)}</b></td>
          <td>${esc(r.loai_dau)}</td>
          <td>${esc(formatKg(r.dau_kg))}</td>
          <td>${r.sua_duoc
            ? `<button type="button" class="sx-cell-btn sx-xd-huy" data-n="${esc(r.name)}" data-lo="${esc(r.lo_rang)}">✕</button>`
            : '<span class="sx-muted">đã nhập bột</span>'}</td>
        </tr>`).join('')}</tbody>
    </table>`;
  box.querySelectorAll('.sx-xd-huy').forEach((b) => {
    b.addEventListener('click', () => {
      confirm2Step({
        title: `Huỷ phiếu xuất đậu ${b.dataset.lo}`,
        message: 'Huỷ phiếu ghi nhầm. Lô rang này sẽ không còn chờ nhập bột nữa. '
          + 'Đậu chưa bị trừ kho nên không ảnh hưởng tồn.',
        confirmLabel: 'HUỶ PHIẾU',
        onConfirm: async () => {
          try {
            await call('sx.api.tang1.huy_xuat_dau', { name: b.dataset.n });
            toast('Đã huỷ phiếu xuất đậu.');
            refresh();
          } catch (e) { toastErr(e.message); throw e; }
        },
      });
    });
  });
}

function openXuatDau(boot, call, refresh) {
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
      const r = await call('sx.api.tang1.xuat_dau', {
        loai_dau: state.loai_dau, dau_kg: state.kg,
        ...(boot.la_hom_nay ? {} : { ngay_xuat: boot.ngay_xem }),
      });
      m.close();
      showLoRang(r, refresh);
    } catch (err) {
      e.target.disabled = false;
      toastErr(err.message);
    }
  });
}

function showLoRang(r, refresh) {
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
    refresh();
  });
}
