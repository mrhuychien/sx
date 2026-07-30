// Wrapper gọi whitelisted method — CSRF + bóc lỗi tiếng Việt + banner mất mạng
// + HÀNG CHỜ GỬI khi offline (D37).

import { guiLai, lyDoChan, onQueue, trangThai, xepHang, xepHangDuoc } from './queue.js';

export { danhSach as hangCho, onQueue, trangThai as trangThaiHang } from './queue.js';

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
  // Frappe xuống dòng bằng thẻ HTML; textContent nuốt sạch -> mọi dòng dính liền
  // thành một khối chữ không đọc nổi. Đổi thành \n TRƯỚC khi bóc thẻ.
  d.innerHTML = String(s).replace(/<br\s*\/?>|<\/(p|div|li|tr)>/gi, '\n');
  return (d.textContent || d.innerText || s).replace(/\n{3,}/g, '\n\n').trim();
}

/** Gọi thẳng server, KHÔNG qua hàng chờ. Dùng cho chính việc gửi lại hàng chờ. */
async function goiThang(method, args = {}) {
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
    const err = new Error('Mất kết nối mạng. Kiểm tra wifi rồi thử lại.');
    err.mat_mang = true;      // để hàng chờ phân biệt "mất mạng" với "server từ chối"
    throw err;
  }
  notifyOffline(false);
  let data = {};
  try { data = await res.json(); } catch (e) { /* body rỗng */ }
  if (!res.ok) throw new Error(extractError(data));
  return data.message;
}

export async function call(method, args = {}) {
  // Đã biết là offline -> khỏi thử fetch cho mất 30 giây timeout
  if (!navigator.onLine) return xuLyOffline(method, args, null);
  try {
    return await goiThang(method, args);
  } catch (e) {
    if (!e.mat_mang) throw e;              // server từ chối -> lỗi nghiệp vụ thật
    return xuLyOffline(method, args, e);
  }
}

function xuLyOffline(method, args, loiGoc) {
  if (!xepHangDuoc(method)) {
    // KHÔNG im lặng bỏ qua, KHÔNG giả vờ thành công. Nói rõ vì sao phải chờ mạng.
    const e = new Error(`📴 Đang mất mạng. ${lyDoChan(method)}`);
    e.mat_mang = true;
    throw e;
  }
  const n = xepHang(method, args);
  notifyOffline(true);
  // Trả "thành công lạc quan": dữ liệu đã nằm trên máy, chắc chắn không mất.
  return { _hang_cho: true, _thu_tu: n };
}

/** Gửi lại toàn bộ hàng chờ. Gọi khi có mạng lại và khi mở app. */
export async function guiHangCho() {
  if (!navigator.onLine) return { da_gui: 0, loi: 0, con_lai: trangThai().so_luong };
  return guiLai(goiThang);
}

// Có mạng lại là gửi ngay, không đợi ai bấm
window.addEventListener('online', () => { guiHangCho(); });
