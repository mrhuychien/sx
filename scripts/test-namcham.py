"""D158 (W30) — BM.08.01 bản 3: mục 5 thùng ủ gỗ / vải ủ theo HD.08.02, mục 6 tách ba nam châm.

Vì sao phải có bài này:
  · Bản giấy 09/10/2026 có BA dòng nam châm: NC-01 (máy vỡ đỗ), NC-02 M1, NC-02 M2 (sau máy nghiền). App
    chỉ một dòng thì mạt kim loại ở máy nghiền M2 ghi vào ô "nam châm" chung — đi nhặt mạt ở máy vỡ đỗ.
  · Phiếu đã ghi trước ngày đổi (bản 2) phải giữ đúng MỘT dòng nam châm, in đúng mục đã ghi — chen ba
    dòng trống vào tờ in tháng trước là hồ sơ đổi nghĩa.
  · NC-02 theo máy nghiền: máy M2 không chạy (hay hôm đó không nghiền) mà vẫn bắt ghi là ép QC ghi bừa.

Nạp sx/qc/muc.py, su_co.py, controller SX QC Round, sx/api/qc.py THẬT trên frappe giả.
Chạy: python3 scripts/test-namcham.py   (verify.sh gọi sẵn)
"""

import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

F.cai()
Q = F.nap_qc()
M = sys.modules["sx.qc.muc"]
SC = sys.modules["sx.qc.su_co"]
kiem = F.kiem
F.dat_ngay("2026-10-09")


def ap(luot, **kw):
    return {m["f"] for m in M.muc_ap_dung(luot, F.Doc(kw))}


def sc(**kw):
    kw.setdefault("luot", M.DAU_SANG)
    kw.setdefault("phien_ban", 3)
    return SC.phat_hien(F.Doc(kw))


NC3 = {"nc01_da_kiem", "nc01_vat", "nc01_mat_kim_loai", "nc02_da_kiem", "nc02_vat", "nc02_mat_kim_loai"}
NC3_M2 = {"nc02_da_kiem_m2", "nc02_vat_m2", "nc02_mat_kim_loai_m2"}
CU = {"nam_cham_da_kiem", "nam_cham_vat", "nam_cham_mat_kim_loai"}

# ═══ 1. Phiên bản: phiếu cũ một dòng, phiếu mới ba nam châm ══════════════════════
print("-- phiên bản bộ mục --")
kiem("bộ mục hiện hành là bản 3", M.PHIEN_BAN == 3)
kiem("phiếu bản 2 (trước 09/10) giữ đúng MỘT bộ nam châm + mục 5 cũ, không chen dòng mới",
     CU <= ap(M.DAU_SANG, phien_ban=2) and "u_thung_vai_sach" in ap(M.DAU_SANG, phien_ban=2)
     and not (NC3 | {"u_thung_go_vai"}) & ap(M.DAU_SANG, phien_ban=2), ap(M.DAU_SANG, phien_ban=2) & (NC3 | CU))
kiem("phiếu bản 3: NC-01 + NC-02 M1 (một máy nghiền), không còn bộ nam châm cũ, không M2",
     NC3 <= ap(M.DAU_SANG, phien_ban=3) and not CU & ap(M.DAU_SANG, phien_ban=3)
     and not NC3_M2 & ap(M.DAU_SANG, phien_ban=3))
kiem("… hai máy nghiền chạy → thêm NC-02 M2", NC3_M2 <= ap(M.DAU_SANG, phien_ban=3, so_may_nghien=2))
kiem("… lượt Tuần (thứ Hai thay Đầu sáng) cũng có", NC3 <= ap(M.TUAN, phien_ban=3))
kiem("nam châm chỉ lượt Đầu sáng / Tuần (bản giấy: Trưa, Cuối chiều gạch)",
     not (NC3 | NC3_M2) & ap(M.TRUA, phien_ban=3, so_may_nghien=2)
     and not (NC3 | NC3_M2) & ap(M.CUOI_CHIEU, phien_ban=3, so_may_nghien=2))
kiem("hôm không nghiền (tắt bước 7) → không kiểm NC-02, NC-01 vẫn kiểm",
     not {"nc02_da_kiem"} & ap(M.DAU_SANG, phien_ban=3, buoc_nghi="7")
     and "nc01_da_kiem" in ap(M.DAU_SANG, phien_ban=3, buoc_nghi="7"))
kiem("hôm không vỡ đỗ (tắt bước 6) → không mục nam châm nào",
     not (NC3 | NC3_M2) & ap(M.DAU_SANG, phien_ban=3, so_may_nghien=2, buoc_nghi="6"))
