// #/qc/baocao — báo cáo tháng ATTP, chỉ tiêu ATTP (W25, D151): nút trong tab Xem xét.
//
// Chọn tháng → chỉ tiêu năm (Đạt / Không đạt theo tháng và lũy kế), bảng chỉ số từ đầu năm, in báo cáo
// tháng cho họp xem xét của lãnh đạo. Ban ISO đặt chỉ tiêu: chỉ số nào, ≥ / ≤ bao nhiêu (theo văn bản
// mục tiêu ATTP). Số liệu tính tới hết hôm qua. Luật ở sx/qc/bao_cao.py.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment, tabXemXet } from '/assets/sx/sx/components/qcui.js';

const st = { thang: null };

function hien(v, dv) {
  if (v == null) return '—';
  return `${String(v).replace('.', ',')}${dv === '%' ? '%' : ''}`;
}

function kq(d) {
  if (d === true) return chip('Đạt', 'dong');
  if (d === false) return chip('Không đạt', 'cao');
  return chip('—');
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  let dl;
  try {
    dl = await call('sx.api.qc_baocao.so_lieu', st.thang ? { thang: st.thang } : {});
  } catch (e) {
    container.innerHTML = '';
    container.appendChild(tabXemXet('baocao'));
    container.appendChild(khungTrong(e.message));
    if (st.thang) {
      const b = el('button', 'sx-btn sx-btn-ghost', 'VỀ THÁNG TRƯỚC');
      b.type = 'button';
      b.addEventListener('click', () => { st.thang = null; render(api); });
      container.appendChild(b);
    }
    return;
  }
  st.thang = dl.thang;
  container.innerHTML = '';
  container.appendChild(tabXemXet('baocao'));
  const lai = () => render(api);

  const top = el('div', 'sx-qc-top');
  top.appendChild(el('div', null, `<div class="sx-qc-ngay">Báo cáo ATTP tháng ${esc(dl.thang.slice(5, 7))}/${dl.nam}</div>
    <div class="sx-qc-ai">số liệu tới hết ${esc(dl.cat.slice(8, 10))}/${esc(dl.cat.slice(5, 7))}</div>`));
  const inp = el('input', 'sx-textarea');
  inp.type = 'month';
  inp.value = dl.thang;
  inp.max = dl.hom_nay.slice(0, 7);
  inp.style.maxWidth = '180px';
  inp.addEventListener('change', () => { if (inp.value) { st.thang = inp.value; lai(); } });
  top.appendChild(inp);
  container.appendChild(top);

  const nutIn = el('button', 'sx-btn sx-btn-primary sx-btn-big', '🖨 IN BÁO CÁO THÁNG');
  nutIn.type = 'button';
  nutIn.addEventListener('click', () => inBaoCao(dl.thang, api, nutIn));
  container.appendChild(nutIn);

  // ── chỉ tiêu ─────────────────────────────────────────────────────────
  container.appendChild(el('div', 'sx-qc-buoc', `<span class="sx-qc-buoc-ten">Chỉ tiêu ATTP năm ${dl.nam}</span>`));
  if (!dl.chi_tieu.length) {
    container.appendChild(el('div', 'sx-qc-goiy', `Chưa đặt chỉ tiêu năm ${dl.nam}. Báo cáo vẫn đủ bảng chỉ số; `
      + 'chỉ tiêu nhập theo văn bản mục tiêu ATTP của nhà máy.'));
  }
  dl.chi_tieu.forEach((c) => {
    const the = el('div', `sx-qc-sc ${c.dat_ky === false || c.dat_nam === false ? 'sx-qc-sc-mo' : 'sx-qc-sc-dong'}`);
    the.appendChild(el('div', 'sx-qc-sc-ten', esc(c.ten)));
    const meta = el('div', 'sx-qc-sc-meta');
    meta.appendChild(el('span', null, `mục tiêu <b>${esc(c.so_sanh)} ${esc(hien(c.muc_tieu, c.don_vi))}</b>`));
    meta.appendChild(el('span', null, `${c.kieu === 'hien_tai' ? 'hiện tại' : `tháng ${dl.thang.slice(5, 7)}`} `
      + `<b>${esc(hien(c.ky, c.don_vi))}</b>`));
    meta.appendChild(kq(c.dat_ky));
    if (c.kieu !== 'hien_tai') {
      meta.appendChild(el('span', null, `lũy kế <b>${esc(hien(c.nam, c.don_vi))}</b>`));
      meta.appendChild(kq(c.dat_nam));
    }
    the.appendChild(meta);
    if (dl.duoc_sua) {
      const s = el('button', 'sx-btn sx-btn-ghost', 'SỬA');
      s.type = 'button';
      s.addEventListener('click', () => moChiTieu(c, dl, api, lai));
      const w = el('div', 'sx-qc-chips sx-tb-nut');
      w.appendChild(s);
      the.appendChild(w);
    }
    container.appendChild(the);
  });
  if (dl.duoc_sua) {
    const them = el('button', 'sx-btn sx-btn-ghost', '+ THÊM CHỈ TIÊU');
    them.type = 'button';
    them.addEventListener('click', () => moChiTieu(null, dl, api, lai));
    container.appendChild(them);
    const ngung = dl.ds_chi_tieu.filter((c) => c.ngung);
    if (ngung.length) {
      const tenCs = (ma) => (dl.chi_so.find((x) => x.ma === ma) || {}).ten || ma;
      container.appendChild(el('div', 'sx-qc-goiy', `Đã ngừng: ${ngung.map((c) => esc(c.ten || tenCs(c.chi_so))).join(', ')}`));
    }
  }

  // ── bảng chỉ số ──────────────────────────────────────────────────────
  container.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">Chỉ số từ đầu năm</span>'));
  const thang = dl.bang.find((x) => x.kieu === 'thang');
  const cac = thang ? Object.keys(thang.thang) : [];
  let h = `<table><tr><th>Chỉ số</th>${cac.map((t) => `<th>T${esc(t.slice(5, 7))}</th>`).join('')}<th>Lũy kế</th></tr>`;
  dl.bang.filter((x) => x.kieu === 'thang').forEach((x) => {
    h += `<tr><td class="sx-bc-ten">${esc(x.ten)}</td>${cac.map((t) => `<td>${esc(hien(x.thang[t], x.don_vi))}</td>`).join('')}`
      + `<td><b>${esc(hien(x.nam, x.don_vi))}</b></td></tr>`;
  });
  h += '</table>';
  const luoi = el('div', 'sx-qc-luoi sx-bc-bang');
  luoi.innerHTML = h;
  container.appendChild(luoi);
  const ht = dl.bang.filter((x) => x.kieu === 'hien_tai');
  const kp = el('div', 'sx-qc-kpi');
  ht.forEach((x) => {
    const o = el('div', 'sx-qc-kpi-o');
    o.appendChild(el('div', 'sx-qc-kpi-nhan', esc(x.ten)));
    o.appendChild(el('div', 'sx-qc-kpi-so', esc(hien(x.ky, x.don_vi))));
    o.appendChild(el('div', 'sx-qc-goiy', 'tại ngày lập'));
    kp.appendChild(o);
  });
  container.appendChild(kp);
}

