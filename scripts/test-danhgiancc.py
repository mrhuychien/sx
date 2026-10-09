"""W44 (D173) — phiếu đánh giá nhà cung cấp BM.07.01 lần BH 02 (SX Danh Gia NCC).

Vì sao phải có bài này:
  · Kết luận là cổng vào danh sách NCC được duyệt BM.07.02: tính sai biên (20 / 29 / 30), bỏ sót luật "điểm chất
    lượng < 5" hay "thiếu hồ sơ phần A" là NCC không đủ điều kiện vẫn được Chấp nhận.
  · Phần A tự điền từ hồ sơ NCC (W09): hồ sơ hết hạn mà ghi Có, mục không áp dụng mà bắt chấm → phiếu sai từ gốc.
  · Luồng ký: Mua hàng chấm → QC ký (vật tư loại 1) → Giám đốc duyệt; người chấm không tự ký, không tự duyệt; phiếu
    Xem xét phải có quyết định của Giám đốc; duyệt xong là khóa (cả Desk).
  · C26: từ ngày áp dụng, tích "Đã duyệt" NCC phải có phiếu Chấp nhận còn hạn; NCC duyệt trước đó không bị chặn, chỉ
    nhắc đánh giá lại.
  · Đánh giá lại: gợi ý điểm I từ tỷ lệ lô không đạt 12 tháng (BM.07.03 + phiếu sự cố gắn lô).

Nạp sx/qc/danh_gia_ncc.py, sx/qc/ncc.py, controller SX Danh Gia NCC, sx/api/qc_danhgiancc.py THẬT trên frappe giả.
Chạy: python3 scripts/test-danhgiancc.py   (verify.sh gọi sẵn)
"""

import os
import re
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

FR = F.cai()
Q = F.nap_qc()
DG = sys.modules["sx.qc.danh_gia_ncc"]
NCC = sys.modules["sx.qc.ncc"]
NH = sys.modules["sx.qc.nhac"]
for g in ("sx.config",):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m
F.nap("sx.config.roles", "sx/config/roles.py")
F.nap("sx.qc.attp", "sx/qc/attp.py")
HS = F.nap("sx.qc.ho_so", "sx/qc/ho_so.py")
F.nap("sx.qc.mau_in", "sx/qc/mau_in.py")
F.nap("sx.api.qc_tailieu", "sx/api/qc_tailieu.py")
A = F.nap("sx.api.qc_danhgiancc", "sx/api/qc_danhgiancc.py")
C = F.nap("c_dg", "sx/qc/doctype/sx_danh_gia_ncc/sx_danh_gia_ncc.py")
F.dang_ky(DG.PT, C.SXDanhGiaNCC)
F.bang_con(DG.PT, "ho_so", DG.PT_A)
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")
L1, L2, TN, NK = DG.LOAI_1, DG.LOAI_2, NCC.TRONG_NUOC, NCC.NHAP_KHAU

NGUOI = {"mua@x": ("Lê Mua Hàng", ["Purchase User"]), "mua2@x": ("Trần Mua Hai", ["Purchase User"]),
         "qc@x": ("Nguyễn Thị QC", ["SX QC"]), "gd@x": ("Giám Đốc", ["SX Quan Ly"]),
         "iso@x": ("Nguyễn Huy Chiến", ["ISO Manager"]), "cd@x": ("Phạm Cơ Điện", ["SX Co Dien"]),
         "goi@x": ("Lê QC Gói", ["SX QC Packing"])}
for u, (ten, _v) in NGUOI.items():
    F.bang("User")[u] = {"name": u, "full_name": ten, "enabled": 1}


def la(u, roles=None):
    F.NGUOI["u"], F.NGUOI["roles"] = u, list(roles or NGUOI[u][1])


def ncc(ma, ten, loai, nguon, duyet=0, **k):
    F.bang("Supplier")[ma] = dict({"name": ma, "supplier_name": ten, "custom_loai_ncc": loai, "custom_nguon_goc": nguon,
                                  "custom_ncc_duyet": duyet, "disabled": 0}, **k)


def ho_so(ma, loai, so_hieu="", ngay_cap=None, het_han=None):
    F.bang("SX Ho So NCC")[f"{ma}-{loai}-{so_hieu}"] = {"name": f"{ma}-{loai}-{so_hieu}", "parent": ma,
                                                         "parenttype": "Supplier", "loai_ho_so": loai,
                                                         "so_hieu": so_hieu, "ngay_cap": ngay_cap, "het_han": het_han}


