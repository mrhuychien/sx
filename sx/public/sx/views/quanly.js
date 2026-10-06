// View Quản lý (#/quanly) — gate isQuanLy (server guard thật): KPI 7/30 ngày,
// mẻ trộn vs cán, tồn BTP. Truy xuất lô: card truyxuat (D115). Biểu đồ cột dựng bằng
// CSS — bỏ Chart.js từ CDN vì portal phải chạy được cả khi mất mạng (D37/D45).

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatNumber, formatVND } from '/assets/sx/sx/lib/format.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';

// Bố cục máy tính (D119): hai cột đầu màn — trái là việc PHẢI LÀM (QC treo, nợ,
// lịch chốt), phải là việc TRA CỨU (truy xuất, lương, tài khoản). Thẻ không có
// trong hai danh sách (tồn BTP theo luồng…) trải hết bề ngang bên dưới. Điện thoại
// chỉ là một cột: trái rồi phải rồi phần rộng, thứ tự gần như cũ.
const COT_TRAI = ['qcnhac', 'nobom', 'nogia', 'novaohop', 'lichchot'];
const COT_PHAI = ['truyxuat', 'phieuluong', 'nguoidung'];

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
  const tren = el('div', 'sx-ql-tren');
  const trai = el('div', 'sx-ql-cot');
  const phai = el('div', 'sx-ql-cot');
  const rong = el('div', 'sx-ql-cot sx-ql-rong-ds');
  tren.appendChild(trai);
  tren.appendChild(phai);
  wrap.appendChild(tren);
  wrap.appendChild(rong);
  // Song song (D120) — kể cả số liệu Theo dõi bên dưới (xem cuối hàm).
  const dangGan = (cards || []).map((c) => mountCard(c,
    COT_TRAI.includes(c) ? trai : (COT_PHAI.includes(c) ? phai : rong)));

  let soNgay = 7;
  const than = el('div');
  wrap.appendChild(than);
  than.className = 'sx-ql-theodoi';
  than.innerHTML = `
    <div class="sx-ql-dau">
      <h2 class="sx-h1">Theo dõi</h2>
      <div class="sx-ql-ky" role="group" aria-label="Kỳ xem">
        <button type="button" class="sx-ql-ky-on" id="sx-ql-7" aria-pressed="true">7 ngày</button>
        <button type="button" id="sx-ql-30" aria-pressed="false">30 ngày</button>
      </div>
    </div>
    <div id="sx-ql-body"><div class="sx-boot-loading">Đang tải…</div></div>
  `;

  const body = than.querySelector('#sx-ql-body');
  const btn7 = than.querySelector('#sx-ql-7');
  const btn30 = than.querySelector('#sx-ql-30');
  const chonKy = (n) => {
    soNgay = n;
    [[btn7, 7], [btn30, 30]].forEach(([b, k]) => {
      b.classList.toggle('sx-ql-ky-on', k === n);
      b.setAttribute('aria-pressed', k === n ? 'true' : 'false');
    });
    load();
  };
  btn7.addEventListener('click', () => chonKy(7));
  btn30.addEventListener('click', () => chonKy(30));

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
    const box = body.querySelector('#sx-ql-cot');
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
    }).join('') : `<div class="sx-ql-trong">Chưa có dữ liệu trong ${soNgay} ngày qua.</div>`;
  }

  function paint(d) {
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
      <div class="sx-ql-hang">
        <div class="sx-card sx-ql-bieudo"><div class="sx-field-label">Sản lượng theo ngày (sản phẩm)</div>
          <div class="sx-cot" id="sx-ql-cot"></div></div>
        <div class="sx-card sx-ql-lienket"><div class="sx-field-label">Liên kết nhanh</div>
          <a class="sx-desk-link" href="/app/sx-ngay-san-xuat" target="_blank" rel="noopener">Mở Desk: Phiếu ngày SX <span>↗</span></a>
          <a class="sx-desk-link" href="/app/query-report/Serial and Batch Summary" target="_blank" rel="noopener">Serial &amp; Batch Traceability Report <span>↗</span></a>
          <a class="sx-desk-link" href="/app/stock-reconciliation" target="_blank" rel="noopener">Kiểm kê (Stock Reconciliation) <span>↗</span></a>
        </div>
      </div>
      <div class="sx-ql-bang">
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
      ${veDoiChieu(d.doi_chieu_kho)}
      </div>
    `;
    // Vẽ cột SAU khi khung đã vào trang — trước D119 gọi trước innerHTML nên ô
    // biểu đồ luôn trống.
    veCot(d.phieu.map((p) => ({ ngay: p.ngay, tong: p.tong_hop_tp })));
  }

  await Promise.all([...dangGan, load()]);
}

// Đối chiếu chấm vào hộp vs đã nhập kho (D66).
//
// Hai con số này KHÔNG ràng buộc nhau — chấm vào hộp tính lương, nhập kho ghi tồn,
// hai chứng từ độc lập (D62). Nhưng lệch nhiều thì có chuyện: hộp lỗi, hàng còn ở
// xưởng chưa chuyển, hoặc quên lập phiếu nhận. Đối chiếu thuộc về BÁO CÁO, đặt ở
// đây thay vì chặn lúc nhập liệu.
function veDoiChieu(ds) {
  if (!ds || !ds.length) return '';
  const tongVH = ds.reduce((a, r) => a + r.vao_hop, 0);
  const tongNK = ds.reduce((a, r) => a + r.nhap_kho, 0);
  return `
    <div class="sx-card"><div class="sx-field-label">Vào hộp vs Nhập kho</div>
      <div class="sx-muted">Chấm vào hộp tính lương, nhập kho ghi tồn — hai việc riêng.
        Lệch âm là hàng chưa chuyển hết hoặc hộp lỗi; lệch dương thường là chấm sót.</div>
      <table class="sx-table">
        <thead><tr><th>Sản phẩm</th><th>Vào hộp</th><th>Nhập kho</th><th>Lệch</th></tr></thead>
        <tbody>${ds.map((r) => `
          <tr class="${r.lech > 0 ? 'sx-row-warn' : ''}">
            <td>${esc(r.ten)}</td>
            <td>${formatNumber(r.vao_hop)}</td>
            <td>${formatNumber(r.nhap_kho)}</td>
            <td><b>${r.lech > 0 ? '+' : ''}${formatNumber(r.lech)}</b></td>
          </tr>`).join('')}
          <tr><td><b>Tổng</b></td><td><b>${formatNumber(tongVH)}</b></td>
            <td><b>${formatNumber(tongNK)}</b></td>
            <td><b>${tongNK - tongVH > 0 ? '+' : ''}${formatNumber(tongNK - tongVH)}</b></td></tr>
        </tbody></table></div>`;
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

