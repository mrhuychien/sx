// #/qc/vaiu — sổ giặt vải ủ BM.08.05 (W29, D163).
//
// Mỗi việc MỘT dòng: giặt định kỳ (1 lần/tuần) / giặt ngoài lịch / nhập vải mới / loại vải. Người giặt
// có thể không có tài khoản: QC ghi hộ và KÝ — giặt mà đun sôi chưa đủ 10 phút tính từ lúc nước sôi lại
// thì không ký được. Tab Danh mục vải: QLSX / Ban ISO khai vải (mã theo thùng: V01-A, V01-B), đổi Đang
// dùng ↔ Dự phòng; loại vải chỉ qua dòng Loại vải. Trưởng Ban ISO bấm "Đã xem tháng".
// Luật ở sx/qc/vai_u.py + controller SX Giat Vai / SX Vai U; màn này chỉ ghi và xem.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment } from '/assets/sx/sx/components/qcui.js';

// Tháng đang xem ('YYYY-MM', null = tháng này) và tab. Ngoài render: in xong quay lại không mất.
const st = { thang: null, tab: 'so' };

const GIAT = ['Giặt định kỳ', 'Giặt ngoài lịch'];
const CAN_LY_DO = ['Giặt ngoài lịch', 'Loại vải'];
const ngayVN = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}` : '');
const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const thangVN = (t) => `${t.slice(5)}/${t.slice(0, 4)}`;

function congThang(t, n) {
  const [y, m] = t.split('-').map(Number);
  const d = new Date(Date.UTC(y, m - 1 + n, 1));
  return d.toISOString().slice(0, 7);
}

function soNgay(tu, den) {
  return Math.round((Date.parse(`${den}T00:00:00Z`) - Date.parse(`${tu}T00:00:00Z`)) / 86400000);
}

/** Số phút đun sôi từ hai ô giờ — như sx/qc/vai_u.so_phut: vớt qua nửa đêm thì cộng 24 giờ. */
export function soPhut(soi, vot) {
  const p = (t) => {
    const m = /^(\d{1,2}):(\d{2})/.exec(t || '');
    return m && Number(m[1]) < 24 && Number(m[2]) < 60 ? Number(m[1]) * 60 + Number(m[2]) : null;
  };
  const a = p(soi);
  const b = p(vot);
  if (a == null || b == null) return null;
  return (((b - a) % 1440) + 1440) % 1440;
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc_vaiu.tong_quan', st.thang ? { thang: st.thang } : {});
  container.innerHTML = '';
  const lai = () => render(api);
  const thangNay = dl.hom_nay.slice(0, 7);

  // ── đầu màn: tháng đang xem ──────────────────────────────────────────
  const top = el('div', 'sx-qc-top sx-dv-tuan');
  const lui = el('button', 'sx-btn sx-btn-ghost', '‹');
  lui.type = 'button';
  lui.title = 'Tháng trước';
  lui.addEventListener('click', () => { st.thang = congThang(dl.thang, -1); lai(); });
  const tien = el('button', 'sx-btn sx-btn-ghost', '›');
  tien.type = 'button';
  tien.title = 'Tháng sau';
  tien.disabled = dl.thang >= thangNay;
  tien.addEventListener('click', () => {
    const t = congThang(dl.thang, 1);
    st.thang = t >= thangNay ? null : t;
    lai();
  });
  top.appendChild(lui);
  top.appendChild(el('div', 'sx-dv-tuan-ten', `<div class="sx-qc-ngay">🧺 Sổ giặt vải ủ</div>
    <div class="sx-qc-ai">BM.08.05 · tháng ${esc(thangVN(dl.thang))}${dl.thang === thangNay ? '' : ' · <b>tháng cũ</b>'}</div>`));
  top.appendChild(tien);
  container.appendChild(top);

  const than = el('div', 'sx-qc-than');
  const veTab = () => {
    than.innerHTML = '';
    if (st.tab === 'vai') veDanhMuc(than, dl, api, lai);
    else veSo(than, dl, api, lai);
  };
  const conDung = dl.vai.filter((v) => v.trang_thai !== 'Đã loại').length;
  const tab = segment([{ v: 'so', ten: 'Sổ giặt' }, { v: 'vai', ten: `Danh mục vải (${conDung})` }],
    st.tab, (v) => { st.tab = v || 'so'; veTab(); }, false);
  tab.classList.add('sx-vu-tab');
  container.appendChild(tab);
  container.appendChild(than);
  veTab();
}

// ── tab Sổ giặt ──────────────────────────────────────────────────────────
function veSo(box, dl, api, lai) {
  const cd = dl.cai_dat;
  const dang = dl.vai.filter((v) => v.trang_thai === 'Đang dùng');
  const duPhong = dl.vai.filter((v) => v.trang_thai === 'Dự phòng');
  const the = el('div', 'sx-qc-sc sx-cat-hien');
  the.appendChild(el('div', 'sx-qc-goiy', cd.giat_moi_lan ? 'GIẶT SAU MỖI LẦN DÙNG (thẩm tra không đạt) — LẦN GẦN NHẤT'
    : 'GIẶT ĐỊNH KỲ GẦN NHẤT'));
  if (dl.lan_cuoi) {
    const n = soNgay(dl.lan_cuoi, dl.hom_nay);
    the.appendChild(el('div', 'sx-cat-so', `${esc(ngayDu(dl.lan_cuoi))} <small>· ${n === 0 ? 'hôm nay' : `${n} ngày trước`}</small>`));
    if (dang.length && n > dl.chu_ky) {
      the.appendChild(el('div', 'sx-vu-qua', `⚠ Quá ${esc(dl.chu_ky)} ngày chưa giặt — giặt, đun sôi toàn bộ vải đang dùng.`));
    }
  } else {
    the.appendChild(el('div', 'sx-qc-sc-ten', 'Sổ chưa có lần giặt định kỳ nào'));
  }
  the.appendChild(el('div', 'sx-cat-nguon', `Chu kỳ: ${cd.giat_moi_lan ? 'sau mỗi lần dùng' : '1 lần/tuần'}${
    cd.thu_giat ? ` · ngày giặt <b>${esc(cd.thu_giat)}</b>` : ' · chưa chọn ngày giặt cố định (QLSX)'}${
    cd.noi_giat ? ` · giặt tại ${esc(cd.noi_giat)}` : ''}`));
  the.appendChild(el('div', 'sx-cat-nguon', dl.vai.length
    ? `${dang.length} vải đang dùng · ${duPhong.length} dự phòng`
    : 'Chưa khai vải ủ — QLSX / Ban ISO khai ở tab Danh mục vải. Chưa khai vải đang dùng thì app không nhắc giặt.'));
  box.appendChild(the);

  if (dl.duoc_ghi) {
    const nut = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'GHI GIẶT ĐỊNH KỲ');
    nut.type = 'button';
    nut.addEventListener('click', () => moGhi(dl, null, 'Giặt định kỳ', api, lai));
    box.appendChild(nut);
    const hang = el('div', 'sx-qc-luoi-so');
    [['Giặt ngoài lịch', 'vải ẩm, mùi, ố, rách…'], ['Nhập vải mới', 'vào danh mục: dự phòng'],
      ['Loại vải', 'vải hỏng → đã loại']].forEach(([v, phu]) => {
      const b = el('button', 'sx-btn sx-btn-ghost', `${esc(v)}<small>${esc(phu)}</small>`);
      b.type = 'button';
      b.addEventListener('click', () => moGhi(dl, null, v, api, lai));
      hang.appendChild(b);
    });
    box.appendChild(hang);
  } else {
    box.appendChild(el('div', 'sx-qc-goiy', 'Bạn chỉ có quyền xem — QC ghi và ký sổ giặt vải ủ.'));
  }

  box.appendChild(el('div', 'sx-dv-khu', `Các dòng trong tháng (${dl.ds.length})`));
  if (!dl.ds.length) box.appendChild(khungTrong('Tháng này chưa có dòng nào.'));
  dl.ds.forEach((x) => box.appendChild(veDong(x, dl, api, lai)));

  veXem(box, dl, api, lai);

  const inB = el('button', 'sx-btn sx-btn-ghost', `🖨 IN BM.08.05 — tháng ${esc(thangVN(dl.thang))}`);
  inB.type = 'button';
  inB.addEventListener('click', () => inTo(api, 'sx.api.qc_vaiu.in_bm0805', { thang: dl.thang }, 'BM.08.05'));
  box.appendChild(inB);
}

/** Chip số phút đun sôi: dưới ngưỡng là chữ đỏ — chính là lý do QC không ký được. */
export function chipDun(x, phutSoi) {
  if (!(x.gio_soi_lai && x.gio_vot)) return GIAT.includes(x.viec) ? chip('chưa ghi giờ đun', 'mo') : null;
  const n = soPhut(x.gio_soi_lai, x.gio_vot);
  return chip(`đun ${n}′`, n < phutSoi ? 'cao' : 'dong');
}

function veDong(x, dl, api, lai) {
  const the = el('div', `sx-qc-sc sx-cat-dong${x.qc_ky_luc ? '' : ' sx-vu-cho'}`);
  the.tabIndex = 0;
  the.setAttribute('role', 'button');
  the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(ngayVN(x.ngay))} · ${esc(x.viec)}`));
  const meta = el('div', 'sx-qc-sc-meta');
  if (x.vai.length) meta.appendChild(chip(x.vai.join(', ')));
  if (x.so_luong) meta.appendChild(chip(`${x.so_luong} vải`));
  const dun = chipDun(x, dl.phut_soi);
  if (dun) meta.appendChild(dun);
  meta.appendChild(x.qc_ky_luc ? chip('QC đã ký', 'dong') : chip('CHỜ QC KÝ', 'mo'));
  if (x.xem_luc) meta.appendChild(chip('đã xem'));
  meta.appendChild(el('span', null, esc(x.nguoi_lam || '')));
  the.appendChild(meta);
  if (x.ly_do) the.appendChild(el('div', 'sx-qc-goiy', esc(x.ly_do)));
  if (x.su_co) the.appendChild(el('div', 'sx-qc-goiy', `Phiếu sự cố: <b>${esc(x.su_co)}</b>`));
  the.addEventListener('click', () => moGhi(dl, x, x.viec, api, lai));
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

