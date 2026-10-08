// #/qc/khieunai — sổ khiếu nại khách hàng BM.11.01 (W13, D135), ghi trên Issue.
//
// Người khiếu nại chỉ cầm hộp, trên hộp chỉ có HSD — nên form hỏi SẢN PHẨM + HSD, app
// tự tìm lô (W05: mỗi sản phẩm + HSD một lô). Có lô thì mẫu lưu của lô được giữ khi
// khiếu nại còn mở, và thẻ lô trong Truy xuất liệt kê khiếu nại.
//
// Phân loại nguy hiểm (dị vật, vi sinh, dị ứng) hoặc mức Cao → lập luôn phiếu sự cố
// điều tra (BM.08.02). Đóng khiếu nại: Ban ISO / người được giao, phải có kết luận +
// xử lý với khách — chốt ở sx/qc/khieu_nai.py (cả Desk), nút ẩn chỉ cho đỡ rối mắt.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { chip, khungTrong, segment, tabSuCo } from '/assets/sx/sx/components/qcui.js';

const st = { tab: 'Mở' };

const ngayVN = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc_khieunai.list_khieu_nai', { trang_thai: st.tab });
  container.innerHTML = '';
  container.appendChild(tabSuCo('khieunai'));

  const them = el('button', 'sx-btn sx-btn-primary sx-btn-big', '+ GHI KHIẾU NẠI');
  them.type = 'button';
  them.addEventListener('click', () => moThem(dl, api));
  container.appendChild(them);

  container.appendChild(segment(
    [{ v: 'Mở', ten: `Đang mở (${dl.so_mo})` }, { v: 'Đóng', ten: 'Đã đóng (30 ngày)' }],
    st.tab, (v) => { st.tab = v; render(api); }));

  const ds = el('div', 'sx-qc-than');
  container.appendChild(ds);
  if (!dl.danh_sach.length) {
    ds.appendChild(khungTrong(st.tab === 'Mở' ? 'Không có khiếu nại nào đang mở.'
      : 'Chưa có khiếu nại nào được đóng trong 30 ngày qua.'));
  }
  dl.danh_sach.forEach((k) => ds.appendChild(veThe(k, dl, api)));

  const inSo = el('button', 'sx-btn sx-btn-ghost', '🖨 IN SỔ BM.11.01 (tháng này)');
  inSo.type = 'button';
  inSo.addEventListener('click', () => inSoThang(api));
  container.appendChild(inSo);
}

function veThe(k, dl, api) {
  const the = el('div', `sx-qc-sc sx-qc-sc-${k.mo ? 'mo' : 'dong'}`);
  the.appendChild(el('div', 'sx-qc-sc-ten', esc(k.mo_ta || k.tieu_de)));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(k.name));
  meta.appendChild(el('span', null, esc(ngayVN(k.ngay))));
  if (k.khach || k.lien_he) meta.appendChild(chip(`👤 ${k.khach || k.lien_he}`));
  if (k.ten_sp) meta.appendChild(chip(k.ten_sp));
  if (k.nhan_lo) meta.appendChild(chip(k.nhan_lo));
  else if (k.san_pham) meta.appendChild(chip('chưa rõ lô', 'han'));
  if (k.phan_loai) meta.appendChild(chip(k.phan_loai));
  if (k.muc_do === 'Cao') meta.appendChild(chip('mức CAO', 'cao'));
  if (k.qua_han) meta.appendChild(chip('quá hạn', 'han'));
  the.appendChild(meta);
  if (k.su_co) the.appendChild(el('div', 'sx-qc-goiy', `Phiếu sự cố điều tra: <b>${esc(k.su_co)}</b>`));
  if (k.ket_luan || k.xu_ly) {
    the.appendChild(el('div', 'sx-qc-goiy',
      `${k.ket_luan ? `Kết luận: ${esc(k.ket_luan)}. ` : ''}${k.xu_ly ? `Xử lý: ${esc(k.xu_ly)}` : ''}`));
  } else if (k.mo) {
    the.appendChild(el('div', 'sx-qc-goiy', '⚠ chưa có kết luận / xử lý với khách'));
  }
  if (!k.mo) {
    the.appendChild(el('div', 'sx-qc-goiy', `Đóng ${esc(ngayVN(k.dong_luc.slice(0, 10)))} · ${esc(k.dong_boi)}`));
  }
  const nut = el('div', 'sx-qc-chips');
  const b = el('button', 'sx-btn sx-btn-ghost', k.mo ? 'GHI XỬ LÝ' : 'XEM');
  b.type = 'button';
  b.addEventListener('click', () => moChiTiet(k, dl, api));
  nut.appendChild(b);
  the.appendChild(nut);
  return the;
}