ncc("NCC-DX", "Công ty Đỗ Xanh Hải Dương", NCC.TP, TN, tax_id="0801234567", mobile_no="0912 000 111")
ncc("NCC-NK", "Green Bean Co. (nhập khẩu)", NCC.TP, NK)
ncc("NCC-BB", "Bao bì thùng carton Minh Anh", NCC.BB_NGOAI, TN)
ncc("NCC-CAT", "Cát rang Lô Sông", NCC.CAT, TN)
ncc("NCC-CU", "Đường Biên Hòa (duyệt trước W44)", NCC.TP, TN, duyet=1)
ncc("NCC-DV", "Dịch vụ diệt côn trùng", NCC.DV, TN)
ho_so("NCC-DX", NCC.DKKD, "0801234567", "2015-03-02")
ho_so("NCC-DX", NCC.CONG_BO, "05/2025/HG", "2025-01-10")
ho_so("NCC-DX", NCC.PKN, "KN-123", "2026-01-02", "2027-01-01")
ho_so("NCC-DX", NCC.HACCP, "HACCP-9", "2023-10-01", "2026-09-30")          # hết hạn trước ngày đánh giá
ho_so("NCC-BB", NCC.DKKD, "0109999999", "2018-05-05")
ho_so("NCC-NK", NCC.DKKD, "GB-1", "2019-01-01")
ho_so("NCC-NK", NCC.CONG_BO, "CB-NK", "2024-01-01")

# ═══ 1. Hàm thuần ═════════════════════════════════════════════════════════
print("\n-- phần A: áp dụng, tự điền, thiếu, luật giấy --")
kiem("áp dụng theo giấy — loại 1 trong nước: 1, 2, 3, 5, 7 áp dụng; 4 không; 6 người chấm chọn",
     [DG.ap_dung(t, L1, TN, NCC.TP) for t in range(1, 8)] == [True, True, True, False, True, None, True])
kiem("loại 1 nhập khẩu: mục 4 (COA từng lô) áp dụng, mục 5 không",
     (DG.ap_dung(4, L1, NK, NCC.TP), DG.ap_dung(5, L1, NK, NCC.TP)) == (True, False))
kiem("loại 2, cát rang: mục 3–6 không áp dụng (chỉ hợp đồng / đơn hàng + ĐKKD — QT.07)",
     all(DG.ap_dung(t, L2, TN, NCC.BB_NGOAI) is False and DG.ap_dung(t, L1, TN, NCC.CAT) is False for t in (3, 4, 5, 6)))
hs_dx = [x for x in F.bang("SX Ho So NCC").values() if x["parent"] == "NCC-DX"]
td = {r["tt"]: r for r in DG.tu_dien(hs_dx, L1, TN, NCC.TP, "2026-10-09")}
kiem("tự điền NCC-DX: ĐKKD Có (số, ngày cấp), hợp đồng Không (chưa có hồ sơ), công bố Có, mục 4 KAD, phiếu kiểm "
     "nghiệm năm Có + hiệu lực, mục 6 để người chấm, HACCP hết hạn 30/09 → Không (vẫn ghi số, hiệu lực)",
     [td[t]["ket_qua"] for t in range(1, 8)] == ["Có", "Không", "Có", "KAD", "Có", "", "Không"]
     and td[1]["so_ngay"] == "0801234567 ngày 02/03/2015" and td[5]["hieu_luc"] == "2027-01-01"
     and td[7]["so_ngay"].startswith("HACCP-9") and td[7]["hieu_luc"] == "2026-09-30", td)
kiem("thiếu phần A: mục bắt buộc Không / chưa chấm; mục 6 ghi KAD được; hiệu lực qua ngày đánh giá là thiếu",
     DG.thieu_a(list(td.values()), L1, TN, NCC.TP, "2026-10-09") == ["Mục 2: Không", "Mục 6: chưa chấm"]
     and DG.thieu_a([dict(r, ket_qua="Có" if t == 2 else ("KAD" if t == 6 else r["ket_qua"])) for t, r in td.items()],
                    L1, TN, NCC.TP, "2026-10-09") == []
     and DG.thieu_a([dict(r, ket_qua="Có" if t in (2, 6) else r["ket_qua"]) for t, r in td.items()], L1, TN, NCC.TP,
                    "2027-02-01") == ["Mục 5: hết hiệu lực 01/01/2027"])
kiem("luật giấy: mục 1, 2, 7 không có ô KAD; mục 3–5 áp dụng thì không ghi KAD; chữ lạ → lỗi; mục 6 KAD được",
     DG.loi_a([{"tt": 1, "ket_qua": "KAD"}], L1, TN, NCC.TP) and DG.loi_a([{"tt": 3, "ket_qua": "KAD"}], L1, TN, NCC.TP)
     and DG.loi_a([{"tt": 2, "ket_qua": "Có thể"}], L1, TN, NCC.TP)
     and not DG.loi_a([{"tt": 6, "ket_qua": "KAD"}, {"tt": 4, "ket_qua": "KAD"}], L1, TN, NCC.TP))

