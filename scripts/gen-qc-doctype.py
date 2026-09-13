"""Sinh sx_qc_round.json từ sx/qc/muc.py — chạy lại mỗi khi đổi danh mục mục kiểm.

Chạy: python3 scripts/gen-qc-doctype.py   (ghi đè file JSON, rồi git diff mà xem)

Vì sao sinh chứ không gõ tay: 40 mục × (fieldname, label, kiểu, options) gõ hai
lần ở hai file là hai lần cơ hội lệch. scripts/test-qc.py chốt JSON khớp muc.py,
nên quên chạy lại file này thì verify.sh kêu ngay.
"""
import json
import os
import sys

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ".")
from sx.qc import muc  # noqa: E402

KIEU = {
    "chon":     lambda m: {"fieldtype": "Select", "options": muc.TRI_STATE},
    "chon3":    lambda m: {"fieldtype": "Select", "options": muc.B7_OPTIONS},
    "so":       lambda m: {"fieldtype": "Float", "precision": "1"},
    "nguyen":   lambda m: {"fieldtype": "Int", "default": "0"},
    "chu":      lambda m: {"fieldtype": "Data"},
    "co_khong": lambda m: {"fieldtype": "Check", "default": "0"},
    "gio":      lambda m: {"fieldtype": "Time"},
}

# Int mặc định 0 hợp lý cho ĐẾM (thùng quá hạn, trạm bẫy) nhưng SAI cho ĐO
# (nhiệt độ, phút): 0 °C là một phép đo, không phải "chưa đo".
KHONG_MAC_DINH_0 = {"rang_nhiet_do", "b2_rang_lac_nhiet", "b2_rang_lac_phut"}


def f(fieldname, fieldtype, label=None, **kw):
    d = {"fieldname": fieldname, "fieldtype": fieldtype}
    if label:
        d["label"] = label
    d.update(kw)
    return d


fields = [
    f("naming_series", "Select", "Số phiếu", options="QC-.YYYY.-.MM.-.####",
      default="QC-.YYYY.-.MM.-.####", reqd=1),
    f("ngay", "Date", "Ngày", reqd=1, in_list_view=1),
    f("ca", "Select", "Ca", options="\n".join(muc.CA), reqd=1, in_list_view=1,
      description="Chưa có DocType ca sản xuất trong app — xem sx/qc/README.md."),
    f("luot", "Select", "Lượt", options="\n".join(muc.LUOT), reqd=1, in_list_view=1,
      description="Tuần = lượt đầu ca thứ Hai (gồm cả phần A và phần C), "
                  "không phải một lượt thứ tư."),
    f("column_break_head", "Column Break"),
    f("co_san_xuat_bot", "Check", "Hôm nay có sản xuất bột", default="0"),
    f("qc_user", "Link", "QC chế biến", options="User", reqd=1),
    f("qc_goi_user", "Link", "QC đóng gói", options="User"),
    f("ngay_san_xuat", "Link", "Phiếu ngày sản xuất", options="SX Ngay San Xuat",
      description="Tuỳ chọn, chỉ để nối hồ sơ. Module qc không đọc gì từ phiếu này."),

    f("section_thoi_gian", "Section Break", "Thời gian"),
    f("started_at", "Datetime", "Bắt đầu", read_only=1),
    f("finished_at", "Datetime", "Hoàn tất", read_only=1),
    f("duration_min", "Int", "Số phút", read_only=1),
    f("column_break_tg", "Column Break"),
    f("ghi_muon", "Check", "Ghi muộn", read_only=1, in_list_view=1,
      description="Chỉ hiển thị, không chặn. Ghi muộn vẫn là hồ sơ thật."),
    f("nhap_lai_tu_giay", "Check", "Nhập lại từ bản giấy", default="0"),
    f("so_muc_ap_dung", "Int", "Số mục phải chấm", read_only=1),
    f("so_muc_da_cham", "Int", "Đã chấm", read_only=1),
]