function o(body, nhan, gt, kieu) {
  body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
  const n = el(kieu === 'ta' ? 'textarea' : 'input');
  n.className = 'sx-textarea';
  if (kieu === 'ta') n.rows = 2;
  else if (kieu) n.type = kieu;
  n.value = gt || '';
  body.appendChild(n);
  return n;
}

function chonBox(body, nhan, lua, gt) {
  body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
  const s = el('select', 'sx-textarea');
  ['', ...lua].forEach((x) => {
    const opt = el('option', null, esc(x || '—'));
    opt.value = x;
    if (x === gt) opt.selected = true;
    s.appendChild(opt);
  });
  body.appendChild(s);
  return s;
}

/** Ô tìm có danh sách kết quả bấm chọn. `tim(q)` trả [{v, ten}]. */
function oTim(body, nhan, placeholder, tim, onChon) {
  body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
  const da = el('div', 'sx-qc-lm-chon');
  const inp = el('input', 'sx-textarea');
  inp.type = 'search';
  inp.placeholder = placeholder;
  const kq = el('div', 'sx-qc-vi');
  let hen = null;
  inp.addEventListener('input', () => {
    clearTimeout(hen);
    hen = setTimeout(async () => {
      kq.innerHTML = '';
      if (inp.value.trim().length < 2) return;
      try {
        const r = await tim(inp.value.trim());
        if (!r.length) kq.appendChild(el('div', 'sx-muted', 'Không thấy.'));
        r.forEach((x) => {
          const b = el('button', 'sx-qc-vi-o', esc(x.ten));
          b.type = 'button';
          b.addEventListener('click', () => {
            da.innerHTML = `✓ <b>${esc(x.ten)}</b>`;
            kq.innerHTML = '';
            inp.value = '';
            onChon(x);
          });
          kq.appendChild(b);
        });
      } catch (e) { toastErr(e.message); }
    }, 300);
  });
  body.appendChild(da);
  body.appendChild(inp);
  body.appendChild(kq);
  return { da };
}

