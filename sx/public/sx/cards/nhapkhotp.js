// Card Nhập kho thành phẩm (D62) — chứng từ ĐỘC LẬP, không liên quan bảng vào hộp.
//
//   Người lập ghi hàng chuyển sang kho: loại nào, bao nhiêu  →  PHIẾU NHÁP
//   Thủ kho đếm thật, sửa số cho khớp  →  DUYỆT  →  hàng vào Kho TP
//
// Số ĐẾM là số vào kho. Số người lập ghi chỉ để đối chiếu — chỗ lệch giữa hai số là
// thứ đáng xem, không phải thứ để chặn.
//
// Hai chứng từ vẫn độc lập, nhưng màn này BÀY RA thứ xưởng vừa đóng xong (mục "Vừa
// vào hộp"): bắt thủ kho tự nhớ hôm nay đóng những mã nào rồi đi tìm trong vài chục
// SKU là chỗ sinh sót hàng. Bày ra để bấm, không phải để ràng buộc — vẫn ghi được mã
// không có trong bảng chấm, và sửa số xuống thoải mái.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { formatNumber } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openSoLuong, moTaUom, tachUom } from '/assets/sx/sx/components/soluong.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
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

  // D104: bấm một phiếu đã duyệt → xem chi tiết, thủ kho huỷ được ngay tại đây.
  // Gắn MỘT lần trên khung card (bắt sự kiện nổi lên), vì hai nhánh dưới vẽ lại
  // innerHTML và listener gắn trên từng dòng sẽ mất theo.
  if (!container.dataset.ganDay) {
    container.dataset.ganDay = '1';
    container.addEventListener('click', (e) => {
      const dong = e.target.closest('[data-phieu]');
      if (dong) moPhieuDaDuyet(dong.dataset.phieu, call, refresh);
    });
  }

  if (r.nhap) return vePhieu(container, r, ganDay, call, refresh, boot);
  return veChuaCo(container, r, ganDay, call, refresh);
}

// Chi tiết phiếu ĐÃ DUYỆT + huỷ (D104). Huỷ là THU HỒI chứng từ kho thật, nên:
// bắt lý do, nói rõ hệ quả, và có "Huỷ & lập lại" cho lý do hay gặp nhất — đếm sai
// một dòng — để thủ kho không phải gõ lại cả phiếu.
async function moPhieuDaDuyet(name, call, refresh) {
  let p;
  try { p = await call('sx.api.khotp.chi_tiet_phieu', { name }); } catch (e) {
    toastErr(e.message); return;
  }
  const m = openModal({ kicker: 'Phiếu đã duyệt', title: `${p.name} · ${veNgay(p.ngay)}` });
  m.body.innerHTML = `
    <div class="sx-muted">Duyệt bởi ${esc(p.nguoi_duyet || '?')}${p.duyet_luc
      ? ` lúc ${esc(String(p.duyet_luc).slice(11, 16))}` : ''} · vào ${esc(p.kho_dich || '')}</div>
    <div class="sx-vh-list">${p.dong.map((x) => `
      <div class="sx-vh-row" style="cursor:default">
        <div class="sx-vh-who"><div class="sx-vh-name">${esc(x.ten || x.item)}</div>
          ${x.hsd ? `<div class="sx-vh-meta">HSD ${esc(veNgayDu(x.hsd))}</div>` : ''}</div>
        <span class="sx-nv-qty">${formatNumber(x.so_dem)} ${esc(x.dvt || '')}</span>
      </div>`).join('')}</div>
    <div class="sx-vh-footer"><span class="sx-field-label">Tổng</span>
      <span>${formatNumber(p.tong_dem)}</span></div>`;
  if (!p.duoc_huy) {
    m.body.appendChild(el('div', 'sx-muted', p.docstatus === 1
      ? '🔒 Chỉ thủ kho / quản lý huỷ được phiếu đã duyệt.' : ''));
    return;
  }
  m.body.appendChild(el('div', 'sx-modal-msg',
    'Huỷ phiếu sẽ RÚT số hàng trên ra khỏi kho, trả lại bột và bao bì đã trừ; nợ '
    + 'BOM / nợ vào hộp của phiếu này chuyển sang Đã huỷ. Hàng đã bán hoặc xuất đi '
    + 'thì không huỷ được — phải huỷ chứng từ xuất trước.'));
  const ta = el('textarea', 'sx-textarea');
  ta.rows = 2;
  ta.placeholder = 'Lý do huỷ (bắt buộc) — vd: đếm sai dòng Sen 300g';
  m.body.appendChild(ta);
  const huy = async (lapLai, nut) => {
    if (!ta.value.trim()) { toastErr('Phải ghi lý do huỷ.'); ta.focus(); return; }
    nut.disabled = true;
    try {
      const kq = await call('sx.api.khotp.huy_phieu',
        { name: p.name, ly_do: ta.value.trim(), lap_lai: lapLai ? 1 : 0 });
      toast(kq.phieu_moi
        ? `Đã huỷ ${p.name} — phiếu nháp ${kq.phieu_moi} chép sẵn các dòng, sửa rồi duyệt lại.`
        : `Đã huỷ ${p.name}.`);
      m.close();
      refresh();
    } catch (e) { nut.disabled = false; toastErr(e.message); }
  };
  const hang = el('div', 'sx-nobom-nut');
  if (!p.co_nhap) {
    const lai = el('button', 'sx-btn sx-btn-primary', 'HUỶ & LẬP LẠI');
    lai.type = 'button';
    lai.title = 'Huỷ rồi lập phiếu nháp mới chép sẵn các dòng — sửa số sai rồi duyệt lại';
    lai.addEventListener('click', () => huy(true, lai));
    hang.appendChild(lai);
  }
  const chi = el('button', 'sx-btn sx-btn-danger', 'HUỶ PHIẾU');
  chi.type = 'button';
  chi.addEventListener('click', () => confirm2Step({
    title: `Huỷ ${p.name}?`,
    message: `Rút ${formatNumber(p.tong_dem)} sản phẩm ra khỏi ${p.kho_dich}. Không lập lại phiếu.`,
    confirmLabel: 'HUỶ PHIẾU',
    onConfirm: () => huy(false, chi),
  }));
  hang.appendChild(chi);
  m.body.appendChild(hang);
}

