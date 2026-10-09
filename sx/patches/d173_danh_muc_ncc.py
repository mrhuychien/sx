"""D173 (W44): danh mục có hạn (khung Sổ) + đánh giá nhà cung cấp BM.07.01 + BM.01.04 theo cột giấy.

  · Sổ W44 trong sx/qc/seed/so.json (BM.PRP.04 hóa chất, BM.PRP.05 kính / nhựa giòn, BM.PRP.07 khám sức khỏe, tập
    huấn, BM.05.01 bên quan tâm, BM.05.02 rủi ro): tạo sổ còn thiếu (site đã chạy d172 với seed 5 sổ W43; site mới thì
    d172 đã tạo đủ). Sổ có rồi (Ban ISO đã sửa) không đè.
  · Việc định kỳ: xác định lại bên quan tâm, rủi ro (QT.05) hằng năm trước họp xem xét của lãnh đạo — hạn 15/12/2026
    (Lịch biểu mẫu 21/9/2026: ● T12/26, cùng tháng BM.01.10), nhắc trước 30 ngày.
  · BM.01.04: dòng hồ sơ cho biểu mẫu app lập từ W29 tới W44 còn thiếu (so mã / biểu mẫu, không phân biệt hoa thường,
    khoảng trắng); điền thời gian lưu, người lưu theo BM.01.04 giấy cập nhật 21/9/2026 vào dòng còn TRỐNG (dòng Ban
    ISO đã ghi thì giữ).
  · C26: ngày áp dụng BM.07.01 (chặn tích "Đã duyệt" NCC chưa có phiếu Chấp nhận) = ngày chạy patch nếu Setting còn
    trống; hạn đánh giá lại lần đầu NCC đã duyệt = 31/12/2026 nếu trống.
Chỉ tạo / điền cái còn thiếu. Chạy lại vô hại.
"""

import frappe
from frappe.utils import nowdate

from sx.qc import ho_so as HS
from sx.qc import so as SO

VIEC = ("Xác định lại các bên quan tâm (BM.05.01), rủi ro và cơ hội (BM.05.02)", "Năm", "2026-12-15", 30,
        "Ban ISO; trưởng bộ phận — Giám đốc phê duyệt", "BM.05.01, BM.05.02",
        "QT.05: xác định lại hằng năm trước họp xem xét của lãnh đạo (BM.01.10, tháng 12) hoặc khi yêu cầu các bên, "
        "bối cảnh thay đổi. Cập nhật trên app (Sổ → BM.05.01, BM.05.02), Giám đốc phê duyệt từng dòng; rủi ro cấp độ 1 "
        "là đầu vào BM.01.10.")

KS, TX, NCC, TB, HT, PRP = ("Kiểm soát sản xuất", "Truy xuất, sự cố, khiếu nại", "Nhà cung cấp, nguyên liệu",
                            "Thiết bị đo", "Hệ thống quản lý", "Điều kiện nhà xưởng (PRP)")
