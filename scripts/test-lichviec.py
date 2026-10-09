"""D146 (W21) — lịch việc định kỳ cho hồ sơ giấy (việc năm / quý lên hộp nhắc).

Vì sao phải có bài này:
  · Việc làm muộn mà hạn kỳ sau tính từ ngày làm → lịch trôi dần (tháng 11 thành tháng 12…).
  · Việc "một lần" làm xong vẫn nhắc mãi → người ta học cách bỏ qua hộp nhắc.
  · Hai việc tài liệu nêu (thử khôi phục dữ liệu T11/2026, thay bóng đèn bẫy T3/2027) phải có sẵn.

Nạp sx/qc/viec_dinh_ky.py, controller, sx/api/qc_lichviec.py, patch THẬT; frappe giả.
Chạy: python3 scripts/test-lichviec.py   (verify.sh gọi sẵn)
"""

import contextlib
import io
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

F.cai()
Q = F.nap_qc()
NH = sys.modules["sx.qc.nhac"]
VD = sys.modules["sx.qc.viec_dinh_ky"]
A = F.nap("sx.api.qc_lichviec", "sx/api/qc_lichviec.py")
VDC = F.nap("vd_ctl", "sx/qc/doctype/sx_viec_dinh_ky/sx_viec_dinh_ky.py")
F.dang_ky(VD.PT, VDC.SXViecDinhKy)
P = F.nap("sx.patches.d146_viec_dinh_ky", "sx/patches/d146_viec_dinh_ky.py")
P169 = F.nap("sx.patches.d169_bo_thau_rua_be", "sx/patches/d169_bo_thau_rua_be.py")
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")


def lan_cua(ten):
    return [r for r in (F.bang(VD.PT)[ten].get("ds_lan") or [])]


# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- kỳ sau, trạng thái (hàm thuần) --")
kiem("kỳ sau tính từ hạn cũ: năm +12, quý +3, tháng +1; một lần → hết",
     VD.ke_tiep("2026-11-30", "Năm") == date(2027, 11, 30) and VD.ke_tiep("2026-11-30", "Quý") == date(2027, 2, 28)
     and VD.ke_tiep("2026-01-31", "Tháng") == date(2026, 2, 28) and VD.ke_tiep("2026-11-30", "Một lần") is None)
tt = VD.trang_thai
kiem("trạng thái: quá hạn / sắp đến (trong số ngày nhắc trước) / còn hạn / ngừng",
     tt({"han": "2026-10-08"}, "2026-10-09")[0] == VD.QUA_HAN
     and tt({"han": "2026-10-20", "bao_truoc": 14}, "2026-10-09") == (VD.SAP_DEN, 11)
     and tt({"han": "2026-11-30", "bao_truoc": 30}, "2026-10-09")[0] == VD.CON_HAN
     and tt({"han": "2026-10-01", "ngung": 1}, "2026-10-09")[0] == VD.NGUNG)
kiem("nhắc trước trống / 0 → 14 ngày", tt({"han": "2026-10-23", "bao_truoc": 0}, "2026-10-09")[0] == VD.SAP_DEN
     and tt({"han": "2026-10-24"}, "2026-10-09")[0] == VD.CON_HAN)

# ═══ 2. Patch, ghi đã làm ══════════════════════════════════════════════════
print("\n-- hai việc tài liệu nêu, ghi đã làm --")
P.execute()
ten = {x["ten"]: n for n, x in F.bang(VD.PT).items()}
kp = ten["Thử khôi phục dữ liệu app từ bản sao lưu"]
den = ten["Thay bóng đèn bẫy côn trùng"]
kiem("patch: thử khôi phục dữ liệu hạn 30/11/2026, thay bóng đèn bẫy 31/03/2027, nhắc trước 30 ngày, hằng năm",
     (str(F.bang(VD.PT)[kp]["han"]), str(F.bang(VD.PT)[den]["han"]), F.bang(VD.PT)[kp]["bao_truoc"],
      F.bang(VD.PT)[kp]["chu_ky"]) == ("2026-11-30", "2027-03-31", 30, "Năm"))
F.bang(VD.PT)[kp]["han"] = "2026-11-20"
P.execute()
kiem("chạy lại patch: không nhân đôi, giữ hạn người ta đã sửa", len(F.bang(VD.PT)) == 2
     and F.bang(VD.PT)[kp]["han"] == "2026-11-20")
F.bang(VD.PT)[kp]["han"] = "2026-11-30"
q = {x["name"]: x for x in A.tong_quan()["ds"]}
kiem("09/10: thử khôi phục còn 52 ngày → Còn hạn", q[kp]["trang_thai"] == VD.CON_HAN and q[kp]["con"] == 52)
F.dat_ngay("2026-11-05")
kiem("05/11: vào cửa sổ nhắc 30 ngày → Sắp đến hạn", {x["name"]: x for x in A.tong_quan()["ds"]}[kp]["trang_thai"]
     == VD.SAP_DEN)
