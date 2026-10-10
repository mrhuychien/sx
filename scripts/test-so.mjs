// Màn "Sổ" #/so (W43, D172) — views/so.js.
//
// Vì sao phải có bài này: phiếu ghi SINH TỪ CỘT của sổ — thêm sổ chỉ khai định nghĩa, không sửa JS; nên phải chốt
// mỗi kiểu cột ra đúng ô nhập (chọn, giờ, tích, nhiều lựa chọn, danh sách thiết bị) và gửi đúng khóa / giá trị;
// ô bắt buộc trống thì không gửi; người chỉ xem không thấy nút ghi; QC thấy nút xác nhận; Danh mục không có tháng
// mà có "hiện dòng đã ngừng"; xem xét tháng gửi đúng tháng đang xem; in sổ gửi đúng khoảng.
// Nạp code THẬT (view + qcui + dom); modal / toast / bàn số giả — scripts/fakedom.mjs.
//
// Chạy: node scripts/test-so.mjs   (verify.sh gọi sẵn)

import {
  E, MO, TOAST, XAC, cho, dangChon, ketThuc, kiem, napView, tim,
} from './fakedom.mjs';

const V = await napView('views/so.js');
const nutCo = (goc, chu) => tim(goc, (e) => e.tagName === 'BUTTON' && e.textContent.includes(chu))[0];
const moCuoi = () => MO[MO.length - 1];
globalThis.window.location = { hash: '#/so' };

const GOI = [];
let traVe = {};
const api = () => ({
  container: new E('div'),
  call: async (m, a) => {
    GOI.push([m, a]);
    const k = m.split('.').pop();
    if (k in traVe) return typeof traVe[k] === 'function' ? traVe[k](a) : traVe[k];
    return {};
  },
});
const goi = (k) => GOI.filter(([m]) => m.endsWith(`.${k}`));

console.log('\n-- tiện ích --');
kiem('đổi tháng qua năm: 01/2026 − 1 = 12/2025; 12/2026 + 1 = 01/2027',
  V.doiThang('2026-01', -1) === '2025-12' && V.doiThang('2026-12', 1) === '2027-01');
kiem('việc chờ của bước xác nhận: bỏ "(ký)"; sổ không đặt nhãn → "xác nhận"',
  V.viecCho('QC kiểm trước chạy (ký)') === 'QC kiểm trước chạy' && V.viecCho('') === 'xác nhận');
kiem('ô bắt buộc còn trống: chữ trống, tích chưa bật, nhiều lựa chọn rỗng — số 0 không phải trống',
  JSON.stringify(V.thieu([{ key: 'a', nhan: 'A', bat_buoc: 1 }, { key: 'b', nhan: 'B', kieu: 'Check', bat_buoc: 1 },
    { key: 'c', nhan: 'C', kieu: 'MultiSelect', bat_buoc: 1 }, { key: 'd', nhan: 'D', kieu: 'Int', bat_buoc: 1 },
    { key: 'e', nhan: 'E' }], { a: '', b: 0, c: [], d: 0 })) === '["A","B","C"]');

console.log('\n-- danh sách sổ --');
traVe = {
  ds_so: { hom_nay: '2026-10-09', ds: [
    { ma: 'BM.06.05', ten: 'Sổ bảo dưỡng, sửa chữa thiết bị', kieu: 'Ghi theo dòng', so_dong: 3, cho: 1, han: 0,
      chua_xem: [], kiem_lai: 1, bao_duong: 0, nhan_xac_nhan: 'QC kiểm trước chạy (ký)',
      quyen: { ghi: true, xac_nhan: false, xem: true, xem_thang: true } },
    { ma: 'BM.03.01', ten: 'Sổ quản lý thiết bị PCCC', kieu: 'Danh mục', so_dong: 12, cho: 0, han: 2, chua_xem: [],
      kiem_lai: 0, bao_duong: 0, quyen: { ghi: false, xem: true } }] },
};
let a = api();
await V.render(a);
const the = tim(a.container, (e) => e.tagName === 'A' && e.classList.contains('sx-qc-sc'));
kiem('mỗi sổ một thẻ, bấm sang #/so/<mã>', the.length === 2 && the[0].href === '#/so/BM.06.05'
  && the[1].href === '#/so/BM.03.01');
kiem('thẻ BM.06.05: dòng tháng này, chờ QC kiểm, thiết bị chờ kiểm lại, việc của mình',
  the[0].chu.includes('3 dòng tháng này') && the[0].chu.includes('1 chờ QC kiểm trước chạy')
  && the[0].chu.includes('1 thiết bị chờ kiểm lại') && the[0].chu.includes('bạn: ghi, xem xét tháng'), the[0].chu);
