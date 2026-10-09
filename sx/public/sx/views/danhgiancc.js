// #/so/BM.07.01 — phiếu đánh giá nhà cung cấp BM.07.01 (W44, D173). Mở từ thẻ BM.07.01 của màn Sổ (so.js nạp màn
// này khi vào đúng mã).
//
//   #/so/BM.07.01            việc của bạn (chờ QC ký / chờ Giám đốc duyệt / phiếu trả lại, nháp), nhà cung cấp (đã vào
//                            BM.07.02 chưa, phiếu đã duyệt gần nhất, hạn đánh giá lại) + nút ĐÁNH GIÁ, phiếu gần đây.
//   #/so/BM.07.01/<phiếu>    một phiếu: đầu phiếu, phần A (Có / Không / KAD, số, hiệu lực — app tự điền từ hồ sơ NCC),
//                            phần B (chọn mức điểm như giấy), tổng + kết luận app tính, ba ô ký; nút theo quyền:
//                            LƯU, GỬI, QC KÝ, DUYỆT (phiếu Xem xét: Giám đốc chọn Chấp nhận / Không chấp nhận),
//                            TRẢ LẠI, IN, XOÁ.
// Luật chấm, kết luận: sx/qc/danh_gia_ncc.py — server tính lại mọi lần lưu; số trên màn chỉ để nhìn.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment } from '/assets/sx/sx/components/qcui.js';

const API = 'sx.api.qc_danhgiancc';
export const MA = 'BM.07.01';
export const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const KIEU_TT = { 'Nháp': '', 'Chờ QC': 'oprp', 'Chờ duyệt': 'oprp', 'Đã duyệt': 'dong', 'Trả lại': 'cao' };
const KIEU_KL = { 'Chấp nhận': 'dong', 'Xem xét': 'oprp', 'Loại bỏ': 'cao' };

