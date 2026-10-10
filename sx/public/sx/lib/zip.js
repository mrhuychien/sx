// Đọc tệp .zip ngay trên trình duyệt (D180) — để Ban ISO chọn thẳng tai_lieu_pdf.zip thay vì giải nén rồi chọn cả
// trăm tệp. Không thư viện ngoài: đọc mục lục cuối tệp (central directory), giải nén từng tệp khi cần bằng
// DecompressionStream('deflate-raw') của trình duyệt. Không đọc được (ZIP64, mã hoá, trình duyệt quá cũ) → báo lỗi
// rõ để người dùng giải nén rồi chọn các tệp như cũ.

const KY_CUOI = 0x06054b50;      // End of central directory
const KY_MUC = 0x02014b50;       // một mục trong central directory
const KY_TEP = 0x04034b50;       // local file header

/** Tên tệp không kèm thư mục ("tai_lieu_pdf/QT.01.pdf" → "QT.01.pdf"). */
export const tenGoc = (ten) => String(ten || '').split(/[\\/]/).pop();

/** [{ten (đường dẫn trong zip), co (byte sau giải nén), lay: () => Promise<Blob>}] — thư mục bị bỏ. */
export async function docZip(tep) {
  const buf = new Uint8Array(await tep.arrayBuffer());
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  let cuoi = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 22 - 0xffff); i -= 1) {
    if (dv.getUint32(i, true) === KY_CUOI) { cuoi = i; break; }
  }
  if (cuoi < 0) throw new Error(`${tep.name || 'Tệp'} không phải tệp .zip`);
  const so = dv.getUint16(cuoi + 10, true);
  let p = dv.getUint32(cuoi + 16, true);
  if (so === 0xffff || p === 0xffffffff) throw new Error('Tệp .zip quá lớn (ZIP64) — giải nén rồi chọn các tệp PDF');
  const giaiMa = new TextDecoder('utf-8');
  const ra = [];
  for (let k = 0; k < so; k += 1) {
    if (p + 46 > buf.length || dv.getUint32(p, true) !== KY_MUC) throw new Error('Tệp .zip hỏng (mục lục)');
    const co = dv.getUint16(p + 8, true);
    const kieu = dv.getUint16(p + 10, true);
    const nen = dv.getUint32(p + 20, true);
    const goc = dv.getUint32(p + 24, true);
    const lt = dv.getUint16(p + 28, true);
    const ten = giaiMa.decode(buf.subarray(p + 46, p + 46 + lt));
    const dau = dv.getUint32(p + 42, true);
    p += 46 + lt + dv.getUint16(p + 30, true) + dv.getUint16(p + 32, true);
    if (ten.endsWith('/') || ten.endsWith('\\')) continue;                     // thư mục
    if (co & 1) throw new Error(`${ten}: tệp .zip có mật khẩu — giải nén rồi chọn các tệp PDF`);
    if (kieu !== 0 && kieu !== 8) throw new Error(`${ten}: kiểu nén ${kieu} không đọc được — giải nén rồi chọn tệp`);
    ra.push({
      ten,
      co: goc,
      lay: async () => {
        if (dv.getUint32(dau, true) !== KY_TEP) throw new Error(`${ten}: tệp .zip hỏng`);
        const tu = dau + 30 + dv.getUint16(dau + 26, true) + dv.getUint16(dau + 28, true);
        const tho = new Blob([buf.subarray(tu, tu + nen)]);
        if (kieu === 0) return tho;
        if (typeof DecompressionStream === 'undefined') {
          throw new Error('Trình duyệt này không giải nén được .zip — cập nhật trình duyệt, hoặc giải nén rồi chọn tệp');
        }
        return new Response(tho.stream().pipeThrough(new DecompressionStream('deflate-raw'))).blob();
      },
    });
  }
  return ra;
}
