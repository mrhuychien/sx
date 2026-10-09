// Màn "Nhật ký cát rang" (D164 — W32: mỗi việc một dòng): views/qc_cat.js.
//
// Vì sao phải có bài này: mỗi việc có ô riêng theo HD.08.03 — nhập cát mà không đòi nguồn / số BM.07.03, loại
// mà không đòi lý do, vệ sinh mà gửi khối lượng, đưa dùng giữa chừng mà vẫn cho khai "số ngày đầu sổ" là sổ sai
// ngay từ màn điện thoại. Nhập NCC khác lần trước phải báo ĐỔI NGUỒN trước khi lưu. Dòng sổ cũ, dòng Ban ISO đã
// xem thì không còn nút lưu. Nạp code THẬT (view + qcui + dom); modal / toast giả — scripts/fakedom.mjs.
//
// Chạy: node scripts/test-cat.mjs   (verify.sh gọi sẵn)

import {
  E, MO, TOAST, XAC, bang, cho, dangChon, ketThuc, kiem, napView, nut, tim,
} from './fakedom.mjs';

const V = await napView('views/qc_cat.js');

console.log('\n-- ô theo việc (như controller) --');
const o = V.oTheoViec;
kiem('nhập cát: nguồn, số BM.07.03, cảm quan, khối lượng bắt buộc', bang(o('Nhập cát'),
  { nguon: true, phieu: true, camQuan: true, kl: true, canKl: true, lyDo: false, veSinh: false }));
kiem('rang khô đưa dùng / bổ sung: nguồn (mặc định), khối lượng bắt buộc, không số phiếu',
  bang(o('Rang khô đưa dùng'), { nguon: true, phieu: false, camQuan: false, kl: true, canKl: true, lyDo: false, veSinh: false })
  && bang(o('Bổ sung'), o('Rang khô đưa dùng')));
kiem('loại cát: lý do, khối lượng không bắt buộc, không nguồn', bang(o('Loại cát'),
  { nguon: false, phieu: false, camQuan: false, kl: true, canKl: false, lyDo: true, veSinh: false }));
kiem('vệ sinh: chỉ thùng / khay', bang(o('Vệ sinh thùng, khay'),
  { nguon: false, phieu: false, camQuan: false, kl: false, canKl: false, lyDo: false, veSinh: true }));

