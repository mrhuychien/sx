// Màn "Sổ giặt vải ủ" (D163 — W29): views/qc_vaiu.js.
//
// Vì sao phải có bài này: màn điện thoại là chỗ QC ghi hộ người giặt — giặt định kỳ phải chọn sẵn TOÀN BỘ vải
// đang dùng (HD.08.02 mục 6), số phút đun phải hiện đỏ ngay khi chưa đủ 10 phút (trước khi bấm ký), loại vải
// không gửi giờ đun, nhập vải mới gửi mã gõ tay; dòng đã ký không còn nút lưu; Trưởng Ban ISO có nút "Đã xem
// tháng", QC thì không. Nạp code THẬT (view + qcui + dom); modal / toast giả — scripts/fakedom.mjs.
//
// Chạy: node scripts/test-vaiu.mjs   (verify.sh gọi sẵn)

import {
  E, MO, TOAST, XAC, bang, cho, dangChon, ketThuc, kiem, napView, nut, tim,
} from './fakedom.mjs';

const V = await napView('views/qc_vaiu.js');

console.log('\n-- số phút đun sôi (như sx/qc/vai_u.so_phut) --');
kiem('07:00 → 07:12 = 12; vớt qua nửa đêm 23:55 → 00:07 = 12', V.soPhut('07:00', '07:12') === 12
  && V.soPhut('23:55', '00:07') === 12);
kiem('thiếu một đầu / giờ sai → null', V.soPhut('07:00', '') === null && V.soPhut('', '07:00') === null
  && V.soPhut('25:00', '07:00') === null);
const lop = (c) => (c ? c.className : null);
kiem('chip đun: 8′ đỏ, 12′ xanh; giặt chưa ghi giờ → "chưa ghi giờ đun"; loại vải không giờ → không chip',
  lop(V.chipDun({ viec: 'Giặt định kỳ', gio_soi_lai: '07:00', gio_vot: '07:08' }, 10)) === 'sx-qc-tag sx-qc-tag-cao'
  && lop(V.chipDun({ viec: 'Giặt định kỳ', gio_soi_lai: '07:00', gio_vot: '07:12' }, 10)) === 'sx-qc-tag sx-qc-tag-dong'
  && lop(V.chipDun({ viec: 'Giặt định kỳ', gio_soi_lai: '07:00', gio_vot: '07:10' }, 10)) === 'sx-qc-tag sx-qc-tag-dong'
  && V.chipDun({ viec: 'Giặt ngoài lịch' }, 10).textContent === 'chưa ghi giờ đun'
  && V.chipDun({ viec: 'Loại vải' }, 10) === null);

const VAI = [
  { ma: 'V01-A', thung: '01', trang_thai: 'Đang dùng', ngay_nhap: '', ngay_loai: '', ly_do_loai: '', ghi_chu: '' },
  { ma: 'V01-B', thung: '01', trang_thai: 'Dự phòng', ngay_nhap: '2026-09-01', ngay_loai: '', ly_do_loai: '', ghi_chu: '' },
  { ma: 'V02-A', thung: '02', trang_thai: 'Đang dùng', ngay_nhap: '', ngay_loai: '', ly_do_loai: '', ghi_chu: '' },
  { ma: 'V02-B', thung: '02', trang_thai: 'Đã loại', ngay_nhap: '', ngay_loai: '2026-10-05', ly_do_loai: 'Rách mép',
    dong_loai: 'GVU-2026-00007', ghi_chu: '' }];
