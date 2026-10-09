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
import { kb, nenAnh } from '/assets/sx/sx/lib/anh.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';
import {
  batTatBot, chip, hangChon, oCheck, oChon3, oChonBot, oChu, oGio, oSo, oVatKinh, t4TheoVat, tieuDeBuoc,
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
// Mục vệ sinh chuyển đổi (D129: 1e, B7c) — "Không có" là một câu trả lời thật.
const CD = [
  { v: 'Không có chuyển đổi', ten: 'Không có' },
  { v: 'Đạt', ten: '✓ Đạt' },
  { v: 'Không đạt', ten: '✕ Không' },
];

/** Giờ trên MÁY QC, dạng server đọc được. Cố tình lấy giờ máy chứ không phải
 *  giờ server: khi ghi ngoại tuyến rồi gửi sau, chỗ lệch giữa hai giờ đó chính
 *  là thứ auditor cần thấy. */
/** Mã máy thật (M1, M2…) nếu nhóm đó có, không thì số thứ tự — D129 (W02). */
function tenMay(nm, k) {
  return (nm && nm.ma && nm.ma[k - 1]) || String(k);
}

function gioMay() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} `
    + `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

// Ô ĐẾM: 0 là số thật. So theo mục GỐC — ô máy 2 của "hạt thô" cũng là ô đếm.
const DEM = ['thung_bot_qua_han', 't2_so_bay_dau_hieu', 'hat_tho'];

/** Bản sao client của muc.co_ghi() bên server. Chỉ để vẽ thanh tiến độ —
 *  server vẫn là chỗ quyết định. Lệch nhau thì thanh tiến độ sai, không phải
 *  dữ liệu sai. */
