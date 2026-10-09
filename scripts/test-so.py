"""W43 (D172) — khung "Sổ" ghi theo dòng: BM.06.05, BM.PRP.06, BM.03.01, BM.03.02, BM.03.03.

Vì sao phải có bài này:
  · Sổ trên app phải giữ đúng luật của sổ giấy: không nhận ô lạ / sai kiểu / thiếu ô bắt buộc; dòng đã xác nhận là
    khóa; người ghi không tự xác nhận; ghi nhầm thì ngừng có lý do chứ không xóa; danh mục sửa được nhưng có vết.
  · Quyền theo định nghĩa sổ: Cơ điện ghi BM.06.05, QC xác nhận, Bảo vệ không xem được sổ bảo dưỡng…; Trưởng Ban ISO
    xem mọi sổ; người chưa được giao sổ nào không có tab Sổ.
  · Nghiệm thu md W43: Cơ điện ghi sửa máy rang, QC xác nhận, app nhắc hiệu chuẩn lại đồng hồ nhiệt (QT.06) tới khi
    có phiếu kiểm; máy sản xuất quá 6 tháng chưa bảo dưỡng → nhắc.
  · Nhắc: cột hạn (PCCC, kiểm định) đến / quá hạn; dòng chờ xác nhận quá 2 ngày; tháng chưa xem xét sau ngày 5, ghi
    bù sau lần xem thì xem lại.
  · Bản in: đầu trang chung, cột như giấy, "Ký trên phần mềm", lưới 12 tháng của BM.03.03, dòng ngừng gạch.

Nạp sx/qc/so.py, controller SX So / SX So Dong / SX So Xem / thiết bị đo, sx/api/qc_so.py, patch d172 THẬT trên frappe
giả (fakefrappe); seed thật sx/qc/seed/so.json.
Chạy: python3 scripts/test-so.py   (verify.sh gọi sẵn)
"""

import base64
import json
import os
import re
import sys
import tempfile
import types
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

FR = F.cai()
Q = F.nap_qc()
SO = sys.modules["sx.qc.so"]
NH = sys.modules["sx.qc.nhac"]
TBM = sys.modules["sx.qc.thiet_bi"]
for g in ("sx.config",):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m
R = F.nap("sx.config.roles", "sx/config/roles.py")
AT = F.nap("sx.qc.attp", "sx/qc/attp.py")
HS = F.nap("sx.qc.ho_so", "sx/qc/ho_so.py")
F.nap("sx.qc.mau_in", "sx/qc/mau_in.py")
F.nap("sx.api.qc_tailieu", "sx/api/qc_tailieu.py")
C_SO = F.nap("c_so", "sx/qc/doctype/sx_so/sx_so.py")
C_DONG = F.nap("c_dong", "sx/qc/doctype/sx_so_dong/sx_so_dong.py")
C_XEM = F.nap("c_xem", "sx/qc/doctype/sx_so_xem/sx_so_xem.py")
C_TB = F.nap("c_tb", "sx/qc/doctype/sx_thiet_bi_do/sx_thiet_bi_do.py")
C_KT = F.nap("c_kt", "sx/qc/doctype/sx_kiem_thiet_bi/sx_kiem_thiet_bi.py")
C_HS = F.nap("c_hs", "sx/qc/doctype/sx_ho_so_danh_muc/sx_ho_so_danh_muc.py")
A = F.nap("sx.api.qc_so", "sx/api/qc_so.py")
F.nap("sx.api.qc_danhgiancc", "sx/api/qc_danhgiancc.py")       # thẻ BM.07.01 trong danh sách sổ (W44)
ROLE_TAO = []
st = types.ModuleType("sx.setup")
st.dam_bao_role = lambda: ROLE_TAO.append(1) or []
sys.modules["sx.setup"] = st
P = F.nap("sx.patches.d172_so", "sx/patches/d172_so.py")
F.dang_ky(SO.PT, C_SO.SXSo, ten_theo="ma")
F.dang_ky(SO.PT_DONG, C_DONG.SXSoDong)
F.dang_ky(SO.PT_XEM, C_XEM.SXSoXem)
F.dang_ky(TBM.TB, C_TB.SXThietBiDo, ten_theo="ma")
F.dang_ky(TBM.KT, C_KT.SXKiemThietBi)
F.dang_ky(HS.PT, C_HS.SXHoSoDanhMuc)
F.bang_con(SO.PT, "cot", SO.PT_COT)
for o in SO.VAI_O:
    F.bang_con(SO.PT, o, SO.PT_VAI)
F.bang_con(SO.PT_DONG, "sua_doi", SO.PT_SUA)
kiem, thu = F.kiem, F.thu
TMP = tempfile.mkdtemp()


class TepGia(F.Document):
    """File của frappe: lưu nội dung ra đĩa, có file_url riêng tư."""

    def before_insert(self):
        ten = f"{F.SO['n']}-{self.file_name}"
        with open(os.path.join(TMP, ten), "wb") as fh:
            fh.write(self.content)
        self.file_url = f"/private/files/{ten}"
        self.content = None

    def get_full_path(self):
        return os.path.join(TMP, self.file_url.rsplit("/", 1)[-1])


F.dang_ky("File", TepGia)
FR.local = types.SimpleNamespace(response=types.SimpleNamespace())
F.dat_ngay("2026-10-09")

NGUOI = {"cd@x": ("Phạm Cơ Điện", ["SX Co Dien"]), "cd2@x": ("Trưởng Cơ Điện", ["SX Co Dien"]),
         "qc@x": ("Nguyễn Thị QC", ["SX QC"]), "goi@x": ("Lê QC Gói", ["SX QC Packing"]),
         "iso@x": ("Nguyễn Huy Chiến", ["ISO Manager"]), "gd@x": ("Giám Đốc", ["SX Quan Ly"]),
         "ql@x": ("Trần QLSX", ["Production Manager"]), "hc@x": ("Hoàng Hành Chính", ["SX Hanh Chinh"]),
         "bv@x": ("Vũ Bảo Vệ", ["SX Bao Ve"]), "gs@x": ("Đỗ Ghi Sổ", ["SX Ghi So"]), "ngoai@x": ("Khách", ["Guest"])}
for u, (ten, vs) in NGUOI.items():
    F.bang("User")[u] = {"name": u, "full_name": ten, "enabled": 1}
    for v in vs:
        F.bang("Has Role")[f"{u}-{v}"] = {"name": f"{u}-{v}", "parent": u, "parenttype": "User", "role": v}


def la(u):
    F.NGUOI["u"], F.NGUOI["roles"] = u, list(NGUOI[u][1])


def cot(*ds):
    return [dict(c, idx=i) for i, c in enumerate(ds, 1)]


# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- định nghĩa sổ, kiểm dữ liệu (hàm thuần) --")
kiem("mảng của sổ = mã thẻ Tổng quan ATTP + 'so_khac' (một danh sách, hai nơi khai — chốt khớp)",
     set(SO.MANG) == {x[0] for x in AT.LINH_VUC} and "so_khac" in SO.MANG)
SEED = json.load(open("sx/qc/seed/so.json", encoding="utf-8"))
W43 = ["BM.06.05", "BM.PRP.06", "BM.03.01", "BM.03.02", "BM.03.03"]
W44 = ["BM.PRP.04", "BM.PRP.05", "BM.PRP.07", "BM.05.01", "BM.05.02"]
kiem("seed: 5 sổ md W43 rồi 5 danh mục md W44, mã duy nhất", [x["ma"] for x in SEED] == W43 + W44)
loi_seed = {x["ma"]: SO.loi_dinh_nghia(dict(P.doc_so(x), cot=[dict(c, idx=i) for i, c in enumerate(
    P.doc_so(x)["cot"], 1)], **{o: [r["role"] for r in P.doc_so(x)[o]] for o in SO.VAI_O})) for x in SEED}
kiem("10 định nghĩa seed hợp lệ (khóa, kiểu, lựa chọn, Link được phép, cột hạn là ngày, cột gom nhóm)",
     not any(loi_seed.values()), loi_seed)
kiem("BM.03.01, BM.03.03 kiểu Danh mục, có cột app Ngày kiểm gần nhất, Hạn tiếp (báo trước 30 ngày), Số tem / giấy",
     all(x["kieu"] == "Danh mục" and {"ngay_kiem_gan_nhat", "han_tiep", "so_tem_giay"} <= {c["key"] for c in x["cot"]}
         and next(c for c in x["cot"] if c["key"] == "han_tiep").get("bao_truoc") == 30
         for x in SEED if x["ma"] in ("BM.03.01", "BM.03.03")))
kiem("BM.03.03: 12 cột tháng giấy → một ô nhiều lựa chọn thang_ke_hoach (1–12)",
     next(c for c in SEED[4]["cot"] if c["key"] == "thang_ke_hoach")["lua_chon"] == [str(i) for i in range(1, 13)])
kiem("BM.06.05: QC xác nhận (cột 'QC kiểm trước chạy' thành bước xác nhận), Trưởng Cơ điện xem tháng, hàm bao_duong",
     SEED[0]["vai_xac_nhan"] == ["SX QC", "SX QC Packing"] and SEED[0]["tinh_toan"] == "bao_duong"
     and "qc_kiem" not in {c["key"] for c in SEED[0]["cot"]} and SEED[0]["nhan_xac_nhan"] == "QC kiểm trước chạy (ký)"
     and "SX Co Dien" in SEED[0]["vai_xem_thang"])
DN_SAI = {"kieu": "Sổ", "mang": "abc", "tinh_toan": "eval(x)", "nhac_khong_ghi_ngay": -1,
          "cot": cot({"key": "Thiết bị", "nhan": "A", "kieu": "Data"}, {"key": "a", "nhan": "B", "kieu": "Select"},
                     {"key": "a", "nhan": "C", "kieu": "Data"}, {"key": "b", "nhan": "D", "kieu": "Link",
                                                                  "link_doctype": "User"},
                     {"key": "c", "nhan": "E", "kieu": "Data", "han": 1}, {"key": "ngay", "nhan": "F", "kieu": "Date"},
                     {"key": "d", "nhan": "G", "kieu": "Python"})}
ls = SO.loi_dinh_nghia(DN_SAI)
kiem("định nghĩa sai: kiểu sổ, mảng, hàm lạ, khóa có dấu, khóa trùng, Select không lựa chọn, Link ngoài danh sách, "
     "cột hạn không phải ngày, khóa 'ngay', kiểu lạ, số ngày âm → mỗi lỗi một câu",
     len(ls) == 11, ls)

C1 = cot({"key": "ten", "nhan": "Tên", "kieu": "Data", "bat_buoc": 1, "hien_ds": 1},
         {"key": "so_luong", "nhan": "Số lượng", "kieu": "Int"},
         {"key": "nhiet", "nhan": "Nhiệt", "kieu": "Float", "hien_ds": 1},
         {"key": "ngay_mua", "nhan": "Ngày mua", "kieu": "Date"},
         {"key": "luc", "nhan": "Lúc", "kieu": "Datetime"},
         {"key": "gio", "nhan": "Giờ", "kieu": "Time"},
         {"key": "loai", "nhan": "Loại", "kieu": "Select", "lua_chon": "A\nB", "hien_ds": 1},
         {"key": "thang", "nhan": "Tháng", "kieu": "MultiSelect", "lua_chon": "1\n2\n3\n12"},
         {"key": "ok", "nhan": "Đã vệ sinh", "kieu": "Check", "bat_buoc": 1, "hien_ds": 1},
         {"key": "han", "nhan": "Hạn", "kieu": "Date", "han": 1, "bao_truoc": 30},
         {"key": "ghi_chu", "nhan": "Ghi chú", "kieu": "Text"})
