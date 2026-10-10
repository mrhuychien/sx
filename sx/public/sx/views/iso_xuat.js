// #/iso/xuat — Xuất báo cáo cho đoàn kiểm tra (D176): chọn biểu mẫu + kỳ → Excel / PDF.
//
// Biểu mẫu xếp theo nhóm của danh mục hồ sơ (BM.01.04), mỗi biểu mẫu nói sẽ ra những tờ nào (mỗi tháng một tờ, danh
// mục hiện hành…). Kỳ chọn nhanh: tháng này / trước, quý này / trước, 3 / 6 tháng, năm nay / trước. Bấm XUẤT là máy
// chủ dựng NỀN (PDF nhiều tháng là hàng trăm trang): lần xuất hiện ngay ở "Các lần xuất" — Đang chờ / Đang tạo (màn
// tự hỏi lại) → Xong (TẢI VỀ) hoặc Lỗi (lý do, LÀM LẠI). Hàng đợi máy chủ không chạy thì sau 20 giây có CHẠY NGAY.
// Lần xuất được giữ lại: ai, lúc nào, kỳ nào, cho đoàn nào. API sx/api/qc_xuatbc.py, luật dựng sx/qc/xuat_bao_cao.py.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, tabXemXet } from '/assets/sx/sx/components/qcui.js';

const API = 'sx.api.qc_xuatbc';
// Lựa chọn giữ qua các lần vẽ lại (đổi tab rồi quay lại không mất biểu mẫu đã chọn).
export const st = { chon: null, tu: '', den: '', ghi_chu: '', q: '', thay: {}, hoi: 0, nhip: 0 };
export const CHO_LAU = 20;          // giây lần xuất còn Đang chờ thì hiện CHẠY NGAY (hàng đợi máy chủ không chạy)
export const HOI_LAI = 2500;        // ms giữa hai lần hỏi trạng thái (st.nhip đè — test)
const DANG = ['Đang chờ', 'Đang tạo'];
const KIEU_TT = { 'Đang chờ': 'oprp', 'Đang tạo': 'oprp', Xong: 'dong', 'Lỗi': 'cao' };
export const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const gioDu = (s) => (s ? `${ngayDu(s)} ${String(s).slice(11, 16)}` : '');

export const KY_NHANH = [['thang', 'Tháng này'], ['thang_truoc', 'Tháng trước'], ['quy', 'Quý này'],
  ['quy_truoc', 'Quý trước'], ['3thang', '3 tháng'], ['6thang', '6 tháng'], ['nam', 'Năm nay'],
  ['nam_truoc', 'Năm trước']];

/** Kỳ chọn nhanh từ ngày hôm nay của máy chủ ('YYYY-MM-DD' — chuỗi, không qua Date của máy để khỏi lệch múi giờ).
 *  Kỳ "đang chạy" (tháng / quý / năm này, 3 / 6 tháng) tính tới hôm nay; kỳ "trước" là kỳ trọn vẹn. */
export function kyNhanh(ma, homNay) {
  const [y, m] = homNay.split('-').map(Number);
  const ngay = (yy, mm, dd) => `${yy}-${String(mm).padStart(2, '0')}-${String(dd).padStart(2, '0')}`;
  const cuoi = (yy, mm) => new Date(Date.UTC(yy, mm, 0)).getUTCDate();
  const lui = (yy, mm, n) => { const t = yy * 12 + (mm - 1) - n; return [Math.floor(t / 12), (t % 12) + 1]; };
  const q0 = Math.floor((m - 1) / 3) * 3 + 1;
  if (ma === 'thang') return [ngay(y, m, 1), homNay];
  if (ma === 'thang_truoc') { const [a, b] = lui(y, m, 1); return [ngay(a, b, 1), ngay(a, b, cuoi(a, b))]; }
  if (ma === 'quy') return [ngay(y, q0, 1), homNay];
  if (ma === 'quy_truoc') {
    const [a, b] = lui(y, q0, 3);
    const [c, d] = lui(y, q0, 1);
    return [ngay(a, b, 1), ngay(c, d, cuoi(c, d))];
  }
  if (ma === '3thang' || ma === '6thang') {
    const [a, b] = lui(y, m, ma === '3thang' ? 2 : 5);
    return [ngay(a, b, 1), homNay];
  }
  if (ma === 'nam') return [ngay(y, 1, 1), homNay];
  if (ma === 'nam_truoc') return [ngay(y - 1, 1, 1), ngay(y - 1, 12, 31)];
  return null;
}

