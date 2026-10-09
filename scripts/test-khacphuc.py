"""D150 (W24) — phiếu hành động khắc phục BM.01.07, gắn với sự cố.

Vì sao phải có bài này:
  · Người làm tự xác nhận "có hiệu lực" rồi tự đóng → bước kiểm tra hiệu lực thành dấu tích.
  · Báo "đã thực hiện" mà chưa có nguyên nhân / kết quả → phiếu rỗng nằm ở Chờ kiểm tra.
  · Một sự cố đẻ hai phiếu khắc phục song song → không ai biết phiếu nào là thật.
  · Phiếu quá hạn không lên hộp nhắc / Tổng quan → nguyên nhân còn đó, sự cố lặp lại.

Nạp sx/qc/khac_phuc.py, controller SX Khac Phuc, sx/api/qc_khacphuc.py, patch THẬT; frappe giả.
Chạy: python3 scripts/test-khacphuc.py   (verify.sh gọi sẵn)
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

F.cai()
Q = F.nap_qc()
for t in ("khieu_nai", "ncc", "rework", "attp", "ho_so"):
    F.nap(f"sx.qc.{t}", f"sx/qc/{t}.py")
for t in ("qc_ncc", "qc_attp", "qc_khacphuc", "qc_hoso"):
    F.nap(f"sx.api.{t}", f"sx/api/{t}.py")
KP = sys.modules["sx.qc.khac_phuc"]
NH = sys.modules["sx.qc.nhac"]
HS = sys.modules["sx.qc.ho_so"]
A = sys.modules["sx.api.qc_khacphuc"]
ATTP = sys.modules["sx.api.qc_attp"]
HSA = sys.modules["sx.api.qc_hoso"]
CT = F.nap("kp_ctl", "sx/qc/doctype/sx_khac_phuc/sx_khac_phuc.py")
F.dang_ky(KP.PT, CT.SXKhacPhuc)
HCT = F.nap("hs_ctl", "sx/qc/doctype/sx_ho_so_danh_muc/sx_ho_so_danh_muc.py")
F.dang_ky(HS.PT, HCT.SXHoSoDanhMuc)
P = F.nap("sx.patches.d150_khac_phuc", "sx/patches/d150_khac_phuc.py")
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")
SC = F.bang("SX Su Co")
SC.update({
    "SC-1": {"name": "SC-1", "ngay": "2026-10-02", "trang_thai": "Mở", "muc_do": "Cao", "dien_tap": 0,
             "mo_ta": "Mạt kim loại ở nam châm sau nghiền M2", "nguyen_nhan": "Lưới sàng LS-01-M2 rách",
             "hanh_dong_khac_phuc": "Thay lưới, kiểm lưới đầu ca", "xu_ly_ngay": "Cô lập lô", "car_so": ""},
    "SC-2": {"name": "SC-2", "ngay": "2026-10-05", "trang_thai": "Mở", "muc_do": "Thường", "dien_tap": 0,
             "mo_ta": "Thùng bột hở nắp", "car_so": "CAR-GIAY-07"}})


def kp(ten):
    return F.bang(KP.PT)[ten]


# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- quá hạn, ô thiếu (hàm thuần) --")
kiem("quá hạn: phiếu Mở, hạn trước hôm nay; đúng hạn hôm nay / phiếu chờ kiểm tra → không",
     KP.qua_han({"trang_thai": "Mở", "han": "2026-10-08"}, "2026-10-09")
     and not KP.qua_han({"trang_thai": "Mở", "han": "2026-10-09"}, "2026-10-09")
     and not KP.qua_han({"trang_thai": "Chờ kiểm tra", "han": "2026-10-01"}, "2026-10-09")
     and not KP.qua_han({"trang_thai": "Mở"}, "2026-10-09"))
kiem("báo đã thực hiện cần đủ: nguyên nhân, hành động, kết quả, ngày xong",
     KP.thieu_de_gui({"nguyen_nhan": "a", "hanh_dong": " "}) == ["Hành động khắc phục", "Kết quả thực hiện",
                                                                "Ngày hoàn thành"])

# ═══ 2. Lập từ sự cố ══════════════════════════════════════════════════════
print("\n-- lập từ sự cố, một sự cố một phiếu chưa đóng --")
r = A.lap(json.dumps({"su_co": "SC-1"}))
c1 = r["name"]
x = kp(c1)
kiem("lập từ sự cố: nguồn Sự cố, lấy sẵn mô tả / nguyên nhân / hành động đã ghi trên sự cố, người lập",
     x["nguon"] == "Sự cố" and x["su_co"] == "SC-1" and x["mo_ta"].startswith("Mạt kim loại")
     and x["nguyen_nhan"] == "Lưới sàng LS-01-M2 rách" and x["hanh_dong"].startswith("Thay lưới")
     and x["trang_thai"] == "Mở" and x["lap_boi"] == "qc@x" and r["da_co"] == 0, x)
kiem("số phiếu ghi ngược vào ô Số CAR của sự cố", SC["SC-1"]["car_so"] == c1)
r2 = A.lap(json.dumps({"su_co": "SC-1"}))
kiem("bấm lập lần nữa → trả lại chính phiếu đang mở, không đẻ phiếu thứ hai",
     r2 == {"name": c1, "da_co": 1} and len(F.bang(KP.PT)) == 1)
loi = thu(lambda: F.get_doc({"doctype": KP.PT, "nguon": "Sự cố", "su_co": "SC-1", "mo_ta": "x",
                             "trang_thai": "Mở", "ngay": "2026-10-09"}).insert())
kiem("Desk: phiếu thứ hai chưa đóng cho cùng sự cố → chặn", loi and "đã có phiếu khắc phục" in loi, loi)
kiem("sự cố không có → chặn", "Không có phiếu sự cố" in (thu(lambda: A.lap(json.dumps({"su_co": "SC-9"}))) or ""))
kiem("nguồn Sự cố mà không gắn phiếu sự cố → chặn", "chọn phiếu sự cố" in (thu(lambda: F.get_doc({
    "doctype": KP.PT, "nguon": "Sự cố", "mo_ta": "x", "trang_thai": "Mở", "ngay": "2026-10-09"}).insert()) or ""))
kiem("lập tay không mô tả → chặn", "điều không phù hợp" in (thu(lambda: A.lap(json.dumps(
    {"nguon": "Đánh giá nội bộ"}))) or ""))
c9 = A.lap(json.dumps({"nguon": "Đánh giá nội bộ", "mo_ta": "Chưa có biên bản đào tạo đồng hồ nhiệt"}))["name"]
kiem("lập tay (đánh giá nội bộ) không cần sự cố", kp(c9)["nguon"] == "Đánh giá nội bộ" and not kp(c9).get("su_co"))

# ═══ 3. Ghi, báo đã thực hiện ═════════════════════════════════════════════
print("\n-- ghi nội dung, báo đã thực hiện --")
kiem("hạn trước ngày lập → chặn", "trước ngày lập" in (thu(lambda: A.luu(c1, json.dumps({"han": "2026-10-01"})))
                                                     or ""))
kiem("ngày hoàn thành sau hôm nay → chặn", "sau hôm nay" in (thu(lambda: A.luu(c1, json.dumps(
    {"ngay_xong": "2026-10-10"}))) or ""))
A.luu(c1, json.dumps({"nguoi_thuc_hien": "Tổ cơ điện", "han": "2026-10-20"}))
loi = thu(lambda: A.luu(c1, json.dumps({}), gui=1))
kiem("báo đã thực hiện khi chưa có kết quả, ngày xong → chặn, nói thiếu gì",
     loi and "Kết quả thực hiện" in loi and "Ngày hoàn thành" in loi and kp(c1)["trang_thai"] == "Mở", loi)
r = A.luu(c1, json.dumps({"ket_qua": "Đã thay lưới mới, thêm mục kiểm lưới đầu ca", "ngay_xong": "2026-10-08"}),
          gui=1)
kiem("đủ ô → Chờ kiểm tra, ghi người báo", r["trang_thai"] == "Chờ kiểm tra" and kp(c1)["ket_qua_boi"] == "qc@x")
loi = thu(lambda: A.kiem_tra(c1, "Có hiệu lực"))
kiem("QC (người làm) kiểm tra hiệu lực → API chặn ngay (trước cả controller)",
     loi and loi.endswith("mới kiểm tra hiệu lực.") and kp(c1)["trang_thai"] == "Chờ kiểm tra", loi)
d = F.get_doc(KP.PT, c9)
d.trang_thai = "Đóng"
kiem("Desk: QC đổi thẳng trạng thái Mở → Đóng (không đụng kết luận) → chặn", "Trưởng Ban ISO" in (thu(d.save) or ""))
d = F.get_doc(KP.PT, c1)
d.trang_thai = "Mở"
kiem("…nhưng rút lại phiếu chờ kiểm tra (Chờ kiểm tra → Mở) thì được", thu(d.save) is None)
A.luu(c1, json.dumps({}), gui=1)
d = F.get_doc(KP.PT, c1)
d.trang_thai, d.hieu_luc = "Đóng", "Có hiệu lực"
kiem("Desk: QC tự đóng / tự ghi Có hiệu lực → chặn", "Trưởng Ban ISO" in (thu(d.save) or ""))
d = F.get_doc(KP.PT, c1)
d.hieu_luc = "Có hiệu lực"
kiem("Desk: QC ghi kết luận kiểm tra mà không đổi trạng thái → vẫn chặn", "Trưởng Ban ISO" in (thu(d.save) or ""))
A.rut_lai(c1)
kiem("người làm rút lại để sửa (Chờ kiểm tra → Mở) khi chưa ai kiểm", kp(c1)["trang_thai"] == "Mở")
A.luu(c1, json.dumps({}), gui=1)

# ═══ 4. Ban ISO kiểm tra hiệu lực ═════════════════════════════════════════
print("\n-- kiểm tra hiệu lực, chưa hiệu lực, đóng, mở lại --")
F.vai("ISO Manager")
d = F.get_doc(KP.PT, c1)
d.trang_thai = "Đóng"
kiem("Desk: Ban ISO đóng mà chưa ghi kết luận Có hiệu lực → chặn", "Có hiệu lực" in (thu(d.save) or ""))
kiem("chưa hiệu lực mà không ghi làm gì tiếp → chặn", "nhận xét" in (thu(lambda: A.kiem_tra(c1, "Chưa hiệu lực"))
                                                                     or ""))
r = A.kiem_tra(c1, "Chưa hiệu lực", "Lưới mới vẫn sờn mép — đổi loại lưới inox")
x = kp(c1)
kiem("chưa hiệu lực → về Mở, đếm 1 lần, xoá ngày xong (làm lại), ghi người / ngày kiểm, nhận xét có ngày",
     r["trang_thai"] == "Mở" and x["so_lan"] == 1 and x["ngay_xong"] is None and x["kiem_boi"] == "iso@x"
     and "[09/10/2026 · Chưa hiệu lực] Lưới mới vẫn sờn mép" in x["nhan_xet"], x)
F.vai("SX QC")
A.luu(c1, json.dumps({"ket_qua": "Đã đổi lưới inox", "ngay_xong": "2026-10-09"}), gui=1)
kiem("báo lại → Chờ kiểm tra, kết luận cũ xoá để chờ lần kiểm mới, nhận xét cũ còn",
     kp(c1)["trang_thai"] == "Chờ kiểm tra" and kp(c1)["hieu_luc"] is None and "sờn mép" in kp(c1)["nhan_xet"])
F.vai("ISO Manager")
r = A.kiem_tra(c1, "Có hiệu lực", "Theo dõi 1 tuần không còn mạt")
kiem("có hiệu lực → Đóng, ngày kiểm hôm nay", r["trang_thai"] == "Đóng" and str(kp(c1)["kiem_ngay"]) == "2026-10-09")
F.vai("SX QC")
kiem("phiếu đã đóng: QC sửa → chặn", "đã đóng" in (thu(lambda: A.luu(c1, json.dumps({"ket_qua": "x"}))) or ""))
kiem("QC mở lại → chặn", thu(lambda: A.mo_lai(c1, "x")) is not None)
F.vai("ISO Manager")
kiem("mở lại không lý do → chặn", "lý do" in (thu(lambda: A.mo_lai(c1, " ")) or ""))
A.mo_lai(c1, "Lặp lại mạt ngày 15/10")
kiem("Ban ISO mở lại (ghi lý do vào nhận xét), kết luận xoá", kp(c1)["trang_thai"] == "Mở"
     and kp(c1)["hieu_luc"] is None and "Mở lại] Lặp lại mạt" in kp(c1)["nhan_xet"])
A.luu(c1, json.dumps({"ngay_xong": "2026-10-09"}), gui=1)
A.kiem_tra(c1, "Có hiệu lực", "ok")
F.vai("SX QC")
c2 = A.lap(json.dumps({"su_co": "SC-1"}))["name"]
kiem("phiếu cũ đã đóng → sự cố lập được phiếu mới, ô Số CAR trỏ phiếu mới", c2 != c1 and SC["SC-1"]["car_so"] == c2)

# ═══ 5. Xoá ═══════════════════════════════════════════════════════════════
print("\n-- xoá --")
F.vai("SX QC", u="qc2@x")
kiem("QC khác không xoá phiếu người khác", thu(lambda: A.xoa(c2)) is not None)
F.vai("SX QC")
F.bang(KP.PT)[c2]["creation"] = "2026-10-01 08:00:00"
kiem("người lập không xoá phiếu từ hôm trước", "Ban ISO" in (thu(lambda: A.xoa(c2)) or ""))
F.bang(KP.PT)[c2]["creation"] = "2026-10-09 08:00:00"
A.xoa(c2)
kiem("người lập xoá phiếu lập nhầm trong ngày → ô Số CAR của sự cố bỏ trỏ", c2 not in F.bang(KP.PT)
     and SC["SC-1"]["car_so"] in (None, ""))

# ═══ 6. Nhắc, sự cố, Tổng quan ════════════════════════════════════════════
print("\n-- hộp nhắc, phiếu sự cố, Tổng quan ATTP --")
c3 = A.lap(json.dumps({"su_co": "SC-2"}))["name"]
F.bang(KP.PT)[c3].update(ngay="2026-10-05", han="2026-10-07")
c4 = A.lap(json.dumps({"nguon": "Khác", "mo_ta": "Kho bao bì ẩm"}))["name"]
F.bang(KP.PT)[c4].update(trang_thai="Chờ kiểm tra", ngay_xong="2026-09-25", ngay="2026-09-20")
c5 = A.lap(json.dumps({"nguon": "Khác", "mo_ta": "Đèn kho vỡ"}))["name"]
F.bang(KP.PT)[c5].update(trang_thai="Chờ kiểm tra", ngay_xong="2026-10-05")
n = KP.nhac(F.hom_nay())
kiem("nhắc: phiếu Mở quá hạn; chờ kiểm tra quá 7 ngày (phiếu mới xong 4 ngày chưa nhắc)",
     [x["name"] for x in n["qua_han"]] == [c3] and [x["name"] for x in n["cho_kiem"]] == [c4], n)
m = [x for x in NH.tinh(F.hom_nay(), [], [], {}, khac_phuc=n) if x.get("nhom") == "khac_phuc"]
kiem("hộp nhắc: quá hạn mức CAO kèm số phiếu + hạn; chờ kiểm tra mức thường; sang #/qc/khacphuc",
     len(m) == 2 and m[0]["muc_do"] == "cao" and f"{c3} (hạn 07/10)" in m[0]["chi_tiet"]
     and m[1]["muc_do"] == "thuong" and all(x["route"] == "#/qc/khacphuc" for x in m), m)
hop = Q.nhac()["ds"]
kiem("sx.api.qc.nhac đưa phiếu khắc phục vào hộp nhắc", any("khắc phục" in x["tieu_de"] for x in hop))
ds = {x["name"]: x for x in Q.list_incidents(trang_thai="Mở", tu="2026-10-01", den="2026-10-09")["danh_sach"]}
kiem("sổ sự cố: mỗi sự cố kèm phiếu khắc phục (số, trạng thái, hạn); sự cố chưa có → None",
     ds["SC-2"]["khac_phuc"] == {"name": c3, "trang_thai": "Mở", "han": "2026-10-07"}
     and ds["SC-1"]["khac_phuc"]["name"] == c1, ds["SC-2"]["khac_phuc"])
F.vai("ISO Manager")
F.bang(KP.PT)[c1]["kiem_ngay"] = "2026-10-08"
t = {x["ma"]: x for x in ATTP.tong_quan()["linh_vuc"]}["khac_phuc"]
kiem("Tổng quan ATTP: thẻ Hành động khắc phục — 4 chưa đóng, 1 quá hạn → Đỏ; lập / đóng trong kỳ (30 ngày tới "
     "hôm qua: phiếu lập hôm nay chưa tính)",
     t["den"] == "do" and t["so"] == "4" and t["dong"][0] == "1 quá hạn · 2 chờ kiểm tra hiệu lực"
     and t["dong"][1] == "2 lập · 1 đóng trong kỳ", t)
q = A.tong_quan()
kiem("màn khắc phục: đếm theo trạng thái + quá hạn; thông tin sự cố gắn kèm; Ban ISO kiểm tra được",
     q["dem"] == {"Mở": 2, "Chờ kiểm tra": 2, "Đóng": 1, "qua_han": 1} and q["duoc_kiem"]
     and next(x for x in q["ds"] if x["name"] == c3)["su_co_info"]["mo_ta"] == "Thùng bột hở nắp", q["dem"])
F.vai("Stock User")
kiem("người ngoài QC không xem được", thu(A.tong_quan) is not None)
F.vai("SX QC")

# ═══ 7. Bản in, gói hồ sơ ═════════════════════════════════════════════════
print("\n-- BM.01.07, gói hồ sơ cho đoàn --")
if F.jinja2:
    h = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", A.in_bm0107(c1).split("</style>")[1]))
    kiem("BM.01.07: số phiếu, sự cố + mức CAO, điều không phù hợp, nguyên nhân, kết quả, kết luận, chỗ ký",
         all(s in h for s in ("BM.01.07", c1, "SC-1", "mức CAO", "Mạt kim loại", "Lưới sàng LS-01-M2 rách",
                              "Đã đổi lưới inox", "Có hiệu lực", "Trưởng Ban ISO")), h[:400])
kiem("danh mục hồ sơ: BM.01.07 là biểu mẫu app, đèn theo mảng khắc phục",
     HS.BIEU_MAU["BM.01.07"] == ("Phiếu hành động khắc phục", "khac_phuc"))
P.execute()
P.execute()
dm = [x for x in F.bang(HS.PT).values() if x["ma"] == "BM.01.07"]
kiem("patch d150: thêm dòng BM.01.07 vào danh mục hồ sơ, chạy lại không nhân đôi",
     len(dm) == 1 and dm[0]["nguon"] == HS.APP and dm[0]["bieu_mau"] == "BM.01.07")
if F.jinja2:
    g = HSA._in("BM.01.07", F.getdate("2026-10-01"), F.getdate("2026-10-09"))
    kiem("gói zip: các phiếu lập trong kỳ, một tệp (phiếu lập 20/09 ngoài kỳ không vào)",
         len(g) == 1 and g[0][0] == "phieu-khac-phuc.html" and c1 in g[0][1] and c4 not in g[0][1])

# ═══ 8. Màn hình ══════════════════════════════════════════════════════════
print("\n-- màn hình --")
kiem("patch có trong patches.txt", "sx.patches.d150_khac_phuc" in open("sx/patches.txt", encoding="utf-8").read())
qj = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
ui = open("sx/public/sx/components/qcui.js", encoding="utf-8").read()
kiem("route #/qc/khacphuc, nút thứ ba trong tab Sự cố (tab Sự cố sáng ở màn này)",
     "khacphuc: '/assets/sx/sx/views/qc_khacphuc.js'" in qj and "['khacphuc', 'Khắc phục']" in ui
     and "dang === 'khacphuc'" in qj)
ij = open("sx/public/sx/views/qc_incidents.js", encoding="utf-8").read()
kiem("phiếu sự cố: khối khắc phục (lập / mở phiếu), bỏ ô Số CAR gõ tay",
     "khoiKhacPhuc(m, s, api)" in ij and "sx.api.qc_khacphuc.lap" in ij and "'Số CAR (BM.01.07)'" not in ij)
js = open("sx/public/sx/views/qc_khacphuc.js", encoding="utf-8").read()
kiem("màn khắc phục: lưu / gửi kiểm tra, rút lại, kiểm tra hiệu lực, mở lại, xoá, in",
     all(s in js for s in ("sx.api.qc_khacphuc.luu", "sx.api.qc_khacphuc.rut_lai", "sx.api.qc_khacphuc.kiem_tra",
                           "sx.api.qc_khacphuc.mo_lai", "sx.api.qc_khacphuc.xoa", "sx.api.qc_khacphuc.in_bm0107")))

F.ket_thuc("KHACPHUC")
