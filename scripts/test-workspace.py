"""D236 — trang chủ app SX trên Desk: workspace "SX" (sx/sx/workspace/sx/sx.json) + ô SX trên màn Apps (hooks.py).

Vì sao phải có bài này: workspace là tệp JSON nạp khi `bench migrate`, KHÔNG chạy validate (import_file bật
ignore_validate / ignore_links) — sai là trang chủ hiện thiếu, hiện trống, hoặc hỏng mà không ai báo:
  · khối card / shortcut trong `content` gọi tên không khớp dòng Card Break / shortcut → khối đó biến mất;
  · trùng nhãn card / shortcut → hai khối gộp một (Frappe gom theo nhãn);
  · DocType mới của app không có link → "toàn bộ chức năng" thiếu dần mà không ai biết; link tới bảng con / tên sai;
  · tệp không nằm đúng <app>/<module>/workspace/<tên>/<tên>.json → không bao giờ được nạp;
  · route trên màn Apps không khớp mẫu Desk của v16 → đăng nhập bị đẩy ra màn chọn app; khai nhầm app_logo_url →
    đổi logo thanh điều hướng của cả Desk;
  · ô SX hiện cho người không có Desk / không có vai SX.
Chạy: python3 scripts/test-workspace.py   (verify.sh gọi sẵn)
"""

import ast
import glob
import importlib.util
import json
import os
import re
import sys
import types
import xml.etree.ElementTree as ET
from datetime import datetime

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct and not dk else ''}")


def scrub(s):
    return s.replace(" ", "_").replace("-", "_").lower()


def slug(s):
    return s.lower().replace(" ", "-").replace("_", "-")


# DocType của app: {tên: json}
DT = {}
for f in glob.glob("sx/*/doctype/*/*.json"):
    d = json.load(open(f, encoding="utf-8"))
    if d.get("doctype") == "DocType":
        DT[d["name"]] = d
CHINH = {n for n, d in DT.items() if not d.get("istable")}

TEP = "sx/sx/workspace/sx/sx.json"
W = json.load(open(TEP, encoding="utf-8"))

print("-- tệp workspace nạp được khi migrate --")
kiem("đúng chỗ <app>/<module>/workspace/<tên>/<tên>.json (sai chỗ là không bao giờ được nạp)",
     TEP == f"sx/{scrub(W['module'])}/workspace/{scrub(W['name'])}/{scrub(W['name'])}.json", TEP)
kiem("module có trong modules.txt và là package", W["module"] in open("sx/modules.txt").read().split()
     and os.path.exists(f"sx/{scrub(W['module'])}/__init__.py"))
kiem("tên ASCII (scrub giữ dấu tiếng Việt → lệch thư mục), name = label; tiêu đề hiển thị tiếng Việt",
     W["name"].isascii() and W["name"] == W["label"] and W["title"] == "Sản xuất")
kiem("đủ ô bắt buộc của v16 (label, title, type, module); công khai; doctype Workspace",
     all(W.get(k) for k in ("label", "title", "type", "module")) and W["type"] == "Workspace" and W["public"] == 1
     and W["doctype"] == "Workspace")
kiem("modified đúng dạng và mới (tệp cũ hơn bản trên site thì migrate bỏ qua)",
     datetime.fromisoformat(W["modified"]) >= datetime(2026, 11, 10) and W["modified"] >= W["creation"], W["modified"])

print("\n-- khối trang chủ khớp dòng dữ liệu --")
C = json.loads(W["content"])
kiem("content là DANH SÁCH JSON (rỗng / không phải list → 'Content data shoud be a list')", isinstance(C, list) and C)
kiem("khối chỉ dùng loại có sẵn (header, shortcut, card, spacer), id không trùng",
     {b["type"] for b in C} <= {"header", "shortcut", "card", "spacer"} and len({b["id"] for b in C}) == len(C))
the = [r for r in W["links"] if r["type"] == "Card Break"]
nhan_the = [r["label"] for r in the]
khoi_the = [b["data"]["card_name"] for b in C if b["type"] == "card"]
kiem("mỗi card trong content có đúng một dòng Card Break cùng nhãn, và ngược lại (không card nào ẩn)",
     sorted(khoi_the) == sorted(nhan_the) and len(set(nhan_the)) == len(nhan_the), (khoi_the, nhan_the))
nhan_tat = [s["label"] for s in W["shortcuts"]]
khoi_tat = [b["data"]["shortcut_name"] for b in C if b["type"] == "shortcut"]
kiem("mỗi shortcut trong content có đúng một dòng shortcut cùng nhãn, nhãn không trùng",
     sorted(khoi_tat) == sorted(nhan_tat) and len(set(nhan_tat)) == len(nhan_tat), (khoi_tat, nhan_tat))
dem, sai_dem = None, []
for r in W["links"] + [{"type": "Card Break", "label": "_het"}]:
    if r["type"] == "Card Break":
        if dem is not None and dem[1] != dem[0]["link_count"]:
            sai_dem.append((dem[0]["label"], dem[0]["link_count"], dem[1]))
        dem = [r, 0]
    else:
        dem[1] += 1
kiem("link_count của từng card đúng số link theo sau", not sai_dem, sai_dem)
kiem("dòng đầu là Card Break (link trước card đầu tiên rơi vào card 'Link' vô danh)", W["links"][0]["type"] == "Card Break")
kiem("mọi dòng có type + label (bắt buộc)", all(r.get("type") and r.get("label") for r in W["links"] + W["shortcuts"]))

