// D234 — thẻ Phiếu lương: TỪNG NGÀY làm được những sản phẩm nào, số lượng, đơn giá, thành tiền, rồi dòng cộng ngày.
// Chromium thật, CSS thật (shell.css), màn điện thoại 360px, server giả.
//
// Vì sao phải có bài này: đây là chỗ công nhân hỏi "ngày 3 tôi làm gì mà ít tiền thế" và quản lý đọc to câu trả lời.
// Hỏng im lặng theo mấy hướng:
//   · cột lệch (đơn giá nằm ở cột thành tiền), giờ lẻ làm tròn, dòng giờ đọc như hộp;
//   · dòng chưa có giá hiện "0" như giá thật; dòng cộng ngày không khớp thu nhập ngày của phiếu (Chủ nhật × 1,2, tiền ăn);
//   · bảng rộng hơn màn điện thoại (phải kéo ngang mới thấy thành tiền); cuộn tới cuối tháng mất đầu cột;
//   · tên hàng lạ chèn HTML vào bảng.
// Chạy: node scripts/test-phieuluong.mjs   (verify.sh gọi sẵn). SX_SHOT=<thư mục> để chụp ảnh xem bằng mắt.

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

const CHROME = ['/opt/pw-browsers/chromium', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome']
  .find((f) => existsSync(f)) || '/opt/pw-browsers/chromium';
const PW = '/opt/node22/lib/node_modules/playwright/index.js';
if (!existsSync(CHROME) || !existsSync(PW)) {
  console.log('-- trình duyệt thật: BỎ QUA (máy này không có Chromium) --');
  console.log(hong ? `PHIEULUONG-JS-HỎNG (${hong})` : 'PHIEULUONG-JS-OK');
  process.exit(hong ? 1 : 0);
}

const PUB = join(GOC, 'sx/public/sx');
// Phiếu như server trả (sx.api.luong.chi_tiet): mỗi ngày `sp` đã gộp + xếp sẵn (sản phẩm trước, giờ sau, giá cao trước).
const PHIEU = {
  name: 'PL-1', ten: 'Nguyễn Thị An', thang: 11, nam: 2026, trang_thai: 'Nháp', da_duyet: false,
  ngay_cong: 2.5, ngay_san_xuat: 0, cong: [{ ten: 'Lương sản phẩm', tien: 15_772_400 }], tru: [],
  tong_tien: 15_822_400, tong_khau_tru: 0, thuc_nhan: 15_822_400,
  san_pham: [{ ten: 'Bánh đậu xanh sen', cach_lam: 'Máy', don_gia: 1200, so_luong: 110, thanh_tien: 132000 }],
  ngay: [
    { ngay: '2026-11-01', thu: 'Chủ nhật', an_ca: 1, an_dem: 0, tien_an: 20000, luong_sp: 214500, he_so: 1.2,
      so_gio: 2.5, thu_nhap: 277400,
      sp: [{ ten: 'Bánh đậu xanh sen', cach_lam: 'Máy', don_gia: 1200, so_luong: 110, thanh_tien: 132000 },
        { ten: 'Làm theo giờ', cach_lam: '', theo_gio: true, don_gia: 33000, so_luong: 2.5, thanh_tien: 82500 }] },
    { ngay: '2026-11-02', thu: 'Thứ 2', an_ca: 0, an_dem: 0, tien_an: 0, luong_sp: 90000, he_so: 1, so_gio: 3,
      thu_nhap: 90000,
      sp: [{ ten: 'Bánh TT', cach_lam: 'Tay', don_gia: 0, so_luong: 5, thanh_tien: 0 },
        { ten: 'Làm theo giờ', cach_lam: '', theo_gio: true, don_gia: 30000, so_luong: 3, thanh_tien: 90000 }] },
    { ngay: '2026-11-03', thu: 'Thứ 3', an_ca: 1, an_dem: 1, tien_an: 30000, luong_sp: 0, he_so: 1, so_gio: 0,
      thu_nhap: 30000, sp: [] },
    { ngay: '2026-11-04', thu: 'Thứ 4', an_ca: 0, an_dem: 0, tien_an: 0, luong_sp: 15_437_500, he_so: 1, so_gio: 0,
      thu_nhap: 15_437_500,
      sp: [{ ten: 'Bánh trung thu nhân đậu xanh sầu riêng trứng muối đặc biệt hộp bốn cái', cach_lam: 'Máy hỗ trợ',
        don_gia: 12500, so_luong: 1234, thanh_tien: 15_425_000 },
      { ten: 'Bánh <i>lạ</i>', cach_lam: '', don_gia: 1250, so_luong: 10, thanh_tien: 12500 }] },
  ],
  phat: [], ghi_chu: '',
};
const TRANG = `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/assets/sx/sx/shell.css"><body><div id="pl"></div>
<script type="module">
import { render } from '/assets/sx/sx/cards/phieuluong.js';
const PHIEU = ${JSON.stringify(PHIEU)};
const call = async (m) => {
  if (m === 'sx.api.luong.thang') {
    return { nam: 2026, thang: 11, tong: { so_nguoi: 1, luong_san_pham: 15772400, thuc_nhan: 15822400, da_duyet: 0,
      no_gia: 0 }, danh_sach: [{ name: 'PL-1', employee: 'NV1', ten_nhan_vien: 'Nguyễn Thị An', luong_san_pham: 15772400,
      luong_thuc_nhan: 15822400, ngay_cong: 2.5, da_duyet: false, no_gia: 0 }] };
  }
  if (m === 'sx.api.luong.chi_tiet') return PHIEU;
  return {};
};
await render({ container: document.getElementById('pl'), call, boot: { ngay_xem: '2026-11-09' } });
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
const p = await b.newPage({ viewport: { width: 360, height: 740 }, deviceScaleFactor: 1 });
const loi = [];
p.on('pageerror', (e) => loi.push(e.message));
const gon = (s) => (s || '').replace(/\s+/g, ' ').trim();
try {
  await p.goto(`http://127.0.0.1:${srv.address().port}/`);
  await p.waitForFunction(() => window.SAN_SANG, null, { timeout: 10000 });
  await p.click('#pl .sx-lich-nut');
  await p.waitForSelector('#pl .sx-pl-dong');
  await p.click('#pl .sx-pl-dong');
  await p.waitForSelector('.sx-modal table.sx-pl-ngay');

  console.log('-- bảng từng ngày --');
  const dau = await p.$$eval('.sx-pl-ngay thead th', (th) => th.map((x) => x.textContent.trim()));
  kiem('đầu bảng: Sản phẩm · SL · Đơn giá · Thành tiền', JSON.stringify(dau)
    === JSON.stringify(['Sản phẩm', 'SL', 'Đơn giá', 'Thành tiền']), JSON.stringify(dau));
  const ngay = (await p.$$eval('.sx-pl-ngay tbody', (tb) => tb.map((t) => [...t.rows].map((r) => [...r.cells]
    .map((c) => c.textContent))))).map((t) => t.map((r) => r.map(gon)));
  kiem('mỗi ngày một nhóm dòng, đúng thứ tự ngày của phiếu', ngay.length === 4
    && ngay.map((t) => t[0][0].slice(0, 5)).join() === '01/11,02/11,03/11,04/11', JSON.stringify(ngay.map((t) => t[0])));
  const [cn, t2, t3, t4] = ngay;
  kiem('Chủ nhật: đầu ngày ghi thứ + chấm ăn', JSON.stringify(cn[0]) === JSON.stringify(['01/11 · Chủ nhật · ăn ca']),
    JSON.stringify(cn[0]));
  kiem('… sản phẩm: tên · cách làm | số lượng | đơn giá | thành tiền — đúng cột',
    JSON.stringify(cn[1]) === JSON.stringify(['Bánh đậu xanh sen · Máy', '110', '1.200', '132.000']),
    JSON.stringify(cn[1]));
  kiem('… làm theo giờ: SL là số GIỜ, giờ lẻ không làm tròn (2,5 giờ × 33.000)',
    JSON.stringify(cn[2]) === JSON.stringify(['Làm theo giờ', '2,5 giờ', '33.000', '82.500']), JSON.stringify(cn[2]));
  kiem('… cộng ngày ghi phép tính (lương SP × 1,2 + tiền ăn) và đúng thu nhập ngày của phiếu',
    JSON.stringify(cn[3]) === JSON.stringify(['Cộng ngày (lương SP 214.500 × 1,2 + tiền ăn 20.000)', '277.400']),
    JSON.stringify(cn[3]));
  kiem('dòng CHƯA CÓ GIÁ: đơn giá ghi "⚠ chưa có giá", không phải "0" như giá thật',
    JSON.stringify(t2[1]) === JSON.stringify(['Bánh TT · Tay', '5', '⚠ chưa có giá', '0']), JSON.stringify(t2[1]));
  kiem('… giờ mức 30.000 hiện rõ đơn giá (quản lý — D233)',
    JSON.stringify(t2[2]) === JSON.stringify(['Làm theo giờ', '3 giờ', '30.000', '90.000']), JSON.stringify(t2[2]));
  kiem('… không hệ số, không tiền ăn → cộng ngày không cần phép tính',
    JSON.stringify(t2[3]) === JSON.stringify(['Cộng ngày', '90.000']), JSON.stringify(t2[3]));
  kiem('ngày chỉ chấm ăn: không dòng sản phẩm; cộng ngày = tiền ăn',
    JSON.stringify(t3) === JSON.stringify([['03/11 · Thứ 3 · ăn ca · ăn đêm'], ['Cộng ngày (tiền ăn 30.000)', '30.000']]),
    JSON.stringify(t3));
  kiem('số lớn có dấu chấm nghìn (1.234 × 12.500 = 15.425.000)',
    JSON.stringify(t4[1].slice(1)) === JSON.stringify(['1.234', '12.500', '15.425.000']), JSON.stringify(t4[1]));
  kiem('tên hàng lạ không chèn HTML vào bảng (hiện nguyên chữ)', t4[2][0] === 'Bánh <i>lạ</i>'
    && !(await p.$('.sx-pl-ngay i')), JSON.stringify(t4[2]));

  console.log('\n-- trên màn điện thoại 360px --');
  const tran = await p.evaluate(() => {
    const m = document.querySelector('.sx-modal');
    return { m: m.scrollWidth - m.clientWidth, trang: document.documentElement.scrollWidth - window.innerWidth };
  });
  kiem('bảng vừa màn: không phải kéo ngang (cả khung phiếu lẫn trang)', tran.m <= 0 && tran.trang <= 0,
    JSON.stringify(tran));
  const canh = await p.$eval('.sx-pl-ngay tbody tr:nth-child(2) td:nth-child(4)', (td) => getComputedStyle(td).textAlign);
  kiem('cột số căn phải (so hàng đơn vị)', canh === 'right', canh);
  const dinh = await p.evaluate(() => {
    const m = document.querySelector('.sx-modal');
    m.scrollTop = m.scrollHeight;
    const tren = m.getBoundingClientRect().top;
    const th = document.querySelector('.sx-pl-ngay thead th').getBoundingClientRect();
    const bang = document.querySelector('.sx-pl-ngay').getBoundingClientRect();
    return { lech: Math.round(th.top - tren), bangTop: Math.round(bang.top - tren) };
  });
  kiem('cuộn xuống cuối tháng: đầu cột vẫn dính sát mép trên khung (bảng đã trôi lên quá đầu)',
    Math.abs(dinh.lech) <= 1 && dinh.bangTop < 0, JSON.stringify(dinh));
  if (process.env.SX_SHOT) {
    await p.evaluate(() => { document.querySelector('.sx-modal').scrollTop = 0; });
    await p.screenshot({ path: join(process.env.SX_SHOT, 'phieuluong-dau.png') });
    await p.evaluate(() => { const m = document.querySelector('.sx-modal'); m.scrollTop = m.scrollHeight; });
    await p.screenshot({ path: join(process.env.SX_SHOT, 'phieuluong-cuoi.png') });
  }
  kiem('không lỗi JS trên trang', !loi.length, loi.join(' | '));
} catch (e) {
  hong += 1;
  console.log('  HỎNG ', e.message);
} finally {
  await b.close();
  srv.close();
}
console.log(hong ? `PHIEULUONG-JS-HỎNG (${hong})` : 'PHIEULUONG-JS-OK');
process.exit(hong ? 1 : 0);
