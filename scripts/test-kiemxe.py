"""D139 (W14) + D165 (W34) — kiểm tra phương tiện vận chuyển BM.09.01 trên hoá đơn bán trừ kho và chuyến
nhận nguyên liệu (phiếu nhập mua); QC kiểm ngẫu nhiên, Trưởng Ban ISO xem tháng.

Vì sao phải có bài này:
  · Hoá đơn bán trừ kho duyệt được khi chưa kiểm xe / xe Không đạt → BM.09.01 trống tháng.
  · Một mục Không đạt mà kết luận vẫn "Đạt" → hồ sơ tự mâu thuẫn.
  · Xe giao nguyên liệu bẩn mà lô vẫn vào kho dùng → kiểm xe chỉ là thủ tục.
  · Bắt kiểm xe cả hoá đơn không trừ kho / phiếu trả hàng / NCC dịch vụ → thủ kho bị chặn vô lý.
  · W34: đổi sang năm mục QT.09 lần BH 01 mà chuyến cũ mất bốn mục đã ghi, hay in lẫn cột → hồ sơ cũ sai.
  · W34: cả tuần không chuyến nào QC kiểm mà không ai biết; ký bù chuyến cũ để xoá nhắc; Trưởng Ban ISO
    không xem tháng mà không ai nhắc.
  · W34: chép hoá đơn tuần trước (Duplicate) mang theo kết quả kiểm xe cũ → chuyến mới "đã kiểm" mà chưa
    ai nhìn xe.

Nạp sx/qc/kiem_xe.py, ncc.py, tiep_nhan.py, nhac.py, sx/api/qc_kiemxe.py, patch d165 THẬT trên frappe giả.
Chạy: python3 scripts/test-kiemxe.py   (verify.sh gọi sẵn)
"""

import json
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

FR = F.cai()
Q = F.nap_qc()
NCC = sys.modules["sx.qc.ncc"]
K = sys.modules["sx.qc.kiem_xe"]
NH = sys.modules["sx.qc.nhac"]
T = F.nap("sx.qc.tiep_nhan", "sx/qc/tiep_nhan.py")
A = F.nap("sx.api.qc_kiemxe", "sx/api/qc_kiemxe.py")
P = F.nap("sx.patches.d165_kiem_xe_phien_ban", "sx/patches/d165_kiem_xe_phien_ban.py")
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")                     # thứ Sáu — tuần này 05/10 – 11/10

GHI = []                                      # (doctype, tên, update_modified) của mọi db.set_value
_sv = FR.db.set_value


def _ghi(dt, ten, f, v=None, update_modified=True):
    GHI.append((dt, ten, update_modified))
    return _sv(dt, ten, f, v, update_modified)


FR.db.set_value = _ghi
F.bang("User").update({"kho@x": {"name": "kho@x", "full_name": "Thủ kho Hà"},
                       "qc@x": {"name": "qc@x", "full_name": "QC Lan"},
                       "iso@x": {"name": "iso@x", "full_name": "Nguyễn Huy Chiến"}})
F.bang("Supplier").update({
    "NCC-DX": {"name": "NCC-DX", "custom_loai_ncc": NCC.TP, "custom_nguon_goc": "Trong nước", "custom_ncc_duyet": 1},
    "NCC-BB": {"name": "NCC-BB", "custom_loai_ncc": NCC.BB_TX, "custom_ncc_duyet": 1},
    "NCC-DV": {"name": "NCC-DV", "custom_loai_ncc": NCC.DV},
    "NCC-MOI": {"name": "NCC-MOI", "custom_loai_ncc": ""}})
F.CAI_DAT_SX["kho_cach_ly"] = "Kho cách ly - RV"

MUC2 = [f for f, _c, _y in K.MUC_THEO_PB[2]]
MUC1 = [f for f, _c, _y in K.MUC_THEO_PB[1]]
DAT5 = {f: "Đạt" for f in MUC2}
DAT4 = {f: "Đạt" for f in MUC1}
XE = {"custom_xe_bien_so": "29C-123.45", "custom_xe_tai_xe": "Anh Ba"}


def hd(**k):
    return F.Doc({"doctype": "Sales Invoice", "name": "SINV-1", "update_stock": 1, "is_return": 0,
                  "items": [F.Doc(idx=1, item_code="TP-SEN")], **k})


def pr(sup="NCC-DX", **k):
    return F.Doc({"doctype": "Purchase Receipt", "name": "PR-1", "supplier": sup, "is_return": 0,
                  "posting_date": "2026-10-08",
                  "items": [F.Doc(idx=1, item_code="DX-01", warehouse="Kho NVL - RV"),
                            F.Doc(idx=2, item_code="DX-02", warehouse="Kho NVL - RV", custom_ket_luan="Không đạt")],
                  **k})


def chay(d):
    K.validate(d)
    return thu(lambda: K.before_submit(d))


F.vai("SX Thu Kho", u="kho@x")

