// #/qc/lichviec — lịch việc định kỳ cho hồ sơ giấy (W21, D146).
//
// Việc năm / quý / tháng (thử khôi phục dữ liệu, thay bóng đèn bẫy…): hạn lần tới, nhắc trước
// bao nhiêu ngày. "ĐÃ LÀM" ghi lần làm và dời hạn sang kỳ sau tính từ hạn cũ. Hộp nhắc màn Hôm
// nay báo việc quá hạn / sắp đến hạn. Luật ở sx/qc/viec_dinh_ky.py.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment } from '/assets/sx/sx/components/qcui.js';

const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const KIEU = { 'Quá hạn': 'cao', 'Sắp đến hạn': 'oprp', 'Còn hạn': 'dong', 'Ngừng': '' };

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc_lichviec.tong_quan', {});
  container.innerHTML = '';
  const lai = () => render(api);

  container.appendChild(el('div', 'sx-qc-top', `<div style="flex:1;min-width:0">
    <div class="sx-qc-ngay">📅 Việc định kỳ</div>
    <div class="sx-qc-ai">việc năm / quý cho hồ sơ giấy — lên hộp nhắc khi sắp đến hạn</div></div>`));

  if (!dl.ds.length) container.appendChild(khungTrong('Chưa có việc định kỳ nào.'));
  dl.ds.forEach((v) => {
    const the = el('div', `sx-qc-sc ${v.trang_thai === 'Quá hạn' ? 'sx-qc-sc-mo' : 'sx-qc-sc-dong'}`);
    the.appendChild(el('div', 'sx-qc-sc-ten', esc(v.ten)));
    const meta = el('div', 'sx-qc-sc-meta');
    meta.appendChild(chip(v.trang_thai, KIEU[v.trang_thai]));
    meta.appendChild(chip(v.chu_ky));
    if (v.trang_thai !== 'Ngừng') {
      meta.appendChild(el('span', null, v.con < 0 ? `<b>quá hạn ${-v.con} ngày</b> (${esc(ngayDu(v.han))})`
        : `hạn ${esc(ngayDu(v.han))} · còn ${v.con} ngày`));
    }
    if (v.phu_trach) meta.appendChild(el('span', null, esc(v.phu_trach)));
    the.appendChild(meta);
    if (v.mo_ta) the.appendChild(el('div', 'sx-qc-goiy', esc(v.mo_ta)));
    if (v.lan_cuoi) {
      const l = v.lich_su[0] || {};
      the.appendChild(el('div', 'sx-qc-goiy', `Làm gần nhất ${esc(ngayDu(v.lan_cuoi))}${l.nguoi ? ` · ${esc(l.nguoi)}` : ''}${
        l.ghi_chu ? ` · ${esc(l.ghi_chu)}` : ''}`));
    }
    if (dl.duoc_ghi) {
      const nut = el('div', 'sx-qc-chips sx-tb-nut');
      if (v.trang_thai !== 'Ngừng') {
        const b = el('button', 'sx-btn sx-btn-primary', 'ĐÃ LÀM');
        b.type = 'button';
        b.addEventListener('click', () => moDaLam(v, dl, api, lai));
        nut.appendChild(b);
      }
      const s = el('button', 'sx-btn sx-btn-ghost', 'SỬA');
      s.type = 'button';
      s.addEventListener('click', () => moSua(v, dl, api, lai));
      nut.appendChild(s);
      the.appendChild(nut);
    }
    container.appendChild(the);
  });

  if (dl.duoc_ghi) {
    const them = el('button', 'sx-btn sx-btn-primary sx-btn-big', '+ THÊM VIỆC ĐỊNH KỲ');
    them.type = 'button';
    them.addEventListener('click', () => moSua(null, dl, api, lai));
    container.appendChild(them);
  }
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

function moDaLam(v, dl, api, lai) {
  const m = openModal({ kicker: `ĐÃ LÀM · kỳ hạn ${ngayDu(v.han)}`, title: v.ten });
  const ng = oNhap(m.body, 'Ngày làm', dl.hom_nay, 'date');
  ng.max = dl.hom_nay;
  const gc = oNhap(m.body, 'Ghi chú / số biên bản', '', 'ta');
  m.body.appendChild(el('div', 'sx-qc-goiy', v.chu_ky === 'Một lần' ? 'Việc một lần — làm xong thì ngừng nhắc.'
    : `Hạn kỳ sau tính từ hạn cũ (${ngayDu(v.han)}) + 1 ${v.chu_ky.toLowerCase()}.`));
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'GHI ĐÃ LÀM');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc_lichviec.da_lam', { name: v.name, payload: JSON.stringify({ ngay: ng.value, ghi_chu: gc.value }) });
      toast(r.ngung ? 'Đã ghi — việc một lần, ngừng nhắc' : `Đã ghi — hạn kỳ sau ${ngayDu(r.han)}`);
      m.close();
      lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

function moSua(v, dl, api, lai) {
  const m = openModal({ kicker: 'VIỆC ĐỊNH KỲ', title: v ? v.ten : 'Thêm việc định kỳ' });
  const ten = oNhap(m.body, 'Việc', v ? v.ten : '');
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Chu kỳ'));
  let ck = v ? v.chu_ky : 'Năm';
  m.body.appendChild(segment(dl.chu_ky, ck, (x) => { ck = x || 'Năm'; }, false));
  const han = oNhap(m.body, 'Hạn lần tới', v ? v.han : '', 'date');
  const bt = oNhap(m.body, 'Nhắc trước (ngày)', v ? v.bao_truoc : 14, 'number');
  bt.inputMode = 'numeric';
  const pt = oNhap(m.body, 'Phụ trách', v ? v.phu_trach : '');
  const hs = oNhap(m.body, 'Hồ sơ / biểu mẫu liên quan', v ? v.ho_so : '');
  const mt = oNhap(m.body, 'Làm gì', v ? v.mo_ta : '', 'ta');
  const nl = el('label', 'sx-sc-check');
  const nc = el('input');
  nc.type = 'checkbox';
  nc.checked = !!(v && v.ngung);
  nl.appendChild(nc);
  nl.appendChild(el('span', null, 'Ngừng (không nhắc nữa)'));
  m.body.appendChild(nl);
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!ten.value.trim()) { toastErr('Nhập tên việc.'); return; }
    if (!han.value) { toastErr('Chọn hạn lần tới.'); return; }
    ok.disabled = true;
    try {
      await api.call('sx.api.qc_lichviec.luu', { payload: JSON.stringify({
        name: v ? v.name : null, ten: ten.value, chu_ky: ck, han: han.value, bao_truoc: bt.value, phu_trach: pt.value,
        ho_so: hs.value, mo_ta: mt.value, ngung: nc.checked ? 1 : 0 }) });
      toast('Đã lưu');
      m.close();
      lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}
