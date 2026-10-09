// #/so — sổ ghi theo dòng (W43, D172). Mọi vai vào được; mỗi người chỉ thấy sổ mình có quyền (vai ghi / xác nhận /
// xem / xem xét tháng của định nghĩa sổ, cộng siêu quyền; Trưởng Ban ISO xem mọi sổ).
//
//   #/so          danh sách sổ: dòng tháng này (Danh mục: đang dùng), chờ xác nhận, hạn, tháng chưa xem xét
//   #/so/<mã>     một sổ: tháng (Ghi theo dòng) hoặc danh mục; tìm; + GHI DÒNG; bấm một dòng → chi tiết (sửa,
//                 xác nhận, ngừng, bản ký tay, lịch sử sửa); ĐÃ XEM THÁNG; IN SỔ.
// Phiếu ghi SINH TỪ CỘT của sổ (dùng lại ô nhập của qcui.js) — thêm sổ mới chỉ khai định nghĩa, không sửa JS.
// Luật ở sx/qc/so.py, API sx/api/qc_so.py.
// W44 (D173): thẻ BM.07.01 (đánh giá nhà cung cấp — DocType riêng, không phải sổ) mở màn views/danhgiancc.js:
//   #/so/BM.07.01, #/so/BM.07.01/<phiếu>.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, oCheck, oChon3, oChu, oGio, oSo, veNhac } from '/assets/sx/sx/components/qcui.js';

const API = 'sx.api.qc_so';
export const st = { thang: {}, q: {}, ngung: {} };
export const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const KIEU_TT = { 'Đã ghi': 'oprp', 'Đã xác nhận': 'dong', 'Ngừng': '' };
/** Việc chờ của bước xác nhận: "QC kiểm trước chạy (ký)" → "QC kiểm trước chạy"; sổ không đặt nhãn → "xác nhận". */
export const viecCho = (nhan) => String(nhan || '').replace(/\s*\(ký\)\s*$/, '') || 'xác nhận';

export function tachRoute() {
  const h = (window.location.hash || '#/so').split('?')[0];
  const phan = h.replace('#/so', '').split('/').filter(Boolean);
  return { ma: phan[0] ? decodeURIComponent(phan[0]) : null, phieu: phan[1] ? decodeURIComponent(phan[1]) : null };
}

const MA_DG = 'BM.07.01';     // đánh giá NCC — màn riêng, nạp khi mở (không import tĩnh màn khác)

/** "2026-10" ± n tháng. */
export function doiThang(t, n) {
  const [y, m] = t.split('-').map(Number);
  const k = y * 12 + (m - 1) + n;
  return `${Math.floor(k / 12)}-${String((k % 12) + 1).padStart(2, '0')}`;
}