s, ls = SO.kiem_du_lieu(C1, {"ten": " Bình 01 ", "so_luong": "0", "nhiet": "12,5", "ngay_mua": "21/9/2026",
                             "luc": "2026-10-09T07:05", "gio": "7h05", "loai": "B", "thang": "12, 1", "ok": True,
                             "han": "2026-11-01", "ghi_chu": ""})
kiem("chuẩn hoá: chữ bỏ khoảng trắng, số 0 giữ, '12,5' → 12.5, ngày d/m/yyyy → ISO, giờ '7h05' → 07:05, nhiều lựa "
     "chọn theo thứ tự danh sách, ô trống không lưu",
     not ls and s == {"ten": "Bình 01", "so_luong": 0, "nhiet": 12.5, "ngay_mua": "2026-09-21",
                      "luc": "2026-10-09 07:05", "gio": "07:05", "loai": "B", "thang": ["1", "12"], "ok": 1,
                      "han": "2026-11-01"}, (s, ls))
s, ls = SO.kiem_du_lieu(C1, {"ten": "", "so_luong": "1.5", "nhiet": "abc", "ngay_mua": "31/2/2026", "gio": "25:00",
                             "loai": "C", "thang": ["13"], "ok": 0, "la": 1, "khac": 2})
kiem("sai: khóa lạ (một câu), thiếu ô bắt buộc, Check bắt buộc chưa tích, số nguyên / số / ngày / giờ sai, lựa chọn "
     "ngoài danh sách",
     len(ls) == 9 and ls[0] == "Cột lạ không có trong sổ: khac, la." and "Chưa ghi: Tên." in ls
     and "Chưa tích: Đã vệ sinh." in ls and any("số nguyên" in x for x in ls), ls)
kiem("chữ dài quá 140 ký tự → lỗi; dữ liệu không phải dict → lỗi",
     SO.kiem_du_lieu(C1, {"ten": "x" * 141, "ok": 1})[1] == ["Tên: dài quá 140 ký tự."]
     and SO.kiem_du_lieu(C1, "abc")[1] == ["Dữ liệu dòng sổ không hợp lệ."])
CL = cot({"key": "tb", "nhan": "Thiết bị", "kieu": "Link", "link_doctype": TBM.TB, "lua_chon": "Đồng hồ nhiệt"})
TRA = {"DH-1": {"name": "DH-1", "nhan": "Đồng hồ M1", "loai": "Đồng hồ nhiệt"},
       "M1": {"name": "M1", "nhan": "Máy rang", "loai": "Thiết bị sản xuất"}}
kiem("Link: không có → lỗi; sai loại (lựa chọn của cột = loại được chọn) → lỗi; đúng → nhận",
     SO.kiem_du_lieu(CL, {"tb": "X"}, lambda dt, v: TRA.get(v))[1] == ["Thiết bị: không có 'X'."]
     and "chỉ chọn đồng hồ nhiệt" in SO.kiem_du_lieu(CL, {"tb": "M1"}, lambda dt, v: TRA.get(v))[1][0]
     and SO.kiem_du_lieu(CL, {"tb": "DH-1"}, lambda dt, v: TRA.get(v)) == ({"tb": "DH-1"}, []))
kiem("tóm tắt: các cột hiện ở danh sách, Check chỉ hiện nhãn khi tích, số kiểu Việt",
     SO.tom_tat(C1, {"ten": "Bình 01", "nhiet": 12.5, "loai": "B", "ok": 1}) == "Bình 01 · 12,5 · B · Đã vệ sinh"
     and SO.tom_tat(C1, {"ten": "Bình 01", "ok": 0}) == "Bình 01" and len(SO.tom_tat(C1, {"ten": "y" * 300})) == 140)
h = SO.cac_han(C1, {"han": "2026-11-01"}, "2026-10-09")
kiem("cột hạn: còn 23 ngày, báo trước 30 → nhắc; hạn gần nhất là ngày đó",
     h == [{"key": "han", "nhan": "Hạn", "han": "2026-11-01", "con": 23, "bao_truoc": 30}] and SO.han_can_nhac(h[0])
     and SO.han_gan_nhat(C1, {"han": "2026-11-01"}) == "2026-11-01"
     and not SO.han_can_nhac(SO.cac_han(C1, {"han": "2026-12-01"}, "2026-10-09")[0]))

print("\n-- quyền, khóa (hàm thuần) --")
DN = {"kieu": SO.GHI_THEO_DONG, "vai_ghi": ["SX Co Dien"], "vai_xac_nhan": ["SX QC"], "vai_xem": ["Production Manager"],
      "vai_xem_thang": ["SX Co Dien"], "xem_cuoi_thang": 1}
q = lambda *r, sieu=False: SO.quyen(DN, set(r), sieu)  # noqa: E731
kiem("Cơ điện: ghi, xem, xem tháng — không xác nhận; QC: xác nhận, xem — không ghi",
     q("SX Co Dien") == {"ghi": True, "xac_nhan": False, "xem": True, "xem_thang": True, "co_xac_nhan": True}
     and q("SX QC") == {"ghi": False, "xac_nhan": True, "xem": True, "xem_thang": False, "co_xac_nhan": True})
kiem("QLSX chỉ xem; Trưởng Ban ISO xem + xem tháng (mọi sổ); Bảo vệ không gì; siêu quyền mọi việc",
     q("Production Manager")["xem"] and not q("Production Manager")["ghi"]
     and q("ISO Manager") == {"ghi": False, "xac_nhan": False, "xem": True, "xem_thang": True, "co_xac_nhan": True}
     and not q("SX Bao Ve")["xem"] and all(q("SX Quan Ly", sieu=True).values()))
kiem("sổ không có bước xác nhận: không ai xác nhận được, kể cả siêu quyền; không xem tháng nếu sổ không có",
     not SO.quyen(dict(DN, vai_xac_nhan=[]), {"SX Quan Ly"}, True)["xac_nhan"]
     and not SO.quyen(dict(DN, xem_cuoi_thang=0), {"ISO Manager"})["xem_thang"])
D0 = {"trang_thai": SO.DA_GHI, "nguoi_ghi": "cd@x", "ghi_luc": "2026-10-09 08:00:00"}
QG = q("SX Co Dien")
kiem("Ghi theo dòng: người ghi sửa trong ngày khi chưa xác nhận; người khác / hôm sau / đã xác nhận / đã ngừng → khóa",
     SO.loi_sua(DN, D0, "cd@x", QG, "2026-10-09") is None
     and SO.loi_sua(DN, D0, "cd2@x", QG, "2026-10-09") == "Chỉ người ghi dòng này sửa được."
     and "trong ngày ghi" in SO.loi_sua(DN, D0, "cd@x", QG, "2026-10-10")
     and "khóa" in SO.loi_sua(DN, dict(D0, trang_thai=SO.DA_XAC_NHAN), "cd@x", QG, "2026-10-09")
     and "ngừng" in SO.loi_sua(DN, dict(D0, trang_thai=SO.NGUNG), "cd@x", QG, "2026-10-09")
     and "quyền" in SO.loi_sua(DN, D0, "qc@x", q("SX QC"), "2026-10-09"))
DM = dict(DN, kieu=SO.DANH_MUC)
kiem("Danh mục: ai có quyền ghi cũng sửa được, cả hôm sau, cả dòng đã xác nhận (có vết)",
     SO.loi_sua(DM, dict(D0, trang_thai=SO.DA_XAC_NHAN), "cd2@x", QG, "2026-12-01") is None)
QQ = q("SX QC")
kiem("xác nhận: người ghi không tự xác nhận (kể cả có vai xác nhận); người sửa gần nhất cũng không; đã xác nhận / "
     "ngừng / không có vai → không",
     SO.loi_xac_nhan(D0, "qc@x", QQ) is None
     and "không tự xác nhận" in SO.loi_xac_nhan(D0, "cd@x", dict(QQ))
     and "không tự xác nhận" in SO.loi_xac_nhan(dict(D0, nguoi_cuoi="qc@x"), "qc@x", QQ)
     and SO.loi_xac_nhan(dict(D0, trang_thai=SO.DA_XAC_NHAN), "qc@x", QQ) == "Dòng đã xác nhận."
     and "quyền" in SO.loi_xac_nhan(D0, "cd2@x", QG))
kiem("ngừng: phải có lý do; người ghi trong ngày khi chưa xác nhận; hôm sau chỉ Trưởng Ban ISO; Danh mục: vai ghi",
     SO.loi_ngung(DN, D0, "cd@x", QG, False, "2026-10-09", " ") == "Ghi lý do ngừng."
     and SO.loi_ngung(DN, D0, "cd@x", QG, False, "2026-10-09", "ghi nhầm") is None
     and SO.loi_ngung(DN, D0, "cd@x", QG, False, "2026-10-10", "ghi nhầm") is not None
     and SO.loi_ngung(DN, D0, "iso@x", {}, True, "2026-12-10", "ghi nhầm") is None
     and SO.loi_ngung(DM, D0, "cd2@x", QG, False, "2026-12-10", "thanh lý") is None)

print("\n-- xem xét cuối tháng (hàm thuần) --")
kiem("mốc: ngày 1–5 tháng 10 chỉ tháng 8 trở về trước quá hạn; từ ngày 6 → tháng 9",
     SO.moc_xem("2026-10-05") == date(2026, 9, 1) and SO.moc_xem("2026-10-06") == date(2026, 10, 1))
DG = [{"ngay": "2026-09-03", "ghi_luc": "2026-09-03 10:00:00"}, {"ngay": "2026-08-20", "ghi_luc": "2026-08-20 09:00"}]
kiem("tháng 9 chưa xem → nhắc (ngày 9/10); tháng 8 đã xem → không; ghi bù tháng 8 sau lần xem → tháng 8 lại chờ",
     SO.thang_chua_xem(DG, [{"thang": "2026-08", "xem_luc": "2026-09-02 08:00:00"}], "2026-10-09") == ["2026-09"]
     and SO.thang_chua_xem(DG + [{"ngay": "2026-08-25", "ghi_luc": "2026-10-01 10:00:00"}],
                           [{"thang": "2026-08", "xem_luc": "2026-09-02 08:00:00"}], "2026-10-09")
     == ["2026-08", "2026-09"]
     and SO.thang_chua_xem(DG, [], "2026-10-03") == ["2026-08"])
kiem("tháng YYYY-MM → đầu, cuối tháng; sai dạng → lỗi",
     SO.tinh_thang("2026-02") == (date(2026, 2, 1), date(2026, 2, 28)) and thu(lambda: SO.tinh_thang("10/2026")))

print("\n-- BM.06.05: kiểm lại sau sửa chữa, bảo dưỡng định kỳ (hàm thuần) --")
DNB = {"tinh_toan": SO.BAO_DUONG, "cot": [{"key": "thiet_bi"}, {"key": "loai"}, {"key": "can_hieu_chuan"}]}
TB = {"DH-M1": {"name": "DH-M1", "loai": TBM.DONG_HO}, "M1": {"name": "M1", "loai": TBM.SAN_XUAT}}
tra = lambda dt, v: TB.get(v)  # noqa: E731
kiem("sửa chính đồng hồ nhiệt, chưa chọn thiết bị kiểm lại → tự điền chính nó; bảo dưỡng / sửa máy → không tự điền",
     SO.bo_sung(DNB, {"thiet_bi": "DH-M1", "loai": SO.BD_SUA}, tra)["can_hieu_chuan"] == "DH-M1"
     and "can_hieu_chuan" not in SO.bo_sung(DNB, {"thiet_bi": "DH-M1", "loai": SO.BD_BAO_DUONG}, tra)
     and "can_hieu_chuan" not in SO.bo_sung(DNB, {"thiet_bi": "M1", "loai": SO.BD_SUA}, tra)
     and "can_hieu_chuan" not in SO.bo_sung(dict(DNB, tinh_toan=""), {"thiet_bi": "DH-M1", "loai": SO.BD_SUA}, tra))
