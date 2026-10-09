// #/qc/tiepnhan — tiếp nhận nguyên liệu BM.07.03 + kiểm xe BM.09.01 trên điện thoại (W33, D160).
//
// QC chế biến không có Desk, mà phần QC của tiếp nhận nằm trên phiếu nhập mua (Purchase Receipt) /
// hoá đơn mua có trừ kho. Màn này: danh sách phiếu NHÁP 14 ngày → mở một phiếu → kiểm xe (cùng lúc
// với hàng) + từng dòng: lô NCC, CQ/CO, COA vi sinh, aflatoxin, độ ẩm, cảm quan, kết luận → LƯU.
// Server lưu bằng doc.save() nên luật y như Desk: xe không đạt / thiếu COA / thiếu giấy tờ → ép
// Cách ly, lô Cách ly vào kho cách ly; lời cảnh báo hiện ngay dưới đầu phiếu. Duyệt phiếu là việc
// của thủ kho. Ảnh (hàng, giấy tờ, xe) chụp xong gửi ngay, nén trên máy.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';
import { chip, khungTrong, segment } from '/assets/sx/sx/components/qcui.js';
import { nenAnh } from '/assets/sx/sx/lib/anh.js';

const ngayVN = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const ANH_MOT_LAN = 4;            // khớp ANH_MOT_LAN ở sx/api/qc.py
const DAT = 'Đạt';
const KHONG_DAT = 'Không đạt';

/** Kết luận kiểm xe theo các mục — như sx/qc/kiem_xe.ket_luan: có mục Không đạt → Không đạt; đủ
 *  mục Đạt mà chưa kết luận → Đạt; còn lại giữ lựa chọn của người kiểm. Hàm THUẦN để test. */
export function ketLuanXe(giaTri, dang) {
  if (giaTri.includes(KHONG_DAT)) return KHONG_DAT;
  if (!dang && giaTri.length && giaTri.every((v) => v === DAT)) return DAT;
  return dang || '';
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc_tiepnhan.ds_tiep_nhan', {});
  container.innerHTML = '';
  container.appendChild(el('div', 'sx-field-label', `Tiếp nhận nguyên liệu — BM.07.03 · phiếu nhập mua nháp ${dl.so_ngay} ngày`));
  const khoi = (tieuDe, ds, trong) => {
    container.appendChild(el('div', 'sx-field-label sx-xx-khoi', `${esc(tieuDe)} (${ds.length})`));
    const box = el('div', 'sx-qc-than');
    if (!ds.length && trong) box.appendChild(khungTrong(trong));
    ds.forEach((x) => box.appendChild(thePhieu(x, dl, api)));
    container.appendChild(box);
  };
  khoi('Chờ kiểm', dl.ds.filter((x) => !x.xong), 'Không có phiếu nhập mua nào chờ kiểm.');
  const xong = dl.ds.filter((x) => x.xong);
  if (xong.length) khoi('Đã kiểm đủ — chờ thủ kho duyệt', xong);

  // W36 (D167): sổ BM.07.03 theo tháng — một dòng mỗi lô của phiếu đã duyệt.
  const inHang = el('div', 'sx-xx-ngay');
  const th = el('input', 'sx-textarea');
  th.type = 'month';
  th.value = dl.thang || '';
  th.max = dl.thang || '';
  const inB = el('button', 'sx-btn sx-btn-ghost', '🖨 IN SỔ BM.07.03');
  inB.type = 'button';
  inB.addEventListener('click', async () => {
    const thang = th.value || dl.thang;
    try {
      const html = await call('sx.api.qc_tiepnhan.in_bm0703', { thang });
      const w = window.open('', '_blank');
      if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
      w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
        + `<title>BM.07.03 — ${esc(thang)}</title></head><body>${html}</body></html>`);
      w.document.close();
      w.focus();
      setTimeout(() => w.print(), 250);
    } catch (e) { toastErr(e.message); }
  });
  inHang.appendChild(th);
  inHang.appendChild(inB);
  container.appendChild(inHang);
}