function inHtml(html, tieuDe) {
  const w = window.open('', '_blank');
  if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
  w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>${esc(tieuDe)}</title>`
    + `</head><body>${html}</body></html>`);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 400);
}

function docTep(f) {
  return new Promise((ok, loi) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(',')[1]);
    r.onerror = () => loi(new Error(`Không đọc được tệp ${f.name}`));
    r.readAsDataURL(f);
  });
}

function nut(chu, kieu, onClick) {
  const b = el('button', `sx-btn ${kieu || 'sx-btn-ghost'}`, esc(chu));
  b.type = 'button';
  if (onClick) b.addEventListener('click', onClick);
  return b;
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '';
  const wrap = el('div', 'sx-qc sx-so');
  container.appendChild(wrap);
  const { ma, phieu } = tachRoute();
  const ctx = { ...api, container: wrap, lai: () => render(api) };
  try {
    if (ma === MA_DG) {
      const mod = await import(`/assets/sx/sx/views/danhgiancc.js?v=${encodeURIComponent(
        (api.ctx && api.ctx.assetVersion) || Date.now())}`);
      await mod.render({ ...ctx, phieu });
    } else if (ma) await veSo(ctx, ma);
    else veDanhSach(ctx, await call(`${API}.ds_so`, {}));
  } catch (e) {
    wrap.appendChild(khungTrong(e.message || 'Không mở được sổ.'));
  }
}

// ── Danh sách sổ ─────────────────────────────────────────────────────────────────────────────

export function veDanhSach(ctx, dl) {
  const { container } = ctx;
  container.appendChild(el('div', 'sx-qc-top', `<div style="flex:1;min-width:0">
    <div class="sx-qc-ngay">📒 Sổ</div>
    <div class="sx-qc-ai">Sổ ghi theo dòng trên app — thay sổ giấy</div></div>`));
  if (!dl.ds.length) {
    container.appendChild(khungTrong('Bạn chưa được giao sổ nào. Trưởng Ban ISO thêm vai của bạn vào định nghĩa sổ '
      + '(Desk → SX So).'));
    return;
  }
  dl.ds.forEach((s) => {
    const can = s.cho || s.han || s.chua_xem.length || s.kiem_lai || s.bao_duong;
    const a = el('a', `sx-qc-sc ${can ? 'sx-qc-sc-cho' : 'sx-qc-sc-dong'}`);
    a.href = `#/so/${encodeURIComponent(s.ma)}`;
    a.appendChild(el('div', 'sx-qc-sc-ten', `<span class="sx-tl-ma">${esc(s.ma)}</span> ${esc(s.ten)}`));
    const meta = el('div', 'sx-qc-sc-meta');
    meta.appendChild(el('span', null, esc(s.kieu === 'Danh mục' ? `${s.so_dong} đang dùng`
      : (s.kieu === 'Phiếu' ? `${s.so_dong} NCC Chấp nhận còn hạn` : `${s.so_dong} dòng tháng này`))));
    if (s.cho) meta.appendChild(chip(`${s.cho} chờ ${viecCho(s.nhan_xac_nhan)}`, 'oprp'));
    if (s.han) meta.appendChild(chip(s.kieu === 'Phiếu' ? `${s.han} NCC đến hạn đánh giá lại` : `${s.han} hạn đến / quá`,
      'han'));
    if (s.chua_xem.length) meta.appendChild(chip(`${s.chua_xem.length} tháng chưa xem xét`, 'oprp'));
    if (s.kiem_lai) meta.appendChild(chip(`${s.kiem_lai} thiết bị chờ kiểm lại`, 'cao'));
    if (s.bao_duong) meta.appendChild(chip(`${s.bao_duong} máy quá hạn bảo dưỡng`, 'oprp'));
    const q = s.quyen || {};
    const vai = (s.kieu === 'Phiếu' ? [q.lap ? 'lập, chấm' : '', q.qc ? 'QC ký' : '', q.duyet ? 'duyệt' : '']
      : [q.ghi ? 'ghi' : '', q.xac_nhan ? 'xác nhận' : '', q.xem_thang ? 'xem xét tháng' : ''])
      .filter(Boolean).join(', ');
    meta.appendChild(el('span', null, esc(vai ? `bạn: ${vai}` : 'bạn: chỉ xem')));
    a.appendChild(meta);
    container.appendChild(a);
  });
}

// ── Một sổ ───────────────────────────────────────────────────────────────────────────────────

