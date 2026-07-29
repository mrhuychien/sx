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
from frappe.utils import cint, flt, getdate

from sx.api.mfg import cancel_doc, loai_phieu_kho, tao_batch, tao_se_manufacture, tao_wo
from sx.config.roles import guard_card
from sx.utils import (
    cho_phep_ton_am,
    get_bom_active,
    get_settings,
    sinh_ma_lo,
    topo_rank_by_bom,
)


@frappe.whitelist()
def chot_ngay(ngay_sx):
    """Chốt ngày: validate -> T2 (topo) -> submit vào hộp -> T3 -> SalaryProduct
    -> tổng hợp + submit. Lỗi giữa chừng: rollback toàn bộ, báo bước hỏng."""
    guard_card("chotngay")
    doc = frappe.get_doc("SX Ngay San Xuat", ngay_sx)

    # Validate NGOÀI try/except: lỗi nghiệp vụ (đã chốt, thiếu tồn, thiếu đơn giá)
    # phải nổi lên NGUYÊN VĂN cho QC, không bị nuốt thành "check Error Log" + traceback.
    bang = _validate_truoc_chot(doc)
    co_vao_hop = _co_gi_de_ghi(bang)

    buoc = _("bắt đầu sinh chứng từ")
    canh_bao = []
    try:
        chung_tu = []  # [{dt, name}] theo thứ tự sinh — để huỷ ngược

        buoc = _("tầng 2 (nấu + trộn theo báo mẻ)")
        _chot_tang_2(doc, chung_tu)

        ds_salary = []
        if co_vao_hop:
            buoc = _("submit bảng vào hộp")
            if bang.docstatus == 0:
                bang.flags.ignore_permissions = True
                bang.submit()

            buoc = _("tầng 3 (thành phẩm)")
            _chot_tang_3(doc, bang, chung_tu)

            buoc = _("ghi phiếu lương khoán")
            ds_salary = _ghi_luong_khoan(doc, bang)

        buoc = _("tổng hợp + submit phiếu ngày")
        doc.tong_hop_tp = cint(bang.tong_hop) if co_vao_hop else 0
        doc.tong_luong_sp = flt(bang.tong_tien) if co_vao_hop else 0
        doc.ds_wo_se = json.dumps(chung_tu)
        doc.salary_products_json = json.dumps(ds_salary)
        doc.flags.tu_chot_ngay = True
        doc.save()
        doc.submit()

        canh_bao = _canh_bao_mem(doc)
    except Exception:
        frappe.db.rollback()
        frappe.log_error(
            title=f"chot_ngay {ngay_sx} hỏng ở bước: {buoc}",
            message=frappe.get_traceback(),
        )
        frappe.throw(
            _("Chốt ngày THẤT BẠI ở bước: {0}. Toàn bộ đã được hoàn tác — "
              "không có trạng thái nửa vời. Chi tiết trong Error Log.").format(buoc)
        )

    return {
        "name": doc.name,
        "trang_thai": doc.trang_thai,
        "tong_hop_tp": doc.tong_hop_tp,
        "tong_luong_sp": doc.tong_luong_sp,
        "canh_bao": canh_bao,
    }


# ─────────────────────────────────────────────── validate ──


def _validate_truoc_chot(doc):
    if doc.docstatus == 1:
        frappe.throw(_("Phiếu ngày {0} ĐÃ chốt rồi.").format(doc.name))
    if doc.docstatus == 2:
        frappe.throw(_("Phiếu ngày {0} đã huỷ.").format(doc.name))

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
    # TẠI ĐÂY (ngoài try) để QC đọc được nguyên nhân thật, không phải "check Error Log".
    loai_phieu_kho("Manufacture")

    ten_bang = frappe.db.get_value(
        "SX Bang Vao Hop", {"ngay_sx": doc.name, "docstatus": ("<", 2)}, "name"
    )
    bang = frappe.get_doc("SX Bang Vao Hop", ten_bang) if ten_bang else None

    # Ít nhất một trong {bao_me có dòng, bảng vào hộp có dòng} — ngày rỗng vô nghĩa
    co_bao_me = len(doc.bao_me) > 0
    co_vao_hop = _co_gi_de_ghi(bang)
    if not co_bao_me and not co_vao_hop:
        frappe.throw(
            _("Ngày chưa có báo mẻ lẫn bảng vào hộp — không có gì để chốt.")
        )

    if bang and bang.docstatus == 0:
        # Controller lookup đơn giá khi save — save lại để chắc mọi dòng có giá
        bang.flags.ignore_permissions = True
        bang.save()

    _kiem_ton_kho(doc, bang, settings)
    return bang


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


