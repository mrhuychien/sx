"""Kế hoạch kiểm nghiệm KH.KN.01 (W18, D144) — phần tính, đọc dữ liệu qua frappe.

Mỗi sản phẩm trong danh mục tự công bố (W28 — "SX San Pham Cong Bo", bỏ sản phẩm ngừng sản
xuất) gửi mẫu kiểm nghiệm ít nhất 1 lần / năm: lần sau = ngày gửi gần nhất + 12 tháng; chưa
gửi lần nào → hạn đầu (SX QC Setting, mặc định 31/10/2026 — tài liệu 08/10). Mỗi lần gửi là
một phiếu SX Kiem Nghiem: ngày gửi, đơn vị, chỉ tiêu, kết quả, số phiếu.

Cát rang chỉ kiểm khi ĐỔI NGUỒN (W20): kế hoạch lấy các lần đổi nguồn còn thiếu kết quả kim
loại nặng từ nhật ký cát; phiếu gửi mẫu cát gắn với dòng nhật ký đó, kết quả chép sang nhật ký
(phiếu sự cố Không đạt do nhật ký cát lập — một lần, không trùng).

RANH GIỚI MODULE: chỉ đọc bằng frappe (danh mục sản phẩm là doctype của sx — đọc theo tên,
site không có thì kế hoạch rỗng).
"""

from datetime import date

import frappe
from frappe.utils import getdate

from sx.qc import cat as CATM
from sx.qc.thiet_bi import cong_thang

PT, SP = "SX Kiem Nghiem", "SX San Pham Cong Bo"
SAN_PHAM, CAT = "Sản phẩm", "Cát rang"
DAT, KHONG_DAT = "Đạt", "Không đạt"
CHU_KY = 12           # tháng — "ít nhất 1 lần / năm"
HAN_DAU = date(2026, 10, 31)
SAP_DEN = 30          # ngày: báo "đến hạn"
CHO_LAU = 21          # ngày: gửi mẫu mà chưa có kết quả lâu chừng này thì nhắc hỏi phòng kiểm nghiệm
QUA_HAN, DEN_HAN, CHO_KQ, HONG, DAT_TT = "Quá hạn", "Đến hạn", "Chờ kết quả", "Không đạt — kiểm lại", "Đạt"


def han_dau():
    try:
        v = frappe.get_cached_doc("SX QC Setting").get("kn_han_dau")
    except Exception:
        v = None
    return getdate(v) if v else HAN_DAU


def lan_sau(ngay_gui):
    return cong_thang(ngay_gui, CHU_KY)


def dong_ke_hoach(sp, phieu, hom_nay, hd=HAN_DAU):
    """Một dòng kế hoạch của một sản phẩm — hàm thuần.
    `phieu` = các phiếu gửi mẫu của sản phẩm đó ({ngay_gui, ket_qua, ngay_kq, so_phieu, name})."""
    d = getdate(hom_nay)
    ds = sorted(phieu, key=lambda x: (str(x["ngay_gui"]), str(x.get("name") or "")))
    cuoi = ds[-1] if ds else None
    han = lan_sau(cuoi["ngay_gui"]) if cuoi else getdate(hd)
    if cuoi and not cuoi.get("ket_qua"):
        tt = CHO_KQ
    elif cuoi and cuoi.get("ket_qua") == KHONG_DAT:
        tt = HONG
    elif d > han:
        tt = QUA_HAN
    elif (han - d).days <= SAP_DEN:
        tt = DEN_HAN
    else:
        tt = DAT_TT
    return {"san_pham": sp["name"], "ten": sp.get("ten_san_pham") or sp["name"], "so_cong_bo": sp.get("so_cong_bo"),
            "loai": sp.get("loai"), "tccs": sp.get("tccs"), "trang_thai": tt, "han": str(han), "con": (han - d).days,
            "lan_cuoi": str(cuoi["ngay_gui"]) if cuoi else "", "ket_qua": (cuoi or {}).get("ket_qua") or "",
            "phieu_cuoi": (cuoi or {}).get("name"), "cho_ngay": (d - getdate(cuoi["ngay_gui"])).days
            if cuoi and not cuoi.get("ket_qua") else 0,
            "trong_nam": [str(x["ngay_gui"]) for x in ds if getdate(x["ngay_gui"]).year == d.year]}


