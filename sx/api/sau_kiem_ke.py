"""Soát phiếu kiểm kê ĐÃ CHỐT: chứng từ ghi sổ TRƯỚC lúc đếm mà vào sổ SAU lúc chốt — sổ tính hai lần (D216).

Chốt kiểm kê ghi phần CHÊNH (số đếm − sổ lúc bấm chốt) bằng phiếu nhập / xuất điều chỉnh. Chứng từ ghi sổ trước lúc đếm
mà vào sổ sau lúc chốt thì số đếm đã tính hàng đó (hàng ra / vào kho trước lúc đếm) còn phần chênh không biết nó — sổ
tính thêm một lần nữa, tồn sau kiểm kê lệch đúng chừng đó. Hay gặp nhất: ĐÓNG CA POS sau lúc chốt (phiếu POS chỉ vào sổ
lúc đóng ca; hoá đơn gộp ghi sổ lúc phiếu POS cuối của ca); hoá đơn / phiếu chuyển nhập muộn ghi ngày cũ. Vd đếm TX510
còn 31, sổ lúc chốt 0 → kiểm kê nhập +31; đóng ca sau đó trừ 40 hộp bán từ sáng → tồn −9 thay vì 31. Từ D216 chốt chặn
khi còn phiếu POS chưa đóng ca lập trước lúc đếm (SXKiemKe._pos_chua_dong).

Lệnh đọc phiếu kiểm kê ĐÃ CHỐT GẦN NHẤT của kho (mặc định kho thành phẩm; hoặc phiếu chỉ định), từng mã: sổ lúc chốt,
số đếm, tồn hiện nay, các chứng từ đó (hoá đơn gộp POS: theo giờ từng phiếu POS), phần bù. chay=1 ghi phiếu bù: mỗi
chứng từ một phiếu nhập / xuất điều chỉnh ĐÚNG lô, đúng số ngược lại, ghi sổ cùng giờ với chứng từ đó (tạo sau → đứng
ngay sau nó), gắn vào phiếu kiểm kê (ds_se — huỷ chốt thì huỷ theo). Tồn sau kiểm kê lại đúng số đếm; chứng từ sau lúc
đếm (bán, nhập thật) vẫn chạy tiếp trên số đó.

  bench --site site1.local execute sx.api.sau_kiem_ke.soat                               # xem trước, mọi mã
  bench --site site1.local execute sx.api.sau_kiem_ke.soat --kwargs "{'ma': 'TX510'}"    # một mã
  bench --site site1.local execute sx.api.sau_kiem_ke.soat --kwargs "{'chay': 1}"        # ghi phiếu bù
  # phiếu / kho khác: 'phieu': 'KK-…' hoặc 'kho': '…'. Chứng từ mà hàng THẬT ra / vào kho SAU lúc đếm (chỉ ghi nhầm
  # ngày cũ) thì không bù: 'bo': ['ACC-SINV-…']

Không bù, chỉ báo: phần KHÔNG LÔ của mã đã bật lô (thẻ Kiểm kê → Tồn không lô còn lại → DỌN, D198); phiếu Stock
Reconciliation (đặt lại tồn — không có số chênh để bù). Chạy lại an toàn: chứng từ đã bù không bù lần hai; chứng từ đã
bù mà sau đó bị huỷ thì phiếu bù của nó bị huỷ theo (chay=1). Mỗi chứng từ một điểm lưu: lỗi thì bỏ chứng từ đó, báo
lỗi, chứng từ khác vẫn bù. Gọi từ code: xu_ly(...) — cùng tham số, trả dict.
"""

import json
import re

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime

PT = "SX Kiem Ke"
NHAN = "Bù chứng từ ghi lùi sau kiểm kê (D216)"
EPS = 1e-6


def _gio(x):
    return get_datetime(x).strftime("%d/%m %H:%M") if x else "?"


