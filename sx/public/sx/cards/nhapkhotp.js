// Card Nhập kho thành phẩm (D51 → D56: NHÁP rồi DUYỆT).
//
// Hai tay, hai bước:
//   1. Người ở xưởng LẬP PHIẾU NHÁP — điền sẵn số theo sổ (tồn ở khu đóng gói).
//   2. THỦ KHO đi đếm thật, sửa số chỗ lệch, rồi DUYỆT. Duyệt mới sinh phiếu kho.
//
// Cả lý do tồn tại của màn này là có NGƯỜI THỨ HAI đếm lại. Vì vậy nút DUYỆT chỉ
// hiện với role thủ kho, và backend chặn lần nữa — ẩn nút không phải là bảo mật.

import { esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';
import { confirm2Step } from '/assets/sx/sx/components/modal.js';

export async function render({ container, call, refresh }) {
  container.className = 'sx-card';
  container.innerHTML = '<div class="sx-muted">Đang tải…</div>';

  let r;
  try {
    r = await call('sx.api.khotp.phieu_dang_mo');
  } catch (e) {
    container.innerHTML = `<div class="sx-error-box">${esc(e.message)}</div>`;
    return;
  }

  if (r.nhap) return vePhieu(container, r, call, refresh);
  return veLapMoi(container, r, call, refresh);
}

// ─────────────────────────────── chưa có phiếu nháp: mời lập ───────────────
async function veLapMoi(container, r, call, refresh) {
  let t;
  try {
    t = await call('sx.api.khotp.ton_cho_nhap');
  } catch (e) {
    container.innerHTML = `<div class="sx-error-box">${esc(e.message)}</div>`;
    return;
  }

  // Cùng kho = chưa bật bước nhận. Nói rõ phải sửa ở đâu, đừng hiện danh sách rỗng.
  if (t.cung_kho) {
    container.innerHTML = `
      <div class="sx-field-label">Nhập kho thành phẩm</div>
      <div class="sx-error-box">Chưa bật bước nhận: tầng 3 đang nhập TP thẳng vào
        <b>${esc(t.kho_dich)}</b> nên khu đóng gói không có gì để nhận.<br><br>
        Vào <b>SX Settings → Kho nhận TP từ tầng 3</b>, đặt là kho khu đóng gói
        (khác Kho TP), rồi chốt ngày lại.</div>`;
    return;
  }

  const rows = t.rows || [];
  const tong = rows.reduce((a, x) => a + x.cho_nhan, 0);
  container.innerHTML = `
    <div class="sx-vh-top">
      <div>
        <div class="sx-field-label">Chờ thủ kho nhận</div>
        <div class="sx-vh-tong">${formatNumber(tong)} <i>sp</i></div>
      </div>
      <div class="sx-vh-done">
        <div class="sx-field-label">Loại</div>
        <div class="sx-vh-done-so">${rows.length}</div>
      </div>
    </div>
    <div class="sx-muted">${esc(t.kho_nguon)} → ${esc(t.kho_dich)}</div>
    ${rows.length
      ? `<div class="sx-vh-list">${rows.map((x) => `
          <div class="sx-vh-row">
            <div class="sx-vh-who"><div class="sx-vh-name">${esc(x.ten)}</div></div>
            <span class="sx-nv-qty">${formatNumber(x.cho_nhan)} ${esc(x.dvt)}</span>
          </div>`).join('')}</div>
         <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nk-lap">
           LẬP PHIẾU NHẬN</button>
         <div class="sx-muted">Phiếu lập ra ở dạng NHÁP. Thủ kho đếm lại rồi duyệt,
           duyệt xong hàng mới vào ${esc(t.kho_dich)}.</div>`
      : `<div class="sx-muted">Khu đóng gói (${esc(t.kho_nguon)}) không còn hàng
           chờ nhận.</div>`}
    ${veGanDay(r.gan_day)}
  `;
  const btn = container.querySelector('#sx-nk-lap');
  if (btn) {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await call('sx.api.khotp.tao_phieu_nhap', {});
        toast('Đã lập phiếu nháp — mời thủ kho kiểm và duyệt.');
        refresh();
      } catch (e) { btn.disabled = false; toastErr(e.message); }
    });
  }
}