DB = [{"name": "D1", "ngay": "2026-10-05", "du_lieu": {"can_hieu_chuan": "DH-M1"}},
      {"name": "D2", "ngay": "2026-10-06", "du_lieu": {"can_hieu_chuan": "NC-X"}}]
TBK = {"DH-M1": {"ten": "Đồng hồ M1", "loai": TBM.DONG_HO}, "NC-X": {"ten": "Nam châm cũ", "loai": TBM.NAM_CHAM,
                                                                   "thanh_ly": 1}}
kiem("chưa có phiếu kiểm từ ngày sửa → phải kiểm lại (BM.06.02); kiểm trước ngày sửa không tính; đã kiểm từ ngày sửa "
     "→ xong; thiết bị thanh lý bỏ qua",
     SO.can_kiem_lai(DB, TBK, {}) == [{"dong": "D1", "ngay": "2026-10-05", "ma": "DH-M1", "ten": "Đồng hồ M1",
                                       "bieu_mau": "BM.06.02"}]
     and len(SO.can_kiem_lai(DB, TBK, {"DH-M1": "2026-10-04"})) == 1
     and SO.can_kiem_lai(DB, TBK, {"DH-M1": "2026-10-05"}) == [])
MAY = {"M1": {"ten": "Máy rang M1", "chu_ky_thang": 0, "tao": "2026-03-01"},
       "M2": {"ten": "Máy rang M2", "chu_ky_thang": 0, "tao": "2026-10-01"},
       "M3": {"ten": "Máy 3", "chu_ky_thang": 3, "tao": "2026-01-01"}}
DBD = [{"ngay": "2026-08-01", "du_lieu": {"thiet_bi": "M3", "loai": SO.BD_BAO_DUONG}},
       {"ngay": "2026-09-01", "du_lieu": {"thiet_bi": "M2", "loai": SO.BD_SUA}},
       {"ngay": "2026-09-15", "du_lieu": {"thiet_bi": "M1", "loai": SO.BD_SUA}}]
kiem("bảo dưỡng 6 tháng/lần: máy khai 1/3 chưa bảo dưỡng → quá hạn 1/9; máy mới khai không nhắc; sửa chữa không phải "
     "bảo dưỡng; chu kỳ riêng 3 tháng tính từ lần bảo dưỡng gần nhất",
     SO.qua_han_bao_duong(DBD, MAY, "2026-10-09") == [{"ma": "M1", "ten": "Máy rang M1", "han": "2026-09-01",
                                                       "lan_cuoi": None}]
     and SO.qua_han_bao_duong(DBD, MAY, "2026-11-02")[-1]["ma"] == "M3")
kiem("thiết bị sản xuất: không hạn kiểm (không quá hạn, không sự cố), chu kỳ mặc định 6 = bảo dưỡng",
     TBM.trang_thai({"loai": TBM.SAN_XUAT}, None, "2030-01-01") == (TBM.DANG_DUNG, None)
     and TBM.trang_thai({"loai": TBM.SAN_XUAT, "thanh_ly": 1}, None, "2030-01-01")[0] == TBM.THANH_LY
     and TBM.chu_ky({"loai": TBM.SAN_XUAT}) == 6 and TBM.SAN_XUAT in TBM.LOAI and TBM.SAN_XUAT not in TBM.LOAI_DO)

# ═══ 2. Patch d172 ════════════════════════════════════════════════════════
print("\n-- patch d172: tạo các sổ trong seed, máy sản xuất có mã, dòng hồ sơ — chỉ tạo cái thiếu --")
F.bang("Role").update({r: {"name": r} for r in R.VAI_MAC_DINH})
F.bang(HS.PT)["HS-1"] = {"name": "HS-1", "ma": "bm.03.02", "ten": "Sổ dịch bệnh (Ban ISO tự thêm)", "nguon": HS.GIAY}
P.execute()
kiem("tạo đủ sổ trong seed (site mới chạy d172 có luôn 5 danh mục W44); gọi tạo role trước (role W42 do "
     "after_migrate tạo — chạy SAU patch)", sorted(F.bang(SO.PT)) == sorted(W43 + W44) and ROLE_TAO == [1])
d65 = SO.dinh_nghia("BM.06.05")
kiem("BM.06.05: 9 cột theo thứ tự giấy, vai ghi / xác nhận / xem / xem tháng đúng seed, lựa chọn mỗi dòng một",
     [c["key"] for c in d65["cot"]] == ["thiet_bi", "loai", "noi_dung", "dau_mo", "gio_dung", "gio_ban_giao",
                                         "da_ve_sinh", "can_hieu_chuan", "nguoi_lam"]
     and d65["vai_ghi"] == ["SX Co Dien"] and d65["vai_xac_nhan"] == ["SX QC", "SX QC Packing"]
     and d65["vai_xem"] == ["Production Manager"] and d65["vai_xem_thang"] == ["Production Manager", "SX Co Dien"]
     and SO.lua_chon(d65["cot"][1]) == ["Bảo dưỡng", "Sửa chữa"] and d65["mang"] == "thiet_bi", d65)
kiem("máy sản xuất có mã trong BM.06.01 (TBSX-2024-00003, -00002, TBSX-2026-00001) vào danh mục, loại Thiết bị sản "
     "xuất; máy chưa cấp mã không tạo",
     sorted(k for k, v in F.bang(TBM.TB).items() if v["loai"] == TBM.SAN_XUAT)
     == ["TBSX-2024-00002", "TBSX-2024-00003", "TBSX-2026-00001"])
hs = {HS.chuan_ma(v["ma"]) for v in F.bang(HS.PT).values()}
kiem("dòng hồ sơ cho đoàn đánh giá: BM.06.05, PRP.06, 03.01, 03.03 thêm; BM.03.02 Ban ISO đã có (khác hoa thường) → "
     "giữ dòng của Ban ISO",
     {"BM.06.05", "BM.PRP.06", "BM.03.01", "BM.03.02", "BM.03.03"} <= hs and len(F.bang(HS.PT)) == 5
     and F.bang(HS.PT)["HS-1"]["ten"] == "Sổ dịch bệnh (Ban ISO tự thêm)")
doc = F.get_doc(SO.PT, "BM.PRP.06")
doc.ten = "Sổ khách (Ban ISO sửa)"
doc.append("cot", {"key": "so_cccd", "nhan": "Số CCCD", "kieu": "Data"})
doc.save()
P.execute()
kiem("chạy lại: không nhân đôi, không đè sổ Ban ISO đã sửa (tên, cột thêm)",
     len(F.bang(SO.PT)) == 10 and F.bang(SO.PT)["BM.PRP.06"]["ten"] == "Sổ khách (Ban ISO sửa)"
     and len(SO.dinh_nghia("BM.PRP.06")["cot"]) == 11 and len(F.bang(HS.PT)) == 5)

# ═══ 3. Quyền theo sổ, tab Sổ ═════════════════════════════════════════════
print("\n-- ai thấy sổ nào; tab Sổ chỉ cho người được giao sổ --")
THAY = {}
for u in ("cd@x", "qc@x", "goi@x", "ql@x", "bv@x", "hc@x", "iso@x", "gd@x", "gs@x"):
    la(u)
    THAY[u] = [x["ma"] for x in A.ds_so()["ds"]]
kiem("Cơ điện: BM.03.01, BM.06.05, hóa chất, kính (ghi); QC, QC gói: BM.06.05 (xác nhận), hóa chất, kính (xem) — "
     "QC thêm thẻ BM.07.01 (ký phiếu đánh giá NCC loại 1); QLSX: BM.03.03, bên quan tâm, rủi ro (ghi), BM.06.05, hóa "
     "chất, kính (xem), BM.PRP.06; Bảo vệ: BM.PRP.06; Hành chính: 3 sổ QT.03 + khám sức khỏe",
     THAY["cd@x"] == ["BM.03.01", "BM.06.05", "BM.PRP.04", "BM.PRP.05"]
     and THAY["qc@x"] == ["BM.06.05", "BM.07.01", "BM.PRP.04", "BM.PRP.05"]
     and THAY["goi@x"] == ["BM.06.05", "BM.PRP.04", "BM.PRP.05"]
     and THAY["ql@x"] == ["BM.03.03", "BM.05.01", "BM.05.02", "BM.06.05", "BM.PRP.04", "BM.PRP.05", "BM.PRP.06"]
     and THAY["bv@x"] == ["BM.PRP.06"] and THAY["hc@x"] == ["BM.03.01", "BM.03.02", "BM.03.03", "BM.PRP.07"], THAY)
kiem("Trưởng Ban ISO, Giám đốc thấy cả 10 sổ + thẻ BM.07.01; Ghi sổ không được giao sổ nào → danh sách trống",
     len(THAY["iso@x"]) == len(THAY["gd@x"]) == 11 and "BM.07.01" in THAY["gd@x"] and THAY["gs@x"] == [])
kiem("BM.PRP.07 (dữ liệu cá nhân): chỉ Hành chính, Trưởng Ban ISO, Giám đốc — QC, QLSX, Cơ điện không thấy",
     all("BM.PRP.07" not in THAY[u] for u in ("cd@x", "qc@x", "goi@x", "ql@x", "bv@x"))
     and all("BM.PRP.07" in THAY[u] for u in ("hc@x", "iso@x", "gd@x")))
kiem("co_so: Ghi sổ False (không có tab Sổ); Cơ điện, ISO True; Mua hàng True (thẻ BM.07.01 — W44)",
     not SO.co_so({"SX Ghi So"}) and SO.co_so({"SX Co Dien"}) and SO.co_so({"ISO Manager"}) and SO.co_so(set(), True)
     and SO.co_so({"Purchase User"}) and SO.vao_bm0701({"Purchase User"}) and not SO.vao_bm0701({"SX Co Dien"}))
la("ngoai@x")
kiem("không có vai app → không vào màn Sổ", isinstance(thu(lambda: A.ds_so()), str)
     and "quyền" in thu(lambda: A.ds_so()))
la("bv@x")
kiem("Bảo vệ không xem được sổ bảo dưỡng (không thuộc vai của sổ)", "quyền xem" in thu(lambda: A.xem("BM.06.05")))
la("qc@x")
kiem("QC không ghi được BM.06.05 (chỉ xác nhận)",
     "quyền ghi" in thu(lambda: A.ghi("BM.06.05", json.dumps({"du_lieu": {}}))))

# ═══ 4. Nghiệm thu BM.06.05: sửa máy rang → QC xác nhận → nhắc hiệu chuẩn lại đồng hồ nhiệt ══
print("\n-- BM.06.05: Cơ điện ghi sửa máy rang, QC xác nhận, app nhắc kiểm lại đồng hồ nhiệt --")
F.get_doc({"doctype": TBM.TB, "ma": "DH-M1", "ten": "Đồng hồ nhiệt máy rang M1", "loai": TBM.DONG_HO,
           "may": "M1"}).insert()
F.get_doc({"doctype": TBM.TB, "ma": "LS-01-M1", "ten": "Lưới sàng M1", "loai": TBM.LUOI}).insert()
la("cd@x")
goi = A.goi_y("BM.06.05", "thiet_bi")
goi_kl = A.goi_y("BM.06.05", "can_hieu_chuan")
kiem("chọn thiết bị: cả máy sản xuất lẫn thiết bị đo; cột 'cần kiểm lại' chỉ đồng hồ nhiệt, nam châm, lưới",
     {"TBSX-2024-00003", "DH-M1", "LS-01-M1"} <= {x["v"] for x in goi}
     and {x["v"] for x in goi_kl} == {"DH-M1", "LS-01-M1"})
