// Biên bản (W45, D174) — khung chung cho 18 phiếu giấy: họp Ban ISO, xem xét lãnh đạo, đánh giá nội bộ, thẩm tra,
// HACCP, gian lận / phòng vệ, thu hồi, diễn tập, giám sát dịch vụ diệt côn trùng.
//
//   #/qc/bienban            QC → Xem xét → Biên bản: "Chờ tôi ký", mẫu (+ LẬP), lọc trạng thái / mẫu, danh sách
//   #/qc/bienban/<tên>      một biên bản: các phần SINH TỪ MẪU (Văn bản: ô; Bảng / Việc giao: dòng thêm xóa được;
//                           Danh sách kiểm: câu in sẵn + nút kết luận, dòng Không phù hợp → LẬP BM.01.07; Kéo dữ liệu:
//                           bản chụp lúc lập, KÉO LẠI khi còn Nháp), LƯU / GỬI KÝ, KÝ / TRẢ LẠI theo thứ tự ô ký, tải
//                           bản ký tay, tệp kèm, IN.
//   #/tailieu/bienban[/<tên>]  cùng màn trong thư viện tài liệu — mọi vai (biên bản mình lập / phải ký).
// Luật ở sx/qc/bien_ban.py, API sx/api/qc_bienban.py. Thêm phiếu mới = khai mẫu (SX Mau Bien Ban), không sửa JS.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, oCheck, oChon3, oChu, oGio, oSo, segment, tabXemXet } from '/assets/sx/sx/components/qcui.js';

const API = 'sx.api.qc_bienban';
export const st = { tt: '', mau: '', nguoi: null };
export const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const gioDu = (s) => (s ? `${ngayDu(s)} ${String(s).slice(11, 16)}` : '');
const KIEU_TT = { 'Nháp': '', 'Chờ ký': 'oprp', 'Đã ký đủ': 'dong', 'Trả lại': 'cao' };
const KPH = ['KPH', 'Không', 'Không đạt', 'cần điều chỉnh'];
const DGNB_CON = ['BM.01.06', 'BM.01.08', 'BM.01.09'];

/** Gốc đường dẫn theo nơi đang đứng: trong QC hay trong thư viện tài liệu. */
export function goc() {
  return String(window.location.hash || '').startsWith('#/tailieu') ? '#/tailieu/bienban' : '#/qc/bienban';
}

function nut(chu, kieu, onClick) {
  const b = el('button', `sx-btn ${kieu || 'sx-btn-ghost'}`, esc(chu));
  b.type = 'button';
  if (onClick) b.addEventListener('click', onClick);
  return b;
}

/** Mount trong QC (qc.js truyền tham_so = tên biên bản). */
export async function render(api) {
  const { container } = api;
  container.innerHTML = '';
  container.appendChild(tabXemXet('bienban'));
  const than = el('div', 'sx-qc-than sx-bb');
  container.appendChild(than);
  await ve({ ...api, container: than, lai: () => render(api) }, api.tham_so);
}

/** Vẽ danh sách hoặc một biên bản vào ctx.container — dùng chung cho #/qc và #/tailieu. */
export async function ve(ctx, name) {
  try {
    if (name) await vePhieu(ctx, name);
    else await veDanhSach(ctx);
  } catch (e) {
    ctx.container.innerHTML = '';
    ctx.container.appendChild(khungTrong(e.message || 'Không mở được biên bản.'));
  }
}

// ── Danh sách ────────────────────────────────────────────────────────────────────────────────

