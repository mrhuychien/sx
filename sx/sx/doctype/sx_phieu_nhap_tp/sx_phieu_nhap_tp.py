"""Phiếu nhập kho thành phẩm — chứng từ ĐỘC LẬP sinh ra tồn kho TP (D62).

Không liên quan gì tới bảng vào hộp: bảng chấm công cho từng người để tính lương
khoán, phiếu này ghi hàng thật chuyển vào kho. Hai việc, hai người, hai thời điểm.

Thành phẩm chỉ trở thành tồn kho khi thủ kho DUYỆT phiếu này. Trước đó trong sổ
chưa có hộp nào — đúng như ngoài đời, hộp còn nằm trên bàn chưa ai nhận.

Duyệt sinh WO + SE Manufacture theo SỐ THỦ KHO ĐẾM: trừ bột + bao bì theo BOM,
nhập thành phẩm vào Kho TP. Số đếm là số duy nhất quyết định — hàng đã qua bước
kiểm đếm thực tế rồi mới kéo vào kho. Cột "Theo bảng" chỉ để đối chiếu.

Phần chưa nhận KHÔNG bị xoá sổ: nó vẫn hiện ở danh sách chờ lập phiếu cho tới khi
nhận nốt. Phần lớn trường hợp đó chỉ là "chưa chuyển hết", còn nằm ở xưởng chờ
chuyến sau — tự động coi là hộp lỗi rồi xuất huỷ là phá hàng còn tốt.
"""

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime


def _tong_tu_uom(chi_tiet, mac_dinh):
    """Σ (số lượng × hệ số) từ JSON chi tiết ĐVT. Không có chi tiết -> giữ số cũ."""
    if not chi_tiet:
        return flt(mac_dinh)
    try:
        ds = json.loads(chi_tiet)
    except (ValueError, TypeError):
        return flt(mac_dinh)
    if not isinstance(ds, list) or not ds:
        return flt(mac_dinh)
    return flt(sum(flt(d.get("sl")) * flt(d.get("he_so") or 1) for d in ds))