def ke_hoach(hom_nay):
    """[dòng kế hoạch] cho mọi sản phẩm còn sản xuất. Site chưa có danh mục → []."""
    try:
        sps = frappe.get_all(SP, filters={"ngung_san_xuat": 0},
                             fields=["name", "ten_san_pham", "so_cong_bo", "loai", "tccs"], order_by="so_cong_bo asc")
        phieu = frappe.get_all(PT, filters={"doi_tuong": SAN_PHAM},
                               fields=["name", "san_pham", "ngay_gui", "ket_qua", "ngay_kq", "so_phieu"])
    except Exception:
        return []
    theo = {}
    for p in phieu:
        theo.setdefault(p.san_pham, []).append(p)
    hd = han_dau()
    return [dong_ke_hoach(s, theo.get(s.name, []), hom_nay, hd) for s in sps]


def cat_cho_kiem():
    """Lần đổi nguồn cát còn thiếu kim loại nặng Đạt (từ nhật ký cát W20) + phiếu gửi mẫu đã gắn."""
    try:
        doi = CATM.cho_kln(frappe.get_all(CATM.PT, filters={"doi_nguon": 1},
                                          fields=["name", "ngay", "ncc_cat", "ten_ncc", "doi_nguon", "kln",
                                                  "luu_lo_mau", "so_phieu_kln"], order_by="ngay asc"))
        gan = {p.nhat_ky_cat: p for p in frappe.get_all(PT, filters={"doi_tuong": CAT, "nhat_ky_cat": ("is", "set")},
                                                        fields=["name", "nhat_ky_cat", "ngay_gui", "ket_qua"])}
    except Exception:
        return []
    return [dict(x, ngay=str(x.ngay), phieu=(gan.get(x.name) or {}).get("name"),
                 ngay_gui=str((gan.get(x.name) or {}).get("ngay_gui") or "")) for x in doi]


def nhac(hom_nay):
    """Dữ liệu cho hộp nhắc QC. Chưa migrate → {}."""
    kh = ke_hoach(hom_nay)
    if not kh:
        return {}
    return {"qua_han": [x for x in kh if x["trang_thai"] == QUA_HAN],
            "den_han": sorted([x for x in kh if x["trang_thai"] == DEN_HAN], key=lambda x: x["han"]),
            "cho_lau": [x for x in kh if x["trang_thai"] == CHO_KQ and x["cho_ngay"] >= CHO_LAU],
            "khong_dat": [x for x in kh if x["trang_thai"] == HONG]}


def dong_bo_cat(phieu):
    """Phiếu gửi mẫu cát gắn dòng nhật ký cát → chép trạng thái kim loại nặng sang nhật ký.
    Lưu qua controller nhật ký cát: Không đạt thì CHÍNH nó lập phiếu sự cố (một lần)."""
    if phieu.get("doi_tuong") != CAT or not phieu.get("nhat_ky_cat"):
        return None
    doc = frappe.get_doc("SX Nhat Ky Cat", phieu.nhat_ky_cat)
    kln = phieu.ket_qua or "Đã gửi mẫu"
    if doc.kln == kln and (doc.so_phieu_kln or "") == (phieu.so_phieu or doc.so_phieu_kln or ""):
        return doc.su_co
    doc.kln = kln
    if phieu.so_phieu:
        doc.so_phieu_kln = phieu.so_phieu
    doc.save(ignore_permissions=True)
    return doc.su_co


def thang_du_kien(dong):
    """Tháng dự kiến gửi mẫu (in trên KH.KN.01): tháng của hạn lần sau."""
    return getdate(dong["han"]).strftime("%m/%Y")
