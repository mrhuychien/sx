"""D149 (W27) — danh mục hồ sơ cho đoàn đánh giá, gói zip.

Vì sao phải có bài này:
  · Văn bản hết hạn / bắt buộc mà chưa có bản scan không bị cờ → đoàn tới mới biết.
  · CV 10 đã bị CV 21/CV-HGC thay mà dòng cũ vẫn "đang dùng" → đoàn đọc nhầm căn cứ.
  · Sản phẩm ghi TCCS không có văn bản ban hành (QĐ 11 → TCCS 01, QĐ 12 → TCCS 03) mà không ai thấy.
  · Cờ của hồ sơ app lệch đèn Tổng quan ATTP → hai màn nói hai điều.
  · Một tờ in lỗi làm hỏng cả gói zip khi đoàn đang ngồi chờ.

Nạp sx/qc/ho_so.py, controller, patch, sx/api/qc_hoso.py (và các hàm in thật); frappe giả.
Chạy: python3 scripts/test-hoso.py   (verify.sh gọi sẵn)
"""

import base64
import io
import json
import os
import re
import shutil
import sys
import tempfile
import types
import zipfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

F.cai()
Q = F.nap_qc()
for t in ("khieu_nai", "ncc", "kiem_xe", "tiep_nhan", "rework", "attp", "ho_so"):
    F.nap(f"sx.qc.{t}", f"sx/qc/{t}.py")
for t in ("qc_ncc", "qc_attp", "qc_cat", "qc_dvgh", "qc_khieunai", "qc_kiemnghiem", "qc_kiemxe", "qc_rework",
          "qc_thietbi", "qc_tiepnhan", "qc_hoso"):
    F.nap(f"sx.api.{t}", f"sx/api/{t}.py")
HS = sys.modules["sx.qc.ho_so"]
API = sys.modules["sx.api.qc_hoso"]
CT = F.nap("hs_ctl", "sx/qc/doctype/sx_ho_so_danh_muc/sx_ho_so_danh_muc.py")
F.dang_ky(HS.PT, CT.SXHoSoDanhMuc)
P = F.nap("sx.patches.d149_ho_so", "sx/patches/d149_ho_so.py")
P167 = F.nap("sx.patches.d167_ho_so_slm_bm0703", "sx/patches/d167_ho_so_slm_bm0703.py")
FR = sys.modules["frappe"]
FR.local = types.SimpleNamespace(response=F.Doc())


KHO = tempfile.mkdtemp(prefix="sx-hoso-")


class Tep(F.DocThuong):
    """File giả: ghi nội dung ra đĩa như frappe (private/files), đọc lại qua get_full_path."""

    def insert(self, ignore_permissions=False, **k):
        with open(os.path.join(KHO, self["file_name"]), "wb") as fh:
            fh.write(self.pop("content"))
        super().insert()
        self["file_url"] = f"/private/files/{self['file_name']}"
        F.bang("File")[self["name"]]["file_url"] = self["file_url"]
        return self

    def get_full_path(self):
        return os.path.join(KHO, self["file_name"])

    def get_content(self):          # frappe thật: giải mã thành chữ được là trả chữ — API không được dùng
        raise AssertionError("đọc tệp qua get_content() làm hỏng PDF / ảnh")


F.LOP["File"] = Tep
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")


def dong(**k):
    return dict({"ma": "X", "ten": "x", "nhom": "Pháp lý", "nguon": HS.TEP, "bat_buoc": 1, "ngung": 0}, **k)


def co_cua(ds, ma):
    x = next(x for x in ds if x["ma"] == ma)
    return dict(x, ly_do=[l["nd"] for l in x["ly_do"]], muc=[l["muc"] for l in x["ly_do"]])


# ═══ 1. Luật cờ (hàm thuần) ════════════════════════════════════════════════
print("\n-- cờ Đỏ / Vàng (hàm thuần) --")
kiem("mã văn bản so không phân biệt khoảng trắng / hoa thường", HS.chuan_ma("CV 10") == HS.chuan_ma("cv10"))
g = HS.gan_co([dong(ma="A", tep="/f/a.pdf"), dong(ma="B"), dong(ma="C", bat_buoc=0),
               dong(ma="D", tep="/f", het_han="2026-10-08"), dong(ma="E", tep="/f", het_han="2026-12-08"),
               dong(ma="E2", tep="/f", het_han="2026-12-09"), dong(ma="E0", tep="/f", het_han="2026-10-09"),
               dong(ma="G", nguon=HS.GIAY),
               dong(ma="H", nguon=HS.GIAY, noi_luu="Tủ ISO, bìa 3")], "2026-10-09")["ds"]
