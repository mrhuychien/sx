"""D147 (W23) — nhập lại bản giấy (giờ thực tế, ảnh tờ giấy), lượt "Bổ sung" sau mất điện.

Vì sao phải có bài này:
  · Nhập lại từ giấy mà không có giờ kiểm thật → hồ sơ chỉ có giờ NHẬP, auditor hỏi giờ KIỂM.
  · Lượt bổ sung bị luật "một lượt mỗi ngày" chặn → mất điện hai lần là không ghi được lần hai.
  · Lượt bổ sung bị đếm như một trong ba lượt → ngày thiếu lượt trông như đủ.
  · Lượt bổ sung không lý do → một lượt ngoài lịch không ai giải thích được.

Nạp sx/qc/muc.py, controller SX QC Round, sx/api/qc.py THẬT; frappe giả (fakefrappe).
Chạy: python3 scripts/test-bosung.py   (verify.sh gọi sẵn)
"""

import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

F.cai()
Q = F.nap_qc()
M = sys.modules["sx.qc.muc"]
NH = sys.modules["sx.qc.nhac"]
RC = F.nap("round_ctl", "sx/qc/doctype/sx_qc_round/sx_qc_round.py")


DJ = json.load(open("sx/qc/doctype/sx_qc_round/sx_qc_round.json", encoding="utf-8"))["fields"]


class Luot(RC.SXQCRound):
    """Bảng con trống trên frappe là [] — Document giả không biết field nào là bảng."""

    def __init__(self, d=None):
        super().__init__(d)
        for f in DJ:
            if f["fieldtype"] == "Table" and self._d.get(f["fieldname"]) is None:
                self._d[f["fieldname"]] = []


F.dang_ky("SX QC Round", Luot)


class Tep(F.DocThuong):
    def insert(self, ignore_permissions=False, **k):
        super().insert()
        self["file_url"] = f"/private/files/{self['file_name']}"
        return self


F.LOP["File"] = Tep
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")

# ═══ 1. Bộ mục, thứ tự ════════════════════════════════════════════════════
print("\n-- lượt Bổ sung: bộ mục, thứ tự --")
kiem("Bổ sung là một lượt hợp lệ, có lý do mẫu", M.BO_SUNG in M.LUOT and "Mất điện" in M.LY_DO_BO_SUNG)
bc = M.boi_canh(1)
kiem("bộ mục lượt Bổ sung = bộ mục lượt Trưa (các phép đo đang sản xuất)",
     [m["f"] for m in M.muc_cham(M.BO_SUNG, bc)] == [m["f"] for m in M.muc_cham(M.TRUA, bc)]
     and len(M.muc_cham(M.BO_SUNG, bc)) > 0)
kiem("Bổ sung xếp sau ba lượt trong ngày", M.thu_tu_luot(M.BO_SUNG) == len(M.LUOT_TRONG_NGAY))
kiem("ba lượt trong ngày không đổi", M.LUOT_TRONG_NGAY == (M.DAU_SANG, M.TRUA, M.CUOI_CHIEU))
dj = {f["fieldname"]: f for f in DJ}
kiem("doctype: lượt có Bổ sung; có giờ thực tế, ảnh bản giấy, lý do bổ sung",
     "Bổ sung" in dj["luot"]["options"] and dj["gio_thuc_te"]["fieldtype"] == "Time"
     and dj["anh_giay"]["fieldtype"] == "Attach Image" and "ly_do_bo_sung" in dj)

# ═══ 2. Mở lượt bổ sung ═══════════════════════════════════════════════════
print("\n-- mở lượt bổ sung --")
loi = thu(lambda: Q.start_round("2026-10-09", M.BO_SUNG))
kiem("không lý do → chặn", loi and "lý do" in loi, loi)
r1 = Q.start_round("2026-10-09", M.BO_SUNG, ly_do_bo_sung="Mất điện — 10:20 có điện lại")
p1 = F.bang("SX QC Round")[r1["name"]]
kiem("mở được: lượt Bổ sung, lý do lưu, người mở, chi tiết trả lý do", p1["luot"] == M.BO_SUNG
     and p1["ly_do_bo_sung"].startswith("Mất điện") and r1["ly_do_bo_sung"].startswith("Mất điện"), r1)
