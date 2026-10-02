// Card lịch tháng của tab Ghi hộp (D108) — xem components/lichthang.js.
import { renderLich } from '/assets/sx/sx/components/lichthang.js';

export function render(api) {
  return renderLich(api, { loai: 'vaohop', tieuDe: 'Ghi hộp cả tháng', moNgay: true });
}
