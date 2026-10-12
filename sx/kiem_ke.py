"""Kiểm kê kho thành phẩm theo HSD (D154; D188: chốt = đặt lại toàn kho) — phần TÍNH, không đụng DB.

Thủ kho đếm hàng trong kho theo HSD in trên hộp. Chốt kiểm kê thì số đếm THAY toàn bộ tồn của mã đó trong
kho (trừ lô đang thu hồi — để riêng, không kiểm ở đây); D188: mã có tồn mà không đếm thì số đếm là 0. Sau chốt
mỗi (mã, HSD) đúng MỘT lô — lô chuẩn `…-HSDddmmyy` (sx.utils.ma_lo_hsd). Hàm `lap_ke_hoach` nhận tồn từng lô +
số đếm theo HSD của MỘT mã và trả ra phải làm gì với từng lô:

  giu     lô CHUẨN của một HSD, số đếm của HSD đó đủ phủ → để nguyên, không sinh chứng từ
  chuyen  lô cũ (chưa có HSD, hoặc có HSD mà không phải lô chuẩn — D188 gộp về lô chuẩn) và phần dư của lô
          chuẩn mà đếm ít hơn → chuyển sang lô chuẩn của HSD đếm được (Stock Entry Repack: giá vốn đi theo
          hàng, truy xuất ngược từ lô HSD về lô cũ vẫn còn)
  xuat    phần sổ có mà đếm không thấy → xuất điều chỉnh THIẾU (Material Issue)
  nhap    phần đếm thấy mà sổ không có → nhập điều chỉnh THỪA vào lô theo HSD (Material Receipt)
  bu_am   lô đang âm (kho cho phép tồn âm) → nhập bù về 0
  bo_qua  lô đang thu hồi → không đụng

Lô cũ không biết hộp nào mang HSD nào (hộp chỉ in HSD, không in mã lô), nên lô cũ là một "bể" chung. Lấy cho
một HSD: trước hết lô cũ ghi ĐÚNG HSD đó (cùng hàng, chỉ khác tên lô); rồi lô cũ nhất mà NGÀY LÔ ≥ NSX của HSD
(hộp làm ngày D chỉ có thể nằm trong lô nhập từ ngày D trở đi); hết lô hợp lệ mới lấy lô còn lại. Phần bể thừa
là THIẾU, phần HSD chưa có nguồn là THỪA.
"""

EPS = 1e-6


def _r(x):
    return round(float(x), 6)


def lap_ke_hoach(lots, dem, nsx_cua=None):
    """Kế hoạch kiểm kê cho MỘT mã ở MỘT kho — hàm thuần.

    lots    [{batch, qty, hsd ('YYYY-MM-DD' | None), ngay (NSX / ngày tạo lô), thu_hoi, chuan}]
            `chuan` = lô theo HSD sinh từ D131 (tên …-HSDddmmyy) — lô duy nhất được GIỮ cho HSD của nó; lô có
            HSD mà không chuẩn vào bể, gộp sang lô chuẩn (D188: mỗi mã, mỗi HSD một lô).
    dem     {hsd: số đếm}; {} = đã đếm, không còn hộp nào
    nsx_cua hsd → NSX ('YYYY-MM-DD') của hộp mang HSD đó, None khi mã chưa khai hạn dùng
    """
    nsx_cua = nsx_cua or (lambda h: None)
    ke = {"giu": [], "chuyen": [], "xuat": [], "nhap": [], "bu_am": [], "bo_qua": [],
          "so_sach": 0.0, "dem": 0.0}
    dem = {str(h)[:10]: float(q) for h, q in (dem or {}).items() if h and float(q or 0) > EPS}
    ke["dem"] = _r(sum(dem.values()))

    co_hsd, be = {}, []           # be: [[lô, số còn có thể lấy]]
    for l in lots or []:
        q = float(l.get("qty") or 0)
        if abs(q) <= EPS:
            continue
        h = str(l["hsd"])[:10] if l.get("hsd") else None
        if l.get("thu_hoi"):
            ke["bo_qua"].append({"batch": l["batch"], "hsd": h, "so": _r(q)})
            continue
        ke["so_sach"] += q
        if q < 0:
            ke["bu_am"].append({"batch": l["batch"], "hsd": h, "so": _r(-q)})
            continue
        l = dict(l, qty=q, hsd=h)
        if h and l.get("chuan"):
            co_hsd.setdefault(h, []).append(l)
        else:
            be.append([l, q])     # lô cũ: chưa có HSD, hoặc có HSD mà không phải lô chuẩn (D188 — gộp về lô chuẩn)
    ke["so_sach"] = _r(ke["so_sach"])

    can = {}                      # hsd → số còn phải đưa vào lô theo HSD đó
    for h in sorted(set(co_hsd) | set(dem)):
        ds = co_hsd.get(h, [])
        co = sum(l["qty"] for l in ds)
        c = dem.get(h, 0.0)
        if c + EPS >= co:
            ke["giu"] += [{"batch": l["batch"], "hsd": h, "so": _r(l["qty"])} for l in ds]
            if c - co > EPS:
                can[h] = c - co
            continue
        du = co - c               # đếm ít hơn sổ của HSD này: phần dư của lô chuẩn vào bể
        for l in sorted(ds, key=lambda x: (str(x.get("ngay") or ""), x["batch"])):
            lay = min(l["qty"], du)
            du -= lay
            if l["qty"] - lay > EPS:
                ke["giu"].append({"batch": l["batch"], "hsd": h, "so": _r(l["qty"] - lay)})
            if lay > EPS:
                be.append([l, lay])

    be.sort(key=lambda p: (str(p[0].get("ngay") or ""), p[0]["batch"] or ""))
    for h in sorted(can):         # HSD cũ nhất trước — hàng làm sớm nhất ghép với lô sớm nhất
        nsx = nsx_cua(h)
        cung = [i for i, p in enumerate(be) if p[0].get("hsd") == h]     # lô cũ ghi đúng HSD này: cùng hàng
        hop = [i for i, p in enumerate(be) if i not in cung
               and (not nsx or not p[0].get("ngay") or str(p[0]["ngay"])[:10] >= str(nsx)[:10])]
        con_lai = sorted((i for i in range(len(be)) if i not in cung and i not in hop),
                         key=lambda i: str(be[i][0].get("ngay") or ""), reverse=True)
        for i in cung + hop + con_lai:
            if can[h] <= EPS:
                break
            lay = min(be[i][1], can[h])
            if lay <= EPS:
                continue
            be[i][1] -= lay
            can[h] -= lay
            ke["chuyen"].append({"tu": be[i][0]["batch"], "tu_hsd": be[i][0].get("hsd"), "hsd": h,
                                 "so": _r(lay)})

    ke["xuat"] = [{"batch": p[0]["batch"], "hsd": p[0].get("hsd"), "so": _r(p[1])} for p in be if p[1] > EPS]
    ke["nhap"] = [{"hsd": h, "so": _r(q)} for h, q in sorted(can.items()) if q > EPS]
    return ke


