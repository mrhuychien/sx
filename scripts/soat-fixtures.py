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


def main():
    hooks = open(os.path.join(GOC, "sx/hooks.py"), encoding="utf-8").read()
    loi = []

    # Role: bộ lọc liệt kê tên -> so trực tiếp với role.json
    m = re.search(r'"doctype":\s*"Role".*?\["name",\s*"in",\s*(\[[^\]]*\])\]',
                  hooks, re.S)
    if not m:
        loi.append("hooks.py: không đọc được bộ lọc fixtures cho Role")
    else:
        trong_hooks = set(json.loads(m.group(1).replace("'", '"')))
        trong_file = {
            r["name"] for r in
            json.load(open(os.path.join(GOC, "sx/fixtures/role.json"), encoding="utf-8"))
        }
        for ten in sorted(trong_file - trong_hooks):
            loi.append(f'role.json có "{ten}" nhưng hooks.py không liệt kê '
                       f'-> export-fixtures sẽ xoá mất')
        for ten in sorted(trong_hooks - trong_file):
            loi.append(f'hooks.py liệt kê "{ten}" nhưng role.json không có')

    # Custom Field / Print Format lọc theo module=SX -> mọi bản ghi phải có module SX
    for ten_file, nhan in (("custom_field.json", "Custom Field"),
                           ("print_format.json", "Print Format")):
        duong = os.path.join(GOC, "sx/fixtures", ten_file)
        if not os.path.exists(duong):
            continue
        for r in json.load(open(duong, encoding="utf-8")):
            if r.get("module") != "SX":
                loi.append(f'{ten_file}: {nhan} "{r.get("fieldname") or r.get("name")}" '
                           f'có module={r.get("module")!r}, bộ lọc hooks chỉ bắt "SX" '
                           f'-> export-fixtures sẽ xoá mất')

    print("\n".join(f"FIXTURE-FAIL {x}" for x in loi) if loi else "FIXTURE-OK")
    return 1 if loi else 0


if __name__ == "__main__":
    sys.exit(main())