function nut(chu, kieu, onClick) {
  const b = el('button', `sx-btn ${kieu || 'sx-btn-ghost'}`, esc(chu));
  b.type = 'button';
  if (onClick) b.addEventListener('click', onClick);
  return b;
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  let dl;
  try {
    dl = await call(`${API}.tong_quan`, {});
  } catch (e) {
    container.innerHTML = '';
    container.appendChild(tabXemXet('xuat'));
    container.appendChild(khungTrong(e.message));
    return;
  }
  container.innerHTML = '';
  container.appendChild(tabXemXet('xuat'));
  const than = el('div', 'sx-qc-than sx-xbc');
  container.appendChild(than);
  ve({ ...api, container: than, lai: () => render(api) }, dl);
}

/** Vẽ màn xuất vào ctx.container từ dữ liệu tong_quan. */
export function ve(ctx, dl) {
  const c = ctx.container;
  if (!st.chon) st.chon = new Set();
  if (!st.tu || !st.den) { st.tu = dl.tu; st.den = dl.den; }
  c.appendChild(el('div', 'sx-qc-top', `<div style="flex:1;min-width:0">
    <div class="sx-qc-ngay">Xuất báo cáo cho đoàn kiểm tra</div>
    <div class="sx-qc-ai">Chọn biểu mẫu và kỳ → Excel (mỗi tờ in một sheet, có Mục lục) hoặc PDF (gộp một tệp, bìa
    mục lục, bookmark từng biểu mẫu). Nội dung là chính bản in của từng biểu mẫu.</div></div>`));
  c.appendChild(veKy(dl));
  c.appendChild(veBieuMau(dl));
  const hang = el('div', 'sx-qc-chips sx-xbc-nut');
  const xuat = (kieu) => async (e) => {
    const b = e && e.currentTarget;
    const loi = kiemTruoc();
    if (loi) { toastErr(loi); return; }
    if (b) b.disabled = true;
    try {
      const r = await ctx.call(`${API}.xuat`, { payload: JSON.stringify({ kieu, tu: st.tu, den: st.den,
        ghi_chu: st.ghi_chu, bieu_mau: thuTuChon(dl) }) });
      toast(`Đã gửi ${r.name} — máy chủ đang dựng tệp ${kieu}, xong sẽ có nút TẢI VỀ.`);
      ctx.lai();
    } catch (err) { toastErr(err.message); }
    if (b) b.disabled = false;
  };
  hang.appendChild(nut('⬇ XUẤT EXCEL', 'sx-btn-primary sx-btn-big', xuat('Excel')));
  hang.appendChild(nut('⬇ XUẤT PDF', 'sx-btn-primary sx-btn-big', xuat('PDF')));
  c.appendChild(hang);
  c.appendChild(el('div', 'sx-qc-goiy', 'Gói zip đủ hồ sơ (cả bản scan đính kèm) ở tab Hồ sơ đánh giá.'));
  veLanXuat(ctx, dl.ds || []);
}

/** Lỗi chặn trước khi gửi (máy chủ kiểm lại y như vậy). */
export function kiemTruoc() {
  if (!st.chon || !st.chon.size) return 'Chọn ít nhất một biểu mẫu.';
  if (!st.tu || !st.den) return 'Chọn kỳ: từ ngày, đến ngày.';
  if (st.tu > st.den) return 'Từ ngày phải trước đến ngày.';
  return '';
}

