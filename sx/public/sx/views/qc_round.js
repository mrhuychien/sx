// #/qc/round/:name — làm một lượt kiểm. Một trang dài, đúng trình tự công đoạn.
//
// Vì sao MỘT trang dài chứ không chia bước: QC đi một vòng xưởng theo đúng thứ
// tự này. Chia thành tab/bước là bắt người ta bấm Tiếp — Quay lại giữa lúc tay
// đang bận, và tệ hơn: giấu mất "còn bao nhiêu mục nữa", thứ quyết định người ta
// có làm hết lượt hay không.
//
// TỰ LƯU sau mỗi thay đổi (gộp 300 ms). Không có nút Lưu, vì nút Lưu nghĩa là
// có lúc dữ liệu chỉ nằm trong màn hình — mà giữa xưởng thì điện thoại tắt màn,
// hết pin, rơi. Mất mạng thì xếp hàng chờ, thanh đáy nói rõ còn mấy mục chưa lên.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import {
  chip, hangChon, oCheck, oChon3, oChu, oGio, oSo, tieuDeBuoc,
} from '/assets/sx/sx/components/qcui.js';
import { formatTime } from '/assets/sx/sx/lib/format.js';

// Ba lựa chọn THẬT. Không thêm nút "—" cho trạng thái trống: bỏ trống là bấm
// lại đúng nút đang chọn, giống mọi mục Đạt/Không đạt khác. Một nút riêng cho
// "chưa chọn" dạy người ta rằng chưa chọn cũng là một lựa chọn phải bấm.
const B7 = [
  { v: 'Không có chuyển đổi', ten: 'Không có' },
  { v: 'Âm tính', ten: 'Âm tính' },
  { v: 'Dương tính', ten: 'Dương tính' },
];

/** Giờ trên MÁY QC, dạng server đọc được. Cố tình lấy giờ máy chứ không phải
 *  giờ server: khi ghi ngoại tuyến rồi gửi sau, chỗ lệch giữa hai giờ đó chính
 *  là thứ auditor cần thấy. */
function gioMay() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} `
    + `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

const DEM = ['thung_bot_qua_han', 't2_so_bay_dau_hieu'];

/** Bản sao client của muc.co_ghi() bên server. Chỉ để vẽ thanh tiến độ —
 *  server vẫn là chỗ quyết định. Lệch nhau thì thanh tiến độ sai, không phải
 *  dữ liệu sai. */
function daCham(m, v) {
  if (m.kieu === 'co_khong') return true;
  if (v === null || v === undefined || v === '') return false;
  if ((m.kieu === 'so' || m.kieu === 'nguyen') && !DEM.includes(m.f)) {
    return Number(v) !== 0;
  }
  return true;
}

