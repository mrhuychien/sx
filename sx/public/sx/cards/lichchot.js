// Card "Đồng bộ kho & lương" theo lịch tháng (D117 → D123).
//
// Không còn CHỐT: báo mẻ / bảng vào hộp sửa lúc nào cũng được, hệ thống tự đưa chứng
// từ kho và phiếu lương về khớp (sx/api/dongbo.py). Lịch này để NHÌN xem ngày nào
// đã khớp, ngày nào đang chạy, ngày nào LỖI cần người xử lý.
//
// Mỗi ô hai nhãn: KHO (báo mẻ → kho) và LƯƠNG (vào hộp → phiếu lương)
//   xám = không có gì · cam = đang đồng bộ · xanh = đã khớp · ĐỎ = lỗi.
// Bấm ngày → xem nhanh số liệu + trạng thái + lỗi; nút THỬ LẠI và KHAI GIÁ VỐN (D116).

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { renderLich } from '/assets/sx/sx/components/lichthang.js';

const TT = ['không có', 'đang đồng bộ', 'đã khớp', 'LỖI'];

export function oChot(x) {
  return `<span class="sx-lc"><i class="sx-lc-${x.gs}">KHO</i><i class="sx-lc-${x.vh}">LƯƠNG</i></span>`;
}

export function render(api) {
  const { call } = api;
  return renderLich(api, {
    loai: 'chot',
    tieuDe: 'Đồng bộ kho & lương',
    moSan: true,
    oNgay: oChot,
    nhanO: (x) => `Kho ${TT[x.gs]}, lương ${TT[x.vh]}`,
    chuThich: 'KHO = báo mẻ vào kho · LƯƠNG = vào hộp vào phiếu lương — cam: đang chạy · '
      + 'xanh: đã khớp · đỏ: lỗi, bấm ngày để xem',
    themChiTiet(body, ct, { dong, taiLai }) {
      if (!ct.phieu) {
        body.appendChild(el('div', 'sx-muted', 'Ngày này chưa có số liệu.'));
        return;
      }
      veTrangThai(body, ct.phieu, call, () => { dong(); taiLai(); });
    },
  });
}

function veTrangThai(body, p, call, xong) {
  const box = el('div', 'sx-lc-chot');
  const db = p.dong_bo || {};
  const dong = (ten, x) => {
    const tt = (x && x.tt) || 0;
    return `<div class="sx-lc-dong sx-lc-dong-${tt}"><b>${esc(ten)}</b>
      <span>${['—', '⏳ đang đồng bộ…', '✓ đã khớp', '⚠ lỗi'][tt]}</span>
      ${x && x.loi ? `<div class="sx-lc-loi">${esc(x.loi)}</div>` : ''}</div>`;
  };
  box.innerHTML = `<div class="sx-field-label">Đồng bộ</div>
    ${dong('Báo mẻ → kho', db.gs)}${dong('Vào hộp → phiếu lương', db.vh)}
    <div class="sx-muted">Sửa báo mẻ / bảng vào hộp lúc nào cũng được — vài giây sau kho và
      phiếu lương tự khớp lại.</div>`;
  const loiGia = [db.gs, db.vh].some((x) => x && x.loi && /giá vốn/i.test(x.loi));
  if (loiGia) {
    const b = el('button', 'sx-btn', 'KHAI GIÁ VỐN');
    b.type = 'button';
    b.addEventListener('click', async () => {
      let ds = [];
      try { ds = (await call('sx.api.chot.thieu_gia_von_ngay', { ngay_sx: p.name })) || []; } catch (e) { /* bỏ qua */ }
      if (!ds.length) { toast('Không còn mã nào thiếu giá — bấm THỬ LẠI.'); return; }
      moKhaiGia(ds, call, () => thuLai());
    });
    box.appendChild(b);
  }
  const nut = el('button', 'sx-btn sx-btn-primary sx-btn-big',
    [db.gs, db.vh].some((x) => x && x.tt === 3) ? 'THỬ LẠI' : 'ĐỒNG BỘ NGAY');
  nut.type = 'button';
  async function thuLai() {
    nut.disabled = true;
    nut.textContent = 'Đang đồng bộ…';
    try {
      const r = await call('sx.api.dongbo.thu_lai', { ngay_sx: p.name });
      const loi = [r.gs && r.gs.loi, r.vh && r.vh.loi].filter(Boolean);
      if (loi.length) toastErr(loi.join(' · '));
      else toast('Đã đồng bộ — kho và phiếu lương khớp số liệu.');
      xong();
    } catch (e) { toastErr(e.message); nut.disabled = false; nut.textContent = 'THỬ LẠI'; }
  }
  nut.addEventListener('click', thuLai);
  box.appendChild(nut);
  body.appendChild(box);
}

// Khai giá vốn cho mã nguyên liệu chưa từng có giá (D116). Ghi Item.valuation_rate —
// giá DỰ PHÒNG của ERPNext: nhập mua có giá lần sau thì giá thật thay chỗ nó.
export function moKhaiGia(ds, call, xong) {
  const m = openModal({ kicker: 'Đồng bộ kho', title: 'Khai giá vốn' });
  m.body.innerHTML = `
    <div class="sx-modal-msg">${ds.length} mã nguyên liệu chưa có giá vốn (chưa nhập mua có đơn `
      + 'giá) nên ERPNext không trừ kho được. Nhập giá mua ước tính cho mỗi đơn vị kho — chỉ '
      + 'cần một lần; nhập mua có giá sau này sẽ thay giá này. Bán thành phẩm (bột, đường '
      + `hoán…) không phải nhập — máy tự tính từ giá nguyên liệu.</div>
    ${ds.map((d, i) => `<label class="sx-kgv">
      <span class="sx-kgv-ten">${esc(d.ten)} <span class="sx-muted">${esc(d.item)}</span></span>
      <span class="sx-kgv-o"><input class="sx-textarea" type="number" inputmode="decimal" min="0"
        step="any" data-i="${i}" value="${d.goi_y ? esc(String(d.goi_y)) : ''}"
        placeholder="đ"><span>đ / ${esc(d.dvt || 'đơn vị')}</span></span>
      ${d.goi_y ? '<span class="sx-muted">điền sẵn theo giá mua / giá chuẩn trên mã hàng</span>' : ''}
    </label>`).join('')}
    <div class="sx-warn-text" id="sx-kgv-loi" role="alert"></div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-kgv-ok">LƯU GIÁ &amp; ĐỒNG BỘ</button>`;
  const ok = m.body.querySelector('#sx-kgv-ok');
  ok.addEventListener('click', async () => {
    const rows = ds.map((d, i) => ({ item: d.item,
      gia: Number(m.body.querySelector(`[data-i="${i}"]`).value) }));
    const thieu = rows.filter((r) => !(r.gia > 0));
    if (thieu.length) {
      m.body.querySelector('#sx-kgv-loi').textContent = `Còn ${thieu.length} mã chưa nhập giá.`;
      return;
    }
    ok.disabled = true;
    try {
      await call('sx.api.chot.khai_gia_von', { rows: JSON.stringify(rows) });
      m.close();
      toast(`Đã khai giá vốn ${rows.length} mã.`);
      xong();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  return m;
}
