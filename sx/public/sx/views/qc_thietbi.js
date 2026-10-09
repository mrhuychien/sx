// #/qc/thietbi — thiết bị đo, hiệu chuẩn BM.06.01–06.04 (W17, D143).
//
// Danh mục theo loại, mỗi thiết bị một thẻ: hạn kiểm kế tiếp, lần kiểm gần nhất, trạng thái.
// Không đạt hoặc quá hạn = NGỪNG DÙNG (app tự lập phiếu sự cố); kiểm lại Đạt thì dùng lại.
// Trạng thái tính lúc xem (không đợi lịch chạy nền). Luật ở sx/qc/thiet_bi.py + controller.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment } from '/assets/sx/sx/components/qcui.js';

const DH = 'Đồng hồ nhiệt';
const NC = 'Nam châm';
const LS = 'Lưới sàng, rây';
const CAN = 'Cân';
const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const KIEU_TT = { 'Đang dùng': 'dong', 'Ngừng — không đạt': 'cao', 'Ngừng — quá hạn': 'cao', 'Thanh lý': '' };

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc_thietbi.tong_quan', {});
  container.innerHTML = '';
  const lai = () => render(api);

  container.appendChild(el('div', 'sx-qc-top', `<div style="flex:1;min-width:0">
    <div class="sx-qc-ngay">🌡 Thiết bị đo</div>
    <div class="sx-qc-ai">BM.06.01–06.04 · hiệu chuẩn, kiểm tra định kỳ</div></div>`));

  const dung = dl.ds.filter((x) => !x.thanh_ly);
  const qua = dung.filter((x) => x.trang_thai === 'Ngừng — quá hạn');
  const hong = dung.filter((x) => x.trang_thai === 'Ngừng — không đạt');
  const sap = dung.filter((x) => x.trang_thai === 'Đang dùng' && x.con <= dl.sap_den);
  const chuaKiem = dung.filter((x) => x.chua_kiem);
  const tom = el('div', 'sx-qc-chips');
  if (qua.length) tom.appendChild(chip(`${qua.length} quá hạn — ngừng dùng`, 'cao'));
  if (hong.length) tom.appendChild(chip(`${hong.length} không đạt — ngừng dùng`, 'cao'));
  if (sap.length) tom.appendChild(chip(`${sap.length} đến hạn trong ${dl.sap_den} ngày`, 'oprp'));
  if (chuaKiem.length) tom.appendChild(chip(`${chuaKiem.length} chưa kiểm lần nào — hạn ${ngayDu(dl.han_dau)}`, 'han'));
  if (!qua.length && !hong.length && !sap.length && dung.length) tom.appendChild(chip('mọi thiết bị còn hạn', 'dong'));
  container.appendChild(tom);

  dl.loai.forEach((loai) => {
    const nhom = dl.ds.filter((x) => x.loai === loai);
    const khoi = el('div', 'sx-dv-nhom');
    khoi.appendChild(el('div', 'sx-dv-khu', `${esc(loai)}${dl.bieu_mau[loai] ? ` · ${esc(dl.bieu_mau[loai])}` : ''}`));
    if (!nhom.length) {
      if (loai !== 'Khác') khoi.appendChild(el('div', 'sx-qc-goiy', 'Chưa khai thiết bị loại này.'));
    }
    nhom.forEach((x) => khoi.appendChild(veThe(x, dl, api, lai)));
    if (nhom.length || loai !== 'Khác') container.appendChild(khoi);
  });

  if (dl.duoc_ghi) {
    const them = el('button', 'sx-btn sx-btn-primary sx-btn-big', '+ THÊM THIẾT BỊ');
    them.type = 'button';
    them.addEventListener('click', () => moThietBi(null, dl, api, lai));
    container.appendChild(them);
  }
  if (dl.chung_chi === 'Giữ chứng chỉ') {
    container.appendChild(el('div', 'sx-qc-goiy', 'Người tự kiểm đồng hồ nhiệt phải có chứng chỉ còn hạn '
      + '(SX QC Setting) — không thì không ghi được phiếu kiểm nội bộ.'));
  }

  const nam = dl.hom_nay.slice(0, 4);
  const inBtn = (nhan, ma) => {
    const b = el('button', 'sx-btn sx-btn-ghost', esc(nhan));
    b.type = 'button';
    b.addEventListener('click', () => inTo(api, 'sx.api.qc_thietbi.in_bieu_mau', { ma, nam }, ma));
    container.appendChild(b);
  };
  inBtn('🖨 BM.06.01 — danh mục thiết bị', 'BM.06.01');
  inBtn(`🖨 BM.06.02 — đồng hồ nhiệt năm ${nam}`, 'BM.06.02');
  inBtn(`🖨 BM.06.03 — nam châm năm ${nam}`, 'BM.06.03');
  inBtn(`🖨 BM.06.04 — lưới sàng, rây năm ${nam}`, 'BM.06.04');
}

