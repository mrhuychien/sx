"""Phiếu nhập kho thành phẩm (D56 → D59: phiếu này SINH RA tồn kho TP).

Chấm vào hộp là việc độc lập — nó tính lương khoán, không đụng kho. Thành phẩm chỉ
trở thành tồn kho khi thủ kho DUYỆT phiếu này. Trước đó, trong sổ chưa có hộp nào,
đúng như ngoài đời hộp còn nằm trên bàn chưa ai nhận.

Duyệt sinh tối đa hai chứng từ cho mỗi SKU:
  1. WO + SE Manufacture cho SỐ THEO BẢNG — trừ bột + bao bì theo BOM, nhập TP.
     Dùng số bảng vì nguyên liệu đã tiêu thụ THẬT cho toàn bộ số hộp đã đóng.
  2. SE Material Issue cho PHẦN LỆCH (bảng − đếm) nếu > 0 — lý do "hộp lỗi",
     xuất đúng lô vừa nhập.
Kết quả: tồn Kho TP = số ĐẾM, nguyên liệu trừ = cho số ĐÃ ĐÓNG, số hộp hỏng hiện ra
thành chứng từ có lý do thay vì biến mất khỏi sổ.
"""

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class SXPhieuNhapTP(Document):
    def validate(self):
        tong_dem = tong_lech = 0.0
        for r in self.dong:
            if flt(r.so_dem) < 0:
                frappe.throw(_("Dòng {0}: số đếm không được âm.").format(r.idx))
            # Nhận NHIỀU hơn bảng là dấu hiệu bảng vào hộp ghi sót, không phải hàng
            # từ đâu ra. Sửa bảng rồi lập lại phiếu, đừng nhập bừa vào kho.
            if flt(r.so_dem) > flt(r.so_theo_so) + 1e-6:
                frappe.throw(
                    _("{0}: đếm {1} nhiều hơn bảng vào hộp ({2}). Bảng ghi sót thì "
                      "phải huỷ chốt Vào hộp, sửa bảng rồi lập lại phiếu — nhập quá "
                      "số đã đóng là tự tạo hàng trong sổ.").format(
                        r.ten or r.item, flt(r.so_dem, 0), flt(r.so_theo_so, 0))
                )
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
        self.doi_chieu_bang()
        self.kiem_ton_nguyen_lieu()
        self.nguoi_duyet = frappe.session.user
        self.duyet_luc = now_datetime()
        self.trang_thai = "Đã duyệt"

    def doi_chieu_bang(self):
        """Cột "Theo bảng" phải KHỚP bảng vào hộp tại THỜI ĐIỂM DUYỆT (D60).

        Phiếu được phép lập khi bảng chưa chốt, nên giữa lúc lập và lúc duyệt QC có
        thể đã chấm thêm hoặc sửa. Duyệt theo số cũ nghĩa là Work Order chạy sai số
        và nguyên liệu trừ sai — mà không ai phát hiện, vì phiếu vẫn "đẹp".
        Chặn ở đây và chỉ thẳng nút Làm mới, thay vì cấm lập phiếu sớm.
        """
        from sx.api.khotp import _con_lai

        con, bang = _con_lai(self.ngay_sx)
        if not bang:
            frappe.throw(_("Ngày {0} không còn bảng vào hộp.").format(self.ngay_sx))
        lech = []
        for r in self.dong:
            gio = flt(con.get(r.item, 0))
            if abs(gio - flt(r.so_theo_so)) > 1e-6:
                lech.append(_("• {0}: phiếu ghi {1}, bảng hiện tại còn {2}").format(
                    r.ten or r.item, flt(r.so_theo_so, 0), flt(gio, 0)))
        for item, so in con.items():
            if not any(r.item == item for r in self.dong):
                lech.append(_("• {0}: bảng có thêm {1}, phiếu chưa có dòng này").format(
                    item, flt(so, 0)))
        if lech:
            frappe.throw(
                _("Bảng vào hộp đã thay đổi từ lúc lập phiếu:") + "<br>"
                + "<br>".join(lech)
                + "<br><br>" + _("Bấm LÀM MỚI SỐ THEO BẢNG rồi đếm lại phần chênh.")
            )

    def kiem_ton_nguyen_lieu(self):
        """Kiểm đủ bột + bao bì TRƯỚC khi sinh chứng từ (D59).

        Đây mới là lúc nguyên liệu bị trừ, nên kiểm ở đây chứ không phải lúc chốt
        ngày. Cộng dồn nhu cầu rồi đối chiếu MỘT LẦN cho mỗi (item, kho): kiểm từng
        dòng riêng lẻ là sai — 4 SKU cùng cần 100 kg bột, tồn 100 thì cả 4 lần kiểm
        đều "đủ", duyệt qua rồi mới vỡ ở bước sinh phiếu kho.
        """
        from sx.api.chot import _kho_nguon as kho_nguon_rm
        from sx.api.chot import _nhu_cau_bom
        from sx.utils import cho_phep_ton_am, get_bom_active, get_settings

        settings = get_settings()
        can = {}
        for r in self.dong:
            if flt(r.so_theo_so) <= 0:
                continue
            bom = get_bom_active(r.item)
            if not bom:
                frappe.throw(_("Sản phẩm {0} chưa có BOM active.").format(r.item))
            for item_code, so in _nhu_cau_bom(bom, flt(r.so_theo_so)).items():
                kho = kho_nguon_rm(item_code, settings)
                can[(item_code, kho)] = can.get((item_code, kho), 0) + flt(so)

        thieu = []
        for (item_code, kho), so in sorted(can.items()):
            ton = flt(frappe.db.get_value(
                "Bin", {"item_code": item_code, "warehouse": kho}, "actual_qty"))
            if ton + 1e-6 < so:
                thieu.append(_("• {0} tại {1}: cần {2}, tồn {3} → THIẾU {4}").format(
                    item_code, kho, flt(so, 3), flt(ton, 3), flt(so - ton, 3)))
        if not thieu:
            return

        # Thiếu bột thường là do chưa chốt Ghi sổ hôm đó — chỉ thẳng ra, đừng để
        # thủ kho ngồi đoán vì sao "không đủ tồn".
        goi_y = _("\n\nThường là do ngày {0} chưa chốt GHI SỔ — mẻ trộn/nấu chưa "
                  "sinh nên bột chưa vào kho. Nhờ QC chốt Ghi sổ rồi duyệt lại."
                  ).format(frappe.utils.formatdate(self.ngay))
        if cho_phep_ton_am():
            # Site bật Allow Negative Stock -> chặn ở đây là vô nghĩa (ERPNext bên
            # dưới cho ghi âm rồi). Vẫn phải NÓI, để không âm kho mà không ai biết.
            frappe.msgprint(
                _("⚠ Kho đang cho phép tồn âm — vẫn duyệt nhưng các mục sau bị ghi âm:")
                + "<br>" + "<br>".join(thieu), indicator="orange", alert=False)
            return
        frappe.throw(_("Không đủ nguyên liệu để nhập kho:") + "<br>"
                     + "<br>".join(thieu) + goi_y.replace("\n", "<br>"))

    def on_submit(self):
        from sx.api.chot import _kho_nguon as kho_nguon_rm
        from sx.api.mfg import tao_batch, tao_se_manufacture, tao_se_xuat_huy, tao_wo
        from sx.utils import get_bom_active, get_settings, sinh_ma_lo

        settings = get_settings()
        chung_tu = []
        for r in self.dong:
            da_dong = flt(r.so_theo_so)
            if da_dong <= 0:
                continue
            bom = get_bom_active(r.item)
            if not bom:
                frappe.throw(_("Sản phẩm {0} chưa có BOM active.").format(r.item))

            batch = tao_batch(r.item, sinh_ma_lo(r.item, self.ngay), ngay_sx=self.ngay_sx)
            wo = tao_wo(
                settings.cong_ty, r.item, da_dong, bom,
                source_wh=settings.kho_nvl, fg_wh=self.kho_dich,
                ngay_sx=self.ngay_sx, planned_date=self.ngay,
            )
            se = tao_se_manufacture(
                wo, da_dong, batch,
                kho_nguon=lambda item: kho_nguon_rm(item, settings),
                ngay=self.ngay, ngay_sx=self.ngay_sx,
            )
            chung_tu.append({"dt": "Work Order", "name": wo.name})
            chung_tu.append({"dt": "Stock Entry", "name": se.name})

            hong = da_dong - flt(r.so_dem)
            if hong > 1e-6:
                xh = tao_se_xuat_huy(
                    settings.cong_ty, r.item, hong, self.kho_dich, ngay=self.ngay,
                    ghi_chu=_("Hộp lỗi — thủ kho không nhận (phiếu {0}){1}").format(
                        self.name, f" · {r.ghi_chu}" if r.ghi_chu else ""),
                    batch=batch, ngay_sx=self.ngay_sx,
                )
                chung_tu.append({"dt": "Stock Entry", "name": xh.name})

        self.db_set("ds_se", json.dumps(chung_tu), update_modified=False)

    def on_cancel(self):
        """Huỷ phiếu = thu hồi ĐÚNG những chứng từ do phiếu này sinh ra, đảo thứ tự
        (xuất huỷ trước, rồi SE nhập, rồi WO) để không có bước nào rút hàng chưa có."""
        from sx.api.mfg import cancel_doc

        log = []
        for ct in reversed(json.loads(self.ds_se or "[]")):
            cancel_doc(ct.get("dt"), ct.get("name"), log)
        self.db_set("trang_thai", "Đã huỷ", update_modified=False)
        if log:
            ghi = (self.ghi_chu or "") + "\n[Huỷ phiếu] " + "; ".join(log)
            self.db_set("ghi_chu", ghi.strip(), update_modified=False)