def _phieu(phieu=None, kho=None):
    """Phiếu cần soát — chỉ định, hoặc phiếu đã chốt gần nhất của kho (mặc định kho thành phẩm). Phải là phiếu chốt GẦN
    NHẤT của kho: chứng từ vào sổ trước lúc chốt phiếu sau đã nằm trong số sổ của phiếu sau (phần chênh đã tính)."""
    from sx.utils import get_settings

    if phieu:
        if not frappe.db.exists(PT, phieu):
            frappe.throw(_("Không có phiếu kiểm kê {0}.").format(phieu))
        d = frappe.get_doc(PT, phieu)
        if cint(d.docstatus) != 1:
            frappe.throw(_("Phiếu kiểm kê {0} chưa chốt hoặc đã huỷ — chỉ soát phiếu đã chốt.").format(phieu))
    else:
        kho = kho or get_settings().get("kho_tp")
        ten = frappe.get_all(PT, filters={"docstatus": 1, "kho": kho}, fields=["name"], order_by="chot_luc desc",
                             limit=1)
        if not ten:
            frappe.throw(_("Kho {0} chưa có phiếu kiểm kê nào đã chốt.").format(kho))
        d = frappe.get_doc(PT, ten[0].name)
    sau = frappe.get_all(PT, filters={"docstatus": 1, "kho": d.kho, "chot_luc": (">", d.chot_luc),
                                      "name": ("!=", d.name)}, pluck="name")
    if sau:
        frappe.throw(_("Kho {0} đã có phiếu kiểm kê chốt sau {1}: {2} — soát phiếu mới nhất.").format(
            d.kho, d.name, ", ".join(sau)))
    return d


def _dong_muon(kho, items, chot):
    """Dòng sổ cái kho (mỗi lô một dòng — bundle tách theo lô) của các mã ở kho mà ĐỔI SỔ sau lúc chốt: tạo sau `chot`
    (chưa huỷ), hoặc có từ trước mà bị huỷ sau `chot`. Tạo rồi huỷ đều sau lúc chốt thì sổ không đổi — không lấy."""
    if not items:
        return []
    return [frappe._dict(r, b=r.get("b") or None) for r in frappe.db.sql(
        """select sle.name, sle.item_code as item, sle.voucher_type as vt, sle.voucher_no as vn,
                  sle.voucher_detail_no as vd, coalesce(e.batch_no, sle.batch_no) as b,
                  coalesce(e.qty, sle.actual_qty) as q, sle.posting_datetime as luc, sle.creation as tao,
                  sle.modified as sua, sle.is_cancelled as huy, coalesce(e.incoming_rate, sle.valuation_rate) as gia
             from `tabStock Ledger Entry` sle
             left join `tabSerial and Batch Entry` e on e.parent = sle.serial_and_batch_bundle
            where sle.warehouse = %(kho)s and sle.item_code in %(items)s
              and ((sle.is_cancelled = 0 and sle.creation > %(chot)s)
                   or (sle.is_cancelled = 1 and sle.creation <= %(chot)s and sle.modified > %(chot)s))
            order by sle.posting_datetime, sle.creation, sle.name""",
        {"kho": kho, "items": tuple(items), "chot": chot}, as_dict=True)]


