// Quét mã (D63) — BẤM LÀ MỞ CAMERA NGAY.
//
// ═══ HAI BỘ GIẢI MÃ, CHỌN THEO MÁY ═══
//   1. BarcodeDetector — có sẵn trong Chrome/Android. Nhanh nhất, chạy bằng máy.
//   2. jsQR (đóng gói trong repo) — cho Safari/iPhone, nơi KHÔNG có BarcodeDetector.
// Nạp jsQR trễ (dynamic import) để máy Android không phải tải 250KB nó không dùng.
//
// ═══ VẪN GIỮ MÁY QUÉT CẦM TAY ═══
// Máy quét USB/Bluetooth kiểu keyboard wedge gõ mã vào như bàn phím rồi Enter.
// Bắt bằng cách nghe phím ở cấp DOCUMENT chứ không focus vào ô nhập nào — focus ô
// nhập trên điện thoại là bật bàn phím ảo che mất nửa màn hình, đúng lúc đang soi
// camera. Người không có máy quét bấm "Gõ tay" thì mới hiện ô nhập.
//
// ═══ TRA CỨU Ở MÁY ═══
// boot.ma_quet đã có sẵn bảng tra. Quét phải phản hồi tức thì — đợi mạng giữa xưởng
// là mất luôn cái lợi của việc quét — và app phải chạy được khi mất mạng (D37).

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { openModal } from '/assets/sx/sx/components/modal.js';

const CAM = { video: { facingMode: { ideal: 'environment' } } };

export function coCamera() {
  return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
}

/**
 * Mở cửa sổ quét, camera bật ngay.
 *   loai: 'nv' | 'sp' — tra trong bảng nào của boot.ma_quet
 *   onTim(giaTri, maGoc)
 */
export function moQuet({ ma_quet, loai, title = 'Quét mã', kicker = '', onTim }) {
  const bang = (ma_quet && ma_quet[loai]) || {};
  let dungLai = () => {};
  const m = openModal({ title, kicker, onClose: () => dungLai() });

  m.body.innerHTML = `
    <div class="sx-quet-khung" id="sx-quet-khung">
      <div class="sx-quet-tt" id="sx-quet-tt">Đang mở camera…</div>
    </div>
    <div class="sx-quet-tt" id="sx-quet-bao">Đưa mã vào giữa khung.</div>
    <button type="button" class="sx-btn" id="sx-quet-tay">⌨ Gõ mã bằng tay</button>
  `;
  const khung = m.body.querySelector('#sx-quet-khung');
  const bao = m.body.querySelector('#sx-quet-bao');

  let xong = false;
  function nhan(ma) {
    const key = String(ma || '').trim();
    if (!key || xong) return false;
    const gt = bang[key];
    if (!gt) {
      // Mã lạ phải NÓI RÕ: im lặng thì người ta quét đi quét lại một thẻ hỏng mà
      // không hiểu vì sao không ăn.
      bao.textContent = `Không nhận ra mã "${key}". Thẻ sai loại, hoặc chưa có mã này.`;
      bao.className = 'sx-quet-tt sx-quet-loi';
      return false;
    }
    xong = true;
    try { navigator.vibrate && navigator.vibrate(60); } catch (e) { /* máy không rung */ }
    dungLai();
    m.close();
    if (onTim) onTim(gt, key);
    return true;
  }

  // ── máy quét cầm tay: nghe phím ở document, KHÔNG focus ô nào ──
  let dem = '';
  let lucCuoi = 0;
  const nghePhim = (e) => {
    const gio = Date.now();
    if (gio - lucCuoi > 120) dem = '';   // gõ tay người thì chậm hơn nhiều
    lucCuoi = gio;
    if (e.key === 'Enter') {
      if (dem.length >= 3) { e.preventDefault(); nhan(dem); }
      dem = '';
      return;
    }
    if (e.key.length === 1) dem += e.key;
  };
  document.addEventListener('keydown', nghePhim);

  m.body.querySelector('#sx-quet-tay').addEventListener('click', (e) => {
    e.currentTarget.remove();
    const o = el('input', 'sx-textarea sx-quet-input');
    o.setAttribute('autocomplete', 'off');
    o.placeholder = 'Gõ mã rồi Enter';
    o.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') { ev.preventDefault(); ev.stopPropagation(); nhan(o.value); }
    });
    m.body.insertBefore(o, bao);
    o.focus();
  });

  batCamera(khung, m.body.querySelector('#sx-quet-tt'), bao, nhan)
    .then((stop) => { dungLai = () => { stop(); document.removeEventListener('keydown', nghePhim); }; })
    .catch(() => { dungLai = () => document.removeEventListener('keydown', nghePhim); });

  return m;
}