r1b = Q.start_round("2026-10-09", M.BO_SUNG, ly_do_bo_sung="Mất điện")
kiem("bấm lại khi lượt bổ sung còn dở → mở lại chính nó (không đẻ phiếu thứ hai)", r1b["name"] == r1["name"]
     and len(F.bang("SX QC Round")) == 1)
F.bang("SX QC Round")[r1["name"]]["docstatus"] = 1
r2 = Q.start_round("2026-10-09", M.BO_SUNG, ly_do_bo_sung="Sự cố máy — M2 kẹt lồng")
kiem("mất điện / sự cố LẦN HAI trong ngày → lượt bổ sung mới (không bị luật một lượt mỗi ngày chặn)",
     r2["name"] != r1["name"] and len(F.bang("SX QC Round")) == 2)
Q.start_round("2026-10-09", M.TRUA)
kiem("lượt Trưa vẫn mở được bình thường bên cạnh lượt bổ sung", len(F.bang("SX QC Round")) == 3)
kiem("lượt Trưa thứ hai trong ngày vẫn bị chặn (luật cũ giữ nguyên)",
     thu(lambda: F.get_doc({"doctype": "SX QC Round", "ngay": "2026-10-09", "luot": M.TRUA,
                            "qc_user": "qc@x"}).insert()) is not None)
d = RC.SXQCRound({"doctype": "SX QC Round", "name": "QC-X", "ngay": "2026-10-09", "luot": M.BO_SUNG,
                  "ly_do_bo_sung": " "})
kiem("Desk: lượt bổ sung để trống lý do → chặn", "lý do" in (thu(d.validate) or ""))
t = Q.get_today("2026-10-09")
kiem("màn Hôm nay: vẫn ba ô lượt; lượt bổ sung liệt kê riêng, kèm lý do",
     len(t["o_luot"]) == 3 and [x["name"] for x in t["bo_sung"]] == [r1["name"], r2["name"]]
     and t["ly_do_bo_sung"] == list(M.LY_DO_BO_SUNG), t["bo_sung"])

# ═══ 3. Nhập lại bản giấy ═════════════════════════════════════════════════
print("\n-- nhập lại bản giấy: giờ thực tế, ảnh --")
rg = Q.start_round("2026-10-07", M.DAU_SANG, nhap_lai_tu_giay=1)
Q.save_round(rg["name"], json.dumps({"gio_thuc_te": "07:40:00", "ghi_chu": "ghi thật 07/10"}))
kiem("lưu được giờ kiểm thực tế (ô phụ, không phải mục kiểm)", F.bang("SX QC Round")[rg["name"]]["gio_thuc_te"]
     == "07:40:00")
d = F.get_doc("SX QC Round", rg["name"])
kiem("có giờ thực tế + ghi chú → qua khâu kiểm khi hoàn tất", thu(d.kiem_de_trong) is None, thu(d.kiem_de_trong))
d.set("gio_thuc_te", None)
loi = thu(d.kiem_de_trong)
kiem("hoàn tất lượt nhập lại mà thiếu giờ thực tế → chặn", loi and "giờ kiểm thực tế" in loi, loi)
d.set("nhap_lai_tu_giay", 0)
kiem("lượt ghi trực tiếp (không nhập lại) → không đòi giờ thực tế", thu(d.kiem_de_trong) is None)
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
r = Q.them_anh_giay(rg["name"], PNG)
kiem("ảnh bản giấy: lưu tệp riêng tư gắn lượt, ghi đường dẫn lên lượt",
     r["anh_giay"].startswith("/private/files/") and F.bang("SX QC Round")[rg["name"]]["anh_giay"] == r["anh_giay"]
     and any(x.get("attached_to_name") == rg["name"] and x.get("is_private") for x in F.bang("File").values()))
kiem("tệp không phải ảnh → chặn", "không phải ảnh" in (thu(lambda: Q.them_anh_giay(rg["name"], "aGVsbG8=")) or ""))
F.vai("Stock User")
kiem("người ngoài QC không gửi ảnh được", thu(lambda: Q.them_anh_giay(rg["name"], PNG)) is not None)
F.vai("SX QC")

