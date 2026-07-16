// Shell portal /sx (v2) — hash router, bottom-nav THEO ROLE, boot store, offline banner.
// View code-split: dynamic import với withV (assetVersion) — LUẬT VÀNG #1.

import { call, onOffline } from '/assets/sx/sx/lib/api.js';
import { el } from '/assets/sx/sx/lib/dom.js';
import * as router from '/assets/sx/sx/lib/router.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';

const BUILD = 'sx-2';
const CTX = window.SX_CONTEXT || {};
window.SX_APP = { build: BUILD };

function withV(path) {
  return `${path}?v=${encodeURIComponent(CTX.assetVersion || Date.now())}`;
}

const VIEW_MODULES = {
  '#/thukho': () => import(withV('/assets/sx/sx/views/thukho.js')),
  '#/tron': () => import(withV('/assets/sx/sx/views/tron.js')),
  '#/donggoi': () => import(withV('/assets/sx/sx/views/donggoi.js')),
  '#/quanly': () => import(withV('/assets/sx/sx/views/quanly.js')),
};

// Bottom-nav theo role (spec §6): chỉ hiện tab liên quan tới vai của user
const NAV = [
  { route: '#/thukho', label: 'Thủ kho', icon: '🏬', can: 'isThuKho' },
  { route: '#/tron', label: 'Trộn', icon: '🥣', can: 'isToTron' },
  { route: '#/donggoi', label: 'Đóng gói', icon: '📦', can: 'isToDongGoi' },
  { route: '#/quanly', label: 'Quản lý', icon: '📊', can: 'isQuanLy' },
];

const visibleNav = NAV.filter((n) => !n.can || CTX[n.can]);
const HOME = visibleNav.length ? visibleNav[0].route : '#/thukho';

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
  visibleNav.forEach((item) => {
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

// '#/' -> tab đầu tiên user được thấy
router.register('#/', () => VIEW_MODULES[HOME]());
Object.entries(VIEW_MODULES).forEach(([route, loader]) => router.register(route, loader));

router.onRender(async (route, loader) => {
  // Gate hiển thị theo role — quyền THẬT kiểm ở server (mọi method có _guard)
  const navItem = NAV.find((n) => n.route === route);
  if (navItem && navItem.can && !CTX[navItem.can]) { router.go(HOME); return; }
  markActive(route === '#/' ? HOME : route);
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