export async function render({ container, call, tham_so }) {
  if (!tham_so) { window.location.hash = '#/qc'; return; }
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc.chi_tiet_round', { name: tham_so });
  const hom = await call('sx.api.qc.get_today', { ngay: dl.ngay });
  container.innerHTML = '';

  const giaTri = { ...dl.gia_tri, ghi_chu: dl.ghi_chu };
  const khoa = !dl.duoc_ghi;
  const apDung = new Set(dl.ap_dung);
  const muc = hom.muc.filter((m) => apDung.has(m.f));

  // ── đầu màn ─────────────────────────────────────────────────────────
  const dau = el('div', 'sx-qc-top');
  const tenLuot = `${dl.luot} · ${dl.ca} ${dl.ngay.slice(8)}/${dl.ngay.slice(5, 7)}`;
  dau.innerHTML = `<div style="flex:1;min-width:0">
      <div class="sx-qc-ngay" style="font-size:var(--sx-f-md)">${esc(tenLuot)}</div>
      <div class="sx-qc-ai" id="sx-qc-gio">bắt đầu ${esc(formatTime(dl.started_at))}</div>
    </div>`;
  const thoat = el('button', 'sx-btn sx-btn-ghost', '✕');
  thoat.type = 'button';
  thoat.title = 'Về màn Hôm nay';
  thoat.addEventListener('click', () => { window.location.hash = '#/qc'; });
  dau.appendChild(thoat);
  container.appendChild(dau);

  if (dl.docstatus === 1) {
    const b = el('div', 'sx-qc-chips');
    b.appendChild(chip(`hoàn tất ${formatTime(dl.finished_at)} · ${dl.duration_min} phút`,
      'dong'));
    if (dl.ghi_muon) b.appendChild(chip('ghi muộn', 'oprp'));
    if (dl.reviewed_on) b.appendChild(chip(`Ban ISO đã xem xét`, 'dong'));
    container.appendChild(b);
  }
  if (dl.truoc_do) {
    const t = dl.truoc_do;
    container.appendChild(el('div', 'sx-qc-luot-phu',
      esc(`Lượt trước (${t.ngay} ${t.ca} ${t.luot}): rang ${t.rang_nhiet_do || '—'} °C`
        + ` · vòng quay ${t.rang_vong_quay || '—'}`)));
  }

  // ── tự lưu ──────────────────────────────────────────────────────────
  const cho = {};
  let hen = null;
  let dangGui = false;
  const nhanLuu = el('div', 'sx-qc-luu', 'chưa có thay đổi');

  async function gui() {
    if (dangGui || !Object.keys(cho).length) return;
    const values = { ...cho };
    Object.keys(cho).forEach((k) => delete cho[k]);
    dangGui = true;
    try {
      const kq = await call('sx.api.qc.save_round', {
        name: dl.name, values, client_ts: gioMay(),
      });
      if (kq && kq._hang_cho) {
        nhanLuu.className = 'sx-qc-luu sx-qc-luu-cho';
        nhanLuu.textContent = 'mất mạng — đã lưu trên máy';
      } else {
        nhanLuu.className = 'sx-qc-luu';
        nhanLuu.textContent = `đã lưu ${formatTime(kq.luc)}`;
        if (kq.bo_qua && kq.bo_qua.length) {
          // Server bỏ qua = có người khác ghi mục đó SAU mình. Nói ra, đừng im:
          // im thì QC nhìn màn hình thấy số của mình mà trên server là số khác.
          toast(`${kq.bo_qua.length} mục người khác vừa ghi mới hơn — tải lại để xem`);
        }
      }
    } catch (e) {
      // Trả lại hàng: dữ liệu QC gõ tay giữa xưởng không được phép biến mất vì
      // một lần gọi hỏng.
      Object.assign(cho, values, cho);
      nhanLuu.className = 'sx-qc-luu sx-qc-luu-loi';
      nhanLuu.textContent = 'chưa lưu được — sẽ thử lại';
      toastErr(e.message);
    } finally {
      dangGui = false;
      if (Object.keys(cho).length) setTimeout(gui, 1500);
    }
  }

  function onSet(f, v) {
    giaTri[f] = v;
    cho[f] = v;
    nhanLuu.className = 'sx-qc-luu sx-qc-luu-cho';
    nhanLuu.textContent = 'đang lưu…';
    veTienDo();
    if (hen) clearTimeout(hen);
    hen = setTimeout(gui, 300);
  }

  // ── thân: từng bước, từng mục ───────────────────────────────────────
  const than = el('div');
  container.appendChild(than);
  const demBuoc = {};
  hom.buoc.forEach((b) => {
    const cua = muc.filter((m) => m.buoc === b.ma);
    if (!cua.length) return;
    const tieu = tieuDeBuoc(b, 0, cua.filter((m) => !m.phu).length);
    demBuoc[b.ma] = { node: tieu.querySelector('.sx-qc-buoc-dem'), muc: cua };
    than.appendChild(tieu);
    cua.forEach((m) => than.appendChild(veMuc(m, giaTri[m.f], onSet, hom.nguong, khoa)));
  });

  // ── ghi chú ─────────────────────────────────────────────────────────
  than.appendChild(el('div', 'sx-qc-buoc',
    '<span class="sx-qc-buoc-ten">Ghi chú</span>'));
  const ta = el('textarea');
  ta.rows = 3;
  ta.className = 'sx-textarea';
  ta.placeholder = 'lý do mục để trống, rework, chuyển đổi…';
  ta.value = giaTri.ghi_chu || '';
  ta.disabled = khoa;
  ta.addEventListener('input', () => onSet('ghi_chu', ta.value));
  const taBox = el('div');
  taBox.style.padding = '0 var(--sx-s3) var(--sx-s4)';
  taBox.appendChild(ta);
  than.appendChild(taBox);

  // ── thanh đáy ───────────────────────────────────────────────────────
  const day = el('div', 'sx-qc-day');
  const trai = el('div', 'sx-qc-day-trai');
  const so = el('div', 'sx-qc-day-so');
  const thanh = el('div', 'sx-qc-thanh', '<i></i>');
  trai.appendChild(so);
  trai.appendChild(thanh);
  trai.appendChild(nhanLuu);
  day.appendChild(trai);
  const nutXong = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'HOÀN TẤT LƯỢT');
  nutXong.type = 'button';
  nutXong.style.flex = '1';
  day.appendChild(nutXong);
  container.appendChild(day);

  function veTienDo() {
    const canCham = muc.filter((m) => !m.phu);
    const da = canCham.filter((m) => daCham(m, giaTri[m.f])).length;
    so.innerHTML = `${da}/${canCham.length} <span>mục</span>`;
    thanh.querySelector('i').style.width =
      `${canCham.length ? Math.round((da * 100) / canCham.length) : 0}%`;
    Object.entries(demBuoc).forEach(([, x]) => {
      const c = x.muc.filter((m) => !m.phu);
      x.node.textContent = `${c.filter((m) => daCham(m, giaTri[m.f])).length}/${c.length}`;
    });
  }
  veTienDo();

  if (dl.docstatus === 1 || khoa || !dl.duoc_chot) {
    nutXong.disabled = true;
    if (dl.docstatus === 1) nutXong.textContent = 'ĐÃ HOÀN TẤT';
    else if (khoa) nutXong.textContent = 'CHỈ XEM';
    else {
      // QC đóng gói: ghi được, chốt thì không. Nói ra ngay trên nút, đừng để
      // bấm rồi mới biết.
      nutXong.textContent = 'QC CHẾ BIẾN CHỐT';
      nutXong.title = `Bạn ghi được mục đóng gói. Chốt lượt là việc của ${dl.qc_user}.`;
    }
    if (dl.su_co.length) veKetQua(container, dl.su_co, call);
  } else {
    nutXong.addEventListener('click', async () => {
      nutXong.disabled = true;
      try {
        if (hen) clearTimeout(hen);
        await gui();                       // gửi nốt trước khi chốt
        const kq = await call('sx.api.qc.submit_round', { name: dl.name });
        toast(kq.su_co.length
          ? `Đã hoàn tất — sinh ${kq.su_co.length} phiếu sự cố`
          : 'Đã hoàn tất lượt');
        render({ container, call, tham_so });
      } catch (e) {
        nutXong.disabled = false;
        toastErr(e.message);
      }
    });
  }

  // Lệch sẽ thành sự cố — hiện TRƯỚC khi bấm hoàn tất.
  if (dl.se_thanh_su_co.length || dl.canh_bao.length) {
    const box = el('div', 'sx-qc-sc sx-qc-sc-mo');
    box.appendChild(el('div', 'sx-qc-sc-ten', 'Khi hoàn tất sẽ tạo phiếu sự cố'));
    dl.se_thanh_su_co.forEach((x) => box.appendChild(
      el('div', 'sx-qc-sc-meta', `• ${esc(x.mo_ta)}`)));
    dl.canh_bao.forEach((x) => box.appendChild(
      el('div', 'sx-qc-sc-meta', `⚠ ${esc(x)} (chỉ cảnh báo)`)));
    than.insertBefore(box, than.firstChild);
  }
}

