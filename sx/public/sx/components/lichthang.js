// Lịch tháng dùng chung cho tab Ghi hộp / Ghi sổ / Nhập kho (D108).
//
// Ô ngày chỉ hiện MỘT con số — đủ để nhìn ra "hôm nào chưa ghi" (ô trống) và
// "hôm nào số lạ" (lệch hẳn mấy ngày xung quanh). Bấm vào ô thì xem chi tiết.
// Ô trống KHÔNG ghi 0: 0 trông như "đã ghi, bằng không", còn trống là chưa ai ghi.
//
// Gập lại mặc định: lịch cao gần một màn điện thoại, mở sẵn là đẩy phần nhập liệu
// xuống — mà nhập liệu mới là việc chính của tab. Nhớ trạng thái mở theo từng tab.
//
// Server: sx/api/lich.py — chi tiết về cùng một khuôn cho cả ba loại, nên ở đây
// chỉ có MỘT cách vẽ.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';

const THU = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];
const KHOA_MO = 'sx-lich-mo-';

const pad = (n) => String(n).padStart(2, '0');
const iso = (y, m, d) => `${y}-${pad(m)}-${pad(d)}`;

/** Số trong ô ngày: ô chỉ rộng ~44px trên điện thoại 360px. Đến 9.999 hiện đủ
 *  (chữ nhỏ dần theo độ dài), từ 10.000 rút gọn "12,4k" — số đầy đủ ở chi tiết. */
function veSo(n) {
  const v = Math.round(n * 10) / 10;
  const chu = v >= 10000 ? `${formatNumber(Math.round(v / 100) / 10)}k` : formatNumber(v);
  const co = chu.length >= 5 ? ' sx-lich-so-dai' : '';
  return `<span class="sx-lich-so${co}">${esc(chu)}</span>`;
}

function docMo(loai) {
  try { return localStorage.getItem(KHOA_MO + loai) === '1'; } catch (e) { return false; }
}
function ghiMo(loai, mo) {
  try { localStorage.setItem(KHOA_MO + loai, mo ? '1' : '0'); } catch (e) { /* bỏ qua */ }
}

/**
 * @param api      cardApi của shell ({container, call, boot, doiNgay})
 * @param loai     'vaohop' | 'ghiso' | 'nhapkho'
 * @param tieuDe   chữ trên nút gập
 * @param moNgay   true = trong chi tiết có nút "Mở ngày này" (tab theo ngày)
 */
