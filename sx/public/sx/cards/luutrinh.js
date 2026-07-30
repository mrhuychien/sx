// Card Lưu đồ tầng 1 (D31) — QC ghi sổ theo đúng luồng sản xuất:
//   Đỗ (kho NVL) --Xuất kho đỗ--> Đỗ ở xưởng --Luộc+rang--> ĐỖ Ủ --Tách vỏ--> ĐỖ VỠ
//   --Nghiền--> BỘT NỀN (kho BTP)
// Mỗi lô là 1 hàng; mỗi chặng hiện TỒN THẬT đọc từ kho, không có state phụ.

import { esc, el } from '/assets/sx/sx/lib/dom.js';
import { formatKg, formatNumber, nhanNgay } from '/assets/sx/sx/lib/format.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { openModal } from '/assets/sx/sx/components/modal.js';
import { openNumpad } from '/assets/sx/sx/components/numpad.js';

const NHAN_CD = { rang: 'Luộc + rang', tachvo: 'Tách vỏ', nghien: 'Nghiền bột' };
// Chặng nào là ĐẦU VÀO của công đoạn nào — để biết nút nào bật
const CD_TU_CHANG = { dau: 'rang', u: 'tachvo', vo: 'nghien' };

export async function render({ container, boot, call, refresh }) {
  container.className = 'sx-card';
  container.innerHTML = `
    <div class="sx-field-label">Luồng sản xuất tầng 1 — ${nhanNgay(boot)}</div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-lt-xuat">
      🫘 XUẤT KHO ĐỖ
    </button>
    <div id="sx-lt-ds"><div class="sx-muted">Đang tải lưu đồ…</div></div>
  `;
  container.querySelector('#sx-lt-xuat')
    .addEventListener('click', () => openXuatKho(boot, call, refresh));
  await veLuuDo(container.querySelector('#sx-lt-ds'), boot, call, refresh);
}

async function veLuuDo(box, boot, call, refresh) {
  let r;
  try {
    r = await call('sx.api.tang1.luu_do_lo', boot.ngay_xem ? { ngay: boot.ngay_xem } : {});
  } catch (e) {
    box.innerHTML = `<div class="sx-warn-text">${esc(e.message || 'Không đọc được lưu đồ.')}</div>`;
    return;
  }
  const ds = (r && r.lo) || [];
  if (!ds.length) {
    box.innerHTML = '<div class="sx-muted">Không có lô nào đang chạy — lô đã nghiền '
      + 'xong và dùng hết bột thì tự rụng khỏi lưu đồ.</div>';
    return;
  }
  box.innerHTML = ds.map((lo) => veLo(lo)).join('');
  box.querySelectorAll('.sx-lt-btn').forEach((b) => {
    b.addEventListener('click', () => {
      const lo = ds.find((x) => x.name === b.dataset.lo);
      const chang = lo.chang.find((c) => c.chang === b.dataset.chang);
      hoanTat(lo, b.dataset.cd, chang, call, refresh);
    });
  });
}

function veLo(lo) {
  const o = lo.chang.map((c, i) => {
    const cd = CD_TU_CHANG[c.chang];
    const con = Number(c.ton) || 0;
    const bat = cd && con > 0 && !c.thieu_item;
    return `
      ${i ? '<div class="sx-lt-mui" aria-hidden="true"></div>' : ''}
      <div class="sx-lt-o${con > 0 ? ' sx-lt-co' : ''}">
        <div class="sx-lt-nhan">${esc(c.nhan)}</div>
        <div class="sx-lt-ton">${c.thieu_item ? '—' : esc(formatKg(con))}</div>
        ${bat
          ? `<button type="button" class="sx-lt-btn" data-lo="${esc(lo.name)}"
               data-cd="${esc(cd)}" data-chang="${esc(c.chang)}">${esc(NHAN_CD[cd])}</button>`
          : ''}
      </div>`;
  }).join('');
  return `
    <div class="sx-lt-lo">
      <div class="sx-lt-head">
        <b class="sx-lt-ma">${esc(lo.lo_rang)}</b>
        <span class="sx-muted">${esc(lo.loai_dau)} · xuất ${esc(formatKg(lo.dau_kg))}
          · rang ${esc(lo.ngay_rang)}</span>
        ${lo.con_o_xuong > 0
          ? `<span class="sx-lt-tag">còn ${esc(formatKg(lo.con_o_xuong))} ở xưởng</span>`
          : '<span class="sx-lt-tag sx-lt-xong">đã vào kho hết</span>'}
      </div>
      <div class="sx-lt-day">${o}</div>
    </div>`;
}

