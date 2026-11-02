"""Bảng giá vào hộp: mọi thành phẩm hai cách làm Tay / Máy, giá tạm 1 đồng (D224).

Chạy trên site — gọi trần = XEM TRƯỚC, như cả module sx.seed:

    bench --site site1.local execute sx.seed.don_gia.tay_may                                     # xem trước
    bench --site site1.local execute sx.seed.don_gia.tay_may --kwargs "{'dry_run': 0}"           # ghi, từ hôm nay
    bench --site site1.local execute sx.seed.don_gia.tay_may --kwargs "{'dry_run': 0, 'tu_ngay': '2026-11-03'}"

- Cách làm Tay, Máy (SX Cach Lam): chưa có thì tạo, đang tắt thì bật lại.
- Bảng giá hiệu lực từ `tu_ngay` (mặc định hôm nay): đã có bảng đúng ngày đó thì sửa bảng đó; chưa có thì lập bảng mới
  chép đủ dòng của bảng đang áp dụng ngày đó (tra giá chỉ đọc MỘT bảng nên bảng mới phải đủ). Bảng cũ giữ nguyên —
  ngày trước đó vẫn tính giá cũ.
- Mỗi thành phẩm (items_tp) hai dòng Tay, Máy, xếp theo tên hàng: dòng đã có giữ nguyên giá; dòng thiếu thêm giá tạm 1
  đồng (sx.utils.GIA_TAM — coi như chưa có giá: ghi hộp vào sổ nợ đơn giá, nhập giá thật rồi Áp giá). Giá chung và
  cách làm khác của thành phẩm bỏ khỏi bảng này — QC ghi hộp phải chọn Tay hoặc Máy; báo cáo in lại giá cũ để đối
  chiếu khi nhập giá thật. Dòng của mã không phải thành phẩm giữ nguyên.
- DỪNG, không ghi gì: bảng vào hộp CHƯA CHỐT hoặc sổ nợ đơn giá đang chờ giá, từ `tu_ngay` trở đi, có dòng thành phẩm
  không cách làm / cách làm khác — đổi bảng là các dòng đó không còn giá nào để tra (lưu lại thành 0 đồng, áp giá
  không được). Chọn `tu_ngay` sau ngày đó, hoặc sửa các dòng sang Tay / Máy trước.
- Chạy lại an toàn: bảng đã đủ thì không ghi gì.

In báo cáo tiếng Việt (bench in giá trị trả về thành \\uXXXX). Gọi từ code: `xu_ly` (cùng tham số, trả dict).
"""

import frappe
from frappe.utils import add_days, cint, flt, getdate, nowdate

from sx.seed import _dry
from sx.utils import GIA_TAM, bang_don_gia, items_tp

CACH = (("Tay", "Làm tay"), ("Máy", "Làm bằng máy"))


def tay_may(dry_run=None, tu_ngay=None):
    """Lệnh bench (xem đầu module): in báo cáo."""
    print(bao_cao(xu_ly(dry_run=dry_run, tu_ngay=tu_ngay)))


