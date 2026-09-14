"""Hộp nhắc việc QC — nhắc đúng cái đang treo, và IM khi không có gì.

Vì sao bài này quan trọng ngang luật sinh sự cố: hộp nhắc hỏng theo hai hướng,
cả hai đều kết thúc ở chỗ không ai đọc nó nữa.

  · Nhắc THỪA (ca không sản xuất cũng kêu thiếu lượt, ngày nào cũng một hộp đỏ)
    → sau hai tuần mắt tự bỏ qua đúng vùng màn hình đó, và hôm có việc thật thì
    cũng bỏ qua nốt.
  · Nhắc THIẾU (sự cố quá hạn không hiện) → đúng thứ hộp này sinh ra để bắt.

Nên bài kiểm ở đây có nhiều ca KHẲNG ĐỊNH KHÔNG NHẮC ngang với ca có nhắc.

Chạy: python3 scripts/test-nhac.py   (verify.sh gọi sẵn)
"""

import importlib.util
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

for goi in ("sx", "sx.qc"):
    m = types.ModuleType(goi)
    m.__path__ = []
    sys.modules[goi] = m
sp = importlib.util.spec_from_file_location("sx.qc.nhac", "sx/qc/nhac.py")
N = importlib.util.module_from_spec(sp)
sys.modules["sx.qc.nhac"] = N
sp.loader.exec_module(N)

hong = 0

# 2026-09-14 là THỨ HAI (đã kiểm bằng datetime bên dưới).
T2 = "2026-09-14"
T4 = "2026-09-16"
NG = {"su_co_qua_han_ngay": 7, "rang_lac_nhiet_min": None,
      "rang_lac_phut_min": None}


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


def tinh(hom_nay=T2, luot=(), su_co=(), ng=None):
    return N.tinh(hom_nay, list(luot), list(su_co), dict(ng or NG))


def co(ds, chu):
    return [x for x in ds if chu in x["tieu_de"]]


def lt(ngay, ca="Sáng", luot="Đầu ca", docstatus=1, **kw):
    d = {"ngay": ngay, "ca": ca, "luot": luot, "docstatus": docstatus}
    d.update(kw)
    return d


def sc(ngay, trang_thai="Mở", xu_ly_ngay="đã xử lý", **kw):
    d = {"name": f"SC-{ngay}", "ngay": ngay, "trang_thai": trang_thai,
         "xu_ly_ngay": xu_ly_ngay}
    d.update(kw)
    return d


from datetime import date  # noqa: E402

kiem("mốc ngày dùng trong bài đúng là thứ Hai", date(2026, 9, 14).weekday() == 0)

# ═══ 1. Im lặng khi không có gì ══════════════════════════════════════════
print("\n-- không có việc gì thì KHÔNG nhắc --")
ba_luot = [lt(T2, "Sáng", "Tuần"), lt(T2, "Sáng", "Giữa ca"),
           lt(T2, "Sáng", "Cuối ca")]
kiem("ngày sạch, không sự cố → hộp nhắc RỖNG", tinh(luot=ba_luot) == [])
kiem("không có lượt nào, không sự cố nào → chỉ nhắc lượt tuần chưa làm",
     [x["tieu_de"] for x in tinh()] == ["Hôm nay là thứ Hai — chưa làm lượt tuần"],
     str([x["tieu_de"] for x in tinh()]))

# ═══ 2. Sự cố ════════════════════════════════════════════════════════════
print("\n-- sự cố --")
ds = tinh(luot=ba_luot, su_co=[sc("2026-09-01")])
kiem("mở 13 ngày (quá hạn 7) → nhắc mức CAO",
     co(ds, "quá hạn") and co(ds, "quá hạn")[0]["muc_do"] == N.CAO)
kiem("và nói ra số ngày lâu nhất", "13 ngày" in co(ds, "quá hạn")[0]["chi_tiet"],
     co(ds, "quá hạn")[0]["chi_tiet"])
