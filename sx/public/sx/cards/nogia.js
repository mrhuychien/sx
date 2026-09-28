// Card "Sổ nợ đơn giá" (D99) — sản lượng vào hộp đã chốt lúc mã hàng CHƯA khai giá.
//
// Lương khoán của những mã này đang nằm trong phiếu lương tháng ở mức 0 đồng. Không
// xử lý thì tới lúc công nhân cầm phiếu lương mới lộ. Card này tồn tại để khoản nợ
// đó không bị quên.
//
// Gom theo (MÃ HÀNG, CÁCH LÀM): khai một giá là trả được nợ của mọi ngày đã chốt mã
// đó. Giá KHÔNG gõ ở đây — nguồn giá duy nhất là bảng đơn giá áp dụng cho ngày sản
// xuất, card chỉ chỉ ra phải khai ở bảng nào.
//
// Không có khoản nợ nào thì card TỰ ẨN.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';

export async function render({ container, call }) {
  container.className = 'sx-card';
  container.style.display = 'none';
  let dl;
  try {
    dl = await call('sx.api.nogia.so_no_gia');
  } catch (e) {
    return;   // chưa migrate / không có quyền: ẩn card, đừng làm hỏng cả màn
  }
  if (!dl || !dl.nhom || !dl.nhom.length) return;
  container.style.display = '';
  ve(container, dl, call);
}

function ve(container, dl, call) {
  const lai = async () => {
    try { ve(container, await call('sx.api.nogia.so_no_gia'), call); } catch (e) { /* giữ bản cũ */ }
  };
  container.innerHTML = '';
  if (!dl.nhom.length) { container.style.display = 'none'; return; }

  container.appendChild(el('div', 'sx-field-label',
    `Sổ nợ đơn giá — ${dl.nhom.length} mã, ${dl.tong_dong} ngày`));
  container.appendChild(el('div', 'sx-muted',
    'Đã chốt vào hộp khi mã CHƯA có đơn giá: lương khoán đang 0 đồng trong phiếu lương. '
    + 'Khai giá ở bảng đơn giá rồi bấm Áp giá.'));

  dl.nhom.forEach((g) => {
    const ten = g.ten + (g.cach_lam ? ` · ${g.cach_lam}` : '');
    const lop = g.co_gia ? ' sx-nobom-co' : (g.lau ? ' sx-nobom-lau' : '');
    const box = el('div', `sx-nobom-nhom${lop}`);
    box.innerHTML = `
      <div class="sx-nobom-dau">
        <span class="sx-nobom-ten">${esc(ten)}</span>
        <span class="sx-nobom-so">${esc(formatNumber(g.so_hop))} hộp</span>
      </div>
      <div class="sx-nobom-meta">${g.co_gia
        ? `✓ đã có giá — áp được ${g.so_co_gia}/${g.dong.length} ngày, `
          + `≈ <b>${esc(formatNumber(g.tien))} đ</b>`
        : `✕ chưa khai giá ở bảng <b>${esc(g.bang.join(', ') || '(chưa có bảng nào)')}</b>`}
        · cũ nhất ${g.so_ngay} ngày${g.lau && !g.co_gia
        ? ` <b>(quá ${dl.ngay_no_lau} ngày)</b>` : ''}</div>`;

    g.dong.forEach((d) => {
      const h = el('div', 'sx-nobom-dong');
      h.innerHTML = `<span>${esc(d.ngay)} · ${esc(formatNumber(d.so_hop))} hộp · `
        + `${d.so_nguoi} người${d.gia != null ? ` · ${esc(formatNumber(d.gia))} đ/hộp` : ''}</span>`;
      const b = el('button', 'sx-btn sx-btn-ghost', 'Bỏ qua');
      b.type = 'button';
      b.title = 'Giữ 0 đồng cho ngày này (hàng mẫu, làm thử…) — phải ghi lý do';
      b.addEventListener('click', () => moBoQua(d, ten, call, lai));
      h.appendChild(b);
      box.appendChild(h);
    });

    const nut = el('div', 'sx-nobom-nut');
    const ap = el('button', `sx-btn ${g.co_gia ? 'sx-btn-primary' : 'sx-btn-ghost'}`,
      g.co_gia ? 'ÁP GIÁ' : 'CHỜ KHAI GIÁ');
    ap.type = 'button';
    ap.disabled = !g.co_gia;
    ap.addEventListener('click', () => confirm2Step({
      title: `Áp giá ${ten}`,
      message: `Điền đơn giá vào phiếu lương tháng của ${g.so_co_gia} ngày đã chốt `
        + `(≈ ${formatNumber(g.tien)} đ).\n\nGiá lấy từ bảng đơn giá áp dụng cho TỪNG `
        + 'ngày sản xuất. Phiếu lương đã duyệt thì không sửa được — phải huỷ duyệt trước.',
      confirmLabel: 'ÁP GIÁ',
      onConfirm: async () => {
        try {
          const kq = await call('sx.api.nogia.ap_gia',
            { san_pham: g.san_pham, cach_lam: g.cach_lam || null });
          toast(`Đã áp giá ${kq.so_dong} ngày · ${formatNumber(kq.tien)} đ.`
            + (kq.loi && kq.loi.length ? ` ${kq.loi.length} ngày vướng phiếu đã duyệt.` : ''));
          await lai();
        } catch (e) { toastErr(e.message); throw e; }
      },
    }));
    nut.appendChild(ap);
    box.appendChild(nut);
    container.appendChild(box);
  });
}

function moBoQua(d, ten, call, lai) {
  const m = openModal({ kicker: 'Bỏ qua nợ đơn giá', title: `${ten} · ${d.ngay}` });
  const msg = el('div', 'sx-modal-msg');
  msg.textContent = `${formatNumber(d.so_hop)} hộp của ${d.so_nguoi} người sẽ GIỮ 0 ĐỒNG `
    + 'vĩnh viễn. Chỉ dùng khi thật sự không trả khoán: hàng mẫu, làm thử, làm lại hàng lỗi…';
  m.body.appendChild(msg);
  const ta = el('textarea', 'sx-textarea');
  ta.rows = 3;
  ta.placeholder = 'Lý do (bắt buộc)';
  m.body.appendChild(ta);
  const ok = el('button', 'sx-btn sx-btn-warn sx-btn-big', 'BỎ QUA KHOẢN NỢ NÀY');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!ta.value.trim()) { toastErr('Phải ghi lý do.'); return; }
    ok.disabled = true;
    try {
      await call('sx.api.nogia.bo_qua_no_gia', { name: d.name, ly_do: ta.value.trim() });
      toast('Đã bỏ qua khoản nợ.');
      m.close();
      await lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}
