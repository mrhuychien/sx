// Màn ISO #/iso (D176) — views/iso.js, iso_xuat.js; thanh tab qcui.tabXemXet; chuyển đường cũ trong views/qc.js.
//
// Vì sao phải có bài này: màn QC giờ là màn NHẬP LIỆU — người có màn ISO không được còn tab Xem xét / Truy xuất ở QC,
// và đường cũ #/qc/attp, #/qc/bienban/<x> (hộp nhắc, thẻ Tổng quan) phải sang đúng màn con của #/iso, giữ tham số;
// người KHÔNG có màn ISO (QLSX, QC mở biên bản phải ký) vẫn xem trong QC như cũ. Màn xuất: chọn biểu mẫu (cả nhóm,
// tìm), kỳ nhanh đúng ngày, gửi đúng thứ tự đang nhìn; lần xuất Đang chờ → hỏi lại tới Xong → TẢI VỀ; chờ lâu → CHẠY
// NGAY; Lỗi → lý do + LÀM LẠI.
// Nạp code THẬT (view + qcui + dom); modal / toast giả — scripts/fakedom.mjs.
//
// Chạy: node scripts/test-iso.mjs   (verify.sh gọi sẵn)

import { readFileSync } from 'node:fs';
import { E, TOAST, XAC, bang, cho, ketThuc, kiem, napView, tim } from './fakedom.mjs';

const nutCo = (goc, chu) => tim(goc, (e) => e.tagName === 'BUTTON' && e.textContent.includes(chu))[0];
const lien = (goc) => tim(goc, (e) => e.tagName === 'A').map((a) => [a.textContent, a.href]);
const UI = await napView('components/qcui.js');
const ISO = await napView('views/iso.js');
const QC = await napView('views/qc.js');
const X = await napView('views/iso_xuat.js');

console.log('-- đường dẫn màn ISO --');
kiem('#/iso → Tổng quan; #/iso/xuat, /review, /truyxuat; #/iso/bienban/<tên> (giải mã); màn lạ → Tổng quan',
  bang([ISO.tachRoute('#/iso'), ISO.tachRoute('#/iso/xuat'), ISO.tachRoute('#/iso/review?x=1'),
    ISO.tachRoute('#/iso/bienban/BB-2026-0001'), ISO.tachRoute('#/iso/bienban/BB%2F1'), ISO.tachRoute('#/iso/la')],
  [{ man: 'attp', tham_so: null }, { man: 'xuat', tham_so: null }, { man: 'review', tham_so: null },
    { man: 'bienban', tham_so: 'BB-2026-0001' }, { man: 'bienban', tham_so: 'BB/1' }, { man: 'attp', tham_so: null }]));
kiem('màn con dùng LẠI màn sẵn có (một chỗ code) + màn xuất mới', ISO.MAN.attp.endsWith('/qc_attp.js')
  && ISO.MAN.review.endsWith('/qc_review.js') && ISO.MAN.bienban.endsWith('/qc_bienban.js')
  && ISO.MAN.truyxuat.endsWith('/qc_truyxuat.js') && ISO.MAN.xuat.endsWith('/iso_xuat.js'));

console.log('\n-- thanh tab: ISO hay Xem xét cũ theo nơi đang đứng --');
globalThis.window.location = { hash: '#/iso/xuat' };
let t = UI.tabXemXet('xuat');
kiem('trong #/iso: Tổng quan · Xem xét tháng · Báo cáo · Xuất báo cáo · Hồ sơ đánh giá · Biên bản · Truy xuất · Tài liệu',
  bang(lien(t), [['Tổng quan', '#/iso'], ['Xem xét tháng', '#/iso/review'], ['Báo cáo', '#/iso/baocao'],
    ['Xuất báo cáo', '#/iso/xuat'], ['Hồ sơ đánh giá', '#/iso/hoso'], ['Biên bản', '#/iso/bienban'],
    ['Truy xuất', '#/iso/truyxuat'], ['Tài liệu', '#/tailieu/tatca']]) && t.classList.contains('sx-iso-tab'),
  lien(t));
kiem('… tab đang đứng sáng', tim(t, (e) => e.classList && e.classList.contains('sx-qc-seg-on')).map((e) => e.textContent)
  .join() === 'Xuất báo cáo');
