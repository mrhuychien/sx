// Màn phiếu đánh giá nhà cung cấp #/so/BM.07.01 (W44, D173) — views/danhgiancc.js.
//
// Vì sao phải có bài này: phiếu là chỗ Mua hàng chấm điểm trên điện thoại — gửi sai khóa / mất ô phần A là phiếu
// trên server khác điều người ta đã chấm; mục không áp dụng phải khóa ở KAD; người chỉ xem không thấy nút sửa; phiếu
// Xem xét bắt Giám đốc chọn quyết định; trả lại bắt ghi ý kiến; trạng thái đánh giá của từng NCC đọc ra đúng.
// Nạp code THẬT (view + qcui + dom); modal / toast giả — scripts/fakedom.mjs.
//
// Chạy: node scripts/test-danhgiancc.mjs   (verify.sh gọi sẵn)

import {
  E, MO, TOAST, XAC, cho, ketThuc, kiem, napView, tim,
} from './fakedom.mjs';

const V = await napView('views/danhgiancc.js');
const nutCo = (goc, chu) => tim(goc, (e) => e.tagName === 'BUTTON' && e.textContent.includes(chu))[0];
const moCuoi = () => MO[MO.length - 1];
globalThis.window.location = { hash: '#/so/BM.07.01' };

const GOI = [];
let traVe = {};
let lai = 0;
const api = () => ({
  container: new E('div'),
  lai: () => { lai += 1; },
  call: async (m, a) => {
    GOI.push([m, a]);
    const k = m.split('.').pop();
    if (k in traVe) return typeof traVe[k] === 'function' ? traVe[k](a) : traVe[k];
    return {};
  },
});
const goi = (k) => GOI.filter(([m]) => m.endsWith(`.${k}`));

console.log('\n-- tình trạng đánh giá của một NCC --');
kiem('chưa có phiếu: NCC đã duyệt trước W44 → nhắc chưa có phiếu; NCC mới → chưa đánh giá',
  V.tinhTrang({ duyet: true, danh_gia: null }).chu.includes('chưa có phiếu BM.07.01')
  && V.tinhTrang({ duyet: false, danh_gia: null }).chu === 'chưa đánh giá');
kiem('Loại bỏ → đỏ; quá hạn → đỏ; còn ≤ 30 ngày → hạn; còn xa → Chấp nhận · hạn',
  V.tinhTrang({ danh_gia: { ket_qua: 'Loại bỏ', ngay: '2026-10-09' } }).kieu === 'cao'
  && V.tinhTrang({ danh_gia: { ket_qua: 'Chấp nhận', han: '2026-10-01', con: -8 } }).kieu === 'cao'
  && V.tinhTrang({ danh_gia: { ket_qua: 'Chấp nhận', han: '2026-10-20', con: 11 } }).chu
    === 'đánh giá lại trước 20/10/2026 (còn 11 ngày)'
  && V.tinhTrang({ danh_gia: { ket_qua: 'Chấp nhận', han: '2027-10-09', con: 365 } }).chu === 'Chấp nhận · hạn 09/10/2027');

