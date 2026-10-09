// #/qc/cat — nhật ký cát rang BM.08.03 (W20 D141; W32 D164: mỗi việc một dòng).
//
// Nhập cát / rang khô đưa dùng (thay toàn bộ) / bổ sung / loại cát / vệ sinh thùng, khay — một dòng, đúng cột
// giấy HD.08.03. Số ngày cát đã dùng do app ĐẾM: ngày có rang (lượt kiểm ghi nhiệt độ rang) kể từ lần rang khô
// đưa dùng gần nhất; cát bổ sung không tính lại ngày. Nhập cát của NCC khác lần trước = đổi nguồn: nhắc kiểm kim
// loại nặng + lưu lọ mẫu tới khi đủ. Số ngày tối đa chưa chốt (C19) nên chỉ đếm. Luật ở sx/qc/cat.py + controller
// SX Nhat Ky Cat; màn này chỉ ghi và xem.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment } from '/assets/sx/sx/components/qcui.js';

// Tháng đang xem ('YYYY-MM'), null = tháng này. Ngoài render: in xong quay lại không mất.
const st = { thang: null };

const NHAP = 'Nhập cát';
const RANG_KHO = 'Rang khô đưa dùng';
const BO_SUNG = 'Bổ sung';
const LOAI = 'Loại cát';
const VE_SINH = 'Vệ sinh thùng, khay';
const CAN_KL = [NHAP, RANG_KHO, BO_SUNG];
const LY_DO = ['Đủ số ngày', 'Màu sẫm đen', 'Mùi khét', 'Nhiều vụn cháy', 'Bụi nhiều (hạt vỡ mịn)',
  'Dính nước, dầu, vật lạ'];
const PHU = {
  [NHAP]: 'nguồn, số BM.07.03, kg',
  [RANG_KHO]: 'thay toàn bộ — đếm lại ngày',
  [BO_SUNG]: 'bù hao hụt — không tính lại',
  [LOAI]: 'số ngày, lý do',
  [VE_SINH]: 'thùng, khay trống',
};

