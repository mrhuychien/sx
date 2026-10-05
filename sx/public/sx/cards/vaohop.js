// Card Vào hộp — grid CN → picker LOẠI CÔNG VIỆC (search + gần đây, kèm đơn giá)
// → numpad số lượng → auto-save. Loại nào có ≥2 SKU thì hỏi thêm 1 bước chọn SKU
// (cần cho lệnh SX tầng 3); 1 SKU tự gán; 0 SKU chỉ tính lương khoán (D23).
// Đơn giá luôn do server tính lại từ Activity Type.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatNumber, nhanNgay } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';
import { moQuet } from '/assets/sx/sx/components/quet.js';

// Dòng CÔNG NHẬT (D101): hộp do bộ phận công nhật đóng. Chấm cùng một cách như
// một người (chọn mã → số hộp) để vào hộp là số đếm ĐẦY ĐỦ của xưởng — và là trần
// nhập kho — nhưng server không tính khoán, không chấm ăn. Mã giả này chỉ sống ở
// màn hình + ranh giới API (sx/api/portal.py); trong DB là cờ cong_nhat.
const CONG_NHAT = 'CONG_NHAT';
const NV_CONG_NHAT = { name: CONG_NHAT, employee_name: 'Công nhật' };

export async function render({ container, boot, call, ensureNgay }) {
  container.className = 'sx-card';
  const ngay = boot.ngay_sx;
  const daChot = ngay && (ngay.docstatus === 1 || ngay.chot_vaohop);  // nửa Vào hộp (D55)
  const rows = ((boot.bang_vao_hop || {}).dong || []).map((r) => ({ ...r }));
  // D113: mỗi QC chỉ thấy dòng MÌNH ghi (quản lý thấy hết). `biet` = mã dòng máy đã
  // nhận từ server — server chỉ xoá dòng nằm trong đây, nên hai QC ghi cùng lúc
  // không xoá mất dòng của nhau.
  let biet = rows.map((r) => r.name).filter(Boolean);
  const thayHet = !!(boot.bang_vao_hop ? boot.bang_vao_hop.xem_het : boot.is_quan_ly);
  const itemsTp = boot.items_tp || [];
  // D68: ghi thẳng theo MÃ HÀNG, không còn Activity Type. Cùng một mã làm tay hay
  // có máy hỗ trợ thì đơn giá khác nhau, nên cách làm là một chiều riêng.
  const danhMuc = boot.danh_muc_khoan || [];
  const spGanDay = boot.sp_gan_day || [];
  const tenSPKhoan = (code) => (danhMuc.find((d) => d.item === code) || {}).ten || code;
  const nhanVien = boot.nhan_vien || [];
  // Chấm ăn ca / ăn đêm theo người (D30) — {nhan_vien: {an_ca, an_dem}}
  const anCa = {};
  (((boot.bang_vao_hop || {}).an_ca) || []).forEach((r) => {
    anCa[r.nhan_vien] = { an_ca: Number(r.an_ca) || 0, an_dem: Number(r.an_dem) || 0 };
  });
  // Ảnh chụp ăn ca lần lưu cuối — chỉ gửi người VỪA ĐỔI, để hai QC chấm ăn cho hai
  // nhóm người khác nhau không đè lên nhau.
  let anCaGoc = JSON.parse(JSON.stringify(anCa));
  // Tên ngắn (chỉ tên gọi; trùng thì server đã thêm họ / viết tắt đệm)
  const tenNgan = {};
  nhanVien.forEach((nv) => { tenNgan[nv.name] = nv.ten_hien_thi || nv.employee_name || nv.name; });
  tenNgan[CONG_NHAT] = '★ Công nhật';

  // Bố cục theo bản thiết kế "Xưởng SX - App (1a)" (D40):
  //   [tổng sản lượng hôm nay]              [đã nhập N/43]
  //   [dải SKU: mỗi loại một ô, cuộn ngang]
  //   HAY NHẬP — BẤM TÊN ĐỂ CHẤM
  //   [ô tìm 43 công nhân | ⌗ QUÉT THẺ]   ← D73: quét đứng TRƯỚC lưới tên
  //   [hàng công nhân: tên + ăn ca bên trái · số hộp bên phải]
  //   [Xem hết 43 công nhân] → hiện nốt người còn lại
  //   BẢN GHI HÔM NAY  [tên · loại | SL | ✎ | ✕] … [Tổng]
  //   [Copy sản lượng gửi nhóm]
  container.innerHTML = `
    <div class="sx-vh-top">
      <div>
        <div class="sx-field-label">Vào hộp hôm nay</div>
        <div class="sx-vh-tong"><span id="sx-vh-tonghop">0</span> <i>sp</i></div>
        <div class="sx-vh-tien" id="sx-vh-tongtien"></div>
      </div>
      <div class="sx-vh-done">
        <div class="sx-field-label">Đã nhập</div>
        <div class="sx-vh-done-so"><span id="sx-vh-donecount">0</span><i>/${nhanVien.length}</i></div>
      </div>
    </div>
    ${boot.canh_bao_nhan_vien ? `<div class="sx-warn-text">⚠ ${esc(boot.canh_bao_nhan_vien)}</div>` : ''}
    ${daChot ? '<div class="sx-muted">Đã chốt — chỉ xem. Muốn sửa: bấm HUỶ CHỐT NGÀY bên thẻ Chốt ngày.</div>' : ''}
    ${thayHet ? '' : '<div class="sx-muted">Bạn đang thấy phần <b>mình ghi</b>. QC khác ghi riêng phần của họ; tổng cả ngày xem ở màn Quản lý.</div>'}
    <div class="sx-vh-strip" id="sx-vh-strip"></div>
    ${daChot ? '' : `
      <div class="sx-field-label" id="sx-vh-nhan">Chấm hộp cho công nhân</div>
      <div class="sx-vh-timhang">
        <div class="sx-vh-tim-wrap">
          <span class="sx-vh-tim-icon" aria-hidden="true">⌕</span>
          <input class="sx-textarea sx-vh-search" id="sx-vh-tim" type="search"
                 aria-label="Tìm công nhân" placeholder="Tìm ${nhanVien.length} công nhân">
        </div>
        <button type="button" class="sx-btn sx-quet-nut" id="sx-vh-quet"
          >⌗ QUÉT THẺ</button>
      </div>
      <button type="button" class="sx-btn sx-vh-congnhat" id="sx-vh-congnhat"
        >★ Chấm hộp CÔNG NHẬT <span>không tính khoán</span></button>
      <div id="sx-vh-nv"></div>
      <div class="sx-vh-hang2" id="sx-vh-ds-nut" hidden>
        <button type="button" class="sx-vh-xemhet" id="sx-vh-xemhet"
          >Xem hết ${nhanVien.length} công nhân</button>
        <button type="button" class="sx-btn sx-quet-nut" id="sx-vh-dong">✕ ĐÓNG</button>
      </div>
    `}
    <div class="sx-field-label">Bản ghi hôm nay</div>
    <div class="sx-vh-list" id="sx-vh-rows"></div>
    <div class="sx-vh-footer" id="sx-vh-footer"></div>
    <div class="sx-vh-footer" id="sx-vh-an"></div>
    <div class="sx-vh-actions">
      <button type="button" class="sx-btn" id="sx-vh-copy">Copy sản lượng gửi nhóm</button>
      <button type="button" class="sx-btn" id="sx-vh-inthe">In thẻ quét</button>
    </div>
  `;
  let timKiem = '';
  let xemHet = false;
  // Lưới 45 cái tên KHÔNG bày sẵn: nó đẩy bảng ghi hôm nay xuống dưới màn, mà phần
  // lớn thời gian QC quét thẻ hoặc gõ tìm chứ không dò mắt qua lưới. Bấm vào ô tìm
  // mới xổ ra.
  let moDS = false;
  const tbody = container.querySelector('#sx-vh-rows');
  const footer = container.querySelector('#sx-vh-footer');
  const anBox = container.querySelector('#sx-vh-an');

  const tenSP = (code) => {
    const it = itemsTp.find((x) => x.name === code);
    return it ? (it.item_name || it.name) : code;
  };
  const tenNV = (r) => tenNgan[r.nhan_vien] || r.ten_nhan_vien || r.nhan_vien;

  // Gộp các dòng CÙNG công nhân lại (server đã sắp, client sắp lại cho chắc)
  function theoNguoi() {
    const nhom = new Map();
    rows.forEach((r, i) => {
      if (!nhom.has(r.nhan_vien)) nhom.set(r.nhan_vien, { ten: tenNV(r), dong: [] });
      nhom.get(r.nhan_vien).dong.push({ ...r, _i: i });
    });
    // Công nhật xuống cuối — bảng đọc theo người, công nhật không phải một người.
    return [...nhom.entries()]
      .sort(([ka, a], [kb, b]) => ((ka === CONG_NHAT) - (kb === CONG_NHAT))
        || a.ten.localeCompare(b.ten, 'vi'))
      .map(([, g]) => g);
  }

  // Lưới chưa/đã nhập đổi theo dữ liệu -> vẽ lại CÙNG LÚC với bảng, không để lệch
  function paint() { veBang(); veNV(); }

  function veBang() {
    // Danh sách bản ghi: TÊN + loại bên trái, SỐ bên phải, rồi ✎ và ✕.
    // Bảng 3 cột trên tablet dọc bị bóp chữ; danh sách đọc lướt được theo chiều dọc.
    let html = '';
    theoNguoi().forEach((g) => {
      g.dong.forEach((r) => {
        const cn = r.nhan_vien === CONG_NHAT;
        html += `<div class="sx-vh-row${cn ? ' sx-vh-row-cn' : ''}">
          <div class="sx-vh-who">
            <div class="sx-vh-name">${esc(g.ten)}</div>
            <div class="sx-vh-meta">${esc(tenSPKhoan(r.san_pham) || '—')}${
              r.cach_lam ? ` · ${esc(r.cach_lam)}` : ''}${cn ? ' · không tính khoán' : ''}${
              thayHet && r.nguoi_ghi ? ` · ghi: ${esc(String(r.nguoi_ghi).split('@')[0])}` : ''}</div>
          </div>
          <button type="button" class="sx-vh-sl" data-i="${r._i}"${daChot ? ' disabled' : ''}
            >${esc(formatNumber(r.so_hop))}</button>
          ${daChot ? '' : `
            <button type="button" class="sx-vh-them" data-nv="${esc(r.nhan_vien)}"
              aria-label="Ghi thêm sản phẩm cho ${esc(g.ten)}" title="Ghi thêm loại khác">+</button>
            <button type="button" class="sx-vh-del" data-i="${r._i}"
              aria-label="Xoá dòng ${esc(g.ten)}">✕</button>`}
        </div>`;
      });
    });
    tbody.innerHTML = html || '<div class="sx-muted">Chưa có bản ghi nào.</div>';

    const tongHop = rows.reduce((a, r) => a + (Number(r.so_hop) || 0), 0);
    const tongTien = rows.reduce((a, r) => a + (Number(r.thanh_tien) || 0), 0);
    const soNguoi = new Set(rows.map((r) => r.nhan_vien).filter((n) => n !== CONG_NHAT)).size;
    const hopCN = rows.filter((r) => r.nhan_vien === CONG_NHAT)
      .reduce((a, r) => a + (Number(r.so_hop) || 0), 0);
    container.querySelector('#sx-vh-tonghop').textContent = formatNumber(tongHop);
    // Không hiện tiền ở màn nhập (D43) — giữ ô rỗng để bố cục không nhảy
    container.querySelector('#sx-vh-tongtien').textContent = '';
    container.querySelector('#sx-vh-donecount').textContent = soNguoi;
    footer.innerHTML = `<span class="sx-field-label">Tổng</span>
      <span>${formatNumber(tongHop)} sp${hopCN
        ? ` <span class="sx-muted">(công nhật ${formatNumber(hopCN)})</span>` : ''}</span>`;

    // Dải SKU: mỗi loại công việc một ô, cuộn ngang — nhìn ra ngay hôm nay chạy loại gì
    const theoAct = {};
    rows.forEach((r) => {
      const k = r.san_pham || '—';
      theoAct[k] = (theoAct[k] || 0) + (Number(r.so_hop) || 0);
    });
    const strip = container.querySelector('#sx-vh-strip');
    const dsAct = Object.entries(theoAct).sort((a, b) => b[1] - a[1]);
    strip.innerHTML = dsAct.length
      ? dsAct.map(([k, v]) => `<div class="sx-vh-sku">
          <div class="sx-field-label">${esc(tenSPKhoan(k))}</div>
          <div class="sx-vh-sku-so">${formatNumber(v)}</div></div>`).join('')
      : '';
    strip.style.display = dsAct.length ? '' : 'none';

    const suatCa = Object.values(anCa).reduce((a, x) => a + (Number(x.an_ca) || 0), 0);
    const suatDem = Object.values(anCa).reduce((a, x) => a + (Number(x.an_dem) || 0), 0);
    anBox.innerHTML = (suatCa || suatDem)
      ? `<span class="sx-field-label">Suất ăn</span> <span>ca ${suatCa} · đêm ${suatDem}</span>`
      : '<span class="sx-muted">Chưa chấm ăn ca / ăn đêm.</span>';

    if (!daChot) {
      tbody.querySelectorAll('.sx-vh-del').forEach((btn) => {
        btn.addEventListener('click', async () => { rows.splice(Number(btn.dataset.i), 1); await save(); });
      });
      tbody.querySelectorAll('.sx-vh-sl').forEach((btn) => {
        btn.addEventListener('click', () => suaSoLuong(Number(btn.dataset.i)));
      });
      tbody.querySelectorAll('.sx-vh-them').forEach((btn) => {
        const nv = btn.dataset.nv === CONG_NHAT ? NV_CONG_NHAT
          : (nhanVien.find((x) => x.name === btn.dataset.nv) || { name: btn.dataset.nv });
        btn.addEventListener('click',
          () => themDong(nv, danhMuc, spGanDay, rows, save, tenNgan, anCa, boot));
      });
    }
  }

  // Sửa số lượng tại chỗ — chỉ khi chưa chốt (chốt rồi phải huỷ chốt mới sửa được)
  function suaSoLuong(i) {
    const r = rows[i];
    if (!r) return;
    openNumpad({
      // Kicker = việc đang làm, title = NGƯỜI. Bị ngắt quãng rồi quay lại vẫn biết
      // mình đang chấm cho ai (D39).
      kicker: `Sửa · ${tenSPKhoan(r.san_pham) || ''}`,
      title: tenNV(r),
      unitLabel: 'Số lượng',
      titleActions: r.nhan_vien === CONG_NHAT ? null : nutAnCa({ name: r.nhan_vien }, anCa, save),
      initial: r.so_hop,
      onOk: async (v) => {
        const sl = Math.round(v);
        if (sl <= 0) { toastErr('Số lượng phải > 0. Muốn xoá thì bấm ✕.'); return; }
        rows[i].so_hop = sl;
        await save();
      },
    });
  }

  if (!daChot) {
  }

  // QR vẽ NGAY TRÊN MÁY (D63): server chỉ trả danh sách tên + mã. Nạp bộ sinh QR
  // trễ để ai không in thẻ thì không phải tải nó.
  container.querySelector('#sx-vh-inthe').addEventListener('click', async (e) => {
    e.currentTarget.disabled = true;
    try {
      const ds = await call('sx.api.the.danh_sach_the');
      if (!ds || !ds.length) { toastErr('Chưa có công nhân nào để in thẻ.'); }
      else {
        const { moTrangInThe } = await import('/assets/sx/sx/lib/inthe.js');
        if (!moTrangInThe(ds)) {
          toastErr('Trình duyệt chặn cửa sổ mới — cho phép pop-up rồi thử lại.');
        }
      }
    } catch (err) { toastErr(err.message); }
    e.target.disabled = false;
  });

  container.querySelector('#sx-vh-copy').addEventListener('click', () => {
    copySanLuong(theoNguoi(), (boot.ngay_sx && boot.ngay_sx.ngay) || boot.ngay_xem,
      (code) => { const k = tenSPKhoan(code); return k && k !== code ? k : tenSP(code); });
  });

  async function save() {
    try {
      const ng = await ensureNgay();
      const doiAn = Object.entries(anCa)
        .filter(([nv, v]) => {
          const g = anCaGoc[nv] || { an_ca: 0, an_dem: 0 };
          return (Number(v.an_ca) || 0) !== (Number(g.an_ca) || 0)
            || (Number(v.an_dem) || 0) !== (Number(g.an_dem) || 0);
        })
        .map(([nv, v]) => ({ nhan_vien: nv, an_ca: v.an_ca, an_dem: v.an_dem }));
      const r = await call('sx.api.portal.luu_bang_vao_hop', {
        ngay_sx: ng.name,
        rows: JSON.stringify(rows.map((x) => ({
          name: x.name || null, nhan_vien: x.nhan_vien, cach_lam: x.cach_lam,
          san_pham: x.san_pham, so_hop: x.so_hop,
        }))),
        biet: JSON.stringify(biet),
        an_ca: JSON.stringify(doiAn),
      });
      if (r && r._hang_cho) { paint(); toast('Mất mạng — đã lưu trên máy, sẽ gửi khi có mạng.'); return; }
      rows.length = 0;
      (r && r.dong ? r.dong : []).forEach((x) => rows.push(x));
      biet = rows.map((x) => x.name).filter(Boolean);
      Object.keys(anCa).forEach((k) => delete anCa[k]);
      ((r && r.an_ca) || []).forEach((x) => {
        anCa[x.nhan_vien] = { an_ca: Number(x.an_ca) || 0, an_dem: Number(x.an_dem) || 0 };
      });
      anCaGoc = JSON.parse(JSON.stringify(anCa));
      // Chấm xong một người là xong việc với lưới tên — thu lại để bảng ghi hôm nay
      // trở về đúng tầm mắt, khỏi phải cuộn qua 45 cái tên.
      dongDS();
      paint();
      toast('Đã lưu.');
    } catch (e) {
      toastErr(e.message);
      paint();
    }
  }

  // Lưới công nhân: TÁCH "chưa nhập" khỏi "đã nhập".
  //
  // QC#2 đi dọc chuyền hỏi từng người; câu hỏi duy nhất trong đầu là "còn ai chưa
  // hỏi?". Trước đây 30 chip dàn đều nhau, đã hỏi hay chưa nhìn không ra — phải dò
  // xuống bảng dưới rồi ngược lên. Giờ nhóm CHƯA NHẬP nằm trên, ô to; nhóm đã nhập
  // tụt xuống, nhỏ và mờ, kèm số hộp đã ghi để đối chiếu nhanh.
  function veNV() {
    if (daChot) return;
    const nvGrid = container.querySelector('#sx-vh-nv');
    if (!nvGrid) return;
    const nutDS = container.querySelector('#sx-vh-ds-nut');
    const nhan = container.querySelector('#sx-vh-nhan');
    if (nutDS) nutDS.hidden = !moDS;
    if (nhan) {
      nhan.textContent = moDS ? 'Bấm tên để chấm' : 'Chấm hộp cho công nhân';
    }
    if (!moDS) {
      nvGrid.innerHTML = '';
      return;
    }
    if (!nhanVien.length) {
      nvGrid.innerHTML = '<div class="sx-muted">Chưa có công nhân công khoán nào '
        + '(kiểm tra nhóm trong SX Settings).</div>';
      return;
    }
    const daNhap = {};
    const soLoai = {};
    rows.forEach((r) => {
      daNhap[r.nhan_vien] = (daNhap[r.nhan_vien] || 0) + (Number(r.so_hop) || 0);
      (soLoai[r.nhan_vien] = soLoai[r.nhan_vien] || new Set()).add(r.san_pham);
    });

    // Chưa nhập lên trước: câu hỏi duy nhất trong đầu QC khi đi dọc chuyền là
    // "còn ai chưa hỏi". Không tìm gì thì chỉ hiện người chưa nhập + người đã nhập.
    const loc = timKiem.trim().toLowerCase();
    const khop = (nv) => !loc
      || (tenNgan[nv.name] || '').toLowerCase().includes(loc)
      || (nv.employee_name || '').toLowerCase().includes(loc);
    const sapXep = nhanVien.filter(khop)
      .sort((a, b) => (daNhap[a.name] ? 1 : 0) - (daNhap[b.name] ? 1 : 0));
    // Mặc định chỉ 8 người "hay nhập" — 43 thẻ đổ ra màn hình thì không ai đọc.
    // Gõ tìm hoặc bấm "Xem hết" thì hiện toàn bộ.
    const ds = (loc || xemHet) ? sapXep : sapXep.slice(0, 12);

    const veThe = (nv) => {
      const q = daNhap[nv.name] || 0;
      const nLoai = soLoai[nv.name] ? soLoai[nv.name].size : 0;
      const an = anCa[nv.name] || {};
      const suat = (n, ten) => (n ? (n > 1 ? `${ten} ×${n}` : ten) : '');
      const nhanAn = [suat(Number(an.an_ca) || 0, 'ăn ca'),
                      suat(Number(an.an_dem) || 0, 'ăn đêm')].filter(Boolean).join(' + ');
      // Người CHƯA nhập không in dòng "chưa nhập": 45 lần cùng một chữ thì nó
      // không còn là thông tin, chỉ là mỗi ô cao gấp đôi. Chưa nhập = ô xám
      // trống; đã nhập = ô tô màu mùa CÓ số. Chỗ tiết kiệm được đủ hiện thêm
      // một hàng người.
      const phu = q
        ? `${formatNumber(q)} sp${nLoai > 1 ? ` · ${nLoai} loại` : ''}${nhanAn ? ` · ${nhanAn}` : ''}`
        : nhanAn;
      return `<button type="button" class="sx-nv-row${q ? ' sx-nv-row-xong' : ''}"
          data-nv="${esc(nv.name)}" title="${esc(nv.employee_name || nv.name)}">
        <span class="sx-nv-ten">${esc(tenNgan[nv.name])}</span>
        ${phu ? `<span class="sx-nv-qty">${esc(phu)}</span>` : ''}
      </button>`;
    };

    nvGrid.innerHTML = ds.length
      ? `<div class="sx-nv-luoi">${ds.map(veThe).join('')}</div>`
      : '<div class="sx-muted">Không tìm thấy ai khớp.</div>';

    nvGrid.querySelectorAll('.sx-nv-row').forEach((b) => {
      const nv = nhanVien.find((x) => x.name === b.dataset.nv);
      b.addEventListener('click',
        () => themDong(nv, danhMuc, spGanDay, rows, save, tenNgan, anCa, boot));
    });
  }

  const btnHet = container.querySelector('#sx-vh-xemhet');
  if (btnHet) {
    btnHet.addEventListener('click', () => {
      xemHet = !xemHet;
      btnHet.textContent = xemHet
        ? 'Thu gọn — chỉ hiện người hay nhập'
        : `Xem hết ${nhanVien.length} công nhân`;
      veNV();
    });
  }

  // Quét thẻ = đường TẮT tới đúng người, không thay đường bấm tay. Thẻ ướt, bẩn,
  // quên ở nhà, người mới chưa có thẻ — bấm tay vẫn phải chạy.
  const btnCN = container.querySelector('#sx-vh-congnhat');
  if (btnCN) {
    btnCN.addEventListener('click',
      () => themDong(NV_CONG_NHAT, danhMuc, spGanDay, rows, save, tenNgan, anCa, boot));
  }

  const btnQuet = container.querySelector('#sx-vh-quet');
  if (btnQuet) {
    btnQuet.addEventListener('click', () => moQuet({
      ma_quet: boot.ma_quet, loai: 'nv',
      kicker: 'Ghi hộp', title: 'Quét thẻ công nhân',
      onTim: (emp) => {
        const nv = nhanVien.find((x) => x.name === emp);
        if (!nv) { toastErr('Người này không thuộc nhóm công khoán hôm nay.'); return; }
        themDong(nv, danhMuc, spGanDay, rows, save, tenNgan, anCa, boot);
      },
    }));
  }

  const oTim = container.querySelector('#sx-vh-tim');
  if (oTim) {
    const mo = () => { if (!moDS) { moDS = true; veNV(); } };
    // focus lẫn input: máy quét cầm tay đổ chữ vào ô mà không sinh focus.
    oTim.addEventListener('focus', mo);
    oTim.addEventListener('input', (e) => { timKiem = e.target.value; mo(); veNV(); });
  }

  const btnDong = container.querySelector('#sx-vh-dong');
  if (btnDong) {
    btnDong.addEventListener('click', () => { dongDS(); veNV(); });
  }

  function dongDS() {
    moDS = false;
    xemHet = false;
    timKiem = '';
    if (oTim) { oTim.value = ''; oTim.blur(); }
    if (btnHet) btnHet.textContent = `Xem hết ${nhanVien.length} công nhân`;
  }

  if (!daChot && !danhMuc.length) {
    container.querySelector('#sx-vh-nv').insertAdjacentHTML('beforebegin',
      '<div class="sx-warn-text">⚠ Chưa có mã hàng thành phẩm nào — vào SX Settings '
      + 'chọn "Nhóm hàng là thành phẩm", hoặc đánh dấu Item có Nhóm SX = TP.</div>');
  } else if (!daChot && !boot.bang_don_gia) {
    // Thiếu bảng đơn giá thì vẫn ghi được sản lượng, nhưng lương ra 0 — nói ngay đầu
    // ca, đừng để cuối tháng tính lương mới lộ.
    container.querySelector('#sx-vh-nv').insertAdjacentHTML('beforebegin',
      '<div class="sx-warn-text">⚠ Chưa có bảng đơn giá khoán — sản lượng vẫn ghi '
      + 'được nhưng tiền công đang tính 0. Lập MỘT bảng SX Bang Don Gia rồi lưu là '
      + 'tự tính lại; không phải lập lại mỗi tháng.</div>');
  }

  paint();
}

