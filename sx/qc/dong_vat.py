"""Động vật gây hại theo trạm (W15, D140) — phần tính, đọc dữ liệu qua frappe.

Trạm R01–R21 (bẫy chuột), C01–C19 (bẫy / đèn côn trùng); mỗi lần THẤY dấu hiệu thì
quét QR ở trạm (hoặc gõ mã) và ghi một phiếu SX Dau Hieu Dong Vat. Tuần không có phiếu
nào ở một trạm = trạm đó không có dấu hiệu tuần đó (BM.PRP.03).

Nhắc gọi dịch vụ: cùng KHU có dấu hiệu HAI TUẦN LIỀN (tuần tính từ thứ Hai). Xét cặp
(tuần trước, tuần này) và (hai tuần trước, tuần trước) — sáng thứ Hai chưa ai ghi gì
thì cặp hai tuần vừa qua vẫn phải được nhắc. Trạm chưa khai khu thì tự là một khu.

Không có nhắc "phun định kỳ" nào trong app (tài liệu 08/10 bảo bỏ — chưa từng có).
"""

from datetime import date, timedelta

import frappe
from frappe.utils import getdate


def thu_hai(d):
    d = getdate(d)
    return d - timedelta(days=d.weekday())


def ten_khu(khu, tram):
    return khu or f"trạm {tram} (chưa khai khu)"


def khu_hai_tuan(ds, hom_nay):
    """[{khu, tram: [...], tuan: [thứ Hai 1, thứ Hai 2]}] — hàm thuần.
    `ds` = [{ngay, khu, tram}] (phiếu dấu hiệu, mọi ngày)."""
    w = thu_hai(hom_nay)
    theo = {}
    for x in ds:
        k = ten_khu(x.get("khu"), x.get("tram"))
        t = thu_hai(x["ngay"])
        g = theo.setdefault(k, {})
        g.setdefault(t, set()).add(x.get("tram"))
    ra = []
    for k, tuan in theo.items():
        for a, b in ((w - timedelta(days=7), w), (w - timedelta(days=14), w - timedelta(days=7))):
            if a in tuan and b in tuan:
                ra.append({"khu": k, "tram": sorted(tuan[a] | tuan[b]), "tuan": [str(a), str(b)]})
                break
    return sorted(ra, key=lambda x: x["khu"])


def chuoi_lien_tuan(ds):
    """Mọi chuỗi ≥ 2 tuần liền có dấu hiệu, theo khu — cho bản tổng hợp tháng BM.PRP.01
    (khu_hai_tuan chỉ nhìn quanh MỘT tuần nên bỏ sót chuỗi giữa tháng). Hàm thuần.
    → [{khu, tram: [...], tuan: [thứ Hai…]}] theo khu, rồi tuần đầu chuỗi."""
    theo = {}
    for x in ds:
        k = ten_khu(x.get("khu"), x.get("tram"))
        theo.setdefault(k, {}).setdefault(thu_hai(x["ngay"]), set()).add(x.get("tram"))
    ra = []
    for k, tuan in theo.items():
        chuoi = []
        for w in sorted(tuan):
            if chuoi and w - chuoi[-1] == timedelta(days=7):
                chuoi.append(w)
                continue
            if len(chuoi) >= 2:
                ra.append((k, chuoi))
            chuoi = [w]
        if len(chuoi) >= 2:
            ra.append((k, chuoi))
    return [{"khu": k, "tram": sorted(set().union(*(theo[k][w] for w in c))), "tuan": [str(w) for w in c]}
            for k, c in sorted(ra, key=lambda x: (x[0], x[1][0]))]


def nhac(hom_nay):
    """Dữ liệu cho hộp nhắc QC: {co_du_lieu, khu_hai_tuan}. Chưa migrate → {}."""
    hom_nay = getdate(hom_nay)
    try:
        ds = frappe.get_all("SX Dau Hieu Dong Vat",
                            filters={"ngay": (">=", str(thu_hai(hom_nay) - timedelta(days=14)))},
                            fields=["ngay", "khu", "tram"])
        co = bool(ds) or bool(frappe.get_all("SX Dau Hieu Dong Vat", limit=1, pluck="name"))
    except Exception:
        return {}
    return {"co_du_lieu": co, "khu_hai_tuan": khu_hai_tuan(ds, hom_nay)}


def ma_tram(q):
    """"r5" / "R05" / URL ".../qc/dvgh/R05" → "R05"; không ra mã → ""."""
    import re

    q = str(q or "").strip().upper()
    m = re.search(r"([RC])\s*0*(\d{1,2})\s*$", q)
    return f"{m.group(1)}{int(m.group(2)):02d}" if m else ""


DS_TRAM = [f"R{i:02d}" for i in range(1, 22)] + [f"C{i:02d}" for i in range(1, 20)]
# Đúng thứ tự options của SX Dau Hieu Dong Vat.dau_hieu (test-dongvat.py so khớp).
DAU_HIEU = ["Chuột / dấu vết chuột", "Côn trùng bò (gián, kiến…)",
            "Côn trùng bay (ruồi, muỗi, bướm…)", "Khác"]
