// V3 Trộn (#/tron) — thẻ SP -> chips cỡ mẻ -> bảng Định mức/Thực cân
// (prefill bằng nhau) -> nút ĐÚNG CÔNG THỨC submit luôn; tap ô thực cân -> numpad.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, refresh, call }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);

  if (!boot.ngay_sx) {
    wrap.innerHTML = '<div class="sx-card sx-card-center">Chưa mở ngày sản xuất.</div>';
    return;
  }
  if (boot.ngay_sx.docstatus === 1) {
    wrap.innerHTML = '<div class="sx-card sx-card-center">Ngày đã chốt — không thêm mẻ trộn.</div>';
    return;
  }

  chonSanPham(wrap, boot, call, refresh);
}

function chonSanPham(wrap, boot, call, refresh) {
  wrap.innerHTML = `
    <h1 class="sx-h1">Mẻ trộn <span class="sx-badge sx-badge-run">${boot.so_me_tron || 0} mẻ hôm nay</span></h1>
    <div class="sx-field-label">Chọn sản phẩm</div>
    <div class="sx-sp-card-grid" id="sx-tron-sp"></div>
  `;
  const grid = wrap.querySelector('#sx-tron-sp');
  (boot.items_tp || []).forEach((it) => {
    const btn = el('button', 'sx-sp-card');
    btn.type = 'button';
    btn.innerHTML = `<div class="sx-sp-card-name">${esc(it.item_name || it.name)}</div>
      <div class="sx-muted">Mẻ chuẩn ${esc(formatNumber(it.co_me_chuan_kg, 1))} kg</div>`;
    btn.addEventListener('click', () => chonCoMe(wrap, boot, it, call, refresh));
    grid.appendChild(btn);
  });
  if (!(boot.items_tp || []).length) {
    grid.innerHTML = '<div class="sx-muted">Chưa có Item nhóm TP.</div>';
  }
}

function chonCoMe(wrap, boot, item, call, refresh) {
  const chuan = item.co_me_chuan_kg || 0;
  wrap.innerHTML = `
    <h1 class="sx-h1">${esc(item.item_name || item.name)}</h1>
    <div class="sx-field-label">Cỡ mẻ (kg hỗn hợp)</div>
    <div class="sx-sp-grid" id="sx-come-chips"></div>
  `;
  const chips = wrap.querySelector('#sx-come-chips');
  const options = [
    { label: `Chuẩn ${formatNumber(chuan, 1)} kg`, value: chuan },
    { label: `×0,5 → ${formatNumber(chuan * 0.5, 1)} kg`, value: chuan * 0.5 },
    { label: `×2 → ${formatNumber(chuan * 2, 1)} kg`, value: chuan * 2 },
  ];
  options.forEach((o) => {
    const b = el('button', 'sx-sp-chip');
    b.type = 'button';
    b.textContent = o.label;
    if (!o.value) b.disabled = true;
    b.addEventListener('click', () => loadPrefill(wrap, boot, item, o.value, call, refresh));
    chips.appendChild(b);
  });
  const tuNhap = el('button', 'sx-sp-chip');
  tuNhap.type = 'button';
  tuNhap.textContent = 'Nhập tay…';
  tuNhap.addEventListener('click', () => {
    openNumpad({
      title: 'Cỡ mẻ (kg)', initial: chuan, allowDecimal: true, unit: 'kg',
      onOk: (v) => { if (v > 0) loadPrefill(wrap, boot, item, v, call, refresh); },
    });
  });
  chips.appendChild(tuNhap);
}

async function loadPrefill(wrap, boot, item, coMe, call, refresh) {
  wrap.innerHTML = '<div class="sx-boot-loading">Đang lấy công thức…</div>';
  let data;
  try {
    data = await call('sx.api.portal.prefill_me_tron', { san_pham: item.name, co_me_kg: coMe });
  } catch (e) {
    toastErr(e.message);
    chonSanPham(wrap, boot, call, refresh);
    return;
  }
  const rows = data.rows.map((r) => ({ ...r, thuc_can_kg: r.dinh_muc_kg }));

  wrap.innerHTML = `
    <h1 class="sx-h1">${esc(item.item_name || item.name)} — mẻ ${esc(formatNumber(data.co_me_kg, 1))} kg</h1>
    <div class="sx-card">
      <table class="sx-table">
        <thead><tr><th>Nguyên liệu</th><th>Định mức</th><th>Thực cân (bấm để sửa)</th></tr></thead>
        <tbody id="sx-tron-rows"></tbody>
      </table>
    </div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-tron-ok">✓ ĐÚNG CÔNG THỨC — LƯU MẺ</button>
    <button type="button" class="sx-btn sx-btn-ghost" id="sx-tron-back">← Chọn lại</button>
  `;

  const tbody = wrap.querySelector('#sx-tron-rows');
  function paint() {
    tbody.innerHTML = rows.map((r, i) => {
      const lech = r.thuc_can_kg - r.dinh_muc_kg;
      return `<tr>
        <td>${esc(r.item_name || r.item)}</td>
        <td>${esc(formatNumber(r.dinh_muc_kg, 3))} kg</td>
        <td><button type="button" class="sx-cell-btn ${Math.abs(lech) > 1e-9 ? 'sx-cell-lech' : ''}" data-i="${i}">
          ${esc(formatNumber(r.thuc_can_kg, 3))} kg${Math.abs(lech) > 1e-9 ? ` (${lech > 0 ? '+' : ''}${esc(formatNumber(lech, 3))})` : ''}
        </button></td>
      </tr>`;
    }).join('');
    tbody.querySelectorAll('.sx-cell-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const i = Number(btn.dataset.i);
        openNumpad({
          title: `${rows[i].item_name || rows[i].item} — thực cân (kg)`,
          initial: rows[i].thuc_can_kg,
          allowDecimal: true,
          unit: 'kg',
          onOk: (v) => { rows[i].thuc_can_kg = v; paint(); },
        });
      });
    });
  }
  paint();

  wrap.querySelector('#sx-tron-back').addEventListener('click', () => chonSanPham(wrap, boot, call, refresh));
  wrap.querySelector('#sx-tron-ok').addEventListener('click', async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    btn.textContent = 'Đang lưu…';
    try {
      const r = await call('sx.api.portal.luu_me_tron', {
        payload: JSON.stringify({
          ngay_sx: boot.ngay_sx.name,
          san_pham: item.name,
          bom: data.bom,
          co_me_kg: data.co_me_kg,
          nguyen_lieu: rows.map((x) => ({
            item: x.item, dinh_muc_kg: x.dinh_muc_kg, thuc_can_kg: x.thuc_can_kg,
          })),
        }),
      });
      toast(r.dung_cong_thuc
        ? `Đã lưu mẻ ${r.me_so} — đúng công thức.`
        : `Đã lưu mẻ ${r.me_so} — lệch ${formatNumber(r.tong_lech_pct, 2)}%.`);
      await refresh();
      window.location.reload();
    } catch (err) {
      btn.disabled = false;
      btn.textContent = '✓ ĐÚNG CÔNG THỨC — LƯU MẺ';
      toastErr(err.message);
    }
  });
}
