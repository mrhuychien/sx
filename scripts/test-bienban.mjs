// Màn Biên bản #/qc/bienban, #/tailieu/bienban (W45, D174) — views/qc_bienban.js.
//
// Vì sao phải có bài này: phiếu SINH TỪ MẪU — câu in sẵn phải hiện là câu hỏi (không ô sửa), kết luận ≤ 3 lựa chọn là
// nút, dòng Không phù hợp có nút LẬP BM.01.07 (hoặc link phiếu đã lập); LƯU gửi đúng nội dung theo phần; người được
// ký thấy KÝ / TRẢ LẠI (trả lại bắt ghi ý kiến); "Chờ tôi ký" dẫn sang đúng biên bản trong màn đang đứng.
// Nạp code THẬT (view + qcui + dom); modal / toast giả — scripts/fakedom.mjs.
//
// Chạy: node scripts/test-bienban.mjs   (verify.sh gọi sẵn)

import { E, MO, TOAST, cho, dangChon, ketThuc, kiem, napView, tim } from './fakedom.mjs';

const V = await napView('views/qc_bienban.js');
const nutCo = (goc, chu) => tim(goc, (e) => e.tagName === 'BUTTON' && e.textContent.includes(chu))[0];
const moCuoi = () => MO[MO.length - 1];
globalThis.window.location = { hash: '#/qc/bienban' };

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

console.log('\n-- đường dẫn theo nơi đang đứng --');
kiem('trong QC → #/qc/bienban; trong Tài liệu → #/tailieu/bienban', (() => {
  const a = V.goc();
  globalThis.window.location = { hash: '#/tailieu/bienban/BB-1' };
  const b = V.goc();
  globalThis.window.location = { hash: '#/qc/bienban' };
  return a === '#/qc/bienban' && b === '#/tailieu/bienban';
})());

console.log('\n-- danh sách: chờ tôi ký, lập, lọc --');
traVe = {
  ds: {
    cho_toi: [{ name: 'BB-2026-0001', mau: 'BM.01.11', so: '01/BB-ISO', ten_mau: 'Biên bản họp Ban ISO',
      ngay: '2026-10-09', vai_tro: 'Trưởng Ban ISO (chủ trì)' }],
    mau: [{ ma: 'BM.01.11', ten: 'Biên bản họp Ban ISO', chu_ky_lap: 'Tuần', lap: true, so: 2, cho_ky: 1, nhap: 1,
      lan_cuoi: '2026-10-09' },
    { ma: 'BM.01.10', ten: 'Biên bản xem xét của lãnh đạo', chu_ky_lap: 'Năm', lap: false, so: 0 }],
    ds: [{ name: 'BB-2026-0001', mau: 'BM.01.11', so: '01/BB-ISO', ngay: '2026-10-09', tieu_de: 'Họp tuần 41',
      trang_thai: 'Chờ ký', cho: 'Trưởng Ban ISO (chủ trì)', toi_ky: true, nguoi_lap: 'Đào Quang Công' },
    { name: 'BB-2026-0002', mau: 'BM.01.11', so: '02/BB-ISO', ngay: '2026-10-16', tieu_de: 'Họp tuần 42',
      trang_thai: 'Nháp', nguoi_lap: 'Đào Quang Công' }],
  },
};
let a = api();
await V.veDanhSach(a);
let c = a.container;
kiem('Chờ tôi ký: thẻ dẫn sang #/qc/bienban/<tên>, ghi ô phải ký',
  tim(c, (e) => e.tagName === 'A' && e.href === '#/qc/bienban/BB-2026-0001').length === 2
  && c.chu.includes('Chờ tôi ký') && c.chu.includes('Ô Trưởng Ban ISO (chủ trì)'));
kiem('nút lập chỉ cho mẫu được lập (BM.01.11), không cho BM.01.10',
  !!nutCo(c, '+ BM.01.11') && !nutCo(c, '+ BM.01.10'));
nutCo(c, 'Nháp').bam();
kiem('lọc trạng thái Nháp: chỉ còn số 02', c.chu.includes('02/BB-ISO') && !c.chu.includes('Họp tuần 41'));
nutCo(c, 'Tất cả').bam();

console.log('\n-- lập: ô đầu phiếu, gốc bắt buộc với checklist đánh giá nội bộ --');
traVe.mau_lap = { ma: 'BM.01.06', ten: 'Check list đánh giá', nhan_ngay: 'Ngày', goc_mau: 'BM.01.05', can_goc: true,
  goc: [{ name: 'BB-KH', so: '01/2026', ngay: '2026-10-10', tieu_de: 'ĐGNB 2026', bo_phan: ['Cơ điện'] }],
  dau: [{ key: 'bo_phan', nhan: 'Bộ phận được đánh giá', kieu: 'Data', bat_buoc: 1, lua_chon: [] }], hom_nay: '2026-10-09' };
