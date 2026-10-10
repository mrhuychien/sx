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

console.log('\n-- Nạp bộ tài liệu (D180: danh mục đi kèm app, chọn thẳng tệp .zip) --');
// FileReader giả: tệp giả có b64; tệp thật (File / Blob) → base64 của đúng nội dung.
globalThis.FileReader = class {
  readAsDataURL(f) {
    if (f.b64 !== undefined) { this.result = `data:application/pdf;base64,${f.b64}`; this.onload(); return; }
    f.arrayBuffer().then((b) => { this.result = `data:;base64,${Buffer.from(b).toString('base64')}`; this.onload(); });
  }
};
const choDen = async (dk, n = 400) => { for (let i = 0; i < n && !dk(); i += 1) await cho(); };
// tệp .zip THẬT: thư mục + PDF nén deflate + PDF lưu thẳng + tệp không cần
const { execFileSync } = await import('node:child_process');
const { mkdtempSync, readFileSync: docF } = await import('node:fs');
const { tmpdir } = await import('node:os');
const TAM = [];
const tamDir = (t) => { const d = mkdtempSync(`${tmpdir()}/${t}`); TAM.push(d); return d; };
const zipTep = `${tamDir('sx-zip-')}/tai_lieu_pdf.zip`;
const ND = { 'HD.08.01.pdf': `%PDF-1.4 HD.08.01 ${'nội dung '.repeat(80)}`, 'CS.pdf': '%PDF-1.4 CS', 'la.pdf': '%PDF-1.4 la',
  'BM.08.01.pdf': '%PDF-1.4 BM.08.01' };
execFileSync('python3', ['-c', `import sys, zipfile
z = zipfile.ZipFile(sys.argv[1], 'w')
z.writestr('tai_lieu_pdf/', '')
z.writestr(zipfile.ZipInfo('tai_lieu_pdf/HD.08.01.pdf'), sys.argv[2].encode(), zipfile.ZIP_DEFLATED)
z.writestr(zipfile.ZipInfo('tai_lieu_pdf/CS.pdf'), sys.argv[3].encode(), zipfile.ZIP_STORED)
z.writestr('tai_lieu_pdf/la.pdf', sys.argv[4].encode())
z.writestr('tai_lieu_pdf/BM.08.01.pdf', sys.argv[5].encode())
z.writestr(zipfile.ZipInfo('tai_lieu_pdf/QT.99.pdf'), b'%PDF' + b'a' * (11 * 1024 * 1024), zipfile.ZIP_DEFLATED)
z.close()`, zipTep, ND['HD.08.01.pdf'], ND['CS.pdf'], ND['la.pdf'], ND['BM.08.01.pdf']]);
const fZip = new File([docF(zipTep)], 'tai_lieu_pdf.zip');
const b64 = (t) => Buffer.from(t).toString('base64');
const ds = await V.gomTep([fZip]);
kiem('đọc .zip trên máy: bỏ thư mục, khớp theo tên không đường dẫn, giải nén đúng nội dung (deflate + lưu thẳng)',
  JSON.stringify(Object.keys(ds).sort()) === '["BM.08.01.pdf","CS.pdf","HD.08.01.pdf","QT.99.pdf","la.pdf"]'
  && Buffer.from(await (await ds['HD.08.01.pdf'].lay()).arrayBuffer()).toString() === ND['HD.08.01.pdf']
  && Buffer.from(await (await ds['CS.pdf'].lay()).arrayBuffer()).toString() === ND['CS.pdf']
  && ds['HD.08.01.pdf'].co === Buffer.byteLength(ND['HD.08.01.pdf']), Object.keys(ds));
let loiZip = '';
try { await V.gomTep([new File(['không phải zip'], 'hong.zip')]); } catch (e) { loiZip = e.message; }
kiem('tệp đuôi .zip mà không phải zip → báo rõ', loiZip.includes('không phải tệp .zip'), loiZip);

