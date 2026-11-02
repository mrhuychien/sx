// D225 — công khoán làm theo giờ ở màn Ghi hộp + dòng giờ trên thẻ Phiếu lương. Chromium thật, server giả.
//
// Vì sao phải có bài này: số giờ là tiền lương, nhập bằng bàn số có phím phẩy. Hỏng im lặng theo mấy hướng:
//   · gõ 2,5 mà lưu 2 hoặc 25; bàn số hiện tiền sai;
//   · lưu giờ mà gửi kèm ăn ca / ăn đêm cũ của máy này → đè phần QC khác vừa chấm (và ngược lại: chấm ăn đè số giờ);
//   · người chỉ làm theo giờ không hiện trong bảng ghi / không tính là đã nhập; ✕ không bỏ được giờ;
//   · công nhật có lối "làm theo giờ" (công nhật không phải một người);
//   · thẻ phiếu lương in "2,5 × 33.000" như 2,5 hộp, hoặc làm tròn giờ lẻ.
// Chạy: node scripts/test-giocong.mjs   (verify.sh gọi sẵn)

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
  console.log(hong ? `GIOCONG-JS-HỎNG (${hong})` : 'GIOCONG-JS-OK');
  process.exit(hong ? 1 : 0);
}

const PUB = join(GOC, 'sx/public/sx');
const TRANG = `<!doctype html><meta charset="utf-8"><body><div id="vh"></div><div id="pl"></div>
<script type="module">
import { render as veVH } from '/assets/sx/sx/cards/vaohop.js';
import { render as vePL } from '/assets/sx/sx/cards/phieuluong.js';
window.CALLS = [];
// Server giả gộp bảng chấm theo người ĐÚNG như portal.luu_bang_vao_hop: khoá nào gửi mới đổi.
window.AN = { NV1: { nhan_vien: 'NV1', an_ca: 0, an_dem: 1, so_gio: 0 } };
const call = async (m, a) => {
  window.CALLS.push([m, a]);
  if (m === 'sx.api.portal.luu_bang_vao_hop') {
    JSON.parse(a.an_ca || '[]').forEach((d) => {
      const g = window.AN[d.nhan_vien] || (window.AN[d.nhan_vien] = { nhan_vien: d.nhan_vien, an_ca: 0, an_dem: 0, so_gio: 0 });
      ['an_ca', 'an_dem', 'so_gio'].forEach((k) => { if (k in d) g[k] = d[k]; });
    });
    const an = Object.values(window.AN).filter((g) => g.an_ca || g.an_dem || g.so_gio > 0)
      .map((g) => ({ ...g, tien_gio: g.so_gio * 33000 }));
    return { dong: JSON.parse(a.rows), an_ca: an };
  }
  if (m === 'sx.api.luong.thang') {
    return { nam: 2026, thang: 11, tong: { so_nguoi: 1, luong_san_pham: 214500, thuc_nhan: 214500, da_duyet: 0, no_gia: 0 },
      danh_sach: [{ name: 'PL-1', employee: 'NV1', ten_nhan_vien: 'Nguyễn Thị An', luong_san_pham: 214500,
        luong_thuc_nhan: 214500, ngay_cong: 1, da_duyet: false, no_gia: 0 }] };
  }
  if (m === 'sx.api.luong.chi_tiet') {
    return { name: 'PL-1', ten: 'Nguyễn Thị An', thang: 11, nam: 2026, trang_thai: 'Nháp', da_duyet: false,
      ngay_cong: 1, ngay_san_xuat: 0, cong: [{ ten: 'Lương sản phẩm', tien: 214500 }], tru: [],
      tong_tien: 214500, tong_khau_tru: 0, thuc_nhan: 214500,
      san_pham: [{ ten: 'Làm theo giờ', cach_lam: '', theo_gio: true, don_gia: 33000, so_luong: 2.5, thanh_tien: 82500 },
        { ten: 'Bánh sen', cach_lam: '', don_gia: 1200, so_luong: 110, thanh_tien: 132000 }],
      ngay: [{ ngay: '2026-11-01', thu: 'Chủ nhật', an_ca: 1, an_dem: 0, luong_sp: 214500, he_so: 1.2, so_gio: 2.5,
        thu_nhap: 257400 }], phat: [], ghi_chu: '' };
  }
  return {};
};
const ngay = { name: 'N1', ngay: '2026-11-02', docstatus: 0 };
const boot = { ngay_xem: '2026-11-02', la_hom_nay: true, ngay_sx: ngay, bang_don_gia: 'BG', don_gia_gio: 33000,
  items_tp: [{ name: 'TP-SEN', item_name: 'Bánh đậu xanh sen' }],
  danh_muc_khoan: [{ item: 'TP-SEN', ten: 'Bánh đậu xanh sen', dvt: 'Hộp', cach_lam: [], gia_chung: 1000, chua_gia: false }],
  nhan_vien: [{ name: 'NV1', employee_name: 'Nguyễn Thị An', ten_hien_thi: 'An' },
    { name: 'NV2', employee_name: 'Trần Văn Bình', ten_hien_thi: 'Bình' }],
  bang_vao_hop: { dong: [{ name: 'R1', nhan_vien: 'NV1', ten_nhan_vien: 'Nguyễn Thị An', san_pham: 'TP-SEN', so_hop: 100 }],
    an_ca: [{ nhan_vien: 'NV1', an_ca: 0, an_dem: 1, so_gio: 0 }] } };
await veVH({ container: document.getElementById('vh'), boot, call, ensureNgay: async () => ngay });
await vePL({ container: document.getElementById('pl'), call, boot });
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
const ctx = await b.newContext({ permissions: ['clipboard-read', 'clipboard-write'] });
const p = await ctx.newPage();
const loi = [];
p.on('pageerror', (e) => loi.push(e.message));
try {
  await p.goto(`http://127.0.0.1:${srv.address().port}/`);
  await p.waitForFunction(() => window.SAN_SANG, null, { timeout: 10000 });
  const goi = async () => (await p.evaluate(() => window.CALLS))
    .filter(([m]) => m === 'sx.api.portal.luu_bang_vao_hop').map(([, a]) => JSON.parse(a.an_ca));
  const bam = async (k) => p.click(`.sx-modal .sx-numpad-key:text-is("${k}")`);
  const khung = async () => (await p.textContent('.sx-modal .sx-numpad-display')).replace(/\s+/g, ' ').trim();
  const doi = () => p.waitForTimeout(200);

  console.log('-- màn Ghi hộp: lối Làm theo giờ --');
  await p.click('#vh .sx-vh-them[data-nv="NV1"]');
  kiem('chọn mã cho An: có lối ⏱ LÀM THEO GIỜ (thay cho mã hàng)', !!(await p.$('.sx-modal #sx-sp-gio')));
  await p.click('.sx-modal #sx-sp-gio');
  kiem('bấm vào → bàn số "Số giờ" cho An', (await p.textContent('.sx-modal')).includes('Làm theo giờ')
    && (await khung()).toUpperCase().includes('SỐ GIỜ'), await khung());
  kiem('… có phím phẩy (giờ lẻ)', !!(await p.$('.sx-modal .sx-numpad-key:text-is(",")')));
  await bam('2'); await bam(','); await bam('5');
  kiem('gõ 2,5 → ô số 2.5, bên cạnh hiện tiền 2,5 × 33.000 = 82.500 đ', (await khung()).includes('2.5')
    && (await khung()).includes('82.500 đ'), await khung());
  await p.click('.sx-modal .sx-btn-primary');
  await doi();
  let g = await goi();
  kiem('XONG → lưu ĐÚNG khoá vừa đổi: {NV1, so_gio 2.5} — không gửi ăn ca / ăn đêm (không đè QC khác)',
    JSON.stringify(g.at(-1)) === JSON.stringify([{ nhan_vien: 'NV1', so_gio: 2.5 }]), JSON.stringify(g));
  const dongGio = async (nv) => p.$(`#vh .sx-vh-gio-sl[data-gio="${nv}"]`);
  kiem('bảng ghi: dòng ⏱ Làm theo giờ của An, nút số "2,5 giờ"',
    (await (await dongGio('NV1')).textContent()).trim() === '2,5 giờ'
    && (await p.textContent('#vh .sx-vh-row-gio')).includes('⏱ Làm theo giờ'));
  kiem('… chân bảng: tổng giờ + số người', (await p.textContent('#sx-vh-footer')).replace(/\s+/g, ' ')
    .includes('làm theo giờ 2,5 giờ (1 người)'), await p.textContent('#sx-vh-footer'));
  kiem('… hộp không đổi (100) — giờ không cộng vào số hộp', (await p.textContent('#sx-vh-tonghop')).trim() === '100');

  console.log('\n-- người CHỈ làm theo giờ --');
  await p.focus('#sx-vh-tim');
  await p.click('#vh .sx-nv-row[data-nv="NV2"]');
  await p.click('.sx-modal #sx-sp-gio');
  await bam('4');
  await p.click('.sx-modal .sx-numpad-hang button:not(.sx-btn-primary)');      // + GHI TIẾP
  await doi();
  g = await goi();
  kiem('Bình 4 giờ, + GHI TIẾP → lưu rồi quay lại chọn mã cho Bình',
    JSON.stringify(g.at(-1)) === JSON.stringify([{ nhan_vien: 'NV2', so_gio: 4 }])
    && (await p.textContent('.sx-modal')).includes('Bình') && !!(await p.$('.sx-modal #sx-sp-tim')), JSON.stringify(g));
  await p.click('.sx-modal .sx-modal-close');
  kiem('Bình (không hộp) có dòng giờ trong bảng ghi, "Đã nhập" đếm 2 người',
    (await (await dongGio('NV2')).textContent()).trim() === '4 giờ'
    && (await p.textContent('#sx-vh-donecount')).trim() === '2');
  await p.focus('#sx-vh-tim');
  const chip = await p.$('#vh .sx-nv-row[data-nv="NV2"]');
  kiem('lưới tên: Bình tô "đã nhập", ghi "4 giờ"', chip && (await chip.getAttribute('class')).includes('sx-nv-row-xong')
    && (await chip.textContent()).includes('4 giờ'), chip && await chip.textContent());

  console.log('\n-- sửa / bỏ / chấm ăn --');
  await (await dongGio('NV1')).click();
  kiem('bấm số giờ của An → bàn số điền sẵn 2.5', (await khung()).includes('2.5'), await khung());
  await bam('3');
  await p.click('.sx-modal .sx-btn-primary');
  await doi();
  g = await goi();
  kiem('gõ 3 (thay số cũ) → lưu so_gio 3', JSON.stringify(g.at(-1)) === JSON.stringify([{ nhan_vien: 'NV1', so_gio: 3 }]),
    JSON.stringify(g.at(-1)));
  await (await dongGio('NV1')).click();
  await p.click('.sx-modal .sx-title-tog:has-text("Ăn ca")');
  await doi();
  g = await goi();
  kiem('chấm Ăn ca ngay trong bàn số giờ → chỉ gửi khoá an_ca (không gửi lại số giờ)',
    JSON.stringify(g.at(-1)) === JSON.stringify([{ nhan_vien: 'NV1', an_ca: 1 }]), JSON.stringify(g.at(-1)));
  await p.click('.sx-modal .sx-modal-close');
  kiem('… ăn đêm An vẫn còn ở server (không bị đè)', (await p.evaluate(() => window.AN.NV1.an_dem)) === 1);
  await p.click('#vh .sx-vh-gio-del[data-gio="NV2"]');
  await doi();
  g = await goi();
  kiem('✕ ở dòng giờ của Bình → lưu so_gio 0, dòng mất', JSON.stringify(g.at(-1))
    === JSON.stringify([{ nhan_vien: 'NV2', so_gio: 0 }]) && !(await dongGio('NV2')), JSON.stringify(g.at(-1)));
  kiem('… dòng hộp của An không đụng tới', (await p.$$('#vh .sx-vh-row:not(.sx-vh-row-gio)')).length === 1);

  console.log('\n-- công nhật / copy --');
  await p.click('#sx-vh-congnhat');
  kiem('★ Chấm hộp CÔNG NHẬT: KHÔNG có lối làm theo giờ (công nhật không phải một người)',
    !(await p.$('.sx-modal #sx-sp-gio')));
  await p.click('.sx-modal .sx-modal-close');
  await p.click('#sx-vh-copy');
  await p.waitForTimeout(400);
  const clip = await p.evaluate(() => navigator.clipboard.readText());
  kiem('copy gửi nhóm kèm giờ: "An (Bánh đậu xanh sen: 100, Làm theo giờ: 3 giờ)"',
    clip.includes('An (Bánh đậu xanh sen: 100, Làm theo giờ: 3 giờ)') && clip.includes('Tổng: 100'), JSON.stringify(clip));

  console.log('\n-- thẻ Phiếu lương --');
  await p.click('#pl .sx-lich-nut');
  await p.waitForSelector('#pl .sx-pl-dong');
  await p.click('#pl .sx-pl-dong');
  await p.waitForSelector('.sx-modal');
  const pl = (await p.textContent('.sx-modal')).replace(/\s+/g, ' ');
  kiem('dòng Làm theo giờ: "2,5 giờ × 33.000 đ" (không làm tròn, không đọc như hộp)',
    pl.includes('Làm theo giờ') && pl.includes('2,5 giờ × 33.000 đ'), pl);
  kiem('… dòng sản phẩm như cũ: "110 × 1.200 đ"', pl.includes('110 × 1.200 đ'), pl);
  kiem('… từng ngày ghi số giờ của ngày', pl.includes('×1.2 · 2,5 giờ · ăn ca'), pl);
  kiem('không lỗi JS', !loi.length, loi.join(' | '));
} finally {
  await b.close();
  srv.close();
}
console.log(hong ? `GIOCONG-JS-HỎNG (${hong})` : 'GIOCONG-JS-OK');
process.exit(hong ? 1 : 0);
