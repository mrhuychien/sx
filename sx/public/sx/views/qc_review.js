// #/qc/review — màn của Ban ISO: lưới tháng + KPI + "đã xem xét đến ngày…".
//
// Câu hỏi màn này phải trả lời được, và nó là câu hỏi của auditor chứ không phải
// của quản lý: HỒ SƠ CÓ THẬT KHÔNG. Nên KPI đầu tiên không phải "bao nhiêu lượt
// đạt" mà là tỷ lệ lượt ghi đúng khung giờ — một tháng 100% đạt mà toàn ghi muộn
// thì đó là tháng chép hồ sơ, không phải tháng làm tốt.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step } from '/assets/sx/sx/components/modal.js';
import { khungTrong, veNhac } from '/assets/sx/sx/components/qcui.js';

const st = { thang: null };

function dauThang(x) {
  const d = x ? new Date(`${x}-01T12:00:00`) : new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

export async function render(api) {
  const { container, call } = api;
  st.thang = st.thang || dauThang();
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const tu = `${st.thang}-01`;
  const d = new Date(`${tu}T12:00:00`);
  const cuoi = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  const den = `${st.thang}-${String(cuoi.getDate()).padStart(2, '0')}`;

  let kpi = null;
  let ds = [];
  let nh = null;
  try {
    [kpi, ds, nh] = await Promise.all([
      call('sx.api.qc.dashboard', { tu, den }),
      call('sx.api.qc.list_rounds', { tu, den }),
      call('sx.api.qc.nhac').catch(() => null),
    ]);
  } catch (e) {
    container.innerHTML = '';
    container.appendChild(khungTrong(e.message));
    return;
  }
  container.innerHTML = '';

  const dieu = el('div', 'sx-qc-top');
  const inp = el('input');
  inp.type = 'month';
  inp.className = 'sx-textarea';
  inp.value = st.thang;
  inp.addEventListener('change', () => {
    if (inp.value) { st.thang = inp.value; render(api); }
  });
  dieu.appendChild(el('div', 'sx-qc-ngay', 'Tháng'));
  dieu.appendChild(inp);
  container.appendChild(dieu);

  const hopNhac = veNhac((nh && nh.ds) || []);
  if (hopNhac) container.appendChild(hopNhac);

  const o = (nhan, so, ghi) => {
    const b = el('div', 'sx-qc-kpi-o');
    b.appendChild(el('div', 'sx-qc-kpi-nhan', esc(nhan)));
    b.appendChild(el('div', 'sx-qc-kpi-so', esc(so)));
    if (ghi) b.appendChild(el('div', 'sx-qc-goiy', esc(ghi)));
    return b;
  };
  const kp = el('div', 'sx-qc-kpi');
  kp.appendChild(o('Ghi đúng khung giờ', `${kpi.ty_le_dung_gio}%`,
    `${kpi.ghi_muon} lượt ghi muộn`));
  kp.appendChild(o('Lượt đã làm', `${kpi.so_luot}/${kpi.can_co}`,
    `${kpi.ty_le_hoan_tat}% so với 3 lượt × 2 ca mỗi ngày`));
  kp.appendChild(o('Sự cố đang mở', kpi.su_co_mo,
    kpi.su_co_qua_han ? `${kpi.su_co_qua_han} phiếu QUÁ HẠN` : 'không có phiếu quá hạn'));
  kp.appendChild(o('Chưa xem xét', kpi.chua_xem_xet, 'lượt đã hoàn tất, Ban ISO chưa ký'));
  if (kpi.nhap_lai_tu_giay) {
    kp.appendChild(o('Nhập lại từ giấy', kpi.nhap_lai_tu_giay,
      'không tính là ghi muộn'));
  }
  container.appendChild(kp);

  // ── lưới ngày × lượt ────────────────────────────────────────────────
  const luoi = el('div', 'sx-qc-luoi');
  const cot = [];
  ['Sáng', 'Chiều'].forEach((ca) => ['Đầu ca', 'Giữa ca', 'Cuối ca']
    .forEach((l) => cot.push([ca, l])));
  let html = '<table><tr><th>Ngày</th>'
    + cot.map(([ca, l]) => `<th>${esc(ca[0])}·${esc(l.split(' ')[0])}</th>`).join('')
    + '<th>Sự cố</th></tr>';
  for (let i = 1; i <= cuoi.getDate(); i += 1) {
    const ngay = `${st.thang}-${String(i).padStart(2, '0')}`;
    const cua = ds.filter((r) => String(r.ngay) === ngay);
    html += `<tr><td>${i}</td>`;
    cot.forEach(([ca, l]) => {
      const r = cua.find((x) => x.ca === ca
        && (x.luot === l || (l === 'Đầu ca' && x.luot === 'Tuần')));
      const cls = !r ? 'sx-qc-o-thieu'
        : (r.ghi_muon ? 'sx-qc-o-muon' : (r.docstatus === 1 ? 'sx-qc-o-xong' : ''));
      const ky = !r ? '·' : (r.docstatus === 1 ? (r.ghi_muon ? '✻' : '✓') : '…');
      html += `<td class="${cls}" title="${esc(r ? r.name : 'chưa có lượt')}">${ky}</td>`;
    });
    html += '<td></td></tr>';
  }
  html += '</table>';
  luoi.innerHTML = html;
  container.appendChild(luoi);
  container.appendChild(el('div', 'sx-qc-goiy',
    '✓ xong đúng giờ · ✻ ghi muộn · … đang làm dở · · chưa có lượt'));

  // ── sự cố theo công đoạn ────────────────────────────────────────────
  if (kpi.theo_cong_doan.length) {
    container.appendChild(el('div', 'sx-qc-buoc',
      '<span class="sx-qc-buoc-ten">Sự cố theo công đoạn</span>'));
    const box = el('div', 'sx-qc-chips');
    kpi.theo_cong_doan.forEach((x) => box.appendChild(
      el('span', 'sx-qc-tag', `${esc(x.ten)}: ${x.so}`)));
    container.appendChild(box);
  }

  // ── đánh dấu đã xem xét ─────────────────────────────────────────────
  const nut = el('button', 'sx-btn sx-btn-primary sx-btn-big',
    `ĐÃ XEM XÉT ĐẾN ${esc(den)}`);
  nut.type = 'button';
  nut.disabled = !kpi.chua_xem_xet;
  nut.addEventListener('click', () => confirm2Step({
    title: 'Đánh dấu đã xem xét',
    message: `Ký xem xét ${kpi.chua_xem_xet} lượt từ ${tu} đến ${den}. `
      + 'Sau khi ký, các lượt này KHOÁ — không huỷ được nữa, kể cả bởi Ban ISO. '
      + 'Sai sót phát hiện sau thì ghi phiếu sự cố loại "Hiệu chỉnh hồ sơ".',
    confirmLabel: 'XÁC NHẬN ĐÃ XEM XÉT',
    onConfirm: async () => {
      try {
        const kq = await call('sx.api.qc.review_rounds', { tu, den });
        toast(`Đã ký xem xét ${kq.so_luot} lượt`);
        render(api);
      } catch (e) { toastErr(e.message); }
    },
  }));
  container.appendChild(nut);

  // ── hồ sơ giấy cho Ban ISO ──────────────────────────────────────────
  const ho_so = el('div', 'sx-qc-chips');
  ho_so.style.marginTop = 'var(--sx-s3)';
  const nutIn = el('button', 'sx-btn sx-btn-ghost', '🖨 IN CẢ THÁNG');
  nutIn.type = 'button';
  nutIn.addEventListener('click', async () => {
    nutIn.disabled = true;
    try {
      const html = await call('sx.api.qc.month_sheets', { tu, den });
      if (!html) { toastErr('Tháng này chưa có lượt nào hoàn tất.'); return; }
      const w = window.open('', '_blank');
      if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
      // Cùng lý do như tờ ngày: cửa sổ about:blank không thừa kế bảng mã.
      w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
        + `<title>BM.08.01 — ${tu} đến ${den}</title></head><body>${html}</body></html>`);
      w.document.close();
      w.focus();
      setTimeout(() => w.print(), 400);
    } catch (e) { toastErr(e.message); } finally { nutIn.disabled = false; }
  });
  ho_so.appendChild(nutIn);

  [['luot', 'vòng kiểm'], ['su_co', 'sự cố']].forEach(([loai, ten]) => {
    const b = el('button', 'sx-btn sx-btn-ghost', `⬇ CSV ${ten}`);
    b.type = 'button';
    b.addEventListener('click', async () => {
      b.disabled = true;
      try {
        const csv = await call('sx.api.qc.export_csv', { tu, den, loai });
        taiVe(`qc-${loai}-${st.thang}.csv`, csv);
      } catch (e) { toastErr(e.message); } finally { b.disabled = false; }
    });
    ho_so.appendChild(b);
  });
  container.appendChild(ho_so);
}

/** Lưu chuỗi thành file trên máy người dùng.
 *
 * type để 'text/csv;charset=utf-8' và server đã chèn sẵn BOM: thiếu một trong
 * hai thì Excel trên Windows mở ra là "Nhiá»‡t Ä'á»™" — file vẫn đúng, chỉ
 * là người nhận tưởng phần mềm hỏng rồi gõ tay lại cả tháng. */
function taiVe(ten, noi_dung) {
  const blob = new Blob([noi_dung], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = ten;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Thu hồi muộn một nhịp: thu ngay thì Safari huỷ luôn cú tải đang bắt đầu.
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
