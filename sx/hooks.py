app_name = "sx"
app_title = "SX"
app_publisher = "Rong Vang Hoang Gia"
app_description = "Portal San Xuat RVHG - so hoa + truy xuat nguon goc banh & bot dau xanh"
app_email = "mrhuychien@gmail.com"
app_license = "MIT"
required_apps = ["frappe", "erpnext"]

# ═══ DocType Events ═══
doc_events = {
    "SX Ngay San Xuat": {"on_cancel": "sx.api.chot.on_cancel_ngay"},
    "SX Nhap Bot": {
        "on_submit": "sx.api.tang1.on_submit_nhap_bot",
        "on_cancel": "sx.api.tang1.on_cancel_nhap_bot",
    },
    # BM.07.03 — kiểm nguyên liệu đầu vào. Gắn vào Purchase Invoice chứ không
    # Purchase Receipt: kho nguyên liệu nhập thẳng bằng hoá đơn mua.
    "Purchase Invoice": {
        "validate": "sx.qc.tiep_nhan.validate",
        "on_submit": "sx.qc.tiep_nhan.on_submit",
    },
}

# Tạo role còn thiếu — chỉ TẠO, không sửa role đã có (D105).
after_install = "sx.setup.dam_bao_role"
after_migrate = ["sx.setup.dam_bao_role"]

# ═══ Fixtures ═══
fixtures = [
    # Role KHÔNG còn là fixture (D105): fixtures bị xoá-tạo-lại mỗi lần migrate,
    # và tạo lại role là Frappe đăng xuất người giữ role đó. Xem sx.setup.dam_bao_role.
    # Hai module: SX (cũ) và QC (D85+). Để "=" "SX" thì lần export-fixtures sau
    # lặng lẽ xoá sạch custom field của QC khỏi file.
    {"doctype": "Custom Field", "filters": [["module", "in", ["SX", "QC"]]]},
    {"doctype": "Print Format", "filters": [["module", "in", ["SX", "QC"]]]},
]

# www/sx.html tu serve /sx
website_route_rules = []
