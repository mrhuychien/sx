// Đo tốc độ tải (D210) — bật bằng ?do=1 trên địa chỉ trang: /sx?do=1#/nhapkho. Không có ?do=1 thì không làm gì.
//
// "Cảm giác chậm" có thể nằm ở bốn chỗ khác nhau, sửa mỗi chỗ một kiểu: máy chủ tính lâu (trong đó SQL bao nhiêu câu,
// bao lâu — header Server-Timing do sx/do_toc.py ghi), đường truyền, tải mã JS / CSS (tải mới, hỏi lại máy chủ hay lấy
// từ bộ nhớ đệm của máy), hay một thẻ chờ thẻ khác. Vẽ xong màn thì hiện bảng ở chân màn — nút CHÉP để gửi nguyên văn.
// Số lấy từ Resource Timing của trình duyệt (đo đúng từng yêu cầu thật), không tự bấm giờ quanh fetch.

export const DO = /[?&]do=1(?:&|$)/.test((window.location || {}).search || '');
if (DO) { try { performance.setResourceTimingBufferSize(3000); } catch (e) { /* trình duyệt cũ: 250 mục là đủ */ } }

let man = { ten: '', bd: 0, lan: 0 };
const the = [];
const dangVe = new Set();

/** Router bắt đầu vẽ một màn. */
export function batDauMan(ten) {
  if (!DO) return;
  man = { ten, bd: man.lan ? performance.now() : 0, lan: man.lan + 1 };   // lần đầu: tính từ lúc mở trang
  the.length = 0;
}

/** Bọc việc gắn một thẻ: ghi lúc bắt đầu, nạp mã xong, vẽ xong. `nap` = hàm nạp module, `ve` = hàm vẽ (nhận module). */
export async function doThe(ten, nap, ve) {
  if (!DO) return ve(await nap());
  const x = { ten, bd: performance.now(), nap: 0, xong: 0, loi: '' };
  const p = (async () => {
    try {
      const mod = await nap();
      x.nap = performance.now();
      return await ve(mod);
    } catch (e) {
      x.loi = String((e && e.message) || e);
      throw e;
    } finally {
      x.xong = performance.now();
      the.push(x);
    }
  })();
  dangVe.add(p);
  try { return await p; } finally { dangVe.delete(p); }
}

const so = (n) => Math.round(n).toLocaleString('vi-VN');
const kb = (b) => `${(b / 1024).toFixed(b < 10240 ? 1 : 0).replace('.', ',')} KB`;
const st = (e, ten) => (e.serverTiming || []).find((s) => s.name === ten);

