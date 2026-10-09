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

import re
from datetime import date, timedelta

CAO = "cao"
THUONG = "thuong"

# Lượt bỏ dở / lượt thiếu chỉ soi trong cửa sổ này. Xa hơn nữa thì không còn là
# "nhắc" mà là lịch sử — chỗ của nó là màn Xem xét, không phải hộp nhắc việc.
SO_NGAY_SOI = 7
NGAY_CHUA_XEM_XET = 14
# Bột nền để quá chừng này ngày là vượt giới hạn kho bột (mục 8 BM.08.01; lưu bột 2 ngày là PRP — W38).
BOT_NEN_TOI_DA_NGAY = 2


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


def _nhom(ma, ds):
    """Gắn mảng hồ sơ cho từng mục nhắc — Tổng quan ATTP (W22, sx/qc/attp.py) lấy đèn theo mảng
    từ chính danh sách này. Hộp nhắc không đọc `nhom`."""
    for x in ds:
        x["nhom"] = ma
    return ds


def tinh(hom_nay, luot, su_co, ng, bot_nen=None, luu_mau=None, xuat_xuong=None, dong_vat=None,
         cat=None, thiet_bi=None, kiem_nghiem=None, viec_dinh_ky=None, khac_phuc=None, vai_u=None,
         kiem_xe=None, tai_lieu=None, so=None, danh_gia_ncc=None):
    """[{muc_do, tieu_de, chi_tiet, route}] — mức cao trước.

    `bot_nen` = [{batch, ten, ngay, ton, dvt}] lô bột nền còn tồn (W06).
    `luu_mau` = {"den_han": n, "lau_nhat": ngày, "dot_cho": [{name, thang, lap_luc}]} (W07).
    `xuat_xuong` = {"cho_duyet": n, "lau_nhat": ngày gửi} — phiếu BM.08.04 chờ duyệt (W08).
    `dong_vat` = {"co_du_lieu": bool, "khu_hai_tuan": [{khu, tram, tuan}]} — W15 (D140).
    `cat` = sx/qc/cat.nhac(): đổi nguồn còn thiếu, tối đa, có rang mà không có cát đang dùng — W20, W32.
    `thiet_bi` = sx/qc/thiet_bi.nhac(): quá hạn, không đạt, sắp đến hạn, loại chưa khai — W17 (D143).
    `kiem_nghiem` = sx/qc/kiem_nghiem.nhac(): sản phẩm quá / đến hạn gửi mẫu, chờ kết quả lâu — W18 (D144).
    `viec_dinh_ky` = sx/qc/viec_dinh_ky.nhac(): việc năm / quý quá hạn, sắp đến hạn, chưa đặt hạn — W21 (D146);
                     phần `kiem_nghiem` (nước, nguyên liệu, khác theo KH.KN.01) vào mảng Kiểm nghiệm — W35 (D166).
    `khac_phuc` = sx/qc/khac_phuc.nhac(): phiếu BM.01.07 quá hạn, chờ kiểm tra hiệu lực lâu — W24 (D150).
    `vai_u` = sx/qc/vai_u.nhac(): quá chu kỳ chưa giặt vải ủ, dòng chờ QC ký, tháng chưa xem — W29 (D163).
    `kiem_xe` = sx/qc/kiem_xe.nhac(): tuần có chuyến mà chưa chuyến nào QC kiểm, tháng BM.09.01 chưa xem — W34.
    `tai_lieu` = sx/qc/tai_lieu.nhac(): đợt ban hành quá 7 ngày còn người chưa xác nhận đọc, đề nghị BM.01.01 chờ
                 lâu, tài liệu bên ngoài quá 12 tháng chưa soát xét, đợt nháp thiếu PDF — W42 (D171).
    `so` = sx/qc/so.nhac(): sổ ghi theo dòng — hạn, không ghi, chờ xác nhận, chưa xem tháng; BM.06.05 kiểm lại sau sửa
           chữa, máy quá hạn bảo dưỡng. Mỗi sổ vào mảng của nó (`mang`) — W43 (D172).
    `danh_gia_ncc` = sx/qc/danh_gia_ncc.nhac(): đánh giá lại NCC quá / sắp đến hạn, NCC duyệt trước C26 chưa có phiếu,
                     phiếu Chấp nhận chưa vào BM.07.02, Loại bỏ mà vẫn duyệt, phiếu chờ QC / Giám đốc — W44 (D173)."""
    nay = _d(hom_nay)
    ra = []
    # Bột nền quá hạn là giới hạn kho bột — mục 8 BM.08.01 (PRP từ W38), nên thuộc mảng vòng kiểm.
    ra += _nhom("vong_kiem", _nhac_bot_nen(nay, bot_nen or []))
    ra += _nhom("luu_mau", _nhac_luu_mau(nay, luu_mau or {}))
    ra += _nhom("xuat_xuong", _nhac_xuat_xuong(nay, xuat_xuong or {}))
    ra += _nhom("su_co", _nhac_su_co(nay, su_co, ng))
    ra += _nhom("khac_phuc", _nhac_khac_phuc(khac_phuc or {}))
    ra += _nhom("vong_kiem", _nhac_luot_tuan(nay, luot) + _nhac_luot_thieu(nay, luot)
                + _nhac_xem_xet(nay, luot))
    ra += _nhom("dong_vat", _nhac_dong_vat(dong_vat or {}))
    ra += _nhom("cat", _nhac_cat(cat or {}))
    ra += _nhom("vai_u", _nhac_vai_u(nay, vai_u or {}))
    ra += _nhom("kiem_xe", _nhac_kiem_xe(kiem_xe or {}))
    ra += _nhom("tai_lieu", _nhac_tai_lieu(tai_lieu or {}))
    ra += _nhac_so(so or {})
    ra += _nhom("ncc", _nhac_danh_gia_ncc(nay, danh_gia_ncc or {}))
    ra += _nhom("thiet_bi", _nhac_thiet_bi(nay, thiet_bi or {}))
    ra += _nhom("kiem_nghiem", _nhac_kiem_nghiem(kiem_nghiem or {}))
    ra += _nhom("viec_dinh_ky", _nhac_viec_dinh_ky(viec_dinh_ky or {}))
    ra += _nhom("kiem_nghiem", _nhac_viec_kn((viec_dinh_ky or {}).get("kiem_nghiem") or {}))
    # Nhắc cũ theo số trạm có dấu hiệu ở lượt tuần (T2, không biết khu) — chỉ còn dùng khi
    # nhà máy CHƯA ghi dấu hiệu theo trạm (W15); có dữ liệu trạm thì nhắc theo khu thay.
    if not (dong_vat or {}).get("co_du_lieu"):
        ra += _nhom("dong_vat", _nhac_bay(luot))
    ra += _nhom("vong_kiem", _nhac_nguong(luot, ng))
    return sorted(ra, key=lambda x: 0 if x["muc_do"] == CAO else 1)


