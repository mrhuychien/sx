"""D226 — duyệt phiếu nhập mua / hoá đơn mua có trừ kho: tự tạo lô nguyên liệu từ ô Lô NCC.

Vì sao phải có bài này: mã nguyên liệu quản lý theo lô mà dòng hàng chưa chọn Batch No thì lúc duyệt ERPNext báo
"Serial No / Batch No are mandatory for Item …" — tiếng Anh, từng mã một. Lô tự tạo thì phải:
  · đúng số lô NCC QC đã ghi (truy xuất / thu hồi theo số in trên bao bì), NSX / HSD trên bao bì — không bịa NSX;
  · chuyến sau cùng lô NCC (cùng mã, HSD khớp) nhập VÀO lô cũ, không đẻ lô mới; trùng số lô của mã khác hoặc khác HSD
    thì lô riêng -2, -3…;
  · không đụng dòng đã chọn lô / có bundle, mã không lô, hoá đơn không trừ kho, phiếu trả hàng;
  · thiếu Lô NCC / ngày sai → báo MỘT lần đủ các dòng, và khi đã báo thì không tạo lô nào.

Nạp sx/api/lo_mua.py + sx/hooks.py THẬT trên frappe giả. Batch giả như ERPNext v16: tên = batch_id, mã phải bật lô,
NSX mặc định hôm nay, mã Has Expiry Date bắt buộc HSD (có Shelf Life thì tự tính). Duyệt giả như ERPNext: chạy
before_submit của app theo hooks.py, rồi ghi sổ kho — mã có lô mà dòng không lô / bundle → lỗi tiếng Anh như thật.
Chạy: python3 scripts/test-lomua.py   (verify.sh gọi sẵn)
"""

import json
import os
import sys
import types
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

frappe = F.cai()
LM = F.nap("sx.api.lo_mua", "sx/api/lo_mua.py")
H = F.nap("sx.hooks", "sx/hooks.py")
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-11-03")
LUC = {"n": 0}
SO_KHO = []


class LoGia(F.Document):
    def before_insert(self):
        if not getattr(self.flags, "ignore_permissions", False):     # người duyệt phiếu mua không có quyền tạo Batch
            raise frappe.PermissionError("Not permitted: Batch")
        LUC["n"] += 1
        self.creation = f"2026-11-03 10:{LUC['n'] // 60:02d}:{LUC['n'] % 60:02d}"
        if self.manufacturing_date is None:          # _set_defaults: Batch.manufacturing_date mặc định "Today"
            self.manufacturing_date = F.hom_nay()
        if self.disabled is None:
            self.disabled = 0

    def validate(self):
        it = F.bang("Item").get(self.item) or {}
        if not it.get("has_batch_no"):
            frappe.throw("The selected item cannot have Batch")
        if not self.expiry_date and it.get("has_expiry_date") and it.get("shelf_life_in_days") and self.manufacturing_date:
            self.expiry_date = F.getdate(self.manufacturing_date) + timedelta(days=it["shelf_life_in_days"])
        if it.get("has_expiry_date") and not self.expiry_date:
            frappe.throw("Expiry Date Mandatory")


def goi_hook(dt, su_kien, doc):
    """doc_events của app theo đúng thứ tự trong hooks.py (hook không thuộc bài này bỏ qua)."""
    ds = H.doc_events[dt].get(su_kien) or []
    for p in [ds] if isinstance(ds, str) else ds:
        mo, ham = p.rsplit(".", 1)
        if mo == "sx.api.lo_mua":
            getattr(LM, ham)(doc, su_kien)


class PhieuMua(F.Document):
    def before_submit(self):
        goi_hook(self.doctype, "before_submit", self)

    def on_submit(self):
        """Như ERPNext: make_bundle_using_old_serial_batch_fields + sổ kho (SLE.validate_serial_batch_no_bundle)."""
        if F.fu_cint(self.is_return) or (self.doctype == "Purchase Invoice" and not F.fu_cint(self.update_stock)):
            return
        for r in self.items or []:
            it = F.bang("Item").get(r.item_code) or {}
            if not it.get("is_stock_item") or not (float(r.get("qty") or 0) or float(r.get("rejected_qty") or 0)):
                continue
            if it.get("has_serial_no"):          # serial: luật riêng của ERPNext (tự sinh theo series) — ngoài bài này
                continue
            if r.get("from_warehouse"):          # nhận chuyển nội bộ: ERPNext lập bundle theo phiếu xuất của kho nguồn
                continue
            co = r.get("batch_no") or r.get("serial_and_batch_bundle")
            if it.get("has_batch_no") and not co and not it.get("create_new_batch"):
                raise F.Loi(f"Serial No / Batch No are mandatory for Item {r.item_code}")
            if r.get("batch_no"):
                lo = F.bang("Batch").get(r.batch_no)
                if not lo or lo["item"] != r.item_code:
                    raise F.Loi(f"Batch {r.batch_no} does not belong to Item {r.item_code}")
            SO_KHO.append((self.name, r.idx, r.item_code, r.get("batch_no")))


