// D208 — thẻ Sổ nợ BOM / Sổ nợ đơn giá / Nợ vào hộp / Lô cũ chưa có HSD GẬP sẵn, bấm mới xổ danh sách.
//
// Vì sao phải có bài này: gập sai thì hỏng im lặng theo hai hướng —
//   · thẻ gập mà dòng tóm tắt không nói gì gấp (mã hạch toán bù / áp giá được ngay, nợ quá lâu) → không ai
//     mở ra nữa, nợ nằm đó mãi;
//   · đang làm dở trong thẻ (Bỏ qua, + Lô đã hết hàng, Ghi cho công khoán) mà thẻ vẽ lại tự GẬP → mất chỗ,
//     tưởng thao tác không ăn.
// Chromium thật + CSS thật (shell.css): bấm thật, đo chiều cao, đọc lời gọi API.
// Chạy: node scripts/test-gapno.mjs   (verify.sh gọi sẵn)

import { existsSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, join, resolve, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const GOC = resolve(dirname(fileURLToPath(import.meta.url)), '..');
let hong = 0;
const kiem = (ten, dk, ct = '') => {
  if (!dk) hong += 1;
  console.log(`  ${dk ? 'ok  ' : 'HỎNG'} ${ten}${ct ? ` — ${ct}` : ''}`);
};

const CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PW = '/opt/node22/lib/node_modules/playwright/index.js';
if (!existsSync(CHROME) || !existsSync(PW)) {
  console.log('-- trình duyệt thật: BỎ QUA (máy này không có Chromium) --');
  console.log('GAPNO-OK');
  process.exit(0);
}

const PUB = join(GOC, 'sx/public/sx');
const TRANG = `<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="/assets/sx/sx/shell.css">
<body><div class="sx-app"><div class="sx-view" id="khung">
  <div id="bom"></div><div id="gia"></div><div id="vh"></div><div id="lo"></div></div></div>
<script type="module">
import * as BOM from '/assets/sx/sx/cards/nobom.js';
import * as GIA from '/assets/sx/sx/cards/nogia.js';
import * as VH from '/assets/sx/sx/cards/novaohop.js';
import * as LO from '/assets/sx/sx/cards/lohsd.js';
window.CALLS = [];
window.REFRESH = 0;
const call = async (m, a) => {
  window.CALLS.push([m, a]);
  const D = window.DL;
  if (m === 'sx.api.khotp.so_no_bom') return structuredClone(D.bom);
  if (m === 'sx.api.nogia.so_no_gia') return structuredClone(D.gia);
  if (m === 'sx.api.khotp.so_no_vao_hop') return structuredClone(D.vh);
  if (m === 'sx.api.lohsd.danh_sach') return structuredClone(a.ca_het_hang ? D.lo_ca : D.lo);
  if (m === 'sx.api.khotp.bo_qua_no') {
    D.bom.nhom.forEach((g) => { g.dong = g.dong.filter((d) => d.name !== a.name); });
    D.bom.nhom = D.bom.nhom.filter((g) => g.dong.length);
    D.bom.tong_dong = D.bom.nhom.reduce((s, g) => s + g.dong.length, 0);
    return {};
  }
  if (m === 'sx.api.khotp.ghi_no_khoan_chung') return { so_hop: a.so_hop, ten: 'Bánh sen', thanh_tien: 30000 };
  return {};
};
const MOD = { bom: BOM, gia: GIA, vh: VH, lo: LO };
const ngay = { name: 'N1', ngay: '2026-10-14', docstatus: 0 };
const boot = { ngay_xem: '2026-10-14', la_hom_nay: true, ngay_sx: ngay };
// Vẽ (lại) một thẻ vào ô MỚI — như shell gắn thẻ khi mở màn / vẽ lại cả màn.
window.ve = async (k) => {
  const cu = document.getElementById(k);
  const c = document.createElement('div');
  c.id = k;
  cu.replaceWith(c);
  await MOD[k].render({ container: c, call, boot, ensureNgay: async () => ngay,
    refresh: () => { window.REFRESH += 1; } });
};
window.SAN_SANG = true;
</script>`;

const dongBom = (n, goc) => Array.from({ length: n }, (_, i) => ({
  name: `${goc}-${i + 1}`, ngay: `2026-10-${String(2 + i).padStart(2, '0')}`, so_luong: 20 + i,
  phieu_nhap: `PN-${goc}-${i + 1}`, batch: `L${i + 1}` }));
const DL = {
  bom: { tong_dong: 16, duoc_xu_ly: true, ngay_no_lau: 7, nhom: [
    // TP-A nợ đã lâu nhưng ĐÃ có BOM: tính vào "làm được ngay", không vào "nợ quá hạn" (như dòng meta cũ)
    { item: 'TP-A', ten: 'Bánh A', so_luong: 41, dvt: 'Hộp', co_bom: true, bom: 'BOM-A-001', lau: true,
      gia_0: false, so_ngay: 8, dong: dongBom(2, 'A') },
    { item: 'TP-B', ten: 'Bánh B', so_luong: 306, dvt: 'Hộp', co_bom: false, bom: null, lau: true,
      gia_0: true, so_ngay: 12, dong: dongBom(12, 'B') },
    { item: 'TP-C', ten: 'Bánh C', so_luong: 41, dvt: 'Hộp', co_bom: false, bom: null, lau: false,
      gia_0: false, so_ngay: 4, dong: dongBom(2, 'C') }] },
  gia: { tong_dong: 3, ngay_no_lau: 7, nhom: [
    { san_pham: 'TP-A', ten: 'Bánh A', cach_lam: 'Máy', so_hop: 500, co_gia: true, so_co_gia: 2, tien: 400000,
      bang: ['BG-10'], lau: true, so_ngay: 8, dong: [
        { name: 'NG-1', ngay: '2026-10-11', so_hop: 300, so_nguoi: 4, gia: 800 },
        { name: 'NG-2', ngay: '2026-10-12', so_hop: 200, so_nguoi: 3, gia: 800 }] },
    { san_pham: 'TP-B', ten: 'Bánh B', cach_lam: null, so_hop: 200, co_gia: false, so_co_gia: 0, tien: 0,
      bang: ['BG-10'], lau: true, so_ngay: 9, dong: [
        { name: 'NG-3', ngay: '2026-10-05', so_hop: 200, so_nguoi: 2, gia: null }] }] },
  vh: { tong_dong: 2, duoc_bo_qua: true, duoc_ghi_kc: true, nhom: [
    { item: 'TP-SEN', ten: 'Bánh sen', con_lai: 29.5, so_hop: 30, so_ngay: 5, cach_lam: [], gia_chung: 1000,
      dong: [{ name: 'NV-1', ngay: '2026-10-09', so_luong: 30, con_lai: 29.5, phieu_nhap: 'PN-1' }] },
    { item: 'TP-DX', ten: 'Bánh đậu xanh', con_lai: 10, so_hop: 10, so_ngay: 1, cach_lam: [], gia_chung: 900,
      dong: [{ name: 'NV-2', ngay: '2026-10-13', so_luong: 10, con_lai: 10, phieu_nhap: 'PN-2' }] }] },
  lo: { con_ton: 56, het_hang: 3, rows: [
    { batch: 'TH170-OLD1', ten: 'Bánh TH 170g', nsx: '2026-08-01', co_nsx: true, ton: 12, dvt: 'Hộp',
      goi_y: '2027-02-01' },
    { batch: 'SR170-OLD1', ten: 'Bánh SR 170g', nsx: '2026-08-03', co_nsx: true, ton: 5, dvt: 'Hộp',
      goi_y: '2027-02-03' },
    { batch: 'TRE-OLD1', ten: 'Hộp tre 675g', nsx: '2026-07-20', co_nsx: false, ton: 2, dvt: 'Hộp', goi_y: null }] },
};
DL.lo_ca = { ...DL.lo, rows: [...DL.lo.rows, { batch: 'TCT-OLD9', ten: 'Bánh TCT', nsx: '2026-06-01', co_nsx: true,
  ton: 0, dvt: 'Hộp', goi_y: '2026-12-01' }] };

const srv = createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  if (u.startsWith('/assets/sx/sx/')) {
    const f = normalize(join(PUB, u.slice('/assets/sx/sx/'.length)));
    if (f.startsWith(PUB) && existsSync(f)) {
      res.writeHead(200, { 'Content-Type': f.endsWith('.js') ? 'text/javascript' : 'text/css' });
      res.end(readFileSync(f)); return;
    }
    res.writeHead(404); res.end(); return;
  }
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); res.end(TRANG);
});
await new Promise((r) => srv.listen(0, '127.0.0.1', r));
const pw = (await import(PW)).default;
const b = await pw.chromium.launch({ executablePath: CHROME });
const p = await b.newPage({ viewport: { width: 1100, height: 900 } });
const loi = [];
p.on('pageerror', (e) => loi.push(e.message));
await p.goto(`http://127.0.0.1:${srv.address().port}/`);
await p.waitForFunction(() => window.SAN_SANG, null, { timeout: 10000 });
await p.evaluate((d) => { window.DL = d; }, DL);
const veHet = () => p.evaluate(async () => { for (const k of ['bom', 'gia', 'vh', 'lo']) await window.ve(k); });
await veHet();

