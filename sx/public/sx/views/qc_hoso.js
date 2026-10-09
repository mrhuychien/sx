// #/qc/hoso — Hồ sơ cho đoàn đánh giá (W27, D149): nút thứ ba trong tab Xem xét.
//
// Danh mục hồ sơ / văn bản (mã, căn cứ pháp lý, nằm ở đâu, hạn) kèm cờ Đỏ / Vàng, và nút tải GÓI ZIP
// cho đoàn: mục lục + bản in các biểu mẫu app lập trong kỳ + bản scan đính kèm. Luật cờ ở
// sx/qc/ho_so.py; đèn của các mảng app lấy từ Tổng quan ATTP.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment, tabXemXet } from '/assets/sx/sx/components/qcui.js';

const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const DUOI = '.pdf,.png,.jpg,.jpeg,.webp,.doc,.docx,.xls,.xlsx';

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  let dl;
  try {
    dl = await call('sx.api.qc_hoso.tong_quan', {});
  } catch (e) {
    container.innerHTML = '';
    container.appendChild(tabXemXet('hoso'));
    container.appendChild(khungTrong(e.message));
    return;
  }
  container.innerHTML = '';
  container.appendChild(tabXemXet('hoso'));
  const lai = () => render(api);

  container.appendChild(el('div', 'sx-qc-top', `<div style="flex:1;min-width:0">
    <div class="sx-qc-ngay">Hồ sơ cho đoàn đánh giá</div>
    <div class="sx-qc-ai">Cờ Đỏ: đoàn sẽ ghi lỗi · Vàng: xem lại trước khi đoàn tới</div></div>`));
  const dem = el('div', 'sx-attp-dem');
  dem.appendChild(el('span', 'sx-attp-dem-o sx-attp-do',
    `<span class="sx-attp-cham" aria-hidden="true"></span><b>${dl.dem.do}</b> Đỏ`));
  dem.appendChild(el('span', 'sx-attp-dem-o sx-attp-vang',
    `<span class="sx-attp-cham" aria-hidden="true"></span><b>${dl.dem.vang}</b> Vàng`));
  container.appendChild(dem);

  // ── gói zip ──────────────────────────────────────────────────────────
  const goi = el('div', 'sx-qc-sc sx-hs-goi');
  goi.appendChild(el('div', 'sx-qc-sc-ten', 'Gói zip cho đoàn'));
  const ky = el('div', 'sx-hs-ky');
  const tu = el('input', 'sx-textarea');
  tu.type = 'date';
  tu.value = dl.tu;
  const den = el('input', 'sx-textarea');
  den.type = 'date';
  den.value = dl.den;
  den.max = dl.hom_nay;
  ky.appendChild(el('label', null, 'Từ ngày'));
  ky.appendChild(tu);
  ky.appendChild(el('label', null, 'Đến ngày'));
  ky.appendChild(den);
  goi.appendChild(ky);
  goi.appendChild(el('div', 'sx-qc-goiy', 'Mục lục (cờ, căn cứ, chỗ tìm) + bản in các biểu mẫu app trong kỳ + '
    + 'bản scan đính kèm. Mở tệp 00-MUC-LUC.html trước.'));
  const tai = el('button', 'sx-btn sx-btn-primary sx-btn-big', '⬇ TẢI GÓI ZIP');
  tai.type = 'button';
  tai.addEventListener('click', () => {
    if (!tu.value || !den.value || tu.value > den.value) { toastErr('Chọn kỳ: từ ngày trước đến ngày.'); return; }
    // GET để trình duyệt tự tải tệp — server chặn quyền và kỳ quá dài như mọi lời gọi khác.
    window.location.href = `/api/method/sx.api.qc_hoso.tai_goi?${new URLSearchParams({ tu: tu.value, den: den.value })}`;
    toast('Đang đóng gói — trình duyệt sẽ tải tệp zip về.');
  });
  goi.appendChild(tai);
  container.appendChild(goi);

  // ── danh mục theo nhóm ───────────────────────────────────────────────
  if (!dl.ds.length) container.appendChild(khungTrong('Danh mục trống.'));
  let nhom = null;
  dl.ds.filter((x) => !x.ngung).forEach((x) => {
    if (x.nhom !== nhom) {
      nhom = x.nhom;
      container.appendChild(el('div', 'sx-qc-buoc', `<span class="sx-qc-buoc-ten">${esc(nhom || 'Khác')}</span>`));
    }
    container.appendChild(theHoSo(x, dl, api, lai));
  });
  const ngung = dl.ds.filter((x) => x.ngung);
  if (ngung.length) {
    container.appendChild(el('div', 'sx-qc-buoc', '<span class="sx-qc-buoc-ten">Đã ngừng / đã thay thế</span>'));
    ngung.forEach((x) => container.appendChild(theHoSo(x, dl, api, lai)));
  }
  if (dl.duoc_sua) {
    const them = el('button', 'sx-btn sx-btn-primary sx-btn-big', '+ THÊM HỒ SƠ / VĂN BẢN');
    them.type = 'button';
    them.addEventListener('click', () => moSua(null, dl, api, lai));
    container.appendChild(them);
  }
}