console.log('\n-- danh sách: việc của bạn, nhà cung cấp, nút ĐÁNH GIÁ --');
const DS = {
  hom_nay: '2026-10-09', hinh_thuc: ['Đánh giá lần đầu', 'Đánh giá lại hằng năm', 'Đánh giá lại đột xuất'],
  quyen: { lap: true, qc: false, duyet: false },
  viec: [{ name: 'DGNCC-2026-0003', supplier: 'NCC-BB', ten_ncc: 'Bao bì Minh Anh', trang_thai: 'Trả lại',
    hinh_thuc: 'Đánh giá lần đầu', ngay: '2026-10-08', tong: 24, ket_luan: 'Xem xét' }],
  phieu: [],
  ncc: [
    { name: 'NCC-DX', ten: 'Đỗ Xanh Hải Dương', loai: 'Nguyên liệu thực phẩm', nguon: 'Trong nước', duyet: true,
      danh_gia: { ket_qua: 'Chấp nhận', han: '2027-10-09', con: 365, ngay: '2026-10-09' }, dang_mo: '' },
    { name: 'NCC-BB', ten: 'Bao bì Minh Anh', loai: 'Bao bì ngoài', duyet: false, danh_gia: null,
      dang_mo: 'DGNCC-2026-0003' },
    { name: 'NCC-CU', ten: 'Đường Biên Hòa', loai: 'Nguyên liệu thực phẩm', duyet: true, danh_gia: null, dang_mo: '' }],
};
let a = api();
V.veDanhSach(a, DS);
let c = a.container;
const theViec = tim(c, (e) => e.tagName === 'A' && e.href === '#/so/BM.07.01/DGNCC-2026-0003');
kiem('việc của bạn: phiếu trả lại, bấm sang phiếu; NCC có phiếu đang mở chỉ có link, không nút ĐÁNH GIÁ',
  theViec.length === 2 && c.chu.includes('Việc của bạn') && c.chu.includes('Trả lại')
  && tim(c, (e) => e.tagName === 'BUTTON' && e.textContent === 'ĐÁNH GIÁ').length === 2, c.chu);
kiem('thẻ NCC: đã / chưa vào BM.07.02, tình trạng đánh giá', c.chu.includes('đã duyệt BM.07.02')
  && c.chu.includes('Chấp nhận · hạn 09/10/2027') && c.chu.includes('đã duyệt trước W44 — chưa có phiếu BM.07.01'));
const timO = tim(c, (e) => e.tagName === 'INPUT' && e.type === 'search')[0];
timO.doi('biên hòa');
kiem('tìm theo tên (không phân biệt hoa thường): chỉ còn Đường Biên Hòa',
  c.chu.includes('Đường Biên Hòa') && !c.chu.includes('Đỗ Xanh Hải Dương'));
timO.doi('');
traVe = { lap: { name: 'DGNCC-2026-0009' } };
nutCo(c, 'ĐÁNH GIÁ').bam();
let m = moCuoi();
kiem('ĐÁNH GIÁ NCC đã có phiếu duyệt → mặc định Đánh giá lại hằng năm',
  tim(m.body, (e) => e.tagName === 'BUTTON' && e.classList.contains('sx-qc-seg-on'))[0].textContent
  === 'Đánh giá lại hằng năm');
nutCo(m.body, 'LẬP PHIẾU').bam();
await cho();
kiem('lập phiếu: gửi đúng NCC + hình thức, sang màn phiếu', JSON.stringify(goi('lap').at(-1)[1])
  === JSON.stringify({ supplier: 'NCC-DX', hinh_thuc: 'Đánh giá lại hằng năm' })
  && window.location.hash === '#/so/BM.07.01/DGNCC-2026-0009' && m.dong);
a = api();
V.veDanhSach(a, { ...DS, quyen: { lap: false, qc: true, duyet: false }, viec: [] });
kiem('QC (không lập): không có nút ĐÁNH GIÁ', !nutCo(a.container, 'ĐÁNH GIÁ'));

console.log('\n-- phiếu nháp: phần A, phần B, lưu, gửi --');
const MUC_B = [
  { k: 'diem_i', so: 'I', ten: 'Chất lượng', muc: [{ nhan: 'Luôn đạt', diem: 10 }, { nhan: 'Dưới 10% không đạt', diem: 5 },
    { nhan: 'Trên 10% không đạt', diem: 0 }], tu_tinh: false },
  { k: 'diem_ii', so: 'II', ten: 'Dịch vụ', muc: [{ nhan: 'Tốt', diem: 10 }, { nhan: 'Bình thường', diem: 5 },
    { nhan: 'Kém', diem: 0 }], tu_tinh: false },
  { k: 'diem_iii', so: 'III', ten: 'Giá cả', muc: [{ nhan: 'Phù hợp', diem: 10 }, { nhan: 'Không phù hợp', diem: 4 }],
    tu_tinh: false },
  { k: 'diem_iv', so: 'IV', ten: 'Tiến độ giao hàng', muc: [{ nhan: 'Tốt', diem: 10 }, { nhan: 'Chậm 15%', diem: 6 },
    { nhan: 'Chậm 20%', diem: 0 }], tu_tinh: false },
  { k: 'diem_v', so: 'V', ten: 'Giấy chứng nhận', muc: [{ nhan: 'Có', diem: 2 }, { nhan: 'Không', diem: 0 }],
    tu_tinh: true }];