def _nhac_bot_nen(nay, ds):
    """Lô bột nền còn tồn quá BOT_NEN_TOI_DA_NGAY ngày (W06) — mức CAO: đây là giới hạn
    của kho bột, không phải việc nhắc cho có. Tính theo SỔ KHO (ngày làm ra lô): báo mẻ
    chưa đồng bộ thì số tồn còn treo — nói rõ là "theo sổ kho"."""
    qua = sorted(((nay - _d(x["ngay"])).days, x) for x in ds
                 if x.get("ngay") and (nay - _d(x["ngay"])).days > BOT_NEN_TOI_DA_NGAY)
    if not qua:
        return []
    qua.reverse()
    ct = "; ".join(f'{x.get("ten") or x["batch"]} lô {x["batch"]}: {n} ngày, '
                   f'{float(x.get("ton") or 0):g} {x.get("dvt") or ""}'.strip()
                   for n, x in qua[:3])
    return [_m(CAO, f"{len(qua)} lô bột nền quá {BOT_NEN_TOI_DA_NGAY} ngày (theo sổ kho)",
               f"{ct}{'…' if len(qua) > 3 else ''}. Dùng trước hoặc xử lý theo mục 8 Kho bột; "
               f"báo mẻ chưa đồng bộ thì tồn trên sổ còn treo.", "#/qc")]


def _nhac_luu_mau(nay, lm):
    """Mẫu lưu đến hạn chưa vào đợt huỷ; đợt huỷ chờ Ban ISO (W07). Mức thường: để quá
    hạn vài ngày không hại gì — chỉ là tủ mẫu đầy và hồ sơ huỷ tháng bị trễ."""
    ra = []
    if int(lm.get("den_han") or 0):
        lau = (nay - _d(lm["lau_nhat"])).days if lm.get("lau_nhat") else 0
        ra.append(_m(THUONG, f"{lm['den_han']} mẫu lưu đến hạn huỷ",
                     f"Hết hạn lưu, cái lâu nhất quá {lau} ngày — bấm ĐỀ XUẤT HUỶ để gom vào "
                     f"đợt huỷ tháng, Ban ISO xác nhận.", "#/qc/luumau"))
    for d in lm.get("dot_cho") or []:
        cho = (nay - _d(d["lap_luc"])).days if d.get("lap_luc") else 0
        ra.append(_m(THUONG, f"Đợt huỷ mẫu {d['name']} chờ Ban ISO xác nhận",
                     f"Tháng {d.get('thang') or ''}, đề xuất {cho} ngày trước — mẫu nằm ở "
                     f"trạng thái Chờ huỷ cho tới khi xác nhận.", "#/qc/luumau"))
    return ra


def _nhac_xuat_xuong(nay, xx):
    """Phiếu kiểm tra xuất xưởng chờ duyệt (W08). Lô chưa duyệt là hàng đứng ngoài kho —
    chờ quá 1 ngày thì lên mức CAO."""
    n = int(xx.get("cho_duyet") or 0)
    if not n:
        return []
    cho = (nay - _d(xx["lau_nhat"])).days if xx.get("lau_nhat") else 0
    return [_m(CAO if cho >= 1 else THUONG, f"{n} phiếu xuất xưởng BM.08.04 chờ duyệt",
               f"Lô chưa duyệt thì chưa nhập kho, chưa bán được — phiếu lâu nhất chờ {cho} ngày. "
               f"Trưởng Ban ISO / người được giao duyệt.", "#/qc/xuatxuong")]


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