traVe.lap = { name: 'BB-2026-0009', so: '01/2026' };
a = api();
traVe.ds.mau.push({ ma: 'BM.01.06', ten: 'Check list đánh giá', chu_ky_lap: 'Khi phát sinh', lap: true, so: 0 });
await V.veDanhSach(a);
nutCo(a.container, '+ BM.01.06').bam();
await cho();
let m = moCuoi();
nutCo(m.body, 'LẬP').bam();
await cho();
kiem('chưa chọn kế hoạch → không gọi lập', goi('lap').length === 0 && TOAST.some(([s]) => s.includes('BM.01.05')));
const chonGoc = tim(m.body, (e) => e.tagName === 'SELECT')[0];
chonGoc.doi('BB-KH');
kiem('chọn kế hoạch → hiện bộ phận được phân, điền sẵn', m.body.chu.includes('Bộ phận kế hoạch phân cho bạn: Cơ điện'));
nutCo(m.body, 'LẬP').bam();
await cho();
const gl = JSON.parse(goi('lap')[0][1].payload);
kiem('lập: gửi mẫu, gốc, ngày, ô đầu phiếu; chuyển sang biên bản mới',
  gl.mau === 'BM.01.06' && gl.goc === 'BB-KH' && gl.ngay === '2026-10-09' && gl.dau.bo_phan === 'Cơ điện'
  && globalThis.window.location.hash === '#/qc/bienban/BB-2026-0009', gl);
globalThis.window.location = { hash: '#/qc/bienban' };

console.log('\n-- phiếu Nháp: câu in sẵn, nút kết luận, thêm dòng, LƯU --');
const PHAN = [
  { key: 'dau', tieu_de: '', kieu: 'Văn bản', cot: [{ key: 'gio', nhan: 'Thời gian (giờ)', kieu: 'Data', lua_chon: [] }],
    cot_tinh: [] },
  { key: 'su_co', tieu_de: 'Phiếu sự cố trong tuần', kieu: 'Kéo dữ liệu', nguon: 'su_co_ky', cot: [], cot_tinh: [] },
  { key: 'checklist', tieu_de: 'Check list', kieu: 'Danh sách kiểm', ket_luan: 'ket_luan', them_dong: 1, cot_tinh: [],
    cot: [{ key: 'yeu_cau', nhan: 'Yêu cầu', kieu: 'Text', hoi: 1, bat_buoc: 1, lua_chon: [] },
      { key: 'ket_luan', nhan: 'Kết luận', kieu: 'Select', bat_buoc: 1, lua_chon: ['PH', 'KPH', 'Lưu ý'] },
      { key: 'bang_chung', nhan: 'Bằng chứng', kieu: 'Text', lua_chon: [] }] },
  { key: 'viec_giao', tieu_de: '3. Việc giao', kieu: 'Việc giao', cot_tinh: [],
    cot: [{ key: 'viec', nhan: 'Việc', kieu: 'Text', bat_buoc: 1, lua_chon: [] },
      { key: 'phu_trach', nhan: 'Người thực hiện', kieu: 'User', bat_buoc: 1, lua_chon: [] },
      { key: 'han', nhan: 'Hạn', kieu: 'Date', bat_buoc: 1, lua_chon: [] }] },
];
const PHIEU = (q, them = {}) => ({
  name: 'BB-2026-0009', mau: 'BM.01.06', ten_mau: 'Check list đánh giá', so: '01/2026', ngay: '2026-10-09',
  tieu_de: 'ĐGNB Cơ điện', trang_thai: q.sua ? 'Nháp' : 'Chờ ký', ten_nguoi_lap: 'Đào Quang Công', nhan_ngay: 'Ngày',
  hom_nay: '2026-10-09', user: 'qc@x', nguoi_lap: 'qc@x', phan: PHAN, ap_dung: {}, quyen: q, kph: [],
  dong_ap_dung: { checklist: ['m1', 'm2'] }, lien_quan: [], viec: [], tep_kem: [],
  noi_dung: {
    dau: { gia_tri: { gio: '8:30' } },
    su_co: { keo: { luc: '2026-10-09 10:00', tu: '2026-10-03', den: '2026-10-09', ghi_chu: '1 phiếu',
      cot: [{ key: 'phieu', nhan: 'Phiếu' }], dong: [{ phieu: 'SC-1' }] } },
    checklist: { dong: [{ _id: 'm1', _co_dinh: 1, yeu_cau: 'Hiệu chuẩn đồng hồ nhiệt' },
      { _id: 'm2', _co_dinh: 1, yeu_cau: 'Sổ bảo dưỡng', ket_luan: 'KPH' }] },
    viec_giao: { dong: [] },
  },
  ky: [{ vai_tro: 'Chuyên gia đánh giá', ten: '', ky_luc: '', cho: !q.sua, ky_tay: 0 }],
  ...them,
});
traVe = { xem: PHIEU({ sua: true, gui: true }), nguoi: [{ v: 'cd@x', nhan: 'Ngô Văn Trường' }], luu: {}, gui: {} };
a = api();
await V.vePhieu(a, 'BB-2026-0009');
c = a.container;
kiem('kéo dữ liệu: bảng bản chụp + giờ kéo, có KÉO LẠI khi Nháp', c.chu.includes('SC-1')
  && c.chu.includes('Số liệu app lúc 09/10/2026 10:00') && !!nutCo(c, 'KÉO LẠI'));
