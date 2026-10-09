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
    """Loại sự cố khi mục Không đạt: loại khai riêng trên mục (D129 — vd thùng ủ là
    PRP vệ sinh), không thì PRP / oPRP (mã oPRP của mục hoặc của bước) / Khác."""
    if m.get("loai"):
        return m["loai"]
    if m["cd"] == "PRP":
        return "PRP"
    return "oPRP" if m.get("oprp") else "Khác"


def _ngan(s, toi_da=140):
    """Mô tả sự cố vừa ô Data của bảng con lượt (SX QC Round Incident.mo_ta, 140 ký tự)."""
    return s if len(s) <= toi_da else s[:toi_da - 1] + "…"


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

        # Nam châm từ bản 3 (W30): ghi đúng nam châm nào (NC-01 / NC-02 M1 / NC-02 M2) — đi nhặt
        # mạt kim loại ở máy vỡ đỗ hay ở máy nghiền M2 là hai việc khác nhau. oPRP-2 như mục 6 cũ.
        if goc in M.NC_DA_KIEM:
            if v == M.KHONG_DAT:
                ra.append((m["f"], m["cd"], "oPRP", THUONG,
                           _("Mục 6 nam châm {0}: Không đạt — chưa tháo, lau sạch hoặc không còn "
                             "hút").format(M.ten_nam_cham(m))))
            continue
        if goc in M.NC_MAT:
            if cint(v):
                vat = doc.get(M.o_vat(m))
                ra.append((m["f"], m["cd"], "oPRP", CAO,
                           _("Nam châm {0} bắt được mạt kim loại{1} — báo cơ điện kiểm máy").format(
                               M.ten_nam_cham(m), _(" (vật: {0})").format(vat) if vat else "")))
            continue

        # T4 theo vật (W44, D173): danh mục kính, nhựa giòn BM.PRP.05 → mỗi vật Không đạt một phiếu (mỗi chỗ vỡ /
        # thiếu chụp là một việc xử lý riêng: dừng khu vực, cách ly sản phẩm hở, dọn, kiểm — SSOP 11).
        if goc == "t4_den_kinh" and v == M.KHONG_DAT:
            hong = [r for r in doc.get("vat_kinh") or [] if r.get("ket_qua") == M.KHONG_DAT]
            for r in hong:
                ten = " ".join(x for x in (r.get("ma"), r.get("ten")) if x) or r.get("vat")
                gc = f" ({r.get('ghi_chu')})" if r.get("ghi_chu") else ""
                ra.append((m["f"], m["cd"], _loai(m), THUONG, _ngan(
                    _("T4 kính, nhựa giòn {0}: Không đạt{1} — vỡ thì dừng khu vực, cách ly sản phẩm hở 3 m "
                      "(SSOP 11)").format(ten, gc))))
            if hong:
                continue

        if m["kieu"] == "chon" and v == M.KHONG_DAT:
            ra.append((m["f"], m["cd"], _loai(m), THUONG,
                       _("Mục {0} {1}: Không đạt").format(
                           m["so"], m["nhan"] + (may if m["may_so"] == 1 else ""))))

        elif m["kieu"] == "chon_cd" and v == M.KHONG_DAT:
            # Vệ sinh chuyển đổi (1e trong ngày, B7c sau vị có sữa): sót là mang
            # chất gây dị ứng sang mẻ sau — loại Dị ứng. Mức Thường: chưa có kết
            # quả dương tính, chỉ là bước vệ sinh chưa đạt (khác B7 dương tính).
            ra.append((m["f"], m["cd"], _loai(m), THUONG,
                       _("Mục {0} {1}: Không đạt").format(m["so"], m["nhan"])))

        elif goc == "di_vat_ray" and cint(v):
            # Dị vật trên rây kiểm = mối nguy vật lý đã lọt tới bột — Cao như mạt
            # kim loại ở nam châm.
            ra.append((m["f"], m["cd"], "oPRP", CAO,
                       _("Rây kiểm RY-01{0}: có dị vật — cô lập bột của máy, kiểm lưới "
                         "rây").format(may if may else M.ten_may(m))))

        elif goc == "hat_tho" and M.co_ghi(m, v):
            toi_da = ng.get("hat_tho_toi_da")
            if toi_da is not None and cint(v) > toi_da:
                ra.append((m["f"], m["cd"], "oPRP", THUONG,
                           _("Rây kiểm RY-01{0}: {1} hạt thô > {2}").format(
                               may if may else M.ten_may(m), cint(v), toi_da)))

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
            # Hàn nguội → hở túi; hàn nóng → cháy màng, cũng hở. Mối hàn túi bột là PRP
            # (W38, D168 — quyết định 09/10/2026; D128 từng xếp oPRP): loại theo mục.
            lo, hi = ng["han_nhiet_min"], ng["han_nhiet_max"]
            if (lo is not None and flt(v) < lo) or (hi is not None and flt(v) > hi):
                ra.append((m["f"], m["cd"], _loai(m), THUONG,
                           _("Máy đóng gói bột{0}: nhiệt độ hàn {1} °C ngoài khoảng "
                             "{2}–{3} °C").format(may, int(flt(v)),
                                                  "…" if lo is None else lo,
                                                  "…" if hi is None else hi)))

        elif goc == "thung_bot_qua_han":
            # Lưu bột 2 ngày, nắp hộp bột là PRP (W38, D168) — loại theo mục.
            if cint(v) > ng["thung_bot_max"]:
                ra.append((m["f"], m["cd"], _loai(m), THUONG,
                           _("Kho bột: {0} thùng quá 2 ngày / hở nắp").format(cint(v))))

        elif goc in ("b2_rang_lac_nhiet", "b2_rang_lac_phut") and M.co_ghi(m, v):
            # Khoảng chốt ở W03 (D128): 150–180 °C, 30–40 phút. Thiếu nhiệt / thiếu
            # giờ thì lạc chưa chín (vi sinh); quá thì cháy — cả hai đều lệch oPRP.
            # Một đầu bị xoá khỏi Setting và không có mặc định thì đầu đó không xét.
            k, ten, dv = (("rang_lac_nhiet", _("nhiệt độ"), "°C") if goc.endswith("nhiet")
                          else ("rang_lac_phut", _("thời gian"), _("phút")))
            lo, hi = ng[k + "_min"], ng[k + "_max"]
            if (lo is not None and flt(v) < lo) or (hi is not None and flt(v) > hi):
                ra.append((m["f"], m["cd"], "oPRP", THUONG,
                           _("Rang lạc: {0} {1} {2} ngoài khoảng {3}–{4} {2}").format(
                               ten, int(flt(v)), dv, "…" if lo is None else lo,
                               "…" if hi is None else hi)))
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
    if nguong().get("hat_tho_toi_da") is None:
        # Chưa có ngưỡng thì không thành sự cố — nhưng có hạt thô thì phải NÓI.
        for m in M.muc_ap_dung(doc.get("luot"), doc):
            if m["goc"] == "hat_tho" and cint(doc.get(m["f"])) > 0:
                ra.append(_("Rây kiểm RY-01{0}: {1} hạt thô — chưa có ngưỡng, báo tổ "
                            "trưởng xem lưới").format(M.ten_may(m), cint(doc.get(m["f"]))))
    if cint(doc.get("t2_so_bay_dau_hieu")) > 0:
        ra.append(_("Lượt tuần: {0} trạm bẫy có dấu hiệu — theo dõi tuần sau").format(
            cint(doc.get("t2_so_bay_dau_hieu"))))
    ap_dung = M.muc_ap_dung(doc.get("luot"), doc)
    ap = {m["f"] for m in ap_dung}
    if ("nam_cham_vat" in ap and doc.get("nam_cham_vat")
            and not cint(doc.get("nam_cham_mat_kim_loai"))):
        ra.append(_("Nam châm bắt được: {0}").format(doc.get("nam_cham_vat")))
    for m in ap_dung:                     # W30: từng nam châm
        if m["goc"] in M.NC_VAT and doc.get(m["f"]) and not cint(doc.get(m["f"].replace("_vat", "_mat_kim_loai"))):
            ra.append(_("Nam châm {0} bắt được: {1}").format(M.ten_nam_cham(m), doc.get(m["f"])))
    return ra