DL = {"thiet_bi": "TBSX-2024-00003", "loai": "Sửa chữa", "noi_dung": "Thay cặp nhiệt, siết ốc buồng rang",
      "dau_mo": "Mỡ H1", "gio_dung": "8:00", "gio_ban_giao": "10:30", "da_ve_sinh": 1,
      "can_hieu_chuan": "DH-M1", "nguoi_lam": "Phạm Cơ Điện"}
r = A.ghi("BM.06.05", json.dumps({"ngay": "2026-10-09", "du_lieu": DL}))
D1 = r["name"]
row = F.bang(SO.PT_DONG)[D1]
kiem("ghi được: Đã ghi, người ghi + giờ, tóm tắt từ cột danh sách (mã máy + tên), giờ chuẩn hoá; báo phải kiểm lại",
     row["trang_thai"] == SO.DA_GHI and row["nguoi_ghi"] == "cd@x" and row["ghi_luc"]
     and row["tom_tat"].startswith("TBSX-2024-00003 Máy rang đỗ điện từ liên tục số 1 (M1) · Sửa chữa")
     and SO.doc_json(row["du_lieu"])["gio_dung"] == "08:00" and "DH-M1" in (r["kiem_lai"] or ""), (row, r))
NHAC = lambda: NH.tinh(F.hom_nay(), [], [], {}, so=SO.nhac(F.hom_nay()))  # noqa: E731
n = [x for x in NHAC() if "DH-M1" in x["tieu_de"]]
kiem("hộp nhắc: 'DH-M1 chưa kiểm lại sau sửa chữa' — mức CAO, mảng Thiết bị đo, sang màn Thiết bị đo",
     len(n) == 1 and n[0]["muc_do"] == "cao" and n[0]["nhom"] == "thiet_bi" and n[0]["route"] == "#/qc/thietbi"
     and "BM.06.02" in n[0]["chi_tiet"], n)
la("cd@x")
e = thu(lambda: A.xac_nhan(D1))
kiem("Cơ điện không xác nhận được (không có vai, cũng là người ghi)", e and "quyền" in e, e)
la("qc@x")
e = thu(lambda: A.ghi("BM.06.05", json.dumps({"du_lieu": dict(DL, can_hieu_chuan="TBSX-2024-00003")})))
kiem("QC không ghi được (vai ghi là Cơ điện)", e and "quyền ghi" in e, e)
r = A.xac_nhan(D1, "Đã kiểm buồng rang, không sót dụng cụ")
row = F.bang(SO.PT_DONG)[D1]
kiem("QC xác nhận: Đã xác nhận, người + giờ + ý kiến; vẫn nhắc kiểm lại đồng hồ nhiệt (chưa có phiếu)",
     row["trang_thai"] == SO.DA_XAC_NHAN and row["xac_nhan_boi"] == "qc@x" and row["xac_nhan_luc"]
     and row["y_kien_xac_nhan"].startswith("Đã kiểm") and r["kiem_lai"] and len(
         [x for x in NHAC() if "DH-M1" in x["tieu_de"]]) == 1, r)
la("cd@x")
e = thu(lambda: A.sua(D1, json.dumps({"du_lieu": dict(DL, noi_dung="sửa lại")})))
kiem("đã xác nhận → khóa, người ghi không sửa được", e and "khóa" in e, e)
d = F.get_doc(SO.PT_DONG, D1)
d.du_lieu = json.dumps(dict(DL, noi_dung="sửa trên Desk"))
e = thu(d.save)
kiem("sửa dòng đã xác nhận trên Desk (không qua app) → chặn ở controller", e and "khóa" in e, e)
d = F.get_doc(SO.PT_DONG, D1)
d.trang_thai = SO.DA_GHI
e = thu(d.save)
kiem("đổi trạng thái trên Desk → chặn", e and "chỉ đổi trên app" in e, e)
la("qc@x")
F.get_doc({"doctype": TBM.KT, "thiet_bi": "DH-M1", "ngay": "2026-10-09", "hinh_thuc": TBM.NOI_BO, "chuan_1": "100",
           "doc_1": "100,5", "ket_qua": TBM.DAT}).insert()
kiem("ghi phiếu kiểm đồng hồ nhiệt (BM.06.02) từ ngày sửa → hết nhắc kiểm lại",
     not [x for x in NHAC() if "DH-M1" in x["tieu_de"]])
e = thu(lambda: F.get_doc({"doctype": TBM.KT, "thiet_bi": "TBSX-2024-00003", "ngay": "2026-10-09",
                           "hinh_thuc": TBM.NOI_BO, "ket_qua": TBM.DAT}).insert())
kiem("máy sản xuất không ghi phiếu hiệu chuẩn được (bảo dưỡng ghi sổ BM.06.05)", e and "không hiệu chuẩn" in e, e)

la("cd@x")
r = A.ghi("BM.06.05", json.dumps({"du_lieu": {"thiet_bi": "LS-01-M1", "loai": "Sửa chữa", "noi_dung": "Hàn khung lưới",
                                              "da_ve_sinh": 1, "nguoi_lam": "Phạm Cơ Điện"}}))
D2 = r["name"]
kiem("sửa chính lưới sàng mà không chọn thiết bị kiểm lại → app tự điền LS-01-M1, nhắc kiểm lại theo BM.06.04",
     SO.doc_json(F.bang(SO.PT_DONG)[D2]["du_lieu"]).get("can_hieu_chuan") == "LS-01-M1"
     and any("LS-01-M1" in x["tieu_de"] and "BM.06.04" in x["chi_tiet"] for x in NHAC()))
e = thu(lambda: A.ghi("BM.06.05", json.dumps({"du_lieu": dict(DL, can_hieu_chuan="TBSX-2024-00002")})))
kiem("cột 'cần kiểm lại' chọn máy sản xuất → lỗi (chỉ thiết bị đo)", e and "chỉ chọn" in e, e)
e = thu(lambda: A.ghi("BM.06.05", json.dumps({"du_lieu": {"thiet_bi": "TBSX-2024-00003", "loai": "Bảo dưỡng"}})))
kiem("thiếu ô bắt buộc (nội dung, đã vệ sinh, người làm) → một câu báo đủ ô thiếu",
     e and "Chưa ghi: Nội dung" in e and "Chưa tích: Đã vệ sinh" in e and "Chưa ghi: Người làm" in e, e)
e = thu(lambda: A.ghi("BM.06.05", json.dumps({"du_lieu": dict(DL, gio_dung="99:99", la="x")})))
kiem("ô lạ, giờ sai → lỗi", e and "Cột lạ" in e and "giờ" in e, e)
e = thu(lambda: A.ghi("BM.06.05", json.dumps({"ngay": "2026-10-10", "du_lieu": DL})))
kiem("sổ ghi theo dòng: ngày sau hôm nay → lỗi", e and "sau hôm nay" in e, e)

print("\n-- sửa trong ngày, ngừng có lý do, lịch sử --")
r = A.sua(D2, json.dumps({"du_lieu": {"thiet_bi": "LS-01-M1", "loai": "Sửa chữa", "noi_dung": "Hàn khung, thay lưới",
                                      "da_ve_sinh": 1, "nguoi_lam": "Phạm Cơ Điện", "can_hieu_chuan": "LS-01-M1"}}))
d = F.get_doc(SO.PT_DONG, D2)
s0 = d.sua_doi[0]
kiem("người ghi sửa trong ngày: lưu, nối một dòng lịch sử (trước / sau, người, giờ)",
     r["doi"] == 1 and len(d.sua_doi) == 1 and s0["hanh_dong"] == "Sửa" and s0["nguoi"] == "cd@x"
     and SO.doc_json(s0["truoc"])["du_lieu"]["noi_dung"] == "Hàn khung lưới"
     and SO.doc_json(s0["sau"])["du_lieu"]["noi_dung"] == "Hàn khung, thay lưới")
kiem("lưu lại y nguyên → không thêm dòng lịch sử",
     A.sua(D2, json.dumps({"du_lieu": SO.doc_json(d.du_lieu)}))["doi"] == 0
     and len(F.get_doc(SO.PT_DONG, D2).sua_doi) == 1)
la("cd2@x")
kiem("Cơ điện khác không sửa được dòng của người khác (sổ ghi theo dòng)",
     "Chỉ người ghi" in (thu(lambda: A.sua(D2, json.dumps({"du_lieu": {}}))) or ""))
la("qc@x")
e = thu(lambda: A.xac_nhan(D2))
kiem("QC xác nhận được dòng Cơ điện ghi (người sửa gần nhất cũng là Cơ điện)", e is None, e)
F.dat_ngay("2026-10-10")
la("cd@x")
r = A.ghi("BM.06.05", json.dumps({"du_lieu": dict(DL, can_hieu_chuan="", noi_dung="Ghi nhầm máy")}))
D3 = r["name"]
F.dat_ngay("2026-10-11")
e = thu(lambda: A.sua(D3, json.dumps({"du_lieu": dict(DL, noi_dung="sửa hôm sau")})))
kiem("hôm sau người ghi không sửa được nữa", e and "trong ngày ghi" in e, e)
e = thu(lambda: A.ngung(D3, "ghi nhầm"))
kiem("hôm sau người ghi cũng không ngừng được", e and "Trưởng Ban ISO" in e, e)
la("iso@x")
kiem("Trưởng Ban ISO ngừng phải có lý do", "lý do" in (thu(lambda: A.ngung(D3, "")) or ""))
A.ngung(D3, "Ghi nhầm máy — đã ghi lại dòng đúng")
d = F.get_doc(SO.PT_DONG, D3)
kiem("ngừng: trạng thái Ngừng, lý do, lịch sử 'Ngừng'; dòng vẫn còn (không xóa)",
     d.trang_thai == SO.NGUNG and d.ly_do_ngung.startswith("Ghi nhầm") and d.sua_doi[-1]["hanh_dong"] == "Ngừng"
     and D3 in F.bang(SO.PT_DONG))
la("qc@x")
kiem("dòng ngừng không xác nhận được, không vào nhắc chờ xác nhận",
     "ngừng" in (thu(lambda: A.xac_nhan(D3)) or "") and not any(D3 in str(x) for x in SO.nhac(F.hom_nay())["ds"]))
F.dat_ngay("2026-10-09")

# ═══ 5. Danh mục BM.03.01, BM.03.03 ══════════════════════════════════════
print("\n-- Danh mục (PCCC, kiểm định): sửa có vết, ngừng không xóa, nhắc hạn --")
la("hc@x")
P1 = A.ghi("BM.03.01", json.dumps({"du_lieu": {"loai_thiet_bi": "Bình CO2 5 kg", "ma_so": "BCC-01",
                                                "vi_tri": "Kho thành phẩm", "tinh_trang": "Tốt",
                                                "ngay_kiem_gan_nhat": "2026-09-15", "han_tiep": "2026-10-25"}}))["name"]
P2 = A.ghi("BM.03.01", json.dumps({"du_lieu": {"loai_thiet_bi": "Bình bột 4 kg", "ma_so": "BCC-02",
                                                "vi_tri": "Xưởng bánh", "tinh_trang": "Tốt",
                                                "han_tiep": "2026-10-01"}}))["name"]
