#!/usr/bin/env python3
"""Soát fixtures: bộ lọc trong hooks.py phải KHỚP nội dung fixtures/*.json.

Bộ lọc chỉ áp lúc `bench export-fixtures`. Lệch một tên thì lần export sau lặng lẽ
XOÁ bản ghi đó khỏi file, site cài mới sau đó thiếu — và không có lỗi nào báo.
Đã dính thật một lần: role SX Thu Kho thêm ở D56 mà quên thêm vào hooks.

Chạy: python3 scripts/soat-fixtures.py   (đã gọi sẵn trong scripts/verify.sh)
"""

import json
import os
import re
import sys

GOC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _soat_role():
    """Mọi role app dùng phải có trong VAI_MAC_DINH, và dam_bao_role chỉ TẠO role
    thiếu — không save role đã có (save là đăng xuất người giữ role)."""
    import importlib.util
    import types

    TAO, DA_CO = [], {"SX Ghi So", "Production Manager"}
    frappe = types.ModuleType("frappe")
    frappe.__dict__["_"] = lambda s: s
    frappe.db = types.SimpleNamespace(exists=lambda dt, n: n in DA_CO)

    class Doc(dict):
        def insert(self, **k):
            TAO.append(self["role_name"])

        def save(self, **k):
            raise AssertionError("save role đã có")

    frappe.get_doc = lambda d, n=None: Doc(d) if isinstance(d, dict) else Doc(role_name=n)
    sys.modules["frappe"] = frappe
    for g in ("sx", "sx.config"):
        m = types.ModuleType(g); m.__path__ = []; sys.modules[g] = m

    def nap(ten, p):
        sp = importlib.util.spec_from_file_location(ten, os.path.join(GOC, p))
        mo = importlib.util.module_from_spec(sp)
        sys.modules[ten] = mo
        sp.loader.exec_module(mo)
        return mo

    R = nap("sx.config.roles", "sx/config/roles.py")
    S = nap("sx.setup", "sx/setup.py")
    loi = []
    dung = set(R.ROLE_VIEWS) | {r for v in R.CARD_ROLES.values() for r in v} \
        | set(R.NHAN_ROLE)
    thieu = sorted(dung - set(R.VAI_MAC_DINH) - {"System Manager", "Administrator"})
    if thieu:
        loi.append(f"roles.py dùng role {thieu} nhưng VAI_MAC_DINH không có -> site mới thiếu")
    import contextlib
    import io
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            S.dam_bao_role()
    except AssertionError as e:
        loi.append(f"dam_bao_role sửa role đã có ({e}) -> đăng xuất người dùng")
    if set(TAO) != set(R.VAI_MAC_DINH) - DA_CO:
        loi.append(f"dam_bao_role tạo {sorted(TAO)}, đáng ra chỉ tạo role còn thiếu")
    return loi


def main():
    hooks = open(os.path.join(GOC, "sx/hooks.py"), encoding="utf-8").read()
    loi = []

    # Role: KHÔNG được là fixture (D105). Fixtures bị xoá-tạo-lại mỗi lần migrate;
    # tạo lại role là Frappe tính lại kiểu tài khoản và ĐĂNG XUẤT người giữ role.
    if re.search(r'"doctype":\s*"Role"', hooks):
        loi.append('hooks.py: Role lại nằm trong fixtures -> mỗi lần migrate đăng xuất '
                   'người dùng. Role tạo bằng sx.setup.dam_bao_role (D105)')
    if os.path.exists(os.path.join(GOC, "sx/fixtures/role.json")):
        loi.append("sx/fixtures/role.json còn đó -> Frappe vẫn nạp nó mỗi lần migrate "
                   "(nạp MỌI file .json trong fixtures/, không theo hooks)")
    if "sx.setup.dam_bao_role" not in hooks.split("after_migrate", 1)[-1].split("\n")[0]:
        loi.append("hooks.py: after_migrate thiếu sx.setup.dam_bao_role -> site mới "
                   "thiếu role mà không ai biết")
    loi.extend(_soat_role())

    # Custom Field / Print Format lọc theo module -> mọi bản ghi phải nằm trong
    # danh sách module mà hooks.py liệt kê. ĐỌC TỪ hooks, không viết cứng "SX":
    # viết cứng thì thêm module mới (QC, D85) là bài soát này tự nói dối.
    for ten_file, nhan in (("custom_field.json", "Custom Field"),
                           ("print_format.json", "Print Format")):
        dt = nhan
        m2 = re.search(r'"doctype":\s*"%s",\s*"filters":\s*\[\[\s*"module",\s*'
                       r'"(=|in)",\s*(".*?"|\[[^\]]*\])\s*\]\]' % dt, hooks, re.S)
        if not m2:
            loi.append(f"hooks.py: không đọc được bộ lọc fixtures cho {nhan}")
            continue
        tho = m2.group(2)
        cho_phep = ({json.loads(tho)} if tho.startswith('"')
                    else set(json.loads(tho.replace("'", '"'))))
        duong = os.path.join(GOC, "sx/fixtures", ten_file)
        if not os.path.exists(duong):
            continue
        for r in json.load(open(duong, encoding="utf-8")):
            if r.get("module") not in cho_phep:
                loi.append(f'{ten_file}: {nhan} "{r.get("fieldname") or r.get("name")}" '
                           f'có module={r.get("module")!r}, bộ lọc hooks chỉ bắt '
                           f'{sorted(cho_phep)} -> export-fixtures sẽ xoá mất')

    print("\n".join(f"FIXTURE-FAIL {x}" for x in loi) if loi else "FIXTURE-OK")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
