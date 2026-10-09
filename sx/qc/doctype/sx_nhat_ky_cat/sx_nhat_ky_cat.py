"""Một việc trong nhật ký cát rang BM.08.03 — W20 (D141), W32 (D164): mỗi việc một dòng. Luật tính ở sx/qc/cat.py.

Chặn ở đây nên chặn cả đường Desk:
  · không ghi trước ngày; dòng mới phải chọn việc; nhập cát phải có nguồn; nhập, đưa dùng, bổ sung phải có khối
    lượng; loại phải có lý do; vệ sinh phải nói thùng hay khay;
  · bổ sung / loại khi máy không có cát đang dùng (chưa đưa dùng, hoặc đã loại mà chưa đưa cát mới) → chặn;
  · số ngày đã dùng (bổ sung, loại), đổi nguồn (nhập), thay toàn bộ (đưa dùng) do app tính; nhập, sửa, xoá một
    dòng nhập thì dấu đổi nguồn của các lần nhập sau tính lại;
  · dòng Ban ISO đã xem xét thì khoá (chỉ Ban ISO sửa / xoá) — riêng kết quả kim loại nặng, số phiếu, lọ mẫu vẫn
    cập nhật được vì kết quả về sau ngày ký; dòng sổ cũ (trước D164) giữ nguyên;
  · kim loại nặng Không đạt → tự lập phiếu sự cố (nguồn Nhật ký cát, mức Cao).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate

from sx.qc import cat as CAT
from sx.qc.quyen import la_iso

# Sửa được sau khi Ban ISO đã xem xét (kết quả phòng kiểm nghiệm về muộn).
SAU_XEM = ("kln", "so_phieu_kln", "luu_lo_mau")
SUA = ("ngay", "viec", "ncc_cat", "so_bm0703", "khoi_luong", "thung", "so_ngay_dau", "ly_do_loai", "ve_sinh_thung",
       "ve_sinh_khay", "cam_quan", "nguoi_lam", "ghi_chu")


class SXNhatKyCat(Document):
    def validate(self):
        d = getdate(self.ngay)
        if d > getdate(nowdate()):
            frappe.throw(_("Ngày ghi nhật ký cát không được sau hôm nay."))
        cu = None if self.is_new() else self.get_doc_before_save()
        if cu and cu.get("xem_luc") and not la_iso():
            doi = [f for f in SUA if str(cu.get(f) or "") != str(self.get(f) or "")]
            if doi:
                frappe.throw(_("Dòng ngày {0} Ban ISO đã xem xét — chỉ Ban ISO sửa được (kết quả kim "
                               "loại nặng / lọ mẫu thì vẫn cập nhật được).").format(d.strftime("%d/%m/%Y")),
                             frappe.PermissionError)
        if self.is_new():
            self.nguoi_ghi = frappe.session.user
        if cint(self.so_cu):
            return              # dòng sổ cũ: giữ nguyên số ngày, nguồn, đổi nguồn của nó
        self.kiem_viec(d)
        self.thay_cat = 1 if self.viec == CAT.RANG_KHO else 0
        if self.viec != CAT.RANG_KHO:
            self.so_ngay_dau = 0
        if self.viec != CAT.NHAP:
            self.doi_nguon = 0
        if self.ncc_cat:
            # Nguồn có thể do app điền trong validate (sau bước fetch_from của frappe) → tự lấy tên.
            self.ten_ncc = frappe.db.get_value("Supplier", self.ncc_cat, "supplier_name") or self.ten_ncc
            self.canh_bao_ncc()

    def kiem_viec(self, d):
        v = self.viec
        if v not in CAT.VIEC:
            frappe.throw(_("Chọn việc: nhập cát / rang khô đưa dùng / bổ sung / loại cát / vệ sinh thùng, khay."))
        if v == CAT.NHAP and not self.ncc_cat:
            frappe.throw(_("Nhập cát: chọn nguồn cát (NCC loại Cát rang) — có nguồn thì app mới biết lúc nào "
                           "đổi nguồn để nhắc kiểm kim loại nặng."))
        if v in CAT.CAN_KL and flt(self.khoi_luong) <= 0:
            frappe.throw(_("{0}: ghi khối lượng (kg).").format(v))
        if flt(self.khoi_luong) < 0:
            frappe.throw(_("Khối lượng không được âm."))
        if v == CAT.LOAI and not (self.ly_do_loai or "").strip():
            frappe.throw(_("Loại cát: ghi lý do (đủ số ngày, màu sẫm, khét, vụn cháy, bụi, dính nước / dầu / vật lạ…)."))
        if v == CAT.VE_SINH and not (cint(self.ve_sinh_thung) or cint(self.ve_sinh_khay)):
            frappe.throw(_("Vệ sinh: đánh dấu thùng hay khay (hoặc cả hai)."))
        if cint(self.so_ngay_dau) < 0:
            frappe.throw(_("Số ngày cát đã dùng trước đó không được âm."))
        if v == CAT.RANG_KHO and cint(self.so_ngay_dau) > 0 and self.co_dong_truoc(d):
            frappe.throw(_("Chỉ dòng Rang khô đưa dùng ĐẦU SỔ mới khai số ngày cát đã dùng trước đó — các lần thay "
                           "sau app tự đếm từ 0."))
        if v in CAT.CO_NGUON and v != CAT.NHAP and not self.ncc_cat:
            self.ncc_cat = self.nguon_gan(d) or None
        self.so_ngay_dung = 0
        if v in CAT.DEM or v == CAT.RANG_KHO:
            # Cát đang có trong máy, không kể dòng này (bổ sung không tính lại ngày; loại thì ghi số ngày đã dùng).
            so = CAT.so_ngay(d, bo=self.name)
            if v in CAT.DEM:
                if so is None:
                    frappe.throw(_("Máy chưa có cát đang dùng (chưa ghi lần đưa cát vào, hoặc đã loại) — cát mới "
                                   "đưa vào máy thì chọn \"Rang khô đưa dùng\" (app đếm lại số ngày từ đó)."))
                self.so_ngay_dung = so
            elif so is not None and self.is_new():
                frappe.msgprint(_("Cát cũ trong máy (đã dùng {0} ngày) chưa có dòng Loại cát — ghi thêm dòng Loại "
                                  "cát (số ngày, lý do) cho đủ sổ.").format(so), indicator="orange", alert=True)
        if v == CAT.NHAP:
            truoc = self.nguon_truoc(d)
            self.doi_nguon = 1 if (truoc and self.ncc_cat != truoc) else 0
        elif v in (CAT.RANG_KHO, CAT.BO_SUNG) and self.ncc_cat:
            self.canh_bao_kln()

    def co_dong_truoc(self, d):
        """Sổ đã có lần đưa dùng / dòng sổ cũ trước ngày `d` (thì số ngày đã có chỗ đếm)."""
        return bool(frappe.db.exists(CAT.PT, {"viec": CAT.RANG_KHO, "ngay": ("<", str(d)), "name": ("!=", self.name or "")})
                    or frappe.db.exists(CAT.PT, {"so_cu": 1, "ngay": ("<", str(d))}))

    def nguon_truoc(self, d):
        """Nguồn của lần nhập liền trước dòng này (dòng sổ cũ cũng tính)."""
        k = CAT.xep(dict(self.as_dict(), creation=self.creation or "~"))
        for x in frappe.get_all(CAT.PT, filters={"ngay": ("<=", str(d)), "ncc_cat": ("is", "set"),
                                                 "name": ("!=", self.name or "")},
                                fields=["ngay", "viec", "so_cu", "ncc_cat", "creation"],
                                order_by="ngay desc, creation desc", limit=50):
            if (x.viec == CAT.NHAP or cint(x.so_cu)) and CAT.xep(x) < k:
                return x.ncc_cat
        return ""

    def canh_bao_kln(self):
        """Đưa dùng / bổ sung cát của nguồn vừa đổi mà chưa có kim loại nặng Đạt: HD.08.03 đòi kiểm TRƯỚC khi
        dùng — báo (hộp nhắc đã nhắc mức cao), không chặn: máy rang không dừng chờ phòng kiểm nghiệm."""
        cho = [x for x in frappe.get_all(CAT.PT, filters={"doi_nguon": 1, "ncc_cat": self.ncc_cat},
                                         fields=["ngay", "kln"], order_by="ngay desc", limit=1)
               if x.kln != CAT.KLN_DAT]
        if cho:
            frappe.msgprint(_("Cát nguồn {0} đổi nguồn ngày {1} chưa có kết quả kim loại nặng Đạt — HD.08.03: kiểm "
                              "trước khi dùng.").format(self.ncc_cat, getdate(cho[0].ngay).strftime("%d/%m/%Y")),
                            indicator="orange", alert=True)

    def nguon_gan(self, d):
        x = frappe.get_all(CAT.PT, filters={"viec": CAT.NHAP, "ngay": ("<=", str(d)), "name": ("!=", self.name or "")},
                           fields=["ncc_cat"], order_by="ngay desc, creation desc", limit=1)
        return x[0].ncc_cat if x else ""

    def canh_bao_ncc(self):
        """NCC chưa phân loại Cát rang / chưa duyệt BM.07.02: chỉ báo (W09 — không chặn mua)."""
        try:
            n = frappe.db.get_value("Supplier", self.ncc_cat, ["custom_loai_ncc", "custom_ncc_duyet"],
                                    as_dict=True)
        except Exception:
            return
        if n and (n.custom_loai_ncc != "Cát rang" or not n.custom_ncc_duyet):
            frappe.msgprint(_("Nguồn cát {0} chưa là NCC loại Cát rang được duyệt (BM.07.02) — Ban ISO "
                              "duyệt NCC trên Desk.").format(self.ncc_cat), indicator="orange", alert=True)

    def on_update(self):
        cu = self.get_doc_before_save()
        if self.viec == CAT.NHAP or (cu and cu.get("viec") == CAT.NHAP):
            tu = getdate(self.ngay)
            if cu and cu.get("ngay"):
                tu = min(tu, getdate(cu.ngay))
            tinh_nguon(tu)
        if self.kln == CAT.KLN_HONG and not self.su_co:
            self.lap_su_co()

    def lap_su_co(self):
        ten = self.ten_ncc or self.ncc_cat
        sc = frappe.get_doc({
            "doctype": "SX Su Co", "ngay": getdate(), "nguon": "Nhật ký cát", "loai": "Khác",
            "muc_do": "Cao", "trang_thai": "Mở",
            "mo_ta": _("Cát nguồn {0} (nhập ngày {1}, {2}) KHÔNG ĐẠT kim loại nặng{3}. Ngừng dùng cát này, "
                       "thay cát; xem lại các lô đã rang bằng cát này.").format(
                ten, getdate(self.ngay).strftime("%d/%m/%Y"), self.name,
                _(" — phiếu {0}").format(self.so_phieu_kln) if self.so_phieu_kln else ""),
        })
        if frappe.db.exists("SX QC Cong Doan", "3 Rang"):
            sc.cong_doan = "3 Rang"
        # Người ghi có thể không có quyền tạo phiếu sự cố trên Desk, nhưng cát không đạt
        # PHẢI có phiếu — như lô không đạt xuất xưởng.
        sc.insert(ignore_permissions=True)
        self.db_set("su_co", sc.name, update_modified=False)

    def on_trash(self):
        if self.xem_luc and not la_iso():
            frappe.throw(_("Dòng này Ban ISO đã xem xét — chỉ Ban ISO xoá được."), frappe.PermissionError)

    def after_delete(self):
        if self.viec == CAT.NHAP:
            tinh_nguon(self.ngay)


def tinh_nguon(tu):
    """Đổi nguồn của các dòng nhập cát từ ngày `tu` trở đi tính lại (nhập bù một lần cũ, sửa ngày / nguồn, xoá
    một dòng nhập thì lần nhập sau nó có thể thành / hết đổi nguồn)."""
    truoc = frappe.get_all(CAT.PT, filters={"ngay": ("<", str(getdate(tu))), "ncc_cat": ("is", "set")},
                           fields=["name", "ngay", "viec", "so_cu", "ncc_cat", "creation"],
                           order_by="ngay desc, creation desc")
    goc = next((x for x in truoc if x.viec == CAT.NHAP or cint(x.so_cu)), None)
    sau = frappe.get_all(CAT.PT, filters={"ngay": (">=", str(getdate(tu)))},
                         fields=["name", "ngay", "viec", "so_cu", "ncc_cat", "doi_nguon", "creation"],
                         order_by="ngay asc, creation asc")
    cu = {x.name: cint(x.doi_nguon) for x in sau}
    for n, v in CAT.doi_nguon(([goc] if goc else []) + sau).items():
        if n in cu and cu[n] != v:
            frappe.db.set_value(CAT.PT, n, "doi_nguon", v, update_modified=False)
