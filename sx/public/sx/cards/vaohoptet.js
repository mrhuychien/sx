// Card "Vào hộp Tết" (D122) — một màn, một lần lưu.
//
// QC Tết ghi: mã hàng (chọn hoặc quét — chỉ HÀNG TẾT) → MỘT bàn số có tab THÙNG /
// HỘP và ô HSD ngay trên đó (D124): chọn mã là gõ số luôn, không qua cửa sổ thứ hai.
// Từ D153 bàn số này là moSoHsd dùng chung với màn Nhập kho thành phẩm.
// Bấm LƯU một lần là xong: phiếu nhập kho NHÁP (thủ kho đếm + duyệt ở màn Nhập kho)
// và sản lượng CÔNG NHẬT trong bảng vào hộp của ngày. Không chấm từng người, không
// lập phiếu riêng, không bấm qua ba màn.
//
// Dòng đang gõ lưu tạm trên máy theo ngày: lỡ tay tải lại trang không mất.

import { esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { moTaUom } from '/assets/sx/sx/components/soluong.js';
import { moQuet } from '/assets/sx/sx/components/quet.js';
import { hsdTu, moSoHsd, veNgayDu } from '/assets/sx/sx/cards/nhapkhotp.js';

const KHOA = 'sx-tet-dong-';

export async function render({ container, call, boot }) {
  container.className = 'sx-card sx-tet';
  const ngay = (boot && (boot.ngay_xem || boot.hom_nay)) || new Date().toISOString().slice(0, 10);
  const khoa = KHOA + ngay;
  let dong = [];
  try { dong = JSON.parse(localStorage.getItem(khoa) || '[]'); } catch (e) { dong = []; }
  const ghiMay = () => {
    try { localStorage.setItem(khoa, JSON.stringify(dong)); } catch (e) { /* bỏ qua */ }
  };

  container.innerHTML = '<div class="sx-muted">Đang tải danh mục…</div>';
  let dm;
  try { dm = await call('sx.api.tet.danh_muc'); } catch (e) {
    container.innerHTML = `<div class="sx-error-box">${esc(e.message)}</div>`;
    return;
  }
  const sp = (item) => (dm.rows || []).find((x) => x.item === item) || { item, ten: item, uoms: [] };
  const hsdMacDinh = (item) => hsdTu(ngay, sp(item));

  container.innerHTML = `
    <div class="sx-tet-dau">
      <div><div class="sx-field-label">Vào hộp Tết · ngày ${esc(veNgayDu(ngay))}</div>
        <div class="sx-tet-tong"><span id="tet-tong">0</span> <i>hộp</i></div></div>
      <div class="sx-muted sx-tet-giai">Ghi số + HSD rồi bấm LƯU một lần: tạo phiếu nhập
        kho (thủ kho duyệt) và ghi sản lượng công nhật.</div>
    </div>
    ${dm.chua_co_nhom ? `<div class="sx-warn-text">Chưa có nhóm Hàng Tết (SX Settings → Nhóm
      Hàng Tết, hoặc Item Group tên chứa "Tết") — đang bày mọi thành phẩm.</div>` : ''}
    <div class="sx-vh-list" id="tet-dong"></div>
    <div class="sx-vh-hang2">
      <button type="button" class="sx-btn" id="tet-them">+ THÊM HÀNG TẾT</button>
      <button type="button" class="sx-btn sx-quet-nut" id="tet-quet">⌗ QUÉT HỘP</button>
    </div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="tet-luu">
      LƯU — TẠO PHIẾU NHẬP KHO</button>
    <div id="tet-ds"></div>`;
  const $ = (s) => container.querySelector(s);
  const box = $('#tet-dong');

  function ve() {
    box.innerHTML = dong.length ? dong.map((x, i) => {
      const s = sp(x.item);
      const h = x.hsd || hsdMacDinh(x.item);
      return `<div class="sx-vh-row">
        <div class="sx-vh-who">
          <div class="sx-vh-name">${esc(s.ten)}</div>
          <div class="sx-vh-meta">${esc(moTaUom(x.ct) || `${formatNumber(x.so)} ${s.dvt || ''}`)}${
            x.ct && x.ct.length > 1 || (x.ct && x.ct[0] && x.ct[0].he_so > 1)
              ? ` = ${formatNumber(x.so)} ${esc(s.dvt || '')}` : ''}</div>
          ${h ? `<button type="button" class="sx-nk-hsd" data-hsd="${i}"><span>HSD ${esc(veNgayDu(h))} ✎</span>${
            x.hsd ? '' : '<span class="sx-nk-hsd-mac">mặc định</span>'}</button>`
            : `<button type="button" class="sx-nk-hsd sx-nk-hsd-thieu" data-hsd="${i}">⚠ Chưa có HSD — bấm để nhập</button>`}
        </div>
        <button type="button" class="sx-vh-sl" data-sl="${i}">${formatNumber(x.so)}</button>
        <button type="button" class="sx-vh-del" data-del="${i}" aria-label="Bỏ dòng ${esc(s.ten)}">✕</button>
      </div>`;
    }).join('') : '<div class="sx-muted">Chưa có dòng nào — bấm THÊM MÃ HÀNG hoặc quét hộp.</div>';
    $('#tet-tong').textContent = formatNumber(dong.reduce((a, x) => a + Number(x.so || 0), 0));
    box.querySelectorAll('[data-sl]').forEach((b) => b.addEventListener('click', () => moDong(dong[Number(b.dataset.sl)])));
    box.querySelectorAll('[data-hsd]').forEach((b) => b.addEventListener('click', () => moDong(dong[Number(b.dataset.hsd)])));
    box.querySelectorAll('[data-del]').forEach((b) => b.addEventListener('click', () => {
      dong.splice(Number(b.dataset.del), 1); ghiMay(); ve();
    }));
  }

  // Một bàn số cho cả số lẫn HSD. `x` = dòng đang sửa, null = dòng mới của `item`. Cùng mã + cùng HSD là
  // cùng MỘT lô — thủ kho không duyệt được phiếu có hai dòng một lô — nên các dòng khác của mã hiện thành
  // ô bấm trên bàn số, và lưu trùng HSD một dòng khác thì báo ngay tại đó.
  function moDong(x, item = x && x.item) {
    moNhapTet({ s: sp(item), ngay, cu: x, macDinh: hsdMacDinh(item),
      khac: dong.filter((y) => y.item === item && y !== x),
      onKhac: (y) => moDong(y),
      onOk: (so, ct, hsd) => {
        if (x) { x.so = so; x.ct = ct; x.hsd = hsd; } else dong.push({ item, so, ct, hsd });
        ghiMay(); ve();
      } });
  }

  // Chọn / quét mã là vào thẳng bàn số. Mã đã có dòng HSD mặc định thì mở sửa dòng đó (gõ số mới đè
  // số cũ), chưa có thì mở dòng mới.
  function themItem(item) {
    const md = hsdMacDinh(item);
    moDong(dong.find((y) => y.item === item && (y.hsd || md) === md) || null, item);
  }

  $('#tet-them').addEventListener('click', () => moChon(dm.rows || [], themItem));
  $('#tet-quet').addEventListener('click', () => moQuet({
    ma_quet: dm.ma_quet, loai: 'sp', kicker: 'Vào hộp Tết', title: 'Quét hộp',
    onTim: (item) => {
      if (!(dm.rows || []).some((d) => d.item === item)) { toastErr('Mã này không phải hàng Tết.'); return; }
      themItem(item);
    },
  }));

  $('#tet-luu').addEventListener('click', () => {
    if (!dong.length) { toastErr('Chưa có dòng nào.'); return; }
    const thieu = dong.filter((x) => !(x.hsd || hsdMacDinh(x.item)));
    if (thieu.length) {
      toastErr(`Chưa có HSD: ${thieu.map((x) => sp(x.item).ten).join(', ')}`);
      return;
    }
    const tong = dong.reduce((a, x) => a + Number(x.so || 0), 0);
    confirm2Step({
      title: 'Lưu vào hộp Tết',
      message: `${dong.length} dòng · ${formatNumber(tong)} hộp · ngày ${veNgayDu(ngay)}.\n\n`
        + '• Tạo PHIẾU NHẬP KHO NHÁP — thủ kho đếm lại và duyệt ở màn Nhập kho, duyệt rồi '
        + 'hàng mới vào kho (có lô + HSD).\n• Ghi sản lượng CÔNG NHẬT vào bảng vào hộp '
        + 'của ngày.',
      confirmLabel: 'LƯU & TẠO PHIẾU',
      onConfirm: async () => {
        try {
          const r = await call('sx.api.tet.luu', {
            ngay,
            rows: JSON.stringify(dong.map((x) => ({ item: x.item, so: x.so,
              chi_tiet: x.ct || null, hsd: x.hsd || hsdMacDinh(x.item) }))),
          });
          dong = [];
          ghiMay(); ve();
          toast(`Đã tạo phiếu ${r.phieu} (${formatNumber(r.tong)} hộp) — chờ thủ kho duyệt. `
            + 'Công nhật đã ghi.');
          taiDs();
        } catch (e) { toastErr(e.message); throw e; }
      },
    });
  });

  async function taiDs() {
    const ds = $('#tet-ds');
    let r;
    try { r = await call('sx.api.tet.gan_day'); } catch (e) {
      ds.innerHTML = `<div class="sx-warn-text">${esc(e.message)}</div>`; return;
    }
    if (!r.length) { ds.innerHTML = ''; return; }
    ds.innerHTML = `<div class="sx-field-label">Phiếu Tết gần đây</div>
      <div class="sx-vh-list">${r.map((p) => `
        <div class="sx-vh-row">
          <div class="sx-vh-who">
            <div class="sx-vh-name">${esc(p.name)} · ${esc(veNgayDu(p.ngay))}
              <span class="sx-badge ${p.docstatus === 1 ? 'sx-badge-ok'
                : (p.docstatus === 2 ? 'sx-badge-err' : 'sx-tet-cho')}">${esc(p.trang_thai)}</span></div>
            <div class="sx-vh-meta">${esc(p.dong.map((d) => `${d.ten} ${formatNumber(d.so)}${
              d.hsd ? ` (HSD ${veNgayDu(d.hsd)})` : ''}`).join(' · '))}</div>
          </div>
          <span class="sx-nv-qty">${formatNumber(p.tong)}</span>
          ${p.duoc_xoa ? `<button type="button" class="sx-vh-del" data-xoa="${esc(p.name)}"
            aria-label="Xoá phiếu ${esc(p.name)}">✕</button>` : ''}
        </div>`).join('')}</div>`;
    ds.querySelectorAll('[data-xoa]').forEach((b) => b.addEventListener('click', () => confirm2Step({
      title: `Xoá phiếu ${b.dataset.xoa}`,
      message: 'Phiếu chưa duyệt nên chưa có gì vào kho. Xoá phiếu sẽ xoá luôn sản lượng '
        + 'công nhật đã ghi cùng nó.',
      confirmLabel: 'XOÁ PHIẾU',
      onConfirm: async () => {
        try { await call('sx.api.tet.xoa', { name: b.dataset.xoa }); toast('Đã xoá phiếu.'); taiDs(); }
        catch (e) { toastErr(e.message); throw e; }
      },
    })));
  }

  ve();
  taiDs();
}

