"""Xuất hồ sơ theo dõi cho đoàn kiểm tra ra Excel / PDF (D176) — màn ISO → Xuất báo cáo.

Nguồn là CHÍNH bản in của từng biểu mẫu (sx/api/qc_hoso._in — cùng tờ người ta vẫn in, cùng tờ trong gói zip cho
đoàn): không dựng một bản "dữ liệu" thứ hai để rồi lệch với tờ giấy. Một biểu mẫu trong kỳ ra một hay nhiều TỜ (mỗi
tháng một tờ, mỗi phiếu một tờ, danh mục hiện hành…).
  · Excel — mỗi tờ một sheet, dựng lại đúng bảng của tờ in: ô gộp (colspan / rowspan), dòng tiêu đề đậm, chữ ngoài
    bảng (tên biểu mẫu, ghi chú, người ký) mỗi dòng một hàng; ô chắc chắn là số thì ghi SỐ (lọc, cộng được). Sheet
    đầu là Mục lục: kỳ, người xuất, mỗi biểu mẫu có những tờ nào (bấm sang sheet), kỳ này trống hay in lỗi.
  · PDF — mỗi biểu mẫu một lượt dựng (wkhtmltopdf của Frappe) theo ĐÚNG khổ giấy tờ in khai (@page A4 ngang / dọc,
    lề), ghép một tệp: trang bìa mục lục (biểu mẫu → trang) + bookmark từng biểu mẫu.
Hàm THUẦN (không đọc DB): test gọi thẳng; phần dựng workbook / PDF nhận thư viện truyền vào (openpyxl; get_pdf +
PdfWriter của Frappe).
"""

import csv
import html as _html
import io
import re
from html.parser import HTMLParser

PT = "SX Xuat Bao Cao"
EXCEL, PDF = "Excel", "PDF"
KIEU = (EXCEL, PDF)
CHO, DANG, XONG, LOI = "Đang chờ", "Đang tạo", "Xong", "Lỗi"
TRANG_THAI = (CHO, DANG, XONG, LOI)
TOI_DA_THANG = 24           # như gói zip (sx/qc/ho_so.py) — kỳ dài hơn thì chia nhiều lần xuất
MUC_LUC = "BM.01.04"        # danh mục hồ sơ — gói zip coi là tệp mục lục; xuất thì in bản hiện hành

# Mỗi biểu mẫu ra những tờ nào trong kỳ — hiện cạnh tên để người chọn biết sẽ nhận gì (khớp nhánh của qc_hoso._in).
KY = {
    "BM.08.01": "mỗi tháng một tờ (tờ từng ngày)", "BM.08.03": "mỗi tháng một tờ", "BM.08.05": "mỗi tháng một tờ",
    "BM.15.01": "mỗi tháng một tờ", "BM.PRP.01": "mỗi tháng một tờ", "SLM": "mỗi tháng một tờ",
    "BM.07.03": "mỗi tháng một tờ", "BC.THANG": "mỗi tháng đã qua một báo cáo", "BM.PRP.03": "mỗi tuần một tờ",
    "BM.06.02": "mỗi năm một tờ", "BM.06.03": "mỗi năm một tờ", "BM.06.04": "mỗi năm một tờ",
    "KH.KN.01": "mỗi năm một tờ", "BM.08.02": "các phiếu trong kỳ", "BM.11.01": "các khiếu nại trong kỳ",
    "BM.09.01": "các chuyến trong kỳ", "BM.01.07": "các phiếu trong kỳ", "BM.08.04": "các phiếu đã duyệt trong kỳ",
    "BM.02.04": "các lần diễn tập trong kỳ", "HUY_MAU": "mỗi biên bản huỷ trong kỳ",
    "BM.01.13": "mỗi đợt ban hành trong kỳ", "BM.07.01": "mỗi phiếu đã duyệt trong kỳ",
    "BM.06.01": "danh mục hiện hành", "BM.07.02": "danh sách hiện hành", "TU_CONG_BO": "danh mục hiện hành",
    "BM.01.02": "danh mục hiện hành", "BM.01.03": "danh mục hiện hành", MUC_LUC: "danh mục hiện hành",
}
KY_BIEN_BAN = "mỗi biên bản ký đủ trong kỳ"
KY_SO = "mỗi tháng có dòng một tờ / danh mục hiện hành"
KY_KHAC = "trong kỳ"


