// View QC (#/qc) — cửa vào của module QC, tự dựng 5 màn con.
//
// Vì sao một view lo cả 5: shell chỉ biết "tab QC", còn #/qc/round/:name là màn
// toàn trang của cùng một việc. Tách thành 5 tab dưới đáy thì QC đứng giữa xưởng
// phải học một thanh điều hướng thứ hai, mà việc của họ chỉ có một: đi một lượt.

import { el } from '/assets/sx/sx/lib/dom.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';

const MAN = {
  home: '/assets/sx/sx/views/qc_home.js',
  round: '/assets/sx/sx/views/qc_round.js',
  incidents: '/assets/sx/sx/views/qc_incidents.js',
  history: '/assets/sx/sx/views/qc_history.js',
  review: '/assets/sx/sx/views/qc_review.js',
};

// Ngày đang xem của riêng màn QC (thanh ngày chung của shell bị giấu ở màn này).
// null = hôm nay. Giữ ngoài hàm render để đổi tab không mất ngày đang xem.
export const st = { ngay: null };

function tachRoute() {
  const h = (window.location.hash || '#/qc').split('?')[0];
  const phan = h.replace('#/qc', '').split('/').filter(Boolean);
  if (!phan.length) return { man: 'home', tham_so: null };
  if (phan[0] === 'round') return { man: 'round', tham_so: phan[1] || null };
  return { man: MAN[phan[0]] ? phan[0] : 'home', tham_so: null };
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '';
  const { man, tham_so } = tachRoute();
  const wrap = el('div', 'sx-qc');
  container.appendChild(wrap);

  // Màn làm lượt là màn TOÀN TRANG: không có thanh tab phía trên, vì mọi giây ở
  // đó là để chấm mục, không phải để đi chỗ khác. Thoát bằng nút ✕ trên đầu.
  if (man !== 'round') wrap.appendChild(veTab(man, api));

  const noiDung = el('div', 'sx-qc-than');
  wrap.appendChild(noiDung);
  try {
    const mod = await import(`${MAN[man]}?v=${encodeURIComponent(
      (api.ctx && api.ctx.assetVersion) || Date.now())}`);
    await mod.render({ ...api, container: noiDung, call, st, tham_so });
  } catch (e) {
    noiDung.innerHTML = '';
    const box = el('div', 'sx-error-box');
    box.textContent = e.message || 'Không mở được màn hình QC.';
    noiDung.appendChild(box);
    toastErr(e.message || 'Không mở được màn hình QC.');
  }
}

function veTab(dang, api) {
  const tabs = [['home', 'Hôm nay'], ['incidents', 'Sự cố'], ['history', 'Lịch sử']];
  // Tab "Xem xét" chỉ hiện với người duyệt. Ẩn nút KHÔNG phải là chốt quyền —
  // chốt thật nằm ở _guard_manager trong sx/api/qc.py; đây chỉ để đỡ rối mắt.
  if (api.boot && api.boot.is_quan_ly) tabs.push(['review', 'Xem xét']);
  const box = el('div', 'sx-qc-seg');
  tabs.forEach(([ma, ten]) => {
    const a = el('a', 'sx-qc-tab', ten);
    a.href = ma === 'home' ? '#/qc' : `#/qc/${ma}`;
    a.className = `sx-qc-tab${ma === dang ? ' sx-qc-seg-on' : ''}`;
    box.appendChild(a);
  });
  return box;
}
