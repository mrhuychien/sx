"""Chốt ngày sản xuất v3 (spec §5.4) + huỷ ngược (on_cancel_ngay).

Sinh T2 (mẻ trộn/nấu theo bao_me, topo-sort theo phụ thuộc BOM: màu → đường hoán →
bột bánh/bột đậu) rồi T3 (TP theo bảng vào hộp). KHÔNG xử lý T1 (đậu đã trừ ở
SX Nhap Bot — D7). RM FIFO toàn tuyến. try/except toàn khối + rollback.

GATE-B (SalaryProduct): mapping ADAPTIVE đọc meta runtime; không map được -> báo
lỗi rõ + rollback. Chốt mapping cứng sau khi chủ đầu tư duyệt.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime

from sx.api.mfg import cancel_doc, loai_phieu_kho, tao_batch, tao_se_manufacture, tao_wo
from sx.config.roles import guard_card
from sx.utils import (
    cho_phep_ton_am,
    get_bom_active,
    get_settings,
    sinh_ma_lo,
    topo_rank_by_bom,
)


# ══════════════════ HAI NỬA CHỐT ĐỘC LẬP (D55) ══════════════════
#
# Trước D55 chốt ngày là MỘT nút làm tất cả. Thực tế hai nửa thuộc hai người và
# xong ở hai thời điểm khác nhau:
#
#   GHI SỔ  (QC#1) — báo mẻ → tầng 2 → bột bánh / bột đậu vào Kho BTP.
#                    Xong khi mẻ cuối ra lò, thường giữa ca.
#   VÀO HỘP (QC#2) — bảng vào hộp → tầng 3 → thành phẩm + lương khoán.
#                    Xong khi hết ca, sau khi hỏi đủ người.
#
# Bắt hai người chờ nhau ở một cái nút là lý do người ta chốt muộn rồi chốt ẩu.
#
# ─── THỨ TỰ BẮT BUỘC: Ghi sổ TRƯỚC, Vào hộp SAU ───
# Tầng 3 tiêu thụ chính bột mà tầng 2 vừa sinh ra. Chốt Vào hộp trước thì bột
# chưa vào kho -> hoặc báo "không đủ tồn", hoặc (site bật tồn âm) ghi âm kho im
# lặng. Chặn ngay từ đầu bằng một câu nói rõ lý do vẫn hơn để nó vỡ ở giữa.
# Ngày không nấu mẻ nào vẫn phải bấm chốt Ghi sổ — đó là lúc QC tuyên bố
# "hôm nay không có mẻ", chứ không phải "tôi quên chưa nhập".
#
# ─── VÌ SAO KHÔNG DÙNG docstatus CHO TỪNG NỬA ───
# Frappe chỉ có một docstatus, và submit không lùi lại được. Hai cờ riêng
# (chot_ghiso / chot_vaohop) mang trạng thái thật; phiếu ngày chỉ submit khi CẢ
# HAI đã chốt — giữ nguyên mọi thứ đang dựa vào docstatus=1 (dashboard, hook huỷ
# ngược, "ngày đã xong"). Huỷ từng nửa chỉ làm được khi phiếu còn nháp; đã submit
# thì dùng HUỶ CHỐT NGÀY như cũ (đảo cả hai rồi trả lại bản nháp giữ nguyên số).


def _lay_bang(doc):
    ten = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": doc.name, "docstatus": ("<", 2)}, "name"
    )
    return frappe.get_doc("SX Bang Vao Hop", ten) if ten else None


def _ghi_chung_tu(doc, field, them):
    """Cộng dồn chứng từ vào ĐÚNG nửa — huỷ ngược phải đảo đúng nửa đó, không
    được đụng chứng từ của nửa kia."""
    cu = json.loads(doc.get(field) or "[]")
    doc.set(field, json.dumps(cu + them))


def _submit_neu_du_hai_nua(doc):
    """Cả hai nửa xong -> submit phiếu ngày (docstatus 1 = ngày đã xong hẳn)."""
    if not (cint(doc.chot_ghiso) and cint(doc.chot_vaohop)):
        doc.trang_thai = "Chốt một phần"
        doc.flags.ignore_permissions = True
        doc.save()
        return False
    doc.flags.tu_chot_ngay = True
    doc.flags.ignore_permissions = True
    doc.save()
    doc.submit()
    return True


def _kiem_chua_chot(doc, nua):
    if doc.docstatus == 2:
        frappe.throw(_("Phiếu ngày {0} đã huỷ.").format(doc.name))
    if doc.docstatus == 1 or cint(doc.get(f"chot_{nua}")):
        frappe.throw(
            _("Phần {0} của ngày {1} ĐÃ chốt rồi.").format(
                "Ghi sổ" if nua == "ghiso" else "Vào hộp", doc.name)
        )


@frappe.whitelist()
def chot_ghiso(ngay_sx):
    """Chốt nửa GHI SỔ: báo mẻ -> tầng 2 (nấu + trộn) -> bột vào Kho BTP.

    Không đụng bảng vào hộp, không ghi lương. Sau bước này báo mẻ / báo cán / sự cố
    của ngày bị khoá (chứng từ kho đã sinh theo số đó).
    """
    guard_card("chotngay")
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    _kiem_chua_chot(doc, "ghiso")
    _validate_chung(doc)
    _kiem_ton_kho(doc, get_settings())

    buoc = _("tầng 2 (nấu + trộn theo báo mẻ)")
    try:
        chung_tu = []
        _chot_tang_2(doc, chung_tu)

        buoc = _("ghi trạng thái chốt Ghi sổ")
        _ghi_chung_tu(doc, "ds_wo_se_ghiso", chung_tu)
        doc.chot_ghiso = 1
        doc.chot_ghiso_luc = now_datetime()
        doc.chot_ghiso_boi = frappe.session.user
        _submit_neu_du_hai_nua(doc)
        canh_bao = _canh_bao_mem(doc)
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title=f"chot_ghiso {ngay_sx} hỏng ở bước: {buoc}",
                         message=frappe.get_traceback())
        frappe.throw(
            _("Chốt Ghi sổ THẤT BẠI ở bước: {0}. Toàn bộ đã hoàn tác — không có "
              "trạng thái nửa vời. Chi tiết trong Error Log.").format(buoc)
        )
    return _tom_tat(doc, canh_bao)


@frappe.whitelist()
def chot_vaohop(ngay_sx):
    """Chốt nửa VÀO HỘP: chốt bảng vào hộp + ghi lương khoán. KHÔNG đụng kho.

    Từ D59 hai nửa THẬT SỰ độc lập, không còn bắt Ghi sổ phải chốt trước: tầng 3
    không sinh ở đây nữa nên chốt Vào hộp chẳng cần bột của tầng 2 tồn tại. Ràng
    buộc đó chuyển sang đúng chỗ nó thuộc về — lúc thủ kho DUYỆT phiếu nhập kho,
    vì đó mới là lúc nguyên liệu bị trừ.
    """
    guard_card("chotngay")
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    _kiem_chua_chot(doc, "vaohop")
    _validate_chung(doc)
    bang = _lay_bang(doc)
    if not _co_gi_de_ghi(bang):
        frappe.throw(
            _("Bảng vào hộp chưa có sản lượng lẫn chấm ăn ca — không có gì để chốt.")
        )
    if bang.docstatus == 0:
        # Controller lookup đơn giá khi save — save lại để chắc mọi dòng có giá
        bang.flags.ignore_permissions = True
        bang.save()
    # KHÔNG kiểm tồn ở đây nữa (D59): chốt Vào hộp không đụng kho. Nguyên liệu chỉ
    # bị trừ khi thủ kho duyệt phiếu nhập kho, và tồn được kiểm ở đúng lúc đó.

    buoc = _("submit bảng vào hộp")
    try:
        if bang.docstatus == 0:
            bang.flags.ignore_permissions = True
            bang.submit()

        buoc = _("ghi phiếu lương khoán")
        ds_salary = _ghi_luong_khoan(doc, bang)

        buoc = _("ghi trạng thái chốt Vào hộp")
        doc.tong_hop_tp = cint(bang.tong_hop)
        doc.tong_luong_sp = flt(bang.tong_tien)
        doc.salary_products_json = json.dumps(ds_salary)
        doc.chot_vaohop = 1
        doc.chot_vaohop_luc = now_datetime()
        doc.chot_vaohop_boi = frappe.session.user
        _submit_neu_du_hai_nua(doc)
        canh_bao = _canh_bao_mem(doc)
    except Exception:
        frappe.db.rollback()
        frappe.log_error(title=f"chot_vaohop {ngay_sx} hỏng ở bước: {buoc}",
                         message=frappe.get_traceback())
        frappe.throw(
            _("Chốt Vào hộp THẤT BẠI ở bước: {0}. Toàn bộ đã hoàn tác — không có "
              "trạng thái nửa vời. Chi tiết trong Error Log.").format(buoc)
        )
    return _tom_tat(doc, canh_bao)


@frappe.whitelist()
def chot_ngay(ngay_sx):
    """Chốt CẢ NGÀY trong một lần — hai nửa liên tiếp, vẫn một giao dịch.

    Giữ lại vì nhiều ngày một người làm cả hai việc, và vì mọi thứ gọi sẵn method
    này (lịch sử, script). Nửa nào đã chốt rồi thì bỏ qua, không báo lỗi.
    """
    guard_card("chotngay")
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    if doc.docstatus == 1:
        frappe.throw(_("Phiếu ngày {0} ĐÃ chốt rồi.").format(doc.name))
    if doc.docstatus == 2:
        frappe.throw(_("Phiếu ngày {0} đã huỷ.").format(doc.name))

    # Ngày rỗng hoàn toàn thì chốt cũng vô nghĩa — bắt ở đây cho câu báo dễ hiểu,
    # thay vì để hai nửa lần lượt báo hai lỗi khác nhau.
    if not doc.bao_me and not _co_gi_de_ghi(_lay_bang(doc)):
        frappe.throw(_("Ngày chưa có báo mẻ lẫn bảng vào hộp — không có gì để chốt."))

    if not cint(doc.chot_ghiso):
        chot_ghiso(ngay_sx)
        doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    if not cint(doc.chot_vaohop) and _co_gi_de_ghi(_lay_bang(doc)):
        chot_vaohop(ngay_sx)
        doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    return _tom_tat(doc, _canh_bao_mem(doc))


def _tom_tat(doc, canh_bao=None):
    return {
        "name": doc.name,
        "trang_thai": doc.trang_thai,
        "chot_ghiso": cint(doc.chot_ghiso),
        "chot_vaohop": cint(doc.chot_vaohop),
        "tong_hop_tp": doc.tong_hop_tp,
        "tong_luong_sp": doc.tong_luong_sp,
        "canh_bao": canh_bao or [],
    }


# ─────────────────────────────────────────────── validate ──


def _validate_chung(doc):
    """Kiểm cấu hình dùng chung cho CẢ HAI nửa chốt.

    Chạy NGOÀI try/except của hàm gọi: lỗi cấu hình (thiếu kho, thiếu Stock Entry
    Type) phải nổi lên nguyên văn cho QC đọc, không bị nuốt thành "xem Error Log".
    """
    settings = get_settings()
    for f, label in (
        ("cong_ty", "Công ty"),
        ("kho_nvl", "Kho NVL"),
        ("kho_btp", "Kho BTP"),
        ("kho_tp", "Kho TP"),
    ):
        if not settings.get(f):
            frappe.throw(_("SX Settings chưa cấu hình: {0}").format(label))

    # Thiếu Stock Entry Type "Manufacture" -> mọi phiếu kho sẽ chết ở validate. Kiểm
    # TẠI ĐÂY để QC đọc được nguyên nhân thật, không phải "check Error Log".
    loai_phieu_kho("Manufacture")
    return settings


def _co_gi_de_ghi(bang):
    """Bảng vào hộp có gì để ghi lương không: sản lượng khoán HOẶC chấm ăn ca (D30).

    Ngày chỉ chấm ăn mà không ai vào hộp vẫn phải ra dòng lương — nếu chỉ nhìn
    `tong_hop` thì ngày đó bị bỏ qua im lặng.
    """
    if not bang:
        return False
    if cint(bang.tong_hop) > 0:
        return True
    return any(
        cint(r.an_ca) or cint(r.an_dem) for r in (bang.get("an_ca") or [])
    )


def _kho_nguon(item_code, settings):
    """RM nhóm BTP (bột nền/đường hoán/màu/bột bánh/bột đậu) rút Kho BTP; còn lại Kho NVL."""
    nhom = frappe.get_cached_value("Item", item_code, "custom_sx_nhom") or ""
    return settings.kho_btp if nhom.startswith("BTP") else settings.kho_nvl


def _nhu_cau_bom(bom_name, qty_fg):
    """Explode 1 cấp BOM (use_multi_level_bom=0): {item_code: stock_qty cần}."""
    bom = frappe.get_cached_doc("BOM", bom_name)
    he_so = flt(qty_fg) / flt(bom.quantity or 1)
    nhu_cau = {}
    for r in bom.items:
        # Non-stock (Nước) không tính vào nhu cầu kho
        if not cint(frappe.get_cached_value("Item", r.item_code, "is_stock_item")):
            continue
        nhu_cau[r.item_code] = nhu_cau.get(r.item_code, 0) + flt(r.stock_qty) * he_so
    return nhu_cau


def _kiem_ton_kho(doc, settings):
    """Kiểm đủ tồn nguyên liệu TRƯỚC khi sinh chứng từ tầng 2 (chốt Ghi sổ).

    Chỉ tầng 2. Tầng 3 kiểm ở chỗ khác — lúc thủ kho duyệt phiếu nhập kho (D59) —
    vì đó mới là lúc nguyên liệu của nó bị trừ.

    BTP sinh trong CÙNG lần chốt (bao_me) được cộng tín dụng (xấp xỉ — FIFO thật ở
    bước sinh sẽ bắt thiếu chính xác & rollback).
    """
    sx_hom_nay = {}
    for row in doc.bao_me:
        sx_hom_nay[row.item_btp] = sx_hom_nay.get(row.item_btp, 0) + flt(row.tong_kg)
    # KHÔNG cộng tín dụng bột "sắp nhập" nữa: từ D31 bột chỉ vào kho khi QC bấm
    # Nghiền trên lưu đồ. Cộng trước sẽ cho chốt qua rồi vỡ ở bước sinh SE.

    # CỘNG DỒN nhu cầu rồi mới đối chiếu tồn MỘT LẦN cho mỗi (item, kho).
    # Kiểm từng dòng BOM riêng lẻ là sai: 4 công thức cùng cần 1000 kg dầu, tồn 1000
    # thì cả 4 lần kiểm đều "đủ", chốt qua rồi mới vỡ ở bước sinh phiếu kho.
    can_tong = {}

    def _check(item_code, kho, can):
        can_tong[(item_code, kho)] = can_tong.get((item_code, kho), 0) + flt(can)

    for row in doc.bao_me:
        bom = get_bom_active(row.item_btp)
        if not bom:
            frappe.throw(_("BTP {0} chưa có BOM active").format(row.item_btp))
        for item_code, can in _nhu_cau_bom(bom, flt(row.tong_kg)).items():
            _check(item_code, _kho_nguon(item_code, settings), can)

    thieu = []
    thieu_bot_nen = False
    for (item_code, kho), can in sorted(can_tong.items()):
        ton = flt(
            frappe.db.get_value(
                "Bin", {"item_code": item_code, "warehouse": kho}, "actual_qty"
            )
        ) + flt(sx_hom_nay.get(item_code, 0))
        if ton + 1e-6 >= can:
            continue
        if (frappe.get_cached_value("Item", item_code, "custom_sx_nhom") or "") == "BTP-Bot":
            thieu_bot_nen = True
        thieu.append(
            _("• {0} tại {1}: cần {2}, tồn {3} → THIẾU {4}").format(
                item_code, kho, flt(can, 3), flt(ton, 3), flt(can - ton, 3)
            )
        )

    if not thieu:
        return

    # Thiếu bột nền thường là do quên bấm Nghiền -> chỉ thẳng lô nào còn dở dang
    goi_y = _lo_con_o_xuong(doc) if thieu_bot_nen else []
    if cho_phep_ton_am():
        # Site đã bật Allow Negative Stock -> chặn ở đây là vô nghĩa (ERPNext bên
        # dưới cho ghi âm rồi). Vẫn phải NÓI, để không âm kho mà không ai biết.
        doc.flags.canh_bao_ton = (
            [_("⚠ Kho đang cho phép tồn âm — vẫn chốt nhưng các mục sau bị ghi âm:")]
            + thieu + goi_y
        )
        return
    frappe.throw(
        _("Không đủ tồn kho để chốt ngày:")
        + "<br>" + "<br>".join(thieu)
        + ("<br><br>" + "<br>".join(goi_y) if goi_y else "")
    )


# ─────────────────────────────────────────────── tầng 1 tự động ──


def _lo_con_o_xuong(doc):
    """Lô R đã xuất kho mà chưa nghiền xong — cảnh báo mềm khi chốt ngày (D31).

    Từ D31, nghiền là NÚT trên lưu đồ do QC bấm (kg ra cân thật), chốt ngày KHÔNG
    tự nhập bột nữa: đỗ nằm ở kho Xưởng dưới dạng đỗ ủ / đỗ vỡ, tự nhập sẽ trừ sai
    item + sai kho. Chốt ngày chỉ nhắc để QC không bỏ quên lô.
    """
    from sx.api.tang1 import lo_cho_nhap_bot

    ds = lo_cho_nhap_bot(truoc_ngay=doc.ngay)
    if not ds:
        return []
    return [
        _("Lô {0} ({1}, rang {2}) chưa nghiền xong — vào thẻ Luồng sản xuất bấm "
          "Nghiền bột, nếu không bột sẽ thiếu khi trộn.").format(
            lo["lo_rang"], lo["loai_dau"], lo["ngay_rang"])
        for lo in ds
    ]


# ─────────────────────────────────────────────── T2 / T3 ──


def _chot_tang_2(doc, chung_tu):
    """Mỗi dòng bao_me (topo-sort: màu → đường hoán → bột bánh/bột đậu):
    Batch -> WO -> SE Manufacture (RM FIFO, FG vào Kho BTP)."""
    settings = get_settings()
    rank = topo_rank_by_bom([r.item_btp for r in doc.bao_me])
    rows = sorted(doc.bao_me, key=lambda r: rank.get(r.item_btp, 0))

    for row in rows:
        qty = flt(row.tong_kg)
        if qty <= 0:
            continue
        bom = get_bom_active(row.item_btp)
        batch = tao_batch(row.item_btp, sinh_ma_lo(row.item_btp, doc.ngay), ngay_sx=doc.name)
        wo = tao_wo(
            settings.cong_ty, row.item_btp, qty, bom,
            source_wh=settings.kho_nvl, fg_wh=settings.kho_btp,
            ngay_sx=doc.name, planned_date=doc.ngay,
        )
        se = tao_se_manufacture(
            wo, qty, batch,
            kho_nguon=lambda item: _kho_nguon(item, settings),
            ngay=doc.ngay, ngay_sx=doc.name,
        )
        row.batch, row.wo, row.se = batch, wo.name, se.name
        chung_tu.append({"dt": "Work Order", "name": wo.name})
        chung_tu.append({"dt": "Stock Entry", "name": se.name})


# ─── TẦNG 3 KHÔNG CÒN SINH Ở ĐÂY NỮA (D59) ───
#
# Trước D59 chốt Vào hộp sinh luôn Work Order + SE Manufacture, nhập thành phẩm
# thẳng vào Kho TP. Giờ việc đó chuyển sang phiếu nhập kho (SX Phieu Nhap TP): thủ
# kho DUYỆT thì mới sinh chứng từ, và sinh theo số đã đóng.
#
# Vì sao đổi: chấm vào hộp là việc của QC, nhận hàng là việc của thủ kho, mà Kho TP
# thì xuất bán liên tục. Nếu chốt ngày nhập thẳng TP vào kho thì đến lúc thủ kho đi
# đếm, con số đã trộn với hàng vừa bán — không tách được "hộp lỗi" với "đã xuất",
# và cái nhầm đó ăn thẳng vào giá vốn. Để phiếu nhận là chứng từ DUY NHẤT sinh tồn
# kho TP thì hai việc tách hẳn nhau và không cần kho trung gian nào.
#
# Hệ quả: chốt Vào hộp giờ chỉ submit bảng + ghi lương khoán. Nó KHÔNG đụng kho,
# nên cũng không kiểm tồn — nguyên liệu chỉ bị trừ lúc duyệt phiếu nhập kho.


# ─────────────────────────────────────── phiếu lương sản lượng (D69) ──
#
# Từ D69 lương khoán ghi vào doctype RIÊNG của app: `SX Phieu Luong`.
# Trước đó app ghi thẳng vào `SalaryProduct` của app lam-luong — bỏ hẳn, lý do đầy
# đủ trong sx/sx/doctype/sx_phieu_luong/sx_phieu_luong.py. Tóm tắt: trần 6 loại
# mỗi ngày, công thức nằm trong Client Script nên gọi bằng API thì không chạy, và
# ghi đè dữ liệu app khác bằng ignore_permissions.
#
# App KHÔNG còn đọc/ghi gì của app lương nữa.


def _ghi_luong_khoan(doc, bang):
    """Ghi sản lượng của ngày vào PHIẾU LƯƠNG THÁNG của từng công nhân (D69).

    Từ D69 dùng doctype riêng `SX Phieu Luong` thay cho SalaryProduct của app lương
    (lý do đầy đủ trong docstring của doctype đó). Ba khác biệt đáng kể:
      · KHÔNG còn trần 6 loại/ngày — ghi theo mã hàng thì một người dễ quá 6 mã.
      · Đơn giá chốt tại thời điểm ghi, lấy từ bảng đơn giá của THÁNG đó.
      · Mọi công thức tính ở server lúc validate, gọi API hay bấm Desk đều một kết quả.

    Gộp theo (nhân viên, mã hàng, cách làm): cùng một người vào cùng một mã, cùng
    cách làm, ghi làm nhiều lần trong ngày thì cộng lại thành một dòng.
    Trả [{phieu, employee, ngay}] để huỷ chốt gỡ đúng dòng.
    """
    ngay = getdate(doc.ngay)

    gop = {}
    for r in bang.dong:
        if not r.san_pham:
            frappe.throw(_("Dòng {0}: chưa chọn mã hàng.").format(r.idx))
        key = (r.nhan_vien, r.san_pham, r.cach_lam or "")
        g = gop.setdefault(key, {"sl": 0, "dg": flt(r.don_gia)})
        g["sl"] += cint(r.so_hop)
        # Cùng mã cùng cách làm thì đơn giá phải như nhau; lấy giá lớn nhất nếu vì
        # lý do gì đó lệch, để không âm thầm trả thiếu cho công nhân.
        g["dg"] = max(g["dg"], flt(r.don_gia))

    theo_nguoi = {}
    for (nv, sp, cl), g in gop.items():
        theo_nguoi.setdefault(nv, []).append((sp, cl or None, g["sl"], g["dg"]))

    # Ăn ca / ăn đêm (D30): người CHỈ được chấm ăn (không vào hộp) vẫn phải có dòng
    an = {}
    for r in bang.get("an_ca") or []:
        if not (cint(r.an_ca) or cint(r.an_dem)):
            continue
        an[r.nhan_vien] = (cint(r.an_ca), cint(r.an_dem))
        theo_nguoi.setdefault(r.nhan_vien, [])

    ds_ghi = []
    for nv, cong_viec in theo_nguoi.items():
        co_an_ca, co_an_dem = an.get(nv, (0, 0))
        phieu = _phieu_luong_thang(nv, ngay)
        _thay_ngay(phieu, ngay, cong_viec, co_an_ca, co_an_dem)
        phieu.flags.ignore_permissions = True
        phieu.save()
        ds_ghi.append({"phieu": phieu.name, "employee": nv, "ngay": str(ngay)})
    return ds_ghi


def _phieu_luong_thang(employee, ngay):
    """Phiếu lương NHÁP của người đó trong tháng chứa `ngay`; chưa có thì tạo.

    Phiếu ĐÃ DUYỆT thì dừng hẳn: sửa lương đã chốt phải là quyết định của người
    làm lương, không phải hệ quả âm thầm của một lần chốt ngày.
    """
    chung = {"employee": employee, "thang": ngay.month, "nam": ngay.year}
    da_duyet = frappe.db.get_value("SX Phieu Luong", dict(chung, docstatus=1), "name")
    if da_duyet:
        ten = frappe.db.get_value("Employee", employee, "employee_name") or employee
        frappe.throw(
            _("Phiếu lương {0} của {1} tháng {2}/{3} ĐÃ DUYỆT — không ghi thêm được. "
              "Huỷ duyệt phiếu lương đó trước nếu thật sự cần sửa.").format(
                da_duyet, ten, ngay.month, ngay.year)
        )
    ten_phieu = frappe.db.get_value("SX Phieu Luong", dict(chung, docstatus=0), "name")
    if ten_phieu:
        return frappe.get_doc("SX Phieu Luong", ten_phieu)
    phieu = frappe.new_doc("SX Phieu Luong")
    phieu.employee = employee
    phieu.thang = ngay.month
    phieu.nam = ngay.year
    return phieu


def _thay_ngay(phieu, ngay, cong_viec, an_ca, an_dem):
    """Ghi đè TRỌN dữ liệu của MỘT ngày trong phiếu tháng.

    Ghi đè chứ không cộng dồn: chốt lại ngày sau khi sửa bảng vào hộp phải ra đúng
    số mới, không phải số cũ cộng số mới. Ngày khác trong phiếu không bị đụng tới.
    """
    ngay_s = str(ngay)
    phieu.set("chi_tiet", [r for r in phieu.chi_tiet if str(getdate(r.ngay)) != ngay_s])
    for sp, cach_lam, sl, dg in cong_viec:
        if cint(sl) <= 0:
            continue
        phieu.append("chi_tiet", {
            "ngay": ngay, "san_pham": sp, "cach_lam": cach_lam,
            "so_luong": cint(sl), "don_gia": flt(dg),
        })
    dong = next((r for r in phieu.dong if str(getdate(r.ngay)) == ngay_s), None)
    if not dong:
        dong = phieu.append("dong", {"ngay": ngay})
    dong.an_ca = cint(an_ca)
    dong.an_dem = cint(an_dem)


def _go_luong_khoan(ds_ghi):
    """Gỡ dữ liệu của ngày đó khỏi phiếu lương tháng (huỷ chốt).

    Chỉ gỡ ĐÚNG ngày; các ngày khác trong tháng giữ nguyên. Phiếu rỗng hẳn thì xoá,
    để danh sách phiếu lương không đầy phiếu trắng của những ngày đã huỷ.
    """
    log = []
    for g in ds_ghi or []:
        ten, ngay_s = g.get("phieu"), str(g.get("ngay"))
        if not ten or not frappe.db.exists("SX Phieu Luong", ten):
            continue
        phieu = frappe.get_doc("SX Phieu Luong", ten)
        if phieu.docstatus != 0:
            log.append(_("Phiếu lương {0} đã duyệt — KHÔNG gỡ được, phải huỷ duyệt "
                         "rồi sửa tay.").format(ten))
            continue
        phieu.set("chi_tiet",
                  [r for r in phieu.chi_tiet if str(getdate(r.ngay)) != ngay_s])
        phieu.set("dong", [r for r in phieu.dong if str(getdate(r.ngay)) != ngay_s])
        phieu.flags.ignore_permissions = True
        if not phieu.dong and not phieu.chi_tiet:
            phieu.delete()
            log.append(_("Xoá phiếu lương rỗng {0}").format(ten))
        else:
            phieu.save()
            log.append(_("Gỡ ngày {0} khỏi phiếu lương {1}").format(ngay_s, ten))
    return log


# ─────────────────────────────────────────────── cảnh báo mềm ──


def _canh_bao_mem(doc):
    """Không chặn: tồn bột bánh < lượng cán báo (quên báo mẻ trộn) + lô còn ở xưởng."""
    settings = get_settings()
    canh_bao = list(doc.flags.get("canh_bao_ton") or []) + _lo_con_o_xuong(doc)
    can_theo_loai = {}
    for row in doc.bao_can:
        can_theo_loai[row.item_bot_banh] = can_theo_loai.get(row.item_bot_banh, 0) + flt(row.so_me)
    for item, so_me_can in can_theo_loai.items():
        bom = get_bom_active(item)
        co_me = flt(frappe.db.get_value("BOM", bom, "custom_co_me_chuan_kg")) if bom else 0
        kg_can = so_me_can * co_me
        ton = flt(
            frappe.db.get_value(
                "Bin", {"item_code": item, "warehouse": settings.kho_btp}, "actual_qty"
            )
        )
        if kg_can > ton + 1e-6:
            canh_bao.append(
                _("Cán {0} ({1} kg) nhiều hơn tồn bột bánh ({2} kg) — có thể quên báo mẻ trộn.")
                .format(item, flt(kg_can, 1), flt(ton, 1))
            )
    return canh_bao


# ─────────────────────────────────────────────── huỷ ngược (hook) ──


@frappe.whitelist()
def chung_tu_ngay(ngay_sx):
    """Danh sách CHỨNG TỪ đã tạo cho 1 ngày, kèm link Desk để tra cứu (D29).

    Gom theo nhóm: phiếu ngày · phiếu nhập bột (tầng 1) · lệnh SX + phiếu kho
    (tầng 2/3, đọc từ `ds_wo_se` đúng thứ tự sinh) · batch · bảng vào hộp ·
    phiếu lương khoán. Đọc số liệu thật của từng chứng từ để nhìn là hiểu, khỏi
    phải mở từng cái.
    """
    guard_card("chotngay")
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    nhom = []

    def _them(ten_nhom, dt, name, mo_ta=""):
        if not name or not frappe.db.exists(dt, name):
            return
        trang_thai = frappe.db.get_value(dt, name, "docstatus")
        for g in nhom:
            if g["nhom"] == ten_nhom:
                muc = g
                break
        else:
            muc = {"nhom": ten_nhom, "dong": []}
            nhom.append(muc)
        # Chỉ trả link khi user THẬT SỰ mở được trên Desk — 2 role QC cố tình không
        # có DocPerm trên WO/SE/Batch (spec §4), đưa link vào chỉ tổ bấm ra lỗi quyền.
        xem_duoc = frappe.has_permission(dt, "read")
        muc["dong"].append({
            "dt": dt,
            "name": name,
            "mo_ta": mo_ta,
            "docstatus": cint(trang_thai) if trang_thai is not None else 0,
            "url": frappe.utils.get_url_to_form(dt, name) if xem_duoc else None,
        })

    _them(_("Phiếu ngày"), "SX Ngay San Xuat", doc.name, doc.trang_thai or "")

    for ct in json.loads(doc.ds_wo_se) if doc.ds_wo_se else []:
        dt, name = ct.get("dt"), ct.get("name")
        _them(_nhom_chung_tu(dt), dt, name, _mo_ta_chung_tu(dt, name))

    for r in doc.bao_me:
        _them(_("Lô sản xuất (batch)"), "Batch", r.batch,
              _("{0} — {1} kg").format(r.item_btp, flt(r.tong_kg, 2)))

    ten_bang = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": doc.name, "docstatus": ("<", 2)}, "name"
    )
    if ten_bang:
        tong = frappe.db.get_value("SX Bang Vao Hop", ten_bang, ["tong_hop", "tong_tien"])
        _them(_("Bảng vào hộp"), "SX Bang Vao Hop", ten_bang,
              _("{0} sản phẩm · {1}").format(cint(tong[0]), frappe.utils.fmt_money(tong[1], currency="VND")))

    for g in json.loads(doc.salary_products_json) if doc.salary_products_json else []:
        ten_nv = frappe.db.get_value("Employee", g.get("employee"), "employee_name") or ""
        _them(_("Phiếu lương sản lượng"), "SX Phieu Luong", g.get("phieu"), ten_nv)

    return {"ngay": str(doc.ngay), "docstatus": doc.docstatus, "nhom": nhom}


def _nhom_chung_tu(dt):
    return {
        "Work Order": _("Lệnh sản xuất"),
        "Stock Entry": _("Phiếu kho"),
        "SX Nhap Bot": _("Nhập bột (tầng 1)"),
    }.get(dt, dt)


def _mo_ta_chung_tu(dt, name):
    """Một dòng mô tả đủ để nhận ra chứng từ mà không phải mở."""
    try:
        if dt == "Work Order":
            d = frappe.db.get_value(
                "Work Order", name, ["production_item", "qty", "status"], as_dict=True
            )
            return _("{0} × {1} ({2})").format(d.production_item, flt(d.qty, 2), d.status)
        if dt == "Stock Entry":
            d = frappe.db.get_value(
                "Stock Entry", name, ["stock_entry_type", "fg_completed_qty", "posting_date"],
                as_dict=True,
            )
            return _("{0} — {1}").format(
                d.stock_entry_type or "", frappe.utils.formatdate(d.posting_date)
            )
        if dt == "SX Nhap Bot":
            d = frappe.db.get_value(
                "SX Nhap Bot", name, ["lo_rang", "bot_kg"], as_dict=True
            )
            return _("lô {0} — {1} kg bột").format(d.lo_rang or "", flt(d.bot_kg, 2))
    except Exception:
        pass
    return ""


@frappe.whitelist()
def huy_chot_ngay(ngay_sx, ly_do=None):
    """HUỶ CHỐT để sửa lại số liệu (D24).

    Huỷ phiếu ngày -> hook on_cancel_ngay đảo ngược TOÀN BỘ: SE/WO tầng 3 → tầng 2
    → phiếu nhập bột (hoàn đỗ) → bảng vào hộp → gỡ dòng lương khoán của ngày đó.
    Rồi TỰ TẠO LẠI phiếu nháp (amend) giữ nguyên báo mẻ / báo cán / sự cố / bảng vào
    hộp để QC sửa con số cần sửa và chốt lại — không phải gõ lại từ đầu.

    Trả summary phiếu nháp mới.
    """
    guard_card("chotngay")
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    if doc.docstatus != 1:
        frappe.throw(
            _("Phiếu ngày {0} chưa chốt (hoặc đã huỷ) — không cần huỷ chốt.").format(ngay_sx)
        )

    bang_cu = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": doc.name, "docstatus": 1}, "name"
    )

    doc.flags.ignore_permissions = True
    doc.cancel()  # hook on_cancel_ngay đảo ngược toàn bộ chứng từ + lương

    cu = frappe.get_doc("SX Ngay San Xuat", ngay_sx)  # đọc lại: hook vừa ghi ghi_chu
    moi = frappe.copy_doc(cu)
    moi.docstatus = 0   # copy_doc chỉ tự xoá docstatus khi KHÔNG chạy trong test
    moi.amended_from = cu.name
    moi.ds_wo_se = None
    moi.ds_wo_se_ghiso = None
    moi.salary_products_json = None
    moi.chot_ghiso = 0
    moi.chot_ghiso_luc = None
    moi.chot_ghiso_boi = None
    moi.chot_vaohop = 0
    moi.chot_vaohop_luc = None
    moi.chot_vaohop_boi = None
    moi.tong_hop_tp = 0
    moi.tong_luong_sp = 0
    for r in moi.bao_me:
        r.batch = None  # batch sinh lại khi chốt lại (tao_batch idempotent)
    dau_vet = _("[Huỷ chốt {0}] {1}").format(
        frappe.utils.now_datetime().strftime("%d/%m %H:%M"), (ly_do or "").strip() or _("không ghi lý do")
    )
    moi.ghi_chu = ((cu.ghi_chu or "") + "\n" + dau_vet).strip()
    moi.flags.ignore_permissions = True
    moi.insert()

    if bang_cu:
        b_cu = frappe.get_doc("SX Bang Vao Hop", bang_cu)
        b_moi = frappe.copy_doc(b_cu)
        b_moi.docstatus = 0
        b_moi.amended_from = b_cu.name
        b_moi.ngay_sx = moi.name
        b_moi.flags.ignore_permissions = True
        b_moi.insert()

    from sx.api.portal import _ngay_summary  # import trễ: tránh vòng lặp import

    return _ngay_summary(moi.name)


def on_cancel_ngay(doc, method=None):
    """Huỷ chuỗi ngược theo ds_wo_se, ĐẢO thứ tự sinh: SE/WO T3 -> SE/WO T2 ->
    SX Nhap Bot (nhả bột + hoàn đỗ, huỷ sau cùng vì T2 vừa tiêu thụ bột đó)
    -> huỷ bảng vào hộp -> xoá SalaryProduct. Batch giữ (đã có ledger).

    Chỉ thu hồi SX Nhap Bot do CHÍNH lần chốt này tạo (có trong ds_wo_se) — phiếu
    nhập bột người dùng tự tạo trước đó không bị đụng."""
    log = []
    # Đảo NGƯỢC toàn tuyến: tầng 3 trước (nó tiêu thụ bột của tầng 2), rồi tầng 2.
    # Ngày cũ trước D55 có mọi thứ trong ds_wo_se; ds_wo_se_ghiso rỗng nên vẫn đúng.
    chung_tu = (json.loads(doc.ds_wo_se) if doc.ds_wo_se else []) \
        + (json.loads(doc.ds_wo_se_ghiso) if doc.get("ds_wo_se_ghiso") else [])
    for ct in reversed(chung_tu):
        cancel_doc(ct.get("dt"), ct.get("name"), log)

    bang = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": doc.name, "docstatus": 1}, "name"
    )
    cancel_doc("SX Bang Vao Hop", bang, log)

    if doc.salary_products_json:
        log.extend(_go_luong_khoan(json.loads(doc.salary_products_json)))

    batches = [r.batch for r in doc.bao_me if r.batch]
    if batches:
        log.append("Batch giữ nguyên (đã có ledger): " + ", ".join(batches))

    # Hai cờ chốt phải tắt theo, nếu không bản amend copy sang sẽ tưởng đã chốt rồi
    for f in ("chot_ghiso", "chot_vaohop"):
        doc.db_set(f, 0, update_modified=False)

    if log:
        ghi_chu = (doc.ghi_chu or "") + "\n[Huỷ ngày] " + "; ".join(log)
        doc.db_set("ghi_chu", ghi_chu.strip(), update_modified=False)


def _huy_nua(doc, nua, field_ct, ly_do, dep=None):
    """Huỷ NỬA chốt khi phiếu ngày còn nháp: đảo chứng từ của đúng nửa đó rồi tắt cờ.

    Phiếu đã submit (cả hai nửa xong) thì KHÔNG huỷ lẻ được — Frappe không lùi
    docstatus, và đảo lẻ một nửa của phiếu đã submit sẽ để lại phiếu "đã chốt" mà
    chứng từ đã bị rút. Trường hợp đó dùng HUỶ CHỐT NGÀY (đảo cả hai, trả lại bản
    nháp giữ nguyên số liệu).
    """
    nhan = "Ghi sổ" if nua == "ghiso" else "Vào hộp"
    if not cint(doc.get(f"chot_{nua}")):
        frappe.throw(_("Phần {0} chưa chốt — không có gì để huỷ.").format(nhan))
    if doc.docstatus == 1:
        frappe.throw(
            _("Ngày này đã chốt CẢ HAI phần nên phiếu ngày đã khoá. Dùng HUỶ CHỐT "
              "NGÀY để mở lại (số liệu giữ nguyên), rồi chốt lại phần cần sửa.")
        )
    if doc.docstatus == 2:
        frappe.throw(_("Phiếu ngày đã huỷ."))
    if dep:
        frappe.throw(dep)

    log = []
    for ct in reversed(json.loads(doc.get(field_ct) or "[]")):
        cancel_doc(ct.get("dt"), ct.get("name"), log)
    doc.set(field_ct, None)
    doc.set(f"chot_{nua}", 0)
    doc.set(f"chot_{nua}_luc", None)
    doc.set(f"chot_{nua}_boi", None)
    doc.trang_thai = "Đang chạy" if not cint(
        doc.chot_ghiso if nua == "vaohop" else doc.chot_vaohop) else "Chốt một phần"
    dau_vet = _("[Huỷ chốt {0} {1}] {2}").format(
        nhan, now_datetime().strftime("%d/%m %H:%M"),
        (ly_do or "").strip() or _("không ghi lý do"))
    doc.ghi_chu = ((doc.ghi_chu or "") + "\n" + dau_vet
                   + ((" · " + "; ".join(log)) if log else "")).strip()
    doc.flags.ignore_permissions = True
    doc.save()
    return log


@frappe.whitelist()
def huy_chot_ghiso(ngay_sx, ly_do=None):
    """Mở lại nửa Ghi sổ: đảo chứng từ tầng 2, cho sửa báo mẻ rồi chốt lại."""
    guard_card("chotngay")
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    # Tầng 3 đã tiêu thụ chính bột mà tầng 2 sinh ra -> rút bột ra trước khi rút
    # thành phẩm là để lại kho âm. Bắt gỡ theo đúng thứ tự ngược.
    # Không còn ràng buộc "phải huỷ Vào hộp trước" (D59 — chốt Vào hộp không đụng
    # kho). Nhưng phiếu nhập kho ĐÃ DUYỆT thì có: nó đã trừ chính lượng bột này.
    from sx.api.khotp import phieu_da_duyet_sau

    dep = None
    da = phieu_da_duyet_sau(doc.chot_ghiso_luc)
    if da:
        dep = _("Phiếu nhập kho {0} đã duyệt sau khi chốt Ghi sổ và đã trừ bột của "
                "mẻ này. Huỷ phiếu đó trước, nếu không rút bột ra sẽ để kho âm."
                ).format(", ".join(da))
    log = _huy_nua(doc, "ghiso", "ds_wo_se_ghiso", ly_do, dep)
    return {"name": doc.name, "log": log}


@frappe.whitelist()
def huy_chot_vaohop(ngay_sx, ly_do=None):
    """Mở lại nửa Vào hộp: đảo chứng từ tầng 3, gỡ lương khoán, mở lại bảng."""
    guard_card("chotngay")
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)
    # Không còn guard theo phiếu nhập kho (D62): phiếu nhập kho là chứng từ độc
    # lập, không lấy số từ bảng vào hộp, nên sửa bảng không ảnh hưởng gì tới nó.
    log = _huy_nua(doc, "vaohop", "ds_wo_se", ly_do)   # ds_wo_se rỗng từ D59

    bang = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": doc.name, "docstatus": 1}, "name")
    if bang:
        b = frappe.get_doc("SX Bang Vao Hop", bang)
        b.flags.ignore_permissions = True
        b.cancel()
        moi = frappe.copy_doc(b)
        moi.docstatus = 0
        moi.amended_from = b.name
        moi.ngay_sx = doc.name
        moi.flags.ignore_permissions = True
        moi.insert()
        log.append(_("Bảng vào hộp mở lại: {0}").format(moi.name))

    if doc.salary_products_json:
        log.extend(_go_luong_khoan(json.loads(doc.salary_products_json)))
        doc.db_set("salary_products_json", None, update_modified=False)
    doc.db_set("tong_hop_tp", 0, update_modified=False)
    doc.db_set("tong_luong_sp", 0, update_modified=False)
    return {"name": doc.name, "log": log}