kiem('thẻ danh mục: số đang dùng, hạn đến / quá; chỉ xem', the[1].chu.includes('12 đang dùng')
  && the[1].chu.includes('2 hạn đến / quá') && the[1].chu.includes('bạn: chỉ xem'), the[1].chu);
traVe = { ds_so: { ds: [] } };
a = api();
await V.render(a);
kiem('chưa được giao sổ nào → câu báo, không lỗi', a.container.chu.includes('Bạn chưa được giao sổ nào'));

console.log('\n-- một sổ ghi theo dòng: BM.06.05 --');
const COT = [
  { key: 'thiet_bi', nhan: 'Thiết bị (mã, theo BM.06.01)', kieu: 'Link', bat_buoc: 1, lua_chon: [] },
  { key: 'loai', nhan: 'Loại (bảo dưỡng / sửa chữa)', kieu: 'Select', bat_buoc: 1, lua_chon: ['Bảo dưỡng', 'Sửa chữa'] },
  { key: 'noi_dung', nhan: 'Nội dung, chi tiết thay thế', kieu: 'Text', bat_buoc: 1, lua_chon: [] },
  { key: 'gio_dung', nhan: 'Giờ dừng', kieu: 'Time', lua_chon: [] },
  { key: 'da_ve_sinh', nhan: 'Đã vệ sinh, không sót dụng cụ', kieu: 'Check', bat_buoc: 1, lua_chon: [] },
  { key: 'so_lan', nhan: 'Số lần', kieu: 'Int', lua_chon: [] },
  { key: 'nguoi_lam', nhan: 'Người làm (Cơ điện)', kieu: 'Data', bat_buoc: 1, lua_chon: [] },
];
const DN = { ma: 'BM.06.05', ten: 'Sổ bảo dưỡng, sửa chữa thiết bị', kieu: 'Ghi theo dòng', quy_trinh: 'QT.06',
  nhan_xac_nhan: 'QC kiểm trước chạy (ký)', xem_cuoi_thang: 1, nhan_xem_thang: 'Trưởng bộ phận Cơ điện xem xét cuối tháng',
  ghi_chu: 'Cơ điện ghi, QC xác nhận.', cot: COT };
const dong = (o) => ({ name: 'SOD-1', ngay: '2026-10-05', trang_thai: 'Đã ghi', tom_tat: 'TBSX-2024-00003 · Sửa chữa',
  du_lieu: { thiet_bi: 'TBSX-2024-00003', loai: 'Sửa chữa', noi_dung: 'Thay cặp nhiệt', da_ve_sinh: 1,
    nguoi_lam: 'Phạm Cơ Điện' },
  hien: { thiet_bi: 'TBSX-2024-00003 Máy rang M1', loai: 'Sửa chữa', noi_dung: 'Thay cặp nhiệt', gio_dung: '',
    da_ve_sinh: '✓', so_lan: '', nguoi_lam: 'Phạm Cơ Điện' },
  han: [], ten_ghi: 'Phạm Cơ Điện', ky_ghi: 'Ký trên phần mềm: Phạm Cơ Điện, 05/10/2026 08:00', ten_xac_nhan: '',
  ky_xac_nhan: '', sua_doi: [], duoc_sua: true, duoc_xac_nhan: false, duoc_ngung: true, ...o });
const XEM = (o) => ({ dn: DN, quyen: { ghi: true, xac_nhan: false, xem: true, xem_thang: true, co_xac_nhan: true },
  ds: [dong(), dong({ name: 'SOD-2', ngay: '2026-10-08', tom_tat: 'DH-M1 · Sửa chữa', trang_thai: 'Đã xác nhận',
    ten_xac_nhan: 'Nguyễn Thị QC', ky_xac_nhan: 'Ký trên phần mềm: Nguyễn Thị QC, 08/10/2026 10:00', duoc_sua: false,
    duoc_ngung: false, sua_doi: [{ luc: '2026-10-08 09:00', ten: 'Phạm Cơ Điện', hanh_dong: 'Sửa',
      truoc: { ngay: '2026-10-08', du_lieu: { noi_dung: 'cũ' } }, sau: { ngay: '2026-10-08', du_lieu: { noi_dung: 'mới' } } }] })],
  tu: '2026-10-01', den: '2026-10-31', xem_thang: null, hom_nay: '2026-10-09', la_iso: false,
  kiem_lai: [{ dong: 'SOD-1', ngay: '2026-10-05', ma: 'DH-M1', ten: 'Đồng hồ nhiệt M1', bieu_mau: 'BM.06.02' }],
  bao_duong: [], ...o });