# ═══ 1. Hoá đơn bán trừ kho ═══════════════════════════════════════════════
print("\n-- hoá đơn bán trừ kho (năm mục QT.09 lần BH 01) --")
loi = chay(hd())
kiem("chưa kiểm xe → không duyệt được hoá đơn", loi and "Chưa kiểm xe" in loi, loi or "")
d = hd(**XE, **DAT5)
kiem("đủ năm mục Đạt + biển số + lái xe → kết luận tự Đạt, ghi người kiểm, phiên bản 2, duyệt được",
     chay(d) is None and (d["custom_xe_ket_luan"], d["custom_xe_nguoi_kiem"], d["custom_xe_phien_ban"])
     == ("Đạt", "kho@x", 2))
kiem("thiếu biển số → chặn", "biển số" in (chay(hd(custom_xe_tai_xe="Anh Ba", **DAT5)) or ""))
loi = chay(hd(custom_xe_bien_so="29C-123.45", **DAT5))
kiem("thiếu tên lái xe (lái xe ký — QT.09 mục 5.2) → chặn", "lái xe" in (loi or ""), loi or "")
F.BAO.clear()
d = hd(**XE, custom_xe_ket_luan="Đạt", custom_xe_ghi_chu="Đã đổi xe", **dict(DAT5, custom_xe_san="Không đạt"))
loi = chay(d)
kiem("một mục Không đạt mà ghi kết luận Đạt → ép Không đạt, báo, và CHẶN bán (có ghi xử lý cũng chặn)",
     d["custom_xe_ket_luan"] == "Không đạt" and loi and "không xếp hàng" in loi
     and any("Không đạt" in b for b in F.BAO), loi or "")
d = hd(**XE, custom_xe_ket_luan="Đạt")
kiem("chưa chấm hết mục nhưng người kiểm tự kết luận → giữ kết luận đó", chay(d) is None
     and d["custom_xe_ket_luan"] == "Đạt")
kiem("hoá đơn KHÔNG trừ kho → không bắt kiểm xe (vẫn ghi phiên bản)",
     chay(d := hd(update_stock=0)) is None and d["custom_xe_phien_ban"] == 2)
kiem("phiếu trả hàng → không bắt", chay(hd(is_return=1)) is None)
F.CAI_DAT["bat_buoc_kiem_xe"] = 0
kiem("tắt ở SX QC Setting → không chặn", chay(hd()) is None)
F.CAI_DAT.clear()

# ═══ 2. Chuyến nhận nguyên liệu ═══════════════════════════════════════════
print("\n-- chuyến nhận nguyên liệu (phiếu nhập mua) --")
kiem("NCC thực phẩm: chưa kiểm xe → không duyệt được phiếu nhập", "Chưa kiểm xe" in (chay(pr()) or ""))
kiem("NCC bao bì tiếp xúc thực phẩm cũng bắt", "Chưa kiểm xe" in (chay(pr("NCC-BB")) or ""))
kiem("NCC dịch vụ / chưa phân loại → không bắt", chay(pr("NCC-DV")) is None and chay(pr("NCC-MOI")) is None)
d = pr(**XE, **DAT5)
kiem("xe Đạt → duyệt được, dòng hàng giữ nguyên", chay(d) is None and d["items"][0].get("custom_ket_luan") is None)
d = pr(**XE, **dict(DAT5, custom_xe_mui="Không đạt"))
loi = chay(d)
kiem("xe KHÔNG ĐẠT mà chưa ghi xử lý → chặn duyệt: ghi xử lý (cột Xử lý BM.09.01)", "ghi xử lý" in (loi or ""), loi or "")
kiem("… mọi dòng đã chuyển Cách ly ngay lúc lưu", d["items"][0]["custom_ket_luan"] == "Cách ly")
d = pr(**XE, custom_xe_ghi_chu="Xe ám mùi dầu — cách ly lô, báo QLSX", **dict(DAT5, custom_xe_mui="Không đạt"))
loi = chay(d)
kiem("xe KHÔNG ĐẠT có ghi xử lý → không chặn (hàng đã tới sân), mọi dòng Cách ly",
     loi is None and d["items"][0]["custom_ket_luan"] == "Cách ly", loi or "")
kiem("… dòng đã Không đạt giữ nguyên Không đạt", d["items"][1]["custom_ket_luan"] == "Không đạt")
T.validate(d)
kiem("… và tiếp nhận đưa dòng Cách ly vào kho cách ly (thứ tự hook: kiểm xe trước)",
     d["items"][0]["warehouse"] == "Kho cách ly - RV")
hk = open("sx/hooks.py", encoding="utf-8").read()
khoi = re.search(r'"Purchase Receipt": \{(.*?)\n    \}', hk, re.S).group(1)
kiem("hook Purchase Receipt: kiem_xe.validate đứng TRƯỚC tiep_nhan.validate, có before_submit",
     khoi.index("sx.qc.kiem_xe.validate") < khoi.index("sx.qc.tiep_nhan.validate")
     and '"before_submit": "sx.qc.kiem_xe.before_submit"' in khoi)
khoi = re.search(r'"Sales Invoice": \{(.*?)\},\n', hk, re.S).group(1)
kiem("hook Sales Invoice: kiem_xe.validate + before_submit", "sx.qc.kiem_xe.validate" in khoi
     and "sx.qc.kiem_xe.before_submit" in khoi)
kiem("không móc vào Delivery Note (nhà máy không dùng)", "kiem_xe" not in re.search(
    r'"Delivery Note": \{(.*?)\},\n', hk, re.S).group(1))

