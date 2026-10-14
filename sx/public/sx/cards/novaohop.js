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
// D203: hộp không rõ ai đóng → "★ Ghi … cho công khoán": cả số nợ của mã thành MỘT dòng
// ★ Công khoán chung ở bảng vào hộp của ngày đang xem — tính sản lượng + tiền khoán theo
// đơn giá, không vào phiếu lương của ai (tổ tự chia). Đó LÀ một lần chấm bù: nợ tự trừ.
//
// Không nợ gì thì card TỰ ẨN.
//
// D208: GẬP sẵn thành một dòng (số mã, số hộp + mã quá lâu), bấm mới xổ danh sách. Ghi cho công khoán
// vẽ lại CẢ màn — thẻ mới vẽ ngay sau đó mở sẵn, để ghi tiếp mã khác không phải mở lại.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber, formatVND, nhanNgay } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { khungNo, cuNhat } from '/assets/sx/sx/components/gapno.js';

const NGAY_LAU = 3;   // chấm sót quá 3 ngày thì người ta không còn nhớ ai làm
let moDen = 0;        // vừa ghi công khoán (cả màn vẽ lại): thẻ vẽ trước mốc này thì mở sẵn — một lần

export async function render({ container, call, boot, ensureNgay, refresh }) {
  container.className = 'sx-card';
  container.style.display = 'none';
  // Giá công khoán chung tra theo bảng đơn giá của NGÀY ĐANG XEM — ngày dòng chung sẽ ghi vào.
  const ngayXem = (boot && boot.ngay_xem) || null;
  const lay = () => call('sx.api.khotp.so_no_vao_hop', ngayXem ? { ngay: ngayXem } : {});
  let dl;
  try {
    dl = await lay();
  } catch (e) {
    return;   // chưa migrate / không có quyền: ẩn card, đừng làm hỏng cả màn
  }
  const mo = Date.now() < moDen ? true : null;
  moDen = 0;
  ve(container, dl, call, { lay, boot, ensureNgay, refresh }, mo);
}

function ve(container, dl, call, ctx, mo = null) {
  const lai = async () => {
    try { ve(container, await ctx.lay(), call, ctx); } catch (e) { /* giữ bản cũ */ }
  };
  if (!dl || !dl.nhom || !dl.nhom.length) { container.innerHTML = ''; container.style.display = 'none'; return; }
  container.style.display = '';

  const tong = dl.nhom.reduce((a, g) => a + Number(g.con_lai || 0), 0);
  const lau = dl.nhom.filter((g) => g.so_ngay > NGAY_LAU).length;
  const than = khungNo(container, `Nợ vào hộp — ${dl.nhom.length} mã, ${formatNumber(tong)} hộp chưa chấm`, [
    lau && { chu: `${lau} mã quá ${NGAY_LAU} ngày — hỏi tổ sớm`, loai: 'gap' },
    cuNhat(dl.nhom),
  ], mo);
  than.appendChild(el('div', 'sx-muted',
    'Kho đã nhận nhiều hơn số chấm vào hộp. Chấm bù ở màn Ghi hộp — cho đúng công '
    + 'nhân, hoặc dòng ★ CÔNG NHẬT nếu công nhật đóng. Chấm xong nợ tự trừ.'
    + (dl.duoc_ghi_kc ? ' Không rõ ai đóng: bấm ★ Ghi cho công khoán — một dòng chung, tổ tự chia.' : '')));

  dl.nhom.forEach((g) => {
    const box = el('div', `sx-nobom-nhom${g.so_ngay > NGAY_LAU ? ' sx-nobom-lau' : ''}`);
    box.innerHTML = `
      <div class="sx-nobom-dau">
        <span class="sx-nobom-ten">${esc(g.ten)}</span>
        <span class="sx-nobom-so">${esc(formatNumber(g.con_lai))} hộp</span>
      </div>
      <div class="sx-nobom-meta">${g.dong.length} lần nhập · cũ nhất ${g.so_ngay} ngày${
        g.so_ngay > NGAY_LAU ? ' <b>— hỏi tổ sớm, để lâu không ai nhớ ai làm</b>' : ''}</div>`;
    if (dl.duoc_ghi_kc && g.so_hop > 0) {
      const nut = el('div', 'sx-nobom-nut');
      const b = el('button', 'sx-btn sx-nvh-kc', `★ Ghi ${formatNumber(g.so_hop)} hộp cho công khoán`);
      b.type = 'button';
      b.title = 'Không rõ ai đóng: ghi một dòng ★ Công khoán chung — tính khoán theo đơn giá, tổ tự chia';
      b.addEventListener('click', () => moGhiKC(g, call, ctx, lai));
      nut.appendChild(b);
      box.appendChild(nut);
    }
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
    than.appendChild(box);
  });
}

