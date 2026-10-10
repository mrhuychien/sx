// #/tailieu — thư viện tài liệu (W42, D171). Mọi vai có tài khoản app vào được (C27).
//
//   Của tôi   "Chờ tôi ký" (biên bản W45) rồi "Cần đọc" trên cùng — mở PDF xong mới bật ĐÃ ĐỌC, HIỂU (thay chữ ký nhận tài liệu, C28); dưới là
//             tài liệu phân phối cho vai mình, theo nhóm, ô tìm mã / tên; biểu mẫu có màn app → nút sang màn ghi.
//   Tất cả    (Trưởng Ban ISO) mọi trạng thái, cả bản cũ; sửa phân phối / biểu mẫu kèm; tài liệu bên ngoài, soát
//             xét; in BM.01.02, BM.01.03.
//   Đề nghị   BM.01.01: lập → ký gửi → Ban ISO xem xét → Giám đốc duyệt; trả lại; hủy; in.
//   Ban hành  (Trưởng Ban ISO) đợt = QĐ + Phụ lục 1: kéo đề nghị đã duyệt, tải PDF đã ký, QĐ scan, BAN HÀNH; tiến
//             độ đọc; in BM.01.13. Nạp bộ tài liệu 21/9/2026 (một lần) ở #/tailieu/nap — D180: danh mục đi kèm
//             app (một nút), tệp PDF chọn thẳng tai_lieu_pdf.zip.
//   Biên bản (W45, D174) #/tailieu/bienban[/<tên>] — màn views/qc_bienban.js nạp khi mở (không import tĩnh màn khác).
// Luật ở sx/qc/tai_lieu.py, API sx/api/qc_tailieu.py. Tệp riêng tư mở qua tai_tep (GET, kiểm quyền).

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment } from '/assets/sx/sx/components/qcui.js';
import { docZip, tenGoc } from '/assets/sx/sx/lib/zip.js';

const API = 'sx.api.qc_tailieu';
export const st = { q: '', tt: 'Hiện hành', nguon: 'Nội bộ', scan: '', quyen: null, daMo: {} };
export const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const KIEU_DN = { 'Nháp': '', 'Chờ xem xét': 'oprp', 'Chờ duyệt': 'oprp', 'Đã duyệt': 'dong', 'Trả lại': 'cao', 'Hủy': '' };
const KIEU_TT = { 'Hiện hành': 'dong', 'Dự thảo': 'oprp', 'Hết hiệu lực': 'cao' };

export function tachRoute() {
  const h = (window.location.hash || '#/tailieu').split('?')[0];
  const phan = h.replace('#/tailieu', '').split('/').filter(Boolean);
  return { man: phan[0] || 'cuatoi', tham_so: phan[1] ? decodeURIComponent(phan[1]) : null };
}

function nut(chu, kieu, onClick) {
  const b = el('button', `sx-btn ${kieu || 'sx-btn-ghost'}`, esc(chu));
  b.type = 'button';
  if (onClick) b.addEventListener('click', onClick);
  return b;
}

export function veTab(dang, q) {
  const tabs = [['cuatoi', 'Của tôi', '#/tailieu']];
  if (q && q.la_iso) tabs.push(['tatca', 'Tất cả', '#/tailieu/tatca']);
  if (q && (q.duoc_de_nghi || q.la_iso)) tabs.push(['denghi', 'Đề nghị', '#/tailieu/denghi']);
  if (q && q.la_iso) tabs.push(['banhanh', 'Ban hành', '#/tailieu/banhanh']);
  if (q && q.bien_ban) tabs.push(['bienban', 'Biên bản', '#/tailieu/bienban']);
  const box = el('div', 'sx-qc-seg sx-tl-tab');
  tabs.forEach(([ma, ten, href]) => {
    const on = ma === dang || (ma === 'banhanh' && (dang === 'dot' || dang === 'nap'));
    const a = el('a', `sx-qc-tab${on ? ' sx-qc-seg-on' : ''}`, esc(ten));
    a.href = href;
    box.appendChild(a);
  });
  return box;
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '';
  const wrap = el('div', 'sx-qc sx-tl');
  container.appendChild(wrap);
  const { man, tham_so } = tachRoute();
  const than = el('div', 'sx-qc-than');
  let daGan = false;
  try {
    let dl = null;
    if (man === 'cuatoi' || man === 'tatca' || !st.quyen) {
      dl = await call(`${API}.ds`, { tat_ca: man === 'tatca' ? 1 : 0 });
      st.quyen = { la_iso: dl.la_iso, duoc_de_nghi: dl.duoc_de_nghi, duoc_nap: dl.duoc_nap, nap_xong: dl.nap_xong,
        bien_ban: dl.bien_ban };
    }
    wrap.appendChild(veTab(man, st.quyen));
    wrap.appendChild(than);
    daGan = true;
    const ctx = { ...api, container: than, lai: () => render(api) };
    if (man === 'tatca' && st.quyen.la_iso) veDanhSach(ctx, dl, true);
    else if (man === 'denghi') await veDeNghi(ctx);
    else if (man === 'banhanh' && st.quyen.la_iso) await veBanHanh(ctx);
    else if (man === 'dot' && st.quyen.la_iso && tham_so) await veDot(ctx, tham_so);
    else if (man === 'nap' && st.quyen.duoc_nap) await veNap(ctx);
    else if (man === 'bienban') {
      const mod = await import(`/assets/sx/sx/views/qc_bienban.js?v=${encodeURIComponent(
        (api.ctx && api.ctx.assetVersion) || Date.now())}`);
      await mod.ve(ctx, tham_so);
    }
    else veDanhSach(ctx, dl || await call(`${API}.ds`, {}), false);
  } catch (e) {
    if (!daGan) wrap.appendChild(than);
    than.innerHTML = '';
    than.appendChild(khungTrong(e.message || 'Không mở được thư viện tài liệu.'));
  }
}

// ── mở tệp, in ───────────────────────────────────────────────────────────────────────────────

/** Nút mở PDF: thẻ <a> trỏ thẳng tai_tep (bấm là trình duyệt mở — không bị chặn pop-up), đồng thời gọi `mo`
 *  (POST) ghi giờ mở lần đầu. `xong()` chạy khi server đã ghi — lúc đó mới bật ĐÃ ĐỌC, HIỂU. */
export function nutMo(api, name, chu = '📄 MỞ', opts = {}) {
  const a = el('a', `sx-btn ${opts.kieu || 'sx-btn-primary'} sx-tl-mo`, esc(chu));
  const q = new URLSearchParams({ name });
  if (opts.kem != null) q.set('kem', opts.kem);
  if (opts.lan) q.set('lan', opts.lan);
  a.href = `/api/method/${API}.tai_tep?${q}`;
  a.target = '_blank';
  a.rel = 'noopener';
  a.addEventListener('click', () => {
    const args = { name };
    if (opts.kem != null) args.kem = opts.kem;
    if (opts.lan) args.lan = opts.lan;
    api.call(`${API}.mo`, args).then(() => { st.daMo[name] = true; if (opts.xong) opts.xong(); })
      .catch((e) => toastErr(e.message));
  });
  return a;
}

/** Mở bản scan bản gốc đã ký (D176): GET tai_tep?scan=1 — kiểm quyền như PDF; không tính là "đã mở đọc". */
export function nutScan(name, chu = '📎 BẢN SCAN', lan = '') {
  const a = el('a', 'sx-btn sx-btn-ghost sx-tl-mo', esc(chu));
  const q = new URLSearchParams({ name, scan: 1 });
  if (lan) q.set('lan', lan);
  a.href = `/api/method/${API}.tai_tep?${q}`;
  a.target = '_blank';
  a.rel = 'noopener';
  return a;
}