globalThis.window.location = { hash: '#/so/BM.06.05' };
traVe = { xem: XEM(), goi_y: [{ v: 'TBSX-2024-00003', nhan: 'Máy rang M1', loai: 'Thiết bị sản xuất' }],
  ghi: { name: 'SOD-9', kiem_lai: 'DH-M1 phải kiểm lại theo BM.06.02' } };
GOI.length = 0;
a = api();
await V.render(a);
let c = a.container;
kiem('đầu sổ: mã, tên, quy trình, ghi chú hướng dẫn; nhắc riêng thiết bị chờ kiểm lại (mức cao)',
  c.chu.includes('BM.06.05') && c.chu.includes('Sổ bảo dưỡng, sửa chữa thiết bị · QT.06')
  && c.chu.includes('Cơ điện ghi, QC xác nhận.') && c.chu.includes('DH-M1 chưa kiểm lại sau sửa chữa ngày 05/10')
  && tim(c, (e) => e.classList.contains('sx-qc-nhac-cao')).length === 1);
kiem('tháng đang xem 10/2026; ▶ tắt (không sang tháng sau hôm nay)', c.chu.includes('Tháng 10/2026')
  && nutCo(c, '▶').disabled && !nutCo(c, '◀').disabled);
const dongs = tim(c, (e) => e.classList.contains('sx-qc-sc') && e.chu.includes('· Sửa chữa'));
kiem('dòng mới trước; dòng chờ xác nhận ghi "chờ QC kiểm trước chạy"; dòng đã sửa ghi số lần sửa',
  dongs.length === 2 && dongs[0].chu.startsWith('08/10') && dongs[1].chu.includes('chờ QC kiểm trước chạy')
  && dongs[0].chu.includes('sửa 1 lần'), dongs.map((d) => d.chu));
kiem('xem xét tháng: chưa xem → nút ĐÃ XEM THÁNG 10/2026', c.chu.includes('Trưởng bộ phận Cơ điện xem xét cuối tháng — tháng 10/2026')
  && !!nutCo(c, 'ĐÃ XEM THÁNG 10/2026'));
nutCo(c, '◀').bam();
await cho();
kiem('◀ → xem tháng 09/2026 (gửi tu = 2026-09-01)', goi('xem').at(-1)[1].tu === '2026-09-01', goi('xem').at(-1)[1]);
V.st.thang['BM.06.05'] = '2026-10';

console.log('\n-- phiếu ghi sinh từ cột --');
a = api();
await V.render(a);
c = a.container;
nutCo(c, '+ GHI DÒNG').bam();
await cho();
let m = moCuoi();
kiem('phiếu: ngày + đủ 7 cột theo thứ tự, ô bắt buộc có dấu *', m.body.chu.includes('Ngày *')
  && m.body.chu.includes('Thiết bị (mã, theo BM.06.01) *') && m.body.chu.includes('Giờ dừng')
  && !m.body.chu.includes('Giờ dừng *') && m.body.kids.length === 1 + COT.length + 1, m.body.kids.length);
kiem('ô Link tải danh sách chọn từ server (goi_y đúng sổ, đúng cột)', goi('goi_y').length === 1
  && goi('goi_y')[0][1].so === 'BM.06.05' && goi('goi_y')[0][1].key === 'thiet_bi');
nutCo(m.body, 'GHI DÒNG').bam();
await cho();
kiem('ô bắt buộc trống → báo, KHÔNG gửi', TOAST.at(-1)[0].startsWith('Chưa ghi: Thiết bị') && !goi('ghi').length,
  TOAST.at(-1));
const sel = tim(m.body, (e) => e.tagName === 'SELECT')[0];
sel.doi('TBSX-2024-00003');
nutCo(m.body, 'Sửa chữa').bam();
tim(m.body, (e) => e.tagName === 'TEXTAREA')[0].doi('Thay cặp nhiệt');
tim(m.body, (e) => e.tagName === 'INPUT' && e.type === 'time')[0].doi('08:15');
nutCo(m.body, '☐ Không').bam();
tim(m.body, (e) => e.tagName === 'INPUT' && e.type === 'text')[0].doi('Phạm Cơ Điện');
kiem('ô Int mở bàn số (không bàn phím hệ thống)', !!nutCo(m.body, '—') || tim(m.body,
  (e) => e.classList.contains('sx-qc-oso-khung')).length >= 1);
