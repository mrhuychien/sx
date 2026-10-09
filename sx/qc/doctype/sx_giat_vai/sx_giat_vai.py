"""Một việc trong sổ giặt vải ủ BM.08.05 (W29, D163). Luật tính ở sx/qc/vai_u.py.

Chặn ở đây nên chặn cả đường Desk:
  · không ghi trước ngày; thiếu mã vải / số lượng, người làm, lý do (giặt ngoài lịch, loại vải) → chặn;
  · số phút đun sôi do app tính (giờ vớt − giờ sôi lại);
  · dòng đã QC ký phải đủ điều kiện ký — giặt: đun ≥ 10 phút, có chỗ phơi, giờ cất;
  · dòng đã QC ký hoặc Trưởng Ban ISO đã xem thì khoá — chỉ Ban ISO sửa / xoá;
  · không giặt vải đã loại; không loại hai lần; không nhập đè mã của vải còn đang có;
  · nhập vải mới / loại vải → danh mục SX Vai U theo dòng mới nhất (Dự phòng / Đã loại, không xoá vải).
    Sửa, xoá dòng thì danh mục tính lại.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, nowdate

from sx.qc import vai_u as VU
from sx.qc.quyen import la_iso

# Nội dung dòng — khoá sau khi QC ký / Ban ISO xem.
SUA = ("ngay", "viec", "so_luong", "ly_do", "gio_soi_lai", "gio_vot", "phoi_tai", "cat_luc", "nguoi_lam", "su_co")


def _ma(doc):
    return [r.get("vai") for r in (doc.get("vai") or []) if r.get("vai")]


def _x(doc):
    return dict(doc.as_dict(), vai=_ma(doc))


def _gt(f, v):
    """Giá trị để so "có đổi không": DB trả ô Time là timedelta, màn gửi "07:05" — cùng một giờ."""
    if f in ("gio_soi_lai", "gio_vot"):
        return VU.gio(v)
    if f == "ngay":
        return str(getdate(v)) if v else ""
    if f == "cat_luc":
        return str(v or "").replace("T", " ")[:16]
    if f == "so_luong":
        return cint(v)
    return str(v or "")


class SXGiatVai(Document):
    def validate(self):
        ma = _ma(self)
        loi = VU.loi_dong(_x(self), nowdate())
        if loi:
            frappe.throw(_(loi))
        trung = sorted({m for m in ma if ma.count(m) > 1})
        if trung:
            frappe.throw(_("Mã vải {0} ghi hai lần trong một dòng.").format(", ".join(trung)))
        self.so_phut = VU.so_phut(self.gio_soi_lai, self.gio_vot)
        cu = None if self.is_new() else self.get_doc_before_save()
        if cu and (cu.get("qc_ky_luc") or cu.get("xem_luc")) and not la_iso():
            doi = [f for f in SUA if _gt(f, cu.get(f)) != _gt(f, self.get(f))]
            if doi or _ma(cu) != ma:
                frappe.throw(_("Dòng ngày {0} đã {1} — chỉ Ban ISO sửa được.").format(
                    getdate(self.ngay).strftime("%d/%m/%Y"),
                    _("QC ký") if cu.get("qc_ky_luc") else _("được Trưởng Ban ISO xem")), frappe.PermissionError)
        if self.qc_ky_luc:
            loi = VU.loi_ky(_x(self))
            if loi:
                frappe.throw(_(loi))
        if self.is_new() and not self.ghi_boi:
            self.ghi_boi = frappe.session.user
        self.kiem_vai(ma)

    def kiem_vai(self, ma):
        """Vải trong dòng phải hợp với trạng thái của nó trong danh mục."""
        for m in ma:
            v = frappe.db.get_value(VU.VAI, m, ["trang_thai", "ngay_loai", "dong_loai", "dong_nhap"], as_dict=True)
            if not v:
                frappe.throw(_("Vải {0} chưa có trong danh mục — QLSX / Ban ISO khai ở tab Danh mục vải.").format(m))
            loai = v.trang_thai == VU.DA_LOAI
            ngay_loai = getdate(v.ngay_loai).strftime("%d/%m/%Y") if v.ngay_loai else ""
            # Cùng ngày thì được: ngày giặt định kỳ thấy vải rách → giặt cả mẻ rồi loại vải đó.
            if self.viec in VU.GIAT and loai and (not v.ngay_loai or getdate(self.ngay) > getdate(v.ngay_loai)):
                frappe.throw(_("Vải {0} đã loại ngày {1} — không giặt vải đã loại. Vải thay mới khâu lại mã này "
                               "thì ghi dòng Nhập vải mới trước.").format(m, ngay_loai))
            if self.viec == VU.LOAI and loai and v.dong_loai != self.name:
                frappe.throw(_("Vải {0} đã loại ngày {1} (dòng {2}).").format(m, ngay_loai, v.dong_loai or "—"))
            if (self.viec == VU.NHAP and v.dong_nhap != self.name
                    and (v.trang_thai == VU.DANG_DUNG or (v.trang_thai == VU.DU_PHONG and v.dong_nhap))):
                frappe.throw(_("Vải {0} đang có trong danh mục ({1}) — vải thay mới cùng mã chỉ nhập sau khi vải "
                               "cũ đã loại (ghi dòng Loại vải trước).").format(m, v.trang_thai.lower()))

    def on_update(self):
        cu = self.get_doc_before_save()
        if self.viec in (VU.NHAP, VU.LOAI) or (cu and cu.get("viec") in (VU.NHAP, VU.LOAI)):
            VU.tinh_vai(_ma(self) + (_ma(cu) if cu else []))

    def on_trash(self):
        if (self.qc_ky_luc or self.xem_luc) and not la_iso():
            frappe.throw(_("Dòng này đã {0} — chỉ Ban ISO xoá được.").format(
                _("QC ký") if self.qc_ky_luc else _("được Trưởng Ban ISO xem")), frappe.PermissionError)

    def after_delete(self):
        if self.viec in (VU.NHAP, VU.LOAI):
            VU.tinh_vai(_ma(self))
