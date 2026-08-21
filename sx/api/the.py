"""In thẻ mã vạch cho công nhân (D57).

═══ VÌ SAO CODE 39, VÀ VÌ SAO TỰ VẼ ═══
Thẻ phải in được từ máy in văn phòng thường, không phụ thuộc thư viện Python nào
(site này không chắc có `qrcode`/`pyqrcode`), và phải đọc được bằng MỌI máy quét
laser rẻ tiền. Code 39 thoả cả ba: bảng mã chỉ 44 ký tự, mỗi ký tự 9 vạch — 3 vạch
rộng, 6 vạch hẹp (vì thế mới gọi "3 of 9") — nên vẽ bằng <div> nền đen là xong,
không cần ảnh, không cần font đặc biệt.

Mã người dùng employee_number nếu có, không thì Employee ID. Cả hai đều là chữ
HOA + số + gạch ngang, nằm gọn trong bộ ký tự Code 39.

⚠️ IN THỬ MỘT THẺ VÀ QUÉT THỬ TRƯỚC KHI IN CẢ 45 CÁI. Bảng mã dưới đây có kiểm
bất biến ("3 rộng / 9, đúng 1 rộng ở vị trí khoảng trắng") nhưng máy quét còn phụ
thuộc độ phân giải máy in và vùng trắng hai đầu.
"""

import frappe

from sx.config.roles import guard_card

# Mỗi ký tự = 9 phần tử xen kẽ VẠCH/khoảng trắng, bắt đầu bằng vạch.
# n = hẹp, w = rộng. Bất biến Code 39: đúng 3 phần tử rộng, trong đó đúng 1 rơi vào
# khoảng trắng (vị trí lẻ). _kiem_bang() dưới đây kiểm lại lúc import.
CODE39 = {
    "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn",
    "4": "nnnwwnnnw", "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw",
    "8": "wnnwnnwnn", "9": "nnwwnnwnn",
    "A": "wnnnnwnnw", "B": "nnwnnwnnw", "C": "wnwnnwnnn", "D": "nnnnwwnnw",
    "E": "wnnnwwnnn", "F": "nnwnwwnnn", "G": "nnnnnwwnw", "H": "wnnnnwwnn",
    "I": "nnwnnwwnn", "J": "nnnnwwwnn", "K": "wnnnnnnww", "L": "nnwnnnnww",
    "M": "wnwnnnnwn", "N": "nnnnwnnww", "O": "wnnnwnnwn", "P": "nnwnwnnwn",
    "Q": "nnnnnnwww", "R": "wnnnnnwwn", "S": "nnwnnnwwn", "T": "nnnnwnwwn",
    "U": "wwnnnnnnw", "V": "nwwnnnnnw", "W": "wwwnnnnnn", "X": "nwnnwnnnw",
    "Y": "wwnnwnnnn", "Z": "nwwnwnnnn",
    "-": "nwnnnnwnw", ".": "wwnnnnwnn", " ": "nwwnnnwnn", "*": "nwnnwnwnn",
}
# CỐ Ý BỎ $ / + % : bốn ký tự đó là ngoại lệ của Code 39 (3 khoảng trắng rộng, 0
# vạch rộng) nên không qua được bất biến bên dưới. Mã nhân viên không bao giờ chứa
# chúng, mà giữ lại thì mất luôn cái kiểm bắt lỗi bảng mã — đổi đúng chiều rồi.


def _kiem_bang():
    """Sai một dòng trong bảng = in ra 45 cái thẻ không quét được mà không ai biết
    cho tới khi đứng giữa xưởng. Kiểm ngay lúc import cho rẻ."""
    for ky_tu, mau in CODE39.items():
        if len(mau) != 9 or mau.count("w") != 3:
            raise ValueError(f"Code 39 sai ở '{ky_tu}': phải 9 phần tử, 3 rộng")
        if sum(1 for i in (1, 3, 5, 7) if mau[i] == "w") != 1:
            raise ValueError(f"Code 39 sai ở '{ky_tu}': phải đúng 1 khoảng trắng rộng")