function theHoSo(x, dl, api, lai) {
  const the = el('div', `sx-qc-sc ${x.co === 'do' ? 'sx-qc-sc-mo' : 'sx-qc-sc-dong'}${x.ngung ? ' sx-hs-ngung' : ''}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', `${x.co ? `<span class="sx-attp-cham sx-hs-co-${x.co}" `
    + `aria-label="cờ ${x.co === 'do' ? 'Đỏ' : 'Vàng'}"></span> ` : ''}<b>${esc(x.ma)}</b> · ${esc(x.ten)}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(x.nguon === 'App lập' ? `App · ${x.bieu_mau || ''}` : x.nguon));
  if (x.het_han) meta.appendChild(chip(`hạn ${ngayDu(x.het_han)}`, x.co === 'do' ? 'cao' : ''));
  if (x.thay_the) meta.appendChild(el('span', null, `thay ${esc(x.thay_the)}`));
  if (x.nguon === 'Bản giấy' && x.noi_luu) meta.appendChild(el('span', null, `lưu: ${esc(x.noi_luu)}`));
  the.appendChild(meta);
  if (x.can_cu) the.appendChild(el('div', 'sx-qc-goiy', `Căn cứ: ${esc(x.can_cu)}`));
  (x.ly_do || []).forEach((l) => the.appendChild(el('div', `sx-attp-viec sx-attp-viec-${l.muc === 'do' ? 'cao' : 'thuong'}`,
    esc(l.nd))));
  if (x.tep) {
    const a = el('a', 'sx-qc-goiy', '📎 Bản scan');
    a.href = x.tep;
    a.target = '_blank';
    a.rel = 'noopener';
    the.appendChild(a);
  }
  if (dl.duoc_sua) {
    const nut = el('div', 'sx-qc-chips sx-tb-nut');
    if (x.nguon === 'Tệp đính kèm' && !x.ngung) nut.appendChild(nutTep(x, api, lai));
    const s = el('button', 'sx-btn sx-btn-ghost', 'SỬA');
    s.type = 'button';
    s.addEventListener('click', () => moSua(x, dl, api, lai));
    nut.appendChild(s);
    the.appendChild(nut);
  }
  return the;
}

function nutTep(x, api, lai) {
  const b = el('button', 'sx-btn sx-btn-ghost', x.tep ? '📎 THAY BẢN SCAN' : '📎 GẮN BẢN SCAN');
  b.type = 'button';
  const inp = el('input');
  inp.type = 'file';
  inp.accept = DUOI;
  inp.style.display = 'none';
  inp.addEventListener('change', () => {
    const f = inp.files && inp.files[0];
    if (!f) return;
    if (f.size > 10 * 1024 * 1024) { toastErr('Tệp quá 10 MB — scan nhẹ hơn hoặc tách tệp.'); return; }
    const r = new FileReader();
    r.onload = async () => {
      b.disabled = true;
      try {
        await api.call('sx.api.qc_hoso.them_tep', { name: x.name, ten: f.name, noi_dung: String(r.result).split(',')[1] });
        toast('Đã gắn bản scan');
        lai();
      } catch (e) { b.disabled = false; toastErr(e.message); }
    };
    r.readAsDataURL(f);
  });
  b.addEventListener('click', () => inp.click());
  const w = el('span');
  w.appendChild(b);
  w.appendChild(inp);
  return w;
}

function oNhap(body, nhan, gt, kieu) {
  body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
  const n = el(kieu === 'ta' ? 'textarea' : 'input');
  n.className = 'sx-textarea';
  if (kieu === 'ta') n.rows = 2;
  else if (kieu) n.type = kieu;
  n.value = gt == null ? '' : gt;
  body.appendChild(n);
  return n;
}

function oChon(body, nhan, lua, gt) {
  body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
  const s = el('select', 'sx-textarea');
  lua.forEach(([v, ten]) => {
    const o = el('option', null, esc(ten));
    o.value = v;
    if (v === gt) o.selected = true;
    s.appendChild(o);
  });
  body.appendChild(s);
  return s;
}

function oCheck(body, nhan, gt) {
  const l = el('label', 'sx-sc-check');
  const c = el('input');
  c.type = 'checkbox';
  c.checked = !!gt;
  l.appendChild(c);
  l.appendChild(el('span', null, esc(nhan)));
  body.appendChild(l);
  return c;
}

