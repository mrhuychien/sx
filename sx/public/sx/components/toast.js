// Toast to, rõ, tiếng Việt — tự tắt sau 3.5s (lỗi, cảnh báo 6s).

import { el, esc } from '/assets/sx/sx/lib/dom.js';

let wrap = null;

function ensureWrap() {
  if (!wrap) {
    wrap = el('div', 'sx-toast-wrap');
    wrap.setAttribute('role', 'status');
    wrap.setAttribute('aria-live', 'polite');
    document.body.appendChild(wrap);
  }
  return wrap;
}

export function toast(message, kind = 'ok') {
  const node = el('div', `sx-toast sx-toast-${kind}`, esc(message));
  ensureWrap().appendChild(node);
  setTimeout(() => node.classList.add('sx-toast-show'), 10);
  // Lỗi, cảnh báo (vd thiết bị phải kiểm lại sau sửa chữa — W43) đứng lâu hơn để kịp đọc hết câu.
  const ttl = kind === 'ok' ? 3500 : 6000;
  setTimeout(() => {
    node.classList.remove('sx-toast-show');
    setTimeout(() => node.remove(), 300);
  }, ttl);
}

export function toastErr(message) { toast(message, 'err'); }