_kiem_bang()

HOP_LE = set(CODE39) - {"*"}


def _vach(ma, cao=54, hep=2, rong=5):
    """HTML các thanh của một mã Code 39 (đã bọc sẵn ký tự start/stop *)."""
    ra = []
    for ky_tu in f"*{ma}*":
        mau = CODE39[ky_tu]
        for i, kieu in enumerate(mau):
            w = rong if kieu == "w" else hep
            mau_sac = "#000" if i % 2 == 0 else "transparent"
            ra.append(
                f'<i style="display:inline-block;width:{w}px;height:{cao}px;'
                f'background:{mau_sac}"></i>'
            )
        # khoảng trắng giữa hai ký tự, bắt buộc theo chuẩn
        ra.append(f'<i style="display:inline-block;width:{hep}px;height:{cao}px"></i>')
    return "".join(ra)


def _ma_cua(e):
    ma = (e.get("employee_number") or e["name"]).strip().upper()
    return ma if all(c in HOP_LE for c in ma) else None


@frappe.whitelist()
def the_nhan_vien():
    """Trang HTML in thẻ quét cho toàn bộ công nhân công khoán. Mở rồi Ctrl+P."""
    guard_card("vaohop")
    from sx.api.portal import _nhan_vien_vao_hop

    ds, _cb = _nhan_vien_vao_hop()
    the, bo_qua = [], []
    for e in ds:
        ma = _ma_cua(e)
        if not ma:
            # Mã có ký tự Code 39 không mã hoá được (chữ có dấu, ký tự lạ) — NÓI RA
            # chứ không in thẻ trắng rồi để người ta cầm ra xưởng mới biết.
            bo_qua.append(f"{e.get('employee_name') or e['name']} ({e['name']})")
            continue
        the.append(
            '<div class="the">'
            f'<div class="ten">{frappe.utils.escape_html(e.get("employee_name") or e["name"])}</div>'
            f'<div class="bc">{_vach(ma)}</div>'
            f'<div class="ma">{frappe.utils.escape_html(ma)}</div>'
            "</div>"
        )

    canh_bao = ""
    if bo_qua:
        canh_bao = (
            '<div class="canhbao">Không in được thẻ cho: '
            + frappe.utils.escape_html(", ".join(bo_qua))
            + " — mã chứa ký tự Code 39 không hỗ trợ. Sửa Employee Number thành "
            "CHỮ HOA + số + gạch ngang rồi in lại.</div>"
        )

    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<title>Thẻ quét công nhân</title><style>
 body {{ font-family: Arial, sans-serif; margin: 10mm; }}
 .canhbao {{ border:2px solid #b91c1c; color:#b91c1c; padding:8px; margin-bottom:8mm;
   font-weight:700; border-radius:6px; }}
 .luoi {{ display:flex; flex-wrap:wrap; gap:6mm; }}
 .the {{ width:85mm; border:1px solid #999; border-radius:4mm; padding:4mm;
   text-align:center; page-break-inside:avoid; }}
 .ten {{ font-size:15pt; font-weight:700; margin-bottom:2mm; }}
 .bc {{ line-height:0; white-space:nowrap; }}
 .ma {{ font-family:monospace; font-size:11pt; letter-spacing:2px; margin-top:1mm; }}
 .huongdan {{ margin-bottom:6mm; font-size:10pt; color:#444; }}
 @media print {{ .huongdan {{ display:none }} }}
</style></head><body>
{canh_bao}
<div class="huongdan">In thử MỘT thẻ và quét thử trước khi in cả {len(the)} cái.
 In ở 100% (không "fit to page") — co giãn tỉ lệ là máy quét đọc sai.</div>
<div class="luoi">{"".join(the)}</div>
</body></html>"""