// ───────────────────────────── chưa có phiếu nháp ─────────────────────────
// Danh mục TP rỗng: nói rõ phải làm gì VÀ liệt kê ứng viên. "Không tìm thấy sản
// phẩm nào" là bế tắc không lối ra — người dùng không thể đoán rằng thiếu một field
// trên Item.
function veTrongDanhMuc(goi_y) {
  return `<div class="sx-error-box">Chưa khai báo thành phẩm nên chưa nhập kho được.

Cách nhanh nhất: mở <b>SX Settings → Nhóm hàng là thành phẩm</b> rồi chọn Item Group chứa thành phẩm — cả nhóm con tính theo, khỏi phải sửa từng Item.

(Cách lẻ: mở từng Item đặt "Nhóm SX" = TP.)</div>`
    + ((goi_y && goi_y.length)
      ? `<div class="sx-field-label">Nhóm hàng đang có Item CÓ BOM (${goi_y.length})</div>
         <div class="sx-muted">Nhóm nào chứa thành phẩm bán ra thì chọn nhóm đó trong
           SX Settings.</div>
         <div class="sx-vh-list">${goi_y.map((g) => `
           <div class="sx-vh-row">
             <div class="sx-vh-who">
               <div class="sx-vh-name">${esc(g.nhom)}</div>
               <div class="sx-vh-meta">${g.so_item} item · ${esc((g.vi_du || []).join(', '))}${
                 g.so_item > (g.vi_du || []).length ? '…' : ''}</div>
             </div>
             <span class="sx-nv-qty">${g.so_item}</span>
           </div>`).join('')}</div>`
      : '');
}

function veChuaCo(container, r, ganDay, call, refresh) {
  const trong = !(r.danh_muc || []).length;
  const cho = r.cho_nhan || [];
  container.innerHTML = `
    <div class="sx-field-label">Nhập kho thành phẩm</div>
    ${trong
      ? veTrongDanhMuc(r.goi_y)
      : `<div class="sx-muted">Ghi hàng chuyển sang kho, thủ kho đếm lại rồi duyệt —
           duyệt xong hàng mới vào <b>${esc(r.kho_tp)}</b>.</div>
         <div id="sx-nk-cn">${veChoNhan(cho, [])}</div>
         <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nk-tao">
           + LẬP PHIẾU ${cho.length ? 'TRỐNG' : 'NHẬP KHO'}</button>`}
    ${veGanDay(ganDay)}
  `;
  if (trong) return;

  // Bấm thẳng một mã trong "vừa vào hộp" là lập phiếu kèm luôn dòng đó — bắt bấm
  // "lập phiếu trống" rồi mới tìm lại mã vừa thấy là thừa một bước.
  container.querySelectorAll('[data-cn]').forEach((b) => {
    const d = cho.find((x) => x.item === b.dataset.cn);
    const tao = async (ds) => {
      try {
        await call('sx.api.khotp.tao_phieu_nhap', { rows: JSON.stringify(ds) });
        refresh();
      } catch (err) { toastErr(err.message); }
    };
    // W05: nhiều ngày đóng hộp = nhiều HSD = nhiều lô → mỗi HSD một dòng, thủ kho
    // đếm lại từng dòng trên phiếu. Một HSD thì hỏi số như trước.
    const chia = chiaCua(d);
    b.addEventListener('click', () => (chia.length > 1
      ? tao(chia.map((g) => ({ item: d.item, so_luong: Math.floor(g.con), hsd: g.hsd })))
      : openSoLuong({
        kicker: `Đã vào hộp ${formatNumber(d.con)} — chưa nhập kho`,
        ten: d.ten,
        uoms: d.uoms || [],
        chi_tiet: null,
        tong: d.con,
        onOk: (tong, ct) => {
          const n = Math.max(0, Math.round(tong));
          if (!n) return;
          tao([{ item: d.item, so_luong: n, chi_tiet: ct, hsd: (chia[0] || {}).hsd || null }]);
        },
      })));
  });

  container.querySelector('#sx-nk-tao').addEventListener('click', async (e) => {
    e.currentTarget.disabled = true;
    try {
      await call('sx.api.khotp.tao_phieu_nhap', {});
      refresh();
    } catch (err) { e.target.disabled = false; toastErr(err.message); }
  });
}

