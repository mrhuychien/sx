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
const { vanBanSanLuong, coGiDeCopy, viTatCachLam, dam } = await import(`file://${tam}`);
rmSync(tam);
// D239: dòng sản phẩm = thụt 4 dấu cách không ngắt + gạch đầu dòng; tên, số là chữ đậm Unicode. `tron` đọc ngược tin về
// chữ thường (NFKC: chữ đậm → chữ thường, NBSP → dấu cách) — để soi NỘI DUNG (vd không lộ mức giá) bất kể kiểu chữ.
const T = '\u00a0'.repeat(4) + '- ';
const tron = (s) => s.normalize('NFKC');

console.log('-- D239: chữ đậm Unicode --');
const ma = (s) => [...s].map((c) => c.codePointAt(0).toString(16)).join(' ');
kiem('"Bình": chữ gốc sang Sans-Serif Bold (B → U+1D5D5…), GIỮ dấu huyền đi sau (U+0300)',
  dam('Bình') === '\u{1D5D5}\u{1D5F6}\u0300\u{1D5FB}\u{1D5F5}', ma(dam('Bình')));
kiem('chữ HOA không dấu đậm (U → U+1D5E8); chữ HOA CÓ dấu giữ nguyên nét thường — dấu kết hợp trên chữ hoa đậm đè '
  + 'lên đầu chữ ("Út" ra "Ưt"): "Út", "Ánh", "Ước", "Ạ" giữ chữ đầu dựng sẵn',
  dam('Ut') === '\u{1D5E8}\u{1D601}' && dam('Út') === '\u00da\u{1D601}' && dam('Ánh') === `\u00c1${dam('nh')}`
  && dam('Ước') === `\u01af${dam('ớc')}` && dam('Ạ') === '\u1ea0' && dam('AÁ') === '\u{1D5D4}\u00c1',
  [dam('Út'), dam('Ánh'), dam('Ước')].map(ma).join(' | '));
kiem('tên gõ dấu rời ("Unicode tổ hợp", vd Unikey để bảng mã tổ hợp) ra Y NHƯ tên gõ dựng sẵn',
  dam('Bi\u0300nh') === dam('Bình') && dam('U\u0301t') === dam('Út') && dam('\u0110u\u031b\u0301c') === dam('Đức'),
  ma(dam('U\u0301t')));
kiem('"Đức 2": Đ không có bản đậm → giữ nguyên; ư = u + móc + sắc; số đậm (2 → U+1D7EE); dấu cách giữ',
  dam('Đức 2') === 'Đ\u{1D602}\u031B\u0301\u{1D5F0} \u{1D7EE}', ma(dam('Đức 2')));
kiem('số kiểu Việt "1.234,5": chữ số đậm (0 → U+1D7EC, 9 → U+1D7F5), dấu chấm / phẩy giữ nguyên',
  dam('1.234,5') === '\u{1D7ED}.\u{1D7EE}\u{1D7EF}\u{1D7F0},\u{1D7F1}' && dam('09') === '\u{1D7EC}\u{1D7F5}',
  ma(dam('1.234,5')));
kiem('A–Z, a–z đủ hai đầu (A → U+1D5D4, Z → U+1D5ED, a → U+1D5EE, z → U+1D607)',
  dam('AZaz') === '\u{1D5D4}\u{1D5ED}\u{1D5EE}\u{1D607}', ma(dam('AZaz')));
kiem('rỗng / null / undefined → chuỗi rỗng (không ra chữ "null")', dam('') === '' && dam(null) === '' && dam(undefined) === '');
const ten = ['Nguyễn Thị Ánh', 'Đặng Văn Út', 'Lê Hữu Phước', 'Trương Mỹ Lệ', 'Hoàng Ngọc Ẩn', 'Phạm Quỳnh Ỷ',
  'Võ Thị Ỡ', 'Huỳnh Ấu Ặc', 'Đỗ Đình Đông', 'Bùi Thị Ợt'];