n = [x for x in NHAC() if x["tieu_de"].startswith("BM.03.01")]
kiem("hạn kiểm / nạp: BCC-02 quá hạn, BCC-01 còn 16 ngày (báo trước 30) → hai mục nhắc, mảng Sổ khác, sang sổ",
     len(n) == 2 and all(x["nhom"] == "so_khac" and x["route"] == "#/so/BM.03.01" and x["muc_do"] == "thuong"
                         for x in n) and "quá hạn" in n[0]["tieu_de"] and "BCC-02" in n[0]["chi_tiet"]
     and "còn 16 ngày" in n[1]["chi_tiet"], n)
la("cd@x")
A.sua(P2, json.dumps({"du_lieu": {"loai_thiet_bi": "Bình bột 4 kg", "ma_so": "BCC-02", "vi_tri": "Xưởng bánh",
                                  "tinh_trang": "Đã nạp lại", "ngay_kiem_gan_nhat": "2026-10-08",
                                  "han_tiep": "2027-04-08"}}))
d = F.get_doc(SO.PT_DONG, P2)
kiem("Danh mục: người khác có quyền ghi (Cơ điện) sửa được dòng Hành chính ghi, hôm sau cũng được — có vết",
     d.sua_doi[-1]["nguoi"] == "cd@x" and SO.doc_json(d.du_lieu)["tinh_trang"] == "Đã nạp lại"
     and d.han_gan_nhat == "2027-04-08" and len([x for x in NHAC() if x["tieu_de"].startswith("BM.03.01")]) == 1)
A.ngung(P1, "Bình hỏng, thanh lý")
la("hc@x")
x1 = A.xem("BM.03.01")
x2 = A.xem("BM.03.01", ngung=1)
kiem("ngừng: không còn trong danh mục đang dùng, không nhắc hạn; xem cả dòng ngừng vẫn thấy",
     [x["name"] for x in x1["ds"]] == [P2] and {x["name"] for x in x2["ds"]} == {P1, P2}
     and not [x for x in NHAC() if x["tieu_de"].startswith("BM.03.01")])
la("hc@x")
K1 = A.ghi("BM.03.03", json.dumps({"du_lieu": {"thiet_bi": "Nồi hơi", "ma_thiet_bi": "NH-01", "khu_vuc": "Luộc",
                                                "thang_ke_hoach": ["3", "9"], "han_tiep": "2027-03-20",
                                                "so_tem_giay": "KĐ-123"}}))["name"]
kiem("BM.03.03: tháng kế hoạch nhiều lựa chọn, tóm tắt có tháng và hạn",
     F.bang(SO.PT_DONG)[K1]["tom_tat"] == "Nồi hơi · NH-01 · 3, 9 · 20/03/2027")
la("ql@x")
kiem("tìm không dấu: 'noi hoi' thấy dòng Nồi hơi; 'xyz' không thấy",
     [x["name"] for x in A.xem("BM.03.03", q="noi hoi")["ds"]] == [K1] and not A.xem("BM.03.03", q="xyz")["ds"])

print("\n-- Danh mục có bước xác nhận (khung W44): sửa dòng đã xác nhận → chờ xác nhận lại --")
la("iso@x")
F.get_doc(P.doc_so({"ma": "BM.TEST", "ten": "Danh mục thử", "kieu": "Danh mục", "mang": "so_khac",
                    "vai_ghi": ["SX Co Dien"], "vai_xac_nhan": ["ISO Manager"],
                    "cot": [{"key": "ten", "nhan": "Tên", "kieu": "Data", "bat_buoc": 1, "hien_ds": 1}]})).insert()
la("cd@x")
T1 = A.ghi("BM.TEST", json.dumps({"du_lieu": {"ten": "Javel 5%"}}))["name"]
la("iso@x")
A.xac_nhan(T1)
la("cd2@x")
A.sua(T1, json.dumps({"du_lieu": {"ten": "Javel 6%"}}))
d = F.get_doc(SO.PT_DONG, T1)
kiem("sửa dòng đã xác nhận → về Đã ghi, bỏ người xác nhận cũ (lưu trong lịch sử)",
     d.trang_thai == SO.DA_GHI and not d.xac_nhan_boi and SO.doc_json(d.sua_doi[-1]["truoc"])["xac_nhan"]["boi"]
     == "iso@x")
F.NGUOI["u"], F.NGUOI["roles"] = "cd2@x", ["SX Co Dien", "ISO Manager"]
kiem("người sửa gần nhất (dù có vai xác nhận) không tự xác nhận", "không tự xác nhận" in (thu(lambda: A.xac_nhan(T1))
                                                                                     or ""))

# ═══ 6. Xem xét cuối tháng (BM.PRP.06) ═══════════════════════════════════
print("\n-- PRP.06: khách vào xưởng, xem xét cuối tháng, ghi bù --")
F.dat_ngay("2026-09-20")
la("bv@x")
KH = {"ho_ten": "Nguyễn Văn Khách", "don_vi": "Orion", "ly_do": "Đánh giá", "khu_vuc": "Xưởng bánh", "khong_om": 1,
      "bao_ho_du": 1, "nguoi_dan": "Trần QLSX", "gio_vao": "08:30"}
V1 = A.ghi("BM.PRP.06", json.dumps({"du_lieu": KH}))["name"]
A.sua(V1, json.dumps({"du_lieu": dict(KH, gio_ra="11:00")}))
kiem("Bảo vệ ghi lúc khách vào, ghi giờ ra trong ngày",
     SO.doc_json(F.bang(SO.PT_DONG)[V1]["du_lieu"])["gio_ra"] == "11:00")
e = thu(lambda: A.ghi("BM.PRP.06", json.dumps({"du_lieu": dict(KH, khong_om=0)})))
kiem("khách chưa khai không ốm (ô bắt buộc tích) → không ghi được", e and "Chưa tích: Không ốm" in e, e)
F.dat_ngay("2026-10-09")
n = [x for x in NHAC() if x["tieu_de"].startswith("BM.PRP.06")]
kiem("9/10: tháng 9 chưa xem xét → nhắc (mảng Sổ khác), chỉ Trưởng Ban ISO xem tháng",
     len(n) == 1 and "09/2026" in n[0]["tieu_de"] and n[0]["nhom"] == "so_khac"
     and "Trưởng Ban ISO" in n[0]["chi_tiet"], n)
la("bv@x")
kiem("Bảo vệ không xem xét tháng được", "quyền xem xét" in (thu(lambda: A.xem_thang("BM.PRP.06", "2026-09")) or ""))
la("iso@x")
kiem("tháng chưa tới / không có dòng / sai dạng → lỗi",
     "chưa tới" in thu(lambda: A.xem_thang("BM.PRP.06", "2026-11"))
     and "không có dòng" in thu(lambda: A.xem_thang("BM.PRP.06", "2026-08"))
     and "YYYY-MM" in thu(lambda: A.xem_thang("BM.PRP.06", "9/2026")))
r = A.xem_thang("BM.PRP.06", "2026-09", "Đủ khai sức khỏe, có người dẫn")
x = A.xem("BM.PRP.06", tu="2026-09-01")["xem_thang"]
kiem("xem xét tháng 9: hết nhắc; màn sổ hiện 'Ký trên phần mềm: Nguyễn Huy Chiến' + nhận xét",
     not [n for n in NHAC() if n["tieu_de"].startswith("BM.PRP.06")] and r["so_dong"] == 1
     and x["ky"].startswith("Ký trên phần mềm: Nguyễn Huy Chiến, 09/10/2026") and not x["can_xem_lai"], x)
F.dat_ngay("2026-10-12")
la("bv@x")
A.ghi("BM.PRP.06", json.dumps({"ngay": "2026-09-28", "du_lieu": dict(KH, ho_ten="Ghi bù")}))
la("iso@x")
n = [x for x in NHAC() if x["tieu_de"].startswith("BM.PRP.06")]
kiem("ghi bù dòng tháng 9 sau lần xem → tháng 9 lại chờ xem; màn sổ báo cần xem lại",
     len(n) == 1 and "09/2026" in n[0]["tieu_de"] and A.xem("BM.PRP.06", tu="2026-09-01")["xem_thang"]["can_xem_lai"])
F.dat_ngay("2026-10-09")
la("cd2@x")
kiem("BM.06.05: Trưởng Cơ điện (vai xem tháng của sổ) xem xét tháng được",
     A.xem_thang("BM.06.05", "2026-10")["so_dong"] == 3)

print("\n-- chờ xác nhận quá 2 ngày --")
F.dat_ngay("2026-10-13")
la("cd@x")
D4 = A.ghi("BM.06.05", json.dumps({"du_lieu": dict(DL, can_hieu_chuan="", noi_dung="Bảo dưỡng định kỳ máy rang",
                                                   loai="Bảo dưỡng")}))["name"]
F.dat_ngay("2026-10-15")
kiem("2 ngày chưa nhắc", not [x for x in NHAC() if "chờ QC kiểm" in x["tieu_de"]])
F.dat_ngay("2026-10-16")
n = [x for x in NHAC() if "chờ QC kiểm trước chạy quá 2 ngày" in x["tieu_de"]]
kiem("quá 2 ngày QC chưa xác nhận → nhắc (mảng Thiết bị đo)", len(n) == 1 and n[0]["nhom"] == "thiet_bi"
     and "13/10" in n[0]["chi_tiet"], n)
F.dat_ngay("2026-10-09")

print("\n-- máy sản xuất quá hạn bảo dưỡng --")
F.bang(TBM.TB)["TBSX-2024-00002"]["creation"] = "2026-03-01 08:00:00"
F.dat_ngay("2026-10-16")
n = [x for x in NHAC() if "quá hạn bảo dưỡng" in x["tieu_de"]]
kiem("máy rang M2 khai 1/3, chưa ghi bảo dưỡng → quá hạn 1/9 → nhắc; M1 vừa bảo dưỡng 13/10 → không",
     len(n) == 1 and "TBSX-2024-00002" in n[0]["chi_tiet"] and "TBSX-2024-00003" not in n[0]["chi_tiet"]
     and n[0]["nhom"] == "thiet_bi", n)
F.dat_ngay("2026-10-09")

# ═══ 7. Bản in, gói hồ sơ ════════════════════════════════════════════════
print("\n-- bản in --")
la("iso@x")
h = A.in_so("BM.06.05", tu="2026-10-01")
txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))
kiem("BM.06.05 tháng 10: đầu trang chung (mã, tên), dòng hướng dẫn giấy, cột như giấy, QC ký trên phần mềm, dòng chưa "
     "xác nhận ghi rõ, khối Trưởng Cơ điện xem xét",
     "BM.06.05" in txt and "SỔ BẢO DƯỠNG, SỬA CHỮA THIẾT BỊ" in txt.upper() and "Mỗi lần bảo dưỡng theo lịch" in txt
     and "Dầu mỡ dùng (cấp thực phẩm H1?)" in txt and "QC kiểm trước chạy (ký)" in txt
     and "Ký trên phần mềm: Nguyễn Thị QC" in txt and "CHƯA XÁC NHẬN" in txt
     and "Trưởng bộ phận Cơ điện xem xét cuối tháng: Ký trên phần mềm: Trưởng Cơ Điện" in txt
     and "tháng 10/2026" in txt, txt[:600])
kiem("dòng ngừng in gạch, kèm lý do; dòng đã sửa ghi số lần sửa",
     'class="ngung"' in h and "Ngừng : Ghi nhầm máy" in txt.replace("Ngừng: ", "Ngừng : ") and "sửa 1 lần" in txt)
h = A.in_so("BM.03.03")
kiem("BM.03.03: lưới 12 tháng (cột 1…12), dấu ✓ ở tháng 3 và 9; danh mục ghi năm, ô người lập",
     h.count('class="l"') == 12 + 12 and h.count("✓") == 2 and "Năm 2026" in h and "Người lập" in h)
