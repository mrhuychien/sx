// #/qc/kiemnghiem — kế hoạch kiểm nghiệm KH.KN.01 (W18, D144).
//
// Mỗi sản phẩm trong bộ tự công bố (W28) gửi mẫu ít nhất 1 lần / năm: lần sau = lần gửi gần nhất
// + 12 tháng; chưa gửi lần nào → hạn đầu 31/10/2026. Cát rang chỉ kiểm khi đổi nguồn (nhật ký
// cát W20) — kết quả chép sang nhật ký cát. Luật ở sx/qc/kiem_nghiem.py + controller.
// W35 (D166): nước, nguyên liệu, bao bì, thẩm tra vải ủ theo KH.KN.01 — việc kiểm nghiệm định kỳ (màn Việc
// định kỳ, ô "mẫu của"); GỬI MẪU gắn việc → app ghi lần làm, dời hạn sang kỳ sau.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment } from '/assets/sx/sx/components/qcui.js';

const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const KIEU = { 'Quá hạn': 'cao', 'Không đạt — kiểm lại': 'cao', 'Đến hạn': 'oprp', 'Chờ kết quả': '', 'Đạt': 'dong' };
const KIEU_VIEC = { 'Quá hạn': 'cao', 'Sắp đến hạn': 'oprp', 'Chưa đặt hạn': 'han', 'Còn hạn': 'dong', 'Ngừng': '' };