kiem("mục 5 bản 3 chỉ lượt Đầu sáng / Tuần (HD.08.01 bảng 3), bản 2 vẫn mọi lượt",
     "u_thung_go_vai" in ap(M.DAU_SANG, phien_ban=3) and "u_thung_go_vai" in ap(M.TUAN, phien_ban=3)
     and "u_thung_go_vai" not in ap(M.TRUA, phien_ban=3)
     and "u_thung_vai_sach" in ap(M.TRUA, phien_ban=2))
kiem("ô vật bắt được / mạt kim loại là ô đi kèm (không tính vào x/y)",
     all(M.THEO_F[f]["phu"] for f in ("nc01_vat", "nc01_mat_kim_loai", "nc02_vat_m2", "nc02_mat_kim_loai_m2"))
     and not M.THEO_F["nc02_da_kiem_m2"]["phu"])

# ═══ 2. Chữ đúng bản giấy ═══════════════════════════════════════════════════════
print("\n-- nhãn theo bản giấy BM.08.01 09/10/2026 --")
T = M.THEO_F
kiem("mục 5: thùng ủ gỗ, vải ủ … đúng mã thùng; ủ ≤ 48 giờ",
     T["u_thung_go_vai"]["nhan"] == "Thùng ủ gỗ, vải ủ: sạch, khô, không mốc, không đọng nước, phủ kín; vải "
                                    "nguyên vẹn, đúng mã thùng; ủ ≤ 48 giờ" and T["u_thung_go_vai"]["loai"] == "PRP",
     T["u_thung_go_vai"]["nhan"])
kiem("ba dòng nam châm mang mã: NC-01 (máy vỡ đỗ), NC-02 (M1, sau nghiền), NC-02 (M2, sau nghiền)",
     T["nc01_da_kiem"]["nhan"].startswith("NC-01 (máy vỡ đỗ)")
     and T["nc02_da_kiem"]["nhan"].startswith("NC-02 (M1, sau nghiền)")
     and T["nc02_da_kiem_m2"]["nhan"].startswith("NC-02 (M2, sau nghiền)")
     and "— M2" not in T["nc02_da_kiem_m2"]["nhan"], [T[f]["nhan"] for f in ("nc01_da_kiem", "nc02_da_kiem",
                                                                              "nc02_da_kiem_m2")])
kiem("nhãn ngắn trên màn hình cũng theo máy", T["nc02_vat_m2"]["ngan"] == "NC-02 (M2): vật bắt được"
     and T["nc02_da_kiem_m2"]["ngan"].startswith("NC-02 M2"))
kiem("bước 6 là oPRP-2 như bản giấy", dict((b[0], b[2]) for b in M.BUOC)["6"] == "oPRP-2")
kiem("ô máy 2 của NC-02 đứng ngay sau NC-02 máy 1, trước rây kiểm (không trộn hai mục)",
     [m["f"] for m in M.MUC if m["may"] == "nghien"][:6]
     == ["nc02_da_kiem", "nc02_vat", "nc02_mat_kim_loai", "nc02_da_kiem_m2", "nc02_vat_m2", "nc02_mat_kim_loai_m2"])
kiem("tên nam châm theo ô / ô vật cùng nam châm",
     M.ten_nam_cham(T["nc02_mat_kim_loai_m2"]) == "NC-02 M2" and M.ten_nam_cham(T["nc01_da_kiem"]) == "NC-01"
     and M.o_vat(T["nc02_mat_kim_loai_m2"]) == "nc02_vat_m2" and M.o_vat(T["nc01_da_kiem"]) == "nc01_vat")

# ═══ 3. Sự cố ════════════════════════════════════════════════════════════════════
print("\n-- sự cố: ghi đúng nam châm --")
r = sc(so_may_nghien=2, nc02_da_kiem_m2="Không đạt")
kiem("K ở NC-02 M2 → một sự cố oPRP mức Thường, mô tả ghi rõ 'NC-02 M2'",
     [(x[0], x[2], x[3]) for x in r] == [("nc02_da_kiem_m2", "oPRP", "Thường")] and "NC-02 M2" in r[0][4], r)
r = sc(nc01_mat_kim_loai=1, nc01_vat="ốc vít")
kiem("mạt kim loại ở NC-01 → sự cố oPRP mức CAO, ghi NC-01 và vật", [(x[2], x[3]) for x in r] == [("oPRP", "Cao")]
     and "NC-01" in r[0][4] and "ốc vít" in r[0][4], r)
r = sc(so_may_nghien=2, nc02_mat_kim_loai=1, nc02_vat_m2="mảnh dây")
kiem("mạt ở NC-02 M1: vật lấy đúng ô của M1 (không lẫn vật của M2)",
     len(r) == 1 and "NC-02 M1" in r[0][4] and "mảnh dây" not in r[0][4], r)
