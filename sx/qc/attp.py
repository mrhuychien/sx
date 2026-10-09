"""Tổng quan ATTP (W22, D148) — một màn cho Trưởng Ban ISO, Giám đốc.

Mỗi mảng hồ sơ một thẻ: đèn Đỏ / Vàng / Xanh, con số chính, vài dòng số liệu, các mục nhắc
của mảng đó và đường sang đúng màn để làm.

Đèn suy từ CHÍNH hộp nhắc (sx/qc/nhac.py — mỗi mục nhắc mang `nhom`): có mục mức cao → Đỏ,
có mục thường → Vàng, không có → Xanh. Không viết bộ luật đèn thứ hai: hai bộ luật thì sớm
muộn hộp nhắc nói một đằng, tổng quan nói một nẻo, và người đọc tin nhầm cái sai.
Ba mảng hộp nhắc chưa theo dõi (khiếu nại, truy xuất / thu hồi, NCC) có thêm mục cảnh báo
riêng ở `_them_*` — cùng dạng mục nhắc, nên đèn vẫn tính một cách.

Hàm THUẦN: nhận số liệu đã lấy (sx/api/qc_attp.py), không đọc DB. Test gọi thẳng.
"""

DO, VANG, XANH = "do", "vang", "xanh"
CAO, THUONG = "cao", "thuong"      # = sx.qc.nhac.CAO / THUONG (không import: giữ file này thuần)

# Diễn tập truy xuất: quá ngần này ngày chưa diễn tập lại thì cảnh báo — 12 tháng (chốt 09/10/2026;
# ISO 22000 chỉ đòi "kiểm tra định kỳ" hệ thống truy xuất).
DIEN_TAP_TOI_DA_NGAY = 365
CAN_BANG_DAT = 98       # W06: cân bằng lô đạt ≥ 98%

# (mã, tên, biểu mẫu, màn) — thứ tự đọc: xưởng hôm nay có an toàn không (vòng kiểm, sự cố),
# có gì ra tới khách (khiếu nại, xuất xưởng, truy xuất), rồi các hồ sơ nền.
LINH_VUC = (
    ("vong_kiem", "Vòng kiểm hằng ngày", "BM.08.01", "#/qc/review"),
    ("su_co", "Sự cố", "BM.08.02", "#/qc/incidents"),
    ("khac_phuc", "Hành động khắc phục", "BM.01.07", "#/qc/khacphuc"),
    ("khieu_nai", "Khiếu nại khách hàng", "BM.11.01", "#/qc/khieunai"),
    ("xuat_xuong", "Kiểm tra xuất xưởng", "BM.08.04", "#/qc/xuatxuong"),
    ("truy_xuat", "Truy xuất, thu hồi", "BM.02.04", "#/qc/truyxuat"),
    ("thiet_bi", "Thiết bị đo", "BM.06.01–06.04", "#/qc/thietbi"),
    ("kiem_nghiem", "Kiểm nghiệm sản phẩm", "KH.KN.01", "#/qc/kiemnghiem"),
    ("cat", "Cát rang", "BM.08.03", "#/qc/cat"),
    ("vai_u", "Vải ủ", "BM.08.05", "#/qc/vaiu"),
    ("dong_vat", "Động vật gây hại", "BM.PRP.01 / 03", "#/qc/dvgh"),
    ("ncc", "Nhà cung cấp", "BM.07.02", "#/qc/review"),
    ("kiem_xe", "Kiểm tra xe", "BM.09.01", "#/qc/kiemxe"),
    ("luu_mau", "Lưu mẫu", "", "#/qc/luumau"),
    ("rework", "Rework", "BM.15.01", "#/qc/rework"),
    ("viec_dinh_ky", "Việc định kỳ", "", "#/qc/lichviec"),
    ("tai_lieu", "Tài liệu", "BM.01.02", "#/tailieu"),
    ("bien_ban", "Biên bản, đánh giá nội bộ", "BM.01.05–01.11, BM.04.x", "#/qc/bienban"),
    ("so_khac", "Sổ khác", "BM.PRP.06, BM.03.01–03.03", "#/so"),
)
THU_TU_DEN = {DO: 0, VANG: 1, XANH: 2}


