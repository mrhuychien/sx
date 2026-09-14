// #/qc — Hôm nay: ba thẻ lượt, bật/tắt "có sản xuất bột", đếm sự cố mở.
//
// Màn này trả lời đúng một câu hỏi mà QC hỏi khi rút điện thoại ra giữa xưởng:
// "giờ tôi phải đi lượt nào?". Nên lượt kế tiếp là thẻ có nút đậm, hai thẻ kia
// nhạt; lượt đã xong hiện giờ hoàn tất chứ không hiện dấu tích chung chung —
// giờ hoàn tất là thứ auditor hỏi, dấu tích thì không nói gì.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';
import { chip, segment, veNhac } from '/assets/sx/sx/components/qcui.js';
import { formatTime } from '/assets/sx/sx/lib/format.js';

const THU = ['Chủ nhật', 'Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy'];

function tenNgay(iso) {
  const [y, m, d] = String(iso).split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  return `${THU[dt.getUTCDay()]} ${d}/${m}/${y}`;
}

export async function render({ container, call, st }) {
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const [dl, nh] = await Promise.all([
    call('sx.api.qc.get_today', st.ngay ? { ngay: st.ngay } : {}),
    call('sx.api.qc.nhac', st.ngay ? { ngay: st.ngay } : {}).catch(() => null),
  ]);
  st.ngay = dl.ngay;
  if (!st.ca) st.ca = dl.ca[0];
  container.innerHTML = '';

  // ── đầu màn: ngày + người + ca ──────────────────────────────────────
  const top = el('div', 'sx-qc-top');
  const la_hom_nay = dl.ngay === dl.hom_nay;
  top.innerHTML = `<div style="flex:1;min-width:0">
      <div class="sx-qc-ngay">${esc(tenNgay(dl.ngay))}</div>
      <div class="sx-qc-ai">${esc(dl.user)}${la_hom_nay ? ''
        : ' · <b>đang xem ngày cũ</b>'}</div>
    </div>`;
  const doiNgay = el('button', 'sx-btn sx-btn-ghost', '📅');
  doiNgay.type = 'button';
  doiNgay.title = 'Chọn ngày khác (nhập lại từ bản giấy)';
  const inpNgay = el('input');
  inpNgay.type = 'date';
  inpNgay.value = dl.ngay;
  inpNgay.max = dl.hom_nay;
  inpNgay.style.cssText = 'position:absolute;opacity:0;width:1px;height:1px';
  inpNgay.addEventListener('change', () => {
    if (!inpNgay.value) return;
    st.ngay = inpNgay.value;
    render({ container, call, st });
  });
  doiNgay.addEventListener('click', () => {
    if (inpNgay.showPicker) inpNgay.showPicker(); else inpNgay.focus();
  });
  top.appendChild(inpNgay);
  top.appendChild(doiNgay);
  container.appendChild(top);
  // Hộp nhắc đứng NGAY DƯỚI ngày, trên cả ba thẻ lượt: việc đang treo phải
  // đập vào mắt trước khi người ta bấm "Bắt đầu lượt" rồi quên mất nó.
  const hopNhac = veNhac((nh && nh.ds) || []);
  if (hopNhac) container.appendChild(hopNhac);
  container.appendChild(segment(dl.ca, st.ca, (v) => {
    st.ca = v;
    render({ container, call, st });
  }));

  // ── ba thẻ lượt ─────────────────────────────────────────────────────
  const ds = dl.theo_ca[st.ca] || [];
  const ke_tiep = ds.find((x) => !x.round || x.round.docstatus === 0);
  ds.forEach((x) => container.appendChild(
    veThe(x, x === ke_tiep, dl, st, call, container)));

  // ── có sản xuất bột ─────────────────────────────────────────────────
  const bot = el('div', 'sx-qc-luot');
  bot.style.padding = 'var(--sx-s3) var(--sx-s4)';
  const hang = el('div', 'sx-qc-luot-dau');
  hang.appendChild(el('span', 'sx-qc-luot-ten', 'Hôm nay có sản xuất bột'));
  const nutBot = el('button', 'sx-btn', dl.co_san_xuat_bot ? 'CÓ' : 'KHÔNG');
  nutBot.type = 'button';
  nutBot.className = `sx-btn ${dl.co_san_xuat_bot ? 'sx-btn-primary' : 'sx-btn-ghost'}`;
  nutBot.disabled = !dl.duoc_ghi;
  // Bật ở đây chỉ đổi MẶC ĐỊNH cho lượt mở sau. Lượt đang dở thì bật trong
  // chính màn lượt đó — đổi ma trận của một lượt đang ghi từ ngoài vào là làm
  // biến mất mấy ô người ta vừa gõ.
  nutBot.addEventListener('click', () => {
    st.co_bot = dl.co_san_xuat_bot ? 0 : 1;
    dl.co_san_xuat_bot = st.co_bot;
    nutBot.textContent = st.co_bot ? 'CÓ' : 'KHÔNG';
    nutBot.className = `sx-btn ${st.co_bot ? 'sx-btn-primary' : 'sx-btn-ghost'}`;
  });
  hang.appendChild(nutBot);
  bot.appendChild(hang);
  bot.appendChild(el('div', 'sx-qc-luot-phu',
    'Bật thì lượt mở sau có thêm phần B (dây chuyền bột).'));
  container.appendChild(bot);

  // KHÔNG có chip "Sự cố mở / Quá hạn" ở đây nữa: hộp nhắc đầu màn đã nói
  // cùng một chuyện, nói kỹ hơn, và bấm vào cũng sang đúng màn đó. Hai khối
  // cùng một nội dung trên một màn thì người đọc phải dừng lại kiểm xem chúng
  // có khác nhau không — mà chúng thì không.

  // Nhập lại từ bản giấy = mở một ngày cũ. Viết hẳn ra thành câu, vì cái nút 📅
  // trên đầu màn không tự nói được nó dùng để làm việc đó.
  const giay = el('button', 'sx-btn sx-btn-ghost', 'Nhập lại từ bản giấy (chọn ngày cũ)');
  giay.type = 'button';
  giay.style.cssText = 'width:100%;color:var(--sx-text-2)';
  giay.addEventListener('click', () => {
    if (inpNgay.showPicker) inpNgay.showPicker(); else inpNgay.focus();
  });
  container.appendChild(giay);
}