globalThis.window.location = { hash: '#/qc/bienban/BB-1' };
t = UI.tabXemXet('bienban');
kiem('đường cũ #/qc/…: thanh Xem xét cũ, link #/qc/…', bang(lien(t).map((x) => x[1]),
  ['#/qc/attp', '#/qc/review', '#/qc/baocao', '#/qc/bienban', '#/qc/hoso', '#/tailieu/tatca'])
  && !t.classList.contains('sx-iso-tab'));
const BB = await napView('views/qc_bienban.js');
globalThis.window.location = { hash: '#/iso/bienban/BB-1' };
kiem('biên bản trong màn ISO: gốc đường dẫn #/iso/bienban (thẻ Chờ tôi ký, quay lại danh sách ở lại màn ISO)',
  BB.goc() === '#/iso/bienban');

console.log('\n-- màn QC: chuyển đường cũ sang #/iso, bỏ tab Xem xét / Truy xuất --');
kiem('đường cũ → đường ISO, giữ màn con, tên biên bản, tham số', bang(['#/qc/attp', '#/qc/review', '#/qc/baocao?thang=2026-09',
  '#/qc/hoso', '#/qc/bienban', '#/qc/bienban/BB-2026-0001', '#/qc/truyxuat', '#/qc', '#/qc/incidents', '#/qc/khacphuc?mo=CAR-1',
  '#/qc/round/QC-1'].map((h) => QC.duongIso(h)), ['#/iso', '#/iso/review', '#/iso/baocao?thang=2026-09', '#/iso/hoso',
  '#/iso/bienban', '#/iso/bienban/BB-2026-0001', '#/iso/truyxuat', null, null, null, null]));
kiem('có màn ISO hay không: theo views của trang (ctx) hoặc boot', QC.coManIso({ ctx: { views: ['iso', 'qc'] } })
  && QC.coManIso({ boot: { views: ['qc', 'iso'] } }) && !QC.coManIso({ ctx: { views: ['qc', 'so'] } }) && !QC.coManIso({}));
let thay = null;
globalThis.window.location = { hash: '#/qc/bienban/BB-2026-0001', replace: (h) => { thay = h; } };
let c = new E('div');
await QC.render({ container: c, call: async () => ({}), ctx: { views: ['iso', 'qc', 'so', 'tailieu'] },
  boot: { la_iso: true } });
kiem('người có màn ISO mở #/qc/bienban/<x> → thay đường (không thêm lịch sử) sang #/iso/bienban/<x>, không vẽ gì',
  thay === '#/iso/bienban/BB-2026-0001' && !c.kids.length, thay);
thay = null;
globalThis.window.location = { hash: '#/qc/bienban/BB-2026-0001', replace: (h) => { thay = h; } };
c = new E('div');
await QC.render({ container: c, call: async () => ({}), ctx: { views: ['qc', 'so', 'tailieu'] }, boot: {} });
kiem('người KHÔNG có màn ISO (QLSX ký biên bản) → vẫn xem trong QC, không chuyển', thay === null && c.kids.length > 0);
globalThis.window.location = { hash: '#/qc', replace: () => {} };
c = new E('div');
await QC.render({ container: c, call: async () => ({}), ctx: { views: ['iso', 'qc'] }, boot: { la_iso: true, views: ['iso', 'qc'] } });
const tabQc = lien(c).map((x) => x[0]);
kiem('màn QC của Trưởng Ban ISO / quản lý: chỉ tab nhập liệu (Hôm nay, Sự cố, Xuất xưởng, Lịch sử) — Xem xét, Truy xuất '
  + 'đã sang màn ISO', bang(tabQc, ['Hôm nay', 'Sự cố', 'Xuất xưởng', 'Lịch sử']), tabQc);
c = new E('div');
await QC.render({ container: c, call: async () => ({}), ctx: { views: ['qc'] }, boot: { la_iso: true } });
kiem('… site chưa có màn ISO trong views (bản cũ) mà là Ban ISO → giữ tab cũ, không mất đường vào',
  lien(c).map((x) => x[0]).includes('Xem xét'));

