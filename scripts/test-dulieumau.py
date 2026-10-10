"""D177 — lệnh sinh dữ liệu QC MẪU cho site thử (sx/seed/du_lieu_mau.py).

Vì sao phải có bài này:
  · Lệnh lọt lên site thật = hồ sơ ISO giả nằm cạnh hồ sơ thật — cờ site_config phải chặn được, kể cả khi chỉ xem
    trước, kể cả lệnh xoá (D183: không chặn theo tên — site1.local dùng làm site thử thì chạy khi đã bật cờ); còn dữ
    liệu mẫu thì tờ in còn dòng "site thử", kể cả khi đã tắt cờ.
  · "Ngày nào điền rồi thì thôi": ngày đã có lượt, sổ cát từ dòng thật đầu tiên, tuần đã giặt vải, lô đã có phiếu —
    ghi đè / ghi xen là làm bẩn số liệu thật.
  · Dữ liệu mẫu phải đi qua đúng luật của màn QC (lượt đủ mục mới hoàn tất, số trong ngưỡng không tự ra sự cố) và giờ
    phải về đúng ngày, đúng khung lượt — không thì tờ in tháng 9 ghi giờ hoàn tất là lúc chạy lệnh.
  · Chạy lại không đẻ thêm; xoá thì sạch bản ghi mẫu (kể cả dòng con), không đụng bản ghi thật.

Nạp THẬT: muc, controller SX QC Round / Nhat Ky Cat / Giat Vai / Vai U / Su Co / QC Luu Mau / Kiem Tra Xuat Xuong,
sx/api/qc.py, qc_cat.py, qc_vaiu.py, xuatxuong.py, sx/seed/du_lieu_mau.py; frappe giả (fakefrappe) + sx.utils giả.
Chạy: python3 scripts/test-dulieumau.py   (verify.sh gọi sẵn)
"""

import copy
import json
import os
import sys
import types
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

FR = F.cai()
Q = F.nap_qc()
M = sys.modules["sx.qc.muc"]
SO = sys.modules["sx.qc.so"]
CAT = sys.modules["sx.qc.cat"]
VU = sys.modules["sx.qc.vai_u"]
SC = sys.modules["sx.qc.su_co"]
F.nap("sx.qc.rework", "sx/qc/rework.py")
F.nap("sx.qc.tiep_nhan", "sx/qc/tiep_nhan.py")
XX = F.nap("sx.qc.xuat_xuong", "sx/qc/xuat_xuong.py")

# sx.utils giả — đúng bốn hàm sx/api/xuatxuong.py cần.
CONG_BO = {}
U = types.ModuleType("sx.utils")


def _cong_bo(item):
    if item == "TP-HONG":
        raise RuntimeError("bộ tự công bố hỏng")
    return CONG_BO.get(item)


U.cong_bo_cua = _cong_bo
U.get_settings = lambda: F.Doc(F.CAI_DAT_SX)
U.items_tp = lambda *a, **k: []
U.nsx_tu_hsd = lambda item, hsd: str(F.getdate(hsd) - timedelta(days=180)) if hsd else None
sys.modules["sx.utils"] = U
F.nap("sx.api.qc_cat", "sx/api/qc_cat.py")
F.nap("sx.api.qc_vaiu", "sx/api/qc_vaiu.py")
F.nap("sx.api.xuatxuong", "sx/api/xuatxuong.py")
F.nap("sx.seed", "sx/seed/__init__.py")


def _json(dt):
    s = dt.lower().replace(" ", "_")
    p = f"sx/qc/doctype/{s}/{s}.json"
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {"fields": []}


def meta(dt):
    fs = [types.SimpleNamespace(fieldname=f.get("fieldname"), fieldtype=f.get("fieldtype"), options=f.get("options"))
          for f in _json(dt)["fields"]]
    return types.SimpleNamespace(has_field=lambda f: True, get_field=lambda f: None, fields=fs,
                                 get_table_fields=lambda: [x for x in fs if x.fieldtype in ("Table",
                                                                                            "Table MultiSelect")])


FR.get_meta = meta


def lop(goc, dt):
    """Controller thật + bảng con trống là [] (như frappe); khai bảng con để get_all đọc được dòng con."""
    bang = [f for f in meta(dt).get_table_fields()]
    for f in bang:
        F.bang_con(dt, f.fieldname, f.options)

    class L(goc):
        def __init__(self, d=None):
            super().__init__(d)
            for f in bang:
                if self._d.get(f.fieldname) is None:
                    self._d[f.fieldname] = []

        def reload(self):        # bản ghi giả nằm thẳng trong bảng — giá trị trong bộ nhớ là bản mới nhất
            pass

    return L


def nap_ctl(dt):
    s = dt.lower().replace(" ", "_")
    mo = F.nap(f"sx.qc.doctype.{s}.{s}", f"sx/qc/doctype/{s}/{s}.py")
    ten = "".join(w for w in dt.replace(" ", "_").title().split("_"))
    goc = next(v for k, v in vars(mo).items() if isinstance(v, type) and issubclass(v, F.Document)
               and v is not F.Document and k.lower() == ten.lower())
    return lop(goc, dt)


for _dt, _ten in (("SX QC Round", None), ("SX Nhat Ky Cat", None), ("SX Giat Vai", None), ("SX Vai U", "ma"),
                  ("SX Su Co", None), ("SX QC Luu Mau", None), ("SX Kiem Tra Xuat Xuong", None), ("SX QC Ngay", None)):
    F.dang_ky(_dt, nap_ctl(_dt), ten_theo=_ten)
F.Doc.set = lambda self, k, v: self.__setitem__(k, v)        # dòng con có .set như Document của frappe

DL = F.nap("sx.seed.du_lieu_mau", "sx/seed/du_lieu_mau.py")
kiem, thu = F.kiem, F.thu


# ── frappe giả: người dùng, site, cờ site_config, commit / rollback thật (chụp DB) ─────────────────────────────
class NguoiDung(F.DocThuong):
    def insert(self, ignore_permissions=False, **k):
        self["name"] = self.get("name") or self["email"]        # User của frappe: tên = email
        THU_TAT.append(bool(getattr(FR.flags, "mute_emails", None)))
        return super().insert()

    def _goi(self, ten):            # delete_doc giả gọi on_trash / after_delete
        pass

    def add_roles(self, *vai):
        self.setdefault("roles", []).extend({"role": v} for v in vai)
        F.bang("User")[self["name"]] = dict(self)


F.LOP["User"] = NguoiDung
THU_TAT = []           # cờ tắt thư lúc tạo tài khoản mẫu (frappe gửi thư chào ở after_insert của User)


