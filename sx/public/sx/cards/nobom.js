// Card "Sổ nợ BOM" (D97) — thành phẩm đã nhập kho lúc mã hàng CHƯA có BOM.
//
// Hàng đã vào kho nhưng bột và bao bì CHƯA bị trừ. Không xử lý thì tồn nguyên liệu
// trên sổ cao hơn thực tế mãi mãi, và lần kiểm kê nào cũng "thiếu" đúng bằng phần
// này mà không ai nhớ ra vì sao. Card này tồn tại để khoản nợ đó không bị quên.
//
// Gom theo MÃ HÀNG: tạo một BOM là trả được nợ của mọi phiếu đã nhập mã đó. Mã đã
// có BOM đứng đầu (xử lý được ngay), rồi tới nợ lâu nhất.
//
// Không có khoản nợ nào thì card TỰ ẨN — một thẻ "không nợ gì" nằm trên màn mỗi
// ngày sẽ dạy mắt bỏ qua đúng vùng đó.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';

export async function render({ container, call }) {
  container.className = 'sx-card';
  container.style.display = 'none';
  let dl;
  try {
    dl = await call('sx.api.khotp.so_no_bom');
  } catch (e) {
    return;   // chưa migrate / không có quyền: ẩn card, đừng làm hỏng cả màn
  }
  if (!dl || !dl.nhom || !dl.nhom.length) return;
  container.style.display = '';
  ve(container, dl, call);
}

function ve(container, dl, call) {
  const lai = async () => {
    try { ve(container, await call('sx.api.khotp.so_no_bom'), call); } catch (e) { /* giữ bản cũ */ }
  };
  container.innerHTML = '';
  if (!dl.nhom.length) { container.style.display = 'none'; return; }

  container.appendChild(el('div', 'sx-field-label',
    `Sổ nợ BOM — ${dl.nhom.length} mã, ${dl.tong_dong} lần nhập`));
  container.appendChild(el('div', 'sx-muted',
    'Đã nhập kho khi CHƯA có định mức: hàng đã vào kho, bột và bao bì chưa bị trừ. '
    + 'Tạo BOM cho mã đó rồi bấm Hạch toán bù.'));

  dl.nhom.forEach((g) => {
    const lop = g.co_bom ? ' sx-nobom-co' : (g.lau ? ' sx-nobom-lau' : '');
    const box = el('div', `sx-nobom-nhom${lop}`);
    box.innerHTML = `
      <div class="sx-nobom-dau">
        <span class="sx-nobom-ten">${esc(g.ten)}</span>
        <span class="sx-nobom-so">${esc(formatNumber(g.so_luong))} ${esc(g.dvt)}</span>
      </div>
      <div class="sx-nobom-meta">${g.co_bom
        ? `✓ đã có BOM <b>${esc(g.bom)}</b> — hạch toán bù được ngay`
        : '✕ chưa có BOM'} · ${g.dong.length} lần nhập · cũ nhất ${g.so_ngay} ngày${
        g.lau && !g.co_bom ? ` <b>(quá ${dl.ngay_no_lau} ngày)</b>` : ''}${g.gia_0
        ? ' · <b>lô giá vốn 0</b> — giá thành chưa đúng cho tới khi bù' : ''}</div>`;

    g.dong.forEach((d) => {
      const h = el('div', 'sx-nobom-dong');
      h.innerHTML = `<span>${esc(d.ngay)} · ${esc(formatNumber(d.so_luong))} · `
        + `${esc(d.phieu_nhap || '')}${d.batch ? ` · lô ${esc(d.batch)}` : ''}</span>`;
      if (dl.duoc_xu_ly) {
        const b = el('button', 'sx-btn sx-btn-ghost', 'Bỏ qua');
        b.type = 'button';
        b.title = 'Không trừ nguyên liệu cho lần nhập này (hàng trả về…) — phải ghi lý do';
        b.addEventListener('click', () => moBoQua(d, g, call, lai));
        h.appendChild(b);
      }
      box.appendChild(h);
    });

    if (dl.duoc_xu_ly) {
      const nut = el('div', 'sx-nobom-nut');
      const bu = el('button', `sx-btn ${g.co_bom ? 'sx-btn-primary' : 'sx-btn-ghost'}`,
        g.co_bom ? 'HẠCH TOÁN BÙ' : 'CHỜ CÓ BOM');
      bu.type = 'button';
      bu.disabled = !g.co_bom;
      bu.addEventListener('click', () => confirm2Step({
        title: `Hạch toán bù ${g.ten}`,
        message: `Trừ bột và bao bì theo ${g.bom} cho ${formatNumber(g.so_luong)} ${g.dvt} `
          + `đã nhập (${g.dong.length} lần). Mỗi lần nhập một phiếu kho riêng.\n\n`
          + 'Nguyên liệu trừ theo lô FIFO ở THỜI ĐIỂM BÙ — các lô thành phẩm này không '
          + 'truy ngược được tới đúng lô bột đã dùng.',
        confirmLabel: 'HẠCH TOÁN BÙ',
        onConfirm: async () => {
          try {
            const kq = await call('sx.api.khotp.hach_toan_bu', { item: g.item });
            toast(`Đã hạch toán bù ${kq.so_dong} lần nhập ${g.ten}.`);
            await lai();
          } catch (e) { toastErr(e.message); throw e; }
        },
      }));
      nut.appendChild(bu);
      box.appendChild(nut);
    }
    container.appendChild(box);
  });

  if (!dl.duoc_xu_ly) {
    container.appendChild(el('div', 'sx-muted',
      'Chỉ quản lý hạch toán bù / bỏ qua được — báo quản lý khi đã có BOM.'));
  }
}

function moBoQua(d, g, call, lai) {
  const m = openModal({ kicker: 'Bỏ qua nợ BOM', title: `${g.ten} · ${d.ngay}` });
  const msg = el('div', 'sx-modal-msg');
  msg.textContent = `${formatNumber(d.so_luong)} ${g.dvt} (phiếu ${d.phieu_nhap}) sẽ `
    + 'KHÔNG BAO GIỜ trừ nguyên liệu. Chỉ dùng khi thật sự không có tiêu hao: hàng trả '
    + 'về nhập lại, hàng làm bù đã trừ ở chứng từ khác…';
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
      await call('sx.api.khotp.bo_qua_no', { name: d.name, ly_do: ta.value.trim() });
      toast('Đã bỏ qua khoản nợ.');
      m.close();
      await lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}