def _nhac_khac_phuc(kp):
    """Phiếu hành động khắc phục BM.01.07 (W24): quá hạn hoàn thành (cao — nguyên nhân còn đó thì sự cố
    lặp lại), đã làm xong mà Ban ISO để lâu chưa kiểm tra hiệu lực (thường)."""
    ra = []
    qua = kp.get("qua_han") or []
    if qua:
        ra.append(_m(CAO, f"{len(qua)} phiếu khắc phục BM.01.07 quá hạn",
                     ", ".join(f"{x['name']} (hạn {_d(x['han']).strftime('%d/%m')})" for x in qua[:4])
                     + ("…" if len(qua) > 4 else "") + ". Nguyên nhân chưa xử lý thì sự cố còn lặp lại.",
                     "#/qc/khacphuc"))
    cho = kp.get("cho_kiem") or []
    if cho:
        ra.append(_m(THUONG, f"{len(cho)} phiếu khắc phục chờ kiểm tra hiệu lực",
                     f"{', '.join(x['name'] for x in cho[:4])}{'…' if len(cho) > 4 else ''} — đã làm xong hơn "
                     "một tuần, Trưởng Ban ISO kiểm tra rồi đóng.", "#/qc/khacphuc"))
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
                   "Lượt đầu sáng hôm nay ghi là lượt Tuần, có thêm các mục tuần (phần C).",
                   "#/qc")]
    return [_m(CAO, f"Tuần này chưa có lượt tuần nào",
               f"Thứ Hai ({t2.strftime('%d/%m')}) đã qua {(nay - t2).days} ngày. "
               f"Lượt tuần chỉ có mỗi tuần một lần nên bỏ là mất hẳn.", "#/qc")]


def _nhac_luot_thieu(nay, luot):
    ra = []
    tu = nay - timedelta(days=SO_NGAY_SOI)

    # Ngày đã bắt đầu kiểm nhưng không đi đủ 3 lượt.
    #
    # Ngày KHÔNG có lượt nào thì không xuất hiện ở đây — và đó là chủ ý, không
    # phải tình cờ: ngày đó có thể đơn giản là không sản xuất. Đoán bừa rồi nhắc
    # mỗi ngày là cách nhanh nhất để người ta bỏ qua cả hộp nhắc việc.
    # (Điều đó do chỗ GOM NHÓM dưới đây bảo đảm — ngày rỗng không thành khoá.
    #  `0 < so` chỉ là chốt thừa phòng khi sau này ai đó đổi cách gom.)
    #
    # Đếm TÊN LƯỢT KHÁC NHAU, không đếm số phiếu: ngày cũ trước D95 có thể có hai
    # phiếu "Đầu sáng" (ca Sáng + ca Chiều cũ) — đếm phiếu thì ra 2/3 mà thực ra
    # vẫn thiếu Trưa và Cuối chiều như nhau. Tuần tính là Đầu sáng.
    theo_ngay = {}
    for x in luot:
        d = _d(x["ngay"])
        if not (tu <= d < nay) or x.get("luot") == "Bổ sung":   # W23: lượt bổ sung không thay lượt nào
            continue
        ten = "Đầu sáng" if x.get("luot") == "Tuần" else x.get("luot")
        theo_ngay.setdefault(str(d), set()).add(ten)
    thieu = [(k, v) for k, v in theo_ngay.items() if 0 < len(v) < 3]
    if thieu:
        ds = ", ".join(f"{k[8:]}/{k[5:7]} ({len(v)}/3)" for k, v in sorted(thieu)[:4])
        ra.append(_m(THUONG, f"{len(thieu)} ngày đi thiếu lượt trong {SO_NGAY_SOI} ngày",
                     f"{ds}{'…' if len(thieu) > 4 else ''}. "
                     f"Ngày không sản xuất thì không tính ở đây.", "#/qc/history"))

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


def _nhac_dong_vat(dv):
    """Cùng KHU có dấu hiệu động vật gây hại hai tuần liền → gọi đơn vị dịch vụ (W15)."""
    return [_m(CAO, f"{k['khu']}: động vật gây hại hai tuần liền",
               f"Trạm {', '.join(k['tram'])} — tuần {_d(k['tuan'][0]).strftime('%d/%m')} và tuần "
               f"{_d(k['tuan'][1]).strftime('%d/%m')}. Xử lý tại chỗ không ăn — gọi đơn vị dịch vụ.",
               "#/qc/dvgh") for k in dv.get("khu_hai_tuan") or []]