// Đọc một thẻ: đang mở?, tiêu đề, các mẩu nhắc (chữ + lớp), cao bao nhiêu, danh sách có hiện không.
const doc = (k) => p.evaluate((id) => {
  const c = document.getElementById(id);
  const d = c.querySelector(':scope > details.sx-no-gap');
  if (!d) return { co: false, an: c.style.display === 'none' };
  const tom = d.querySelector(':scope > summary.sx-no-tom');
  const ds = d.querySelector('.sx-nobom-nhom, .sx-vh-row');
  return {
    co: true, an: c.style.display === 'none', mo: d.open,
    tieuDe: tom.querySelector('.sx-field-label').textContent,
    nhac: [...tom.querySelectorAll('.sx-no-nhac > span')].map((s) => [s.textContent, s.className]),
    cao: Math.round(c.getBoundingClientRect().height),
    hien: !!ds && ds.checkVisibility(),   // nội dung <details> gập: có hộp nhưng không vẽ
  };
}, k);

console.log('-- mặc định GẬP: một dòng tóm tắt, danh sách ẩn --');
const bd = { bom: await doc('bom'), gia: await doc('gia'), vh: await doc('vh'), lo: await doc('lo') };
kiem('cả bốn thẻ gập sẵn, danh sách không hiện', Object.values(bd).every((x) => x.co && !x.mo && !x.hien),
  JSON.stringify(Object.fromEntries(Object.entries(bd).map(([k, x]) => [k, [x.mo, x.hien]]))));