/** Dòng hạn của một việc kiểm nghiệm định kỳ — hàm THUẦN để test. Không có hạn thì NÓI ra, không im lặng. */
export function hanViec(v) {
  if (v.trang_thai === 'Ngừng') return v.phieu_cuoi ? `đã gửi mẫu ${ngayDu(v.phieu_cuoi.ngay_gui)}` : 'ngừng';
  if (!v.han) return 'chưa đặt hạn — Ban ISO đặt hạn ở màn Việc định kỳ';
  if (v.con < 0) return `quá hạn ${-v.con} ngày (${ngayDu(v.han)})`;
  return `hạn ${ngayDu(v.han)} · còn ${v.con} ngày`;
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc_kiemnghiem.tong_quan', {});
  container.innerHTML = '';
  const lai = () => render(api);

  container.appendChild(el('div', 'sx-qc-top', `<div style="flex:1;min-width:0">
    <div class="sx-qc-ngay">🧪 Kế hoạch kiểm nghiệm</div>
    <div class="sx-qc-ai">KH.KN.01 · năm ${esc(dl.nam)} · mỗi sản phẩm ít nhất 1 lần / năm</div></div>`));

  const dem = (tt) => dl.ke_hoach.filter((x) => x.trang_thai === tt).length;
  const tom = el('div', 'sx-qc-chips');
  [['Quá hạn', 'quá hạn'], ['Không đạt — kiểm lại', 'không đạt'], ['Đến hạn', `đến hạn ${dl.sap_den} ngày`],
    ['Chờ kết quả', 'chờ kết quả']].forEach(([tt, ten]) => {
    const n = dem(tt);
    if (n) tom.appendChild(chip(`${n} ${ten}`, KIEU[tt]));
  });
  const chua = dl.ke_hoach.filter((x) => !x.lan_cuoi).length;
  if (chua) tom.appendChild(chip(`${chua} chưa gửi lần nào — hạn ${ngayDu(dl.han_dau)}`, 'han'));
  [['Quá hạn', 'mẫu nước / NL / khác quá hạn'], ['Sắp đến hạn', 'mẫu nước / NL / khác đến hạn'],
    ['Chưa đặt hạn', 'việc kiểm nghiệm chưa đặt hạn']].forEach(([tt, ten]) => {
    const n = dl.viec.filter((v) => v.trang_thai === tt).length;
    if (n) tom.appendChild(chip(`${n} ${ten}`, KIEU_VIEC[tt]));
  });
  container.appendChild(tom);

  // ── sản phẩm ─────────────────────────────────────────────────────────
  const khoiSp = el('div', 'sx-dv-nhom');
  khoiSp.appendChild(el('div', 'sx-dv-khu', `Sản phẩm (bộ tự công bố) — ${dl.ke_hoach.length}`));
  if (!dl.ke_hoach.length) khoiSp.appendChild(khungTrong('Chưa có danh mục sản phẩm tự công bố.'));
  dl.ke_hoach.forEach((x) => khoiSp.appendChild(veSp(x, dl, api, lai)));
  container.appendChild(khoiSp);

  // ── nước, nguyên liệu, khác: việc kiểm nghiệm định kỳ (W35) ─────────────
  const khoiV = el('div', 'sx-dv-nhom');
  khoiV.appendChild(el('div', 'sx-dv-khu', `Nước · nguyên liệu · khác (KH.KN.01) — ${dl.viec.length}`));
  if (!dl.viec.length) {
    khoiV.appendChild(el('div', 'sx-qc-goiy', 'Chưa khai việc kiểm nghiệm định kỳ nào — Ban ISO khai ở màn Việc định kỳ '
      + '(ô "Kiểm nghiệm — mẫu của").'));
  }
  dl.viec.forEach((v) => khoiV.appendChild(veViec(v, dl, api, lai)));
  container.appendChild(khoiV);

  // ── cát: chỉ khi đổi nguồn ───────────────────────────────────────────
  const khoiCat = el('div', 'sx-dv-nhom');
  khoiCat.appendChild(el('div', 'sx-dv-khu', 'Cát rang — chỉ kiểm khi đổi nguồn'));
  if (!dl.cat.length) {
    khoiCat.appendChild(el('div', 'sx-qc-goiy', 'Không có lần đổi nguồn cát nào đang chờ kết quả kim loại nặng.'));
  }
  dl.cat.forEach((c) => {
    const the = el('div', 'sx-qc-sc sx-qc-sc-mo');
    the.appendChild(el('div', 'sx-qc-sc-ten', `Đổi nguồn ${esc(ngayDu(c.ngay))} · ${esc(c.ten_ncc || c.ncc_cat)}`));
    the.appendChild(el('div', 'sx-qc-goiy', `Kim loại nặng: <b>${esc(c.kln || 'chưa gửi mẫu')}</b>${
      c.phieu ? ` · phiếu ${esc(c.phieu)} gửi ${esc(ngayDu(c.ngay_gui))}` : ''} · lọ mẫu: ${c.luu_lo_mau ? 'đã lưu' : 'CHƯA LƯU'}`));
    if (dl.duoc_ghi) {
      const nut = el('div', 'sx-qc-chips sx-tb-nut');
      const b = el('button', 'sx-btn sx-btn-primary', c.phieu ? 'GHI KẾT QUẢ' : 'GỬI MẪU CÁT');
      b.type = 'button';
      b.addEventListener('click', () => {
        if (c.phieu) moKetQua(dl.phieu.find((p) => p.name === c.phieu) || { name: c.phieu, ten_san_pham: 'Cát rang' }, dl, api, lai);
        else moGui({ doi_tuong: 'Cát rang', nhat_ky_cat: c.name, ten: `Cát ${c.ten_ncc || c.ncc_cat} (đổi nguồn ${ngayDu(c.ngay)})`,
          chi_tieu: 'Kim loại nặng' }, dl, api, lai);
      });
      nut.appendChild(b);
      the.appendChild(nut);
    }
    khoiCat.appendChild(the);
  });
  container.appendChild(khoiCat);

  if (dl.duoc_ghi) {
    const khac = el('button', 'sx-btn sx-btn-ghost', '+ GỬI MẪU KHÁC (nguyên liệu, nước…)');
    khac.type = 'button';
    khac.addEventListener('click', () => moGui({ doi_tuong: '' }, dl, api, lai));
    container.appendChild(khac);
  }

  // ── phiếu trong năm ──────────────────────────────────────────────────
  const tenViec = Object.fromEntries(dl.viec.map((v) => [v.name, v.ten]));
  const khoiP = el('div', 'sx-dv-nhom');
  khoiP.appendChild(el('div', 'sx-dv-khu', `Phiếu gửi mẫu năm ${esc(dl.nam)} (${dl.phieu.length})`));
  if (!dl.phieu.length) khoiP.appendChild(el('div', 'sx-qc-goiy', 'Chưa gửi mẫu nào trong năm.'));
  dl.phieu.forEach((p) => {
    const the = el('div', `sx-qc-sc ${p.ket_qua === 'Không đạt' ? 'sx-qc-sc-mo' : 'sx-qc-sc-dong'} sx-cat-dong`);
    the.tabIndex = 0;
    the.setAttribute('role', 'button');
    the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(ngayDu(p.ngay_gui))} · ${esc(p.ten_san_pham || tenViec[p.viec_dinh_ky]
      || p.doi_tuong)}`));
    const meta = el('div', 'sx-qc-sc-meta');
    meta.appendChild(chip(p.ket_qua || 'chờ kết quả', p.ket_qua === 'Đạt' ? 'dong' : (p.ket_qua ? 'cao' : '')));
    if (p.so_phieu) meta.appendChild(chip(`phiếu ${p.so_phieu}`));
    if (p.phong_kn) meta.appendChild(el('span', null, esc(p.phong_kn)));
    the.appendChild(meta);
    if (p.chi_tieu || p.mo_ta_mau) the.appendChild(el('div', 'sx-qc-goiy', esc([p.mo_ta_mau, p.chi_tieu].filter(Boolean).join(' — '))));
    if (p.su_co) the.appendChild(el('div', 'sx-qc-goiy', `Phiếu sự cố: <b>${esc(p.su_co)}</b>`));
    the.addEventListener('click', () => moKetQua(p, dl, api, lai));
    khoiP.appendChild(the);
  });
  container.appendChild(khoiP);

  const inB = el('button', 'sx-btn sx-btn-ghost', `🖨 IN KH.KN.01 — năm ${esc(dl.nam)}`);
  inB.type = 'button';
  inB.addEventListener('click', () => inTo(api, 'sx.api.qc_kiemnghiem.in_kh_kn01', { nam: dl.nam }, 'KH.KN.01'));
  container.appendChild(inB);
}

function veSp(x, dl, api, lai) {
  const xau = x.trang_thai === 'Quá hạn' || x.trang_thai === 'Không đạt — kiểm lại';
  const the = el('div', `sx-qc-sc ${xau ? 'sx-qc-sc-mo' : 'sx-qc-sc-dong'}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', `${x.so_cong_bo ? `${esc(x.so_cong_bo)} · ` : ''}${esc(x.ten)}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(x.trang_thai, KIEU[x.trang_thai]));
  meta.appendChild(el('span', null, x.con < 0 ? `<b>quá hạn ${-x.con} ngày</b> (${esc(ngayDu(x.han))})`
    : `lần sau ${esc(ngayDu(x.han))} · còn ${x.con} ngày`));
  the.appendChild(meta);
  the.appendChild(el('div', 'sx-qc-goiy', x.lan_cuoi
    ? `Gửi gần nhất ${esc(ngayDu(x.lan_cuoi))}: <b>${esc(x.ket_qua || 'chờ kết quả')}</b>${
      x.trang_thai === 'Chờ kết quả' ? ` · đã chờ ${x.cho_ngay} ngày` : ''}`
    : `Chưa gửi mẫu lần nào — gửi trước ${esc(ngayDu(dl.han_dau))}.`));
  if (dl.duoc_ghi) {
    const nut = el('div', 'sx-qc-chips sx-tb-nut');
    const cho = x.trang_thai === 'Chờ kết quả';
    const b = el('button', 'sx-btn sx-btn-primary', cho ? 'GHI KẾT QUẢ' : 'GỬI MẪU');
    b.type = 'button';
    b.addEventListener('click', () => {
      if (cho) moKetQua(dl.phieu.find((p) => p.name === x.phieu_cuoi) || { name: x.phieu_cuoi, ten_san_pham: x.ten }, dl, api, lai);
      else moGui({ doi_tuong: 'Sản phẩm', san_pham: x.san_pham, ten: x.ten }, dl, api, lai);
    });
    nut.appendChild(b);
    the.appendChild(nut);
  }
  return the;
}

function veViec(v, dl, api, lai) {
  const p = v.phieu_cuoi;
  const the = el('div', `sx-qc-sc ${v.trang_thai === 'Quá hạn' ? 'sx-qc-sc-mo' : 'sx-qc-sc-dong'}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', esc(v.ten)));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(v.trang_thai === 'Ngừng' && p ? 'Đã gửi mẫu' : v.trang_thai, KIEU_VIEC[v.trang_thai]));
  meta.appendChild(chip(`${v.doi_tuong_kn} · ${v.tan_suat}`));
  meta.appendChild(el('span', null, esc(hanViec(v))));
  the.appendChild(meta);
  if (v.mo_ta) the.appendChild(el('div', 'sx-qc-goiy', esc(v.mo_ta)));
  if (p) {
    the.appendChild(el('div', 'sx-qc-goiy', `Gửi gần nhất ${esc(ngayDu(p.ngay_gui))}: <b>${esc(p.ket_qua || 'chờ kết quả')}</b>${
      p.so_phieu ? ` · phiếu ${esc(p.so_phieu)}` : ''}`));
  }
  const cho = !!(p && !p.ket_qua);
  if (dl.duoc_ghi && (cho || v.trang_thai !== 'Ngừng')) {
    const nut = el('div', 'sx-qc-chips sx-tb-nut');
    const b = el('button', 'sx-btn sx-btn-primary', cho ? 'GHI KẾT QUẢ' : 'GỬI MẪU');
    b.type = 'button';
    b.addEventListener('click', () => {
      if (cho) moKetQua(dl.phieu.find((x) => x.name === p.name) || { name: p.name, ten_san_pham: v.ten }, dl, api, lai);
      else moGui({ doi_tuong: v.doi_tuong_kn, viec_dinh_ky: v.name, ten: v.ten, chi_tieu: v.mo_ta }, dl, api, lai);
    });
    nut.appendChild(b);
    the.appendChild(nut);
  }
  return the;
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

function moGui(m0, dl, api, lai) {
  const m = openModal({ kicker: 'GỬI MẪU KIỂM NGHIỆM · KH.KN.01', title: m0.ten || 'Mẫu khác' });
  let doiTuong = m0.doi_tuong;
  if (!doiTuong) {
    m.body.appendChild(el('div', 'sx-qc-goiy', 'Mẫu của'));
    m.body.appendChild(segment(['Nguyên liệu', 'Nước', 'Cát rang', 'Khác'], '', (v) => { doiTuong = v; }, false));
  }
  const ng = oNhap(m.body, 'Ngày gửi mẫu', dl.hom_nay, 'date');
  ng.max = dl.hom_nay;
  const mau = oNhap(m.body, doiTuong === 'Sản phẩm' ? 'Mẫu (lô / HSD)' : 'Mẫu (mô tả, lô)', '');
  const dv = oNhap(m.body, 'Đơn vị kiểm nghiệm', '');
  const ct = oNhap(m.body, 'Chỉ tiêu (theo TCCS / yêu cầu)', m0.chi_tieu || '', 'ta');
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'GHI GỬI MẪU');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!doiTuong) { toastErr('Chọn mẫu của gì.'); return; }
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc_kiemnghiem.gui_mau', {
        payload: JSON.stringify({
          doi_tuong: doiTuong, san_pham: m0.san_pham || '', nhat_ky_cat: m0.nhat_ky_cat || '',
          viec_dinh_ky: m0.viec_dinh_ky || '',
          ngay_gui: ng.value || dl.hom_nay, mo_ta_mau: mau.value, phong_kn: dv.value, chi_tieu: ct.value,
        }),
      });
      toast(`Đã ghi gửi mẫu${r.lan_sau ? ` — lần sau ${ngayDu(r.lan_sau)}` : ''}`);
      m.close();
      lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

function moKetQua(p, dl, api, lai) {
  const m = openModal({ kicker: `PHIẾU ${p.name}${p.ngay_gui ? ` · gửi ${ngayDu(p.ngay_gui)}` : ''}`,
    title: p.ten_san_pham || p.doi_tuong || 'Kết quả kiểm nghiệm' });
  if (p.mo_ta_mau || p.chi_tieu || p.phong_kn) {
    m.body.appendChild(el('div', 'sx-modal-msg', esc([p.mo_ta_mau, p.chi_tieu, p.phong_kn].filter(Boolean).join(' · '))));
  }
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Kết quả (Không đạt → app lập phiếu sự cố)'));
  let kq = p.ket_qua || '';
  m.body.appendChild(segment(['Đạt', 'Không đạt'], kq, (v) => { kq = v; }, !dl.duoc_ghi, true));
  const nk = oNhap(m.body, 'Ngày có kết quả', p.ngay_kq || dl.hom_nay, 'date');
  nk.max = dl.hom_nay;
  const so = oNhap(m.body, 'Số phiếu kết quả', p.so_phieu || '');
  const gc = oNhap(m.body, 'Ghi chú', p.ghi_chu || '', 'ta');
  if (!dl.duoc_ghi) {
    [nk, so, gc].forEach((n) => { n.disabled = true; });
    return;
  }
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU KẾT QUẢ');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc_kiemnghiem.ghi_ket_qua', {
        name: p.name, payload: JSON.stringify({ ket_qua: kq, ngay_kq: kq ? nk.value : '', so_phieu: so.value, ghi_chu: gc.value }),
      });
      toast(r.su_co ? `Đã lưu — KHÔNG ĐẠT · phiếu sự cố ${r.su_co}` : 'Đã lưu kết quả');
      m.close();
      lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
  if (dl.la_iso || (p.nguoi_ghi === dl.user && p.creation === dl.hom_nay)) {
    const xoa = el('button', 'sx-btn sx-btn-ghost', 'XOÁ PHIẾU (ghi nhầm)');
    xoa.type = 'button';
    xoa.addEventListener('click', () => {
      m.close();
      confirm2Step({
        title: `Xoá phiếu gửi mẫu ${p.name}?`, message: 'Kế hoạch tính lại hạn theo các phiếu còn lại.',
        confirmLabel: 'XOÁ',
        onConfirm: async () => { await api.call('sx.api.qc_kiemnghiem.xoa', { name: p.name }); toast('Đã xoá'); lai(); },
      });
    });
    m.body.appendChild(xoa);
  }
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
