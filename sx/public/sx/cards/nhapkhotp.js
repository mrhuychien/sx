// Card Nhập kho thành phẩm (D51) — thủ kho ĐẾM rồi nhận hàng từ khu đóng gói.
//
// Mỗi dòng: tên SP · số theo SỔ đang chờ · ô nhập SỐ ĐẾM THẬT. Điền sẵn bằng số sổ
// vì phần lớn khớp; lệch thì sửa, và app hiện ngay lệch bao nhiêu.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';
import { confirm2Step } from '/assets/sx/sx/components/modal.js';

export async function render({ container, call, refresh }) {
  container.className = 'sx-card';
  container.innerHTML = '<div class="sx-muted">Đang tải hàng chờ nhận…</div>';

  let r;
  try {
    r = await call('sx.api.khotp.ton_cho_nhap');
  } catch (e) {
    container.innerHTML = `<div class="sx-error-box">${esc(e.message)}</div>`;
    return;
  }

  // Cùng kho = chưa bật bước nhận. Nói rõ phải sửa ở đâu, đừng hiện danh sách rỗng.
  if (r.cung_kho) {
    container.innerHTML = `
      <div class="sx-field-label">Nhập kho thành phẩm</div>
      <div class="sx-error-box">Chưa bật bước nhận: tầng 3 đang nhập TP thẳng vào
        <b>${esc(r.kho_dich)}</b> nên khu đóng gói không có gì để nhận.<br><br>
        Vào <b>SX Settings → Kho nhận TP từ tầng 3</b>, đặt là kho khu đóng gói
        (khác Kho TP), rồi chốt ngày lại.</div>`;
    return;
  }

  const rows = (r.rows || []).map((x) => ({ ...x, dem: x.cho_nhan }));
  if (!rows.length) {
    container.innerHTML = `
      <div class="sx-field-label">Nhập kho thành phẩm</div>
      <div class="sx-muted">Khu đóng gói (${esc(r.kho_nguon)}) không còn hàng chờ nhận.</div>`;
    return;
  }

  container.innerHTML = `
    <div class="sx-vh-top">
      <div>
        <div class="sx-field-label">Chờ thủ kho nhận</div>
        <div class="sx-vh-tong"><span id="sx-nk-tong">0</span> <i>sp</i></div>
        <div class="sx-vh-tien" id="sx-nk-lech"></div>
      </div>
      <div class="sx-vh-done">
        <div class="sx-field-label">Loại</div>
        <div class="sx-vh-done-so">${rows.length}</div>
      </div>
    </div>
    <div class="sx-muted">${esc(r.kho_nguon)} → ${esc(r.kho_dich)}. Bấm số để sửa
      theo đúng số đếm được.</div>
    <div class="sx-vh-list" id="sx-nk-rows"></div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nk-ok">
      NHẬN VÀO KHO TP</button>
  `;
  const box = container.querySelector('#sx-nk-rows');

  function ve() {
    box.innerHTML = rows.map((x, i) => {
      const lech = x.dem - x.cho_nhan;
      return `<div class="sx-vh-row">
        <div class="sx-vh-who">
          <div class="sx-vh-name">${esc(x.ten)}</div>
          <div class="sx-vh-meta">sổ ${formatNumber(x.cho_nhan)}${
            lech ? ` · lệch ${lech > 0 ? '+' : ''}${formatNumber(lech)}` : ''}</div>
        </div>
        <button type="button" class="sx-vh-sl${lech ? ' sx-cell-lech' : ''}"
          data-i="${i}">${formatNumber(x.dem)}</button>
      </div>`;
    }).join('');
    box.querySelectorAll('.sx-vh-sl').forEach((b) => {
      const x = rows[Number(b.dataset.i)];
      b.addEventListener('click', () => openNumpad({
        kicker: 'Số đếm thật', title: x.ten, unitLabel: 'Số lượng', initial: x.dem,
        hint: (n) => (n !== x.cho_nhan
          ? `sổ ${formatNumber(x.cho_nhan)} · lệch ${n - x.cho_nhan > 0 ? '+' : ''}${
              formatNumber(n - x.cho_nhan)}` : ''),
        onOk: (v) => { x.dem = Math.max(0, Math.round(v)); ve(); },
      }));
    });
    const tong = rows.reduce((a, x) => a + x.dem, 0);
    const lechTong = tong - rows.reduce((a, x) => a + x.cho_nhan, 0);
    container.querySelector('#sx-nk-tong').textContent = formatNumber(tong);
    container.querySelector('#sx-nk-lech').textContent =
      lechTong ? `lệch ${lechTong > 0 ? '+' : ''}${formatNumber(lechTong)} so với sổ` : '';
  }
  ve();

  container.querySelector('#sx-nk-ok').addEventListener('click', () => {
    const gui = rows.filter((x) => x.dem > 0).map((x) => ({ item: x.item, so_luong: x.dem }));
    if (!gui.length) { toastErr('Chưa nhập số lượng nhận cho sản phẩm nào.'); return; }
    const tong = gui.reduce((a, x) => a + x.so_luong, 0);
    const lech = tong - rows.reduce((a, x) => a + x.cho_nhan, 0);
    // Ghi kho thật -> xác nhận 2 bước, và nói rõ phần lệch sẽ NẰM LẠI khu đóng gói
    confirm2Step({
      title: 'Nhận vào Kho TP',
      message: `Nhận ${formatNumber(tong)} sản phẩm vào ${r.kho_dich}.`
        + (lech ? ` Lệch ${lech > 0 ? '+' : ''}${formatNumber(lech)} so với sổ — phần `
          + 'chênh nằm lại khu đóng gói, kiểm kê sau.' : '')
        + ' Phiếu kho ghi xong không sửa được, chỉ huỷ trên Desk.',
      confirmLabel: 'NHẬN VÀO KHO',
      onConfirm: async () => {
        try {
          const kq = await call('sx.api.khotp.nhap_kho_tp', { rows: JSON.stringify(gui) });
          toast(`Đã nhận ${formatNumber(kq.tong)} sản phẩm vào kho.`);
          refresh();
        } catch (e) { toastErr(e.message); }
      },
    });
  });
}
