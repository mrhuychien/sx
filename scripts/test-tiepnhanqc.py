"""D160 (W33) — màn "Tiếp nhận NL" cho QC trên điện thoại (BM.07.03 + kiểm xe BM.09.01).

Vì sao phải có bài này: QC chế biến không có Desk, nên trước W33 phần QC của phiếu nhập mua chỉ người có
Desk ghi được — tức là thủ kho tự ghi "Đạt" cho hàng mình nhận. Màn điện thoại phải:
  · ghi ĐÚNG ô QC có sẵn, không đụng số lượng / đơn giá / kho (QC sửa số lượng là sai sổ kho);
  · chạy y luật Desk khi lưu: xe không đạt / thiếu COA → ép Cách ly, lô Cách ly vào kho cách ly, "Đạt"
    mà cảm quan Không đạt bị chặn — và NÓI ra cho QC thấy (cổng không hiện thông báo server khi thành công);
  · chỉ phiếu nháp: phiếu đã duyệt là phần QC đã khoá;
  · đúng người: QC ghi, Ban ISO / QLSX chỉ xem, người ngoài QC không vào.

Nạp sx/api/qc_tiepnhan.py, sx/qc/tiep_nhan.py, kiem_xe.py, ncc.py THẬT trên frappe giả; hook validate /
on_submit của phiếu nhập mua gắn như sx/hooks.py.
Chạy: python3 scripts/test-tiepnhanqc.py   (verify.sh gọi sẵn)
"""

import base64
import json
import os
import re
import sys
import types
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fakefrappe as F  # noqa: E402

frappe = F.cai()
# Như frappe thật: msgprint ghi vào nhật ký thông báo của request.
frappe.local = types.SimpleNamespace(message_log=[])
frappe.msgprint = lambda m, **k: frappe.local.message_log.append({"message": m, **k})
F.Doc.set = lambda self, k, v: self.__setitem__(k, v)
Q = F.nap_qc()
NCC = F.nap("sx.qc.ncc", "sx/qc/ncc.py")
TN = F.nap("sx.qc.tiep_nhan", "sx/qc/tiep_nhan.py")
KX = F.nap("sx.qc.kiem_xe", "sx/qc/kiem_xe.py")
A = F.nap("sx.api.qc_tiepnhan", "sx/api/qc_tiepnhan.py")
kiem, thu = F.kiem, F.thu
F.dat_ngay("2026-10-09")


class PhieuMua(F.Document):
    """Hook như sx/hooks.py: kiem_xe → tiep_nhan → ncc (validate), kiem_xe (before_submit),
    tiep_nhan (on_submit). Dòng con chép ra bảng "<doctype> Item" như frappe lưu bảng con."""

    def validate(self):
        if self.doctype == "Purchase Receipt":
            KX.validate(self)
        TN.validate(self)
        NCC.canh_bao_mua(self)

    def before_submit(self):
        if self.doctype == "Purchase Receipt":
            KX.before_submit(self)

    def on_update(self):
        b = F.bang(f"{self.doctype} Item")
        for k in [k for k, v in b.items() if v["parent"] == self.name]:
            del b[k]
        for r in self.get("items") or []:
            b[r["name"]] = dict(r, parent=self.name, parenttype=self.doctype)

    def on_submit(self):
        TN.on_submit(self)


class TepGia(F.DocThuong):
    def get_content(self):
        return self.get("content")


F.dang_ky("Purchase Receipt", PhieuMua)
F.dang_ky("Purchase Invoice", PhieuMua)
F.dang_ky("File", TepGia)

# ── dữ liệu nền ────────────────────────────────────────────────────────
F.bang("Item Group").update({
    "Phụ liệu bột": {"name": "Phụ liệu bột", "parent_item_group": "Nguyên liệu"},
    "Sữa bột": {"name": "Sữa bột", "parent_item_group": "Phụ liệu bột"},
    "Nguyên liệu": {"name": "Nguyên liệu", "parent_item_group": None},
    "Đỗ": {"name": "Đỗ", "parent_item_group": "Nguyên liệu"},
})
F.bang("Item").update({"SUA": {"name": "SUA", "item_group": "Sữa bột"},
                       "DX": {"name": "DX", "item_group": "Đỗ"}})