function moThem(dl, api) {
  const m = openModal({ kicker: 'SỔ KHIẾU NẠI BM.11.01', title: 'Ghi khiếu nại khách hàng' });
  const f = { khach: '', khach_ten: '', san_pham: '', hsd: '' };
  oTim(m.body, 'Khách hàng (trong danh mục)', 'gõ 2 chữ tên khách / đại lý…',
    async (q) => (await api.call('sx.api.qc_khieunai.tim_khach', { q }))
      .map((x) => ({ v: x.customer, ten: x.ten })),
    (x) => { f.khach = x.v; f.khach_ten = x.ten; });
  const lh = o(m.body, 'Người khiếu nại / liên hệ (tên, số điện thoại)', '');
  const kenh = chonBox(m.body, 'Kênh tiếp nhận', dl.kenh, 'Điện thoại');

  oTim(m.body, 'Sản phẩm', 'gõ 2 chữ tên sản phẩm…',
    async (q) => (await api.call('sx.api.qc.tim_hang', { q })).map((x) => ({ v: x.item, ten: x.ten })),
    (x) => { f.san_pham = x.v; taiLo(); });
  // HSD: bấm chọn HSD của các lô đang có, hoặc gõ ngày in trên hộp.
  m.body.appendChild(el('div', 'sx-qc-goiy', 'HSD in trên hộp'));
  const loBox = el('div', 'sx-qc-vi');
  const hsd = el('input', 'sx-textarea');
  hsd.type = 'date';
  const nhanLo = el('div', 'sx-qc-goiy');
  let dsLo = [];
  const veLo = () => {
    loBox.innerHTML = '';
    dsLo.slice(0, 8).forEach((b) => {
      const c = el('button', `sx-qc-vi-o${f.hsd === b.hsd ? ' sx-qc-vi-on' : ''}`, esc(b.nhan));
      c.type = 'button';
      c.addEventListener('click', () => { f.hsd = b.hsd; hsd.value = b.hsd; veLo(); });
      loBox.appendChild(c);
    });
    const co = dsLo.find((b) => b.hsd && b.hsd === f.hsd);
    nhanLo.textContent = !f.san_pham ? 'Chọn sản phẩm trước.'
      : (!f.hsd ? 'Bấm HSD bên trên hoặc gõ ngày.'
        : (co ? `✓ Tìm thấy lô HSD ${ngayVN(f.hsd)}.`
          : '⚠ Không có lô nào của sản phẩm này với HSD đó — kiểm lại ngày trên hộp (vẫn ghi được).'));
  };
  async function taiLo() {
    try { dsLo = (await api.call('sx.api.qc.tim_lo', { san_pham: f.san_pham })).filter((b) => b.hsd); } catch (e) {
      toastErr(e.message);
    }
    veLo();
  }
  hsd.addEventListener('change', () => { f.hsd = hsd.value; veLo(); });
  m.body.appendChild(loBox);
  m.body.appendChild(hsd);
  m.body.appendChild(nhanLo);
  veLo();
  const sl = o(m.body, 'Số lượng khiếu nại (VD: 2 hộp)', '');
  const pl = chonBox(m.body, 'Phân loại', dl.phan_loai, '');
  const md = chonBox(m.body, 'Mức độ', ['Thường', 'Cao'], 'Thường');
  const mo = o(m.body, 'Nội dung khiếu nại (bắt buộc)', '', 'ta');
  const nhanSc = el('label', 'sx-sc-check');
  const sc = el('input');
  sc.type = 'checkbox';
  nhanSc.appendChild(sc);
  nhanSc.appendChild(el('span', null, 'Lập phiếu sự cố để điều tra (BM.08.02)'));
  m.body.appendChild(nhanSc);
  // Dị vật / vi sinh / dị ứng hoặc mức Cao: server lập phiếu sự cố bắt buộc — ô tích
  // khoá ở trạng thái bật để màn hình nói đúng điều sẽ xảy ra.
  const capNhatSc = () => {
    if (dl.nguy_hiem.includes(pl.value)) md.value = 'Cao';   // server cũng nâng lên Cao
    const buoc = md.value === 'Cao' || dl.nguy_hiem.includes(pl.value);
    if (buoc) sc.checked = true;
    sc.disabled = buoc;
  };
  pl.addEventListener('change', capNhatSc);
  md.addEventListener('change', capNhatSc);

  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'GHI VÀO SỔ');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!mo.value.trim()) { toastErr('Chưa ghi nội dung khiếu nại.'); return; }
    if (!f.khach && !lh.value.trim()) { toastErr('Chưa ghi khách hàng / người khiếu nại.'); return; }
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc_khieunai.them_khieu_nai', {
        payload: JSON.stringify({
          khach: f.khach, khach_ten: f.khach_ten, lien_he: lh.value.trim(), kenh: kenh.value,
          san_pham: f.san_pham, hsd: f.hsd, so_luong: sl.value.trim(), phan_loai: pl.value,
          muc_do: md.value, mo_ta: mo.value, lap_su_co: sc.checked ? 1 : 0,
        }),
      });
      toast(`Đã ghi ${r.name}${r.su_co ? ` · phiếu sự cố ${r.su_co}` : ''}${
        f.san_pham && !r.lo ? ' · CHƯA khớp được lô' : ''}`);
      m.close();
      st.tab = 'Mở';
      render(api);
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