export function theChoKy(x, href) {
  const a = el('a', 'sx-qc-sc sx-qc-sc-cho sx-bb-the');
  a.href = href;
  a.appendChild(el('div', 'sx-qc-sc-ten', `${esc(x.mau)} số ${esc(x.so)} — ${esc(x.ten_mau)}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(`Ô ${x.vai_tro}`, 'oprp'));
  meta.appendChild(el('span', null, `ngày ${esc(ngayDu(x.ngay))}${x.gui_luc ? ` · gửi ${esc(gioDu(x.gui_luc))}` : ''}`));
  a.appendChild(meta);
  return a;
}

export function veChoKy(ds, base) {
  const box = el('div', 'sx-bb-cho');
  box.appendChild(el('div', 'sx-qc-buoc', `<span class="sx-qc-buoc-ten">Chờ tôi ký</span>
    <span class="sx-qc-buoc-dem">${ds.length} biên bản</span>`));
  ds.forEach((x) => box.appendChild(theChoKy(x, `${base}/${encodeURIComponent(x.name)}`)));
  return box;
}

function dongDs(x, base) {
  const a = el('a', `sx-qc-sc sx-bb-the${x.toi_ky ? ' sx-qc-sc-cho' : ''}`);
  a.href = `${base}/${encodeURIComponent(x.name)}`;
  a.appendChild(el('div', 'sx-qc-sc-ten', `${esc(x.mau)} số ${esc(x.so)} · ${esc(ngayDu(x.ngay))}`));
  a.appendChild(el('div', 'sx-bb-td', esc(x.tieu_de || x.ten_mau)));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(x.trang_thai, KIEU_TT[x.trang_thai]));
  if (x.cho) meta.appendChild(el('span', null, `chờ ${esc(x.cho)}`));
  if (x.thieu_ky_tay) meta.appendChild(chip('chờ bản ký tay', 'oprp'));
  if (x.toi_ky) meta.appendChild(chip('tới lượt bạn ký', 'cao'));
  if (x.nguoi_lap) meta.appendChild(el('span', null, `lập: ${esc(x.nguoi_lap)}`));
  a.appendChild(meta);
  return a;
}

export async function veDanhSach(ctx) {
  const c = ctx.container;
  const dl = await ctx.call(`${API}.ds`, {});
  c.innerHTML = '';
  const base = goc();
  if (dl.cho_toi && dl.cho_toi.length) c.appendChild(veChoKy(dl.cho_toi, base));
  const lap = (dl.mau || []).filter((m) => m.lap);
  if (lap.length) {
    const box = el('div', 'sx-bb-mau');
    box.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">Lập biên bản</span>'));
    lap.forEach((m) => {
      const b = el('button', 'sx-qc-sc sx-bb-lap');
      b.type = 'button';
      b.innerHTML = `<div class="sx-qc-sc-ten">+ ${esc(m.ma)} ${esc(m.ten)}</div>
        <div class="sx-qc-sc-meta"><span>${esc(m.chu_ky_lap)}</span>${m.lan_cuoi ? `<span>gần nhất ${esc(ngayDu(m.lan_cuoi))}</span>` : ''}
        ${m.cho_ky ? `<span>${m.cho_ky} chờ ký</span>` : ''}${m.nhap ? `<span>${m.nhap} đang soạn</span>` : ''}</div>`;
      b.addEventListener('click', () => moLap(ctx, m.ma));
      box.appendChild(b);
    });
    c.appendChild(box);
  }
  c.appendChild(segment(['Tất cả', 'Nháp', 'Chờ ký', 'Đã ký đủ', 'Trả lại'], st.tt || 'Tất cả', (v) => {
    st.tt = v === 'Tất cả' ? '' : v; ve2();
  }));
  const chon = el('select', 'sx-textarea sx-bb-loc');
  chon.innerHTML = `<option value="">Mọi mẫu</option>${(dl.mau || []).map((m) => `<option value="${esc(m.ma)}">${
    esc(m.ma)} ${esc(m.ten)} (${m.so})</option>`).join('')}`;
  chon.value = st.mau || '';
  chon.addEventListener('change', () => { st.mau = chon.value; ve2(); });
  c.appendChild(chon);
  const vung = el('div', 'sx-qc-than');
  c.appendChild(vung);
  function ve2() {
    vung.innerHTML = '';
    const ds = (dl.ds || []).filter((x) => (!st.tt || x.trang_thai === st.tt) && (!st.mau || x.mau === st.mau));
    if (!ds.length) { vung.appendChild(khungTrong('Chưa có biên bản nào.')); return; }
    ds.forEach((x) => vung.appendChild(dongDs(x, base)));
  }
  ve2();
}

// ── Lập ──────────────────────────────────────────────────────────────────────────────────────

async function dsNguoi(ctx) {
  if (!st.nguoi) st.nguoi = await ctx.call(`${API}.nguoi`, {});
  return st.nguoi;
}

/** Ô nhập một cột / ô (kiểu như SX So Cot). `dat(v)` ghi giá trị. */
export function oCot(ctx, c, v, dat, khoa) {
  const m = { f: c.key, so: '', nhan: `${c.nhan}${c.bat_buoc ? ' *' : ''}` };
  const onSet = (_f, g) => dat(g);
  if (c.kieu === 'Check') return oCheck(m, v, onSet, khoa);
  if (c.kieu === 'Select') {
    if ((c.lua_chon || []).length <= 4) return oChon3(m, v, onSet, c.lua_chon || [], khoa);
    const w = el('div', 'sx-qc-oso');
    w.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc(m.nhan)}</div>`));
    const s = el('select', 'sx-textarea');
    s.innerHTML = `<option value="">— chọn —</option>${(c.lua_chon || []).map((o) => `<option>${esc(o)}</option>`).join('')}`;
    s.value = v || '';
    s.disabled = !!khoa;
    s.addEventListener('change', () => dat(s.value || null));
    w.appendChild(s);
    return w;
  }
  if (c.kieu === 'Time') return oGio(m, v, onSet, khoa);
  if (c.kieu === 'Int' || c.kieu === 'Float') return oSo({ ...m, kieu: c.kieu === 'Float' ? 'so' : 'nguyen' }, v, onSet, {}, khoa);
  if (c.kieu === 'User') {
    const w = el('div', 'sx-qc-oso');
    w.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc(m.nhan)}</div>`));
    const s = el('select', 'sx-textarea');
    s.innerHTML = `<option value="">${v ? esc(v) : '— chọn người —'}</option>`;
    s.disabled = !!khoa;
    s.addEventListener('change', () => dat(s.value || null));
    w.appendChild(s);
    dsNguoi(ctx).then((ds) => {
      s.innerHTML = `<option value="">— chọn người —</option>${ds.map((x) => `<option value="${esc(x.v)}">${esc(x.nhan)}</option>`).join('')}`;
      s.value = v || '';
    }).catch((e) => toastErr(e.message));
    return w;
  }
  if (c.kieu === 'Text' || c.kieu === 'Date' || c.kieu === 'Datetime') {
    const w = el('div', 'sx-qc-oso');
    w.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc(m.nhan)}</div>`));
    const i = el(c.kieu === 'Text' ? 'textarea' : 'input', 'sx-textarea');
    if (c.kieu === 'Text') i.rows = 2;
    else i.type = c.kieu === 'Date' ? 'date' : 'datetime-local';
    i.value = v ? String(v).slice(0, c.kieu === 'Date' ? 10 : undefined) : '';
    i.disabled = !!khoa;
    i.addEventListener(c.kieu === 'Text' ? 'input' : 'change', () => dat(i.value));
    w.appendChild(i);
    return w;
  }
  return oChu(m, v, onSet, khoa);
}