function daCham(m, v) {
  if (m.kieu === 'co_khong') return true;
  if (v === null || v === undefined || v === '') return false;
  if ((m.kieu === 'so' || m.kieu === 'nguyen') && !DEM.includes(m.goc || m.f)) {
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
  // Ca chỉ còn trên phiếu trước D95; phiếu mới một ngày ba lượt, không chia ca.
  const tenLuot = `${dl.luot}${dl.ca ? ` (ca ${dl.ca})` : ''} · `
    + `${dl.ngay.slice(8)}/${dl.ngay.slice(5, 7)}`;
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
  if (dl.ly_do_bo_sung) {
    container.appendChild(el('div', 'sx-qc-luot-phu', `Lượt bổ sung — <b>${esc(dl.ly_do_bo_sung)}</b> · `
      + 'không tính vào ba lượt trong ngày.'));
  }
  if (dl.truoc_do) {
    // W16 (D142): theo từng máy rang của lượt trước (M1 / M2 / M3).
    const t = dl.truoc_do;
    const may = (t.may && t.may.length) ? t.may
      : [{ may: '', nhiet: t.rang_nhiet_do, vong: t.rang_vong_quay }];
    container.appendChild(el('div', 'sx-qc-luot-phu',
      esc(`Lượt trước (${t.ngay} ${t.luot}): ${may.map((x) => `${x.may ? `${x.may} ` : ''}`
        + `${x.nhiet || '—'} °C · ${x.vong || '—'} v/ph`).join(' | ')}`)));
  }

  // ── tự lưu ──────────────────────────────────────────────────────────
  const cho = {};
  let hen = null;
  let dangGui = false;
  const nhanLuu = el('div', 'sx-qc-luu', 'chưa có thay đổi');

  async function gui() {
    if (dangGui || !Object.keys(cho).length) return null;
    const values = { ...cho };
    Object.keys(cho).forEach((k) => delete cho[k]);
    dangGui = true;
    let kq = null;
    try {
      kq = await call('sx.api.qc.save_round', {
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
    return kq;
  }

  // Đổi vị bột / số máy làm BỘ MỤC áp dụng đổi theo (D100) — ô lạc, ô máy 2/3
  // hiện ra hoặc ẩn đi. Server là chỗ tính bộ mục, nên gửi ngay rồi vẽ lại cả
  // lượt, không đoán ở máy QC. Mất mạng thì chưa vẽ lại được: nói ra.
  async function doiVaVeLai(f, v) {
    giaTri[f] = v;
    cho[f] = v;
    if (hen) clearTimeout(hen);
    while (dangGui) await new Promise((r) => { setTimeout(r, 100); });
    const kq = await gui();
    if (kq && kq._hang_cho) {
      toastErr('Mất mạng — đã lưu trên máy; các ô mới sẽ hiện khi có mạng.');
      return;
    }
    if (kq) render({ container, call, tham_so });
  }

  const laLac = (v) => String(v || '').split('\n')
    .some((c) => (hom.loai_bot || []).some((x) => x.item === c.trim() && x.lac));

  function onSet(f, v) {
    giaTri[f] = v;
    cho[f] = v;
    nhanLuu.className = 'sx-qc-luu sx-qc-luu-cho';
    nhanLuu.textContent = 'đang lưu…';
    veTienDo();
    if (hen) clearTimeout(hen);
    hen = setTimeout(gui, 300);
  }

  // T4 theo vật (W44, D173): mỗi vật một khóa "vat_kinh:<dòng BM.PRP.05>" trong hàng chờ — gửi lại / ngoại tuyến
  // không đè vật khác. Giá trị T4 trên máy chỉ để vẽ tiến độ; server tính lại từ các vật.
  const vatKinh = dl.vat_kinh && dl.vat_kinh.ds.length ? dl.vat_kinh : null;
  function onSetVat(x) {
    giaTri.t4_den_kinh = t4TheoVat(vatKinh.ds);
    onSet(`vat_kinh:${x.vat}`, { ket_qua: x.ket_qua || '', ghi_chu: x.ghi_chu || '' });
  }

  // ── có sản xuất bột — cho RIÊNG lượt này (D98) ──────────────────────
  // Trước D98 lượt đã mở thì không có cách nào thêm phần bột: dây chuyền bột
  // chạy từ 10h mà lượt Trưa mở lúc 9h là mất hẳn phần B của lượt đó.
  if (dl.docstatus === 0 && !khoa) {
    const hang = el('div', 'sx-qc-luot-dau sx-qc-bot-luot');
    hang.appendChild(el('span', 'sx-qc-luot-phu', dl.co_san_xuat_bot
      ? 'Lượt này CÓ phần bột (B)' : 'Lượt này KHÔNG có phần bột'));
    const nut = el('button', `sx-btn ${dl.co_san_xuat_bot ? 'sx-btn-ghost' : 'sx-btn-primary'}`,
      dl.co_san_xuat_bot ? 'TẮT BỘT' : 'BẬT BỘT');
    nut.type = 'button';
    nut.addEventListener('click', async () => {
      nut.disabled = true;
      // Gửi nốt số đang gõ TRƯỚC: đổi bột là tải lại cả lượt từ server, số chưa
      // gửi mà để trong ô thì mất theo màn hình cũ.
      if (hen) clearTimeout(hen);
      await gui();
      await batTatBot({
        call,
        method: 'sx.api.qc.doi_co_bot_luot',
        args: { name: dl.name, co_bot: dl.co_san_xuat_bot ? 0 : 1 },
        onXong: () => {
          toast(dl.co_san_xuat_bot ? 'Đã tắt phần bột' : 'Đã bật phần bột — thêm phần B');
          render({ container, call, tham_so });
        },
      });
      nut.disabled = false;
    });
    hang.appendChild(nut);
    container.appendChild(hang);
  }

  // ── công đoạn không chạy — cho RIÊNG lượt này (D107) ────────────────
  // Hôm không rang đỗ thì mục Rang không có gì để kiểm. Trước D107 QC phải để
  // trống rồi viết lý do mỗi lượt. Tắt ở đây: mục của bước đó không áp dụng,
  // không tính "phải chấm", không sinh sự cố; lượt sau trong ngày nhận lại.
  // Bấm tắt / bật được ghi vào nhật ký lượt (ai, lúc nào) và in trên tờ BM.08.01.
  const nghi = new Set(dl.buoc_nghi || []);
  const tatDuoc = (hom.buoc || []).filter((b) => (hom.buoc_tat_duoc || []).includes(b.ma));
  if (tatDuoc.length && (!khoa || nghi.size)) {
    const box = el('div', 'sx-qc-nghi');
    box.appendChild(el('div', 'sx-qc-luot-phu',
      nghi.size ? `Công đoạn KHÔNG chạy lượt này (${nghi.size}) — bấm để bật lại`
        : 'Công đoạn nào hôm nay không chạy? Bấm để bỏ khỏi lượt kiểm'));
    const chips = el('div', 'sx-qc-vi');
    tatDuoc.forEach((b) => {
      const tat = nghi.has(b.ma);
      const c = el('button', `sx-qc-vi-o${tat ? ' sx-qc-nghi-on' : ''}`,
        `${tat ? '⊘ ' : ''}${esc(b.ma)} ${esc(b.ten)}`);
      c.type = 'button';
      c.disabled = khoa;
      c.setAttribute('aria-pressed', tat ? 'true' : 'false');
      c.addEventListener('click', () => {
        const moi = new Set(nghi);
        if (tat) moi.delete(b.ma); else moi.add(b.ma);
        const giaTriMoi = tatDuoc.filter((x) => moi.has(x.ma)).map((x) => x.ma).join('\n');
        const daGhi = tat ? [] : muc.filter((m) => m.buoc === b.ma && daCham(m, giaTri[m.f]));
        if (!daGhi.length) { doiVaVeLai('buoc_nghi', giaTriMoi); return; }
        confirm2Step({
          title: `${b.ten} không chạy?`,
          message: `Đã ghi ${daGhi.length} mục của ${b.ten}. Tắt thì các mục đó ẩn khỏi `
            + 'lượt, khỏi tờ in và không sinh sự cố (giá trị vẫn giữ trong hồ sơ).',
          confirmLabel: 'KHÔNG CHẠY',
          onConfirm: () => doiVaVeLai('buoc_nghi', giaTriMoi),
        });
      });
      chips.appendChild(c);
    });
    box.appendChild(chips);
    container.appendChild(box);
  }

  // ── thân: từng bước, từng mục ───────────────────────────────────────
  const than = el('div');
  container.appendChild(than);
  const demBuoc = {};
  const soMay = dl.so_may || {};
  const onSetMuc = (f, v) => {
    // Chọn / bỏ một vị có lạc làm B1, B2, B7 hiện ra hay ẩn đi → vẽ lại.
    if (f === 'san_pham_bot' && laLac(v) !== laLac(giaTri[f])) {
      doiVaVeLai(f, v);
      return;
    }
    onSet(f, v);
  };
  hom.buoc.forEach((b) => {
    const cua = muc.filter((m) => m.buoc === b.ma);
    if (!cua.length) return;
    const tieu = tieuDeBuoc(b, 0, cua.filter((m) => !m.phu).length);
    demBuoc[b.ma] = { node: tieu.querySelector('.sx-qc-buoc-dem'), muc: cua };
    than.appendChild(tieu);
    cua.forEach((m, i) => {
      const truoc = cua[i - 1];
      const sau = cua[i + 1];
      if (m.may && !(truoc && truoc.may === m.may && truoc.may_so === m.may_so)) {
        than.appendChild(dauMay(m));
      }
      than.appendChild(m.f === 't4_den_kinh' && vatKinh ? oVatKinh(m, vatKinh, onSetVat, khoa)
        : veMuc(m, giaTri[m.f], onSetMuc, hom, khoa));
      if (m.may && !(sau && sau.may === m.may)) {
        const n = nutThemMay(m.may);
        if (n) than.appendChild(n);
      }
    });
  });

  // ── máy chạy song song (D100) ───────────────────────────────────────
  function dauMay(m) {
    const nm = (hom.nhom_may || {})[m.may] || { ten: 'Máy', toi_da: 1 };
    const h = el('div', 'sx-qc-may');
    h.appendChild(el('span', 'sx-qc-may-ten', `${esc(nm.ten)} ${esc(tenMay(nm, m.may_so))}`));
    const dang = soMay[m.may] || 1;
    if (!khoa && m.may_so > 1 && m.may_so === dang) {
      const bot = el('button', 'sx-btn sx-btn-ghost', 'Máy này nghỉ');
      bot.type = 'button';
      bot.addEventListener('click', () => {
        const oMay = muc.filter((x) => x.may === m.may && x.may_so === m.may_so);
        const daGhi = oMay.filter((x) => daCham(x, giaTri[x.f]));
        const bo = () => doiVaVeLai(nm.truong, dang - 1);
        if (!daGhi.length) { bo(); return; }
        confirm2Step({
          title: `${nm.ten} ${tenMay(nm, m.may_so)} nghỉ?`,
          message: `Đã ghi ${daGhi.length} ô của máy này. Các ô đó sẽ ẩn khỏi lượt, `
            + 'khỏi tờ in và không sinh sự cố (giá trị vẫn giữ trong hồ sơ).',
          confirmLabel: 'MÁY NÀY NGHỈ',
          onConfirm: bo,
        });
      });
      h.appendChild(bot);
    }
    return h;
  }

  function nutThemMay(nhom) {
    const nm = (hom.nhom_may || {})[nhom];
    const dang = soMay[nhom] || 1;
    if (khoa || !nm || dang >= nm.toi_da) return null;
    const b = el('button', 'sx-btn sx-btn-ghost sx-qc-may-them',
      `+ THÊM ${esc(nm.ten.toUpperCase())} ${esc(tenMay(nm, dang + 1))}`);
    b.type = 'button';
    b.title = `Có ${dang + 1} máy đang chạy — thêm ô ghi cho máy ${dang + 1}`;
    b.addEventListener('click', () => { b.disabled = true; doiVaVeLai(nm.truong, dang + 1); });
    return b;
  }

  // ── nhập lại từ bản giấy (W23, D147): giờ kiểm thật + ảnh tờ giấy ─────────
  if (dl.nhap_lai_tu_giay) {
    than.appendChild(el('div', 'sx-qc-buoc',
      '<span class="sx-qc-buoc-ten">Nhập lại từ bản giấy</span>'));
    const g = el('div', 'sx-qc-giay');
    g.appendChild(el('div', 'sx-qc-goiy', 'Giờ kiểm thực tế ghi trên tờ giấy (bắt buộc trước khi hoàn tất)'));
    const gio = el('input', 'sx-textarea');
    gio.type = 'time';
    gio.value = dl.gio_thuc_te || '';
    gio.disabled = khoa;
    gio.addEventListener('change', () => onSet('gio_thuc_te', gio.value ? `${gio.value}:00` : ''));
    g.appendChild(gio);
    const anh = el('div', 'sx-qc-goiy', dl.anh_giay ? '📷 Đã có ảnh bản giấy.' : 'Ảnh tờ giấy (tuỳ chọn).');
    g.appendChild(anh);
    if (!khoa || dl.docstatus === 1) {
      const chon = el('input');
      chon.type = 'file';
      chon.accept = 'image/*';
      chon.setAttribute('capture', 'environment');
      chon.style.display = 'none';
      const nut = el('button', 'sx-btn sx-btn-ghost', dl.anh_giay ? '📷 CHỤP LẠI ẢNH BẢN GIẤY' : '📷 CHỤP ẢNH BẢN GIẤY');
      nut.type = 'button';
      nut.addEventListener('click', () => chon.click());
      chon.addEventListener('change', async () => {
        const f = chon.files && chon.files[0];
        if (!f) return;
        nut.disabled = true;
        try {
          const n = await nenAnh(f);
          await call('sx.api.qc.them_anh_giay', { name: dl.name, anh: n.base64 });
          anh.textContent = `📷 Đã lưu ảnh bản giấy (${kb(n.sau)}).`;
          toast('Đã lưu ảnh bản giấy');
        } catch (e) { toastErr(e.message); } finally { nut.disabled = false; chon.value = ''; }
      });
      g.appendChild(chon);
      g.appendChild(nut);
    }
    than.appendChild(g);
  }

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

function veMuc(m, v, onSet, hom, khoa) {
  const ng = hom.nguong;
  if (m.kieu === 'chon_bot') return oChonBot(m, v, onSet, hom.loai_bot, khoa);
  if (m.kieu === 'so' || m.kieu === 'nguyen') return oSo(m, v, onSet, ng, khoa);
  if (m.kieu === 'chu') return oChu(m, v, onSet, khoa);
  if (m.kieu === 'gio') return oGio(m, v, onSet, khoa);
  if (m.kieu === 'co_khong') return oCheck(m, v, onSet, khoa);
  if (m.kieu === 'chon3') {
    return oChon3(m, v, onSet, B7, khoa);
  }
  if (m.kieu === 'chon_cd') return oChon3(m, v, onSet, CD, khoa);
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