/** Mã đã chọn theo thứ tự trên màn (nhóm, rồi mã) — tệp xuất theo đúng thứ tự người đang nhìn. */
export function thuTuChon(dl) {
  const ra = [];
  (dl.nhom || []).forEach((n) => n.bm.forEach((b) => { if (st.chon.has(b.ma)) ra.push(b.ma); }));
  return ra;
}

function veKy(dl) {
  const ky = el('div', 'sx-qc-sc sx-xbc-chonky');
  ky.appendChild(el('div', 'sx-qc-sc-ten', 'Kỳ'));
  const o = el('div', 'sx-hs-ky');
  const tu = el('input', 'sx-textarea');
  tu.type = 'date';
  tu.value = st.tu;
  const den = el('input', 'sx-textarea');
  den.type = 'date';
  den.value = st.den;
  tu.addEventListener('change', () => { st.tu = tu.value; });
  den.addEventListener('change', () => { st.den = den.value; });
  const nhanh = el('div', 'sx-qc-chips');
  KY_NHANH.forEach(([ma, ten]) => {
    const b = el('button', 'sx-qc-tag', esc(ten));
    b.type = 'button';
    b.addEventListener('click', () => {
      [st.tu, st.den] = kyNhanh(ma, dl.hom_nay);
      tu.value = st.tu;
      den.value = st.den;
    });
    nhanh.appendChild(b);
  });
  ky.appendChild(nhanh);
  o.appendChild(el('label', null, 'Từ ngày'));
  o.appendChild(tu);
  o.appendChild(el('label', null, 'Đến ngày'));
  o.appendChild(den);
  ky.appendChild(o);
  const gc = el('input', 'sx-textarea');
  gc.type = 'text';
  gc.value = st.ghi_chu;
  gc.placeholder = 'Ghi chú: đoàn kiểm tra / mục đích (vd Đoàn Orion 10/2026)';
  gc.addEventListener('input', () => { st.ghi_chu = gc.value; });
  ky.appendChild(gc);
  ky.appendChild(el('div', 'sx-qc-goiy', `Tối đa ${dl.toi_da_thang || 24} tháng một lần xuất.`));
  return ky;
}

function veBieuMau(dl) {
  const box = el('div', 'sx-qc-sc sx-xbc-bm');
  const tong = (dl.nhom || []).reduce((s, n) => s + n.bm.length, 0);
  const dau = el('div', 'sx-qc-sc-ten', '');
  const demChon = () => { dau.textContent = `Biểu mẫu · đã chọn ${st.chon.size} / ${tong}`; };
  box.appendChild(dau);
  const tim = el('input', 'sx-textarea sx-xbc-tim');
  tim.type = 'search';
  tim.placeholder = 'Tìm mã, tên biểu mẫu…';
  tim.value = st.q;
  box.appendChild(tim);
  const cong = el('div', 'sx-qc-chips');
  const vung = el('div', 'sx-xbc-ds');
  const hien = () => (dl.nhom || []).map((n) => ({ ...n, bm: n.bm.filter((b) => khop(b, st.q)) }))
    .filter((n) => n.bm.length);
  const veDs = () => {
    vung.innerHTML = '';
    demChon();
    const ds = hien();
    if (!ds.length) { vung.appendChild(khungTrong('Không có biểu mẫu khớp.')); return; }
    ds.forEach((n) => {
      const g = el('div', 'sx-xbc-nhom');
      const het = n.bm.every((b) => st.chon.has(b.ma));
      const nn = el('button', `sx-xbc-nhom-ten${het ? ' sx-xbc-on' : ''}`, `${het ? '☑' : '☐'} ${esc(n.ten)}
        <span class="sx-qc-goiy">${n.bm.length}</span>`);
      nn.type = 'button';
      nn.addEventListener('click', () => {
        n.bm.forEach((b) => { if (het) st.chon.delete(b.ma); else st.chon.add(b.ma); });
        veDs();
      });
      g.appendChild(nn);
      n.bm.forEach((b) => {
        const on = st.chon.has(b.ma);
        const o = el('button', `sx-xbc-o${on ? ' sx-xbc-on' : ''}`, `<span class="sx-xbc-hop">${on ? '☑' : '☐'}</span>
          <span><b>${esc(b.ma)}</b> · ${esc(b.ten)}<span class="sx-xbc-ky">${esc(b.ky || '')}</span></span>`);
        o.type = 'button';
        o.dataset.ma = b.ma;
        o.addEventListener('click', () => {
          if (st.chon.has(b.ma)) st.chon.delete(b.ma); else st.chon.add(b.ma);
          veDs();
        });
        g.appendChild(o);
      });
      vung.appendChild(g);
    });
  };
  cong.appendChild(nut('CHỌN HẾT (đang hiện)', null, () => { hien().forEach((n) => n.bm.forEach((b) => st.chon.add(b.ma))); veDs(); }));
  cong.appendChild(nut('BỎ CHỌN', null, () => { st.chon.clear(); veDs(); }));
  box.appendChild(cong);
  box.appendChild(vung);
  tim.addEventListener('input', () => { st.q = tim.value; veDs(); });
  veDs();
  return box;
}