console.log('\n-- shell, quyền --');
const shell = readFileSync('sx/public/sx/shell.js', 'utf8');
kiem('shell: view iso (đường dẫn, nhãn ISO, tự lo ngày, route #/iso/…)', shell.includes("iso: '/assets/sx/sx/views/iso.js'")
  && shell.includes("iso: { label: 'ISO'") && /VIEW_TU_LO_NGAY = new Set\(\[[^\]]*'iso'/.test(shell)
  && shell.includes("router.registerPrefix('#/iso/'"));
const nhac = readFileSync('sx/public/sx/cards/qcnhac.js', 'utf8');
kiem('thẻ nhắc QC trên màn Quản lý: TỔNG QUAN ATTP mở màn ISO', nhac.includes("['#/iso', 'TỔNG QUAN ATTP']"));

console.log('\n-- màn xuất: kỳ nhanh --');
const H = '2026-10-09';
kiem('kỳ nhanh: tháng này / trước, quý này / trước, 3 / 6 tháng, năm nay / trước', bang(X.KY_NHANH.map(([m]) => X.kyNhanh(m, H)), [
  ['2026-10-01', H], ['2026-09-01', '2026-09-30'], ['2026-10-01', H], ['2026-07-01', '2026-09-30'], ['2026-08-01', H],
  ['2026-05-01', H], ['2026-01-01', H], ['2025-01-01', '2025-12-31']]), X.KY_NHANH.map(([m]) => X.kyNhanh(m, H)));
kiem('qua năm: tháng 1 → tháng trước là 12 năm trước; quý 1 → quý trước là quý 4 năm trước; tháng 2 nhuận',
  bang([X.kyNhanh('thang_truoc', '2026-01-15'), X.kyNhanh('quy_truoc', '2026-02-10'), X.kyNhanh('thang_truoc', '2028-03-05'),
    X.kyNhanh('6thang', '2026-03-31')], [['2025-12-01', '2025-12-31'], ['2025-10-01', '2025-12-31'],
    ['2028-02-01', '2028-02-29'], ['2025-10-01', '2026-03-31']]));

console.log('\n-- màn xuất: chọn biểu mẫu, gửi --');
const DL = {
  tu: '2026-08-01', den: H, hom_nay: H, toi_da_thang: 24,
  nhom: [{ ten: 'Kiểm soát sản xuất', bm: [{ ma: 'BM.08.01', ten: 'Vòng kiểm hằng ngày', ky: 'mỗi tháng một tờ (tờ từng ngày)' },
    { ma: 'BM.08.03', ten: 'Nhật ký cát rang', ky: 'mỗi tháng một tờ' }] },
  { ten: 'Thiết bị đo', bm: [{ ma: 'BM.06.01', ten: 'Danh mục thiết bị', ky: 'danh mục hiện hành' }] }],
  ds: [],
};
const GOI = [];
let traVe = {};
let lai = 0;
const ctx = () => ({
  container: new E('div'),
  lai: () => { lai += 1; },
  call: async (m, a) => {
    GOI.push([m, a]);
    const k = m.split('.').pop();
    if (k in traVe) return typeof traVe[k] === 'function' ? traVe[k](a) : traVe[k];
    return {};
  },
});
let a = ctx();
X.ve(a, DL);
c = a.container;
const o = (ma) => tim(c, (e) => e.dataset && e.dataset.ma === ma)[0];
kiem('kỳ mặc định từ máy chủ (3 tháng); đếm đã chọn 0 / 3; mỗi biểu mẫu nói sẽ ra tờ nào',
  X.st.tu === '2026-08-01' && X.st.den === H && c.chu.includes('đã chọn 0 / 3') && c.chu.includes('mỗi tháng một tờ (tờ từng ngày)'));
const xuatExcel = nutCo(c, 'XUẤT EXCEL');
xuatExcel.bam();
await cho();
kiem('chưa chọn biểu mẫu → báo, không gửi', TOAST.at(-1)[0] === 'Chọn ít nhất một biểu mẫu.' && !GOI.length);
o('BM.08.03').bam();
kiem('bấm một biểu mẫu → chọn (☑), đếm 1 / 3', c.chu.includes('đã chọn 1 / 3') && o('BM.08.03').classList.contains('sx-xbc-on')
  && o('BM.08.03').innerHTML.includes('☑'));
tim(c, (e) => e.tagName === 'BUTTON' && e.textContent.includes('Thiết bị đo'))[0].bam();
kiem('bấm tên nhóm → chọn cả nhóm', X.st.chon.has('BM.06.01'));
tim(c, (e) => e.tagName === 'BUTTON' && e.textContent.includes('Kiểm soát sản xuất'))[0].bam();
kiem('… bấm nhóm còn thiếu → chọn đủ nhóm; bấm lại nhóm đã đủ → bỏ cả nhóm', X.st.chon.size === 3 && (() => {
  tim(c, (e) => e.tagName === 'BUTTON' && e.textContent.includes('Kiểm soát sản xuất'))[0].bam();
  return !X.st.chon.has('BM.08.01') && !X.st.chon.has('BM.08.03') && X.st.chon.has('BM.06.01');
})());
const timO = tim(c, (e) => e.tagName === 'INPUT' && e.type === 'search')[0];
timO.doi('cát');
kiem('tìm "cát" → chỉ hiện Nhật ký cát rang; CHỌN HẾT chỉ chọn cái đang hiện', !o('BM.08.01') && !!o('BM.08.03') && (() => {
  nutCo(c, 'CHỌN HẾT').bam();
  return X.st.chon.has('BM.08.03') && !X.st.chon.has('BM.08.01');
})());
timO.doi('');
o('BM.08.01').bam();
tim(c, (e) => e.tagName === 'BUTTON' && e.textContent.trim() === 'Năm trước')[0].bam();
const ngayO = tim(c, (e) => e.tagName === 'INPUT' && e.type === 'date');
kiem('bấm kỳ nhanh "Năm trước" → hai ô ngày đổi theo', X.st.tu === '2025-01-01' && X.st.den === '2025-12-31'
  && ngayO[0].value === '2025-01-01' && ngayO[1].value === '2025-12-31');
ngayO[0].doi('2026-09-01');
ngayO[1].doi('2026-09-30');
tim(c, (e) => e.tagName === 'INPUT' && e.type === 'text')[0].doi('Đoàn Orion 10/2026');
traVe = { xuat: { name: 'XBC-2026-0001', trang_thai: 'Đang chờ' } };
nutCo(c, 'XUẤT PDF').bam();
await cho();
const g = GOI.filter(([m]) => m.endsWith('.xuat')).at(-1);
const p = g && JSON.parse(g[1].payload);
kiem('XUẤT PDF: gửi kiểu, kỳ, ghi chú, biểu mẫu theo THỨ TỰ trên màn (nhóm, mã) — không theo thứ tự bấm',
  p && bang(p, { kieu: 'PDF', tu: '2026-09-01', den: '2026-09-30', ghi_chu: 'Đoàn Orion 10/2026',
    bieu_mau: ['BM.08.01', 'BM.08.03', 'BM.06.01'] }), p);
kiem('… báo đã gửi, vẽ lại để lần xuất hiện ở danh sách', TOAST.at(-1)[0].includes('XBC-2026-0001') && lai === 1);
X.st.tu = '2026-10-01';
nutCo(c, 'XUẤT EXCEL').bam();
await cho();
kiem('kỳ ngược → báo, không gửi', TOAST.at(-1)[0] === 'Từ ngày phải trước đến ngày.'
  && GOI.filter(([m]) => m.endsWith('.xuat')).length === 1);
X.st.tu = '2026-09-01';

console.log('\n-- các lần xuất: trạng thái, tải, chạy ngay, làm lại, hỏi lại --');
const lanXuat = (k) => ({ name: `XBC-${k.trang_thai}`, kieu: 'Excel', tu: '2026-09-01', den: '2026-09-30', so_bieu_mau: 3,
  ghi_chu: 'Đoàn Orion', nguoi: 'Nguyễn Huy Chiến', creation: '2026-10-10 14:30:00', so_to: 5, kich_thuoc: 20480,
  co_tep: k.trang_thai === 'Xong', ket_qua: [], ...k });
const xong = lanXuat({ trang_thai: 'Xong', ket_qua: [{ ma: 'BM.08.01', so_to: 0, loi: 'division by zero' },
  { ma: 'BM.08.04', so_to: 0, loi: '' }, { ma: 'BM.08.03', so_to: 2, loi: '' }] });
const loi = lanXuat({ trang_thai: 'Lỗi', loi: 'wkhtmltopdf: không có trên máy chủ' });
const chuaChay = lanXuat({ trang_thai: 'Đang chờ' });
X.st.thay = {};
X.st.nhip = 1;
traVe = { trang_thai: () => [{ ...chuaChay, trang_thai: 'Xong', co_tep: true }] };
a = ctx();
X.ve(a, { ...DL, ds: [xong, loi, chuaChay] });
c = a.container;
const theX = tim(c, (e) => e.classList && e.classList.contains('sx-xbc-lan'));
const taiX = tim(theX[0], (e) => e.tagName === 'A')[0];
kiem('Xong: kiểu, kỳ, số biểu mẫu, ghi chú đoàn, người, giờ, số tờ, KB; nút TẢI VỀ (GET tai) ',
  theX[0].chu.includes('Excel · 01/09/2026 – 30/09/2026 · 3 biểu mẫu · Đoàn Orion') && theX[0].chu.includes('Nguyễn Huy Chiến')
  && theX[0].chu.includes('5 tờ · 20 KB') && taiX && taiX.href === '/api/method/sx.api.qc_xuatbc.tai?name=XBC-Xong', theX[0].chu);
kiem('… biểu mẫu in lỗi nói lỗi; biểu mẫu kỳ trống liệt kê', theX[0].chu.includes('BM.08.01: không in được — division by zero')
  && theX[0].chu.includes('Kỳ này không có bản ghi: BM.08.04') && !theX[0].chu.includes('BM.08.03:'));
kiem('Lỗi: lý do + LÀM LẠI, không có TẢI VỀ', theX[1].chu.includes('wkhtmltopdf: không có trên máy chủ')
  && !!nutCo(theX[1], 'LÀM LẠI') && !tim(theX[1], (e) => e.tagName === 'A').length);
kiem('Đang chờ (mới thấy): báo đang chờ hàng đợi, CHƯA có CHẠY NGAY', theX[2].chu.includes('Đang chờ hàng đợi máy chủ')
  && !nutCo(theX[2], 'CHẠY NGAY'));
await new Promise((r) => { setTimeout(r, 20); });
const sau = tim(c, (e) => e.classList && e.classList.contains('sx-xbc-lan'))[2];
kiem('màn tự hỏi lại trạng thái lần đang chờ → Xong thì có TẢI VỀ + báo', GOI.some(([m, x]) => m.endsWith('.trang_thai')
  && JSON.parse(x.names).join() === 'XBC-Đang chờ') && !!tim(sau, (e) => e.tagName === 'A' && e.textContent.includes('TẢI VỀ'))[0]
  && TOAST.some(([s]) => s.includes('XBC-Đang chờ xong')));
const nGoi = GOI.filter(([m]) => m.endsWith('.trang_thai')).length;
await new Promise((r) => { setTimeout(r, 20); });
kiem('… hết lần đang chờ thì thôi hỏi', GOI.filter(([m]) => m.endsWith('.trang_thai')).length === nGoi);
X.st.thay = { 'XBC-Đang chờ': Date.now() - (X.CHO_LAU + 1) * 1000 };
const o2 = new E('div');
X.veThe(a, o2, chuaChay);
kiem('chờ quá 20 giây → CHẠY NGAY', !!nutCo(o2, 'CHẠY NGAY'));
traVe = { chay_ngay: { ...chuaChay, trang_thai: 'Xong', co_tep: true } };
nutCo(o2, 'CHẠY NGAY').bam();
await cho();
kiem('… bấm CHẠY NGAY → gọi chay_ngay, thẻ đổi sang Xong có TẢI VỀ', GOI.at(-1)[0].endsWith('.chay_ngay')
  && GOI.at(-1)[1].name === 'XBC-Đang chờ' && !!tim(o2, (e) => e.tagName === 'A')[0]);
const dangTao = new E('div');
X.veThe(a, dangTao, lanXuat({ trang_thai: 'Đang tạo' }));
kiem('Đang tạo: không có XOÁ (máy chủ cũng chặn)', dangTao.chu.includes('đang dựng tệp') && !nutCo(dangTao, 'XOÁ'));
nutCo(theX[1], 'LÀM LẠI').bam();
await cho();
kiem('LÀM LẠI → gọi lam_lai, vẽ lại', GOI.at(-1)[0].endsWith('.lam_lai') && lai === 2);
nutCo(theX[0], 'XOÁ').bam();
const xac = XAC.at(-1);
kiem('XOÁ hỏi xác nhận, nói rõ xoá cả tệp', xac && xac.title.includes('XBC-Xong') && xac.message.includes('Xoá cả tệp'));
await xac.onConfirm();
kiem('… xác nhận → gọi xoa', GOI.at(-1)[0].endsWith('.xoa') && GOI.at(-1)[1].name === 'XBC-Xong');
X.st.nhip = 0;

ketThuc('ISO-JS');
