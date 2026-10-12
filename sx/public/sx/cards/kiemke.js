// Card "Kiểm kê kho" — đếm / cân hàng trong kho rồi chốt.
//
// THÀNH PHẨM (D154): lô thành phẩm vào kho từ trước khi lô mang HSD — truy xuất theo HSD in trên hộp không ra,
// xuất FEFO và báo cận date bỏ sót. Thủ kho đi từng mã, đếm theo HSD in trên hộp (cùng bàn số thùng / hộp + HSD
// với Nhập kho), xem trước rồi CHỐT. D188: chốt = ĐẶT LẠI TOÀN KHO theo số đếm — mỗi loại, mỗi HSD một lô; mã có
// tồn mà không đếm về 0; lô cũ chuyển sang lô theo HSD, thừa / thiếu ghi điều chỉnh kho. D189: mã chưa quản lý lô
// (hoặc có tồn không gắn lô) đếm theo HSD như mã khác — chốt bật lô cho mã, tồn cũ không lô về 0. D191: cờ lô là của
// mã, áp mọi kho — tồn ở kho khác (cửa hàng, xưởng) chốt xử lý luôn: kho dương vào lô tồn cũ tại chỗ, kho âm về 0.
// D193: nút "Tồn âm thành phẩm ở Kho Xưởng sản xuất" — xem từng dòng âm (do chuyển sang Kho TP mà không ghi sản xuất
// vào xưởng), quản lý bấm DỌN để nhập điều chỉnh về 0, in danh sách cho kế toán.
// D195: "Chốt sổ tại" — thủ kho / quản lý đặt thời điểm chốt sổ: số sổ sách tính tới lúc đó (số đếm giữ nguyên), chốt
// ghi chứng từ kho lùi về lúc đó (mã bật lô: chênh lệch ghi lùi, chuyển vào lô lúc bấm). Để trống = lúc bấm chốt.
// BÁN THÀNH PHẨM (D155): Kho BTP / Kho xưởng — hàng rời tính kg, lô theo ngày làm / lô rang, không có HSD: CÂN
// TỪNG LÔ. Lô đã cân thì số cân thay số sổ của lô đó; lô chưa cân giữ nguyên.
// Thủ kho chốt luôn (D155). Mỗi lần LƯU là ghi thẳng vào phiếu trên server: tải lại trang, đổi máy vẫn còn số.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';
import { moTaUom } from '/assets/sx/sx/components/soluong.js';
import { moQuet } from '/assets/sx/sx/components/quet.js';
import { moSoHsd, veNgayDu } from '/assets/sx/sx/cards/nhapkhotp.js';

const BTP = 'Bán thành phẩm';
const NHO_KHO = 'sx-kk-kho';            // kho đang kiểm của máy này — mở lại thẻ vào đúng kho đó

// Mặc định xem TẤT CẢ, thứ tự cố định (server xếp): lưu một dòng xong mã vẫn đứng nguyên chỗ, nút "+ HSD"
// ngay đó cho HSD tiếp theo — lọc "Chưa đếm" mà mã biến mất sau dòng đầu là bắt người ta đi tìm lại.
const st = { loc: 'het', tim: '' };     // giữ bộ lọc qua các lần vẽ lại

// [khoá, [nhãn thành phẩm, nhãn bán thành phẩm], lọc]. Bán thành phẩm: "chưa cân" = còn lô trên sổ chưa cân.
const LOC = [
  ['chua', ['Chưa đếm', 'Chưa cân'], (x) => (x.lo ? x.con_chua > 0 : !x.da_dem)],
  ['dem', ['Đã đếm', 'Đã cân'], (x) => x.da_dem],
  ['lech', ['Lệch', 'Lệch'], (x) => x.da_dem && Math.abs(lechCua(x)) > 1e-9],
  ['het', ['Tất cả', 'Tất cả'], () => true],
];

function lechCua(x) { return x.lech != null ? x.lech : x.tong_dem - x.so_sach; }

// Mã lô chép tay: bỏ khoảng trắng, in hoa — như server (sx.api.kiemke.ghi_lo_moi).
const chuanMa = (s) => String(s || '').replace(/\s+/g, '').toUpperCase();
const MA_HOP_LE = /^[A-Z0-9][A-Z0-9._/-]{0,39}$/;

/** Ngày làm đọc từ mã lô: nhóm 6 số ddmmyy CUỐI cùng (R-280926, R-280926-U, BBS-KK071026-2) → 'YYYY-MM-DD'.
 *  Không ra ngày thật thì ''. Hàm thuần. */
export function ngayTuMa(ma) {
  const ds = [...String(ma || '').matchAll(/(?:^|\D)(\d{2})(\d{2})(\d{2})(?=\D|$)/g)];
  if (!ds.length) return '';
  const [, d, m, y] = ds[ds.length - 1];
  const iso = `20${y}-${m}-${d}`;
  const t = new Date(`${iso}T00:00:00Z`);
  return !Number.isNaN(t.getTime()) && t.toISOString().slice(0, 10) === iso ? iso : '';
}
const kg = (n) => formatNumber(n, 3);
/** 'YYYY-MM-DD HH:MM[:SS]' → 'dd/mm/yy HH:MM'. */
const veLuc = (s) => `${veNgayDu(String(s).slice(0, 10))} ${String(s).slice(11, 16)}`;
const coDau = (n, le = 0) => `${n > 0 ? '+' : ''}${formatNumber(n, le)}`;

function khoDaNho() {
  try { return JSON.parse(localStorage.getItem(NHO_KHO) || 'null'); } catch (e) { return null; }
}
function nhoKho(k) {
  try { localStorage.setItem(NHO_KHO, JSON.stringify({ kho: k.kho, loai: k.loai })); } catch (e) { /* chặn bộ nhớ: thôi */ }
}

