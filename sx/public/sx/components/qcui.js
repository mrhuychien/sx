// Ô nhập của màn QC: một mục kiểm → một hàng trên màn hình.
//
// Server gửi xuống danh mục mục kiểm (sx/qc/muc.py) nên file này KHÔNG biết
// trước mục nào tồn tại — thêm mục trên bản giấy chỉ phải sửa muc.py, không sửa
// JS. Đổi lại, mọi thứ ở đây phải chạy được với một mục chưa từng thấy.
//
// Màu cảnh báo ở đây là XEM TRƯỚC, không phải phán quyết: server mới là chỗ
// quyết cái gì thành sự cố (sx/qc/su_co.py). Hiện màu sớm để QC còn kịp đi xem
// lại máy, chứ không phải hoàn tất xong mới biết.

import { el, esc } from '/assets/sx/sx/lib/dom.js';

export const DAT = 'Đạt';
export const KHONG_DAT = 'Không đạt';

/** Trạng thái hiển thị của một ô số: '' | 'canh' | 'loi'. */
export function trangThaiSo(f, v, ng) {
  const n = Number(v);
  if (v === '' || v === null || v === undefined || Number.isNaN(n)) return '';
  const g = ng || {};
  if (f === 'rang_nhiet_do') {
    if (n === 0) return '';                       // 0 = chưa đo, không phải 0 °C
    if (n < (g.rang_nhiet_min ?? 255)) return 'loi';
    return n > (g.rang_nhiet_max_van_hanh ?? 270) ? 'canh' : '';
  }
  if (f === 'rang_vong_quay') {
    if (n === 0) return '';
    return (n < (g.vong_quay_min ?? 6.2) || n > (g.vong_quay_max ?? 7)) ? 'loi' : '';
  }
  if (f === 'thung_bot_qua_han') return n > (g.thung_bot_max ?? 0) ? 'loi' : '';
  if (f === 't2_so_bay_dau_hieu') return n > 0 ? 'canh' : '';
  if (f === 'b2_rang_lac_nhiet') {
    return (g.rang_lac_nhiet_min && n < g.rang_lac_nhiet_min) ? 'loi' : '';
  }
  if (f === 'b2_rang_lac_phut') {
    return (g.rang_lac_phut_min && n < g.rang_lac_phut_min) ? 'loi' : '';
  }
  return '';
}

/** Nhãn một mục. `kemGoiY = false` cho các ô có dòng gợi ý RIÊNG bên dưới ô
 *  nhập — in hai lần cùng một câu thì người đọc phải dừng lại xem hai câu đó có
 *  khác nhau không, mà chúng thì không. */
function nhan(m, kemGoiY = true) {
  const goiy = [kemGoiY ? m.goi_y : '', m.goi ? 'QC đóng gói ghi' : '']
    .filter(Boolean).join(' · ');
  // Nhãn NGẮN trên điện thoại; tờ in A4 vẫn dùng nhãn đầy đủ (sx/qc/muc.py).
  return `<span class="sx-qc-so">${esc(m.so)}</span>
    <div><div class="sx-qc-ten">${esc(m.ngan || m.nhan)}</div>
      ${goiy ? `<div class="sx-qc-goiy">${esc(goiy)}</div>` : ''}</div>`;
}

/** Câu báo cho ô số ngoài ngưỡng. Nói ĐÚNG cái sai, không đọc lại dòng ngưỡng:
 *  QC đang đứng cạnh máy rang, họ cần biết "thấp hơn 255" chứ không cần nghe
 *  lại khoảng cho phép. */
function loiSo(f, v, ng) {
  const n = Number(v);
  const g = ng || {};
  if (f === 'rang_nhiet_do') {
    return n < (g.rang_nhiet_min ?? 255)
      ? `✕ ${n} °C — thấp hơn ${g.rang_nhiet_min ?? 255} °C, sẽ tạo sự cố`
      : `⚠ ${n} °C — vượt trần vận hành ${g.rang_nhiet_max_van_hanh ?? 270} °C, báo tổ trưởng`;
  }
  if (f === 'rang_vong_quay') {
    return `✕ ${n} — ngoài khoảng ${g.vong_quay_min ?? 6.2}–${g.vong_quay_max ?? 7}, sẽ tạo sự cố`;
  }
  if (f === 'thung_bot_qua_han') return `✕ ${n} thùng quá hạn — sẽ tạo sự cố`;
  if (f === 't2_so_bay_dau_hieu') return `⚠ ${n} trạm có dấu hiệu — theo dõi tuần sau`;
  return '✕ ngoài ngưỡng — sẽ tạo sự cố khi hoàn tất';
}

