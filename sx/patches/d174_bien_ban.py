"""D174 (W45): khung "Biên bản" — mẫu biên bản, việc định kỳ năm, công đoạn bột theo sơ đồ, dòng hồ sơ, mốc sơ đồ.

  · Mẫu biên bản theo sx/qc/seed/bien_ban.json (18 phiếu giấy: BM.01.05, 01.06, 01.08–01.11, 04.01, 04.02, HACCP.01,
    HACCP.02, 14.01, 14.02, 02.01, 02.02, 02.03, 02.05, 03.04, PRP.02): tạo mẫu còn thiếu; mẫu có rồi (Ban ISO đã sửa)
    không đè. Vai trong seed không có trên site thì bỏ khỏi vai lập / xem.
  · Việc định kỳ năm theo Lịch biểu mẫu 21/9/2026 (sheet "Lịch 12 tháng"): xem xét của lãnh đạo T12/2026, đánh giá
    nội bộ T11/2026 (QĐ 21/9 Phụ lục 2: quý IV/2026), thẩm tra T11–12/2026, diễn tập PCCC T11/2026, diễn tập truy xuất
    T9/2027 và QT.14 T9/2027 (lần gần nhất 24/9/2026). Ô hồ sơ = mã biên bản đóng việc: biên bản đó ký đủ thì việc tự
    ghi "đã làm" (sx/api/qc_bienban.py).
  · Công đoạn dây chuyền bột theo sơ đồ 11 công đoạn KH.HACCP.02 mục 5.5: thêm 4 công đoạn còn thiếu (bột đậu xanh, bột
    đậu đen bán thành phẩm, lưu kho, xuất hàng); thứ tự 7 công đoạn có sẵn đổi theo sơ đồ — chỉ khi thứ tự vẫn là của
    D130 (Ban ISO đã sửa thì giữ). BM.HACCP.01 bột kéo đủ 11 công đoạn.
  · Mốc sơ đồ (SX QC Setting.so_do_moc): bánh = danh mục công đoạn lúc chạy patch, coi như đã xác nhận bằng giấy
    22/9/2026; bột chưa có mốc → hộp nhắc lập BM.HACCP.01 ngay.
  · BM.01.04: dòng hồ sơ cho 18 biểu mẫu (thời gian lưu theo mục 3: BM.01.10, 02.03–05, 03.x, 04.x, 14.x, HACCP 3 năm;
    còn lại 2 năm). Dòng có rồi không đè.
Chỉ tạo / điền cái còn thiếu. Chạy lại vô hại.
"""

import json
import os

import frappe

from sx.qc import bien_ban as BB
from sx.qc import ho_so as HS

SEED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qc", "seed", "bien_ban.json")
VD = "SX Viec Dinh Ky"
CD = "SX QC Cong Doan"