export function inHtml(html, tieuDe) {
  const w = window.open('', '_blank');
  if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
  w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>${esc(tieuDe)}</title>`
    + `</head><body>${html}</body></html>`);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 400);
}

async function inTheo(api, method, args, tieuDe) {
  try { inHtml(await api.call(`${API}.${method}`, args || {}), tieuDe); } catch (e) { toastErr(e.message); }
}

export function docTep(f) {
  return new Promise((ok, loi) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(',')[1]);
    r.onerror = () => loi(new Error(`Không đọc được tệp ${f.name}`));
    r.readAsDataURL(f);
  });
}

function nutTaiTep(chu, accept, onFile) {
  const w = el('span');
  const b = nut(chu);
  const inp = el('input');
  inp.type = 'file';
  inp.accept = accept;
  inp.style.display = 'none';
  inp.addEventListener('change', async () => {
    const f = inp.files && inp.files[0];
    if (!f) return;
    if (f.size > 10 * 1024 * 1024) { toastErr('Tệp quá 10 MB.'); return; }
    b.disabled = true;
    try { await onFile(f, await docTep(f)); } catch (e) { toastErr(e.message); }
    b.disabled = false;
    inp.value = '';
  });
  b.addEventListener('click', () => inp.click());
  w.appendChild(b);
  w.appendChild(inp);
  return w;
}

function oNhap(body, nhan, gt, kieu, khoa) {
  body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
  const n = el(kieu === 'ta' ? 'textarea' : 'input');
  n.className = 'sx-textarea';
  if (kieu === 'ta') n.rows = 3;
  else if (kieu) n.type = kieu;
  n.value = gt == null ? '' : gt;
  n.disabled = !!khoa;
  body.appendChild(n);
  return n;
}

function oChon(body, nhan, lua, gt, khoa) {
  body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
  const s = el('select', 'sx-textarea');
  lua.forEach(([v, ten]) => {
    const o = el('option', null, esc(ten));
    o.value = v;
    if (v === (gt || '')) o.selected = true;
    s.appendChild(o);
  });
  s.disabled = !!khoa;
  body.appendChild(s);
  return s;
}

/** Chọn nhiều nơi nhận bằng chip bật / tắt. */
function chonNoiNhan(body, ds, dang, khoa) {
  const chon = new Set(dang || []);
  const box = el('div', 'sx-qc-chips sx-tl-nn');
  ds.forEach((ten) => {
    const b = el('button', `sx-qc-tag sx-tl-nn-o${chon.has(ten) ? ' sx-tl-nn-on' : ''}`, esc(ten));
    b.type = 'button';
    b.disabled = !!khoa;
    b.addEventListener('click', () => {
      if (chon.has(ten)) chon.delete(ten); else chon.add(ten);
      b.classList.toggle('sx-tl-nn-on', chon.has(ten));
    });
    box.appendChild(b);
  });
  body.appendChild(box);
  return () => ds.filter((t) => chon.has(t));
}

// ── Của tôi / Tất cả ─────────────────────────────────────────────────────────────────────────

function veCanDoc(ctx, ds) {
  const box = el('div', 'sx-tl-cando');
  box.appendChild(el('div', 'sx-qc-buoc', `<span class="sx-qc-buoc-ten">Cần đọc</span>
    <span class="sx-qc-buoc-dem">${ds.length} tài liệu mới / sửa đổi</span>`));
  ds.forEach((x) => {
    const the = el('div', 'sx-qc-sc sx-qc-sc-cho sx-tl-the');
    the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(x.ma ? `${x.ma} — ` : '')}${esc(x.ten)}`));
    const meta = el('div', 'sx-qc-sc-meta');
    if (x.lan_ban_hanh) meta.appendChild(chip(`Lần BH ${x.lan_ban_hanh}`));
    if (x.dot_ban_hanh) meta.appendChild(el('span', null, `ban hành ${esc(ngayDu(x.ngay))} · ${esc(x.dot_ban_hanh)}`));
    the.appendChild(meta);
    const hang = el('div', 'sx-qc-chips sx-tb-nut');
    const doc = nut('ĐÃ ĐỌC, HIỂU', 'sx-btn-primary');
    const moRoi = () => !!(x.mo_luc || st.daMo[x.tai_lieu] || !x.co_tep);
    doc.disabled = !moRoi();
    if (x.co_tep) hang.appendChild(nutMo(ctx, x.tai_lieu, '📄 MỞ ĐỌC', { kieu: 'sx-btn-ghost', xong: () => { doc.disabled = false; } }));
    doc.addEventListener('click', async () => {
      doc.disabled = true;
      try {
        await ctx.call(`${API}.da_doc`, { name: x.tai_lieu });
        toast('Đã xác nhận đọc');
        ctx.lai();
      } catch (e) { doc.disabled = false; toastErr(e.message); }
    });
    hang.appendChild(doc);
    the.appendChild(hang);
    if (!moRoi()) the.appendChild(el('div', 'sx-qc-goiy', 'Mở tài liệu ra đọc trước — xong mới bấm được Đã đọc, hiểu.'));
    box.appendChild(the);
  });
  return box;
}

export function locDs(ds, q) {
  const k = (q || '').trim().toLowerCase();
  if (!k) return ds;
  return ds.filter((x) => `${x.ma || ''} ${x.ten || ''} ${(x.ma_bieu_mau || []).map((b) => b.ma).join(' ')}`
    .toLowerCase().includes(k));
}

function nhomTheo(ds) {
  const ra = [];
  ds.forEach((x) => {
    const n = x.nhom_thu_muc || 'Khác';
    let g = ra.find((y) => y[0] === n);
    if (!g) { g = [n, []]; ra.push(g); }
    g[1].push(x);
  });
  return ra;
}

function veDong(ctx, x, dl, tatCa) {
  const the = el('div', `sx-qc-sc sx-tl-the${x.trang_thai === 'Hết hiệu lực' ? ' sx-tl-het' : ''}`);
  const ten = el('a', 'sx-qc-sc-ten sx-tl-ten', `${x.ma ? `<span class="sx-tl-ma">${esc(x.ma)}</span> ` : ''}${esc(x.ten)}`);
  ten.href = 'javascript:void(0)';
  ten.addEventListener('click', () => moChiTiet(ctx, x.name, dl));
  the.appendChild(ten);
  const meta = el('div', 'sx-qc-sc-meta');
  if (tatCa && x.trang_thai !== 'Hiện hành') meta.appendChild(chip(x.trang_thai, KIEU_TT[x.trang_thai]));
  if (x.lan_ban_hanh) meta.appendChild(chip(`Lần BH ${x.lan_ban_hanh}`));
  if (x.ngay_hieu_luc) meta.appendChild(el('span', null, `hiệu lực ${esc(ngayDu(x.ngay_hieu_luc))}`));
  if (x.nguon === 'Bên ngoài') meta.appendChild(el('span', null, esc(x.so_hieu_co_quan || '')));
  if (x.loai === 'Biểu mẫu trên phần mềm') meta.appendChild(chip('trên phần mềm'));
  if (tatCa) meta.appendChild(el('span', null, `${(x.phan_phoi || []).length} nơi nhận`));
  if (x.co_scan) meta.appendChild(chip('có bản scan', 'dong'));
  else if (tatCa && canScan(x)) meta.appendChild(chip('chưa có bản scan', 'oprp'));
  the.appendChild(meta);
  const nutDs = [];
  if (x.co_tep) nutDs.push(nutMo(ctx, x.name, '📄 MỞ'));
  if (x.co_scan) nutDs.push(nutScan(x.name));
  if (x.man_app) {
    const g = el('a', 'sx-btn sx-btn-ghost', '✍ GHI TRÊN APP');
    g.href = x.man_app;
    nutDs.push(g);
  }
  if (nutDs.length) {
    const hang = el('div', 'sx-qc-chips sx-tb-nut');
    nutDs.forEach((n) => hang.appendChild(n));
    the.appendChild(hang);
  }
  return the;
}

/** Tài liệu nên có bản scan bản gốc đã ký (D176): nội bộ, đang hiện hành, không phải biểu mẫu chỉ có trên phần mềm. */
export function canScan(x) {
  return x.trang_thai === 'Hiện hành' && x.nguon === 'Nội bộ' && x.loai !== 'Biểu mẫu trên phần mềm';
}