// Mã đã chấm vào hộp mà chưa nhập kho. Số bên phải là PHẦN CÒN LẠI, không phải tổng
// đã chấm — nhận một phần rồi thì phần đã nhận biến khỏi danh sách này.
function veChoNhan(cho, rows, coTaiHet) {
  if (!cho || !cho.length) {
    return `<div class="sx-muted">Chưa có mã hàng nào vừa vào hộp mà chưa nhập kho
      (7 ngày gần đây). Vẫn lập phiếu và ghi tay được.</div>`;
  }
  return `
    <div class="sx-field-label">Vừa vào hộp — chưa nhập kho (${cho.length})</div>
    <div class="sx-muted">Bấm mã hàng để ghi số nhận. Số bên phải là phần còn lại.</div>
    ${coTaiHet ? `<button type="button" class="sx-btn" id="sx-nk-tai">
      ⇩ TẢI TẤT CẢ VÀO PHIẾU</button>` : ''}
    <div class="sx-vh-list">${cho.map((d) => {
    // W05: một mã có thể nhiều dòng (mỗi HSD một dòng) — cộng hết các dòng của mã.
    const cua = (rows || []).filter((x) => x.item === d.item);
    const co = cua.length ? {
      so_hien: cua.reduce((a, x) => a + Number(x.so_hien != null ? x.so_hien : x.so_dem), 0),
    } : null;
    const theoHsd = chiaCua(d).filter((g) => g.hsd);
    // Kèm cách chia: người bấm là người đang đứng trước chồng thùng, "21 thùng 3 hộp"
    // đọc được ngay còn "255" thì phải chia nhẩm mới biết đủ hay thiếu.
    const chia = [moTaUom(tachUom(co ? co.so_hien : d.con, d.uoms)),
      theoHsd.length > 1 ? theoHsd.map((g) => `HSD ${veNgayDu(g.hsd)}: ${formatNumber(g.con)}`)
        .join(' · ') : (theoHsd[0] ? `HSD ${veNgayDu(theoHsd[0].hsd)}` : '')]
      .filter(Boolean).join(' — ');
    return `<button type="button" class="sx-nv-row${co ? ' sx-nv-row-xong' : ''}"
        data-cn="${esc(d.item)}" style="flex-direction:row;align-items:center;
        justify-content:space-between;min-height:var(--sx-tap-lg)">
        <span class="sx-nv-who">
          <span class="sx-nv-ten">${esc(d.ten)}</span>
          ${chia ? `<span class="sx-vh-meta">${esc(chia)}</span>` : ''}
        </span>
        <span class="sx-nv-qty">${co
      ? `ghi ${formatNumber(co.so_hien)}`
      : formatNumber(d.con)}</span>
      </button>`;
  }).join('')}</div>`;
}

