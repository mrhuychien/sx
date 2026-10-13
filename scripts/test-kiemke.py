#!/usr/bin/env python3
"""Kiểm kê kho thành phẩm theo HSD (D154): kế hoạch từng lô, chốt ra chứng từ kho, API thẻ, chốt chặn.

Vì sao phải có bài này: chốt kiểm kê sinh chứng từ kho THẬT (chuyển lô, xuất thiếu, nhập thừa) và không có
nút hoàn tác trên màn hình. Sai số học ở đây là tồn kho sai cả lô, mất mắt xích truy xuất, hoặc hàng tồn cũ
bị chặn bán vì không có phiếu xuất xưởng. Nạp module THẬT (sx/kiem_ke.py, controller SX Kiem Ke, API, mfg,
utils, khotp) trên Frappe giả; sổ cái kho giả cộng trừ đúng theo các Stock Entry được submit, rồi đọc lại tồn
sau chốt để so với số đếm.

Chạy: python3 scripts/test-kiemke.py   (verify.sh gọi sẵn)
"""

import calendar
import json
import os
import sys
import types
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fakefrappe as F  # noqa: E402

frappe = F.cai()
frappe.local = types.SimpleNamespace()
fu = sys.modules["frappe.utils"]


def add_months(d, n):
    d = F.getdate(d)
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


fu.add_months = add_months
for g in ("sx.sx", "sx.sx.doctype", "sx.sx.doctype.sx_kiem_ke", "sx.sx.doctype.sx_phieu_nhap_tp", "sx.config"):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m

kiem, thu = F.kiem, F.thu
K = F.nap("sx.kiem_ke", "sx/kiem_ke.py")

# ═══════════════════════════════ 1. kế hoạch (hàm thuần) ═══════════════════════════════
print("-- kế hoạch từng lô (hàm thuần) --")
H1, H2 = "2027-06-08", "2027-06-18"
NSX = {H1: "2026-09-11", H2: "2026-09-21", "2027-01-01": "2026-04-06"}


def lo(b, q, hsd=None, ngay=None, **k):
    return dict(batch=b, qty=q, hsd=hsd, ngay=ngay, **k)


A100, B50 = lo("SEN-120926", 100, ngay="2026-09-12"), lo("SEN-220926", 50, ngay="2026-09-22")
ke = K.lap_ke_hoach([A100, B50], {H1: 60, H2: 90}, NSX.get)
kiem("lô cũ khớp tổng: không xuất / nhập gì, sổ 150 = đếm 150",
     not ke["xuat"] and not ke["nhap"] and ke["so_sach"] == 150 and ke["dem"] == 150, ke)
kiem("HSD cũ nhất (NSX 11/09) lấy từ lô cũ nhất nhập SAU ngày làm ra hộp (lô 12/09)",
     ke["chuyen"][0] == {"tu": "SEN-120926", "tu_hsd": None, "hsd": H1, "so": 60}, ke["chuyen"])
kiem("HSD 18/06 (NSX 21/09): lô 22/09 trước; hết lô hợp lệ mới lấy lô nhập trước ngày đó (12/09)",
     ke["chuyen"][1:] == [{"tu": "SEN-220926", "tu_hsd": None, "hsd": H2, "so": 50},
                          {"tu": "SEN-120926", "tu_hsd": None, "hsd": H2, "so": 40}], ke["chuyen"])
ke = K.lap_ke_hoach([lo("SEN-100926", 100, ngay="2026-09-10"), lo("SEN-200926", 50, ngay="2026-09-20")],
                    {H1: 60}, NSX.get)
kiem("lô nhập TRƯỚC ngày làm ra hộp không chứa được hộp đó: HSD 08/06 (NSX 11/09) lấy lô 20/09 trước lô 10/09",
     ke["chuyen"] == [{"tu": "SEN-200926", "tu_hsd": None, "hsd": H1, "so": 50},
                      {"tu": "SEN-100926", "tu_hsd": None, "hsd": H1, "so": 10}], ke["chuyen"])

ke = K.lap_ke_hoach([A100, B50], {H1: 60}, NSX.get)
kiem("đếm thiếu: phần bể còn lại thành XUẤT THIẾU", ke["xuat"] == [
    {"batch": "SEN-120926", "hsd": None, "so": 40}, {"batch": "SEN-220926", "hsd": None, "so": 50}], ke["xuat"])
kiem("… và tổng chuyển + thiếu = sổ", sum(x["so"] for x in ke["chuyen"] + ke["xuat"]) == 150)

ke = K.lap_ke_hoach([A100, B50], {H1: 200}, NSX.get)
kiem("đếm thừa: chuyển hết bể (150), phần còn lại NHẬP THỪA vào lô HSD",
     sum(x["so"] for x in ke["chuyen"]) == 150 and ke["nhap"] == [{"hsd": H1, "so": 50}] and not ke["xuat"], ke)

C30 = lo("SEN-HSD080627", 30, hsd=H1, ngay="2026-09-11", chuan=True)
ke = K.lap_ke_hoach([C30, A100], {H1: 50, H2: 70}, NSX.get)
kiem("lô đã có HSD đủ đếm → GIỮ NGUYÊN (không sinh chứng từ cho phần đó)",
     ke["giu"] == [{"batch": "SEN-HSD080627", "hsd": H1, "so": 30}], ke["giu"])
kiem("… phần đếm thêm của HSD đó + HSD mới lấy từ lô cũ; dư thành thiếu",
     sorted((x["hsd"], x["so"]) for x in ke["chuyen"]) == [(H1, 20), (H2, 70)]
     and ke["xuat"] == [{"batch": "SEN-120926", "hsd": None, "so": 10}], ke)

D20 = lo("SEN-110926", 20, hsd=H1, ngay="2026-09-10")
ke = K.lap_ke_hoach([C30, D20], {H1: 35}, NSX.get)
kiem("D188 mỗi (mã, HSD) một lô: lô cũ CÙNG HSD (không phải lô chuẩn) gộp vào lô chuẩn …-HSD, phần dư xuất thiếu",
     ke["giu"] == [{"batch": "SEN-HSD080627", "hsd": H1, "so": 30}]
     and ke["chuyen"] == [{"tu": "SEN-110926", "tu_hsd": H1, "hsd": H1, "so": 5}]
     and ke["xuat"] == [{"batch": "SEN-110926", "hsd": H1, "so": 15}], ke)
ke = K.lap_ke_hoach([D20, A100], {H1: 20}, NSX.get)
kiem("… chưa có lô chuẩn: lô cũ ghi đúng HSD đó lấy TRƯỚC lô chưa có HSD (cùng hàng, chỉ khác tên lô)",
     ke["chuyen"] == [{"tu": "SEN-110926", "tu_hsd": H1, "hsd": H1, "so": 20}] and not ke["giu"]
     and ke["xuat"] == [{"batch": "SEN-120926", "hsd": None, "so": 100}], ke)
ke = K.lap_ke_hoach([D20, lo("SEN-HSD080627", 30, hsd=H1, ngay="2026-09-11", chuan=True)], {H1: 50}, NSX.get)
kiem("… đếm đúng tổng hai lô: lô chuẩn giữ 30, lô cũ chuyển hết 20 sang — không còn hai lô một HSD",
     ke["giu"] == [{"batch": "SEN-HSD080627", "hsd": H1, "so": 30}] and not ke["xuat"] and not ke["nhap"]
     and ke["chuyen"] == [{"tu": "SEN-110926", "tu_hsd": H1, "hsd": H1, "so": 20}], ke)

ke = K.lap_ke_hoach([lo("SEN-HSD010127", 10, hsd="2027-01-01", chuan=True)], {}, NSX.get)
kiem("đếm \"không còn hàng\": lô có HSD cũng xuất thiếu hết",
     ke["xuat"] == [{"batch": "SEN-HSD010127", "hsd": "2027-01-01", "so": 10}] and ke["dem"] == 0, ke)

ke = K.lap_ke_hoach([lo("SEN-HSD010127", 10, hsd="2027-01-01", chuan=True)], {H1: 10}, NSX.get)
kiem("hộp ghi nhầm HSD lúc nhập (đếm thấy HSD khác): CHUYỂN sang lô HSD đúng, không xuất rồi nhập",
     ke["chuyen"] == [{"tu": "SEN-HSD010127", "tu_hsd": "2027-01-01", "hsd": H1, "so": 10}]
     and not ke["xuat"] and not ke["nhap"], ke)

ke = K.lap_ke_hoach([A100, lo("SEN-010926", 10, ngay="2026-09-01", thu_hoi=True)], {H1: 100}, NSX.get)
kiem("lô đang THU HỒI: bỏ qua, không tính vào sổ, không đụng",
     ke["bo_qua"] == [{"batch": "SEN-010926", "hsd": None, "so": 10}] and ke["so_sach"] == 100
     and all(x["tu"] != "SEN-010926" for x in ke["chuyen"]), ke)

ke = K.lap_ke_hoach([A100, lo("SEN-050926", -5, ngay="2026-09-05")], {H1: 100}, NSX.get)
kiem("lô ÂM (kho cho tồn âm): nhập bù về 0; sổ 95 → đếm 100",
     ke["bu_am"] == [{"batch": "SEN-050926", "hsd": None, "so": 5}] and ke["so_sach"] == 95
     and sum(x["so"] for x in ke["chuyen"]) == 100, ke)

ke = K.lap_ke_hoach([C30], {H1: 30}, NSX.get)
kiem("khớp sổ hết → không có thay đổi nào", not K.co_thay_doi(ke) and ke["giu"], ke)
kiem("lệch số lẻ thập phân không đẻ dòng rác", not K.co_thay_doi(K.lap_ke_hoach([C30], {H1: 30.0000001}, NSX.get)))

ke = K.lap_ke_hoach([C30, A100], {H1: 50, H2: 70}, NSX.get)
bang = K.theo_lo(ke, lambda h: f"SEN-HSD{h[8:10]}{h[5:7]}{h[2:4]}")
kiem("bảng theo lô: lô cũ 100 → 0 (chuyển 90, thiếu 10)",
     bang["SEN-120926"]["truoc"] == 100 and bang["SEN-120926"]["sau"] == 0, bang["SEN-120926"])
kiem("lô chuẩn đang có: 30 → 50 (giữ 30 + nhận 20); lô HSD mới: 0 → 70",
     (bang["SEN-HSD080627"]["truoc"], bang["SEN-HSD080627"]["sau"]) == (30, 50)
     and (bang["SEN-HSD180627"]["truoc"], bang["SEN-HSD180627"]["sau"]) == (0, 70), bang)

ke1 = K.lap_ke_hoach([lo("DO-150926", 40, ngay="2026-09-15")], {"2026-09-01": 10, "2027-03-15": 25}, lambda h: None)
ke2 = K.lap_ke_hoach([C30, A100], {H1: 50, H2: 70}, NSX.get)
ct = K.chia_chung_tu({"TP-DO": ke1, "TP-SEN": ke2}, "2026-10-09")
kiem("chia chứng từ: phần chuyển sang lô ĐÃ HẾT HẠN đi đường xuất + nhập (ERPNext cấm Repack đụng lô hết hạn)",
     [x["hsd"] for x in ct["repack"]["TP-DO"]] == ["2027-03-15"]
     and {"item": "TP-DO", "batch": "DO-150926", "so": 10.0} in ct["xuat"]
     and {"item": "TP-DO", "hsd": "2026-09-01", "batch": None, "so": 10.0} in ct["nhap"], ct)
kiem("… mã còn lại vẫn Repack; thiếu vào phiếu xuất; số chứng từ = 2 Repack + 1 xuất + 1 nhập",
     sorted(ct["repack"]) == ["TP-DO", "TP-SEN"] and {"item": "TP-SEN", "batch": "SEN-120926", "so": 10.0} in ct["xuat"]
     and K.so_chung_tu(ct) == 4, ct)
ct = K.chia_chung_tu({"TP-X": K.lap_ke_hoach([lo("X-HSD010926", 5, hsd="2026-09-01", chuan=True)],
                                             {"2027-01-01": 5}, lambda h: None)}, "2026-10-09")
kiem("… nguồn là lô có HSD đã hết hạn cũng không Repack", not ct["repack"] and ct["xuat"] and ct["nhap"], ct)
kiem("chỉ thiếu, không thừa: 1 Repack + 1 phiếu xuất = 2 chứng từ (không đẻ phiếu nhập rỗng)",
     K.so_chung_tu(K.chia_chung_tu({"TP-SEN": K.lap_ke_hoach([A100], {H1: 60}, NSX.get)}, "2026-10-09")) == 2)
kiem("HSD đúng ngày chốt chưa tính là hết hạn", K.chia_chung_tu({"TP-DO": K.lap_ke_hoach(
    [lo("DO-150926", 4, ngay="2026-09-15")], {"2026-10-09": 4}, lambda h: None)}, "2026-10-09")["repack"])
ke_kl = K.lap_ke_hoach([lo(None, 50)], {H1: 40, H2: 15}, NSX.get)
ke_am = K.lap_ke_hoach([lo(None, -30)], {H2: 12}, NSX.get)
ke_le = K.lap_ke_hoach([lo(None, 3), lo("SEN-HSD080627", 30, hsd=H1, ngay="2026-09-11", chuan=True)], {H1: 33}, NSX.get)
ct = K.chia_chung_tu({"TP-RONG": ke_kl, "TP-KM": ke_am, "TP-SEN": ke_le, "TP-TUI": K.lap_ke_hoach([lo(None, 8)], {})},
                     "2026-10-09", {"TP-RONG": "bat", "TP-KM": "bat", "TP-SEN": "le"})
kiem("D189 chia chứng từ: tồn KHÔNG LÔ của mã chuyển sang lô → xuất (gộp một dòng mỗi mã) / nhập bù âm riêng; phần "
     "đếm được vào lô theo HSD ở phiếu nhập; không Repack",
     ct["xuat_kl"] == [{"item": "TP-RONG", "kho": None, "so": 50.0, "batch": None},
                       {"item": "TP-SEN", "kho": None, "so": 3.0, "batch": None}]
     and ct["nhap_kl"] == [{"item": "TP-KM", "kho": None, "so": 30.0, "batch": None}] and not ct["repack"]
     and ct["nhap_cu"] == []
     and sorted((x["item"], x["hsd"], x["so"]) for x in ct["nhap"])
     == [("TP-KM", H2, 12.0), ("TP-RONG", H1, 40.0), ("TP-RONG", H2, 5.0), ("TP-RONG", H2, 10.0), ("TP-SEN", H1, 3.0)], ct)
kiem("… mã KHÔNG chuyển (túi, còn tồn kho công ty khác) về 0 ở phiếu xuất thường; tổng 4 chứng từ",
     ct["xuat"] == [{"item": "TP-TUI", "batch": None, "so": 8.0}] and K.so_chung_tu(ct) == 4, ct)
ct = K.chia_chung_tu({"TP-RONG": ke_kl}, "2026-10-09", {"TP-RONG": "bat"},
                     {"TP-RONG": [("CH A", 54), ("CH B", 102), ("Xuong", -20093)]})
kiem("D191 tồn ở kho khác của mã bật lô: kho dương xuất ra rồi nhập lại nguyên số vào lô tồn cũ TẠI KHO ĐÓ; kho âm "
     "nhập bù về 0 — mỗi (mã, kho) một dòng",
     ct["xuat_kl"] == [{"item": "TP-RONG", "kho": None, "so": 50.0, "batch": None},
                       {"item": "TP-RONG", "kho": "CH A", "so": 54.0, "batch": None},
                       {"item": "TP-RONG", "kho": "CH B", "so": 102.0, "batch": None}]
     and ct["nhap_kl"] == [{"item": "TP-RONG", "kho": "Xuong", "so": 20093.0, "batch": None}]
     and ct["nhap_cu"] == [{"item": "TP-RONG", "kho": "CH A", "so": 54.0}, {"item": "TP-RONG", "kho": "CH B", "so": 102.0}]
     and K.so_chung_tu(ct) == 3, ct)
kiem("… chỉ có tồn ở kho khác (Kho TP không có gì để nhập) vẫn tính phiếu nhập lô tồn cũ",
     K.so_chung_tu(K.chia_chung_tu({"TP-X": K.lap_ke_hoach([], {})}, "2026-10-09", {"TP-X": "bat"},
                                   {"TP-X": [("CH A", 3)]})) == 2)

tl = K.gop_ton_lo({"SR170": 6265, "LOT": 82, "MOI": 0}, [{"item": "LOT", "b": "A", "q": 70}, {"item": "LOT", "b": "B", "q": 7},
                                                           {"item": "X", "b": "X1", "q": 3}])
kiem("D194 tồn theo lô: tổng của mã = số tồn ERPNext (qty_after_transaction dòng cuối — có cả Stock Reconciliation), "
     "các lô cộng từ lô, phần chênh là tồn KHÔNG lô; mã tổng 0 không đẻ dòng 0",
     sorted((r["item"], r["b"] or "", r["q"]) for r in tl)
     == [("LOT", "", 5.0), ("LOT", "A", 70.0), ("LOT", "B", 7.0), ("SR170", "", 6265.0), ("X", "X1", 3.0)], tl)

print("\n-- bán thành phẩm: kế hoạch theo LÔ (hàm thuần, D155) --")
R1, R5 = lo("R-011026", 40), lo("R-051026", 25.5)
ke = K.lap_ke_hoach_lo([R1, R5, lo("R-070926", 3, thu_hoi=True), lo("BBS-061026", -2)],
                       {"R-011026": 38.4, "R-280926": 2, "BBS-061026": 0.5})
kiem("lô cân ÍT hơn sổ: giữ phần cân thấy, xuất THIẾU phần chênh",
     {"batch": "R-011026", "hsd": None, "so": 38.4} in ke["giu"]
     and ke["xuat"] == [{"batch": "R-011026", "hsd": None, "so": 1.6}], ke)
kiem("lô CHƯA CÂN giữ nguyên — không vào sổ / đếm của phiếu, không sinh chứng từ",
     all("R-051026" not in str(ke[k]) for k in ("giu", "xuat", "nhap_lo", "bu_am")) and ke["so_sach"] == 38.0, ke)
kiem("lô sổ không có mà cân thấy hàng → NHẬP THỪA vào đúng lô đó",
     {"batch": "R-280926", "so": 2.0} in ke["nhap_lo"], ke["nhap_lo"])
kiem("lô âm: bù về 0 rồi nhập phần cân thấy", ke["bu_am"] == [{"batch": "BBS-061026", "hsd": None, "so": 2.0}]
     and {"batch": "BBS-061026", "so": 0.5} in ke["nhap_lo"], ke)
kiem("lô thu hồi: bỏ qua dù có số cân, sổ 40 + 0 − 2 = 38, cân 38,4 + 2 + 0,5 = 40,9",
     ke["bo_qua"] == [{"batch": "R-070926", "hsd": None, "so": 3.0}] and ke["dem"] == 40.9, ke)
ke = K.lap_ke_hoach_lo([lo("R-070926", 3, thu_hoi=True)], {"R-070926": 1})
kiem("… số cân của lô thu hồi không tính vào đếm", ke["dem"] == 0 and not K.co_thay_doi(ke), ke)
ke = K.lap_ke_hoach_lo([R5], {"R-051026": 25.5})
kiem("cân khớp sổ → không thay đổi gì", not K.co_thay_doi(ke) and ke["giu"] == [{"batch": "R-051026", "hsd": None,
                                                                                    "so": 25.5}], ke)
kiem("chỉ thừa (nhap_lo) cũng là có thay đổi", K.co_thay_doi(K.lap_ke_hoach_lo([R5], {"R-051026": 26})))
ke = K.lap_ke_hoach_lo([lo(None, 30)], {None: 31.25})
kiem("mã không quản lý lô: cân cả mã (lô None)", ke["nhap_lo"] == [{"batch": None, "so": 1.25}], ke)
ke = K.lap_ke_hoach_lo([R1, lo("R-280926", 0.0000001)], {"R-011026": 0, "R-280926": 0})
kiem("cân 0 = lô đã hết: xuất hết; lô sổ 0 cân 0 không đẻ dòng rác",
     ke["xuat"] == [{"batch": "R-011026", "hsd": None, "so": 40.0}] and not ke["nhap_lo"] and not ke["giu"], ke)
ke = K.lap_ke_hoach_lo([R1], {"R-011026": -5})
kiem("số cân âm (dữ liệu hỏng) coi như 0 — không bao giờ đẻ nhập âm", ke["dem"] == 0 and ke["xuat"] == [
    {"batch": "R-011026", "hsd": None, "so": 40.0}] and not ke["nhap_lo"], ke)
ke = K.lap_ke_hoach_lo([R1, lo("BBS-061026", -2)], {"R-011026": 41, "BBS-061026": 0})
bang = K.theo_lo(ke, lambda h: None)
kiem("bảng theo lô: R-011026 40 → 41 (nhập thừa 1), lô âm −2 → 0 (bù lô âm 2)",
     (bang["R-011026"]["truoc"], bang["R-011026"]["sau"], bang["R-011026"]["viec"]) == (40, 41, [("thua", None, 1.0)])
     and (bang["BBS-061026"]["truoc"], bang["BBS-061026"]["sau"]) == (-2, 0), bang)
ct = K.chia_chung_tu({"BOT-NEN": ke}, "2026-10-09")
kiem("chứng từ: không Repack; nhập đúng lô (thừa + bù âm) — 1 phiếu nhập",
     not ct["repack"] and not ct["xuat"] and K.so_chung_tu(ct) == 1
     and {"item": "BOT-NEN", "hsd": None, "batch": "R-011026", "so": 1.0} in ct["nhap"]
     and {"item": "BOT-NEN", "hsd": None, "batch": "BBS-061026", "so": 2.0} in ct["nhap"], ct)

# ═══════════════════════════════ 2. controller + API trên Frappe giả ═══════════════════════════════
print("\n-- phiếu kiểm kê: đếm, xem trước, chốt --")
F.CAI_DAT_SX.update({"kho_tp": "Kho TP", "cong_ty": "RVHG"})
KHO = "Kho TP"
for i, ten, lo_, han, pre in (("TP-SEN", "Bánh đậu xanh sen", 1, 270, "SEN"), ("TP-DO", "Bột đậu 500g", 1, 180, "DO"),
                              ("TP-KL", "Bánh không lô", 0, 270, "KL"), ("TP-MOI", "Hộp quà mới", 1, 365, "MOI")):
    F.bang("Item")[i] = {"name": i, "item_name": ten, "stock_uom": "Hộp", "custom_sx_nhom": "TP", "disabled": 0,
                         "has_batch_no": lo_, "shelf_life_in_days": han, "custom_batch_prefix": pre}
F.bang("Item")["BOT-NEN"] = {"name": "BOT-NEN", "item_name": "Bột nền", "stock_uom": "Kg", "custom_sx_nhom": "BTP-Bot",
                             "has_batch_no": 1, "disabled": 0}
F.bang("UOM Conversion Detail")["u1"] = {"name": "u1", "parent": "TP-SEN", "parenttype": "Item", "uom": "Thùng",
                                         "conversion_factor": 12}
for p in ("Repack", "Material Issue", "Material Receipt"):
    F.bang("Stock Entry Type")[p] = {"name": p, "purpose": p, "is_standard": 1}
F.bang("Bin")["b1"] = {"name": "b1", "item_code": "TP-SEN", "warehouse": KHO, "valuation_rate": 20000}
F.bang("Bin")["b2"] = {"name": "b2", "item_code": "TP-DO", "warehouse": KHO, "valuation_rate": 15000}
for b, i, hsd, nsx in (("SEN-100926", "TP-SEN", None, "2026-09-10"), ("SEN-200926", "TP-SEN", None, "2026-09-20"),
                       ("SEN-HSD080627", "TP-SEN", H1, "2026-09-11"), ("SEN-010926", "TP-SEN", None, "2026-09-01"),
                       ("DO-150926", "TP-DO", None, "2026-09-15")):
    F.bang("Batch")[b] = {"name": b, "item": i, "expiry_date": hsd, "manufacturing_date": nsx,
                          "creation": f"{nsx} 08:00:00", "custom_thu_hoi": 1 if b == "SEN-010926" else 0}

SO = {}             # sổ cái kho giả: (item, batch) → tồn tại Kho TP
SOB, SOX = {}, {}   # … tại Kho BTP, Kho Xuong (bán thành phẩm — D155)
SO_KHO = {KHO: SO, "Kho BTP": SOB, "Kho Xuong": SOX}
CHO_AM = {"v": False}  # site cho tồn âm (Stock Settings) — có lô âm trong kho nghĩa là đang bật
for (i, b), q in {("TP-SEN", "SEN-100926"): 100, ("TP-SEN", "SEN-200926"): 50, ("TP-SEN", "SEN-HSD080627"): 30,
                  ("TP-SEN", "SEN-010926"): 10, ("TP-DO", "DO-150926"): 40, ("TP-KL", None): 5}.items():
    SO[(i, b)] = q
SE_LOG = []