# Biểu mẫu app lập từ W29 tới W44: (mã, mã dòng hồ sơ, nhóm, thứ tự, căn cứ). Dòng của W29–W43 các patch trước đã
# tạo — ở đây là lưới an toàn (site lỡ xoá dòng); W44 tạo mới.
MOI = (
    ("BM.08.05", "BM.08.05", KS, 25, "HD.08.02 lần BH 01: giặt, đun sôi ≥ 10 phút 1 lần/tuần; lưu 2 năm tại xưởng."),
    ("SLM", "SLM", TX, 35, "QĐ.01 lần BH 02 — SLM lần BH 02 (21/9/2026): mỗi lô một mẫu, lưu 1 năm từ NSX; sổ lưu 2 năm."),
    ("BM.07.03", "BM.07.03", NCC, 15, "QT.07, HD.07.01 — một dòng mỗi lô nhận; lưu 2 năm kèm COA, phiếu kiểm nghiệm."),
    ("BC.THANG", "BC ATTP tháng", HT, 10, "Đầu vào họp xem xét của lãnh đạo; mục tiêu ATTP năm."),
    ("BM.01.02", "BM.01.02", HT, 3, "QT.01 phần kiểm soát tài liệu; QĐ ban hành, sửa đổi tài liệu 21/9/2026."),
    ("BM.01.03", "BM.01.03", HT, 4, "QT.01 phần kiểm soát tài liệu; QĐ ban hành, sửa đổi tài liệu 21/9/2026."),
    ("BM.01.13", "BM.01.13", HT, 5, "QT.01 phần kiểm soát tài liệu; QĐ ban hành, sửa đổi tài liệu 21/9/2026."),
    ("BM.06.05", "BM.06.05", TB, 40, "QT.06: bảo dưỡng định kỳ 6 tháng/lần, sau sửa chữa QC kiểm trước khi chạy lại."),
    ("BM.PRP.06", "BM.PRP.06", PRP, 40, "PRP SSOP 15; QT.14 Phụ lục B — QLSX giữ sổ, lưu 2 năm."),
    ("BM.03.01", "BM.03.01", HT, 40, "QT.03: kiểm tra thiết bị PCCC hằng tháng; lưu 3 năm."),
    ("BM.03.02", "BM.03.02", HT, 41, "QT.03; PL.03.04: theo dõi dịch bệnh phát sinh; lưu 3 năm."),
    ("BM.03.03", "BM.03.03", HT, 42, "QT.03: kế hoạch kiểm định thiết bị nghiêm ngặt về an toàn; lưu 3 năm."),
    # W44
    ("BM.01.04", "BM.01.04", HT, 5, "QT.01 mục 5.2: danh mục hồ sơ; hằng năm xem xét hồ sơ hết hạn lưu (BM.01.04)."),
    ("BM.05.01", "BM.05.01", HT, 60, "QT.05: các bên quan tâm, yêu cầu, cách đáp ứng; xác định lại hằng năm."),
    ("BM.05.02", "BM.05.02", HT, 61, "QT.05: rủi ro RR = A + B + C + D, cấp độ, biện pháp; xác định lại hằng năm."),
    ("BM.07.01", "BM.07.01", NCC, 5, "QT.07 sửa đổi 01: đánh giá lần đầu, đánh giá lại hằng năm; Giám đốc duyệt."),
    ("BM.PRP.04", "BM.PRP.04", PRP, 50, "PRP SSOP 10: hóa chất được phép, MSDS, nơi để; Cơ điện lập, cập nhật khi đổi."),
    ("BM.PRP.05", "BM.PRP.05", PRP, 60, "PRP SSOP 11: kính, nhựa giòn; QC kiểm hằng tuần (BM.08.01 T4 theo từng vật)."),
    ("BM.PRP.07", "BM.PRP.07", PRP, 70, "PRP SSOP 5, 14: khám sức khỏe 1 lần/năm, tập huấn ATTP; dữ liệu cá nhân."),
)

# BM.01.04 giấy cập nhật 21/9/2026: mã (biểu mẫu app hoặc mã dòng) → (thời gian lưu, người / bộ phận lưu).
LUU = {
    "BM.08.01": ("2 năm", "QC; Ban ISO (bản giấy dự phòng)"), "BM.08.02": ("2 năm", "Ban ISO"),
    "BM.08.03": ("2 năm", "Xưởng sản xuất"), "BM.08.05": ("2 năm", "Xưởng sản xuất"),
    "BM.08.04": ("2 năm", "Ban ISO"), "BM.09.01": ("2 năm", "Kho"), "BM.15.01": ("2 năm", "Xưởng sản xuất"),
    "SLM": ("Sổ 2 năm; mẫu 1 năm từ NSX", "QC"), "BM.07.01": ("2 năm", "Mua hàng"),
    "BM.07.02": ("2 năm (bản hiện hành luôn cập nhật)", "Mua hàng"), "BM.07.03": ("2 năm", "Kho"),
    "BM.06.01": ("Lâu dài", "Cơ điện"), "BM.06.02": ("2 năm", "Xưởng sản xuất"), "BM.06.03": ("2 năm", "Cơ điện"),
    "BM.06.04": ("2 năm", "Cơ điện"), "BM.06.05": ("2 năm", "Cơ điện"), "KH.KN.01": ("3 năm", "Ban ISO"),
    "BM.PRP.01": ("2 năm", "Xưởng sản xuất; Cơ điện"), "BM.PRP.03": ("2 năm", "Xưởng sản xuất; Cơ điện"),
    "BM.PRP.04": ("Cập nhật khi thay đổi", "Cơ điện"), "BM.PRP.05": ("Cập nhật khi thay đổi", "Cơ điện"),
    "BM.PRP.06": ("2 năm", "QLSX"), "BM.PRP.07": ("Theo hiệu lực từng người", "Hành chính"),
    "BM.11.01": ("3 năm", "Ban ISO"), "BM.02.04": ("3 năm", "Ban ISO"),
    "BM.03.01": ("3 năm", "Hành chính; xưởng sản xuất"), "BM.03.02": ("3 năm", "Hành chính; xưởng sản xuất"),
    "BM.03.03": ("3 năm", "Hành chính; xưởng sản xuất"),
    "BM.05.01": ("2 năm; xem xét hằng năm", "Các bộ phận; Ban ISO"),
    "BM.05.02": ("2 năm; xem xét hằng năm", "Các bộ phận; Ban ISO"),
    "BM.01.07": ("2 năm", "Các bộ phận; Ban ISO"), "BC.THANG": ("2 năm", "Ban ISO"),
    "BM.01.13": ("2 năm", "Ban ISO"), "BM.01.02": ("Lâu dài", "Ban ISO; các bộ phận"),
    "BM.01.03": ("Lâu dài", "Ban ISO; các bộ phận"), "BM.01.04": ("Lâu dài", "Ban ISO; các bộ phận"),
    "TU_CONG_BO": ("Lâu dài; bản bị thay thế đánh dấu hết hiệu lực", "Ban ISO"),
    "TCCS 01": ("Lâu dài; bản bị thay thế đánh dấu hết hiệu lực", "Ban ISO"),
    "TCCS 03": ("Lâu dài; bản bị thay thế đánh dấu hết hiệu lực", "Ban ISO"),
}


