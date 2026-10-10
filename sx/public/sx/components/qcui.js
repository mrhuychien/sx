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
import { confirm2Step } from '/assets/sx/sx/components/modal.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';

export const DAT = 'Đạt';
export const KHONG_DAT = 'Không đạt';

/** Trạng thái hiển thị của một ô số: '' | 'canh' | 'loi'. */
export function trangThaiSo(f, v, ng) {
  const n = Number(v);
  if (v === '' || v === null || v === undefined || Number.isNaN(n)) return '';
  const g = ng || {};
  if (f === 'rang_nhiet_do') {
    if (n === 0) return '';                       // 0 = chưa đo, không phải 0 °C
    if (n < (g.rang_nhiet_min ?? 240)) return 'loi';
    return n > (g.rang_nhiet_max_van_hanh ?? 280) ? 'canh' : '';
  }
  if (f === 'rang_vong_quay') {
    if (n === 0) return '';
    return (n < (g.vong_quay_min ?? 6.2) || n > (g.vong_quay_max ?? 7)) ? 'loi' : '';
  }
  if (f === 'thung_bot_qua_han') return n > (g.thung_bot_max ?? 0) ? 'loi' : '';
  if (f === 't2_so_bay_dau_hieu') return n > 0 ? 'canh' : '';
  // W03 (D128): rang lạc có cả trần — quá nhiệt / quá giờ là cháy, cũng lệch oPRP.
  if (f === 'b2_rang_lac_nhiet' || f === 'b2_rang_lac_phut') {
    if (n === 0) return '';
    const k = f === 'b2_rang_lac_nhiet' ? 'rang_lac_nhiet' : 'rang_lac_phut';
    return ((g[`${k}_min`] && n < g[`${k}_min`])
      || (g[`${k}_max`] && n > g[`${k}_max`])) ? 'loi' : '';
  }
  // W02 (D129): hạt thô trên rây — có ngưỡng thì vượt là lỗi, chưa có thì > 0 cảnh báo.
  if (f === 'hat_tho') {
    if (g.hat_tho_toi_da !== null && g.hat_tho_toi_da !== undefined) {
      return n > g.hat_tho_toi_da ? 'loi' : '';
    }
    return n > 0 ? 'canh' : '';
  }
  if (f === 'b8_nhiet_han') {
    if (n === 0) return '';
    return ((g.han_nhiet_min && n < g.han_nhiet_min)
      || (g.han_nhiet_max && n > g.han_nhiet_max)) ? 'loi' : '';
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
 *  QC đang đứng cạnh máy rang, họ cần biết "thấp hơn 240" chứ không cần nghe
 *  lại khoảng cho phép. */
function loiSo(f, v, ng) {
  const n = Number(v);
  const g = ng || {};
  if (f === 'rang_nhiet_do') {
    return n < (g.rang_nhiet_min ?? 240)
      ? `✕ ${n} °C — thấp hơn ${g.rang_nhiet_min ?? 240} °C, sẽ tạo sự cố`
      : `⚠ ${n} °C — vượt trần vận hành ${g.rang_nhiet_max_van_hanh ?? 280} °C, báo tổ trưởng`;
  }
  if (f === 'rang_vong_quay') {
    return `✕ ${n} — ngoài khoảng ${g.vong_quay_min ?? 6.2}–${g.vong_quay_max ?? 7}, sẽ tạo sự cố`;
  }
  if (f === 'thung_bot_qua_han') return `✕ ${n} thùng quá hạn — sẽ tạo sự cố`;
  if (f === 't2_so_bay_dau_hieu') return `⚠ ${n} trạm có dấu hiệu — theo dõi tuần sau`;
  if (f === 'hat_tho') {
    return (g.hat_tho_toi_da !== null && g.hat_tho_toi_da !== undefined)
      ? `✕ ${n} hạt thô — vượt ${g.hat_tho_toi_da}, sẽ tạo sự cố`
      : `⚠ ${n} hạt thô — chưa có ngưỡng, báo tổ trưởng xem lưới rây`;
  }
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

/** T4 theo vật (W44, D173): giá trị mục T4 từ các vật đã tích — có vật Không đạt → Không đạt; mọi vật Đạt → Đạt;
 *  còn vật chưa tích → '' (chưa chấm). Bản sao client của sx/qc/so.t4_theo_vat — server tính lại khi lưu. */
export function t4TheoVat(ds) {
  if (ds.some((x) => x.ket_qua === KHONG_DAT)) return KHONG_DAT;
  if (ds.length && ds.every((x) => x.ket_qua === DAT)) return DAT;
  return '';
}

/** Mục T4 "Đèn, kính có bảo vệ" khi danh mục kính, nhựa giòn BM.PRP.05 có vật: mỗi vật một hàng ✓ Đạt / ✕ Không
 *  (bấm lại nút đang chọn = bỏ trống); Không đạt thì ô ghi chú (vỡ, mất chụp…). `vk` = {so, ds: [{vat, ma, ten,
 *  ket_qua, ghi_chu}]}; `onSetVat(x)` gọi sau mỗi lần đổi một vật. */
export function oVatKinh(m, vk, onSetVat, khoa) {
  const wrap = el('div', 'sx-qc-vat');
  wrap.dataset.f = m.f;
  const dau = el('div', 'sx-qc-hang');
  dau.appendChild(el('div', 'sx-qc-nhan', nhan(m, false)));
  const tt = el('span', 'sx-qc-vat-tt');
  dau.appendChild(tt);
  wrap.appendChild(dau);
  wrap.appendChild(el('div', 'sx-qc-goiy sx-qc-vat-hd', esc(`Theo danh mục ${vk.so}: tích từng vật. Có vật Không đạt `
    + '→ T4 Không đạt, mỗi vật một phiếu sự cố.')));
  const veTong = () => {
    const v = t4TheoVat(vk.ds);
    const con = vk.ds.filter((x) => !x.ket_qua).length;
    tt.textContent = v === KHONG_DAT ? '✕ Không đạt' : (v === DAT ? '✓ Đạt' : `còn ${con} vật`);
    tt.className = `sx-qc-vat-tt${v === KHONG_DAT ? ' sx-qc-vat-k' : (v === DAT ? ' sx-qc-vat-d' : '')}`;
    wrap.dataset.tt = v;
  };
  vk.ds.forEach((x) => {
    const row = el('div', 'sx-qc-hang sx-qc-vat-hang');
    row.appendChild(el('div', 'sx-qc-nhan', `<div class="sx-qc-ten">${esc([x.ma, x.ten].filter(Boolean).join(' · ')
      || x.vat)}</div>`));
    const nut2 = el('div', 'sx-qc-nut2');
    const a = el('button', null, '✓ Đạt');
    const b = el('button', null, '✕ Không');
    nut2.appendChild(a);
    nut2.appendChild(b);
    row.appendChild(nut2);
    const gc = el('input', 'sx-textarea sx-qc-vat-gc');
    gc.type = 'text';
    gc.maxLength = 140;
    gc.placeholder = 'Không đạt vì… (vỡ, nứt, mất chụp)';
    gc.value = x.ghi_chu || '';
    gc.disabled = !!khoa;
    const ve = () => {
      row.dataset.tt = x.ket_qua || '';
      a.classList.toggle('sx-qc-dat-on', x.ket_qua === DAT);
      b.classList.toggle('sx-qc-khong-on', x.ket_qua === KHONG_DAT);
      gc.style.display = x.ket_qua === KHONG_DAT ? '' : 'none';
      veTong();
    };
    [[a, DAT], [b, KHONG_DAT]].forEach(([n, gt]) => {
      n.type = 'button';
      n.disabled = !!khoa;
      n.addEventListener('click', () => {
        x.ket_qua = x.ket_qua === gt ? '' : gt;
        if (x.ket_qua !== KHONG_DAT) { x.ghi_chu = ''; gc.value = ''; }
        ve();
        onSetVat(x);
      });
    });
    gc.addEventListener('change', () => { x.ghi_chu = gc.value.trim(); onSetVat(x); });
    wrap.appendChild(row);
    wrap.appendChild(gc);
    ve();
  });
  veTong();
  return wrap;
}

/** Dòng phụ NGẮN cho ô mực của bàn số. Phải ngắn: nó nằm cạnh con số trong một
 *  ô hẹp, câu dài thì vỡ layout hoặc bị cắt giữa chừng. Câu đầy đủ vẫn ở dưới ô
 *  nhập trên màn chính. */
function goiYNgan(f, v, ng) {
  const g = ng || {};
  const tt = trangThaiSo(f, v, ng);
  if (f === 'rang_nhiet_do') {
    if (tt === 'loi') return `✕ < ${g.rang_nhiet_min ?? 240}`;
    if (tt === 'canh') return `⚠ > ${g.rang_nhiet_max_van_hanh ?? 280}`;
    return `≥ ${g.rang_nhiet_min ?? 240} °C`;
  }
  if (f === 'rang_vong_quay') {
    const kh = `${g.vong_quay_min ?? 6.2}–${g.vong_quay_max ?? 7}`;
    return tt === 'loi' ? `✕ ngoài ${kh}` : kh;
  }
  if (f === 'thung_bot_qua_han') return tt === 'loi' ? '✕ > 0' : '0 = đạt';
  if (f === 't2_so_bay_dau_hieu') return tt === 'canh' ? '⚠ có dấu hiệu' : '/ 12 trạm';
  if (f === 'b2_rang_lac_nhiet' || f === 'b2_rang_lac_phut') {
    const k = f === 'b2_rang_lac_nhiet' ? 'rang_lac_nhiet' : 'rang_lac_phut';
    const dv = f === 'b2_rang_lac_nhiet' ? '°C' : 'phút';
    const kh = `${g[`${k}_min`] ?? '…'}–${g[`${k}_max`] ?? '…'} ${dv}`;
    return tt === 'loi' ? `✕ ngoài ${kh}` : kh;
  }
  if (f === 'hat_tho') {
    if (g.hat_tho_toi_da !== null && g.hat_tho_toi_da !== undefined) {
      return tt === 'loi' ? `✕ > ${g.hat_tho_toi_da} hạt` : `≤ ${g.hat_tho_toi_da} hạt`;
    }
    return tt === 'canh' ? '⚠ có hạt thô' : '0 = không có';
  }
  if (f === 'b8_nhiet_han') {
    if (!g.han_nhiet_min && !g.han_nhiet_max) return 'chưa có ngưỡng';
    const kh = `${g.han_nhiet_min ?? '…'}–${g.han_nhiet_max ?? '…'} °C`;
    return tt === 'loi' ? `✕ ngoài ${kh}` : kh;
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
  // Ô máy 2/3 dùng NGƯỠNG của ô gốc (rang_nhiet_do_m2 → rang_nhiet_do). D100.
  const goc = m.goc || m.f;
  const dem = ['thung_bot_qua_han', 't2_so_bay_dau_hieu', 'hat_tho'].includes(goc);
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
    const tt = trangThaiSo(goc, v, ng);
    wrap.classList.toggle('sx-qc-oso-loi', tt === 'loi');
    wrap.classList.toggle('sx-qc-oso-canh', tt === 'canh');
    goiy.textContent = tt ? loiSo(goc, v, ng) : (m.goi_y || '');
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
    hint: (n) => goiYNgan(goc, n, ng),
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
  // Dựng bằng el() (không innerHTML + querySelector): cùng cây DOM, và test DOM giả dựng được (sổ W43 dùng ô này).
  const row = el('div', 'sx-qc-hang');
  row.dataset.f = m.f;
  row.appendChild(el('div', 'sx-qc-nhan', nhan(m)));
  const nut2 = el('div', 'sx-qc-nut2');
  const b = el('button', null, '☐ Không');
  b.type = 'button';
  nut2.appendChild(b);
  row.appendChild(nut2);
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

/** B0 — chọn loại bột: bấm chip, chọn được nhiều vị (D100).
 *
 *  Danh mục lấy đúng tab "Bột đậu" của card Báo mẻ, không cho gõ tay: gõ tay
 *  thì "Sữa dừa", "sua dua", "Bột SD" là ba vị khác nhau với máy, và cờ lạc
 *  (quyết định có hiện B1/B2/B7 không) sẽ trượt đúng lúc cần nó nhất.
 *  Vị đã lưu mà không còn trong danh mục (hàng ngừng dùng) vẫn hiện để bỏ chọn.
 *  Danh mục rỗng (module QC cài ở nơi không có báo mẻ) → rơi về ô chữ. */
export function oChonBot(m, giaTri, onSet, dsBot, khoa) {
  if (!dsBot || !dsBot.length) return oChu(m, giaTri, onSet, khoa);
  const wrap = el('div', 'sx-qc-oso');
  wrap.dataset.f = m.f;
  wrap.appendChild(el('div', 'sx-qc-nhan', nhan(m, false)));
  const chon = new Set(String(giaTri || '').split('\n').map((x) => x.trim()).filter(Boolean));
  const ds = [...dsBot];
  chon.forEach((c) => { if (!ds.some((x) => x.item === c)) ds.push({ item: c, ten: c, lac: 0 }); });
  const box = el('div', 'sx-qc-vi');
  const ve = () => {
    box.innerHTML = '';
    ds.forEach((x) => {
      const b = el('button', `sx-qc-vi-o${chon.has(x.item) ? ' sx-qc-vi-on' : ''}`);
      b.type = 'button';
      b.disabled = !!khoa;
      b.setAttribute('aria-pressed', chon.has(x.item) ? 'true' : 'false');
      b.innerHTML = `${chon.has(x.item) ? '✓ ' : ''}${esc(x.ten)}`
        + (x.lac ? ' <span class="sx-qc-vi-lac">có lạc</span>' : '');
      b.addEventListener('click', () => {
        if (chon.has(x.item)) chon.delete(x.item); else chon.add(x.item);
        ve();
        // Giữ thứ tự danh mục, không theo thứ tự bấm: cùng một lựa chọn thì
        // cùng một chuỗi, tờ in và CSV không nhảy thứ tự giữa các lượt.
        onSet(m.f, ds.filter((y) => chon.has(y.item)).map((y) => y.item).join('\n'));
      });
      box.appendChild(b);
    });
  };
  ve();
  wrap.appendChild(box);
  wrap.appendChild(el('div', 'sx-qc-goiy',
    'Chọn vị <b>có lạc</b> thì mới hiện các mục về lạc (B1, B2, B7).'));
  return wrap;
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

/** Nút đầu tab Sự cố (W13): phiếu sự cố BM.08.02 ↔ khiếu nại khách hàng BM.11.01 ↔ hành động
 *  khắc phục BM.01.07 (W24, D150). Cùng một tab trên thanh QC: khiếu nại là nơi sự cố bắt đầu,
 *  khắc phục là nơi nó kết thúc — tách tab là thêm chỗ phải nhớ đi xem. */
export function tabSuCo(dang) {
  const box = el('div', 'sx-qc-seg sx-sc-tab');
  [['incidents', 'Phiếu sự cố'], ['khieunai', 'Khiếu nại KH'], ['khacphuc', 'Khắc phục']].forEach(([ma, ten]) => {
    const a = el('a', `sx-qc-tab${ma === dang ? ' sx-qc-seg-on' : ''}`, esc(ten));
    a.href = `#/qc/${ma}`;
    box.appendChild(a);
  });
  return box;
}

/** Hai nút đầu tab Xuất xưởng (W08): kiểm xuất xưởng BM.08.04 ↔ tủ lưu mẫu. Cùng
 *  một việc ở cùng một lúc — lô ra khỏi xưởng thì QC kiểm và lấy mẫu lưu. */
export function tabLo(dang) {
  const box = el('div', 'sx-qc-seg sx-sc-tab');
  [['xuatxuong', 'Kiểm xuất xưởng'], ['luumau', 'Lưu mẫu']].forEach(([ma, ten]) => {
    const a = el('a', `sx-qc-tab${ma === dang ? ' sx-qc-seg-on' : ''}`, esc(ten));
    a.href = `#/qc/${ma}`;
    box.appendChild(a);
  });
  return box;
}

/** Nút đầu tab Xem xét (W22, D148): Tổng quan ATTP ↔ Xem xét tháng ↔ Báo cáo tháng, chỉ tiêu ATTP
 *  (W25, D151) ↔ Hồ sơ cho đoàn đánh giá (W27, D149). Tab trên thanh QC đã đủ sáu với người duyệt —
 *  thêm tab thứ bảy là chữ gãy dòng trên điện thoại. */
export function tabXemXet(dang) {
  // D176: đang đứng trong màn ISO (#/iso) → thanh tab của màn ISO (thêm Xuất báo cáo, Truy xuất). Đường cũ #/qc/…
  // (người không có màn ISO mở từ hộp nhắc, trang đã đánh dấu) → thanh Xem xét cũ.
  const iso = String((window.location && window.location.hash) || '').startsWith('#/iso');
  const box = el('div', `sx-qc-seg sx-sc-tab${iso ? ' sx-iso-tab' : ''}`);
  // W42 (D171): "Tài liệu" sang thư viện tài liệu (#/tailieu, tab Ban hành / Đề nghị cho Ban ISO).
  // W45 (D174): "Biên bản" — họp Ban ISO, xem xét lãnh đạo, đánh giá nội bộ, thẩm tra… (#/qc/bienban).
  const tabs = iso
    ? [['attp', 'Tổng quan'], ['review', 'Xem xét tháng'], ['baocao', 'Báo cáo'], ['xuat', 'Xuất báo cáo'],
      ['hoso', 'Hồ sơ đánh giá'], ['bienban', 'Biên bản'], ['truyxuat', 'Truy xuất'], ['tailieu', 'Tài liệu']]
    : [['attp', 'Tổng quan'], ['review', 'Xem xét tháng'], ['baocao', 'Báo cáo'], ['bienban', 'Biên bản'],
      ['hoso', 'Hồ sơ đánh giá'], ['tailieu', 'Tài liệu']];
  tabs.forEach(([ma, ten]) => {
    const a = el('a', `sx-qc-tab${ma === dang ? ' sx-qc-seg-on' : ''}`, esc(ten));
    if (ma === 'tailieu') a.href = '#/tailieu/tatca';
    else if (iso) a.href = ma === 'attp' ? '#/iso' : `#/iso/${ma}`;
    else a.href = `#/qc/${ma}`;
    box.appendChild(a);
  });
  return box;
}

export function khungTrong(text) {
  return el('div', 'sx-qc-trong-box', esc(text));
}

/** Hộp nhắc việc — dùng chung cho màn QC, màn Xem xét, màn Sổ và card trên Quản lý.
 *
 * D186: GẬP sẵn thành một dòng — "🔔 8 việc cần chú ý · 2 mức cao" + việc quan trọng nhất; bấm mới mở danh
 * sách (8 hộp chồng nhau đẩy lượt kiểm xuống cuối màn). <details> gốc: không cần JS, bàn phím hiểu sẵn.
 * Có mục mức "cao" thì dòng gập viền đỏ, chữ đếm đỏ; trong danh sách mức "cao" viền đỏ, mức thường viền vàng.
 * Không có mục nào thì KHÔNG vẽ gì cả: một hộp "không có việc gì" chiếm chỗ mỗi ngày sẽ dạy mắt bỏ qua đúng
 * vùng màn hình đó, và hôm có việc thật thì nó cũng bị bỏ qua nốt.
 * opts.tieu_de: chữ dòng gập thay cho "N việc cần chú ý"; opts.mo: mở sẵn. */
export function veNhac(ds, opts = {}) {
  if (!ds || !ds.length) return null;
  const cao = ds.filter((x) => x.muc_do === 'cao');
  const dau = cao[0] || ds[0];
  const box = el('details', `sx-qc-nhac sx-qc-nhac-gap sx-qc-nhac-gap-${cao.length ? 'cao' : 'thuong'}`);
  if (opts.mo) box.open = true;
  box.appendChild(el('summary', 'sx-qc-nhac-tom', `<span class="sx-qc-nhac-dem">🔔 ${esc(opts.tieu_de
    || `${ds.length} việc cần chú ý`)}${cao.length ? ` · <b class="sx-qc-nhac-dem-cao">${cao.length} mức cao</b>` : ''}`
    + `</span><span class="sx-qc-nhac-dau">${esc(dau.tieu_de)}${ds.length > 1 ? ` · và ${ds.length - 1} việc khác` : ''}`
    + '</span>'));
  const ds_ = el('div', 'sx-qc-nhac-ds');
  ds.forEach((x) => {
    const a = el('a', `sx-qc-nhac-o sx-qc-nhac-${x.muc_do === 'cao' ? 'cao' : 'thuong'}`);
    a.href = x.route || '#/qc';
    a.innerHTML = `<div class="sx-qc-nhac-ten">${esc(x.tieu_de)}</div>
      <div class="sx-qc-nhac-ct">${esc(x.chi_tiet)}</div>`;
    ds_.appendChild(a);
  });
  box.appendChild(ds_);
  return box;
}

// ── Ba lượt trong ngày (D95 — không còn chia ca) ─────────────────────────
// Nhãn ngắn cho những chỗ chật (pill lịch sử, cột lưới tháng).
export const LUOT_NGAY = [
  { luot: 'Đầu sáng', ngan: 'Sáng' },
  { luot: 'Trưa', ngan: 'Trưa' },
  { luot: 'Cuối chiều', ngan: 'Chiều' },
];

/** Phiếu của một lượt trong danh sách phiếu CÙNG NGÀY.
 *
 * Tuần tính là Đầu sáng (nó chiếm chỗ Đầu sáng vào thứ Hai). Ngày cũ trước D95
 * có thể có hai phiếu cùng tên lượt (ca Sáng + ca Chiều): ưu tiên phiếu ĐÃ HOÀN
 * TẤT, vì ô này trả lời câu "lượt đó có người đi xong chưa". */
export function timLuot(dsNgay, luot) {
  const khop = dsNgay.filter((x) => x.luot === luot
    || (luot === 'Đầu sáng' && x.luot === 'Tuần'));
  return khop.find((x) => Number(x.docstatus) === 1) || khop[0] || null;
}


/** Bật / tắt "có sản xuất bột" (D98) — dùng chung cho màn Hôm nay và màn lượt.
 *
 * Tắt mà có lượt dở đã ghi mục bột thì server KHÔNG đổi gì, trả về danh sách
 * mục sẽ bị giấu; ở đây hỏi lại bằng hai bước rồi mới gửi `ep=1`. Tắt lặng lẽ
 * thì mấy ô người ta vừa ghi biến khỏi màn hình, khỏi tờ in, và không còn sinh
 * sự cố — mà không ai hay. */
export async function batTatBot({ call, method, args, onXong }) {
  try {
    const kq = await call(method, args);
    if (kq && kq.can_xac_nhan) {
      const ds = kq.luot.map((l) => `• ${l.luot}: ${l.muc.join(', ')}`).join('\n');
      confirm2Step({
        title: 'Tắt sản xuất bột',
        message: `Các mục bột ĐÃ GHI dưới đây sẽ biến khỏi lượt (không vào tờ in, `
          + `không sinh sự cố):\n\n${ds}\n\nGiá trị vẫn lưu lại, bật lại là thấy.`,
        confirmLabel: 'VẪN TẮT',
        onConfirm: async () => {
          try { onXong(await call(method, { ...args, ep: 1 })); } catch (e) {
            toastErr(e.message); throw e;
          }
        },
      });
      return;
    }
    onXong(kq);
  } catch (e) {
    toastErr(e.message);
  }
}