const dong = (them) => ({
  name: 'GVU-2026-00010', ngay: '2026-10-08', viec: 'Giặt định kỳ', vai: ['V01-A', 'V02-A'], so_luong: 0, ly_do: '',
  gio_soi_lai: '07:00', gio_vot: '07:12', so_phut: 12, phoi_tai: 'Giá mái che', cat_luc: '2026-10-08 15:30',
  nguoi_lam: 'Chị Lan', ghi_boi: 'qc@x', su_co: null, qc_ky_boi: 'qc@x', qc_ky_luc: '2026-10-08 16:00', ten_ky: 'QC Hà',
  xem_boi: null, xem_luc: '', xem_nhan_xet: '', creation: '2026-10-08', ten_xem: '', ...them,
});
const duLieu = (them = {}) => ({
  thang: '2026-10', hom_nay: '2026-10-09', vai: VAI, lan_cuoi: '2026-10-01', chu_ky: 7,
  cai_dat: { thu_giat: 'Thứ Hai', noi_giat: 'Nhà giặt sau xưởng', nguoi_giat: 'Chị Lan', giat_moi_lan: 0 },
  phoi_tai: 'Giá mái che', xem: null, chua_xem: 2, chua_ky: 1,
  ds: [dong({ name: 'GVU-2026-00011', ngay: '2026-10-09', viec: 'Giặt ngoài lịch', vai: ['V01-A'], ly_do: 'Vải ẩm',
    gio_vot: '07:08', so_phut: 8, qc_ky_boi: null, qc_ky_luc: '', creation: '2026-10-09' }), dong()],
  su_co: [{ name: 'SC-0007', ngay: '2026-10-05', mo_ta: 'Vải rách thiếu mảnh' }],
  viec: ['Giặt định kỳ', 'Giặt ngoài lịch', 'Nhập vải mới', 'Loại vải'], phut_soi: 10,
  duoc_ghi: true, duoc_khai_vai: false, duoc_xem_thang: false, la_iso: false, user: 'qc@x', ...them,
});
const GOI = [];
let traVe = duLieu();
const api = {
  container: new E('div'),
  call: async (m, a) => {
    GOI.push([m, a]);
    if (m.endsWith('tong_quan')) return traVe;
    if (m.endsWith('.ghi')) return { name: 'GVU-2026-00012', so_phut: 12, da_ky: true, vai_moi: [], chua_ky_duoc: null };
    return {};
  },
};
const goi = (ten) => GOI.filter(([m]) => m === `sx.api.qc_vaiu.${ten}`);
const nutCo = (goc, chu) => tim(goc, (e) => e.tagName === 'BUTTON' && e.textContent.includes(chu))[0];
const moCuoi = () => MO[MO.length - 1];
const oChu = (m, nhan) => {
  // ô nhập ngay sau dòng nhãn `nhan` (oNhap: nhãn rồi tới ô)
  const ds = [];
  const di = (e) => e.kids.forEach((k) => { ds.push(k); di(k); });
  di(m.body);
  const i = ds.findIndex((k) => k.textContent === nhan);
  return ds.slice(i + 1).find((k) => ['INPUT', 'TEXTAREA', 'SELECT'].includes(k.tagName));
};
const payload = () => JSON.parse(goi('ghi').at(-1)[1].payload);

console.log('\n-- màn Sổ giặt --');
await V.render(api);
const c = api.container;
kiem('đầu màn: BM.08.05 · tháng 10/2026; hai tab, tab Danh mục đếm vải chưa loại (3)',
  c.chu.includes('BM.08.05 · tháng 10/2026') && c.chu.includes('Danh mục vải (3)') && c.chu.includes('Sổ giặt'));
kiem('giặt định kỳ gần nhất 01/10/2026 · 8 ngày trước → cảnh báo quá 7 ngày', c.chu.includes('01/10/2026')
  && c.chu.includes('8 ngày trước') && c.chu.includes('Quá 7 ngày chưa giặt'));
kiem('chu kỳ, ngày giặt cố định, nơi giặt; số vải đang dùng / dự phòng', c.chu.includes('ngày giặt Thứ Hai')
  && c.chu.includes('giặt tại Nhà giặt sau xưởng') && c.chu.includes('2 vải đang dùng · 1 dự phòng'));
kiem('QC: nút ghi giặt định kỳ + 3 việc khác; chưa có nút "Đã xem tháng"', !!nut(c, 'GHI GIẶT ĐỊNH KỲ')
  && !!nutCo(c, 'Giặt ngoài lịch') && !!nutCo(c, 'Nhập vải mới') && !!nutCo(c, 'Loại vải') && !nutCo(c, 'ĐÃ XEM THÁNG'));
kiem('thẻ dòng: đun 8′ (đỏ), CHỜ QC KÝ; dòng đã ký: đun 12′, QC đã ký', c.chu.includes('đun 8′')
  && c.chu.includes('CHỜ QC KÝ') && c.chu.includes('đun 12′') && c.chu.includes('QC đã ký'));
