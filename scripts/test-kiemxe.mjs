// Màn "Kiểm xe" BM.09.01 (D165 — W34): views/qc_kiemxe.js.
//
// Vì sao phải có bài này: màn là chỗ QC đóng dấu "QC kiểm" cho chuyến kiểm ngẫu nhiên và Trưởng Ban ISO bấm
// "Đã xem tháng". Tuần có chuyến mà chưa chuyến nào QC kiểm phải hiện ngay (vàng khi tuần còn chạy, đỏ khi đã
// hết); chỉ chuyến còn trong hạn mới có nút QC KIỂM; dấu gửi đúng chứng từ kèm nhận xét; bỏ dấu chỉ người đóng
// dấu trong ngày / Ban ISO; QC không có nút xem tháng. Nạp code THẬT (view + qcui + dom); modal / toast giả.
//
// Chạy: node scripts/test-kiemxe.mjs   (verify.sh gọi sẵn)

import {
  E, MO, TOAST, XAC, ketThuc, kiem, napView, tim,
} from './fakedom.mjs';

const V = await napView('views/qc_kiemxe.js');

console.log('\n-- tuần thứ Hai – Chủ nhật (hàm thuần) --');
const tt = (t) => V.trangThaiTuan(t);
kiem('không chuyến → không màu; có chuyến QC kiểm → xanh, nói số',
  tt({ so_chuyen: 0, so_qc: 0 }).kieu === '' && tt({ so_chuyen: 4, so_qc: 1 }).kieu === 'dong'
  && tt({ so_chuyen: 4, so_qc: 1 }).chu === 'QC kiểm 1/4 chuyến');
kiem('có chuyến, chưa QC kiểm: tuần đang chạy vàng (còn làm được), tuần đã hết đỏ (lỡ)',
  tt({ so_chuyen: 3, so_qc: 0, qua: false }).kieu === 'giu' && tt({ so_chuyen: 3, so_qc: 0, qua: true }).kieu === 'cao'
  && tt({ so_chuyen: 3, so_qc: 0, qua: true }).chu === '3 chuyến — KHÔNG chuyến nào QC kiểm');
const D0 = { user: 'qc@x', hom_nay: '2026-10-09', la_iso: false };
kiem('bỏ dấu QC: người đóng dấu trong ngày; người khác / qua ngày / tháng đã xem → không; Ban ISO → được',
  V.boDuocQc({ qc_kiem: 'qc@x', qc_luc: '2026-10-09 08:00', xem_luc: '' }, D0)
  && !V.boDuocQc({ qc_kiem: 'qc2@x', qc_luc: '2026-10-09 08:00', xem_luc: '' }, D0)
  && !V.boDuocQc({ qc_kiem: 'qc@x', qc_luc: '2026-10-08 08:00', xem_luc: '' }, D0)
  && !V.boDuocQc({ qc_kiem: 'qc@x', qc_luc: '2026-10-09 08:00', xem_luc: '2026-10-09 09:00' }, D0)
  && V.boDuocQc({ qc_kiem: 'qc2@x', qc_luc: '2026-10-01 08:00', xem_luc: '' }, { ...D0, la_iso: true })
  && !V.boDuocQc({ qc_kiem: '', qc_luc: '', xem_luc: '' }, { ...D0, la_iso: true }));

const MUC = (san = 'Đạt') => [['Sạch khô', 'Thùng xe sạch, khô'], ['Mùi', 'Không mùi lạ'], ['Kín/che', 'Kín, có bạt'],
  ['Hàng chung', 'Không chở chung'], ['Sàn', 'Sàn không đinh']].map(([cot, yc], i) => ({
  f: `f${i}`, cot, yc, gt: cot === 'Sàn' ? san : 'Đạt' }));