class StockEntry(F.Document):
    """Stock Entry giả: kiểm dòng như ERPNext cần, submit thì cộng / trừ sổ cái giả theo lô."""

    def validate(self):
        p = self.purpose
        for r in self.items or []:
            assert r.get("qty", 0) > 0, ("qty", r)
            assert bool(r.get("s_warehouse")) != bool(r.get("t_warehouse")), ("kho", r)
            if F.bang("Item")[r["item_code"]].get("has_batch_no", 1):
                assert r.get("use_serial_batch_fields") == 1 and r.get("batch_no"), ("lô", r)
                assert F.bang("Batch").get(r["batch_no"], {}).get("item") == r["item_code"], ("lô sai mã", r)
            else:                                    # ERPNext: mã không lô mà dòng có lô → lỗi
                assert not r.get("batch_no") and not r.get("use_serial_batch_fields"), ("mã không lô có lô", r)
            if p == "Material Issue":
                assert r.get("s_warehouse"), r
            if p == "Material Receipt":
                assert r.get("t_warehouse"), r
        # ERPNext so HSD với NGÀY GHI SỔ của phiếu (D195: phiếu ghi lùi có set_posting_time + posting_date).
        ngay = str(self.posting_date)[:10] if self.get("set_posting_time") else F.hom_nay().isoformat()
        if p not in ("Material Issue", "Material Transfer"):   # ERPNext StockController.validate_serialized_batch
            for r in self.items:
                hsd = F.bang("Batch").get(r.get("batch_no") or "", {}).get("expiry_date")
                assert not hsd or str(hsd)[:10] >= ngay, ("The batch has already expired", r["batch_no"])
        if p == "Repack":
            for r in self.items:                     # ERPNext StockEntry.validate_batch
                hsd = F.bang("Batch")[r["batch_no"]].get("expiry_date")
                assert not hsd or str(hsd)[:10] >= ngay, ("Batch has expired", r["batch_no"])
            assert any(r.get("is_finished_item") for r in self.items), "Repack thiếu thành phẩm"
            assert len({r["item_code"] for r in self.items}) == 1, "Repack trộn nhiều mã — trộn giá vốn"
        # phiếu của kiểm kê gắn số phiếu kiểm kê; phiếu dọn tồn âm (D193), dọn tồn không lô (D198) không thuộc phiếu
        # kiểm kê nào
        assert self.stock_entry_type == p and self.company == "RVHG" and (
            self.custom_kiem_ke or str(self.remarks or "").startswith(("Dọn tồn âm thành phẩm",
                                                                      "Dọn tồn không lô sau bật lô")))

    def _ghi(self, dau):
        for r in self.items:
            so = SO_KHO[r.get("t_warehouse") or r.get("s_warehouse")]
            k = (r["item_code"], r.get("batch_no"))
            co = so.get(k, 0)
            q = r["qty"] * (1 if r.get("t_warehouse") else -1) * dau
            assert co + q > -1e-9 or CHO_AM["v"], ("âm kho", k, co, q)
            so[k] = round(co + q, 6)

    def on_submit(self):
        self._ghi(1)
        SE_LOG.append(("submit", self.name, self.purpose))

    def on_cancel(self):
        self._ghi(-1)
        SE_LOG.append(("cancel", self.name, self.purpose))


F.dang_ky("Stock Entry", StockEntry)


class Batch(F.Document):
    pass


F.dang_ky("Batch", Batch, ten_theo="batch_id")

R = F.nap("sx.config.roles", "sx/config/roles.py")
U = F.nap("sx.utils", "sx/utils.py")
KT = F.nap("sx.api.khotp", "sx/api/khotp.py")
PN = F.nap("sx.sx.doctype.sx_phieu_nhap_tp.sx_phieu_nhap_tp", "sx/sx/doctype/sx_phieu_nhap_tp/sx_phieu_nhap_tp.py")
MFG = F.nap("sx.api.mfg", "sx/api/mfg.py")
XX_CAI = {"bat": True, "tn": date(2026, 10, 1), "duyet": set()}
xxa = types.ModuleType("sx.api.xuatxuong")
xxa._bat = lambda s=None: XX_CAI["bat"]
xxa.tu_ngay = lambda s=None: XX_CAI["tn"]
sys.modules["sx.api.xuatxuong"] = xxa
xxq = types.ModuleType("sx.qc.xuat_xuong")
xxq.chua_duyet = lambda cap: [(i, str(h)[:10], None) for i, h in cap if (i, str(h)[:10]) not in XX_CAI["duyet"]]
sys.modules["sx.qc.xuat_xuong"] = xxq
C = F.nap("sx.sx.doctype.sx_kiem_ke.sx_kiem_ke", "sx/sx/doctype/sx_kiem_ke/sx_kiem_ke.py")
C._so_lo = lambda kho, items, den=None: [F.Doc(item=i, b=b, q=q) for (i, b), q in SO_KHO.get(kho, {}).items()
                                         if i in items]
F.dang_ky("SX Kiem Ke", C.SXKiemKe)
A = F.nap("sx.api.kiemke", "sx/api/kiemke.py")


def hang(tq, item):
    return next((x for x in tq["hang"] if x["item"] == item), None)


F.vai("SX Thu Kho", u="kho@x")
tq = A.tong_quan()
sen = hang(tq, "TP-SEN")
kiem("chưa có phiếu: thẻ bày tồn từng mã — sổ 180 (bỏ lô thu hồi 10), chưa HSD 150, HSD 08/06/27: 30",
     tq["phieu"] is None and sen and sen["so_sach"] == 180 and sen["chua_hsd"] == 150 and sen["thu_hoi"] == 10
     and sen["theo_hsd"] == [{"hsd": H1, "so": 30}], sen)
kiem("bàn số có tab thùng / hộp theo bảng quy đổi của mã",
     sen["uoms"] == [{"uom": "Thùng", "he_so": 12}, {"uom": "Hộp", "he_so": 1}], sen["uoms"])
kiem("mã không quản lý lô: đánh dấu (D189: chốt sẽ bật lô, không còn tồn kho khác), xếp cuối",
     hang(tq, "TP-KL")["khong_lo"] and hang(tq, "TP-KL")["bat_lo"] and hang(tq, "TP-KL")["kho_khac"] == []
     and not hang(tq, "TP-SEN")["bat_lo"] and tq["hang"][-1]["item"] == "TP-KL", hang(tq, "TP-KL"))
kiem("thủ kho chốt được (D155)", tq["duoc_chot"] is True)

tq = A.bat_dau()
P = tq["phieu"]["name"]
kiem("BẮT ĐẦU KIỂM KÊ: mở phiếu đang đếm (người lập, giờ bắt đầu)",
     F.bang("SX Kiem Ke")[P]["trang_thai"] == "Đang đếm" and F.bang("SX Kiem Ke")[P]["nguoi_lap"] == "kho@x"
     and tq["phieu"]["duoc_huy"], tq["phieu"])
kiem("bấm lần nữa không mở phiếu thứ hai", A.bat_dau()["phieu"]["name"] == P and len(F.bang("SX Kiem Ke")) == 1)
kiem("+ MÃ KHÁC: danh mục thành phẩm chưa có trên sổ kho", [x["item"] for x in tq["danh_muc"]] == ["TP-MOI"])

ct = json.dumps([{"uom": "Thùng", "sl": 3, "he_so": 12}, {"uom": "Hộp", "sl": 4, "he_so": 1}])
tq = A.ghi(P, "TP-SEN", hsd=H1, so_dem=999, chi_tiet=ct)
kiem("ghi dòng có thùng / hộp: tổng tính lại từ chi tiết (3 × 12 + 4 = 40), không tin số máy gửi",
     hang(tq, "TP-SEN")["dem"][0]["so"] == 40 and hang(tq, "TP-SEN")["da_dem"], hang(tq, "TP-SEN")["dem"])
A.ghi(P, "TP-SEN", hsd=H2, so_dem=120)
kiem("trùng (mã, HSD) với dòng đang có → chặn", "đã có dòng HSD" in (thu(lambda: A.ghi(P, "TP-SEN", hsd=H1, so_dem=5)) or ""))
kiem("đổi HSD của dòng sang HSD dòng khác → chặn",
     "đã có dòng HSD" in (thu(lambda: A.ghi(P, "TP-SEN", hsd=H1, so_dem=118, hsd_cu=H2)) or ""))
tq = A.ghi(P, "TP-SEN", hsd=H2, so_dem=118, hsd_cu=H2)
kiem("sửa số của dòng (hsd_cu)", [x["so"] for x in hang(tq, "TP-SEN")["dem"]] == [40, 118], hang(tq, "TP-SEN")["dem"])
kiem("số > 0 mà thiếu HSD → chặn", "HSD" in (thu(lambda: A.ghi(P, "TP-SEN", hsd=None, so_dem=3)) or ""))
kiem("mã không phải thành phẩm → chặn", "không phải thành phẩm" in (thu(lambda: A.ghi(P, "BOT-NEN", hsd=H1, so_dem=3)) or ""))
tq = A.het_hang(P, "TP-DO")
kiem("KHÔNG CÒN: mã đã đếm, không còn hộp nào", hang(tq, "TP-DO")["da_dem"] and hang(tq, "TP-DO")["tong_dem"] == 0)
tq = A.ghi(P, "TP-DO", hsd="2027-03-15", so_dem=2)
kiem("ghi số cho mã đang \"không còn\" → bỏ dấu không còn", [x["hsd"] for x in hang(tq, "TP-DO")["dem"]] == ["2027-03-15"])
tq = A.ghi(P, "TP-DO", hsd="2027-03-15", so_dem=0, hsd_cu="2027-03-15")
kiem("sửa dòng về 0 → bỏ dòng (mã về chưa đếm)", not hang(tq, "TP-DO")["da_dem"])
A.het_hang(P, "TP-DO")
tq = A.ghi(P, "TP-MOI", hsd="2027-03-01", so_dem=6)
kiem("mã ngoài sổ đếm thấy → hiện trong danh sách", hang(tq, "TP-MOI")["da_dem"] and hang(tq, "TP-MOI")["so_sach"] == 0)

xt = A.xem_truoc(P)
ma = {x["item"]: x for x in xt["ma"]}
kiem("XEM TRƯỚC: không lỗi; sổ → đếm từng mã", not xt["loi"] and ma["TP-SEN"]["so_sach"] == 180
     and ma["TP-SEN"]["dem"] == 158 and ma["TP-DO"]["thieu"] == 40 and ma["TP-MOI"]["thua"] == 6, xt)
kiem("D188 đặt lại toàn kho: mã có tồn mà CHƯA ĐẾM (bánh không lô, 5) vào kế hoạch, về 0 — đánh dấu, xếp cuối, báo",
     ma["TP-KL"]["chua_dem"] and ma["TP-KL"]["thieu"] == 5 and ma["TP-KL"]["dem"] == 0
     and xt["ma"][-1]["item"] == "TP-KL" and not ma["TP-SEN"]["chua_dem"] and not ma["TP-DO"]["chua_dem"]
     and xt["tong"]["ve_0"] == 1 and any("CHƯA ĐẾM" in c and "Bánh không lô" in c for c in xt["canh_bao"]),
     (ma["TP-KL"], xt["canh_bao"]))
kiem("… chuyển 2 lô cũ sang 2 lô HSD, thiếu 22; số chứng từ kho sẽ sinh = 4 (thêm phiếu xuất tồn không lô — D189)",
     ma["TP-SEN"]["lo_cu"] == 2 and ma["TP-SEN"]["lo_moi"] == 2 and ma["TP-SEN"]["thieu"] == 22
     and xt["tong"]["phieu_kho"] == 4, (ma["TP-SEN"], xt["tong"]))
kiem("D189: mã chưa quản lý lô trong kế hoạch (bánh không lô, về 0) — chốt sẽ BẬT lô: đánh dấu, đếm, báo trước",
     ma["TP-KL"]["bat_lo"] and not ma["TP-SEN"]["bat_lo"] and xt["tong"]["bat_lo"] == 1
     and any("BẬT quản lý lô" in c and "Bánh không lô" in c for c in xt["canh_bao"]), (ma["TP-KL"], xt["canh_bao"]))
R.CARD_ROLES["kiemke"].append("SX QC")
F.vai("SX QC", u="qc@x")
kiem("vai khác thủ kho / quản lý (thẻ có mở cho) → không chốt được", "thủ kho / quản lý" in (thu(lambda: A.chot(P)) or ""))
R.CARD_ROLES["kiemke"].remove("SX QC")
F.vai("SX Thu Kho", u="kho@x")

F.bang("SX Phieu Nhap TP")["PN1"] = {"name": "PN1", "docstatus": 0}
kiem("còn phiếu nhập kho nháp → cảnh báo (không chặn)", any("phiếu nhập kho nháp" in c for c in A.xem_truoc(P)["canh_bao"]))
F.bang("SX Phieu Nhap TP").clear()

kq = A.chot(P)
d = F.bang("SX Kiem Ke")[P]
kiem("CHỐT (thủ kho — D155): phiếu Đã chốt, người chốt, tổng sổ 225 → đếm 164, lệch −61 (gồm mã chưa đếm về 0)",
     d["docstatus"] == 1 and d["trang_thai"] == "Đã chốt" and d["nguoi_chot"] == "kho@x"
     and (d["tong_so_sach"], d["tong_dem"], d["tong_lech"], d["so_ma"]) == (225, 164, -61, 4), kq)
ds = json.loads(d["ds_se"])
kiem("chứng từ kho: xuất tồn không lô (mã chuyển sang lô — ghi TRƯỚC khi bật, D189) → bật lô → Repack (chuyển lô) → "
     "Material Issue (thiếu) → Material Receipt (thừa)",
     [x["dt"] if x["dt"] == "Item" else F.bang("Stock Entry")[x["name"]]["purpose"] for x in ds]
     == ["Material Issue", "Item", "Repack", "Material Issue", "Material Receipt"], ds)
kl, *se = [F.bang("Stock Entry")[x["name"]] for x in ds if x["dt"] == "Stock Entry"]
rp = se[0]["items"]
kiem("Repack của mã SEN: tiêu lô cũ 50 + 78, ra lô HSD 10 + 118 (dòng ra là thành phẩm)",
     sorted((r["batch_no"], r["qty"]) for r in rp if r.get("s_warehouse")) == [("SEN-100926", 78), ("SEN-200926", 50)]
     and sorted((r["batch_no"], r["qty"], r.get("is_finished_item")) for r in rp if r.get("t_warehouse"))
     == [("SEN-HSD080627", 10, 1), ("SEN-HSD180627", 118, 1)], rp)
kiem("nhập thừa mã chưa có giá vốn → cho giá 0 (không bịa giá)",
     se[2]["items"][0].get("allow_zero_valuation_rate") == 1 and se[2]["items"][0]["batch_no"] == "MOI-HSD010327")
kiem("TỒN SAU CHỐT = SỐ ĐẾM theo từng HSD; lô cũ về 0; lô thu hồi giữ nguyên",
     SO[("TP-SEN", "SEN-HSD080627")] == 40 and SO[("TP-SEN", "SEN-HSD180627")] == 118
     and SO[("TP-SEN", "SEN-100926")] == 0 and SO[("TP-SEN", "SEN-200926")] == 0
     and SO[("TP-SEN", "SEN-010926")] == 10 and SO[("TP-DO", "DO-150926")] == 0
     and SO[("TP-MOI", "MOI-HSD010327")] == 6 and SO[("TP-KL", None)] == 0, SO)
kiem("… mã không quản lý lô chưa đếm: về 0 bằng phiếu xuất KHÔNG lô riêng (lúc mã còn tắt lô), rồi bật lô cho mã",
     kl["purpose"] == "Material Issue"
     and [{k: r.get(k) for k in ("item_code", "qty", "s_warehouse")} for r in kl["items"]]
     == [{"item_code": "TP-KL", "qty": 5.0, "s_warehouse": KHO}] and not kl["items"][0].get("batch_no")
     and F.bang("Item")["TP-KL"]["has_batch_no"] == 1
     and {"dt": "Item", "name": "TP-KL", "has_batch_no": [0, 1]} in ds, (kl["items"], ds))
b = F.bang("Batch")
kiem("lô theo HSD mới: HSD đúng, NSX = HSD − hạn dùng, đánh dấu nhận hàng tồn cũ qua phiếu này",
     str(b["SEN-HSD180627"]["expiry_date"]) == H2 and str(b["SEN-HSD180627"]["manufacturing_date"]) == "2026-09-21"
     and b["SEN-HSD180627"]["custom_kiem_ke"] == P and b["MOI-HSD010327"]["custom_kiem_ke"] == P
     and b["SEN-HSD080627"]["custom_kiem_ke"] == P, {k: v.get("custom_kiem_ke") for k, v in b.items()})
kiem("mọi chứng từ kho gắn số phiếu kiểm kê", all(x["custom_kiem_ke"] == P for x in se + [kl]))
lo_bang = {r["batch"]: r for r in d["lo"]}
kiem("bảng kết quả theo lô ghi trước → sau + việc",
     (lo_bang["SEN-100926"]["so_truoc"], lo_bang["SEN-100926"]["so_sau"]) == (100, 0)
     and "chuyển 78 sang lô HSD 18/06/27" in lo_bang["SEN-100926"]["viec"]
     and "xuất thiếu 22" in lo_bang["SEN-100926"]["viec"]
     and "đang thu hồi" in lo_bang["SEN-010926"]["viec"]
     and lo_bang["SEN-HSD080627"]["so_sau"] == 40, {k: (v["so_truoc"], v["so_sau"], v["viec"]) for k, v in lo_bang.items()})
kiem("phiếu đã chốt: không ghi thêm được", "đã chốt" in (thu(lambda: A.ghi(P, "TP-SEN", hsd=H1, so_dem=1)) or ""))
html = A.bien_ban(P)
kiem("biên bản: tên, sổ / đếm / lệch, kết quả lô, chứng từ, chỗ ký",
     "Biên bản kiểm kê kho thành phẩm" in html and "Bánh đậu xanh sen" in html and "-61" in html
     and "SEN-HSD180627" in html and "Kế toán" in html and se[0]["name"] in html and "BẢN NHÁP" not in html)
kiem("… biên bản có cả mã chưa đếm đã về 0 (D188): ghi rõ, sổ 5 → 0",
     "Bánh không lô" in html and "chưa đếm — về 0" in html and "Cộng 4 mã" in " ".join(html.split()), html)
kiem("… biên bản ghi mã đã bật quản lý lô (D189), chứng từ kho không lẫn dòng đổi cờ",
     "Đã bật quản lý theo lô cho mã: Bánh không lô" in " ".join(html.split()) and kl["name"] in html
     and "TP-KL, " not in html, html)
kiem("chốt trả số chứng từ kho thật (không đếm dòng đổi cờ lô)", kq["so_phieu_kho"] == 4, kq)
gd = A.tong_quan()["gan_day"]
kiem("thẻ: phiếu vừa chốt vào danh sách gần đây", gd and gd[0]["name"] == P and gd[0]["tong_lech"] == -61, gd)

print("\n-- chốt chặn --")
F.vai("SX Thu Kho", u="kho@x")
P2 = A.bat_dau()["phieu"]["name"]
A.ghi(P2, "TP-SEN", hsd=H1, so_dem=40)
dd = F.bang("SX Kiem Ke")[P2]
dd["dong"][0]["dem_luc"] = "2026-10-09 09:00:00"
F.bang("Stock Ledger Entry")["s1"] = {"name": "s1", "item_code": "TP-SEN", "warehouse": KHO, "voucher_type": "Sales Invoice",
                                      "voucher_no": "SINV-0007", "actual_qty": -5, "creation": "2026-10-09 09:30:00",
                                      "modified": "2026-10-09 09:30:00", "is_cancelled": 0}
F.bang("Stock Ledger Entry")["s2"] = {"name": "s2", "item_code": "TP-SEN", "warehouse": KHO, "voucher_type": "Stock Entry",
                                      "voucher_no": "SE-REPOST", "actual_qty": 7, "creation": "2026-10-08 09:00:00",
                                      "modified": "2026-10-09 09:40:00", "is_cancelled": 0}
F.bang("Stock Ledger Entry")["s3"] = {"name": "s3", "item_code": "TP-SEN", "warehouse": KHO, "voucher_type": "Delivery Note",
                                      "voucher_no": "DN-0003", "actual_qty": -2, "creation": "2026-10-09 09:10:00",
                                      "modified": "2026-10-09 09:20:00", "is_cancelled": 1}
F.bang("Stock Ledger Entry")["s4"] = {"name": "s4", "item_code": "TP-SEN", "warehouse": KHO, "voucher_type": "Sales Invoice",
                                      "voucher_no": "SINV-0001", "actual_qty": -3, "creation": "2026-10-08 15:00:00",
                                      "modified": "2026-10-09 09:50:00", "is_cancelled": 1}
loi = " ".join(A.xem_truoc(P2)["loi"])
kiem("mã có chứng từ kho SAU lúc đếm → chặn chốt, kể chứng từ (bán sau đếm; huỷ phiếu cũ sau đếm)",
     "sau lúc đếm" in loi and "SINV-0007 (-5)" in loi and "SINV-0001 (+3)" in loi, loi)
kiem("… không kể SLE chỉ repost lại giá, không kể phiếu tạo rồi huỷ sau đếm (số không đổi)",
     "SE-REPOST" not in loi and "DN-0003" not in loi, loi)
F.bang("Stock Ledger Entry")["s5"] = {"name": "s5", "item_code": "TP-SEN", "warehouse": KHO, "voucher_type": "Stock Reconciliation",
                                      "voucher_no": "MAT-RECO-0001", "actual_qty": 0, "creation": "2026-10-09 09:45:00",
                                      "modified": "2026-10-09 09:45:00", "is_cancelled": 0}
loi = " ".join(A.xem_truoc(P2)["loi"])
kiem("D194: Stock Reconciliation sau lúc đếm (đặt thẳng số tồn, actual_qty = 0) cũng tính là chứng từ đổi sổ",
     "MAT-RECO-0001 (đặt lại tồn)" in loi, loi)
F.bang("Stock Ledger Entry").pop("s5")
F.vai("SX Quan Ly", u="ql@x")
n_truoc = len(F.bang("Stock Entry"))
kiem("chốt lúc đó → không được, nói đếm lại", "ĐẾM LẠI" in (thu(lambda: A.chot(P2)) or ""))
kiem("… chốt hỏng thì phiếu vẫn đang đếm, chưa sinh chứng từ nào",
     F.bang("SX Kiem Ke")[P2]["docstatus"] == 0 and len(F.bang("Stock Entry")) == n_truoc == 4)
F.vai("SX Thu Kho", u="kho@x")
A.dem_lai(P2, "TP-SEN")
kiem("ĐẾM LẠI: bỏ mọi dòng của mã", not hang(A.tong_quan(), "TP-SEN")["da_dem"])
A.ghi(P2, "TP-SEN", hsd=H1, so_dem=40)
kiem("đếm lại sau chứng từ đó → hết chặn", not A.xem_truoc(P2)["loi"], A.xem_truoc(P2)["loi"])
for k in ("s1", "s2", "s3", "s4"):
    F.bang("Stock Ledger Entry").pop(k)

A.ghi(P2, "TP-SEN", hsd="2027-07-01", so_dem=3)
xt = A.xem_truoc(P2)
cb = " ".join(xt["canh_bao"])
kiem("D188: HSD của hàng làm SAU ngày áp dụng BM.08.04 chưa duyệt → KHÔNG chặn chốt, cảnh báo chưa bán được",
     not xt["loi"] and "BM.08.04" in cb and "01/07/27" in cb and "CHƯA BÁN ĐƯỢC" in cb, (xt["loi"], cb))
A.ghi(P2, "TP-SEN", hsd="2027-06-28", so_dem=2)
kiem("… kể cả hàng làm ĐÚNG ngày áp dụng (NSX 01/10/26 = ngày áp dụng)",
     "28/06/27" in " ".join(A.xem_truoc(P2)["canh_bao"]), A.xem_truoc(P2)["canh_bao"])
A.ghi(P2, "TP-SEN", hsd="2027-06-28", so_dem=0, hsd_cu="2027-06-28")
XX_CAI["duyet"].add(("TP-SEN", "2027-07-01"))
kiem("đã duyệt xuất xưởng → hết cảnh báo", not any("BM.08.04" in c for c in A.xem_truoc(P2)["canh_bao"]))
XX_CAI["duyet"].clear()
XX_CAI["bat"] = False
kiem("tắt chặn BM.08.04 ở SX Settings → không cảnh báo", not any("BM.08.04" in c for c in A.xem_truoc(P2)["canh_bao"]))
XX_CAI["bat"] = True
A.ghi(P2, "TP-SEN", hsd="2027-07-01", so_dem=0, hsd_cu="2027-07-01")

SO[("TP-KL", None)] = 5
F.bang("Stock Ledger Entry")["k1"] = {"name": "k1", "item_code": "TP-KL", "warehouse": KHO, "actual_qty": 5,
                                      "creation": "2026-09-01 08:00:00", "modified": "2026-09-01 08:00:00", "is_cancelled": 0}
A.ghi(P2, "TP-KL", hsd=H1, so_dem=5)
xt2 = A.xem_truoc(P2)
kiem("D189: mã (đã bật lô ở phiếu trước) còn tồn KHÔNG gắn lô, đếm theo HSD → không chặn; báo đưa phần đó về 0 / vào lô",
     not any("không quản lý" in x or "KHÔNG gắn lô" in x for x in xt2["loi"])
     and any("KHÔNG gắn lô" in c and "Bánh không lô" in c for c in xt2["canh_bao"])
     and next(x for x in xt2["ma"] if x["item"] == "TP-KL")["le_khong_lo"], (xt2["loi"], xt2["canh_bao"]))
A.dem_lai(P2, "TP-KL")

dd = F.get_doc("SX Kiem Ke", P2)
dd.set("dong", [F.Doc(item="TP-DO", hsd=None, so_dem=0), F.Doc(item="TP-DO", hsd="2027-03-15", so_dem=4),
                F.Doc(item="TP-SEN", hsd=H1, so_dem=40)])
dd.save()
kiem("lưu phiếu (cả trên Desk): mã có dòng số thì bỏ dòng \"không còn hàng\"",
     [(r["item"], r["hsd"]) for r in F.bang("SX Kiem Ke")[P2]["dong"]] == [("TP-DO", "2027-03-15"), ("TP-SEN", H1)],
     F.bang("SX Kiem Ke")[P2]["dong"])
dd = F.get_doc("SX Kiem Ke", P2)
dd.append("dong", {"item": "TP-SEN", "hsd": H1, "so_dem": 3})
kiem("lưu phiếu có hai dòng cùng (mã, HSD) → chặn, bảo gộp", "gộp" in (thu(dd.save) or ""))
dd = F.get_doc("SX Kiem Ke", P2)
dd.append("dong", {"item": "TP-SEN", "hsd": None, "so_dem": 3})
kiem("dòng có số mà thiếu HSD → chặn", "HSD" in (thu(dd.save) or ""))
A.dem_lai(P2, "TP-DO")
F.vai("SX Quan Ly", u="ql@x")
kiem("phiếu đã chốt: submit lại → chặn", "đang đếm" in (thu(lambda: F.get_doc("SX Kiem Ke", P).submit()) or ""))
SO[("TP-SEN", None)] = 3
xt2 = A.xem_truoc(P2)
kiem("mã có lô mà còn tồn KHÔNG gắn lô → không chặn nữa (D189), dòng mã ghi \"tồn không lô về 0\"",
     not any("KHÔNG gắn lô" in x for x in xt2["loi"])
     and any("KHÔNG gắn lô" in c and "Bánh đậu xanh sen" in c for c in xt2["canh_bao"])
     and next(x for x in xt2["ma"] if x["item"] == "TP-SEN")["le_khong_lo"], (xt2["loi"], xt2["canh_bao"]))
