// #/qc/dvgh — động vật gây hại theo trạm (W15, D140). #/qc/dvgh/R05 mở thẳng phiếu trạm
// R05: đó là URL in trên tem QR dán ở trạm, camera điện thoại quét là vào.
//
// Ghi KHI THẤY dấu hiệu — không bắt QC bấm "không có" cho 40 trạm mỗi tuần: tuần nào một
// trạm không có dòng nào thì BM.PRP.03 in "Không" cho trạm đó. Cùng khu có dấu hiệu hai
// tuần liền → nhắc gọi đơn vị dịch vụ (đầu màn này + hộp nhắc màn Hôm nay). Luật nằm ở
// sx/qc/dong_vat.py; màn này chỉ ghi và xem.

import { el, esc } from '/assets/sx/sx/lib/dom.js';
import { toast, toastErr } from '/assets/sx/sx/components/toast.js';
import { confirm2Step, openModal } from '/assets/sx/sx/components/modal.js';
import { moQuet } from '/assets/sx/sx/components/quet.js';
import { moTrangInTram } from '/assets/sx/sx/lib/inthe.js';
import { chip, khungTrong } from '/assets/sx/sx/components/qcui.js';

// Tuần đang xem (theo một ngày bất kỳ trong tuần). null = tuần này. Để ngoài render:
// in xong quay lại không mất tuần đang xem.
const st = { ngay: null };

const ngayVN = (s) => (s ? `${s.slice(8, 10)}/${s.slice(5, 7)}` : '');

/** "r5" / "R05" / ".../sx#/qc/dvgh/R05" → "R05"; không ra mã → "". Cùng luật với
 *  dong_vat.ma_tram (Python) — mã gõ tay và mã quét đi chung một đường. */
export function maTram(q) {
  const m = String(q || '').trim().toUpperCase().match(/([RC])\s*0*(\d{1,2})\s*$/);
  return m ? `${m[1]}${String(Number(m[2])).padStart(2, '0')}` : '';
}

function congNgay(iso, n) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
}