function moChiTiet(k, dl, api) {
  const m = openModal({ kicker: k.name, title: k.ten_sp ? `${k.ten_sp}${k.nhan_lo ? ` · ${k.nhan_lo}` : ''}` : 'Khiếu nại' });
  m.body.appendChild(el('div', 'sx-modal-msg',
    `${esc(k.khach || k.lien_he)}${k.kenh ? ` · ${esc(k.kenh)}` : ''} · nhận ${esc(ngayVN(k.ngay))}`
    + `${k.so_luong ? ` · ${esc(k.so_luong)}` : ''}<br>${esc(k.mo_ta)}`));
  const sua = k.mo || dl.duoc_dong;
  const pl = chonBox(m.body, 'Phân loại', dl.phan_loai, k.phan_loai);
  const md = chonBox(m.body, 'Mức độ', ['Thường', 'Cao'], k.muc_do);
  const kl = chonBox(m.body, 'Kết luận (bắt buộc trước khi đóng)', dl.ket_luan, k.ket_luan);
  const xl = o(m.body, 'Xử lý với khách — đổi, trả, bồi hoàn… (bắt buộc trước khi đóng)', k.xu_ly, 'ta');
  [pl, md, kl, xl].forEach((x) => { x.disabled = !sua; });
  const goi = () => ({ phan_loai: pl.value, muc_do: md.value, ket_luan: kl.value, xu_ly: xl.value });
  const lam = async (b, fn, xong) => {
    b.disabled = true;
    try { await fn(); toast(xong); m.close(); render(api); } catch (e) { b.disabled = false; toastErr(e.message); }
  };
  if (sua) {
    const luu = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU');
    luu.type = 'button';
    luu.addEventListener('click', () => lam(luu, () => api.call('sx.api.qc_khieunai.sua_khieu_nai',
      { name: k.name, payload: JSON.stringify(goi()) }), 'Đã lưu'));
    m.body.appendChild(luu);
  }
  if (k.mo && !k.su_co) {
    const sc = el('button', 'sx-btn sx-btn-ghost sx-btn-big', 'LẬP PHIẾU SỰ CỐ ĐIỀU TRA');
    sc.type = 'button';
    sc.addEventListener('click', () => lam(sc, () => api.call('sx.api.qc_khieunai.lap_su_co_khieu_nai',
      { name: k.name }), 'Đã lập phiếu sự cố'));
    m.body.appendChild(sc);
  }
  if (k.mo && dl.duoc_dong) {
    const dong = el('button', 'sx-btn sx-btn-warn sx-btn-big', 'ĐÓNG KHIẾU NẠI');
    dong.type = 'button';
    dong.addEventListener('click', () => lam(dong, async () => {
      // Lưu trước rồi mới đóng: server chặn đóng khi thiếu kết luận / xử lý — đóng thẳng
      // là báo thiếu đúng cái người ta vừa gõ.
      await api.call('sx.api.qc_khieunai.sua_khieu_nai', { name: k.name, payload: JSON.stringify(goi()) });
      await api.call('sx.api.qc_khieunai.dong_khieu_nai', { name: k.name });
    }, 'Đã đóng khiếu nại'));
    m.body.appendChild(dong);
  } else if (k.mo) {
    m.body.appendChild(el('div', 'sx-qc-goiy',
      'Đóng khiếu nại là việc của Trưởng Ban ISO / người được giao — người tiếp nhận không tự đóng.'));
  }
  if (!k.mo && dl.duoc_dong) {
    const ly = o(m.body, 'Lý do mở lại', '');
    const mo = el('button', 'sx-btn sx-btn-ghost sx-btn-big', 'MỞ LẠI');
    mo.type = 'button';
    mo.addEventListener('click', () => {
      if (!ly.value.trim()) { toastErr('Ghi lý do mở lại.'); return; }
      lam(mo, () => api.call('sx.api.qc_khieunai.mo_lai_khieu_nai', { name: k.name, ly_do: ly.value.trim() }),
        'Đã mở lại');
    });
    m.body.appendChild(mo);
  }
}

// Cửa sổ mới, tự khai charset (about:blank không thừa kế) — cùng cách in tờ BM.08.01.
async function inSoThang(api) {
  const nay = new Date();
  const tu = `${nay.getFullYear()}-${String(nay.getMonth() + 1).padStart(2, '0')}-01`;
  try {
    const html = await api.call('sx.api.qc_khieunai.in_so_khieu_nai', { tu });
    const w = window.open('', '_blank');
    if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
      + `<title>Sổ khiếu nại BM.11.01</title></head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 250);
  } catch (e) { toastErr(e.message); }
}
