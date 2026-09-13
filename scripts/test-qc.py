"""Module QC: danh mục mục kiểm, ma trận áp dụng, luật sinh sự cố, chặn hoàn tất.

Vì sao phải có bài này: mọi thứ hỏng ở đây đều hỏng ÂM THẦM.

  · Sót một luật sinh sự cố → lượt vẫn hoàn tất, màn hình vẫn xanh, chỉ là chỗ
    không đạt kia không thành phiếu và không ai đi xử lý.
  · Lệch giữa muc.py và DocType JSON → mục biến mất khỏi màn hình, ô trên tờ in
    vẫn còn, không lỗi nào hiện ra cho tới lúc auditor đếm.
  · Sai chỗ "0 nghĩa là gì" → ngày nào cũng vài sự cố giả, rồi không ai đọc sổ
    sự cố nữa. Đó là cách một hệ thống ISO chết.

Nạp MODULE THẬT với frappe giả, không chép logic sang đây.
Chạy: python3 scripts/test-qc.py   (verify.sh gọi sẵn)
"""

import importlib.util
import json
import os
import sys
import types
from datetime import datetime, timedelta

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# ── frappe giả ────────────────────────────────────────────────────────────
TRUNG = []          # frappe.get_all trả gì cho lần gọi sau
DA_TAO = []         # phiếu sự cố được insert


class Loi(Exception):
    pass


def _throw(msg, exc=None):
    raise (exc or Loi)(str(msg))


class Doc(dict):
    """Bản ghi giả: truy cập được cả .field lẫn ['field'], có append/get/set."""

    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v

    def set(self, k, v):
        self[k] = v

    def append(self, k, v):
        self.setdefault(k, []).append(Doc(v))
        return self[k][-1]

    def insert(self, **kw):
        DA_TAO.append(self)
        self["name"] = f"SC-{len(DA_TAO):04d}"
        return self


frappe = types.ModuleType("frappe")
frappe.throw = _throw
frappe.whitelist = lambda *a, **k: (lambda f: f)
frappe.PermissionError = type("PermissionError", (Loi,), {})
def _khop(hang, filters):
    """get_all giả có LỌC THẬT. Lọc giả (trả nguyên danh sách) thì bài kiểm
    trùng lượt sẽ 'đạt' cả khi code quên lọc theo lượt — tức là test nói dối."""
    for truong, dk in (filters or {}).items():
        if truong not in hang:
            continue                      # cột test không dựng thì bỏ qua
        v = hang[truong]
        if isinstance(dk, (list, tuple)):
            toan, moc = dk
            if toan == "in" and v not in moc:
                return False
            if toan == "!=" and v == moc:
                return False
            if toan == "<" and not v < moc:
                return False
        elif v != dk:
            return False
    return True


frappe.get_all = lambda dt=None, filters=None, **k: [
    h for h in TRUNG if _khop(h, filters)]
frappe.get_roles = lambda u=None: ["SX QC"]
frappe.session = types.SimpleNamespace(user="qc@rvhg.vn")
frappe.get_doc = lambda d: Doc(d) if isinstance(d, dict) else Doc({"name": d})
frappe.get_cached_doc = lambda dt: CAI_DAT
frappe.__dict__["_"] = lambda s: s

frappe.utils = types.ModuleType("frappe.utils")
frappe.utils.cint = lambda v: int(float(v or 0))
frappe.utils.flt = lambda v, p=None: round(float(v or 0), p) if p else float(v or 0)
frappe.utils.now_datetime = lambda: GIO_SERVER[0]
frappe.utils.nowdate = lambda: "2026-09-14"
frappe.utils.getdate = lambda x=None: x
frappe.utils.add_days = lambda d, n: d
frappe.utils.get_datetime = lambda x=None: x
frappe.utils.get_time = lambda x=None: (x.time() if isinstance(x, datetime)
                                        else datetime.strptime(str(x)[:8], "%H:%M:%S").time())
frappe.utils.formatdate = lambda d: str(d)
frappe.utils.time_diff_in_seconds = lambda a, b: (a - b).total_seconds()
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = frappe.utils