F.bang("Supplier").update({
    "NCC-SUA": {"name": "NCC-SUA", "custom_ncc_duyet": 1, "custom_loai_ncc": NCC.TP, "custom_nguon_goc": NCC.TRONG_NUOC},
    "NCC-DV": {"name": "NCC-DV", "custom_ncc_duyet": 1, "custom_loai_ncc": NCC.DV},
})
F.bang("SX Ho So NCC").update({"HS-1": {"name": "HS-1", "parenttype": "Supplier", "parent": "NCC-SUA",
                                        "loai_ho_so": NCC.PKN, "so_hieu": "PKN-26/01", "het_han": date(2027, 3, 1)}})
F.CAI_DAT.update({"nhom_can_coa": [F.Doc(item_group="Phụ liệu bột")],
                  "nhom_can_aflatoxin": [F.Doc(item_group="Đỗ")]})
F.CAI_DAT_SX.update({"kho_cach_ly": "Kho cách ly - HG"})


def phieu(ten, dt="Purchase Receipt", ngay="2026-10-08", ncc="NCC-SUA", **k):
    d = {"doctype": dt, "name": ten, "supplier": ncc, "supplier_name": f"Công ty {ncc}", "posting_date": ngay,
         "docstatus": 0, "is_return": 0,
         "items": [{"name": f"{ten}-1", "idx": 1, "item_code": "SUA", "item_name": "Sữa bột nguyên kem", "qty": 50,
                    "uom": "Kg", "rate": 120000, "warehouse": "Kho NVL - HG"},
                   {"name": f"{ten}-2", "idx": 2, "item_code": "DX", "item_name": "Đỗ xanh", "qty": 500,
                    "uom": "Kg", "rate": 30000, "warehouse": "Kho NVL - HG"}]}
    d.update(k)
    d["items"] = [F.Doc(r) for r in d["items"]]
    doc = F.get_doc(d)
    doc.insert()
    return doc


phieu("PR-1")
phieu("PR-CU", ngay="2026-09-20")                                       # quá 14 ngày
phieu("PR-TRA", is_return=1)
phieu("PR-DV", ncc="NCC-DV")
phieu("PI-1", dt="Purchase Invoice", update_stock=1, ngay="2026-10-09")
phieu("PI-KHONG-KHO", dt="Purchase Invoice", update_stock=0)
d = phieu("PR-DUYET", ngay="2026-10-07")
F.bang("Purchase Receipt")["PR-DUYET"]["docstatus"] = 1
frappe.local.message_log.clear()

# ═══ 1. Quyền, danh sách ═════════════════════════════════════════════════
print("-- quyền, danh sách phiếu chờ kiểm --")
F.vai("SX Vao Hop")
kiem("người ngoài QC không vào được", thu(A.ds_tiep_nhan) is not None)
F.vai("ISO Manager")
kiem("Ban ISO xem được danh sách nhưng không ghi được",
     thu(A.ds_tiep_nhan) is None and A.ds_tiep_nhan()["duoc_ghi"] is False
     and "QC" in (thu(lambda: A.luu_phieu("Purchase Receipt", "PR-1", "{}")) or ""))
F.vai("SX QC")
dl = A.ds_tiep_nhan()
ten = [x["name"] for x in dl["ds"]]
kiem("chỉ phiếu NHÁP 14 ngày nhập kho hàng mua: phiếu nhập mua + hoá đơn mua có trừ kho, mới nhất trước",
     ten == ["PI-1", "PR-1"], ten)
kiem("… không có: phiếu quá 14 ngày, trả hàng NCC, NCC dịch vụ, hoá đơn không trừ kho, phiếu đã duyệt",
     not {"PR-CU", "PR-TRA", "PR-DV", "PI-KHONG-KHO", "PR-DUYET"} & set(ten))
x = next(x for x in dl["ds"] if x["name"] == "PR-1")
kiem("thẻ phiếu: NCC, số dòng có kết luận, cần kiểm xe (NCC thực phẩm)",
     (x["ncc"], x["loai_ncc"], x["so_dong"], x["xe_can"]) == ("Công ty NCC-SUA", NCC.TP, 2, True), x)
kiem("kho lập phiếu: luật W10 tự ép dòng đỗ (thiếu aflatoxin) Cách ly → 1/2 dòng có kết luận, nhưng CHƯA "
     "QC nào kiểm → vẫn 'chờ kiểm'", (x["da_kl"], x["nguoi_kiem"], x["xong"]) == (1, "", False), x)