function veMuc(m, v, onSet, ng, khoa) {
  if (m.kieu === 'so' || m.kieu === 'nguyen') return oSo(m, v, onSet, ng, khoa);
  if (m.kieu === 'chu') return oChu(m, v, onSet, khoa);
  if (m.kieu === 'gio') return oGio(m, v, onSet, khoa);
  if (m.kieu === 'co_khong') return oCheck(m, v, onSet, khoa);
  if (m.kieu === 'chon3') {
    return oChon3(m, v, onSet, B7, khoa);
  }
  return hangChon(m, v, onSet, khoa);
}

function veKetQua(container, suCo, call) {
  const box = el('div', 'sx-qc-sc sx-qc-sc-mo');
  box.appendChild(el('div', 'sx-qc-sc-ten',
    `${suCo.length} phiếu sự cố đã lập từ lượt này`));
  suCo.forEach((s) => {
    const h = el('div', 'sx-qc-sc-meta');
    h.appendChild(el('span', null, `${esc(s.name)} — ${esc(s.mo_ta)}`));
    const n = el('button', 'sx-btn sx-btn-ghost', 'GHI XỬ LÝ NGAY');
    n.type = 'button';
    n.addEventListener('click', () => moXuLy(s, call));
    h.appendChild(n);
    box.appendChild(h);
  });
  container.appendChild(box);
}

/** Ghi xử lý ngay — mở ngay tại chỗ, không bắt đi sang màn Sự cố.
 *  Lúc vừa phát hiện là lúc DUY NHẤT người ta còn nhớ đã làm gì với lô hàng đó. */
export function moXuLy(s, call, xong) {
  const m = openModal({ kicker: s.name, title: s.mo_ta || 'Phiếu sự cố' });
  const ta = el('textarea');
  ta.rows = 3;
  ta.className = 'sx-textarea';
  ta.placeholder = 'đã làm gì ngay lúc đó: dừng máy, cô lập lô, chỉnh nhiệt…';
  ta.value = s.xu_ly_ngay || '';
  const lo = el('input');
  lo.type = 'text';
  lo.className = 'sx-textarea';
  lo.placeholder = 'lô ảnh hưởng (HSD / ngày nghiền / vị)';
  lo.value = s.lo_anh_huong || '';
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Xử lý ngay'));
  m.body.appendChild(ta);
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Lô ảnh hưởng'));
  m.body.appendChild(lo);
  const luu = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU');
  luu.type = 'button';
  luu.addEventListener('click', async () => {
    luu.disabled = true;
    try {
      await call('sx.api.qc.update_incident', {
        name: s.name,
        payload: JSON.stringify({ xu_ly_ngay: ta.value, lo_anh_huong: lo.value }),
      });
      toast('Đã ghi xử lý');
      m.close();
      if (xong) xong();
    } catch (e) {
      luu.disabled = false;
      toastErr(e.message);
    }
  });
  m.body.appendChild(luu);
  return m;
}