export async function veSo(ctx, ma) {
  const { container, call } = ctx;
  const args = { so: ma };
  const thang = st.thang[ma];
  if (thang) args.tu = `${thang}-01`;
  if (st.q[ma]) args.q = st.q[ma];
  if (st.ngung[ma]) args.ngung = 1;
  const dl = await call(`${API}.xem`, args);
  const dn = dl.dn;
  const gtd = dn.kieu === 'Ghi theo dòng';
  if (gtd && !st.thang[ma]) st.thang[ma] = dl.tu.slice(0, 7);

  const top = el('div', 'sx-qc-top');
  top.innerHTML = `<div style="flex:1;min-width:0">
    <div class="sx-qc-ngay"><a href="#/so" class="sx-tl-ten">‹ Sổ</a> · ${esc(dn.ma)}</div>
    <div class="sx-qc-ai">${esc(dn.ten)}${dn.quy_trinh ? ` · ${esc(dn.quy_trinh)}` : ''}</div></div>`;
  container.appendChild(top);
  if (dn.ghi_chu) container.appendChild(el('div', 'sx-qc-goiy', esc(dn.ghi_chu)));

  // Nhắc riêng BM.06.05: thiết bị chờ kiểm lại sau sửa chữa (mức cao), máy quá hạn bảo dưỡng.
  const nh = [];
  (dl.kiem_lai || []).forEach((x) => nh.push({
    muc_do: 'cao', tieu_de: `${x.ma} chưa kiểm lại sau sửa chữa ngày ${ngayDu(x.ngay).slice(0, 5)}`,
    chi_tiet: `${x.ten} — kiểm lại theo ${x.bieu_mau || 'BM.06.0x'} trước khi dùng (QT.06).`, route: '#/qc/thietbi' }));
  if ((dl.bao_duong || []).length) {
    nh.push({ muc_do: 'thuong', tieu_de: `${dl.bao_duong.length} máy quá hạn bảo dưỡng định kỳ`,
      chi_tiet: dl.bao_duong.map((x) => `${x.ma} ${x.ten} (hạn ${ngayDu(x.han)})`).join('; '), route: `#/so/${dn.ma}` });
  }
  const hop = veNhac(nh);
  if (hop) container.appendChild(hop);

  // Tháng (Ghi theo dòng) / dòng đã ngừng (Danh mục) + ô tìm
  const loc = el('div', 'sx-qc-chips sx-so-loc');
  if (gtd) {
    const t = st.thang[ma];
    loc.appendChild(nut('◀', 'sx-btn-ghost', () => { st.thang[ma] = doiThang(t, -1); ctx.lai(); }));
    loc.appendChild(el('span', 'sx-so-thang', `Tháng ${t.slice(5, 7)}/${t.slice(0, 4)}`));
    const sau = nut('▶', 'sx-btn-ghost', () => { st.thang[ma] = doiThang(t, 1); ctx.lai(); });
    sau.disabled = t >= dl.hom_nay.slice(0, 7);
    loc.appendChild(sau);
  } else {
    loc.appendChild(nut(st.ngung[ma] ? 'Ẩn dòng đã ngừng' : 'Hiện cả dòng đã ngừng', 'sx-btn-ghost', () => {
      st.ngung[ma] = !st.ngung[ma];
      ctx.lai();
    }));
  }
  container.appendChild(loc);
  const tim = el('input', 'sx-textarea sx-tl-tim');
  tim.type = 'search';
  tim.placeholder = 'Tìm (không cần dấu)…';
  tim.value = st.q[ma] || '';
  tim.addEventListener('change', () => { st.q[ma] = tim.value.trim(); ctx.lai(); });
  container.appendChild(tim);

  if (dl.quyen.ghi) {
    container.appendChild(nut('+ GHI DÒNG', 'sx-btn-primary sx-btn-big', () => moPhieu(ctx, dl, null)));
  }

  const ds = gtd ? [...dl.ds].reverse() : dl.ds;
  if (!ds.length) {
    container.appendChild(khungTrong(gtd ? 'Tháng này chưa có dòng nào.' : 'Danh mục chưa có dòng nào.'));
  }
  ds.forEach((x) => container.appendChild(veDong(ctx, dl, x)));

  if (gtd && dn.xem_cuoi_thang) container.appendChild(veXemThang(ctx, dl));
  container.appendChild(nut(`🖨 IN SỔ ${gtd ? `THÁNG ${st.thang[ma].slice(5, 7)}/${st.thang[ma].slice(0, 4)}`
    : '(DANH MỤC HIỆN HÀNH)'}`, 'sx-btn-ghost', async () => {
    try {
      inHtml(await call(`${API}.in_so`, gtd ? { so: ma, tu: `${st.thang[ma]}-01` } : { so: ma }), `${dn.ma} ${dn.ten}`);
    } catch (e) { toastErr(e.message); }
  }));
}