def _tong_hop_theo_sp(bang):
    """Σ số hộp theo SKU. Dòng KHÔNG có SKU (loại công việc chưa gắn Item TP — D23)
    chỉ tính lương khoán, không sinh lệnh SX tầng 3 nên bỏ qua ở đây."""
    tong = {}
    for r in bang.dong:
        if not r.san_pham:
            continue
        tong[r.san_pham] = tong.get(r.san_pham, 0) + cint(r.so_hop)
    return tong


def _kiem_ton_kho(doc, bang, settings):
    """Kiểm đủ tồn TRƯỚC khi sinh chứng từ. BTP sinh trong chốt (bao_me) được cộng
    tín dụng (xấp xỉ — FIFO thật ở bước sinh sẽ bắt thiếu chính xác & rollback)."""
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

    if bang:
        for sp, so_hop in _tong_hop_theo_sp(bang).items():
            bom_sp = get_bom_active(sp)
            if not bom_sp:
                frappe.throw(_("Sản phẩm {0} chưa có BOM active").format(sp))
            for item_code, can in _nhu_cau_bom(bom_sp, so_hop).items():
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


def _chot_tang_3(doc, bang, chung_tu):
    """Mỗi SKU trong bảng vào hộp: Batch TP -> WO -> SE (RM bột bánh/đậu FIFO Kho BTP
    + bao bì Kho NVL; FG vào Kho TP). Trả {sku: batch}."""
    settings = get_settings()
    ket_qua = {}
    for sp, so_hop in _tong_hop_theo_sp(bang).items():
        if so_hop <= 0:
            continue
        bom_sp = get_bom_active(sp)
        batch = tao_batch(sp, sinh_ma_lo(sp, doc.ngay), ngay_sx=doc.name)
        wo = tao_wo(
            settings.cong_ty, sp, so_hop, bom_sp,
            source_wh=settings.kho_nvl, fg_wh=settings.kho_tp,
            ngay_sx=doc.name, planned_date=doc.ngay,
        )
        se = tao_se_manufacture(
            wo, so_hop, batch,
            kho_nguon=lambda item: _kho_nguon(item, settings),
            ngay=doc.ngay, ngay_sx=doc.name,
        )
        ket_qua[sp] = batch
        chung_tu.append({"dt": "Work Order", "name": wo.name})
        chung_tu.append({"dt": "Stock Entry", "name": se.name})
    return ket_qua


# ─────────────────────────────────────── phiếu lương khoán (SalaryProduct) ──
#
# Schema thật (app lam-luong):
#   SalaryProduct   = phiếu THÁNG của MỘT nhân viên (employee, month, year), submittable.
#   child luongkhoan (SalaryProductDetail2) = MỘT DÒNG MỖI NGÀY, mỗi dòng tối đa 6 loại
#   công việc: sp1..sp6 (tên Activity Type, kiểu Data) · sl1..sl6 · dg1..dg6 · tt1..tt6,
#   cộng tienanca/andem do bộ phận lương điền, thunhapngay = Σtt + tienanca.
#
# Chốt ngày UPSERT đúng dòng của ngày đó trong phiếu tháng, để phiếu ở DRAFT —
# bộ phận lương kiểm và submit cuối tháng. KHÔNG đụng ăn ca / chuyên cần / bảo hiểm.

SALARY_DT = "SalaryProduct"
SALARY_CHILD = "luongkhoan"
SP_MAX = 6  # schema chỉ có 6 slot sp1..sp6


def _kiem_salary_doctype():
    if not frappe.db.exists("DocType", SALARY_DT):
        frappe.throw(
            _("Không tìm thấy DocType {0} (app lương khoán). Cài app đó trước khi chốt ngày.")
            .format(SALARY_DT)
        )


