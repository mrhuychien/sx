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
const { vanBanSanLuong, coGiDeCopy, viTatCachLam } = await import(`file://${tam}`);
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

console.log('\n-- D231: ăn ca / ăn đêm trong tin gửi nhóm --');
const tenHang = (c) => ({ 'TP-SEN': 'Bánh sen', 'TP-TT': 'Bánh TT' }[c]);
const nhomAn = [
  { ten: 'An', dong: [{ nhan_vien: 'NV1', san_pham: 'TP-SEN', so_hop: 120 }] },
  { ten: 'Dũng', dong: [{ nhan_vien: 'NV4', _gio: 3 }] },                         // làm theo giờ (D225)
  { ten: 'Bình', dong: [{ nhan_vien: 'NV2', san_pham: 'TP-TT', so_hop: 30 }] },
  { ten: '★ Công nhật', dong: [{ nhan_vien: 'CONG_NHAT', san_pham: 'TP-SEN', so_hop: 50 }] },
];
const an = { NV1: { an_ca: 1, an_dem: 1 }, NV2: { an_ca: 2, an_dem: 0 }, NV3: { an_ca: 1, an_dem: 0 },
  NV4: { an_ca: 0, an_dem: 0, so_gio: 3 }, NV5: { an_ca: 0, an_dem: 0 }, CONG_NHAT: { an_ca: 5, an_dem: 5 } };
const vbAn = vanBanSanLuong(nhomAn, '2026-10-05', tenHang, an, (ma) => ({ NV3: 'Cúc', NV5: 'Em' }[ma] || ma));
kiem('mỗi người: sản lượng · chấm ăn (ăn ca + ăn đêm, ×2); người chỉ có chấm ăn vẫn có dòng; người không chấm ăn '
  + 'không thêm chữ; xếp theo tên; dòng cuối tổng suất ăn (không cộng mã giả)',
  vbAn === 'SẢN LƯỢNG 05/10/2026\n'
    + 'An (Bánh sen: 120) · ăn ca + ăn đêm\n'
    + 'Bình (Bánh TT: 30) · ăn ca ×2\n'
    + 'Cúc · ăn ca\n'
    + 'Dũng (Làm theo giờ: 3 giờ)\n'
    + '— Tổng: 150 sản phẩm\n'
    + '— Suất ăn: ăn ca 4 · ăn đêm 1', JSON.stringify(vbAn));
kiem('không ai được chấm ăn → không có dòng suất ăn, tin y như cũ',
  vanBanSanLuong(nhomAn, '2026-10-05', tenHang, { NV1: { an_ca: 0, an_dem: 0 } })
  === vanBanSanLuong(nhomAn, '2026-10-05', tenHang)
  && !vanBanSanLuong(nhomAn, '2026-10-05', tenHang).includes('Suất ăn'));
kiem('chỉ có ăn đêm → vẫn ghi đủ hai số (ăn ca 0)',
  vanBanSanLuong([], '', tenHang, { NV9: { an_dem: 1 } }, () => 'Hà').endsWith('Hà · ăn đêm\n— Tổng: 0 sản phẩm'
    + '\n— Suất ăn: ăn ca 0 · ăn đêm 1'));
console.log('\n-- D232: cách làm viết tắt --');
const vbCl = vanBanSanLuong([
  { ten: 'An', dong: [{ nhan_vien: 'NV1', san_pham: 'TP-SEN', cach_lam: 'Tay', so_hop: 50 },
    { nhan_vien: 'NV1', san_pham: 'TP-SEN', cach_lam: 'Máy', so_hop: 70 },
    { nhan_vien: 'NV1', san_pham: 'TP-TT', so_hop: 5 }] },
  { ten: 'Bình', dong: [{ nhan_vien: 'NV2', san_pham: 'TP-TT', cach_lam: 'máy', so_hop: 30 }] },
], '2026-10-05', tenHang, { NV2: { an_ca: 1 } });
kiem('mỗi dòng sản phẩm kèm cách làm viết tắt: Tay → T, Máy / "máy" → M; dòng không cách làm giữ như cũ',
  vbCl === 'SẢN LƯỢNG 05/10/2026\n'
    + 'An (Bánh sen (T): 50, Bánh sen (M): 70, Bánh TT: 5)\n'
    + 'Bình (Bánh TT (M): 30) · ăn ca\n'
    + '— Tổng: 155 sản phẩm\n'
    + '— Suất ăn: ăn ca 1 · ăn đêm 0', JSON.stringify(vbCl));