def dat_nguoi(u):
    F.NGUOI["u"] = u
    x = F.bang("User").get(u)
    F.NGUOI["roles"] = ["System Manager"] if u == "Administrator" else [r["role"] for r in (x or {}).get("roles") or []]


FR.set_user = dat_nguoi
FR.local = types.SimpleNamespace(site="sx-thu.local")
FR.conf = {"sx_du_lieu_mau": 1}
CHUP = {"db": None}


def commit():
    CHUP["db"] = copy.deepcopy(F.DB)


def rollback():
    if CHUP["db"] is not None:
        F.DB.clear()
        F.DB.update(copy.deepcopy(CHUP["db"]))


def xoa_bang(dt, loc):
    for k in [k for k, v in F.bang(dt).items() if F.khop(v, loc)]:
        F.bang(dt).pop(k)


FR.db.commit, FR.db.rollback, FR.db.delete = commit, rollback, xoa_bang
FR.utils.now_datetime = F.sys.modules["frappe.utils"].now_datetime

# ── dữ liệu "thật" của site thử (chép từ site thật) ─────────────────────────────────────────────────────────────
F.dat_ngay("2026-10-10")                       # thứ Bảy, 10:00 (now_datetime giả)
dat_nguoi("Administrator")
F.CAI_DAT.update({"vai_u_thu_giat": "Thứ Sáu"})
B = F.bang
for it, ten in (("BOT-DX", "Bột đậu xanh"), ("BOT-CHE", "Chè đậu đen cốt dừa")):
    B("Item")[it] = {"name": it, "item_name": ten, "custom_sx_nhom": "BTP-Bot-SP", "disabled": 0, "stock_uom": "Túi"}
for it in ("TP-BANH", "TP-BOT", "TP-DA", "TP-SUCO", "TP-HONG"):
    B("Item")[it] = {"name": it, "item_name": f"Sản phẩm {it}", "stock_uom": "Hộp", "disabled": 0}
CONG_BO.update({"TP-BANH": {"loai": "Bánh", "quy_cach": "Hộp 300 g (10 bánh)"},
                "TP-BOT": {"loai": "Bột", "quy_cach": "Túi 40g"}})
B("Supplier")["NCC-CAT"] = {"name": "NCC-CAT", "supplier_name": "Cát sông Lô", "custom_loai_ncc": "Cát rang",
                            "disabled": 0, "custom_ncc_duyet": 1}
# lượt THẬT ngày 24/9 (thứ Năm) — ngày đó phải để nguyên
B("SX QC Round")["QCR-THAT"] = {"name": "QCR-THAT", "ngay": date(2026, 9, 24), "luot": M.DAU_SANG, "docstatus": 1,
                                "qc_user": "qc@x", "owner": "qc@x", "rang_nhiet_do": 255}
# cờ bột QC THẬT đã bật cho thứ Sáu 2/10 (ngày thường không có bột) mà chưa đi lượt
B("SX QC Ngay")["NGAY-THAT"] = {"name": "NGAY-THAT", "ngay": date(2026, 10, 2), "co_san_xuat_bot": 1,
                                "cap_nhat_boi": "qc@x", "owner": "qc@x"}
# sổ cát THẬT bắt đầu 6/10 — mẫu chỉ sinh trước ngày đó
B(CAT.PT)["CAT-THAT"] = {"name": "CAT-THAT", "ngay": date(2026, 10, 6), "viec": CAT.VE_SINH, "ve_sinh_thung": 1,
                         "owner": "qc@x", "creation": "2026-10-06 14:00:00"}
# giặt vải ngoài lịch THẬT thứ Tư 30/9 — tuần đó không sinh lần giặt định kỳ
B(VU.PT)["GV-THAT"] = {"name": "GV-THAT", "ngay": date(2026, 9, 30), "viec": VU.NGOAI_LICH, "so_luong": 4,
                       "ly_do": "vải ẩm", "nguoi_lam": "Chị Lan", "owner": "qc@x", "creation": "2026-09-30 15:00:00"}
# phiếu nhập kho thành phẩm: đã duyệt (TP-BANH, TP-BOT, TP-DA, TP-SUCO, TP-HONG) + một phiếu nháp (không tính)
# (lô hỏng TP-HONG xếp TRƯỚC một lô chạy được: quên cuộn lại thì lần commit của lô sau giữ luôn rác của nó)
NHAP = (("NTP-1", date(2026, 9, 28), 1, [("TP-BANH", "2027-03-25", 120), ("TP-DA", "2027-03-20", 50),
                                         ("TP-HONG", "2027-03-29", 10)]),
        ("NTP-2", date(2026, 10, 5), 1, [("TP-BOT", "2027-04-02", 300), ("TP-BANH", "2027-03-25", 30),
                                         ("TP-SUCO", "2027-03-28", 40)]),
        ("NTP-3", date(2026, 10, 6), 0, [("TP-BOT", "2027-04-05", 80)]))
for ten, ngay, ds, dong in NHAP:
    B("SX Phieu Nhap TP")[ten] = {"name": ten, "ngay": ngay, "docstatus": ds,
                                  "duyet_luc": datetime(2026, 9, 28, 7, 50) if ten == "NTP-1" else None}
    for i, (it, hsd, sl) in enumerate(dong, 1):
        B("SX Phieu Nhap TP Item")[f"{ten}-{i}"] = {
            "name": f"{ten}-{i}", "parent": ten, "parenttype": "SX Phieu Nhap TP", "item": it,
            "hsd": date.fromisoformat(hsd), "so_dem": sl, "dvt": "Hộp", "docstatus": ds}
# lô TP-DA đã có phiếu xuất xưởng THẬT
B(XX.PT)["XX-THAT"] = {"name": "XX-THAT", "san_pham": "TP-DA", "hsd": date(2027, 3, 20), "trang_thai": XX.DUYET,
                       "ket_luan": XX.CHO_XUAT, "owner": "qc@x", "creation": "2026-09-28 08:00:00"}
# lô TP-BOT đã có mẫu lưu THẬT → không lấy thêm
B("SX QC Luu Mau")["LM-THAT"] = {"name": "LM-THAT", "san_pham": "TP-BOT", "lo": "HSD 02/04/2027", "so_luong": 2,
                                 "trang_thai": "Đang lưu", "owner": "qc@x"}
# phiếu sự cố THẬT còn mở ở ngày sản xuất của lô TP-SUCO (NSX = HSD − 180 ngày = 29/9) → A2 Không đạt → bỏ lô
B("SX Su Co")["SC-THAT"] = {"name": "SC-THAT", "ngay": date(2026, 9, 29), "nguon": "Vòng kiểm QC", "trang_thai": "Mở",
                            "dien_tap": 0, "mo_ta": "thật", "owner": "qc@x"}