def ky_cua(ma, bien_ban=(), so=()):
    """Chữ gợi ý "sẽ nhận những tờ nào" của một biểu mẫu (biên bản, sổ: theo khung chung W43 / W45)."""
    if ma in KY:
        return KY[ma]
    if ma in set(bien_ban or ()):
        return KY_BIEN_BAN
    if ma in set(so or ()):
        return KY_SO
    return KY_KHAC


NGOAI_DANH_MUC = "Chưa có trong danh mục hồ sơ"


def nhom_bieu_mau(bieu_mau, nhom_cua, thu_tu_nhom, bien_ban=(), so=()):
    """Danh sách chọn trên màn: [{ten (nhóm), bm: [{ma, ten, ky}]}]. Biểu mẫu xếp theo NHÓM của dòng danh mục hồ sơ
    (BM.01.04 — Ban ISO đã quen nhóm này), nhóm theo thứ tự danh mục; biểu mẫu chưa có dòng danh mục ở nhóm cuối.
    `bieu_mau` = {mã: tên}; `nhom_cua` = {mã: nhóm}."""
    nhom = {}
    for ma, ten in bieu_mau.items():
        nhom.setdefault(nhom_cua.get(ma) or NGOAI_DANH_MUC, []).append(
            {"ma": ma, "ten": ten, "ky": ky_cua(ma, bien_ban, so)})
    thu = {n: i for i, n in enumerate(thu_tu_nhom)}
    return [{"ten": n, "bm": sorted(ds, key=lambda x: x["ma"])}
            for n, ds in sorted(nhom.items(), key=lambda t: (t[0] == NGOAI_DANH_MUC, thu.get(t[0], len(thu)), t[0]))]


def ten_tep(kieu, tu, den):
    """Tên tệp tải về: ho-so-theo-doi_<từ>_<đến>.xlsx / .pdf (không dấu — máy nào mở cũng đọc được tên)."""
    return f"ho-so-theo-doi_{tu}_{den}.{'xlsx' if kieu == EXCEL else 'pdf'}"


# ── HTML tờ in → các khối (dòng chữ, bảng) ─────────────────────────────────────────────────────

KHONG_DOC = {"style", "script", "title", "head"}
BAN_THU_LOP = "sx-ban-thu"  # khối dòng "có dữ liệu mẫu" của đầu trang in chung — tệp xuất đặt chân trang riêng (D185)
KHOI = {"div", "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "section", "header", "footer", "article",
        "blockquote", "pre", "dl", "dt", "dd", "form", "fieldset", "address", "center"}
TIEU_DE = {"h1", "h2", "h3"}
XUONG = "\x00"              # dấu xuống dòng THẬT (<br>, hết khối) — khác xuống dòng trong mã nguồn HTML (chỉ là cách)
TOI_DA_GOP = 100            # colspan / rowspan gõ sai (9999) không được làm nổ lưới


def _gop(v):
    try:
        return max(1, min(TOI_DA_GOP, int(str(v).strip())))
    except (TypeError, ValueError):
        return 1


def gon(manh):
    """Ghép các mảnh chữ: khoảng trắng của mã nguồn gộp một dấu cách; XUONG thành xuống dòng; bỏ dòng trống."""
    s = re.sub(r"[ \t\r\n\f\v ]+", " ", "".join(manh))
    return "\n".join(d.strip() for d in s.split(XUONG) if d.strip())


