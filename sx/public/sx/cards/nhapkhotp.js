// Card Nhập kho thành phẩm (D62) — chứng từ ĐỘC LẬP, không liên quan bảng vào hộp.
//
//   Người lập ghi hàng chuyển sang kho: loại nào, bao nhiêu  →  PHIẾU NHÁP
//   Thủ kho đếm thật, sửa số cho khớp  →  DUYỆT  →  hàng vào Kho TP
//
// Số ĐẾM là số vào kho. Số người lập ghi chỉ để đối chiếu — chỗ lệch giữa hai số là
// thứ đáng xem, không phải thứ để chặn.

import { esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';
import { confirm2Step } from '/assets/sx/sx/components/modal.js';
import { moQuet } from '/assets/sx/sx/components/quet.js';

export async function render({ container, call, refresh, boot }) {
  container.className = 'sx-card';
  container.innerHTML = '<div class="sx-muted">Đang tải…</div>';

  let r;
  try {
    r = await call('sx.api.khotp.phieu_dang_mo');
  } catch (e) {
    container.innerHTML = `<div class="sx-error-box">${esc(e.message)}</div>`;
    return;
  }
  const ganDay = await call('sx.api.khotp.phieu_gan_day').catch(() => []);

  if (r.nhap) return vePhieu(container, r, ganDay, call, refresh, boot);
  return veChuaCo(container, r, ganDay, call, refresh);
}

// ───────────────────────────── chưa có phiếu nháp ─────────────────────────
// Danh mục TP rỗng: nói rõ phải làm gì VÀ liệt kê ứng viên. "Không tìm thấy sản
// phẩm nào" là bế tắc không lối ra — người dùng không thể đoán rằng thiếu một field
// trên Item.
function veTrongDanhMuc(goi_y) {
  return `<div class="sx-error-box">Danh mục thành phẩm đang TRỐNG nên chưa nhập kho được.

Item thành phẩm phải gắn nhóm SX = TP: mở Item trên Desk → trường "Nhóm SX" (custom_sx_nhom) = <b>TP</b>, và bỏ tick Disabled. Item cũng phải có BOM active thì mới nhập kho được.</div>`
    + ((goi_y && goi_y.length)
      ? `<div class="sx-field-label">Item ĐÃ có BOM nhưng chưa gắn nhóm TP (${goi_y.length})</div>
         <div class="sx-vh-list">${goi_y.map((g) => `
           <div class="sx-vh-row">
             <div class="sx-vh-who">
               <div class="sx-vh-name">${esc(g.ten)}</div>
               <div class="sx-vh-meta">${esc(g.item)}${
                 g.nhom ? ` · đang là nhóm ${esc(g.nhom)}` : ' · chưa gắn nhóm'}</div>
             </div>
           </div>`).join('')}</div>
         <div class="sx-muted">Cái nào là thành phẩm bán ra thì đổi nhóm SX thành TP,
           rồi quay lại màn này.</div>`
      : '');
}

function veChuaCo(container, r, ganDay, call, refresh) {
  const trong = !(r.danh_muc || []).length;
  container.innerHTML = `
    <div class="sx-field-label">Nhập kho thành phẩm</div>
    ${trong
      ? veTrongDanhMuc(r.goi_y)
      : `<div class="sx-muted">Ghi hàng chuyển sang kho, thủ kho đếm lại rồi duyệt —
           duyệt xong hàng mới vào <b>${esc(r.kho_tp)}</b>.</div>
         <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nk-tao">
           + LẬP PHIẾU NHẬP KHO</button>`}
    ${veGanDay(ganDay)}
  `;
  if (trong) return;
  container.querySelector('#sx-nk-tao').addEventListener('click', async (e) => {
    e.currentTarget.disabled = true;
    try {
      await call('sx.api.khotp.tao_phieu_nhap', {});
      refresh();
    } catch (err) { e.target.disabled = false; toastErr(err.message); }
  });
}

// ──────────────────────── có phiếu nháp: ghi hàng + duyệt ─────────────────
function vePhieu(container, r, ganDay, call, refresh, boot) {
  const p = r.nhap;
  const danhMuc = r.danh_muc || [];
  const rows = p.dong.map((x) => ({ ...x }));
  const tenSP = (item) => (danhMuc.find((d) => d.item === item) || {}).ten || item;

  container.innerHTML = `
    <div class="sx-vh-top">
      <div>
        <div class="sx-field-label">Phiếu nháp ${esc(p.name)}</div>
        <div class="sx-vh-tong"><span id="sx-nk-tong">0</span> <i>sp</i></div>
        <div class="sx-vh-tien" id="sx-nk-lech"></div>
      </div>
      <div class="sx-vh-done">
        <div class="sx-field-label">Ngày nhận</div>
        <div class="sx-vh-done-so" style="font-size:var(--sx-f-md)">${esc(veNgay(p.ngay))}</div>
      </div>
    </div>
    <div class="sx-vh-list" id="sx-nk-rows"></div>
    ${danhMuc.length
      ? '<div class="sx-field-label">Chọn sản phẩm — bấm để nhập số</div>'
      : veTrongDanhMuc(r.goi_y)}
    ${danhMuc.length > 10
      ? `<div class="sx-vh-tim-wrap">
           <span class="sx-vh-tim-icon" aria-hidden="true">⌕</span>
           <input class="sx-textarea sx-vh-search" id="sx-nk-tim" type="search"
             aria-label="Tìm sản phẩm" placeholder="Tìm trong ${danhMuc.length} sản phẩm">
         </div>` : ''}
    <div class="sx-sp-grid" id="sx-nk-dm"></div>
    <button type="button" class="sx-btn sx-quet-nut" id="sx-nk-quet">⌗ QUÉT HỘP</button>
    ${p.duoc_duyet
      ? `<div class="sx-muted">Thủ kho: đếm thật rồi sửa số cho khớp —
           <b>số đếm là số vào kho</b>.</div>
         <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nk-duyet">
           DUYỆT — NHẬN VÀO KHO</button>
         <button type="button" class="sx-btn" id="sx-nk-huy">Xoá phiếu nháp</button>`
      : `<button type="button" class="sx-btn sx-btn-big" id="sx-nk-luu">LƯU PHIẾU NHÁP</button>
         <div class="sx-muted">🔒 Bạn không có quyền duyệt. Thủ kho (role
           <b>SX Thu Kho</b>) sẽ đếm lại và duyệt phiếu này.</div>`}
    ${veGanDay(ganDay)}
  `;

  const box = container.querySelector('#sx-nk-rows');
  const laThuKho = p.duoc_duyet;

  function ve() {
    box.innerHTML = rows.length
      ? rows.map((x, i) => {
        const lech = x.so_dem - x.so_lap;
        return `<div class="sx-vh-row">
          <div class="sx-vh-who">
            <div class="sx-vh-name">${esc(x.ten || tenSP(x.item))}</div>
            <div class="sx-vh-meta">${laThuKho
              ? `phiếu ghi ${formatNumber(x.so_lap)}${
                lech ? ` · lệch ${lech > 0 ? '+' : ''}${formatNumber(lech)}` : ''}`
              : esc(x.dvt || '')}</div>
          </div>
          <button type="button" class="sx-vh-sl${lech ? ' sx-cell-lech' : ''}"
            data-i="${i}">${formatNumber(x.so_dem)}</button>
          <button type="button" class="sx-vh-del" data-del="${i}"
            aria-label="Bỏ dòng ${esc(x.ten || x.item)}">✕</button>
        </div>`;
      }).join('')
      : `<div class="sx-muted">Chưa ghi sản phẩm nào — chọn ở lưới bên dưới${
        danhMuc.length ? ', hoặc quét hộp' : ''}.</div>`;

    box.querySelectorAll('.sx-vh-sl').forEach((b) => {
      const x = rows[Number(b.dataset.i)];
      b.addEventListener('click', () => openNumpad({
        kicker: laThuKho ? 'Số thủ kho đếm' : 'Số chuyển sang kho',
        title: x.ten || tenSP(x.item),
        unitLabel: 'Số lượng', initial: x.so_dem,
        hint: (n) => (laThuKho && n !== x.so_lap
          ? `phiếu ghi ${formatNumber(x.so_lap)} · lệch ${n - x.so_lap > 0 ? '+' : ''}${
            formatNumber(n - x.so_lap)}` : ''),
        onOk: (v) => {
          x.so_dem = Math.max(0, Math.round(v));
          // Người LẬP sửa số thì sửa cả hai; THỦ KHO sửa thì chỉ đụng số đếm —
          // giữ nguyên số người lập ghi, vì chỗ lệch mới là thứ đáng xem.
          if (!laThuKho) x.so_lap = x.so_dem;
          ve();
        },
      }));
    });
    box.querySelectorAll('[data-del]').forEach((b) => {
      b.addEventListener('click', () => { rows.splice(Number(b.dataset.del), 1); ve(); });
    });

    const tong = rows.reduce((a, x) => a + x.so_dem, 0);
    const lech = tong - rows.reduce((a, x) => a + x.so_lap, 0);
    container.querySelector('#sx-nk-tong').textContent = formatNumber(tong);
    container.querySelector('#sx-nk-lech').textContent =
      (laThuKho && lech) ? `lệch ${lech > 0 ? '+' : ''}${formatNumber(lech)} so với phiếu` : '';
    veDanhMuc();
  }

  // Lưới sản phẩm hiện THẲNG trên màn, không giấu sau một nút: đây là việc chính
  // của màn này, mà giấu đi thì người dùng mở phiếu ra thấy trống trơn.
  // Sản phẩm đã ghi tô nền mùa kèm số — bấm lại là sửa.
  const oTim = container.querySelector('#sx-nk-tim');
  function veDanhMuc() {
    const q = (oTim ? oTim.value : '').toLowerCase().trim();
    const khop = danhMuc.filter((d) => !q || d.ten.toLowerCase().includes(q)
      || d.item.toLowerCase().includes(q));
    const grid = container.querySelector('#sx-nk-dm');
    if (!danhMuc.length) { grid.innerHTML = ''; return; }
    grid.innerHTML = khop.length
      ? khop.map((d) => {
        const co = rows.find((x) => x.item === d.item);
        return `<button type="button" class="sx-sp-chip${co ? ' sx-sp-chip-on' : ''}"
          data-item="${esc(d.item)}">${esc(d.ten)}${
          co ? ` · ${formatNumber(co.so_dem)}` : ''}</button>`;
      }).join('')
      : '<div class="sx-muted">Không tìm thấy sản phẩm nào.</div>';
    grid.querySelectorAll('[data-item]').forEach((b) => {
      b.addEventListener('click', () => themItem(b.dataset.item));
    });
  }
  if (oTim) oTim.addEventListener('input', veDanhMuc);
  ve();

  function themItem(item) {
    const co = rows.find((x) => x.item === item);
    const d = danhMuc.find((x) => x.item === item) || {};
    openNumpad({
      kicker: co ? 'Sửa số' : 'Thêm sản phẩm',
      title: d.ten || item,
      unitLabel: 'Số lượng', initial: co ? co.so_dem : 0,
      onOk: (v) => {
        const n = Math.max(0, Math.round(v));
        if (!n) { if (co) rows.splice(rows.indexOf(co), 1); ve(); return; }
        if (co) { co.so_dem = n; if (!laThuKho) co.so_lap = n; }
        else rows.push({ item, ten: d.ten || item, dvt: d.dvt || '', so_lap: n, so_dem: n });
        ve();
      },
    });
  }

  container.querySelector('#sx-nk-quet').addEventListener('click', () => moQuet({
    ma_quet: boot && boot.ma_quet, loai: 'sp',
    kicker: 'Nhập kho', title: 'Quét hộp',
    onTim: (item) => {
      if (!danhMuc.some((d) => d.item === item)) {
        toastErr('Sản phẩm này không nằm trong danh mục thành phẩm.');
        return;
      }
      themItem(item);
    },
  }));

  const luu = () => call('sx.api.khotp.sua_phieu', {
    name: p.name,
    rows: JSON.stringify(rows.map((x) => ({
      item: x.item, so_lap: x.so_lap, so_dem: x.so_dem,
    }))),
  });

  const btnLuu = container.querySelector('#sx-nk-luu');
  if (btnLuu) {
    btnLuu.addEventListener('click', async () => {
      try { await luu(); toast('Đã lưu phiếu nháp — mời thủ kho kiểm và duyệt.'); refresh(); }
      catch (e) { toastErr(e.message); }
    });
  }

  const btnHuy = container.querySelector('#sx-nk-huy');
  if (btnHuy) {
    btnHuy.addEventListener('click', () => confirm2Step({
      title: 'Xoá phiếu nháp',
      message: `Xoá phiếu ${p.name}. Chưa có gì vào kho nên không phải thu hồi gì.`,
      confirmLabel: 'XOÁ PHIẾU',
      onConfirm: async () => {
        try {
          await call('sx.api.khotp.huy_phieu', { name: p.name });
          toast('Đã xoá phiếu nháp.');
          refresh();
        } catch (e) { toastErr(e.message); throw e; }
      },
    }));
  }

  const btnDuyet = container.querySelector('#sx-nk-duyet');
  if (btnDuyet) {
    btnDuyet.addEventListener('click', async () => {
      const tong = rows.reduce((a, x) => a + x.so_dem, 0);
      if (!tong) { toastErr('Chưa có dòng nào có số > 0.'); return; }
      // Số đang sửa trên màn PHẢI lưu trước khi duyệt, không thì duyệt số cũ.
      try { await luu(); } catch (e) { toastErr(e.message); return; }
      confirm2Step({
        title: 'Duyệt phiếu nhận',
        message: `Nhận ${formatNumber(tong)} sản phẩm vào ${p.kho_dich} theo đúng số `
          + 'đếm. Duyệt xong chứng từ kho được ghi; sửa thì phải huỷ phiếu.',
        confirmLabel: 'DUYỆT',
        onConfirm: async () => {
          try {
            await call('sx.api.khotp.duyet_phieu', { name: p.name });
            toast(`Đã nhận ${formatNumber(tong)} sản phẩm vào kho.`);
            refresh();
          } catch (e) { toastErr(e.message); throw e; }
        },
      });
    });
  }
}

// "2026-08-22" -> "22/08" — người ở xưởng đọc ngày kiểu này, không đọc ISO
function veNgay(iso) {
  const d = String(iso || '').split('-');
  return d.length === 3 ? `${d[2]}/${d[1]}` : String(iso || '');
}

function veGanDay(ds) {
  if (!ds || !ds.length) return '';
  return `
    <div class="sx-field-label">Phiếu đã duyệt gần đây</div>
    <div class="sx-vh-list">${ds.map((g) => `
      <div class="sx-vh-row">
        <div class="sx-vh-who">
          <div class="sx-vh-name">${esc(g.name)}</div>
          <div class="sx-vh-meta">${esc(veNgay(g.ngay))} · ${esc(g.nguoi_duyet || '')}${
            g.tong_lech ? ` · lệch ${g.tong_lech > 0 ? '+' : ''}${formatNumber(g.tong_lech)}` : ''}</div>
        </div>
        <span class="sx-nv-qty">${formatNumber(g.tong_dem)}</span>
      </div>`).join('')}</div>`;
}