// zip khó (D182): tên có dấu (UTF-8), tên theo bảng mã Windows (không cờ UTF-8), tệp rác máy Mac, ZIP64, dữ liệu chèn trước
const zipKho = (ten, ma) => {
  const p2 = `${tamDir('sx-zip-')}/${ten}`;
  execFileSync('python3', ['-c', ma, p2]);
  return new File([docF(p2)], ten);
};
const fWin = zipKho('win.zip', `import sys, zipfile, unicodedata
z = zipfile.ZipFile(sys.argv[1], 'w')
z.writestr('Quy triXnh QT.99.pdf', b'%PDF win')
z.writestr(unicodedata.normalize('NFD', 'Tài liệu/Hướng dẫn HD.08.01.pdf'), b'%PDF utf8')   # tên kiểu máy Mac (NFD)
z.writestr('__MACOSX/Tài liệu/._Hướng dẫn HD.08.01.pdf', b'rac')
z.writestr('Tài liệu/.DS_Store', b'rac')
z.close()
import unicodedata
b = open(sys.argv[1], 'rb').read().replace(b'triXnh', unicodedata.normalize('NFD', 'trình').encode('cp1258'))
open(sys.argv[1], 'wb').write(b)`);
const gWin = await V.gomTep([fWin]);
kiem('zip Windows: tên không cờ UTF-8 đọc theo bảng mã tiếng Việt; tên UTF-8 có dấu; bỏ __MACOSX/, .DS_Store',
  JSON.stringify(Object.keys(gWin).sort()) === JSON.stringify(['Hướng dẫn HD.08.01.pdf', 'Quy trình QT.99.pdf'])
  && Buffer.from(await (await gWin['Quy trình QT.99.pdf'].lay()).arrayBuffer()).toString() === '%PDF win',
  Object.keys(gWin));
const f64 = zipKho('z64.zip', `import sys, zipfile, struct
zipfile.ZIP64_LIMIT = 1                     # buộc ghi ZIP64: cỡ, vị trí ở trường phụ 0x0001
z = zipfile.ZipFile(sys.argv[1], 'w', allowZip64=True)
z.writestr(zipfile.ZipInfo('a/CS.pdf'), b'%PDF cs ' * 50, zipfile.ZIP_DEFLATED)
z.writestr('a/HD.08.01.pdf', b'%PDF hd')
z.close()
b = bytearray(open(sys.argv[1], 'rb').read())
i = b.rfind(b'PK\\x05\\x06')
b[i + 10:i + 12] = b'\\xff\\xff'; b[i + 16:i + 20] = b'\\xff\\xff\\xff\\xff'   # khối cuối thường "bão hoà" → phải đọc ZIP64
open(sys.argv[1], 'wb').write(bytes(b))`);
const g64 = await V.gomTep([f64]);
kiem('zip ZIP64 (khối cuối ZIP64, cỡ / vị trí tệp ở trường phụ) đọc đúng',
  JSON.stringify(Object.keys(g64).sort()) === '["CS.pdf","HD.08.01.pdf"]'
  && Buffer.from(await (await g64['CS.pdf'].lay()).arrayBuffer()).toString() === '%PDF cs '.repeat(50)
  && Buffer.from(await (await g64['HD.08.01.pdf'].lay()).arrayBuffer()).toString() === '%PDF hd', Object.keys(g64));
const fTruoc = new File([Buffer.concat([Buffer.from('MZ dữ liệu chèn trước '.repeat(10)), docF(zipTep)])], 'sfx.zip');
const gTruoc = await V.gomTep([fTruoc]);
kiem('zip có dữ liệu chèn trước (tự giải nén / zip ghép) → vẫn đọc đúng vị trí',
  Object.keys(gTruoc).length === 5
  && Buffer.from(await (await gTruoc['HD.08.01.pdf'].lay()).arrayBuffer()).toString() === ND['HD.08.01.pdf']);