SO.pop(("TP-SEN", None))
F.vai("SX Thu Kho", u="kho2@x")
kiem("thủ kho KHÁC người lập không bỏ được phiếu", "người lập" in (thu(lambda: A.huy(P2)) or ""))
F.vai("SX Thu Kho", u="kho@x")
html = A.bien_ban(P2)
kiem("in biên bản lúc đang đếm: ghi BẢN NHÁP, sổ tính tới lúc in", "BẢN NHÁP" in html and "Bánh đậu xanh sen" in html)
A.huy(P2)
kiem("người lập bỏ phiếu đang đếm → xoá, chưa có gì vào kho", P2 not in F.bang("SX Kiem Ke"))

print("\n-- huỷ phiếu đã chốt (Desk) --")
F.vai("System Manager", u="admin@x")
truoc = dict(SO)
F.get_doc("SX Kiem Ke", P).cancel()
d = F.bang("SX Kiem Ke")[P]
kiem("huỷ: các chứng từ kho huỷ theo thứ tự NGƯỢC (thừa → thiếu → chuyển lô → tồn không lô)",
     [x[2] for x in SE_LOG if x[0] == "cancel"] == ["Material Receipt", "Material Issue", "Repack", "Material Issue"],
     SE_LOG)
kiem("… mã đã bật lô ở phiếu đó trả về KHÔNG lô (đúng như trước chốt — D189)",
     F.bang("Item")["TP-KL"]["has_batch_no"] == 0)
kiem("… tồn về như trước chốt", SO[("TP-SEN", "SEN-100926")] == 100 and SO[("TP-SEN", "SEN-200926")] == 50
     and SO[("TP-SEN", "SEN-HSD080627")] == 30 and SO[("TP-SEN", "SEN-HSD180627")] == 0
     and SO[("TP-DO", "DO-150926")] == 40, {k: v for k, v in SO.items() if v != truoc.get(k)})
kiem("… gỡ dấu lô, phiếu Đã huỷ", d["trang_thai"] == "Đã huỷ"
     and not any(v.get("custom_kiem_ke") == P for v in F.bang("Batch").values()))

print("\n-- hàng hết hạn trong kho --")
F.vai("SX Quan Ly", u="ql@x")
P3 = A.bat_dau()["phieu"]["name"]
A.ghi(P3, "TP-DO", hsd="2026-09-01", so_dem=10)
A.ghi(P3, "TP-DO", hsd="2027-03-15", so_dem=25)
n_se = len(F.bang("Stock Entry"))
SO_TRUOC = dict(SO)
xt = A.xem_truoc(P3)
kiem("xem trước: hàng hết hạn vẫn đếm được, không lỗi; 4 chứng từ (tồn không lô của bánh không lô + Repack phần còn "
     "hạn + xuất + nhập)", not xt["loi"] and xt["tong"]["phieu_kho"] == 4, xt)
A.chot(P3)
se3 = [F.bang("Stock Entry")[x["name"]] for x in json.loads(F.bang("SX Kiem Ke")[P3]["ds_se"])
       if x["dt"] == "Stock Entry"]
kiem("chốt: Repack chỉ có phần còn hạn; lô hết hạn đi xuất + nhập — không văng \"Batch has expired\"",
     [x["purpose"] for x in se3] == ["Material Issue", "Repack", "Material Issue", "Material Receipt"]
     and all(r["batch_no"] != "DO-HSD010926" for r in se3[1]["items"])
     and any(r["batch_no"] == "DO-HSD010926" for r in se3[3]["items"]), [(x["purpose"], x["items"]) for x in se3])
kiem("tồn sau chốt: HSD 01/09/26 (hết hạn) 10, HSD 15/03/27 25, lô cũ 40 → 5 thiếu xuất hết",
     SO[("TP-DO", "DO-HSD010926")] == 10 and SO[("TP-DO", "DO-HSD150327")] == 25 and SO[("TP-DO", "DO-150926")] == 0,
     {k: v for k, v in SO.items() if k[0] == "TP-DO"})
kiem("D190: phiếu nhập vào lô HẾT HẠN qua được chặn của ERPNext (tạm bỏ HSD lúc ghi) — ghi xong lô giữ đúng HSD cũ",
     str(F.bang("Batch")["DO-HSD010926"]["expiry_date"]) == "2026-09-01", F.bang("Batch")["DO-HSD010926"])
F.get_doc("SX Kiem Ke", P3).cancel()
kiem("huỷ phiếu đó: tồn về như trước", all(abs(SO.get(k, 0) - SO_TRUOC.get(k, 0)) < 1e-9 for k in set(SO) | set(SO_TRUOC)))

print("\n-- D188: chốt = đặt lại toàn kho (mỗi mã, mỗi HSD một lô; mã không đếm về 0) --")
F.vai("SX Thu Kho", u="kho@x")
F.bang("Batch")["SEN-110926"] = {"name": "SEN-110926", "item": "TP-SEN", "expiry_date": H1,
                                 "manufacturing_date": "2026-09-10", "creation": "2026-09-10 08:00:00",
                                 "custom_thu_hoi": 0}
SO[("TP-SEN", "SEN-110926")] = 20
F.bang("Item")["TP-THU"] = {"name": "TP-THU", "item_name": "Bánh đang thu hồi", "stock_uom": "Hộp", "custom_sx_nhom": "TP",
                            "disabled": 0, "has_batch_no": 1, "shelf_life_in_days": 270, "custom_batch_prefix": "THU"}
F.bang("Batch")["THU-050926"] = {"name": "THU-050926", "item": "TP-THU", "expiry_date": None,
                                 "manufacturing_date": "2026-09-05", "creation": "2026-09-05 08:00:00", "custom_thu_hoi": 1}
SO[("TP-THU", "THU-050926")] = 7      # mã chỉ còn lô đang thu hồi — để riêng, không phải "chưa đếm"
frappe.local.__dict__.pop("sx_nho", None)   # request mới: items_tp đọc lại danh mục (có mã vừa thêm)
SO_TRUOC = dict(SO)
P4 = A.bat_dau()["phieu"]["name"]
F.bang("SX Kiem Ke")[P4]["bat_dau_luc"] = "2026-10-09 08:00:00"
A.ghi(P4, "TP-SEN", hsd=H1, so_dem=45)
A.ghi(P4, "TP-SEN", hsd="2027-07-01", so_dem=3)
F.bang("Stock Ledger Entry")["d1"] = {"name": "d1", "item_code": "TP-DO", "warehouse": KHO, "voucher_type": "Delivery Note",
                                      "voucher_no": "DN-0009", "actual_qty": -1, "creation": "2026-10-09 09:00:00",
                                      "modified": "2026-10-09 09:00:00", "is_cancelled": 0}
loi = " ".join(A.xem_truoc(P4)["loi"])
kiem("mã CHƯA ĐẾM (sắp về 0) có chứng từ kho sau lúc bắt đầu kiểm kê → chặn chốt, bảo đếm / bấm KHÔNG CÒN",
     "chưa đếm mà có chứng từ kho sau lúc bắt đầu" in loi and "DN-0009" in loi and "Bột đậu 500g" in loi, loi)
A.het_hang(P4, "TP-DO")
xt = A.xem_truoc(P4)
ma = {x["item"]: x for x in xt["ma"]}
kiem("… bấm KHÔNG CÒN (đếm 0 sau chứng từ đó) → hết chặn; còn MỘT mã chưa đếm về 0 (bánh không lô); mã chỉ còn lô "
     "thu hồi không tính là chưa đếm",
     not xt["loi"] and xt["tong"]["ve_0"] == 1 and ma["TP-KL"]["chua_dem"] and not ma["TP-DO"]["chua_dem"]
     and "TP-THU" not in ma, (xt["loi"], xt["tong"], list(ma)))
F.bang("Stock Ledger Entry").pop("d1")
kiem("… lô làm từ ngày áp dụng BM.08.04 chưa duyệt (HSD 01/07/27): cảnh báo, không chặn",
     any("BM.08.04" in c and "01/07/27" in c for c in xt["canh_bao"]), xt["canh_bao"])
A.chot(P4)
se4 = [F.bang("Stock Entry")[x["name"]] for x in json.loads(F.bang("SX Kiem Ke")[P4]["ds_se"])
       if x["dt"] == "Stock Entry"]
rp = next(x for x in se4 if x["purpose"] == "Repack")["items"]
kiem("Repack: lô cũ CÙNG HSD (SEN-110926) gộp 15 vào lô chuẩn trước; HSD mới lấy 3 từ lô cũ gần nhất",
     sorted((r["batch_no"], r["qty"]) for r in rp if r.get("s_warehouse")) == [("SEN-110926", 15), ("SEN-200926", 3)]
     and sorted((r["batch_no"], r["qty"]) for r in rp if r.get("t_warehouse"))
     == [("SEN-HSD010727", 3), ("SEN-HSD080627", 15)], rp)
con = {b: q for (i, b), q in SO.items() if i == "TP-SEN" and q > 1e-9 and not F.bang("Batch")[b].get("custom_thu_hoi")}
kiem("sau chốt mỗi HSD đúng MỘT lô: SEN-HSD080627 = 45 (HSD 08/06/27), SEN-HSD010727 = 3; lô cũ về 0; lô thu hồi "
     "giữ nguyên", con == {"SEN-HSD080627": 45, "SEN-HSD010727": 3} and SO[("TP-SEN", "SEN-010926")] == 10
     and len({str(F.bang("Batch")[b]["expiry_date"]) for b in con}) == len(con), con)
kiem("mã không đếm / đếm KHÔNG CÒN về 0 (bột đậu, bánh không lô); lô đang thu hồi của mã khác giữ nguyên",
     SO[("TP-DO", "DO-150926")] == 0 and SO[("TP-KL", None)] == 0 and SO[("TP-THU", "THU-050926")] == 7,
     {k: v for k, v in SO.items() if k[0] in ("TP-DO", "TP-KL", "TP-THU")})
b = F.bang("Batch")
kiem("lô nhận hàng tồn cũ đánh dấu kiểm kê (bán không cần BM.08.04); lô hàng làm từ ngày áp dụng chưa duyệt "
     "KHÔNG đánh dấu — bán phải duyệt", b["SEN-HSD080627"].get("custom_kiem_ke") == P4
     and not b["SEN-HSD010727"].get("custom_kiem_ke"), {k: b[k].get("custom_kiem_ke") for k in ("SEN-HSD080627",
                                                                                                   "SEN-HSD010727")})
F.vai("System Manager", u="admin@x")
F.get_doc("SX Kiem Ke", P4).cancel()
kiem("huỷ phiếu đặt lại kho: tồn về như trước",
     all(abs(SO.get(k, 0) - SO_TRUOC.get(k, 0)) < 1e-9 for k in set(SO) | set(SO_TRUOC)))
SO.pop(("TP-SEN", "SEN-110926"))
SO.pop(("TP-THU", "THU-050926"))
F.bang("Item").pop("TP-THU")
F.bang("Batch").pop("THU-050926")
frappe.local.__dict__.pop("sx_nho", None)

print("\n-- D189 + D191: mã chưa quản lý lô — đếm theo HSD, chốt bật lô (xử lý cả tồn ở kho khác) --")
F.vai("SX Thu Kho", u="kho@x")
SO_GOC = dict(SO)
SO.clear()                       # riêng phần này: chỉ các mã dưới đây có tồn ở Kho TP
CHO_AM["v"] = True               # site cho tồn âm — mã bán khi chưa nhập kho đang âm
for i, ten in (("TP-RONG", "Thỏi vàng Rồng 200g"), ("TP-KM", "Khoai môn H24 300g"), ("TP-TUI", "Túi 250g"),
               ("TP-CTYB", "Bánh gửi công ty B")):
    F.bang("Item")[i] = {"name": i, "item_name": ten, "stock_uom": "Hộp", "custom_sx_nhom": "TP", "disabled": 0,
                         "has_batch_no": 0, "shelf_life_in_days": 270, "custom_batch_prefix": i[3:]}
SO.update({("TP-RONG", None): 50,      # dương: đếm 40 HSD 08/06/27 + 15 HSD 18/06/27 → 50 vào lô + 5 thừa
           ("TP-KM", None): -30,       # âm (bán khi chưa nhập kho): đếm 12 → bù âm 30 rồi 12 vào lô
           ("TP-TUI", None): 8,        # còn 2 hộp ở cửa hàng → chốt chuyển nguyên số vào lô tồn cũ tại cửa hàng
           ("TP-CTYB", None): 4,       # còn tồn ở kho của CÔNG TY KHÁC → không bật lô được
           ("TP-SEN", None): 3, ("TP-SEN", "SEN-HSD080627"): 30})   # mã có lô mà còn tồn không lô (dữ liệu cũ)
for k, cty in (("CH Le", "RVHG"), ("Xuong", "RVHG"), ("Kho Cty B", "CTY-B")):
    F.bang("Warehouse")[k] = {"name": k, "company": cty}
    SO_KHO[k] = {}
SO_KHO["CH Le"][("TP-TUI", None)] = 2
SO_KHO["Xuong"][("TP-RONG", None)] = -20
SO_KHO["Kho Cty B"][("TP-CTYB", None)] = 5
F.bang("Bin")["bk1"] = {"name": "bk1", "item_code": "TP-TUI", "warehouse": "CH Le", "actual_qty": 2, "valuation_rate": 9000}
F.bang("Bin")["bk2"] = {"name": "bk2", "item_code": "TP-RONG", "warehouse": KHO, "actual_qty": 50, "valuation_rate": 12000}
F.bang("Bin")["bk3"] = {"name": "bk3", "item_code": "TP-RONG", "warehouse": "Xuong", "actual_qty": -20,
                        "valuation_rate": 11000}
F.bang("Bin")["bk4"] = {"name": "bk4", "item_code": "TP-CTYB", "warehouse": "Kho Cty B", "actual_qty": 5}
frappe.local.__dict__.pop("sx_nho", None)
SO_TRUOC = {k: dict(v) for k, v in SO_KHO.items()}
tq = A.tong_quan()
r_, t_, s_, c_ = hang(tq, "TP-RONG"), hang(tq, "TP-TUI"), hang(tq, "TP-SEN"), hang(tq, "TP-CTYB")
kiem("thẻ: mã chưa quản lý lô là dòng đếm được (sẽ bật lô); tồn ở kho khác ghi kho, số (kho công ty khác đánh dấu); "
     "mã có lô lẫn tồn không lô ghi số đó",
     r_["bat_lo"] and r_["kho_khac"] == [{"kho": "Xuong", "so": -20, "cty_khac": False}] and t_["bat_lo"]
     and t_["kho_khac"] == [{"kho": "CH Le", "so": 2, "cty_khac": False}]
     and c_["kho_khac"] == [{"kho": "Kho Cty B", "so": 5, "cty_khac": True}]
     and not s_["bat_lo"] and s_["le_khong_lo"] == 3, (r_, t_, s_, c_))
P5 = A.bat_dau()["phieu"]["name"]
A.ghi(P5, "TP-RONG", hsd=H1, so_dem=40)
A.ghi(P5, "TP-RONG", hsd=H2, so_dem=15)
A.ghi(P5, "TP-KM", hsd=H2, so_dem=12)
A.ghi(P5, "TP-TUI", hsd=H1, so_dem=8)
A.ghi(P5, "TP-SEN", hsd=H1, so_dem=33)
A.ghi(P5, "TP-CTYB", hsd=H1, so_dem=4)
xt = A.xem_truoc(P5)
kiem("mã chưa quản lý lô còn tồn ở kho của CÔNG TY KHÁC mà có số đếm → chặn chốt, nói kho, số (kho khác cùng công ty "
     "không chặn — D191)", len(xt["loi"]) == 1 and "CÔNG TY KHÁC" in xt["loi"][0]
     and "Bánh gửi công ty B — Kho Cty B: 5" in xt["loi"][0] and "Túi" not in xt["loi"][0], xt["loi"])
A.het_hang(P5, "TP-CTYB")
xt = A.xem_truoc(P5)
m5 = {x["item"]: x for x in xt["ma"]}
kiem("… mã đó bấm KHÔNG CÒN → hết chặn; chỉ về 0 ở Kho TP, vẫn để không lô (cảnh báo)",
     not xt["loi"] and not m5["TP-CTYB"]["bat_lo"]
     and any("công ty khác" in c and "Bánh gửi công ty B" in c and "không lô" in c for c in xt["canh_bao"]),
     (xt["loi"], xt["canh_bao"]))
kiem("xem trước: 3 mã bật lô, 1 mã dọn tồn không lô; báo trước từng kho khác (cửa hàng → lô tồn cũ, xưởng âm → về 0)",
     m5["TP-RONG"]["bat_lo"] and m5["TP-KM"]["bat_lo"] and m5["TP-TUI"]["bat_lo"] and m5["TP-SEN"]["le_khong_lo"]
     and xt["tong"]["bat_lo"] == 3 and xt["tong"]["phieu_kho"] == 4
     and any("BẬT quản lý lô" in c and "Khoai môn H24 300g, Thỏi vàng Rồng 200g, Túi 250g" in c for c in xt["canh_bao"])
     and any("kho khác" in c and "Thỏi vàng Rồng 200g (Xuong -20 → về 0)" in c and "Túi 250g (CH Le 2 → lô tồn cũ)" in c
             and "điều chỉnh kho (báo kế toán)" in c for c in xt["canh_bao"]), (xt["tong"], xt["canh_bao"]))
kiem("… tổng ghi riêng tồn âm ở kho khác sẽ đưa về 0 (để hộp xác nhận nói rõ)",
     xt["tong"]["kho_am"] == [{"ten": "Thỏi vàng Rồng 200g", "kho": "Xuong", "so": -20}], xt["tong"]["kho_am"])
html = " ".join(A.bien_ban(P5).split())
kiem("biên bản nháp: ghi mã SẼ bật quản lý lô + bảng tồn ở kho khác",
     "Chốt sẽ bật quản lý theo lô cho mã: Khoai môn H24 300g, Thỏi vàng Rồng 200g, Túi 250g" in html
     and "Tồn ở kho khác của mã bật lô" in html and "đưa về 0, ghi điều chỉnh kho" in html
     and "chuyển nguyên số vào lô tồn cũ (chưa rõ HSD)" in html, html[-1500:])
A.chot(P5)
d5 = F.bang("SX Kiem Ke")[P5]
ds5 = json.loads(d5["ds_se"])
buoc = [f"Item {x['name']} {x['has_batch_no']}" if x["dt"] == "Item" else F.bang("Stock Entry")[x["name"]]["purpose"]
        for x in ds5]
kiem("thứ tự: tạm tắt lô mã có lô lẫn tồn không lô → xuất / nhập bù tồn KHÔNG LÔ (cả kho khác) → bật lô từng mã → "
     "xuất thiếu → nhập vào lô", buoc == ["Item TP-SEN [1, 0]", "Material Issue", "Material Receipt", "Item TP-KM [0, 1]",
                                          "Item TP-RONG [0, 1]", "Item TP-SEN [0, 1]", "Item TP-TUI [0, 1]",
                                          "Material Issue", "Material Receipt"], buoc)
se5 = [F.bang("Stock Entry")[x["name"]] for x in ds5 if x["dt"] == "Stock Entry"]
dong = lambda e: sorted((r["item_code"], r.get("s_warehouse") or r.get("t_warehouse"), r.get("batch_no") or "",   # noqa: E731
                         r["qty"]) for r in e["items"])
kiem("phiếu tồn không lô: xuất hết phần dương (Rồng 50, sen 3, túi 8 ở Kho TP + 2 ở cửa hàng), nhập bù phần âm (khoai "
     "môn 30 ở Kho TP, Rồng 20 ở xưởng) — dòng KHÔNG lô, đúng kho",
     dong(se5[0]) == [("TP-RONG", KHO, "", 50), ("TP-SEN", KHO, "", 3), ("TP-TUI", "CH Le", "", 2), ("TP-TUI", KHO, "", 8)]
     and dong(se5[1]) == [("TP-KM", KHO, "", 30), ("TP-RONG", "Xuong", "", 20)], (dong(se5[0]), dong(se5[1])))
kiem("… bù âm ở xưởng theo giá vốn của kho đó", next(r for r in se5[1]["items"] if r["item_code"] == "TP-RONG")
     .get("basic_rate") == 11000, se5[1]["items"])
kiem("phiếu xuất thiếu: mã còn tồn ở kho công ty khác về 0 ở Kho TP bằng dòng không lô",
     dong(se5[2]) == [("TP-CTYB", KHO, "", 4)], dong(se5[2]))
kiem("phiếu nhập: số đếm vào lô theo HSD ở Kho TP; tồn cửa hàng nhập lại nguyên số vào lô TỒN CŨ tại cửa hàng",
     dong(se5[3]) == [("TP-KM", KHO, "KM-HSD180627", 12), ("TP-RONG", KHO, "RONG-HSD080627", 40),
                      ("TP-RONG", KHO, "RONG-HSD180627", 5), ("TP-RONG", KHO, "RONG-HSD180627", 10),
                      ("TP-SEN", KHO, "SEN-HSD080627", 3), ("TP-TUI", "CH Le", "TUI-TONCU", 2),
                      ("TP-TUI", KHO, "TUI-HSD080627", 8)], dong(se5[3]))
kiem("… cùng giá vốn: Rồng 12.000 (Kho TP), túi ở cửa hàng 9.000 (giá kho đó); mã chưa có giá vốn cho giá 0",
     all(r.get("basic_rate") == 12000 for r in se5[3]["items"] if r["item_code"] == "TP-RONG")
     and next(r for r in se5[3]["items"] if r["batch_no"] == "TUI-TONCU").get("basic_rate") == 9000
     and all(r.get("allow_zero_valuation_rate") == 1 for r in se5[3]["items"] if r["item_code"] == "TP-KM"), se5[3]["items"])
kiem("tồn sau chốt: tồn không lô về 0 ở MỌI kho của mã bật lô; Kho TP mỗi mã mỗi HSD một lô; cửa hàng giữ nguyên 2 hộp "
     "(trong lô tồn cũ)",
     SO[("TP-RONG", None)] == 0 and SO[("TP-KM", None)] == 0 and SO[("TP-TUI", None)] == 0 and SO[("TP-SEN", None)] == 0
     and SO[("TP-CTYB", None)] == 0 and SO[("TP-RONG", "RONG-HSD080627")] == 40 and SO[("TP-RONG", "RONG-HSD180627")] == 15
     and SO[("TP-KM", "KM-HSD180627")] == 12 and SO[("TP-SEN", "SEN-HSD080627")] == 33
     and SO[("TP-TUI", "TUI-HSD080627")] == 8 and SO_KHO["CH Le"] == {("TP-TUI", None): 0, ("TP-TUI", "TUI-TONCU"): 2}
     and SO_KHO["Xuong"] == {("TP-RONG", None): 0} and SO_KHO["Kho Cty B"] == {("TP-CTYB", None): 5},
     {k: v for k, v in SO_KHO.items() if k != "Kho BTP"})
it = F.bang("Item")
kiem("cờ quản lý lô: Rồng, khoai môn, túi BẬT; sen giữ bật; mã có tồn ở công ty khác vẫn tắt",
     (it["TP-RONG"]["has_batch_no"], it["TP-KM"]["has_batch_no"], it["TP-TUI"]["has_batch_no"],
      it["TP-SEN"]["has_batch_no"], it["TP-CTYB"]["has_batch_no"]) == (1, 1, 1, 1, 0))
b = F.bang("Batch")
kiem("lô mới: HSD đúng, NSX = HSD − hạn dùng, đánh dấu tồn cũ qua kiểm kê; lô tồn cũ của cửa hàng không HSD, có ghi "
     "nguồn, cũng đánh dấu (bán không cần BM.08.04)",
     str(b["RONG-HSD080627"]["expiry_date"]) == H1 and str(b["KM-HSD180627"]["manufacturing_date"]) == "2026-09-21"
     and b["RONG-HSD080627"]["custom_kiem_ke"] == P5 and not b["TUI-TONCU"].get("expiry_date")
     and b["TUI-TONCU"]["custom_kiem_ke"] == P5 and "Tồn KHÔNG LÔ chưa rõ HSD" in b["TUI-TONCU"]["description"]
     and "kho khác" in b["TUI-TONCU"]["description"],
     b["TUI-TONCU"])
lo5 = {(r["item"], r["batch"]): r["viec"] for r in d5["lo"]}
kiem("bảng kết quả lô: tồn không lô ghi chuyển sang lô + \"mã chuyển sang quản lý lô\"; lô HSD ghi nhận từ tồn không lô",
     "mã chuyển sang quản lý lô" in lo5[("TP-RONG", None)] and "chuyển 40 sang lô HSD 08/06/27" in lo5[("TP-RONG", None)]
     and "nhận 40 từ tồn không lô" in lo5[("TP-RONG", "RONG-HSD080627")]
     and "mã chuyển sang quản lý lô" not in lo5[("TP-SEN", None)], lo5)
html = " ".join(A.bien_ban(P5).split())
kiem("biên bản đã chốt: mã đã bật quản lý lô; bảng tồn ở kho khác ghi kho, số, việc (có tên lô tồn cũ)",
     "Đã bật quản lý theo lô cho mã: Khoai môn H24 300g, Thỏi vàng Rồng 200g, Túi 250g —" in html
     and "<td>Túi 250g</td><td>CH Le</td><td class=\"s\">2</td> <td>chuyển nguyên số vào lô tồn cũ TUI-TONCU (chưa rõ HSD)"
     in html and "<td>Xuong</td><td class=\"s\">-20</td> <td>tồn âm (chuyển ra mà chưa ghi nhập / sản xuất vào kho này) — đưa về "
     "0, ghi điều chỉnh kho</td>" in html, html[-1800:])
F.bang("Stock Ledger Entry")["r9"] = {"name": "r9", "item_code": "TP-RONG", "warehouse": KHO, "voucher_type": "Sales Invoice",
                                      "voucher_no": "SINV-0099", "actual_qty": -2, "creation": "2026-10-09 11:00:00",
                                      "modified": "2026-10-09 11:00:00", "is_cancelled": 0}
F.vai("System Manager", u="admin@x")
loi = thu(lambda: F.get_doc("SX Kiem Ke", P5).cancel()) or ""
kiem("huỷ phiếu mà sau chốt mã vừa bật lô đã có chứng từ kho (bán theo lô) → chặn, nói chứng từ",
     "Không huỷ được" in loi and "Thỏi vàng Rồng 200g" in loi and "SINV-0099" in loi
     and F.bang("SX Kiem Ke")[P5]["docstatus"] == 1 and it["TP-RONG"]["has_batch_no"] == 1, loi)
