// D109 — nén ảnh lưu mẫu trên máy trước khi gửi (sx/public/sx/lib/anh.js).
//
// Hỏng theo hai hướng, cả hai đều im lặng:
//   · nén không tới → ảnh 4 MB đi thẳng lên server: chờ lâu trên 4G, server từ chối
//     (> 1,5 MB), ổ đĩa đầy dần theo năm;
//   · nén quá tay → ảnh bé, mờ, không đọc được chữ HSD — mà đó là lý do chụp.
//
// Phần 1 (Node): hàm thuần tinhKichThuoc + nenVongLap với bộ mã hoá giả.
// Phần 2 (Chromium thật, nếu máy có): nén một ảnh 4000×3000 nhiễu như ảnh chụp.
// Chạy: node scripts/test-anh.mjs   (verify.sh gọi sẵn)

import { existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const GOC = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const A = await import(join(GOC, 'sx/public/sx/lib/anh.js'));

let hong = 0;
const kiem = (ten, dk, ct = '') => {
  if (!dk) hong += 1;
  console.log(`  ${dk ? 'ok  ' : 'HỎNG'} ${ten}${ct ? ` — ${ct}` : ''}`);
};

console.log('-- kích thước --');
kiem('ảnh 4000×3000 → cạnh dài 1600, giữ tỉ lệ',
  JSON.stringify(A.tinhKichThuoc(4000, 3000)) === JSON.stringify({ w: 1600, h: 1200 }));
kiem('ảnh dọc 3000×4000 → 1200×1600 (không xoay ngang)',
  JSON.stringify(A.tinhKichThuoc(3000, 4000)) === JSON.stringify({ w: 1200, h: 1600 }));
kiem('ảnh nhỏ hơn giới hạn giữ nguyên',
  JSON.stringify(A.tinhKichThuoc(800, 600)) === JSON.stringify({ w: 800, h: 600 }));

console.log('\n-- vòng nén (bộ mã hoá giả: byte ∝ điểm ảnh × chất lượng) --');
const gia = (heSo) => {
  const goi = [];
  const f = async (w, h, q) => { goi.push([w, h, q]); return { size: Math.round(w * h * q * heSo) }; };
  return { f, goi };
};
let g = gia(0.1);
let kq = await A.nenVongLap(g.f, 4000, 3000);
kiem('ảnh dễ nén: đạt ngay ở chất lượng đầu, không hạ chất lượng vô ích',
  g.goi.length === 1 && kq.chatLuong === 0.82 && kq.w === 1600, JSON.stringify(g.goi));
g = gia(0.25);
kq = await A.nenVongLap(g.f, 4000, 3000);
kiem('ảnh khó hơn: hạ chất lượng từng bậc tới khi dưới mục tiêu',
  kq.blob.size <= A.TOI_DA && kq.chatLuong < 0.82 && kq.w === 1600, JSON.stringify(kq));
g = gia(0.6);
kq = await A.nenVongLap(g.f, 4000, 3000);
kiem('ảnh rất khó: thu nhỏ thêm khi chất lượng đã chạm đáy',
  kq.blob.size <= A.TOI_DA && kq.w < 1600, JSON.stringify(kq));
g = gia(50);
kq = await A.nenVongLap(g.f, 4000, 3000);
kiem('không bao giờ thu nhỏ dưới mức đọc được chữ (cạnh dài ≥ 640)',
  Math.max(kq.w, kq.h) >= 640, JSON.stringify(kq));
kiem('… và vòng nén luôn dừng', g.goi.length < 60, String(g.goi.length));
kiem('hiện dung lượng dễ đọc', A.kb(3.2 * 1024 * 1024) === '3,2 MB' && A.kb(215 * 1024) === '215 KB');

// ── Phần 2: Chromium thật ────────────────────────────────────────────────
const CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PW = '/opt/node22/lib/node_modules/playwright/index.js';
if (!existsSync(CHROME) || !existsSync(PW)) {
  console.log('\n-- trình duyệt thật: BỎ QUA (máy này không có Chromium) --');
} else {
  console.log('\n-- trình duyệt thật: nén ảnh 4000×3000 nhiễu như ảnh chụp --');
  const srv = createServer((req, res) => {
    if (req.url.startsWith('/anh.js')) {
      res.writeHead(200, { 'Content-Type': 'text/javascript' });
      res.end(readFileSync(join(GOC, 'sx/public/sx/lib/anh.js')));
    } else { res.writeHead(200, { 'Content-Type': 'text/html' }); res.end('<!doctype html><body>'); }
  });
  await new Promise((r) => srv.listen(0, r));
  const pw = (await import(PW)).default;
  const b = await pw.chromium.launch({ executablePath: CHROME });
  const p = await b.newPage();
  await p.goto(`http://127.0.0.1:${srv.address().port}/`);
  const ra = await p.evaluate(async () => {
    const A2 = await import('/anh.js');
    const tao = async (w, h, kieu) => {
      const c = document.createElement('canvas');
      c.width = w; c.height = h;
      const g2 = c.getContext('2d');
      const d = g2.createImageData(w, h);
      for (let i = 0; i < d.data.length; i += 4) {        // nhiễu: khó nén như ảnh thật
        const v = (Math.sin(i / 97) * 60 + 128 + Math.random() * 70) | 0;
        d.data[i] = v; d.data[i + 1] = (v * 0.8) | 0; d.data[i + 2] = (v * 0.6) | 0;
        d.data[i + 3] = kieu === 'image/png' && i < d.data.length / 2 ? 0 : 255;
      }
      g2.putImageData(d, 0, 0);
      const blob = await new Promise((ok) => c.toBlob(ok, kieu, 0.95));
      return new File([blob], kieu === 'image/png' ? 'a.png' : 'a.jpg', { type: kieu });
    };
    const out = {};
    const ngang = await tao(4000, 3000, 'image/jpeg');
    const n1 = await A2.nenAnh(ngang);
    out.ngang = { truoc: n1.truoc, sau: n1.sau, w: n1.w, h: n1.h, b64: n1.base64.slice(0, 4) };
    const doc = await tao(1500, 2000, 'image/jpeg');
    const n2 = await A2.nenAnh(doc);
    out.doc = { w: n2.w, h: n2.h };
    const png = await tao(1200, 900, 'image/png');
    const n3 = await A2.nenAnh(png);
    const bmp = await createImageBitmap(n3.blob);
    const c = document.createElement('canvas'); c.width = 4; c.height = 4;
    c.getContext('2d').drawImage(bmp, 0, 0, 4, 4, 0, 0, 4, 4);
    out.png = { kieu: n3.blob.type, goc: Array.from(c.getContext('2d').getImageData(0, 0, 1, 1).data) };
    return out;
  });
  await b.close();
  srv.close();
  kiem('ảnh chụp 4000×3000 nén xuống dưới mục tiêu', ra.ngang.sau <= A.TOI_DA,
    `${A.kb(ra.ngang.truoc)} → ${A.kb(ra.ngang.sau)}`);
  kiem('… nhỏ hơn ảnh gốc nhiều lần', ra.ngang.sau * 4 < ra.ngang.truoc);
  kiem('… cạnh dài 1600 (còn đọc được chữ HSD)', Math.max(ra.ngang.w, ra.ngang.h) >= 1200,
    `${ra.ngang.w}×${ra.ngang.h}`);
  kiem('… gửi đi là JPEG (base64 bắt đầu /9j/)', ra.ngang.b64 === '/9j/');
  kiem('ảnh dọc vẫn dọc', ra.doc.h > ra.doc.w, `${ra.doc.w}×${ra.doc.h}`);
  kiem('PNG trong suốt → nền TRẮNG, không thành đen',
    ra.png.kieu === 'image/jpeg' && ra.png.goc[0] > 240 && ra.png.goc[1] > 240, JSON.stringify(ra.png));
}

console.log(hong ? `ANH: ${hong} HỎNG` : 'ANH-OK');
process.exit(hong ? 1 : 0);
