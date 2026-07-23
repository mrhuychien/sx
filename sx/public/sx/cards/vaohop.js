// Card Vào hộp — grid CN → SKU picker (search + nhóm + gần đây) → phương thức
// → numpad hộp → auto-save (đơn giá tính server-side); bảng dòng + footer tổng.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatNumber, formatVND } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, call, ensureNgay }) {
  container.className = 'sx-card';
  const ngay = boot.ngay_sx;
  const daChot = ngay && ngay.docstatus === 1;
  const rows = ((boot.bang_vao_hop || {}).dong || []).map((r) => ({ ...r }));
  const itemsTp = boot.items_tp || [];
  const skuGanDay = boot.sku_gan_day || [];

  container.innerHTML = `
    <div class="sx-field-label">Bảng vào hộp ${daChot ? '(đã chốt — chỉ xem)' : '(bấm tên công nhân)'}</div>
    ${daChot ? '' : '<div class="sx-nv-grid" id="sx-vh-nv"></div>'}
    <table class="sx-table">
      <thead><tr><th>Công nhân</th><th>SKU</th><th>PT</th><th>Hộp</th><th>Tiền</th>${daChot ? '' : '<th></th>'}</tr></thead>
      <tbody id="sx-vh-rows"></tbody>
    </table>
    <div class="sx-vh-footer" id="sx-vh-footer"></div>
  `;
  const tbody = container.querySelector('#sx-vh-rows');
  const footer = container.querySelector('#sx-vh-footer');

  const tenSP = (code) => {
    const it = itemsTp.find((x) => x.name === code);
    return it ? (it.item_name || it.name) : code;
  };

  function paint() {
    tbody.innerHTML = rows.map((r, i) => `
      <tr>
        <td>${esc(r.ten_nhan_vien || r.nhan_vien)}</td>
        <td>${esc(tenSP(r.san_pham))}</td>
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
        btn.addEventListener('click', async () => { rows.splice(Number(btn.dataset.i), 1); await save(); });
      });
    }
  }

  async function save() {
    try {
      const ng = await ensureNgay();
      const r = await call('sx.api.portal.luu_bang_vao_hop', {
        ngay_sx: ng.name,
        rows: JSON.stringify(rows.map((x) => ({
          nhan_vien: x.nhan_vien, san_pham: x.san_pham,
          phuong_thuc: x.phuong_thuc, so_hop: x.so_hop,
        }))),
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
    const nvGrid = container.querySelector('#sx-vh-nv');
    (boot.nhan_vien || []).forEach((nv) => {
      const btn = el('button', 'sx-nv-card');
      btn.type = 'button';
      btn.textContent = nv.employee_name || nv.name;
      btn.addEventListener('click', () => themDong(nv, itemsTp, skuGanDay, rows, save));
      nvGrid.appendChild(btn);
    });
    if (!(boot.nhan_vien || []).length) {
      nvGrid.innerHTML = '<div class="sx-muted">Chưa có nhân viên Active.</div>';
    }
  }

  paint();
}

function themDong(nv, itemsTp, skuGanDay, rows, save) {
  openSkuPicker(nv, itemsTp, skuGanDay, (sanPham) => {
    chonPhuongThuc(nv, sanPham, (phuongThuc) => {
      openNumpad({
        title: `${nv.employee_name || nv.name} — số hộp`, unit: 'hộp',
        onOk: async (v) => {
          const soHop = Math.round(v);
          if (soHop <= 0) { toastErr('Số hộp phải > 0.'); return; }
          rows.push({
            nhan_vien: nv.name, ten_nhan_vien: nv.employee_name,
            san_pham: sanPham, phuong_thuc: phuongThuc, so_hop: soHop,
          });
          await save();
        },
      });
    });
  });
}

function openSkuPicker(nv, itemsTp, skuGanDay, onPick) {
  const m = openModal({ title: `${nv.employee_name || nv.name} — chọn SKU` });
  m.body.innerHTML = `
    <input class="sx-textarea" id="sx-sku-search" placeholder="Tìm SKU…" autocomplete="off">
    <div id="sx-sku-list"></div>
  `;
  const list = m.body.querySelector('#sx-sku-list');
  const search = m.body.querySelector('#sx-sku-search');
  const ten = (code) => { const it = itemsTp.find((x) => x.name === code); return it ? (it.item_name || it.name) : code; };

  function draw(q) {
    q = (q || '').toLowerCase().trim();
    const match = (it) => !q
      || (it.item_name || '').toLowerCase().includes(q)
      || (it.name || '').toLowerCase().includes(q);
    let html = '';
    if (!q && skuGanDay.length) {
      html += '<div class="sx-field-label">Dùng gần đây</div><div class="sx-sp-grid">';
      html += skuGanDay.map((c) => `<button type="button" class="sx-sp-chip sx-sku-pick" data-sku="${esc(c)}">${esc(ten(c))}</button>`).join('');
      html += '</div>';
    }
    // nhóm theo item_group
    const groups = {};
    itemsTp.filter(match).forEach((it) => {
      const g = it.item_group || 'Khác';
      (groups[g] = groups[g] || []).push(it);
    });
    Object.keys(groups).sort().forEach((g) => {
      html += `<div class="sx-field-label">${esc(g)}</div><div class="sx-sp-grid">`;
      html += groups[g].map((it) => `<button type="button" class="sx-sp-chip sx-sku-pick" data-sku="${esc(it.name)}">${esc(it.item_name || it.name)}</button>`).join('');
      html += '</div>';
    });
    if (!itemsTp.filter(match).length && !(!q && skuGanDay.length)) {
      html = '<div class="sx-muted">Không tìm thấy SKU.</div>';
    }
    list.innerHTML = html;
    list.querySelectorAll('.sx-sku-pick').forEach((b) => {
      b.addEventListener('click', () => { m.close(); onPick(b.dataset.sku); });
    });
  }
  search.addEventListener('input', () => draw(search.value));
  draw('');
}

function chonPhuongThuc(nv, sanPham, onPick) {
  const m = openModal({ title: 'Phương thức' });
  m.body.innerHTML = `
    <div class="sx-pt-grid">
      <button type="button" class="sx-btn sx-btn-ghost sx-btn-big" data-pt="Thủ công">✋ Thủ công</button>
      <button type="button" class="sx-btn sx-btn-ghost sx-btn-big" data-pt="Máy hỗ trợ">⚙️ Máy hỗ trợ</button>
    </div>
  `;
  m.body.querySelectorAll('[data-pt]').forEach((b) => {
    b.addEventListener('click', () => { m.close(); onPick(b.dataset.pt); });
  });
}
