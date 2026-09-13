// Hash router tối giản + self-heal (LUẬT VÀNG #2): route lạ -> reload đúng 1 lần.

const routes = {};
const prefixes = [];
let renderFn = null;

export function register(path, loader) {
  routes[path] = loader;
}

/** Route có tham số: '#/qc/round/' khớp mọi '#/qc/round/QC-2026-09-0001'.
 *
 * Màn hình nhận cả route nên tự đọc phần đuôi. Không viết bộ khớp ':param' kiểu
 * framework: app này có đúng MỘT route có tham số, thêm một cỗ máy so khớp chỉ
 * để phục vụ nó là thêm chỗ để hỏng. */
export function registerPrefix(prefix, loader) {
  prefixes.push([prefix, loader]);
}

export function onRender(fn) {
  renderFn = fn;
}

export function currentRoute() {
  const hash = window.location.hash || '#/';
  return hash.split('?')[0];
}

export function go(path) {
  if (window.location.hash === path) {
    dispatch();
  } else {
    window.location.hash = path;
  }
}

async function dispatch() {
  const route = currentRoute();
  let loader = routes[route];
  if (!loader) {
    // Khớp tiền tố DÀI NHẤT trước: '#/qc/round/' phải thắng '#/qc/' nếu sau này
    // có cả hai, chứ không phụ thuộc thứ tự đăng ký.
    const hop = prefixes.filter(([p]) => route.startsWith(p))
      .sort((a, b) => b[0].length - a[0].length);
    if (hop.length) loader = hop[0][1];
  }
  if (!loader) {
    // Self-heal: shell cũ không biết route mới -> reload 1 lần (cờ chống loop)
    const key = `sx-heal-${route}`;
    if (!sessionStorage.getItem(key)) {
      sessionStorage.setItem(key, '1');
      window.location.reload();
      return;
    }
    loader = routes['#/'];
  }
  if (renderFn && loader) await renderFn(route, loader);
}

window.addEventListener('hashchange', dispatch);

export function start() {
  dispatch();
}