export async function render(api) {
  const { container, call, tham_so } = api;
  const lai = () => render({ ...api, tham_so: null });
  container.innerHTML = '<div class="sx-boot-loading">Đang tải…</div>';
  const dl = await call('sx.api.qc_dvgh.tong_quan', st.ngay ? { ngay: st.ngay } : {});
  container.innerHTML = '';
  const theoMa = Object.fromEntries(dl.tram.map((t) => [t.ma, t]));
  const ghi = (ma) => moGhi(theoMa[ma], dl, api, lai);

  // ── đầu màn: tuần đang xem, lùi / tiến ───────────────────────────────
  const top = el('div', 'sx-qc-top sx-dv-tuan');
  const lui = el('button', 'sx-btn sx-btn-ghost', '‹');
  lui.type = 'button';
  lui.title = 'Tuần trước';
  lui.addEventListener('click', () => { st.ngay = congNgay(dl.tuan_tu, -7); lai(); });
  const tien = el('button', 'sx-btn sx-btn-ghost', '›');
  tien.type = 'button';
  tien.title = 'Tuần sau';
  const tuanNay = dl.tuan_den >= dl.hom_nay;
  tien.disabled = tuanNay;
  tien.addEventListener('click', () => {
    const t = congNgay(dl.tuan_tu, 7);
    st.ngay = t > dl.hom_nay ? null : t;
    lai();
  });
  const giua = el('div', 'sx-dv-tuan-ten', `<div class="sx-qc-ngay">🐀 Động vật gây hại</div>
    <div class="sx-qc-ai">Tuần ${esc(ngayVN(dl.tuan_tu))} – ${esc(ngayVN(dl.tuan_den))}${
  tuanNay ? ' · tuần này' : ' · <b>tuần cũ</b>'}</div>`);
  top.appendChild(lui);
  top.appendChild(giua);
  top.appendChild(tien);
  container.appendChild(top);

  // ── khu có dấu hiệu hai tuần liền ────────────────────────────────────
  if (dl.canh_bao.length) {
    const box = el('div', 'sx-qc-nhac');
    dl.canh_bao.forEach((k) => {
      const o = el('div', 'sx-qc-nhac-o sx-qc-nhac-cao');
      o.innerHTML = `<div class="sx-qc-nhac-ten">⚠ ${esc(k.khu)}: dấu hiệu hai tuần liền</div>
        <div class="sx-qc-nhac-ct">Trạm ${esc(k.tram.join(', '))} — tuần ${esc(ngayVN(k.tuan[0]))} và
        tuần ${esc(ngayVN(k.tuan[1]))}. Xử lý tại chỗ không ăn — gọi đơn vị dịch vụ.</div>`;
      box.appendChild(o);
    });
    container.appendChild(box);
  }

  // ── quét tem / gõ mã ─────────────────────────────────────────────────
  if (dl.duoc_ghi) {
    const quet = el('button', 'sx-btn sx-btn-primary sx-btn-big', '⌗ QUÉT TEM TRẠM');
    quet.type = 'button';
    quet.addEventListener('click', () => moQuet({
      loai: 'tram', title: 'Quét tem trạm', kicker: 'ĐỘNG VẬT GÂY HẠI',
      // Tem chứa URL .../sx#/qc/dvgh/R05 — lấy mã ở cuối, không khớp nguyên chuỗi.
      tra: (k) => (theoMa[maTram(k)] ? maTram(k) : undefined),
      onTim: (ma) => ghi(ma),
    }));
    container.appendChild(quet);
    const go = el('div', 'sx-dv-go');
    const inp = el('input', 'sx-textarea');
    inp.placeholder = 'hoặc gõ mã trạm: R5, C12…';
    inp.setAttribute('autocomplete', 'off');
    inp.setAttribute('autocapitalize', 'characters');
    const nutGo = el('button', 'sx-btn', 'GHI');
    nutGo.type = 'button';
    const moTay = () => {
      const ma = maTram(inp.value);
      if (!theoMa[ma]) {
        toastErr(`Không có trạm "${inp.value.trim()}" — mã đúng dạng R01–R21, C01–C19.`);
        return;
      }
      inp.value = '';
      ghi(ma);
    };
    nutGo.addEventListener('click', moTay);
    inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); moTay(); } });
    go.appendChild(inp);
    go.appendChild(nutGo);
    container.appendChild(go);
  } else {
    container.appendChild(el('div', 'sx-qc-goiy', 'Bạn chỉ có quyền xem — QC ghi dấu hiệu.'));
  }

  // ── dấu hiệu trong tuần ──────────────────────────────────────────────
  container.appendChild(el('div', 'sx-dv-khu', `Dấu hiệu trong tuần (${dl.phieu_tuan.length})`));
  if (!dl.phieu_tuan.length) {
    container.appendChild(khungTrong('Tuần này chưa ghi dấu hiệu nào — trên BM.PRP.03 mọi trạm là "Không".'));
  }
  dl.phieu_tuan.forEach((p) => container.appendChild(veDong(p, dl, api, lai)));

  // ── trạm theo khu ────────────────────────────────────────────────────
  const nhom = {};
  dl.tram.forEach((t) => { (nhom[t.khu || ''] = nhom[t.khu || ''] || []).push(t); });
  const khu = Object.keys(nhom).sort((a, b) => {
    if (!a || !b) return a ? -1 : (b ? 1 : 0);   // "chưa khai khu" xuống cuối
    return a.localeCompare(b, 'vi');
  });
  khu.forEach((k) => {
    const khoi = el('div', 'sx-dv-nhom');
    khoi.appendChild(el('div', 'sx-dv-khu', esc(k || 'Chưa khai khu')));
    const luoi = el('div', 'sx-dv-luoi');
    nhom[k].forEach((t) => {
      const b = el('button', `sx-dv-tram${t.tuan_nay ? ' sx-dv-tram-co' : ''}`,
        `${esc(t.ma)}<small>${t.tuan_nay ? `${t.tuan_nay} lần` : esc(t.loai === 'Bẫy chuột' ? 'chuột' : 'côn trùng')}</small>`);
      b.type = 'button';
      b.title = [t.vi_tri, t.lan_cuoi ? `ghi gần nhất ${ngayVN(t.lan_cuoi)}` : ''].filter(Boolean).join(' · ');
      b.disabled = !dl.duoc_ghi;
      b.addEventListener('click', () => ghi(t.ma));
      luoi.appendChild(b);
    });
    khoi.appendChild(luoi);
    container.appendChild(khoi);
  });
  if (nhom['']) {
    container.appendChild(el('div', 'sx-qc-goiy', 'Khu / vị trí trạm: Ban ISO khai trên Desk → '
      + 'SX Tram Dong Vat theo sơ đồ đặt trạm. Chưa khai khu thì mỗi trạm tự là một khu khi xét '
      + '"hai tuần liền".'));
  }

  // ── in ───────────────────────────────────────────────────────────────
  const thang = dl.tuan_tu.slice(0, 7);
  const inBtn = (nhan, fn) => {
    const b = el('button', 'sx-btn sx-btn-ghost', esc(nhan));
    b.type = 'button';
    b.addEventListener('click', fn);
    container.appendChild(b);
  };
  inBtn(`🖨 IN BM.PRP.03 — tuần ${ngayVN(dl.tuan_tu)}–${ngayVN(dl.tuan_den)}`,
    () => inTo(api, 'sx.api.qc_dvgh.in_prp03', { ngay: dl.tuan_tu }, 'BM.PRP.03'));
  inBtn(`🖨 IN BM.PRP.01 — tháng ${thang.slice(5)}/${thang.slice(0, 4)}`,
    () => inTo(api, 'sx.api.qc_dvgh.in_prp01', { thang }, 'BM.PRP.01'));
  inBtn(`🖨 IN TEM QR TRẠM (${dl.tram.length} tem)`, () => {
    const goc = `${window.location.origin}/sx#/qc/dvgh/`;
    if (!moTrangInTram(dl.tram.map((t) => ({ ...t, url: `${goc}${t.ma}` })))) {
      toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.');
    }
  });

  // ── #/qc/dvgh/R05: tem vừa quét bằng camera → mở phiếu trạm đó ──────────
  if (tham_so) {
    // Bỏ mã trạm khỏi địa chỉ (không phát hashchange): ghi xong tải lại màn thì không
    // tự mở lại phiếu, và nút Back không quay về một phiếu đã ghi.
    try { window.history.replaceState(null, '', '#/qc/dvgh'); } catch (e) { /* bỏ qua */ }
    const ma = maTram(tham_so);
    if (theoMa[ma]) ghi(ma);
    else toastErr(`Không có trạm "${tham_so}" (hoặc trạm đã ngừng dùng).`);
  }
}

