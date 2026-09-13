"""BM.07.03 — kiểm nguyên liệu đầu vào trên Purchase Invoice.

Vì sao phải có bài này: đây là CỔNG. Nới nhầm thì lô dừa sấy không có COA vi
sinh đi thẳng vào kho rồi vào bánh, và không có gì trên màn hình nói khác đi —
hoá đơn vẫn duyệt, tồn vẫn tăng, chỉ là tờ hồ sơ ghi "Đạt". Siết nhầm thì thủ
kho không duyệt nổi hoá đơn mua bao bì và sẽ bỏ trống ô QC cho xong việc, tức
là cổng tự mở.

Chốt bốn thứ:
  1. Dòng không phải nguyên liệu (bao bì, dịch vụ) đi qua không vướng gì.
  2. Hai luật ÉP kết luận chạy đúng, kể cả với nhóm hàng con.
  3. Mâu thuẫn Đạt / cảm quan Không đạt bị CHẶN.
  4. Duyệt hoá đơn sinh phiếu sự cố; duyệt lại không nhân đôi.

Chạy: python3 scripts/test-tiepnhan.py   (verify.sh gọi sẵn)
"""

import importlib.util
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

DA_TAO = []
DA_BAO = []
CAY_NHOM = {"Sữa bột nguyên kem": "Phụ liệu bột",
            "Phụ liệu bột": "Nguyên liệu",
            "Nguyên liệu": None,
            "Đỗ xanh": "Nguyên liệu",
            "Bao bì": None}
NHOM_CUA_ITEM = {"SUA-01": "Sữa bột nguyên kem", "DX-01": "Đỗ xanh",
                 "TUI-01": "Bao bì"}
CAI_DAT = {}


class Loi(Exception):
    pass


class Doc(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v

    def insert(self, **kw):
        self["name"] = f"SC-{len(DA_TAO) + 1:04d}"
        DA_TAO.append(self)
        return self


frappe = types.ModuleType("frappe")
frappe.throw = lambda m, e=None: (_ for _ in ()).throw((e or Loi)(str(m)))
frappe.msgprint = lambda m, **k: DA_BAO.append(str(m))
frappe.get_doc = lambda d: Doc(d)
frappe.get_cached_doc = lambda dt: Doc(CAI_DAT)
frappe.get_cached_value = lambda dt, ten, truong: (
    CAY_NHOM.get(ten) if dt == "Item Group" else NHOM_CUA_ITEM.get(ten))
frappe.db = types.SimpleNamespace(
    exists=lambda dt, dk: any(x.get("khoa_cu") == dk.get("khoa_cu") for x in DA_TAO))
frappe.__dict__["_"] = lambda s: s
frappe.utils = types.ModuleType("frappe.utils")
frappe.utils.flt = lambda v, p=None: (round(float(v or 0), p) if p is not None
                                      else float(v or 0))
frappe.utils.cint = lambda v: int(float(v or 0))
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = frappe.utils

for goi in ("sx", "sx.qc"):
    m = types.ModuleType(goi)
    m.__path__ = []
    sys.modules[goi] = m


def nap(ten, duong):
    sp = importlib.util.spec_from_file_location(ten, duong)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[ten] = mod
    sp.loader.exec_module(mod)
    return mod


NG = nap("sx.qc.nguong", "sx/qc/nguong.py")
T = nap("sx.qc.tiep_nhan", "sx/qc/tiep_nhan.py")

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + ct) if ct else ''}")


def dong(item="DX-01", **kw):
    d = Doc({"idx": 1, "item_code": item, "item_name": item, "qty": 100,
             "uom": "kg"})
    d.update({f"custom_{k}": v for k, v in kw.items()})
    return d


def ng(do_am=13.0, coa=("Phụ liệu bột",)):
    return {"do_am_toi_da": do_am, "nhom_can_coa": list(coa)}


def xet(d, item_group=None):
    return T.kiem_dong(d, item_group or NHOM_CUA_ITEM.get(d["item_code"]),
                       ng(), lambda g: CAY_NHOM.get(g))


# ═══ 1. Dòng nào được kiểm ═══════════════════════════════════════════════
print("-- dòng nào là nguyên liệu, dòng nào không --")
kiem("dòng trống phần QC → bỏ qua (bao bì, dịch vụ, vật tư sửa chữa)",
     not T.co_kiem(dong("TUI-01")))