kiem('thẻ gập chỉ cao một dòng (≤ 120px) dù sổ BOM có 16 lần nhập', Object.values(bd).every((x) => x.cao <= 120),
  JSON.stringify(Object.fromEntries(Object.entries(bd).map(([k, x]) => [k, x.cao]))));
kiem('Nợ BOM: tiêu đề giữ nguyên số mã, số lần nhập', bd.bom.tieuDe === 'Sổ nợ BOM — 3 mã, 16 lần nhập', bd.bom.tieuDe);
kiem('Nợ BOM: nhắc mã hạch toán bù được ngay (xanh), nợ quá hạn + lô giá vốn 0 (đỏ), cũ nhất',
  JSON.stringify(bd.bom.nhac) === JSON.stringify([
    ['✓ 1 mã đã có BOM — hạch toán bù được ngay', 'sx-no-nhac-lam'], ['1 mã nợ quá 7 ngày', 'sx-no-nhac-gap'],
    ['1 mã lô giá vốn 0', 'sx-no-nhac-gap'], ['cũ nhất 12 ngày', '']]), JSON.stringify(bd.bom.nhac));
kiem('Nợ đơn giá: tiêu đề + mã áp giá được ngay, nợ quá hạn, cũ nhất',
  bd.gia.tieuDe === 'Sổ nợ đơn giá — 2 mã, 3 ngày' && JSON.stringify(bd.gia.nhac) === JSON.stringify([
    ['✓ 1 mã đã có giá — áp giá được ngay', 'sx-no-nhac-lam'], ['1 mã nợ quá 7 ngày', 'sx-no-nhac-gap'],
    ['cũ nhất 9 ngày', '']]), JSON.stringify([bd.gia.tieuDe, bd.gia.nhac]));
