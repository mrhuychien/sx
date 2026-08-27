// Quét mã (D63, sửa lớn D77) — BẤM LÀ MỞ CAMERA NGAY.
//
// ═══ VÌ SAO KHÓ QUÉT MÃ VẠCH (D77) ═══
// Bốn nguyên nhân, sửa cả bốn:
//   1. KHÔNG XIN LẤY NÉT. Trình duyệt mở camera ở chế độ mặc định của máy, nhiều máy
//      Android để nét cố định -> mã vạch mờ, đọc mãi không ra. Nay xin
//      focusMode:'continuous' cả lúc mở lẫn sau khi có track, và cho BẤM VÀO KHUNG
//      để lấy nét lại đúng chỗ đang soi.
//   2. ĐỘ PHÂN GIẢI MẶC ĐỊNH. Trình duyệt hay trả 640×480. Vạch hẹp của EAN/Code128
//      ở 480p chỉ dày một hai điểm ảnh — QR thì còn đọc được, mã vạch thì thua.
//      Nay xin 1920×1080, máy yếu tự hạ xuống.
//   3. Ô NGẮM VUÔNG. Mã vạch thì rộng mà thấp; ô ngắm vuông dạy người ta lùi xa cho
//      vừa khung, mà lùi xa là vạch càng nhỏ. Nay ô ngắm rộng khi quét hộp.
//   4. TỐI. Trong xưởng thiếu sáng thì cảm biến tăng ISO -> nhiễu -> hỏng vạch.
//      Nay có nút bật đèn flash khi máy hỗ trợ.
//
// ═══ HAI BỘ GIẢI MÃ, CHỌN THEO MÁY — CẢ HAI ĐỀU ĐỌC ĐƯỢC MÃ VẠCH KẺ SỌC ═══
//   1. BarcodeDetector — có sẵn trong Chrome/Android. Nhanh nhất, chạy bằng máy.
//   2. zxing1d (đóng gói trong repo) — cho Safari/iPhone, nơi KHÔNG có
//      BarcodeDetector. Đọc EAN-13/8, UPC-A/E, Code128/39/93, ITF, Codabar và QR.
// Trước D78 bộ dự phòng là jsQR, mà jsQR CHỈ đọc QR — iPhone không quét nổi mã vạch
// trên hộp. Xưởng dùng iPhone, nên đó không phải hạn chế chấp nhận được.
// Nạp trễ (dynamic import) để máy Android không phải tải 184KB nó không dùng.
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

const CAM = {
  video: {
    facingMode: { ideal: 'environment' },
    width: { ideal: 1920 },
    height: { ideal: 1080 },
    // Máy nào không hiểu thì BỎ QUA nhánh advanced chứ không báo lỗi, nên xin thẳng.
    advanced: [{ focusMode: 'continuous' }],
  },
};

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

  // Ô ngắm theo thứ sắp quét: thẻ nhân viên là QR (vuông), hộp là mã vạch (rộng).
  const ngang = loai === 'sp';
  m.body.innerHTML = `
    <div class="sx-quet-khung" id="sx-quet-khung">
      <div class="sx-quet-tt" id="sx-quet-tt">Đang mở camera…</div>
    </div>
    <div class="sx-quet-hang" id="sx-quet-hang"></div>
    <div class="sx-quet-tt" id="sx-quet-bao">Đưa mã vào giữa khung.</div>
    <button type="button" class="sx-btn" id="sx-quet-tay">⌨ Gõ mã bằng tay</button>
  `;
  const khung = m.body.querySelector('#sx-quet-khung');
  const bao = m.body.querySelector('#sx-quet-bao');
  const hang = m.body.querySelector('#sx-quet-hang');

  let xong = false;
  function nhan(ma) {
    const key = String(ma || '').trim();
    if (!key || xong) return false;
    const gt = traBang(bang, key);
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

  batCamera({ khung, hang, tt: m.body.querySelector('#sx-quet-tt'), bao, nhan, ngang })
    .then((stop) => { dungLai = () => { stop(); document.removeEventListener('keydown', nghePhim); }; })
    .catch(() => { dungLai = () => document.removeEventListener('keydown', nghePhim); });

  return m;
}

// ───────────────────────────────────────────────── ống kính ──

/** Khả năng của track, hoặc {} nếu trình duyệt không cho hỏi. */
function khaNang(track) {
  try {
    return (track && track.getCapabilities && track.getCapabilities()) || {};
  } catch (e) {
    return {};
  }
}

function coNet(kn, che_do) {
  return !!(kn.focusMode && kn.focusMode.indexOf(che_do) >= 0);
}

async function apDung(track, nc) {
  try {
    await track.applyConstraints({ advanced: nc });
    return true;
  } catch (e) {
    return false;
  }
}

/** Lấy nét liên tục — thứ mà mặc định của trình duyệt KHÔNG bật. */
async function netLienTuc(track, kn) {
  if (!coNet(kn, 'continuous')) return false;
  return apDung(track, [{ focusMode: 'continuous' }]);
}

