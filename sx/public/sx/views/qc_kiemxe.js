// #/qc/kiemxe — kiểm xe BM.09.01 (W34, D165).
//
// Thủ kho ghi kiểm xe ngay trên chứng từ của chuyến (hoá đơn bán trừ kho / phiếu nhập mua — Desk): biển số,
// đơn vị vận chuyển, năm mục, kết luận, xử lý, lái xe ký. QC kiểm NGẪU NHIÊN ít nhất 1 chuyến/tuần (QT.09
// mục 4): mở chuyến đang xếp / nhận hàng, đối chiếu năm mục tại xe → QC KIỂM (người + giờ), thấy khác thì ghi
// nhận xét. Xe nguyên liệu QC ghi luôn trên màn Tiếp nhận NL — tính là QC kiểm. Mỗi tuần thứ Hai – Chủ nhật
// một dòng: có chuyến mà chưa chuyến nào QC kiểm thì đỏ. Trưởng Ban ISO bấm "Đã xem tháng"; in BM.09.01.
// Luật ở sx/qc/kiem_xe.py + sx/api/qc_kiemxe.py; màn này chỉ đóng dấu và xem.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong } from '/assets/sx/sx/components/qcui.js';

// Tháng đang xem ('YYYY-MM', null = tháng này) — ngoài render: in xong quay lại không mất.
const st = { thang: null };

const DAT = 'Đạt';
const KHONG_DAT = 'Không đạt';
const ngayVN = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}` : '');
const ngayDu = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');
const thangVN = (t) => `${t.slice(5)}/${t.slice(0, 4)}`;
const dk = (v) => (v === DAT ? 'Đ' : (v === KHONG_DAT ? 'K' : '—'));

function congThang(t, n) {
  const [y, m] = t.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1 + n, 1)).toISOString().slice(0, 7);
}

/** Một tuần thứ Hai – Chủ nhật — hàm THUẦN để test: {kieu, chu}. Có chuyến mà chưa chuyến nào QC kiểm:
 *  tuần đang chạy là việc còn làm được (vàng), tuần đã hết là lỡ (đỏ). */
export function trangThaiTuan(t) {
  if (!t.so_chuyen) return { kieu: '', chu: 'không có chuyến' };
  if (t.so_qc) return { kieu: 'dong', chu: `QC kiểm ${t.so_qc}/${t.so_chuyen} chuyến` };
  if (t.qua) return { kieu: 'cao', chu: `${t.so_chuyen} chuyến — KHÔNG chuyến nào QC kiểm` };
  return { kieu: 'giu', chu: `${t.so_chuyen} chuyến — chưa chuyến nào QC kiểm` };
}

/** Bỏ được dấu QC kiểm không — như sx/api/qc_kiemxe.bo_qc_kiem: người đóng dấu trong ngày, hoặc Ban ISO;
 *  tháng đã xem thì giữ nguyên. */
export function boDuocQc(x, dl) {
  if (!x.qc_kiem || x.xem_luc) return false;
  return !!dl.la_iso || (x.qc_kiem === dl.user && x.qc_luc.slice(0, 10) === dl.hom_nay);
}

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc_kiemxe.tong_quan', st.thang ? { thang: st.thang } : {});
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
  top.appendChild(el('div', 'sx-dv-tuan-ten', `<div class="sx-qc-ngay">🚚 Kiểm xe</div>
    <div class="sx-qc-ai">BM.09.01 · tháng ${esc(thangVN(dl.thang))}${dl.thang === thangNay ? '' : ' · <b>tháng cũ</b>'}</div>`));
  top.appendChild(tien);
  container.appendChild(top);

  // ── các tuần ─────────────────────────────────────────────────────────
  const tuan = el('div', 'sx-qc-sc');
  tuan.appendChild(el('div', 'sx-qc-goiy', 'QC KIỂM NGẪU NHIÊN ÍT NHẤT 1 CHUYẾN/TUẦN (QT.09) · THỨ HAI – CHỦ NHẬT'));
  dl.tuan.forEach((t) => {
    const tt = trangThaiTuan(t);
    const h = el('div', 'sx-kx-tuan');
    h.appendChild(el('span', null, `${esc(ngayVN(t.tu))} – ${esc(ngayVN(t.den))}${t.nay ? ' · <b>tuần này</b>' : ''}`));
    h.appendChild(chip(tt.chu, tt.kieu));
    tuan.appendChild(h);
  });
  container.appendChild(tuan);

  // ── chuyến trong tháng ───────────────────────────────────────────────
  container.appendChild(el('div', 'sx-field-label sx-xx-khoi', `Chuyến trong tháng (${dl.ds.length})`));
  if (!dl.ds.length) {
    container.appendChild(khungTrong('Tháng này chưa có chuyến nào ghi kiểm xe. Thủ kho ghi trên hoá đơn bán trừ kho / '
      + 'phiếu nhập mua (mục "Kiểm tra phương tiện vận chuyển").'));
  }
  dl.ds.forEach((x) => container.appendChild(theChuyen(x, dl, api, lai)));

  veXem(container, dl, api, lai);
  const inB = el('button', 'sx-btn sx-btn-ghost', `🖨 IN BM.09.01 — tháng ${esc(thangVN(dl.thang))}`);
  inB.type = 'button';
  inB.addEventListener('click', () => inTo(api, { tu: dl.tu, den: dl.den }, `BM.09.01 — ${thangVN(dl.thang)}`));
  container.appendChild(inB);
}

function theChuyen(x, dl, api, lai) {
  const the = el('div', `sx-qc-sc sx-cat-dong${x.duoc_qc && dl.duoc_ghi ? ' sx-vu-cho' : ''}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', `${esc(ngayVN(x.ngay))} · ${esc(x.chieu)} · ${esc(x.doi_tac || x.name)}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(x.bien_so || 'chưa ghi biển số'));
  meta.appendChild(chip(`xe ${x.ket_luan}`, x.ket_luan === DAT ? 'dong' : 'cao'));
  if (x.nhap) meta.appendChild(chip('chưa duyệt', 'giu'));
  if (x.qc_kiem) meta.appendChild(chip(`QC kiểm · ${x.ten_qc} ${x.qc_luc.slice(11, 16)}`, 'dong'));
  if (x.ten_nguoi_kiem) meta.appendChild(el('span', null, `người kiểm ${esc(x.ten_nguoi_kiem)}`));
  the.appendChild(meta);
  const k = x.muc.filter((m) => m.gt === KHONG_DAT);
  if (k.length) the.appendChild(el('div', 'sx-vu-qua', `K: ${esc(k.map((m) => m.cot).join(', '))}${x.xu_ly ? ` — ${esc(x.xu_ly)}` : ''}`));
  const qc = x.duoc_qc && dl.duoc_ghi;
  const b = el('button', `sx-btn ${qc ? 'sx-btn-primary' : 'sx-btn-ghost'}`, qc ? 'QC KIỂM CHUYẾN NÀY' : 'XEM');
  b.type = 'button';
  b.addEventListener('click', () => moChuyen(x, dl, api, lai));
  const nut = el('div', 'sx-qc-lm-nut');
  nut.appendChild(b);
  the.appendChild(nut);
  return the;
}