// bộ khớp tệp (D182) với danh mục THẬT (sx/qc/seed/tai_lieu.json, 88 tệp)
const { writeFileSync: ghiF, rmSync: xoaF } = await import('node:fs');
const tamG = `${tamDir('sx-ghep-')}/ghep.mjs`;
ghiF(tamG, docF('sx/public/sx/lib/ghep.js', 'utf8'));
const G = await import(`file://${tamG}`);
xoaF(tamG);
const SEED = JSON.parse(docF('sx/qc/seed/tai_lieu.json', 'utf8'));
const CAN88 = SEED.map((x) => ({ khoa: `${{ tai_lieu: 'tl', anh: 'kem', dot: 'qd', ho_so_dot: 'hsdot', ho_so: 'hs' }[x.kieu_nap]}:${x.stt}`,
  tep: x.tep, co: false, ma: x.kieu_nap === 'tai_lieu' ? (x.ma_chuan || '').trim() : '', ten: x.ten }));
const maCua = (k) => (CAN88.find((x) => x.khoa === k) || {}).ma;
const tenCua = (k) => (CAN88.find((x) => x.khoa === k) || {}).ten || '';
const g88 = G.ghepTep(CAN88, SEED.map((x) => x.tep));
const g88k = G.ghepTep(CAN88, SEED.map((x, i) => x.tep.replace(/\.(pdf|png)$/, i % 2 ? '_signed.$1' : ' (đã ký số).$1')));
kiem('khớp: 88 tệp đúng tên sổ đăng ký → 88 "khớp tên"; thêm đuôi _signed / (đã ký số) của phần mềm ký số → vẫn 88',
  g88.dong.every((d, i) => d.cach === 'ten' && d.khoa) && new Set(g88.dong.map((d) => d.khoa)).size === 88
  && g88k.dong.every((d) => d.cach === 'ten') && new Set(g88k.dong.map((d) => d.khoa)).size === 88);
const TU_DAT = {
  'QT.01 - Quản lý chung hệ thống ATTP (đã ký).pdf': ['ma', 'QT.01'],
  'BM.01.01 Phiếu yêu cầu sửa đổi tài liệu.pdf': ['ten', 'BM.01.01'],
  'Sổ tay an toàn thực phẩm.pdf': ['ten', 'ST.ATTP'],
  'KH.HACCP.01-PL So do qua trinh banh dau xanh.pdf': ['ma', 'KH.HACCP.01-PL'],
  'KH.HACCP.01 Ke hoach HACCP banh dau xanh_signed.pdf': ['ma', 'KH.HACCP.01'],
  'PRP Hệ thống quy phạm vệ sinh.pdf': ['ma', 'PRP'],
  'BM.PRP.04 Danh mục hóa chất.pdf': ['ma', 'BM.PRP.04'],
  'QT 8 quy trinh quan ly san xuat.pdf': ['ma', 'QT.08'],
  'qt-02_thu_hoi.pdf': ['ma', 'QT.02'],
  'KH.CĐS.01 Kế hoạch chuyển đổi số.pdf': ['ma', 'KH.CĐS.01'],
  'SĐ.02 Sơ đồ thiết bị loại trừ vật lạ.pdf': ['ma', 'SĐ.02'],
  'TTr-01 To trinh may do kim loai.pdf': ['ma', 'TTr-01'],
  'BM.08.01 + BM.08.02 Vong kiem QC.pdf': ['ma', 'BM.08.01'],
  'QT.01 ban 2.pdf': ['trung', undefined],
  'QT.01.02 Lạ.pdf': ['', undefined],
  'Bien ban hop giao ban thang 9.pdf': ['', undefined],
  'So do.pdf': ['', undefined],
  'Ke hoach.pdf': ['', undefined],
  'Rework.pdf': ['', undefined],
  'Tai lieu khac.docx': ['', undefined],
};
const gTu = G.ghepTep(CAN88, [...Object.keys(TU_DAT), 'So do to chuc (ky so).pdf', 'SĐ.02 ảnh sơ đồ.png',
  'Quyết định ban hành sửa đổi tài liệu hệ thống ATTP.pdf']);