def _nhac_cat(c):
    """Nhật ký cát rang (W20; W32 — mỗi việc một dòng): đổi nguồn chưa kiểm kim loại nặng / chưa lưu lọ mẫu;
    số ngày tối đa chỉ nhắc khi SX QC Setting đã điền (C19 chưa chốt); có rang mà sổ không có cát đang dùng
    (chưa ghi lần đưa cát vào máy, hoặc đã loại mà chưa ghi cát mới) — số ngày cát đã dùng đếm sai từ đó."""
    ra = []
    for x in c.get("cho_kln") or []:
        thieu = []
        if x.get("kln") != "Đạt":
            thieu.append("chờ kết quả kim loại nặng" if x.get("kln") else "chưa gửi mẫu kiểm kim loại nặng")
        if not x.get("lo_mau"):
            thieu.append("chưa lưu lọ mẫu")
        ra.append(_m(CAO if not x.get("kln") else THUONG, f"Đổi nguồn cát: {', '.join(thieu)}",
                     f"Nguồn {x.get('ncc') or ''}, nhập ngày {_d(x['ngay']).strftime('%d/%m')}. Đổi nguồn cát "
                     f"phải kiểm kim loại nặng (trước khi dùng) và lưu một lọ mẫu — có kết quả thì ghi vào nhật ký "
                     f"cát.", "#/qc/cat"))
    toi_da, so = int(c.get("toi_da") or 0), int(c.get("so_ngay") or 0)
    if c.get("dang_dung") and toi_da and so >= toi_da:
        ra.append(_m(THUONG, f"Cát đã dùng {so} ngày (tối đa {toi_da})",
                     f"Nguồn {c.get('ncc') or ''}. Loại cát cũ, đưa cát mới vào rồi ghi \"Loại cát\" + \"Rang khô "
                     f"đưa dùng\" vào nhật ký cát.", "#/qc/cat"))
    if c.get("rang_khong_cat"):
        ra.append(_m(THUONG, "Có rang mà nhật ký cát không có cát đang dùng",
                     f"Từ {_d(c['rang_khong_cat']).strftime('%d/%m')} có lượt ghi nhiệt độ rang. Ghi dòng \"Rang khô "
                     f"đưa dùng\" (cát đưa vào máy) — app đếm số ngày cát đã dùng từ đó.", "#/qc/cat"))
    return ra


def _nhac_vai_u(nay, v):
    """Sổ giặt vải ủ BM.08.05 (W29). Nhắc giặt CHỈ khi đã khai ít nhất một vải Đang dùng (C31: số thùng,
    số vải HD.08.02 còn để trống — chưa khai thì app không biết có vải để giặt):
      · quá chu kỳ (7 ngày; giặt sau mỗi lần dùng: 2 ngày) chưa giặt — gấp đôi chu kỳ là mức cao;
      · hôm nay là ngày giặt cố định mà chưa ghi (khi QLSX đã chọn ngày, chưa quá hạn).
    Dòng chờ QC ký quá 1 ngày, tháng đã qua hạn xem mà Trưởng Ban ISO chưa xem: nhắc dù chưa khai vải."""
    ra = []
    dang = int(v.get("dang_dung") or 0)
    ck = int(v.get("chu_ky") or 7)
    ten = "giặt (giặt sau mỗi lần dùng)" if v.get("giat_moi_lan") else "giặt định kỳ"
    cuoi = v.get("lan_cuoi")
    qua = cuoi is not None and (nay - _d(cuoi)).days > ck
    if dang and not cuoi:
        ra.append(_m(THUONG, "Sổ giặt vải ủ chưa có lần giặt định kỳ nào",
                     f"Đã khai {dang} vải đang dùng. Giặt, đun sôi ≥ 10 phút 1 lần/tuần (HD.08.02) — ghi lần giặt "
                     f"gần nhất vào sổ BM.08.05 (ghi bù từ sổ giấy được).", "#/qc/vaiu"))
    elif dang and qua:
        n = (nay - _d(cuoi)).days
        ra.append(_m(CAO if n > 2 * ck else THUONG, f"Vải ủ {n} ngày chưa {ten}",
                     f"Lần gần nhất {_d(cuoi).strftime('%d/%m')}. Giặt, đun sôi toàn bộ vải đang dùng ≥ 10 phút tính "
                     f"từ lúc nước sôi lại rồi ghi sổ BM.08.05.", "#/qc/vaiu"))
    elif dang and v.get("hom_nay_la_ngay_giat") and not v.get("hom_nay_da_giat") and not v.get("giat_moi_lan"):
        ra.append(_m(THUONG, f"Hôm nay ({str(v.get('thu_giat') or '').lower()}) là ngày giặt vải ủ",
                     "Giặt, đun sôi toàn bộ vải đang dùng; ngày giặt thay vải còn lại của từng thùng. Ghi sổ "
                     "BM.08.05 — QC ký.", "#/qc/vaiu"))
    cho = v.get("cho_ky") or []
    if cho:
        ra.append(_m(THUONG, f"{len(cho)} dòng sổ giặt vải ủ chờ QC ký",
                     f"Sớm nhất ngày {_d(cho[0]['ngay']).strftime('%d/%m')} ({str(cho[0].get('viec') or '').lower()}). "
                     f"Xem giờ đun sôi (≥ 10 phút), chỗ phơi, giờ cất rồi ký.", "#/qc/vaiu"))
    for t in v.get("chua_xem") or []:
        ra.append(_m(THUONG, f"Sổ giặt vải ủ tháng {t[5:7]}/{t[:4]} chưa được Trưởng Ban ISO xem",
                     "Trưởng Ban ISO xem BM.08.05 cuối tháng (HD.08.02 mục 9) — bấm \"Đã xem tháng\" trên màn Sổ "
                     "giặt vải ủ.", "#/qc/vaiu"))
    return ra