async function moLap(ctx, ma) {
  let ml;
  try { ml = await ctx.call(`${API}.mau_lap`, { ma }); } catch (e) { toastErr(e.message); return; }
  const m = openModal({ kicker: `${ma} · lập biên bản`, title: ml.ten });
  m.body.classList.add('sx-so-phieu');
  const dau = {};
  const gt = { ngay: ml.hom_nay, tieu_de: '', goc: '', chep: 0 };
  const ngay = el('input', 'sx-textarea');
  ngay.type = 'date';
  ngay.value = gt.ngay;
  ngay.max = ml.hom_nay;
  ngay.addEventListener('change', () => { gt.ngay = ngay.value; });
  const wn = el('div', 'sx-qc-oso');
  wn.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc(ml.nhan_ngay)}</div>`));
  wn.appendChild(ngay);
  m.body.appendChild(wn);
  const td = el('input', 'sx-textarea');
  td.placeholder = 'Tiêu đề (để trống = tên biên bản + ngày)';
  td.addEventListener('input', () => { gt.tieu_de = td.value; });
  m.body.appendChild(td);
  const vungBp = el('div');
  if (ml.goc_mau) {
    const w = el('div', 'sx-qc-oso');
    w.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">Lập từ ${esc(ml.goc_mau)}${ml.can_goc ? ' *' : ''}</div>`));
    const s = el('select', 'sx-textarea');
    s.innerHTML = `<option value="">${ml.can_goc ? '— chọn —' : '— không —'}</option>${(ml.goc || []).map((g) => `<option value="${
      esc(g.name)}">${esc(g.so)} · ${esc(ngayDu(g.ngay))} · ${esc(g.tieu_de)}</option>`).join('')}`;
    s.addEventListener('change', () => { gt.goc = s.value; veBp(); });
    w.appendChild(s);
    m.body.appendChild(w);
    if (!(ml.goc || []).length) {
      m.body.appendChild(el('div', 'sx-qc-goiy', ml.can_goc
        ? `Chưa có ${esc(ml.goc_mau)} ký đủ mà bạn có tên trong đó.` : `Chưa có ${esc(ml.goc_mau)} ký đủ — lập từ mẫu trắng.`));
    }
  }
  m.body.appendChild(vungBp);
  // BM.01.06: bộ phận được đánh giá chọn trong các bộ phận kế hoạch phân cho mình.
  function veBp() {
    vungBp.innerHTML = '';
    const g = (ml.goc || []).find((x) => x.name === gt.goc);
    if (!g || !g.bo_phan || ma !== 'BM.01.06') return;
    vungBp.appendChild(el('div', 'sx-qc-goiy', `Bộ phận kế hoạch phân cho bạn: ${esc(g.bo_phan.join(', ') || '—')}`));
    if (g.bo_phan.length) dau.bo_phan = dau.bo_phan || g.bo_phan[0];
    vungOdau.innerHTML = '';
    veOdau();
  }
  const vungOdau = el('div');
  m.body.appendChild(vungOdau);
  function veOdau() {
    (ml.dau || []).forEach((c) => vungOdau.appendChild(oCot(ctx, c, dau[c.key], (v) => { dau[c.key] = v; })));
  }
  veOdau();
  if (ml.chep) {
    m.body.appendChild(oCheck({ f: 'chep', so: '', nhan: `Chép bảng của lần trước (${ml.chep.so}, ${ngayDu(ml.chep.ngay)})` },
      0, (_f, v) => { gt.chep = v; }, false));
  }
  if (ml.ghi_chu) m.body.appendChild(el('div', 'sx-qc-goiy sx-bb-ghichu', esc(ml.ghi_chu)));
  const hang = el('div', 'sx-qc-chips sx-tb-nut');
  hang.appendChild(nut('LẬP', 'sx-btn-primary', async (ev) => {
    if (DGNB_CON.includes(ma) && !gt.goc) { toastErr('Chọn kế hoạch đánh giá nội bộ (BM.01.05).'); return; }
    ev.target.disabled = true;
    try {
      const r = await ctx.call(`${API}.lap`, { payload: JSON.stringify({ mau: ma, ...gt, dau }) });
      m.close();
      toast(`Đã lập ${ma} số ${r.so}`);
      window.location.hash = `${goc()}/${encodeURIComponent(r.name)}`;
    } catch (e) { ev.target.disabled = false; toastErr(e.message); }
  }));
  m.body.appendChild(hang);
}