kiem("hoá đơn mua: không có kiểm xe (BM.09.01 chỉ ở phiếu nhập mua)",
     next(x for x in dl["ds"] if x["name"] == "PI-1")["xe_can"] is False)
hai_do = [{"name": "PI-2-1", "idx": 1, "item_code": "DX", "item_name": "Đỗ xanh", "qty": 100, "uom": "Kg"},
          {"name": "PI-2-2", "idx": 2, "item_code": "DX", "item_name": "Đỗ xanh", "qty": 200, "uom": "Kg"}]
phieu("PI-2", dt="Purchase Invoice", update_stock=1, items=hai_do)
x = next(x for x in A.ds_tiep_nhan()["ds"] if x["name"] == "PI-2")
kiem("mọi dòng đã bị LUẬT ép Cách ly lúc kho lập phiếu, nhưng chưa QC nào kiểm → vẫn 'chờ kiểm'",
     (x["da_kl"], x["so_dong"], x["xong"]) == (2, 2, False), x)
F.bang("Purchase Invoice").pop("PI-2")
frappe.local.message_log.clear()

# ═══ 2. Mở phiếu ═════════════════════════════════════════════════════════
print("\n-- mở phiếu: NCC, giấy tờ, dòng hàng, kiểm xe --")
p = A.xem_phieu("Purchase Receipt", "PR-1")
kiem("NCC: loại, nguồn, đã duyệt, phiếu kiểm nghiệm năm còn hạn",
     (p["ncc_loai"], p["ncc_nguon"], p["ncc_duyet"], p["pkn"]) == (NCC.TP, NCC.TRONG_NUOC, True,
                                                                     {"so_hieu": "PKN-26/01", "het_han": "2027-03-01"}), p)
kiem("dòng hàng: số lượng, kho; sữa (nhóm con của 'Phụ liệu bột') bắt buộc COA; đỗ phải có aflatoxin",
     (p["dong"][0]["qty"], p["dong"][0]["kho"], p["dong"][0]["can_coa"], p["dong"][0]["can_aflatoxin"],
      p["dong"][1]["can_coa"], p["dong"][1]["can_aflatoxin"]) == (50, "Kho NVL - HG", True, False, False, True))
kiem("kiểm xe: áp dụng, đúng các mục của sx/qc/kiem_xe.py", p["xe"]["ap_dung"] is True
     and [m["f"] for m in p["xe"]["muc"]] == [f for f, _n in KX.MUC])
kiem("QC sửa được phiếu nháp, thêm ảnh được", p["sua"] and p["them_anh"])
F.bang("Stock Entry")["SE-1"] = {"name": "SE-1", "docstatus": 0, "items": []}
kiem("chứng từ khác phiếu mua (có thật) → chặn", "phiếu nhập mua" in (thu(lambda: A.xem_phieu("Stock Entry", "SE-1")) or ""))
kiem("hoá đơn mua không trừ kho / phiếu trả hàng → chặn",
     "không nhập kho" in (thu(lambda: A.xem_phieu("Purchase Invoice", "PI-KHONG-KHO")) or "")
     and "không nhập kho" in (thu(lambda: A.xem_phieu("Purchase Receipt", "PR-TRA")) or ""))
fx = {(f["dt"], f["fieldname"]): f for f in json.load(open("sx/fixtures/custom_field.json", encoding="utf-8"))}
kiem("lựa chọn của từng ô = đúng ô Select trên phiếu nhập mua VÀ hoá đơn mua (fixtures)",
     all(list(A.O_DONG[f]) == fx[(dt, f)]["options"].split("\n")
         for dt in ("Purchase Receipt Item", "Purchase Invoice Item") for f, k in A.O_DONG.items() if isinstance(k, tuple))
     and fx[("Purchase Receipt Item", "custom_do_am")]["fieldtype"] == "Float"
     and all(fx[("Purchase Receipt", f)]["options"].split("\n") == ["", KX.DAT, KX.KHONG_DAT] for f in A.XE_CHON))

# ═══ 3. Lưu: chỉ ô QC, luật như Desk ═════════════════════════════════════
print("\n-- lưu: chỉ ô QC, luật như Desk --")


def luu(ten, dong=None, xe=None, dt="Purchase Receipt", **k):
    p = {"dong": dong or [], **k}
    if xe is not None:
        p["xe"] = xe
    return A.luu_phieu(dt, ten, json.dumps(p))