# ═══ 3. Phiên bản bộ mục, chép chứng từ, patch, fixtures ══════════════════
print("\n-- phiên bản bộ mục (chuyến cũ giữ bốn mục cũ) --")
kiem("bộ hiện hành = năm cột giấy BM.09.01 lần BH 01, đúng thứ tự",
     K.PHIEN_BAN == 2 and [c for _f, c, _y in K.MUC] == ["Sạch khô", "Mùi", "Kín/che", "Hàng chung", "Sàn"])
kiem("bộ cũ (phiên bản 1) giữ nguyên bốn ô D139",
     MUC1 == ["custom_xe_sach", "custom_xe_khong_chung", "custom_xe_con_trung", "custom_xe_che_chan"]
     and not set(MUC1) & set(MUC2))
d = hd(custom_xe_phien_ban=1, custom_xe_bien_so="29C-1", **dict(DAT4, custom_xe_san="Không đạt"))
loi = chay(d)
kiem("chuyến phiên bản 1: kết luận theo bốn mục cũ (ô mục mới bị bỏ qua), không bắt lái xe (luật cũ)",
     loi is None and d["custom_xe_ket_luan"] == "Đạt" and d["custom_xe_phien_ban"] == 1, loi or d)
d = hd(custom_xe_bien_so="29C-1", **dict(DAT4, custom_xe_con_trung="Không đạt"))
chay(d)
kiem("ô phiên bản trống mà đã có giá trị mục cũ (chép từ chuyến cũ) → phiên bản 1, xét theo mục cũ",
     d["custom_xe_phien_ban"] == 1 and d["custom_xe_ket_luan"] == "Không đạt")
d = hd(custom_xe_phien_ban=1, custom_xe_bien_so="29C-1", custom_xe_ket_luan="Đạt")
loi = chay(d)
kiem("ô phiên bản đã ghi là gốc: chuyến cũ chỉ có kết luận (chưa chấm mục) vẫn phiên bản 1, luật cũ",
     loi is None and d["custom_xe_phien_ban"] == 1, loi or d)
d = hd(custom_xe_phien_ban=2, **XE, **dict(DAT5, custom_xe_sach="Không đạt"))
chay(d)
kiem("… chuyến phiên bản 2 có sót giá trị ô cũ → vẫn phiên bản 2, ô cũ không làm đổi kết luận",
     d["custom_xe_phien_ban"] == 2 and d["custom_xe_ket_luan"] == "Đạt")
kiem("chứng từ mới chưa ghi gì → phiên bản hiện hành (2)", (lambda x: (K.validate(x), x["custom_xe_phien_ban"])[1])(hd()) == 2)

cf = json.load(open("sx/fixtures/custom_field.json", encoding="utf-8"))
for dt in K.LOAI:
    o = {f["fieldname"]: f for f in cf if f["dt"] == dt}
    kiem(f"{dt}: đủ ô mọi phiên bản (Select Đạt / Không đạt), ô cũ chỉ hiện ở phiên bản 1, ô mới ở phiên bản khác 1",
         all(o[f]["fieldtype"] == "Select" and o[f]["options"].split("\n") == ["", K.DAT, K.KHONG_DAT]
             for f in MUC1 + MUC2 + ["custom_xe_ket_luan"])
         and all(o[f]["depends_on"] == "eval:doc.custom_xe_phien_ban==1" for f in MUC1)
         and all(o[f]["depends_on"] == "eval:doc.custom_xe_phien_ban!=1" for f in MUC2)
         and [o[f]["label"] for f in MUC2] == [c for _f, c, _y in K.MUC])
    kiem(f"{dt}: ô phiên bản ẩn, chỉ đọc; QC kiểm / Trưởng Ban ISO xem: chỉ đọc, ghi được sau duyệt",
         o["custom_xe_phien_ban"]["fieldtype"] == "Int" and o["custom_xe_phien_ban"].get("hidden")
         and o["custom_xe_phien_ban"].get("read_only")
         and all(o[f].get("read_only") and o[f].get("allow_on_submit")
                 for f in ("custom_xe_qc_kiem", "custom_xe_qc_luc", "custom_xe_qc_nhan_xet", "custom_xe_xem_boi",
                           "custom_xe_xem_luc"))
         and o["custom_xe_qc_kiem"]["options"] == "User" and o["custom_xe_qc_luc"]["fieldtype"] == "Datetime")
    du_lieu = [f for f in o if f.startswith("custom_xe_")]
    kiem(f"{dt}: MỌI ô kiểm xe không chép khi Duplicate (chuyến mới phải kiểm lại xe, QC chưa kiểm)",
         all(o[f].get("no_copy") for f in du_lieu) and len(du_lieu) == 21, len(du_lieu))
    co = set(o) | {"items", "custom_ghi_chu_qc"}
    kiem(f"{dt}: lái xe ký, đơn vị vận chuyển, ô Xử lý; mỗi ô chèn sau một ô có thật, không ô nào trùng chỗ",
         "Lái xe" in o["custom_xe_tai_xe"]["label"] and o["custom_xe_don_vi"]["label"] == "Đơn vị vận chuyển"
         and o["custom_xe_ghi_chu"]["label"].startswith("Xử lý")
         and all(f["insert_after"] in co for f in o.values() if f["fieldname"].startswith(("custom_xe", "custom_cb_kiem")))
         and len({f["insert_after"] for f in o.values()}) == len(o))

