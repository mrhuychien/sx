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
from frappe.utils import add_days, cint, flt, getdate, now_datetime


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


def hsd_goi_y(item, ngay):
    """HSD mặc định = ngày nhập + "Shelf Life In Days" của mã hàng (D114).

    None khi mã hàng chưa khai số ngày — KHÔNG bịa: thủ kho gõ tay theo bao bì,
    hoặc quản lý khai Shelf Life trên Item một lần là các phiếu sau tự điền.
    """
    so_ngay = cint(frappe.get_cached_value("Item", item, "shelf_life_in_days"))
    if so_ngay <= 0 or not ngay:
        return None
    return str(add_days(getdate(ngay), so_ngay))


def _gia_von_tam(item, kho):
    """Đơn giá cho hàng nhập tạm: giá vốn đang chạy ở kho → Item.valuation_rate → 0.

    KHÔNG bịa giá. 0 nghĩa là lô này vào kho giá trị 0 cho tới khi hạch toán bù —
    ghi rõ trên SX No BOM để kế toán biết lô nào đang lệch giá.
    """
    gia = flt(frappe.db.get_value("Bin", {"item_code": item, "warehouse": kho},
                                  "valuation_rate"))
    if not gia:
        gia = flt(frappe.db.get_value("Item", item, "valuation_rate"))
    return gia


