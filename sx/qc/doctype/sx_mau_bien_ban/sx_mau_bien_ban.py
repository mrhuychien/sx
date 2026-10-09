"""Mẫu biên bản (W45, D174) — các phần theo thứ tự in, ô ký theo thứ tự ký, vai lập / xem. Luật ở sx/qc/bien_ban.py.
Chặn ở đây nên chặn cả Desk: khóa phần, khóa cột hợp lệ; kiểu phần, kiểu cột đúng; Việc giao đủ cột viec / phu_trach /
han; hàm kéo, hàm tính phải có tên trong code (không chạy biểu thức người gõ); mỗi ô ký có người ký được.
Biên bản đã lập giữ bản chụp các phần lúc lập — sửa mẫu không làm đổi biên bản cũ."""

import frappe
from frappe import _
from frappe.model.document import Document

from sx.qc import bien_ban as BB


class SXMauBienBan(Document):
    def before_insert(self):
        # autoname = field:ma đặt tên TRƯỚC validate — chuẩn hoá ở đây (như SX So).
        self.ma = (self.ma or "").strip().upper()

    def validate(self):
        self.ma = (self.ma or "").strip().upper()
        self.ten = (self.ten or "").strip()
        self.nhan_ngay = (self.nhan_ngay or "").strip() or "Ngày"
        for p in self.get("phan") or []:
            p.key = (p.key or "").strip()
            for f in ("nguon", "tinh", "chi_khi"):
                setattr(p, f, (p.get(f) or "").strip() or None)
        loi = BB.loi_mau(BB.mau_tu_doc(self))
        if loi:
            frappe.throw(_("Mẫu biên bản {0}: {1}").format(self.ma, " ".join(loi)))