def _nhac_kiem_xe(kx):
    """Kiểm xe BM.09.01 (W34). QT.09 mục 4: QC kiểm ngẫu nhiên ít nhất 1 chuyến/tuần — tuần thứ Hai – Chủ
    nhật có chuyến (đã ghi kiểm xe) mà chưa chuyến nào QC kiểm: nhắc tuần này, và tuần trước nếu đã lỡ (QC
    chỉ đóng dấu được chuyến mới — SO_NGAY_QC ở sx/qc/kiem_xe.py — nên tuần trước thường không gỡ được nữa:
    nhắc để rút kinh nghiệm, hết tuần này thì thôi). Tháng đã qua hạn xem mà Trưởng Ban ISO chưa xem."""
    ra = []
    for k, ten in (("tuan_nay", "Tuần này"), ("tuan_truoc", "Tuần trước")):
        t = kx.get(k) or {}
        if not t.get("so_chuyen") or t.get("so_qc"):
            continue
        tu, den = _d(t["tu"]), _d(t["den"])
        ra.append(_m(THUONG, f"{ten} {t['so_chuyen']} chuyến hàng, chưa chuyến nào QC kiểm xe",
                     f"Thứ Hai {tu.strftime('%d/%m')} – Chủ nhật {den.strftime('%d/%m')}. QT.09: QC kiểm ngẫu nhiên "
                     f"ít nhất 1 chuyến/tuần (xe nguyên liệu: kiểm cùng lúc trên màn Tiếp nhận NL) — bấm QC KIỂM "
                     f"trên màn Kiểm xe.", "#/qc/kiemxe"))
    for t in kx.get("chua_xem") or []:
        ra.append(_m(THUONG, f"Kiểm xe BM.09.01 tháng {t[5:7]}/{t[:4]} chưa được Trưởng Ban ISO xem",
                     "QT.09 mục 4: Trưởng Ban ISO xem BM.09.01 hằng tháng — bấm \"Đã xem tháng\" trên màn Kiểm xe.",
                     "#/qc/kiemxe"))
    return ra


def _nhac_tai_lieu(tl):
    """Thư viện tài liệu (W42). "Cần đọc" của từng người hiện ở đầu màn Tài liệu, không ở đây — hộp này nhắc
    việc của Ban ISO / Giám đốc: đợt ban hành quá 7 ngày mà còn người chưa xác nhận đọc (theo đợt), đề nghị
    BM.01.01 chờ xem xét / duyệt quá 7 ngày, tài liệu bên ngoài quá 12 tháng chưa soát xét (QT.01), đợt nháp còn
    dòng thiếu PDF đã ký."""
    ra = []
    for x in tl.get("chua_doc") or []:
        ra.append(_m(THUONG, f"Đợt ban hành {x['dot']}: {x['chua']}/{x['tong']} người chưa xác nhận đã đọc",
                     f"QĐ {x.get('so') or '…'} ban hành {_d(x['ngay']).strftime('%d/%m/%Y') if x.get('ngay') else ''}"
                     " — quá 7 ngày. Nhắc người chưa đọc, hoặc in BM.01.13 cho người không có tài khoản ký tay.",
                     f"#/tailieu/dot/{x['dot']}"))
    dn = tl.get("de_nghi") or []
    if dn:
        ra.append(_m(THUONG, f"{len(dn)} đề nghị tài liệu (BM.01.01) chờ xem xét / duyệt quá 7 ngày",
                     "; ".join(f"{x['name']} {x.get('ten') or ''} — {x['trang_thai'].lower()}".strip()
                               for x in dn[:3]) + ("…" if len(dn) > 3 else ""), "#/tailieu/denghi"))
    sx_ = tl.get("soat_xet") or []
    if sx_:
        ra.append(_m(THUONG, f"{len(sx_)} tài liệu bên ngoài quá 12 tháng chưa soát xét (BM.01.03)",
                     "QT.01: Ban ISO soát xét danh mục tài liệu bên ngoài ít nhất 1 lần / năm — "
                     + ", ".join(sx_[:4]) + ("…" if len(sx_) > 4 else ""), "#/tailieu/tatca"))
    for x in tl.get("dot_thieu") or []:
        ra.append(_m(THUONG, f"Đợt ban hành {x['dot']} (nháp) còn {x['thieu']} tài liệu chưa có PDF đã ký",
                     "Tải PDF bản đã ký cho từng dòng rồi bấm Ban hành.", f"#/tailieu/dot/{x['dot']}"))
    return ra