def _ghi_no_bom(phieu, r, so_luong, batch, se_nhap, gia):
    no = frappe.get_doc({
        "doctype": "SX No BOM",
        "item": r.item,
        "ten": r.ten or r.item,
        "so_luong": so_luong,
        "dvt": r.dvt or "",
        "ngay": phieu.ngay,
        "phieu_nhap": phieu.name,
        "dong_idx": r.idx,
        "se_nhap": se_nhap,
        "batch": batch,
        "kho": phieu.kho_dich,
        "gia_tam": gia,
        "trang_thai": "Chờ BOM",
    })
    # Thủ kho duyệt phiếu không có quyền tạo trên sổ nợ — nhưng hệ thống PHẢI ghi
    # được. Không ghi được thì hàng vào kho mà khoản nợ nguyên liệu biến mất.
    no.insert(ignore_permissions=True)
    return no.name


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
            if r.get("hsd") and getdate(r.hsd) <= getdate(self.ngay):
                frappe.throw(_("Dòng {0} ({1}): HSD {2} không sau ngày nhập {3}.").format(
                    r.idx, r.ten or r.item, frappe.utils.formatdate(r.hsd),
                    frappe.utils.formatdate(self.ngay)))
            tong_dem += flt(r.so_dem)
            tong_lech += flt(r.lech)
        self.tong_dem = tong_dem
        self.tong_lech = tong_lech
        if self.docstatus == 0:
            self.trang_thai = "Nháp"

    def before_submit(self):
        if not any(flt(r.so_dem) > 0 for r in self.dong):
            frappe.throw(_("Chưa có dòng nào đếm được số > 0 — không duyệt phiếu rỗng."))
        self.kiem_hsd()
        self.kiem_tran_da_cham()
        self.kiem_ton_nguyen_lieu()
        self.nguoi_duyet = frappe.session.user
        self.duyet_luc = now_datetime()
        self.trang_thai = "Đã duyệt"

    def kiem_hsd(self):
        """Mọi dòng nhận > 0 phải có HSD trước khi thành lô trong kho (D114).

        Để trống thì lấy mặc định theo Shelf Life của mã hàng — không lưu sẵn lúc
        nháp, để đổi ngày phiếu thì mặc định đi theo. Mã chưa khai Shelf Life mà
        thủ kho cũng chưa gõ → chặn, nói rõ hai cách gỡ. Lô vào kho không HSD thì
        sau này không ai biết hộp nào sắp hết hạn.
        """
        thieu = []
        for r in self.dong:
            if flt(r.so_dem) <= 0 or r.get("hsd"):
                continue
            goi_y = hsd_goi_y(r.item, self.ngay)
            if goi_y:
                r.hsd = goi_y
            else:
                thieu.append(_("• Dòng {0}: {1}").format(r.idx, r.ten or r.item))
        if thieu:
            frappe.throw(
                _("Chưa có hạn sử dụng cho:") + "<br>" + "<br>".join(thieu) + "<br><br>"
                + _("Bấm vào ô HSD của dòng để nhập theo HSD in trên bao bì, hoặc nhờ "
                    "quản lý khai \"Shelf Life In Days\" trên mã hàng (Item) để các phiếu "
                    "sau tự điền."),
                title=_("Thiếu HSD"))

    def kiem_tran_da_cham(self):
        """Phần nhận VƯỢT số đã chấm vào hộp → ghi nợ, KHÔNG chặn (D101).

        D70 chặn cứng chỗ này: hàng thật đứng ngoài kho vì QC chưa kịp chấm, còn
        hàng công nhật đóng thì không có chỗ nào chấm. Từ D101 công nhật chấm ở màn
        Ghi hộp, vượt thì duyệt vẫn qua, phần vượt vào SX No Vao Hop (on_submit).
        Tính ở ĐÂY (trước khi phiếu thành đã duyệt) để phiếu chưa tự trừ chính mình.
        """
        from sx.api.khotp import vuot_so_cham

        self.flags.vuot_cham = vuot_so_cham(self.ngay, self.dong, self.name)

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
                # D97: chưa có BOM thì nhập tạm + ghi nợ, KHÔNG trừ nguyên liệu lúc
                # này — nên cũng không có gì để kiểm tồn. Kiểm lúc hạch toán bù.
                continue
            for item_code, so in _nhu_cau_bom(bom, flt(r.so_dem)).items():
                kho = kho_nguon_rm(item_code, settings)
                can[(item_code, kho)] = can.get((item_code, kho), 0) + flt(so)

        # D116: mã chưa có giá vốn thì ERPNext văng tiếng Anh lúc submit phiếu kho.
        from sx.api.mfg import bao_thieu_gia_von, thieu_gia_von
        thieu_gia = thieu_gia_von(set(can))
        if thieu_gia:
            bao_thieu_gia_von(thieu_gia, _("duyệt nhập kho"))

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

        D97 — dòng CHƯA CÓ BOM không chặn cả phiếu nữa. Trước đây một mã hàng mới
        chưa kịp làm định mức là thủ kho không duyệt được, hàng đứng ngoài kho, và
        người ta tìm cách lách (nhập qua Desk, ghi sổ tay). Giờ dòng đó:
          · vẫn vào kho, có lô theo ngày (Material Receipt),
          · KHÔNG trừ nguyên liệu,
          · ghi một dòng vào SX No BOM để hạch toán bù khi có BOM.
        Dòng có BOM đi đường cũ, không đổi gì.
        """
        from sx.api.chot import _kho_nguon as kho_nguon_rm
        from sx.api.mfg import tao_batch, tao_se_manufacture, tao_se_nhap_thang, tao_wo
        from sx.utils import get_bom_active, get_settings, sinh_ma_lo

        settings = get_settings()
        chung_tu = []
        for r in self.dong:
            nhan = flt(r.so_dem)
            if nhan <= 0:
                continue
            bom = get_bom_active(r.item)

            # Mã lô sinh theo NGÀY NHẬN — truy xuất NGÀY × LOẠI (D3) vẫn nguyên,
            # không cần bám vào phiếu ngày sản xuất nào.
            # D114: NSX = ngày nhập (lô sinh theo ngày nhận), HSD đã kiểm ở before_submit.
            batch = tao_batch(r.item, sinh_ma_lo(r.item, self.ngay),
                              nsx=self.ngay, hsd=r.get("hsd"))

            if not bom:
                gia = _gia_von_tam(r.item, self.kho_dich)
                se = tao_se_nhap_thang(
                    settings.cong_ty, r.item, nhan, self.kho_dich, batch, gia=gia,
                    ngay=self.ngay,
                    ghi_chu=_("Nhập tạm — {0} chưa có BOM. Nguyên liệu CHƯA trừ, "
                              "ghi nợ ở SX No BOM (phiếu {1} dòng {2}).").format(
                                  r.item, self.name, r.idx))
                chung_tu.append({"dt": "Stock Entry", "name": se.name})
                _ghi_no_bom(self, r, nhan, batch, se.name, gia)
                continue
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

        # D101: kho nhận vượt số chấm → nợ vào hộp, cùng một lần duyệt.
        vuot = self.flags.get("vuot_cham")
        if vuot:
            from sx.api.khotp import ghi_no_vao_hop
            ghi_no_vao_hop(self, vuot)

    def on_cancel(self):
        """Huỷ phiếu = thu hồi ĐÚNG những chứng từ do phiếu này sinh ra, đảo thứ tự
        (xuất huỷ trước, rồi SE nhập, rồi WO) để không có bước nào rút hàng chưa có."""
        from sx.api.mfg import cancel_doc

        log = []
        # D97: nợ BOM của phiếu này. Nợ đã HẠCH TOÁN BÙ thì huỷ luôn phiếu trừ
        # nguyên liệu bù — huỷ thành phẩm mà để nguyên liệu vẫn bị trừ là kho mất
        # bột oan. Mỗi dòng nợ có phiếu bù RIÊNG nên huỷ ở đây không đụng tới nợ
        # của phiếu nhập khác.
        for no in frappe.get_all("SX No BOM", filters={"phieu_nhap": self.name},
                                 fields=["name", "trang_thai", "se_bu"]):
            if no.se_bu:
                cancel_doc("Stock Entry", no.se_bu, log)
            frappe.db.set_value("SX No BOM", no.name, {
                "trang_thai": "Đã huỷ",
                "ly_do": _("Huỷ theo phiếu nhập {0}").format(self.name),
            }, update_modified=True)
            log.append(f"Nợ BOM {no.name} → Đã huỷ")
        # D101: nợ vào hộp của phiếu này hết nghĩa — hàng không còn trong kho.
        for n in frappe.get_all("SX No Vao Hop",
                                filters={"phieu_nhap": self.name, "trang_thai": "Chờ chấm"},
                                pluck="name"):
            frappe.db.set_value("SX No Vao Hop", n, {
                "trang_thai": "Đã huỷ",
                "ly_do": _("Huỷ theo phiếu nhập {0}").format(self.name)})
            log.append(f"Nợ vào hộp {n} → Đã huỷ")
        for ct in reversed(json.loads(self.ds_se or "[]")):
            cancel_doc(ct.get("dt"), ct.get("name"), log)
        self.db_set("trang_thai", "Đã huỷ", update_modified=False)
        if log:
            ghi = (self.ghi_chu or "") + "\n[Huỷ phiếu] " + "; ".join(log)
            self.db_set("ghi_chu", ghi.strip(), update_modified=False)