class SXPhieuNhapTP(Document):
    def validate(self):
        tong_dem = tong_lech = 0.0
        for r in self.dong:
            # Có chi tiết ĐVT thì TÍNH LẠI tổng từ nó, không tin con số client gửi:
            # đây là số vào sổ kho, mà phép nhân hệ số quy đổi thì để server làm.
            # .get() chứ không .lap_uom: site chưa migrate thì field chưa có trong
            # meta và truy cập thẳng là AttributeError -> 500 trống trơn.
            r.so_lap = _tong_tu_uom(r.get("lap_uom"), r.so_lap)
            r.so_dem = _tong_tu_uom(r.get("dem_uom"), r.so_dem)
            if flt(r.so_dem) < 0:
                frappe.throw(_("Dòng {0}: số đếm không được âm.").format(r.idx))
            r.lech = flt(r.so_dem) - flt(r.so_lap)
            tong_dem += flt(r.so_dem)
            tong_lech += flt(r.lech)
        self.tong_dem = tong_dem
        self.tong_lech = tong_lech
        if self.docstatus == 0:
            self.trang_thai = "Nháp"

    def before_submit(self):
        if not any(flt(r.so_dem) > 0 for r in self.dong):
            frappe.throw(_("Chưa có dòng nào đếm được số > 0 — không duyệt phiếu rỗng."))
        self.kiem_tran_da_cham()
        self.kiem_ton_nguyen_lieu()
        self.nguoi_duyet = frappe.session.user
        self.duyet_luc = now_datetime()
        self.trang_thai = "Đã duyệt"

    def kiem_tran_da_cham(self):
        """Không nhập quá số đã CHẤM VÀO HỘP (D70).

        Kiểm lại lúc DUYỆT chứ không chỉ lúc tải: giữa lúc tải và lúc duyệt có thể
        đã có phiếu khác nhận bớt, hoặc QC sửa bảng xuống. Chỉ chặn khi VƯỢT — nhận
        thiếu là chuyện bình thường (chưa chuyển hết).

        Dòng nào mã hàng không xuất hiện trong bảng vào hộp thì BỎ QUA kiểm: phiếu
        nhập kho là chứng từ độc lập, vẫn cho nhập hàng không qua chấm công (vd hàng
        làm bù, hàng trả về) — chỉ là không có trần để đối chiếu.
        """
        from frappe.utils import add_days

        from sx.api.khotp import tran_con_lai

        den = getdate(self.ngay)
        con = tran_con_lai(add_days(den, -30), den, self.name)
        vuot = []
        for r in self.dong:
            if r.item not in con:
                continue
            if flt(r.so_dem) > flt(con[r.item]) + 1e-6:
                vuot.append(_("• {0}: nhận {1}, còn được nhập {2}").format(
                    r.ten or r.item, flt(r.so_dem, 0), flt(con[r.item], 0)))
        if vuot:
            frappe.throw(
                _("Nhận quá số đã chấm vào hộp:") + "<br>" + "<br>".join(vuot)
                + "<br><br>" + _("Chấm thiếu thì sửa bảng vào hộp rồi bấm TẢI LẠI; "
                                 "hàng không qua chấm công thì bỏ dòng này ra và lập "
                                 "phiếu riêng.")
            )

    def kiem_ton_nguyen_lieu(self):
        """Kiểm đủ bột + bao bì TRƯỚC khi sinh chứng từ (D59).

        Đây là lúc nguyên liệu bị trừ nên kiểm ở đây. Cộng dồn nhu cầu rồi đối
        chiếu MỘT LẦN cho mỗi (item, kho): kiểm từng dòng riêng lẻ là sai — 4 SKU
        cùng cần 100 kg bột, tồn 100 thì cả 4 lần kiểm đều "đủ", duyệt qua rồi mới
        vỡ ở bước sinh phiếu kho.
        """
        from sx.api.chot import _kho_nguon as kho_nguon_rm
        from sx.api.chot import _nhu_cau_bom
        from sx.utils import cho_phep_ton_am, get_bom_active, get_settings

        settings = get_settings()
        can = {}
        for r in self.dong:
            if flt(r.so_dem) <= 0:
                continue
            bom = get_bom_active(r.item)
            if not bom:
                frappe.throw(_("Sản phẩm {0} chưa có BOM active.").format(r.item))
            for item_code, so in _nhu_cau_bom(bom, flt(r.so_dem)).items():
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
        goi_y = _("\n\nThường là do chưa chốt GHI SỔ hôm nay — mẻ trộn/nấu chưa "
                  "sinh nên bột chưa vào kho. Nhờ QC chốt Ghi sổ rồi duyệt lại.")
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
        """Duyệt = SINH TỒN KHO theo SỐ THỦ KHO ĐẾM.

        Số đếm là số duy nhất quyết định: hàng đã qua bước kiểm đếm thực tế rồi mới
        kéo vào kho. Cột "Số lập phiếu" chỉ để đối chiếu — chỗ lệch giữa hai số là
        thứ đáng xem, không phải thứ để chặn.
        """
        from sx.api.chot import _kho_nguon as kho_nguon_rm
        from sx.api.mfg import tao_batch, tao_se_manufacture, tao_wo
        from sx.utils import get_bom_active, get_settings, sinh_ma_lo

        settings = get_settings()
        chung_tu = []
        for r in self.dong:
            nhan = flt(r.so_dem)
            if nhan <= 0:
                continue
            bom = get_bom_active(r.item)
            if not bom:
                frappe.throw(_("Sản phẩm {0} chưa có BOM active.").format(r.item))

            # Mã lô sinh theo NGÀY NHẬN — truy xuất NGÀY × LOẠI (D3) vẫn nguyên,
            # không cần bám vào phiếu ngày sản xuất nào.
            batch = tao_batch(r.item, sinh_ma_lo(r.item, self.ngay))
            wo = tao_wo(
                settings.cong_ty, r.item, nhan, bom,
                source_wh=settings.kho_nvl, fg_wh=self.kho_dich,
                planned_date=self.ngay,
            )
            se = tao_se_manufacture(
                wo, nhan, batch,
                kho_nguon=lambda item: kho_nguon_rm(item, settings),
                ngay=self.ngay,
            )
            chung_tu.append({"dt": "Work Order", "name": wo.name})
            chung_tu.append({"dt": "Stock Entry", "name": se.name})

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