print("\n-- phần B, kết luận: biên 20 / 29 / 30, điểm I < 5, thiếu phần A --")
kiem("điểm đúng mức in sẵn: I 10/5/0, III 10/4 — '7', '5' ở giá, trống, chữ → sai",
     DG.diem_hop_le("diem_i", "10") and DG.diem_hop_le("diem_i", 0) and not DG.diem_hop_le("diem_i", "7")
     and not DG.diem_hop_le("diem_iii", "5") and not DG.diem_hop_le("diem_ii", "") and not DG.diem_hop_le("diem_ii", None)
     and not DG.diem_hop_le("diem_iv", "abc") and DG.TOI_DA == 42)
DU_A = [{"tt": t, "ket_qua": "Có"} for t in (1, 2, 3, 5)] + [{"tt": 4, "ket_qua": "KAD"}, {"tt": 6, "ket_qua": "KAD"},
                                                             {"tt": 7, "ket_qua": "Không"}]


def kl(i, ii, iii, iv, a7="Không", a=None):
    d = {"phan_loai": L1, "nguon": TN, "loai_ncc": NCC.TP, "ngay": "2026-10-09", "diem_i": i, "diem_ii": ii,
         "diem_iii": iii, "diem_iv": iv,
         "ho_so": [dict(r, ket_qua=a7) if r["tt"] == 7 else r for r in (a or DU_A)]}
    t = DG.tinh(d)
    return t["tong"], t["ket_luan"]


kiem("tổng 30 (10 + 10 + 4 + 6), đủ A → Chấp nhận (biên dưới)", kl(10, 10, 4, 6) == (30, DG.CHAP_NHAN))
kiem("tổng 29 → Xem xét (biên trên)", kl(10, 5, 4, 10) == (29, DG.XEM_XET))
kiem("tổng 20 → Xem xét (biên dưới)", kl(5, 5, 4, 6) == (20, DG.XEM_XET))
kiem("tổng 19 → Loại bỏ", kl(5, 0, 4, 10) == (19, DG.LOAI_BO))
kiem("điểm I = 0 (trên 10 % lô không đạt) mà tổng 32 → Loại bỏ (luật I < 5)",
     kl(0, 10, 10, 10, a7="Có") == (32, DG.LOAI_BO))
kiem("có giấy chứng nhận (A7 Có) → V = 2; đủ điểm tối đa 42 → Chấp nhận", kl(10, 10, 10, 10, a7="Có")
     == (42, DG.CHAP_NHAN))
kiem("thiếu hồ sơ phần A (hợp đồng Không) dù 42 điểm → Loại bỏ",
     kl(10, 10, 10, 10, a7="Có", a=[dict(r, ket_qua="Không") if r["tt"] == 2 else r for r in DU_A])
     == (42, DG.LOAI_BO))
kiem("chưa chấm đủ I–IV → chưa kết luận", kl(10, 10, None, 10)[1] is None and kl(10, 10, "", 10)[1] is None)
kiem("gợi ý điểm I từ tỷ lệ lô không đạt: 0 % → 10, 5 % → 5, đúng 10 % → 0, không có lô → không gợi ý",
     (DG.goi_y_diem_i(20, 0), DG.goi_y_diem_i(20, 1), DG.goi_y_diem_i(10, 1), DG.goi_y_diem_i(0, 0))
     == (10, 5, 0, None))
kiem("kết quả khi Giám đốc duyệt: Xem xét theo quyết định; Loại bỏ không thành Chấp nhận được",
     (DG.ket_qua_duyet(DG.CHAP_NHAN, None), DG.ket_qua_duyet(DG.XEM_XET, DG.CHAP_NHAN),
      DG.ket_qua_duyet(DG.XEM_XET, DG.KHONG_CHAP_NHAN), DG.ket_qua_duyet(DG.LOAI_BO, DG.CHAP_NHAN))
     == (DG.CHAP_NHAN, DG.CHAP_NHAN, DG.LOAI_BO, DG.LOAI_BO))
kiem("hạn đánh giá lại = ngày duyệt + 12 tháng (29/02 → 28/02)", str(DG.han_lai("2026-10-09")) == "2027-10-09"
     and str(DG.han_lai("2028-02-29")) == "2029-02-28")
kiem("phân loại gợi ý từ loại NCC: nguyên liệu, bao bì tiếp xúc, cát rang → loại 1; bao bì ngoài → loại 2",
     [DG.phan_loai_mac_dinh(x) for x in (NCC.TP, NCC.BB_TX, NCC.CAT, NCC.BB_NGOAI)] == [L1, L1, L1, L2])

