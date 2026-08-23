// Shell portal /sx (v3) — hash router, nav theo views, view lắp từ CARDS.
// Card-based: view render bằng mountCard(name) → dynamic import card (withV).

import { call, guiHangCho, onOffline, onQueue } from '/assets/sx/sx/lib/api.js';
import { el } from '/assets/sx/sx/lib/dom.js';
import * as router from '/assets/sx/sx/lib/router.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';
import { apDungMua, iconMua, moChonMua } from '/assets/sx/sx/components/mua.js';

const BUILD = 'sx-52';
const CTX = window.SX_CONTEXT || {};
window.SX_APP = { build: BUILD };

function withV(path) {
  return `${path}?v=${encodeURIComponent(CTX.assetVersion || Date.now())}`;
}

const VIEW_PATHS = {
  ghiso: '/assets/sx/sx/views/ghiso.js',
  vaohop: '/assets/sx/sx/views/vaohop.js',
  nhapkho: '/assets/sx/sx/views/nhapkho.js',
  quanly: '/assets/sx/sx/views/quanly.js',
};
const CARD_PATHS = {
  xuatdau: '/assets/sx/sx/cards/xuatdau.js',
  luutrinh: '/assets/sx/sx/cards/luutrinh.js',
  luutrinhbtp: '/assets/sx/sx/cards/luutrinhbtp.js',
  nhapkhotp: '/assets/sx/sx/cards/nhapkhotp.js',
  baome: '/assets/sx/sx/cards/baome.js',
  baocan: '/assets/sx/sx/cards/baocan.js',
  suco: '/assets/sx/sx/cards/suco.js',
  vaohop: '/assets/sx/sx/cards/vaohop.js',
  chotngay: '/assets/sx/sx/cards/chotngay.js',
};
const VIEW_META = {
  ghiso: { label: 'Ghi số', icon: '📋' },
  vaohop: { label: 'Ghi hộp', icon: '📦' },
  nhapkho: { label: 'Nhập kho', icon: '🏭' },
  quanly: { label: 'Quản lý', icon: '📊' },
};

const views = (CTX.views && CTX.views.length) ? CTX.views : ['ghiso'];
const landing = CTX.landing || views[0];

// Bản boot lưu trên máy (D37): danh mục công nhân / loại công việc / item đổi rất ít,
// nên mất mạng vẫn dựng được form để nhập. Có mạng thì luôn lấy bản tươi.
const BOOT_KEY = 'sx-boot-v1';

function luuBoot(ngay, boot) {
  try {
    localStorage.setItem(BOOT_KEY, JSON.stringify({ ngay: ngay || null, boot, luc: Date.now() }));
  } catch (e) { /* hết chỗ -> bỏ qua, chỉ mất tiện nghi offline */ }
}

function docBoot(ngay) {
  try {
    const d = JSON.parse(localStorage.getItem(BOOT_KEY) || 'null');
    if (!d || !d.boot) return null;
    // Chỉ dùng lại khi ĐÚNG ngày đang xem: số liệu của ngày khác là số sai, thà
    // báo không tải được còn hơn cho QC nhìn số của hôm qua mà tưởng hôm nay.
    if ((d.ngay || null) !== (ngay || null)) return null;
    return d.boot;
  } catch (e) {
    return null;
  }
}

