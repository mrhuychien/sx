// #/qc/luumau — tủ lưu mẫu (D100, W07/D133).
//
// Tủ mẫu có giá trị đúng một lúc: khi khách khiếu nại lô X, mẫu lô X phải còn
// đó và tìm ra ngay. Nên màn này làm ba việc, theo thứ tự hay cần:
//   1. Mẫu ĐẾN HẠN HUỶ đứng đầu, viền đỏ — không ai phải nhớ đi dọn tủ.
//   2. Tìm theo tên / lô / vị trí — khiếu nại tới là gõ lô vào là thấy.
//   3. Lấy mẫu mới: sản phẩm + vị trí hay dùng hiện sẵn thành nút bấm, chọn LÔ
//      theo HSD in trên hộp → hạn lưu tự tính NSX + 12 tháng (W07).
//
// Huỷ (W07): QC KHÔNG huỷ lẻ — bấm ĐỀ XUẤT HUỶ gom mọi mẫu đến hạn thành một đợt
// tháng, Trưởng Ban ISO xác nhận thì mẫu mới thành "Đã huỷ" và in biên bản. Mẫu
// đang bị GIỮ (lô có sự cố / khiếu nại mở, hoặc bấm Giữ lại) không vào đợt huỷ.
// Lấy ra: bắt buộc lý do — mẫu biến mất mà không ai ghi vì sao thì tủ mẫu chỉ
// còn là cái tủ.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';
import { chip, khungTrong, segment, tabLo } from '/assets/sx/sx/components/qcui.js';
import { kb, nenAnh } from '/assets/sx/sx/lib/anh.js';

const ANH_TOI_DA = 4;   // một lần chụp — khớp ANH_MOT_LAN ở sx/api/qc.py

/** Ô chọn ảnh ẩn. `chup` = mở thẳng camera sau (điện thoại); không thì cho chọn
 *  ảnh có sẵn. Trả về Promise<File[]> khi người dùng chọn xong. */
function chonAnh(chup) {
  return new Promise((ok) => {
    const inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = 'image/*';
    if (chup) inp.setAttribute('capture', 'environment');
    else inp.multiple = true;
    inp.addEventListener('change', () => ok([...(inp.files || [])]));
    inp.click();
  });
}

/** Khối "Ảnh mẫu": chụp / chọn → NÉN NGAY trên máy → xem trước, bỏ được.
 *  Trả {node, anh: () => [base64]}; `dangNen()` true khi còn ảnh chưa nén xong. */
function khoiAnh() {
  const ds = [];          // {url, base64, truoc, sau}
  let dangNen = 0;
  const node = el('div', 'sx-lm-anh');
  const luoi = el('div', 'sx-lm-anh-luoi');
  const nhan = el('div', 'sx-muted');
  const hang = el('div', 'sx-lm-anh-nut');
  const ve = () => {
    luoi.innerHTML = '';
    ds.forEach((a, i) => {
      const o = el('div', 'sx-lm-anh-o');
      o.innerHTML = `<img src="${a.url}" alt="Ảnh mẫu ${i + 1}">
        <span>${esc(kb(a.sau))}</span>`;
      const bo = el('button', 'sx-lm-anh-bo', '✕');
      bo.type = 'button';
      bo.setAttribute('aria-label', `Bỏ ảnh ${i + 1}`);
      bo.addEventListener('click', () => { URL.revokeObjectURL(a.url); ds.splice(i, 1); ve(); });
      o.appendChild(bo);
      luoi.appendChild(o);
    });
    const truoc = ds.reduce((t, a) => t + a.truoc, 0);
    const sau = ds.reduce((t, a) => t + a.sau, 0);
    nhan.textContent = dangNen ? `Đang nén ${dangNen} ảnh…`
      : (ds.length ? `${ds.length} ảnh · ${kb(truoc)} → ${kb(sau)} sau khi nén` : 'Chưa có ảnh (không bắt buộc).');
    hang.querySelectorAll('button').forEach((b) => { b.disabled = ds.length + dangNen >= ANH_TOI_DA; });
  };
  const them = async (chup) => {
    const files = (await chonAnh(chup)).slice(0, ANH_TOI_DA - ds.length - dangNen);
    dangNen += files.length;
    ve();
    for (const f of files) {
      try {
        const n = await nenAnh(f);
        ds.push({ url: URL.createObjectURL(n.blob), base64: n.base64, truoc: n.truoc, sau: n.sau });
      } catch (e) { toastErr(`Không đọc được ảnh ${f.name}: ${e.message}`); }
      dangNen -= 1;
      ve();
    }
  };
  [['📷 CHỤP ẢNH', true], ['🖼 Ảnh có sẵn', false]].forEach(([t, chup]) => {
    const b = el('button', `sx-btn${chup ? ' sx-btn-primary' : ''}`, t);
    b.type = 'button';
    b.addEventListener('click', () => them(chup));
    hang.appendChild(b);
  });
  node.appendChild(hang);
  node.appendChild(luoi);
  node.appendChild(nhan);
  ve();
  return { node, anh: () => ds.map((a) => a.base64), dangNen: () => dangNen > 0 };
}