// ──────────────────────── có phiếu nháp: ghi hàng + duyệt ─────────────────
function vePhieu(container, r, ganDay, call, refresh, boot) {
  const p = r.nhap;
  const danhMuc = r.danh_muc || [];
  const cho = r.cho_nhan || [];
  const rows = p.dong.map((x) => ({ ...x }));
  const tenSP = (item) => (danhMuc.find((d) => d.item === item) || {}).ten || item;
  // D97: dòng có cờ riêng từ server; dòng vừa thêm trên máy thì tra danh mục.
  const coBom = (x) => (x.co_bom !== undefined ? x.co_bom
    : (danhMuc.find((d) => d.item === x.item) || {}).co_bom !== false);

  container.innerHTML = `
    <div class="sx-vh-top">
      <div>
        <div class="sx-field-label">Phiếu nháp ${esc(p.name)}${
          p.nguon ? ` · 🧧 ${esc(p.nguon)}` : ''}${
          r.so_nhap_cho ? ` · còn ${r.so_nhap_cho} phiếu nháp chờ sau` : ''}</div>
        <div class="sx-vh-tong"><span id="sx-nk-tong">0</span> <i>sp</i></div>
        <div class="sx-vh-tien" id="sx-nk-lech"></div>
      </div>
      <div class="sx-vh-done">
        <div class="sx-field-label">Ngày nhận</div>
        <div class="sx-vh-done-so" style="font-size:var(--sx-f-md)">${esc(veNgay(p.ngay))}</div>
      </div>
    </div>
    <div class="sx-vh-list" id="sx-nk-rows"></div>
    <div id="sx-nk-cn"></div>
    ${danhMuc.length
      ? `<div class="sx-vh-hang2">
           <button type="button" class="sx-btn" id="sx-nk-tim">⌕ TÌM SẢN PHẨM</button>
           <button type="button" class="sx-btn sx-quet-nut" id="sx-nk-quet">⌗ QUÉT HỘP</button>
         </div>`
      : veTrongDanhMuc(r.goi_y)}
    ${p.duoc_duyet
      ? `<div class="sx-muted">Thủ kho: đếm thật rồi sửa số cho khớp —
           <b>số đếm là số vào kho</b>.</div>
         <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nk-duyet">
           DUYỆT — NHẬN VÀO KHO</button>`
      : `<button type="button" class="sx-btn sx-btn-big" id="sx-nk-luu">LƯU PHIẾU NHÁP</button>
         <div class="sx-muted">🔒 Bạn không có quyền duyệt. Thủ kho (role
           <b>SX Thu Kho</b>) sẽ đếm lại và duyệt phiếu này.</div>`}
    ${p.duoc_xoa
      ? '<button type="button" class="sx-btn" id="sx-nk-huy">Xoá phiếu nháp</button>'
      : ''}
    ${veGanDay(ganDay)}
  `;

  const box = container.querySelector('#sx-nk-rows');
  const laThuKho = p.duoc_duyet;

  function uomCua(item) {
    return (danhMuc.find((x) => x.item === item) || {}).uoms
      || (cho.find((x) => x.item === item) || {}).uoms || [];
  }

  // Dòng nào chưa có cách chia (phiếu cũ, hoặc lưu lúc site chưa migrate) thì đổi
  // TẠM ra thùng + hộp để đọc. Chỉ để hiển thị — số vào kho vẫn là tổng.
  function veUom(ct, tong, item) {
    return moTaUom(ct && ct.length ? ct : tachUom(tong, uomCua(item)));
  }

  // MỘT cặp cột cho cả màn: thủ kho làm việc với cột ĐẾM, người lập với cột LẬP.
  // Trộn hai cột (chi tiết của cột này, tổng của cột kia) là cách chắc chắn nhất để
  // ghi đè mất số thủ kho vừa đếm — cửa sổ nhập dựng ô TỪ chi tiết và bỏ qua tổng.
  const ctCua = (x) => (laThuKho ? x.dem_uom : x.lap_uom);
  const soCua = (x) => (laThuKho ? x.so_dem : x.so_lap);

  // Có chi tiết ĐVT thì server TÍNH LẠI tổng từ chi tiết, nên client phải giữ đúng
  // Σ đó — làm tròn ở đây là màn hình một số, sổ kho một số.
  const chotSo = (tong, ct) => (ct && ct.length
    ? Math.max(0, tong) : Math.max(0, Math.round(tong)));

  // D114: HSD của lô. Thủ kho gõ (x.hsd) > mặc định server (ngày phiếu + Shelf
  // Life) > tự tính cho dòng vừa thêm trên máy. Cả ba trống = duyệt bị chặn.
  const hsdMacDinh = (x) => x.hsd_goi_y || hsdTu(p.ngay,
    danhMuc.find((d) => d.item === x.item));
  const hsdCua = (x) => x.hsd || hsdMacDinh(x);
  function veHsd(x, i) {
    const h = hsdCua(x);
    if (!h) {
      return `<button type="button" class="sx-nk-hsd sx-nk-hsd-thieu" data-hsd="${i}">
        ⚠ Chưa có HSD — bấm để nhập</button>`;
    }
    return `<button type="button" class="sx-nk-hsd" data-hsd="${i}">
      <span>HSD ${esc(veNgayDu(h))} ✎</span>${
      x.hsd ? '' : '<span class="sx-nk-hsd-mac">mặc định</span>'}</button>`;
  }

  function ve() {
    box.innerHTML = rows.length
      ? rows.map((x, i) => {
        const lech = x.so_dem - x.so_lap;
        return `<div class="sx-vh-row">
          <div class="sx-vh-who">
            <div class="sx-vh-name">${esc(x.ten || tenSP(x.item))}${coBom(x) ? ''
              : ' <span class="sx-nobom-tag" title="Duyệt vẫn nhập kho được, nhưng '
                + 'CHƯA trừ nguyên liệu — ghi vào sổ nợ BOM">chưa có BOM</span>'}</div>
            <div class="sx-vh-meta">${esc(veUom(ctCua(x), soCua(x), x.item))
              || esc(x.dvt || '')}${laThuKho
              ? ` · phiếu ghi ${formatNumber(x.so_lap)}${
                lech ? ` · lệch ${lech > 0 ? '+' : ''}${formatNumber(lech)}` : ''}`
              : ''}</div>
            ${veHsd(x, i)}
          </div>
          <button type="button" class="sx-vh-sl${lech ? ' sx-cell-lech' : ''}"
            data-i="${i}">${formatNumber(soCua(x))}</button>
          <button type="button" class="sx-vh-del" data-del="${i}"
            aria-label="Bỏ dòng ${esc(x.ten || x.item)}">✕</button>
        </div>`;
      }).join('')
      : `<div class="sx-muted">Chưa ghi sản phẩm nào${
        danhMuc.length ? ' — bấm TÌM SẢN PHẨM hoặc quét hộp' : ''}.</div>`;

    box.querySelectorAll('.sx-vh-sl').forEach((b) => {
      const x = rows[Number(b.dataset.i)];
      b.addEventListener('click', () => openSoLuong({
        kicker: laThuKho ? 'Số thủ kho đếm' : 'Số chuyển sang kho',
        ten: x.ten || tenSP(x.item),
        uoms: uomCua(x.item),
        chi_tiet: ctCua(x),
        tong: soCua(x),
        onOk: (tong, ct) => {
          x.so_dem = chotSo(tong, ct);
          x.dem_uom = ct;
          // Người LẬP sửa số thì sửa cả hai; THỦ KHO sửa thì chỉ đụng số đếm —
          // giữ nguyên số người lập ghi, vì chỗ lệch mới là thứ đáng xem.
          if (!laThuKho) { x.so_lap = x.so_dem; x.lap_uom = ct; }
          ve();
        },
      }));
    });
    box.querySelectorAll('[data-hsd]').forEach((b) => {
      const x = rows[Number(b.dataset.hsd)];
      b.addEventListener('click', () => moHsd({
        ten: x.ten || tenSP(x.item), ngay: p.ngay, hsd: x.hsd, macDinh: hsdMacDinh(x),
        onOk: (v) => { x.hsd = v || null; ve(); },
      }));
    });
    box.querySelectorAll('[data-del]').forEach((b) => {
      b.addEventListener('click', () => { rows.splice(Number(b.dataset.del), 1); ve(); });
    });

    // Vẽ lại cả khung "vừa vào hộp" mỗi lần đổi dòng: mã nào đã ghi vào phiếu phải
    // thấy ngay là đã ghi, không thì thủ kho bấm lại lần hai tưởng là chưa ghi.
    const hopBox = container.querySelector('#sx-nk-cn');
    hopBox.innerHTML = cho.length
      ? veChoNhan(cho, rows.map((x) => ({ ...x, so_hien: soCua(x) })), true) : '';
    hopBox.querySelectorAll('[data-cn]').forEach((b) => {
      const d = cho.find((x) => x.item === b.dataset.cn);
      b.addEventListener('click', () => themTuVaoHop(d));
    });
    const btnTai = hopBox.querySelector('#sx-nk-tai');
    if (btnTai) {
      btnTai.addEventListener('click', async (e) => {
        e.currentTarget.disabled = true;
        try {
          await call('sx.api.khotp.tai_tu_vao_hop', { name: p.name });
          toast('Đã tải phần còn lại vào phiếu — đếm lại rồi sửa cho khớp.');
          refresh();
        } catch (err) { e.target.disabled = false; toastErr(err.message); }
      });
    }

    const tong = rows.reduce((a, x) => a + x.so_dem, 0);
    const lech = tong - rows.reduce((a, x) => a + x.so_lap, 0);
    container.querySelector('#sx-nk-tong').textContent = formatNumber(tong);
    container.querySelector('#sx-nk-lech').textContent =
      (laThuKho && lech) ? `lệch ${lech > 0 ? '+' : ''}${formatNumber(lech)} so với phiếu` : '';
  }

  // Danh mục KHÔNG bày sẵn: vài chục SKU trải hết ra thì phiếu đang ghi bị đẩy khỏi
  // màn hình. Bấm TÌM SẢN PHẨM mới xổ danh sách, có ô lọc.
  const btnTim = container.querySelector('#sx-nk-tim');
  // Chọn trong danh mục một mã đang "vừa vào hộp" → điền sẵn phần còn lại theo HSD.
  if (btnTim) {
    btnTim.addEventListener('click', () => moChonSP(danhMuc, rows, cho,
      (item, cn) => (cn ? themTuVaoHop(cn) : themItem(item))));
  }
  ve();


  // Mở số của MỘT dòng (đã có) để sửa.
  function suaDong(co) {
    openSoLuong({
      kicker: hsdCua(co) ? `Sửa số · HSD ${veNgayDu(hsdCua(co))}` : 'Sửa số',
      ten: co.ten || tenSP(co.item),
      uoms: uomCua(co.item),
      chi_tiet: ctCua(co),
      tong: soCua(co),
      onOk: (tong, ct) => {
        const n = chotSo(tong, ct);
        if (!n) { rows.splice(rows.indexOf(co), 1); ve(); return; }
        co.so_dem = n; co.dem_uom = ct;
        if (!laThuKho) { co.so_lap = n; co.lap_uom = ct; }
        ve();
      },
    });
  }

  // Thêm MỘT dòng mới (mã + HSD); `hsd` null = HSD mặc định của phiếu.
  // `goiY` là dòng bên bảng vào hộp: điền sẵn phần CÒN LẠI để thủ kho chỉ phải sửa khi
  // đếm thật lệch, chứ không phải gõ lại từ 0.
  function dongMoi(item, hsd, goiY, so) {
    const d = danhMuc.find((x) => x.item === item) || goiY || {};
    openSoLuong({
      kicker: goiY ? `Đã vào hộp ${formatNumber(so)} — chưa nhập kho`
        : `Thêm sản phẩm${hsd ? ` · HSD ${veNgayDu(hsd)}` : ''}`,
      ten: d.ten || item,
      uoms: d.uoms || [],
      chi_tiet: null,
      tong: goiY ? so : 0,
      onOk: (tong, ct) => {
        const n = chotSo(tong, ct);
        if (!n) return;
        rows.push({ item, ten: d.ten || item, dvt: d.dvt || '', hsd: hsd || null,
                    so_lap: n, so_dem: n, lap_uom: ct, dem_uom: ct });
        ve();
      },
    });
  }

  // W05 (D131): mỗi (mã, HSD) một dòng = một lô. Mã chưa có dòng → thêm dòng. Mã đã
  // có dòng → hỏi sửa dòng nào, hay thêm dòng HSD khác (hộp in HSD khác ngày).
  function themItem(item) {
    const cua = rows.filter((x) => x.item === item);
    if (!cua.length) { dongMoi(item, null); return; }
    const m = openModal({ kicker: 'Nhập kho', title: cua[0].ten || tenSP(item) });
    m.body.innerHTML = `<div class="sx-muted">Mã này đã có ${cua.length} dòng trên phiếu —
      mỗi HSD một dòng (một lô).</div>
      <div class="sx-vh-list">${cua.map((x, i) => `
        <button type="button" class="sx-nv-row" data-sua="${i}"
          style="flex-direction:row;align-items:center;justify-content:space-between;
          min-height:var(--sx-tap-lg)">
          <span class="sx-nv-ten">HSD ${esc(hsdCua(x) ? veNgayDu(hsdCua(x)) : '—')} ✎</span>
          <span class="sx-nv-qty">${formatNumber(soCua(x))}</span></button>`).join('')}</div>
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nk-hsd-khac">
        + DÒNG HSD KHÁC</button>`;
    m.body.querySelectorAll('[data-sua]').forEach((b) => b.addEventListener('click', () => {
      m.close(); suaDong(cua[Number(b.dataset.sua)]);
    }));
    m.body.querySelector('#sx-nk-hsd-khac').addEventListener('click', () => {
      m.close();
      moHsd({
        ten: cua[0].ten || tenSP(item), ngay: p.ngay, hsd: null,
        macDinh: hsdMacDinh({ item }),
        onOk: (v) => {
          const h = v || hsdMacDinh({ item });
          const trung = cua.find((x) => hsdCua(x) === h);
          if (trung) { toast('Đã có dòng HSD này — sửa số dòng đó.'); suaDong(trung); return; }
          dongMoi(item, h);
        },
      });
    });
  }

  // Bấm một mã ở "vừa vào hộp": thêm đủ các dòng theo HSD còn thiếu trên phiếu.
  function themTuVaoHop(d) {
    const chia = chiaCua(d);
    const chuaCo = chia.filter((g) => !rows.some((x) => x.item === d.item
      && hsdCua(x) === (g.hsd || hsdMacDinh({ item: d.item }))));
    if (!chuaCo.length) { themItem(d.item); return; }
    if (chuaCo.length === 1) { dongMoi(d.item, chuaCo[0].hsd, d, chuaCo[0].con); return; }
    chuaCo.forEach((g) => {
      const n = Math.floor(g.con);
      if (n > 0) {
        rows.push({ item: d.item, ten: d.ten, dvt: d.dvt || '', hsd: g.hsd || null,
                    so_lap: n, so_dem: n, lap_uom: null, dem_uom: null });
      }
    });
    toast(`Đã thêm ${chuaCo.length} dòng theo HSD — đếm lại từng dòng.`);
    ve();
  }

  // Guard null như mọi nút khác: nút này chỉ render khi danh mục TP không rỗng. Đổi
  // "Nhóm hàng là thành phẩm" trong SX Settings lúc đang có phiếu nháp là danh mục
  // rỗng mà phiếu vẫn còn -> bind thẳng là TypeError, cả màn đổ, thủ kho không duyệt
  // cũng không xoá được phiếu, mà phiếu thứ hai thì bị chặn tạo -> tắc hẳn.
  const btnQuet = container.querySelector('#sx-nk-quet');
  if (btnQuet) btnQuet.addEventListener('click', () => moQuet({
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
      lap_uom: x.lap_uom || null, dem_uom: x.dem_uom || null,
      hsd: x.hsd || null,
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
      message: `Xoá phiếu ${p.name}. Chưa có gì vào kho nên không phải thu hồi gì — `
        + 'lập lại phiếu mới ngay được.',
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
      // D114: lô vào kho phải có HSD — chặn ngay trên máy, khỏi đi một vòng server.
      const thieuHsd = rows.filter((x) => x.so_dem > 0 && !hsdCua(x));
      if (thieuHsd.length) {
        toastErr(`Chưa có HSD: ${thieuHsd.map((x) => x.ten || tenSP(x.item)).join(', ')}`
          + ' — bấm ô "Chưa có HSD" của dòng để nhập theo bao bì.');
        return;
      }
      // Số đang sửa trên màn PHẢI lưu trước khi duyệt, không thì duyệt số cũ.
      let moi;
      try { moi = await luu(); } catch (e) { toastErr(e.message); return; }
      // D97: nói trước dòng nào sẽ nhập tạm — thủ kho phải biết mình đang ghi
      // nợ nguyên liệu, không phải phát hiện sau qua một dòng lạ trên sổ nợ.
      const thieuBom = rows.filter((x) => x.so_dem > 0 && !coBom(x));
      // D101: nhận vượt số QC đã chấm vào hộp → vẫn duyệt, phần vượt ghi nợ.
      // Lấy từ kết quả VỪA LƯU, không từ lần tải trang: số vừa sửa đổi phần vượt.
      const vuot = (((moi && moi.dong) || p.dong) || []).filter((x) => Number(x.vuot) > 0);
      confirm2Step({
        title: 'Duyệt phiếu nhận',
        message: `Nhận ${formatNumber(tong)} sản phẩm vào ${p.kho_dich} theo đúng số `
          + 'đếm. Duyệt xong chứng từ kho được ghi; sửa thì phải huỷ phiếu.'
          + (thieuBom.length
            ? `\n\n⚠ ${thieuBom.length} mã CHƯA CÓ BOM (${thieuBom.map((x) => x.ten
              || tenSP(x.item)).join(', ')}): vẫn nhập kho, nhưng CHƯA trừ bột và `
              + 'bao bì — ghi vào sổ nợ BOM để quản lý hạch toán bù khi có định mức.'
            : '')
          + (vuot.length
            ? `\n\n⚠ Nhận VƯỢT số đã chấm vào hộp: ${vuot.map((x) => `${x.ten
              || tenSP(x.item)} +${formatNumber(x.vuot)}`).join(', ')}. Vẫn nhập kho; `
              + 'phần vượt ghi vào sổ nợ vào hộp để QC chấm bù (công nhân hoặc CÔNG NHẬT).'
            : ''),
        confirmLabel: 'DUYỆT',
        onConfirm: async () => {
          try {
            await call('sx.api.khotp.duyet_phieu', { name: p.name });
            toast(`Đã nhận ${formatNumber(tong)} sản phẩm vào kho.`
              + (thieuBom.length ? ` ${thieuBom.length} mã ghi vào sổ nợ BOM.` : '')
              + (vuot.length ? ` ${vuot.length} mã ghi nợ vào hộp.` : ''));
            refresh();
          } catch (e) { toastErr(e.message); throw e; }
        },
      });
    });
  }
}