const A7 = (o) => [1, 2, 3, 4, 5, 6, 7].map((tt) => ({ tt, ten: `Hồ sơ ${tt}`, ap_dung: tt === 4 ? 'Loại 1 nhập khẩu' : 'Mọi NCC',
  co_kad: ![1, 2, 7].includes(tt), ap: tt === 4 ? false : (tt === 6 ? null : true),
  ket_qua: { 1: 'Có', 2: 'Không', 3: 'Có', 4: 'KAD', 5: 'Có', 6: '', 7: 'Không' }[tt], so_ngay: tt === 1 ? '0801234567' : '',
  hieu_luc: tt === 5 ? '2027-01-01' : '', ...(o || {})[tt] }));
const PHIEU = {
  name: 'DGNCC-2026-0001', supplier: 'NCC-DX', ten_ncc: 'Đỗ Xanh Hải Dương', loai_ncc: 'Nguyên liệu thực phẩm',
  ngay: '2026-10-09', hinh_thuc: 'Đánh giá lần đầu', phan_loai: 'Vật tư loại 1 (ảnh hưởng ATTP)', nguon: 'Trong nước',
  trang_thai: 'Nháp', mat_hang: '', dia_chi: '', nguoi_lien_he: '0912 000 111', mst: '0801234567', ghi_chu: '',
  goi_y_i: 'Đánh giá lần đầu: chấm điểm chất lượng theo mẫu / lô thử.', diem_i: '10', diem_ii: '', diem_iii: '',
  diem_iv: '', quyet_dinh: '', ket_qua: '', han_danh_gia_lai: '', y_kien_qc: '', y_kien_gd: '', ho_so: A7(),
  muc_b: MUC_B, diem_v: 0, tong: 10, toi_da: 42, thieu_a: ['Mục 2: Không', 'Mục 6: chưa chấm'], du_diem: false,
  ket_luan: '', ky: { danh_gia: '', qc: '', duyet: '' }, can_qc: true,
  lua_chon: { hinh_thuc: DS.hinh_thuc, phan_loai: ['Vật tư loại 1 (ảnh hưởng ATTP)', 'Vật tư loại 2'],
    nguon: ['Nhập khẩu', 'Trong nước'] },
  quyen: { lap: true, qc: false, duyet: false, sua: true, gui: true, qc_ky: false, tra_lai: false, xoa: true },
  hom_nay: '2026-10-09' };
a = api();
V.vePhieu(a, PHIEU);
c = a.container;
const hangA = tim(c, (e) => e.classList.contains('sx-dg-a'));
kiem('phần A: 7 mục; mục 1, 2, 7 chỉ Có / Không; mục 4 không áp dụng khóa ở KAD; thiếu phần A hiện rõ',
  hangA.length === 7 && tim(hangA[0], (e) => e.tagName === 'BUTTON').length === 2
  && tim(hangA[3], (e) => e.tagName === 'BUTTON').length === 3
  && tim(hangA[3], (e) => e.tagName === 'BUTTON').every((b) => b.disabled)
  && c.chu.includes('Thiếu phần A: Mục 2: Không; Mục 6: chưa chấm'), c.chu);
kiem('phần B: mức điểm như giấy; V không chấm tay (theo A7); gợi ý điểm I; tổng chưa đủ → —',
  c.chu.includes('Luôn đạt · 10') && c.chu.includes('Không phù hợp · 4') && c.chu.includes('0 điểm — theo mục A7')
  && c.chu.includes('Gợi ý điểm I: Đánh giá lần đầu') && c.chu.includes('Tổng điểm: — / 42'));