kiem('viết tắt: chữ đầu mỗi từ, viết hoa, bỏ khoảng trắng thừa; rỗng thì rỗng',
  viTatCachLam('Tay') === 'T' && viTatCachLam(' Máy ') === 'M' && viTatCachLam('Máy hỗ  trợ') === 'MHT'
  && viTatCachLam('đóng tay') === 'ĐT' && viTatCachLam('Máy\thỗ trợ') === 'MHT'   // tên dán từ Excel có tab
  && viTatCachLam('') === '' && viTatCachLam(null) === '');
kiem('có gì để copy: dòng hộp của người, hoặc một người được chấm ăn — mã giả / chấm 0 thì không',
  coGiDeCopy([], { NV3: { an_ca: 1 } }) && coGiDeCopy([nhomAn[0]], {})
  && !coGiDeCopy([nhomAn[3]], {}) && !coGiDeCopy([nhomAn[3]], { CONG_NHAT: { an_ca: 1 } })
  && !coGiDeCopy([], { NV1: { an_ca: 0, an_dem: 0, so_gio: 2 } }) && !coGiDeCopy([]));

// ── Phần 2: bấm nút thật trong Chromium ─────────────────────────────────
// Đường dẫn cố định của máy chạy thử (liên kết tới bản Chromium đang cài) — ghim số bản là máy đổi bản thì bài
// lặng lẽ BỎ QUA (D224).
const CHROME = ['/opt/pw-browsers/chromium', '/opt/pw-browsers/chromium-1194/chrome-linux/chrome']
  .find((f) => existsSync(f)) || '/opt/pw-browsers/chromium';
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
  danh_muc_khoan: [], nhan_vien: [{ name: 'NV1', employee_name: 'Nguyễn Thị An', ten_hien_thi: 'An' },
    { name: 'NV2', employee_name: 'Trần Văn Bình', ten_hien_thi: 'Bình' }],
  bang_vao_hop: { dong: [{ nhan_vien: 'NV1', ten_nhan_vien: 'Nguyễn Thị An', san_pham: 'TP-SEN', cach_lam: 'Máy',
    so_hop: 120 },
    { nhan_vien: 'CONG_NHAT', ten_nhan_vien: 'Công nhật', cong_nhat: 1, san_pham: 'TP-SEN', so_hop: 50 }],
    an_ca: [{ nhan_vien: 'NV1', an_ca: 1, an_dem: 1, so_gio: 0 }, { nhan_vien: 'NV2', an_ca: 1, an_dem: 0, so_gio: 0 }] } };
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
  await p.click('#sx-vh-tim');                       // ô tìm → xổ danh sách tên
  await p.waitForTimeout(200);
  const theAn = await p.textContent('.sx-nv-row[data-nv="NV1"]');
  await b.close();
  srv.close();
  kiem('bấm nút không lỗi JavaScript', !loi.length, loi.join(' | '));
  kiem('clipboard có sản lượng, tên hàng thay mã, cách làm viết tắt (D232: Máy → M)',
    clip.includes('SẢN LƯỢNG 05/10/2026') && clip.includes('An (Bánh đậu xanh sen (M): 120)'),
    JSON.stringify(clip));
  kiem('clipboard không có công nhật, tổng 120', !clip.includes('ông nhật') && clip.includes('Tổng: 120'));
  kiem('D231: clipboard kèm chấm ăn từng người (cả người chỉ có chấm ăn) + tổng suất ăn',
    clip.includes('An (Bánh đậu xanh sen (M): 120) · ăn ca + ăn đêm\nBình · ăn ca\n')
    && clip.endsWith('— Suất ăn: ăn ca 2 · ăn đêm 1'), JSON.stringify(clip));
  kiem('… thẻ tên trên màn vẫn ghi chấm ăn y như tin (cùng một hàm)', (theAn || '').includes('ăn ca + ăn đêm'),
    JSON.stringify(theAn));
}

console.log(hong ? `COPY: ${hong} HỎNG` : 'COPY-OK');
process.exit(hong ? 1 : 0);
