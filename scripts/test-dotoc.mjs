// D210 — bảng đo tốc độ (?do=1): lib/do.js + lib/api.js trong Chromium thật, máy chủ giả trả Server-Timing.
//
// Vì sao phải có bài này: bảng đo là thứ dùng để quyết định SỬA CHỖ NÀO. Sai thì sửa nhầm:
//   · không xin máy chủ đo (thiếu header X-Sx-Do) → cột "máy chủ" trống, tưởng chậm do mạng;
//   · đọc nhầm Server-Timing / lấy lời gọi của màn trước → đổ lỗi nhầm API;
//   · bật đo khi KHÔNG có ?do=1 → mọi người dùng chịu thêm việc, máy chủ bọc SQL mọi lời gọi.
// Chạy: node scripts/test-dotoc.mjs   (verify.sh gọi sẵn)

import { existsSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, join, resolve, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const GOC = resolve(dirname(fileURLToPath(import.meta.url)), '..');
let hong = 0;
const kiem = (ten, dk, ct = '') => {
  if (!dk) hong += 1;
  console.log(`  ${dk ? 'ok  ' : 'HỎNG'} ${ten}${ct && !dk ? ` — ${ct}` : ''}`);
};

// ── dây nối trong shell.js (đọc mã) ─────────────────────────────────────
const shell = readFileSync(join(GOC, 'sx/public/sx/shell.js'), 'utf8');
console.log('-- dây nối trong shell.js --');
kiem('mỗi thẻ gắn qua doThe (ghi nạp mã / vẽ xong), y như cũ khi không đo',
  shell.includes("await doThe(name, () => import(withV(path)), (mod) => mod.render(cardApi(wrap)));"));
kiem('router: batDauMan trước khi tải boot, xongMan(BUILD) sau khi màn vẽ xong',
  /batDauMan\(viewName\);\s*try \{\s*if \(!store\.boot\)/.test(shell)
  && /await loader\(main\);\s*xongMan\(BUILD\);/.test(shell));

const CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PW = '/opt/node22/lib/node_modules/playwright/index.js';
if (!existsSync(CHROME) || !existsSync(PW)) {
  console.log('\n-- trình duyệt thật: BỎ QUA (máy này không có Chromium) --');
  console.log(hong ? `DOTOC-JS: ${hong} HỎNG` : 'DOTOC-JS-OK');
  process.exit(hong ? 1 : 0);
}

const PUB = join(GOC, 'sx/public/sx');
const TRANG = `<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="/assets/sx/sx/shell.css">
<body><div class="sx-app" id="app"></div>
<script type="module">
import { call } from '/assets/sx/sx/lib/api.js';
import { DO, batDauMan, doThe, xongMan } from '/assets/sx/sx/lib/do.js';
window.DO = DO;
window.chay = async (ten) => {
  batDauMan(ten);
  const kq = await Promise.allSettled([
    doThe('kiemke', () => import('/assets/sx/sx/lib/format.js'), async () => {
      await call('sx.api.thu.cham');
      return 'vẽ';
    }),
    doThe('lohsd', () => import('/assets/sx/sx/lib/dom.js'), async () => { await call('sx.api.thu.nhanh'); }),
    doThe('hong', async () => { throw new Error('không tải được thẻ'); }, async () => {}),
  ]);
  await xongMan('sx-thu');
  return kq.map((x) => x.status + ':' + (x.value || (x.reason && x.reason.message) || ''));
};
// Màn KHÔNG chờ thẻ của nó (gắn thẻ rồi trả về ngay): bảng đo phải tự chờ thẻ vẽ xong mới tính.
window.chayKhongCho = async (ten) => {
  batDauMan(ten);
  doThe('thecham', () => import('/assets/sx/sx/lib/format.js'), async () => { await call('sx.api.thu.cham'); });
  await xongMan('sx-thu');
};
window.SAN_SANG = true;
</script>`;

const HEADER_DO = [];
const srv = createServer((req, res) => {
  const u = decodeURIComponent(req.url.split('?')[0]);
  if (u.startsWith('/assets/sx/sx/')) {
    const f = normalize(join(PUB, u.slice('/assets/sx/sx/'.length)));
    if (f.startsWith(PUB) && existsSync(f)) {
      res.writeHead(200, { 'Content-Type': f.endsWith('.js') ? 'text/javascript' : 'text/css',
        'Cache-Control': 'no-store' });
      res.end(readFileSync(f)); return;
    }
    res.writeHead(404); res.end(); return;
  }
  if (u.startsWith('/api/method/')) {
    const xin = !!req.headers['x-sx-do'];
    HEADER_DO.push([u, xin]);
    const cham = u.endsWith('.cham');
    setTimeout(() => {
      res.writeHead(200, { 'Content-Type': 'application/json',
        ...(xin ? { 'Server-Timing': cham ? 'sx;dur=110.5, sql;dur=80.2;desc="42"'
          : 'sx;dur=3.2, sql;dur=1.0;desc="2"' } : {}) });
      res.end(JSON.stringify({ message: cham ? 'x'.repeat(20000) : 1 }));
    }, cham ? 150 : 5);
    return;
  }
  const doTrang = /[?&]do=1/.test(req.url);
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8',
    ...(doTrang ? { 'Server-Timing': 'sx;dur=320.0, sql;dur=150.0;desc="77"' } : {}) });
  res.end(TRANG);
});
await new Promise((r) => srv.listen(0, '127.0.0.1', r));
const goc = `http://127.0.0.1:${srv.address().port}`;
const pw = (await import(PW)).default;
const b = await pw.chromium.launch({ executablePath: CHROME });
const ctx = await b.newContext({ permissions: ['clipboard-read', 'clipboard-write'],
  viewport: { width: 390, height: 800 } });
