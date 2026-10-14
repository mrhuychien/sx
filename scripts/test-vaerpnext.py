"""D205 — vá ERPNext: get_item_details → update_stock sập khi KHÔNG kèm phiếu (màn POS, mã có lô).

Lỗi thật (14/10/2026, ERPNext 16.15.1): vào POS thêm TH170 (mã vừa bật lô ở kiểm kê 12/10) →
  erpnext/stock/get_item_details.py update_stock: doc.get("selling_price_list")
  AttributeError: 'NoneType' object has no attribute 'get'
Bài này chạy ĐÚNG mã update_stock của ERPNext 16.15.1 (chép nguyên văn bên dưới — hàm thuần, chỉ giả các hàm
nó gọi tới): trước vá tái hiện đúng lỗi, sau sx.va_erpnext.va() chọn lô bình thường; có phiếu thật thì bản vá
không đụng gì.

Chạy: python3 scripts/test-vaerpnext.py   (verify.sh gọi sẵn)
"""

import ast
import importlib.util
import os
import sys
import types

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# ── Mã gốc ERPNext 16.15.1 (erpnext/stock/get_item_details.py) — KHÔNG sửa ──
UPSTREAM = r'''
def update_stock(ctx, out, doc=None):
	from erpnext.stock.doctype.batch.batch import get_available_batches
	from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos_for_outward

	if (
		(
			ctx.get("doctype") in ["Delivery Note", "POS Invoice"]
			or (ctx.get("doctype") == "Sales Invoice" and ctx.get("update_stock"))
		)
		and out.warehouse
		and out.stock_qty > 0
	):
		if doc and isinstance(doc, dict):
			doc = frappe._dict(doc)

		kwargs = frappe._dict(
			{
				"item_code": ctx.item_code,
				"warehouse": ctx.warehouse,
				"based_on": frappe.get_single_value("Stock Settings", "pick_serial_and_batch_based_on"),
				"sabb_voucher_no": doc.get("name") if doc else None,
				"sabb_voucher_detail_no": ctx.child_docname,
				"sabb_voucher_type": ctx.doctype,
				"pick_reserved_items": True,
				"qty": out.stock_qty,
			}
		)

		if ctx.get("doctype") == "Delivery Note":
			kwargs["against_sales_order"] = ctx.get("against_sales_order")

		if ctx.get("ignore_serial_nos"):
			kwargs["ignore_serial_nos"] = ctx.get("ignore_serial_nos")

		qty = out.stock_qty
		batches = []
		if out.has_batch_no and not ctx.get("batch_no"):
			batches = get_available_batches(kwargs)
			if doc:
				filter_batches(batches, doc)

			for batch_no, batch_qty in batches.items():
				rate = get_batch_based_item_price(
					{"price_list": doc.get("selling_price_list"), "uom": out.uom, "batch_no": batch_no},
					out.item_code,
				)
				if batch_qty >= qty:
					out.update({"batch_no": batch_no, "actual_batch_qty": qty})
					if rate:
						out.update({"rate": rate, "price_list_rate": rate})
					break
				else:
					qty -= batch_qty

				out.update({"batch_no": batch_no, "actual_batch_qty": batch_qty})
				if rate:
					out.update({"rate": rate, "price_list_rate": rate})

		if out.has_serial_no and out.has_batch_no and has_incorrect_serial_nos(ctx, out):
			kwargs["batches"] = [ctx.get("batch_no")] if ctx.get("batch_no") else [out.get("batch_no")]
			serial_nos = get_serial_nos_for_outward(kwargs)
			serial_nos = get_filtered_serial_nos(serial_nos, doc)

			out["serial_no"] = "\n".join(serial_nos[: cint(out.stock_qty)])

		elif out.has_serial_no and not ctx.get("serial_no"):
			serial_nos = get_serial_nos_for_outward(kwargs)
			serial_nos = get_filtered_serial_nos(serial_nos, doc)

			out["serial_no"] = "\n".join(serial_nos[: cint(out.stock_qty)])


def has_incorrect_serial_nos(ctx, out):
	from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos

	if not ctx.get("serial_no"):
		return True

	serial_nos = get_serial_nos(ctx.get("serial_no"))
	if len(serial_nos) != out.get("stock_qty"):
		return True

	return False


def filter_batches(batches, doc):
	for row in doc.get("items"):
		if row.get("batch_no") in batches:
			batches[row.get("batch_no")] -= row.get("qty")
			if batches[row.get("batch_no")] <= 0:
				del batches[row.get("batch_no")]


def get_filtered_serial_nos(serial_nos, doc, table=None):
	from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos

	if not table:
		table = "items"

	for row in doc.get(table):
		if row.get("serial_no"):
			for serial_no in get_serial_nos(row.get("serial_no")):
				if serial_no in serial_nos:
					serial_nos.remove(serial_no)

	return serial_nos
'''