F.bang("Stock Ledger Entry").pop("r9")
for j, x in enumerate(se5):      # sổ cái của CHÍNH các phiếu kho kiểm kê này (ghi sau lúc chốt) — không tính là chứng từ khác
    F.bang("Stock Ledger Entry")[f"own{j}"] = {"name": f"own{j}", "item_code": "TP-RONG", "warehouse": KHO,
                                               "voucher_type": "Stock Entry", "voucher_no": x["name"], "actual_qty": 1,
                                               "creation": "2026-10-09 10:00:05", "modified": "2026-10-09 10:00:05",
                                               "is_cancelled": 0}
F.get_doc("SX Kiem Ke", P5).cancel()
for j in range(len(se5)):
    F.bang("Stock Ledger Entry").pop(f"own{j}")
kiem("huỷ được thì: chứng từ huỷ ngược, cờ lô trả đúng như cũ (Rồng, khoai môn, túi tắt; sen bật), tồn MỌI kho về như "
     "trước", (it["TP-RONG"]["has_batch_no"], it["TP-KM"]["has_batch_no"], it["TP-TUI"]["has_batch_no"],
               it["TP-SEN"]["has_batch_no"]) == (0, 0, 0, 1)
     and all(abs(SO_KHO[k].get(x, 0) - SO_TRUOC[k].get(x, 0)) < 1e-9
             for k in SO_TRUOC for x in set(SO_KHO[k]) | set(SO_TRUOC[k]))
     and [x[2] for x in SE_LOG if x[0] == "cancel"][-4:] == ["Material Receipt", "Material Issue", "Material Receipt",
                                                             "Material Issue"],
     ({k: {x: q for x, q in v.items() if abs(q - SO_TRUOC[k].get(x, 0)) > 1e-9} for k, v in SO_KHO.items()}, SE_LOG[-4:]))
SO.clear()
SO.update(SO_GOC)
CHO_AM["v"] = False
for i in ("TP-RONG", "TP-KM", "TP-TUI", "TP-CTYB"):
    F.bang("Item").pop(i)
for k in ("bk1", "bk2", "bk3", "bk4"):
    F.bang("Bin").pop(k)
for k in ("CH Le", "Xuong", "Kho Cty B"):
    F.bang("Warehouse").pop(k)
    SO_KHO.pop(k)
frappe.local.__dict__.pop("sx_nho", None)

print("\n-- bán thành phẩm: cân theo lô (D155) --")
BTP_ = "Bán thành phẩm"
CHO_AM["v"] = True
F.CAI_DAT_SX.update({"kho_btp": "Kho BTP", "kho_xuong": "Kho Xuong"})
for i, ten, nhom, lo_ in (("BOT-BANH-SEN", "Bột bánh sen", "BTP-Banh", 1), ("DUONG-HOAN", "Đường hoán", "BTP-Phu", 0),
                          ("DO-U", "Đỗ ủ", "BTP-Dau", 1)):
    F.bang("Item")[i] = {"name": i, "item_name": ten, "stock_uom": "Kg", "custom_sx_nhom": nhom, "has_batch_no": lo_,
                         "disabled": 0}
for b, i, nsx, th in (("R-011026", "BOT-NEN", "2026-10-01", 0), ("R-051026", "BOT-NEN", "2026-10-05", 0),
                      ("R-070926", "BOT-NEN", "2026-09-07", 1), ("R-280926", "BOT-NEN", "2026-09-28", 0),
                      ("BBS-081026", "BOT-BANH-SEN", "2026-10-08", 0), ("BBS-061026", "BOT-BANH-SEN", "2026-10-06", 0),
                      ("BBS-091026", "BOT-BANH-SEN", "2026-10-09", 0), ("R-011026-U", "DO-U", "2026-10-01", 0),
                      ("DH-OLD", "DUONG-HOAN", "2026-01-01", 0)):
    F.bang("Batch")[b] = {"name": b, "item": i, "manufacturing_date": nsx, "creation": f"{nsx} 08:00:00",
                          "custom_thu_hoi": th}
SOB.update({("BOT-NEN", "R-011026"): 40, ("BOT-NEN", "R-051026"): 25.5, ("BOT-NEN", "R-070926"): 3,
            ("BOT-NEN", None): 1.5, ("BOT-BANH-SEN", "BBS-081026"): 12.5, ("BOT-BANH-SEN", "BBS-061026"): -2,
            ("DUONG-HOAN", None): 30})
SOX.update({("DO-U", "R-011026-U"): 8})
F.bang("Bin")["b3"] = {"name": "b3", "item_code": "BOT-NEN", "warehouse": "Kho BTP", "valuation_rate": 30000}
F.bang("SX Ngay San Xuat")["NSX-1"] = {"name": "NSX-1", "ngay": "2026-10-08", "docstatus": 0, "chot_ghiso": 1,
                                       "chot_vaohop": 0}

F.vai("SX Thu Kho", u="kho@x")
tq = A.tong_quan()
kiem("thẻ: ba kho để chọn — Thành phẩm (Kho TP), Bán thành phẩm (Kho BTP), Kho xưởng; mặc định Kho TP",
     [(k["kho"], k["loai"]) for k in tq["cac_kho"]] == [("Kho TP", "Thành phẩm"), ("Kho BTP", BTP_),
                                                        ("Kho Xuong", BTP_)]
     and (tq["kho"], tq["loai"]) == ("Kho TP", "Thành phẩm"), tq["cac_kho"])
tq = A.tong_quan("Kho BTP", BTP_)
kiem("Kho BTP: mã xếp theo chuyền — bột nền → đường hoán → bột bánh (đỗ ủ nằm kho xưởng, không hiện)",
     [x["item"] for x in tq["hang"]] == ["BOT-NEN", "DUONG-HOAN", "BOT-BANH-SEN"], [x["item"] for x in tq["hang"]])
bn = hang(tq, "BOT-NEN")
kiem("bột nền: lô theo ngày (cũ trước), lô thu hồi đánh dấu; tồn không gắn lô 1,5 báo riêng; sổ 67",
     [(l["batch"], l["so"], l["thu_hoi"]) for l in bn["lo"]] == [("R-070926", 3, True), ("R-011026", 40, False),
                                                                 ("R-051026", 25.5, False)]
     and bn["le"] == 1.5 and bn["so_sach"] == 67 and bn["thu_hoi"] == 3 and bn["con_chua"] == 2
     and bn["nhom"] == "Bột nền" and not bn["khong_lo"] and not bn["da_dem"], bn)
kiem("đường hoán (mã không lô): một dòng lô None", hang(tq, "DUONG-HOAN")["khong_lo"]
     and [l["batch"] for l in hang(tq, "DUONG-HOAN")["lo"]] == [None], hang(tq, "DUONG-HOAN"))
kiem("cảnh báo: ngày sản xuất chưa chốt Vào hộp (bột chưa trừ sổ) — không chặn",
     any("chưa chốt Vào hộp (08/10)" in c for c in tq["canh_bao"]) and not any("Ghi sổ" in c for c in tq["canh_bao"]),
     tq["canh_bao"])
F.bang("SX Ngay San Xuat")["NSX-2"] = {"name": "NSX-2", "ngay": "2026-10-09", "docstatus": 0, "chot_ghiso": 0,
                                       "chot_vaohop": 0}
kiem("… chưa chốt Ghi sổ cũng báo", any("chưa chốt Ghi sổ (09/10)" in c for c in A.tong_quan("Kho BTP", BTP_)["canh_bao"]))
F.bang("SX Ngay San Xuat").pop("NSX-2")
F.bang("SX Ngay San Xuat")["NSX-3"] = {"name": "NSX-3", "ngay": "2026-10-12", "docstatus": 0, "chot_ghiso": 0,
                                       "chot_vaohop": 0}
kiem("… phiếu ngày lập trước cho ngày SAU hôm nay thì không nhắc",
     not any("12/10" in c for c in A.tong_quan("Kho BTP", BTP_)["canh_bao"]))
tx = A.tong_quan("Kho Xuong", BTP_)
kiem("kho xưởng: không cảnh báo chốt ngày (tầng 1 ghi sổ ngay); đỗ ủ hiện ở đó",
     not tx["canh_bao"] and [x["item"] for x in tx["hang"]] == ["DO-U"] and tx["hang"][0]["nhom"] == "Đỗ ủ / đỗ vỡ", tx)
kiem("kho không kiểm kê ở đây → chặn", "Không kiểm kê kho" in (thu(lambda: A.tong_quan("Kho NVL")) or ""))

PT_TP = A.bat_dau()["phieu"]["name"]
tq = A.bat_dau("Kho BTP", BTP_)
PB = tq["phieu"]["name"]
kiem("mở phiếu bán thành phẩm song song phiếu thành phẩm — mỗi kho một phiếu",
     PB != PT_TP and F.bang("SX Kiem Ke")[PB]["loai"] == BTP_ and A.tong_quan()["phieu"]["name"] == PT_TP
     and A.bat_dau("Kho BTP", BTP_)["phieu"]["name"] == PB and tq["loai"] == BTP_, (PB, PT_TP))
kiem("+ MÃ KHÁC: bán thành phẩm chưa có trên sổ kho này", [x["item"] for x in tq["danh_muc"]] == ["DO-U"], tq["danh_muc"])
kiem("+ LÔ KHÁC: lô của mã không có trên sổ kho này, mới nhất trước",
     [x["batch"] for x in A.lo_khac(PB, "BOT-NEN")] == ["R-280926"] and A.lo_khac(PB, "BOT-NEN")[0]["ngay"] == "2026-09-28"
     and [x["batch"] for x in A.lo_khac(PB, "BOT-BANH-SEN")] == ["BBS-091026"], A.lo_khac(PB, "BOT-NEN"))
kiem("… tìm theo mã lô", A.lo_khac(PB, "BOT-NEN", tim="2809") and not A.lo_khac(PB, "BOT-NEN", tim="xyz"))

tq = A.ghi_lo(PB, "BOT-NEN", "R-011026", 38.4)
bn = hang(tq, "BOT-NEN")
kiem("cân một lô: số kg lẻ ghi vào lô; lệch của mã chỉ tính lô đã cân (−1,6)",
     next(l for l in bn["lo"] if l["batch"] == "R-011026")["can"] == 38.4 and bn["lech"] == -1.6
     and bn["con_chua"] == 1 and bn["da_dem"] and bn["tong_dem"] == 38.4 and bn["so_sach_dem"] == 40, bn)
A.ghi_lo(PB, "BOT-NEN", "R-051026", 25.5)
tq = A.ghi_lo(PB, "BOT-NEN", "R-280926", 2)
kiem("cân lô sổ không có (+ LÔ KHÁC): thêm dòng sổ 0, kèm ngày lô",
     any(l["batch"] == "R-280926" and l["so"] == 0 and l["can"] == 2 and l["ngay"] == "2026-09-28"
         for l in hang(tq, "BOT-NEN")["lo"]), hang(tq, "BOT-NEN")["lo"])
kiem("… lô đã cân không còn trong + LÔ KHÁC", not A.lo_khac(PB, "BOT-NEN"))
for mo_ta_, can_co, f in (
        ("mã quản lý lô mà không chọn lô", "chọn lô", lambda: A.ghi_lo(PB, "BOT-NEN", None, 5)),
        ("lô của mã khác", "không phải lô của", lambda: A.ghi_lo(PB, "BOT-NEN", "BBS-081026", 1)),
        ("lô đang thu hồi", "THU HỒI", lambda: A.ghi_lo(PB, "BOT-NEN", "R-070926", 3)),
        ("thành phẩm", "không phải bán thành phẩm", lambda: A.ghi_lo(PB, "TP-SEN", "SEN-100926", 1)),
        ("mã không lô mà chọn lô", "không quản lý theo lô", lambda: A.ghi_lo(PB, "DUONG-HOAN", "DH-OLD", 1)),
        ("số âm", "Số cân không được âm", lambda: A.ghi_lo(PB, "BOT-NEN", "R-011026", -1)),
        ("ghi kiểu thành phẩm (HSD) vào phiếu bán thành phẩm", "cân theo lô",
         lambda: A.ghi(PB, "BOT-NEN", hsd=H1, so_dem=1)),
        ("cân lô vào phiếu thành phẩm", "đếm theo HSD", lambda: A.ghi_lo(PT_TP, "BOT-NEN", "R-011026", 1))):
    kiem(f"chặn: {mo_ta_}", can_co in (thu(f) or ""), thu(f))
tq = A.ghi_lo(PB, "DUONG-HOAN", None, 31.25)
kiem("mã không lô: cân cả mã", hang(tq, "DUONG-HOAN")["lo"][0]["can"] == 31.25 and hang(tq, "DUONG-HOAN")["lech"] == 1.25)
tq = A.het_hang(PB, "BOT-BANH-SEN")
kiem("KHÔNG CÒN: mọi lô trên sổ của mã ghi cân 0",
     sorted((l["batch"], l["can"]) for l in hang(tq, "BOT-BANH-SEN")["lo"]) == [("BBS-061026", 0), ("BBS-081026", 0)],
     hang(tq, "BOT-BANH-SEN")["lo"])
tq = A.ghi_lo(PB, "BOT-BANH-SEN", "BBS-081026", 12)
kiem("cân lại một lô = ghi đè số cũ (không thêm dòng)",
     sorted((l["batch"], l["can"]) for l in hang(tq, "BOT-BANH-SEN")["lo"]) == [("BBS-061026", 0), ("BBS-081026", 12)]
     and len([r for r in F.bang("SX Kiem Ke")[PB]["dong"] if r["item"] == "BOT-BANH-SEN"]) == 2)
tq = A.bo_lo(PB, "BOT-NEN", "R-280926")
kiem("BỎ SỐ CÂN một lô (cân nhầm lô): lô về chưa cân — lô ngoài sổ thì rời danh sách, về lại + LÔ KHÁC",
     not any(l["batch"] == "R-280926" for l in hang(tq, "BOT-NEN")["lo"]) and A.lo_khac(PB, "BOT-NEN"))
kiem("… bỏ lô chưa cân → báo", "chưa cân" in (thu(lambda: A.bo_lo(PB, "BOT-NEN", "R-280926")) or ""))
A.ghi_lo(PB, "BOT-NEN", "R-280926", 2)
tq = A.dem_lai(PB, "DUONG-HOAN")
kiem("CÂN LẠI cả mã: bỏ mọi số cân của mã", not hang(tq, "DUONG-HOAN")["da_dem"])
A.ghi_lo(PB, "DUONG-HOAN", None, 31.25)

xt = A.xem_truoc(PB)
ma = {x["item"]: x for x in xt["ma"]}
kiem("XEM TRƯỚC: không lỗi; bột nền 3 lô cân, sổ 65,5 → cân 65,9 (thiếu 1,6, thừa 2)",
     not xt["loi"] and xt["loai"] == BTP_ and ma["BOT-NEN"]["lo_can"] == 3 and ma["BOT-NEN"]["so_sach"] == 65.5
     and ma["BOT-NEN"]["dem"] == 65.9 and ma["BOT-NEN"]["thieu"] == 1.6 and ma["BOT-NEN"]["thua"] == 2, xt)
kiem("… bột bánh: bù lô âm 2, thiếu 0,5; đường hoán thừa 1,25; 2 chứng từ (1 xuất + 1 nhập), không chuyển lô",
     ma["BOT-BANH-SEN"]["bu_am"] == 2 and ma["BOT-BANH-SEN"]["thieu"] == 0.5 and ma["DUONG-HOAN"]["thua"] == 1.25
     and xt["tong"]["phieu_kho"] == 2 and xt["tong"]["chuyen"] == 0 and xt["tong"]["so_lo"] == 6, xt["tong"])
kiem("… cảnh báo chốt ngày đi theo xem trước", any("Vào hộp" in c for c in xt["canh_bao"]), xt["canh_bao"])
html = A.bien_ban(PB)
ok = ("BẢN NHÁP" in html and "Biên bản kiểm kê kho bán thành phẩm" in html and "R-011026" in html
      and "38,4" in html and "-1,6" in html and "HSD" not in html)
kiem("in bản nháp bán thành phẩm: BẢN NHÁP, từng lô sổ / cân / lệch (sổ 40 → cân 38,4: −1,6)", ok,
     "" if ok else html[-2500:])

dd = F.bang("SX Kiem Ke")[PB]
for r in dd["dong"]:
    r["dem_luc"] = "2026-10-09 09:00:00"
F.bang("Stock Ledger Entry")["b1"] = {"name": "b1", "item_code": "BOT-NEN", "warehouse": "Kho BTP",
                                      "voucher_type": "Stock Entry", "voucher_no": "SE-ME-1", "actual_qty": -5,
                                      "serial_and_batch_bundle": "SBB-1", "creation": "2026-10-09 09:30:00",
                                      "modified": "2026-10-09 09:30:00", "is_cancelled": 0}
F.bang("Serial and Batch Entry")["e1"] = {"name": "e1", "parent": "SBB-1", "batch_no": "R-051026", "qty": -5}
F.bang("Stock Ledger Entry")["b2"] = {"name": "b2", "item_code": "BOT-BANH-SEN", "warehouse": "Kho BTP",
                                      "voucher_type": "Stock Entry", "voucher_no": "SE-ME-2", "actual_qty": 8,
                                      "batch_no": "BBS-091026", "creation": "2026-10-09 09:40:00",
                                      "modified": "2026-10-09 09:40:00", "is_cancelled": 0}
F.bang("Stock Ledger Entry")["b3"] = {"name": "b3", "item_code": "BOT-NEN", "warehouse": "Kho Xuong",
                                      "voucher_type": "Stock Entry", "voucher_no": "SE-XUONG", "actual_qty": 4,
                                      "batch_no": "R-011026", "creation": "2026-10-09 09:45:00",
                                      "modified": "2026-10-09 09:45:00", "is_cancelled": 0}
SOB[("BOT-NEN", "R-051026")] -= 5
SOB[("BOT-BANH-SEN", "BBS-091026")] = 8
loi = " ".join(A.xem_truoc(PB)["loi"])
kiem("chứng từ sau lúc cân xét theo LÔ: lô đã cân bị trừ (qua bundle) → chặn, nói cân lại lô đó",
     "Bột nền lô R-051026" in loi and "SE-ME-1 (-5)" in loi and "Cân lại lô này" in loi, loi)
kiem("… mẻ mới ra lô CHƯA cân, chứng từ ở kho khác → không chặn",
     "SE-ME-2" not in loi and "SE-XUONG" not in loi and "R-011026" not in loi, loi)
F.vai("SX Thu Kho", u="kho2@x")
kiem("chốt lúc đó → không được", "Cân lại" in (thu(lambda: A.chot(PB)) or ""))
A.ghi_lo(PB, "BOT-NEN", "R-051026", 20.5)
kiem("cân lại lô đó → hết chặn", not A.xem_truoc(PB)["loi"], A.xem_truoc(PB)["loi"])

kq = A.chot(PB)
d = F.bang("SX Kiem Ke")[PB]
kiem("CHỐT (thủ kho khác người lập cũng chốt được): Đã chốt; sổ 101 → cân 104,15 (+3,15), 3 mã, 2 chứng từ",
     d["docstatus"] == 1 and d["trang_thai"] == "Đã chốt" and d["nguoi_chot"] == "kho2@x" and d["so_ma"] == 3
     and (d["tong_so_sach"], d["tong_dem"], d["tong_lech"]) == (101, 104.15, 3.15) and kq["so_phieu_kho"] == 2, kq)
se = [F.bang("Stock Entry")[x["name"]] for x in json.loads(d["ds_se"])]
kiem("chứng từ: Material Issue (thiếu) → Material Receipt (thừa + bù âm), không Repack",
     [x["purpose"] for x in se] == ["Material Issue", "Material Receipt"], [x["purpose"] for x in se])
kiem("xuất thiếu ĐÚNG LÔ: R-011026 1,6; BBS-081026 0,5",
     sorted((r["item_code"], r["batch_no"], r["qty"]) for r in se[0]["items"])
     == [("BOT-BANH-SEN", "BBS-081026", 0.5), ("BOT-NEN", "R-011026", 1.6)], se[0]["items"])
kiem("nhập thừa đúng lô (lô ngoài sổ, bù lô âm); mã không lô thì dòng không lô; theo giá vốn đang chạy",
     sorted((r["item_code"], r.get("batch_no") or "", r["qty"]) for r in se[1]["items"])
     == [("BOT-BANH-SEN", "BBS-061026", 2), ("BOT-NEN", "R-280926", 2), ("DUONG-HOAN", "", 1.25)]
     and next(r for r in se[1]["items"] if r["item_code"] == "BOT-NEN")["basic_rate"] == 30000, se[1]["items"])
kiem("TỒN SAU CHỐT = SỐ CÂN từng lô; lô chưa cân, lô thu hồi, tồn không lô của mã có lô giữ nguyên",
     SOB[("BOT-NEN", "R-011026")] == 38.4 and SOB[("BOT-NEN", "R-051026")] == 20.5 and SOB[("BOT-NEN", "R-280926")] == 2
     and SOB[("BOT-BANH-SEN", "BBS-081026")] == 12 and SOB[("BOT-BANH-SEN", "BBS-061026")] == 0
     and SOB[("DUONG-HOAN", None)] == 31.25 and SOB[("BOT-NEN", "R-070926")] == 3 and SOB[("BOT-NEN", None)] == 1.5
     and SOB[("BOT-BANH-SEN", "BBS-091026")] == 8, SOB)
lo_bang = {(r["item"], r["batch"]): r for r in d["lo"]}
kiem("bảng kết quả từng lô: sổ trước → sau + việc",
     (lo_bang[("BOT-NEN", "R-011026")]["so_truoc"], lo_bang[("BOT-NEN", "R-011026")]["so_sau"]) == (40, 38.4)
     and "xuất thiếu 1.6" in lo_bang[("BOT-NEN", "R-011026")]["viec"]
     and "nhập thừa 2" in lo_bang[("BOT-NEN", "R-280926")]["viec"]
     and "bù lô âm 2" in lo_bang[("BOT-BANH-SEN", "BBS-061026")]["viec"]
     and "đang thu hồi" in lo_bang[("BOT-NEN", "R-070926")]["viec"]
     and lo_bang[("DUONG-HOAN", None)]["so_sau"] == 31.25
     and lo_bang[("BOT-NEN", "R-051026")]["viec"] == "khớp sổ — giữ nguyên",
     {k: (v["so_truoc"], v["so_sau"], v["viec"]) for k, v in lo_bang.items()})
kiem("không đánh dấu lô 'tồn cũ' (việc của lô thành phẩm theo HSD)",
     not any(v.get("custom_kiem_ke") == PB for v in F.bang("Batch").values()))
html = A.bien_ban(PB)
ok = ("Biên bản kiểm kê kho bán thành phẩm" in html and "R-280926" in html and "Cân thật" in html
      and "38,4" in html and "31,25" in html and se[0]["name"] in html and "Kế toán" in html
      and "HSD" not in html and "BẢN NHÁP" not in html and "(không lô)" in html
      and "-1,6" in html and "+3,15" in html and "Cộng 3 mã, 6 lô" in html)
kiem("biên bản bán thành phẩm: tiêu đề, lô, cân thật, sổ lúc chốt → lệch từng lô, số kiểu VN, chứng từ, chỗ ký; "
     "không cột HSD", ok,
     "" if ok else html[-2500:])
gd = A.tong_quan("Kho BTP", BTP_)["gan_day"]
kiem("thẻ Kho BTP: phiếu vừa chốt vào gần đây; thẻ Kho TP không lẫn",
     gd and gd[0]["name"] == PB and all(g["name"] != PB for g in A.tong_quan()["gan_day"]), gd)

print("\n-- bán thành phẩm: chốt chặn khi sửa trên Desk, huỷ, kho xưởng --")
F.vai("SX Thu Kho", u="kho@x")
PB2 = A.bat_dau("Kho BTP", BTP_)["phieu"]["name"]
for mo_ta_, dong, can_co in (
        ("số cân âm", {"item": "BOT-NEN", "batch": "R-011026", "so_dem": -1}, "âm"),
        ("lô của mã khác", {"item": "BOT-NEN", "batch": "BBS-081026", "so_dem": 1}, "không phải lô của")):
    dd = F.get_doc("SX Kiem Ke", PB2)
    dd.append("dong", dong)
    kiem(f"lưu phiếu (Desk): {mo_ta_} → chặn", can_co in (thu(dd.save) or ""), thu(dd.save))
dd = F.get_doc("SX Kiem Ke", PB2)
dd.append("dong", {"item": "BOT-NEN", "batch": "R-011026", "so_dem": 1})
dd.append("dong", {"item": "BOT-NEN", "batch": "R-011026", "so_dem": 2})
kiem("lưu phiếu có hai dòng cùng (mã, lô) → chặn, bảo gộp", "gộp" in (thu(dd.save) or ""))
dd = F.get_doc("SX Kiem Ke", PB2)
dd.append("dong", {"item": "BOT-NEN", "batch": "R-011026", "hsd": H1, "so_dem": 38.4})
dd.append("dong", {"item": "BOT-NEN", "batch": None, "so_dem": 1.5})
dd.append("dong", {"item": "DUONG-HOAN", "batch": "DH-OLD", "so_dem": 30})
dd.append("dong", {"item": "BOT-NEN", "batch": "R-070926", "so_dem": 3})
dd.save()
kiem("lưu được; HSD trên dòng bán thành phẩm bị bỏ",
     next(r for r in F.bang("SX Kiem Ke")[PB2]["dong"] if r["batch"] == "R-011026")["hsd"] is None)
loi = " ".join(A.xem_truoc(PB2)["loi"])
kiem("chốt chặn: dòng không lô của mã có lô / dòng có lô của mã không lô / lô thu hồi",
     "không ghi lô" in loi and "có ghi lô" in loi and "THU HỒI" in loi and "lô R-070926" in loi, loi)
tq = A.het_hang(PB2, "BOT-NEN")
kiem("KHÔNG CÒN: chỉ lô có trên sổ, bỏ lô thu hồi và tồn không gắn lô; xoá dòng cũ của mã",
     sorted((l["batch"], l["can"]) for l in hang(tq, "BOT-NEN")["lo"] if l["can"] is not None)
     == [("R-011026", 0), ("R-051026", 0), ("R-280926", 0)]
     and sorted(r["batch"] or "" for r in F.bang("SX Kiem Ke")[PB2]["dong"] if r["item"] == "BOT-NEN")
     == ["R-011026", "R-051026", "R-280926"], F.bang("SX Kiem Ke")[PB2]["dong"])