print("\n-- patch d165: chuyến đã ghi trước D165 → phiên bản 1 --")
FR.get_app_path = lambda app, *p: os.path.join(app, *p)
F.dang_ky("Custom Field", F.Document, ten_theo="name")      # như frappe: tạo trùng tên → DuplicateEntryError
FR.db.has_column = lambda dt, f: True
F.bang("Sales Invoice").update({
    "SI-CU": {"name": "SI-CU", "custom_xe_bien_so": "29C-9", "custom_xe_sach": "Đạt", "custom_xe_phien_ban": 0},
    "SI-KL": {"name": "SI-KL", "custom_xe_ket_luan": "Đạt"},
    "SI-TRONG": {"name": "SI-TRONG", "custom_xe_phien_ban": 0},
    "SI-MOI": {"name": "SI-MOI", "custom_xe_phien_ban": 2, "custom_xe_bien_so": "29C-8", **DAT5}})
F.bang("Purchase Receipt")["PR-CU"] = {"name": "PR-CU", "custom_xe_tai_xe": "Anh Tư"}
GHI.clear()
P.execute()
P.execute()
pb = {n: F.bang("Sales Invoice")[n].get("custom_xe_phien_ban") for n in ("SI-CU", "SI-KL", "SI-TRONG", "SI-MOI")}
kiem("có ghi kiểm xe (mục cũ / kết luận / biển số / lái xe) → 1; chưa ghi gì → để 0; đã có phiên bản → giữ",
     pb == {"SI-CU": 1, "SI-KL": 1, "SI-TRONG": 0, "SI-MOI": 2}
     and F.bang("Purchase Receipt")["PR-CU"]["custom_xe_phien_ban"] == 1, pb)
kiem("patch tạo trước ô custom_xe_phien_ban từ fixtures (migrate đồng bộ fixtures SAU patch), chạy lại không trùng",
     sorted(F.bang("Custom Field")) == ["Purchase Receipt-custom_xe_phien_ban", "Sales Invoice-custom_xe_phien_ban"])
kiem("patch không đổi `modified` của chứng từ", GHI and all(u is False for _d, _t, u in GHI))
for b in ("Sales Invoice", "Purchase Receipt", "Custom Field"):
    F.bang(b).clear()

# ═══ 4. QC kiểm ngẫu nhiên — nhắc theo tuần thứ Hai – Chủ nhật ═════════════
print("\n-- nhắc QC: tuần có chuyến mà chưa chuyến nào QC kiểm --")


def xe(dt, ten, ngay, docstatus=1, **k):
    h = {"name": ten, "posting_date": ngay, "docstatus": docstatus, "is_return": 0, "custom_xe_phien_ban": 2,
         "custom_xe_bien_so": "29C-123.45", "custom_xe_don_vi": "Nhà xe Minh Phát", "custom_xe_tai_xe": "Anh Ba",
         "custom_xe_ket_luan": "Đạt", "custom_xe_nguoi_kiem": "kho@x", **DAT5}
    h.update({"update_stock": 1, "customer_name": "Đại lý Nam Định"} if dt == "Sales Invoice"
             else {"supplier_name": "NCC Đỗ Xanh"})
    h.update(k)
    F.bang(dt)[ten] = h


xe("Sales Invoice", "SI-A", "2026-10-08")                          # tuần này (hôm qua)
xe("Sales Invoice", "SI-H", "2026-10-06")                          # tuần này (3 ngày trước)
xe("Purchase Receipt", "PR-B", "2026-10-01", custom_xe_san="Không đạt", custom_xe_ket_luan="Không đạt",
   custom_xe_ghi_chu="Sàn còn đinh — cách ly lô, báo QLSX")         # tuần trước
xe("Sales Invoice", "SI-C", "2026-10-04", docstatus=0)            # Chủ nhật tuần trước, nháp
xe("Sales Invoice", "SI-D", "2026-10-05", docstatus=2)            # huỷ
xe("Sales Invoice", "SI-E", "2026-10-07", is_return=1)            # trả hàng
xe("Sales Invoice", "SI-F", "2026-10-07", update_stock=0)         # không trừ kho
xe("Sales Invoice", "SI-G", "2026-10-08", docstatus=0, custom_xe_ket_luan=None)   # chưa ghi kiểm xe
xe("Sales Invoice", "SI-S1", "2026-09-15")                         # tháng 9, đã duyệt
xe("Sales Invoice", "SI-S2", "2026-09-20", docstatus=0)           # tháng 9, nháp
kiem("tuần = thứ Hai – Chủ nhật: Chủ nhật 04/10 thuộc tuần 28/09, thứ Hai 05/10 mở tuần mới",
     set(K.theo_tuan([{"posting_date": "2026-10-04"}, {"posting_date": "2026-10-05"}])) == {
         date(2026, 9, 28), date(2026, 10, 5)} and K.thu_hai("2026-10-11") == date(2026, 10, 5))