function veDong(p, dl, api, lai) {
  const the = el('div', 'sx-qc-sc sx-qc-sc-mo');
  the.appendChild(el('div', 'sx-qc-sc-ten',
    `${esc(p.tram)} · ${esc(p.dau_hieu)}${p.so_luong ? ` · ${esc(p.so_luong)}` : ''}`));
  const meta = el('div', 'sx-qc-sc-meta');
  meta.appendChild(el('span', null, esc(ngayVN(p.ngay))));
  meta.appendChild(chip(p.khu || 'chưa khai khu'));
  meta.appendChild(el('span', null, esc(p.nguoi_ghi)));
  the.appendChild(meta);
  if (p.xu_ly) the.appendChild(el('div', 'sx-qc-goiy', `Xử lý: ${esc(p.xu_ly)}`));
  // Người ghi xoá được trong ngày (ghi nhầm trạm); Ban ISO lúc nào cũng xoá được. Server
  // chốt lại đúng luật này — nút chỉ hiện cho người sẽ được phép.
  if (dl.la_iso || (p.nguoi_ghi === dl.user && p.ngay === dl.hom_nay)) {
    const nut = el('div', 'sx-qc-chips');
    const xoa = el('button', 'sx-btn sx-btn-ghost', 'XOÁ (ghi nhầm)');
    xoa.type = 'button';
    xoa.addEventListener('click', () => confirm2Step({
      title: `Xoá dấu hiệu ${p.tram} ngày ${ngayVN(p.ngay)}?`,
      message: 'Chỉ xoá khi ghi nhầm (nhầm trạm, nhầm ngày). Dấu hiệu thật thì giữ — BM.PRP.03 cần nó.',
      confirmLabel: 'XOÁ',
      onConfirm: async () => {
        await api.call('sx.api.qc_dvgh.xoa_dau_hieu', { name: p.name });
        toast('Đã xoá');
        lai();
      },
    }));
    nut.appendChild(xoa);
    the.appendChild(nut);
  }
  return the;
}