F.fu_cint = sys.modules["frappe.utils"].cint
F.dang_ky("Batch", LoGia, ten_theo="batch_id")
F.dang_ky("Purchase Receipt", PhieuMua)
F.dang_ky("Purchase Invoice", PhieuMua)
F.bang("Item").update({
    "Hương cốm": {"name": "Hương cốm", "has_batch_no": 1, "is_stock_item": 1},
    "Hương sen": {"name": "Hương sen", "has_batch_no": 1, "is_stock_item": 1},
    "Bột sữa": {"name": "Bột sữa", "has_batch_no": 1, "is_stock_item": 1, "create_new_batch": 0},
    "Đường kính": {"name": "Đường kính", "has_batch_no": 0, "is_stock_item": 1},
    "Men": {"name": "Men", "has_batch_no": 1, "is_stock_item": 1, "has_expiry_date": 1},
    "Bơ": {"name": "Bơ", "has_batch_no": 1, "is_stock_item": 1, "has_expiry_date": 1, "shelf_life_in_days": 180},
    "Tem tự sinh": {"name": "Tem tự sinh", "has_batch_no": 1, "is_stock_item": 1, "create_new_batch": 1},
    "Máy seri": {"name": "Máy seri", "has_batch_no": 1, "has_serial_no": 1, "is_stock_item": 1},
    "Phí lô": {"name": "Phí lô", "has_batch_no": 1, "is_stock_item": 0},
})
F.bang("Batch").update({
    "SEN-CU": {"name": "SEN-CU", "item": "Hương sen", "disabled": 0, "creation": "2026-09-01 08:00:00"},
    "M77": {"name": "M77", "item": "Hương cốm", "manufacturing_date": date(2026, 10, 1), "disabled": 0,
            "creation": "2026-10-01 08:00:00"},
    "X1": {"name": "X1", "item": "Hương sen", "disabled": 0, "creation": "2026-10-02 08:00:00"},
    "D9": {"name": "D9", "item": "Hương cốm", "disabled": 1, "creation": "2026-10-03 08:00:00"},
    "DA1": {"name": "DA1", "item": "Hương cốm", "custom_ncc_lo": "DA9", "disabled": 1, "creation": "2026-10-03 09:00:00"},
    "PF": {"name": "PF", "item": "Bột sữa", "custom_ncc_lo": "PF", "disabled": 0, "creation": "2026-10-04 08:00:00"},
    "PF-2": {"name": "PF-2", "item": "Bột sữa", "custom_ncc_lo": "PF", "expiry_date": date(2027, 12, 12), "disabled": 0,
             "creation": "2026-10-05 08:00:00"},
})
SO = {"n": 0}


def dong(item, lo=None, nsx=None, hsd=None, **k):
    r = {"item_code": item}
    if lo is not None:
        r["custom_ncc_lo"] = lo
    if nsx:
        r["custom_ncc_nsx"] = nsx
    if hsd:
        r["custom_ncc_hsd"] = hsd
    r.update(k)
    return r


def phieu(*ds, dt="Purchase Receipt", ngay="2026-11-03", **k):
    SO["n"] += 1
    ten = f"{'PR' if dt == 'Purchase Receipt' else 'PI'}-{SO['n']:03d}"
    items = [F.Doc(dict({"name": f"{ten}-{i}", "idx": i, "qty": 10, "warehouse": "Kho NVL"}, **r))
             for i, r in enumerate(ds, 1)]
    d = F.get_doc(dict({"doctype": dt, "name": ten, "supplier": "NCC-HUONG", "posting_date": ngay, "docstatus": 0,
                        "is_return": 0, "items": items}, **k))
    d.insert()
    return d


