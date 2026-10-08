// #/qc/xuatxuong — kiểm tra xuất xưởng theo lô, BM.08.04 (W08, D137).
//
// Lô thành phẩm = (sản phẩm, HSD). Hàng đã vào hộp mà chưa nhập kho hiện ở "Lô chờ
// kiểm": QC bấm KIỂM → phiếu tự tra hồ sơ lô (lượt BM.08.01 ngày NSX, sự cố mở, mẫu
// lưu) → chấm từng mục → GỬI DUYỆT. Trưởng Ban ISO / người được giao DUYỆT hoặc TRẢ
// LẠI — người đã kiểm lô không tự duyệt (chốt ở controller, cả Desk).
//
// Lô chưa duyệt thì thủ kho KHÔNG duyệt được phiếu nhập kho có lô đó, và không bán
// được — nên "Chờ duyệt" đứng trên cùng: mỗi phiếu nằm đó là hàng đang đứng ngoài kho.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';
import { chip, khungTrong, segment, tabLo } from '/assets/sx/sx/components/qcui.js';

const ngayVN = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const KQ = ['Đạt', 'Không đạt', 'Không áp dụng'];

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.xuatxuong.ds_xuat_xuong', {});
  container.innerHTML = '';
  container.appendChild(tabLo('xuatxuong'));
  if (!dl.chan) {
    container.appendChild(el('div', 'sx-warn-text',
      'Chốt BM.08.04 đang TẮT (SX Settings) — lô chưa duyệt vẫn nhập kho / bán được.'));
  }

  const theo = (tt) => dl.phieu.filter((p) => p.trang_thai === tt);
  const khoi = (tieuDe, ds, ve, trong) => {
    container.appendChild(el('div', 'sx-field-label sx-xx-khoi', `${esc(tieuDe)} (${ds.length})`));
    const box = el('div', 'sx-qc-than');
    if (!ds.length && trong) box.appendChild(khungTrong(trong));
    ds.forEach((x) => box.appendChild(ve(x)));
    container.appendChild(box);
  };

  khoi('Chờ duyệt', theo('Chờ duyệt'), (p) => thePhieu(p, dl, api),
    dl.duoc_duyet ? 'Không có phiếu nào chờ duyệt.' : null);
  khoi('Lô chờ kiểm', dl.cho_kiem, (x) => theCho(x, dl, api),
    'Không có lô nào chờ kiểm (hàng đã vào hộp nhưng chưa nhập kho).');
  const dang = [...theo('Trả lại'), ...theo('Nháp')];
  if (dang.length) khoi('QC đang kiểm / bị trả lại', dang, (p) => thePhieu(p, dl, api));
  const xong = theo('Đã duyệt');
  if (xong.length) khoi('Đã duyệt (30 ngày)', xong, (p) => thePhieu(p, dl, api));
}

