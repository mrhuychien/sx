// Card "Kiểm kê kho thành phẩm" (D154) — đếm hàng trong kho theo HSD in trên hộp rồi chốt.
//
// Lô thành phẩm vào kho từ trước khi lô mang HSD: truy xuất theo HSD in trên hộp không ra, xuất FEFO và
// báo cận date bỏ sót. Kiểm kê chốt lại một lần cho đúng: thủ kho đi từng mã, đếm theo HSD in trên hộp
// (cùng bàn số thùng / hộp + HSD với Nhập kho), quản lý xem trước rồi CHỐT — số đếm thay tồn của mã: lô cũ
// chuyển sang lô theo HSD, thừa / thiếu ghi điều chỉnh kho. Mỗi lần LƯU là ghi thẳng vào phiếu trên server:
// tải lại trang, đổi máy vẫn còn số đã đếm.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { moTaUom } from '/assets/sx/sx/components/soluong.js';
import { moQuet } from '/assets/sx/sx/components/quet.js';
import { moSoHsd, veNgayDu } from '/assets/sx/sx/cards/nhapkhotp.js';

// Mặc định xem TẤT CẢ, thứ tự cố định theo tên (server xếp): lưu một dòng xong mã vẫn đứng nguyên chỗ, nút
// "+ HSD" ngay đó cho HSD tiếp theo — lọc "Chưa đếm" mà mã biến mất sau dòng đầu là bắt người ta đi tìm lại.
const st = { loc: 'het', tim: '' };     // giữ bộ lọc qua các lần vẽ lại

const LOC = [
  ['chua', 'Chưa đếm', (x) => !x.da_dem && !x.khong_lo],
  ['dem', 'Đã đếm', (x) => x.da_dem],
  ['lech', 'Lệch', (x) => x.da_dem && Math.abs(x.tong_dem - x.so_sach) > 1e-9],
  ['het', 'Tất cả', () => true],
];

const coDau = (n) => `${n > 0 ? '+' : ''}${formatNumber(n)}`;