tim(hangA[1], (e) => e.tagName === 'BUTTON' && e.textContent === 'Có')[0].bam();
tim(hangA[1], (e) => e.tagName === 'INPUT' && e.type === 'text')[0].doi('HĐ 12/2026');
tim(hangA[5], (e) => e.tagName === 'BUTTON' && e.textContent === 'KAD')[0].bam();
const segB = tim(c, (e) => e.classList.contains('sx-qc-seg'));
const bamMuc = (chu) => tim(c, (e) => e.tagName === 'BUTTON' && e.textContent === chu)[0].bam();
bamMuc('Bình thường · 5');
bamMuc('Phù hợp · 10');
bamMuc('Chậm 15% · 6');
tim(c, (e) => e.tagName === 'INPUT' && e.type === 'text')[0].doi('Đỗ xanh tách vỏ');
traVe = { luu: { name: PHIEU.name }, gui: {} };
nutCo(c, 'LƯU').bam();
await cho();
const p = JSON.parse(goi('luu').at(-1)[1].payload);
kiem('LƯU gửi đúng: đầu phiếu đổi, điểm II–IV (chuỗi mức), phần A chỉ mục đã đổi (kèm số, hiệu lực cũ)',
  p.mat_hang === 'Đỗ xanh tách vỏ' && p.diem_ii === '5' && p.diem_iii === '10' && p.diem_iv === '6' && !('diem_i' in p)
  && JSON.stringify(p.ho_so) === JSON.stringify([{ tt: 2, ket_qua: 'Có', so_ngay: 'HĐ 12/2026', hieu_luc: '' },
    { tt: 6, ket_qua: 'KAD', so_ngay: '', hieu_luc: '' }]) && segB.length >= 7 && lai === 1, p);
a = api();
V.vePhieu(a, PHIEU);
nutCo(a.container, 'GỬI QC KÝ').bam();
await cho();
kiem('GỬI không có gì đổi → không gọi lưu, gọi gửi; vật tư loại 1 ghi "GỬI QC KÝ"', goi('gui').length === 1
  && goi('luu').length === 1 && TOAST.at(-1)[0] === 'Đã gửi');
a = api();
V.vePhieu(a, { ...PHIEU, phan_loai: 'Vật tư loại 2', can_qc: false });
kiem('vật tư loại 2: nút "GỬI GIÁM ĐỐC DUYỆT", ô QC ghi Không áp dụng', !!nutCo(a.container, 'GỬI GIÁM ĐỐC DUYỆT')
  && a.container.chu.includes('Không áp dụng (vật tư loại 2)'));
nutCo(a.container, 'XOÁ').bam();
kiem('XOÁ hỏi lại hai bước', XAC.at(-1).title === 'Xoá phiếu DGNCC-2026-0001?');

console.log('\n-- QC ký, Giám đốc duyệt, trả lại, chỉ xem --');
const CHO = { ...PHIEU, trang_thai: 'Chờ duyệt', ho_so: A7({ 2: { ket_qua: 'Có' }, 6: { ket_qua: 'KAD' } }),
  diem_ii: '5', diem_iii: '4', diem_iv: '10', diem_i: '5', tong: 24, du_diem: true, thieu_a: [], ket_luan: 'Xem xét',
  ky: { danh_gia: 'Ký trên phần mềm: Lê Mua Hàng, 09/10/2026 10:00', qc: 'Ký trên phần mềm: Nguyễn Thị QC, 09/10/2026 10:00', duyet: '' },
  quyen: { lap: false, qc: false, duyet: true, sua: false, gui: false, qc_ky: false, tra_lai: true, xoa: false } };
a = api();
V.vePhieu(a, CHO);
c = a.container;
kiem('Giám đốc: không sửa (ô, nút mức khóa), có DUYỆT, TRẢ LẠI, IN; không LƯU / GỬI / XOÁ',
  !nutCo(c, 'LƯU') && !nutCo(c, 'GỬI') && !nutCo(c, 'XOÁ') && !!nutCo(c, 'DUYỆT') && !!nutCo(c, 'TRẢ LẠI')
  && !!nutCo(c, 'IN') && tim(c, (e) => e.tagName === 'INPUT').every((i) => i.disabled)
  && tim(c, (e) => e.classList.contains('sx-dg-a')).every((h) => tim(h, (b) => b.tagName === 'BUTTON')
    .every((b) => b.disabled)), c.chu);