print("\n-- toàn bộ chức năng --")
link = [r for r in W["links"] if r["type"] == "Link"]
toi = [r["link_to"] for r in link]
kiem("link nào cũng là DocType của app (tên đúng), không trỏ bảng con",
     all(r["link_type"] == "DocType" and r["link_to"] in CHINH for r in link),
     [r["link_to"] for r in link if r["link_to"] not in CHINH])
kiem(f"MỌI DocType của app ({len(CHINH)}, trừ bảng con) có link — DocType mới quên thêm là báo ở đây",
     set(toi) == CHINH, sorted(CHINH - set(toi)))
kiem("mỗi DocType đúng một link (không lặp giữa các card)", len(toi) == len(set(toi)),
     sorted({t for t in toi if toi.count(t) > 1}))
kiem("nhãn link tiếng Việt, không để tên DocType trần (\"SX …\")", all(not r["label"].startswith("SX ") for r in link)
     and len({r["label"] for r in link}) == len(link))
tat = {s["label"]: s for s in W["shortcuts"]}
kiem("shortcut đầu: mở portal /sx (trang portal có thật)", W["shortcuts"][0]["type"] == "URL"
     and W["shortcuts"][0]["url"] == "/sx" and os.path.exists("sx/www/sx.py"))
kiem("shortcut DocType trỏ DocType có thật của app",
     all(s["link_to"] in CHINH for s in W["shortcuts"] if s["type"] == "DocType"))

print("\n-- ai thấy --")
VAI = set()
frappe = types.ModuleType("frappe")
frappe.get_roles = lambda u=None: list(VAI)
frappe.__dict__["_"] = lambda s: s
LOAI = {}
frappe.session = types.SimpleNamespace(user="a@x")
frappe.get_cached_value = lambda dt, n, f: LOAI.get(n) if (dt, f) == ("User", "user_type") else None
sys.modules["frappe"] = frappe
for g in ("sx", "sx.config"):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m
sp = importlib.util.spec_from_file_location("sx.config.roles", "sx/config/roles.py")
R = importlib.util.module_from_spec(sp)
sys.modules["sx.config.roles"] = R
sp.loader.exec_module(R)
vai_ws = {r["role"] for r in W["roles"]}
kiem("workspace chỉ hiện cho vai SX có Desk + quản trị — đúng VAI_APP_DESK (một nguồn với ô trên màn Apps)",
     vai_ws == R.VAI_APP_DESK, sorted(vai_ws ^ R.VAI_APP_DESK))
kiem("… vai nào cũng là vai app tạo (VAI_MAC_DINH, vào Desk) hoặc System Manager",
     all(R.VAI_MAC_DINH.get(v) == 1 or v == "System Manager" for v in vai_ws), vai_ws)


def thay(user, loai, *roles):
    frappe.session.user = user
    LOAI.clear()
    LOAI[user] = loai
    VAI.clear()
    VAI.update(roles)
    return R.co_quyen_app_desk()


kiem("ô SX trên màn Apps: quản lý SX (Desk) thấy", thay("ql@x", "System User", "SX Quan Ly"))
kiem("… Trưởng Ban ISO, QLSX, thủ kho NL, mua hàng thấy",
     all(thay("u@x", "System User", v) for v in ("ISO Manager", "Production Manager", "Warehouse", "Purchase User")))
kiem("… QC vào hộp (portal, không Desk) KHÔNG thấy", not thay("qc@x", "Website User", "SX Vao Hop"))
kiem("… người Desk không có vai SX (kế toán) KHÔNG thấy", not thay("kt@x", "System User", "Accounts User"))
kiem("… có vai SX mà là Website User KHÔNG thấy (không vào được Desk)", not thay("w@x", "Website User", "SX Quan Ly"))
kiem("… Administrator thấy", thay("Administrator", None))

print("\n-- hooks.py: màn Apps --")
H = open("sx/hooks.py", encoding="utf-8").read()
cay = ast.parse(H)
gan = {t.id: n.value for n in cay.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
apps = ast.literal_eval(gan["add_to_apps_screen"]) if "add_to_apps_screen" in gan else []
a = apps[0] if apps else {}
kiem("add_to_apps_screen: một ô, name = app_name", len(apps) == 1 and a.get("name") == ast.literal_eval(gan["app_name"]))
kiem("route khớp mẫu Desk của v16 (^/desk(/.*)?$) — đăng nhập vẫn vào /desk, không bị đẩy ra màn chọn app",
     re.match(r"^/desk(/.*)?$", a.get("route", "")) is not None, a.get("route"))
kiem("route trỏ đúng workspace (slug tên)", a.get("route") == f"/desk/{slug(W['name'])}", a.get("route"))
lg = a.get("logo", "")
tep_lg = lg.replace("/assets/sx/", "sx/public/", 1)
kiem("logo có thật dưới sx/public, là SVG đọc được", lg.startswith("/assets/sx/") and os.path.exists(tep_lg)
     and ET.parse(tep_lg).getroot().tag.endswith("svg"), lg)
mod, ham = a.get("has_permission", "").rsplit(".", 1)
kiem("has_permission trỏ hàm có thật", mod == "sx.config.roles" and callable(getattr(R, ham, None)), a.get("has_permission"))
kiem("KHÔNG khai hook app_logo_url (Frappe dùng làm logo thanh điều hướng của cả Desk)", "app_logo_url" not in gan)

print()
print("WORKSPACE-HỎNG ({})".format(hong) if hong else "WORKSPACE-OK")
sys.exit(1 if hong else 0)
