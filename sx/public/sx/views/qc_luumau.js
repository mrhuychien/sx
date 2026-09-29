// #/qc/luumau — tủ lưu mẫu (D100).
//
// Tủ mẫu có giá trị đúng một lúc: khi khách khiếu nại lô X, mẫu lô X phải còn
// đó và tìm ra ngay. Nên màn này làm ba việc, theo thứ tự hay cần:
//   1. Mẫu ĐẾN HẠN HUỶ đứng đầu, viền đỏ — không ai phải nhớ đi dọn tủ.
//   2. Tìm theo tên / lô / vị trí — khiếu nại tới là gõ lô vào là thấy.
//   3. Lấy mẫu mới: sản phẩm + vị trí hay dùng hiện sẵn thành nút bấm.
//
// Huỷ đúng hạn: một bước xác nhận. Huỷ sớm hoặc lấy ra: bắt buộc lý do — mẫu
// biến mất mà không ai ghi vì sao thì tủ mẫu chỉ còn là cái tủ.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';
import { chip, khungTrong, segment } from '/assets/sx/sx/components/qcui.js';

const st = { tab: 'Đang lưu', q: '' };

const ngayVN = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc.list_luu_mau', { trang_thai: st.tab, q: st.q || null });
  container.innerHTML = '';

  if (dl.duoc_ghi) {
    const lay = el('button', 'sx-btn sx-btn-primary sx-btn-big', '+ LẤY MẪU');
    lay.type = 'button';
    lay.addEventListener('click', () => moLayMau(dl, api));
    container.appendChild(lay);
  }

  container.appendChild(segment(
    [{ v: 'Đang lưu', ten: `Đang lưu${dl.so_den_han ? ` · ${dl.so_den_han} đến hạn` : ''}` },
      { v: 'Đã lấy ra', ten: 'Đã lấy ra' }, { v: 'Đã huỷ', ten: 'Đã huỷ' }],
    st.tab, (v) => { st.tab = v; render(api); }));

  const tim = el('input', 'sx-textarea sx-qc-lm-tim');
  tim.type = 'search';
  tim.placeholder = 'Tìm sản phẩm, lô / HSD, vị trí…';
  tim.value = st.q;
  let hen = null;
  tim.addEventListener('input', () => {
    clearTimeout(hen);
    hen = setTimeout(() => { st.q = tim.value.trim(); render(api); }, 400);
  });
  container.appendChild(tim);

  const ds = el('div', 'sx-qc-than');
  container.appendChild(ds);
  if (!dl.danh_sach.length) {
    ds.appendChild(khungTrong(st.q ? 'Không có mẫu nào khớp.'
      : (st.tab === 'Đang lưu' ? 'Tủ mẫu đang trống.' : 'Chưa có mẫu nào.')));
  }
  dl.danh_sach.forEach((x) => ds.appendChild(veThe(x, dl, api)));
  if (st.q) setTimeout(() => { tim.focus(); tim.setSelectionRange(tim.value.length, tim.value.length); }, 0);
}

