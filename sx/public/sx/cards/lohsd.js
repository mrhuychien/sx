// Card "Lô cũ chưa có HSD" (W05, D131) — lô thành phẩm vào kho trước khi lô mang HSD.
//
// Lô không HSD thì truy xuất theo HSD in trên hộp không ra lô nào, và báo cận date bỏ
// sót. HSD gợi ý = NSX + hạn dùng của mã (bộ tự công bố) — người soát theo bao bì rồi
// bấm GHI. Lô còn tồn đứng trước; lô đã bán hết vẫn nên ghi (để tra khách đã mua).
//
// Không còn lô nào thì card TỰ ẨN.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step } from '/assets/sx/sx/components/modal.js';

const ngay = (iso) => {
  const d = String(iso || '').slice(0, 10).split('-');
  return d.length === 3 ? `${d[2]}/${d[1]}/${d[0]}` : '';
};

export async function render({ container, call }) {
  container.className = 'sx-card';
  container.style.display = 'none';
  const st = { caHet: false };
  async function tai() {
    let dl;
    try { dl = await call('sx.api.lohsd.danh_sach', { ca_het_hang: st.caHet ? 1 : 0 }); } catch (e) {
      return;   // chưa migrate / không có quyền: ẩn card, đừng làm hỏng cả màn
    }
    if (!dl.rows.length && !dl.het_hang) { container.style.display = 'none'; return; }
    container.style.display = '';
    ve(dl);
  }

  function ve(dl) {
    const hsd = {};
    dl.rows.forEach((r) => { hsd[r.batch] = r.goi_y || ''; });
    container.innerHTML = `
      <div class="sx-field-label">Lô cũ chưa có HSD — ${dl.con_ton} lô còn tồn${
        dl.het_hang ? ` · ${dl.het_hang} lô đã hết hàng` : ''}</div>
      <div class="sx-muted">Lô nhập trước khi lô mang HSD: truy xuất theo HSD in trên hộp
        không ra. Soát HSD theo bao bì (đã điền sẵn = NSX + hạn dùng) rồi bấm GHI. Hàng còn
        trong kho thì nên dùng thẻ <b>Kiểm kê kho thành phẩm</b>: đếm theo HSD in trên hộp —
        một lô cũ có thể chứa hộp nhiều HSD.</div>
      <div class="sx-vh-list" id="lh-ds">${dl.rows.map((r) => `
        <div class="sx-vh-row">
          <div class="sx-vh-who">
            <div class="sx-vh-name">${esc(r.ten)}</div>
            <div class="sx-vh-meta">${r.co_nsx ? 'NSX' : 'nhập'} ${esc(ngay(r.nsx))} ·
              ${r.ton > 0 ? `tồn ${formatNumber(r.ton)} ${esc(r.dvt)}` : 'đã hết hàng'}
              · <span class="sx-muted">mã cũ ${esc(r.batch)}</span></div>
            ${r.goi_y ? '' : '<div class="sx-warn-text">Mã chưa khai hạn dùng — nhập HSD theo bao bì.</div>'}
          </div>
          <input class="sx-textarea sx-lh-o" type="date" data-lo="${esc(r.batch)}"
            value="${esc(r.goi_y || '')}" aria-label="HSD lô ${esc(r.ten)}">
        </div>`).join('')}</div>
      <div class="sx-nobom-nut">
        <button type="button" class="sx-btn sx-btn-primary" id="lh-ghi">GHI HSD</button>
        <button type="button" class="sx-btn" id="lh-het">${st.caHet
          ? 'Chỉ lô còn tồn' : `+ Lô đã hết hàng (${dl.het_hang || 0})`}</button>
      </div>`;
    container.querySelectorAll('.sx-lh-o').forEach((o) => o.addEventListener('change', () => {
      hsd[o.dataset.lo] = o.value;
    }));
    container.querySelector('#lh-het').addEventListener('click', () => {
      st.caHet = !st.caHet; tai();
    });
    container.querySelector('#lh-ghi').addEventListener('click', () => {
      const rows = Object.entries(hsd).filter(([, v]) => v).map(([batch, v]) => ({ batch, hsd: v }));
      if (!rows.length) { toastErr('Chưa có lô nào có HSD để ghi.'); return; }
      confirm2Step({
        title: `Ghi HSD cho ${rows.length} lô`,
        message: 'HSD ghi vào lô thành phẩm — truy xuất và báo cận date dùng ngay. '
          + 'Đã soát theo bao bì chưa? Lô đã có HSD thì không bị ghi đè.',
        confirmLabel: 'GHI HSD',
        onConfirm: async () => {
          try {
            const kq = await call('sx.api.lohsd.dat_hsd', { rows: JSON.stringify(rows) });
            if (kq.loi && kq.loi.length) toastErr(kq.loi.slice(0, 4).join(' · '));
            if (kq.xong) toast(`Đã ghi HSD cho ${kq.xong} lô.`);
            tai();
          } catch (e) { toastErr(e.message); throw e; }
        },
      });
    });
  }
  tai();
}
