// Màn "Tài liệu" #/tailieu (W42, D171) — views/tailieu.js.
//
// Vì sao phải có bài này: "Đã đọc, hiểu" thay chữ ký nhận tài liệu (C28) chỉ có giá trị khi người ta ĐÃ MỞ tệp —
// nút phải tắt tới khi server ghi giờ mở; nút mở phải là thẻ <a> trỏ thẳng tệp (bấm sau một lời gọi mạng thì điện
// thoại chặn pop-up); QC mở HD.08.01 trong 2 lần bấm; người không phải Ban ISO không thấy tab Tất cả / Ban hành;
// đề nghị gửi phải lưu rồi mới ký gửi; Giám đốc không thấy nút duyệt đề nghị của chính mình; ban hành lưu đợt
// trước khi bấm; nạp bộ khớp tệp theo tên, bỏ qua tệp đã có.
// Nạp code THẬT (view + qcui + dom); modal / toast / xác nhận giả — scripts/fakedom.mjs.
//
// Chạy: node scripts/test-tailieu.mjs   (verify.sh gọi sẵn)

import {
  E, MO, TOAST, XAC, cho, ketThuc, kiem, napView, tim,
} from './fakedom.mjs';

const V = await napView('views/tailieu.js');
const nutCo = (goc, chu) => tim(goc, (e) => e.tagName === 'BUTTON' && e.textContent.includes(chu))[0];
const link = (goc, chu) => tim(goc, (e) => e.tagName === 'A' && e.textContent.includes(chu))[0];
const moCuoi = () => MO[MO.length - 1];
globalThis.window.location = { hash: '#/tailieu' };
globalThis.window.prompt = () => 'lập nhầm';

const tl = (o) => ({ name: 'TL-1', ma: 'HD.08.01', ten: 'Hướng dẫn thực hiện Vòng kiểm QC', loai: 'Hướng dẫn', nguon: 'Nội bộ',
  trang_thai: 'Hiện hành', nhom_thu_muc: 'QT.08 Quản lý sản xuất', lan_ban_hanh: '01', ngay_hieu_luc: '2026-09-22',
  co_tep: true, phan_phoi: ['QC'], ma_bieu_mau: [], man_app: '', ...o });
const DS = {
  ds: [tl(), tl({ name: 'TL-2', ma: 'BM.08.01', ten: 'Vòng kiểm QC + phiếu sự cố', loai: 'Biểu mẫu',
    ma_bieu_mau: [{ ma: 'BM.08.01', man_app: '#/qc' }, { ma: 'BM.08.02', man_app: '#/qc/incidents' }], man_app: '#/qc' }),
  tl({ name: 'TL-3', ma: 'CS.ATTP', ten: 'Chính sách ATTP', nhom_thu_muc: 'Sổ tay, chính sách, mục tiêu', loai: 'Chính sách' }),
  tl({ name: 'TL-4', ma: 'PLK', ten: 'Phiếu theo dõi sản lượng', loai: 'Biểu mẫu trên phần mềm', co_tep: false,
    man_app: '#/ghiso', nhom_thu_muc: 'QT.08 Quản lý sản xuất' })],
  can_doc: [{ name: 'D1', tai_lieu: 'TL-1', ma: 'HD.08.01', ten: 'Hướng dẫn thực hiện Vòng kiểm QC', lan_ban_hanh: '02',
    dot_ban_hanh: 'DBH-2026-01', mo_luc: '', ngay: '2026-10-09', co_tep: true }],
  cua_toi: ['QC', 'Toàn bộ người lao động'], la_iso: false, duoc_de_nghi: true, duoc_nap: false,
  noi_nhan: [], loai: ['Hướng dẫn', 'Biểu mẫu', 'Khác'], user: 'qc@x', hom_nay: '2026-10-09',
};
const GOI = [];
let traVe = {};
const api = (dl) => ({
  container: new E('div'),
  call: async (m, a) => {
    GOI.push([m, a]);
    const k = m.split('.').pop();
    if (k in traVe) return typeof traVe[k] === 'function' ? traVe[k](a) : traVe[k];
    if (k === 'ds') return dl;
    return {};
  },
});
const goi = (k) => GOI.filter(([m]) => m.endsWith(`.${k}`));

