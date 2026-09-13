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
}

# Ngưỡng chờ thẩm định: không có mặc định, chưa đặt thì không sinh sự cố.
CHO_THAM_DINH = ("rang_lac_nhiet_min", "rang_lac_phut_min")

KHUNG_MAC_DINH = {
    "Sáng": {"Đầu ca": (None, "09:30:00"),
             "Giữa ca": ("09:30:00", "12:00:00"),
             "Cuối ca": (None, "13:00:00")},
    "Chiều": {"Đầu ca": (None, "15:30:00"),
              "Giữa ca": ("15:30:00", "18:00:00"),
              "Cuối ca": (None, "19:00:00")},
}


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
    ra["cho_phep_bo_qua_luot_khi_khong_san_xuat"] = int(
        (s.get("cho_phep_bo_qua_luot_khi_khong_san_xuat") if s else 1) or 0)

    khung = {}
    for ca, mac in KHUNG_MAC_DINH.items():
        tien_to = "sang" if ca == "Sáng" else "chieu"
        khung[ca] = {
            "Đầu ca": (None, (s.get(f"{tien_to}_dau_den") if s else None)
                       or mac["Đầu ca"][1]),
            "Giữa ca": ((s.get(f"{tien_to}_giua_tu") if s else None)
                        or mac["Giữa ca"][0],
                        (s.get(f"{tien_to}_giua_den") if s else None)
                        or mac["Giữa ca"][1]),
            "Cuối ca": (None, (s.get(f"{tien_to}_cuoi_den") if s else None)
                        or mac["Cuối ca"][1]),
        }
    ra["khung"] = khung
    return ra
