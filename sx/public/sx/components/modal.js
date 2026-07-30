// Modal bottom-sheet tablet-first. openModal trả node body để render tuỳ ý.
// confirm2Step: xác nhận nguy hiểm 2 bước (Chốt ngày) — spec UX cứng.

import { el } from '/assets/sx/sx/lib/dom.js';

export function openModal({ title = '', kicker = '', onClose = null } = {}) {
  const overlay = el('div', 'sx-modal-overlay');
  const sheet = el('div', 'sx-modal');
  const head = el('div', 'sx-modal-head');
  // Tiêu đề 2 tầng theo bản thiết kế: dòng KICKER mono in hoa nói ĐANG LÀM GÌ,
  // dòng dưới là ĐỐI TƯỢNG (tên người / tên lô). Bị ngắt quãng giữa xưởng rồi
  // quay lại thì nhìn 2 dòng đó là biết mình đang ở đâu.
  const titleWrap = el('div', 'sx-modal-titles');
  if (kicker) {
    const k = el('div', 'sx-modal-kicker');
    k.textContent = kicker;
    titleWrap.appendChild(k);
  }
  const titleNode = el('div', 'sx-modal-title');
  titleNode.textContent = title;
  titleWrap.appendChild(titleNode);
  const closeBtn = el('button', 'sx-modal-close', '&times;');
  closeBtn.type = 'button';
  head.appendChild(titleWrap);
  head.appendChild(closeBtn);
  const body = el('div', 'sx-modal-body');
  sheet.appendChild(head);
  sheet.appendChild(body);
  overlay.appendChild(sheet);
  document.body.appendChild(overlay);

  function close() {
    overlay.remove();
    if (onClose) onClose();
  }
  closeBtn.addEventListener('click', close);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  return { body, close, sheet };
}

export function confirm2Step({ title, message, confirmLabel, onConfirm }) {
  const m = openModal({ title });
  const msg = el('div', 'sx-modal-msg');
  msg.textContent = message;
  const step1 = el('button', 'sx-btn sx-btn-warn sx-btn-big', '');
  step1.type = 'button';
  step1.textContent = confirmLabel;
  const step2 = el('button', 'sx-btn sx-btn-danger sx-btn-big', '');
  step2.type = 'button';
  step2.textContent = `XÁC NHẬN LẦN 2 — ${confirmLabel}`;
  step2.style.display = 'none';
  const cancel = el('button', 'sx-btn sx-btn-ghost sx-btn-big', '');
  cancel.type = 'button';
  cancel.textContent = 'Quay lại';
  m.body.appendChild(msg);
  m.body.appendChild(step1);
  m.body.appendChild(step2);
  m.body.appendChild(cancel);
  step1.addEventListener('click', () => {
    step1.style.display = 'none';
    step2.style.display = '';
  });
  step2.addEventListener('click', async () => {
    step2.disabled = true;
    step2.textContent = 'Đang xử lý…';
    try {
      await onConfirm();
      m.close();
    } catch (e) {
      step2.disabled = false;
      step2.textContent = `XÁC NHẬN LẦN 2 — ${confirmLabel}`;
      throw e;
    }
  });
  cancel.addEventListener('click', m.close);
  return m;
}
