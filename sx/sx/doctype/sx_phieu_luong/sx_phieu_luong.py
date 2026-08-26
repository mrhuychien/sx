"""Phiếu lương sản lượng — ĐỘC LẬP, không dùng phiếu lương của app khác (D69).

Trước D69, chốt ngày ghi thẳng vào `SalaryProduct` của app lam-luong: ghi đè nguyên
dòng của ngày đó (sp1..sp6 / sl1..sl6 / dg1..dg6 / tt1..tt6 + tienanca + andem).
Ba vấn đề với cách đó, và cả ba đều là lý do bỏ:
  · Trần 6 loại/ngày. Từ D68 QC ghi theo MÃ HÀNG, một người một ngày dễ quá 6 mã.
  · Toàn bộ công thức nằm trong Client Script — chỉ chạy khi mở form trên Desk. Ghi
    bằng API thì không công thức nào chạy, số trên phiếu là số ai đó phải tự tính.
  · Ghi đè dữ liệu của app khác bằng ignore_permissions là chỗ hỏng ngầm chực chờ.

Phiếu này giữ NGUYÊN mọi quy tắc tính của bảng lương đang dùng (chép từ Client
Script), chỉ khác: tính ở SERVER lúc validate, nên gọi bằng API hay bấm trên Desk
đều ra một kết quả.

═══ QUY TẮC (giữ nguyên từ bảng lương hiện hành) ═══
  tiền ăn ngày   = ăn ca × đơn giá ăn ca + ăn đêm × đơn giá ăn đêm
  lương SP ngày  = Σ (số lượng × đơn giá) các dòng chi tiết của ngày
  thu nhập ngày  = lương SP ngày × HỆ SỐ + tiền ăn        (hệ số 1.2 nếu Chủ nhật / 1-1)
  ngày công      = số ngày có ăn ca  +  0,5 × số ngày chỉ có ăn đêm
  chuyên cần     = ngưỡng thường nếu ngày công > 25 hoặc ≥ (ngày SX − 0,5)
                   ngày SX > 29 và thiếu < 1 công -> mức cao (tháng cao điểm cao hơn)
  hỗ trợ ngày công = (ngày công chuẩn − ngày công) × đơn giá, chỉ khi ngày SX < chuẩn
                     và thiếu < 1 công. Tháng 2 không tính.
  thưởng thâm niên = 5% × (lương SP tháng này + 2 tháng liền trước)
  tổng thu nhập  = lương SP + tiền ăn + hỗ trợ + chuyên cần + hỗ trợ ngày công + thâm niên
  thực nhận      = tổng thu nhập − (tiền phạt + bảo hiểm)

Mọi con số cấu hình nằm ở SX Settings, không hardcode: đổi mức ăn ca giữa năm là
chuyện thường, mà sửa code để đổi một con số thì lần sau không ai dám đổi.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

from sx.utils import get_settings


def _cau_hinh():
    """Đọc tham số lương từ SX Settings, có mặc định = mức đang dùng thực tế."""
    s = get_settings()

    def lay(field, mac_dinh):
        v = s.get(field)
        return flt(v) if v not in (None, "") else mac_dinh

    thang_cao = str(s.get("thang_cao_diem") or "11,12,1")
    return {
        "an_ca": lay("tien_an_ca", 20000),
        "an_dem": lay("tien_an_dem", 10000),
        "he_so_le": lay("he_so_ngay_le", 1.2),
        "cc_dat": lay("chuyen_can_dat", 200000),
        "cc_du": lay("chuyen_can_du", 300000),
        "cc_du_cao_diem": lay("chuyen_can_du_cao_diem", 1000000),
        "ngay_cong_chuan": lay("ngay_cong_chuan", 22),
        "ho_tro_moi_ngay": lay("ho_tro_ngay_cong", 70000),
        "tham_nien": lay("ty_le_tham_nien", 0.05),
        "thang_cao_diem": {
            cint(x) for x in thang_cao.replace(" ", "").split(",") if x.strip().isdigit()
        },
    }


def _la_ngay_he_so(ngay):
    """Ngày hưởng hệ số: Chủ nhật, và mùng 1 tháng 1.

    Giữ đúng quy tắc đang chạy. Ngày lễ khác chưa nằm trong quy tắc nào — thêm thì
    phải hỏi bộ phận lương, không tự suy."""
    d = getdate(ngay)
    return d.weekday() == 6 or (d.day == 1 and d.month == 1)


class SXPhieuLuong(Document):
    def validate(self):
        self.validate_ky()
        cf = _cau_hinh()
        self.tinh_chi_tiet(cf)
        self.tinh_theo_ngay(cf)
        self.tinh_phat()
        self.tinh_tong(cf)
        if self.docstatus == 0:
            self.trang_thai = "Nháp"

    def validate_ky(self):
        if not 1 <= cint(self.thang) <= 12:
            frappe.throw(_("Tháng phải từ 1 đến 12."))
        trung = frappe.db.exists(
            "SX Phieu Luong",
            {"employee": self.employee, "thang": self.thang, "nam": self.nam,
             "docstatus": ("<", 2), "name": ("!=", self.name)},
        )
        if trung:
            frappe.throw(
                _("{0} đã có phiếu lương tháng {1}/{2}: {3}. Mỗi người một phiếu "
                  "mỗi tháng.").format(self.ten_nhan_vien or self.employee,
                                       self.thang, self.nam, trung)
            )
        # Dòng lạc tháng là dấu hiệu nhập nhầm — bắt ngay, đừng để nó lặng lẽ
        # cộng vào lương tháng này.
        for r in list(self.dong) + list(self.chi_tiet):
            d = getdate(r.ngay)
            if d.month != cint(self.thang) or d.year != cint(self.nam):
                frappe.throw(
                    _("Ngày {0} không thuộc tháng {1}/{2}.").format(
                        frappe.utils.formatdate(r.ngay), self.thang, self.nam)
                )

    def tinh_chi_tiet(self, cf):
        for r in self.chi_tiet:
            r.thanh_tien = flt(r.don_gia) * cint(r.so_luong)

    def tinh_theo_ngay(self, cf):
        """Σ chi tiết về từng ngày, rồi áp hệ số ngày lễ."""
        THU = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
        sp_theo_ngay = {}
        for r in self.chi_tiet:
            k = str(getdate(r.ngay))
            sp_theo_ngay[k] = sp_theo_ngay.get(k, 0) + flt(r.thanh_tien)

        co_dong = {str(getdate(r.ngay)) for r in self.dong}
        # Ngày có sản lượng mà chưa có dòng ngày -> tự thêm, nếu không lương sản
        # phẩm của ngày đó rơi mất mà bảng vẫn trông đầy đủ.
        for k in sorted(set(sp_theo_ngay) - co_dong):
            self.append("dong", {"ngay": k, "an_ca": 0, "an_dem": 0})

        for r in self.dong:
            d = getdate(r.ngay)
            r.thu = THU[d.weekday()]
            r.tien_an = (cint(r.an_ca) * cf["an_ca"] + cint(r.an_dem) * cf["an_dem"])
            r.luong_sp = flt(sp_theo_ngay.get(str(d), 0))
            r.he_so = cf["he_so_le"] if _la_ngay_he_so(d) else 1.0
            r.thu_nhap_ngay = r.luong_sp * flt(r.he_so) + flt(r.tien_an)
        self.dong = sorted(self.dong, key=lambda r: getdate(r.ngay))
        for i, r in enumerate(self.dong, start=1):
            r.idx = i

    def tinh_phat(self):
        for r in self.phat:
            r.thanh_tien = flt(r.so_luong) * flt(r.gia_tien)
        self.tien_phat = sum(flt(r.thanh_tien) for r in self.phat)

    def tinh_tong(self, cf):
        self.luong_san_pham = sum(
            flt(r.thu_nhap_ngay) - flt(r.tien_an) for r in self.dong)
        self.tien_an = sum(flt(r.tien_an) for r in self.dong)

        # Ngày công: có ăn ca = 1 công; chỉ ăn đêm = nửa công.
        so_ca = sum(1 for r in self.dong if cint(r.an_ca) > 0)
        so_dem = sum(1 for r in self.dong if cint(r.an_dem) > 0 and cint(r.an_ca) == 0)
        self.ngay_cong = so_ca + so_dem * 0.5

        self.chuyen_can = self._chuyen_can(cf)
        self.ho_tro_ngay_cong = self._ho_tro_ngay_cong(cf)
        self._tham_nien(cf)

        self.tong_khau_tru = flt(self.tien_phat) + flt(self.bao_hiem)
        self.tong_tien = (
            flt(self.luong_san_pham) + flt(self.tien_an) + flt(self.ho_tro)
            + flt(self.chuyen_can) + flt(self.ho_tro_ngay_cong)
            + flt(self.thuong_tham_nien)
        )
        self.luong_thuc_nhan = flt(self.tong_tien) - flt(self.tong_khau_tru)

    def _chuyen_can(self, cf):
        ngay_sx = flt(self.ngay_san_xuat)
        cong = flt(self.ngay_cong)
        muc = 0.0
        if cong > 25 or (ngay_sx and cong >= ngay_sx - 0.5):
            muc = cf["cc_dat"]
        # Tháng xưởng chạy gần như không nghỉ mà vẫn đi đủ -> mức cao hơn hẳn.
        # Điều kiện này ĐÈ lên mức thường, đúng thứ tự của bảng lương đang dùng.
        if ngay_sx > 29 and ngay_sx - cong < 1:
            muc = (cf["cc_du_cao_diem"] if cint(self.thang) in cf["thang_cao_diem"]
                   else cf["cc_du"])
        return muc

    def _ho_tro_ngay_cong(self, cf):
        """Xưởng chạy ÍT ngày hơn chuẩn mà công nhân đi đủ -> bù cho phần thiếu.

        Đây là bù do THIẾU VIỆC, không phải do người ta nghỉ, nên chỉ tính khi
        người ta đi gần như đủ số ngày xưởng chạy."""
        if cint(self.thang) == 2:
            return 0.0   # tháng 2 không tính, theo quy tắc đang dùng
        ngay_sx = flt(self.ngay_san_xuat)
        cong = flt(self.ngay_cong)
        chuan = cf["ngay_cong_chuan"]
        if not (ngay_sx and ngay_sx < chuan and ngay_sx - cong < 1):
            return 0.0
        thieu = chuan - cong - (0.5 if abs(ngay_sx - cong - 0.5) < 1e-9 else 0)
        return max(0.0, thieu) * cf["ho_tro_moi_ngay"]

    def _tham_nien(self, cf):
        if not cint(self.tinh_thuong_tham_nien):
            self.tham_nien_thang_nay = 0
            self.tham_nien_thang_truoc = 0
            self.tham_nien_thang_truoc_nua = 0
            self.thuong_tham_nien = 0
            return
        ty = cf["tham_nien"]

        def luong_sp(lui):
            th, na = cint(self.thang) - lui, cint(self.nam)
            while th < 1:
                th += 12
                na -= 1
            return flt(frappe.db.get_value(
                "SX Phieu Luong",
                {"employee": self.employee, "thang": th, "nam": na,
                 "docstatus": ("<", 2)},
                "luong_san_pham"))

        self.tham_nien_thang_nay = flt(self.luong_san_pham) * ty
        self.tham_nien_thang_truoc = luong_sp(1) * ty
        self.tham_nien_thang_truoc_nua = luong_sp(2) * ty
        self.thuong_tham_nien = (flt(self.tham_nien_thang_nay)
                                 + flt(self.tham_nien_thang_truoc)
                                 + flt(self.tham_nien_thang_truoc_nua))

    def before_submit(self):
        self.trang_thai = "Đã duyệt"

    def on_cancel(self):
        self.db_set("trang_thai", "Đã huỷ", update_modified=False)
