// Card "Kiểm kê kho" — đếm / cân hàng trong kho rồi chốt.
//
// THÀNH PHẨM (D154): lô thành phẩm vào kho từ trước khi lô mang HSD — truy xuất theo HSD in trên hộp không ra,
// xuất FEFO và báo cận date bỏ sót. Thủ kho đi từng mã, đếm theo HSD in trên hộp (cùng bàn số thùng / hộp + HSD
// với Nhập kho), xem trước rồi CHỐT — số đếm thay tồn của mã: lô cũ chuyển sang lô theo HSD, thừa / thiếu ghi
// điều chỉnh kho.
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
  ['chua', ['Chưa đếm', 'Chưa cân'], (x) => (x.lo ? x.con_chua > 0 : !x.da_dem && !x.khong_lo)],
  ['dem', ['Đã đếm', 'Đã cân'], (x) => x.da_dem],
  ['lech', ['Lệch', 'Lệch'], (x) => x.da_dem && Math.abs(lechCua(x)) > 1e-9],
  ['het', ['Tất cả', 'Tất cả'], () => true],
];

function lechCua(x) { return x.lech != null ? x.lech : x.tong_dem - x.so_sach; }
const kg = (n) => formatNumber(n, 3);
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
      const co = dl.hang.filter((x) => !x.khong_lo && x.so_sach > 0);
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
    : `Đếm hàng trong kho theo HSD in trên hộp rồi chốt: lô cũ chưa có HSD chuyển sang lô theo HSD, thừa / thiếu
        ghi điều chỉnh kho.`}</div>
      ${tom}
      ${veCanhBao()}
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="kk-bat">BẮT ĐẦU KIỂM KÊ</button>
      ${veGanDay()}`;
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
      tien = `Đã đếm ${daDem.length}/${hang.filter((x) => !x.khong_lo).length} mã`;
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
      <div class="sx-kk-tien">${tien}${daDem.length ? ` · lệch <span class="${Math.abs(lech) > 1e-9 ? 'sx-kk-lech'
    : 'sx-kk-khop'}">${coDau(lech, le())}${laBtp() ? ' kg' : ''}</span>` : ''}</div>
      <div class="sx-kk-nhac">${laBtp()
    ? 'Đang kiểm kê: lô đã cân thì đừng xuất / nhập lô đó. Có chứng từ kho của lô sau lúc cân thì phải cân lại lô đó mới chốt được.'
    : 'Đang kiểm kê: đừng bán / nhập / xuất các mã đang đếm. Có chứng từ kho sau lúc đếm thì phải đếm lại mã đó mới chốt được.'}</div>
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
      ${veGanDay()}`;

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
          if (x.khong_lo) { toastErr(`${x.ten}: mã không quản lý theo lô — không ghi HSD được.`); return; }
          moDong(x, null);
        },
      }));
    }
    $('#kk-xem').addEventListener('click', (e) => xemTruoc(e.currentTarget));
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

  function veMa(x, i) {
    if (x.khong_lo) {
      return `<div class="sx-kk-ma sx-kk-ma-tat"><div class="sx-vh-name">${esc(x.ten)}</div>
        <div class="sx-vh-meta">sổ ${formatNumber(x.so_sach)} · mã không quản lý theo lô — không ghi HSD được</div></div>`;
    }
    const l = lechCua(x);
    const tom = x.da_dem
      ? `đếm <b>${formatNumber(x.tong_dem)}</b> · sổ ${formatNumber(x.so_sach)} · ${Math.abs(l) > 1e-9
        ? `<span class="sx-kk-lech">${coDau(l)}</span>` : '<span class="sx-kk-khop">khớp</span>'}`
      : `sổ <b>${formatNumber(x.so_sach)}</b> · <span class="sx-kk-chua">chưa đếm</span>`;
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
        ${x.khong_lo ? '' : `<button type="button" class="sx-np-chip sx-kk-them" data-lokhac="${i}">+ LÔ KHÁC</button>`}
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
        if (!co && !(v > 0)) { toastErr('Chưa nhập số cân. Lô không còn gì thì bấm LÔ HẾT.'); return; }
        ghi(v);
      },
      okPhu: co
        ? { label: 'BỎ SỐ CÂN', onOk: () => lam(() => call('sx.api.kiemke.bo_lo', {
          name: dl.phieu.name, item: x.item, batch: l.batch || '' })) }
        : { label: 'LÔ HẾT · 0', onOk: () => ghi(0) },
    });
  }

  // "+ LÔ KHÁC": cân thấy hàng của lô mà sổ kho này không có — chọn trong các lô của mã (mới nhất trước).
  function moLoKhac(x) {
    const m = openModal({ kicker: `Kiểm kê · ${x.ten}`, title: 'Lô khác (sổ kho này không có)' });
    m.body.innerHTML = `<input class="sx-textarea" type="search" id="kk-tim-lo" autocomplete="off"
        placeholder="Tìm mã lô…"><div id="kk-ds-lo"><div class="sx-muted">Đang tải…</div></div>`;
    const o = m.body.querySelector('#kk-tim-lo');
    const box = m.body.querySelector('#kk-ds-lo');
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
      box.innerHTML = ds.length ? `<div class="sx-vh-list">${ds.map((l) => `
        <button type="button" class="sx-nv-row" data-b="${esc(l.batch)}"
          style="flex-direction:row;align-items:center;justify-content:space-between;min-height:var(--sx-tap-lg)">
          <span class="sx-nv-ten">${esc(l.batch)}</span><span class="sx-nv-qty">${esc(veNgayDu(l.ngay))}</span></button>`)
    .join('')}</div>` : '<div class="sx-muted">Không có lô nào khác của mã này.</div>';
      box.querySelectorAll('[data-b]').forEach((b) => b.addEventListener('click', () => {
        const l = ds.find((y) => y.batch === b.dataset.b);
        m.close();
        moCan(x, { batch: l.batch, so: 0, ngay: l.ngay, can: null, thu_hoi: false });
      }));
    }
    o.addEventListener('input', () => { clearTimeout(hen); hen = setTimeout(napDs, 250); });
    napDs();
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
      <div class="sx-kk-tien">${t.so_ma} mã${btp ? ` · ${t.so_lo} lô` : ''} · sổ ${n(t.so_sach)} → ${btp ? 'cân' : 'đếm'} ${
  n(t.dem)}${dv} · <span class="${Math.abs(t.dem - t.so_sach) > 1e-9 ? 'sx-kk-lech' : 'sx-kk-khop'}">${
  coDau(t.dem - t.so_sach, d)}</span></div>
      ${x.loi.length ? `<div class="sx-error-box">Chưa chốt được:<br>${x.loi.map(esc).join('<br>')}</div>` : ''}
      ${x.canh_bao.map((c) => `<div class="sx-warn-text">⚠ ${esc(c)}</div>`).join('')}
      <div class="sx-vh-list">${x.ma.map((r) => `
        <div class="sx-vh-row" style="cursor:default"><div class="sx-vh-who">
          <div class="sx-vh-name">${esc(r.ten)}</div>
          <div class="sx-vh-meta">${esc([
    btp && r.lo_can ? `${r.lo_can} lô` : '',
    r.chuyen ? `chuyển ${formatNumber(r.chuyen)} từ ${r.lo_cu} lô cũ sang lô theo HSD` : '',
    r.thieu ? `thiếu ${n(r.thieu)}${dv}` : '', r.thua ? `thừa ${n(r.thua)}${dv}` : '',
    r.bu_am ? `bù lô âm ${n(r.bu_am)}${dv}` : '',
    r.thu_hoi ? `thu hồi ${n(r.thu_hoi)}${dv} để riêng` : ''].filter(Boolean).join(' · ')
    || 'khớp sổ — không đổi gì')}</div></div>
          <span class="sx-nv-qty">${n(r.so_sach)} → ${n(r.dem)}</span></div>`).join('')}</div>
      <div class="sx-muted">${btp ? `Chốt sẽ sinh ${t.phieu_kho} chứng từ kho: thiếu / thừa từng lô ghi điều chỉnh kho.
        Lô chưa cân giữ nguyên số sổ sách.` : `Chốt sẽ sinh ${t.phieu_kho} chứng từ kho: chuyển lô giữ nguyên giá vốn;
        thiếu / thừa ghi điều chỉnh kho. Mã chưa đếm giữ nguyên số sổ sách.`}</div>`;
    if (x.duoc_chot && !x.loi.length && x.ma.length) {
      const b = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'CHỐT KIỂM KÊ');
      b.type = 'button';
      b.addEventListener('click', () => confirm2Step({
        title: `Chốt kiểm kê ${x.name}`,
        message: `${t.so_ma} mã${btp ? `, ${t.so_lo} lô` : ''}: sổ ${n(t.so_sach)} → ${btp ? 'cân' : 'đếm'} ${n(t.dem)}${dv} (${
          coDau(t.dem - t.so_sach, d)}).\n`
          + `Sinh ${t.phieu_kho} chứng từ kho. Chốt rồi không sửa trên màn này được nữa — muốn huỷ phải huỷ `
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
      const html = await call('sx.api.kiemke.bien_ban', { name });
      const w = window.open('', '_blank');
      if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
      // Cửa sổ about:blank không thừa kế bảng mã — tự khai, như các tờ in khác.
      w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Biên bản kiểm kê ${
        esc(name)}</title></head><body>${html}</body></html>`);
      w.document.close();
      w.focus();
      setTimeout(() => w.print(), 400);
    } catch (e) { toastErr(e.message); }
  }

  ve();
}