/** Chọn mã vải: nút bật / tắt từng vải trong danh mục (không gõ tay — gõ tay thì "v01a" và "V01-A"
 *  là hai vải). Vải đã loại không hiện, trừ khi dòng đang xem đã ghi nó. */
function chonVai(box, dl, chon, khoa) {
  box.innerHTML = '';
  const ds = dl.vai.filter((v) => v.trang_thai !== 'Đã loại' || chon.has(v.ma));
  if (!ds.length) {
    box.appendChild(el('div', 'sx-qc-goiy', 'Danh mục chưa có vải nào — ghi số lượng; QLSX / Ban ISO khai vải ở tab Danh mục vải.'));
    return;
  }
  const hang = el('div', 'sx-qc-vi');
  ds.forEach((v) => {
    const b = el('button', `sx-qc-vi-o${chon.has(v.ma) ? ' sx-qc-vi-on' : ''}`,
      `${chon.has(v.ma) ? '✓ ' : ''}${esc(v.ma)}${v.trang_thai === 'Dự phòng' ? ' <small>dự phòng</small>' : ''}`);
    b.type = 'button';
    b.disabled = !!khoa;
    b.setAttribute('aria-pressed', chon.has(v.ma) ? 'true' : 'false');
    b.addEventListener('click', () => {
      if (chon.has(v.ma)) chon.delete(v.ma); else chon.add(v.ma);
      chonVai(box, dl, chon, khoa);
    });
    hang.appendChild(b);
  });
  box.appendChild(hang);
}