/** "Chờ tôi ký" (W45): biên bản đang tới lượt mình ký — bấm sang #/tailieu/bienban/<tên>. */
function veChoKy(ds) {
  const box = el('div', 'sx-tl-cando');
  box.appendChild(el('div', 'sx-qc-buoc', `<span class="sx-qc-buoc-ten">Chờ tôi ký</span>
    <span class="sx-qc-buoc-dem">${ds.length} biên bản</span>`));
  ds.forEach((x) => {
    const a = el('a', 'sx-qc-sc sx-qc-sc-cho sx-tl-the');
    a.href = `#/tailieu/bienban/${encodeURIComponent(x.name)}`;
    a.appendChild(el('div', 'sx-qc-sc-ten', `${esc(x.mau)} số ${esc(x.so)} — ${esc(x.ten_mau)}`));
    const meta = el('div', 'sx-qc-sc-meta');
    meta.appendChild(chip(`Ô ${x.vai_tro}`, 'oprp'));
    meta.appendChild(el('span', null, `ngày ${esc(ngayDu(x.ngay))}`));
    a.appendChild(meta);
    box.appendChild(a);
  });
  return box;
}

export function veDanhSach(ctx, dl, tatCa) {
  const c = ctx.container;
  if (!tatCa && dl.cho_ky && dl.cho_ky.length) c.appendChild(veChoKy(dl.cho_ky));
  if (!tatCa && dl.can_doc && dl.can_doc.length) c.appendChild(veCanDoc(ctx, dl.can_doc));
  if (tatCa) {
    const tren = el('div', 'sx-qc-chips sx-tb-nut');
    tren.appendChild(nut('🖨 BM.01.02', null, () => inTheo(ctx, 'in_bm0102', {}, 'BM.01.02 — Danh mục tài liệu nội bộ')));
    tren.appendChild(nut('🖨 BM.01.03', null, () => inTheo(ctx, 'in_bm0103', {}, 'BM.01.03 — Danh mục tài liệu bên ngoài')));
    tren.appendChild(nut('+ TÀI LIỆU BÊN NGOÀI', null, () => moSuaTL(ctx, null, dl)));
    if (dl.duoc_nap && !dl.nap_xong) {
      const n = el('a', 'sx-btn sx-btn-ghost', '📦 NẠP BỘ TÀI LIỆU');
      n.href = '#/tailieu/nap';
      tren.appendChild(n);
    }
    c.appendChild(tren);
    c.appendChild(segment(['Hiện hành', 'Dự thảo', 'Hết hiệu lực', 'Tất cả'], st.tt, (v) => { st.tt = v || 'Hiện hành'; ctx.lai(); }));
    c.appendChild(segment(['Nội bộ', 'Bên ngoài'], st.nguon, (v) => { st.nguon = v || 'Nội bộ'; ctx.lai(); }));
    // D176: bản scan bản gốc đã ký — đếm đã có / cần có, lọc ra những tài liệu còn thiếu để đi scan.
    const can = (dl.ds || []).filter(canScan);
    c.appendChild(el('div', 'sx-qc-goiy', `Bản scan bản gốc đã ký: <b>${can.filter((x) => x.co_scan).length} / ${can.length}</b> `
      + 'tài liệu nội bộ hiện hành.'));
    c.appendChild(segment([{ v: '', ten: 'Mọi tài liệu' }, { v: 'thieu', ten: 'Chưa có bản scan' }], st.scan,
      (v) => { st.scan = v || ''; ctx.lai(); }));
  }
  const tim = el('input', 'sx-textarea sx-tl-tim');
  tim.type = 'search';
  tim.placeholder = 'Tìm mã, tên tài liệu, mã biểu mẫu…';
  tim.value = st.q;
  c.appendChild(tim);
  const ds = (dl.ds || []).filter((x) => !tatCa || ((st.tt === 'Tất cả' || x.trang_thai === st.tt) && x.nguon === st.nguon
    && (st.scan !== 'thieu' || (canScan(x) && !x.co_scan))));
  const vung = el('div', 'sx-qc-than');
  c.appendChild(vung);
  const ve = () => {
    vung.innerHTML = '';
    const loc = locDs(ds, st.q);
    if (!loc.length) {
      vung.appendChild(khungTrong(ds.length ? 'Không có tài liệu khớp.' : (tatCa ? 'Chưa có tài liệu nào — nạp bộ tài liệu.'
        : 'Chưa có tài liệu nào được phân phối cho vai của bạn.')));
      return;
    }
    if (tatCa && st.nguon === 'Bên ngoài') {
      const sx = nut('✓ ĐÃ SOÁT XÉT CẢ DANH MỤC HÔM NAY', null, () => confirm2Step({
        title: 'Soát xét danh mục tài liệu bên ngoài?',
        message: 'Ghi ngày soát xét hôm nay cho mọi tài liệu bên ngoài đang hiện hành (QT.01 — ít nhất 1 lần / năm).',
        confirmLabel: 'ĐÃ SOÁT XÉT',
        onConfirm: async () => { await ctx.call(`${API}.soat_xet`, {}); toast('Đã ghi soát xét'); ctx.lai(); },
      }));
      vung.appendChild(sx);
    }
    nhomTheo(loc).forEach(([ten, xs]) => {
      vung.appendChild(el('div', 'sx-qc-buoc', `<span class="sx-qc-buoc-ten">${esc(ten)}</span>
        <span class="sx-qc-buoc-dem">${xs.length}</span>`));
      xs.forEach((x) => vung.appendChild(veDong(ctx, x, dl, tatCa)));
    });
  };
  tim.addEventListener('input', () => { st.q = tim.value; ve(); });
  ve();
  if (!tatCa && dl.cua_toi && dl.cua_toi.length) {
    c.appendChild(el('div', 'sx-qc-goiy', `Bạn nhận tài liệu của: ${esc(dl.cua_toi.join(', '))}.`));
  }
}

async function moChiTiet(ctx, name, dl) {
  let x;
  try { x = await ctx.call(`${API}.xem`, { name }); } catch (e) { toastErr(e.message); return; }
  const m = openModal({ kicker: `${x.ma || 'Tài liệu'} · ${x.trang_thai}`, title: x.ten });
  const b = m.body;
  const dong = (k, v) => { if (v) b.appendChild(el('div', 'sx-qc-goiy', `${esc(k)}: <b>${esc(v)}</b>`)); };
  dong('Loại', x.loai);
  dong('Lần ban hành', x.lan_ban_hanh);
  dong('Ngày ban hành', ngayDu(x.ngay_ban_hanh));
  dong('Ngày hiệu lực', ngayDu(x.ngay_hieu_luc));
  dong('Đợt ban hành', x.dot_ban_hanh);
  if (x.nguon === 'Bên ngoài') {
    dong('Số hiệu, cơ quan', x.so_hieu_co_quan);
    dong('Nội dung áp dụng', x.noi_dung_ap_dung);
    dong('Dẫn chiếu', x.dan_chieu);
    dong('Bộ phận quản lý', x.bo_phan_quan_ly);
    dong('Soát xét gần nhất', ngayDu(x.ngay_soat_xet));
  }
  const hang = el('div', 'sx-qc-chips sx-tb-nut');
  if (x.co_tep) hang.appendChild(nutMo(ctx, x.name, '📄 MỞ PDF'));
  (x.tep_kem || []).filter((t) => t.co_tep).forEach((t) => hang.appendChild(
    nutMo(ctx, x.name, `🖼 ${t.mo_ta || `tệp kèm ${t.i + 1}`}`, { kem: t.i, kieu: 'sx-btn-ghost' })));
  b.appendChild(hang);
  b.appendChild(veScan(ctx, x, dl, m));
  if ((x.ma_bieu_mau || []).length) {
    b.appendChild(el('div', 'sx-qc-goiy', 'Biểu mẫu trong tệp:'));
    const bm = el('div', 'sx-qc-chips sx-tb-nut');
    x.ma_bieu_mau.forEach((y) => {
      if (y.man_app) {
        const a = el('a', 'sx-btn sx-btn-ghost', `✍ ${esc(y.ma)}`);
        a.href = y.man_app;
        a.addEventListener('click', () => m.close());
        bm.appendChild(a);
      } else bm.appendChild(chip(`${y.ma} (giấy)`));
    });
    b.appendChild(bm);
  }
  if (x.cua_toi && x.cua_toi.can_doc) {
    b.appendChild(el('div', 'sx-qc-goiy', x.cua_toi.doc_luc ? `Bạn đã xác nhận đọc lúc ${esc(x.cua_toi.doc_luc)}`
      : 'Bạn cần đọc và xác nhận tài liệu này (mục Cần đọc ở đầu màn).'));
  }
  if (!dl.la_iso) return;
  b.appendChild(el('div', 'sx-qc-goiy', `Nơi nhận: <b>${esc((x.phan_phoi || []).join(', ') || 'chưa phân phối')}</b>`
    + (x.so_doc ? ` · đã đọc ${x.da_doc}/${x.so_doc} người (lần hiện hành)` : '')));
  if ((x.lich_su || []).length) {
    b.appendChild(el('div', 'sx-qc-sc-ten', 'Các lần ban hành trước'));
    x.lich_su.forEach((l) => {
      const r = el('div', 'sx-qc-chips sx-tb-nut');
      r.appendChild(el('span', 'sx-qc-goiy', `Lần ${esc(l.lan_ban_hanh || '—')} · ${esc(ngayDu(l.ngay_ban_hanh))} → hết `
        + `${esc(ngayDu(l.het_hieu_luc_tu))}${l.tom_tat_thay_doi ? ` · ${esc(l.tom_tat_thay_doi)}` : ''}`));
      if (l.co_tep && l.lan_ban_hanh) r.appendChild(nutMo(ctx, x.name, '📄 bản cũ', { lan: l.lan_ban_hanh, kieu: 'sx-btn-ghost' }));
      if (l.co_scan && l.lan_ban_hanh) r.appendChild(nutScan(x.name, '📎 scan bản cũ', l.lan_ban_hanh));
      b.appendChild(r);
    });
  }
  b.appendChild(nut('SỬA (TÊN, PHÂN PHỐI, BIỂU MẪU KÈM)', 'sx-btn-ghost sx-btn-big', () => { m.close(); moSuaTL(ctx, x, dl); }));
}