const ngayVN = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}` : '');
const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const so = (v) => Number(v || 0).toLocaleString('vi-VN', { maximumFractionDigits: 2 });

function congThang(t, n) {
  const [y, m] = t.split('-').map(Number);
  const d = new Date(Date.UTC(y, m - 1 + n, 1));
  return d.toISOString().slice(0, 7);
}

/** Các ô của form theo việc (giống luật controller): nguồn, số BM.07.03, khối lượng, lý do loại, vệ sinh. */
export function oTheoViec(viec) {
  return {
    nguon: [NHAP, RANG_KHO, BO_SUNG].includes(viec),
    phieu: viec === NHAP,
    camQuan: viec === NHAP,
    kl: viec !== VE_SINH,
    canKl: CAN_KL.includes(viec),
    lyDo: viec === LOAI,
    veSinh: viec === VE_SINH,
  };
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc_cat.tong_quan', st.thang ? { thang: st.thang } : {});
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
  top.appendChild(el('div', 'sx-dv-tuan-ten', `<div class="sx-qc-ngay">♨ Nhật ký cát rang</div>
    <div class="sx-qc-ai">BM.08.03 · tháng ${esc(dl.thang.slice(5))}/${esc(dl.thang.slice(0, 4))}${
  dl.thang === thangNay ? '' : ' · <b>tháng cũ</b>'}</div>`));
  top.appendChild(tien);
  container.appendChild(top);

  // ── cát đang dùng ────────────────────────────────────────────────────
  const h = dl.hien_tai;
  const the = el('div', 'sx-qc-sc sx-cat-hien');
  the.appendChild(el('div', 'sx-qc-goiy', 'CÁT ĐANG DÙNG TRONG MÁY'));
  if (h.so_ngay != null) {
    the.appendChild(el('div', 'sx-cat-so', `Đã dùng ${esc(h.so_ngay)} ngày${
      dl.toi_da ? ` <small>/ tối đa ${esc(dl.toi_da)}</small>` : ''}`));
    the.appendChild(el('div', 'sx-cat-nguon', `Nguồn: <b>${esc(h.ten_ncc || h.ncc || '—')}</b>${
      h.ngay_thay ? ` · thay toàn bộ ${esc(ngayDu(h.ngay_thay))}` : ' · theo sổ cũ'}`));
    the.appendChild(el('div', 'sx-qc-goiy', 'App đếm ngày có rang (lượt kiểm ghi nhiệt độ rang) từ lần rang khô đưa '
      + 'dùng; cát bổ sung không tính lại ngày.'));
    if (!dl.toi_da) {
      the.appendChild(el('div', 'sx-qc-goiy', 'Chưa quy định cát dùng tối đa bao nhiêu ngày (C19) — app chỉ đếm, không nhắc.'));
    }
  } else if (h.ngay_loai) {
    the.appendChild(el('div', 'sx-qc-sc-ten', `Đã loại cát ngày ${esc(ngayDu(h.ngay_loai))}`));
    the.appendChild(el('div', 'sx-qc-goiy', 'Chưa ghi cát mới đưa vào máy — ghi "Rang khô đưa dùng".'));
  } else {
    the.appendChild(el('div', 'sx-qc-sc-ten', 'Sổ chưa có lần đưa cát vào máy'));
    the.appendChild(el('div', 'sx-qc-goiy', 'Ghi "Rang khô đưa dùng" (khai cát đang dùng đã qua mấy ngày có rang) — '
      + 'từ đó app tự đếm.'));
  }
  container.appendChild(the);

  // ── đổi nguồn còn thiếu kim loại nặng / lọ mẫu ──────────────────────────
  if (dl.cho_kln.length) {
    const box = el('div', 'sx-qc-nhac');
    dl.cho_kln.forEach((x) => {
      const o = el('div', `sx-qc-nhac-o sx-qc-nhac-${x.kln ? 'thuong' : 'cao'}`);
      const thieu = [];
      if (x.kln !== 'Đạt') thieu.push(x.kln ? 'chờ kết quả kim loại nặng' : 'CHƯA gửi mẫu kim loại nặng');
      if (!x.luu_lo_mau) thieu.push('chưa lưu lọ mẫu');
      o.innerHTML = `<div class="sx-qc-nhac-ten">⚠ Đổi nguồn cát ${esc(ngayVN(x.ngay))}: ${esc(thieu.join(' · '))}</div>
        <div class="sx-qc-nhac-ct">Nguồn ${esc(x.ten_ncc || x.ncc_cat)}. Đổi nguồn phải kiểm kim loại nặng (trước khi dùng) và lưu một lọ mẫu.</div>`;
      if (dl.duoc_ghi || dl.la_iso) {
        const b = el('button', 'sx-btn sx-btn-ghost', 'GHI KẾT QUẢ');
        b.type = 'button';
        b.addEventListener('click', () => moKln(x, api, lai));
        o.appendChild(b);
      }
      box.appendChild(o);
    });
    container.appendChild(box);
  }

  // ── ghi một việc ─────────────────────────────────────────────────────
  if (dl.duoc_ghi) {
    container.appendChild(el('div', 'sx-dv-khu', 'Ghi một việc'));
    const luoi = el('div', 'sx-qc-luoi-so');
    dl.viec.forEach((v) => {
      const b = el('button', 'sx-btn sx-btn-ghost', `${esc(v)}<small>${esc(PHU[v] || '')}</small>`);
      b.type = 'button';
      b.addEventListener('click', () => moGhi(dl, null, v, api, lai));
      luoi.appendChild(b);
    });
    container.appendChild(luoi);
  } else {
    container.appendChild(el('div', 'sx-qc-goiy', 'Bạn chỉ có quyền xem — QC ghi nhật ký cát.'));
  }

  // ── các dòng trong tháng ─────────────────────────────────────────────
  container.appendChild(el('div', 'sx-dv-khu', `Các dòng trong tháng (${dl.ds.length})`));
  if (!dl.ds.length) container.appendChild(khungTrong('Tháng này chưa có dòng nhật ký cát nào.'));
  dl.ds.forEach((x) => container.appendChild(veDong(x, dl, api, lai)));

  const inB = el('button', 'sx-btn sx-btn-ghost',
    `🖨 IN BM.08.03 — tháng ${esc(dl.thang.slice(5))}/${esc(dl.thang.slice(0, 4))}`);
  inB.type = 'button';
  inB.addEventListener('click', () => inTo(api, 'sx.api.qc_cat.in_bm0803', { thang: dl.thang }, 'BM.08.03'));
  container.appendChild(inB);
}

function veDong(x, dl, api, lai) {
  const the = el('div', `sx-qc-sc sx-cat-dong${x.thay_cat ? ' sx-cat-thay' : ''}`);
  the.tabIndex = 0;
  the.setAttribute('role', 'button');
  the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(ngayVN(x.ngay))} · ${esc(x.viec || 'Ngày có rang')}`));
  const meta = el('div', 'sx-qc-sc-meta');
  if (x.so_cu) meta.appendChild(chip('sổ cũ'));
  if (x.doi_nguon) meta.appendChild(chip(`ĐỔI NGUỒN · ${x.ten_ncc || x.ncc_cat}`, 'cao'));
  else if (x.ncc_cat) meta.appendChild(el('span', null, esc(x.ten_ncc || x.ncc_cat)));
  if (x.khoi_luong) meta.appendChild(chip(`${so(x.khoi_luong)} kg`));
  if (x.thung) meta.appendChild(chip(`thùng ${x.thung}`));
  if (x.viec === BO_SUNG || x.viec === LOAI || x.so_cu) meta.appendChild(chip(`${x.so_ngay_dung} ngày`, 'oprp'));
  if (x.ve_sinh_thung || x.ve_sinh_khay) {
    meta.appendChild(chip(`vệ sinh ${[x.ve_sinh_thung ? 'thùng' : '', x.ve_sinh_khay ? 'khay' : ''].filter(Boolean).join(', ')}`, 'dong'));
  }
  if (x.cam_quan) meta.appendChild(chip(`cảm quan ${x.cam_quan}`, x.cam_quan === 'Đạt' ? 'dong' : 'mo'));
  if (x.xem_luc) meta.appendChild(chip('đã xem xét'));
  meta.appendChild(el('span', null, esc([x.nguoi_lam, x.nguoi_ghi].filter(Boolean).join(' / '))));
  the.appendChild(meta);
  if (x.ly_do_loai) the.appendChild(el('div', 'sx-qc-goiy', `Lý do loại: ${esc(x.ly_do_loai)}`));
  if (x.ghi_chu) the.appendChild(el('div', 'sx-qc-goiy', esc(x.ghi_chu)));
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

