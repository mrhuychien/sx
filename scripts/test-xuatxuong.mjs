// Màn phiếu kiểm tra xuất xưởng BM.08.04 lần BH 01 (D159 — W31): views/qc_xuatxuong.js.
//
// Vì sao phải có bài này: màn điện thoại là chỗ QC ghi 5 mẫu × 6 chỉ tiêu. Sai ở đây là sai lặng lẽ —
// chạm ô mẫu không đổi giá trị, mẫu K mà dòng vẫn Đạt (server chặn, QC không hiểu vì sao), số cân B2
// không lên payload, số phiếu BM.08.02 gửi kèm cả khi Cho xuất xưởng, phiếu cũ (8 mục tạm) mở bằng form
// mới rồi mất mục đã ghi. Nạp code THẬT (view + qcui + dom); modal / toast / bàn số thay bằng bản giả
// ghi lại lời gọi; DOM giả tối thiểu theo cây con (kids) — scripts/fakedom.mjs.
//
// Chạy: node scripts/test-xuatxuong.mjs   (verify.sh gọi sẵn)

import {
  E, MO, PAD, TOAST, bang, cho, dangChon, ketThuc, kiem, napView, nut, tim,
} from './fakedom.mjs';

const XV = await napView('views/qc_xuatxuong.js');
const dongCua = (goc, ma) => tim(goc, (e) => e.classList.contains('sx-xx-muc')
  && e.kids[0] && e.kids[0].textContent.startsWith(`${ma} `))[0];

// ── hàm thuần ──────────────────────────────────────────────────────────
console.log('\n-- ô mẫu, kết luận dòng (hàm thuần) --');
kiem('chạm ô mẫu: — → Đ → K → —', bang(['', 'Đ', 'K'].map(XV.vongMau), ['Đ', 'K', '']) && XV.vongMau(undefined) === 'Đ');
kiem('có mẫu K → dòng ép Không đạt (kể cả QC đã bấm Đạt)', XV.ketQuaDong('B1', ['Đ', 'K', '', '', ''], 'Đạt') === 'Không đạt');
kiem('đủ 5 Đ, dòng trống → gợi Đạt; QC đã bấm thì giữ', XV.ketQuaDong('B3', ['Đ', 'Đ', 'Đ', 'Đ', 'Đ'], '') === 'Đạt'
  && XV.ketQuaDong('B3', ['Đ', 'Đ', 'Đ', 'Đ', 'Đ'], 'Không đạt') === 'Không đạt');
kiem('chưa đủ 5 mẫu → để trống', XV.ketQuaDong('B3', ['Đ', 'Đ', 'Đ', 'Đ', ''], '') === ''
  && XV.ketQuaDong('B3', ['Đ', 'Đ', 'Đ', 'Đ'], '') === '');
kiem('B2 (số cân) không tự kết luận', XV.ketQuaDong('B2', ['150', '151', '149', '150', '150'], '') === ''
  && XV.ketQuaDong('B2', ['K'], 'Đạt') === 'Đạt');
kiem('ba kết luận đúng bản giấy, 5 mẫu', bang(XV.KET_LUAN, ['Cho xuất xưởng', 'Giữ lại chờ xử lý', 'Không cho xuất'])
  && XV.SO_MAU === 5);

// ── màn hình ───────────────────────────────────────────────────────────
const A = [['A1', 'Vòng kiểm QC BM.08.01', 'Đủ 3 lượt', 'Đạt', 'BM.08.01 — ngày SX 05/07/2026: 3 lượt'],
  ['A2', 'Phiếu sự cố BM.08.02 liên quan đến lô', 'Không có', 'Không đạt', 'SC-1 Mở: CHƯA quyết định'],
  ['A3', 'Nguyên liệu, bao bì', 'tiếp nhận đạt', '', ''], ['A4', 'Bột vị không lạc', 'Âm tính', 'Không áp dụng', 'Lô bánh — KAD.'],
  ['A5', 'Mẫu lưu', 'đúng lô', 'Đạt', 'Mẫu lưu: LM-1']];