nh = K.nhac("2026-10-09")
kiem("tuần này 2 chuyến, tuần trước 2 (nháp tính — chuyến đang xếp hàng); không tính phiếu huỷ, trả hàng, "
     "hoá đơn không trừ kho, chứng từ chưa ghi kiểm xe",
     nh["tuan_nay"] == {"tu": "2026-10-05", "den": "2026-10-11", "so_chuyen": 2, "so_qc": 0}
     and nh["tuan_truoc"] == {"tu": "2026-09-28", "den": "2026-10-04", "so_chuyen": 2, "so_qc": 0}, nh)
kiem("tháng 9 qua ngày 5 tháng 10 mà Trưởng Ban ISO chưa xem → nhắc (chuyến nháp không tính)",
     nh["chua_xem"] == ["2026-09"])
kiem("ngày 05/10 tháng 9 chưa tới hạn xem", K.nhac("2026-10-05")["chua_xem"] == [])
ds = NH.tinh(date(2026, 10, 9), [], [], {}, kiem_xe=nh)
xe_nh = [x for x in ds if x["nhom"] == "kiem_xe"]
kiem("hộp nhắc: tuần này / tuần trước chưa chuyến nào QC kiểm + tháng chưa xem; mức thường, sang màn Kiểm xe",
     [x["tieu_de"] for x in xe_nh] == ["Tuần này 2 chuyến hàng, chưa chuyến nào QC kiểm xe",
                                       "Tuần trước 2 chuyến hàng, chưa chuyến nào QC kiểm xe",
                                       "Kiểm xe BM.09.01 tháng 09/2026 chưa được Trưởng Ban ISO xem"]
     and all(x["muc_do"] == NH.THUONG and x["route"] == "#/qc/kiemxe" for x in xe_nh)
     and "Thứ Hai 05/10 – Chủ nhật 11/10" in xe_nh[0]["chi_tiet"], [x["tieu_de"] for x in xe_nh])
F.vai("SX QC")
kiem("hộp nhắc QC (sx.api.qc.nhac) có nhắc kiểm xe — cùng nguồn _du_lieu_nhac",
     "Tuần này 2 chuyến hàng, chưa chuyến nào QC kiểm xe" in [x["tieu_de"] for x in Q.nhac()["ds"]])
kiem("tuần không có chuyến → không nhắc; site chưa migrate → {} (không lỗi hộp nhắc)",
     not [x for x in NH.tinh(date(2026, 10, 9), [], [], {}, kiem_xe={"tuan_nay": {"so_chuyen": 0, "so_qc": 0}})
          if x["nhom"] == "kiem_xe"]
     and (lambda g: (setattr(K, "chuyen", lambda *a, **k: 1 / 0), K.nhac("2026-10-09"),
                     setattr(K, "chuyen", g))[1])(K.chuyen) == {})

print("\n-- QC KIỂM: đóng dấu người + giờ --")
GHI.clear()
r = A.qc_kiem("Sales Invoice", "SI-A", "Sàn sạch, đúng như thủ kho ghi")
h = F.bang("Sales Invoice")["SI-A"]
kiem("QC đóng dấu chuyến hôm qua: người, giờ, nhận xét — modified ĐỔI (Desk đang mở bản cũ không lưu đè)",
     (h["custom_xe_qc_kiem"], str(h["custom_xe_qc_luc"])[:16], h["custom_xe_qc_nhan_xet"])
     == ("qc@x", "2026-10-09 10:00", "Sàn sạch, đúng như thủ kho ghi") and r["qc_luc"] == "2026-10-09 10:00"
     and GHI == [("Sales Invoice", "SI-A", True)], (h, GHI))
kiem("có chuyến QC kiểm → tuần này hết nhắc", K.nhac("2026-10-09")["tuan_nay"]["so_qc"] == 1
     and not [x for x in NH.tinh(date(2026, 10, 9), [], [], {}, kiem_xe=K.nhac("2026-10-09"))
              if x["nhom"] == "kiem_xe" and x["tieu_de"].startswith("Tuần này")])
kiem("đóng dấu lần hai → chặn", "đã có QC kiểm" in (thu(lambda: A.qc_kiem("Sales Invoice", "SI-A")) or ""))
loi = thu(lambda: A.qc_kiem("Sales Invoice", "SI-H"))
kiem("chuyến quá 2 ngày → không ký bù (kiểm xe là kiểm lúc xếp / nhận hàng)", "không ký bù" in (loi or ""), loi)
kiem("chuyến tuần trước (để xoá nhắc tuần trước) → không ký bù",
     "không ký bù" in (thu(lambda: A.qc_kiem("Purchase Receipt", "PR-B")) or ""))
xe("Sales Invoice", "SI-MAI", "2026-10-10")
kiem("chuyến ngày mai → không ký trước", "không ký bù" in (thu(lambda: A.qc_kiem("Sales Invoice", "SI-MAI")) or ""))
F.bang("Sales Invoice").pop("SI-MAI")
kiem("chứng từ chưa ghi kiểm xe → chưa có gì để QC đối chiếu",
     "chưa ghi kiểm xe" in (thu(lambda: A.qc_kiem("Sales Invoice", "SI-G")) or ""))
