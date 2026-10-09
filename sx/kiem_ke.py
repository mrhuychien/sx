"""Kiểm kê kho thành phẩm theo HSD (D154) — phần TÍNH, không đụng DB.

Thủ kho đếm hàng trong kho theo HSD in trên hộp. Chốt kiểm kê thì số đếm THAY toàn bộ tồn của mã đó trong
kho (trừ lô đang thu hồi — để riêng, không kiểm ở đây). Hàm `lap_ke_hoach` nhận tồn từng lô + số đếm theo
HSD của MỘT mã và trả ra phải làm gì với từng lô:

  giu     lô đã có HSD, số đếm của HSD đó đủ phủ → để nguyên, không sinh chứng từ
  chuyen  lô cũ chưa có HSD (và phần dư của lô có HSD mà đếm ít hơn) → chuyển sang lô theo HSD đếm được
          (Stock Entry Repack: giá vốn đi theo hàng, truy xuất ngược từ lô HSD về lô cũ vẫn còn)
  xuat    phần sổ có mà đếm không thấy → xuất điều chỉnh THIẾU (Material Issue)
  nhap    phần đếm thấy mà sổ không có → nhập điều chỉnh THỪA vào lô theo HSD (Material Receipt)
  bu_am   lô đang âm (kho cho phép tồn âm) → nhập bù về 0
  bo_qua  lô đang thu hồi → không đụng

Lô cũ không biết hộp nào mang HSD nào (hộp chỉ in HSD, không in mã lô), nên lô cũ là một "bể" chung. Ghép
HSD cũ nhất với lô cũ nhất mà NGÀY LÔ ≥ NSX của HSD đó (hộp làm ngày D chỉ có thể nằm trong lô nhập từ
ngày D trở đi); hết lô hợp lệ mới lấy lô còn lại. Phần bể thừa là THIẾU, phần HSD chưa có nguồn là THỪA.
"""

EPS = 1e-6


def _r(x):
    return round(float(x), 6)


def lap_ke_hoach(lots, dem, nsx_cua=None):
    """Kế hoạch kiểm kê cho MỘT mã ở MỘT kho — hàm thuần.

    lots    [{batch, qty, hsd ('YYYY-MM-DD' | None), ngay (NSX / ngày tạo lô), thu_hoi, chuan}]
            `chuan` = lô theo HSD sinh từ D131 (tên …-HSDddmmyy) — đếm ít hơn sổ thì giữ hàng trên lô
            chuẩn trước, bớt từ lô cũ trước.
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
        if h:
            co_hsd.setdefault(h, []).append(l)
        else:
            be.append([l, q])
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
        du = co - c               # đếm ít hơn sổ của HSD này: bớt từ lô cũ trước, lô cũ nhất trước
        for l in sorted(ds, key=lambda x: (bool(x.get("chuan")), str(x.get("ngay") or ""), x["batch"])):
            lay = min(l["qty"], du)
            du -= lay
            if l["qty"] - lay > EPS:
                ke["giu"].append({"batch": l["batch"], "hsd": h, "so": _r(l["qty"] - lay)})
            if lay > EPS:
                be.append([l, lay])

    be.sort(key=lambda p: (str(p[0].get("ngay") or ""), p[0]["batch"]))
    for h in sorted(can):         # HSD cũ nhất trước — hàng làm sớm nhất ghép với lô sớm nhất
        nsx = nsx_cua(h)
        hop = [i for i, p in enumerate(be)
               if not nsx or not p[0].get("ngay") or str(p[0]["ngay"])[:10] >= str(nsx)[:10]]
        con_lai = sorted((i for i in range(len(be)) if i not in hop),
                         key=lambda i: str(be[i][0].get("ngay") or ""), reverse=True)
        for i in hop + con_lai:
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


def chia_chung_tu(ke_theo_ma, hom_nay):
    """Chia kế hoạch các mã thành chứng từ kho — hàm thuần.

    {"repack": {item: [chuyển]}, "xuat": [{item, batch, so}], "nhap": [{item, hsd, batch, so}]}
      repack  mỗi mã một phiếu: giá vốn đi theo hàng, truy xuất ngược còn mắt xích.
      xuat    phần THIẾU + nguồn của phần chuyển dính lô ĐÃ HẾT HẠN.
      nhap    phần THỪA (batch None = lô theo HSD), bù lô âm (batch có sẵn), đích của phần chuyển hết hạn.
    ERPNext không cho Repack đụng lô đã hết hạn (StockEntry.validate_batch: "Batch … has expired") — hàng hết
    hạn vẫn nằm trong kho, vẫn phải đếm, nên phần đó đi đường xuất + nhập (hai phiếu này không bị chặn).
    `hom_nay` = ngày ghi sổ ('YYYY-MM-DD'); HSD trước ngày đó là hết hạn.
    """
    het = lambda h: bool(h) and str(h)[:10] < str(hom_nay)[:10]   # noqa: E731
    ra = {"repack": {}, "xuat": [], "nhap": []}
    for i in sorted(ke_theo_ma):
        k = ke_theo_ma[i]
        for x in k["chuyen"]:
            if het(x["hsd"]) or het(x.get("tu_hsd")):
                ra["xuat"].append({"item": i, "batch": x["tu"], "so": x["so"]})
                ra["nhap"].append({"item": i, "hsd": x["hsd"], "batch": None, "so": x["so"]})
            else:
                ra["repack"].setdefault(i, []).append(x)
        ra["xuat"] += [{"item": i, "batch": x["batch"], "so": x["so"]} for x in k["xuat"]]
        ra["nhap"] += [{"item": i, "hsd": x["hsd"], "batch": None, "so": x["so"]} for x in k["nhap"]]
        ra["nhap"] += [{"item": i, "hsd": x["hsd"], "batch": x["batch"], "so": x["so"]} for x in k["bu_am"]]
    return ra


def so_chung_tu(ct):
    """Số Stock Entry sẽ sinh: mỗi mã có chuyển lô một Repack, cộng một phiếu xuất, một phiếu nhập."""
    return len(ct["repack"]) + (1 if ct["xuat"] else 0) + (1 if ct["nhap"] else 0)


def co_thay_doi(ke):
    """Kế hoạch có sinh chứng từ kho nào không (khớp hết thì không)."""
    return bool(ke["chuyen"] or ke["xuat"] or ke["nhap"] or ke["bu_am"])


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
    for x in ke["bo_qua"]:
        g = lo(x["batch"], x["hsd"])
        g["truoc"] += x["so"]
        g["sau"] += x["so"]
        g["viec"].append(("thu_hoi", None, x["so"]))
    for g in ra.values():
        g["truoc"], g["sau"] = _r(g["truoc"]), _r(g["sau"])
    return ra
