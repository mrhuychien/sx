// Bốn mùa (D53) — chữ ký của phong cách NPP: đổi mùa là đổi tông cả app.
//
// Mùa chỉ đổi ACCENT (nút chính, tab đang mở, gradient, glow, nền). Màu NGỮ NGHĨA
// — đỏ hết hàng, vàng cảnh báo, xanh đạt — KHÔNG bao giờ đổi theo mùa: chúng nói
// tình trạng hàng hoá, mà tình trạng thì không phụ thuộc vào tháng mấy.
//
// Vì sao giữ tính năng "trang trí" này trong app xưởng: hai QC dùng màn hình này
// suốt ca, ngày nào cũng vậy, nhiều tháng liền. Đổi được tông là thứ duy nhất
// trong app thuộc về họ. Nó không đụng vào một con số nào.

import { el } from '/assets/sx/sx/lib/dom.js';
import { openModal } from '/assets/sx/sx/components/modal.js';

const KEY = 'sx_mua';   // KHÔNG dùng chung key với portal khác trên cùng site
const MUA = [
  { ma: 'xuan', ten: 'Xuân', icon: '🌸' },
  { ma: 'ha', ten: 'Hạ', icon: '☀️' },
  { ma: 'thu', ten: 'Thu', icon: '🍂' },
  { ma: 'dong', ten: 'Đông', icon: '❄️' },
];
const HOP_LE = MUA.map((m) => m.ma);

/** Mùa theo lịch VN: 4/2→4/5 Xuân · 5/5→6/8 Hạ · 7/8→6/11 Thu · còn lại Đông. */
export function muaTheoLich(d = new Date()) {
  const mmdd = (d.getMonth() + 1) * 100 + d.getDate();
  if (mmdd >= 204 && mmdd <= 504) return 'xuan';
  if (mmdd >= 505 && mmdd <= 806) return 'ha';
  if (mmdd >= 807 && mmdd <= 1106) return 'thu';
  return 'dong';
}

export function muaHienTai() {
  try {
    const v = localStorage.getItem(KEY);
    if (v && HOP_LE.includes(v)) return v;
  } catch (e) { /* localStorage bị chặn -> rơi về mùa theo lịch */ }
  return muaTheoLich();
}

export function apDungMua(app, ma) {
  const mua = HOP_LE.includes(ma) ? ma : muaHienTai();
  HOP_LE.forEach((m) => app.classList.remove(`sx-${m}`));
  app.classList.add(`sx-${mua}`);
  if (ma) { try { localStorage.setItem(KEY, ma); } catch (e) { /* không lưu được thì thôi */ } }
  return mua;
}

export function iconMua(ma) {
  return (MUA.find((m) => m.ma === (ma || muaHienTai())) || MUA[0]).icon;
}

/** Modal lưới 2×2. onDoi(ma) để nơi gọi cập nhật icon trên header. */
export function moChonMua(app, onDoi) {
  const dangChon = muaHienTai();
  const m = openModal({ kicker: 'Giao diện', title: 'Chọn mùa' });
  const grid = el('div', 'sx-mua-grid');
  MUA.forEach((x) => {
    const b = el('button', `sx-mua-o${x.ma === dangChon ? ' sx-mua-on' : ''}`);
    b.type = 'button';
    b.innerHTML = `<span aria-hidden="true">${x.icon}</span>${x.ten}`;
    b.setAttribute('aria-label', `Mùa ${x.ten}`);
    b.addEventListener('click', () => {
      apDungMua(app, x.ma);
      if (onDoi) onDoi(x.ma);
      m.close();
    });
    grid.appendChild(b);
  });
  const ghi = el('div', 'sx-modal-msg');
  ghi.textContent = 'Chỉ đổi màu giao diện trên máy này. Số liệu không đổi.';
  m.body.appendChild(grid);
  m.body.appendChild(ghi);
  return m;
}