function moChon(ds, onChon) {
  const m = openModal({ kicker: 'Vào hộp Tết', title: 'Chọn hàng Tết' });
  m.body.innerHTML = `<input class="sx-textarea" type="search" id="tet-loc" autocomplete="off"
      placeholder="Tìm trong ${ds.length} mã hàng Tết…"><div id="tet-ds-sp"></div>`;
  const o = m.body.querySelector('#tet-loc');
  const box = m.body.querySelector('#tet-ds-sp');
  function ve() {
    const q = o.value.toLowerCase().trim();
    const khop = ds.filter((d) => !q || d.ten.toLowerCase().includes(q) || d.item.toLowerCase().includes(q));
    box.innerHTML = khop.length ? `<div class="sx-vh-list">${khop.map((d) => `
      <button type="button" class="sx-nv-row" data-item="${esc(d.item)}"
        style="flex-direction:row;align-items:center;justify-content:space-between;min-height:var(--sx-tap-lg)">
        <span class="sx-nv-ten">${esc(d.ten)}</span>
        <span class="sx-nv-qty">${d.uoms && d.uoms.length > 1 ? esc(d.uoms.map((u) => u.uom).join(' / '))
          : esc(d.dvt || '')}</span></button>`).join('')}</div>`
      : `<div class="sx-muted">${ds.length ? 'Không tìm thấy.' : 'Chưa có mã hàng Tết nào.'}</div>`;
    box.querySelectorAll('[data-item]').forEach((b) => b.addEventListener('click', () => {
      m.close(); onChon(b.dataset.item);
    }));
  }
  o.addEventListener('input', ve);
  ve();
}