kiem("… mã không có lô nào trên sổ kho này → báo", "không còn lô nào" in (thu(lambda: A.het_hang(PB2, "DO-U")) or ""))
A.huy(PB2)
A.huy(PT_TP)
kiem("bỏ hai phiếu nháp", PB2 not in F.bang("SX Kiem Ke") and PT_TP not in F.bang("SX Kiem Ke"))

F.vai("System Manager", u="admin@x")
F.get_doc("SX Kiem Ke", PB).cancel()
kiem("huỷ phiếu bán thành phẩm đã chốt: chứng từ huỷ ngược, tồn từng lô về như trước",
     SOB[("BOT-NEN", "R-011026")] == 40 and SOB[("BOT-NEN", "R-280926")] == 0 and SOB[("DUONG-HOAN", None)] == 30
     and SOB[("BOT-BANH-SEN", "BBS-061026")] == -2 and SOB[("BOT-BANH-SEN", "BBS-081026")] == 12.5
     and F.bang("SX Kiem Ke")[PB]["trang_thai"] == "Đã huỷ"
     and [x[2] for x in SE_LOG if x[0] == "cancel"][-2:] == ["Material Receipt", "Material Issue"], SOB)

F.vai("SX Quan Ly", u="ql@x")
PX = A.bat_dau("Kho Xuong", BTP_)["phieu"]["name"]
A.ghi_lo(PX, "DO-U", "R-011026-U", 7.2)
A.chot(PX)
kiem("kho xưởng: đỗ ủ cân 7,2 → tồn lô 7,2 (xuất thiếu 0,8 ở chính kho xưởng)",
     SOX[("DO-U", "R-011026-U")] == 7.2 and F.bang("SX Kiem Ke")[PX]["kho"] == "Kho Xuong", SOX)
print("\n-- bán thành phẩm: tạo lô mới ngay lúc cân (D156) --")
F.vai("SX Thu Kho", u="kho@x")
F.bang("Item")["BOT-BANH-SEN"]["custom_batch_prefix"] = "BBS"
PB4 = A.bat_dau("Kho BTP", BTP_)["phieu"]["name"]
n_lo = len(F.bang("Batch"))
# Như ERPNext thật: lô vừa tạo, chưa có chứng từ kho nào là lô "chưa dùng" (utils.lo_chua_dung) — Frappe giả không có
# db.sql nên lo_chua_dung luôn trả "đã dùng"; giả lập lại cho đúng (sổ cái giả không ghi SLE theo lô).
_lcd = U.lo_chua_dung
U.lo_chua_dung = lambda ma, item: (F.bang("Batch").get(ma) or {}).get("item") == item and not any(
    x.get("batch_no") == ma for x in F.bang("Stock Ledger Entry").values())
tq = A.ghi_lo_moi(PB4, "BOT-BANH-SEN", " bbs-071026 ", "2026-10-07", 4.25)
b_ = F.bang("Batch").get("BBS-071026") or {}
kiem("mã lô gõ theo thẻ (chữ thường, thừa khoảng trắng) → tạo lô BBS-071026 của đúng mã, NSX = ngày làm, ghi chú phiếu",
     b_.get("item") == "BOT-BANH-SEN" and str(b_.get("manufacturing_date")) == "2026-10-07"
     and PB4 in (b_.get("description") or "") and tq["lo_moi"] == {"batch": "BBS-071026", "tao": True, "tu_dat": False},
     (b_, tq.get("lo_moi")))
l_ = next((l for l in hang(tq, "BOT-BANH-SEN")["lo"] if l["batch"] == "BBS-071026"), {})
kiem("… lô mới hiện ngay trong danh sách của mã: sổ 0, cân 4,25, ngày lô 07/10",
     (l_.get("so"), l_.get("can"), l_.get("ngay")) == (0, 4.25, "2026-10-07"), l_)
A.ghi_lo_moi(PB4, "BOT-BANH-SEN", "", "2026-10-08", 3)
tq = A.ghi_lo_moi(PB4, "BOT-BANH-SEN", None, "2026-10-08", 2)
kiem("bỏ trống mã → app đặt BBS-KK081026; lô thứ hai cùng ngày trong phiếu → BBS-KK081026-2 (không đè số lô trước)",
     tq["lo_moi"] == {"batch": "BBS-KK081026-2", "tao": True, "tu_dat": True}
     and {l["batch"]: l["can"] for l in hang(tq, "BOT-BANH-SEN")["lo"]}.get("BBS-KK081026") == 3, tq["lo_moi"])
F.bang("Batch")["BBS-KK051026"] = {"name": "BBS-KK051026", "item": "BOT-BANH-SEN", "manufacturing_date": "2026-10-05",
                                   "creation": "2026-10-05 08:00:00"}
tq = A.ghi_lo_moi(PB4, "BOT-BANH-SEN", "", "2026-10-05", 1.5)
kiem("lô -KK của mã này còn chưa dùng (phiếu trước bỏ ngang) → dùng lại đúng mã đã chép ra thẻ, không đẻ -2",
     tq["lo_moi"] == {"batch": "BBS-KK051026", "tao": False, "tu_dat": True}, tq["lo_moi"])
tq = A.ghi_lo_moi(PB4, "BOT-NEN", "R-280926", "2026-09-28", 2)
kiem("mã gõ trùng lô đã có của chính mã → ghi số cân vào lô đó, không tạo lô",
     tq["lo_moi"] == {"batch": "R-280926", "tao": False, "tu_dat": False}
     and any(l["batch"] == "R-280926" and l["can"] == 2 for l in hang(tq, "BOT-NEN")["lo"]), tq["lo_moi"])
kiem("… tạo lô mới chỉ đẻ đúng 3 lô (BBS-071026, BBS-KK081026, BBS-KK081026-2)", len(F.bang("Batch")) == n_lo + 4,
     len(F.bang("Batch")) - n_lo)
F.bang("Batch")["R-KHOA"] = {"name": "R-KHOA", "item": "BOT-NEN", "disabled": 1, "creation": "2026-09-01 08:00:00"}
PT3 = A.bat_dau()["phieu"]["name"]
for mo_ta_, can_co, f in (
        ("trùng lô của mã khác", "đã là lô của Bột nền", lambda: A.ghi_lo_moi(PB4, "BOT-BANH-SEN", "R-011026", "2026-10-01", 1)),
        ("lô đang thu hồi", "THU HỒI", lambda: A.ghi_lo_moi(PB4, "BOT-NEN", "R-070926", "2026-09-07", 1)),
        ("lô bị khoá trên Desk", "khoá", lambda: A.ghi_lo_moi(PB4, "BOT-NEN", "r-khoa", "2026-09-01", 1)),
        ("mã lô có ký tự lạ", "chỉ gồm chữ, số", lambda: A.ghi_lo_moi(PB4, "BOT-NEN", "R-07?10", "2026-10-07", 1)),
        ("số cân 0", "phải có số cân", lambda: A.ghi_lo_moi(PB4, "BOT-NEN", "R-MOI", "2026-10-07", 0)),
        ("ngày làm sau hôm nay", "sau hôm nay", lambda: A.ghi_lo_moi(PB4, "BOT-NEN", "R-MOI", "2026-10-10", 1)),
        ("mã không quản lý lô", "không tạo lô", lambda: A.ghi_lo_moi(PB4, "DUONG-HOAN", "", "2026-10-07", 1)),
        ("thành phẩm", "không phải bán thành phẩm", lambda: A.ghi_lo_moi(PB4, "TP-SEN", "", "2026-10-07", 1)),
        ("phiếu kiểm kê thành phẩm", "đếm theo HSD", lambda: A.ghi_lo_moi(PT3, "BOT-NEN", "", "2026-10-07", 1))):
    kiem(f"tạo lô mới — chặn: {mo_ta_}", can_co in (thu(f) or ""), thu(f))
kiem("… các lần bị chặn không đẻ lô nào", len(F.bang("Batch")) == n_lo + 5
     and not ({"R-MOI", "R-07?10"} & set(F.bang("Batch"))) and not any("-KK" in k and not k.startswith("BBS-")
                                                                          for k in F.bang("Batch")),
     (len(F.bang("Batch")) - n_lo, sorted(F.bang("Batch"))))
A.huy(PT3)
U.lo_chua_dung = _lcd
xt = A.xem_truoc(PB4)
ma = {x["item"]: x for x in xt["ma"]}
kiem("xem trước: lô mới là phần THỪA (sổ 0) của mã — 4,25 + 3 + 2 + 1,5 = 10,75",
     not xt["loi"] and ma["BOT-BANH-SEN"]["thua"] == 10.75 and ma["BOT-BANH-SEN"]["lo_can"] == 4, (xt["loi"], ma))
A.chot(PB4)
kiem("chốt: lô mới nhập đúng lô (Material Receipt) — tồn từng lô mới = số cân",
     SOB[("BOT-BANH-SEN", "BBS-071026")] == 4.25 and SOB[("BOT-BANH-SEN", "BBS-KK081026")] == 3
     and SOB[("BOT-BANH-SEN", "BBS-KK081026-2")] == 2 and SOB[("BOT-BANH-SEN", "BBS-KK051026")] == 1.5
     and SOB[("BOT-NEN", "R-280926")] == 2, {k: v for k, v in SOB.items() if k[0] in ("BOT-BANH-SEN", "BOT-NEN")})

F.CAI_DAT_SX.update({"kho_btp": "Kho TP", "kho_xuong": None})
kiem("chưa có Kho xưởng riêng → không có ô Kho xưởng; Kho BTP trùng Kho TP vẫn tách hai loại",
     [(k["kho"], k["loai"]) for k in A.cac_kho()] == [("Kho TP", "Thành phẩm"), ("Kho TP", BTP_)], A.cac_kho())
F.vai("SX Thu Kho", u="kho@x")
PT2 = A.bat_dau()["phieu"]["name"]
tq = A.tong_quan("Kho TP", BTP_)
kiem("cùng một kho: thẻ bán thành phẩm không lấy phiếu / lịch sử của thành phẩm",
     tq["loai"] == BTP_ and tq["phieu"] is None and tq["gan_day"] == [] and A.tong_quan()["gan_day"], tq["gan_day"])
PB3 = A.bat_dau("Kho TP", BTP_)["phieu"]["name"]
kiem("… mở phiếu bán thành phẩm riêng, thẻ thành phẩm vẫn là phiếu thành phẩm",
     PB3 != PT2 and A.tong_quan()["phieu"]["name"] == PT2 and A.tong_quan("Kho TP", BTP_)["phieu"]["name"] == PB3)
A.huy(PB3)
A.huy(PT2)
F.CAI_DAT_SX.update({"kho_btp": "Kho BTP", "kho_xuong": "Kho Xuong"})
CHO_AM["v"] = False

print("\n-- D193: dọn tồn âm thành phẩm ở Kho Xưởng sản xuất --")
TA = F.nap("sx.api.tonam", "sx/api/tonam.py")
TA._so_lo = C._so_lo
F.vai("SX Quan Ly", u="ql@x")
F.CAI_DAT_SX["kho_xuong"] = None
kiem("chưa đặt Kho Xưởng sản xuất → báo, không lấy kho thay thế",
     "Chưa đặt Kho Xưởng sản xuất" in (TA.ds_am()["loi"] or "") and TA.ds_am()["dong"] == [])
F.CAI_DAT_SX["kho_xuong"] = KHO
kiem("Kho Xưởng đặt trùng Kho TP → báo (Kho TP do kiểm kê lo)", "trùng Kho TP" in (TA.ds_am()["loi"] or ""))
F.CAI_DAT_SX["kho_xuong"] = "Kho Xuong"
F.bang("Warehouse")["Kho Xuong"] = {"name": "Kho Xuong", "company": "CTY-B"}
kiem("Kho Xưởng thuộc công ty khác → báo", "công ty CTY-B" in (TA.ds_am()["loi"] or ""))
F.bang("Warehouse")["Kho Xuong"] = {"name": "Kho Xuong", "company": "RVHG"}
SOX_GOC, SO_GOC = dict(SOX), dict(SO)
SOX.update({("TP-KL", None): -20,                 # mã không lô: chuyển ra mà không ghi sản xuất vào
            ("TP-SEN", None): -7,                 # mã có lô mà âm không lô (dữ liệu cũ) → tạm tắt lô lúc ghi
            ("TP-SEN", "SEN-HSD080627"): -3,      # âm theo lô → bù đúng lô
            ("TP-DO", "DO-HSD010926"): -2,        # âm ở lô ĐÃ HẾT HẠN → bù được (tạm bỏ HSD)
            ("TP-MOI", None): 5,                  # dương → giữ nguyên
            ("BOT-NEN", "R-011026-X"): -4})       # không phải thành phẩm → không đụng
SO_KHO["CH Le"] = {("TP-KL", None): -9}           # kho khác (cửa hàng) → không đụng
SO[("TP-KL", None)] = -3                          # Kho TP → không đụng (kiểm kê lo)
F.bang("Item")["TP-MOI"]["has_batch_no"] = 0
CHO_AM["v"] = True
frappe.local.__dict__.pop("sx_nho", None)
F.vai("SX Thu Kho", u="kho@x")
x = TA.ds_am()
kiem("xem: đúng các dòng âm của THÀNH PHẨM ở Kho Xưởng (mã × lô), xếp theo tên; không dòng dương, không mã ngoài thành "
     "phẩm, không kho khác",
     x["kho"] == "Kho Xuong" and not x["loi"]
     and [(r["item"], r["batch"], r["so"]) for r in x["dong"]] == [("TP-KL", None, -20), ("TP-SEN", None, -7),
                                                                    ("TP-SEN", "SEN-HSD080627", -3), ("TP-DO", "DO-HSD010926", -2)]
     and x["tong"] == {"so_dong": 4, "so_ma": 3, "so_luong": 32, "gia_tri": 230000}, x)
kiem("… kèm HSD của lô, giá vốn, giá trị từng dòng; thủ kho xem được nhưng không dọn được",
     x["dong"][3]["hsd"] == "2026-09-01" and x["dong"][1]["gia"] == 20000 and x["dong"][1]["gia_tri"] == 140000
     and x["duoc_don"] is False, x["dong"])
kiem("thủ kho bấm dọn → chặn (chỉ quản lý — bút toán điều chỉnh kho)", "Chỉ quản lý" in (thu(TA.don_am) or ""))
F.vai("SX Quan Ly", u="ql@x")
n_truoc = len(SE_LOG)
kq = TA.don_am()
moi_se = [F.bang("Stock Entry")[n] for n in kq["phieu"]]
dong_ = lambda e: sorted((r["item_code"], r.get("batch_no") or "", r["qty"], r["t_warehouse"]) for r in e["items"])   # noqa: E731
kiem("dọn: phiếu nhập KHÔNG lô (lúc mã có lô tạm tắt lô) rồi phiếu nhập có lô — đúng kho xưởng, đúng số",
     [e["purpose"] for e in moi_se] == ["Material Receipt", "Material Receipt"]
     and dong_(moi_se[0]) == [("TP-KL", "", 20, "Kho Xuong"), ("TP-SEN", "", 7, "Kho Xuong")]
     and dong_(moi_se[1]) == [("TP-DO", "DO-HSD010926", 2, "Kho Xuong"), ("TP-SEN", "SEN-HSD080627", 3, "Kho Xuong")]
     and len(SE_LOG) == n_truoc + 2, [dong_(e) for e in moi_se])
kiem("… theo giá vốn (mã chưa có giá vốn: giá 0); ghi chú phiếu nói rõ là điều chỉnh tồn âm, có mã lần dọn",
     next(r for r in moi_se[0]["items"] if r["item_code"] == "TP-SEN")["basic_rate"] == 20000
     and next(r for r in moi_se[0]["items"] if r["item_code"] == "TP-KL").get("allow_zero_valuation_rate") == 1
     and all(e["remarks"].startswith("Dọn tồn âm thành phẩm [DA-091026-100000] ở Kho Xuong") for e in moi_se), moi_se[0])
kiem("sau dọn: dòng âm ở Kho Xưởng về 0; dương, mã ngoài thành phẩm, kho khác, Kho TP giữ nguyên; cờ lô trả lại; lô hết "
     "hạn giữ HSD", SOX[("TP-KL", None)] == 0 and SOX[("TP-SEN", None)] == 0 and SOX[("TP-SEN", "SEN-HSD080627")] == 0
     and SOX[("TP-DO", "DO-HSD010926")] == 0 and SOX[("TP-MOI", None)] == 5 and SOX[("BOT-NEN", "R-011026-X")] == -4
     and SO_KHO["CH Le"] == {("TP-KL", None): -9} and SO[("TP-KL", None)] == -3
     and F.bang("Item")["TP-SEN"]["has_batch_no"] == 1
     and str(F.bang("Batch")["DO-HSD010926"]["expiry_date"]) == "2026-09-01", SOX)
kiem("trả kết quả: số dòng, giá trị, các phiếu", kq["so_dong"] == 4 and kq["gia_tri"] == 230000 and len(kq["phieu"]) == 2
     and kq["kho"] == "Kho Xuong", kq)
x = TA.ds_am()
kiem("xem lại: hết dòng âm; lần dọn vừa rồi trong danh sách đã dọn (in lại được)",
     x["dong"] == [] and len(x["lan_truoc"]) == 1 and x["lan_truoc"][0]["lan"] == "DA-091026-100000"
     and sorted(x["lan_truoc"][0]["phieu"]) == sorted(kq["phieu"]), x["lan_truoc"])
kiem("dọn lần nữa → báo không còn gì", "Không còn tồn âm" in (thu(TA.don_am) or ""))
html = " ".join(TA.bien_ban(json.dumps(kq["phieu"])).split())
kiem("danh sách in cho kế toán: tên mã, lô, số, giá vốn, giá trị, tổng, chứng từ, chỗ ký",
     "Danh sách điều chỉnh tồn âm thành phẩm" in html and "Kho Xuong" in html and "Bánh đậu xanh sen" in html
     and "SEN-HSD080627" in html and "(không lô)" in html and "+20" in html and "230.000" in html
     and "140.000" in html and "Kế toán" in html and all(n in html for n in kq["phieu"]), html[-1500:])
kiem("in phiếu không phải phiếu dọn tồn âm → chặn",
     "không phải phiếu dọn tồn âm" in (thu(lambda: TA.bien_ban(json.dumps([se[0]["name"]]))) or ""))
for n in kq["phieu"]:
    F.get_doc("Stock Entry", n).cancel()
SOX.clear()
SOX.update(SOX_GOC)
SO.clear()
SO.update(SO_GOC)
SO_KHO.pop("CH Le")
F.bang("Warehouse").pop("Kho Xuong")
F.bang("Item")["TP-MOI"]["has_batch_no"] = 1
CHO_AM["v"] = False

print("\n-- D195: thời điểm chốt sổ (sổ sách tính tới lúc đó, chứng từ ghi lùi; mã bật lô hai nhịp) --")
pls = K.phan_lo_sau
kiem("chia tồn sau thời điểm chốt (hàm thuần): ra lấy HSD sớm nhất trước, vào theo HSD của nó",
     pls({"2027-01-10": 60, "2027-03-01": 40}, [{"q": -30, "ngay": "2026-10-10"},
                                                {"q": 50, "hsd": "2027-06-01", "ngay": "2026-10-10"},
                                                {"q": -40, "ngay": "2026-10-11"}])
     == ({"2027-03-01": 30.0, "2027-06-01": 50.0}, 0.0))
kiem("… HSD đã hết ở ngày chứng từ lấy sau cùng (sau cả hàng chưa rõ HSD); ra quá số đang có → thiếu",
     pls({"2026-10-01": 5, "2027-03-01": 40}, [{"q": -10, "ngay": "2026-10-10"}, {"q": 7, "ngay": "2026-10-11"}])
     == ({"2026-10-01": 5.0, "2027-03-01": 30.0, None: 7.0}, 0.0)
     and pls({"2026-10-01": 5, "2027-03-01": 40}, [{"q": -10, "ngay": "2026-10-10"}, {"q": 7, "ngay": "2026-10-11"},
                                                   {"q": -50, "ngay": "2026-10-11"}]) == ({}, 8.0))

SLE = F.bang("Stock Ledger Entry")
SLE_GOC, SO_GOC6 = dict(SLE), dict(SO)
SLE.clear()
SO.clear()
CHO_AM["v"] = False
F.bang("Item")["TP-XA"] = {"name": "TP-XA", "item_name": "Bánh xá xíu", "stock_uom": "Hộp", "custom_sx_nhom": "TP",
                           "disabled": 0, "has_batch_no": 0, "shelf_life_in_days": 270, "custom_batch_prefix": "XA"}
F.bang("Bin")["bx1"] = {"name": "bx1", "item_code": "TP-XA", "warehouse": KHO, "actual_qty": 50, "valuation_rate": 8000}
frappe.local.__dict__.pop("sx_nho", None)
# Sổ HIỆN TẠI (10:00). Lúc 08:30 / 09:45: sen lô cũ 100 + lô HSD 30; xá xíu 46 (chưa có lô). Sau đó:
#   09:00 nhập 5 bột đậu (chưa ai đếm), 09:30 bán 30 sen từ lô cũ, 09:50 bán 8 xá xíu, 09:55 nhập 12 xá xíu (phiếu
#   nhập thành phẩm, HSD 05/07/27).
SO.update({("TP-SEN", "SEN-100926"): 70, ("TP-SEN", "SEN-HSD080627"): 30, ("TP-XA", None): 50, ("TP-DO", "DO-150926"): 5})


def sle(n, item, q, luc, vt="Sales Invoice", vn=None, b=None):
    SLE[n] = {"name": n, "item_code": item, "warehouse": KHO, "batch_no": b, "actual_qty": q, "voucher_type": vt,
              "voucher_no": vn or n.upper(), "posting_datetime": luc, "creation": luc, "modified": luc, "is_cancelled": 0}


sle("d9", "TP-DO", 5, "2026-10-09 09:00:00", "Stock Entry", "SE-D9", "DO-150926")
sle("t1", "TP-SEN", -30, "2026-10-09 09:30:00", vn="SINV-T1", b="SEN-100926")
sle("x1", "TP-XA", -8, "2026-10-09 09:50:00", vn="SINV-X1")
sle("x2", "TP-XA", 12, "2026-10-09 09:55:00", "Stock Entry", "SE-NX")
F.bang("SX Phieu Nhap TP")["PNX"] = {"name": "PNX", "docstatus": 1, "ds_se": json.dumps(
    [{"dt": "Work Order", "name": "WO-X"}, {"dt": "Stock Entry", "name": "SE-NX"}]),
    "dong": [{"item": "TP-XA", "so_dem": 12, "hsd": "2027-07-05"}]}


def so_lo_gia(kho, items, den=None):
    """Sổ giả tính TỚI `den`: tồn hiện tại trừ các dòng sổ cái ghi sau đó."""
    so = {k: q for k, q in SO_KHO.get(kho, {}).items() if k[0] in items}
    for r in SLE.values():
        if den and not r["is_cancelled"] and r["warehouse"] == kho and r["item_code"] in items \
                and fu.get_datetime(r["posting_datetime"]) > fu.get_datetime(den):
            k = (r["item_code"], r.get("batch_no"))
            so[k] = so.get(k, 0) - r["actual_qty"]
    return [F.Doc(item=i, b=b, q=q) for (i, b), q in so.items()]


def sle_khoang_gia(khos, items, tu=None, den=None):
    ra = [r for r in SLE.values() if not r["is_cancelled"] and r["warehouse"] in khos and r["item_code"] in items
          and (not tu or fu.get_datetime(r["posting_datetime"]) > fu.get_datetime(tu))
          and (not den or fu.get_datetime(r["posting_datetime"]) <= fu.get_datetime(den))]
    return [F.Doc(kho=r["warehouse"], item=r["item_code"], b=r.get("batch_no") or None, q=r["actual_qty"],
                  luc=r["posting_datetime"], vt=r["voucher_type"], vn=r["voucher_no"])
            for r in sorted(ra, key=lambda r: (r["posting_datetime"], r["name"]))]


SO_LO_CU, SLE_KHOANG_CU = C._so_lo, C._sle_khoang
C._so_lo, C._sle_khoang = so_lo_gia, sle_khoang_gia
F.vai("SX Thu Kho", u="kho@x")
P6 = A.bat_dau()["phieu"]["name"]
d6 = F.bang("SX Kiem Ke")[P6]
d6["bat_dau_luc"] = "2026-10-09 08:00:00"
A.ghi(P6, "TP-SEN", hsd=H1, so_dem=40)
A.ghi(P6, "TP-SEN", hsd=H2, so_dem=90)
A.ghi(P6, "TP-XA", hsd=H1, so_dem=20)
A.ghi(P6, "TP-XA", hsd="2027-03-01", so_dem=24)
d6 = F.bang("SX Kiem Ke")[P6]
for j, r in enumerate(d6["dong"]):
    r["dem_luc"] = f"2026-10-09 08:2{j}:00"
dem_goc = [(r["item"], str(r["hsd"]), r["so_dem"]) for r in d6["dong"]]
tq = A.tong_quan()
kiem("chưa đặt thời điểm chốt: sổ sách là số HIỆN TẠI (sen 100), giờ hiện tại cho ô chọn, phiếu chưa có thời điểm",
     hang(tq, "TP-SEN")["so_sach"] == 100 and tq["bay_gio"] == "2026-10-09T10:00" and tq["phieu"]["thoi_diem"] == "",
     (hang(tq, "TP-SEN")["so_sach"], tq["bay_gio"], tq["phieu"]))
kiem("thời điểm ở tương lai → chặn", "tương lai" in (thu(lambda: A.dat_thoi_diem(P6, "2026-10-09 11:00")) or ""))
R.CARD_ROLES["kiemke"].append("SX QC")
F.vai("SX QC", u="qc@x")
kiem("không phải thủ kho / quản lý → không đặt được",
     "thủ kho / quản lý" in (thu(lambda: A.dat_thoi_diem(P6, "2026-10-09 08:30")) or ""))
R.CARD_ROLES["kiemke"].remove("SX QC")
F.vai("SX Thu Kho", u="kho@x")
F.CAI_DAT_SX["stock_frozen_upto"] = "2026-10-09"
kiem("sổ kho đã khoá tới ngày đó (Stock Settings) → chặn",
     "Sổ kho đã khoá tới 09/10/2026" in (thu(lambda: A.dat_thoi_diem(P6, "2026-10-09 08:30")) or ""))