# ═══ 2. Luồng: Mua hàng chấm → QC ký → Giám đốc duyệt ════════════════════
print("\n-- luồng vật tư loại 1: Mua hàng chấm, QC ký, Giám đốc duyệt --")
la("cd@x")
kiem("Cơ điện không vào BM.07.01", "quyền" in (thu(lambda: A.ds()) or ""))
la("qc@x")
kiem("QC không lập phiếu (Mua hàng lập)", "Mua hàng lập" in (thu(lambda: A.lap("NCC-DX")) or ""))
la("mua@x")
kiem("NCC dịch vụ không đánh giá theo BM.07.01", "dịch vụ" in (thu(lambda: A.lap("NCC-DV")) or ""))
p = A.lap("NCC-DX")
P1 = p["name"]
kiem("lập phiếu: lần đầu (chưa có phiếu duyệt), loại 1 trong nước, mã số thuế, điện thoại; phần A tự điền; gợi ý "
     "điểm I theo mẫu / lô thử",
     (p["hinh_thuc"], p["phan_loai"], p["nguon"], p["mst"], p["nguoi_lien_he"], p["trang_thai"])
     == (DG.LAN_DAU, L1, TN, "0801234567", "0912 000 111", DG.NHAP)
     and [x["ket_qua"] for x in p["ho_so"]] == ["Có", "Không", "Có", "KAD", "Có", "", "Không"]
     and p["ho_so"][5]["ap"] is None and p["ho_so"][3]["ap"] is False and "lô thử" in p["goi_y_i"], p)
kiem("lập lại khi phiếu cũ chưa duyệt → mở phiếu đó, không đẻ phiếu thứ hai",
     A.lap("NCC-DX")["name"] == P1 and len(F.bang(DG.PT)) == 1)
e = thu(lambda: A.luu(P1, {"diem_iii": 5}))
kiem("điểm ngoài mức in sẵn → chặn", e and "Điểm III" in e and "10 / 4" in e, e)
e = thu(lambda: A.luu(P1, {"ho_so": [{"tt": 1, "ket_qua": "KAD"}]}))
kiem("mục 1 ghi KAD → chặn (giấy không có ô KAD)", e and "Mục 1" in e, e)
e = thu(lambda: A.gui(P1))
kiem("gửi khi chưa chấm đủ điểm → chặn", e and "Chưa chấm đủ" in e, e)
p = A.luu(P1, {"ho_so": [{"tt": 2, "ket_qua": "Có", "so_ngay": "HĐ 12/2026/HG-DX"}],
               "diem_i": "10", "diem_ii": "10", "diem_iii": 10, "diem_iv": "10", "mat_hang": "Đỗ xanh tách vỏ"})
kiem("chấm: tổng 40 (V = 0 vì HACCP hết hạn), kết luận chưa có vì mục 6 chưa chấm → thiếu phần A → app tính Loại "
     "bỏ", (p["tong"], p["ket_luan"]) == (40, DG.LOAI_BO) and p["thieu_a"] == ["Mục 6: chưa chấm"], p["thieu_a"])
e = thu(lambda: A.gui(P1))
kiem("gửi khi phần A còn mục bỏ trống → chặn, nêu mục", e and "Phần A còn mục chưa chấm: 6" in e, e)
p = A.luu(P1, {"ho_so": [{"tt": 6, "ket_qua": "Có", "so_ngay": "Phiếu KN đỗ đen 07/2026"}]})
kiem("đủ phần A → Chấp nhận (40 điểm)", (p["ket_luan"], p["thieu_a"]) == (DG.CHAP_NHAN, []))
p = A.gui(P1)
kiem("gửi: vật tư loại 1 → Chờ QC; ghi người đánh giá + giờ", p["trang_thai"] == DG.CHO_QC
     and p["ky"]["danh_gia"].startswith("Ký trên phần mềm: Lê Mua Hàng, 09/10/2026"), p["ky"])
kiem("phiếu đã gửi: Mua hàng không sửa; Giám đốc chưa duyệt được (chờ QC)",
     "không sửa" in (thu(lambda: A.luu(P1, {"diem_ii": "5"})) or "")
     and (la("gd@x") or "Giám đốc duyệt" in (thu(lambda: A.duyet(P1)) or "")))
la("qc@x")
p = A.luu(P1, {"diem_ii": "5"})
kiem("QC cùng chấm khi phiếu chờ QC (dịch vụ 5) → tổng 35, vẫn Chấp nhận", (p["tong"], p["ket_luan"])
     == (35, DG.CHAP_NHAN))
p = A.qc_ky(P1, "Mẫu đỗ đạt cảm quan")
kiem("QC ký → Chờ duyệt, chữ ký QC có tên + giờ", p["trang_thai"] == DG.CHO_DUYET
     and p["ky"]["qc"].startswith("Ký trên phần mềm: Nguyễn Thị QC"))