kiem('nút in BM.08.05 của tháng', !!nutCo(c, 'IN BM.08.05 — tháng 10/2026'));

console.log('\n-- ghi giặt định kỳ --');
nut(c, 'GHI GIẶT ĐỊNH KỲ').bam();
let m = moCuoi();
kiem('form mới: tiêu đề "Giặt định kỳ", việc đang chọn đúng nút vừa bấm', m.title === 'Giặt định kỳ'
  && dangChon(tim(m.body, (e) => e.classList.contains('sx-qc-seg'))[0]) === 'Giặt định kỳ');
const chon = () => tim(m.body, (e) => e.tagName === 'BUTTON' && e.classList.contains('sx-qc-vi-on')).map((b) => b.textContent);
kiem('chọn sẵn TOÀN BỘ vải đang dùng (HD.08.02: giặt toàn bộ vải đang dùng); vải đã loại không hiện',
  bang(chon(), ['✓ V01-A', '✓ V02-A']) && !m.body.chu.includes('V02-B'), chon());
const khoiLyDo = () => tim(m.body, (e) => e.tagName === 'DIV' && e.kids.some((k) => k.tagName === 'TEXTAREA')
  && e.kids.some((k) => k.textContent && k.textContent.startsWith('Lý do')))[0];
kiem('giặt định kỳ: không có ô lý do (lý do chỉ cho giặt ngoài lịch, loại vải)', khoiLyDo().style.display === 'none');
kiem('người làm điền sẵn người giặt trong cài đặt, chỗ phơi điền chỗ phơi gần nhất',
  oChu(m, 'Người làm (người giặt)').value === 'Chị Lan'
  && oChu(m, 'Phơi tại (giá riêng, mái che, lưới chắn chim)').value === 'Giá mái che');
oChu(m, 'Giờ sôi lại').doi('07:00');
oChu(m, 'Giờ vớt').doi('07:08');
const phut = tim(m.body, (e) => e.classList.contains('sx-vu-phut'))[0];
kiem('đun 8 phút → hiện ngay "chưa đủ 10 phút", chữ đỏ', phut.textContent.includes('= 8 phút — chưa đủ 10 phút')
  && phut.classList.contains('sx-vu-thieu'), phut.textContent);
oChu(m, 'Giờ vớt').doi('07:11');
kiem('đun 11 phút → ✓, hết đỏ', phut.textContent === '= 11 phút ✓' && !phut.classList.contains('sx-vu-thieu'));
tim(m.body, (e) => e.tagName === 'BUTTON' && e.textContent === '✓ V02-A')[0].bam();
oChu(m, 'Khô hẳn, cất lúc (còn ẩm thì không cất)').doi('2026-10-09T15:30');
nut(m.body, 'LƯU VÀ KÝ (QC)').bam();
await cho();
let p = payload();
kiem('LƯU VÀ KÝ: gửi việc, ngày, mã vải đang chọn (bỏ V02-A), giờ đun, chỗ phơi, giờ cất, người làm, ky = 1',
  p.viec === 'Giặt định kỳ' && p.ngay === '2026-10-09' && bang(p.vai, ['V01-A']) && p.gio_soi_lai === '07:00'
  && p.gio_vot === '07:11' && p.phoi_tai === 'Giá mái che' && p.cat_luc === '2026-10-09T15:30'
  && p.nguoi_lam === 'Chị Lan' && p.ky === 1 && p.ly_do === '' && p.name === null, p);
kiem('lưu xong: báo "Đã ghi và ký", đóng form, tải lại', TOAST.at(-1)[0].startsWith('Đã ghi và ký') && m.dong
  && goi('tong_quan').length === 2);

console.log('\n-- giặt ngoài lịch, nhập vải mới, loại vải --');
nutCo(api.container, 'Giặt ngoài lịch').bam();
m = moCuoi();
kiem('giặt ngoài lịch: không chọn sẵn vải; có ô lý do', chon().length === 0
  && m.body.chu.includes('Lý do giặt ngoài lịch'));
