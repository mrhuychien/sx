// Card Chốt ngày — modal 2 bước → chot_ngay; hiện cảnh báo mềm nếu có.

import { esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';

export async function render({ container, boot, call, ensureNgay, reload }) {
  container.className = 'sx-card';
  const ngay = boot.ngay_sx;
  if (ngay && ngay.docstatus === 1) {
    container.innerHTML = '<div class="sx-card-center">✅ Ngày đã chốt. Kho + lương sản phẩm đã ghi nhận.</div>';
    return;
  }
  container.innerHTML = '<button type="button" class="sx-btn sx-btn-danger sx-btn-big" id="sx-chot">CHỐT NGÀY</button>';
  container.querySelector('#sx-chot').addEventListener('click', async () => {
    const ng = await ensureNgay();
    confirm2Step({
      title: 'Chốt ngày sản xuất',
      message: 'Chốt ngày sẽ sinh chứng từ kho (mẻ trộn + thành phẩm), tính lương '
        + 'sản phẩm và KHOÁ phiếu. Kiểm tra: báo mẻ, báo cán, bảng vào hộp.',
      confirmLabel: 'CHỐT NGÀY',
      onConfirm: async () => {
        try {
          const r = await call('sx.api.chot.chot_ngay', { ngay_sx: ng.name });
          if (r.canh_bao && r.canh_bao.length) {
            showCanhBao(r, reload);
          } else {
            toast(`Đã chốt ngày — ${formatNumber(r.tong_hop_tp)} hộp.`);
            reload();
          }
        } catch (e) {
          toastErr(e.message);
          throw e;
        }
      },
    });
  });
}

function showCanhBao(r, reload) {
  const m = openModal({ title: '✅ Đã chốt — có cảnh báo' });
  m.body.innerHTML = `
    <div class="sx-modal-msg">Đã chốt ${formatNumber(r.tong_hop_tp)} hộp. Lưu ý:</div>
    ${r.canh_bao.map((c) => `<div class="sx-warn-text">⚠ ${esc(c)}</div>`).join('')}
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-cb-ok">ĐÃ HIỂU</button>
  `;
  m.body.querySelector('#sx-cb-ok').addEventListener('click', () => { m.close(); reload(); });
}
