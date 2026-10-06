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
  veChot(container, boot.ngay_sx, { boot, call, ensureNgay, refresh });
}

/** Hai nửa chốt của MỘT phiếu ngày vào `container` — thẻ này và lịch chốt (D117)
 *  dùng chung. `ngay` = {name, ngay, docstatus, chot_ghiso, chot_vaohop}. */
export function veChot(container, ngay, { boot, call, ensureNgay, refresh }) {
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
      // D116: mã nguyên liệu chưa có giá vốn → khai giá TRƯỚC, khỏi chốt rồi mới
      // văng lỗi tiếng Anh của ERPNext giữa chừng.
      if (n.ma === 'ghiso') {
        const thieu = await layThieuGia(call, ng.name);
        if (thieu.length) { moKhaiGia(thieu, call, () => hoiChot(ng)); return; }
      }
      hoiChot(ng);
    });
    const hoiChot = (ng) => {
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
          } catch (e) {
            const thieu = n.ma === 'ghiso' ? await layThieuGia(call, ng.name) : [];
            if (thieu.length) { moKhaiGia(thieu, call, () => hoiChot(ng)); return; }
            toastErr(e.message); throw e;
          }
        },
      });
    };
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

async function layThieuGia(call, ngaySx) {
  try { return (await call('sx.api.chot.thieu_gia_von_ngay', { ngay_sx: ngaySx })) || []; } catch (e) { return []; }
}

// D116: khai giá vốn cho mã chưa từng có giá (vani, màu… chưa nhập mua có đơn giá).
// Ghi vào Item.valuation_rate — chỉ là giá DỰ PHÒNG của ERPNext: nhập mua có giá
// lần sau thì giá thật thay chỗ nó.
export function moKhaiGia(ds, call, xong) {
  const m = openModal({ kicker: 'Chốt Ghi sổ', title: 'Khai giá vốn' });
  m.body.innerHTML = `
    <div class="sx-modal-msg">${ds.length} mã nguyên liệu chưa có giá vốn (chưa nhập mua có đơn `
      + 'giá) nên ERPNext không trừ kho được. Nhập giá mua ước tính cho mỗi đơn vị kho — chỉ '
      + `cần một lần; nhập mua có giá sau này sẽ thay giá này.</div>
    ${ds.map((d, i) => `<label class="sx-kgv">
      <span class="sx-kgv-ten">${esc(d.ten)} <span class="sx-muted">${esc(d.item)}</span></span>
      <span class="sx-kgv-o"><input class="sx-textarea" type="number" inputmode="decimal" min="0"
        step="any" data-i="${i}" value="${d.goi_y ? esc(String(d.goi_y)) : ''}"
        placeholder="đ"><span>đ / ${esc(d.dvt || 'đơn vị')}</span></span>
      ${d.goi_y ? '<span class="sx-muted">điền sẵn theo giá mua / giá chuẩn trên mã hàng</span>' : ''}
    </label>`).join('')}
    <div class="sx-warn-text" id="sx-kgv-loi" role="alert"></div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-kgv-ok">LƯU GIÁ &amp; CHỐT TIẾP</button>`;
  const ok = m.body.querySelector('#sx-kgv-ok');
  ok.addEventListener('click', async () => {
    const rows = ds.map((d, i) => ({ item: d.item,
      gia: Number(m.body.querySelector(`[data-i="${i}"]`).value) }));
    const thieu = rows.filter((r) => !(r.gia > 0));
    if (thieu.length) {
      m.body.querySelector('#sx-kgv-loi').textContent = `Còn ${thieu.length} mã chưa nhập giá.`;
      return;
    }
    ok.disabled = true;
    try {
      await call('sx.api.chot.khai_gia_von', { rows: JSON.stringify(rows) });
      m.close();
      toast(`Đã khai giá vốn ${rows.length} mã.`);
      xong();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  return m;
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