la("mua@x")
kiem("Mua hàng không duyệt", "Giám đốc duyệt" in (thu(lambda: A.duyet(P1)) or ""))
la("gd@x")
p = A.duyet(P1, y_kien="Đồng ý đưa vào danh sách")
kiem("Giám đốc duyệt: Đã duyệt, kết quả Chấp nhận, hạn đánh giá lại 09/10/2027, phiếu khóa",
     (p["trang_thai"], p["ket_qua"], p["han_danh_gia_lai"]) == (DG.DA_DUYET, DG.CHAP_NHAN, "2027-10-09")
     and p["ky"]["duyet"].startswith("Ký trên phần mềm: Giám Đốc") and not p["quyen"]["sua"], p)
la("mua@x")
kiem("phiếu đã duyệt: không sửa qua app", "không sửa" in (thu(lambda: A.luu(P1, {"mat_hang": "X"})) or ""))
d = F.get_doc(DG.PT, P1)
d.mat_hang = "Sửa trên Desk"
kiem("… và không sửa trên Desk", "đã duyệt" in (thu(d.save) or ""))
kiem("Desk không tự đặt trạng thái / kết quả (chỉ API)", "chỉ đổi trên app" in (thu(lambda: F.get_doc({
    "doctype": DG.PT, "supplier": "NCC-BB", "ngay": "2026-10-09", "hinh_thuc": DG.LAN_DAU, "phan_loai": L2,
    "nguon": TN, "trang_thai": DG.DA_DUYET, "ket_qua": DG.CHAP_NHAN}).insert()) or ""))

print("\n-- vật tư loại 2: Xem xét → Giám đốc quyết định; tự duyệt; trả lại --")
la("mua@x")
P2 = A.lap("NCC-BB")["name"]
p = A.luu(P2, {"ho_so": [{"tt": 2, "ket_qua": "Có", "so_ngay": "Đơn hàng 15/9"}], "diem_i": "5", "diem_ii": "5",
               "diem_iii": "4", "diem_iv": "10"})
kiem("bao bì ngoài: loại 2, mục 3–6 KAD tự động; 24 điểm → Xem xét",
     p["phan_loai"] == L2 and [x["ket_qua"] for x in p["ho_so"]][2:6] == ["KAD"] * 4
     and (p["tong"], p["ket_luan"]) == (24, DG.XEM_XET), p)
p = A.gui(P2)
kiem("loại 2 → thẳng Chờ duyệt (không qua QC)", p["trang_thai"] == DG.CHO_DUYET and not p["can_qc"])
la("qc@x")
kiem("QC không ký phiếu loại 2 (không ở bước chờ QC)", "QC ký" in (thu(lambda: A.qc_ky(P2)) or ""))
la("gd@x")
kiem("phiếu Xem xét: Giám đốc phải chọn Chấp nhận / Không chấp nhận", "Không chấp nhận" in (thu(lambda: A.duyet(P2))
                                                                                         or ""))
kiem("trả lại không ghi ý kiến → chặn", "ý kiến" in (thu(lambda: A.tra_lai(P2, " ")) or ""))
p = A.tra_lai(P2, "Bổ sung hợp đồng ký, giao lô thử")
kiem("Giám đốc trả lại kèm ý kiến → Trả lại; Mua hàng sửa, gửi lại được",
     p["trang_thai"] == DG.TRA_LAI and p["y_kien_gd"] == "Bổ sung hợp đồng ký, giao lô thử")
la("mua@x")
A.gui(P2)
la("gd@x")
p = A.duyet(P2, A_QD := DG.KHONG_CHAP_NHAN, "Chưa đạt, tìm NCC khác")
kiem("Giám đốc Không chấp nhận → kết quả Loại bỏ, không có hạn đánh giá lại",
     (p["ket_qua"], p["quyet_dinh"], p["han_danh_gia_lai"]) == (DG.LOAI_BO, A_QD, ""), p)
la("mua@x", ["Purchase User", "SX Quan Ly"])
P3 = A.lap("NCC-CAT")["name"]
A.luu(P3, {"ho_so": [{"tt": 2, "ket_qua": "Có"}], "diem_i": "10", "diem_ii": "10", "diem_iii": "10", "diem_iv": "10"})
p = A.gui(P3)
kiem("cát rang: loại 1 (theo loại NCC) nhưng mục 3–6 KAD; gửi → chờ QC", p["trang_thai"] == DG.CHO_QC
     and [x["ket_qua"] for x in p["ho_so"]][2:6] == ["KAD"] * 4)
la("mua@x", ["Purchase User", "SX QC"])
kiem("người chấm có cả vai QC không tự ký thay QC", "không tự ký" in (thu(lambda: A.qc_ky(P3)) or ""))
la("qc@x")
A.qc_ky(P3)
la("mua@x", ["Purchase User", "SX Quan Ly"])
kiem("người chấm có vai Giám đốc không tự duyệt", "không tự duyệt" in (thu(lambda: A.duyet(P3)) or ""))
la("gd@x")
A.duyet(P3)
la("mua@x")
P4 = A.lap("NCC-NK")["name"]
p = A.luu(P4, {"ho_so": [{"tt": 2, "ket_qua": "Có"}, {"tt": 4, "ket_qua": "Không"}, {"tt": 6, "ket_qua": "KAD"}],
               "diem_i": "10", "diem_ii": "10", "diem_iii": "10", "diem_iv": "10"})