function inHtml(html, tieuDe) {
  const w = window.open('', '_blank');
  if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
  w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>${esc(tieuDe)}</title>`
    + `</head><body>${html}</body></html>`);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 400);
}

function nut(chu, lop, f) {
  const b = el('button', `sx-btn ${lop}`, esc(chu));
  b.type = 'button';
  b.addEventListener('click', f);
  return b;
}

/** Chữ tình trạng đánh giá của một NCC: phiếu duyệt gần nhất + hạn đánh giá lại. */
export function tinhTrang(s) {
  const t = s.danh_gia;
  if (!t) return { chu: s.duyet ? 'đã duyệt trước W44 — chưa có phiếu BM.07.01' : 'chưa đánh giá', kieu: s.duyet ? 'oprp' : '' };
  if (t.ket_qua === 'Loại bỏ') return { chu: `Loại bỏ (${ngayDu(t.ngay)})`, kieu: 'cao' };
  if (t.con !== null && t.con < 0) return { chu: `quá hạn đánh giá lại ${ngayDu(t.han)}`, kieu: 'cao' };
  if (t.con !== null && t.con <= 30) return { chu: `đánh giá lại trước ${ngayDu(t.han)} (còn ${t.con} ngày)`, kieu: 'han' };
  return { chu: `Chấp nhận · hạn ${ngayDu(t.han)}`, kieu: 'dong' };
}

export async function render(ctx) {
  const { call, phieu } = ctx;
  if (phieu) vePhieu(ctx, await call(`${API}.xem`, { name: phieu }));
  else veDanhSach(ctx, await call(`${API}.ds`, {}));
}

// ── Danh sách ────────────────────────────────────────────────────────────────────────────────

export function veDanhSach(ctx, dl) {
  const { container } = ctx;
  const top = el('div', 'sx-qc-top');
  const dau = el('div', null);
  dau.style.flex = '1';
  dau.style.minWidth = '0';
  const t1 = el('div', 'sx-qc-ngay');
  const ve = el('a', 'sx-tl-ten', '‹ Sổ');
  ve.href = '#/so';
  t1.appendChild(ve);
  t1.appendChild(el('span', null, ` · ${MA}`));
  dau.appendChild(t1);
  dau.appendChild(el('div', 'sx-qc-ai', 'Phiếu đánh giá nhà cung cấp · QT.07 — Mua hàng chấm, QC ký (loại 1), '
    + 'Giám đốc duyệt'));
  top.appendChild(dau);
  container.appendChild(top);

  if (dl.viec.length) {
    container.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">Việc của bạn</span>'));
    dl.viec.forEach((p) => container.appendChild(thePhieu(p)));
  }

  container.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">Nhà cung cấp</span>'));
  const tim = el('input', 'sx-textarea');
  tim.type = 'search';
  tim.placeholder = 'Tìm nhà cung cấp…';
  container.appendChild(tim);
  const ds = el('div', 'sx-dg-ds');
  container.appendChild(ds);
  const veNcc = () => {
    ds.innerHTML = '';
    const k = tim.value.trim().toLowerCase();
    const cua = dl.ncc.filter((s) => !k || `${s.name} ${s.ten}`.toLowerCase().includes(k));
    if (!cua.length) ds.appendChild(khungTrong('Không có nhà cung cấp nào (đã phân loại, trừ dịch vụ).'));
    cua.forEach((s) => ds.appendChild(theNcc(ctx, dl, s)));
  };
  tim.addEventListener('input', veNcc);
  veNcc();

  if (dl.phieu.length) {
    container.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">Phiếu gần đây</span>'));
    dl.phieu.slice(0, 15).forEach((p) => container.appendChild(thePhieu(p)));
  }
}

function thePhieu(p) {
  const a = el('a', `sx-qc-sc ${p.trang_thai === 'Đã duyệt' ? 'sx-qc-sc-dong' : 'sx-qc-sc-cho'}`);
  a.href = `#/so/${MA}/${encodeURIComponent(p.name)}`;
  a.appendChild(el('div', 'sx-qc-sc-ten', `<span class="sx-tl-ma">${esc(p.name)}</span> ${esc(p.ten_ncc || p.supplier)}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(p.trang_thai, KIEU_TT[p.trang_thai] || ''));
  if (p.ket_qua) meta.appendChild(chip(p.ket_qua, KIEU_KL[p.ket_qua] || ''));
  else if (p.ket_luan) meta.appendChild(chip(`app tính: ${p.ket_luan}`, KIEU_KL[p.ket_luan] || ''));
  meta.appendChild(el('span', null, esc(`${p.hinh_thuc} · ${ngayDu(p.ngay)}${p.tong ? ` · ${p.tong} điểm` : ''}`)));
  a.appendChild(meta);
  return a;
}

function theNcc(ctx, dl, s) {
  const tt = tinhTrang(s);
  const the = el('div', `sx-qc-sc ${tt.kieu === 'cao' || tt.kieu === 'han' ? 'sx-qc-sc-cho' : 'sx-qc-sc-dong'}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', `<span class="sx-tl-ma">${esc(s.name)}</span> ${esc(s.ten)}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(s.duyet ? 'đã duyệt BM.07.02' : 'chưa vào BM.07.02', s.duyet ? 'dong' : ''));
  meta.appendChild(chip(tt.chu, tt.kieu));
  if (s.loai) meta.appendChild(el('span', null, esc(`${s.loai}${s.nguon ? ` · ${s.nguon}` : ''}`)));
  the.appendChild(meta);
  if (s.dang_mo) {
    const a = el('a', 'sx-qc-goiy', `Phiếu đang mở: ${esc(s.dang_mo)} ›`);
    a.href = `#/so/${MA}/${encodeURIComponent(s.dang_mo)}`;
    the.appendChild(a);
  } else if (dl.quyen.lap) {
    const hang = el('div', 'sx-qc-chips sx-tb-nut');
    hang.appendChild(nut('ĐÁNH GIÁ', 'sx-btn-primary', () => moLap(ctx, dl, s)));
    the.appendChild(hang);
  }
  return the;
}

/** Chọn hình thức rồi lập phiếu (phần A tự điền; đánh giá lại có gợi ý điểm I). */
export function moLap(ctx, dl, s) {
  const m = openModal({ kicker: `${MA} · lập phiếu`, title: s.ten });
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Hình thức đánh giá'));
  let ht = s.danh_gia ? dl.hinh_thuc[1] : dl.hinh_thuc[0];
  m.body.appendChild(segment(dl.hinh_thuc, ht, (v) => { ht = v || ht; }, false));
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Phần A tự điền từ hồ sơ nhà cung cấp (Supplier → hồ sơ NCC) — xem lại '
    + 'từng mục. Đánh giá lại: app gợi ý điểm chất lượng từ các lô nhận 12 tháng.'));
  const ok = nut('LẬP PHIẾU', 'sx-btn-primary sx-btn-big', async () => {
    ok.disabled = true;
    try {
      const p = await ctx.call(`${API}.lap`, { supplier: s.name, hinh_thuc: ht });
      m.close();
      window.location.hash = `#/so/${MA}/${encodeURIComponent(p.name)}`;
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

// ── Một phiếu ────────────────────────────────────────────────────────────────────────────────

export function vePhieu(ctx, d) {
  const { container, call } = ctx;
  const q = d.quyen;
  const sua = q.sua || q.qc_ky;           // QC cùng chấm khi phiếu chờ QC
  const doi = {};                          // ô đổi chưa lưu
  const a = {};                            // phần A đổi chưa lưu: {tt: {ket_qua, so_ngay, hieu_luc}}
  const lai = () => ctx.lai();

  const top = el('div', 'sx-qc-top');
  const dau = el('div', null);
  dau.style.flex = '1';
  dau.style.minWidth = '0';
  const t1 = el('div', 'sx-qc-ngay');
  const ve = el('a', 'sx-tl-ten', `‹ ${MA}`);
  ve.href = `#/so/${MA}`;
  t1.appendChild(ve);
  t1.appendChild(el('span', null, ` · ${d.name}`));
  dau.appendChild(t1);
  dau.appendChild(el('div', 'sx-qc-ai', esc(`${d.ten_ncc} (${d.supplier})`)));
  top.appendChild(dau);
  container.appendChild(top);
  const tt = el('div', 'sx-qc-chips');
  tt.appendChild(chip(d.trang_thai, KIEU_TT[d.trang_thai] || ''));
  if (d.ket_qua) tt.appendChild(chip(`Kết quả: ${d.ket_qua}`, KIEU_KL[d.ket_qua] || ''));
  if (d.han_danh_gia_lai) tt.appendChild(chip(`hạn đánh giá lại ${ngayDu(d.han_danh_gia_lai)}`, 'han'));
  container.appendChild(tt);
  if (d.y_kien_gd || d.y_kien_qc) {
    container.appendChild(el('div', 'sx-attp-viec sx-attp-viec-thuong', esc([d.y_kien_qc ? `QC: ${d.y_kien_qc}` : '',
      d.y_kien_gd ? `Giám đốc: ${d.y_kien_gd}` : ''].filter(Boolean).join(' · '))));
  }

  // Đầu phiếu
  container.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">Đầu phiếu</span>'));
  const khoiDau = el('div', 'sx-dg-khoi');
  [['mat_hang', 'Mặt hàng cung cấp'], ['dia_chi', 'Địa chỉ'], ['nguoi_lien_he', 'Người liên hệ, điện thoại'],
    ['mst', 'Mã số thuế / số ĐKKD']].forEach(([f, nhan]) => khoiDau.appendChild(oChu(nhan, d[f], q.sua,
    (v) => { doi[f] = v; })));
  const ngay = el('input', 'sx-textarea');
  ngay.type = 'date';
  ngay.value = d.ngay;
  ngay.max = d.hom_nay;
  ngay.disabled = !q.sua;
  ngay.addEventListener('change', () => { doi.ngay = ngay.value; });
  khoiDau.appendChild(nhanO('Ngày đánh giá', ngay));
  [['hinh_thuc', 'Hình thức'], ['phan_loai', 'Phân loại (QT.07 mục 4)'], ['nguon', 'Nguồn gốc hàng']].forEach(([f, nhan]) => {
    khoiDau.appendChild(nhanO(nhan, segment(d.lua_chon[f], d[f], (v) => { if (v) doi[f] = v; }, !q.sua)));
  });
  container.appendChild(khoiDau);

  // Phần A
  container.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">A. Hồ sơ pháp lý và an toàn thực '
    + 'phẩm</span>'));
  container.appendChild(el('div', 'sx-qc-goiy', 'Mục 1–6 bắt buộc khi áp dụng — thiếu một mục: không được duyệt. '
    + 'KAD: không áp dụng.'));
  d.ho_so.forEach((r) => container.appendChild(dongA(r, sua, a)));
  if (d.thieu_a.length) {
    container.appendChild(el('div', 'sx-attp-viec sx-attp-viec-cao', esc(`Thiếu phần A: ${d.thieu_a.join('; ')}`)));
  }

  // Phần B
  container.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">B. Đánh giá năng lực (chấm '
    + 'điểm)</span>'));
  if (d.goi_y_i) container.appendChild(el('div', 'sx-qc-goiy', esc(`Gợi ý điểm I: ${d.goi_y_i}`)));
  d.muc_b.forEach((b) => {
    const w = el('div', 'sx-qc-oso');
    w.appendChild(el('div', 'sx-qc-nhan', `<span class="sx-qc-so">${esc(b.so)}</span><div class="sx-qc-ten">`
      + `${esc(b.ten)}</div>`));
    if (b.tu_tinh) {
      w.appendChild(el('div', 'sx-qc-goiy', esc(`${d.diem_v} điểm — theo mục A7 (giấy chứng nhận còn hiệu lực: 2)`)));
    } else {
      const lua = b.muc.map((x) => ({ v: String(x.diem), ten: `${x.nhan} · ${x.diem}` }));
      w.appendChild(segment(lua, d[b.k] === '' ? '' : String(d[b.k]), (v) => { doi[b.k] = v; }, !sua, true));
    }
    container.appendChild(w);
  });
  const tong = el('div', `sx-qc-sc ${d.ket_luan === 'Chấp nhận' ? 'sx-qc-sc-dong' : 'sx-qc-sc-cho'}`);
  tong.appendChild(el('div', 'sx-qc-sc-ten', esc(`Tổng điểm: ${d.du_diem ? d.tong : '—'} / ${d.toi_da}`)));
  const kl = el('div', 'sx-qc-sc-meta');
  kl.appendChild(d.ket_luan ? chip(`Kết luận (app tính): ${d.ket_luan}`, KIEU_KL[d.ket_luan] || '')
    : el('span', null, 'Chưa chấm đủ điểm I–IV'));
  if (d.quyet_dinh) kl.appendChild(chip(`Giám đốc: ${d.quyet_dinh}`, ''));
  tong.appendChild(kl);
  tong.appendChild(el('div', 'sx-qc-goiy', 'Chấp nhận: đủ phần A, 30–42 điểm, điểm chất lượng ≥ 5 · Xem xét: 20–29 '
    + '(Giám đốc quyết định) · Loại bỏ: < 20, chất lượng < 5 hoặc thiếu phần A.'));
  container.appendChild(tong);

  // Ký
  container.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">Ký, duyệt</span>'));
  [['Người đánh giá (Mua hàng)', d.ky.danh_gia], ['QC (vật tư loại 1)', d.can_qc ? d.ky.qc : 'Không áp dụng (vật tư loại 2)'],
    ['Giám đốc phê duyệt', d.ky.duyet]].forEach(([nhan, ky]) => {
    const h = el('div', 'sx-dg-ky');
    h.appendChild(el('b', null, esc(nhan)));
    h.appendChild(el('span', null, esc(ky || '—')));
    container.appendChild(h);
  });
  if (d.ghi_chu) container.appendChild(el('div', 'sx-qc-goiy', esc(`Ghi chú: ${d.ghi_chu}`)));

  // Nút
  const hang = el('div', 'sx-qc-chips sx-tb-nut sx-dg-nut');
  const payload = () => {
    const p = { ...doi };
    const ds = Object.entries(a).map(([t, x]) => ({ tt: Number(t), ...x }));
    if (ds.length) p.ho_so = ds;
    return p;
  };
  const luu = async () => {
    const p = payload();
    if (!Object.keys(p).length) return null;
    return call(`${API}.luu`, { name: d.name, payload: JSON.stringify(p) });
  };
  if (sua) {
    hang.appendChild(nut('LƯU', 'sx-btn-primary', async (ev) => {
      ev.currentTarget.disabled = true;
      try { const r = await luu(); toast(r ? 'Đã lưu' : 'Không có gì thay đổi'); lai(); } catch (e) { toastErr(e.message); lai(); }
    }));
  }
  if (q.gui) {
    hang.appendChild(nut(d.can_qc ? 'GỬI QC KÝ' : 'GỬI GIÁM ĐỐC DUYỆT', 'sx-btn-primary', async (ev) => {
      ev.currentTarget.disabled = true;
      try { await luu(); await call(`${API}.gui`, { name: d.name }); toast('Đã gửi'); lai(); } catch (e) { toastErr(e.message); lai(); }
    }));
  }
  if (q.qc_ky) hang.appendChild(nut('QC KÝ', 'sx-btn-primary', () => moKy(ctx, d, 'qc', luu)));
  if (q.duyet) hang.appendChild(nut('DUYỆT', 'sx-btn-primary', () => moKy(ctx, d, 'duyet', luu)));
  if (q.tra_lai) hang.appendChild(nut('TRẢ LẠI', 'sx-btn-ghost', () => moKy(ctx, d, 'tra_lai', luu)));
  hang.appendChild(nut('IN', 'sx-btn-ghost', async () => {
    try { inHtml(await call(`${API}.in_phieu`, { name: d.name }), `${MA} ${d.name}`); } catch (e) { toastErr(e.message); }
  }));
  if (q.xoa) {
    hang.appendChild(nut('XOÁ', 'sx-btn-ghost', () => confirm2Step({
      title: `Xoá phiếu ${d.name}?`,
      message: 'Chỉ phiếu nháp / trả lại. Phiếu đã gửi, đã duyệt là hồ sơ — không xoá.',
      confirmLabel: 'XOÁ',
      onConfirm: async () => {
        await call(`${API}.xoa`, { name: d.name });
        toast('Đã xoá');
        window.location.hash = `#/so/${MA}`;
      },
    })));
  }
  container.appendChild(hang);
}

