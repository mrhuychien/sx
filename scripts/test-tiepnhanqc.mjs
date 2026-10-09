// Màn "Tiếp nhận NL" của QC (D160 — W33): views/qc_tiepnhan.js.
//
// Vì sao phải có bài này: màn điện thoại gửi lên ĐÚNG các ô QC — gửi kèm số lượng / kho là QC sửa sổ kho;
// mất ô kiểm xe là chuyến hàng không có BM.09.01; kết luận xe không tự thành Không đạt khi một mục hỏng là
// xe bẩn vẫn "Đạt" trên màn hình; phiếu đã duyệt mà còn nút lưu là QC bấm rồi nhận lỗi khó hiểu. Nạp code
// THẬT (view + qcui + dom); modal / toast / bàn số giả — scripts/fakedom.mjs.
//
// Chạy: node scripts/test-tiepnhanqc.mjs   (verify.sh gọi sẵn)

import {
  E, MO, PAD, TOAST, bang, cho, dangChon, ketThuc, kiem, napView, nut, tim,
} from './fakedom.mjs';

const TV = await napView('views/qc_tiepnhan.js');

console.log('\n-- kết luận kiểm xe (hàm thuần, như sx/qc/kiem_xe.ket_luan) --');
kiem('một mục Không đạt → Không đạt (kể cả người kiểm đã bấm Đạt)', TV.ketLuanXe(['Đạt', 'Không đạt', '', ''], 'Đạt') === 'Không đạt');
kiem('đủ mục Đạt, chưa kết luận → Đạt; người kiểm đã chọn thì giữ', TV.ketLuanXe(['Đạt', 'Đạt'], '') === 'Đạt'
  && TV.ketLuanXe(['Đạt', 'Đạt'], 'Không đạt') === 'Không đạt');
kiem('chưa đủ mục → giữ nguyên', TV.ketLuanXe(['Đạt', ''], '') === '' && TV.ketLuanXe([], '') === '');

const MUC = [{ f: 'custom_xe_sach', nhan: 'Thùng xe sạch' }, { f: 'custom_xe_khong_chung', nhan: 'Không chở chung' },
  { f: 'custom_xe_con_trung', nhan: 'Không côn trùng' }, { f: 'custom_xe_che_chan', nhan: 'Thùng kín' }];
const phieu = (them = {}) => ({
  doctype: 'Purchase Receipt', name: 'MAT-PRE-0007', docstatus: 0, ngay: '2026-10-09', ncc: 'Công ty Sữa ABC',
  ncc_loai: 'Nguyên liệu thực phẩm', ncc_nguon: 'Nhập khẩu', ncc_duyet: true, pkn: null, nguoi_kiem: '', ghi_chu_qc: '',
  xe: { ap_dung: true, muc: MUC, nguoi_kiem: '', custom_xe_bien_so: '', custom_xe_tai_xe: '', custom_xe_ghi_chu: '',
    custom_xe_sach: '', custom_xe_khong_chung: '', custom_xe_con_trung: '', custom_xe_che_chan: '', custom_xe_ket_luan: '' },
  dong: [{ name: 'r1', idx: 1, item_code: 'SUA', item_name: 'Sữa bột', qty: 50, uom: 'Kg', kho: 'Kho NVL', batch_no: '',
    giay_to: 'Nhập khẩu — COA lô: KHÔNG', can_coa: true, can_aflatoxin: false, custom_ncc_lo: '', custom_co_cq: '',
    custom_coa_vi_sinh: '', custom_aflatoxin: '', custom_do_am: null, custom_cam_quan_dat: '', custom_ket_luan: '' }],
  so_anh: 0, do_am_toi_da: 13,
  lua_chon: { custom_co_cq: ['Có', 'Không'], custom_coa_vi_sinh: ['Có', 'Không', 'Không yêu cầu'],
    custom_aflatoxin: ['Có', 'Không', 'Không yêu cầu'], custom_cam_quan_dat: ['Đạt', 'Không đạt'],
    custom_ket_luan: ['Đạt', 'Không đạt', 'Cách ly'] },
  sua: true, them_anh: true, bao: [],
  ...them,
});
const GOI = [];
let traVe = phieu();
const DS = [
  { doctype: 'Purchase Receipt', name: 'MAT-PRE-0007', ncc: 'Công ty Sữa ABC', loai_ncc: 'Nguyên liệu thực phẩm',
    ngay: '2026-10-09', so_dong: 1, da_kl: 0, xe_can: true, xe_kl: '', bien_so: '', nguoi_kiem: '', xong: false },
  { doctype: 'Purchase Invoice', name: 'ACC-PINV-0003', ncc: 'Công ty Đỗ', loai_ncc: 'Nguyên liệu thực phẩm',
    ngay: '2026-10-08', so_dong: 2, da_kl: 2, xe_can: false, xe_kl: '', bien_so: '', nguoi_kiem: 'qc@x', xong: true }];
