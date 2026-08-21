"""Phiếu nhập kho thành phẩm (D56) — thủ kho KIỂM rồi DUYỆT mới vào kho.

Vì sao phải có phiếu nháp thay vì ghi thẳng như D51:
Sản lượng do QC ghi (bảng vào hộp) và số thủ kho ĐẾM là hai con số của hai người,
và chúng được phép lệch nhau — hộp lỗi bị loại, hộp còn trên bàn chưa xếp pallet,
đếm sai. Chính chỗ lệch đó là thông tin duy nhất phát hiện hao hụt. Phiếu nháp cho
thủ kho thời gian đi đếm thật rồi mới ký; ghi thẳng thì không ai kiểm ai.

Số vào sổ kho là `so_dem` — KHÔNG phải `so_theo_so`. `so_theo_so` chỉ là ảnh chụp
tồn ở kho chờ nhận lúc lập phiếu, để đối chiếu.
"""

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class SXPhieuNhapTP(Document):
    def validate(self):
        if self.kho_nguon == self.kho_dich:
            frappe.throw(
                _("Kho chờ nhận và Kho TP đang là một ({0}) — không có gì để "
                  "chuyển. Sửa ở SX Settings → Kho nhận TP từ tầng 3.").format(self.kho_dich)
            )
        tong_dem = tong_lech = 0.0
        for r in self.dong:
            if flt(r.so_dem) < 0:
                frappe.throw(_("Dòng {0}: số đếm không được âm.").format(r.idx))
            r.lech = flt(r.so_dem) - flt(r.so_theo_so)
            tong_dem += flt(r.so_dem)
            tong_lech += flt(r.lech)
        self.tong_dem = tong_dem
        self.tong_lech = tong_lech
        if self.docstatus == 0:
            self.trang_thai = "Nháp"

    def before_submit(self):
        if not any(flt(r.so_dem) > 0 for r in self.dong):
            frappe.throw(_("Chưa có dòng nào đếm được số > 0 — không duyệt phiếu rỗng."))
        self.nguoi_duyet = frappe.session.user
        self.duyet_luc = now_datetime()
        self.trang_thai = "Đã duyệt"

    def on_submit(self):
        """Duyệt = sinh phiếu kho THẬT. Mỗi item một Stock Entry Material Transfer."""
        from sx.api.mfg import tao_se_chuyen_kho
        from sx.utils import get_settings

        settings = get_settings()
        ds_se = []
        for r in self.dong:
            sl = flt(r.so_dem)
            if sl <= 0:
                continue
            ton = flt(frappe.db.get_value(
                "Bin", {"item_code": r.item, "warehouse": self.kho_nguon}, "actual_qty"))
            # Kiểm LẠI lúc duyệt, không tin số lúc lập: giữa lúc lập và lúc duyệt
            # có thể đã có phiếu khác lấy hàng đi.
            if sl > ton + 1e-6:
                frappe.throw(
                    _("{0}: kho chờ nhận chỉ còn {1}, không nhận {2} được. "
                      "Đếm lại hoặc kiểm tra phiếu nhận khác đã lấy hàng.").format(
                        r.ten or r.item, flt(ton, 0), flt(sl, 0))
                )
            se = tao_se_chuyen_kho(
                settings.cong_ty, r.item, sl,
                kho_di=self.kho_nguon, kho_den=self.kho_dich, ngay=self.ngay,
                ghi_chu=_("Thủ kho nhận TP — phiếu {0}").format(self.name),
                cong_doan="nhaptp",
            )
            ds_se.append(se.name)
        self.db_set("ds_se", json.dumps(ds_se), update_modified=False)

    def on_cancel(self):
        """Huỷ phiếu = thu hồi đúng những phiếu kho do phiếu này sinh ra."""
        from sx.api.mfg import cancel_doc

        log = []
        for name in json.loads(self.ds_se or "[]"):
            cancel_doc("Stock Entry", name, log)
        self.db_set("trang_thai", "Đã huỷ", update_modified=False)
        if log:
            ghi = (self.ghi_chu or "") + "\n[Huỷ phiếu] " + "; ".join(log)
            self.db_set("ghi_chu", ghi.strip(), update_modified=False)
