// #/qc/attp — Tổng quan ATTP (W22, D148): một màn cho Trưởng Ban ISO, Giám đốc.
//
// Mỗi mảng hồ sơ một thẻ: đèn Đỏ / Vàng / Xanh, con số chính, vài dòng số liệu, các việc đang
// treo của mảng đó; bấm thẻ sang đúng màn để làm. Thẻ đỏ lên đầu. Đèn suy từ chính hộp nhắc
// (sx/qc/attp.py) — tổng quan và hộp nhắc không bao giờ nói hai điều khác nhau.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { khungTrong, tabXemXet } from '/assets/sx/sx/components/qcui.js';

const TEN_DEN = { do: 'Đỏ', vang: 'Vàng', xanh: 'Xanh' };
const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  let dl;
  try {
    dl = await call('sx.api.qc_attp.tong_quan', {});
  } catch (e) {
    container.innerHTML = '';
    container.appendChild(tabXemXet('attp'));
    container.appendChild(khungTrong(e.message));
    return;
  }
  container.innerHTML = '';
  container.appendChild(tabXemXet('attp'));

  const dau = el('div', 'sx-qc-top');
  dau.appendChild(el('div', null, `<div class="sx-qc-ngay">Tổng quan ATTP · ${esc(ngayDu(dl.ngay))}</div>
    <div class="sx-qc-ai">Số liệu ${dl.so_ngay} ngày (${esc(ngayDu(dl.tu))} – ${esc(ngayDu(dl.den))});
    việc đang treo tính tới hôm nay.</div>`));
  container.appendChild(dau);

  const dem = el('div', 'sx-attp-dem');
  ['do', 'vang', 'xanh'].forEach((k) => {
    dem.appendChild(el('span', `sx-attp-dem-o sx-attp-${k}`,
      `<span class="sx-attp-cham" aria-hidden="true"></span><b>${dl.dem[k]}</b> ${TEN_DEN[k]}`));
  });
  container.appendChild(dem);

  const luoi = el('div', 'sx-attp-luoi');
  dl.linh_vuc.forEach((x) => {
    const a = el('a', `sx-attp-the sx-attp-${x.den}`);
    a.href = x.route;
    a.setAttribute('aria-label', `${x.ten}: đèn ${TEN_DEN[x.den]}`);
    a.innerHTML = `<div class="sx-attp-the-dau">
        <span class="sx-attp-cham" aria-hidden="true"></span>
        <span class="sx-attp-ten">${esc(x.ten)}</span>
        <span class="sx-attp-bm">${esc(x.bieu_mau)}</span>
      </div>
      <div class="sx-attp-so"><b>${esc(x.so)}</b> <span>${esc(x.nhan_so)}</span></div>
      ${x.dong.map((d) => `<div class="sx-attp-dong">${esc(d)}</div>`).join('')}
      ${x.nhac.map((n) => `<div class="sx-attp-viec sx-attp-viec-${n.muc_do === 'cao' ? 'cao' : 'thuong'}"
        title="${esc(n.chi_tiet)}">${esc(n.tieu_de)}</div>`).join('')}`;
    luoi.appendChild(a);
  });
  container.appendChild(luoi);
  container.appendChild(el('div', 'sx-qc-goiy',
    'Đỏ = có việc mức cao (quá hạn, chưa xử lý, lô đang thu hồi…) · Vàng = có việc đang treo · '
    + 'Xanh = không có gì treo. Cùng luật với hộp nhắc màn Hôm nay.'));
}