def lap_ke_hoach_lo(lots, dem):
    """Kế hoạch kiểm kê BÁN THÀNH PHẨM (D155) cho MỘT mã ở MỘT kho — kiểm theo LÔ, hàm thuần.

    BTP là hàng rời tính kg (bột nền, bột bánh, đỗ ủ…), lô theo ngày làm / lô rang, không có HSD in trên bao:
    cân từng lô. Lô nào đã cân thì số cân THAY số sổ của lô đó; lô chưa cân giữ nguyên (khác thành phẩm — ở đó
    số đếm thay cả mã, vì hộp không mang mã lô). Cùng cấu trúc kết quả với lap_ke_hoach:
      giu      phần sổ của lô còn nguyên
      xuat     lô cân thấy ít hơn sổ → xuất THIẾU phần chênh
      nhap_lo  lô cân thấy nhiều hơn sổ → nhập THỪA phần chênh vào ĐÚNG lô đó
      bu_am    lô đang âm → nhập bù về 0 (rồi nhap_lo phần cân thấy)
      bo_qua   lô đang thu hồi → không đụng (màn hình không cho cân)
    lots  [{batch, qty, thu_hoi}] — batch None = tồn không lô (mã tắt quản lý lô)
    dem   {batch: số cân} — chỉ lô đã cân
    """
    ke = {"giu": [], "chuyen": [], "xuat": [], "nhap": [], "nhap_lo": [], "bu_am": [], "bo_qua": [],
          "so_sach": 0.0, "dem": 0.0}
    ton = {}
    for l in lots or []:
        if l.get("thu_hoi"):
            if abs(float(l.get("qty") or 0)) > EPS:
                ke["bo_qua"].append({"batch": l["batch"], "hsd": None, "so": _r(l["qty"])})
            continue
        ton[l["batch"]] = ton.get(l["batch"], 0.0) + float(l.get("qty") or 0)
    bo = {x["batch"] for x in ke["bo_qua"]}
    for b in sorted(dem, key=lambda x: str(x or "")):
        if b in bo:
            continue
        q, c = ton.get(b, 0.0), max(0.0, float(dem[b] or 0))
        ke["so_sach"] += q
        ke["dem"] += c
        if q < -EPS:
            ke["bu_am"].append({"batch": b, "hsd": None, "so": _r(-q)})
            q = 0.0
        if min(q, c) > EPS:
            ke["giu"].append({"batch": b, "hsd": None, "so": _r(min(q, c))})
        if q - c > EPS:
            ke["xuat"].append({"batch": b, "hsd": None, "so": _r(q - c)})
        elif c - q > EPS:
            ke["nhap_lo"].append({"batch": b, "so": _r(c - q)})
    ke["so_sach"], ke["dem"] = _r(ke["so_sach"]), _r(ke["dem"])
    return ke