def _nhac_so(so):
    """Sổ ghi theo dòng (W43). Mỗi mục vào mảng của sổ (`mang` — thẻ Tổng quan ATTP; sổ chung là "Sổ khác"):
      · cột hạn đã quá / còn ≤ số ngày báo trước (BM.03.01 kiểm, nạp bình PCCC; BM.03.03 kiểm định);
      · quá N ngày không ghi dòng nào (sổ có đặt N);
      · dòng chờ xác nhận quá 2 ngày (BM.06.05: QC chưa kiểm máy sau sửa chữa);
      · tháng đã qua ngày 5 mà chưa xem xét cuối tháng;
      · BM.06.05: thiết bị đo đã sửa / được chọn kiểm lại mà chưa có phiếu kiểm từ ngày đó — mức CAO (QT.06: chưa kiểm
        lại thì chưa được dùng, như thiết bị quá hạn); máy sản xuất quá hạn bảo dưỡng định kỳ."""
    ra = []
    for s in so.get("ds") or []:
        r = f"#/so/{s['ma']}"
        ten = f"{s['ma']} {s.get('ten') or ''}".strip()
        m = []
        han = s.get("han") or []
        qua = [h for h in han if h["con"] < 0]
        sap = [h for h in han if h["con"] >= 0]
        # Sổ dữ liệu cá nhân (BM.PRP.07): hộp nhắc ai có màn QC cũng thấy → không ghi họ tên, chỉ hạn.
        ai = (lambda h: "") if s.get("rieng_tu") else (lambda h: f"{h.get('tom_tat') or h.get('dong')} — ")
        if qua:
            h = qua[0]
            m.append(_m(THUONG, f"{ten}: {len(qua)} mục quá hạn",
                        f"Quá hạn lâu nhất: {ai(h)}{h['nhan'].lower()} "
                        f"{_d(h['han']).strftime('%d/%m/%Y')}. Kiểm / nạp / kiểm định xong thì cập nhật sổ.", r))
        if sap:
            h = sap[0]
            m.append(_m(THUONG, f"{ten}: {len(sap)} mục sắp đến hạn",
                        f"Sớm nhất: {ai(h)}{h['nhan'].lower()} "
                        f"{_d(h['han']).strftime('%d/%m/%Y')} (còn {h['con']} ngày).", r))
        k = s.get("khong_ghi")
        if k:
            m.append(_m(THUONG, f"{ten}: {k['so_ngay']} ngày chưa ghi dòng nào",
                        (f"Dòng gần nhất {_d(k['ngay_cuoi']).strftime('%d/%m/%Y')}." if k.get("ngay_cuoi")
                         else "Sổ chưa có dòng nào.") + f" Sổ này phải ghi ít nhất {k['nguong']} ngày một lần.", r))
        cho = s.get("cho") or []
        if cho:
            viec = re.sub(r"\s*\(ký\)\s*$", "", s.get("nhan_xac_nhan") or "") or "xác nhận"
            m.append(_m(THUONG, f"{ten}: {len(cho)} dòng chờ {viec} quá {s.get('cho_nguong') or 2} ngày",
                        f"Sớm nhất ngày {_d(cho[0]['ngay']).strftime('%d/%m')}: {cho[0].get('tom_tat') or ''}.", r))
        for x in s.get("kiem_lai") or []:
            m.append(_m(CAO, f"{x['ma']} chưa kiểm lại sau sửa chữa ngày {_d(x['ngay']).strftime('%d/%m')}",
                        f"{x.get('ten') or ''} — QT.06: hiệu chuẩn / kiểm lại theo {x.get('bieu_mau') or 'BM.06.0x'} "
                        f"trước khi dùng. Ghi phiếu kiểm ở màn Thiết bị đo.".strip(" —"), "#/qc/thietbi"))
        bd = s.get("bao_duong") or []
        if bd:
            m.append(_m(THUONG, f"{len(bd)} máy sản xuất quá hạn bảo dưỡng định kỳ",
                        "; ".join(f"{x['ma']} {x.get('ten') or ''} (hạn {_d(x['han']).strftime('%d/%m/%Y')})".strip()
                                  for x in bd[:3]) + ("…" if len(bd) > 3 else "")
                        + ". Bảo dưỡng rồi ghi sổ BM.06.05 (QT.06: 6 tháng/lần).", r))
        cx = s.get("chua_xem") or []
        if cx:
            m.append(_m(THUONG, f"{ten}: tháng {', '.join(f'{t[5:7]}/{t[:4]}' for t in cx[:3])}"
                                f"{'…' if len(cx) > 3 else ''} chưa xem xét cuối tháng",
                        f"{s.get('nhan_xem_thang') or 'Xem xét cuối tháng'}: mở sổ, chọn tháng, bấm \"Đã xem tháng\".", r))
        ra += _nhom(s.get("mang") or "so_khac", m)
    return ra