export async function renderLich(api, { loai, tieuDe, moNgay = false }) {
  const { container, call, boot } = api;
  container.className = 'sx-card sx-lich';
  const goc = (boot && (boot.ngay_xem || boot.hom_nay)) || new Date().toISOString().slice(0, 10);
  const homNay = (boot && boot.hom_nay) || goc;
  const st = { nam: Number(goc.slice(0, 4)), thang: Number(goc.slice(5, 7)), mo: docMo(loai) };

  const nut = el('button', 'sx-lich-nut');
  nut.type = 'button';
  const than = el('div', 'sx-lich-than');
  container.appendChild(nut);
  container.appendChild(than);

  const veNut = (tong, donVi) => {
    nut.innerHTML = `<span>📅 ${esc(tieuDe)}</span><span class="sx-lich-tong">${
      tong != null ? `${formatNumber(tong)} ${esc(donVi || '')} · ` : ''}${st.mo ? '▲' : '▼'}</span>`;
    nut.setAttribute('aria-expanded', st.mo ? 'true' : 'false');
  };
  nut.addEventListener('click', () => {
    st.mo = !st.mo;
    ghiMo(loai, st.mo);
    if (st.mo) taiThang(); else { than.innerHTML = ''; veNut(null); }
  });

  async function taiThang() {
    than.innerHTML = '<div class="sx-muted">Đang tải…</div>';
    let dl;
    try {
      dl = await call('sx.api.lich.thang', { loai, nam: st.nam, thang: st.thang });
    } catch (e) {
      than.innerHTML = '';
      than.appendChild(el('div', 'sx-error-box', esc(e.message)));
      return;
    }
    veNut(dl.tong, dl.don_vi);
    veLich(dl);
  }

  function doiThang(buoc) {
    st.thang += buoc;
    if (st.thang < 1) { st.thang = 12; st.nam -= 1; }
    if (st.thang > 12) { st.thang = 1; st.nam += 1; }
    taiThang();
  }

  function veLich(dl) {
    than.innerHTML = '';
    const dau = el('div', 'sx-lich-dau');
    const lui = el('button', 'sx-icon-btn', '‹');
    lui.type = 'button';
    lui.setAttribute('aria-label', 'Tháng trước');
    lui.addEventListener('click', () => doiThang(-1));
    const toi = el('button', 'sx-icon-btn', '›');
    toi.type = 'button';
    toi.setAttribute('aria-label', 'Tháng sau');
    toi.addEventListener('click', () => doiThang(1));
    dau.appendChild(lui);
    dau.appendChild(el('div', 'sx-lich-ten',
      `Tháng ${st.thang}/${st.nam} · <b>${formatNumber(dl.tong)}</b> ${esc(dl.don_vi)}`));
    dau.appendChild(toi);
    than.appendChild(dau);

    const luoi = el('div', 'sx-lich-luoi');
    THU.forEach((t) => luoi.appendChild(el('div', 'sx-lich-thu', t)));
    const so = new Date(st.nam, st.thang, 0).getDate();
    const thuDau = (new Date(st.nam, st.thang - 1, 1).getDay() + 6) % 7;   // T2 = 0
    for (let i = 0; i < thuDau; i += 1) luoi.appendChild(el('div', 'sx-lich-o sx-lich-rong'));
    for (let d = 1; d <= so; d += 1) {
      const k = iso(st.nam, st.thang, d);
      const x = dl.ngay[k];
      const o = el('button', `sx-lich-o${x ? ' sx-lich-co' : ''}${k === homNay ? ' sx-lich-nay' : ''}`
        + `${x && x.chot ? ' sx-lich-chot' : ''}`);
      o.type = 'button';
      o.innerHTML = `<span class="sx-lich-d">${d}</span>`
        + (x && x.so ? veSo(x.so) : '');
      o.setAttribute('aria-label', `Ngày ${d}: ${x && x.so ? `${x.so} ${dl.don_vi}` : 'chưa ghi'}`);
      o.addEventListener('click', () => moChiTiet(k));
      luoi.appendChild(o);
    }
    than.appendChild(luoi);
    than.appendChild(el('div', 'sx-muted sx-lich-chu',
      `Ô trống = chưa ghi · viền xanh = đã chốt · bấm một ngày để xem chi tiết`));
  }

  async function moChiTiet(ngay) {
    let ct;
    try { ct = await call('sx.api.lich.chi_tiet', { loai, ngay }); } catch (e) {
      toastErr(e.message); return;
    }
    const m = openModal({ kicker: tieuDe, title: `${ngay.slice(8)}/${ngay.slice(5, 7)}/${ngay.slice(0, 4)}` });
    const tong = el('div', 'sx-lich-ct-tong',
      `<b>${formatNumber(ct.so)}</b> ${esc(ct.don_vi)}`);
    m.body.appendChild(tong);
    if (ct.chips.length) {
      const chips = el('div', 'sx-qc-chips');
      ct.chips.forEach((c) => chips.appendChild(el('span', 'sx-qc-tag', esc(c))));
      m.body.appendChild(chips);
    }
    if (!ct.khoi.length) m.body.appendChild(el('div', 'sx-muted', 'Ngày này chưa có gì được ghi.'));
    ct.khoi.forEach((k) => {
      m.body.appendChild(el('div', 'sx-field-label', esc(k.ten)));
      const ds = el('div', 'sx-vh-list');
      k.dong.forEach((r) => {
        ds.appendChild(el('div', 'sx-vh-row', `
          <div class="sx-vh-who"><div class="sx-vh-name">${esc(r.trai)}</div>
            ${r.phu ? `<div class="sx-vh-meta">${esc(r.phu)}</div>` : ''}</div>
          <span class="sx-nv-qty">${esc(typeof r.phai === 'number' ? formatNumber(r.phai) : r.phai)}</span>`));
      });
      m.body.appendChild(ds);
    });
    if (moNgay && api.doiNgay) {
      const nutMo = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'MỞ NGÀY NÀY ĐỂ SỬA');
      nutMo.type = 'button';
      nutMo.addEventListener('click', () => { m.close(); api.doiNgay(ngay); });
      m.body.appendChild(nutMo);
    }
  }

  veNut(null);
  if (st.mo) taiThang();
}
