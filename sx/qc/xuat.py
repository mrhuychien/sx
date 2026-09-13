"""Dựng CSV tháng cho Ban ISO — hàm THUẦN, không đọc DB.

Tách ra khỏi sx/api/qc.py để test gọi thẳng: chỗ dễ sai nhất của một file xuất
không phải là truy vấn mà là Ý NGHĨA CỦA Ô TRỐNG. Ở đây có ba thứ khác nhau mà
trông giống hệt nhau nếu để cùng một ô trống:

  "n/a"  mục không áp dụng ở lượt đó (lượt giữa ca không có phần PRP đầu ca)
  ""     áp dụng mà chưa kiểm  ← đây mới là thứ Ban ISO cần đếm
  "—"    số chưa đo

Gộp chúng lại là người phân tích đếm nhầm tỷ lệ bỏ sót, theo hướng đẹp hơn sự
thật. Cả file này tồn tại để giữ ba thứ đó tách nhau.
"""

import csv
import io

from sx.qc import muc as M

BOM = "﻿"

COT_LUOT = ["Số phiếu", "Ngày", "Ca", "Lượt", "Có bột", "Giờ hoàn tất",
            "Số phút", "Ghi muộn", "Nhập lại từ giấy", "QC chế biến",
            "QC đóng gói", "Đã chấm", "Phải chấm", "Xem xét lúc", "Ghi chú"]

COT_SU_CO = ["Số phiếu", "Ngày", "Ca", "Nguồn", "Vòng kiểm", "Mục", "Công đoạn",
             "Loại", "Mức độ", "Mô tả", "Lô ảnh hưởng", "Xử lý ngay",
             "Nguyên nhân", "Hành động khắc phục", "Quyết định SP", "Số CAR",
             "Trạng thái", "Đóng bởi", "Đóng lúc"]

KHOA_SU_CO = ["name", "ngay", "ca", "nguon", "qc_round", "muc", "cong_doan",
              "loai", "muc_do", "mo_ta", "lo_anh_huong", "xu_ly_ngay",
              "nguyen_nhan", "hanh_dong_khac_phuc", "quyet_dinh_sp", "car_so",
              "trang_thai", "dong_boi", "dong_ngay"]


def tieu_de_luot():
    return COT_LUOT + [f'{m["so"]} {m["nhan"]}' for m in M.MUC]


def dong_luot(doc, in_gia_tri, cint):
    """Một dòng CSV cho một lượt. `doc` là bản ghi SX QC Round."""
    ap = {m["f"] for m in M.muc_ap_dung(doc.get("luot"),
                                        cint(doc.get("co_san_xuat_bot")))}
    return ([doc.get("name"), doc.get("ngay"), doc.get("ca"), doc.get("luot"),
             cint(doc.get("co_san_xuat_bot")), doc.get("finished_at"),
             cint(doc.get("duration_min")), cint(doc.get("ghi_muon")),
             cint(doc.get("nhap_lai_tu_giay")), doc.get("qc_user"),
             doc.get("qc_goi_user"), cint(doc.get("so_muc_da_cham")),
             cint(doc.get("so_muc_ap_dung")), doc.get("reviewed_on"),
             doc.get("ghi_chu")]
            + [("n/a" if m["f"] not in ap else in_gia_tri(m, doc.get(m["f"])))
               for m in M.MUC])


def dong_su_co(hang):
    return [hang.get(k) for k in KHOA_SU_CO]


def thanh_csv(tieu_de, hang):
    """Chuỗi CSV kèm BOM UTF-8.

    BOM không phải trang trí: thiếu nó thì Excel trên Windows mở ra là
    "Nhiá»‡t Ä'á»™" — file vẫn đúng, chỉ là người nhận tưởng phần mềm hỏng
    rồi gõ tay lại cả tháng.
    """
    buf = io.StringIO()
    ghi = csv.writer(buf, lineterminator="\n")
    ghi.writerow(tieu_de)
    for h in hang:
        ghi.writerow(["" if x is None else x for x in h])
    return BOM + buf.getvalue()