export function veDong(ctx, dl, x) {
  const dn = dl.dn;
  const gtd = dn.kieu === 'Ghi theo dòng';
  const ngung = x.trang_thai === 'Ngừng';
  const cho = x.trang_thai === 'Đã ghi' && dl.quyen.co_xac_nhan;
  const the = el('div', `sx-qc-sc ${ngung ? 'sx-tl-het' : (cho ? 'sx-qc-sc-cho' : 'sx-qc-sc-dong')}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', `${gtd ? `${esc(ngayDu(x.ngay).slice(0, 5))} · ` : ''}${
    esc(x.tom_tat || '(trống)')}`));
  const meta = el('div', 'sx-qc-sc-meta');
  if (ngung || dl.quyen.co_xac_nhan) {
    meta.appendChild(chip(ngung ? 'Ngừng' : (cho ? `chờ ${viecCho(dn.nhan_xac_nhan)}` : x.trang_thai),
      ngung ? '' : KIEU_TT[x.trang_thai]));
  }
  (x.han || []).forEach((h) => {
    if (h.con < 0) meta.appendChild(chip(`${h.nhan}: quá ${-h.con} ngày`, 'cao'));
    else if (h.con <= h.bao_truoc) meta.appendChild(chip(`${h.nhan}: còn ${h.con} ngày`, 'han'));
  });
  meta.appendChild(el('span', null, esc(`ghi: ${x.ten_ghi}${x.ten_xac_nhan ? ` · xác nhận: ${x.ten_xac_nhan}` : ''}`)));
  const sua = (x.sua_doi || []).filter((s) => s.hanh_dong === 'Sửa').length;
  if (sua) meta.appendChild(el('span', null, `sửa ${sua} lần`));
  the.appendChild(meta);
  the.addEventListener('click', () => moDong(ctx, dl, x));
  return the;
}

// ── Chi tiết một dòng ────────────────────────────────────────────────────────────────────────

function oTep(x, key, nhan) {
  const a = el('a', 'sx-btn sx-btn-ghost', esc(`📎 ${nhan}`));
  a.href = `/api/method/${API}.tep?${new URLSearchParams({ name: x.name, key })}`;
  a.target = '_blank';
  a.rel = 'noopener';
  return a;
}

export function moDong(ctx, dl, x) {
  const dn = dl.dn;
  const m = openModal({ kicker: `${dn.ma} · ${x.trang_thai}`, title: x.tom_tat || x.name });
  const bang = el('div', 'sx-so-ct');
  const o = (nhan, gt) => {
    const h = el('div', 'sx-so-o');
    h.appendChild(el('b', null, esc(nhan)));
    h.appendChild(el('span', null, gt ? esc(gt) : '—'));
    bang.appendChild(h);
  };
  if (dn.kieu === 'Ghi theo dòng') o('Ngày', ngayDu(x.ngay));
  dn.cot.forEach((c) => {
    o(c.nhan, x.hien[c.key]);
    if (c.kieu === 'Attach' && x.du_lieu[c.key]) bang.appendChild(oTep(x, c.key, c.nhan));
  });
  m.body.appendChild(bang);
  const ky = [`Ghi: ${x.ky_ghi || x.ten_ghi}`];
  if (x.ky_xac_nhan) ky.push(`${dn.nhan_xac_nhan || 'Xác nhận'}: ${x.ky_xac_nhan}${x.y_kien_xac_nhan ? ` — ${x.y_kien_xac_nhan}` : ''}`);
  if (x.trang_thai === 'Ngừng') ky.push(`Ngừng: ${x.ly_do_ngung || ''}`);
  if (x.su_co) ky.push(`Phiếu sự cố: ${x.su_co}`);
  m.body.appendChild(el('div', 'sx-qc-goiy', ky.map(esc).join('<br>')));
  if (x.tep) m.body.appendChild(oTep(x, 'tep', 'Tệp đính kèm'));
  if (x.ban_ky_tay) m.body.appendChild(oTep(x, 'ban_ky_tay', 'Bản ký tay (scan)'));

  const hang = el('div', 'sx-qc-chips sx-so-nut');
  if (x.duoc_xac_nhan) {
    hang.appendChild(nut(`✓ ${(dn.nhan_xac_nhan || 'XÁC NHẬN').toUpperCase()}`, 'sx-btn-primary',
      () => { m.close(); moXacNhan(ctx, dl, x); }));
  }
  if (x.duoc_sua) hang.appendChild(nut('SỬA', 'sx-btn-ghost', () => { m.close(); moPhieu(ctx, dl, x); }));
  if (x.duoc_ngung) hang.appendChild(nut('NGỪNG DÒNG', 'sx-btn-ghost', () => { m.close(); moNgung(ctx, dl, x); }));
  if ((dl.quyen.ghi || dl.la_iso) && x.trang_thai !== 'Ngừng') {
    hang.appendChild(nutTaiLen(ctx, dl, x, 'ban_ky_tay', x.ban_ky_tay ? 'THAY BẢN KÝ TAY' : 'TẢI BẢN KÝ TAY (scan)', m));
    hang.appendChild(nutTaiLen(ctx, dl, x, 'tep', x.tep ? 'THAY TỆP KÈM' : 'ĐÍNH KÈM TỆP', m));
  }
  m.body.appendChild(hang);
  if ((x.sua_doi || []).length) {
    m.body.appendChild(el('div', 'sx-dv-khu', 'Lịch sử sửa, ngừng'));
    x.sua_doi.forEach((s) => m.body.appendChild(el('div', 'sx-qc-goiy sx-so-sua',
      esc(`${ngayDu(s.luc)} ${s.luc.slice(11, 16)} · ${s.ten} · ${s.hanh_dong}: ${tomTatDoi(dn, s)}`))));
  }
}

/** Một lần sửa đọc được: các ô đổi "nhãn: cũ → mới". */
export function tomTatDoi(dn, s) {
  if (s.hanh_dong === 'Ngừng') return s.sau.ly_do || '';
  if (s.hanh_dong === 'Đính kèm') return Object.keys(s.sau).join(', ');
  const a = s.truoc.du_lieu || {};
  const b = s.sau.du_lieu || {};
  const doi = dn.cot.filter((c) => JSON.stringify(a[c.key] ?? null) !== JSON.stringify(b[c.key] ?? null))
    .map((c) => `${c.nhan}: ${hienGT(a[c.key])} → ${hienGT(b[c.key])}`);
  if (s.truoc.ngay !== s.sau.ngay) doi.unshift(`Ngày: ${ngayDu(s.truoc.ngay)} → ${ngayDu(s.sau.ngay)}`);
  if (s.truoc.xac_nhan) doi.push('bỏ xác nhận cũ, chờ xác nhận lại');
  return doi.join('; ') || '(không đổi dữ liệu)';
}

function hienGT(v) {
  if (v === null || v === undefined || v === '') return '—';
  if (Array.isArray(v)) return v.join(', ');
  if (v === 1 || v === true) return '✓';
  return String(v);
}

function nutTaiLen(ctx, dl, x, dich, chu, m) {
  const w = el('span');
  const b = nut(chu);
  const inp = el('input');
  inp.type = 'file';
  inp.accept = '.pdf,.png,.jpg,.jpeg,application/pdf,image/*';
  inp.style.display = 'none';
  inp.addEventListener('change', async () => {
    const f = inp.files && inp.files[0];
    if (!f) return;
    if (f.size > 10 * 1024 * 1024) { toastErr('Tệp quá 10 MB.'); return; }
    b.disabled = true;
    try {
      await ctx.call(`${API}.tai_len`, { so: dl.dn.ma, ten: f.name, noi_dung: await docTep(f), name: x.name, dich });
      toast('Đã gắn tệp');
      m.close();
      ctx.lai();
    } catch (e) { toastErr(e.message); }
    b.disabled = false;
  });
  b.addEventListener('click', () => inp.click());
  w.appendChild(b);
  w.appendChild(inp);
  return w;
}

function moXacNhan(ctx, dl, x) {
  const dn = dl.dn;
  const m = openModal({ kicker: `${dn.ma} · ${dn.nhan_xac_nhan || 'Xác nhận'}`, title: x.tom_tat || x.name });
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Xác nhận là ký trên phần mềm (người + giờ). Dòng sổ Ghi theo dòng '
    + 'khóa sau khi xác nhận.'));
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Ý kiến (nếu có)'));
  const yk = el('textarea', 'sx-textarea');
  yk.rows = 2;
  m.body.appendChild(yk);
  const ok = nut('✓ XÁC NHẬN', 'sx-btn-primary sx-btn-big', async () => {
    ok.disabled = true;
    try {
      const r = await ctx.call(`${API}.xac_nhan`, { name: x.name, y_kien: yk.value.trim() });
      toast('Đã xác nhận');
      if (r && r.kiem_lai) toast(r.kiem_lai, 'warn');
      m.close();
      ctx.lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

function moNgung(ctx, dl, x) {
  const dn = dl.dn;
  const m = openModal({ kicker: `${dn.ma} · ngừng dòng`, title: x.tom_tat || x.name });
  m.body.appendChild(el('div', 'sx-qc-goiy', dn.kieu === 'Danh mục'
    ? 'Đối tượng không dùng nữa: dòng vẫn còn trên sổ (lịch sử), không in vào danh mục hiện hành.'
    : 'Ghi nhầm: dòng vẫn còn trên sổ, bản in gạch đi kèm lý do. Ghi lại dòng đúng sau.'));
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Lý do (bắt buộc)'));
  const ly = el('textarea', 'sx-textarea');
  ly.rows = 2;
  m.body.appendChild(ly);
  m.body.appendChild(nut('NGỪNG DÒNG', 'sx-btn-warn sx-btn-big', () => {
    if (!ly.value.trim()) { toastErr('Ghi lý do ngừng.'); return; }
    confirm2Step({
      title: 'Ngừng dòng sổ',
      message: `${x.tom_tat || x.name}\nLý do: ${ly.value.trim()}`,
      confirmLabel: 'NGỪNG',
      onConfirm: async () => {
        try {
          await ctx.call(`${API}.ngung`, { name: x.name, ly_do: ly.value.trim() });
          toast('Đã ngừng dòng');
          m.close();
          ctx.lai();
        } catch (e) { toastErr(e.message); throw e; }
      },
    });
  }));
}

// ── Xem xét cuối tháng ───────────────────────────────────────────────────────────────────────

function veXemThang(ctx, dl) {
  const dn = dl.dn;
  const t = st.thang[dn.ma];
  const khoi = el('div', 'sx-qc-sc sx-so-xem');
  khoi.appendChild(el('div', 'sx-qc-sc-ten', esc(`${dn.nhan_xem_thang} — tháng ${t.slice(5, 7)}/${t.slice(0, 4)}`)));
  const x = dl.xem_thang;
  khoi.appendChild(el('div', 'sx-qc-goiy', x
    ? esc(`${x.ky}${x.nhan_xet ? ` — ${x.nhan_xet}` : ''}${x.can_xem_lai ? ' · có dòng ghi sau lần xem, chờ xem lại' : ''}`)
    : 'Chưa xem xét tháng này.'));
  if (dl.quyen.xem_thang && dl.ds.length && (!x || x.can_xem_lai)) {
    khoi.appendChild(nut(`ĐÃ XEM THÁNG ${t.slice(5, 7)}/${t.slice(0, 4)}`, 'sx-btn-primary', () => {
      const m = openModal({ kicker: `${dn.ma} · xem xét cuối tháng`, title: `Tháng ${t.slice(5, 7)}/${t.slice(0, 4)}` });
      m.body.appendChild(el('div', 'sx-qc-goiy', `${dl.ds.length} dòng. Nhận xét (nếu có)`));
      const nx = el('textarea', 'sx-textarea');
      nx.rows = 3;
      m.body.appendChild(nx);
      const ok = nut('XÁC NHẬN ĐÃ XEM', 'sx-btn-primary sx-btn-big', async () => {
        ok.disabled = true;
        try {
          await ctx.call(`${API}.xem_thang`, { so: dn.ma, thang: t, nhan_xet: nx.value.trim() });
          toast('Đã ghi xem xét tháng');
          m.close();
          ctx.lai();
        } catch (e) { ok.disabled = false; toastErr(e.message); }
      });
      m.body.appendChild(ok);
    }));
  }
  return khoi;
}

// ── Phiếu ghi / sửa — sinh từ cột của sổ ─────────────────────────────────────────────────────

/** Ô nhập của một cột. `dat(v)` lưu giá trị; trả node. */
export function oCot(ctx, dl, c, v, dat) {
  const m = { f: c.key, so: '', nhan: `${c.nhan}${c.bat_buoc ? ' *' : ''}`, ngan: `${c.nhan}${c.bat_buoc ? ' *' : ''}` };
  const onSet = (_f, g) => dat(g);
  if (c.kieu === 'Check') return oCheck(m, v, onSet, false);
  if (c.kieu === 'Select') return oChon3(m, v, onSet, c.lua_chon, false);
  if (c.kieu === 'Time') return oGio(m, v, onSet, false);
  if (c.kieu === 'Int' || c.kieu === 'Float') {
    return oSo({ ...m, kieu: c.kieu === 'Float' ? 'so' : 'nguyen' }, v, onSet, {}, false);
  }
  if (c.kieu === 'MultiSelect') return oNhieu(m, v, dat, c.lua_chon);
  if (c.kieu === 'Link' || c.kieu === 'User') return oLienKet(ctx, dl, c, m, v, dat);
  if (c.kieu === 'Attach') return oDinhKem(ctx, dl, m, v, dat);
  if (c.kieu === 'Text') {
    const w = el('div', 'sx-qc-oso');
    w.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc(m.nhan)}</div>`));
    const t = el('textarea', 'sx-textarea');
    t.rows = 2;
    t.value = v || '';
    t.addEventListener('input', () => dat(t.value));
    w.appendChild(t);
    return w;
  }
  if (c.kieu === 'Date' || c.kieu === 'Datetime') {
    const w = el('div', 'sx-qc-oso');
    w.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc(m.nhan)}</div>`));
    const i = el('input', 'sx-textarea');
    i.type = c.kieu === 'Date' ? 'date' : 'datetime-local';
    i.value = v ? (c.kieu === 'Date' ? String(v).slice(0, 10) : String(v).slice(0, 16).replace(' ', 'T')) : '';
    i.addEventListener('change', () => dat(i.value));
    w.appendChild(i);
    return w;
  }
  return oChu(m, v, onSet, false);
}

/** Nhiều lựa chọn (vd tháng kế hoạch kiểm định): bấm chip bật / tắt, giữ thứ tự lựa chọn. */
function oNhieu(m, v, dat, lua) {
  const chon = new Set(Array.isArray(v) ? v : []);
  const w = el('div', 'sx-qc-oso');
  w.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc(m.nhan)}</div>`));
  const box = el('div', 'sx-qc-vi');
  lua.forEach((o) => {
    const b = el('button', `sx-qc-vi-o${chon.has(o) ? ' sx-qc-vi-on' : ''}`, esc(o));
    b.type = 'button';
    b.addEventListener('click', () => {
      if (chon.has(o)) chon.delete(o); else chon.add(o);
      b.classList.toggle('sx-qc-vi-on', chon.has(o));
      dat(lua.filter((x) => chon.has(x)));
    });
    box.appendChild(b);
  });
  w.appendChild(box);
  return w;
}

