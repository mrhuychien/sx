// D204 — nhãn "⚠ lỗi đồng bộ" trên thanh ngày bấm được: câu lỗi + cách xử lý + THỬ LẠI tại chỗ.
//
// Vì sao phải có bài này: trước D204 nhãn chỉ nói "xem lịch ở Quản lý" — người đang ở chính màn
// Quản lý không biết lịch ở đâu, lỗi nằm im. Hai chỗ dễ hỏng im lặng:
//   · nhãn nằm DƯỚI ô date trong suốt phủ cả khối ngày → bấm vào chỉ mở bảng chọn ngày;
//   · hộp lỗi gọi sai API / không vẽ lại sau THỬ LẠI / cho người không phải quản lý bấm.
//
// Phần 1 (Node): cách xử lý theo câu lỗi. Phần 2 (Chromium thật, nếu máy có): CSS thật của
// thanh ngày + hộp lỗi thật, bấm nút, đọc lời gọi API.
// Chạy: node scripts/test-loidongbo.mjs   (verify.sh gọi sẵn)

import { existsSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { dirname, join, resolve, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

const GOC = resolve(dirname(fileURLToPath(import.meta.url)), '..');
let hong = 0;
const kiem = (ten, dk, ct = '') => {
  if (!dk) hong += 1;
  console.log(`  ${dk ? 'ok  ' : 'HỎNG'} ${ten}${ct ? ` — ${ct}` : ''}`);
};

// ── Phần 1: cách xử lý theo câu lỗi (hàm thuần) ─────────────────────────
const src = readFileSync(join(GOC, 'sx/public/sx/components/dongbo.js'), 'utf8')
  .split('\n').filter((d) => !d.startsWith('import ')).join('\n');
const tam = join(tmpdir(), `db-${process.pid}.mjs`);
writeFileSync(tam, src);
const { goiY } = await import(`file://${tam}`);
rmSync(tam);
console.log('-- cách xử lý theo câu lỗi --');
const ca = [
  ["'SXBangVaoHopItem' object is not subscriptable", 'migrate'],
  ['Thiếu giá vốn: Đường kính — khai giá ở lịch Đồng bộ (màn Quản lý) rồi bấm Thử lại.', 'KHAI GIÁ VỐN'],
  ['Phiếu lương PL-0012 của An tháng 10/2026 ĐÃ DUYỆT — không ghi thêm được.', 'huỷ duyệt'],
  ['Bột bánh: chưa có BOM active', 'tạo BOM'],
  ['Bột bánh: 12.5 đơn vị Đậu xanh cần thêm trong Kho NVL để hoàn thành giao dịch này', 'nhập mua'],
  ['Bột bánh: Insufficient Stock — 40 units of DX needed in NVL', 'nhập mua'],
  ['Ngày cũ chưa từng chốt trước khi bỏ chốt (D123) — kiểm lại số liệu rồi bấm Thử lại.', 'D123'],
  ['Bột bánh: Batch No BB-131026 of Item BB has negative stock', 'nhập mua'],
  ['Bột bánh: Batch BB-131026 không thuộc mã BB', 'lô'],
  ['Lỗi lạ chưa gặp bao giờ', 'chụp màn'],
];
ca.forEach(([loi, can]) => kiem(`"${loi.slice(0, 48)}…" → ${can}`, goiY(loi).includes(can), goiY(loi)));

// ── Nối dây trong shell.js ───────────────────────────────────────────────
const shell = readFileSync(join(GOC, 'sx/public/sx/shell.js'), 'utf8');
console.log('\n-- dây nối trong shell.js --');
kiem('nhãn lỗi không còn bảo "xem lịch ở Quản lý" mà bảo bấm', !shell.includes('xem lịch ở Quản lý')
  && shell.includes("'⚠ lỗi đồng bộ — bấm xem'"));
kiem('nhãn lỗi mang lớp nổi trên ô date + cờ data-loi', shell.includes('sx-day-tag-nut')
  && shell.includes("tag.dataset.loi = loiDb && !store.tuBoNho ? '1' : ''"));
kiem('bấm nhãn mở hộp lỗi (components/dongbo.js), chặn bảng chọn ngày',
  shell.includes("import(withV('/assets/sx/sx/components/dongbo.js'))") && shell.includes('e.stopPropagation();'));
kiem('quyền THỬ LẠI theo boot.is_quan_ly (thẻ lịch đồng bộ chỉ cho quản lý)',
  shell.includes('quanLy: !!store.boot.is_quan_ly'));

// ── Phần 2: Chromium thật ────────────────────────────────────────────────
const CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PW = '/opt/node22/lib/node_modules/playwright/index.js';
if (!existsSync(CHROME) || !existsSync(PW)) {
  console.log('\n-- trình duyệt thật: BỎ QUA (máy này không có Chromium) --');
} else {
  const PUB = join(GOC, 'sx/public/sx');
  // Thanh ngày lấy NGUYÊN khuôn trong shell.js — đổi khuôn ở đó là bài này đọc theo.
  const khuon = /daybar\.innerHTML = `([\s\S]*?)`;/.exec(shell)[1];
  const TRANG = `<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="/assets/sx/sx/shell.css">
<body><div id="sx-app"><div class="sx-daybar">${khuon}</div></div>
<script type="module">
import { moDongBo } from '/assets/sx/sx/components/dongbo.js';
window.CALLS = [];
window.XONG = 0;
window.TRA = [];
const call = async (m, a) => {
  window.CALLS.push([m, a]);
  if (m === 'sx.api.dongbo.thu_lai') return window.TRA.shift();
  if (m === 'sx.api.chot.thieu_gia_von_ngay') return [];
  return {};
};
window.mo = (ngay, quanLy) => moDongBo({ ngay, call, quanLy, xong: () => { window.XONG += 1; } });
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
  const pw = (await import(PW)).default;
  const b = await pw.chromium.launch({ executablePath: CHROME });
  const p = await b.newPage({ viewport: { width: 390, height: 800 } });
  const loi = [];
  p.on('pageerror', (e) => loi.push(e.message));
  await p.goto(`http://127.0.0.1:${srv.address().port}/`);
  await p.waitForFunction(() => window.SAN_SANG, null, { timeout: 10000 });

  console.log('\n-- thanh ngày (CSS thật): bấm trúng nhãn lỗi --');
  const trung = (lop) => p.evaluate((l) => {
    const t = document.getElementById('sx-day-tag');
    t.className = l;
    t.textContent = '⚠ lỗi đồng bộ — bấm xem';
    const r = t.getBoundingClientRect();
    return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2).id;
  }, lop);
  kiem('nhãn lỗi nổi TRÊN ô date trong suốt — bấm vào là trúng nhãn',
    (await trung('sx-day-tag sx-day-chot sx-day-tag-nut')) === 'sx-day-tag');
  kiem('(đối chứng) nhãn thường vẫn nằm dưới ô date — bấm là mở bảng chọn ngày như cũ',
    (await trung('sx-day-tag sx-day-chot')) === 'sx-day-input');

  console.log('\n-- hộp lỗi đồng bộ --');
  const ngay = { name: 'N1', ngay: '2026-10-13', dong_bo: {
    gs: { cho: 1, loi: 'Thiếu giá vốn: Đường kính — khai giá ở lịch Đồng bộ (màn Quản lý) rồi bấm Thử lại.' },
    vh: { cho: 1, loi: "'SXBangVaoHopItem' object is not subscriptable" } } };
  await p.evaluate((n) => window.mo(n, true), ngay);
  const phan = await p.$$eval('.sx-modal .sx-db-phan', (ds) => ds.map((d) => ({
    k: d.dataset.phan, loi: d.querySelector('.sx-lc-loi').textContent,
    cach: d.querySelector('.sx-db-goiy').textContent })));
  kiem('tiêu đề có ngày', (await p.textContent('.sx-modal-kicker')).includes('13/10'));
  kiem('hai phần lỗi, mỗi phần câu lỗi nguyên văn + cách xử lý đúng loại',
    phan.length === 2 && phan[0].k === 'gs' && phan[0].cach.includes('KHAI GIÁ VỐN')
    && phan[1].k === 'vh' && phan[1].loi.includes('not subscriptable') && phan[1].cach.includes('migrate'),
    JSON.stringify(phan));
  const nut = await p.$$eval('.sx-modal button.sx-btn', (ds) => ds.map((d) => d.textContent.trim()));
  kiem('quản lý: có KHAI GIÁ VỐN (lỗi giá vốn) và THỬ LẠI', JSON.stringify(nut) === '["KHAI GIÁ VỐN","THỬ LẠI"]',
    JSON.stringify(nut));
  await p.click('.sx-modal button:has-text("KHAI GIÁ VỐN")');
  await p.waitForTimeout(150);
  kiem('KHAI GIÁ VỐN hỏi đúng ngày', (await p.evaluate(() => window.CALLS)).some(([m, a]) =>
    m === 'sx.api.chot.thieu_gia_von_ngay' && a.ngay_sx === 'N1'));

  await p.evaluate(() => { window.TRA.push({ gs: { cho: 1, loi: 'Bột bánh: chưa có BOM active' },
    vh: { cho: 0, loi: null } }); });
  await p.click('.sx-modal button:has-text("THỬ LẠI")');
  await p.waitForTimeout(200);
  let goi = (await p.evaluate(() => window.CALLS)).filter(([m]) => m === 'sx.api.dongbo.thu_lai');
  kiem('THỬ LẠI gọi thu_lai đúng phiếu ngày', goi.length === 1 && goi[0][1].ngay_sx === 'N1', JSON.stringify(goi));
  const con = await p.$$eval('.sx-modal .sx-db-phan', (ds) => ds.map((d) => d.dataset.phan + ':'
    + d.querySelector('.sx-db-goiy').textContent));
  kiem('còn lỗi: hộp vẽ lại đúng phần còn lỗi + cách xử lý mới; màn được vẽ lại (thanh ngày)',
    con.length === 1 && con[0].startsWith('gs:') && con[0].includes('BOM')
    && (await p.evaluate(() => window.XONG)) === 1, JSON.stringify(con));
  kiem('hết lỗi giá vốn thì không còn nút KHAI GIÁ VỐN',
    !(await p.$('.sx-modal button:has-text("KHAI GIÁ VỐN")')));
  await p.evaluate(() => { window.TRA.push({ gs: { cho: 0, loi: null }, vh: { cho: 0, loi: null } }); });
  await p.click('.sx-modal button:has-text("THỬ LẠI")');
  await p.waitForTimeout(200);
  kiem('hết lỗi: đóng hộp, vẽ lại màn', !(await p.$('.sx-modal')) && (await p.evaluate(() => window.XONG)) === 2);

  await p.evaluate((n) => window.mo(n, false), ngay);
  kiem('không phải quản lý: thấy lỗi + cách xử lý, KHÔNG có nút THỬ LẠI / KHAI GIÁ VỐN',
    (await p.$$('.sx-modal .sx-db-phan')).length === 2 && !(await p.$('.sx-modal button.sx-btn'))
    && (await p.textContent('.sx-modal')).includes('Chỉ quản lý bấm THỬ LẠI'));
  await p.click('.sx-modal-close');

  await b.close();
  srv.close();
  kiem('không lỗi JavaScript', !loi.length, loi.join(' | '));
}

console.log(hong ? `LOIDONGBO: ${hong} HỎNG` : 'LOIDONGBO-OK');
process.exit(hong ? 1 : 0);
