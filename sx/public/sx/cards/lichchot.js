// Card "Chốt ngày" bằng lịch tháng (D117) — thay thẻ chốt theo ô ngày ở đầu màn.
//
// Mỗi ô hai chấm: GS (Ghi sổ) và VH (Vào hộp) — xám = không có gì, cam = có số liệu
// CHƯA chốt, xanh = đã chốt. Bấm ngày → xem nhanh báo mẻ / báo cán / rang / vào hộp
// của ngày đó, thấy ổn thì chốt luôn ngay dưới (cùng nút chốt của thẻ chotngay, kể
// cả bước khai giá vốn D116). Đầu thẻ đếm số ngày còn nửa nào chưa chốt.

import { el } from '/assets/sx/sx/lib/dom.js';
import { renderLich } from '/assets/sx/sx/components/lichthang.js';
import { veChot } from '/assets/sx/sx/cards/chotngay.js';

const TT = ['không có', 'chưa chốt', 'đã chốt'];

export function oChot(x) {
  return `<span class="sx-lc"><i class="sx-lc-${x.gs}">GS</i><i class="sx-lc-${x.vh}">VH</i></span>`;
}

export function render(api) {
  const { call } = api;
  return renderLich(api, {
    loai: 'chot',
    tieuDe: 'Chốt ngày',
    moSan: true,
    oNgay: oChot,
    nhanO: (x) => `Ghi sổ ${TT[x.gs]}, Vào hộp ${TT[x.vh]}`,
    chuThich: 'GS = Ghi sổ · VH = Vào hộp — cam: chưa chốt · xanh: đã chốt · '
      + 'bấm một ngày để xem nhanh rồi chốt',
    themChiTiet(body, ct, { dong, taiLai }) {
      if (!ct.phieu) {
        body.appendChild(el('div', 'sx-muted', 'Ngày này chưa có phiếu ngày — không có gì để chốt.'));
        return;
      }
      const box = el('div', 'sx-lc-chot');
      body.appendChild(box);
      const xong = () => { dong(); taiLai(); };
      veChot(box, ct.phieu, {
        boot: { ngay_sx: ct.phieu },
        call,
        ensureNgay: async () => ct.phieu,
        refresh: xong,
      });
    },
  });
}
