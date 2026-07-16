// V Quản lý (#/quanly) — gate isQuanLy (server guard thật): KPI 7/30 ngày,
// công suất máy thực/định mức, TRUY XUẤT lô 2 chiều, Chart.js lazy (destroy trước khi vẽ lại).

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatKg, formatNumber, formatVND } from '/assets/sx/sx/lib/format.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';

let chartLib = null;
let currentChart = null;

async function loadChartLib() {
  if (chartLib) return chartLib;
  await new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4';
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
  chartLib = window.Chart;
  return chartLib;
}

export async function render({ container, ctx, call }) {
  container.innerHTML = '';
  const wrap = el('div', 'sx-view');
  container.appendChild(wrap);

  if (!ctx.isQuanLy) {
    wrap.innerHTML = '<div class="sx-card sx-card-center">Chỉ dành cho quản lý.</div>';
    return;
  }

  let soNgay = 7;
  wrap.innerHTML = `
    <h1 class="sx-h1">Quản lý</h1>
    <div class="sx-card">
      <div class="sx-field-label">Truy xuất lô — nhập mã batch TP</div>
      <div class="sx-tx-row">
        <input class="sx-textarea" id="sx-tx-input" placeholder="VD: BDX01-160726">
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

  // ── truy xuất
  wrap.querySelector('#sx-tx-go').addEventListener('click', async (e) => {
    const batch = wrap.querySelector('#sx-tx-input').value.trim();
    if (!batch) { toastErr('Nhập mã batch TP.'); return; }
    e.currentTarget.disabled = true;
    const box = wrap.querySelector('#sx-tx-result');
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

  // ── KPI
  const body = wrap.querySelector('#sx-ql-body');
  const btn7 = wrap.querySelector('#sx-ql-7');
  const btn30 = wrap.querySelector('#sx-ql-30');
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

  function paint(d) {
    const tongHop = d.phieu.reduce((a, p) => a + p.tong_hop_tp, 0);
    const tongLuong = d.phieu.reduce((a, p) => a + p.tong_luong_sp, 0);
    const hhAm = (d.ton_hon_hop || []).filter((t) => t.am);
    body.innerHTML = `
      ${hhAm.length ? `<div class="sx-error-box">⚠ Tồn hỗn hợp ÂM (có thể quên báo mẻ):
        ${hhAm.map((t) => `${esc(t.item)} (${esc(formatNumber(t.ton_kg, 1))} kg)`).join(', ')}</div>` : ''}
      <div class="sx-kpi-grid">
        <div class="sx-card sx-kpi"><div class="sx-kpi-label">Sản lượng</div>
          <div class="sx-kpi-value">${formatNumber(tongHop)} hộp</div>
          <div class="sx-muted">${d.phieu.length} ngày chốt</div></div>
        <div class="sx-card sx-kpi"><div class="sx-kpi-label">Lương SP</div>
          <div class="sx-kpi-value">${esc(formatVND(tongLuong))}</div></div>
        <div class="sx-card sx-kpi"><div class="sx-kpi-label">Dừng sự cố</div>
          <div class="sx-kpi-value">${formatNumber(d.phut_dung)} phút</div>
          <div class="sx-muted">${d.su_co.length} sự cố</div></div>
        <div class="sx-card sx-kpi"><div class="sx-kpi-label">Yield bột định mức</div>
          <div class="sx-kpi-value">${d.yield_dinh_muc != null ? `${formatNumber(d.yield_dinh_muc * 100, 1)}%` : '—'}</div></div>
      </div>
      <div class="sx-card"><div class="sx-field-label">Sản lượng theo ngày</div>
        <div class="sx-chart-box"><canvas id="sx-ql-chart"></canvas></div></div>
      <div class="sx-card"><div class="sx-field-label">Sản lượng theo SKU</div>
        <table class="sx-table"><thead><tr><th>SKU</th><th>Hộp</th></tr></thead>
        <tbody>${(d.san_luong_sku || []).map((r) => `
          <tr><td>${esc(r.san_pham)}</td><td><b>${formatNumber(r.so_hop)}</b></td></tr>`).join('')
          || '<tr><td colspan="2" class="sx-muted">Chưa có dữ liệu.</td></tr>'}</tbody></table></div>
      <div class="sx-card"><div class="sx-field-label">Năng suất vào hộp theo người</div>
        <table class="sx-table"><thead><tr><th>Công nhân</th><th>Hộp</th><th>Lương SP</th></tr></thead>
        <tbody>${(d.nang_suat_vao_hop || []).map((r) => `
          <tr><td>${esc(r.ten || r.nhan_vien)}</td><td><b>${formatNumber(r.so_hop)}</b></td>
          <td>${esc(formatVND(r.tien))}</td></tr>`).join('')
          || '<tr><td colspan="3" class="sx-muted">Chưa có dữ liệu.</td></tr>'}</tbody></table></div>
      <div class="sx-card"><div class="sx-field-label">Công suất máy cán (thực / định mức kỳ)</div>
        <table class="sx-table"><thead><tr><th>Máy</th><th>Thùng</th><th>Định mức kỳ</th><th>%</th></tr></thead>
        <tbody>${(d.cong_suat_may || []).map((r) => `
          <tr><td>${esc(r.may)}</td><td><b>${formatNumber(r.so_thung)}</b></td>
          <td>${r.dinh_muc_ky ? formatNumber(r.dinh_muc_ky) : '—'}</td>
          <td>${r.pct != null ? `${formatNumber(r.pct, 1)}%` : '—'}</td></tr>`).join('')
          || '<tr><td colspan="4" class="sx-muted">Chưa có dữ liệu.</td></tr>'}</tbody></table></div>
      <div class="sx-card"><div class="sx-field-label">Tồn hỗn hợp hiện tại</div>
        <table class="sx-table"><thead><tr><th>Hỗn hợp</th><th>Tồn (kg)</th></tr></thead>
        <tbody>${(d.ton_hon_hop || []).map((t) => `
          <tr><td>${esc(t.item)}</td><td class="${t.am ? 'sx-warn-text' : ''}"><b>${formatNumber(t.ton_kg, 1)}</b></td></tr>`).join('')
          || '<tr><td colspan="2" class="sx-muted">Chưa có Item hỗn hợp.</td></tr>'}</tbody></table></div>
      <div class="sx-card">
        <a class="sx-desk-link" href="/app/sx-ngay-san-xuat" target="_blank" rel="noopener">Mở Desk: Phiếu ngày SX ↗</a>
        <a class="sx-desk-link" href="/app/query-report/Serial and Batch Summary" target="_blank" rel="noopener">Serial & Batch Traceability Report ↗</a>
      </div>
    `;
    drawChart(d);
  }

  async function drawChart(d) {
    let Chart;
    try { Chart = await loadChartLib(); } catch (e) { return; }
    const canvas = body.querySelector('#sx-ql-chart');
    if (!canvas) return;
    if (currentChart) { currentChart.destroy(); currentChart = null; }
    currentChart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: d.phieu.map((p) => p.ngay.slice(5)),
        datasets: [{
          label: 'Hộp TP',
          data: d.phieu.map((p) => p.tong_hop_tp),
          backgroundColor: '#1d6ef5',
          borderRadius: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }

  await load();
}

function renderTruyXuat(d) {
  if (!(d.hon_hop || []).length) {
    return `<div class="sx-muted">Batch <b>${esc(d.batch_tp)}</b> (${esc(d.item_tp)}) chưa có
      chứng từ sản xuất nào — kiểm tra lại mã hoặc ngày chưa chốt.</div>`;
  }
  return `
    <div class="sx-tx-chain">
      <div class="sx-tx-node sx-tx-tp">📦 TP <b>${esc(d.batch_tp)}</b> <span class="sx-muted">(${esc(d.item_tp)})</span></div>
      ${d.hon_hop.map((hh) => `
        <div class="sx-tx-node sx-tx-hh">↳ 🥣 Hỗn hợp <b>${esc(hh.batch || '?')}</b>
          <span class="sx-muted">(${esc(hh.item)} · ${esc(formatKg(hh.kg))} · SE ${esc(hh.se_t3)})</span>
          ${(hh.bot || []).map((b) => `
            <div class="sx-tx-node sx-tx-bot">↳ 🌾 Bột lô rang <b>${esc(b.lo_rang)}</b>
              <span class="sx-muted">(${esc(formatKg(b.kg))} · SE ${esc(b.se_t2)})</span>
              ${b.lo_dau_ncc ? `<div class="sx-tx-node sx-tx-dau">↳ 🫘 Đậu lô NCC <b>${esc(b.lo_dau_ncc)}</b>
                <span class="sx-muted">(rang ${esc(b.ngay_rang || '?')} · phiếu ${esc(b.xuat_dau || '?')})</span></div>` : ''}
            </div>`).join('')}
        </div>`).join('')}
    </div>`;
}