nutCo(m.body, 'Lưu, ký sau').bam();
await cho();
kiem('Lưu, ký sau → ky = 0', payload().ky === 0 && payload().viec === 'Giặt ngoài lịch');
nutCo(api.container, 'Nhập vải mới').bam();
m = moCuoi();
const maMoi = tim(m.body, (e) => e.tagName === 'INPUT' && e.placeholder === 'V03-A, V03-B')[0];
kiem('nhập vải mới: ô gõ mã mới (không phải nút chọn vải có sẵn); vẫn có phần đun sôi (vải mới đun trước lần dùng đầu)',
  !!maMoi && chon().length === 0 && tim(m.body, (e) => e.classList.contains('sx-qc-vi')).length === 0
  && m.body.chu.includes('Đun sôi'));
maMoi.doi('v03-a, V03-B');
nut(m.body, 'LƯU VÀ KÝ (QC)').bam();
await cho();
kiem('nhập vải mới gửi chuỗi mã gõ tay (server chuẩn hoá, thêm vào danh mục)', payload().vai === 'v03-a, V03-B'
  && payload().viec === 'Nhập vải mới');
nutCo(api.container, 'Loại vải').bam();
m = moCuoi();
const khoi = tim(m.body, (e) => e.tagName === 'DIV' && e.kids.some((k) => k.textContent && k.textContent.startsWith('Đun sôi')))[0];
kiem('loại vải: ẩn phần đun sôi / phơi / cất; nhãn lý do loại', khoi.style.display === 'none'
  && m.body.chu.includes('Lý do loại'));
oChu(m, 'Lý do loại (thủng, rách, sờn, ố, mốc, còn mùi sau giặt, cháy xém…)').doi('Rách mép');
tim(m.body, (e) => e.tagName === 'BUTTON' && e.textContent === 'V01-A')[0].bam();
nut(m.body, 'LƯU VÀ KÝ (QC)').bam();
await cho();
p = payload();
kiem('loại vải gửi lý do, mã vải; KHÔNG gửi giờ đun / phơi / cất', p.viec === 'Loại vải' && p.ly_do === 'Rách mép'
  && bang(p.vai, ['V01-A']) && p.gio_soi_lai === '' && p.gio_vot === '' && p.phoi_tai === '' && p.cat_luc === '', p);
nut(api.container, 'GHI GIẶT ĐỊNH KỲ').bam();
m = moCuoi();
tim(m.body, (e) => e.tagName === 'BUTTON' && e.textContent === 'Loại vải')[0].bam();
kiem('đổi việc ngay trong form (giặt định kỳ → loại vải): hiện lý do, ẩn đun sôi',
  m.body.chu.includes('Lý do loại') && tim(m.body, (e) => e.tagName === 'DIV'
    && e.kids.some((k) => k.textContent && k.textContent.startsWith('Đun sôi')))[0].style.display === 'none');
nut(api.container, 'GHI GIẶT ĐỊNH KỲ').bam();
m = moCuoi();
oChu(m, 'Giờ sôi lại').doi('07:00');
oChu(m, 'Giờ vớt').doi('07:12');
oChu(m, 'Khô hẳn, cất lúc (còn ẩm thì không cất)').doi('2026-10-09T15:30');
tim(m.body, (e) => e.tagName === 'BUTTON' && e.textContent === 'Loại vải')[0].bam();
khoiLyDo().kids.find((k) => k.tagName === 'TEXTAREA').doi('Sờn');
nut(m.body, 'LƯU VÀ KÝ (QC)').bam();
await cho();
p = payload();
kiem('gõ giờ đun rồi mới đổi sang loại vải → vẫn KHÔNG gửi giờ đun / phơi / cất', p.viec === 'Loại vải'
  && p.gio_soi_lai === '' && p.gio_vot === '' && p.cat_luc === '' && p.phoi_tai === '' && p.ly_do === 'Sờn', p);

console.log('\n-- dòng đã ký, dòng chờ ký, xoá --');
const the = (chu) => tim(api.container, (e) => e.classList.contains('sx-cat-dong') && e.chu.includes(chu))[0];
the('08/10 · Giặt định kỳ').bam();
m = moCuoi();
kiem('dòng đã ký: báo QC đã ký + người ký, khoá; không nút lưu, không nút xoá (QC thường)',
  m.body.chu.includes('QC đã ký: QC Hà') && !nutCo(m.body, 'LƯU VÀ KÝ') && !nutCo(m.body, 'XOÁ DÒNG')
  && m.body.querySelectorAll('input, textarea').every((n) => n.disabled));
