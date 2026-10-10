// Khớp tệp người dùng chọn với các tệp còn thiếu của bộ tài liệu (màn Nạp bộ — D182). Bản đã ký số mang tên tự đặt
// ("QT.01 Quản lý chung … (đã ký).pdf", "BM.01.01_…_signed.pdf") khác tên trong sổ đăng ký, nên khớp lần lượt:
//   1. đúng tên;
//   2. cùng tên khi bỏ dấu, hoa / thường, dấu câu, số 0 đầu, đuôi "_signed" / "đã ký" / "ký số";
//   3. mã tài liệu trong tên tệp — QT.01, BM.PRP.04, SĐ.02, KH.HACCP.01-PL… (viết "QT 01", "qt-1" cũng được);
//   4. tên gần giống: hầu hết các từ của tên tệp có trong tên tài liệu, và hơn hẳn ứng viên thứ hai — chỉ là gợi ý,
//      người dùng xem lại. Gợi ý sai (gắn nhầm PDF vào tài liệu) tệ hơn không gợi ý, nên đòi chặt.
// Ảnh chỉ ghép với ảnh, PDF với PDF. Mã chỉ dùng cho tài liệu (`ma` rỗng ở ảnh, hồ sơ đợt: trùng mã tài liệu).

/** Bỏ dấu tiếng Việt (cả đ / Đ), về chữ thường. */
export const boDau = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[đĐ]/g, 'd').toLowerCase();

/** Các từ (chữ, số) của chuỗi, số bỏ số 0 đầu: "QT.01_Quản lý" → ["qt", "1", "quan", "ly"]. */
export const tu = (s) => boDau(s).split(/[^a-z0-9]+/).filter(Boolean).map((t) => t.replace(/^0+(?=\d)/, ''));

export const duoi = (ten) => { const m = /\.([a-z0-9]+)$/i.exec(String(ten || '')); return m ? m[1].toLowerCase() : ''; };
const goc = (ten) => String(ten || '').replace(/\.[a-z0-9]+$/i, '');

// đuôi "đã ký" hay gặp ở các phần mềm ký số — dài trước ngắn
const DUOI_KY = [['da', 'ky', 'so'], ['ban', 'ky', 'so'], ['da', 'ky'], ['ban', 'ky'], ['ky', 'so'], ['kyso'],
  ['signed'], ['sign'], ['ky'], ['final'], ['copy']];

/** Bỏ các từ "đã ký" ở CUỐI dãy từ (lặp tới khi hết): …_signed, (đã ký), ký số, final, copy. */
export function boDuoiKy(ds) {
  let a = ds.slice();
  for (;;) {
    const d = DUOI_KY.find((p) => a.length > p.length && p.every((t, i) => a[a.length - p.length + i] === t));
    if (!d) return a;
    a = a.slice(0, a.length - d.length);
  }
}

const khoaTen = (ten) => boDuoiKy(tu(goc(ten))).join(' ');

/** Vị trí mã (dãy từ) trong dãy từ của tên tệp; mã một từ (PRP, SLM) chỉ tính ở đầu tên; từ ngay sau mã không được
 *  là số (QT.01 không khớp "QT.01.02 …"). -1 = không có. */
export function viTriMa(ds, ma) {
  for (let i = 0; i + ma.length <= ds.length; i += 1) {
    if (i > 0 && ma.length < 2) return -1;
    if (ma.every((t, k) => ds[i + k] === t) && !/^\d+$/.test(ds[i + ma.length] || '')) return i;
  }
  return -1;
}

/** Phần các từ (khác nhau) của tên tệp có trong tên tài liệu — "So do to chuc" trong "Sơ đồ tổ chức, chức năng…" = 1;
 *  "Bien ban hop giao ban thang 9" với "Biên bản họp Ban ISO" = 0,5 (giao, tháng 9 không có). {phu, chung}. */
const phu = (tep, muc) => {
  const A = new Set(tep);
  let chung = 0;
  A.forEach((t) => { if (muc.has(t)) chung += 1; });
  return { phu: A.size ? chung / A.size : 0, chung };
};

