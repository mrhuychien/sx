// Bàn số phím TO tự dựng (không dùng bàn phím hệ thống) — dựng theo bản thiết kế
// "Xưởng SX - App (1a)" (D39).
//
// Bố cục từ trên xuống, đúng thứ tự người dùng đi qua:
//   KICKER mono in hoa  ·  ĐỐI TƯỢNG (tên người / tên lô)      [×]
//   [chip chọn loại]  — chip đang chọn tô nền MỰC
//   ┌ nền mực ────────────────────────────────┐
//   │ SỐ HỘP                                  │   ô đọc lại trước khi lưu:
//   │ 170                            136.000 đ│   nền tối để con số nhảy hẳn ra
//   └─────────────────────────────────────────┘
//   [1][2][3] … [C][0][⌫]
//   [ LƯU ]
//
// Vì sao ô số nền tối: đây là chỗ duy nhất QC kiểm lại trước khi ghi, và cũng là chỗ
// sai một chữ số thì sai tồn kho. Tách hẳn khỏi nền trang là cách rẻ nhất để bắt mắt
// dừng lại ở đó.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { openModal } from '/assets/sx/sx/components/modal.js';

export function openNumpad({
  title = 'Nhập số',
  kicker = '',
  initial = '',
  allowDecimal = false,
  unit = '',
  unitLabel = '',      // nhãn mono trong ô mực; bỏ trống thì suy từ `unit`
  chips = null,        // [{ label, value, on }] — hàng chọn loại phía trên ô số
  onChip = null,       // (value) => nhãn đơn vị mới (hoặc không trả gì)
  hint = null,         // (soNhap) => string — dòng phụ bên phải ô mực (vd tiền)
  okLabel = 'LƯU',
  onOk,
}) {
  const m = openModal({ title, kicker });
  let value = String(initial === 0 || initial == null ? '' : initial);
  let nhanDonVi = unitLabel || unit || 'SỐ';

  // ── hàng chip chọn loại ──
  let chipRow = null;
  if (chips && chips.length) {
    chipRow = el('div', 'sx-np-chips');
    chips.forEach((c) => {
      const b = el('button', `sx-np-chip${c.on ? ' sx-np-chip-on' : ''}`);
      b.type = 'button';
      b.textContent = c.label;
      b.addEventListener('click', () => {
        chipRow.querySelectorAll('.sx-np-chip').forEach((x) => x.classList.remove('sx-np-chip-on'));
        b.classList.add('sx-np-chip-on');
        if (onChip) {
          const nhan = onChip(c.value);
          if (nhan) nhanDonVi = nhan;
        }
        paint();
      });
      chipRow.appendChild(b);
    });
  }

  // ── ô số nền mực ──
  const display = el('div', 'sx-numpad-display');
  function paint() {
    const so = parseFloat(value || '0') || 0;
    const phu = hint ? hint(so) : '';
    display.innerHTML = `
      <div class="sx-np-left">
        <div class="sx-numpad-unit">${esc(nhanDonVi)}</div>
        <div class="sx-numpad-value">${esc(value || '0')}</div>
      </div>
      ${phu ? `<div class="sx-np-hint">${esc(phu)}</div>` : ''}`;
  }
  paint();

  // ── bàn phím: 1-9 rồi C / 0 / xoá, đúng thứ tự trong bản thiết kế ──
  const grid = el('div', 'sx-numpad-grid');
  const keys = ['1', '2', '3', '4', '5', '6', '7', '8', '9',
                allowDecimal ? ',' : 'C', '0', '⌫'];
  keys.forEach((k) => {
    const btn = el('button', 'sx-numpad-key');
    btn.type = 'button';
    btn.textContent = k;
    if (k === 'C' || k === '⌫') btn.classList.add('sx-np-key-phu');
    if (k === 'C') btn.classList.add('sx-np-key-xoa');
    btn.addEventListener('click', () => {
      if (k === '⌫') value = value.slice(0, -1);
      else if (k === 'C') value = '';
      else if (k === ',') { if (!value.includes('.')) value = (value || '0') + '.'; }
      else if (value.replace('.', '').length < 9) value += k;
      paint();
    });
    grid.appendChild(btn);
  });

  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', '');
  ok.type = 'button';
  ok.textContent = okLabel;
  ok.addEventListener('click', () => {
    const num = parseFloat(value || '0') || 0;
    m.close();
    if (onOk) onOk(num);
  });

  if (chipRow) m.body.appendChild(chipRow);
  m.body.appendChild(display);
  m.body.appendChild(grid);
  m.body.appendChild(ok);
  return m;
}