the('09/10 · Giặt ngoài lịch').bam();
m = moCuoi();
kiem('dòng chờ ký của mình, ghi hôm nay: sửa được, có nút xoá; giờ cũ điền lại, số phút đỏ',
  !!nutCo(m.body, 'LƯU VÀ KÝ') && !!nutCo(m.body, 'XOÁ DÒNG') && oChu(m, 'Giờ vớt').value === '07:08'
  && tim(m.body, (e) => e.classList.contains('sx-vu-thieu')).length === 1);
tim(m.body, (e) => e.tagName === 'BUTTON' && e.textContent === 'Giặt định kỳ')[0].bam();
nutCo(m.body, 'LƯU VÀ KÝ').bam();
await cho();
kiem('dòng ngoài lịch (có lý do) đổi thành giặt định kỳ → không gửi lý do cũ', payload().ly_do === ''
  && payload().viec === 'Giặt định kỳ' && payload().name === 'GVU-2026-00011');
the('09/10 · Giặt ngoài lịch').bam();
m = moCuoi();
nutCo(m.body, 'XOÁ DÒNG').bam();
kiem('xoá: hỏi xác nhận trước', XAC.length === 1 && XAC[0].title.includes('Xoá dòng giặt ngoài lịch ngày 09/10/2026'));
await XAC[0].onConfirm();
kiem('… xác nhận → gọi xoa đúng dòng', bang(goi('xoa').at(-1)[1], { name: 'GVU-2026-00011' }));

traVe = duLieu({ ds: [dong({ name: 'GVU-2026-00009', ngay: '2026-10-07', viec: 'Giặt ngoài lịch', ly_do: 'ẩm',
  qc_ky_boi: null, qc_ky_luc: '', creation: '2026-10-08' })] });
await V.render(api);
the('07/10 · Giặt ngoài lịch').bam();
kiem('dòng mình ghi HÔM QUA, chưa ký: sửa / ký được nhưng không còn nút xoá', !!nutCo(moCuoi().body, 'LƯU VÀ KÝ')
  && !nutCo(moCuoi().body, 'XOÁ DÒNG'));
traVe = duLieu({ ds: [dong({ qc_ky_boi: null, qc_ky_luc: '', xem_boi: 'iso@x', xem_luc: '2026-10-09 08:00' })] });
await V.render(api);
the('08/10 · Giặt định kỳ').bam();
m = moCuoi();
kiem('Trưởng Ban ISO đã xem, dòng chưa ký: nội dung khoá, QC vẫn có nút KÝ', m.body.chu.includes('Trưởng Ban ISO đã xem')
  && !nutCo(m.body, 'LƯU VÀ KÝ') && !!nut(m.body, 'QC KÝ DÒNG NÀY'));
nut(m.body, 'QC KÝ DÒNG NÀY').bam();
await cho();
kiem('… bấm KÝ → gọi ky đúng dòng', bang(goi('ky').at(-1)[1], { name: 'GVU-2026-00010' }));

console.log('\n-- Trưởng Ban ISO, chỉ xem, danh mục vải --');
traVe = duLieu({ duoc_ghi: false, duoc_xem_thang: true, la_iso: true, duoc_khai_vai: true, user: 'iso@x' });
await V.render(api);
kiem('Ban ISO: không nút ghi (QC ghi), có "ĐÃ XEM THÁNG 10/2026"', !nut(api.container, 'GHI GIẶT ĐỊNH KỲ')
  && api.container.chu.includes('QC ghi và ký sổ giặt') && !!nutCo(api.container, 'ĐÃ XEM THÁNG 10/2026'));
