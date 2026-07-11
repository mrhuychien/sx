// Shell portal /sx — hash router, bottom-nav, boot store, offline banner.
// View code-split: dynamic import với withV (assetVersion) — LUẬT VÀNG #1.

import { call, onOffline } from '/assets/sx/sx/lib/api.js';
import { el } from '/assets/sx/sx/lib/dom.js';
import * as router from '/assets/sx/sx/lib/router.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';

const BUILD = 'sx-1';
const CTX = window.SX_CONTEXT || {};
window.SX_APP = { build: BUILD };

function withV(path) {
  return `${path}?v=${encodeURIComponent(CTX.assetVersion || Date.now())}`;
}

const VIEW_MODULES = {
  '#/': () => import(withV('/assets/sx/sx/views/homnay.js')),
  '#/ccp': () => import(withV('/assets/sx/sx/views/ccp.js')),
  '#/tron': () => import(withV('/assets/sx/sx/views/tron.js')),
  '#/vaohop': () => import(withV('/assets/sx/sx/views/vaohop.js')),
  '#/quanly': () => import(withV('/assets/sx/sx/views/quanly.js')),
};

const NAV = [
  { route: '#/', label: 'Hôm nay', icon: '🏠' },
  { route: '#/ccp', label: 'CCP', icon: '🌡️' },
  { route: '#/tron', label: 'Trộn', icon: '🥣', can: 'isToTruong' },
  { route: '#/vaohop', label: 'Vào hộp', icon: '📦', can: 'isToTruong' },
  { route: '#/quanly', label: 'Quản lý', icon: '📊', can: 'isQuanLy' },
];

const store = {
  boot: null,
  async refresh() {
    this.boot = await call('sx.api.portal.get_boot');
    return this.boot;
  },
};

const app = document.getElementById('sx-app');

function buildShell() {
  app.innerHTML = '';
  const banner = el('div', 'sx-offline-banner');
  banner.textContent = 'Mất mạng — đang thử kết nối lại…';
  banner.style.display = 'none';
  const main = el('main', 'sx-main');
  const nav = el('nav', 'sx-bottom-nav');
  NAV.forEach((item) => {
    if (item.can && !CTX[item.can]) return;
    const btn = el('a', 'sx-nav-btn');
    btn.href = item.route;
    btn.dataset.route = item.route;
    btn.innerHTML = `<span class="sx-nav-icon">${item.icon}</span><span>${item.label}</span>`;
    nav.appendChild(btn);
  });
  app.appendChild(banner);
  app.appendChild(main);
  app.appendChild(nav);
  onOffline((isOff) => { banner.style.display = isOff ? '' : 'none'; });
  return { main, nav };
}

const { main, nav } = buildShell();

function markActive(route) {
  nav.querySelectorAll('.sx-nav-btn').forEach((b) => {
    b.classList.toggle('sx-nav-active', b.dataset.route === route);
  });
}

Object.entries(VIEW_MODULES).forEach(([route, loader]) => router.register(route, loader));

router.onRender(async (route, loader) => {
  // Gate quản lý: quyền THẬT kiểm ở server (dashboard có _guard) — đây chỉ là UI
  if (route === '#/quanly' && !CTX.isQuanLy) { router.go('#/'); return; }
  markActive(route);
  main.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  try {
    if (!store.boot) await store.refresh();
    const mod = await loader();
    await mod.render({
      container: main,
      boot: store.boot,
      ctx: CTX,
      refresh: () => store.refresh(),
      call,
    });
  } catch (e) {
    main.innerHTML = '';
    const err = el('div', 'sx-error-box');
    err.textContent = e.message || 'Có lỗi xảy ra.';
    const retry = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'THỬ LẠI');
    retry.type = 'button';
    retry.addEventListener('click', () => { store.boot = null; router.go(route); });
    main.appendChild(err);
    main.appendChild(retry);
    toastErr(e.message || 'Có lỗi xảy ra.');
  }
});

router.start();
