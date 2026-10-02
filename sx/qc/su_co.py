"""Sinh phiếu sự cố (BM.08.02) từ một vòng kiểm — luật "lệch → sự cố".

Đây là chỗ duy nhất quyết định cái gì thành sự cố. Gom một chỗ vì hai lý do:

  • Sót một luật thì hỏng ÂM THẦM. Lượt vẫn hoàn tất, màn hình vẫn xanh, chỉ là
    chỗ không đạt kia không thành phiếu và không ai đi xử lý. Test đối chiếu
    thẳng với danh sách luật trong file này (scripts/test-qc.py).
  • Mức độ "Cao" phải hiếm thì mới có nghĩa. Ba thứ được coi là Cao: dị ứng
    (dương tính chuyển đổi), nhiệt rang dưới ngưỡng, mạt kim loại. Thêm nữa là
    pha loãng, rồi Cao thành bình thường.

`ignore_permissions=True` chỉ dùng ở đây, và có lý do: QC không có quyền tạo
phiếu sự cố tay cho người khác, nhưng hệ thống PHẢI tạo được khi phát hiện lệch —
nếu quyền chặn được việc này thì "bỏ qua sự cố" chỉ còn là chuyện bấm sai role.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from sx.qc import muc as M
from sx.qc.nguong import nguong

CAO = "Cao"
THUONG = "Thường"


def _loai(m):
    """oPRP / PRP / Khác theo bước của mục."""
    if m["cd"] == "PRP":
        return "PRP"
    for ma, _ten, oprp, _ghi in M.BUOC:
        if ma == m["buoc"]:
            return "oPRP" if oprp else "Khác"
    return "Khác"


def phat_hien(doc):
    """[(muc_key, cong_doan, loai, muc_do, mo_ta)] — mọi chỗ lệch của một lượt.

    Hàm THUẦN: không đọc DB ngoài ngưỡng, không ghi gì. Test gọi thẳng nó.
    """
    ng = nguong()
    luot = doc.get("luot")
    ra = []

    for m in M.muc_ap_dung(luot, doc):
        v = doc.get(m["f"])
        goc = m["goc"]            # ô máy 2/3 theo đúng luật của ô gốc (D100)
        may = M.ten_may(m) if M.boi_canh(doc)["may"].get(m.get("may"), 1) > 1 else ""

        if m["kieu"] == "chon" and v == M.KHONG_DAT:
            ra.append((m["f"], m["cd"], _loai(m), THUONG,
                       _("Mục {0} {1}: Không đạt").format(
                           m["so"], m["nhan"] + (may if m["may_so"] == 1 else ""))))

        elif goc == "b7_chuyen_doi" and v == M.B7_DUONG:
            # Dị ứng là thứ đưa người vào viện, không phải thứ ghi nhận rồi thôi.
            ra.append((m["f"], m["cd"], "Dị ứng", CAO,
                       _("B7 Chuyển đổi: thử nhanh lạc DƯƠNG TÍNH — dừng dây "
                         "chuyền, cô lập lô, vệ sinh lại trước khi chạy tiếp")))

        elif goc == "nam_cham_mat_kim_loai" and cint(v):
            ra.append((m["f"], m["cd"], "oPRP", CAO,
                       _("Nam châm bắt được mạt kim loại{0}").format(
                           _(" (vật: {0})").format(doc.get("nam_cham_vat"))
                           if doc.get("nam_cham_vat") else "")))

        elif goc == "rang_nhiet_do" and M.co_ghi(m, v):
            if flt(v) < ng["rang_nhiet_min"]:
                ra.append((m["f"], m["cd"], "oPRP", CAO,
                           _("Rang{0}: nhiệt độ {1} °C < {2} °C").format(
                               may, int(flt(v)), ng["rang_nhiet_min"])))

        elif goc == "rang_vong_quay" and M.co_ghi(m, v):
            if not (ng["vong_quay_min"] <= flt(v) <= ng["vong_quay_max"]):
                ra.append((m["f"], m["cd"], "oPRP", THUONG,
                           _("Rang{0}: vòng quay {1} ngoài khoảng {2}–{3}").format(
                               may, flt(v, 1), ng["vong_quay_min"], ng["vong_quay_max"])))

        elif goc == "b8_nhiet_han" and M.co_ghi(m, v):
            # Khoảng chờ thẩm định như rang lạc: chưa đặt đầu nào thì đầu đó không
            # sinh sự cố. Hàn nguội → hở túi; hàn nóng → cháy màng, cũng hở.
            lo, hi = ng["han_nhiet_min"], ng["han_nhiet_max"]
            if (lo is not None and flt(v) < lo) or (hi is not None and flt(v) > hi):
                ra.append((m["f"], m["cd"], "Khác", THUONG,
                           _("Máy đóng gói bột{0}: nhiệt độ hàn {1} °C ngoài khoảng "
                             "{2}–{3}").format(may, int(flt(v)),
                                               "…" if lo is None else lo,
                                               "…" if hi is None else hi)))

        elif goc == "thung_bot_qua_han":
            if cint(v) > ng["thung_bot_max"]:
                ra.append((m["f"], m["cd"], "oPRP", THUONG,
                           _("Kho bột: {0} thùng quá 2 ngày / hở nắp").format(cint(v))))

        elif goc in ("b2_rang_lac_nhiet", "b2_rang_lac_phut") and M.co_ghi(m, v):
            # Ngưỡng chờ thẩm định: chưa đặt thì CHỈ GHI SỐ. Bịa ngưỡng ra để
            # "có cho đủ" là sinh báo động giả suốt ngày rồi không ai đọc nữa.
            key = ("rang_lac_nhiet_min" if m["f"].endswith("nhiet")
                   else "rang_lac_phut_min")
            if ng[key] is not None and flt(v) < ng[key]:
                ra.append((m["f"], m["cd"], "oPRP", THUONG,
                           _("Rang lạc: {0} dưới ngưỡng {1}").format(
                               flt(v, 1), ng[key])))
    return ra


def canh_bao(doc):
    """Chỗ đáng để mắt nhưng KHÔNG thành sự cố — trả cho màn hình hiển thị.

    Tách hẳn khỏi phat_hien(): trộn cảnh báo vào sự cố là cách nhanh nhất để
    sổ sự cố đầy thứ không phải sự cố, rồi cái thật chìm nghỉm trong đó.
    """
    ng = nguong()
    ra = []
    nhieu = M.boi_canh(doc)["may"]["rang"] > 1
    for m in M.muc_ap_dung(doc.get("luot"), doc):
        if m["goc"] != "rang_nhiet_do":
            continue
        v = doc.get(m["f"])
        if M.co_ghi(m, v) and flt(v) > ng["rang_nhiet_max_van_hanh"]:
            ra.append(_("Rang{0}: {1} °C vượt trần vận hành {2} °C — báo tổ trưởng")
                      .format(M.ten_may(m) if nhieu else "", int(flt(v)),
                              ng["rang_nhiet_max_van_hanh"]))
    if cint(doc.get("t2_so_bay_dau_hieu")) > 0:
        ra.append(_("Lượt tuần: {0} trạm bẫy có dấu hiệu — theo dõi tuần sau").format(
            cint(doc.get("t2_so_bay_dau_hieu"))))
    ap = {m["f"] for m in M.muc_ap_dung(doc.get("luot"), doc)}
    if ("nam_cham_vat" in ap and doc.get("nam_cham_vat")
            and not cint(doc.get("nam_cham_mat_kim_loai"))):
        ra.append(_("Nam châm bắt được: {0}").format(doc.get("nam_cham_vat")))
    return ra


def tao_tu_vong_kiem(doc):
    """Sinh phiếu sự cố cho mọi chỗ lệch, gắn hai chiều với lượt.

    Gọi ở `before_submit`, KHÔNG phải `on_submit`: bảng con `su_co` là read-only
    sau khi submit, nên ghi ở on_submit là Frappe chặn "not allowed to change
    after submission". Ở before_submit thì mấy dòng này đi chung một lần ghi với
    chính cú submit — hoặc cả hai cùng vào sổ, hoặc cả hai cùng không. Lỗi giữa
    chừng thì transaction cuộn lại, không để lại phiếu sự cố mồ côi.
    """
    doc.set("su_co", [])
    for key, cong_doan, loai, muc_do, mo_ta in phat_hien(doc):
        m = M.THEO_F.get(key)
        sc = frappe.get_doc({
            "doctype": "SX Su Co",
            "ngay": doc.ngay,
            "nguon": "Vòng kiểm QC",
            "qc_round": doc.name,
            "muc": f'{m["so"]} {m["nhan"]}' if m else key,
            "cong_doan": cong_doan,
            "loai": loai,
            "muc_do": muc_do,
            "mo_ta": mo_ta,
            "trang_thai": "Mở",
        })
        # Xem chú thích đầu file: đây là chỗ DUY NHẤT của module bỏ qua quyền.
        sc.insert(ignore_permissions=True)
        doc.append("su_co", {"incident": sc.name, "muc": sc.muc, "mo_ta": mo_ta})