def _nhac_danh_gia_ncc(nay, dg):
    """Đánh giá nhà cung cấp BM.07.01 (W44, D173) — mảng Nhà cung cấp. Mua vẫn chỉ cảnh báo (W09) nên mức thường."""
    r = "#/so/BM.07.01"
    ds = lambda xs: ", ".join(x.get("ten") or x.get("ncc") or "" for x in xs[:3]) + ("…" if len(xs) > 3 else "")  # noqa: E731
    ra = []
    x = dg.get("loai_bo_dang_duyet") or []
    if x:
        ra.append(_m(THUONG, f"{len(x)} nhà cung cấp bị Loại bỏ (BM.07.01) mà vẫn đang duyệt",
                     f"{ds(x)} — bỏ tích Đã duyệt, dừng đặt hàng, ghi ngày dừng và lý do trên BM.07.02 (QT.07).", r))
    x = dg.get("qua_han") or []
    if x:
        ra.append(_m(THUONG, f"{len(x)} nhà cung cấp quá hạn đánh giá lại (BM.07.01)",
                     f"{ds(x)} — hạn sớm nhất {_d(x[0]['han']).strftime('%d/%m/%Y')}. Đánh giá lại hằng năm "
                     "(QT.07): Mua hàng chấm, Giám đốc duyệt.", r))
    x = dg.get("sap_han") or []
    if x:
        ra.append(_m(THUONG, f"{len(x)} nhà cung cấp sắp đến hạn đánh giá lại (BM.07.01)",
                     f"{ds(x)} — hạn sớm nhất {_d(x[0]['han']).strftime('%d/%m/%Y')} (còn {x[0]['con']} ngày).", r))
    x = dg.get("chua_co") or []
    if x:
        han = _d(dg["han_dau"])
        con = (han - nay).days
        ra.append(_m(THUONG, f"{len(x)} nhà cung cấp đã duyệt chưa có phiếu đánh giá BM.07.01",
                     f"Hạn đánh giá lại lần đầu {han.strftime('%d/%m/%Y')} "
                     f"({f'còn {con} ngày' if con >= 0 else f'quá {-con} ngày'}): {ds(x)}.", r))
    x = dg.get("chap_nhan_chua_duyet") or []
    if x:
        ra.append(_m(THUONG, f"{len(x)} nhà cung cấp đã Chấp nhận (BM.07.01) chưa vào BM.07.02",
                     f"{ds(x)} — Trưởng Ban ISO / người được giao tích Đã duyệt trên nhà cung cấp.", r))
    for k, ten in (("cho_qc", "chờ QC ký"), ("cho_duyet", "chờ Giám đốc duyệt")):
        x = dg.get(k) or []
        if x:
            ra.append(_m(THUONG, f"{len(x)} phiếu đánh giá nhà cung cấp {ten}",
                         f"{', '.join((p.get('ten_ncc') or p.get('supplier') or '') for p in x[:3])}"
                         f"{'…' if len(x) > 3 else ''}.", r))
    return ra


def _nhac_thiet_bi(nay, tb):
    """Thiết bị đo (W17): quá hạn / không đạt = đang NGỪNG DÙNG (mức cao); sắp đến hạn 30 ngày;
    loại thiết bị chưa khai trong danh mục (đồng hồ nhiệt, nam châm, lưới sàng, cân)."""
    ra = []
    ds = lambda xs: ", ".join(x["ma"] for x in xs[:5]) + ("…" if len(xs) > 5 else "")  # noqa: E731
    if tb.get("qua_han"):
        x = tb["qua_han"]
        ra.append(_m(CAO, f"{len(x)} thiết bị đo quá hạn kiểm — ngừng dùng",
                     f"{ds(x)}. Kiểm / hiệu chuẩn rồi ghi phiếu trên màn Thiết bị đo; phiếu sự cố đã "
                     f"được lập tự động.", "#/qc/thietbi"))
    if tb.get("khong_dat"):
        x = tb["khong_dat"]
        ra.append(_m(CAO, f"{len(x)} thiết bị đo Không đạt — đang ngừng dùng",
                     f"{ds(x)}. Sửa / thay, kiểm lại Đạt thì mới dùng lại.", "#/qc/thietbi"))
    if tb.get("sap_den"):
        x = tb["sap_den"]
        ra.append(_m(THUONG, f"{len(x)} thiết bị đo đến hạn kiểm trong 30 ngày",
                     f"Sớm nhất {x[0]['ma']} — hạn {_d(x[0]['han']).strftime('%d/%m/%Y')}.", "#/qc/thietbi"))
    if tb.get("thieu_loai"):
        ra.append(_m(THUONG, f"Danh mục thiết bị đo chưa có: {', '.join(tb['thieu_loai']).lower()}",
                     f"Ban ISO khai trên màn Thiết bị đo — hạn kiểm lần đầu "
                     f"{_d(tb.get('han_dau') or nay).strftime('%d/%m/%Y')}.", "#/qc/thietbi"))
    return ra


