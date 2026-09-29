"""Vòng kiểm QC (BM.08.01) — một lượt đi kiểm của QC chế biến.

Ba luật nằm trong code chứ không nằm trong lời dặn, vì lời dặn thì hết ca là quên:

1. GHI TẠI CHỖ. `started_at` do server đặt lúc tạo lượt, `finished_at` lúc hoàn
   tất, mỗi giá trị kèm giờ trên máy QC trong bảng `log`. Ghi muộn KHÔNG bị chặn
   — chặn thì người ta ghi bừa cho kịp giờ, mà đó mới là thứ phá hồ sơ. Chỉ gắn
   cờ để người xem xét thấy.

2. ĐỂ TRỐNG, KHÔNG ĐIỀN BÙ. Mỗi mục có ba trạng thái Đạt / Không đạt / trống.
   Mục áp dụng mà để trống thì phải có lý do trong ghi_chu — không chặn ghi, chặn
   HOÀN TẤT. Ép đủ ô là dạy người ta bấm Đạt cho xong.

3. LỆCH → SỰ CỐ. Không đạt hoặc vượt ngưỡng thì lúc hoàn tất tự sinh phiếu sự cố
   trạng thái Mở, gắn hai chiều với lượt. QC không có nút "bỏ qua".

Người ghi không tự duyệt: đóng sự cố và đánh dấu đã xem xét là việc của ISO
Manager (chốt trong sx/api/qc.py).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
    cint,
    get_datetime,
    get_time,
    now_datetime,
    time_diff_in_seconds,
)

from sx.qc import muc as M
from sx.qc.nguong import nguong
from sx.qc.su_co import tao_tu_vong_kiem


def _gia_tri(doc, m):
    """Giá trị một mục, đọc qua .get() — site chưa migrate thì field chưa có trong
    meta và truy cập thẳng là AttributeError, trả về 500 trống trơn."""
    return doc.get(m["f"])


class SXQCRound(Document):
    # ── ghi ──────────────────────────────────────────────────────────────
    def before_insert(self):
        # Giờ bắt đầu do SERVER đặt. Lấy giờ máy QC ở đây là mời người ta chỉnh
        # đồng hồ điện thoại rồi ghi lượt hôm qua thành đúng giờ.
        self.started_at = now_datetime()
        if not self.qc_user:
            self.qc_user = frappe.session.user

    def validate(self):
        self.kiem_trung()
        self.tinh_boi_canh()
        ap = M.muc_cham(self.luot, self)
        self.so_muc_ap_dung = len(ap)
        self.so_muc_da_cham = sum(1 for m in ap if M.co_ghi(m, _gia_tri(self, m)))

    def tinh_boi_canh(self):
        """Số máy và hai cờ lạc (D100) — SERVER tính, không nhận từ máy QC.

        Cờ lạc suy từ ô B0 (vị đang làm) + danh sách vị có lạc ở SX QC Setting.
        Tính ở đây chứ không để máy QC gửi lên: gửi lên được thì tắt được, và tắt
        B7 là bỏ bước thử dị ứng mà hồ sơ trông vẫn đủ.
        """
        for nhom, (_ten, _toi_da, truong) in M.NHOM_MAY.items():
            self.set(truong, M.so_may(self.get(truong), nhom))
        if not cint(self.co_san_xuat_bot):
            self.co_lac = 0
            self.can_thu_lac = 0
            return
        chon = M.tach_chon(self.get("san_pham_bot"))
        ten = {r.name: r.item_name for r in frappe.get_all(
            "Item", filters={"name": ("in", chon)}, fields=["name", "item_name"])} \
            if chon else {}
        self.co_lac = M.co_lac_trong(chon, ten, nguong()["bot_co_lac"])
        khac = frappe.get_all(
            "SX QC Round",
            filters={"ngay": self.ngay, "docstatus": ("<", 2),
                     "name": ("!=", self.name or "")},
            fields=["luot", "co_lac"])
        self.can_thu_lac = M.can_thu_lac(
            self.co_lac, self.luot, [(r.luot, r.co_lac) for r in khac])

    def on_update(self):
        """Lượt này vừa đổi cờ lạc → các lượt SAU trong ngày còn dở phải tính lại
        B7: sáng thêm chè đậu đen thì lượt trưa đang mở phải hiện ô thử lạc."""
        if not self.has_value_changed("co_lac"):
            return
        t = M.thu_tu_luot(self.luot)
        for r in frappe.get_all("SX QC Round",
                                filters={"ngay": self.ngay, "docstatus": 0,
                                         "name": ("!=", self.name)},
                                fields=["name", "luot"]):
            if M.thu_tu_luot(r.luot) > t:
                frappe.get_doc("SX QC Round", r.name).save()

    def kiem_trung(self):
        """Một (ngày, lượt) chỉ có một phiếu; Đầu sáng và Tuần loại trừ nhau.

        Không dùng unique index vì luật loại trừ Đầu sáng ↔ Tuần không phải là
        unique trên hai cột — và vì thông báo của MariaDB ("Duplicate entry") thì
        QC đứng giữa xưởng đọc không hiểu gì.

        Không lọc theo ca (bỏ từ D95). Phiếu cũ trước D95 có thể còn hai lượt
        cùng tên trong một ngày (ca Sáng + ca Chiều); đó là hồ sơ đã chốt, không
        ai sửa nó, nên chuyện này chỉ chặn việc mở THÊM lượt vào ngày cũ đó.
        """
        cung = [self.luot]
        if self.luot in M.DAU_NGAY_HOAC_TUAN:
            cung = list(M.DAU_NGAY_HOAC_TUAN)
        trung = frappe.get_all(
            "SX QC Round",
            filters={"ngay": self.ngay, "luot": ("in", cung),
                     "docstatus": ("<", 2), "name": ("!=", self.name or "")},
            fields=["name", "luot"], limit=1,
        )
        if not trung:
            return
        t = trung[0]
        them = ""
        if t["luot"] != self.luot:
            them = _(" — lượt Tuần LÀ lượt đầu sáng thứ Hai, không phải lượt thêm.")
        frappe.throw(
            _("Ngày {0} đã có lượt {1} ({2}){3}").format(
                self.ngay, t["luot"], t["name"], them))

    # ── hoàn tất ─────────────────────────────────────────────────────────
    def before_submit(self):
        self.finished_at = now_datetime()
        self.duration_min = int(
            time_diff_in_seconds(self.finished_at,
                                 self.started_at or self.finished_at) // 60)
        self.kiem_bat_buoc()
        self.kiem_de_trong()
        self.ghi_muon = 0 if cint(self.nhap_lai_tu_giay) else cint(self.tinh_ghi_muon())
        # Sinh sự cố Ở ĐÂY chứ không ở on_submit — xem chú thích trong sx/qc/su_co.py.
        tao_tu_vong_kiem(self)

    def kiem_bat_buoc(self):
        """Mục bắt buộc thì thiếu là CHẶN, không phải nhắc.

        Chỉ có nhiệt độ rang nằm ở nhóm này: nó là phép đo oPRP, không có nó thì
        cả lượt không chứng minh được gì. Mọi mục khác được phép để trống kèm lý do.
        """
        thieu = [m for m in M.muc_cham(self.luot, self)
                 if m["batbuoc"] and not M.co_ghi(m, _gia_tri(self, m))]
        if thieu:
            frappe.throw(_("Chưa ghi mục bắt buộc: {0}").format(
                ", ".join(f'{m["so"]} {m["nhan"]}' for m in thieu)))

    def kiem_de_trong(self):
        """Mục áp dụng để trống thì phải có lý do — không chặn nếu đã ghi lý do."""
        trong = [m for m in M.muc_cham(self.luot, self)
                 if not M.co_ghi(m, _gia_tri(self, m))]
        if trong and not (self.ghi_chu or "").strip():
            frappe.throw(
                _("Còn {0} mục để trống. Ghi lý do vào ô Ghi chú rồi hoàn tất — "
                  "để trống có lý do là hồ sơ thật, bấm Đạt cho đủ ô thì không.")
                .format(len(trong))
                + "<br><br>" + "<br>".join(f'• {m["so"]} {m["nhan"]}' for m in trong[:12])
                + ("<br>…" if len(trong) > 12 else ""))
        if cint(self.nhap_lai_tu_giay) and not (self.ghi_chu or "").strip():
            frappe.throw(_("Nhập lại từ bản giấy thì phải ghi rõ ngày ghi thật "
                           "vào ô Ghi chú."))

    def tinh_ghi_muon(self):
        """Ghi muộn = làm quá lâu, hoặc hoàn tất ngoài khung giờ của lượt."""
        ng = nguong()
        if cint(self.duration_min) > cint(ng.get("ghi_muon_phut")):
            return 1
        khung = ng["khung"].get(M.DAU_SANG if self.luot == M.TUAN else self.luot)
        if not khung:
            return 0
        gio = get_time(get_datetime(self.finished_at))
        tu, den = khung
        if tu and gio < get_time(tu):
            return 1
        return 1 if den and gio > get_time(den) else 0

    def on_cancel(self):
        """Đã xem xét thì khoá — kể cả ISO Manager.

        Sau khi Ban ISO ký xem xét, hồ sơ đó đã đi vào hồ sơ chất lượng. Sửa sai
        thì lập phiếu sự cố loại "Hiệu chỉnh hồ sơ" ghi nội dung đúng, chứ không
        xoá dấu vết. Chỉ System Manager gỡ được, và việc đó để lại vết trong log.
        """
        if self.reviewed_on and "System Manager" not in frappe.get_roles():
            frappe.throw(
                _("Lượt này Ban ISO đã xem xét ngày {0} — không huỷ được nữa. "
                  "Ghi nhận sai sót bằng phiếu sự cố loại 'Hiệu chỉnh hồ sơ'.")
                .format(frappe.utils.formatdate(self.reviewed_on)),
                frappe.PermissionError)

    # ── dùng chung ───────────────────────────────────────────────────────
    def gia_tri_muc(self):
        """{fieldname: giá trị} của các mục áp dụng — cho tờ in và màn hình."""
        return {m["f"]: _gia_tri(self, m)
                for m in M.muc_ap_dung(self.luot, self)}
