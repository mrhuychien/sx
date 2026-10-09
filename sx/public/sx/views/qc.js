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
  luumau: '/assets/sx/sx/views/qc_luumau.js',
  // W08 (D137): kiểm tra xuất xưởng BM.08.04 — tab Xuất xưởng, cùng chỗ với Lưu mẫu.
  xuatxuong: '/assets/sx/sx/views/qc_xuatxuong.js',
  // W13 (D135): sổ khiếu nại BM.11.01 — nằm trong tab Sự cố (hai nút trên đầu).
  khieunai: '/assets/sx/sx/views/qc_khieunai.js',
  // W06 (D132): Ban ISO diễn tập truy xuất ngay trong màn QC.
  truyxuat: '/assets/sx/sx/views/qc_truyxuat.js',
  // W15 (D140): động vật gây hại theo trạm — nút ở cuối Hôm nay; #/qc/dvgh/R05 là URL trên
  // tem QR tại trạm.
  dvgh: '/assets/sx/sx/views/qc_dvgh.js',
  // W20 (D141): nhật ký cát rang BM.08.03 — nút ở cuối Hôm nay, cạnh động vật gây hại.
  cat: '/assets/sx/sx/views/qc_cat.js',
  // W17 (D143): thiết bị đo, hiệu chuẩn BM.06.01–06.04.
  thietbi: '/assets/sx/sx/views/qc_thietbi.js',
};

// Sổ mở từ lưới nút cuối màn Hôm nay — tab "Hôm nay" sáng khi đang ở các màn này.
const SO_HOM_NAY = ['dvgh', 'cat', 'thietbi'];

// Ngày đang xem của riêng màn QC (thanh ngày chung của shell bị giấu ở màn này).
// null = hôm nay. Giữ ngoài hàm render để đổi tab không mất ngày đang xem.
export const st = { ngay: null };

function tachRoute() {
  const h = (window.location.hash || '#/qc').split('?')[0];
  const phan = h.replace('#/qc', '').split('/').filter(Boolean);
  if (!phan.length) return { man: 'home', tham_so: null };
  if (phan[0] === 'round' || phan[0] === 'dvgh') return { man: phan[0], tham_so: phan[1] || null };
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
  // W08 (D137): tab "Lưu mẫu" thành "Xuất xưởng" — bên trong hai nút Kiểm xuất xưởng
  // (BM.08.04) / Lưu mẫu. Thêm tab thứ năm là thanh tab gãy dòng trên điện thoại.
  const tabs = [['home', 'Hôm nay'], ['incidents', 'Sự cố'], ['xuatxuong', 'Xuất xưởng'],
    ['history', 'Lịch sử']];
  // Tab "Xem xét" chỉ hiện với người duyệt. Ẩn nút KHÔNG phải là chốt quyền —
  // chốt thật nằm ở _guard_manager trong sx/api/qc.py; đây chỉ để đỡ rối mắt.
  // `la_iso` (D132): Trưởng Ban ISO hoặc quản lý — trước đây chỉ quản lý thấy tab
  // này, Ban ISO (người xem xét thật) phải tự gõ địa chỉ.
  if (api.boot && (api.boot.la_iso || api.boot.is_quan_ly)) {
    tabs.push(['review', 'Xem xét']);
    tabs.push(['truyxuat', 'Truy xuất']);
  }
  const box = el('div', 'sx-qc-seg');
  tabs.forEach(([ma, ten]) => {
    const a = el('a', 'sx-qc-tab', ten);
    a.href = ma === 'home' ? '#/qc' : `#/qc/${ma}`;
    const on = ma === dang || (ma === 'incidents' && dang === 'khieunai')
      || (ma === 'xuatxuong' && dang === 'luumau') || (ma === 'home' && SO_HOM_NAY.includes(dang));
    a.className = `sx-qc-tab${on ? ' sx-qc-seg-on' : ''}`;
    box.appendChild(a);
  });
  return box;
}