kiem("mở 3 ngày, đã ghi xử lý → chỉ nhắc mức thường",
     [x["muc_do"] for x in tinh(luot=ba_luot, su_co=[sc("2026-09-11")])]
     == [N.THUONG])
ds = tinh(luot=ba_luot, su_co=[sc("2026-09-13", xu_ly_ngay="")])
kiem("mở 1 ngày mà CHƯA ghi xử lý → vẫn mức CAO",
     co(ds, "chưa ghi xử lý") and co(ds, "chưa ghi xử lý")[0]["muc_do"] == N.CAO)
kiem("phiếu đã ĐÓNG không nhắc",
     tinh(luot=ba_luot, su_co=[sc("2026-01-01", "Đóng")]) == [])
kiem("một phiếu vừa quá hạn vừa chưa xử lý không bị đếm ba lần",
     len(tinh(luot=ba_luot, su_co=[sc("2026-09-01", xu_ly_ngay="")])) == 2,
     str([x["tieu_de"] for x in
          tinh(luot=ba_luot, su_co=[sc("2026-09-01", xu_ly_ngay="")])]))

# ═══ 3. Lượt tuần ════════════════════════════════════════════════════════
print("\n-- lượt tuần (mỗi tuần một lần, bỏ là mất hẳn) --")
kiem("thứ Hai chưa làm → nhắc mức thường (còn cả ngày để làm)",
     tinh()[0]["muc_do"] == N.THUONG)
ds = tinh(hom_nay=T4)
kiem("thứ Tư vẫn chưa làm → mức CAO", co(ds, "lượt tuần")[0]["muc_do"] == N.CAO)
kiem("và nói đã qua mấy ngày", "2 ngày" in co(ds, "lượt tuần")[0]["chi_tiet"],
     co(ds, "lượt tuần")[0]["chi_tiet"])
kiem("đã làm rồi → im", not co(tinh(luot=ba_luot), "lượt tuần"))
kiem("lượt Tuần của TUẦN TRƯỚC không tính cho tuần này",
     co(tinh(hom_nay=T4, luot=[lt("2026-09-07", luot="Tuần")]), "lượt tuần"))

# ═══ 4. Lượt thiếu / bỏ dở ═══════════════════════════════════════════════
print("\n-- ca đi thiếu lượt --")
kiem("ca KHÔNG có lượt nào → KHÔNG nhắc (hôm đó có thể không sản xuất)",
     not co(tinh(hom_nay=T4, luot=[lt(T4, luot="Tuần")]), "đi thiếu"))
ds = tinh(hom_nay=T4, luot=[lt(T2, "Sáng", "Tuần"), lt(T2, "Sáng", "Giữa ca")])
kiem("ca đi 2/3 lượt → có nhắc", co(ds, "đi thiếu"))
kiem("và chỉ đúng ngày nào ca nào", "14/09 Sáng (2/3)" in co(ds, "đi thiếu")[0]["chi_tiet"],
     co(ds, "đi thiếu")[0]["chi_tiet"])
kiem("ca đủ 3 lượt → không nhắc",
     not co(tinh(hom_nay=T4, luot=ba_luot + [lt(T4, luot="Tuần")]), "đi thiếu"))
kiem("HÔM NAY đi mới 1 lượt → chưa nhắc (ngày còn đang chạy)",
     not co(tinh(luot=[lt(T2, "Sáng", "Tuần")]), "đi thiếu"))
ds = tinh(hom_nay=T4, luot=[lt(T2, "Sáng", "Tuần", docstatus=0)])
kiem("lượt mở ra rồi bỏ dở từ ngày cũ → có nhắc", co(ds, "bỏ dở"))
kiem("và nói bỏ dở mấy ngày", "2 ngày" in co(ds, "bỏ dở")[0]["chi_tiet"],
     co(ds, "bỏ dở")[0]["chi_tiet"])
kiem("lượt đang làm dở HÔM NAY → không nhắc",
     not co(tinh(luot=[lt(T2, "Sáng", "Tuần", docstatus=0)]), "bỏ dở"))