def duyet(d):
    F.BAO.clear()
    return thu(d.submit)


def lo(ten):
    return F.bang("Batch").get(ten) or {}


def dong_db(d, i):
    return F.bang(d.doctype)[d.name]["items"][i - 1]


def da_duyet(d):
    return F.bang(d.doctype)[d.name]["docstatus"] == 1


# ═══ 0. Gắn hook ═══════════════════════════════════════════════════════════
print("-- gắn hook --")
kiem("Purchase Receipt before_submit: kiểm xe trước (xe chặn thì khỏi tạo lô), rồi tạo lô",
     H.doc_events["Purchase Receipt"]["before_submit"] == ["sx.qc.kiem_xe.before_submit", "sx.api.lo_mua.tao_lo"],
     H.doc_events["Purchase Receipt"]["before_submit"])
kiem("Purchase Invoice before_submit: tạo lô (hoá đơn mua có trừ kho — đường cũ)",
     H.doc_events["Purchase Invoice"]["before_submit"] in ("sx.api.lo_mua.tao_lo", ["sx.api.lo_mua.tao_lo"]))
kiem("không móc vào validate / on_update: lưu nháp không tạo lô (phiếu nháp xoá đi không để lại lô rác)",
     all("lo_mua" not in json.dumps(H.doc_events[dt].get(e)) for dt in ("Purchase Receipt", "Purchase Invoice")
         for e in ("validate", "on_update", "before_save", "on_submit")))

# ═══ 1. Lỗi người dùng gặp: mã có lô, dòng chưa có lô ════════════════════════
print("\n-- dòng mã có lô chưa có Lô NCC: báo tiếng Việt, đủ các dòng --")
n_lo = len(F.bang("Batch"))
d = phieu(dong("Hương cốm"), dong("Đường kính"), dong("Bột sữa"), dong("Hương sen", "S1", hsd="2027-01-01"))
loi = duyet(d)
kiem("báo MỘT lần đủ các dòng thiếu lô (tiếng Việt), không phải lỗi tiếng Anh từng mã",
     loi and "Chưa có số lô cho các dòng: 1 (Hương cốm), 3 (Bột sữa)." in loi and "mandatory" not in loi, loi)
kiem("… chỉ cách sửa: ghi số lô trên bao bì vào ô Lô NCC (màn Tiếp nhận NL hoặc trên dòng), hoặc chọn Batch No",
     "ô <b>Lô NCC</b>" in loi and "Tiếp nhận NL" in loi and "Batch No" in loi)
kiem("… mã không lô (đường) không bị kể; dòng đủ (Hương sen S1) cũng KHÔNG tạo lô — một dòng hỏng là chưa tạo gì",
     "Đường kính" not in loi and len(F.bang("Batch")) == n_lo and not da_duyet(d))
d = phieu(dong("Hương cốm"))
kiem("một dòng → 'dòng' (không 'các dòng')", "Chưa có số lô cho dòng: 1 (Hương cốm)." in (duyet(d) or ""))

# ═══ 2. Tạo lô theo Lô NCC ═══════════════════════════════════════════════════
print("\n-- có Lô NCC: tạo lô đúng số lô, NSX / HSD trên bao bì --")
d = phieu(dong("Hương cốm", "HC-2409", nsx="2026-09-24", hsd="2027-09-24"), dong("Đường kính"),
          dong("Hương sen", batch_no="SEN-CU"), dong("Bột sữa", serial_and_batch_bundle="SABB-0001"))
loi = duyet(d)
b = lo("HC-2409")
kiem("duyệt được (ERPNext không còn báo thiếu lô)", loi is None and da_duyet(d), loi)
kiem("lô tên = số lô NCC, đúng mã, NSX / HSD trên bao bì, NCC + chứng từ nguồn, ô Lô NCC của lô",
     (b.get("item"), b.get("manufacturing_date"), b.get("expiry_date"), b.get("supplier"), b.get("reference_doctype"),
      b.get("reference_name"), b.get("custom_ncc_lo"))
     == ("Hương cốm", date(2026, 9, 24), date(2027, 9, 24), "NCC-HUONG", "Purchase Receipt", d.name, "HC-2409"), b)
kiem("dòng mang lô vừa tạo, bật 'dùng ô Batch No' (ERPNext lập bundle từ ô này) — lưu cả vào phiếu",
     (dong_db(d, 1).get("batch_no"), dong_db(d, 1).get("use_serial_batch_fields")) == ("HC-2409", 1))
