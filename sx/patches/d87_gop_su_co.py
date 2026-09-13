"""D87: chuyển sự cố của tổ Ghi sổ từ bảng con SX Su Co Item sang sổ chung SX Su Co.

Trước D87 có HAI chỗ ghi sự cố: bảng con trên phiếu ngày (tổ Ghi sổ) và — từ
D85 — DocType SX Su Co (QC). Hai sổ nghĩa là hai chỗ phải nhớ đi xem, và cái
không ai nhớ thì không ai đóng.

Patch này CHÉP sang, KHÔNG xoá bảng con: dữ liệu gốc còn nguyên để đối chiếu
nếu chuyển sai. Bảng con chỉ ngừng được ghi thêm (sx/api/portal.py).

Chạy lại bao nhiêu lần cũng không nhân đôi: mỗi dòng mang khoá `<phiếu>#<idx>`
và patch bỏ qua khoá đã có. Việc này quan trọng hơn nó có vẻ — `bench migrate`
chạy lại sau một lần lỗi giữa chừng là chuyện bình thường, mà sổ sự cố nhân đôi
thì không ai phát hiện ra bằng mắt.
"""

import frappe
from frappe.utils import cint


def execute():
    if not (frappe.db.table_exists("SX Su Co Item")
            and frappe.db.table_exists("SX Su Co")):
        return

    da_co = set(frappe.get_all("SX Su Co", filters={"khoa_cu": ("is", "set")},
                               pluck="khoa_cu"))
    dong = frappe.get_all(
        "SX Su Co Item",
        filters={"parenttype": "SX Ngay San Xuat"},
        fields=["parent", "idx", "thoi_diem", "loai", "mo_ta", "phut_dung"],
        order_by="parent, idx",
    )
    if not dong:
        return

    ngay_cua = {}
    for p in {r["parent"] for r in dong}:
        ngay_cua[p] = frappe.db.get_value("SX Ngay San Xuat", p, "ngay")

    da_chuyen = 0
    for r in dong:
        khoa = f'{r["parent"]}#{r["idx"]}'
        if khoa in da_co:
            continue
        ngay = ngay_cua.get(r["parent"])
        if not ngay:
            # Phiếu ngày đã bị xoá: không có ngày thì phiếu sự cố vô nghĩa.
            # Bỏ qua và NÓI RA, đừng lấy hôm nay làm ngày — sai ngày trong hồ sơ
            # chất lượng còn tệ hơn thiếu bản ghi.
            print(f"D87: bỏ qua {khoa} — không còn phiếu ngày {r['parent']}")
            continue
        doc = frappe.get_doc({
            "doctype": "SX Su Co",
            "ngay": ngay,
            "nguon": "Nhật ký chuyền",
            "loai_chuyen": r["loai"],
            "loai": "Khác",
            "phut_dung": cint(r["phut_dung"]),
            "mo_ta": r["mo_ta"] or r["loai"] or "(không ghi mô tả)",
            "ngay_san_xuat": r["parent"],
            "khoa_cu": khoa,
            # Sự cố cũ đã qua rồi, đóng luôn: để Mở hết thì sổ sự cố mới mở ra
            # đã có hàng trăm phiếu quá hạn và không ai đọc nó nữa.
            "trang_thai": "Đóng",
            "xu_ly_ngay": "(chuyển từ nhật ký chuyền cũ, không ghi xử lý)",
            "quyet_dinh_sp": "Không ảnh hưởng sản phẩm",
        })
        doc.insert(ignore_permissions=True)
        da_chuyen += 1

    frappe.db.commit()
    print(f"D87: chuyển {da_chuyen}/{len(dong)} dòng sự cố sang SX Su Co")
