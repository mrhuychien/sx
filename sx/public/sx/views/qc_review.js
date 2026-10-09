// #/qc/review — màn của Ban ISO: lưới tháng + KPI + "đã xem xét đến ngày…".
//
// Câu hỏi màn này phải trả lời được, và nó là câu hỏi của auditor chứ không phải
// của quản lý: HỒ SƠ CÓ THẬT KHÔNG. Nên KPI đầu tiên không phải "bao nhiêu lượt
// đạt" mà là tỷ lệ lượt ghi đúng khung giờ — một tháng 100% đạt mà toàn ghi muộn
// thì đó là tháng chép hồ sơ, không phải tháng làm tốt.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step } from '/assets/sx/sx/components/modal.js';
import {
  LUOT_NGAY, chip, khungTrong, tabXemXet, timLuot, veNhac,
} from '/assets/sx/sx/components/qcui.js';

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
    container.appendChild(tabXemXet('review'));
    container.appendChild(khungTrong(e.message));
    return;
  }
  container.innerHTML = '';
  container.appendChild(tabXemXet('review'));

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
  // W12 (D141): mẫu số là NGÀY SẢN XUẤT (có báo mẻ / lượt kiểm / nhật ký cát), tới hôm nay —
  // Chủ nhật, ngày nghỉ, ngày chưa tới không còn kéo tỷ lệ xuống.
  kp.appendChild(o('Lượt đã làm', `${kpi.so_luot}/${kpi.can_co}`,
    `${kpi.ty_le_hoan_tat}% · 3 lượt × ${kpi.so_ngay_sx} ngày sản xuất`));
  kp.appendChild(o('Sự cố đang mở', kpi.su_co_mo,
    kpi.su_co_qua_han ? `${kpi.su_co_qua_han} phiếu QUÁ HẠN` : 'không có phiếu quá hạn'));
  const cat = kpi.cat || {};
  kp.appendChild(o('Chưa xem xét', kpi.chua_xem_xet, `lượt đã hoàn tất, Ban ISO chưa ký${
    cat.chua_xem ? ` · + ${cat.chua_xem} dòng nhật ký cát` : ''}`));
  if (kpi.nhap_lai_tu_giay) {
    kp.appendChild(o('Nhập lại từ giấy', kpi.nhap_lai_tu_giay,
      'không tính là ghi muộn'));
  }
  container.appendChild(kp);

  // ── lưới ngày × lượt ────────────────────────────────────────────────
  // Ngày sản xuất thiếu lượt: ô ĐỎ (✗) — đó là lỗ hồ sơ. Ngày không sản xuất: "–" nhạt —
  // không ai phải giải trình. Trước W12 cả hai cùng một dấu chấm xám.
  const luoi = el('div', 'sx-qc-luoi');
  const cot = LUOT_NGAY;
  const coSx = new Set(kpi.ngay_sx || []);
  const tn = kpi.theo_ngay || {};
  const nay = new Date();
  const homNay = `${nay.getFullYear()}-${String(nay.getMonth() + 1).padStart(2, '0')}-${
    String(nay.getDate()).padStart(2, '0')}`;
  let html = '<table><tr><th>Ngày</th>'
    + cot.map((c) => `<th>${esc(c.ngan)}</th>`).join('')
    + '<th>Sự cố</th><th>Cát</th></tr>';
  for (let i = 1; i <= cuoi.getDate(); i += 1) {
    const ngay = `${st.thang}-${String(i).padStart(2, '0')}`;
    const cua = ds.filter((r) => String(r.ngay) === ngay);
    const laSx = coSx.has(ngay);
    const sau = ngay > homNay;
    html += `<tr class="${sau ? 'sx-qc-hang-sau' : (laSx ? '' : 'sx-qc-hang-nghi')}"><td>${i}</td>`;
    cot.forEach((c) => {
      const r = timLuot(cua, c.luot);
      let cls = '';
      let ky = sau ? '' : '–';
      if (r) {
        cls = r.ghi_muon ? 'sx-qc-o-muon' : (r.docstatus === 1 ? 'sx-qc-o-xong' : '');
        ky = r.docstatus === 1 ? (r.ghi_muon ? '✻' : '✓') : '…';
      } else if (laSx) {
        cls = 'sx-qc-o-loi';
        ky = '✗';
      }
      html += `<td class="${cls}" title="${esc(r ? r.name : (laSx ? 'ngày sản xuất — thiếu lượt'
        : 'không sản xuất'))}">${ky}</td>`;
    });
    const g = tn[ngay] || {};
    html += `<td>${g.su_co || ''}</td><td>${g.cat === 'thay' ? '↻' : (g.cat ? '✓' : '')}</td></tr>`;
  }
  html += '</table>';
  luoi.innerHTML = html;
  container.appendChild(luoi);
  container.appendChild(el('div', 'sx-qc-goiy',
    '✓ xong đúng giờ · ✻ ghi muộn · … đang làm dở · ✗ ngày sản xuất thiếu lượt · – không sản xuất'
    + ' · Cát: ✓ có nhật ký, ↻ thay cát'));

  // ── sự cố theo công đoạn ────────────────────────────────────────────
  if (kpi.theo_cong_doan.length) {
    container.appendChild(el('div', 'sx-qc-buoc',
      '<span class="sx-qc-buoc-ten">Sự cố theo công đoạn</span>'));
    const box = el('div', 'sx-qc-chips');
    kpi.theo_cong_doan.forEach((x) => box.appendChild(
      el('span', 'sx-qc-tag', `${esc(x.ten)}: ${x.so}`)));
    container.appendChild(box);
  }

  // ── số đo theo máy (W16): mỗi máy rang M1–M3 / máy gói bột một dòng mỗi số đo ──
  // Gộp ba máy thì một lồng rang quay chậm cả tháng vẫn nằm lọt trong trung bình.
  const sd = kpi.so_do_may || [];
  if (sd.length) {
    container.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">Số đo theo máy</span>'));
    const so = (v) => (v === null || v === undefined ? '…'
      : Number(v).toLocaleString('vi-VN', { maximumFractionDigits: 1 }));
    // Nhãn ngắn cho vừa màn điện thoại; tên đầy đủ ở title.
    const NGAN = { rang_nhiet_do: 'Nhiệt độ', rang_vong_quay: 'Vòng quay', b8_nhiet_han: 'Nhiệt độ hàn' };
    const mayNgan = (t) => t.replace('Máy rang đỗ', 'Rang').replace('Máy đóng gói bột', 'Gói bột');
    let h = '<table><tr><th>Máy</th><th>Số đo</th><th>Lần</th><th>Thấp – cao</th><th>Ngoài</th></tr>';
    sd.forEach((x) => {
      const ngoai = [x.duoi ? `${x.duoi} dưới` : '', x.tren ? `${x.tren} trên` : ''].filter(Boolean).join(' · ');
      h += `<tr><td title="${esc(x.ten_may)}">${esc(mayNgan(x.ten_may))}</td>`
        + `<td title="${esc(x.ten)}">${esc(NGAN[x.f] || x.ten)}</td><td>${x.so_lan}</td>`
        + `<td>${so(x.thap)} – ${so(x.cao)} ${esc(x.dv)}</td>`
        + `<td class="${ngoai ? 'sx-qc-o-loi' : 'sx-qc-o-xong'}" title="ngưỡng ${so(x.lo)} – ${so(x.hi)} ${esc(x.dv)}">`
        + `${ngoai || '0'}</td></tr>`;
    });
    const bang = el('div', 'sx-qc-luoi');
    bang.innerHTML = `${h}</table>`;
    container.appendChild(bang);
    container.appendChild(el('div', 'sx-qc-goiy', 'Ngưỡng ở SX QC Setting. Nhiệt độ rang: dưới ngưỡng là sự cố oPRP, '
      + 'trên trần vận hành là cảnh báo. Máy gói bột chưa có mã (chờ Cơ điện) — hiện theo số thứ tự.'));
  }

  // ── nhật ký cát rang của tháng (W12: Ban ISO xem cuối tháng) ─────────────
  container.appendChild(el('div', 'sx-qc-buoc',
    '<span class="sx-qc-buoc-ten">Nhật ký cát rang (BM.08.03)</span>'));
  // D164 (W32): mỗi việc một dòng — đếm theo việc; số ngày cát đã dùng ở cuối kỳ do app đếm (ngày có rang).
  if (!cat.so_dong) {
    container.appendChild(khungTrong('Tháng này chưa có dòng nhật ký cát nào.'));
  } else {
    const box = el('div', 'sx-qc-chips');
    box.appendChild(chip(`${cat.so_dong} dòng${cat.so_cu ? ` (${cat.so_cu} dòng sổ cũ)` : ''}`));
    [['nhập', cat.so_nhap], ['thay toàn bộ', cat.so_lan_thay], ['bổ sung', cat.so_bo_sung], ['loại', cat.so_loai],
      ['vệ sinh', cat.so_ve_sinh]].forEach(([t, n]) => { if (n) box.appendChild(chip(`${t} ${n} lần`)); });
    box.appendChild(chip(cat.so_ngay_cuoi == null ? 'cuối kỳ: không có cát đang dùng'
      : `cuối kỳ: cát đã dùng ${cat.so_ngay_cuoi} ngày`, cat.so_ngay_cuoi == null ? 'han' : ''));
    if (cat.cam_quan_hong) box.appendChild(chip(`${cat.cam_quan_hong} lần cảm quan Không đạt`, 'han'));
    (cat.doi_nguon || []).forEach((x) => box.appendChild(chip(
      `đổi nguồn ${x.ncc} ${x.ngay.slice(8, 10)}/${x.ngay.slice(5, 7)}: kim loại nặng ${x.kln || 'CHƯA GỬI'}`
      + ` · lọ mẫu ${x.lo_mau ? '✓' : '✗'}`, x.kln === 'Đạt' && x.lo_mau ? '' : 'han')));
    container.appendChild(box);
  }
  const moCat = el('button', 'sx-btn sx-btn-ghost', 'MỞ NHẬT KÝ CÁT');
  moCat.type = 'button';
  moCat.addEventListener('click', () => { window.location.hash = '#/qc/cat'; });
  container.appendChild(moCat);

  // ── đánh dấu đã xem xét ─────────────────────────────────────────────
  // Một chữ ký cho cả lượt kiểm lẫn nhật ký cát của khoảng đang xem (W12).
  const nut = el('button', 'sx-btn sx-btn-primary sx-btn-big',
    `ĐÃ XEM XÉT ĐẾN ${esc(den)}`);
  nut.type = 'button';
  nut.disabled = !(kpi.chua_xem_xet || cat.chua_xem);
  nut.addEventListener('click', () => confirm2Step({
    title: 'Đánh dấu đã xem xét',
    message: `Ký xem xét ${kpi.chua_xem_xet} lượt${cat.chua_xem ? ` và ${cat.chua_xem} dòng nhật ký cát` : ''}`
      + ` từ ${tu} đến ${den}. `
      + 'Sau khi ký, các lượt này KHOÁ — không huỷ được nữa, kể cả bởi Ban ISO. '
      + 'Dòng nhật ký cát đã ký chỉ Ban ISO sửa (kết quả kim loại nặng / lọ mẫu vẫn ghi được). '
      + 'Sai sót phát hiện sau thì ghi phiếu sự cố loại "Hiệu chỉnh hồ sơ".',
    confirmLabel: 'XÁC NHẬN ĐÃ XEM XÉT',
    onConfirm: async () => {
      try {
        const kq = await call('sx.api.qc.review_rounds', { tu, den });
        toast(`Đã ký xem xét ${kq.so_luot} lượt${kq.so_cat ? ` · ${kq.so_cat} dòng nhật ký cát` : ''}`);
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

  // W09 (D138): danh sách nhà cung cấp được duyệt BM.07.02 — in từ dữ liệu Supplier.
  const nutNcc = el('button', 'sx-btn sx-btn-ghost', '🖨 NCC ĐƯỢC DUYỆT (BM.07.02)');
  nutNcc.type = 'button';
  nutNcc.addEventListener('click', async () => {
    nutNcc.disabled = true;
    try {
      const html = await call('sx.api.qc_ncc.in_ds_ncc');
      const w = window.open('', '_blank');
      if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
      w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
        + `<title>BM.07.02 — NCC được duyệt</title></head><body>${html}</body></html>`);
      w.document.close();
      w.focus();
      setTimeout(() => w.print(), 400);
    } catch (e) { toastErr(e.message); } finally { nutNcc.disabled = false; }
  });
  ho_so.appendChild(nutNcc);

  // W20 (D141): nhật ký cát rang BM.08.03 của tháng đang xem.
  const nutCat = el('button', 'sx-btn sx-btn-ghost', '🖨 NHẬT KÝ CÁT (BM.08.03)');
  nutCat.type = 'button';
  nutCat.addEventListener('click', async () => {
    nutCat.disabled = true;
    try {
      const html = await call('sx.api.qc_cat.in_bm0803', { thang: st.thang });
      const w = window.open('', '_blank');
      if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
      w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
        + `<title>BM.08.03 — ${st.thang}</title></head><body>${html}</body></html>`);
      w.document.close();
      w.focus();
      setTimeout(() => w.print(), 400);
    } catch (e) { toastErr(e.message); } finally { nutCat.disabled = false; }
  });
  ho_so.appendChild(nutCat);

  // W14 (D139): sổ kiểm xe BM.09.01 của tháng đang xem — gom từ hoá đơn bán + phiếu nhập mua.
  const nutXe = el('button', 'sx-btn sx-btn-ghost', '🖨 KIỂM XE THÁNG (BM.09.01)');
  nutXe.type = 'button';
  nutXe.addEventListener('click', async () => {
    nutXe.disabled = true;
    try {
      const html = await call('sx.api.qc_kiemxe.in_so_kiem_xe', { tu, den });
      const w = window.open('', '_blank');
      if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
      w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
        + `<title>BM.09.01 — ${tu} đến ${den}</title></head><body>${html}</body></html>`);
      w.document.close();
      w.focus();
      setTimeout(() => w.print(), 400);
    } catch (e) { toastErr(e.message); } finally { nutXe.disabled = false; }
  });
  ho_so.appendChild(nutXe);

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