/** Các dòng đo của màn vừa vẽ — chữ thuần, để in ra bảng và để chép gửi đi. Hàm thuần trên các mục Resource Timing. */
export function tomTat({ ten, bd, build, xong, nav, tainguyen, the: dsThe }) {
  const ra = [`⏱ ĐO TỐC ĐỘ — màn ${ten} — ${build} — ${new Date().toLocaleString('vi-VN')}`];
  if (nav) {
    const sv = st(nav, 'sx');
    const sql = st(nav, 'sql');
    ra.push(`Trang HTML: nhận xong ${so(nav.responseEnd)} ms sau lúc mở${sv ? ` · máy chủ ${so(sv.duration)} ms` : ''}${
      sql ? ` (SQL ${sql.description || '?'} câu, ${so(sql.duration)} ms)` : ''}`);
  }
  ra.push(`Màn vẽ đủ: ${so(xong - bd)} ms ${bd ? 'sau lúc bấm chuyển màn' : 'sau lúc mở trang'}`);
  const tep = tainguyen.filter((e) => /\/assets\/.+\.(js|css)(\?|$)/.test(e.name) && e.startTime >= bd);
  if (tep.length) {
    const dem = { moi: 0, hoi: 0, dem: 0 };
    let tai = 0;
    tep.forEach((e) => {
      if (!e.transferSize) dem.dem += 1;                                  // bộ nhớ đệm của máy
      else if (e.transferSize < e.encodedBodySize || e.transferSize < 600) dem.hoi += 1;   // 304: hỏi lại máy chủ
      else { dem.moi += 1; tai += e.transferSize; }
    });
    const cham = tep.reduce((a, e) => (e.duration > a.duration ? e : a));
    ra.push(`JS/CSS: ${tep.length} tệp · ${dem.moi} tải mới (${kb(tai)}) · ${dem.hoi} hỏi lại máy chủ · `
      + `${dem.dem} từ bộ nhớ đệm · chậm nhất ${cham.name.split('/assets/sx/sx/').pop().split('?')[0]} `
      + `${so(cham.duration)} ms`);
  }
  const api = tainguyen.filter((e) => e.name.includes('/api/method/') && e.startTime >= bd)
    .sort((a, b) => b.duration - a.duration);
  if (api.length) {
    ra.push(`API (${api.length} lời gọi, chậm nhất trước): tổng · máy chủ · SQL · cỡ`);
    api.forEach((e) => {
      const sv = st(e, 'sx');
      const sql = st(e, 'sql');
      const m = e.name.split('/api/method/').pop().split('?')[0].replace(/^sx\.api\./, '');
      const sqlChu = sql ? `${sql.description || '?'} câu ${so(sql.duration)} ms` : '—';
      ra.push(`  ${so(e.duration).padStart(6)} ms · ${sv ? `${so(sv.duration)} ms` : '—'} · ${sqlChu} · `
        + `${kb(e.encodedBodySize || e.transferSize || 0)}  ${m}`);
    });
  }
  if (dsThe.length) {
    ra.push('Thẻ (vẽ xong lúc · nạp mã):');
    [...dsThe].sort((a, b) => a.xong - b.xong).forEach((x) => {
      ra.push(`  ${so(x.xong - bd).padStart(6)} ms · ${so(x.nap ? x.nap - x.bd : 0)} ms  ${x.ten}${x.loi
        ? ` — LỖI: ${x.loi}` : ''}`);
    });
  }
  return ra;
}

/** Màn vẽ xong (router): chờ các thẻ còn đang vẽ, rồi hiện bảng đo. */
export async function xongMan(build) {
  if (!DO) return;
  await Promise.allSettled([...dangVe]);
  const xong = performance.now();
  await new Promise((r) => { setTimeout(r, 50); });           // để mục Resource Timing cuối cùng kịp ghi
  const dong = tomTat({
    ten: man.ten, bd: man.bd, build, xong, the,
    nav: man.lan === 1 ? performance.getEntriesByType('navigation')[0] : null,
    tainguyen: performance.getEntriesByType('resource'),
  });
  hienBang(dong);
}

function hienBang(dong) {
  let hop = document.getElementById('sx-do');
  if (!hop) {
    hop = document.createElement('div');
    hop.id = 'sx-do';
    hop.className = 'sx-do';
    hop.innerHTML = `<div class="sx-do-dau"><b>⏱ Đo tốc độ</b>
      <button type="button" class="sx-btn sx-btn-primary" data-do="chep">CHÉP</button>
      <button type="button" class="sx-btn sx-btn-ghost" data-do="dong" aria-label="Đóng">✕</button></div>
      <pre class="sx-do-chu"></pre>`;
    hop.querySelector('[data-do="dong"]').addEventListener('click', () => hop.remove());
    hop.querySelector('[data-do="chep"]').addEventListener('click', async (e) => {
      const nut = e.currentTarget;                              // sau await thì e.currentTarget đã là null
      const chu = hop.querySelector('.sx-do-chu').textContent;
      try { await navigator.clipboard.writeText(chu); nut.textContent = 'ĐÃ CHÉP'; } catch (er) {
        const r = document.createRange();                       // không chép được (http, quyền): bôi đen để chép tay
        r.selectNodeContents(hop.querySelector('.sx-do-chu'));
        const s = window.getSelection();
        s.removeAllRanges();
        s.addRange(r);
      }
    });
    document.body.appendChild(hop);
  }
  hop.querySelector('[data-do="chep"]').textContent = 'CHÉP';
  hop.querySelector('.sx-do-chu').textContent = dong.join('\n');
}
