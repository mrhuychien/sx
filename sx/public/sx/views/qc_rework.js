// #/qc/rework — phiếu rework BM.15.01 (W19, D145; W32 D164: QLSX quyết định + giờ, giờ bắt đầu – kết thúc).
//
// Đưa hàng đem rework vào một mẻ: KHÔNG QUÁ 10% khối lượng mẻ, KHÔNG đưa hàng có lạc vào sản
// phẩm không lạc (cờ "Có lạc" của bộ tự công bố W28). Màn này tính trước cho người lập thấy;
// chốt thật ở sx/qc/rework.py + controller (chặn cả Desk).

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong } from '/assets/sx/sx/components/qcui.js';

const st = { thang: null };
const ngayVN = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}` : '');
const so = (v) => Number(v || 0).toLocaleString('vi-VN', { maximumFractionDigits: 2 });

function congThang(t, n) {
  const [y, m] = t.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1 + n, 1)).toISOString().slice(0, 7);
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc_rework.tong_quan', st.thang ? { thang: st.thang } : {});
  container.innerHTML = '';
  const lai = () => render(api);
  const thangNay = dl.hom_nay.slice(0, 7);

  const top = el('div', 'sx-qc-top sx-dv-tuan');
  const lui = el('button', 'sx-btn sx-btn-ghost', '‹');
  lui.type = 'button';
  lui.addEventListener('click', () => { st.thang = congThang(dl.thang, -1); lai(); });
  const tien = el('button', 'sx-btn sx-btn-ghost', '›');
  tien.type = 'button';
  tien.disabled = dl.thang >= thangNay;
  tien.addEventListener('click', () => { const t = congThang(dl.thang, 1); st.thang = t >= thangNay ? null : t; lai(); });
  top.appendChild(lui);
  top.appendChild(el('div', 'sx-dv-tuan-ten', `<div class="sx-qc-ngay">♻ Rework</div>
    <div class="sx-qc-ai">BM.15.01 · tháng ${esc(dl.thang.slice(5))}/${esc(dl.thang.slice(0, 4))}</div>`));
  top.appendChild(tien);
  container.appendChild(top);
  container.appendChild(el('div', 'sx-qc-goiy', `Tối đa ${dl.toi_da}% khối lượng mẻ · không đưa hàng CÓ LẠC vào `
    + 'sản phẩm không lạc. Phiếu sự cố quyết định "Rework" chỉ đóng được khi đã có phiếu này.'));

  if (dl.duoc_ghi) {
    const them = el('button', 'sx-btn sx-btn-primary sx-btn-big', '+ LẬP PHIẾU REWORK');
    them.type = 'button';
    them.addEventListener('click', () => moLap(dl, api, lai));
    container.appendChild(them);
  }

  if (!dl.ds.length) container.appendChild(khungTrong('Tháng này chưa có rework.'));
  dl.ds.forEach((x) => {
    const the = el('div', 'sx-qc-sc sx-qc-sc-dong');
    the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(ngayVN(x.ngay))} · ${esc(x.ten_nguon)} → ${esc(x.ten_dich)}`));
    const meta = el('div', 'sx-qc-sc-meta');
    meta.appendChild(chip(`${so(x.kl_rework)} kg / mẻ ${so(x.kl_me)} kg = ${so(x.ty_le)}%`));
    if (x.nguon_co_lac) meta.appendChild(chip('có lạc', 'oprp'));
    if (x.me) meta.appendChild(el('span', null, `mẻ ${esc(x.me)}`));
    if (x.su_co) meta.appendChild(chip(x.su_co));
    if (x.gio_bat_dau || x.gio_ket_thuc) meta.appendChild(chip(`${x.gio_bat_dau || '…'}–${x.gio_ket_thuc || '…'}`));
    if (x.qlsx_quyet_dinh) meta.appendChild(chip(`QLSX ${x.ten_qlsx || x.qlsx_quyet_dinh} ${x.qlsx_luc.slice(11, 16)}`, 'dong'));
    meta.appendChild(el('span', null, esc(x.nguoi_lap || '')));
    the.appendChild(meta);
    if (x.ly_do || x.ket_qua) the.appendChild(el('div', 'sx-qc-goiy', esc([x.ly_do, x.ket_qua].filter(Boolean).join(' · '))));
    if (dl.la_iso || (x.nguoi_lap === dl.user && x.creation === dl.hom_nay)) {
      const xoa = el('button', 'sx-btn sx-btn-ghost', 'XOÁ (lập nhầm)');
      xoa.type = 'button';
      xoa.addEventListener('click', () => confirm2Step({
        title: `Xoá phiếu rework ${x.name}?`, message: 'Chỉ xoá khi lập nhầm.', confirmLabel: 'XOÁ',
        onConfirm: async () => { await api.call('sx.api.qc_rework.xoa', { name: x.name }); toast('Đã xoá'); lai(); },
      }));
      const nut = el('div', 'sx-qc-chips sx-tb-nut');
      nut.appendChild(xoa);
      the.appendChild(nut);
    }
    container.appendChild(the);
  });

  const inB = el('button', 'sx-btn sx-btn-ghost', `🖨 IN BM.15.01 — tháng ${esc(dl.thang.slice(5))}/${esc(dl.thang.slice(0, 4))}`);
  inB.type = 'button';
  inB.addEventListener('click', () => inTo(api, 'sx.api.qc_rework.in_bm1501', { thang: dl.thang }, 'BM.15.01'));
  container.appendChild(inB);
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