console.log('\n-- Của tôi: Cần đọc, mở tệp rồi mới xác nhận --');
V.st.quyen = null;
const a1 = api(DS);
await V.render(a1);
const c = a1.container;
const tabs = tim(c, (e) => e.tagName === 'A' && e.classList.contains('sx-qc-tab')).map((e) => e.textContent);
kiem('QC: tab Của tôi, Đề nghị — không Tất cả, không Ban hành', JSON.stringify(tabs) === '["Của tôi","Đề nghị"]', tabs);
const canDoc = tim(c, (e) => e.classList.contains('sx-tl-cando'))[0];
const than = c.kids[0].kids[1];
kiem('Cần đọc trên cùng (trước ô tìm, danh sách): HD.08.01 lần 02, đợt', than.kids[0] === canDoc
  && canDoc.chu.includes('HD.08.01 — Hướng dẫn') && canDoc.chu.includes('Lần BH 02') && canDoc.chu.includes('DBH-2026-01'));
const daDoc = nutCo(canDoc, 'ĐÃ ĐỌC, HIỂU');
kiem('chưa mở tệp: ĐÃ ĐỌC, HIỂU tắt, có lời nhắc mở trước', daDoc.disabled && canDoc.chu.includes('Mở tài liệu ra đọc trước'));
const moDoc = link(canDoc, 'MỞ ĐỌC');
kiem('nút mở là thẻ <a> trỏ thẳng tai_tep, mở tab mới (không bị chặn pop-up)', moDoc
  && moDoc.href === '/api/method/sx.api.qc_tailieu.tai_tep?name=TL-1' && moDoc.target === '_blank', moDoc && moDoc.href);
moDoc.bam();
kiem('… bấm: gọi mo (ghi giờ mở) — nút vẫn tắt tới khi server trả', goi('mo').length === 1
  && goi('mo')[0][1].name === 'TL-1' && daDoc.disabled);
await cho();
kiem('… server đã ghi giờ mở → bật ĐÃ ĐỌC, HIỂU', !daDoc.disabled);
daDoc.bam();
await cho();
kiem('bấm ĐÃ ĐỌC, HIỂU → da_doc đúng tài liệu', goi('da_doc').length === 1 && goi('da_doc')[0][1].name === 'TL-1'
  && TOAST.some(([s]) => s === 'Đã xác nhận đọc'));

console.log('\n-- Của tôi: nhóm, tìm, mở, sang màn ghi --');
const c2 = a1.container;
kiem('nhóm theo thư mục, đếm', c2.chu.includes('QT.08 Quản lý sản xuất') && c2.chu.includes('Sổ tay, chính sách, mục tiêu'));
const the = (goc, ma) => tim(goc, (e) => e.classList.contains('sx-tl-the') && e.chu.includes(ma))[0];
const hd = the(c2, 'HD.08.01 Hướng dẫn');
kiem('QC mở HD.08.01 trong 2 lần bấm: tab Tài liệu → nút 📄 MỞ ngay trên thẻ', !!link(hd, 'MỞ')
  && link(hd, 'MỞ').href.endsWith('tai_tep?name=TL-1'));
const bm = the(c2, 'BM.08.01');
kiem('biểu mẫu có màn app → ✍ GHI TRÊN APP sang #/qc', link(bm, 'GHI TRÊN APP').href === '#/qc');
const plk = the(c2, 'PLK');
kiem('biểu mẫu trên phần mềm (không PDF): không nút mở, có sang màn #/ghiso', !link(plk, 'MỞ')
  && link(plk, 'GHI TRÊN APP').href === '#/ghiso' && plk.chu.includes('trên phần mềm'));
