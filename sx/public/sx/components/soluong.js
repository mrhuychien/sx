// Nhập số lượng theo NHIỀU ĐƠN VỊ (D65) — "2 thùng 3 hộp", không phải "27 hộp".
//
// Thủ kho đếm theo cách hàng XẾP ngoài kho: đếm thùng trước, lẻ ra bao nhiêu hộp thì
// đếm hộp. Bắt quy đổi trong đầu là chỗ sinh lỗi, mà lỗi ở đây là lệch tồn kho thật.
// App nhân hệ số, người chỉ việc đọc số mình đếm được.
//
// Item chỉ có MỘT đơn vị thì không mở cửa sổ này — rơi thẳng về bàn số một ô, đỡ
// một bước cho phần lớn trường hợp.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';

/**
 * openSoLuong({ ten, kicker, uoms, chi_tiet, tong, onOk })
 *   uoms:     [{uom, he_so}] — hệ số quy về đơn vị kho, đã sắp giảm dần
 *   chi_tiet: [{uom, sl, he_so}] đang có (sửa lại)
 *   onOk(tong, chi_tiet)
 */
export function openSoLuong({ ten, kicker = '', uoms, chi_tiet, tong = 0, onOk }) {
  const ds = (uoms || []).filter((u) => u && u.uom);
  const goc = ds.length ? ds[ds.length - 1] : null;   // đơn vị kho = hệ số nhỏ nhất

  // Một đơn vị thì khỏi bày cửa sổ nhiều dòng
  if (ds.length <= 1) {
    return openNumpad({
      kicker, title: ten, unitLabel: goc ? goc.uom : 'Số lượng', initial: tong,
      onOk: (v) => onOk(Math.max(0, v), null),
    });
  }

  const so = {};
  ds.forEach((u) => { so[u.uom] = 0; });
  (chi_tiet || []).forEach((c) => {
    if (c && c.uom && so[c.uom] !== undefined) so[c.uom] = Number(c.sl) || 0;
  });
  // Chưa có chi tiết mà đã có tổng (số từ bảng vào hộp, hoặc dòng cũ) -> TỰ ĐỔI ra
  // thùng + hộp. Đưa 255 hộp cho người đang đứng đếm thùng là bắt họ chia nhẩm; chia
  // sẵn thì họ chỉ việc soát lại. Vẫn sửa được từng ô, và tổng không đổi.
  if (!(chi_tiet || []).length && tong > 0 && goc) {
    const tach = tachUom(tong, ds);
    if (tach) tach.forEach((c) => { so[c.uom] = c.sl; });
    else so[goc.uom] = tong;
  }

  const m = openModal({ kicker, title: ten });
  const hang = el('div', 'sx-sl-hang');
  const tongBox = el('div', 'sx-sl-tong');
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big');
  ok.type = 'button';
  ok.textContent = 'LƯU';

  const tinhTong = () => ds.reduce((a, u) => a + so[u.uom] * (Number(u.he_so) || 1), 0);

  function ve() {
    hang.innerHTML = ds.map((u, i) => `
      <button type="button" class="sx-sl-o${so[u.uom] ? ' sx-sl-o-co' : ''}" data-i="${i}">
        <span class="sx-sl-ten">${esc(u.uom)}${
      Number(u.he_so) > 1 && goc
        ? ` <i>= ${formatNumber(u.he_so)} ${esc(goc.uom)}</i>` : ''}</span>
        <span class="sx-sl-so">${formatNumber(so[u.uom])}</span>
      </button>`).join('');
    hang.querySelectorAll('[data-i]').forEach((b) => {
      const u = ds[Number(b.dataset.i)];
      b.addEventListener('click', () => openNumpad({
        kicker: ten, title: u.uom, unitLabel: `Số ${u.uom.toLowerCase()}`,
        initial: so[u.uom],
        hint: (n) => (Number(u.he_so) > 1 && goc
          ? `= ${formatNumber(n * u.he_so)} ${goc.uom}` : ''),
        onOk: (v) => { so[u.uom] = Math.max(0, Math.round(v)); ve(); },
      }));
    });
    const t = tinhTong();
    tongBox.innerHTML = `<span class="sx-field-label">Tổng</span>`
      + `<b>${formatNumber(t)} ${esc(goc ? goc.uom : '')}</b>`;
  }
  ve();

  ok.addEventListener('click', () => {
    const ct = ds
      .filter((u) => so[u.uom] > 0)
      .map((u) => ({ uom: u.uom, sl: so[u.uom], he_so: Number(u.he_so) || 1 }));
    m.close();
    onOk(tinhTong(), ct.length ? ct : null);
  });

  m.body.appendChild(hang);
  m.body.appendChild(tongBox);
  m.body.appendChild(ok);
  return m;
}

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