/** Hai nút bật/tắt ăn ca · ăn đêm gắn cạnh TÊN trong bàn số (D41).
 *
 * Chấm ăn là việc của cùng một lần chạm vào người đó: QC đang hỏi "hôm nay chị làm
 * bao nhiêu" thì hỏi luôn "có ăn ca không". Bắt đi hai vòng chuyền cho hai việc là
 * cách chắc chắn để lần thứ hai bị quên. Thẻ riêng vẫn giữ cho thao tác HÀNG LOẠT
 * (tất cả ăn ca / bỏ hết).
 *
 * Lưu NGAY khi bấm, không đợi bấm LƯU của bàn số: người dùng có thể bấm ✕ đóng bàn
 * số mà vẫn muốn giữ phần chấm ăn vừa bật.
 */
function nutAnCa(nv, anCa, save) {
  if (!anCa) return null;
  const cur = () => (anCa[nv.name] = anCa[nv.name] || { an_ca: 0, an_dem: 0 });
  return [
    { label: 'Ăn ca', value: Number(cur().an_ca) || 0,
      onChange: (n) => { cur().an_ca = n; save(); } },
    { label: 'Ăn đêm', value: Number(cur().an_dem) || 0,
      onChange: (n) => { cur().an_dem = n; save(); } },
  ];
}

