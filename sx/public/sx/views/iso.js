// View ISO (#/iso) — màn riêng của Trưởng Ban ISO (D176), tách khỏi màn QC: màn QC giữ việc NHẬP LIỆU của QC
// (lượt kiểm, sự cố, xuất xưởng, sổ…); việc xem xét, báo cáo, hồ sơ cho đoàn sang đây.
//
//   #/iso                 Tổng quan ATTP — đèn từng mảng, việc đang treo           views/qc_attp.js
//   #/iso/review          Xem xét tháng — lưới tháng, KPI, đã xem xét đến ngày      views/qc_review.js
//   #/iso/baocao          Báo cáo tháng BM.01.12, chỉ tiêu ATTP                    views/qc_baocao.js
//   #/iso/xuat            Xuất báo cáo cho đoàn: biểu mẫu + kỳ → Excel / PDF        views/iso_xuat.js
//   #/iso/hoso            Hồ sơ đánh giá — danh mục BM.01.04, gói zip               views/qc_hoso.js
//   #/iso/bienban[/<tên>] Biên bản — họp Ban ISO, xem xét lãnh đạo, ĐGNB, thẩm tra…  views/qc_bienban.js
//   #/iso/truyxuat        Diễn tập truy xuất BM.02.04 (thẻ Truy xuất của Quản lý)    views/qc_truyxuat.js
// Thanh tab do từng màn tự vẽ (qcui.tabXemXet thấy đang đứng ở #/iso thì vẽ tab ISO); tab "Tài liệu" sang thư viện
// (#/tailieu/tatca) — một thư viện chung cho mọi vai, không chép sang đây.
// Đường cũ #/qc/attp, #/qc/review… (hộp nhắc, thẻ Tổng quan, trang đã đánh dấu) → views/qc.js chuyển sang đây.

import { el } from '/assets/sx/sx/lib/dom.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';
import { tabXemXet } from '/assets/sx/sx/components/qcui.js';

export const MAN = {
  attp: '/assets/sx/sx/views/qc_attp.js',
  review: '/assets/sx/sx/views/qc_review.js',
  baocao: '/assets/sx/sx/views/qc_baocao.js',
  xuat: '/assets/sx/sx/views/iso_xuat.js',
  hoso: '/assets/sx/sx/views/qc_hoso.js',
  bienban: '/assets/sx/sx/views/qc_bienban.js',
  truyxuat: '/assets/sx/sx/views/qc_truyxuat.js',
};
// Màn tự vẽ thanh tab ở đầu. Truy xuất là nguyên thẻ của màn Quản lý — view này vẽ tab giùm.
const TU_VE_TAB = new Set(['attp', 'review', 'baocao', 'xuat', 'hoso', 'bienban']);

// Ngày đang xem của riêng màn này (thanh ngày chung của shell bị giấu ở đây), như st của màn QC.
export const st = { ngay: null };

export function tachRoute(hash) {
  const h = String(hash || '#/iso').split('?')[0];
  const phan = h.replace(/^#\/iso/, '').split('/').filter(Boolean);
  if (!phan.length) return { man: 'attp', tham_so: null };
  if (phan[0] === 'bienban') return { man: 'bienban', tham_so: phan[1] ? decodeURIComponent(phan[1]) : null };
  return { man: MAN[phan[0]] ? phan[0] : 'attp', tham_so: null };
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '';
  const { man, tham_so } = tachRoute(window.location.hash);
  const wrap = el('div', 'sx-qc sx-iso');
  container.appendChild(wrap);
  if (!TU_VE_TAB.has(man)) wrap.appendChild(tabXemXet(man));
  const noiDung = el('div', 'sx-qc-than');
  wrap.appendChild(noiDung);
  try {
    const mod = await import(`${MAN[man]}?v=${encodeURIComponent(
      (api.ctx && api.ctx.assetVersion) || Date.now())}`);
    await mod.render({ ...api, container: noiDung, call, st, tham_so });
  } catch (e) {
    noiDung.innerHTML = '';
    const box = el('div', 'sx-error-box');
    box.textContent = e.message || 'Không mở được màn hình ISO.';
    noiDung.appendChild(box);
    toastErr(e.message || 'Không mở được màn hình ISO.');
  }
}
