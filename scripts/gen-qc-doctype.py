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
    # Mục chuyển đổi (D129): Không có chuyển đổi / Đạt / Không đạt, trống = chưa kiểm.
    "chon_cd":  lambda m: {"fieldtype": "Select", "options": muc.CD_OPTIONS},
    "so":       lambda m: {"fieldtype": "Float", "precision": "1"},
    "nguyen":   lambda m: {"fieldtype": "Int", "default": "0"},
    "chu":      lambda m: {"fieldtype": "Data"},
    "co_khong": lambda m: {"fieldtype": "Check", "default": "0"},
    "gio":      lambda m: {"fieldtype": "Time"},
    # Nhiều vị một lượt, mỗi mã một dòng (D100). Small Text chứ không Data: tám
    # vị × 30 ký tự vượt 140 ký tự của Data.
    "chon_bot": lambda m: {"fieldtype": "Small Text"},
}

# Int mặc định 0 hợp lý cho ĐẾM (thùng quá hạn, trạm bẫy) nhưng SAI cho ĐO
# (nhiệt độ, phút): 0 °C là một phép đo, không phải "chưa đo".
# So theo mục GỐC: ô máy 2/3 của một ô đo cũng là ô đo.
KHONG_MAC_DINH_0 = {"rang_nhiet_do", "b2_rang_lac_nhiet", "b2_rang_lac_phut",
                    "b8_nhiet_han"}


def f(fieldname, fieldtype, label=None, **kw):
    d = {"fieldname": fieldname, "fieldtype": fieldtype}
    if label:
        d["label"] = label
    d.update(kw)
    return d


fields = [
    f("naming_series", "Select", "Số phiếu", options="QC-.YYYY.-.MM.-.####",
      default="QC-.YYYY.-.MM.-.####", reqd=1),
    f("ngay", "Date", "Ngày", reqd=1, in_list_view=1, search_index=1),   # D120
    f("luot", "Select", "Lượt", options="\n".join(muc.LUOT), reqd=1, in_list_view=1,
      description="Một ngày ba lượt: Đầu sáng · Trưa · Cuối chiều. Tuần = lượt "
                  "đầu sáng thứ Hai (gồm cả phần A và phần C), không phải lượt thứ tư. "
                  "Bổ sung = lượt riêng sau mất điện / sự cố máy, không tính vào ba lượt."),
    # Bỏ từ D95 (không còn chia ca). Giữ field để phiếu cũ còn nguyên giá trị —
    # xoá cột là mất dấu vết phiếu đó được ghi ở ca nào.
    f("ca", "Select", "Ca (phiếu cũ)", options="\n" + "\n".join(("Sáng", "Chiều")),
      hidden=1, read_only=1,
      description="Chỉ còn trên phiếu trước D95. Từ D95 một ngày ba lượt, không chia ca."),
    f("column_break_head", "Column Break"),
    f("co_san_xuat_bot", "Check", "Hôm nay có sản xuất bột", default="0"),
    # D100: hai cờ lạc do SERVER tính lúc validate từ ô B0 (loại bột) — không ai
    # gõ tay. Xem muc.co_lac_trong / muc.can_thu_lac.
    f("co_lac", "Check", "Có làm vị có lạc", default="0", read_only=1),
    f("can_thu_lac", "Check", "Phải thử nhanh lạc (B7)", default="0", read_only=1,
      description="Lượt này hoặc một lượt trước trong ngày làm vị có lạc."),
    # D129: sữa bột — cùng luật với lạc, cho ô B7c vệ sinh chuyển đổi.
    f("co_sua", "Check", "Có làm vị có sữa bột", default="0", read_only=1),
    f("can_ve_sinh_sua", "Check", "Phải vệ sinh chuyển đổi sữa (B7c)", default="0",
      read_only=1, description="Lượt này hoặc một lượt trước trong ngày làm vị có sữa bột."),
    # D129: bộ mục của bản giấy lúc MỞ phiếu (sx/qc/muc.py PHIEN_BAN). Trống = 1.
    f("phien_ban", "Int", "Phiên bản bộ mục", read_only=1,
      description="Bộ mục BM.08.01 lúc mở phiếu. Phiếu trước D129 để trống = bản 1."),
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
    # W23 (D147): nhập lại từ giấy — giờ kiểm THẬT trên bản giấy (bắt buộc khi hoàn tất) và
    # ảnh bản giấy (tuỳ chọn). Lượt Bổ sung — lý do.
    f("gio_thuc_te", "Time", "Giờ kiểm thực tế (theo bản giấy)",
      description="Nhập lại từ bản giấy: giờ ghi trên tờ giấy. Bắt buộc trước khi hoàn tất."),
    f("anh_giay", "Attach Image", "Ảnh bản giấy", description="Tuỳ chọn — chụp tờ giấy đã ghi."),
    f("ly_do_bo_sung", "Small Text", "Lý do lượt bổ sung",
      description="Lượt Bổ sung (sau mất điện / sự cố máy): bắt buộc."),
    f("so_muc_ap_dung", "Int", "Số mục phải chấm", read_only=1),
    f("so_muc_da_cham", "Int", "Đã chấm", read_only=1),

    # D100: số máy đang chạy của từng nhóm — quyết định ô máy 2/3 có áp dụng không.
    f("section_may", "Section Break", "Máy và công đoạn đang chạy"),
    # D107: công đoạn hôm nay KHÔNG chạy — mục của nó không áp dụng ở lượt này.
    # Mỗi dòng một mã bước (sx/qc/muc.py BUOC_TAT_DUOC); server lọc bỏ mã lạ.
    f("buoc_nghi", "Small Text", "Công đoạn không chạy",
      description="Mã bước, mỗi dòng một mã (2 Luộc, 3 Rang, 4 Sàng cát, 6 Vỡ đỗ, "
                  "7 Nghiền, 10 Ủ sau trộn, 12 Đóng gói). Ghi từ màn lượt kiểm."),
] + [x for i, (nhom, (ten, toi_da, truong)) in enumerate(muc.NHOM_MAY.items())
     for x in ([f(f"column_break_may_{i}", "Column Break")] if i else [])
     + [f(truong, "Int", f"Số {ten.lower()} đang chạy", default="1",
          description=f"1 – {toi_da}. Máy không chạy thì ô của nó không áp dụng.")]]

for ma, ten, oprp, ghi in muc.BUOC:
    nhan = f"{ma}. {ten}" if ma not in ("A", "B", "C") else f"{ma} — {ten}"
    if oprp:
        nhan += f"  ({oprp})"
    fields.append(f(f"section_buoc_{ma.lower()}", "Section Break", nhan,
                    collapsible=1))
    for m in [x for x in muc.MUC if x["buoc"] == ma]:
        extra = KIEU[m["kieu"]](m)
        if m["kieu"] == "nguyen" and m["goc"] in KHONG_MAC_DINH_0:
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