def phan_tich(moc, dong, pos, lo_rieng=False, cua_kk=(), bo=(), da_bu=()):
    """Chứng từ ghi lùi — hàm thuần. `dong` = _dong_muon; giờ THẬT của dòng = giờ phiếu POS gốc nếu là dòng hoá đơn gộp
    (`pos` {dòng hoá đơn: giờ} — sx_kiem_ke.gio_pos), không thì giờ ghi sổ. Lấy dòng có giờ thật KHÔNG muộn hơn mốc đếm
    của khoá đó (`moc` — SXKiemKe.moc_dem; khoá = mã, bán thành phẩm (mã, lô)). Bỏ phiếu kho của chính kiểm kê (`cua_kk`,
    cả phiếu bù). Số đổi sổ: dòng mới = số của nó, dòng bị huỷ = ngược lại.
    Trả [{vt, vn, luc, vao, tu, den, huy, dong {(mã, lô): số đổi sổ}, gia {(mã, lô): giá}, bo, da_bu, dat_lai}] theo giờ
    ghi sổ — `luc` giờ ghi sổ của chứng từ, `vao` lúc nó vào / ra khỏi sổ, `tu`/`den` giờ thật sớm / muộn nhất."""
    ra = {}
    for r in dong:
        if r.vt == "Stock Entry" and r.vn in cua_kk:
            continue
        k = (r.item, r.b or None) if lo_rieng else r.item
        t = moc.get(k)
        if t is None:
            continue
        that = pos.get(r.vd) or get_datetime(r.luc)
        if that > t:
            continue                       # ra / vào kho SAU lúc đếm: thật, số đếm không có — không bù
        huy = cint(r.huy)
        g = ra.get((r.vt, r.vn))
        if g is None:
            g = ra[(r.vt, r.vn)] = {
                "vt": r.vt, "vn": r.vn, "luc": get_datetime(r.luc), "vao": get_datetime(r.sua if huy else r.tao),
                "tu": that, "den": that, "huy": huy, "dong": {}, "gia": {}, "bo": r.vn in bo,
                "da_bu": (r.vt, r.vn) in da_bu, "dat_lai": r.vt == "Stock Reconciliation"}
        g["tu"], g["den"] = min(g["tu"], that), max(g["den"], that)
        x = (r.item, r.b or None)
        g["dong"][x] = g["dong"].get(x, 0.0) + (-flt(r.q) if huy else flt(r.q))
        if flt(r.gia) and x not in g["gia"]:
            g["gia"][x] = abs(flt(r.gia))
    for g in ra.values():
        g["dong"] = {x: flt(v, 6) for x, v in g["dong"].items() if abs(v) > EPS or g["dat_lai"]}
    return [g for g in sorted(ra.values(), key=lambda g: (g["luc"], g["vn"])) if g["dong"]]


def chia_bu(ct, co_lo):
    """Phần bù của từng chứng từ — hàm thuần. g["bu"] {(mã, lô): số bù = ngược số đổi sổ}; g["khong"] {(mã, lô): lý do
    không bù}: dat_lai (Stock Reconciliation), khong_lo (phần không lô của mã đang quản lý lô — DỌN, D198), bo (chỉ định
    bỏ), da_bu (đã bù lần trước). `co_lo` = các mã đang quản lý lô."""
    for g in ct:
        g["bu"], g["khong"] = {}, {}
        for (i, b), v in g["dong"].items():
            ly = ("dat_lai" if g["dat_lai"] else "da_bu" if g["da_bu"] else "bo" if g["bo"]
                  else "khong_lo" if not b and i in co_lo else None)
            if ly:
                g["khong"][(i, b)] = ly
            elif abs(v) > EPS:
                g["bu"][(i, b)] = flt(-v, 6)
    return ct


def _ds_bu(ds_se):
    """{(vt, vn): {"se": [phiếu bù], "huy": chứng từ đó lúc bù là phiếu bị huỷ}} — phiếu bù đã ghi (ds_se của kiểm kê)."""
    ra = {}
    for x in ds_se:
        if x.get("dt") == "Stock Entry" and x.get("bu"):
            vt, vn, huy = (list(x["bu"]) + [0])[:3]
            g = ra.setdefault((vt, vn), {"se": [], "huy": cint(huy)})
            g["se"].append(x["name"])
    return ra


