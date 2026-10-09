"""D161 (W37): rang đỗ 240–280 °C; bỏ aflatoxin từng lô với đỗ, lạc (quyết định 09/10/2026).

· SX QC Setting còn đúng mặc định cũ (255 / 270) thì đổi sang 240 / 280. Site đã tự chỉnh số khác thì
  giữ — đó là quyết định của site. Chưa lưu bao giờ (trống) thì code đọc mặc định mới, không cần ghi.
· "Nhóm hàng phải có kết quả aflatoxin khi tiếp nhận": bỏ các nhóm đỗ / đậu / lạc — không kiểm aflatoxin
  từng lô nữa, chuyển vào kiểm nghiệm năm (KH.KN.01). Code chưa từng có mặc định cho ô này (site khai theo
  ví dụ "lạc, đỗ" của W10), nên chỉ bỏ đúng các nhóm đó; nhóm khác site đã khai thì để nguyên.
· Công đoạn 9 mang tên đúng QT.08 / KH.HACCP.01: "9 Nấu đường, trộn" (bản tạo sẵn D130 là "9 Trộn"). Đổi
  bằng Rename như Ban ISO làm trên Desk (phiếu sự cố cũ trỏ theo). Site đã tự đặt tên khác thì giữ.
Chạy lại vô hại.
"""

import frappe
from frappe.utils import cint

ST = "SX QC Setting"
DOI = {"rang_nhiet_min": (255, 240), "rang_nhiet_max_van_hanh": (270, 280)}
DO_LAC = ("đỗ", "đậu", "lạc")
CD = "SX QC Cong Doan"
CD_CU, CD_MOI = "9 Trộn", "9 Nấu đường, trộn"


def la_do_lac(nhom):
    t = str(nhom or "").lower()
    return any(k in t for k in DO_LAC)


def execute():
    for f, (cu, moi) in DOI.items():
        v = frappe.db.get_single_value(ST, f)
        if cint(v) == cu:
            frappe.db.set_single_value(ST, f, moi)
    if frappe.db.table_exists(CD) and frappe.db.exists(CD, CD_CU) and not frappe.db.exists(CD, CD_MOI):
        frappe.rename_doc(CD, CD_CU, CD_MOI, force=True, ignore_permissions=True)
    try:
        ds = frappe.get_all("SX QC Nhom COA", filters={"parenttype": ST, "parent": ST,
                                                       "parentfield": "nhom_can_aflatoxin"},
                            fields=["name", "item_group"])
    except Exception:          # site chưa có ô này (trước W10)
        return
    bo = [x.name for x in ds if la_do_lac(x.item_group)]
    for n in bo:
        frappe.db.delete("SX QC Nhom COA", {"name": n})
    if bo:
        frappe.clear_cache(doctype=ST)