/** Form một dòng. x = dòng đang xem / sửa (null = dòng mới); viec0 = việc của nút vừa bấm. */
function moGhi(dl, x, viec0, api, lai) {
  const daKy = !!(x && x.qc_ky_luc);
  const khoa = daKy || !!(x && x.xem_luc);
  const sua = dl.duoc_ghi && !khoa;
  const m = openModal({ kicker: 'SỔ GIẶT VẢI Ủ BM.08.05', title: x ? `${x.viec} · ${ngayDu(x.ngay)}` : viec0 });
  if (daKy) {
    m.body.appendChild(el('div', 'sx-qc-goiy', `QC đã ký: <b>${esc(x.ten_ky || x.qc_ky_boi)}</b> · ${esc(x.qc_ky_luc)}`
      + ' — dòng đã khoá, chỉ Ban ISO sửa (trên Desk).'));
  } else if (khoa) {
    m.body.appendChild(el('div', 'sx-qc-goiy', 'Trưởng Ban ISO đã xem tháng này — nội dung dòng đã khoá.'));
  }
  let viec = (x && x.viec) || viec0;
  const ng = oNhap(m.body, 'Ngày', (x && x.ngay) || dl.hom_nay, 'date');
  ng.max = dl.hom_nay;
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Việc'));
  m.body.appendChild(segment(dl.viec, viec, (v) => { viec = v || viec; capNhat(); }, !sua));

  // Mã vải. Giặt định kỳ mới: chọn sẵn toàn bộ vải đang dùng (HD.08.02 mục 6: giặt toàn bộ vải đang dùng).
  const nhanMa = el('div', 'sx-qc-goiy');
  m.body.appendChild(nhanMa);
  const khoiMa = el('div');
  m.body.appendChild(khoiMa);
  const chon = new Set(x ? x.vai : (viec0 === 'Giặt định kỳ'
    ? dl.vai.filter((v) => v.trang_thai === 'Đang dùng').map((v) => v.ma) : []));
  const maMoi = el('input');
  maMoi.className = 'sx-textarea';
  maMoi.placeholder = 'V03-A, V03-B';
  maMoi.value = x && x.viec === 'Nhập vải mới' ? x.vai.join(', ') : '';
  const sl = oNhap(m.body, 'Số lượng vải (khi chưa có mã: vải mới chưa khâu mã, vải cũ không mã)',
    x && x.so_luong ? x.so_luong : '', 'number');
  sl.min = '0';
  sl.inputMode = 'numeric';

  const khoiLyDo = el('div');
  m.body.appendChild(khoiLyDo);
  const nhanLyDo = el('div', 'sx-qc-goiy');
  khoiLyDo.appendChild(nhanLyDo);
  const lyDo = el('textarea', 'sx-textarea');
  lyDo.rows = 2;
  lyDo.value = (x && x.ly_do) || '';
  khoiLyDo.appendChild(lyDo);

  // Đun sôi, phơi, cất — giặt và nhập vải mới (vải mới giặt, đun sôi trước lần dùng đầu).
  const khoiDun = el('div');
  m.body.appendChild(khoiDun);
  khoiDun.appendChild(el('div', 'sx-qc-goiy', `Đun sôi — tính từ lúc nước SÔI LẠI, ít nhất ${esc(dl.phut_soi)} phút`));
  const gio = el('div', 'sx-vu-gio');
  const o1 = el('div');
  const o2 = el('div');
  gio.appendChild(o1);
  gio.appendChild(o2);
  khoiDun.appendChild(gio);
  const soi = oNhap(o1, 'Giờ sôi lại', (x && x.gio_soi_lai) || '', 'time');
  const vot = oNhap(o2, 'Giờ vớt', (x && x.gio_vot) || '', 'time');
  const phut = el('div', 'sx-vu-phut');
  khoiDun.appendChild(phut);
  const tinhPhut = () => {
    const n = soPhut(soi.value, vot.value);
    const thieu = n != null && n < dl.phut_soi;
    phut.className = `sx-vu-phut${thieu ? ' sx-vu-thieu' : ''}`;
    phut.textContent = n == null ? '' : `= ${n} phút${thieu
      ? ` — chưa đủ ${dl.phut_soi} phút: đun lại cho đủ rồi ghi giờ mới (chưa ký được)` : ' ✓'}`;
  };
  soi.addEventListener('input', tinhPhut);
  vot.addEventListener('input', tinhPhut);
  const phoi = oNhap(khoiDun, 'Phơi tại (giá riêng, mái che, lưới chắn chim)', x ? x.phoi_tai : (dl.phoi_tai || ''));
  const cat = oNhap(khoiDun, 'Khô hẳn, cất lúc (còn ẩm thì không cất)', x && x.cat_luc ? x.cat_luc.replace(' ', 'T') : '',
    'datetime-local');

  const lam = oNhap(m.body, 'Người làm (người giặt)', x ? x.nguoi_lam : (dl.cai_dat.nguoi_giat || ''));
  let suCo = (x && x.su_co) || '';
  const dsSuCo = dl.su_co.concat(suCo && !dl.su_co.find((s) => s.name === suCo) ? [{ name: suCo, ngay: '', mo_ta: '' }] : []);
  let chonSuCo = null;
  if (dsSuCo.length) {
    m.body.appendChild(el('div', 'sx-qc-goiy', 'Phiếu sự cố liên quan (nếu có — vải rách, thiếu mảnh, dính dấu chuột…)'));
    chonSuCo = el('select', 'sx-textarea');
    [{ name: '', ngay: '', mo_ta: '— không —' }].concat(dsSuCo).forEach((s) => {
      const o = el('option', null, esc(s.name ? `${s.name} · ${ngayVN(s.ngay)} ${s.mo_ta}` : s.mo_ta));
      o.value = s.name;
      if (s.name === suCo) o.selected = true;
      chonSuCo.appendChild(o);
    });
    chonSuCo.addEventListener('change', () => { suCo = chonSuCo.value; });
    m.body.appendChild(chonSuCo);
  }

  const capNhat = () => {
    const nhap = viec === 'Nhập vải mới';
    nhanMa.textContent = nhap ? 'Mã vải mới (cách nhau dấu phẩy) — mã chưa có thì app thêm vào danh mục, Dự phòng'
      : 'Mã vải';
    khoiMa.innerHTML = '';
    if (nhap) khoiMa.appendChild(maMoi);
    else chonVai(khoiMa, dl, chon, !sua);
    khoiLyDo.style.display = CAN_LY_DO.includes(viec) ? '' : 'none';
    nhanLyDo.textContent = viec === 'Loại vải' ? 'Lý do loại (thủng, rách, sờn, ố, mốc, còn mùi sau giặt, cháy xém…)'
      : 'Lý do giặt ngoài lịch (vải ẩm, có mùi, ố, đọng nước, dính dấu chuột, côn trùng…)';
    khoiDun.style.display = viec === 'Loại vải' ? 'none' : '';
  };
  capNhat();
  tinhPhut();
  if (!sua) m.body.querySelectorAll('input, select, textarea').forEach((n) => { n.disabled = true; });

  const gui = async (nut, ky) => {
    if (!ng.value) { toastErr('Chọn ngày.'); return; }
    nut.disabled = true;
    try {
      const r = await api.call('sx.api.qc_vaiu.ghi', {
        payload: JSON.stringify({
          name: x ? x.name : null, ngay: ng.value, viec,
          vai: viec === 'Nhập vải mới' ? maMoi.value : [...chon],
          so_luong: Number(sl.value) || 0, ly_do: CAN_LY_DO.includes(viec) ? lyDo.value : '',
          gio_soi_lai: viec === 'Loại vải' ? '' : soi.value, gio_vot: viec === 'Loại vải' ? '' : vot.value,
          phoi_tai: viec === 'Loại vải' ? '' : phoi.value, cat_luc: viec === 'Loại vải' ? '' : cat.value,
          nguoi_lam: lam.value, su_co: suCo, ky: ky ? 1 : 0,
        }),
      });
      toast(`Đã ghi${r.da_ky ? ' và ký' : ''}${r.vai_moi && r.vai_moi.length
        ? ` · thêm vào danh mục: ${r.vai_moi.join(', ')} (dự phòng)` : ''}${
        !r.da_ky && r.chua_ky_duoc ? ` · chưa ký được: ${r.chua_ky_duoc}` : ''}`);
      m.close();
      st.thang = ng.value.slice(0, 7) === dl.hom_nay.slice(0, 7) ? null : ng.value.slice(0, 7);
      lai();
    } catch (e) { nut.disabled = false; toastErr(e.message); }
  };
  if (sua) {
    const okKy = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU VÀ KÝ (QC)');
    okKy.type = 'button';
    okKy.addEventListener('click', () => gui(okKy, true));
    m.body.appendChild(okKy);
    const ok = el('button', 'sx-btn sx-btn-ghost', 'Lưu, ký sau');
    ok.type = 'button';
    ok.addEventListener('click', () => gui(ok, false));
    m.body.appendChild(ok);
  } else if (x && !daKy && dl.duoc_ghi) {
    // Trưởng Ban ISO đã xem tháng mà dòng chưa ký: nội dung khoá, QC vẫn ký muộn được.
    const b = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'QC KÝ DÒNG NÀY');
    b.type = 'button';
    b.addEventListener('click', async () => {
      b.disabled = true;
      try {
        await api.call('sx.api.qc_vaiu.ky', { name: x.name });
        toast('Đã ký');
        m.close();
        lai();
      } catch (e) { b.disabled = false; toastErr(e.message); }
    });
    m.body.appendChild(b);
  }
  // Ghi nhầm cả dòng: người ghi xoá được trong ngày ghi khi chưa ký; Ban ISO lúc nào cũng được.
  if (x && (dl.la_iso || (sua && x.ghi_boi === dl.user && x.creation === dl.hom_nay))) {
    const xoa = el('button', 'sx-btn sx-btn-ghost', 'XOÁ DÒNG (ghi nhầm)');
    xoa.type = 'button';
    xoa.addEventListener('click', () => {
      m.close();
      confirm2Step({
        title: `Xoá dòng ${x.viec.toLowerCase()} ngày ${ngayDu(x.ngay)}?`,
        message: x.viec === 'Nhập vải mới' || x.viec === 'Loại vải'
          ? 'Danh mục vải tính lại theo các dòng còn lại.' : 'Dòng này biến khỏi sổ giặt.',
        confirmLabel: 'XOÁ',
        onConfirm: async () => {
          await api.call('sx.api.qc_vaiu.xoa', { name: x.name });
          toast('Đã xoá');
          lai();
        },
      });
    });
    m.body.appendChild(xoa);
  }
}