kiem("nhập khẩu thiếu cam kết COA từng lô (mục 4 Không) → thiếu phần A → Loại bỏ dù 40 điểm",
     (p["tong"], p["ket_luan"]) == (40, DG.LOAI_BO) and p["thieu_a"] == ["Mục 4: Không"], p["thieu_a"])
la("mua2@x")
kiem("người khác không xoá nháp của mình; người lập xoá được", "Chỉ xoá" in (thu(lambda: A.xoa(P4)) or "")
     and (la("mua@x") or A.xoa(P4)["ok"] == 1) and P4 not in F.bang(DG.PT))
kiem("phiếu đã duyệt không xoá được", "Chỉ xoá" in (thu(lambda: A.xoa(P1)) or ""))

# ═══ 3. Gợi ý điểm I khi đánh giá lại ═════════════════════════════════════
print("\n-- đánh giá lại: gợi ý điểm I từ lô 12 tháng --")
for i in range(19):
    F.bang("Purchase Receipt")[f"PR-{i}"] = {"name": f"PR-{i}", "supplier": "NCC-DX", "docstatus": 1, "is_return": 0,
                                            "posting_date": "2026-05-0" + str(1 + i % 9)}
    F.bang("Purchase Receipt Item")[f"PRI-{i}"] = {"name": f"PRI-{i}", "parent": f"PR-{i}",
                                                  "parenttype": "Purchase Receipt", "batch_no": f"LO-{i}",
                                                  "custom_ket_luan": "Không đạt" if i == 0 else "Đạt"}
F.bang("Purchase Receipt")["PR-CU"] = {"name": "PR-CU", "supplier": "NCC-DX", "docstatus": 1, "is_return": 0,
                                       "posting_date": "2025-09-01"}
F.bang("Purchase Receipt Item")["PRI-CU"] = {"name": "PRI-CU", "parent": "PR-CU", "parenttype": "Purchase Receipt",
                                             "custom_ket_luan": "Không đạt"}
kiem("19 lô trong 12 tháng, 1 không đạt (5 %) → 5 điểm; lô quá 12 tháng không tính",
     DG.lo_12_thang("NCC-DX", "2026-10-09")[:2] == (19, 1)
     and DG.goi_y_diem_i(*DG.lo_12_thang("NCC-DX", "2026-10-09")[:2]) == 5)
F.bang("SX Su Co")["SC-9"] = {"name": "SC-9", "nguon": "Vòng kiểm QC", "ngay": "2026-08-01"}
F.bang("SX Su Co Lo")["SCL-9"] = {"name": "SCL-9", "parent": "SC-9", "parenttype": "SX Su Co", "batch": "LO-5"}
# Không tính: phiếu sự cố LÚC TIẾP NHẬN (đã tính qua kết luận lô) và phiếu quá 12 tháng.
F.bang("SX Su Co")["SC-10"] = {"name": "SC-10", "nguon": "Tiếp nhận NL", "ngay": "2026-05-01"}
F.bang("SX Su Co Lo")["SCL-10"] = {"name": "SCL-10", "parent": "SC-10", "parenttype": "SX Su Co", "batch": "LO-0"}
F.bang("SX Su Co")["SC-11"] = {"name": "SC-11", "nguon": "Vòng kiểm QC", "ngay": "2025-06-01"}
F.bang("SX Su Co Lo")["SCL-11"] = {"name": "SCL-11", "parent": "SC-11", "parenttype": "SX Su Co", "batch": "LO-7"}
la("mua@x")
p = A.lap("NCC-DX", DG.LAI_NAM)
kiem("thêm phiếu sự cố sau nhận gắn lô của NCC → 2 / 19 (11 %) → gợi ý 0 điểm; phiếu lập sẵn điểm I = 0, ghi rõ căn "
     "cứ", p["hinh_thuc"] == DG.LAI_NAM and p["diem_i"] == "0" and "19 lô nhận, 2 không đạt (gồm 1 phiếu sự cố sau "
     "nhận)" in p["goi_y_i"] and "gợi ý 0 điểm" in p["goi_y_i"], p["goi_y_i"])
P5 = p["name"]

# ═══ 4. C26: nối Supplier ═════════════════════════════════════════════════
print("\n-- C26: tích Đã duyệt NCC phải có phiếu Chấp nhận còn hạn (từ ngày áp dụng) --")