F.dat_ngay("2026-12-05")
kiem("ghi đã làm ngày sau hôm nay → chặn", "sau hôm nay" in (thu(lambda: A.da_lam(kp, json.dumps(
    {"ngay": "2026-12-06"}))) or ""))
r = A.da_lam(kp, json.dumps({"ngay": "2026-12-05", "ghi_chu": "BB-KP-01"}))
l = lan_cua(kp)
kiem("làm MUỘN 05/12 → hạn kỳ sau vẫn 30/11/2027 (tính từ hạn cũ), ghi lần làm + kỳ hạn + người",
     r["han"] == "2027-11-30" and len(l) == 1 and str(l[0]["han_ky"]) == "2026-11-30" and l[0]["nguoi"] == "qc@x"
     and l[0]["ghi_chu"] == "BB-KP-01" and str(F.bang(VD.PT)[kp]["lan_cuoi"]) == "2026-12-05", (r, l))
A.luu(json.dumps({"ten": "Đánh giá nội bộ lần đầu", "chu_ky": "Một lần", "han": "2026-12-20"}))
mot = next(n for n, x in F.bang(VD.PT).items() if x["ten"] == "Đánh giá nội bộ lần đầu")
r = A.da_lam(mot)
kiem("việc một lần làm xong → ngừng, không nhắc nữa", r["ngung"] == 1
     and mot not in json.dumps(VD.nhac("2027-06-01")))
kiem("ghi đã làm việc đã ngừng → chặn", "đã ngừng" in (thu(lambda: A.da_lam(mot)) or ""))
# W35 (D166): hạn để trống được khi chưa biết — hiện "Chưa đặt hạn", hộp nhắc nói ra (không im lặng).
r = A.luu(json.dumps({"ten": "Thôi nhiễm bao bì", "chu_ky": "2 năm"}))
x = {v["name"]: v for v in A.tong_quan()["ds"]}[r["name"]]
kiem("thêm việc chưa biết hạn → lưu được, trạng thái 'Chưa đặt hạn' (không phải Ngừng)",
     (x["han"], x["trang_thai"], x["con"]) == ("", VD.CHUA_HAN, None) and not F.bang(VD.PT)[r["name"]].get("han"), x)
F.dat_ngay("2026-12-20")
r2 = A.da_lam(r["name"], json.dumps({"ngay": "2026-12-15"}))
kiem("việc chưa đặt hạn mà đã làm → hạn kỳ sau tính từ NGÀY LÀM + 2 năm", r2["han"] == "2028-12-15", r2)
F.dat_ngay("2026-12-05")
kiem("chu kỳ lạ → chặn (controller)", "Chu kỳ" in (thu(lambda: A.luu(json.dumps({"ten": "x", "chu_ky": "Tuần",
                                                                                "han": "2027-01-01"}))) or ""))

print("\n-- W35: chu kỳ 2 năm, chưa đặt hạn, việc kiểm nghiệm --")
kiem("chu kỳ 2 năm = +24 tháng; đủ trong danh sách chọn, đúng thứ tự Select của doctype",
     VD.ke_tiep("2026-10-31", "2 năm") == date(2028, 10, 31) and A.tong_quan()["chu_ky"] == list(VD.THANG)
     and next(f for f in json.load(open("sx/qc/doctype/sx_viec_dinh_ky/sx_viec_dinh_ky.json", encoding="utf-8"))[
         "fields"] if f["fieldname"] == "chu_ky")["options"].split("\n") == list(VD.THANG))
fj = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_viec_dinh_ky/sx_viec_dinh_ky.json",
                                                 encoding="utf-8"))["fields"]}
kiem("doctype: hạn không bắt buộc; ô 'mẫu của' kiểm nghiệm = Nước / Nguyên liệu / Khác",
     not fj["han"].get("reqd") and fj["doi_tuong_kn"]["options"].split("\n")[1:] == list(VD.DOI_TUONG_KN))
kiem("trạng thái: không hạn → Chưa đặt hạn; ngừng thì vẫn Ngừng", tt({}, "2026-10-09") == (VD.CHUA_HAN, None)
     and tt({"ngung": 1}, "2026-10-09")[0] == VD.NGUNG)
F.dat_ngay("2026-10-09")
kn = A.luu(json.dumps({"ten": "Kiểm nghiệm nước sản xuất", "chu_ky": "Năm", "han": "2026-10-31", "bao_truoc": 30,
                       "doi_tuong_kn": "Nước"}))["name"]