kiem('tên Việt đủ thanh, dấu chồng (ễ, ặ, ượ…): không sót chữ / số thường; đọc ngược (NFKC) ra đúng tên gốc',
  ten.every((x) => !/[A-Za-z0-9]/.test(dam(x)) && tron(dam(x)) === x.normalize('NFC')),
  ten.filter((x) => /[A-Za-z0-9]/.test(dam(x)) || tron(dam(x)) !== x.normalize('NFC')).join(', '));
kiem('dam không tách dấu chữ không đổi được: "Đ" vẫn là MỘT ký tự U+0110', dam('Đ') === '\u0110' && dam('đ') === '\u0111');
kiem('chữ không có bản đậm giữ NGUYÊN DẠNG, không bị tách dấu (tách để đổi chữ gốc rồi ghép lại): "ά" Hy Lạp, "Å"',
  dam('ά') === '\u03ac' && dam('ά b') === `\u03ac ${dam('b')}` && dam('Å').normalize('NFKC') === '\u00c5',
  ma(dam('ά')));

console.log('\n-- văn bản gửi nhóm --');
const nhom = [
  { ten: 'An', dong: [{ san_pham: 'TP-SEN', so_hop: 120 }, { san_pham: 'TP-TT', so_hop: 30 }] },
  { ten: '★ Công nhật', dong: [{ nhan_vien: 'CONG_NHAT', san_pham: 'TP-SEN', so_hop: 50 }] },
];
const vb = vanBanSanLuong(nhom, '2026-10-05', (c) => ({ 'TP-SEN': 'Bánh sen', 'TP-TT': 'Bánh TT' }[c]));
kiem('D239: tiêu đề có ngày dd/mm/yyyy, rồi một dòng trống',
  vb.startsWith('SẢN LƯỢNG 05/10/2026\n\n') && !vb.startsWith('SẢN LƯỢNG 05/10/2026\n\n\n'), JSON.stringify(vb));
kiem('D239: mỗi người một khối — tên ĐẬM; mỗi sản phẩm một dòng thụt + gạch đầu dòng, tên hàng thay mã, số ĐẬM',
  vb === `SẢN LƯỢNG 05/10/2026\n\n${dam('An')}\n${T}Bánh sen: ${dam('120')}\n${T}Bánh TT: ${dam('30')}\n\n`
    + `— Tổng: ${dam('150')} sản phẩm`, JSON.stringify(vb));
kiem('… dòng sản phẩm thụt bằng dấu cách KHÔNG NGẮT (U+00A0), không phải dấu cách thường (có nơi gộp làm một)',
  vb.includes('\n\u00a0\u00a0\u00a0\u00a0- Bánh sen') && !/\n {2,}-/.test(vb), JSON.stringify(vb));
kiem('KHÔNG có dòng công nhật (soi cả bản đọc ngược — tên in đậm không lách được)',
  !tron(vb).includes('ông nhật') && !/: 50(\n|$)/.test(tron(vb)), JSON.stringify(vb));
kiem('tổng chỉ tính công khoán (không cộng công nhật), số ĐẬM', vb.endsWith(`— Tổng: ${dam('150')} sản phẩm`));
kiem('mã không có tên → hiện "?" chứ không vỡ', vanBanSanLuong(
  [{ ten: 'B', dong: [{ san_pham: 'X', so_hop: 1 }] }], '', () => undefined).includes(`${dam('B')}\n${T}?: ${dam('1')}`));

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
kiem('mỗi người: tên ĐẬM · chấm ăn (ăn ca + ăn đêm, ×2) rồi các dòng sản phẩm / giờ; người chỉ có chấm ăn vẫn có '
  + 'khối; người không chấm ăn không thêm chữ; xếp theo tên; khối cách dòng trống; cuối là tổng suất ăn (không cộng mã giả)',
  vbAn === 'SẢN LƯỢNG 05/10/2026\n\n'
    + `${dam('An')} · ăn ca + ăn đêm\n${T}Bánh sen: ${dam('120')}\n\n`
    + `${dam('Bình')} · ăn ca ×2\n${T}Bánh TT: ${dam('30')}\n\n`
    + `${dam('Cúc')} · ăn ca\n\n`
    + `${dam('Dũng')}\n${T}Làm theo giờ: ${dam('3')} giờ\n\n`
    + `— Tổng: ${dam('150')} sản phẩm\n`
    + `— Suất ăn: ăn ca ${dam('4')} · ăn đêm ${dam('1')}`, JSON.stringify(vbAn));
