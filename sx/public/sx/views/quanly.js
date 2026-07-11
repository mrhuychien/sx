// V5 Quản lý (#/quanly) — gate isQuanLy (server guard thật): KPI 7/30 ngày,
// Chart.js lazy từ CDN, destroy chart cũ trước khi vẽ lại, link mở Desk.

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
    <div class="sx-sp-grid">
      <button type="button" class="sx-sp-chip sx-sp-chip-on" id="sx-ql-7">7 ngày</button>
      <button type="button" class="sx-sp-chip" id="sx-ql-30">30 ngày</button>
    </div>
    <div id="sx-ql-body"><div class="sx-boot-loading">Đang tải…</div></div>
  `;
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
    const tongHop = d.phieu.reduce((a, p) => a + p.tong_hop, 0);
    const tongLuong = d.phieu.reduce((a, p) => a + p.tong_luong_sp, 0);
    const tongBtp = d.phieu.reduce((a, p) => a + p.btp_thuc_te_kg, 0);
    body.innerHTML = `
      <div class="sx-kpi-grid">
        <div class="sx-card sx-kpi"><div class="sx-kpi-label">Sản lượng</div>
          <div class="sx-kpi-value">${formatNumber(tongHop)} hộp</div>
          <div class="sx-muted">${esc(formatKg(tongBtp))} bột · ${d.phieu.length} ngày chốt</div></div>
        <div class="sx-card sx-kpi"><div class="sx-kpi-label">Yield bột</div>
          <div class="sx-kpi-value">${d.yield_thuc ? formatNumber(d.yield_thuc * 100, 1) : '—'}%</div>
          <div class="sx-muted">Định mức ${formatNumber(d.yield_dinh_muc * 100, 1)}%</div></div>
        <div class="sx-card sx-kpi ${d.ccp_pct_dat != null && d.ccp_pct_dat < 100 ? 'sx-kpi-warn' : ''}">
          <div class="sx-kpi-label">CCP đạt</div>
          <div class="sx-kpi-value">${d.ccp_pct_dat == null ? '—' : `${formatNumber(d.ccp_pct_dat, 1)}%`}</div>
          <div class="sx-muted">${d.ccp_dat}/${d.ccp_tong} lần ghi</div></div>
        <div class="sx-card sx-kpi"><div class="sx-kpi-label">Dừng sự cố</div>
          <div class="sx-kpi-value">${formatNumber(d.phut_dung)} phút</div>
          <div class="sx-muted">${d.su_co.length} sự cố · lương SP ${esc(formatVND(tongLuong))}</div></div>
      </div>
      <div class="sx-card"><div class="sx-field-label">Sản lượng theo ngày</div>
        <div class="sx-chart-box"><canvas id="sx-ql-chart"></canvas></div></div>
      <div class="sx-card"><div class="sx-field-label">Năng suất vào hộp theo người</div>
        <table class="sx-table"><thead><tr><th>Công nhân</th><th>Hộp</th><th>Lương SP</th></tr></thead>
        <tbody>${d.nang_suat_vao_hop.map((r) => `
          <tr><td>${esc(r.ten || r.nhan_vien)}</td><td><b>${formatNumber(r.so_hop)}</b></td>
          <td>${esc(formatVND(r.tien))}</td></tr>`).join('')
          || '<tr><td colspan="3" class="sx-muted">Chưa có dữ liệu.</td></tr>'}</tbody></table></div>
      <div class="sx-card">
        <a class="sx-desk-link" href="/app/sx-ngay-san-xuat" target="_blank" rel="noopener">Mở Desk: Phiếu ngày SX ↗</a>
        <a class="sx-desk-link" href="/app/query-report/Serial and Batch Summary" target="_blank" rel="noopener">Truy xuất lô (Traceability) ↗</a>
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
          data: d.phieu.map((p) => p.tong_hop),
          backgroundColor: '#3b82f6',
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
