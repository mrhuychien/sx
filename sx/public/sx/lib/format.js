// Format tập trung — số, tiền VND, giờ phút.

export function formatNumber(n, decimals = 0) {
  const v = Number(n || 0);
  return v.toLocaleString('vi-VN', {
    maximumFractionDigits: decimals,
    minimumFractionDigits: 0,
  });
}

export function formatVND(n) {
  return `${formatNumber(Math.round(Number(n || 0)))} đ`;
}

export function formatKg(n) {
  return `${formatNumber(n, 2)} kg`;
}

export function formatTime(dt) {
  if (!dt) return '';
  const d = new Date(String(dt).replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return String(dt);
  return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

export function phutTuLuc(dt) {
  const d = new Date(String(dt).replace(' ', 'T'));
  if (Number.isNaN(d.getTime())) return null;
  return Math.floor((Date.now() - d.getTime()) / 60000);
}

// "2026-07-29" -> "29/07". Không dùng Date (tránh lệch múi giờ khi chỉ có ngày).
export function nhanNgay(boot) {
  const iso = (boot && (boot.ngay_xem || boot.hom_nay)) || '';
  const d = iso.split('-');
  if (d.length !== 3) return '';
  return (boot && boot.la_hom_nay) ? 'hôm nay' : `ngày ${d[2]}/${d[1]}`;
}