kiem('Nợ vào hộp: tiêu đề số hộp chưa chấm + mã quá 3 ngày (đỏ), cũ nhất',
  bd.vh.tieuDe === 'Nợ vào hộp — 2 mã, 40 hộp chưa chấm' && JSON.stringify(bd.vh.nhac) === JSON.stringify([
    ['1 mã quá 3 ngày — hỏi tổ sớm', 'sx-no-nhac-gap'], ['cũ nhất 5 ngày', '']]),
  JSON.stringify([bd.vh.tieuDe, bd.vh.nhac]));
kiem('Lô cũ chưa có HSD: tiêu đề 56 lô còn tồn · 3 lô hết hàng + lô có HSD gợi ý (xanh) / mã chưa khai hạn dùng (đỏ)',
  bd.lo.tieuDe === 'Lô cũ chưa có HSD — 56 lô còn tồn · 3 lô đã hết hàng'
  && JSON.stringify(bd.lo.nhac) === JSON.stringify([
    ['2 lô đã điền sẵn HSD gợi ý — soát theo bao bì rồi GHI', 'sx-no-nhac-lam'],
    ['1 lô mã chưa khai hạn dùng — nhập HSD tay', 'sx-no-nhac-gap']]), JSON.stringify([bd.lo.tieuDe, bd.lo.nhac]));

const css = await p.evaluate(() => {
  const tom = document.querySelector('#bom summary.sx-no-tom');
  const s = getComputedStyle(tom);
  const sau = getComputedStyle(tom, '::after');
  return { display: s.display, cursor: s.cursor, minH: s.minHeight, mui: sau.content,
    lam: getComputedStyle(document.querySelector('#bom .sx-no-nhac-lam')).color,
    gap: getComputedStyle(document.querySelector('#bom .sx-no-nhac-gap')).color,
    hoa: getComputedStyle(tom.querySelector('.sx-field-label')).textTransform };
});
kiem('CSS thật: dòng gập là flex (không mũi tam giác mặc định), con trỏ tay, cao ≥ 48px (bấm bằng ngón tay)',
  css.display === 'flex' && css.cursor === 'pointer' && parseFloat(css.minH) >= 48, JSON.stringify(css));
kiem('mũi ▸ bên phải; nhắc "làm được ngay" màu xanh, "quá lâu" màu đỏ; tiêu đề kiểu nhãn IN HOA như cũ',
  css.mui === '"▸"' && css.lam === 'rgb(4, 120, 87)' && css.gap === 'rgb(185, 28, 28)' && css.hoa === 'uppercase',
  JSON.stringify(css));

console.log('\n-- bấm dòng gập: xổ danh sách --');
await p.click('#bom summary.sx-no-tom');
await p.waitForTimeout(250);   // mũi xoay có chuyển động .15s
let x = await doc('bom');
const quay = await p.evaluate(() => getComputedStyle(document.querySelector('#bom summary.sx-no-tom'), '::after')
  .transform);
kiem('bấm → mở, danh sách hiện, thẻ dài ra (đủ 3 mã, 16 dòng)', x.mo && x.hien && x.cao > 400
  && (await p.$$('#bom .sx-nobom-nhom')).length === 3 && (await p.$$('#bom .sx-nobom-dong')).length === 16,
  JSON.stringify([x.mo, x.hien, x.cao]));
