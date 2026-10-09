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
  set innerHTML(h) { this._html = String(h); this._the = new Map(); this.kids = []; }
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
  'cards/nhapkhotp.js', 'cards/vaohoptet.js']) {
  writeFileSync(tep(rel), doiDuong(readFileSync(GOC + rel, 'utf8')));
}
writeFileSync(tep('components/modal.js'), 'export const openModal = (o) => globalThis.__gia.openModal(o);\n'
  + 'export const confirm2Step = (o) => globalThis.__gia.confirm2Step(o);\n');
writeFileSync(tep('components/toast.js'), 'export const toast = (s, k) => globalThis.__gia.toast(s, k);\n'
  + "export const toastErr = (s) => globalThis.__gia.toast(s, 'err');\n");
writeFileSync(tep('components/quet.js'), 'export const moQuet = (o) => globalThis.__gia.moQuet(o);\n');
let NK; let TET;
try {
  NK = await import(pathToFileURL(tep('cards/nhapkhotp.js')).href);
  TET = await import(pathToFileURL(tep('cards/vaohoptet.js')).href);
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

console.log(hong ? `SOHSD-FAIL (${hong} ca)` : 'SOHSD-OK');
process.exit(hong ? 1 : 0);