export const GAN_TOI_THIEU = 0.8;   // phần từ của tên tệp phải có trong tên tài liệu
export const GAN_CACH = 0.15;       // phải hơn ứng viên thứ hai ít nhất chừng này

/** can: [{khoa, tep, co, ma, ten}] (tinh_trang_nap.can_tep); tenTep: tên các tệp đã chọn.
 *  → {dong: [{ten, khoa, cach}], thieu: [mục còn thiếu]}. cach: 'ten' (đúng / cùng tên), 'ma', 'gan' (gợi ý),
 *  'da_co' (tệp của mục đã có trên app — không tải lại), 'trung' (mục đó đã có tệp khác nhận), '' (chưa khớp).
 *  Mỗi mục nhận nhiều nhất một tệp. */
export function ghepTep(can, tenTep) {
  const tat = can || [];
  const thieu = tat.filter((x) => !x.co);
  const ds = Array.from(tenTep || []).sort((a, b) => a.localeCompare(b));
  const gan = {};
  const daNhan = new Set();
  const cungLoai = (f, x) => duoi(f) === duoi(x.tep);
  const trong = (f) => !gan[f];
  const dat = (f, x, cach) => {           // x = mục tệp f thuộc về (theo tên / mã)
    if (x.co) gan[f] = { khoa: '', cach: 'da_co' };
    else if (daNhan.has(x.khoa)) gan[f] = { khoa: '', cach: 'trung' };
    else { gan[f] = { khoa: x.khoa, cach }; daNhan.add(x.khoa); }
  };
  // 1–2. đúng tên, rồi cùng tên sau chuẩn hoá
  [(f, x) => f === x.tep, (f, x) => khoaTen(f) !== '' && khoaTen(f) === khoaTen(x.tep)].forEach((la) => {
    ds.filter(trong).forEach((f) => {
      const x = tat.find((y) => cungLoai(f, y) && la(f, y) && !y.co && !daNhan.has(y.khoa))
        || tat.find((y) => cungLoai(f, y) && la(f, y));
      if (x) dat(f, x, 'ten');
    });
  });
  // 3. mã tài liệu: mã đứng sớm nhất, rồi mã dài nhất
  const coMa = tat.filter((x) => x.ma).map((x) => ({ x, m: tu(x.ma) })).filter((o) => o.m.length);
  ds.filter(trong).forEach((f) => {
    const t = tu(goc(f));
    let tot = null;
    coMa.forEach((o) => {
      if (!cungLoai(f, o.x)) return;
      const i = viTriMa(t, o.m);
      if (i >= 0 && (!tot || i < tot.i || (i === tot.i && o.m.length > tot.n))) tot = { x: o.x, i, n: o.m.length };
    });
    if (tot) dat(f, tot.x, 'ma');
  });
  // 4. gần giống: từ của tên tệp nằm trong tên tài liệu / tên tệp trong sổ (≥ 2 từ); điểm cao nhận trước
  const goiY = [];
  ds.filter(trong).forEach((f) => {
    const t = boDuoiKy(tu(goc(f)));
    const diem = thieu.filter((x) => !daNhan.has(x.khoa) && cungLoai(f, x))
      .map((x) => ({ x, ...phu(t, new Set([...tu(x.ten), ...boDuoiKy(tu(goc(x.tep)))])) }))
      .sort((a, b) => b.phu - a.phu);
    const [a, b] = diem;
    if (a && a.phu >= GAN_TOI_THIEU && a.chung >= 2 && (!b || a.phu - b.phu >= GAN_CACH)) goiY.push({ f, x: a.x, d: a.phu });
  });
  goiY.sort((a, b) => b.d - a.d).forEach((g) => { if (!daNhan.has(g.x.khoa)) dat(g.f, g.x, 'gan'); });
  return { dong: ds.map((f) => ({ ten: f, khoa: gan[f] ? gan[f].khoa : '', cach: gan[f] ? gan[f].cach : '' })), thieu };
}