// Cửa sổ chọn sản phẩm: lọc theo tên/mã, sản phẩm đã ghi tô màu kèm số
function moChonSP(danhMuc, rows, cho, onPick) {
  const m = openModal({ kicker: 'Nhập kho', title: 'Chọn sản phẩm' });
  m.body.innerHTML = `
    <input class="sx-textarea" id="sx-cs-tim" type="search" autocomplete="off"
      placeholder="Tìm trong ${danhMuc.length} sản phẩm…">
    <div id="sx-cs-ds"></div>
  `;
  const box = m.body.querySelector('#sx-cs-ds');
  const oTim = m.body.querySelector('#sx-cs-tim');
  // Mã vừa vào hộp đẩy lên đầu: giữa vài chục SKU, thứ xưởng vừa đóng xong mới là
  // thứ thủ kho đang cầm trên tay.
  const conCua = (item) => (cho || []).find((x) => x.item === item);
  function ve() {
    const q = oTim.value.toLowerCase().trim();
    const khop = danhMuc.filter((d) => !q || d.ten.toLowerCase().includes(q)
      || d.item.toLowerCase().includes(q))
      .slice()
      .sort((a, b) => (conCua(b.item) ? 1 : 0) - (conCua(a.item) ? 1 : 0));
    box.innerHTML = khop.length
      ? `<div class="sx-vh-list">${khop.map((d) => {
        const cua = rows.filter((x) => x.item === d.item);
        const co = cua.length ? { so_dem: cua.reduce((a, x) => a + x.so_dem, 0) } : null;
        const cn = conCua(d.item);
        return `<button type="button" class="sx-nv-row${co ? ' sx-nv-row-xong' : ''}"
            data-item="${esc(d.item)}" style="flex-direction:row;align-items:center;
            justify-content:space-between;min-height:var(--sx-tap-lg)">
            <span class="sx-nv-ten">${esc(d.ten)}${cn
          ? ` <b>· vào hộp còn ${formatNumber(cn.con)}</b>` : ''}</span>
            <span class="sx-nv-qty">${co ? formatNumber(co.so_dem) : (d.uoms && d.uoms.length > 1
          ? `${d.uoms.length} đơn vị` : esc(d.dvt || ''))}</span>
          </button>`;
      }).join('')}</div>`
      : '<div class="sx-muted">Không tìm thấy sản phẩm nào.</div>';
    box.querySelectorAll('[data-item]').forEach((b) => {
      b.addEventListener('click', () => {
        m.close();
        onPick(b.dataset.item, conCua(b.dataset.item));
      });
    });
  }
  oTim.addEventListener('input', ve);
  ve();
  return m;
}