XE_DAT = {"custom_xe_bien_so": "29C-123.45", "custom_xe_tai_xe": "Anh Ba",
          **{f: "Đạt" for f, _n in KX.MUC}}
r = luu("PR-1", [{"name": "PR-1-1", "custom_ncc_lo": " L2610 ", "custom_co_cq": "Có", "custom_coa_vi_sinh": "Có",
                  "custom_cam_quan_dat": "Đạt", "custom_ket_luan": "Đạt", "qty": 1, "rate": 1, "warehouse": "Kho X"}],
        xe=XE_DAT, ghi_chu_qc="Hàng khô, bao nguyên")
pr = F.bang("Purchase Receipt")["PR-1"]
kiem("ghi đúng ô QC của dòng (lô NCC cắt khoảng trắng), KHÔNG đụng số lượng / đơn giá / kho dù gửi kèm",
     (pr["items"][0]["custom_ncc_lo"], pr["items"][0]["custom_ket_luan"], pr["items"][0]["qty"], pr["items"][0]["rate"],
      pr["items"][0]["warehouse"]) == ("L2610", "Đạt", 50, 120000, "Kho NVL - HG"), pr["items"][0])
kiem("ghi người kiểm, ghi chú QC; kiểm xe đủ mục Đạt → kết luận xe Đạt, người kiểm xe = QC",
     (pr["custom_nguoi_kiem"], pr["custom_ghi_chu_qc"], pr["custom_xe_ket_luan"], pr["custom_xe_nguoi_kiem"],
      pr["custom_xe_bien_so"]) == ("qc@x", "Hàng khô, bao nguyên", "Đạt", "qc@x", "29C-123.45"))
kiem("luật giấy tờ chạy khi lưu: dòng sữa ghi 'Giấy tờ lô' theo phiếu kiểm nghiệm năm của NCC",
     "PKN-26/01" in (pr["items"][0].get("custom_giay_to") or "") and "PKN-26/01" in r["dong"][0]["giay_to"])
kiem("… dòng đỗ (nhóm phải có aflatoxin, chưa ghi) vẫn Cách ly ở kho cách ly, NÓI lý do trong kết quả",
     pr["items"][1]["custom_ket_luan"] == "Cách ly" and pr["items"][1]["warehouse"] == "Kho cách ly - HG"
     and any("Dòng 2 (DX): nhóm Đỗ phải có kết quả aflatoxin" in b for b in r["bao"]), r["bao"])
kiem("… lời cảnh báo không lẫn HTML", all("<" not in b for b in r["bao"]))
dl = A.ds_tiep_nhan()
x = next(x for x in dl["ds"] if x["name"] == "PR-1")
kiem("đủ kết luận + đã kiểm xe → chuyển xuống 'đã kiểm đủ'", x["xong"] and x["da_kl"] == 2
     and [y["name"] for y in dl["ds"]] == ["PI-1", "PR-1"])
phieu("PR-3", ngay="2026-10-09")
luu("PR-3", [{"name": "PR-3-1", "custom_ket_luan": "Đạt", "custom_coa_vi_sinh": "Có", "custom_cam_quan_dat": "Đạt"},
             {"name": "PR-3-2", "custom_ket_luan": "Đạt", "custom_aflatoxin": "Có", "custom_cam_quan_dat": "Đạt"}])
x = next(x for x in A.ds_tiep_nhan()["ds"] if x["name"] == "PR-3")
kiem("đủ kết luận, có người kiểm nhưng CHƯA kiểm xe (NCC thực phẩm) → vẫn 'chờ kiểm'",
     (x["da_kl"], x["nguoi_kiem"], x["xe_kl"], x["xong"]) == (2, "qc@x", "", False), x)
luu("PR-3", xe=XE_DAT)
kiem("… kiểm xe xong → 'đã kiểm đủ'", next(x for x in A.ds_tiep_nhan()["ds"] if x["name"] == "PR-3")["xong"] is True)
F.vai("SX QC", u="qc2@x")
luu("PR-3", xe={"custom_xe_sach": "Không đạt", "custom_xe_ghi_chu": "Kiểm lại: sàn xe ướt"})
kiem("QC khác kiểm lại xe → người kiểm xe là người vừa kiểm (không giữ tên người trước)",
     (F.bang("Purchase Receipt")["PR-3"]["custom_xe_nguoi_kiem"],
      F.bang("Purchase Receipt")["PR-3"]["custom_xe_ket_luan"]) == ("qc2@x", "Không đạt"))