function thePhieu(x, dl, api) {
  const the = el('div', `sx-qc-sc sx-qc-sc-${x.xong ? 'dong' : 'cho'}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(x.ncc)} · ${esc(ngayVN(x.ngay))}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(x.name));
  if (x.loai_ncc) meta.appendChild(chip(x.loai_ncc));
  meta.appendChild(chip(`kết luận ${x.da_kl}/${x.so_dong} dòng`, x.da_kl < x.so_dong ? 'han' : 'dong'));
  if (x.xe_can) meta.appendChild(chip(x.xe_kl ? `xe: ${x.xe_kl}` : 'xe: chưa kiểm', x.xe_kl === DAT ? 'dong' : (x.xe_kl ? 'cao' : 'han')));
  if (x.nguoi_kiem) meta.appendChild(el('span', null, `QC ${esc(x.nguoi_kiem.split('@')[0])}`));
  the.appendChild(meta);
  const b = el('button', `sx-btn ${x.xong ? 'sx-btn-ghost' : 'sx-btn-primary'}`, x.xong || !dl.duoc_ghi ? 'MỞ PHIẾU' : 'KIỂM TIẾP NHẬN');
  b.type = 'button';
  b.addEventListener('click', async () => {
    b.disabled = true;
    try { moPhieu(await api.call('sx.api.qc_tiepnhan.xem_phieu', { doctype: x.doctype, name: x.name }), api); } catch (e) {
      toastErr(e.message);
    }
    b.disabled = false;
  });
  const nut = el('div', 'sx-qc-lm-nut');
  nut.appendChild(b);
  the.appendChild(nut);
  return the;
}

function oChu(nhan, gt, onSet, khoa, goiY = '') {
  const o = el('label', 'sx-tn-o');
  o.appendChild(el('span', 'sx-qc-goiy', esc(nhan)));
  const n = el('input', 'sx-textarea');
  n.type = 'text';
  n.value = gt || '';
  n.placeholder = goiY;
  n.maxLength = 140;
  n.disabled = khoa;
  n.addEventListener('input', () => onSet(n.value));
  o.appendChild(n);
  return o;
}

function oChon(nhan, lua, gt, onSet, khoa, goiY = '') {
  const o = el('div', 'sx-tn-o');
  o.appendChild(el('span', 'sx-qc-goiy', `${esc(nhan)}${goiY ? ` · <b>${esc(goiY)}</b>` : ''}`));
  o.appendChild(segment(lua, gt, onSet, khoa, true));
  return o;
}

function khoiXe(xe, khoa) {
  const box = el('div', 'sx-tn-xe');
  box.appendChild(el('div', 'sx-field-label', `Kiểm xe BM.09.01${xe.ap_dung ? '' : ' (không bắt buộc với NCC này)'}`));
  const hang = el('div', 'sx-xx-ngay');
  hang.appendChild(oChu('Biển số xe', xe.custom_xe_bien_so, (v) => { xe.custom_xe_bien_so = v; }, khoa, 'vd 29C-123.45'));
  hang.appendChild(oChu('Đơn vị vận chuyển', xe.custom_xe_don_vi, (v) => { xe.custom_xe_don_vi = v; }, khoa, 'nhà xe / NCC tự chở'));
  box.appendChild(hang);
  // W34 (D165): "lái xe ký" = tên lái xe — lái xe ký xác nhận kết quả kiểm (QT.09 mục 5.2).
  box.appendChild(oChu('Lái xe (ký xác nhận)', xe.custom_xe_tai_xe, (v) => { xe.custom_xe_tai_xe = v; }, khoa));
  const kl = el('div');
  const veKl = () => {
    kl.innerHTML = '';
    kl.appendChild(oChon('Kết luận kiểm xe', [DAT, KHONG_DAT], xe.custom_xe_ket_luan,
      (v) => { xe.custom_xe_ket_luan = v; }, khoa,
      xe.custom_xe_ket_luan === KHONG_DAT ? 'xe không đạt → mọi dòng Cách ly' : ''));
  };
  xe.muc.forEach((m) => {
    box.appendChild(oChon(m.yc && m.yc !== m.nhan ? `${m.nhan} — ${m.yc}` : m.nhan, [DAT, KHONG_DAT], xe[m.f], (v) => {
      xe[m.f] = v;
      const moi = ketLuanXe(xe.muc.map((x) => xe[x.f] || ''), xe.custom_xe_ket_luan);
      if (moi !== xe.custom_xe_ket_luan) { xe.custom_xe_ket_luan = moi; veKl(); }
    }, khoa));
  });
  veKl();
  box.appendChild(kl);
  box.appendChild(oChu('Xử lý / ghi chú kiểm xe (mục nào K: ghi xử lý)', xe.custom_xe_ghi_chu,
    (v) => { xe.custom_xe_ghi_chu = v; }, khoa));
  if (xe.qc_kiem) {
    box.appendChild(el('div', 'sx-qc-goiy', `QC kiểm: ${esc(xe.qc_kiem.split('@')[0])} · ${esc(xe.qc_luc.slice(8, 10))}/`
      + `${esc(xe.qc_luc.slice(5, 7))} ${esc(xe.qc_luc.slice(11, 16))} — tính là chuyến QC kiểm trong tuần (QT.09).`));
  }
  return box;
}

function dongHang(r, d, khoa) {
  const o = el('div', 'sx-xx-muc');
  o.appendChild(el('div', 'sx-xx-muc-ten',
    `<b>${r.idx}.</b> ${esc(r.item_name)} · ${esc(String(r.qty))} ${esc(r.uom)}${r.kho ? ` · <span class="sx-qc-goiy">${esc(r.kho)}</span>` : ''}`));
  const lc = d.lua_chon;
  o.appendChild(oChu('Lô NCC (số lô trên bao bì)', r.custom_ncc_lo, (v) => { r.custom_ncc_lo = v; }, khoa));
  o.appendChild(oChon('CQ / CO', lc.custom_co_cq, r.custom_co_cq, (v) => { r.custom_co_cq = v; }, khoa));
  o.appendChild(oChon('COA vi sinh', lc.custom_coa_vi_sinh, r.custom_coa_vi_sinh, (v) => { r.custom_coa_vi_sinh = v; },
    khoa, r.can_coa ? 'nhóm hàng bắt buộc COA' : ''));
  if (r.can_aflatoxin || r.custom_aflatoxin) {
    o.appendChild(oChon('Kết quả aflatoxin', lc.custom_aflatoxin, r.custom_aflatoxin, (v) => { r.custom_aflatoxin = v; },
      khoa, r.can_aflatoxin ? 'nhóm hàng phải có' : ''));
  }
  // W40 (D162): đỗ, lạc không đo độ ẩm khi nhận — ô chỉ hiện khi site đặt ngưỡng, hoặc dòng đã có số cũ.
  const coAm = d.do_am_toi_da || r.custom_do_am != null;
  const am = el('button', 'sx-qc-oso-khung', '');
  am.type = 'button';
  am.disabled = khoa;
  const veAm = () => {
    am.innerHTML = `<span class="sx-qc-oso-val">${r.custom_do_am != null ? esc(String(r.custom_do_am)) : '—'}</span>`
      + `<span class="sx-qc-oso-dv">% ẩm${d.do_am_toi_da ? ` · ngưỡng ≤ ${esc(String(d.do_am_toi_da))}` : ''}</span>`;
  };
  veAm();
  const oAm = el('div', 'sx-tn-o');
  oAm.appendChild(el('span', 'sx-qc-goiy', 'Độ ẩm (%)'));
  oAm.appendChild(am);
  am.addEventListener('click', () => openNumpad({
    kicker: `Dòng ${r.idx}`, title: `${r.item_name} — độ ẩm (%)`, initial: r.custom_do_am != null ? String(r.custom_do_am) : '',
    allowDecimal: true, unitLabel: '%',
    onOk: (n) => { r.custom_do_am = n > 0 ? n : null; veAm(); },
  }));
  if (coAm) o.appendChild(oAm);
  o.appendChild(oChon('Cảm quan', lc.custom_cam_quan_dat, r.custom_cam_quan_dat, (v) => { r.custom_cam_quan_dat = v; }, khoa));
  o.appendChild(oChon('Kết luận tiếp nhận', lc.custom_ket_luan, r.custom_ket_luan, (v) => { r.custom_ket_luan = v; }, khoa));
  if (r.giay_to) o.appendChild(el('div', 'sx-xx-goiy', `Giấy tờ lô: ${esc(r.giay_to)}`));
  return o;
}

function khoiAnh(d, api) {
  const box = el('div', 'sx-tn-anh');
  const nhan = el('div', 'sx-qc-goiy', `Ảnh hàng / giấy tờ / xe: ${d.so_anh}`);
  box.appendChild(nhan);
  const hang = el('div', 'sx-xx-ngay');
  const gui = async (chup, b) => {
    const files = await new Promise((ok) => {
      const inp = document.createElement('input');
      inp.type = 'file';
      inp.accept = 'image/*';
      if (chup) inp.setAttribute('capture', 'environment'); else inp.multiple = true;
      inp.addEventListener('change', () => ok([...(inp.files || [])]));
      inp.click();
    });
    if (!files.length) return;
    b.disabled = true;
    try {
      const anh = [];
      for (const f of files.slice(0, ANH_MOT_LAN)) anh.push((await nenAnh(f)).base64);
      const r = await api.call('sx.api.qc_tiepnhan.them_anh', { doctype: d.doctype, name: d.name, anh: JSON.stringify(anh) });
      d.so_anh = r.so_anh;
      nhan.textContent = `Ảnh hàng / giấy tờ / xe: ${d.so_anh}`;
      toast(`Đã gửi ${anh.length} ảnh`);
    } catch (e) { toastErr(e.message); }
    b.disabled = false;
  };
  if (d.them_anh) {
    [['📷 CHỤP ẢNH', true], ['🖼 Ảnh có sẵn', false]].forEach(([t, chup]) => {
      const b = el('button', `sx-btn${chup ? ' sx-btn-primary' : ' sx-btn-ghost'}`, t);
      b.type = 'button';
      b.addEventListener('click', () => gui(chup, b));
      hang.appendChild(b);
    });
  }
  const xem = el('button', 'sx-btn sx-btn-ghost', 'XEM ẢNH');
  xem.type = 'button';
  xem.addEventListener('click', async () => {
    try {
      const ds = await api.call('sx.api.qc_tiepnhan.anh_phieu', { doctype: d.doctype, name: d.name });
      const m = openModal({ kicker: 'Ảnh tiếp nhận', title: d.name });
      if (!ds.length) m.body.appendChild(el('div', 'sx-muted', 'Phiếu này chưa có ảnh.'));
      ds.forEach((a) => {
        const img = el('img', 'sx-lm-anh-lon');
        img.src = a.url;
        img.alt = 'Ảnh tiếp nhận';
        m.body.appendChild(img);
      });
    } catch (e) { toastErr(e.message); }
  });
  hang.appendChild(xem);
  box.appendChild(hang);
  return box;
}

export function moPhieu(d, api) {
  const m = openModal({ kicker: `BM.07.03 · ${d.name}`, title: d.ncc });
  const khoa = !d.sua;
  const f = {
    dong: d.dong.map((r) => ({ ...r })), ghi_chu_qc: d.ghi_chu_qc || '',
    xe: d.xe ? { ...d.xe, muc: d.xe.muc } : null,
  };
  const thongTin = [ngayVN(d.ngay), d.ncc_loai || 'NCC chưa phân loại', d.ncc_nguon,
    d.ncc_duyet ? 'NCC đã duyệt BM.07.02' : 'NCC CHƯA duyệt BM.07.02'].filter(Boolean);
  m.body.appendChild(el('div', 'sx-modal-msg', esc(thongTin.join(' · '))
    + (d.pkn ? `<br>Phiếu kiểm nghiệm năm của NCC: ${esc(d.pkn.so_hieu)}${d.pkn.het_han ? ` · còn hạn đến ${esc(ngayVN(d.pkn.het_han))}` : ''}` : '')
    + (d.docstatus === 1 ? '<br><b>Phiếu đã duyệt — chỉ xem, thêm ảnh.</b>' : '')));
  (d.bao || []).forEach((b) => m.body.appendChild(el('div', 'sx-warn-text sx-tn-bao', esc(b))));
  if (f.xe && (f.xe.ap_dung || f.xe.custom_xe_ket_luan || f.xe.custom_xe_bien_so)) m.body.appendChild(khoiXe(f.xe, khoa));
  m.body.appendChild(el('div', 'sx-field-label sx-xx-khoi', `Hàng nhận (${f.dong.length} dòng)`));
  f.dong.forEach((r) => m.body.appendChild(dongHang(r, d, khoa)));
  const gc = el('textarea', 'sx-textarea');
  gc.rows = 2;
  gc.placeholder = 'Ghi chú QC';
  gc.value = f.ghi_chu_qc;
  gc.disabled = khoa;
  gc.addEventListener('input', () => { f.ghi_chu_qc = gc.value; });
  m.body.appendChild(gc);
  m.body.appendChild(khoiAnh(d, api));
  if (d.sua) {
    const b = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU KẾT QUẢ KIỂM');
    b.type = 'button';
    b.addEventListener('click', async () => {
      b.disabled = true;
      const goi = {
        dong: f.dong.map((r) => ({
          name: r.name, custom_ncc_lo: r.custom_ncc_lo, custom_co_cq: r.custom_co_cq,
          custom_coa_vi_sinh: r.custom_coa_vi_sinh, custom_aflatoxin: r.custom_aflatoxin, custom_do_am: r.custom_do_am,
          custom_cam_quan_dat: r.custom_cam_quan_dat, custom_ket_luan: r.custom_ket_luan,
        })),
        ghi_chu_qc: f.ghi_chu_qc,
      };
      if (f.xe) {
        goi.xe = {};
        ['custom_xe_bien_so', 'custom_xe_don_vi', 'custom_xe_tai_xe', 'custom_xe_ghi_chu', 'custom_xe_ket_luan',
          ...f.xe.muc.map((x) => x.f)]
          .forEach((k) => { goi.xe[k] = f.xe[k] || ''; });
      }
      try {
        const moi = await api.call('sx.api.qc_tiepnhan.luu_phieu', { doctype: d.doctype, name: d.name, payload: JSON.stringify(goi) });
        toast(moi.bao && moi.bao.length ? 'Đã lưu — xem cảnh báo trên đầu phiếu' : 'Đã lưu');
        m.close();
        moPhieu(moi, api);
        render(api);
      } catch (e) { b.disabled = false; toastErr(e.message); }
    });
    m.body.appendChild(b);
    m.body.appendChild(el('div', 'sx-qc-goiy', 'Thủ kho duyệt phiếu nhập trên Desk — duyệt xong thì phần QC khoá.'));
  }
}
