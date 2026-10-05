// Card "Phiếu lương" trên màn Quản lý — xem nhanh, chỉ đọc (D110).
//
// Mỗi người một dòng: tên · lương SP · thực nhận · đã duyệt hay chưa. Bấm vào
// người → các khoản, sản phẩm gộp theo mã, từng ngày. Sửa / duyệt vẫn ở Desk
// (có lịch sử phiên bản) — nút "Mở trên Desk" đưa thẳng tới phiếu.
//
// Gập sẵn như lịch tháng: thẻ quản lý đã dài, lương không phải việc mỗi giờ.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';

const KHOA_MO = 'sx-phieuluong-mo';
const dong = (n) => `${formatNumber(Math.round(n || 0))} đ`;

export async function render({ container, call, boot }) {
  container.className = 'sx-card sx-lich';
  const goc = (boot && (boot.ngay_xem || boot.hom_nay)) || new Date().toISOString().slice(0, 10);
  const st = { nam: Number(goc.slice(0, 4)), thang: Number(goc.slice(5, 7)), q: '', mo: false };
  try { st.mo = localStorage.getItem(KHOA_MO) === '1'; } catch (e) { /* bỏ qua */ }

  const nut = el('button', 'sx-lich-nut');
  nut.type = 'button';
  const than = el('div', 'sx-lich-than');
  container.appendChild(nut);
  container.appendChild(than);
  const veNut = (tong) => {
    nut.innerHTML = `<span>💰 Phiếu lương</span><span class="sx-lich-tong">${
      tong ? `T${st.thang}: ${esc(dong(tong.thuc_nhan))} · ` : ''}${st.mo ? '▲' : '▼'}</span>`;
    nut.setAttribute('aria-expanded', st.mo ? 'true' : 'false');
  };
  nut.addEventListener('click', () => {
    st.mo = !st.mo;
    try { localStorage.setItem(KHOA_MO, st.mo ? '1' : '0'); } catch (e) { /* bỏ qua */ }
    if (st.mo) tai(); else { than.innerHTML = ''; veNut(null); }
  });

  let hen = null;
  async function tai() {
    than.innerHTML = '<div class="sx-muted">Đang tải…</div>';
    let dl;
    try { dl = await call('sx.api.luong.thang', { nam: st.nam, thang: st.thang, q: st.q || null }); } catch (e) {
      than.innerHTML = '';
      than.appendChild(el('div', 'sx-error-box', esc(e.message)));
      return;
    }
    veNut(dl.tong);
    ve(dl);
  }

  function doiThang(b) {
    st.thang += b;
    if (st.thang < 1) { st.thang = 12; st.nam -= 1; }
    if (st.thang > 12) { st.thang = 1; st.nam += 1; }
    tai();
  }

  function ve(dl) {
    than.innerHTML = '';
    const dau = el('div', 'sx-lich-dau');
    [['‹', -1, 'Tháng trước'], ['›', 1, 'Tháng sau']].forEach(([k, b, nhan], i) => {
      const n = el('button', 'sx-icon-btn', k);
      n.type = 'button';
      n.setAttribute('aria-label', nhan);
      n.addEventListener('click', () => doiThang(b));
      if (i === 0) dau.appendChild(n);
      else {
        dau.appendChild(el('div', 'sx-lich-ten', `Tháng ${st.thang}/${st.nam}`));
        dau.appendChild(n);
      }
    });
    than.appendChild(dau);

    const t = dl.tong;
    than.appendChild(el('div', 'sx-pl-tong', `
      <div><span class="sx-field-label">Thực nhận</span><b>${esc(dong(t.thuc_nhan))}</b></div>
      <div><span class="sx-field-label">Lương SP</span><b>${esc(dong(t.luong_san_pham))}</b></div>
      <div><span class="sx-field-label">Đã duyệt</span><b>${t.da_duyet}/${t.so_nguoi}</b></div>`));
    if (t.no_gia) {
      than.appendChild(el('div', 'sx-warn-text',
        `⚠ ${t.no_gia} phiếu còn dòng 0 đồng đang nợ đơn giá — chưa duyệt được. Xem thẻ Sổ nợ đơn giá.`));
    }

    const tim = el('input', 'sx-textarea sx-qc-lm-tim');
    tim.type = 'search';
    tim.placeholder = 'Tìm tên…';
    tim.value = st.q;
    tim.addEventListener('input', () => {
      clearTimeout(hen);
      hen = setTimeout(() => { st.q = tim.value.trim(); tai(); }, 350);
    });
    than.appendChild(tim);
    if (st.q) setTimeout(() => { tim.focus(); tim.setSelectionRange(tim.value.length, tim.value.length); }, 0);

    if (!dl.danh_sach.length) {
      than.appendChild(el('div', 'sx-muted', st.q ? 'Không ai khớp.'
        : 'Tháng này chưa có phiếu lương — phiếu tự ghi khi chốt Vào hộp.'));
      return;
    }
    const ds = el('div', 'sx-vh-list');
    dl.danh_sach.forEach((x) => {
      const h = el('button', 'sx-vh-row sx-pl-dong');
      h.type = 'button';
      h.innerHTML = `
        <div class="sx-vh-who">
          <div class="sx-vh-name">${esc(x.ten_nhan_vien || x.employee)}
            ${x.da_duyet ? '<span class="sx-badge sx-badge-ok">đã duyệt</span>' : ''}
            ${x.no_gia ? '<span class="sx-qc-tag sx-qc-tag-han">nợ giá</span>' : ''}</div>
          <div class="sx-vh-meta">SP ${esc(dong(x.luong_san_pham))} · ${formatNumber(x.ngay_cong)} công</div>
        </div>
        <span class="sx-nv-qty">${esc(dong(x.luong_thuc_nhan))}</span>`;
      h.addEventListener('click', () => moPhieu(x.name, call));
      ds.appendChild(h);
    });
    than.appendChild(ds);
  }

  veNut(null);
  if (st.mo) tai();
}

