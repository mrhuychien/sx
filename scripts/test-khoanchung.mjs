// D203 — "Ghi cho công khoán" ở thẻ Sổ nợ vào hộp + dòng ★ Công khoán chung ở màn Ghi hộp.
//
// Vì sao phải có bài này: dòng chung là TIỀN KHOÁN không gắn người. Hỏng im lặng theo hai hướng:
//   · màn Ghi hộp coi dòng chung là một công nhân (đếm vào "đã nhập", cho chấm thêm / chấm ăn),
//     hoặc lần lưu sau làm rơi mất mã giả → dòng chung thành dòng của "người" KHOAN_CHUNG;
//   · thẻ sổ nợ ghi sai số / sai cách làm / sai ngày, hoặc ghi khi chưa chọn cách làm.
//
// Phần 1 (Node): văn bản gửi nhóm có dòng công khoán chung. Phần 2 (Chromium thật, nếu máy có):
// bấm nút trên hai thẻ thật, đọc lại lời gọi API.
// Chạy: node scripts/test-khoanchung.mjs   (verify.sh gọi sẵn)

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

// ── Phần 1: hàm thuần ───────────────────────────────────────────────────
const src = readFileSync(join(GOC, 'sx/public/sx/cards/vaohop.js'), 'utf8')
  .split('\n').filter((d) => !d.startsWith('import ')).join('\n');
const tam = join(tmpdir(), `kc-${process.pid}.mjs`);
writeFileSync(tam, `const formatNumber = (n) => Number(n).toLocaleString('vi-VN');\n${src}`);
const { vanBanSanLuong } = await import(`file://${tam}`);
rmSync(tam);
console.log('-- văn bản gửi nhóm --');
const vb = vanBanSanLuong([
  { ten: 'An', dong: [{ nhan_vien: 'NV1', san_pham: 'TP-SEN', so_hop: 120 }] },
  { ten: '★ Công khoán chung', dong: [{ nhan_vien: 'KHOAN_CHUNG', san_pham: 'TP-SEN', so_hop: 30 }] },
  { ten: '★ Công nhật', dong: [{ nhan_vien: 'CONG_NHAT', san_pham: 'TP-SEN', so_hop: 50 }] },
], '2026-10-13', () => 'Bánh sen');
kiem('có dòng công khoán chung — tổ biết còn phần chung để chia', vb.includes('★ Công khoán chung (Bánh sen: 30)'),
  JSON.stringify(vb));
kiem('tổng = công khoán (người + chung), không cộng công nhật', vb.trim().endsWith('— Tổng: 150 sản phẩm'));

const Q = await import(`file://${join(GOC, 'sx/public/sx/lib/queue.js')}`);
kiem('mất mạng: Ghi cho công khoán KHÔNG xếp hàng gửi sau (gửi lại muộn = có thể trả khoán cho số đã chấm bù)',
  !Q.xepHangDuoc('sx.api.khotp.ghi_no_khoan_chung')
  && Q.lyDoChan('sx.api.khotp.ghi_no_khoan_chung').includes('đối chiếu sổ nợ'));