def xu_ly(phieu=None, kho=None, ma=None, chay=0, bo=None):
    """Soát (chay=0) / ghi phiếu bù (chay=1) cho phiếu kiểm kê đã chốt — xem đầu tệp."""
    from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import _so_lo, gio_pos

    d = _phieu(phieu, kho)
    lo_rieng = d.la_btp()
    chot = get_datetime(d.chot_luc)
    ds_se = json.loads(d.ds_se or "[]")
    cua_kk = {x.get("name") for x in ds_se if x.get("dt") == "Stock Entry"}
    da_bu = _ds_bu(ds_se)
    if isinstance(bo, str):
        bo = [bo]
    bo = {str(x).strip() for x in bo or [] if str(x).strip()}

    kq = {}                                   # khoá → kết quả kiểm kê (sổ lúc chốt, số đếm)
    for r in d.lo or []:
        k = (r.item, r.batch or None) if lo_rieng else r.item
        x = kq.setdefault(k, {"item": r.item, "lo": (r.batch or None) if lo_rieng else None, "ten": r.ten or r.item,
                              "so": 0.0, "dem": 0.0})
        x["so"] += flt(r.so_truoc)
        x["dem"] += flt(r.so_sau)
    items = sorted({x["item"] for x in kq.values()})
    ten = {i.name: i.item_name or i.name for i in frappe.get_all("Item", filters={"name": ("in", items or [""])},
                                                                    fields=["name", "item_name"])}
    ra = {"chay": cint(chay), "phieu": d.name, "kho": d.kho, "chot": str(chot)[:16], "lo_rieng": lo_rieng,
          "thoi_diem": str(d.get("thoi_diem") or "")[:16], "khong_thay": None, "ma": [], "huy_bu": []}
    if ma:
        m = str(ma).strip().lower()
        chon = [i for i in items if i.lower() == m] or [
            i for i in items if m in i.lower() or m in str(ten.get(i, "")).lower()]
        if not chon:
            ra["khong_thay"] = str(ma)
            return ra
        kq = {k: v for k, v in kq.items() if v["item"] in chon}
        items = chon
    moc = d.moc_dem(list(kq))
    dong = _dong_muon(d.kho, items, chot)
    co_lo = {i.name for i in frappe.get_all("Item", filters={"name": ("in", items or [""]), "has_batch_no": 1},
                                            fields=["name"])}
    ct = chia_bu(phan_tich(moc, dong, gio_pos([r.vd for r in dong if r.vt == "Sales Invoice"]), lo_rieng, cua_kk, bo,
                           set(da_bu)), co_lo)

    # Phiếu bù thừa: chứng từ đã bù (không phải phiếu huỷ) mà nay đã huỷ — sổ không còn số đó, phiếu bù phải huỷ theo.
    for (vt, vn), x in sorted(da_bu.items()):
        if not x["huy"] and cint(frappe.db.get_value(vt, vn, "docstatus")) == 2:
            con = [n for n in x["se"] if cint(frappe.db.get_value("Stock Entry", n, "docstatus")) == 1]
            if con:
                ra["huy_bu"].append({"vt": vt, "vn": vn, "se": con, "loi": None})

    ton = {}
    for r in _so_lo(d.kho, items):
        k = (r.item, r.b or None) if lo_rieng else r.item
        if k in kq:
            x = ton.setdefault(k, {"q": 0.0, "kl": 0.0})
            x["q"] += flt(r.q)
            if not r.b:
                x["kl"] += flt(r.q)
    am_khac = {}
    if not lo_rieng:
        for b in frappe.get_all("Bin", filters={"item_code": ("in", items or [""]), "warehouse": ("!=", d.kho)},
                                fields=["item_code", "warehouse", "actual_qty"]):
            if flt(b.actual_qty) < -EPS:
                am_khac.setdefault(b.item_code, []).append((b.warehouse, flt(b.actual_qty, 6)))

    for k, x in kq.items():
        cua = [g for g in ct if any(((i, b) if lo_rieng else i) == k for i, b in g["dong"])]
        lech = flt(sum(v for g in cua for (i, b), v in g["dong"].items() if ((i, b) if lo_rieng else i) == k), 6)
        bu = flt(sum(v for g in cua for (i, b), v in g["bu"].items() if ((i, b) if lo_rieng else i) == k), 6)
        da = flt(sum(-v for g in cua if g["da_bu"] for (i, b), v in g["dong"].items()
                     if ((i, b) if lo_rieng else i) == k), 6)
        nay = flt(ton.get(k, {}).get("q"), 6)
        x.update({"khoa": k, "ten": ten.get(x["item"], x["ten"]), "moc": str(moc.get(k) or "")[:16], "ct": cua,
                  "co_lo": x["item"] in co_lo, "lech": lech, "bu": bu, "da_bu": da, "nay": nay,
                  "khong_lo": flt(ton.get(k, {}).get("kl"), 6), "sau_dem": flt(nay - x["dem"] - lech - da, 6),
                  "sau_bu": flt(nay + bu, 6), "am_khac": am_khac.get(x["item"], [])})
        if cua or nay < -EPS or ma:
            ra["ma"].append(x)
    ra["ma"].sort(key=lambda x: (not x["ct"], x["ten"], str(x["lo"] or "")))

    if cint(chay):
        for h in ra["huy_bu"]:
            frappe.db.savepoint("sx_sau_kk")
            try:
                for se in h["se"]:
                    s = frappe.get_doc("Stock Entry", se)
                    if cint(s.docstatus) == 1:
                        s.flags.ignore_permissions = True
                        s.cancel()
            except Exception as e:  # noqa: BLE001 — báo lỗi từng chứng từ, chứng từ khác vẫn làm
                frappe.db.rollback(save_point="sx_sau_kk")
                h["loi"] = " ".join(re.sub(r"<[^>]+>", " ", str(e)).split())
        moi = []
        for g in ct:
            if not g["bu"]:
                continue
            frappe.db.savepoint("sx_sau_kk")
            try:
                g["phieu"] = _ghi_bu(d, g)
                moi += [{"dt": "Stock Entry", "name": n, "bu": [g["vt"], g["vn"], g["huy"]]} for n in g["phieu"]]
            except Exception as e:  # noqa: BLE001
                frappe.db.rollback(save_point="sx_sau_kk")
                g["loi"] = " ".join(re.sub(r"<[^>]+>", " ", str(e)).split())
        if moi:
            d.db_set("ds_se", json.dumps(ds_se + moi), update_modified=False)
    return ra