const B = [['B1', 'Cảm quan'], ['B2', 'Khối lượng tịnh (g)'], ['B3', 'Bao gói, mối hàn'], ['B4', 'Nhãn'],
  ['B5', 'HSD in trên bao bì'], ['B6', 'Thùng carton']];
const phieu = (them = {}) => ({
  name: 'XX-1', san_pham: 'TP-SEN', ten_san_pham: 'Bánh sen', hsd: '2027-04-05', nsx: '2026-07-05', trang_thai: 'Nháp',
  ket_luan: '', ghi_chu: '', quy_cach: 'Hộp 250 g', ngay_nghien: '2026-07-03', ngay_rang: '2026-07-02', su_co: '',
  qc_kiem: '', moi: true, sua: true, duyet: false, tu_kiem: false, ky_qlsx: false,
  xu_ly: { 'Cho xuất xưởng': 'Lô đạt toàn bộ', 'Giữ lại chờ xử lý': 'Kiểm lại trên phiếu mới', 'Không cho xuất': 'Huỷ' },
  su_co_lo: [{ name: 'SC-1', trang_thai: 'Mở', quyet_dinh_sp: '', mo_ta: 'NC-02' }],
  ds_muc: [...A.map(([ma, nd, yc, gy, cc]) => ({ ma, noi_dung: nd, yeu_cau: yc, ket_qua: ma === 'A5' ? 'Đạt' : '',
    ghi_chu: '', mau: ['', '', '', '', ''], su_co: ma === 'A2' ? 'SC-1' : '', goi_y: gy, can_cu: cc })),
  ...B.map(([ma, nd]) => ({ ma, noi_dung: nd, yeu_cau: 'yêu cầu', ket_qua: '', ghi_chu: '', mau: ['', '', '', '', ''],
    su_co: '', goi_y: '', can_cu: '' }))],
  ...them,
});
const GOI = [];
let traVe = phieu();
const api = {
  container: new E('div'),
  call: async (m, a) => {
    GOI.push([m, a]);
    if (m.endsWith('ds_xuat_xuong')) {
      return { chan: 1, duoc_ghi: true, duoc_duyet: false, phieu: [],
        cho_kiem: [{ item: 'TP-SEN', ten: 'Bánh sen', hsd: '2027-04-05', nsx: '2026-07-05', so_luong: 120, dvt: 'Hộp', nguon: 'đã vào hộp' }] };
    }
    return traVe;
  },
};

console.log('\n-- phiếu lần BH 01 trên điện thoại --');
await XV.render(api);
nut(api.container, 'KIỂM BM.08.04').bam();
await cho();
let m = MO[MO.length - 1];
kiem('bấm KIỂM → lập phiếu đúng lô, mở phiếu', GOI.some(([k, a]) => k.endsWith('lap_phieu') && a.hsd === '2027-04-05')
  && m && m.kicker === 'BM.08.04 · XX-1');
kiem('mục A: hiện yêu cầu + gợi ý của app, nhưng KHÔNG chấm sẵn (QC vẫn bấm)',
  dongCua(m.body, 'A1').chu.includes('Gợi ý: Đạt') && dongCua(m.body, 'A1').chu.includes('3 lượt')
  && dangChon(dongCua(m.body, 'A1')) === '' && dangChon(dongCua(m.body, 'A5')) === 'Đạt');
kiem('A4 có KAD, A1 không có KAD', !!nut(dongCua(m.body, 'A4'), 'KAD') && !nut(dongCua(m.body, 'A1'), 'KAD'));
kiem('QC đang ghi: không có nút ký Quản lý sản xuất', !nut(m.body, 'KÝ — QUẢN LÝ SẢN XUẤT') && !!nut(m.body, 'GỬI DUYỆT'));
kiem('A1 có hai ô ngày (nghiền, rang); A2 có chọn số phiếu BM.08.02',
  tim(dongCua(m.body, 'A1'), (e) => e.tagName === 'INPUT' && e.type === 'date').map((e) => e.value).join() === '2026-07-03,2026-07-02'
  && tim(dongCua(m.body, 'A2'), (e) => e.tagName === 'SELECT').length === 1);