nutCo(m.body, 'GHI DÒNG').bam();
await cho();
const g = goi('ghi').at(-1);
const p = g && JSON.parse(g[1].payload);
kiem('gửi ghi: đúng sổ, ngày hôm nay, đúng khóa / giá trị (tích = 1, giờ HH:MM), không gửi ô trống',
  g && g[1].so === 'BM.06.05' && p.ngay === '2026-10-09' && JSON.stringify(p.du_lieu) === JSON.stringify({
    thiet_bi: 'TBSX-2024-00003', loai: 'Sửa chữa', noi_dung: 'Thay cặp nhiệt', gio_dung: '08:15', da_ve_sinh: 1,
    nguoi_lam: 'Phạm Cơ Điện' }), p);
kiem('server báo phải kiểm lại thiết bị đo → hiện cảnh báo', TOAST.some(([s, k]) => k === 'warn'
  && s.includes('DH-M1')) && m.dong);

console.log('\n-- chi tiết dòng, sửa, ngừng --');
a = api();
await V.render(a);
c = a.container;
tim(c, (e) => e.classList.contains('sx-qc-sc') && e.chu.startsWith('05/10'))[0].bam();
m = moCuoi();
kiem('chi tiết: từng cột nhãn + giá trị hiển thị (Link kèm tên, tích ✓), người ghi ký trên phần mềm',
  m.body.chu.includes('Thiết bị (mã, theo BM.06.01) TBSX-2024-00003 Máy rang M1')
  && m.body.chu.includes('Đã vệ sinh, không sót dụng cụ ✓') && m.body.chu.includes('Ghi: Ký trên phần mềm: Phạm Cơ Điện'));
kiem('người ghi: SỬA, NGỪNG DÒNG, tải bản ký tay; không có nút xác nhận', !!nutCo(m.body, 'SỬA')
  && !!nutCo(m.body, 'NGỪNG DÒNG') && !!nutCo(m.body, 'TẢI BẢN KÝ TAY') && !nutCo(m.body, 'QC KIỂM'));
nutCo(m.body, 'SỬA').bam();
const ms = moCuoi();
kiem('SỬA → phiếu điền sẵn dữ liệu dòng (chọn Sửa chữa, tích Có)', ms.kicker.includes('sửa dòng')
  && dangChon(tim(ms.body, (e) => e.classList.contains('sx-qc-seg'))[0]) === 'Sửa chữa' && !!nutCo(ms.body, '☑ Có'));
tim(ms.body, (e) => e.tagName === 'TEXTAREA')[0].doi('Thay cặp nhiệt, siết ốc');
traVe.sua = { name: 'SOD-1', doi: 1 };
nutCo(ms.body, 'LƯU SỬA').bam();
await cho();
const gs = goi('sua').at(-1);
kiem('lưu sửa: đúng dòng, dữ liệu mới', gs && gs[1].name === 'SOD-1'
  && JSON.parse(gs[1].payload).du_lieu.noi_dung === 'Thay cặp nhiệt, siết ốc' && TOAST.at(-1)[0] === 'Đã lưu sửa');
tim(c, (e) => e.classList.contains('sx-qc-sc') && e.chu.startsWith('05/10'))[0].bam();
nutCo(moCuoi().body, 'NGỪNG DÒNG').bam();
const mn = moCuoi();
nutCo(mn.body, 'NGỪNG DÒNG').bam();
kiem('ngừng không lý do → báo, không hỏi xác nhận', TOAST.at(-1)[0] === 'Ghi lý do ngừng.' && !XAC.length);
tim(mn.body, (e) => e.tagName === 'TEXTAREA')[0].value = 'Ghi nhầm máy';
nutCo(mn.body, 'NGỪNG DÒNG').bam();
await XAC.at(-1).onConfirm();
kiem('ngừng có lý do → xác nhận 2 bước → gửi ngừng đúng dòng + lý do', goi('ngung').at(-1)[1].name === 'SOD-1'
  && goi('ngung').at(-1)[1].ly_do === 'Ghi nhầm máy');
tim(c, (e) => e.classList.contains('sx-qc-sc') && e.chu.startsWith('08/10'))[0].bam();
m = moCuoi();
kiem('dòng đã xác nhận: chữ ký QC, lịch sử sửa đọc được (nhãn: cũ → mới), không SỬA',
  m.body.chu.includes('QC kiểm trước chạy (ký): Ký trên phần mềm: Nguyễn Thị QC')
  && m.body.chu.includes('Nội dung, chi tiết thay thế: cũ → mới') && !nutCo(m.body, 'SỬA'));