function theCho(x, dl, api) {
  const the = el('div', 'sx-qc-sc sx-qc-sc-cho');
  the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(x.ten)} · HSD ${esc(ngayVN(x.hsd))}`));
  const meta = el('div', 'sx-qc-sc-meta');
  if (x.nsx) meta.appendChild(el('span', null, `NSX ${esc(ngayVN(x.nsx))}`));
  if (x.so_luong) meta.appendChild(chip(`${x.so_luong} ${x.dvt || ''}`.trim()));
  meta.appendChild(chip(x.nguon));
  the.appendChild(meta);
  if (dl.duoc_ghi) {
    const b = el('button', 'sx-btn sx-btn-primary', 'KIỂM BM.08.04');
    b.type = 'button';
    b.addEventListener('click', async () => {
      b.disabled = true;
      try {
        const d = await api.call('sx.api.xuatxuong.lap_phieu',
          { san_pham: x.item, hsd: x.hsd, so_luong: x.so_luong || null, dvt: x.dvt || null });
        moPhieu(d, api);
      } catch (e) { toastErr(e.message); }
      b.disabled = false;
    });
    const nut = el('div', 'sx-qc-lm-nut');
    nut.appendChild(b);
    the.appendChild(nut);
  }
  return the;
}

function thePhieu(p, dl, api) {
  const lop = { 'Chờ duyệt': 'cho', 'Đã duyệt': p.ket_luan === 'Đạt' ? 'dong' : 'mo', 'Trả lại': 'mo' }[p.trang_thai] || 'luu';
  const the = el('div', `sx-qc-sc sx-qc-sc-${lop}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(p.ten_san_pham || p.san_pham)} · HSD ${esc(ngayVN(p.hsd))}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(p.name));
  meta.appendChild(chip(p.trang_thai, p.trang_thai === 'Trả lại' ? 'han' : ''));
  if (p.ket_luan) meta.appendChild(chip(p.ket_luan, p.ket_luan === 'Đạt' ? 'dong' : 'cao'));
  if (p.qc_kiem) meta.appendChild(el('span', null, `QC ${esc(p.qc_kiem.split('@')[0])}`));
  if (p.nguoi_duyet) meta.appendChild(el('span', null, `duyệt ${esc(p.nguoi_duyet.split('@')[0])}`));
  the.appendChild(meta);
  if (p.trang_thai === 'Trả lại' && p.y_kien_duyet) {
    the.appendChild(el('div', 'sx-qc-goiy sx-lm-giu', `Trả lại: ${esc(p.y_kien_duyet)}`));
  }
  if (p.su_co) the.appendChild(el('div', 'sx-qc-goiy', `Phiếu sự cố: <b>${esc(p.su_co)}</b>`));
  const b = el('button', 'sx-btn sx-btn-ghost', p.trang_thai === 'Chờ duyệt' && dl.duoc_duyet ? 'XEM & DUYỆT' : 'MỞ PHIẾU');
  b.type = 'button';
  b.addEventListener('click', async () => {
    try { moPhieu(await api.call('sx.api.xuatxuong.xem_phieu', { name: p.name }), api); } catch (e) {
      toastErr(e.message);
    }
  });
  const nut = el('div', 'sx-qc-lm-nut');
  nut.appendChild(b);
  the.appendChild(nut);
  return the;
}