# danh mục kính, nhựa giòn BM.PRP.05 có hai vật → T4 lượt Tuần ghi theo vật
SO.ds_vat_kinh = lambda: [{"vat": "PRP05-1", "ma": "K01", "ten": "Đèn phòng rang", "bao_ve": "Có"},
                          {"vat": "PRP05-2", "ma": "K02", "ten": "Kính cửa sổ kho", "bao_ve": "Có"}]
THAT = {dt: set(B(dt)) for dt in ("SX QC Round", "SX QC Ngay", CAT.PT, VU.PT, XX.PT, "SX Su Co", "SX QC Luu Mau")}
commit()


def mau(dt):
    return {k: v for k, v in B(dt).items() if v.get("owner") in (DL.QC_MAU, DL.ISO_MAU)}


def luc(v):
    return v if isinstance(v, datetime) else datetime.fromisoformat(str(v)[:19])


# ═══ 1. Chốt site ═══════════════════════════════════════════════════════════
print("\n-- chốt site: chỉ chạy trên site đã bật cờ dữ liệu mẫu (site thử) --")
truoc = copy.deepcopy(F.DB)
FR.local.site = "site1.local"
FR.conf = {}
for ten, f in (("xem trước", lambda: DL.chay()), ("ghi", lambda: DL.chay(dry_run=0)),
               ("xoá", lambda: DL.don(dry_run=0)), ("lệnh bench tao", lambda: DL.tao(dry_run=0))):
    loi = thu(f)
    kiem(f"site1.local chưa bật cờ → {ten} bị chặn, chỉ lệnh set-config, báo trước dòng \"site thử\" trên tờ in",
         loi and "bench --site site1.local set-config sx_du_lieu_mau 1" in loi and DL.MI.BAN_THU in loi, loi)
FR.local.site = "sx-thu.local"
for co in ({}, {"sx_du_lieu_mau": 0}, {"sx_du_lieu_mau": "khong"}):
    FR.conf = co
    loi = thu(lambda: DL.chay(dry_run=0))
    kiem(f"site thử chưa bật cờ ({co}) → chặn, chỉ lệnh set-config", loi and "set-config sx_du_lieu_mau 1" in loi, loi)
kiem("bị chặn thì DB không đổi gì (không tạo cả tài khoản mẫu)", F.DB == truoc)
FR.local.site = "site1.local"
FR.conf = {"sx_du_lieu_mau": 1}
co_ban = lambda db: {k: v for k, v in db.items() if v}  # noqa: E731 — bỏ bảng rỗng (đọc bảng chưa có thì bản giả tạo rỗng)
k_s1 = DL.chay()
kiem("D183: site1.local dùng làm site thử, đã bật cờ → chạy được (xem trước, không ghi gì); báo cáo nói rõ tờ in, tệp "
     "xuất mang dòng \"site thử\" tới khi xoá dữ liệu mẫu",
     k_s1["xem_truoc"] and k_s1["site"] == "site1.local" and co_ban(F.DB) == co_ban(truoc)
     and f"Tờ in, tệp xuất của site site1.local mang dòng \"{DL.MI.BAN_THU}\"" in DL.bao_cao(k_s1)
     and "bench --site site1.local execute sx.seed.du_lieu_mau.tao" in DL.bao_cao(k_s1), DL.bao_cao(k_s1)[:300])
FR.local.site = "sx-thu.local"
FR.conf = {"sx_du_lieu_mau": "1"}
kiem("cờ ghi dạng chữ '1' (bench set-config) vẫn nhận", thu(lambda: DL.chay()) is None, thu(lambda: DL.chay()))
FR.conf = {"sx_du_lieu_mau": 1}
kiem("tên phần lạ → chặn", "Phần không có" in (thu(lambda: DL.chay(phan="luot,abc")) or ""))
kiem("dry_run gõ bậy → chặn, không đoán", thu(lambda: DL.chay(dry_run="ok")) is not None)

# ═══ 2. Xem trước ═══════════════════════════════════════════════════════════
print("\n-- xem trước: kế hoạch đúng, không ghi gì --")
truoc = copy.deepcopy(F.DB)
kq = DL.chay()
kiem("xem trước không ghi một bản ghi nào", F.DB == truoc and kq["xem_truoc"])
L = kq["luot"]
kiem("kỳ 22/9 → hôm nay 10/10", kq["tu"] == "2026-09-22" and kq["den"] == "2026-10-10", (kq["tu"], kq["den"]))
kiem("bỏ ngày 24/9 đã có lượt thật; nghỉ hai Chủ nhật", L["bo_qua"] == ["2026-09-24"]
     and L["nghi"] == ["2026-09-27", "2026-10-04"], (L["bo_qua"], L["nghi"]))
kiem("16 ngày, 46 lượt (15 ngày × 3 + hôm nay chỉ lượt Đầu sáng đã qua lúc 10:00)",
     len(L["ngay"]) == 16 and L["so_luot"] == 46, (len(L["ngay"]), L["so_luot"]))
kiem("có bột: thứ Ba / Năm / Bảy (8 ngày — thứ Năm 24/9 đã có lượt thật) + thứ Sáu 2/10 (cờ thật)",
     L["ngay_bot"] == 9, L["ngay_bot"])
kiem("2 sự cố mẫu, rải trong kỳ, ở lượt Trưa", kq["su_co"]["ke_hoach"] == [
    "2026-09-28 Trưa: luoi_sang_nguyen_ven", "2026-10-03 Trưa: thung_bot_qua_han"], kq["su_co"]["ke_hoach"])
kiem("cát: dừng trước 6/10 (sổ thật); nhập + đưa dùng 22/9, bổ sung sau mỗi 6 ngày rang, vệ sinh thứ Bảy",
     kq["cat"]["dung"] == "2026-10-06" and kq["cat"]["ke_hoach"] == [
         "2026-09-22 Nhập cát", "2026-09-22 Rang khô đưa dùng", "2026-09-26 Vệ sinh thùng, khay",
         "2026-09-28 Bổ sung", "2026-10-03 Vệ sinh thùng, khay", "2026-10-05 Bổ sung"], kq["cat"]["ke_hoach"])
kiem("vải: khai 4 vải mẫu; giặt thứ Sáu (Setting) 25/9, 9/10; tuần 30/9 đã giặt thật → bỏ",
     kq["vai"]["vai_moi"] == ["V01-A", "V01-B", "V02-A", "V02-B"] and kq["vai"]["ke_hoach"] == [
         "2026-09-25", "2026-10-09"] and kq["vai"]["bo_qua"] == ["2026-10-02"], kq["vai"])