const VIEC = ['Nhập cát', 'Rang khô đưa dùng', 'Bổ sung', 'Loại cát', 'Vệ sinh thùng, khay'];
const dong = (them) => ({
  name: 'CAT-2026-00010', ngay: '2026-10-05', viec: 'Bổ sung', so_cu: 0, ncc_cat: 'CAT-A', ten_ncc: 'Cát sông Lô',
  so_bm0703: '', khoi_luong: 20, thung: 'T1', thay_cat: 0, so_ngay_dung: 6, so_ngay_dau: 0, ly_do_loai: '',
  doi_nguon: 0, kln: '', so_phieu_kln: '', luu_lo_mau: 0, ve_sinh_thung: 0, ve_sinh_khay: 0, cam_quan: '',
  ghi_chu: '', nguoi_lam: 'Anh Tâm', nguoi_ghi: 'qc@x', su_co: null, xem_boi: null, xem_luc: '', creation: '2026-10-05',
  ...them,
});
const duLieu = (them = {}) => ({
  thang: '2026-10', hom_nay: '2026-10-09',
  hien_tai: { so_ngay: 7, ncc: 'CAT-A', ten_ncc: 'Cát sông Lô', ngay_thay: '2026-10-01', ngay_loai: null, dau_so: false },
  nguon_nhap: 'CAT-A', cho_kln: [],
  ncc: [{ name: 'CAT-A', supplier_name: 'Cát sông Lô', duyet: 1 }, { name: 'CAT-B', supplier_name: 'Cát Minh Anh', duyet: 1 }],
  viec: VIEC, toi_da: 0, duoc_ghi: true, la_iso: false, user: 'qc@x',
  ds: [dong({ name: 'CAT-2026-00012', ngay: '2026-10-09', viec: 'Loại cát', ly_do_loai: 'Màu sẫm đen', so_ngay_dung: 8,
    khoi_luong: 130, creation: '2026-10-09' }),
  dong(),
  dong({ name: 'CAT-2026-00008', ngay: '2026-10-01', viec: 'Nhập cát', ncc_cat: 'CAT-B', ten_ncc: 'Cát Minh Anh',
    doi_nguon: 1, so_bm0703: 'PN-12', khoi_luong: 500, so_ngay_dung: 0, cam_quan: 'Đạt' }),
  dong({ name: 'CAT-2026-00002', ngay: '2026-09-22', viec: '', so_cu: 1, so_ngay_dung: 9, khoi_luong: 0, thung: '',
    ve_sinh_thung: 1 })],
  ...them,
});
const GOI = [];
let traVe = duLieu();
const api = {
  container: new E('div'),
  call: async (m, a) => {
    GOI.push([m, a]);
    if (m.endsWith('tong_quan')) return traVe;
    if (m.endsWith('.ghi')) return { name: 'CAT-2026-00013', viec: JSON.parse(a.payload).viec, so_ngay_dung: 7, doi_nguon: 0 };
    return {};
  },
};
const goi = (ten) => GOI.filter(([m]) => m === `sx.api.qc_cat.${ten}`);
const nutCo = (goc, chu) => tim(goc, (e) => e.tagName === 'BUTTON' && e.textContent.includes(chu))[0];
const moCuoi = () => MO[MO.length - 1];
const oSau = (m, nhan) => {
  const ds = [];
  const di = (e) => e.kids.forEach((k) => { ds.push(k); di(k); });
  di(m.body);
  const i = ds.findIndex((k) => k.textContent === nhan);
  return ds.slice(i + 1).find((k) => ['INPUT', 'TEXTAREA', 'SELECT'].includes(k.tagName));
};
const khoiCo = (m, chu) => tim(m.body, (e) => e.tagName === 'DIV' && e.kids.some((k) => k.textContent && k.textContent.startsWith(chu)))[0];
const payload = () => JSON.parse(goi('ghi').at(-1)[1].payload);
const tich = (m, chu) => tim(m.body, (e) => e.tagName === 'LABEL' && e.chu.startsWith(chu))[0].kids[0];
const hien = (k) => k && k.style.display !== 'none';

console.log('\n-- màn chính --');
await V.render(api);
const c = api.container;
kiem('cát đang dùng: đã dùng 7 ngày, nguồn, thay toàn bộ 01/10/2026; chưa quy định tối đa (C19)',
  c.chu.includes('Đã dùng 7 ngày') && c.chu.includes('Cát sông Lô') && c.chu.includes('thay toàn bộ 01/10/2026')
  && c.chu.includes('C19'));
kiem('5 nút việc, mỗi nút có gợi ý (bổ sung không tính lại ngày…)', VIEC.every((v) => !!nutCo(c, v))
  && nutCo(c, 'Bổ sung').textContent.includes('không tính lại'));
kiem('dòng: loại 8 ngày + lý do; nhập ĐỔI NGUỒN + kg; dòng sổ cũ có nhãn, "Ngày có rang"',
  c.chu.includes('09/10 · Loại cát') && c.chu.includes('8 ngày') && c.chu.includes('Lý do loại: Màu sẫm đen')
  && c.chu.includes('ĐỔI NGUỒN · Cát Minh Anh') && c.chu.includes('500 kg') && c.chu.includes('sổ cũ')
  && c.chu.includes('22/09 · Ngày có rang'));

console.log('\n-- nhập cát --');
nutCo(c, 'Nhập cát').bam();
let m = moCuoi();
const ncc = oSau(m, 'Nguồn cát (NCC loại Cát rang) — bắt buộc');
kiem('form nhập: nguồn bắt buộc, số BM.07.03, khối lượng; không có ô lý do loại / vệ sinh',
  !!ncc && hien(khoiCo(m, 'Số BM.07.03')) && !hien(khoiCo(m, 'Lý do loại')) && !hien(khoiCo(m, 'Đã vệ sinh thùng')));
nut(m.body, 'GHI NHẬT KÝ').bam();
await cho();
kiem('chưa chọn nguồn → báo, KHÔNG gọi server', TOAST.at(-1)[0] === 'Chọn nguồn cát.' && !goi('ghi').length);
ncc.doi('CAT-B');
const bao = tim(m.body, (e) => e.classList.contains('sx-cat-doi'))[0];
kiem('chọn NCC khác lần nhập gần nhất → báo ĐỔI NGUỒN, hiện ô kim loại nặng / lọ mẫu',
  bao.style.display === '' && bao.textContent.includes('ĐỔI NGUỒN CÁT') && m.body.chu.includes('Đã lưu một lọ mẫu cát'));