F.vai("SX QC")
F.bang("Purchase Receipt").pop("PR-3")
frappe.local.message_log[:] = [{"message": "cũ"}, {"message": "<b>Dòng 1</b> (SUA):<br>chuyển <i>Cách ly</i>"},
                               json.dumps({"message": "Kiểm xe<br/>Không đạt"}), {"message": "  "}]
kiem("lời cảnh báo: chỉ phần mới của request, bỏ thẻ HTML, <br> thành xuống dòng, nhận cả bản JSON",
     A._bao_tu(1) == ["Dòng 1 (SUA):\nchuyển Cách ly", "Kiểm xe\nKhông đạt"], A._bao_tu(1))
frappe.local.message_log.clear()

frappe.local.message_log.clear()
loi = thu(lambda: luu("PR-1", [{"name": "PR-1-1", "custom_cam_quan_dat": "Không đạt", "custom_ket_luan": "Đạt"}]))
kiem("'Đạt' mà cảm quan Không đạt → CHẶN như trên Desk, không ghi gì",
     loi and "cảm quan 'Không đạt'" in loi and F.bang("Purchase Receipt")["PR-1"]["items"][0]["custom_cam_quan_dat"] == "Đạt",
     loi or "")
kiem("giá trị lạ ở ô chọn → chặn", "không hợp lệ" in (thu(lambda: luu("PR-1", [{"name": "PR-1-1", "custom_ket_luan": "Tốt"}])) or ""))
kiem("độ ẩm ngoài 0–100 / không phải số → chặn",
     thu(lambda: luu("PR-1", [{"name": "PR-1-2", "custom_do_am": 120}])) is not None
     and thu(lambda: luu("PR-1", [{"name": "PR-1-2", "custom_do_am": "abc"}])) is not None)
r = luu("PR-1", [{"name": "PR-1-2", "custom_do_am": "12,5", "custom_aflatoxin": "Có", "custom_ket_luan": "Đạt",
                  "custom_cam_quan_dat": "Đạt"}])
kiem("độ ẩm dấu phẩy → số; đỗ có aflatoxin → giữ Đạt", (F.bang("Purchase Receipt")["PR-1"]["items"][1]["custom_do_am"],
                                                     r["dong"][1]["custom_ket_luan"]) == (12.5, "Đạt"))
r = luu("PR-1", [{"name": "PR-1-1", "custom_coa_vi_sinh": "Không"}])
kiem("sữa (nhóm bắt buộc COA) mà COA = Không → ép Cách ly, nói lý do",
     r["dong"][0]["custom_ket_luan"] == "Cách ly" and any("COA" in b for b in r["bao"]), r["bao"])
r = luu("PR-1", [{"name": "PR-1-1", "custom_coa_vi_sinh": "Có", "custom_ket_luan": "Đạt"},
                 {"name": "PR-1-2", "custom_ket_luan": "Đạt"}], xe={"custom_xe_che_chan": "Không đạt"})
kiem("xe giao hàng Không đạt (một mục) → kết luận xe Không đạt, MỌI dòng Cách ly vào kho cách ly",
     r["xe"]["custom_xe_ket_luan"] == "Không đạt" and all(d["custom_ket_luan"] == "Cách ly" for d in r["dong"])
     and all(d["kho"] == "Kho cách ly - HG" for d in r["dong"])
     and any("KHÔNG ĐẠT" in b for b in r["bao"]), r["bao"])
kiem("kiểm xe giá trị lạ → chặn", thu(lambda: luu("PR-1", xe={"custom_xe_sach": "Tốt"})) is not None)
kiem("hoá đơn mua trừ kho: ghi được phần QC (không có kiểm xe)",
     luu("PI-1", [{"name": "PI-1-1", "custom_ket_luan": "Đạt", "custom_cam_quan_dat": "Đạt", "custom_coa_vi_sinh": "Có"}],
         dt="Purchase Invoice", xe=XE_DAT)["dong"][0]["custom_ket_luan"] == "Đạt"
     and "custom_xe_bien_so" not in F.bang("Purchase Invoice")["PI-1"])

print("\n-- thủ kho duyệt: luật on_submit như Desk --")
pr = F.get_doc("Purchase Receipt", "PR-1")
pr.submit()
sc = [s for s in F.bang("SX Su Co").values() if s.get("khoa_cu", "").startswith("PR-1#")]
kiem("duyệt phiếu QC đã kiểm trên điện thoại → lô Cách ly sinh phiếu sự cố như trên Desk",
     len(sc) == 2 and all(s["nguon"] == "Tiếp nhận NL" for s in sc), sc)