kiem("có bản scan, không hạn → không cờ; bắt buộc mà chưa scan → Đỏ; không bắt buộc → Vàng",
     co_cua(g, "A")["co"] is None and co_cua(g, "B")["co"] == HS.DO and co_cua(g, "C")["co"] == HS.VANG
     and co_cua(g, "B")["ly_do"] == ["Chưa có bản scan đính kèm"])
kiem("hết hạn → Đỏ, nói ngày; còn đúng 60 ngày → Vàng; 61 ngày → không cờ",
     co_cua(g, "D")["ly_do"] == ["Hết hạn 08/10/2026"] and co_cua(g, "D")["co"] == HS.DO
     and co_cua(g, "E")["co"] == HS.VANG and "còn 60 ngày" in co_cua(g, "E")["ly_do"][0]
     and co_cua(g, "E2")["co"] is None)
kiem("hết hạn đúng hôm nay → còn hiệu lực hôm nay: Vàng 'còn 0 ngày', chưa Đỏ",
     co_cua(g, "E0")["co"] == HS.VANG and "còn 0 ngày" in co_cua(g, "E0")["ly_do"][0])
kiem("bản giấy chưa ghi nơi lưu → Vàng; có nơi lưu → không cờ",
     co_cua(g, "G")["co"] == HS.VANG and co_cua(g, "H")["co"] is None)
DEN = {"su_co": {"ten": "Sự cố", "den": "do", "nhac": [{"tieu_de": "1 phiếu sự cố quá hạn"}]},
       "cat": {"ten": "Cát rang", "den": "vang", "nhac": [{"tieu_de": "Thiếu nhật ký cát"}]},
       "thiet_bi": {"ten": "Thiết bị đo", "den": "xanh", "nhac": []}}
g = HS.gan_co([dong(ma="BM.08.02", nguon=HS.APP, bieu_mau="BM.08.02"), dong(ma="BM.08.03", nguon=HS.APP,
                                                                            bieu_mau="BM.08.03"),
               dong(ma="BM.06.01", nguon=HS.APP, bieu_mau="BM.06.01"),
               dong(ma="BM.09.01", nguon=HS.APP, bieu_mau="BM.09.01")], "2026-10-09", DEN)["ds"]
kiem("hồ sơ app: cờ = đèn mảng ở Tổng quan ATTP, kèm việc đang treo; mảng xanh / không có đèn → không cờ",
     co_cua(g, "BM.08.02")["co"] == HS.DO
     and co_cua(g, "BM.08.02")["ly_do"] == ["Tổng quan ATTP — Sự cố đang Đỏ: 1 phiếu sự cố quá hạn"]
     and co_cua(g, "BM.08.03")["co"] == HS.VANG and co_cua(g, "BM.06.01")["co"] is None
     and co_cua(g, "BM.09.01")["co"] is None, [x["ly_do"] for x in g])
g = HS.gan_co([dong(ma="CV 21/CV-HGC", thay_the="CV 10", tep="/f"), dong(ma="cv10", tep="/f"),
               dong(ma="CV 9", tep="/f", ngung=1), dong(ma="CV 8", thay_the="CV 9", tep="/f")], "2026-10-09")["ds"]
kiem("văn bản cũ (CV 10) còn để đang dùng khi đã có CV 21/CV-HGC thay → Vàng, bảo đánh dấu Ngừng",
     co_cua(g, "cv10")["co"] == HS.VANG
     and co_cua(g, "cv10")["ly_do"] == ["Đã có văn bản thay thế: CV 21/CV-HGC — đánh dấu Ngừng"]
     and co_cua(g, "CV 21/CV-HGC")["co"] is None)