def _ngay(s):
    s = str(s or "")[:10]
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}" if len(s) == 10 else ""


def _so(x):
    """15.0 → "15", 99.25 → "99,25" (cách viết số của tờ giấy)."""
    x = float(x or 0)
    return (f"{x:.2f}".rstrip("0").rstrip(".") if x != int(x) else str(int(x))).replace(".", ",")


def _m(muc_do, tieu_de, chi_tiet, route):
    return {"muc_do": muc_do, "tieu_de": tieu_de, "chi_tiet": chi_tiet, "route": route}


def den(nhac):
    """Đèn của một mảng từ các mục nhắc của nó."""
    if any(x.get("muc_do") == CAO for x in nhac):
        return DO
    return VANG if nhac else XANH


# ── Từng mảng: số liệu thô → {so, nhan_so, dong, them} ────────────────────────────────────
# `them` = mục cảnh báo cho điều hộp nhắc chưa theo dõi (cùng dạng mục nhắc).

def _vong_kiem(s):
    dong = [f"Hôm nay {s.get('hom_nay_xong', 0)}/3 lượt đã xong" if s.get("hom_nay_sx")
            else "Hôm nay chưa có sản xuất / chưa có lượt nào"]
    thieu = int(s.get("ngay_thieu") or 0)
    dong.append(f"{thieu} ngày sản xuất thiếu lượt" if thieu else "Không ngày sản xuất nào thiếu lượt")
    dong.append(f"{s.get('ghi_muon', 0)} lượt ghi muộn · {s.get('chua_xem_xet', 0)} lượt chưa xem xét")
    if s.get("so_bo_sung"):
        dong.append(f"{s['so_bo_sung']} lượt bổ sung (mất điện / sự cố máy)")
    return {"so": f"{_so(s.get('ty_le'))}%", "nhan_so": f"lượt đủ · {s.get('so_luot', 0)}/{s.get('can_co', 0)}",
            "dong": dong}


def _su_co(s):
    return {"so": str(s.get("mo", 0)), "nhan_so": "phiếu đang mở",
            "dong": [f"{s.get('qua_han', 0)} quá hạn · {s.get('cao', 0)} mức Cao",
                     f"{s.get('ky', 0)} phiếu mới trong kỳ" + (f" · {s['dien_tap']} phiếu diễn tập"
                                                              if s.get("dien_tap") else "")]}


def _khac_phuc(s):
    return {"so": str(s.get("mo", 0)), "nhan_so": "phiếu chưa đóng",
            "dong": [f"{s.get('qua_han', 0)} quá hạn · {s.get('cho_kiem', 0)} chờ kiểm tra hiệu lực",
                     f"{s.get('lap_ky', 0)} lập · {s.get('dong_ky', 0)} đóng trong kỳ"]}


def _khieu_nai(s, route):
    mo, qua = int(s.get("mo") or 0), int(s.get("qua_han") or 0)
    dong = [f"{s.get('ky', 0)} khiếu nại mới trong kỳ"]
    if mo:
        dong.append(f"Mở lâu nhất {s.get('lau_nhat', 0)} ngày")
    them = []
    # Cùng hạn với phiếu sự cố (SX QC Setting → số ngày quá hạn) — màn khiếu nại tô đỏ đúng
    # những dòng này.
    if qua:
        them.append(_m(CAO, f"{qua} khiếu nại quá hạn xử lý",
                       "Đã quá số ngày xử lý của phiếu sự cố mà chưa đóng — xem kết luận, trả lời khách.", route))
    elif mo:
        them.append(_m(THUONG, f"{mo} khiếu nại đang mở, chưa quá hạn xử lý",
                       "Ghi kết luận, trả lời khách rồi đóng.", route))
    return {"so": str(mo), "nhan_so": "đang mở", "dong": dong, "them": them}