kiem('câu in sẵn hiện là câu hỏi (không ô sửa câu), kết luận là 3 nút',
  c.chu.includes('1. Hiệu chuẩn đồng hồ nhiệt')
  && tim(c, (e) => e.tagName === 'TEXTAREA' && e.value === 'Hiệu chuẩn đồng hồ nhiệt').length === 0
  && tim(c, (e) => e.tagName === 'BUTTON' && e.textContent === 'Lưu ý').length === 2);
kiem('dòng KPH khi Nháp: báo lưu, gửi xong mới lập BM.01.07 (chưa có nút)', !nutCo(c, 'LẬP BM.01.07')
  && c.chu.includes('lập BM.01.07 từ dòng này'));
tim(c, (e) => e.tagName === 'BUTTON' && e.textContent === 'PH')[0].bam();
nutCo(c, '+ CÂU HỎI').bam();
const moi = tim(c, (e) => e.tagName === 'TEXTAREA' && e.value === '');
moi[moi.length - 2].doi('Nam châm NC-01');
nutCo(c, '+ DÒNG').bam();
tim(c, (e) => e.tagName === 'TEXTAREA' && e.value === '').slice(-1)[0].doi('Hiệu chỉnh M2');
nutCo(c, 'LƯU').bam();
await cho();
const nd = JSON.parse(goi('luu').slice(-1)[0][1].payload).noi_dung;
kiem('LƯU gửi nội dung theo phần: kết luận PH dòng 1, câu hỏi thêm, việc giao thêm; câu in sẵn giữ id',
  nd.checklist.dong[0].ket_luan === 'PH' && nd.checklist.dong[0]._id === 'm1'
  && nd.checklist.dong[2].yeu_cau === 'Nam châm NC-01' && nd.viec_giao.dong[0].viec === 'Hiệu chỉnh M2', nd);
nutCo(c, 'GỬI KÝ').bam();
await cho();
await cho();
kiem('GỬI KÝ: lưu rồi gửi', goi('gui').length === 1);

console.log('\n-- chờ ký: KÝ, TRẢ LẠI (bắt ý kiến), BM.01.07 --');
traVe = { xem: PHIEU({ sua: false, ky: true, tra_lai: true, car: true }), ky: {}, tra_lai: {}, lap_car: { name: 'CAR-1' } };
a = api();
await V.vePhieu(a, 'BB-2026-0009');
c = a.container;
kiem('không còn ô sửa / nút LƯU; có KÝ, TRẢ LẠI; ô ký đang chờ', !nutCo(c, 'LƯU') && !!nutCo(c, 'KÝ')
  && !!nutCo(c, 'TRẢ LẠI') && c.chu.includes('đang chờ ký'));
nutCo(c, 'TRẢ LẠI').bam();
m = moCuoi();
nutCo(m.body, 'XÁC NHẬN').bam();
await cho();
kiem('trả lại không ý kiến → không gọi', goi('tra_lai').length === 0);
tim(m.body, (e) => e.tagName === 'TEXTAREA')[0].doi('Ghi rõ bằng chứng');
nutCo(m.body, 'XÁC NHẬN').bam();
await cho();
kiem('trả lại gửi ý kiến', goi('tra_lai')[0][1].y_kien === 'Ghi rõ bằng chứng');
nutCo(c, 'KÝ').bam();
nutCo(moCuoi().body, 'XÁC NHẬN').bam();
await cho();
kiem('ký gửi tên biên bản', goi('ky')[0][1].name === 'BB-2026-0009');
nutCo(c, 'LẬP BM.01.07').bam();
await cho();
kiem('LẬP BM.01.07 gửi phần + id dòng KPH', goi('lap_car')[0][1].phan === 'checklist' && goi('lap_car')[0][1].dong === 'm2');
traVe.xem = PHIEU({ sua: false, car: true }, { kph: [{ phan: 'checklist', dong: 'm2', car: 'CAR-1' }] });
a = api();
await V.vePhieu(a, 'BB-2026-0009');
kiem('dòng đã có BM.01.07 → link phiếu, không nút lập lại', !nutCo(a.container, 'LẬP BM.01.07')
  && a.container.chu.includes('BM.01.07 CAR-1'));
kiem('dangChon dùng được (segment kết luận đọc lại)', typeof dangChon === 'function');

ketThuc('BIENBAN-JS');