F.CAI_DAT_SX.pop("stock_frozen_upto")
F.CAI_DAT_SX["stock_frozen_upto_days"] = 1
kiem("ghi lùi quá số ngày cho phép (Stock Settings) → chặn",
     "quá 1 ngày" in (thu(lambda: A.dat_thoi_diem(P6, "2026-10-08 17:00")) or ""))
F.CAI_DAT_SX.pop("stock_frozen_upto_days")
for g in ("erpnext", "erpnext.stock", "erpnext.stock.doctype", "erpnext.stock.doctype.stock_closing_entry"):
    sys.modules[g] = types.ModuleType(g)
sce = types.ModuleType("erpnext.stock.doctype.stock_closing_entry.stock_closing_entry")
sce.get_closing_entry_for_closed_period = lambda cty: F.Doc(name="SCE-0001", to_date="2026-10-09")
sys.modules[sce.__name__] = sce
kiem("kỳ kho đã khoá sổ (Stock Closing Entry) → chặn, nói phiếu khoá",
     "Stock Closing Entry SCE-0001" in (thu(lambda: A.dat_thoi_diem(P6, "2026-10-09 08:30")) or ""))
for g in ("erpnext", "erpnext.stock", "erpnext.stock.doctype", "erpnext.stock.doctype.stock_closing_entry", sce.__name__):
    sys.modules.pop(g)
A.dat_thoi_diem(P6, "2026-10-08 17:00")
kiem("đặt thời điểm chốt hôm trước → ngày kiểm kê là ngày đó", str(F.bang("SX Kiem Ke")[P6]["ngay"]) == "2026-10-08",
     F.bang("SX Kiem Ke")[P6]["ngay"])
tq = A.dat_thoi_diem(P6, "2026-10-09 08:30:42")
d6 = F.bang("SX Kiem Ke")[P6]
kiem("ĐẶT thời điểm chốt 08:30 (bỏ giây): lưu vào phiếu, ngày kiểm kê theo đó; sổ sách tính lại TỚI lúc đó (sen 130)",
     str(d6["thoi_diem"])[:19] == "2026-10-09 08:30:00" and str(d6["ngay"]) == "2026-10-09"
     and tq["phieu"]["thoi_diem"] == "2026-10-09 08:30" and hang(tq, "TP-SEN")["so_sach"] == 130
     and hang(tq, "TP-XA")["so_sach"] == 46, (d6["thoi_diem"], tq["phieu"], hang(tq, "TP-SEN")["so_sach"]))
kiem("… số đã đếm giữ nguyên",
     [(r["item"], str(r["hsd"]), r["so_dem"]) for r in d6["dong"]] == dem_goc and all(
         str(r["dem_luc"]).startswith("2026-10-09 08:2") for r in d6["dong"]), d6["dong"])
xt = A.xem_truoc(P6)
loi = " ".join(xt["loi"])
kiem("chứng từ SAU thời điểm chốt rút từ lô mà chốt giảm (bán 30 từ lô cũ — chốt chuyển hết lô đó sang lô HSD) → chặn, "
     "nói lô + chứng từ; mã bật lô bán / nhập sau đó không chặn (hai nhịp)",
     "Sau thời điểm chốt sổ 09/10/2026 08:30" in loi and "Bánh đậu xanh sen lô SEN-100926: Sales Invoice SINV-T1" in loi
     and "xá xíu" not in loi and "Bột đậu" not in loi, xt["loi"])
tq = A.dat_thoi_diem(P6, "2026-10-09 09:45")
xt = A.xem_truoc(P6)
loi = " ".join(xt["loi"])
kiem("đổi sang 09:45 (sau phiếu bán): số đếm lúc 08:20 không phải tồn lúc 09:45 — có phiếu bán ở giữa → đếm lại; mã chưa "
     "đếm có phiếu nhập sau lúc bắt đầu kiểm kê → đếm",
     "Bánh đậu xanh sen: có chứng từ kho giữa lúc đếm (09/10 08:20–08:21) và thời điểm chốt sổ (09/10 09:45) — Sales "
     "Invoice SINV-T1 (-30)" in loi and "Bột đậu 500g chưa đếm (chốt sẽ về 0) mà có chứng từ kho giữa lúc bắt đầu kiểm kê "
     "(09/10 08:00) và thời điểm chốt sổ (09/10 09:45) — Stock Entry SE-D9 (+5)" in loi and "xá xíu" not in loi, xt["loi"])
A.dem_lai(P6, "TP-SEN")
A.ghi(P6, "TP-SEN", hsd=H1, so_dem=30)
A.ghi(P6, "TP-SEN", hsd=H2, so_dem=70)
A.ghi(P6, "TP-DO", hsd="2027-03-15", so_dem=5)
F.CAI_DAT_SX["role_allowed_to_create_edit_back_dated_transactions"] = "Stock Manager"
loi = " ".join(A.xem_truoc(P6)["loi"])
kiem("Stock Settings chỉ cho vai riêng ghi lùi trước chứng từ đã có (xá xíu có phiếu sau 09:45, chốt ghi lùi phần thiếu) "
     "→ chặn, nói vai", "chỉ người có vai Stock Manager" in loi, loi)
F.vai("SX Thu Kho", "Stock Manager", u="kho@x")
kiem("… người có vai đó thì được", not A.xem_truoc(P6)["loi"], A.xem_truoc(P6)["loi"])
F.CAI_DAT_SX.pop("role_allowed_to_create_edit_back_dated_transactions")
F.vai("SX Thu Kho", u="kho@x")
A.dat_thoi_diem(P6, "2026-10-08 17:00")
A.dat_thoi_diem(P6)
loi = " ".join(A.xem_truoc(P6)["loi"])
kiem("BỎ thời điểm chốt (chốt theo lúc bấm): ngày kiểm kê về ngày bắt đầu; về kiểm như cũ — xá xíu có chứng từ sau lúc "
     "đếm → đếm lại", F.bang("SX Kiem Ke")[P6].get("thoi_diem") is None
     and str(F.bang("SX Kiem Ke")[P6]["ngay"]) == "2026-10-09" and "sau lúc đếm" in loi and "SINV-X1" in loi, loi)
A.dat_thoi_diem(P6, "2026-10-09 09:45")
xt = A.xem_truoc(P6)
cb = " ".join(xt["canh_bao"])
kiem("đếm lại xong, 09:45 → chốt được; báo mã bật lô hai nhịp: tồn hiện tại chia HSD (bán 8 trừ HSD sớm nhất 01/03/27, "
     "nhập 12 theo HSD của phiếu nhập thành phẩm 05/07/27)",
     not xt["loi"] and xt["tong"]["thoi_diem"] == "2026-10-09 09:45" and xt["tong"]["bat_lui"] == 1
     and "chốt lùi" in cb and "Bánh xá xíu → HSD 01/03/27 16, HSD 08/06/27 20, HSD 05/07/27 12" in cb,
     (xt["loi"], xt["tong"], cb))
kiem("số chứng từ kho: lượt ghi lùi 3 (Repack sen, Repack bột đậu, xuất thiếu) + lượt lúc bấm 2 (xuất tồn không lô, "
     "nhập vào lô)", xt["tong"]["phieu_kho"] == 5, xt["tong"])
html = " ".join(A.bien_ban(P6).split())
kiem("biên bản nháp: Chốt sổ tại 09/10/2026 09:45; số sổ sách tính tới thời điểm chốt sổ",
     "Chốt sổ tại 09/10/2026 09:45" in html and "tính tới thời điểm chốt sổ" in html, html[:900])
SO_TRUOC6 = {k: dict(v) for k, v in SO_KHO.items()}
n_se = len(F.bang("Stock Entry"))
A.chot(P6)
d6 = F.bang("SX Kiem Ke")[P6]
ds6 = json.loads(d6["ds_se"])
se6 = {x["name"]: F.bang("Stock Entry")[x["name"]] for x in ds6 if x["dt"] == "Stock Entry"}
buoc = [f"Item {x['name']} {x['has_batch_no']}" if x["dt"] == "Item"
        else (se6[x["name"]]["purpose"] + (" lùi" if se6[x["name"]].get("set_posting_time") else "")) for x in ds6]
kiem("CHỐT: lượt 1 ghi lùi (Repack, xuất thiếu — gồm phần thiếu KHÔNG lô của xá xíu) → lượt 2 lúc bấm (xuất tồn không lô "
     "hiện tại, bật lô, nhập vào lô)",
     buoc == ["Repack lùi", "Repack lùi", "Material Issue lùi", "Material Issue", "Item TP-XA [0, 1]",
              "Material Receipt"] and len(F.bang("Stock Entry")) == n_se + 5, buoc)
lui = [e for e in se6.values() if e.get("set_posting_time")]
kiem("… phiếu ghi lùi: ngày giờ ghi sổ = thời điểm chốt sổ",
     all(str(e["posting_date"]) == "2026-10-09" and e["posting_time"] == "09:45:00" for e in lui) and len(lui) == 3,
     [(e["posting_date"], e["posting_time"]) for e in lui])
xu = next(e for e in lui if e["purpose"] == "Material Issue")
kiem("… phần thiếu của xá xíu (đếm 44 − sổ 46 = 2) ghi lùi, KHÔNG lô (lúc đó mã chưa có lô)",
     sorted((r["item_code"], r.get("batch_no") or "", r["qty"]) for r in xu["items"])
     == [("TP-XA", "", 2.0)], xu["items"])
nh = [e for e in se6.values() if e["purpose"] == "Material Receipt"][0]
kiem("lượt 2: tồn không lô HIỆN TẠI 48 vào lô theo HSD — 01/03/27: 16, 08/06/27: 20, 05/07/27: 12 (cùng giá vốn)",
     sorted((r["batch_no"], r["qty"]) for r in nh["items"]) == [("XA-HSD010327", 16.0), ("XA-HSD050727", 12.0),
                                                                ("XA-HSD080627", 20.0)]
     and all(r.get("basic_rate") == 8000 for r in nh["items"]), nh["items"])
kiem("tồn sau chốt: sen mỗi HSD một lô (30 + 70), bột đậu vào lô HSD; xá xíu không lô về 0, tổng 48 = 50 − 2 thiếu",
     SO[("TP-SEN", "SEN-100926")] == 0 and SO[("TP-SEN", "SEN-HSD080627")] == 30 and SO[("TP-SEN", "SEN-HSD180627")] == 70
     and SO[("TP-DO", "DO-HSD150327")] == 5 and SO[("TP-XA", None)] == 0
     and sum(q for (i, b), q in SO.items() if i == "TP-XA") == 48 and F.bang("Item")["TP-XA"]["has_batch_no"] == 1, SO)
bx = F.bang("Batch")
kiem("lô của hàng nhập sau thời điểm chốt (làm từ ngày áp dụng BM.08.04, chưa duyệt) không đánh dấu tồn cũ; lô số đếm thì có",
     not bx["XA-HSD050727"].get("custom_kiem_ke") and bx["XA-HSD080627"]["custom_kiem_ke"] == P6
     and str(bx["XA-HSD050727"]["expiry_date"]) == "2027-07-05", (bx["XA-HSD050727"], bx["XA-HSD080627"]))
lo6 = {(r["item"], r["batch"]): r["viec"] for r in d6["lo"]}
kiem("bảng lô: dòng tồn không lô của xá xíu ghi chuyển vào lô lúc bấm chốt", "lúc bấm chốt" in lo6[("TP-XA", None)], lo6)
html = " ".join(A.bien_ban(P6).split())
kiem("biên bản đã chốt: Chốt sổ tại 09/10/2026 09:45 · Bấm chốt 09/10/2026 10:00",
     "Chốt sổ tại 09/10/2026 09:45" in html and "Bấm chốt 09/10/2026 10:00" in html, html[:900])
F.vai("System Manager", u="admin@x")
F.get_doc("SX Kiem Ke", P6).cancel()
kiem("huỷ phiếu chốt lùi: huỷ ngược cả hai lượt, mã về không lô, tồn về như trước",
     F.bang("Item")["TP-XA"]["has_batch_no"] == 0
     and all(abs(SO_KHO[k].get(x, 0) - SO_TRUOC6[k].get(x, 0)) < 1e-9
             for k in SO_TRUOC6 for x in set(SO_KHO[k]) | set(SO_TRUOC6[k])),
     {k: {x: q for x, q in v.items() if abs(q - SO_TRUOC6[k].get(x, 0)) > 1e-9} for k, v in SO_KHO.items()})
F.vai("SX Thu Kho", u="kho@x")
P7 = A.bat_dau()["phieu"]["name"]
F.bang("SX Kiem Ke")[P7]["bat_dau_luc"] = "2026-10-09 08:00:00"
A.ghi(P7, "TP-XA", hsd=H1, so_dem=5)
A.ghi(P7, "TP-SEN", hsd=H1, so_dem=30)
A.ghi(P7, "TP-SEN", hsd=H2, so_dem=70)
A.ghi(P7, "TP-DO", hsd="2027-03-15", so_dem=5)
for r in F.bang("SX Kiem Ke")[P7]["dong"]:
    r["dem_luc"] = {("TP-XA", H1): "2026-10-09 08:20:00", ("TP-SEN", H1): "2026-10-09 09:40:00",
                    ("TP-DO", "2027-03-15"): "2026-10-09 09:45:00"}.get((r["item"], str(r["hsd"])), r["dem_luc"])
SO[("TP-SEN", "SEN-HSD080627")] += 2
sle("t2", "TP-SEN", 2, "2026-10-09 09:50:00", "Stock Entry", "SE-T2", "SEN-HSD080627")
A.dat_thoi_diem(P7, "2026-10-09 09:45")
loi = " ".join(A.xem_truoc(P7)["loi"])
kiem("mã bật lô: sau thời điểm chốt bán nhiều hơn số đếm (đếm 5, bán 8) → chặn, nói thiếu bao nhiêu + chứng từ",
     "Bánh xá xíu: sau thời điểm chốt bán / xuất nhiều hơn số đếm 3 — Sales Invoice SINV-X1" in loi, loi)
kiem("mã đếm trước VÀ sau thời điểm chốt: chứng từ giữa thời điểm chốt và lần đếm sau cũng tính → đếm lại",
     "Bánh đậu xanh sen: có chứng từ kho giữa lúc đếm (09/10 09:40–10:00) và thời điểm chốt sổ (09/10 09:45) — Stock "
     "Entry SE-T2 (+2)" in loi, loi)
sle("r1", "TP-DO", 0, "2026-10-09 09:58:00", "Stock Reconciliation", "MAT-RECO-9", "DO-150926")
sle("r2", "TP-XA", 0, "2026-10-09 09:52:00", "Stock Reconciliation", "MAT-RECO-X")
loi = " ".join(A.xem_truoc(P7)["loi"])
kiem("Stock Reconciliation SAU thời điểm chốt ở mã chốt ghi lùi (đặt lại tồn — đè phần chốt) → chặn, nói phiếu; mã bật "
     "lô cũng vậy", "Bột đậu 500g lô DO-150926: Stock Reconciliation MAT-RECO-9" in loi
     and "Bánh xá xíu: Stock Reconciliation MAT-RECO-X (đặt lại tồn)" in loi, loi)
SO[("TP-SEN", None)] = 3                 # mã có lô mà còn tồn KHÔNG lô (dữ liệu cũ): chốt đưa phần đó về 0
sle("n1", "TP-SEN", 1, "2026-10-09 09:56:00", "Stock Entry", "SE-N1")
loi = " ".join(A.xem_truoc(P7)["loi"])
kiem("mã có lô còn tồn không lô: sau thời điểm chốt có chứng từ KHÔNG lô → chặn",
     "Bánh đậu xanh sen (không lô): Stock Entry SE-N1" in loi, loi)
for k in ("t2", "r1", "r2", "n1"):
    SLE.pop(k)
SO[("TP-SEN", "SEN-HSD080627")] -= 2
SO.pop(("TP-SEN", None))
A.huy(P7)

# Hàng nhập sau thời điểm chốt KHÔNG qua phiếu nhập thành phẩm (chuyển về, trả lại…) → chưa rõ HSD → lô tồn cũ.
SO_P8, SLE_P8 = dict(SO), dict(SLE)
SO.clear()
SO[("TP-XA", None)] = 53
SLE.clear()
sle("x1", "TP-XA", -8, "2026-10-09 09:50:00", vn="SINV-X1")
sle("x2", "TP-XA", 12, "2026-10-09 09:55:00", "Stock Entry", "SE-NX")
sle("x3", "TP-XA", 3, "2026-10-09 09:57:00", "Stock Entry", "SE-TRA")
P8 = A.bat_dau()["phieu"]["name"]
F.bang("SX Kiem Ke")[P8]["bat_dau_luc"] = "2026-10-09 09:30:00"
A.ghi(P8, "TP-XA", hsd=H1, so_dem=46)
F.bang("SX Kiem Ke")[P8]["dong"][0]["dem_luc"] = "2026-10-09 09:40:00"
A.dat_thoi_diem(P8, "2026-10-09 09:45")
xt = A.xem_truoc(P8)
kiem("xem trước: đếm 46 = sổ lúc 09:45 (không chênh lệch); tồn hiện tại 53 chia: HSD 08/06/27 38, HSD 05/07/27 12 (phiếu "
     "nhập thành phẩm), lô tồn cũ 3 (nhập không rõ HSD)", not xt["loi"] and xt["tong"]["phieu_kho"] == 2
     and "Bánh xá xíu → HSD 08/06/27 38, HSD 05/07/27 12, lô tồn cũ 3" in " ".join(xt["canh_bao"]), (xt["loi"], xt["tong"]))
A.chot(P8)
ds8 = json.loads(F.bang("SX Kiem Ke")[P8]["ds_se"])
kiem("chốt: không có phiếu ghi lùi (khớp sổ); lúc bấm: tồn không lô → lô theo HSD + lô tồn cũ ngay tại Kho TP",
     SO[("TP-XA", None)] == 0 and SO[("TP-XA", "XA-HSD080627")] == 38 and SO[("TP-XA", "XA-HSD050727")] == 12
     and SO[("TP-XA", "XA-TONCU")] == 3 and not any(F.bang("Stock Entry")[x["name"]].get("set_posting_time")
                                                    for x in ds8 if x["dt"] == "Stock Entry")
     and "hàng nhập sau thời điểm chốt sổ" in F.bang("Batch")["XA-TONCU"]["description"], (SO, ds8))
kiem("… biên bản không kể Kho TP là \"kho khác\" (phần chưa rõ HSD ở ngay kho kiểm kê)",
     not any(x.get("kho_khac") for x in ds8 if x["dt"] == "Item"), ds8)
F.vai("System Manager", u="admin@x")
F.get_doc("SX Kiem Ke", P8).cancel()
F.vai("SX Thu Kho", u="kho@x")
kiem("… huỷ: tồn về như trước, mã về không lô", SO[("TP-XA", None)] == 53 and F.bang("Item")["TP-XA"]["has_batch_no"] == 0
     and all(abs(q) < 1e-9 for (i, b), q in SO.items() if b), SO)
SO.clear()
SO.update(SO_P8)
SLE.clear()
SLE.update(SLE_P8)
C._so_lo, C._sle_khoang = SO_LO_CU, SLE_KHOANG_CU
SLE.clear()
SLE.update(SLE_GOC)
SO.clear()
SO.update(SO_GOC6)
F.bang("Item").pop("TP-XA")
F.bang("Bin").pop("bx1")
F.bang("SX Phieu Nhap TP").pop("PNX")
frappe.local.__dict__.pop("sx_nho", None)

print("\n-- D196: huỷ chốt, mở lại phiếu đang đếm (giữ số đã đếm) --")
SLE_GOC9, SO_GOC9 = dict(SLE), dict(SO)
SLE.clear()
SO.clear()
CHO_AM["v"] = False
C._so_lo, C._sle_khoang = so_lo_gia, sle_khoang_gia
F.bang("Item")["TP-XB"] = {"name": "TP-XB", "item_name": "Bánh xốp", "stock_uom": "Hộp", "custom_sx_nhom": "TP",
                           "disabled": 0, "has_batch_no": 0, "shelf_life_in_days": 270, "custom_batch_prefix": "XB"}
F.bang("Bin")["bxb"] = {"name": "bxb", "item_code": "TP-XB", "warehouse": KHO, "actual_qty": 10, "valuation_rate": 5000}
frappe.local.__dict__.pop("sx_nho", None)
SO.update({("TP-SEN", "SEN-100926"): 50, ("TP-XB", None): 10})
SO_TRUOC9 = {k: dict(v) for k, v in SO_KHO.items()}
F.vai("SX Thu Kho", u="kho@x")
P9 = A.bat_dau()["phieu"]["name"]
F.bang("SX Kiem Ke")[P9].update({"creation": "2026-10-09 22:00:00", "bat_dau_luc": "2026-10-09 08:00:00"})
A.ghi(P9, "TP-SEN", hsd=H1, so_dem=30)          # mới đếm một phần — HSD 18/06/27 chưa đếm
A.ghi(P9, "TP-XB", hsd=H1, so_dem=10)
A.dat_thoi_diem(P9, "2026-10-09 09:58")
dong9 = [(r["item"], str(r["hsd"]), r["so_dem"], r["nguoi_dem"], str(r["dem_luc"]))
         for r in F.bang("SX Kiem Ke")[P9]["dong"]]
A.chot(P9)                                       # chốt nhầm khi chưa đếm xong
kiem("(chốt nhầm: phiếu đã chốt, mã không lô đã bật lô, lô cũ của sen đã về 0)",
     F.bang("SX Kiem Ke")[P9]["docstatus"] == 1 and F.bang("Item")["TP-XB"]["has_batch_no"] == 1
     and SO[("TP-SEN", "SEN-100926")] == 0)
tq = A.tong_quan()
kiem("danh sách đã chốt có giờ chốt (hộp huỷ chốt ghi)", tq["gan_day"][0]["name"] == P9
     and tq["gan_day"][0]["chot_luc"] == "2026-10-09 10:00", tq["gan_day"][0])
kiem("thiếu lý do → chặn", "lý do" in (thu(lambda: A.huy_chot(P9, "  ")) or ""))
R.CARD_ROLES["kiemke"].append("SX QC")
F.vai("SX QC", u="qc@x")
kiem("không phải thủ kho / quản lý → chặn", "thủ kho / quản lý" in (thu(lambda: A.huy_chot(P9, "chốt nhầm")) or ""))
R.CARD_ROLES["kiemke"].remove("SX QC")
F.vai("SX Thu Kho", u="kho@x")
P10 = A.bat_dau()["phieu"]["name"]
kiem("phiếu chưa chốt → không huỷ chốt được",
     "không ở trạng thái đã chốt" in (thu(lambda: A.huy_chot(P10, "chốt nhầm")) or ""))
kiem("kho đang có phiếu đang đếm → chặn, nói phiếu (mỗi kho một phiếu đang đếm)",
     f"đang có phiếu kiểm kê {P10} đang đếm" in (thu(lambda: A.huy_chot(P9, "chốt nhầm")) or ""))
A.huy(P10)
F.bang("SX Kiem Ke")["SKK-SAU"] = {"name": "SKK-SAU", "doctype": "SX Kiem Ke", "docstatus": 1, "kho": KHO,
                                   "loai": "Thành phẩm", "creation": "2026-10-09 23:00:00"}
kiem("đã chốt phiếu khác SAU phiếu này → chặn (lần chốt sau tính trên số của lần trước)",
     "đã chốt phiếu SKK-SAU" in (thu(lambda: A.huy_chot(P9, "chốt nhầm")) or ""))
F.bang("SX Kiem Ke").pop("SKK-SAU")
SLE["hx1"] = {"name": "hx1", "item_code": "TP-XB", "warehouse": KHO, "batch_no": "XB-HSD080627", "actual_qty": -1,
              "voucher_type": "Sales Invoice", "voucher_no": "SINV-XB", "posting_datetime": "2026-10-09 11:00:00",
              "creation": "2026-10-09 11:00:00", "modified": "2026-10-09 11:00:00", "is_cancelled": 0}
loi = thu(lambda: A.huy_chot(P9, "chốt nhầm")) or ""
kiem("sau chốt mã vừa bật lô đã bán theo lô → không huỷ được, nói chứng từ; phiếu vẫn đã chốt, không mở phiếu mới",
     "Không huỷ được" in loi and "SINV-XB" in loi and F.bang("SX Kiem Ke")[P9]["docstatus"] == 1
     and not A._nhap(KHO), loi)
SLE.pop("hx1")
kq = A.huy_chot(P9, "chốt nhầm khi chưa đếm xong")
d9 = F.bang("SX Kiem Ke")[P9]
moi = kq["huy_chot"]["moi"]
dm = F.bang("SX Kiem Ke")[moi]
kiem("HUỶ CHỐT: phiếu cũ Đã huỷ, ghi lý do; chứng từ kho của lần chốt huỷ hết; tồn về như trước lúc chốt; mã đã bật lô "
     "về không lô", kq["huy_chot"]["cu"] == P9 and d9["docstatus"] == 2 and d9["trang_thai"] == "Đã huỷ"
     and "chốt nhầm khi chưa đếm xong" in d9["ghi_chu"] and F.bang("Item")["TP-XB"]["has_batch_no"] == 0
     and all(F.bang("Stock Entry")[x["name"]]["docstatus"] == 2 for x in json.loads(d9["ds_se"]) if x["dt"] == "Stock Entry")
     and all(abs(SO_KHO[k].get(x, 0) - SO_TRUOC9[k].get(x, 0)) < 1e-9
             for k in SO_TRUOC9 for x in set(SO_KHO[k]) | set(SO_TRUOC9[k])),
     {k: {x: q for x, q in v.items() if abs(q - SO_TRUOC9[k].get(x, 0)) > 1e-9} for k, v in SO_KHO.items()})
kiem("… mở lại phiếu đang đếm: đúng các dòng đã đếm (số, người đếm, lúc đếm), lúc bắt đầu, thời điểm chốt sổ; ghi nguồn; "
     "thẻ hiện phiếu đó", kq["phieu"]["name"] == moi and dm["docstatus"] == 0 and dm["trang_thai"] == "Đang đếm"
     and [(r["item"], str(r["hsd"]), r["so_dem"], r["nguoi_dem"], str(r["dem_luc"])) for r in dm["dong"]] == dong9
     and str(dm["bat_dau_luc"])[:16] == "2026-10-09 08:00" and str(dm["thoi_diem"])[:16] == "2026-10-09 09:58"
     and f"Mở lại từ phiếu đã huỷ chốt {P9}: chốt nhầm khi chưa đếm xong" in dm["ghi_chu"]
     and not dm.get("chot_luc") and not dm.get("ds_se") and dm["nguoi_lap"] == "kho@x", (kq["phieu"], dm))
