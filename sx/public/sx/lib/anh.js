// Nén ảnh NGAY TRÊN MÁY trước khi gửi lên server (D109).
//
// Ảnh điện thoại thường 3–6 MB, 4000 px. Gửi nguyên là: chờ lâu trên 4G giữa
// xưởng, ổ server đầy dần theo năm, và mở lại tủ mẫu thì tải chậm. Ảnh lưu mẫu chỉ
// cần đủ rõ để nhận ra sản phẩm, lô in trên bao bì — 1600 px, JPEG ~300 KB là đủ.
//
// Cách nén: thu cạnh dài về CANH_MAX, rồi hạ chất lượng JPEG từng bậc tới khi dưới
// TOI_DA; vẫn chưa đạt thì thu nhỏ thêm. Phần quyết định (kích thước, bậc chất
// lượng) là hàm THUẦN để test được không cần trình duyệt; phần vẽ canvas mỏng.

export const CANH_MAX = 1600;        // px — đọc được chữ HSD in trên bao bì
export const TOI_DA = 350 * 1024;    // byte — mục tiêu sau nén
const CL_DAU = 0.82;
const CL_THAP = 0.5;
const CANH_SAN = 640;                // không thu nhỏ hơn mức này: mất chữ HSD

/** Kích thước mới giữ tỉ lệ, cạnh dài ≤ canhMax. Ảnh nhỏ hơn thì giữ nguyên. */
export function tinhKichThuoc(w, h, canhMax = CANH_MAX) {
  const dai = Math.max(w, h);
  if (!dai || dai <= canhMax) return { w, h };
  const k = canhMax / dai;
  return { w: Math.max(1, Math.round(w * k)), h: Math.max(1, Math.round(h * k)) };
}

/**
 * Vòng nén: `maHoa(w, h, chatLuong)` → Promise<Blob>. Trả {blob, w, h, chatLuong}.
 * Hạ chất lượng 0.82 → 0.5 (bước 0.08); vẫn quá TOI_DA thì thu cạnh 80% rồi lại.
 * Dừng ở CANH_SAN dù chưa đạt — ảnh to một chút còn hơn ảnh không đọc được chữ.
 */
export async function nenVongLap(maHoa, w0, h0, { toiDa = TOI_DA, canhMax = CANH_MAX } = {}) {
  let { w, h } = tinhKichThuoc(w0, h0, canhMax);
  for (;;) {
    for (let q = CL_DAU; q >= CL_THAP - 1e-9; q -= 0.08) {
      const blob = await maHoa(w, h, Math.round(q * 100) / 100);
      if (blob.size <= toiDa) return { blob, w, h, chatLuong: Math.round(q * 100) / 100 };
    }
    const dai = Math.max(w, h);
    if (dai * 0.8 < CANH_SAN) {
      return { blob: await maHoa(w, h, CL_THAP), w, h, chatLuong: CL_THAP };
    }
    w = Math.round(w * 0.8);
    h = Math.round(h * 0.8);
  }
}

async function docAnh(file) {
  // createImageBitmap tự xoay theo EXIF — ảnh chụp dọc không bị nằm ngang.
  if (window.createImageBitmap) {
    try { return await createImageBitmap(file, { imageOrientation: 'from-image' }); } catch (e) { /* rơi xuống */ }
  }
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Nén một File ảnh. Trả {blob, base64, w, h, truoc, sau}. */
export async function nenAnh(file, opts = {}) {
  const goc = await docAnh(file);
  const w0 = goc.width || goc.naturalWidth;
  const h0 = goc.height || goc.naturalHeight;
  const canvas = document.createElement('canvas');
  const maHoa = (w, h, q) => new Promise((ok, loi) => {
    canvas.width = w;
    canvas.height = h;
    const g = canvas.getContext('2d');
    g.fillStyle = '#fff';               // PNG trong suốt → nền trắng, không thành đen
    g.fillRect(0, 0, w, h);
    g.drawImage(goc, 0, 0, w, h);
    canvas.toBlob((b) => (b ? ok(b) : loi(new Error('Không nén được ảnh.'))), 'image/jpeg', q);
  });
  const kq = await nenVongLap(maHoa, w0, h0, opts);
  if (goc.close) goc.close();
  const base64 = await new Promise((ok, loi) => {
    const r = new FileReader();
    r.onload = () => ok(String(r.result).split(',')[1]);
    r.onerror = () => loi(new Error('Không đọc được ảnh đã nén.'));
    r.readAsDataURL(kq.blob);
  });
  return { ...kq, base64, truoc: file.size, sau: kq.blob.size };
}

export function kb(n) {
  return n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1).replace('.', ',')} MB`
    : `${Math.max(1, Math.round(n / 1024))} KB`;
}
