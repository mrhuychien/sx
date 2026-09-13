// #/qc/incidents — sổ sự cố (BM.08.02).
//
// Hai tab Mở / Đóng, và "Mở" là tab mặc định: sổ sự cố tồn tại để mấy cái ĐANG
// MỞ không bị quên. Phiếu quá hạn có viền đỏ và chữ "quá hạn" — không dựa vào
// việc ai đó chịu khó đọc ngày trên từng dòng.
//
// Nút "Đóng" chỉ hiện với Ban ISO, nhưng đó chỉ là chuyện đỡ rối mắt: chốt thật
// nằm ở _guard_manager trong sx/api/qc.py.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment } from '/assets/sx/sx/components/qcui.js';

const st = { tab: 'Mở', cong_doan: '', loai: '' };

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc.list_incidents', { trang_thai: st.tab });
  container.innerHTML = '';

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
  container.appendChild(loc);

  const ds = el('div', 'sx-qc-than');
  container.appendChild(ds);

  function ve() {
    loc.querySelectorAll('button').forEach((b) => {
      b.className = `sx-qc-tag${st.loai === b.textContent ? ' sx-qc-tag-chon' : ''}`;
    });
    ds.innerHTML = '';
    const loc_ds = dl.danh_sach.filter((s) => !st.loai || s.loai === st.loai);
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
  meta.appendChild(el('span', null, esc(`${s.ngay}${s.ca ? ` · ${s.ca}` : ''}`)));
  if (s.cong_doan) meta.appendChild(chip(s.cong_doan));
  if (s.loai) meta.appendChild(chip(s.loai, s.loai === 'oPRP' ? 'oprp' : ''));
  if (s.muc_do === 'Cao') meta.appendChild(chip('mức CAO', 'cao'));
  if (s.qua_han) meta.appendChild(chip('quá hạn', 'han'));
  the.appendChild(meta);
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

function moChiTiet(s, dl, api) {
  const m = openModal({ kicker: s.name, title: s.mo_ta || 'Phiếu sự cố' });
  const xl = o(m.body, 'Xử lý ngay (bắt buộc trước khi đóng)', s.xu_ly_ngay, 'ta');
  const lo = o(m.body, 'Lô ảnh hưởng', s.lo_anh_huong);
  const nn = o(m.body, 'Nguyên nhân', s.nguyen_nhan, 'ta');
  const hd = o(m.body, 'Hành động khắc phục', s.hanh_dong_khac_phuc, 'ta');
  const qd = chonBox(m.body, 'Quyết định với sản phẩm (bắt buộc trước khi đóng)',
    dl.quyet_dinh_sp, s.quyet_dinh_sp);
  const car = o(m.body, 'Số CAR (BM.01.07)', s.car_so);

  const goi = () => ({
    xu_ly_ngay: xl.value, lo_anh_huong: lo.value, nguyen_nhan: nn.value,
    hanh_dong_khac_phuc: hd.value, quyet_dinh_sp: qd.value, car_so: car.value,
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
        await api.call('sx.api.qc.close_incident',
          { name: s.name, quyet_dinh_sp: qd.value, car_so: car.value });
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

function moThem(dl, api) {
  const m = openModal({ kicker: 'PHÁT HIỆN KHÁC', title: 'Lập phiếu sự cố' });
  const mo = o(m.body, 'Mô tả (bắt buộc)', '', 'ta');
  const cd = chonBox(m.body, 'Công đoạn', dl.cong_doan, '');
  const loai = chonBox(m.body, 'Loại', dl.loai, 'Khác');
  const mucdo = chonBox(m.body, 'Mức độ', ['Thường', 'Cao'], 'Thường');
  const lo = o(m.body, 'Lô ảnh hưởng', '');
  const xl = o(m.body, 'Xử lý ngay', '', 'ta');
  const luu = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LẬP PHIẾU');
  luu.type = 'button';
  luu.addEventListener('click', async () => {
    if (!mo.value.trim()) { toastErr('Chưa ghi mô tả.'); return; }
    luu.disabled = true;
    try {
      await api.call('sx.api.qc.add_incident', {
        payload: JSON.stringify({
          mo_ta: mo.value, cong_doan: cd.value, loai: loai.value,
          muc_do: mucdo.value, lo_anh_huong: lo.value, xu_ly_ngay: xl.value,
        }),
      });
      toast('Đã lập phiếu');
      m.close();
      render(api);
    } catch (e) { luu.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(luu);
}