# ═══ 4. Đếm lượt: bổ sung không thay lượt nào ══════════════════════════════
print("\n-- lượt bổ sung không tính vào ba lượt --")
F.bang("SX QC Round").clear()
for ten_l, ds in (("Đầu sáng", 1), ("Trưa", 1), ("Bổ sung", 1)):
    n = f"QC-{ten_l}"
    F.bang("SX QC Round")[n] = {"name": n, "ngay": "2026-10-08", "luot": ten_l, "docstatus": ds, "ghi_muon": 0,
                                "nhap_lai_tu_giay": 0, "reviewed_on": None, "creation": "2026-10-08 08:00:00"}
F.vai("ISO Manager")
db = Q.dashboard("2026-10-01", "2026-10-31")
kiem("Xem xét: 2 lượt chính + 1 bổ sung → 'đã làm' đếm 2, bổ sung đếm riêng, ngày 08/10 vẫn thiếu lượt",
     db["so_luot"] == 2 and db["so_bo_sung"] == 1 and "2026-10-08" in db["ngay_thieu"]
     and db["theo_ngay"]["2026-10-08"]["luot"] == 2, (db["so_luot"], db["so_bo_sung"], db["ngay_thieu"]))
F.vai("SX QC")
luot = [dict(x) for x in F.bang("SX QC Round").values()]
m = [x for x in NH.tinh(F.hom_nay(), luot, [], {}) if "đi thiếu lượt" in x["tieu_de"]]
kiem("hộp nhắc: ngày có lượt bổ sung vẫn báo thiếu lượt (2/3)", m and "08/10 (2/3)" in m[0]["chi_tiet"], m)

# ═══ 5. Tờ in, màn hình ═══════════════════════════════════════════════════
print("\n-- tờ in BM.08.01, màn hình --")
if F.jinja2:
    F.bang("SX QC Round").clear()
    base = {"ngay": "2026-10-08", "docstatus": 1, "ghi_muon": 0, "qc_user": "qc@x", "co_san_xuat_bot": 0,
            "reviewed_on": None, "phien_ban": 2}
    F.bang("SX QC Round").update({
        "QC-A": dict(base, name="QC-A", luot="Đầu sáng", nhap_lai_tu_giay=1, gio_thuc_te="07:40:00",
                     anh_giay="/private/files/a.png", started_at=datetime(2026, 10, 8, 16, 0),
                     finished_at=datetime(2026, 10, 8, 16, 20), creation="2026-10-08 16:00:00"),
        "QC-B": dict(base, name="QC-B", luot="Bổ sung", nhap_lai_tu_giay=0, ly_do_bo_sung="Mất điện — 10:20",
                     started_at=datetime(2026, 10, 8, 10, 25), finished_at=datetime(2026, 10, 8, 10, 50),
                     creation="2026-10-08 10:25:00")})
    h = re.sub(r"\s+", " ", re.sub("<[^>]+>", " ", Q.day_sheet("2026-10-08")))
    kiem("tờ ngày: cột Bổ sung kèm giờ mở + lý do; dòng giờ kiểm thực tế cho lượt nhập lại (📷 có ảnh)",
         "Bổ sung 10:25 · Mất điện — 10:20" in h and "Giờ kiểm thực tế" in h and "07:40 📷" in h, h[:300])
rj = open("sx/public/sx/views/qc_round.js", encoding="utf-8").read()
kiem("màn lượt: ô giờ thực tế + chụp ảnh bản giấy khi nhập lại; dòng lý do lượt bổ sung",
     "gio_thuc_te" in rj and "sx.api.qc.them_anh_giay" in rj and "dl.ly_do_bo_sung" in rj)
hj = open("sx/public/sx/views/qc_home.js", encoding="utf-8").read()
kiem("màn Hôm nay: nút + LƯỢT BỔ SUNG (chọn lý do), thẻ lượt bổ sung", "+ LƯỢT BỔ SUNG" in hj
     and "ly_do_bo_sung" in hj and "dl.bo_sung" in hj)

F.ket_thuc("BOSUNG")
