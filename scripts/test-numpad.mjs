// Bàn số: phím đầu tiên GHI ĐÈ số điền sẵn.
//
// Vì sao bài này đáng có: mọi chỗ gọi bàn số trong app đều điền sẵn giá trị hiện
// tại (tồn kg, số mẻ, số hộp, nhiệt độ rang) vì người dùng cần thấy số cũ. Nếu
// phím số gõ NỐI vào đuôi thì tồn 120, gõ 50, ra 12050 — không lỗi nào hiện ra,
// chỉ là một con số vô lý đi thẳng vào sổ kho hoặc vào hồ sơ chất lượng.
//
// Nạp hàm THẬT từ components/numpad.js, không chép logic sang đây.
//
// Chạy: node scripts/test-numpad.mjs   (verify.sh gọi sẵn)

import { readFileSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

// numpad.js import dom.js + modal.js (chỉ đụng document BÊN TRONG hàm), nên cắt
// hai dòng import đó ra là nạp được trong node.
const goc = readFileSync('sx/public/sx/components/numpad.js', 'utf8')
  .split('\n').filter((d) => !d.startsWith('import ')).join('\n');
const tam = join(tmpdir(), `np-${process.pid}.mjs`);
writeFileSync(tam, goc);
const { bamPhim } = await import(`file://${tam}`);
rmSync(tam);

let hong = 0;
function kiem(ten, dk, ct = '') {
  if (!dk) hong += 1;
  console.log(`  ${dk ? 'ok  ' : 'HỎNG'} ${ten}${ct ? ` — ${ct}` : ''}`);
}

/** Gõ một chuỗi phím từ trạng thái vừa mở bàn số với `initial`. */
function go(initial, phim) {
  let v = String(initial ?? '');
  let chuaGo = v !== '';
  for (const k of phim) {
    v = bamPhim(v, k, chuaGo);
    chuaGo = false;
  }
  return v;
}

console.log('-- phím số đầu tiên ghi đè số điền sẵn --');
kiem('tồn 120, gõ 50 → 50 (KHÔNG phải 12050)', go(120, ['5', '0']) === '50',
  go(120, ['5', '0']));
kiem('nhiệt 248, gõ 265 → 265', go(248, ['2', '6', '5']) === '265',
  go(248, ['2', '6', '5']));
kiem('mở ra trống, gõ 7 → 7', go('', ['7']) === '7');
kiem('gõ tiếp sau phím đầu thì NỐI như thường', go(120, ['5', '0', '0']) === '500');

console.log('\n-- vẫn sửa được số cũ khi muốn --');
kiem('bấm ⌫ trước → xoá một chữ số của số cũ', go(248, ['⌫']) === '24');
kiem('⌫ rồi gõ số → nối vào phần còn lại', go(248, ['⌫', '9']) === '249');
kiem('C xoá sạch', go(248, ['C']) === '');
kiem('C rồi gõ → số mới', go(248, ['C', '3', '0']) === '30');
kiem('⌫ hết sạch rồi gõ → số mới', go(12, ['⌫', '⌫', '9']) === '9');

console.log('\n-- số thập phân --');
kiem('vòng quay 6.8, gõ 7,2 → 7.2', go(6.8, [',']) === '0.'
  ? go(6.8, ['7', ',', '2']) === '7.2' : false, go(6.8, ['7', ',', '2']));
kiem('dấu phẩy ngay khi vừa mở → 0. (không nối vào số cũ)',
  go(6.8, [',']) === '0.', go(6.8, [',']));
kiem('không cho hai dấu phẩy', go('', ['1', ',', '5', ',']) === '1.5');

console.log('\n-- chặn số dài vô hạn --');
kiem('tối đa 9 chữ số', go('', '1234567890123'.split('')).replace('.', '').length === 9,
  go('', '1234567890123'.split('')));

// ── chỗ nối dây ────────────────────────────────────────────────────────
// Mấy bài trên kiểm hàm THUẦN bamPhim(). Hàm đúng mà openNumpad() nối dây sai
// thì vẫn hỏng y như cũ — và bài kiểm vẫn xanh, vì nó tự tính lấy cờ `chuaGo`.
// Đây là kiểm phần nối dây: đọc thẳng mã nguồn. Thô, nhưng thô còn hơn không có.
console.log('\n-- openNumpad nối dây đúng cờ ghi đè --');
kiem('khởi tạo chuaGo theo giá trị điền sẵn',
  /let chuaGo = value !== ''/.test(goc));
kiem('gọi bamPhim với cờ đó', /value = bamPhim\(value, k, chuaGo\)/.test(goc));
kiem('và hạ cờ sau MỖI phím (⌫ và C là ý định sửa số cũ)',
  /bamPhim\(value, k, chuaGo\);[\s\S]{0,200}?chuaGo = false;/.test(goc));

console.log(hong ? `NUMPAD-FAIL (${hong} ca)` : 'NUMPAD-OK');
process.exit(hong ? 1 : 0);