kiem("việc kiểm nghiệm: không bấm Đã làm ở đây (lần làm = phiếu gửi mẫu ở màn Kiểm nghiệm)",
     "màn Kiểm nghiệm" in (thu(lambda: A.da_lam(kn)) or "") and not F.bang(VD.PT)[kn].get("ds_lan"))
kiem("mẫu của lạ → chặn (controller)", "Mẫu kiểm nghiệm" in (thu(lambda: A.luu(json.dumps(
    {"ten": "y", "chu_ky": "Năm", "han": "2027-01-01", "doi_tuong_kn": "Sản phẩm"}))) or ""))
A.luu(json.dumps({"name": kn, "ten": "Kiểm nghiệm nước sản xuất", "chu_ky": "Năm", "han": "2026-10-31",
                  "bao_truoc": 30}))
kiem("sửa việc không gửi ô mẫu của → giữ nguyên (màn cũ không xoá mất)", F.bang(VD.PT)[kn]["doi_tuong_kn"] == "Nước")
n = VD.nhac("2026-10-09")
kiem("nhắc tách: việc kiểm nghiệm sang phần kiem_nghiem (mảng Kiểm nghiệm), việc chưa đặt hạn có danh sách riêng",
     [x["ten"] for x in n["kiem_nghiem"]["sap_den"]] == ["Kiểm nghiệm nước sản xuất"]
     and "Kiểm nghiệm nước sản xuất" not in json.dumps([n["qua_han"], n["sap_den"], n["chua_han"]], ensure_ascii=False))
ds = NH.tinh(F.hom_nay(), [], [], {}, viec_dinh_ky=n)
kn_nh = [x for x in ds if x["nhom"] == "kiem_nghiem"]
kiem("hộp nhắc: việc kiểm nghiệm đến hạn → mảng Kiểm nghiệm, sang màn Kiểm nghiệm",
     [x["tieu_de"] for x in kn_nh] == ["1 mẫu nước / nguyên liệu / khác đến hạn gửi kiểm nghiệm"]
     and kn_nh[0]["route"] == "#/qc/kiemnghiem" and "31/10/2026" in kn_nh[0]["chi_tiet"], kn_nh)
F.bang(VD.PT)[kn]["han"] = None
ds = NH.tinh(F.hom_nay(), [], [], {}, viec_dinh_ky=VD.nhac("2026-10-09"))
kiem("việc kiểm nghiệm chưa đặt hạn → nhắc (mức thường), không im lặng",
     any(x["tieu_de"] == "1 việc kiểm nghiệm chưa đặt hạn" and x["muc_do"] == "thuong" for x in ds))
F.bang(VD.PT).pop(kn)
F.bang(VD.PT)["VD-TRONG"] = {"name": "VD-TRONG", "ten": "Xem xét lãnh đạo", "chu_ky": "Năm", "ngung": 0}
ds = NH.tinh(F.hom_nay(), [], [], {}, viec_dinh_ky=VD.nhac("2026-10-09"))
kiem("việc định kỳ chưa đặt hạn → '1 việc định kỳ chưa đặt hạn', sang màn Việc định kỳ",
     any(x["tieu_de"] == "1 việc định kỳ chưa đặt hạn" and x["route"] == "#/qc/lichviec"
         and "Xem xét lãnh đạo" in x["chi_tiet"] for x in ds))
F.bang(VD.PT).pop("VD-TRONG")

# W39 (D169): nước lấy thẳng tại vòi, không có bể chứa → việc "thau rửa bể" (nếu site có khai) ngừng, không xoá.
print("\n-- W39: ngừng việc thau rửa bể (không xoá) --")
la = P169.la_thau_rua_be
kiem("nhận: thau rửa bể, súc rửa bể chứa, vệ sinh bể nước, rửa bể., thau rửa bồn nước",
     all(la(t) for t in ("Thau rửa bể", "THAU RỬA BỂ NƯỚC định kỳ", "Súc rửa bể chứa nước 6 tháng/lần",
                         "Vệ sinh bể nước, thay lõi lọc", "Rửa bể.", "Thau rửa bồn nước inox")))
kiem("không nhận: bể ngâm, nước thải, bể phốt, bồn rửa tay, kiểm nghiệm nước tại vòi, kiểm tra bể (không làm sạch)",
     not any(la(t) for t in ("Vệ sinh bể ngâm đỗ", "Thau rửa bể nước thải", "Hút bể phốt", "Vệ sinh bồn rửa tay",
                             "Kiểm nghiệm nước sản xuất — mẫu nước tại vòi", "Kiểm tra bể nước", "Thau rửa thùng ủ",
                             "Thay bóng đèn bẫy côn trùng", "")))