function nhanO(nhan, o) {
  const w = el('div', 'sx-qc-oso');
  w.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc(nhan)}</div>`));
  w.appendChild(o);
  return w;
}

function oChu(nhan, v, duoc, dat) {
  const i = el('input', 'sx-textarea');
  i.type = 'text';
  i.value = v || '';
  i.maxLength = 140;
  i.disabled = !duoc;
  i.addEventListener('input', () => dat(i.value));
  return nhanO(nhan, i);
}

/** Một mục phần A: Có / Không (/ KAD) — mục không áp dụng khóa ở KAD; số, ngày; hiệu lực. */
export function dongA(r, sua, a) {
  const w = el('div', `sx-qc-oso sx-dg-a${r.ket_qua === 'Không' ? ' sx-dg-a-k' : ''}`);
  w.appendChild(el('div', 'sx-qc-nhan', `<span class="sx-qc-so">${r.tt}</span><div><div class="sx-qc-ten">`
    + `${esc(r.ten)}</div><div class="sx-qc-goiy">Áp dụng: ${esc(r.ap_dung)}</div></div>`));
  const dat = (k, v) => { a[r.tt] = { ...(a[r.tt] || { ket_qua: r.ket_qua, so_ngay: r.so_ngay, hieu_luc: r.hieu_luc }), [k]: v }; };
  const lua = r.co_kad ? ['Có', 'Không', 'KAD'] : ['Có', 'Không'];
  w.appendChild(segment(lua, r.ket_qua, (v) => dat('ket_qua', v), !sua || r.ap === false, true));
  const so = el('input', 'sx-textarea');
  so.type = 'text';
  so.placeholder = 'Số, ngày';
  so.value = r.so_ngay || '';
  so.maxLength = 140;
  so.disabled = !sua;
  so.addEventListener('input', () => dat('so_ngay', so.value));
  w.appendChild(so);
  const hl = el('input', 'sx-textarea');
  hl.type = 'date';
  hl.value = r.hieu_luc || '';
  hl.disabled = !sua;
  hl.title = 'Hiệu lực (hết hạn)';
  hl.addEventListener('change', () => dat('hieu_luc', hl.value));
  w.appendChild(el('div', 'sx-qc-goiy', 'Hiệu lực đến (để trống nếu không thời hạn)'));
  w.appendChild(hl);
  return w;
}

/** QC ký / Giám đốc duyệt / trả lại: lưu thay đổi đang dở trước; phiếu Xem xét — Giám đốc chọn quyết định. */
export function moKy(ctx, d, viec, luu) {
  const ten = { qc: 'QC ký phiếu', duyet: 'Giám đốc duyệt', tra_lai: 'Trả lại Mua hàng' }[viec];
  const m = openModal({ kicker: `${MA} · ${d.name}`, title: ten });
  let qd = '';
  if (viec === 'duyet') {
    m.body.appendChild(el('div', 'sx-qc-goiy', esc(`Kết luận app tính: ${d.ket_luan || '—'} (${d.tong} / ${d.toi_da} `
      + 'điểm).')));
    if (d.ket_luan === 'Xem xét') {
      m.body.appendChild(el('div', 'sx-qc-goiy', 'Phiếu Xem xét (20–29 điểm): Giám đốc quyết định.'));
      m.body.appendChild(segment(['Chấp nhận', 'Không chấp nhận'], '', (v) => { qd = v; }, false));
    }
  }
  const y = el('textarea', 'sx-textarea');
  y.rows = 3;
  y.placeholder = viec === 'tra_lai' ? 'Bổ sung gì, sửa gì (bắt buộc)' : 'Ý kiến (không bắt buộc)';
  m.body.appendChild(y);
  const ok = nut(viec === 'tra_lai' ? 'TRẢ LẠI' : (viec === 'qc' ? 'KÝ' : 'DUYỆT'), 'sx-btn-primary sx-btn-big', async () => {
    if (viec === 'tra_lai' && !y.value.trim()) { toastErr('Ghi ý kiến trả lại.'); return; }
    if (viec === 'duyet' && d.ket_luan === 'Xem xét' && !qd) { toastErr('Chọn Chấp nhận hoặc Không chấp nhận.'); return; }
    ok.disabled = true;
    try {
      if (viec === 'qc') await luu();
      if (viec === 'qc') await ctx.call(`${API}.qc_ky`, { name: d.name, y_kien: y.value });
      else if (viec === 'duyet') await ctx.call(`${API}.duyet`, { name: d.name, quyet_dinh: qd, y_kien: y.value });
      else await ctx.call(`${API}.tra_lai`, { name: d.name, y_kien: y.value });
      toast(viec === 'tra_lai' ? 'Đã trả lại' : (viec === 'qc' ? 'QC đã ký' : 'Đã duyệt'));
      m.close();
      ctx.lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}
