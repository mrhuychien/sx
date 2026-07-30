// Hàng chờ gửi khi mất mạng (D37) — lưu trên máy, gửi lại khi có mạng.
//
// ════════════════ QUYẾT ĐỊNH QUAN TRỌNG NHẤT: CÁI GÌ ĐƯỢC XẾP HÀNG ════════════════
//
// KHÔNG phải thao tác nào cũng xếp hàng được. Xếp hàng bừa là cách nhanh nhất để có
// tồn kho sai mà không ai biết. Chia làm hai loại:
//
// XẾP HÀNG ĐƯỢC — chỉ ghi số vào phiếu NHÁP, chưa động tới kho hay lương:
//   bao_me · bao_can · luu_bang_vao_hop · ghi_su_co
//   Mỗi lần gọi gửi TOÀN BỘ dữ liệu của ngày đó (ghi đè, không cộng dồn), nên gửi
//   lại nhiều lần vẫn ra đúng một kết quả. Đây là lý do chúng an toàn: gửi trùng
//   không nhân đôi số. Cũng vì vậy chỉ giữ BẢN CUỐI của mỗi (method + ngày).
//
// KHÔNG XẾP HÀNG ĐƯỢC — và phải báo rõ lý do, không được im lặng bỏ qua:
//   chot_ngay / huy_chot_ngay   ghi kho + lương thật, cần kiểm tồn ngay lúc chốt
//   xuat_kho_dau               sinh mã lô để QC GHI TAY ra thẻ; offline không biết
//                              mã nào, đoán sai là đứt cả chuỗi truy xuất
//   hoan_tat_cong_doan         cần tồn thật của lô để chặn làm quá tay
//
// Người dùng vẫn NHẬP được mọi thứ khi mất mạng; chỉ mấy nút ghi kho là phải chờ.
// Đó là đánh đổi đúng: nhập liệu mất mạng thì ghi lại được, còn ghi kho sai thì
// phải đi kiểm kê mới phát hiện.

const KEY = 'sx-queue-v1';
const MAX = 200;   // chặn phình vô hạn nếu mất mạng cả tuần

// method -> hàm lấy "khoá gộp": cùng khoá thì bản sau ĐÈ bản trước
const XEP_HANG_DUOC = {
  'sx.api.portal.bao_me': (a) => a.ngay_sx || '',
  'sx.api.portal.bao_can': (a) => a.ngay_sx || '',
  'sx.api.portal.luu_bang_vao_hop': (a) => a.ngay_sx || '',
  'sx.api.portal.ghi_su_co': () => null,   // mỗi sự cố là một bản ghi riêng, KHÔNG gộp
};

const LY_DO_CHAN = {
  'sx.api.chot.chot_ngay':
    'Chốt ngày ghi kho và lương thật nên phải có mạng — số tồn phải kiểm ngay lúc chốt. '
    + 'Cứ nhập tiếp, có mạng rồi chốt.',
  'sx.api.chot.huy_chot_ngay':
    'Huỷ chốt phải thu hồi chứng từ kho nên phải có mạng.',
  'sx.api.tang1.xuat_kho_dau':
    'Xuất kho đỗ sinh mã lô để bạn ghi tay ra thẻ — mất mạng thì chưa biết mã nào, '
    + 'ghi sai là đứt chuỗi truy xuất. Chờ có mạng rồi bấm lại.',
  'sx.api.tang1.hoan_tat_cong_doan':
    'Hoàn tất công đoạn cần đọc tồn thật của lô để không làm quá số đang có. Chờ có mạng.',
  'sx.api.tang1.huy_xuat_dau':
    'Huỷ phiếu xuất đỗ phải thu hồi phiếu kho nên phải có mạng.',
};

const listeners = [];

function doc() {
  try {
    const raw = localStorage.getItem(KEY);
    const ds = raw ? JSON.parse(raw) : [];
    return Array.isArray(ds) ? ds : [];
  } catch (e) {
    return [];   // localStorage hỏng/đầy -> coi như rỗng, không làm app chết
  }
}

function ghi(ds) {
  try {
    localStorage.setItem(KEY, JSON.stringify(ds.slice(-MAX)));
  } catch (e) { /* hết chỗ: giữ nguyên hàng cũ, thà mất bản mới hơn mất cả hàng */ }
  listeners.forEach((fn) => fn(trangThai()));
}

export function onQueue(fn) { listeners.push(fn); fn(trangThai()); }

export function trangThai() {
  const ds = doc();
  return { so_luong: ds.length, loi: ds.filter((x) => x.loi).length };
}

export function xepHangDuoc(method) { return Object.hasOwn(XEP_HANG_DUOC, method); }

export function lyDoChan(method) {
  return LY_DO_CHAN[method]
    || 'Thao tác này cần có mạng vì nó ghi vào kho. Chờ có mạng rồi làm lại.';
}

/** Xếp một lời gọi vào hàng. Trả số thứ tự trong hàng. */
export function xepHang(method, args) {
  const ds = doc();
  const khoa = XEP_HANG_DUOC[method](args || {});
  if (khoa !== null && khoa !== undefined) {
    // Bản sau đè bản trước cho cùng (method, ngày): mỗi lần gọi vốn gửi trọn dữ liệu
    // của ngày, giữ 5 bản nháp liên tiếp chỉ để gửi rồi ghi đè nhau là vô nghĩa.
    const i = ds.findIndex((x) => x.method === method && x.khoa === khoa);
    if (i >= 0) ds.splice(i, 1);
  }
  ds.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    method,
    args: args || {},
    khoa: khoa === undefined ? null : khoa,
    luc: new Date().toISOString(),
    loi: null,
  });
  ghi(ds);
  return ds.length;
}

export function xoaHang() { ghi([]); }

export function danhSach() { return doc(); }

/** Gửi lần lượt từ đầu hàng. Dừng ngay khi mất mạng lại (giữ thứ tự nhập).
 *
 * postFn(method, args) phải THROW nếu thất bại. Lỗi mạng -> để lại trong hàng.
 * Lỗi nghiệp vụ (server từ chối) -> đánh dấu `loi` và GIỮ LẠI để người dùng thấy,
 * không xoá âm thầm: dữ liệu người ta gõ tay giữa xưởng không được phép biến mất.
 */
export async function guiLai(postFn) {
  let ds = doc();
  const ok = [];
  const loi = [];
  for (const item of ds) {
    if (item.loi) continue;               // đã lỗi nghiệp vụ -> chờ người xử lý
    if (!navigator.onLine) break;
    try {
      await postFn(item.method, item.args);
      ok.push(item.id);
    } catch (e) {
      if (!navigator.onLine || e.mat_mang) break;   // mất mạng giữa chừng -> để lại
      item.loi = e.message || 'Server từ chối';
      loi.push(item);
    }
  }
  ds = doc().filter((x) => !ok.includes(x.id));
  loi.forEach((l) => {
    const i = ds.findIndex((x) => x.id === l.id);
    if (i >= 0) ds[i].loi = l.loi;
  });
  ghi(ds);
  return { da_gui: ok.length, loi: loi.length, con_lai: ds.length };
}
