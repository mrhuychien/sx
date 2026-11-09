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
// Server giả gộp bảng chấm theo người ĐÚNG như portal.luu_bang_vao_hop: khoá nào gửi mới đổi; đơn giá mỗi mức chốt
// lúc ghi (D233: mức 1 33.000, mức 2 30.000), bỏ giờ thì bỏ đơn giá.
window.AN = { NV1: { nhan_vien: 'NV1', an_ca: 0, an_dem: 1, so_gio: 0, so_gio_2: 0 } };
const call = async (m, a) => {
  window.CALLS.push([m, a]);
  if (m === 'sx.api.portal.luu_bang_vao_hop') {
    JSON.parse(a.an_ca || '[]').forEach((d) => {
      const g = window.AN[d.nhan_vien]
        || (window.AN[d.nhan_vien] = { nhan_vien: d.nhan_vien, an_ca: 0, an_dem: 0, so_gio: 0, so_gio_2: 0 });
      ['an_ca', 'an_dem', 'so_gio', 'so_gio_2'].forEach((k) => { if (k in d) g[k] = d[k]; });
    });
    const an = Object.values(window.AN).filter((g) => g.an_ca || g.an_dem || g.so_gio > 0 || g.so_gio_2 > 0)
      .map((g) => {
        g.don_gia_gio = g.so_gio > 0 ? (g.don_gia_gio || 33000) : 0;
        g.don_gia_gio_2 = g.so_gio_2 > 0 ? (g.don_gia_gio_2 || 30000) : 0;
        return { ...g, tien_gio: g.so_gio * g.don_gia_gio + g.so_gio_2 * g.don_gia_gio_2 };
      });
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
        { ten: 'Làm theo giờ', cach_lam: '', theo_gio: true, don_gia: 30000, so_luong: 3, thanh_tien: 90000 },
        { ten: 'Bánh sen', cach_lam: '', don_gia: 1200, so_luong: 110, thanh_tien: 132000 }],
      // D234: mỗi ngày kèm sản phẩm của ngày (server đã gộp, xếp: sản phẩm trước, giờ sau) + tiền ăn
      ngay: [{ ngay: '2026-11-01', thu: 'Chủ nhật', an_ca: 1, an_dem: 0, tien_an: 20000, luong_sp: 214500, he_so: 1.2,
        so_gio: 2.5, thu_nhap: 277400,
        sp: [{ ten: 'Bánh sen', cach_lam: '', don_gia: 1200, so_luong: 110, thanh_tien: 132000 },
          { ten: 'Làm theo giờ', cach_lam: '', theo_gio: true, don_gia: 33000, so_luong: 2.5, thanh_tien: 82500 }] }],
      phat: [], ghi_chu: '' };
  }
  return {};
};
const ngay = { name: 'N1', ngay: '2026-11-02', docstatus: 0 };
const boot = { ngay_xem: '2026-11-02', la_hom_nay: true, ngay_sx: ngay, bang_don_gia: 'BG', don_gia_gio: 33000,
  don_gia_gio_2: 30000,
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
  kiem('… chân bảng: tổng giờ + số người + giờ theo đơn giá (D233)', (await p.textContent('#sx-vh-footer'))
    .replace(/\s+/g, ' ').includes('làm theo giờ 2,5 giờ (1 người: 2,5 giờ × 33.000 đ)'),
  await p.textContent('#sx-vh-footer'));
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

  console.log('\n-- D233: mức 30.000 đ / giờ --');
  await p.click('#vh .sx-vh-them[data-nv="NV1"]');
  kiem('chọn mã: hai lối làm theo giờ, mỗi lối ghi rõ đơn giá (33.000 / 30.000 đ / giờ)',
    (await p.textContent('.sx-modal #sx-sp-gio')).includes('33.000 đ / giờ')
    && (await p.textContent('.sx-modal #sx-sp-gio-2')).includes('30.000 đ / giờ'));
  await p.click('.sx-modal #sx-sp-gio-2');
  kiem('mức 30.000: bàn số ghi rõ mức, ô trống (mức 1 của An không điền vào đây)',
    (await p.textContent('.sx-modal')).includes('30.000 đ/giờ') && !(await khung()).includes('3'), await khung());
  await bam('3');
  kiem('… gõ 3 → tiền 3 × 30.000 = 90.000 đ', (await khung()).includes('90.000 đ'), await khung());
  await p.click('.sx-modal .sx-btn-primary');
  await doi();
  g = await goi();
  kiem('XONG → chỉ gửi khoá so_gio_2 (không gửi lại giờ mức 1 / ăn ca)',
    JSON.stringify(g.at(-1)) === JSON.stringify([{ nhan_vien: 'NV1', so_gio_2: 3 }]), JSON.stringify(g.at(-1)));
  const gioMuc = (nv, k) => p.$(`#vh .sx-vh-gio-sl[data-gio="${nv}"][data-muc="${k}"]`);
  const dongMuc = async (nv, k) => (await (await gioMuc(nv, k)).evaluate((e) => e.closest('.sx-vh-row').textContent))
    .replace(/\s+/g, ' ');
  kiem('bảng ghi: An có HAI dòng giờ, mỗi dòng ghi rõ mức (ghi công hiện rõ)',
    (await dongMuc('NV1', 'so_gio')).includes('33.000 đ/giờ') && (await dongMuc('NV1', 'so_gio')).includes('3 giờ')
    && (await dongMuc('NV1', 'so_gio_2')).includes('30.000 đ/giờ') && (await dongMuc('NV1', 'so_gio_2')).includes('3 giờ'),
    `${await dongMuc('NV1', 'so_gio')} | ${await dongMuc('NV1', 'so_gio_2')}`);
  kiem('… chân bảng: tổng 6 giờ, tách theo đơn giá', (await p.textContent('#sx-vh-footer')).replace(/\s+/g, ' ')
    .includes('làm theo giờ 6 giờ (1 người: 3 giờ × 33.000 đ, 3 giờ × 30.000 đ)'), await p.textContent('#sx-vh-footer'));
  await p.focus('#sx-vh-tim');
  kiem('… lưới tên: An ghi tổng giờ mọi mức (6 giờ)',
    (await p.textContent('#vh .sx-nv-row[data-nv="NV1"]')).includes('6 giờ'), await p.textContent('#vh .sx-nv-row[data-nv="NV1"]'));
  await (await gioMuc('NV1', 'so_gio_2')).click();
  kiem('bấm số giờ mức 30.000 → bàn số điền sẵn 3, ghi rõ mức', (await khung()).includes('3')
    && (await p.textContent('.sx-modal')).includes('30.000 đ/giờ'), await khung());
  const truoc = (await goi()).length;
  await bam('2'); await bam('2');
  await p.click('.sx-modal .sx-btn-primary');
  await doi();
  kiem('3 giờ mức 1 + 22 giờ mức 2 = 25 > 24 → báo, KHÔNG lưu',
    (await goi()).length === truoc && (await p.textContent('.sx-toast-wrap')).includes('không quá 24 giờ (cộng mọi mức)'));
  if (await p.$('.sx-modal .sx-modal-close')) await p.click('.sx-modal .sx-modal-close');   // bàn số tự đóng sau XONG

  console.log('\n-- công nhật / copy --');
  await p.click('#sx-vh-congnhat');
  kiem('★ Chấm hộp CÔNG NHẬT: KHÔNG có lối làm theo giờ (công nhật không phải một người)',
    !(await p.$('.sx-modal #sx-sp-gio')));
  await p.click('.sx-modal .sx-modal-close');
  await p.click('#sx-vh-copy');
  await p.waitForTimeout(400);
  const clip = await p.evaluate(() => navigator.clipboard.readText());
  kiem('copy gửi nhóm: giờ MỌI mức gộp một mục "Làm theo giờ: 6 giờ", không ghi mức 33.000 / 30.000 (tránh tị nạnh)',
    clip.includes('An (Bánh đậu xanh sen: 100, Làm theo giờ: 6 giờ)') && clip.includes('Tổng: 100')
    && !/33\.000|30\.000|đ\/giờ|mức/.test(clip), JSON.stringify(clip));
  await p.click('#vh .sx-vh-gio-del[data-gio="NV1"][data-muc="so_gio_2"]');
  await doi();
  g = await goi();
  kiem('✕ ở dòng giờ mức 30.000 → chỉ gửi so_gio_2 0; dòng mức 33.000 còn',
    JSON.stringify(g.at(-1)) === JSON.stringify([{ nhan_vien: 'NV1', so_gio_2: 0 }])
    && !(await gioMuc('NV1', 'so_gio_2')) && !!(await gioMuc('NV1', 'so_gio')), JSON.stringify(g.at(-1)));

  console.log('\n-- thẻ Phiếu lương --');
  await p.click('#pl .sx-lich-nut');
  await p.waitForSelector('#pl .sx-pl-dong');
  await p.click('#pl .sx-pl-dong');
  await p.waitForSelector('.sx-modal');
  const pl = (await p.textContent('.sx-modal')).replace(/\s+/g, ' ');
  kiem('dòng Làm theo giờ: "2,5 giờ × 33.000 đ" (không làm tròn, không đọc như hộp)',
    pl.includes('Làm theo giờ') && pl.includes('2,5 giờ × 33.000 đ'), pl);
  kiem('… mỗi mức một dòng: "3 giờ × 30.000 đ" (quản lý hiện rõ mức — D233)', pl.includes('3 giờ × 30.000 đ'), pl);
  kiem('… dòng sản phẩm như cũ: "110 × 1.200 đ"', pl.includes('110 × 1.200 đ'), pl);
  const ngayGio = await p.$$eval('.sx-modal .sx-pl-ngay tbody tr', (tr) => tr.map((r) => [...r.cells]
    .map((c) => c.textContent.replace(/\s+/g, ' ').trim()).join(' | ')));
  kiem('… từng ngày (D234): dòng giờ của ngày ghi số giờ × đơn giá = thành tiền',
    ngayGio.includes('Làm theo giờ | 2,5 giờ | 33.000 | 82.500'), JSON.stringify(ngayGio));
  await p.click('.sx-modal .sx-modal-close');

  console.log('\n-- D233: đơn giá trên dòng giờ = giá ĐÃ CHỐT, không có thì giá hiện hành --');
  await p.evaluate(async () => {
    const { render } = await import('/assets/sx/sx/cards/vaohop.js');
    const c = document.createElement('div');
    c.id = 'vh2';
    document.body.appendChild(c);
    const bt = { ngay_xem: '2026-11-03', la_hom_nay: true, ngay_sx: { name: 'N2', ngay: '2026-11-03', docstatus: 0 },
      don_gia_gio: 33000, don_gia_gio_2: 30000, items_tp: [], danh_muc_khoan: [],
      nhan_vien: [{ name: 'NV1', employee_name: 'Nguyễn Thị An', ten_hien_thi: 'An' },
        { name: 'NV2', employee_name: 'Trần Văn Bình', ten_hien_thi: 'Bình' },
        { name: 'NV3', employee_name: 'Lê Thị Cúc', ten_hien_thi: 'Cúc' }],
      bang_vao_hop: { dong: [], an_ca: [
        { nhan_vien: 'NV2', an_ca: 0, an_dem: 0, so_gio: 0, so_gio_2: 2 },              // server bản cũ: không gửi giá chốt
        { nhan_vien: 'NV1', an_ca: 0, an_dem: 0, so_gio: 1, don_gia_gio: 32000 },     // chốt lúc giá còn 32.000
        { nhan_vien: 'NV3', an_ca: 0, an_dem: 0, so_gio: 1.5, don_gia_gio: 33000 }] } };
    await render({ container: c, boot: bt, call: async () => ({}), ensureNgay: async () => bt.ngay_sx });
  });
  const dong2 = async (nv, k) => (await p.$eval(`#vh2 .sx-vh-gio-sl[data-gio="${nv}"][data-muc="${k}"]`,
    (e) => e.closest('.sx-vh-row').textContent)).replace(/\s+/g, ' ');
  kiem('giá chốt (32.000) khác giá hiện hành (33.000) → dòng ghi giá CHỐT — đúng số tiền sẽ vào lương',
    (await dong2('NV1', 'so_gio')).includes('32.000 đ/giờ'), await dong2('NV1', 'so_gio'));
  kiem('chưa có giá chốt (server bản cũ) → ghi giá hiện hành của mức đó (30.000)',
    (await dong2('NV2', 'so_gio_2')).includes('30.000 đ/giờ'), await dong2('NV2', 'so_gio_2'));
  kiem('chân bảng: giờ gộp theo đơn giá, giá cao trước',
    (await p.textContent('#vh2 #sx-vh-footer')).replace(/\s+/g, ' ')
      .includes('làm theo giờ 4,5 giờ (3 người: 1,5 giờ × 33.000 đ, 1 giờ × 32.000 đ, 2 giờ × 30.000 đ)'),
    await p.textContent('#vh2 #sx-vh-footer'));
  await p.click('#vh2 .sx-vh-gio-sl[data-gio="NV1"][data-muc="so_gio"]');
  kiem('bấm số giờ của An → bàn số ghi giá CHỐT 32.000 (không phải giá hiện hành)',
    (await p.textContent('.sx-modal')).includes('32.000 đ/giờ'), await p.textContent('.sx-modal'));
  await p.click('.sx-modal .sx-modal-close');
  kiem('không lỗi JS', !loi.length, loi.join(' | '));
} finally {
  await b.close();
  srv.close();
}
console.log(hong ? `GIOCONG-JS-HỎNG (${hong})` : 'GIOCONG-JS-OK');
process.exit(hong ? 1 : 0);