class _Tach(HTMLParser):
    """Đi một lượt qua tờ in: chữ ngoài bảng → dòng; bảng → hàng × ô (giữ colspan / rowspan, ô tiêu đề <th>);
    bảng lồng trong ô → chữ của ô (mỗi hàng một dòng, ô cách nhau " | ")."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.khoi = []      # [("dong", chữ, kiểu) | ("bang", [[ô]])]
        self.doan = []
        self.kieu = ""
        self.bo = 0
        self.bang = []
        self.chan = 0       # đang trong khối .sx-ban-thu (dòng "có dữ liệu mẫu") — tệp xuất tự đặt chân trang (D185)

    def _xa(self):
        for d in gon(self.doan).split("\n"):
            if d:
                self.khoi.append(("dong", d, self.kieu))
        self.doan = []

    @staticmethod
    def _dong_o(b):
        o = b["o"]
        if o is None:
            return
        b["o"] = None
        o["text"] = gon(o.pop("chu"))
        if not b["hang"]:
            b["hang"].append([])
        b["hang"][-1].append(o)

    def _het_bang(self):
        b = self.bang.pop()
        self._dong_o(b)
        hang = [h for h in b["hang"] if h]
        cha = self.bang[-1] if self.bang else None
        if cha is None:
            if hang:
                self.khoi.append(("bang", hang))
        elif cha["o"] is not None:
            cha["o"]["chu"] += [XUONG] + [XUONG.join([" | ".join(o["text"] for o in h if o["text"]) for h in hang])
                                          ] + [XUONG]

    def handle_starttag(self, tag, attrs):
        if tag in KHONG_DOC:
            self.bo += 1
            return
        if self.bo:
            return
        if self.chan or (tag == "div" and BAN_THU_LOP in str(dict(attrs).get("class") or "").split()):
            self.chan += tag == "div"
            return
        b = self.bang[-1] if self.bang else None
        if tag == "table":
            if b is None:
                self._xa()
            self.bang.append({"hang": [], "o": None})
            return
        if b is not None:
            if tag == "tr":
                self._dong_o(b)
                b["hang"].append([])
            elif tag in ("td", "th"):
                self._dong_o(b)
                a = dict(attrs)
                b["o"] = {"chu": [], "cs": _gop(a.get("colspan", 1)), "rs": _gop(a.get("rowspan", 1)),
                          "th": tag == "th"}
            elif b["o"] is not None and (tag == "br" or tag in KHOI):
                b["o"]["chu"].append(XUONG)
            return
        if tag == "br" or tag in KHOI:
            self.doan.append(XUONG)
            if tag in TIEU_DE:
                self._xa()
                self.kieu = "tieu_de"

    def handle_endtag(self, tag):
        if tag in KHONG_DOC:
            self.bo = max(0, self.bo - 1)
            return
        if self.bo:
            return
        if self.chan:
            self.chan -= tag == "div"
            return
        b = self.bang[-1] if self.bang else None
        if tag == "table":
            if b is not None:
                self._het_bang()
            return
        if b is not None:
            if tag in ("td", "th", "tr"):
                self._dong_o(b)
            elif b["o"] is not None and tag in KHOI:
                b["o"]["chu"].append(XUONG)
            return
        if tag in KHOI:
            self.doan.append(XUONG)
            if tag in TIEU_DE:
                self._xa()
                self.kieu = ""

    def handle_data(self, data):
        if self.bo or self.chan:
            return
        b = self.bang[-1] if self.bang else None
        if b is None:
            self.doan.append(data)
        elif b["o"] is not None:
            b["o"]["chu"].append(data)

    def ket(self):
        self.close()
        while self.bang:          # tờ in thiếu </table> — vẫn lấy được bảng
            self._het_bang()
        self._xa()
        return self.khoi


def tach(html):
    """Tờ in (HTML) → [("dong", chữ, kiểu) | ("bang", hàng)] theo thứ tự trên giấy. Ô = {text, cs, rs, th}."""
    t = _Tach()
    t.feed(str(html or ""))
    return t.ket()


def tach_csv(chu):
    """Tệp CSV (sổ sự cố BM.08.02) → một khối bảng; hàng đầu là tiêu đề."""
    hang = list(csv.reader(io.StringIO(str(chu or "").lstrip("﻿"))))
    hang = [h for h in hang if any((x or "").strip() for x in h)]
    return [("bang", [[{"text": (x or "").strip(), "cs": 1, "rs": 1, "th": i == 0} for x in h]
                      for i, h in enumerate(hang)])] if hang else []


def _dat(hang):
    chiem, ra = set(), []
    for r, h in enumerate(hang):
        c = 0
        for o in h:
            while (r, c) in chiem:
                c += 1
            cs, rs = o["cs"], min(o["rs"], len(hang) - r)
            for i in range(rs):
                for j in range(cs):
                    chiem.add((r + i, c + j))
            ra.append((r, c, dict(o, cs=cs, rs=rs)))
            c += cs
    return ra, (max(c for _r, c in chiem) + 1 if chiem else 0)


def luoi(hang):
    """Đặt ô lên lưới như trình duyệt: ô vào cột trống đầu tiên của hàng, ô rowspan giữ chỗ ở các hàng dưới.
    → ([(hàng, cột, ô)], số cột). Rowspan vượt đáy bảng thì cắt ở đáy (trình duyệt cũng vậy); colspan vượt bề
    ngang thật của bảng (các ô không gộp ngang tới đâu) thì cắt ở mép — "colspan=99" không đẻ 99 cột Excel."""
    ra, cot = _dat(hang)
    that = max((c + 1 for _r, c, o in ra if o["cs"] == 1), default=0)
    if that and cot > that:
        hang = [[dict(o, cs=max(1, min(o["cs"], that - c))) for (_r, c, o) in sorted(
            (t for t in ra if t[0] == r), key=lambda t: t[1])] for r in range(len(hang))]
        ra, cot = _dat(hang)
    return ra, cot


SO_NGUYEN = re.compile(r"^-?(0|[1-9]\d{0,14})$")
SO_LE = re.compile(r"^-?(0|[1-9]\d{0,14})\.\d{1,2}$")


def so(t):
    """Chữ trong ô → số khi CHẮC là số (Excel lọc, cộng được); không chắc thì giữ chữ: "09" (mã), "1.250" (có thể là
    nghìn), "99.5%" giữ nguyên."""
    s = str(t or "").strip()
    if SO_NGUYEN.match(s):
        return int(s)
    if SO_LE.match(s):
        return float(s)
    return t


CAM_SHEET = re.compile(r"[:\\/?*\[\]]")


def ten_sheet(goi_y, da_co):
    """Tên sheet hợp lệ (≤ 31 ký tự, không : \\ / ? * [ ], không trùng — Excel không phân biệt hoa thường).
    `da_co`: tập tên (chữ thường) đã dùng — hàm thêm tên mới vào."""
    s = CAM_SHEET.sub("-", str(goi_y or "")).strip().strip("'").strip() or "To"
    s = s[:31].strip()
    goc, i = s, 2
    while s.lower() in da_co:
        hau = f" ({i})"
        s = goc[:31 - len(hau)].rstrip() + hau
        i += 1
    da_co.add(s.lower())
    return s


def nhan_to(ma, ten_tep, mot_to):
    """Tên gợi ý cho sheet / bookmark của một tờ: biểu mẫu chỉ một tờ → mã; nhiều tờ → mã + tên tệp (tháng…)."""
    goc = str(ten_tep or "").rsplit(".", 1)[0]
    return ma if mot_to or not goc else f"{ma} {goc}"


# ── khổ giấy của tờ in (PDF, thiết lập in của sheet) ──────────────────────────────────────────

TRANG = re.compile(r"@page\s*\{(?!\s*@)([^}]*)\}", re.I)   # bỏ @page chỉ chứa ô lề (@bottom-center — D185)
DO_DAI = re.compile(r"^\d+(\.\d+)?(mm|cm|in)$")


def kho_giay(html):
    """Tuỳ chọn wkhtmltopdf theo @page đầu tiên của tờ in: khổ, hướng, lề (CSS 1–4 giá trị). Không khai → A4 dọc,
    lề 10 mm. wkhtmltopdf không đọc @page nên phải tự truyền — không thì tờ ngang in dọc, mất cột."""
    ra = {"page-size": "A4", "orientation": "Portrait", "margin-top": "10mm", "margin-right": "10mm",
          "margin-bottom": "10mm", "margin-left": "10mm"}
    m = TRANG.search(str(html or ""))
    if not m:
        return ra
    k = m.group(1)
    sz = re.search(r"size\s*:\s*([^;]+)", k, re.I)
    if sz:
        p = sz.group(1).lower().split()
        if "landscape" in p:
            ra["orientation"] = "Landscape"
        kho = [x for x in p if re.fullmatch(r"a[3-6]|letter|legal", x)]
        if kho:
            ra["page-size"] = kho[0].upper() if kho[0].startswith("a") else kho[0].capitalize()
    mg = re.search(r"margin\s*:\s*([^;]+)", k, re.I)
    if mg:
        p = mg.group(1).split()
        if 1 <= len(p) <= 4 and all(DO_DAI.match(x) for x in p):
            if len(p) == 1:
                p = p * 4
            elif len(p) == 2:
                p = [p[0], p[1], p[0], p[1]]
            elif len(p) == 3:
                p = [p[0], p[1], p[2], p[1]]
            t, r, b, l_ = p
            ra.update({"margin-top": t, "margin-right": r, "margin-bottom": b, "margin-left": l_})
    return ra


THAN = re.compile(r"<body[^>]*>(.*)</body>", re.I | re.S)
NGAT = '<div style="page-break-after:always"></div>'


def than_html(h):
    """Phần trong <body> của một tờ (tờ của _trang là cả tài liệu) — để ghép nhiều tờ cùng mẫu vào một lượt dựng."""
    m = THAN.search(str(h or ""))
    return m.group(1) if m else str(h or "")


def ghep_html(cac_to, tieu_de=""):
    """Các tờ CÙNG MẪU → một tài liệu, mỗi tờ sang trang mới (khối <style> của mẫu đi theo từng tờ — cùng luật)."""
    return (f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>{_html.escape(tieu_de)}</title>'
            f"</head><body>{NGAT.join(than_html(h) for h in cac_to)}</body></html>")


def bang_html(cot, hang):
    """Bảng HTML đơn giản (tờ CSV → PDF)."""
    e = _html.escape
    return ("<table><tr>" + "".join(f"<th>{e(c)}</th>" for c in cot) + "</tr>"
            + "".join("<tr>" + "".join(f"<td>{e(x)}</td>" for x in h) + "</tr>" for h in hang) + "</table>")


# ── Excel ───────────────────────────────────────────────────────────────────────────────────

KY_TU_CAM = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
TOI_DA_O = 32000            # Excel: tối đa 32 767 ký tự một ô


def chu_o(v):
    """Giá trị ghi vào ô: bỏ ký tự điều khiển (openpyxl từ chối), cắt chữ quá dài."""
    if isinstance(v, str):
        v = KY_TU_CAM.sub("", v)
        return v[:TOI_DA_O]
    return v


def _ghi(ws, r, c, v, **kieu):
    o = ws.cell(row=r, column=c, value=chu_o(v))
    if isinstance(o.value, str) and o.value.startswith("="):
        o.data_type = "s"        # "=…" là chữ người gõ, không phải công thức (chống chèn công thức vào Excel)
    for k, x in kieu.items():
        setattr(o, k, x)
    return o


def _do_rong(chu):
    return max((len(d) for d in str(chu or "").split("\n")), default=0)


def chan_trang(ws, chan, r):
    """Dòng chân trang (site có dữ liệu mẫu — D185): hàng cuối sheet + chân trang khi in Excel (mọi trang)."""
    if not chan:
        return
    _ghi(ws, r, 1, chan)
    ws.oddFooter.center.text = chan
    ws.oddFooter.center.size = 8


def ve_sheet(opx, ws, tieu_de, khoi, kho=None, chan=""):
    """Một tờ in → sheet: dòng tiêu đề, rồi lần lượt các khối (dòng chữ cột A; bảng có viền, ô gộp, <th> đậm nền
    xám), `chan` ở cuối. Đặt hướng giấy theo tờ in, in vừa bề ngang trang."""
    st = opx.styles
    mong = st.Side(style="thin", color="000000")
    vien = st.Border(left=mong, right=mong, top=mong, bottom=mong)
    boc = st.Alignment(wrap_text=True, vertical="top")
    xam = st.PatternFill("solid", fgColor="EEEEEE")
    dam = st.Font(bold=True)
    rong, o_bang = {}, []
    _ghi(ws, 1, 1, tieu_de, font=st.Font(bold=True, size=13))
    r0 = 3
    for k in khoi:
        if k[0] == "dong":
            _ghi(ws, r0, 1, k[1], font=st.Font(bold=True, size=12) if k[2] == "tieu_de" else st.Font())
            r0 += 1
            continue
        o_ds, so_cot = luoi(k[1])
        so_hang = max((r + o["rs"] for r, _c, o in o_ds), default=0)
        for r in range(so_hang):                  # viền cả ô bị gộp — Excel chỉ vẽ viền ô góc nếu không
            for c in range(so_cot):
                x = ws.cell(row=r0 + r, column=1 + c)
                x.border = vien
                x.alignment = boc
        for r, c, o in o_ds:
            x = _ghi(ws, r0 + r, 1 + c, so(o["text"]), border=vien, alignment=boc)
            if o["th"]:
                x.font = dam
                x.fill = xam
            if o["cs"] > 1 or o["rs"] > 1:
                ws.merge_cells(start_row=r0 + r, start_column=1 + c, end_row=r0 + r + o["rs"] - 1,
                               end_column=c + o["cs"])
            elif o["text"]:
                rong[1 + c] = max(rong.get(1 + c, 0), _do_rong(o["text"]))
            if o["rs"] == 1 and o["text"]:
                o_bang.append((r0 + r, 1 + c, o["cs"], o["text"]))
        r0 += so_hang + 1
    chan_trang(ws, chan, r0 + 1)
    for c, w in rong.items():
        rong[c] = max(6, min(50, w + 2))
        ws.column_dimensions[opx.utils.get_column_letter(c)].width = rong[c]
    # Chiều cao hàng có chữ xuống dòng: Excel không tự giãn hàng của tệp dựng sẵn (nhất là ô gộp) — ước theo bề
    # rộng cột (ký tự / dòng), đủ để đọc hết chữ, không cần bấm từng hàng.
    cao = {}
    for r, c, cs, chu in o_bang:
        w = sum(rong.get(c + j, 12) for j in range(cs))
        n = sum(max(1, -(-len(d) // max(1, int(w * 1.1)))) for d in chu.split("\n"))
        cao[r] = max(cao.get(r, 1), n)
    for r, n in cao.items():
        if n > 1:
            ws.row_dimensions[r].height = min(409, 15 * n)
    if kho:
        ws.page_setup.orientation = "landscape" if kho.get("orientation") == "Landscape" else "portrait"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True


def khoi_cua(ten_tep, noi_dung):
    """Một tờ (tên tệp, nội dung) → các khối: CSV thì một bảng; còn lại là HTML."""
    if str(ten_tep or "").lower().endswith(".csv"):
        return tach_csv(noi_dung if isinstance(noi_dung, str) else noi_dung.decode("utf-8-sig", "replace"))
    return tach(noi_dung if isinstance(noi_dung, str) else noi_dung.decode("utf-8", "replace"))


def dung_excel(opx, dau, bm):
    """Workbook: Mục lục + mỗi tờ một sheet → bytes.

    `dau` = {tieu_de, dong: [chữ], chan: chữ chân trang mọi sheet ("" = không)} — đầu Mục lục (kỳ, người xuất, ghi
    chú). `bm` = [{ma, ten, to: [(tên tệp, nội dung)], loi}] theo thứ tự chọn. Ghi `sheet` (tên sheet từng tờ) vào
    từng biểu mẫu."""
    wb = opx.Workbook()
    ml = wb.active
    ml.title = "Mục lục"
    da_co = {"mục lục"}
    for x in bm:
        x["sheet"] = []
        mot = len(x.get("to") or []) == 1
        for ten_tep, nd in x.get("to") or []:
            ten = ten_sheet(nhan_to(x["ma"], ten_tep, mot), da_co)
            ws = wb.create_sheet(ten)
            ve_sheet(opx, ws, f"{x['ma']} — {x['ten']}" + ("" if mot else f" · {str(ten_tep).rsplit('.', 1)[0]}"),
                     khoi_cua(ten_tep, nd), kho_giay(nd if isinstance(nd, str) else ""), dau.get("chan") or "")
            x["sheet"].append(ten)
    _ve_muc_luc(opx, ml, dau, bm)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _ve_muc_luc(opx, ws, dau, bm):
    st = opx.styles
    mong = st.Side(style="thin", color="000000")
    vien = st.Border(left=mong, right=mong, top=mong, bottom=mong)
    boc = st.Alignment(wrap_text=True, vertical="top")
    _ghi(ws, 1, 1, dau.get("tieu_de") or "Hồ sơ theo dõi", font=st.Font(bold=True, size=14))
    r = 2
    for d in dau.get("dong") or []:
        _ghi(ws, r, 1, d)
        r += 1
    r += 1
    for c, t in enumerate(("STT", "Mã", "Biểu mẫu", "Tờ (bấm để mở)", "Ghi chú"), 1):
        _ghi(ws, r, c, t, font=st.Font(bold=True), fill=st.PatternFill("solid", fgColor="EEEEEE"), border=vien,
             alignment=boc)
    r += 1
    for i, x in enumerate(bm, 1):
        to = x.get("sheet") or [""]
        ghi_chu = ("Không in được: " + x["loi"]) if x.get("loi") else ("" if x.get("sheet") else "Kỳ này không có bản ghi")
        for j, ten in enumerate(to):
            for c, v in enumerate((i if j == 0 else "", x["ma"] if j == 0 else "", x["ten"] if j == 0 else "",
                                   ten, ghi_chu if j == 0 else ""), 1):
                _ghi(ws, r, c, v, border=vien, alignment=boc)
            if ten:
                o = ws.cell(row=r, column=4)
                o.hyperlink = f"#'{ten}'!A1"
                o.hyperlink.location, o.hyperlink.target = f"'{ten}'!A1", None   # liên kết TRONG tệp
                o.font = st.Font(color="0563C1", underline="single")
            r += 1
    chan_trang(ws, dau.get("chan") or "", r + 1)
    for c, w in zip("ABCDE", (6, 14, 46, 30, 40)):
        ws.column_dimensions[c].width = w


# ── PDF ─────────────────────────────────────────────────────────────────────────────────────

def nhom_theo_kho(cac_to):
    """Các tờ của MỘT biểu mẫu → [(tuỳ chọn khổ giấy, [html])] — tờ liền nhau cùng khổ dựng một lượt (wkhtmltopdf
    chỉ đổi hướng giấy giữa các lượt)."""
    ra = []
    for h in cac_to:
        k = kho_giay(h)
        if ra and ra[-1][0] == k:
            ra[-1][1].append(h)
        else:
            ra.append((k, [h]))
    return ra


def bia_html(dau, bm, trang):
    """Trang bìa PDF: đầu (kỳ, người xuất…) + bảng biểu mẫu → trang bắt đầu (`trang`: {mã: số trang} — None = không
    có tờ)."""
    e = _html.escape
    hang = []
    for i, x in enumerate(bm, 1):
        if x.get("loi"):
            gc, tr = "Không in được: " + x["loi"], ""
        elif trang.get(x["ma"]) is None:
            gc, tr = "Kỳ này không có bản ghi", ""
        else:
            gc, tr = f"{len(x.get('to') or [])} tờ", str(trang[x["ma"]])
        hang.append(f"<tr><td class='c'>{i}</td><td>{e(x['ma'])}</td><td>{e(x['ten'])}</td><td class='c'>{e(tr)}</td>"
                    f"<td>{e(gc)}</td></tr>")
    return ('<!doctype html><html lang="vi"><head><meta charset="utf-8"><style>'
            'body{font:12px/1.35 "Times New Roman",serif;color:#000}h1{font-size:18px;text-align:center;margin:0 0 6px}'
            '.d{text-align:center;margin:0 0 2px}table{width:100%;border-collapse:collapse;margin-top:10px}'
            'td,th{border:1px solid #000;padding:3px 5px;vertical-align:top}th{background:#eee}.c{text-align:center}'
            'tr{page-break-inside:avoid}</style></head><body>'
            f"<h1>{e(dau.get('tieu_de') or '')}</h1>"
            + "".join(f"<div class='d'>{e(d)}</div>" for d in dau.get("dong") or [])
            + "<table><tr><th style='width:5%'>STT</th><th style='width:13%'>Mã</th><th>Biểu mẫu</th>"
              "<th style='width:8%'>Trang</th><th style='width:30%'>Ghi chú</th></tr>" + "".join(hang)
            + "</table></body></html>")


def dung_pdf(lam_pdf, moi_writer, dau, bm):
    """Ghép PDF: mỗi biểu mẫu dựng riêng (theo khổ từng tờ), rồi trang bìa đánh số trang, rồi bookmark → bytes.

    `lam_pdf(html, tuỳ chọn, writer)` thêm trang vào writer (frappe.utils.pdf.get_pdf với output=…);
    `moi_writer()` → PdfWriter rỗng. Một biểu mẫu dựng hỏng thì ghi lỗi vào biểu mẫu đó (bìa nói rõ), các biểu mẫu
    khác vẫn vào tệp. Không biểu mẫu nào dựng được mà có lỗi → ném lỗi đầu tiên (máy chủ thiếu wkhtmltopdf…)."""
    phan, loi_dau = [], None
    # chân trang mọi trang (site có dữ liệu mẫu — D185): wkhtmltopdf không đọc @page @bottom-center của tờ in
    chan = {"footer-center": dau["chan"], "footer-font-size": "8", "footer-spacing": "3"} if dau.get("chan") else {}
    for x in bm:
        cac_to = [nd if isinstance(nd, str) else nd.decode("utf-8", "replace") for _t, nd in x.get("to") or []]
        if not cac_to or x.get("loi"):
            continue
        tam = moi_writer()              # dựng riêng: biểu mẫu hỏng giữa chừng không để lại trang dở trong tệp
        try:
            for kho, nhom in nhom_theo_kho(cac_to):
                lam_pdf(ghep_html(nhom, f"{x['ma']} — {x['ten']}"), dict(kho, **chan), tam)
        except Exception as e:  # noqa: BLE001 — một biểu mẫu hỏng không chặn cả tệp
            x["loi"] = str(e) or type(e).__name__
            loi_dau = loi_dau or e
            continue
        if len(tam.pages):
            phan.append((x, tam))
    if loi_dau is not None and not phan:
        raise loi_dau
    vi_tri, dem = {}, 0
    for x, w in phan:
        vi_tri[x["ma"]] = dem
        dem += len(w.pages)
    so_bia, bia = 1, None
    for _lan in range(3):                 # số trang bìa đổi thì số trang các mục đổi — dựng lại tối đa 2 lần
        bia = moi_writer()
        lam_pdf(bia_html(dau, bm, {m: t + so_bia + 1 for m, t in vi_tri.items()}),
                {"page-size": "A4", "orientation": "Portrait", "margin-top": "12mm", "margin-right": "12mm",
                 "margin-bottom": "12mm", "margin-left": "12mm", **chan}, bia)
        if len(bia.pages) == so_bia:
            break
        so_bia = len(bia.pages)
    for _x, w in phan:
        for p in w.pages:
            bia.add_page(p)
    bia.add_outline_item("Mục lục", 0)
    for x, _w in phan:
        bia.add_outline_item(f"{x['ma']} — {x['ten']}", vi_tri[x["ma"]] + so_bia)
    buf = io.BytesIO()
    bia.write(buf)
    return buf.getvalue()
