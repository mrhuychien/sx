"""D145 (W19) + D164 (W32) — phiếu rework BM.15.01.

Vì sao phải có bài này:
  · Rework quá 10% khối lượng mẻ mà vẫn ghi được → trái tài liệu, không ai thấy.
  · Hàng CÓ LẠC đưa vào sản phẩm KHÔNG LẠC → sự cố dị ứng thật.
  · Phiếu sự cố quyết định "Rework" đóng được khi chưa có phiếu rework → hồ sơ đứt.
  · "QLSX quyết định" ghi tên một người không phải QLSX, giờ kết thúc trước giờ bắt đầu → ô ký trên giấy vô nghĩa.

Nạp sx/qc/rework.py, controller SX Rework + SX Su Co, sx/api/qc_rework.py THẬT; frappe giả.
Chạy: python3 scripts/test-rework.py   (verify.sh gọi sẵn)
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
RW = F.nap("sx.qc.rework", "sx/qc/rework.py")
A = F.nap("sx.api.qc_rework", "sx/api/qc_rework.py")
RWC = F.nap("rw_ctl", "sx/qc/doctype/sx_rework/sx_rework.py")
SCC = F.nap("sc_ctl", "sx/qc/doctype/sx_su_co/sx_su_co.py")
F.dang_ky(RW.PT, RWC.SXRework)
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")
F.bang(RW.SP).update({
    "SP-SEN": {"name": "SP-SEN", "so_cong_bo": "01/2023", "ten_san_pham": "Bánh đậu xanh sen", "co_lac": 0,
               "co_sua_bot": 0, "ngung_san_xuat": 0},
    "SP-LAC": {"name": "SP-LAC", "so_cong_bo": "05/2023", "ten_san_pham": "Bánh đậu xanh lạc", "co_lac": 1,
               "co_sua_bot": 0, "ngung_san_xuat": 0},
    "SP-SUA": {"name": "SP-SUA", "so_cong_bo": "01/HOANGGIANG/2026", "ten_san_pham": "Bột sữa", "co_lac": 0,
               "co_sua_bot": 1, "ngung_san_xuat": 0}})

# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- luật rework (hàm thuần) --")
SEN = {"co_lac": 0, "co_sua_bot": 0, "ten": "sen"}
LAC = {"co_lac": 1, "co_sua_bot": 0, "ten": "lạc"}
SUA = {"co_lac": 0, "co_sua_bot": 1, "ten": "sữa"}
kiem("tỷ lệ = rework / mẻ × 100, mẻ 0 → không tính", RW.ty_le(12, 150) == 8.0 and RW.ty_le(5, 0) is None)
kiem("đúng 10% → được", not RW.kiem({"kl_rework": 15, "kl_me": 150}, SEN, SEN)["loi"])
r = RW.kiem({"kl_rework": 16, "kl_me": 150}, SEN, SEN)
kiem("10,67% → chặn, nói tối đa bao nhiêu kg", r["loi"] and "15 kg" in r["loi"][0] and r["ty_le"] == 10.67, r)
kiem("rework nặng hơn cả mẻ → chặn, nói rõ; số 0 → chặn",
     "lớn hơn cả mẻ" in RW.kiem({"kl_rework": 200, "kl_me": 150}, SEN, SEN)["loi"][0]
     and len(RW.kiem({}, SEN, SEN)["loi"]) == 2)
kiem("hàng CÓ LẠC vào sản phẩm KHÔNG LẠC → chặn", any("LẠC" in x for x in RW.kiem({"kl_rework": 1, "kl_me": 100},
                                                                                LAC, SEN)["loi"]))
kiem("lạc vào lạc / không lạc vào lạc → được", not RW.kiem({"kl_rework": 1, "kl_me": 100}, LAC, LAC)["loi"]
     and not RW.kiem({"kl_rework": 1, "kl_me": 100}, SEN, LAC)["loi"])
r = RW.kiem({"kl_rework": 1, "kl_me": 100}, SUA, SEN)
kiem("sữa bột vào sản phẩm không sữa → chỉ cảnh báo (tài liệu chưa nói chặn)", not r["loi"] and r["canh_bao"], r)
BAY = "2026-10-09 10:00:00"
kg = RW.kiem_gio
kiem("giờ: bắt đầu 07:30 – kết thúc 08:10 → được; trống cả hai → được",
     kg({"gio_bat_dau": "07:30", "gio_ket_thuc": "08:10"}, BAY) == {"loi": [], "canh_bao": []}
     and kg({}, BAY) == {"loi": [], "canh_bao": []})
kiem("giờ kết thúc trước giờ bắt đầu → chặn (rework trong cùng ngày)",
     "trước giờ bắt đầu" in kg({"gio_bat_dau": "08:10", "gio_ket_thuc": "07:30"}, BAY)["loi"][0])
kiem("giờ sai dạng / giờ 25:00 → chặn", "giờ:phút" in kg({"gio_bat_dau": "8 giờ"}, BAY)["loi"][0]
     and "giờ:phút" in kg({"gio_ket_thuc": "25:00"}, BAY)["loi"][0])
kiem("bắt đầu = kết thúc → được (không chặn oan)", not kg({"gio_bat_dau": "07:30", "gio_ket_thuc": "07:30"}, BAY)["loi"])
kiem("có giờ QLSX quyết định mà chưa chọn QLSX → chặn; giờ quyết định ở tương lai → chặn",
     "chưa chọn QLSX" in kg({"qlsx_luc": "2026-10-09 07:00:00"}, BAY)["loi"][0]
     and "sau bây giờ" in kg({"qlsx_quyet_dinh": "q", "qlsx_luc": "2026-10-09 11:00:00"}, BAY)["loi"][0])
r = kg({"ngay": "2026-10-09", "qlsx_quyet_dinh": "q", "qlsx_luc": "2026-10-09 08:00:00", "gio_bat_dau": "07:30"}, BAY)
kiem("QLSX quyết định SAU giờ bắt đầu rework (cùng ngày) → chỉ cảnh báo (QT.15: quyết định trước khi làm)",
     not r["loi"] and "sau giờ bắt đầu" in r["canh_bao"][0], r)
kiem("… quyết định đúng giờ bắt đầu → không cảnh báo",
     not kg({"ngay": "2026-10-09", "qlsx_quyet_dinh": "q", "qlsx_luc": "2026-10-09 07:30:00", "gio_bat_dau": "07:30"},
            BAY)["canh_bao"])
kiem("… quyết định trước giờ bắt đầu, hoặc khác ngày phiếu → không cảnh báo",
     not kg({"ngay": "2026-10-09", "qlsx_quyet_dinh": "q", "qlsx_luc": "2026-10-09 07:00:00", "gio_bat_dau": "07:30"},
            BAY)["canh_bao"]
     and not kg({"ngay": "2026-10-08", "qlsx_quyet_dinh": "q", "qlsx_luc": "2026-10-09 08:00:00", "gio_bat_dau": "07:30"},
                BAY)["canh_bao"])

# ═══ 2. Lập phiếu ═════════════════════════════════════════════════════════
print("\n-- lập phiếu, quyền --")


def lap(**k):
    return A.lap_phieu(json.dumps(k))


r = lap(sp_nguon="SP-SEN", kl_rework=12, sp_dich="SP-SEN", kl_me=150, me="M3", mo_ta_nguon="bánh vỡ HSD 05/07/2027")
p = F.bang(RW.PT)[r["name"]]
kiem("lập được: tỷ lệ 8%, cờ lạc ghi lại, người lập tự điền", r["ty_le"] == 8.0 and p["nguoi_lap"] == "qc@x"
     and p["nguon_co_lac"] == 0 and p["dich_co_lac"] == 0, p)
loi = thu(lambda: lap(sp_nguon="SP-SEN", kl_rework=20, sp_dich="SP-SEN", kl_me=150))
kiem("vượt 10% → chặn (cả đường Desk — luật ở controller)", loi and "vượt 10%" in loi, loi)
loi = thu(lambda: lap(sp_nguon="SP-LAC", kl_rework=5, sp_dich="SP-SEN", kl_me=150))
kiem("bánh lạc vào bánh sen → chặn", loi and "CÓ LẠC" in loi, loi)
kiem("thiếu sản phẩm nhận → chặn, nói cần cờ lạc", "sản phẩm nhận" in (thu(lambda: lap(
    sp_nguon="SP-SEN", kl_rework=1, kl_me=100)) or ""))
kiem("thiếu sản phẩm của hàng đem rework → chặn", "hàng đem rework" in (thu(lambda: lap(
    sp_dich="SP-SEN", kl_rework=1, kl_me=100)) or ""))
kiem("ngày sau hôm nay → chặn", "sau hôm nay" in (thu(lambda: lap(ngay="2026-10-10", sp_nguon="SP-SEN", kl_rework=1,
                                                                  sp_dich="SP-SEN", kl_me=100)) or ""))
F.BAO.clear()
lap(sp_nguon="SP-SUA", kl_rework=1, sp_dich="SP-SEN", kl_me=100)
kiem("sữa vào không sữa → lập được, có cảnh báo", any("sữa bột" in b for b in F.BAO), F.BAO)
F.vai("Production Manager", u="qlsx@x")
kiem("QLSX lập được", thu(lambda: lap(sp_nguon="SP-LAC", kl_rework=3, sp_dich="SP-LAC", kl_me=100)) is None)
F.vai("Stock User")
kiem("người ngoài không xem được", thu(A.tong_quan) is not None)
F.vai("SX QC", u="qc2@x")
kiem("QC khác không xoá phiếu người khác", thu(lambda: A.xoa(r["name"])) is not None)
F.vai("SX QC")
F.bang(RW.PT)[r["name"]]["creation"] = "2026-10-01 08:00:00"
kiem("người lập không xoá phiếu từ hôm trước", "Ban ISO" in (thu(lambda: A.xoa(r["name"])) or ""))
F.vai("ISO Manager")
kiem("Ban ISO xoá được", thu(lambda: A.xoa(r["name"])) is None)
F.vai("SX QC")
q = A.tong_quan()
kiem("tổng quan tháng: danh sách phiếu, sản phẩm có cờ lạc, tối đa 10%",
     len(q["ds"]) == 2 and q["toi_da"] == 10.0 and any(x["co_lac"] for x in q["san_pham"])
     and q["ds"][0]["ten_dich"].startswith("05/2023"), q["ds"])

# ═══ 2b. QLSX quyết định, giờ bắt đầu – kết thúc (W32) ═══════════════════
print("\n-- QLSX quyết định (người + giờ), giờ bắt đầu – kết thúc --")
F.bang("Has Role").update({
    "hr1": {"name": "hr1", "parent": "qlsx@x", "parenttype": "User", "role": "Production Manager"},
    "hr2": {"name": "hr2", "parent": "gd@x", "parenttype": "User", "role": "SX Quan Ly"},
    "hr3": {"name": "hr3", "parent": "qc@x", "parenttype": "User", "role": "SX QC"},
    "hr4": {"name": "hr4", "parent": "Administrator", "parenttype": "User", "role": "SX Quan Ly"},
    "hr5": {"name": "hr5", "parent": "cu@x", "parenttype": "User", "role": "Production Manager"}})
F.bang("User").update({"Administrator": {"name": "Administrator", "full_name": "Administrator", "enabled": 1},
                       "qlsx@x": {"name": "qlsx@x", "full_name": "Trần Văn Quản", "enabled": 1},
                       "gd@x": {"name": "gd@x", "full_name": "Đào Văn Tiến", "enabled": 1},
                       "cu@x": {"name": "cu@x", "full_name": "QLSX đã nghỉ", "enabled": 0}})
F.vai("SX QC")
r = lap(sp_nguon="SP-SEN", kl_rework=6, sp_dich="SP-SEN", kl_me=100, qlsx_quyet_dinh="qlsx@x",
        qlsx_luc="2026-10-09T07:10", gio_bat_dau="07:30", gio_ket_thuc="08:05")
p = F.bang(RW.PT)[r["name"]]
kiem("lập phiếu có QLSX quyết định + giờ, giờ bắt đầu – kết thúc → lưu đúng (giờ datetime-local đổi sang dạng DB)",
     p["qlsx_quyet_dinh"] == "qlsx@x" and p["qlsx_luc"] == "2026-10-09 07:10:00" and p["gio_bat_dau"] == "07:30:00"
     and p["gio_ket_thuc"] == "08:05:00", p)
loi = thu(lambda: lap(sp_nguon="SP-SEN", kl_rework=6, sp_dich="SP-SEN", kl_me=100, qlsx_quyet_dinh="qc@x"))
kiem("chọn người KHÔNG có vai QLSX vào ô QLSX quyết định → chặn", loi and "không có vai QLSX" in loi, loi)
kiem("giờ kết thúc trước giờ bắt đầu → chặn (cả Desk)", "trước giờ bắt đầu" in (thu(lambda: lap(
    sp_nguon="SP-SEN", kl_rework=6, sp_dich="SP-SEN", kl_me=100, gio_bat_dau="09:00", gio_ket_thuc="08:00")) or ""))
r = lap(sp_nguon="SP-SEN", kl_rework=6, sp_dich="SP-SEN", kl_me=100, qlsx_quyet_dinh="gd@x")
kiem("Giám đốc (SX Quan Ly) cũng được; chọn QLSX mà không ghi giờ → lấy giờ lúc lưu",
     str(F.bang(RW.PT)[r["name"]]["qlsx_luc"])[:16] == "2026-10-09 10:00")
F.BAO.clear()
lap(sp_nguon="SP-SEN", kl_rework=6, sp_dich="SP-SEN", kl_me=100, qlsx_quyet_dinh="qlsx@x",
    qlsx_luc="2026-10-09T08:00", gio_bat_dau="07:30")
kiem("QLSX quyết định sau giờ bắt đầu → lưu được, có cảnh báo", any("sau giờ bắt đầu" in b for b in F.BAO), F.BAO)
q = A.tong_quan()
kiem("tổng quan: danh sách QLSX để chọn = người có vai QLSX / Giám đốc còn dùng (bỏ Administrator, tài khoản khoá)",
     sorted(u["name"] for u in q["qlsx"]) == ["gd@x", "qlsx@x"]
     and {u["name"]: u["ten"] for u in q["qlsx"]}["qlsx@x"] == "Trần Văn Quản", q["qlsx"])
x = next(x for x in q["ds"] if x["gio_ket_thuc"])
kiem("dòng phiếu: giờ 'HH:MM', tên QLSX, giờ quyết định", x["gio_bat_dau"] == "07:30" and x["gio_ket_thuc"] == "08:05"
     and x["ten_qlsx"] == "Trần Văn Quản" and x["qlsx_luc"] == "2026-10-09 07:10", x)

# ═══ 3. Đóng sự cố quyết định Rework ══════════════════════════════════════
print("\n-- sự cố quyết định Rework (BM.15.01) --")
sc = SCC.SXSuCo({"doctype": "SX Su Co", "name": "SC-2026-0007", "trang_thai": "Đóng", "xu_ly_ngay": "cô lập lô",
                 "quyet_dinh_sp": RW.QD_REWORK})
loi = thu(sc.kiem_du_de_dong)
kiem("đóng sự cố quyết định Rework khi CHƯA có phiếu rework → chặn", loi and "phiếu rework BM.15.01" in loi, loi)
lap(sp_nguon="SP-SEN", kl_rework=5, sp_dich="SP-SEN", kl_me=100, su_co="SC-2026-0007")
kiem("có phiếu rework gắn sự cố → đóng được", thu(sc.kiem_du_de_dong) is None)
sc2 = SCC.SXSuCo({"doctype": "SX Su Co", "name": "SC-2026-0008", "trang_thai": "Đóng", "xu_ly_ngay": "x",
                  "quyet_dinh_sp": "Loại bỏ"})
kiem("quyết định khác (Loại bỏ) → không đòi phiếu rework", thu(sc2.kiem_du_de_dong) is None)

# ═══ 4. Bản in, màn hình ══════════════════════════════════════════════════
print("\n-- BM.15.01, màn hình --")
if F.jinja2:
    h = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", A.in_bm1501("2026-10").split("</style>")[1]))
    kiem("BM.15.01: tháng, hàng → sản phẩm nhận, kg, tỷ lệ, lạc nguồn / nhận, sự cố, chỗ ký",
         "BM.15.01" in h and "Tháng 10/2026" in h and "01/2023 · Bánh đậu xanh sen" in h and "5%" in h
         and "SC-2026-0007" in h and "Quản lý sản xuất" in h, h[:300])
    kiem("BM.15.01 (W32): cột giờ bắt đầu – kết thúc, QLSX quyết định (tên + giờ)",
         "Giờ bắt đầu – kết thúc" in h and "07:30 – 08:05" in h and "QLSX quyết định (giờ)" in h
         and "Trần Văn Quản 07:10" in h, h[:600])
kiem("route #/qc/rework + nút ở Hôm nay", "rework: '/assets/sx/sx/views/qc_rework.js'" in open(
    "sx/public/sx/views/qc.js", encoding="utf-8").read() and "#/qc/rework" in open(
    "sx/public/sx/views/qc_home.js", encoding="utf-8").read())
js = open("sx/public/sx/views/qc_rework.js", encoding="utf-8").read()
kiem("màn rework: tính trước tỷ lệ + lạc (khoá nút), lập, xoá, in", all(x in js for x in (
    "sx.api.qc_rework.lap_phieu", "sx.api.qc_rework.xoa", "sx.api.qc_rework.in_bm1501", "ok.disabled = loi.length > 0")))
kiem("màn rework (W32): chọn QLSX quyết định + giờ, giờ bắt đầu – kết thúc gửi lên", all(x in js for x in (
    "qlsx_quyet_dinh: ql.value", "qlsx_luc:", "gio_bat_dau: gioBd.value", "gio_ket_thuc:", "dl.qlsx")))
fl = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_rework/sx_rework.json", encoding="utf-8"))["fields"]}
kiem("SX Rework: ô QLSX quyết định (User), giờ quyết định, giờ bắt đầu, kết thúc",
     fl["qlsx_quyet_dinh"]["options"] == "User" and fl["qlsx_luc"]["fieldtype"] == "Datetime"
     and fl["gio_bat_dau"]["fieldtype"] == fl["gio_ket_thuc"]["fieldtype"] == "Time")

F.ket_thuc("REWORK")
