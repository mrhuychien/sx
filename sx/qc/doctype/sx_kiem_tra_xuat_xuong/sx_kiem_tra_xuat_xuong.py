"""Phiếu kiểm tra xuất xưởng BM.08.04 — một lô thành phẩm (W08, D137; lần BH 01: W31, D159).

Luồng: Nháp (QC chấm mục) → Chờ duyệt (QC gửi) → Đã duyệt | Trả lại (Trưởng Ban ISO /
người được giao). Luật nằm ở đây nên chặn cả đường Desk:
  · gửi duyệt phải chấm đủ mục A1–A5, đủ 5 mẫu B1–B6, có kết luận; "Cho xuất xưởng" mà có mục
    Không đạt → chặn (sx/qc/xuat_xuong.can_ket_luan);
  · duyệt / trả lại chỉ người có quyền (sx/qc/quyen.py) và KHÔNG phải QC đã kiểm lô đó
    (tài liệu 08/10: người duyệt không phải QC đã kiểm) — kể cả khi người đó là Ban ISO;
  · phiếu đã duyệt thì khoá — chỉ người có quyền duyệt mới sửa / thu hồi duyệt;
  · mỗi lô một phiếu đang hiệu lực. Phiếu Đã duyệt "Giữ lại chờ xử lý" không chặn phiếu kiểm
    lại sau xử lý; "Không cho xuất" thì chặn — lô huỷ, không rework (QT.15).
"Giữ lại" / "Không cho xuất" → luôn có phiếu sự cố BM.08.02: QC chọn phiếu có sẵn, không thì
app lập lúc gửi duyệt (nguồn Kiểm tra xuất xưởng; Không cho xuất mức Cao).
Ô ký Quản lý sản xuất (W31) xoá khi phiếu quay lại sửa — chữ ký không đứng trên nội dung đã đổi.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

from sx.qc import xuat_xuong as XX
from sx.qc.quyen import duoc_duyet_xuat_xuong


class SXKiemTraXuatXuong(Document):
    def validate(self):
        if self.san_pham and not self.ten_san_pham:
            self.ten_san_pham = frappe.db.get_value("Item", self.san_pham, "item_name") or self.san_pham
        if not self.get("ds_muc"):
            for ma, nd, yc in XX.MUC:
                self.append("ds_muc", {"ma": ma, "noi_dung": nd, "yeu_cau": yc})
        if XX.la_moi(self.ds_muc):
            self.so_mau = XX.SO_MAU
        if self.ket_luan in XX.KET_LUAN_CU:
            self.ket_luan = XX.kl(self.ket_luan)
        if self.san_pham and self.hsd and not self.batch:
            ds = frappe.get_all("Batch", filters={"item": self.san_pham, "expiry_date": getdate(self.hsd)},
                                pluck="name", order_by="creation asc", limit=1)
            self.batch = ds[0] if ds else None
        cu = None if self.is_new() else self.get_doc_before_save()
        tt_cu = cu.trang_thai if cu else None
        if tt_cu == XX.DUYET and not duoc_duyet_xuat_xuong():
            frappe.throw(_("Phiếu đã duyệt — chỉ Trưởng Ban ISO / người được giao sửa được."),
                         frappe.PermissionError)
        if self.is_new():
            if self.trang_thai != XX.NHAP:
                frappe.throw(_("Phiếu mới phải bắt đầu ở trạng thái Nháp."))
        elif self.trang_thai != tt_cu:
            self.doi_trang_thai(tt_cu)
        self.kiem_trung()

    def kiem_trung(self):
        """Mỗi lô một phiếu đang hiệu lực."""
        if self.trang_thai == XX.DUYET and XX.kl(self.ket_luan) == XX.GIU_LAI:
            return
        for x in frappe.get_all(XX.PT, filters={"san_pham": self.san_pham, "hsd": getdate(self.hsd),
                                               "name": ("!=", self.name or "")},
                                fields=["name", "trang_thai", "ket_luan"]):
            if x.trang_thai == XX.DUYET and XX.kl(x.ket_luan) == XX.GIU_LAI:
                continue
            if x.trang_thai == XX.DUYET and XX.kl(x.ket_luan) == XX.KHONG_XUAT:
                frappe.throw(_("Lô này đã kết luận Không cho xuất (phiếu {0}) — lô huỷ, không kiểm lại. "
                               "Duyệt nhầm thì Trưởng Ban ISO thu hồi duyệt phiếu đó.").format(x.name))
            frappe.throw(_("Lô này đã có phiếu {0} ({1}) — mở phiếu đó, đừng lập phiếu thứ hai.")
                         .format(x.name, XX.mo_ta(x)))

    def doi_trang_thai(self, tt_cu):
        tt, ai = self.trang_thai, frappe.session.user
        if tt == XX.CHO:
            if tt_cu not in (XX.NHAP, XX.TRA):
                frappe.throw(_("Chỉ gửi duyệt phiếu đang Nháp / bị Trả lại."))
            loi = XX.can_ket_luan(self)
            if loi:
                frappe.throw(_("Chưa gửi duyệt được:") + "<br>" + "<br>".join(f"• {x}" for x in loi))
            self.qc_kiem, self.kiem_luc = ai, now_datetime()
            self.nguoi_duyet = self.duyet_luc = None
        elif tt in (XX.DUYET, XX.TRA):
            if tt_cu != XX.CHO:
                frappe.throw(_("Chỉ duyệt / trả lại phiếu đang chờ duyệt."))
            if not duoc_duyet_xuat_xuong():
                frappe.throw(_("Chỉ Trưởng Ban ISO hoặc người được giao mới duyệt phiếu kiểm tra "
                               "xuất xưởng."), frappe.PermissionError)
            if self.qc_kiem and self.qc_kiem == ai:
                frappe.throw(_("Người đã kiểm lô này không tự duyệt được — nhờ Trưởng Ban ISO / "
                               "người được giao khác."), frappe.PermissionError)
            if tt == XX.TRA and not (self.y_kien_duyet or "").strip():
                frappe.throw(_("Trả lại thì ghi ý kiến cho QC biết kiểm lại gì."))
            self.nguoi_duyet, self.duyet_luc = ai, now_datetime()
            if tt == XX.TRA:
                self.qlsx = self.qlsx_luc = None
        elif tt == XX.NHAP:
            if tt_cu == XX.DUYET:
                # Thu hồi duyệt (duyệt nhầm): đã qua cửa khoá ở validate → người có quyền.
                if not (self.y_kien_duyet or "").strip():
                    frappe.throw(_("Thu hồi duyệt thì ghi lý do vào Ý kiến người duyệt."))
            self.nguoi_duyet = self.duyet_luc = None
            self.qlsx = self.qlsx_luc = None

    def on_update(self):
        k = XX.kl(self.ket_luan)
        if self.trang_thai in (XX.CHO, XX.DUYET) and k in (XX.GIU_LAI, XX.KHONG_XUAT) and not self.su_co:
            self.lap_su_co(k)

    def lap_su_co(self, k):
        """BM.08.02 cho lô Giữ lại / Không cho xuất — số phiếu ghi ngay vào kết luận như bản giấy."""
        hsd = getdate(self.hsd).strftime("%d/%m/%Y")
        hong = [f"{r.ma} {(r.noi_dung or '')[:60]}" for r in self.ds_muc if r.ket_qua == XX.KHONG_DAT]
        sc = frappe.get_doc({
            "doctype": "SX Su Co", "ngay": getdate(), "nguon": "Kiểm tra xuất xưởng",
            "loai": "Khác", "muc_do": "Cao" if k == XX.KHONG_XUAT else "Thường", "trang_thai": "Mở",
            "mo_ta": _("Lô {0} HSD {1} — {2} (kiểm tra xuất xưởng {3}){4}{5}").format(
                self.ten_san_pham or self.san_pham, hsd, k.upper(), self.name,
                (": " + "; ".join(hong)) if hong else "",
                (". " + self.ghi_chu.strip()) if (self.ghi_chu or "").strip() else "")[:1000],
            "lo_anh_huong": _("{0} HSD {1}").format(self.ten_san_pham or self.san_pham, hsd)[:140],
            "so_luong": f"{self.so_luong or ''} {self.dvt or ''}".strip(),
        })
        if self.batch:
            sc.append("ds_lo", {"batch": self.batch})
        # Người gửi / người duyệt có thể không có quyền tạo phiếu sự cố trên Desk, nhưng lô giữ
        # lại / không cho xuất PHẢI có phiếu — như vòng kiểm / tiếp nhận NL sinh phiếu.
        sc.insert(ignore_permissions=True)
        self.db_set("su_co", sc.name, update_modified=False)