const saiTu = gTu.dong.filter((d) => TU_DAT[d.ten] && (d.cach !== TU_DAT[d.ten][0] || maCua(d.khoa) !== TU_DAT[d.ten][1]));
const goiY = (t) => gTu.dong.find((d) => d.ten === t);
kiem('khớp tên tự đặt: mã trong tên (QT.01, "QT 8", "qt-02", KH.CĐS.01, SĐ.02, TTr-01, BM.PRP.04 chứ không PRP, '
  + 'KH.HACCP.01-PL chứ không KH.HACCP.01); trùng tài liệu → "trùng"; mã lạ / ảnh không chắc / .docx → để chọn tay',
  !saiTu.length, saiTu.map((d) => `${d.ten} → ${d.cach} ${maCua(d.khoa)}`));
kiem('gợi ý khi mọi từ của tên tệp có trong tên một tài liệu (Sơ đồ tổ chức, QĐ ban hành, ảnh sơ đồ SĐ.02) — đánh dấu '
  + '"gần đúng"; "Biên bản họp giao ban tháng 9" KHÔNG gợi ý sang "Biên bản họp Ban ISO" (giao ban, tháng 9 không có)',
  goiY('So do to chuc (ky so).pdf').cach === 'gan' && tenCua(goiY('So do to chuc (ky so).pdf').khoa).startsWith('Sơ đồ tổ chức')
  && goiY('SĐ.02 ảnh sơ đồ.png').cach === 'gan'
  && (CAN88.find((x) => x.khoa === goiY('SĐ.02 ảnh sơ đồ.png').khoa) || {}).tep === 'SD.02_so_do_thiet_bi_loai_tru_vat_la.png'
  && goiY('Quyết định ban hành sửa đổi tài liệu hệ thống ATTP.pdf').cach === 'gan'
  && goiY('Quyết định ban hành sửa đổi tài liệu hệ thống ATTP.pdf').khoa.startsWith('qd:'));
const CAN88b = CAN88.map((x) => ({ ...x, co: x.ma === 'QT.01' }));
const gCo = G.ghepTep(CAN88b, ['QT.01 Quản lý chung (đã ký).pdf', 'QT_01_Quan_ly_chung_he_thong_an_toan_thuc_pham.pdf']);
kiem('tệp của tài liệu đã có trên app (theo mã hoặc đúng tên) → "đã có", không tải lại', gCo.dong.every((d) => d.cach === 'da_co' && !d.khoa)
  && gCo.thieu.length === 87);
kiem('đuôi "đã ký" chỉ bỏ ở cuối; Đ → d; mã một từ chỉ tính ở đầu tên; số ngay sau mã thì không khớp',
  JSON.stringify(G.boDuoiKy(G.tu('Ke hoach dinh ky (da ky so)_signed'))) === '["ke","hoach","dinh"]'
  && JSON.stringify(G.tu('SĐ.02 Đồ_KH.CĐS.01')) === '["sd","2","do","kh","cds","1"]'
  && G.viTriMa(G.tu('BM.PRP.04 Danh muc'), G.tu('PRP')) === -1 && G.viTriMa(G.tu('PRP Danh muc'), G.tu('PRP')) === 0
  && G.viTriMa(G.tu('Danh muc PRP ve sinh'), G.tu('PRP')) === -1 && G.viTriMa(G.tu('So SLM'), G.tu('SLM')) === -1
  && G.viTriMa(G.tu('Quy trinh QT.08 lan 2'), G.tu('QT.08')) === 2 && G.viTriMa(G.tu('QT.08.01 x'), G.tu('QT.08')) === -1);

const CHUA = { tai_lieu: [0, 81], ngoai: [0, 21], noi_nhan: [0, 10], dot: false, ngay: '2026-09-21', can_tep: [],
  tong_tep: 5, danh_muc_xong: false, xong: false };