export async function render({ container, call, boot }) {
  container.className = 'sx-card sx-kk';
  container.innerHTML = '<div class="sx-muted">Đang tải kiểm kê…</div>';
  const tai = (k) => call('sx.api.kiemke.tong_quan', k && k.kho ? { kho: k.kho, loai: k.loai } : {});
  let dl;
  try {
    const nho = khoDaNho();
    // Kho đã nhớ không còn (đổi cấu hình kho) thì về kho mặc định.
    dl = await tai(nho).catch((e) => (nho ? tai(null) : Promise.reject(e)));
  } catch (e) {
    container.innerHTML = `<div class="sx-field-label">Kiểm kê kho</div>
      <div class="sx-muted">Chưa dùng được: ${esc(e.message)}</div>`;
    return;
  }
  const $ = (q) => container.querySelector(q);
  const laBtp = () => dl.loai === BTP;
  const so = (n) => (laBtp() ? kg(n) : formatNumber(n));
  const le = () => (laBtp() ? 3 : 0);
  const dem = () => (laBtp() ? 'cân' : 'đếm');
  const khoNay = () => ({ kho: dl.kho, loai: dl.loai || 'Thành phẩm' });

  // Gọi API (trả lại toàn bộ trạng thái thẻ) rồi vẽ lại. true = xong.
  async function lam(viec, nut) {
    if (nut) nut.disabled = true;
    try {
      dl = await viec();
      ve();
      return true;
    } catch (e) {
      if (nut) nut.disabled = false;
      toastErr(e.message);
      return false;
    }
  }

  function ve() {
    if (dl.phieu) veDangDem(dl.phieu);
    else veChuaMo();
  }

  function tieuDe() {
    const k = (dl.cac_kho || []).find((x) => x.kho === dl.kho && x.loai === dl.loai);
    if (!laBtp()) return 'Kiểm kê kho thành phẩm';
    return k && k.nhan === 'Kho xưởng' ? 'Kiểm kê kho xưởng (bán thành phẩm)' : 'Kiểm kê kho bán thành phẩm';
  }

  // Chọn kho: thành phẩm đếm theo HSD, bán thành phẩm / kho xưởng cân theo lô. Mỗi kho một phiếu riêng.
  function veKho() {
    const ds = dl.cac_kho || [];
    if (ds.length < 2) return '';
    return `<div class="sx-kk-loc sx-kk-kho" role="tablist" aria-label="Kho kiểm kê">${ds.map((k, i) => {
      const on = k.kho === dl.kho && k.loai === dl.loai;
      return `<button type="button" role="tab" class="sx-np-chip${on ? ' sx-np-chip-on' : ''}" data-kho="${i}"
        aria-selected="${on}">${esc(k.nhan)}</button>`;
    }).join('')}</div>`;
  }

  function ganKho() {
    container.querySelectorAll('[data-kho]').forEach((b) => b.addEventListener('click', () => {
      const k = dl.cac_kho[Number(b.dataset.kho)];
      if (k.kho === dl.kho && k.loai === dl.loai) return;
      st.loc = 'het';
      st.tim = '';
      lam(() => tai(k), b).then((xong) => { if (xong) nhoKho(k); });
    }));
  }

  const veCanhBao = () => (dl.canh_bao || []).map((c) => `<div class="sx-kk-nhac">⚠ ${esc(c)}</div>`).join('');

  // ─────────────────────────── chưa có phiếu đang đếm ───────────────────────────
  function veChuaMo() {
    let tom;
    if (laBtp()) {
      const soLo = dl.hang.reduce((a, x) => a + x.lo.filter((l) => !l.thu_hoi).length, 0);
      tom = `<div class="sx-muted">${dl.hang.length} mã · ${soLo} lô trên sổ ${esc(dl.kho)}.</div>`;
    } else {
      const co = dl.hang.filter((x) => x.so_sach > 0);
      const chua = co.filter((x) => x.chua_hsd > 0);
      tom = chua.length ? `<div class="sx-kk-bao">${chua.length} mã còn hàng chưa ghi HSD · ${formatNumber(
        chua.reduce((a, x) => a + x.chua_hsd, 0))} sp</div>`
        : `<div class="sx-muted">${co.length} mã đang có hàng trong ${esc(dl.kho)} — lô nào cũng đã có HSD.</div>`;
    }
    container.innerHTML = `
      ${veKho()}
      <div class="sx-field-label">${tieuDe()}</div>
      <div class="sx-muted">${laBtp()
    ? 'Cân từng lô (kg) rồi chốt: lô đã cân thì số cân thay số sổ của lô đó, lô chưa cân giữ nguyên; thừa / thiếu ghi điều chỉnh kho.'
    : `Đếm số thùng / hộp từng loại theo HSD in trên hộp rồi chốt. Chốt = <b>đặt lại toàn bộ kho thành phẩm</b>
        theo số đếm: mỗi loại, mỗi HSD một lô; mã không đếm về 0; thừa / thiếu ghi điều chỉnh kho.`}</div>
      ${tom}
      ${veCanhBao()}
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="kk-bat">BẮT ĐẦU KIỂM KÊ</button>
      ${veGanDay()}
      ${veNutAm()}`;
    $('#kk-bat').addEventListener('click', (e) => lam(() => call('sx.api.kiemke.bat_dau', khoNay()), e.currentTarget));
    ganKho();
    ganGanDay();
  }

  function veGanDay() {
    if (!dl.gan_day.length) return '';
    return `<div class="sx-field-label">Kiểm kê đã chốt — bấm để in biên bản</div>
      <div class="sx-vh-list">${dl.gan_day.map((g) => `
        <div class="sx-vh-row" data-bb="${esc(g.name)}" role="button" tabindex="0" style="cursor:pointer">
          <div class="sx-vh-who"><div class="sx-vh-name">${esc(g.name)} · ${esc(veNgayDu(g.ngay))}${
  g.trang_thai === 'Đã huỷ' ? ' <span class="sx-badge sx-badge-err">Đã huỷ</span>' : ''}</div>
            <div class="sx-vh-meta">${g.so_ma} mã · sổ ${so(g.tong_so_sach)} → ${dem()} ${
  so(g.tong_dem)}${laBtp() ? ' kg' : ''}</div></div>
          <span class="sx-nv-qty">${coDau(g.tong_lech, le())}</span></div>`).join('')}</div>`;
  }

  function ganGanDay() {
    container.querySelectorAll('[data-bb]').forEach((b) => b.addEventListener('click', () => inBienBan(b.dataset.bb)));
    const am = $('#kk-am');
    if (am) am.addEventListener('click', (e) => moDonAm(e.currentTarget));
  }

  // D193: chỉ thành phẩm — tồn âm ở Kho Xưởng sản xuất (không phải kho đang kiểm kê).
  const veNutAm = () => (laBtp() ? '' : `<button type="button" class="sx-btn sx-btn-ghost" id="kk-am">
    Tồn âm thành phẩm ở Kho Xưởng sản xuất</button>`);

  // D195: thời điểm chốt sổ — không đụng số đã đếm, chỉ tính lại số sổ sách tới lúc đó.
  function moThoiDiem(p) {
    const m = openModal({ kicker: `Kiểm kê · ${p.name}`, title: 'Thời điểm chốt sổ' });
    const goc = String(p.thoi_diem || p.bat_dau_luc || '').replace(' ', 'T').slice(0, 16);
    m.body.innerHTML = `
      <div class="sx-muted">Số sổ sách tính tới thời điểm này; chốt ghi chứng từ kho <b>lùi về</b> thời điểm này. Số đã
        ${dem()} giữ nguyên. Nên đặt đúng lúc ${dem()} (kho đứng yên); để trống = lúc bấm chốt.</div>
      <input class="sx-textarea" type="datetime-local" id="kk-td-o" value="${esc(goc)}" max="${esc(dl.bay_gio || '')}">`;
    const luu = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU THỜI ĐIỂM');
    luu.type = 'button';
    luu.addEventListener('click', () => {
      const v = (m.body.querySelector('#kk-td-o').value || '').trim();
      if (!v) { toastErr('Chọn ngày giờ chốt sổ.'); return; }
      lam(() => call('sx.api.kiemke.dat_thoi_diem', { name: p.name, thoi_diem: v.replace('T', ' ') }), luu)
        .then((xong) => { if (xong) { m.close(); toast(`Chốt sổ tại ${veLuc(v.replace('T', ' '))} — số sổ sách đã tính lại.`); } });
    });
    m.body.appendChild(luu);
    if (p.thoi_diem) {
      const bo = el('button', 'sx-btn sx-btn-ghost sx-btn-big', 'BỎ — CHỐT THEO LÚC BẤM');
      bo.type = 'button';
      bo.addEventListener('click', () => lam(() => call('sx.api.kiemke.dat_thoi_diem', { name: p.name }), bo)
        .then((xong) => { if (xong) { m.close(); toast('Bỏ thời điểm chốt sổ — chốt theo lúc bấm.'); } }));
      m.body.appendChild(bo);
    }
  }

  async function moDonAm(nut) {
    if (nut) nut.disabled = true;
    let x;
    try { x = await call('sx.api.tonam.ds_am'); } catch (e) { toastErr(e.message); return; } finally {
      if (nut) nut.disabled = false;
    }
    const t = x.tong;
    const m = openModal({ kicker: 'Dọn tồn âm thành phẩm', title: x.kho || 'Kho Xưởng sản xuất' });
    const dong = x.dong.map((r) => `
        <div class="sx-vh-row" style="cursor:default"><div class="sx-vh-who">
          <div class="sx-vh-name">${esc(r.ten)}</div>
          <div class="sx-vh-meta">${esc([r.batch ? `lô ${r.batch}${r.hsd ? ` · HSD ${veNgayDu(r.hsd)}` : ''}` : 'không lô',
    `giá vốn ${r.gia ? formatNumber(r.gia) : '0'}`, `giá trị ${formatNumber(r.gia_tri)} đ`].join(' · '))}</div></div>
          <span class="sx-nv-qty">${formatNumber(r.so)} → 0</span></div>`).join('');
    m.body.innerHTML = `
      ${x.loi ? `<div class="sx-error-box">${esc(x.loi)}</div>` : ''}
      <div class="sx-muted">Số âm không có thật — thành phẩm từng chuyển từ kho này sang Kho TP (phiếu chuyển kho) mà không
        ghi sản xuất vào. <b>DỌN</b> = nhập điều chỉnh từng dòng âm về 0 theo giá vốn của kho (bút toán điều chỉnh kho —
        báo kế toán). Chỉ kho này; phần dương giữ nguyên.</div>
      ${x.dong.length ? `<div class="sx-kk-tien">${t.so_ma} mã · ${t.so_dong} dòng · +${formatNumber(t.so_luong)} · giá trị ${
  formatNumber(t.gia_tri)} đ</div>
      <div class="sx-vh-list">${dong}</div>` : (x.loi ? '' : '<div class="sx-muted">Không còn tồn âm thành phẩm ở kho này.</div>')}
      ${x.lan_truoc.length ? `<div class="sx-field-label">Đã dọn — bấm để in danh sách</div>
      <div class="sx-vh-list">${x.lan_truoc.map((g, i) => `
        <div class="sx-vh-row" data-inam="${i}" role="button" tabindex="0" style="cursor:pointer">
          <div class="sx-vh-who"><div class="sx-vh-name">${esc(g.lan)} · ${esc(veNgayDu(g.ngay))}</div>
            <div class="sx-vh-meta">${esc(g.phieu.join(', '))}</div></div><span class="sx-nv-qty">🖨</span></div>`).join('')}</div>` : ''}`;
    m.body.querySelectorAll('[data-inam]').forEach((b) => b.addEventListener('click', () => inDonAm(
      x.lan_truoc[Number(b.dataset.inam)].phieu)));
    if (x.dong.length && x.duoc_don) {
      const b = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'DỌN TỒN ÂM');
      b.type = 'button';
      b.addEventListener('click', () => confirm2Step({
        title: `Dọn tồn âm ở ${x.kho}`,
        message: `Nhập điều chỉnh ${t.so_dong} dòng âm (${t.so_ma} mã, +${formatNumber(t.so_luong)}) về 0 ở ${x.kho}, tổng giá trị ${
          formatNumber(t.gia_tri)} đ — bút toán điều chỉnh kho, báo kế toán. Chỉ kho này. Muốn huỷ thì huỷ các phiếu nhập `
          + 'trên Desk.',
        confirmLabel: 'DỌN',
        onConfirm: async () => {
          try {
            const kq = await call('sx.api.tonam.don_am');
            m.close();
            toast(`Đã dọn ${kq.so_dong} dòng âm ở ${kq.kho}: ${kq.phieu.join(', ')}.`);
            inDonAm(kq.phieu);
          } catch (e) { toastErr(e.message); throw e; }
        },
      }));
      m.body.appendChild(b);
    } else if (x.dong.length) {
      m.body.appendChild(el('div', 'sx-muted', 'Chỉ quản lý dọn được (bút toán điều chỉnh kho).'));
    }
  }

  async function inDonAm(phieu) {
    try {
      inHtml('Dọn tồn âm thành phẩm', await call('sx.api.tonam.bien_ban', { phieu: JSON.stringify(phieu) }));
    } catch (e) { toastErr(e.message); }
  }

  // ─────────────────────────── đang đếm ───────────────────────────
  function veDangDem(p) {
    const hang = dl.hang;
    const daDem = hang.filter((x) => x.da_dem);
    const lech = daDem.reduce((a, x) => a + lechCua(x), 0);
    const fn = (LOC.find((l) => l[0] === st.loc) || LOC[3])[2];
    const q = st.tim.toLowerCase().trim();
    const ds = hang.map((x, i) => [x, i]).filter(([x]) => fn(x)
      && (!q || x.ten.toLowerCase().includes(q) || x.item.toLowerCase().includes(q)
        || (x.lo || []).some((l) => String(l.batch || '').toLowerCase().includes(q))));
    let tien;
    if (laBtp()) {
      const lo = hang.flatMap((x) => x.lo.filter((l) => !l.thu_hoi));
      tien = `Đã cân ${lo.filter((l) => l.can != null).length}/${lo.length} lô`;
    } else {
      tien = `Đã đếm ${daDem.length}/${hang.length} mã`;
    }
    let nhom = null;
    const khoi = ds.map(([x, i]) => {
      let dau = '';
      if (laBtp() && x.nhom !== nhom) {
        nhom = x.nhom;
        dau = `<div class="sx-kk-nhom">${esc(nhom || 'Khác')}</div>`;
      }
      return dau + (laBtp() ? veMaBtp(x, i) : veMa(x, i));
    }).join('');
    container.innerHTML = `
      ${veKho()}
      <div class="sx-field-label">Kiểm kê ${esc(p.name)} · bắt đầu ${esc(veNgayDu(p.bat_dau_luc))} ${
  esc(String(p.bat_dau_luc).slice(11, 16))} · ${esc(dl.kho)}</div>
      <div class="sx-kk-moc">Chốt sổ tại: <b>${p.thoi_diem ? esc(veLuc(p.thoi_diem)) : 'lúc bấm chốt'}</b>${
  dl.duoc_chot ? ' <button type="button" class="sx-np-chip" id="kk-td">✎ Đổi</button>' : ''}</div>
      <div class="sx-kk-tien">${tien}${daDem.length ? ` · lệch <span class="${Math.abs(lech) > 1e-9 ? 'sx-kk-lech'
    : 'sx-kk-khop'}">${coDau(lech, le())}${laBtp() ? ' kg' : ''}</span>` : ''}</div>
      <div class="sx-kk-nhac">${laBtp()
    ? 'Đang kiểm kê: lô đã cân thì đừng xuất / nhập lô đó. Có chứng từ kho của lô sau lúc cân thì phải cân lại lô đó mới chốt được.'
    : 'Đang kiểm kê: đừng bán / nhập / xuất thành phẩm. Chốt sẽ đặt lại toàn kho theo số đếm — mã có tồn mà không đếm về 0.'}${
  p.thoi_diem ? ` Số sổ sách tính tới ${esc(veLuc(p.thoi_diem))}; chốt ghi chứng từ kho lùi về lúc đó. Có chứng từ kho giữa lúc ${
    dem()} và lúc đó thì ${dem()} lại; chứng từ sau lúc đó không được rút từ lô mà chốt giảm.`
    : ` Có chứng từ kho sau lúc ${dem()} thì phải ${dem()} lại mới chốt được.`}</div>
      ${veCanhBao()}
      <div class="sx-kk-loc" role="tablist">${LOC.map(([k, ten, f]) => `<button type="button" role="tab"
        class="sx-np-chip${st.loc === k ? ' sx-np-chip-on' : ''}" data-loc="${k}" aria-selected="${st.loc === k}">${
  ten[laBtp() ? 1 : 0]} <b>${hang.filter(f).length}</b></button>`).join('')}</div>
      ${hang.length > 8 ? `<input class="sx-textarea" type="search" id="kk-tim" autocomplete="off"
        placeholder="${laBtp() ? 'Tìm mã / lô…' : 'Tìm mã…'}" value="${esc(st.tim)}">` : ''}
      <div class="sx-kk-ds">${khoi || `<div class="sx-muted">${st.loc === 'chua'
    ? (laBtp() ? 'Đã cân hết các lô có trên sổ.' : 'Đã đếm hết các mã có trên sổ.') : 'Không có mã nào.'}</div>`}</div>
      ${laBtp() ? '<button type="button" class="sx-btn" id="kk-them">+ MÃ KHÁC</button>' : `<div class="sx-vh-hang2">
        <button type="button" class="sx-btn" id="kk-them">+ MÃ KHÁC</button>
        <button type="button" class="sx-btn sx-quet-nut" id="kk-quet">⌗ QUÉT HỘP</button>
      </div>`}
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="kk-xem">${
  dl.duoc_chot ? 'XEM TRƯỚC & CHỐT' : 'XEM TRƯỚC'}</button>
      ${dl.duoc_chot ? '' : '<div class="sx-muted">Xong thì báo thủ kho / quản lý vào chốt.</div>'}
      <div class="sx-kk-phu">
        <button type="button" class="sx-btn sx-btn-ghost" id="kk-in">🖨 In bản nháp</button>
        ${p.duoc_huy ? '<button type="button" class="sx-btn sx-btn-ghost" id="kk-huy">Bỏ phiếu kiểm kê</button>' : ''}
      </div>
      ${veGanDay()}
      ${veNutAm()}`;

    ganKho();
    container.querySelectorAll('[data-loc]').forEach((b) => b.addEventListener('click', () => {
      st.loc = b.dataset.loc; ve();
    }));
    const tim = $('#kk-tim');
    if (tim) {
      tim.addEventListener('input', () => {
        st.tim = tim.value;
        const vt = tim.selectionStart;
        ve();
        const moi = $('#kk-tim');
        if (moi) { moi.focus(); moi.setSelectionRange(vt, vt); }
      });
    }
    container.querySelectorAll('[data-them]').forEach((b) => b.addEventListener('click', () => {
      moDong(hang[Number(b.dataset.them)], null);
    }));
    container.querySelectorAll('[data-sua]').forEach((b) => b.addEventListener('click', () => {
      const [i, j] = b.dataset.sua.split(':').map(Number);
      moDong(hang[i], hang[i].dem[j]);
    }));
    container.querySelectorAll('[data-lo]').forEach((b) => b.addEventListener('click', () => {
      const [i, j] = b.dataset.lo.split(':').map(Number);
      moCan(hang[i], hang[i].lo[j]);
    }));
    container.querySelectorAll('[data-lokhac]').forEach((b) => b.addEventListener('click', () => {
      moLoKhac(hang[Number(b.dataset.lokhac)]);
    }));
    container.querySelectorAll('[data-het]').forEach((b) => b.addEventListener('click', () => lam(
      () => call('sx.api.kiemke.het_hang', { name: p.name, item: hang[Number(b.dataset.het)].item }), b)));
    container.querySelectorAll('[data-lai]').forEach((b) => b.addEventListener('click', () => {
      const x = hang[Number(b.dataset.lai)];
      lam(() => call('sx.api.kiemke.dem_lai', { name: p.name, item: x.item }), b)
        .then((xong) => { if (xong) toast(`Đã bỏ số ${dem()} của ${x.ten} — ${dem()} lại mã này.`); });
    }));
    $('#kk-them').addEventListener('click', () => moChonMa());
    const quet = $('#kk-quet');
    if (quet) {
      quet.addEventListener('click', () => moQuet({
        ma_quet: boot && boot.ma_quet, loai: 'sp', kicker: 'Kiểm kê', title: 'Quét hộp',
        onTim: (item) => {
          const x = hang.find((h) => h.item === item) || moi(dl.danh_muc.find((h) => h.item === item));
          if (!x) { toastErr('Mã này không phải thành phẩm.'); return; }
          moDong(x, null);
        },
      }));
    }
    $('#kk-xem').addEventListener('click', (e) => xemTruoc(e.currentTarget));
    const td = $('#kk-td');
    if (td) td.addEventListener('click', () => moThoiDiem(p));
    $('#kk-in').addEventListener('click', () => inBienBan(p.name));
    const huy = $('#kk-huy');
    if (huy) {
      huy.addEventListener('click', () => confirm2Step({
        title: `Bỏ phiếu kiểm kê ${p.name}`,
        message: `Phiếu chưa chốt nên chưa có gì vào kho. Bỏ phiếu là mất hết số đã ${dem()}.`,
        confirmLabel: 'BỎ PHIẾU',
        onConfirm: async () => {
          try { dl = await call('sx.api.kiemke.huy', { name: p.name }); ve(); toast('Đã bỏ phiếu kiểm kê.'); }
          catch (e) { toastErr(e.message); throw e; }
        },
      }));
    }
    ganGanDay();
  }

  // D189: mã chưa quản lý lô / có tồn không gắn lô — đếm như mã khác, chốt chuyển sang lô. D191: cờ lô là của mã, áp
  // mọi kho — tồn ở kho khác chốt xử lý luôn (nói trước từng kho); riêng kho của công ty khác thì chưa bật lô được.
  function veLo(x) {
    const kk = x.kho_khac || [];
    const cty = kk.filter((k) => k.cty_khac);
    if (x.bat_lo && cty.length) {
      return `<div class="sx-kk-nhac">⚠ Mã chưa quản lý theo lô, còn tồn ở kho của công ty khác (${esc(cty.map((k) => `${
        k.kho}: ${formatNumber(k.so)}`).join(', '))}) — chưa bật lô được: điều chỉnh tồn kho đó về 0 trước khi chốt.</div>`;
    }
    if (x.bat_lo && kk.length) {
      return `<div class="sx-kk-nhac">Mã chưa quản lý theo lô — chốt sẽ bật lô: tồn cũ không lô về 0, số đếm vào lô theo HSD.
        Cờ lô là của mã, áp cả kho khác — chốt xử lý luôn: ${esc(kk.map((k) => `${k.kho} ${formatNumber(k.so)} → ${
  k.so > 0 ? 'lô tồn cũ (chưa rõ HSD), vẫn bán được' : 'về 0 (tồn âm)'}`).join('; '))}.</div>`;
    }
    if (x.bat_lo) {
      return '<div class="sx-kk-nhac">Mã chưa quản lý theo lô — chốt sẽ bật lô: tồn cũ không lô về 0, số đếm vào lô theo HSD.</div>';
    }
    if (x.le_khong_lo) {
      return `<div class="sx-kk-nhac">Có ${formatNumber(x.le_khong_lo)} tồn không gắn lô (dữ liệu cũ) — chốt đưa phần đó về 0 / vào lô theo số đếm.</div>`;
    }
    return '';
  }

  function veMa(x, i) {
    const l = lechCua(x);
    const tom = x.da_dem
      ? `đếm <b>${formatNumber(x.tong_dem)}</b> · sổ ${formatNumber(x.so_sach)} · ${Math.abs(l) > 1e-9
        ? `<span class="sx-kk-lech">${coDau(l)}</span>` : '<span class="sx-kk-khop">khớp</span>'}`
      : `sổ <b>${formatNumber(x.so_sach)}</b> · <span class="sx-kk-chua">chưa đếm${
        x.so_sach > 0 ? ' — chốt về 0' : ''}</span>`;
    const tren = [x.chua_hsd > 0 ? `chưa có HSD ${formatNumber(x.chua_hsd)}` : '',
      ...x.theo_hsd.map((h) => `HSD ${veNgayDu(h.hsd)}: ${formatNumber(h.so)}`),
      x.thu_hoi > 0 ? `thu hồi ${formatNumber(x.thu_hoi)} (để riêng, không đếm)` : ''].filter(Boolean).join(' · ');
    const dong = x.dem.map((d, j) => (d.hsd
      ? `<button type="button" class="sx-np-chip${d.hsd < dl.hom_nay ? ' sx-kk-hethan' : ''}" data-sua="${i}:${j}">HSD ${
        esc(veNgayDu(d.hsd))} · ${formatNumber(d.so)}${d.chi_tiet ? ` <i>(${esc(moTaUom(d.chi_tiet))})</i>` : ''}${
        d.hsd < dl.hom_nay ? ' · hết hạn' : ''} ✎</button>`
      : '<span class="sx-kk-het">không còn hàng</span>')).join('');
    return `<div class="sx-kk-ma${x.da_dem ? ' sx-kk-ma-xong' : ''}">
      <div class="sx-kk-dau"><div class="sx-vh-name">${esc(x.ten)}</div><div class="sx-kk-so">${tom}</div></div>
      ${tren ? `<div class="sx-vh-meta">Sổ: ${esc(tren)}</div>` : ''}
      ${x.khong_lo ? veLo(x) : ''}
      <div class="sx-kk-dong">${dong}
        <button type="button" class="sx-np-chip sx-kk-them" data-them="${i}">+ HSD</button>
        ${x.da_dem ? `<button type="button" class="sx-np-chip" data-lai="${i}">Đếm lại</button>`
    : `<button type="button" class="sx-np-chip" data-het="${i}">Không còn</button>`}
      </div></div>`;
  }

  // Bán thành phẩm: mỗi lô một ô bấm — chưa cân thì ghi "CÂN", đã cân thì số cân + lệch của lô.
  function veMaBtp(x, i) {
    const lo = x.lo.filter((l) => !l.thu_hoi);
    const xong = lo.filter((l) => l.can != null).length;
    const tom = x.da_dem
      ? `${xong}/${lo.length} lô · cân <b>${kg(x.tong_dem)}</b> · ${Math.abs(x.lech) > 1e-9
        ? `<span class="sx-kk-lech">${coDau(x.lech, 3)} kg</span>` : '<span class="sx-kk-khop">khớp</span>'}`
      : `sổ <b>${kg(x.so_sach)}</b> kg · <span class="sx-kk-chua">chưa cân</span>`;
    const o = x.lo.map((l, j) => {
      const ten = esc(l.batch || 'không lô');
      if (l.thu_hoi) return `<span class="sx-kk-het">${ten} · thu hồi ${kg(l.so)} kg — để riêng, không cân</span>`;
      if (l.can == null) {
        return `<button type="button" class="sx-np-chip sx-kk-lo-chua" data-lo="${i}:${j}">${ten}${
          l.ngay ? ` <i>${esc(veNgayDu(l.ngay).slice(0, 5))}</i>` : ''} · sổ ${kg(l.so)} · <b>CÂN</b></button>`;
      }
      const d = l.can - l.so;
      return `<button type="button" class="sx-np-chip" data-lo="${i}:${j}">${ten} · <b>${kg(l.can)}</b> kg${
        Math.abs(d) > 1e-9 ? ` <i>(${coDau(d, 3)})</i>` : ' <i>khớp</i>'} ✎</button>`;
    }).join('');
    return `<div class="sx-kk-ma${x.da_dem && !x.con_chua ? ' sx-kk-ma-xong' : ''}">
      <div class="sx-kk-dau"><div class="sx-vh-name">${esc(x.ten)}</div><div class="sx-kk-so">${tom}</div></div>
      ${x.le ? `<div class="sx-kk-nhac">Có ${kg(x.le)} kg tồn KHÔNG gắn lô — sửa trên Desk, không cân ở đây.</div>` : ''}
      <div class="sx-kk-dong">${o}
        ${x.khong_lo ? '' : `<button type="button" class="sx-np-chip sx-kk-them" data-lokhac="${i}">+ LÔ KHÁC / MỚI</button>`}
        ${x.da_dem ? `<button type="button" class="sx-np-chip" data-lai="${i}">Cân lại cả mã</button>`
    : (lo.length ? `<button type="button" class="sx-np-chip" data-het="${i}">Không còn</button>` : '')}
      </div></div>`;
  }

  // Mã ngoài sổ (đếm thấy mà kho này chưa từng có): dựng dòng trống để mở bàn số.
  function moi(d) {
    return d ? { ...d, so_sach: 0, chua_hsd: 0, thu_hoi: 0, theo_hsd: [], dem: [], tong_dem: 0, da_dem: false } : null;
  }

  function moiBtp(d) {
    return { ...d, lo: [], le: 0, thu_hoi: 0, so_sach: 0, so_sach_dem: 0, tong_dem: 0, lech: 0, con_chua: 0,
      da_dem: false };
  }

  // Một bàn số cho cả số lẫn HSD — y như Nhập kho. `d` = dòng đang sửa, null = dòng mới. Nút HSD nhanh là
  // các HSD đang có trên sổ của mã (chưa đếm); không điền sẵn HSD: phải đọc trên hộp.
  function moDong(x, d) {
    const khac = x.dem.filter((y) => y.hsd && y !== d);
    const daDem = new Set(khac.map((y) => y.hsd));
    moSoHsd({
      kicker: `Kiểm kê · ${dl.phieu.name}`, ten: x.ten, uoms: x.uoms, dvt: x.dvt, ngay: dl.hom_nay,
      chi_tiet: d ? d.chi_tiet : null, tong: d ? d.so : 0, hsd: d ? d.hsd : null, macDinh: null,
      nhanh: x.theo_hsd.filter((h) => !daDem.has(h.hsd)).map((h) => ({ nhan: veNgayDu(h.hsd), hsd: h.hsd })),
      sauNgay: false,
      phu: `sổ ${formatNumber(x.so_sach)}`,
      daCo: khac.map((y) => ({ nhan: `HSD ${veNgayDu(y.hsd)}`, so: y.so })),
      onDaCo: (k) => moDong(x, khac[k]),
      choPhepKhong: !!d,
      kiemLuu: (t, h) => (daDem.has(h) ? `Mã này đã có dòng HSD ${veNgayDu(h)} — bấm ô HSD đó phía trên để sửa.` : ''),
      onOk: (tong, ct, h) => lam(() => call('sx.api.kiemke.ghi', {
        name: dl.phieu.name, item: x.item, hsd: h || '', so_dem: tong, chi_tiet: ct ? JSON.stringify(ct) : '',
        ...(d ? { hsd_cu: d.hsd } : {}),
      })),
    });
  }

  // Cân một lô: bàn số kg có dấu phẩy. Ô bên phải đọc lại sổ của lô và lệch theo số đang gõ.
  // Lô chưa cân: LƯU số 0 bị chặn (bấm nhầm LƯU là xoá sạch lô trên sổ) — lô hết thật thì bấm LÔ HẾT.
  // Lô đã cân: nút phụ BỎ SỐ CÂN (cân nhầm lô) — lô về chưa cân, chốt giữ nguyên số sổ của lô đó.
  function moCan(x, l) {
    const co = l.can != null;
    const ghi = (v) => lam(() => call('sx.api.kiemke.ghi_lo', {
      name: dl.phieu.name, item: x.item, batch: l.batch || '', so_dem: v,
    }));
    openNumpad({
      kicker: `Kiểm kê · ${dl.phieu.name} · ${x.ten}`,
      title: l.batch ? `Lô ${l.batch}` : `${x.ten} (không lô)`,
      allowDecimal: true,
      unitLabel: 'Cân thật · kg',
      initial: co ? l.can : '',
      hint: (v) => `sổ ${kg(l.so)}${co || v ? ` · ${coDau(v - l.so, 3)}` : ''}`,
      onOk: (v) => {
        if (!co && !(v > 0)) {
          toastErr('Chưa nhập số cân. Lô không còn gì thì bấm LÔ HẾT.');
          moCan(x, l);
          return;
        }
        ghi(v);
      },
      okPhu: co
        ? { label: 'BỎ SỐ CÂN', onOk: () => lam(() => call('sx.api.kiemke.bo_lo', {
          name: dl.phieu.name, item: x.item, batch: l.batch || '' })) }
        : { label: 'LÔ HẾT · 0', onOk: () => ghi(0) },
    });
  }

  // "+ LÔ KHÁC / MỚI": cân thấy hàng của lô mà sổ kho này không có — chọn trong các lô của mã (mới nhất trước);
  // hệ thống chưa có lô đó (thẻ ghi mã lạ, hay bao không thẻ) thì TẠO LÔ MỚI ngay tại đây (D156).
  function moLoKhac(x) {
    const m = openModal({ kicker: `Kiểm kê · ${x.ten}`, title: 'Lô khác (sổ kho này không có)' });
    m.body.innerHTML = `<input class="sx-textarea" type="search" id="kk-tim-lo" autocomplete="off"
        placeholder="Tìm mã lô…">
      <button type="button" class="sx-btn sx-kk-lo-moi" id="kk-lo-moi">+ TẠO LÔ MỚI</button>
      <div id="kk-ds-lo"><div class="sx-muted">Đang tải…</div></div>`;
    const o = m.body.querySelector('#kk-tim-lo');
    const box = m.body.querySelector('#kk-ds-lo');
    const nutMoi = m.body.querySelector('#kk-lo-moi');
    nutMoi.addEventListener('click', () => { m.close(); moLoMoi(x, chuanMa(o.value)); });
    let lan = 0;
    let hen = null;
    async function napDs() {
      lan += 1;
      const n = lan;
      let ds;
      try {
        ds = await call('sx.api.kiemke.lo_khac', { name: dl.phieu.name, item: x.item, tim: o.value.trim() });
      } catch (e) {
        if (n === lan) box.innerHTML = `<div class="sx-error-box">${esc(e.message)}</div>`;
        return;
      }
      if (n !== lan) return;            // đã gõ tiếp — bỏ kết quả cũ
      const q = chuanMa(o.value);
      nutMoi.textContent = q ? `+ TẠO LÔ MỚI «${q}»` : '+ TẠO LÔ MỚI';
      box.innerHTML = ds.length ? `<div class="sx-vh-list">${ds.map((l) => `
        <button type="button" class="sx-nv-row" data-b="${esc(l.batch)}"
          style="flex-direction:row;align-items:center;justify-content:space-between;min-height:var(--sx-tap-lg)">
          <span class="sx-nv-ten">${esc(l.batch)}</span><span class="sx-nv-qty">${esc(veNgayDu(l.ngay))}</span></button>`)
    .join('')}</div>` : `<div class="sx-muted">${q ? `Hệ thống không có lô «${esc(q)}» của mã này — bấm TẠO LÔ MỚI.`
    : 'Mã này không có lô nào khác — hàng không có lô trong hệ thống thì bấm TẠO LÔ MỚI.'}</div>`;
      box.querySelectorAll('[data-b]').forEach((b) => b.addEventListener('click', () => {
        const l = ds.find((y) => y.batch === b.dataset.b);
        m.close();
        moCan(x, { batch: l.batch, so: 0, ngay: l.ngay, can: null, thu_hoi: false });
      }));
    }
    o.addEventListener('input', () => { clearTimeout(hen); hen = setTimeout(napDs, 250); });
    napDs();
  }

  // Lô mới: mã ghi trên thẻ (bỏ trống = app đặt …-KK + ngày làm) + ngày làm, rồi cân. Lô chỉ được tạo khi LƯU số
  // cân (một lần gọi) — bỏ ngang giữa chừng không đẻ lô rác.
  function moLoMoi(x, maGo) {
    const m = openModal({ kicker: `Kiểm kê · ${x.ten}`, title: 'Lô mới (hệ thống chưa có)' });
    m.body.innerHTML = `
      <div class="sx-muted">Cân thấy hàng mà hệ thống chưa có lô: tạo lô mới cho mã này rồi cân. Thẻ có ghi mã lô thì gõ
        đúng mã đó; bao / thùng không có thẻ thì bỏ trống — app tự đặt mã, chép ra thẻ.</div>
      <label class="sx-field-label" for="kk-ma-moi">Mã lô ghi trên thẻ</label>
      <input class="sx-textarea" id="kk-ma-moi" autocomplete="off" autocapitalize="characters" spellcheck="false"
        placeholder="Bỏ trống = app tự đặt" value="${esc(maGo || '')}">
      <label class="sx-field-label" for="kk-ngay-moi">Ngày làm</label>
      <input class="sx-textarea" type="date" id="kk-ngay-moi" max="${esc(dl.hom_nay)}"
        value="${esc(ngayTuMa(maGo) || dl.hom_nay)}">
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="kk-tiep-moi">TIẾP — CÂN LÔ NÀY</button>`;
    const ma = m.body.querySelector('#kk-ma-moi');
    const ngay = m.body.querySelector('#kk-ngay-moi');
    let ngayTay = false;                // đã tự chọn ngày thì thôi đoán ngày theo mã
    ngay.addEventListener('change', () => { ngayTay = true; });
    ma.addEventListener('input', () => {
      const n = ngayTuMa(ma.value);
      if (!ngayTay && n) ngay.value = n;
    });
    m.body.querySelector('#kk-tiep-moi').addEventListener('click', () => {
      const code = chuanMa(ma.value);
      const n = ngay.value;
      if (code && !MA_HOP_LE.test(code)) { toastErr('Mã lô chỉ gồm chữ, số và - . / _ (tối đa 40 ký tự).'); return; }
      if (!n) { toastErr('Chọn ngày làm.'); return; }
      if (n > dl.hom_nay) { toastErr('Ngày làm sau hôm nay.'); return; }
      const co = code && x.lo.find((l) => String(l.batch || '').toUpperCase() === code);
      if (co && co.thu_hoi) { toastErr(`Lô ${co.batch} đang thu hồi — để riêng, không cân ở đây.`); return; }
      m.close();
      if (co) moCan(x, co);             // lô đã có trong danh sách của mã: cân lô đó
      else moCanMoi(x, code, n);
    });
  }

  function moCanMoi(x, ma, ngay) {
    openNumpad({
      kicker: `Kiểm kê · ${dl.phieu.name} · ${x.ten}`,
      title: ma ? `Lô mới ${ma}` : 'Lô mới (app đặt mã)',
      allowDecimal: true,
      unitLabel: 'Cân thật · kg',
      hint: () => `làm ${veNgayDu(ngay)}`,
      onOk: (v) => {
        if (!(v > 0)) { toastErr('Lô mới phải có số cân.'); moCanMoi(x, ma, ngay); return; }
        let kq;
        lam(async () => {
          kq = await call('sx.api.kiemke.ghi_lo_moi', {
            name: dl.phieu.name, item: x.item, ma_lo: ma, ngay, so_dem: v,
          });
          return kq;
        }).then((xong) => { if (xong) baoLoMoi(kq.lo_moi); });
      },
    });
  }

  // App vừa đặt mã cho lô → phải chép ra thẻ treo vào bao / thùng (như "Ghi mã này ra thẻ lô" lúc xuất đỗ).
  function baoLoMoi(lm) {
    if (!lm) return;
    if (!lm.tao) { toast(`Lô ${lm.batch} đã có — đã ghi số cân vào lô đó.`); return; }
    if (!lm.tu_dat) { toast(`Đã tạo lô ${lm.batch}.`); return; }
    const m = openModal({ kicker: 'Kiểm kê · lô mới', title: 'Ghi mã này ra thẻ hàng' });
    m.body.innerHTML = `
      <div class="sx-lot-display">${esc(lm.batch)}</div>
      <div class="sx-modal-msg" style="text-align:center">${'App vừa đặt mã cho lô mới. Chép mã trên ra thẻ, treo vào '
        + 'đúng bao / thùng vừa cân.'}</div>
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="kk-da-ghi">✓ ĐÃ GHI THẺ</button>`;
    m.body.querySelector('#kk-da-ghi').addEventListener('click', () => m.close());
  }

  function moChonMa() {
    const btp = laBtp();
    const m = openModal({ kicker: 'Kiểm kê', title: 'Mã khác (chưa có trên sổ kho)' });
    const ds = dl.danh_muc || [];
    m.body.innerHTML = `<input class="sx-textarea" type="search" id="kk-loc" autocomplete="off"
        placeholder="Tìm trong ${ds.length} ${btp ? 'bán thành phẩm' : 'thành phẩm'}…"><div id="kk-ds-ma"></div>`;
    const o = m.body.querySelector('#kk-loc');
    const box = m.body.querySelector('#kk-ds-ma');
    function veDs() {
      const q = o.value.toLowerCase().trim();
      const khop = ds.filter((x) => !q || x.ten.toLowerCase().includes(q) || x.item.toLowerCase().includes(q));
      box.innerHTML = khop.length ? `<div class="sx-vh-list">${khop.map((x) => `
        <button type="button" class="sx-nv-row" data-ma="${esc(x.item)}"
          style="flex-direction:row;align-items:center;justify-content:space-between;min-height:var(--sx-tap-lg)">
          <span class="sx-nv-ten">${esc(x.ten)}</span><span class="sx-nv-qty">${esc(btp ? x.nhom || '' : x.dvt || '')}</span></button>`)
    .join('')}</div>` : '<div class="sx-muted">Không tìm thấy.</div>';
      box.querySelectorAll('[data-ma]').forEach((b) => b.addEventListener('click', () => {
        m.close();
        const d = ds.find((x) => x.item === b.dataset.ma);
        if (!btp) { moDong(moi(d), null); return; }
        const x = moiBtp(d);
        if (x.khong_lo) moCan(x, { batch: null, so: 0, can: null, thu_hoi: false });
        else moLoKhac(x);
      }));
    }
    o.addEventListener('input', veDs);
    veDs();
  }

  async function xemTruoc(nut) {
    nut.disabled = true;
    let x;
    try { x = await call('sx.api.kiemke.xem_truoc', { name: dl.phieu.name }); } catch (e) {
      toastErr(e.message); return;
    } finally { nut.disabled = false; }
    const t = x.tong;
    const btp = x.loai === BTP;
    const n = (v) => (btp ? kg(v) : formatNumber(v));
    const d = btp ? 3 : 0;
    const dv = btp ? ' kg' : '';
    const m = openModal({ kicker: 'Kiểm kê · xem trước khi chốt', title: x.name });
    m.body.innerHTML = `
      <div class="sx-kk-moc">Chốt sổ tại: <b>${t.thoi_diem ? `${esc(veLuc(t.thoi_diem))} — sổ sách tính tới lúc đó, chứng từ ghi lùi về lúc đó`
    : 'lúc bấm chốt'}</b></div>
      <div class="sx-kk-tien">${t.so_ma} mã${btp ? ` · ${t.so_lo} lô` : ''} · sổ ${n(t.so_sach)} → ${btp ? 'cân' : 'đếm'} ${
  n(t.dem)}${dv} · <span class="${Math.abs(t.dem - t.so_sach) > 1e-9 ? 'sx-kk-lech' : 'sx-kk-khop'}">${
  coDau(t.dem - t.so_sach, d)}</span></div>
      ${x.loi.length ? `<div class="sx-error-box">Chưa chốt được:<br>${x.loi.map(esc).join('<br>')}</div>` : ''}
      ${x.canh_bao.map((c) => `<div class="sx-warn-text">⚠ ${esc(c)}</div>`).join('')}
      <div class="sx-vh-list">${x.ma.map((r) => `
        <div class="sx-vh-row" style="cursor:default"><div class="sx-vh-who">
          <div class="sx-vh-name">${esc(r.ten)}</div>
          <div class="sx-vh-meta">${r.chua_dem ? '<span class="sx-kk-chua">chưa đếm → về 0</span> · ' : ''}${
  r.bat_lo ? '<span class="sx-kk-chua">bật quản lý lô</span> · ' : ''}${
  r.le_khong_lo ? '<span class="sx-kk-chua">tồn không lô về 0</span> · ' : ''}${esc([
    btp && r.lo_can ? `${r.lo_can} lô` : '',
    r.chuyen ? `chuyển ${formatNumber(r.chuyen)} từ ${r.lo_cu} lô cũ sang lô theo HSD` : '',
    r.thieu ? `thiếu ${n(r.thieu)}${dv}` : '', r.thua ? `thừa ${n(r.thua)}${dv}` : '',
    r.bu_am ? `bù lô âm ${n(r.bu_am)}${dv}` : '',
    r.thu_hoi ? `thu hồi ${n(r.thu_hoi)}${dv} để riêng` : ''].filter(Boolean).join(' · ')
    || 'khớp sổ — không đổi gì')}</div></div>
          <span class="sx-nv-qty">${n(r.so_sach)} → ${n(r.dem)}</span></div>`).join('')}</div>
      <div class="sx-muted">${btp ? `Chốt sẽ sinh ${t.phieu_kho} chứng từ kho: thiếu / thừa từng lô ghi điều chỉnh kho.
        Lô chưa cân giữ nguyên số sổ sách.` : `Chốt sẽ <b>đặt lại toàn bộ kho thành phẩm</b> theo số đếm, sinh ${
  t.phieu_kho} chứng từ kho: chuyển lô giữ nguyên giá vốn; thiếu / thừa ghi điều chỉnh kho. Sau chốt mỗi loại,
        mỗi HSD một lô${t.ve_0 ? `; ${t.ve_0} mã chưa đếm về 0` : ''}${
  t.bat_lo ? `; ${t.bat_lo} mã bật quản lý lô` : ''}.`}</div>`;
    if (x.duoc_chot && !x.loi.length && x.ma.length) {
      const b = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'CHỐT KIỂM KÊ');
      b.type = 'button';
      b.addEventListener('click', () => confirm2Step({
        title: `Chốt kiểm kê ${x.name}`,
        message: `${btp ? '' : 'Đặt lại toàn bộ kho thành phẩm theo số đếm. '}${t.so_ma} mã${btp ? `, ${t.so_lo} lô` : ''}: sổ ${
          n(t.so_sach)} → ${btp ? 'cân' : 'đếm'} ${n(t.dem)}${dv} (${coDau(t.dem - t.so_sach, d)})${
          t.ve_0 ? `; ${t.ve_0} mã chưa đếm về 0` : ''}${t.bat_lo ? `; ${t.bat_lo} mã bật quản lý lô` : ''}${
          (t.kho_am || []).length ? `; tồn âm ở kho khác đưa về 0: ${t.kho_am.map((k) => `${k.ten} ở ${k.kho} ${
            formatNumber(k.so)}`).join(', ')}` : ''}.\n`
          + `Sinh ${t.phieu_kho} chứng từ kho${t.thoi_diem ? `, ghi lùi về ${veLuc(t.thoi_diem)}${t.bat_lui
            ? ` (riêng việc chuyển ${t.bat_lui} mã bật lô vào lô theo HSD làm lúc bấm, với tồn hiện tại)` : ''}` : ''}. `
          + 'Chốt rồi không sửa trên màn này được nữa — muốn huỷ phải huỷ '
          + 'phiếu kiểm kê trên Desk (các chứng từ kho huỷ theo).',
        confirmLabel: 'CHỐT',
        onConfirm: async () => {
          try {
            const kq = await call('sx.api.kiemke.chot', { name: x.name });
            m.close();
            toast(`Đã chốt ${kq.name}: ${kq.so_ma} mã, lệch ${coDau(kq.tong_lech, d)}${dv}, ${kq.so_phieu_kho} chứng từ kho.`);
            dl = await tai(khoNay());
            ve();
          } catch (e) { toastErr(e.message); throw e; }
        },
      }));
      m.body.appendChild(b);
    } else if (!x.duoc_chot) {
      m.body.appendChild(el('div', 'sx-muted', 'Xong thì báo thủ kho / quản lý vào chốt.'));
    }
  }

  async function inBienBan(name) {
    try {
      inHtml(`Biên bản kiểm kê ${name}`, await call('sx.api.kiemke.bien_ban', { name }));
    } catch (e) { toastErr(e.message); }
  }

  function inHtml(tieuDe, html) {
    const w = window.open('', '_blank');
    if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
    // Cửa sổ about:blank không thừa kế bảng mã — tự khai, như các tờ in khác.
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>${
      esc(tieuDe)}</title></head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 400);
  }

  ve();
}