function chon(body, nhan, ds) {
  body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
  const s = el('select', 'sx-textarea');
  ds.forEach(([v, t]) => { const o = el('option', null, esc(t)); o.value = v; s.appendChild(o); });
  body.appendChild(s);
  return s;
}

function moLap(dl, api, lai) {
  const m = openModal({ kicker: 'PHIẾU REWORK BM.15.01', title: 'Lập phiếu rework' });
  const ng = oNhap(m.body, 'Ngày', dl.hom_nay, 'date');
  ng.max = dl.hom_nay;
  const sc = chon(m.body, 'Phiếu sự cố (nếu rework theo quyết định sự cố)', [['', '— không —']].concat(
    dl.su_co.map((x) => [x.name, `${x.name} · ${ngayVN(x.ngay)} · ${x.mo_ta}`])));
  const dsSp = [['', '— chọn sản phẩm —']].concat(dl.san_pham.map((x) => [x.name,
    `${x.so_cong_bo ? `${x.so_cong_bo} · ` : ''}${x.ten_san_pham}${x.co_lac ? ' (CÓ LẠC)' : ''}`]));
  m.body.appendChild(el('div', 'sx-dv-khu', 'Hàng đem rework'));
  const spN = chon(m.body, 'Thuộc sản phẩm', dsSp);
  const moTa = oNhap(m.body, 'Hàng / lô / HSD', '');
  const klR = oNhap(m.body, 'Khối lượng đem rework (kg)', '', 'number');
  klR.inputMode = 'decimal';
  const lyDo = oNhap(m.body, 'Lý do (vỡ, móp, lỗi in…)', '', 'ta');
  m.body.appendChild(el('div', 'sx-dv-khu', 'Mẻ nhận rework'));
  const spD = chon(m.body, 'Đưa vào sản phẩm', dsSp);
  const me = oNhap(m.body, 'Mẻ / lô sản xuất', '');
  const ngSx = oNhap(m.body, 'Ngày sản xuất mẻ', dl.hom_nay, 'date');
  const klM = oNhap(m.body, 'Khối lượng mẻ (kg, tính cả phần rework)', '', 'number');
  klM.inputMode = 'decimal';
  const bao = el('div', 'sx-cat-doi');
  bao.style.display = 'none';
  const tinh = el('div', 'sx-qc-goiy sx-tb-kq');
  m.body.appendChild(tinh);
  m.body.appendChild(bao);
  // W32: QT.15 mục 6 — QLSX quyết định (người + giờ) trước khi làm; giờ bắt đầu – kết thúc rework.
  m.body.appendChild(el('div', 'sx-dv-khu', 'QLSX quyết định, giờ rework'));
  const ql = chon(m.body, 'QLSX quyết định (túi hở, hộp in sai: QC đóng gói tự quyết — để trống)',
    [['', '— không —']].concat(dl.qlsx.map((u) => [u.name, u.ten])));
  if (dl.qlsx.find((u) => u.name === dl.user)) ql.value = dl.user;
  const qlLuc = oNhap(m.body, 'QLSX quyết định lúc', `${dl.hom_nay}T${new Date().toTimeString().slice(0, 5)}`,
    'datetime-local');
  const gio = el('div', 'sx-vu-gio');
  const o1 = el('div');
  const o2 = el('div');
  gio.appendChild(o1);
  gio.appendChild(o2);
  m.body.appendChild(gio);
  const gioBd = oNhap(o1, 'Giờ bắt đầu', '', 'time');
  const gioKt = oNhap(o2, 'Giờ kết thúc', '', 'time');
  const kq = oNhap(m.body, 'Kết quả / kiểm tra sau rework', '', 'ta');
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LẬP PHIẾU');
  ok.type = 'button';
  // Bản sao client của rework.kiem() — chỉ để người lập thấy trước; server vẫn chốt.
  const capNhat = () => {
    const r = Number(klR.value || 0);
    const k = Number(klM.value || 0);
    const loi = [];
    const canh = [];
    if (r > 0 && k > 0) {
      const tl = Math.round((r * 10000) / k) / 100;
      tinh.textContent = `Tỷ lệ rework ${so(tl)}% khối lượng mẻ (tối đa ${dl.toi_da}% = ${so((k * dl.toi_da) / 100)} kg)`;
      if (r > k) loi.push('Khối lượng rework lớn hơn cả mẻ.');
      else if (tl > dl.toi_da) loi.push(`Vượt ${dl.toi_da}% khối lượng mẻ.`);
    } else tinh.textContent = '';
    const n = dl.san_pham.find((x) => x.name === spN.value);
    const d = dl.san_pham.find((x) => x.name === spD.value);
    if (n && d && n.co_lac && !d.co_lac) loi.push('Hàng CÓ LẠC không được đưa vào sản phẩm KHÔNG LẠC.');
    if (n && d && n.co_sua_bot && !d.co_sua_bot) canh.push('Hàng có sữa bột vào sản phẩm không sữa — kiểm lại nhãn.');
    if (gioBd.value && gioKt.value && gioKt.value < gioBd.value) loi.push('Giờ kết thúc trước giờ bắt đầu.');
    bao.innerHTML = [...loi.map((x) => `⛔ ${esc(x)}`), ...canh.map((x) => `⚠ ${esc(x)}`)].join('<br>');
    bao.style.display = loi.length || canh.length ? '' : 'none';
    ok.disabled = loi.length > 0;
  };
  [klR, klM, gioBd, gioKt].forEach((n) => n.addEventListener('input', capNhat));
  [spN, spD].forEach((n) => n.addEventListener('change', capNhat));
  ok.addEventListener('click', async () => {
    if (!spN.value || !spD.value) { toastErr('Chọn sản phẩm của hàng đem rework và sản phẩm nhận.'); return; }
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc_rework.lap_phieu', {
        payload: JSON.stringify({
          ngay: ng.value || dl.hom_nay, su_co: sc.value, sp_nguon: spN.value, mo_ta_nguon: moTa.value, ly_do: lyDo.value,
          kl_rework: klR.value, sp_dich: spD.value, me: me.value, ngay_sx: ngSx.value, kl_me: klM.value, ket_qua: kq.value,
          qlsx_quyet_dinh: ql.value, qlsx_luc: ql.value ? qlLuc.value : '', gio_bat_dau: gioBd.value,
          gio_ket_thuc: gioKt.value,
        }),
      });
      toast(`Đã lập ${r.name} — ${so(r.ty_le)}% khối lượng mẻ`);
      m.close();
      st.thang = null;
      lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

// Cửa sổ mới, tự khai charset (about:blank không thừa kế) — cùng cách in BM.11.01.
async function inTo(api, method, args, ten) {
  try {
    const html = await api.call(method, args);
    const w = window.open('', '_blank');
    if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
      + `<title>${esc(ten)}</title></head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 250);
  } catch (e) { toastErr(e.message); }
}
