// #/qc/incidents — sổ sự cố (BM.08.02).
//
// Hai tab Mở / Đóng, và "Mở" là tab mặc định: sổ sự cố tồn tại để mấy cái ĐANG
// MỞ không bị quên. Phiếu quá hạn có viền đỏ và chữ "quá hạn" — không dựa vào
// việc ai đó chịu khó đọc ngày trên từng dòng.
//
// Nút "Đóng" chỉ hiện với Ban ISO / người được giao, nhưng đó chỉ là chuyện đỡ rối
// mắt: chốt thật nằm ở sx/qc/quyen.py (API lẫn controller — cả đường Desk, W11).
//
// W11 (D134): phiếu gắn LÔ LIÊN QUAN (tìm theo tên, HSD hoặc mã lô; lô thành phẩm
// hiện bằng HSD), chọn NGUỒN khi lập tay, cờ DIỄN TẬP (không tính vào số liệu).

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment, tabSuCo } from '/assets/sx/sx/components/qcui.js';

const st = { tab: 'Mở', cong_doan: '', loai: '', dien_tap: false };

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc.list_incidents', { trang_thai: st.tab });
  container.innerHTML = '';
  container.appendChild(tabSuCo('incidents'));

  container.appendChild(segment(
    [{ v: 'Mở', ten: `Đang mở (${dl.danh_sach.filter((x) => x.trang_thai === 'Mở').length})` },
      { v: 'Đóng', ten: 'Đã đóng' }],
    st.tab, (v) => { st.tab = v; render(api); }));

  const loc = el('div', 'sx-qc-chips');
  const nutLoc = (ten, khoa, gt) => {
    const b = el('button', `sx-qc-tag${st[khoa] === gt ? ' sx-qc-tag-chon' : ''}`,
      esc(ten));
    b.type = 'button';
    b.style.cursor = 'pointer';
    b.addEventListener('click', () => { st[khoa] = st[khoa] === gt ? '' : gt; ve(); });
    return b;
  };
  dl.loai.forEach((l) => loc.appendChild(nutLoc(l, 'loai', l)));
  const nutDt = el('button', 'sx-qc-tag', 'Diễn tập');
  nutDt.type = 'button';
  nutDt.style.cursor = 'pointer';
  nutDt.addEventListener('click', () => { st.dien_tap = !st.dien_tap; ve(); });
  loc.appendChild(nutDt);
  container.appendChild(loc);

  const ds = el('div', 'sx-qc-than');
  container.appendChild(ds);

  function ve() {
    loc.querySelectorAll('button').forEach((b) => {
      const chon = b === nutDt ? st.dien_tap : st.loai === b.textContent;
      b.className = `sx-qc-tag${chon ? ' sx-qc-tag-chon' : ''}`;
    });
    ds.innerHTML = '';
    const loc_ds = dl.danh_sach.filter((s) => (!st.loai || s.loai === st.loai)
      && (!st.dien_tap || s.dien_tap));
    if (!loc_ds.length) {
      ds.appendChild(khungTrong(st.tab === 'Mở'
        ? 'Không có sự cố nào đang mở.'
        : 'Chưa có phiếu nào được đóng trong khoảng này.'));
      return;
    }
    loc_ds.forEach((s) => ds.appendChild(veThe(s, dl, api)));
  }
  ve();

  const them = el('button', 'sx-btn sx-btn-ghost sx-btn-big', '+ LẬP PHIẾU SỰ CỐ');
  them.type = 'button';
  them.addEventListener('click', () => moThem(dl, api));
  container.appendChild(them);
}