// ── Một biên bản ─────────────────────────────────────────────────────────────────────────────

function giaTriDoc(c, v, tenNguoi) {
  if (v === null || v === undefined || v === '') return '';
  if (c.kieu === 'Check') return Number(v) ? '✓' : '';
  if (c.kieu === 'Date') return ngayDu(String(v));
  if (c.kieu === 'User') return tenNguoi[v] || v;
  if (c.kieu === 'Float') return String(v).replace('.', ',');
  return String(v);
}

function veKeo(k) {
  const box = el('div', 'sx-bb-keo');
  const ky = k.tu ? ` · kỳ ${ngayDu(k.tu)} – ${ngayDu(k.den)}` : '';
  box.appendChild(el('div', 'sx-qc-goiy', `Số liệu app lúc ${esc(gioDu(k.luc))}${esc(ky)}${k.ghi_chu ? ` — ${esc(k.ghi_chu)}` : ''}`));
  if ((k.dong || []).length && (k.cot || []).length) {
    const t = el('table', 'sx-bb-bang');
    t.appendChild(el('tr', null, k.cot.map((c) => `<th>${esc(c.nhan)}</th>`).join('')));
    k.dong.forEach((r) => t.appendChild(el('tr', null, k.cot.map((c) => `<td>${esc(r[c.key] ?? '')}</td>`).join(''))));
    const w = el('div', 'sx-bb-cuon');
    w.appendChild(t);
    box.appendChild(w);
  }
  return box;
}

function veVanBan(ctx, p, v, sua, tenNguoi) {
  const box = el('div', 'sx-bb-vb');
  const g = (v.gia_tri = v.gia_tri || {});
  p.cot.forEach((c) => {
    const tinh = (p.cot_tinh || []).includes(c.key);
    if (sua && !tinh) box.appendChild(oCot(ctx, c, g[c.key], (x) => { g[c.key] = x; }, false));
    else {
      const s = giaTriDoc(c, g[c.key], tenNguoi);
      box.appendChild(el('div', 'sx-so-o', `<b>${esc(c.nhan)}</b><span>${esc(s || (c.kieu === 'Check' ? '—' : '…'))}</span>`));
    }
  });
  return box;
}