kiem("… danh sách đã chốt: phiếu cũ hiện Đã huỷ", A.tong_quan()["gan_day"][0]["trang_thai"] == "Đã huỷ")
A.ghi(moi, "TP-SEN", hsd=H2, so_dem=20)
A.chot(moi)
kiem("đếm tiếp phần còn lại rồi chốt lại → tồn đúng số đếm đủ",
     SO[("TP-SEN", "SEN-HSD080627")] == 30 and SO[("TP-SEN", "SEN-HSD180627")] == 20 and SO[("TP-SEN", "SEN-100926")] == 0
     and SO[("TP-XB", "XB-HSD080627")] == 10 and SO[("TP-XB", None)] == 0
     and F.bang("SX Kiem Ke")[moi]["docstatus"] == 1, SO)
F.vai("System Manager", u="admin@x")
F.get_doc("SX Kiem Ke", moi).cancel()
cu = json.loads(json.dumps(F.bang("SX Kiem Ke")[moi], default=str))
for k in ("name", "creation", "modified"):
    cu.pop(k, None)
cu.update({"docstatus": 0, "amended_from": moi,
           "dong": [{k: v for k, v in r.items() if k not in ("name", "parent", "idx")} for r in cu["dong"]]})
am = F.get_doc(cu).insert()
da = F.bang("SX Kiem Ke")[am.name]
kiem("Amend trên Desk (phiếu đã huỷ): bản sửa đổi là phiếu đang đếm sạch — không mang giờ chốt, người chốt, chứng từ, "
     "bảng lô, tổng của lần chốt cũ; giữ các dòng đếm",
     da["trang_thai"] == "Đang đếm" and not da.get("chot_luc") and not da.get("nguoi_chot") and not da.get("ds_se")
     and not da.get("lo") and da.get("so_ma") == 0 and da.get("tong_dem") == 0 and len(da["dong"]) == 3, da)
F.bang("SX Kiem Ke").pop(am.name)
F.vai("SX Thu Kho", u="kho@x")
C._so_lo, C._sle_khoang = SO_LO_CU, SLE_KHOANG_CU
SLE.clear()
SLE.update(SLE_GOC9)
SO.clear()
SO.update(SO_GOC9)
F.bang("Item").pop("TP-XB")
F.bang("Bin").pop("bxb")
frappe.local.__dict__.pop("sx_nho", None)

print("\n-- D198: chứng từ lập trước lúc mã bật lô (đóng ca POS, sửa hoá đơn cũ); dọn tồn không lô --")
L = F.nap("sx.api.lo_cu", "sx/api/lo_cu.py")
BH = F.nap("sx.api.banhang", "sx/api/banhang.py")
H = F.nap("sx.hooks", "sx/hooks.py")
KKB = F.bang("SX Kiem Ke")
cu_ = next(n for n, d in KKB.items() if '"TP-TUI"' in (d.get("ds_se") or ""))
KKB[cu_]["docstatus"] = 1
frappe.local.__dict__.pop("sx_moc_bat_lo", None)
m = L.moc_bat_lo()
kiem("lúc bật lô đọc từ nhật ký phiếu kiểm kê ĐÃ CHỐT (đúng dạng chốt ghi): mã đổi cờ 0 → 1, lúc bấm chốt, kho đã đếm, lô "
     "tồn cũ (D191); mã vốn có lô chỉ tạm tắt lúc chốt (1 → 0 → 1) không tính",
     set(m) == {"TP-KM", "TP-RONG", "TP-TUI"} and m["TP-TUI"]["lo_cu"] == "TUI-TONCU" and m["TP-KM"]["lo_cu"] is None
     and m["TP-RONG"]["kho"] == KHO and m["TP-TUI"]["phieu"] == cu_
     and str(m["TP-TUI"]["luc"]) == "2026-10-09 10:00:00", m)
KKB[cu_]["docstatus"] = 2
frappe.local.__dict__.pop("sx_moc_bat_lo", None)
kiem("phiếu kiểm kê đã huỷ không tính", L.moc_bat_lo() == {})

# Mã bật lô qua kiểm kê SKK-LC lúc 08/10 17:00 (Kho TP đếm; cửa hàng CH Le có tồn không lô → lô tồn cũ LC-TONCU).
for i, ten, pre in (("TP-LC", "Bánh lá cẩm", "LC"), ("TP-LD", "Bánh lá dứa", "LD"), ("TP-LE", "Bánh lẻ", "LE"),
                    ("TP-LH", "Bánh lá hẹ", "LH"), ("TP-LG", "Bánh lá gai", "LG")):
    F.bang("Item")[i] = {"name": i, "item_name": ten, "stock_uom": "Hộp", "custom_sx_nhom": "TP", "disabled": 0,
                         "has_batch_no": 1, "shelf_life_in_days": 270, "custom_batch_prefix": pre}
KKB["SKK-LC"] = {"name": "SKK-LC", "docstatus": 1, "kho": KHO, "chot_luc": "2026-10-08 17:00:00", "ds_se": json.dumps([
    {"dt": "Stock Entry", "name": "SE-LC1"}, {"dt": "Item", "name": "TP-LE", "has_batch_no": [1, 0]},
    {"dt": "Item", "name": "TP-LC", "has_batch_no": [0, 1], "kho_khac": [["CH Le", 10.0]], "lo_cu": "LCX-TONCU"},
    {"dt": "Item", "name": "TP-LD", "has_batch_no": [0, 1]}, {"dt": "Item", "name": "TP-LE", "has_batch_no": [0, 1]},
    {"dt": "Stock Entry", "name": "SE-LC2"}])}
KKB["SKK-LC9"] = {"name": "SKK-LC9", "docstatus": 1, "kho": "CH Le", "chot_luc": "2026-10-09 09:00:00",
                  "ds_se": json.dumps([{"dt": "Item", "name": "TP-LC", "has_batch_no": [0, 1]},
                                       {"dt": "Item", "name": "TP-LG", "has_batch_no": [0, 1]}])}
KKB["SKK-LC0"] = {"name": "SKK-LC0", "docstatus": 2, "kho": KHO, "chot_luc": "2026-10-07 10:00:00",
                  "ds_se": json.dumps([{"dt": "Item", "name": "TP-LH", "has_batch_no": [0, 1]}])}
for b, i, hsd, th in (("LCX-TONCU", "TP-LC", None, 0), ("LC-HSD010327", "TP-LC", "2027-03-01", 0),
                      ("LC-HSD011226", "TP-LC", "2026-12-01", 1), ("LC-HSD011026", "TP-LC", "2026-10-01", 0),
                      ("LD-HSD010327", "TP-LD", "2027-03-01", 0), ("LD-HSD010127", "TP-LD", "2027-01-01", 0)):
    F.bang("Batch")[b] = {"name": b, "batch_id": b, "item": i, "expiry_date": hsd, "custom_thu_hoi": th,
                          "custom_kiem_ke": "SKK-LC" if b in ("LCX-TONCU", "LC-HSD010327") else None}
SO[("TP-LC", "LC-HSD010327")] = 50
SO_KHO["CH Le"] = {("TP-LC", "LCX-TONCU"): 10, ("TP-LC", "LC-HSD010327"): 9, ("TP-LC", "LC-HSD011226"): 30,
                   ("TP-LC", "LC-HSD011026"): 50, ("TP-LD", "LD-HSD010327"): 4, ("TP-LD", "LD-HSD010127"): 2}
SO_KHO["CH Ba"] = {("TP-LC", "LC-HSD010327"): 2}
SO_KHO["CH Khac"] = {("TP-LC", None): -1}
F.bang("Warehouse")["CH Khac"] = {"name": "CH Khac", "company": "CTY-B"}
for n, i, w, g in (("blc1", "TP-LC", KHO, 12000), ("blc2", "TP-LC", "CH Le", 12000), ("blc3", "TP-LC", "CH Ba", 0),
                   ("blc4", "TP-LC", "CH Khac", 12000), ("bld1", "TP-LD", "CH Le", 9000)):
    F.bang("Bin")[n] = {"name": n, "item_code": i, "warehouse": w, "valuation_rate": g}
F.bang("POS Invoice").update({p: {"name": p, "posting_date": "2026-10-08", "posting_time": t} for p, t in (
    ("POS-1", "14:00:00"), ("POS-2", "16:30:00"), ("POS-3", "18:00:00"))})
F.bang("Serial and Batch Entry").update({
    "sbe1": {"name": "sbe1", "parent": "SABB-1", "batch_no": "LD-HSD010127", "qty": -1},
    "sbe2": {"name": "sbe2", "parent": "SABB-2", "batch_no": "LC-HSD010327", "qty": -1}})
frappe.local.__dict__.pop("sx_moc_bat_lo", None)
frappe.local.__dict__.pop("sx_nho", None)
m = L.moc_bat_lo()
kiem("nhiều phiếu bật lô cùng mã → lần SỚM NHẤT; mã vốn có lô (1 → 0 → 1) không tính; phiếu kho của lần chốt (để soát)",
     set(m) == {"TP-LC", "TP-LD", "TP-LG"} and m["TP-LC"]["phieu"] == "SKK-LC" and m["TP-LG"]["phieu"] == "SKK-LC9"
     and str(m["TP-LC"]["luc"]) == "2026-10-08 17:00:00"
     and m["TP-LC"]["lo_cu"] == "LCX-TONCU" and m["TP-LD"]["lo_cu"] is None and m["TP-LC"]["kho"] == KHO
     and m["TP-LC"]["se"] == {"SE-LC1", "SE-LC2"}, m)


def goi_hook(dt, su_kien, doc):
    """Chạy doc_events của app theo đúng thứ tự trong hooks.py (các hook khác không thuộc bài này thì bỏ qua)."""
    ds = H.doc_events[dt].get(su_kien) or []
    for p in [ds] if isinstance(ds, str) else ds:
        mo, ham = p.rsplit(".", 1)
        if mo in ("sx.api.lo_cu", "sx.api.banhang"):
            getattr(sys.modules[mo], ham)(doc, su_kien)


class ChungTuBan(F.Document):
    """Sales Invoice / Delivery Note giả: như Frappe — controller trước rồi doc_events của app. on_submit: ERPNext ghi sổ
    kho theo cờ lô của mã LÚC ĐÓ (mã có lô mà dòng không lô → lỗi; mã không lô mà dòng có lô → lỗi), từ lô ở ô batch_no /
    bundle; huỷ thì ghi ngược."""

    def _ghi_so(self, dau):
        for r in self.items or []:
            co = F.bang("Item")[r["item_code"]].get("has_batch_no")
            sb = r.get("serial_and_batch_bundle")
            if dau > 0 and co and not (r.get("batch_no") or sb):
                raise F.Loi(f"Serial and Batch Bundle not set for {r['item_code']}")
            if dau > 0 and not co and (r.get("batch_no") or sb):
                raise F.Loi(f"Serial No and Batch No are not allowed for Item {r['item_code']}")
            lay = ([(e["batch_no"], abs(e["qty"])) for e in F.bang("Serial and Batch Entry").values() if e["parent"] == sb]
                   if sb else [(r.get("batch_no") if co else None, r.get("stock_qty") or r["qty"])])
            for b, q in lay:
                so = SO_KHO[r["warehouse"]]
                so[(r["item_code"], b)] = round(so.get((r["item_code"], b), 0) - q * dau, 6)
                n = f"sle-{self.name}-{r['idx']}-{b}-{dau}"
                SLE[n] = {"name": n, "item_code": r["item_code"], "warehouse": r["warehouse"], "batch_no": b,
                          "serial_and_batch_bundle": sb, "actual_qty": -q * dau, "voucher_type": self.doctype,
                          "voucher_no": self.name, "posting_datetime": f"{self.posting_date} {self.posting_time}",
                          "creation": "2026-10-09 10:00:00", "is_cancelled": 0 if dau > 0 else 1}

    def before_submit(self):
        goi_hook(self.doctype, "before_submit", self)

    def on_submit(self):
        self._ghi_so(1)
        goi_hook(self.doctype, "on_submit", self)

    def before_cancel(self):
        goi_hook(self.doctype, "before_cancel", self)

    def on_cancel(self):
        self._ghi_so(-1)
        goi_hook(self.doctype, "on_cancel", self)


F.dang_ky("Sales Invoice", ChungTuBan)
F.dang_ky("Delivery Note", ChungTuBan)


def hd(luc, dong, dt="Sales Invoice", **k):
    d = {"doctype": dt, "company": "RVHG", "posting_date": luc[:10], "posting_time": luc[11:],
         "items": [dict({"idx": j, "item_name": F.bang("Item")[r["item_code"]]["item_name"], "stock_qty": r["qty"]}, **r)
                   for j, r in enumerate(dong, 1)]}
    if dt == "Sales Invoice":
        d["update_stock"] = 1
    d.update(k)
    return F.get_doc(d)


def lc(q, w=KHO, **k):
    return dict({"item_code": "TP-LC", "qty": q, "warehouse": w}, **k)


def ld(q, w="CH Le", **k):
    return dict({"item_code": "TP-LD", "qty": q, "warehouse": w}, **k)


co_lo = lambda i: F.bang("Item")[i]["has_batch_no"]   # noqa: E731
SO_D198 = {k: dict(v) for k, v in SO_KHO.items()}

# Hoá đơn tháng 8 (đã ghi sổ hồi tháng 8 — trước lúc bật lô) huỷ để sửa rồi gửi lại.
sa = hd("2026-08-20 09:00:00", [lc(3)], docstatus=1)
sa.insert()
kiem("hoá đơn tháng 8 (ghi sổ trước lúc bật lô), dòng không lô → tạm tắt lô mã đó", L.ma_tam_tat_lo(sa) == {"TP-LC"})
F.get_doc("Sales Invoice", sa.name).cancel()
kiem("HUỶ hoá đơn tháng 8 sau lúc bật lô: trả lại phần KHÔNG lô (như lúc ghi), mã bật lô lại ngay",
     SO[("TP-LC", None)] == 3 and co_lo("TP-LC") == 1 and F.bang("Sales Invoice")[sa.name]["docstatus"] == 2, SO)
sa2 = hd("2026-08-20 09:00:00", [lc(2)], amended_from=sa.name)
n_bao = len(F.BAO)
sa2.insert()
sa2.submit()
kiem("GỬI bản sửa (vẫn ngày tháng 8): qua chặn thiếu lô (W06), ERPNext ghi sổ không lô; mã bật lô lại; không nhắc \"bán "
     "mã không có lô\"", SO[("TP-LC", None)] == 1 and co_lo("TP-LC") == 1
     and F.bang("Sales Invoice")[sa2.name]["docstatus"] == 1 and not any("lá cẩm" in b for b in F.BAO[n_bao:]),
     (SO[("TP-LC", None)], F.BAO[n_bao:]))
# D199: sửa hoá đơn 14/8 trên Desk — hộp chọn lô của ERPNext tự điền lô HSD (gói lô nháp / ô batch_no). Lô đó chỉ có
# hàng từ lúc bật lô: ghi sổ ngày 14/8 thì ERPNext báo "Batch No … has negative stock".
sc = hd("2026-08-14 10:00:00", [lc(2), lc(1)], docstatus=1)
sc.insert()
F.get_doc("Sales Invoice", sc.name).cancel()
F.bang("Serial and Batch Bundle")["SABB-9"] = {"name": "SABB-9", "docstatus": 0, "item_code": "TP-LC"}
F.bang("Serial and Batch Entry")["sbe9"] = {"name": "sbe9", "parent": "SABB-9", "batch_no": "LC-HSD010327", "qty": -2}
sc2 = hd("2026-08-14 10:00:00", [lc(2, serial_and_batch_bundle="SABB-9"),
                                 lc(1, batch_no="LC-HSD010327", use_serial_batch_fields=1)], amended_from=sc.name)
kiem("dòng MANG lô mà ghi sổ trước lúc bật lô: chưa gửi thì chưa đụng (không tắt lô)", L.ma_tam_tat_lo(sc2) == set())
sc2.insert()
n_bao = len(F.BAO)
sc2.submit()
dong9 = [(r.get("batch_no"), r.get("serial_and_batch_bundle"), r.get("use_serial_batch_fields"))
         for r in F.bang("Sales Invoice")[sc2.name]["items"]]
kiem("D199: GỬI bản sửa hoá đơn 14/8 mà dòng mang lô (gói lô nháp, ô Batch No) → bỏ lô, xoá gói lô nháp, ghi sổ KHÔNG lô; "
     "lô HSD không bị trừ; cờ lô bật lại",
     dong9 == [(None, None, 0), (None, None, 0)] and "SABB-9" not in F.bang("Serial and Batch Bundle")
     and SO[("TP-LC", None)] == 1 and SO[("TP-LC", "LC-HSD010327")] == 50 and co_lo("TP-LC") == 1
     and F.bang("Sales Invoice")[sc2.name]["docstatus"] == 1, (dong9, SO.get(("TP-LC", None))))
bao9 = " ".join(F.BAO[n_bao:])
kiem("… báo lại: ngày ghi sổ, đã bỏ lô nào ở dòng nào", "Chứng từ ghi sổ ngày 14/08/2026" in bao9
     and "Dòng 1: Bánh lá cẩm — lô LC-HSD010327" in bao9 and "Dòng 2: Bánh lá cẩm — lô LC-HSD010327" in bao9, bao9)
F.bang("Serial and Batch Bundle")["SABB-8"] = {"name": "SABB-8", "docstatus": 1, "item_code": "TP-LC"}
x = hd("2026-08-14 10:00:00", [lc(1, serial_and_batch_bundle="SABB-8")], docstatus=1)
L.tam_tat_lo(x)
kiem("… gói lô ĐÃ GỬI thì để nguyên (không bỏ, không tắt lô)",
     x.items[0].get("serial_and_batch_bundle") == "SABB-8" and x.flags.sx_tam_tat_lo == [] and co_lo("TP-LC") == 1)
x = hd("2026-08-14 10:00:00", [lc(1, batch_no="LC-HSD010327")], docstatus=2)
L.tam_tat_lo(x)
kiem("… lúc HUỶ không bỏ lô, không tắt lô (chứng từ đã gửi có lô thì ERPNext đã ghi theo lô)",
     x.items[0].get("batch_no") == "LC-HSD010327" and x.flags.sx_tam_tat_lo == [])
sb = hd("2026-10-09 09:30:00", [lc(1)])
sb.insert()
loi = thu(sb.submit) or ""
kiem("hoá đơn lập SAU lúc bật lô, dòng không lô → không tắt lô: chặn \"Chưa chọn lô\" như thường (chọn lô trên hoá đơn)",
     L.ma_tam_tat_lo(sb) == set() and "Chưa chọn lô" in loi and co_lo("TP-LC") == 1 and SO[("TP-LC", None)] == 1, loi)
kiem("hoá đơn không trừ kho; mã không có trong nhật ký bật lô; dòng đã gắn lô (chưa gửi — xem D199) → không đụng",
     L.ma_tam_tat_lo(hd("2026-08-20 09:00:00", [lc(1)], update_stock=0)) == set()
     and L.ma_tam_tat_lo(hd("2026-08-20 09:00:00", [{"item_code": "TP-SEN", "qty": 1, "warehouse": KHO}])) == set()
     and L.ma_tam_tat_lo(hd("2026-08-20 09:00:00", [lc(1), lc(1, batch_no="LC-HSD010327")])) == set())
F.bang("Item")["TP-LD"]["has_batch_no"] = 0
kiem("mã đang KHÔNG lô (đã tắt lại tay) → không đụng", L.ma_tam_tat_lo(hd("2026-08-20 09:00:00", [ld(1)])) == set())
F.bang("Item")["TP-LD"]["has_batch_no"] = 1

# Phiếu giao hàng tháng 9 (ghi sổ trước lúc bật lô) huỷ sau lúc bật lô → cửa hàng dư phần không lô.
dn = hd("2026-09-15 10:00:00", [ld(2)], dt="Delivery Note", docstatus=1)
dn.insert()
F.get_doc("Delivery Note", dn.name).cancel()
kiem("Delivery Note cũ huỷ: cũng ghi không lô, lô bật lại", SO_KHO["CH Le"][("TP-LD", None)] == 2 and co_lo("TP-LD") == 1,
     SO_KHO["CH Le"])

# Đóng ca POS: hoá đơn gộp, giờ ghi sổ = giờ phiếu POS cuối.
sp = hd("2026-10-08 16:30:00", [lc(2, "CH Le", pos_invoice="POS-1"), lc(1, "CH Le", pos_invoice="POS-2")],
        is_consolidated=1)
kiem("hoá đơn gộp từ POS, mọi phiếu POS lập trước lúc bật lô → tạm tắt lô", L.ma_tam_tat_lo(sp) == {"TP-LC"})
kiem("… xét giờ TỪNG phiếu POS, không theo giờ hoá đơn gộp",
     L.ma_tam_tat_lo(hd("2026-10-08 18:00:00", [lc(1, "CH Le", pos_invoice="POS-1")], is_consolidated=1)) == {"TP-LC"}
     and L.ma_tam_tat_lo(hd("2026-10-08 16:00:00", [lc(1, "CH Le", pos_invoice="POS-3")], is_consolidated=1)) == set())
sp.insert()
sp.submit()
kiem("ĐÓNG CA POS được: hoá đơn gộp ghi sổ không lô ở cửa hàng, lô tồn cũ chưa đụng (dọn sau), mã bật lô lại",
     SO_KHO["CH Le"][("TP-LC", None)] == -3 and SO_KHO["CH Le"][("TP-LC", "LCX-TONCU")] == 10 and co_lo("TP-LC") == 1
     and F.bang("Sales Invoice")[sp.name]["docstatus"] == 1, SO_KHO["CH Le"])
kiem("phiếu trả hàng gộp từ POS (phiếu POS trả trước lúc bật lô) → cũng ghi không lô",
     L.ma_tam_tat_lo(hd("2026-10-09 09:00:00", [lc(-1, "CH Le", pos_invoice="POS-2")], is_consolidated=1,
                        is_return=1)) == {"TP-LC"})

# Ca lẫn: phiếu POS trước lúc bật lô (không lô) gộp cùng phiếu sau lúc bật lô (đã có lô / máy POS còn nhớ mã chưa lô).
sm = hd("2026-10-08 18:00:00", [ld(2, pos_invoice="POS-1"), ld(1, pos_invoice="POS-3", serial_and_batch_bundle="SABB-1"),
                                lc(6, "CH Le", pos_invoice="POS-3"), lc(5, "CH Le", pos_invoice="POS-3"),
                                lc(1, "CH Le", pos_invoice="POS-3")], is_consolidated=1)
kiem("ca lẫn: mã có dòng đã gắn lô / dòng lập sau lúc bật lô → không tắt lô được", L.ma_tam_tat_lo(sm) == set()
     and L.ma_tam_tat_lo(hd("2026-10-08 18:00:00", [lc(1, "CH Le", pos_invoice="POS-1"),
                                                    lc(1, "CH Le", pos_invoice="POS-3")], is_consolidated=1)) == set())
sm.insert()
sm.submit()
gan = [(r["item_code"], r.get("batch_no"), r.get("use_serial_batch_fields"))
       for r in F.bang("Sales Invoice")[sm.name]["items"]]
kiem("… GÁN LÔ dòng không lô: lô tồn cũ trước (đủ cả dòng); không đủ → HSD sớm nhất (bỏ lô thu hồi, lô hết hạn ở ngày "
     "ghi sổ); lô dòng có bundle đã lấy thì trừ ra (lá dứa HSD 01/01/27 còn 1 < 2 → HSD 01/03/27)",
     gan == [("TP-LD", "LD-HSD010327", 1), ("TP-LD", None, None), ("TP-LC", "LCX-TONCU", 1),
             ("TP-LC", "LC-HSD010327", 1), ("TP-LC", "LCX-TONCU", 1)], gan)
kiem("… hoá đơn gộp qua chặn thiếu lô, ghi sổ đúng lô đã gán; cờ lô không đổi",
     F.bang("Sales Invoice")[sm.name]["docstatus"] == 1 and SO_KHO["CH Le"][("TP-LC", "LCX-TONCU")] == 3
     and SO_KHO["CH Le"][("TP-LC", "LC-HSD010327")] == 4 and SO_KHO["CH Le"][("TP-LD", "LD-HSD010327")] == 2
     and SO_KHO["CH Le"][("TP-LD", "LD-HSD010127")] == 1 and SO_KHO["CH Le"][("TP-LC", None)] == -3
     and co_lo("TP-LC") == 1 and co_lo("TP-LD") == 1, SO_KHO["CH Le"])
x = hd("2026-10-08 18:00:00", [lc(3, "CH Le", pos_invoice="POS-3", batch_no="LCX-TONCU"),
                               lc(2, "CH Le", pos_invoice="POS-3")], is_consolidated=1, docstatus=1)
L.tam_tat_lo(x)
kiem("… dòng đã chọn lô ở ô batch_no cũng trừ ra (lô tồn cũ còn 3, dòng kia lấy hết → HSD 01/03/27)",
     [r.get("batch_no") for r in x.items] == ["LCX-TONCU", "LC-HSD010327"], [r.get("batch_no") for r in x.items])
x = hd("2026-10-08 18:00:00", [lc(2, pos_invoice="POS-3")], is_consolidated=1, docstatus=1)
L.tam_tat_lo(x)
kiem("… phiếu POS lập SAU lúc bật lô ở chính kho đã kiểm kê: gán lô bình thường (số đếm chưa trừ phần này)",
     x.items[0].get("batch_no") == "LC-HSD010327", x.items[0])
SO_KHO["CH Le"][("TP-LC", "LC-HSD010327")] += 20                  # nhập 20 vào lô lúc 09/10 09:00 (sau giờ hoá đơn)
for n, b, q in (("d198n", "LC-HSD010327", 20), ("d198x", "LCX-TONCU", -5)):    # … và đã bán 5 từ lô tồn cũ
    SLE[n] = {"name": n, "item_code": "TP-LC", "warehouse": "CH Le", "batch_no": b, "actual_qty": q,
              "voucher_type": "Stock Entry", "voucher_no": "SE-" + n, "posting_datetime": "2026-10-09 09:00:00",
              "creation": "2026-10-09 09:00:00", "is_cancelled": 0}