console.log('\n-- QC: chỉ xác nhận --');
traVe = { xem: XEM({ quyen: { ghi: false, xac_nhan: true, xem: true, xem_thang: false, co_xac_nhan: true },
  ds: [dong({ duoc_sua: false, duoc_ngung: false, duoc_xac_nhan: true })] }),
xac_nhan: { name: 'SOD-1', kiem_lai: 'DH-M1 phải kiểm lại theo BM.06.02' } };
a = api();
await V.render(a);
c = a.container;
kiem('QC không có + GHI DÒNG, không có nút xem tháng', !nutCo(c, '+ GHI DÒNG') && !nutCo(c, 'ĐÃ XEM THÁNG'));
tim(c, (e) => e.classList.contains('sx-qc-sc') && e.chu.startsWith('05/10'))[0].bam();
nutCo(moCuoi().body, 'QC KIỂM TRƯỚC CHẠY').bam();
const mx = moCuoi();
tim(mx.body, (e) => e.tagName === 'TEXTAREA')[0].value = 'Đã kiểm, không sót dụng cụ';
nutCo(mx.body, 'XÁC NHẬN').bam();
await cho();
kiem('xác nhận: gửi đúng dòng + ý kiến; báo thiết bị phải kiểm lại', goi('xac_nhan').at(-1)[1].name === 'SOD-1'
  && goi('xac_nhan').at(-1)[1].y_kien === 'Đã kiểm, không sót dụng cụ' && TOAST.some(([s, k]) => k === 'warn'));

console.log('\n-- xem xét tháng, in --');
traVe = { xem: XEM(), xem_thang: { thang: '10/2026' } };
a = api();
await V.render(a);
c = a.container;
nutCo(c, 'ĐÃ XEM THÁNG 10/2026').bam();
const mt = moCuoi();
tim(mt.body, (e) => e.tagName === 'TEXTAREA')[0].value = 'Đủ dòng, QC ký đủ';
nutCo(mt.body, 'XÁC NHẬN ĐÃ XEM').bam();
await cho();
kiem('xem tháng: gửi đúng sổ, tháng đang xem, nhận xét', JSON.stringify(goi('xem_thang').at(-1)[1])
  === JSON.stringify({ so: 'BM.06.05', thang: '2026-10', nhan_xet: 'Đủ dòng, QC ký đủ' }));
traVe.xem = XEM({ xem_thang: { ky: 'Ký trên phần mềm: Trưởng Cơ Điện, 31/10/2026 16:00', nhan_xet: 'ok', can_xem_lai: false } });
a = api();
await V.render(a);
c = a.container;
kiem('đã xem: hiện chữ ký + nhận xét, không còn nút', c.chu.includes('Ký trên phần mềm: Trưởng Cơ Điện')
  && !nutCo(c, 'ĐÃ XEM THÁNG'));
traVe.in_so = '<div>in</div>';
nutCo(c, 'IN SỔ THÁNG 10/2026').bam();
await cho();
kiem('in sổ tháng: gửi đúng sổ + ngày đầu tháng (trình duyệt chặn pop-up → báo)',
  JSON.stringify(goi('in_so').at(-1)[1]) === JSON.stringify({ so: 'BM.06.05', tu: '2026-10-01' })
  && TOAST.at(-1)[0].includes('chặn cửa sổ in'));