function moChiTieu(c, dl, api, lai) {
  const v = c || { nam: dl.nam, chi_so: dl.chi_so[0].ma, so_sanh: '', muc_tieu: '' };
  const m = openModal({ kicker: `CHỈ TIÊU ATTP NĂM ${v.nam}`, title: c ? c.ten : 'Thêm chỉ tiêu' });
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Chỉ số (app tự tính)'));
  const cs = el('select', 'sx-textarea');
  dl.chi_so.forEach((x) => {
    const o = el('option', null, `${esc(x.ten)} (${esc(x.don_vi)}${x.kieu === 'hien_tai' ? ', tại ngày lập' : ''})`);
    o.value = x.ma;
    if (x.ma === v.chi_so) o.selected = true;
    cs.appendChild(o);
  });
  m.body.appendChild(cs);
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Tên chỉ tiêu theo văn bản (để trống = tên chỉ số)'));
  const ten = el('input', 'sx-textarea');
  ten.value = c && c.ten !== (dl.chi_so.find((x) => x.ma === c.chi_so) || {}).ten ? c.ten : '';
  m.body.appendChild(ten);
  m.body.appendChild(el('div', 'sx-qc-goiy', 'So sánh'));
  let ss = v.so_sanh || '≥';
  m.body.appendChild(segment(['≥', '≤'], ss, (x) => { ss = x || ss; }, false));
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Mục tiêu (số; chỉ số % thì 0 – 100)'));
  const mt = el('input', 'sx-textarea');
  mt.type = 'number';
  mt.step = 'any';
  mt.inputMode = 'decimal';
  mt.value = v.muc_tieu == null ? '' : v.muc_tieu;
  m.body.appendChild(mt);
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Ghi chú / căn cứ'));
  const gc = el('textarea', 'sx-textarea');
  gc.rows = 2;
  gc.value = (c && c.ghi_chu) || '';
  m.body.appendChild(gc);
  const nl = el('label', 'sx-sc-check');
  const nc = el('input');
  nc.type = 'checkbox';
  nc.checked = !!(c && c.ngung);
  nl.appendChild(nc);
  nl.appendChild(el('span', null, 'Ngừng (không đánh giá nữa)'));
  m.body.appendChild(nl);
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (mt.value === '') { toastErr('Nhập mục tiêu.'); return; }
    ok.disabled = true;
    try {
      await api.call('sx.api.qc_baocao.luu_chi_tieu', { payload: JSON.stringify({
        name: c ? c.name : null, nam: v.nam, chi_so: cs.value, ten: ten.value, so_sanh: ss, muc_tieu: mt.value,
        ghi_chu: gc.value, ngung: nc.checked ? 1 : 0 }) });
      toast('Đã lưu chỉ tiêu');
      m.close();
      lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
  if (c) {
    const xoa = el('button', 'sx-btn sx-btn-ghost', 'XOÁ CHỈ TIÊU');
    xoa.type = 'button';
    xoa.addEventListener('click', () => confirm2Step({
      title: 'Xoá chỉ tiêu?', message: 'Chỉ tiêu không dùng nữa thì nên bấm Ngừng — còn dấu vết năm đó.',
      confirmLabel: 'XOÁ',
      onConfirm: async () => { await api.call('sx.api.qc_baocao.xoa_chi_tieu', { name: c.name }); m.close(); lai(); },
    }));
    m.body.appendChild(xoa);
  }
}

async function inBaoCao(thang, api, nut) {
  nut.disabled = true;
  try {
    const html = await api.call('sx.api.qc_baocao.in_bao_cao', { thang });
    const w = window.open('', '_blank');
    if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
    // Cửa sổ about:blank không thừa kế bảng mã — tự khai, như các tờ in khác.
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Báo cáo ATTP ${thang}</title>`
      + `</head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 400);
  } catch (e) { toastErr(e.message); } finally { nut.disabled = false; }
}