kiem("văn bản cũ đã Ngừng → không cờ (dòng ngừng không bao giờ bị cờ)", co_cua(g, "CV 9")["co"] is None)
SPS = [{"name": "SP-1", "so_cong_bo": "01/2023", "ten_san_pham": "Bánh 1", "tccs": "TCCS 01"},
       {"name": "SP-2", "so_cong_bo": "02/2023", "ten_san_pham": "Bánh 2", "tccs": "TCCS 02"},
       {"name": "SP-3", "so_cong_bo": "03/2023", "ten_san_pham": "Bánh 3", "tccs": ""},
       {"name": "SP-4", "so_cong_bo": "", "ten_san_pham": "Bánh 4", "tccs": "tccs 01"}]
g = HS.gan_co([dong(ma="Tự công bố SP", nguon=HS.APP, bieu_mau="TU_CONG_BO"), dong(ma="TCCS 01", tep="/f"),
               dong(ma="TCCS 02", tep="/f", ngung=1)], "2026-10-09", {}, SPS)["ds"]
t = co_cua(g, "Tự công bố SP")
kiem("tự công bố: sản phẩm chưa có số → Đỏ; chưa ghi TCCS → Vàng; TCCS không có văn bản (đang dùng) trong danh mục → Vàng",
     t["co"] == HS.DO and t["ly_do"] == ["1 sản phẩm chưa có số tự công bố: Bánh 4",
                                         "1 sản phẩm chưa ghi TCCS áp dụng: 03/2023",
                                         "TCCS 02 chưa có trong danh mục (văn bản ban hành TCCS)"]
     and t["muc"] == [HS.DO, HS.VANG, HS.VANG], t["ly_do"])
r = HS.gan_co([dong(ma="Z", nhom="Thiết bị đo", tep="/f"), dong(ma="B2", nhom="Sản phẩm", thu_tu=20, tep="/f"),
               dong(ma="B1", nhom="Sản phẩm", thu_tu=10), dong(ma="A", nhom="Pháp lý", het_han="2026-10-20",
                                                              tep="/f")], "2026-10-09")
kiem("xếp theo nhóm (thứ tự danh mục), rồi thứ tự; đếm cờ", [x["ma"] for x in r["ds"]] == ["A", "B1", "B2", "Z"]
     and r["dem"] == {"do": 1, "vang": 1})
kiem("kỳ gói: tháng chạm khoảng (qua năm), thứ Hai các tuần, năm",
     HS.thang_trong("2026-07-15", "2026-10-09") == ["2026-07", "2026-08", "2026-09", "2026-10"]
     and HS.thang_trong("2026-12-20", "2027-01-05") == ["2026-12", "2027-01"]
     and [str(x) for x in HS.thu_hai_trong("2026-10-01", "2026-10-14")] == ["2026-09-28", "2026-10-05", "2026-10-12"]
     and HS.nam_trong("2025-11-01", "2026-02-01") == [2025, 2026])
kiem("tên tệp trong zip: bỏ dấu, chỉ ký tự an toàn", HS.slug("Bản tự công bố — Đồng hồ/CV 21") == "Ban-tu-cong-bo-Dong-ho-CV-21")

# ═══ 2. Controller, patch ══════════════════════════════════════════════════
print("\n-- controller, patch --")
P.execute()
ds = F.bang(HS.PT)
theo = {x["ma"]: x for x in ds.values()}
kiem("patch: CV 21/CV-HGC thay CV 10; TCCS 01 theo QĐ 11; TCCS 03 theo QĐ 12; bản tự công bố; biểu mẫu app",
     theo["CV 21/CV-HGC"]["thay_the"] == "CV 10" and "QĐ 11" in theo["TCCS 01"]["can_cu"]
     and "QĐ 12" in theo["TCCS 03"]["can_cu"] and theo["Tự công bố SP"]["bieu_mau"] == "TU_CONG_BO"
     and all(theo[m]["nguon"] == HS.APP for m in ("BM.08.01", "BM.08.02", "KH.KN.01", "BM.PRP.03")), sorted(theo))
n = len(ds)
P.execute()
kiem("chạy lại patch: không nhân đôi", len(F.bang(HS.PT)) == n == len(P.DS))
kiem("mọi biểu mẫu app trong danh mục mẫu đều có hàm in (không có dòng 'App' mà gói luôn trống)",
     all(x["bieu_mau"] in HS.BIEU_MAU for x in ds.values() if x["nguon"] == HS.APP))
