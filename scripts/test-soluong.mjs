// Kiểm openSoLuong() giữ đúng TỔNG khi bảng quy đổi ĐVT đổi sau lúc ghi phiếu.
//
// Vì sao phải có bài này: cửa sổ nhập dựng ô TỪ `chi_tiet` và bỏ qua `tong` khi
// chi_tiet không rỗng, lại lọc bỏ IM LẶNG bậc ĐVT không còn trong bảng quy đổi. Đổi
// tên "Thùng" thành "Két" là "21 thùng 3 hộp" thành "3 hộp" — 252 hộp bốc hơi thẳng
// vào sổ kho, không một dòng cảnh báo. Đã dính thật ở D72, phát hiện ở D75.
//
// Chạy: node scripts/test-soluong.mjs   (verify.sh gọi sẵn)
//
// Nạp hàm THẬT từ file nguồn: bỏ dòng import, bỏ từ khoá export, rồi dựng lại bằng
// new Function với vài stub DOM tối thiểu. Chép logic ra đây rồi test bản chép là
// test chính mình, không phải test code chạy trên máy công nhân.

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const goc = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const nguon = path.join(goc, 'sx/public/sx/components/soluong.js');

class E {
  constructor(t = 'div', c = '') { this.tag = t; this.className = c; this.kids = []; this.innerHTML = ''; }
  appendChild(x) { this.kids.push(x); return x; }
  addEventListener() {}
  querySelectorAll() { return []; }
}

const stub = {
  el: (t, c) => new E(t, c),
  esc: (s) => String(s == null ? '' : s),
  formatNumber: (n) => String(n),
  openModal: () => ({ body: new E('div', 'body'), close() {} }),
  openNumpad: (o) => { stub._numpad = o; return o; },
};

const src = fs.readFileSync(nguon, 'utf8')
  .replace(/^import .*?;$/gm, '')
  .replace(/^export /gm, '');
const nap = new Function('el', 'esc', 'openModal', 'openNumpad', 'formatNumber',
  `${src}\nreturn { openSoLuong, tachUom, moTaUom };`);
const { openSoLuong } = nap(stub.el, stub.esc, stub.openModal, stub.openNumpad, stub.formatNumber);

let hong = 0;
function ca(ten, arg, mong) {
  stub._numpad = null;
  const m = openSoLuong({ ...arg, onOk: () => {} });
  const than = m.body ? m.body.kids : [];
  const hopTong = than.find((k) => k.className === 'sx-sl-tong');
  const canh = !!than.find((k) => k.className === 'sx-warn-text');
  const so = hopTong
    ? Number((String(hopTong.innerHTML).match(/<b>([\d.]+)/) || [])[1])
    : Number((stub._numpad || {}).initial);
  const ok = Math.abs(so - mong.tong) < 1e-6 && canh === !!mong.canh;
  if (!ok) hong++;
  console.log(`  ${ok ? 'ok  ' : 'HỎNG'} ${ten}: tổng ${so} (mong ${mong.tong}), `
    + `cảnh báo ${canh} (mong ${!!mong.canh})`);
}

const UOMS = [{ uom: 'Thùng', he_so: 12 }, { uom: 'Hộp', he_so: 1 }];
const CT = [{ uom: 'Thùng', sl: 21, he_so: 12 }, { uom: 'Hộp', sl: 3, he_so: 1 }];

ca('chi tiết khớp bảng quy đổi', { uoms: UOMS, chi_tiet: CT, tong: 255 },
  { tong: 255, canh: false });
ca('không có chi tiết -> tự chia thùng/hộp', { uoms: UOMS, chi_tiet: null, tong: 255 },
  { tong: 255, canh: false });
ca('ĐVT bị đổi tên (Thùng -> Két)',
  { uoms: [{ uom: 'Két', he_so: 12 }, { uom: 'Hộp', he_so: 1 }], chi_tiet: CT, tong: 255 },
  { tong: 255, canh: true });
ca('hệ số bị sửa (12 -> 10)',
  { uoms: [{ uom: 'Thùng', he_so: 10 }, { uom: 'Hộp', he_so: 1 }], chi_tiet: CT, tong: 255 },
  { tong: 255, canh: true });
ca('xoá hẳn bậc Thùng (còn một ĐVT)',
  { uoms: [{ uom: 'Hộp', he_so: 1 }], chi_tiet: CT, tong: 255 },
  { tong: 255, canh: false });
ca('dòng mới, chưa có gì', { uoms: UOMS, chi_tiet: null, tong: 0 },
  { tong: 0, canh: false });

console.log(hong ? `SOLUONG-FAIL (${hong} ca)` : 'SOLUONG-OK');
process.exit(hong ? 1 : 0);