console.log('\n-- danh mục BM.03.03: không tháng, hiện dòng ngừng, nhiều lựa chọn --');
const DM = { ma: 'BM.03.03', ten: 'Sổ quản lý thiết bị kiểm định an toàn', kieu: 'Danh mục', cot: [
  { key: 'thiet_bi', nhan: 'Thiết bị', kieu: 'Data', bat_buoc: 1, lua_chon: [] },
  { key: 'thang_ke_hoach', nhan: 'Kế hoạch kiểm định an toàn năm (tháng)', kieu: 'MultiSelect',
    lua_chon: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'] },
  { key: 'han_tiep', nhan: 'Hạn kiểm định tiếp', kieu: 'Date', han: 1, bao_truoc: 30, lua_chon: [] }] };
globalThis.window.location = { hash: '#/so/BM.03.03' };
traVe = { xem: { dn: DM, quyen: { ghi: true, xem: true }, ds: [{ name: 'SOD-5', ngay: '2026-10-01', trang_thai: 'Đã ghi',
  tom_tat: 'Nồi hơi · 3, 9 · 20/10/2026', du_lieu: {}, hien: {}, sua_doi: [], ten_ghi: 'Hoàng Hành Chính',
  han: [{ key: 'han_tiep', nhan: 'Hạn kiểm định tiếp', han: '2026-10-20', con: 11, bao_truoc: 30 }] }],
hom_nay: '2026-10-09', tu: '', den: '' }, ghi: { name: 'SOD-6' } };
a = api();
await V.render(a);
c = a.container;
kiem('danh mục: không có ◀ tháng ▶, có "Hiện cả dòng đã ngừng"; dòng ghi hạn còn 11 ngày',
  !nutCo(c, '◀') && !!nutCo(c, 'Hiện cả dòng đã ngừng') && c.chu.includes('Hạn kiểm định tiếp: còn 11 ngày'));
nutCo(c, 'Hiện cả dòng đã ngừng').bam();
await cho();
kiem('bật hiện dòng ngừng → gửi ngung = 1', goi('xem').at(-1)[1].ngung === 1);
V.st.ngung['BM.03.03'] = false;
a = api();
await V.render(a);
nutCo(a.container, '+ GHI DÒNG').bam();
m = moCuoi();
kiem('danh mục: ô ngày là "Ngày ghi / cập nhật", không bắt buộc', m.body.chu.includes('Ngày ghi / cập nhật'));
tim(m.body, (e) => e.tagName === 'INPUT' && e.type === 'text')[0].doi('Nồi hơi');
const chips = tim(m.body, (e) => e.tagName === 'BUTTON' && e.classList.contains('sx-qc-vi-o'));
chips.find((b) => b.textContent === '9').bam();
chips.find((b) => b.textContent === '3').bam();
chips.find((b) => b.textContent === '12').bam();
chips.find((b) => b.textContent === '12').bam();
tim(m.body, (e) => e.tagName === 'INPUT' && e.type === 'date').at(-1).doi('2027-03-20');
nutCo(m.body, 'GHI DÒNG').bam();
await cho();
kiem('nhiều lựa chọn gửi theo thứ tự danh sách (bấm 9, 3; 12 bật rồi tắt), ngày hạn ISO',
  JSON.stringify(JSON.parse(goi('ghi').at(-1)[1].payload).du_lieu) === JSON.stringify({ thiet_bi: 'Nồi hơi',
    thang_ke_hoach: ['3', '9'], han_tiep: '2027-03-20' }), goi('ghi').at(-1)[1].payload);
nutCo(a.container, '+ GHI DÒNG').bam();
m = moCuoi();
tim(m.body, (e) => e.tagName === 'INPUT' && e.type === 'text')[0].doi('Lò hơi');
const c5 = tim(m.body, (e) => e.tagName === 'BUTTON' && e.textContent === '5')[0];
c5.bam();
c5.bam();
const nh = tim(m.body, (e) => e.tagName === 'INPUT' && e.type === 'date').at(-1);
nh.doi('2027-01-01');
nh.doi('');
nutCo(m.body, 'GHI DÒNG').bam();
await cho();
kiem('ô bật rồi xoá (nhiều lựa chọn bỏ hết, ngày xoá trống) → không gửi khóa đó',
  JSON.stringify(JSON.parse(goi('ghi').at(-1)[1].payload).du_lieu) === JSON.stringify({ thiet_bi: 'Lò hơi' }),
  goi('ghi').at(-1)[1].payload);
kiem('in danh mục: chỉ gửi mã sổ (danh mục hiện hành)', (() => {
  nutCo(a.container, 'IN SỔ (DANH MỤC HIỆN HÀNH)').bam();
  return JSON.stringify(goi('in_so').at(-1)[1]) === JSON.stringify({ so: 'BM.03.03' });
})());

console.log('\n-- W44: BM.05.02 rủi ro — RR, cấp độ app tính; chọn nhân viên theo họ tên --');
kiem('lựa chọn nhân viên hiện "họ tên · mã"; thiết bị "mã · tên (loại)"',
  V.tenChon({ v: 'HR-EMP-00003', nhan: 'Lê Văn Bột', an_ma: 1 }) === 'Lê Văn Bột · HR-EMP-00003'
  && V.tenChon({ v: 'DH-M1', nhan: 'Đồng hồ nhiệt M1', loai: 'Đồng hồ nhiệt', an_ma: 0 })
    === 'DH-M1 · Đồng hồ nhiệt M1 (Đồng hồ nhiệt)');
const RRDN = { ma: 'BM.05.02', ten: 'Bảng xác định rủi ro', kieu: 'Danh mục', cot_tinh: ['rr', 'cap_do'], cot: [
  { key: 'rui_ro', nhan: 'Rủi ro', kieu: 'Text', bat_buoc: 1, lua_chon: [] },
  ...['a', 'b', 'c', 'd'].map((k) => ({ key: k, nhan: k.toUpperCase(), kieu: 'Select', bat_buoc: 1,
    lua_chon: ['1', '2', '3', '4'] })),
  { key: 'rr', nhan: 'RR = A + B + C + D', kieu: 'Int', lua_chon: [] },
  { key: 'cap_do', nhan: 'Cấp độ kiểm soát', kieu: 'Select', lua_chon: ['Cấp độ 1', 'Cấp độ 2', 'Cấp độ 3'] }] };
globalThis.window.location = { hash: '#/so/BM.05.02' };
traVe = { xem: { dn: RRDN, quyen: { ghi: true, xem: true }, ds: [], hom_nay: '2026-10-09', tu: '', den: '' },
  ghi: { name: 'SOD-9' } };
a = api();
await V.render(a);
nutCo(a.container, '+ GHI DÒNG').bam();
m = moCuoi();
kiem('phiếu không có ô RR, cấp độ (chỉ ngày, rủi ro, A, B, C, D); ghi rõ phần app tự tính',
  !m.body.chu.includes('Cấp độ 1') && m.body.chu.includes('App tự tính: RR = A + B + C + D, Cấp độ kiểm soát.')
  && m.body.kids.length === 1 + 5 + 1 + 1, m.body.kids.length);
tim(m.body, (e) => e.tagName === 'TEXTAREA')[0].doi('Cháy máy rang');
const ba = tim(m.body, (e) => e.tagName === 'BUTTON' && e.textContent === '3');
ba[0].bam();
ba[1].bam();
ba[2].bam();
const nGhi = goi('ghi').length;
nutCo(m.body, 'GHI DÒNG').bam();
await cho();
kiem('chưa chọn D → báo "Chưa ghi: D *", không gửi', TOAST.at(-1)[0].startsWith('Chưa ghi: D')
  && goi('ghi').length === nGhi, TOAST.at(-1));
tim(m.body, (e) => e.tagName === 'BUTTON' && e.textContent === '2')[3].bam();
nutCo(m.body, 'GHI DÒNG').bam();
await cho();
kiem('gửi A, B, C, D (chuỗi 1–4), không gửi RR / cấp độ — server tính',
  JSON.stringify(JSON.parse(goi('ghi').at(-1)[1].payload).du_lieu) === JSON.stringify({ rui_ro: 'Cháy máy rang',
    a: '3', b: '3', c: '3', d: '2' }), goi('ghi').at(-1)[1].payload);

console.log('\n-- W44: mục T4 lượt Tuần theo từng vật (components/qcui.js) --');
const UI = await napView('components/qcui.js');

console.log('\n-- D186: hộp nhắc gập một dòng, bấm mới mở (components/qcui.js veNhac) --');
const NH = [
  { muc_do: 'thuong', tieu_de: '2 ngày đi thiếu lượt', chi_tiet: 'a', route: '#/qc' },
  { muc_do: 'cao', tieu_de: 'Có rang mà nhật ký cát không có cát đang dùng', chi_tiet: 'b', route: '#/qc/cat' },
  { muc_do: 'cao', tieu_de: 'Lượt quá hạn', chi_tiet: 'c' }];
const h1 = UI.veNhac(NH);
const tom = tim(h1, (e) => e.tagName === 'SUMMARY')[0];
kiem('gập sẵn: <details> chưa mở; dòng tóm tắt = số việc, số mức cao (chữ đỏ), việc mức cao đầu tiên + "và N việc '
  + 'khác"; có mức cao thì viền đỏ',
  h1.tagName === 'DETAILS' && !h1.open && h1.classList.contains('sx-qc-nhac-gap-cao') && !!tom
  && tom.textContent.includes('🔔 3 việc cần chú ý') && tom.innerHTML.includes('<b class="sx-qc-nhac-dem-cao">2 mức cao</b>')
  && tom.textContent.includes('Có rang mà nhật ký cát không có cát đang dùng · và 2 việc khác'), tom && tom.textContent);
const lk = tim(h1, (e) => e.tagName === 'A');
kiem('bấm mở: đủ mọi việc, mỗi việc một liên kết tới màn của nó (không có thì #/qc), mức cao viền đỏ',
  lk.length === 3 && lk[1].href === '#/qc/cat' && lk[2].href === '#/qc'
  && tim(h1, (e) => e.classList.contains('sx-qc-nhac-cao')).length === 2);
const h2 = UI.veNhac([{ muc_do: 'thuong', tieu_de: 'Một việc', chi_tiet: '' }], { tieu_de: 'QC đang treo 1 việc', mo: true });
kiem('không mức cao: viền vàng, không chữ "mức cao"; một việc thì không "và … việc khác"; tiêu đề riêng; mở sẵn khi cần',
  h2.classList.contains('sx-qc-nhac-gap-thuong') && !h2.chu.includes('mức cao') && !h2.chu.includes('việc khác')
  && h2.chu.includes('🔔 QC đang treo 1 việc') && h2.open === true, h2.chu);
kiem('không có việc → không vẽ gì', UI.veNhac([]) === null && UI.veNhac(null) === null);
kiem('t4TheoVat: có vật Không đạt → Không đạt; đủ Đạt → Đạt; còn vật trống / danh sách rỗng → chưa chấm',
  UI.t4TheoVat([{ ket_qua: 'Đạt' }, { ket_qua: 'Không đạt' }]) === 'Không đạt'
  && UI.t4TheoVat([{ ket_qua: 'Đạt' }]) === 'Đạt' && UI.t4TheoVat([{ ket_qua: 'Đạt' }, { ket_qua: '' }]) === ''
  && UI.t4TheoVat([]) === '');
const vk = { so: 'BM.PRP.05', ds: [
  { vat: 'S1', ma: 'K-01', ten: 'Đèn huỳnh quang · Phòng đóng gói', ket_qua: '', ghi_chu: '' },
  { vat: 'S2', ma: 'K-02', ten: 'Cửa kính · Kho', ket_qua: 'Đạt', ghi_chu: '' }] };
const doiVat = [];
const w = UI.oVatKinh({ f: 't4_den_kinh', so: 'T4', nhan: 'Đèn, kính có bảo vệ' }, vk, (x) => doiVat.push({ ...x }), false);
const gcK = tim(w, (e) => e.tagName === 'INPUT');
kiem('mỗi vật một hàng "mã · vật · vị trí"; tổng "còn 1 vật"; ô ghi chú ẩn khi chưa Không đạt',
  w.chu.includes('K-01 · Đèn huỳnh quang · Phòng đóng gói') && w.chu.includes('K-02 · Cửa kính · Kho')
  && w.chu.includes('còn 1 vật') && gcK.length === 2 && gcK.every((i) => i.style.display === 'none'), w.chu);
tim(w, (e) => e.tagName === 'BUTTON' && e.textContent === '✕ Không')[0].bam();
kiem('bấm ✕ Không ở K-01 → báo đổi đúng vật; tổng T4 "✕ Không đạt"; hiện ô ghi chú của K-01',
  doiVat.at(-1).vat === 'S1' && doiVat.at(-1).ket_qua === 'Không đạt' && w.chu.includes('✕ Không đạt')
  && gcK[0].style.display === '' && w.dataset.tt === 'Không đạt', doiVat);
gcK[0].doi(' vỡ chụp ');
kiem('ghi chú (cắt khoảng trắng) gửi kèm vật', doiVat.at(-1).vat === 'S1' && doiVat.at(-1).ghi_chu === 'vỡ chụp');
tim(w, (e) => e.tagName === 'BUTTON' && e.textContent === '✓ Đạt')[0].bam();
kiem('đổi K-01 sang Đạt → bỏ ghi chú; mọi vật Đạt → tổng "✓ Đạt"', doiVat.at(-1).ket_qua === 'Đạt'
  && doiVat.at(-1).ghi_chu === '' && w.chu.includes('✓ Đạt') && gcK[0].style.display === 'none');
tim(w, (e) => e.tagName === 'BUTTON' && e.textContent === '✓ Đạt')[0].bam();
kiem('bấm lại nút đang chọn → bỏ trống vật đó (T4 về chưa chấm)', doiVat.at(-1).ket_qua === ''
  && w.chu.includes('còn 1 vật'));
const wk = UI.oVatKinh({ f: 't4_den_kinh', so: 'T4', nhan: 'Đèn, kính có bảo vệ' }, vk, () => {}, true);
kiem('lượt đã khóa: nút, ô ghi chú bị khóa', tim(wk, (e) => e.tagName === 'BUTTON' || e.tagName === 'INPUT')
  .every((e) => e.disabled));

ketThuc('SO-JS');