kiem("xuất xưởng: lô của phiếu nhập ĐÃ DUYỆT chưa có phiếu (TP-DA đã có, phiếu nháp không tính)",
     kq["xuat"]["ke_hoach"] == ["TP-BANH HSD 2027-03-25", "TP-HONG HSD 2027-03-29", "TP-BOT HSD 2027-04-02",
                                "TP-SUCO HSD 2027-03-28"] and kq["xuat"]["da_co"] == 1, kq["xuat"])
bc = DL.bao_cao(kq)
kiem("báo cáo xem trước: nói rõ chưa ghi, đưa lệnh ghi thật, liệt kê thứ không sinh",
     "XEM TRƯỚC (chưa ghi gì)" in bc and "{'dry_run': 0}" in bc and "Không sinh: sản lượng" in bc, bc)
k2 = DL.chay(phan="luot")
kiem("chọn phần: chỉ lượt → không có kế hoạch cát / vải / xuất / sự cố",
     not k2["cat"]["ke_hoach"] and not k2["vai"]["ke_hoach"] and not k2["xuat"]["ke_hoach"]
     and not k2["su_co"]["ke_hoach"] and k2["luot"]["so_luot"] == 46)
_td = CAT.toi_da
CAT.toi_da = lambda: 5
k3 = DL.chay(phan="luot,cat")
CAT.toi_da = _td
kiem("cát đủ số ngày tối đa (Setting 5) → loại cát + đưa cát mới cùng ngày, đếm lại từ đầu",
     "2026-09-28 Loại cát" in k3["cat"]["ke_hoach"] and "2026-09-28 Rang khô đưa dùng" in k3["cat"]["ke_hoach"]
     and k3["cat"]["ke_hoach"].index("2026-09-28 Loại cát") < k3["cat"]["ke_hoach"].index(
         "2026-09-28 Rang khô đưa dùng"), k3["cat"]["ke_hoach"])
import random  # noqa: E402

_g = DL._gio_lo({"ngay": date(2026, 10, 10), "duyet_nhap": None}, random.Random(1), datetime(2026, 10, 10, 8, 0))
kiem("chạy lệnh lúc 08:00 cho lô nhập hôm nay (phiếu nhập không ghi giờ duyệt) → giờ lấy mẫu < kiểm < duyệt < 08:00",
     _g[0] < _g[1] < _g[2] < datetime(2026, 10, 10, 8, 0), _g)
kiem("giờ mẫu không vượt lúc chạy lệnh", DL._da_qua(datetime(2026, 10, 10, 13, 30), datetime(2026, 10, 10, 9, 0))
     < datetime(2026, 10, 10, 9, 0) and DL._da_qua(datetime(2026, 10, 9, 13, 30), datetime(2026, 10, 10, 9, 0))
     == datetime(2026, 10, 9, 13, 30))
kiem("phiên bản bộ mục theo ngày: 1 trước 8/10, 2 ngày 8/10, 3 từ 9/10",
     [DL.phien_ban(x) for x in ("2026-09-22", "2026-10-07", "2026-10-08", "2026-10-09", "2026-10-10")]
     == [1, 1, 2, 3, 3])

# ═══ 3. Ghi ═════════════════════════════════════════════════════════════════
print("\n-- ghi: lượt kiểm BM.08.01 --")
kq = DL.chay(dry_run=0)
kiem("không lỗi phần nào", not kq["loi"], kq["loi"])
kiem("xong trả lại Administrator", F.NGUOI["u"] == "Administrator")
kiem("không gửi thư khi chạy (mute_emails bật trong lúc ghi rồi trả lại)",
     THU_TAT == [True, True] and not getattr(FR.flags, "mute_emails", None), THU_TAT)
U_ = B("User")
kiem("hai tài khoản mẫu: tên gọn QC Mẫu / Ban ISO Mẫu, đủ vai, không mật khẩu, không thư chào",
     (U_[DL.QC_MAU]["first_name"], U_[DL.QC_MAU]["last_name"]) == ("QC", "Mẫu")
     and (U_[DL.ISO_MAU]["first_name"], U_[DL.ISO_MAU]["last_name"]) == ("Ban ISO", "Mẫu")
     and {r["role"] for r in U_[DL.QC_MAU]["roles"]}
     == {"SX QC", "SX QC Packing"} and [r["role"] for r in U_[DL.ISO_MAU]["roles"]] == ["ISO Manager"]
     and not any("new_password" in U_[u] for u in U_) and U_[DL.QC_MAU]["send_welcome_email"] == 0)
LU = mau("SX QC Round")
kiem("46 lượt mẫu, đều hoàn tất, QC mẫu ghi", len(LU) == 46 == kq["luot"]["tao"]
     and all(x["docstatus"] == 1 and x["qc_user"] == DL.QC_MAU for x in LU.values()), len(LU))
kiem("lượt thật 24/9 để nguyên (kể cả chưa xem xét — Ban ISO mẫu chỉ ký phiếu mẫu), không có lượt mẫu ngày đó",
     B("SX QC Round")["QCR-THAT"]["qc_user"] == "qc@x" and not B("SX QC Round")["QCR-THAT"].get("reviewed_on")
     and not any(str(x["ngay"]) == "2026-09-24" for x in LU.values()))
theo = {(str(x["ngay"]), x["luot"]): x for x in LU.values()}
kiem("thứ Hai: lượt Tuần thay Đầu sáng", ("2026-09-28", M.TUAN) in theo and ("2026-09-28", M.DAU_SANG) not in theo
     and ("2026-10-05", M.TUAN) in theo)
kiem("hôm nay (thứ Bảy 10/10, 10:00): chỉ lượt Đầu sáng", [lt for (d, lt) in theo if d == "2026-10-10"] == [M.DAU_SANG])
kiem("D179: lượt mẫu không mang ghi chú riêng (ô ghi chú trống như lượt ghi đủ mục)",
     all(not x.get("ghi_chu") for x in LU.values()))

