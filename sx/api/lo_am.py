"""Dọn ÂM TRONG LỊCH SỬ của lô — lô đang còn hàng mà ERPNext vẫn chặn xuất (D207).

ERPNext 16 (serial_and_batch_bundle.py get_batchwise_available_qty): mỗi lần xuất một lô nó cộng dồn MỌI dòng của lô
đó ở kho đó theo thứ tự (giờ ghi sổ, giờ tạo) — chỉ cần một điểm trong QUÁ KHỨ bị âm là chặn: "The Batch … has negative
stock in the warehouse … as of <giờ>. Please add a stock quantity of N…", dù lô hiện còn hàng (14/10/2026: TH170-TONCU
ở CH Tuệ Tĩnh còn 63 mà âm 3 lúc 12/10 14:36:08). Điểm âm như vậy do chứng từ GHI LÙI giờ (ngày kiểm kê bật lô: bán
ghi lúc 14:36 mà lô tồn cũ vào sổ muộn hơn; huỷ phiếu nhập cũ — ERPNext không kiểm khi huỷ phiếu nhập). Bật "Allow
Negative Stock for Batch" (Stock Settings) thì ERPNext bỏ qua; lệnh này dọn sạch để tắt lại được.

Mỗi (mã, kho, lô) có điểm âm, âm sâu nhất −N:
  · phiếu NHẬP (Material Receipt) N vào lô, ghi 1 giây trước điểm âm đầu tiên;
  · phiếu XUẤT (Material Issue) N khỏi lô, ghi đúng lúc dòng làm lô hết âm lần cuối (giờ tạo muộn hơn → đứng sau nó).
Từ điểm âm đầu tới lúc hết âm lô có thêm N → hết điểm âm; sau đó y như cũ → tồn hiện tại KHÔNG ĐỔI, các ngày ngoài
khoảng đó không đổi. Giá nhập = giá vốn hiện tại của mã ở kho; phiếu xuất ERPNext tự tính → chênh giá trị gần như 0.
KHÔNG dọn (chỉ báo): lô đang âm tới hiện tại (thiếu hàng thật — kiểm kê / nhập bù tay); lô có phiếu Stock
Reconciliation ghi sau điểm âm (ERPNext không cho ghi lùi trước phiếu đó — huỷ phiếu đó trước).

Chạy bằng bench, không gọi từ web — in báo cáo tiếng Việt (từng lô, phiếu đã ghi, lý do bỏ qua, bước tiếp):
  bench --site site1.local execute sx.api.lo_am.don                            # xem trước
  bench --site site1.local execute sx.api.lo_am.don --kwargs "{'chay': 1}"     # làm thật
  # chỉ một mã / kho / lô: thêm 'item': 'TH170', 'kho': 'CH Tuệ Tĩnh - HGC', 'lo': 'TH170-TONCU'
Chạy lại an toàn: dọn xong thì không còn điểm âm. Mỗi lô một điểm lưu: lô lỗi thì bỏ lô đó, báo lỗi, lô khác vẫn dọn.
Gọi từ code: xu_ly(...) — cùng tham số, trả dict.
"""

import re
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, now_datetime

GHI_CHU = "Dọn âm lịch sử lô (D207)"


def _dong(item=None, kho=None, lo=None):
    """Mọi dòng sổ kho theo lô — ĐÚNG hai nguồn ERPNext cộng khi kiểm âm lô (get_available_qty_from_sabb +
    get_available_qty_from_stock_ledger): dòng lô trong Serial and Batch Bundle của sổ kho chưa huỷ, và batch_no cũ
    trên sổ kho không có bundle."""
    dk, loc_e, loc_s = {}, "", ""
    for k, cot_e, cot_s, v in (("item", "e.item_code", "sle.item_code", item),
                               ("kho", "e.warehouse", "sle.warehouse", kho),
                               ("lo", "e.batch_no", "sle.batch_no", lo)):
        if v:
            dk[k] = v
            loc_e += f" and {cot_e} = %({k})s"
            loc_s += f" and {cot_s} = %({k})s"
    a = frappe.db.sql(f"""
        select e.item_code as item, e.warehouse as kho, e.batch_no as lo, e.qty as q, e.posting_datetime as luc,
               e.creation as tao, sle.voucher_type as loai, sle.voucher_no as phieu
          from `tabSerial and Batch Entry` e
          join `tabStock Ledger Entry` sle on sle.serial_and_batch_bundle = e.parent
         where sle.is_cancelled = 0 and e.is_cancelled = 0 and e.docstatus = 1
           and e.type_of_transaction in ('Inward', 'Outward') and e.voucher_type != 'Pick List'
           and ifnull(e.batch_no, '') != ''{loc_e}""", dk, as_dict=True)
    b = frappe.db.sql(f"""
        select sle.item_code as item, sle.warehouse as kho, sle.batch_no as lo, sle.actual_qty as q,
               sle.posting_datetime as luc, sle.creation as tao, sle.voucher_type as loai, sle.voucher_no as phieu
          from `tabStock Ledger Entry` sle
         where sle.is_cancelled = 0 and sle.docstatus = 1 and sle.serial_and_batch_bundle is null
           and ifnull(sle.batch_no, '') != ''{loc_s}""", dk, as_dict=True)
    return list(a) + list(b)