# W46 (D157): Frappe kiểm Select lúc insert (BaseDocument._validate_selects, kể cả trong patch) — mã có trong
# BIEU_MAU mà thiếu ở options thì patch d150 / d151 dừng migrate ("Biểu mẫu app cannot be BM.01.07") và màn Hồ sơ
# đánh giá không lưu được dòng đó. Frappe giả không đọc JSON nên kiểm thẳng ở đây: thêm mã vào BIEU_MAU là phải
# thêm vào options của DocType.
_hs = json.load(open("sx/qc/doctype/sx_ho_so_danh_muc/sx_ho_so_danh_muc.json", encoding="utf-8"))
_chon = {x for x in next(f for f in _hs["fields"] if f["fieldname"] == "bieu_mau")["options"].split("\n") if x.strip()}
kiem("Select 'Biểu mẫu app' có ĐÚNG các mã của BIEU_MAU (thiếu mã → migrate chết ở patch, màn không lưu được)",
     _chon == set(HS.BIEU_MAU), {"thiếu trong JSON": sorted(set(HS.BIEU_MAU) - _chon),
                                 "thừa trong JSON": sorted(_chon - set(HS.BIEU_MAU))})
loi = thu(lambda: F.get_doc({"doctype": HS.PT, "ma": "tccs01", "ten": "trùng", "nhom": "Sản phẩm",
                             "nguon": HS.TEP}).insert())
kiem("mã trùng (khác khoảng trắng / hoa thường) → chặn", loi and "Đã có hồ sơ mã TCCS 01" in loi, loi)
kiem("hồ sơ app mà chưa chọn biểu mẫu → chặn", "biểu mẫu app" in (thu(lambda: F.get_doc({
    "doctype": HS.PT, "ma": "M1", "ten": "x", "nhom": "Khác", "nguon": HS.APP}).insert()) or ""))
kiem("văn bản thay thế chính nó → chặn", "chính nó" in (thu(lambda: F.get_doc({
    "doctype": HS.PT, "ma": "M2", "ten": "x", "nhom": "Khác", "nguon": HS.TEP, "thay_the": "m 2"}).insert()) or ""))
d = F.get_doc({"doctype": HS.PT, "ma": " M3 ", "ten": " x ", "nhom": "Khác", "nguon": HS.GIAY, "bieu_mau": "BM.08.01"})
d.insert()
kiem("không phải hồ sơ app → bỏ biểu mẫu; mã / tên được cắt khoảng trắng",
     F.bang(HS.PT)[d.name]["bieu_mau"] is None and F.bang(HS.PT)[d.name]["ma"] == "M3")
F.bang(HS.PT).pop(d.name)

# ═══ 3. API: danh mục, tệp scan, quyền ═════════════════════════════════════
print("\n-- tong_quan, tệp scan, quyền --")
F.bang("SX San Pham Cong Bo").update({x["name"]: dict(x, ngung_san_xuat=0) for x in SPS})
F.bang("SX Su Co")["SC-1"] = {"name": "SC-1", "ngay": "2026-09-20", "trang_thai": "Mở", "muc_do": "Cao",
                              "xu_ly_ngay": "x", "dien_tap": 0}
F.vai("ISO Manager")
r = API.tong_quan()
c = {x["ma"]: co_cua(r["ds"], x["ma"]) for x in r["ds"]}
kiem("kỳ gói mặc định 3 tháng: 01/08 – hôm nay; Ban ISO sửa được", (r["tu"], r["den"]) == ("2026-08-01", "2026-10-09")
     and r["duoc_sua"])
kiem("CV 21/CV-HGC, TCCS 01, TCCS 03 chưa có bản scan → Đỏ", all(c[m]["co"] == HS.DO and "Chưa có bản scan"
                                                                in c[m]["ly_do"][0] for m in ("CV 21/CV-HGC", "TCCS 01",
                                                                                              "TCCS 03")))
kiem("BM.08.02 theo đèn Sự cố ở Tổng quan ATTP (phiếu quá hạn) → Đỏ", c["BM.08.02"]["co"] == HS.DO
     and "Sự cố đang Đỏ" in c["BM.08.02"]["ly_do"][0], c["BM.08.02"]["ly_do"])
kiem("tự công bố: lấy sản phẩm thật (W28) — Đỏ vì SP chưa có số, TCCS 02 không có văn bản",
     c["Tự công bố SP"]["co"] == HS.DO and any("TCCS 02" in x for x in c["Tự công bố SP"]["ly_do"]))