KH = DL._khoang(sys.modules["sx.qc.nguong"].nguong())
sai, gio_sai, du, la = [], [], [], []
for x in LU.values():
    d = F.get_doc("SX QC Round", x["name"])
    ap = M.muc_cham(d.luot, d)
    if d.so_muc_da_cham != d.so_muc_ap_dung or not ap or any(not M.co_ghi(m, d.get(m["f"])) for m in ap):
        du.append(x["name"])
    hong = SC.phat_hien(d)
    if hong and not d.su_co:
        la.append((x["name"], hong))
    bd, kt = luc(d.started_at), luc(d.finished_at)
    tu, den = {M.TUAN: ("06:00", "08:30"), M.DAU_SANG: ("06:00", "08:30"), M.TRUA: ("08:30", "14:00"),
               M.CUOI_CHIEU: ("14:00", "20:00")}[d.luot]
    if not (str(bd.date()) == str(d.ngay) == str(kt.date()) and tu <= bd.strftime("%H:%M") < kt.strftime("%H:%M") <= den
            and d.duration_min == int((kt - bd).total_seconds() // 60) <= 45 and d.ghi_muon == 0
            and luc(d.creation) == bd and luc(d.modified) == kt):
        gio_sai.append((d.name, d.luot, str(bd), str(kt), d.duration_min, d.ghi_muon))
    for m in M.muc_ap_dung(d.luot, d):
        v = d.get(m["f"])
        if m["goc"] == "rang_nhiet_do" and not (KH["rang_nhiet_do"][0] <= v <= KH["rang_nhiet_do"][1]):
            sai.append((d.name, m["f"], v))
        if m["goc"] == "rang_vong_quay" and not (6.2 <= v <= 7.0):
            sai.append((d.name, m["f"], v))
kiem("mọi lượt ghi ĐỦ mọi mục áp dụng (đã chấm = phải chấm)", not du, du[:3])
kiem("số trong ngưỡng: nhiệt độ rang, vòng quay mọi máy đang chạy", not sai, sai[:3])
kiem("giờ bắt đầu / hoàn tất: đúng ngày, trong khung lượt, ≤ 45 phút, không ghi muộn, giờ lập = giờ bắt đầu",
     not gio_sai, gio_sai[:3])
kiem("lượt không cài hỏng thì không có chỗ lệch nào (sự cố chỉ ở 2 lượt cài)", not la, la[:2])
log_sai = []
for x in LU.values():
    bd, kt = luc(x["started_at"]), luc(x["finished_at"])
    for r in F.get_all("SX QC Round Log", filters={"parent": x["name"]}):
        if not (bd <= luc(r["client_ts"]) < luc(r["server_ts"]) <= kt + timedelta(seconds=2)
                and luc(r["creation"]) == luc(r["client_ts"]) and r["boi"] == DL.QC_MAU):
            log_sai.append((x["name"], r["fieldname"], str(r["client_ts"])))
kiem("giờ ghi từng ô (log) nằm trong lượt, không phải giờ chạy lệnh", not log_sai and len(
    F.get_all("SX QC Round Log", filters={"parent": next(iter(LU))})) > 5, log_sai[:3])
kiem("phiên bản bộ mục theo ngày: tháng 9 bản 1 (không ô NC-02), 8/10 bản 2, 9–10/10 bản 3",
     all(x["phien_ban"] == DL.phien_ban(x["ngay"]) for x in LU.values())
     and theo[("2026-09-22", M.DAU_SANG)].get("nc02_da_kiem") is None
     and theo[("2026-09-22", M.DAU_SANG)].get("nam_cham_da_kiem") == M.DAT
     and theo[("2026-10-09", M.DAU_SANG)].get("nc01_da_kiem") == M.DAT)
t = theo[("2026-09-28", M.TUAN)]
vk = F.get_all("SX QC Round Vat", filters={"parent": t["name"]})
kiem("lượt Tuần: T1–T10 đạt, T2 đếm 0, T4 ghi theo từng vật BM.PRP.05", t["t1_be_nuoc"] == M.DAT
     and t["t2_so_bay_dau_hieu"] == 0 and t["t4_den_kinh"] == M.DAT
     and sorted((r["vat"], r["ket_qua"]) for r in vk) == [("PRP05-1", M.DAT), ("PRP05-2", M.DAT)], vk)
kiem("ngày thường không có bột; thứ Ba có bột (vị không lạc), có số máy gói bột",
     not theo[("2026-09-23", M.TRUA)]["co_san_xuat_bot"] and theo[("2026-09-22", M.TRUA)]["co_san_xuat_bot"] == 1
     and theo[("2026-09-22", M.TRUA)]["san_pham_bot"] == "BOT-DX"
     and theo[("2026-09-22", M.TRUA)].get("b6_kl_tui") == M.DAT)
s1, s2 = theo[("2026-10-01", M.DAU_SANG)], theo[("2026-10-01", M.TRUA)]
kiem("thứ Năm: sáng làm Chè (có lạc) → rang lạc 150–180 °C, 30–40 phút; B7 chưa chuyển đổi",
     s1["san_pham_bot"] == "BOT-CHE" and s1["co_lac"] == 1 and 155 <= s1["b2_rang_lac_nhiet"] <= 175
     and 32 <= s1["b2_rang_lac_phut"] <= 38 and s1["b7_chuyen_doi"] == M.B7_KHONG and not s1.get("b7_gio"),
     s1.get("b7_gio"))
kiem("…trưa đổi vị không lạc → thử nhanh lạc ÂM TÍNH, có giờ thử trong lượt",
     s2["san_pham_bot"] == "BOT-DX" and not s2["co_lac"] and s2["can_thu_lac"] == 1 and s2["b7_chuyen_doi"] == M.B7_AM
     and luc(s2["started_at"]).strftime("%H:%M:%S") <= str(s2["b7_gio"]) <= luc(s2["finished_at"]).strftime("%H:%M:%S"),
     (s2.get("b7_gio"), s2["started_at"], s2["finished_at"]))
q2 = B("SX QC Ngay")["NGAY-THAT"]
kiem("thứ Sáu 2/10 có cờ bột thật: lượt có bột, KHÔNG ghi đè bản ghi cờ của QC thật",
     theo[("2026-10-02", M.TRUA)]["co_san_xuat_bot"] == 1 and q2["cap_nhat_boi"] == "qc@x"
     and not any(str(x["ngay"]) == "2026-10-02" for x in mau("SX QC Ngay").values()))
qn = mau("SX QC Ngay")
kiem("ngày bột khác: QC mẫu bật cờ ngày (SX QC Ngay), giờ bật trước lượt đầu",
     len(qn) == 8 and all(luc(x["cap_nhat_luc"]) < luc(theo[(str(x["ngay"]), M.DAU_SANG)]["started_at"])
                          for x in qn.values()), len(qn))

print("\n-- sự cố mẫu BM.08.02, Ban ISO xem xét --")
SCM = mau("SX Su Co")
kiem("2 phiếu sự cố từ lượt Trưa đã cài, nguồn Vòng kiểm QC, gắn hai chiều với lượt", len(SCM) == 2
     and sorted(str(x["ngay"]) for x in SCM.values()) == ["2026-09-28", "2026-10-03"]
     and all(x["nguon"] == "Vòng kiểm QC" and B("SX QC Round")[x["qc_round"]]["luot"] == M.TRUA for x in SCM.values())
     and kq["su_co"]["tao"] == sorted(SCM, key=lambda n: str(SCM[n]["ngay"])), kq["su_co"])
kiem("QC mẫu ghi xử lý (chữ trơn, không tiền tố), Ban ISO mẫu đóng sáng hôm sau, có quyết định sản phẩm",
     all(x["trang_thai"] == "Đóng" and x["dong_boi"] == DL.ISO_MAU and x["nguoi_xu_ly"] == DL.QC_MAU
         and x["xu_ly_ngay"] in {h["xu_ly_ngay"] for h in DL.HONG} and x["quyet_dinh_sp"]
         and luc(x["dong_ngay"]).date() > F.getdate(x["ngay"]) and luc(x["creation"]).date() == F.getdate(x["ngay"])
         for x in SCM.values()) and kq["su_co"]["dong"] == 2, list(SCM.values())[:1])
xx = [x for x in LU.values() if x.get("reviewed_on")]
kiem("Ban ISO mẫu xem xét các tuần đã qua (thứ Hai tuần sau, 16 giờ); tuần này chưa",
     all(x["reviewed_by"] == DL.ISO_MAU and luc(x["reviewed_on"]).weekday() == 0
         and luc(x["reviewed_on"]).hour == 16 and luc(x["reviewed_on"]) > luc(x["finished_at"]) for x in xx)
     and {str(x["ngay"]) for x in LU.values() if not x.get("reviewed_on")} == {
         "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09", "2026-10-10"}
     and kq["xem_xet"] == len(xx) == 30, (len(xx), kq["xem_xet"]))

print("\n-- nhật ký cát BM.08.03 --")
CM = sorted(mau(CAT.PT).values(), key=lambda x: (str(x["ngay"]), str(x["creation"])))
kiem("6 dòng cát mẫu đúng kế hoạch, QC mẫu ghi, người làm Tổ rang, không ghi chú riêng",
     [f'{x["ngay"]} {x["viec"]}' for x in CM] == kq["cat"]["ke_hoach"] and kq["cat"]["tao"] == 6
     and all(x["nguoi_ghi"] == DL.QC_MAU and not x.get("ghi_chu") and x["nguoi_lam"] == "Tổ rang" for x in CM),
     [x["viec"] for x in CM])
kiem("D181: rang khô đưa dùng — cảm quan là lựa chọn của ô (Đạt), không ghi chữ tự do (site chặn: Select chỉ nhận "
     "Đạt / Không đạt)", [x.get("cam_quan") for x in CM if x["viec"] == CAT.RANG_KHO] == ["Đạt"]
     and all(not x.get("cam_quan") for x in CM if x["viec"] != CAT.RANG_KHO),
     [(x["viec"], x.get("cam_quan")) for x in CM])
bs = [x for x in CM if x["viec"] == CAT.BO_SUNG]
kiem("bổ sung: app tự đếm số ngày đã dùng (ngày có rang kể cả lượt thật 24/9): 6 rồi 12",
     [x["so_ngay_dung"] for x in bs] == [6, 12], [x["so_ngay_dung"] for x in bs])
kiem("nhập cát có nguồn NCC Cát rang; đưa dùng nhận nguồn đó; lần nhập đầu không bị coi là đổi nguồn",
     CM[0]["ncc_cat"] == "NCC-CAT" and CM[1]["ncc_cat"] == "NCC-CAT" and not CM[0].get("doi_nguon"))
kiem("giờ lập dòng cát là giờ trong ngày đó (nhập sáng, việc khác chiều), không phải giờ chạy lệnh",
     all(str(luc(x["creation"]).date()) == str(x["ngay"]) for x in CM) and luc(CM[0]["creation"]).hour == 7)
kiem("dòng cát thật 6/10 để nguyên; Ban ISO mẫu xem dòng mẫu tuần đã qua cùng lượt, tuần này (5/10) chưa",
     B(CAT.PT)["CAT-THAT"]["owner"] == "qc@x" and not B(CAT.PT)["CAT-THAT"].get("xem_luc")
     and all((x.get("xem_boi") == DL.ISO_MAU) == (str(x["ngay"]) < "2026-10-05") for x in CM))

print("\n-- sổ giặt vải ủ BM.08.05 --")
VM = mau(VU.VAI)
kiem("danh mục vải trống → Ban ISO mẫu khai 4 vải Đang dùng (không ghi chú riêng)",
     sorted(VM) == ["V01-A", "V01-B", "V02-A", "V02-B"]
     and all(x["trang_thai"] == VU.DANG_DUNG and not x.get("ghi_chu") for x in VM.values()))
GM = sorted(mau(VU.PT).values(), key=lambda x: str(x["ngay"]))
kiem("giặt định kỳ thứ Sáu 25/9, 9/10 (tuần có giặt thật bỏ qua), đủ 4 vải",
     [str(x["ngay"]) for x in GM] == ["2026-09-25", "2026-10-09"] and all(
         x["viec"] == VU.DINH_KY and sorted(r["vai"] for r in x["vai"]) == sorted(VM) for x in GM))
kiem("QC mẫu ký: đun sôi ≥ 10 phút, có chỗ phơi, giờ cất sau giờ vớt, ký lúc cất (không phải giờ chạy lệnh)",
     all(x["qc_ky_boi"] == DL.QC_MAU and x["so_phut"] >= 10 and x["phoi_tai"]
         and luc(x["cat_luc"]) > luc(f'{x["ngay"]} {x["gio_vot"]}') and luc(x["qc_ky_luc"]) > luc(x["cat_luc"])
         and luc(x["qc_ky_luc"]) < datetime(2026, 10, 10, 10) for x in GM), GM)
kiem("Ban ISO mẫu xem tháng 9 (ngày 3/10); tháng 10 chưa xem; dòng thật để nguyên",
     GM[0]["xem_boi"] == DL.ISO_MAU and luc(GM[0]["xem_luc"]).date() == date(2026, 10, 3)
     and not GM[1].get("xem_luc") and not B(VU.PT)["GV-THAT"].get("xem_luc"))

print("\n-- xuất xưởng BM.08.04 + sổ lưu mẫu --")
XM = mau(XX.PT)
kiem("2 lô được kiểm + duyệt: TP-BANH, TP-BOT (Cho xuất xưởng, QC mẫu kiểm, Ban ISO mẫu duyệt — không tự duyệt)",
     sorted(x["san_pham"] for x in XM.values()) == ["TP-BANH", "TP-BOT"] and all(
         x["trang_thai"] == XX.DUYET and x["ket_luan"] == XX.CHO_XUAT and x["qc_kiem"] == DL.QC_MAU
         and x["nguoi_duyet"] == DL.ISO_MAU for x in XM.values()) and kq["xuat"]["tao"] == 2, kq["xuat"])
pb = next(x for x in XM.values() if x["san_pham"] == "TP-BANH")
b2 = next(r for r in pb["ds_muc"] if r["ma"] == "B2")
kiem("B2 cân 5 mẫu quanh khối lượng trên quy cách (300 g, không dưới nhãn); B khác 5 ô Đ",
     all(300 < float(b2[f"mau_{i}"]) < 303 for i in range(1, 6)) and all(
         r[f"mau_{i}"] == XX.D for r in pb["ds_muc"] if r["ma"] in XX.MA_B and r["ma"] != "B2" for i in range(1, 6)))
kiem("A theo gợi ý hồ sơ lô: A4 bánh KAD, A5 Đạt (đã lấy mẫu lưu)",
     {r["ma"]: r["ket_qua"] for r in pb["ds_muc"]}["A4"] == XX.KAD
     and {r["ma"]: r["ket_qua"] for r in pb["ds_muc"]}["A5"] == XX.DAT)
kiem("giờ kiểm / duyệt: ngày nhập kho của lô, duyệt sau kiểm, TRƯỚC lúc thủ kho duyệt phiếu nhập (07:50)",
     luc(pb["kiem_luc"]).date() == date(2026, 9, 28) and luc(pb["kiem_luc"]) < luc(pb["duyet_luc"])
     < datetime(2026, 9, 28, 7, 50) and luc(pb["creation"]) < luc(pb["kiem_luc"]), (pb["kiem_luc"], pb["duyet_luc"]))
po = next(x for x in XM.values() if x["san_pham"] == "TP-BOT")
kiem("phiếu nhập không ghi giờ duyệt → kiểm / duyệt buổi sáng ngày nhập kho",
     luc(po["kiem_luc"]).date() == luc(po["duyet_luc"]).date() == date(2026, 10, 5)
     and 8 <= luc(po["kiem_luc"]).hour and luc(po["duyet_luc"]).hour <= 9, (po["kiem_luc"], po["duyet_luc"]))
LMM = mau("SX QC Luu Mau")
kiem("sổ lưu mẫu: lấy mẫu cho lô chưa có (đúng HSD lô, lấy trước khi kiểm, ngày nhập kho); TP-BOT có mẫu thật → thôi",
     [(x["san_pham"], x["lo"], str(x["ngay_lay"])) for x in LMM.values()] == [("TP-BANH", "HSD 25/03/2027",
                                                                               "2026-09-28")]
     and kq["xuat"]["mau_luu"] == 1
     and all(not x.get("ghi_chu") and x["vi_tri"] == "Tủ mẫu lưu" for x in LMM.values())
     and {r["ma"]: r["ket_qua"] for r in next(x for x in XM.values() if x["san_pham"] == "TP-BOT")["ds_muc"]}["A5"]
     == XX.DAT, [(x["san_pham"], x["lo"], x["ngay_lay"]) for x in LMM.values()])
kiem("lô có sự cố THẬT chưa quyết định (A2 gợi ý Không đạt) → bỏ, cuộn lại cả mẫu lưu đã lấy",
     any(b.startswith("TP-SUCO") and "A2" in b for b in kq["xuat"]["bo"]) and not any(
         x["san_pham"] == "TP-SUCO" for x in list(XM.values()) + list(LMM.values())), kq["xuat"]["bo"])
kiem("lô lỗi giữa chừng → ghi LỖI, cuộn lại lô đó, các lô khác vẫn chạy",
     any(b.startswith("TP-HONG") and "LỖI" in b for b in kq["xuat"]["bo"]) and not any(
         x["san_pham"] == "TP-HONG" for x in list(XM.values()) + list(LMM.values())))
kiem("phiếu xuất xưởng thật của TP-DA để nguyên", B(XX.PT)["XX-THAT"]["owner"] == "qc@x" and len(
    [x for x in B(XX.PT).values() if x["san_pham"] == "TP-DA"]) == 1)


def _chu(v):
    if isinstance(v, dict):
        return " ".join(_chu(x) for x in v.values())
    if isinstance(v, (list, tuple)):
        return " ".join(_chu(x) for x in v)
    return str(v if v is not None else "")


_cha = {k for dt in DL.XOA for k in mau(dt)}
_con = ("SX QC Round Log", "SX QC Round Vat", "SX QC Round Incident", "SX Giat Vai Ma", "SX Kiem Tra Xuat Xuong Muc")
_xet = [(dt, v) for dt in DL.XOA for v in mau(dt).values()] + [
    (dt, v) for dt in _con for v in B(dt).values() if v.get("parent") in _cha]
_ban = [(dt, v.get("name")) for dt, v in _xet if "dữ liệu mẫu" in _chu(v).lower() or "(mẫu)" in _chu(v).lower()]
kiem("D179: không bản ghi mẫu nào (kể cả dòng con) còn chữ \"dữ liệu mẫu\" / \"(mẫu)\"",
     not _ban and len(_xet) > 500, (_ban[:3], len(_xet)))
import jinja2  # noqa: E402

MI = sys.modules["sx.qc.mau_in"]
_env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))
_env.globals["sx_dau_trang"] = F.sx_dau_trang
_tpl = _env.from_string('{% from "sx/qc/_dau_trang.html" import dau_trang %}{{ dau_trang("BM.08.03", "Nhật ký") }}')
_h1 = _tpl.render()
FR.conf = {}
_h0 = _tpl.render()
FR.conf = {"sx_du_lieu_mau": 1}
kiem("D184: dòng in đúng chữ \"Phần mềm đang thử nghiệm — có dữ liệu mẫu\" — vẫn nói rõ có dữ liệu mẫu",
     MI.BAN_THU == "Phần mềm đang thử nghiệm — có dữ liệu mẫu", MI.BAN_THU)