def tim_am(dong, p=3, nay=None):
    """Hàm thuần: cộng dồn từng (mã, kho, lô) theo (giờ ghi sổ, giờ tạo) như ERPNext — trả các nhóm có điểm âm:
    {item, kho, lo, am_nhat (âm sâu nhất), dau (dòng âm đầu tiên), het (dòng ngay sau lần âm cuối; None = âm tới
    dòng cuối), ton (tồn sau dòng cuối), ton_nay (tồn tới `nay` — bỏ dòng ghi ngày tương lai), so_dong}."""
    nhom = {}
    for r in dong:
        nhom.setdefault((r.get("item"), r.get("kho"), r.get("lo")), []).append(r)
    ra = []
    for (i, w, b), ds in sorted(nhom.items(), key=lambda x: tuple(str(v or "") for v in x[0])):
        ds.sort(key=lambda r: (get_datetime(r.get("luc")), get_datetime(r.get("tao") or r.get("luc"))))
        ton, thap, dau, cuoi, ton_nay = 0.0, 0.0, None, None, 0.0
        for k, r in enumerate(ds):
            ton += flt(r.get("q"))
            if nay is None or get_datetime(r.get("luc")) <= nay:
                ton_nay = ton
            if flt(ton, p) < 0:
                dau = r if dau is None else dau
                thap = min(thap, ton)
                cuoi = k
        if dau is None:
            continue
        ra.append({"item": i, "kho": w, "lo": b, "am_nhat": flt(thap, p), "dau": dau,
                   "het": ds[cuoi + 1] if cuoi + 1 < len(ds) else None, "ton": flt(ton, p),
                   "ton_nay": flt(ton_nay, p), "so_dong": len(ds)})
    return ra


def _gio_xuat(luc):
    """Giờ ghi phiếu xuất: đúng giờ dòng làm lô hết âm, làm tròn LÊN tới giây — giờ ghi sổ có phần lẻ giây (phiếu ghi
    'bây giờ'), làm tròn xuống là phiếu xuất đứng TRƯỚC dòng đó → lại âm."""
    d = get_datetime(luc)
    return d if not d.microsecond else (d + timedelta(seconds=1)).replace(microsecond=0)


def _kiem_ke_sau(item, kho, lo, luc):
    """Phiếu Stock Reconciliation có lô này ở kho này ghi SAU `luc` — ERPNext không cho ghi lùi trước nó
    (SerialandBatchBundle.check_future_entries_exists)."""
    r = frappe.db.sql("""
        select p.voucher_no from `tabSerial and Batch Bundle` p
          join `tabSerial and Batch Entry` e on e.parent = p.name
         where p.item_code = %(item)s and p.warehouse = %(kho)s and e.batch_no = %(lo)s
           and p.voucher_type = 'Stock Reconciliation' and p.docstatus = 1 and p.is_cancelled = 0
           and p.type_of_transaction in ('Inward', 'Outward') and p.posting_datetime > %(luc)s
         limit 1""", {"item": item, "kho": kho, "lo": lo, "luc": luc})
    return r[0][0] if r else None


def don(item=None, kho=None, lo=None, chay=0):
    """Lệnh bench: in báo cáo đọc được, không trả gì — giá trị trả về bench in thành JSON một dòng, chữ Việt thành
    \\uXXXX."""
    print(bao_cao(xu_ly(item, kho, lo, chay)))