/**
 * Bàn số Vào hộp Tết (D124): tab đơn vị (THÙNG / HỘP — mỗi tab một số riêng) + ô HSD + phím số, tất cả
 * trên MỘT màn. Từ D153 là bàn số chung moSoHsd (cards/nhapkhotp.js) — màn Nhập kho dùng y hệt.
 * onOk(tong, chi_tiet|null, hsd|null) — hsd null là dùng HSD mặc định của mã (ngày + Shelf Life).
 * `khac` = các dòng khác cùng mã trên màn (mỗi HSD một lô): hiện thành ô bấm (onKhac), trùng HSD thì
 * không cho lưu.
 */
export function moNhapTet({ s, ngay, cu, macDinh, khac = [], onKhac, onOk }) {
  const hsdCua = (y) => y.hsd || macDinh;
  return moSoHsd({
    kicker: `Vào hộp Tết · ${veNgayDu(ngay)}`, ten: s.ten, uoms: s.uoms, dvt: s.dvt, ngay,
    chi_tiet: cu && cu.ct, tong: (cu && Number(cu.so)) || 0, hsd: cu && cu.hsd, macDinh,
    daCo: khac.map((y) => ({ nhan: `HSD ${hsdCua(y) ? veNgayDu(hsdCua(y)) : '—'}`, so: Number(y.so) || 0 })),
    onDaCo: (i) => onKhac && onKhac(khac[i]),
    kiemLuu: (t, h) => (khac.some((y) => hsdCua(y) === h)
      ? `Mã này đã có dòng HSD ${veNgayDu(h)} — cùng mã cùng HSD là một lô: bấm ô HSD đó phía trên để sửa số.`
      : ''),
    onOk,
  });
}