const CAN = [
  { khoa: 'tl:TL-1', tep: 'HD.08.01.pdf', co: false, ma: 'HD.08.01', ten: 'Hướng dẫn thực hiện Vòng kiểm QC' },
  { khoa: 'tl:TL-2', tep: 'BM.08.01.pdf', co: true, ma: 'BM.08.01', ten: 'Vòng kiểm QC' },
  { khoa: 'tl:TL-3', tep: 'CS.pdf', co: false, ma: 'CS.ATTP', ten: 'Chính sách an toàn thực phẩm' },
  { khoa: 'tl:TL-9', tep: 'QT.99.pdf', co: false, ma: 'QT.99', ten: 'Quy trình thử' },
  { khoa: 'kem:TL-7', tep: 'SD.03_so_do.png', co: false, ma: '', ten: 'Sơ đồ trạm bẫy – ảnh' }];
const DA = { tai_lieu: [81, 81], ngoai: [21, 21], noi_nhan: [10, 10], dot: true, ngay: '2026-09-21', can_tep: CAN,
  tong_tep: 5, danh_muc_xong: true, xong: false };
let tinh = CHUA;
traVe = { tinh_trang_nap: () => tinh, nap_bo: () => { tinh = DA; return { tao: {}, can_tep: CAN, loi: [] }; },
  nap_tep: (a) => { const x = CAN.find((y) => y.khoa === a.khoa); if (x) x.co = true; return {}; } };
globalThis.window.location = { hash: '#/tailieu/nap' };
V.st.quyen = { la_iso: true, duoc_de_nghi: true, duoc_nap: true, nap_xong: false };
const a5 = api(DS);
await V.render(a5);
let c5 = a5.container;
const inp5 = () => tim(c5, (e) => e.tagName === 'INPUT' && e.type === 'file');
kiem('mở màn là thấy đã nạp tới đâu (0/81 …, 0/5 tệp — chưa nạp danh mục vẫn biết cả bộ bao nhiêu tệp); một nút '
  + 'NẠP DANH MỤC — không còn ô chọn tệp .json',
  c5.chu.includes('0/81 tài liệu nội bộ') && c5.chu.includes('0/10 nơi nhận') && !!nutCo(c5, 'NẠP DANH MỤC')
  && c5.chu.includes('0/5 tệp đã có') && inp5().length === 1 && inp5()[0].accept === '.zip,.pdf,.png'
  && inp5()[0].multiple === true && !c5.chu.includes('.json'), c5.chu.slice(0, 300));
let moChon = 0;
inp5()[0].click = () => { moChon += 1; };
const chon5 = () => nutCo(c5, 'CHỌN TỆP ZIP / PDF');
const phu = !!chon5() && chon5().className.includes('sx-btn-ghost') && !chon5().className.includes('sx-btn-primary');
chon5().bam();
kiem('nút CHỌN TỆP của app (ô chọn tệp trình duyệt ẩn đi) — bấm là mở hộp chọn; chưa nạp danh mục thì là nút phụ',
  inp5()[0].style.display === 'none' && moChon === 1 && phu, chon5() && chon5().className);
nutCo(c5, 'NẠP DANH MỤC').bam();
await choDen(() => c5.chu.includes('81/81'));
const pn = JSON.parse(goi('nap_bo').pop()[1].payload);
kiem('NẠP DANH MỤC: không gửi tệp nào (danh mục đi kèm app), mặc định không tạo yêu cầu đọc; màn tự cập nhật; còn '
  + 'thiếu ghi theo mã + tên tài liệu (tệp người dùng tự đặt tên)',
  !pn.tai_lieu && pn.tao_yeu_cau_doc === 0 && c5.chu.includes('✓ Danh mục') && !nutCo(c5, 'NẠP DANH MỤC')
  && c5.chu.includes('1/5 tệp đã có') && c5.chu.includes('Còn thiếu 4 tệp: HD.08.01 · Hướng dẫn thực hiện Vòng kiểm '
    + 'QC; CS.ATTP · Chính sách an toàn thực phẩm; QT.99 · Quy trình thử; Ảnh · Sơ đồ trạm bẫy – ảnh')
  && chon5().className.includes('sx-btn-primary'), c5.chu.slice(-260));