kiem("M2 không chạy → mạt ghi nhầm ở ô M2 không thành sự cố", not sc(so_may_nghien=1, nc02_mat_kim_loai_m2=1))
kiem("NC-01 Đạt, không mạt → không sự cố", not sc(nc01_da_kiem="Đạt", nc02_da_kiem="Đạt"))
kiem("mục 5 bản 3 Không đạt → sự cố PRP", [x[2] for x in sc(u_thung_go_vai="Không đạt")] == ["PRP"])
r = sc(phien_ban=2, nam_cham_mat_kim_loai=1, nam_cham_vat="đinh")
kiem("phiếu bản 2 vẫn theo luật cũ (mạt kim loại → Cao)", [(x[0], x[3]) for x in r]
     == [("nam_cham_mat_kim_loai", "Cao")], r)
kiem("phiếu bản 2: ô nam châm mới (chưa tồn tại lúc ghi) không xét", not sc(phien_ban=2, nc01_mat_kim_loai=1))
cb = SC.canh_bao(F.Doc(luot=M.DAU_SANG, phien_ban=3, nc02_vat="mảnh nhựa"))
kiem("vật bắt được (không phải kim loại) → cảnh báo ghi đúng nam châm", "Nam châm NC-02 M1 bắt được: mảnh nhựa" in cb,
     cb)

# ═══ 4. Tờ in ngày ══════════════════════════════════════════════════════════════
print("\n-- tờ in BM.08.01 --")
if F.jinja2:
    base = {"docstatus": 1, "ghi_muon": 0, "qc_user": "qc@x", "co_san_xuat_bot": 0, "reviewed_on": None,
            "nhap_lai_tu_giay": 0, "log": [], "su_co": []}
    F.bang("SX QC Round").update({
        "QC-CU": dict(base, name="QC-CU", ngay="2026-10-08", luot=M.DAU_SANG, phien_ban=2,
                      nam_cham_da_kiem="Đạt", started_at=datetime(2026, 10, 8, 7, 0),
                      finished_at=datetime(2026, 10, 8, 7, 20), creation="2026-10-08 07:00:00"),
        "QC-MOI": dict(base, name="QC-MOI", ngay="2026-10-09", luot=M.DAU_SANG, phien_ban=3, so_may_nghien=2,
                       nc01_da_kiem="Đạt", nc02_da_kiem="Đạt", nc02_da_kiem_m2="Không đạt",
                       started_at=datetime(2026, 10, 9, 7, 0), finished_at=datetime(2026, 10, 9, 7, 20),
                       creation="2026-10-09 07:00:00")})

    def to(ngay):
        return re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", Q.day_sheet(ngay)))

    h = to("2026-10-08")
    kiem("tờ ngày phiếu cũ: đúng một dòng nam châm, không có dòng NC-01 / NC-02",
         "Nam châm đã kiểm, vệ sinh" in h and "NC-01" not in h and "NC-02" not in h, h[:200])
    h = to("2026-10-09")
    kiem("tờ ngày phiếu mới: NC-01, NC-02 (M1…), NC-02 (M2…) — mỗi máy một dòng, có oPRP-2",
         "NC-01 (máy vỡ đỗ)" in h and "NC-02 (M1, sau nghiền)" in h and "NC-02 (M2, sau nghiền)" in h
         and "Vỡ đỗ · Nam châm (oPRP-2)" in h and "Nam châm đã kiểm, vệ sinh" not in h, h[:400])
    kiem("… nhãn máy 1 không bị nối thêm '— M1' (mã máy đã nằm trong nhãn)", "sau nghiền): đã tháo, lau sạch, còn "
                                                                             "hút — M1" not in h)
    kiem("… mục 5 chữ mới", "ủ ≤ 48 giờ" in h)

# ═══ 5. DocType sinh từ muc.py ══════════════════════════════════════════════════
print("\n-- DocType SX QC Round --")
jd = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_qc_round/sx_qc_round.json",
                                                encoding="utf-8"))["fields"]}
kiem("đủ ô mới (NC-01, NC-02 M1, M2, mục 5 mới); ô cũ còn nguyên cho phiếu cũ",
     all(f in jd for f in NC3 | NC3_M2 | CU | {"u_thung_go_vai", "u_thung_vai_sach"}))
kiem("ô Đ/K là Select ba trạng thái, mạt kim loại là Check, vật là Data",
     jd["nc02_da_kiem_m2"]["fieldtype"] == "Select" and jd["nc01_mat_kim_loai"]["fieldtype"] == "Check"
     and jd["nc02_vat_m2"]["fieldtype"] == "Data")
rd = open("README.md", encoding="utf-8").read()
kiem("README: dữ liệu cần khai NC-02 M1, M2 trong Thiết bị đo", "NC-02 M1" in rd and "11.000" in rd)

F.ket_thuc("NAMCHAM")