async function guiAnh(api, name, anh) {
  if (!anh.length) return null;
  return api.call('sx.api.qc.them_anh_luu_mau', { name, anh: JSON.stringify(anh) });
}

async function xemAnh(x, api) {
  let ds;
  try { ds = await api.call('sx.api.qc.anh_luu_mau', { name: x.name }); } catch (e) {
    toastErr(e.message); return;
  }
  const m = openModal({ kicker: 'Ảnh mẫu', title: `${x.ten_san_pham}${x.lo ? ` · ${x.lo}` : ''}` });
  if (!ds.length) { m.body.appendChild(el('div', 'sx-muted', 'Mẫu này chưa có ảnh.')); return; }
  ds.forEach((a) => {
    const img = el('img', 'sx-lm-anh-lon');
    img.src = a.url;
    img.loading = 'lazy';
    img.alt = 'Ảnh mẫu';
    m.body.appendChild(img);
  });
}

const st = { tab: 'Đang lưu', q: '' };

const ngayVN = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}/${s.slice(0, 4)}` : '');

export async function render(api) {
  const { container, call } = api;
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc.list_luu_mau', { trang_thai: st.tab, q: st.q || null });
  container.innerHTML = '';
  container.appendChild(tabLo('luumau'));

  if (dl.duoc_ghi) {
    const lay = el('button', 'sx-btn sx-btn-primary sx-btn-big', '+ LẤY MẪU');
    lay.type = 'button';
    lay.addEventListener('click', () => moLayMau(dl, api));
    container.appendChild(lay);
  }

  // Đợt huỷ chờ Ban ISO đứng trên cùng: chừng nào chưa xác nhận thì mẫu còn nằm
  // trong tủ ở trạng thái Chờ huỷ, và QC chưa đề xuất được đợt mới.
  (dl.dot_cho || []).forEach((d) => container.appendChild(veDot(d, dl, api)));
  if (dl.duoc_ghi && dl.so_den_han && !(dl.dot_cho || []).length) {
    const dx = el('button', 'sx-btn sx-btn-warn sx-btn-big sx-lm-dexuat',
      `ĐỀ XUẤT HUỶ ${dl.so_den_han} MẪU ĐẾN HẠN`);
    dx.type = 'button';
    dx.addEventListener('click', () => confirm2Step({
      title: 'Đề xuất đợt huỷ mẫu',
      message: `Gom ${dl.so_den_han} mẫu đã hết hạn lưu (mẫu đang GIỮ không tính) thành một đợt `
        + 'huỷ tháng. Mẫu chuyển "Chờ huỷ" và vẫn nằm trong tủ cho tới khi Trưởng Ban ISO xác nhận.',
      confirmLabel: 'ĐỀ XUẤT HUỶ',
      onConfirm: async () => {
        try {
          const r = await api.call('sx.api.qc.de_xuat_huy', {});
          toast(`Đã đề xuất đợt ${r.name} · ${r.so_mau} mẫu — chờ Ban ISO`);
          st.tab = 'Chờ huỷ';
          render(api);
        } catch (e) { toastErr(e.message); throw e; }
      },
    }));
    container.appendChild(dx);
  }

  const seg = segment(
    [{ v: 'Đang lưu', ten: `Đang lưu${dl.so_den_han ? `\n${dl.so_den_han} đến hạn` : ''}` },
      { v: 'Chờ huỷ', ten: 'Chờ huỷ' },
      { v: 'Đã lấy ra', ten: 'Đã lấy ra' }, { v: 'Đã huỷ', ten: 'Đã huỷ' }],
    st.tab, (v) => { st.tab = v; render(api); });
  seg.classList.add('sx-lm-seg');      // 4 tab: số đến hạn xuống dòng riêng, không gãy 3 dòng
  container.appendChild(seg);

  const tim = el('input', 'sx-textarea sx-qc-lm-tim');
  tim.type = 'search';
  tim.placeholder = 'Tìm sản phẩm, lô / HSD, vị trí…';
  tim.value = st.q;
  let hen = null;
  tim.addEventListener('input', () => {
    clearTimeout(hen);
    hen = setTimeout(() => { st.q = tim.value.trim(); render(api); }, 400);
  });
  container.appendChild(tim);

  const ds = el('div', 'sx-qc-than');
  container.appendChild(ds);
  if (!dl.danh_sach.length) {
    ds.appendChild(khungTrong(st.q ? 'Không có mẫu nào khớp.'
      : ({ 'Đang lưu': 'Tủ mẫu đang trống.', 'Chờ huỷ': 'Không có mẫu nào chờ huỷ.' }[st.tab]
        || 'Chưa có mẫu nào.')));
  }
  dl.danh_sach.forEach((x) => ds.appendChild(veThe(x, dl, api)));

  // W36 (D167): Sổ lưu mẫu SLM theo tháng — mẫu lấy trong tháng + mẫu huỷ / lấy ra trong tháng.
  const inHang = el('div', 'sx-xx-ngay sx-lm-in');
  const th = el('input', 'sx-textarea');
  th.type = 'month';
  th.value = dl.thang || '';
  th.max = dl.thang || '';
  const inB = el('button', 'sx-btn sx-btn-ghost', '🖨 IN SỔ LƯU MẪU (SLM)');
  inB.type = 'button';
  inB.addEventListener('click', () => inSo(th.value || dl.thang, api));
  inHang.appendChild(th);
  inHang.appendChild(inB);
  container.appendChild(inHang);
  if (st.q) setTimeout(() => { tim.focus(); tim.setSelectionRange(tim.value.length, tim.value.length); }, 0);
}

/** Thẻ một đợt huỷ chờ xác nhận. Ban ISO: XÁC NHẬN / TRẢ LẠI; ai cũng in được
 *  biên bản (bản nháp trước khi ký, bản chính sau khi xác nhận). */
function veDot(d, dl, api) {
  const the = el('div', 'sx-qc-sc sx-qc-sc-cho sx-lm-dot');
  the.appendChild(el('div', 'sx-qc-sc-ten',
    `Đợt huỷ ${esc(d.name)} · tháng ${esc(d.thang || '')} · ${d.so_mau} mẫu`));
  the.appendChild(el('div', 'sx-qc-goiy',
    `${esc(d.lap_boi || '')} đề xuất ${esc(ngayVN(String(d.lap_luc || '').slice(0, 10)))} — `
    + 'chờ Trưởng Ban ISO xác nhận. Mẫu vẫn trong tủ (tab Chờ huỷ).'));
  const nut = el('div', 'sx-qc-lm-nut');
  const inBb = el('button', 'sx-btn sx-btn-ghost', '🖨 BIÊN BẢN');
  inBb.type = 'button';
  inBb.addEventListener('click', () => inBienBan(d.name, api));
  nut.appendChild(inBb);
  if (dl.duoc_huy) {
    const tra = el('button', 'sx-btn sx-btn-ghost', 'TRẢ LẠI');
    tra.type = 'button';
    tra.addEventListener('click', () => moTraLai(d, api));
    nut.appendChild(tra);
    const ok = el('button', 'sx-btn sx-btn-primary', 'XÁC NHẬN ĐÃ HUỶ');
    ok.type = 'button';
    ok.addEventListener('click', () => confirm2Step({
      title: `Xác nhận đợt huỷ ${d.name}`,
      message: `${d.so_mau} mẫu đã huỷ thật (đã bỏ khỏi tủ). Mẫu nào vừa bị GIỮ (lô có sự cố / `
        + 'khiếu nại, bấm Giữ lại) sau lúc đề xuất sẽ tự trả về Đang lưu.',
      confirmLabel: 'XÁC NHẬN ĐÃ HUỶ',
      onConfirm: async () => {
        try {
          const r = await api.call('sx.api.qc.xac_nhan_huy', { dot: d.name, dong_y: 1 });
          toast(`Đã huỷ ${r.da_huy} mẫu${r.giu_lai ? ` · ${r.giu_lai} mẫu đang giữ, trả về tủ` : ''}`);
          st.tab = 'Đã huỷ';
          render(api);
        } catch (e) { toastErr(e.message); throw e; }
      },
    }));
    nut.appendChild(ok);
  }
  the.appendChild(nut);
  return the;
}

function moTraLai(d, api) {
  const m = openModal({ kicker: 'Trả lại đợt huỷ', title: `${d.name} · ${d.so_mau} mẫu` });
  m.body.appendChild(el('div', 'sx-modal-msg',
    'Mọi mẫu trong đợt về lại Đang lưu. Ghi lý do để QC biết sửa gì trước khi đề xuất lại.'));
  const ta = el('textarea', 'sx-textarea');
  ta.rows = 3;
  ta.placeholder = 'Lý do (bắt buộc)';
  m.body.appendChild(ta);
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'TRẢ LẠI');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!ta.value.trim()) { toastErr('Phải ghi lý do.'); return; }
    ok.disabled = true;
    try {
      await api.call('sx.api.qc.xac_nhan_huy', { dot: d.name, dong_y: 0, ly_do: ta.value.trim() });
      toast('Đã trả lại đợt huỷ');
      m.close();
      st.tab = 'Đang lưu';
      render(api);
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

// W36 (D167): in Sổ lưu mẫu SLM (lần BH 02) theo tháng — tháng chọn ở ô tháng cạnh nút.
async function inSo(thang, api) {
  try {
    const html = await api.call('sx.api.qc.in_so_luu_mau', { thang });
    const w = window.open('', '_blank');
    if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
      + `<title>SLM — ${esc(thang)}</title></head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 250);
  } catch (e) { toastErr(e.message); }
}