// 1. tai_lieu_pdf.zip có một tệp lạ (la.pdf): khớp tên phần lớn, tệp lạ → bảng xem lại trước khi tải
inp5()[0].files = [fZip];
inp5()[0].doi('');
await choDen(() => !!nutCo(c5, 'TỆP LÊN'));
const sel5 = () => tim(c5, (e) => e.tagName === 'SELECT');
kiem('có tệp không khớp đúng tên → CHƯA tải gì, hiện bảng xem lại: đếm từng loại, tệp lạ "chưa khớp" để trống, nút '
  + 'TẢI 3 TỆP (tệp đã có trên app không tải lại)',
  !goi('nap_tep').length && c5.chu.includes('Đã đọc 5 tệp PDF, PNG: 3 khớp tên · 0 theo mã tài liệu · 0 gần đúng · '
    + '1 chưa khớp · 1 đã có trên app') && !!nutCo(c5, 'TẢI 3 TỆP LÊN')
  && sel5().some((s) => s.textContent.includes('Không tải tệp này')) && c5.chu.includes('📄 la.pdf'),
  c5.chu.slice(-400));
nutCo(c5, 'TẢI 3 TỆP LÊN').bam();
await choDen(() => c5.chu.includes('Đã tải'));
const tai = goi('nap_tep');
const tai1 = (k) => (tai.find((x) => x[1].khoa === k) || [])[1] || {};
kiem('TẢI LÊN: đúng tệp còn thiếu (BM.08.01 đã có, tệp lạ bỏ qua), đúng khoá, đúng nội dung đã giải nén',
  tai.length === 2 && tai1('tl:TL-1').noi_dung === b64(ND['HD.08.01.pdf'])
  && tai1('tl:TL-3').noi_dung === b64(ND['CS.pdf']) && c5.chu.includes('Đã tải 2/3 tệp'),
  tai.map((x) => x[1].ten));
kiem('tệp trong zip quá 10 MB (sau giải nén) → không gửi, báo đúng tên', !tai.some((x) => x[1].ten === 'QT.99.pdf')
  && c5.chu.includes('QT.99.pdf: quá 10 MB'), c5.chu.slice(-200));
// 2. bản ĐÃ KÝ SỐ, tên tự đặt (D182): khớp theo mã, gần đúng, chọn tay; một tài liệu chỉ nhận một tệp
CAN.forEach((x) => { x.co = x.khoa === 'tl:TL-2'; });
GOI.length = 0;
const ND2 = { hd: '%PDF HD đã ký', cs: '%PDF CS đã ký', qt: '%PDF QT đã ký', png: '\x89PNG tram bay' };
const fKy = zipKho('ban_ky_so.zip', `import sys, zipfile
z = zipfile.ZipFile(sys.argv[1], 'w', zipfile.ZIP_DEFLATED)
z.writestr('Tài liệu đã ký/HD.08.01 Hướng dẫn vòng kiểm QC (đã ký).pdf', ${JSON.stringify(ND2.hd)}.encode())
z.writestr('Tài liệu đã ký/Chinh sach ATTP_signed.pdf', ${JSON.stringify(ND2.cs)}.encode())
z.writestr('Tài liệu đã ký/QT.99 Quy trinh thu.pdf', ${JSON.stringify(ND2.qt)}.encode())
z.writestr('Tài liệu đã ký/BM.08.01 Vong kiem QC.pdf', b'%PDF da co')
z.writestr('Tài liệu đã ký/So do tram bay.png', ${JSON.stringify(ND2.png)}.encode('latin-1'))
z.writestr('Tài liệu đã ký/Ghi chu.docx', b'PK docx')
z.writestr('__MACOSX/Tài liệu đã ký/._QT.99 Quy trinh thu.pdf', b'rac')
z.close()`);
await V.render(a5);
c5 = a5.container;
inp5()[0].files = [fKy];
inp5()[0].doi('');
await choDen(() => !!nutCo(c5, 'TỆP LÊN'));
const dongCua = (ten) => tim(c5, (e) => e.tagName === 'DIV' && e.className.includes('sx-tl-ghep')
  && e.kids.some((k) => (k.textContent || '').includes(ten)))[0];