C._so_lo = so_lo_gia
loi = thu(lambda: hd("2026-10-08 18:00:00", [lc(10, "CH Le", pos_invoice="POS-3")], is_consolidated=1).insert().submit())
kiem("tồn lô tính tới GIỜ GHI SỔ hoá đơn (nhập sau đó không tính) — không lô nào đủ → chặn, nói dòng, phiếu POS, kho, số",
     "Dòng 1: Bánh lá cẩm (phiếu POS POS-3, kho CH Le) — không lô nào ở kho đủ 10 (lô bán được: LCX-TONCU 3, "
     "LC-HSD010327 4)" in (loi or ""), loi)
loi = thu(lambda: hd("2026-10-08 18:00:00", [lc(6, "CH Le", pos_invoice="POS-3")], is_consolidated=1).insert().submit())
kiem("… và không quá tồn HIỆN TẠI (lô tồn cũ lúc đó 8 nhưng giờ còn 3 — đã bán sau đó)",
     "không lô nào ở kho đủ 6 (lô bán được: LCX-TONCU 3, LC-HSD010327 4)" in (loi or "")
     and "bán quá tồn lô" in loi, loi)
C._so_lo = SO_LO_CU
SO_KHO["CH Le"][("TP-LC", "LC-HSD010327")] -= 20
SLE.pop("d198n")
SLE.pop("d198x")
F.bang("Sales Invoice")["SI-POSCU"] = {"name": "SI-POSCU", "doctype": "Sales Invoice", "docstatus": 1, "update_stock": 1,
                                       "is_consolidated": 1, "posting_date": "2026-10-08", "posting_time": "18:00:00",
                                       "items": [lc(1, "CH Le", idx=1, pos_invoice="POS-3", stock_qty=1)]}
F.get_doc("Sales Invoice", "SI-POSCU").cancel()
kiem("HUỶ hoá đơn gộp: không gán lô (chỉ lúc gửi)", F.bang("Sales Invoice")["SI-POSCU"]["docstatus"] == 2
     and not F.bang("Sales Invoice")["SI-POSCU"]["items"][0].get("batch_no"), F.bang("Sales Invoice")["SI-POSCU"])
SO_KHO["CH Le"][("TP-LC", None)] -= 1
for k in [k for k, v in SLE.items() if v.get("voucher_no") == "SI-POSCU"]:
    SLE.pop(k)
so_truoc = {k: dict(v) for k, v in SO_KHO.items()}
sk = hd("2026-10-08 18:00:00", [lc(2, pos_invoice="POS-1"), lc(1, pos_invoice="POS-3", serial_and_batch_bundle="SABB-2")],
        is_consolidated=1)
sk.insert()
n_se = len(F.bang("Stock Entry"))
sk.submit()
bu_ = [e for n, e in F.bang("Stock Entry").items() if f"hoá đơn gộp POS {sk.name} " in (e.get("remarks") or "")]
kiem("D200 — ca lẫn ở CHÍNH kho đã kiểm kê: phiếu POS trước lúc bật lô (số đếm đã trừ phần đó) → nhập bù đủ số vào lô "
     "tồn cũ ngay trước giờ hoá đơn rồi bán ra: lô không đổi, không trừ hai lần; dòng đã chọn lô bán như thường",
     F.bang("Sales Invoice")[sk.name]["docstatus"] == 1 and len(bu_) == 1 and len(F.bang("Stock Entry")) == n_se + 1
     and [(r["item_code"], r["t_warehouse"], r["batch_no"], r["qty"]) for r in bu_[0]["items"]]
     == [("TP-LC", KHO, "LCX-TONCU", 2)] and bu_[0]["posting_time"] == "17:59:59"
     and str(bu_[0]["posting_date"]) == "2026-10-08" and SO[("TP-LC", "LCX-TONCU")] == 0
     and SO[("TP-LC", "LC-HSD010327")] == so_truoc[KHO][("TP-LC", "LC-HSD010327")] - 1
     and F.bang("Sales Invoice")[sk.name]["items"][0]["batch_no"] == "LCX-TONCU" and co_lo("TP-LC") == 1,
     (bu_, F.bang("Sales Invoice")[sk.name]["items"]))
# D200 — cửa hàng (CH BD): phiếu POS lập trước lúc bật lô (không lô) + phiếu sau lúc bật lô đã chọn lô tồn cũ; sổ cửa
# hàng chỉ có 5 trong lô tồn cũ mà ca bán 8 + 6 → lô không đủ (lô không được âm).
SO_KHO["CH BD"] = {("TP-LC", "LCX-TONCU"): 5}
F.bang("POS Invoice")["POS-4"] = {"name": "POS-4", "posting_date": "2026-10-08", "posting_time": "18:30:00"}
F.bang("Serial and Batch Bundle")["SABB-4"] = {"name": "SABB-4", "docstatus": 1, "item_code": "TP-LC"}
F.bang("Serial and Batch Entry")["sbe4"] = {"name": "sbe4", "parent": "SABB-4", "batch_no": "LCX-TONCU", "qty": -2}
sq = hd("2026-10-08 19:00:00", [lc(8, "CH BD", pos_invoice="POS-1"),
                                lc(2, "CH BD", pos_invoice="POS-4", serial_and_batch_bundle="SABB-4")], is_consolidated=1)
sq.insert()
n_bao = len(F.BAO)
sq.submit()
bu_ = [e for n, e in F.bang("Stock Entry").items() if f"hoá đơn gộp POS {sq.name} " in (e.get("remarks") or "")]
kiem("D200 — đóng ca vắt qua lúc bật lô, lô tồn cũ ở cửa hàng không đủ (sổ thiếu hàng so với thực bán): NHẬP BÙ phần "
     "thiếu vào lô tồn cũ 1 giây trước giờ hoá đơn (lô còn 3 sau dòng đã chọn lô, phiếu trước lúc bật lô cần 8 → bù 5) "
     "rồi ghi sổ theo lô — đóng ca được, lô về 0 không âm",
     F.bang("Sales Invoice")[sq.name]["docstatus"] == 1 and len(bu_) == 1
     and [(r["item_code"], r["t_warehouse"], r["batch_no"], r["qty"]) for r in bu_[0]["items"]]
     == [("TP-LC", "CH BD", "LCX-TONCU", 5)] and bu_[0]["posting_time"] == "18:59:59"
     and bu_[0]["items"][0]["basic_rate"] == 12000 and SO_KHO["CH BD"][("TP-LC", "LCX-TONCU")] == 0
     and F.bang("Sales Invoice")[sq.name]["items"][0]["batch_no"] == "LCX-TONCU" and co_lo("TP-LC") == 1,
     (bu_, SO_KHO["CH BD"]))
kiem("… ghi chú như phiếu dọn tồn không lô (có mã lần dọn, số hoá đơn) — in lại được; báo lại đã nhập bù",
     bu_[0]["remarks"].startswith("Dọn tồn không lô sau bật lô [DL-") and "Nhập bù lô" in " ".join(F.BAO[n_bao:])
     and "TP-LC · CH BD · LCX-TONCU: +5" in " ".join(F.BAO[n_bao:]), F.BAO[n_bao:])
F.get_doc("Sales Invoice", sq.name).cancel()
kiem("… HUỶ hoá đơn gộp (huỷ lần đóng ca): huỷ luôn phiếu nhập bù — lô tồn cũ về như trước",
     F.bang("Sales Invoice")[sq.name]["docstatus"] == 2 and F.bang("Stock Entry")[bu_[0]["name"]]["docstatus"] == 2
     and SO_KHO["CH BD"][("TP-LC", "LCX-TONCU")] == 5, SO_KHO["CH BD"])
F.bang("POS Invoice")["POS-0"] = {"name": "POS-0", "posting_date": "2026-10-08", "posting_time": "15:00:00"}
F.bang("Serial and Batch Bundle")["SABB-7"] = {"name": "SABB-7", "docstatus": 1, "item_code": "TP-LC"}
F.bang("Serial and Batch Entry")["sbe7"] = {"name": "sbe7", "parent": "SABB-7", "batch_no": "LCX-TONCU", "qty": -2}
F.bang("Serial and Batch Bundle")["SABB-5"] = {"name": "SABB-5", "docstatus": 1, "item_code": "TP-LC"}
F.bang("Serial and Batch Entry")["sbe5"] = {"name": "sbe5", "parent": "SABB-5", "batch_no": "LCX-TONCU", "qty": -6}
sv = hd("2026-10-08 19:00:00", [lc(2, "CH BD", pos_invoice="POS-0", serial_and_batch_bundle="SABB-7"),
                                lc(6, "CH BD", pos_invoice="POS-4", serial_and_batch_bundle="SABB-5")], is_consolidated=1)
sv.insert()
sv.submit()
bu_ = [e for n, e in F.bang("Stock Entry").items() if f"hoá đơn gộp POS {sv.name} " in (e.get("remarks") or "")]
kiem("… ca chỉ có dòng đã chọn lô (phiếu POS đã chọn lô TRƯỚC lúc bật lô — kiểm kê huỷ chốt rồi chốt lại — và sau): "
     "lô các dòng đó lấy quá tồn (2 + 6 > 5) → nhập bù 3",
     F.bang("Sales Invoice")[sv.name]["docstatus"] == 1 and len(bu_) == 1
     and [(r["batch_no"], r["qty"]) for r in bu_[0]["items"]] == [("LCX-TONCU", 3)]
     and SO_KHO["CH BD"][("TP-LC", "LCX-TONCU")] == 0, (bu_, SO_KHO["CH BD"]))
F.get_doc("Sales Invoice", sv.name).cancel()
# mã TP-LG bật lô ở phiếu SKK-LC9 (09/10 09:00, kho CH Le — kho đã kiểm kê của mã đó), chưa có lô tồn cũ.
F.bang("Batch")["LG-HSD010327"] = {"name": "LG-HSD010327", "batch_id": "LG-HSD010327", "item": "TP-LG",
                                   "expiry_date": "2027-03-01", "custom_kiem_ke": "SKK-LC9"}
SO_KHO["CH Le"][("TP-LG", "LG-HSD010327")] = 5
F.bang("POS Invoice")["POS-5"] = {"name": "POS-5", "posting_date": "2026-10-09", "posting_time": "09:30:00"}
F.bang("Serial and Batch Bundle")["SABB-6"] = {"name": "SABB-6", "docstatus": 1, "item_code": "TP-LG"}
F.bang("Serial and Batch Entry")["sbe6"] = {"name": "sbe6", "parent": "SABB-6", "batch_no": "LG-HSD010327", "qty": -1}
sg = hd("2026-10-09 09:30:00", [{"item_code": "TP-LG", "qty": 2, "warehouse": "CH Le", "pos_invoice": "POS-1"},
                                {"item_code": "TP-LG", "qty": 1, "warehouse": "CH Le", "pos_invoice": "POS-5",
                                 "serial_and_batch_bundle": "SABB-6"}], is_consolidated=1)
sg.insert()
sg.submit()
kiem("… lô tồn cũ chưa có thì tạo khi nhập bù — gắn phiếu kiểm kê bật lô của mã (miễn BM.08.04), ghi rõ nguồn",
     F.bang("Sales Invoice")[sg.name]["docstatus"] == 1 and F.bang("Batch")["LG-TONCU"]["item"] == "TP-LG"
     and F.bang("Batch")["LG-TONCU"]["custom_kiem_ke"] == "SKK-LC9"
     and "nhập bù lúc đóng ca POS" in F.bang("Batch")["LG-TONCU"]["description"]
     and SO_KHO["CH Le"][("TP-LG", "LG-TONCU")] == 0 and SO_KHO["CH Le"][("TP-LG", "LG-HSD010327")] == 4,
     F.bang("Batch").get("LG-TONCU"))
x = hd("2026-10-08 16:00:00", [lc(1, "CH BD", pos_invoice="POS-1"),
                               lc(2, "CH BD", pos_invoice="POS-0", serial_and_batch_bundle="SABB-7")],
       is_consolidated=1, docstatus=1)
loi = thu(lambda: L.tam_tat_lo(x)) or ""
kiem("… hoá đơn gộp ghi sổ TRƯỚC lúc bật lô mà có phiếu POS đã chọn lô (lập trong lúc kiểm kê bị huỷ chốt) → chặn, nói "
     "phiếu POS, lúc bật lô, cách làm; không nhập bù",
     "hoá đơn ghi sổ lúc 08/10 16:00, trước lúc kiểm kê SKK-LC bật lô (08/10 17:00) mà có phiếu POS đã chọn lô (POS-0)"
     in loi and "huỷ chốt" in loi and getattr(x.flags, "sx_tam_tat_lo", None) is None, loi)
kiem("hook nối đúng thứ tự: tạm tắt lô ĐẦU before_submit (trước chặn thiếu lô W06) / before_cancel; bật lại CUỐI "
     "on_submit / on_cancel — cả Sales Invoice và Delivery Note",
     all(H.doc_events[dt]["before_submit"][:2] == ["sx.api.lo_cu.tam_tat_lo", "sx.api.banhang.kiem_lo_ban"]
         and H.doc_events[dt]["on_submit"][-1] == "sx.api.lo_cu.bat_lai_lo"
         and H.doc_events[dt]["before_cancel"] == "sx.api.lo_cu.tam_tat_lo"
         and H.doc_events[dt]["on_cancel"] == "sx.api.lo_cu.bat_lai_lo" for dt in ("Sales Invoice", "Delivery Note")))

# Dọn tồn không lô còn lại: Kho TP (đã đếm) +1; CH Le lá cẩm −3, lá dứa +2; CH Ba lá cẩm −5 (lô chỉ còn 2); CH Khac (công
# ty khác) −1.
SO_KHO["CH Ba"][("TP-LC", None)] = -5
for n, vn, luc in (("d198c", "SE-LC1", "2026-10-08 17:00:05"), ("d198t", "SINV-CU", "2026-10-01 09:00:00")):
    SLE[n] = {"name": n, "item_code": "TP-LC", "warehouse": KHO, "batch_no": None, "serial_and_batch_bundle": None,
              "actual_qty": -1, "voucher_type": "Stock Entry", "voucher_no": vn, "posting_datetime": luc,
              "creation": luc, "is_cancelled": 0}
CHO_AM["v"] = True                         # có phần không lô âm nghĩa là site đang cho tồn âm
F.vai("SX Thu Kho", u="kho@x")
x = L.ds_du()
dong_ = [(r["item"], r["kho"], r["so"], r["cach"], r["lay"], r["vao"], r["thieu"]) for r in x["dong"]]
kiem("xem: phần không lô khác 0 của mã đã bật lô, mỗi (mã, kho) một dòng; kho đã kiểm kê → điều chỉnh; kho khác → đổi với "
     "lô (âm: lấy lô tồn cũ trước, thiếu thì báo; dương: vào lô tồn cũ — chưa có thì theo tên lô tồn cũ của mã); bỏ kho "
     "công ty khác",
     dong_ == [("TP-LC", "CH Ba", -5, "doi_lo", [{"batch": "LC-HSD010327", "so": 2}], None, 3),
               ("TP-LC", "CH Le", -3, "doi_lo", [{"batch": "LCX-TONCU", "so": 3}], None, 0),
               ("TP-LC", KHO, 1, "dieu_chinh", [], None, 0), ("TP-LD", "CH Le", 2, "doi_lo", [], "LD-TONCU", 0)], dong_)
kiem("… giá vốn (kho chưa có giá → giá của kho khác), giá trị điều chỉnh; tổng; thủ kho xem được, không dọn được",
     x["dong"][0]["gia"] == 12000 and x["dong"][2]["gia_tri"] == 12000 and x["dong"][3]["gia"] == 9000
     and x["tong"] == {"so_dong": 4, "so_ma": 2, "dieu_chinh": 12000} and x["duoc_don"] is False, x["tong"])
kiem("… kèm chứng từ ghi sổ phần không lô sau lúc bật lô (để soát)",
     x["dong"][2]["ct"] == [f"Sales Invoice {sa.name} (huỷ)", f"Sales Invoice {sa2.name}",
                            f"Sales Invoice {sc.name} (huỷ)", f"Sales Invoice {sc2.name}"]
     and x["dong"][1]["ct"] == [f"Sales Invoice {sp.name}"], [r["ct"] for r in x["dong"]])
kiem("thủ kho bấm dọn → chặn (bút toán điều chỉnh kho — chỉ quản lý)", "Chỉ quản lý" in (thu(L.don_du) or ""))
F.vai("SX QC", u="qc@x")
kiem("vai ngoài thẻ kiểm kê → không xem được", thu(L.ds_du) is not None)
F.vai("SX Quan Ly", u="ql@x")
n_se = len(F.bang("Stock Entry"))
kq = L.don_du()
se_ = [F.bang("Stock Entry")[n] for n in kq["phieu"]]
buoc = [(e["purpose"], sorted((r.get("s_warehouse") or r.get("t_warehouse"), r["item_code"], r.get("batch_no") or "",
                               r["qty"]) for r in e["items"])) for e in se_]
kiem("DỌN: (1) mã tạm tắt lô — nhập bù phần không lô âm (đổi với lô: đúng số lấy được), xuất phần không lô dương; (2) bật "
     "lô — xuất khỏi lô phần đã bán trước lúc bật lô, nhập phần thừa vào lô tồn cũ",
     buoc == [("Material Receipt", [("CH Ba", "TP-LC", "", 2), ("CH Le", "TP-LC", "", 3)]),
              ("Material Issue", [("CH Le", "TP-LD", "", 2), (KHO, "TP-LC", "", 1)]),
              ("Material Issue", [("CH Ba", "TP-LC", "LC-HSD010327", 2), ("CH Le", "TP-LC", "LCX-TONCU", 3)]),
              ("Material Receipt", [("CH Le", "TP-LD", "LD-TONCU", 2)])]
     and len(F.bang("Stock Entry")) == n_se + 4, buoc)
kiem("… sau dọn: phần không lô về 0 (CH Ba còn −3 — lô không đủ, báo lại); lô tồn cũ trừ / cộng đúng; kho công ty khác "
     "giữ nguyên; cờ lô bật lại",
     SO[("TP-LC", None)] == 0 and SO_KHO["CH Le"][("TP-LC", None)] == 0 and SO_KHO["CH Le"][("TP-LC", "LCX-TONCU")] == 0
     and SO_KHO["CH Le"][("TP-LD", None)] == 0 and SO_KHO["CH Le"][("TP-LD", "LD-TONCU")] == 2
     and SO_KHO["CH Ba"][("TP-LC", None)] == -3 and SO_KHO["CH Ba"][("TP-LC", "LC-HSD010327")] == 0
     and SO_KHO["CH Khac"] == {("TP-LC", None): -1} and co_lo("TP-LC") == 1 and co_lo("TP-LD") == 1,
     {k: v for k, v in SO_KHO.items() if k != "Kho BTP"})
kiem("… lô tồn cũ chưa có thì tạo (gắn phiếu kiểm kê bật lô — miễn BM.08.04); giá vốn; ghi chú có mã lần dọn",
     F.bang("Batch")["LD-TONCU"]["item"] == "TP-LD" and F.bang("Batch")["LD-TONCU"]["custom_kiem_ke"] == "SKK-LC"
     and "dọn sau lúc bật lô — DL-091026-100000" in F.bang("Batch")["LD-TONCU"]["description"]
     and se_[0]["items"][0]["basic_rate"] == 12000
     and all(e["remarks"].startswith("Dọn tồn không lô sau bật lô [DL-091026-100000]: ") for e in se_), se_[0])
kiem("… trả kết quả: lần dọn, số dòng / mã, dòng còn âm vì lô không đủ",
     kq["lan"] == "DL-091026-100000" and kq["so_dong"] == 4 and kq["so_ma"] == 2
     and kq["con_thieu"] == [{"ten": "Bánh lá cẩm", "kho": "CH Ba", "so": 3}], kq)
x = L.ds_du()
kiem("xem lại: còn đúng dòng thiếu lô; lần dọn vừa rồi trong danh sách đã dọn (in lại được)",
     [(r["kho"], r["so"], r["lay"], r["thieu"]) for r in x["dong"]] == [("CH Ba", -3, [], 3)]
     and x["lan_truoc"][0]["lan"] == "DL-091026-100000" and set(kq["phieu"]) <= set(x["lan_truoc"][0]["phieu"])
     and x["duoc_don"] is True, (x["dong"], x["lan_truoc"]))
SO_KHO["CH Ba"][("TP-LC", None)] = 0
kiem("hết phần không lô → dọn báo không còn gì", "Không còn tồn không lô" in (thu(L.don_du) or ""))
html = " ".join(L.bien_ban(json.dumps(kq["phieu"])).split())
kiem("danh sách in cho kế toán: kho, sản phẩm, lô / không lô, số (+ / −), việc, phiếu, lần dọn, chỗ ký",
     "Danh sách dọn tồn không lô sau lúc bật quản lý lô" in html and "Lần DL-091026-100000" in html
     and "CH Ba" in html and "Bánh lá dứa" in html and "LD-TONCU" in html and "(không lô)" in html and "+3" in html
     and "-3" in html and "nhập bù phần không lô âm" in html and "Kế toán" in html
     and all(n in html for n in kq["phieu"]), html[:1500])
khac_ = next(n for n, e in F.bang("Stock Entry").items() if not str(e.get("remarks") or "").startswith("Dọn tồn không"))
kiem("in phiếu không phải phiếu dọn tồn không lô → chặn",
     f"{khac_} không phải phiếu dọn tồn không lô" in (thu(lambda: L.bien_ban(json.dumps([se_[0]["name"], khac_]))) or ""))

for n in reversed(kq["phieu"]):
    F.get_doc("Stock Entry", n).cancel()
for t in ("Sales Invoice", "Delivery Note", "POS Invoice", "Serial and Batch Entry", "Serial and Batch Bundle"):
    F.bang(t).clear()
for k in [k for k, v in SLE.items() if v.get("voucher_no") in (sa.name, sa2.name, sc.name, sc2.name, sp.name, sm.name,
                                                               dn.name, sk.name, sq.name, sv.name, sg.name)]:
    SLE.pop(k)
SLE.pop("d198c")
SLE.pop("d198t")
for k in ("SKK-LC", "SKK-LC9", "SKK-LC0"):
    KKB.pop(k)
for i in ("TP-LC", "TP-LD", "TP-LE", "TP-LH", "TP-LG"):
    F.bang("Item").pop(i)
for b in [b for b, v in F.bang("Batch").items() if v.get("item") in ("TP-LC", "TP-LD", "TP-LG")]:
    F.bang("Batch").pop(b)
for n in ("blc1", "blc2", "blc3", "blc4", "bld1"):
    F.bang("Bin").pop(n)
for k in ("CH Le", "CH Ba", "CH Khac", "CH BD"):
    SO_KHO.pop(k)
for k in [k for k in SO if k[0] == "TP-LC"]:
    SO.pop(k)
F.bang("Warehouse").pop("CH Khac")
CHO_AM["v"] = False
frappe.local.__dict__.pop("sx_moc_bat_lo", None)
frappe.local.__dict__.pop("sx_nho", None)
F.vai("SX Thu Kho", u="kho@x")

print("\n-- dây nối --")
kiem("thẻ kiemke: thủ kho + quản lý; nằm ở màn Nhập kho (sau phiếu nhập) và Quản lý",
     R.CARD_ROLES["kiemke"] == [R.THU_KHO, R.QUAN_LY] and R.VIEW_CARDS["nhapkho"][:2] == ["nhapkhotp", "kiemke"]
     and "kiemke" in R.VIEW_CARDS["quanly"])
sh = open("sx/public/sx/shell.js", encoding="utf-8").read()
kiem("shell biết thẻ kiemke", "kiemke: '/assets/sx/sx/cards/kiemke.js'" in sh)
cf = {f["name"]: f for f in json.load(open("sx/fixtures/custom_field.json", encoding="utf-8"))}
kiem("custom field: Batch.custom_kiem_ke + Stock Entry.custom_kiem_ke (Link SX Kiem Ke, chỉ đọc)",
     all(cf.get(n, {}).get("options") == "SX Kiem Ke" and cf[n].get("read_only") == 1
         for n in ("Batch-custom_kiem_ke", "Stock Entry-custom_kiem_ke")))
xx = open("sx/api/xuatxuong.py", encoding="utf-8").read()
kiem("chặn bán BM.08.04 miễn lô nhận hàng tồn cũ qua kiểm kê", 'x.get("custom_kiem_ke")' in xx
     and '"custom_kiem_ke"]' in xx)
for d_ in ("sx_kiem_ke", "sx_kiem_ke_dong", "sx_kiem_ke_lo"):
    kiem(f"doctype {d_} đủ __init__ / json / py", all(os.path.exists(f"sx/sx/doctype/{d_}/{f}")
                                                     for f in ("__init__.py", f"{d_}.json", f"{d_}.py")))
dt = json.load(open("sx/sx/doctype/sx_kiem_ke/sx_kiem_ke.json", encoding="utf-8"))
kiem("SX Kiem Ke submittable, có amended_from, bảng dòng + lô",
     dt["is_submittable"] == 1 and {"amended_from", "dong", "lo", "ds_se"} <= {f["fieldname"] for f in dt["fields"]})
loai_ = next(f for f in dt["fields"] if f["fieldname"] == "loai")
kiem("SX Kiem Ke: ô loại hàng Thành phẩm / Bán thành phẩm, mặc định Thành phẩm (phiếu D154 cũ migrate ra thành phẩm)",
     loai_["options"].split("\n") == ["Thành phẩm", "Bán thành phẩm"] and loai_["default"] == "Thành phẩm"
     and C.TP == "Thành phẩm" and C.BTP == "Bán thành phẩm")
for d_ in ("sx_kiem_ke_dong", "sx_kiem_ke_lo"):
    j = json.load(open(f"sx/sx/doctype/{d_}/{d_}.json", encoding="utf-8"))
    kiem(f"{d_}: cột lưới ≤ 10 (Frappe bỏ bớt cột thừa trên Desk)",
         sum(f.get("columns") or 0 for f in j["fields"] if f.get("in_list_view")) <= 10)
kiem("bảng dòng có cột lô (bán thành phẩm cân theo lô)", "batch" in {f["fieldname"] for f in json.load(open(
    "sx/sx/doctype/sx_kiem_ke_dong/sx_kiem_ke_dong.json", encoding="utf-8"))["fields"]})

F.ket_thuc("KIEMKE")