export async function render({ container, call, boot }) {
  container.className = 'sx-card sx-kk';
  container.innerHTML = '<div class="sx-muted">Đang tải kiểm kê…</div>';
  let dl;
  try { dl = await call('sx.api.kiemke.tong_quan'); } catch (e) {
    container.innerHTML = `<div class="sx-field-label">Kiểm kê kho thành phẩm</div>
      <div class="sx-muted">Chưa dùng được: ${esc(e.message)}</div>`;
    return;
  }
  const $ = (q) => container.querySelector(q);

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

  // ─────────────────────────── chưa có phiếu đang đếm ───────────────────────────
  function veChuaMo() {
    const co = dl.hang.filter((x) => !x.khong_lo && x.so_sach > 0);
    const chua = co.filter((x) => x.chua_hsd > 0);
    container.innerHTML = `
      <div class="sx-field-label">Kiểm kê kho thành phẩm</div>
      <div class="sx-muted">Đếm hàng trong kho theo HSD in trên hộp rồi chốt: lô cũ chưa có HSD chuyển sang
        lô theo HSD, thừa / thiếu ghi điều chỉnh kho.</div>
      ${chua.length ? `<div class="sx-kk-bao">${chua.length} mã còn hàng chưa ghi HSD · ${formatNumber(
    chua.reduce((a, x) => a + x.chua_hsd, 0))} sp</div>`
    : `<div class="sx-muted">${co.length} mã đang có hàng trong ${esc(dl.kho)} — lô nào cũng đã có HSD.</div>`}
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="kk-bat">BẮT ĐẦU KIỂM KÊ</button>
      ${veGanDay()}`;
    $('#kk-bat').addEventListener('click', (e) => lam(() => call('sx.api.kiemke.bat_dau'), e.currentTarget));
    ganGanDay();
  }

  function veGanDay() {
    if (!dl.gan_day.length) return '';
    return `<div class="sx-field-label">Kiểm kê đã chốt — bấm để in biên bản</div>
      <div class="sx-vh-list">${dl.gan_day.map((g) => `
        <div class="sx-vh-row" data-bb="${esc(g.name)}" role="button" tabindex="0" style="cursor:pointer">
          <div class="sx-vh-who"><div class="sx-vh-name">${esc(g.name)} · ${esc(veNgayDu(g.ngay))}${
  g.trang_thai === 'Đã huỷ' ? ' <span class="sx-badge sx-badge-err">Đã huỷ</span>' : ''}</div>
            <div class="sx-vh-meta">${g.so_ma} mã · sổ ${formatNumber(g.tong_so_sach)} → đếm ${
  formatNumber(g.tong_dem)}</div></div>
          <span class="sx-nv-qty">${coDau(g.tong_lech)}</span></div>`).join('')}</div>`;
  }

  function ganGanDay() {
    container.querySelectorAll('[data-bb]').forEach((b) => b.addEventListener('click', () => inBienBan(b.dataset.bb)));
  }

  // ─────────────────────────── đang đếm ───────────────────────────
  function veDangDem(p) {
    const hang = dl.hang;
    const daDem = hang.filter((x) => x.da_dem);
    const lech = daDem.reduce((a, x) => a + x.tong_dem - x.so_sach, 0);
    const fn = (LOC.find((l) => l[0] === st.loc) || LOC[3])[2];
    const q = st.tim.toLowerCase().trim();
    const ds = hang.map((x, i) => [x, i]).filter(([x]) => fn(x)
      && (!q || x.ten.toLowerCase().includes(q) || x.item.toLowerCase().includes(q)));
    container.innerHTML = `
      <div class="sx-field-label">Kiểm kê ${esc(p.name)} · bắt đầu ${esc(veNgayDu(p.bat_dau_luc))} ${
  esc(String(p.bat_dau_luc).slice(11, 16))} · ${esc(dl.kho)}</div>
      <div class="sx-kk-tien">Đã đếm ${daDem.length}/${hang.filter((x) => !x.khong_lo).length} mã${
  daDem.length ? ` · lệch <span class="${Math.abs(lech) > 1e-9 ? 'sx-kk-lech' : 'sx-kk-khop'}">${coDau(lech)}</span>`
    : ''}</div>
      <div class="sx-kk-nhac">Đang kiểm kê: đừng bán / nhập / xuất các mã đang đếm. Có chứng từ kho sau lúc
        đếm thì phải đếm lại mã đó mới chốt được.</div>
      ${dl.canh_bao.map((c) => `<div class="sx-kk-nhac">⚠ ${esc(c)}</div>`).join('')}
      <div class="sx-kk-loc" role="tablist">${LOC.map(([k, ten, f]) => `<button type="button" role="tab"
        class="sx-np-chip${st.loc === k ? ' sx-np-chip-on' : ''}" data-loc="${k}" aria-selected="${st.loc === k}">${
  ten} <b>${hang.filter(f).length}</b></button>`).join('')}</div>
      ${hang.length > 8 ? `<input class="sx-textarea" type="search" id="kk-tim" autocomplete="off"
        placeholder="Tìm mã…" value="${esc(st.tim)}">` : ''}
      <div class="sx-kk-ds">${ds.length ? ds.map(([x, i]) => veMa(x, i)).join('')
    : `<div class="sx-muted">${st.loc === 'chua' ? 'Đã đếm hết các mã có trên sổ.' : 'Không có mã nào.'}</div>`}</div>
      <div class="sx-vh-hang2">
        <button type="button" class="sx-btn" id="kk-them">+ MÃ KHÁC</button>
        <button type="button" class="sx-btn sx-quet-nut" id="kk-quet">⌗ QUÉT HỘP</button>
      </div>
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="kk-xem">${
  dl.duoc_chot ? 'XEM TRƯỚC & CHỐT' : 'XEM TRƯỚC'}</button>
      ${dl.duoc_chot ? '' : '<div class="sx-muted">Đếm xong báo quản lý vào chốt.</div>'}
      <div class="sx-kk-phu">
        <button type="button" class="sx-btn sx-btn-ghost" id="kk-in">🖨 In bản nháp</button>
        ${p.duoc_huy ? '<button type="button" class="sx-btn sx-btn-ghost" id="kk-huy">Bỏ phiếu kiểm kê</button>' : ''}
      </div>
      ${veGanDay()}`;

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
    container.querySelectorAll('[data-het]').forEach((b) => b.addEventListener('click', () => lam(
      () => call('sx.api.kiemke.het_hang', { name: p.name, item: hang[Number(b.dataset.het)].item }), b)));
    container.querySelectorAll('[data-lai]').forEach((b) => b.addEventListener('click', () => {
      const x = hang[Number(b.dataset.lai)];
      lam(() => call('sx.api.kiemke.dem_lai', { name: p.name, item: x.item }), b)
        .then((xong) => { if (xong) toast(`Đã bỏ số đếm của ${x.ten} — đếm lại mã này.`); });
    }));
    $('#kk-them').addEventListener('click', () => moChonMa());
    $('#kk-quet').addEventListener('click', () => moQuet({
      ma_quet: boot && boot.ma_quet, loai: 'sp', kicker: 'Kiểm kê', title: 'Quét hộp',
      onTim: (item) => {
        const x = hang.find((h) => h.item === item) || moi(dl.danh_muc.find((h) => h.item === item));
        if (!x) { toastErr('Mã này không phải thành phẩm.'); return; }
        if (x.khong_lo) { toastErr(`${x.ten}: mã không quản lý theo lô — không ghi HSD được.`); return; }
        moDong(x, null);
      },
    }));
    $('#kk-xem').addEventListener('click', (e) => xemTruoc(e.currentTarget));
    $('#kk-in').addEventListener('click', () => inBienBan(p.name));
    const huy = $('#kk-huy');
    if (huy) {
      huy.addEventListener('click', () => confirm2Step({
        title: `Bỏ phiếu kiểm kê ${p.name}`,
        message: 'Phiếu chưa chốt nên chưa có gì vào kho. Bỏ phiếu là mất hết số đã đếm.',
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
    const l = x.tong_dem - x.so_sach;
    const so = x.da_dem
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
      <div class="sx-kk-dau"><div class="sx-vh-name">${esc(x.ten)}</div><div class="sx-kk-so">${so}</div></div>
      ${tren ? `<div class="sx-vh-meta">Sổ: ${esc(tren)}</div>` : ''}
      <div class="sx-kk-dong">${dong}
        <button type="button" class="sx-np-chip sx-kk-them" data-them="${i}">+ HSD</button>
        ${x.da_dem ? `<button type="button" class="sx-np-chip" data-lai="${i}">Đếm lại</button>`
    : `<button type="button" class="sx-np-chip" data-het="${i}">Không còn</button>`}
      </div></div>`;
  }

  // Mã ngoài sổ (đếm thấy mà kho này chưa từng có): dựng dòng trống để mở bàn số.
  function moi(d) {
    return d ? { ...d, so_sach: 0, chua_hsd: 0, thu_hoi: 0, theo_hsd: [], dem: [], tong_dem: 0, da_dem: false } : null;
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

  function moChonMa() {
    const m = openModal({ kicker: 'Kiểm kê', title: 'Mã khác (chưa có trên sổ kho)' });
    const ds = dl.danh_muc || [];
    m.body.innerHTML = `<input class="sx-textarea" type="search" id="kk-loc" autocomplete="off"
        placeholder="Tìm trong ${ds.length} thành phẩm…"><div id="kk-ds-ma"></div>`;
    const o = m.body.querySelector('#kk-loc');
    const box = m.body.querySelector('#kk-ds-ma');
    function veDs() {
      const q = o.value.toLowerCase().trim();
      const khop = ds.filter((x) => !q || x.ten.toLowerCase().includes(q) || x.item.toLowerCase().includes(q));
      box.innerHTML = khop.length ? `<div class="sx-vh-list">${khop.map((x) => `
        <button type="button" class="sx-nv-row" data-ma="${esc(x.item)}"
          style="flex-direction:row;align-items:center;justify-content:space-between;min-height:var(--sx-tap-lg)">
          <span class="sx-nv-ten">${esc(x.ten)}</span><span class="sx-nv-qty">${esc(x.dvt || '')}</span></button>`)
    .join('')}</div>` : '<div class="sx-muted">Không tìm thấy.</div>';
      box.querySelectorAll('[data-ma]').forEach((b) => b.addEventListener('click', () => {
        m.close();
        moDong(moi(ds.find((x) => x.item === b.dataset.ma)), null);
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
    const m = openModal({ kicker: 'Kiểm kê · xem trước khi chốt', title: x.name });
    m.body.innerHTML = `
      <div class="sx-kk-tien">${t.so_ma} mã · sổ ${formatNumber(t.so_sach)} → đếm ${formatNumber(t.dem)} ·
        <span class="${Math.abs(t.dem - t.so_sach) > 1e-9 ? 'sx-kk-lech' : 'sx-kk-khop'}">${coDau(t.dem - t.so_sach)}</span></div>
      ${x.loi.length ? `<div class="sx-error-box">Chưa chốt được:<br>${x.loi.map(esc).join('<br>')}</div>` : ''}
      ${x.canh_bao.map((c) => `<div class="sx-warn-text">⚠ ${esc(c)}</div>`).join('')}
      <div class="sx-vh-list">${x.ma.map((r) => `
        <div class="sx-vh-row" style="cursor:default"><div class="sx-vh-who">
          <div class="sx-vh-name">${esc(r.ten)}</div>
          <div class="sx-vh-meta">${esc([
    r.chuyen ? `chuyển ${formatNumber(r.chuyen)} từ ${r.lo_cu} lô cũ sang lô theo HSD` : '',
    r.thieu ? `thiếu ${formatNumber(r.thieu)}` : '', r.thua ? `thừa ${formatNumber(r.thua)}` : '',
    r.bu_am ? `bù lô âm ${formatNumber(r.bu_am)}` : '',
    r.thu_hoi ? `thu hồi ${formatNumber(r.thu_hoi)} để riêng` : ''].filter(Boolean).join(' · ')
    || 'khớp sổ — không đổi gì')}</div></div>
          <span class="sx-nv-qty">${formatNumber(r.so_sach)} → ${formatNumber(r.dem)}</span></div>`).join('')}</div>
      <div class="sx-muted">Chốt sẽ sinh ${t.phieu_kho} chứng từ kho: chuyển lô giữ nguyên giá vốn; thiếu / thừa ghi
        điều chỉnh kho. Mã chưa đếm giữ nguyên số sổ sách.</div>`;
    if (x.duoc_chot && !x.loi.length && x.ma.length) {
      const b = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'CHỐT KIỂM KÊ');
      b.type = 'button';
      b.addEventListener('click', () => confirm2Step({
        title: `Chốt kiểm kê ${x.name}`,
        message: `${t.so_ma} mã: sổ ${formatNumber(t.so_sach)} → đếm ${formatNumber(t.dem)} (${coDau(t.dem - t.so_sach)}).\n`
          + `Sinh ${t.phieu_kho} chứng từ kho. Chốt rồi không sửa trên màn này được nữa — muốn huỷ phải huỷ `
          + 'phiếu kiểm kê trên Desk (các chứng từ kho huỷ theo).',
        confirmLabel: 'CHỐT',
        onConfirm: async () => {
          try {
            const kq = await call('sx.api.kiemke.chot', { name: x.name });
            m.close();
            toast(`Đã chốt ${kq.name}: ${kq.so_ma} mã, lệch ${coDau(kq.tong_lech)}, ${kq.so_phieu_kho} chứng từ kho.`);
            dl = await call('sx.api.kiemke.tong_quan');
            ve();
          } catch (e) { toastErr(e.message); throw e; }
        },
      }));
      m.body.appendChild(b);
    } else if (!x.duoc_chot) {
      m.body.appendChild(el('div', 'sx-muted', 'Đếm xong báo quản lý vào chốt.'));
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