kiem("chỉ ghi mỗi số lô → đã là dòng cần kiểm", T.co_kiem(dong(ncc_lo="L123")))
kiem("chỉ ghi mỗi độ ẩm → đã là dòng cần kiểm", T.co_kiem(dong(do_am=12.0)))
kiem("ghi kết luận Đạt → đã là dòng cần kiểm", T.co_kiem(dong(ket_luan="Đạt")))

# ═══ 2. Độ ẩm ════════════════════════════════════════════════════════════
print("\n-- độ ẩm --")
kl, bao = xet(dong(do_am=12.5, ket_luan="Đạt"))
kiem("12,5% (dưới ngưỡng 13) → không đụng vào kết luận", kl is None and not bao)
kl, bao = xet(dong(do_am=13.0, ket_luan="Đạt"))
kiem("đúng 13,0% → vẫn Đạt (ngưỡng là ≤, không phải <)", kl is None)
kl, bao = xet(dong(do_am=14.2, ket_luan="Đạt"))
kiem("14,2% → ÉP sang Cách ly", kl == "Cách ly", str(kl))
kiem("và nói ra con số, không sửa lặng lẽ", bao and "14.2" in bao, bao or "")
kl, _b = xet(dong(do_am=0, ket_luan="Đạt"))
kiem("chưa đo (0) → không ép gì", kl is None)
kl, _b = xet(dong(do_am=20.0, ket_luan="Không đạt"))
kiem("đã Không đạt rồi thì KHÔNG hạ xuống Cách ly", kl == "Không đạt", str(kl))

# ═══ 3. COA vi sinh ══════════════════════════════════════════════════════
print("\n-- COA vi sinh theo nhóm hàng --")
kl, bao = xet(dong("SUA-01", coa_vi_sinh="Không", ket_luan="Đạt"))
kiem("sữa bột ở NHÓM CON của nhóm bắt buộc → vẫn ÉP Cách ly",
     kl == "Cách ly", str(kl))
kiem("và nói rõ nhóm nào", bao and "Sữa bột" in bao, bao or "")
kl, _b = xet(dong("SUA-01", coa_vi_sinh="Có", ket_luan="Đạt"))
kiem("có COA → không đụng vào", kl is None)
kl, _b = xet(dong("SUA-01", coa_vi_sinh="Không yêu cầu", ket_luan="Đạt"))
kiem("'Không yêu cầu' KHÁC 'Không' → không ép", kl is None)
kl, _b = xet(dong("DX-01", coa_vi_sinh="Không", ket_luan="Đạt"))
kiem("đỗ xanh không thuộc nhóm bắt buộc → không ép", kl is None)
kl, _b = T.kiem_dong(dong("SUA-01", coa_vi_sinh="Không", ket_luan="Đạt"),
                     "Sữa bột nguyên kem",
                     {"do_am_toi_da": 13.0, "nhom_can_coa": []},
                     lambda g: CAY_NHOM.get(g))
kiem("chưa khai nhóm nào ở Setting → luật COA KHÔNG chạy (không đoán bừa)",
     kl is None)

# Cây nhóm hàng bị vòng là dữ liệu hỏng, nhưng nó không được phép treo cả lần
# lưu hoá đơn — thủ kho sẽ thấy màn hình đứng và không ai đoán ra vì sao.
kiem("cây nhóm bị vòng vẫn thoát ra được",
     T._nhom_va_cha("A", lambda g: {"A": "B", "B": "A"}.get(g)) == ["A", "B"])

# ═══ 4. Mâu thuẫn ════════════════════════════════════════════════════════
print("\n-- mâu thuẫn trên cùng một lô --")
kiem("Đạt + cảm quan Không đạt = mâu thuẫn",
     T.mau_thuan(dong(ket_luan="Đạt", cam_quan_dat="Không đạt")))
kiem("Cách ly + cảm quan Không đạt = hợp lý, không phải mâu thuẫn",
     not T.mau_thuan(dong(ket_luan="Cách ly", cam_quan_dat="Không đạt")))
kiem("Đạt + cảm quan Đạt = bình thường",
     not T.mau_thuan(dong(ket_luan="Đạt", cam_quan_dat="Đạt")))

# ═══ 5. Móc vào Purchase Invoice ═════════════════════════════════════════
print("\n-- lưu hoá đơn --")
CAI_DAT.update({"do_am_toi_da": 13.0,
                "nhom_can_coa": [Doc({"item_group": "Phụ liệu bột"})]})


def hoa_don(*ds):
    for i, d in enumerate(ds, 1):
        d["idx"] = i
    return Doc({"name": "PINV-0001", "posting_date": "2026-09-14",
                "items": list(ds), "custom_nguoi_kiem": "qc@rvhg.vn"})


