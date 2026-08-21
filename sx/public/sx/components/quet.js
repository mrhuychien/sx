// Quét mã (D57) — máy quét cầm tay HOẶC camera, cùng một cửa sổ.
//
// ═══ VÌ SAO ƯU TIÊN MÁY QUÉT CẦM TAY, KHÔNG PHẢI CAMERA ═══
// Máy quét USB/Bluetooth kiểu "keyboard wedge" gửi mã vào y như gõ phím rồi Enter.
// Trong xưởng nó thắng camera ở mọi mặt quan trọng: bấm cò là xong (không căn nét),
// ĐEO GĂNG dùng được, chói nắng hay tối đều đọc, không xin quyền, không cần thư
// viện. Camera chỉ là phương án khi chưa có máy — nên nó là tuỳ chọn, không mặc định.
//
// Vì vậy cửa sổ này LUÔN có một ô nhập đang focus: máy quét gõ thẳng vào đó, và
// người không có máy quét vẫn GÕ TAY được mã. Camera bật thêm nếu trình duyệt hỗ trợ.
//
// ═══ TRA CỨU Ở MÁY, KHÔNG GỌI SERVER ═══
// boot.ma_quet đã có sẵn bảng tra. Quét phải phản hồi tức thì — đợi mạng giữa xưởng
// là mất luôn cái lợi của việc quét — và app phải chạy được khi mất mạng (D37).

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { openModal } from '/assets/sx/sx/components/modal.js';

/** Có camera đọc mã được không (Chrome Android có BarcodeDetector; iOS thì không). */
export function coCamera() {
  return typeof window.BarcodeDetector === 'function'
    && !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

/**
 * Mở cửa sổ quét.
 *   loai: 'nv' | 'sp'  — tra trong bảng nào
 *   ma_quet: boot.ma_quet
 *   onTim(giaTri, maGoc) — quét trúng
 * Trả về modal để nơi gọi tự đóng nếu muốn.
 */
export function moQuet({ ma_quet, loai, title = 'Quét mã', kicker = '', onTim }) {
  const bang = (ma_quet && ma_quet[loai]) || {};
  const m = openModal({ title, kicker, onClose: () => dungCamera() });

  m.body.innerHTML = `
    <div class="sx-quet-o">
      <input class="sx-textarea sx-quet-input" id="sx-quet-in" autocomplete="off"
             inputmode="text" placeholder="Bấm cò máy quét, hoặc gõ mã rồi Enter">
    </div>
    <div class="sx-quet-tt" id="sx-quet-tt">Đang chờ quét…</div>
    <div id="sx-quet-cam"></div>
    <button type="button" class="sx-btn" id="sx-quet-dong">Đóng</button>
  `;
  const inp = m.body.querySelector('#sx-quet-in');
  const tt = m.body.querySelector('#sx-quet-tt');
  const camBox = m.body.querySelector('#sx-quet-cam');
  m.body.querySelector('#sx-quet-dong').addEventListener('click', () => m.close());

  let video = null;
  let stream = null;
  let dungVong = false;

  function dungCamera() {
    dungVong = true;
    if (stream) stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }

  function thu(ma) {
    const key = String(ma || '').trim();
    if (!key) return;
    const gt = bang[key];
    if (!gt) {
      // Mã lạ phải NÓI RÕ, không im lặng: người dùng sẽ quét đi quét lại một cái
      // thẻ hỏng mà không hiểu vì sao không ăn.
      tt.textContent = `Không nhận ra mã "${key}". Thẻ sai loại, hoặc người/sản phẩm này chưa có mã.`;
      tt.className = 'sx-quet-tt sx-quet-loi';
      inp.value = '';
      inp.focus();
      return;
    }
    dungCamera();
    m.close();
    if (onTim) onTim(gt, key);
  }

  // Máy quét HID kết thúc bằng Enter. Gõ tay cũng vậy.
  inp.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); thu(inp.value); }
  });
  setTimeout(() => inp.focus(), 50);

  if (!coCamera()) {
    camBox.innerHTML = '<div class="sx-muted">Máy này không đọc được mã bằng camera '
      + '— dùng máy quét cầm tay, hoặc gõ mã bằng tay.</div>';
    return m;
  }

  const btnCam = el('button', 'sx-btn');
  btnCam.type = 'button';
  btnCam.textContent = '📷 Bật camera quét';
  btnCam.addEventListener('click', async () => {
    btnCam.remove();
    video = el('video', 'sx-quet-video');
    video.setAttribute('playsinline', '');
    video.muted = true;
    camBox.appendChild(video);
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      });
      video.srcObject = stream;
      await video.play();
    } catch (e) {
      camBox.innerHTML = '<div class="sx-warn-text">Không mở được camera '
        + '(chưa cấp quyền, hoặc trang không chạy HTTPS). Dùng máy quét cầm tay '
        + 'hoặc gõ mã bằng tay.</div>';
      return;
    }
    const det = new window.BarcodeDetector();
    dungVong = false;
    const vong = async () => {
      if (dungVong || !stream) return;
      try {
        const ds = await det.detect(video);
        if (ds && ds.length) { thu(ds[0].rawValue); return; }
      } catch (e) { /* khung lỗi -> thử khung sau */ }
      requestAnimationFrame(vong);
    };
    requestAnimationFrame(vong);
    tt.textContent = 'Đưa mã vào khung hình…';
  });
  camBox.appendChild(btnCam);
  return m;
}

/** Nút "quét" dùng chung — trả về phần tử button đã gắn sự kiện. */
export function nutQuet({ ma_quet, loai, nhan = '⌗ Quét mã', title, kicker, onTim }) {
  const b = el('button', 'sx-btn sx-quet-nut');
  b.type = 'button';
  b.innerHTML = esc(nhan);
  b.addEventListener('click', () => moQuet({ ma_quet, loai, title, kicker, onTim }));
  return b;
}
