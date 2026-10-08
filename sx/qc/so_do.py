"""Số đo theo máy (W16, D142) — nhiệt độ / vòng quay máy rang M1–M3, nhiệt độ hàn máy gói bột.

Mỗi máy ghi riêng trên lượt kiểm từ D100: máy 1 = field gốc, máy k = `<f>_mk`. Ở đây gom
lại theo MÃ MÁY cho Ban ISO xem cuối tháng: mỗi máy bao nhiêu lần đo, thấp nhất / cao nhất,
bao nhiêu lần ngoài ngưỡng. Một máy chạy lệch (lồng rang M2 quay chậm cả tháng) mà gộp chung
với hai máy kia thì trung bình vẫn đẹp — đó là lý do phải tách theo máy.

Chỉ tính ô ÁP DỤNG ở lượt đó (muc.ap_dung: máy đang chạy, bước không nghỉ, có bột…) và đã
ghi (muc.co_ghi) — giá trị cũ còn nằm trong DB của máy đã tắt không được lọt vào số liệu.
Hàm thuần: nhận lượt + ngưỡng đã lấy sẵn.
"""

from sx.qc import muc as M

# (nhóm máy, field gốc, tên, đơn vị, khoá ngưỡng dưới, khoá ngưỡng trên)
DO = (
    ("rang", "rang_nhiet_do", "Nhiệt độ rang", "°C", "rang_nhiet_min", "rang_nhiet_max_van_hanh"),
    ("rang", "rang_vong_quay", "Vòng quay lồng rang", "v/ph", "vong_quay_min", "vong_quay_max"),
    ("goi_bot", "b8_nhiet_han", "Nhiệt độ hàn", "°C", "han_nhiet_min", "han_nhiet_max"),
)


def truong(f, k):
    return f if k == 1 else f"{f}_m{k}"


def can_lay():
    """Các field phải đọc từ SX QC Round để tổng hợp (đủ cho muc.boi_canh)."""
    ra = {"name", "ngay", "luot", "buoc_nghi", "co_san_xuat_bot", "co_lac", "can_thu_lac",
          "can_ve_sinh_sua", "co_sua", "phien_ban"}
    ra |= {t[2] for t in M.NHOM_MAY.values()}
    for nhom, f, *_r in DO:
        ra |= {truong(f, k) for k in range(1, M.NHOM_MAY[nhom][1] + 1)}
    return sorted(ra)


def tong_hop(rounds, ng):
    """[{nhom, ten_nhom, k, may, f, ten, dv, so_lan, thap, cao, duoi, tren, lo, hi}] — mỗi
    (máy, số đo) có ít nhất một lần đo một dòng, theo thứ tự nhóm → máy → số đo."""
    ra = []
    for nhom, ten_nhom_, toi_da in ((n, t[0], t[1]) for n, t in M.NHOM_MAY.items()):
        for k in range(1, toi_da + 1):
            for nh, f, ten, dv, kmin, kmax in DO:
                if nh != nhom:
                    continue
                m = M.THEO_F[truong(f, k)]
                gt = []
                for r in rounds:
                    v = r.get(m["f"])
                    if M.co_ghi(m, v) and M.ap_dung(m, r.get("luot"), M.boi_canh(r)):
                        gt.append(float(v))
                if not gt:
                    continue
                lo, hi = ng.get(kmin), ng.get(kmax)
                ma = M.ten_may_so(nhom, k)
                ra.append({
                    "nhom": nhom, "ten_nhom": ten_nhom_, "k": k, "may": ma,
                    # "Máy rang đỗ M2" / "Máy đóng gói bột 2" (nhóm chưa có mã — C10)
                    "ten_may": f"{ten_nhom_} {k if ma.startswith('máy ') else ma}",
                    "f": f, "ten": ten, "dv": dv, "so_lan": len(gt),
                    "thap": min(gt), "cao": max(gt), "lo": lo, "hi": hi,
                    "duoi": sum(1 for x in gt if lo is not None and x < lo),
                    "tren": sum(1 for x in gt if hi is not None and x > hi),
                })
    return ra