/** Bật camera + vòng giải mã. Trả hàm dừng. */
async function batCamera(khung, tt, bao, nhan) {
  if (!coCamera()) {
    khung.innerHTML = '<div class="sx-quet-tt sx-quet-loi">Máy này không mở được '
      + 'camera. Dùng máy quét cầm tay, hoặc bấm "Gõ mã bằng tay".</div>';
    return () => {};
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia(CAM);
  } catch (e) {
    // Nói đúng nguyên nhân: từ chối quyền và không chạy HTTPS là hai lỗi khác nhau,
    // mà cách sửa cũng khác nhau.
    const ly_do = (e && e.name === 'NotAllowedError')
      ? 'Bạn đã từ chối quyền camera. Vào cài đặt trình duyệt bật lại cho trang này.'
      : (!window.isSecureContext
        ? 'Trang không chạy HTTPS nên trình duyệt chặn camera.'
        : 'Không mở được camera (máy đang bận, hoặc không có camera sau).');
    khung.innerHTML = `<div class="sx-quet-tt sx-quet-loi">${esc(ly_do)}<br>`
      + 'Dùng máy quét cầm tay, hoặc bấm "Gõ mã bằng tay".</div>';
    throw e;
  }

  const video = el('video', 'sx-quet-video');
  video.setAttribute('playsinline', '');
  video.setAttribute('muted', '');
  video.muted = true;
  video.srcObject = stream;
  khung.innerHTML = '';
  khung.appendChild(video);
  khung.appendChild(el('div', 'sx-quet-o-ngam'));
  await video.play().catch(() => {});
  if (tt) tt.remove();

  let chay = true;
  const dung = () => {
    chay = false;
    stream.getTracks().forEach((t) => t.stop());
  };

  // Chrome/Android: BarcodeDetector. Còn lại: jsQR nạp trễ.
  let doc;
  if (typeof window.BarcodeDetector === 'function') {
    const det = new window.BarcodeDetector();
    doc = async () => {
      const ds = await det.detect(video);
      return ds && ds.length ? ds[0].rawValue : null;
    };
  } else {
    bao.textContent = 'Đang tải bộ đọc mã…';
    const { default: jsQR } = await import('/assets/sx/sx/vendor/jsqr.js');
    bao.textContent = 'Đưa mã vào giữa khung.';
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    doc = async () => {
      const w = video.videoWidth;
      if (!w) return null;
      // Thu nhỏ về ~480px rồi mới đọc: đọc thẳng khung 1080p tốn gấp mấy lần thời
      // gian mà không đọc thêm được mã nào.
      const ti = Math.min(1, 480 / w);
      canvas.width = Math.round(w * ti);
      canvas.height = Math.round(video.videoHeight * ti);
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const anh = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const kq = jsQR(anh.data, anh.width, anh.height, { inversionAttempts: 'dontInvert' });
      return kq ? kq.data : null;
    };
  }

  const vong = async () => {
    if (!chay) return;
    try {
      const ma = await doc();
      if (ma && nhan(ma)) return;
    } catch (e) { /* khung lỗi -> thử khung sau */ }
    if (chay) setTimeout(() => requestAnimationFrame(vong), 120);
  };
  requestAnimationFrame(vong);
  return dung;
}

/** Nút "quét" dùng chung. */
export function nutQuet({ ma_quet, loai, nhan = '⌗ Quét mã', title, kicker, onTim }) {
  const b = el('button', 'sx-btn sx-quet-nut');
  b.type = 'button';
  b.innerHTML = esc(nhan);
  b.addEventListener('click', () => moQuet({ ma_quet, loai, title, kicker, onTim }));
  return b;
}