DA_BAO[:] = []
hd = hoa_don(dong("DX-01", do_am=14.5, ket_luan="Đạt"), dong("TUI-01"))
T.validate(hd)
kiem("ép kết luận đúng dòng có ghi QC", hd["items"][0]["custom_ket_luan"] == "Cách ly")
kiem("dòng bao bì không bị đụng tới", "custom_ket_luan" not in hd["items"][1])
kiem("có báo ra màn hình", len(DA_BAO) == 1, str(DA_BAO))

DA_BAO[:] = []
T.validate(hoa_don(dong("DX-01", do_am=12.0, ket_luan="Đạt")))
kiem("hoá đơn sạch thì KHÔNG hiện hộp thoại làm phiền", not DA_BAO)

try:
    T.validate(hoa_don(dong("DX-01", ket_luan="Đạt", cam_quan_dat="Không đạt")))
    kiem("chặn mâu thuẫn khi lưu", False)
except Loi as e:
    kiem("chặn mâu thuẫn khi lưu", "cảm quan" in str(e), str(e)[:70])

# ═══ 6. Duyệt hoá đơn → phiếu sự cố ══════════════════════════════════════
print("\n-- duyệt hoá đơn --")
DA_TAO[:] = []
hd = hoa_don(dong("DX-01", ncc_lo="L-2609", ket_luan="Không đạt", do_am=15.0),
             dong("SUA-01", ncc_lo="S-77", ket_luan="Cách ly"),
             dong("TUI-01", ket_luan="Đạt"),
             dong("DX-01"))
T.on_submit(hd)
kiem("lập đúng 2 phiếu (Đạt và dòng trống không tính)", len(DA_TAO) == 2,
     str(len(DA_TAO)))
kiem("nguồn = Tiếp nhận NL", all(x["nguon"] == "Tiếp nhận NL" for x in DA_TAO))
kiem("Không đạt = mức Cao, Cách ly = mức Thường",
     [x["muc_do"] for x in DA_TAO] == ["Cao", "Thường"],
     str([x["muc_do"] for x in DA_TAO]))
kiem("phiếu mang số lô của NCC để truy ngược",
     [x["lo_anh_huong"] for x in DA_TAO] == ["L-2609", "S-77"])
kiem("mô tả có cả độ ẩm đo được", "15.0%" in DA_TAO[0]["mo_ta"], DA_TAO[0]["mo_ta"])
kiem("ghi số lượng để biết cách ly bao nhiêu",
     DA_TAO[0]["so_luong"] == "100.0 kg", str(DA_TAO[0]["so_luong"]))
kiem("lấy ngày của hoá đơn, không phải hôm nay",
     all(x["ngay"] == "2026-09-14" for x in DA_TAO))
kiem("mở sẵn, chờ xử lý", all(x["trang_thai"] == "Mở" for x in DA_TAO))

T.on_submit(hd)
T.on_submit(hd)
kiem("huỷ rồi duyệt lại KHÔNG đẻ phiếu thứ hai", len(DA_TAO) == 2,
     str(len(DA_TAO)))

# Lỗ im lặng: luật sinh sự cố bám vào ô kết luận, nên bỏ trống ô đó là cách
# chắc chắn nhất để một lô có vấn đề đi vào kho không dấu vết — mà nhìn màn hình
# thì dòng ấy trông y hệt dòng đã kiểm xong.
print("\n-- kiểm dở rồi bỏ trống kết luận --")
DA_TAO[:] = []
try:
    T.on_submit(hoa_don(dong("DX-01", ncc_lo="L-99", do_am=12.0)))
    kiem("chặn duyệt khi dòng đã kiểm dở mà chưa có kết luận", False)
except Loi as e:
    kiem("chặn duyệt khi dòng đã kiểm dở mà chưa có kết luận",
         "kết luận" in str(e), str(e)[:60])
kiem("và không lập phiếu sự cố nửa vời", not DA_TAO)
try:
    T.on_submit(hoa_don(dong("TUI-01"), dong("TUI-01")))
    kiem("hoá đơn KHÔNG phải nguyên liệu vẫn duyệt bình thường", True)
except Loi as e:
    kiem("hoá đơn KHÔNG phải nguyên liệu vẫn duyệt bình thường", False, str(e)[:60])

print("TIEPNHAN-FAIL ({} ca)".format(hong) if hong else "TIEPNHAN-OK")
sys.exit(1 if hong else 0)
