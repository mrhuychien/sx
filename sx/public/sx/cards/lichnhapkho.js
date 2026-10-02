// Card lịch tháng của tab Nhập kho (D108) — xem components/lichthang.js.
import { renderLich } from '/assets/sx/sx/components/lichthang.js';

export function render(api) {
  return renderLich(api, { loai: 'nhapkho', tieuDe: 'Nhập kho cả tháng', moNgay: false });
}