kiem("không đụng: mã không lô, dòng đã chọn lô, dòng đã có bundle",
     not dong_db(d, 2).get("batch_no") and dong_db(d, 3).get("batch_no") == "SEN-CU"
     and not dong_db(d, 4).get("batch_no") and not dong_db(d, 4).get("use_serial_batch_fields"))
kiem("sổ kho ghi đúng lô từng dòng", [x for x in SO_KHO if x[0] == d.name] == [
    (d.name, 1, "Hương cốm", "HC-2409"), (d.name, 2, "Đường kính", None), (d.name, 3, "Hương sen", "SEN-CU"),
    (d.name, 4, "Bột sữa", None)])
kiem("báo lại lô đã gán (tạo mới)", any("dòng 1 (Hương cốm): lô <b>HC-2409</b> — tạo mới" in m for m in F.BAO), F.BAO)

print("\n-- chuyến sau: cùng lô NCC → nhập vào lô cũ; trùng số mà khác mã / khác HSD → lô riêng --")
n_lo = len(F.bang("Batch"))
d = phieu(dong("Hương cốm", "HC-2409", hsd="2027-09-24"))
kiem("cùng mã + cùng số lô NCC + cùng HSD → nhập thêm vào lô cũ, không tạo lô mới",
     duyet(d) is None and dong_db(d, 1)["batch_no"] == "HC-2409" and len(F.bang("Batch")) == n_lo
     and any("lô <b>HC-2409</b> — nhập thêm vào lô đã có" in m for m in F.BAO), F.BAO)
d = phieu(dong("Hương sen", "HC-2409", hsd="2027-06-30"))
loi = duyet(d)
b = lo("HC-2409-2")
kiem("số lô trùng lô của MÃ KHÁC → lô riêng 'HC-2409-2' (ô Lô NCC giữ số gốc); không NSX → NSX để trống, không bịa "
     "ngày nhận", loi is None and dong_db(d, 1)["batch_no"] == "HC-2409-2"
     and (b.get("item"), b.get("custom_ncc_lo"), b.get("expiry_date"), b.get("manufacturing_date"))
     == ("Hương sen", "HC-2409", date(2027, 6, 30), None), b)
d = phieu(dong("Hương sen", "HC-2409", nsx="2026-06-30"))
kiem("… chuyến sau của Hương sen cùng lô NCC (không ghi HSD) → tìm ra đúng 'HC-2409-2' qua ô Lô NCC của lô; NSX lô "
     "đang trống thì điền", duyet(d) is None and dong_db(d, 1)["batch_no"] == "HC-2409-2"
     and lo("HC-2409-2")["manufacturing_date"] == date(2026, 6, 30), lo("HC-2409-2"))
d = phieu(dong("Hương cốm", "HC-2409", hsd="2028-01-15"))
kiem("cùng mã, cùng số lô NCC mà KHÁC HSD (NCC quay vòng số lô) → lô mới 'HC-2409-3'",
     duyet(d) is None and dong_db(d, 1)["batch_no"] == "HC-2409-3" and lo("HC-2409-3")["expiry_date"] == date(2028, 1, 15))
for hsd, mong in ((None, "HC-2409"), ("2027-09-24", "HC-2409"), ("2028-01-15", "HC-2409-3")):
    d = phieu(dong("Hương cốm", "HC-2409", hsd=hsd))
    kiem(f"… lần sau HSD {hsd or 'trống'} → lô {mong} (khớp HSD trước, không có thì lô cũ nhất)",
         duyet(d) is None and dong_db(d, 1)["batch_no"] == mong, dong_db(d, 1).get("batch_no"))

print("\n-- lô tạo tay trên Desk --")
d = phieu(dong("Hương cốm", "M77", nsx="2026-09-01", hsd="2027-03-01"))
loi = duyet(d)
b = lo("M77")
kiem("lô tạo tay đặt tên đúng số lô NCC → nhập vào đó; điền HSD + ô Lô NCC còn trống, NSX đã có thì giữ",
     loi is None and dong_db(d, 1)["batch_no"] == "M77"
     and (b.get("expiry_date"), b.get("custom_ncc_lo"), b.get("manufacturing_date"))
     == (date(2027, 3, 1), "M77", date(2026, 10, 1)), b)
