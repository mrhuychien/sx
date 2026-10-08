// #/qc/cat — nhật ký cát rang BM.08.03 (W20, D141).
//
// Mỗi ngày có rang MỘT dòng: nguồn cát, có thay cát không, vệ sinh thùng / khay, cảm quan.
// Số ngày cát đã dùng do app ĐẾM (dòng nhật ký kể từ lần thay gần nhất) — người ghi không
// phải nhớ hay cộng tay. Chọn nguồn khác cát đang dùng = đổi nguồn: app tự đánh dấu thay
// cát và nhắc kiểm kim loại nặng + lưu lọ mẫu tới khi đủ. Số ngày tối đa chưa chốt (C19)
// nên chỉ đếm. Luật ở sx/qc/cat.py + controller SX Nhat Ky Cat; màn này chỉ ghi và xem.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment } from '/assets/sx/sx/components/qcui.js';

// Tháng đang xem ('YYYY-MM'), null = tháng này. Ngoài render: in xong quay lại không mất.
const st = { thang: null };

const ngayVN = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}` : '');
const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');

function congThang(t, n) {
  const [y, m] = t.split('-').map(Number);
  const d = new Date(Date.UTC(y, m - 1 + n, 1));
  return d.toISOString().slice(0, 7);
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
  if (h) {
    the.appendChild(el('div', 'sx-qc-goiy', 'CÁT ĐANG DÙNG'));
    the.appendChild(el('div', 'sx-cat-so', `Ngày thứ ${esc(h.so_ngay_dung)}${
      dl.toi_da ? ` <small>/ tối đa ${esc(dl.toi_da)}</small>` : ''}`));
    the.appendChild(el('div', 'sx-cat-nguon', `Nguồn: <b>${esc(h.ten_ncc || h.ncc_cat || '—')}</b>`
      + ` · ghi gần nhất ${esc(ngayVN(h.ngay))}${dl.ngay_thay ? ` · thay cát ${esc(ngayDu(dl.ngay_thay))}` : ''}`));
    if (!dl.toi_da) {
      the.appendChild(el('div', 'sx-qc-goiy', 'Chưa quy định cát dùng tối đa bao nhiêu ngày (C19) — app chỉ đếm, không nhắc.'));
    }
  } else {
    the.appendChild(el('div', 'sx-qc-sc-ten', 'Sổ chưa có dòng nào'));
    the.appendChild(el('div', 'sx-qc-goiy', 'Dòng đầu tiên: chọn nguồn cát và khai cát đang dùng đã được mấy ngày — '
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
        <div class="sx-qc-nhac-ct">Nguồn ${esc(x.ten_ncc || x.ncc_cat)}. Đổi nguồn phải kiểm kim loại nặng và lưu một lọ mẫu.</div>`;
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

  // ── ghi hôm nay / ghi bù ─────────────────────────────────────────────
  if (dl.duoc_ghi) {
    const nut = el('button', 'sx-btn sx-btn-primary sx-btn-big',
      dl.hom_nay_co ? 'SỬA NHẬT KÝ HÔM NAY' : 'GHI NHẬT KÝ HÔM NAY');
    nut.type = 'button';
    nut.addEventListener('click', () => moGhi(dl, dl.hom_nay_dong || null, dl.hom_nay, api, lai));
    container.appendChild(nut);
    const bu = el('button', 'sx-btn sx-btn-ghost', 'Ghi bù ngày khác (từ sổ giấy)');
    bu.type = 'button';
    bu.addEventListener('click', () => moGhi(dl, null, '', api, lai));
    container.appendChild(bu);
  } else {
    container.appendChild(el('div', 'sx-qc-goiy', 'Bạn chỉ có quyền xem — QC ghi nhật ký cát.'));
  }

  // ── các ngày trong tháng ─────────────────────────────────────────────
  container.appendChild(el('div', 'sx-dv-khu', `Các ngày trong tháng (${dl.ds.length})`));
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
  the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(ngayVN(x.ngay))} · cát ngày thứ ${esc(x.so_ngay_dung)}`));
  const meta = el('div', 'sx-qc-sc-meta');
  if (x.doi_nguon) meta.appendChild(chip(`ĐỔI NGUỒN · ${x.ten_ncc || x.ncc_cat}`, 'cao'));
  else if (x.thay_cat) meta.appendChild(chip('THAY CÁT', 'oprp'));
  meta.appendChild(chip(`${x.ve_sinh_thung ? '✓' : '✗'} thùng`, x.ve_sinh_thung ? 'dong' : 'mo'));
  meta.appendChild(chip(`${x.ve_sinh_khay ? '✓' : '✗'} khay`, x.ve_sinh_khay ? 'dong' : 'mo'));
  if (x.cam_quan) meta.appendChild(chip(`cảm quan ${x.cam_quan}`, x.cam_quan === 'Đạt' ? 'dong' : 'mo'));
  if (x.xem_luc) meta.appendChild(chip('đã xem xét'));
  meta.appendChild(el('span', null, esc(x.nguoi_ghi || '')));
  the.appendChild(meta);
  if (x.ghi_chu) the.appendChild(el('div', 'sx-qc-goiy', esc(x.ghi_chu)));
  if (x.su_co) the.appendChild(el('div', 'sx-qc-goiy', `Phiếu sự cố: <b>${esc(x.su_co)}</b>`));
  the.addEventListener('click', () => moGhi(dl, x, x.ngay, api, lai));
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
  const so = oNhap(body, 'Số phiếu kết quả', x.so_phieu_kln || '');
  const lo = oTich(body, 'Đã lưu một lọ mẫu cát', x.luu_lo_mau);
  return () => ({ kln: kln.value, so_phieu_kln: so.value.trim(), luu_lo_mau: lo.checked ? 1 : 0 });
}

/** Form một ngày. x = dòng đang sửa (null = dòng mới); ngay = ngày mặc định ('' = để chọn). */
function moGhi(dl, x, ngay, api, lai) {
  const khoa = !!(x && x.xem_luc && !dl.la_iso);
  const sua = dl.duoc_ghi && !khoa;
  const m = openModal({ kicker: 'NHẬT KÝ CÁT RANG BM.08.03',
    title: x ? `Ngày ${ngayDu(x.ngay)}` : (ngay ? `Hôm nay ${ngayDu(ngay)}` : 'Ghi bù một ngày') });
  if (khoa) {
    m.body.appendChild(el('div', 'sx-qc-goiy', 'Ban ISO đã xem xét dòng này — chỉ Ban ISO sửa được.'));
  }
  const ng = oNhap(m.body, 'Ngày', (x && x.ngay) || ngay || '', 'date');
  ng.max = dl.hom_nay;
  const h = dl.hien_tai;
  // Nguồn của cát đang dùng TRƯỚC dòng này — đổi khác nó là đổi nguồn.
  const goc = x ? (x.doi_nguon ? '' : x.ncc_cat) : (h ? h.ncc_cat : '');
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Nguồn cát (NCC loại Cát rang)'));
  const ncc = el('select', 'sx-textarea');
  const ds = dl.ncc.concat([]);
  const dang = (x && x.ncc_cat) || (h && h.ncc_cat) || '';
  if (dang && !ds.find((n) => n.name === dang)) {
    ds.unshift({ name: dang, supplier_name: (x && x.ten_ncc) || (h && h.ten_ncc) || dang, duyet: 0 });
  }
  [{ name: '', supplier_name: '— chọn nguồn cát —' }].concat(ds).forEach((n) => {
    const o = el('option', null, esc(`${n.supplier_name || n.name}${n.name && !n.duyet ? ' (chưa duyệt BM.07.02)' : ''}`));
    o.value = n.name;
    if (n.name === dang) o.selected = true;
    ncc.appendChild(o);
  });
  m.body.appendChild(ncc);
  if (!dl.ncc.length) {
    m.body.appendChild(el('div', 'sx-qc-goiy', 'Chưa có NCC loại Cát rang — Ban ISO khai trên Desk → Supplier '
      + '(Loại NCC: Cát rang).'));
  }
  const bao = el('div', 'sx-cat-doi');
  m.body.appendChild(bao);
  const thay = oTich(m.body, 'Thay cát mới hôm nay', x && x.thay_cat);
  // Dòng đầu sổ (chưa có dòng nào trước ngày này): cát đang dùng từ trước khi có app.
  const dauSo = el('div');
  m.body.appendChild(dauSo);
  const soDau = oNhap(dauSo, 'Cát đang dùng đã dùng được mấy ngày (tính cả ngày này)?',
    (x && x.so_ngay_dung) || 1, 'number');
  soDau.min = '1';
  soDau.inputMode = 'numeric';
  const khoiKln = el('div');
  m.body.appendChild(khoiKln);
  let layKln = null;
  const capNhat = () => {
    const doi = !!(goc && ncc.value && ncc.value !== goc);
    bao.innerHTML = doi ? '⚠ <b>ĐỔI NGUỒN CÁT</b> — app tự ghi thay cát. Phải gửi mẫu kiểm kim loại nặng và lưu '
      + 'một lọ mẫu (ghi ngay dưới, hoặc ghi sau khi có kết quả).' : '';
    bao.style.display = doi ? '' : 'none';
    if (doi) thay.checked = true;
    thay.disabled = doi || !sua;
    const d = ng.value || dl.hom_nay;
    dauSo.style.display = (!thay.checked && (!dl.ngay_dau_so || d <= dl.ngay_dau_so)
      && (!x || x.ngay === dl.ngay_dau_so)) ? '' : 'none';
    if (doi && !layKln) layKln = chonKln(khoiKln, x || {});
    khoiKln.style.display = doi || (x && x.doi_nguon) ? '' : 'none';
  };
  if (x && x.doi_nguon) layKln = chonKln(khoiKln, x);
  ncc.addEventListener('change', capNhat);
  thay.addEventListener('change', capNhat);
  ng.addEventListener('change', capNhat);
  const thung = oTich(m.body, 'Đã vệ sinh thùng', x ? x.ve_sinh_thung : 0);
  const khay = oTich(m.body, 'Đã vệ sinh khay', x ? x.ve_sinh_khay : 0);
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Cảm quan cát (sạch, khô, không vón, không lẫn tạp chất)'));
  let camQuan = (x && x.cam_quan) || '';
  m.body.appendChild(segment(['Đạt', 'Không đạt'], camQuan, (v) => { camQuan = v; }, !sua, true));
  const gc = oNhap(m.body, 'Ghi chú', (x && x.ghi_chu) || '', 'ta');
  capNhat();
  if (!sua) m.body.querySelectorAll('input, select, textarea').forEach((n) => { n.disabled = true; });

  if (sua) {
    const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'GHI NHẬT KÝ');
    ok.type = 'button';
    ok.addEventListener('click', async () => {
      if (!ng.value) { toastErr('Chọn ngày.'); return; }
      if (!ncc.value) { toastErr('Chọn nguồn cát.'); return; }
      ok.disabled = true;
      try {
        const r = await api.call('sx.api.qc_cat.ghi', {
          payload: JSON.stringify({
            name: x ? x.name : null, ngay: ng.value, ncc_cat: ncc.value, thay_cat: thay.checked ? 1 : 0,
            ve_sinh_thung: thung.checked ? 1 : 0, ve_sinh_khay: khay.checked ? 1 : 0, cam_quan: camQuan,
            ghi_chu: gc.value, so_ngay_dau: dauSo.style.display === 'none' ? 0 : Number(soDau.value) || 1,
            ...(layKln && khoiKln.style.display !== 'none' ? layKln() : {}),
          }),
        });
        toast(`Đã ghi — cát dùng ngày thứ ${r.so_ngay_dung}${
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
        title: `Xoá nhật ký cát ngày ${ngayDu(x.ngay)}?`,
        message: 'Các ngày sau sẽ được đếm lại số ngày cát đã dùng.',
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