const api = {
  container: new E('div'),
  call: async (m, a) => {
    GOI.push([m, a]);
    if (m.endsWith('ds_tiep_nhan')) return { ds: DS, duoc_ghi: true, so_ngay: 14 };
    return traVe;
  },
};

console.log('\n-- danh sách --');
await TV.render(api);
kiem('hai khối: chờ kiểm / đã kiểm đủ — chờ thủ kho duyệt', api.container.chu.includes('Chờ kiểm (1)')
  && api.container.chu.includes('Đã kiểm đủ — chờ thủ kho duyệt (1)'));
kiem('thẻ phiếu: số dòng đã kết luận, xe chưa kiểm', api.container.chu.includes('kết luận 0/1 dòng')
  && api.container.chu.includes('xe: chưa kiểm'));
nut(api.container, 'KIỂM TIẾP NHẬN').bam();
await cho();
let m = MO[MO.length - 1];
kiem('mở phiếu đúng chứng từ', GOI.some(([k, a]) => k.endsWith('xem_phieu') && a.doctype === 'Purchase Receipt'
  && a.name === 'MAT-PRE-0007') && m.kicker === 'BM.07.03 · MAT-PRE-0007');

console.log('\n-- phiếu: kiểm xe + dòng hàng --');
const xe = tim(m.body, (e) => e.classList.contains('sx-tn-xe'))[0];
kiem('khối kiểm xe: đủ các mục server gửi + kết luận', !!xe && MUC.every((x) => xe.chu.includes(x.nhan))
  && xe.chu.includes('Kết luận kiểm xe'));
const hangMuc = (nhan) => tim(xe, (e) => e.classList.contains('sx-tn-o') && e.kids[0] && e.kids[0].textContent.startsWith(nhan))[0];
MUC.forEach((x) => nut(hangMuc(x.nhan), 'Đạt').bam());
kiem('chấm đủ mục Đạt → kết luận xe tự Đạt', dangChon(hangMuc('Kết luận kiểm xe')) === 'Đạt');
nut(hangMuc('Thùng kín'), 'Không đạt').bam();
kiem('một mục Không đạt → kết luận xe Không đạt, nói hậu quả', dangChon(hangMuc('Kết luận kiểm xe')) === 'Không đạt'
  && hangMuc('Kết luận kiểm xe').chu.includes('mọi dòng Cách ly'));
nut(hangMuc('Thùng kín'), 'Đạt').bam();
tim(xe, (e) => e.tagName === 'INPUT')[0].doi('29C-123.45');
const dong = tim(m.body, (e) => e.classList.contains('sx-xx-muc'))[0];
kiem('dòng hàng: tên, số lượng, kho; COA báo nhóm hàng bắt buộc; giấy tờ lô app ghi',
  dong.chu.includes('Sữa bột') && dong.chu.includes('50 Kg') && dong.chu.includes('nhóm hàng bắt buộc COA')
  && dong.chu.includes('Giấy tờ lô: Nhập khẩu — COA lô: KHÔNG'));
