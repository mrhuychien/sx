// Bàn số MỘT MÀN thùng / hộp + HSD (D153) — moSoHsd, dùng chung cho Nhập kho thành phẩm và Vào hộp Tết.
//
// Vì sao phải có bài này: đây là chỗ số đếm đi thẳng vào sổ kho và HSD thành hạn dùng của lô. Sai ở đây
// là sai lặng lẽ — tab thùng nhân nhầm hệ số, gõ đè mất số thủ kho đếm, HSD tự rơi về mặc định, hai dòng
// cùng một lô — không lỗi nào hiện ra, chỉ có tồn kho lệch hoặc phiếu tới tay thủ kho thì không duyệt được.
// Kèm luôn ba ca của bài openSoLuong cũ (D75): bảng quy đổi đổi sau lúc ghi phiếu thì TỔNG vẫn giữ nguyên.
//
// Nạp code THẬT: chép các module vào thư mục tạm, đổi đường dẫn /assets/... sang file tạm; modal / toast /
// quét thay bằng bản giả ghi lại lời gọi; DOM là bộ giả tối thiểu đọc innerHTML bằng regex (đủ cho #id,
// .class, [data-x]). Chép logic sang đây rồi test bản chép là test chính mình.
//
// Chạy: node scripts/test-sohsd.mjs   (verify.sh gọi sẵn)

import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

// ── DOM giả ────────────────────────────────────────────────────────────
class DsLop {
  constructor(e) { this.e = e; }
  add(...c) { c.forEach((x) => this.e._lop.add(x)); }
  remove(...c) { c.forEach((x) => this.e._lop.delete(x)); }
  contains(c) { return this.e._lop.has(c); }
  toggle(c, bat) {
    const on = bat === undefined ? !this.e._lop.has(c) : !!bat;
    if (on) this.e._lop.add(c); else this.e._lop.delete(c);
    return on;
  }
}

const lopRe = (c) => new RegExp(`\\bclass="(?:[^"]*\\s)?${c.replace(/[-]/g, '\\-')}(?:\\s[^"]*)?"`);
function khop(q, attrs) {
  if (q.startsWith('#')) return attrs.includes(`id="${q.slice(1)}"`);
  if (q.startsWith('.')) return lopRe(q.slice(1)).test(attrs);
  const m = q.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/);
  if (m) return m[2] === undefined ? new RegExp(`(^|\\s)${m[1]}="`).test(attrs) : attrs.includes(`${m[1]}="${m[2]}"`);
  throw new Error(`DOM giả chưa hiểu selector: ${q}`);
}
const camel = (s) => s.replace(/-([a-z])/g, (_, c) => c.toUpperCase());

class E {
  constructor(tag = 'div', lop = '') {
    this.tagName = String(tag).toUpperCase();
    this._lop = new Set(String(lop || '').split(/\s+/).filter(Boolean));
    this.classList = new DsLop(this);
    this.kids = []; this.nghe = {}; this.dataset = {}; this.style = {};
    this.textContent = ''; this.value = ''; this.disabled = false; this.type = '';
    this._html = ''; this._the = new Map();
  }
  get className() { return [...this._lop].join(' '); }
  set className(v) { this._lop = new Set(String(v || '').split(/\s+/).filter(Boolean)); }
  get innerHTML() { return this._html; }
  set innerHTML(h) {
    this._html = String(h); this._the = new Map(); this.kids = [];
    this.textContent = this._html.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
  }
  appendChild(x) { this.kids.push(x); return x; }
  addEventListener(ev, f) { (this.nghe[ev] = this.nghe[ev] || []).push(f); }
  focus() {}
  bam() { (this.nghe.click || []).forEach((f) => f({ currentTarget: this, target: this, preventDefault() {} })); }
  doi(v) { this.value = v; (this.nghe.change || []).forEach((f) => f({ target: this })); }
  querySelector(q) { return this.querySelectorAll(q)[0] || null; }
  // Một thẻ trong chuỗi HTML = MỘT phần tử, tìm bằng selector nào cũng ra nó (theo vị trí thẻ) — code
  // gắn listener qua selector này, test bấm qua selector khác vẫn trúng đúng phần tử.
  querySelectorAll(q) {
    const ra = [];
    const re = /<([a-z]+)\b([^>]*)>/gi;
    let m;
    while ((m = re.exec(this._html))) {
      const [, tag, attrs] = m;
      if (!khop(q, attrs)) continue;
      if (this._the.has(m.index)) { ra.push(this._the.get(m.index)); continue; }
      const e = new E(tag, (attrs.match(/\bclass="([^"]*)"/) || [])[1]);
      this._the.set(m.index, e);
      for (const a of attrs.matchAll(/\bdata-([\w-]+)="([^"]*)"/g)) e.dataset[camel(a[1])] = a[2];
      const id = attrs.match(/\bid="([^"]*)"/);
      if (id) e.id = id[1];
      const v = attrs.match(/\bvalue="([^"]*)"/);
      if (v) e.value = v[1];
      const mn = attrs.match(/\bmin="([^"]*)"/);
      if (mn) e.min = mn[1];
      const het = this._html.indexOf(`</${tag}>`, re.lastIndex);
      e._html = het >= 0 ? this._html.slice(re.lastIndex, het) : '';
      e.textContent = e._html.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
      ra.push(e);
    }
    return ra;
  }
}

globalThis.document = { createElement: (t) => new E(t) };
const kho = new Map();
globalThis.localStorage = { getItem: (k) => (kho.has(k) ? kho.get(k) : null), setItem: (k, v) => kho.set(k, String(v)) };

// ── modal / toast / quét giả ──────────────────────────────────────────
const MO = [];      // các cửa sổ đã mở — cái cuối là cái đang mở
const HOI = [];     // confirm2Step
const TOAST = [];
globalThis.__gia = {
  openModal: (o) => { const m = { ...o, body: new E('div'), dong: false, close() { m.dong = true; } }; MO.push(m); return m; },
  confirm2Step: (o) => { HOI.push(o); },
  toast: (s, k) => { TOAST.push([s, k]); },
  moQuet: () => {},
};

// ── nạp module thật ───────────────────────────────────────────────────
const GOC = 'sx/public/sx/';
const tam = mkdtempSync(join(tmpdir(), 'sx-sohsd-'));
const tep = (rel) => join(tam, `${rel.replace(/\//g, '__').replace(/\.js$/, '')}.mjs`);
const doiDuong = (src) => src.replace(/from '\/assets\/sx\/sx\/([^']+)'/g,
  (_, rel) => `from '${pathToFileURL(tep(rel)).href}'`);
for (const rel of ['lib/dom.js', 'lib/format.js', 'components/soluong.js', 'components/numpad.js',
  'cards/nhapkhotp.js', 'cards/vaohoptet.js', 'cards/kiemke.js']) {
  writeFileSync(tep(rel), doiDuong(readFileSync(GOC + rel, 'utf8')));
}
writeFileSync(tep('components/modal.js'), 'export const openModal = (o) => globalThis.__gia.openModal(o);\n'
  + 'export const confirm2Step = (o) => globalThis.__gia.confirm2Step(o);\n');
writeFileSync(tep('components/toast.js'), 'export const toast = (s, k) => globalThis.__gia.toast(s, k);\n'
  + "export const toastErr = (s) => globalThis.__gia.toast(s, 'err');\n");
writeFileSync(tep('components/quet.js'), 'export const moQuet = (o) => globalThis.__gia.moQuet(o);\n');
let NK; let TET; let KK;
try {
  NK = await import(pathToFileURL(tep('cards/nhapkhotp.js')).href);
  TET = await import(pathToFileURL(tep('cards/vaohoptet.js')).href);
  KK = await import(pathToFileURL(tep('cards/kiemke.js')).href);
} finally { rmSync(tam, { recursive: true, force: true }); }