def _ghi_bu(d, g):
    """Phiếu bù của MỘT chứng từ: phần bù dương → Material Receipt, âm → Material Issue, đúng lô, ghi sổ cùng giờ với
    chứng từ (tạo sau → đứng ngay sau nó). Giá nhập = giá của dòng chứng từ (giá lô lúc nó ra kho), không có thì giá vốn
    đang chạy. Lô hết hạn: tạm bỏ HSD trong lúc ghi (ERPNext không cho nhập vào lô hết hạn — D190)."""
    from sx.api.kiemke import so_vn
    from sx.api.mfg import gia_von_hien, loai_phieu_kho
    from sx.sx.doctype.sx_kiem_ke.sx_kiem_ke import tam_bo_hsd, tra_hsd

    cty = frappe.db.get_value("Warehouse", d.kho, "company")
    luc = g["luc"]
    nguon = (_("phiếu POS {0}→{1}").format(_gio(g["tu"]), _gio(g["den"])) if g["tu"] != g["luc"]
             else _("ghi sổ {0}").format(_gio(g["luc"])))
    ra = []
    for muc, phan in (("Material Receipt", {x: v for x, v in g["bu"].items() if v > EPS}),
                      ("Material Issue", {x: -v for x, v in g["bu"].items() if v < -EPS})):
        if not phan:
            continue
        se = frappe.new_doc("Stock Entry")
        se.purpose = muc
        se.stock_entry_type = loai_phieu_kho(muc)
        se.company = cty
        se.custom_kiem_ke = d.name
        se.set_posting_time = 1
        se.posting_date, se.posting_time = luc.date().isoformat(), luc.strftime("%H:%M:%S")
        dong_bu = sorted(phan.items(), key=lambda x: (x[0][0], x[0][1] or ""))
        se.remarks = _("{0} — kiểm kê {1} (chốt {2}): {3} {4}{5} ({6}, trước lúc đếm) vào sổ {7}, sau lúc chốt — số đếm "
                       "đã tính phần này, sổ tính thêm lần nữa → {8} {9}.").format(
            NHAN, d.name, _gio(d.chot_luc), g["vt"], g["vn"], _(" (phiếu huỷ)") if g["huy"] else "", nguon,
            _gio(g["vao"]), _("nhập bù") if muc == "Material Receipt" else _("xuất bù"),
            ", ".join(f"{i}{' lô ' + b if b else ''} {so_vn(q)}" for (i, b), q in dong_bu))
        for (i, b), q in dong_bu:
            dong = {"item_code": i, "qty": flt(q, 6), **({"use_serial_batch_fields": 1, "batch_no": b} if b else {})}
            if muc == "Material Receipt":
                gia = flt(g["gia"].get((i, b))) or flt(gia_von_hien(i, d.kho))
                dong.update({"t_warehouse": d.kho, **({"basic_rate": gia} if gia > 0 else
                                                      {"allow_zero_valuation_rate": 1})})
            else:
                dong.update({"s_warehouse": d.kho, **({} if flt(gia_von_hien(i, d.kho)) > 0 else
                                                      {"allow_zero_valuation_rate": 1})})
            se.append("items", dong)
        het = tam_bo_hsd(se.items, luc.date()) if muc == "Material Receipt" else {}
        se.flags.ignore_permissions = True
        try:
            se.insert()
            se.submit()
        finally:
            tra_hsd(het)
        ra.append(se.name)
    return ra