/** Bản scan bản gốc đã ký, đóng dấu (D176): ai xem được tài liệu thì mở được; Trưởng Ban ISO gắn / thay / bỏ (PDF,
 *  ảnh ≤ 10 MB). Bản scan đi theo bản hiện hành — ra bản mới thì bản cũ cùng bản scan của nó vào lịch sử. */
export function veScan(ctx, x, dl, m) {
  const box = el('div', 'sx-tl-scan');
  box.appendChild(el('div', 'sx-qc-sc-ten', 'Bản scan (bản gốc đã ký, đóng dấu)'));
  if (x.co_scan) {
    const h = el('div', 'sx-qc-chips sx-tb-nut');
    h.appendChild(nutScan(x.name, '📎 MỞ BẢN SCAN'));
    box.appendChild(h);
    if (dl.la_iso && x.scan_luc) {
      box.appendChild(el('div', 'sx-qc-goiy', `Gắn ${esc(ngayDu(x.scan_luc))} ${esc(String(x.scan_luc).slice(11, 16))}`
        + `${x.scan_boi ? ` · ${esc(x.scan_boi)}` : ''}`));
    }
  } else box.appendChild(el('div', 'sx-qc-goiy', 'Chưa có bản scan.'));
  if (dl.la_iso && x.trang_thai !== 'Hết hiệu lực') {
    const h = el('div', 'sx-qc-chips sx-tb-nut');
    h.appendChild(nutTaiTep(x.co_scan ? '📎 THAY BẢN SCAN' : '📎 GẮN BẢN SCAN', '.pdf,.jpg,.jpeg,.png', async (f, b64) => {
      await ctx.call(`${API}.scan_gan`, { name: x.name, ten: f.name, noi_dung: b64 });
      toast('Đã gắn bản scan');
      if (m) m.close();
      ctx.lai();
    }));
    if (x.co_scan) {
      h.appendChild(nut('BỎ BẢN SCAN', null, () => confirm2Step({
        title: `Bỏ bản scan của ${x.ma || x.ten}?`,
        message: 'Chỉ bỏ khi gắn nhầm tệp. Tài liệu sẽ thành "chưa có bản scan".',
        confirmLabel: 'BỎ BẢN SCAN',
        onConfirm: async () => {
          await ctx.call(`${API}.scan_bo`, { name: x.name });
          toast('Đã bỏ bản scan');
          if (m) m.close();
          ctx.lai();
        },
      })));
    }
    box.appendChild(h);
    box.appendChild(el('div', 'sx-qc-goiy', 'PDF hoặc ảnh, tối đa 10 MB — nhiều trang thì scan thành một PDF.'));
  }
  return box;
}

function moSuaTL(ctx, x, dl) {
  const moi = !x;
  const ngoai = moi || x.nguon === 'Bên ngoài';
  const m = openModal({ kicker: moi ? 'BM.01.03 · thêm tài liệu bên ngoài' : `Sửa ${x.ma || ''}`, title: moi ? 'Tài liệu bên ngoài' : x.ten });
  const b = m.body;
  const ma = oNhap(b, ngoai ? 'Mã / số hiệu' : 'Mã', x ? x.ma : '');
  const ten = oNhap(b, 'Tên tài liệu', x ? x.ten : '');
  const nhom = oNhap(b, 'Nhóm hiển thị', x ? x.nhom_thu_muc : '');
  const loai = moi ? null : oChon(b, 'Loại', (dl.loai || []).map((l) => [l, l]), x.loai);
  let shcq; let nd; let dc; let bp;
  if (ngoai) {
    shcq = oNhap(b, 'Số hiệu, cơ quan ban hành', x ? x.so_hieu_co_quan : '');
    nd = oNhap(b, 'Nội dung áp dụng', x ? x.noi_dung_ap_dung : '', 'ta');
    dc = oNhap(b, 'Nơi dẫn chiếu trong hệ thống', x ? x.dan_chieu : '', 'ta');
    bp = oNhap(b, 'Bộ phận quản lý', x ? x.bo_phan_quan_ly : 'Ban ISO');
  }
  b.appendChild(el('div', 'sx-qc-goiy', 'Nơi nhận (Phụ lục 3) — người thuộc nơi nhận thấy tài liệu này'));
  const layNn = chonNoiNhan(b, (dl.noi_nhan || []).map((n) => n.ten), x ? x.phan_phoi : []);
  let cxn = !!(x && x.can_xac_nhan);
  b.appendChild(segment([{ v: '1', ten: 'Phải xác nhận đã đọc' }, { v: '0', ten: 'Không cần' }], cxn ? '1' : '0',
    (v) => { cxn = v === '1'; }));
  const bm = moi ? null : oNhap(b, 'Mã biểu mẫu trong tệp (cách nhau dấu phẩy)',
    (x.ma_bieu_mau || []).map((y) => y.ma).join(', '));
  const gc = oNhap(b, 'Ghi chú', x ? x.ghi_chu : '', 'ta');
  const luu = nut('LƯU', 'sx-btn-primary sx-btn-big', async () => {
    const p = { ma: ma.value, ten: ten.value, nhom_thu_muc: nhom.value, phan_phoi: layNn(), can_xac_nhan: cxn ? 1 : 0,
      ghi_chu: gc.value };
    if (x) p.name = x.name;
    if (loai) p.loai = loai.value;
    if (ngoai) Object.assign(p, { so_hieu_co_quan: shcq.value, noi_dung_ap_dung: nd.value, dan_chieu: dc.value, bo_phan_quan_ly: bp.value });
    if (bm) {
      const cu = Object.fromEntries((x.ma_bieu_mau || []).map((y) => [y.ma, y]));
      p.ma_bieu_mau = bm.value.split(',').map((s) => s.trim()).filter(Boolean).map((s) => cu[s] || { ma: s });
    }
    luu.disabled = true;
    try { await ctx.call(`${API}.luu_tai_lieu`, { payload: JSON.stringify(p) }); toast('Đã lưu'); m.close(); ctx.lai(); } catch (e) { luu.disabled = false; toastErr(e.message); }
  });
  b.appendChild(luu);
  if (!moi) b.appendChild(el('div', 'sx-qc-goiy', 'Lần BH, ngày, PDF, trạng thái chỉ đổi qua Ban hành (đợt ban hành).'));
}

// ── Đề nghị BM.01.01 ─────────────────────────────────────────────────────────────────────────