for n, t, ng in (("VD-BE", "Thau rửa bể nước", 0), ("VD-NGAM", "Vệ sinh bể ngâm đỗ", 0),
                 ("VD-BE2", "Súc rửa bể chứa", 1)):
    F.bang(VD.PT)[n] = {"name": n, "ten": t, "chu_ky": "Quý", "han": "2026-12-31", "ngung": ng,
                        "ds_lan": [{"ngay": "2026-09-30"}] if n == "VD-BE" else []}
so = len(F.bang(VD.PT))
P169.execute()
_ra = io.StringIO()
with contextlib.redirect_stdout(_ra):
    P169.execute()
kiem("chạy lại: không in lại việc đã ngừng (log migrate chỉ kể việc vừa ngừng)", _ra.getvalue() == "", _ra.getvalue())
kiem("patch: thau rửa bể → ngừng; bể ngâm, việc khác giữ; không xoá, lần đã làm còn; chạy lại vô hại",
     F.bang(VD.PT)["VD-BE"]["ngung"] == 1 and F.bang(VD.PT)["VD-NGAM"]["ngung"] == 0
     and not F.bang(VD.PT)[kp].get("ngung") and F.bang(VD.PT)["VD-BE2"]["ngung"] == 1 and len(F.bang(VD.PT)) == so
     and F.bang(VD.PT)["VD-BE"]["ds_lan"] == [{"ngay": "2026-09-30"}]
     and {x["name"]: x["trang_thai"] for x in A.tong_quan()["ds"]}["VD-BE"] == VD.NGUNG)
for n in ("VD-BE", "VD-NGAM", "VD-BE2"):
    F.bang(VD.PT).pop(n)
kiem("patch d169 trong patches.txt", "sx.patches.d169_bo_thau_rua_be" in open("sx/patches.txt", encoding="utf-8").read())

# ═══ 3. Nhắc, quyền ═══════════════════════════════════════════════════════
print("\n-- hộp nhắc, quyền --")
F.dat_ngay("2027-04-02")
n = VD.nhac(F.hom_nay())
m = [x for x in NH.tinh(F.hom_nay(), [], [], {}, viec_dinh_ky=n) if x["route"] == "#/qc/lichviec"]
kiem("thay bóng đèn bẫy quá hạn 31/03 → nhắc mức CAO, tên việc ngay trên tiêu đề",
     any(x["muc_do"] == "cao" and "Thay bóng đèn bẫy" in x["tieu_de"] for x in m), m)
F.dat_ngay("2027-11-05")
n = VD.nhac(F.hom_nay())
m = [x for x in NH.tinh(F.hom_nay(), [], [], {}, viec_dinh_ky=n) if x["route"] == "#/qc/lichviec"]
kiem("kỳ sau của thử khôi phục (30/11/2027) vào cửa sổ → nhắc mức thường",
     any(x["muc_do"] == "thuong" and "khôi phục" in x["tieu_de"] for x in m), m)
F.dat_ngay("2026-10-09")
kiem("sx.api.qc.nhac truyền việc định kỳ vào hộp nhắc", "_viec_dinh_ky.nhac(d)" in open(
    "sx/api/qc.py", encoding="utf-8").read())
F.vai("Stock User")
kiem("người ngoài không xem được", thu(A.tong_quan) is not None)
F.vai("SX Quan Ly")
kiem("quản trị xem được", thu(A.tong_quan) is None)
F.vai("ISO Manager")
kiem("Ban ISO ghi được", thu(lambda: A.luu(json.dumps({"ten": "Xem xét lãnh đạo", "chu_ky": "Năm",
                                                        "han": "2026-12-15"}))) is None)
F.vai("SX QC")

# ═══ 4. Màn hình ══════════════════════════════════════════════════════════
print("\n-- màn hình --")
kiem("patch có trong patches.txt", "sx.patches.d146_viec_dinh_ky" in open("sx/patches.txt", encoding="utf-8").read())
kiem("route #/qc/lichviec + nút ở Hôm nay", "lichviec: '/assets/sx/sx/views/qc_lichviec.js'" in open(
    "sx/public/sx/views/qc.js", encoding="utf-8").read() and "#/qc/lichviec" in open(
    "sx/public/sx/views/qc_home.js", encoding="utf-8").read())
js = open("sx/public/sx/views/qc_lichviec.js", encoding="utf-8").read()
kiem("màn việc định kỳ: đã làm, thêm / sửa", "sx.api.qc_lichviec.da_lam" in js and "sx.api.qc_lichviec.luu" in js)

F.ket_thuc("LICHVIEC")