function veThe(x, dl, api) {
  const lop = x.trang_thai !== 'Đang lưu' ? 'dong' : (x.den_han ? 'mo' : 'luu');
  const the = el('div', `sx-qc-sc sx-qc-sc-${lop}`);
  the.appendChild(el('div', 'sx-qc-sc-ten',
    `${esc(x.ten_san_pham || x.san_pham)}${x.lo ? ` · <span class="sx-qc-lm-lo">${esc(x.lo)}</span>` : ''}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(`${x.so_luong} ${x.dvt || ''}`.trim()));
  if (x.vi_tri) meta.appendChild(chip(`📍 ${x.vi_tri}`));
  meta.appendChild(el('span', null, `lấy ${esc(ngayVN(x.ngay_lay))} · lưu đến ${esc(ngayVN(x.han_luu))}`));
  if (x.den_han) meta.appendChild(chip('đến hạn huỷ', 'han'));
  else if (x.trang_thai === 'Đang lưu' && x.con_ngay <= 14) meta.appendChild(chip(`còn ${x.con_ngay} ngày`));
  the.appendChild(meta);
  if (x.trang_thai !== 'Đang lưu') {
    the.appendChild(el('div', 'sx-qc-goiy',
      `${esc(x.trang_thai)} ${esc(ngayVN((x.xu_ly_luc || '').slice(0, 10)))}`
      + `${x.ly_do ? ` — ${esc(x.ly_do)}` : ''}`));
  }
  if (x.trang_thai === 'Đang lưu' && dl.duoc_ghi) {
    const nut = el('div', 'sx-qc-lm-nut');
    const huy = el('button', `sx-btn ${x.den_han ? 'sx-btn-primary' : 'sx-btn-ghost'}`, 'HUỶ MẪU');
    huy.type = 'button';
    huy.addEventListener('click', () => (x.den_han
      ? confirm2Step({
        title: `Huỷ mẫu ${x.ten_san_pham}`,
        message: `Lô ${x.lo || '(không ghi lô)'} — đã hết hạn lưu ${ngayVN(x.han_luu)}.`,
        confirmLabel: 'ĐÃ HUỶ MẪU',
        onConfirm: async () => {
          try {
            await api.call('sx.api.qc.xu_ly_luu_mau', { name: x.name, hanh_dong: 'huy' });
            toast('Đã ghi huỷ mẫu');
            render(api);
          } catch (e) { toastErr(e.message); throw e; }
        },
      })
      : moLyDo(x, 'huy', api)));
    const ra = el('button', 'sx-btn sx-btn-ghost', 'LẤY RA');
    ra.type = 'button';
    ra.title = 'Mang mẫu đi dùng: khiếu nại, gửi kiểm nghiệm…';
    ra.addEventListener('click', () => moLyDo(x, 'lay_ra', api));
    nut.appendChild(ra);
    nut.appendChild(huy);
    the.appendChild(nut);
  }
  return the;
}

function moLyDo(x, hanhDong, api) {
  const laHuy = hanhDong === 'huy';
  const m = openModal({
    kicker: laHuy ? 'Huỷ mẫu TRƯỚC hạn' : 'Lấy mẫu ra',
    title: `${x.ten_san_pham}${x.lo ? ` · ${x.lo}` : ''}`,
  });
  m.body.appendChild(el('div', 'sx-modal-msg', laHuy
    ? `Mẫu còn hạn lưu tới ${ngayVN(x.han_luu)}. Huỷ sớm thì phải ghi lý do.`
    : 'Ghi rõ dùng vào việc gì: khiếu nại của ai, gửi kiểm nghiệm ở đâu…'));
  const ta = el('textarea', 'sx-textarea');
  ta.rows = 3;
  ta.placeholder = 'Lý do (bắt buộc)';
  m.body.appendChild(ta);
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', laHuy ? 'HUỶ MẪU' : 'LẤY RA');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!ta.value.trim()) { toastErr('Phải ghi lý do.'); return; }
    ok.disabled = true;
    try {
      await api.call('sx.api.qc.xu_ly_luu_mau',
        { name: x.name, hanh_dong: hanhDong, ly_do: ta.value.trim() });
      toast(laHuy ? 'Đã ghi huỷ mẫu' : 'Đã ghi lấy mẫu ra');
      m.close();
      render(api);
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

function moLayMau(dl, api) {
  const m = openModal({ kicker: 'Lưu mẫu', title: 'Lấy mẫu mới' });
  const f = { san_pham: '', ten: '', dvt: 'hộp', lo: '', so_luong: 1, vi_tri: '', han_luu: dl.han_mac_dinh };

  // ── sản phẩm: nút gợi ý + ô tìm ─────────────────────────────────────
  m.body.appendChild(el('div', 'sx-field-label', 'Sản phẩm'));
  const daChon = el('div', 'sx-qc-lm-chon');
  const goiY = el('div', 'sx-qc-vi');
  const tim = el('input', 'sx-textarea');
  tim.type = 'search';
  tim.placeholder = 'gõ 2 chữ để tìm…';
  const kq = el('div', 'sx-qc-vi');
  const chonSp = (x) => {
    f.san_pham = x.item; f.ten = x.ten;
    if (x.dvt) { f.dvt = x.dvt; dvt.value = x.dvt; veSl(); }
    veChon();
  };
  const nutSp = (x) => {
    const b = el('button', `sx-qc-vi-o${f.san_pham === x.item ? ' sx-qc-vi-on' : ''}`, esc(x.ten));
    b.type = 'button';
    b.addEventListener('click', () => chonSp(x));
    return b;
  };
  function veChon() {
    daChon.innerHTML = f.san_pham ? `✓ <b>${esc(f.ten)}</b>` : '';
    goiY.innerHTML = '';
    dl.goi_y_sp.forEach((x) => goiY.appendChild(nutSp(x)));
    kq.querySelectorAll('button').forEach((b) => {
      b.classList.toggle('sx-qc-vi-on', b.dataset.item === f.san_pham);
    });
  }
  let hen = null;
  tim.addEventListener('input', () => {
    clearTimeout(hen);
    hen = setTimeout(async () => {
      kq.innerHTML = '';
      if (tim.value.trim().length < 2) return;
      try {
        const ds = await api.call('sx.api.qc.tim_hang', { q: tim.value.trim() });
        if (!ds.length) kq.appendChild(el('div', 'sx-muted', 'Không thấy sản phẩm nào.'));
        ds.forEach((x) => { const b = nutSp(x); b.dataset.item = x.item; kq.appendChild(b); });
      } catch (e) { toastErr(e.message); }
    }, 300);
  });
  m.body.appendChild(daChon);
  m.body.appendChild(goiY);
  m.body.appendChild(tim);
  m.body.appendChild(kq);

  // ── lô, số lượng, vị trí, hạn ───────────────────────────────────────
  m.body.appendChild(el('div', 'sx-field-label', 'Lô / HSD (như in trên bao bì)'));
  const lo = el('input', 'sx-textarea');
  lo.type = 'text';
  lo.placeholder = 'VD: HSD 29/03/2027 hoặc số lô';
  lo.addEventListener('input', () => { f.lo = lo.value; });
  m.body.appendChild(lo);

  const hang = el('div', 'sx-qc-lm-hang');
  const sl = el('button', 'sx-qc-oso-khung', '');
  sl.type = 'button';
  // Kèm đơn vị: ô số chỉ có mỗi con số bị CSS chung coi là ô trống (tô xám).
  const veSl = () => {
    sl.innerHTML = `<span class="sx-qc-oso-val">${f.so_luong}</span>`
      + `<span class="sx-qc-oso-dv">${esc(f.dvt || '')}</span>`;
  };
  veSl();
  sl.addEventListener('click', () => openNumpad({
    kicker: 'Lưu mẫu', title: 'Số lượng mẫu', initial: String(f.so_luong),
    allowDecimal: false, unitLabel: f.dvt || 'SỐ',
    onOk: (n) => { f.so_luong = Math.max(1, Math.round(n)); veSl(); },
  }));
  const dvt = el('input', 'sx-textarea');
  dvt.type = 'text';
  dvt.value = f.dvt;
  dvt.addEventListener('input', () => { f.dvt = dvt.value; veSl(); });
  const o1 = el('div'); o1.appendChild(el('div', 'sx-field-label', 'Số lượng')); o1.appendChild(sl);
  const o2 = el('div'); o2.appendChild(el('div', 'sx-field-label', 'Đơn vị')); o2.appendChild(dvt);
  hang.appendChild(o1); hang.appendChild(o2);
  m.body.appendChild(hang);

  m.body.appendChild(el('div', 'sx-field-label', 'Vị trí lưu'));
  const vt = el('input', 'sx-textarea');
  vt.type = 'text';
  vt.placeholder = 'tủ / kệ / ngăn';
  vt.addEventListener('input', () => { f.vi_tri = vt.value; veVt(); });
  const vtGoiY = el('div', 'sx-qc-vi');
  function veVt() {
    vtGoiY.innerHTML = '';
    dl.goi_y_vi_tri.forEach((v) => {
      const b = el('button', `sx-qc-vi-o${f.vi_tri === v ? ' sx-qc-vi-on' : ''}`, esc(v));
      b.type = 'button';
      b.addEventListener('click', () => { f.vi_tri = v; vt.value = v; veVt(); });
      vtGoiY.appendChild(b);
    });
  }
  veVt();
  m.body.appendChild(vtGoiY);
  m.body.appendChild(vt);

  m.body.appendChild(el('div', 'sx-field-label', `Lưu đến ngày (mặc định ${dl.so_ngay_luu} ngày)`));
  const han = el('input', 'sx-textarea');
  han.type = 'date';
  han.value = f.han_luu;
  han.addEventListener('change', () => { f.han_luu = han.value; });
  m.body.appendChild(han);

  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU MẪU');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!f.san_pham) { toastErr('Chưa chọn sản phẩm.'); return; }
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc.tao_luu_mau', { payload: JSON.stringify(f) });
      toast(`Đã lưu mẫu ${r.name}`);
      m.close();
      st.tab = 'Đang lưu';
      render(api);
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
  veChon();
}