async function veDeNghi(ctx) {
  const c = ctx.container;
  const dl = await ctx.call(`${API}.de_nghi_ds`, {});
  if (dl.duoc_lap) c.appendChild(nut('+ LẬP ĐỀ NGHỊ (BM.01.01)', 'sx-btn-primary sx-btn-big', () => moDeNghi(ctx, null, dl)));
  else c.appendChild(el('div', 'sx-qc-goiy', 'Vai của bạn chưa lập được đề nghị tài liệu — báo Trưởng Ban ISO.'));
  const cho = dl.ds.filter((x) => (dl.la_iso && x.trang_thai === 'Chờ xem xét') || (dl.la_gd && x.trang_thai === 'Chờ duyệt'
    && x.nguoi_de_nghi !== dl.user));
  if (cho.length) c.appendChild(el('div', 'sx-qc-goiy', `<b>${cho.length} đề nghị chờ bạn ${dl.la_gd ? 'xem xét / duyệt' : 'xem xét'}</b>`));
  if (!dl.ds.length) { c.appendChild(khungTrong('Chưa có đề nghị nào.')); return; }
  dl.ds.forEach((x) => {
    const the = el('div', `sx-qc-sc${cho.includes(x) ? ' sx-qc-sc-cho' : ''}`);
    the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(x.ten_de_xuat || '')}`));
    const meta = el('div', 'sx-qc-sc-meta');
    meta.appendChild(chip(x.trang_thai, KIEU_DN[x.trang_thai]));
    meta.appendChild(chip(x.loai_yeu_cau));
    meta.appendChild(el('span', null, `${esc(x.name)} · ${esc(x.ho_ten_de_nghi || '')} · ${esc(ngayDu(x.ngay_de_nghi))}`));
    if (x.dot_ban_hanh) meta.appendChild(chip(`đợt ${x.dot_ban_hanh}`, 'dong'));
    the.appendChild(meta);
    the.addEventListener('click', () => moDeNghi(ctx, x, dl));
    c.appendChild(the);
  });
}

function moDeNghi(ctx, x, dl) {
  const cuaToi = !x || x.nguoi_de_nghi === dl.user || x.owner === dl.user;
  const sua = !x || (cuaToi && ['Nháp', 'Trả lại'].includes(x.trang_thai));
  const m = openModal({ kicker: `BM.01.01${x ? ` · ${x.name} · ${x.trang_thai}` : ' · đề nghị mới'}`,
    title: x ? x.ten_de_xuat || '' : 'Phiếu yêu cầu sửa đổi / biên soạn tài liệu' });
  const b = m.body;
  let loai = x ? x.loai_yeu_cau : 'Sửa đổi';
  b.appendChild(el('div', 'sx-qc-goiy', 'Yêu cầu'));
  b.appendChild(segment(dl.loai_yc, loai, (v) => { loai = v || loai; }, !sua));
  const tl = oChon(b, 'Tài liệu (sửa đổi / hủy bỏ)', [['', '— tài liệu mới —'],
    ...dl.tai_lieu.map((t) => [t.name, `${t.ma ? `${t.ma} — ` : ''}${t.ten}${t.lan_ban_hanh ? ` (lần ${t.lan_ban_hanh})` : ''}`])],
  x ? x.tai_lieu : '', !sua);
  const ma = oNhap(b, 'Mã số (tài liệu mới)', x ? x.ma_de_xuat : '', '', !sua);
  const ten = oNhap(b, 'Tên tài liệu (tài liệu mới; sửa đổi để trống = theo tài liệu)', x ? x.ten_de_xuat : '', '', !sua);
  const lan = oNhap(b, 'Lần ban hành (đề xuất)', x ? x.lan_ban_hanh : '', '', !sua);
  const hl = oNhap(b, 'Ngày hiệu lực (đề xuất)', x ? x.ngay_hieu_luc : '', 'date', !sua);
  const bp = oNhap(b, 'Bộ phận', x ? x.bo_phan : '', '', !sua);
  const ld = oNhap(b, 'Lý do (bắt buộc khi gửi)', x ? x.ly_do : '', 'ta', !sua);
  const nd = oNhap(b, 'Nội dung đề nghị', x ? x.noi_dung : '', 'ta', !sua);
  const td = oNhap(b, 'Những phòng ban chịu tác động', x ? x.bo_phan_tac_dong : '', '', !sua);
  const ns = oNhap(b, 'Người soạn thảo', x ? x.nguoi_soan_thao : '', '', !sua);
  const nh = oNhap(b, 'Ngày hoàn thành', x ? x.ngay_hoan_thanh : '', 'date', !sua);
  const goi = () => JSON.stringify({ name: x ? x.name : undefined, loai_yeu_cau: loai, tai_lieu: tl.value, ma_de_xuat: ma.value,
    ten_de_xuat: ten.value, lan_ban_hanh: lan.value, ngay_hieu_luc: hl.value, bo_phan: bp.value, ly_do: ld.value,
    noi_dung: nd.value, bo_phan_tac_dong: td.value, nguoi_soan_thao: ns.value, ngay_hoan_thanh: nh.value });
  const xong = (tb) => { toast(tb); m.close(); ctx.lai(); };
  const lam = async (nutB, f) => { nutB.disabled = true; try { await f(); } catch (e) { nutB.disabled = false; toastErr(e.message); } };
  if (x && (x.y_kien_xem_xet || x.xem_xet_luc)) {
    b.appendChild(el('div', 'sx-qc-goiy', `Ban ISO: ${esc(x.y_kien_xem_xet || 'đồng ý')} — ký trên phần mềm ${esc(x.xem_xet_ten || '')} ${esc(x.xem_xet_luc || '')}`));
  }
  if (x && x.duyet_luc) b.appendChild(el('div', 'sx-qc-goiy', `Giám đốc duyệt: ${esc(x.duyet_ten || '')} ${esc(x.duyet_luc)}${x.y_kien_duyet ? ` · ${esc(x.y_kien_duyet)}` : ''}`));
  if (x && x.nhat_ky) b.appendChild(el('div', 'sx-qc-goiy sx-tl-nk', esc(x.nhat_ky).replace(/\n/g, '<br>')));
  const hang = el('div', 'sx-qc-chips sx-tb-nut');
  if (sua) {
    const l = nut('LƯU NHÁP', null, () => lam(l, async () => { await ctx.call(`${API}.de_nghi_luu`, { payload: goi() }); xong('Đã lưu nháp'); }));
    hang.appendChild(l);
    const g = nut('KÝ GỬI BAN ISO', 'sx-btn-primary', () => lam(g, async () => {
      const r = await ctx.call(`${API}.de_nghi_luu`, { payload: goi() });
      await ctx.call(`${API}.de_nghi_gui`, { name: r.name });
      xong('Đã gửi — chờ Ban ISO xem xét');
    }));
    hang.appendChild(g);
    if (x) {
      hang.appendChild(nutTaiTep(x.co_tep ? '📎 THAY TỆP DỰ THẢO' : '📎 TỆP DỰ THẢO', '.pdf,.docx,.doc', async (f, nd64) => {
        await ctx.call(`${API}.de_nghi_tep`, { name: x.name, ten: f.name, noi_dung: nd64 });
        toast('Đã gắn tệp dự thảo');
      }));
    }
  }
  if (x && x.trang_thai === 'Chờ xem xét' && dl.la_iso) {
    const yk = oNhap(b, 'Ý kiến Ban ISO (bắt buộc khi trả lại)', '', 'ta');
    hang.appendChild(nut('ĐỒNG Ý — CHUYỂN GIÁM ĐỐC DUYỆT', 'sx-btn-primary', (e) => lam(e.currentTarget, async () => {
      await ctx.call(`${API}.de_nghi_xem_xet`, { name: x.name, dong_y: 1, y_kien: yk.value }); xong('Đã chuyển Giám đốc duyệt');
    })));
    hang.appendChild(nut('TRẢ LẠI', null, (e) => lam(e.currentTarget, async () => {
      await ctx.call(`${API}.de_nghi_xem_xet`, { name: x.name, dong_y: 0, y_kien: yk.value }); xong('Đã trả lại');
    })));
  }
  if (x && x.trang_thai === 'Chờ duyệt' && dl.la_gd && x.nguoi_de_nghi !== dl.user) {
    const yk = oNhap(b, 'Ý kiến phê duyệt (bắt buộc khi trả lại)', '', 'ta');
    hang.appendChild(nut('DUYỆT', 'sx-btn-primary', (e) => lam(e.currentTarget, async () => {
      await ctx.call(`${API}.de_nghi_duyet`, { name: x.name, dong_y: 1, y_kien: yk.value }); xong('Đã duyệt — chờ đưa vào đợt ban hành');
    })));
    hang.appendChild(nut('TRẢ LẠI', null, (e) => lam(e.currentTarget, async () => {
      await ctx.call(`${API}.de_nghi_duyet`, { name: x.name, dong_y: 0, y_kien: yk.value }); xong('Đã trả lại');
    })));
  }
  if (x && x.co_tep) {
    const a = el('a', 'sx-btn sx-btn-ghost', '📄 TỆP DỰ THẢO');
    a.href = `/api/method/${API}.de_nghi_tai_tep?name=${encodeURIComponent(x.name)}`;
    a.target = '_blank';
    hang.appendChild(a);
  }
  if (x) hang.appendChild(nut('🖨 IN BM.01.01', null, () => inTheo(ctx, 'in_bm0101', { name: x.name }, `BM.01.01 — ${x.name}`)));
  if (x && !['Đã duyệt', 'Hủy'].includes(x.trang_thai) && (cuaToi || dl.la_iso)) {
    hang.appendChild(nut('HỦY ĐỀ NGHỊ', null, () => {
      const ly = window.prompt('Lý do hủy đề nghị');
      if (ly === null) return;
      ctx.call(`${API}.de_nghi_huy`, { name: x.name, ly_do: ly }).then(() => xong('Đã hủy')).catch((e) => toastErr(e.message));
    }));
  }
  b.appendChild(hang);
}

// ── Ban hành ─────────────────────────────────────────────────────────────────────────────────

async function veBanHanh(ctx) {
  const c = ctx.container;
  const dl = await ctx.call(`${API}.dot_ds`, {});
  const tren = el('div', 'sx-qc-chips sx-tb-nut');
  tren.appendChild(nut('+ LẬP ĐỢT BAN HÀNH', 'sx-btn-primary', async (e) => {
    e.currentTarget.disabled = true;
    try {
      const r = await ctx.call(`${API}.dot_luu`, { payload: JSON.stringify({}) });
      window.location.hash = `#/tailieu/dot/${encodeURIComponent(r.name)}`;
    } catch (er) { e.currentTarget.disabled = false; toastErr(er.message); }
  }));
  if (st.quyen && st.quyen.duoc_nap && !st.quyen.nap_xong) {
    const n = el('a', 'sx-btn sx-btn-ghost', '📦 NẠP BỘ TÀI LIỆU');
    n.href = '#/tailieu/nap';
    tren.appendChild(n);
  }
  c.appendChild(tren);
  if (dl.de_nghi_cho.length) {
    c.appendChild(el('div', 'sx-qc-goiy', `<b>${dl.de_nghi_cho.length} đề nghị đã duyệt chưa vào đợt nào</b> — mở đợt nháp, `
      + 'bấm KÉO ĐỀ NGHỊ ĐÃ DUYỆT.'));
  }
  if (!dl.ds.length) { c.appendChild(khungTrong('Chưa có đợt ban hành nào.')); return; }
  dl.ds.forEach((x) => {
    const a = el('a', `sx-qc-sc sx-tl-the${x.trang_thai === 'Nháp' ? ' sx-qc-sc-cho' : ''}`);
    a.href = `#/tailieu/dot/${encodeURIComponent(x.name)}`;
    a.appendChild(el('div', 'sx-qc-sc-ten', `${esc(x.name)}${x.so_quyet_dinh ? ` · QĐ ${esc(x.so_quyet_dinh)}` : ''}`));
    const meta = el('div', 'sx-qc-sc-meta');
    meta.appendChild(chip(x.trang_thai, x.trang_thai === 'Nháp' ? 'oprp' : 'dong'));
    meta.appendChild(el('span', null, `${x.so_dong} tài liệu · ban hành ${esc(ngayDu(x.ngay_ban_hanh) || '…')}`));
    if (x.tien_do && x.tien_do.tong) {
      meta.appendChild(chip(`đã đọc ${x.tien_do.da}/${x.tien_do.tong}`, x.tien_do.da === x.tien_do.tong ? 'dong' : 'oprp'));
    }
    a.appendChild(meta);
    c.appendChild(a);
  });
}