def _nhac_kiem_nghiem(kn):
    """Kế hoạch kiểm nghiệm (W18): sản phẩm quá hạn gửi mẫu năm (cao), không đạt chờ kiểm lại
    (cao), đến hạn trong 30 ngày, gửi mẫu lâu chưa có kết quả. Cát: nhắc ở nhật ký cát (W20)."""
    ra = []
    ds = lambda xs: ", ".join(x.get("so_cong_bo") or x["ten"] for x in xs[:5]) + ("…" if len(xs) > 5 else "")  # noqa: E731
    if kn.get("qua_han"):
        x = kn["qua_han"]
        ra.append(_m(CAO, f"{len(x)} sản phẩm quá hạn gửi mẫu kiểm nghiệm",
                     f"{ds(x)}. Mỗi sản phẩm ít nhất 1 lần / năm (KH.KN.01) — gửi mẫu rồi ghi trên màn "
                     f"Kiểm nghiệm.", "#/qc/kiemnghiem"))
    if kn.get("khong_dat"):
        x = kn["khong_dat"]
        ra.append(_m(CAO, f"{len(x)} sản phẩm kiểm nghiệm Không đạt — chưa kiểm lại",
                     f"{ds(x)}. Xử lý theo phiếu sự cố rồi gửi mẫu kiểm lại.", "#/qc/kiemnghiem"))
    if kn.get("den_han"):
        x = kn["den_han"]
        ra.append(_m(THUONG, f"{len(x)} sản phẩm đến hạn gửi mẫu kiểm nghiệm trong 30 ngày",
                     f"{ds(x)} — hạn sớm nhất {_d(x[0]['han']).strftime('%d/%m/%Y')}.", "#/qc/kiemnghiem"))
    if kn.get("cho_lau"):
        x = kn["cho_lau"]
        ra.append(_m(THUONG, f"{len(x)} mẫu kiểm nghiệm gửi lâu chưa có kết quả",
                     f"{ds(x)} — hỏi đơn vị kiểm nghiệm, có kết quả thì ghi ngay.", "#/qc/kiemnghiem"))
    return ra


def _nhac_viec_dinh_ky(vd):
    """Việc định kỳ cho hồ sơ giấy (W21): quá hạn — mức cao (việc bắt buộc đã lỡ); sắp đến hạn
    trong số ngày "nhắc trước" của từng việc — mức thường. Mỗi việc một dòng: tên việc chính là
    điều phải làm, gộp lại thì người ta phải mở màn khác mới biết việc gì."""
    ra = []
    for x in vd.get("qua_han") or []:
        ra.append(_m(CAO, f"Việc định kỳ quá hạn: {x['ten']}",
                     f"Hạn {_d(x['han']).strftime('%d/%m/%Y')} — đã quá {-x['con']} ngày. Làm xong bấm "
                     f"\"Đã làm\" để dời sang kỳ sau.", "#/qc/lichviec"))
    for x in vd.get("sap_den") or []:
        ra.append(_m(THUONG, f"Sắp đến hạn: {x['ten']}",
                     f"Hạn {_d(x['han']).strftime('%d/%m/%Y')} — còn {x['con']} ngày.", "#/qc/lichviec"))
    if vd.get("chua_han"):
        x = vd["chua_han"]
        ra.append(_m(THUONG, f"{len(x)} việc định kỳ chưa đặt hạn",
                     f"{_ten_viec(x)}. Đặt hạn lần tới trên màn Việc định kỳ — chưa có hạn thì không nhắc được.",
                     "#/qc/lichviec"))
    return ra


def _ten_viec(xs, n=4):
    return "; ".join(x["ten"] for x in xs[:n]) + ("…" if len(xs) > n else "")


def _nhac_viec_kn(kn):
    """Kiểm nghiệm KH.KN.01 ngoài thành phẩm (W35): nước, nguyên liệu, bao bì, thẩm tra vải ủ — việc định kỳ
    có ô "mẫu của". Quá hạn gửi mẫu — mức cao như sản phẩm; đến hạn trong số ngày nhắc trước; chưa đặt hạn
    (KH.KN.01 ghi "khi đổi NCC hoặc 2 năm/lần" mà chưa biết lần gần nhất) — nói ra, không im lặng."""
    ra = []
    if kn.get("qua_han"):
        x = kn["qua_han"]
        ra.append(_m(CAO, f"{len(x)} mẫu nước / nguyên liệu / khác quá hạn gửi kiểm nghiệm",
                     f"{_ten_viec(x)} — hạn {_d(x[0]['han']).strftime('%d/%m/%Y')}. Gửi mẫu rồi ghi trên màn Kiểm "
                     f"nghiệm (KH.KN.01).", "#/qc/kiemnghiem"))
    if kn.get("sap_den"):
        x = kn["sap_den"]
        ra.append(_m(THUONG, f"{len(x)} mẫu nước / nguyên liệu / khác đến hạn gửi kiểm nghiệm",
                     f"{_ten_viec(x)} — hạn sớm nhất {_d(x[0]['han']).strftime('%d/%m/%Y')}.", "#/qc/kiemnghiem"))
    if kn.get("chua_han"):
        x = kn["chua_han"]
        ra.append(_m(THUONG, f"{len(x)} việc kiểm nghiệm chưa đặt hạn",
                     f"{_ten_viec(x)}. Ban ISO đặt hạn lần tới (màn Việc định kỳ) — chưa có hạn thì không nhắc được.",
                     "#/qc/kiemnghiem"))
    return ra


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
