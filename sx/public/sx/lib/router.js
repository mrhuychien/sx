// Hash router tối giản + self-heal (LUẬT VÀNG #2): route lạ -> reload đúng 1 lần.

const routes = {};
let renderFn = null;

export function register(path, loader) {
  routes[path] = loader;
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
