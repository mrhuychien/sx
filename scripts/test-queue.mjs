globalThis.localStorage = (() => { let m = {}; return {
  getItem: k => (k in m ? m[k] : null), setItem: (k,v) => { m[k] = String(v); },
  removeItem: k => { delete m[k]; } }; })();
let _on = false;
Object.defineProperty(globalThis, 'navigator', {
  configurable: true, get: () => ({ onLine: _on }),
});
const setOn = (v) => { _on = v; };

const q = await import('/home/user/sx/sx/public/sx/lib/queue.js');

const an_toan = ['sx.api.portal.bao_me','sx.api.portal.bao_can',
                 'sx.api.portal.luu_bang_vao_hop','sx.api.portal.ghi_su_co'];
const chan = ['sx.api.chot.chot_ngay','sx.api.chot.huy_chot_ngay',
              'sx.api.tang1.xuat_kho_dau','sx.api.tang1.hoan_tat_cong_doan'];
for (const m of an_toan) if (!q.xepHangDuoc(m)) throw new Error('phải xếp hàng được: '+m);
for (const m of chan) if (q.xepHangDuoc(m)) throw new Error('KHÔNG được xếp hàng: '+m);
for (const m of chan) if (!q.lyDoChan(m).length) throw new Error('thiếu lý do: '+m);
console.log('✓ phân loại 4 an toàn / 4 bị chặn, đều có lý do rõ');

q.xepHang('sx.api.portal.bao_me', {ngay_sx:'D1', dong:[1]});
q.xepHang('sx.api.portal.bao_me', {ngay_sx:'D1', dong:[1,2]});
q.xepHang('sx.api.portal.bao_me', {ngay_sx:'D1', dong:[1,2,3]});
q.xepHang('sx.api.portal.bao_me', {ngay_sx:'D2', dong:[9]});
let ds = q.danhSach();
if (ds.length !== 2) throw new Error('gộp sai, còn '+ds.length);
if (ds.find(x => x.khoa === 'D1').args.dong.length !== 3) throw new Error('không giữ bản CUỐI');
console.log('✓ gộp: 3 lần cùng ngày -> 1 bản (giữ bản cuối); ngày khác giữ riêng');

q.xepHang('sx.api.portal.ghi_su_co', {loai:'A'});
q.xepHang('sx.api.portal.ghi_su_co', {loai:'B'});
if (q.danhSach().filter(x => x.method.endsWith('ghi_su_co')).length !== 2)
  throw new Error('sự cố bị gộp mất');
console.log('✓ sự cố: 2 bản riêng, KHÔNG gộp');

setOn(false);
let kq = await q.guiLai(async () => { throw Object.assign(new Error('x'), {mat_mang:true}); });
if (kq.con_lai !== 4) throw new Error('mất mạng mà hàng bị xoá: '+kq.con_lai);
console.log('✓ mất mạng: hàng giữ nguyên 4, không mất gì');

setOn(true);
let n = 0;
kq = await q.guiLai(async () => { n++; if (n === 2) throw new Error('Ngày đã chốt'); });
if (kq.da_gui !== 3 || kq.loi !== 1) throw new Error('sai: '+JSON.stringify(kq));
const conLoi = q.danhSach().filter(x => x.loi);
if (conLoi.length !== 1 || conLoi[0].loi !== 'Ngày đã chốt')
  throw new Error('lỗi nghiệp vụ không được giữ kèm nguyên văn');
console.log('✓ server từ chối: GIỮ LẠI kèm lý do "Ngày đã chốt", không xoá âm thầm');
console.log('✓ trạng thái cuối:', JSON.stringify(q.trangThai()));
