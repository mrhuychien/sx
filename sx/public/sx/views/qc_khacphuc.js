// #/qc/khacphuc — phiếu hành động khắc phục BM.01.07 (W24, D150): nút thứ ba trong tab Sự cố.
//
// Ba nhóm: Đang mở (quá hạn viền đỏ) · Chờ kiểm tra hiệu lực · Đã đóng. Ai vào được màn QC đều ghi
// được nội dung và báo "đã thực hiện"; Ban ISO / người được giao kiểm tra hiệu lực rồi mới đóng.
// #/qc/khacphuc?mo=CAR-… mở thẳng phiếu đó (nút trên phiếu sự cố). Luật ở sx/qc/khac_phuc.py.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment, tabSuCo } from '/assets/sx/sx/components/qcui.js';

const st = { tab: 'Mở' };
const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  let dl;
  try {
    dl = await call('sx.api.qc_khacphuc.tong_quan', {});
  } catch (e) {
    container.innerHTML = '';
    container.appendChild(tabSuCo('khacphuc'));
    container.appendChild(khungTrong(e.message));
    return;
  }
  container.innerHTML = '';
  container.appendChild(tabSuCo('khacphuc'));
  const lai = () => render(api);

  const mo = new URLSearchParams((window.location.hash.split('?')[1]) || '').get('mo');
  const can = mo && dl.ds.find((x) => x.name === mo);
  if (can) st.tab = can.trang_thai;

  container.appendChild(segment([
    { v: 'Mở', ten: `Đang mở (${dl.dem['Mở']})` },
    { v: 'Chờ kiểm tra', ten: `Chờ kiểm tra (${dl.dem['Chờ kiểm tra']})` },
    { v: 'Đóng', ten: 'Đã đóng' }], st.tab, (v) => { st.tab = v; lai(); }));
  if (dl.dem.qua_han) {
    container.appendChild(el('div', 'sx-qc-goiy', `<b>${dl.dem.qua_han} phiếu quá hạn hoàn thành</b> — nguyên nhân `
      + 'chưa xử lý thì sự cố còn lặp lại.'));
  }
  const ds = dl.ds.filter((x) => x.trang_thai === st.tab);
  if (!ds.length) {
    container.appendChild(khungTrong({ 'Mở': 'Không có phiếu khắc phục nào đang mở.',
      'Chờ kiểm tra': 'Không có phiếu nào chờ kiểm tra hiệu lực.', 'Đóng': 'Chưa có phiếu nào đã đóng.' }[st.tab]));
  }
  ds.forEach((x) => container.appendChild(veThe(x, dl, api, lai)));

  const them = el('button', 'sx-btn sx-btn-ghost sx-btn-big', '+ LẬP PHIẾU KHẮC PHỤC (không từ sự cố)');
  them.type = 'button';
  them.addEventListener('click', () => moLap(dl, api));
  container.appendChild(them);
  container.appendChild(el('div', 'sx-qc-goiy', 'Phiếu từ sự cố: mở phiếu sự cố → + LẬP PHIẾU KHẮC PHỤC.'));

  if (can) {
    history.replaceState(null, '', '#/qc/khacphuc');
    moSua(can, dl, api, lai);
  }
}