// ── Phần 2: hai thẻ thật trong Chromium ─────────────────────────────────
const CHROME = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
const PW = '/opt/node22/lib/node_modules/playwright/index.js';
if (!existsSync(CHROME) || !existsSync(PW)) {
  console.log('\n-- trình duyệt thật: BỎ QUA (máy này không có Chromium) --');
} else {
  const PUB = join(GOC, 'sx/public/sx');
  const TRANG = `<!doctype html><meta charset="utf-8"><body><div id="vh"></div><div id="no"></div><div id="vh2"></div>
<script type="module">
import { render as veVH } from '/assets/sx/sx/cards/vaohop.js';
import { render as veNo } from '/assets/sx/sx/cards/novaohop.js';
window.CALLS = [];
window.REFRESH = 0;
window.LOI = null;
const call = async (m, a) => {
  window.CALLS.push([m, a]);
  if (m === 'sx.api.portal.luu_bang_vao_hop') {
    return { dong: JSON.parse(a.rows), an_ca: [], chung_khac: window.CHUNG || [] };
  }
  if (m === 'sx.api.khotp.so_no_vao_hop') return window.NO;
  if (m === 'sx.api.khotp.ghi_no_khoan_chung') {
    if (window.LOI) throw new Error(window.LOI);
    return { so_hop: a.so_hop, ten: 'Bánh sen', thanh_tien: 24000 };
  }
  return {};
};
const ngay = { name: 'N1', ngay: '2026-10-13', docstatus: 0 };
const boot = { ngay_xem: '2026-10-13', la_hom_nay: true, ngay_sx: ngay, bang_don_gia: 'BG',
  items_tp: [{ name: 'TP-SEN', item_name: 'Bánh đậu xanh sen' }], danh_muc_khoan: [],
  nhan_vien: [{ name: 'NV1', employee_name: 'Nguyễn Thị An', ten_hien_thi: 'An' }],
  bang_vao_hop: { dong: [
    { name: 'R3', nhan_vien: 'CONG_NHAT', ten_nhan_vien: 'Công nhật', cong_nhat: 1, san_pham: 'TP-SEN', so_hop: 50 },
    { name: 'R2', nhan_vien: 'KHOAN_CHUNG', ten_nhan_vien: 'Công khoán chung', khoan_chung: 1, san_pham: 'TP-SEN',
      cach_lam: 'Máy', so_hop: 30 },
    { name: 'R1', nhan_vien: 'NV1', ten_nhan_vien: 'Nguyễn Thị An', san_pham: 'TP-SEN', so_hop: 120 }], an_ca: [] } };
await veVH({ container: document.getElementById('vh'), boot, call, ensureNgay: async () => ngay });
window.veNo = async (no) => {
  window.NO = no;
  const c = document.getElementById('no');
  c.innerHTML = '';
  await veNo({ container: c, call, boot, ensureNgay: async () => ngay, refresh: () => { window.REFRESH += 1; } });
};
// D212: QC (không xem hết) — dòng ★ Công khoán chung do QUẢN LÝ ghi về trong chung_khac (chỉ xem).
window.CHUNG = [];
window.veVH2 = async () => {
  window.CHUNG = [{ name: 'R9', nhan_vien: 'KHOAN_CHUNG', ten_nhan_vien: 'Công khoán chung', khoan_chung: 1,
    san_pham: 'TP-SEN', so_hop: 30, nguoi_ghi: 'quanly@x' }];
  const b2 = { ...boot, bang_vao_hop: { xem_het: false, an_ca: [], chung_khac: window.CHUNG,
    dong: [{ name: 'R1', nhan_vien: 'NV1', ten_nhan_vien: 'Nguyễn Thị An', san_pham: 'TP-SEN', so_hop: 120,
      nguoi_ghi: 'qc@x' }] } };
  await veVH({ container: document.getElementById('vh2'), boot: b2, call, ensureNgay: async () => ngay });
};
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
  await p.goto(`http://127.0.0.1:${srv.address().port}/`);
  await p.waitForFunction(() => window.SAN_SANG, null, { timeout: 10000 });

  console.log('\n-- màn Ghi hộp: dòng ★ Công khoán chung --');
  const ten = await p.$$eval('#vh .sx-vh-name', (ds) => ds.map((d) => d.textContent.trim()));
  kiem('thứ tự: người → ★ Công khoán chung → ★ Công nhật', JSON.stringify(ten)
    === JSON.stringify(['An', '★ Công khoán chung', '★ Công nhật']), JSON.stringify(ten));
  const kc = await p.$eval('#vh .sx-vh-row-kc', (r) => ({
    meta: r.querySelector('.sx-vh-meta').textContent, them: r.querySelectorAll('.sx-vh-them').length,
    xoa: r.querySelectorAll('.sx-vh-del').length }));
  kiem('dòng chung: ghi rõ tính khoán, tổ tự chia; có ✕, KHÔNG có nút + (không chấm thêm cho "người" này)',
    kc.meta.includes('Máy') && kc.meta.includes('tính khoán, tổ tự chia') && kc.them === 0 && kc.xoa === 1,
    JSON.stringify(kc));
  kiem('"Đã nhập" chỉ đếm người (dòng chung, công nhật không phải người)',
    (await p.textContent('#sx-vh-donecount')).trim() === '1');
  const chan = (await p.textContent('#sx-vh-footer')).replace(/\s+/g, ' ');
  kiem('tổng ngày ghi riêng phần công khoán chung và công nhật',
    chan.includes('200') && chan.includes('công khoán chung 30') && chan.includes('công nhật 50'), chan);
  await p.click('#vh .sx-vh-row-cn .sx-vh-del');
  await p.waitForTimeout(200);
  const luu = (await p.evaluate(() => window.CALLS)).filter(([m]) => m === 'sx.api.portal.luu_bang_vao_hop').pop();
  const rows = luu ? JSON.parse(luu[1].rows) : [];
  kiem('lưu bảng (xoá dòng công nhật): dòng chung gửi lại ĐÚNG mã giả + mã dòng, không thành dòng của người',
    rows.some((r) => r.name === 'R2' && r.nhan_vien === 'KHOAN_CHUNG' && r.so_hop === 30 && r.cach_lam === 'Máy')
    && !rows.some((r) => r.name === 'R3'), JSON.stringify(rows));
  await p.click('#sx-vh-copy');
  await p.waitForTimeout(400);
  const clip = await p.evaluate(() => navigator.clipboard.readText());
  kiem('copy gửi nhóm có dòng công khoán chung', clip.includes('★ Công khoán chung (Bánh đậu xanh sen: 30)')
    && clip.includes('Tổng: 150'), JSON.stringify(clip));

  console.log('\n-- thẻ Sổ nợ vào hộp: Ghi cho công khoán --');
  const nhom = (x) => ({ nhom: [{ item: 'TP-SEN', ten: 'Bánh sen', con_lai: 29.5, so_hop: 30, so_ngay: 1,
    dong: [{ name: 'NV-1', ngay: '2026-10-12', so_luong: 30, con_lai: 29.5, phieu_nhap: 'PN-1' }],
    cach_lam: [], gia_chung: null, ...x }], tong_dong: 1, duoc_bo_qua: false, duoc_ghi_kc: true });
  // D208: thẻ gập sẵn — mở ra (như người bấm dòng gập) rồi mới tới nút trong danh sách.
  const mo = async (no) => {
    await p.evaluate(async (n) => {
      window.CALLS = []; window.REFRESH = 0; await window.veNo(n);
      const d = document.querySelector('#no details.sx-no-gap');
      if (d) d.open = true;
    }, no);
  };
  const okNut = () => p.$('.sx-modal .sx-btn-primary');
  const goiGhi = async () => (await p.evaluate(() => window.CALLS))
    .filter(([m]) => m === 'sx.api.khotp.ghi_no_khoan_chung');

  await mo(nhom({ cach_lam: [{ ten: 'Máy', don_gia: 800 }, { ten: 'Tay', don_gia: 1000 }] }));
  const doc = (await p.evaluate(() => window.CALLS)).find(([m]) => m === 'sx.api.khotp.so_no_vao_hop');
  kiem('thẻ hỏi sổ nợ kèm NGÀY ĐANG XEM (giá theo bảng đơn giá ngày đó)', doc && doc[1].ngay === '2026-10-13',
    JSON.stringify(doc));
  kiem('mỗi mã một nút ghi đúng số hộp nợ (làm tròn lên ở server)',
    (await p.textContent('#no .sx-nvh-kc')).trim() === '★ Ghi 30 hộp cho công khoán');
  await p.click('#no .sx-nvh-kc');
  kiem('mã hai cách làm: chưa chọn thì nút GHI khoá', await (await okNut()).isDisabled());
  const msg = await p.textContent('.sx-modal .sx-modal-msg');
  kiem('hộp xác nhận nói rõ: dòng chung, ngày ghi, không vào phiếu lương ai, nợ về 0',
    msg.includes('★ CÔNG KHOÁN CHUNG') && msg.includes('hôm nay') && msg.includes('KHÔNG vào phiếu lương')
    && msg.includes('Nợ mã này về 0'), msg);
  await p.click('.sx-modal .sx-sl-o:has-text("Máy")');
  const tien = await p.textContent('.sx-modal .sx-sl-o-co');
  kiem('chọn Máy: tô chọn, hiện tiền 800 × 30', tien.includes('Máy') && tien.includes('24.000'), tien);
  kiem('chọn xong thì nút GHI mở', !(await (await okNut()).isDisabled()));
  await (await okNut()).click();
  await p.waitForTimeout(200);
  let g = await goiGhi();
  kiem('gọi ghi_no_khoan_chung: ngày đang xem, mã, ĐÚNG số trên màn, cách làm đã chọn',
    g.length === 1 && JSON.stringify(g[0][1]) === JSON.stringify(
      { ngay_sx: 'N1', item: 'TP-SEN', so_hop: 30, cach_lam: 'Máy' }), JSON.stringify(g));
  kiem('ghi xong: đóng hộp, vẽ lại cả màn (dòng chung hiện ở bảng ghi)',
    !(await p.$('.sx-modal')) && (await p.evaluate(() => window.REFRESH)) === 1);

  await mo(nhom({ gia_chung: 1000 }));
  await p.click('#no .sx-nvh-kc');
  kiem('chỉ có giá chung: không phải chọn, nút GHI mở ngay', !(await (await okNut()).isDisabled()));
  await (await okNut()).click();
  await p.waitForTimeout(200);
  g = await goiGhi();
  kiem('… gửi cách làm rỗng (giá chung)', g.length === 1 && g[0][1].cach_lam === null, JSON.stringify(g));

  await mo(nhom({ cach_lam: [{ ten: 'Máy', don_gia: 800 }] }));
  await p.click('#no .sx-nvh-kc');
  kiem('chỉ một cách làm (không giá chung): tự chọn sẵn, tô chọn',
    !(await (await okNut()).isDisabled()) && (await p.textContent('.sx-modal .sx-sl-o-co')).includes('Máy'));
  await (await okNut()).click();
  await p.waitForTimeout(200);
  g = await goiGhi();
  kiem('… gửi đúng cách làm đó', g.length === 1 && g[0][1].cach_lam === 'Máy', JSON.stringify(g));

  await mo(nhom({}));
  await p.click('#no .sx-nvh-kc');
  kiem('mã chưa khai giá: báo tạm 0 đồng + sổ nợ đơn giá, vẫn cho ghi',
    (await p.textContent('.sx-modal .sx-nvh-gia')).includes('chưa khai đơn giá')
    && !(await (await okNut()).isDisabled()));
  await p.evaluate(() => { window.LOI = 'Nợ vào hộp của Bánh sen vừa đổi: còn 8 hộp'; });
  await (await okNut()).click();
  await p.waitForTimeout(200);
  kiem('server báo nợ đã đổi: giữ hộp mở, nút bấm lại được, KHÔNG vẽ lại màn',
    !!(await p.$('.sx-modal')) && !(await (await okNut()).isDisabled())
    && (await p.evaluate(() => window.REFRESH)) === 0);
  await p.evaluate(() => { window.LOI = null; document.querySelector('.sx-modal-close').click(); });

  await mo({ ...nhom({ gia_chung: 1000 }), duoc_ghi_kc: false });
  kiem('không có quyền ghi hộp → không có nút', !(await p.$('#no .sx-nvh-kc')));

  console.log('\n-- D212: QC thấy ★ Công khoán chung do người khác ghi — chỉ xem, có trong tin gửi nhóm --');
  await p.evaluate(() => { window.CALLS = []; return window.veVH2(); });
  const ds2 = await p.$$eval('#vh2 .sx-vh-row', (rs) => rs.map((r) => ({
    ten: r.querySelector('.sx-vh-name').textContent.trim(), meta: r.querySelector('.sx-vh-meta').textContent,
    xem: r.classList.contains('sx-vh-row-xem'), xoa: r.querySelectorAll('.sx-vh-del').length,
    soKhoa: r.querySelector('.sx-vh-sl').disabled })));
  kiem('danh sách: người của QC + dòng chung của quản lý (cuối), dòng chung CHỈ XEM: không ✕, số không bấm được, '
    + 'nói ai ghi', ds2.length === 2 && ds2[0].ten === 'An' && !ds2[0].xem && ds2[0].xoa === 1
    && ds2[1].ten === '★ Công khoán chung' && ds2[1].xem && ds2[1].xoa === 0 && ds2[1].soKhoa
    && ds2[1].meta.includes('ghi: quanly') && ds2[1].meta.includes('chỉ xem'), JSON.stringify(ds2));
  kiem('ghi chú đầu thẻ nói rõ: riêng công khoán chung thấy cả dòng người khác ghi',
    (await p.textContent('#vh2')).includes('Riêng ★ Công khoán chung (của cả tổ) thấy cả dòng người khác ghi'));
  const chan2 = (await p.textContent('#vh2 #sx-vh-footer')).replace(/\s+/g, ' ');
  kiem('tổng vẫn là phần mình ghi (120), kèm "+ 30 công khoán chung người khác ghi"',
    chan2.includes('120 sp') && chan2.includes('+ 30 công khoán chung người khác ghi'), chan2);
  await p.click('#vh2 .sx-vh-row-xem .sx-vh-sl', { force: true });
  kiem('bấm số của dòng chỉ xem: không mở bàn số', !(await p.$('.sx-modal')));
  await p.click('#vh2 #sx-vh-copy');
  await p.waitForTimeout(400);
  const clip2 = await p.evaluate(() => navigator.clipboard.readText());
  kiem('COPY gửi nhóm CÓ dòng công khoán chung người khác ghi, tổng tính cả phần đó',
    clip2.includes('An (Bánh đậu xanh sen: 120)') && clip2.includes('★ Công khoán chung (Bánh đậu xanh sen: 30)')
    && clip2.trim().endsWith('— Tổng: 150 sản phẩm'), JSON.stringify(clip2));
  // Trong lúc đó quản lý sửa dòng chung thành 40 → câu trả lời của lần lưu mang số mới.
  await p.evaluate(() => { window.CHUNG = [{ ...window.CHUNG[0], so_hop: 40 }]; });
  await p.click('#vh2 .sx-vh-row:not(.sx-vh-row-xem) .sx-vh-del');
  await p.waitForTimeout(250);
  const luu2 = (await p.evaluate(() => window.CALLS)).filter(([m]) => m === 'sx.api.portal.luu_bang_vao_hop').pop();
  kiem('lưu (xoá dòng của mình): KHÔNG gửi dòng chỉ xem, không đưa mã R9 vào "biet"',
    luu2 && JSON.parse(luu2[1].rows).length === 0 && !JSON.parse(luu2[1].biet).includes('R9'),
    luu2 && JSON.stringify(luu2[1]));
  kiem('lưu xong: dòng chung chỉ xem vẫn hiện, số theo câu trả lời MỚI của máy chủ (40)',
    (await p.$$('#vh2 .sx-vh-row-xem')).length === 1
    && (await p.textContent('#vh2 .sx-vh-row-xem .sx-vh-sl')).trim() === '40');

  await b.close();
  srv.close();
  kiem('không lỗi JavaScript', !loi.length, loi.join(' | '));
}

console.log(hong ? `KHOANCHUNG: ${hong} HỎNG` : 'KHOANCHUNG-OK');
process.exit(hong ? 1 : 0);