// Phần "vừa vào hộp" của một mã chia theo HSD (W05) — server tính theo ngày đóng hộp.
// Phiếu cũ / server cũ không gửi `chia` thì coi cả phần còn lại là một nhóm.
function chiaCua(d) {
  return (d && d.chia && d.chia.length) ? d.chia : [{ hsd: null, con: (d || {}).con || 0 }];
}

// D114: cửa sổ nhập HSD. Ô ngày + nút nhanh theo tháng (HSD bánh thường tính
// tròn tháng từ ngày sản xuất) + "Theo mặc định" để bỏ số gõ tay.
export function moHsd({ ten, ngay, hsd, macDinh, onOk }) {
  const m = openModal({ kicker: `Hạn sử dụng · nhập ngày ${veNgayDu(ngay)}`, title: ten });
  m.body.innerHTML = `
    <div class="sx-muted">Ghi đúng HSD in trên bao bì. Ngày này thành hạn dùng của lô
      trong kho.</div>
    <input class="sx-textarea sx-nk-hsd-o" id="sx-hsd-o" type="date" min="${esc(congNgay(ngay, 1))}"
      value="${esc(hsd || macDinh || '')}">
    <div class="sx-nk-hsd-nhanh">${[3, 6, 9, 12].map((t) => `
      <button type="button" class="sx-btn" data-thang="${t}">+${t} tháng</button>`).join('')}
    </div>
    ${macDinh ? `<div class="sx-muted">Mặc định theo mã hàng: <b>${esc(veNgayDu(macDinh))}</b></div>` : ''}
    <div class="sx-warn-text" id="sx-hsd-loi" role="alert"></div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-hsd-ok">LƯU HSD</button>
    ${hsd && macDinh ? '<button type="button" class="sx-btn" id="sx-hsd-bo">Dùng mặc định</button>' : ''}
  `;
  const o = m.body.querySelector('#sx-hsd-o');
  m.body.querySelectorAll('[data-thang]').forEach((b) => b.addEventListener('click', () => {
    o.value = congThang(ngay, Number(b.dataset.thang));
  }));
  m.body.querySelector('#sx-hsd-ok').addEventListener('click', () => {
    const v = o.value;
    const loi = m.body.querySelector('#sx-hsd-loi');
    if (!v) { loi.textContent = 'Chọn một ngày.'; return; }
    if (v <= ngay) { loi.textContent = 'HSD phải sau ngày nhập.'; return; }
    m.close();
    onOk(v);
  });
  const bo = m.body.querySelector('#sx-hsd-bo');
  if (bo) bo.addEventListener('click', () => { m.close(); onOk(null); });
  return m;
}

