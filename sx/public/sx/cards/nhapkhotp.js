// Card Nhập kho thành phẩm (D59) — PHIẾU NÀY sinh ra tồn kho TP.
//
//   QC chấm vào hộp (độc lập)  →  chốt Vào hộp  →  QC lập PHIẾU NHÁP
//   →  thủ kho đếm thật, sửa số  →  DUYỆT  →  hàng vào Kho TP
//
// Trước khi duyệt, trong sổ chưa có hộp nào — đúng như ngoài đời hộp còn nằm trên
// bàn chưa ai nhận. Nút DUYỆT chỉ hiện với thủ kho, và backend chặn lần nữa: ẩn
// nút không phải là bảo mật, mà cả giá trị của phiếu nằm ở chỗ người duyệt khác
// người lập.

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
    r = await call('sx.api.khotp.cho_lap_phieu');
  } catch (e) {
    container.innerHTML = `<div class="sx-error-box">${esc(e.message)}</div>`;
    return;
  }
  const ganDay = await call('sx.api.khotp.phieu_gan_day').catch(() => []);

  if (r.nhap) return vePhieu(container, r, ganDay, call, refresh, boot);
  return veChoLap(container, r, ganDay, call, refresh);
}

// ─────────────────────────── chưa có phiếu nháp: mời lập ───────────────────
function veChoLap(container, r, ganDay, call, refresh) {
  const ds = r.cho_lap || [];
  container.innerHTML = `
    <div class="sx-field-label">Nhập kho thành phẩm</div>
    ${ds.length
      ? `<div class="sx-muted">Hàng chưa nhập kho, theo bảng vào hộp từng ngày. Bấm
           để lập phiếu nháp — thủ kho đếm lại rồi duyệt, duyệt xong hàng mới vào
           <b>${esc(r.kho_tp)}</b>.</div>
         <div class="sx-vh-list">${ds.map((d, i) => `
           <div class="sx-vh-row">
             <div class="sx-vh-who">
               <div class="sx-vh-name">${esc(d.ngay)}${d.da_chot
                 ? '' : ' <span class="sx-badge sx-badge-run">bảng chưa chốt</span>'}</div>
               <div class="sx-vh-meta">${formatNumber(d.tong)} sp · ${d.so_loai} loại${
                 d.da_chot ? '' : ' · số còn có thể đổi'}</div>
             </div>
             <button type="button" class="sx-btn sx-nk-lap" data-i="${i}">LẬP PHIẾU</button>
           </div>`).join('')}</div>`
      : `<div class="sx-muted">Không còn hàng nào chưa nhập kho. Phiếu lập từ
           <b>bảng vào hộp</b> — QC chấm được sản phẩm nào thì ngày đó hiện ở đây,
           không cần chờ chốt Vào hộp.</div>`}
    ${veGanDay(ganDay)}
  `;
  container.querySelectorAll('.sx-nk-lap').forEach((b) => {
    b.addEventListener('click', async () => {
      const d = ds[Number(b.dataset.i)];
      b.disabled = true;
      try {
        await call('sx.api.khotp.tao_phieu_nhap', { ngay_sx: d.ngay_sx });
        toast('Đã lập phiếu nháp — mời thủ kho kiểm và duyệt.');
        refresh();
      } catch (e) { b.disabled = false; toastErr(e.message); }
    });
  });
}