def _xuat_xuong(s):
    return {"so": str(s.get("cho_duyet", 0)), "nhan_so": "phiếu chờ duyệt",
            "dong": [f"{s.get('duyet', 0)} lô đã duyệt · {s.get('tra_lai', 0)} trả lại trong kỳ"]}


def _truy_xuat(s, route):
    thu_hoi = int(s.get("thu_hoi") or 0)
    dt = s.get("dien_tap")
    them = []
    if thu_hoi:
        them.append(_m(CAO, f"{thu_hoi} lô đang thu hồi, khoá xuất tới khi gỡ",
                       "Theo dõi hàng trả về, phiếu sự cố; xử lý xong thì gỡ thu hồi.", route))
    if not dt:
        dong = ["Chưa có lần diễn tập truy xuất nào trên app"]
        them.append(_m(THUONG, "Chưa diễn tập truy xuất lần nào",
                       "Bấm giờ diễn tập ở tab Truy xuất — bản in làm phụ lục BM.02.04.", route))
    else:
        dong = [f"Diễn tập gần nhất {_ngay(dt.get('ngay'))} — cân bằng {_so(dt.get('can_bang_pt'))}%"
                f" ({'đạt' if dt.get('dat') else 'chưa đạt'})"]
        if int(dt.get("so_ngay") or 0) > DIEN_TAP_TOI_DA_NGAY:
            them.append(_m(THUONG, "Quá 12 tháng chưa diễn tập truy xuất",
                           f"Lần gần nhất {_ngay(dt.get('ngay'))}.", route))
        elif not dt.get("dat"):
            them.append(_m(THUONG, f"Diễn tập gần nhất chưa đạt cân bằng {CAN_BANG_DAT}%",
                           f"{_ngay(dt.get('ngay'))}: {_so(dt.get('can_bang_pt'))}% — tìm chỗ hụt, diễn tập lại.",
                           route))
    return {"so": str(thu_hoi), "nhan_so": "lô đang thu hồi", "dong": dong, "them": them}


def _thiet_bi(s):
    dong = [f"{s.get('qua_han', 0)} quá hạn · {s.get('khong_dat', 0)} không đạt · "
            f"{s.get('sap_den', 0)} sắp đến hạn"]
    if s.get("thieu_loai"):
        dong.append("Chưa khai: " + ", ".join(s["thieu_loai"]).lower())
    return {"so": str(s.get("dang_dung", 0)), "nhan_so": "thiết bị trong danh mục", "dong": dong}


def _kiem_nghiem(s):
    return {"so": f"{s.get('dat', 0)}/{s.get('tong', 0)}", "nhan_so": "sản phẩm có kết quả đạt còn hạn",
            "dong": [f"{s.get('qua_han', 0)} quá hạn · {s.get('den_han', 0)} đến hạn · "
                     f"{s.get('cho_kq', 0)} chờ kết quả · {s.get('khong_dat', 0)} không đạt"]}


def _cat(s):
    if not s.get("co_du_lieu"):
        return {"so": "–", "nhan_so": "chưa có nhật ký cát", "dong": []}
    dong = [f"Nguồn: {s.get('ncc') or '—'}"]
    if s.get("cho_kln"):
        dong.append(f"{s['cho_kln']} lần đổi nguồn chờ kết quả kim loại nặng")
    # W32: đã loại mà chưa ghi cát mới đưa vào máy → không có số ngày để nói.
    if s.get("dang_dung") is False:
        return {"so": "–", "nhan_so": "không có cát đang dùng (đã loại, chưa ghi cát mới)", "dong": dong}
    return {"so": str(s.get("so_ngay", 0)),
            "nhan_so": "ngày cát đang dùng" + (f" / tối đa {s['toi_da']}" if s.get("toi_da") else ""), "dong": dong}