def _phieu_luong_thang(employee, ngay, settings):
    """Phiếu lương khoán THÁNG (draft) của 1 nhân viên — có thì lấy, chưa có thì tạo."""
    ten = frappe.db.get_value("Employee", employee, "employee_name") or employee
    chung = {"employee": employee, "month": ngay.month, "year": ngay.year}

    da_duyet = frappe.db.get_value(SALARY_DT, dict(chung, docstatus=1), "name")
    if da_duyet:
        frappe.throw(
            _("Phiếu lương khoán {0} của {1} tháng {2}/{3} ĐÃ duyệt — không ghi thêm được. "
              "Nhờ bộ phận lương huỷ/amend phiếu đó rồi chốt ngày lại.").format(
                da_duyet, ten, ngay.month, ngay.year)
        )

    dang_co = frappe.db.get_value(SALARY_DT, dict(chung, docstatus=0), "name")
    if dang_co:
        return frappe.get_doc(SALARY_DT, dang_co)

    phieu = frappe.new_doc(SALARY_DT)
    phieu.employee = employee
    phieu.company = settings.cong_ty
    phieu.ngay = ngay
    phieu.month = ngay.month
    phieu.year = ngay.year
    phieu.status = "Nháp"
    phieu.title = f"{ten.upper()} T{ngay.month}.{ngay.year}"
    return phieu


def _dong_ngay(phieu, ngay):
    for r in phieu.get(SALARY_CHILD) or []:
        if r.ngay and getdate(r.ngay) == ngay:
            return r
    return phieu.append(SALARY_CHILD, {"ngay": ngay})


def _ghi_an(dong, fieldname, co_an, so_tien):
    """Ghi 1 ô ăn ca / ăn đêm theo ĐÚNG kiểu field bên app lương (D30).

    Check  -> đánh dấu 1/0, tiền do bên lương tự quy đổi (không cộng vào thu nhập).
    Số     -> ghi số tiền lấy từ SX Settings, và CÓ cộng vào thunhapngay.
    Trả phần tiền đã ghi (0 nếu là ô đánh dấu / không có field).
    """
    df = frappe.get_meta(SALARY_CHILD).get_field(fieldname)
    if not df:
        return 0.0
    if df.fieldtype == "Check":
        dong.set(fieldname, 1 if co_an else 0)
        return 0.0
    tien = flt(so_tien) if co_an else 0.0
    dong.set(fieldname, tien)
    return tien


def _ghi_dong_ngay(dong, cong_viec, an_ca=False, an_dem=False, settings=None):
    """Ghi ĐÈ dòng ngày: 6 slot công việc + ăn ca/ăn đêm (chốt lại = thay, không cộng dồn)."""
    for i in range(1, SP_MAX + 1):
        dong.set(f"sp{i}", None)
        dong.set(f"sl{i}", 0)
        dong.set(f"dg{i}", 0)
        dong.set(f"tt{i}", 0)
    tong = 0.0
    for i, (act, sl, dg) in enumerate(cong_viec, start=1):
        tt = flt(dg) * cint(sl)
        dong.set(f"sp{i}", act)
        dong.set(f"sl{i}", cint(sl))
        dong.set(f"dg{i}", flt(dg))
        dong.set(f"tt{i}", tt)
        tong += tt
    settings = settings or get_settings()
    tien_an = _ghi_an(dong, "tienanca", an_ca, settings.get("tien_an_ca"))
    tien_an += _ghi_an(dong, "andem", an_dem, settings.get("tien_an_dem"))
    dong.thunhapngay = tong + tien_an
    return tong


def _tinh_lai_luong_san_pham(phieu):
    phieu.luongsanpham = sum(
        flt(r.get(f"tt{i}"))
        for r in (phieu.get(SALARY_CHILD) or [])
        for i in range(1, SP_MAX + 1)
    )


