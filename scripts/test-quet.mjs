// Kiểm vungNgam(): quy ô ngắm trên màn về đúng vùng trong khung hình camera.
//
// Vì sao phải có bài này (D77): video vẽ bằng object-fit:cover nên khung hình bị cắt
// bớt MỘT chiều khi hiển thị. Quên trừ phần bị cắt thì bộ đọc mã cắt lệch — đọc vào
// chỗ trống bên cạnh cái mã, và triệu chứng y hệt "camera mờ": soi mãi không ăn,
// không có lỗi nào hiện ra. Sai lệch thầm lặng thì phải chặn bằng test.
//
// Chạy: node scripts/test-quet.mjs   (verify.sh gọi sẵn)
//
// Nạp hàm THẬT từ file nguồn (bỏ import, bỏ export, dựng lại bằng new Function).

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const goc = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const src = fs.readFileSync(path.join(goc, 'sx/public/sx/components/quet.js'), 'utf8')
  .replace(/^import .*?;$/gm, '')
  .replace(/^export /gm, '');
const { vungNgam } = new Function(`${src}\nreturn { vungNgam };`)();

const R = (left, top, width, height) => ({ left, top, width, height });
let hong = 0;
function kiem(ten, dk, ct = '') {
  if (!dk) hong++;
  console.log(`  ${dk ? 'ok  ' : 'HỎNG'} ${ten}${ct ? ` — ${ct}` : ''}`);
}
const gan = (a, b) => Math.abs(a - b) < 0.51;

// ── A. Khung hình 16:9 vẽ vào ô 4:3 -> cover cắt hai bên TRÁI/PHẢI ──
// video 1920x1080, ô hiển thị 360x270. ti = max(360/1920, 270/1080) = 0.25
// -> ảnh vẽ ra 480x270, thừa 120px ngang, mỗi bên 60px bị cắt.
{
  const rC = R(0, 0, 360, 270);
  const rO = R(126, 81, 108, 108);            // ô ngắm vuông giữa màn
  const v = vungNgam(1920, 1080, rC, rO);
  kiem('cover cắt ngang: sx trừ đúng phần bị cắt',
    gan(v.sx, (126 + 60) / 0.25), `sx=${v.sx.toFixed(1)} mong ${(186 / 0.25).toFixed(1)}`);
  kiem('sy không bị trừ (chiều dọc vừa khít)',
    gan(v.sy, 81 / 0.25), `sy=${v.sy.toFixed(1)}`);
  kiem('sw = bề rộng ô ngắm quy về khung hình',
    gan(v.sw, 108 / 0.25), `sw=${v.sw.toFixed(1)}`);
  kiem('vùng cắt nằm gọn trong khung hình',
    v.sx >= 0 && v.sy >= 0 && v.sx + v.sw <= 1920 + 0.5 && v.sy + v.sh <= 1080 + 0.5);
  // Tâm ô ngắm phải rơi đúng tâm khung hình
  kiem('tâm vùng cắt = tâm khung hình', gan(v.sx + v.sw / 2, 960) && gan(v.sy + v.sh / 2, 540),
    `tâm=(${(v.sx + v.sw / 2).toFixed(0)}, ${(v.sy + v.sh / 2).toFixed(0)})`);
}

// ── B. Khung hình 4:3 vẽ vào ô 16:9 -> cover cắt TRÊN/DƯỚI ──
// video 1600x1200, ô 320x180. ti = max(320/1600, 180/1200) = 0.2 -> ảnh 320x240,
// thừa 60px dọc, mỗi bên 30px.
{
  const rC = R(0, 0, 320, 180);
  const rO = R(48, 45, 224, 90);              // ô ngắm rộng (quét hộp)
  const v = vungNgam(1600, 1200, rC, rO);
  kiem('cover cắt dọc: sy trừ đúng phần bị cắt',
    gan(v.sy, (45 + 30) / 0.2), `sy=${v.sy.toFixed(1)} mong ${(75 / 0.2).toFixed(1)}`);
  kiem('sx không bị trừ', gan(v.sx, 48 / 0.2), `sx=${v.sx.toFixed(1)}`);
  kiem('tâm vùng cắt = tâm khung hình', gan(v.sx + v.sw / 2, 800) && gan(v.sy + v.sh / 2, 600),
    `tâm=(${(v.sx + v.sw / 2).toFixed(0)}, ${(v.sy + v.sh / 2).toFixed(0)})`);
  kiem('ô ngắm rộng -> vùng cắt cũng rộng, không vuông', v.sw > v.sh * 2);
}

// ── C. Ô video lệch khỏi gốc màn (modal nằm giữa trang) ──
{
  const v0 = vungNgam(1920, 1080, R(0, 0, 360, 270), R(126, 81, 108, 108));
  const v1 = vungNgam(1920, 1080, R(40, 300, 360, 270), R(166, 381, 108, 108));
  kiem('dời cả video lẫn ô ngắm -> vùng cắt không đổi',
    gan(v0.sx, v1.sx) && gan(v0.sy, v1.sy) && gan(v0.sw, v1.sw) && gan(v0.sh, v1.sh));
}

// ── D. Số đo chưa sẵn sàng -> đọc CẢ khung, không cắt bừa ──
{
  for (const [ten, W, H, rC, rO] of [
    ['video chưa có kích thước', 0, 0, R(0, 0, 360, 270), R(1, 1, 10, 10)],
    ['ô video chưa layout', 1920, 1080, R(0, 0, 0, 0), R(0, 0, 0, 0)],
    ['ô ngắm bé xíu', 1920, 1080, R(0, 0, 360, 270), R(180, 135, 1, 1)],
    ['thiếu rO', 1920, 1080, R(0, 0, 360, 270), null],
  ]) {
    const v = vungNgam(W, H, rC, rO);
    kiem(`${ten} -> đọc cả khung`, v.sx === 0 && v.sy === 0 && v.sw === W && v.sh === H,
      `(${v.sx}, ${v.sy}, ${v.sw}, ${v.sh})`);
  }
}

// ── E. Cắt phải GIỮ ĐƯỢC điểm ảnh, không phải thu nhỏ cả khung ──
{
  const v = vungNgam(1920, 1080, R(0, 0, 360, 270), R(126, 81, 108, 108));
  // Cách cũ: thu cả 1920 về 480 -> ô ngắm 62% còn ~298px.
  // Cách mới: cắt ô ngắm (432px) rồi mới thu về tối đa 720 -> giữ nguyên 432px.
  kiem('vùng ô ngắm giữ nhiều điểm ảnh hơn cách thu nhỏ cả khung',
    v.sw > 480 * 0.62, `sw=${v.sw.toFixed(0)}px vs cách cũ ~${(480 * 0.62).toFixed(0)}px`);
}

console.log(hong ? `QUET-FAIL (${hong} ca)` : 'QUET-OK');
process.exit(hong ? 1 : 0);