kiem("phiếu đã duyệt → QC không sửa được phần QC nữa",
     "đã duyệt" in (thu(lambda: luu("PR-1", [{"name": "PR-1-1", "custom_ket_luan": "Đạt"}])) or ""))
kiem("… vẫn mở xem được, không còn nút sửa", A.xem_phieu("Purchase Receipt", "PR-1")["sua"] is False)

# ═══ 4. Ảnh ══════════════════════════════════════════════════════════════
print("\n-- ảnh tiếp nhận --")
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()
JPG = base64.b64encode(b"\xff\xd8\xff" + b"1" * 64).decode()
kiem("không phải ảnh / base64 hỏng → chặn",
     "không phải ảnh" in (thu(lambda: A.them_anh("Purchase Receipt", "PR-1", json.dumps([base64.b64encode(b"PDF").decode()]))) or "")
     and "hỏng" in (thu(lambda: A.them_anh("Purchase Receipt", "PR-1", json.dumps(["@@@"]))) or ""))
kiem("quá 4 ảnh một lần → chặn", thu(lambda: A.them_anh("Purchase Receipt", "PR-1", json.dumps([PNG] * 5))) is not None)
r = A.them_anh("Purchase Receipt", "PR-1", json.dumps([PNG, JPG]))
tep = [t for t in F.bang("File").values() if t.get("attached_to_name") == "PR-1"]
kiem("ảnh ghi được cả sau khi duyệt (bằng chứng): File riêng tư gắn đúng phiếu",
     r["so_anh"] == 2 and len(tep) == 2 and all(t["is_private"] == 1 and t["attached_to_doctype"] == "Purchase Receipt"
                                               for t in tep) and tep[0]["file_name"].endswith(".png"))
A.them_anh("Purchase Receipt", "PR-1", json.dumps([PNG] * 4))
kiem("tối đa 8 ảnh một phiếu", "tối đa 8" in (thu(lambda: A.them_anh("Purchase Receipt", "PR-1", json.dumps([PNG] * 3))) or ""))
F.vai("ISO Manager")
ds = A.anh_phieu("Purchase Receipt", "PR-1")
kiem("xem ảnh qua API (QC / Ban ISO không đọc được file riêng tư của phiếu mua trên Desk)",
     len(ds) == 6 and ds[0]["url"].startswith("data:image/png;base64,") and ds[1]["url"].startswith("data:image/jpeg;base64,"))
kiem("Ban ISO không thêm ảnh được (chỉ xem)", thu(lambda: A.them_anh("Purchase Receipt", "PR-1", json.dumps([PNG]))) is not None)
F.vai("SX QC")
F.bang("Purchase Receipt")["PR-1"]["docstatus"] = 2
kiem("phiếu đã huỷ → không mở / không thêm ảnh", thu(lambda: A.xem_phieu("Purchase Receipt", "PR-1")) is not None
     and thu(lambda: A.them_anh("Purchase Receipt", "PR-1", json.dumps([PNG]))) is not None)

# ═══ 5. Màn hình ═════════════════════════════════════════════════════════
print("\n-- màn hình --")
js = open("sx/public/sx/views/qc_tiepnhan.js", encoding="utf-8").read()
for m in sorted(set(re.findall(r"sx\.api\.qc_tiepnhan\.(\w+)", js))):
    kiem(f"màn Tiếp nhận NL gọi method có thật: {m}", callable(getattr(A, m, None)))
qcjs = open("sx/public/sx/views/qc.js", encoding="utf-8").read()
home = open("sx/public/sx/views/qc_home.js", encoding="utf-8").read()
kiem("route #/qc/tiepnhan + nút ở lưới cuối màn Hôm nay (tab Hôm nay sáng khi ở màn này)",
     "tiepnhan: '/assets/sx/sx/views/qc_tiepnhan.js'" in qcjs and "'tiepnhan'" in qcjs.split("SO_HOM_NAY =")[1].split("\n")[0]
     and "'#/qc/tiepnhan'" in home)
kiem("README ghi cách tạm (role kho cho QC)", "Stock User" in open("README.md", encoding="utf-8").read().split("(D160 — W33)")[1][:3000])

F.ket_thuc("TIEPNHANQC")