nut(m.body, 'GHI NHẬT KÝ').bam();
await cho();
kiem('thiếu khối lượng → báo, không gọi server', TOAST.at(-1)[0] === 'Ghi khối lượng (kg).' && !goi('ghi').length);
oSau(m, 'Khối lượng (kg)').doi('400');
oSau(m, 'Số BM.07.03 / phiếu nhập mua').doi('PN-0031');
nut(m.body, 'GHI NHẬT KÝ').bam();
await cho();
let p = payload();
kiem('nhập: gửi việc, nguồn, số BM.07.03, kg, kim loại nặng (chưa gửi), không gửi lý do / vệ sinh / số ngày đầu',
  p.viec === 'Nhập cát' && p.ncc_cat === 'CAT-B' && p.so_bm0703 === 'PN-0031' && p.khoi_luong === 400 && p.kln === ''
  && p.ly_do_loai === '' && p.ve_sinh_thung === 0 && !('so_ngay_dau' in p) && p.name === null, p);

console.log('\n-- đổi việc ngay trong form: chỉ gửi ô của việc đang chọn --');
const doiViec = (mm, v) => tim(mm.body, (e) => e.tagName === 'BUTTON' && e.textContent === v)[0].bam();
nutCo(api.container, 'Nhập cát').bam();
m = moCuoi();
oSau(m, 'Nguồn cát (NCC loại Cát rang) — bắt buộc').doi('CAT-B');
oSau(m, 'Số BM.07.03 / phiếu nhập mua').doi('PN-9');
oSau(m, 'Khối lượng (kg)').doi('50');
doiViec(m, 'Loại cát');
kiem('nhập → loại: ẩn nguồn, số phiếu', !hien(khoiCo(m, 'Nguồn cát')) && !hien(khoiCo(m, 'Số BM.07.03')));
nut(m.body, 'Bụi nhiều (hạt vỡ mịn)').bam();
doiViec(m, 'Bổ sung');
kiem('bổ sung: không có ô số BM.07.03 / cảm quan', !hien(khoiCo(m, 'Số BM.07.03')));
doiViec(m, 'Vệ sinh thùng, khay');
tich(m, 'Đã vệ sinh thùng').checked = true;
doiViec(m, 'Loại cát');
nut(m.body, 'GHI NHẬT KÝ').bam();
await cho();
p = payload();
kiem('… lưu là loại: không gửi nguồn / số phiếu đã gõ lúc là nhập, không gửi cờ vệ sinh đã tích lúc là vệ sinh',
  p.viec === 'Loại cát' && p.ncc_cat === '' && p.so_bm0703 === '' && p.ve_sinh_thung === 0
  && p.ly_do_loai === 'Bụi nhiều (hạt vỡ mịn)' && p.khoi_luong === 50, p);
nutCo(api.container, 'Loại cát').bam();
m = moCuoi();
nut(m.body, 'Mùi khét').bam();
doiViec(m, 'Vệ sinh thùng, khay');
tich(m, 'Đã vệ sinh khay').checked = true;
oSau(m, 'Khối lượng (kg)').doi('70');
nut(m.body, 'GHI NHẬT KÝ').bam();
await cho();
p = payload();
kiem('… loại → vệ sinh: không gửi lý do loại, không gửi khối lượng', p.viec === 'Vệ sinh thùng, khay' && p.ly_do_loai === ''
  && p.khoi_luong === 0 && p.ve_sinh_khay === 1, p);
traVe = duLieu({ nguon_nhap: '' });
await V.render(api);
nutCo(api.container, 'Nhập cát').bam();
m = moCuoi();
oSau(m, 'Nguồn cát (NCC loại Cát rang) — bắt buộc').doi('CAT-A');
kiem('lần nhập ĐẦU TIÊN của sổ → không phải đổi nguồn', tim(m.body, (e) => e.classList.contains('sx-cat-doi'))[0]
  .style.display === 'none');
traVe = duLieu({ hien_tai: { so_ngay: 0, ncc: 'CAT-A', ten_ncc: 'Cát sông Lô', ngay_thay: '2026-10-09', ngay_loai: null,
  dau_so: false } });