// HSD mặc định từ một ngày + hạn dùng của mã hàng (D127): `han_dung_thang` theo bộ
// tự công bố (cộng tháng theo lịch), không có thì `han_dung` ngày (Shelf Life).
export function hsdTu(iso, d) {
  if (!iso || !d) return null;
  if (Number(d.han_dung_thang) > 0) return congThang(iso, Number(d.han_dung_thang));
  return congNgay(iso, d.han_dung);
}

// "2026-08-22" + n ngày -> ISO. Tính theo UTC để không lệch một ngày vì múi giờ.
export function congNgay(iso, n) {
  if (!iso || !(Number(n) > 0)) return null;
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + Number(n));
  return d.toISOString().slice(0, 10);
}

// + n tháng; ngày 31 sang tháng không có 31 thì lùi về cuối tháng (31/08 + 6 = 28/02).
export function congThang(iso, n) {
  const [y, mo, dd] = String(iso).slice(0, 10).split('-').map(Number);
  const tong = (mo - 1) + n;
  const ny = y + Math.floor(tong / 12);
  const nm = tong % 12;
  const cuoi = new Date(Date.UTC(ny, nm + 1, 0)).getUTCDate();
  return `${ny}-${String(nm + 1).padStart(2, '0')}-${String(Math.min(dd, cuoi)).padStart(2, '0')}`;
}

