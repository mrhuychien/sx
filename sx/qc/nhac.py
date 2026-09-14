"""Nhắc lịch QC — tính ra danh sách việc đang treo, để HIỆN TRÊN DASHBOARD.

Không gửi email, không gửi Zalo. Lý do: thứ gửi đi thì người ta tắt thông báo
sau tuần thứ hai, còn thứ nằm sẵn trên màn hình người ta mở mỗi sáng thì không
tắt được. Cái giá phải trả là nó chỉ nhắc khi có người mở màn — nên mỗi mục
nhắc phải nói rõ ĐANG TREO BAO LÂU, không chỉ "có việc".

Hàm THUẦN: nhận dữ liệu đã lấy sẵn, không đọc DB. Test gọi thẳng nó.

Nguyên tắc viết một mục nhắc:
  · Nói CON SỐ và SỐ NGÀY, không nói "có vài việc cần xử lý".
  · Mỗi mục phải chỉ được sang đúng màn để làm việc đó (route).
  · Mức "cao" phải hiếm. Để cao hết thì không còn cao nữa — ở đây chỉ có bốn
    thứ: sự cố quá hạn, sự cố mở mà chưa ghi xử lý, lượt tuần bị bỏ, và bẫy
    chuột có dấu hiệu hai tuần liền.
"""

from datetime import date, timedelta

CAO = "cao"
THUONG = "thuong"

# Lượt bỏ dở / lượt thiếu chỉ soi trong cửa sổ này. Xa hơn nữa thì không còn là
# "nhắc" mà là lịch sử — chỗ của nó là màn Xem xét, không phải hộp nhắc việc.
SO_NGAY_SOI = 7
NGAY_CHUA_XEM_XET = 14


def _d(x):
    if isinstance(x, date):
        return x
    y, m, d = str(x)[:10].split("-")
    return date(int(y), int(m), int(d))


def _thu_hai(d):
    return d - timedelta(days=d.weekday())


def _m(muc_do, tieu_de, chi_tiet, route):
    return {"muc_do": muc_do, "tieu_de": tieu_de, "chi_tiet": chi_tiet,
            "route": route}


def tinh(hom_nay, luot, su_co, ng):
    """[{muc_do, tieu_de, chi_tiet, route}] — mức cao trước."""
    nay = _d(hom_nay)
    ra = []
    ra += _nhac_su_co(nay, su_co, ng)
    ra += _nhac_luot_tuan(nay, luot)
    ra += _nhac_luot_thieu(nay, luot)
    ra += _nhac_xem_xet(nay, luot)
    ra += _nhac_bay(luot)
    ra += _nhac_nguong(luot, ng)
    return sorted(ra, key=lambda x: 0 if x["muc_do"] == CAO else 1)


def _nhac_su_co(nay, su_co, ng):
    mo = [s for s in su_co if s.get("trang_thai") == "Mở"]
    if not mo:
        return []
    han = int(ng.get("su_co_qua_han_ngay") or 7)
    ra = []

    qua = [s for s in mo if (nay - _d(s["ngay"])).days > han]
    if qua:
        lau = max((nay - _d(s["ngay"])).days for s in qua)
        ra.append(_m(CAO, f"{len(qua)} phiếu sự cố quá hạn",
                     f"Mở quá {han} ngày, cái lâu nhất {lau} ngày. "
                     f"Phiếu quá hạn là phiếu không ai đóng được nữa "
                     f"— xem còn thiếu gì rồi đóng.", "#/qc/incidents"))

    # Sự cố mở mà CHƯA GHI XỬ LÝ NGAY là loại nguy hiểm nhất: không ai biết lô
    # hàng đó đã bị làm gì, và càng để lâu càng không ai nhớ ra.
    chua = [s for s in mo if not (s.get("xu_ly_ngay") or "").strip()]
    if chua:
        lau = max((nay - _d(s["ngay"])).days for s in chua)
        ra.append(_m(CAO, f"{len(chua)} phiếu chưa ghi xử lý ngay",
                     f"Cũ nhất {lau} ngày. Không có dòng này thì không ai biết "
                     f"lô hàng đó đã bị làm gì — và để càng lâu càng không ai "
                     f"nhớ ra.", "#/qc/incidents"))

    con = len(mo) - len({id(x) for x in qua} | {id(x) for x in chua})
    if con > 0:
        ra.append(_m(THUONG, f"{con} phiếu sự cố đang mở",
                     "Đã ghi xử lý, chờ Ban ISO đóng.", "#/qc/incidents"))
    return ra