async function moPhieu(name, call) {
  let p;
  try { p = await call('sx.api.luong.chi_tiet', { name }); } catch (e) { toastErr(e.message); return; }
  const m = openModal({ kicker: `Phiếu lương T${p.thang}/${p.nam}${p.da_duyet ? ' · đã duyệt' : ''}`, title: p.ten });
  const b = m.body;
  b.appendChild(el('div', 'sx-pl-tong', `
    <div><span class="sx-field-label">Thực nhận</span><b>${esc(dong(p.thuc_nhan))}</b></div>
    <div><span class="sx-field-label">Ngày công</span><b>${formatNumber(p.ngay_cong)}${
      p.ngay_san_xuat ? `/${formatNumber(p.ngay_san_xuat)}` : ''}</b></div>`));

  const khoi = (ten, hang) => {
    if (!hang.length) return;
    b.appendChild(el('div', 'sx-field-label', esc(ten)));
    const ds = el('div', 'sx-vh-list');
    hang.forEach(([trai, phai, phu]) => ds.appendChild(el('div', 'sx-vh-row', `
      <div class="sx-vh-who"><div class="sx-vh-name">${esc(trai)}</div>
        ${phu ? `<div class="sx-vh-meta">${esc(phu)}</div>` : ''}</div>
      <span class="sx-nv-qty">${esc(phai)}</span>`)));
    b.appendChild(ds);
  };
  // Đúng thứ tự trên phiếu giấy: cộng → tổng thu nhập → trừ → thực nhận.
  khoi('Các khoản', [
    ...p.cong.map((x) => [x.ten, dong(x.tien)]),
    ['Tổng thu nhập', dong(p.tong_tien)],
    ...p.tru.map((x) => [x.ten, `− ${dong(x.tien)}`]),
    ...(p.tru.length ? [['Thực nhận', dong(p.thuc_nhan)]] : []),
  ]);
  khoi('Sản phẩm trong tháng', p.san_pham.map((x) => [
    `${x.ten}${x.cach_lam ? ` · ${x.cach_lam}` : ''}`, dong(x.thanh_tien),
    x.don_gia ? `${formatNumber(x.so_luong)} × ${formatNumber(x.don_gia)} đ`
      : `${formatNumber(x.so_luong)} × ⚠ chưa có giá`]));
  khoi('Từng ngày', p.ngay.map((x) => [
    `${x.ngay.slice(8)}/${x.ngay.slice(5, 7)} ${x.thu || ''}`, dong(x.thu_nhap),
    [x.luong_sp ? `SP ${dong(x.luong_sp)}${x.he_so > 1 ? ` ×${x.he_so}` : ''}` : '',
      x.an_ca ? 'ăn ca' : '', x.an_dem ? 'ăn đêm' : ''].filter(Boolean).join(' · ')]));
  khoi('Lỗi phạt', p.phat.map((x) => [x.ly_do || '—', `− ${dong(x.tien)}`]));
  if (p.ghi_chu) b.appendChild(el('div', 'sx-muted', esc(p.ghi_chu)));

  const desk = el('a', 'sx-btn sx-btn-big', 'Mở trên Desk để sửa / duyệt');
  desk.href = `/app/sx-phieu-luong/${encodeURIComponent(p.name)}`;
  desk.target = '_blank';
  desk.rel = 'noopener';
  b.appendChild(desk);
}