await V.render(api);
kiem('vừa đưa cát mới, chưa có ngày rang → "Đã dùng 0 ngày" (không phải "sổ chưa có")',
  api.container.chu.includes('Đã dùng 0 ngày') && !api.container.chu.includes('Sổ chưa có'));
traVe = duLieu({ ds: [dong({ name: 'CAT-2026-00001', ngay: '2026-10-01', viec: 'Rang khô đưa dùng', so_ngay_dau: 4,
  thay_cat: 1, so_ngay_dung: 0, creation: '2026-10-09' }), dong({ name: 'CAT-2026-00003', ngay: '2026-10-03',
  viec: 'Rang khô đưa dùng', so_ngay_dau: 0, thay_cat: 1, so_ngay_dung: 0, creation: '2026-10-09' })] });
await V.render(api);
tim(api.container, (e) => e.classList.contains('sx-cat-dong') && e.chu.includes('01/10'))[0].bam();
m = moCuoi();
kiem('sửa dòng đưa dùng đầu sổ đã khai 4 ngày: hiện lại số đã khai', hien(khoiCo(m, 'Cát này đã dùng'))
  && oSau(m, 'Cát này đã dùng bao nhiêu ngày có rang TRƯỚC ngày ghi? (chỉ dòng đầu sổ)').value === 4);
tim(api.container, (e) => e.classList.contains('sx-cat-dong') && e.chu.includes('03/10'))[0].bam();
m = moCuoi();
nut(m.body, 'GHI NHẬT KÝ').bam();
await cho();
kiem('sửa dòng đưa dùng sau đó: không có ô số ngày đầu, không gửi số đó (server giữ nguyên)',
  !hien(khoiCo(m, 'Cát này đã dùng')) && !('so_ngay_dau' in payload()) && payload().name === 'CAT-2026-00003', payload());
traVe = duLieu();
await V.render(api);

console.log('\n-- loại, vệ sinh, đưa dùng, bổ sung --');
nutCo(api.container, 'Loại cát').bam();
m = moCuoi();
kiem('loại: có ô lý do + nút lý do nhanh; không có nguồn; nói số ngày đã dùng hôm nay',
  hien(khoiCo(m, 'Lý do loại')) && !hien(khoiCo(m, 'Nguồn cát')) && m.body.chu.includes('hôm nay: 7 ngày'));
nut(m.body, 'GHI NHẬT KÝ').bam();
await cho();
kiem('loại thiếu lý do → báo', TOAST.at(-1)[0] === 'Ghi lý do loại.');
nut(m.body, 'Màu sẫm đen').bam();
nut(m.body, 'Mùi khét').bam();
nut(m.body, 'GHI NHẬT KÝ').bam();
await cho();
p = payload();
kiem('nút lý do nhanh nối vào ô lý do; loại không gửi nguồn', p.ly_do_loai === 'Màu sẫm đen; Mùi khét' && p.ncc_cat === ''
  && p.viec === 'Loại cát', p);
nutCo(api.container, 'Vệ sinh thùng, khay').bam();
m = moCuoi();
kiem('vệ sinh: không có ô khối lượng', !hien(khoiCo(m, 'Khối lượng (kg)')));
nut(m.body, 'GHI NHẬT KÝ').bam();
await cho();
kiem('vệ sinh không đánh dấu gì → báo', TOAST.at(-1)[0] === 'Đánh dấu vệ sinh thùng hay khay.');
tich(m, 'Đã vệ sinh thùng').checked = true;
nut(m.body, 'GHI NHẬT KÝ').bam();
await cho();
p = payload();
kiem('vệ sinh thùng: gửi cờ thùng, khối lượng 0', p.ve_sinh_thung === 1 && p.ve_sinh_khay === 0 && p.khoi_luong === 0, p);
nutCo(api.container, 'Rang khô đưa dùng').bam();
m = moCuoi();
kiem('đưa dùng giữa chừng (sổ đã có mốc): KHÔNG cho khai số ngày đầu sổ; nhắc ghi loại cát cũ (7 ngày)',
  !hien(khoiCo(m, 'Cát này đã dùng')) && m.body.chu.includes('đã dùng 7 ngày') && m.body.chu.includes('Loại cát'));
