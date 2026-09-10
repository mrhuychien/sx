// Card Tài khoản portal (D81) — quản lý tạo tài khoản QC bằng SỐ ĐIỆN THOẠI.
//
//   Nhập số điện thoại (+ tên, + vai trò)  ->  app tự đặt mật khẩu và cấp mã QR
//   ->  IN THẺ  ->  đưa tận tay  ->  QC quét QR là vào thẳng portal.
//
// Mật khẩu và mã QR chỉ hiện ĐÚNG MỘT LẦN, ngay sau khi tạo. Đóng cửa sổ là mất —
// Frappe lưu mật khẩu đã băm nên không ai đọc lại được, kể cả app này. Cửa sổ kết quả
// nói thẳng điều đó và chỉ sẵn đường sửa (CẤP LẠI), chứ không cố chặn thao tác đóng:
// chặn được nút ✕ cũng không chặn được người ta khoá màn hình hay hết pin.

import { esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { moTrangInDangNhap } from '/assets/sx/sx/lib/inthe.js';

export async function render({ container, call }) {
  container.className = 'sx-card';
  container.innerHTML = '<div class="sx-muted">Đang tải…</div>';

  let d;
  try {
    d = await call('sx.api.nguoidung.danh_sach');
  } catch (e) {
    container.innerHTML = `<div class="sx-error-box">${esc(e.message)}</div>`;
    return;
  }
  const roles = d.roles || [];
  const rows = d.rows || [];

  container.innerHTML = `
    <div class="sx-field-label">Tài khoản portal</div>
    <div class="sx-muted">${rows.length} tài khoản · tạo bằng số điện thoại, app tự
      đặt mật khẩu và cấp QR đăng nhập.</div>
    <div class="sx-vh-timhang">
      <div class="sx-vh-tim-wrap">
        <span class="sx-vh-tim-icon" aria-hidden="true">⌕</span>
        <input class="sx-textarea sx-vh-search" id="sx-nd-tim" type="search"
               aria-label="Tìm tài khoản" placeholder="Tìm theo tên hoặc số">
      </div>
      <button type="button" class="sx-btn sx-btn-primary sx-quet-nut" id="sx-nd-them"
        >+ TẠO</button>
    </div>
    <div class="sx-vh-list" id="sx-nd-ds"></div>
  `;

  const box = container.querySelector('#sx-nd-ds');
  const oTim = container.querySelector('#sx-nd-tim');

  function ve() {
    const q = oTim.value.trim().toLowerCase();
    const ds = rows.filter((r) => !q
      || r.ten.toLowerCase().includes(q) || String(r.sdt).includes(q));
    box.innerHTML = ds.length
      ? ds.map((r, i) => `
        <div class="sx-vh-row${r.bat ? '' : ' sx-nd-khoa'}">
          <div class="sx-vh-who">
            <div class="sx-vh-name">${esc(r.ten)}${r.bat ? '' : ' · đã khoá'}</div>
            <div class="sx-vh-meta">${esc(r.sdt)} · ${esc(r.nhan_roles)}${
  r.lan_cuoi ? ` · vào lần cuối ${esc(veNgay(r.lan_cuoi))}` : ' · chưa vào lần nào'}</div>
          </div>
          <button type="button" class="sx-btn sx-quet-nut" data-cap="${i}"
            >CẤP LẠI</button>
          <button type="button" class="sx-vh-del" data-khoa="${i}"
            aria-label="${r.bat ? 'Khoá' : 'Mở'} ${esc(r.ten)}">${r.bat ? '⊘' : '↺'}</button>
        </div>`).join('')
      : `<div class="sx-muted">${rows.length
        ? 'Không tìm thấy ai khớp.'
        : 'Chưa có tài khoản nào — bấm TẠO.'}</div>`;

    box.querySelectorAll('[data-cap]').forEach((b) => {
      b.addEventListener('click', () => moCapLai(ds[Number(b.dataset.cap)]));
    });
    box.querySelectorAll('[data-khoa]').forEach((b) => {
      b.addEventListener('click', () => doiKhoa(ds[Number(b.dataset.khoa)]));
    });
  }
  oTim.addEventListener('input', ve);
  ve();

  // ── tạo mới ──────────────────────────────────────────────────────────
  container.querySelector('#sx-nd-them').addEventListener('click', () => {
    const m = openModal({ kicker: 'Tài khoản portal', title: 'Tạo tài khoản' });
    m.body.innerHTML = `
      <div class="sx-field-label">Số điện thoại</div>
      <input class="sx-textarea sx-quet-input" id="sx-nd-sdt" type="tel"
        inputmode="numeric" autocomplete="off" placeholder="0912345678">
      <div class="sx-field-label">Họ tên</div>
      <input class="sx-textarea" id="sx-nd-ten" autocomplete="off"
        placeholder="Nguyễn Thị Nga">
      <div class="sx-field-label">Vai trò</div>
      <div class="sx-sp-grid" id="sx-nd-vai">${roles.map((r, i) => `
        <button type="button" class="sx-sp-chip${i ? '' : ' sx-sp-chip-on'}"
          data-role="${esc(r.ma)}">${esc(r.ten)}</button>`).join('')}</div>
      <div class="sx-muted">Số điện thoại là TÊN ĐĂNG NHẬP. Mật khẩu do app đặt, hiện
        một lần ngay sau khi tạo — in thẻ trước khi đóng.</div>
      <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nd-ok"
        >TẠO TÀI KHOẢN</button>
    `;
    let role = roles.length ? roles[0].ma : 'SX Vao Hop';
    m.body.querySelectorAll('[data-role]').forEach((b) => {
      b.addEventListener('click', () => {
        role = b.dataset.role;
        m.body.querySelectorAll('[data-role]').forEach(
          (x) => x.classList.toggle('sx-sp-chip-on', x === b));
      });
    });

    const oSdt = m.body.querySelector('#sx-nd-sdt');
    const oTen = m.body.querySelector('#sx-nd-ten');
    // Gợi ý tên từ hồ sơ nhân viên: số đã có trong danh bạ công ty thì khỏi gõ lại,
    // mà gõ lại là chỗ sinh ra hai cách viết tên cho cùng một người.
    oSdt.addEventListener('change', async () => {
      if (!oSdt.value.trim() || oTen.value.trim()) return;
      try {
        const g = await call('sx.api.nguoidung.goi_y_ten', { sdt: oSdt.value.trim() });
        if (g && g.ten) oTen.value = g.ten;
      } catch (e) { /* không gợi ý được thì thôi, người dùng tự gõ */ }
    });

    m.body.querySelector('#sx-nd-ok').addEventListener('click', async (e) => {
      const sdt = oSdt.value.trim();
      if (!sdt) { toastErr('Nhập số điện thoại.'); return; }
      e.currentTarget.disabled = true;
      try {
        const r = await call('sx.api.nguoidung.tao_user', {
          sdt, ho_ten: oTen.value.trim(), role,
        });
        m.close();
        moKetQua(r, 'Đã tạo tài khoản');
        rows.unshift({
          user: r.user, ten: r.ten, sdt: r.sdt, roles: [r.role],
          nhan_roles: r.nhan_role, bat: true, lan_cuoi: null,
        });
        ve();
      } catch (err) { e.target.disabled = false; toastErr(err.message); }
    });
    setTimeout(() => oSdt.focus(), 50);
  });

  // ── cấp lại ──────────────────────────────────────────────────────────
  function moCapLai(r) {
    confirm2Step({
      title: 'Cấp lại thẻ',
      message: `Đặt MẬT KHẨU MỚI cho ${r.ten} (${r.sdt}) và cấp mã QR mới. `
        + 'Mật khẩu cũ ngừng dùng được ngay — người này phải nhận thẻ mới thì mới '
        + 'vào lại được.',
      confirmLabel: 'CẤP LẠI',
      onConfirm: async () => {
        try {
          const kq = await call('sx.api.nguoidung.cap_lai', { user: r.user });
          moKetQua({ ...kq, nhan_role: r.nhan_roles }, 'Đã cấp lại');
        } catch (e) { toastErr(e.message); throw e; }
      },
    });
  }

  function doiKhoa(r) {
    if (r.bat) {
      confirm2Step({
        title: 'Khoá tài khoản',
        message: `${r.ten} (${r.sdt}) sẽ không đăng nhập được nữa, và mã QR chưa `
          + 'dùng bị huỷ. Dữ liệu đã ghi vẫn giữ nguyên.',
        confirmLabel: 'KHOÁ',
        onConfirm: () => datKhoa(r, 0),
      });
    } else {
      datKhoa(r, 1);
    }
  }

  async function datKhoa(r, bat) {
    try {
      await call('sx.api.nguoidung.bat_tat', { user: r.user, bat });
      r.bat = !!bat;
      ve();
      toast(bat ? 'Đã mở lại tài khoản.' : 'Đã khoá tài khoản.');
    } catch (e) { toastErr(e.message); throw e; }
  }
}

/**
 * Cửa sổ kết quả — chỗ DUY NHẤT mật khẩu và mã QR hiện ra.
 *
 * Đóng là mất thật: Frappe lưu mật khẩu đã băm nên không ai đọc lại được, kể cả app
 * này. Cửa sổ vẫn có nút ✕ và vẫn đóng khi bấm ra ngoài (dùng chung openModal), nên
 * chỗ dựa không phải là chặn thao tác mà là NÓI RÕ trước, và chỉ sẵn đường sửa: đóng
 * nhầm thì bấm CẤP LẠI ở dòng của người đó, mất chưa tới mười giây.
 */
function moKetQua(r, tieuDe) {
  const m = openModal({ kicker: tieuDe, title: r.ten || r.sdt });
  m.body.innerHTML = `
    <div class="sx-warn-text">⚠ Mật khẩu và mã QR chỉ hiện MỘT LẦN, ngay bây giờ.
      Đóng cửa sổ là không xem lại được. Lỡ đóng thì bấm CẤP LẠI ở dòng của người
      này — mật khẩu mới, thẻ mới.</div>
    <div class="sx-vh-list">
      <div class="sx-vh-row"><div class="sx-vh-who">
        <div class="sx-vh-meta">Số điện thoại (tên đăng nhập)</div>
        <div class="sx-vh-name sx-nd-gt">${esc(r.sdt)}</div>
      </div></div>
      ${r.mat_khau ? `<div class="sx-vh-row"><div class="sx-vh-who">
        <div class="sx-vh-meta">Mật khẩu</div>
        <div class="sx-vh-name sx-nd-gt">${esc(r.mat_khau)}</div>
      </div></div>` : ''}
      <div class="sx-vh-row"><div class="sx-vh-who">
        <div class="sx-vh-meta">Mã QR đăng nhập${
  r.het_han ? ` · hết hạn ${esc(veNgay(r.het_han))}` : ''}</div>
        <div class="sx-vh-meta">Dùng được MỘT lần, cho lần đăng nhập đầu tiên.</div>
      </div></div>
    </div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-nd-in"
      >⎙ IN THẺ ĐĂNG NHẬP</button>
    <button type="button" class="sx-btn" id="sx-nd-chep">Chép nội dung thẻ</button>
    <button type="button" class="sx-btn" id="sx-nd-xong">Tôi đã lưu — đóng</button>
  `;

  m.body.querySelector('#sx-nd-in').addEventListener('click', () => {
    if (!moTrangInDangNhap([r])) {
      toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi bấm lại, '
        + 'hoặc bấm "Chép nội dung thẻ".');
    }
  });

  m.body.querySelector('#sx-nd-chep').addEventListener('click', async () => {
    const chu = [
      r.ten || '', `Số điện thoại: ${r.sdt}`,
      r.mat_khau ? `Mật khẩu: ${r.mat_khau}` : '',
      `Link đăng nhập (một lần): ${r.link || ''}`,
    ].filter(Boolean).join('\n');
    try {
      await navigator.clipboard.writeText(chu);
      toast('Đã chép. Dán vào chỗ an toàn, đừng gửi qua nhóm chat chung.');
    } catch (e) {
      toastErr('Máy không cho chép tự động — bấm IN THẺ, hoặc chép tay.');
    }
  });

  m.body.querySelector('#sx-nd-xong').addEventListener('click', () => {
    confirm2Step({
      title: 'Đóng cửa sổ',
      message: 'Mật khẩu và mã QR sẽ không xem lại được. Đã in hoặc chép rồi chứ?',
      confirmLabel: 'ĐÃ LƯU — ĐÓNG',
      onConfirm: () => { m.close(); },
    });
  });
  return m;
}

/** "2026-09-24 15:00:00" -> "24/09" */
function veNgay(iso) {
  const d = String(iso || '').slice(0, 10).split('-');
  return d.length === 3 ? `${d[2]}/${d[1]}` : String(iso || '');
}