mdl = types.ModuleType("frappe.model")
mdl.__path__ = []
doc_mod = types.ModuleType("frappe.model.document")
doc_mod.Document = Doc
sys.modules["frappe.model"] = mdl
sys.modules["frappe.model.document"] = doc_mod

GIO_SERVER = [datetime(2026, 9, 14, 7, 12, 0)]
CAI_DAT = Doc({})          # SX QC Setting rỗng -> mọi ngưỡng lấy mặc định


def nap(ten, duong_dan):
    sp = importlib.util.spec_from_file_location(ten, duong_dan)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mod
    sp.loader.exec_module(mod)
    return mod


for goi in ("sx", "sx.qc", "sx.qc.doctype"):
    m = types.ModuleType(goi)
    m.__path__ = []
    sys.modules[goi] = m

M = nap("sx.qc.muc", "sx/qc/muc.py")
NG = nap("sx.qc.nguong", "sx/qc/nguong.py")
SC = nap("sx.qc.su_co", "sx/qc/su_co.py")
R = nap("sx.qc.doctype.sx_qc_round.sx_qc_round",
        "sx/qc/doctype/sx_qc_round/sx_qc_round.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


def luot(**kw):
    """Một lượt THẬT (instance của controller), không phải dict giả: có vậy mới
    gọi được before_submit và thấy đúng thứ tự các bước kiểm chạy."""
    d = R.SXQCRound({"name": "QC-0001", "ngay": "2026-09-14", "ca": "Sáng",
                     "luot": M.DAU_CA, "co_san_xuat_bot": 0, "log": [],
                     "su_co": []})
    d.update(kw)
    return d


# ═══ 1. muc.py ↔ DocType JSON ════════════════════════════════════════════
print("-- danh mục mục kiểm khớp DocType JSON --")
jd = json.load(open("sx/qc/doctype/sx_qc_round/sx_qc_round.json", encoding="utf-8"))
field = {f["fieldname"]: f for f in jd["fields"]}
thieu = [m["f"] for m in M.MUC if m["f"] not in field]
kiem("mọi mục trong muc.py đều có field trong JSON", not thieu, ", ".join(thieu))

KIEU_JSON = {"chon": "Select", "chon3": "Select", "so": "Float", "nguyen": "Int",
             "chu": "Data", "co_khong": "Check", "gio": "Time"}
sai = [f'{m["f"]}: {field[m["f"]]["fieldtype"]} ≠ {KIEU_JSON[m["kieu"]]}'
       for m in M.MUC if m["f"] in field
       and field[m["f"]]["fieldtype"] != KIEU_JSON[m["kieu"]]]
kiem("kiểu field khớp kiểu mục", not sai, ", ".join(sai))

# Tri-state PHẢI là Select có lựa chọn rỗng. Đổi thành Check là mất hẳn trạng
# thái "chưa kiểm" — và mất im lặng: 0 trông y như "đã kiểm, không đạt".
xau = [m["f"] for m in M.MUC if m["kieu"] == "chon"
       and not field[m["f"]].get("options", "").startswith("\n")]
kiem("mục Đạt/Không đạt giữ được trạng thái TRỐNG", not xau, ", ".join(xau))

# Ô ĐO không được có default 0: Frappe đọc Int rỗng ra 0, mà default 0 thì cả
# lúc export lại càng chắc chắn thành "đã đo được 0 °C".
do = [f for f in ("rang_nhiet_do", "b2_rang_lac_nhiet", "b2_rang_lac_phut")
      if field[f].get("default")]
kiem("ô ĐO không đặt default 0", not do, ", ".join(do))

thua = [f["fieldname"] for f in jd["fields"]
        if f["fieldname"] not in M.THEO_F and f["fieldtype"] not in
        ("Section Break", "Column Break", "Table", "Link", "Datetime", "Date",
         "Select", "Check", "Int", "Small Text", "Data")]
kiem("JSON không có field lạ ngoài khung", not thua, ", ".join(thua))

# ═══ 2. Ma trận áp dụng (spec 1.1.5) ═════════════════════════════════════
print("\n-- ma trận áp dụng: mục nào ghi ở lượt nào --")


def ap(f, l, bot=0):
    return f in M.ma_tran(bot)[l]


kiem("phần A chỉ ở Đầu ca và Tuần",
     ap("a1_ve_sinh", M.DAU_CA) and ap("a1_ve_sinh", M.TUAN)
     and not ap("a1_ve_sinh", M.GIUA_CA) and not ap("a1_ve_sinh", M.CUOI_CA))
kiem("nam châm chỉ ở Đầu ca / Tuần",
     ap("nam_cham_da_kiem", M.DAU_CA) and not ap("nam_cham_da_kiem", M.CUOI_CA))
kiem("mối hàn túi chỉ ở Giữa ca / Cuối ca",
     ap("moi_han_kin", M.GIUA_CA) and ap("moi_han_kin", M.CUOI_CA)
     and not ap("moi_han_kin", M.DAU_CA) and not ap("moi_han_kin", M.TUAN))
kiem("phần C (t1–t11) chỉ ở lượt Tuần",
     all(ap(f, M.TUAN) and not ap(f, M.DAU_CA)
         for f in ("t1_be_nuoc", "t2_so_bay_dau_hieu", "t11_can_qua_chuan")))
kiem("phần D chỉ khi hôm đó có bột",
     ap("b1_lac_sach", M.GIUA_CA, 1) and not ap("b1_lac_sach", M.GIUA_CA, 0))
kiem("rang + luộc + nhãn ghi ở MỌI lượt",
     all(ap(f, l) for f in ("luoc_soi_du", "rang_nhiet_do", "nhan_hsd_dung")
         for l in M.LUOT))
kiem("lượt Tuần nhiều mục hơn Đầu ca thường",
     len(M.muc_cham(M.TUAN, 0)) > len(M.muc_cham(M.DAU_CA, 0)),
     f"{len(M.muc_cham(M.TUAN, 0))} vs {len(M.muc_cham(M.DAU_CA, 0))}")

# ═══ 3. "0" nghĩa là gì ══════════════════════════════════════════════════
print("\n-- ô ĐO với ô ĐẾM: số 0 có phải là số không --")
kiem("nhiệt độ 0 = CHƯA ĐO", not M.co_ghi(M.THEO_F["rang_nhiet_do"], 0))
kiem("nhiệt độ 248 = đã đo", M.co_ghi(M.THEO_F["rang_nhiet_do"], 248))
kiem("thùng quá hạn 0 = ĐẾM ĐƯỢC 0", M.co_ghi(M.THEO_F["thung_bot_qua_han"], 0))
kiem("trạm bẫy 0 = đếm được 0", M.co_ghi(M.THEO_F["t2_so_bay_dau_hieu"], 0))
kiem("chọn rỗng = chưa kiểm", not M.co_ghi(M.THEO_F["luoc_soi_du"], ""))
kiem("checkbox không tích VẪN là câu trả lời",
     M.co_ghi(M.THEO_F["nam_cham_mat_kim_loai"], 0))

# ═══ 4. Luật sinh sự cố ══════════════════════════════════════════════════
print("\n-- lệch → sự cố: từng luật một --")


def pt(**kw):
    return SC.phat_hien(luot(**kw))


kiem("nhiệt rang 250 → 1 sự cố oPRP công đoạn 3, mức CAO",
     [(c, l, m) for _f, c, l, m, _t in pt(rang_nhiet_do=250)]
     == [("3 Rang", "oPRP", "Cao")], str(pt(rang_nhiet_do=250)))
kiem("nhiệt rang 262 → không sự cố", not pt(rang_nhiet_do=262))
kiem("nhiệt rang 0 (chưa đo) → không sự cố giả", not pt(rang_nhiet_do=0))
kiem("nhiệt rang 275 → cảnh báo vận hành, KHÔNG phải sự cố",
     not pt(rang_nhiet_do=275)
     and len(SC.canh_bao(luot(rang_nhiet_do=275))) == 1)
kiem("vòng quay 6,8 → không sự cố", not pt(rang_vong_quay=6.8))
kiem("vòng quay 5,0 → sự cố oPRP mức Thường",
     [(l, m) for _f, _c, l, m, _t in pt(rang_vong_quay=5.0)] == [("oPRP", "Thường")])
kiem("vòng quay 0 (chưa đo) → không sự cố", not pt(rang_vong_quay=0))
kiem("thùng bột quá hạn 0 → không sự cố", not pt(thung_bot_qua_han=0))
kiem("thùng bột quá hạn 3 → sự cố kèm số thùng",
     len(pt(thung_bot_qua_han=3)) == 1 and "3 thùng" in pt(thung_bot_qua_han=3)[0][4])
kiem("mục Không đạt → sự cố", len(pt(luoc_soi_du="Không đạt")) == 1)
kiem("mục Đạt → không sự cố", not pt(luoc_soi_du="Đạt"))
kiem("mục để trống → không sự cố (để trống khác không đạt)", not pt(luoc_soi_du=""))
kiem("mạt kim loại → sự cố mức CAO",
     [(c, m) for _f, c, _l, m, _t in pt(nam_cham_mat_kim_loai=1)]
     == [("6 Vỡ đỗ, nam châm", "Cao")])
kiem("có vật bắt được nhưng KHÔNG phải mạt kim loại → chỉ cảnh báo",
     not pt(nam_cham_vat="mảnh nhựa")
     and SC.canh_bao(luot(nam_cham_vat="mảnh nhựa")))

bot = {"co_san_xuat_bot": 1, "luot": M.GIUA_CA}
kiem("B7 Dương tính → sự cố Dị ứng mức CAO",
     [(l, m) for _f, _c, l, m, _t in pt(b7_chuyen_doi="Dương tính", **bot)]
     == [("Dị ứng", "Cao")])
kiem("B7 Âm tính → không sự cố", not pt(b7_chuyen_doi="Âm tính", **bot))
kiem("rang lạc thiếu nhiệt mà NGƯỠNG CHƯA THẨM ĐỊNH → không bịa sự cố",
     not pt(b2_rang_lac_nhiet=90, **bot))
CAI_DAT["rang_lac_nhiet_min"] = 150
kiem("đặt ngưỡng rang lạc rồi thì 90 °C → sự cố",
     len(pt(b2_rang_lac_nhiet=90, **bot)) == 1)
CAI_DAT.pop("rang_lac_nhiet_min")
kiem("mục KHÔNG áp dụng ở lượt này thì không sinh sự cố",
     not pt(luot=M.GIUA_CA, a1_ve_sinh="Không đạt"))
kiem("nhiều lệch → nhiều phiếu, không gộp một",
     len(pt(rang_nhiet_do=250, luoc_soi_du="Không đạt", thung_bot_qua_han=2)) == 3)

# ═══ 5. Chặn hoàn tất ════════════════════════════════════════════════════
print("\n-- hoàn tất lượt: chặn cái gì, không chặn cái gì --")


def thu(doc, ham):
    try:
        ham(doc)
        return None
    except Loi as e:
        return str(e)


day_du = {m["f"]: ("Đạt" if m["kieu"] == "chon" else 1)
          for m in M.muc_cham(M.DAU_CA, 0)}
day_du["rang_nhiet_do"] = 260
day_du["rang_vong_quay"] = 6.5
# ĐẾM được 1 thùng quá hạn LÀ một sự cố. Để nguyên 1 ở đây thì "lượt sạch" của
# bài dưới không sạch — và đó là bài học của chính luật này.
day_du["thung_bot_qua_han"] = 0

d = luot(**day_du)
kiem("chấm đủ → qua", thu(d, R.SXQCRound.kiem_de_trong) is None)

d = luot(**{**day_du, "luoc_soi_du": ""})
loi = thu(d, R.SXQCRound.kiem_de_trong)
kiem("để trống mà không có lý do → CHẶN", loi is not None)
kiem("thông báo nói rõ mục nào trống", loi and "2 Sôi liên tục" in loi, loi or "")

d = luot(**{**day_du, "luoc_soi_du": "", "ghi_chu": "hôm nay không luộc mẻ nào"})
kiem("để trống CÓ lý do → cho qua (không ép điền bù)",
     thu(d, R.SXQCRound.kiem_de_trong) is None)

d = luot(**{**day_du, "rang_nhiet_do": 0})
kiem("thiếu nhiệt độ rang → CHẶN dù có ghi chú",
     thu(luot(**{**day_du, "rang_nhiet_do": 0, "ghi_chu": "x"}),
         R.SXQCRound.kiem_bat_buoc) is not None)

d = luot(**{**day_du, "nhap_lai_tu_giay": 1})
kiem("nhập lại từ giấy mà không ghi ngày thật → CHẶN",
     thu(d, R.SXQCRound.kiem_de_trong) is not None)

# ═══ 6. Cờ ghi muộn ══════════════════════════════════════════════════════
print("\n-- cờ ghi muộn: gắn cờ, KHÔNG chặn --")


def ghi_muon(phut, ca="Sáng", l=M.DAU_CA, xong=datetime(2026, 9, 14, 7, 30)):
    d = luot(ca=ca, luot=l, duration_min=phut, finished_at=xong)
    return R.SXQCRound.tinh_ghi_muon(d)


kiem("làm 20 phút trong khung giờ → không muộn", ghi_muon(20) == 0)
kiem("làm 60 phút → muộn (quá 45)", ghi_muon(60) == 1)
kiem("đầu ca ca Sáng hoàn tất 10:30 → muộn",
     ghi_muon(20, xong=datetime(2026, 9, 14, 10, 30)) == 1)
kiem("giữa ca ca Sáng hoàn tất 11:00 → đúng khung",
     ghi_muon(20, l=M.GIUA_CA, xong=datetime(2026, 9, 14, 11, 0)) == 0)
kiem("giữa ca ca Sáng hoàn tất 08:00 → muộn (ghi trước khung)",
     ghi_muon(20, l=M.GIUA_CA, xong=datetime(2026, 9, 14, 8, 0)) == 1)
kiem("lượt Tuần dùng khung giờ của Đầu ca",
     ghi_muon(20, l=M.TUAN, xong=datetime(2026, 9, 14, 10, 30)) == 1)

d = luot(nhap_lai_tu_giay=1, duration_min=600, ghi_chu="ghi thật ngày 12/9",
         started_at=GIO_SERVER[0] - timedelta(minutes=600),
         finished_at=GIO_SERVER[0], **day_du)
R.SXQCRound.before_submit(d)
kiem("nhập lại từ giấy → KHÔNG gắn cờ ghi muộn", d["ghi_muon"] == 0)

# ═══ 7. Trùng lượt ═══════════════════════════════════════════════════════
print("\n-- một (ngày, ca, lượt) chỉ một phiếu --")
TRUNG[:] = []
kiem("chưa có phiếu nào → qua", thu(luot(), R.SXQCRound.kiem_trung) is None)
TRUNG[:] = [{"name": "QC-0009", "luot": M.DAU_CA}]
kiem("đã có Đầu ca → chặn Đầu ca thứ hai",
     thu(luot(name="QC-0002"), R.SXQCRound.kiem_trung) is not None)
loi = thu(luot(name="QC-0002", luot=M.TUAN), R.SXQCRound.kiem_trung)
kiem("đã có Đầu ca → chặn cả lượt Tuần (Tuần LÀ đầu ca thứ Hai)", loi is not None)
kiem("và nói rõ vì sao", loi and "không phải lượt thêm" in loi, loi or "")
TRUNG[:] = [{"name": "QC-0009", "luot": M.GIUA_CA}]
kiem("đã có Giữa ca → vẫn mở được Đầu ca",
     thu(luot(name="QC-0002"), R.SXQCRound.kiem_trung) is None)
TRUNG[:] = []

# ═══ 8. Sinh phiếu sự cố gắn hai chiều ═══════════════════════════════════
print("\n-- sự cố gắn hai chiều với lượt --")
DA_TAO[:] = []
d = luot(**{**day_du, "rang_nhiet_do": 250, "luoc_soi_du": "Không đạt"})
SC.tao_tu_vong_kiem(d)
kiem("sinh đúng 2 phiếu", len(DA_TAO) == 2, str(len(DA_TAO)))
kiem("phiếu trỏ về lượt", all(x["qc_round"] == "QC-0001" for x in DA_TAO))
kiem("lượt trỏ về phiếu", [r["incident"] for r in d["su_co"]]
     == [x["name"] for x in DA_TAO])
kiem("phiếu mở sẵn, chờ người xử lý",
     all(x["trang_thai"] == "Mở" for x in DA_TAO))
kiem("phiếu ghi rõ mục nào", sorted(x["muc"].split()[0] for x in DA_TAO)
     == ["2", "3a"], str([x["muc"] for x in DA_TAO]))
kiem("gọi lại lần nữa không nhân đôi bảng con", (
    lambda: (DA_TAO.clear(), SC.tao_tu_vong_kiem(d), len(d["su_co"]) == 2)[-1])())

# ═══ 9. Sự cố không có luật nào thì không sinh ════════════════════════════
DA_TAO[:] = []
d = luot(**day_du)
SC.tao_tu_vong_kiem(d)
kiem("lượt sạch → không phiếu sự cố nào", not DA_TAO and not d["su_co"])

# ═══ 10. Khoá sau khi Ban ISO xem xét ════════════════════════════════════
print("\n-- lượt đã xem xét thì KHOÁ, kể cả với Ban ISO --")
frappe.get_roles = lambda u=None: ["ISO Manager"]
d = luot(reviewed_on="2026-09-20 10:00:00", reviewed_by="iso@rvhg.vn")
loi = thu(d, R.SXQCRound.on_cancel)
kiem("Ban ISO KHÔNG huỷ được lượt đã ký xem xét", loi is not None)
kiem("và chỉ đường sang cách làm đúng",
     loi and "Hiệu chỉnh hồ sơ" in loi, loi or "")
frappe.get_roles = lambda u=None: ["System Manager"]
kiem("System Manager vẫn gỡ được (và việc đó có vết trong log)",
     thu(d, R.SXQCRound.on_cancel) is None)
frappe.get_roles = lambda u=None: ["ISO Manager"]
kiem("lượt CHƯA xem xét thì Ban ISO huỷ được",
     thu(luot(), R.SXQCRound.on_cancel) is None)
frappe.get_roles = lambda u=None: ["SX QC"]

# ═══ 11. Tờ in A4 ════════════════════════════════════════════════════════
print("\n-- tờ ngày BM.08.01: dựng được và có đủ thứ auditor hỏi --")
import jinja2  # noqa: E402

tt = jinja2.Environment(
    loader=jinja2.FileSystemLoader("sx/qc"), autoescape=True).get_template("day_sheet.html")
r1 = luot(**{**day_du, "luot": M.TUAN, "finished_at": datetime(2026, 9, 14, 7, 30),
             "ghi_muon": 1, "qc_user": "hoa@rvhg.vn", "rang_nhiet_do": 250,
             "ghi_chu": "không luộc mẻ nào buổi sáng"})
cot = [{"doc": r1, "ap": {m["f"] for m in M.muc_ap_dung(M.TUAN, 0)}}]
hang = []
for ma, ten, oprp, _g in M.BUOC:
    mb = [m for m in M.MUC if m["buoc"] == ma and not m["bot"]]
    if not mb:
        continue
    hang.append({"buoc": True, "ten": f"{ma}. {ten}"})
    for m in mb:
        hang.append({"buoc": False, "so": m["so"], "nhan": m["nhan"],
                     "o": ["Đ" if m["f"] in cot[0]["ap"] else ""],
                     "khong_ap": [m["f"] not in cot[0]["ap"]]})
html = tt.render(
    ngay="2026-09-14", rounds=[r1], hang=hang, co_bot=0,
    su_co=[{"name": "SC-0001", "muc": "3a Nhiệt độ rang", "mo_ta": "250 < 255",
            "muc_do": "Cao", "trang_thai": "Mở", "xu_ly_ngay": "chỉnh lại nhiệt",
            "quyet_dinh_sp": "Không ảnh hưởng sản phẩm"}],
    frappe=types.SimpleNamespace(utils=types.SimpleNamespace(
        formatdate=lambda d, f=None: "14/09/2026",
        format_datetime=lambda d, f=None: "20/09/2026 10:00")))
kiem("dựng được tờ in", "BM.08.01" in html)
# Auditor cầm tờ này lên và hỏi: ai ghi, ghi lúc mấy giờ, mục nào không đạt, và
# đã làm gì. Thiếu bất kỳ cái nào thì tờ giấy không dùng được để chứng minh.
for ten, can in [("nhãn ĐẦY ĐỦ của mục (không phải nhãn ngắn của điện thoại)",
                  "Vệ sinh đầu ca: xưởng, bề mặt, thiết bị sạch khô"),
                 ("giờ hoàn tất", "07:30"),
                 ("tên người kiểm", "hoa@rvhg.vn"),
                 # Tìm đúng Ô TRONG BẢNG, không tìm ký tự ✻ trơn: dòng chú
                 # thích cuối trang lúc nào cũng có ✻, nên bài kiểm cũ vẫn "đạt"
                 # cả khi bỏ hẳn cờ khỏi bảng. Đã dính thật lúc thử phá code.
                 ("cờ ghi muộn ở đúng ô trong bảng", '<span class="muon">✻</span>'),
                 ("ghi chú lý do để trống", "không luộc mẻ nào"),
                 ("bảng sự cố kèm xử lý", "chỉnh lại nhiệt"),
                 ("mức độ sự cố", "Cao")]:
    kiem(f"tờ in có {ten}", can in html, "" if can in html else f"thiếu {can!r}")
kiem("ô của mục KHÔNG áp dụng được tô xám, không để trắng như chưa ghi",
     'class="o na"' in html)

# ═══ 12. Print Format BM.08.02 ═══════════════════════════════════════════
# Lỗi cú pháp Jinja trong print format chỉ lộ ra lúc có người bấm In — tức là
# lúc Ban ISO cần tờ giấy, không phải lúc deploy.
print("\n-- print format phiếu sự cố BM.08.02 --")
pf = [x for x in json.load(open("sx/fixtures/print_format.json", encoding="utf-8"))
      if x.get("module") == "QC"]
kiem("có print format cho phiếu sự cố", len(pf) == 1, str([x["name"] for x in pf]))


class _D(dict):
    def __getattr__(self, k):
        return self.get(k)


mau = _D({"name": "SC-2026-0007", "ngay": "2026-09-14", "ca": "Sáng",
          "nguon": "Vòng kiểm QC", "qc_round": "QC-0003", "cong_doan": "3 Rang",
          "loai": "oPRP", "muc": "3a Nhiệt độ rang", "muc_do": "Cao",
          "qua_han": 1, "lo_anh_huong": "DX-140926", "so_luong": "420 hộp",
          "mo_ta": "Rang: nhiệt độ 248 °C < 255 °C",
          "xu_ly_ngay": "Dừng máy, chỉnh lại nhiệt", "trang_thai": "Mở",
          "owner": "hoa@rvhg.vn"})
gia_frappe = types.SimpleNamespace(utils=types.SimpleNamespace(
    formatdate=lambda x, f=None: "14/09/2026",
    format_datetime=lambda x, f=None: ""))
for x in pf:
    try:
        ra = jinja2.Environment(autoescape=True).from_string(
            x["html"]).render(doc=mau, frappe=gia_frappe)
        loi_pf = None
    except Exception as e:            # noqa: BLE001 — bắt mọi lỗi template
        ra, loi_pf = "", f"{type(e).__name__}: {e}"
    kiem(f'{x["name"]}: dựng được', not loi_pf, loi_pf or "")
    # Phiếu sự cố mà thiếu ba ô này thì không dùng làm hồ sơ được: lô nào, đã
    # làm gì ngay lúc đó, và ai ký.
    for ten, can in [("số phiếu", "SC-2026-0007"), ("lô ảnh hưởng", "DX-140926"),
                     ("xử lý ngay", "chỉnh lại nhiệt"),
                     ("ô ký của Ban ISO", "Trưởng Ban ISO"),
                     ("dấu quá hạn", "QUÁ HẠN")]:
        kiem(f"  có {ten}", can in ra)

# Cửa sổ in mở bằng about:blank KHÔNG thừa kế bảng mã của trang cha; trình duyệt
# tự đoán và nó đoán sai, tờ giấy in ra đầy "Nhiá»‡t Ä'á»™". Không lỗi nào hiện
# ra — chỉ có tờ giấy vứt đi, mà lại là tờ đưa cho auditor.
js = open("sx/public/sx/views/qc_history.js", encoding="utf-8").read()
kiem("cửa sổ in tự khai charset utf-8",
     "charset=\"utf-8\"" in js and "document.write" in js)

print("QC-FAIL ({} ca)".format(hong) if hong else "QC-OK")
sys.exit(1 if hong else 0)