def xu_ly(item=None, kho=None, lo=None, chay=0):
    """Xem trước (chay=0) / dọn (chay=1) các điểm âm trong lịch sử lô — xem đầu tệp."""
    from sx.api.kiemke import so_vn

    p = cint(frappe.get_precision("Serial and Batch Entry", "qty")) or 3
    nay = now_datetime()
    duoc, bo_qua = [], []
    for g in tim_am(_dong(item, kho, lo), p, nay):
        nhap_luc = (get_datetime(g["dau"].get("luc")) - timedelta(seconds=1)).replace(microsecond=0)
        x = {"item": g["item"], "kho": g["kho"], "lo": g["lo"], "am_nhat": g["am_nhat"],
             "am_luc": str(get_datetime(g["dau"].get("luc")))[:19],
             "am_tu": f'{g["dau"].get("loai")} {g["dau"].get("phieu")}', "ton_nay": g["ton_nay"]}
        if g["het"] is None or get_datetime(g["het"].get("luc")) > nay:
            tl = "" if g["het"] is None else _(" — chỉ hết âm nhờ {0} {1} ghi NGÀY TƯƠNG LAI {2}").format(
                g["het"].get("loai"), g["het"].get("phieu"), str(get_datetime(g["het"].get("luc")))[:19])
            bo_qua.append(dict(x, ly_do=_("lô đang âm tới hiện tại ({0}){1} — thiếu hàng thật: kiểm kê lại / nhập "
                                          "bù tay").format(so_vn(g["ton_nay"]), tl)))
            continue
        x.update(nhap=flt(-g["am_nhat"], p), nhap_luc=str(nhap_luc), xuat_luc=str(_gio_xuat(g["het"].get("luc"))),
                 het_tu=f'{g["het"].get("loai")} {g["het"].get("phieu")}')
        kk = _kiem_ke_sau(g["item"], g["kho"], g["lo"], str(nhap_luc))
        if kk:
            bo_qua.append(dict(x, ly_do=_("có phiếu Stock Reconciliation {0} ghi sau điểm âm — ERPNext không cho ghi "
                                          "lùi trước nó; huỷ phiếu đó trước").format(kk)))
            continue
        duoc.append(x)
    ma = list({x["item"] for x in duoc + bo_qua}) or [""]
    ten = {r.name: r.item_name for r in frappe.get_all("Item", filters={"name": ("in", ma)},
                                                        fields=["name", "item_name"])}
    for x in duoc + bo_qua:
        x["ten"] = ten.get(x["item"]) or x["item"]
    if cint(chay):
        lan = nay.strftime("LA-%d%m%y-%H%M%S")
        for x in duoc:
            frappe.db.savepoint("sx_lo_am")
            try:
                x["phieu_nhap"], x["phieu_xuat"] = _don_mot(x, lan, p)
            except Exception as e:  # noqa: BLE001 — báo lỗi từng lô, lô khác vẫn dọn
                frappe.db.rollback(save_point="sx_lo_am")
                x["loi"] = " ".join(re.sub(r"<[^>]+>", " ", str(e)).split())
    con = [x for x in duoc if x.get("loi")] + bo_qua
    viec = None
    if cint(chay) and con:
        viec = _("Còn {0} lô chưa dọn được (xem 'loi' / 'bo_qua') — giữ 'Allow Negative Stock for Batch' (Stock "
                 "Settings) BẬT tới khi xử lý xong, không thì các lô đó không bán được.").format(len(con))
    elif cint(chay) and (item or kho or lo):
        viec = _("Phần đã lọc hết âm — chạy lại KHÔNG lọc để chắc mọi lô đã sạch trước khi tắt 'Allow Negative "
                 "Stock for Batch'.")
    elif cint(chay):
        viec = _("Hết âm trong lịch sử lô — có thể tắt lại 'Allow Negative Stock for Batch' trong Stock Settings.")
    return {"chay": cint(chay), "so_lo": len(duoc), "lo_am": duoc, "bo_qua": bo_qua, "con_viec": viec}