kiem('ký: hiện chữ ký điện tử của Mua hàng, QC', c.chu.includes('Ký trên phần mềm: Lê Mua Hàng')
  && c.chu.includes('Ký trên phần mềm: Nguyễn Thị QC'));
traVe = { duyet: {}, tra_lai: {} };
nutCo(c, 'DUYỆT').bam();
m = moCuoi();
nutCo(m.body, 'DUYỆT').bam();
await cho();
kiem('phiếu Xem xét: chưa chọn quyết định → báo, không gọi duyệt', !goi('duyet').length
  && TOAST.at(-1)[0] === 'Chọn Chấp nhận hoặc Không chấp nhận.');
tim(m.body, (e) => e.tagName === 'BUTTON' && e.textContent === 'Chấp nhận')[0].bam();
tim(m.body, (e) => e.tagName === 'TEXTAREA')[0].doi('Giao lô thử đạt');
nutCo(m.body, 'DUYỆT').bam();
await cho();
kiem('duyệt gửi quyết định + ý kiến', JSON.stringify(goi('duyet').at(-1)[1]) === JSON.stringify({
  name: CHO.name, quyet_dinh: 'Chấp nhận', y_kien: 'Giao lô thử đạt' }) && m.dong);
nutCo(c, 'TRẢ LẠI').bam();
m = moCuoi();
nutCo(m.body, 'TRẢ LẠI').bam();
await cho();
kiem('trả lại không ý kiến → báo, không gọi', !goi('tra_lai').length && TOAST.at(-1)[0] === 'Ghi ý kiến trả lại.');
tim(m.body, (e) => e.tagName === 'TEXTAREA')[0].doi('Bổ sung hợp đồng');
nutCo(m.body, 'TRẢ LẠI').bam();
await cho();
kiem('trả lại gửi ý kiến', goi('tra_lai').at(-1)[1].y_kien === 'Bổ sung hợp đồng');
a = api();
traVe = { qc_ky: {}, luu: {} };
V.vePhieu(a, { ...CHO, trang_thai: 'Chờ QC', ket_luan: 'Chấp nhận',
  quyen: { lap: false, qc: true, duyet: false, sua: false, gui: false, qc_ky: true, tra_lai: true, xoa: false } });
c = a.container;
kiem('QC (phiếu chờ QC): cùng chấm được (nút mức mở, có LƯU), có QC KÝ', !!nutCo(c, 'LƯU') && !!nutCo(c, 'QC KÝ')
  && tim(c, (e) => e.tagName === 'BUTTON' && e.textContent === 'Tốt · 10').some((b) => !b.disabled));
tim(c, (e) => e.tagName === 'BUTTON' && e.textContent === 'Tốt · 10')[0].bam();
nutCo(c, 'QC KÝ').bam();
m = moCuoi();
nutCo(m.body, 'KÝ').bam();
await cho();
kiem('QC KÝ: lưu điểm vừa đổi trước, rồi ký', goi('luu').length >= 2 && JSON.parse(goi('luu').at(-1)[1].payload).diem_ii
  === '10' && goi('qc_ky').at(-1)[1].name === CHO.name);
a = api();
V.vePhieu(a, { ...CHO, trang_thai: 'Đã duyệt', ket_qua: 'Chấp nhận', han_danh_gia_lai: '2027-10-09',
  quyen: { lap: true, qc: false, duyet: false, sua: false, gui: false, qc_ky: false, tra_lai: false, xoa: false } });
kiem('đã duyệt: chỉ còn IN; hiện kết quả + hạn đánh giá lại', !nutCo(a.container, 'LƯU') && !nutCo(a.container, 'DUYỆT')
  && !!nutCo(a.container, 'IN') && a.container.chu.includes('Kết quả: Chấp nhận')
  && a.container.chu.includes('hạn đánh giá lại 09/10/2027'));

ketThuc('DANHGIANCC-JS');