def gop_ton_lo(tong, lo):
    """Tồn theo (mã, lô) từ hai nguồn của sổ cái kho — hàm thuần (D194).

    tong  {item: tồn của mã tại kho} = qty_after_transaction của dòng sổ cái CUỐI (ERPNext tính tồn như vậy — Bin,
          Stock Balance). Không cộng actual_qty: phiếu Stock Reconciliation (tồn đầu kỳ, kiểm kê trên ERPNext) ghi
          actual_qty = 0 và đặt số tồn ở qty_after_transaction — cộng actual_qty là bỏ sót cả phần đó.
    lo    [{item, b, q}] — tồn từng lô (cộng dòng Serial and Batch Entry, batch_no cũ trên SLE).
    Trả [{item, b, q}]: các lô + phần chênh (tổng − các lô) là tồn KHÔNG gắn lô (b None). Mã có lô mà không có tổng
    (không có dòng sổ cái nào — không xảy ra trên ERPNext) thì giữ số các lô."""
    ra, theo = [], {}
    for r in lo or []:
        if r.get("b"):
            theo.setdefault(r["item"], []).append(r)
    for item in list(dict.fromkeys(list(tong or {}) + list(theo))):
        ds = theo.get(item, [])
        ra += [{"item": item, "b": r["b"], "q": _r(r["q"])} for r in ds]
        if item in (tong or {}):
            le = _r(float(tong[item] or 0) - sum(float(r["q"] or 0) for r in ds))
            if abs(le) > EPS:
                ra.append({"item": item, "b": None, "q": le})
    return ra


def chia_chung_tu(ke_theo_ma, hom_nay, doi_lo=(), kho_khac=None):
    """Chia kế hoạch các mã thành chứng từ kho — hàm thuần.

    {"repack": {item: [chuyển]}, "xuat": [{item, batch, so}], "nhap": [{item, hsd, batch, so}],
     "xuat_kl": [{item, kho, batch None, so}], "nhap_kl": [{item, kho, batch None, so}], "nhap_cu": [{item, kho, so}]}
      repack  mỗi mã một phiếu: giá vốn đi theo hàng, truy xuất ngược còn mắt xích.
      xuat    phần THIẾU + nguồn của phần chuyển dính lô ĐÃ HẾT HẠN.
      nhap    phần THỪA (batch None = lô theo HSD), bù lô âm (batch có sẵn), đích của phần chuyển hết hạn.
      xuat_kl / nhap_kl  (D189) tồn KHÔNG LÔ của mã chuyển sang quản lý lô (`doi_lo`): xuất hết phần dương, nhập bù
              phần âm về 0. Hai phiếu này ghi lúc mã còn TẮT lô; bật lô xong, phần đếm được vào lô theo HSD ở phiếu
              `nhap` (cùng giá vốn) — một mã không vừa tắt vừa bật lô trong một phiếu được, nên không Repack.
              `kho` None = kho đang kiểm kê.
      nhap_cu (D191) cờ lô là của MÃ, áp mọi kho: tồn không lô của mã đó ở KHO KHÁC (`kho_khac` {item: [(kho, số)]})
              cũng phải vào lô — kho dương: xuất ra ở xuat_kl rồi nhập lại NGUYÊN SỐ vào lô "tồn cũ" (chưa rõ HSD) ngay
              tại kho đó; kho âm (tồn âm không có thật): nhập bù về 0 ở nhap_kl.
    ERPNext không cho Repack đụng lô đã hết hạn (StockEntry.validate_batch: "Batch … has expired") — hàng hết
    hạn vẫn nằm trong kho, vẫn phải đếm, nên phần đó đi đường xuất + nhập.
    `hom_nay` = ngày ghi sổ ('YYYY-MM-DD'); HSD trước ngày đó là hết hạn.
    """
    het = lambda h: bool(h) and str(h)[:10] < str(hom_nay)[:10]   # noqa: E731
    ra = {"repack": {}, "xuat": [], "nhap": [], "xuat_kl": [], "nhap_kl": [], "nhap_cu": []}
    for i in sorted(ke_theo_ma):
        k = ke_theo_ma[i]
        doi = i in doi_lo
        for x in k["chuyen"]:
            if doi and not x["tu"]:
                ra["xuat_kl"].append({"item": i, "batch": None, "so": x["so"]})
                ra["nhap"].append({"item": i, "hsd": x["hsd"], "batch": None, "so": x["so"]})
            elif het(x["hsd"]) or het(x.get("tu_hsd")):
                ra["xuat"].append({"item": i, "batch": x["tu"], "so": x["so"]})
                ra["nhap"].append({"item": i, "hsd": x["hsd"], "batch": None, "so": x["so"]})
            else:
                ra["repack"].setdefault(i, []).append(x)
        for x in k["xuat"]:
            ra["xuat_kl" if doi and not x["batch"] else "xuat"].append({"item": i, "batch": x["batch"], "so": x["so"]})
        ra["nhap"] += [{"item": i, "hsd": x["hsd"], "batch": None, "so": x["so"]} for x in k["nhap"]]
        for x in k["bu_am"]:
            ra["nhap_kl" if doi and not x["batch"] else "nhap"].append(
                {"item": i, "hsd": x["hsd"], "batch": x["batch"], "so": x["so"]})
        ra["nhap"] += [{"item": i, "hsd": None, "batch": x["batch"], "so": x["so"]} for x in k.get("nhap_lo", [])]
    for i, ds in sorted((kho_khac or {}).items()):
        for kho, q in ds:
            if q > EPS:
                ra["xuat_kl"].append({"item": i, "kho": kho, "batch": None, "so": q})
                ra["nhap_cu"].append({"item": i, "kho": kho, "so": q})
            elif q < -EPS:
                ra["nhap_kl"].append({"item": i, "kho": kho, "batch": None, "so": -q})
    for loai in ("xuat_kl", "nhap_kl", "nhap_cu"):     # một dòng mỗi (mã, kho)
        gom = {}
        for x in ra[loai]:
            k = (x["item"], x.get("kho") or "")
            gom[k] = gom.get(k, 0.0) + x["so"]
        ra[loai] = [dict({"item": i, "kho": kho or None, "so": _r(q)}, **({} if loai == "nhap_cu" else {"batch": None}))
                    for (i, kho), q in sorted(gom.items())]
    return ra