PDF = base64.b64encode(b"%PDF-1.4 tccs01").decode()
name = c["TCCS 01"]["name"]
kiem("đuôi lạ → chặn", "PDF, ảnh" in (thu(lambda: API.them_tep(name, "x.exe", PDF)) or ""))
kiem("nội dung không khớp đuôi (.pdf mà là PNG) → chặn", "không khớp" in (thu(lambda: API.them_tep(
    name, "x.pdf", base64.b64encode(b"\x89PNG....").decode())) or ""))
kiem("tệp quá 10 MB → chặn", "quá lớn" in (thu(lambda: API.them_tep(
    name, "x.pdf", base64.b64encode(b"%PDF" + b"0" * (10 * 1024 * 1024)).decode())) or ""))
t = API.them_tep(name, "TCCS 01 ban hanh.PDF", PDF)
f = next(x for x in F.bang("File").values() if x.get("attached_to_name") == name)
kiem("gắn bản scan: tệp riêng tư gắn dòng danh mục, tên theo mã; dòng hết cờ Đỏ",
     t["tep"] == "/private/files/TCCS-01.pdf" and f["is_private"] == 1
     and {x["ma"]: x for x in API.tong_quan()["ds"]}["TCCS 01"]["co"] is None, t)
API.luu(json.dumps({"ma": "GCN ATTP", "ten": "Giấy chứng nhận cơ sở đủ điều kiện ATTP", "nhom": "Pháp lý",
                    "nguon": HS.GIAY, "noi_luu": "Tủ ISO", "het_han": "2026-11-01", "bat_buoc": 1}))
g = co_cua(API.tong_quan()["ds"], "GCN ATTP")
kiem("thêm văn bản bản giấy có hạn: còn 23 ngày → Vàng", g["co"] == HS.VANG and "còn 23 ngày" in g["ly_do"][0], g)
API.luu(json.dumps({"name": g["name"], "ten": "GCN ATTP (sửa)", "het_han": ""}))
g2 = F.bang(HS.PT)[g["name"]]
kiem("sửa: chỉ đổi các ô gửi lên; xoá hạn → hết cờ", g2["ten"] == "GCN ATTP (sửa)" and g2["noi_luu"] == "Tủ ISO"
     and g2["het_han"] is None)
for vai, duoc in (("SX QC", False), ("Production Manager", False), ("SX Quan Ly", True)):
    F.vai(vai)
    kiem(f"{vai}: {'xem / sửa / tải được' if duoc else 'không xem, không sửa, không tải gói'}",
         all((thu(f) is None) == duoc for f in (API.tong_quan, lambda: API.luu(json.dumps({"name": g["name"]})),
                                                lambda: API.tai_goi("2026-10-01", "2026-10-09"))))
F.vai("ISO Manager")

# ═══ 4. Gói zip ════════════════════════════════════════════════════════════
print("\n-- gói zip cho đoàn --")
cv10 = API.luu(json.dumps({"ma": "CV 10", "ten": "Công văn 10 (cũ)", "nhom": "Pháp lý", "nguon": HS.TEP, "ngung": 1,
                           "ghi_chu": "Thay bằng CV 21/CV-HGC từ 08/10/2026"}))["name"]
API.them_tep(cv10, "cv10.pdf", base64.b64encode(b"%PDF-1.4 cv10").decode())   # có bản scan cũ vẫn không vào gói
base = {"docstatus": 1, "ghi_muon": 0, "nhap_lai_tu_giay": 0, "qc_user": "qc@x", "co_san_xuat_bot": 0,
        "reviewed_on": None, "phien_ban": 2}
F.bang("SX QC Round").update({
    "QC-1": dict(base, name="QC-1", ngay="2026-09-15", luot="Đầu sáng", rang_nhiet_do=262,
                 started_at=datetime(2026, 9, 15, 7, 0), finished_at=datetime(2026, 9, 15, 7, 30),
                 creation="2026-09-15 07:00:00")})
F.bang("SX Nhat Ky Cat")["CAT-1"] = {"name": "CAT-1", "ngay": "2026-09-15", "so_ngay_dung": 3, "ten_ncc": "Cát Lô",
                                     "thay_cat": 0, "doi_nguon": 0}