function veThe(x, dl, api, lai) {
  const the = el('div', `sx-qc-sc ${x.qua_han ? 'sx-qc-sc-mo' : 'sx-qc-sc-dong'}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', esc(x.mo_ta)));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(x.name));
  meta.appendChild(el('span', null, esc(ngayDu(x.ngay))));
  meta.appendChild(chip(x.su_co ? `sự cố ${x.su_co}` : x.nguon));
  if (x.su_co_info && x.su_co_info.muc_do === 'Cao') meta.appendChild(chip('mức CAO', 'cao'));
  if (x.qua_han) meta.appendChild(chip(`quá hạn ${ngayDu(x.han)}`, 'han'));
  else if (x.han && x.trang_thai === 'Mở') meta.appendChild(el('span', null, `hạn ${esc(ngayDu(x.han))}`));
  if (x.so_lan) meta.appendChild(chip(`${x.so_lan} lần chưa hiệu lực`, 'cao'));
  if (x.hieu_luc && x.trang_thai === 'Đóng') meta.appendChild(chip(x.hieu_luc));
  the.appendChild(meta);
  if (x.hanh_dong) the.appendChild(el('div', 'sx-qc-goiy', `Hành động: ${esc(x.hanh_dong)}${
    x.nguoi_thuc_hien ? ` · ${esc(x.nguoi_thuc_hien)}` : ''}`));
  else if (x.trang_thai === 'Mở') the.appendChild(el('div', 'sx-qc-goiy', '⚠ chưa ghi nguyên nhân / hành động'));
  if (x.ket_qua && x.trang_thai !== 'Mở') the.appendChild(el('div', 'sx-qc-goiy', `Kết quả: ${esc(x.ket_qua)}`));
  const nut = el('div', 'sx-qc-chips sx-tb-nut');
  const ghi = el('button', 'sx-btn sx-btn-ghost', x.trang_thai === 'Mở' ? 'GHI' : 'XEM');
  ghi.type = 'button';
  ghi.addEventListener('click', () => moSua(x, dl, api, lai));
  nut.appendChild(ghi);
  if (x.trang_thai === 'Chờ kiểm tra' && dl.duoc_kiem) {
    const k = el('button', 'sx-btn sx-btn-primary', 'KIỂM TRA HIỆU LỰC');
    k.type = 'button';
    k.addEventListener('click', () => moKiem(x, api, lai));
    nut.appendChild(k);
  }
  const inb = el('button', 'sx-btn sx-btn-ghost', '🖨 IN');
  inb.type = 'button';
  inb.addEventListener('click', () => inPhieu(x, api));
  nut.appendChild(inb);
  the.appendChild(nut);
  return the;
}

function oNhap(body, nhan, gt, kieu, khoa) {
  body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
  const n = el(kieu === 'ta' ? 'textarea' : 'input');
  n.className = 'sx-textarea';
  if (kieu === 'ta') n.rows = 3;
  else if (kieu) n.type = kieu;
  n.value = gt == null ? '' : gt;
  n.disabled = !!khoa;
  body.appendChild(n);
  return n;
}

function moLap(dl, api) {
  const m = openModal({ kicker: 'BM.01.07', title: 'Lập phiếu hành động khắc phục' });
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Nguồn'));
  let nguon = 'Đánh giá nội bộ';
  m.body.appendChild(segment(dl.nguon.filter((x) => x !== 'Sự cố'), nguon, (v) => { nguon = v || nguon; }, false));
  const mt = oNhap(m.body, 'Điều không phù hợp (bắt buộc)', '', 'ta');
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LẬP PHIẾU');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!mt.value.trim()) { toastErr('Ghi điều không phù hợp.'); return; }
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc_khacphuc.lap', { payload: JSON.stringify({ nguon, mo_ta: mt.value }) });
      m.close();
      // Đổi hash là router dựng lại màn và mở thẳng phiếu vừa lập (?mo=).
      window.location.hash = `#/qc/khacphuc?mo=${encodeURIComponent(r.name)}`;
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

function moSua(x, dl, api, lai) {
  const khoa = x.trang_thai !== 'Mở';
  const m = openModal({ kicker: `BM.01.07 · ${x.name} · ${x.trang_thai}`, title: x.mo_ta });
  if (x.su_co) {
    m.body.appendChild(el('div', 'sx-qc-goiy', `Từ phiếu sự cố <b>${esc(x.su_co)}</b>${x.su_co_info
      ? ` (${esc(ngayDu(x.su_co_info.ngay))}${x.su_co_info.muc_do === 'Cao' ? ', mức CAO' : ''})` : ''}`));
  }
  const mt = oNhap(m.body, 'Điều không phù hợp', x.mo_ta, 'ta', khoa);
  const nn = oNhap(m.body, 'Nguyên nhân gốc', x.nguyen_nhan, 'ta', khoa);
  const hd = oNhap(m.body, 'Hành động khắc phục (xoá nguyên nhân — khác xử lý ngay)', x.hanh_dong, 'ta', khoa);
  const ng = oNhap(m.body, 'Người thực hiện', x.nguoi_thuc_hien, '', khoa);
  const han = oNhap(m.body, 'Hạn hoàn thành', x.han, 'date', khoa);
  const kq = oNhap(m.body, 'Kết quả thực hiện', x.ket_qua, 'ta', khoa);
  const nx = oNhap(m.body, 'Ngày hoàn thành', x.ngay_xong, 'date', khoa);
  nx.max = dl.hom_nay;
  if (x.nhan_xet) m.body.appendChild(el('div', 'sx-qc-goiy', `Kiểm tra hiệu lực: ${esc(x.nhan_xet).replace(/\n/g, '<br>')}`));
  const goi = () => JSON.stringify({ mo_ta: mt.value, nguyen_nhan: nn.value, hanh_dong: hd.value,
    nguoi_thuc_hien: ng.value, han: han.value, ket_qua: kq.value, ngay_xong: nx.value });
  const gui = async (b, laGui) => {
    b.disabled = true;
    try {
      await api.call('sx.api.qc_khacphuc.luu', { name: x.name, payload: goi(), gui: laGui ? 1 : 0 });
      toast(laGui ? 'Đã báo thực hiện xong — chờ Ban ISO kiểm tra hiệu lực' : 'Đã lưu');
      m.close();
      lai();
    } catch (e) { b.disabled = false; toastErr(e.message); }
  };
  if (!khoa) {
    const luu = el('button', 'sx-btn sx-btn-ghost sx-btn-big', 'LƯU');
    luu.type = 'button';
    luu.addEventListener('click', () => gui(luu, false));
    m.body.appendChild(luu);
    const xong = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'ĐÃ THỰC HIỆN — GỬI KIỂM TRA');
    xong.type = 'button';
    xong.addEventListener('click', () => gui(xong, true));
    m.body.appendChild(xong);
  }
  if (x.trang_thai === 'Chờ kiểm tra') {
    if (dl.duoc_kiem) {
      const k = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'KIỂM TRA HIỆU LỰC');
      k.type = 'button';
      k.addEventListener('click', () => { m.close(); moKiem(x, api, lai); });
      m.body.appendChild(k);
    }
    const rut = el('button', 'sx-btn sx-btn-ghost', 'RÚT LẠI ĐỂ SỬA');
    rut.type = 'button';
    rut.addEventListener('click', async () => {
      try { await api.call('sx.api.qc_khacphuc.rut_lai', { name: x.name }); toast('Đã rút lại'); m.close(); lai(); } catch (e) { toastErr(e.message); }
    });
    m.body.appendChild(rut);
  }
  if (x.trang_thai === 'Đóng' && dl.duoc_kiem) {
    const ml = el('button', 'sx-btn sx-btn-ghost', 'MỞ LẠI');
    ml.type = 'button';
    ml.addEventListener('click', () => {
      const ly = window.prompt('Lý do mở lại (việc lặp lại, kiểm tra sau thấy chưa ổn…)');
      if (!ly) return;
      api.call('sx.api.qc_khacphuc.mo_lai', { name: x.name, ly_do: ly })
        .then(() => { toast('Đã mở lại'); m.close(); lai(); }).catch((e) => toastErr(e.message));
    });
    m.body.appendChild(ml);
  }
  if (x.trang_thai !== 'Đóng' && (dl.duoc_kiem || x.lap_boi === dl.user)) {
    const xoa = el('button', 'sx-btn sx-btn-ghost', 'XOÁ PHIẾU');
    xoa.type = 'button';
    xoa.addEventListener('click', () => confirm2Step({
      title: `Xoá ${x.name}?`, message: 'Lập nhầm thì xoá; còn việc thật thì để phiếu, ghi rõ và đóng.',
      confirmLabel: 'XOÁ',
      onConfirm: async () => { await api.call('sx.api.qc_khacphuc.xoa', { name: x.name }); toast('Đã xoá'); m.close(); lai(); },
    }));
    m.body.appendChild(xoa);
  }
}

