// #/qc/truyxuat — thẻ Truy xuất ngay trong màn QC, cho Ban ISO (W06, D132).
//
// Ban ISO là người diễn tập truy xuất (BM.02.04) nhưng không vào màn Quản lý. Dùng
// lại NGUYÊN thẻ truy xuất của Quản lý — một chỗ code, hai cửa vào. Quyền gọi API
// chốt ở sx/config/roles.py (CARD_ROLES["truyxuat"]).

export async function render(api) {
  const { render: veThe } = await import(`/assets/sx/sx/cards/truyxuat.js?v=${encodeURIComponent(
    (api.ctx && api.ctx.assetVersion) || Date.now())}`);
  const box = document.createElement('div');
  api.container.appendChild(box);
  await veThe({ ...api, container: box });
}