// Ghi CẢ số nợ của một mã thành một dòng ★ Công khoán chung (D203). Mã có nhiều mức giá
// (cách làm) thì chọn trước — mỗi cách một đơn giá, như lúc chấm ở màn Ghi hộp.
function moGhiKC(g, call, ctx, lai) {
  const chon = [
    ...(g.cach_lam || []).map((c) => ({ ten: c.ten, gia: c.don_gia, val: c.ten })),
    ...(g.gia_chung != null ? [{ ten: 'Chung', gia: g.gia_chung, val: null }] : []),
  ];
  let pick = chon.length === 1 ? chon[0] : null;
  const m = openModal({ kicker: 'Ghi cho công khoán', title: g.ten });
  const msg = el('div', 'sx-modal-msg');
  msg.textContent = `${formatNumber(g.so_hop)} hộp kho đã nhận mà chưa ai chấm sẽ ghi thành MỘT dòng `
    + `★ CÔNG KHOÁN CHUNG ở bảng vào hộp ${nhanNgay(ctx.boot) || 'hôm nay'}: tính sản lượng và tiền khoán `
    + 'theo đơn giá, KHÔNG vào phiếu lương của ai — tổ tự chia. Nợ mã này về 0. Ghi nhầm thì xoá dòng đó '
    + 'ở màn Ghi hộp — nợ hiện lại.';
  m.body.appendChild(msg);
  const gia = el('div', 'sx-nvh-gia');
  m.body.appendChild(gia);
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', `GHI ${formatNumber(g.so_hop)} HỘP CHO CÔNG KHOÁN`);
  ok.type = 'button';
  function veGia() {
    ok.disabled = chon.length > 1 && !pick;
    if (!chon.length) {
      gia.innerHTML = '<div class="sx-warn-text">⚠ Mã này chưa khai đơn giá — dòng chung tạm tính 0 đồng và '
        + 'vào Sổ nợ đơn giá; khai giá rồi bấm Áp giá ở màn Quản lý.</div>';
      return;
    }
    gia.innerHTML = (chon.length > 1 ? '<div class="sx-field-label">Làm bằng cách nào?</div>' : '')
      + '<div class="sx-sl-hang">' + chon.map((c, i) => `
        <button type="button" class="sx-sl-o${pick === c ? ' sx-sl-o-co' : ''}" data-i="${i}">
          <span class="sx-sl-ten">${esc(c.ten)} <i>${esc(formatNumber(c.gia))} đ/hộp</i></span>
          <span class="sx-sl-so">${esc(formatVND(c.gia * g.so_hop))}</span>
        </button>`).join('') + '</div>';
    gia.querySelectorAll('[data-i]').forEach((b) => {
      b.addEventListener('click', () => { pick = chon[Number(b.dataset.i)]; veGia(); });
    });
  }
  veGia();
  ok.addEventListener('click', async () => {
    if (chon.length > 1 && !pick) { toastErr('Chọn cách làm trước.'); return; }
    ok.disabled = true;
    try {
      const ng = await ctx.ensureNgay();
      const r = await call('sx.api.khotp.ghi_no_khoan_chung', {
        ngay_sx: ng.name, item: g.item, so_hop: g.so_hop, cach_lam: pick ? pick.val : null,
      });
      toast(`Đã ghi ${formatNumber(r.so_hop)} hộp ${r.ten} cho ★ Công khoán chung`
        + `${r.thanh_tien ? ` — ${formatVND(r.thanh_tien)}` : ''}.`);
      m.close();
      // Cả màn vẽ lại: dòng chung hiện ngay ở bảng ghi hôm nay, thẻ nợ bớt mã này (vẫn mở — D208).
      if (ctx.refresh) { moDen = Date.now() + 15000; ctx.refresh(); } else await lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
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
