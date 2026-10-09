// Màn "Kiểm nghiệm" + "Việc định kỳ" — phần W35 (D166): views/qc_kiemnghiem.js, views/qc_lichviec.js.
//
// Vì sao phải có bài này: nước, nguyên liệu, bao bì, thẩm tra vải ủ theo KH.KN.01 là việc kiểm nghiệm định kỳ —
// màn Kiểm nghiệm phải hiện chúng (kể cả việc CHƯA ĐẶT HẠN — nói ra, không im lặng), GỬI MẪU phải gửi kèm việc
// (không gắn việc thì việc không dời hạn, nhắc mãi), chờ kết quả thì là GHI KẾT QUẢ; màn Việc định kỳ không cho
// bấm "Đã làm" việc kiểm nghiệm (lần làm = phiếu gửi mẫu), cho lưu việc chưa biết hạn, có chu kỳ 2 năm.
// Nạp code THẬT (view + qcui + dom); modal / toast giả — scripts/fakedom.mjs.
//
// Chạy: node scripts/test-kiemnghiem.mjs   (verify.sh gọi sẵn)

import {
  E, MO, ketThuc, kiem, napView, tim,
} from './fakedom.mjs';

const KN = await napView('views/qc_kiemnghiem.js');
const LV = await napView('views/qc_lichviec.js');
const nutCo = (goc, chu) => tim(goc, (e) => e.tagName === 'BUTTON' && e.textContent.includes(chu))[0];
const cho = () => new Promise((r) => { setTimeout(r, 0); });
const moCuoi = () => MO[MO.length - 1];

console.log('\n-- dòng hạn việc kiểm nghiệm (hàm thuần) --');
kiem('chưa đặt hạn → nói ra, chỉ chỗ đặt', KN.hanViec({ trang_thai: 'Chưa đặt hạn', han: '' })
  === 'chưa đặt hạn — Ban ISO đặt hạn ở màn Việc định kỳ');
kiem('quá hạn / còn hạn / một lần đã gửi', KN.hanViec({ trang_thai: 'Quá hạn', han: '2026-10-01', con: -8 })
  === 'quá hạn 8 ngày (01/10/2026)' && KN.hanViec({ trang_thai: 'Sắp đến hạn', han: '2026-10-31', con: 22 })
  === 'hạn 31/10/2026 · còn 22 ngày' && KN.hanViec({ trang_thai: 'Ngừng', phieu_cuoi: { ngay_gui: '2026-10-09' } })
  === 'đã gửi mẫu 09/10/2026');
kiem('chu kỳ: + 1 năm, + 2 năm, + 1 quý', LV.kyChu('Năm') === '1 năm' && LV.kyChu('2 năm') === '2 năm'
  && LV.kyChu('Quý') === '1 quý');

const viec = (o) => ({ name: 'VD-1', ten: 'Kiểm nghiệm đỗ xanh nhập khẩu', chu_ky: 'Năm', han: '2026-10-31', con: 22,
  bao_truoc: 30, ngung: 0, doi_tuong_kn: 'Nguyên liệu', tan_suat: '1 lần / năm', trang_thai: 'Sắp đến hạn',
  mo_ta: 'Aflatoxin B1, tổng; độ ẩm', ho_so: 'KH.KN.01', lan_cuoi: '', phieu_cuoi: null, ...o });
const DL = {
  ke_hoach: [], cat: [], phieu: [{ name: 'KN-2026-00007', doi_tuong: 'Nước', viec_dinh_ky: 'VD-2', ngay_gui: '2026-10-02',
    ket_qua: '', so_phieu: '', ten_san_pham: null, mo_ta_mau: '', chi_tieu: '', phong_kn: '', creation: '2026-10-02' }],
  viec: [viec(), viec({ name: 'VD-2', ten: 'Kiểm nghiệm nước sản xuất', doi_tuong_kn: 'Nước', trang_thai: 'Còn hạn',
    han: '2027-10-31', con: 387, phieu_cuoi: { name: 'KN-2026-00007', ngay_gui: '2026-10-02', ket_qua: '', so_phieu: '' } }),
  viec({ name: 'VD-3', ten: 'Kiểm nghiệm thôi nhiễm bao bì', doi_tuong_kn: 'Khác', chu_ky: '2 năm', tan_suat: '2 năm / lần',
    trang_thai: 'Chưa đặt hạn', han: '', con: null }),
  viec({ name: 'VD-4', ten: 'Thẩm tra vải ủ — tháng 10/2026', doi_tuong_kn: 'Khác', chu_ky: 'Một lần', ngung: 1,
    trang_thai: 'Ngừng', phieu_cuoi: { name: 'KN-2026-00009', ngay_gui: '2026-10-09', ket_qua: 'Đạt', so_phieu: 'KQ-9' } })],
  nam: 2026, hom_nay: '2026-10-09', han_dau: '2026-10-31', sap_den: 30, cho_lau: 21,
  doi_tuong: ['Sản phẩm', 'Cát rang', 'Nguyên liệu', 'Nước', 'Khác'], duoc_ghi: true, la_iso: false, user: 'qc@x',
};
const GOI = [];
const api = {
  container: new E('div'),
  call: async (m, a) => {
    GOI.push([m, a]);
    if (m.endsWith('qc_kiemnghiem.tong_quan')) return DL;
    if (m.endsWith('gui_mau')) return { name: 'KN-2026-00010', lan_sau: '2027-10-31', su_co: null };
    if (m.endsWith('qc_lichviec.tong_quan')) {
      return { ds: [viec({ lich_su: [] }), viec({ name: 'VD-5', ten: 'Thử khôi phục dữ liệu', doi_tuong_kn: '', lich_su: [] }),
        viec({ name: 'VD-6', ten: 'Xem xét lãnh đạo', doi_tuong_kn: '', trang_thai: 'Chưa đặt hạn', han: '', con: null,
          lich_su: [] })],
      chu_ky: ['Năm', '2 năm', 'Quý', 'Tháng', 'Một lần'], doi_tuong_kn: ['Nước', 'Nguyên liệu', 'Khác'],
      hom_nay: '2026-10-09', duoc_ghi: true };
    }
    return {};
  },
};
const the = (c, ten) => tim(c, (e) => e.classList.contains('sx-qc-sc') && e.chu.startsWith(ten))[0];