d = phieu(dong("Hương cốm", "X1"))
kiem("tên đã là lô tạo tay của mã khác → 'X1-2'", duyet(d) is None and dong_db(d, 1)["batch_no"] == "X1-2"
     and lo("X1-2")["item"] == "Hương cốm" and lo("X1")["item"] == "Hương sen")
d = phieu(dong("Hương cốm", "D9"), dong("Hương cốm", "DA9"))
kiem("lô đã tắt (Disabled) — lô tạo tay cùng tên, hay lô app tạo có ô Lô NCC đó — không nhập vào: 'D9-2', 'DA9'",
     duyet(d) is None and (dong_db(d, 1)["batch_no"], dong_db(d, 2)["batch_no"]) == ("D9-2", "DA9"))
d = phieu(dong("Bột sữa", "PF", hsd="2027-12-12"))
kiem("lô khớp đúng HSD được chọn trước lô chưa có HSD (dù lô kia cũ hơn) — không dồn hai HSD vào một lô",
     duyet(d) is None and dong_db(d, 1)["batch_no"] == "PF-2" and not lo("PF").get("expiry_date"))

print("\n-- trong một phiếu --")
n_lo = len(F.bang("Batch"))
d = phieu(dong("Bột sữa", "BS1", hsd="2027-02-02"), dong("Bột sữa", "BS1", hsd="2027-02-02", qty=5))
kiem("hai dòng cùng mã + cùng lô NCC + cùng HSD → MỘT lô, cả hai dòng mang lô đó",
     duyet(d) is None and dong_db(d, 1)["batch_no"] == dong_db(d, 2)["batch_no"] == "BS1"
     and len(F.bang("Batch")) == n_lo + 1
     and any("dòng 1 (Bột sữa): lô <b>BS1</b> — tạo mới" in m and "dòng 2 (Bột sữa): lô <b>BS1</b> — nhập thêm" in m
             for m in F.BAO), F.BAO)
d = phieu(dong("Hương cốm", "  AB  12<x> "))
kiem("số lô gõ thừa khoảng trắng / ký tự Frappe cấm (< >) → tên lô sạch, ô Lô NCC của lô cũng sạch",
     duyet(d) is None and dong_db(d, 1)["batch_no"] == "AB 12 x" and lo("AB 12 x")["custom_ncc_lo"] == "AB 12 x")
d = phieu(dong("Hương cốm", "Z" * 140), dong("Hương sen", "Z" * 140))
kiem("số lô 140 ký tự → tên lô 130 + hậu tố vẫn ≤ 140", duyet(d) is None and dong_db(d, 1)["batch_no"] == "Z" * 130
     and dong_db(d, 2)["batch_no"] == "Z" * 130 + "-2")

# ═══ 3. Ngày của lô NCC ══════════════════════════════════════════════════════
print("\n-- NSX / HSD sai: báo đủ, không tạo lô --")
n_lo = len(F.bang("Batch"))
d = phieu(dong("Hương cốm", "E1", hsd="2026-11-02"), dong("Hương sen", "E2", nsx="2027-09-24", hsd="2026-09-24"),
          dong("Bột sữa", "E3", nsx="2026-11-04", hsd="2027-11-04"), dong("Men", "E4"), dong("Bơ", "E5"),
          dong("Hương cốm", "E6", hsd="2026-11-03"), dong("Hương sen", "E7", nsx="2026-11-03", hsd="2026-11-03"),
          dong("Bột sữa", "E8", nsx="2026-11-03", hsd="2027-11-03"))
loi = duyet(d) or ""
kiem("HSD trước ngày nhập (hàng đã hết hạn) → chặn như ERPNext", "dòng 1 (Hương cốm): HSD 02/11/2026 đã qua ngày nhập "
     "03/11/2026" in loi, loi)
kiem("HSD không sau NSX (gõ đảo hai ô) → nói đúng chỗ sai, không chỉ 'đã qua ngày nhập'",
     "dòng 2 (Hương sen): HSD 24/09/2026 không sau NSX 24/09/2027 — gõ đảo hai ô?" in loi)
kiem("NSX sau ngày nhập → chặn", "dòng 3 (Bột sữa): NSX 04/11/2026 sau ngày nhập 03/11/2026" in loi)
kiem("HSD = NSX → chặn", "dòng 7 (Hương sen): HSD 03/11/2026 không sau NSX 03/11/2026" in loi)
kiem("mã bắt HSD (Has Expiry Date, không Shelf Life) mà chưa ghi HSD → chặn trước khi ERPNext báo tiếng Anh",
     "dòng 4 (Men): mã bắt buộc HSD" in loi)