const timO = tim(c2, (e) => e.tagName === 'INPUT' && e.classList.contains('sx-tl-tim'))[0];
timO.doi('bm.08.02');
kiem('tìm theo mã biểu mẫu kèm (BM.08.02 → tài liệu BM.08.01)', the(c2, 'BM.08.01') && !the(c2, 'HD.08.01 Hướng dẫn')
  && !the(c2, 'CS.ATTP'));
timO.doi('');
kiem('lọc (hàm thuần): theo mã / tên, không phân biệt hoa thường', V.locDs(DS.ds, 'chính sách').length === 1
  && V.locDs(DS.ds, '').length === 4);

console.log('\n-- Ban ISO: Tất cả, in danh mục --');
V.st.quyen = null;
V.st.q = '';
globalThis.window.location = { hash: '#/tailieu/tatca' };
const DSI = { ...DS, la_iso: true, duoc_nap: true, can_doc: [], noi_nhan: [{ ten: 'QC' }, { ten: 'Ban ISO' }],
  ds: [...DS.ds, tl({ name: 'TL-9', ma: 'BM.06.05', ten: 'Sổ bảo dưỡng', trang_thai: 'Hết hiệu lực' }),
    tl({ name: 'TL-8', ma: 'QCVN 01-1:2024/BYT', ten: 'Nước sạch', nguon: 'Bên ngoài', nhom_thu_muc: 'B. QUY CHUẨN',
      so_hieu_co_quan: 'QCVN 01-1:2024/BYT; Bộ Y tế', co_tep: false })] };
const a2 = api(DSI);
await V.render(a2);
const c3 = a2.container;
const tabs2 = tim(c3, (e) => e.tagName === 'A' && e.classList.contains('sx-qc-tab')).map((e) => e.textContent);
kiem('Ban ISO: 4 tab; Tất cả đang sáng', JSON.stringify(tabs2) === '["Của tôi","Tất cả","Đề nghị","Ban hành"]'
  && tim(c3, (e) => e.classList.contains('sx-qc-seg-on') && e.tagName === 'A')[0].textContent === 'Tất cả', tabs2);
kiem('gọi ds với tat_ca=1; mặc định Hiện hành + Nội bộ', goi('ds').pop()[1].tat_ca === 1 && !the(c3, 'BM.06.05')
  && !the(c3, 'QCVN'));
nutCo(c3, 'BM.01.02').bam();
await cho();
kiem('🖨 BM.01.02 → in_bm0102', goi('in_bm0102').length === 1);
const segTT = tim(c3, (e) => e.tagName === 'BUTTON' && e.textContent === 'Hết hiệu lực')[0];
segTT.bam();
await cho();
kiem('lọc Hết hiệu lực → thấy BM.06.05 (mờ)', !!the(a2.container, 'BM.06.05')
  && the(a2.container, 'BM.06.05').classList.contains('sx-tl-het'));
V.st.tt = 'Hiện hành';
V.st.nguon = 'Bên ngoài';
await V.render(a2);
kiem('Bên ngoài: số hiệu, nút ĐÃ SOÁT XÉT CẢ DANH MỤC', !!the(a2.container, 'QCVN')
  && !!nutCo(a2.container, 'ĐÃ SOÁT XÉT'));
nutCo(a2.container, 'ĐÃ SOÁT XÉT').bam();
await XAC[XAC.length - 1].onConfirm();
kiem('… xác nhận 2 bước → soat_xet', goi('soat_xet').length === 1);
V.st.nguon = 'Nội bộ';

console.log('\n-- Đề nghị BM.01.01 --');
globalThis.window.location = { hash: '#/tailieu/denghi' };
V.st.quyen = { la_iso: false, duoc_de_nghi: true };
const DN = { ds: [], tai_lieu: [{ name: 'TL-1', ma: 'HD.08.01', ten: 'Hướng dẫn', lan_ban_hanh: '01' }],
  loai_yc: ['Soạn mới', 'Sửa đổi', 'Hủy bỏ', 'Áp dụng tài liệu bên ngoài'], la_iso: false, la_gd: false, duoc_lap: true,
  user: 'qc@x' };