function moSua(x, dl, api, lai) {
  const v = x || { nhom: dl.nhom[0], nguon: 'Tệp đính kèm', bat_buoc: 1 };
  const m = openModal({ kicker: 'DANH MỤC HỒ SƠ', title: x ? `${x.ma} · ${x.ten}` : 'Thêm hồ sơ / văn bản' });
  const ma = oNhap(m.body, 'Mã / số hiệu (BM.08.01, TCCS 01, CV 21/CV-HGC…)', v.ma);
  const ten = oNhap(m.body, 'Tên hồ sơ / văn bản', v.ten);
  const nhom = oChon(m.body, 'Nhóm', dl.nhom.map((n) => [n, n]), v.nhom);
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Nằm ở đâu'));
  let nguon = v.nguon;
  const bmWrap = el('div');
  const giayWrap = el('div');
  const hien = () => {
    bmWrap.style.display = nguon === 'App lập' ? '' : 'none';
    giayWrap.style.display = nguon === 'Bản giấy' ? '' : 'none';
  };
  m.body.appendChild(segment(dl.nguon, nguon, (g) => { nguon = g || nguon; hien(); }, false));
  const bm = oChon(bmWrap, 'Biểu mẫu app', [['', '— chọn —']].concat(dl.bieu_mau.map((b) => [b.ma, `${b.ma} · ${b.ten}`])),
    v.bieu_mau || '');
  m.body.appendChild(bmWrap);
  const noiLuu = oNhap(giayWrap, 'Nơi lưu bản giấy (tủ / bìa số…)', v.noi_luu);
  m.body.appendChild(giayWrap);
  hien();
  const canCu = oNhap(m.body, 'Căn cứ / nguồn pháp lý (vd "Ban hành theo QĐ 11")', v.can_cu, 'ta');
  const thay = oNhap(m.body, 'Thay thế văn bản (mã văn bản cũ, vd CV 10)', v.thay_the);
  const nbh = oNhap(m.body, 'Ngày ban hành', v.ngay_ban_hanh, 'date');
  const hh = oNhap(m.body, `Hết hạn (cờ Vàng khi còn ≤ ${dl.sap_het} ngày)`, v.het_han, 'date');
  const tt = oNhap(m.body, 'Thứ tự trong nhóm', v.thu_tu || '', 'number');
  tt.inputMode = 'numeric';
  const gc = oNhap(m.body, 'Ghi chú', v.ghi_chu, 'ta');
  const bb = oCheck(m.body, 'Bắt buộc có khi đánh giá (thiếu bản scan → cờ Đỏ)', v.bat_buoc);
  const ng = oCheck(m.body, 'Ngừng (đã thay / không dùng nữa)', v.ngung);
  if (x && x.tep) {
    const bo = el('button', 'sx-btn sx-btn-ghost', 'BỎ BẢN SCAN');
    bo.type = 'button';
    bo.addEventListener('click', async () => {
      try { await api.call('sx.api.qc_hoso.bo_tep', { name: x.name }); toast('Đã bỏ bản scan'); m.close(); lai(); } catch (e) { toastErr(e.message); }
    });
    m.body.appendChild(bo);
  }
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!ma.value.trim() || !ten.value.trim()) { toastErr('Nhập mã và tên.'); return; }
    if (nguon === 'App lập' && !bm.value) { toastErr('Chọn biểu mẫu app.'); return; }
    ok.disabled = true;
    try {
      await api.call('sx.api.qc_hoso.luu', { payload: JSON.stringify({
        name: x ? x.name : null, ma: ma.value, ten: ten.value, nhom: nhom.value, nguon, bieu_mau: bm.value,
        noi_luu: noiLuu.value, can_cu: canCu.value, thay_the: thay.value, ngay_ban_hanh: nbh.value, het_han: hh.value,
        thu_tu: tt.value, ghi_chu: gc.value, bat_buoc: bb.checked ? 1 : 0, ngung: ng.checked ? 1 : 0 }) });
      toast('Đã lưu');
      m.close();
      lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
  if (x) {
    const xoa = el('button', 'sx-btn sx-btn-ghost', 'XOÁ KHỎI DANH MỤC');
    xoa.type = 'button';
    xoa.addEventListener('click', () => confirm2Step({
      title: `Xoá ${x.ma} khỏi danh mục?`,
      message: 'Văn bản chỉ không còn dùng thì nên bấm Ngừng — dòng vẫn còn để tra.',
      confirmLabel: 'XOÁ',
      onConfirm: async () => {
        await api.call('sx.api.qc_hoso.xoa', { name: x.name });
        toast('Đã xoá');
        m.close();
        lai();
      },
    }));
    m.body.appendChild(xoa);
  }
}