def _vai_u(s):
    if not s.get("dang_dung") and not s.get("so_lan"):
        return {"so": "–", "nhan_so": "chưa khai vải ủ / chưa ghi sổ giặt", "dong": []}
    dong = [f"Giặt gần nhất {_ngay(s['lan_cuoi'])} · chu kỳ {s.get('chu_ky') or 7} ngày" if s.get("lan_cuoi")
            else "Chưa có lần giặt định kỳ nào",
            f"{s.get('dang_dung', 0)} vải đang dùng · {s.get('du_phong', 0)} dự phòng · {s.get('da_loai', 0)} đã loại"]
    if s.get("cho_ky"):
        dong.append(f"{s['cho_ky']} dòng chờ QC ký")
    return {"so": str(s.get("so_lan", 0)), "nhan_so": "lần giặt trong kỳ", "dong": dong}


def _kiem_xe(s):
    n = int(s.get("so_chuyen") or 0)
    if not n and not s.get("tuan"):
        return {"so": "–", "nhan_so": "chưa có chuyến nào ghi kiểm xe", "dong": []}
    return {"so": f"{s.get('tuan_qc', 0)}/{s.get('tuan', 0)}", "nhan_so": "tuần có chuyến được QC kiểm xe",
            "dong": [f"{n} chuyến · {s.get('khong_dat', 0)} xe không đạt"]}


def _dong_vat(s):
    k = int(s.get("khu_hai_tuan") or 0)
    return {"so": str(s.get("dau_hieu", 0)), "nhan_so": "lần thấy dấu hiệu trong kỳ",
            "dong": [f"{k} khu có dấu hiệu 2 tuần liền" if k else "Không khu nào có dấu hiệu 2 tuần liền"]}


def _ncc(s, route):
    tong, duyet, thieu = int(s.get("tong") or 0), int(s.get("duyet") or 0), int(s.get("thieu") or 0)
    them = []
    # W09: chỉ cảnh báo, không chặn mua — nên tối đa là Vàng.
    if tong > duyet:
        them.append(_m(THUONG, f"{tong - duyet} nhà cung cấp chưa duyệt",
                       "Đã phân loại nhưng chưa tích Đã duyệt (BM.07.02).", route))
    if thieu:
        them.append(_m(THUONG, f"{thieu} nhà cung cấp thiếu / hết hạn hồ sơ",
                       "Xem cột Thiếu trên danh sách NCC được duyệt.", route))
    return {"so": f"{duyet}/{tong}", "nhan_so": "nhà cung cấp đã duyệt",
            "dong": [f"{thieu} thiếu / hết hạn hồ sơ"], "them": them}


def _luu_mau(s):
    return {"so": str(s.get("dang_luu", 0)), "nhan_so": "mẫu đang lưu",
            "dong": [f"{s.get('den_han', 0)} mẫu đến hạn huỷ · {s.get('dot_cho', 0)} đợt chờ xác nhận"]}


def _rework(s):
    n = int(s.get("so") or 0)
    return {"so": str(n), "nhan_so": "phiếu trong kỳ",
            "dong": [f"Cao nhất {_so(s.get('cao_nhat'))}% khối lượng mẻ (tối đa 10%)" if n else "Không có phiếu"]}


def _tai_lieu(s):
    """W42: tài liệu hiện hành; đợt chờ người đọc, đề nghị chờ, tài liệu bên ngoài chưa soát xét."""
    if not s.get("tong"):
        return {"so": "–", "nhan_so": "chưa nạp thư viện tài liệu", "dong": []}
    return {"so": str(s.get("hien_hanh", 0)), "nhan_so": "tài liệu hiện hành",
            "dong": [f"{s.get('chua_doc', 0)} lượt chưa xác nhận đọc · {s.get('de_nghi', 0)} đề nghị đang chờ",
                     f"{s.get('ngoai', 0)} tài liệu bên ngoài · {s.get('soat_xet', 0)} quá 12 tháng chưa soát xét"]}