traVe = { de_nghi_ds: DN, de_nghi_luu: { name: 'DNTL-2026-001' } };
const a3 = api(DS);
await V.render(a3);
nutCo(a3.container, 'LẬP ĐỀ NGHỊ').bam();
const m = moCuoi();
const sel = tim(m.body, (e) => e.tagName === 'SELECT')[0];
sel.value = 'TL-1';
tim(m.body, (e) => e.tagName === 'TEXTAREA')[0].doi('Bỏ đo độ ẩm');
nutCo(m.body, 'KÝ GỬI').bam();
await cho();
await cho();
const p = JSON.parse(goi('de_nghi_luu').pop()[1].payload);
kiem('ký gửi: lưu trước (loại Sửa đổi, tài liệu, lý do) rồi mới gửi', p.loai_yeu_cau === 'Sửa đổi' && p.tai_lieu === 'TL-1'
  && p.ly_do === 'Bỏ đo độ ẩm' && goi('de_nghi_gui').length === 1 && goi('de_nghi_gui')[0][1].name === 'DNTL-2026-001'
  && GOI.findIndex(([k]) => k.endsWith('de_nghi_luu')) < GOI.findIndex(([k]) => k.endsWith('de_nghi_gui')), p);
const dnX = { name: 'DNTL-2026-002', loai_yeu_cau: 'Sửa đổi', ten_de_xuat: 'HD.08.01', trang_thai: 'Chờ duyệt',
  nguoi_de_nghi: 'gd@x', owner: 'gd@x', ho_ten_de_nghi: 'Giám Đốc', ngay_de_nghi: '2026-10-09', nhat_ky: '[…] gửi' };
traVe = { de_nghi_ds: { ...DN, ds: [dnX], la_iso: true, la_gd: true, user: 'gd@x' } };
await V.render(a3);
tim(a3.container, (e) => e.classList.contains('sx-qc-sc') && e.chu.includes('HD.08.01'))[0].bam();
kiem('Giám đốc không thấy nút DUYỆT đề nghị của chính mình', !nutCo(moCuoi().body, 'DUYỆT'));
traVe = { de_nghi_ds: { ...DN, ds: [{ ...dnX, nguoi_de_nghi: 'qc@x', owner: 'qc@x' }], la_iso: true, la_gd: true, user: 'gd@x' } };
await V.render(a3);
tim(a3.container, (e) => e.classList.contains('sx-qc-sc') && e.chu.includes('HD.08.01'))[0].bam();
const mDuyet = moCuoi();
kiem('… đề nghị của người khác, Chờ duyệt: có DUYỆT, TRẢ LẠI; khóa nội dung', !!nutCo(mDuyet.body, 'DUYỆT')
  && !!nutCo(mDuyet.body, 'TRẢ LẠI') && tim(mDuyet.body, (e) => e.tagName === 'TEXTAREA')[0].disabled);
nutCo(mDuyet.body, 'DUYỆT').bam();
await cho();
kiem('DUYỆT → de_nghi_duyet đồng ý', goi('de_nghi_duyet').pop()[1].dong_y === 1);