const p = await ctx.newPage();
const loi = [];
p.on('pageerror', (e) => loi.push(e.message));

console.log('\n-- KHÔNG có ?do=1: không đo gì --');
await p.goto(`${goc}/#/nhapkho`);
await p.waitForFunction(() => window.SAN_SANG, null, { timeout: 10000 });
let kq = await p.evaluate(() => window.chay('nhapkho'));
kiem('thẻ vẽ như thường (kết quả / lỗi của thẻ giữ nguyên)',
  kq[0] === 'fulfilled:vẽ' && kq[2] === 'rejected:không tải được thẻ', JSON.stringify(kq));
kiem('không gửi X-Sx-Do (máy chủ không bọc SQL của người dùng thường)', HEADER_DO.length === 2
  && HEADER_DO.every(([, xin]) => !xin), JSON.stringify(HEADER_DO));
kiem('không hiện bảng đo', !(await p.$('#sx-do')) && (await p.evaluate(() => window.DO)) === false);

console.log('\n-- /sx?do=1: đo và hiện bảng --');
HEADER_DO.length = 0;
await p.goto(`${goc}/?do=1#/nhapkho`);
await p.waitForFunction(() => window.SAN_SANG, null, { timeout: 10000 });
kq = await p.evaluate(() => window.chay('nhapkho'));
kiem('thẻ vẫn vẽ / báo lỗi như thường khi đang đo', kq[0] === 'fulfilled:vẽ' && kq[2] === 'rejected:không tải được thẻ',
  JSON.stringify(kq));
kiem('mọi lời gọi API gửi X-Sx-Do', HEADER_DO.length === 2 && HEADER_DO.every(([, xin]) => xin),
  JSON.stringify(HEADER_DO));
const chu = await p.textContent('#sx-do .sx-do-chu');
const dong = chu.split('\n');
kiem('đầu bảng: màn, build', dong[0].startsWith('⏱ ĐO TỐC ĐỘ — màn nhapkho — sx-thu — '), dong[0]);
kiem('trang HTML: nhận xong lúc nào + máy chủ / SQL theo Server-Timing của trang',
  /^Trang HTML: nhận xong [\d.]+ ms sau lúc mở · máy chủ 320 ms \(SQL 77 câu, 150 ms\)$/.test(dong[1]), dong[1]);
kiem('màn vẽ đủ sau bao lâu kể từ lúc mở trang', /^Màn vẽ đủ: [\d.]+ ms sau lúc mở trang$/.test(dong[2]), dong[2]);
const js = dong.find((d) => d.startsWith('JS/CSS:'));
const JS_RE = new RegExp('^JS/CSS: \\d+ tệp · \\d+ tải mới \\([\\d,]+ KB\\) · \\d+ hỏi lại máy chủ · '
  + '\\d+ từ bộ nhớ đệm · chậm nhất \\S+\\.(js|css) [\\d.]+ ms$');
kiem('JS/CSS: số tệp, tải mới / hỏi lại / bộ nhớ đệm, tệp chậm nhất', JS_RE.test(js || ''), js);
const iApi = dong.findIndex((d) => d.startsWith('API ('));
kiem('API: 2 lời gọi, chậm nhất trước', dong[iApi] === 'API (2 lời gọi, chậm nhất trước): tổng · máy chủ · SQL · cỡ',
  dong[iApi]);
