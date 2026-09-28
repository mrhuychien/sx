// Nút tài khoản trên header + menu (D96) — đứng cạnh nút chọn mùa.
//
// Vì sao cần: một điện thoại ở xưởng hay bị chuyền tay giữa hai QC. Trước D96
// không có chỗ nào trên màn hình nói ĐANG ĐĂNG NHẬP BẰNG AI, và không có nút
// đăng xuất — muốn đổi người phải xoá cookie. Kết quả là người sau ghi số dưới
// tên người trước, mà trong hồ sơ QC "ai ghi" là thứ auditor hỏi đầu tiên.
//
// Đăng xuất là chỗ duy nhất ở đây có thể làm hỏng dữ liệu: hàng chờ ngoại tuyến
// nằm trong trình duyệt chứ không nằm trong tài khoản. Nên còn thao tác chưa gửi
// thì KHÔNG cho đăng xuất trơn — gửi trước, hoặc chủ động bỏ qua hai bước xác nhận.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { openModal, confirm2Step } from '/assets/sx/sx/components/modal.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import {
  boHangChoCuaToi, guiHangCho, hangChoCuaToi,
} from '/assets/sx/sx/lib/api.js';

/** "Nguyễn Thị Hoa" → "HO": hai chữ đầu của TÊN (chữ cuối) — người Việt gọi
 *  nhau bằng tên, không bằng họ; "NG" thì nửa xưởng trùng nhau. */
export function chuVietTat(ten, user) {
  const tu = String(ten || '').trim().split(/\s+/).filter(Boolean);
  const goc = tu.length ? tu[tu.length - 1] : String(user || '?').split('@')[0];
  return goc.slice(0, 2).toUpperCase() || '?';
}

/** Tên đăng nhập để HIỆN: tài khoản tạo bằng số điện thoại thì chỉ hiện số —
 *  phần "@sx.local" là email giả, không ai cần đọc nó. */
export function tenDangNhap(user) {
  const u = String(user || '');
  const [dau] = u.split('@');
  return /^\+?\d{8,12}$/.test(dau) ? dau : u;
}

export function nutTaiKhoan(ctx, opts = {}) {
  const b = el('button', 'sx-icon-btn sx-tk-nut');
  b.type = 'button';
  b.id = 'sx-head-tk';
  b.textContent = chuVietTat(ctx.fullName, ctx.user);
  b.setAttribute('aria-label', `Tài khoản: ${ctx.fullName || ctx.user}`);
  b.title = ctx.fullName || ctx.user || '';
  b.addEventListener('click', () => moMenu(ctx, opts));
  return b;
}

export function moMenu(ctx, { xoaBoNho } = {}) {
  const m = openModal({ kicker: 'Tài khoản', title: ctx.fullName || ctx.user || '' });

  const dau = el('div', 'sx-tk-dau');
  dau.innerHTML = `
    <div class="sx-tk-avatar" aria-hidden="true">${esc(chuVietTat(ctx.fullName, ctx.user))}</div>
    <div class="sx-tk-info">
      <div class="sx-tk-user">${esc(tenDangNhap(ctx.user))}</div>
      <div class="sx-tk-vai">${(ctx.vaiTro || []).map((v) => `<span class="sx-tk-chip">${esc(v)}</span>`).join('')
        || '<span class="sx-muted">chưa có vai trò nào của portal</span>'}</div>
    </div>`;
  m.body.appendChild(dau);

  const ds = el('div', 'sx-tk-ds');
  const muc = (icon, ten, phu, fn, lop = '') => {
    const x = el('button', `sx-tk-muc ${lop}`.trim());
    x.type = 'button';
    x.innerHTML = `<span class="sx-tk-icon" aria-hidden="true">${icon}</span>
      <span class="sx-tk-muc-ten">${esc(ten)}${phu ? `<small>${esc(phu)}</small>` : ''}</span>`;
    x.addEventListener('click', fn);
    ds.appendChild(x);
    return x;
  };

  muc('🔑', 'Đổi mật khẩu', null, () => { window.location.href = '/update-password'; });
  if (ctx.deskAccess) {
    muc('🖥', 'Mở Desk ERPNext', 'màn quản trị đầy đủ', () => { window.location.href = '/app'; });
  }

  const cho = hangChoCuaToi().length;
  muc('🚪', 'Đăng xuất', cho ? `còn ${cho} thao tác chưa gửi trên máy này` : null,
    () => batDauDangXuat(m, xoaBoNho), 'sx-tk-thoat');

  m.body.appendChild(ds);
  return m;
}