const b1 = dongCua(m.body, 'B1');
const o1 = tim(b1, (e) => e.classList.contains('sx-xx-mau-o'));
kiem('B1: đủ 5 ô mẫu', o1.length === 5 && o1.every((o) => o.textContent.includes('—')));
o1.forEach((o) => o.bam());
kiem('chạm cả 5 ô → Đ, dòng tự Đạt', o1.every((o) => o.textContent.endsWith('Đ')) && dangChon(b1) === 'Đạt', dangChon(b1));
o1[2].bam();
kiem('chạm lại mẫu 3 → K, dòng ép Không đạt, ô tô đỏ', o1[2].textContent.endsWith('K') && dangChon(b1) === 'Không đạt'
  && o1[2].classList.contains('sx-xx-mau-k'));
const o2 = tim(dongCua(m.body, 'B2'), (e) => e.classList.contains('sx-xx-mau-o'));
o2[0].bam();
const pad = PAD[PAD.length - 1];
kiem('B2: chạm ô → bàn số gam có số thập phân', pad && pad.allowDecimal === true && pad.title === 'Khối lượng tịnh (g)'
  && pad.kicker === 'B2 · Mẫu 1');
pad.onOk(150.5);
kiem('… ghi số cân vào ô', o2[0].textContent.endsWith('150.5'));
PAD[PAD.length - 1] && (o2[0].bam(), PAD[PAD.length - 1].onOk(0));
kiem('… bàn số về 0 = xoá ô', o2[0].textContent.endsWith('—'));
o2[0].bam(); PAD[PAD.length - 1].onOk(150.5);
const kl = tim(m.body, (e) => e.classList.contains('sx-xx-kl'))[0];
kiem('kết luận: ba nút đúng bản giấy', bang(tim(kl, (e) => e.tagName === 'BUTTON').map((e) => e.textContent),
  ['Cho xuất xưởng', 'Giữ lại chờ xử lý', 'Không cho xuất']));
nut(kl, 'Giữ lại chờ xử lý').bam();
const sc = tim(m.body, (e) => e.classList.contains('sx-xx-sc'))[0];
kiem('Giữ lại → hiện cách xử lý + chọn phiếu BM.08.02 (mặc định: app lập lúc gửi duyệt)',
  m.body.chu.includes('Kiểm lại trên phiếu mới') && sc.chu.includes('app lập phiếu mới lúc gửi duyệt')
  && sc.chu.includes('SC-1'));
tim(sc, (e) => e.tagName === 'SELECT')[0].doi('SC-1');
tim(dongCua(m.body, 'A1'), (e) => e.tagName === 'INPUT' && e.type === 'date')[1].doi('2026-07-01');
nut(m.body, 'LƯU').bam();
await cho();
let p = JSON.parse(GOI.filter(([k]) => k.endsWith('luu_phieu')).pop()[1].payload);
const r = (ma) => p.ds_muc.find((x) => x.ma === ma);
kiem('LƯU gửi: 5 mẫu B1 + kết luận dòng, số cân B2, ngày rang QC sửa, kết luận + số phiếu chọn',
  bang(r('B1').mau, ['Đ', 'Đ', 'K', 'Đ', 'Đ']) && r('B1').ket_qua === 'Không đạt' && r('B2').mau[0] === '150.5'
  && p.ngay_rang === '2026-07-01' && p.ket_luan === 'Giữ lại chờ xử lý' && p.su_co === 'SC-1', p);
kiem('… mục A không gửi ô mẫu; A2 gửi số phiếu của dòng', r('A1').mau === undefined && r('A2').su_co === 'SC-1'
  && r('A5').ket_qua === 'Đạt');

traVe = phieu();
await XV.render(api);
nut(api.container, 'KIỂM BM.08.04').bam();
await cho();
m = MO[MO.length - 1];
nut(tim(m.body, (e) => e.classList.contains('sx-xx-kl'))[0], 'Cho xuất xưởng').bam();
nut(m.body, 'GỬI DUYỆT').bam();
await cho();
p = JSON.parse(GOI.filter(([k]) => k.endsWith('gui_duyet')).pop()[1].payload);
kiem('Cho xuất xưởng → KHÔNG gửi số phiếu BM.08.02, không hiện ô chọn', p.ket_luan === 'Cho xuất xưởng'
  && !('su_co' in p) && tim(m.body, (e) => e.classList.contains('sx-xx-sc'))[0].kids.length === 0);
