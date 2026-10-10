// Đọc tệp .zip ngay trên trình duyệt (D180) — để Ban ISO chọn thẳng tệp zip thay vì giải nén rồi chọn cả trăm tệp.
// Không thư viện ngoài: đọc mục lục cuối tệp (central directory), giải nén từng tệp khi cần bằng
// DecompressionStream('deflate-raw') của trình duyệt. D182: đọc cả zip ZIP64, zip có dữ liệu chèn trước (tự giải nén),
// tên tệp không đánh dấu UTF-8 (zip của Windows — đọc theo bảng mã Windows tiếng Việt); bỏ tệp rác __MACOSX/, ._x,
// .DS_Store, Thumbs.db. Zip mã hoá / kiểu nén lạ / trình duyệt quá cũ → báo lỗi rõ để giải nén rồi chọn các tệp.

const KY_CUOI = 0x06054b50;      // End of central directory
const KY_CUOI64 = 0x06064b50;    // ZIP64 end of central directory record
const KY_DINH64 = 0x07064b50;    // ZIP64 end of central directory locator
const KY_MUC = 0x02014b50;       // một mục trong central directory
const KY_TEP = 0x04034b50;       // local file header
const HET32 = 0xffffffff;

const u64 = (dv, i) => dv.getUint32(i, true) + dv.getUint32(i + 4, true) * 0x100000000;

/** Tên tệp không kèm thư mục ("tai_lieu_pdf/QT.01.pdf" → "QT.01.pdf"). */
export const tenGoc = (ten) => String(ten || '').split(/[\\/]/).pop();

/** Tệp rác máy Mac / Windows bỏ vào zip — không phải tài liệu. */
export const laRac = (ten) => /(^|[\\/])__MACOSX[\\/]/.test(String(ten || '')) || tenGoc(ten).startsWith('.')
  || /^(thumbs\.db|desktop\.ini)$/i.test(tenGoc(ten));

const UTF8 = new TextDecoder('utf-8', { fatal: true });
let WIN = null;
// tên về dạng dựng sẵn (NFC): zip của máy Mac và bảng mã Windows tiếng Việt ghi dấu thanh bằng ký tự tổ hợp
const docTen = (b) => {
  let t;
  try { t = UTF8.decode(b); } catch (e) {
    try { WIN = WIN || new TextDecoder('windows-1258'); } catch (e2) { WIN = new TextDecoder('latin1'); }
    t = WIN.decode(b);
  }
  return t.normalize('NFC');
};

/** [{ten (đường dẫn trong zip), co (byte sau giải nén), lay: () => Promise<Blob>}] — bỏ thư mục, tệp rác. */
export async function docZip(tep) {
  const buf = new Uint8Array(await tep.arrayBuffer());
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  let cuoi = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 22 - 0xffff); i -= 1) {
    if (dv.getUint32(i, true) === KY_CUOI) { cuoi = i; break; }
  }
  if (cuoi < 0) throw new Error(`${tep.name || 'Tệp'} không phải tệp .zip`);
  let so = dv.getUint16(cuoi + 10, true);
  let coMucLuc = dv.getUint32(cuoi + 12, true);
  let p = dv.getUint32(cuoi + 16, true);
  let hetMucLuc = cuoi;                                     // mục lục nằm ngay trước khối cuối
  if (so === 0xffff || coMucLuc === HET32 || p === HET32) {
    const d = cuoi - 20;
    const r = d >= 0 && dv.getUint32(d, true) === KY_DINH64 ? u64(dv, d + 8) : -1;
    if (r < 0 || r + 56 > buf.length || dv.getUint32(r, true) !== KY_CUOI64) throw new Error('Tệp .zip hỏng (ZIP64)');
    so = u64(dv, r + 32);
    coMucLuc = u64(dv, r + 40);
    p = u64(dv, r + 48);
    hetMucLuc = r;
  }
  // zip có dữ liệu chèn trước (tệp tự giải nén, zip ghép): vị trí ghi trong tệp lệch đi — tính lại từ cuối
  let lech = 0;
  if (p + 4 > buf.length || dv.getUint32(p, true) !== KY_MUC) {
    const p2 = hetMucLuc - coMucLuc;
    if (so && (p2 < 0 || dv.getUint32(p2, true) !== KY_MUC)) throw new Error('Tệp .zip hỏng (mục lục)');
    lech = p2 - p;
    p = p2;
  }
  const ra = [];
  for (let k = 0; k < so; k += 1) {
    if (p + 46 > buf.length || dv.getUint32(p, true) !== KY_MUC) throw new Error('Tệp .zip hỏng (mục lục)');
    const co = dv.getUint16(p + 8, true);
    const kieu = dv.getUint16(p + 10, true);
    let nen = dv.getUint32(p + 20, true);
    let goc = dv.getUint32(p + 24, true);
    const lt = dv.getUint16(p + 28, true);
    const lp = dv.getUint16(p + 30, true);
    let dau = dv.getUint32(p + 42, true);
    const ten = docTen(buf.subarray(p + 46, p + 46 + lt));
    if (goc === HET32 || nen === HET32 || dau === HET32) {  // ZIP64: số thật nằm ở trường phụ 0x0001
      for (let q = p + 46 + lt; q + 4 <= p + 46 + lt + lp;) {
        const id = dv.getUint16(q, true);
        const n = dv.getUint16(q + 2, true);
        if (id === 1) {
          let j = q + 4;
          if (goc === HET32) { goc = u64(dv, j); j += 8; }
          if (nen === HET32) { nen = u64(dv, j); j += 8; }
          if (dau === HET32) dau = u64(dv, j);
          break;
        }
        q += 4 + n;
      }
    }
    dau += lech;
    p += 46 + lt + lp + dv.getUint16(p + 32, true);
    if (ten.endsWith('/') || ten.endsWith('\\') || laRac(ten)) continue;   // thư mục, tệp rác
    if (co & 1) throw new Error(`${ten}: tệp .zip có mật khẩu — giải nén rồi chọn các tệp PDF`);
    if (kieu !== 0 && kieu !== 8) throw new Error(`${ten}: kiểu nén ${kieu} không đọc được — giải nén rồi chọn tệp`);
    ra.push({
      ten,
      co: goc,
      lay: async () => {
        if (dau + 30 > buf.length || dv.getUint32(dau, true) !== KY_TEP) throw new Error(`${ten}: tệp .zip hỏng`);
        const tu = dau + 30 + dv.getUint16(dau + 26, true) + dv.getUint16(dau + 28, true);
        const tho = new Blob([buf.subarray(tu, tu + nen)]);
        if (kieu === 0) return tho;
        if (typeof DecompressionStream === 'undefined') {
          throw new Error('Trình duyệt này không giải nén được .zip — cập nhật trình duyệt, hoặc giải nén rồi chọn tệp');
        }
        let ds;
        try { ds = new DecompressionStream('deflate-raw'); } catch (e) {
          throw new Error('Trình duyệt này quá cũ, không giải nén được .zip — cập nhật trình duyệt, hoặc giải nén rồi '
            + 'chọn các tệp');
        }
        return new Response(tho.stream().pipeThrough(ds)).blob();
      },
    });
  }
  return ra;
}