kiem('không ai được chấm ăn → không có dòng suất ăn, tin y như cũ',
  vanBanSanLuong(nhomAn, '2026-10-05', tenHang, { NV1: { an_ca: 0, an_dem: 0 } })
  === vanBanSanLuong(nhomAn, '2026-10-05', tenHang)
  && !vanBanSanLuong(nhomAn, '2026-10-05', tenHang).includes('Suất ăn'));
kiem('chỉ có ăn đêm → vẫn ghi đủ hai số (ăn ca 0)',
  vanBanSanLuong([], '', tenHang, { NV9: { an_dem: 1 } }, () => 'Hà') === `SẢN LƯỢNG\n\n${dam('Hà')} · ăn đêm\n\n`
    + `— Tổng: ${dam('0')} sản phẩm\n— Suất ăn: ăn ca ${dam('0')} · ăn đêm ${dam('1')}`);
console.log('\n-- D232: cách làm viết tắt --');
const vbCl = vanBanSanLuong([
  { ten: 'An', dong: [{ nhan_vien: 'NV1', san_pham: 'TP-SEN', cach_lam: 'Tay', so_hop: 50 },
    { nhan_vien: 'NV1', san_pham: 'TP-SEN', cach_lam: 'Máy', so_hop: 70 },
    { nhan_vien: 'NV1', san_pham: 'TP-TT', so_hop: 5 }] },
  { ten: 'Bình', dong: [{ nhan_vien: 'NV2', san_pham: 'TP-TT', cach_lam: 'máy', so_hop: 30 }] },
], '2026-10-05', tenHang, { NV2: { an_ca: 1 } });
kiem('mỗi dòng sản phẩm kèm cách làm viết tắt: Tay → T, Máy / "máy" → M; dòng không cách làm giữ như cũ; '
  + 'thứ tự dòng = thứ tự ghi',
  vbCl === 'SẢN LƯỢNG 05/10/2026\n\n'
    + `${dam('An')}\n${T}Bánh sen (T): ${dam('50')}\n${T}Bánh sen (M): ${dam('70')}\n${T}Bánh TT: ${dam('5')}\n\n`
    + `${dam('Bình')} · ăn ca\n${T}Bánh TT (M): ${dam('30')}\n\n`
    + `— Tổng: ${dam('155')} sản phẩm\n`
    + `— Suất ăn: ăn ca ${dam('1')} · ăn đêm ${dam('0')}`, JSON.stringify(vbCl));
