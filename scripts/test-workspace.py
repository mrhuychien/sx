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

print("\n-- D237: icon SX trên trang chủ Desk kiểu LƯỚI ICON (Desktop Icon) --")
# Desk v16 kiểu lưới icon (bản 16 đầu luôn vậy; bản mới khi Desktop Settings → Desktop Page = Desktop Icons) không đọc
# add_to_apps_screen lúc chạy: icon là dòng Desktop Icon, Frappe chỉ tự tạo LÚC CÀI APP. App cài từ trước → migrate
# nạp tệp app ship ở <app>/desktop_icon/*.json (frappe.model.sync: mọi tệp trong thư mục đó; bộ dọn xoá icon chuẩn
# của app không có tệp <scrub(tên)>.json).
THU = "sx/desktop_icon"
tep_icon = sorted(os.listdir(THU))
kiem("thư mục icon chỉ có tệp .json (Frappe nạp MỌI tệp trong đó — __init__.py hay tệp lạ là migrate gãy)",
     tep_icon and all(t.endswith(".json") for t in tep_icon), tep_icon)
I = json.load(open(f"{THU}/sx.json", encoding="utf-8"))
kiem("tên tệp = scrub(tên icon) — đúng đường bộ dọn tìm, không bị xoá ở lần migrate sau",
     I["name"] == I["label"] and f"{scrub(I['name'].lower())}.json" == "sx.json", I["name"])
kiem("icon loại App, nhãn = app_title, app = app_name (Frappe kiểm quyền icon App theo nhãn / app → has_permission)",
     (I["doctype"], I["icon_type"], I["label"], I["app"]) == ("Desktop Icon", "App", ast.literal_eval(gan["app_title"]),
                                                              ast.literal_eval(gan["app_name"])), I)
kiem("bấm icon mở đúng trang chủ (External → link = route ô màn Apps), cùng logo",
     (I["link_type"], I["link"], I["logo_url"]) == ("External", a.get("route"), a.get("logo")), I)
kiem("icon chuẩn, không ẩn, không giới hạn vai riêng (quyền theo has_permission của app)",
     (I["standard"], I["hidden"], I["roles"]) == (1, 0, []))
kiem("modified đúng dạng, mới (tệp cũ hơn bản trên site thì migrate bỏ qua)",
     datetime.fromisoformat(I["modified"]) >= datetime(2026, 11, 10))
O_ICON = {"label", "standard", "link", "icon", "idx", "logo_url", "icon_type", "app", "link_to", "parent_icon", "hidden",
          "link_type", "roles", "sidebar", "icon_image", "restrict_removal", "bg_color"}
kiem("chỉ ô có trong schema Desktop Icon (v16.0.0 … 16.55) + ô hệ thống",
     set(I) - {"doctype", "name", "owner", "creation", "modified", "modified_by", "docstatus"} <= O_ICON,
     set(I) - O_ICON)

print("\n-- D238: icon SX vào bố cục trang chủ ĐÃ LƯU (Frappe 16.16: có bố cục là bỏ qua icon chuẩn mới) --")
ROLES_CUA = {"ql@x": ["SX Quan Ly"], "kt@x": ["Accounts User"], "iso@x": ["ISO Manager"], "web@x": ["SX Quan Ly"],
             "hu@x": ["SX Quan Ly"], "rong@x": ["SX Quan Ly"]}
LOAI_CUA = {"ql@x": "System User", "kt@x": "System User", "iso@x": "System User", "web@x": "Website User",
            "hu@x": "System User", "rong@x": "System User"}
frappe.get_roles = lambda u=None: ROLES_CUA.get(u or frappe.session.user, [])
frappe.get_cached_value = lambda dt, n, f: LOAI_CUA.get(n) if (dt, f) == ("User", "user_type") else None
CU = [{"name": "ERPNext", "label": "ERPNext", "icon_type": "App", "idx": 3, "parent_icon": None},
      {"name": "Accounting", "label": "Accounting", "icon_type": "Link", "idx": 9, "parent_icon": "ERPNext"},
      {"name": "Kế toán", "label": "Kế toán", "icon_type": "Folder", "idx": 5, "parent_icon": None}]
DB_ICON = {"SX": {"label": "SX", "link": "/desk/sx", "link_type": "External", "app": "sx", "icon_type": "App",
                  "parent_icon": None, "idx": 50, "standard": 1, "logo_url": "/assets/sx/images/sx-logo.svg",
                  "hidden": 0, "name": "SX", "restrict_removal": 0}}
BO_CUC, GHI, BANG = {}, [], {"Desktop Layout": True}