function oTich(body, nhan, bat) {
  const l = el('label', 'sx-sc-check');
  const c = el('input');
  c.type = 'checkbox';
  c.checked = !!bat;
  l.appendChild(c);
  l.appendChild(el('span', null, esc(nhan)));
  body.appendChild(l);
  return c;
}

function chonKln(body, x) {
  const kln = el('select', 'sx-textarea');
  [['', '— chưa gửi mẫu —'], ['Đã gửi mẫu', 'Đã gửi mẫu, chờ kết quả'], ['Đạt', 'Đạt'], ['Không đạt', 'Không đạt']]
    .forEach(([v, t]) => {
      const o = el('option', null, esc(t));
      o.value = v;
      if ((x.kln || '') === v) o.selected = true;
      kln.appendChild(o);
    });
  body.appendChild(el('div', 'sx-qc-goiy', 'Kiểm kim loại nặng (Không đạt → app lập phiếu sự cố)'));
  body.appendChild(kln);
  const soPhieu = oNhap(body, 'Số phiếu kết quả', x.so_phieu_kln || '');
  const lo = oTich(body, 'Đã lưu một lọ mẫu cát', x.luu_lo_mau);
  return () => ({ kln: kln.value, so_phieu_kln: soPhieu.value.trim(), luu_lo_mau: lo.checked ? 1 : 0 });
}

