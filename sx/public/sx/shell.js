// Shell portal /sx (v3) — hash router, nav theo views, view lắp từ CARDS.
// Card-based: view render bằng mountCard(name) → dynamic import card (withV).

import { call, onOffline } from '/assets/sx/sx/lib/api.js';
import { el } from '/assets/sx/sx/lib/dom.js';
import * as router from '/assets/sx/sx/lib/router.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';

const BUILD = 'sx-3';
const CTX = window.SX_CONTEXT || {};
window.SX_APP = { build: BUILD };

function withV(path) {
  return `${path}?v=${encodeURIComponent(CTX.assetVersion || Date.now())}`;
}

const VIEW_PATHS = {
  ghiso: '/assets/sx/sx/views/ghiso.js',
  vaohop: '/assets/sx/sx/views/vaohop.js',
  quanly: '/assets/sx/sx/views/quanly.js',
};
const CARD_PATHS = {
  xuatdau: '/assets/sx/sx/cards/xuatdau.js',
  nhapbot: '/assets/sx/sx/cards/nhapbot.js',
  baome: '/assets/sx/sx/cards/baome.js',
  baocan: '/assets/sx/sx/cards/baocan.js',
  suco: '/assets/sx/sx/cards/suco.js',
  vaohop: '/assets/sx/sx/cards/vaohop.js',
  chotngay: '/assets/sx/sx/cards/chotngay.js',
};
const VIEW_META = {
  ghiso: { label: 'Ghi số', icon: '📝' },
  vaohop: { label: 'Vào hộp', icon: '📦' },
  quanly: { label: 'Quản lý', icon: '📊' },
};

const views = (CTX.views && CTX.views.length) ? CTX.views : ['ghiso'];
const landing = CTX.landing || views[0];

const store = {
  boot: null,
  async refresh() {
    this.boot = await call('sx.api.portal.get_boot');
    return this.boot;
  },
};

// state phiếu ngày dùng chung cho các card cần gắn báo mẻ/cán/vào hộp
const dayState = { ngay: null };
async function ensureNgay() {
  if (dayState.ngay) return dayState.ngay;
  if (store.boot && store.boot.ngay_sx) { dayState.ngay = store.boot.ngay_sx; return dayState.ngay; }
  dayState.ngay = await call('sx.api.portal.get_or_create_ngay', {});
  return dayState.ngay;
}

async function mountCard(name, container) {
  const path = CARD_PATHS[name];
  if (!path) { return; } // card không có file (vd view standalone) → bỏ qua an toàn
  const mod = await import(withV(path));
  const wrap = el('div', 'sx-card-slot');
  container.appendChild(wrap);
  await mod.render(cardApi(wrap));
}

function cardApi(container) {
  return {
    container,
    boot: store.boot,
    ctx: CTX,
    call,
    ensureNgay,
    dayState,
    refresh: async () => { store.boot = null; dayState.ngay = null; router.go(router.currentRoute()); },
    reload: () => window.location.reload(),
  };
}

const app = document.getElementById('sx-app');

function buildShell() {
  app.innerHTML = '';
  const banner = el('div', 'sx-offline-banner');
  banner.textContent = 'Mất mạng — đang thử kết nối lại…';
  banner.style.display = 'none';
  const main = el('main', 'sx-main');
  const nav = el('nav', 'sx-bottom-nav');
  views.forEach((v) => {
    const meta = VIEW_META[v] || { label: v, icon: '•' };
    const btn = el('a', 'sx-nav-btn');
    btn.href = `#/${v}`;
    btn.dataset.route = `#/${v}`;
    btn.innerHTML = `<span class="sx-nav-icon">${meta.icon}</span><span>${meta.label}</span>`;
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

// đăng ký MỌI view (gate quyền trong renderView để route lạ → landing + toast,
// không cần reload); '#/' = landing cho hash rỗng
Object.keys(VIEW_PATHS).forEach((v) => {
  router.register(`#/${v}`, async (container) => renderView(v, container));
});
router.register('#/', async (container) => renderView(landing, container));

async function renderView(viewName, container) {
  if (!views.includes(viewName)) {
    toastErr('Bạn không có quyền vào màn hình này.');
    router.go(`#/${landing}`);
    return;
  }
  const mod = await import(withV(VIEW_PATHS[viewName]));
  const cards = (store.boot.viewCards && store.boot.viewCards[viewName]) || [];
  await mod.render({
    container,
    viewName,
    cards,
    mountCard,
    boot: store.boot,
    ctx: CTX,
    call,
    ensureNgay,
    dayState,
  });
}

router.onRender(async (route, loader) => {
  const viewName = route === '#/' ? landing : route.replace('#/', '');
  if (!views.includes(viewName)) { markActive(`#/${landing}`); }
  else { markActive(`#/${viewName}`); }
  main.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  try {
    if (!store.boot) await store.refresh();
    dayState.ngay = store.boot.ngay_sx || dayState.ngay;
    await loader(main);
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

// hash rỗng → landing
if (!window.location.hash || window.location.hash === '#/') {
  window.location.hash = `#/${landing}`;
}
router.start();
