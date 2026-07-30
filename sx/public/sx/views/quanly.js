// View Quản lý (#/quanly) — gate isQuanLy (server guard thật): KPI 7/30 ngày,
// mẻ trộn vs cán, tồn BTP, truy xuất lô 2 chiều (cây đệ quy). Biểu đồ cột dựng bằng
// CSS — bỏ Chart.js từ CDN vì portal phải chạy được cả khi mất mạng (D37/D45).

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatNumber, formatVND } from '/assets/sx/sx/lib/format.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';

export async function render({ container, ctx, call, cards, mountCard }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);
  if (!ctx.isQuanLy) {
    wrap.innerHTML = '<div class="sx-card sx-card-center">Chỉ dành cho quản lý.</div>';
    return;
  }

  // D33: chốt ngày + lưu đồ tồn BTP nằm ở ĐẦU màn, trên dashboard. Chốt ngày là việc
  // phải làm mỗi ngày nên không được nằm dưới đáy trang sau 6 bảng thống kê.
  const dauMan = el('div');
  wrap.appendChild(dauMan);
  for (const c of (cards || [])) {
    await mountCard(c, dauMan);
  }

  let soNgay = 7;
  const than = el('div');
  wrap.appendChild(than);
  than.innerHTML = `
    <h1 class="sx-h1">Theo dõi</h1>
    <div class="sx-card">
      <div class="sx-field-label">Truy xuất lô — nhập mã batch TP</div>
      <div class="sx-tx-row">
        <input class="sx-textarea" id="sx-tx-input" aria-label="Mã batch thành phẩm"
          placeholder="VD: BB-TT-230726">
        <button type="button" class="sx-btn sx-btn-primary" id="sx-tx-go">TRUY XUẤT</button>
      </div>
      <div id="sx-tx-result"></div>
    </div>
    <div class="sx-sp-grid">
      <button type="button" class="sx-sp-chip sx-sp-chip-on" id="sx-ql-7">7 ngày</button>
      <button type="button" class="sx-sp-chip" id="sx-ql-30">30 ngày</button>
    </div>
    <div id="sx-ql-body"><div class="sx-boot-loading">Đang tải…</div></div>
  `;

  than.querySelector('#sx-tx-go').addEventListener('click', async (e) => {
    const batch = than.querySelector('#sx-tx-input').value.trim();
    if (!batch) { toastErr('Nhập mã batch TP.'); return; }
    e.currentTarget.disabled = true;
    const box = than.querySelector('#sx-tx-result');
    box.innerHTML = '<div class="sx-boot-loading">Đang tra…</div>';
    try {
      const d = await call('sx.api.portal.truy_xuat', { batch_tp: batch });
      box.innerHTML = renderTruyXuat(d);
    } catch (err) {
      box.innerHTML = '';
      toastErr(err.message);
    } finally {
      e.target.disabled = false;
    }
  });

  const body = than.querySelector('#sx-ql-body');
  const btn7 = than.querySelector('#sx-ql-7');
  const btn30 = than.querySelector('#sx-ql-30');
  btn7.addEventListener('click', () => { soNgay = 7; btn7.classList.add('sx-sp-chip-on'); btn30.classList.remove('sx-sp-chip-on'); load(); });
  btn30.addEventListener('click', () => { soNgay = 30; btn30.classList.add('sx-sp-chip-on'); btn7.classList.remove('sx-sp-chip-on'); load(); });

  async function load() {
    body.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
    let d;
    try {
      const den = new Date();
      const tu = new Date(Date.now() - (soNgay - 1) * 86400000);
      const iso = (x) => x.toISOString().slice(0, 10);
      d = await call('sx.api.portal.dashboard', { tu_ngay: iso(tu), den_ngay: iso(den) });
    } catch (e) {
      body.innerHTML = '';
      toastErr(e.message);
      return;
    }
    paint(d);
  }

  // Cột dựng bằng CSS: cao theo tỉ lệ với ngày cao nhất, số ở trên, nhãn ở dưới.
  // Không cần thư viện, không cần mạng, và đọc được cả khi font chưa tải xong.
  function veCot(hop) {
    const box = document.getElementById('sx-ql-cot');
    if (!box) return;
    const ds = (hop || []).slice(-7);
    const max = Math.max(1, ...ds.map((x) => Number(x.tong) || 0));
    box.innerHTML = ds.length ? ds.map((x) => {
      const v = Number(x.tong) || 0;
      const nhan = String(x.ngay || '').slice(5).replace('-', '/');
      return `<div class="sx-cot-1">
        <div class="sx-cot-so">${formatNumber(v)}</div>
        <div class="sx-cot-truc"><div class="sx-cot-thanh" style="height:${
          Math.max(2, Math.round((v / max) * 100))}%"></div></div>
        <div class="sx-cot-nhan">${esc(nhan)}</div>
      </div>`;
    }).join('') : '<div class="sx-muted">Chưa có ngày chốt nào.</div>';
  }

  function paint(d) {
    veCot(d.phieu.map((p) => ({ ngay: p.ngay, tong: p.tong_hop_tp })));
    const tongHop = d.phieu.reduce((a, p) => a + p.tong_hop_tp, 0);
    const tongLuong = d.phieu.reduce((a, p) => a + p.tong_luong_sp, 0);
    const canhBaoTron = (d.tron_vs_can || []).filter((x) => x.canh_bao);
    const btpAm = (d.ton_btp || []).filter((t) => t.am);
    body.innerHTML = `
      ${veCanhBao(btpAm, canhBaoTron)}
      <div class="sx-kpi-grid">
        <div class="sx-card sx-kpi"><div class="sx-kpi-label">Sản lượng</div>
          <div class="sx-kpi-value">${formatNumber(tongHop)} hộp</div>
          <div class="sx-muted">${d.phieu.length} ngày chốt</div></div>
        <div class="sx-card sx-kpi"><div class="sx-kpi-label">Lương SP</div>
          <div class="sx-kpi-value">${esc(formatVND(tongLuong))}</div></div>
        <div class="sx-card sx-kpi"><div class="sx-kpi-label">Dừng sự cố</div>
          <div class="sx-kpi-value">${formatNumber(d.phut_dung)} phút</div>
          <div class="sx-muted">${d.su_co.length} sự cố</div></div>
        <div class="sx-card sx-kpi"><div class="sx-kpi-label">SKU đã đóng</div>
          <div class="sx-kpi-value">${(d.san_luong_sku || []).length}</div></div>
      </div>
      <div class="sx-card"><div class="sx-field-label">Sản lượng theo ngày (sản phẩm)</div>
        <div class="sx-cot" id="sx-ql-cot"></div></div>
      <div class="sx-card"><div class="sx-field-label">Sản lượng theo SKU</div>
        <table class="sx-table"><thead><tr><th>SKU</th><th>Hộp</th></tr></thead>
        <tbody>${(d.san_luong_sku || []).map((r) => `<tr><td>${esc(r.san_pham)}</td><td><b>${formatNumber(r.so_hop)}</b></td></tr>`).join('')
          || '<tr><td colspan="2" class="sx-muted">Chưa có dữ liệu.</td></tr>'}</tbody></table></div>
      <div class="sx-card"><div class="sx-field-label">Năng suất vào hộp theo người</div>
        <table class="sx-table"><thead><tr><th>Công nhân</th><th>Hộp</th><th>Lương SP</th></tr></thead>
        <tbody>${(d.nang_suat_vao_hop || []).map((r) => `<tr><td>${esc(r.ten || r.nhan_vien)}</td><td><b>${formatNumber(r.so_hop)}</b></td><td>${esc(formatVND(r.tien))}</td></tr>`).join('')
          || '<tr><td colspan="3" class="sx-muted">Chưa có dữ liệu.</td></tr>'}</tbody></table></div>
      <div class="sx-card"><div class="sx-field-label">Mẻ trộn vs cán (bột bánh)</div>
        <table class="sx-table"><thead><tr><th>Bột bánh</th><th>Mẻ trộn</th><th>Mẻ cán</th></tr></thead>
        <tbody>${(d.tron_vs_can || []).map((r) => `<tr class="${r.canh_bao ? 'sx-row-warn' : ''}"><td>${esc(r.item)}</td><td>${formatNumber(r.me_tron, 1)}</td><td>${formatNumber(r.me_can, 1)}</td></tr>`).join('')
          || '<tr><td colspan="3" class="sx-muted">Chưa có dữ liệu.</td></tr>'}</tbody></table></div>
      <div class="sx-card">
        <a class="sx-desk-link" href="/app/sx-ngay-san-xuat" target="_blank" rel="noopener">Mở Desk: Phiếu ngày SX ↗</a>
        <a class="sx-desk-link" href="/app/query-report/Serial and Batch Summary" target="_blank" rel="noopener">Serial & Batch Traceability Report ↗</a>
        <a class="sx-desk-link" href="/app/stock-reconciliation" target="_blank" rel="noopener">Kiểm kê (Stock Reconciliation) ↗</a>
      </div>
    `;
  }

  await load();
}

