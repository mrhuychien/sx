"""D172 (W43): khung "Sổ" ghi theo dòng — tạo định nghĩa 5 sổ theo sx/qc/seed/so.json (BM.06.05, BM.PRP.06,
BM.03.01, BM.03.02, BM.03.03), máy sản xuất đã có mã trong BM.06.01 (để sổ bảo dưỡng trỏ tới), các dòng hồ sơ cho
đoàn đánh giá (W27).

Chỉ TẠO cái còn thiếu: sổ đã có (Ban ISO đã sửa cột, vai trên site) thì không đè; máy, hồ sơ đã có mã thì bỏ qua.
Role mới của W42 (SX Co Dien, SX Hanh Chinh, SX Bao Ve) do after_migrate tạo — chạy SAU patch, nên patch tự gọi
sx.setup.dam_bao_role trước (chỉ tạo role thiếu, role có rồi không đụng). Chạy lại vô hại.
"""

import json
import os

import frappe

from sx.qc import ho_so as HS
from sx.qc import so as SO
from sx.qc import thiet_bi as TBM

SEED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "qc", "seed", "so.json")

# Máy sản xuất có mã trong BM.06.01 lần BH 01 (21/9/2026). Máy chưa cấp mã (máy rang M3, máy hút ẩm…) Ban ISO / QC
# khai ở màn Thiết bị đo khi có mã.
MAY = (
    ("TBSX-2024-00003", "Máy rang đỗ điện từ liên tục số 1 (M1)", "Phòng luộc rang đỗ", "M1"),
    ("TBSX-2024-00002", "Máy rang đỗ điện từ liên tục số 2 (M2)", "Phòng luộc rang đỗ", "M2"),
    ("TBSX-2026-00001", "Máy rang lạc", "", ""),
)
# (mã, nhóm, thứ tự, căn cứ) — dòng danh mục hồ sơ, app lập.
HO_SO = (
    ("BM.06.05", "Thiết bị đo", 40, "QT.06: bảo dưỡng định kỳ 6 tháng/lần, sau sửa chữa QC kiểm trước khi chạy lại; "
                                    "Cơ điện lưu 2 năm."),
    ("BM.PRP.06", "Điều kiện nhà xưởng (PRP)", 40, "PRP SSOP 15; QT.14 Phụ lục B — QLSX giữ sổ, lưu 2 năm."),
    ("BM.03.01", "Hệ thống quản lý", 40, "QT.03: kiểm tra thiết bị PCCC hằng tháng; lưu 3 năm."),
    ("BM.03.02", "Hệ thống quản lý", 41, "QT.03; PL.03.04: theo dõi dịch bệnh phát sinh; lưu 3 năm."),
    ("BM.03.03", "Hệ thống quản lý", 42, "QT.03: kế hoạch kiểm định thiết bị nghiêm ngặt về an toàn; lưu 3 năm."),
)


def doc_seed():
    with open(SEED, encoding="utf-8") as fh:
        return json.load(fh)


def doc_so(x):
    """Một mục seed → dict tạo SX So (lựa chọn là danh sách → mỗi dòng một; vai → bảng SX So Vai)."""
    d = {k: x.get(k) for k in SO.TRUONG_DN if k in x and k != "creation"}
    d["doctype"] = SO.PT
    d["cot"] = [dict({k: v for k, v in c.items() if k != "lua_chon"}, thu_tu=i,
                     lua_chon="\n".join(c.get("lua_chon") or [])) for i, c in enumerate(x.get("cot") or [], 1)]
    for o in SO.VAI_O:
        d[o] = [{"role": r} for r in x.get(o) or []]
    return d


def execute():
    if not frappe.db.table_exists(SO.PT):
        return
    try:
        from sx.setup import dam_bao_role
        dam_bao_role()
    except Exception:
        pass
    tao = []
    for x in doc_seed():
        if frappe.db.exists(SO.PT, x["ma"]):
            continue
        frappe.get_doc(doc_so(x)).insert(ignore_permissions=True)
        tao.append(x["ma"])
    if frappe.db.table_exists(TBM.TB):
        for ma, ten, vi_tri, may in MAY:
            if not frappe.db.exists(TBM.TB, ma):
                frappe.get_doc({"doctype": TBM.TB, "ma": ma, "ten": ten, "loai": TBM.SAN_XUAT, "vi_tri": vi_tri,
                                "may": may}).insert(ignore_permissions=True)
    if frappe.db.table_exists(HS.PT):
        co = {HS.chuan_ma(m) for m in frappe.get_all(HS.PT, pluck="ma")}
        for ma, nhom, thu_tu, can_cu in HO_SO:
            if HS.chuan_ma(ma) in co:
                continue
            frappe.get_doc({"doctype": HS.PT, "ma": ma, "ten": HS.BIEU_MAU[ma][0], "nhom": nhom, "nguon": HS.APP,
                            "bieu_mau": ma, "thu_tu": thu_tu, "bat_buoc": 1, "can_cu": can_cu}).insert(
                ignore_permissions=True)
    if tao:
        print("sx: đã tạo sổ " + ", ".join(tao))
