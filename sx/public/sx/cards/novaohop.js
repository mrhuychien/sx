// Card "Sổ nợ vào hộp" (D101) — kho đã nhận NHIỀU HƠN số QC chấm vào hộp.
//
// Nghĩa duy nhất của một dòng ở đây: CHẤM SÓT. Hộp công nhật đóng đã có chỗ chấm
// riêng (dòng ★ Công nhật ở màn Ghi hộp), nên phần vượt còn lại là hộp của ai đó
// chưa được ghi — hoặc lương khoán của một người đang thiếu, hoặc công nhật quên chấm.
//
// Không có nút "đã chấm bù": nợ TỰ GIẢM khi QC chấm bù (server đối soát mỗi lần mở
// card). Nút bấm tay thì đóng được mà không ai chấm. Chỉ Quản lý có nút Bỏ qua (hàng
// trả về nhập lại…), và phải ghi lý do.
//
// Không nợ gì thì card TỰ ẨN.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';

const NGAY_LAU = 3;   // chấm sót quá 3 ngày thì người ta không còn nhớ ai làm

export async function render({ container, call }) {
  container.className = 'sx-card';
  container.style.display = 'none';
  let dl;
  try {
    dl = await call('sx.api.khotp.so_no_vao_hop');
  } catch (e) {
    return;   // chưa migrate / không có quyền: ẩn card, đừng làm hỏng cả màn
  }
  ve(container, dl, call);
}

function ve(container, dl, call) {
  const lai = async () => {
    try { ve(container, await call('sx.api.khotp.so_no_vao_hop'), call); } catch (e) { /* giữ bản cũ */ }
  };
  container.innerHTML = '';
  if (!dl || !dl.nhom || !dl.nhom.length) { container.style.display = 'none'; return; }
  container.style.display = '';

  const tong = dl.nhom.reduce((a, g) => a + Number(g.con_lai || 0), 0);
  container.appendChild(el('div', 'sx-field-label',
    `Nợ vào hộp — ${dl.nhom.length} mã, ${formatNumber(tong)} hộp chưa chấm`));
  container.appendChild(el('div', 'sx-muted',
    'Kho đã nhận nhiều hơn số chấm vào hộp. Chấm bù ở màn Ghi hộp — cho đúng công '
    + 'nhân, hoặc dòng ★ CÔNG NHẬT nếu công nhật đóng. Chấm xong nợ tự trừ.'));

  dl.nhom.forEach((g) => {
    const box = el('div', `sx-nobom-nhom${g.so_ngay > NGAY_LAU ? ' sx-nobom-lau' : ''}`);
    box.innerHTML = `
      <div class="sx-nobom-dau">
        <span class="sx-nobom-ten">${esc(g.ten)}</span>
        <span class="sx-nobom-so">${esc(formatNumber(g.con_lai))} hộp</span>
      </div>
      <div class="sx-nobom-meta">${g.dong.length} lần nhập · cũ nhất ${g.so_ngay} ngày${
        g.so_ngay > NGAY_LAU ? ' <b>— hỏi tổ sớm, để lâu không ai nhớ ai làm</b>' : ''}</div>`;
    g.dong.forEach((d) => {
      const h = el('div', 'sx-nobom-dong');
      h.innerHTML = `<span>${esc(d.ngay)} · còn ${esc(formatNumber(d.con_lai))}`
        + `${d.con_lai < d.so_luong ? `/${esc(formatNumber(d.so_luong))}` : ''} · `
        + `${esc(d.phieu_nhap || '')}</span>`;
      if (dl.duoc_bo_qua) {
        const b = el('button', 'sx-btn sx-btn-ghost', 'Bỏ qua');
        b.type = 'button';
        b.title = 'Hộp này không bao giờ được chấm (hàng trả về nhập lại…) — phải ghi lý do';
        b.addEventListener('click', () => moBoQua(d, g, call, lai));
        h.appendChild(b);
      }
      box.appendChild(h);
    });
    container.appendChild(box);
  });
}

function moBoQua(d, g, call, lai) {
  const m = openModal({ kicker: 'Bỏ qua nợ vào hộp', title: `${g.ten} · ${d.ngay}` });
  const msg = el('div', 'sx-modal-msg');
  msg.textContent = `${formatNumber(d.con_lai)} hộp (phiếu ${d.phieu_nhap}) sẽ KHÔNG BAO `
    + 'GIỜ được chấm — không ai được tính khoán cho số hộp này. Chỉ dùng khi thật sự '
    + 'không phải hàng mới đóng: hàng trả về nhập lại, hàng chuyển kho…';
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
      await call('sx.api.khotp.bo_qua_no_vao_hop', { name: d.name, ly_do: ta.value.trim() });
      toast('Đã bỏ qua khoản nợ.');
      m.close();
      await lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}