// "2027-02-28" -> "28/02/27"
export function veNgayDu(iso) {
  const d = String(iso || '').slice(0, 10).split('-');
  return d.length === 3 ? `${d[2]}/${d[1]}/${d[0].slice(2)}` : String(iso || '');
}

// "2026-08-22" -> "22/08" — người ở xưởng đọc ngày kiểu này, không đọc ISO
function veNgay(iso) {
  const d = String(iso || '').split('-');
  return d.length === 3 ? `${d[2]}/${d[1]}` : String(iso || '');
}

function veGanDay(ds) {
  if (!ds || !ds.length) return '';
  return `
    <div class="sx-field-label">Phiếu đã duyệt gần đây — bấm để xem / huỷ</div>
    <div class="sx-vh-list">${ds.map((g) => `
      <div class="sx-vh-row" data-phieu="${esc(g.name)}" role="button" tabindex="0"
        style="cursor:pointer">
        <div class="sx-vh-who">
          <div class="sx-vh-name">${esc(g.name)}</div>
          <div class="sx-vh-meta">${esc(veNgay(g.ngay))} · ${esc(g.nguoi_duyet || '')}${
            g.tong_lech ? ` · lệch ${g.tong_lech > 0 ? '+' : ''}${formatNumber(g.tong_lech)}` : ''}</div>
        </div>
        <span class="sx-nv-qty">${formatNumber(g.tong_dem)}</span>
      </div>`).join('')}</div>`;
}