// Cây truy xuất đệ quy: node {batch,item,nhom,nguon_lieu:[{item,batch,kg,nhom,con?,lo_rang?,lo_dau_ncc?,lo_ncc?}]}
function renderTruyXuat(d) {
  if (!d.cay || !(d.cay.nguon_lieu || []).length) {
    return `<div class="sx-muted">Batch <b>${esc(d.batch_tp)}</b> (${esc(d.item_tp)}) chưa có
      chứng từ sản xuất — kiểm tra mã hoặc ngày chưa chốt.</div>`;
  }
  return `<div class="sx-tx-chain"><div class="sx-tx-node sx-tx-tp">📦 TP <b>${esc(d.batch_tp)}</b>
    <span class="sx-muted">(${esc(d.item_tp)})</span></div>${renderNguonLieu(d.cay.nguon_lieu, 1)}</div>`;
}

// Cảnh báo gộp thành MỘT khối "cần xử lý" ở đầu màn (D36).
//
// Trước đây mỗi loại cảnh báo là một hộp đỏ riêng, và khi không có gì bất thường thì
// không hiện gì cả — quản lý không phân biệt được "đã kiểm, mọi thứ ổn" với "chưa
// tải xong". Trạng thái BÌNH THƯỜNG cũng phải nói ra thì mới tin được.
function veCanhBao(btpAm, canhBaoTron) {
  const muc = [];
  if (btpAm.length) {
    muc.push(`<li><b>Tồn bán thành phẩm ÂM</b> — thường là quên báo mẻ:<br>`
      + btpAm.map((t) => `${esc(t.item)} (${esc(formatNumber(t.ton_kg, 1))} kg)`).join(', ')
      + '</li>');
  }
  if (canhBaoTron.length) {
    muc.push('<li><b>Cán nhiều hơn trộn</b> — thiếu mẻ trộn hoặc báo cán sai:<br>'
      + canhBaoTron.map((t) => esc(t.item)).join(', ') + '</li>');
  }
  if (!muc.length) {
    return '<div class="sx-ok-box">✓ Không có bất thường trong kỳ đang xem.</div>';
  }
  return `<div class="sx-error-box"><div class="sx-canhbao-tieude">
      ⚠ ${muc.length} việc cần xử lý</div>
    <ul class="sx-canhbao-ds">${muc.join('')}</ul></div>`;
}

function renderNguonLieu(list, depth) {
  return (list || []).map((e) => {
    const icon = e.nhom && e.nhom.startsWith('BTP') ? '🥣' : '🧂';
    let html = `<div class="sx-tx-node sx-tx-d${Math.min(depth, 3)}">↳ ${icon} <b>${esc(e.batch)}</b>
      <span class="sx-muted">(${esc(e.item)} · ${esc(formatNumber(e.kg, 1))} kg)</span>`;
    if (e.lo_rang) {
      const dau = (e.lo_dau_ncc || []).join(', ');
      html += `<div class="sx-tx-node sx-tx-dau">↳ 🫘 Đậu lô NCC <b>${esc(dau || '?')}</b>
        <span class="sx-muted">(lô rang ${esc(e.lo_rang)} · ${esc(e.loai_dau || '')})</span></div>`;
    } else if (e.lo_ncc) {
      html += `<div class="sx-tx-node sx-tx-dau">↳ 🏭 Lô NCC <b>${esc(e.lo_ncc)}</b></div>`;
    }
    if (e.con && (e.con.nguon_lieu || []).length) {
      html += renderNguonLieu(e.con.nguon_lieu, depth + 1);
    }
    html += '</div>';
    return html;
  }).join('');
}