def xu_ly(dry_run=None, tu_ngay=None):
    dry_run = _dry(dry_run)
    ngay = getdate(tu_ngay or nowdate())
    cach = []
    for ten, mo_ta in CACH:
        co = frappe.db.get_value("SX Cach Lam", ten, ["name", "disabled"], as_dict=True)
        # MariaDB so tên không phân biệt hoa thường: site đã có "máy" thì dùng đúng tên đó
        cach.append({"ten": co.name if co else ten, "mo_ta": mo_ta, "moi": not co, "tat": bool(co and cint(co.disabled))})
    ten_cach = [c["ten"] for c in cach]
    tp = {i.name: i.item_name or i.name for i in items_tp(["name", "item_name"])}

    bang = frappe.db.get_value("SX Bang Don Gia", {"hieu_luc_tu": ngay, "docstatus": ("<", 2)}, "name")
    goc = bang or bang_don_gia(ngay)
    cu = list(frappe.get_doc("SX Bang Don Gia", goc).dong) if goc else []
    ngoai, co_tp, bo = [], {}, []
    for r in cu:
        d = {"san_pham": r.san_pham, "ten_san_pham": r.ten_san_pham or tp.get(r.san_pham), "cach_lam": r.cach_lam or None,
             "don_gia": flt(r.don_gia), "ghi_chu": r.ghi_chu}
        if r.san_pham not in tp:
            ngoai.append(d)
        elif (r.cach_lam or "") in ten_cach:
            co_tp[(r.san_pham, r.cach_lam)] = d
        else:
            bo.append({"san_pham": r.san_pham, "ten": tp[r.san_pham], "cach_lam": r.cach_lam or "", "don_gia": d["don_gia"]})
    moi, them = list(ngoai), []
    for sp, ten in tp.items():
        for cl in ten_cach:
            d = co_tp.get((sp, cl))
            if d is None:
                d = {"san_pham": sp, "ten_san_pham": ten, "cach_lam": cl, "don_gia": GIA_TAM, "ghi_chu": None}
                them.append(d)
            moi.append(d)

    # Bảng nguồn đã đủ (mọi thành phẩm có Tay / Máy, không gì phải bỏ) thì không lập bảng trùng y hệt
    doi_bang = [(d["san_pham"], d["cach_lam"] or "", flt(d["don_gia"])) for d in moi] != [
        (r.san_pham, r.cach_lam or "", flt(r.don_gia)) for r in cu]
    doi = doi_bang or any(c["moi"] or c["tat"] for c in cach)
    chan = _se_mat_gia(ngay, tp, ten_cach) if doi_bang else []
    kq = {"dry_run": dry_run, "ngay": ngay, "cach": cach, "bang": bang, "goc": goc, "so_chep": len(cu), "tp": len(tp),
          "them": them, "giu": [d for d in co_tp.values() if flt(d["don_gia"]) > GIA_TAM], "bo": bo,
          "ngoai": len(ngoai), "chan": chan, "doi": doi, "doi_bang": doi_bang, "da_ghi": None}
    if dry_run or chan or not doi:
        return kq

    for c in cach:
        if c["moi"]:
            frappe.get_doc({"doctype": "SX Cach Lam", "mo_ta": c["mo_ta"]}).insert(
                set_name=c["ten"], ignore_permissions=True)
        elif c["tat"]:
            frappe.db.set_value("SX Cach Lam", c["ten"], "disabled", 0)
    if not doi_bang:
        return kq
    doc = frappe.get_doc("SX Bang Don Gia", bang) if bang else frappe.new_doc("SX Bang Don Gia")
    if not bang:
        doc.hieu_luc_tu = ngay
        doc.ghi_chu = ("D224: mỗi thành phẩm hai cách làm Tay / Máy. Giá 1 đồng = giá tạm (chưa có giá) — sửa thành giá "
                       "thật." + (f" Chép từ {goc}." if goc else ""))
    doc.set("dong", [])
    for d in moi:
        doc.append("dong", d)
    doc.flags.ignore_permissions = True
    doc.save()
    kq["da_ghi"] = doc.name
    return kq


def _se_mat_gia(ngay, tp, ten_cach):
    """Dòng sẽ không còn giá để tra sau khi đổi bảng: thành phẩm, không cách làm / cách làm khác Tay, Máy — ở bảng vào hộp
    CHƯA CHỐT (lưu lại là tính lại theo bảng mới) và sổ nợ đơn giá đang chờ giá (áp giá tra bảng mới), từ `ngay`."""
    ra = []
    ngay_sx = {x.name: getdate(x.ngay) for x in frappe.get_all(
        "SX Ngay San Xuat", filters={"ngay": (">=", ngay)}, fields=["name", "ngay"])}
    bvh = {b.name: ngay_sx[b.ngay_sx] for b in frappe.get_all(
        "SX Bang Vao Hop", filters={"ngay_sx": ("in", list(ngay_sx)), "docstatus": 0},
        fields=["name", "ngay_sx"])} if ngay_sx else {}
    if bvh:
        for r in frappe.get_all("SX Bang Vao Hop Item", filters={"parent": ("in", list(bvh)),
                                                                 "parenttype": "SX Bang Vao Hop"},
                                fields=["parent", "idx", "san_pham", "cach_lam", "cong_nhat"]):
            if r.san_pham in tp and not cint(r.cong_nhat) and (r.cach_lam or "") not in ten_cach:
                ra.append({"ngay": bvh[r.parent], "noi": f"bảng vào hộp {r.parent} dòng {r.idx}",
                           "ten": tp[r.san_pham], "cach_lam": r.cach_lam or ""})
    for n in frappe.get_all("SX No Don Gia", filters={"trang_thai": "Chờ giá", "ngay": (">=", ngay)},
                            fields=["name", "ngay", "san_pham", "cach_lam"]):
        if n.san_pham in tp and (n.cach_lam or "") not in ten_cach:
            ra.append({"ngay": getdate(n.ngay), "noi": f"sổ nợ đơn giá {n.name}", "ten": tp[n.san_pham],
                       "cach_lam": n.cach_lam or ""})
    return sorted(ra, key=lambda x: (x["ngay"], x["noi"]))


