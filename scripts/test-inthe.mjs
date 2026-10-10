// Tem / thẻ QR in ra giấy được (lib/inthe.js — D186).
//
// Vì sao bài này đáng có: trước D186 QR vẽ bằng bảng ô có MÀU NỀN đen. Trình duyệt mặc
// định không in màu nền (ô "Đồ hoạ nền" tắt sẵn) — trên màn hình thấy QR, in ra tem trạm
// động vật gây hại / thẻ quét / thẻ đăng nhập thì trắng trơn, mà không lỗi nào hiện ra.
// Giờ QR là hình SVG (nội dung, luôn in). Bài này kiểm: hình SVG khớp ĐÚNG từng ô của mã
// (sai một ô là máy quét đọc sai / không đọc), có viền trắng 4 ô, và cả ba loại tem / thẻ
// không còn chỗ nào dựa vào màu nền.
//
// Nạp inthe.js + vendor/qrcode.js THẬT (đổi đường import sang tệp tạm).
// Chạy: node scripts/test-inthe.mjs   (verify.sh gọi sẵn)

import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const G = 'sx/public/sx/';
const tam = mkdtempSync(join(tmpdir(), 'inthe-'));
writeFileSync(join(tam, 'qrcode.mjs'), readFileSync(`${G}vendor/qrcode.js`, 'utf8'));
writeFileSync(join(tam, 'inthe.mjs'), readFileSync(`${G}lib/inthe.js`, 'utf8')
  .replace("'/assets/sx/sx/vendor/qrcode.js'", `'file://${join(tam, 'qrcode.mjs')}'`));
let html = '';
globalThis.Blob = class { constructor(p) { html = p.join(''); } };
globalThis.URL.createObjectURL = () => 'blob:x';
globalThis.URL.revokeObjectURL = () => {};
globalThis.window = { open: () => ({}) };
const I = await import(`file://${join(tam, 'inthe.mjs')}`);
const qrcode = (await import(`file://${join(tam, 'qrcode.mjs')}`)).default;
rmSync(tam, { recursive: true });

let hong = 0;
function kiem(ten, dk, ct = '') {
  if (!dk) hong += 1;
  console.log(`  ${dk ? 'ok  ' : 'HỎNG'} ${ten}${ct ? ` — ${ct}` : ''}`);
}

/** Đọc lại SVG của veQR → ma trận ô đen (gồm cả viền). */
function docSvg(svg) {
  const m = Number((svg.match(/viewBox="0 0 (\d+) \1"/) || [])[1] || 0);
  const o = Array.from({ length: m }, () => Array(m).fill(false));
  const d = (svg.match(/<path d="([^"]*)"/) || [])[1] || '';
  for (const [, x, y] of d.matchAll(/M(\d+) (\d+)h1v1h-1z/g)) o[Number(y)][Number(x)] = true;
  return { m, o, so: (d.match(/M/g) || []).length };
}

console.log('-- QR vẽ bằng SVG, khớp từng ô --');
const URL_TRAM = 'https://sx.example/sx#/qc/dvgh/R05';
const svg = I.veQR(URL_TRAM, 3);
const qr = qrcode(0, 'M');
qr.addData(URL_TRAM);
qr.make();
const n = qr.getModuleCount();
const { m, o, so } = docSvg(svg);
let lech = 0;
let den = 0;
for (let y = 0; y < m; y += 1) {
  for (let x = 0; x < m; x += 1) {
    const phai = y >= 4 && y < n + 4 && x >= 4 && x < n + 4 && qr.isDark(y - 4, x - 4);
    if (phai !== o[y][x]) lech += 1;
    if (phai) den += 1;
  }
}
kiem('mỗi ô đen của mã là một ô đen trên hình, đúng chỗ; viền trắng 4 ô quanh mã; không ô thừa',
  m === n + 8 && lech === 0 && so === den && den > 100, `${n}×${n}, lệch ${lech}`);
kiem('SVG có kích thước in thật (3 px / ô), nền trắng là hình chứ không phải màu nền, nét sắc khi in',
  svg.startsWith('<svg class="qr"') && svg.includes(`width="${m * 3}" height="${m * 3}"`)
  && svg.includes(`<rect width="${m}" height="${m}" fill="#fff"/>`) && svg.includes('fill="#000"')
  && svg.includes('shape-rendering="crispEdges"'));

console.log('\n-- ba loại tem / thẻ: không còn dựa vào màu nền --');
const khongNen = (h) => !/<td class="[ds]"/.test(h) && !/\.qr td/.test(h) && !/background:\s*#000/.test(h);
I.moTrangInTram([{ ma: 'R05', loai: 'Bẫy chuột', khu: 'Kho NL', url: URL_TRAM },
  { ma: 'C02', loai: 'Đèn côn trùng', khu: 'Xưởng', url: 'https://sx.example/sx#/qc/dvgh/C02' }]);
const tram = html;
kiem('tem trạm động vật gây hại: mỗi tem một QR SVG chứa đúng URL của trạm, mã trạm in to',
  (tram.match(/<svg class="qr"/g) || []).length === 2 && tram.includes(I.veQR(URL_TRAM, 3))
  && tram.includes('<div class="ma">R05</div>') && khongNen(tram));
I.moTrangInThe([{ ten: 'Nguyễn Văn A', ma: 'NV-001' }]);
kiem('thẻ quét công nhân: QR SVG, không màu nền', html.includes(I.veQR('NV-001', 3)) && khongNen(html));
I.moTrangInDangNhap([{ ten: 'QC 1', nhan_role: 'QC', link: 'https://sx.example/dn/abc', sdt: '0900', mat_khau: 'x' }]);
kiem('thẻ đăng nhập: QR SVG, không màu nền', html.includes(I.veQR('https://sx.example/dn/abc', 3)) && khongNen(html));

console.log(hong ? `\nINTHE-FAIL (${hong})` : '\nINTHE-OK');
process.exit(hong ? 1 : 0);
