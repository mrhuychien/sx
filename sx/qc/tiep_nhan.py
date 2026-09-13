"""Tiếp nhận nguyên liệu (BM.07.03) — gắn vào Purchase Invoice.

Vì sao Purchase Invoice chứ không Purchase Receipt như spec viết: kho nguyên
liệu của nhà máy này nhập thẳng bằng hoá đơn mua, không lập phiếu nhập kho
riêng. Bám spec ở đây nghĩa là dựng một chứng từ không ai lập.

Vì sao kết luận nằm ở TỪNG DÒNG HÀNG chứ không ở đầu phiếu: BM.07.03 kiểm theo
LÔ. Một hoá đơn có thể có ba mặt hàng ba lô khác nhau; để một ô kết luận ở đầu
phiếu thì ba lô chung một câu trả lời, và cái lô có vấn đề biến mất trong đó.

Hai luật ÉP kết luận (không phải gợi ý — đây là cổng an toàn thực phẩm):
  · nhóm hàng bắt buộc có COA vi sinh mà COA = Không  → Cách ly
  · độ ẩm vượt ngưỡng                                  → Cách ly
Ép chứ không chặn: hàng đã về tới sân rồi, chặn lưu hoá đơn không làm hàng biến
mất — nó chỉ làm người ta bỏ trống ô QC cho xong việc.

Một luật CHẶN: kết luận "Đạt" trong khi cảm quan "Không đạt" là mâu thuẫn trên
một hồ sơ an toàn thực phẩm, không phải một đánh giá — gần như chắc chắn là gõ
nhầm dòng.
"""

import frappe
from frappe import _
from frappe.utils import flt

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


def mau_thuan(dong):
    """Kết luận Đạt trong khi cảm quan Không đạt."""
    return (dong.get("custom_ket_luan") == DAT
            and dong.get("custom_cam_quan_dat") == KHONG_DAT)


# ── móc vào Purchase Invoice ─────────────────────────────────────────────


def _tra_cha(item_group):
    return frappe.get_cached_value("Item Group", item_group, "parent_item_group")


def _item_group(item_code):
    return frappe.get_cached_value("Item", item_code, "item_group")


def validate(doc, method=None):
    ng = nguong()
    canh = []
    for r in doc.get("items") or []:
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
        # Thủ kho duyệt hoá đơn không có quyền tạo phiếu sự cố, nhưng hệ thống
        # PHẢI tạo được — nếu quyền chặn được việc này thì "bỏ qua lô không đạt"
        # chỉ còn là chuyện bấm bằng tài khoản nào.
        sc.insert(ignore_permissions=True)
