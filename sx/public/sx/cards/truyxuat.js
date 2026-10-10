// Card "Truy xuất nguồn gốc" trên màn Quản lý (D115).
//
// Vào bằng đúng thứ người cầm hộp có: quét mã vạch (hoặc chọn loại) + HSD in trên
// hộp → lô. Hoặc gõ thẳng mã lô của bất cứ thứ gì (lô đỗ NCC, lô bột…).
//
// Một lô hiện 4 khối:
//   ⬅ Nguồn gốc   — cây nguyên liệu tới tận lô NCC (nhà cung cấp, hoá đơn, QC tiếp nhận)
//   🏭 Quá trình   — từng ngày: làm gì, ai vào hộp, lượt QC, sự cố
//   ➡ Đi đâu       — bán cho ai / xuất khác / còn tồn; lô không phải TP thì đi xuôi
//                    tới mọi lô TP làm ra từ nó
//   👥 Khách       — danh sách gộp phải gọi khi THU HỒI
// Bấm mã lô bất kỳ trong cây là truy tiếp lô đó.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { moQuet } from '/assets/sx/sx/components/quet.js';

// "2027-04-04" -> "04/04/27"
export function ngayNgan(iso) {
  const d = String(iso || '').slice(0, 10).split('-');
  return d.length === 3 ? `${d[2]}/${d[1]}/${d[0].slice(2)}` : '';
}

const so = (n, dvt) => `${formatNumber(n, Number.isInteger(Number(n)) ? 0 : 2)}${dvt ? ` ${dvt}` : ''}`;