/**
 * Chấm cho MỘT công nhân. Một người thường nhận nhiều loại hộp trong ca, nên sau khi
 * nhập số có hai lối ra: GHI TIẾP quay lại chọn mã hàng cho CHÍNH người đó, XONG thì
 * đóng hẳn. Bắt bấm lại tên người sau mỗi mã là bắt làm lại một bước đã làm.
 */
function themDong(nv, danhMuc, spGanDay, rows, save, tenNgan, anCa, boot) {
  const ten = (tenNgan && tenNgan[nv.name]) || nv.employee_name || nv.name;
  const chonMa = () => openSanPhamPicker(ten, danhMuc, spGanDay, (sp) => {
    // Mã có nhiều cách làm -> hỏi thêm một bước, vì mỗi cách một đơn giá.
    // Chỉ một cách (và không có giá chung) -> tự chọn, QC không phải bấm.
    const cach = sp.cach_lam || [];
    const tiep = (cachLam) =>
      nhapSoLuong(nv, ten, sp, cachLam, rows, save, anCa, chonMa);
    if (cach.length > 1 || (cach.length === 1 && sp.gia_chung != null)) {
      openCachLamPicker(ten, sp, tiep);
    } else if (cach.length === 1) {
      tiep(cach[0].ten);
    } else {
      tiep(null);
    }
  }, boot);
  chonMa();
}

