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
# Bột nền để quá chừng này ngày là vượt giới hạn kho bột (mục 8 BM.08.01, oPRP-3).
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


def tinh(hom_nay, luot, su_co, ng, bot_nen=None, luu_mau=None, xuat_xuong=None, dong_vat=None,
         cat=None, thiet_bi=None, kiem_nghiem=None):
    """[{muc_do, tieu_de, chi_tiet, route}] — mức cao trước.

    `bot_nen` = [{batch, ten, ngay, ton, dvt}] lô bột nền còn tồn (W06).
    `luu_mau` = {"den_han": n, "lau_nhat": ngày, "dot_cho": [{name, thang, lap_luc}]} (W07).
    `xuat_xuong` = {"cho_duyet": n, "lau_nhat": ngày gửi} — phiếu BM.08.04 chờ duyệt (W08).
    `dong_vat` = {"co_du_lieu": bool, "khu_hai_tuan": [{khu, tram, tuan}]} — W15 (D140).
    `cat` = sx/qc/cat.nhac(): đổi nguồn còn thiếu, ngày có rang thiếu nhật ký — W20 (D141).
    `thiet_bi` = sx/qc/thiet_bi.nhac(): quá hạn, không đạt, sắp đến hạn, loại chưa khai — W17 (D143).
    `kiem_nghiem` = sx/qc/kiem_nghiem.nhac(): sản phẩm quá / đến hạn gửi mẫu, chờ kết quả lâu — W18 (D144)."""
    nay = _d(hom_nay)
    ra = []
    ra += _nhac_bot_nen(nay, bot_nen or [])
    ra += _nhac_luu_mau(nay, luu_mau or {})
    ra += _nhac_xuat_xuong(nay, xuat_xuong or {})
    ra += _nhac_su_co(nay, su_co, ng)
    ra += _nhac_luot_tuan(nay, luot)
    ra += _nhac_luot_thieu(nay, luot)
    ra += _nhac_xem_xet(nay, luot)
    ra += _nhac_dong_vat(dong_vat or {})
    ra += _nhac_cat(cat or {})
    ra += _nhac_thiet_bi(nay, thiet_bi or {})
    ra += _nhac_kiem_nghiem(kiem_nghiem or {})
    # Nhắc cũ theo số trạm có dấu hiệu ở lượt tuần (T2, không biết khu) — chỉ còn dùng khi
    # nhà máy CHƯA ghi dấu hiệu theo trạm (W15); có dữ liệu trạm thì nhắc theo khu thay.
    if not (dong_vat or {}).get("co_du_lieu"):
        ra += _nhac_bay(luot)
    ra += _nhac_nguong(luot, ng)
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
        if not (tu <= d < nay):
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
    """Nhật ký cát rang (W20): đổi nguồn chưa kiểm kim loại nặng / chưa lưu lọ mẫu, ngày có
    rang mà chưa ghi. Số ngày tối đa chỉ nhắc khi SX QC Setting đã điền (C19 chưa chốt)."""
    ra = []
    for x in c.get("cho_kln") or []:
        thieu = []
        if x.get("kln") != "Đạt":
            thieu.append("chờ kết quả kim loại nặng" if x.get("kln") else "chưa gửi mẫu kiểm kim loại nặng")
        if not x.get("lo_mau"):
            thieu.append("chưa lưu lọ mẫu")
        ra.append(_m(CAO if not x.get("kln") else THUONG, f"Đổi nguồn cát: {', '.join(thieu)}",
                     f"Nguồn {x.get('ncc') or ''}, thay ngày {_d(x['ngay']).strftime('%d/%m')}. Đổi nguồn cát "
                     f"phải kiểm kim loại nặng và lưu một lọ mẫu — có kết quả thì ghi vào nhật ký cát.",
                     "#/qc/cat"))
    toi_da, so = int(c.get("toi_da") or 0), int(c.get("so_ngay") or 0)
    if toi_da and so >= toi_da:
        ra.append(_m(THUONG, f"Cát đã dùng {so} ngày (tối đa {toi_da})",
                     f"Nguồn {c.get('ncc') or ''}. Thay cát rồi ghi \"Thay cát mới\" vào nhật ký cát.",
                     "#/qc/cat"))
    thieu = c.get("thieu") or []
    if thieu:
        ds = ", ".join(_d(x).strftime("%d/%m") for x in thieu[:5])
        ra.append(_m(THUONG, f"{len(thieu)} ngày có rang mà chưa ghi nhật ký cát",
                     f"{ds}{'…' if len(thieu) > 5 else ''} — ghi bù (chọn ngày cũ) trong nhật ký cát "
                     f"BM.08.03. App đếm số ngày cát đã dùng theo các dòng này.", "#/qc/cat"))
    if c.get("hom_nay_chua"):
        ra.append(_m(THUONG, "Hôm nay có rang — chưa ghi nhật ký cát",
                     "Ghi trong ngày: nguồn cát, có thay cát không, vệ sinh thùng / khay.", "#/qc/cat"))
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
