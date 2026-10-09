"""Phiếu đánh giá nhà cung cấp BM.07.01 (W44, D173) — luật ở sx/qc/danh_gia_ncc.py, luồng ở sx/api/qc_danhgiancc.py.

Chặn ở đây nên chặn cả Desk:
  · thông tin NCC (tên, loại) lấy từ Supplier; phần A đủ 7 mục, đúng luật giấy (mục 1, 2, 7 chỉ Có / Không; mục 3–5 áp
    dụng thì không KAD; mục không áp dụng → KAD); điểm phần B đúng mức in sẵn;
  · điểm V, tổng, kết luận, thiếu phần A do app TÍNH — giá trị gõ tay bị tính đè;
  · trạng thái, chữ ký, kết quả, hạn đánh giá lại chỉ đổi qua API (cờ frappe.flags.sx_dgncc); phiếu đã duyệt là khóa.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from sx.qc import danh_gia_ncc as DG

# Ô chỉ API được đổi (luồng ký, duyệt).
CHI_API = ("trang_thai", "nguoi_danh_gia", "danh_gia_luc", "qc_ky", "qc_luc", "y_kien_qc", "duyet_boi", "duyet_luc",
           "quyet_dinh", "y_kien_gd", "ket_qua", "han_danh_gia_lai")


class SXDanhGiaNCC(Document):
    def validate(self):
        api = bool(getattr(frappe.flags, "sx_dgncc", False))
        cu = None if self.is_new() else self.get_doc_before_save()
        if cu is not None and cu.get("trang_thai") == DG.DA_DUYET and not api:
            frappe.throw(_("Phiếu {0} đã duyệt — không sửa. Đánh giá lại thì lập phiếu mới.").format(self.name))
        if not api:
            for f in CHI_API:
                if ((cu.get(f) if cu is not None else None) or None) != (self.get(f) or None) and not (
                        cu is None and f == "trang_thai" and self.get(f) in (None, "", DG.NHAP)):
                    frappe.throw(_("Trạng thái, chữ ký, kết quả của phiếu BM.07.01 chỉ đổi trên app (màn Sổ → "
                                   "BM.07.01)."), frappe.PermissionError)
        self.trang_thai = self.trang_thai or DG.NHAP
        s = frappe.db.get_value("Supplier", self.supplier, ["supplier_name", "custom_loai_ncc"], as_dict=True)
        if not s:
            frappe.throw(_("Không có nhà cung cấp {0}.").format(self.supplier))
        self.ten_ncc, self.loai_ncc = s.supplier_name or self.supplier, s.custom_loai_ncc or ""
        for f, lua in (("hinh_thuc", DG.HINH_THUC), ("phan_loai", DG.PHAN_LOAI), ("nguon", DG.NGUON)):
            if self.get(f) not in lua:
                frappe.throw(_("Chọn {0}: {1}.").format(self.meta.get_label(f) if self.meta else f, " / ".join(lua)))
        self.chuan_a()
        for k in DG.CHAM_TAY:
            v = self.get(k)
            if v not in (None, "") and not DG.diem_hop_le(k, v):
                ten = DG.MUC_B[k]
                frappe.throw(_("Điểm {0} {1}: chọn {2}.").format(ten[0], ten[1].split(" (")[0].lower(), " / ".join(
                    str(d) for _m, d in ten[2])))
        t = DG.tinh(self.as_dict())
        self.diem_v, self.tong, self.ket_luan = t["diem_v"], t["tong"], t["ket_luan"]
        self.thieu_a = "; ".join(t["thieu"]) or None

    def chuan_a(self):
        """Đủ 7 mục theo TT (thiếu mục thì thêm dòng trống), sắp theo TT, chữ "Áp dụng" như giấy, mục không áp dụng
        → KAD; dòng sai luật giấy → chặn."""
        theo = {}
        for r in self.get("ho_so") or []:
            tt = int(r.get("tt") or 0)
            if tt in theo:
                frappe.throw(_("Phần A: mục {0} ghi hai lần.").format(tt))
            theo[tt] = r
        loi = DG.loi_a([{"tt": tt, "ket_qua": r.get("ket_qua")} for tt, r in theo.items()], self.phan_loai,
                       self.nguon, self.loai_ncc)
        if loi:
            frappe.throw(_("Phần A: {0}").format(" ".join(loi)))
        dong = []
        for tt in DG.MUC_A:
            r = theo.get(tt)
            d = {"tt": tt, "ap_dung": DG.MUC_A[tt][1], "ket_qua": (r.get("ket_qua") if r else None) or None,
                 "so_ngay": (r.get("so_ngay") if r else None) or None, "hieu_luc": (r.get("hieu_luc") if r else None)}
            if DG.ap_dung(tt, self.phan_loai, self.nguon, self.loai_ncc) is False:
                d["ket_qua"] = DG.KAD
            dong.append(d)
        self.set("ho_so", dong)