# D185: dòng ở CHÂN TRANG — in: ô lề dưới mọi trang (@page @bottom-center); màn hình: thanh đáy cửa sổ, ẩn khi in
chan_ok = lambda h: (h.count(MI.BAN_THU) == 2 and '@page{@bottom-center{content:"' + MI.BAN_THU + '"' in h  # noqa: E731
                     and '<div class="sx-ban-thu">' + MI.BAN_THU + "</div>" in h
                     and "@media print{.sx-ban-thu{display:none}}" in h and "position:fixed" in h
                     and "@media screen{body{padding-bottom:22px}}" in h
                     and "bottom:0" in h and "margin:0 0 4px" not in h)
kiem("D185: tờ in site thử (cờ bật) — dòng \"Phần mềm đang thử nghiệm — có dữ liệu mẫu\" ở CHÂN TRANG mọi trang khi in "
     "(ô lề dưới), thanh đáy cửa sổ trên màn hình (ẩn khi in), không còn khung trên đầu; D183: tắt cờ mà dữ liệu mẫu "
     "còn → vẫn mang dòng đó", chan_ok(_h1) and chan_ok(_h0) and "sx-dau-trang" in _h0, _h1[:400])
_bm = sys.modules["sx.api.qc_cat"].in_bm0803("2026-09")
kiem("D179: tờ in thật (BM.08.03 tháng 9) trên site thử có dòng đó, dữ liệu mẫu vẫn in đủ",
     MI.BAN_THU in _bm and "Tổ rang" in _bm, _bm[:200])