function nhapSoLuong(nv, ten, sp, cachLam, rows, save, anCa, ghiTiep) {
  const cn = nv.name === CONG_NHAT;
  const gia = cachLam
    ? ((sp.cach_lam || []).find((c) => c.ten === cachLam) || {}).don_gia
    : sp.gia_chung;

  // Cả hai nút đều LƯU con số đang nhập; chỉ khác chuyện sau đó đi đâu.
  const luu = async (v) => {
    const sl = Math.round(v);
    if (sl <= 0) { toastErr('Số lượng phải > 0.'); return false; }
    rows.push({
      nhan_vien: nv.name, ten_nhan_vien: nv.employee_name,
      san_pham: sp.item, cach_lam: cachLam || null, so_hop: sl,
    });
    await save();
    return true;
  };

  openNumpad({
    kicker: cachLam ? `${sp.ten} · ${cachLam}` : sp.ten,
    title: ten,
    unitLabel: 'Số lượng',
    titleActions: cn ? null : nutAnCa(nv, anCa, save),
    // Đơn giá chỉ HIỆN để đối chiếu; server luôn tra lại từ bảng đơn giá áp dụng.
    hint: (n) => (cn ? 'công nhật — không tính khoán'
      : (gia ? `${formatNumber(n * gia)} đ` : '⚠ chưa khai đơn giá')),
    okLabel: 'XONG',
    onOk: (v) => { luu(v); },
    okPhu: ghiTiep ? {
      label: '+ GHI TIẾP',
      onOk: async (v) => { if (await luu(v)) ghiTiep(); },
    } : null,
  });
}

