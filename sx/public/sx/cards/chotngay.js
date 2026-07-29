// Card Chốt ngày — modal 2 bước → chot_ngay; hiện cảnh báo mềm nếu có.

import { esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';

export async function render({ container, boot, call, ensureNgay, refresh }) {
  container.className = 'sx-card';
  const ngay = boot.ngay_sx;
  if (ngay && ngay.docstatus === 1) {
    container.innerHTML = `
      <div class="sx-card-center">✅ Ngày đã chốt. Kho + lương khoán đã ghi nhận.</div>
      <div class="sx-muted">Cần sửa số liệu thì phải huỷ chốt trước — huỷ xong số liệu cũ
        giữ nguyên để sửa, kho và lương khoán được hoàn lại.</div>
      <button type="button" class="sx-btn sx-btn-danger sx-btn-big" id="sx-huy">HUỶ CHỐT NGÀY ĐỂ SỬA</button>
    `;
    container.querySelector('#sx-huy').addEventListener('click', () => {
      confirm2Step({
        title: 'Huỷ chốt ngày ' + (ngay.ngay || ''),
        message: 'Huỷ chốt sẽ THU HỒI toàn bộ chứng từ kho của ngày này (lệnh SX + phiếu '
          + 'nhập/xuất kho + phiếu nhập bột) và GỠ dòng lương khoán của ngày này khỏi phiếu '
          + 'lương tháng. Báo mẻ / báo cán / bảng vào hộp được giữ nguyên để bạn sửa, '
          + 'sửa xong phải CHỐT LẠI thì kho và lương mới được ghi lại.',
        confirmLabel: 'HUỶ CHỐT',
        onConfirm: async () => {
          try {
            await call('sx.api.chot.huy_chot_ngay', { ngay_sx: ngay.name });
            toast('Đã huỷ chốt — sửa xong nhớ CHỐT LẠI.');
            refresh();
          } catch (e) {
            toastErr(e.message);
            throw e;
          }
        },
      });
    });
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
            showCanhBao(r, refresh);
          } else {
            toast(`Đã chốt ngày — ${formatNumber(r.tong_hop_tp)} hộp.`);
            refresh();
          }
        } catch (e) {
          toastErr(e.message);
          throw e;
        }
      },
    });
  });
}

function showCanhBao(r, refresh) {
  const m = openModal({ title: '✅ Đã chốt — có cảnh báo' });
  m.body.innerHTML = `
    <div class="sx-modal-msg">Đã chốt ${formatNumber(r.tong_hop_tp)} sản phẩm. Lưu ý:</div>
    ${r.canh_bao.map((c) => `<div class="sx-warn-text">⚠ ${esc(c)}</div>`).join('')}
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-cb-ok">ĐÃ HIỂU</button>
  `;
  m.body.querySelector('#sx-cb-ok').addEventListener('click', () => { m.close(); refresh(); });
}