/** Chữ một lựa chọn: thiết bị "mã · tên (loại)"; nhân viên (an_ma) "họ tên · mã" — mã chỉ để phân biệt trùng tên. */
export function tenChon(x) {
  if (x.an_ma && x.nhan) return `${esc(x.nhan)} · ${esc(x.v)}`;
  return `${esc(x.v)}${x.nhan ? ` · ${esc(x.nhan)}` : ''}${x.loai ? ` (${esc(x.loai)})` : ''}`;
}

/** Ô chọn từ danh sách (Link / User): tải lựa chọn từ server lúc mở phiếu. */
function oLienKet(ctx, dl, c, m, v, dat) {
  const w = el('div', 'sx-qc-oso');
  w.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc(m.nhan)}</div>`));
  const s = el('select', 'sx-textarea');
  s.innerHTML = `<option value="">${v ? esc(v) : '— chọn —'}</option>`;
  s.value = '';
  s.addEventListener('change', () => dat(s.value || null));
  w.appendChild(s);
  ctx.call(`${API}.goi_y`, { so: dl.dn.ma, key: c.key }).then((ds) => {
    s.innerHTML = `<option value="">— chọn —</option>${ds.map((x) => `<option value="${esc(x.v)}">${
      tenChon(x)}</option>`).join('')}`;
    s.value = v || '';
  }).catch((e) => toastErr(e.message));
  return w;
}

/** Ô đính kèm: tải tệp lên trước (tệp riêng tư), lưu đường tệp vào dòng. */
function oDinhKem(ctx, dl, m, v, dat) {
  const w = el('div', 'sx-qc-oso');
  w.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc(m.nhan)}</div>`));
  const tt = el('div', 'sx-qc-goiy', v ? 'Đã có tệp.' : 'Chưa có tệp.');
  const inp = el('input');
  inp.type = 'file';
  inp.accept = '.pdf,.png,.jpg,.jpeg,application/pdf,image/*';
  inp.addEventListener('change', async () => {
    const f = inp.files && inp.files[0];
    if (!f) return;
    if (f.size > 10 * 1024 * 1024) { toastErr('Tệp quá 10 MB.'); return; }
    try {
      const r = await ctx.call(`${API}.tai_len`, { so: dl.dn.ma, ten: f.name, noi_dung: await docTep(f) });
      dat(r.url);
      tt.textContent = `Đã tải: ${f.name}`;
    } catch (e) { toastErr(e.message); }
  });
  w.appendChild(inp);
  w.appendChild(tt);
  return w;
}

