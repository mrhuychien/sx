// Số lượng theo NHIỀU ĐƠN VỊ (D65) — "2 thùng 3 hộp", không phải "27 hộp".
//
// Thủ kho đếm theo cách hàng XẾP ngoài kho: đếm thùng trước, lẻ ra bao nhiêu hộp thì
// đếm hộp. Bắt quy đổi trong đầu là chỗ sinh lỗi, mà lỗi ở đây là lệch tồn kho thật.
// App nhân hệ số, người chỉ việc đọc số mình đếm được.
//
// Bàn số nhập thùng / hộp là moSoHsd (cards/nhapkhotp.js, D153): một màn có tab đơn
// vị + HSD, dùng chung cho Nhập kho và Vào hộp Tết. File này giữ hai hàm thuần đọc /
// chia số theo đơn vị.

import { formatNumber } from '/assets/sx/sx/lib/format.js';

/** "2 thùng + 3 hộp" từ chi tiết ĐVT; rỗng thì trả ''. */
export function moTaUom(chi_tiet) {
  if (!chi_tiet || !chi_tiet.length) return '';
  return chi_tiet.map((c) => `${formatNumber(c.sl)} ${c.uom.toLowerCase()}`).join(' + ');
}

/**
 * Đổi một TỔNG theo đơn vị kho ra bậc đơn vị lớn trước: 255 hộp -> 21 thùng 3 hộp.
 *
 * Trả null khi không chia khớp tuyệt đối (hệ số lẻ, làm tròn lệch). Thà không chia
 * còn hơn chia ra một tổng khác tổng ban đầu — số này đi thẳng vào tồn kho.
 *
 * @param {number} tong  theo đơn vị kho (hệ số nhỏ nhất)
 * @param {{uom:string,he_so:number}[]} uoms  đã sắp hệ số giảm dần
 */
export function tachUom(tong, uoms) {
  const ds = (uoms || []).filter((u) => u && u.uom && Number(u.he_so) > 0);
  if (ds.length <= 1 || !(tong > 0)) return null;
  const bac = ds.slice().sort((a, b) => Number(b.he_so) - Number(a.he_so));
  const ra = [];
  let con = tong;
  bac.forEach((u, i) => {
    const h = Number(u.he_so);
    // Bậc nhỏ nhất ôm phần dư; các bậc trên chỉ lấy phần chia chẵn.
    const sl = i === bac.length - 1
      ? Math.round(con / h)
      : Math.floor(con / h + 1e-9);
    if (sl > 0) ra.push({ uom: u.uom, sl, he_so: h });
    con -= sl * h;
  });
  const lai = ra.reduce((a, c) => a + c.sl * c.he_so, 0);
  return Math.abs(lai - tong) < 1e-6 ? ra : null;
}