kiem("phiếu huỷ / trả hàng / hoá đơn không trừ kho / doctype khác → không phải chuyến",
     all("không phải chuyến" in (thu(lambda n=n: A.qc_kiem("Sales Invoice", n)) or "") for n in ("SI-D", "SI-E", "SI-F"))
     and "chỉ ghi" in (thu(lambda: A.qc_kiem("Delivery Note", "DN-1")) or ""))
xe("Sales Invoice", "SI-Q", "2026-10-09")
for vai in ("ISO Manager", "Production Manager"):
    F.vai(vai)
    loi = thu(lambda: A.qc_kiem("Sales Invoice", "SI-Q"))
    kiem(f"{vai} không đóng dấu QC kiểm (QT.09: việc của QC)", loi is not None and "đã có" not in loi
         and not F.bang("Sales Invoice")["SI-Q"].get("custom_xe_qc_kiem"), loi)
F.bang("Sales Invoice").pop("SI-Q")
F.vai("SX QC", u="qc2@x")
kiem("QC khác bỏ dấu của người khác → chặn", "Chỉ người đóng dấu" in (thu(lambda: A.bo_qc_kiem("Sales Invoice", "SI-A"))
                                                                       or ""))
F.vai("SX QC")
A.bo_qc_kiem("Sales Invoice", "SI-A")
h = F.bang("Sales Invoice")["SI-A"]
kiem("người đóng dấu bỏ được trong ngày (đóng dấu nhầm chuyến)",
     (h["custom_xe_qc_kiem"], h["custom_xe_qc_luc"], h["custom_xe_qc_nhan_xet"]) == (None, None, None))
A.qc_kiem("Sales Invoice", "SI-A", "")
kiem("đóng dấu lại, nhận xét trống → None", F.bang("Sales Invoice")["SI-A"]["custom_xe_qc_nhan_xet"] is None
     and F.bang("Sales Invoice")["SI-A"]["custom_xe_qc_kiem"] == "qc@x")

print("\n-- màn Kiểm xe: tổng quan tháng --")
F.bang("Sales Invoice Item").update({
    "SII-1": {"name": "SII-1", "parent": "SI-A", "parenttype": "Sales Invoice", "idx": 1, "item_code": "TP-RV250",
              "item_name": "Bánh đậu xanh Rồng Vàng 250g", "qty": 40.0, "uom": "Hộp", "batch_no": "LO-150427"},
    "SII-2": {"name": "SII-2", "parent": "SI-A", "parenttype": "Sales Invoice", "idx": 2, "item_code": "TP-SEN",
              "item_name": "Bánh sen", "qty": 12.5, "uom": "Kg", "serial_and_batch_bundle": "SABB-1"}})
F.bang("Serial and Batch Entry")["SBE-1"] = {"name": "SBE-1", "parent": "SABB-1", "batch_no": "LO-010527"}
F.bang("Batch").update({"LO-150427": {"name": "LO-150427", "expiry_date": date(2027, 4, 15)},
                        "LO-010527": {"name": "LO-010527", "expiry_date": date(2027, 5, 1)}})
dl = A.tong_quan()
tuan = {t["tu"]: t for t in dl["tuan"]}
kiem("tuần của tháng 10, mới trước: 26/10 … 28/09; tuần 28/09 đếm cả ngày tháng 9 trong tuần, đã hết",
     [t["tu"] for t in dl["tuan"]] == ["2026-10-26", "2026-10-19", "2026-10-12", "2026-10-05", "2026-09-28"]
     and (tuan["2026-09-28"]["so_chuyen"], tuan["2026-09-28"]["so_qc"], tuan["2026-09-28"]["qua"]) == (2, 0, True)
     and (tuan["2026-10-05"]["so_chuyen"], tuan["2026-10-05"]["so_qc"], tuan["2026-10-05"]["nay"],
          tuan["2026-10-05"]["qua"]) == (2, 1, True, False)
     and not tuan["2026-10-12"]["qua"] and not tuan["2026-10-12"]["nay"],
     dl["tuan"])
x = {r["name"]: r for r in dl["ds"]}
kiem("chuyến trong tháng mới trước (nháp có, đánh dấu), không lẫn tháng 9",
     [r["name"] for r in dl["ds"]] == ["SI-A", "SI-H", "SI-C", "PR-B"] and x["SI-C"]["nhap"] and not x["SI-A"]["nhap"])
kiem("năm mục Đ/K theo phiên bản chuyến, tên người kiểm, chiều, đối tác, QC kiểm",
     [m["cot"] for m in x["PR-B"]["muc"]] == ["Sạch khô", "Mùi", "Kín/che", "Hàng chung", "Sàn"]
     and x["PR-B"]["muc"][4]["gt"] == "Không đạt" and x["PR-B"]["chieu"] == "Nhận nguyên liệu"
     and x["PR-B"]["doi_tac"] == "NCC Đỗ Xanh" and x["SI-A"]["ten_nguoi_kiem"] == "Thủ kho Hà"
     and x["SI-A"]["ten_qc"] == "QC Lan" and x["SI-A"]["don_vi"] == "Nhà xe Minh Phát")
kiem("hàng, số lượng, HSD: lô ở ô batch_no và trong Serial and Batch Bundle",
     x["SI-A"]["hang"] == ["Bánh đậu xanh Rồng Vàng 250g · 40 Hộp · HSD 15/04/2027",
                           "Bánh sen · 12.5 Kg · HSD 01/05/2027"], x["SI-A"]["hang"])