F.bang("SX Dien Tap Truy Xuat")["DT-1"] = {"name": "DT-1", "ngay": "2026-09-30", "ket_thuc": "2026-09-30 10:00:00",
                                           "ten_san_pham": "Bánh 1", "lo": "LO-1", "so_phut": 25,
                                           "can_bang_pt": 99.5, "dat": 1}
# W36 (D167): Sổ lưu mẫu SLM, sổ tiếp nhận BM.07.03 vào danh mục (patch) → gói có bản in từng tháng.
F.bang(HS.PT)["HS-SLM-GIAY"] = {"name": "HS-SLM-GIAY", "ma": "bm.07.03", "ten": "Sổ tiếp nhận (giấy cũ)", "nhom": "Khác",
                                "nguon": HS.GIAY, "noi_luu": "Kho"}
P167.execute()
P167.execute()
slm = [x for x in F.bang(HS.PT).values() if x["ma"] == "SLM"]
kiem("patch d167: thêm SLM (app lập, nhóm truy xuất…, bắt buộc); BM.07.03 đã có dòng (khác hoa thường) → giữ; "
     "chạy lại không nhân đôi", len(slm) == 1 and (slm[0]["nguon"], slm[0]["bieu_mau"], slm[0]["bat_buoc"])
     == (HS.APP, "SLM", 1) and not [x for x in F.bang(HS.PT).values() if x["ma"] == "BM.07.03"], slm)
F.bang(HS.PT).pop("HS-SLM-GIAY")
P167.execute()
kiem("… không có dòng BM.07.03 thì thêm (app lập, nhóm nhà cung cấp, nguyên liệu)",
     [(x["nguon"], x["bieu_mau"], x["nhom"]) for x in F.bang(HS.PT).values() if x["ma"] == "BM.07.03"]
     == [(HS.APP, "BM.07.03", "Nhà cung cấp, nguyên liệu")])
FR.local.response = F.Doc()
API.tai_goi("2026-09-01", "2026-10-09")
rs = FR.local.response
z = zipfile.ZipFile(io.BytesIO(rs.filecontent)) if rs.get("filecontent") else None
ten = z.namelist() if z else []
kiem("tải về đúng kiểu download, tên tệp theo kỳ", rs.get("type") == "download"
     and rs.get("filename") == "ho-so-attp_2026-09-01_2026-10-09.zip", (rs.get("type"), rs.get("filename")))
ml = z.read("00-MUC-LUC.html").decode("utf-8") if z else ""
mlt = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", ml))
kiem("mục lục: tự khai bảng mã; kỳ; căn cứ (Thay CV 10, QĐ 11, QĐ 12); cờ ĐỎ kèm lý do",
     '<meta charset="utf-8">' in ml and "Kỳ hồ sơ 01/09/2026 – 09/10/2026" in mlt and "Thay CV 10" in mlt
     and "Ban hành theo QĐ 11" in mlt and "Ban hành theo QĐ 12" in mlt and "ĐỎ" in mlt
     and "Chưa có bản scan đính kèm" in mlt, mlt[:400])
kiem("văn bản đã ngừng (CV 10) nằm ở mục 'đã ngừng / đã thay thế', không có thư mục trong gói",
     "Văn bản đã ngừng / đã thay thế" in mlt and "Thay bằng CV 21/CV-HGC" in mlt
     and not any("CV-10" in x for x in ten))
tccs = [x for x in ten if x.endswith("/TCCS-01.pdf")]
kiem("bản scan TCCS 01 nằm trong gói, đúng nội dung; mục lục chỉ đường tới nó",
     tccs and z.read(tccs[0]) == b"%PDF-1.4 tccs01" and tccs[0] in ml, [x for x in ten if "TCCS" in x])
bm1 = [x for x in ten if "BM.08.01" in x]
kiem("BM.08.01: một tệp mỗi tháng có lượt (tháng 9) — tờ ngày thật; tháng không có lượt thì không có tệp",
     len(bm1) == 1 and bm1[0].endswith("/2026-09.html") and "15/09/2026" in z.read(bm1[0]).decode("utf-8"), bm1)
