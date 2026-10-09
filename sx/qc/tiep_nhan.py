"""Tiếp nhận nguyên liệu (BM.07.03) — gắn vào PHIẾU NHẬP MUA (Purchase Receipt, W10)
và hoá đơn mua có trừ kho (Purchase Invoice "Update Stock" — đường cũ trước D138).

W10 (D138) — tài liệu 08/10: chuyển sang phiếu nhập mua; giấy tờ theo NGUỒN của NCC
(sx/qc/ncc.py, W09): nhập khẩu → COA từng lô; trong nước → phiếu kiểm nghiệm năm của NCC
còn hạn (hoặc COA lô); aflatoxin cho nhóm hàng khai ở SX QC Setting; lô Không đạt /
Cách ly → tự nhập KHO CÁCH LY (SX Settings); cát rang không đòi giấy tờ thực phẩm.
NCC loại thực phẩm thì MỌI dòng phải có kết luận tiếp nhận mới duyệt được phiếu.

Vì sao kết luận nằm ở TỪNG DÒNG HÀNG chứ không ở đầu phiếu: BM.07.03 kiểm theo
LÔ. Một hoá đơn có thể có ba mặt hàng ba lô khác nhau; để một ô kết luận ở đầu
phiếu thì ba lô chung một câu trả lời, và cái lô có vấn đề biến mất trong đó.

Hai luật ÉP kết luận (không phải gợi ý — đây là cổng an toàn thực phẩm):
  · nhóm hàng bắt buộc có COA vi sinh mà COA = Không  → Cách ly
  · độ ẩm vượt ngưỡng                                  → Cách ly
    W40 (D162): đỗ, lạc KHÔNG đo độ ẩm khi nhận (quyết định 09/10/2026), ô Độ ẩm ẩn, ngưỡng mặc định
    trống = không kiểm. Luật giữ cho site tự bật lại với nhóm hàng khác.
Ép chứ không chặn: hàng đã về tới sân rồi, chặn lưu hoá đơn không làm hàng biến
mất — nó chỉ làm người ta bỏ trống ô QC cho xong việc.

Một luật CHẶN: kết luận "Đạt" trong khi cảm quan "Không đạt" là mâu thuẫn trên
một hồ sơ an toàn thực phẩm, không phải một đánh giá — gần như chắc chắn là gõ
nhầm dòng.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

from sx.qc import ncc as NCC
from sx.qc.nguong import nguong

DAT = "Đạt"
KHONG_DAT = "Không đạt"
CACH_LY = "Cách ly"
KHONG = "Không"

# Dòng nào không ghi gì ở phần QC thì bỏ qua hẳn: hoá đơn mua bao bì, dịch vụ,
# vật tư sửa chữa… không phải nguyên liệu và không có gì để kiểm.
O_QC = ("custom_ncc_lo", "custom_co_cq", "custom_coa_vi_sinh",
        "custom_aflatoxin", "custom_do_am", "custom_cam_quan_dat",
        "custom_ket_luan")


def co_kiem(dong):
    """Dòng này có ghi gì ở phần QC không."""
    for o in O_QC:
        v = dong.get(o)
        if v not in (None, "", 0, 0.0):
            return True
    return False


def _nhom_va_cha(item_group, tra_cha, sau=6):
    """Nhóm hàng + mọi nhóm cha của nó.

    Đi ngược lên cây vì nhóm hàng là cây: khai "Phụ liệu bột" ở Setting mà hàng
    nằm ở nhóm con "Phụ liệu bột / Sữa" thì vẫn phải bắt buộc có COA. Chặn độ
    sâu để một cây bị vòng (dữ liệu hỏng) không treo cả lần lưu hoá đơn.
    """
    ra, g = [], item_group
    while g and len(ra) < sau:
        ra.append(g)
        g = tra_cha(g)
        if g in ra:
            break
    return ra


def kiem_dong(dong, item_group, ng, tra_cha):
    """Xét MỘT dòng hàng. Hàm thuần — trả (kết luận mới | None, cảnh báo | None).

    `dong` là dict-like; không đọc DB, không ghi gì. Test gọi thẳng nó.
    """
    kl = dong.get("custom_ket_luan") or ""

    do_am = flt(dong.get("custom_do_am"))
    toi_da = flt(ng.get("do_am_toi_da"))
    if do_am and toi_da and do_am > toi_da:
        return CACH_LY if kl != KHONG_DAT else kl, _(
            "Độ ẩm {0}% vượt ngưỡng {1}% → chuyển Cách ly").format(
                flt(do_am, 1), flt(toi_da, 1))

    can_coa = set(ng.get("nhom_can_coa") or ())
    if can_coa and item_group and dong.get("custom_coa_vi_sinh") == KHONG:
        if set(_nhom_va_cha(item_group, tra_cha)) & can_coa:
            return CACH_LY if kl != KHONG_DAT else kl, _(
                "Nhóm {0} bắt buộc có COA vi sinh mà lô này không có "
                "→ chuyển Cách ly").format(item_group)
    return None, None


def kiem_giay_to(dong, ncc, ngay, item_group, nhom_aflatoxin, tra_cha):
    """Luật giấy tờ W10 cho MỘT dòng — hàm thuần. Trả (kết luận mới | None, cảnh báo |
    None, câu ghi vào ô "Giấy tờ lô"). `ncc` = sx.qc.ncc.thong_tin(supplier)."""
    kl = dong.get("custom_ket_luan") or ""
    loai, nguon = (ncc or {}).get("loai"), (ncc or {}).get("nguon")
    if loai == NCC.CAT:
        return None, None, _("Cát rang — không yêu cầu giấy tờ thực phẩm")
    ep, giay = [], []
    if loai in NCC.THUC_PHAM:
        coa = dong.get("custom_coa_vi_sinh") == "Có"
        if nguon == NCC.NHAP_KHAU:
            giay.append(_("Nhập khẩu — COA lô: {0}").format(_("có") if coa else _("KHÔNG")))
            if not coa:
                ep.append(_("hàng nhập khẩu phải có COA từng lô"))
        elif nguon == NCC.TRONG_NUOC:
            pkn = NCC.pkn_con_han(ncc.get("ho_so"), ngay)
            if pkn:
                giay.append(_("Trong nước — phiếu kiểm nghiệm năm {0}{1}").format(
                    pkn.get("so_hieu") or "", _(" còn hạn đến {0}").format(
                        getdate(pkn["het_han"]).strftime("%d/%m/%Y")) if pkn.get("het_han") else ""))
            elif coa:
                giay.append(_("Trong nước — không có phiếu kiểm nghiệm năm còn hạn, có COA lô"))
            else:
                giay.append(_("Trong nước — THIẾU phiếu kiểm nghiệm năm còn hạn"))
                ep.append(_("NCC trong nước chưa có phiếu kiểm nghiệm năm còn hạn và lô không có COA"))
        else:
            giay.append(_("NCC chưa khai nguồn trong nước / nhập khẩu"))
    can_af = set(nhom_aflatoxin or ())
    if can_af and item_group and set(_nhom_va_cha(item_group, tra_cha)) & can_af:
        giay.append(_("Aflatoxin: {0}").format(dong.get("custom_aflatoxin") or _("chưa ghi")))
        if dong.get("custom_aflatoxin") != "Có":
            ep.append(_("nhóm {0} phải có kết quả aflatoxin").format(item_group))
    if ep:
        return (CACH_LY if kl != KHONG_DAT else kl), "; ".join(ep) + _(" → chuyển Cách ly"), " · ".join(giay)
    return None, None, " · ".join(giay)


def mau_thuan(dong):
    """Kết luận Đạt trong khi cảm quan Không đạt."""
    return (dong.get("custom_ket_luan") == DAT
            and dong.get("custom_cam_quan_dat") == KHONG_DAT)


# ── móc vào Purchase Receipt / Purchase Invoice ───────────────────────────


def _tra_cha(item_group):
    return frappe.get_cached_value("Item Group", item_group, "parent_item_group")


def _item_group(item_code):
    return frappe.get_cached_value("Item", item_code, "item_group")


def _ngay(doc):
    return doc.get("posting_date") or frappe.utils.nowdate()


def _kho_cach_ly():
    try:
        return frappe.get_cached_doc("SX Settings").get("kho_cach_ly") or None
    except Exception:
        return None


def _la_nhap_kho(doc):
    """Phiếu nhập mua, hoặc hoá đơn mua có trừ kho. Phiếu trả hàng NCC: không xét."""
    if frappe.utils.cint(doc.get("is_return")):
        return False
    return doc.doctype == "Purchase Receipt" or frappe.utils.cint(doc.get("update_stock"))


def validate(doc, method=None):
    ng = nguong()
    canh = []
    ncc = NCC.thong_tin(doc.get("supplier")) if _la_nhap_kho(doc) else {}
    ngay = _ngay(doc)
    kho_cl = _kho_cach_ly()
    for r in doc.get("items") or []:
        if ncc.get("loai") in NCC.THUC_PHAM or co_kiem(r):
            kl, bao, giay = kiem_giay_to(r, ncc, ngay, _item_group(r.item_code),
                                         ng.get("nhom_can_aflatoxin"), _tra_cha)
            r.custom_giay_to = giay
            if kl and kl != r.get("custom_ket_luan"):
                r.custom_ket_luan = kl
            if bao:
                canh.append(_("Dòng {0} ({1}): {2}").format(r.idx, r.item_code, bao))
        if not co_kiem(r):
            continue
        if mau_thuan(r):
            frappe.throw(_(
                "Dòng {0} ({1}): kết luận 'Đạt' nhưng cảm quan 'Không đạt'. "
                "Sửa một trong hai — hồ sơ an toàn thực phẩm không nói hai câu "
                "trái nhau về cùng một lô.").format(r.idx, r.item_code))
        kl, bao = kiem_dong(r, _item_group(r.item_code), ng, _tra_cha)
        if kl and kl != r.get("custom_ket_luan"):
            r.custom_ket_luan = kl
        if bao:
            canh.append(_("Dòng {0} ({1}): {2}").format(r.idx, r.item_code, bao))
    # W10: lô Không đạt / Cách ly nhập KHO CÁCH LY — không lẫn vào kho nguyên liệu dùng.
    if _la_nhap_kho(doc):
        cl = [r for r in doc.get("items") or [] if r.get("custom_ket_luan") in (KHONG_DAT, CACH_LY)]
        if cl and kho_cl:
            doi = [str(r.idx) for r in cl if r.get("warehouse") != kho_cl]
            for r in cl:
                r.warehouse = kho_cl
            if doi:
                canh.append(_("Dòng {0}: lô Không đạt / Cách ly → nhập {1}").format(", ".join(doi), kho_cl))
        elif cl:
            canh.append(_("Chưa khai Kho cách ly (SX Settings) — lô Không đạt / Cách ly đang nhập "
                          "chung kho nguyên liệu."))
    if canh:
        # msgprint chứ không throw: xem chú thích đầu file — ép kết luận, không
        # chặn lưu. Nhưng PHẢI nói ra, đừng sửa lặng lẽ ô người ta vừa gõ.
        frappe.msgprint(_("Kiểm tra nguyên liệu đầu vào:") + "<br>"
                        + "<br>".join(canh), indicator="orange", alert=False)


def on_submit(doc, method=None):
    """Duyệt hoá đơn = lập phiếu sự cố cho mọi lô Không đạt / Cách ly.

    Trước đó chặn dòng ĐÃ KIỂM DỞ mà bỏ trống kết luận. Đây là lỗ im lặng: luật
    sinh sự cố bám vào ô kết luận, nên bỏ trống nó là cách chắc chắn nhất để một
    lô có vấn đề đi vào kho mà không để lại dấu vết nào — mà trên màn hình thì
    dòng đó trông y hệt dòng đã kiểm xong.

    Chỉ chặn dòng đã ghi thứ gì đó ở phần QC. Hoá đơn mua bao bì, dịch vụ, vật
    tư sửa chữa không có gì để kiểm và đi qua như thường.
    """
    thieu = [r for r in (doc.get("items") or [])
             if co_kiem(r) and not r.get("custom_ket_luan")]
    # W10: NCC thực phẩm (nguyên liệu, phụ gia) — MỌI dòng nhập kho phải được kiểm tiếp
    # nhận. Bỏ trống cả phần QC là lô thực phẩm vào kho không qua BM.07.03.
    if _la_nhap_kho(doc) and NCC.thong_tin(doc.get("supplier")).get("loai") in NCC.THUC_PHAM:
        thieu += [r for r in (doc.get("items") or [])
                  if not co_kiem(r) and not r.get("custom_ket_luan") and r not in thieu]
    if thieu:
        frappe.throw(_(
            "Chưa có kết luận cho {0}: {1}.<br><br>Đã ghi thông tin kiểm thì "
            "phải chốt Đạt / Không đạt / Cách ly — bỏ trống ô này là lô đó đi "
            "vào kho mà không để lại dấu vết nào.").format(
                _("dòng") if len(thieu) == 1 else _("các dòng"),
                ", ".join(f"{r.idx} ({r.item_code})" for r in thieu)))

    for r in doc.get("items") or []:
        if r.get("custom_ket_luan") not in (KHONG_DAT, CACH_LY):
            continue
        khoa = f"{doc.name}#{r.idx}"
        if frappe.db.exists("SX Su Co", {"khoa_cu": khoa}):
            continue        # duyệt lại sau khi huỷ: đừng đẻ phiếu thứ hai
        sc = frappe.get_doc({
            "doctype": "SX Su Co",
            "ngay": doc.posting_date,
            "nguon": "Tiếp nhận NL",
            "loai": "PRP",
            # Không đạt là hàng hỏng; Cách ly là hàng chờ quyết định. Chỉ cái
            # đầu mới là mức Cao — để Cao cho cả hai thì Cao hết nghĩa.
            "muc_do": "Cao" if r.custom_ket_luan == KHONG_DAT else "Thường",
            "muc": _("Tiếp nhận: {0}").format(r.item_code),
            "mo_ta": _("{0} — lô NCC {1}: kết luận {2}{3}").format(
                r.item_name or r.item_code, r.get("custom_ncc_lo") or "—",
                r.custom_ket_luan,
                _(" (độ ẩm {0}%)").format(flt(r.custom_do_am, 1))
                if flt(r.custom_do_am) else ""),
            "lo_anh_huong": r.get("custom_ncc_lo") or "",
            "so_luong": f"{flt(r.qty, 3)} {r.uom or ''}".strip(),
            "nguoi_xu_ly": doc.get("custom_nguoi_kiem") or None,
            "khoa_cu": khoa,
            "trang_thai": "Mở",
        })
        if r.get("batch_no"):
            sc.append("ds_lo", {"batch": r.batch_no})       # W11: gắn đúng lô NCC
        # Thủ kho duyệt hoá đơn không có quyền tạo phiếu sự cố, nhưng hệ thống
        # PHẢI tạo được — nếu quyền chặn được việc này thì "bỏ qua lô không đạt"
        # chỉ còn là chuyện bấm bằng tài khoản nào.
        sc.insert(ignore_permissions=True)
