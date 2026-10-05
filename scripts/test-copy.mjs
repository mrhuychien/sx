// D111 — nút "Copy sản lượng gửi nhóm" ở màn Ghi hộp.
//
// Lỗi thật: hàm copy nằm NGOÀI render() nhưng gọi `tenSP` chỉ sống TRONG render()
// → bấm nút là ReferenceError, không copy gì, không báo gì. Bài này bấm đúng cái
// nút đó trong Chromium thật và đọc lại clipboard.
//
// Phần 1 (Node): văn bản gửi nhóm đúng khuôn. Phần 2 (Chromium, nếu máy có).
// Chạy: node scripts/test-copy.mjs   (verify.sh gọi sẵn)

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

// ── Phần 1: hàm thuần (cắt import, thay formatNumber) ───────────────────
const src = readFileSync(join(GOC, 'sx/public/sx/cards/vaohop.js'), 'utf8')
  .split('\n').filter((d) => !d.startsWith('import ')).join('\n');
const tam = join(tmpdir(), `vh-${process.pid}.mjs`);
writeFileSync(tam, `const formatNumber = (n) => Number(n).toLocaleString('vi-VN');\n${src}`);
const { vanBanSanLuong } = await import(`file://${tam}`);
rmSync(tam);
console.log('-- văn bản gửi nhóm --');
const nhom = [
  { ten: 'An', dong: [{ san_pham: 'TP-SEN', so_hop: 120 }, { san_pham: 'TP-TT', so_hop: 30 }] },
  { ten: '★ Công nhật', dong: [{ nhan_vien: 'CONG_NHAT', san_pham: 'TP-SEN', so_hop: 50 }] },
];
const vb = vanBanSanLuong(nhom, '2026-10-05', (c) => ({ 'TP-SEN': 'Bánh sen', 'TP-TT': 'Bánh TT' }[c]));
kiem('tiêu đề có ngày dd/mm/yyyy', vb.startsWith('SẢN LƯỢNG 05/10/2026\n'), JSON.stringify(vb));
kiem('mỗi người một dòng, tên hàng thay mã', vb.includes('An (Bánh sen: 120, Bánh TT: 30)'));
kiem('KHÔNG có dòng công nhật', !vb.includes('Công nhật'), JSON.stringify(vb));
kiem('tổng chỉ tính công khoán (không cộng công nhật)', vb.trim().endsWith('— Tổng: 150 sản phẩm'));
kiem('mã không có tên → hiện "?" chứ không vỡ', vanBanSanLuong(
  [{ ten: 'B', dong: [{ san_pham: 'X', so_hop: 1 }] }], '', () => undefined).includes('B (?: 1)'));

// ── Phần 2: bấm nút thật trong Chromium ─────────────────────────────────
const CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PW = '/opt/node22/lib/node_modules/playwright/index.js';
if (!existsSync(CHROME) || !existsSync(PW)) {
  console.log('\n-- trình duyệt thật: BỎ QUA (máy này không có Chromium) --');
} else {
  console.log('\n-- trình duyệt thật: bấm "Copy sản lượng gửi nhóm" --');
  const PUB = join(GOC, 'sx/public/sx');
  const TRANG = `<!doctype html><meta charset="utf-8"><body><div id="c"></div>
<script type="module">
import { render } from '/assets/sx/sx/cards/vaohop.js';
const boot = { ngay_xem: '2026-10-05', ngay_sx: { name: 'N1', ngay: '2026-10-05', docstatus: 0 },
  bang_don_gia: 'BG', items_tp: [{ name: 'TP-SEN', item_name: 'Bánh đậu xanh sen' }],
  danh_muc_khoan: [], nhan_vien: [{ name: 'NV1', employee_name: 'Nguyễn Thị An', ten_hien_thi: 'An' }],
  bang_vao_hop: { dong: [{ nhan_vien: 'NV1', ten_nhan_vien: 'Nguyễn Thị An', san_pham: 'TP-SEN', so_hop: 120 },
    { nhan_vien: 'CONG_NHAT', ten_nhan_vien: 'Công nhật', cong_nhat: 1, san_pham: 'TP-SEN', so_hop: 50 }], an_ca: [] } };
await render({ container: document.getElementById('c'), boot, call: async () => ({}), ensureNgay: async () => boot.ngay_sx });
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
  await p.goto(goc + '/');
  await p.waitForFunction(() => window.SAN_SANG, null, { timeout: 10000 });
  await p.click('#sx-vh-copy');
  await p.waitForTimeout(500);
  const clip = await p.evaluate(() => navigator.clipboard.readText());
  await b.close();
  srv.close();
  kiem('bấm nút không lỗi JavaScript', !loi.length, loi.join(' | '));
  kiem('clipboard có sản lượng, tên hàng thay mã',
    clip.includes('SẢN LƯỢNG 05/10/2026') && clip.includes('An (Bánh đậu xanh sen: 120)'), JSON.stringify(clip));
  kiem('clipboard không có công nhật, tổng 120', !clip.includes('ông nhật') && clip.includes('Tổng: 120'));
}

console.log(hong ? `COPY: ${hong} HỎNG` : 'COPY-OK');
process.exit(hong ? 1 : 0);