def _so_khac(s):
    """W43: các sổ ghi theo dòng thuộc thẻ "Sổ khác" (khách vào xưởng, PCCC, dịch bệnh, kiểm định an toàn…)."""
    if not s.get("so_so"):
        return {"so": "–", "nhan_so": "chưa có sổ nào", "dong": []}
    return {"so": str(s.get("dong_ky", 0)), "nhan_so": f"dòng ghi trong kỳ · {s['so_so']} sổ",
            "dong": [f"{s.get('cho', 0)} dòng chờ xác nhận · {s.get('han', 0)} mục đến / quá hạn",
                     ", ".join(s.get("ma") or [])]}


def _bien_ban(s):
    """W45: biên bản chờ ký, ký đủ / đang soạn trong kỳ; họp Ban ISO gần nhất."""
    if not s.get("so_mau"):
        return {"so": "–", "nhan_so": "chưa khai mẫu biên bản", "dong": []}
    return {"so": str(s.get("cho_ky", 0)), "nhan_so": "biên bản chờ ký",
            "dong": [f"{s.get('ky_du', 0)} biên bản ký đủ trong kỳ · {s.get('nhap', 0)} đang soạn",
                     f"Họp Ban ISO gần nhất {_ngay(s['hop_cuoi'])}" if s.get("hop_cuoi")
                     else "Chưa có biên bản họp Ban ISO trên app"]}


def _viec_dinh_ky(s):
    t = s.get("tiep")
    return {"so": str(s.get("qua_han", 0)), "nhan_so": "việc quá hạn",
            "dong": [f"Tiếp theo: {t['ten']} — {_ngay(t['han'])}" if t else "Chưa có việc định kỳ nào"]}


THE = {"vong_kiem": _vong_kiem, "su_co": _su_co, "khac_phuc": _khac_phuc, "xuat_xuong": _xuat_xuong,
       "thiet_bi": _thiet_bi,
       "kiem_nghiem": _kiem_nghiem, "cat": _cat, "vai_u": _vai_u, "dong_vat": _dong_vat, "kiem_xe": _kiem_xe,
       "luu_mau": _luu_mau,
       "rework": _rework, "viec_dinh_ky": _viec_dinh_ky, "tai_lieu": _tai_lieu, "bien_ban": _bien_ban,
       "so_khac": _so_khac}
THE_ROUTE = {"khieu_nai": _khieu_nai, "truy_xuat": _truy_xuat, "ncc": _ncc}


def tong_hop(nhac, so_lieu):
    """{linh_vuc: [thẻ], dem: {do, vang, xanh}} — thẻ đỏ lên trước, cùng màu giữ thứ tự LINH_VUC.

    `nhac` = sx.qc.nhac.tinh(...) (mỗi mục có `nhom`); `so_lieu` = {mã mảng: số liệu thô}.
    Mảng không có số liệu (site chưa dùng / chưa migrate) vẫn hiện, số là "–"."""
    theo = {}
    for x in nhac:
        theo.setdefault(x.get("nhom"), []).append(x)
    ds = []
    for i, (ma, ten, bm, route) in enumerate(LINH_VUC):
        s = so_lieu.get(ma)
        if s is None:
            t = {"so": "–", "nhan_so": "chưa có số liệu", "dong": []}
        else:
            t = THE_ROUTE[ma](s, route) if ma in THE_ROUTE else THE[ma](s)
        nh = theo.get(ma, []) + t.get("them", [])
        nh.sort(key=lambda x: 0 if x.get("muc_do") == CAO else 1)
        ds.append({"ma": ma, "ten": ten, "bieu_mau": bm, "route": route, "den": den(nh), "so": t["so"],
                   "nhan_so": t["nhan_so"], "dong": t["dong"], "nhac": nh, "_i": i})
    ds.sort(key=lambda x: (THU_TU_DEN[x["den"]], x["_i"]))
    for x in ds:
        x.pop("_i")
    return {"linh_vuc": ds, "dem": {k: sum(1 for x in ds if x["den"] == k) for k in (DO, VANG, XANH)}}