function moKiem(x, api, lai) {
  const m = openModal({ kicker: `KIỂM TRA HIỆU LỰC · ${x.name}`, title: x.mo_ta });
  m.body.appendChild(el('div', 'sx-qc-goiy', `Hành động: ${esc(x.hanh_dong || '')}<br>Kết quả: ${esc(x.ket_qua || '')}`
    + ` (xong ${esc(ngayDu(x.ngay_xong))})`));
  let kl = '';
  m.body.appendChild(segment(['Có hiệu lực', 'Chưa hiệu lực'], kl, (v) => { kl = v; }, false));
  const nx = oNhap(m.body, 'Nhận xét (bắt buộc khi chưa hiệu lực — làm gì tiếp)', '', 'ta');
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'GHI KẾT LUẬN');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!kl) { toastErr('Chọn kết luận.'); return; }
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc_khacphuc.kiem_tra', { name: x.name, hieu_luc: kl, nhan_xet: nx.value });
      toast(r.trang_thai === 'Đóng' ? 'Đã đóng phiếu — có hiệu lực' : 'Chưa hiệu lực — phiếu quay về Đang mở');
      m.close();
      lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

async function inPhieu(x, api) {
  try {
    const html = await api.call('sx.api.qc_khacphuc.in_bm0107', { name: x.name });
    const w = window.open('', '_blank');
    if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
    // Cửa sổ about:blank không thừa kế bảng mã — tự khai, như các tờ in khác.
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>BM.01.07 — ${x.name}</title>`
      + `</head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 400);
  } catch (e) { toastErr(e.message); }
}