export function veTienDo(td) {
  const box = el('div', 'sx-qc-sc');
  box.appendChild(el('div', 'sx-qc-sc-ten', `Tiến độ đọc: ${td.da}/${td.tong} lượt · ${td.nguoi_xong}/${td.nguoi} người xong`));
  (td.chua_doc || []).forEach((n) => box.appendChild(el('div', 'sx-qc-goiy',
    `${esc(n.ho_ten)}${n.vai ? ` (${esc(n.vai)})` : ''} — chưa đọc: ${esc(n.chua.join(', '))}`)));
  if (!td.tong) box.appendChild(el('div', 'sx-qc-goiy', 'Đợt không có yêu cầu đọc trên app.'));
  return box;
}

async function veDot(ctx, name) {
  const c = ctx.container;
  const [d, dl] = await Promise.all([ctx.call(`${API}.dot_xem`, { name }), ctx.call(`${API}.dot_ds`, {})]);
  const nhap = d.trang_thai === 'Nháp';
  const quay = el('a', 'sx-btn sx-btn-ghost', '← CÁC ĐỢT');
  quay.href = '#/tailieu/banhanh';
  c.appendChild(quay);
  c.appendChild(el('div', 'sx-qc-top', `<div class="sx-qc-ngay">Đợt ${esc(d.name)}</div>`));
  const tt = el('div', 'sx-qc-sc-meta');
  tt.appendChild(chip(d.trang_thai, nhap ? 'oprp' : 'dong'));
  if (d.ban_hanh_luc) tt.appendChild(el('span', null, `ban hành bởi ${esc(d.ban_hanh_ten)} lúc ${esc(d.ban_hanh_luc)}`));
  c.appendChild(tt);
  const f = el('div', 'sx-qc-sc');
  const so = oNhap(f, 'Số quyết định', d.so_quyet_dinh, '', !nhap);
  const nbh = oNhap(f, 'Ngày ban hành', d.ngay_ban_hanh, 'date', !nhap);
  const nhl = oNhap(f, 'Ngày hiệu lực', d.ngay_hieu_luc, 'date', !nhap);
  let ycd = d.tao_yeu_cau_doc;
  f.appendChild(segment([{ v: '1', ten: 'Tạo yêu cầu đọc' }, { v: '0', ten: 'Không (đã phổ biến giấy)' }],
    String(ycd), (v) => { ycd = Number(v || 0); }, !nhap));
  const gc = oNhap(f, 'Ghi chú', d.ghi_chu, 'ta', !nhap);
  const qd = el('div', 'sx-qc-chips sx-tb-nut');
  if (d.co_qd) {
    const a = el('a', 'sx-btn sx-btn-ghost', '📄 QĐ ĐÃ KÝ');
    a.href = `/api/method/${API}.dot_tai_tep?name=${encodeURIComponent(d.name)}&dich=qd`;
    a.target = '_blank';
    qd.appendChild(a);
  }
  if (nhap) {
    qd.appendChild(nutTaiTep(d.co_qd ? '📎 THAY QĐ SCAN' : '📎 TẢI QĐ ĐÃ KÝ (PDF)', '.pdf', async (fi, nd64) => {
      await ctx.call(`${API}.dot_tep`, { name: d.name, dich: 'qd', ten: fi.name, noi_dung: nd64 });
      toast('Đã tải quyết định');
      ctx.lai();
    }));
  }
  f.appendChild(qd);
  c.appendChild(f);

  const rows = d.ds.map((r) => ({ ...r }));
  const ds = el('div', 'sx-qc-than');
  c.appendChild(el('div', 'sx-qc-buoc', `<span class="sx-qc-buoc-ten">Phụ lục 1 — tài liệu trong đợt</span>
    <span class="sx-qc-buoc-dem">${rows.length}</span>`));
  c.appendChild(ds);
  const veRows = () => {
    ds.innerHTML = '';
    rows.forEach((r, i) => {
      const the = el('div', `sx-qc-sc${r.co_tep || r.hanh_dong === 'Giữ nguyên' || r.hanh_dong === 'Hủy bỏ' ? '' : ' sx-qc-sc-cho'}`);
      the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(r.ma ? `${r.ma} — ` : '')}${esc(r.ten || '(tài liệu mới)')}`));
      const meta = el('div', 'sx-qc-sc-meta');
      meta.appendChild(chip(r.hanh_dong));
      if (r.lan_ban_hanh_moi) meta.appendChild(el('span', null, `lần ${esc(r.lan_hien || '—')} → ${esc(r.lan_ban_hanh_moi)}`));
      if (r.de_nghi) meta.appendChild(chip(r.de_nghi));
      if (r.co_tep) meta.appendChild(chip('có PDF', 'dong'));
      the.appendChild(meta);
      if (r.tom_tat) the.appendChild(el('div', 'sx-qc-goiy', esc(r.tom_tat)));
      const hang = el('div', 'sx-qc-chips sx-tb-nut');
      if (r.co_tep && r.row) {
        const a = el('a', 'sx-btn sx-btn-ghost', '📄 PDF');
        a.href = `/api/method/${API}.dot_tai_tep?name=${encodeURIComponent(d.name)}&dich=row:${encodeURIComponent(r.row)}`;
        a.target = '_blank';
        hang.appendChild(a);
      }
      if (nhap) {
        if (r.row && ['Ban hành mới', 'Sửa đổi – thay thế', 'Ban hành lại – thay thế'].includes(r.hanh_dong)) {
          hang.appendChild(nutTaiTep(r.co_tep ? '📎 THAY PDF' : '📎 TẢI PDF ĐÃ KÝ', '.pdf', async (fi, nd64) => {
            await ctx.call(`${API}.dot_tep`, { name: d.name, dich: `row:${r.row}`, ten: fi.name, noi_dung: nd64 });
            toast('Đã tải PDF');
            ctx.lai();
          }));
        }
        hang.appendChild(nut('SỬA', null, () => moDong(r, dl, () => veRows())));
        hang.appendChild(nut('BỎ', null, () => { rows.splice(i, 1); veRows(); }));
      }
      the.appendChild(hang);
      ds.appendChild(the);
    });
    if (!rows.length) ds.appendChild(khungTrong('Đợt chưa có tài liệu.'));
  };
  veRows();
  if (nhap) {
    const luu = () => ctx.call(`${API}.dot_luu`, { payload: JSON.stringify({ name: d.name, so_quyet_dinh: so.value,
      ngay_ban_hanh: nbh.value, ngay_hieu_luc: nhl.value, tao_yeu_cau_doc: ycd, ghi_chu: gc.value, ds: rows }) });
    const them = el('div', 'sx-qc-chips sx-tb-nut');
    them.appendChild(nut('+ THÊM TÀI LIỆU', null, () => moDong(null, dl, (r) => { rows.push(r); veRows(); })));
    if (dl.de_nghi_cho.length) {
      them.appendChild(nut(`⇣ KÉO ĐỀ NGHỊ ĐÃ DUYỆT (${dl.de_nghi_cho.length})`, null, async (e) => {
        e.currentTarget.disabled = true;
        try { await luu(); const r = await ctx.call(`${API}.dot_keo_de_nghi`, { name: d.name }); toast(`Đã kéo ${r.them} đề nghị`); ctx.lai(); } catch (er) { toastErr(er.message); }
      }));
    }
    c.appendChild(them);
    const l = nut('LƯU ĐỢT', 'sx-btn-ghost sx-btn-big', async () => {
      l.disabled = true;
      try { await luu(); toast('Đã lưu đợt'); ctx.lai(); } catch (e) { l.disabled = false; toastErr(e.message); }
    });
    c.appendChild(l);
    if (d.thieu.length) c.appendChild(el('div', 'sx-qc-goiy', `<b>Chưa ban hành được:</b><br>${d.thieu.map(esc).join('<br>')}`));
    const bh = nut('BAN HÀNH', 'sx-btn-primary sx-btn-big', () => confirm2Step({
      title: `Ban hành đợt ${d.name}?`,
      message: 'Bản cũ vào lịch sử, bản mới thành Hiện hành, tài liệu hủy bỏ hết hiệu lực, người thuộc nơi nhận nhận '
        + 'yêu cầu đọc. Đợt khóa sau khi ban hành.',
      confirmLabel: 'BAN HÀNH',
      onConfirm: async () => {
        await luu();
        const r = await ctx.call(`${API}.ban_hanh`, { name: d.name });
        toast(`Đã ban hành ${r.so_tai_lieu} tài liệu · ${r.yeu_cau_doc} yêu cầu đọc`);
        ctx.lai();
      },
    }));
    c.appendChild(bh);
    c.appendChild(nut('XÓA ĐỢT NHÁP', null, () => confirm2Step({
      title: `Xóa đợt ${d.name}?`, message: 'Lập nhầm thì xóa; đề nghị trong đợt trở về chờ đợt khác.', confirmLabel: 'XÓA',
      onConfirm: async () => { await ctx.call(`${API}.dot_xoa`, { name: d.name }); window.location.hash = '#/tailieu/banhanh'; },
    })));
  } else {
    c.appendChild(veTienDo(d.tien_do));
    c.appendChild(nut('🖨 IN BM.01.13', 'sx-btn-primary', () => inTheo(ctx, 'in_bm0113', { name: d.name }, `BM.01.13 — ${d.name}`)));
  }
  c.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">Hồ sơ của đợt</span>'));
  d.ho_so.forEach((h) => {
    const r = el('div', 'sx-qc-chips sx-tb-nut');
    if (h.co_tep) {
      const a = el('a', 'sx-btn sx-btn-ghost', `📄 ${esc(h.mo_ta || 'hồ sơ')}`);
      a.href = `/api/method/${API}.dot_tai_tep?name=${encodeURIComponent(d.name)}&dich=hs:${encodeURIComponent(h.row)}`;
      a.target = '_blank';
      r.appendChild(a);
    } else r.appendChild(el('span', 'sx-qc-goiy', `${esc(h.mo_ta)} — chưa có tệp`));
    c.appendChild(r);
  });
  c.appendChild(nutTaiTep('📎 THÊM HỒ SƠ (biên bản phổ biến có chữ ký, BM.01.01 giấy…)', '.pdf,.png,.jpg,.jpeg', async (fi, nd64) => {
    await ctx.call(`${API}.dot_tep`, { name: d.name, dich: 'hs', ten: fi.name, noi_dung: nd64 });
    toast('Đã thêm hồ sơ');
    ctx.lai();
  }));
}

function moDong(r, dl, xong) {
  const m = openModal({ kicker: 'Phụ lục 1', title: r ? `${r.ma || ''} ${r.ten || ''}` : 'Thêm tài liệu vào đợt' });
  const b = m.body;
  let hd = r ? r.hanh_dong : 'Sửa đổi – thay thế';
  b.appendChild(el('div', 'sx-qc-goiy', 'Hành động'));
  b.appendChild(segment(dl.hanh_dong, hd, (v) => { hd = v || hd; }));
  const tl = oChon(b, 'Tài liệu (trống = ban hành tài liệu mới)', [['', '— tài liệu mới —'],
    ...dl.tai_lieu.map((t) => [t.name, `${t.ma ? `${t.ma} — ` : ''}${t.ten}${t.lan_ban_hanh ? ` (lần ${t.lan_ban_hanh})` : ''}`])],
  r ? r.tai_lieu : '');
  const ma = oNhap(b, 'Mã (tài liệu mới)', r ? r.ma : '');
  const ten = oNhap(b, 'Tên (tài liệu mới)', r ? r.ten : '');
  const loai = oChon(b, 'Loại (tài liệu mới)', [['', '—'], ...dl.loai.map((l) => [l, l])], r ? r.loai : '');
  const lan = oNhap(b, 'Lần ban hành mới', r ? r.lan_ban_hanh_moi : '');
  const tt = oNhap(b, 'Tóm tắt thay đổi / nội dung chính phổ biến', r ? r.tom_tat : '', 'ta');
  b.appendChild(el('div', 'sx-qc-goiy', 'Nơi nhận (tài liệu mới — tài liệu đã có giữ phân phối của nó)'));
  const layNn = chonNoiNhan(b, dl.noi_nhan, r && r.phan_phoi ? r.phan_phoi.split(',').map((s) => s.trim()) : []);
  b.appendChild(nut('XONG', 'sx-btn-primary sx-btn-big', () => {
    const t = dl.tai_lieu.find((y) => y.name === tl.value);
    const moi = { ...(r || {}), hanh_dong: hd, tai_lieu: tl.value, ma: t ? t.ma : ma.value, ten: t ? t.ten : ten.value,
      loai: loai.value, lan_ban_hanh_moi: lan.value, tom_tat: tt.value, phan_phoi: layNn().join(', '),
      lan_hien: t ? t.lan_ban_hanh : '' };
    if (r) Object.assign(r, moi);
    m.close();
    xong(r || moi);
  }));
}

// ── Nạp bộ tài liệu ban hành 21/9/2026 (một lần) ──────────────────────────────────────────────────
// D180: danh mục (sổ đăng ký, BM.01.03, Phụ lục 3) ĐI KÈM APP — một nút NẠP DANH MỤC, không còn chọn 3 tệp .json; tệp
// PDF chọn thẳng tai_lieu_pdf.zip (giải nén ngay trên máy — lib/zip.js) hoặc các tệp PDF, PNG như cũ. Mở màn là thấy
// đã nạp tới đâu (tinh_trang_nap) — tải lại trang vẫn đúng chỗ dở; nạp đủ thì nút NẠP BỘ ở Ban hành / Tất cả ẩn đi.

const MB10 = 10 * 1024 * 1024;

/** {tên tệp: {ten, co, lay}} từ các tệp đã chọn — tệp .zip mở ra từng tệp bên trong; khớp theo tên không thư mục. */
export async function gomTep(files) {
  const ra = {};
  for (const f of Array.from(files || [])) {
    if (/\.zip$/i.test(f.name)) {
      (await docZip(f)).forEach((x) => { const t = tenGoc(x.ten); if (!ra[t]) ra[t] = x; });
    } else if (!ra[f.name]) ra[f.name] = { ten: f.name, co: f.size, lay: async () => f };
  }
  return ra;
}

const soNap = (t) => `${t.tai_lieu[0]}/${t.tai_lieu[1]} tài liệu nội bộ · ${t.ngoai[0]}/${t.ngoai[1]} tài liệu bên ngoài · `
  + `${t.noi_nhan[0]}/${t.noi_nhan[1]} nơi nhận${t.dot === null ? '' : ` · đợt ${ngayDu(t.ngay)} ${t.dot ? 'đã có' : 'chưa có'}`}`;

async function veNap(ctx) {
  const c = ctx.container;
  c.appendChild(el('div', 'sx-qc-top', '<div class="sx-qc-ngay">Nạp bộ tài liệu ban hành 21/9/2026 (một lần)</div>'));
  const than = el('div');
  const kq = el('div', 'sx-qc-goiy');
  c.appendChild(than);
  c.appendChild(kq);
  let tt = null;
  let yeuCau = false;
  const napDanhMuc = async () => {
    const r = await ctx.call(`${API}.nap_bo`, { payload: JSON.stringify({ tao_yeu_cau_doc: yeuCau ? 1 : 0 }) });
    (r.loi || []).forEach((l) => toastErr(l));
  };
  const taiTep = async (files) => {
    let tep;
    try { tep = await gomTep(files); } catch (e) { toastErr(e.message); return; }
    if (!tt.danh_muc_xong) {               // chọn tệp trước khi nạp danh mục: nạp luôn, khỏi bắt bấm hai nút
      try { await napDanhMuc(); tt = await ctx.call(`${API}.tinh_trang_nap`); } catch (e) { toastErr(e.message); return; }
    }
    const viec = tt.can_tep.filter((x) => !x.co && tep[x.tep]);
    const loi = [];
    let xong = 0;
    for (const x of viec) {
      const y = tep[x.tep];
      kq.textContent = `Đang tải ${xong + loi.length + 1}/${viec.length}: ${x.tep}`;
      try {
        if (y.co > MB10) throw new Error('quá 10 MB');
        const b = await y.lay();
        await ctx.call(`${API}.nap_tep`, { khoa: x.khoa, ten: x.tep, noi_dung: await docTep(new File([b], x.tep)) });
        xong += 1;
      } catch (e) { loi.push(`${x.tep}: ${e.message}`); }
    }
    kq.innerHTML = `Đã tải ${xong}/${viec.length} tệp.${!viec.length ? ' Không tệp nào khớp tên tệp còn thiếu.' : ''}`
      + `${loi.length ? `<br>⚠ ${loi.map(esc).join('<br>⚠ ')}` : ''}`;
  };
  const ve = async () => {
    try { tt = await ctx.call(`${API}.tinh_trang_nap`); } catch (e) { toastErr(e.message); return; }
    than.innerHTML = '';
    const tong = tt.tong_tep || tt.can_tep.length;
    const thieu = tt.can_tep.filter((x) => !x.co);
    if (tt.xong) {
      if (st.quyen) st.quyen.nap_xong = true;
      than.appendChild(el('div', 'sx-qc-sc', `<div class="sx-qc-sc-ten">✓ Đã nạp đủ bộ tài liệu</div><div class="sx-qc-goiy">`
        + `${soNap(tt)} · ${tong}/${tong} tệp. Phân phối, bản scan: tab Tất cả; lần ban hành sau: tab Ban hành.</div>`));
      return;
    }
    const b1 = el('div', 'sx-qc-sc', `<div class="sx-qc-sc-ten">${tt.danh_muc_xong ? '✓' : '①'} Danh mục</div>`
      + `<div class="sx-qc-goiy">${soNap(tt)}</div>`);
    if (!tt.danh_muc_xong) {
      const hoi = el('label', 'sx-qc-goiy');
      const cb = el('input');
      cb.type = 'checkbox';
      cb.checked = yeuCau;
      cb.addEventListener('change', () => { yeuCau = !!cb.checked; });
      hoi.appendChild(cb);
      hoi.appendChild(el('span', null, ' Tạo yêu cầu "Đã đọc, hiểu" cho đợt này (thường không cần — đã phổ biến bản giấy 22/9)'));
      b1.appendChild(hoi);
      b1.appendChild(nut('NẠP DANH MỤC', 'sx-btn-primary sx-btn-big', async (e) => {
        e.currentTarget.disabled = true;
        try { await napDanhMuc(); } catch (er) { toastErr(er.message); }
        await ve();
      }));
    }
    than.appendChild(b1);
    const b2 = el('div', 'sx-qc-sc', `<div class="sx-qc-sc-ten">② Tệp PDF, ảnh</div><div class="sx-qc-goiy">`
      + `${tt.can_tep.length - thieu.length}/${tong} tệp đã có trên app. Chọn tệp <b>tai_lieu_pdf.zip</b> — không cần `
      + 'giải nén (hoặc chọn các tệp PDF, PNG). App tự khớp tên, tải lần lượt; tệp đã có thì bỏ qua.</div>');
    const inp = el('input');
    inp.type = 'file';
    inp.accept = '.zip,.pdf,.png';
    inp.multiple = true;
    inp.style.display = 'none';
    // nút của app thay ô chọn tệp của trình duyệt ("Choose Files"); chưa nạp danh mục thì nút phụ — chọn vẫn được
    const chon = nut('📦 CHỌN TỆP tai_lieu_pdf.zip', tt.danh_muc_xong ? 'sx-btn-primary sx-btn-big' : '',
      () => inp.click());
    inp.addEventListener('change', async () => {
      if (!inp.files || !inp.files.length) return;
      chon.disabled = true;
      await taiTep(inp.files);
      await ve();
    });
    b2.appendChild(chon);
    b2.appendChild(inp);
    if (tt.danh_muc_xong && thieu.length) {
      b2.appendChild(el('div', 'sx-qc-goiy', `Còn thiếu ${thieu.length} tệp: ${esc(thieu.slice(0, 8).map((x) => x.tep)
        .join(', '))}${thieu.length > 8 ? '…' : ''}`));
    }
    than.appendChild(b2);
  };
  await ve();
}