console.log('\n-- Đợt ban hành --');
globalThis.window.location = { hash: '#/tailieu/dot/DBH-2026-01' };
V.st.quyen = { la_iso: true, duoc_de_nghi: true, duoc_nap: true };
const DOT = { name: 'DBH-2026-01', so_quyet_dinh: '', ngay_ban_hanh: '2026-10-09', ngay_hieu_luc: '2026-10-12',
  trang_thai: 'Nháp', co_qd: false, tao_yeu_cau_doc: 1, ghi_chu: '', ban_hanh_ten: '', ban_hanh_luc: '',
  ds: [{ row: 'r1', tai_lieu: 'TL-1', ma: 'HD.08.01', ten: 'Hướng dẫn', hanh_dong: 'Sửa đổi – thay thế',
    lan_ban_hanh_moi: '02', lan_hien: '01', co_tep: false, de_nghi: 'DNTL-2026-001', tom_tat: 'Bỏ đo độ ẩm' }],
  ho_so: [], tien_do: { tong: 0, da: 0, nguoi: 0, nguoi_xong: 0, chua_doc: [] },
  thieu: ['Chưa ghi số quyết định.', 'HD.08.01: thiếu PDF bản mới đã ký.'] };
traVe = { dot_xem: DOT, dot_ds: { ds: [], de_nghi_cho: [{ name: 'DNTL-2026-009' }], noi_nhan: ['QC'], tai_lieu: [],
  hanh_dong: ['Ban hành mới', 'Sửa đổi – thay thế', 'Hủy bỏ', 'Giữ nguyên'], loai: ['Khác'] },
ban_hanh: { so_tai_lieu: 1, yeu_cau_doc: 5 } };
const a4 = api(DS);
await V.render(a4);
const c4 = a4.container;
kiem('đợt nháp: dòng HD.08.01 lần 01 → 02, đề nghị, chưa PDF; lý do chưa ban hành được nói rõ',
  c4.chu.includes('lần 01 → 02') && c4.chu.includes('DNTL-2026-001') && c4.chu.includes('HD.08.01: thiếu PDF')
  && !!nutCo(c4, 'TẢI PDF ĐÃ KÝ') && !!nutCo(c4, 'KÉO ĐỀ NGHỊ ĐÃ DUYỆT (1)'));
tim(c4, (e) => e.tagName === 'INPUT' && e.type === '')[0].doi('15/QĐ-HG');
nutCo(c4, 'BAN HÀNH').bam();
await XAC[XAC.length - 1].onConfirm();
const lu = JSON.parse(goi('dot_luu').pop()[1].payload);
kiem('BAN HÀNH (xác nhận 2 bước): lưu đợt (số QĐ, dòng giữ row) rồi ban_hanh', lu.so_quyet_dinh === '15/QĐ-HG'
  && lu.ds[0].row === 'r1' && goi('ban_hanh').length === 1
  && GOI.map(([k]) => k).lastIndexOf('sx.api.qc_tailieu.dot_luu') < GOI.map(([k]) => k).lastIndexOf('sx.api.qc_tailieu.ban_hanh'), lu);
traVe.dot_xem = { ...DOT, trang_thai: 'Đã ban hành', thieu: [], ban_hanh_ten: 'Nguyễn Huy Chiến', ban_hanh_luc: '2026-10-09 10:00',
  tien_do: { tong: 6, da: 2, nguoi: 6, nguoi_xong: 2, chua_doc: [{ ho_ten: 'Lê QC Gói', vai: 'QC đóng gói', chua: ['HD.08.01'] }] } };
await V.render(a4);
kiem('đã ban hành: không sửa; tiến độ đọc 2/6, người chưa đọc; in BM.01.13; vẫn thêm hồ sơ', !nutCo(a4.container, 'BAN HÀNH')
  && a4.container.chu.includes('Tiến độ đọc: 2/6') && a4.container.chu.includes('Lê QC Gói')
  && !!nutCo(a4.container, 'IN BM.01.13') && !!nutCo(a4.container, 'THÊM HỒ SƠ'));

console.log('\n-- Nạp bộ tài liệu --');
kiem('nhận ra tệp seed theo nội dung', V.loaiSeed([{ stt: 1 }]) === 'tai_lieu' && V.loaiSeed({ soat_xet: '', ds: [] }) === 'ngoai'
  && V.loaiSeed({ ds: [{ noi_nhan: 'QC' }] }) === 'phan_phoi' && V.loaiSeed({ ds: [] }) === null);
