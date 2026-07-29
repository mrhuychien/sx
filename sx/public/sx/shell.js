// Shell portal /sx (v3) — hash router, nav theo views, view lắp từ CARDS.
// Card-based: view render bằng mountCard(name) → dynamic import card (withV).

import { call, onOffline } from '/assets/sx/sx/lib/api.js';
import { el } from '/assets/sx/sx/lib/dom.js';
import * as router from '/assets/sx/sx/lib/router.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';

const BUILD = 'sx-20';
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
  luutrinh: '/assets/sx/sx/cards/luutrinh.js',
  luutrinhbtp: '/assets/sx/sx/cards/luutrinhbtp.js',
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
  ngayXem: null,   // null = hôm nay (D25)
  async refresh() {
    this.boot = await call('sx.api.portal.get_boot', this.ngayXem ? { ngay: this.ngayXem } : {});
    this.ngayXem = this.boot.ngay_xem || null;
    return this.boot;
  },
};

// state phiếu ngày dùng chung cho các card cần gắn báo mẻ/cán/vào hộp
const dayState = { ngay: null };
async function ensureNgay() {
  if (dayState.ngay) return dayState.ngay;
  if (store.boot && store.boot.ngay_sx) { dayState.ngay = store.boot.ngay_sx; return dayState.ngay; }
  const ng = (store.boot && store.boot.ngay_xem) ? { ngay: store.boot.ngay_xem } : {};
  dayState.ngay = await call('sx.api.portal.get_or_create_ngay', ng);
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
    doiNgay,
  };
}

const app = document.getElementById('sx-app');

function buildShell() {
  app.innerHTML = '';
  const banner = el('div', 'sx-offline-banner');
  banner.setAttribute('role', 'status');
  banner.textContent = 'Mất mạng — đang thử kết nối lại…';
  banner.style.display = 'none';
  const main = el('main', 'sx-main');
  const daybar = el('div', 'sx-daybar');
  daybar.innerHTML = `
    <button type="button" class="sx-day-nav" id="sx-day-prev"
            aria-label="Ngày trước" title="Ngày trước">◀</button>
    <input type="date" class="sx-day-input" id="sx-day-input" aria-label="Chọn ngày xem">
    <button type="button" class="sx-day-nav" id="sx-day-next"
            aria-label="Ngày sau" title="Ngày sau">▶</button>
    <button type="button" class="sx-day-today" id="sx-day-today">Hôm nay</button>
    <span class="sx-day-tag" id="sx-day-tag"></span>
  `;
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
  app.appendChild(daybar);
  app.appendChild(main);
  app.appendChild(nav);
  onOffline((isOff) => { banner.style.display = isOff ? '' : 'none'; });

  daybar.querySelector('#sx-day-input').addEventListener('change', (e) => {
    if (e.target.value) doiNgay(e.target.value);
  });
  daybar.querySelector('#sx-day-prev').addEventListener('click', () => doiNgay(dichNgay(-1)));
  daybar.querySelector('#sx-day-next').addEventListener('click', () => doiNgay(dichNgay(1)));
  daybar.querySelector('#sx-day-today').addEventListener('click', () => doiNgay(null));
  return { main, nav, daybar };
}

// Ngày làm việc = chuỗi ISO "YYYY-MM-DD", KHÔNG dùng Date để tránh lệch múi giờ
function dichNgay(buoc) {
  const goc = (store.boot && store.boot.ngay_xem) || (store.boot && store.boot.hom_nay);
  if (!goc) return null;
  const [y, m, d] = goc.split('-').map(Number);
  const t = new Date(Date.UTC(y, m - 1, d));
  t.setUTCDate(t.getUTCDate() + buoc);
  return t.toISOString().slice(0, 10);
}

function doiNgay(iso) {
  store.ngayXem = iso;       // null = quay về hôm nay
  store.boot = null;
  dayState.ngay = null;
  router.go(router.currentRoute());
}

function paintDayBar() {
  const b = store.boot || {};
  const input = daybar.querySelector('#sx-day-input');
  const tag = daybar.querySelector('#sx-day-tag');
  if (input && b.ngay_xem) input.value = b.ngay_xem;
  if (!tag) return;
  const daChot = b.ngay_sx && b.ngay_sx.docstatus === 1;
  if (daChot) { tag.textContent = '🔒 đã chốt'; tag.className = 'sx-day-tag sx-day-chot'; }
  else if (b.la_hom_nay) { tag.textContent = ''; tag.className = 'sx-day-tag'; }
  else { tag.textContent = '✎ ngày cũ'; tag.className = 'sx-day-tag sx-day-cu'; }
}

const { main, nav, daybar } = buildShell();

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
    paintDayBar();
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