/** Form một việc. x = dòng đang xem / sửa (null = dòng mới); viec0 = việc của nút vừa bấm. */
function moGhi(dl, x, viec0, api, lai) {
  const cu = !!(x && x.so_cu);
  const khoa = cu || !!(x && x.xem_luc && !dl.la_iso);
  const sua = dl.duoc_ghi && !khoa;
  const m = openModal({ kicker: 'NHẬT KÝ CÁT RANG BM.08.03',
    title: x ? `${x.viec || 'Ngày có rang'} · ${ngayDu(x.ngay)}` : viec0 });
  if (cu) {
    m.body.appendChild(el('div', 'sx-qc-goiy', `Dòng sổ cũ (mỗi ngày có rang một dòng) — giữ nguyên. Cát ngày thứ `
      + `<b>${esc(x.so_ngay_dung)}</b>${x.thay_cat ? ' · thay cát' : ''}.`));
  } else if (khoa) {
    m.body.appendChild(el('div', 'sx-qc-goiy', 'Ban ISO đã xem xét dòng này — chỉ Ban ISO sửa được.'));
  }
  let viec = (x && x.viec) || viec0;
  const ng = oNhap(m.body, 'Ngày', (x && x.ngay) || dl.hom_nay, 'date');
  ng.max = dl.hom_nay;
  if (!cu) {
    m.body.appendChild(el('div', 'sx-qc-goiy', 'Việc'));
    m.body.appendChild(segment(dl.viec, viec, (v) => { viec = v || viec; capNhat(); }, !sua));
  }

  // Nguồn: nhập cát bắt buộc; đưa dùng / bổ sung bỏ trống = nguồn của lần nhập gần nhất.
  const khoiNguon = el('div');
  m.body.appendChild(khoiNguon);
  const nhanNguon = el('div', 'sx-qc-goiy');
  khoiNguon.appendChild(nhanNguon);
  const ncc = el('select', 'sx-textarea');
  const ds = dl.ncc.concat([]);
  const dang = (x && x.ncc_cat) || '';
  if (dang && !ds.find((n) => n.name === dang)) ds.unshift({ name: dang, supplier_name: (x && x.ten_ncc) || dang, duyet: 0 });
  [{ name: '', supplier_name: '— chọn nguồn cát —' }].concat(ds).forEach((n) => {
    const o = el('option', null, esc(`${n.supplier_name || n.name}${n.name && !n.duyet ? ' (chưa duyệt BM.07.02)' : ''}`));
    o.value = n.name;
    if (n.name === dang) o.selected = true;
    ncc.appendChild(o);
  });
  khoiNguon.appendChild(ncc);
  if (!dl.ncc.length) {
    khoiNguon.appendChild(el('div', 'sx-qc-goiy', 'Chưa có NCC loại Cát rang — Ban ISO khai trên Desk → Supplier '
      + '(Loại NCC: Cát rang).'));
  }
  const bao = el('div', 'sx-cat-doi');
  khoiNguon.appendChild(bao);
  const khoiPhieu = el('div');
  khoiNguon.appendChild(khoiPhieu);
  const soPhieu = oNhap(khoiPhieu, 'Số BM.07.03 / phiếu nhập mua', (x && x.so_bm0703) || '');
  khoiPhieu.appendChild(el('div', 'sx-qc-goiy', 'Cảm quan khi nhận (vàng đồng đều, hạt thô, không mùi dầu / hoá chất, không rác, vỏ sò, kim loại)'));
  let camQuan = (x && x.cam_quan) || '';
  khoiPhieu.appendChild(segment(['Đạt', 'Không đạt'], camQuan, (v) => { camQuan = v; }, !sua, true));
  const khoiKln = el('div');
  khoiNguon.appendChild(khoiKln);
  let layKln = null;

  const khoiKl = el('div');
  m.body.appendChild(khoiKl);
  const kl = oNhap(khoiKl, 'Khối lượng (kg)', x && x.khoi_luong ? x.khoi_luong : '', 'number');
  kl.min = '0';
  kl.inputMode = 'decimal';
  const thung = oNhap(m.body, 'Thùng số / nhãn ngày ("CÁT RANG — ngày xử lý — thùng số")', (x && x.thung) || '');
  // Dòng đưa dùng đầu sổ: cát đang dùng từ trước khi có sổ đã qua mấy ngày có rang.
  const khoiDau = el('div');
  m.body.appendChild(khoiDau);
  const soDau = oNhap(khoiDau, 'Cát này đã dùng bao nhiêu ngày có rang TRƯỚC ngày ghi? (chỉ dòng đầu sổ)',
    (x && x.so_ngay_dau) || 0, 'number');
  soDau.min = '0';
  soDau.inputMode = 'numeric';
  const dem = el('div', 'sx-qc-goiy sx-cat-dem');
  m.body.appendChild(dem);

  const khoiLyDo = el('div');
  m.body.appendChild(khoiLyDo);
  khoiLyDo.appendChild(el('div', 'sx-qc-goiy', 'Lý do loại (HD.08.03 mục 5)'));
  const lyDo = el('textarea', 'sx-textarea');
  lyDo.rows = 2;
  lyDo.value = (x && x.ly_do_loai) || '';
  const nhanh = el('div', 'sx-qc-chips');
  LY_DO.forEach((t) => {
    const b = el('button', 'sx-qc-tag', esc(t));
    b.type = 'button';
    b.disabled = !sua;
    b.addEventListener('click', () => { lyDo.value = lyDo.value.trim() ? `${lyDo.value.trim()}; ${t}` : t; });
    nhanh.appendChild(b);
  });
  khoiLyDo.appendChild(nhanh);
  khoiLyDo.appendChild(lyDo);

  const khoiVs = el('div');
  m.body.appendChild(khoiVs);
  const vsThung = oTich(khoiVs, 'Đã vệ sinh thùng (rửa, úp ráo, khô hẳn, đậy nắp)', x ? x.ve_sinh_thung : 0);
  const vsKhay = oTich(khoiVs, 'Đã vệ sinh khay', x ? x.ve_sinh_khay : 0);

  const lam = oNhap(m.body, 'Người làm (công nhân khu cát / rang)', (x && x.nguoi_lam) || '');
  const gc = oNhap(m.body, 'Ghi chú', (x && x.ghi_chu) || '', 'ta');

  const capNhat = () => {
    const o = oTheoViec(viec);
    khoiNguon.style.display = o.nguon || cu ? '' : 'none';
    nhanNguon.textContent = viec === NHAP ? 'Nguồn cát (NCC loại Cát rang) — bắt buộc'
      : 'Nguồn cát (bỏ trống = nguồn của lần nhập gần nhất)';
    khoiPhieu.style.display = o.phieu ? '' : 'none';
    khoiKl.style.display = o.kl ? '' : 'none';
    khoiLyDo.style.display = o.lyDo ? '' : 'none';
    khoiVs.style.display = o.veSinh || (cu && (x.ve_sinh_thung || x.ve_sinh_khay)) ? '' : 'none';
    // Số ngày đầu sổ: dòng đưa dùng mới khi sổ chưa có mốc nào, hoặc dòng đã khai (sửa dòng không làm mất số).
    khoiDau.style.display = viec === RANG_KHO && (x ? Number(x.so_ngay_dau) > 0 : dl.hien_tai.dau_so) ? '' : 'none';
    // Nhập từ NCC khác lần nhập gần nhất = đổi nguồn (server tính lại khi lưu).
    const doi = viec === NHAP && !x && !!(dl.nguon_nhap && ncc.value && ncc.value !== dl.nguon_nhap);
    bao.innerHTML = doi ? '⚠ <b>ĐỔI NGUỒN CÁT</b> — phải gửi mẫu kiểm kim loại nặng (trước khi dùng) và lưu một lọ '
      + 'mẫu (ghi ngay dưới, hoặc ghi sau khi có kết quả).' : '';
    bao.style.display = doi ? '' : 'none';
    if (doi && !layKln) layKln = chonKln(khoiKln, x || {});
    khoiKln.style.display = doi || (x && x.doi_nguon) ? '' : 'none';
    const h = dl.hien_tai;
    if (viec === BO_SUNG || viec === LOAI) {
      dem.textContent = h.so_ngay == null ? 'Máy chưa có cát đang dùng — ghi "Rang khô đưa dùng" trước.'
        : `Số ngày đã dùng của cát trong máy: app đếm khi lưu (hôm nay: ${h.so_ngay} ngày).`;
    } else if (viec === RANG_KHO) {
      dem.textContent = h.so_ngay != null
        ? `Thay toàn bộ: app đếm lại từ ngày này. Cát cũ (đã dùng ${h.so_ngay} ngày) — nhớ ghi dòng Loại cát.`
        : 'Thay toàn bộ: app đếm số ngày có rang từ ngày này.';
    } else dem.textContent = '';
  };
  if (x && x.doi_nguon) layKln = chonKln(khoiKln, x);
  ncc.addEventListener('change', capNhat);
  capNhat();
  if (!sua) m.body.querySelectorAll('input, select, textarea').forEach((n) => { n.disabled = true; });

  if (sua) {
    const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'GHI NHẬT KÝ');
    ok.type = 'button';
    ok.addEventListener('click', async () => {
      const o = oTheoViec(viec);
      if (!ng.value) { toastErr('Chọn ngày.'); return; }
      if (viec === NHAP && !ncc.value) { toastErr('Chọn nguồn cát.'); return; }
      if (o.canKl && !(Number(kl.value) > 0)) { toastErr('Ghi khối lượng (kg).'); return; }
      if (o.lyDo && !lyDo.value.trim()) { toastErr('Ghi lý do loại.'); return; }
      if (o.veSinh && !vsThung.checked && !vsKhay.checked) { toastErr('Đánh dấu vệ sinh thùng hay khay.'); return; }
      ok.disabled = true;
      try {
        const r = await api.call('sx.api.qc_cat.ghi', {
          payload: JSON.stringify({
            name: x ? x.name : null, ngay: ng.value, viec,
            ncc_cat: o.nguon ? ncc.value : '', so_bm0703: o.phieu ? soPhieu.value : '',
            cam_quan: o.camQuan ? camQuan : '', khoi_luong: o.kl ? Number(kl.value) || 0 : 0, thung: thung.value,
            ly_do_loai: o.lyDo ? lyDo.value : '',
            ve_sinh_thung: o.veSinh && vsThung.checked ? 1 : 0, ve_sinh_khay: o.veSinh && vsKhay.checked ? 1 : 0,
            nguoi_lam: lam.value, ghi_chu: gc.value,
            ...(khoiDau.style.display === 'none' ? {} : { so_ngay_dau: Number(soDau.value) || 0 }),
            ...(layKln && khoiKln.style.display !== 'none' ? layKln() : {}),
          }),
        });
        toast(`Đã ghi ${r.viec.toLowerCase()}${viec === BO_SUNG || viec === LOAI ? ` — cát đã dùng ${r.so_ngay_dung} ngày` : ''}${
          r.doi_nguon ? ' · ĐỔI NGUỒN: nhớ kiểm kim loại nặng + lưu lọ mẫu' : ''}${r.su_co ? ` · sự cố ${r.su_co}` : ''}`);
        m.close();
        st.thang = ng.value.slice(0, 7) === dl.hom_nay.slice(0, 7) ? null : ng.value.slice(0, 7);
        lai();
      } catch (e) { ok.disabled = false; toastErr(e.message); }
    });
    m.body.appendChild(ok);
  } else if (x && x.doi_nguon && (dl.duoc_ghi || dl.la_iso)) {
    const b = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'GHI KẾT QUẢ KIM LOẠI NẶNG / LỌ MẪU');
    b.type = 'button';
    b.addEventListener('click', () => { m.close(); moKln(x, api, lai); });
    m.body.appendChild(b);
  }
  // Ghi nhầm cả dòng: người ghi xoá được trong ngày ghi; Ban ISO lúc nào cũng được.
  if (x && (dl.la_iso || (sua && x.nguoi_ghi === dl.user && x.creation === dl.hom_nay))) {
    const xoa = el('button', 'sx-btn sx-btn-ghost', 'XOÁ DÒNG (ghi nhầm)');
    xoa.type = 'button';
    xoa.addEventListener('click', () => {
      m.close();
      confirm2Step({
        title: `Xoá dòng ${(x.viec || 'ngày có rang').toLowerCase()} ngày ${ngayDu(x.ngay)}?`,
        message: x.viec === RANG_KHO || x.viec === LOAI ? 'Số ngày cát đã dùng sẽ được đếm lại theo các dòng còn lại.'
          : 'Dòng này biến khỏi nhật ký cát.',
        confirmLabel: 'XOÁ',
        onConfirm: async () => {
          await api.call('sx.api.qc_cat.xoa', { name: x.name });
          toast('Đã xoá');
          lai();
        },
      });
    });
    m.body.appendChild(xoa);
  }
}

function moKln(x, api, lai) {
  const m = openModal({ kicker: `ĐỔI NGUỒN CÁT ${ngayDu(x.ngay)}`, title: x.ten_ncc || x.ncc_cat });
  const lay = chonKln(m.body, x);
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc_cat.cap_nhat_kln', { name: x.name, payload: JSON.stringify(lay()) });
      toast(r.su_co ? `Đã lưu · lập phiếu sự cố ${r.su_co}` : 'Đã lưu');
      m.close();
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