def _ghi_luong_khoan(doc, bang):
    """Ghi sản lượng khoán của ngày vào phiếu lương khoán tháng của từng công nhân.

    Gộp theo (nhân viên, loại công việc): 1 người vào nhiều SKU cùng loại thì cộng dồn
    số lượng — đúng cách bảng lương ghi (sp = loại công việc, không phải SKU).
    Trả danh sách {phieu, employee, ngay} để huỷ ngày gỡ đúng dòng.
    """
    _kiem_salary_doctype()
    ngay = getdate(doc.ngay)
    settings = get_settings()

    gop = {}
    for r in bang.dong:
        if not r.activity_type:
            frappe.throw(
                _("Dòng {0}: sản phẩm {1} chưa gán loại công việc khoán (Activity Type).")
                .format(r.idx, r.san_pham)
            )
        key = (r.nhan_vien, r.activity_type)
        cu = gop.get(key)
        if cu:
            cu["sl"] += cint(r.so_hop)
        else:
            gop[key] = {"sl": cint(r.so_hop), "dg": flt(r.don_gia)}

    theo_nguoi = {}
    for (nv, act), g in gop.items():
        theo_nguoi.setdefault(nv, []).append((act, g["sl"], g["dg"]))

    # Ăn ca / ăn đêm (D30): người CHỈ được chấm ăn (không vào hộp) vẫn phải có dòng
    an = {}
    for r in bang.get("an_ca") or []:
        if not (cint(r.an_ca) or cint(r.an_dem)):
            continue
        an[r.nhan_vien] = (cint(r.an_ca), cint(r.an_dem))
        theo_nguoi.setdefault(r.nhan_vien, [])

    ds_ghi = []
    for nv, cong_viec in theo_nguoi.items():
        if len(cong_viec) > SP_MAX:
            ten = frappe.db.get_value("Employee", nv, "employee_name") or nv
            frappe.throw(
                _("{0} làm {1} loại công việc trong ngày, phiếu lương khoán chỉ chứa được "
                  "{2} loại/ngày. Gộp bớt loại hoặc nhờ bộ phận lương mở rộng bảng.").format(
                    ten, len(cong_viec), SP_MAX)
            )
        co_an_ca, co_an_dem = an.get(nv, (0, 0))
        phieu = _phieu_luong_thang(nv, ngay, settings)
        _ghi_dong_ngay(
            _dong_ngay(phieu, ngay), cong_viec,
            an_ca=co_an_ca, an_dem=co_an_dem, settings=settings,
        )
        _tinh_lai_luong_san_pham(phieu)
        phieu.flags.ignore_permissions = True
        phieu.save()
        ds_ghi.append({"phieu": phieu.name, "employee": nv, "ngay": str(ngay)})
    return ds_ghi


def _go_luong_khoan(ds_ghi):
    """Huỷ ngày: gỡ ĐÚNG dòng của ngày đó khỏi phiếu tháng (không xoá cả phiếu)."""
    log = []
    for g in ds_ghi or []:
        ten_phieu, ngay = g.get("phieu"), getdate(g.get("ngay"))
        if not ten_phieu or not frappe.db.exists(SALARY_DT, ten_phieu):
            continue
        phieu = frappe.get_doc(SALARY_DT, ten_phieu)
        if phieu.docstatus != 0:
            log.append(
                f"Phiếu lương {ten_phieu} đã duyệt — KHÔNG gỡ được dòng ngày {ngay}, xử lý tay"
            )
            continue
        con_lai = [r for r in (phieu.get(SALARY_CHILD) or [])
                   if not (r.ngay and getdate(r.ngay) == ngay)]
        if len(con_lai) == len(phieu.get(SALARY_CHILD) or []):
            continue
        phieu.set(SALARY_CHILD, con_lai)
        _tinh_lai_luong_san_pham(phieu)
        phieu.flags.ignore_permissions = True
        phieu.save()
        log.append(f"Gỡ dòng {ngay} khỏi phiếu lương {ten_phieu}")
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
        _them(_("Phiếu lương khoán"), SALARY_DT, g.get("phieu"), ten_nv)

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
    moi.salary_products_json = None
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
    chung_tu = json.loads(doc.ds_wo_se) if doc.ds_wo_se else []
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

    if log:
        ghi_chu = (doc.ghi_chu or "") + "\n[Huỷ ngày] " + "; ".join(log)
        doc.db_set("ghi_chu", ghi_chu.strip(), update_modified=False)