kiem('mũi xoay xuống khi mở (hình dạng đổi, không chỉ màu)', /^matrix\((-?0|[0-9.e-]+), 1, -1, /.test(quay), quay);
kiem('mở một thẻ không mở thẻ khác', !(await doc('gia')).mo && !(await doc('vh')).mo && !(await doc('lo')).mo);
await p.click('#bom summary.sx-no-tom');
kiem('bấm lần nữa → gập lại', !(await doc('bom')).mo);
await p.focus('#gia summary.sx-no-tom');
await p.keyboard.press('Enter');
kiem('bàn phím: Enter trên dòng gập cũng mở (details gốc)', (await doc('gia')).mo && (await doc('gia')).hien);
await p.keyboard.press('Enter');
kiem('… Enter lần nữa gập lại', !(await doc('gia')).mo);

console.log('\n-- đang làm dở trong thẻ: vẽ lại vẫn MỞ --');
await p.click('#bom summary.sx-no-tom');
await p.click('#bom .sx-nobom-dong:has-text("PN-B-1") button');
await p.fill('.sx-modal textarea', 'hàng trả về nhập lại');
await p.click('.sx-modal .sx-btn-warn');
await p.waitForFunction(() => document.querySelector('#bom .sx-field-label').textContent.includes('15 lần'),
  null, { timeout: 3000 }).catch(() => {});
x = await doc('bom');
kiem('Bỏ qua một lần nhập (Nợ BOM): thẻ vẽ lại với số mới mà VẪN MỞ', x.mo && x.hien
  && x.tieuDe === 'Sổ nợ BOM — 3 mã, 15 lần nhập', JSON.stringify([x.mo, x.tieuDe]));
await p.click('#lo summary.sx-no-tom');
await p.click('#lo #lh-het');
await p.waitForFunction(() => (document.querySelector('#lo #lh-het') || {}).textContent === 'Chỉ lô còn tồn',
  null, { timeout: 3000 }).catch(() => {});
x = await doc('lo');
kiem('Lô cũ: "+ Lô đã hết hàng" vẽ lại kèm lô hết hàng mà VẪN MỞ', x.mo && x.hien
  && (await p.$$('#lo .sx-vh-row')).length === 4, JSON.stringify([x.mo, x.hien]));
await p.click('#lo #lh-ghi');
await p.click('.sx-modal .sx-btn-warn');
await p.click('.sx-modal .sx-btn-danger');
await p.waitForTimeout(250);
const ghi = (await p.evaluate(() => window.CALLS)).filter(([m]) => m === 'sx.api.lohsd.dat_hsd').pop();
kiem('Lô cũ: GHI HSD từ thẻ đã mở gửi đúng các lô có HSD; thẻ vẽ lại vẫn mở',
  ghi && JSON.parse(ghi[1].rows).length === 3 && (await doc('lo')).mo, ghi ? ghi[1].rows : '(không gọi)');

console.log('\n-- Ghi cho công khoán (vẽ lại CẢ màn): thẻ mới vẽ ngay sau đó mở sẵn, một lần --');
await p.click('#vh summary.sx-no-tom');
await p.click('#vh .sx-nvh-kc');
await p.click('.sx-modal .sx-btn-primary');
await p.waitForFunction(() => window.REFRESH === 1, null, { timeout: 3000 }).catch(() => {});
kiem('ghi xong gọi vẽ lại cả màn', (await p.evaluate(() => window.REFRESH)) === 1);
await p.evaluate(() => window.ve('vh'));
kiem('thẻ vẽ lại ngay sau đó (ô mới) → MỞ sẵn, ghi tiếp mã khác không phải bấm mở', (await doc('vh')).mo);
await p.evaluate(() => window.ve('vh'));
kiem('lần vẽ sau đó → gập như mặc định (chỉ mở sẵn một lần)', !(await doc('vh')).mo);
await p.evaluate(() => window.ve('bom'));
kiem('mở lại màn (ô mới, không thao tác gì) → gập như mặc định', !(await doc('bom')).mo);

console.log('\n-- hết nợ: thẻ tự ẩn như cũ --');
await p.evaluate(() => { window.DL.bom = { nhom: [], tong_dong: 0, duoc_xu_ly: true, ngay_no_lau: 7 };
  window.DL.vh = { ...window.DL.vh, nhom: [] }; });
await p.evaluate(async () => { await window.ve('bom'); await window.ve('vh'); });
kiem('không nợ BOM / nợ vào hộp → thẻ ẩn hẳn, không còn dòng gập trống',
  (await doc('bom')).an && !(await doc('bom')).co && (await doc('vh')).an && !(await doc('vh')).co);

console.log('\n-- điện thoại (360px): dòng gập không tràn ngang --');
await p.setViewportSize({ width: 360, height: 800 });
await p.evaluate((d) => { window.DL = d; }, DL);
await veHet();
const tran = await p.evaluate(() => ['bom', 'gia', 'vh', 'lo'].map((k) => {
  const c = document.getElementById(k);
  return [k, c.scrollWidth - c.clientWidth, document.documentElement.scrollWidth - window.innerWidth];
}));
kiem('nhắc dài xuống dòng trong thẻ, trang không cuộn ngang', tran.every(([, a, t]) => a <= 0 && t <= 0),
  JSON.stringify(tran));

await b.close();
srv.close();
kiem('không lỗi JavaScript', !loi.length, loi.join(' | '));
console.log(hong ? `GAPNO: ${hong} HỎNG` : 'GAPNO-OK');
process.exit(hong ? 1 : 0);
