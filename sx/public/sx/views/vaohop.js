// V4 Vào hộp (#/vaohop) — grid công nhân -> SP + phương thức -> numpad số hộp
// -> thêm dòng (auto-save draft server-side); bảng dòng sửa/xoá; footer tổng.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatNumber, formatVND } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, refresh, call }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);

  if (!boot.ngay_sx) {
    wrap.innerHTML = '<div class="sx-card sx-card-center">Chưa mở ngày sản xuất.</div>';
    return;
  }
  const daChot = boot.ngay_sx.docstatus === 1;
  const rows = ((boot.bang_vao_hop || {}).dong || []).map((r) => ({ ...r }));

  wrap.innerHTML = `
    <h1 class="sx-h1">Bảng vào hộp</h1>
    ${daChot ? '<div class="sx-card sx-card-center">Ngày đã chốt — bảng chỉ xem.</div>' : `
    <div class="sx-field-label">Bấm tên công nhân để thêm dòng</div>
    <div class="sx-nv-grid" id="sx-nv-grid"></div>`}
    <div class="sx-card">
      <table class="sx-table">
        <thead><tr><th>Công nhân</th><th>Sản phẩm</th><th>PT</th><th>Hộp</th><th>Tiền</th>${daChot ? '' : '<th></th>'}</tr></thead>
        <tbody id="sx-vh-rows"></tbody>
      </table>
      <div class="sx-vh-footer" id="sx-vh-footer"></div>
    </div>
  `;

  const tbody = wrap.querySelector('#sx-vh-rows');
  const footer = wrap.querySelector('#sx-vh-footer');

  function paint() {
    tbody.innerHTML = rows.map((r, i) => `
      <tr>
        <td>${esc(r.ten_nhan_vien || r.nhan_vien)}</td>
        <td>${esc(tenSP(boot, r.san_pham))}</td>
        <td>${esc(r.phuong_thuc === 'Máy hỗ trợ' ? 'Máy' : 'Tay')}</td>
        <td><b>${esc(formatNumber(r.so_hop))}</b></td>
        <td>${esc(r.thanh_tien != null ? formatVND(r.thanh_tien) : '…')}</td>
        ${daChot ? '' : `<td><button type="button" class="sx-cell-btn sx-cell-del" data-i="${i}">✕</button></td>`}
      </tr>`).join('') || `<tr><td colspan="6" class="sx-muted">Chưa có dòng nào.</td></tr>`;
    const tongHop = rows.reduce((a, r) => a + (Number(r.so_hop) || 0), 0);
    const tongTien = rows.reduce((a, r) => a + (Number(r.thanh_tien) || 0), 0);
    footer.innerHTML = `Tổng: <b>${formatNumber(tongHop)}</b> hộp · <b>${esc(formatVND(tongTien))}</b>`;
    if (!daChot) {
      tbody.querySelectorAll('.sx-cell-del').forEach((btn) => {
        btn.addEventListener('click', async () => {
          rows.splice(Number(btn.dataset.i), 1);
          await save();
        });
      });
    }
  }

  async function save() {
    try {
      const r = await call('sx.api.portal.luu_bang_vao_hop', {
        payload: JSON.stringify({
          ngay_sx: boot.ngay_sx.name,
          dong: rows.map((x) => ({
            nhan_vien: x.nhan_vien, san_pham: x.san_pham,
            phuong_thuc: x.phuong_thuc, so_hop: x.so_hop,
          })),
        }),
      });
      rows.length = 0;
      (r && r.dong ? r.dong : []).forEach((x) => rows.push(x));
      paint();
      toast('Đã lưu.');
    } catch (e) {
      toastErr(e.message);
      paint();
    }
  }

  if (!daChot) {
    const grid = wrap.querySelector('#sx-nv-grid');
    (boot.nhan_vien || []).forEach((nv) => {
      const btn = el('button', 'sx-nv-card');
      btn.type = 'button';
      btn.textContent = nv.employee_name || nv.name;
      btn.addEventListener('click', () => themDong(nv));
      grid.appendChild(btn);
    });
    if (!(boot.nhan_vien || []).length) {
      grid.innerHTML = '<div class="sx-muted">Chưa có nhân viên Active.</div>';
    }
  }

  function themDong(nv) {
    const m = openModal({ title: nv.employee_name || nv.name });
    const state = { san_pham: null, phuong_thuc: null };
    m.body.innerHTML = `
      <div class="sx-field-label">Sản phẩm</div>
      <div class="sx-sp-grid" id="sx-vh-sp"></div>
      <div class="sx-field-label">Phương thức</div>
      <div class="sx-pt-grid">
        <button type="button" class="sx-btn sx-btn-ghost sx-btn-big" data-pt="Thủ công">✋ Thủ công</button>
        <button type="button" class="sx-btn sx-btn-ghost sx-btn-big" data-pt="Máy hỗ trợ">⚙️ Máy hỗ trợ</button>
      </div>
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-vh-next" disabled>NHẬP SỐ HỘP →</button>
    `;
    const spGrid = m.body.querySelector('#sx-vh-sp');
    const nextBtn = m.body.querySelector('#sx-vh-next');
    const checkReady = () => { nextBtn.disabled = !(state.san_pham && state.phuong_thuc); };
    (boot.items_tp || []).forEach((it) => {
      const b = el('button', 'sx-sp-chip');
      b.type = 'button';
      b.textContent = it.item_name || it.name;
      b.addEventListener('click', () => {
        state.san_pham = it.name;
        spGrid.querySelectorAll('.sx-sp-chip').forEach((x) => x.classList.remove('sx-sp-chip-on'));
        b.classList.add('sx-sp-chip-on');
        checkReady();
      });
      spGrid.appendChild(b);
    });
    m.body.querySelectorAll('[data-pt]').forEach((b) => {
      b.addEventListener('click', () => {
        state.phuong_thuc = b.dataset.pt;
        m.body.querySelectorAll('[data-pt]').forEach((x) => x.classList.remove('sx-btn-primary'));
        b.classList.add('sx-btn-primary');
        checkReady();
      });
    });
    nextBtn.addEventListener('click', () => {
      m.close();
      openNumpad({
        title: `${nv.employee_name || nv.name} — số hộp`,
        unit: 'hộp',
        onOk: async (v) => {
          const soHop = Math.round(v);
          if (soHop <= 0) { toastErr('Số hộp phải > 0.'); return; }
          rows.push({
            nhan_vien: nv.name,
            ten_nhan_vien: nv.employee_name,
            san_pham: state.san_pham,
            phuong_thuc: state.phuong_thuc,
            so_hop: soHop,
          });
          paint();
          await save();
        },
      });
    });
  }

  paint();
}

function tenSP(boot, code) {
  const it = (boot.items_tp || []).find((x) => x.name === code);
  return it ? (it.item_name || it.name) : code;
}
