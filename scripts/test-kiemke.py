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
kiem("đếm ÍT hơn sổ của một HSD: bớt từ lô CŨ trước, giữ hàng trên lô chuẩn …-HSD",
     sorted((x["batch"], x["so"]) for x in ke["giu"]) == [("SEN-110926", 5), ("SEN-HSD080627", 30)]
     and ke["xuat"] == [{"batch": "SEN-110926", "hsd": H1, "so": 15}], ke)

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
        if p == "Repack":
            for r in self.items:                     # ERPNext StockEntry.validate_batch
                hsd = F.bang("Batch")[r["batch_no"]].get("expiry_date")
                assert not hsd or str(hsd)[:10] >= F.hom_nay().isoformat(), ("Batch has expired", r["batch_no"])
            assert any(r.get("is_finished_item") for r in self.items), "Repack thiếu thành phẩm"
            assert len({r["item_code"] for r in self.items}) == 1, "Repack trộn nhiều mã — trộn giá vốn"
        assert self.stock_entry_type == p and self.company == "RVHG" and self.custom_kiem_ke

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
C._so_lo = lambda kho, items: [F.Doc(item=i, b=b, q=q) for (i, b), q in SO_KHO.get(kho, {}).items() if i in items]
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
kiem("mã không quản lý lô: đánh dấu, xếp cuối", hang(tq, "TP-KL")["khong_lo"] and tq["hang"][-1]["item"] == "TP-KL")
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
kiem("… chuyển 2 lô cũ sang 2 lô HSD, thiếu 22; số chứng từ kho sẽ sinh = 3",
     ma["TP-SEN"]["lo_cu"] == 2 and ma["TP-SEN"]["lo_moi"] == 2 and ma["TP-SEN"]["thieu"] == 22
     and xt["tong"]["phieu_kho"] == 3, (ma["TP-SEN"], xt["tong"]))
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
kiem("CHỐT (thủ kho — D155): phiếu Đã chốt, người chốt, tổng sổ 220 → đếm 164, lệch −56",
     d["docstatus"] == 1 and d["trang_thai"] == "Đã chốt" and d["nguoi_chot"] == "kho@x"
     and (d["tong_so_sach"], d["tong_dem"], d["tong_lech"], d["so_ma"]) == (220, 164, -56, 3), kq)
ds = json.loads(d["ds_se"])
se = [F.bang("Stock Entry")[x["name"]] for x in ds]
kiem("chứng từ kho: Repack (chuyển lô) → Material Issue (thiếu) → Material Receipt (thừa)",
     [x["purpose"] for x in se] == ["Repack", "Material Issue", "Material Receipt"], [x["purpose"] for x in se])
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
     and SO[("TP-MOI", "MOI-HSD010327")] == 6, SO)
b = F.bang("Batch")
kiem("lô theo HSD mới: HSD đúng, NSX = HSD − hạn dùng, đánh dấu nhận hàng tồn cũ qua phiếu này",
     str(b["SEN-HSD180627"]["expiry_date"]) == H2 and str(b["SEN-HSD180627"]["manufacturing_date"]) == "2026-09-21"
     and b["SEN-HSD180627"]["custom_kiem_ke"] == P and b["MOI-HSD010327"]["custom_kiem_ke"] == P
     and b["SEN-HSD080627"]["custom_kiem_ke"] == P, {k: v.get("custom_kiem_ke") for k, v in b.items()})
kiem("mọi chứng từ kho gắn số phiếu kiểm kê", all(x["custom_kiem_ke"] == P for x in se))
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
     "Biên bản kiểm kê kho thành phẩm" in html and "Bánh đậu xanh sen" in html and "-56" in html
     and "SEN-HSD180627" in html and "Kế toán" in html and se[0]["name"] in html and "BẢN NHÁP" not in html)
gd = A.tong_quan()["gan_day"]
kiem("thẻ: phiếu vừa chốt vào danh sách gần đây", gd and gd[0]["name"] == P and gd[0]["tong_lech"] == -56, gd)

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
F.vai("SX Quan Ly", u="ql@x")
kiem("chốt lúc đó → không được, nói đếm lại", "ĐẾM LẠI" in (thu(lambda: A.chot(P2)) or ""))
kiem("… chốt hỏng thì phiếu vẫn đang đếm, chưa sinh chứng từ nào",
     F.bang("SX Kiem Ke")[P2]["docstatus"] == 0 and len(F.bang("Stock Entry")) == 3)