# (tên việc, hạn, nhắc trước, phụ trách, mã biên bản đóng việc, làm gì)
VIEC = (
    ("Xem xét của lãnh đạo (BM.01.10)", "2026-12-31", 30, "Giám đốc; Trưởng Ban ISO", "BM.01.10",
     "QT.01 mục 5.5: ít nhất 1 lần/năm (đầu vào ISO 22000 mục 9.3.2, đầu ra 9.3.3); xem xét Chính sách, mục tiêu "
     "ATTP. Báo cáo đầu vào gửi Giám đốc trước ít nhất 03 ngày làm việc. Lập biên bản trên app (QC → Xem xét → Biên "
     "bản → BM.01.10) — ký đủ thì việc này tự ghi đã làm."),
    ("Đánh giá nội bộ mọi bộ phận (BM.01.05 → BM.01.09)", "2026-11-30", 30, "Ban ISO; trưởng đoàn do Giám đốc chỉ định",
     "BM.01.09",
     "QT.01: mọi bộ phận ít nhất 1 lần/năm (Lịch biểu mẫu: T11/2026; QĐ 21/9/2026 Phụ lục 2: quý IV/2026). Kế hoạch "
     "BM.01.05 → checklist BM.01.06 → điểm lưu ý BM.01.08 → báo cáo BM.01.09 trên app; báo cáo ký đủ thì việc tự ghi "
     "đã làm."),
    ("Thẩm tra hệ thống (BM.04.01 → BM.04.02)", "2026-12-15", 30, "Trưởng Ban ISO; thành viên Ban ISO", "BM.04.02",
     "QT.04: sau đánh giá nội bộ, trước xem xét của lãnh đạo (Lịch biểu mẫu: T11–12/2026); thẩm tra xác nhận giá trị "
     "không quá 12 tháng/lần. Báo cáo thẩm tra ký đủ thì việc tự ghi đã làm."),
    ("Diễn tập PCCC, tình huống khẩn cấp (KH.03.01, BM.03.04)", "2026-11-30", 30, "Hành chính; Ban ISO; Cơ điện",
     "BM.03.04",
     "QT.03, KH.03.01: ít nhất 1 lần/năm — DT-1 và DT-2 hoặc DT-3 luân phiên (lần đầu quý IV/2026: DT-1, DT-2). Biên "
     "bản BM.03.04 lập ngay sau buổi diễn tập."),
    ("Diễn tập truy xuất và thu hồi (BM.02.03, 02.04, 02.05)", "2027-09-24", 30, "Ban ISO", "BM.02.05",
     "QT.02: ít nhất 1 lần/năm (Lịch biểu mẫu: T9/2027 — lần gần nhất 24/9/2026). Kịch bản BM.02.03, bấm giờ ở tab "
     "Truy xuất (BM.02.04), biên bản đánh giá BM.02.05."),
    ("Xem xét đánh giá gian lận (BM.14.01), kế hoạch phòng vệ thực phẩm (BM.14.02)", "2027-09-24", 30,
     "Trưởng Ban ISO — Giám đốc ký", "BM.14.01",
     "QT.14: xem xét hằng năm (Lịch biểu mẫu: T9/2027 — ký lần đầu 24/9/2026); đánh giá lại khi đổi NCC / nguồn, có "
     "cảnh báo gian lận, sự cố. Lập trên app, chép bảng của lần trước rồi sửa; lập cả BM.14.02."),
)

# Sơ đồ bột KH.HACCP.02 mục 5.5: (mã, tên, thứ tự theo sơ đồ, thứ tự D130 — None = công đoạn mới).
BOT = (
    ("bot-tiep-nhan", "Bột: tiếp nhận", 1, 1),
    ("bot-btp-dau-xanh", "Bột: bột đậu xanh bán thành phẩm", 2, None),
    ("bot-btp-dau-den", "Bột: bột đậu đen bán thành phẩm", 3, None),
    ("bot-nhat-lac", "Bột: nhặt lạc", 4, 2),
    ("bot-rang-lac", "Bột: rang lạc", 5, 3),
    ("bot-xay-duong", "Bột: xay đường", 6, 4),
    ("bot-tron", "Bột: trộn", 7, 5),
    ("bot-dong-tui", "Bột: đóng túi", 8, 6),
    ("bot-dong-thung", "Bột: đóng thùng", 9, 7),
    ("bot-luu-kho", "Bột: lưu kho thành phẩm", 10, None),
    ("bot-xuat-hang", "Bột: xuất hàng, phân phối", 11, None),
)