def so_chung_tu(ct):
    """Số Stock Entry sẽ sinh: mỗi mã có chuyển lô một Repack, cộng một phiếu xuất, một phiếu nhập; mã chuyển sang
    quản lý lô (D189) thêm một phiếu xuất / một phiếu nhập phần tồn không lô."""
    return (len(ct["repack"]) + (1 if ct["xuat"] else 0) + (1 if ct["nhap"] or ct.get("nhap_cu") else 0)
            + (1 if ct.get("xuat_kl") else 0) + (1 if ct.get("nhap_kl") else 0))


def co_thay_doi(ke):
    """Kế hoạch có sinh chứng từ kho nào không (khớp hết thì không)."""
    return bool(ke["chuyen"] or ke["xuat"] or ke["nhap"] or ke["bu_am"] or ke.get("nhap_lo"))


def theo_lo(ke, ten_lo_hsd):
    """{lô: {hsd, truoc, sau, viec[]}} — bảng kết quả từng lô cho biên bản.

    `ten_lo_hsd(hsd)` → tên lô theo HSD sẽ nhận hàng (lô chuẩn …-HSDddmmyy)."""
    ra = {}

    def lo(b, h, truoc=0.0):
        return ra.setdefault(b, {"hsd": h, "truoc": truoc, "sau": truoc, "viec": []})

    for x in ke["giu"]:
        g = lo(x["batch"], x["hsd"])
        g["truoc"] += x["so"]
        g["sau"] += x["so"]
    for x in ke["chuyen"]:
        g = lo(x["tu"], x["tu_hsd"])
        g["truoc"] += x["so"]
        g["viec"].append(("chuyen_di", x["hsd"], x["so"]))
        d = lo(ten_lo_hsd(x["hsd"]), x["hsd"])
        d["sau"] += x["so"]
        d["viec"].append(("nhan", x["tu"], x["so"]))
    for x in ke["xuat"]:
        g = lo(x["batch"], x["hsd"])
        g["truoc"] += x["so"]
        g["viec"].append(("thieu", None, x["so"]))
    for x in ke["nhap"]:
        d = lo(ten_lo_hsd(x["hsd"]), x["hsd"])
        d["sau"] += x["so"]
        d["viec"].append(("thua", None, x["so"]))
    for x in ke["bu_am"]:
        g = lo(x["batch"], x["hsd"])
        g["truoc"] -= x["so"]
        g["viec"].append(("bu_am", None, x["so"]))
    for x in ke.get("nhap_lo", []):
        g = lo(x["batch"], None)
        g["sau"] += x["so"]
        g["viec"].append(("thua", None, x["so"]))
    for x in ke["bo_qua"]:
        g = lo(x["batch"], x["hsd"])
        g["truoc"] += x["so"]
        g["sau"] += x["so"]
        g["viec"].append(("thu_hoi", None, x["so"]))
    for g in ra.values():
        g["truoc"], g["sau"] = _r(g["truoc"]), _r(g["sau"])
    return ra
