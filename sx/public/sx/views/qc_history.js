// #/qc/history — lịch sử lượt theo tuần + nút in tờ ngày BM.08.01.
//
// Dải tuần thay cho danh sách: cái QC và Ban ISO cần thấy là LỖ HỔNG — ngày nào
// thiếu lượt, ngày nào ghi muộn. Danh sách dọc thì phải đếm bằng mắt mới ra,
// còn hàng pill thì chỗ trống tự nó lộ.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toastErr } from '/assets/sx/sx/components/toast.js';
import { khungTrong } from '/assets/sx/sx/components/qcui.js';

const THU = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'];
const st = { lech: 0 };   // số tuần lùi so với tuần này

function dauTuan(lech) {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  const thu = (d.getDay() + 6) % 7;          // thứ Hai = 0
  d.setDate(d.getDate() - thu - lech * 7);
  return d;
}

function iso(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const d0 = dauTuan(st.lech);
  const d6 = new Date(d0);
  d6.setDate(d6.getDate() + 6);
  const ds = await call('sx.api.qc.list_rounds', { tu: iso(d0), den: iso(d6) });
  container.innerHTML = '';

  const dieu = el('div', 'sx-qc-top');
  const lui = el('button', 'sx-btn sx-btn-ghost', '◀');
  const toi = el('button', 'sx-btn sx-btn-ghost', '▶');
  lui.type = 'button';
  toi.type = 'button';
  lui.addEventListener('click', () => { st.lech += 1; render(api); });
  toi.addEventListener('click', () => {
    if (st.lech > 0) { st.lech -= 1; render(api); }
  });
  toi.disabled = st.lech === 0;
  dieu.appendChild(lui);
  dieu.appendChild(el('div', 'sx-qc-ngay',
    esc(`${iso(d0).slice(8)}/${iso(d0).slice(5, 7)} – ${iso(d6).slice(8)}/${iso(d6).slice(5, 7)}`)));
  dieu.appendChild(toi);
  container.appendChild(dieu);

  const tuan = el('div', 'sx-qc-tuan');
  container.appendChild(tuan);

  let coGi = false;
  for (let i = 0; i < 7; i += 1) {
    const d = new Date(d0);
    d.setDate(d.getDate() + i);
    const ngay = iso(d);
    const cua = ds.filter((r) => String(r.ngay) === ngay);
    if (cua.length) coGi = true;
    const hang = el('div', 'sx-qc-ngayhang');
    hang.appendChild(el('div', 'sx-qc-ngayhang-ten',
      esc(`${THU[d.getDay()]} ${ngay.slice(8)}/${ngay.slice(5, 7)}`)));
    const pills = el('div', 'sx-qc-chips');
    ['Sáng', 'Chiều'].forEach((ca) => {
      ['Đầu ca', 'Giữa ca', 'Cuối ca'].forEach((luot) => {
        const r = cua.find((x) => x.ca === ca
          && (x.luot === luot || (luot === 'Đầu ca' && x.luot === 'Tuần')));
        let cls = '';
        if (r && r.docstatus === 1) cls = r.ghi_muon ? ' sx-qc-pill-muon' : ' sx-qc-pill-xong';
        else if (r) cls = ' sx-qc-pill-nhap';
        const p = el('span', `sx-qc-pill${cls}`,
          esc(`${ca[0]}${luot === 'Đầu ca' ? 'Đ' : (luot === 'Giữa ca' ? 'G' : 'C')}`));
        p.title = r
          ? `${r.luot} ${ca} — ${r.docstatus === 1 ? 'xong' : 'đang làm'}`
            + `${r.ghi_muon ? ' (ghi muộn)' : ''}`
          : `${luot} ${ca} — chưa có`;
        pills.appendChild(p);
      });
    });
    hang.appendChild(pills);
    if (cua.length) {
      const inNut = el('button', 'sx-btn sx-btn-ghost', '🖨');
      inNut.type = 'button';
      inNut.title = 'In tờ ngày BM.08.01';
      inNut.addEventListener('click', () => inToNgay(ngay, call));
      hang.appendChild(inNut);
    }
    tuan.appendChild(hang);
  }

  if (!coGi) container.appendChild(khungTrong('Tuần này chưa có lượt kiểm nào.'));
  container.appendChild(el('div', 'sx-qc-goiy',
    'Ô vàng = ghi muộn · ô xanh = xong đúng khung giờ · ô xám = chưa có lượt. '
    + 'Chữ SĐ = ca Sáng đầu ca, CG = ca Chiều giữa ca…'));
}

/** Mở tờ A4 ở cửa sổ mới rồi gọi in. Server trả HTML đã dựng sẵn (day_sheet). */
async function inToNgay(ngay, call) {
  try {
    const html = await call('sx.api.qc.day_sheet', { ngay });
    const w = window.open('', '_blank');
    if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
    // BẮT BUỘC có <meta charset>: cửa sổ mở bằng about:blank không thừa kế bảng
    // mã của trang cha, trình duyệt tự đoán, và nó đoán sai — tờ giấy in ra đầy
    // "Nhiá»‡t Ä'á»™". Với auditor thì đó là tờ giấy vứt đi.
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
      + `<title>BM.08.01 — ${ngay}</title></head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 250);
  } catch (e) {
    toastErr(e.message);
  }
}