function veThe(x, la_ke_tiep, dl, st, call, container) {
  const r = x.round;
  const the = el('div', `sx-qc-luot${r && r.docstatus === 1 ? ' sx-qc-luot-xong' : ''}`);
  const dau = el('div', 'sx-qc-luot-dau');
  const ten = x.luot === 'Tuần' && x.o === 'Đầu ca' ? 'Đầu ca · Tuần' : x.o;
  dau.appendChild(el('div', 'sx-qc-luot-ten', esc(ten)));
  if (r && r.docstatus === 1) {
    dau.appendChild(el('div', 'sx-qc-luot-gio', `xong ${esc(formatTime(r.finished_at))}`));
  } else {
    const k = ((dl.khung || {})[st.ca] || {})[x.o];
    if (k) {
      // Nói trước khung giờ, đừng để QC biết mình muộn sau khi đã bị gắn cờ.
      dau.appendChild(el('div', 'sx-qc-luot-gio', esc(
        k[0] ? `${k[0].slice(0, 5)}–${k[1].slice(0, 5)}` : `trước ${k[1].slice(0, 5)}`)));
    }
  }
  the.appendChild(dau);

  const phu = [];
  phu.push(`${x.so_muc} mục`);
  if (x.luot === 'Tuần') phu.push('có thêm phần C (lượt tuần)');
  if (r && r.docstatus === 0) phu.push(`đang làm ${r.so_muc_da_cham}/${r.so_muc_ap_dung}`);
  the.appendChild(el('div', 'sx-qc-luot-phu', esc(phu.join(' · '))));

  if (r && (r.ghi_muon || r.nhap_lai_tu_giay)) {
    const c = el('div', 'sx-qc-chips');
    if (r.ghi_muon) c.appendChild(chip('ghi muộn', 'oprp'));
    if (r.nhap_lai_tu_giay) c.appendChild(chip('nhập lại từ giấy'));
    the.appendChild(c);
  }

  const nut = el('button', 'sx-btn sx-btn-big', '');
  nut.type = 'button';
  if (r && r.docstatus === 1) {
    nut.className = 'sx-btn sx-btn-ghost sx-btn-big';
    nut.textContent = 'XEM LẠI';
    nut.addEventListener('click', () => { window.location.hash = `#/qc/round/${r.name}`; });
  } else if (r) {
    nut.className = `sx-btn ${la_ke_tiep ? 'sx-btn-primary' : 'sx-btn-ghost'} sx-btn-big`;
    nut.textContent = 'LÀM TIẾP';
    nut.addEventListener('click', () => { window.location.hash = `#/qc/round/${r.name}`; });
  } else {
    nut.className = `sx-btn ${la_ke_tiep ? 'sx-btn-primary' : 'sx-btn-ghost'} sx-btn-big`;
    nut.textContent = 'BẮT ĐẦU LƯỢT';
    nut.disabled = !dl.duoc_ghi;
    nut.addEventListener('click', async () => {
      nut.disabled = true;
      try {
        const kq = await call('sx.api.qc.start_round', {
          ngay: dl.ngay, ca: st.ca, luot: x.luot,
          co_san_xuat_bot: st.co_bot ?? dl.co_san_xuat_bot,
          // Ngày quá khứ = nhập lại từ bản giấy. Không bắt QC tự tick: họ mở
          // ngày cũ ra là đã nói rõ mình đang làm gì rồi.
          nhap_lai_tu_giay: dl.ngay === dl.hom_nay ? 0 : 1,
        });
        window.location.hash = `#/qc/round/${kq.name}`;
      } catch (e) {
        nut.disabled = false;
        toastErr(e.message);
      }
    });
  }
  the.appendChild(nut);

  if (!dl.duoc_ghi && !r) {
    the.appendChild(el('div', 'sx-qc-luot-phu',
      'Bạn chỉ có quyền xem — lượt do QC chế biến / QC đóng gói ghi.'));
  }
  return the;
}
