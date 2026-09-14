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
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

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

/** Dòng phụ NGẮN cho ô mực của bàn số. Phải ngắn: nó nằm cạnh con số trong một
 *  ô hẹp, câu dài thì vỡ layout hoặc bị cắt giữa chừng. Câu đầy đủ vẫn ở dưới ô
 *  nhập trên màn chính. */
function goiYNgan(f, v, ng) {
  const g = ng || {};
  const tt = trangThaiSo(f, v, ng);
  if (f === 'rang_nhiet_do') {
    if (tt === 'loi') return `✕ < ${g.rang_nhiet_min ?? 255}`;
    if (tt === 'canh') return `⚠ > ${g.rang_nhiet_max_van_hanh ?? 270}`;
    return `≥ ${g.rang_nhiet_min ?? 255} °C`;
  }
  if (f === 'rang_vong_quay') {
    const kh = `${g.vong_quay_min ?? 6.2}–${g.vong_quay_max ?? 7}`;
    return tt === 'loi' ? `✕ ngoài ${kh}` : kh;
  }
  if (f === 'thung_bot_qua_han') return tt === 'loi' ? '✕ > 0' : '0 = đạt';
  if (f === 't2_so_bay_dau_hieu') return tt === 'canh' ? '⚠ có dấu hiệu' : '/ 12 trạm';
  if (f === 'b2_rang_lac_nhiet') {
    return g.rang_lac_nhiet_min ? `≥ ${g.rang_lac_nhiet_min} °C` : 'chưa có ngưỡng';
  }
  if (f === 'b2_rang_lac_phut') {
    return g.rang_lac_phut_min ? `≥ ${g.rang_lac_phut_min} phút` : 'chưa có ngưỡng';
  }
  return '';
}

/** Ô số.
 *
 * Bấm vào con số là mở BÀN SỐ TO của app, không dùng bàn phím hệ thống. Lý do
 * giống mọi chỗ nhập số khác trong app: QC đeo găng, đứng cạnh máy rang, và bàn
 * phím hệ thống trên điện thoại che mất hai phần ba màn hình đúng lúc cần nhìn
 * lại con số vừa gõ. Bàn số của app hiện con số trên nền mực kèm ngưỡng ngay
 * bên cạnh, nên sai một chữ số là thấy ngay trước khi bấm LƯU.
 *
 * Ô ĐẾM (thùng quá hạn, trạm bẫy) giữ thêm nút − / +: đếm mấy thùng giữa kho
 * thì bấm nhanh hơn mở bàn số.
 */
export function oSo(m, giaTri, onSet, ng, khoa) {
  const dem = m.f === 'thung_bot_qua_han' || m.f === 't2_so_bay_dau_hieu';
  const thap = m.kieu === 'so';
  const wrap = el('div', 'sx-qc-oso');
  wrap.dataset.f = m.f;
  wrap.appendChild(el('div', 'sx-qc-nhan', nhan(m, false)));

  // 0 ở ô ĐO nghĩa là "chưa đo" nên hiện dấu —, còn 0 ở ô ĐẾM là số thật.
  let v = (giaTri === null || giaTri === undefined || giaTri === '') ? ''
    : String(giaTri);
  if (!dem && Number(v) === 0) v = '';

  const box = el('button', 'sx-qc-oso-khung');
  box.type = 'button';
  box.disabled = !!khoa;
  const goiy = el('div', 'sx-qc-goiy', esc(m.goi_y || ''));

  const ve = () => {
    box.innerHTML = `<span class="sx-qc-oso-val${v === '' ? ' sx-qc-trong-so' : ''}">`
      + `${esc(v === '' ? '—' : v)}</span>`
      + (m.dv ? `<span class="sx-qc-oso-dv">${esc(m.dv)}</span>` : '');
    box.setAttribute('aria-label',
      `${m.so} ${m.ngan || m.nhan}: ${v === '' ? 'chưa ghi' : v} ${m.dv || ''}`.trim());
    const tt = trangThaiSo(m.f, v, ng);
    wrap.classList.toggle('sx-qc-oso-loi', tt === 'loi');
    wrap.classList.toggle('sx-qc-oso-canh', tt === 'canh');
    goiy.textContent = tt ? loiSo(m.f, v, ng) : (m.goi_y || '');
  };

  const dat = (moi) => {
    v = moi;
    ve();
    onSet(m.f, v);
  };

  box.addEventListener('click', () => openNumpad({
    kicker: m.so,
    title: m.ngan || m.nhan,
    initial: v,
    allowDecimal: thap,
    unitLabel: m.dv || 'SỐ',
    // Ngưỡng hiện NGAY CẠNH con số đang gõ: thấy 248 đỏ lúc còn đứng ở máy thì
    // còn kịp đi xem lại, chứ không phải biết sau khi đã bấm Hoàn tất lượt.
    hint: (n) => goiYNgan(m.f, n, ng),
    onOk: (n) => dat(thap ? String(n) : String(Math.round(n))),
  }));

  if (dem) {
    const hang = el('div', 'sx-qc-dem');
    const nut = (ky, buoc) => {
      const b = el('button', null, ky);
      b.type = 'button';
      b.disabled = !!khoa;
      b.addEventListener('click', () => dat(String(Math.max(0, (Number(v) || 0) + buoc))));
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
  ve();
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

/** Hộp nhắc việc — dùng chung cho màn QC, màn Xem xét và card trên Quản lý.
 *
 * Mức "cao" viền đỏ, mức thường viền vàng. Không có mục nào thì KHÔNG vẽ gì
 * cả: một hộp "không có việc gì" chiếm chỗ mỗi ngày sẽ dạy mắt bỏ qua đúng
 * vùng màn hình đó, và hôm có việc thật thì nó cũng bị bỏ qua nốt. */
export function veNhac(ds, opts = {}) {
  if (!ds || !ds.length) return null;
  const box = el('div', 'sx-qc-nhac');
  if (opts.tieu_de) box.appendChild(el('div', 'sx-qc-sc-ten', esc(opts.tieu_de)));
  ds.forEach((x) => {
    const a = el('a', `sx-qc-nhac-o sx-qc-nhac-${x.muc_do === 'cao' ? 'cao' : 'thuong'}`);
    a.href = x.route || '#/qc';
    a.innerHTML = `<div class="sx-qc-nhac-ten">${esc(x.tieu_de)}</div>
      <div class="sx-qc-nhac-ct">${esc(x.chi_tiet)}</div>`;
    box.appendChild(a);
  });
  return box;
}