const m1 = /^\s+([\d.]+) ms · 111 ms · 42 câu 80 ms · ([\d,]+) KB {2}thu\.cham$/.exec(dong[iApi + 1] || '');
kiem('… dòng 1 = thu.cham: tổng ≥ 150 ms, máy chủ 111 ms, 42 câu SQL 80 ms, ~20 KB, bỏ tiền tố sx.api.',
  m1 && Number(m1[1].replace(/\./g, '')) >= 150 && /^19|^20/.test(m1[2]), dong[iApi + 1]);
kiem('… dòng 2 = thu.nhanh', / ms · 3 ms · 2 câu 1 ms · .* {2}thu\.nhanh$/.test(dong[iApi + 2] || ''), dong[iApi + 2]);
const iThe = dong.indexOf('Thẻ (vẽ xong lúc · nạp mã):');
const the = dong.slice(iThe + 1);
kiem('Thẻ: đủ 3, xếp theo lúc vẽ xong; thẻ hỏng ghi LỖI', iThe > 0 && the.length === 3
  && the.some((d) => /kiemke$/.test(d)) && the.some((d) => /lohsd$/.test(d))
  && the.some((d) => d.endsWith('hong — LỖI: không tải được thẻ'))
  && /kiemke$/.test(the[2]), JSON.stringify(the));

const css = await p.evaluate(() => {
  const h = document.getElementById('sx-do');
  const s = getComputedStyle(h);
  const r = h.getBoundingClientRect();
  return { pos: s.position, z: s.zIndex, font: getComputedStyle(h.querySelector('.sx-do-chu')).fontFamily,
    trong: r.left >= 0 && r.right <= innerWidth && r.bottom <= innerHeight && r.top >= 0,
    tran: document.documentElement.scrollWidth - innerWidth };
});
kiem('bảng nằm cố định trong màn hình (điện thoại 390px), dưới hộp thoại, chữ đều; trang không cuộn ngang',
  css.pos === 'fixed' && css.z === '1050' && /monospace|Menlo|Consolas/.test(css.font) && css.trong && css.tran <= 0,
  JSON.stringify(css));
await p.click('#sx-do [data-do="chep"]');
await p.waitForTimeout(150);
const clip = await p.evaluate(() => navigator.clipboard.readText());
kiem('CHÉP → bộ nhớ tạm có nguyên văn bảng, nút đổi thành ĐÃ CHÉP',
  clip === chu && (await p.textContent('#sx-do [data-do="chep"]')) === 'ĐÃ CHÉP');

console.log('\n-- chuyển sang màn khác (không tải lại trang) --');
HEADER_DO.length = 0;
await p.evaluate(() => window.chay('quanly'));
const chu2 = await p.textContent('#sx-do .sx-do-chu');
const d2 = chu2.split('\n');
kiem('cùng một bảng, cập nhật cho màn mới; không còn dòng trang HTML; tính từ lúc bấm chuyển màn',
  (await p.$$('#sx-do')).length === 1 && d2[0].includes('màn quanly') && !d2.some((d) => d.startsWith('Trang HTML'))
  && /^Màn vẽ đủ: [\d.]+ ms sau lúc bấm chuyển màn$/.test(d2[1]), JSON.stringify(d2.slice(0, 3)));
kiem('chỉ lời gọi của màn mới (2), không lẫn màn trước',
  d2.includes('API (2 lời gọi, chậm nhất trước): tổng · máy chủ · SQL · cỡ'), JSON.stringify(d2));
kiem('nút trở lại CHÉP cho bảng mới', (await p.textContent('#sx-do [data-do="chep"]')) === 'CHÉP');
await p.click('#sx-do [data-do="dong"]');
kiem('✕ đóng bảng', !(await p.$('#sx-do')));

console.log('\n-- màn không chờ thẻ của nó --');
await p.evaluate(() => window.chayKhongCho('tet'));
const d3 = (await p.textContent('#sx-do .sx-do-chu')).split('\n');
const ve3 = Number(((/^Màn vẽ đủ: ([\d.]+) ms/.exec(d3[1]) || [])[1] || '0').replace(/\./g, ''));
kiem('bảng tự chờ thẻ đang vẽ: có dòng thẻ, có lời gọi của nó, "vẽ đủ" ≥ 150 ms máy chủ giả trả chậm',
  d3.some((d) => /thecham$/.test(d)) && d3.some((d) => /thu\.cham$/.test(d)) && ve3 >= 150, JSON.stringify(d3));

await b.close();
srv.close();
kiem('không lỗi JavaScript', !loi.length, loi.join(' | '));
console.log(hong ? `DOTOC-JS: ${hong} HỎNG` : 'DOTOC-JS-OK');
process.exit(hong ? 1 : 0);