/** Hàng Đạt / Không đạt. Bấm lại đúng nút đang chọn = bỏ về TRỐNG.
 *
 * Bỏ về trống phải làm được: chấm nhầm mà không gỡ ra được thì người ta để
 * nguyên cho xong, và từ đó tờ phiếu bắt đầu nói dối. */
export function hangChon(m, giaTri, onSet, khoa) {
  const row = el('div', 'sx-qc-hang');
  row.dataset.f = m.f;
  row.innerHTML = `<div class="sx-qc-nhan">${nhan(m)}</div>
    <span class="sx-qc-trong"></span>
    <div class="sx-qc-nut2">
      <button type="button" data-v="${esc(DAT)}">✓ Đạt</button>
      <button type="button" data-v="${esc(KHONG_DAT)}">✕ Không</button>
    </div>`;
  const ve = (v) => {
    row.dataset.tt = v || '';
    row.querySelector('.sx-qc-trong').textContent = v ? '' : '—';
    const [a, b] = row.querySelectorAll('.sx-qc-nut2 button');
    a.classList.toggle('sx-qc-dat-on', v === DAT);
    b.classList.toggle('sx-qc-khong-on', v === KHONG_DAT);
  };
  ve(giaTri || '');
  row.querySelectorAll('.sx-qc-nut2 button').forEach((b) => {
    if (khoa) { b.disabled = true; return; }
    b.addEventListener('click', () => {
      const dang = row.dataset.tt || '';
      const moi = dang === b.dataset.v ? '' : b.dataset.v;
      ve(moi);
      onSet(m.f, moi);
    });
  });
  return row;
}

function khungSo(m, giaTri, onSet, ng, khoa, thap) {
  const box = el('div', 'sx-qc-oso-khung');
  const inp = el('input');
  inp.type = 'text';
  inp.inputMode = thap ? 'decimal' : 'numeric';
  inp.value = (giaTri === 0 || giaTri === '0') && !m.dem ? '' : (giaTri ?? '');
  inp.placeholder = '—';
  inp.disabled = !!khoa;
  box.appendChild(inp);
  if (m.dv) box.appendChild(el('span', 'sx-qc-oso-dv', esc(m.dv)));
  return { box, inp, ng };
}

/** Ô số. Ô ĐẾM có nút − / + (đếm thùng giữa kho thì bấm nhanh hơn gõ);
 *  ô ĐO chỉ có bàn phím số. */
export function oSo(m, giaTri, onSet, ng, khoa) {
  const dem = m.f === 'thung_bot_qua_han' || m.f === 't2_so_bay_dau_hieu';
  const wrap = el('div', 'sx-qc-oso');
  wrap.dataset.f = m.f;
  wrap.appendChild(el('div', 'sx-qc-nhan', nhan(m, false)));
  const { box, inp } = khungSo({ ...m, dem }, giaTri, onSet, ng, khoa,
    m.kieu === 'so');
  const goiy = el('div', 'sx-qc-goiy', esc(m.goi_y || ''));

  const capNhat = () => {
    const tt = trangThaiSo(m.f, inp.value, ng);
    wrap.classList.toggle('sx-qc-oso-loi', tt === 'loi');
    wrap.classList.toggle('sx-qc-oso-canh', tt === 'canh');
    goiy.textContent = tt ? loiSo(m.f, inp.value, ng) : (m.goi_y || '');
  };
  inp.addEventListener('input', () => { capNhat(); onSet(m.f, inp.value); });

  if (dem) {
    const hang = el('div', 'sx-qc-dem');
    const nut = (ky, buoc) => {
      const b = el('button', null, ky);
      b.type = 'button';
      b.disabled = !!khoa;
      b.addEventListener('click', () => {
        inp.value = String(Math.max(0, (Number(inp.value) || 0) + buoc));
        capNhat();
        onSet(m.f, inp.value);
      });
      return b;
    };
    hang.appendChild(nut('−', -1));
    hang.appendChild(box);
    hang.appendChild(nut('+', 1));
    wrap.appendChild(hang);
  } else {
    wrap.appendChild(box);
  }
  wrap.appendChild(goiy);
  capNhat();
  return wrap;
}