def _nhac_luot_tuan(nay, luot):
    """Lượt tuần là lượt dễ bị bỏ nhất: nó chỉ có mỗi tuần một lần."""
    t2 = _thu_hai(nay)
    co = any(x.get("luot") == "Tuần" and t2 <= _d(x["ngay"]) <= nay
             for x in luot)
    if co:
        return []
    if nay == t2:
        return [_m(THUONG, "Hôm nay là thứ Hai — chưa làm lượt tuần",
                   "Lượt đầu ca hôm nay ghi là lượt Tuần, có thêm 11 mục phần C.",
                   "#/qc")]
    return [_m(CAO, f"Tuần này chưa có lượt tuần nào",
               f"Thứ Hai ({t2.strftime('%d/%m')}) đã qua {(nay - t2).days} ngày. "
               f"Lượt tuần chỉ có mỗi tuần một lần nên bỏ là mất hẳn.", "#/qc")]


def _nhac_luot_thieu(nay, luot):
    ra = []
    tu = nay - timedelta(days=SO_NGAY_SOI)

    # Ca đã bắt đầu nhưng không đi đủ 3 lượt.
    #
    # Ca KHÔNG có lượt nào thì không xuất hiện ở đây — và đó là chủ ý, không
    # phải tình cờ: ca đó có thể đơn giản là không sản xuất. Đoán bừa rồi nhắc
    # mỗi ngày là cách nhanh nhất để người ta bỏ qua cả hộp nhắc việc.
    # (Điều đó do chỗ GOM NHÓM dưới đây bảo đảm — ca rỗng không thành khoá.
    #  `0 < len(v)` chỉ là chốt thừa phòng khi sau này ai đó đổi cách gom.)
    theo_ca = {}
    for x in luot:
        d = _d(x["ngay"])
        if not (tu <= d < nay):
            continue
        theo_ca.setdefault((str(d), x.get("ca")), []).append(x)
    thieu = [(k, v) for k, v in theo_ca.items() if 0 < len(v) < 3]
    if thieu:
        ds = ", ".join(f"{k[0][8:]}/{k[0][5:7]} {k[1]} ({len(v)}/3)"
                       for k, v in sorted(thieu)[:4])
        ra.append(_m(THUONG, f"{len(thieu)} ca đi thiếu lượt trong {SO_NGAY_SOI} ngày",
                     f"{ds}{'…' if len(thieu) > 4 else ''}. "
                     f"Ca không sản xuất thì không tính ở đây.", "#/qc/history"))

    # Lượt mở ra rồi bỏ dở: dữ liệu nằm đó, không vào hồ sơ, không sinh sự cố.
    do_dang = [x for x in luot
               if int(x.get("docstatus") or 0) == 0 and _d(x["ngay"]) < nay]
    if do_dang:
        lau = max((nay - _d(x["ngay"])).days for x in do_dang)
        ra.append(_m(THUONG, f"{len(do_dang)} lượt bỏ dở từ ngày cũ",
                     f"Cũ nhất {lau} ngày. Chưa hoàn tất thì chưa vào hồ sơ và "
                     f"chưa sinh phiếu sự cố nào.", "#/qc/history"))
    return ra


def _nhac_xem_xet(nay, luot):
    cu = [x for x in luot
          if int(x.get("docstatus") or 0) == 1 and not x.get("reviewed_on")
          and (nay - _d(x["ngay"])).days > NGAY_CHUA_XEM_XET]
    if not cu:
        return []
    return [_m(THUONG, f"{len(cu)} lượt chờ Ban ISO xem xét",
               f"Đã hoàn tất quá {NGAY_CHUA_XEM_XET} ngày mà chưa ai ký.",
               "#/qc/review")]


def _nhac_bay(luot):
    """Bẫy chuột có dấu hiệu HAI TUẦN LIỀN nghĩa là xử lý tuần trước không ăn."""
    tuan = {}
    for x in luot:
        if x.get("luot") != "Tuần":
            continue
        d = _d(x["ngay"])
        tuan[_thu_hai(d)] = int(x.get("t2_so_bay_dau_hieu") or 0)
    if len(tuan) < 2:
        return []
    hai = sorted(tuan)[-2:]
    if all(tuan[t] > 0 for t in hai):
        return [_m(CAO, "Bẫy chuột có dấu hiệu hai tuần liền",
                   f"Tuần {hai[0].strftime('%d/%m')}: {tuan[hai[0]]} trạm · "
                   f"tuần {hai[1].strftime('%d/%m')}: {tuan[hai[1]]} trạm. "
                   f"Lặp lại nghĩa là xử lý tuần trước không ăn — gọi đơn vị "
                   f"diệt côn trùng.", "#/qc/history")]
    return []


def _nhac_nguong(luot, ng):
    """Đang ghi số mà không có ngưỡng nào kiểm nó — số đó chỉ để cho vui."""
    if ng.get("rang_lac_nhiet_min") or ng.get("rang_lac_phut_min"):
        return []
    if not any(float(x.get("b2_rang_lac_nhiet") or 0) for x in luot):
        return []
    return [_m(THUONG, "Ngưỡng rang lạc chưa thẩm định",
               "QC đang ghi nhiệt độ rang lạc nhưng chưa có ngưỡng nào trong "
               "SX QC Setting, nên không mục nào tự sinh sự cố. Số đó hiện chỉ "
               "để ghi nhận.", "#/qc/review")]
