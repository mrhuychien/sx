"""D226 / D227 — duyệt phiếu nhập mua / hoá đơn mua có trừ kho: tự tạo lô nguyên liệu, mã {NCC}-{mã hàng}-{ngày nhập}.

Vì sao phải có bài này: mã nguyên liệu quản lý theo lô mà dòng hàng chưa chọn Batch No thì lúc duyệt ERPNext báo
"Serial No / Batch No are mandatory for Item …" — tiếng Anh, từng mã một. Lô tự tạo thì phải:
  · mã lô đọc ra được của ai, hàng gì, về ngày nào: viết tắt NCC + prefix mã hàng + DDMMYY ngày nhập; viết tắt / prefix
    giữ ổn định (lưu lại, sửa được), hai NCC / hai mã trùng chữ thì cái sau thêm số;
  · cùng NCC + mã + ngày, cùng lô NCC / HSD (hoặc chưa ghi) → nhập vào lô đó; khác lô NCC / HSD → lô riêng -2, -3…;
  · số lô NCC, NSX / HSD trên bao bì vào lô — không bịa NSX;
  · không đụng dòng đã chọn lô / có bundle, mã không lô, hoá đơn không trừ kho, phiếu trả hàng;
  · NSX / HSD sai → báo MỘT lần đủ các dòng, và khi đã báo thì không tạo lô nào.

Nạp sx/api/lo_mua.py, sx/utils.py, sx/hooks.py THẬT trên frappe giả. Batch giả như ERPNext v16: tên = batch_id, mã phải
bật lô, NSX mặc định hôm nay, mã Has Expiry Date bắt buộc HSD (có Shelf Life thì tự tính), người duyệt không có quyền tạo
Batch. Duyệt giả như ERPNext: chạy before_submit của app theo hooks.py, rồi ghi sổ kho — mã có lô mà dòng không lô /
bundle → lỗi tiếng Anh như thật.
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
U = F.nap("sx.utils", "sx/utils.py")
LM = F.nap("sx.api.lo_mua", "sx/api/lo_mua.py")
H = F.nap("sx.hooks", "sx/hooks.py")
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-11-03")
LUC = {"n": 0}
SO_KHO = []
cint = sys.modules["frappe.utils"].cint


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
        if cint(self.is_return) or (self.doctype == "Purchase Invoice" and not cint(self.update_stock)):
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


F.dang_ky("Batch", LoGia, ten_theo="batch_id")
F.dang_ky("Purchase Receipt", PhieuMua)
F.dang_ky("Purchase Invoice", PhieuMua)
F.bang("Item").update({k: dict({"name": k, "has_batch_no": 1, "is_stock_item": 1}, **v) for k, v in {
    "Hương cốm": {}, "Hương sen": {}, "Bột sữa": {}, "Hạt chia": {}, "Cốm xanh": {"custom_batch_prefix": "COM"},
    "Đường kính": {"has_batch_no": 0},
    "Men": {"has_expiry_date": 1},
    "Bơ": {"has_expiry_date": 1, "shelf_life_in_days": 180},
    "Tem tự sinh": {"create_new_batch": 1},
    "Máy seri": {"has_serial_no": 1},
    "Phí lô": {"is_stock_item": 0},
}.items()})
F.bang("Supplier").update({
    "NCC-HUONG": {"name": "NCC-HUONG", "supplier_name": "Công ty TNHH Hương liệu ABC"},
    "NCC-SEN": {"name": "NCC-SEN", "supplier_name": "Cơ sở Sen Hồ Tây", "custom_viet_tat": "s.h t"},
    "NCC-TRUNG": {"name": "NCC-TRUNG", "supplier_name": "Hương Liệu Á Bắc Cường"},
    "NCC-HOA": {"name": "NCC-HOA", "supplier_name": "CÔNG TY TNHH HƯƠNG LIỆU XYZ"},
    "NCC-MOI": {"name": "NCC-MOI", "supplier_name": "Công ty Gia vị Nam Á"},
    "NCC-DAI": {"name": "NCC-DAI", "supplier_name": "Công ty TNHH Nông sản Thực phẩm Miền Bắc Việt Nam"},
    "NCC-DAI2": {"name": "NCC-DAI2", "supplier_name": "Nông Sản Thực Phẩm Miền Bắc Việt Nam Mới"},
})
F.bang("Batch").update({
    "SEN-CU": {"name": "SEN-CU", "item": "Hương sen", "disabled": 0, "creation": "2026-09-01 08:00:00"},
    "SHT-HS-031126": {"name": "SHT-HS-031126", "item": "Hương sen", "disabled": 1, "creation": "2026-11-03 07:00:00"},
    "HLABC-BS-041126": {"name": "HLABC-BS-041126", "item": "Hương cốm", "disabled": 0, "creation": "2026-11-01 07:00:00"},
    # lô tạo tay mang tên giống họ lô mà không phải goc / goc-N — không được coi là cùng lô
    "HLABC-HC-031126-X": {"name": "HLABC-HC-031126-X", "item": "Hương cốm", "disabled": 0,
                          "creation": "2026-11-01 07:00:00"},
    "SHT-HC-031126-12": {"name": "SHT-HC-031126-12", "item": "Hương cốm", "custom_ncc_lo": "Z12", "disabled": 0,
                         "creation": "2026-11-01 07:00:00"},
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


def phieu(*ds, dt="Purchase Receipt", ngay="2026-11-03", ncc="NCC-HUONG", **k):
    SO["n"] += 1
    ten = f"{'PR' if dt == 'Purchase Receipt' else 'PI'}-{SO['n']:03d}"
    items = [F.Doc(dict({"name": f"{ten}-{i}", "idx": i, "qty": 10, "warehouse": "Kho NVL"}, **r))
             for i, r in enumerate(ds, 1)]
    d = F.get_doc(dict({"doctype": dt, "name": ten, "supplier": ncc, "posting_date": ngay, "docstatus": 0,
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

# ═══ 1. Viết tắt NCC (hàm thuần) ═════════════════════════════════════════════
print("\n-- viết tắt tên NCC --")
for ten, mong in (("Công ty TNHH Hương liệu ABC", "HLABC"), ("Công ty CP Thực phẩm Á Châu", "TPAC"),
                  ("Công ty TNHH Thương mại và Dịch vụ Minh Phát", "MP"), ("Vinamilk", "VINAMILK"),
                  ("CÔNG TY TNHH HƯƠNG LIỆU XYZ", "HLX"), ("Hộ kinh doanh Nguyễn Văn A", "NVA"),
                  ("Cơ sở Đỗ xanh Bà Hai", "DXBH"), ("Công ty 3A Food", "3AF"), ("Cơ sở Bột mì 79", "BM79"),
                  ("Công ty Hương liệu VN", "HLVN"),
                  ("Công ty TNHH Nông sản Thực phẩm Miền Bắc Việt Nam", "NSTPMBVN"),
                  ("Công ty TNHH Nông sản Thực phẩm Xuất khẩu Miền Bắc Việt Nam", "NSTPXKMB"), ("", "")):
    kiem(f"'{ten}' → '{mong}'", LM.rut_gon_ncc(ten) == mong, LM.rut_gon_ncc(ten))
kiem("tên chỉ có chữ loại hình ('Công ty TNHH') → vẫn ra chữ, không rỗng", bool(LM.rut_gon_ncc("Công ty TNHH")))
kiem("không có NCC → 'NCC'", LM.viet_tat_ncc(None) == "NCC")

# ═══ 2. Tạo lô ════════════════════════════════════════════════════════════════
print("\n-- duyệt: tạo lô {NCC}-{mã hàng}-{ngày nhập} --")
d = phieu(dong("Hương cốm", " L2409 ", nsx="2026-09-24", hsd="2027-09-24"), dong("Đường kính"),
          dong("Hương sen", batch_no="SEN-CU"), dong("Bột sữa", serial_and_batch_bundle="SABB-0001"), dong("Bột sữa"))
loi = duyet(d)
b = lo("HLABC-HC-031126")
kiem("duyệt được (ERPNext không còn báo thiếu lô) — không cần ghi số lô NCC", loi is None and da_duyet(d), loi)
kiem("mã lô = viết tắt NCC (rút gọn tên) + prefix mã hàng (rút gọn mã) + DDMMYY ngày nhập",
     dong_db(d, 1).get("batch_no") == "HLABC-HC-031126" and dong_db(d, 5).get("batch_no") == "HLABC-BS-031126",
     [dong_db(d, i).get("batch_no") for i in (1, 5)])
kiem("viết tắt NCC / prefix mã hàng LƯU lại (lần sau ra đúng chữ đó, sửa được trên Desk)",
     (F.bang("Supplier")["NCC-HUONG"].get("custom_viet_tat"), F.bang("Item")["Hương cốm"].get("custom_batch_prefix"))
     == ("HLABC", "HC"))
kiem("lô ghi số lô NCC (gộp khoảng trắng), NSX / HSD trên bao bì, NCC, chứng từ nguồn",
     (b.get("item"), b.get("custom_ncc_lo"), b.get("manufacturing_date"), b.get("expiry_date"), b.get("supplier"),
      b.get("reference_doctype"), b.get("reference_name"))
     == ("Hương cốm", "L2409", date(2026, 9, 24), date(2027, 9, 24), "NCC-HUONG", "Purchase Receipt", d.name), b)
kiem("dòng không ghi gì vẫn có lô; NSX để trống (không bịa ngày nhận), không có số lô NCC",
     (lo("HLABC-BS-031126").get("manufacturing_date"), lo("HLABC-BS-031126").get("custom_ncc_lo")) == (None, None))
kiem("dòng mang lô vừa tạo, bật 'dùng ô Batch No' (ERPNext lập bundle từ ô này) — lưu cả vào phiếu",
     dong_db(d, 1).get("use_serial_batch_fields") == 1)
kiem("không đụng: mã không lô, dòng đã chọn lô, dòng đã có bundle",
     not dong_db(d, 2).get("batch_no") and dong_db(d, 3).get("batch_no") == "SEN-CU"
     and not dong_db(d, 4).get("batch_no") and not dong_db(d, 4).get("use_serial_batch_fields"))
kiem("sổ kho ghi đúng lô từng dòng", [x for x in SO_KHO if x[0] == d.name] == [
    (d.name, 1, "Hương cốm", "HLABC-HC-031126"), (d.name, 2, "Đường kính", None), (d.name, 3, "Hương sen", "SEN-CU"),
    (d.name, 4, "Bột sữa", None), (d.name, 5, "Bột sữa", "HLABC-BS-031126")])
kiem("báo lại lô đã gán", any("dòng 1 (Hương cốm): lô <b>HLABC-HC-031126</b> — tạo mới" in m for m in F.BAO), F.BAO)

print("\n-- cùng NCC + mã + ngày: một lô; khác lô NCC / HSD: lô riêng --")
n_lo = len(F.bang("Batch"))
d = phieu(dong("Hương cốm", "l2409", hsd="2027-09-24"), dong("Hương cốm"))
kiem("chuyến sau cùng ngày, cùng số lô NCC (khác hoa / thường) + cùng HSD → nhập vào lô đó; dòng không ghi gì cũng vậy",
     duyet(d) is None and dong_db(d, 1)["batch_no"] == dong_db(d, 2)["batch_no"] == "HLABC-HC-031126"
     and len(F.bang("Batch")) == n_lo
     and any("dòng 2 (Hương cốm): lô <b>HLABC-HC-031126</b> — nhập thêm vào lô đã có" in m for m in F.BAO), F.BAO)
d = phieu(dong("Hương cốm", "L2410"))
kiem("cùng ngày mà KHÁC số lô NCC → lô riêng '-2' (giữ số lô NCC của nó)", duyet(d) is None
     and dong_db(d, 1)["batch_no"] == "HLABC-HC-031126-2" and lo("HLABC-HC-031126-2")["custom_ncc_lo"] == "L2410")
d = phieu(dong("Hương cốm", "L2409", hsd="2028-01-01"))
kiem("cùng số lô NCC mà KHÁC HSD → lô riêng '-3'", duyet(d) is None and dong_db(d, 1)["batch_no"] == "HLABC-HC-031126-3")
d = phieu(dong("Hương cốm", "L2410", hsd="2027-10-10"))
kiem("… chuyến sau của lô NCC thứ hai → đúng lô '-2', điền HSD còn trống", duyet(d) is None
     and dong_db(d, 1)["batch_no"] == "HLABC-HC-031126-2" and lo("HLABC-HC-031126-2")["expiry_date"] == date(2027, 10, 10))
d = phieu(dong("Hương cốm", "L2409", hsd="2027-09-24"), ngay="2026-11-04")
kiem("khác NGÀY nhập (dù cùng NCC, mã, lô NCC) → lô của ngày đó", duyet(d) is None
     and dong_db(d, 1)["batch_no"] == "HLABC-HC-041126")
F.bang("Batch")["HLABC-BS-031126-2"] = {"name": "HLABC-BS-031126-2", "item": "Bột sữa", "custom_ncc_lo": "PF",
                                        "expiry_date": date(2027, 12, 12), "disabled": 0,
                                        "creation": "2026-11-03 23:00:00"}
d = phieu(dong("Bột sữa", "PF", nsx="2026-10-01", hsd="2027-12-12"))
kiem("lô khớp hẳn (cùng lô NCC + HSD) được chọn trước lô cũ hơn khớp nhờ ô trống — không dồn hai lô NCC vào một",
     duyet(d) is None and dong_db(d, 1)["batch_no"] == "HLABC-BS-031126-2"
     and not lo("HLABC-BS-031126").get("expiry_date") and lo("HLABC-BS-031126-2")["manufacturing_date"] == date(2026, 10, 1))
d = phieu(dong("Bột sữa", "BS9", hsd="2027-02-02"))
kiem("lô cũ chưa có số lô NCC / HSD khớp mọi dòng → nhập vào, điền số lô NCC + HSD", duyet(d) is None
     and dong_db(d, 1)["batch_no"] == "HLABC-BS-031126"
     and (lo("HLABC-BS-031126")["custom_ncc_lo"], lo("HLABC-BS-031126")["expiry_date"]) == ("BS9", date(2027, 2, 2)))
d = phieu(dong("Bột sữa"), ngay="2026-11-04")
kiem("tên đã là lô của MÃ KHÁC (lô tạo tay) → '-2'", duyet(d) is None and dong_db(d, 1)["batch_no"] == "HLABC-BS-041126-2"
     and lo("HLABC-BS-041126")["item"] == "Hương cốm")
d = phieu(dong("Hương sen"), ncc="NCC-SEN")
kiem("NCC có sẵn viết tắt (gõ 's.h t') → dùng, chỉ lấy chữ / số viết hoa; không ghi đè ô của NCC; lô cùng tên đã tắt "
     "(Disabled) → '-2'", duyet(d) is None and dong_db(d, 1)["batch_no"] == "SHT-HS-031126-2"
     and F.bang("Supplier")["NCC-SEN"]["custom_viet_tat"] == "s.h t")
d = phieu(dong("Hương cốm", "Z12"), ncc="NCC-SEN")
kiem("lô hậu tố hai chữ số (-12) vẫn là cùng họ lô → nhập vào đúng lô cùng số lô NCC",
     duyet(d) is None and dong_db(d, 1)["batch_no"] == "SHT-HC-031126-12")
d = phieu(dong("Hương cốm"), ncc="NCC-DAI")
d2 = phieu(dong("Hương cốm"), ncc="NCC-DAI2")
kiem("viết tắt dài đủ 8 chữ mà trùng → NCC sau cắt bớt rồi thêm số, vẫn 8 chữ ('NSTPMBV2')",
     duyet(d) is None and duyet(d2) is None and dong_db(d2, 1)["batch_no"] == "NSTPMBV2-HC-031126"
     and dong_db(d, 1)["batch_no"] == "NSTPMBVN-HC-031126", dong_db(d2, 1).get("batch_no"))
d = phieu(dong("Hương cốm"), ncc="NCC-TRUNG")
kiem("hai NCC rút gọn trùng chữ (Hương Liệu Á Bắc Cường cũng ra HLABC) → NCC sau thêm số, lưu lại",
     duyet(d) is None and dong_db(d, 1)["batch_no"] == "HLABC2-HC-031126"
     and F.bang("Supplier")["NCC-TRUNG"]["custom_viet_tat"] == "HLABC2")
d = phieu(dong("Hạt chia"), dong("Cốm xanh"), dong("Tem tự sinh"), ncc="NCC-HOA")
kiem("hai mã rút gọn trùng chữ (Hạt chia / Hương cốm) → mã sau 'HC2'; prefix có sẵn (COM) dùng luôn; mã ERPNext tự "
     "sinh lô cũng đặt tên theo cách này; tên NCC gõ toàn chữ hoa → chữ đầu", duyet(d) is None
     and [dong_db(d, i)["batch_no"] for i in (1, 2, 3)] == ["HLX-HC2-031126", "HLX-COM-031126", "HLX-TTS-031126"],
     [dong_db(d, i).get("batch_no") for i in (1, 2, 3)])
n_lo = len(F.bang("Batch"))
d = phieu(dong("Hương sen", "Q1", hsd="2027-03-03"), dong("Hương sen", "Q1", hsd="2027-03-03", qty=5),
          dong("Hương sen", "Q2"), ncc="NCC-HOA")
kiem("trong một phiếu: hai dòng cùng lô NCC + HSD → một lô; dòng lô NCC khác → '-2'", duyet(d) is None
     and [dong_db(d, i)["batch_no"] for i in (1, 2, 3)] == ["HLX-HS-031126", "HLX-HS-031126", "HLX-HS-031126-2"]
     and len(F.bang("Batch")) == n_lo + 2, [dong_db(d, i).get("batch_no") for i in (1, 2, 3)])

# ═══ 3. Ngày của lô NCC ══════════════════════════════════════════════════════
print("\n-- NSX / HSD sai: báo đủ, không tạo lô --")
n_lo = len(F.bang("Batch"))
d = phieu(dong("Hương cốm", hsd="2026-11-02"), dong("Hương sen", nsx="2027-09-24", hsd="2026-09-24"),
          dong("Bột sữa", nsx="2026-11-04", hsd="2027-11-04"), dong("Men"), dong("Bơ"),
          dong("Hương cốm", hsd="2026-11-03"), dong("Hương sen", nsx="2026-11-03", hsd="2026-11-03"),
          dong("Bột sữa", nsx="2026-11-03", hsd="2027-11-03"), ngay="2026-11-03", ncc="NCC-MOI")
loi = duyet(d) or ""
kiem("HSD trước ngày nhập (hàng đã hết hạn) → chặn như ERPNext",
     "dòng 1 (Hương cốm): HSD 02/11/2026 đã qua ngày nhập 03/11/2026" in loi, loi)
kiem("HSD không sau NSX (gõ đảo hai ô) → nói đúng chỗ sai, không chỉ 'đã qua ngày nhập'",
     "dòng 2 (Hương sen): HSD 24/09/2026 không sau NSX 24/09/2027 — gõ đảo hai ô?" in loi)
kiem("NSX sau ngày nhập → chặn", "dòng 3 (Bột sữa): NSX 04/11/2026 sau ngày nhập 03/11/2026" in loi)
kiem("mã bắt HSD (Has Expiry Date, không Shelf Life) mà chưa ghi HSD → chặn trước khi ERPNext báo tiếng Anh",
     "dòng 4 (Men): mã bắt buộc HSD" in loi)
kiem("HSD = NSX → chặn", "dòng 7 (Hương sen): HSD 03/11/2026 không sau NSX 03/11/2026" in loi)
kiem("… mã có Shelf Life (ERPNext tự tính HSD), HSD = ngày nhập, NSX = ngày nhập thì không kể; chưa tạo lô nào; viết "
     "tắt NCC chưa ghi", "(Bơ)" not in loi and "dòng 6" not in loi and "dòng 8" not in loi
     and len(F.bang("Batch")) == n_lo and "Sửa ô NSX / HSD lô NCC" in loi and "Chưa tạo lô nào" in loi
     and not F.bang("Supplier")["NCC-MOI"].get("custom_viet_tat"), loi)
d = phieu(dong("Bơ"), dong("Hương cốm", hsd="2026-11-03"), dong("Bột sữa", nsx="2026-11-03", hsd="2027-11-03"),
          ngay="2026-11-03", ncc="NCC-MOI")
kiem("Bơ: ERPNext tự tính HSD = NSX mặc định + 180 ngày; ô NSX của lô vẫn để trống (không bịa); HSD = ngày nhập, NSX "
     "= ngày nhập vẫn nhận", duyet(d) is None
     and (lo("GVNA-BO-031126").get("expiry_date"), lo("GVNA-BO-031126").get("manufacturing_date")) == (date(2027, 5, 2), None)
     and [dong_db(d, i)["batch_no"] for i in (2, 3)] == ["GVNA-HC-031126", "GVNA-BS-031126"],
     [dong_db(d, i).get("batch_no") for i in (1, 2, 3)])
kiem("kiem_ngay (hàm thuần): ngày ổn → None; thiếu ngày nhập thì không xét quá hạn",
     LM.kiem_ngay({"custom_ncc_nsx": "2026-01-01", "custom_ncc_hsd": "2027-01-01"}, {}, date(2026, 11, 3)) is None
     and LM.kiem_ngay({"custom_ncc_hsd": "2020-01-01"}, {}, None) is None)

# ═══ 4. Chứng từ / dòng không xét ═════════════════════════════════════════════
print("\n-- chứng từ / dòng không xét --")
n_lo = len(F.bang("Batch"))
d = phieu(dong("Hương cốm"), dong("Hương cốm", "PI0"), dt="Purchase Invoice", update_stock=0, ngay="2026-11-05")
kiem("hoá đơn mua KHÔNG trừ kho → không tạo lô", duyet(d) is None and len(F.bang("Batch")) == n_lo
     and not dong_db(d, 2).get("batch_no"))
d = phieu(dong("Hương cốm", "PI1"), dt="Purchase Invoice", update_stock=1, ngay="2026-11-05")
kiem("hoá đơn mua CÓ trừ kho → tạo lô như phiếu nhập (chứng từ nguồn = hoá đơn)", duyet(d) is None
     and dong_db(d, 1)["batch_no"] == "HLABC-HC-051126" and lo("HLABC-HC-051126")["reference_doctype"] == "Purchase Invoice")
d = phieu(dong("Hương cốm"), dong("Bột sữa"), is_return=1, ngay="2026-11-06")
kiem("phiếu trả hàng NCC → không đụng (lô lấy theo phiếu gốc)", duyet(d) is None
     and not any(k.endswith("061126") for k in F.bang("Batch")))
d = phieu(dong("Máy seri"), dong("Phí lô"), dong("Hương cốm", qty=0), dong("Hương cốm", from_warehouse="Kho khác"),
          ngay="2026-11-07")
kiem("không đụng: mã có serial, mã không giữ kho, dòng số lượng 0, dòng nhận chuyển nội bộ",
     duyet(d) is None and not any(dong_db(d, i).get("batch_no") for i in (1, 2, 3, 4)))
d = phieu(dong("Hương cốm", qty=0, rejected_qty=3), ngay="2026-11-07")
kiem("dòng chỉ có số lượng trả lại (rejected) vẫn vào kho → vẫn có lô", duyet(d) is None
     and dong_db(d, 1)["batch_no"] == "HLABC-HC-071126")
_gv = frappe.db.get_value


def _gv_nhu_frappe(dt, ten, *a, **k):
    """frappe.db.get_value(dt, None, …) KHÔNG trả None: không bộ lọc = bản ghi đầu bảng."""
    if dt == "Item" and ten is None:
        ten = "Hương cốm"
    return _gv(dt, ten, *a, **k)


frappe.db.get_value = _gv_nhu_frappe
d = phieu(dong(None, description="Cước vận chuyển"), dong("Hương cốm"), dt="Purchase Invoice", update_stock=1,
          ngay="2026-11-08")
kiem("hoá đơn mua có dòng chi phí không mã hàng (chỉ diễn giải) → bỏ qua dòng đó, không tra nhầm mã khác",
     duyet(d) is None and not dong_db(d, 1).get("batch_no") and dong_db(d, 2)["batch_no"] == "HLABC-HC-081126", F.BAO)
frappe.db.get_value = _gv
ten, moi = LM.lo_cho(F.Doc(doctype="Purchase Receipt", name="PR-CHUA-LUU", supplier="NCC-HUONG", posting_date="2026-11-09"),
                     "Hương cốm", "API1")
kiem("lập + duyệt một lượt (phiếu chưa vào DB): vẫn tạo lô, chỉ không gắn chứng từ nguồn (Frappe chặn link chưa có)",
     (ten, moi, lo(ten).get("reference_name"), lo(ten).get("supplier"), lo(ten).get("custom_ncc_lo"))
     == ("HLABC-HC-091126", True, None, "NCC-HUONG", "API1"), lo(ten))
kiem("can_lo / nhap_kho / sach (hàm thuần)", LM.can_lo({"qty": 1}, {}) is False and LM.can_lo({"qty": 1}, None) is False
     and LM.nhap_kho(F.Doc(doctype="Purchase Receipt")) and not LM.nhap_kho(F.Doc(doctype="Purchase Invoice"))
     and LM.nhap_kho(F.Doc(doctype="Purchase Invoice", update_stock=1))
     and not LM.nhap_kho(F.Doc(doctype="Purchase Receipt", is_return=1)) and LM.sach("  L  24 ") == "L 24")

# ═══ 5. Xem trước (màn QC) ════════════════════════════════════════════════════
print("\n-- xem trước mã lô (màn Tiếp nhận NL) --")
F.bang("Supplier")["NCC-XEM"] = {"name": "NCC-XEM", "supplier_name": "Công ty Bột Ngọt Sài Gòn"}
F.bang("Item")["Bột ngọt"] = {"name": "Bột ngọt", "has_batch_no": 1, "is_stock_item": 1}
kiem("xem trước = mã lô gốc sẽ tạo, KHÔNG ghi viết tắt / prefix vào NCC, Item",
     LM.ten_goc(F.Doc(doctype="Purchase Receipt", supplier="NCC-XEM", posting_date="2026-11-10"), "Bột ngọt", luu=False)
     == "BNSG-BN-101126" and not F.bang("Supplier")["NCC-XEM"].get("custom_viet_tat")
     and not F.bang("Item")["Bột ngọt"].get("custom_batch_prefix"))
kiem("… prefix / viết tắt đã có thì xem trước dùng đúng chữ đó",
     LM.ten_goc(F.Doc(doctype="Purchase Receipt", supplier="NCC-SEN", posting_date="2026-11-10"), "Cốm xanh", luu=False)
     == "SHT-COM-101126")

# ═══ 6. Site chưa migrate ═════════════════════════════════════════════════════
print("\n-- site chưa migrate (chưa có ô Lô NCC của lô, Viết tắt của NCC) --")
_meta, _ga = frappe.get_meta, frappe.get_all
frappe.get_meta = lambda dt: types.SimpleNamespace(has_field=lambda f: dt not in ("Batch", "Supplier"))


def _ga_chua_migrate(dt, filters=None, fields=None, **k):
    """Như MariaDB: lọc / đọc cột chưa có → lỗi SQL."""
    if (dt == "Batch" and "custom_ncc_lo" in json.dumps([filters, fields], default=str)) or (
            dt == "Supplier" and "custom_viet_tat" in json.dumps([filters, fields], default=str)):
        raise RuntimeError("(1054, \"Unknown column\")")
    return _ga(dt, filters, fields, **k)


def _gv_chua_migrate(dt, ten, fld=None, *a, **k):
    if (dt == "Batch" and "custom_ncc_lo" in json.dumps([ten, fld], default=str)) or (
            dt in ("Supplier",) and "custom_viet_tat" in json.dumps([ten, fld], default=str)):
        raise RuntimeError("(1054, \"Unknown column\")")
    return _gv(dt, ten, fld, *a, **k)


def _ex_chua_migrate(dt, ten=None):
    if dt == "Supplier" and "custom_viet_tat" in json.dumps(ten, default=str):
        raise RuntimeError("(1054, \"Unknown column\")")
    return F.exists(dt, ten)


frappe.get_all, frappe.db.get_value, frappe.db.exists = _ga_chua_migrate, _gv_chua_migrate, _ex_chua_migrate
F.bang("Supplier")["NCC-CU"] = {"name": "NCC-CU", "supplier_name": "Công ty Đường Biên Hoà"}
d = phieu(dong("Hương cốm", "C1", hsd="2027-01-01"), dong("Hương cốm", "C1", hsd="2027-01-01"), ncc="NCC-CU",
          ngay="2026-11-11")
kiem("vẫn duyệt được: viết tắt rút gọn từ tên (không lưu), lô mới không ghi ô chưa có; dòng sau nhập vào lô đó",
     duyet(d) is None and dong_db(d, 1)["batch_no"] == dong_db(d, 2)["batch_no"] == "DBH-HC-111126"
     and "custom_ncc_lo" not in lo("DBH-HC-111126") and "custom_viet_tat" not in F.bang("Supplier")["NCC-CU"], F.BAO)
frappe.get_meta = lambda dt: (_ for _ in ()).throw(RuntimeError("meta hỏng"))
kiem("… đọc meta lỗi → coi như chưa có ô, không văng lỗi", LM._co_o("Batch", "custom_ncc_lo") is False)
frappe.get_meta, frappe.get_all, frappe.db.get_value, frappe.db.exists = _meta, _ga, _gv, F.exists

# ═══ 7. Tài liệu ═════════════════════════════════════════════════════════════
print("\n-- fixtures, README --")
fx = {f["name"]: f for f in json.load(open("sx/fixtures/custom_field.json", encoding="utf-8"))}
b = fx.get("Batch-custom_ncc_lo") or {}
kiem("Batch có ô Lô NCC (chỉ đọc, đánh chỉ mục, không chép khi nhân bản) — module trong bộ lọc fixtures",
     (b.get("fieldtype"), b.get("read_only"), b.get("search_index"), b.get("no_copy"), b.get("module"))
     == ("Data", 1, 1, 1, "SX"), b)
v = fx.get("Supplier-custom_viet_tat") or {}
kiem("NCC có ô 'Viết tắt (mã lô)' ngay sau tên NCC (sửa được); Item: 'Prefix mã lô' nói cả lô nguyên liệu mua",
     (v.get("fieldtype"), v.get("insert_after"), v.get("module"), v.get("read_only")) == ("Data", "supplier_name", "SX", None)
     and fx["Item-custom_batch_prefix"]["label"] == "Prefix mã lô"
     and "{viết tắt NCC}-{prefix}-DDMMYY" in fx["Item-custom_batch_prefix"]["description"], v)
rd = open("README.md", encoding="utf-8").read()
kiem("README: mục D227", "(D227)" in rd and "HLABC-HC-031126" in rd)

F.ket_thuc("LOMUA")