export function oChu(m, giaTri, onSet, khoa) {
  const wrap = el('div', 'sx-qc-oso');
  wrap.dataset.f = m.f;
  wrap.appendChild(el('div', 'sx-qc-nhan', nhan(m, false)));
  const box = el('div', 'sx-qc-oso-khung');
  const inp = el('input');
  inp.type = 'text';
  inp.value = giaTri || '';
  inp.placeholder = m.goi_y || '';
  inp.disabled = !!khoa;
  inp.style.fontSize = 'var(--sx-f-md)';
  inp.addEventListener('input', () => onSet(m.f, inp.value));
  box.appendChild(inp);
  wrap.appendChild(box);
  return wrap;
}

export function oGio(m, giaTri, onSet, khoa) {
  const wrap = el('div', 'sx-qc-oso');
  wrap.dataset.f = m.f;
  wrap.appendChild(el('div', 'sx-qc-nhan', nhan(m, false)));
  const box = el('div', 'sx-qc-oso-khung');
  const inp = el('input');
  inp.type = 'time';
  inp.value = String(giaTri || '').slice(0, 5);
  inp.disabled = !!khoa;
  inp.style.fontSize = 'var(--sx-f-md)';
  inp.addEventListener('change', () => onSet(m.f, inp.value));
  box.appendChild(inp);
  wrap.appendChild(box);
  return wrap;
}

export function oCheck(m, giaTri, onSet, khoa) {
  const row = el('div', 'sx-qc-hang');
  row.dataset.f = m.f;
  row.innerHTML = `<div class="sx-qc-nhan">${nhan(m)}</div>
    <div class="sx-qc-nut2"><button type="button">☐ Không</button></div>`;
  const b = row.querySelector('button');
  let v = Number(giaTri) ? 1 : 0;
  const ve = () => {
    b.textContent = v ? '☑ Có' : '☐ Không';
    b.classList.toggle('sx-qc-khong-on', !!v);
  };
  ve();
  b.disabled = !!khoa;
  b.addEventListener('click', () => { v = v ? 0 : 1; ve(); onSet(m.f, v); });
  return row;
}

/** Segmented control. Dùng cho ca Sáng/Chiều, tab, và B7 ba trạng thái. */
export function segment(lua, dang, onSet, khoa, boDuoc = false) {
  const box = el('div', 'sx-qc-seg');
  let hien = dang;
  lua.forEach((x) => {
    const gt = typeof x === 'string' ? x : x.v;
    const ten = typeof x === 'string' ? x : x.ten;
    const b = el('button', null, esc(ten));
    b.type = 'button';
    b.classList.toggle('sx-qc-seg-on', gt === dang);
    b.disabled = !!khoa;
    b.addEventListener('click', () => {
      // Bấm lại nút đang chọn = bỏ về TRỐNG. Chấm nhầm mà không gỡ ra được thì
      // người ta để nguyên cho xong, và từ đó tờ phiếu bắt đầu nói dối.
      const moi = (boDuoc && hien === gt) ? '' : gt;
      hien = moi;
      box.querySelectorAll('button').forEach((o) => o.classList.remove('sx-qc-seg-on'));
      if (moi) b.classList.add('sx-qc-seg-on');
      onSet(moi);
    });
    box.appendChild(b);
  });
  return box;
}

export function oChon3(m, giaTri, onSet, lua, khoa) {
  const wrap = el('div', 'sx-qc-oso');
  wrap.dataset.f = m.f;
  wrap.appendChild(el('div', 'sx-qc-nhan', nhan(m, false)));
  wrap.appendChild(segment(lua, giaTri || '', (v) => onSet(m.f, v), khoa, true));
  if (m.goi_y) wrap.appendChild(el('div', 'sx-qc-goiy', esc(m.goi_y)));
  return wrap;
}

export function tieuDeBuoc(b, da, tong) {
  const h = el('div', 'sx-qc-buoc');
  h.innerHTML = `<span class="sx-qc-buoc-ma">${esc(b.ma)}</span>
    <span class="sx-qc-buoc-ten">${esc(b.ten)}</span>
    ${b.oprp ? `<span class="sx-qc-tag sx-qc-tag-oprp">${esc(b.oprp)}</span>` : ''}
    ${b.ghi ? `<span class="sx-qc-tag">${esc(b.ghi)}</span>` : ''}
    <span class="sx-qc-buoc-dem">${da}/${tong}</span>`;
  return h;
}

export function chip(text, kieu) {
  return el('span', `sx-qc-tag${kieu ? ` sx-qc-tag-${kieu}` : ''}`, esc(text));
}

export function khungTrong(text) {
  return el('div', 'sx-qc-trong-box', esc(text));
}