function o(body, nhan, gt, kieu) {
  body.appendChild(el('div', 'sx-qc-goiy', esc(nhan)));
  const n = el(kieu === 'ta' ? 'textarea' : 'input');
  n.className = 'sx-textarea';
  if (kieu === 'ta') n.rows = 2;
  else if (kieu) n.type = kieu;
  n.value = gt || '';
  body.appendChild(n);
  return n;
}

function moGhi(t, dl, api, lai) {
  if (!t) return;
  if (!dl.duoc_ghi) { toastErr('Bạn chỉ có quyền xem — QC ghi dấu hiệu.'); return; }
  const m = openModal({
    kicker: `TRẠM ${t.ma} · ${t.loai || ''}`,
    title: t.khu ? `${t.khu}${t.vi_tri ? ` · ${t.vi_tri}` : ''}` : (t.vi_tri || 'Chưa khai khu'),
  });
  if (t.lan_cuoi) {
    m.body.appendChild(el('div', 'sx-qc-goiy', `Lần ghi gần nhất: ${esc(ngayVN(t.lan_cuoi))}${
      t.tuan_nay ? ` · tuần đang xem đã ghi ${t.tuan_nay} lần` : ''}`));
  }
  // Không chọn sẵn loại dấu hiệu kể cả ở trạm bẫy chuột: chọn sẵn mà QC thấy gián ở trạm R
  // rồi quên đổi thì sổ ghi sai; để trống thì quên là bị nhắc ngay.
  let dauHieu = '';
  m.body.appendChild(el('div', 'sx-qc-goiy', 'Thấy gì? (bắt buộc)'));
  const vi = el('div', 'sx-qc-vi');
  dl.dau_hieu.forEach((x) => {
    const b = el('button', 'sx-qc-vi-o', esc(x));
    b.type = 'button';
    b.addEventListener('click', () => {
      dauHieu = x;
      vi.querySelectorAll('button').forEach((n) => n.classList.toggle('sx-qc-vi-on', n === b));
    });
    vi.appendChild(b);
  });
  m.body.appendChild(vi);
  const sl = o(m.body, 'Số lượng (con / vết) — đếm được thì ghi', '', 'number');
  sl.min = '0';
  sl.inputMode = 'numeric';
  const xl = o(m.body, 'Xử lý tại chỗ (thay mồi, dọn, bịt lỗ, báo bảo trì…)', '', 'ta');
  const ng = o(m.body, 'Ngày thấy (ghi bù từ giấy thì chọn ngày cũ)', dl.hom_nay, 'date');
  ng.max = dl.hom_nay;
  const ok = el('button', 'sx-btn sx-btn-primary sx-btn-big', 'GHI DẤU HIỆU');
  ok.type = 'button';
  ok.addEventListener('click', async () => {
    if (!dauHieu) { toastErr('Chọn loại dấu hiệu.'); return; }
    if (sl.value && Number(sl.value) < 0) { toastErr('Số lượng không âm.'); return; }
    ok.disabled = true;
    try {
      const r = await api.call('sx.api.qc_dvgh.ghi_dau_hieu', {
        payload: JSON.stringify({
          tram: t.ma, dau_hieu: dauHieu, so_luong: sl.value, xu_ly: xl.value.trim(),
          ngay: ng.value || dl.hom_nay,
        }),
      });
      toast(`Đã ghi ${r.tram}${r.khu ? ` · ${r.khu}` : ''}`);
      m.close();
      // Ghi bù ngày cũ → nhảy sang tuần đó cho thấy dòng vừa ghi.
      st.ngay = ng.value && ng.value !== dl.hom_nay ? ng.value : null;
      lai();
    } catch (e) { ok.disabled = false; toastErr(e.message); }
  });
  m.body.appendChild(ok);
}

// Cửa sổ mới, tự khai charset (about:blank không thừa kế) — cùng cách in BM.11.01.
async function inTo(api, method, args, ten) {
  try {
    const html = await api.call(method, args);
    const w = window.open('', '_blank');
    if (!w) { toastErr('Trình duyệt chặn cửa sổ in. Cho phép pop-up rồi thử lại.'); return; }
    w.document.write(`<!doctype html><html lang="vi"><head><meta charset="utf-8">`
      + `<title>${esc(ten)}</title></head><body>${html}</body></html>`);
    w.document.close();
    w.focus();
    setTimeout(() => w.print(), 250);
  } catch (e) { toastErr(e.message); }
}