HT, KS, TX, PRP = "Hệ thống quản lý", "Kiểm soát sản xuất", "Truy xuất, sự cố, khiếu nại", "Điều kiện nhà xưởng (PRP)"
# Dòng BM.01.04: (mã, nhóm, thứ tự, thời gian lưu, người lưu, căn cứ).
HO_SO = (
    ("BM.01.05", HT, 20, "2 năm", "Ban ISO", "QT.01: đánh giá nội bộ mọi bộ phận ít nhất 1 lần/năm."),
    ("BM.01.06", HT, 21, "2 năm", "Ban ISO", "QT.01: checklist từng bộ phận của đợt đánh giá nội bộ."),
    ("BM.01.08", HT, 22, "2 năm", "Ban ISO", "QT.01: tổng hợp điểm lưu ý gửi các bộ phận."),
    ("BM.01.09", HT, 23, "2 năm", "Ban ISO", "QT.01: báo cáo kết quả đánh giá nội bộ — đầu vào BM.01.10."),
    ("BM.01.10", HT, 24, "3 năm", "Ban ISO (kèm báo cáo đầu vào)", "QT.01 mục 5.5: xem xét của lãnh đạo ≥ 1 lần/năm."),
    ("BM.01.11", HT, 25, "2 năm", "Ban ISO", "QĐ kiện toàn Ban ISO 21/9/2026: họp hằng tuần."),
    ("BM.04.01", HT, 30, "3 năm", "Ban ISO", "QT.04: kế hoạch thẩm tra hằng năm, khi có thay đổi."),
    ("BM.04.02", HT, 31, "3 năm", "Ban ISO", "QT.04: báo cáo thẩm tra; không đạt → thẩm tra lại, BM.01.07."),
    ("BM.14.01", HT, 50, "3 năm", "Ban ISO (bản có chữ ký)", "QT.14 Phụ lục A: xem xét hằng năm."),
    ("BM.14.02", HT, 51, "3 năm", "Ban ISO (bản có chữ ký)", "QT.14 Phụ lục B: xem xét hằng năm."),
    ("BM.03.04", HT, 43, "3 năm", "Ban ISO", "QT.03, KH.03.01: diễn tập PCCC, tình huống khẩn cấp ≥ 1 lần/năm."),
    ("BM.HACCP.01", KS, 50, "3 năm", "Ban ISO", "KH.HACCP mục 5.5: xác nhận sơ đồ tại hiện trường khi thay đổi."),
    ("BM.HACCP.02", KS, 51, "3 năm", "Ban ISO", "KH.HACCP mục 5.10, 5.13: thẩm định biện pháp kiểm soát (oPRP)."),
    ("BM.02.01", TX, 40, "2 năm", "Ban ISO", "QT.02: kế hoạch thu hồi khi có quyết định thu hồi."),
    ("BM.02.02", TX, 41, "2 năm", "Ban ISO", "QT.02: báo cáo thu hồi — đầu vào BM.01.10 mục e."),
    ("BM.02.03", TX, 42, "3 năm", "Ban ISO", "QT.02: kịch bản diễn tập truy xuất, thu hồi ≥ 1 lần/năm."),
    ("BM.02.05", TX, 43, "3 năm", "Ban ISO", "QT.02: biên bản đánh giá diễn tập — đầu vào BM.01.10 mục e."),
    ("BM.PRP.02", PRP, 20, "2 năm", "Xưởng sản xuất", "PRP SSOP 7: chỉ khi gọi dịch vụ — không phun, diệt định kỳ."),
)


def doc_seed():
    with open(SEED, encoding="utf-8") as fh:
        return json.load(fh)


def doc_mau(x, co_role=None):
    """Một mẫu trong seed → dict tạo SX Mau Bien Ban. `co_role(r)` → role có trên site không (vai thiếu thì bỏ)."""
    co = co_role or (lambda r: True)
    d = {"doctype": BB.PT, **{k: x.get(k) for k in ("ma", "ten", "quy_trinh", "lan_ban_hanh", "chu_ky_lap",
                                                       "nhan_ngay", "ky_hieu_so", "goc_mau", "ky_tay_khi",
                                                       "nguon_car", "ghi_chu")}}
    d["phan"] = [dict({k: v for k, v in p.items() if k != "cot"}, cot=json.dumps(p.get("cot") or [],
                                                                                ensure_ascii=False))
                 for p in x.get("phan") or []]
    d["ky"] = [dict(s) for s in x.get("ky") or []]
    for o in ("vai_lap", "vai_xem"):
        d[o] = [{"role": r} for r in x.get(o) or [] if co(r)]
    return d