// ── Trưởng Ban ISO xem tháng ─────────────────────────────────────────────
function veXem(box, dl, api, lai) {
  const k = el('div', 'sx-qc-sc');
  k.appendChild(el('div', 'sx-qc-goiy', 'TRƯỞNG BAN ISO XEM XÉT CUỐI THÁNG'));
  if (dl.xem) {
    k.appendChild(el('div', null, `<b>${esc(dl.xem.ten || dl.xem.boi)}</b> · ${esc(ngayDu(dl.xem.luc.slice(0, 10)))}${
      dl.xem.nhan_xet ? ` — ${esc(dl.xem.nhan_xet)}` : ''}`));
    if (dl.chua_xem) k.appendChild(el('div', 'sx-qc-goiy', `${dl.chua_xem} dòng ghi sau lần xem — chưa xem.`));
  } else {
    k.appendChild(el('div', 'sx-qc-goiy', dl.ds.length ? 'Chưa xem.' : 'Tháng chưa có dòng nào.'));
  }
  if (dl.duoc_xem_thang && dl.chua_xem) {
    const nx = oNhap(k, 'Nhận xét', '', 'ta');
    const b = el('button', 'sx-btn sx-btn-primary', `ĐÃ XEM THÁNG ${esc(thangVN(dl.thang))}`);
    b.type = 'button';
    b.addEventListener('click', () => confirm2Step({
      title: `Đã xem sổ giặt vải ủ tháng ${thangVN(dl.thang)}`,
      message: `Ký xem ${dl.chua_xem} dòng${dl.chua_ky ? ` — còn ${dl.chua_ky} dòng CHƯA QC KÝ` : ''}. `
        + 'Dòng đã xem thì khoá nội dung (chỉ Ban ISO sửa).',
      confirmLabel: 'ĐÃ XEM',
      onConfirm: async () => {
        await api.call('sx.api.qc_vaiu.xem_thang', { thang: dl.thang, nhan_xet: nx.value });
        toast('Đã ghi xem xét tháng');
        lai();
      },
    }));
    k.appendChild(b);
  }
  box.appendChild(k);
}