kiem("QC KIỂM được: chuyến chưa có dấu trong 2 ngày; chuyến 3 ngày trước / đã có dấu → không",
     not x["SI-A"]["duoc_qc"] and not x["SI-H"]["duoc_qc"] and not x["PR-B"]["duoc_qc"]
     and dl["so_ngay_qc"] == K.SO_NGAY_QC == 2)
kiem("quyền: QC ghi được, không xem tháng; chưa ai xem tháng 10",
     dl["duoc_ghi"] and not dl["duoc_xem_thang"] and dl["xem"] is None and dl["chua_xem"] == 3 and dl["so_nhap"] == 1)
F.vai("ISO Manager")
dl = A.tong_quan()
kiem("Trưởng Ban ISO: xem tháng được, không đóng dấu QC", dl["duoc_xem_thang"] and not dl["duoc_ghi"])
F.vai("Production Manager")
kiem("QLSX xem được màn (chỉ đọc)", thu(A.tong_quan) is None and not A.tong_quan()["duoc_ghi"])
F.vai("SX Vao Hop")
kiem("người ngoài QC không vào", thu(A.tong_quan) is not None)

print("\n-- Trưởng Ban ISO: Đã xem tháng --")
F.vai("SX QC")
kiem("QC không bấm Đã xem tháng", thu(lambda: A.xem_thang("2026-09")) is not None)
F.vai("ISO Manager")
kiem("tháng chưa tới / tháng không có chuyến → báo", "chưa tới" in (thu(lambda: A.xem_thang("2026-11")) or "")
     and "không có chuyến" in (thu(lambda: A.xem_thang("2026-08")) or ""))
GHI.clear()
r = A.xem_thang("2026-09")
kiem("ký xem mọi chuyến ĐÃ DUYỆT chưa xem của tháng (nháp chờ lần sau); modified đổi",
     r["so"] == 1 and F.bang("Sales Invoice")["SI-S1"]["custom_xe_xem_boi"] == "iso@x"
     and not F.bang("Sales Invoice")["SI-S2"].get("custom_xe_xem_luc") and GHI == [("Sales Invoice", "SI-S1", True)])
kiem("tháng 9 hết nhắc", K.nhac("2026-10-09")["chua_xem"] == [])
F.bang("Sales Invoice")["SI-S2"]["docstatus"] = 1
kiem("chuyến tháng 9 duyệt sau lần xem → nhắc lại tháng đó", K.nhac("2026-10-09")["chua_xem"] == ["2026-09"])
dl = A.tong_quan("2026-09")
kiem("màn tháng 9: lần xem gần nhất (tên Trưởng Ban ISO), 1 chuyến duyệt sau lần xem",
     dl["xem"]["ten"] == "Nguyễn Huy Chiến" and dl["chua_xem"] == 1)
F.vai("SX QC", u="qc2@x")
kiem("tháng đã xem: QC không bỏ được dấu QC kiểm", "đã được Trưởng Ban ISO xem" in (
    thu(lambda: (F.bang("Sales Invoice")["SI-S1"].update(custom_xe_qc_kiem="qc2@x", custom_xe_qc_luc="2026-10-09 09:00"),
                 A.bo_qc_kiem("Sales Invoice", "SI-S1"))) or ""))
F.dat_ngay("2026-10-10")
F.vai("SX QC")
kiem("qua ngày: người đóng dấu không bỏ được nữa", "Chỉ người đóng dấu" in (
    thu(lambda: A.bo_qc_kiem("Sales Invoice", "SI-A")) or ""))
F.vai("ISO Manager")
kiem("Ban ISO bỏ được (tháng chưa xem)", thu(lambda: A.bo_qc_kiem("Sales Invoice", "SI-A")) is None
     and F.bang("Sales Invoice")["SI-A"]["custom_xe_qc_kiem"] is None)
F.vai("SX QC")
A.qc_kiem("Sales Invoice", "SI-A", "Kiểm lại: đạt")
F.dat_ngay("2026-10-09")

# ═══ 5. Bản in BM.09.01 ═══════════════════════════════════════════════════
print("\n-- bản in BM.09.01 (đúng cột giấy lần BH 01) --")
xe("Sales Invoice", "SI-CU", "2026-10-02", custom_xe_phien_ban=1, custom_xe_tai_xe="Anh Năm",
   **{f: None for f in MUC2}, **dict(DAT4, custom_xe_con_trung="Không đạt"), custom_xe_ket_luan="Không đạt")


def chu(html):
    return re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", html.split("</style>")[1]).replace("&nbsp;", " "))