/**
 * Lấy nét vào ĐÚNG CHỖ vừa bấm (x, y trong [0,1] theo khung hình).
 *
 * Máy có pointsOfInterest thì chỉ thẳng điểm cần nét. Không có thì ép một nhịp
 * single-shot rồi trả về liên tục — chỉ riêng việc bắt ống kính chạy lại một vòng đã
 * gỡ được phần lớn trường hợp "nét chết ở vô cực".
 */
async function netTaiDiem(track, kn, x, y) {
  const nc = [];
  if (kn.pointsOfInterest) nc.push({ pointsOfInterest: [{ x, y }] });
  if (coNet(kn, 'single-shot')) nc.push({ focusMode: 'single-shot' });
  else if (coNet(kn, 'continuous')) nc.push({ focusMode: 'continuous' });
  if (!nc.length) return false;
  const ok = await apDung(track, nc);
  if (ok && coNet(kn, 'single-shot') && coNet(kn, 'continuous')) {
    // Nét một nhịp xong phải trả về liên tục, không thì mã kế tiếp lại mờ.
    setTimeout(() => netLienTuc(track, kn), 1200);
  }
  return ok;
}

/** Bật camera + vòng giải mã. Trả hàm dừng. */
async function batCamera({ khung, hang, tt, bao, nhan, ngang }) {
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
  const oNgam = el('div', `sx-quet-o-ngam${ngang ? ' sx-quet-o-ngang' : ''}`);
  khung.appendChild(oNgam);
  await video.play().catch(() => {});
  if (tt) tt.remove();

  let chay = true;
  const dung = () => {
    chay = false;
    stream.getTracks().forEach((t) => t.stop());
  };

  // ── ống kính: nét liên tục + bấm để nét lại + đèn ──
  const track = stream.getVideoTracks()[0];
  const kn = khaNang(track);
  const coNetGi = coNet(kn, 'continuous') || coNet(kn, 'single-shot') || !!kn.pointsOfInterest;
  await netLienTuc(track, kn);

  if (coNetGi) {
    khung.classList.add('sx-quet-net-duoc');
    khung.addEventListener('click', async (e) => {
      const o = khung.getBoundingClientRect();
      if (!o.width || !o.height) return;
      const x = Math.min(1, Math.max(0, (e.clientX - o.left) / o.width));
      const y = Math.min(1, Math.max(0, (e.clientY - o.top) / o.height));
      oNgam.classList.add('sx-quet-dang-net');
      setTimeout(() => oNgam.classList.remove('sx-quet-dang-net'), 700);
      await netTaiDiem(track, kn, x, y);
    });
  }

  if (kn.torch) {
    const den = el('button', 'sx-btn sx-quet-den');
    den.type = 'button';
    den.textContent = '💡 BẬT ĐÈN';
    let sang = false;
    den.addEventListener('click', async () => {
      const ok = await apDung(track, [{ torch: !sang }]);
      if (!ok) return;
      sang = !sang;
      den.textContent = sang ? '💡 TẮT ĐÈN' : '💡 BẬT ĐÈN';
      den.classList.toggle('sx-quet-den-sang', sang);
    });
    hang.appendChild(den);
  }

  // ── bộ giải mã ──
  const boDoc = await dungBoGiaiMa(video, oNgam, bao);
  if (boDoc.loi) {
    bao.innerHTML = esc(boDoc.loi);
    bao.className = 'sx-quet-tt sx-quet-loi';
  } else {
    bao.textContent = meoQuet(coNetGi, !!kn.torch);
  }
  const doc = boDoc.doc;

  // Soi mãi không ăn thì nhắc cách xoay xở, chứ đừng để người ta đứng đoán.
  const nhac = setTimeout(() => {
    if (!chay || bao.classList.contains('sx-quet-loi')) return;
    bao.textContent = 'Chưa đọc được? Đưa gần hơn cho mã kín ngang ô ngắm, '
      + (coNetGi ? 'bấm vào khung để lấy nét, ' : '')
      + (kn.torch ? 'bật đèn, ' : '') + 'hoặc bấm "Gõ mã bằng tay".';
  }, 7000);

  const vong = async () => {
    if (!chay) return;
    try {
      const ma = await doc();
      if (ma && nhan(ma)) { clearTimeout(nhac); return; }
    } catch (e) { /* khung lỗi -> thử khung sau */ }
    if (!chay) return;
    // requestVideoFrameCallback chạy đúng nhịp khung hình thật, không đọc lại một
    // khung hai lần như setTimeout mù.
    if (video.requestVideoFrameCallback) video.requestVideoFrameCallback(() => vong());
    else setTimeout(() => requestAnimationFrame(vong), 120);
  };
  if (video.requestVideoFrameCallback) video.requestVideoFrameCallback(() => vong());
  else requestAnimationFrame(vong);

  return () => { clearTimeout(nhac); dung(); };
}