// ── công cụ ───────────────────────────────────────────────────────────
let hong = 0;
function kiem(ten, dk, ct = '') {
  if (!dk) hong += 1;
  console.log(`  ${dk ? 'ok  ' : 'HỎNG'} ${ten}${!dk && ct !== '' ? ` — ${typeof ct === 'string' ? ct : JSON.stringify(ct)}` : ''}`);
}
const bang = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/** Điều khiển bàn số đang mở (cửa sổ cuối cùng). */
function pad(m = MO[MO.length - 1]) {
  const $ = (q) => m.body.querySelector(q);
  const phim = (k) => $('#sh-phim').kids.find((b) => b.textContent === k);
  return {
    m,
    la: () => !!$('#sh-phim'),
    go(chuoi) { for (const k of String(chuoi)) phim(k).bam(); },
    phim: (k) => phim(k).bam(),
    tab(i) { $('#sh-tab').querySelectorAll('[data-tab]')[i].bam(); },
    tabs: () => ($('#sh-tab') ? $('#sh-tab').querySelectorAll('[data-tab]').map((b) => b.textContent) : []),
    so: () => ($('#sh-so').innerHTML.match(/sx-numpad-value">([^<]*)</) || [])[1],
    don: () => ($('#sh-so').innerHTML.match(/sx-numpad-unit">([^<]*)</) || [])[1],
    goiY: () => ($('#sh-so').innerHTML.match(/sx-np-hint">([\s\S]*?)<\/div>/) || [])[1].trim(),
    hsd: () => $('#sh-hsd').value,
    minHsd: () => $('#sh-hsd').min,
    datHsd(v) { $('#sh-hsd').doi(v); },
    nhanh(t) { m.body.querySelectorAll('[data-thang]').find((b) => b.dataset.thang === String(t)).bam(); },
    macDinh() { $('#sh-md').bam(); },
    mdBat: () => !!$('#sh-md') && $('#sh-md').classList.contains('sx-np-chip-on'),
    coMd: () => !!$('#sh-md'),
    daCo: () => m.body.querySelectorAll('[data-daco]'),
    luu() { $('#sh-ok').bam(); },
    nutLuu: () => $('#sh-ok').textContent,
    loi: () => $('#sh-loi').textContent,
    canh: () => /sx-warn-text">⚠/.test(m.body.innerHTML),
    dong: () => m.dong,
  };
}

/** Bấm một nút phải MỞ một bàn số MỚI — bàn số cũ đã đóng vẫn còn closure, bấm vào nó vẫn "chạy" nên
 *  không kiểm cái này thì nút không gắn gì mà bài vẫn xanh. Trả bàn số mới (hoặc null). */
function moi(nut) {
  const truoc = MO.length;
  nut.bam();
  const m = MO[MO.length - 1];
  return MO.length > truoc && !m.dong && m.body.querySelector('#sh-phim') ? pad(m) : null;
}

const UOMS = [{ uom: 'Thùng', he_so: 12 }, { uom: 'Hộp', he_so: 1 }];
const CT255 = [{ uom: 'Thùng', sl: 21, he_so: 12 }, { uom: 'Hộp', sl: 3, he_so: 1 }];
const NGAY = '2026-10-09';

/** Mở moSoHsd trực tiếp; trả [bàn số, danh sách lần onOk]. */
function moTrucTiep(o) {
  const ra = [];
  NK.moSoHsd({ ten: 'Sen 300g', ngay: NGAY, macDinh: '2027-04-09', ...o, onOk: (...a) => ra.push(a) });
  return [pad(), ra];
}

// ═════════════════════════════════════════════════════════════════════
console.log('-- moSoHsd: tab thùng / hộp + HSD trên một màn --');
{
  const [p, ra] = moTrucTiep({ uoms: UOMS });
  kiem('dòng mới: hai tab Thùng / Hộp, bắt đầu ở Thùng, ô số trống',
    p.tabs().length === 2 && /^Thùng/.test(p.tabs()[0]) && p.don() === 'Số thùng' && p.so() === '0', p.tabs());
  kiem('ô HSD điền sẵn HSD mặc định, nút "mặc định" đang sáng', p.hsd() === '2027-04-09' && p.mdBat());
  kiem('ô HSD không cho chọn ngày ≤ ngày nhập (min = ngày + 1)', p.minHsd() === '2026-10-10', p.minHsd());
  p.luu();
  kiem('chưa gõ số → LƯU bị chặn, nói rõ thiếu gì', !ra.length && !p.dong() && p.loi() === 'Chưa nhập số thùng / hộp.', p.loi());
  p.go('2');
  p.tab(1);
  kiem('sang tab Hộp: tab Thùng giữ số 2 (· 24 hộp tính vào tổng)', /Thùng · 2/.test(p.tabs()[0]) && p.don() === 'Số hộp', p.tabs());
  p.go('3');
  kiem('tổng = 2 × 12 + 3 = 27, nút LƯU đọc ra tổng', /Tổng 27 hộp/.test(p.goiY()) && p.nutLuu() === 'LƯU · 27 HỘP',
    `${p.goiY()} | ${p.nutLuu()}`);
  p.luu();
  kiem('LƯU: onOk(27, chi tiết thùng + hộp, hsd null = đúng mặc định), bàn số đóng',
    p.dong() && bang(ra, [[27, [{ uom: 'Thùng', sl: 2, he_so: 12 }, { uom: 'Hộp', sl: 3, he_so: 1 }], null]]), ra);
}
{
  const [p, ra] = moTrucTiep({ uoms: UOMS, tong: 255 });
  kiem('có tổng, chưa có chi tiết → tự chia 21 thùng 3 hộp', /Thùng · 21/.test(p.tabs()[0]) && /Hộp · 3/.test(p.tabs()[1])
    && p.so() === '21', p.tabs());
  p.go('20');
  kiem('phím đầu tiên GHI ĐÈ số điền sẵn (21 → gõ 20 = 20, không phải 2120)', p.so() === '20' && /Tổng 243 hộp/.test(p.goiY()),
    `${p.so()} ${p.goiY()}`);
  p.tab(1);
  p.go('5');
  kiem('sang tab khác cũng ghi đè (3 → gõ 5 = 5)', p.so() === '5' && /Tổng 245 hộp/.test(p.goiY()), p.goiY());
  p.nhanh(3);
  kiem('nút +3T: HSD = ngày nhập + 3 tháng, nút "mặc định" tắt', p.hsd() === '2027-01-09' && !p.mdBat(), p.hsd());
  p.luu();
  kiem('HSD khác mặc định thì trả ra đúng ngày đó', bang(ra[0], [245, [{ uom: 'Thùng', sl: 20, he_so: 12 },
    { uom: 'Hộp', sl: 5, he_so: 1 }], '2027-01-09']), ra);
}
{
  const [p, ra] = moTrucTiep({ uoms: UOMS, tong: 24, hsd: '2027-01-09' });
  kiem('HSD đang có (khác mặc định) được điền vào ô', p.hsd() === '2027-01-09' && !p.mdBat());
  p.macDinh();
  kiem('bấm "mặc định" → về HSD mặc định', p.hsd() === '2027-04-09' && p.mdBat());
  p.luu();
  kiem('… và trả hsd null (dòng theo mặc định, đổi ngày phiếu thì đi theo)', ra.length === 1 && ra[0][2] === null, ra);
}
{
  const [p, ra] = moTrucTiep({ uoms: UOMS, macDinh: null });
  p.go('1');
  p.luu();
  kiem('mã chưa khai hạn dùng: ô HSD trống, không có nút "mặc định", LƯU bị chặn',
    !ra.length && !p.coMd() && p.hsd() === '' && /Chưa có HSD/.test(p.loi()), p.loi());
  p.datHsd(NGAY);
  p.luu();
  kiem('HSD = ngày nhập → chặn "HSD phải sau ngày nhập."', !ra.length && p.loi() === 'HSD phải sau ngày nhập.', p.loi());
  p.datHsd('2027-02-01');
  p.luu();
  kiem('HSD hợp lệ → lưu, trả đúng ngày gõ', bang(ra, [[12, [{ uom: 'Thùng', sl: 1, he_so: 12 }], '2027-02-01']]), ra);
}
{
  const [p, ra] = moTrucTiep({ uoms: [], dvt: 'Hộp', tong: 0 });
  kiem('mã một đơn vị: không có tab, ô số theo đơn vị kho', !p.tabs().length && p.don() === 'Số hộp');
  p.go('40');
  kiem('nút LƯU đọc tổng', p.nutLuu() === 'LƯU · 40 HỘP', p.nutLuu());
  p.luu();
  kiem('một đơn vị: chi tiết null', bang(ra, [[40, null, null]]), ra);
}
{
  const [p, ra] = moTrucTiep({ uoms: UOMS, tong: 36, chi_tiet: [{ uom: 'Thùng', sl: 3, he_so: 12 }], choPhepKhong: true });
  p.go('0');
  p.luu();
  kiem('sửa dòng (choPhepKhong): gõ 0 → lưu được số 0 (để bỏ dòng), không đòi HSD', bang(ra, [[0, null, null]]), ra);
}
{
  const [p, ra] = moTrucTiep({ uoms: UOMS, tong: 0 });
  p.go('0');
  p.luu();
  kiem('dòng mới: số 0 không lưu', !ra.length && /Chưa nhập số/.test(p.loi()));
}
{
  const [p, ra] = moTrucTiep({ uoms: UOMS, kiemLuu: (t, h) => (h === '2027-04-09' ? `trùng ${t}` : '') });
  p.go('1');
  p.luu();
  kiem('kiemLuu báo lỗi → giữ bàn số, hiện lỗi, không gọi onOk', !ra.length && !p.dong() && p.loi() === 'trùng 12', p.loi());
  p.nhanh(9);
  p.luu();
  kiem('đổi HSD hết trùng → lưu', ra.length === 1 && p.dong() && ra[0][2] === '2027-07-09', ra);
}
{
  let chon = null;
  const [p] = moTrucTiep({ uoms: UOMS, daCo: [{ nhan: 'HSD 09/01/27', so: 245 }], onDaCo: (i) => { chon = i; } });
  const ds = p.daCo();
  kiem('dòng khác của cùng mã hiện thành ô bấm, kèm số', ds.length === 1 && /HSD 09\/01\/27 · 245/.test(ds[0].textContent),
    ds.map((b) => b.textContent));
  ds[0].bam();
  kiem('bấm ô đó → đóng bàn số, gọi onDaCo(0)', p.dong() && chon === 0);
}

console.log('\n-- giữ đúng TỔNG khi bảng quy đổi đổi sau lúc ghi (ca cũ của openSoLuong, D75) --');
for (const [ten, uoms, mong] of [
  ['chi tiết khớp bảng quy đổi', UOMS, false],
  ['ĐVT bị đổi tên (Thùng → Két)', [{ uom: 'Két', he_so: 12 }, { uom: 'Hộp', he_so: 1 }], true],
  ['hệ số bị sửa (12 → 10)', [{ uom: 'Thùng', he_so: 10 }, { uom: 'Hộp', he_so: 1 }], true],
  ['xoá hẳn bậc Thùng (còn một ĐVT)', [{ uom: 'Hộp', he_so: 1 }], false],
]) {
  const [p, ra] = moTrucTiep({ uoms, chi_tiet: CT255, tong: 255, choPhepKhong: true });
  p.luu();
  kiem(`${ten}: LƯU không gõ gì vẫn ra 255, cảnh báo ${mong ? 'CÓ' : 'không'}`,
    ra.length === 1 && Math.abs(ra[0][0] - 255) < 1e-6 && p.canh() === mong, { ra, canh: p.canh() });
}

// ═════════════════════════════════════════════════════════════════════
console.log('\n-- Nhập kho: chọn sản phẩm → bàn số một màn --');
const DM = [
  { item: 'TP-SEN', ten: 'Sen 300g', dvt: 'Hộp', uoms: UOMS, han_dung_thang: 6, co_bom: true },
  { item: 'TP-DO', ten: 'Đỗ 200g', dvt: 'Hộp', uoms: [], han_dung: 90, co_bom: true },
];
const CT_DEM = [{ uom: 'Thùng', sl: 20, he_so: 12 }, { uom: 'Hộp', sl: 15, he_so: 1 }];   // = 255, đếm hộp lẻ riêng
function phieu(thuKho) {
  return {
    nhap: {
      name: 'PNK-0001', ngay: NGAY, duoc_duyet: thuKho, duoc_xoa: true, kho_dich: 'Kho TP', dong: [
        { item: 'TP-SEN', ten: 'Sen 300g', dvt: 'Hộp', so_lap: 255, so_dem: 255, lap_uom: CT255, dem_uom: CT255,
          lech: 0, hsd: null, hsd_goi_y: '2027-04-09', co_bom: true, xx_hsd: '', xx: null, vuot: 0 },
      ],
    },
    danh_muc: DM, cho_nhan: [], kho_tp: 'Kho TP',
  };
}
const GOI = [];
async function moNhapKho(r) {
  GOI.length = 0;
  const call = async (method, args) => {
    GOI.push([method, args]);
    if (method === 'sx.api.khotp.phieu_dang_mo') return r;
    if (method === 'sx.api.khotp.phieu_gan_day') return [];
    if (method === 'sx.api.khotp.sua_phieu') return { dong: [] };
    return {};
  };
  const c = new E('div');
  await NK.render({ container: c, call, refresh: () => {}, boot: { hom_nay: NGAY } });
  return c;
}
// Cửa sổ chọn sản phẩm đang mở: danh sách vẽ trong khung con #sx-cs-ds.
const chonSP = (item) => moi(MO[MO.length - 1].body.querySelector('#sx-cs-ds').querySelector(`[data-item="${item}"]`));
const guiLuu = () => JSON.parse((GOI.filter(([m]) => m === 'sx.api.khotp.sua_phieu').pop() || [])[1].rows);
const choRe = () => new Promise((r) => { setTimeout(r, 0); });

{
  const c = await moNhapKho(phieu(false));
  const box = c.querySelector('#sx-nk-rows');
  let p = moi(box.querySelectorAll('.sx-vh-sl')[0]);
  kiem('người lập bấm SỐ của dòng → bàn số "Sửa dòng" điền sẵn 21 thùng 3 hộp + HSD mặc định của dòng',
    p && p.m.kicker === 'Sửa dòng' && /Thùng · 21/.test(p.tabs()[0]) && p.hsd() === '2027-04-09' && p.mdBat(),
    p && p.m.kicker);
  p.go('20');
  p.tab(1);
  p.go('5');
  p.luu();
  c.querySelector('#sx-nk-luu').bam();
  await choRe();
  let g = guiLuu();
  kiem('lưu phiếu: số LẬP và số ĐẾM cùng = 245, chi tiết 20 thùng 5 hộp, HSD vẫn mặc định (null)',
    g.length === 1 && g[0].so_lap === 245 && g[0].so_dem === 245 && g[0].hsd === null
    && bang(g[0].lap_uom, [{ uom: 'Thùng', sl: 20, he_so: 12 }, { uom: 'Hộp', sl: 5, he_so: 1 }])
    && bang(g[0].dem_uom, g[0].lap_uom), g);

  p = moi(c.querySelector('#sx-nk-rows').querySelectorAll('[data-hsd]')[0]);
  kiem('bấm HSD của dòng → mở CÙNG bàn số (số đang có giữ nguyên)', p && /Thùng · 20/.test(p.tabs()[0])
    && /Hộp · 5/.test(p.tabs()[1]), p && p.tabs());
  p.nhanh(3);
  p.luu();
  c.querySelector('#sx-nk-luu').bam();
  await choRe();
  g = guiLuu();
  kiem('đổi HSD trên bàn số → dòng mang HSD đó, số không đổi', g[0].hsd === '2027-01-09' && g[0].so_dem === 245, g);

  c.querySelector('#sx-nk-tim').bam();
  p = chonSP('TP-SEN');
  kiem('TÌM SẢN PHẨM → chọn mã → vào THẲNG bàn số (không qua cửa sổ chọn dòng / HSD)', p
    && p.m.kicker === 'Thêm sản phẩm' && p.so() === '0', p && p.m.kicker);
  kiem('dòng HSD khác của mã hiện thành ô bấm "HSD 09/01/27 · 245"', p.daCo().length === 1
    && /HSD 09\/01\/27 · 245/.test(p.daCo()[0].textContent), p.daCo().map((b) => b.textContent));
  p.go('10');
  p.datHsd('2027-01-09');
  p.luu();
  kiem('lưu trùng HSD dòng đang có → chặn ngay trên bàn số (cùng mã + HSD là một lô)', !p.dong()
    && /đã có dòng HSD 09\/01\/27/.test(p.loi()), p.loi());
  p.macDinh();
  p.luu();
  c.querySelector('#sx-nk-luu').bam();
  await choRe();
  g = guiLuu();
  kiem('về HSD mặc định → thêm dòng thứ hai: 10 thùng = 120, HSD null', g.length === 2 && g[1].item === 'TP-SEN'
    && g[1].so_lap === 120 && g[1].hsd === null && bang(g[1].lap_uom, [{ uom: 'Thùng', sl: 10, he_so: 12 }]), g);

  c.querySelector('#sx-nk-tim').bam();
  p = chonSP('TP-SEN');
  kiem('chọn lại mã đã có dòng HSD mặc định → mở SỬA dòng đó (không đẻ dòng trùng lô)',
    p && p.m.kicker === 'Sửa dòng' && /Thùng · 10/.test(p.tabs()[0]) && p.daCo().length === 1, p && p.m.kicker);
  p = moi(p.daCo()[0]);
  kiem('bấm ô dòng kia → chuyển sang sửa dòng HSD 09/01/27', p && p.hsd() === '2027-01-09'
    && /Thùng · 20/.test(p.tabs()[0]), p && p.hsd());
  p.go('0');
  p.tab(1);
  p.go('0');
  p.luu();
  c.querySelector('#sx-nk-luu').bam();
  await choRe();
  g = guiLuu();
  kiem('sửa dòng về 0 → bỏ dòng', g.length === 1 && g[0].so_lap === 120, g);

  c.querySelector('#sx-nk-tim').bam();
  p = chonSP('TP-DO');
  kiem('mã một đơn vị: không tab, HSD mặc định = ngày + 90 ngày', p && !p.tabs().length && p.hsd() === '2027-01-07',
    p && p.hsd());
  p.go('40');
  p.luu();
  c.querySelector('#sx-nk-luu').bam();
  await choRe();
  g = guiLuu();
  kiem('thêm dòng Đỗ 40 hộp, chi tiết null', g.length === 2 && g[1].item === 'TP-DO' && g[1].so_dem === 40
    && g[1].lap_uom === null, g);
}
{
  const r = phieu(true);
  r.nhap.dong[0].dem_uom = CT_DEM;
  const c = await moNhapKho(r);
  const p = moi(c.querySelector('#sx-nk-rows').querySelectorAll('.sx-vh-sl')[0]);
  kiem('thủ kho bấm SỐ → "Số thủ kho đếm", có dòng phụ "phiếu ghi 255"', p && p.m.kicker === 'Số thủ kho đếm'
    && /phiếu ghi 255/.test(p.goiY()), p && `${p.m.kicker} | ${p.goiY()}`);
  kiem('… dựng ô từ cách chia CỦA CỘT ĐẾM (20 thùng 15 hộp), không phải cột lập / tự chia',
    /Thùng · 20/.test(p.tabs()[0]) && /Hộp · 15/.test(p.tabs()[1]), p.tabs());
  p.go('19');
  p.luu();
  c.querySelector('#sx-nk-duyet').bam();
  await choRe();
  const g = guiLuu();
  kiem('thủ kho sửa: chỉ số ĐẾM đổi (243), số người lập giữ 255 — chỗ lệch còn nguyên để xem',
    g[0].so_dem === 243 && g[0].so_lap === 255 && bang(g[0].lap_uom, CT255)
    && bang(g[0].dem_uom, [{ uom: 'Thùng', sl: 19, he_so: 12 }, { uom: 'Hộp', sl: 15, he_so: 1 }]), g);
  kiem('duyệt: lưu số trước rồi mới hỏi xác nhận', HOI.length > 0 && /243/.test(HOI[HOI.length - 1].message));
}
{
  const r = phieu(false);
  r.nhap = null;
  r.cho_nhan = [{ item: 'TP-SEN', ten: 'Sen 300g', dvt: 'Hộp', uoms: UOMS, con: 30, chia: [{ hsd: '2027-04-01', con: 30 }] }];
  const c = await moNhapKho(r);
  let p = moi(c.querySelector('[data-cn="TP-SEN"]'));
  kiem('chưa có phiếu, bấm mã "vừa vào hộp" → bàn số điền sẵn 2 thùng 6 hộp + HSD theo ngày đóng hộp',
    p && /Thùng · 2/.test(p.tabs()[0]) && /Hộp · 6/.test(p.tabs()[1]) && p.hsd() === '2027-04-01',
    p && `${p.tabs()} ${p.hsd()}`);
  kiem('… nút "mặc định" là HSD theo ngày đóng hộp (đang sáng)', p.mdBat());
  p.luu();
  await choRe();
  const tao = () => GOI.filter(([m]) => m === 'sx.api.khotp.tao_phieu_nhap').map(([, a]) => JSON.parse(a.rows));
  let rows = tao()[0];
  kiem('LƯU → lập phiếu kèm dòng: 30, chi tiết thùng / hộp, HSD theo ngày đóng hộp',
    rows && rows.length === 1 && rows[0].so_luong === 30 && rows[0].hsd === '2027-04-01'
    && bang(rows[0].chi_tiet, [{ uom: 'Thùng', sl: 2, he_so: 12 }, { uom: 'Hộp', sl: 6, he_so: 1 }]), rows);
  p = moi(c.querySelector('[data-cn="TP-SEN"]'));
  p.go('1');
  p.nhanh(9);
  p.luu();
  await choRe();
  rows = tao()[1];
  kiem('đổi số + HSD trên bàn số → phiếu lập theo đúng số + HSD vừa gõ (1 thùng 6 hộp = 18, HSD +9T)',
    rows && rows[0].so_luong === 18 && rows[0].hsd === '2027-07-09', rows);
}

// ═════════════════════════════════════════════════════════════════════
console.log('\n-- Vào hộp Tết: cùng bàn số --');
{
  const goi = [];
  const call = async (method, args) => {
    goi.push([method, args]);
    if (method === 'sx.api.tet.danh_muc') {
      return { rows: [{ item: 'TP-TET', ten: 'Hộp Tết Sen', dvt: 'Hộp', uoms: UOMS, han_dung_thang: 6 }],
        ma_quet: { sp: {} }, chua_co_nhom: false };
    }
    if (method === 'sx.api.tet.gan_day') return [];
    if (method === 'sx.api.tet.luu') return { phieu: 'PNK-0009', tong: 96 };
    return {};
  };
  const c = new E('div');
  await TET.render({ container: c, call, boot: { hom_nay: NGAY } });
  const chon = () => {
    c.querySelector('#tet-them').bam();
    return moi(MO[MO.length - 1].body.querySelector('#tet-ds-sp').querySelector('[data-item="TP-TET"]'));
  };
  let p = chon();
  kiem('THÊM HÀNG TẾT → chọn mã → bàn số một màn (kicker Vào hộp Tết, tab Thùng / Hộp, HSD mặc định)',
    /^Vào hộp Tết/.test(p.m.kicker) && p.tabs().length === 2 && p.hsd() === '2027-04-09', p.m.kicker);
  p.go('5');
  p.luu();
  p = chon();
  kiem('chọn lại mã đã có dòng HSD mặc định → mở sửa dòng đó (điền sẵn 5 thùng)', /Thùng · 5/.test(p.tabs()[0])
    && !p.daCo().length, p.tabs());
  p.nhanh(3);
  p.luu();
  p = chon();
  kiem('dòng đó đổi HSD → chọn lại mã là dòng MỚI, dòng kia hiện thành ô "HSD 09/01/27 · 60"',
    p.so() === '0' && p.daCo().length === 1 && /HSD 09\/01\/27 · 60/.test(p.daCo()[0].textContent),
    p.daCo().map((b) => b.textContent));
  p.go('3');
  p.datHsd('2027-01-09');
  p.luu();
  kiem('lưu trùng HSD dòng kia → chặn tại bàn số', !p.dong() && /đã có dòng HSD 09\/01\/27/.test(p.loi()), p.loi());
  p.macDinh();
  p.luu();
  p = chon();
  kiem('chọn lại mã → mở dòng HSD mặc định (3 thùng), dòng HSD 09/01/27 là ô bấm', p && /Thùng · 3/.test(p.tabs()[0])
    && p.daCo().length === 1, p && p.tabs());
  p = moi(p.daCo()[0]);
  kiem('bấm ô đó → chuyển sang bàn số của dòng HSD 09/01/27 (5 thùng)', p && p.hsd() === '2027-01-09'
    && /Thùng · 5/.test(p.tabs()[0]), p && p.hsd());
  p = moi(c.querySelector('#tet-dong').querySelectorAll('[data-hsd]')[0]);
  kiem('bấm HSD của dòng → bàn số của dòng đó, ô HSD là HSD của dòng (09/01/27)', p && p.hsd() === '2027-01-09'
    && /Thùng · 5/.test(p.tabs()[0]), p && p.hsd());
  c.querySelector('#tet-luu').bam();
  await HOI[HOI.length - 1].onConfirm();
  const luu = goi.find(([m]) => m === 'sx.api.tet.luu');
  const rows = luu && JSON.parse(luu[1].rows);
  kiem('LƯU: hai dòng hai lô — 60 (HSD 09/01/27) và 36 (HSD mặc định tính sẵn)', bang(rows, [
    { item: 'TP-TET', so: 60, chi_tiet: [{ uom: 'Thùng', sl: 5, he_so: 12 }], hsd: '2027-01-09' },
    { item: 'TP-TET', so: 36, chi_tiet: [{ uom: 'Thùng', sl: 3, he_so: 12 }], hsd: '2027-04-09' },
  ]), rows);
}

// ═════════════════════════════════════════════════════════════════════
console.log('\n-- Kiểm kê (D154): đếm bằng cùng bàn số --');
{
  const goi = [];
  const KH = { chot: false, loi: [] };
  const st = { phieu: null, dem: {} };
  const HANG = [
    { item: 'TP-SEN', ten: 'Bánh sen', dvt: 'Hộp', uoms: UOMS, so_sach: 180, chua_hsd: 150, thu_hoi: 0,
      theo_hsd: [{ hsd: '2027-06-08', so: 30 }], khong_lo: false },
    { item: 'TP-DO', ten: 'Bột đậu', dvt: 'Gói', uoms: [], so_sach: 40, chua_hsd: 40, thu_hoi: 0, theo_hsd: [],
      khong_lo: false },
  ];
  const tq = () => ({
    kho: 'Kho TP', duoc_chot: KH.chot, hom_nay: NGAY, phieu: st.phieu, danh_muc: [], gan_day: [], canh_bao: [],
    hang: HANG.map((h) => ({ ...h, da_dem: !!st.dem[h.item], dem: st.dem[h.item] || [],
      tong_dem: (st.dem[h.item] || []).reduce((a, x) => a + x.so, 0) })),
  });
  const call = async (m, a = {}) => {
    goi.push([m, a]);
    if (m === 'sx.api.kiemke.bat_dau') st.phieu = { name: 'KK-1', bat_dau_luc: '2026-10-09 08:15', duoc_huy: true };
    if (m === 'sx.api.kiemke.ghi') {
      const ds = (st.dem[a.item] || []).filter((x) => x.hsd);
      const i = a.hsd_cu ? ds.findIndex((x) => x.hsd === a.hsd_cu) : -1;
      if (Number(a.so_dem) <= 0) ds.splice(i, 1);
      else if (i >= 0) ds[i] = { hsd: a.hsd, so: Number(a.so_dem), chi_tiet: a.chi_tiet ? JSON.parse(a.chi_tiet) : null };
      else ds.push({ hsd: a.hsd, so: Number(a.so_dem), chi_tiet: a.chi_tiet ? JSON.parse(a.chi_tiet) : null });
      ds.sort((x, y) => (x.hsd < y.hsd ? -1 : 1));          // server xếp dòng theo HSD
      if (ds.length) st.dem[a.item] = ds; else delete st.dem[a.item];
    }
    if (m === 'sx.api.kiemke.het_hang') st.dem[a.item] = [{ hsd: null, so: 0 }];
    if (m === 'sx.api.kiemke.dem_lai') delete st.dem[a.item];
    if (m === 'sx.api.kiemke.xem_truoc') {
      return { name: 'KK-1', loi: KH.loi, canh_bao: [], duoc_chot: KH.chot,
        ma: [{ item: 'TP-SEN', ten: 'Bánh sen', so_sach: 180, dem: 120, chuyen: 120, lo_cu: 2, thieu: 60, thua: 0,
          bu_am: 0, thu_hoi: 0 }], tong: { so_ma: 1, so_sach: 180, dem: 120, phieu_kho: 2 } };
    }
    if (m === 'sx.api.kiemke.chot') { st.phieu = null; return { name: 'KK-1', so_ma: 1, tong_lech: -60, so_phieu_kho: 2 }; }
    return tq();
  };
  const loiGoi = (m) => goi.filter((g) => g[0] === m).pop();
  const c = new E('div');
  await KK.render({ container: c, call, boot: {} });
  kiem('chưa có phiếu: nhắc số mã còn hàng chưa ghi HSD + nút BẮT ĐẦU',
    /2 mã còn hàng chưa ghi HSD · 190/.test(c.innerHTML) && !!c.querySelector('#kk-bat'));
  c.querySelector('#kk-bat').bam();
  await choRe();
  kiem('BẮT ĐẦU → phiếu đang đếm, mã chưa đếm có nút + HSD / Không còn',
    !!c.querySelector('[data-them="0"]') && !!c.querySelector('[data-het="1"]'), c.innerHTML.slice(0, 200));
  let p = moi(c.querySelector('[data-them="0"]'));
  kiem('+ HSD → bàn số một màn: tab thùng / hộp, HSD KHÔNG điền sẵn (phải đọc trên hộp)',
    p && /^Kiểm kê · KK-1/.test(p.m.kicker) && p.tabs().length === 2 && p.hsd() === '', p && p.hsd());
  const chip = p.m.body.querySelectorAll('[data-hsdnhanh]');
  kiem('nút HSD nhanh = các HSD đang có trên sổ của mã; không có +3T…, không có "mặc định"',
    chip.length === 1 && chip[0].textContent === '08/06/27' && !p.m.body.querySelector('[data-thang]') && !p.coMd(),
    chip.map((b) => b.textContent));
  kiem('ô HSD không chặn ngày cũ (hàng hết hạn vẫn phải đếm)', p.minHsd() === undefined, p.minHsd());
  p.go('10');
  chip[0].bam();
  kiem('… bấm nút HSD nhanh điền đúng ngày', p.hsd() === '2027-06-08' && /phiếu|sổ 180/.test(p.goiY()), p.goiY());
  p.luu();
  await choRe();
  let g = loiGoi('sx.api.kiemke.ghi');
  kiem('LƯU → ghi(mã, HSD, 10 thùng = 120, chi tiết thùng / hộp), dòng mới không có hsd_cu',
    g && g[1].item === 'TP-SEN' && g[1].hsd === '2027-06-08' && g[1].so_dem === 120
    && g[1].chi_tiet === JSON.stringify([{ uom: 'Thùng', sl: 10, he_so: 12 }]) && !('hsd_cu' in g[1]), g && g[1]);
  p = moi(c.querySelector('[data-them="0"]'));
  kiem('mở + HSD lần nữa: dòng đã đếm hiện thành ô bấm, nút nhanh bỏ HSD đã đếm',
    p && p.daCo().length === 1 && !p.m.body.querySelectorAll('[data-hsdnhanh]').length, p && p.daCo().map((b) => b.textContent));
  p.go('1');
  p.datHsd('2027-06-08');
  p.luu();
  kiem('trùng HSD dòng đã đếm → chặn ngay trên bàn số', !p.dong() && /đã có dòng HSD 08\/06\/27/.test(p.loi()), p.loi());
  p.tab(1);
  p.go('5');
  p.datHsd('2026-01-01');
  p.luu();
  await choRe();
  g = loiGoi('sx.api.kiemke.ghi');
  kiem('HSD đã qua (hàng hết hạn trong kho) vẫn ghi được', g[1].hsd === '2026-01-01' && p.dong(), g[1]);
  kiem('dòng hết hạn hiện cờ "hết hạn"', /sx-kk-hethan/.test(c.innerHTML) && /hết hạn/.test(c.innerHTML));
  p = moi(c.querySelector('[data-sua="0:1"]'));       // dòng xếp theo HSD: 01/01/26 rồi 08/06/27
  kiem('bấm dòng đã đếm → bàn số của dòng đó (10 thùng, HSD 08/06/27)', p && /Thùng · 10/.test(p.tabs()[0])
    && p.hsd() === '2027-06-08', p && p.tabs());
  p.go('0');
  p.luu();
  await choRe();
  g = loiGoi('sx.api.kiemke.ghi');
  kiem('sửa về 0 → ghi số 0 kèm hsd_cu (server bỏ dòng)', g[1].so_dem === 0 && g[1].hsd_cu === '2027-06-08', g[1]);
  c.querySelector('[data-het="1"]').bam();
  await choRe();
  kiem('KHÔNG CÒN → het_hang(mã)', loiGoi('sx.api.kiemke.het_hang')[1].item === 'TP-DO'
    && /không còn hàng/.test(c.innerHTML));
  c.querySelector('[data-lai="1"]').bam();
  await choRe();
  kiem('ĐẾM LẠI → dem_lai(mã)', loiGoi('sx.api.kiemke.dem_lai')[1].item === 'TP-DO');
  const nhanTruoc = MO.length;
  c.querySelector('#kk-xem').bam();
  await choRe();
  let xm = MO[MO.length - 1];
  kiem('không được chốt (duoc_chot = false) XEM TRƯỚC: thấy kế hoạch, KHÔNG có nút chốt, nhắc báo người chốt',
    MO.length > nhanTruoc && /180 → 120/.test(xm.body.innerHTML) && !xm.body.kids.some((k) => k.textContent === 'CHỐT KIỂM KÊ')
    && xm.body.kids.some((k) => /báo thủ kho \/ quản lý/.test(k.textContent)), xm.body.kids.map((k) => k.textContent));
  KH.chot = true;
  KH.loi = ['Bánh sen: có chứng từ kho sau lúc đếm'];
  c.querySelector('#kk-xem').bam();
  await choRe();
  xm = MO[MO.length - 1];
  kiem('người chốt (thủ kho / quản lý) xem trước mà còn lỗi chặn → hiện lỗi, KHÔNG có nút chốt',
    /sau lúc đếm/.test(xm.body.innerHTML) && !xm.body.kids.some((k) => k.textContent === 'CHỐT KIỂM KÊ'));
  KH.loi = [];
  c.querySelector('#kk-xem').bam();
  await choRe();
  xm = MO[MO.length - 1];
  const nut = xm.body.kids.find((k) => k.textContent === 'CHỐT KIỂM KÊ');
  kiem('được chốt, không lỗi → có nút CHỐT KIỂM KÊ', !!nut);
  nut.bam();
  await HOI[HOI.length - 1].onConfirm();
  await choRe();
  kiem('CHỐT → xác nhận 2 bước rồi gọi chot(phiếu), thẻ về trạng thái chưa có phiếu',
    loiGoi('sx.api.kiemke.chot')[1].name === 'KK-1' && !!c.querySelector('#kk-bat')
    && TOAST.some(([t]) => /Đã chốt KK-1/.test(t)));
}

// ═════════════════════════════════════════════════════════════════════
console.log('\n-- Kiểm kê bán thành phẩm (D155): chọn kho, cân từng lô bằng bàn số kg --');
{
  /** Điều khiển bàn số openNumpad đang mở (cửa sổ cuối cùng). */
  function banSo(m = MO[MO.length - 1]) {
    const tat = (e) => [e, ...e.kids.flatMap(tat)];
    const all = () => tat(m.body);
    const grid = () => all().find((e) => e.classList.contains('sx-numpad-grid'));
    const man = () => all().find((e) => e.classList.contains('sx-numpad-display'));
    return {
      m,
      la: () => !!grid(),
      go(chuoi) { for (const k of String(chuoi)) grid().kids.find((b) => b.textContent === k).bam(); },
      so: () => (man().innerHTML.match(/sx-numpad-value">([^<]*)</) || [])[1],
      don: () => (man().innerHTML.match(/sx-numpad-unit">([^<]*)</) || [])[1],
      goiY: () => ((man().innerHTML.match(/sx-np-hint">([^<]*)</) || [])[1] || '').trim(),
      phim: () => grid().kids.map((b) => b.textContent),
      nut: (t) => all().find((e) => e.tagName === 'BUTTON' && e.textContent === t),
      dong: () => m.dong,
    };
  }
  function moiSo(nut) {
    const truoc = MO.length;
    nut.bam();
    const m = MO[MO.length - 1];
    const b = MO.length > truoc && !m.dong ? banSo(m) : null;
    return b && b.la() ? b : null;
  }
  const goi = [];
  const BTP = 'Bán thành phẩm';
  const KHO = [{ kho: 'Kho TP', loai: 'Thành phẩm', nhan: 'Thành phẩm' }, { kho: 'Kho BTP', loai: BTP, nhan: BTP },
    { kho: 'Kho Xuong', loai: BTP, nhan: 'Kho xưởng' }];
  const st = { kho: 'Kho TP', loai: 'Thành phẩm', phieu: null, can: {} };   // can: "mã|lô" → kg
  const LO = {
    'BOT-NEN': [{ batch: 'R-070926', so: 3, ngay: '2026-09-07', thu_hoi: true },
      { batch: 'R-011026', so: 40, ngay: '2026-10-01', thu_hoi: false },
      { batch: 'R-051026', so: 25.5, ngay: '2026-10-05', thu_hoi: false }],
    'DUONG-HOAN': [{ batch: null, so: 30, ngay: null, thu_hoi: false }],
  };
  const TEN = { 'BOT-NEN': 'Bột nền', 'DUONG-HOAN': 'Đường hoán' };
  const tq = () => {
    const chung = { kho: st.kho, loai: st.loai, cac_kho: KHO, duoc_chot: true, hom_nay: NGAY, gan_day: [] };
    if (st.loai !== BTP) return { ...chung, phieu: null, danh_muc: [], canh_bao: [], hang: [] };
    const hang = Object.entries(LO).map(([item, ls]) => {
      const lo = ls.map((l) => ({ ...l, can: st.can[`${item}|${l.batch}`] ?? null }));
      for (const [k, v] of Object.entries(st.can)) {
        const [it, b] = k.split('|');
        if (it === item && !lo.some((l) => String(l.batch) === b)) lo.push({ batch: b, so: 0, ngay: '2026-09-28', thu_hoi: false, can: v });
      }
      const xong = lo.filter((l) => l.can != null);
      return { item, ten: TEN[item], dvt: 'Kg', nhom: TEN[item], khong_lo: item === 'DUONG-HOAN', lo,
        le: item === 'BOT-NEN' ? 1.5 : 0, so_sach: lo.filter((l) => !l.thu_hoi).reduce((a, l) => a + l.so, 0),
        da_dem: xong.length > 0, tong_dem: xong.reduce((a, l) => a + l.can, 0),
        lech: xong.reduce((a, l) => a + l.can - l.so, 0), con_chua: lo.filter((l) => l.can == null && !l.thu_hoi).length };
    });
    return { ...chung, phieu: st.phieu, hang, canh_bao: ['1 ngày chưa chốt Vào hộp (08/10): bột đã vào hộp chưa trừ sổ.'],
      danh_muc: st.phieu ? [{ item: 'BOT-BANH', ten: 'Bột bánh sen', dvt: 'Kg', nhom: 'Bột bánh', khong_lo: false },
        { item: 'DUONG-MOI', ten: 'Đường hoán mới', dvt: 'Kg', nhom: 'Đường hoán', khong_lo: true }] : [] };
  };
  const call = async (m, a = {}) => {
    goi.push([m, a]);
    if (m === 'sx.api.kiemke.tong_quan' && a.kho) { st.kho = a.kho; st.loai = a.loai; }
    if (m === 'sx.api.kiemke.bat_dau') st.phieu = { name: 'KK-B1', bat_dau_luc: '2026-10-09 08:15', duoc_huy: true };
    if (m === 'sx.api.kiemke.ghi_lo') st.can[`${a.item}|${a.batch || null}`] = Number(a.so_dem);
    if (m === 'sx.api.kiemke.bo_lo') delete st.can[`${a.item}|${a.batch || null}`];
    if (m === 'sx.api.kiemke.dem_lai') Object.keys(st.can).filter((k) => k.startsWith(`${a.item}|`)).forEach((k) => delete st.can[k]);
    if (m === 'sx.api.kiemke.lo_khac') return [{ batch: 'R-280926', ngay: '2026-09-28' }];
    if (m === 'sx.api.kiemke.xem_truoc') {
      return { name: 'KK-B1', loai: BTP, loi: [], canh_bao: [], duoc_chot: true,
        ma: [{ item: 'BOT-NEN', ten: 'Bột nền', so_sach: 65.5, dem: 65.9, chuyen: 0, lo_cu: 0, thieu: 1.6, thua: 2,
          bu_am: 0, thu_hoi: 3, lo_can: 3 }], tong: { so_ma: 1, so_lo: 3, so_sach: 65.5, dem: 65.9, phieu_kho: 2 } };
    }
    if (m === 'sx.api.kiemke.chot') { st.phieu = null; st.can = {}; return { name: 'KK-B1', so_ma: 1, tong_lech: 0.4, so_phieu_kho: 2 }; }
    return tq();
  };
  const loiGoi = (m) => goi.filter((g) => g[0] === m).pop();
  kho.delete('sx-kk-kho');
  let c = new E('div');
  await KK.render({ container: c, call, boot: {} });
  const chip = c.querySelectorAll('[data-kho]');
  kiem('ba kho để chọn, máy chưa nhớ kho nào → mở Kho TP', chip.length === 3 && /sx-np-chip-on/.test(
    c.innerHTML.match(/<button[^>]*data-kho="0"[^>]*>/)[0]) && bang(goi[0], ['sx.api.kiemke.tong_quan', {}]),
  chip.map((b) => b.textContent));
  chip[1].bam();
  await choRe();
  kiem('chọn Bán thành phẩm → tải Kho BTP; màn chưa mở phiếu: số mã / lô trên sổ + cảnh báo chốt ngày',
    bang(loiGoi('sx.api.kiemke.tong_quan')[1], { kho: 'Kho BTP', loai: BTP })
    && /Kiểm kê kho bán thành phẩm/.test(c.innerHTML) && /2 mã · 3 lô trên sổ Kho BTP/.test(c.innerHTML)
    && /chưa chốt Vào hộp/.test(c.innerHTML), c.textContent.slice(0, 300));
  kiem('… máy nhớ kho vừa chọn', kho.get('sx-kk-kho') === JSON.stringify({ kho: 'Kho BTP', loai: BTP }), kho.get('sx-kk-kho'));
  c = new E('div');
  await KK.render({ container: c, call, boot: {} });
  kiem('mở lại thẻ → vào thẳng kho đã nhớ', bang(goi[goi.length - 1], ['sx.api.kiemke.tong_quan', { kho: 'Kho BTP', loai: BTP }])
    && /bán thành phẩm/.test(c.innerHTML));
  c.querySelector('#kk-bat').bam();
  await choRe();
  kiem('BẮT ĐẦU → mở phiếu cho đúng kho / loại', bang(loiGoi('sx.api.kiemke.bat_dau')[1], { kho: 'Kho BTP', loai: BTP }));
  kiem('đang cân: nhóm theo chuyền, mỗi lô một ô CÂN; lô thu hồi chỉ ghi, không bấm được; tồn không lô báo riêng',
    /sx-kk-nhom">Bột nền/.test(c.innerHTML) && /sx-kk-nhom">Đường hoán/.test(c.innerHTML)
    && !!c.querySelector('[data-lo="0:1"]') && !!c.querySelector('[data-lo="0:2"]') && !c.querySelector('[data-lo="0:0"]')
    && /R-070926 · thu hồi 3 kg/.test(c.innerHTML) && /1,5 kg tồn KHÔNG gắn lô/.test(c.innerHTML)
    && /Đã cân 0\/3 lô/.test(c.innerHTML), c.textContent.slice(0, 400));
  kiem('… + LÔ KHÁC cho mã có lô (không cho mã không lô); không có nút quét hộp; lọc ghi "Chưa cân"',
    !!c.querySelector('[data-lokhac="0"]') && !c.querySelector('[data-lokhac="1"]') && !c.querySelector('#kk-quet')
    && /Chưa cân <b>2/.test(c.innerHTML));
  let b = moiSo(c.querySelector('[data-lo="0:1"]'));
  kiem('bấm lô → bàn số kg có dấu phẩy, tên lô, sổ của lô', b && b.m.title === 'Lô R-011026' && /Bột nền$/.test(b.m.kicker)
    && b.don() === 'Cân thật · kg' && b.phim().includes(',') && b.goiY() === 'sổ 40' && !!b.nut('LÔ HẾT · 0'),
  b && [b.m.title, b.don(), b.goiY(), b.phim()]);
  b.go('38,4');
  kiem('… gõ 38,4 → đọc lại lệch ngay trên bàn số', b.so() === '38.4' && b.goiY() === 'sổ 40 · -1,6', [b.so(), b.goiY()]);
  b.nut('LƯU').bam();
  await choRe();
  kiem('LƯU → ghi_lo(mã, lô, 38,4)', bang(loiGoi('sx.api.kiemke.ghi_lo')[1],
    { name: 'KK-B1', item: 'BOT-NEN', batch: 'R-011026', so_dem: 38.4 }), loiGoi('sx.api.kiemke.ghi_lo'));
  kiem('… ô lô hiện số cân + lệch; tiến độ 1/3 lô, lệch -1,6 kg',
    /R-011026 · <b>38,4<\/b> kg <i>\(-1,6\)<\/i>/.test(c.innerHTML) && /Đã cân 1\/3 lô · lệch <span class="sx-kk-lech">-1,6 kg/.test(c.innerHTML),
  c.textContent.slice(0, 300));
  const nGhi = goi.filter((g) => g[0] === 'sx.api.kiemke.ghi_lo').length;
  b = moiSo(c.querySelector('[data-lo="0:2"]'));
  b.nut('LƯU').bam();
  await choRe();
  kiem('lô chưa cân: LƯU khi chưa gõ số → chặn (bấm nhầm là xoá cả lô), chỉ cách bấm LÔ HẾT',
    goi.filter((g) => g[0] === 'sx.api.kiemke.ghi_lo').length === nGhi && TOAST.some(([t, k]) => k === 'err' && /LÔ HẾT/.test(t)));
  b = moiSo(c.querySelector('[data-lo="0:2"]'));
  b.nut('LÔ HẾT · 0').bam();
  await choRe();
  kiem('LÔ HẾT → ghi_lo số 0; lô cân 0 vẫn là lô ĐÃ cân (2/3)', bang(loiGoi('sx.api.kiemke.ghi_lo')[1],
    { name: 'KK-B1', item: 'BOT-NEN', batch: 'R-051026', so_dem: 0 })
    && /R-051026 · <b>0<\/b> kg/.test(c.innerHTML) && /Đã cân 2\/3 lô/.test(c.innerHTML), c.textContent.slice(0, 200));
  b = moiSo(c.querySelector('[data-lo="0:1"]'));
  kiem('bấm lô đã cân → bàn số điền sẵn số cân, nút phụ BỎ SỐ CÂN', b && b.so() === '38.4' && !!b.nut('BỎ SỐ CÂN')
    && b.goiY() === 'sổ 40 · -1,6', b && [b.so(), b.goiY()]);
  b.nut('BỎ SỐ CÂN').bam();
  await choRe();
  kiem('BỎ SỐ CÂN → bo_lo(mã, lô); lô về chưa cân', bang(loiGoi('sx.api.kiemke.bo_lo')[1],
    { name: 'KK-B1', item: 'BOT-NEN', batch: 'R-011026' }) && /R-011026 <i>01\/10<\/i> · sổ 40 · <b>CÂN/.test(c.innerHTML),
  c.textContent.slice(0, 300));
  c.querySelector('[data-lokhac="0"]').bam();
  await choRe();
  let m = MO[MO.length - 1];
  const dsLo = m.body.querySelector('#kk-ds-lo');           // ô danh sách: vẽ lại sau khi tải xong
  kiem('+ LÔ KHÁC → danh sách lô của mã không có trên sổ', bang(loiGoi('sx.api.kiemke.lo_khac')[1],
    { name: 'KK-B1', item: 'BOT-NEN', tim: '' }) && !!dsLo.querySelector('[data-b="R-280926"]'), dsLo.innerHTML.slice(0, 200));
  // Mạng chậm: gõ tìm khi danh sách đầu chưa về — kết quả CŨ về sau không được đè kết quả mới.
  {
    let tra;
    const cham = async (mm, a = {}) => {
      if (mm === 'sx.api.kiemke.lo_khac' && !a.tim) { await new Promise((r) => { tra = r; }); return [{ batch: 'R-CU', ngay: '2026-09-01' }]; }
      if (mm === 'sx.api.kiemke.lo_khac') return [{ batch: 'R-250926', ngay: '2026-09-25' }];
      return call(mm, a);
    };
    const c2 = new E('div');
    await KK.render({ container: c2, call: cham, boot: {} });
    c2.querySelector('[data-lokhac="0"]').bam();
    const m2 = MO[MO.length - 1];
    const o2 = m2.body.querySelector('#kk-tim-lo');
    o2.value = '2509';
    (o2.nghe.input || []).forEach((f) => f({ target: o2 }));
    await new Promise((r) => { setTimeout(r, 320); });
    tra();
    await choRe();
    const ds2 = m2.body.querySelector('#kk-ds-lo');
    kiem('+ LÔ KHÁC, mạng chậm: danh sách cũ về sau không đè kết quả tìm mới',
      !!ds2.querySelector('[data-b="R-250926"]') && !ds2.querySelector('[data-b="R-CU"]'), ds2.innerHTML.slice(0, 200));
    m2.close();
  }
  b = moiSo(dsLo.querySelector('[data-b="R-280926"]'));
  kiem('… chọn lô → bàn số cân lô đó (sổ 0)', b && b.m.title === 'Lô R-280926' && b.goiY() === 'sổ 0' && m.dong);
  b.go('2');
  b.nut('LƯU').bam();
  await choRe();
  kiem('… LƯU → ghi_lo lô khác', bang(loiGoi('sx.api.kiemke.ghi_lo')[1], { name: 'KK-B1', item: 'BOT-NEN', batch: 'R-280926', so_dem: 2 }));
  b = moiSo(c.querySelector('[data-lo="1:0"]'));
  kiem('mã không lô: bàn số mang tên mã', b && b.m.title === 'Đường hoán (không lô)', b && b.m.title);
  b.go('31,25');
  b.nut('LƯU').bam();
  await choRe();
  kiem('… LƯU → ghi_lo không lô (batch rỗng), 31,25', bang(loiGoi('sx.api.kiemke.ghi_lo')[1],
    { name: 'KK-B1', item: 'DUONG-HOAN', batch: '', so_dem: 31.25 }));
  c.querySelector('#kk-them').bam();
  m = MO[MO.length - 1];
  b = moiSo(m.body.querySelector('#kk-ds-ma').querySelector('[data-ma="DUONG-MOI"]'));
  kiem('+ MÃ KHÁC → mã không lô: vào thẳng bàn số', b && b.m.title === 'Đường hoán mới (không lô)' && m.dong);
  c.querySelector('#kk-them').bam();
  m = MO[MO.length - 1];
  m.body.querySelector('#kk-ds-ma').querySelector('[data-ma="BOT-BANH"]').bam();
  await choRe();
  kiem('+ MÃ KHÁC → mã có lô: chọn lô trước', MO[MO.length - 1].kicker === 'Kiểm kê · Bột bánh sen'
    && loiGoi('sx.api.kiemke.lo_khac')[1].item === 'BOT-BANH');
  c.querySelector('[data-lai="0"]').bam();
  await choRe();
  kiem('CÂN LẠI cả mã → dem_lai(mã), báo đã bỏ số cân', loiGoi('sx.api.kiemke.dem_lai')[1].item === 'BOT-NEN'
    && TOAST.some(([t]) => /Đã bỏ số cân của Bột nền — cân lại mã này/.test(t)));
  c.querySelector('#kk-xem').bam();
  await choRe();
  const xm = MO[MO.length - 1];
  kiem('XEM TRƯỚC: kg, số lô cân, thiếu / thừa từng mã', /1 mã · 3 lô · sổ 65,5 → cân 65,9 kg · /.test(xm.body.innerHTML)
    && /3 lô · thiếu 1,6 kg · thừa 2 kg/.test(xm.body.innerHTML) && /Lô chưa cân giữ nguyên/.test(xm.body.innerHTML),
  xm.body.innerHTML.slice(0, 400));
  xm.body.kids.find((k) => k.textContent === 'CHỐT KIỂM KÊ').bam();
  kiem('… xác nhận chốt nói số lô', /1 mã, 3 lô: sổ 65,5 → cân 65,9 kg \(\+0,4\)/.test(HOI[HOI.length - 1].message),
    HOI[HOI.length - 1].message);
  await HOI[HOI.length - 1].onConfirm();
  await choRe();
  kiem('CHỐT → về đúng kho đang kiểm (không nhảy sang Kho TP)', bang(loiGoi('sx.api.kiemke.tong_quan')[1], { kho: 'Kho BTP', loai: BTP })
    && !!c.querySelector('#kk-bat') && /bán thành phẩm/.test(c.innerHTML)
    && TOAST.some(([t]) => /Đã chốt KK-B1: 1 mã, lệch \+0,4 kg, 2 chứng từ kho/.test(t)));
  kho.set('sx-kk-kho', JSON.stringify({ kho: 'Kho Cu', loai: BTP }));
  const loiKho = async (mm, a = {}) => {
    if (mm === 'sx.api.kiemke.tong_quan' && a.kho === 'Kho Cu') throw new Error('Không kiểm kê kho Kho Cu ở đây.');
    return call(mm, a);
  };
  c = new E('div');
  await KK.render({ container: c, call: loiKho, boot: {} });
  kiem('kho đã nhớ không còn (đổi cấu hình) → về kho mặc định, không treo thẻ', !!c.querySelector('#kk-bat')
    && bang(goi[goi.length - 1], ['sx.api.kiemke.tong_quan', {}]), c.textContent.slice(0, 200));
  kho.delete('sx-kk-kho');
}

console.log(hong ? `SOHSD-FAIL (${hong} ca)` : 'SOHSD-OK');
process.exit(hong ? 1 : 0);
