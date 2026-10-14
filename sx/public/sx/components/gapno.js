// Thẻ sổ nợ GẬP sẵn (D208) — dùng chung cho Sổ nợ BOM, Sổ nợ đơn giá, Nợ vào hộp.
//
// Mỗi thẻ nợ là một danh sách dài (mỗi mã một khối, mỗi lần nhập một dòng); ba thẻ liền nhau ở màn
// Quản lý đẩy lịch chốt, truy xuất xuống cuối màn. Gập thành MỘT dòng: tên sổ + số mã + một dòng nhắc
// (việc làm được ngay / nợ quá lâu / cũ nhất bao lâu) — bấm mới xổ danh sách. <details> gốc như hộp
// nhắc QC (D186): không cần JS, bàn phím và trình đọc màn hình hiểu sẵn.
//
// Vẽ lại sau một thao tác trong thẻ (Bỏ qua, Hạch toán bù, Áp giá) GIỮ nguyên đang mở: đang làm dở
// mà thẻ tự gập là mất chỗ. Mở lại màn / tải lại trang thì gập như mặc định.

import { el, esc } from '/assets/sx/sx/lib/dom.js';

/** Dựng khung gập trong `container` (xoá nội dung cũ), trả phần thân để thẻ vẽ danh sách vào.
 * nhac: [{ chu, loai: 'lam' (làm được ngay) | 'gap' (nợ quá lâu) | không có }] — mục rỗng / 0 bị bỏ.
 * mo: true = mở sẵn; không truyền = giữ như khung đang có (lần đầu: gập). */
export function khungNo(container, tieuDe, nhac = [], mo = null) {
  const cu = container.firstElementChild;
  const box = el('details', 'sx-no-gap');
  box.open = mo == null ? !!(cu && cu.tagName === 'DETAILS' && cu.open) : !!mo;
  const ds = nhac.filter((x) => x && x.chu);
  box.appendChild(el('summary', 'sx-no-tom', `<span class="sx-field-label">${esc(tieuDe)}</span>${ds.length
    ? `<span class="sx-no-nhac">${ds.map((x) => `<span${x.loai ? ` class="sx-no-nhac-${x.loai}"` : ''}>${
      esc(x.chu)}</span>`).join(' · ')}</span>` : ''}`));
  const than = el('div', 'sx-no-than');
  box.appendChild(than);
  container.innerHTML = '';
  container.appendChild(box);
  return than;
}

/** Dòng nhắc "cũ nhất N ngày" của cả sổ (so_ngay = tuổi khoản nợ cũ nhất của từng mã). */
export function cuNhat(nhom) {
  const n = Math.max(0, ...nhom.map((g) => Number(g.so_ngay) || 0));
  return { chu: n ? `cũ nhất ${n} ngày` : 'từ hôm nay' };
}