def _mau():
    tao, bo = [], []
    ds = doc_seed()
    for x in sorted(ds, key=lambda x: 1 if x.get("goc_mau") else 0):     # mẫu gốc trước (goc_mau là Link)
        if frappe.db.exists(BB.PT, x["ma"]):
            continue
        thieu = [s["role"] for s in x.get("ky") or [] if s.get("role") and not frappe.db.exists("Role", s["role"])]
        if thieu:
            bo.append(f"{x['ma']} (thiếu vai {', '.join(thieu)})")
            continue
        frappe.get_doc(doc_mau(x, lambda r: bool(frappe.db.exists("Role", r)))).insert(ignore_permissions=True)
        tao.append(x["ma"])
    return tao, bo


def _viec():
    for ten, han, bao_truoc, phu_trach, ho_so, mo_ta in VIEC:
        if frappe.db.exists(VD, {"ten": ten}):
            continue
        frappe.get_doc({"doctype": VD, "ten": ten, "chu_ky": "Năm", "han": han, "bao_truoc": bao_truoc,
                        "phu_trach": phu_trach, "ho_so": ho_so, "mo_ta": mo_ta}).insert(ignore_permissions=True)


def _cong_doan_bot():
    them = []
    for ma, ten, tt, tt_cu in BOT:
        ten_co = frappe.db.get_value(CD, {"ma": ma}, "name") or (ten if frappe.db.exists(CD, ten) else None)
        if not ten_co:
            frappe.get_doc({"doctype": CD, "ten": ten, "day_chuyen": "Bột", "thu_tu": tt,
                            "ma": ma}).insert(ignore_permissions=True)
            them.append(ten)
            continue
        if tt_cu is not None and frappe.db.get_value(CD, ten_co, "thu_tu") == tt_cu and tt != tt_cu:
            frappe.db.set_value(CD, ten_co, "thu_tu", tt)
    return them


def _moc_so_do():
    dt = "SX QC Setting"
    if BB.doc_json(frappe.db.get_single_value(dt, "so_do_moc"), {}):
        return
    ds = BB.ds_cong_doan(BB.BANH)
    if ds:
        frappe.db.set_single_value(dt, "so_do_moc", BB.ghi_json(
            {BB.BANH: {"ngay": BB.SO_DO_GIAY[BB.BANH].isoformat(), "van_tay": BB.van_tay(ds)}}))


def _ho_so():
    ds = frappe.get_all(HS.PT, fields=["name", "ma", "bieu_mau"])
    co = {HS.chuan_ma(x.ma) for x in ds} | {HS.chuan_ma(x.bieu_mau) for x in ds if x.bieu_mau}
    them = []
    for ma, nhom, thu_tu, tg, nguoi, can_cu in HO_SO:
        if HS.chuan_ma(ma) in co:
            continue
        frappe.get_doc({"doctype": HS.PT, "ma": ma, "ten": HS.BIEU_MAU[ma][0], "nhom": nhom, "nguon": HS.APP,
                        "bieu_mau": ma, "thu_tu": thu_tu, "bat_buoc": 1, "can_cu": can_cu, "thoi_gian_luu": tg,
                        "nguoi_luu": nguoi}).insert(ignore_permissions=True)
        them.append(ma)
    return them


def execute():
    try:
        from sx.setup import dam_bao_role       # role của app do after_migrate tạo — chạy SAU patch
        dam_bao_role()
    except Exception:
        pass
    tao, bo = _mau() if frappe.db.table_exists(BB.PT) else ([], [])
    if frappe.db.table_exists(VD):
        _viec()
    them_cd = _cong_doan_bot() if frappe.db.table_exists(CD) else []
    if frappe.db.table_exists(CD):
        _moc_so_do()
    them = _ho_so() if frappe.db.table_exists(HS.PT) else []
    if tao or bo or them or them_cd:
        print("sx: mẫu biên bản " + (", ".join(tao) or "—") + (f"; BỎ QUA {', '.join(bo)}" if bo else "")
              + "; công đoạn bột " + (", ".join(them_cd) or "—") + "; dòng hồ sơ " + (", ".join(them) or "—"))