F.vai("SX Thu Kho", u="kho@x")
A.dem_lai(P2, "TP-SEN")
kiem("ĐẾM LẠI: bỏ mọi dòng của mã", not hang(A.tong_quan(), "TP-SEN")["da_dem"])
A.ghi(P2, "TP-SEN", hsd=H1, so_dem=40)
kiem("đếm lại sau chứng từ đó → hết chặn", not A.xem_truoc(P2)["loi"], A.xem_truoc(P2)["loi"])
for k in ("s1", "s2", "s3", "s4"):
    F.bang("Stock Ledger Entry").pop(k)

A.ghi(P2, "TP-SEN", hsd="2027-07-01", so_dem=3)
loi = " ".join(A.xem_truoc(P2)["loi"])
kiem("HSD của hàng làm SAU ngày áp dụng BM.08.04 mà chưa duyệt xuất xưởng → không phải tồn cũ, chặn",
     "BM.08.04" in loi and "01/07/27" in loi, loi)
A.ghi(P2, "TP-SEN", hsd="2027-06-28", so_dem=2)
kiem("… kể cả hàng làm ĐÚNG ngày áp dụng (NSX 01/10/26 = ngày áp dụng)",
     "28/06/27" in " ".join(A.xem_truoc(P2)["loi"]), A.xem_truoc(P2)["loi"])
A.ghi(P2, "TP-SEN", hsd="2027-06-28", so_dem=0, hsd_cu="2027-06-28")
XX_CAI["duyet"].add(("TP-SEN", "2027-07-01"))
kiem("đã duyệt xuất xưởng → qua", not A.xem_truoc(P2)["loi"], A.xem_truoc(P2)["loi"])
XX_CAI["duyet"].clear()
XX_CAI["bat"] = False
kiem("tắt chặn BM.08.04 ở SX Settings → qua", not A.xem_truoc(P2)["loi"])
XX_CAI["bat"] = True
A.ghi(P2, "TP-SEN", hsd="2027-07-01", so_dem=0, hsd_cu="2027-07-01")

SO[("TP-KL", None)] = 5
F.bang("Stock Ledger Entry")["k1"] = {"name": "k1", "item_code": "TP-KL", "warehouse": KHO, "actual_qty": 5,
                                      "creation": "2026-09-01 08:00:00", "modified": "2026-09-01 08:00:00", "is_cancelled": 0}
A.ghi(P2, "TP-KL", hsd=H1, so_dem=5)
kiem("mã không quản lý lô (đã có giao dịch) → chặn, nói bỏ khỏi phiếu",
     any("không quản lý theo lô" in x for x in A.xem_truoc(P2)["loi"]))
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
kiem("mã có lô mà còn tồn KHÔNG gắn lô → chặn, nói sửa trên Desk",
     any("KHÔNG gắn lô" in x and "Bánh đậu xanh sen (3)" in x for x in A.xem_truoc(P2)["loi"]), A.xem_truoc(P2)["loi"])
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
kiem("huỷ: các chứng từ kho huỷ theo thứ tự NGƯỢC (thừa → thiếu → chuyển lô)",
     [x[2] for x in SE_LOG if x[0] == "cancel"] == ["Material Receipt", "Material Issue", "Repack"], SE_LOG)
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
kiem("xem trước: hàng hết hạn vẫn đếm được, không lỗi; 3 chứng từ (Repack phần còn hạn + xuất + nhập)",
     not xt["loi"] and xt["tong"]["phieu_kho"] == 3, xt)
A.chot(P3)
se3 = [F.bang("Stock Entry")[x["name"]] for x in json.loads(F.bang("SX Kiem Ke")[P3]["ds_se"])]
kiem("chốt: Repack chỉ có phần còn hạn; lô hết hạn đi xuất + nhập — không văng \"Batch has expired\"",
     [x["purpose"] for x in se3] == ["Repack", "Material Issue", "Material Receipt"]
     and all(r["batch_no"] != "DO-HSD010926" for r in se3[0]["items"])
     and any(r["batch_no"] == "DO-HSD010926" for r in se3[2]["items"]), [(x["purpose"], x["items"]) for x in se3])
kiem("tồn sau chốt: HSD 01/09/26 (hết hạn) 10, HSD 15/03/27 25, lô cũ 40 → 5 thiếu xuất hết",
     SO[("TP-DO", "DO-HSD010926")] == 10 and SO[("TP-DO", "DO-HSD150327")] == 25 and SO[("TP-DO", "DO-150926")] == 0,
     {k: v for k, v in SO.items() if k[0] == "TP-DO"})
F.get_doc("SX Kiem Ke", P3).cancel()
kiem("huỷ phiếu đó: tồn về như trước", all(abs(SO.get(k, 0) - SO_TRUOC.get(k, 0)) < 1e-9 for k in set(SO) | set(SO_TRUOC)))

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