const selCua = (ten) => tim(dongCua(ten), (e) => e.tagName === 'SELECT')[0];
kiem('bản đã ký, tên tự đặt: mã trong tên (HD.08.01, QT.99) → đúng tài liệu; ảnh tên gần giống → gợi ý; tên lạ → chờ chọn '
  + 'tay; tệp của tài liệu đã có, tệp .docx, tệp rác máy Mac → bỏ qua; chưa tải gì',
  !goi('nap_tep').length && c5.chu.includes('Đã đọc 5 tệp PDF, PNG: 0 khớp tên · 2 theo mã tài liệu · 1 gần đúng · '
    + '1 chưa khớp · 1 đã có trên app · bỏ qua 1 tệp không phải PDF, PNG')
  && selCua('HD.08.01 Hướng dẫn vòng kiểm QC (đã ký).pdf').value === 'tl:TL-1'
  && selCua('QT.99 Quy trinh thu.pdf').value === 'tl:TL-9' && selCua('So do tram bay.png').value === 'kem:TL-7'
  && selCua('Chinh sach ATTP_signed.pdf').value === '' && !c5.chu.includes('._QT.99')
  && !selCua('So do tram bay.png').innerHTML.includes('tl:TL-1') && !!nutCo(c5, 'TẢI 3 TỆP LÊN'), c5.chu.slice(-500));
selCua('QT.99 Quy trinh thu.pdf').doi('tl:TL-3');
const tranh = selCua('QT.99 Quy trinh thu.pdf').value === 'tl:TL-3';
selCua('Chinh sach ATTP_signed.pdf').doi('tl:TL-3');
kiem('chọn tay: một tài liệu chỉ một tệp — chọn trùng thì tệp kia thôi nhận; nút đếm lại số tệp sẽ tải',
  tranh && selCua('Chinh sach ATTP_signed.pdf').value === 'tl:TL-3' && selCua('QT.99 Quy trinh thu.pdf').value === ''
  && c5.chu.includes('chọn tay') && !!nutCo(c5, 'TẢI 3 TỆP LÊN'));
selCua('QT.99 Quy trinh thu.pdf').doi('tl:TL-9');
nutCo(c5, 'TẢI 4 TỆP LÊN').bam();
await choDen(() => c5.chu.includes('Đã tải'));
const tai2 = goi('nap_tep').map((x) => x[1]);
const theo = (k) => tai2.find((x) => x.khoa === k) || {};
kiem('TẢI 4 TỆP: mỗi tệp vào đúng tài liệu, gửi dưới tên trong sổ đăng ký (server kiểm tên), nội dung là bản đã ký',
  tai2.length === 4 && theo('tl:TL-1').ten === 'HD.08.01.pdf' && theo('tl:TL-1').noi_dung === b64(ND2.hd)
  && theo('tl:TL-3').ten === 'CS.pdf' && theo('tl:TL-3').noi_dung === b64(ND2.cs)
  && theo('tl:TL-9').ten === 'QT.99.pdf' && theo('tl:TL-9').noi_dung === b64(ND2.qt)
  && theo('kem:TL-7').ten === 'SD.03_so_do.png'
  && theo('kem:TL-7').noi_dung === Buffer.from(ND2.png, 'latin1').toString('base64')
  && c5.chu.includes('Đã tải 4/4 tệp') && !nutCo(c5, 'TỆP LÊN'), tai2.map((x) => `${x.khoa} ${x.ten}`));