globalThis.window.location = { hash: '#/tailieu/nap' };
traVe = { nap_bo: { tao: { tai_lieu: 81, ngoai: 21, noi_nhan: 10, phan_phoi: 102, dot: 1, ho_so: 1, yeu_cau_doc: 0 },
  can_tep: [{ khoa: 'tl:TL-1', tep: 'HD.08.01.pdf', co: false }, { khoa: 'tl:TL-2', tep: 'BM.08.01.pdf', co: true },
    { khoa: 'tl:TL-3', tep: 'CS.pdf', co: false }], loi: [] } };
globalThis.FileReader = class { readAsDataURL(f) { this.result = `data:application/pdf;base64,${f.b64}`; this.onload(); } };
const a5 = api(DS);
await V.render(a5);
const c5 = a5.container;
const [inJ, inF] = tim(c5, (e) => e.tagName === 'INPUT');
inJ.files = [{ name: 'seed_tai_lieu.json', text: async () => '[{"stt":1}]' },
  { name: 'seed_phan_phoi.json', text: async () => '{"ds":[{"noi_nhan":"QC"}]}' }];
inJ.doi('');
await cho();
await cho();
nutCo(c5, 'NẠP DANH MỤC').bam();
await cho();
const pn = JSON.parse(goi('nap_bo').pop()[1].payload);
kiem('NẠP DANH MỤC: gửi seed theo loại, mặc định không tạo yêu cầu đọc (đợt 21/9 đã phổ biến giấy)',
  pn.tai_lieu.length === 1 && pn.phan_phoi.ds[0].noi_nhan === 'QC' && pn.tao_yeu_cau_doc === 0
  && c5.chu.includes('81 tài liệu nội bộ') && c5.chu.includes('1/3 đã có'), pn);
inF.files = [{ name: 'HD.08.01.pdf', size: 1000, b64: 'JVBERg==' }, { name: 'BM.08.01.pdf', size: 1000, b64: 'JVBERg==' },
  { name: 'la.pdf', size: 1000, b64: 'JVBERg==' }];
nutCo(c5, 'TẢI TỆP').bam();
await cho();
await cho();
await cho();
const tai = goi('nap_tep');
kiem('TẢI TỆP: chỉ tệp khớp tên và chưa có (HD.08.01), đúng khoá, nội dung base64; nói còn tệp chưa chọn',
  tai.length === 1 && tai[0][1].khoa === 'tl:TL-1' && tai[0][1].ten === 'HD.08.01.pdf' && tai[0][1].noi_dung === 'JVBERg=='
  && c5.chu.includes('Còn 1 tệp chưa chọn: CS.pdf'), tai);

console.log('\n-- bản scan bản gốc đã ký (D176) --');
kiem('nên có bản scan: tài liệu nội bộ hiện hành; không: dự thảo, bên ngoài, biểu mẫu chỉ có trên phần mềm',
  V.canScan(tl()) && !V.canScan(tl({ trang_thai: 'Dự thảo' })) && !V.canScan(tl({ nguon: 'Bên ngoài' }))
  && !V.canScan(tl({ loai: 'Biểu mẫu trên phần mềm' })));
const DS_ISO = { ...DS, la_iso: true, can_doc: [], ds: [tl({ co_scan: true }), tl({ name: 'TL-5', ma: 'QT.08', ten: 'Quy trình SX' }),
  tl({ name: 'TL-4', ma: 'PLK', ten: 'Phiếu theo dõi sản lượng', loai: 'Biểu mẫu trên phần mềm', co_tep: false })] };
globalThis.window.location = { hash: '#/tailieu/tatca' };
V.st.quyen = null;
V.st.tt = 'Hiện hành';
V.st.nguon = 'Nội bộ';
V.st.scan = '';
const a6 = api(DS_ISO);
await V.render(a6);
let c6 = a6.container;
const the6 = tim(c6, (e) => e.classList.contains('sx-tl-the'));
kiem('Tất cả (Ban ISO): đếm bản scan đã có / cần có (biểu mẫu phần mềm không tính)',
  c6.chu.includes('Bản scan bản gốc đã ký: 1 / 2'), c6.chu.slice(0, 300));