kiem('aflatoxin chỉ hiện với nhóm hàng phải có (hoặc đã ghi)', !dong.chu.includes('Kết quả aflatoxin'));
const o = (nhan) => tim(dong, (e) => e.classList.contains('sx-tn-o') && e.kids[0] && e.kids[0].textContent.startsWith(nhan))[0];
tim(o('Lô NCC'), (e) => e.tagName === 'INPUT')[0].doi('LOT-2610');
nut(o('COA vi sinh'), 'Có').bam();
nut(o('Cảm quan'), 'Đạt').bam();
nut(o('Kết luận tiếp nhận'), 'Đạt').bam();
tim(dong, (e) => e.classList.contains('sx-qc-oso-khung'))[0].bam();
const pad = PAD[PAD.length - 1];
kiem('độ ẩm: bàn số có thập phân, nói ngưỡng', pad.allowDecimal === true && pad.unitLabel === '%'
  && dong.chu.includes('ngưỡng ≤ 13'));
pad.onOk(0);
kiem('… bàn số về 0 = xoá độ ẩm (rỗng khác 0)', tim(dong, (e) => e.classList.contains('sx-qc-oso-khung'))[0].chu.startsWith('—'));
tim(dong, (e) => e.classList.contains('sx-qc-oso-khung'))[0].bam();
PAD[PAD.length - 1].onOk(11.5);
traVe = phieu({ bao: ['Kiểm tra nguyên liệu đầu vào:\nDòng 1 (SUA): Nhập khẩu — phải có COA'] });
nut(m.body, 'LƯU KẾT QUẢ KIỂM').bam();
await cho();
const p = JSON.parse(GOI.filter(([k]) => k.endsWith('luu_phieu')).pop()[1].payload);
kiem('LƯU gửi đúng ô QC của dòng — KHÔNG gửi số lượng / kho / đơn giá',
  bang(Object.keys(p.dong[0]).sort(), ['custom_aflatoxin', 'custom_cam_quan_dat', 'custom_co_cq', 'custom_coa_vi_sinh',
    'custom_do_am', 'custom_ket_luan', 'custom_ncc_lo', 'name'])
  && p.dong[0].custom_ncc_lo === 'LOT-2610' && p.dong[0].custom_do_am === 11.5 && p.dong[0].custom_ket_luan === 'Đạt', p);
kiem('… kèm kiểm xe: biển số, các mục, kết luận', p.xe.custom_xe_bien_so === '29C-123.45'
  && MUC.every((x) => p.xe[x.f] === 'Đạt') && p.xe.custom_xe_ket_luan === 'Không đạt', p.xe);
m = MO[MO.length - 1];
kiem('lưu xong: mở lại phiếu với lời cảnh báo của luật trên đầu', MO[MO.length - 2].dong
  && m.body.chu.includes('Dòng 1 (SUA): Nhập khẩu — phải có COA')
  && TOAST.some(([s]) => s.startsWith('Đã lưu — xem cảnh báo')));

console.log('\n-- phiếu đã duyệt / hoá đơn mua --');
traVe = phieu({ docstatus: 1, sua: false, xe: { ...phieu().xe, ap_dung: false } });
nut(api.container, 'KIỂM TIẾP NHẬN').bam();
await cho();
m = MO[MO.length - 1];
kiem('phiếu đã duyệt: nói rõ chỉ xem; không còn nút lưu; ô khoá; vẫn thêm ảnh được',
  m.body.chu.includes('Phiếu đã duyệt — chỉ xem, thêm ảnh.') && !nut(m.body, 'LƯU KẾT QUẢ KIỂM')
  && tim(m.body, (e) => e.tagName === 'INPUT').every((e) => e.disabled) && !!nut(m.body, '📷 CHỤP ẢNH'));
kiem('… NCC không bắt kiểm xe và chưa ghi gì → không hiện khối kiểm xe', !tim(m.body, (e) => e.classList.contains('sx-tn-xe')).length);
traVe = phieu({ doctype: 'Purchase Invoice', xe: null });
nut(api.container, 'MỞ PHIẾU').bam();
await cho();
m = MO[MO.length - 1];
nut(m.body, 'LƯU KẾT QUẢ KIỂM').bam();
await cho();
const p2 = JSON.parse(GOI.filter(([k]) => k.endsWith('luu_phieu')).pop()[1].payload);
kiem('hoá đơn mua: không có khối xe, payload không có xe', !('xe' in p2)
  && GOI.filter(([k]) => k.endsWith('luu_phieu')).pop()[1].doctype === 'Purchase Invoice');

ketThuc('TIEPNHANQC-JS');