hong = 0


def kiem(ten, dk, ct=""):
    global hong
    if not dk:
        hong += 1
    print(f"  {'ok  ' if dk else 'HỎNG'} {ten}{(' — ' + str(ct)) if ct else ''}")


class _dict(dict):
    def __getattr__(self, k):
        if k.startswith("__"):
            raise AttributeError(k)
        return self.get(k)

    def __setattr__(self, k, v):
        self[k] = v


LOG, LO, GIA_LO, GOI_GIA, GOI_LO = [], {}, {}, [], []
frappe = types.ModuleType("frappe")
frappe._dict = _dict
frappe.get_single_value = lambda dt, f: "FIFO"
frappe.log_error = lambda **k: LOG.append(k)
frappe.get_traceback = lambda: "traceback"
fu = types.ModuleType("frappe.utils")
fu.cint = lambda v: int(float(v or 0))
frappe.utils = fu
sys.modules["frappe"] = frappe
sys.modules["frappe.utils"] = fu

for g in ("erpnext", "erpnext.stock", "erpnext.stock.doctype", "erpnext.stock.doctype.batch",
          "erpnext.stock.doctype.serial_no", "sx"):
    m = types.ModuleType(g)
    m.__path__ = []
    sys.modules[g] = m
bt = types.ModuleType("erpnext.stock.doctype.batch.batch")
bt.get_available_batches = lambda kw: GOI_LO.append(dict(kw)) or dict(LO)
sys.modules["erpnext.stock.doctype.batch.batch"] = bt
sr = types.ModuleType("erpnext.stock.doctype.serial_no.serial_no")
sr.get_serial_nos_for_outward = lambda kw: ["S1", "S2", "S3"]
sr.get_serial_nos = lambda s: [x for x in str(s or "").split("\n") if x]
sys.modules["erpnext.stock.doctype.serial_no.serial_no"] = sr

gid = types.ModuleType("erpnext.stock.get_item_details")
gid.frappe = frappe
gid.cint = fu.cint
gid.get_batch_based_item_price = lambda pctx, item_code: GOI_GIA.append(dict(pctx)) or GIA_LO.get(pctx["batch_no"], 0.0)
exec(compile(UPSTREAM, "erpnext/stock/get_item_details.py@16.15.1", "exec"), gid.__dict__)
sys.modules["erpnext.stock.get_item_details"] = gid
sys.modules["erpnext.stock"].get_item_details = gid
GOC = gid.update_stock

sp = importlib.util.spec_from_file_location("sx.va_erpnext", "sx/va_erpnext.py")
V = importlib.util.module_from_spec(sp)
sys.modules["sx.va_erpnext"] = V
sp.loader.exec_module(V)


def ctx_pos(**k):
    return _dict(dict(item_code="TH170", doctype="POS Invoice", warehouse="CH Tuệ Tĩnh - HGC",
                      price_list="Bảng giá Online", name="new-pos-invoice-x"), **k)


def out_lo(**k):
    return _dict(dict(item_code="TH170", warehouse="CH Tuệ Tĩnh - HGC", stock_qty=1, uom="Hộp",
                      has_batch_no=1), **k)


print("-- trước vá: tái hiện đúng lỗi trên site --")
LO.update({"TH170-HSD100727": 50})
try:
    GOC(ctx_pos(), out_lo(), None)
    kiem("mã gốc ERPNext 16.15.1 sập khi không kèm phiếu (mã có lô, POS)", False)
except AttributeError as e:
    kiem("mã gốc ERPNext 16.15.1 sập khi không kèm phiếu (mã có lô, POS)",
         "'NoneType' object has no attribute 'get'" in str(e), str(e))