def dat_bo_cuc():
    BO_CUC.clear()
    BO_CUC.update({
        "ql@x": json.dumps(CU),
        "kt@x": json.dumps(CU),
        "iso@x": json.dumps(CU + [dict(DB_ICON["SX"], idx=2)]),
        "web@x": json.dumps(CU),
        "hu@x": "{không phải json",
        "rong@x": "{}",
        "Administrator": json.dumps(CU),
    })
    GHI.clear()


class _r(dict):
    __getattr__ = dict.get


frappe.db = types.SimpleNamespace(
    table_exists=lambda dt: BANG.get(dt, False),
    exists=lambda dt, n=None: dt == "Desktop Icon" and n in DB_ICON,
    has_column=lambda dt, f: f in ("label", "link", "link_type", "app", "icon_type", "parent_icon", "idx", "standard",
                                   "logo_url", "hidden", "name", "restrict_removal"),
    get_value=lambda dt, n, f, as_dict=False: _r({k: DB_ICON[n].get(k) for k in f}),
    set_value=lambda dt, n, f, v, update_modified=True: (GHI.append((n, f, update_modified)),
                                                          BO_CUC.__setitem__(n, v)),
    commit=lambda: None)
frappe.get_all = lambda dt, fields=None, **k: [_r(name=u, user=u, layout=l) for u, l in BO_CUC.items()]
P = importlib.util.spec_from_file_location("sx.patches.d238", "sx/patches/d238_icon_sx_vao_bo_cuc.py")
PA = importlib.util.module_from_spec(P)
P.loader.exec_module(PA)
dat_bo_cuc()
with open(os.devnull, "w") as _n:
    _cu, sys.stdout = sys.stdout, _n
    try:
        PA.execute()
    finally:
        sys.stdout = _cu
moi = json.loads(BO_CUC["ql@x"])
kiem("quản lý SX (Desk) đã có bố cục: icon SX vào CUỐI hàng ngoài cùng (idx lớn nhất + 1, bỏ qua icon con)",
     [x["name"] for x in moi] == ["ERPNext", "Accounting", "Kế toán", "SX"] and moi[-1]["idx"] == 6
     and moi[-1]["link"] == "/desk/sx" and moi[-1]["parent_icon"] is None and moi[-1]["hidden"] == 0, moi[-1:])
kiem("… sắp xếp cũ giữ nguyên từng icon", moi[:3] == CU)
kiem("… Administrator cũng có", json.loads(BO_CUC["Administrator"])[-1]["name"] == "SX")
kiem("… ghi đúng khuôn Frappe tự lưu (json.dumps mặc định — toàn ASCII, chèn thẳng vào HTML trang chủ)",
     BO_CUC["ql@x"].isascii() and BO_CUC["ql@x"] == json.dumps(json.loads(BO_CUC["ql@x"])))
kiem("người Desk KHÔNG có vai SX (kế toán): bố cục không đụng — bố cục đã lưu không qua lọc quyền",
     BO_CUC["kt@x"] == json.dumps(CU))
kiem("có vai SX nhưng là Website User: không đụng", BO_CUC["web@x"] == json.dumps(CU))
kiem("đã có icon SX (tự thêm / tự dời): không thêm lần hai, không đổi chỗ",
     json.loads(BO_CUC["iso@x"]) == CU + [dict(DB_ICON["SX"], idx=2)])
kiem("bố cục hỏng / rỗng ({}): bỏ qua, không gãy migrate", BO_CUC["hu@x"] == "{không phải json"
     and BO_CUC["rong@x"] == "{}")
kiem("ghi thẳng ô layout, không đổi 'modified' (không phải người dùng sửa)",
     sorted(n for n, _f, _u in GHI) == ["Administrator", "ql@x"] and all(f == "layout" and u is False
                                                                         for _n, f, u in GHI), GHI)
GHI.clear()
with open(os.devnull, "w") as _n:
    _cu, sys.stdout = sys.stdout, _n
    try:
        PA.execute()
    finally:
        sys.stdout = _cu
kiem("chạy lại: không ghi gì thêm (đã có icon thì thôi)", GHI == [], GHI)
dat_bo_cuc()
DB_ICON_CU = DB_ICON.pop("SX")
PA.execute()
kiem("site chưa có dòng icon SX (chưa migrate D237): không làm gì", GHI == [])
DB_ICON["SX"] = DB_ICON_CU
BANG["Desktop Layout"] = False
PA.execute()
kiem("Frappe chưa có Desktop Layout (bản 16 cũ hơn): không làm gì", GHI == [])
BANG["Desktop Layout"] = True
kiem("patch đăng ký ở [post_model_sync] — chạy SAU khi migrate nạp icon SX",
     open("sx/patches.txt").read().split("[post_model_sync]")[1].split().count("sx.patches.d238_icon_sx_vao_bo_cuc")
     == 1)

print()
print("WORKSPACE-HỎNG ({})".format(hong) if hong else "WORKSPACE-OK")
sys.exit(1 if hong else 0)
