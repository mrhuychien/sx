// Card Vào hộp — grid CN → picker LOẠI CÔNG VIỆC (search + gần đây, kèm đơn giá)
// → numpad số lượng → auto-save. Loại nào có ≥2 SKU thì hỏi thêm 1 bước chọn SKU
// (cần cho lệnh SX tầng 3); 1 SKU tự gán; 0 SKU chỉ tính lương khoán (D23).
// Đơn giá luôn do server tính lại từ Activity Type.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatNumber, formatVND, nhanNgay } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

export async function render({ container, boot, call, ensureNgay }) {
  container.className = 'sx-card';
  const ngay = boot.ngay_sx;
  const daChot = ngay && ngay.docstatus === 1;
  const rows = ((boot.bang_vao_hop || {}).dong || []).map((r) => ({ ...r }));
  const itemsTp = boot.items_tp || [];
  const activities = boot.activity_types || [];
  const actGanDay = boot.activity_gan_day || [];
  const nhanVien = boot.nhan_vien || [];
  // Tên ngắn (chỉ tên gọi; trùng thì server đã thêm họ / viết tắt đệm)
  const tenNgan = {};
  nhanVien.forEach((nv) => { tenNgan[nv.name] = nv.ten_hien_thi || nv.employee_name || nv.name; });

  container.innerHTML = `
    <div class="sx-field-label">Bảng vào hộp ${nhanNgay(boot)} ${daChot ? '(đã chốt — chỉ xem)' : '(bấm tên công nhân)'}</div>
    ${boot.canh_bao_nhan_vien ? `<div class="sx-warn-text">⚠ ${esc(boot.canh_bao_nhan_vien)}</div>` : ''}
    ${daChot ? '<div class="sx-muted">Muốn sửa: bấm HUỶ CHỐT NGÀY ở thẻ Chốt ngày, sửa xong chốt lại.</div>' : ''}
    ${daChot ? '' : '<div class="sx-nv-grid" id="sx-vh-nv"></div>'}
    <table class="sx-table">
      <thead><tr><th>Công nhân</th><th>Loại công việc</th><th>SL</th><th>Tiền</th>${daChot ? '' : '<th></th>'}</tr></thead>
      <tbody id="sx-vh-rows"></tbody>
    </table>
    <div class="sx-vh-footer" id="sx-vh-footer"></div>
    <div class="sx-vh-actions">
      <button type="button" class="sx-btn" id="sx-vh-copy">📋 Copy sản lượng gửi nhóm</button>
    </div>
  `;
  const tbody = container.querySelector('#sx-vh-rows');
  const footer = container.querySelector('#sx-vh-footer');

  const tenSP = (code) => {
    const it = itemsTp.find((x) => x.name === code);
    return it ? (it.item_name || it.name) : code;
  };
  const tenNV = (r) => tenNgan[r.nhan_vien] || r.ten_nhan_vien || r.nhan_vien;

  // Gộp các dòng CÙNG công nhân lại (server đã sắp, client sắp lại cho chắc)
  function theoNguoi() {
    const nhom = new Map();
    rows.forEach((r, i) => {
      if (!nhom.has(r.nhan_vien)) nhom.set(r.nhan_vien, { ten: tenNV(r), dong: [] });
      nhom.get(r.nhan_vien).dong.push({ ...r, _i: i });
    });
    return [...nhom.values()].sort((a, b) => a.ten.localeCompare(b.ten, 'vi'));
  }

  function paint() {
    const nhom = theoNguoi();
    let html = '';
    nhom.forEach((g) => {
      g.dong.forEach((r, k) => {
        html += `<tr>
          <td>${k === 0 ? `<b>${esc(g.ten)}</b>` : ''}</td>
          <td>${esc(r.activity_type || '—')}${r.san_pham ? `<div class="sx-muted">${esc(tenSP(r.san_pham))}</div>` : ''}</td>
          <td><button type="button" class="sx-vh-sl" data-i="${r._i}"${daChot ? ' disabled' : ''}>${esc(formatNumber(r.so_hop))}</button></td>
          <td>${esc(r.thanh_tien != null ? formatVND(r.thanh_tien) : '…')}</td>
          ${daChot ? '' : `<td><button type="button" class="sx-cell-btn sx-cell-del" data-i="${r._i}">✕</button></td>`}
        </tr>`;
      });
      if (g.dong.length > 1) {
        const tien = g.dong.reduce((a, r) => a + (Number(r.thanh_tien) || 0), 0);
        html += `<tr class="sx-vh-nguoi"><td></td><td>Cộng ${esc(g.ten)}</td>
          <td>${esc(formatNumber(g.dong.reduce((a, r) => a + (Number(r.so_hop) || 0), 0)))}</td>
          <td>${esc(formatVND(tien))}</td>${daChot ? '' : '<td></td>'}</tr>`;
      }
    });
    tbody.innerHTML = html || `<tr><td colspan="5" class="sx-muted">Chưa có dòng nào.</td></tr>`;
    const tongHop = rows.reduce((a, r) => a + (Number(r.so_hop) || 0), 0);
    const tongTien = rows.reduce((a, r) => a + (Number(r.thanh_tien) || 0), 0);
    footer.innerHTML = `Tổng: <b>${formatNumber(tongHop)}</b> sản phẩm · <b>${esc(formatVND(tongTien))}</b>`;
    if (!daChot) {
      tbody.querySelectorAll('.sx-cell-del').forEach((btn) => {
        btn.addEventListener('click', async () => { rows.splice(Number(btn.dataset.i), 1); await save(); });
      });
      tbody.querySelectorAll('.sx-vh-sl').forEach((btn) => {
        btn.addEventListener('click', () => suaSoLuong(Number(btn.dataset.i)));
      });
    }
  }

  // Sửa số lượng tại chỗ — chỉ khi chưa chốt (chốt rồi phải huỷ chốt mới sửa được)
  function suaSoLuong(i) {
    const r = rows[i];
    if (!r) return;
    openNumpad({
      title: `${tenNV(r)} — ${r.activity_type || ''}`,
      unit: 'sp',
      initial: r.so_hop,
      onOk: async (v) => {
        const sl = Math.round(v);
        if (sl <= 0) { toastErr('Số lượng phải > 0. Muốn xoá thì bấm ✕.'); return; }
        rows[i].so_hop = sl;
        await save();
      },
    });
  }

  container.querySelector('#sx-vh-copy').addEventListener('click', () => {
    copySanLuong(theoNguoi(), (boot.ngay_sx && boot.ngay_sx.ngay) || boot.ngay_xem);
  });

  async function save() {
    try {
      const ng = await ensureNgay();
      const r = await call('sx.api.portal.luu_bang_vao_hop', {
        ngay_sx: ng.name,
        rows: JSON.stringify(rows.map((x) => ({
          nhan_vien: x.nhan_vien, activity_type: x.activity_type,
          san_pham: x.san_pham, so_hop: x.so_hop,
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
    nhanVien.forEach((nv) => {
      const btn = el('button', 'sx-nv-card');
      btn.type = 'button';
      btn.textContent = tenNgan[nv.name];
      btn.title = nv.employee_name || nv.name;   // tên đầy đủ khi cần đối chiếu
      btn.addEventListener('click', () => themDong(nv, activities, actGanDay, rows, save, tenNgan));
      nvGrid.appendChild(btn);
    });
    if (!nhanVien.length) {
      nvGrid.innerHTML = '<div class="sx-muted">Chưa có công nhân công khoán nào (kiểm tra nhóm trong SX Settings).</div>';
    }
    if (!activities.length) {
      nvGrid.insertAdjacentHTML('beforebegin',
        '<div class="sx-warn-text">⚠ Chưa có Activity Type nào dùng được — vào Desk tạo loại công việc khoán (vd "Vào hộp 300") và điền đơn giá.</div>');
    }
  }

  paint();
}

function themDong(nv, activities, actGanDay, rows, save, tenNgan) {
  const ten = (tenNgan && tenNgan[nv.name]) || nv.employee_name || nv.name;
  openActivityPicker(ten, activities, actGanDay, (act) => {
    // Loại có nhiều SKU -> hỏi thêm SKU nào (cần cho lệnh SX tầng 3).
    // 1 SKU tự gán, 0 SKU thì để trống -> chỉ tính lương khoán.
    const tiep = (sanPham) => nhapSoLuong(nv, ten, act, sanPham, rows, save);
    if (act.sku && act.sku.length > 1) openSkuPicker(ten, act, tiep);
    else tiep(act.sku && act.sku.length === 1 ? act.sku[0].name : null);
  });
}

function nhapSoLuong(nv, ten, act, sanPham, rows, save) {
  openNumpad({
    title: `${ten} — ${act.name}`, unit: 'sp',
    onOk: async (v) => {
      const sl = Math.round(v);
      if (sl <= 0) { toastErr('Số lượng phải > 0.'); return; }
      rows.push({
        nhan_vien: nv.name, ten_nhan_vien: nv.employee_name,
        activity_type: act.name, san_pham: sanPham, so_hop: sl,
      });
      await save();
    },
  });
}

function openActivityPicker(ten, activities, actGanDay, onPick) {
  const m = openModal({ title: `${ten} — chọn loại công việc` });
  m.body.innerHTML = `
    <input class="sx-textarea" id="sx-act-search" placeholder="Tìm loại công việc…" autocomplete="off">
    <div id="sx-act-list"></div>
  `;
  const list = m.body.querySelector('#sx-act-list');
  const search = m.body.querySelector('#sx-act-search');
  const byName = {};
  activities.forEach((a) => { byName[a.name] = a; });

  const chip = (a) => `<button type="button" class="sx-sp-chip sx-act-pick" data-act="${esc(a.name)}">`
    + `${esc(a.name)}<div class="sx-muted">${esc(formatVND(a.don_gia))}${a.sku && a.sku.length ? ` · ${a.sku.length} SKU` : ''}</div>`
    + '</button>';

  function draw(q) {
    q = (q || '').toLowerCase().trim();
    const khop = activities.filter((a) => !q || a.name.toLowerCase().includes(q));
    let html = '';
    const ganDay = actGanDay.map((n) => byName[n]).filter(Boolean);
    if (!q && ganDay.length) {
      html += '<div class="sx-field-label">Dùng gần đây</div><div class="sx-sp-grid">'
        + ganDay.map(chip).join('') + '</div>';
    }
    if (khop.length) {
      html += `<div class="sx-field-label">${q ? 'Kết quả' : 'Tất cả loại công việc'}</div>`
        + '<div class="sx-sp-grid">' + khop.map(chip).join('') + '</div>';
    } else if (!ganDay.length || q) {
      html += '<div class="sx-muted">Không tìm thấy loại công việc nào.</div>';
    }
    list.innerHTML = html;
    list.querySelectorAll('.sx-act-pick').forEach((b) => {
      b.addEventListener('click', () => { m.close(); onPick(byName[b.dataset.act]); });
    });
  }
  search.addEventListener('input', () => draw(search.value));
  draw('');
}

function openSkuPicker(ten, act, onPick) {
  const m = openModal({ title: `${ten} — ${act.name}: sản phẩm nào?` });
  m.body.innerHTML = '<div class="sx-sp-grid">'
    + act.sku.map((it) => `<button type="button" class="sx-sp-chip sx-sku-pick" data-sku="${esc(it.name)}">${esc(it.item_name)}</button>`).join('')
    + '</div>';
  m.body.querySelectorAll('.sx-sku-pick').forEach((b) => {
    b.addEventListener('click', () => { m.close(); onPick(b.dataset.sku); });
  });
}

// Copy sản lượng ra clipboard để dán vào nhóm chat — công nhân tự đối chiếu (D27).
// Người có nhiều loại thì ghi tắt: "Khanh (Vào hộp 170: 29, Vào hộp 300: 50)".
function copySanLuong(nhom, ngay) {
  if (!nhom.length) { toastErr('Chưa có dòng nào để copy.'); return; }
  const d = (ngay || '').split('-');
  const tieuDe = d.length === 3 ? `SẢN LƯỢNG ${d[2]}/${d[1]}/${d[0]}` : 'SẢN LƯỢNG';
  const dong = nhom.map((g) => {
    const ct = g.dong.map((r) => `${r.activity_type || '?'}: ${formatNumber(r.so_hop)}`).join(', ');
    return `${g.ten} (${ct})`;
  });
  const tong = nhom.reduce((a, g) => a + g.dong.reduce((x, r) => x + (Number(r.so_hop) || 0), 0), 0);
  const text = `${tieuDe}\n${dong.join('\n')}\n— Tổng: ${formatNumber(tong)} sản phẩm`;
  chepVaoClipboard(text);
}

function chepVaoClipboard(text) {
  const xong = () => toast('Đã copy — dán vào nhóm chat.');
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(xong, () => hienDeChepTay(text));
    return;
  }
  hienDeChepTay(text);   // http / trình duyệt cũ: clipboard API không dùng được
}

function hienDeChepTay(text) {
  const m = openModal({ title: 'Copy sản lượng' });
  m.body.innerHTML = `
    <div class="sx-modal-msg">Bấm giữ để chọn rồi copy:</div>
    <textarea class="sx-textarea" id="sx-cp-text" rows="10" readonly></textarea>
  `;
  const ta = m.body.querySelector('#sx-cp-text');
  ta.value = text;
  ta.focus();
  ta.select();
}