kiem("… mã có Shelf Life (ERPNext tự tính HSD) và HSD đúng ngày nhập thì không kể; chưa tạo lô nào",
     "(Bơ)" not in loi and "dòng 6" not in loi and "dòng 8" not in loi and len(F.bang("Batch")) == n_lo
     and "Sửa ô NSX / HSD lô NCC" in loi, loi)
d = phieu(dong("Bơ", "E5"), dong("Hương cốm", "E6", hsd="2026-11-03"), dong("Bột sữa", "E8", nsx="2026-11-03",
                                                                            hsd="2027-11-03"))
kiem("Bơ: ERPNext tự tính HSD = NSX mặc định + 180 ngày; ô NSX của lô vẫn để trống (không bịa); HSD = ngày nhập, NSX "
     "= ngày nhập vẫn nhận", duyet(d) is None
     and (lo("E5").get("expiry_date"), lo("E5").get("manufacturing_date")) == (date(2027, 5, 2), None)
     and (dong_db(d, 2)["batch_no"], dong_db(d, 3)["batch_no"]) == ("E6", "E8"), lo("E5"))
ten, moi = LM.lo_cho(F.Doc(doctype="Purchase Receipt", name="PR-CHUA-LUU", supplier="NCC-HUONG"), "Hương cốm", "API1")
kiem("lập + duyệt một lượt (phiếu chưa vào DB): vẫn tạo lô, chỉ không gắn chứng từ nguồn (Frappe chặn link chưa có)",
     (ten, moi, lo("API1").get("reference_name"), lo("API1").get("supplier")) == ("API1", True, None, "NCC-HUONG"),
     lo("API1"))
r = {"custom_ncc_nsx": "2026-01-01", "custom_ncc_hsd": "2027-01-01"}
kiem("kiem_ngay (hàm thuần): ngày ổn → None; thiếu ngày nhập thì không xét quá hạn",
     LM.kiem_ngay(r, {}, date(2026, 11, 3)) is None and LM.kiem_ngay({"custom_ncc_hsd": "2020-01-01"}, {}, None) is None)

# ═══ 4. Chứng từ / dòng không xét ═════════════════════════════════════════════
print("\n-- chứng từ / dòng không xét --")
n_lo = len(F.bang("Batch"))
d = phieu(dong("Hương cốm"), dong("Hương cốm", "PI0"), dt="Purchase Invoice", update_stock=0)
kiem("hoá đơn mua KHÔNG trừ kho → không đòi lô, không tạo lô", duyet(d) is None and len(F.bang("Batch")) == n_lo
     and not dong_db(d, 2).get("batch_no"))
d = phieu(dong("Hương cốm", "PI1", hsd="2027-04-04"), dt="Purchase Invoice", update_stock=1)
kiem("hoá đơn mua CÓ trừ kho → tạo lô như phiếu nhập (chứng từ nguồn = hoá đơn)", duyet(d) is None
     and dong_db(d, 1)["batch_no"] == "PI1" and lo("PI1")["reference_doctype"] == "Purchase Invoice")
d = phieu(dong("Hương cốm", "TRA"), dong("Bột sữa"), is_return=1)
kiem("phiếu trả hàng NCC → không đụng (lô lấy theo phiếu gốc)", duyet(d) is None and "TRA" not in F.bang("Batch"))
d = phieu(dong("Tem tự sinh"), dong("Máy seri"), dong("Phí lô"), dong("Hương cốm", qty=0),
          dong("Hương cốm", from_warehouse="Kho khác"))
kiem("không kể: mã ERPNext tự sinh lô, mã có serial, mã không giữ kho, dòng số lượng 0, dòng nhận chuyển nội bộ",
     duyet(d) is None, F.BAO)
d = phieu(dong("Hương cốm", qty=0, rejected_qty=3))
kiem("dòng chỉ có số lượng trả lại (rejected) vẫn vào kho → vẫn phải có lô", "1 (Hương cốm)" in (duyet(d) or ""))
_gv = frappe.db.get_value


def _gv_nhu_frappe(dt, ten, *a, **k):
    """frappe.db.get_value(dt, None, …) KHÔNG trả None: không bộ lọc = bản ghi đầu bảng."""
    if dt == "Item" and ten is None:
        ten = "Hương cốm"
    return _gv(dt, ten, *a, **k)