const chuyen = (them) => ({
  doctype: 'Sales Invoice', name: 'ACC-SINV-2026-00012', ngay: '2026-10-08', chieu: 'Giao hàng',
  doi_tac: 'Đại lý Nam Định', nhap: false, pb: 2, bien_so: '29C-123.45', don_vi: 'Nhà xe Minh Phát', tai_xe: 'Anh Ba',
  muc: MUC(), ket_luan: 'Đạt', xu_ly: '', nguoi_kiem: 'kho@x', ten_nguoi_kiem: 'Thủ kho Hà', qc_kiem: '', ten_qc: '',
  qc_luc: '', qc_nhan_xet: '', xem_boi: '', ten_xem: '', xem_luc: '', duoc_qc: true,
  hang: ['Bánh đậu xanh Rồng Vàng 250g · 40 Hộp · HSD 15/04/2027'], ...them,
});
const duLieu = (them = {}) => ({
  thang: '2026-10', hom_nay: '2026-10-09', tu: '2026-10-01', den: '2026-10-31',
  tuan: [{ tu: '2026-10-05', den: '2026-10-11', so_chuyen: 2, so_qc: 0, nay: true, qua: false },
    { tu: '2026-09-28', den: '2026-10-04', so_chuyen: 2, so_qc: 0, nay: false, qua: true }],
  ds: [chuyen(),
    chuyen({ doctype: 'Purchase Receipt', name: 'MAT-PRE-2026-00031', ngay: '2026-10-01', chieu: 'Nhận nguyên liệu',
      doi_tac: 'NCC Đỗ Xanh', muc: MUC('Không đạt'), ket_luan: 'Không đạt', xu_ly: 'Sàn còn đinh — cách ly lô',
      duoc_qc: false, hang: [] }),
    chuyen({ name: 'ACC-SINV-2026-00009', ngay: '2026-10-06', nhap: true, duoc_qc: false, qc_kiem: 'qc@x', ten_qc: 'QC Lan',
      qc_luc: '2026-10-09 08:05', qc_nhan_xet: 'Đúng như thủ kho ghi' })],
  xem: null, chua_xem: 2, so_nhap: 1, so_ngay_qc: 2,
  duoc_ghi: true, duoc_xem_thang: false, la_iso: false, user: 'qc@x', ...them,
});
const GOI = [];
let traVe = duLieu();
const api = {
  container: new E('div'),
  call: async (m, a) => {
    GOI.push([m, a]);
    if (m.endsWith('tong_quan')) return traVe;
    return {};
  },
};
const goi = (ten) => GOI.filter(([m]) => m === `sx.api.qc_kiemxe.${ten}`);
const nutCo = (goc, chu) => tim(goc, (e) => e.tagName === 'BUTTON' && e.textContent.includes(chu))[0];
const moCuoi = () => MO[MO.length - 1];
const the = (c, ten) => tim(c, (e) => e.classList.contains('sx-qc-sc') && e.chu.includes(ten))[0];

console.log('\n-- màn Kiểm xe (QC) --');
await V.render(api);
const c = api.container;
kiem('đầu màn: BM.09.01 · tháng 10/2026', c.chu.includes('🚚 Kiểm xe') && c.chu.includes('BM.09.01 · tháng 10/2026'));
const tuan = tim(c, (e) => e.classList.contains('sx-kx-tuan'));
kiem('mỗi tuần một dòng: tuần này vàng "chưa", tuần trước đỏ "KHÔNG"',
  tuan.length === 2 && tuan[0].chu.includes('05/10 – 11/10') && tuan[0].chu.includes('tuần này')
  && tim(tuan[0], (e) => e.classList.contains('sx-qc-tag-giu')).length === 1
  && tim(tuan[1], (e) => e.classList.contains('sx-qc-tag-cao'))[0].textContent === '2 chuyến — KHÔNG chuyến nào QC kiểm');
const t1 = the(c, '08/10 · Giao hàng');
const t2 = the(c, 'NCC Đỗ Xanh');
const t3 = the(c, '06/10');
kiem('thẻ chuyến: ngày · chiều · đối tác, biển số, kết luận, người kiểm',
  t1.chu.includes('08/10 · Giao hàng · Đại lý Nam Định') && t1.chu.includes('29C-123.45') && t1.chu.includes('xe Đạt')
  && t1.chu.includes('người kiểm Thủ kho Hà'));
kiem('chuyến xe Không đạt: nói mục K + xử lý', t2.chu.includes('K: Sàn — Sàn còn đinh — cách ly lô'));
kiem('chuyến nháp / đã có QC kiểm: chip "chưa duyệt", "QC kiểm · QC Lan 08:05"', t3.chu.includes('chưa duyệt')
  && t3.chu.includes('QC kiểm · QC Lan 08:05'));
kiem('nút QC KIỂM chỉ ở chuyến còn trong hạn chưa có dấu; còn lại XEM',
  !!nutCo(t1, 'QC KIỂM CHUYẾN NÀY') && !nutCo(t2, 'QC KIỂM') && !!nutCo(t2, 'XEM') && !nutCo(t3, 'QC KIỂM'));
kiem('QC không có nút Đã xem tháng; có nút in BM.09.01 của tháng',
  !nutCo(c, 'ĐÃ XEM THÁNG') && !!nutCo(c, '🖨 IN BM.09.01 — tháng 10/2026') && c.chu.includes('Chưa xem.'));