/** Ô bắt buộc còn trống (kiểm trước khi gửi — server vẫn kiểm lại). */
export function thieu(cot, du) {
  return cot.filter((c) => c.bat_buoc && (c.kieu === 'Check' ? !Number(du[c.key])
    : (du[c.key] === undefined || du[c.key] === null || du[c.key] === ''
      || (Array.isArray(du[c.key]) && !du[c.key].length)))).map((c) => c.nhan);
}

export function moPhieu(ctx, dl, x) {
  const dn = dl.dn;
  const gtd = dn.kieu === 'Ghi theo dòng';
  const m = openModal({ kicker: `${dn.ma} · ${x ? 'sửa dòng' : 'ghi dòng mới'}`, title: dn.ten });
  m.body.classList.add('sx-so-phieu');
  const du = { ...(x ? x.du_lieu : {}) };
  let ngay = x ? x.ngay : dl.hom_nay;
  const wn = el('div', 'sx-qc-oso');
  wn.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${gtd ? 'Ngày *' : 'Ngày ghi / cập nhật'}</div>`));
  const n = el('input', 'sx-textarea');
  n.type = 'date';
  n.value = ngay;
  if (gtd) n.max = dl.hom_nay;
  n.addEventListener('change', () => { ngay = n.value; });
  wn.appendChild(n);
  m.body.appendChild(wn);
  // Ô app tự tính (vd RR, cấp độ BM.05.02) không cho nhập — server tính lại mỗi lần lưu.
  const tinh = new Set(dn.cot_tinh || []);
  const nhap = dn.cot.filter((c) => !tinh.has(c.key));
  nhap.forEach((c) => m.body.appendChild(oCot(ctx, dl, c, du[c.key], (v) => {
    if (v === null || v === undefined || v === '' || (Array.isArray(v) && !v.length)) delete du[c.key];
    else du[c.key] = v;
  })));
  if (tinh.size) {
    m.body.appendChild(el('div', 'sx-qc-goiy', esc(`App tự tính: ${dn.cot.filter((c) => tinh.has(c.key))
      .map((c) => c.nhan).join(', ')}.`)));
  }
  if (x && dn.kieu === 'Danh mục' && x.trang_thai === 'Đã xác nhận') {
    m.body.appendChild(el('div', 'sx-qc-goiy', 'Dòng đã xác nhận — sửa xong phải xác nhận lại.'));
  }
  const ok = nut(x ? 'LƯU SỬA' : 'GHI DÒNG', 'sx-btn-primary sx-btn-big', async () => {
    const t = thieu(nhap, du);
    if (t.length) { toastErr(`Chưa ghi: ${t.join(', ')}`); return; }
    ok.disabled = true;
    try {
      const payload = JSON.stringify({ ngay, du_lieu: du });
      const r = x ? await ctx.call(`${API}.sua`, { name: x.name, payload })
        : await ctx.call(`${API}.ghi`, { so: dn.ma, payload });
      toast(x ? (r.doi ? 'Đã lưu sửa' : 'Không có gì thay đổi') : 'Đã ghi dòng');
      if (r && r.kiem_lai) toast(r.kiem_lai, 'warn');
      m.close();
      ctx.lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}