export function khop(b, q) {
  const k = String(q || '').trim().toLowerCase();
  return !k || `${b.ma} ${b.ten}`.toLowerCase().includes(k);
}

// ── Các lần xuất ─────────────────────────────────────────────────────────────────────────────

function veLanXuat(ctx, ds) {
  const c = ctx.container;
  c.appendChild(el('div', 'sx-qc-buoc', `<span class="sx-qc-buoc-ten">Các lần xuất</span>
    <span class="sx-qc-buoc-dem">${ds.length}</span>`));
  const vung = el('div', 'sx-qc-than');
  c.appendChild(vung);
  if (!ds.length) { vung.appendChild(khungTrong('Chưa xuất lần nào.')); return; }
  const the = {};
  ds.forEach((x) => {
    the[x.name] = el('div');
    vung.appendChild(the[x.name]);
    veThe(ctx, the[x.name], x);
  });
  hoiLai(ctx, c, the, ds);
}

/** Một lần xuất: trạng thái, kỳ, biểu mẫu, ghi chú, người xuất; nút theo trạng thái. */
export function veThe(ctx, o, x) {
  o.innerHTML = '';
  o.className = `sx-qc-sc ${x.trang_thai === 'Lỗi' ? 'sx-qc-sc-mo' : 'sx-qc-sc-dong'} sx-xbc-lan`;
  o.appendChild(el('div', 'sx-qc-sc-ten', `${esc(x.kieu)} · ${esc(ngayDu(x.tu))} – ${esc(ngayDu(x.den))}
    · ${x.so_bieu_mau || 0} biểu mẫu${x.ghi_chu ? ` · ${esc(x.ghi_chu)}` : ''}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(x.trang_thai, KIEU_TT[x.trang_thai]));
  meta.appendChild(el('span', null, `${esc(x.name)} · ${esc(x.nguoi || '')} · ${esc(gioDu(x.creation))}`));
  if (x.trang_thai === 'Xong') {
    meta.appendChild(el('span', null, `${x.so_to || 0} tờ · ${Math.max(1, Math.round((x.kich_thuoc || 0) / 1024))} KB`));
  }
  o.appendChild(meta);
  const kq = x.ket_qua || [];
  const loi = kq.filter((k) => k.loi);
  const trong = kq.filter((k) => !k.loi && !k.so_to);
  loi.forEach((k) => o.appendChild(el('div', 'sx-attp-viec sx-attp-viec-cao', `${esc(k.ma)}: không in được — ${esc(k.loi)}`)));
  if (trong.length) {
    o.appendChild(el('div', 'sx-qc-goiy', `Kỳ này không có bản ghi: ${esc(trong.map((k) => k.ma).join(', '))}`));
  }
  if (x.trang_thai === 'Lỗi' && x.loi) o.appendChild(el('div', 'sx-attp-viec sx-attp-viec-cao', esc(x.loi)));
  const hang = el('div', 'sx-qc-chips sx-tb-nut');
  if (x.trang_thai === 'Xong' && x.co_tep) {
    const a = el('a', 'sx-btn sx-btn-primary', '⬇ TẢI VỀ');
    a.href = `/api/method/${API}.tai?${new URLSearchParams({ name: x.name })}`;
    hang.appendChild(a);
  }
  if (DANG.includes(x.trang_thai)) {
    st.thay[x.name] = st.thay[x.name] || Date.now();
    hang.appendChild(el('span', 'sx-qc-goiy', x.trang_thai === 'Đang tạo' ? '⏳ Máy chủ đang dựng tệp…'
      : '⏳ Đang chờ hàng đợi máy chủ…'));
    if (x.trang_thai === 'Đang chờ' && Date.now() - st.thay[x.name] > CHO_LAU * 1000) {
      hang.appendChild(nut('CHẠY NGAY', null, async (e) => {
        e.currentTarget.disabled = true;
        try {
          const r = await ctx.call(`${API}.chay_ngay`, { name: x.name });
          veThe(ctx, o, r);
          if (r.trang_thai === 'Xong') toast(`${x.name} xong — bấm TẢI VỀ.`);
        } catch (err) { toastErr(err.message); }
      }));
    }
  }
  if (x.trang_thai === 'Lỗi') {
    hang.appendChild(nut('LÀM LẠI', null, async () => {
      try { await ctx.call(`${API}.lam_lai`, { name: x.name }); ctx.lai(); } catch (err) { toastErr(err.message); }
    }));
  }
  if (x.trang_thai !== 'Đang tạo') {
    hang.appendChild(nut('XOÁ', null, () => confirm2Step({
      title: `Xoá lần xuất ${x.name}?`,
      message: 'Xoá cả tệp đã dựng. Lần xuất là dấu vết đã đưa gì cho đoàn — chỉ xoá lần xuất thử / nhầm.',
      confirmLabel: 'XOÁ',
      onConfirm: async () => { await ctx.call(`${API}.xoa`, { name: x.name }); toast('Đã xoá'); ctx.lai(); },
    })));
  }
  o.appendChild(hang);
}

/** Hỏi lại trạng thái các lần đang chờ / đang dựng cho tới khi xong; rời màn (thẻ bị gỡ) hoặc vẽ lại là thôi. */
function hoiLai(ctx, c, the, ds) {
  st.hoi += 1;
  const luot = st.hoi;
  const dang = () => ds.filter((x) => DANG.includes(x.trang_thai)).map((x) => x.name);
  const vong = async () => {
    if (luot !== st.hoi || c.isConnected === false || !dang().length) return;
    try {
      const moi = await ctx.call(`${API}.trang_thai`, { names: JSON.stringify(dang()) });
      if (luot !== st.hoi) return;
      (moi || []).forEach((x) => {
        const i = ds.findIndex((y) => y.name === x.name);
        if (i < 0) return;
        if (DANG.includes(ds[i].trang_thai) && x.trang_thai === 'Xong') toast(`${x.name} xong — bấm TẢI VỀ.`);
        ds[i] = x;
        veThe(ctx, the[x.name], x);
      });
    } catch (e) { /* mất mạng một nhịp — hỏi lại nhịp sau */ }
    setTimeout(vong, st.nhip || HOI_LAI);
  };
  if (dang().length) setTimeout(vong, st.nhip || HOI_LAI);
}
