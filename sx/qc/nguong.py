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
    "luu_mau_so_ngay": 180,
    # W03 (D128): ngưỡng phần bột đã chốt theo tài liệu 08/10/2026 — trước đó là
    # "chờ thẩm định" (chưa đặt thì chỉ ghi số). Rang lạc 150–180 °C, 30–40 phút;
    # hàn túi 150–190 °C. Sửa được trong SX QC Setting; để trống = số ở đây.
    "rang_lac_nhiet_min": 150,
    "rang_lac_nhiet_max": 180,
    "rang_lac_phut_min": 30,
    "rang_lac_phut_max": 40,
    "han_nhiet_min": 150,
    "han_nhiet_max": 190,
}

# Ngưỡng chờ thẩm định: không có mặc định, chưa đặt thì không sinh sự cố.
# (Từ D128 rang lạc và nhiệt độ hàn đã có số — xem MAC_DINH.)
CHO_THAM_DINH = (
    # Rây kiểm RY-01 (W02, D129): số hạt thô tối đa trên rây — chưa ai đưa con số.
    # Chưa đặt thì chỉ ghi số + cảnh báo khi có hạt thô, không tự sinh sự cố.
    "hat_tho_toi_da",
)

# Vị bột có lạc (D100) khi SX QC Setting chưa khai gì. Đây là vị duy nhất đang
# có lạc trong công thức (BOM chè đậu đen cốt dừa có Lạc).
BOT_CO_LAC_MAC_DINH = ("Chè đậu đen cốt dừa",)

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
        # Ô chữ (Data) chứ không Int: Int không để trống được, mà 0 hạt thô là một
        # ngưỡng THẬT ("không cho hạt nào") — khác hẳn "chưa đặt".
        try:
            ra[k] = int(float(str(v).strip())) if str(v if v is not None else "").strip() else None
        except ValueError:
            ra[k] = None
    # Danh sách nhóm hàng bắt buộc có COA: RỖNG nghĩa là chưa khai, và chưa khai
    # thì luật COA KHÔNG chạy. Không đoán bừa vài tên nhóm: đoán sai thì hoặc
    # chặn nhầm hàng tốt, hoặc cho qua đúng thứ cần chặn.
    ra["nhom_can_coa"] = [r.item_group for r in (s.get("nhom_can_coa") or [])] if s else []
    # Mỗi dòng một mã / tên hàng. Rỗng = mặc định ở trên — không để rỗng thành
    # "không vị nào có lạc": thế là B1/B2/B7 lặng lẽ biến khỏi mọi lượt.
    khai = [x.strip() for x in str((s.get("bot_co_lac") if s else "") or "").split("\n")
            if x.strip()]
    ra["bot_co_lac"] = khai or list(BOT_CO_LAC_MAC_DINH)
    # Vị bột có sữa bột (D129): KHÔNG có mặc định — nguồn chính là cờ "Có sữa bột"
    # của sản phẩm tự công bố (W28); danh sách này chỉ để bổ sung.
    ra["bot_co_sua"] = [x.strip() for x in str((s.get("bot_co_sua") if s else "") or "")
                        .split("\n") if x.strip()]
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