h = A.in_so("BM.03.01")
kiem("BM.03.01 danh mục hiện hành: chỉ dòng đang dùng, ghi số dòng đã ngừng",
     "BCC-02" in h and "BCC-01" not in h and "1 dòng đã ngừng" in h)
la("bv@x")
kiem("in sổ không có quyền → chặn", "quyền xem" in (thu(lambda: A.in_so("BM.03.01")) or ""))
kiem("gói hồ sơ: Ghi theo dòng mỗi tháng có dòng một tệp; Danh mục một tệp danh mục",
     [t for t, _h in A.in_ho_so("BM.PRP.06", "2026-08-01", "2026-10-31")] == ["2026-09.html"]
     and [t for t, _h in A.in_ho_so("BM.03.03", "2026-08-01", "2026-10-31")] == ["danh-muc.html"]
     and A.in_ho_so("BM.KHONG", "2026-08-01", "2026-10-31") == [])

print("\n-- tệp: bản ký tay scan, tải về có kiểm quyền --")
la("bv@x")
PNG = base64.b64encode(b"\x89PNG chu ky khach").decode()
r = A.tai_len("BM.PRP.06", "ky.png", PNG, name=V1, dich="ban_ky_tay")
d = F.get_doc(SO.PT_DONG, V1)
kiem("Bảo vệ gắn bản ký tay của khách vào dòng (kể cả dòng đã qua ngày) — có vết",
     d.ban_ky_tay == r["url"] and d.sua_doi[-1]["hanh_dong"] == "Đính kèm")
A.tep(V1, "ban_ky_tay")
kiem("tải bản ký tay: người xem được sổ", FR.local.response.filecontent == b"\x89PNG chu ky khach"
     and FR.local.response.display_content_as == "inline")
la("cd@x")
kiem("Cơ điện (không thuộc sổ khách) không tải được", "quyền xem" in (thu(lambda: A.tep(V1, "ban_ky_tay")) or ""))
la("ql@x")
kiem("QLSX chỉ xem sổ bảo dưỡng → không gắn tệp được", "quyền ghi" in (thu(
    lambda: A.tai_len("BM.06.05", "ky.png", PNG, name=D1, dich="ban_ky_tay")) or ""))
la("iso@x")
kiem("Trưởng Ban ISO (không ghi sổ) gắn được bản ký tay vào dòng; nhưng không tải tệp cho ô dữ liệu",
     thu(lambda: A.tai_len("BM.06.05", "ky.png", PNG, name=D1, dich="ban_ky_tay")) is None
     and "quyền ghi" in (thu(lambda: A.tai_len("BM.06.05", "ky.png", PNG)) or ""))
la("bv@x")
kiem("tệp sai chữ ký đầu / sai đuôi → lỗi",
     "không khớp" in (thu(lambda: A.tai_len("BM.PRP.06", "a.pdf", PNG, name=V1, dich="tep")) or "")
     and "Chỉ nhận" in (thu(lambda: A.tai_len("BM.PRP.06", "a.exe", PNG, name=V1, dich="tep")) or ""))

# ═══ 8. Định nghĩa sổ trên Desk, Tổng quan ATTP ═══════════════════════════
print("\n-- định nghĩa sổ trên Desk, Tổng quan ATTP --")
d = F.get_doc(SO.PT, "BM.PRP.06")
d.cot = [c for c in d.cot if c["key"] != "gio_ra"]
e = thu(d.save)
kiem("bỏ cột đã có dữ liệu → chặn (dòng cũ thành khóa lạ); đổi nhãn được", e and "gio_ra" in e, e)
d = F.get_doc(SO.PT, "BM.PRP.06")
d.cot[0]["nhan"] = "Họ và tên"
kiem("đổi nhãn cột → lưu được", thu(d.save) is None)
d = F.get_doc(SO.PT, "BM.PRP.06")
d.tinh_toan = "__import__('os')"
kiem("hàm riêng không có trong code → chặn", "không có trong code" in (thu(d.save) or ""))
F.dat_ngay("2026-10-09")
th = {x["ma"]: x for x in AT.tong_hop(NHAC(), {"so_khac": {"so_so": 4, "dong_ky": 3, "cho": 0, "han": 0,
                                                            "ma": ["BM.03.01"]}})["linh_vuc"]}
kiem("thẻ 'Sổ khác' ở Tổng quan ATTP: số dòng trong kỳ, đèn theo mục nhắc của các sổ thuộc thẻ",
     th["so_khac"]["so"] == "3" and th["so_khac"]["route"] == "#/so" and th["so_khac"]["den"] in (AT.VANG, AT.XANH))
kiem("thiết bị sản xuất không làm hỏng nhắc thiết bị đo (không hạn kiểm)",
     all("TBSX" not in str(x) for x in TBM.nhac("2026-10-09").get("qua_han", [])))

# ═══ 9. W44: danh mục có hạn — rủi ro, bên quan tâm, sức khỏe, hóa chất, kính ════════════════
print("\n-- W44: RR = A + B + C + D, cấp độ (hàm thuần) --")
S44 = {x["ma"]: x for x in SEED}
kiem("biên cấp độ md W44: RR 16, 12 → cấp độ 1; 11, 10 → cấp độ 2; 9, 4 → cấp độ 3",
     [SO.rr_cap_do(*x) for x in ((4, 4, 4, 4), (3, 3, 3, 3), (3, 3, 3, 2), (3, 3, 2, 2), (3, 2, 2, 2), (1, 1, 1, 1))]
     == [(16, "Cấp độ 1"), (12, "Cấp độ 1"), (11, "Cấp độ 2"), (10, "Cấp độ 2"), (9, "Cấp độ 3"), (4, "Cấp độ 3")])
kiem("ô trống / ngoài 1–4 / chữ / lẻ → không tính; ô Select gửi chuỗi ' 3 ' vẫn tính",
     all(SO.rr_cap_do(*x) == (None, None) for x in ((0, 1, 1, 1), (5, 1, 1, 1), ("", 1, 1, 1), (None, 1, 1, 1),
                                                      ("a", 1, 1, 1), (2.5, 1, 1, 1)))
     and SO.rr_cap_do("3", "3", "3", " 3 ") == (12, "Cấp độ 1"))
kiem("tên cấp độ trong code = lựa chọn cột cap_do của seed BM.05.02; cột app tính (rr, cap_do) có trong seed",
     [t for _n, t in SO.CAP_DO] == next(c for c in S44["BM.05.02"]["cot"] if c["key"] == "cap_do")["lua_chon"]
     and set(SO.TINH_COT[SO.RR_ABCD]) <= {c["key"] for c in S44["BM.05.02"]["cot"]})
kiem("BM.05.02: A, B, C, D bắt buộc, chọn 1–4",
     all(c.get("bat_buoc") and c["lua_chon"] == ["1", "2", "3", "4"] for c in S44["BM.05.02"]["cot"]
         if c["key"] in ("a", "b", "c", "d")))
dn01 = dict(P.doc_so(S44["BM.05.01"]), cot=cot(*P.doc_so(S44["BM.05.01"])["cot"]))
kiem("gom bản in theo cột: phải là khóa một cột Select (BM.05.01 'nhom' được; 'ben_quan_tam' kiểu Data, khóa lạ → lỗi)",
     not SO.loi_dinh_nghia(dn01) and any("phải là khóa một cột kiểu Select" in x for x in SO.loi_dinh_nghia(
         dict(dn01, nhom_theo="ben_quan_tam"))) and SO.loi_dinh_nghia(dict(dn01, nhom_theo="khong_co")))
kiem("hạn khám lại = ngày khám + 12 tháng khi để trống; có hạn ghi tay thì giữ; sổ khác không đụng",
     SO.bo_sung({"tinh_toan": SO.SUC_KHOE}, {"ngay_kham": "2025-11-01"})["han_kham_lai"] == "2026-11-01"
     and SO.bo_sung({"tinh_toan": SO.SUC_KHOE}, {"ngay_kham": "2024-02-29"})["han_kham_lai"] == "2025-02-28"
     and SO.bo_sung({"tinh_toan": SO.SUC_KHOE}, {"ngay_kham": "2025-11-01", "han_kham_lai": "2026-06-30"})[
         "han_kham_lai"] == "2026-06-30"
     and "han_kham_lai" not in SO.bo_sung({"tinh_toan": SO.SUC_KHOE}, {"ngay_kham": "sai"})
     and "han_kham_lai" not in SO.bo_sung({}, {"ngay_kham": "2025-11-01"}))

print("\n-- BM.05.02 rủi ro: app tính RR, cấp độ; Giám đốc phê duyệt --")
F.dat_ngay("2026-10-09")
la("ql@x")
RR = {"loai": "Hoạt động", "hoat_dong": "Rang đỗ", "rui_ro": "Cháy máy rang", "a": "3", "b": "3", "c": "3", "d": "2",
      "rr": 4, "cap_do": "Cấp độ 3", "bien_phap": "Kiểm đồng hồ nhiệt hằng ngày", "trach_nhiem": "Cơ điện"}
R1 = A.ghi("BM.05.02", json.dumps({"du_lieu": RR}))["name"]
dl = SO.doc_json(F.bang(SO.PT_DONG)[R1]["du_lieu"])
kiem("QLSX ghi A3 B3 C3 D2 kèm RR 4 / Cấp độ 3 gõ tay → app tính đè: RR 11, Cấp độ 2",
     dl["rr"] == 11 and dl["cap_do"] == "Cấp độ 2", dl)
e = thu(lambda: A.ghi("BM.05.02", json.dumps({"du_lieu": dict(RR, d="")})))
kiem("thiếu D → không ghi được (không có RR)", e and "D (khả năng phát hiện)" in e, e)
e = thu(lambda: A.ghi("BM.05.02", json.dumps({"du_lieu": dict(RR, d="5")})))
kiem("D = 5 (ngoài 1–4) → không ghi được", e and "D (khả năng phát hiện)" in e, e)
la("iso@x")
A.sua(R1, json.dumps({"du_lieu": dict(RR, d="3")}))
dl = SO.doc_json(F.bang(SO.PT_DONG)[R1]["du_lieu"])
kiem("Trưởng Ban ISO sửa D thành 3 → tính lại RR 12, Cấp độ 1", dl["rr"] == 12 and dl["cap_do"] == "Cấp độ 1", dl)
x = A.xem("BM.05.02")
kiem("màn sổ nhận danh sách cột app tính (rr, cap_do) — phiếu ghi không cho nhập; tóm tắt có RR và cấp độ",
     x["dn"]["cot_tinh"] == ["rr", "cap_do"] and "12 · Cấp độ 1" in x["ds"][0]["tom_tat"]
     and A.xem("BM.06.05")["dn"]["cot_tinh"] == [], (x["dn"].get("cot_tinh"), x["ds"][0]["tom_tat"]))
la("ql@x")
kiem("QLSX (vai ghi) không phê duyệt được", "quyền" in (thu(lambda: A.xac_nhan(R1)) or ""))
la("gd@x")
A.xac_nhan(R1, "Đồng ý")
kiem("Giám đốc phê duyệt → Đã xác nhận", F.bang(SO.PT_DONG)[R1]["trang_thai"] == SO.DA_XAC_NHAN)

print("\n-- BM.05.01 bên quan tâm: bản in gom 4 nhóm theo thứ tự giấy --")
la("iso@x")
for nhom, ben in (("Nội bộ", "Người lao động"), ("Khách hàng", "Orion Food Vina"),
                  ("Cơ quan quản lý nhà nước", "Chi cục ATTP Hải Dương"), ("Khách hàng", "Đại lý, siêu thị")):
    A.ghi("BM.05.01", json.dumps({"du_lieu": {"nhom": nhom, "ben_quan_tam": ben, "noi_dung_tuan_thu": "Yêu cầu ATTP",
                                              "trach_nhiem": "Ban ISO"}}))