def bao_cao(kq):
    """Kết quả xu_ly() → chữ in ra màn hình bench."""
    from sx.api.kiemke import so_vn

    def ve_lo(x):
        ma = x["item"] if x.get("ten") in (None, x["item"]) else f'{x["item"]} {x["ten"]}'
        return _("{0} | {1} | lô {2}: âm {3} lúc {4} ({5}), tồn nay {6}").format(
            ma, x["kho"], x["lo"], so_vn(abs(x["am_nhat"])), x["am_luc"], x["am_tu"], so_vn(x["ton_nay"]))

    ra = [_("DỌN ÂM LỊCH SỬ LÔ — LÀM THẬT") if cint(kq.get("chay")) else
          _("DỌN ÂM LỊCH SỬ LÔ — XEM TRƯỚC, chưa ghi gì (làm thật: thêm --kwargs \"{'chay': 1}\")")]
    if not kq["lo_am"] and not kq["bo_qua"]:
        ra.append(_("Không lô nào có điểm âm trong lịch sử."))
    if kq["lo_am"]:
        ra.append(_("Lô dọn được: {0}").format(len(kq["lo_am"])))
    for k, x in enumerate(kq["lo_am"], 1):
        ra.append(f"  {k}. {ve_lo(x)}")
        ra.append("     " + _("→ nhập {0} lúc {1}, xuất lại {0} lúc {2} (lô hết âm nhờ {3})").format(
            so_vn(x["nhap"]), x["nhap_luc"], x["xuat_luc"], x["het_tu"]))
        if x.get("loi"):
            ra.append("     " + _("✗ LỖI — lô này không ghi gì: {0}").format(x["loi"]))
        elif x.get("phieu_nhap"):
            ra.append("     " + _("✓ đã ghi: phiếu nhập {0}, phiếu xuất {1}").format(x["phieu_nhap"], x["phieu_xuat"]))
    if kq["bo_qua"]:
        ra.append(_("Không dọn — phải xử lý tay: {0}").format(len(kq["bo_qua"])))
    for x in kq["bo_qua"]:
        ra.append(f"  - {ve_lo(x)}")
        ra.append("    " + _("lý do: {0}").format(x["ly_do"]))
    if kq.get("con_viec"):
        ra.append(_("Bước tiếp: {0}").format(kq["con_viec"]))
    return "\n".join(ra)


def _don_mot(x, lan, p):
    """Cặp phiếu của một lô: NHẬP N trước điểm âm đầu, XUẤT N lúc lô hết âm. Lô hết hạn: tạm bỏ HSD trong lúc ghi
    (ERPNext không cho nhập vào lô hết hạn — D190), trả lại ngay sau."""
    from sx.api.kiemke import so_vn
    from sx.api.mfg import gia_von_hien, loai_phieu_kho
    from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import tam_bo_hsd, tra_hsd

    cty = frappe.db.get_value("Warehouse", x["kho"], "company")
    g = flt(gia_von_hien(x["item"], x["kho"]))
    gia = {"basic_rate": g} if g > 0 else {"allow_zero_valuation_rate": 1}
    ghi = _("{0} [{1}]: lô {2} ở {3} âm {4} lúc {5} ({6}) — nhập {7} ngay trước, xuất lại {7} lúc lô hết âm {8} ({9}); "
            "tồn hiện tại không đổi.").format(GHI_CHU, lan, x["lo"], x["kho"], so_vn(x["am_nhat"]), x["am_luc"],
                                              x["am_tu"], so_vn(x["nhap"]), x["xuat_luc"], x["het_tu"])
    ra = []
    for muc, luc, ben in (("Material Receipt", x["nhap_luc"], {"t_warehouse": x["kho"], **gia}),
                          ("Material Issue", x["xuat_luc"], {"s_warehouse": x["kho"],
                                                             **({} if g > 0 else {"allow_zero_valuation_rate": 1})})):
        d = get_datetime(luc)
        se = frappe.new_doc("Stock Entry")
        se.purpose = muc
        se.stock_entry_type = loai_phieu_kho(muc)
        se.company = cty
        se.set_posting_time = 1
        se.posting_date, se.posting_time = d.date().isoformat(), d.strftime("%H:%M:%S")
        se.remarks = ghi
        se.append("items", dict({"item_code": x["item"], "qty": flt(x["nhap"], p), "use_serial_batch_fields": 1,
                                 "batch_no": x["lo"]}, **ben))
        het = tam_bo_hsd(se.items, d.date())
        se.flags.ignore_permissions = True
        se.insert()
        se.submit()
        tra_hsd(het)
        ra.append(se.name)
    return ra
