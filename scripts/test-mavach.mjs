// Kiểm bộ đọc mã vạch đóng gói trong repo (sx/public/sx/vendor/zxing1d.js).
//
// Vì sao phải có bài này (D78): xưởng dùng iPhone, mà Safari không có
// BarcodeDetector. Toàn bộ việc quét trên iPhone dựa vào file vendor này. Nếu nó
// hỏng — dựng lại sai, quy đổi độ sáng sai, tree-shake nhầm mất một bộ đọc — thì
// triệu chứng là "soi mãi không ăn", không có lỗi nào hiện ra. Đúng loại hỏng phải
// chặn bằng test.
//
// Chạy: node scripts/test-mavach.mjs   (verify.sh gọi sẵn)
//
// TỰ SINH mã vạch ngay trong file này, KHÔNG cài thư viện: bộ sinh và bộ đọc là hai
// bản cài đặt độc lập, khớp nhau mới có nghĩa. Dùng chung một thư viện cho cả hai
// đầu thì nó chỉ chứng minh thư viện đó nhất quán với chính nó.

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const goc = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { taoBoDoc } = await import(
  'file://' + path.join(goc, 'sx/public/sx/vendor/zxing1d.js'));
const doc = taoBoDoc();

// ───────────────────────────── bộ sinh EAN-13 ──
// Cấu trúc: 101 | 6 số trái (L/G theo số đầu) | 01010 | 6 số phải (R) | 101
const L = ['0001101', '0011001', '0010011', '0111101', '0100011',
  '0110001', '0101111', '0111011', '0110111', '0001011'];
const G = ['0100111', '0110011', '0011011', '0100001', '0011101',
  '0111001', '0000101', '0010001', '0001001', '0010111'];
const R = L.map((s) => s.split('').map((c) => (c === '0' ? '1' : '0')).join(''));
const CHAN_LE = ['LLLLLL', 'LLGLGG', 'LLGGLG', 'LLGGGL', 'LGLLGG',
  'LGGLLG', 'LGGGLL', 'LGLGLG', 'LGLGGL', 'LGGLGL'];

function kiemTraEan13(d12) {
  let t = 0;
  for (let i = 0; i < 12; i++) t += Number(d12[i]) * (i % 2 ? 3 : 1);
  return String((10 - (t % 10)) % 10);
}

function veEan13(d12) {
  const so = d12 + kiemTraEan13(d12);
  const mau = CHAN_LE[Number(so[0])];
  let bit = '101';
  for (let i = 1; i <= 6; i++) bit += (mau[i - 1] === 'L' ? L : G)[Number(so[i])];
  bit += '01010';
  for (let i = 7; i <= 12; i++) bit += R[Number(so[i])];
  bit += '101';
  return { bit, text: so };
}

// ───────────────────────────── bộ sinh Code 39 ──
// Mỗi ký tự 9 phần tử (5 vạch + 4 khoảng), 3 phần tử rộng. n = hẹp, w = rộng.
const C39 = {
  0: 'nnnwwnwnn', 1: 'wnnwnnnnw', 2: 'nnwwnnnnw', 3: 'wnwwnnnnn', 4: 'nnnwwnnnw',
  5: 'wnnwwnnnn', 6: 'nnwwwnnnn', 7: 'nnnwnnwnw', 8: 'wnnwnnwnn', 9: 'nnwwnnwnn',
  A: 'wnnnnwnnw', B: 'nnwnnwnnw', C: 'wnwnnwnnn', D: 'nnnnwwnnw', E: 'wnnnwwnnn',
  F: 'nnwnwwnnn', G: 'nnnnnwwnw', H: 'wnnnnwwnn', I: 'nnwnnwwnn', J: 'nnnnwwwnn',
  K: 'wnnnnnnww', L: 'nnwnnnnww', M: 'wnwnnnnwn', N: 'nnnnwnnww', O: 'wnnnwnnwn',
  P: 'nnwnwnnwn', Q: 'nnnnnnwww', R: 'wnnnnnwwn', S: 'nnwnnnwwn', T: 'nnnnwnwwn',
  U: 'wwnnnnnnw', V: 'nwwnnnnnw', W: 'wwwnnnnnn', X: 'nwnnwnnnw', Y: 'wwnnwnnnn',
  Z: 'nwwnwnnnn', '-': 'nwnnnnwnw', '.': 'wwnnnnwnn', ' ': 'nwwnnnwnn', '*': 'nwnnwnwnn',
};

function veCode39(text) {
  let bit = '';
  for (const c of `*${text}*`) {
    const mau = C39[c];
    if (!mau) throw new Error(`Code39 không có ký tự "${c}"`);
    for (let i = 0; i < 9; i++) {
      // phần tử chẵn = vạch (1), lẻ = khoảng (0); rộng = 3 đơn vị
      bit += (i % 2 ? '0' : '1').repeat(mau[i] === 'w' ? 3 : 1);
    }
    bit += '0';   // khoảng ngăn giữa hai ký tự
  }
  return { bit, text };
}