function moPhieu(d, api) {
  const m = openModal({ kicker: `BM.08.04 · ${d.name}`,
    title: `${d.ten_san_pham || d.san_pham} · HSD ${ngayVN(d.hsd)}` });
  const f = { ds_muc: d.ds_muc.map((r) => ({ ...r })), ket_luan: d.ket_luan || '', so_mau: d.so_mau || 0,
    ghi_chu: d.ghi_chu || '' };
  m.body.appendChild(el('div', 'sx-modal-msg',
    `${d.nsx ? `NSX ${esc(ngayVN(d.nsx))} · ` : ''}${d.so_luong ? `${esc(String(d.so_luong))} ${esc(d.dvt || '')} · ` : ''}`
    + `<b>${esc(d.trang_thai)}</b>${d.qc_kiem ? ` · QC ${esc(d.qc_kiem)}` : ''}`));
  if (d.ho_so) m.body.appendChild(el('div', 'sx-xx-hoso', esc(d.ho_so)));
  if (d.trang_thai === 'Trả lại' && d.y_kien_duyet) {
    m.body.appendChild(el('div', 'sx-warn-text', `Ban ISO trả lại: ${esc(d.y_kien_duyet)}`));
  }

  f.ds_muc.forEach((r) => {
    const o = el('div', 'sx-xx-muc');
    o.appendChild(el('div', 'sx-xx-muc-ten', `<b>${esc(r.ma)}</b> ${esc(r.noi_dung)}`));
    o.appendChild(segment(KQ.map((v) => ({ v, ten: v === 'Không áp dụng' ? 'KAD' : v })), r.ket_qua,
      (v) => { r.ket_qua = v; }, !d.sua, true));
    const gc = el('input', 'sx-textarea sx-xx-gc');
    gc.type = 'text';
    gc.placeholder = 'ghi chú / số đo';
    gc.value = r.ghi_chu;
    gc.disabled = !d.sua;
    gc.addEventListener('input', () => { r.ghi_chu = gc.value; });
    o.appendChild(gc);
    m.body.appendChild(o);
  });

  m.body.appendChild(el('div', 'sx-field-label', 'Số mẫu đã kiểm'));
  const sm = el('button', 'sx-qc-oso-khung', '');
  sm.type = 'button';
  const veSm = () => { sm.innerHTML = `<span class="sx-qc-oso-val">${f.so_mau || '—'}</span><span class="sx-qc-oso-dv">mẫu</span>`; };
  veSm();
  sm.disabled = !d.sua;
  sm.addEventListener('click', () => openNumpad({
    kicker: 'BM.08.04', title: 'Số mẫu đã kiểm', initial: String(f.so_mau || ''), allowDecimal: false,
    unitLabel: 'MẪU', onOk: (n) => { f.so_mau = Math.max(0, Math.round(n)); veSm(); },
  }));
  m.body.appendChild(sm);
  m.body.appendChild(el('div', 'sx-field-label', 'Kết luận'));
  m.body.appendChild(segment(['Đạt', 'Không đạt'], f.ket_luan, (v) => { f.ket_luan = v; }, !d.sua, true));
  const gc = el('textarea', 'sx-textarea');
  gc.rows = 2;
  gc.placeholder = 'Ghi chú của QC';
  gc.value = f.ghi_chu;
  gc.disabled = !d.sua;
  gc.addEventListener('input', () => { f.ghi_chu = gc.value; });
  m.body.appendChild(gc);

  const goi = () => JSON.stringify(f);
  const lam = async (b, fn, xong) => {
    b.disabled = true;
    try { await fn(); toast(xong); m.close(); render(api); } catch (e) { b.disabled = false; toastErr(e.message); }
  };
  const nut = (nhan, lop, fn, xong) => {
    const b = el('button', `sx-btn ${lop} sx-btn-big`, nhan);
    b.type = 'button';
    b.addEventListener('click', () => lam(b, fn, xong));
    m.body.appendChild(b);
    return b;
  };
  if (d.sua) {
    nut('LƯU', 'sx-btn-ghost', () => api.call('sx.api.xuatxuong.luu_phieu', { name: d.name, payload: goi() }), 'Đã lưu');
    nut('GỬI DUYỆT', 'sx-btn-primary', () => api.call('sx.api.xuatxuong.gui_duyet', { name: d.name, payload: goi() }),
      'Đã gửi Ban ISO duyệt');
  }
  if (d.tu_kiem) {
    m.body.appendChild(el('div', 'sx-qc-goiy',
      'Bạn là người kiểm lô này — không tự duyệt. Phiếu chờ Trưởng Ban ISO / người được giao.'));
    nut('RÚT LẠI ĐỂ SỬA', 'sx-btn-ghost', () => api.call('sx.api.xuatxuong.rut_lai', { name: d.name }), 'Đã rút về Nháp');
  }
  if (d.duyet) {
    const yk = el('textarea', 'sx-textarea');
    yk.rows = 2;
    yk.placeholder = 'Ý kiến (bắt buộc khi trả lại)';
    m.body.appendChild(yk);
    nut(d.ket_luan === 'Đạt' ? 'DUYỆT — CHO XUẤT XƯỞNG' : 'DUYỆT KẾT LUẬN KHÔNG ĐẠT', 'sx-btn-primary',
      () => api.call('sx.api.xuatxuong.duyet_phieu', { name: d.name, dong_y: 1, y_kien: yk.value }),
      d.ket_luan === 'Đạt' ? 'Đã duyệt — lô nhập kho / bán được' : 'Đã duyệt — lô không đạt, đã lập phiếu sự cố');
    nut('TRẢ LẠI QC', 'sx-btn-ghost', async () => {
      if (!yk.value.trim()) throw new Error('Ghi ý kiến cho QC biết kiểm lại gì.');
      await api.call('sx.api.xuatxuong.duyet_phieu', { name: d.name, dong_y: 0, y_kien: yk.value });
    }, 'Đã trả lại QC');
  }
  const inP = el('button', 'sx-btn sx-btn-ghost', '🖨 IN PHIẾU');
  inP.type = 'button';
  inP.addEventListener('click', () => inPhieu(d.name, api));
  m.body.appendChild(inP);
}

// Cửa sổ mới, tự khai charset (about:blank không thừa kế) — cùng cách in tờ BM.08.01.
async function inPhieu(name, api) {
  try {
    const html = await api.call('sx.api.xuatxuong.in_phieu', { name });
    const w = window.open('', '_blank');
    if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
      + `<title>BM.08.04 — ${esc(name)}</title></head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 250);
  } catch (e) { toastErr(e.message); }
}