def _so(x):
    return f"{flt(x):,.0f}".replace(",", ".")


def _cach(cl):
    return cl or "giá chung"


def bao_cao(kq):
    d = kq["ngay"].strftime("%d/%m/%Y")
    ra = ["═══ Bảng giá vào hộp — mọi thành phẩm hai cách làm Tay / Máy (D224)"
          + (" — XEM TRƯỚC, chưa ghi gì" if kq["dry_run"] else "") + " ═══",
          "Cách làm: " + " · ".join(f"{c['ten']} ({'tạo mới' if c['moi'] else 'bật lại' if c['tat'] else 'đã có'})"
                                    for c in kq["cach"])]
    if not kq["doi_bang"]:
        ra.append(f"Bảng giá: {kq['goc']} đã đủ Tay / Máy cho mọi thành phẩm — giữ nguyên.")
    elif kq["bang"]:
        ra.append(f"Bảng giá: sửa {kq['bang']} (đã có bảng hiệu lực đúng từ {d}).")
    elif kq["goc"]:
        ra.append(f"Bảng giá: lập bảng mới hiệu lực từ {d}, chép {kq['so_chep']} dòng từ {kq['goc']} — bảng đó giữ "
                  f"nguyên, ngày trước {d} vẫn tính giá cũ.")
    else:
        ra.append(f"Bảng giá: chưa có bảng nào — lập bảng đầu tiên, hiệu lực từ {d}.")
    ra.append(f"Thành phẩm: {kq['tp']} mã.")
    ra.append(f"  + thêm {len(kq['them'])} dòng giá tạm {GIA_TAM} đồng (Tay / Máy).")
    if kq["giu"]:
        ra.append(f"  = giữ giá đã có — {len(kq['giu'])} dòng:")
        ra += [f"      • {x['ten_san_pham'] or x['san_pham']} — {x['cach_lam']} {_so(x['don_gia'])}" for x in kq["giu"]]
    if kq["bo"]:
        ra.append(f"  − bỏ {len(kq['bo'])} dòng giá chung / cách làm khác (giá cũ — để đối chiếu khi nhập giá thật):")
        ra += [f"      • {x['ten']} ({x['san_pham']}) — {_cach(x['cach_lam'])} {_so(x['don_gia'])}" for x in kq["bo"]]
    if kq["ngoai"]:
        ra.append(f"Dòng của mã không phải thành phẩm: giữ nguyên {kq['ngoai']} dòng.")
    if kq["chan"]:
        sau = add_days(max(x["ngay"] for x in kq["chan"]), 1)
        ra.append("")
        ra.append(f"⚠ DỪNG — KHÔNG GHI GÌ: từ {d} đã có dòng thành phẩm không cách làm / cách làm khác Tay, Máy. "
                  "Đổi bảng là các dòng này không còn giá nào để tra (lưu lại thành 0 đồng, áp giá không được):")
        ra += [f"      • {x['ngay'].strftime('%d/%m/%Y')} · {x['noi']}: {x['ten']} — {_cach(x['cach_lam'])}"
               for x in kq["chan"][:40]]
        if len(kq["chan"]) > 40:
            ra.append(f"      … và {len(kq['chan']) - 40} dòng nữa")
        ra.append(f"→ Chạy với 'tu_ngay': '{sau.isoformat()}' (ngày sau dòng cuối ở trên), hoặc sửa các dòng đó sang "
                  "Tay / Máy rồi chạy lại.")
        return "\n".join(ra)
    if not kq["doi"]:
        ra.append("Không có gì phải ghi.")
    elif kq["dry_run"]:
        ra.append("")
        ra.append("Bước tiếp: chạy lại với --kwargs \"{'dry_run': 0}\" để ghi.")
    else:
        ra.append("")
        ra.append(f"✓ Đã ghi{' bảng ' + kq['da_ghi'] if kq['da_ghi'] else ' cách làm'}.")
    ra.append(f"Nhập giá thật: SX Bang Don Gia → {kq['da_ghi'] or kq['bang'] or 'bảng mới'} — sửa các dòng "
              f"{GIA_TAM} đồng. Dòng còn {GIA_TAM} đồng = CHƯA có giá: màn Ghi hộp vẫn hiện Tay / Máy (\"chưa có giá\"), "
              "dòng ghi tính 0 đồng và vào Sổ nợ đơn giá — nhập giá thật rồi bấm Áp giá ở màn Quản lý (ngày chưa chốt "
              "thì lưu lại bảng vào hộp là tính lại).")
    return "\n".join(ra)