// Cửa sổ mới, tự khai charset (about:blank không thừa kế) — cùng cách in tờ BM.08.01.
async function inBienBan(dot, api) {
  try {
    const html = await api.call('sx.api.qc.in_bien_ban_huy', { dot });
    const w = window.open('', '_blank');
    if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
      + `<title>Biên bản huỷ mẫu — ${esc(dot)}</title></head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 250);
  } catch (e) { toastErr(e.message); }
}

function veThe(x, dl, api) {
  const lop = { 'Đang lưu': x.den_han && !x.giu ? 'mo' : 'luu', 'Chờ huỷ': 'cho' }[x.trang_thai] || 'dong';
  const the = el('div', `sx-qc-sc sx-qc-sc-${lop}`);
  const dau = el('div', 'sx-lm-dau');
  if (x.anh) {
    const tb = el('button', 'sx-lm-tb');
    tb.type = 'button';
    tb.setAttribute('aria-label', 'Xem ảnh mẫu');
    tb.innerHTML = `<img src="${esc(x.anh)}" alt="" loading="lazy">`;
    tb.addEventListener('click', () => xemAnh(x, api));
    dau.appendChild(tb);
  }
  const lo = x.lo || (x.hsd ? `HSD ${ngayVN(x.hsd)}` : '');
  dau.appendChild(el('div', 'sx-qc-sc-ten',
    `${esc(x.ten_san_pham || x.san_pham)}${lo ? ` · <span class="sx-qc-lm-lo">${esc(lo)}</span>` : ''}`));
  the.appendChild(dau);
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(chip(`${x.so_luong} ${x.dvt || ''}`.trim()));
  if (x.vi_tri) meta.appendChild(chip(`📍 ${x.vi_tri}`));
  meta.appendChild(el('span', null, `${x.nsx ? `NSX ${esc(ngayVN(x.nsx))} · ` : ''}`
    + `lấy ${esc(ngayVN(x.ngay_lay))} · lưu đến ${esc(ngayVN(x.han_luu))}`));
  if (x.giu) meta.appendChild(chip('🔒 đang giữ', 'giu'));
  else if (x.den_han) meta.appendChild(chip('đến hạn huỷ', 'han'));
  else if (x.trang_thai === 'Đang lưu' && x.con_ngay <= 14) meta.appendChild(chip(`còn ${x.con_ngay} ngày`));
  the.appendChild(meta);
  if (x.giu) the.appendChild(el('div', 'sx-qc-goiy sx-lm-giu', esc(x.giu)));
  if (x.trang_thai === 'Chờ huỷ') {
    the.appendChild(el('div', 'sx-qc-goiy',
      `Trong đợt huỷ ${esc(x.dot_huy || '')} — chờ Ban ISO xác nhận.${x.giu ? ' Mẫu đang giữ sẽ trả về tủ.' : ''}`));
  } else if (x.trang_thai !== 'Đang lưu') {
    the.appendChild(el('div', 'sx-qc-goiy',
      `${esc(x.trang_thai)} ${esc(ngayVN((x.xu_ly_luc || '').slice(0, 10)))}`
      + `${x.ly_do ? ` — ${esc(x.ly_do)}` : ''}`));
  }
  if (!['Đang lưu', 'Chờ huỷ'].includes(x.trang_thai)) return the;

  const nut = el('div', 'sx-qc-lm-nut');
  if (x.trang_thai === 'Đang lưu' && dl.duoc_ghi) {
    const them = el('button', 'sx-btn sx-btn-ghost', '📷 + ẢNH');
    them.type = 'button';
    them.title = 'Chụp thêm ảnh cho mẫu này';
    them.addEventListener('click', async () => {
      const files = (await chonAnh(true)).slice(0, ANH_TOI_DA);
      if (!files.length) return;
      them.disabled = true;
      them.textContent = 'đang nén…';
      try {
        const anh = [];
        for (const f of files) anh.push((await nenAnh(f)).base64);
        await guiAnh(api, x.name, anh);
        toast('Đã thêm ảnh');
        render(api);
      } catch (e) {
        toastErr(e.message);
        them.disabled = false;
        them.textContent = '📷 + ẢNH';
      }
    });
    nut.appendChild(them);
  }
  // Giữ lại: QC và Ban ISO đều bấm được. Mẫu giữ vì lô có sự cố thì không có nút
  // bỏ giữ — đóng phiếu sự cố là tự thôi giữ.
  if (dl.duoc_ghi || dl.duoc_huy) {
    if (x.giu_lai) {
      const bo = el('button', 'sx-btn sx-btn-ghost', 'BỎ GIỮ');
      bo.type = 'button';
      bo.addEventListener('click', () => confirm2Step({
        title: `Bỏ giữ mẫu ${x.ten_san_pham}`,
        message: 'Mẫu hết hạn lưu sẽ được đưa vào đợt huỷ tháng tới.',
        confirmLabel: 'BỎ GIỮ',
        onConfirm: async () => {
          try {
            await api.call('sx.api.qc.giu_mau', { name: x.name, giu: 0 });
            toast('Đã bỏ giữ');
            render(api);
          } catch (e) { toastErr(e.message); throw e; }
        },
      }));
      nut.appendChild(bo);
    } else if (!x.giu) {
      const giu = el('button', 'sx-btn sx-btn-ghost', '🔒 GIỮ LẠI');
      giu.type = 'button';
      giu.title = 'Không huỷ mẫu này: khiếu nại / điều tra chưa xong';
      giu.addEventListener('click', () => moGiu(x, api));
      nut.appendChild(giu);
    }
  }
  if (dl.duoc_ghi) {
    const ra = el('button', 'sx-btn sx-btn-ghost', 'LẤY RA');
    ra.type = 'button';
    ra.title = 'Mang mẫu đi dùng: khiếu nại, gửi kiểm nghiệm…';
    ra.addEventListener('click', () => moLyDo(x, 'lay_ra', api));
    nut.appendChild(ra);
  }
  // Huỷ lẻ một mẫu: chỉ Ban ISO (mẫu hỏng, mốc…). QC đi đường đợt huỷ tháng.
  if (x.trang_thai === 'Đang lưu' && dl.duoc_huy && !x.giu) {
    const huy = el('button', `sx-btn ${x.den_han ? 'sx-btn-primary' : 'sx-btn-ghost'}`, 'HUỶ MẪU');
    huy.type = 'button';
    huy.addEventListener('click', () => (x.den_han
      ? confirm2Step({
        title: `Huỷ mẫu ${x.ten_san_pham}`,
        message: `${lo || 'Không ghi lô'} — đã hết hạn lưu ${ngayVN(x.han_luu)}.`,
        confirmLabel: 'ĐÃ HUỶ MẪU',
        onConfirm: async () => {
          try {
            await api.call('sx.api.qc.xu_ly_luu_mau', { name: x.name, hanh_dong: 'huy' });
            toast('Đã ghi huỷ mẫu');
            render(api);
          } catch (e) { toastErr(e.message); throw e; }
        },
      })
      : moLyDo(x, 'huy', api)));
    nut.appendChild(huy);
  }
  if (nut.children.length) the.appendChild(nut);
  return the;
}

function moGiu(x, api) {
  const m = openModal({ kicker: 'Giữ lại mẫu', title: `${x.ten_san_pham}${x.lo ? ` · ${x.lo}` : ''}` });
  m.body.appendChild(el('div', 'sx-modal-msg',
    'Mẫu giữ lại không vào đợt huỷ dù hết hạn lưu. Ghi rõ vì sao: khiếu nại của ai, điều tra gì…'
    + ' (Lô đã có phiếu sự cố đang mở thì app tự giữ, không cần bấm.)'));
  const ta = el('textarea', 'sx-textarea');
  ta.rows = 3;
  ta.placeholder = 'Lý do giữ (bắt buộc)';
  m.body.appendChild(ta);
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'GIỮ LẠI');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!ta.value.trim()) { toastErr('Phải ghi lý do.'); return; }
    ok.disabled = true;
    try {
      await api.call('sx.api.qc.giu_mau', { name: x.name, giu: 1, ly_do: ta.value.trim() });
      toast('Đã giữ lại mẫu');
      m.close();
      render(api);
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

function moLyDo(x, hanhDong, api) {
  const laHuy = hanhDong === 'huy';
  const m = openModal({
    kicker: laHuy ? 'Huỷ mẫu TRƯỚC hạn' : 'Lấy mẫu ra',
    title: `${x.ten_san_pham}${x.lo ? ` · ${x.lo}` : ''}`,
  });
  m.body.appendChild(el('div', 'sx-modal-msg', laHuy
    ? `Mẫu còn hạn lưu tới ${ngayVN(x.han_luu)}. Huỷ sớm thì phải ghi lý do.`
    : 'Ghi rõ dùng vào việc gì: khiếu nại của ai, gửi kiểm nghiệm ở đâu…'));
  const ta = el('textarea', 'sx-textarea');
  ta.rows = 3;
  ta.placeholder = 'Lý do (bắt buộc)';
  m.body.appendChild(ta);
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', laHuy ? 'HUỶ MẪU' : 'LẤY RA');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!ta.value.trim()) { toastErr('Phải ghi lý do.'); return; }
    ok.disabled = true;
    try {
      await api.call('sx.api.qc.xu_ly_luu_mau',
        { name: x.name, hanh_dong: hanhDong, ly_do: ta.value.trim() });
      toast(laHuy ? 'Đã ghi huỷ mẫu' : 'Đã ghi lấy mẫu ra');
      m.close();
      render(api);
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

function moLayMau(dl, api) {
  const m = openModal({ kicker: 'Lưu mẫu', title: 'Lấy mẫu mới' });
  const han = el('input', 'sx-textarea');
  han.type = 'date';
  han.value = dl.han_mac_dinh;
  // han_luu chỉ gửi khi người dùng TỰ sửa ngày — còn lại server tính NSX của lô + số
  // tháng ở Setting (W07), máy QC không tự quyết hạn lưu.
  const f = { san_pham: '', ten: '', dvt: 'hộp', lo: '', batch: '', so_luong: 1, vi_tri: '', han_luu: '' };

  // ── sản phẩm: nút gợi ý + ô tìm ─────────────────────────────────────
  m.body.appendChild(el('div', 'sx-field-label', 'Sản phẩm'));
  const daChon = el('div', 'sx-qc-lm-chon');
  const goiY = el('div', 'sx-qc-vi');
  const tim = el('input', 'sx-textarea');
  tim.type = 'search';
  tim.placeholder = 'gõ 2 chữ để tìm…';
  const kq = el('div', 'sx-qc-vi');
  const chonSp = (x) => {
    const doi = f.san_pham !== x.item;
    f.san_pham = x.item; f.ten = x.ten;
    if (x.dvt) { f.dvt = x.dvt; dvt.value = x.dvt; veSl(); }
    veChon();
    if (doi) taiLo();
  };
  const nutSp = (x) => {
    const b = el('button', `sx-qc-vi-o${f.san_pham === x.item ? ' sx-qc-vi-on' : ''}`, esc(x.ten));
    b.type = 'button';
    b.addEventListener('click', () => chonSp(x));
    return b;
  };
  function veChon() {
    daChon.innerHTML = f.san_pham ? `✓ <b>${esc(f.ten)}</b>` : '';
    goiY.innerHTML = '';
    dl.goi_y_sp.forEach((x) => goiY.appendChild(nutSp(x)));
    kq.querySelectorAll('button').forEach((b) => {
      b.classList.toggle('sx-qc-vi-on', b.dataset.item === f.san_pham);
    });
  }
  let hen = null;
  tim.addEventListener('input', () => {
    clearTimeout(hen);
    hen = setTimeout(async () => {
      kq.innerHTML = '';
      if (tim.value.trim().length < 2) return;
      try {
        const ds = await api.call('sx.api.qc.tim_hang', { q: tim.value.trim() });
        if (!ds.length) kq.appendChild(el('div', 'sx-muted', 'Không thấy sản phẩm nào.'));
        ds.forEach((x) => { const b = nutSp(x); b.dataset.item = x.item; kq.appendChild(b); });
      } catch (e) { toastErr(e.message); }
    }, 300);
  });
  m.body.appendChild(daChon);
  m.body.appendChild(goiY);
  m.body.appendChild(tim);
  m.body.appendChild(kq);

  // ── lô (W07): chọn theo HSD in trên hộp — mã lô ẩn như mọi chỗ khác (W05) ──
  m.body.appendChild(el('div', 'sx-field-label', 'Lô — chọn theo HSD in trên hộp'));
  const loBox = el('div', 'sx-qc-vi sx-lm-lo-chon');
  const loGoiY = el('div', 'sx-qc-goiy');
  const lo = el('input', 'sx-textarea');
  lo.type = 'text';
  lo.placeholder = 'Lô không có trong danh sách: ghi HSD / số lô như in trên bao bì';
  lo.addEventListener('input', () => {
    // Gõ tay = lô ngoài hệ thống → bỏ lô đã chọn, hạn lưu tính từ ngày lấy.
    f.lo = lo.value;
    if (f.batch) { f.batch = ''; veLo(); datHan(dl.han_mac_dinh); }
  });
  let dsLo = [];
  function datHan(v) {
    if (f.han_luu) return;              // người dùng đã tự sửa ngày → không đè
    han.value = v || dl.han_mac_dinh;
  }
  function veLo() {
    loBox.innerHTML = '';
    dsLo.forEach((b) => {
      const o = el('button', `sx-qc-vi-o${f.batch === b.batch ? ' sx-qc-vi-on' : ''}`,
        `HSD ${esc(ngayVN(b.hsd))}${b.nsx ? `<small> · NSX ${esc(ngayVN(b.nsx))}</small>` : ''}`);
      o.type = 'button';
      o.addEventListener('click', () => {
        f.batch = f.batch === b.batch ? '' : b.batch;
        f.lo = f.batch ? `HSD ${ngayVN(b.hsd)}` : '';
        lo.value = f.lo;
        datHan(f.batch ? b.han_luu : dl.han_mac_dinh);
        veLo();
      });
      loBox.appendChild(o);
    });
    loGoiY.textContent = !f.san_pham ? 'Chọn sản phẩm trước.'
      : (dsLo.length ? (f.batch ? 'Hạn lưu = NSX của lô + '
        + `${dl.so_thang_luu} tháng.` : 'Bấm chọn lô của mẫu.')
        : 'Sản phẩm này chưa có lô nào có HSD trong hệ thống — ghi tay bên dưới.');
  }
  async function taiLo() {
    f.batch = ''; dsLo = []; veLo();
    datHan(dl.han_mac_dinh);
    try {
      dsLo = await api.call('sx.api.qc.lo_cua_sp', { san_pham: f.san_pham });
    } catch (e) { toastErr(e.message); }
    veLo();
  }
  m.body.appendChild(loBox);
  m.body.appendChild(loGoiY);
  m.body.appendChild(lo);

  const hang = el('div', 'sx-qc-lm-hang');
  const sl = el('button', 'sx-qc-oso-khung', '');
  sl.type = 'button';
  // Kèm đơn vị: ô số chỉ có mỗi con số bị CSS chung coi là ô trống (tô xám).
  const veSl = () => {
    sl.innerHTML = `<span class="sx-qc-oso-val">${f.so_luong}</span>`
      + `<span class="sx-qc-oso-dv">${esc(f.dvt || '')}</span>`;
  };
  veSl();
  sl.addEventListener('click', () => openNumpad({
    kicker: 'Lưu mẫu', title: 'Số lượng mẫu', initial: String(f.so_luong),
    allowDecimal: false, unitLabel: f.dvt || 'SỐ',
    onOk: (n) => { f.so_luong = Math.max(1, Math.round(n)); veSl(); },
  }));
  const dvt = el('input', 'sx-textarea');
  dvt.type = 'text';
  dvt.value = f.dvt;
  dvt.addEventListener('input', () => { f.dvt = dvt.value; veSl(); });
  const o1 = el('div'); o1.appendChild(el('div', 'sx-field-label', 'Số lượng')); o1.appendChild(sl);
  const o2 = el('div'); o2.appendChild(el('div', 'sx-field-label', 'Đơn vị')); o2.appendChild(dvt);
  hang.appendChild(o1); hang.appendChild(o2);
  m.body.appendChild(hang);

  m.body.appendChild(el('div', 'sx-field-label', 'Vị trí lưu'));
  const vt = el('input', 'sx-textarea');
  vt.type = 'text';
  vt.placeholder = 'tủ / kệ / ngăn';
  vt.addEventListener('input', () => { f.vi_tri = vt.value; veVt(); });
  const vtGoiY = el('div', 'sx-qc-vi');
  function veVt() {
    vtGoiY.innerHTML = '';
    dl.goi_y_vi_tri.forEach((v) => {
      const b = el('button', `sx-qc-vi-o${f.vi_tri === v ? ' sx-qc-vi-on' : ''}`, esc(v));
      b.type = 'button';
      b.addEventListener('click', () => { f.vi_tri = v; vt.value = v; veVt(); });
      vtGoiY.appendChild(b);
    });
  }
  veVt();
  m.body.appendChild(vtGoiY);
  m.body.appendChild(vt);

  m.body.appendChild(el('div', 'sx-field-label',
    `Lưu đến ngày (mặc định NSX + ${dl.so_thang_luu} tháng; không chọn lô thì tính từ hôm nay)`));
  han.addEventListener('change', () => { f.han_luu = han.value; });
  m.body.appendChild(han);

  m.body.appendChild(el('div', 'sx-field-label', 'Ảnh mẫu'));
  const kAnh = khoiAnh();
  m.body.appendChild(kAnh.node);

  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'LƯU MẪU');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!f.san_pham) { toastErr('Chưa chọn sản phẩm.'); return; }
    if (kAnh.dangNen()) { toastErr('Đợi nén ảnh xong đã.'); return; }
    ok.disabled = true;
    let r;
    try {
      r = await api.call('sx.api.qc.tao_luu_mau', { payload: JSON.stringify(f) });
    } catch (e) { ok.disabled = false; toastErr(e.message); return; }
    // Mẫu đã lưu rồi mới gửi ảnh: ảnh hỏng không được làm mất cả lần lấy mẫu.
    try {
      const a = await guiAnh(api, r.name, kAnh.anh());
      toast(`Đã lưu mẫu ${r.name}${a ? ` · ${a.anh.length} ảnh` : ''}`);
    } catch (e) {
      toastErr(`Đã lưu mẫu ${r.name} nhưng CHƯA gửi được ảnh: ${e.message} — bấm "📷 + ẢNH" trên mẫu để gửi lại.`);
    }
    m.close();
    st.tab = 'Đang lưu';
    render(api);
  });
  m.body.appendChild(ok);
  veChon();
  veLo();
}