class Ncc(F.Document):
    pass


def tich(ma, **k):
    cu = dict(F.bang("Supplier")[ma], doctype="Supplier",
              custom_ho_so_ncc=[x for x in F.bang("SX Ho So NCC").values() if x["parent"] == ma])
    d = Ncc(cu)
    d.custom_ncc_duyet = 1
    for f, v in k.items():
        d.set(f, v)
    return thu(lambda: NCC.validate_supplier(d))


ho_so("NCC-DX", NCC.ATTP, "ATTP-77", "2025-06-01", "2028-06-01")
ho_so("NCC-BB", NCC.DKKD, "0109999999-b", "2018-05-05")
la("iso@x")
F.CAI_DAT["ncc_ngay_ap_dung_bm0701"] = "2026-10-09"
kiem("NCC có phiếu Chấp nhận còn hạn (DX) → tích Đã duyệt được", tich("NCC-DX") is None, tich("NCC-DX"))
e = tich("NCC-BB")
kiem("NCC phiếu mới nhất Loại bỏ (BB) → chặn, chỉ đường sang BM.07.01", e and "BM.07.01" in e and "C26" in e, e)
F.CAI_DAT["ncc_ngay_ap_dung_bm0701"] = "2026-11-01"
kiem("trước ngày áp dụng → chưa chặn", tich("NCC-BB") is None)
F.CAI_DAT["ncc_ngay_ap_dung_bm0701"] = "2026-10-09"
d = Ncc(dict(F.bang("Supplier")["NCC-CU"], doctype="Supplier", custom_ho_so_ncc=[]))
kiem("NCC duyệt trước C26 (CU), không đổi tích → không bị chặn dù chưa có phiếu",
     thu(lambda: NCC.validate_supplier(d)) is None)
F.dat_ngay("2027-10-10")
kiem("phiếu Chấp nhận quá hạn đánh giá lại (09/10/2027) → duyệt mới bị chặn", "BM.07.01" in (tich("NCC-DX") or ""))
F.dat_ngay("2026-10-09")

# ═══ 5. Nhắc mảng Nhà cung cấp ═══════════════════════════════════════════
print("\n-- nhắc: đánh giá lại, chưa có phiếu, chưa vào BM.07.02, Loại bỏ mà vẫn duyệt, chờ ký --")


def NHAC():
    return [x for x in NH.tinh(F.hom_nay(), [], [], {}, danh_gia_ncc=DG.nhac(F.hom_nay())) if x["nhom"] == "ncc"]


F.bang("Supplier")["NCC-BB"]["custom_ncc_duyet"] = 1
n = {x["tieu_de"]: x for x in NHAC()}
kiem("9/10: DX Chấp nhận chưa tích Đã duyệt → nhắc vào BM.07.02; BB Loại bỏ mà vẫn duyệt → nhắc bỏ duyệt, dừng đặt "
     "hàng; CU (duyệt trước) chưa tới mốc nhắc (hạn lần đầu 31/12, báo trước 30 ngày); mọi mục sang #/so/BM.07.01",
     "1 nhà cung cấp đã Chấp nhận (BM.07.01) chưa vào BM.07.02" in n
     and "Công ty Đỗ Xanh Hải Dương" in n["1 nhà cung cấp đã Chấp nhận (BM.07.01) chưa vào BM.07.02"]["chi_tiet"]
     and "1 nhà cung cấp bị Loại bỏ (BM.07.01) mà vẫn đang duyệt" in n
     and not any("chưa có phiếu" in t for t in n) and all(x["route"] == "#/so/BM.07.01" for x in n.values()), n)
kiem("phiếu đánh giá lại DX đang nháp không thành mục chờ; cát rang đã duyệt thì không còn chờ",
     not any("chờ" in t for t in n))
F.dat_ngay("2026-12-05")
n = {x["tieu_de"]: x for x in NHAC()}
kiem("5/12: NCC duyệt trước C26 chưa có phiếu → nhắc hạn lần đầu 31/12/2026 (còn 26 ngày)",
     "1 nhà cung cấp đã duyệt chưa có phiếu đánh giá BM.07.01" in n
     and "31/12/2026 (còn 26 ngày)" in n["1 nhà cung cấp đã duyệt chưa có phiếu đánh giá BM.07.01"]["chi_tiet"], n)
F.bang("Supplier")["NCC-DX"]["custom_ncc_duyet"] = 1
F.bang("Supplier")["NCC-BB"]["custom_ncc_duyet"] = 0
F.dat_ngay("2027-09-20")
n = {x["tieu_de"]: x for x in NHAC()}
kiem("20/9/2027: DX (hạn 09/10/2027) sắp đến hạn đánh giá lại (còn 19 ngày)",
     "1 nhà cung cấp sắp đến hạn đánh giá lại (BM.07.01)" in n
     and "còn 19 ngày" in n["1 nhà cung cấp sắp đến hạn đánh giá lại (BM.07.01)"]["chi_tiet"], n)
