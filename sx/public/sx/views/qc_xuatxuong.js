// #/qc/xuatxuong — kiểm tra xuất xưởng theo lô, BM.08.04 (W08, D137; lần BH 01: W31, D159).
//
// Lô thành phẩm = (sản phẩm, HSD). Hàng đã vào hộp mà chưa nhập kho hiện ở "Lô chờ
// kiểm": QC bấm KIỂM → phiếu đúng bản giấy lần BH 01:
//   A. Hồ sơ của lô A1–A5 — app tra hồ sơ (lượt BM.08.01 ngày SX / nghiền / rang, sự cố liên
//      quan lô, nguyên liệu đã tiếp nhận, thử lạc B7, mẫu lưu) và GỢI Ý; QC vẫn tự bấm;
//   B. Kiểm thành phẩm B1–B6 — 5 mẫu ở 5 thùng: chạm ô mẫu đổi — → Đ → K; B2 ghi số cân (g);
//   C. Kết luận — Cho xuất xưởng / Giữ lại chờ xử lý / Không cho xuất (+ số phiếu BM.08.02).
// → GỬI DUYỆT. Trưởng Ban ISO / người được giao DUYỆT hoặc TRẢ LẠI — người đã kiểm lô không
// tự duyệt (chốt ở controller, cả Desk). Quản lý sản xuất ký ô thứ ba (không bắt buộc).
//
// Lô chưa "Cho xuất xưởng" thì thủ kho KHÔNG duyệt được phiếu nhập kho có lô đó, và không bán
// được — nên "Chờ duyệt" đứng trên cùng: mỗi phiếu nằm đó là hàng đang đứng ngoài kho.
// Phiếu trước D159 (8 mục tạm) mở bằng form cũ — giữ nguyên mục đã ghi.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';
import { chip, khungTrong, segment, tabLo } from '/assets/sx/sx/components/qcui.js';

const ngayVN = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const gioVN = (s) => (s ? `${ngayVN(s)} ${s.slice(11, 16)}` : '');
const KQ = ['Đạt', 'Không đạt', 'Không áp dụng'];
export const KET_LUAN = ['Cho xuất xưởng', 'Giữ lại chờ xử lý', 'Không cho xuất'];
const CHO_XUAT = KET_LUAN[0];
export const SO_MAU = 5;
const VONG = ['', 'Đ', 'K'];

/** Chạm một ô mẫu B1, B3–B6: — → Đ → K → —. Hàm THUẦN để test. */
export function vongMau(v) {
  return VONG[(VONG.indexOf(v || '') + 1) % VONG.length];
}

/** Kết luận dòng B theo 5 ô mẫu. Có mẫu K → Không đạt (ép: server chặn "Đạt" có mẫu K); đủ 5 Đ mà
 *  dòng còn trống → Đạt; còn lại giữ nguyên lựa chọn của QC. B2 (số cân) QC tự kết luận theo khối
 *  lượng ghi trên nhãn — app không biết sai số cho phép của từng quy cách. */
