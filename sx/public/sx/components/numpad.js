// Numpad phím TO tự dựng (không bàn phím hệ thống) — spec UX cứng cho lowtech.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { openModal } from '/assets/sx/sx/components/modal.js';

export function openNumpad({ title = 'Nhập số', initial = '', allowDecimal = false, unit = '', onOk }) {
  const m = openModal({ title });
  let value = String(initial === 0 || initial == null ? '' : initial);

  const display = el('div', 'sx-numpad-display');
  const unitNode = unit ? `<span class="sx-numpad-unit">${esc(unit)}</span>` : '';
  function paint() {
    display.innerHTML = `<span class="sx-numpad-value">${esc(value || '0')}</span>${unitNode}`;
  }
  paint();

  const grid = el('div', 'sx-numpad-grid');
  const keys = ['7', '8', '9', '4', '5', '6', '1', '2', '3', allowDecimal ? ',' : '', '0', '⌫'];
  keys.forEach((k) => {
    const btn = el('button', 'sx-numpad-key');
    btn.type = 'button';
    btn.textContent = k;
    if (!k) btn.disabled = true;
    btn.addEventListener('click', () => {
      if (k === '⌫') value = value.slice(0, -1);
      else if (k === ',') { if (!value.includes('.')) value = (value || '0') + '.'; }
      else if (value.replace('.', '').length < 9) value += k;
      paint();
    });
    grid.appendChild(btn);
  });

  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'XONG');
  ok.type = 'button';
  ok.addEventListener('click', () => {
    const num = parseFloat(value || '0') || 0;
    m.close();
    if (onOk) onOk(num);
  });

  m.body.appendChild(display);
  m.body.appendChild(grid);
  m.body.appendChild(ok);
  return m;
}
