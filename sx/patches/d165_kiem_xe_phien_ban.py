"""D165 (W34): chuyến đã ghi kiểm xe trước D165 giữ bộ bốn mục cũ (bản dự thảo QT.09) — đánh dấu phiên bản 1.

Patch chạy TRƯỚC khi migrate đồng bộ fixtures (custom field), nên tạo trước ô custom_xe_phien_ban từ đúng bản
khai trong sx/fixtures/custom_field.json (lần đồng bộ ngay sau ghi lại y hệt). Chứng từ chưa ghi gì về xe để 0 —
lần lưu sau sx/qc/kiem_xe.validate ghi phiên bản hiện hành (năm mục). Chạy lại vô hại.
"""

import json

import frappe

from sx.qc import kiem_xe as KX

# Có một trong các ô này = chuyến đã ghi kiểm xe theo bộ cũ.
CU = [f for f, _c, _y in KX.MUC_THEO_PB[1]] + ["custom_xe_ket_luan", "custom_xe_bien_so", "custom_xe_tai_xe",
                                                "custom_xe_ghi_chu"]


def _dam_bao_o():
    with open(frappe.get_app_path("sx", "fixtures", "custom_field.json"), encoding="utf-8") as f:
        ds = json.load(f)
    for x in ds:
        if x["fieldname"] == "custom_xe_phien_ban" and not frappe.db.exists("Custom Field", x["name"]):
            frappe.get_doc(dict(x)).insert(ignore_permissions=True)


def execute():
    _dam_bao_o()
    for dt in KX.LOAI:
        if not frappe.db.has_column(dt, "custom_xe_phien_ban"):
            continue
        co = [f for f in CU if frappe.db.has_column(dt, f)]
        if not co:
            continue
        for x in frappe.get_all(dt, filters={"custom_xe_phien_ban": 0}, fields=["name"] + co):
            if any(x.get(f) for f in co):
                frappe.db.set_value(dt, x.name, "custom_xe_phien_ban", 1, update_modified=False)