console.log('\n-- màn Kiểm nghiệm: nước · nguyên liệu · khác --');
await KN.render(api);
const c = api.container;
kiem('khối riêng, đếm 4 việc; chip đầu màn: 1 đến hạn, 1 chưa đặt hạn', c.chu.includes('Nước · nguyên liệu · khác (KH.KN.01) — 4')
  && c.chu.includes('1 mẫu nước / NL / khác đến hạn') && c.chu.includes('1 việc kiểm nghiệm chưa đặt hạn'));
const t1 = the(c, 'Kiểm nghiệm đỗ xanh');
kiem('thẻ việc: trạng thái, mẫu của · tần suất, hạn, chỉ tiêu, nút GỬI MẪU', t1.chu.includes('Sắp đến hạn')
  && t1.chu.includes('Nguyên liệu · 1 lần / năm') && t1.chu.includes('hạn 31/10/2026 · còn 22 ngày')
  && t1.chu.includes('Aflatoxin B1, tổng; độ ẩm') && !!nutCo(t1, 'GỬI MẪU'));
kiem('việc chưa đặt hạn: nói "chưa đặt hạn", vẫn gửi mẫu được', the(c, 'Kiểm nghiệm thôi nhiễm').chu.includes('chưa đặt hạn')
  && !!nutCo(the(c, 'Kiểm nghiệm thôi nhiễm'), 'GỬI MẪU'));
kiem('việc đang chờ kết quả → GHI KẾT QUẢ; việc một lần đã gửi → "Đã gửi mẫu", không nút',
  !!nutCo(the(c, 'Kiểm nghiệm nước'), 'GHI KẾT QUẢ') && the(c, 'Thẩm tra vải ủ').chu.includes('Đã gửi mẫu')
  && !tim(the(c, 'Thẩm tra vải ủ'), (e) => e.tagName === 'BUTTON').length);
kiem('phiếu trong năm gắn việc: hiện tên việc (không chỉ "Nước")', c.chu.includes('02/10/2026 · Kiểm nghiệm nước sản xuất'));
nutCo(t1, 'GỬI MẪU').bam();
const m = moCuoi();
kiem('hộp gửi mẫu: tiêu đề = việc, chỉ tiêu điền sẵn, không hỏi lại mẫu của', m.title === 'Kiểm nghiệm đỗ xanh nhập khẩu'
  && tim(m.body, (e) => e.tagName === 'TEXTAREA')[0].value === 'Aflatoxin B1, tổng; độ ẩm' && !m.body.chu.includes('Mẫu của'));
nutCo(m.body, 'GHI GỬI MẪU').bam();
await cho();
const p = JSON.parse(GOI.filter(([k]) => k.endsWith('gui_mau')).pop()[1].payload);
kiem('gửi kèm việc + mẫu của của việc', p.viec_dinh_ky === 'VD-1' && p.doi_tuong === 'Nguyên liệu', p);

console.log('\n-- màn Việc định kỳ --');
await LV.render(api);
const c2 = api.container;
const kn = the(c2, 'Kiểm nghiệm đỗ xanh');
kiem('việc kiểm nghiệm: chip "Kiểm nghiệm · Nguyên liệu", không có ĐÃ LÀM, có nút sang màn Kiểm nghiệm',
  kn.chu.includes('Kiểm nghiệm · Nguyên liệu') && !nutCo(kn, 'ĐÃ LÀM') && !!nutCo(kn, 'GỬI MẪU (màn Kiểm nghiệm)'));
globalThis.window.location = { hash: '' };
nutCo(kn, 'GỬI MẪU (màn Kiểm nghiệm)').bam();
kiem('… bấm → #/qc/kiemnghiem', globalThis.window.location.hash === '#/qc/kiemnghiem');
kiem('việc thường vẫn ĐÃ LÀM; việc chưa đặt hạn nói ra', !!nutCo(the(c2, 'Thử khôi phục'), 'ĐÃ LÀM')
  && the(c2, 'Xem xét lãnh đạo').chu.includes('chưa đặt hạn'));
nutCo(c2, '+ THÊM VIỆC ĐỊNH KỲ').bam();
const ms = moCuoi();
tim(ms.body, (e) => e.tagName === 'INPUT')[0].doi('Kiểm nghiệm thôi nhiễm bao bì');
nutCo(ms.body, '2 năm').bam();
nutCo(ms.body, 'Khác').bam();
nutCo(ms.body, 'LƯU').bam();
await cho();
const pl = JSON.parse(GOI.filter(([k]) => k.endsWith('qc_lichviec.luu')).pop()[1].payload);
kiem('thêm việc không có hạn → vẫn gửi lưu (chưa đặt hạn); chu kỳ 2 năm; mẫu của Khác',
  pl.han === '' && pl.chu_ky === '2 năm' && pl.doi_tuong_kn === 'Khác' && pl.ten === 'Kiểm nghiệm thôi nhiễm bao bì', pl);

ketThuc('KIEMNGHIEM-JS');