// 3. CHỌN TỆP KHÁC: bỏ bảng xem lại, không tải gì
CAN.forEach((x) => { x.co = x.khoa === 'tl:TL-2'; });
GOI.length = 0;
await V.render(a5);
c5 = a5.container;
inp5()[0].files = [fKy];
inp5()[0].doi('');
await choDen(() => !!nutCo(c5, 'CHỌN TỆP KHÁC'));
nutCo(c5, 'CHỌN TỆP KHÁC').bam();
await choDen(() => !!chon5());
kiem('CHỌN TỆP KHÁC: bỏ bảng xem lại, về nút chọn tệp, không tải gì', !goi('nap_tep').length && !nutCo(c5, 'TỆP LÊN')
  && !!chon5());
// 4. chỉ có tệp không phải PDF / PNG → báo rõ, không tải
inp5()[0].files = [new File(['x'], 'Ke hoach.docx')];
inp5()[0].doi('');
await choDen(() => c5.chu.includes('Không có tệp PDF, PNG'));
kiem('chọn toàn tệp không phải PDF, PNG → báo rõ, không gửi gì', !goi('nap_tep').length
  && c5.chu.includes('⚠ Không có tệp PDF, PNG nào trong 1 tệp đã chọn'));
// 5. tệp .zip hỏng → báo lỗi ngay trên màn (không chỉ thông báo chớp qua)
inp5()[0].files = [new File(['không phải zip'], 'hong.zip')];
inp5()[0].doi('');
await choDen(() => c5.chu.includes('không phải tệp .zip'));
kiem('zip hỏng → dòng báo lỗi nằm lại trên màn', c5.chu.includes('⚠ hong.zip không phải tệp .zip'));
tinh = { ...DA, can_tep: CAN, xong: true };
await V.render(a5);
c5 = a5.container;
kiem('nạp đủ: màn báo xong, không còn nút / ô chọn tệp; nút NẠP BỘ ở Ban hành ẩn đi',
  c5.chu.includes('✓ Đã nạp đủ bộ tài liệu') && !inp5().length && V.st.quyen.nap_xong === true, c5.chu.slice(0, 200));
// chọn tệp ngay khi chưa nạp danh mục → app nạp danh mục trước rồi tải; chọn thẳng PDF đúng tên → tải luôn, không hỏi
CAN.forEach((x) => { x.co = x.khoa === 'tl:TL-2'; });
tinh = CHUA;
GOI.length = 0;
const a7 = api(DS);
await V.render(a7);
const c7 = a7.container;
const in7 = tim(c7, (e) => e.tagName === 'INPUT' && e.type === 'file')[0];
in7.files = [new File([ND['CS.pdf']], 'CS.pdf')];
in7.doi('');
await choDen(() => goi('nap_tep').length >= 1);
kiem('chọn tệp khi CHƯA nạp danh mục: app tự nạp danh mục trước (một thao tác), rồi tải luôn tệp khớp đúng tên',
  goi('nap_bo').length === 1 && goi('nap_tep').length === 1 && goi('nap_tep')[0][1].khoa === 'tl:TL-3'
  && GOI.findIndex(([m]) => m.endsWith('.nap_bo')) < GOI.findIndex(([m]) => m.endsWith('.nap_tep')), GOI.map((x) => x[0]));
// nút vào màn Nạp bộ: có khi chưa xong, ẩn khi đã xong
traVe = { dot_ds: { ds: [], de_nghi_cho: [] } };
globalThis.window.location = { hash: '#/tailieu/banhanh' };
V.st.quyen = { la_iso: true, duoc_de_nghi: true, duoc_nap: true, nap_xong: false };
const a8 = api(DS);
await V.render(a8);
const coNut = !!link(a8.container, 'NẠP BỘ TÀI LIỆU');
V.st.quyen.nap_xong = true;
const a9 = api(DS);
await V.render(a9);
kiem('Ban hành: nút NẠP BỘ TÀI LIỆU hiện khi chưa nạp đủ, ẩn khi đã nạp đủ', coNut && !link(a9.container, 'NẠP BỘ TÀI LIỆU'));
traVe = {};
TAM.forEach((d) => xoaF(d, { recursive: true, force: true }));

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
