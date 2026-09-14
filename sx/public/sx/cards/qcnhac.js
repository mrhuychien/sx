// Card "QC đang treo việc gì" trên màn Quản lý (#/quanly).
//
// Cùng một danh sách với hộp nhắc trong màn QC, cố ý: quản lý và QC phải nhìn
// thấy ĐÚNG MỘT bản. Hai bản khác nhau là cách sinh ra cuộc cãi nhau "tôi có
// thấy gì đâu" — và người thua luôn là tờ hồ sơ.
//
// Không có việc treo thì card TỰ ẨN. Một thẻ "mọi thứ ổn" nằm trên đầu dashboard
// mỗi ngày sẽ dạy mắt bỏ qua đúng vùng đó, rồi hôm có việc thật cũng bỏ qua nốt.

import { el } from '/assets/sx/sx/lib/dom.js';
import { veNhac } from '/assets/sx/sx/components/qcui.js';

export async function render({ container, call }) {
  container.className = 'sx-card';
  container.style.display = 'none';
  let nh = null;
  try {
    nh = await call('sx.api.qc.nhac');
  } catch (e) {
    // Chưa migrate module QC / chưa có quyền: im lặng ẩn card, đừng làm hỏng
    // cả màn Quản lý vì một khối phụ.
    return;
  }
  const hop = veNhac((nh && nh.ds) || [], { tieu_de: 'QC đang treo việc' });
  if (!hop) return;
  container.style.display = '';
  container.appendChild(hop);
  const a = el('a', 'sx-btn sx-btn-ghost', 'MỞ MÀN QC');
  a.href = '#/qc';
  a.style.cssText = 'display:block;text-align:center;text-decoration:none;margin-top:var(--sx-s3)';
  container.appendChild(a);
}