// Chọn MÃ HÀNG: mã hay dùng lên đầu, còn lại tìm theo tên. Mã chưa khai đơn giá vẫn
// chọn được (đánh dấu) — chặn QC giữa xưởng vì một dòng thiếu giá là bắt chuyền dừng.
function openSanPhamPicker(ten, danhMuc, spGanDay, onPick, boot) {
  const m = openModal({ kicker: 'Chọn mã hàng', title: ten });
  m.body.innerHTML = `
    <div class="sx-vh-hang2">
      <input class="sx-textarea" id="sx-sp-tim" type="search" autocomplete="off"
        placeholder="Tìm trong ${danhMuc.length} mã hàng…">
      <button type="button" class="sx-btn sx-quet-nut" id="sx-sp-quet">⌗ QUÉT HỘP</button>
    </div>
    <div id="sx-sp-ds"></div>
  `;
  const box = m.body.querySelector('#sx-sp-ds');
  const oTim = m.body.querySelector('#sx-sp-tim');
  const byItem = {};
  danhMuc.forEach((d) => { byItem[d.item] = d; });

  const chip = (d) => `<button type="button" class="sx-sp-chip sx-sp-pick"
      data-item="${esc(d.item)}">${esc(d.ten)}${
    d.chua_gia ? '<div class="sx-muted">chưa khai giá</div>'
      : (d.cach_lam.length > 1 ? `<div class="sx-muted">${d.cach_lam.length} cách làm</div>` : '')}
    </button>`;

  function ve() {
    const q = oTim.value.toLowerCase().trim();
    const khop = danhMuc.filter((d) => !q || d.ten.toLowerCase().includes(q)
      || d.item.toLowerCase().includes(q));
    const ganDay = spGanDay.map((c) => byItem[c]).filter(Boolean);
    let html = '';
    if (!q && ganDay.length) {
      html += '<div class="sx-field-label">Hay ghi</div><div class="sx-sp-grid">'
        + ganDay.map(chip).join('') + '</div>';
    }
    html += khop.length
      ? `<div class="sx-field-label">${q ? 'Kết quả' : 'Tất cả mã hàng'}</div>`
        + '<div class="sx-sp-grid">' + khop.map(chip).join('') + '</div>'
      : '<div class="sx-muted">Không tìm thấy mã hàng nào.</div>';
    box.innerHTML = html;
    box.querySelectorAll('.sx-sp-pick').forEach((b) => {
      b.addEventListener('click', () => { m.close(); onPick(byItem[b.dataset.item]); });
    });
  }
  oTim.addEventListener('input', ve);
  m.body.querySelector('#sx-sp-quet').addEventListener('click', () => moQuet({
    ma_quet: boot && boot.ma_quet, loai: 'sp', kicker: ten, title: 'Quét hộp',
    onTim: (item) => {
      const d = byItem[item];
      if (!d) { toastErr('Mã này không nằm trong danh mục thành phẩm.'); return; }
      m.close();
      onPick(d);
    },
  }));
  ve();
}