export function moChuyen(x, dl, api, lai) {
  const m = openModal({ kicker: `BM.09.01 · ${x.name}`, title: `${x.bien_so || 'Chưa ghi biển số'} · ${x.doi_tac}` });
  const tt = [`${ngayDu(x.ngay)} · ${x.chieu}${x.nhap ? ' · chưa duyệt' : ''}`,
    `Đơn vị vận chuyển: ${x.don_vi || '—'} · Lái xe ký: ${x.tai_xe || '—'}`,
    `Người kiểm: ${x.ten_nguoi_kiem || '—'}`];
  m.body.appendChild(el('div', 'sx-modal-msg', tt.map(esc).join('<br>')
    + (x.hang.length ? `<br><b>Hàng:</b> ${x.hang.map(esc).join('; ')}` : '')));
  const bang = el('div', 'sx-kx-muc');
  x.muc.forEach((mu) => {
    const h = el('div', 'sx-kx-dong');
    h.appendChild(el('div', null, `<b>${esc(mu.cot)}</b>${mu.yc !== mu.cot ? `<br><span class="sx-qc-goiy">${esc(mu.yc)}</span>` : ''}`));
    h.appendChild(el('span', `sx-kx-dk${mu.gt === KHONG_DAT ? ' sx-kx-k' : ''}`, dk(mu.gt)));
    bang.appendChild(h);
  });
  const kl = el('div', 'sx-kx-dong');
  kl.appendChild(el('div', null, '<b>Kết luận (Đạt)</b>'));
  kl.appendChild(el('span', `sx-kx-dk${x.ket_luan === KHONG_DAT ? ' sx-kx-k' : ''}`, dk(x.ket_luan)));
  bang.appendChild(kl);
  m.body.appendChild(bang);
  if (x.xu_ly) m.body.appendChild(el('div', 'sx-qc-goiy', `Xử lý: ${esc(x.xu_ly)}`));
  if (x.pb !== 2) m.body.appendChild(el('div', 'sx-qc-goiy', 'Chuyến ghi theo bộ mục cũ (bốn mục, trước QT.09 lần BH 01).'));

  if (x.qc_kiem) {
    m.body.appendChild(el('div', 'sx-kx-qc', `<b>QC kiểm:</b> ${esc(x.ten_qc)} · ${esc(ngayDu(x.qc_luc.slice(0, 10)))} `
      + `${esc(x.qc_luc.slice(11, 16))}${x.qc_nhan_xet ? ` — ${esc(x.qc_nhan_xet)}` : ''}`));
    if (boDuocQc(x, dl)) {
      const bo = el('button', 'sx-btn sx-btn-ghost', 'BỎ DẤU QC KIỂM (đóng dấu nhầm chuyến)');
      bo.type = 'button';
      bo.addEventListener('click', () => {
        m.close();
        confirm2Step({
          title: `Bỏ dấu QC kiểm chuyến ${x.bien_so || x.name}?`,
          message: 'Chuyến này không còn tính là chuyến QC kiểm trong tuần.',
          confirmLabel: 'BỎ DẤU',
          onConfirm: async () => {
            await api.call('sx.api.qc_kiemxe.bo_qc_kiem', { doctype: x.doctype, name: x.name });
            toast('Đã bỏ dấu QC kiểm');
            lai();
          },
        });
      });
      m.body.appendChild(bo);
    }
    return;
  }
  if (!dl.duoc_ghi) return;
  if (!x.duoc_qc) {
    m.body.appendChild(el('div', 'sx-qc-goiy', `QC đóng dấu kiểm cho chuyến trong ${dl.so_ngay_qc} ngày kể từ ngày chuyến — `
      + 'kiểm xe là kiểm lúc xếp / nhận hàng.'));
    return;
  }
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Kiểm lại năm mục tại xe. Thấy khác người kiểm (vd sàn còn đinh mà ghi Đ): '
    + 'ghi nhận xét, báo thủ kho sửa trước khi duyệt / xếp hàng.'));
  const nx = el('textarea', 'sx-textarea');
  nx.rows = 2;
  nx.maxLength = 500;
  nx.placeholder = 'Nhận xét của QC (nếu có)';
  m.body.appendChild(nx);
  const b = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'QC ĐÃ KIỂM XE NÀY');
  b.type = 'button';
  b.addEventListener('click', async () => {
    b.disabled = true;
    try {
      await api.call('sx.api.qc_kiemxe.qc_kiem', { doctype: x.doctype, name: x.name, nhan_xet: nx.value });
      toast('Đã ghi QC kiểm');
      m.close();
      lai();
    } catch (e) { b.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(b);
}

// ── Trưởng Ban ISO xem tháng ─────────────────────────────────────────────
function veXem(box, dl, api, lai) {
  const k = el('div', 'sx-qc-sc');
  k.appendChild(el('div', 'sx-qc-goiy', 'TRƯỞNG BAN ISO XEM BM.09.01 HẰNG THÁNG'));
  if (dl.xem) {
    k.appendChild(el('div', null, `<b>${esc(dl.xem.ten || dl.xem.boi)}</b> · ${esc(ngayDu(dl.xem.luc.slice(0, 10)))}`));
    if (dl.chua_xem) k.appendChild(el('div', 'sx-qc-goiy', `${dl.chua_xem} chuyến duyệt sau lần xem — chưa xem.`));
  } else {
    k.appendChild(el('div', 'sx-qc-goiy', dl.ds.length ? 'Chưa xem.' : 'Tháng chưa có chuyến nào.'));
  }
  if (dl.duoc_xem_thang && dl.chua_xem) {
    const b = el('button', 'sx-btn sx-btn-primary', `ĐÃ XEM THÁNG ${esc(thangVN(dl.thang))}`);
    b.type = 'button';
    b.addEventListener('click', () => confirm2Step({
      title: `Đã xem kiểm xe tháng ${thangVN(dl.thang)}`,
      message: `Ký xem ${dl.chua_xem} chuyến đã duyệt${dl.so_nhap ? ` — ${dl.so_nhap} chuyến chưa duyệt sẽ chờ lần xem sau` : ''}. `
        + 'Đơn vị vận chuyển vi phạm lặp lại: xử lý theo QT.09.',
      confirmLabel: 'ĐÃ XEM',
      onConfirm: async () => {
        await api.call('sx.api.qc_kiemxe.xem_thang', { thang: dl.thang });
        toast('Đã ghi xem xét tháng');
        lai();
      },
    }));
    k.appendChild(b);
  }
  box.appendChild(k);
}

async function inTo(api, args, ten) {
  try {
    const html = await api.call('sx.api.qc_kiemxe.in_so_kiem_xe', args);
    const w = window.open('', '_blank');
    if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
      + `<title>${esc(ten)}</title></head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 250);
  } catch (e) { toastErr(e.message); }
}