kiem("BM.08.02 sổ sự cố CSV (BOM cho Excel); BM.08.03 mỗi tháng một tờ",
     any(x.endswith("BM.08.02/so-su-co.csv") for x in ten)
     and z.read(next(x for x in ten if x.endswith("so-su-co.csv"))).decode("utf-8").startswith("﻿")
     and sorted(x.rsplit("/", 1)[1] for x in ten if "BM.08.03" in x) == ["2026-09.html", "2026-10.html"])
dt = next((x for x in ten if x.endswith("dien-tap.html")), "")
kiem("diễn tập truy xuất trong kỳ: bảng các lần (lô, cân bằng, kết quả)",
     dt and "99.5%" in z.read(dt).decode("utf-8") and "LO-1" in z.read(dt).decode("utf-8"))
kiem("tự công bố: danh mục sản phẩm (số bản, TCCS)", any(x.endswith("danh-muc-san-pham.html") for x in ten)
     and "02/2023" in z.read(next(x for x in ten if x.endswith("danh-muc-san-pham.html"))).decode("utf-8"))
kiem("BM.PRP.03: một tờ mỗi tuần chạm kỳ (6 tuần)", len([x for x in ten if "BM.PRP.03" in x]) == 6)
kiem("W36: SLM và BM.07.03 mỗi tháng một tờ (tháng 9, tháng 10) — đúng mẫu giấy",
     sorted(x.rsplit("/", 1)[1] for x in ten if "-SLM/" in x) == ["2026-09.html", "2026-10.html"]
     and sorted(x.rsplit("/", 1)[1] for x in ten if "BM.07.03/" in x) == ["2026-09.html", "2026-10.html"]
     and "Lần BH 02" in z.read(next(x for x in ten if "-SLM/" in x)).decode("utf-8")
     and "BM.07.03 (QT.07)" in z.read(next(x for x in ten if "BM.07.03/" in x)).decode("utf-8"),
     [x for x in ten if "SLM" in x or "07.03" in x])
kiem("hồ sơ app kỳ này không có bản ghi (BM.08.04) → mục lục nói rõ, không có thư mục rỗng",
     "kỳ này không có bản ghi" in mlt and not any("BM.08.04" in x for x in ten))
goc = Q.month_sheets
Q.month_sheets = lambda *a: 1 / 0
FR.local.response = F.Doc()
API.tai_goi("2026-09-01", "2026-10-09")
Q.month_sheets = goc
z2 = zipfile.ZipFile(io.BytesIO(FR.local.response.filecontent))
ml2 = z2.read("00-MUC-LUC.html").decode("utf-8")
kiem("một tờ in lỗi (BM.08.01) → mục lục ghi 'Không in được', gói vẫn đủ phần còn lại",
     "Không in được: division by zero" in ml2 and any(x.endswith("TCCS-01.pdf") for x in z2.namelist()))
kiem("kỳ ngược / quá 24 tháng → chặn", "trước" in (thu(lambda: API.tai_goi("2026-10-09", "2026-10-01")) or "")
     and "24 tháng" in (thu(lambda: API.tai_goi("2024-01-01", "2026-10-09")) or ""))

# ═══ 5. Màn hình ══════════════════════════════════════════════════════════
print("\n-- màn hình --")
kiem("patch có trong patches.txt", all(f"sx.patches.{p}" in open("sx/patches.txt", encoding="utf-8").read()
                                      for p in ("d149_ho_so", "d167_ho_so_slm_bm0703")))
qj = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
ui = open("sx/public/sx/components/qcui.js", encoding="utf-8").read()
kiem("route #/qc/hoso; nút thứ ba 'Hồ sơ đánh giá' trong tab Xem xét",
     "hoso: '/assets/sx/sx/views/qc_hoso.js'" in qj and "['hoso', 'Hồ sơ đánh giá']" in ui)
js = open("sx/public/sx/views/qc_hoso.js", encoding="utf-8").read()
kiem("màn hồ sơ: tải gói (GET), gắn / bỏ bản scan, thêm / sửa / xoá",
     all(x in js for x in ("sx.api.qc_hoso.tai_goi?", "sx.api.qc_hoso.them_tep", "sx.api.qc_hoso.bo_tep",
                           "sx.api.qc_hoso.luu", "sx.api.qc_hoso.xoa", "tabXemXet('hoso')")))

shutil.rmtree(KHO, ignore_errors=True)
F.ket_thuc("HOSO")
