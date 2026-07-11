// Wrapper gọi whitelisted method — CSRF + bóc lỗi tiếng Việt + banner mất mạng.

const listeners = { offline: [] };

export function onOffline(fn) { listeners.offline.push(fn); }

function notifyOffline(isOffline) {
  listeners.offline.forEach((fn) => fn(isOffline));
}

window.addEventListener('offline', () => notifyOffline(true));
window.addEventListener('online', () => notifyOffline(false));

function extractError(data) {
  // Frappe trả lỗi trong _server_messages (JSON lồng JSON) hoặc exception
  try {
    if (data && data._server_messages) {
      const msgs = JSON.parse(data._server_messages);
      const first = JSON.parse(msgs[0]);
      if (first && first.message) return stripHtml(first.message);
    }
  } catch (e) { /* fallthrough */ }
  if (data && data.exception) {
    const m = String(data.exception).split(':').slice(1).join(':').trim();
    if (m) return m;
  }
  return 'Có lỗi xảy ra. Vui lòng thử lại.';
}

function stripHtml(s) {
  const d = document.createElement('div');
  d.innerHTML = s;
  return d.textContent || d.innerText || s;
}

export async function call(method, args = {}) {
  let res;
  try {
    res = await fetch(`/api/method/${method}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': (window.SX_CONTEXT || {}).csrfToken || '',
        Accept: 'application/json',
      },
      body: JSON.stringify(args),
    });
  } catch (e) {
    notifyOffline(true);
    throw new Error('Mất kết nối mạng. Kiểm tra wifi rồi thử lại.');
  }
  notifyOffline(false);
  let data = {};
  try { data = await res.json(); } catch (e) { /* body rỗng */ }
  if (!res.ok) throw new Error(extractError(data));
  return data.message;
}
