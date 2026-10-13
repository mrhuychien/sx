// Lỗi đồng bộ của NGÀY ĐANG XEM (D204) — bấm nhãn "⚠ lỗi đồng bộ" trên thanh ngày.
//
// Trước D204 nhãn chỉ nói "xem lịch ở Quản lý": người đang ở chính màn Quản lý phải cuộn tìm
// thẻ lịch, bấm đúng ngày mới thấy câu lỗi. Giờ bấm nhãn là thấy NGAY câu lỗi từng phần (báo mẻ
// → kho, vào hộp → phiếu lương), cách xử lý theo loại lỗi, và — quản lý — nút KHAI GIÁ VỐN /
// THỬ LẠI như ở lịch (cùng API: sx.api.dongbo.thu_lai, sx.api.chot.thieu_gia_von_ngay).

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { moKhaiGia } from '/assets/sx/sx/cards/lichchot.js';

const PHAN = [['gs', 'Báo mẻ → kho'], ['vh', 'Vào hộp → phiếu lương']];

/** Cách xử lý theo câu lỗi đồng bộ — hàm thuần (test gọi thẳng). */
export function goiY(loi) {
  const s = String(loi || '');
  if (/not subscriptable/i.test(s)) {
    return 'Lỗi phần mềm đã sửa ở bản D202: cập nhật bản mới (git pull → bench migrate → bench restart) — '
      + 'lúc migrate hệ thống tự ghi lại phiếu lương các ngày dính lỗi này.';
  }
  if (/giá vốn|valuation rate/i.test(s)) {
    return 'Nguyên liệu chưa có giá vốn (chưa từng nhập mua có đơn giá): bấm KHAI GIÁ VỐN, nhập giá mua ước tính, '
      + 'rồi THỬ LẠI.';
  }
  if (/đã duyệt/i.test(s)) {
    return 'Phiếu lương tháng đó đã duyệt nên không ghi thêm được. Cần sửa lương ngày này thì huỷ duyệt phiếu lương '
      + 'đó (Desk → SX Phieu Luong) rồi THỬ LẠI; không cần thì để nguyên.';
  }
  if (/BOM/.test(s)) {
    return 'Mã bán thành phẩm chưa có BOM đang dùng: trên Desk tạo BOM cho mã đó (Đang dùng + Mặc định, Gửi) '
      + 'rồi THỬ LẠI.';
  }
  if (/không đủ|đủ tồn|insufficient|needed in|cần thêm|negative stock|tồn âm|âm kho/i.test(s)) {
    return 'Kho không đủ hàng để trừ theo số báo mẻ: kiểm tra phiếu nhập mua / chuyển kho nguyên liệu đã ghi đủ '
      + 'chưa, hoặc số báo mẻ có nhập nhầm — sửa xong rồi THỬ LẠI.';
  }
  if (/chưa từng chốt/i.test(s)) {
    return 'Ngày cũ từ trước khi bỏ chốt (D123): kiểm lại số liệu ngày đó rồi THỬ LẠI.';
  }
  if (/batch|lô /i.test(s)) {
    return 'Lỗi lô hàng: xem mã và lô trong câu báo (kho đó còn đủ hàng ở lô đó không, mã vừa kiểm kê bật lô '
      + 'không) rồi THỬ LẠI.';
  }
  return 'Sửa số liệu ngày đó (lưu lại là hệ thống tự chạy lại) hoặc bấm THỬ LẠI. Vẫn lỗi thì chụp màn này gửi '
    + 'bộ phận phần mềm.';
}

/** Mở hộp lỗi đồng bộ của một phiếu ngày.
 *  ngay   = boot.ngay_sx: {name, ngay, dong_bo: {gs: {cho, loi}, vh: {cho, loi}}}
 *  quanLy = được bấm THỬ LẠI / KHAI GIÁ VỐN (thẻ lịch đồng bộ — chỉ quản lý)
 *  xong() = sau mỗi lần thử lại: vẽ lại màn để thanh ngày nói đúng trạng thái mới. */
export function moDongBo({ ngay, call, quanLy, xong }) {
  const [, th, d] = String(ngay.ngay || '').split('-');
  const m = openModal({ kicker: `Đồng bộ ngày ${d}/${th}`, title: 'Lỗi đồng bộ' });
  let db = ngay.dong_bo || {};

  async function thuLai(nut) {
    if (nut) { nut.disabled = true; nut.textContent = 'Đang đồng bộ…'; }
    try {
      const r = await call('sx.api.dongbo.thu_lai', { ngay_sx: ngay.name });
      db = { gs: r.gs, vh: r.vh };
      if (xong) xong();
      if (PHAN.some(([k]) => db[k] && db[k].loi)) {
        toastErr('Vẫn còn lỗi — đọc câu báo và cách xử lý.');
        ve();
      } else {
        toast('Đã đồng bộ — kho và phiếu lương khớp số liệu.');
        m.close();
      }
    } catch (e) {
      toastErr(e.message);
      if (nut) { nut.disabled = false; nut.textContent = 'THỬ LẠI'; }
    }
  }

  function ve() {
    m.body.innerHTML = '';
    const loi = PHAN.filter(([k]) => db[k] && db[k].loi);
    if (!loi.length) {
      m.body.appendChild(el('div', 'sx-muted', 'Ngày này không còn lỗi đồng bộ.'));
      return;
    }
    loi.forEach(([k, ten]) => {
      const box = el('div', 'sx-db-phan');
      box.dataset.phan = k;
      box.innerHTML = `<div class="sx-field-label">${esc(ten)}</div>
        <div class="sx-lc-loi">${esc(db[k].loi)}</div>
        <div class="sx-db-goiy"><b>Cách xử lý:</b> ${esc(goiY(db[k].loi))}</div>`;
      m.body.appendChild(box);
    });
    if (!quanLy) {
      m.body.appendChild(el('div', 'sx-muted', 'Chỉ quản lý bấm THỬ LẠI được. Sửa rồi lưu lại số liệu ngày đó '
        + '(báo mẻ / bảng vào hộp) thì hệ thống cũng tự chạy lại.'));
      return;
    }
    if (loi.some(([k]) => /giá vốn/i.test(db[k].loi))) {
      const b = el('button', 'sx-btn', 'KHAI GIÁ VỐN');
      b.type = 'button';
      b.addEventListener('click', async () => {
        let ds = [];
        try { ds = (await call('sx.api.chot.thieu_gia_von_ngay', { ngay_sx: ngay.name })) || []; } catch (e) { /* */ }
        if (!ds.length) { toast('Không còn mã nào thiếu giá — bấm THỬ LẠI.'); return; }
        moKhaiGia(ds, call, () => thuLai(null));
      });
      m.body.appendChild(b);
    }
    const nut = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'THỬ LẠI');
    nut.type = 'button';
    nut.addEventListener('click', () => thuLai(nut));
    m.body.appendChild(nut);
  }
  ve();
  return m;
}