traVe = duLieu({ hien_tai: { so_ngay: null, ncc: '', ten_ncc: '', ngay_thay: null, ngay_loai: null, dau_so: true },
  ds: [] });
await V.render(api);
kiem('sổ chưa có lần đưa cát vào máy → nói rõ cách bắt đầu', api.container.chu.includes('Sổ chưa có lần đưa cát vào máy'));
nutCo(api.container, 'Rang khô đưa dùng').bam();
m = moCuoi();
kiem('đưa dùng ĐẦU SỔ: có ô khai số ngày cát đã dùng trước đó', hien(khoiCo(m, 'Cát này đã dùng')));
oSau(m, 'Cát này đã dùng bao nhiêu ngày có rang TRƯỚC ngày ghi? (chỉ dòng đầu sổ)').doi('4');
oSau(m, 'Khối lượng (kg)').doi('120');
nut(m.body, 'GHI NHẬT KÝ').bam();
await cho();
p = payload();
kiem('… gửi số ngày đầu sổ, nguồn bỏ trống (server lấy nguồn lần nhập gần nhất)', p.so_ngay_dau === 4
  && p.viec === 'Rang khô đưa dùng' && p.ncc_cat === '' && p.khoi_luong === 120, p);
nutCo(api.container, 'Bổ sung').bam();
kiem('bổ sung khi chưa có cát đang dùng → form nói ghi "Rang khô đưa dùng" trước',
  moCuoi().body.chu.includes('Máy chưa có cát đang dùng'));
traVe = duLieu({ hien_tai: { so_ngay: null, ncc: 'CAT-A', ten_ncc: 'Cát sông Lô', ngay_thay: '2026-10-01',
  ngay_loai: '2026-10-07', dau_so: false } });
await V.render(api);
kiem('đã loại mà chưa ghi cát mới → thẻ nói ngày loại', api.container.chu.includes('Đã loại cát ngày 07/10/2026'));

console.log('\n-- dòng sổ cũ, dòng đã xem, xoá --');
traVe = duLieu();
await V.render(api);
const the = (chu) => tim(api.container, (e) => e.classList.contains('sx-cat-dong') && e.chu.includes(chu))[0];
the('22/09 · Ngày có rang').bam();
m = moCuoi();
kiem('dòng sổ cũ: chỉ xem (không nút ghi), nói cát ngày thứ 9, không có chọn việc',
  m.body.chu.includes('Dòng sổ cũ') && m.body.chu.includes('9') && !nut(m.body, 'GHI NHẬT KÝ')
  && !nut(m.body, 'Bổ sung') && !nut(m.body, 'Nhập cát'));
the('09/10 · Loại cát').bam();
m = moCuoi();
kiem('dòng mình ghi hôm nay: sửa được (giữ việc), có nút xoá', !!nut(m.body, 'GHI NHẬT KÝ') && !!nutCo(m.body, 'XOÁ DÒNG')
  && dangChon(tim(m.body, (e) => e.classList.contains('sx-qc-seg'))[0]) === 'Loại cát');
nutCo(m.body, 'XOÁ DÒNG').bam();
kiem('xoá dòng loại: hỏi xác nhận, nói số ngày sẽ đếm lại', XAC.at(-1).message.includes('đếm lại'));
await XAC.at(-1).onConfirm();
kiem('… gọi xoa đúng dòng', bang(goi('xoa').at(-1)[1], { name: 'CAT-2026-00012' }));
the('05/10 · Bổ sung').bam();
kiem('dòng ghi hôm trước: không còn nút xoá (QC)', !nutCo(moCuoi().body, 'XOÁ DÒNG'));
traVe = duLieu({ ds: [dong({ xem_luc: '2026-10-09 08:00' })] });
await V.render(api);
the('05/10 · Bổ sung').bam();
kiem('dòng Ban ISO đã xem: QC không có nút lưu', moCuoi().body.chu.includes('Ban ISO đã xem xét')
  && !nut(moCuoi().body, 'GHI NHẬT KÝ'));
traVe = duLieu({ duoc_ghi: false, la_iso: true, user: 'iso@x' });
await V.render(api);
kiem('Ban ISO: không nút ghi việc (QC ghi), chỉ xem', !nutCo(api.container, 'Nhập cát')
  && api.container.chu.includes('QC ghi nhật ký cát'));

ketThuc('CAT-JS');