print("\n-- sau vá --")
V.va()
kiem("update_stock đã bọc bản vá, giữ mã gốc", getattr(gid.update_stock, "_sx_va", False)
     and gid.update_stock.__wrapped__ is GOC)
GOI_GIA.clear(); GOI_LO.clear()
o = out_lo()
gid.update_stock(ctx_pos(), o, None)
kiem("không kèm phiếu: tự chọn lô như thường (lô đủ số)",
     (o.batch_no, o.actual_batch_qty) == ("TH170-HSD100727", 1), o)
kiem("giá theo lô tra theo BẢNG GIÁ đang bán (ctx.price_list)", GOI_GIA and GOI_GIA[-1]["price_list"] == "Bảng giá Online",
     GOI_GIA)
kiem("phiếu tạm không đổi cách tìm lô (không gắn số phiếu)", GOI_LO and GOI_LO[-1]["sabb_voucher_no"] is None, GOI_LO)
GIA_LO["TH170-HSD100727"] = 99000.0
o = out_lo()
gid.update_stock(ctx_pos(), o, None)
kiem("lô có giá riêng → lấy giá lô như ERPNext vẫn làm khi có phiếu",
     (o.rate, o.price_list_rate) == (99000.0, 99000.0), o)
GIA_LO.clear()
LO.clear(); LO.update({"A": 2, "B": 5})
o = out_lo()
gid.update_stock(ctx_pos(), o, {"name": "POS-1", "selling_price_list": "Bảng giá lẻ",
                                 "items": [{"batch_no": "A", "qty": 2}]})
kiem("CÓ phiếu thật: bản vá không đụng — phiếu đã lấy hết lô A thì chọn lô B, giá theo bảng giá của phiếu",
     o.batch_no == "B" and GOI_GIA[-1]["price_list"] == "Bảng giá lẻ" and GOI_LO[-1]["sabb_voucher_no"] == "POS-1",
     (o, GOI_GIA[-1]))
o = out_lo(has_batch_no=0, has_serial_no=1)
gid.update_stock(ctx_pos(), o, None)
kiem("mã có số serial, không kèm phiếu: cũng không sập (cùng lỗi ở nhánh serial)", o.serial_no == "S1", o)
o = out_lo()
gid.update_stock(ctx_pos(doctype="Sales Order"), o, None)
kiem("chứng từ không xuất kho (Sales Order): không chọn lô, không lỗi", not o.batch_no)

print("\n-- an toàn của hook --")
V.va()
kiem("gọi lại nhiều lần: vẫn MỘT lớp bọc", gid.update_stock.__wrapped__ is GOC)
V._DA_VA = False
V.va()
kiem("áp lại khi đã vá: không bọc chồng", gid.update_stock.__wrapped__ is GOC)
V._DA_VA = False
goc_va = V._va_update_stock
V._va_update_stock = lambda: 1 / 0
try:
    V.va()
    kiem("bản vá hỏng thì ghi Error Log, KHÔNG làm hỏng yêu cầu (hook chạy trước mọi yêu cầu)",
         len(LOG) == 1 and "D205" in LOG[0]["title"], LOG)
except Exception as e:
    kiem("bản vá hỏng thì ghi Error Log, KHÔNG làm hỏng yêu cầu (hook chạy trước mọi yêu cầu)", False, e)
V._va_update_stock = goc_va
hk = open("sx/hooks.py", encoding="utf-8").read()
# Đọc danh sách hook (D210 thêm sx.do_toc.bat_dau vào before_request) — bản vá phải đứng ĐẦU, chạy trước mọi hook khác.
DS_HOOK = {t.id: ast.literal_eval(n.value) for n in ast.parse(hk).body if isinstance(n, ast.Assign)
           and isinstance(n.value, ast.List) for t in n.targets if isinstance(t, ast.Name)}
kiem("hook before_request (đứng đầu) + before_job gọi sx.va_erpnext.va",
     DS_HOOK.get("before_request", [None])[0] == "sx.va_erpnext.va"
     and "sx.va_erpnext.va" in DS_HOOK.get("before_job", []))

print("VAERPNEXT-OK" if not hong else f"VAERPNEXT: {hong} HỎNG")
sys.exit(1 if hong else 0)