function meoQuet(coNetGi, coDen) {
  const meo = [];
  if (coNetGi) meo.push('bấm vào khung để lấy nét');
  if (coDen) meo.push('bật đèn nếu tối');
  return 'Đưa mã vào giữa khung' + (meo.length ? ` — ${meo.join(', ')}.` : '.');
}

/**
 * Chọn bộ giải mã. Trả { doc, loi }.
 *
 * Cả hai đường đều đọc được mã vạch kẻ sọc — không còn máy nào chỉ quét được QR.
 */
async function dungBoGiaiMa(video, oNgam, bao) {
  if (typeof window.BarcodeDetector === 'function') {
    try {
      const det = new window.BarcodeDetector();
      return {
        doc: async () => {
          const ds = await det.detect(video);
          return ds && ds.length ? ds[0].rawValue : null;
        },
      };
    } catch (e) { /* máy khai có mà dựng không được -> rơi xuống zxing1d */ }
  }

  bao.textContent = 'Đang tải bộ đọc mã…';
  const { taoBoDoc } = await import('/assets/sx/sx/vendor/zxing1d.js');
  const docAnh = taoBoDoc();
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const doc = async () => {
    const W = video.videoWidth;
    const H = video.videoHeight;
    if (!W) return null;
    // CẮT ĐÚNG Ô NGẮM rồi mới đọc, thay vì thu nhỏ cả khung 1080p về 480px. Thu nhỏ
    // cả khung là ném đi đúng phần điểm ảnh của cái mã; cắt thì giữ được độ nét ở
    // vùng người ta đang chĩa vào.
    const { sx, sy, sw, sh } = vungNgam(
      W, H, video.getBoundingClientRect(), oNgam.getBoundingClientRect());
    const ti2 = Math.min(1, 720 / Math.max(sw, sh));
    canvas.width = Math.max(1, Math.round(sw * ti2));
    canvas.height = Math.max(1, Math.round(sh * ti2));
    ctx.drawImage(video, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
    const anh = ctx.getImageData(0, 0, canvas.width, canvas.height);
    return docAnh(anh.data, anh.width, anh.height);
  };

  return { doc, loi: '' };
}

/**
 * Tra mã trong bảng, có xử lý chuyện EAN-13 ↔ UPC-A.
 *
 * EAN-13 bắt đầu bằng 0 CHÍNH LÀ UPC-A: cùng một mã in trên hộp, hai cách viết.
 * Bộ đọc trả về dạng UPC-A 12 số ("036000291452") trong khi ERPNext thường lưu dạng
 * EAN-13 13 số ("0036000291452") — so chuỗi thẳng là không khớp, và người dùng chỉ
 * thấy "không nhận ra mã" trên một cái mã hoàn toàn hợp lệ.
 *
 * Chỉ nới đúng một chữ số 0 ở đầu, không nới lỏng gì thêm: quét sai người hay sai mã
 * hàng còn tệ hơn quét không ra.
 */
export function traBang(bang, key) {
  if (!bang || !key) return undefined;
  if (bang[key] !== undefined) return bang[key];
  if (/^\d{12}$/.test(key) && bang[`0${key}`] !== undefined) return bang[`0${key}`];
  if (/^0\d{12}$/.test(key) && bang[key.slice(1)] !== undefined) return bang[key.slice(1)];
  return undefined;
}

/**
 * Vùng khung hình ứng với Ô NGẮM đang hiện trên màn.
 *
 * Video vẽ bằng object-fit:cover nên khung hình bị cắt bớt MỘT chiều: quy toạ độ ô
 * ngắm về toạ độ khung hình phải trừ đúng phần bị cắt, không thì cắt lệch và đọc
 * vào chỗ trống. Trả về cả khung khi số đo chưa sẵn sàng (video chưa layout xong).
 *
 * @param {number} W,H  kích thước khung hình thật (videoWidth/Height)
 * @param {{left,top,width,height}} rC  ô video trên màn
 * @param {{left,top,width,height}} rO  ô ngắm trên màn
 */
export function vungNgam(W, H, rC, rO) {
  const ca = { sx: 0, sy: 0, sw: W, sh: H };
  if (!W || !H || !rC || !rO || !rC.width || !rC.height) return ca;
  const ti = Math.max(rC.width / W, rC.height / H);   // object-fit: cover
  const leX = (W * ti - rC.width) / 2;
  const leY = (H * ti - rC.height) / 2;
  const sx = Math.max(0, (rO.left - rC.left + leX) / ti);
  const sy = Math.max(0, (rO.top - rC.top + leY) / ti);
  const sw = Math.min(W - sx, rO.width / ti);
  const sh = Math.min(H - sy, rO.height / ti);
  return (sw < 8 || sh < 8) ? ca : { sx, sy, sw, sh };
}

/** Nút "quét" dùng chung. */
export function nutQuet({ ma_quet, loai, nhan = '⌗ Quét mã', title, kicker, onTim }) {
  const b = el('button', 'sx-btn sx-quet-nut');
  b.type = 'button';
  b.innerHTML = esc(nhan);
  b.addEventListener('click', () => moQuet({ ma_quet, loai, title, kicker, onTim }));
  return b;
}