kiem('… thẻ có scan: chip "có bản scan" + nút mở bản scan (GET tai_tep?scan=1); thiếu: chip "chưa có bản scan"',
  the6[0].chu.includes('có bản scan') && link(the6[0], 'BẢN SCAN').href === '/api/method/sx.api.qc_tailieu.tai_tep?name=TL-1&scan=1'
  && link(the6[0], 'BẢN SCAN').target === '_blank' && the6[1].chu.includes('chưa có bản scan') && !link(the6[1], 'BẢN SCAN')
  && !the6[2].chu.includes('chưa có bản scan'));
tim(c6, (e) => e.tagName === 'BUTTON' && e.textContent === 'Chưa có bản scan')[0].bam();
await cho();
c6 = a6.container;
const con = tim(c6, (e) => e.classList.contains('sx-tl-the')).map((e) => tim(e, (k) => k.classList.contains('sx-tl-ma'))
  .map((k) => k.textContent).join() || e.chu);
kiem('lọc "Chưa có bản scan" → chỉ tài liệu còn thiếu (đi scan cho đủ)', V.st.scan === 'thieu'
  && con.length === 1 && con[0].includes('QT.08'), con);
V.st.scan = '';
const mo = { close() { mo.dong = true; } };
const XEM = tl({ co_scan: true, scan_luc: '2026-10-10 09:05', scan_boi: 'Nguyễn Huy Chiến' });
let sc = V.veScan({ ...api(DS_ISO), lai: () => {} }, XEM, { la_iso: true }, mo);
kiem('chi tiết (Ban ISO, có scan): MỞ BẢN SCAN, người + giờ gắn, THAY / BỎ bản scan; nhận PDF / ảnh',
  link(sc, 'MỞ BẢN SCAN').href.endsWith('tai_tep?name=TL-1&scan=1') && sc.chu.includes('Gắn 10/10/2026 09:05 · Nguyễn Huy Chiến')
  && !!nutCo(sc, 'THAY BẢN SCAN') && !!nutCo(sc, 'BỎ BẢN SCAN')
  && tim(sc, (e) => e.tagName === 'INPUT')[0].accept === '.pdf,.jpg,.jpeg,.png');
nutCo(sc, 'BỎ BẢN SCAN').bam();
const x6 = XAC[XAC.length - 1];
await x6.onConfirm();
kiem('BỎ BẢN SCAN hỏi xác nhận rồi gọi scan_bo, đóng chi tiết', x6.title.includes('HD.08.01') && goi('scan_bo').pop()[1].name === 'TL-1'
  && mo.dong);
sc = V.veScan(api(DS_ISO), tl(), { la_iso: true }, mo);
kiem('chi tiết (Ban ISO, chưa có): "Chưa có bản scan" + GẮN BẢN SCAN', sc.chu.includes('Chưa có bản scan')
  && !!nutCo(sc, 'GẮN BẢN SCAN') && !nutCo(sc, 'BỎ BẢN SCAN'));
sc = V.veScan(api(DS), XEM, { la_iso: false }, mo);
kiem('người thường: chỉ MỞ BẢN SCAN — không gắn / thay / bỏ, không thấy ai gắn', !!link(sc, 'MỞ BẢN SCAN')
  && !nutCo(sc, 'BẢN SCAN') && !sc.chu.includes('Nguyễn Huy Chiến'));
sc = V.veScan(api(DS_ISO), tl({ trang_thai: 'Hết hiệu lực' }), { la_iso: true }, mo);
kiem('tài liệu Hết hiệu lực: không gắn bản scan mới', !nutCo(sc, 'GẮN BẢN SCAN'));

ketThuc('TAILIEU-JS');