for ma, ten, oprp, ghi in muc.BUOC:
    nhan = f"{ma}. {ten}" if ma not in ("A", "B", "C") else f"{ma} — {ten}"
    if oprp:
        nhan += f"  ({oprp})"
    fields.append(f(f"section_buoc_{ma.lower()}", "Section Break", nhan,
                    collapsible=1))
    for m in [x for x in muc.MUC if x["buoc"] == ma]:
        extra = KIEU[m["kieu"]](m)
        if m["kieu"] == "nguyen" and m["f"] in KHONG_MAC_DINH_0:
            extra.pop("default", None)
        mo_ta = " · ".join(x for x in (m["goi_y"],
                                       "QC đóng gói ghi" if m["goi"] else "") if x)
        fields.append(f(m["f"], extra.pop("fieldtype"),
                        f'{m["so"]} {m["nhan"]}',
                        **({"description": mo_ta} if mo_ta else {}), **extra))

fields += [
    f("section_ghi_chu", "Section Break", "Ghi chú"),
    f("ghi_chu", "Small Text", "Ghi chú",
      description="Lý do mục để trống, rework, chuyển đổi. Bắt buộc khi có mục "
                  "áp dụng bỏ trống, hoặc khi nhập lại từ bản giấy."),
    f("section_xem_xet", "Section Break", "Ban ISO xem xét"),
    f("reviewed_by", "Link", "Người xem xét", options="User", read_only=1),
    f("reviewed_on", "Datetime", "Xem xét lúc", read_only=1),
    f("section_su_co", "Section Break", "Sự cố phát sinh"),
    f("su_co", "Table", "Sự cố", options="SX QC Round Incident", read_only=1),
    f("section_log", "Section Break", "Nhật ký ghi tại chỗ", collapsible=1),
    f("log", "Table", "Nhật ký", options="SX QC Round Log", read_only=1,
      description="Mỗi lần gõ một giá trị là một dòng, kèm giờ trên máy QC. "
                  "Đây là bằng chứng 'ghi tại chỗ' cho auditor."),
    f("amended_from", "Link", "Sửa từ", options="SX QC Round", read_only=1,
      no_copy=1, print_hide=1),
]

doc = {
    "actions": [],
    "autoname": "naming_series:",
    "creation": "2026-09-13 08:00:00.000000",
    "doctype": "DocType",
    "engine": "InnoDB",
    "field_order": [x["fieldname"] for x in fields],
    "fields": fields,
    "is_submittable": 1,
    "links": [],
    "modified": "2026-09-13 08:00:00.000000",
    "modified_by": "Administrator",
    "module": "QC",
    "name": "SX QC Round",
    "owner": "Administrator",
    # Quyền DocType (nền). Quyền THẬT của từng thao tác chốt trong sx/api/qc.py —
    # ở đây chỉ mở đủ để ORM không chặn đúng người. Chú ý SX QC Packing KHÔNG có
    # submit: QC đóng gói ghi mục của mình trên bản nháp người khác, nhưng người
    # chốt lượt phải là người đã đi hết lượt đó.
    "permissions": [
        {"role": "System Manager", "read": 1, "write": 1, "create": 1,
         "delete": 1, "submit": 1, "cancel": 1, "amend": 1,
         "report": 1, "export": 1},
        {"role": "SX QC", "read": 1, "write": 1, "create": 1, "submit": 1,
         "report": 1, "export": 1},
        {"role": "SX QC Packing", "read": 1, "write": 1, "report": 1, "export": 1},
        {"role": "Production Manager", "read": 1, "report": 1, "export": 1},
        {"role": "ISO Manager", "read": 1, "cancel": 1, "report": 1, "export": 1},
        {"role": "SX Quan Ly", "read": 1, "report": 1, "export": 1},
    ],
    "sort_field": "modified",
    "sort_order": "DESC",
    "track_changes": 1,
}

ra = "sx/qc/doctype/sx_qc_round/sx_qc_round.json"
with open(ra, "w", encoding="utf-8") as fh:
    json.dump(doc, fh, ensure_ascii=False, indent=1)
    fh.write("\n")
print(f"{ra}: {len(fields)} field ({len(muc.MUC)} mục kiểm)")