export function ketQuaDong(ma, mau, dang) {
  if (ma === 'B2') return dang || '';
  if (mau.includes('K')) return 'Không đạt';
  if (!dang && mau.length === SO_MAU && mau.every((x) => x === 'Đ')) return 'Đạt';
  return dang || '';
}

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
  const cho = p.ket_luan === CHO_XUAT;
  const lop = { 'Chờ duyệt': 'cho', 'Đã duyệt': cho ? 'dong' : 'mo', 'Trả lại': 'mo' }[p.trang_thai] || 'luu';
  const the = el('div', `sx-qc-sc sx-qc-sc-${lop}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(p.ten_san_pham || p.san_pham)} · HSD ${esc(ngayVN(p.hsd))}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(p.name));
  meta.appendChild(chip(p.trang_thai, p.trang_thai === 'Trả lại' ? 'han' : ''));
  if (p.ket_luan) meta.appendChild(chip(p.ket_luan, cho ? 'dong' : 'cao'));
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

function oChu(gt, onSet, khoa, goiY, dai = 140) {
  const n = el('input', 'sx-textarea sx-xx-gc');
  n.type = 'text';
  n.placeholder = goiY;
  n.value = gt || '';
  n.maxLength = dai;
  n.disabled = khoa;
  n.addEventListener('input', () => onSet(n.value));
  return n;
}

function oNgay(nhan, gt, onSet, khoa) {
  const o = el('label', 'sx-xx-ngay-o');
  o.appendChild(el('span', 'sx-qc-goiy', esc(nhan)));
  const n = el('input', 'sx-textarea');
  n.type = 'date';
  n.value = gt || '';
  n.disabled = khoa;
  n.addEventListener('change', () => onSet(n.value));
  o.appendChild(n);
  return o;
}

/** Chọn phiếu sự cố BM.08.02 trong các phiếu liên quan lô (app tra) — hoặc để trống. */
function chonSuCo(d, gt, onSet, khoa, trong) {
  const s = el('select', 'sx-textarea');
  const ds = [...(d.su_co_lo || [])];
  if (gt && !ds.some((x) => x.name === gt)) ds.unshift({ name: gt, trang_thai: '', quyet_dinh_sp: '', mo_ta: '' });
  [['', trong], ...ds.map((x) => [x.name, `${x.name}${x.trang_thai ? ` · ${x.trang_thai}` : ''}`
    + `${x.trang_thai ? ` · ${x.quyet_dinh_sp || 'chưa quyết định SP'}` : ''}${x.mo_ta ? ` — ${x.mo_ta}` : ''}`])]
    .forEach(([v, t]) => {
      const o = el('option', null, esc(t));
      o.value = v;
      if ((gt || '') === v) o.selected = true;
      s.appendChild(o);
    });
  s.disabled = khoa;
  s.addEventListener('change', () => onSet(s.value));
  return s;
}

function dongA(r, f, d, khoa) {
  const o = el('div', 'sx-xx-muc');
  o.appendChild(el('div', 'sx-xx-muc-ten', `<b>${esc(r.ma)}</b> ${esc(r.noi_dung)}`));
  o.appendChild(el('div', 'sx-qc-goiy', `Yêu cầu: ${esc(r.yeu_cau)}`));
  if (r.goi_y || r.can_cu) {
    o.appendChild(el('div', 'sx-xx-goiy',
      `${r.goi_y ? `<b>Gợi ý: ${esc(r.goi_y === 'Không áp dụng' ? 'KAD' : r.goi_y)}</b> · ` : ''}${esc(r.can_cu)}`));
  }
  const lua = (r.ma === 'A4' ? KQ : KQ.slice(0, 2)).map((v) => ({ v, ten: v === 'Không áp dụng' ? 'KAD' : v }));
  o.appendChild(segment(lua, r.ket_qua, (v) => { r.ket_qua = v; }, khoa, true));
  if (r.ma === 'A1') {
    const hang = el('div', 'sx-xx-ngay');
    hang.appendChild(oNgay('Ngày nghiền bột đậu', f.ngay_nghien, (v) => { f.ngay_nghien = v; }, khoa));
    hang.appendChild(oNgay('Ngày rang đỗ', f.ngay_rang, (v) => { f.ngay_rang = v; }, khoa));
    o.appendChild(hang);
  }
  if (r.ma === 'A2' && ((d.su_co_lo || []).length || r.su_co)) {
    o.appendChild(chonSuCo(d, r.su_co, (v) => { r.su_co = v; }, khoa, '— số phiếu BM.08.02 —'));
  }
  o.appendChild(oChu(r.ghi_chu, (v) => { r.ghi_chu = v; }, khoa, 'ghi chú'));
  return o;
}

function dongB(r, khoa) {
  const o = el('div', 'sx-xx-muc');
  o.appendChild(el('div', 'sx-xx-muc-ten', `<b>${esc(r.ma)}</b> ${esc(r.noi_dung)}`));
  o.appendChild(el('div', 'sx-qc-goiy', esc(r.yeu_cau)));
  const so = r.ma === 'B2';
  const hang = el('div', 'sx-xx-mau');
  const kq = el('div', 'sx-xx-kq');
  const veKq = () => {
    kq.innerHTML = '';
    kq.appendChild(segment(['Đạt', 'Không đạt'], r.ket_qua, (v) => { r.ket_qua = v; }, khoa, true));
  };
  const veO = (i, b) => {
    const v = r.mau[i] || '';
    b.innerHTML = `<span class="sx-xx-mau-so">${i + 1}</span><span class="sx-xx-mau-v">${esc(v || '—')}</span>`;
    b.classList.toggle('sx-xx-mau-k', v === 'K');
    b.classList.toggle('sx-xx-mau-d', !!v && v !== 'K');
  };
  for (let i = 0; i < SO_MAU; i += 1) {
    const b = el('button', 'sx-xx-mau-o');
    b.type = 'button';
    b.disabled = khoa;
    veO(i, b);
    b.addEventListener('click', () => {
      if (so) {
        openNumpad({
          kicker: `${r.ma} · Mẫu ${i + 1}`, title: 'Khối lượng tịnh (g)', initial: r.mau[i] || '',
          allowDecimal: true, unitLabel: 'G',
          onOk: (n) => { r.mau[i] = n > 0 ? String(n) : ''; veO(i, b); },
        });
        return;
      }
      r.mau[i] = vongMau(r.mau[i]);
      veO(i, b);
      const moi = ketQuaDong(r.ma, r.mau, r.ket_qua);
      if (moi !== r.ket_qua) { r.ket_qua = moi; veKq(); }
    });
    hang.appendChild(b);
  }
  o.appendChild(hang);
  o.appendChild(el('div', 'sx-qc-goiy', so ? 'Chạm ô ghi số cân (g) · kết luận dòng:' : 'Chạm ô: — → Đ → K · kết luận dòng:'));
  veKq();
  o.appendChild(kq);
  o.appendChild(oChu(r.ghi_chu, (v) => { r.ghi_chu = v; }, khoa, 'ghi chú (mẫu nào, lỗi gì)'));
  return o;
}

function moPhieu(d, api) {
  if (!d.moi) { moPhieuCu(d, api); return; }
  const m = openModal({ kicker: `BM.08.04 · ${d.name}`,
    title: `${d.ten_san_pham || d.san_pham} · HSD ${ngayVN(d.hsd)}` });
  const khoa = !d.sua;
  const f = {
    ds_muc: d.ds_muc.map((r) => ({ ...r, mau: [...(r.mau || [])] })),
    ket_luan: d.ket_luan || '', ghi_chu: d.ghi_chu || '', quy_cach: d.quy_cach || '',
    ngay_nghien: d.ngay_nghien || '', ngay_rang: d.ngay_rang || '', su_co: d.su_co || '',
  };
  m.body.appendChild(el('div', 'sx-modal-msg',
    `${d.nsx ? `NSX ${esc(ngayVN(d.nsx))} · ` : ''}${d.so_luong ? `${esc(String(d.so_luong))} ${esc(d.dvt || '')} · ` : ''}`
    + `<b>${esc(d.trang_thai)}</b>${d.qc_kiem ? ` · QC ${esc(d.qc_kiem)}` : ''}`));
  if (d.trang_thai === 'Trả lại' && d.y_kien_duyet) {
    m.body.appendChild(el('div', 'sx-warn-text', `Ban ISO trả lại: ${esc(d.y_kien_duyet)}`));
  }
  m.body.appendChild(el('div', 'sx-field-label', 'Quy cách'));
  m.body.appendChild(oChu(f.quy_cach, (v) => { f.quy_cach = v; }, khoa, 'vd Hộp 250 g, thùng 20 hộp'));

  m.body.appendChild(el('div', 'sx-field-label sx-xx-khoi', 'A. Hồ sơ của lô'));
  f.ds_muc.filter((r) => r.ma[0] === 'A').forEach((r) => m.body.appendChild(dongA(r, f, d, khoa)));
  const goi = () => JSON.stringify({
    ds_muc: f.ds_muc.map((r) => ({
      ma: r.ma, ket_qua: r.ket_qua, ghi_chu: r.ghi_chu,
      ...(r.ma[0] === 'B' ? { mau: r.mau } : {}), ...(r.ma === 'A2' ? { su_co: r.su_co } : {}),
    })),
    ket_luan: f.ket_luan, ghi_chu: f.ghi_chu, quy_cach: f.quy_cach,
    ngay_nghien: f.ngay_nghien, ngay_rang: f.ngay_rang,
    ...(f.ket_luan && f.ket_luan !== CHO_XUAT ? { su_co: f.su_co } : {}),
  });
  if (!khoa) {
    m.body.appendChild(el('div', 'sx-qc-goiy', 'Sửa ngày nghiền / ngày rang, hoặc vừa lấy mẫu lưu → tra lại:'));
    const tra = el('button', 'sx-btn sx-btn-ghost', '↻ TRA LẠI HỒ SƠ LÔ');
    tra.type = 'button';
    tra.addEventListener('click', async () => {
      tra.disabled = true;
      try {
        const moi = await api.call('sx.api.xuatxuong.tra_ho_so', { name: d.name, payload: goi() });
        m.close();
        moPhieu(moi, api);
      } catch (e) { tra.disabled = false; toastErr(e.message); }
    });
    m.body.appendChild(tra);
  }

  m.body.appendChild(el('div', 'sx-field-label sx-xx-khoi',
    `B. Kiểm thành phẩm — ${SO_MAU} mẫu (hộp / túi) ở ${SO_MAU} thùng khác nhau`));
  f.ds_muc.filter((r) => r.ma[0] === 'B').forEach((r) => m.body.appendChild(dongB(r, khoa)));

  m.body.appendChild(el('div', 'sx-field-label sx-xx-khoi', 'C. Kết luận'));
  const xl = el('div', 'sx-qc-goiy');
  const scBox = el('div', 'sx-xx-sc');
  const veC = () => {
    xl.textContent = f.ket_luan ? ((d.xu_ly || {})[f.ket_luan] || '') : '';
    scBox.innerHTML = '';
    if (f.ket_luan && f.ket_luan !== CHO_XUAT) {
      scBox.appendChild(el('div', 'sx-qc-goiy', 'Phiếu sự cố BM.08.02 (bắt buộc):'));
      scBox.appendChild(chonSuCo(d, f.su_co, (v) => { f.su_co = v; }, khoa,
        '— app lập phiếu mới lúc gửi duyệt —'));
    }
  };
  const seg = segment(KET_LUAN, f.ket_luan, (v) => { f.ket_luan = v; veC(); }, khoa, true);
  seg.classList.add('sx-xx-kl');
  m.body.appendChild(seg);
  m.body.appendChild(xl);
  m.body.appendChild(scBox);
  veC();
  const gc = el('textarea', 'sx-textarea');
  gc.rows = 2;
  gc.placeholder = 'Ghi chú của QC';
  gc.value = f.ghi_chu;
  gc.disabled = khoa;
  gc.addEventListener('input', () => { f.ghi_chu = gc.value; });
  m.body.appendChild(gc);

  m.body.appendChild(el('div', 'sx-xx-ky',
    `<div><b>QC kiểm</b> ${esc(d.qc_kiem || '—')}${d.kiem_luc ? ` · ${esc(gioVN(d.kiem_luc))}` : ''}</div>`
    + `<div><b>Quản lý sản xuất</b> ${d.qlsx ? `${esc(d.qlsx)} · ${esc(gioVN(d.qlsx_luc))}` : 'chưa ký'}</div>`
    + `<div><b>Người duyệt</b> ${d.trang_thai === 'Đã duyệt' && d.nguoi_duyet
      ? `${esc(d.nguoi_duyet)} · ${esc(gioVN(d.duyet_luc))}` : 'chưa duyệt'}</div>`));
  nutPhieu(m, d, api, goi);
}

function nutPhieu(m, d, api, goi) {
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
  if (d.ky_qlsx) {
    nut('KÝ — QUẢN LÝ SẢN XUẤT', 'sx-btn-ghost', () => api.call('sx.api.xuatxuong.ky_qlsx', { name: d.name }),
      'Đã ký ô Quản lý sản xuất');
  }
  if (d.duyet) {
    const yk = el('textarea', 'sx-textarea');
    yk.rows = 2;
    yk.placeholder = 'Ý kiến (bắt buộc khi trả lại)';
    m.body.appendChild(yk);
    const cho = d.ket_luan === CHO_XUAT;
    nut(cho ? 'DUYỆT — CHO XUẤT XƯỞNG' : `DUYỆT KẾT LUẬN ${String(d.ket_luan || '').toUpperCase()}`, 'sx-btn-primary',
      () => api.call('sx.api.xuatxuong.duyet_phieu', { name: d.name, dong_y: 1, y_kien: yk.value }),
      cho ? 'Đã duyệt — lô nhập kho / bán được' : `Đã duyệt — lô đứng ngoài kho, xử lý theo ${d.su_co || 'phiếu sự cố'}`);
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

// Phiếu trước D159 (8 mục tạm "1".."8") — form cũ, kết luận theo bộ chữ mới.
function moPhieuCu(d, api) {
  const m = openModal({ kicker: `BM.08.04 · ${d.name} · mẫu tạm`,
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
    o.appendChild(oChu(r.ghi_chu, (v) => { r.ghi_chu = v; }, !d.sua, 'ghi chú / số đo'));
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
  const seg = segment(KET_LUAN, f.ket_luan, (v) => { f.ket_luan = v; }, !d.sua, true);
  seg.classList.add('sx-xx-kl');
  m.body.appendChild(seg);
  const gc = el('textarea', 'sx-textarea');
  gc.rows = 2;
  gc.placeholder = 'Ghi chú của QC';
  gc.value = f.ghi_chu;
  gc.disabled = !d.sua;
  gc.addEventListener('input', () => { f.ghi_chu = gc.value; });
  m.body.appendChild(gc);
  nutPhieu(m, d, api, () => JSON.stringify(f));
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