# ═══ 5. Chờ xem xét ══════════════════════════════════════════════════════
print("\n-- chờ Ban ISO xem xét --")
kiem("hoàn tất 20 ngày chưa ai ký → nhắc",
     co(tinh(luot=ba_luot + [lt("2026-08-25", luot="Tuần")]), "chờ Ban ISO"))
kiem("hoàn tất 20 ngày và ĐÃ ký → im",
     not co(tinh(luot=ba_luot + [lt("2026-08-25", luot="Tuần",
                                    reviewed_on="2026-08-26 10:00:00")]),
            "chờ Ban ISO"))
kiem("hoàn tất 3 ngày chưa ký → chưa nhắc (chưa tới hạn)",
     not co(tinh(luot=ba_luot + [lt("2026-09-11", luot="Tuần")]), "chờ Ban ISO"))

# ═══ 6. Bẫy chuột ════════════════════════════════════════════════════════
print("\n-- bẫy chuột hai tuần liền --")
hai_tuan = [lt("2026-09-07", luot="Tuần", t2_so_bay_dau_hieu=2),
            lt(T2, luot="Tuần", t2_so_bay_dau_hieu=1)]
ds = tinh(luot=hai_tuan + ba_luot[1:])
kiem("hai tuần liền có dấu hiệu → mức CAO",
     co(ds, "Bẫy chuột") and co(ds, "Bẫy chuột")[0]["muc_do"] == N.CAO)
kiem("chỉ MỘT tuần có dấu hiệu → không nhắc (bắt được một con là bình thường)",
     not co(tinh(luot=[lt("2026-09-07", luot="Tuần", t2_so_bay_dau_hieu=0),
                       lt(T2, luot="Tuần", t2_so_bay_dau_hieu=3)] + ba_luot[1:]),
            "Bẫy chuột"))
kiem("mới có một tuần dữ liệu → chưa kết luận được, không nhắc",
     not co(tinh(luot=[lt(T2, luot="Tuần", t2_so_bay_dau_hieu=3)] + ba_luot[1:]),
            "Bẫy chuột"))

# ═══ 7. Ngưỡng chưa thẩm định ════════════════════════════════════════════
print("\n-- đang ghi số mà không có ngưỡng nào kiểm nó --")
co_bot = ba_luot + [lt(T2, "Chiều", "Giữa ca", b2_rang_lac_nhiet=160)]
kiem("có ghi nhiệt rang lạc mà Setting chưa đặt ngưỡng → nhắc",
     co(tinh(luot=co_bot), "Ngưỡng rang lạc"))
kiem("đặt ngưỡng rồi → im",
     not co(tinh(luot=co_bot, ng={**NG, "rang_lac_nhiet_min": 150}),
            "Ngưỡng rang lạc"))
kiem("chưa ai ghi nhiệt rang lạc → im (đừng nhắc việc chưa tồn tại)",
     not co(tinh(luot=ba_luot), "Ngưỡng rang lạc"))

# ═══ 8. Thứ tự ═══════════════════════════════════════════════════════════
print("\n-- mức cao đứng trước --")
ds = tinh(hom_nay=T4, su_co=[sc("2026-09-01"), sc("2026-09-13", xu_ly_ngay="")])
kiem("mọi mục CAO xếp trước mọi mục thường",
     [x["muc_do"] for x in ds] == sorted(
         [x["muc_do"] for x in ds], key=lambda m: 0 if m == N.CAO else 1),
     str([(x["muc_do"], x["tieu_de"]) for x in ds]))
kiem("mục nào cũng chỉ được sang một màn cụ thể",
     all(x["route"].startswith("#/qc") for x in ds))
kiem("mục nào cũng có con số hoặc số ngày trong phần chi tiết",
     all(any(c.isdigit() for c in x["chi_tiet"]) for x in ds),
     str([x["chi_tiet"] for x in ds if not any(c.isdigit() for c in x["chi_tiet"])]))

print("NHAC-FAIL ({} ca)".format(hong) if hong else "NHAC-OK")
sys.exit(1 if hong else 0)
