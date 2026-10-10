"""D161 (W37) — rang đỗ 240–280 °C, bỏ aflatoxin từng lô với đỗ / lạc, công đoạn 9 "Nấu đường, trộn".

Vì sao phải có bài này:
  · Ngưỡng rang là oPRP-1 — sai một chỗ (mã, cài đặt mặc định, chữ gợi ý, số dự phòng trên màn QC) là
    QC thấy "thấp hơn 255" trong khi tài liệu nói 240: sự cố giả, hoặc tệ hơn, lò 245 °C bị coi là lỗi
    còn lò 235 °C ở site chưa lưu cài đặt lại đi qua.
  · Patch không được đè số site đã tự chỉnh (đó là quyết định của site) — chỉ đổi khi còn đúng 255 / 270.
  · Aflatoxin từng lô với đỗ, lạc đã bỏ (chuyển kiểm nghiệm năm): để nhóm đó trong luật là mọi lô đỗ tự
    vào Cách ly. Nhóm khác site đã khai thì giữ.

Nạp sx/qc/nguong.py, su_co.py, patch d161 THẬT trên frappe giả.
Chạy: python3 scripts/test-rangdo.py   (verify.sh gọi sẵn)
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

frappe = F.cai()
DOI_TEN, DOI_TEN_CO = [], {}


def _doi_ten(doctype, old, new, force=False, merge=False, *, ignore_if_exists=False, show_alert=True,
             rebuild_search=True):
    """Đúng chữ ký `frappe.rename_doc` công khai v15 / v16: tham số lạ (ignore_permissions) là TypeError
    như trên site — bản giả cũ nhận `**k` nên lỗi lọt qua, migrate dừng ở d161 (D175)."""
    DOI_TEN.append((doctype, old, new))
    DOI_TEN_CO.update(force=force, merge=merge, show_alert=show_alert, rebuild_search=rebuild_search)
    b = F.bang(doctype)
    b[new] = dict(b.pop(old), name=new, ten=new)


frappe.rename_doc = _doi_ten
frappe.db.delete = lambda dt, f=None: [F.bang(dt).pop(k) for k in [k for k, v in F.bang(dt).items() if F.khop(v, f)]]
frappe.clear_cache = lambda **k: None
Q = F.nap_qc()
NG = sys.modules["sx.qc.nguong"]
M = sys.modules["sx.qc.muc"]
P = F.nap("sx.patches.d161_rang_240_280", "sx/patches/d161_rang_240_280.py")
kiem = F.kiem

# ═══ 1. Ngưỡng mới ở mọi chỗ ═════════════════════════════════════════════
print("-- ngưỡng rang đỗ 240–280 °C --")
kiem("mã: mặc định 240 / 280", (NG.MAC_DINH["rang_nhiet_min"], NG.MAC_DINH["rang_nhiet_max_van_hanh"]) == (240, 280))
kiem("site chưa lưu cài đặt → đọc 240 / 280", (NG.nguong()["rang_nhiet_min"], NG.nguong()["rang_nhiet_max_van_hanh"]) == (240, 280))
st = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_qc_setting/sx_qc_setting.json", encoding="utf-8"))["fields"]}
kiem("SX QC Setting: mặc định ô = 240 / 280", (st["rang_nhiet_min"]["default"], st["rang_nhiet_max_van_hanh"]["default"])
     == ("240", "280"))
rd = {f["fieldname"]: f for f in json.load(open("sx/qc/doctype/sx_qc_round/sx_qc_round.json", encoding="utf-8"))["fields"]}
kiem("chữ gợi ý ô nhiệt độ rang (cả máy 2, 3) theo ngưỡng mới — đã chạy lại gen-qc-doctype.py",
     all(rd[f]["description"] == "≥ 240 · ngoài 240–280 cảnh báo vận hành"
         for f in ("rang_nhiet_do", "rang_nhiet_do_m2", "rang_nhiet_do_m3")))
ui = open("sx/public/sx/components/qcui.js", encoding="utf-8").read()
kiem("màn QC: số dự phòng khi server chưa gửi ngưỡng = 240 / 280 (không còn 255 / 270)",
     "?? 240" in ui and "?? 280" in ui and not re.search(r"\?\? 2(55|70)\b", ui))

# ═══ 2. Patch ════════════════════════════════════════════════════════════
print("\n-- patch D161: cài đặt site --")
F.CAI_DAT.update({"rang_nhiet_min": 255, "rang_nhiet_max_van_hanh": 270})
P.execute()
kiem("site còn đúng mặc định cũ 255 / 270 → 240 / 280",
     (F.CAI_DAT["rang_nhiet_min"], F.CAI_DAT["rang_nhiet_max_van_hanh"]) == (240, 280))
F.CAI_DAT.update({"rang_nhiet_min": 250, "rang_nhiet_max_van_hanh": 275})
P.execute()
kiem("site đã tự chỉnh số khác → giữ nguyên", (F.CAI_DAT["rang_nhiet_min"], F.CAI_DAT["rang_nhiet_max_van_hanh"]) == (250, 275))
F.CAI_DAT.update({"rang_nhiet_min": "255", "rang_nhiet_max_van_hanh": 290})
P.execute()
kiem("từng ô riêng: ô còn mặc định cũ thì đổi, ô đã chỉnh thì giữ (cả khi số lưu dạng chữ)",
     (F.CAI_DAT["rang_nhiet_min"], F.CAI_DAT["rang_nhiet_max_van_hanh"]) == (240, 290))
F.CAI_DAT.pop("rang_nhiet_min"), F.CAI_DAT.pop("rang_nhiet_max_van_hanh")
P.execute()
kiem("site chưa lưu cài đặt (trống) → không ghi gì, code đọc mặc định mới",
     "rang_nhiet_min" not in F.CAI_DAT and "rang_nhiet_max_van_hanh" not in F.CAI_DAT)

print("\n-- patch D161: nhóm hàng phải có aflatoxin --")
ST = "SX QC Setting"
F.bang("SX QC Nhom COA").update({
    "a1": {"name": "a1", "parent": ST, "parenttype": ST, "parentfield": "nhom_can_aflatoxin", "item_group": "Đỗ xanh"},
    "a2": {"name": "a2", "parent": ST, "parenttype": ST, "parentfield": "nhom_can_aflatoxin", "item_group": "LẠC NHÂN"},
    "a3": {"name": "a3", "parent": ST, "parenttype": ST, "parentfield": "nhom_can_aflatoxin", "item_group": "Đậu đen"},
    "a4": {"name": "a4", "parent": ST, "parenttype": ST, "parentfield": "nhom_can_aflatoxin", "item_group": "Dừa sấy"},
    "c1": {"name": "c1", "parent": ST, "parenttype": ST, "parentfield": "nhom_can_coa", "item_group": "Đỗ xanh"},
})
P.execute()
con = {k: v["item_group"] for k, v in F.bang("SX QC Nhom COA").items()}
kiem("bỏ nhóm đỗ / đậu / lạc khỏi luật aflatoxin từng lô (kể cả chữ hoa)", not {"a1", "a2", "a3"} & set(con), con)
kiem("… nhóm khác site đã khai (dừa sấy) giữ nguyên; danh sách COA không đụng tới",
     con == {"a4": "Dừa sấy", "c1": "Đỗ xanh"}, con)
P.execute()
kiem("chạy lại vô hại", len(F.bang("SX QC Nhom COA")) == 2)

print("\n-- patch D161: công đoạn 9 --")
CD = "SX QC Cong Doan"
F.bang(CD).update({"9 Trộn": {"name": "9 Trộn", "ten": "9 Trộn", "ma": "9"}})
loi = F.thu(P.execute)
kiem("gọi frappe.rename_doc đúng chữ ký v16 — không truyền ignore_permissions (migrate dừng ở d161, D175)",
     loi is None, loi)
kiem("bản tạo sẵn '9 Trộn' → Rename '9 Nấu đường, trộn' (tên QT.08 / KH.HACCP.01)",
     DOI_TEN == [(CD, "9 Trộn", "9 Nấu đường, trộn")] and "9 Nấu đường, trộn" in F.bang(CD))
kiem("… Rename force (không phụ thuộc cờ allow_rename), không gộp, không thông báo, không đẩy việc dựng "
     "lại tìm kiếm vào hàng đợi giữa lúc migrate",
     DOI_TEN_CO == {"force": True, "merge": False, "show_alert": False, "rebuild_search": False}, DOI_TEN_CO)
P.execute()
kiem("chạy lại vô hại (không đổi tên lần hai)", len(DOI_TEN) == 1)
F.bang(CD).clear()
F.bang(CD).update({"9 Trộn": {"name": "9 Trộn", "ma": "9"}, "9 Nấu đường, trộn": {"name": "9 Nấu đường, trộn"}})
P.execute()
kiem("đã có công đoạn tên mới → không đổi (không trùng tên)", len(DOI_TEN) == 1)
F.bang(CD).clear()
F.bang(CD).update({"9 Pha trộn": {"name": "9 Pha trộn", "ma": "9"}})
P.execute()
kiem("Ban ISO đã tự đặt tên khác → giữ", len(DOI_TEN) == 1 and "9 Pha trộn" in F.bang(CD))
kiem("sự cố mới sinh theo mã công đoạn → mang tên hiện tại", sys.modules["sx.qc.su_co"].ten_cong_doan("9 Trộn") == "9 Pha trộn")
kiem("patch có trong patches.txt", "sx.patches.d161_rang_240_280" in open("sx/patches.txt", encoding="utf-8").read())

F.ket_thuc("RANGDO")