def _so():
    from sx.patches.d172_so import doc_seed, doc_so
    tao = []
    for x in doc_seed():
        if frappe.db.exists(SO.PT, x["ma"]):
            continue
        frappe.get_doc(doc_so(x)).insert(ignore_permissions=True)
        tao.append(x["ma"])
    return tao


def _viec():
    ten, chu_ky, han, bao_truoc, phu_trach, ho_so, mo_ta = VIEC
    if frappe.db.exists("SX Viec Dinh Ky", {"ten": ten}):
        return
    frappe.get_doc({"doctype": "SX Viec Dinh Ky", "ten": ten, "chu_ky": chu_ky, "han": han, "bao_truoc": bao_truoc,
                    "phu_trach": phu_trach, "ho_so": ho_so, "mo_ta": mo_ta}).insert(ignore_permissions=True)


def _ho_so():
    ds = frappe.get_all(HS.PT, fields=["name", "ma", "bieu_mau", "thoi_gian_luu", "nguoi_luu"])
    co = {HS.chuan_ma(x.ma) for x in ds} | {HS.chuan_ma(x.bieu_mau) for x in ds if x.bieu_mau}
    them = []
    for bm, ma, nhom, thu_tu, can_cu in MOI:
        if HS.chuan_ma(bm) in co or HS.chuan_ma(ma) in co:
            continue
        tg, nguoi = LUU.get(bm, (None, None))
        frappe.get_doc({"doctype": HS.PT, "ma": ma, "ten": HS.BIEU_MAU[bm][0], "nhom": nhom, "nguon": HS.APP,
                        "bieu_mau": bm, "thu_tu": thu_tu, "bat_buoc": 1, "can_cu": can_cu, "thoi_gian_luu": tg,
                        "nguoi_luu": nguoi}).insert(ignore_permissions=True)
        them.append(ma)
    luu = {HS.chuan_ma(k): v for k, v in LUU.items()}
    for x in ds:
        v = luu.get(HS.chuan_ma(x.bieu_mau)) or luu.get(HS.chuan_ma(x.ma))
        if not v:
            continue
        doi = {f: g for f, g in (("thoi_gian_luu", v[0]), ("nguoi_luu", v[1])) if not (x.get(f) or "").strip()}
        if doi:
            frappe.db.set_value(HS.PT, x.name, doi)
    return them


def _c26():
    dt = "SX QC Setting"
    if not frappe.db.get_single_value(dt, "ncc_ngay_ap_dung_bm0701"):
        frappe.db.set_single_value(dt, "ncc_ngay_ap_dung_bm0701", nowdate())
    if not frappe.db.get_single_value(dt, "ncc_han_danh_gia_dau"):
        frappe.db.set_single_value(dt, "ncc_han_danh_gia_dau", "2026-12-31")


def execute():
    try:
        from sx.setup import dam_bao_role       # role W42 (Cơ điện, Hành chính…) do after_migrate tạo — chạy SAU patch
        dam_bao_role()
    except Exception:
        pass
    tao = _so() if frappe.db.table_exists(SO.PT) else []
    if frappe.db.table_exists("SX Viec Dinh Ky"):
        _viec()
    them = _ho_so() if frappe.db.table_exists(HS.PT) else []
    _c26()
    if tao or them:
        print("sx: đã tạo sổ " + (", ".join(tao) or "—") + "; dòng hồ sơ " + (", ".join(them) or "—"))
