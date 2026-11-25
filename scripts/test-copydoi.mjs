// D242 — nút "Copy thay đổi" ở màn Ghi hộp: sau lần copy gửi nhóm, chỉ chép khối của người ĐỔI từ lần đó.
//
// Vì sao phải có bài này: tin thay đổi mà sót người là người đó đối chiếu số cũ; thừa người là lại "loãng" — đúng cái
// chủ xưởng muốn bỏ. Hỏng im lặng theo mấy hướng:
//   · người chuyển hết số sang người khác (chấm nhầm) biến mất khỏi tin — nhóm vẫn tin số cũ của họ;
//   · chỉ đổi ăn ca thì tổng sản phẩm không đổi — dòng Tổng không được lặp; suất ăn đổi thì phải có dòng Suất ăn;
//   · copy thay đổi xong mà không nhớ lại → lần sau chép lại đúng những người vừa gửi;
//   · nhớ theo máy: người khác / ngày khác trên cùng máy không được dùng nhầm bản nhớ; bộ nhớ bị chặn thì copy đầy đủ
//     vẫn phải chạy.
//
// Phần 1 (Node): hàm thuần. Phần 2 (Chromium thật, nếu máy có): bấm nút, đọc clipboard, tải lại trang.
// Chạy: node scripts/test-copydoi.mjs   (verify.sh gọi sẵn)

import { existsSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { dirname, join, resolve, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const GOC = resolve(dirname(fileURLToPath(import.meta.url)), '..');
let hong = 0;
const kiem = (ten, dk, ct = '') => {
  if (!dk) hong += 1;
  console.log(`  ${dk ? 'ok  ' : 'HỎNG'} ${ten}${ct && !dk ? ` — ${ct}` : ''}`);
};

// ── Phần 1: hàm thuần (cắt import, thay formatNumber) ───────────────────
const src = readFileSync(join(GOC, 'sx/public/sx/cards/vaohop.js'), 'utf8')
  .split('\n').filter((d) => !d.startsWith('import ')).join('\n');
const tam = join(tmpdir(), `cd-${process.pid}.mjs`);
writeFileSync(tam, `const formatNumber = (n) => Number(n).toLocaleString('vi-VN');\n${src}`);
const VH = await import(`file://${tam}`);
rmSync(tam);
const { khoiSanLuong, vanBanTuKhoi, vanBanSanLuong, anhChup, thayDoi, vanBanThayDoi, lucCopy, dam } = VH;
const T = '\u00a0'.repeat(4) + '- ';
const BO = 'Bỏ hết số đã gửi — không còn sản lượng, suất ăn';

const tenHang = (c) => ({ 'TP-SEN': 'Bánh sen', 'TP-TT': 'Bánh TT' }[c]);
const TEN = { NV1: 'An', NV2: 'Bình', NV3: 'Cúc', NV4: 'Dũng', NV5: 'Em' };
const tenNguoi = (m) => TEN[m] || m;
const NGAY = '2026-11-25';
// nhóm theo người như theoNguoi() ở màn hình; an = chấm ăn / giờ theo người
const nguoi = (nv, ...dong) => ({ ten: TEN[nv], dong: dong.map((d) => ({ nhan_vien: nv, ...d })) });
const sen = (so_hop, cach_lam = 'Máy') => ({ san_pham: 'TP-SEN', cach_lam, so_hop });
const tt = (so_hop) => ({ san_pham: 'TP-TT', cach_lam: 'Tay', so_hop });
const CN = { ten: '★ Công nhật', dong: [{ nhan_vien: 'CONG_NHAT', san_pham: 'TP-SEN', so_hop: 50 }] };
const AN0 = { NV1: { an_ca: 1, an_dem: 1 }, NV2: { an_ca: 1 }, NV3: { an_ca: 1 } };
const khoi = (nhom, an = AN0) => khoiSanLuong(nhom, NGAY, tenHang, an, tenNguoi);
const NHOM0 = [nguoi('NV1', sen(120)), nguoi('NV2', tt(30)), nguoi('NV4', { _gio: 3 }), CN];

console.log('-- tách tin theo người --');
const k0 = khoi(NHOM0);
const day = vanBanSanLuong(NHOM0, NGAY, tenHang, AN0, tenNguoi);
kiem('ghép lại các khối = ĐÚNG tin đầy đủ (copy đầy đủ không đổi một ký tự)', vanBanTuKhoi(k0) === day, day);
kiem('mỗi người một khối, khoá theo mã nhân viên, xếp theo tên; người chỉ có ăn ca (Cúc) cũng có khối; công nhật không',
  JSON.stringify(k0.khoi.map((x) => [x.nv, x.ten])) === JSON.stringify([['NV1', 'An'], ['NV2', 'Bình'], ['NV3', 'Cúc'],
    ['NV4', 'Dũng']]), JSON.stringify(k0.khoi));
kiem('… khối đúng như đoạn của người đó trong tin đầy đủ',
  JSON.stringify(k0.khoi.map((x) => x.chu)) === JSON.stringify(day.split('\n\n').slice(1, -1)));
kiem('tổng 150 (không cộng công nhật), suất ăn ca 3 · ăn đêm 1 — là SỐ',
  k0.tong === 150 && k0.ca === 3 && k0.dem === 1, JSON.stringify([k0.tong, k0.ca, k0.dem]));
const anh = anhChup(k0, 1000);
kiem('bản nhớ lần copy: giờ copy, khối theo mã (tên + chữ), tổng, suất ăn',
  anh.luc === 1000 && anh.khoi.NV2.ten === 'Bình' && anh.khoi.NV2.chu === k0.khoi[1].chu && anh.tong === 150
  && anh.ca === 3 && anh.dem === 1, JSON.stringify(anh));
kiem('bản nhớ qua JSON (localStorage) vẫn so được y nguyên', vanBanThayDoi(JSON.parse(JSON.stringify(anh)), k0) === '');

console.log('\n-- so với lần copy trước --');
const t0 = thayDoi(anh, k0);
kiem('không đổi gì → không người nào, tổng / suất không đổi, tin rỗng',
  !t0.doi.length && !t0.bo.length && !t0.tong && !t0.suat && vanBanThayDoi(anh, k0) === '');
kiem('chỉ đổi công nhật (không có trong tin) → vẫn không có gì để gửi',
  vanBanThayDoi(anh, khoi([nguoi('NV1', sen(120)), nguoi('NV2', tt(30)), nguoi('NV4', { _gio: 3 }),
    { ...CN, dong: [{ ...CN.dong[0], so_hop: 80 }] }])) === '');
const vSua = vanBanThayDoi(anh, khoi([nguoi('NV1', sen(140)), nguoi('NV2', tt(30)), nguoi('NV4', { _gio: 3 }), CN]));
kiem('sửa số một người: tiêu đề CẬP NHẬT + NGUYÊN khối mới của người đó + dòng Tổng mới; không Suất ăn (không đổi)',
  vSua === `SẢN LƯỢNG 25/11/2026 — CẬP NHẬT\n\n${dam('An')} · ăn ca + ăn đêm\n${T}Bánh sen (M): ${dam('140')}\n\n`
    + `— Tổng: ${dam('170')} sản phẩm`, JSON.stringify(vSua));
const vAn = vanBanThayDoi(anh, khoi(NHOM0, { ...AN0, NV2: { an_ca: 2 } }));
kiem('chỉ đổi ăn ca của một người: khối người đó + dòng Suất ăn mới; KHÔNG dòng Tổng (tổng sản phẩm không đổi)',
  vAn === `SẢN LƯỢNG 25/11/2026 — CẬP NHẬT\n\n${dam('Bình')} · ăn ca ×2\n${T}Bánh TT (T): ${dam('30')}\n\n`
    + `— Suất ăn: ăn ca ${dam('4')} · ăn đêm ${dam('1')}`, JSON.stringify(vAn));
const vDem = vanBanThayDoi(anh, khoi(NHOM0, { ...AN0, NV2: { an_ca: 1, an_dem: 1 } }));
kiem('chỉ thêm ăn ĐÊM (ăn ca giữ nguyên) → vẫn có dòng Suất ăn mới (ăn đêm 2)',
  vDem === `SẢN LƯỢNG 25/11/2026 — CẬP NHẬT\n\n${dam('Bình')} · ăn ca + ăn đêm\n${T}Bánh TT (T): ${dam('30')}\n\n`
    + `— Suất ăn: ăn ca ${dam('3')} · ăn đêm ${dam('2')}`, JSON.stringify(vDem));
const vChiTong = vanBanThayDoi({ ...anh, ca: 2 }, k0);
kiem('khối không ai đổi mà số suất ăn lệch bản nhớ → vẫn gửi dòng Suất ăn (không nuốt mất)',
  vChiTong === `SẢN LƯỢNG 25/11/2026 — CẬP NHẬT\n\n— Suất ăn: ăn ca ${dam('3')} · ăn đêm ${dam('1')}`,
  JSON.stringify(vChiTong));
const vChuyen = vanBanThayDoi(anh, khoi([nguoi('NV1', sen(120)), nguoi('NV3', tt(30)), nguoi('NV4', { _gio: 3 }), CN]));
kiem('chấm nhầm người (30 hộp của Bình chuyển sang Cúc): cả hai khối, Bình còn ăn ca; tổng / suất không đổi → không '
  + 'dòng tổng', vChuyen === `SẢN LƯỢNG 25/11/2026 — CẬP NHẬT\n\n${dam('Bình')} · ăn ca\n\n`
    + `${dam('Cúc')} · ăn ca\n${T}Bánh TT (T): ${dam('30')}`, JSON.stringify(vChuyen));
const k3 = khoi([nguoi('NV1', sen(140)), nguoi('NV2', tt(30)), nguoi('NV5', sen(10, 'Tay')), CN]);
const t3 = thayDoi(anh, k3);
kiem('người không còn gì (Dũng bỏ giờ, không ăn) → mục "bỏ"; người mới (Em) → moi; người sửa (An) → không moi',
  JSON.stringify(t3.bo) === JSON.stringify([{ nv: 'NV4', ten: 'Dũng' }])
  && JSON.stringify(t3.doi.map((x) => [x.nv, x.moi])) === JSON.stringify([['NV1', false], ['NV5', true]]),
  JSON.stringify(t3));
const v3 = vanBanThayDoi(anh, k3);
kiem('… tin: An, Dũng (bỏ số đã gửi), Em — xếp theo tên, lẫn cả người bỏ; Tổng mới 180',
  v3 === `SẢN LƯỢNG 25/11/2026 — CẬP NHẬT\n\n${dam('An')} · ăn ca + ăn đêm\n${T}Bánh sen (M): ${dam('140')}\n\n`
    + `${dam('Dũng')}\n${T}${BO}\n\n${dam('Em')}\n${T}Bánh sen (T): ${dam('10')}\n\n— Tổng: ${dam('180')} sản phẩm`,
  JSON.stringify(v3));
const vHet = vanBanThayDoi(anh, khoi([CN], {}));
kiem('bỏ hết mọi người, bỏ hết ăn: mỗi người một mục bỏ + Tổng 0 + Suất ăn 0 · 0 (không bỏ sót dòng suất)',
  vHet === `SẢN LƯỢNG 25/11/2026 — CẬP NHẬT\n\n${['An', 'Bình', 'Cúc', 'Dũng'].map((x) => `${dam(x)}\n${T}${BO}`)
    .join('\n\n')}\n\n— Tổng: ${dam('0')} sản phẩm\n— Suất ăn: ăn ca ${dam('0')} · ăn đêm ${dam('0')}`,
  JSON.stringify(vHet));
kiem('lần trước chưa copy gì (bản nhớ rỗng) → mọi người là mới',
  thayDoi({ khoi: {}, tong: 0, ca: 0, dem: 0 }, k0).doi.length === 4);
kiem('bản nhớ thiếu số suất ăn (khuôn cũ / hỏng) → coi là 0, không ra NaN',
  thayDoi({ khoi: anh.khoi, tong: 150 }, k0).suat === true
  && thayDoi({ khoi: anh.khoi, tong: 150 }, khoi(NHOM0, {})).suat === false);
kiem('ngày không rõ → tiêu đề "SẢN LƯỢNG — CẬP NHẬT"',
  vanBanThayDoi(anh, khoiSanLuong(NHOM0, '', tenHang, { ...AN0, NV1: {} }, tenNguoi)).startsWith('SẢN LƯỢNG — CẬP NHẬT\n\n'));

console.log('\n-- giờ copy --');
const g = (d, h, m) => new Date(2026, 10, d, h, m).getTime();
kiem('cùng ngày → "lúc 17:05"; ngày khác → "24/11 lúc 07:09"',
  lucCopy(g(25, 17, 5), new Date(2026, 10, 25, 20, 0)) === 'lúc 17:05'
  && lucCopy(g(24, 7, 9), new Date(2026, 10, 25, 8, 0)) === '24/11 lúc 07:09',
  [lucCopy(g(25, 17, 5), new Date(2026, 10, 25, 20, 0)), lucCopy(g(24, 7, 9), new Date(2026, 10, 25, 8, 0))].join(' | '));

// ── Phần 2: Chromium thật ───────────────────────────────────────────────
const CHROME = ['/opt/pw-browsers/chromium', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome']
  .find((f) => existsSync(f)) || '/opt/pw-browsers/chromium';
const PW = '/opt/node22/lib/node_modules/playwright/index.js';
if (!existsSync(CHROME) || !existsSync(PW)) {
  console.log('\n-- trình duyệt thật: BỎ QUA (máy này không có Chromium) --');
} else {
  const PUB = join(GOC, 'sx/public/sx');
  // ?v=a|b (dữ liệu trước / sau khi sửa) &u=người dùng &ngay=… ; bảng lưu (gọi API) trả lại đúng dòng gửi lên.
  const TRANG = `<!doctype html><meta charset="utf-8"><body><div id="c"></div>
<script type="module">
import * as VH from '/assets/sx/sx/cards/vaohop.js';
window.VH = VH;
const q = new URLSearchParams(location.search);
const ngayXem = q.get('ngay') || '2026-11-25';
const sen = (nv, so, cl = 'Máy') => ({ nhan_vien: nv, san_pham: 'TP-SEN', cach_lam: cl, so_hop: so });
const A = { dong: [sen('NV1', 120), { ...sen('NV2', 30), cach_lam: 'Tay' },
    { nhan_vien: 'CONG_NHAT', cong_nhat: 1, san_pham: 'TP-SEN', so_hop: 50 }],
  an_ca: [{ nhan_vien: 'NV1', an_ca: 1, an_dem: 1 }, { nhan_vien: 'NV2', an_ca: 1, an_dem: 0 },
    { nhan_vien: 'NV3', an_ca: 1, an_dem: 0 }, { nhan_vien: 'NV4', an_ca: 0, an_dem: 0, so_gio: 3 }] };
const B = { dong: [sen('NV1', 140), { ...sen('NV2', 30), cach_lam: 'Tay' }, sen('NV5', 10, 'Tay'),
    { nhan_vien: 'CONG_NHAT', cong_nhat: 1, san_pham: 'TP-SEN', so_hop: 50 }],
  an_ca: [{ nhan_vien: 'NV1', an_ca: 1, an_dem: 1 }, { nhan_vien: 'NV2', an_ca: 1, an_dem: 0 },
    { nhan_vien: 'NV3', an_ca: 1, an_dem: 0 }] };
const bang = JSON.parse(JSON.stringify(q.get('v') === 'b' ? B : A));
bang.dong.forEach((r, i) => { r.name = 'R' + i; });
const AN = bang.an_ca;
const ngay = { name: 'N1', ngay: ngayXem, docstatus: 0 };
const boot = { user: q.get('u') || 'qc1@xuong', ngay_xem: ngayXem, ngay_sx: ngay, bang_don_gia: 'BG',
  don_gia_gio: 33000, don_gia_gio_2: 30000, items_tp: [{ name: 'TP-SEN', item_name: 'Bánh sen' }],
  danh_muc_khoan: [{ item: 'TP-SEN', ten: 'Bánh sen', dvt: 'Hộp', cach_lam: [], gia_chung: 1000, chua_gia: false }],
  nhan_vien: ['An', 'Bình', 'Cúc', 'Dũng', 'Em'].map((t, i) => ({ name: 'NV' + (i + 1), employee_name: t,
    ten_hien_thi: t })),
  bang_vao_hop: bang };
const call = async (m, a) => {
  if (m === 'sx.api.portal.luu_bang_vao_hop') {
    const dong = JSON.parse(a.rows).map((r, i) => ({ ...r, name: r.name || 'M' + i }));
    JSON.parse(a.an_ca).forEach((d) => {
      const x = AN.find((y) => y.nhan_vien === d.nhan_vien);
      if (x) Object.assign(x, d); else AN.push(d);
    });
    return { dong, an_ca: AN };
  }
  return {};
};
await VH.render({ container: document.getElementById('c'), boot, call, ensureNgay: async () => ngay });
window.SAN_SANG = true;
</script>`;
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
  const goc = `http://127.0.0.1:${srv.address().port}`;
  const pw = (await import(PW)).default;
  const b = await pw.chromium.launch({ executablePath: CHROME });
  const ctx = await b.newContext({ permissions: ['clipboard-read', 'clipboard-write'] });
  const p = await ctx.newPage();
  const loi = [];
  p.on('pageerror', (e) => loi.push(e.message));
  const mo = async (qs) => {
    await p.goto(`${goc}/?${qs}`);
    await p.waitForFunction(() => window.SAN_SANG, null, { timeout: 10000 });
  };
  const dat = (s) => p.evaluate((x) => navigator.clipboard.writeText(x), s);
  const clip = () => p.evaluate(() => navigator.clipboard.readText());
  const nut = () => p.textContent('#sx-vh-copydoi');
  const tt = () => p.evaluate(() => { const x = document.querySelector('#sx-vh-copy-tt'); return x.hidden ? null : x.textContent; });
  const bao = async () => (await p.textContent('.sx-toast-wrap')) || '';
  const xoaBao = () => p.evaluate(() => { const w = document.querySelector('.sx-toast-wrap'); if (w) w.innerHTML = ''; });
  const bam = async (sel) => { await xoaBao(); await p.click(sel); await p.waitForTimeout(300); };
  const gioCopy = /^Đã copy lúc \d\d:\d\d — /;
  try {
    console.log('\n-- trình duyệt thật: lần đầu, chưa copy --');
    await mo('v=a&u=qc1@xuong');
    await dat('TRỐNG');
    kiem('chưa copy ngày này: không có dòng trạng thái, nút "Copy thay đổi" không số',
      (await tt()) === null && (await nut()) === 'Copy thay đổi');
    await bam('#sx-vh-copydoi');
    kiem('bấm Copy thay đổi khi máy chưa copy → báo dùng copy đầy đủ trước, clipboard để nguyên',
      (await bao()).includes('Máy này chưa copy tin ngày 25/11') && (await clip()) === 'TRỐNG', await bao());

    console.log('\n-- copy đầy đủ → nhớ --');
    await bam('#sx-vh-copy');
    const day = await clip();
    kiem('copy đầy đủ như cũ (có An, Bình, Cúc, Dũng)', day.startsWith('SẢN LƯỢNG 25/11/2026\n\n')
      && ['An', 'Bình', 'Cúc', 'Dũng'].every((x) => day.includes(dam(x))), JSON.stringify(day));
    kiem('… dòng trạng thái: "Đã copy lúc HH:MM — chưa có gì thay đổi."',
      gioCopy.test(await tt()) && (await tt()).endsWith('chưa có gì thay đổi.'), await tt());
    const nho = await p.evaluate(() => JSON.parse(localStorage.getItem('sx-vh-da-gui-nhom')));
    kiem('… nhớ trên máy theo "người dùng|ngày"', Object.keys(nho).join() === 'qc1@xuong|2026-11-25'
      && Object.keys(nho['qc1@xuong|2026-11-25'].khoi).sort().join() === 'NV1,NV2,NV3,NV4', JSON.stringify(nho));

    console.log('\n-- dữ liệu đổi (tải lại trang) → copy thay đổi --');
    await mo('v=b&u=qc1@xuong');
    kiem('tải lại có dữ liệu mới: trạng thái kể người đổi (An sửa, Dũng bỏ, Em mới), nút "Copy thay đổi (3)"',
      gioCopy.test(await tt()) && (await tt()).endsWith('đổi từ đó: An, Dũng, Em.') && (await nut()) === 'Copy thay đổi (3)',
      `${await tt()} | ${await nut()}`);
    await bam('#sx-vh-copydoi');
    const doi = await clip();
    kiem('clipboard CHỈ có An (khối mới), Dũng (bỏ số đã gửi), Em + Tổng mới — không Bình, Cúc',
      doi === `SẢN LƯỢNG 25/11/2026 — CẬP NHẬT\n\n${dam('An')} · ăn ca + ăn đêm\n${T}Bánh sen (M): ${dam('140')}\n\n`
        + `${dam('Dũng')}\n${T}${BO}\n\n${dam('Em')}\n${T}Bánh sen (T): ${dam('10')}\n\n— Tổng: ${dam('180')} sản phẩm`,
      JSON.stringify(doi));
    kiem('… báo "Đã copy phần thay đổi" kèm lời nhắc chữ to', (await bao()).includes('Đã copy phần thay đổi — dán vào nhóm Zalo')
      && (await bao()).includes('giữ nút Gửi'), await bao());
    kiem('… nhớ lại ngay: trạng thái "chưa có gì thay đổi", nút hết số',
      (await tt()).endsWith('chưa có gì thay đổi.') && (await nut()) === 'Copy thay đổi', `${await tt()} | ${await nut()}`);
    await dat('TRỐNG');
    await bam('#sx-vh-copydoi');
    kiem('bấm lại khi chưa đổi gì → báo "Chưa có gì thay đổi so với lần copy lúc …", clipboard để nguyên',
      /Chưa có gì thay đổi so với lần copy lúc \d\d:\d\d\./.test(await bao()) && (await clip()) === 'TRỐNG', await bao());

    console.log('\n-- sửa ngay trên màn → trạng thái đổi theo --');
    await p.click('.sx-vh-sl[data-i="0"]');                       // dòng của An
    for (const k of ['1', '5', '0']) await p.click(`.sx-modal .sx-numpad-key:text-is("${k}")`);
    await p.click('.sx-modal .sx-btn-primary');
    await p.waitForTimeout(400);
    kiem('sửa số của An (140 → 150) → lưu xong trạng thái "đổi từ đó: An.", nút "Copy thay đổi (1)"',
      (await tt()).endsWith('đổi từ đó: An.') && (await nut()) === 'Copy thay đổi (1)', `${await tt()} | ${await nut()}`);
    await bam('#sx-vh-copydoi');
    kiem('… copy thay đổi: chỉ An 150 + Tổng 190',
      (await clip()) === `SẢN LƯỢNG 25/11/2026 — CẬP NHẬT\n\n${dam('An')} · ăn ca + ăn đêm\n${T}Bánh sen (M): ${dam('150')}`
        + `\n\n— Tổng: ${dam('190')} sản phẩm`, JSON.stringify(await clip()));

    console.log('\n-- người khác / ngày khác trên cùng máy --');
    await mo('v=b&u=qc2@xuong');
    await dat('TRỐNG');
    await bam('#sx-vh-copydoi');
    kiem('người dùng khác trên cùng máy: không dùng bản nhớ của qc1 → báo chưa copy',
      (await tt()) === null && (await bao()).includes('Máy này chưa copy tin ngày 25/11') && (await clip()) === 'TRỐNG');
    await mo('v=b&u=qc1@xuong&ngay=2026-11-26');
    kiem('ngày khác: không dùng bản nhớ ngày 25/11', (await tt()) === null);
    await bam('#sx-vh-copydoi');
    kiem('… báo đúng ngày đang xem (26/11)', (await bao()).includes('chưa copy tin ngày 26/11'), await bao());

    console.log('\n-- giữ 14 ngày gần nhất --');
    await p.evaluate(() => {
      const t = {};
      for (let i = 1; i <= 20; i += 1) t[`qc9|2026-10-${String(i).padStart(2, '0')}`] = { luc: i, khoi: {}, tong: 0 };
      localStorage.setItem('sx-vh-da-gui-nhom', JSON.stringify(t));
    });
    await bam('#sx-vh-copy');
    const con = await p.evaluate(() => Object.keys(JSON.parse(localStorage.getItem('sx-vh-da-gui-nhom'))));
    kiem('21 bản → còn 14: bản vừa copy + 13 bản mới nhất (bỏ bản cũ nhất)',
      con.length === 14 && con.includes('qc1@xuong|2026-11-26') && !con.includes('qc9|2026-10-07')
      && con.includes('qc9|2026-10-08'), JSON.stringify(con));
    await p.evaluate(() => localStorage.setItem('sx-vh-da-gui-nhom', '{hỏng'));
    await mo('v=b&u=qc1@xuong');
    kiem('bản nhớ hỏng (không phải JSON) → coi như chưa copy, màn không lỗi', (await tt()) === null);
    await p.evaluate(() => localStorage.setItem('sx-vh-da-gui-nhom',
      JSON.stringify({ 'qc1@xuong|2026-11-25': { luc: 5, tong: 0 } })));
    await mo('v=b&u=qc1@xuong');
    kiem('bản nhớ của ngày này thiếu phần khối (hỏng dở) → coi như chưa copy, không kể cả nhóm là "đổi"',
      (await tt()) === null && (await nut()) === 'Copy thay đổi', `${await tt()} | ${await nut()}`);
    await bam('#sx-vh-copy');
    await p.evaluate(() => localStorage.removeItem('sx-vh-da-gui-nhom'));
    await p.click('.sx-vh-sl[data-i="0"]');
    for (const k of ['1', '6', '0']) await p.click(`.sx-modal .sx-numpad-key:text-is("${k}")`);
    await p.click('.sx-modal .sx-btn-primary');
    await p.waitForTimeout(400);
    kiem('bản nhớ bị xoá giữa chừng (dọn bộ nhớ) → lần vẽ sau ẩn dòng trạng thái, nút hết số — không treo trạng thái cũ',
      (await tt()) === null && (await nut()) === 'Copy thay đổi', `${await tt()} | ${await nut()}`);

    console.log('\n-- máy không cho chép → ô chép tay --');
    const p3 = await ctx.newPage();
    await p3.addInitScript(() => {
      Object.defineProperty(navigator, 'clipboard', { value: { writeText: () => Promise.reject(new Error('chặn')) } });
      document.execCommand = () => false;
    });
    await p3.goto(`${goc}/?v=a&u=qc7@xuong`);
    await p3.waitForFunction(() => window.SAN_SANG, null, { timeout: 10000 });
    await p3.click('#sx-vh-copy');
    await p3.waitForSelector('#sx-cp-text', { timeout: 3000 }).catch(() => {});
    const o3 = await p3.evaluate(() => ({ chu: (document.querySelector('#sx-cp-text') || {}).value || '',
      tt: document.querySelector('#sx-vh-copy-tt').hidden ? null : document.querySelector('#sx-vh-copy-tt').textContent }));
    kiem('copy đầy đủ rơi về ô chép tay → vẫn nhớ là đã copy (người dùng đang gửi đúng tin này)',
      o3.chu.startsWith('SẢN LƯỢNG 25/11/2026') && /^Đã copy lúc \d\d:\d\d — chưa có gì thay đổi\.$/.test(o3.tt || ''),
      JSON.stringify(o3));
    await p3.close();

    console.log('\n-- bộ nhớ trình duyệt bị chặn --');
    const p2 = await ctx.newPage();
    const loi2 = [];
    p2.on('pageerror', (e) => loi2.push(e.message));
    await p2.addInitScript(() => {
      Storage.prototype.getItem = () => { throw new Error('chặn'); };
      Storage.prototype.setItem = () => { throw new Error('chặn'); };
    });
    await p2.goto(`${goc}/?v=a&u=qc1@xuong`);
    await p2.waitForFunction(() => window.SAN_SANG, null, { timeout: 10000 });
    await p2.evaluate(() => navigator.clipboard.writeText('TRỐNG'));
    await p2.click('#sx-vh-copy');
    await p2.waitForTimeout(300);
    const c2 = await p2.evaluate(() => navigator.clipboard.readText());
    await p2.click('#sx-vh-copydoi');
    await p2.waitForTimeout(300);
    kiem('copy đầy đủ vẫn chạy, Copy thay đổi báo chưa copy, không lỗi JavaScript',
      c2.startsWith('SẢN LƯỢNG 25/11/2026') && (await p2.textContent('.sx-toast-wrap')).includes('chưa copy tin')
      && !loi2.length, loi2.join(' | '));
    kiem('không lỗi JavaScript suốt bài', !loi.length, loi.join(' | '));
  } finally {
    await b.close();
    srv.close();
  }
}

console.log(hong ? `COPYDOI: ${hong} HỎNG` : 'COPYDOI-OK');
process.exit(hong ? 1 : 0);