function batDauDangXuat(menu, xoaBoNho) {
  const cho = hangChoCuaToi();
  if (!cho.length) { dangXuat(xoaBoNho); return; }

  // Còn số chưa gửi: đăng xuất trơn thì hoặc số đó nằm lại chờ người sau gửi
  // dưới tên họ (đã chặn trong queue.js, nhưng khi đó số nằm kẹt không ai gửi),
  // hoặc mất hẳn. Cả hai đều phải là LỰA CHỌN có ý thức, không phải tai nạn.
  menu.close();
  const loi = cho.filter((x) => x.loi).length;
  const m = openModal({ kicker: 'Đăng xuất', title: `Còn ${cho.length} thao tác chưa gửi` });
  const msg = el('div', 'sx-modal-msg');
  msg.textContent = `Số bạn đã gõ nhưng chưa lên server (mất mạng lúc ghi)${loi
    ? `, trong đó ${loi} bị server từ chối` : ''}. Gửi xong rồi hãy đăng xuất — `
    + 'đăng xuất bây giờ là bỏ chúng.';
  m.body.appendChild(msg);

  const gui = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'GỬI NGAY RỒI ĐĂNG XUẤT');
  gui.type = 'button';
  gui.disabled = !navigator.onLine;
  if (!navigator.onLine) gui.textContent = 'ĐANG MẤT MẠNG — CHƯA GỬI ĐƯỢC';
  gui.addEventListener('click', async () => {
    gui.disabled = true;
    try {
      await guiHangCho();
      const con = hangChoCuaToi();
      if (!con.length) { m.close(); dangXuat(xoaBoNho); return; }
      toastErr(`Còn ${con.length} thao tác chưa gửi được`
        + `${con.some((x) => x.loi) ? ' — có cái bị server từ chối, mở màn đó sửa trước' : ''}.`);
    } catch (e) { toastErr(e.message); } finally { gui.disabled = !navigator.onLine; }
  });
  m.body.appendChild(gui);

  const bo = el('button', 'sx-btn sx-btn-ghost sx-btn-big', `BỎ ${cho.length} THAO TÁC VÀ ĐĂNG XUẤT`);
  bo.type = 'button';
  bo.addEventListener('click', () => {
    m.close();
    confirm2Step({
      title: 'Bỏ thao tác chưa gửi',
      message: `${cho.length} thao tác sẽ bị xoá khỏi máy này và KHÔNG BAO GIỜ lên server. `
        + 'Số đó phải ghi lại từ đầu.',
      confirmLabel: `BỎ ${cho.length} THAO TÁC`,
      onConfirm: () => { boHangChoCuaToi(); dangXuat(xoaBoNho); },
    });
  });
  m.body.appendChild(bo);

  const o = el('button', 'sx-btn sx-btn-ghost sx-btn-big', 'Ở LẠI');
  o.type = 'button';
  o.addEventListener('click', () => m.close());
  m.body.appendChild(o);
}

async function dangXuat(xoaBoNho) {
  if (!navigator.onLine) {
    // Mất mạng thì server không huỷ được phiên, và trang /login cũng không tải
    // được — chuyển trang lúc này là ném người dùng ra màn lỗi trình duyệt.
    toastErr('Đang mất mạng — cần có mạng để đăng xuất.');
    return;
  }
  try {
    const res = await fetch('/api/method/logout', {
      method: 'POST',
      headers: { 'X-Frappe-CSRF-Token': (window.SX_CONTEXT || {}).csrfToken || '',
        Accept: 'application/json' },
    });
    if (!res.ok && res.status !== 401) throw new Error(`HTTP ${res.status}`);
  } catch (e) {
    toastErr('Chưa đăng xuất được — thử lại.');
    return;
  }
  // Xoá số liệu của người vừa đăng xuất khỏi máy: bản boot lưu để dùng khi mất
  // mạng chứa danh sách công nhân, phiếu ngày… Người sau mất mạng mà app bật lên
  // bằng số của người trước thì còn tệ hơn không bật được.
  try { if (xoaBoNho) xoaBoNho(); } catch (e) { /* không xoá được thì thôi */ }
  toast('Đã đăng xuất');
  window.location.href = '/login?redirect-to=%2Fsx';
}