tim(api.container, (e) => e.tagName === 'TEXTAREA')[0].doi('Đủ chu kỳ');
nutCo(api.container, 'ĐÃ XEM THÁNG 10/2026').bam();
kiem('đã xem: hỏi xác nhận, nói rõ còn dòng chưa QC ký', XAC.at(-1).message.includes('còn 1 dòng CHƯA QC KÝ'));
await XAC.at(-1).onConfirm();
kiem('… gửi tháng + nhận xét', bang(goi('xem_thang').at(-1)[1], { thang: '2026-10', nhan_xet: 'Đủ chu kỳ' }));
the('08/10 · Giặt định kỳ').bam();
kiem('Ban ISO mở dòng đã ký: xoá được (sửa trên Desk)', !!nutCo(moCuoi().body, 'XOÁ DÒNG'));
traVe = duLieu({ duoc_ghi: false, xem: { boi: 'iso@x', ten: 'Nguyễn Huy Chiến', luc: '2026-10-09 09:00', nhan_xet: 'Đạt' },
  chua_xem: 0 });
await V.render(api);
kiem('đã xem hết: hiện người xem, ngày, nhận xét; không còn nút', api.container.chu.includes('Nguyễn Huy Chiến · 09/10/2026 — Đạt')
  && !nutCo(api.container, 'ĐÃ XEM THÁNG'));

traVe = duLieu({ duoc_ghi: false, duoc_khai_vai: true });
await V.render(api);
nutCo(api.container, 'Danh mục vải').bam();
const dm = api.container;
kiem('tab Danh mục: nhóm Đang dùng (2), Dự phòng (1), Đã loại (1) + lý do loại', dm.chu.includes('Đang dùng (2)')
  && dm.chu.includes('Dự phòng (1)') && dm.chu.includes('Đã loại (1)') && dm.chu.includes('Rách mép')
  && dm.chu.includes('loại 05/10/2026'));
nut(dm, '+ KHAI VẢI').bam();
m = moCuoi();
oChu(m, 'Mã vải (theo thùng: V01-A, V01-B…)').doi('v05-a');
nut(m.body, 'LƯU').bam();
await cho();
let pv = JSON.parse(goi('luu_vai').at(-1)[1].payload);
kiem('khai vải mới: mặc định Dự phòng, moi = 1, thùng để trống (server đọc từ mã)', pv.ma === 'v05-a'
  && pv.trang_thai === 'Dự phòng' && pv.moi === 1 && pv.thung === '', pv);
tim(api.container, (e) => e.classList.contains('sx-cat-dong') && e.chu.startsWith('V02-B'))[0].bam();
m = moCuoi();
kiem('vải đã loại: không cho đổi trạng thái ở danh mục, chỉ dẫn ghi Nhập vải mới',
  m.body.chu.includes('Đã loại ngày 05/10/2026') && m.body.chu.includes('Nhập vải mới')
  && !tim(m.body, (e) => e.classList.contains('sx-qc-seg')).length);
nut(m.body, 'LƯU').bam();
await cho();
pv = JSON.parse(goi('luu_vai').at(-1)[1].payload);
kiem('… lưu ghi chú vải đã loại: không gửi trạng thái', pv.trang_thai === null && pv.moi === 0 && pv.ma === 'V02-B', pv);

traVe = duLieu({ lan_cuoi: '2026-10-02' });
st_so: {
  await V.render(api);
  nut(api.container, 'Sổ giặt').bam();
  kiem('giặt định kỳ đúng 7 ngày trước → chưa cảnh báo quá hạn', api.container.chu.includes('7 ngày trước')
    && !api.container.chu.includes('Quá 7 ngày'));
  nutCo(api.container, 'Danh mục vải').bam();
  break st_so;
}
traVe = duLieu({ duoc_ghi: false, duoc_khai_vai: false, vai: [], lan_cuoi: '2026-09-01', ds: [] });
await V.render(api);
kiem('tab đang mở giữ qua lần tải lại (vẫn Danh mục vải)', api.container.chu.includes('Chưa khai vải nào')
  && !nut(api.container, 'GHI GIẶT ĐỊNH KỲ'));
nut(api.container, 'Sổ giặt').bam();
kiem('QLSX/người xem, chưa khai vải: báo khai vải ở tab Danh mục, không nhắc quá hạn',
  api.container.chu.includes('Chưa khai vải ủ') && !api.container.chu.includes('Quá 7 ngày'));

ketThuc('VAIU-JS');