h = A.in_so("BM.05.01")
txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))
vt = [txt.find(t) for t in ("Cơ quan quản lý nhà nước", "Khách hàng", "Nội bộ")]
kiem("BM.05.01: dòng tiêu đề nhóm theo thứ tự lựa chọn (nhóm Nhà cung cấp chưa có dòng → không in), đánh số lại trong "
     "nhóm, cột nhóm không in lặp ở từng dòng, đếm đủ 4 dòng",
     h.count('class="nhom"') == 3 and -1 not in vt and vt == sorted(vt) and "Nhà cung cấp" not in txt
     and re.search(r"Khách hàng 1 Orion Food Vina .* 2 Đại lý, siêu thị", txt) and "Nhóm bên quan tâm" not in txt
     and "4 dòng đang dùng" in txt and "Giám đốc phê duyệt" in txt, txt[:900])
kiem("sổ không gom (BM.03.03): đánh số liền, không có dòng nhóm", 'class="nhom"' not in A.in_so("BM.03.03"))
F.bang(SO.PT_DONG)["SOD-CU-NHOM"] = {"name": "SOD-CU-NHOM", "so": "BM.05.01", "ngay": "2026-01-05",
                                     "trang_thai": SO.DA_GHI, "du_lieu": SO.ghi_json({"nhom": "Đối tác (nhóm cũ)",
                                                                                   "ben_quan_tam": "Ngân hàng"}),
                                     "tom_tat": "Ngân hàng", "nguoi_ghi": "iso@x", "sua_doi": []}
txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", A.in_so("BM.05.01")))
kiem("dòng mang lựa chọn nhóm đã bị Ban ISO đổi tên trên Desk → không mất: in cuối, dưới '(chưa chọn nhóm)'",
     re.search(r"Nội bộ 1 Người lao động .* \(chưa chọn nhóm\) 1 Ngân hàng", txt) is not None, txt[-700:])
F.bang(SO.PT_DONG).pop("SOD-CU-NHOM")

print("\n-- BM.PRP.07 khám sức khỏe: nhân viên trên hệ thống, hạn tự tính, nhắc, dữ liệu cá nhân --")
F.bang("Employee").update({
    "HR-EMP-00001": {"name": "HR-EMP-00001", "employee_name": "Nguyễn Văn Bánh", "status": "Active"},
    "HR-EMP-00002": {"name": "HR-EMP-00002", "employee_name": "Trần Thị Nghỉ", "status": "Left"},
    "HR-EMP-00003": {"name": "HR-EMP-00003", "employee_name": "Lê Văn Bột", "status": "Active"}})
la("hc@x")
kiem("chọn nhân viên: người đã nghỉ (Left) không có trong danh sách; xếp theo họ tên, đánh dấu hiện tên thay mã",
     [(x["v"], x["nhan"], x["an_ma"]) for x in A.goi_y("BM.PRP.07", "nhan_vien")]
     == [("HR-EMP-00003", "Lê Văn Bột", 1), ("HR-EMP-00001", "Nguyễn Văn Bánh", 1)])
GK = A.tai_len("BM.PRP.07", "giay-kham.png", PNG)["url"]
SK = {"nhan_vien": "HR-EMP-00001", "bo_phan": "Xưởng bánh", "tiep_xuc_truc_tiep": "Có", "ngay_kham": "2025-11-01",
      "ket_luan": "Đủ sức khỏe", "anh_giay_kham": GK}
S1 = A.ghi("BM.PRP.07", json.dumps({"du_lieu": SK}))["name"]
row = F.bang(SO.PT_DONG)[S1]
kiem("ngày khám 01/11/2025, để trống hạn → hạn khám lại 01/11/2026; tóm tắt hiện họ tên (không mã HR-EMP)",
     SO.doc_json(row["du_lieu"])["han_kham_lai"] == "2026-11-01" and "Nguyễn Văn Bánh" in row["tom_tat"]
     and "HR-EMP" not in row["tom_tat"], row)
S2 = A.ghi("BM.PRP.07", json.dumps({"du_lieu": dict(SK, nhan_vien="HR-EMP-00003", ngay_kham="2026-03-10",
                                                    han_kham_lai="2027-03-01", anh_giay_kham="")}))["name"]
kiem("hạn khám lại ghi tay theo giấy khám → giữ nguyên",
     SO.doc_json(F.bang(SO.PT_DONG)[S2]["du_lieu"])["han_kham_lai"] == "2027-03-01")
e = thu(lambda: A.ghi("BM.PRP.07", json.dumps({"du_lieu": dict(SK, nhan_vien="HR-EMP-99999")})))
kiem("mã nhân viên không có trên hệ thống → không ghi được", bool(e), e)
n = [x for x in NHAC() if x["tieu_de"].startswith("BM.PRP.07")]
kiem("9/10: hạn khám lại 01/11 còn 23 ngày (báo trước 30) → nhắc; hạn 01/03/2027 chưa tới mốc → không. Hộp nhắc "
     "chung KHÔNG ghi họ tên (dữ liệu cá nhân), chỉ hạn",
     len(n) == 1 and "1 mục sắp đến hạn" in n[0]["tieu_de"] and "còn 23 ngày" in n[0]["chi_tiet"]
     and "hạn khám lại 01/11/2026" in n[0]["chi_tiet"] and "Nguyễn" not in n[0]["chi_tiet"]
     and "Bánh" not in str(SO.nhac(F.hom_nay())), n)
kiem("Hành chính thấy hạn trên thẻ sổ ở màn Sổ", next(x for x in A.ds_so()["ds"] if x["ma"] == "BM.PRP.07")["han"] == 1)
A.tep(S1, "anh_giay_kham")
kiem("Hành chính mở được ảnh giấy khám", FR.local.response.filecontent == b"\x89PNG chu ky khach")
for u in ("qc@x", "ql@x", "cd@x"):
    la(u)
    kiem(f"{NGUOI[u][0]}: không xem, không in, không mở ảnh giấy khám",
         "quyền xem" in (thu(lambda: A.xem("BM.PRP.07")) or "") and "quyền xem" in (thu(
             lambda: A.in_so("BM.PRP.07")) or "") and "quyền xem" in (thu(lambda: A.tep(S1, "anh_giay_kham")) or ""))
la("iso@x")
kiem("Trưởng Ban ISO xem được (không ghi)", len(A.xem("BM.PRP.07")["ds"]) == 2
     and "quyền ghi" in (thu(lambda: A.ghi("BM.PRP.07", json.dumps({"du_lieu": SK}))) or ""))

print("\n-- BM.PRP.04 hóa chất, BM.PRP.05 kính: Cơ điện lập, Trưởng Ban ISO duyệt --")
la("cd@x")
MS = A.tai_len("BM.PRP.04", "msds.pdf", base64.b64encode(b"%PDF-1.4 msds").decode())["url"]
H1 = A.ghi("BM.PRP.04", json.dumps({"du_lieu": {
    "ten_hoa_chat": "Javel 5%", "loai_muc_dich": "Khử trùng dụng cụ", "noi_de": "Tủ hóa chất kho phụ",
    "nguoi_phu_trach": "Phạm Cơ Điện", "msds": MS, "han_ho_so": "2026-10-20"}}))["name"]
n = [x for x in NHAC() if x["tieu_de"].startswith("BM.PRP.04")]
kiem("hạn hồ sơ 20/10 (còn 11 ngày) → nhắc, có tên hóa chất", len(n) == 1 and "Javel 5%" in n[0]["chi_tiet"], n)
la("iso@x")
A.xac_nhan(H1)
la("qc@x")
A.tep(H1, "msds")
kiem("Trưởng Ban ISO duyệt; QC (vai xem) mở được MSDS",
     F.bang(SO.PT_DONG)[H1]["trang_thai"] == SO.DA_XAC_NHAN and FR.local.response.filecontent == b"%PDF-1.4 msds")
kiem("QC chỉ xem: không ghi danh mục hóa chất",
     "quyền ghi" in (thu(lambda: A.ghi("BM.PRP.04", json.dumps({"du_lieu": {}}))) or ""))
la("cd@x")
K1 = A.ghi("BM.PRP.05", json.dumps({"du_lieu": {"ma": "K-01", "vat": "Đèn huỳnh quang", "vi_tri": "Phòng đóng gói",
                                                 "so_luong": 6, "phia_tren_sp_ho": "Có", "bao_ve": "Máng chụp"}}))
kiem("BM.PRP.05: ghi vật kính có số lượng, phía trên sản phẩm hở", F.bang(SO.PT_DONG)[K1["name"]]["tom_tat"]
     .startswith("K-01 · Đèn huỳnh quang · Phòng đóng gói"))
e = thu(lambda: A.ghi("BM.PRP.05", json.dumps({"du_lieu": {"ma": "K-02", "vat": "Kính", "vi_tri": "Kho",
                                                             "so_luong": 1, "phia_tren_sp_ho": "Có thể"}})))
kiem("lựa chọn ngoài Có / Không → không ghi được", bool(e), e)

print("\n-- W44: lượt Tuần — T4 tích từng vật của BM.PRP.05 --")
RC = F.nap("round_ctl", "sx/qc/doctype/sx_qc_round/sx_qc_round.py")
DJ = json.load(open("sx/qc/doctype/sx_qc_round/sx_qc_round.json", encoding="utf-8"))["fields"]
M = sys.modules["sx.qc.muc"]


class Luot(RC.SXQCRound):
    """Bảng con trống trên frappe là [] — Document giả không biết field nào là bảng."""

    def __init__(self, d=None):
        super().__init__(d)
        for f in DJ:
            if f["fieldtype"] == "Table" and self._d.get(f["fieldname"]) is None:
                self._d[f["fieldname"]] = []

    def reload(self):           # bản ghi giả nằm thẳng trong bảng — không có gì để đọc lại
        pass


F.dang_ky("SX QC Round", Luot)
kiem("doctype lượt: bảng con vat_kinh (SX QC Round Vat: dòng BM.PRP.05, mã, tên chép lại, kết quả, ghi chú)",
     next(f for f in DJ if f["fieldname"] == "vat_kinh")["options"] == "SX QC Round Vat"
     and [f["fieldname"] for f in json.load(open("sx/qc/doctype/sx_qc_round_vat/sx_qc_round_vat.json",
                                                 encoding="utf-8"))["fields"]] == ["vat", "ma", "ten", "ket_qua",
                                                                                   "ghi_chu"])
kiem("hàm thuần t4_theo_vat: có K → K; đủ Đạt → Đạt; thiếu vật → chưa chấm; danh mục rỗng → chưa chấm",
     SO.t4_theo_vat([{"vat": "a", "ket_qua": "Đạt"}, {"vat": "b", "ket_qua": "Không đạt"}], [{"vat": "a"}])
     == "Không đạt" and SO.t4_theo_vat([{"vat": "a", "ket_qua": "Đạt"}], [{"vat": "a"}]) == "Đạt"
     and SO.t4_theo_vat([{"vat": "a", "ket_qua": "Đạt"}], [{"vat": "a"}, {"vat": "b"}]) is None
     and SO.t4_theo_vat([], []) is None)
la("cd@x")
K2 = A.ghi("BM.PRP.05", json.dumps({"du_lieu": {"ma": "K-02", "vat": "Cửa kính", "vi_tri": "Kho thành phẩm",
                                                 "so_luong": 2, "phia_tren_sp_ho": "Không"}}))["name"]
