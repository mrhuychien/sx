"""D169 (W39): nước máy lấy thẳng tại vòi, không qua bể chứa (PRP lần BH 02, SSOP 1) — việc định kỳ "thau rửa
bể" (nếu site có khai ở màn Việc định kỳ) thôi nhắc: đặt `ngung=1`, KHÔNG xoá (các lần đã làm vẫn là hồ sơ).

Nhận theo tên, không dấu, không phân biệt hoa thường: có việc làm sạch (thau / súc / rửa / vệ sinh) và nói bể
(bể, bể nước, bể chứa) hoặc bồn nước / bồn chứa. Không đụng bể ngâm, bể / bồn nước thải, bể phốt, bể tự hoại,
bồn rửa tay — các việc đó vẫn còn. Chạy lại vô hại.
"""

import re
import unicodedata

import frappe

PT = "SX Viec Dinh Ky"
LAM_SACH = re.compile(r"\b(thau|suc|rua|ve sinh)\b")
KHONG_PHAI = re.compile(r"\b(thai|phot|tu hoai)\b")
BE = re.compile(r"\bbe(\s+(nuoc|chua)\b|\s*([^\w\s]|$))|\bbon\s+(nuoc|chua)\b")


def khong_dau(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return " ".join("".join(c for c in s if unicodedata.category(c) != "Mn").split())


def la_thau_rua_be(ten):
    t = khong_dau(ten)
    return bool(LAM_SACH.search(t) and BE.search(t) and not KHONG_PHAI.search(t))


def execute():
    if not frappe.db.table_exists(PT):
        return
    for x in frappe.get_all(PT, filters={"ngung": 0}, fields=["name", "ten"]):
        if la_thau_rua_be(x.ten):
            frappe.db.set_value(PT, x.name, "ngung", 1)
            print(f"D169: ngừng việc định kỳ {x.name} — {x.ten} (nước lấy tại vòi, không có bể)")