function veThe(s, dl, api) {
  const the = el('div', `sx-qc-sc sx-qc-sc-${s.trang_thai === 'Mở' ? 'mo' : 'dong'}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', esc(s.mo_ta)));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(s.name));
  if (s.dien_tap) meta.appendChild(chip('DIỄN TẬP', 'dt'));
  meta.appendChild(el('span', null, esc(s.ngay)));
  if (s.nguon && s.nguon !== 'Vòng kiểm QC') meta.appendChild(chip(s.nguon));
  if (s.cong_doan) meta.appendChild(chip(s.cong_doan));
  if (s.loai) {
    meta.appendChild(chip(s.loai === 'oPRP' && s.oprp ? s.oprp : s.loai,
      s.loai === 'oPRP' ? 'oprp' : ''));
  }
  if (s.muc_do === 'Cao') meta.appendChild(chip('mức CAO', 'cao'));
  if (s.qua_han) meta.appendChild(chip('quá hạn', 'han'));
  the.appendChild(meta);
  if ((s.ds_lo || []).length) {
    the.appendChild(el('div', 'sx-qc-goiy sx-sc-lo-dong',
      `Lô: ${s.ds_lo.map((x) => `<b>${esc(x.nhan)}</b> ${esc(x.ten || '')}`).join(' · ')}`));
  }
  if (s.xu_ly_ngay) {
    the.appendChild(el('div', 'sx-qc-goiy', `Xử lý ngay: ${esc(s.xu_ly_ngay)}`));
  } else if (s.trang_thai === 'Mở') {
    the.appendChild(el('div', 'sx-qc-goiy', '⚠ chưa ghi xử lý ngay'));
  }
  const nut = el('div', 'sx-qc-chips');
  const b = el('button', 'sx-btn sx-btn-ghost', 'GHI XỬ LÝ');
  b.type = 'button';
  b.addEventListener('click', () => moChiTiet(s, dl, api));
  nut.appendChild(b);
  the.appendChild(nut);
  return the;
}

function o(body, nhan, gt, kieu) {
  body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
  const n = el(kieu === 'ta' ? 'textarea' : 'input');
  n.className = 'sx-textarea';
  if (kieu === 'ta') n.rows = 2;
  n.value = gt || '';
  body.appendChild(n);
  return n;
}

function chonBox(body, nhan, lua, gt) {
  body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
  const s = el('select', 'sx-textarea');
  ['', ...lua].forEach((x) => {
    const opt = el('option', null, esc(x || '—'));
    opt.value = x;
    if (x === gt) opt.selected = true;
    s.appendChild(opt);
  });
  body.appendChild(s);
  return s;
}

/** Khối "Lô liên quan": lô đã gắn (bỏ được) + ô tìm lô theo tên / HSD / mã lô.
 *  Trả {node, lay: () => [{batch, so_luong}]}. */
function khoiLo(body, api, dau) {
  const ds = (dau || []).map((x) => ({ ...x }));
  body.appendChild(el('div', 'sx-qc-goiy', 'Lô liên quan (thành phẩm theo HSD, nguyên liệu theo mã lô)'));
  const daGan = el('div', 'sx-qc-chips sx-sc-lo');
  const tim = el('input', 'sx-textarea');
  tim.type = 'search';
  tim.placeholder = 'Gõ tên sản phẩm, HSD (05/04/2027) hoặc mã lô…';
  const kq = el('div', 'sx-qc-vi');
  const ve = () => {
    daGan.innerHTML = '';
    if (!ds.length) daGan.appendChild(el('span', 'sx-muted', 'Chưa gắn lô nào.'));
    ds.forEach((x, i) => {
      const c = el('span', 'sx-qc-tag sx-sc-lo-o', `${esc(x.nhan || x.batch)} ${esc(x.ten || '')}`);
      const bo = el('button', 'sx-sc-lo-bo', '✕');
      bo.type = 'button';
      bo.setAttribute('aria-label', `Bỏ lô ${x.nhan || x.batch}`);
      bo.addEventListener('click', () => { ds.splice(i, 1); ve(); });
      c.appendChild(bo);
      daGan.appendChild(c);
    });
  };
  let hen = null;
  tim.addEventListener('input', () => {
    clearTimeout(hen);
    hen = setTimeout(async () => {
      kq.innerHTML = '';
      const q = tim.value.trim();
      if (q.length < 2) return;
      try {
        const r = await api.call('sx.api.qc.tim_lo', { q });
        if (!r.length) kq.appendChild(el('div', 'sx-muted', 'Không thấy lô nào.'));
        r.forEach((x) => {
          const b = el('button', 'sx-qc-vi-o',
            `${esc(x.nhan)} · ${esc(x.ten)}<small> · tồn ${esc(String(x.ton))}</small>`);
          b.type = 'button';
          b.disabled = ds.some((y) => y.batch === x.batch);
          b.addEventListener('click', () => {
            if (!ds.some((y) => y.batch === x.batch)) ds.push(x);
            b.disabled = true;
            ve();
          });
          kq.appendChild(b);
        });
      } catch (e) { toastErr(e.message); }
    }, 300);
  });
  body.appendChild(daGan);
  body.appendChild(tim);
  body.appendChild(kq);
  ve();
  return { lay: () => ds.map((x) => ({ batch: x.batch, so_luong: x.so_luong || '' })) };
}

function oCheck(body, nhan, gt) {
  const nhanEl = el('label', 'sx-sc-check');
  const c = el('input');
  c.type = 'checkbox';
  c.checked = !!gt;
  nhanEl.appendChild(c);
  nhanEl.appendChild(el('span', null, esc(nhan)));
  body.appendChild(nhanEl);
  return c;
}

function moChiTiet(s, dl, api) {
  const m = openModal({ kicker: s.name, title: s.mo_ta || 'Phiếu sự cố' });
  if (s.dien_tap) m.body.appendChild(el('div', 'sx-sc-dt', 'PHIẾU DIỄN TẬP — không tính vào số liệu sự cố'));
  const xl = o(m.body, 'Xử lý ngay (bắt buộc trước khi đóng)', s.xu_ly_ngay, 'ta');
  const kLo = khoiLo(m.body, api, s.ds_lo);
  const lo = o(m.body, 'Ghi chú lô (ngày nghiền, vị…)', s.lo_anh_huong);
  const nn = o(m.body, 'Nguyên nhân', s.nguyen_nhan, 'ta');
  const hd = o(m.body, 'Hành động khắc phục', s.hanh_dong_khac_phuc, 'ta');
  const qd = chonBox(m.body, 'Quyết định với sản phẩm (bắt buộc trước khi đóng)',
    dl.quyet_dinh_sp, s.quyet_dinh_sp);
  // W24 (D150): phiếu hành động khắc phục BM.01.07 là phiếu thật gắn sự cố, không còn là ô số gõ tay.
  khoiKhacPhuc(m, s, api);
  // Cờ diễn tập đổi được sau khi lập: chỉ người được đóng phiếu (controller chặn
  // người khác) — QC đổi được là giấu được một sự cố thật khỏi số liệu.
  const dt = dl.duoc_dong ? oCheck(m.body, 'Phiếu diễn tập (không tính vào số liệu)', s.dien_tap) : null;

  const goi = () => ({
    xu_ly_ngay: xl.value, lo_anh_huong: lo.value, nguyen_nhan: nn.value,
    hanh_dong_khac_phuc: hd.value, quyet_dinh_sp: qd.value,
    ds_lo: kLo.lay(), ...(dt ? { dien_tap: dt.checked ? 1 : 0 } : {}),
  });

  const luu = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU');
  luu.type = 'button';
  luu.addEventListener('click', async () => {
    luu.disabled = true;
    try {
      await api.call('sx.api.qc.update_incident',
        { name: s.name, payload: JSON.stringify(goi()) });
      toast('Đã lưu');
      m.close();
      render(api);
    } catch (e) { luu.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(luu);

  if (dl.duoc_dong && s.trang_thai === 'Mở') {
    const dong = el('button', 'sx-btn sx-btn-warn sx-btn-big', 'ĐÓNG PHIẾU');
    dong.type = 'button';
    dong.addEventListener('click', async () => {
      dong.disabled = true;
      try {
        // Lưu nội dung trước rồi mới đóng: server chặn đóng khi còn thiếu, nên
        // đóng thẳng mà chưa lưu là báo thiếu đúng cái người ta vừa gõ xong.
        await api.call('sx.api.qc.update_incident',
          { name: s.name, payload: JSON.stringify(goi()) });
        await api.call('sx.api.qc.close_incident', { name: s.name, quyet_dinh_sp: qd.value });
        toast('Đã đóng phiếu');
        m.close();
        render(api);
      } catch (e) { dong.disabled = false; toastErr(e.message); }
    });
    m.body.appendChild(dong);
  } else if (!dl.duoc_dong && s.trang_thai === 'Mở') {
    m.body.appendChild(el('div', 'sx-qc-goiy',
      'Đóng phiếu là việc của Trưởng Ban ISO — người ghi không tự duyệt.'));
  }
  return m;
}

/** Khối phiếu khắc phục BM.01.07 trên phiếu sự cố: đã có → trạng thái + nút mở; chưa có → nút lập
 *  (lấy sẵn mô tả / nguyên nhân / hành động đã ghi ở đây). Số CAR gõ tay trước D150 vẫn hiện. */
function khoiKhacPhuc(m, s, api) {
  const { body } = m;
  const kp = s.khac_phuc;
  body.appendChild(el('div', 'sx-qc-goiy', 'Hành động khắc phục BM.01.07 (xoá nguyên nhân để không lặp lại)'));
  if (kp) {
    body.appendChild(el('div', 'sx-qc-goiy', `<b>${esc(kp.name)}</b> · ${esc(kp.trang_thai)}${
      kp.han ? ` · hạn ${esc(kp.han.slice(8, 10))}/${esc(kp.han.slice(5, 7))}` : ''}`));
  } else if (s.car_so) {
    body.appendChild(el('div', 'sx-qc-goiy', `Số CAR ghi tay: ${esc(s.car_so)}`));
  }
  const b = el('button', 'sx-btn sx-btn-ghost', kp ? 'MỞ PHIẾU KHẮC PHỤC' : '+ LẬP PHIẾU KHẮC PHỤC');
  b.type = 'button';
  b.addEventListener('click', async () => {
    b.disabled = true;
    try {
      const r = kp ? { name: kp.name } : await api.call('sx.api.qc_khacphuc.lap', { payload: JSON.stringify({ su_co: s.name }) });
      m.close();
      window.location.hash = `#/qc/khacphuc?mo=${encodeURIComponent(r.name)}`;
    } catch (e) { b.disabled = false; toastErr(e.message); }
  });
  body.appendChild(b);
}