frappe.db.get_value = _gv_nhu_frappe
d = phieu(dong(None, description="Cước vận chuyển"), dong("Hương cốm", "PI2"), dt="Purchase Invoice", update_stock=1)
kiem("hoá đơn mua có dòng chi phí không mã hàng (chỉ diễn giải) → bỏ qua dòng đó, không tra nhầm mã khác",
     duyet(d) is None and not dong_db(d, 1).get("batch_no") and dong_db(d, 2)["batch_no"] == "PI2", F.BAO)
frappe.db.get_value = _gv
kiem("can_lo (hàm thuần): không có cờ mã → không xét", LM.can_lo({"qty": 1}, {}) is False
     and LM.can_lo({"qty": 1}, None) is False)
kiem("nhap_kho: phiếu nhập mua luôn; hoá đơn chỉ khi trừ kho; trả hàng không",
     LM.nhap_kho(F.Doc(doctype="Purchase Receipt")) and not LM.nhap_kho(F.Doc(doctype="Purchase Invoice"))
     and LM.nhap_kho(F.Doc(doctype="Purchase Invoice", update_stock=1))
     and not LM.nhap_kho(F.Doc(doctype="Purchase Receipt", is_return=1)))

# ═══ 5. Site chưa migrate D226 ════════════════════════════════════════════════
print("\n-- site chưa migrate (Batch chưa có ô Lô NCC) --")
_meta, _ga = frappe.get_meta, frappe.get_all
frappe.get_meta = lambda dt: types.SimpleNamespace(has_field=lambda f: dt != "Batch")


def _ga_chua_migrate(dt, filters=None, fields=None, **k):
    """Như MariaDB: lọc / đọc cột chưa có → lỗi SQL."""
    if dt == "Batch" and "custom_ncc_lo" in json.dumps([filters, fields], default=str):
        raise RuntimeError("(1054, \"Unknown column 'custom_ncc_lo' in 'where clause'\")")
    return _ga(dt, filters, fields, **k)


def _gv_chua_migrate(dt, ten, fld=None, *a, **k):
    if dt == "Batch" and "custom_ncc_lo" in json.dumps([ten, fld], default=str):
        raise RuntimeError("(1054, \"Unknown column 'custom_ncc_lo' in 'field list'\")")
    return _gv(dt, ten, fld, *a, **k)


frappe.get_all, frappe.db.get_value = _ga_chua_migrate, _gv_chua_migrate
d = phieu(dong("Hương cốm", "HC-2409", hsd="2027-09-24"), dong("Hương cốm", "NM1"))
kiem("vẫn duyệt được: tìm lô theo tên (HC-2409), lô mới không ghi ô Lô NCC chưa có",
     duyet(d) is None and dong_db(d, 1)["batch_no"] == "HC-2409" and dong_db(d, 2)["batch_no"] == "NM1"
     and "custom_ncc_lo" not in lo("NM1"), lo("NM1"))
frappe.get_meta = lambda dt: (_ for _ in ()).throw(RuntimeError("meta hỏng"))
kiem("… đọc meta lỗi → coi như chưa có ô, không văng lỗi", LM._co_o_lo_ncc() is False)
frappe.get_meta, frappe.get_all, frappe.db.get_value = _meta, _ga, _gv

# ═══ 6. Tài liệu ═════════════════════════════════════════════════════════════
print("\n-- fixtures, README --")
fx = {f["name"]: f for f in json.load(open("sx/fixtures/custom_field.json", encoding="utf-8"))}
b = fx.get("Batch-custom_ncc_lo") or {}
kiem("Batch có ô Lô NCC (chỉ đọc, đánh chỉ mục, không chép khi nhân bản) — module trong bộ lọc fixtures",
     (b.get("fieldtype"), b.get("read_only"), b.get("search_index"), b.get("no_copy"), b.get("module"))
     == ("Data", 1, 1, 1, "SX"), b)
rd = open("README.md", encoding="utf-8").read()
kiem("README: mục D226 + 'Còn phải làm tay' không còn bắt tạo lô tay", "(D226)" in rd
     and "Purchase Receipt NVL phải có batch = lô NCC (điều kiện FIFO truy xuất)" not in rd)

F.ket_thuc("LOMUA")