function veDong(ctx, x, p, r, i, sua, tenNguoi, veLai) {
  const cs = p.kieu === 'Danh sách kiểm';
  const coDinh = cs && Number(r._co_dinh);
  if (Number(r._tieu_de)) return el('div', 'sx-bb-tieude', esc(p.cot.map((c) => r[c.key]).filter(Boolean).join(' — ')));
  const the = el('div', 'sx-qc-sc sx-bb-dong');
  const hoi = p.cot.filter((c) => c.hoi);
  if (cs && hoi.length && (coDinh || !sua)) {
    the.appendChild(el('div', 'sx-bb-hoi', `<span class="sx-bb-stt">${i}.</span> ${hoi.map((c) => esc(r[c.key] || '')).filter(Boolean).join(' — ')}`));
  } else the.appendChild(el('div', 'sx-bb-stt', `Dòng ${i}`));
  p.cot.forEach((c) => {
    if (cs && c.hoi && (coDinh || !sua)) return;
    const tinh = (p.cot_tinh || []).includes(c.key);
    if (sua && !tinh) {
      if (cs && c.key === p.ket_luan) {
        const w = el('div', 'sx-qc-oso');
        w.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc(c.nhan)}${c.bat_buoc ? ' *' : ''}</div>`));
        w.appendChild(segment(c.lua_chon, r[c.key] || '', (v) => { r[c.key] = v || null; veLai(); }, false, true));
        the.appendChild(w);
      } else the.appendChild(oCot(ctx, c, r[c.key], (v) => { r[c.key] = v; }, false));
    } else {
      const s = giaTriDoc(c, r[c.key], tenNguoi);
      if (s || c.key === p.ket_luan) {
        the.appendChild(el('div', `sx-so-o${c.key === 'diem' && r.diem ? ` sx-bb-muc-${r.diem >= 6 ? 'cao' : (r.diem >= 3 ? 'tb' : 'thap')}` : ''}`,
          `<b>${esc(c.nhan)}</b><span>${esc(s || '…')}</span>`));
      }
    }
  });
  if (cs && p.ket_luan && KPH.includes(r[p.ket_luan])) {
    the.classList.add('sx-bb-kph');
    const k = (x.kph || []).find((y) => y.phan === p.key && y.dong === r._id);
    const hang = el('div', 'sx-qc-chips sx-tb-nut');
    if (k && k.car) {
      const a = el('a', 'sx-btn sx-btn-ghost', `BM.01.07 ${esc(k.car)}`);
      a.href = '#/qc/khacphuc';
      hang.appendChild(a);
    } else if (x.quyen.car && !sua) {
      hang.appendChild(nut('LẬP BM.01.07', 'sx-btn-danger', async (ev) => {
        ev.target.disabled = true;
        try {
          const kq = await ctx.call(`${API}.lap_car`, { name: x.name, phan: p.key, dong: r._id });
          toast(kq.da_co ? `Dòng này đã có ${kq.name}` : `Đã lập ${kq.name}`);
          ctx.lai();
        } catch (e) { ev.target.disabled = false; toastErr(e.message); }
      }));
    } else if (sua) hang.appendChild(el('span', 'sx-qc-goiy', 'Không phù hợp — lưu, gửi ký xong thì lập BM.01.07 từ dòng này.'));
    the.appendChild(hang);
  }
  if (sua && (!cs || !coDinh)) {
    const hang = el('div', 'sx-qc-chips');
    hang.appendChild(nut('Xóa dòng', 'sx-btn-ghost', () => {
      const ds = (x.noi_dung[p.key] || {}).dong || [];
      ds.splice(ds.indexOf(r), 1);
      veLai();
    }));
    the.appendChild(hang);
  }
  return the;
}

function vePhan(ctx, x, p, sua, tenNguoi) {
  const khung = el('div', 'sx-bb-phan');
  if (p.tieu_de) khung.appendChild(el('div', 'sx-qc-buoc', `<span class="sx-qc-buoc-ten">${esc(p.tieu_de)}</span>`));
  const v = (x.noi_dung[p.key] = x.noi_dung[p.key] || {});
  const than = el('div');
  khung.appendChild(than);
  const veLai = () => {
    than.innerHTML = '';
    if (p.kieu === 'Kéo dữ liệu') {
      if (v.keo) than.appendChild(veKeo(v.keo));
      else than.appendChild(el('div', 'sx-qc-goiy', 'Chưa kéo dữ liệu.'));
    } else if (p.kieu === 'Văn bản') {
      if (p.cot.length) than.appendChild(veVanBan(ctx, p, v, sua, tenNguoi));
      else if (sua) {
        const t = el('textarea', 'sx-textarea');
        t.rows = 4;
        t.value = v.chu || '';
        t.addEventListener('input', () => { v.chu = t.value; });
        than.appendChild(t);
      } else than.appendChild(el('div', 'sx-bb-chu', esc(v.chu || '…')));
    } else {
      if (v.keo) than.appendChild(el('div', 'sx-qc-goiy', `Dòng lấy từ app lúc ${esc(gioDu(v.keo.luc))}${v.keo.ghi_chu ? ` — ${esc(v.keo.ghi_chu)}` : ''}`));
      const ds = (v.dong = v.dong || []);
      const apDung = (x.dong_ap_dung || {})[p.key];
      let i = 0;
      ds.forEach((r) => {
        if (p.kieu === 'Danh sách kiểm' && apDung && r._id && !Number(r._tieu_de) && !apDung.includes(r._id)) return;
        if (!Number(r._tieu_de)) i += 1;
        than.appendChild(veDong(ctx, x, p, r, i, sua, tenNguoi, veLai));
      });
      if (!ds.length) than.appendChild(el('div', 'sx-qc-goiy', 'Chưa có dòng nào.'));
      if (sua && (p.kieu !== 'Danh sách kiểm' || p.them_dong)) {
        than.appendChild(nut(p.kieu === 'Danh sách kiểm' ? '+ CÂU HỎI' : '+ DÒNG', 'sx-btn-ghost', () => {
          ds.push({}); veLai();
        }));
      }
    }
    if (sua && p.nguon) {
      than.appendChild(nut('↻ KÉO LẠI', 'sx-btn-ghost', async (ev) => {
        ev.target.disabled = true;
        try {
          await ctx.call(`${API}.luu`, { name: x.name, payload: JSON.stringify({ noi_dung: x.noi_dung }) });
          await ctx.call(`${API}.keo_lai`, { name: x.name, phan: p.key });
          toast('Đã kéo lại dữ liệu'); ctx.lai();
        } catch (e) { ev.target.disabled = false; toastErr(e.message); }
      }));
    }
  };
  veLai();
  return khung;
}

function veKy(x) {
  const box = el('div', 'sx-bb-kyds');
  box.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">Ký</span>'));
  x.ky.forEach((s) => {
    let tt;
    if (s.ky_tay) tt = x.co_ky_tay ? 'Ký tay — đã có bản scan' : 'Ký tay — in, ký, tải bản scan';
    else if (s.ky_luc) tt = `Ký trên phần mềm: ${s.ten}, ${gioDu(s.ky_luc)}${s.chuc_danh ? ` (${s.chuc_danh})` : ''}`;
    else tt = s.cho ? 'đang chờ ký' : (s.gan && s.ten ? `chờ ${s.ten}` : 'chưa ký');
    const d = el('div', `sx-dg-ky${s.cho ? ' sx-bb-ky-cho' : ''}`, `<b>${esc(s.vai_tro)}</b><span>${esc(tt)}</span>`);
    if (s.y_kien) d.appendChild(el('span', null, `Ý kiến: ${esc(s.y_kien)}`));
    box.appendChild(d);
  });
  if (x.can_ky_tay && !x.ky.some((s) => s.ky_tay)) {
    box.appendChild(el('div', 'sx-dg-ky', `<b>Bên ngoài tham gia</b><span>${x.co_ky_tay ? 'Ký tay — đã có bản scan' : 'Ký tay — in, ký, tải bản scan'}</span>`));
  }
  return box;
}

function docTep(f) {
  return new Promise((ok, loi) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(',')[1]);
    r.onerror = () => loi(new Error(`Không đọc được tệp ${f.name}`));
    r.readAsDataURL(f);
  });
}

function nutTep(chu, onFile) {
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
    try { await onFile(f, await docTep(f)); } catch (e) { toastErr(e.message); }
    b.disabled = false;
  });
  b.addEventListener('click', () => inp.click());
  w.appendChild(b);
  w.appendChild(inp);
  return w;
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

function hoiYKien(tieuDe, batBuoc, onOk) {
  const m = openModal({ kicker: 'Biên bản', title: tieuDe });
  const t = el('textarea', 'sx-textarea');
  t.rows = 3;
  t.placeholder = batBuoc ? 'Ý kiến (bắt buộc)' : 'Ý kiến (nếu có)';
  m.body.appendChild(t);
  const h = el('div', 'sx-qc-chips sx-tb-nut');
  h.appendChild(nut('XÁC NHẬN', 'sx-btn-primary', async (ev) => {
    if (batBuoc && !t.value.trim()) { toastErr('Ghi ý kiến.'); return; }
    ev.target.disabled = true;
    try { await onOk(t.value.trim()); m.close(); } catch (e) { ev.target.disabled = false; toastErr(e.message); }
  }));
  m.body.appendChild(h);
}

export async function vePhieu(ctx, name) {
  const c = ctx.container;
  const x = await ctx.call(`${API}.xem`, { name });
  c.innerHTML = '';
  const q = x.quyen;
  const sua = !!q.sua;
  const tenNguoi = {};
  if (sua || x.phan.some((p) => p.cot.some((k) => k.kieu === 'User'))) {
    try { (await dsNguoi(ctx)).forEach((u) => { tenNguoi[u.v] = u.nhan; }); } catch (e) { /* chỉ để hiện tên */ }
  }
  const lai = () => ve({ ...ctx, lai: () => ve(ctx, name) }, name);
  const ctx2 = { ...ctx, lai };
  const ve_ = el('a', 'sx-qc-goiy', '← Danh sách biên bản');
  ve_.href = goc();
  c.appendChild(ve_);
  const dau = el('div', 'sx-qc-sc sx-bb-dau');
  dau.appendChild(el('div', 'sx-qc-sc-ten', `${esc(x.mau)} số ${esc(x.so)} — ${esc(x.ten_mau)}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(x.trang_thai, KIEU_TT[x.trang_thai]));
  meta.appendChild(el('span', null, `lập: ${esc(x.ten_nguoi_lap)}`));
  if (x.goc) {
    const a = el('a', null, `từ ${esc(x.goc.mau)} số ${esc(x.goc.so)}`);
    a.href = `${goc()}/${encodeURIComponent(x.goc.name)}`;
    meta.appendChild(a);
  }
  dau.appendChild(meta);
  const gt = { ngay: x.ngay, tieu_de: x.tieu_de };
  if (sua) {
    const wn = el('div', 'sx-qc-oso');
    wn.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc(x.nhan_ngay)}</div>`));
    const i = el('input', 'sx-textarea');
    i.type = 'date';
    i.value = x.ngay;
    i.max = x.hom_nay;
    i.addEventListener('change', () => { gt.ngay = i.value; });
    wn.appendChild(i);
    dau.appendChild(wn);
    const t = el('input', 'sx-textarea');
    t.value = x.tieu_de;
    t.addEventListener('input', () => { gt.tieu_de = t.value; });
    dau.appendChild(t);
  } else {
    dau.appendChild(el('div', 'sx-so-o', `<b>${esc(x.nhan_ngay)}</b><span>${esc(ngayDu(x.ngay))}</span>`));
    dau.appendChild(el('div', 'sx-bb-td', esc(x.tieu_de)));
  }
  c.appendChild(dau);
  if (x.y_kien_tra_lai) c.appendChild(el('div', 'sx-qc-sc sx-bb-tralai', `<b>Ý kiến trả lại</b><div class="sx-bb-chu">${esc(x.y_kien_tra_lai)}</div>`));
  x.phan.forEach((p) => {
    if (x.ap_dung && x.ap_dung[p.key] === false) return;
    c.appendChild(vePhan(ctx2, x, p, sua, tenNguoi));
  });
  if (x.chep_cau_hoi) {
    c.appendChild(nut('CHÉP CÂU HỎI TỪ ĐỢT TRƯỚC', 'sx-btn-ghost', async (ev) => {
      ev.target.disabled = true;
      try {
        await ctx.call(`${API}.luu`, { name: x.name, payload: JSON.stringify({ noi_dung: x.noi_dung }) });
        const r = await ctx.call(`${API}.chep_cau_hoi`, { name: x.name });
        toast(`Đã chép ${r.da_chep} câu hỏi`); lai();
      } catch (e) { ev.target.disabled = false; toastErr(e.message); }
    }));
  }
  c.appendChild(veKy(x));
  if ((x.viec || []).length) {
    const box = el('div', 'sx-bb-viec');
    box.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">Việc giao (đã vào việc định kỳ)</span>'));
    x.viec.forEach((v) => box.appendChild(el('div', 'sx-so-o', `<b>${esc(v.noi_dung)}</b><span>${esc(v.nguoi)} · hạn ${esc(ngayDu(v.han))}</span>`)));
    const a = el('a', 'sx-btn sx-btn-ghost', 'Mở lịch việc định kỳ');
    a.href = '#/qc/lichviec';
    box.appendChild(a);
    c.appendChild(box);
  }
  if ((x.lien_quan || []).length) {
    c.appendChild(el('div', 'sx-qc-goiy', `Phiếu liên quan: ${x.lien_quan.map((r) => esc(r.ten)).join(', ')}`));
  }
  if ((x.tep_kem || []).length) {
    const box = el('div', 'sx-bb-tep');
    x.tep_kem.forEach((t) => {
      const a = el('a', 'sx-btn sx-btn-ghost', `📎 ${esc(t.mo_ta)}`);
      a.href = `/api/method/${API}.tai_tep?name=${encodeURIComponent(x.name)}&i=${t.i}`;
      a.target = '_blank';
      a.rel = 'noopener';
      box.appendChild(a);
    });
    c.appendChild(box);
  }
  const hang = el('div', 'sx-qc-chips sx-tb-nut sx-bb-nut');
  const luu = async () => ctx.call(`${API}.luu`, { name: x.name, payload: JSON.stringify({ ...gt, noi_dung: x.noi_dung }) });
  if (sua) {
    hang.appendChild(nut('LƯU', 'sx-btn-ghost', async (ev) => {
      ev.target.disabled = true;
      try { await luu(); toast('Đã lưu'); lai(); } catch (e) { ev.target.disabled = false; toastErr(e.message); }
    }));
    hang.appendChild(nut('GỬI KÝ', 'sx-btn-primary', async (ev) => {
      ev.target.disabled = true;
      try { await luu(); await ctx.call(`${API}.gui`, { name: x.name }); toast('Đã gửi ký'); lai(); } catch (e) {
        ev.target.disabled = false; toastErr(e.message);
      }
    }));
  }
  if (q.ky) {
    hang.appendChild(nut('KÝ', 'sx-btn-primary', () => hoiYKien('Ký biên bản', false, async (yk) => {
      await ctx.call(`${API}.ky`, { name: x.name, y_kien: yk }); toast('Đã ký'); lai();
    })));
    hang.appendChild(nut('TRẢ LẠI', 'sx-btn-ghost', () => hoiYKien('Trả lại người lập', true, async (yk) => {
      await ctx.call(`${API}.tra_lai`, { name: x.name, y_kien: yk }); toast('Đã trả lại'); lai();
    })));
  }
  if (q.ky_tay) {
    hang.appendChild(nutTep('TẢI BẢN KÝ TAY', async (f, nd) => {
      await ctx.call(`${API}.tai_ky_tay`, { name: x.name, ten: f.name, noi_dung: nd }); toast('Đã tải bản ký tay'); lai();
    }));
  }
  if (x.co_ky_tay) {
    const a = el('a', 'sx-btn sx-btn-ghost', '📄 BẢN KÝ TAY');
    a.href = `/api/method/${API}.tai_tep?name=${encodeURIComponent(x.name)}&ky_tay=1`;
    a.target = '_blank';
    a.rel = 'noopener';
    hang.appendChild(a);
  }
  if (x.trang_thai !== 'Đã ký đủ' && (sua || (x.trang_thai === 'Chờ ký' && x.user === x.nguoi_lap))) {
    hang.appendChild(nutTep('+ TỆP KÈM', async (f, nd) => {
      await ctx.call(`${API}.them_tep`, { name: x.name, ten: f.name, noi_dung: nd, mo_ta: f.name }); toast('Đã thêm tệp'); lai();
    }));
  }
  hang.appendChild(nut('🖨 IN', 'sx-btn-ghost', async () => {
    try { inHtml(await ctx.call(`${API}.in_bb`, { name: x.name }), `${x.mau} số ${x.so}`); } catch (e) { toastErr(e.message); }
  }));
  if (q.xoa) {
    hang.appendChild(nut('XÓA', 'sx-btn-ghost', () => confirm2Step({
      title: `Xóa ${x.mau} số ${x.so}?`, message: 'Biên bản chưa ai ký — xóa hẳn.', confirmLabel: 'XÓA',
      onConfirm: async () => { await ctx.call(`${API}.xoa`, { name: x.name }); toast('Đã xóa'); window.location.hash = goc(); },
    })));
  }
  c.appendChild(hang);
}