function veThe(x, dl, api, lai) {
  const ngung = x.trang_thai !== 'Đang dùng';
  const the = el('div', `sx-qc-sc ${ngung && !x.thanh_ly ? 'sx-qc-sc-mo' : 'sx-qc-sc-dong'}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(x.name)} · ${esc(x.ten)}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(x.trang_thai, KIEU_TT[x.trang_thai]));
  if (!x.thanh_ly) {
    meta.appendChild(el('span', null, x.con < 0 ? `<b>quá hạn ${-x.con} ngày</b> (${esc(ngayDu(x.han))})`
      : `hạn ${esc(ngayDu(x.han))} · còn ${x.con} ngày`));
  }
  if (x.vi_tri || x.may) meta.appendChild(el('span', null, esc([x.vi_tri, x.may].filter(Boolean).join(' · '))));
  the.appendChild(meta);
  the.appendChild(el('div', 'sx-qc-goiy', x.lan_cuoi
    ? `Kiểm gần nhất ${esc(ngayDu(x.lan_cuoi))}: <b>${esc(x.ket_qua_cuoi)}</b> · chu kỳ ${x.chu_ky} tháng${
      x.loai === CAN ? ' (cân: theo hạn giấy kiểm định)' : ''}`
    : `Chưa kiểm lần nào — kiểm trước ${esc(ngayDu(dl.han_dau))}.`));
  const nut = el('div', 'sx-qc-chips sx-tb-nut');
  if (dl.duoc_ghi && !x.thanh_ly) {
    const g = el('button', 'sx-btn sx-btn-primary', 'GHI KIỂM TRA');
    g.type = 'button';
    g.addEventListener('click', () => moKiem(x, dl, api, lai));
    nut.appendChild(g);
  }
  const ls = el('button', 'sx-btn sx-btn-ghost', 'LỊCH SỬ');
  ls.type = 'button';
  ls.addEventListener('click', () => moLichSu(x, dl, api, lai));
  nut.appendChild(ls);
  if (dl.duoc_ghi) {
    const s = el('button', 'sx-btn sx-btn-ghost', 'SỬA');
    s.type = 'button';
    s.addEventListener('click', () => moThietBi(x, dl, api, lai));
    nut.appendChild(s);
  }
  the.appendChild(nut);
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

function moThietBi(x, dl, api, lai) {
  const m = openModal({ kicker: 'DANH MỤC THIẾT BỊ BM.06.01', title: x ? `${x.name} · ${x.ten}` : 'Thêm thiết bị' });
  const ma = x ? null : oNhap(m.body, 'Mã thiết bị (VD: DH-01, NC-01, CAN-01) — không đổi được sau khi tạo', '');
  if (ma) ma.setAttribute('autocapitalize', 'characters');
  const ten = oNhap(m.body, 'Tên thiết bị', x ? x.ten : '');
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Loại'));
  let loai = x ? x.loai : '';
  m.body.appendChild(segment(dl.loai, loai, (v) => { loai = v; }, false));
  const vt = oNhap(m.body, 'Vị trí / công đoạn', x ? x.vi_tri : '');
  const may = oNhap(m.body, 'Máy (M1 / M2 / M3 — nếu gắn theo máy)', x ? x.may : '');
  const ck = oNhap(m.body, 'Chu kỳ kiểm (tháng) — bỏ trống = 12; cân theo hạn giấy kiểm định',
    x && x.chu_ky_thang ? x.chu_ky_thang : '', 'number');
  ck.min = '0';
  ck.inputMode = 'numeric';
  const gc = oNhap(m.body, 'Ghi chú', x ? x.ghi_chu : '', 'ta');
  const tl = el('label', 'sx-sc-check');
  const tlc = el('input');
  tlc.type = 'checkbox';
  tlc.checked = !!(x && x.thanh_ly);
  tl.appendChild(tlc);
  tl.appendChild(el('span', null, 'Thanh lý / không dùng nữa (không nhắc hạn)'));
  m.body.appendChild(tl);
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (ma && !ma.value.trim()) { toastErr('Nhập mã thiết bị.'); return; }
    if (!loai) { toastErr('Chọn loại thiết bị.'); return; }
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc_thietbi.luu_thiet_bi', {
        payload: JSON.stringify({
          name: x ? x.name : null, ma: ma ? ma.value : null, ten: ten.value, loai, vi_tri: vt.value,
          may: may.value, chu_ky_thang: ck.value, ghi_chu: gc.value, thanh_ly: tlc.checked ? 1 : 0,
        }),
      });
      toast(`Đã lưu ${r.name}`);
      m.close();
      lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

/** Form ghi một lần kiểm — tiêu chí theo loại thiết bị. */
function moKiem(x, dl, api, lai) {
  const m = openModal({ kicker: `${x.bieu_mau || 'BM.06.01'} · ${x.name}`, title: x.ten });
  const ng = oNhap(m.body, 'Ngày kiểm', dl.hom_nay, 'date');
  ng.max = dl.hom_nay;
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Hình thức'));
  let hinhThuc = 'Kiểm tra nội bộ';
  const khoiGiay = el('div');
  m.body.appendChild(segment(['Kiểm tra nội bộ', 'Hiệu chuẩn bên ngoài', 'Kiểm định bên ngoài'], hinhThuc,
    (v) => { hinhThuc = v || 'Kiểm tra nội bộ'; veGiay(); capNhat(); }, false));
  const f = {};
  const kq = el('div', 'sx-qc-goiy sx-tb-kq');
  let ketQua = 'Đạt';
  const tieuChi = (nhan, key) => {
    m.body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
    m.body.appendChild(segment(['Đạt', 'Không đạt'], '', (v) => { f[key] = v; capNhat(); }, false, true));
  };
  if (x.loai === DH) {
    m.body.appendChild(el('div', 'sx-qc-goiy', 'So với nhiệt kế chuẩn / nước đá 0 °C / nước sôi 100 °C — ghi ít nhất một điểm.'));
    const hang = (i) => {
      const r = el('div', 'sx-qc-lm-hang');
      const a = el('div');
      const b = el('div');
      r.appendChild(a);
      r.appendChild(b);
      const c = oNhap(a, `Điểm ${i} — chuẩn (°C)`, '');
      const d = oNhap(b, `Điểm ${i} — đồng hồ đọc`, '');
      [c, d].forEach((n) => { n.inputMode = 'decimal'; n.addEventListener('input', () => { f[`chuan_${i}`] = c.value; f[`doc_${i}`] = d.value; capNhat(); }); });
      m.body.appendChild(r);
    };
    hang(1);
    hang(2);
    const cp = oNhap(m.body, 'Sai số cho phép (± °C)', '2');
    cp.inputMode = 'decimal';
    f.sai_so_cho_phep = '2';
    cp.addEventListener('input', () => { f.sai_so_cho_phep = cp.value; capNhat(); });
  } else if (x.loai === NC) {
    tieuChi('Bề mặt nguyên vẹn, không nứt vỡ', 'be_mat');
    tieuChi('Lực hút (thử bằng que thử / máy đo)', 'luc_hut');
    const g = oNhap(m.body, 'Lực hút đo được (Gauss — nếu có máy đo)', '');
    g.inputMode = 'decimal';
    g.addEventListener('input', () => { f.luc_hut_gauss = g.value; });
  } else if (x.loai === LS) {
    tieuChi('Không rách, thủng', 'nguyen_ven');
    tieuChi('Mắt lưới đúng cỡ, không giãn', 'mat_luoi');
    tieuChi('Khung, mối hàn chắc', 'khung');
  }
  m.body.appendChild(khoiGiay);
  const giay = {};
  function veGiay() {
    khoiGiay.innerHTML = '';
    if (hinhThuc === 'Kiểm tra nội bộ' && x.loai !== CAN) return;
    if (hinhThuc === 'Kiểm tra nội bộ') {
      khoiGiay.appendChild(el('div', 'sx-qc-goiy', 'Kiểm nội bộ (quả chuẩn) không kéo dài hạn kiểm định của cân.'));
      return;
    }
    const so = oNhap(khoiGiay, 'Số giấy chứng nhận', giay.so_giay || '');
    const dv = oNhap(khoiGiay, 'Đơn vị kiểm định / hiệu chuẩn', giay.don_vi || '');
    const han = oNhap(khoiGiay, `Hạn ghi trên giấy${x.loai === CAN ? ' (bắt buộc — hạn kiểm kế tiếp lấy ngày này)' : ''}`,
      giay.han_giay || '', 'date');
    so.addEventListener('input', () => { giay.so_giay = so.value; });
    dv.addEventListener('input', () => { giay.don_vi = dv.value; });
    han.addEventListener('change', () => { giay.han_giay = han.value; });
  }
  veGiay();
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Kết quả'));
  const segKq = el('div');
  m.body.appendChild(segKq);
  m.body.appendChild(kq);
  const gc = oNhap(m.body, 'Ghi chú (hỏng gì, đã xử lý gì)', '', 'ta');
  // Tiêu chí hỏng → kết quả ép Không đạt (server cũng ép); không hỏng thì người kiểm chọn.
  let ep = false;
  function veKq() {
    segKq.innerHTML = '';
    segKq.appendChild(segment(['Đạt', 'Không đạt'], ketQua, (v) => { ketQua = v || 'Đạt'; }, ep));
  }
  function capNhat() {
    const ly = [];
    if (x.loai === DH) {
      let maxSs = null;
      [1, 2].forEach((i) => {
        const c = parseFloat(String(f[`chuan_${i}`] || '').replace(',', '.'));
        const d = parseFloat(String(f[`doc_${i}`] || '').replace(',', '.'));
        if (!Number.isNaN(c) && !Number.isNaN(d)) maxSs = Math.max(maxSs || 0, Math.abs(d - c));
      });
      const cp = parseFloat(String(f.sai_so_cho_phep || '2').replace(',', '.')) || 2;
      if (maxSs !== null) {
        kq.textContent = `Sai số lớn nhất ${Math.round(maxSs * 100) / 100} °C (cho phép ± ${cp})`;
        if (maxSs > cp) ly.push('sai số vượt cho phép');
      } else kq.textContent = '';
    } else {
      ['be_mat', 'luc_hut', 'nguyen_ven', 'mat_luoi', 'khung'].forEach((k) => { if (f[k] === 'Không đạt') ly.push(k); });
      kq.textContent = '';
    }
    const epMoi = ly.length > 0;
    if (epMoi) ketQua = 'Không đạt';
    if (epMoi !== ep || epMoi) { ep = epMoi; veKq(); }
    if (epMoi) kq.textContent = `${kq.textContent ? `${kq.textContent} — ` : ''}KHÔNG ĐẠT → thiết bị ngừng dùng, app lập phiếu sự cố.`;
  }
  veKq();
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'GHI KIỂM TRA');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc_thietbi.ghi_kiem', {
        payload: JSON.stringify({
          thiet_bi: x.name, ngay: ng.value || dl.hom_nay, hinh_thuc: hinhThuc, ket_qua: ketQua,
          ghi_chu: gc.value, ...f, ...(hinhThuc === 'Kiểm tra nội bộ' ? {} : giay),
        }),
      });
      toast(r.ket_qua === 'Đạt' ? `Đã ghi ${x.name}: Đạt` : `Đã ghi ${x.name}: KHÔNG ĐẠT — ngừng dùng${r.su_co ? ` · sự cố ${r.su_co}` : ''}`);
      m.close();
      lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

async function moLichSu(x, dl, api, lai) {
  const m = openModal({ kicker: `LỊCH SỬ KIỂM · ${x.name}`, title: x.ten });
  m.body.appendChild(el('div', 'sx-boot-loading', 'Đang tải…'));
  let ds = [];
  try { ds = await api.call('sx.api.qc_thietbi.lich_su', { thiet_bi: x.name }); } catch (e) { toastErr(e.message); }
  m.body.innerHTML = '';
  if (!ds.length) m.body.appendChild(khungTrong('Chưa có lần kiểm nào.'));
  ds.forEach((k) => {
    const the = el('div', `sx-qc-sc ${k.ket_qua === 'Đạt' ? 'sx-qc-sc-dong' : 'sx-qc-sc-mo'}`);
    the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(ngayDu(k.ngay))} · ${esc(k.ket_qua)}`));
    const meta = el('div', 'sx-qc-sc-meta');
    meta.appendChild(chip(k.hinh_thuc || 'Kiểm tra nội bộ'));
    if (k.sai_so) meta.appendChild(chip(`sai số ${k.sai_so} °C`));
    if (k.so_giay) meta.appendChild(chip(`giấy ${k.so_giay}`));
    if (k.han_giay) meta.appendChild(chip(`hạn ${ngayDu(k.han_giay)}`));
    meta.appendChild(el('span', null, esc(k.nguoi_kiem || '')));
    the.appendChild(meta);
    if (k.ghi_chu) the.appendChild(el('div', 'sx-qc-goiy', esc(k.ghi_chu)));
    if (k.su_co) the.appendChild(el('div', 'sx-qc-goiy', `Phiếu sự cố: <b>${esc(k.su_co)}</b>`));
    if (dl.la_iso || (k.nguoi_kiem === dl.user && k.creation === dl.hom_nay)) {
      const xoa = el('button', 'sx-btn sx-btn-ghost', 'XOÁ (ghi nhầm)');
      xoa.type = 'button';
      xoa.addEventListener('click', () => {
        m.close();
        confirm2Step({
          title: `Xoá phiếu kiểm ${x.name} ngày ${ngayDu(k.ngay)}?`,
          message: 'Hạn kiểm và trạng thái thiết bị sẽ tính lại theo các phiếu còn lại.',
          confirmLabel: 'XOÁ',
          onConfirm: async () => {
            await api.call('sx.api.qc_thietbi.xoa_kiem', { name: k.name });
            toast('Đã xoá');
            lai();
          },
        });
      });
      the.appendChild(xoa);
    }
    m.body.appendChild(the);
  });
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