bc = DL.bao_cao(kq)
kiem("báo cáo ghi: ĐÃ GHI, số lượt, sự cố đóng, lô bỏ kèm lý do",
     "ĐÃ GHI" in bc and "đã ghi 46 lượt" in bc and "Ban ISO đóng 2" in bc and "bỏ lô TP-SUCO" in bc, bc)

# ═══ 4. Chạy lại ════════════════════════════════════════════════════════════
print("\n-- chạy lại: ngày đã có thì thôi --")
dem = {dt: len(B(dt)) for dt in list(F.DB)}
k2 = DL.chay(dry_run=0)
kiem("chạy lại không đẻ thêm bản ghi nào", {dt: len(B(dt)) for dt in list(F.DB)} == dem
     and k2["luot"]["tao"] == 0 and not k2["luot"]["ngay"] and not k2["cat"]["ke_hoach"]
     and not k2["vai"]["ke_hoach"] and k2["xuat"]["tao"] == 0, (k2["luot"]["ngay"][:3], k2["cat"]["ke_hoach"]))
kiem("…mọi ngày đã có lượt đều là ngày bỏ qua", len(k2["luot"]["bo_qua"]) == 17)
kiem("…vải: dùng 4 vải đang dùng, không khai thêm", k2["vai"]["vai_moi"] == [] and k2["vai"]["vai"] == [
    "V01-A", "V01-B", "V02-A", "V02-B"] and not k2["vai"]["ghi_chu"], k2["vai"])