// ─────────────────────────── có phiếu nháp: kiểm + duyệt ───────────────────
function vePhieu(container, r, ganDay, call, refresh, boot) {
  const p = r.nhap;
  const rows = p.dong.map((x) => ({ ...x }));

  container.innerHTML = `
    <div class="sx-vh-top">
      <div>
        <div class="sx-field-label">Phiếu nháp ${esc(p.name)}</div>
        <div class="sx-vh-tong"><span id="sx-nk-tong">0</span> <i>sp</i></div>
        <div class="sx-vh-tien" id="sx-nk-lech"></div>
      </div>
      <div class="sx-vh-done">
        <div class="sx-field-label">Ngày SX</div>
        <div class="sx-vh-done-so" style="font-size:var(--sx-f-md)">${esc(p.ngay)}</div>
      </div>
    </div>
    <div class="sx-muted">Duyệt xong hàng vào <b>${esc(p.kho_dich)}</b> · lập bởi
      ${esc(p.nguoi_lap || '')}. Bấm số để sửa theo đúng số ĐẾM ĐƯỢC.</div>
    <div class="sx-vh-hang2">
      <button type="button" class="sx-btn sx-quet-nut" id="sx-nk-quet">⌗ QUÉT HỘP</button>
      <button type="button" class="sx-btn sx-quet-nut" id="sx-nk-lammoi"
        title="Nạp lại số theo bảng vào hộp hiện tại">↻ LÀM MỚI SỐ THEO BẢNG</button>
    </div>
    <div class="sx-vh-list" id="sx-nk-rows"></div>
    ${p.duoc_duyet
      ? `<button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nk-duyet">
           DUYỆT — NHẬN VÀO KHO</button>
         <button type="button" class="sx-btn" id="sx-nk-huy">Xoá phiếu nháp</button>`
      : `<button type="button" class="sx-btn sx-btn-big" id="sx-nk-luu">LƯU SỐ ĐẾM</button>
         <div class="sx-muted">🔒 Bạn không có quyền duyệt. Thủ kho (role
           <b>SX Thu Kho</b>) sẽ kiểm và duyệt phiếu này.</div>`}
    ${veGanDay(ganDay)}
  `;

  const box = container.querySelector('#sx-nk-rows');
  function ve() {
    box.innerHTML = rows.map((x, i) => {
      const lech = x.so_dem - x.so_theo_so;
      return `<div class="sx-vh-row">
        <div class="sx-vh-who">
          <div class="sx-vh-name">${esc(x.ten)}</div>
          <div class="sx-vh-meta">bảng ${formatNumber(x.so_theo_so)}${
            lech ? ` · hộp lỗi ${formatNumber(-lech)}` : ''}</div>
        </div>
        <button type="button" class="sx-vh-sl${lech ? ' sx-cell-lech' : ''}"
          data-i="${i}">${formatNumber(x.so_dem)}</button>
      </div>`;
    }).join('');
    box.querySelectorAll('.sx-vh-sl').forEach((b) => {
      const x = rows[Number(b.dataset.i)];
      b.addEventListener('click', () => openNumpad({
        kicker: 'Số đếm thật', title: x.ten, unitLabel: 'Số lượng', initial: x.so_dem,
        // Nhận nhiều hơn bảng là bảng ghi sót, không phải hàng từ đâu ra — chặn
        // ngay ở bàn số thay vì để server từ chối sau khi gõ xong cả phiếu.
        hint: (n) => (n > x.so_theo_so
          ? `⚠ nhiều hơn bảng (${formatNumber(x.so_theo_so)})`
          : (n < x.so_theo_so ? `hộp lỗi ${formatNumber(x.so_theo_so - n)}` : '')),
        onOk: (v) => {
          const n = Math.max(0, Math.round(v));
          if (n > x.so_theo_so) {
            toastErr(`Không nhận quá số trên bảng (${formatNumber(x.so_theo_so)}). `
              + 'Bảng ghi sót thì phải sửa bảng.');
            return;
          }
          x.so_dem = n;
          ve();
        },
      }));
    });
    const tong = rows.reduce((a, x) => a + x.so_dem, 0);
    const hong = rows.reduce((a, x) => a + (x.so_theo_so - x.so_dem), 0);
    container.querySelector('#sx-nk-tong').textContent = formatNumber(tong);
    container.querySelector('#sx-nk-lech').textContent =
      hong ? `${formatNumber(hong)} hộp lỗi không nhận` : '';
  }
  ve();

  // Quét làm đúng việc nó giỏi nhất là ĐỊNH DANH: nhảy tới đúng dòng rồi mở bàn
  // số. Số lượng vẫn do thủ kho ĐẾM và gõ — không ai quét 1.240 hộp.
  container.querySelector('#sx-nk-quet').addEventListener('click', () => moQuet({
    ma_quet: boot && boot.ma_quet, loai: 'sp',
    kicker: 'Nhập kho', title: 'Quét hộp để tìm dòng',
    onTim: (item) => {
      const i = rows.findIndex((x) => x.item === item);
      if (i < 0) { toastErr('Sản phẩm này không có trong phiếu.'); return; }
      const b = box.querySelector(`.sx-vh-sl[data-i="${i}"]`);
      if (b) { b.scrollIntoView({ block: 'center' }); b.click(); }
    },
  }));

  // Bảng vào hộp có thể đổi sau lúc lập phiếu (QC vẫn đang chấm). Nút này nạp lại
  // cột "Theo bảng" mà GIỮ số đếm đã gõ — không phải xoá phiếu gõ lại từ đầu.
  container.querySelector('#sx-nk-lammoi').addEventListener('click', async (e) => {
    e.currentTarget.disabled = true;
    try {
      await call('sx.api.khotp.lam_moi_phieu', { name: p.name });
      toast('Đã nạp lại số theo bảng vào hộp.');
      refresh();
    } catch (err) { e.target.disabled = false; toastErr(err.message); }
  });

  const luu = () => call('sx.api.khotp.sua_phieu', {
    name: p.name,
    rows: JSON.stringify(rows.map((x) => ({ item: x.item, so_luong: x.so_dem }))),
  });

  const btnLuu = container.querySelector('#sx-nk-luu');
  if (btnLuu) {
    btnLuu.addEventListener('click', async () => {
      try { await luu(); toast('Đã lưu số đếm vào phiếu nháp.'); refresh(); }
      catch (e) { toastErr(e.message); }
    });
  }

  const btnHuy = container.querySelector('#sx-nk-huy');
  if (btnHuy) {
    btnHuy.addEventListener('click', () => confirm2Step({
      title: 'Xoá phiếu nháp',
      message: `Xoá phiếu ${p.name}. Chưa có gì vào kho nên không phải thu hồi gì; `
        + 'lập lại phiếu cho ngày đó lúc nào cũng được.',
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
      const hong = rows.reduce((a, x) => a + (x.so_theo_so - x.so_dem), 0);
      if (!tong) { toastErr('Chưa có dòng nào đếm được số > 0.'); return; }
      // Số đang sửa trên màn PHẢI lưu trước khi duyệt, không thì duyệt số cũ.
      try { await luu(); } catch (e) { toastErr(e.message); return; }
      confirm2Step({
        title: 'Duyệt phiếu nhận',
        message: `Nhận ${formatNumber(tong)} sản phẩm vào ${p.kho_dich}.`
          + (hong ? ` ${formatNumber(hong)} hộp lỗi được ghi thành phiếu xuất huỷ riêng `
            + '— nguyên liệu của số hộp đó vẫn trừ, vì đã đóng thật.' : '')
          + ' Duyệt xong chứng từ kho được ghi; sửa thì phải huỷ phiếu.',
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

function veGanDay(ds) {
  if (!ds || !ds.length) return '';
  return `
    <div class="sx-field-label">Phiếu đã duyệt gần đây</div>
    <div class="sx-vh-list">${ds.map((g) => `
      <div class="sx-vh-row">
        <div class="sx-vh-who">
          <div class="sx-vh-name">${esc(g.name)}</div>
          <div class="sx-vh-meta">${esc(g.ngay)} · ${esc(g.nguoi_duyet || '')}${
            g.tong_lech ? ` · ${formatNumber(-g.tong_lech)} hộp lỗi` : ''}</div>
        </div>
        <span class="sx-nv-qty">${formatNumber(g.tong_dem)}</span>
      </div>`).join('')}</div>`;
}