// Hoàn tất công đoạn: mặc định LẤY HẾT tồn chặng trước; muốn làm một phần thì nhập số
function hoanTat(lo, cd, chang, call, refresh) {
  const m = openModal({ title: `${NHAN_CD[cd]} — lô ${lo.lo_rang}` });
  m.body.innerHTML = `
    <div class="sx-modal-msg">Đang có <b>${esc(formatKg(chang.ton))}</b> ${esc(chang.nhan)}.</div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-lt-het">
      HOÀN TẤT CẢ LÔ (${esc(formatKg(chang.ton))})
    </button>
    <button type="button" class="sx-btn" id="sx-lt-mot-phan">Nhập số cụ thể…</button>
  `;
  const goi = async (kg_vao, kg_ra) => {
    try {
      const kq = await call('sx.api.tang1.hoan_tat_cong_doan', {
        xuat_dau_name: lo.name, cong_doan: cd,
        ...(kg_vao ? { kg_vao } : {}), ...(kg_ra ? { kg_ra } : {}),
      });
      m.close();
      hienKetQua(kq, refresh);
    } catch (e) { toastErr(e.message); }
  };

  // Tỉ lệ hao hụt gợi ý do BACKEND đưa xuống — cùng con số mà nút "hoàn tất cả lô"
  // dùng. Trước đây ô kg RA điền sẵn = kg VÀO, nên nghiền một phần ra bột 1:1 (quên
  // trừ hao); giờ 200 kg đỗ vỡ điền sẵn ~156 kg bột, QC sửa lại theo cân thật.
  const tyLe = Number((lo.cong_doan || []).find((x) => x.ma === cd)?.ty_le) || 1;
  const lam1 = (v) => Math.round(v * 10) / 10;

  m.body.querySelector('#sx-lt-het').addEventListener('click', () => goi(null, null));
  m.body.querySelector('#sx-lt-mot-phan').addEventListener('click', () => {
    openNumpad({
      kicker: `${NHAN_CD[cd]} — kg vào`, title: `Lô ${lo.lo_rang}`,
      unitLabel: 'Số kg', initial: chang.ton, allowDecimal: true, unit: 'kg',
      onOk: (vao) => {
        if (vao <= 0) { toastErr('Số kg phải > 0.'); return; }
        openNumpad({
          kicker: tyLe < 1 ? `Kg ra — định mức ~${formatNumber(lam1(vao * tyLe), 1)} kg` : 'Kg ra',
          title: `Lô ${lo.lo_rang}`,
          unitLabel: 'Cân thật',
          hint: (n) => (n > 0 && vao > 0 ? `hao ${formatNumber(vao - n, 1)} kg` : ''),
          initial: lam1(vao * tyLe), allowDecimal: true, unit: 'kg',
          onOk: (ra) => goi(vao, ra),
        });
      },
    });
  });
}

function hienKetQua(kq, refresh) {
  const m = openModal({ title: `✅ ${kq.cong_doan}` });
  m.body.innerHTML = `
    <div class="sx-lo-big">${esc(kq.batch_ra)}</div>
    <div class="sx-modal-msg">
      ${esc(kq.item_ra)}: <b>${esc(formatKg(kq.kg_ra))}</b>
      ${kq.hao_hut > 0 ? ` · hao hụt ${esc(formatKg(kq.hao_hut))}` : ''}
    </div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-lt-ok">XONG</button>
  `;
  m.body.querySelector('#sx-lt-ok').addEventListener('click', () => { m.close(); refresh(); });
}

function openXuatKho(boot, call, refresh) {
  const loaiDau = boot.loai_dau || [];
  if (!loaiDau.length) { toastErr('Chưa có loại đỗ (cần BOM bột nền trên Desk).'); return; }
  const m = openModal({ title: 'Xuất kho đỗ ra xưởng' });
  const state = { loai_dau: loaiDau[0].name, kg: 0 };
  m.body.innerHTML = `
    <div class="sx-field-label">Loại đỗ</div>
    <div class="sx-sp-grid" id="sx-lt-loai"></div>
    <div class="sx-field-label">Số kg đỗ — bấm để nhập</div>
    <button type="button" class="sx-value-btn" id="sx-lt-kg">0 kg</button>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-lt-ok">XUẤT KHO</button>
  `;
  const grid = m.body.querySelector('#sx-lt-loai');
  loaiDau.forEach((d, i) => {
    const b = el('button', `sx-sp-chip${i === 0 ? ' sx-sp-chip-on' : ''}`);
    b.type = 'button';
    b.textContent = d.item_name || d.name;
    b.addEventListener('click', () => {
      state.loai_dau = d.name;
      grid.querySelectorAll('.sx-sp-chip').forEach((x) => x.classList.remove('sx-sp-chip-on'));
      b.classList.add('sx-sp-chip-on');
    });
    grid.appendChild(b);
  });
  const kgBtn = m.body.querySelector('#sx-lt-kg');
  kgBtn.addEventListener('click', () => {
    openNumpad({
      kicker: 'Xuất kho đỗ', title: state.loai_dau,
      unitLabel: 'Số kg', initial: state.kg, allowDecimal: true, unit: 'kg',
      onOk: (v) => { state.kg = v; kgBtn.textContent = `${formatNumber(v, 1)} kg`; },
    });
  });
  m.body.querySelector('#sx-lt-ok').addEventListener('click', async (e) => {
    if (state.kg <= 0) { toastErr('Nhập số kg đỗ.'); return; }
    e.currentTarget.disabled = true;
    try {
      const r = await call('sx.api.tang1.xuat_kho_dau', {
        loai_dau: state.loai_dau, dau_kg: state.kg,
        ...(boot.la_hom_nay ? {} : { ngay_xuat: boot.ngay_xem }),
      });
      m.close();
      hienLo(r, refresh);
    } catch (err) {
      e.target.disabled = false;
      toastErr(err.message);
    }
  });
}

function hienLo(r, refresh) {
  const m = openModal({ title: 'Đã xuất kho — ghi mã lô ra thẻ' });
  m.body.innerHTML = `
    <div class="sx-lo-big">${esc(r.lo_rang)}</div>
    <div class="sx-modal-msg">Rang ngày ${esc(r.ngay_rang)}. Đỗ đã chuyển sang kho Xưởng.</div>
    <button type="button" class="sx-btn sx-btn-primary sx-btn-big" id="sx-lt-done">XONG</button>
  `;
  m.body.querySelector('#sx-lt-done').addEventListener('click', () => { m.close(); refresh(); });
  toast('Đã tạo phiếu xuất kho.');
}
