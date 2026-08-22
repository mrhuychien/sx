// Card Chốt ngày — HAI NỬA ĐỘC LẬP (D55).
//
//   GHI SỔ  = báo mẻ → tầng 2 → bột bánh / bột đậu vào Kho BTP   (xong giữa ca)
//   VÀO HỘP = bảng vào hộp → tầng 3 → thành phẩm + lương khoán   (xong hết ca)
//
// Hai nửa ĐỘC LẬP, chốt theo thứ tự nào cũng được (D59): Vào hộp chỉ ghi lương,
// không đụng kho. Thành phẩm vào kho ở màn Nhập kho, khi thủ kho duyệt phiếu.

import { esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';

export async function render({ container, boot, call, ensureNgay, refresh }) {
  container.className = 'sx-card';
  const ngay = boot.ngay_sx;
  const xongCa = ngay && ngay.docstatus === 1;
  const gs = xongCa || (ngay && ngay.chot_ghiso);
  const vh = xongCa || (ngay && ngay.chot_vaohop);

  container.innerHTML = `
    <div class="sx-field-label">Chốt ngày — hai phần chốt riêng</div>
    <div id="sx-chot-gs"></div>
    <div id="sx-chot-vh"></div>
    ${gs && vh
      ? '<div class="sx-ok-box">✅ Ngày đã chốt đủ hai phần. Kho + lương khoán đã ghi nhận.</div>'
      : ''}
    ${gs || vh ? '<div id="sx-ct-box"><div class="sx-muted">Đang tải chứng từ…</div></div>' : ''}
  `;

  veNua(container.querySelector('#sx-chot-gs'), {
    ma: 'ghiso',
    ten: 'Ghi sổ',
    icon: '📋',
    xong: gs,
    mo_ta: 'Báo mẻ → mẻ trộn/nấu → bột bánh, bột đậu vào Kho BTP.',
    canhBao: 'Chốt Ghi sổ sẽ sinh chứng từ kho cho các mẻ đã báo và KHOÁ báo mẻ / '
      + 'báo cán của ngày. Kiểm lại số mẻ trước khi chốt.',
    khoa: null,
    khoaHuy: null,
  }, { boot, call, ensureNgay, refresh, xongCa });

  veNua(container.querySelector('#sx-chot-vh'), {
    ma: 'vaohop',
    ten: 'Vào hộp',
    icon: '📦',
    xong: vh,
    mo_ta: 'Chốt bảng vào hộp + ghi lương khoán. Thành phẩm vào kho ở màn Nhập kho.',
    canhBao: 'Chốt Vào hộp sẽ ghi lương khoán và KHOÁ bảng vào hộp. Thành phẩm CHƯA '
      + 'vào kho — hàng chỉ vào kho khi thủ kho duyệt phiếu nhập kho.',
    // D59: hai nửa độc lập thật, không còn bắt Ghi sổ chốt trước. Ràng buộc nguyên
    // liệu chuyển sang lúc duyệt phiếu nhập kho — đúng chỗ nó thuộc về.
    khoa: null,
    khoaHuy: null,
  }, { boot, call, ensureNgay, refresh, xongCa });

  if (gs || vh) veChungTu(container.querySelector('#sx-ct-box'), ngay, call);
}

function veNua(box, n, ctx) {
  const { call, ensureNgay, refresh, xongCa } = ctx;
  box.className = 'sx-fold-body';
  box.innerHTML = `
    <div class="sx-row-item">
      <div class="sx-vh-row" style="border:0;padding:0;background:none;cursor:default">
        <div class="sx-vh-who">
          <div class="sx-vh-name">${n.icon} ${esc(n.ten)}
            ${n.xong ? '<span class="sx-badge sx-badge-ok">đã chốt</span>' : ''}</div>
          <div class="sx-vh-meta">${esc(n.mo_ta)}</div>
        </div>
      </div>
      ${n.xong
        ? `<button type="button" class="sx-btn sx-btn-danger" data-act="huy">
             HUỶ CHỐT ${esc(n.ten.toUpperCase())}</button>`
        : `<button type="button" class="sx-btn sx-btn-primary sx-btn-big" data-act="chot"
             ${n.khoa ? 'disabled' : ''}>CHỐT ${esc(n.ten.toUpperCase())}</button>`}
      ${n.khoa && !n.xong ? `<div class="sx-muted">🔒 ${esc(n.khoa)}</div>` : ''}
    </div>`;

  const btn = box.querySelector('[data-act]');
  if (!btn) return;

  if (btn.dataset.act === 'chot') {
    btn.addEventListener('click', async () => {
      const ng = await ensureNgay();
      confirm2Step({
        title: `Chốt ${n.ten} — ${ng.ngay || ''}`,
        message: n.canhBao,
        confirmLabel: `CHỐT ${n.ten.toUpperCase()}`,
        onConfirm: async () => {
          try {
            const r = await call(`sx.api.chot.chot_${n.ma}`, { ngay_sx: ng.name });
            if (r.canh_bao && r.canh_bao.length) return showCanhBao(n, r, refresh);
            toast(`Đã chốt ${n.ten}.`);
            refresh();
          } catch (e) { toastErr(e.message); throw e; }
        },
      });
    });
    return;
  }

  btn.addEventListener('click', () => {
    // Cả hai nửa đã chốt -> phiếu ngày submit rồi, Frappe không lùi docstatus được.
    // Lúc đó chỉ có HUỶ CHỐT NGÀY (đảo cả hai, giữ nguyên số liệu để sửa).
    if (xongCa) return huyCaNgay(ctx);
    if (n.khoaHuy) { toastErr(n.khoaHuy); return; }
    confirm2Step({
      title: `Huỷ chốt ${n.ten}`,
      message: `Thu hồi chứng từ kho của phần ${n.ten} và mở lại cho sửa. `
        + (n.ma === 'vaohop'
          ? 'Lương khoán của ngày cũng được gỡ khỏi phiếu lương tháng. '
          : '')
        + 'Số liệu đã nhập giữ nguyên; sửa xong phải CHỐT LẠI.',
      confirmLabel: 'HUỶ CHỐT',
      onConfirm: async () => {
        try {
          await call(`sx.api.chot.huy_chot_${n.ma}`, { ngay_sx: ctx.boot.ngay_sx.name });
          toast(`Đã huỷ chốt ${n.ten} — sửa xong nhớ CHỐT LẠI.`);
          refresh();
        } catch (e) { toastErr(e.message); throw e; }
      },
    });
  });
}

function huyCaNgay({ boot, call, refresh }) {
  confirm2Step({
    title: 'Huỷ chốt ngày ' + (boot.ngay_sx.ngay || ''),
    message: 'Ngày này đã chốt CẢ HAI phần nên phiếu ngày đã khoá — không huỷ lẻ một '
      + 'phần được. Huỷ chốt ngày sẽ THU HỒI toàn bộ chứng từ kho (lệnh SX + phiếu '
      + 'nhập/xuất kho + phiếu nhập bột) và GỠ lương khoán của ngày. Báo mẻ / báo cán / '
      + 'bảng vào hộp giữ nguyên để sửa; sửa xong chốt lại từng phần.',
    confirmLabel: 'HUỶ CHỐT NGÀY',
    onConfirm: async () => {
      try {
        await call('sx.api.chot.huy_chot_ngay', { ngay_sx: boot.ngay_sx.name });
        toast('Đã huỷ chốt ngày — sửa xong nhớ CHỐT LẠI.');
        refresh();
      } catch (e) { toastErr(e.message); throw e; }
    },
  });
}

function showCanhBao(n, r, refresh) {
  const m = openModal({ kicker: `Chốt ${n.ten}`, title: '✅ Xong — có cảnh báo' });
  m.body.innerHTML = `
    <div class="sx-modal-msg">${r.tong_hop_tp
      ? `Đã chốt ${formatNumber(r.tong_hop_tp)} sản phẩm. ` : ''}Lưu ý:</div>
    ${r.canh_bao.map((c) => `<div class="sx-warn-text">⚠ ${esc(c)}</div>`).join('')}
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-cb-ok">ĐÃ HIỂU</button>
  `;
  m.body.querySelector('#sx-cb-ok').addEventListener('click', () => { m.close(); refresh(); });
}

// Danh sách chứng từ đã sinh trong ngày + link mở thẳng trên Desk (D29)
async function veChungTu(box, ngay, call) {
  if (!box) return;
  let r;
  try {
    r = await call('sx.api.chot.chung_tu_ngay', { ngay_sx: ngay.name });
  } catch (e) {
    box.innerHTML = `<div class="sx-warn-text">Không đọc được danh sách chứng từ: ${esc(e.message || '')}</div>`;
    return;
  }
  const nhom = (r && r.nhom) || [];
  if (!nhom.length) { box.innerHTML = '<div class="sx-muted">Chưa có chứng từ nào.</div>'; return; }
  const tong = nhom.reduce((a, g) => a + g.dong.length, 0);
  box.innerHTML = `
    <div class="sx-field-label">Chứng từ đã tạo (${tong}) — bấm để mở</div>
    ${nhom.map((g) => `
      <div class="sx-ct-nhom">${esc(g.nhom)}</div>
      <ul class="sx-ct-list">
        ${g.dong.map((d) => `
          <li class="sx-ct-item${d.docstatus === 2 ? ' sx-ct-huy' : ''}">
            ${d.url
              ? `<a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.name)}</a>`
              : `<b>${esc(d.name)}</b>`}
            ${d.docstatus === 2 ? '<span class="sx-ct-tag">đã huỷ</span>' : ''}
            ${d.mo_ta ? `<div class="sx-muted">${esc(d.mo_ta)}</div>` : ''}
          </li>`).join('')}
      </ul>`).join('')}
  `;
}