K3 = A.ghi("BM.PRP.05", json.dumps({"du_lieu": {"ma": "K-00", "vat": "Kính hỏng cũ", "vi_tri": "Kho",
                                                 "so_luong": 1, "phia_tren_sp_ho": "Không"}}))["name"]
A.ngung(K3, "Đã tháo bỏ")
F.dat_ngay("2026-10-12")
la("qc@x")
r = Q.start_round("2026-10-12", M.TUAN)
ct = Q.chi_tiet_round(r["name"])
ds = (ct.get("vat_kinh") or {}).get("ds") or []
kiem("lượt Tuần: T4 mở danh sách vật đang dùng của BM.PRP.05 theo mã (vật đã ngừng không có), chưa tích",
     [(x["ma"], x["ten"], x["ket_qua"]) for x in ds] == [("K-01", "Đèn huỳnh quang · Phòng đóng gói", ""),
                                                         ("K-02", "Cửa kính · Kho thành phẩm", "")]
     and ct["vat_kinh"]["so"] == "BM.PRP.05", ct.get("vat_kinh"))
v1, v2 = [x["vat"] for x in ds]
kq = Q.save_round(r["name"], json.dumps({f"vat_kinh:{v1}": {"ket_qua": "Đạt"}, "t4_den_kinh": "Đạt"}),
                  "2026-10-12 08:00:00")
d = F.bang("SX QC Round")[r["name"]]
kiem("tích K-01 Đạt: vào bảng con của lượt (mã, tên chép lại), có nhật ký; T4 chưa chấm vì còn K-02; ô T4 gửi "
     "thẳng bị bỏ qua (danh mục có vật thì T4 do các vật quyết định)",
     [(x["ma"], x["ten"], x["ket_qua"]) for x in d["vat_kinh"]] == [("K-01", "Đèn huỳnh quang · Phòng đóng gói",
                                                                     "Đạt")]
     and not d.get("t4_den_kinh") and kq["bo_qua"] == ["t4_den_kinh"]
     and any(x["fieldname"] == f"vat_kinh:{v1}" and x["gia_tri"] == "Đạt" for x in d["log"]), (d["vat_kinh"], kq))
kq = Q.save_round(r["name"], json.dumps({f"vat_kinh:{v2}": {"ket_qua": "Đạt"}}), "2026-10-12 08:01:00")
d = F.bang("SX QC Round")[r["name"]]
kiem("mọi vật Đạt → T4 Đạt (server tính, có dòng nhật ký T4; trả t4 cho máy QC)",
     d["t4_den_kinh"] == "Đạt" and kq["t4"] == "Đạt" and d["log"][-1]["fieldname"] == "t4_den_kinh")
Q.save_round(r["name"], json.dumps({f"vat_kinh:{v2}": {"ket_qua": "Không đạt", "ghi_chu": "vỡ kính cửa"}}),
             "2026-10-12 08:02:00")
ct = Q.chi_tiet_round(r["name"])
kiem("K-02 Không đạt (kèm ghi chú) → T4 Không đạt; xem trước: một phiếu sự cố cho riêng K-02",
     F.bang("SX QC Round")[r["name"]]["t4_den_kinh"] == "Không đạt"
     and [x["mo_ta"] for x in ct["se_thanh_su_co"] if "T4" in x["mo_ta"]]
     == ["T4 kính, nhựa giòn K-02 Cửa kính · Kho thành phẩm: Không đạt (vỡ kính cửa) — vỡ thì dừng khu vực, "
         "cách ly sản phẩm hở 3 m (SSOP 11)"], ct["se_thanh_su_co"])
kq = Q.save_round(r["name"], json.dumps({f"vat_kinh:{v2}": {"ket_qua": "Đạt"}}), "2026-10-12 07:59:00")
kiem("máy khác gửi muộn giá trị CŨ hơn cho cùng vật → bỏ qua, không đè", kq["bo_qua"] == [f"vat_kinh:{v2}"]
     and F.bang("SX QC Round")[r["name"]]["t4_den_kinh"] == "Không đạt")
kq = Q.save_round(r["name"], json.dumps({f"vat_kinh:{K3}": {"ket_qua": "Đạt"}, "vat_kinh:SOD-LA": "Đạt"}),
                  "2026-10-12 08:03:00")
kiem("vật đã ngừng / vật lạ → bỏ qua; kết quả lạ → lỗi", kq["bo_qua"] == [f"vat_kinh:{K3}", "vat_kinh:SOD-LA"]
     and "Đạt hoặc Không đạt" in (thu(lambda: Q.save_round(r["name"], json.dumps(
         {f"vat_kinh:{v1}": {"ket_qua": "Tốt"}}), "2026-10-12 08:04:00")) or ""))
rd = Q.start_round("2026-10-13", M.DAU_SANG)
kq = Q.save_round(rd["name"], json.dumps({f"vat_kinh:{v1}": {"ket_qua": "Đạt"}}), "2026-10-13 07:10:00")
kiem("lượt Đầu sáng (T4 không áp dụng): không nhận vật, không có danh sách",
     kq["bo_qua"] == [f"vat_kinh:{v1}"] and Q.chi_tiet_round(rd["name"])["vat_kinh"] is None)
Q.save_round(r["name"], json.dumps({"ghi_chu": "thử T4 theo vật", "rang_nhiet_do": 262}), "2026-10-12 08:05:00")
F.bang("Has Role")["qc@x-SX QC"] = {"name": "qc@x-SX QC", "parent": "qc@x", "parenttype": "User", "role": "SX QC"}
kq = Q.submit_round(r["name"])
kiem("hoàn tất: một phiếu sự cố mục T4 cho K-02, nối hai chiều với lượt",
     [x["muc"] for x in kq["su_co"]] == ["T4 Đèn, kính có bảo vệ"] and "K-02" in kq["su_co"][0]["mo_ta"]
     and F.bang("SX Su Co")[kq["su_co"][0]["name"]]["qc_round"] == r["name"], kq)
la("cd@x")
A.ngung(v2, "Đã thay cửa nhôm")
la("qc@x")
ct = Q.chi_tiet_round(r["name"])
kiem("lượt đã hoàn tất giữ nguyên vật đã tích dù danh mục đổi sau (ngừng K-02)",
     [(x["ma"], x["ket_qua"]) for x in ct["vat_kinh"]["ds"]] == [("K-01", "Đạt"), ("K-02", "Không đạt")])
h = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", Q._to_ngay("2026-10-12")))
kiem("tờ ngày BM.08.01: ghi từng vật của T4 (Đ / K kèm ghi chú) — ô T4 chỉ là tổng",
     "T4 từng vật kính, nhựa giòn (BM.PRP.05)" in h and "K-01 Đ; K-02 K (vỡ kính cửa)" in h, h[-900:])
F.dat_ngay("2026-10-09")

print("\n-- chọn thiết bị: thiết bị đã thanh lý không có trong danh sách --")
F.get_doc({"doctype": TBM.TB, "ma": "DH-CU", "ten": "Đồng hồ nhiệt cũ", "loai": TBM.DONG_HO, "thanh_ly": 1}).insert()
la("cd@x")
kiem("goi_y bỏ thiết bị thanh lý (trước D173 bộ lọc 'bo' không chạy vì thiếu ô thanh_ly)",
     "DH-CU" not in {x["v"] for x in A.goi_y("BM.06.05", "thiet_bi")}
     and "DH-M1" in {x["v"] for x in A.goi_y("BM.06.05", "thiet_bi")})
F.dat_ngay("2026-10-09")

# ═══ 10. Patch d173 (W44) ══════════════════════════════════════════════════
print("\n-- patch d173: sổ W44 còn thiếu, việc định kỳ QT.05, dòng hồ sơ + thời gian lưu BM.01.04, ngày C26 --")
P173 = F.nap("sx.patches.d173_danh_muc_ncc", "sx/patches/d173_danh_muc_ncc.py")
F.bang(SO.PT).pop("BM.PRP.04")
F.bang(HS.PT)["HS-1"]["thoi_gian_luu"] = "5 năm (Ban ISO tự ghi)"
F.CAI_DAT.pop("ncc_ngay_ap_dung_bm0701", None)
F.CAI_DAT.pop("ncc_han_danh_gia_dau", None)
truoc = len(F.bang(HS.PT))
P173.execute()
hs = {HS.chuan_ma(v.get("bieu_mau") or v["ma"]): v for v in F.bang(HS.PT).values()}
kiem("tạo lại sổ W44 còn thiếu (BM.PRP.04) từ seed, không đụng sổ có rồi", "BM.PRP.04" in F.bang(SO.PT)
     and F.bang(SO.PT)["BM.PRP.06"]["ten"] == "Sổ khách (Ban ISO sửa)")
kiem("việc định kỳ: xác định lại bên quan tâm, rủi ro — năm, hạn 15/12/2026, nhắc trước 30 ngày",
     [(v["chu_ky"], str(v["han"]), v["bao_truoc"], v["ho_so"]) for v in F.bang("SX Viec Dinh Ky").values()
      if "BM.05.01" in v["ten"]] == [("Năm", "2026-12-15", 30, "BM.05.01, BM.05.02")])
kiem("dòng hồ sơ thêm cho biểu mẫu W29–W44 còn thiếu (BM.08.05, SLM, BC.THANG… BM.07.01, BM.01.04, PRP.07)",
     {"BM.08.05", "SLM", "BC.THANG", "BM.01.13", "BM.01.04", "BM.05.01", "BM.05.02", "BM.07.01", "BM.PRP.04",
      "BM.PRP.05", "BM.PRP.07"} <= set(hs) and hs["BM.PRP.07"]["nhom"] == "Điều kiện nhà xưởng (PRP)"
     and hs["BC.THANG"]["ma"] == "BC ATTP tháng" and hs["BM.07.01"]["nguon"] == HS.APP, sorted(hs))
kiem("thời gian lưu, người lưu theo BM.01.04 giấy: dòng trống được điền; dòng Ban ISO đã ghi giữ nguyên",
     (hs["BM.06.05"]["thoi_gian_luu"], hs["BM.06.05"]["nguoi_luu"]) == ("2 năm", "Cơ điện")
     and (hs["BM.PRP.07"]["thoi_gian_luu"], hs["BM.PRP.07"]["nguoi_luu"]) == ("Theo hiệu lực từng người", "Hành chính")
     and F.bang(HS.PT)["HS-1"]["thoi_gian_luu"] == "5 năm (Ban ISO tự ghi)"
     and F.bang(HS.PT)["HS-1"]["nguoi_luu"] == "Hành chính; xưởng sản xuất")
kiem("C26: ngày áp dụng = ngày chạy patch; hạn đánh giá lại lần đầu 31/12/2026",
     (F.CAI_DAT.get("ncc_ngay_ap_dung_bm0701"), F.CAI_DAT.get("ncc_han_danh_gia_dau")) == ("2026-10-09", "2026-12-31"))
sau = len(F.bang(HS.PT))
F.CAI_DAT["ncc_ngay_ap_dung_bm0701"] = "2026-11-20"
P173.execute()
kiem("chạy lại: không nhân đôi sổ, việc, hồ sơ; không đè ngày áp dụng đã đặt",
     len(F.bang(HS.PT)) == sau > truoc and len([v for v in F.bang("SX Viec Dinh Ky").values() if "BM.05.01" in v["ten"]])
     == 1 and F.CAI_DAT["ncc_ngay_ap_dung_bm0701"] == "2026-11-20" and len(F.bang(SO.PT)) >= 10)
kiem("patch có trong patches.txt, sau d172", open("sx/patches.txt", encoding="utf-8").read().index(
    "sx.patches.d173_danh_muc_ncc") > open("sx/patches.txt", encoding="utf-8").read().index("sx.patches.d172_so"))

F.ket_thuc("SO")