LY_DO = {"dat_lai": "Stock Reconciliation đặt lại tồn — không có số chênh để bù, xem tay",
         "khong_lo": "phần KHÔNG LÔ của mã đã bật lô — không bù ở đây: thẻ Kiểm kê → Tồn không lô còn lại → DỌN",
         "bo": "bỏ theo yêu cầu (hàng thật ra / vào sau lúc đếm)",
         "da_bu": "đã bù lần trước"}


def bao_cao(kq):
    """Kết quả xu_ly() → chữ in ra màn hình bench."""
    from sx.api.kiemke import so_vn

    def so(x):
        return ("+" if x > EPS else "") + so_vn(x)

    chay = cint(kq.get("chay"))
    ra = [_("SOÁT KIỂM KÊ SAU CHỐT — GHI PHIẾU BÙ") if chay else
          _("SOÁT KIỂM KÊ SAU CHỐT — XEM TRƯỚC, chưa ghi gì (ghi phiếu bù: thêm --kwargs \"{'chay': 1}\")")]
    ra.append(_("Phiếu {0} · {1} · chốt {2}{3}").format(
        kq["phieu"], kq["kho"], kq["chot"], _(" · thời điểm chốt sổ {0}").format(kq["thoi_diem"])
        if kq.get("thoi_diem") else ""))
    if kq.get("khong_thay"):
        ra.append(_("Không thấy mã '{0}' trong phiếu kiểm kê này.").format(kq["khong_thay"]))
        return "\n".join(ra)
    co = [x for x in kq["ma"] if x["ct"]]
    am = [x for x in kq["ma"] if x["nay"] < -EPS]
    tong_bu = sum(len([1 for g in x["ct"] if g["bu"]]) for x in co)
    ra.append(_("Mã có chứng từ ghi lùi (ghi sổ trước lúc đếm, vào sổ sau lúc chốt): {0} · mã đang âm ở kho này: {1}")
              .format(len(co), len(am)))
    if not kq["ma"]:
        ra.append(_("Không mã nào có chứng từ ghi lùi, không mã nào âm — tồn sau kiểm kê đúng số đếm."))
    da_in = set()
    for n, x in enumerate(kq["ma"], 1):
        ma = x["item"] if x["ten"] in (None, x["item"]) else f'{x["item"]} {x["ten"]}'
        ra.append("")
        ra.append(f"{n}. {ma}" + (_(" · lô {0}").format(x["lo"]) if x.get("lo") else ""))
        ra.append("   " + _("Kiểm kê: sổ {0} → đếm {1} (ghi {2}), đếm lúc {3}. Tồn hiện nay: {4}{5}.").format(
            so_vn(x["so"]), so_vn(x["dem"]), so(x["dem"] - x["so"]), _gio(x["moc"]) if x["moc"] else "?",
            so_vn(x["nay"]), _(" (không lô {0})").format(so_vn(x["khong_lo"]))
            if x.get("co_lo") and abs(x["khong_lo"]) > EPS else ""))
        if x["ct"]:
            ra.append("   " + _("Ghi sổ trước lúc đếm mà vào sổ sau lúc chốt — số đếm đã tính, sổ tính thêm:"))
        for g in x["ct"]:
            phan = {k: v for k, v in g["dong"].items() if (k if kq.get("lo_rieng") else k[0]) == x["khoa"]}
            nguon = (_("đóng ca POS — phiếu POS {0}→{1}").format(_gio(g["tu"]), _gio(g["den"]))
                     if g["tu"] != g["luc"] else _("ghi sổ {0}").format(_gio(g["luc"])))
            ra.append("     " + _("{0} {1}{2} ({3}, vào sổ {4}): {5}").format(
                g["vt"], g["vn"], _(" — phiếu bị HUỶ") if g["huy"] else "", nguon, _gio(g["vao"]),
                ", ".join(f"{so(v)}{' lô ' + b if b else _(' không lô')}" for (i, b), v in sorted(
                    phan.items(), key=lambda t: t[0][1] or ""))))
            for k, ly in sorted(g["khong"].items(), key=lambda t: t[0][1] or ""):
                if k in phan:
                    ra.append("       " + _("không bù: {0}").format(_(LY_DO[ly])))
            if g.get("loi") and g["vn"] not in da_in:
                ra.append("       " + _("✗ LỖI — chứng từ này không bù được: {0}").format(g["loi"]))
            elif g.get("phieu") and g["vn"] not in da_in:
                ra.append("       " + _("✓ đã ghi phiếu bù {0}").format(", ".join(g["phieu"])))
            da_in.add(g["vn"])
        if abs(x["bu"]) > EPS:
            ra.append("   " + _("→ bù {0}: tồn {1} → {2}").format(so(x["bu"]), so_vn(x["nay"]), so_vn(x["sau_bu"])))
        if abs(x["sau_dem"]) > EPS:
            ra.append("   " + _("Chứng từ sau lúc đếm (bán / nhập thật): {0}.").format(so(x["sau_dem"])))
        if x["nay"] + x["bu"] < -EPS:
            ra.append("   " + _("Vẫn âm sau khi bù: chứng từ sau lúc đếm ra nhiều hơn số đếm cộng hàng nhập — hàng bán mà "
                                "chưa nhập kho (phiếu nhập kho còn chờ duyệt, vào hộp chưa nhập kho), hoặc đếm thiếu."))
        if x["am_khac"]:
            ra.append("   " + _("Kho khác đang âm: {0}.").format(", ".join(f"{w} {so_vn(q)}" for w, q in x["am_khac"])))
    for h in kq.get("huy_bu") or []:
        ra.append("")
        ra.append(_("Phiếu bù thừa — {0} {1} đã bị huỷ sau khi bù: {2}").format(h["vt"], h["vn"], ", ".join(h["se"]))
                  + (_(" → ✗ LỖI không huỷ được: {0}").format(h["loi"]) if h.get("loi")
                     else _(" → đã huỷ") if chay else _(" → chay=1 sẽ huỷ")))
    ra.append("")
    if not chay and (tong_bu or kq.get("huy_bu")):
        ra.append(_("Bước tiếp: chạy lại với --kwargs \"{'chay': 1}\" (thêm 'ma' nếu chỉ một mã) để ghi phiếu bù. Chứng "
                    "từ nào hàng THẬT ra / vào kho sau lúc đếm (chỉ ghi nhầm ngày cũ) thì thêm 'bo': ['số chứng từ']."))
    elif chay:
        loi = [g for x in co for g in x["ct"] if g.get("loi")] + [h for h in kq.get("huy_bu") or [] if h.get("loi")]
        ghi = {g["vn"] for x in co for g in x["ct"] if g.get("phieu")} | {h["vn"] for h in kq.get("huy_bu") or []
                                                                           if not h.get("loi")}
        ra.append(_("Xong — {0} chứng từ lỗi, xem dòng ✗.").format(len({g["vn"] for g in loi})) if loi
                  else _("Xong — tồn sau kiểm kê đã về đúng số đếm cho các chứng từ trên.") if ghi
                  else _("Không có gì để ghi."))
    return "\n".join(ra)


def soat(phieu=None, kho=None, ma=None, chay=0, bo=None):
    """Lệnh bench: in báo cáo đọc được, không trả gì — giá trị trả về bench in thành JSON một dòng, chữ Việt thành
    \\uXXXX."""
    print(bao_cao(xu_ly(phieu=phieu, kho=kho, ma=ma, chay=chay, bo=bo)))