// Chọn CÁCH LÀM — chỉ hiện khi mã đó có nhiều hơn một mức giá
function openCachLamPicker(ten, sp, onPick) {
  const m = openModal({ kicker: sp.ten, title: `${ten} — làm bằng cách nào?` });
  const chon = [
    ...(sp.cach_lam || []).map((c) => ({ ten: c.ten, gia: c.don_gia, val: c.ten })),
    ...(sp.gia_chung != null ? [{ ten: 'Chung', gia: sp.gia_chung, val: null }] : []),
  ];
  m.body.innerHTML = '<div class="sx-sl-hang">' + chon.map((c, i) => `
    <button type="button" class="sx-sl-o" data-i="${i}">
      <span class="sx-sl-ten">${esc(c.ten)}</span>
      <span class="sx-sl-so">${formatNumber(c.gia)} đ</span>
    </button>`).join('') + '</div>';
  m.body.querySelectorAll('[data-i]').forEach((b) => {
    b.addEventListener('click', () => { m.close(); onPick(chon[Number(b.dataset.i)].val); });
  });
}

// Copy sản lượng ra clipboard để dán vào nhóm chat — công nhân tự đối chiếu (D27).
// Người có nhiều loại thì ghi tắt: "Khanh (Vào hộp 170: 29, Vào hộp 300: 50)".
/** Văn bản sản lượng gửi nhóm chat. Hàm THUẦN — `tenSP(code)` truyền vào từ
 *  render(), nơi có danh mục mã hàng. (Trước đây hàm này gọi thẳng `tenSP` vốn chỉ
 *  sống TRONG render() → bấm nút là lỗi "tenSP is not defined", không copy gì.) */