def ten_cong_doan(ten_goc):
    """Tên HIỆN TẠI của công đoạn mà mục kiểm trỏ tới (W04, D130).

    Mục kiểm khai công đoạn bằng tên gốc trong muc.py; Ban ISO có thể đã đổi tên
    trong SX QC Cong Doan cho khớp QT.08. Tra qua MÃ: tên gốc → mã → tên đang dùng.
    Chưa có danh mục (chưa migrate) / không tìm thấy thì giữ tên gốc.
    """
    ma = M.MA_CONG_DOAN.get(ten_goc)
    if not ma:
        return ten_goc
    try:
        return frappe.db.get_value("SX QC Cong Doan", {"ma": ma}, "name") or ten_goc
    except Exception:
        return ten_goc


def tao_tu_vong_kiem(doc):
    """Sinh phiếu sự cố cho mọi chỗ lệch, gắn hai chiều với lượt.

    Gọi ở `before_submit`, KHÔNG phải `on_submit`: bảng con `su_co` là read-only
    sau khi submit, nên ghi ở on_submit là Frappe chặn "not allowed to change
    after submission". Ở before_submit thì mấy dòng này đi chung một lần ghi với
    chính cú submit — hoặc cả hai cùng vào sổ, hoặc cả hai cùng không. Lỗi giữa
    chừng thì transaction cuộn lại, không để lại phiếu sự cố mồ côi.
    """
    doc.set("su_co", [])
    ten_cd = {}
    for key, cong_doan, loai, muc_do, mo_ta in phat_hien(doc):
        if cong_doan not in ten_cd:
            ten_cd[cong_doan] = ten_cong_doan(cong_doan)
        m = M.THEO_F.get(key)
        sc = frappe.get_doc({
            "doctype": "SX Su Co",
            "ngay": doc.ngay,
            "nguon": "Vòng kiểm QC",
            "qc_round": doc.name,
            "muc": f'{m["so"]} {m["nhan"]}' if m else key,
            "cong_doan": ten_cd[cong_doan],
            "loai": loai,
            # Mã oPRP cụ thể (W03): sự cố oPRP phải gắn đúng oPRP nào của KH.HACCP.
            "oprp": (m.get("oprp") or "") if (m and loai == "oPRP") else "",
            "muc_do": muc_do,
            "mo_ta": mo_ta,
            "trang_thai": "Mở",
        })
        # Xem chú thích đầu file: đây là chỗ DUY NHẤT của module bỏ qua quyền.
        sc.insert(ignore_permissions=True)
        doc.append("su_co", {"incident": sc.name, "muc": sc.muc, "mo_ta": mo_ta})