export async function render({ container, call }) {
  container.className = 'sx-card sx-tx';
  const st = { item: null, ten: '', dm: null, lichSu: [] };

  container.innerHTML = `
    <div class="sx-tx-dau">🔎 Truy xuất nguồn gốc</div>
    <div id="tx-dt"></div>
    <div id="tx-th"></div>
    <div class="sx-muted">Quét mã vạch hộp (hoặc chọn sản phẩm) + nhập HSD in trên hộp.
      Hoặc gõ thẳng mã lô.</div>
    <div class="sx-tx-form">
      <div class="sx-tx-hang">
        <button type="button" class="sx-btn sx-tx-sp" id="tx-sp">Chọn sản phẩm…</button>
        <button type="button" class="sx-btn sx-quet-nut" id="tx-quet">⌗ Quét</button>
      </div>
      <div class="sx-tx-2o">
        <label class="sx-tx-o"><span class="sx-field-label">HSD in trên hộp</span>
          <input class="sx-textarea" id="tx-hsd" type="date"></label>
        <label class="sx-tx-o"><span class="sx-field-label">hoặc mã lô</span>
          <input class="sx-textarea" id="tx-q" type="search" autocomplete="off"
            placeholder="VD: BB-TT-061026"></label>
      </div>
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="tx-tra">TRA</button>
    </div>
    <div id="tx-kq"></div>`;
  const $ = (s) => container.querySelector(s);
  const kq = $('#tx-kq');
  const nutSp = $('#tx-sp');
  // W06 (D132): diễn tập truy xuất — đồng hồ chạy từ lúc bấm tới lúc kết thúc ở lô.
  const dt = { dang: null, hen: null };
  veDienTap();
  veThuHoi();

  // W26 (D136): lô đang thu hồi đứng đầu thẻ — bấm để mở hồ sơ lô (gọi khách, gỡ cờ).
  async function veThuHoi() {
    const box = $('#tx-th');
    let ds = [];
    try { ds = await call('sx.api.thuhoi.ds_thu_hoi'); } catch (e) { ds = []; }
    box.innerHTML = '';
    if (!ds.length) return;
    box.appendChild(el('div', 'sx-tx-th-dau', `⛔ Lô đang thu hồi (${ds.length}) — khoá bán / xuất`));
    const list = el('div', 'sx-vh-list');
    ds.forEach((x) => {
      const b = el('button', 'sx-vh-row sx-tx-lo sx-tx-th-lo');
      b.type = 'button';
      b.innerHTML = `<div class="sx-vh-who"><div class="sx-vh-name">${x.hsd ? `HSD ${esc(ngayNgan(x.hsd))}`
        : esc(x.batch)} · ${esc(x.ten)}</div><div class="sx-vh-meta">${esc(x.ly_do)}${
        x.luc ? ` · từ ${esc(ngayNgan(x.luc))}` : ''}</div></div><span class="sx-nv-qty">tồn ${esc(so(x.ton))}</span>`;
      b.addEventListener('click', () => moLo(x.batch, true));
      list.appendChild(b);
    });
    box.appendChild(list);
  }

  async function danhMuc() {
    if (!st.dm) st.dm = await call('sx.api.truyxuat.danh_muc');
    return st.dm;
  }
  function chonSp(item) {
    const d = (st.dm.sp || []).find((x) => x.item === item);
    st.item = item;
    st.ten = d ? d.ten : item;
    nutSp.textContent = st.item ? `📦 ${st.ten}` : 'Chọn sản phẩm…';
    nutSp.classList.toggle('sx-tx-sp-co', !!st.item);
  }

  nutSp.addEventListener('click', async () => {
    try { await danhMuc(); } catch (e) { toastErr(e.message); return; }
    moChonSp(st.dm.sp || [], st.item, (item) => chonSp(item));
  });
  $('#tx-quet').addEventListener('click', async () => {
    try { await danhMuc(); } catch (e) { toastErr(e.message); return; }
    moQuet({
      ma_quet: st.dm.ma_quet, loai: 'sp', kicker: 'Truy xuất', title: 'Quét mã vạch hộp',
      onTim: (item) => { chonSp(item); $('#tx-hsd').focus(); },
    });
  });

  $('#tx-tra').addEventListener('click', async (e) => {
    const q = $('#tx-q').value.trim();
    const hsd = $('#tx-hsd').value;
    if (!q && !st.item && !hsd) { toastErr('Chọn sản phẩm, nhập HSD, hoặc gõ mã lô.'); return; }
    e.currentTarget.disabled = true;
    kq.innerHTML = '<div class="sx-muted">Đang tìm…</div>';
    try {
      const r = await call('sx.api.truyxuat.tim_lo', { item: q ? null : st.item, hsd: q ? null : (hsd || null), q: q || null });
      if (r.lo.length === 1 && !r.gan_dung) moLo(r.lo[0].batch, true);
      else veDanhSach(r, hsd);
    } catch (err) {
      kq.innerHTML = '';
      toastErr(err.message);
    } finally { e.target.disabled = false; }
  });

  function veDanhSach(r, hsd) {
    kq.innerHTML = '';
    if (!r.lo.length) {
      kq.appendChild(el('div', 'sx-warn-text', hsd
        ? `Không có lô nào HSD ${esc(ngayNgan(hsd))} (kể cả lệch ±7 ngày). Lô nhập trước khi có `
          + 'ô HSD ở màn Nhập kho thì không mang HSD — thử gõ mã lô, hoặc bỏ HSD để xem các lô gần nhất.'
        : 'Không tìm thấy lô nào.'));
      return;
    }
    if (r.gan_dung) {
      kq.appendChild(el('div', 'sx-warn-text',
        `Không có lô đúng HSD ${esc(ngayNgan(hsd))}. Các lô HSD gần đó:`));
    } else {
      kq.appendChild(el('div', 'sx-field-label', `${r.lo.length} lô — bấm để xem`));
    }
    const ds = el('div', 'sx-vh-list');
    r.lo.forEach((x) => {
      const b = el('button', 'sx-vh-row sx-tx-lo');
      b.type = 'button';
      // W05: lô thành phẩm hiện bằng HSD (thứ in trên hộp), không bằng mã lô.
      const tpHsd = x.la_tp && x.hsd;
      b.innerHTML = `<div class="sx-vh-who"><div class="sx-vh-name">${tpHsd
        ? `HSD ${esc(ngayNgan(x.hsd))}` : esc(x.batch)}</div>
        <div class="sx-vh-meta">${esc(x.ten)}${x.nsx ? ` · NSX ${esc(ngayNgan(x.nsx))}` : ''}${
          x.hsd && !tpHsd ? ` · HSD ${esc(ngayNgan(x.hsd))}` : ''}</div></div>
        <span class="sx-nv-qty">tồn ${esc(so(x.ton))}</span>`;
      b.addEventListener('click', () => moLo(x.batch, true));
      ds.appendChild(b);
    });
    kq.appendChild(ds);
  }

  async function veDienTap() {
    const box = $('#tx-dt');
    if (dt.hen) { clearInterval(dt.hen); dt.hen = null; }
    if (dt.dang === null) {
      try { dt.dang = (await call('sx.api.truyxuat.dien_tap_dang')) || false; } catch (e) { dt.dang = false; }
    }
    if (!dt.dang) {
      box.innerHTML = `<div class="sx-tx-dt-hang">
        <button type="button" class="sx-btn" id="tx-dt-bd">⏱ DIỄN TẬP TRUY XUẤT</button>
        <button type="button" class="sx-btn sx-btn-ghost" id="tx-dt-ds">Lần trước</button></div>`;
      box.querySelector('#tx-dt-bd').addEventListener('click', batDauDienTap);
      box.querySelector('#tx-dt-ds').addEventListener('click', moDsDienTap);
      return;
    }
    const bd = new Date(String(dt.dang.bat_dau).replace(' ', 'T'));
    box.innerHTML = `<div class="sx-tx-dt-chay" role="status">
      <span>⏱ Đang diễn tập · <b id="tx-dt-gio">00:00</b></span>
      <span class="sx-muted">tra tới lô cần truy rồi bấm KẾT THÚC trên thẻ lô</span>
      <button type="button" class="sx-btn sx-btn-ghost" id="tx-dt-huy">Bỏ</button></div>`;
    const gio = box.querySelector('#tx-dt-gio');
    const dem = () => {
      const g = Math.max(0, Math.floor((Date.now() - bd.getTime()) / 1000));
      gio.textContent = `${String(Math.floor(g / 60)).padStart(2, '0')}:${String(g % 60).padStart(2, '0')}`;
    };
    dem();
    dt.hen = setInterval(() => { if (!gio.isConnected) { clearInterval(dt.hen); return; } dem(); }, 1000);
    box.querySelector('#tx-dt-huy').addEventListener('click', async () => {
      try { await call('sx.api.truyxuat.dien_tap_huy', { name: dt.dang.name }); } catch (e) { toastErr(e.message); return; }
      dt.dang = false; veDienTap(); toast('Đã bỏ lần diễn tập.');
    });
  }

  async function batDauDienTap() {
    try { dt.dang = await call('sx.api.truyxuat.dien_tap_bat_dau'); } catch (e) { toastErr(e.message); return; }
    veDienTap();
    toast('Bắt đầu bấm giờ — tra lô như khi có khiếu nại thật.');
  }

  function ketThucDienTap(batch, d) {
    const m = openModal({ kicker: 'Kết thúc diễn tập', title: d.lo.la_tp && d.lo.hsd
      ? `${d.lo.ten} · HSD ${ngayNgan(d.lo.hsd)}` : `${d.lo.ten} · ${d.lo.batch}` });
    m.body.innerHTML = `
      <div class="sx-muted">Đồng hồ dừng khi bấm LƯU. Có đếm thực tế tồn trong kho thì ghi
        số đếm — cân bằng tính theo số đếm + mẫu lưu; để trống thì theo tồn sổ sách.</div>
      <label class="sx-field-label" for="tx-dt-ton">Tồn đếm thực tế (${esc(d.lo.dvt || 'đơn vị kho')})</label>
      <input class="sx-textarea" id="tx-dt-ton" type="number" inputmode="decimal" min="0" step="any"
        placeholder="để trống = không đếm">
      <label class="sx-field-label" for="tx-dt-gc">Ghi chú / nhận xét</label>
      <textarea class="sx-textarea" id="tx-dt-gc" rows="2"></textarea>
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="tx-dt-luu">LƯU & DỪNG ĐỒNG HỒ</button>`;
    const nut = m.body.querySelector('#tx-dt-luu');
    nut.addEventListener('click', async () => {
      nut.disabled = true;
      const ton = m.body.querySelector('#tx-dt-ton').value;
      try {
        const r = await call('sx.api.truyxuat.dien_tap_ket_thuc', {
          name: dt.dang.name, batch, ton_thuc_te: ton === '' ? null : ton,
          ghi_chu: m.body.querySelector('#tx-dt-gc').value,
        });
        m.close();
        const ten = dt.dang.name;
        dt.dang = false;
        veDienTap();
        const cb = r.can_bang || {};
        toast(`Diễn tập ${ten}: ${r.so_phut} phút · cân bằng ${cb.pt ?? '—'}% `
          + `${cb.dat ? '✓ đạt' : '✕ chưa đạt'}`);
        inDienTap(ten, call);
      } catch (e) { nut.disabled = false; toastErr(e.message); }
    });
  }

  async function moDsDienTap() {
    let ds = [];
    try { ds = await call('sx.api.truyxuat.ds_dien_tap'); } catch (e) { toastErr(e.message); return; }
    const m = openModal({ kicker: 'Truy xuất', title: 'Các lần diễn tập' });
    m.body.innerHTML = ds.length ? `<div class="sx-vh-list">${ds.map((x) => `
      <button type="button" class="sx-nv-row" data-dt="${esc(x.name)}"
        style="flex-direction:row;align-items:center;justify-content:space-between;min-height:var(--sx-tap-lg)">
        <span class="sx-nv-who"><span class="sx-nv-ten">${esc(x.ten_san_pham || x.name)}${
          x.hsd ? ` · HSD ${esc(ngayNgan(x.hsd))}` : ''}</span>
          <span class="sx-vh-meta">${esc(ngayNgan(x.ngay))} · ${x.so_phut} phút · ${esc(x.nguoi || '')}</span></span>
        <span class="sx-nv-qty">${x.can_bang_pt}% ${x.dat ? '✓' : '✕'} 🖨</span></button>`).join('')}</div>`
      : '<div class="sx-muted">Chưa có lần diễn tập nào.</div>';
    m.body.querySelectorAll('[data-dt]').forEach((b) => b.addEventListener('click', () => inDienTap(b.dataset.dt, call)));
  }

  // Thu hồi / gỡ thu hồi một lô (W26) — Ban ISO / người được giao; server chốt quyền.
  function moThuHoi(batch, d) {
    const dang = d.thu_hoi.dang;
    const ten = d.lo.la_tp && d.lo.hsd ? `${d.lo.ten} · HSD ${ngayNgan(d.lo.hsd)}` : `${d.lo.ten} · ${d.lo.batch}`;
    const m = openModal({ kicker: dang ? 'Gỡ thu hồi' : 'THU HỒI LÔ', title: ten });
    m.body.innerHTML = `
      <div class="sx-modal-msg">${dang
    ? 'Gỡ cờ: lô bán / xuất lại được. Chỉ gỡ khi đã xử lý xong hoặc thu hồi nhầm.'
    : `Khoá NGAY mọi chứng từ bán / xuất lô này (trừ chuyển vào kho hàng trả về / cách ly, xuất huỷ).
       Danh sách ${(d.khach || []).length} khách đã nhận lô ở khối 👥 bên dưới.`}</div>
      <label class="sx-field-label" for="tx-th-ly">Lý do (bắt buộc)</label>
      <textarea class="sx-textarea" id="tx-th-ly" rows="2"></textarea>
      ${dang ? '' : `<label class="sx-field-label" for="tx-th-sc">Phiếu sự cố / khiếu nại liên quan</label>
      <select class="sx-textarea" id="tx-th-sc"><option value="">— lập phiếu sự cố mới —</option>${
  (d.su_co_lo || []).filter((x) => x.trang_thai === 'Mở').map((x) => `<option value="${esc(x.name)}">${
    esc(x.name)} · ${esc((x.mo_ta || '').slice(0, 40))}</option>`).join('')}</select>`}
      <button type="button" class="sx-btn ${dang ? 'sx-btn-primary' : 'sx-btn-danger'} sx-btn-big" id="tx-th-ok">${
  dang ? 'GỠ THU HỒI' : '⛔ THU HỒI LÔ NÀY'}</button>`;
    const ok = m.body.querySelector('#tx-th-ok');
    ok.addEventListener('click', async () => {
      const ly = m.body.querySelector('#tx-th-ly').value.trim();
      if (!ly) { toastErr('Ghi lý do.'); return; }
      ok.disabled = true;
      try {
        if (dang) await call('sx.api.thuhoi.go_thu_hoi', { batch, ly_do: ly });
        else {
          const r = await call('sx.api.thuhoi.thu_hoi_lo',
            { batch, ly_do: ly, su_co: m.body.querySelector('#tx-th-sc').value || null });
          toast(`Đã khoá xuất lô · phiếu sự cố ${r.su_co}`);
        }
        m.close();
        veThuHoi();
        moLo(batch, false);
      } catch (e) { ok.disabled = false; toastErr(e.message); }
    });
  }

  async function moLo(batch, moi) {
    if (moi) st.lichSu = [];
    kq.innerHTML = '<div class="sx-muted">Đang truy…</div>';
    let d;
    try { d = await call('sx.api.truyxuat.lo', { batch }); } catch (e) {
      kq.innerHTML = '';
      toastErr(e.message);
      return;
    }
    if (st.lichSu[st.lichSu.length - 1] !== batch) st.lichSu.push(batch);
    veLo(kq, d, {
      quayLai: st.lichSu.length > 1 ? () => { st.lichSu.pop(); moLo(st.lichSu.pop(), false); } : null,
      mo: (b) => moLo(b, false),
      ketThuc: dt.dang ? () => ketThucDienTap(batch, d) : null,
      thuHoi: d.thu_hoi && d.thu_hoi.duoc ? () => moThuHoi(batch, d) : null,
    });
    kq.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// ───────────────────────────── hồ sơ một lô ─────────────────────────────
export function veLo(box, d, { quayLai, mo, ketThuc, thuHoi }) {
  const l = d.lo;
  const n = d.nhap_kho;
  const b = d.ban || { ban: [], khac: [], ton: [], da_ban: 0, nhap: 0 };
  box.innerHTML = `
    ${quayLai ? '<button type="button" class="sx-btn sx-tx-lui" data-lui>‹ Lô trước</button>' : ''}
    <div class="sx-tx-the">
      <div class="sx-tx-the-lo">${l.la_tp && l.hsd ? `HSD ${esc(ngayNgan(l.hsd))}` : esc(l.batch)}</div>
      <div class="sx-tx-the-ten">${esc(l.ten)}</div>
      <div class="sx-tx-the-ngay">
        ${l.nsx ? `<span>NSX <b>${esc(ngayNgan(l.nsx))}</b></span>` : ''}
        ${l.hsd ? `<span>HSD <b>${esc(ngayNgan(l.hsd))}</b></span>` : ''}
        ${l.ngay_sx ? `<span>Làm ngày <b>${esc(ngayNgan(l.ngay_sx))}</b></span>` : ''}
      </div>
      ${n ? `<div class="sx-vh-meta">Nhập kho ${esc(ngayNgan(n.ngay))} · phiếu ${esc(n.phieu)} ·
        duyệt ${esc(n.nguoi_duyet || '?')}${(n.them || []).length
    ? ` · thêm ${n.them.map((x) => `${esc(x.phieu)} (${esc(ngayNgan(x.ngay))})`).join(', ')}` : ''}</div>`
    : ''}
      <div class="sx-tx-so">
        <div><span class="sx-field-label">Nhập</span><b>${esc(so(b.nhap, l.dvt))}</b></div>
        ${l.la_tp
    ? `<div><span class="sx-field-label">Đã bán</span><b>${esc(so(b.da_ban, l.dvt))}</b></div>`
    : `<div><span class="sx-field-label">Đã xuất</span><b>${esc(so(Math.max(0, b.nhap - l.ton), l.dvt))}</b></div>`}
        <div><span class="sx-field-label">Còn tồn</span><b>${esc(so(l.ton, l.dvt))}</b></div>
      </div>
    </div>
    ${d.thu_hoi && d.thu_hoi.dang ? `<div class="sx-tx-th-bang" role="alert">⛔ LÔ ĐANG THU HỒI — khoá bán / xuất
      <div class="sx-vh-meta">${esc((d.thu_hoi.ly_do || '').split('\n')[0])}${d.thu_hoi.su_co
    ? ` · phiếu ${esc(d.thu_hoi.su_co)}` : ''}${d.thu_hoi.luc ? ` · ${esc(ngayNgan(d.thu_hoi.luc))}` : ''}</div></div>` : ''}
    ${ketThuc ? '<button type="button" class="sx-btn sx-btn-primary sx-btn-big" data-ketthuc>⏹ KẾT THÚC DIỄN TẬP Ở LÔ NÀY</button>' : ''}
    ${thuHoi ? `<button type="button" class="sx-btn ${d.thu_hoi.dang ? 'sx-btn-ghost' : 'sx-btn-warn'}" data-thuhoi>${
    d.thu_hoi.dang ? 'Gỡ thu hồi lô' : '⛔ Thu hồi lô này'}</button>` : ''}
    ${(d.ghi_chu || []).map((g) => `<div class="sx-muted sx-tx-ghichu">ⓘ ${esc(g)}</div>`).join('')}
    ${d.can_bang && d.can_bang.san_xuat ? khoi(`⚖ Cân bằng lô — ${d.can_bang.pt ?? '—'}% ${
      d.can_bang.dat ? '✓' : '✕'}`, canBang(d.can_bang, l.dvt), !d.can_bang.dat) : ''}
    ${(d.khieu_nai_lo || []).length ? khoi('📣 Khiếu nại khách hàng của lô này',
    d.khieu_nai_lo.map(dongKhieuNai).join(''), true) : ''}
    ${(d.su_co_lo || []).length ? khoi('⚠ Sự cố ghi theo lô này', d.su_co_lo.map(dongSuCo).join(''), true) : ''}
    ${d.ncc ? khoi('🏭 Nhà cung cấp', dongNcc(d.ncc), true) : ''}
    ${(d.nguon || []).length ? khoi('⬅ Nguồn gốc nguyên liệu', cay(d.nguon), true) : ''}
    ${(d.qua_trinh || []).length ? khoi('🏭 Quá trình sản xuất', d.qua_trinh.map(ngay).join(''), true) : ''}
    ${d.xuat_xuong ? khoi('🧾 Kiểm tra xuất xưởng BM.08.04', d.xuat_xuong.length
    ? d.xuat_xuong.map(dongXuatXuong).join('')
    : '<div class="sx-muted">Lô chưa có phiếu kiểm tra xuất xưởng.</div>', true) : ''}
    ${l.la_tp ? khoi('➡ Đi đâu', diDau(b, l.dvt), true) : ''}
    ${d.xuoi ? khoi(l.la_tp ? `➡ Hàng đã chuyển sang ${demTp(d.xuoi)} lô theo HSD (kiểm kê)`
    : `➡ Đã đi vào ${demTp(d.xuoi)} lô thành phẩm`, d.xuoi.length
      ? cayXuoi(d.xuoi) : '<div class="sx-muted">Chưa dùng vào phiếu sản xuất nào.</div>', true) : ''}
    ${khoi(`👥 Khách đã nhận (${(d.khach || []).length})`, khach(d.khach || []), !l.la_tp)}
    ${(d.luu_mau || []).length ? khoi('🧪 Mẫu lưu', d.luu_mau.map(luuMau).join(''), false) : ''}
  `;
  const lui = box.querySelector('[data-lui]');
  if (lui) lui.addEventListener('click', quayLai);
  const kt = box.querySelector('[data-ketthuc]');
  if (kt) kt.addEventListener('click', ketThuc);
  const th = box.querySelector('[data-thuhoi]');
  if (th) th.addEventListener('click', thuHoi);
  box.querySelectorAll('[data-lo]').forEach((x) => x.addEventListener('click', () => mo(x.dataset.lo)));
}

// Bảng cân bằng lô (W06): sản xuất = bán + xuất khác + tồn (+ mẫu khi đếm thực tế).
function canBang(c, dvt) {
  const h = (ten, v, dam) => `<div class="sx-vh-row" style="cursor:default"><div class="sx-vh-who">
    <div class="sx-vh-name">${dam ? `<b>${esc(ten)}</b>` : esc(ten)}</div></div>
    <span class="sx-nv-qty">${esc(so(v, dvt))}</span></div>`;
  return `<div class="sx-vh-list">
    ${h('Sản xuất / nhập kho', c.san_xuat, true)}
    ${h('Đã bán (trừ trả lại)', c.da_ban)}
    ${h('Xuất khác (huỷ, dùng)', c.xuat_khac)}
    ${c.ton_thuc_te !== null && c.ton_thuc_te !== undefined
    ? h('Tồn đếm thực tế', c.ton_thuc_te) + h('Mẫu lưu đã lấy', c.mau_luu)
    : h('Tồn sổ sách', c.ton_so_sach)}
    ${h('Xác định được', c.tim_thay, true)}
    ${h('Chênh lệch', c.chenh_lech)}</div>
    <div class="${c.dat ? 'sx-muted' : 'sx-warn-text'}">Cân bằng ${c.pt ?? '—'}% — đạt khi ≥ ${c.nguong}%.${
      c.mau_luu ? ` Mẫu lưu ${esc(so(c.mau_luu, dvt))} nằm trong tồn sổ (lấy mẫu không trừ kho).` : ''}</div>`;
}

// In phụ lục BM.02.04 — cửa sổ mới, tự khai charset (cửa sổ about:blank không thừa kế).
async function inDienTap(name, call) {
  try {
    const html = await call('sx.api.truyxuat.in_dien_tap', { name });
    const w = window.open('', '_blank');
    if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
      + `<title>Phụ lục BM.02.04 — ${name}</title></head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 250);
  } catch (e) { toastErr(e.message); }
}

function khoi(tieuDe, than, mo) {
  return `<details class="sx-tx-khoi"${mo ? ' open' : ''}><summary>${esc(tieuDe)}</summary>
    <div class="sx-tx-than">${than}</div></details>`;
}

// `nhan`: chữ hiện trên nút — lô thành phẩm hiện "HSD …" thay mã lô (W05).
const nutLo = (b, nhan) => (b ? `<button type="button" class="sx-tx-ma" data-lo="${esc(b)}">${
  esc(nhan || b)}</button>` : '');

function dongNcc(c) {
  if (!c) return '<div class="sx-warn-text">Chưa rõ nhà cung cấp — lô không gắn hoá đơn mua nào.</div>';
  const kl = c.ket_luan
    ? `<span class="sx-tx-kl ${c.ket_luan === 'Đạt' ? 'sx-tx-kl-ok' : 'sx-tx-kl-loi'}">${esc(c.ket_luan)}</span>` : '';
  // W09 (D138): NCC đã duyệt BM.07.02 chưa; W10: giấy tờ lô app ghi lúc tiếp nhận.
  const duyet = c.ncc_duyet === undefined ? ''
    : `<span class="sx-tx-kl ${c.ncc_duyet ? 'sx-tx-kl-ok' : 'sx-tx-kl-loi'}">${
      c.ncc_duyet ? 'NCC đã duyệt' : 'NCC CHƯA duyệt'}</span>`;
  return `<div class="sx-tx-ncc">🏭 <b>${esc(c.ten_ncc || c.ncc || '?')}</b> ${kl} ${duyet}
    <div class="sx-vh-meta">${esc(c.chung_tu || '')}${c.ngay ? ` · ${esc(ngayNgan(c.ngay))}` : ''}${
      c.lo_ncc ? ` · lô NCC ${esc(c.lo_ncc)}` : ''}${c.coa ? ` · COA ${esc(c.coa)}` : ''}</div>${
      c.giay_to ? `<div class="sx-vh-meta">📄 ${esc(c.giay_to)}</div>` : ''}</div>`;
}

function cay(ds) {
  return `<ul class="sx-tx-cay">${ds.map((x) => {
    const btp = String(x.nhom || '').startsWith('BTP');
    return `<li><div class="sx-tx-nut">${btp ? '🥣' : '🧂'} <b>${esc(x.ten)}</b>
        <span class="sx-tx-sl">${esc(so(x.so, x.dvt))}</span>
        <div class="sx-vh-meta">${x.batch ? nutLo(x.batch) : '<i>không quản lý lô</i>'}${
          x.lap ? ' · <i>đã có ở nhánh trên</i>' : ''}${
          x.ngay_sx ? ` · làm ${esc(ngayNgan(x.ngay_sx))}` : ''}${
          x.rang ? ` · rang ${esc(ngayNgan(x.rang.ngay))} (${esc(x.rang.loai_dau || '')})` : ''}${
          !btp && x.hsd ? ` · HSD ${esc(ngayNgan(x.hsd))}` : ''}</div>
        ${x.batch && !btp ? dongNcc(x.ncc) : ''}</div>
      ${(x.con || []).length ? cay(x.con) : ''}</li>`;
  }).join('')}</ul>`;
}

// D178: "lệch" theo đúng luật sinh sự cố của vòng kiểm (nhiệt độ rang dưới ngưỡng, mạt kim loại, thử lạc dương
// tính… — không chỉ ô Không đạt); ảnh chụp diễn tập cũ chỉ có nhãn mục Không đạt, vẫn hiện như cũ.
function ngay(g) {
  const qc = g.qc.length
    ? g.qc.map((v) => `<div class="sx-tx-qc">QC ${esc(v.luot || '')} · ${v.nop ? 'đã nộp' : 'nháp'}${
      v.duyet ? ' · đã xem xét' : ''}${v.khong_dat.length
      ? ` · <b class="sx-tx-kl-loi">${v.cao ? 'Lệch mức CAO' : 'Lệch'}: ${esc(v.khong_dat.join('; '))}</b>`
      : ' · ✓ đạt hết'}</div>`).join('')
    : '<div class="sx-muted">Không có lượt kiểm QC ngày này.</div>';
  const vh = g.vao_hop.length
    ? `<div class="sx-tx-vh">📦 Vào hộp: ${g.vao_hop.map((v) => `${esc(v.ten)} ${formatNumber(v.so_hop)}`).join(' · ')}</div>`
    : '';
  return `<div class="sx-tx-ngay"><div class="sx-tx-ngay-dau"><b>${esc(ngayNgan(g.ngay))}</b>
      <span>${esc(g.viec.join(' · '))}</span></div>
    ${vh}${qc}${dongCat(g.cat)}${dongVai(g.vai)}${g.su_co.map(dongSuCo).join('')}</div>`;
}

// Ngày rang (D178): cát trong máy rang hôm đó — BM.08.03.
function dongCat(c) {
  if (!c) return '';
  const so = c.so_ngay === null || c.so_ngay === undefined
    ? '<b class="sx-tx-kl-loi">sổ cát không có cát đang dùng hôm này</b>'
    : `đã dùng ${esc(c.so_ngay)} ngày${c.qua_han ? ` <b class="sx-tx-kl-loi">(quá ${esc(c.toi_da)} ngày tối đa)</b>` : ''}`;
  const kln = c.doi_nguon
    ? ` · kim loại nặng khi đổi nguồn ${esc(ngayNgan(c.doi_nguon))}: ${c.kln === 'Đạt' ? 'Đạt'
      : `<b class="sx-tx-kl-loi">${esc(c.kln || 'chưa có kết quả')}</b>`}` : '';
  return `<div class="sx-tx-qc">🔥 Cát rang: ${so}${c.ncc ? ` · nguồn ${esc(c.ncc)}` : ''}${kln}</div>`;
}

// Ngày rang (D178): đỗ vừa rang vào thùng ủ phủ vải — lần giặt vải ủ gần nhất, BM.08.05.
function dongVai(v) {
  if (!v) return '';
  if (!v.ngay) return '<div class="sx-tx-qc">🧺 Vải ủ: <b class="sx-tx-kl-loi">sổ giặt chưa có lần giặt nào</b></div>';
  return `<div class="sx-tx-qc">🧺 Vải ủ: giặt ${esc(ngayNgan(v.ngay))} (${esc(v.so_ngay)} ngày trước${
    v.so_phut ? `, đun sôi ${esc(v.so_phut)} phút` : ''})${v.da_ky ? '' : ' · <b class="sx-tx-kl-loi">chưa QC ký</b>'}${
    v.qua_han ? ` · <b class="sx-tx-kl-loi">quá chu kỳ ${esc(v.chu_ky)} ngày</b>` : ''}</div>`;
}

// Phiếu kiểm tra xuất xưởng BM.08.04 của lô (D178): ai kiểm, ai duyệt, kết luận.
function dongXuatXuong(x) {
  const kl = x.ket_luan
    ? `<span class="sx-tx-kl ${x.cho_xuat ? 'sx-tx-kl-ok' : 'sx-tx-kl-loi'}">${esc(x.ket_luan)}</span>` : '';
  return `<div class="sx-vh-row"><div class="sx-vh-who"><div class="sx-vh-name">${esc(x.name)} · ${
    esc(x.trang_thai)} ${kl}</div>
    <div class="sx-vh-meta">${x.qc_kiem ? `QC kiểm ${esc(x.qc_kiem)}${x.kiem_luc ? ` ${esc(ngayGio(x.kiem_luc))}` : ''}` : ''}${
      x.nguoi_duyet ? ` · duyệt ${esc(x.nguoi_duyet)}${x.duyet_luc ? ` ${esc(ngayGio(x.duyet_luc))}` : ''}` : ''}${
      x.su_co ? ` · sự cố ${esc(x.su_co)}` : ''}</div>
    ${x.khong_dat.length ? `<div class="sx-vh-meta"><b class="sx-tx-kl-loi">Không đạt: ${
      esc(x.khong_dat.join('; '))}</b></div>` : ''}${x.y_kien ? `<div class="sx-vh-meta">Ý kiến duyệt: ${
      esc(x.y_kien)}</div>` : ''}</div></div>`;
}

const ngayGio = (s) => `${ngayNgan(String(s).slice(0, 10))} ${String(s).slice(11, 16)}`;

function dongKhieuNai(k) {
  return `<div class="sx-tx-suco">📣 ${esc(k.name)} · ${esc(k.trang_thai)}${
    k.muc_do === 'Cao' ? ' · <b>Cao</b>' : ''}${k.phan_loai ? ` · ${esc(k.phan_loai)}` : ''}${
    k.ngay ? ` · ${esc(ngayNgan(k.ngay))}` : ''}
    <div class="sx-vh-meta">${esc(k.mo_ta || '')}</div></div>`;
}

function dongSuCo(s) {
  return `<div class="sx-tx-suco">⚠ ${esc(s.name)}${s.dien_tap ? ' · DIỄN TẬP' : ''}${
    s.nguon ? ` · ${esc(s.nguon)}` : ''}${s.muc_do ? ` · ${esc(s.muc_do)}` : ''}${
    s.trang_thai ? ` · ${esc(s.trang_thai)}` : ''}${s.ngay ? ` · ${esc(ngayNgan(s.ngay))}` : ''}
    <div class="sx-vh-meta">${esc(s.mo_ta || '')}</div></div>`;
}

const MUC_DICH = {
  'Material Issue': 'Xuất dùng / huỷ', 'Material Transfer': 'Chuyển kho',
  'Manufacture': 'Đưa vào sản xuất', 'Repack': 'Đóng gói lại',
  'Material Transfer for Manufacture': 'Chuyển đi sản xuất',
};

function diDau(b, dvt) {
  const ban = b.ban.length
    ? b.ban.map((x) => `<div class="sx-vh-row"><div class="sx-vh-who">
        <div class="sx-vh-name">${esc(x.ten_khach || '?')}${x.tra_lai ? ' <i>(trả lại)</i>' : ''}</div>
        <div class="sx-vh-meta">${esc(x.chung_tu)} · ${esc(ngayNgan(x.ngay))}</div></div>
        <span class="sx-nv-qty">${x.tra_lai ? '↩ ' : ''}${esc(so(Math.abs(x.so), dvt))}</span></div>`).join('')
    : '<div class="sx-muted">Chưa bán (chưa có phiếu giao / hoá đơn bán nào ghi lô này).</div>';
  const khac = b.khac.map((x) => `<div class="sx-vh-row"><div class="sx-vh-who">
      <div class="sx-vh-name">${esc(x.kiem_ke ? `Kiểm kê ${x.kiem_ke} — ${x.muc_dich === 'Repack'
    ? 'chuyển sang lô theo HSD' : 'xuất thiếu'}` : (MUC_DICH[x.muc_dich] || x.muc_dich || x.loai))}</div>
      <div class="sx-vh-meta">${esc(x.chung_tu)} · ${esc(ngayNgan(x.ngay))} · từ ${esc(x.kho)}</div></div>
      <span class="sx-nv-qty">${esc(so(x.so, dvt))}</span></div>`).join('');
  const ton = b.ton.map((t) => `${esc(t.kho)}: <b>${esc(so(t.so, dvt))}</b>`).join(' · ');
  return `<div class="sx-vh-list">${ban}${khac}</div>
    ${ton ? `<div class="sx-vh-meta">Còn tồn — ${ton}</div>` : ''}`;
}

function demTp(ds) {
  let k = 0;
  (function di(x) { (x || []).forEach((n) => { if (n.la_tp && !n.lap) k += 1; di(n.con); }); }(ds));
  return k;
}

function cayXuoi(ds) {
  return `<ul class="sx-tx-cay">${ds.map((x) => `<li><div class="sx-tx-nut">${x.la_tp ? '📦' : '🥣'}
      <b>${esc(x.ten)}</b> <span class="sx-tx-sl">dùng ${esc(so(x.dung))}</span>
      <div class="sx-vh-meta">${nutLo(x.batch, x.la_tp && x.hsd ? `HSD ${ngayNgan(x.hsd)}` : null)}${
        x.nsx ? ` · NSX ${esc(ngayNgan(x.nsx))}` : ''}${x.bu ? ' · <i>trừ bù (nợ BOM)</i>' : ''}${
        x.lap ? ' · <i>đã có ở nhánh trên</i>' : ''}</div>
      ${x.ban ? `<div class="sx-vh-meta">→ bán ${esc(so(x.ban.da_ban))}${x.ban.ban.length
        ? ` cho ${esc([...new Set(x.ban.ban.map((y) => y.ten_khach))].join(', '))}` : ''}</div>` : ''}
    </div>${(x.con || []).length ? cayXuoi(x.con) : ''}</li>`).join('')}</ul>`;
}

function khach(ds) {
  if (!ds.length) return '<div class="sx-muted">Chưa khách nào nhận hàng từ lô này.</div>';
  return `<div class="sx-vh-list">${ds.map((k) => `<div class="sx-vh-row"><div class="sx-vh-who">
      <div class="sx-vh-name">${esc(k.ten_khach || k.khach || '?')}</div>
      <div class="sx-vh-meta">${k.lan_cuoi ? `lần cuối ${esc(ngayNgan(k.lan_cuoi))}` : ''}${
        k.lo.length ? ` · lô ${esc(k.lo.join(', '))}` : ''}</div></div>
      <span class="sx-nv-qty">${esc(so(k.so))}</span></div>`).join('')}</div>`;
}

function luuMau(m) {
  return `<div class="sx-vh-row"><div class="sx-vh-who"><div class="sx-vh-name">${esc(m.name)}
      ${m.co_anh ? '📷' : ''} <span class="sx-muted">khớp theo ${esc(m.khop)}</span></div>
    <div class="sx-vh-meta">lấy ${esc(ngayNgan(m.ngay_lay))}${m.lo ? ` · ghi "${esc(m.lo)}"` : ''}${
      m.vi_tri ? ` · ${esc(m.vi_tri)}` : ''} · ${esc(m.trang_thai || '')}</div></div>
    <span class="sx-nv-qty">${esc(so(m.so_luong, m.dvt))}</span></div>`;
}

function moChonSp(ds, dangChon, onChon) {
  const m = openModal({ kicker: 'Truy xuất', title: 'Chọn sản phẩm' });
  m.body.innerHTML = `<input class="sx-textarea" type="search" id="tx-loc" autocomplete="off"
      placeholder="Tìm trong ${ds.length} sản phẩm…"><div id="tx-ds"></div>`;
  const o = m.body.querySelector('#tx-loc');
  const box = m.body.querySelector('#tx-ds');
  function ve() {
    const q = o.value.toLowerCase().trim();
    const khop = ds.filter((d) => !q || d.ten.toLowerCase().includes(q) || d.item.toLowerCase().includes(q));
    box.innerHTML = khop.length ? `<div class="sx-vh-list">${khop.map((d) => `
      <button type="button" class="sx-nv-row${d.item === dangChon ? ' sx-nv-row-xong' : ''}"
        data-item="${esc(d.item)}" style="min-height:var(--sx-tap-lg)">
        <span class="sx-nv-ten">${esc(d.ten)}</span></button>`).join('')}</div>`
      : '<div class="sx-muted">Không tìm thấy.</div>';
    box.querySelectorAll('[data-item]').forEach((b) => b.addEventListener('click', () => {
      m.close(); onChon(b.dataset.item);
    }));
  }
  o.addEventListener('input', ve);
  ve();
}
