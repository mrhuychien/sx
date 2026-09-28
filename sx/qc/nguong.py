"""Đọc ngưỡng và khung giờ từ SX QC Setting — một chỗ, có mặc định an toàn.

Vì sao không `frappe.get_single` rải khắp nơi: site mới cài chưa có bản ghi
Single, đọc ra toàn 0. Mà 0 ở đây không vô hại — `rang_nhiet_min = 0` nghĩa là
không lượt nào sinh sự cố nhiệt độ nữa, im lặng, cho tới lúc auditor hỏi.
Nên mọi ngưỡng đều có mặc định trong code và số 0 bị coi là "chưa đặt".

Ngưỡng CHƯA THẨM ĐỊNH (rang lạc) thì để None, và khi None thì chỉ ghi số,
không tự sinh sự cố: bịa ngưỡng ra để "có cho đủ" còn tệ hơn không có.
"""

import frappe

MAC_DINH = {
    "rang_nhiet_min": 255,
    "rang_nhiet_max_van_hanh": 270,
    "vong_quay_min": 6.2,
    "vong_quay_max": 7.0,
    "thung_bot_max": 0,
    "ghi_muon_phut": 45,
    "su_co_qua_han_ngay": 7,
    "do_am_toi_da": 13.0,
}

# Ngưỡng chờ thẩm định: không có mặc định, chưa đặt thì không sinh sự cố.
CHO_THAM_DINH = ("rang_lac_nhiet_min", "rang_lac_phut_min")

# Hạn chót của từng lượt trong ngày (D95). Khung của một lượt = từ hạn chót của
# lượt TRƯỚC tới hạn chót của chính nó — nên chỉ cần khai ba mốc, và không thể
# khai ra hai khung chồng lên nhau hay hở một khoảng ở giữa.
#
#   Đầu sáng    … → 08:30
#   Trưa    08:30 → 14:00      làm Trưa lúc 07:00 cũng bị gắn cờ: đó không phải
#   Cuối chiều 14:00 → 20:00   lượt trưa, chỉ là ghi sớm cho xong
#
# (fieldname trong SX QC Setting, mặc định)
HAN_CHOT = (
    ("Đầu sáng", "han_dau_sang", "08:30:00"),
    ("Trưa", "han_trua", "14:00:00"),
    ("Cuối chiều", "han_cuoi_chieu", "20:00:00"),
)


def _single():
    try:
        return frappe.get_cached_doc("SX QC Setting")
    except Exception:
        # Chưa migrate / chưa có DocType -> chạy bằng mặc định, đừng làm chết màn hình
        return None


def nguong():
    s = _single()

    def lay(ten, md):
        v = s.get(ten) if s else None
        # thung_bot_max = 0 là ngưỡng THẬT (không cho phép thùng nào quá hạn),
        # nên nó không được rơi vào luật "0 = chưa đặt" như các ngưỡng khác.
        if ten == "thung_bot_max":
            return int(v or 0)
        return type(md)(v) if v else md

    ra = {k: lay(k, v) for k, v in MAC_DINH.items()}
    for k in CHO_THAM_DINH:
        v = s.get(k) if s else None
        ra[k] = int(v) if v else None
    # Danh sách nhóm hàng bắt buộc có COA: RỖNG nghĩa là chưa khai, và chưa khai
    # thì luật COA KHÔNG chạy. Không đoán bừa vài tên nhóm: đoán sai thì hoặc
    # chặn nhầm hàng tốt, hoặc cho qua đúng thứ cần chặn.
    ra["nhom_can_coa"] = [r.item_group for r in (s.get("nhom_can_coa") or [])] if s else []
    ra["cho_phep_bo_qua_luot_khi_khong_san_xuat"] = int(
        (s.get("cho_phep_bo_qua_luot_khi_khong_san_xuat") if s else 1) or 0)

    # {lượt: (từ, đến)} — xem HAN_CHOT. Lượt Tuần dùng khung của Đầu sáng.
    khung, truoc = {}, None
    for luot, truong, mac in HAN_CHOT:
        den = str((s.get(truong) if s else None) or mac)
        khung[luot] = (truoc, den)
        truoc = den
    ra["khung"] = khung
    return ra