// ───────────────────────────── bit -> ảnh RGBA ──
function veAnh(bit, { dv = 3, cao = 60, le = 20, nghieng = 0 } = {}) {
  const w = bit.length * dv + le * 2;
  const h = cao + le * 2;
  const d = new Uint8ClampedArray(w * h * 4).fill(255);
  for (let y = le; y < le + cao; y++) {
    for (let i = 0; i < bit.length; i++) {
      if (bit[i] !== '1') continue;
      for (let k = 0; k < dv; k++) {
        // nghiêng: mỗi hàng dịch ngang một chút, mô phỏng cầm máy không thẳng
        const x = le + i * dv + k + Math.round((y - le) * nghieng);
        if (x < 0 || x >= w) continue;
        const o = (y * w + x) * 4;
        d[o] = 0; d[o + 1] = 0; d[o + 2] = 0;
      }
    }
  }
  return { data: d, w, h };
}

// ───────────────────────────── chạy ──
let hong = 0;
function kiem(ten, dk, ct = '') {
  if (!dk) hong++;
  console.log(`  ${dk ? 'ok  ' : 'HỎNG'} ${ten}${ct ? ` — ${ct}` : ''}`);
}

console.log('-- EAN-13 (mã in trên hộp bán lẻ) --');
for (const d12 of ['893850597419', '400638133393', '590123412345']) {
  const { bit, text } = veEan13(d12);
  const a = veAnh(bit);
  const got = doc(a.data, a.w, a.h);
  kiem(`EAN-13 ${text}`, got === text, `đọc ra ${JSON.stringify(got)}`);
}

// EAN-13 bắt đầu bằng 0 CHÍNH LÀ UPC-A — bộ đọc trả dạng 12 số. Không phải lỗi, và
// cũng không được lờ đi: ERPNext hay lưu dạng 13 số nên tra bảng phải chịu được cả hai.
{
  const { bit, text } = veEan13('000000000000');
  const a = veAnh(bit);
  const got = doc(a.data, a.w, a.h);
  kiem('EAN-13 đầu 0 -> trả dạng UPC-A 12 số', got === text.slice(1),
    `${JSON.stringify(text)} đọc ra ${JSON.stringify(got)}`);
}

console.log('\n-- Code 39 (tem nội bộ: mã Item có chữ và gạch) --');
for (const t of ['RVHG123', 'BD-SR-300-DL', 'TX300', 'A']) {
  const { bit } = veCode39(t);
  const a = veAnh(bit, { dv: 2 });
  const got = doc(a.data, a.w, a.h);
  kiem(`Code39 ${t}`, got === t, `đọc ra ${JSON.stringify(got)}`);
}

console.log('\n-- ảnh khó: vạch mảnh, mã thấp, cầm nghiêng --');
{
  const { bit, text } = veEan13('893850597419');
  for (const [ten, opt] of [
    ['vạch mảnh (1 điểm ảnh/đơn vị)', { dv: 1 }],
    ['mã thấp (cao 20px)', { dv: 2, cao: 20 }],
    ['cầm nghiêng nhẹ', { dv: 3, nghieng: 0.15 }],
  ]) {
    const a = veAnh(bit, opt);
    const got = doc(a.data, a.w, a.h);
    kiem(`EAN-13 ${ten}`, got === text, `${a.w}x${a.h} -> ${JSON.stringify(got)}`);
  }
}

console.log('\n-- không có mã thì phải trả null, KHÔNG được bịa ra số --');
kiem('khung trắng', doc(new Uint8ClampedArray(400 * 300 * 4).fill(255), 400, 300) === null);
{
  // Nhiễu ngẫu nhiên tất định (không dùng Math.random để chạy lại ra cùng kết quả)
  const n = 400 * 300;
  const d = new Uint8ClampedArray(n * 4);
  let x = 12345;
  for (let i = 0; i < n; i++) {
    x = (x * 1103515245 + 12345) & 0x7fffffff;
    const v = (x >> 16) & 0xff;
    d[i * 4] = v; d[i * 4 + 1] = v; d[i * 4 + 2] = v; d[i * 4 + 3] = 255;
  }
  const got = doc(d, 400, 300);
  kiem('khung nhiễu', got === null, `đọc ra ${JSON.stringify(got)}`);
}

console.log('\n-- tra bảng chịu được EAN-13 <-> UPC-A --');
{
  const src = fs.readFileSync(path.join(goc, 'sx/public/sx/components/quet.js'), 'utf8')
    .replace(/^import .*?;$/gm, '').replace(/^export /gm, '');
  const { traBang } = new Function(`${src}\nreturn { traBang };`)();
  const bangEan = { '0036000291452': 'ITEM-A' };   // ERPNext lưu 13 số
  const bangUpc = { '036000291452': 'ITEM-B' };    // ERPNext lưu 12 số
  kiem('đọc ra UPC-A 12 số, bảng lưu EAN-13',
    traBang(bangEan, '036000291452') === 'ITEM-A');
  kiem('đọc ra EAN-13 13 số, bảng lưu UPC-A',
    traBang(bangUpc, '0036000291452') === 'ITEM-B');
  kiem('khớp thẳng vẫn chạy', traBang(bangUpc, '036000291452') === 'ITEM-B');
  kiem('mã lạ vẫn là không tìm thấy',
    traBang(bangEan, '8938505974194') === undefined);
  kiem('KHÔNG nới cho mã chữ (tránh quét nhầm mã hàng)',
    traBang({ '0BD-SR': 'X' }, 'BD-SR') === undefined);
  kiem('KHÔNG bỏ số 0 đầu của mã 6 số', traBang({ 12345: 'X' }, '012345') === undefined);
}

console.log(hong ? `MAVACH-FAIL (${hong} ca)` : 'MAVACH-OK');
process.exit(hong ? 1 : 0);
