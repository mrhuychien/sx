// Hàng chờ ngoại tuyến KHÔNG gửi thao tác của người này dưới tên người khác (D96).
//
// Vì sao bài này đáng có: điện thoại xưởng chuyền tay giữa hai QC. Hàng chờ nằm
// trong trình duyệt chứ không trong tài khoản — QC A mất mạng, đăng xuất, QC B
// đăng nhập vào đúng máy đó, app mở lên là gửi luôn số của A dưới tên B. Không
// lỗi nào hiện ra; nhật ký chỉ ghi sai người, và "ai ghi" là thứ auditor hỏi đầu.
//
// Nạp queue.js THẬT với localStorage / navigator / window giả.
//
// Chạy: node scripts/test-hangcho.mjs   (verify.sh gọi sẵn)

import { readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const kho = {};
globalThis.localStorage = {
  getItem: (k) => (k in kho ? kho[k] : null),
  setItem: (k, v) => { kho[k] = String(v); },
  removeItem: (k) => { delete kho[k]; },
};
globalThis.window = { SX_CONTEXT: { user: 'a@x' } };
Object.defineProperty(globalThis, 'navigator', { value: { onLine: true }, configurable: true });

const tam = join(tmpdir(), `q-${process.pid}.mjs`);
writeFileSync(tam, readFileSync('sx/public/sx/lib/queue.js', 'utf8'));
const Q = await import(`file://${tam}`);
rmSync(tam);

let hong = 0;
function kiem(ten, dk, ct = '') {
  if (!dk) hong += 1;
  console.log(`  ${dk ? 'ok  ' : 'HỎNG'} ${ten}${ct ? ` — ${ct}` : ''}`);
}
const la = (u) => { window.SX_CONTEXT.user = u; };
const daGui = [];
const post = async (method, args) => { daGui.push({ method, args, boi: window.SX_CONTEXT.user }); };

console.log('-- ghi tên người xếp hàng --');
la('a@x');
Q.xepHang('sx.api.portal.ghi_su_co', { mo_ta: 'của A' });
kiem('thao tác xếp hàng mang tên người xếp', Q.danhSach()[0].user === 'a@x');

console.log('\n-- đổi người trên cùng máy --');
la('b@x');
kiem('B chỉ thấy 0 thao tác của mình (không tính của A)', Q.cuaToi().length === 0);
let kq = await Q.guiLai(post);
kiem('B mở app: KHÔNG gửi thao tác của A dưới tên B', daGui.length === 0,
  JSON.stringify(daGui));
kiem('thao tác của A không bị xoá âm thầm', Q.danhSach().length === 1);
kiem('mà được đánh dấu rõ là của ai', String(Q.danhSach()[0].loi).includes('a@x'),
  Q.danhSach()[0].loi);

console.log('\n-- chủ thật quay lại --');
la('a@x');
kq = await Q.guiLai(post);
kiem('A đăng nhập lại → gửi được, đúng tên A',
  daGui.length === 1 && daGui[0].boi === 'a@x', JSON.stringify(daGui));
kiem('và hàng chờ sạch', Q.danhSach().length === 0);

console.log('\n-- bỏ thao tác khi đăng xuất --');
la('a@x'); Q.xepHang('sx.api.portal.ghi_su_co', { mo_ta: 'A1' });
la('b@x'); Q.xepHang('sx.api.portal.ghi_su_co', { mo_ta: 'B1' });
Q.xoaCuaToi();
kiem('B chọn bỏ thao tác của mình → chỉ mất của B',
  Q.danhSach().length === 1 && Q.danhSach()[0].args.mo_ta === 'A1',
  JSON.stringify(Q.danhSach().map((x) => x.args.mo_ta)));
kiem('thao tác của A vẫn nguyên', Q.danhSach()[0].user === 'a@x');

console.log('\n-- dữ liệu cũ (trước D96, chưa có tên người) --');
Q.xoaHang();
kho['sx-queue-v1'] = JSON.stringify([{ id: '1', method: 'sx.api.portal.ghi_su_co',
  args: { mo_ta: 'cũ' }, khoa: null, luc: '', loi: null }]);
la('b@x'); daGui.length = 0;
await Q.guiLai(post);
// Thao tác xếp hàng TRƯỚC khi có cơ chế này không biết của ai. Gửi đi còn hơn
// kẹt vĩnh viễn: trước D96 máy nào cũng chỉ một người dùng trên thực tế.
kiem('thao tác cũ chưa có tên người vẫn gửi được (không kẹt vĩnh viễn)',
  daGui.length === 1);

console.log('\n-- lỗi máy chủ đọc được (lib/api.js, D182) --');
// Máy chủ chặn vì gửi quá lớn (413, trang HTML): trước D182 chỉ hiện "Có lỗi xảy ra" — Ban ISO tải bản đã ký số lớn
// không biết vì sao hỏng. Nạp api.js THẬT (kèm queue.js) với fetch giả.
const { mkdtempSync } = await import('node:fs');
const thu = mkdtempSync(join(tmpdir(), 'api-'));
writeFileSync(join(thu, 'queue.mjs'), readFileSync('sx/public/sx/lib/queue.js', 'utf8'));
writeFileSync(join(thu, 'api.mjs'), readFileSync('sx/public/sx/lib/api.js', 'utf8').replaceAll("'./queue.js'", "'./queue.mjs'"));
window.addEventListener = () => {};
const traLoi = { status: 413, ok: false, body: null };
globalThis.fetch = async () => ({ status: traLoi.status, ok: traLoi.ok,
  json: async () => { if (!traLoi.body) throw new Error('không phải JSON'); return traLoi.body; } });
const API = await import(`file://${join(thu, 'api.mjs')}`);
rmSync(thu, { recursive: true });
const loiCua = async () => { try { await API.call('sx.api.qc_tailieu.nap_tep', {}); return ''; } catch (e) { return e.message; } };
kiem('413 (quá giới hạn máy chủ) → báo rõ "quá lớn … max_file_size", không phải "Có lỗi xảy ra"',
  (await loiCua()).includes('quá lớn so với giới hạn của máy chủ (max_file_size)'));
Object.assign(traLoi, { status: 417, body: { exception: 'frappe.exceptions.ValidationError: Nội dung tệp không khớp đuôi .pdf.' } });
kiem('lỗi nghiệp vụ khác vẫn bóc đúng câu của server', (await loiCua()) === 'Nội dung tệp không khớp đuôi .pdf.');
Object.assign(traLoi, { status: 200, ok: true, body: { message: { khoa: 'tl:1' } } });
kiem('thành công trả message', (await API.call('x', {})).khoa === 'tl:1');

console.log(hong ? `HANGCHO-FAIL (${hong} ca)` : 'HANGCHO-OK');
process.exit(hong ? 1 : 0);