const vbGio = vanBanSanLuong([
  { ten: 'An', dong: [{ nhan_vien: 'NV1', san_pham: 'TP-SEN', cach_lam: 'Tay', so_hop: 50 },
    { nhan_vien: 'NV1', _gio: 2, _muc: 'so_gio', _gia: 33000 }, { nhan_vien: 'NV1', _gio: 3.5, _muc: 'so_gio_2', _gia: 30000 }] },
  { ten: 'Bình', dong: [{ nhan_vien: 'NV2', _gio: 4, _muc: 'so_gio_2', _gia: 30000 }] },
], '2026-11-08', tenHang);
kiem('D233: giờ MỌI mức của một người gộp MỘT dòng "Làm theo giờ: tổng" (sau các dòng hộp), không ghi mức / đơn giá '
  + '(tránh tị nạnh) — soi cả bản đọc ngược, số in đậm không lách được',
  vbGio === `SẢN LƯỢNG 08/11/2026\n\n${dam('An')}\n${T}Bánh sen (T): ${dam('50')}\n${T}Làm theo giờ: ${dam('5,5')} giờ\n\n`
    + `${dam('Bình')}\n${T}Làm theo giờ: ${dam('4')} giờ\n\n— Tổng: ${dam('50')} sản phẩm`
    && !/30\.000|33\.000|30000|33000|đ\/giờ|mức/.test(tron(vbGio)),
  JSON.stringify(vbGio));
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
  const luc = Date.now();
  await p.click('#sx-vh-copy');
  await p.waitForTimeout(500);
  const clip = await p.evaluate(() => navigator.clipboard.readText());
  const baoCopy = await p.textContent('.sx-toast-wrap');
  await p.click('#sx-vh-tim');                       // ô tìm → xổ danh sách tên
  await p.waitForTimeout(200);
  const theAn = await p.textContent('.sx-nv-row[data-nv="NV1"]');
  // Toast thường tắt sau 3,5 giây — lời nhắc dài phải đứng lâu hơn (6 giây) mới kịp đọc.
  await p.waitForTimeout(Math.max(0, luc + 4500 - Date.now()));
  const baoSau = await p.evaluate(() => [...document.querySelectorAll('.sx-toast-show')].map((x) => x.textContent).join('|'));
  // Máy không cho chép (Clipboard API bị chặn, execCommand hỏng — chuyện thường trên điện thoại xưởng) → hiện ô chữ để
  // người dùng tự bấm giữ chép.
  const p2 = await ctx.newPage();
  await p2.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: () => Promise.reject(new Error('chặn')) } });
    document.execCommand = () => false;
  });
  await p2.goto(goc + '/');
  await p2.waitForFunction(() => window.SAN_SANG, null, { timeout: 10000 });
  await p2.click('#sx-vh-copy');
  await p2.waitForSelector('#sx-cp-text', { timeout: 3000 }).catch(() => {});
  const chepTay = await p2.evaluate(() => ({ chu: (document.querySelector('#sx-cp-text') || {}).value || '',
    nhac: (document.querySelector('.sx-modal .sx-modal-msg') || {}).textContent || '' }));
  await b.close();
  srv.close();
  kiem('bấm nút không lỗi JavaScript', !loi.length, loi.join(' | '));
  kiem('clipboard có sản lượng, tên hàng thay mã, cách làm viết tắt (D232: Máy → M)',
    clip.includes('SẢN LƯỢNG 05/10/2026') && tron(clip).includes('- Bánh đậu xanh sen (M): 120'),
    JSON.stringify(clip));
  kiem('D239: qua clipboard thật vẫn giữ chữ đậm, thụt dấu cách không ngắt, dòng trống giữa người',
    clip.includes(`${dam('An')} · ăn ca + ăn đêm\n${T}Bánh đậu xanh sen (M): ${dam('120')}\n\n${dam('Bình')} · ăn ca\n\n`),
    JSON.stringify(clip));
  kiem('clipboard không có công nhật, tổng 120', !tron(clip).includes('ông nhật') && clip.includes(`Tổng: ${dam('120')}`));
  kiem('D231: clipboard kèm chấm ăn từng người (cả người chỉ có chấm ăn) + tổng suất ăn',
    clip.endsWith(`— Suất ăn: ăn ca ${dam('2')} · ăn đêm ${dam('1')}`), JSON.stringify(clip));
  kiem('D239: báo copy xong kèm lời nhắc chữ to (cỡ chữ không đi theo chữ copy — chọn trong Zalo)',
    (baoCopy || '').includes('Đã copy') && (baoCopy || '').includes('giữ nút Gửi'), JSON.stringify(baoCopy));
  kiem('… lời nhắc còn trên màn sau 4,5 giây (toast thường tắt sau 3,5 giây — câu dài không kịp đọc)',
    baoSau.includes('giữ nút Gửi'), JSON.stringify(baoSau));
  kiem('không chép được → ô chữ để chép tay: đúng nguyên tin (chữ đậm, thụt) + lời nhắc chữ to',
    !!chepTay.chu && chepTay.chu === clip && chepTay.nhac.includes('giữ nút Gửi'), JSON.stringify(chepTay));
  kiem('… thẻ tên trên màn vẫn ghi chấm ăn y như tin (cùng một hàm)', (theAn || '').includes('ăn ca + ăn đêm'),
    JSON.stringify(theAn));
}

console.log(hong ? `COPY: ${hong} HỎNG` : 'COPY-OK');
process.exit(hong ? 1 : 0);
