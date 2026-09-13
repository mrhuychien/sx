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

# ═══ Fixtures ═══
fixtures = [
    {
        "doctype": "Role",
        # Danh sách này phải KHỚP fixtures/role.json. Nó chỉ áp lúc `bench
        # export-fixtures`, nên thiếu một tên thì lần export sau lặng lẽ XOÁ role đó
        # khỏi file, và site cài mới sau đó thiếu role mà không ai biết.
        "filters": [
            ["name", "in", ["SX Ghi So", "SX Vao Hop", "SX Thu Kho", "SX Quan Ly",
                            "SX QC", "SX QC Packing", "ISO Manager",
                            "Production Manager", "Warehouse"]]
        ],
    },
    # Hai module: SX (cũ) và QC (D85+). Để "=" "SX" thì lần export-fixtures sau
    # lặng lẽ xoá sạch custom field của QC khỏi file.
    {"doctype": "Custom Field", "filters": [["module", "in", ["SX", "QC"]]]},
    {"doctype": "Print Format", "filters": [["module", "in", ["SX", "QC"]]]},
]

# www/sx.html tu serve /sx
website_route_rules = []