if F.jinja2:
    html = A.in_so_kiem_xe("2026-10-01", "2026-10-31")
    c = chu(html)
    dau = re.findall(r"<tr><th.*?</tr>", html, re.S)
    cot = [re.sub(r"\s+", " ", re.sub("<[^>]+>", "", t)).strip() for t in re.findall(r"<th[^>]*>(.*?)</th>", dau[0], re.S)]
    kiem("tháng 10/2026, mã BM.09.01 · Lần BH 01, cột đúng tờ giấy",
         "tháng 10/2026" in c and "BM.09.01 · Lần BH 01" in c
         and cot == ["Ngày", "Biển số", "Đơn vị VC", "Hàng, số lượng, HSD", "Sạch khô", "Mùi", "Kín/che", "Hàng chung",
                     "Sàn", "Đạt", "Xử lý", "Người kiểm", "Lái xe ký"], cot)
    kiem("chỉ chuyến đã duyệt (nháp SI-C không in); Đ / K; xử lý; QC kiểm ghi dưới người kiểm; lái xe ký",
         not re.search(r"SI-C\b", c) and "PR-B" in c and "Sàn còn đinh" in c and "QC kiểm: QC Lan" in c and "Kiểm lại: đạt" in c
         and "Anh Ba" in c and "HSD 15/04/2027" in c and " K " in c and " Đ " in c, c[:600])
    hang_b = next(t for t in re.findall(r"<tr>(.*?)</tr>", html, re.S) if "PR-B" in t)
    o = [re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", t)).strip() for t in re.findall(r"<td[^>]*>(.*?)</td>", hang_b, re.S)]
    kiem("dòng PR-B: năm mục + Đạt in Đ / K đúng thứ tự, ô K in đậm, xử lý ở cột Xử lý",
         o[4:10] == ["Đ", "Đ", "Đ", "Đ", "K", "K"] and o[10] == "Sàn còn đinh — cách ly lô, báo QLSX"
         and hang_b.count('class="kd"') == 2, o)
    kiem("chuyến bộ mục cũ in bảng riêng, đúng bốn cột cũ", len(dau) == 2 and "bộ mục cũ" in c
         and "Không có dấu hiệu côn trùng" in dau[1] and "Sạch khô" not in dau[1] and "Anh Năm" in c)
    kiem("chân tờ: Trưởng Ban ISO xem tháng 10 — chưa xem (dòng chấm để ký tay)",
         "Trưởng Ban ISO xem xét hằng tháng" in c and "Tháng 10/2026: ……" in c)
    c = chu(A.in_so_kiem_xe("2026-09-01", "2026-09-30"))
    kiem("tháng 9: tên Trưởng Ban ISO đã xem + số chuyến duyệt sau lần xem; không chuyến bộ cũ → không in bảng cũ",
         "Tháng 09/2026: Nguyễn Huy Chiến" in c and "còn 1 chuyến duyệt sau lần xem" in c and "bộ mục cũ" not in c,
         c[-300:])
    c = chu(A.in_so_kiem_xe("2026-10-05", "2026-10-11"))
    kiem("khoảng không trọn tháng → ghi Từ … đến …", "Từ 05/10/2026 đến 11/10/2026" in c and "tháng 10/2026" not in c)
    goc = K.chuyen
    K.chuyen = lambda *a, **k: 1 / 0
    c = chu(A.in_so_kiem_xe("2026-10-01", "2026-10-31"))
    kiem("site chưa migrate → tờ trống, không lỗi", "Không có chuyến nào" in c and A.tong_quan()["ds"] == [])
    K.chuyen = goc

# ═══ 6. Màn hình, nối vào app ═════════════════════════════════════════════
print("\n-- màn hình, cấu hình --")
st = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_qc_setting/sx_qc_setting.json",
                                                encoding="utf-8"))["fields"]}
kiem("SX QC Setting: bắt kiểm xe (mặc định bật)", st["bat_buoc_kiem_xe"].get("default") == "1")
qj = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
kiem("route #/qc/kiemxe, tab Hôm nay sáng khi ở màn này",
     "kiemxe: '/assets/sx/sx/views/qc_kiemxe.js'" in qj and re.search(r"SO_HOM_NAY = \[[^\]]*'kiemxe'", qj))
kiem("nút Kiểm xe ở lưới cuối màn Hôm nay", "'#/qc/kiemxe', '🚚 Kiểm xe'" in open(
    "sx/public/sx/views/qc_home.js", encoding="utf-8").read())
vj = open("sx/public/sx/views/qc_kiemxe.js", encoding="utf-8").read()
kiem("màn gọi đủ API: tổng quan, QC kiểm, bỏ dấu, xem tháng, in",
     all(f"sx.api.qc_kiemxe.{m}" in vj for m in ("tong_quan", "qc_kiem", "bo_qc_kiem", "xem_thang", "in_so_kiem_xe")))
kiem("màn Xem xét vẫn có nút in BM.09.01", "sx.api.qc_kiemxe.in_so_kiem_xe" in open(
    "sx/public/sx/views/qc_review.js", encoding="utf-8").read())
HS = F.nap("sx.qc.ho_so", "sx/qc/ho_so.py")
AT = F.nap("sx.qc.attp", "sx/qc/attp.py")
kiem("danh mục hồ sơ: BM.09.01 thuộc mảng Kiểm tra xe của Tổng quan ATTP",
     HS.BIEU_MAU["BM.09.01"][1] == "kiem_xe" and ("kiem_xe", "Kiểm tra xe", "BM.09.01", "#/qc/kiemxe") in AT.LINH_VUC)
kiem("patch d165 trong patches.txt", "sx.patches.d165_kiem_xe_phien_ban" in open("sx/patches.txt", encoding="utf-8").read())

F.ket_thuc("KIEMXE")
