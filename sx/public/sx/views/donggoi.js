// View Tổ đóng gói (#/donggoi) — (1) công suất máy cán, (2) bảng vào hộp
// (grid công nhân -> SKU + phương thức -> numpad), (3) sự cố, (4) CHỐT NGÀY 2 bước.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatNumber, formatVND } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, call, refresh }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);

  let ngay = boot.ngay_sx;
  const daChot = ngay && ngay.docstatus === 1;
  const rows = ((boot.bang_vao_hop || {}).dong || []).map((r) => ({ ...r }));
  const csMay = {};
  ((ngay && ngay.cong_suat_may) || []).forEach((r) => { csMay[r.may] = r.so_thung; });

  async function ensureNgay() {
    if (!ngay) {
      ngay = await call('sx.api.portal.get_or_create_ngay', {});
    }
    return ngay;
  }

  wrap.innerHTML = `
    <h1 class="sx-h1">Tổ đóng gói
      ${daChot ? '<span class="sx-badge sx-badge-ok">Đã chốt</span>' : ''}</h1>
    <div class="sx-card">
      <div class="sx-field-label">1 · Công suất máy cán (số thùng ủ đã chạy)</div>
      <div class="sx-sp-card-grid" id="sx-cs-grid"></div>
    </div>
    <div class="sx-card">
      <div class="sx-field-label">2 · Bảng vào hộp ${daChot ? '(chỉ xem)' : '(bấm tên công nhân để thêm)'}</div>
      ${daChot ? '' : '<div class="sx-nv-grid" id="sx-nv-grid"></div>'}
      <table class="sx-table">
        <thead><tr><th>Công nhân</th><th>SKU</th><th>PT</th><th>Hộp</th><th>Tiền</th>${daChot ? '' : '<th></th>'}</tr></thead>
        <tbody id="sx-vh-rows"></tbody>
      </table>
      <div class="sx-vh-footer" id="sx-vh-footer"></div>
    </div>
    ${daChot ? '' : `
    <button type="button" class="sx-btn sx-btn-warn" id="sx-btn-su-co">⚠ Ghi sự cố</button>
    <button type="button" class="sx-btn sx-btn-danger sx-btn-big" id="sx-btn-chot">CHỐT NGÀY</button>`}
    <div class="sx-card">
      <div class="sx-field-label">Sự cố hôm nay (${((ngay && ngay.su_co) || []).length})</div>
      ${(((ngay && ngay.su_co) || []).map((s) => `
        <div class="sx-row-item"><b>${esc(s.loai)}</b> ${esc(s.mo_ta || '')}
          ${s.phut_dung ? `<span class="sx-muted">· dừng ${esc(s.phut_dung)} phút</span>` : ''}</div>`).join('')
        || '<div class="sx-muted">Chưa có sự cố.</div>')}
    </div>
  `;

  // ── công suất máy
  const csGrid = wrap.querySelector('#sx-cs-grid');
  function paintCs() {
    csGrid.innerHTML = '';
    (boot.may || []).forEach((mAy) => {
      const st = csMay[mAy.name] || 0;
      const btn = el('button', `sx-sp-card${st > 0 ? ' sx-sp-card-on' : ''}`);
      btn.type = 'button';
      btn.innerHTML = `<div class="sx-sp-card-name">${esc(mAy.name)}</div>
        <div class="${st > 0 ? 'sx-sp-card-count' : 'sx-muted'}">${st > 0 ? `${st} thùng` : '—'}</div>`;
      if (!daChot) {
        btn.addEventListener('click', () => {
          openNumpad({
            title: `${mAy.name} — số thùng ủ đã chạy`,
            initial: csMay[mAy.name] || '',
            unit: 'thùng',
            onOk: async (v) => {
              csMay[mAy.name] = Math.round(v);
              paintCs();
              try {
                await ensureNgay();
                const rowsCs = Object.entries(csMay)
                  .filter(([, x]) => x > 0)
                  .map(([may, so_thung]) => ({ may, so_thung }));
                await call('sx.api.portal.cong_suat_may', {
                  ngay_sx: ngay.name, rows: JSON.stringify(rowsCs),
                });
                toast('Đã lưu công suất.');
              } catch (e) { toastErr(e.message); }
            },
          });
        });
      }
      csGrid.appendChild(btn);
    });
    if (!(boot.may || []).length) {
      csGrid.innerHTML = '<div class="sx-muted">Chưa khai máy (SX May) — quản lý thêm trên Desk.</div>';
    }
  }
  paintCs();

  // ── bảng vào hộp
  const tbody = wrap.querySelector('#sx-vh-rows');
  const footer = wrap.querySelector('#sx-vh-footer');

  function paintRows() {
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
          await saveRows();
        });
      });
    }
  }

  async function saveRows() {
    try {
      await ensureNgay();
      const r = await call('sx.api.portal.luu_bang_vao_hop', {
        ngay_sx: ngay.name,
        rows: JSON.stringify(rows.map((x) => ({
          nhan_vien: x.nhan_vien, san_pham: x.san_pham,
          phuong_thuc: x.phuong_thuc, so_hop: x.so_hop,
        }))),
      });
      rows.length = 0;
      (r && r.dong ? r.dong : []).forEach((x) => rows.push(x));
      paintRows();
      toast('Đã lưu.');
    } catch (e) {
      toastErr(e.message);
      paintRows();
    }
  }

  if (!daChot) {
    const nvGrid = wrap.querySelector('#sx-nv-grid');
    (boot.nhan_vien || []).forEach((nv) => {
      const btn = el('button', 'sx-nv-card');
      btn.type = 'button';
      btn.textContent = nv.employee_name || nv.name;
      btn.addEventListener('click', () => themDong(nv));
      nvGrid.appendChild(btn);
    });
    if (!(boot.nhan_vien || []).length) {
      nvGrid.innerHTML = '<div class="sx-muted">Chưa có nhân viên Active.</div>';
    }
  }

  function themDong(nv) {
    const m = openModal({ title: nv.employee_name || nv.name });
    const state = { san_pham: null, phuong_thuc: null };
    m.body.innerHTML = `
      <div class="sx-field-label">SKU</div>
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
          paintRows();
          await saveRows();
        },
      });
    });
  }

  paintRows();

  // ── sự cố + chốt ngày
  const suCoBtn = wrap.querySelector('#sx-btn-su-co');
  if (suCoBtn) suCoBtn.addEventListener('click', async () => { await ensureNgay(); openSuCo(ngay, call, refresh); });

  const chotBtn = wrap.querySelector('#sx-btn-chot');
  if (chotBtn) {
    chotBtn.addEventListener('click', async () => {
      await ensureNgay();
      confirm2Step({
        title: 'Chốt ngày sản xuất',
        message: 'Chốt ngày sẽ sinh chứng từ kho (hỗn hợp + thành phẩm), tính lương '
          + 'sản phẩm và KHOÁ phiếu. Kiểm tra: báo mẻ, công suất máy, bảng vào hộp.',
        confirmLabel: 'CHỐT NGÀY',
        onConfirm: async () => {
          try {
            const r = await call('sx.api.chot.chot_ngay', { ngay_sx: ngay.name });
            toast(`Đã chốt ngày — ${formatNumber(r.tong_hop_tp)} hộp.`);
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

function tenSP(boot, code) {
  const it = (boot.items_tp || []).find((x) => x.name === code);
  return it ? (it.item_name || it.name) : code;
}