function moThem(dl, api) {
  const m = openModal({ kicker: 'PHIẾU SỰ CỐ BM.08.02', title: 'Lập phiếu sự cố' });
  const mo = o(m.body, 'Mô tả (bắt buộc)', '', 'ta');
  const nguon = chonBox(m.body, 'Nguồn phát hiện', dl.nguon_tay || ['Phát hiện khác'], 'Phát hiện khác');
  const cd = chonBox(m.body, 'Công đoạn', dl.cong_doan, '');
  const loai = chonBox(m.body, 'Loại', dl.loai, 'Khác');
  const mucdo = chonBox(m.body, 'Mức độ', ['Thường', 'Cao'], 'Thường');
  const kLo = khoiLo(m.body, api, []);
  const lo = o(m.body, 'Ghi chú lô (ngày nghiền, vị…)', '');
  const xl = o(m.body, 'Xử lý ngay', '', 'ta');
  const dt = oCheck(m.body, 'Phiếu DIỄN TẬP (truy xuất, thu hồi, ứng phó — không tính vào số liệu)', false);
  const luu = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LẬP PHIẾU');
  luu.type = 'button';
  luu.addEventListener('click', async () => {
    if (!mo.value.trim()) { toastErr('Chưa ghi mô tả.'); return; }
    luu.disabled = true;
    try {
      await api.call('sx.api.qc.add_incident', {
        payload: JSON.stringify({
          mo_ta: mo.value, nguon: nguon.value || 'Phát hiện khác', cong_doan: cd.value,
          loai: loai.value, muc_do: mucdo.value, lo_anh_huong: lo.value, xu_ly_ngay: xl.value,
          ds_lo: kLo.lay(), dien_tap: dt.checked ? 1 : 0,
        }),
      });
      toast('Đã lập phiếu');
      m.close();
      render(api);
    } catch (e) { luu.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(luu);
}
