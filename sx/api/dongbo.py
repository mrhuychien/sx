"""Đồng bộ ngầm kho + lương theo ngày (D123) — thay cho CHỐT GHI SỔ / CHỐT VÀO HỘP.

═══ VÌ SAO BỎ CHỐT ═══
Chốt là một bước người phải nhớ bấm, và bấm rồi thì khoá: sửa một mẻ là phải huỷ chốt,
sửa, chốt lại. Thực tế xưởng sửa số liên tục (báo mẻ thiếu, chấm nhầm người), nên
chốt thành cái gờ ai cũng vấp. Giờ: số liệu LUÔN sửa / xoá được; hệ thống tự đưa
chứng từ kho + phiếu lương về khớp với số liệu hiện tại.

═══ CƠ CHẾ ═══
  lưu báo mẻ          → đánh dấu ngày `can_dong_bo_gs`  ┐
  lưu bảng vào hộp    → đánh dấu ngày `can_dong_bo_vh`  ├→ job nền `chay(ngay_sx)`
  (dự phòng) mỗi 5 phút quét ngày còn dấu, không có lỗi ┘

GHI SỔ — so SỐ ĐÃ GHI SỔ (`so_cai_ghiso`: [{item, kg, batch, wo, se}]) với tổng kg
báo mẻ hiện tại, THEO TỪNG MÃ, xếp topo (đường hoán trước bột bánh):
  · bằng nhau           → không đụng gì (mã khác đổi không kéo mã này theo);
  · báo mẻ nhiều hơn    → ghi THÊM phần chênh (WO + SE Manufacture), CÙNG lô của mã
                          trong ngày — một mã một lô một ngày như trước;
  · báo mẻ ít hơn       → rút chứng từ mới nhất của mã đó, rồi ghi lại phần còn thiếu.
Mỗi mã một savepoint: mã này hỏng (thiếu tồn, bột đã bị dùng để nhập TP nên không
rút ra được…) thì mã khác vẫn đồng bộ, và lỗi ghi lên ngày để người xem biết.

VÀO HỘP — ghi đè ĐÚNG ngày đó trong phiếu lương tháng của từng người (như chốt cũ),
gỡ ngày đó khỏi người không còn trong bảng, đối chiếu sổ nợ đơn giá (giữ nợ còn
thiếu, huỷ nợ đã hết thiếu, thêm nợ mới).

Lỗi: ghi vào `loi_dong_bo_gs/vh`, giữ dấu "cần đồng bộ". Job dự phòng KHÔNG tự thử lại
ngày đang lỗi (thử đi thử lại mỗi 5 phút chỉ đầy Error Log) — sửa số liệu (lưu lại là
xoá lỗi) hoặc quản lý bấm "Thử lại" trên lịch.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime

NGAY = "SX Ngay San Xuat"
PHAN = ("gs", "vh")


# ═══════════════════════════════ đánh dấu + chạy ═══════════════════════════════

def danh_dau(ngay_sx, phan, chay_ngay=True):
    """Ngày `ngay_sx` vừa đổi số liệu phần `phan` ("gs" | "vh"): đánh dấu, xoá lỗi
    cũ (số liệu mới có thể đã sửa được lỗi), xếp job đồng bộ chạy sau khi lưu xong."""
    if not ngay_sx or phan not in PHAN:
        return
    frappe.db.set_value(NGAY, ngay_sx, {f"can_dong_bo_{phan}": 1, f"loi_dong_bo_{phan}": None},
                        update_modified=False)
    if chay_ngay:
        xep_job(ngay_sx)


def xep_job(ngay_sx):
    try:
        frappe.enqueue("sx.api.dongbo.chay", queue="short", ngay_sx=ngay_sx,
                       job_id=f"sx-dongbo-{ngay_sx}", deduplicate=True,
                       enqueue_after_commit=True)
    except Exception:
        # Không có Redis / worker (máy dev, test): job dự phòng 5 phút sẽ làm.
        frappe.log_error(title="sx: không xếp được job đồng bộ", message=frappe.get_traceback())


def chay(ngay_sx, ca_loi=False):
    """Đồng bộ một ngày cho tới khi hết dấu (tối đa 3 vòng — có người sửa tiếp trong
    lúc đang chạy thì vòng sau bắt kịp). `ca_loi`: chạy cả phần đang báo lỗi."""
    for _vong in range(3):
        if not frappe.db.exists(NGAY, ngay_sx):
            return
        # Khoá dòng phiếu ngày: hai job cùng một ngày không được chạy song song —
        # cả hai cùng thấy "thiếu 50 kg" là ghi hai lần.
        frappe.db.sql(f"select name from `tab{NGAY}` where name=%s for update", ngay_sx)
        d = frappe.db.get_value(NGAY, ngay_sx, ["can_dong_bo_gs", "can_dong_bo_vh",
                                                "loi_dong_bo_gs", "loi_dong_bo_vh"],
                                as_dict=True)
        lam = [p for p in PHAN if cint(d.get(f"can_dong_bo_{p}"))
               and (ca_loi or not d.get(f"loi_dong_bo_{p}"))]
        if not lam:
            return
        for p in lam:
            frappe.db.set_value(NGAY, ngay_sx, f"can_dong_bo_{p}", 0, update_modified=False)
        doc = frappe.get_doc(NGAY, ngay_sx)
        for p in lam:
            loi = dong_bo_ghiso(doc) if p == "gs" else dong_bo_vaohop(doc)
            frappe.db.set_value(NGAY, ngay_sx,
                                {f"can_dong_bo_{p}": 1, f"loi_dong_bo_{p}": "\n".join(loi)}
                                if loi else {f"loi_dong_bo_{p}": None},   # khớp rồi: xoá lỗi cũ
                                update_modified=False)
        frappe.db.set_value(NGAY, ngay_sx, "dong_bo_luc", now_datetime(), update_modified=False)
        frappe.db.commit()


def chay_tat_ca():
    """Scheduler mỗi 5 phút: ngày còn dấu mà không đang lỗi (job lỡ / không có worker)."""
    ds = frappe.get_all(NGAY, filters={"docstatus": ("<", 2)},
                        or_filters=[["can_dong_bo_gs", "=", 1], ["can_dong_bo_vh", "=", 1]],
                        pluck="name", limit=50)
    for ten in ds:
        try:
            chay(ten)
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title=f"sx: đồng bộ {ten} hỏng", message=frappe.get_traceback())


@frappe.whitelist()
def thu_lai(ngay_sx):
    """Quản lý bấm "Thử lại / Đồng bộ ngay" trên lịch: chạy luôn, cả phần đang lỗi."""
    from sx.config.roles import guard_card

    guard_card("lichchot")
    d = frappe.db.get_value(NGAY, ngay_sx, ["name"], as_dict=True)
    if not d:
        frappe.throw(_("Không tìm thấy phiếu ngày {0}.").format(ngay_sx))
    # Ngày chưa từng đồng bộ (dữ liệu cũ) cũng phải chạy được khi bấm tay.
    frappe.db.set_value(NGAY, ngay_sx, {"can_dong_bo_gs": 1, "can_dong_bo_vh": 1},
                        update_modified=False)
    chay(ngay_sx, ca_loi=True)
    return trang_thai(ngay_sx)


def trang_thai(ngay_sx):
    d = frappe.db.get_value(NGAY, ngay_sx, ["can_dong_bo_gs", "can_dong_bo_vh",
                                            "loi_dong_bo_gs", "loi_dong_bo_vh", "dong_bo_luc"],
                            as_dict=True) or {}
    return {p: {"cho": cint(d.get(f"can_dong_bo_{p}")), "loi": d.get(f"loi_dong_bo_{p}")}
            for p in PHAN} | {"luc": str(d.get("dong_bo_luc") or "")}


def _chu(e):
    """Câu lỗi đọc được: bỏ thẻ HTML, gom tin của frappe.throw."""
    s = str(e) or e.__class__.__name__
    s = re.sub(r"<br\s*/?>", " ", s)
    return re.sub(r"<[^>]+>", "", s).strip()[:400]


def _savepoint(ten):
    try:
        frappe.db.savepoint(ten)
        return True
    except Exception:
        return False


def _ve_savepoint(ten, co):
    if co:
        frappe.db.rollback(save_point=ten)
    # Tin nhắn msgprint của lần hỏng không được trôi sang lần sau.
    try:
        frappe.local.message_log = []
    except Exception:
        pass


# ═══════════════════════════════ GHI SỔ ═══════════════════════════════

def _so_cai(doc):
    try:
        return json.loads(doc.get("so_cai_ghiso") or "[]")
    except (ValueError, TypeError):
        return []


def dong_bo_ghiso(doc):
    """Đưa chứng từ kho tầng 2 về khớp báo mẻ hiện tại. Trả danh sách lỗi (rỗng = ổn)."""
    from sx.api.chot import _kho_nguon, _nhu_cau_bom
    from sx.api.mfg import (cancel_doc, ghi_gia_tu_tinh, tao_batch,
                            tao_se_manufacture, tao_wo, xet_gia_von)
    from sx.utils import get_bom_active, get_settings, sinh_ma_lo, topo_rank_by_bom

    settings = get_settings()
    so_cai = _so_cai(doc)
    muc_tieu = {}
    for r in doc.bao_me:
        if r.item_btp and flt(r.tong_kg) > 0:
            muc_tieu[r.item_btp] = flt(muc_tieu.get(r.item_btp, 0) + flt(r.tong_kg), 3)
    da_ghi = {}
    for e in so_cai:
        da_ghi[e["item"]] = flt(da_ghi.get(e["item"], 0) + flt(e["kg"]), 3)
    doi = [i for i in set(muc_tieu) | set(da_ghi)
           if abs(flt(muc_tieu.get(i)) - flt(da_ghi.get(i))) > 1e-6]
    if not doi:
        return []
    rank = topo_rank_by_bom(doi)
    doi.sort(key=lambda i: rank.get(i, 0))
    loi = []

    # Giá vốn trước khi ghi thêm (D116/D118): BTP tự tính, NVL thiếu giá thì dừng phần tăng.
    can = {}
    for i in doi:
        them = flt(muc_tieu.get(i)) - flt(da_ghi.get(i))
        bom = get_bom_active(i)
        if them > 0 and bom:
            for it, so in _nhu_cau_bom(bom, them).items():
                k = (it, _kho_nguon(it, settings))
                can[k] = can.get(k, 0) + so
    gia = xet_gia_von({k for k in can if k[0] not in muc_tieu})
    if gia["tu_tinh"]:
        ghi_gia_tu_tinh(gia["tu_tinh"])
    chan_tang = None
    if gia["hoi"]:
        chan_tang = _("Thiếu giá vốn: {0} — khai giá ở lịch Đồng bộ (màn Quản lý) rồi bấm "
                      "Thử lại.").format(", ".join(d["ten"] for d in gia["hoi"]))
        loi.append(chan_tang)

    for item in doi:
        t = flt(muc_tieu.get(item))
        cua_ma = [e for e in so_cai if e["item"] == item]
        ten_sp = f"sx_gs_{abs(hash(item)) % 10**8}"
        co = _savepoint(ten_sp)
        try:
            # Giảm: rút chứng từ MỚI NHẤT trước cho tới khi số đã ghi ≤ mục tiêu.
            while cua_ma and flt(sum(flt(e["kg"]) for e in cua_ma)) - t > 1e-6:
                e = cua_ma.pop()
                cancel_doc("Stock Entry", e.get("se"))
                cancel_doc("Work Order", e.get("wo"))
                so_cai.remove(e)
            thieu = flt(t - sum(flt(e["kg"]) for e in cua_ma), 3)
            if thieu > 1e-6:
                if chan_tang:
                    raise frappe.ValidationError(chan_tang)
                bom = get_bom_active(item)
                if not bom:
                    raise frappe.ValidationError(_("chưa có BOM active"))
                lo = (cua_ma[0].get("batch") if cua_ma else None) \
                    or tao_batch(item, sinh_ma_lo(item, doc.ngay), ngay_sx=doc.name)
                wo = tao_wo(settings.cong_ty, item, thieu, bom,
                            source_wh=settings.kho_nvl, fg_wh=settings.kho_btp,
                            ngay_sx=doc.name, planned_date=doc.ngay)
                se = tao_se_manufacture(wo, thieu, lo,
                                        kho_nguon=lambda it: _kho_nguon(it, settings),
                                        ngay=doc.ngay, ngay_sx=doc.name)
                so_cai.append({"item": item, "kg": thieu, "batch": lo,
                               "wo": wo.name, "se": se.name})
        except Exception as ex:
            _ve_savepoint(ten_sp, co)
            # Hoàn tác trong bộ nhớ: so_cai phải khớp đúng những gì CÒN trong DB.
            so_cai = [e for e in so_cai if e["item"] != item] + [
                e for e in _so_cai(doc) if e["item"] == item]
            if str(ex) != str(chan_tang):
                ten = frappe.db.get_value("Item", item, "item_name") or item
                loi.append(f"{ten}: {_chu(ex)}")

    _luu_so_cai(doc, so_cai)
    return loi


def _luu_so_cai(doc, so_cai):
    """Ghi sổ cái + danh sách chứng từ phẳng (thẻ chứng từ / truy xuất / xoá ngày đọc
    ds_wo_se_ghiso) + lô của từng dòng báo mẻ để màn hình hiện mã lô."""
    phang = []
    for e in so_cai:
        phang += [{"dt": "Work Order", "name": e.get("wo")},
                  {"dt": "Stock Entry", "name": e.get("se")}]
    doc.db_set({"so_cai_ghiso": json.dumps(so_cai), "ds_wo_se_ghiso": json.dumps(phang)},
               update_modified=False)
    lo = {e["item"]: e.get("batch") for e in so_cai}
    for r in doc.bao_me:
        if r.get("name") and lo.get(r.item_btp) != r.get("batch"):
            frappe.db.set_value("SX Bao Me", r.name, "batch", lo.get(r.item_btp),
                                update_modified=False)


# ═══════════════════════════════ VÀO HỘP ═══════════════════════════════

def dong_bo_vaohop(doc):
    """Phiếu lương + sổ nợ đơn giá + tổng của ngày khớp bảng vào hộp hiện tại."""
    from sx.api.chot import _co_gi_de_ghi, _ghi_luong_khoan, _go_luong_khoan

    bang_ten = frappe.db.get_value("SX Bang Vao Hop", {"ngay_sx": doc.name, "docstatus": ("<", 2)},
                                   "name")
    bang = frappe.get_doc("SX Bang Vao Hop", bang_ten) if bang_ten else None
    try:
        cu = json.loads(doc.get("salary_products_json") or "[]")
    except (ValueError, TypeError):
        cu = []
    co = _savepoint("sx_vh")
    try:
        moi = _ghi_luong_khoan(doc, bang) if bang and _co_gi_de_ghi(bang) else []
        con = {g["employee"] for g in moi}
        _go_luong_khoan([g for g in cu if g.get("employee") not in con])
        _dong_bo_no_gia(doc, bang)
        doc.db_set({
            "salary_products_json": json.dumps(moi) if moi else None,
            "tong_hop_tp": sum(cint(r.so_hop) for r in (bang.dong if bang else [])),
            "tong_luong_sp": sum(flt(r.thanh_tien) for r in (bang.dong if bang else [])),
        }, update_modified=False)
        return []
    except Exception as ex:
        _ve_savepoint("sx_vh", co)
        return [_chu(ex)]


def _dong_bo_no_gia(doc, bang):
    """Sổ nợ đơn giá của ngày khớp bảng hiện tại — KHÔNG huỷ-tạo lại mỗi lần lưu:
    nợ vẫn thiếu thì cập nhật số, nợ hết thiếu thì huỷ, chỗ mới thiếu thì thêm."""
    from sx.api.nogia import CHO, gom_thieu_gia
    from sx.utils import bang_don_gia, don_gia_ap_dung

    ngay = getdate(doc.ngay)
    thieu = gom_thieu_gia(bang.dong, don_gia_ap_dung(ngay)) if bang else {}
    dang = {(x.san_pham, x.cach_lam or ""): x for x in frappe.get_all(
        "SX No Don Gia", filters={"ngay_sx": doc.name, "trang_thai": CHO},
        fields=["name", "san_pham", "cach_lam", "so_hop", "so_nguoi"])}
    for k, x in dang.items():
        if k not in thieu:
            frappe.db.set_value("SX No Don Gia", x.name, "trang_thai", "Đã huỷ")
        elif (cint(x.so_hop), cint(x.so_nguoi)) != (cint(thieu[k]["so_hop"]), len(thieu[k]["nguoi"])):
            frappe.db.set_value("SX No Don Gia", x.name, {
                "so_hop": thieu[k]["so_hop"], "so_nguoi": len(thieu[k]["nguoi"])})
    for (sp, cl), g in sorted(thieu.items()):
        if (sp, cl) in dang:
            continue
        no = frappe.get_doc({
            "doctype": "SX No Don Gia", "san_pham": sp,
            "ten_san_pham": frappe.db.get_value("Item", sp, "item_name") or sp,
            "cach_lam": cl or None, "so_hop": g["so_hop"], "so_nguoi": len(g["nguoi"]),
            "trang_thai": CHO, "ngay": ngay, "ngay_sx": doc.name,
            "bang_vao_hop": bang.name, "bang_don_gia": bang_don_gia(ngay),
        })
        no.flags.ignore_permissions = True
        no.insert()


# ═══════════════════════════════ xoá ngày ═══════════════════════════════

def go_het(doc):
    """Phiếu ngày bị xoá: rút mọi chứng từ kho đã ghi + gỡ lương + huỷ nợ giá."""
    from sx.api.chot import _go_luong_khoan
    from sx.api.mfg import cancel_doc
    from sx.api.nogia import huy_no_gia

    for e in reversed(_so_cai(doc)):
        cancel_doc("Stock Entry", e.get("se"))
        cancel_doc("Work Order", e.get("wo"))
    try:
        _go_luong_khoan(json.loads(doc.get("salary_products_json") or "[]"))
    except (ValueError, TypeError):
        pass
    huy_no_gia(doc.name)


# ═══════════════════════════════ hook ═══════════════════════════════

def sau_luu_bang(doc, method=None):
    """Hook SX Bang Vao Hop (lưu / xoá): ngày đó cần đồng bộ lương."""
    danh_dau(doc.get("ngay_sx"), "vh")