export function vanBanSanLuong(nhomVao, ngay, tenSP) {
  // Bỏ dòng CÔNG NHẬT: tin gửi nhóm là để từng công nhân khoán đối chiếu số của
  // mình — công nhật không phải một người, cũng không ai đối chiếu dòng đó.
  const nhom = nhomVao
    .map((g) => ({ ...g, dong: g.dong.filter((r) => r.nhan_vien !== CONG_NHAT) }))
    .filter((g) => g.dong.length);
  const d = (ngay || '').split('-');
  const tieuDe = d.length === 3 ? `SẢN LƯỢNG ${d[2]}/${d[1]}/${d[0]}` : 'SẢN LƯỢNG';
  const dong = nhom.map((g) => {
    const ct = g.dong.map((r) => `${tenSP(r.san_pham) || '?'}: ${formatNumber(r.so_hop)}`).join(', ');
    return `${g.ten} (${ct})`;
  });
  const tong = nhom.reduce((a, g) => a + g.dong.reduce((x, r) => x + (Number(r.so_hop) || 0), 0), 0);
  return `${tieuDe}\n${dong.join('\n')}\n— Tổng: ${formatNumber(tong)} sản phẩm`;
}

function copySanLuong(nhom, ngay, tenSP) {
  if (!nhom.some((g) => g.dong.some((r) => r.nhan_vien !== CONG_NHAT))) {
    toastErr('Chưa có dòng công khoán nào để copy.'); return;
  }
  chepVaoClipboard(vanBanSanLuong(nhom, ngay, tenSP));
}

/** Copy kiểu cũ (execCommand) — chạy được cả khi trang mở bằng http hoặc trình
 *  duyệt chặn Clipboard API, là chuyện thường trên điện thoại xưởng. */
function chepKieuCu(text) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.setAttribute('readonly', '');
  ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0;';
  document.body.appendChild(ta);
  ta.select();
  ta.setSelectionRange(0, text.length);
  let ok = false;
  try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
  ta.remove();
  return ok;
}

function chepVaoClipboard(text) {
  const xong = () => toast('Đã copy — dán vào nhóm chat.');
  const duPhong = () => (chepKieuCu(text) ? xong() : hienDeChepTay(text));
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(xong, duPhong);
    return;
  }
  duPhong();
}

function hienDeChepTay(text) {
  const m = openModal({ title: 'Copy sản lượng' });
  m.body.innerHTML = `
    <div class="sx-modal-msg">Bấm giữ để chọn rồi copy:</div>
    <textarea class="sx-textarea" id="sx-cp-text" rows="10" readonly></textarea>
  `;
  const ta = m.body.querySelector('#sx-cp-text');
  ta.value = text;
  ta.focus();
  ta.select();
}