console.log('\n-- QC KIỂM một chuyến --');
nutCo(t1, 'QC KIỂM CHUYẾN NÀY').bam();
let m = moCuoi();
kiem('mở chuyến: đơn vị VC, lái xe ký, người kiểm, hàng + HSD; năm mục Đ, kết luận',
  m.kicker === 'BM.09.01 · ACC-SINV-2026-00012' && m.body.chu.includes('Đơn vị vận chuyển: Nhà xe Minh Phát')
  && m.body.chu.includes('Lái xe ký: Anh Ba') && m.body.chu.includes('HSD 15/04/2027')
  && tim(m.body, (e) => e.classList.contains('sx-kx-dk')).map((e) => e.textContent).join('') === 'ĐĐĐĐĐĐ'
  && m.body.chu.includes('Thùng xe sạch, khô'));
tim(m.body, (e) => e.tagName === 'TEXTAREA')[0].doi('Sàn sạch, bạt kín');
nutCo(m.body, 'QC ĐÃ KIỂM XE NÀY').bam();
await new Promise((r) => { setTimeout(r, 0); });
kiem('gửi đúng chứng từ + nhận xét, đóng hộp, tải lại', goi('qc_kiem').length === 1
  && JSON.stringify(goi('qc_kiem')[0][1]) === JSON.stringify({ doctype: 'Sales Invoice', name: 'ACC-SINV-2026-00012',
    nhan_xet: 'Sàn sạch, bạt kín' }) && m.dong && TOAST.some(([s]) => s === 'Đã ghi QC kiểm')
  && goi('tong_quan').length === 2);
nutCo(t2, 'XEM').bam();
m = moCuoi();
kiem('chuyến quá hạn: không có nút đóng dấu, nói vì sao; ô K đỏ',
  !nutCo(m.body, 'QC ĐÃ KIỂM') && m.body.chu.includes('trong 2 ngày kể từ ngày chuyến')
  && tim(m.body, (e) => e.classList.contains('sx-kx-k')).length === 2
  && tim(m.body, (e) => e.classList.contains('sx-kx-dk')).map((e) => e.textContent).join('') === 'ĐĐĐĐKK');
nutCo(t3, 'XEM').bam();
m = moCuoi();
kiem('chuyến đã có dấu của mình hôm nay: hiện dấu + nhận xét, nút bỏ dấu', m.body.chu.includes('QC kiểm: QC Lan · 09/10/2026 08:05 — Đúng như thủ kho ghi')
  && !!nutCo(m.body, 'BỎ DẤU QC KIỂM'));
nutCo(m.body, 'BỎ DẤU QC KIỂM').bam();
kiem('bỏ dấu phải xác nhận', XAC.length === 1 && goi('bo_qc_kiem').length === 0);
await XAC[0].onConfirm();
kiem('… xác nhận → gửi đúng chứng từ', JSON.stringify(goi('bo_qc_kiem')[0][1])
  === JSON.stringify({ doctype: 'Sales Invoice', name: 'ACC-SINV-2026-00009' }));

console.log('\n-- Trưởng Ban ISO --');
traVe = duLieu({ duoc_ghi: false, duoc_xem_thang: true, la_iso: true, user: 'iso@x' });
await V.render(api);
const c2 = api.container;
const t1b = the(c2, '08/10 · Giao hàng');
kiem('Ban ISO không có nút QC KIỂM (chỉ XEM)', !nutCo(t1b, 'QC KIỂM') && !!nutCo(t1b, 'XEM'));
nutCo(c2, 'ĐÃ XEM THÁNG 10/2026').bam();
kiem('Đã xem tháng: xác nhận, nói số chuyến đã duyệt + chuyến chưa duyệt chờ lần sau', XAC.length === 2
  && XAC[1].message.includes('Ký xem 2 chuyến đã duyệt — 1 chuyến chưa duyệt sẽ chờ lần xem sau'));
await XAC[1].onConfirm();
kiem('… gửi tháng', JSON.stringify(goi('xem_thang')[0][1]) === JSON.stringify({ thang: '2026-10' }));
traVe = duLieu({ xem: { boi: 'iso@x', ten: 'Nguyễn Huy Chiến', luc: '2026-10-09 16:00' }, chua_xem: 0,
  duoc_xem_thang: true });
await V.render(api);
kiem('đã xem: tên + ngày, hết nút', api.container.chu.includes('Nguyễn Huy Chiến · 09/10/2026')
  && !nutCo(api.container, 'ĐÃ XEM THÁNG'));
nutCo(api.container, '🖨 IN BM.09.01').bam();
await new Promise((r) => { setTimeout(r, 0); });
kiem('in: gọi in_so_kiem_xe đúng khoảng tháng', JSON.stringify(goi('in_so_kiem_xe')[0][1])
  === JSON.stringify({ tu: '2026-10-01', den: '2026-10-31' }));

ketThuc('KIEMXE-JS');
