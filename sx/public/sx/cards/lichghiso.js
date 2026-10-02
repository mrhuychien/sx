// Card lịch tháng của tab Ghi sổ (D108) — xem components/lichthang.js.
import { renderLich } from '/assets/sx/sx/components/lichthang.js';

export function render(api) {
  return renderLich(api, { loai: 'ghiso', tieuDe: 'Ghi sổ cả tháng', moNgay: true });
}