kiem('gửi xong: đóng phiếu, báo đã gửi', m.dong && TOAST.some(([s]) => s === 'Đã gửi Ban ISO duyệt'));

traVe = phieu();
nut(api.container, 'KIỂM BM.08.04').bam();
await cho();
m = MO[MO.length - 1];
traVe = phieu({ ngay_rang: '2026-07-01' });
nut(m.body, '↻ TRA LẠI HỒ SƠ LÔ').bam();
await cho();
kiem('TRA LẠI HỒ SƠ: gửi cái đang ghi, mở lại phiếu với hồ sơ mới', GOI[GOI.length - 1][0].endsWith('tra_ho_so')
  && m.dong && MO[MO.length - 1] !== m);

console.log('\n-- phiếu đã gửi: QLSX ký, người duyệt --');
traVe = phieu({ trang_thai: 'Chờ duyệt', sua: false, ky_qlsx: true, ket_luan: 'Không cho xuất', su_co: 'SC-9',
  qc_kiem: 'qc@x', kiem_luc: '2026-10-08 15:00:00' });
nut(api.container, 'KIỂM BM.08.04').bam();
await cho();
m = MO[MO.length - 1];
kiem('phiếu khoá: ô mẫu, nút kết luận không bấm được; không có LƯU / TRA LẠI',
  tim(m.body, (e) => e.classList.contains('sx-xx-mau-o')).every((o) => o.disabled) && !nut(m.body, 'LƯU')
  && !tim(m.body, (e) => e.tagName === 'BUTTON' && e.textContent.startsWith('↻')).length);
kiem('QLSX thấy nút ký; ô ký hiện QC + giờ', !!nut(m.body, 'KÝ — QUẢN LÝ SẢN XUẤT')
  && m.body.chu.includes('QC kiểm qc@x · 08/10/2026 15:00') && m.body.chu.includes('Quản lý sản xuất chưa ký'));
nut(m.body, 'KÝ — QUẢN LÝ SẢN XUẤT').bam();
await cho();
kiem('… bấm ký gọi ky_qlsx đúng phiếu, xong thì tải lại danh sách',
  GOI.some(([k, a]) => k.endsWith('ky_qlsx') && a.name === 'XX-1') && GOI[GOI.length - 1][0].endsWith('ds_xuat_xuong'));
traVe = phieu({ trang_thai: 'Chờ duyệt', sua: false, duyet: true, ket_luan: 'Không cho xuất', su_co: 'SC-9' });
nut(api.container, 'KIỂM BM.08.04').bam();
await cho();
m = MO[MO.length - 1];
kiem('người duyệt: nút ghi rõ kết luận đang duyệt', !!nut(m.body, 'DUYỆT KẾT LUẬN KHÔNG CHO XUẤT'));

console.log('\n-- phiếu cũ (8 mục tạm) --');
traVe = phieu({ moi: false, ds_muc: [1, 2, 3].map((i) => ({ ma: String(i), noi_dung: `Mục tạm ${i}`, ket_qua: 'Đạt', ghi_chu: '' })),
  so_mau: 3, ket_luan: 'Cho xuất xưởng' });
nut(api.container, 'KIỂM BM.08.04').bam();
await cho();
m = MO[MO.length - 1];
kiem('phiếu cũ mở form cũ: giữ mục đã ghi, có số mẫu, kết luận ba lựa chọn mới',
  m.kicker.includes('mẫu tạm') && m.body.chu.includes('Mục tạm 2') && !tim(m.body, (e) => e.classList.contains('sx-xx-mau-o')).length
  && dangChon(tim(m.body, (e) => e.classList.contains('sx-xx-kl'))[0]) === 'Cho xuất xưởng');
nut(m.body, 'LƯU').bam();
await cho();
p = JSON.parse(GOI.filter(([k]) => k.endsWith('luu_phieu')).pop()[1].payload);
kiem('… LƯU gửi lại đúng mục cũ + số mẫu', p.ds_muc.length === 3 && p.so_mau === 3 && p.ds_muc[1].ma === '2');

ketThuc('XUATXUONG-JS');