F.dat_ngay("2027-10-15")
kiem("15/10/2027: quá hạn đánh giá lại", any(t.startswith("1 nhà cung cấp quá hạn đánh giá lại") for t in
                                               (x["tieu_de"] for x in NHAC())))
F.dat_ngay("2026-10-09")
la("mua@x")
A.luu(P5, {"ho_so": [{"tt": 2, "ket_qua": "Có"}, {"tt": 6, "ket_qua": "KAD"}], "diem_ii": "10", "diem_iii": "10",
           "diem_iv": "10"})
A.gui(P5)
n = {x["tieu_de"]: x for x in NHAC()}
kiem("phiếu gửi → nhắc chờ QC ký (có tên NCC)", "1 phiếu đánh giá nhà cung cấp chờ QC ký" in n
     and "Đỗ Xanh" in n["1 phiếu đánh giá nhà cung cấp chờ QC ký"]["chi_tiet"], n)
la("qc@x")
v = A.ds()
kiem("màn danh sách — QC: việc chờ ký; NCC (trừ dịch vụ) kèm phiếu đã duyệt gần nhất, phiếu đang mở",
     [x["name"] for x in v["viec"]] == [P5] and "NCC-DV" not in [x["name"] for x in v["ncc"]]
     and next(x for x in v["ncc"] if x["name"] == "NCC-DX")["danh_gia"]["ket_qua"] == DG.CHAP_NHAN
     and next(x for x in v["ncc"] if x["name"] == "NCC-DX")["dang_mo"] == P5, v["viec"])
la("gd@x")
kiem("Giám đốc: chưa có việc (phiếu còn chờ QC)", A.ds()["viec"] == [])
la("mua@x")
kiem("tìm NCC theo tên", [x["name"] for x in A.ds("cát")["ncc"]] == ["NCC-CAT"])

# ═══ 6. Bản in ═══════════════════════════════════════════════════════════
print("\n-- bản in BM.07.01 --")
h = A.in_phieu(P1)
t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))
kiem("đầu trang chung (BM.07.01), ô ☑ theo lựa chọn, phần A 7 mục (☑ Có / ☑ KAD), số + hiệu lực",
     "BM.07.01" in t and "Phiếu đánh giá nhà cung cấp" in h and "☑ Vật tư loại 1 (ảnh hưởng ATTP)" in t
     and "☐ Vật tư loại 2" in t and "☑ Trong nước" in t and "☑ Đánh giá lần đầu" in t
     and "0801234567 ngày 02/03/2015" in t and "hiệu lực 01/01/2027" in t and "☑ KAD" in t, t[:1500])
kiem("phần B: điểm ghi ở dòng mức đã chọn (dịch vụ Bình thường 5), V theo A7, tổng 35 / 42; kết luận ☑ Chấp nhận",
     "- Bình thường 5 5" in t and "- Tốt 10 10" in t and "Tổng điểm 42 35" in t
     and "☑ Chấp nhận – đưa vào BM.07.02" in t and "Kết quả sau duyệt: Chấp nhận" in t
     and "Hạn đánh giá lại: 09/10/2027" in t and "Mã NCC trên phần mềm (Mua hàng mở sau khi Giám đốc duyệt): NCC-DX" in t,
     t[1500:3500])
kiem("ba ô ký: Mua hàng, QC, Giám đốc — Ký trên phần mềm: họ tên + giờ",
     "Ký trên phần mềm: Lê Mua Hàng" in t and "Ký trên phần mềm: Nguyễn Thị QC" in t
     and "Ký trên phần mềm: Giám Đốc" in t and "Ngày 09 tháng 10 năm 2026" in t)
t2 = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", A.in_phieu(P2)))
kiem("phiếu loại 2: ô QC ghi Không áp dụng; phiếu Xem xét in quyết định của Giám đốc",
     "Không áp dụng (vật tư loại 2)" in t2 and "Giám đốc quyết định (phiếu Xem xét): Không chấp nhận" in t2
     and "☑ Xem xét" in t2)
kiem("phiếu chưa duyệt in rõ CHƯA DUYỆT", "CHƯA DUYỆT (Chờ QC)" in re.sub(r"\s+", " ", re.sub(
    r"<[^>]+>", " ", A.in_phieu(P5))))
kiem("gói hồ sơ: các phiếu đã duyệt trong kỳ, mỗi phiếu một tệp",
     sorted(n for n, _h in A.in_ho_so("2026-10-01", "2026-10-31")) == sorted(f"{x}.html" for x in (P1, P2, P3))
     and A.in_ho_so("2026-11-01", "2026-11-30") == [])

F.ket_thuc("DANHGIANCC")