// ── tab Danh mục vải ─────────────────────────────────────────────────────
function veDanhMuc(box, dl, api, lai) {
  box.appendChild(el('div', 'sx-qc-goiy', 'Mỗi thùng có vải riêng, mã theo số thùng (thùng 01: V01-A, V01-B) — '
    + '1 vải đang dùng, 1 vải thay vào ngày giặt; thêm ít nhất 2 vải dự phòng (HD.08.02 mục 3). '
    + 'Vải hỏng: QC ghi dòng Loại vải trong sổ — app tự chuyển Đã loại.'));
  if (dl.duoc_khai_vai) {
    const b = el('button', 'sx-btn sx-btn-primary sx-btn-big', '+ KHAI VẢI');
    b.type = 'button';
    b.addEventListener('click', () => moVai(dl, null, api, lai));
    box.appendChild(b);
  } else {
    box.appendChild(el('div', 'sx-qc-goiy', 'QLSX / Ban ISO khai danh mục vải.'));
  }
  if (!dl.vai.length) {
    box.appendChild(khungTrong('Chưa khai vải nào.'));
    return;
  }
  [['Đang dùng', 'dong'], ['Dự phòng', ''], ['Đã loại', 'mo']].forEach(([tt, kieu]) => {
    const ds = dl.vai.filter((v) => v.trang_thai === tt);
    if (!ds.length) return;
    box.appendChild(el('div', 'sx-dv-khu', `${esc(tt)} (${ds.length})`));
    ds.forEach((v) => {
      const the = el('div', 'sx-qc-sc sx-cat-dong');
      the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(v.ma)}${v.thung ? ` · thùng ${esc(v.thung)}` : ''}`));
      const meta = el('div', 'sx-qc-sc-meta');
      meta.appendChild(chip(tt, kieu));
      if (v.ngay_nhap) meta.appendChild(el('span', null, `nhập ${esc(ngayDu(v.ngay_nhap))}`));
      if (v.ngay_loai) meta.appendChild(el('span', null, `loại ${esc(ngayDu(v.ngay_loai))}`));
      the.appendChild(meta);
      if (v.ly_do_loai) the.appendChild(el('div', 'sx-qc-goiy', esc(v.ly_do_loai)));
      if (v.ghi_chu) the.appendChild(el('div', 'sx-qc-goiy', esc(v.ghi_chu)));
      if (dl.duoc_khai_vai) {
        the.tabIndex = 0;
        the.setAttribute('role', 'button');
        the.addEventListener('click', () => moVai(dl, v, api, lai));
      }
      box.appendChild(the);
    });
  });
}

function moVai(dl, v, api, lai) {
  const m = openModal({ kicker: 'DANH MỤC VẢI Ủ', title: v ? v.ma : 'Khai vải' });
  const ma = oNhap(m.body, 'Mã vải (theo thùng: V01-A, V01-B…)', v ? v.ma : '');
  ma.disabled = !!v;
  const thung = oNhap(m.body, 'Thùng số (để trống: app đọc từ mã)', v ? v.thung : '');
  const daLoai = !!(v && v.trang_thai === 'Đã loại');
  let tt = v ? v.trang_thai : 'Dự phòng';
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Trạng thái'));
  if (daLoai) {
    m.body.appendChild(el('div', 'sx-qc-goiy', `<b>Đã loại</b> ngày ${esc(ngayDu(v.ngay_loai))} (dòng ${esc(v.dong_loai || '—')}). `
      + 'Vải thay mới khâu lại mã này thì QC ghi dòng Nhập vải mới.'));
  } else {
    m.body.appendChild(segment(['Đang dùng', 'Dự phòng'], tt, (x) => { tt = x || tt; }, false));
  }
  const nn = oNhap(m.body, 'Ngày nhập', v ? v.ngay_nhap : '', 'date');
  const gc = oNhap(m.body, 'Ghi chú', v ? v.ghi_chu : '', 'ta');
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!ma.value.trim()) { toastErr('Ghi mã vải.'); return; }
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc_vaiu.luu_vai', {
        payload: JSON.stringify({ ma: ma.value, thung: thung.value, trang_thai: daLoai ? null : tt,
          ngay_nhap: nn.value, ghi_chu: gc.value, moi: v ? 0 : 1 }),
      });
      toast(`Đã lưu ${r.ma}${r.thung ? ` · thùng ${r.thung}` : ''}`);
      m.close();
      lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
  if (v) {
    const xoa = el('button', 'sx-btn sx-btn-ghost', 'XOÁ (khai nhầm)');
    xoa.type = 'button';
    xoa.addEventListener('click', () => {
      m.close();
      confirm2Step({
        title: `Xoá vải ${v.ma} khỏi danh mục?`,
        message: 'Chỉ xoá được vải chưa có dòng sổ nào. Vải hỏng thì ghi dòng Loại vải.',
        confirmLabel: 'XOÁ',
        onConfirm: async () => {
          await api.call('sx.api.qc_vaiu.xoa_vai', { ma: v.ma });
          toast('Đã xoá');
          lai();
        },
      });
    });
    m.body.appendChild(xoa);
  }
}

// Cửa sổ mới, tự khai charset (about:blank không thừa kế) — cùng cách in BM.08.03.
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