const store = {
  boot: null,
  ngayXem: null,   // null = hôm nay (D25)
  tuBoNho: false,  // boot đang là bản lưu trên máy?
  async refresh() {
    const ngay = this.ngayXem;
    try {
      this.boot = await call('sx.api.portal.get_boot', ngay ? { ngay } : {});
      this.tuBoNho = false;
      luuBoot(this.boot.ngay_xem || null, this.boot);
    } catch (e) {
      const cu = e.mat_mang ? docBoot(ngay) : null;
      if (!cu) throw e;
      this.boot = cu;
      this.tuBoNho = true;
    }
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
  // Mùa gắn lên #sx-app (KHÔNG lên body — body là của ERPNext, đổi ở đó là đụng
  // vào mọi trang khác của site)
  apDungMua(app);

  // Header kính mờ cố định: tên màn đang mở bên trái, nút phụ bên phải.
  // Làm mới ĐỂ TRÊN CÙNG vì đây là app số liệu — nghi số cũ thì bấm một cái là
  // biết, không phải đi tìm chỗ tải lại.
  const header = el('header', 'sx-header');
  header.innerHTML = `
    <div class="sx-header-inner">
      <div class="sx-header-title" id="sx-head-title">Sản xuất RVHG</div>
      <div class="sx-header-actions">
        <button type="button" class="sx-icon-btn" id="sx-head-refresh"
                aria-label="Làm mới số liệu" title="Làm mới">↻</button>
        <button type="button" class="sx-icon-btn" id="sx-head-mua"
                aria-label="Đổi mùa giao diện" title="Đổi mùa">${iconMua()}</button>
      </div>
    </div>`;
  header.querySelector('#sx-head-refresh').addEventListener('click', () => {
    store.boot = null;
    dayState.ngay = null;
    router.go(router.currentRoute());
  });
  const nutMua = header.querySelector('#sx-head-mua');
  nutMua.addEventListener('click', () => moChonMua(app, (ma) => {
    nutMua.textContent = iconMua(ma);
  }));

  const banner = el('div', 'sx-offline-banner');
  banner.setAttribute('role', 'status');
  banner.textContent = 'Mất mạng — đang thử kết nối lại…';
  banner.style.display = 'none';
  const main = el('main', 'sx-main');
  const daybar = el('div', 'sx-daybar');
  // Nút ◀ ▶ hai đầu, ô ngày + trạng thái xếp giữa. Bọc thêm một lớp inner để
  // trên máy tính thanh ngày căn giữa cùng dải với nội dung.
  daybar.innerHTML = `
    <div class="sx-daybar-inner">
    <button type="button" class="sx-day-nav" id="sx-day-prev"
            aria-label="Ngày trước" title="Ngày trước">◀</button>
    <button type="button" class="sx-day-mid" id="sx-day-open" aria-label="Chọn ngày xem">
      <span class="sx-day-ten" id="sx-day-ten">—</span>
      <span class="sx-day-tag" id="sx-day-tag"></span>
      <input type="date" class="sx-day-input" id="sx-day-input" tabindex="-1" aria-hidden="true">
    </button>
    <button type="button" class="sx-day-nav" id="sx-day-next"
            aria-label="Ngày sau" title="Ngày sau">▶</button>
    <button type="button" class="sx-day-today" id="sx-day-today">Hôm nay</button>
    </div>
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
  // Thanh hàng chờ: luôn nói rõ còn bao nhiêu thao tác chưa gửi được (D37).
  // Im lặng ở đây là tệ nhất — QC phải biết số mình gõ đã lên server chưa.
  const hang = el('div', 'sx-queue-banner');
  hang.setAttribute('role', 'status');
  hang.style.display = 'none';

  app.appendChild(header);
  app.appendChild(banner);
  app.appendChild(hang);
  app.appendChild(daybar);
  app.appendChild(main);
  app.appendChild(nav);
  onOffline((isOff) => { banner.style.display = isOff ? '' : 'none'; });

  onQueue((tt) => {
    if (!tt.so_luong) { hang.style.display = 'none'; return; }
    hang.style.display = '';
    hang.classList.toggle('sx-queue-loi', tt.loi > 0);
    hang.innerHTML = `
      <span title="${tt.loi
        ? `${tt.loi} thao tác server TỪ CHỐI, ${tt.so_luong - tt.loi} đang chờ gửi`
        : `${tt.so_luong} thao tác đã lưu trên máy, đang chờ có mạng`}">${tt.loi
        ? `⚠ ${tt.loi} bị từ chối · ${tt.so_luong - tt.loi} chờ gửi`
        : `💾 ${tt.so_luong} thao tác chờ gửi`}</span>
      <button type="button" class="sx-queue-btn" id="sx-queue-go">GỬI LẠI</button>`;
    hang.querySelector('#sx-queue-go').addEventListener('click', async (e) => {
      e.currentTarget.disabled = true;
      const kq = await guiHangCho();
      if (kq.da_gui) { store.boot = null; router.go(router.currentRoute()); }
      e.currentTarget.disabled = false;
    });
  });

  // Mở app là thử gửi lại ngay — QC mở lại tab sau khi về vùng có wifi
  guiHangCho();

  daybar.querySelector('#sx-day-input').addEventListener('change', (e) => {
    if (e.target.value) doiNgay(e.target.value);
  });
  daybar.querySelector('#sx-day-prev').addEventListener('click', () => doiNgay(dichNgay(-1)));
  daybar.querySelector('#sx-day-next').addEventListener('click', () => doiNgay(dichNgay(1)));
  daybar.querySelector('#sx-day-today').addEventListener('click', () => doiNgay(null));
  // Bấm cả khối ngày để mở lịch — vùng chạm rộng hơn hẳn ô date bé tí
  daybar.querySelector('#sx-day-open').addEventListener('click', (e) => {
    if (e.target.id === 'sx-day-input') return;
    const inp = daybar.querySelector('#sx-day-input');
    if (inp.showPicker) inp.showPicker(); else inp.focus();
  });
  return { main, nav, daybar, header };
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
  const ng = b.ngay_sx || {};
  const daChot = ng.docstatus === 1 || (ng.chot_ghiso && ng.chot_vaohop);
  const chotMotPhan = !daChot && (ng.chot_ghiso || ng.chot_vaohop);
  // "Thứ 5, 30/07" — người ở xưởng nhớ THỨ, không nhớ ngày (bản thiết kế)
  const tenNgay = daybar.querySelector('#sx-day-ten');
  if (tenNgay && b.ngay_sx && b.ngay_sx.ngay) {
    const [y, mo, d] = String(b.ngay_sx.ngay).split('-').map(Number);
    const THU = ['Chủ nhật', 'Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7'];
    const dt = new Date(Date.UTC(y, mo - 1, d));
    tenNgay.textContent = `${THU[dt.getUTCDay()]}, ${String(d).padStart(2, '0')}/${String(mo).padStart(2, '0')}`;
  }

  // Số liệu từ bản lưu trên máy phải NÓI RA: có thể đã cũ so với server (D37)
  if (store.tuBoNho) {
    tag.textContent = '📴 số liệu lưu trên máy';
    tag.className = 'sx-day-tag sx-day-cu';
  } else if (daChot) { tag.textContent = '🔒 đã chốt'; tag.className = 'sx-day-tag sx-day-chot'; }
  else if (chotMotPhan) {
    // Nói rõ NỬA NÀO đã chốt: "đã chốt" chung chung làm QC tưởng cả ngày xong rồi
    tag.textContent = ng.chot_ghiso ? '🔒 xong Ghi sổ' : '🔒 xong Vào hộp';
    tag.className = 'sx-day-tag sx-day-chot';
  }
  else if (b.la_hom_nay) { tag.textContent = ''; tag.className = 'sx-day-tag'; }
  else { tag.textContent = '✎ ngày cũ'; tag.className = 'sx-day-tag sx-day-cu'; }
}

const { main, nav, daybar, header } = buildShell();

function markActive(route) {
  nav.querySelectorAll('.sx-nav-btn').forEach((b) => {
    b.classList.toggle('sx-nav-active', b.dataset.route === route);
  });
  // Header nói ĐANG Ở ĐÂU. Trên điện thoại thanh tab dưới bị ngón tay che nửa,
  // nên tên màn phải có ở trên cùng nữa.
  const meta = VIEW_META[route.replace('#/', '')];
  const t = header.querySelector('#sx-head-title');
  if (t) t.textContent = meta ? `${meta.icon} ${meta.label}` : 'Sản xuất RVHG';
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
  // Màn Quản lý là màn ĐỌC trên máy tính (không phải nhập liệu trên tablet) nên
  // được nới rộng và chia 2 cột; hai màn kia giữ dải hẹp cho dễ đọc khi cầm tay.
  container.classList.toggle('sx-main-rong', viewName === 'quanly');
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