for _m in mau(VU.VAI).values():
    _m["trang_thai"] = VU.DU_PHONG
k4 = DL.chay(phan="vai")
for _m in mau(VU.VAI).values():
    _m["trang_thai"] = VU.DANG_DUNG
kiem("danh mục có vải mà không vải nào Đang dùng → không bịa vải, không giặt, nói rõ",
     not k4["vai"]["vai_moi"] and not k4["vai"]["ke_hoach"] and "không vải nào Đang dùng" in k4["vai"]["ghi_chu"],
     k4["vai"])

# ═══ 5. Xoá ═════════════════════════════════════════════════════════════════
print("\n-- xoá dữ liệu mẫu --")
so_tr = {(str(x["ngay"]), x["luot"]): (x["rang_nhiet_do"], str(x["started_at"]), x["so_may_rang"]) for x in LU.values()}
truoc = copy.deepcopy(F.DB)
x0 = DL.don()
kiem("xoá xem trước: chỉ đếm, không xoá", F.DB == truoc and x0["dem"]["SX QC Round"] == 46
     and x0["dem"]["SX Su Co"] == 2 and x0["dem"][CAT.PT] == 6 and x0["dem"]["SX Vai U"] == 4, x0["dem"])
x1 = DL.don(dry_run=0)
kiem("xoá thật: không còn bản ghi nào của tài khoản mẫu", all(not mau(dt) for dt in DL.XOA), x1["dem"])
kiem("…kể cả dòng con (log từng ô, vật T4, mục phiếu xuất xưởng, mã vải giặt)",
     not any(r.get("parent") in {*LU, *XM, *(x["name"] for x in GM)}
             for con in ("SX QC Round Log", "SX QC Round Vat", "SX Kiem Tra Xuat Xuong Muc", "SX Giat Vai Ma")
             for r in B(con).values()))
kiem("bản ghi thật còn nguyên", all(THAT[dt] <= set(B(dt)) for dt in THAT)
     and B("SX QC Round")["QCR-THAT"]["qc_user"] == "qc@x")
kiem("tài khoản mẫu đã xoá", not any(u in B("User") for u in DL.NGUOI_MAU) and not x1["khoa"])
FR.conf = {}
_h2 = _tpl.render()
FR.conf = {"sx_du_lieu_mau": 1}
_h3 = _tpl.render()
kiem("D183: xoá hết dữ liệu mẫu + tắt cờ → tờ in sạch (không chân trang, không thanh đáy); còn bật cờ thì vẫn có",
     MI.BAN_THU not in _h2 and "sx-ban-thu" not in _h2 and "@bottom-center" not in _h2 and "sx-dau-trang" in _h2
     and chan_ok(_h3))
# tài khoản mẫu tạo trước D179: tên "… Mẫu (dữ liệu mẫu)", bị khoá, thiếu vai → chạy lại sửa cả ba
B("User")[DL.QC_MAU] = {"name": DL.QC_MAU, "email": DL.QC_MAU, "first_name": "QC", "last_name": "Mẫu (dữ liệu mẫu)",
                        "enabled": 0, "roles": [{"role": "SX QC"}], "doctype": "User"}
k3 = DL.chay(dry_run=0)
_u = B("User")[DL.QC_MAU]
kiem("D179: tài khoản mẫu cũ → tên gọn \"Mẫu\", mở khoá, đủ vai (một lần lưu, không ghi đè lẫn nhau)",
     (_u["last_name"], _u["enabled"], {r["role"] for r in _u["roles"]}) == ("Mẫu", 1, {"SX QC", "SX QC Packing"}), _u)
moi = {(str(x["ngay"]), x["luot"]): (x["rang_nhiet_do"], str(x["started_at"]), x["so_may_rang"])
       for x in mau("SX QC Round").values()}
kiem("xoá rồi sinh lại: cùng hạt → đúng số cũ (nhiệt độ rang, giờ bắt đầu, số máy từng lượt)",
     moi == so_tr and not k3["loi"], k3["loi"])

F.ket_thuc("DULIEUMAU")