// ─────────────────────────────── có phiếu nháp: kiểm + duyệt ───────────────
function vePhieu(container, r, call, refresh) {
  const p = r.nhap;
  const rows = p.dong.map((x) => ({ ...x }));

  container.innerHTML = `
    <div class="sx-vh-top">
      <div>
        <div class="sx-field-label">Phiếu nháp ${esc(p.name)}</div>
        <div class="sx-vh-tong"><span id="sx-nk-tong">0</span> <i>sp</i></div>
        <div class="sx-vh-tien" id="sx-nk-lech"></div>
      </div>
      <div class="sx-vh-done">
        <div class="sx-field-label">Loại</div>
        <div class="sx-vh-done-so">${rows.length}</div>
      </div>
    </div>
    <div class="sx-muted">${esc(p.kho_nguon)} → ${esc(p.kho_dich)} · lập bởi
      ${esc(p.nguoi_lap || '')}. Bấm số để sửa theo đúng số ĐẾM ĐƯỢC.</div>
    <div class="sx-vh-list" id="sx-nk-rows"></div>
    ${p.duoc_duyet
      ? `<button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nk-duyet">
           DUYỆT — NHẬN VÀO KHO</button>
         <button type="button" class="sx-btn" id="sx-nk-huy">Xoá phiếu nháp</button>`
      : `<button type="button" class="sx-btn sx-btn-big" id="sx-nk-luu">LƯU SỐ ĐẾM</button>
         <div class="sx-muted">🔒 Bạn không có quyền duyệt. Thủ kho (role
           <b>SX Thu Kho</b>) sẽ kiểm và duyệt phiếu này.</div>`}
    ${veGanDay(r.gan_day)}
  `;

  const box = container.querySelector('#sx-nk-rows');
  function ve() {
    box.innerHTML = rows.map((x, i) => {
      const lech = x.so_dem - x.so_theo_so;
      return `<div class="sx-vh-row">
        <div class="sx-vh-who">
          <div class="sx-vh-name">${esc(x.ten)}</div>
          <div class="sx-vh-meta">sổ ${formatNumber(x.so_theo_so)}${
            lech ? ` · lệch ${lech > 0 ? '+' : ''}${formatNumber(lech)}` : ''}</div>
        </div>
        <button type="button" class="sx-vh-sl${lech ? ' sx-cell-lech' : ''}"
          data-i="${i}">${formatNumber(x.so_dem)}</button>
      </div>`;
    }).join('');
    box.querySelectorAll('.sx-vh-sl').forEach((b) => {
      const x = rows[Number(b.dataset.i)];
      b.addEventListener('click', () => openNumpad({
        kicker: 'Số đếm thật', title: x.ten, unitLabel: 'Số lượng', initial: x.so_dem,
        hint: (n) => (n !== x.so_theo_so
          ? `sổ ${formatNumber(x.so_theo_so)} · lệch ${n - x.so_theo_so > 0 ? '+' : ''}${
              formatNumber(n - x.so_theo_so)}` : ''),
        onOk: (v) => { x.so_dem = Math.max(0, Math.round(v)); ve(); },
      }));
    });
    const tong = rows.reduce((a, x) => a + x.so_dem, 0);
    const lechTong = tong - rows.reduce((a, x) => a + x.so_theo_so, 0);
    container.querySelector('#sx-nk-tong').textContent = formatNumber(tong);
    container.querySelector('#sx-nk-lech').textContent =
      lechTong ? `lệch ${lechTong > 0 ? '+' : ''}${formatNumber(lechTong)} so với sổ` : '';
  }
  ve();

  const gui = () => rows.map((x) => ({ item: x.item, so_luong: x.so_dem }));
  const luu = async () => call('sx.api.khotp.sua_phieu',
    { name: p.name, rows: JSON.stringify(gui()) });

  const btnLuu = container.querySelector('#sx-nk-luu');
  if (btnLuu) {
    btnLuu.addEventListener('click', async () => {
      try { await luu(); toast('Đã lưu số đếm vào phiếu nháp.'); refresh(); }
      catch (e) { toastErr(e.message); }
    });
  }

  const btnHuy = container.querySelector('#sx-nk-huy');
  if (btnHuy) {
    btnHuy.addEventListener('click', () => confirm2Step({
      title: 'Xoá phiếu nháp',
      message: `Xoá phiếu ${p.name}. Hàng vẫn nằm nguyên ở khu đóng gói, `
        + 'lập lại phiếu khác lúc nào cũng được.',
      confirmLabel: 'XOÁ PHIẾU',
      onConfirm: async () => {
        try { await call('sx.api.khotp.huy_phieu', { name: p.name }); toast('Đã xoá phiếu nháp.'); refresh(); }
        catch (e) { toastErr(e.message); throw e; }
      },
    }));
  }

  const btnDuyet = container.querySelector('#sx-nk-duyet');
  if (btnDuyet) {
    btnDuyet.addEventListener('click', async () => {
      const tong = rows.reduce((a, x) => a + x.so_dem, 0);
      const lech = tong - rows.reduce((a, x) => a + x.so_theo_so, 0);
      if (!tong) { toastErr('Chưa có dòng nào đếm được số > 0.'); return; }
      // Số đang sửa trên màn PHẢI lưu trước khi duyệt, không thì duyệt số cũ.
      try { await luu(); } catch (e) { toastErr(e.message); return; }
      confirm2Step({
        title: 'Duyệt phiếu nhận',
        message: `Nhận ${formatNumber(tong)} sản phẩm vào ${p.kho_dich}.`
          + (lech ? ` Lệch ${lech > 0 ? '+' : ''}${formatNumber(lech)} so với sổ — phần `
            + 'chênh nằm lại khu đóng gói, kiểm kê sau.' : '')
          + ' Duyệt xong phiếu kho được ghi; sửa thì phải huỷ phiếu.',
        confirmLabel: 'DUYỆT',
        onConfirm: async () => {
          try {
            await call('sx.api.khotp.duyet_phieu', { name: p.name });
            toast(`Đã nhận ${formatNumber(tong)} sản phẩm vào kho.`);
            refresh();
          } catch (e) { toastErr(e.message); throw e; }
        },
      });
    });
  }
}

function veGanDay(ds) {
  if (!ds || !ds.length) return '';
  return `
    <div class="sx-field-label">Phiếu đã duyệt gần đây</div>
    <div class="sx-vh-list">${ds.map((g) => `
      <div class="sx-vh-row">
        <div class="sx-vh-who">
          <div class="sx-vh-name">${esc(g.name)}</div>
          <div class="sx-vh-meta">${esc(g.ngay)} · ${esc(g.nguoi_duyet || '')}${
            g.tong_lech ? ` · lệch ${g.tong_lech > 0 ? '+' : ''}${formatNumber(g.tong_lech)}` : ''}</div>
        </div>
        <span class="sx-nv-qty">${formatNumber(g.tong_dem)}</span>
      </div>`).join('')}</div>`;
}
